# SPDX-License-Identifier: Apache-2.0
"""DXF entities to curve rows (research 21, Methods 1 to 4; REQ-IO-001, 003, 004, 009 to 016).

The loop over ezdxf entities is Python, since ezdxf yields Python objects; each entity's geometry
is extracted in the drawing's units through its OCS, then scaled once to millimetres (D-028). Arc
rows from polyline bulges are built in geometry2d's C++ kernel over all of an entity's segments at
once (`rows_from_bulges`); an ARC or CIRCLE entity's end points come from its angles through
Python's `math` (libm) once per entity (SPEC, split rule)."""

import math
from collections import Counter
from dataclasses import dataclass

import numpy as np
from ezdxf.entities.arc import Arc
from ezdxf.entities.circle import Circle
from ezdxf.entities.dxfgfx import DXFGraphic
from ezdxf.entities.line import Line
from ezdxf.entities.lwpolyline import LWPolyline
from ezdxf.entities.polyline import Polyline
from numpy.typing import NDArray

from splintercam.foundation import Context, Severity
from splintercam.geometry2d import RowStatus, rows_from_bulges

from . import _diagnostics as diag


class _Reject(Exception):  # noqa: N818 (an internal signal, not an error condition)
    """An entity io cannot read: its diagnostic code and message (REQ-IO-011, 016)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_SEG_BITS = 16
_SEG_MAX = 1 << _SEG_BITS  # the most segments one entity may have (REQ-IO-016)
_MAX_COORD_MM = 1.0e9  # DEC-G2D-019, DEC-G2D-016's half-extent (REQ-IO-011)
_ROW_WIDTH = 7
_READ_TYPES = frozenset({"LINE", "ARC", "CIRCLE", "LWPOLYLINE", "POLYLINE"})


@dataclass(frozen=True, slots=True)
class Candidate:
    """One read entity's geometry in drawing units, before scaling and chaining. `kind` is
    "line", "arc" or "poly"; `points` are the 2D OCS-to-WCS points (lines and polylines) or the
    arc's [p0, p1, centre]; `extra` are the bulges (poly) or the sweep in radians (arc); `closed`
    applies to polylines; `zs` are the world z values for planarity voting (REQ-IO-010)."""

    index: int
    handle: str
    type_name: str
    kind: str
    points: NDArray[np.float64]
    extra: NDArray[np.float64]
    closed: bool
    zs: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class Scan:
    """What a scan of model space found: the read candidates, a loose bounding box of their raw
    points in drawing units (for `DXF_NO_UNITS`, REQ-IO-006), and whether any read entity was on
    the selected layer (REQ-IO-025)."""

    candidates: list[Candidate]
    loose_box_drawing: tuple[float, float, float, float] | None
    any_read: bool


def _polyline_subtype(entity: Polyline) -> str | None:
    """None for a plain 2D polyline io reads, else the subtype name a diagnostic reports it as
    (REQ-IO-003: ezdxf reports every mode as POLYLINE)."""
    if entity.is_3d_polyline:
        return "3D POLYLINE"
    if entity.is_poly_face_mesh:
        return "POLYFACE MESH"
    if entity.is_polygon_mesh:
        return "POLYGON MESH"
    flags = int(entity.dxf.flags)
    if flags & 4:
        return "spline-fit POLYLINE"
    if flags & 2:
        return "curve-fit POLYLINE"
    return None


def _type_name(entity: DXFGraphic) -> tuple[str, bool]:
    """The entity's reported type name and whether io reads it."""
    dxftype = entity.dxftype()
    if isinstance(entity, Polyline):
        subtype = _polyline_subtype(entity)
        return (dxftype, True) if subtype is None else (subtype, False)
    return (dxftype, dxftype in _READ_TYPES)


def _extrusion_sign(extrusion: tuple[float, float, float], eps_ang: float) -> int | None:
    """+1 for an extrusion parallel to +z, -1 for -z (mirrored), None otherwise (REQ-IO-009).
    Parallel means the off-axis component is within sin(eps_ang) of the axis after normalising;
    compared as squares with eps_ang itself (sin x = x to far below float precision at eps_ang =
    1e-9), so only products and a comparison decide it, never libm sin (D-055; ours)."""
    ex, ey, ez = extrusion
    norm_sq = ex * ex + ey * ey + ez * ez
    if norm_sq == 0.0:
        return None
    if (ex * ex + ey * ey) > eps_ang * eps_ang * norm_sq:
        return None
    return 1 if ez > 0.0 else -1


def _finite(*values: float) -> None:
    if not all(math.isfinite(value) for value in values):
        raise _Reject(diag.DXF_ENTITY_INVALID, "holds a value that is not finite")


@dataclass(frozen=True, slots=True)
class _Meta:
    """An entity's identity for a Candidate and its diagnostics: its model-space index, DXF handle
    and reported type name (REQ-IO-016, 028)."""

    index: int
    handle: str
    type_name: str


def _line(entity: Line, meta: _Meta) -> Candidate:
    sx, sy, sz = (float(c) for c in entity.dxf.start)
    ex, ey, ez = (float(c) for c in entity.dxf.end)
    _finite(sx, sy, sz, ex, ey, ez)
    points = np.array([[sx, sy], [ex, ey]], dtype=np.float64)
    return Candidate(meta.index, meta.handle, meta.type_name, "line", points, np.empty(0),
                     False, (sz, ez))  # fmt: skip


def _nearly_closed(p0: tuple[float, float], p1: tuple[float, float], sweep: float, r: float,
                   eps: float) -> bool:  # fmt: skip
    # REQ-G2D-049: a sweep over π whose ends meet within eps and whose missing arc is within eps.
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    chord = math.sqrt(dx * dx + dy * dy)  # sqrt of squares, never hypot (D-055)
    return chord <= eps and abs(sweep) > math.pi and (math.tau - abs(sweep)) * r <= eps


def _arc(entity: Arc, meta: _Meta, mirror: bool, eps: float) -> Candidate:
    cx, cy, cz = (float(c) for c in entity.dxf.center)
    radius = float(entity.dxf.radius)
    a0, a1 = float(entity.dxf.start_angle), float(entity.dxf.end_angle)
    _finite(cx, cy, cz, radius, a0, a1)
    sweep_deg = (a1 - a0) % 360.0
    full = sweep_deg == 0.0
    sweep = math.tau if full else math.radians(sweep_deg)
    p0 = (cx + radius * math.cos(math.radians(a0)), cy + radius * math.sin(math.radians(a0)))
    p1 = p0 if full else (cx + radius * math.cos(math.radians(a1)),
                          cy + radius * math.sin(math.radians(a1)))  # fmt: skip
    if not full and _nearly_closed(p0, p1, sweep, radius, eps):
        p1, sweep = p0, math.tau
    return _arc_candidate(meta, (p0, p1, (cx, cy)), cz, sweep, mirror)


def _circle(entity: Circle, meta: _Meta, mirror: bool) -> Candidate:
    cx, cy, cz = (float(c) for c in entity.dxf.center)
    radius = float(entity.dxf.radius)
    _finite(cx, cy, cz, radius)
    p0 = (cx + radius, cy)
    return _arc_candidate(meta, (p0, p0, (cx, cy)), cz, math.tau, mirror)


def _arc_candidate(meta: _Meta, triple: tuple[tuple[float, float], ...], cz: float, sweep: float,
                   mirror: bool) -> Candidate:  # fmt: skip
    # Mirrored OCS (-z extrusion): x -> -x, the elevation's world z -> -z, the sweep reverses
    # (REQ-IO-009, 013). P1 keeps P0 for a full circle.
    p0, p1, centre = triple
    if mirror:
        p0, p1, centre, sweep = (-p0[0], p0[1]), (-p1[0], p1[1]), (-centre[0], centre[1]), -sweep
    points = np.array([p0, p1, centre], dtype=np.float64)
    world_z = -cz if mirror else cz
    return Candidate(meta.index, meta.handle, meta.type_name, "arc", points, np.array([sweep]),
                     False, (world_z,))  # fmt: skip


@dataclass(frozen=True, slots=True)
class _Poly:
    """A polyline's vertices before chaining: `xy` (n, 2), the per-vertex `bulges` (n,), the closed
    flag and the vertices' world z values `zs`."""

    xy: NDArray[np.float64]
    bulges: NDArray[np.float64]
    closed: bool
    zs: tuple[float, ...]


def _polyline(meta: _Meta, poly: _Poly, mirror: bool) -> Candidate:
    xy, bulges, zs = poly.xy, poly.bulges, poly.zs
    _finite(*xy.ravel().tolist(), *bulges.tolist(), *zs)
    if xy.shape[0] < 2:
        raise _Reject(diag.DXF_ENTITY_INVALID, "polyline with fewer than two vertices")
    n_seg = xy.shape[0] if poly.closed else xy.shape[0] - 1
    if n_seg > _SEG_MAX:
        raise _Reject(
            diag.DXF_ENTITY_TOO_LARGE, f"polyline with {n_seg} segments (limit {_SEG_MAX})"
        )
    if mirror:
        xy = xy.copy()
        xy[:, 0] = -xy[:, 0]
        bulges = -bulges
        zs = tuple(-z for z in zs)
    return Candidate(meta.index, meta.handle, meta.type_name, "poly", xy, bulges, poly.closed, zs)


def _lwpolyline(entity: LWPolyline, meta: _Meta, mirror: bool) -> Candidate:
    pts = entity.get_points("xyb")
    xy = np.array([(float(p[0]), float(p[1])) for p in pts], dtype=np.float64).reshape(-1, 2)
    bulges = np.array([float(p[2]) for p in pts], dtype=np.float64)
    elevation = float(entity.dxf.elevation)
    return _polyline(meta, _Poly(xy, bulges, bool(entity.closed), (elevation,)), mirror)


def _polyline2d(entity: Polyline, meta: _Meta, mirror: bool) -> Candidate:
    locations = [vertex.dxf.location for vertex in entity.vertices]
    xy = np.array([(float(loc.x), float(loc.y)) for loc in locations], dtype=np.float64).reshape(
        -1, 2
    )
    bulges = np.array([float(vertex.dxf.bulge) for vertex in entity.vertices], dtype=np.float64)
    zs = tuple(float(loc.z) for loc in locations)
    return _polyline(meta, _Poly(xy, bulges, bool(entity.is_closed), zs), mirror)


def _extract(entity: DXFGraphic, index: int, type_name: str, eps_len: float,
             eps_ang: float) -> Candidate:  # fmt: skip
    meta = _Meta(index, str(entity.dxf.handle), type_name)
    if isinstance(entity, Line):
        return _line(entity, meta)
    extrusion = entity.dxf.extrusion
    sign = _extrusion_sign((float(extrusion.x), float(extrusion.y), float(extrusion.z)), eps_ang)
    if sign is None:
        raise _Reject(diag.DXF_NOT_PLANAR, "extrusion is not parallel to +-z")
    mirror = sign < 0
    if isinstance(entity, Arc):
        return _arc(entity, meta, mirror, eps_len)
    if isinstance(entity, Circle):
        return _circle(entity, meta, mirror)
    if isinstance(entity, LWPolyline):
        return _lwpolyline(entity, meta, mirror)
    if isinstance(entity, Polyline):
        return _polyline2d(entity, meta, mirror)
    raise _Reject(diag.DXF_ENTITY_INVALID, "unreadable entity")  # unreachable: _type_name gates it


def _loose_box(candidates: list[Candidate]) -> tuple[float, float, float, float] | None:
    # A loose box of the raw points in drawing units for DXF_NO_UNITS (REQ-IO-006, ours): arc
    # candidates add centre ± radius, enough to tell a 100-unit part from a 4-unit one.
    xs: list[float] = []
    ys: list[float] = []
    for cand in candidates:
        xs.extend(cand.points[:, 0].tolist())
        ys.extend(cand.points[:, 1].tolist())
        if cand.kind == "arc":
            (px, py), (cx, cy) = cand.points[0], cand.points[2]
            radius = math.hypot(px - cx, py - cy)
            xs.extend((cx - radius, cx + radius))
            ys.extend((cy - radius, cy + radius))
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def scan(entities: list[DXFGraphic], layer: str | None, ctx: Context,
         collector: diag.Collector) -> Scan:  # fmt: skip
    """Classify model-space entities, extract the readable ones in drawing units, and report the
    skipped types and the rejected entities (REQ-IO-001, 003, 010, 011, 016, 025)."""
    eps_len, eps_ang = ctx.tolerances.length_eps_mm, ctx.tolerances.angle_eps_rad
    skipped: Counter[str] = Counter()
    candidates: list[Candidate] = []
    any_read = False
    for index, entity in enumerate(entities):
        type_name, readable = _type_name(entity)
        if layer is not None and entity.dxf.layer != layer:
            continue
        if not readable:
            skipped[type_name] += 1
            continue
        any_read = True
        try:
            candidates.append(_extract(entity, index, type_name, eps_len, eps_ang))
        except _Reject as reject:
            message = f"{type_name} (handle {entity.dxf.handle}) {reject.message}"
            collector.entity(reject.code, Severity.WARNING, index, 0, message)
    for type_name, count in skipped.items():
        collector.skipped(type_name, count)
    return Scan(candidates, _loose_box(candidates), any_read)


def _reference_z(candidates: list[Candidate], factor: float, eps: float) -> float:
    # The world z (in mm) with the most votes; ties go to the value voted first in model order
    # (REQ-IO-010). One vote per candidate whose own z values agree within eps_len.
    counter: Counter[float] = Counter()
    order: dict[float, int] = {}
    for index, cand in enumerate(candidates):
        zs = [z * factor for z in cand.zs]
        if max(zs) - min(zs) <= eps:
            counter[zs[0]] += 1
            order.setdefault(zs[0], index)
    if not counter:
        return 0.0
    return max(counter, key=lambda value: (counter[value], -order[value]))


def _planar(cand: Candidate, reference: float, factor: float, eps: float) -> bool:
    return all(abs(z * factor - reference) <= eps for z in cand.zs)


def _line_rows(cand: Candidate, factor: float) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    (x0, y0), (x1, y1) = cand.points * factor
    rows = np.array([[x0, y0, x1, y1, np.nan, np.nan, 0.0]], dtype=np.float64)
    return rows, np.array([0], dtype=np.int64)


def _arc_rows(cand: Candidate, factor: float) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    (x0, y0), (x1, y1), (cx, cy) = cand.points * factor
    rows = np.array([[x0, y0, x1, y1, cx, cy, float(cand.extra[0])]], dtype=np.float64)
    return rows, np.array([0], dtype=np.int64)


def _poly_rows(cand: Candidate, factor: float, ctx: Context
               ) -> tuple[NDArray[np.float64], NDArray[np.int64], bool]:  # fmt: skip
    xy = cand.points * factor
    n = xy.shape[0]
    starts = np.arange(n if cand.closed else n - 1, dtype=np.int64)
    nexts = (starts + 1) % n if cand.closed else starts + 1
    p0, p1, bulges = xy[starts], xy[nexts], cand.extra[starts]
    nonzero = (p1[:, 0] != p0[:, 0]) | (p1[:, 1] != p0[:, 1])  # exact zero-chord drop (D-055)
    built = rows_from_bulges(p0[nonzero], p1[nonzero], bulges[nonzero], ctx)
    ok = built.status == RowStatus.OK
    dropped = bool((~nonzero).any() or (~ok).any())
    return built.rows[ok], starts[nonzero][ok], dropped


def _degenerate_mask(rows: NDArray[np.float64], eps: float) -> NDArray[np.bool_]:
    # A line of chord <= eps, a full circle of radius <= eps, or an arc of length |sweep|*r <= eps
    # (REQ-IO-015). Lines carry a NaN centre, so r is used only where the row is an arc.
    sweep = rows[:, 6]
    line, full = sweep == 0.0, np.abs(sweep) == math.tau
    chord = np.sqrt((rows[:, 2] - rows[:, 0]) ** 2 + (rows[:, 3] - rows[:, 1]) ** 2)
    radius = np.sqrt((rows[:, 0] - rows[:, 4]) ** 2 + (rows[:, 1] - rows[:, 5]) ** 2)
    length = np.where(line, chord, np.where(full, radius, np.abs(sweep) * radius))
    return length <= eps  # sqrt of squares, never hypot (D-055)


def _magnitude_ok(rows: NDArray[np.float64]) -> bool:
    coords = rows[:, :6]
    finite = coords[np.isfinite(coords)]
    max_coord = float(np.abs(finite).max()) if finite.size else 0.0
    arc = rows[:, 6] != 0.0
    radii = np.sqrt((rows[arc, 0] - rows[arc, 4]) ** 2 + (rows[arc, 1] - rows[arc, 5]) ** 2)
    max_radius = float(radii.max()) if radii.size else 0.0
    return max_coord <= _MAX_COORD_MM and max_radius <= _MAX_COORD_MM


def _build_candidate(cand: Candidate, factor: float, eps: float, ctx: Context
                     ) -> tuple[NDArray[np.float64], NDArray[np.int64], bool]:  # fmt: skip
    pre_degenerate = False
    if cand.kind == "line":
        rows, segs = _line_rows(cand, factor)
    elif cand.kind == "arc":
        rows, segs = _arc_rows(cand, factor)
    else:
        rows, segs, pre_degenerate = _poly_rows(cand, factor, ctx)
    if not _magnitude_ok(rows):
        raise _Reject(diag.DXF_ENTITY_INVALID, "a coordinate or radius exceeds 1e9 mm")
    keep = ~_degenerate_mask(rows, eps)
    had_degenerate = pre_degenerate or not bool(keep.all())
    return rows[keep], segs[keep], had_degenerate


def build_rows(scan_result: Scan, factor: float, ctx: Context, collector: diag.Collector
               ) -> tuple[NDArray[np.float64], NDArray[np.int64]]:  # fmt: skip
    """Scale the read candidates to millimetres, drop those off the contour plane, the invalid and
    the degenerate, and return their curve rows (m, 7) and source IDs (m,) (REQ-IO-010 to 016)."""
    eps = ctx.tolerances.length_eps_mm
    reference = _reference_z(scan_result.candidates, factor, eps)
    row_parts: list[NDArray[np.float64]] = []
    id_parts: list[NDArray[np.int64]] = []
    for cand in scan_result.candidates:
        place = f"{cand.type_name} (handle {cand.handle})"
        if not _planar(cand, reference, factor, eps):
            collector.entity(diag.DXF_NOT_PLANAR, Severity.WARNING, cand.index, 0,
                             f"{place} lies off the contour plane")  # fmt: skip
            continue
        try:
            rows, segs, had_degenerate = _build_candidate(cand, factor, eps, ctx)
        except _Reject as reject:
            collector.entity(
                reject.code, Severity.WARNING, cand.index, 0, f"{place} {reject.message}"
            )
            continue
        if had_degenerate:
            collector.entity(diag.DXF_DEGENERATE, Severity.INFO, cand.index, 0,
                             f"{place} has a segment of length <= eps, dropped")  # fmt: skip
        if rows.shape[0] > 0:
            row_parts.append(rows)
            id_parts.append((cand.index << _SEG_BITS) + segs)
    if row_parts:
        return np.vstack(row_parts), np.concatenate(id_parts)
    return np.empty((0, _ROW_WIDTH), dtype=np.float64), np.empty(0, dtype=np.int64)

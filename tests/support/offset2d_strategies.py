# SPDX-License-Identifier: Apache-2.0
"""Hypothesis strategies for offset2d's tests (offset2d SPEC, Test plan; research 02, tests 9, 10
and 21): regions of lines and arcs with islands, drawn as plain row lists so that Hypothesis
prints and shrinks them, in any loop order and orientation (REQ-OFF-021).

Every region stays within geometry2d's released requirements: loops are simple and do not cross;
loops lie at least `MIN_GAP_MM` apart, except the touching island of test 21, which meets its wall
at one point (test 16) or lies a drawn gap from it. Rows are [x0, y0, x1, y1, cx, cy, sweep] with
P1 on the circle up to float rounding.
"""

import itertools
import math
from dataclasses import dataclass

import numpy as np
from hypothesis import strategies as st

from geometry2d_checks import reversed_loop
from splintercam.foundation import TOLERANCE_DEFAULTS, Context
from splintercam.geometry2d import AirSide, CurveRows, RegionKind, curve_rows

type Rows = list[list[float]]
type BoxMM = tuple[float, float, float, float]

NAN = math.nan
# The smallest gap between two loops apart (ours): far above t_topo = 2u, so no generated pair
# comes near the loop tree's crossing rule (REQ-G2D-237) or the band of any tolerance of test 10.
MIN_GAP_MM = 0.5
# Bulged pockets after the flatten_loops property test of geometry2d (research 01, test 16): outer
# vertices on a circle of this radius with gaps under π/2 keep every chord 14 mm from the centre.
_BULGED_RADIUS_MM = 20.0
_MAX_BULGE = 0.3  # sagitta <= 0.15·chord <= 4.3 mm, so inward arcs stay 9.7 mm from the centre
# A line, or an arc that bulges by at least 1/40 of its chord either way: a nearly flat arc has a
# centre far beyond the drawing, which a CAD file holds as a line.
_MIN_BULGE = 0.05


def _floats(low: float, high: float) -> st.SearchStrategy[float]:
    """Floats on a 2^-20 grid, as geometry2d's property tests draw them: a tiny draw (an angle near
    0) would put a coordinate below 2^-142, outside the exact predicates' range (geometry2d's
    AGENTS.md, Known pitfalls)."""
    return st.floats(low, high).map(lambda v: min(high, max(low, round(v * 2**20) / 2**20)))


_BULGES = st.one_of(
    st.just(0.0), st.floats(_MIN_BULGE, _MAX_BULGE), st.floats(-_MAX_BULGE, -_MIN_BULGE)
)


@dataclass(frozen=True, slots=True)
class RegionCase:
    """Loops as drawn (any order and orientation), the region's kind, and a box holding every
    curve."""

    loops: list[Rows]
    kind: RegionKind

    @property
    def box(self) -> BoxMM:
        """The box of every row's ends and, for arcs, of its whole circle (a superset)."""
        rows = np.array([row for loop in self.loops for row in loop], dtype=np.float64)
        ends = np.concatenate([rows[:, 0:2], rows[:, 2:4]])
        arcs = rows[rows[:, 6] != 0.0]
        radius = np.hypot(arcs[:, 0] - arcs[:, 4], arcs[:, 1] - arcs[:, 5])[:, None]
        corners = np.concatenate([ends, arcs[:, 4:6] - radius, arcs[:, 4:6] + radius])
        low, high = corners.min(axis=0), corners.max(axis=0)
        return (float(low[0]), float(low[1]), float(high[0]), float(high[1]))

    def curve_rows(self, ctx: Context) -> CurveRows:
        """The loops as geometry2d's checked curve rows, row IDs 100, 101, ..."""
        return to_curve_rows(self.loops, ctx)


def to_curve_rows(loops: list[Rows], ctx: Context) -> CurveRows:
    """Loops as curve rows checked by geometry2d's `curve_rows`, row IDs 100, 101, ..."""
    rows = np.array([row for loop in loops for row in loop], dtype=np.float64)
    starts = np.cumsum([0] + [len(loop) for loop in loops[:-1]], dtype=np.int64)
    ids = 100 + np.arange(rows.shape[0], dtype=np.int64)
    built = curve_rows(rows, ids, starts, ctx)
    assert built.value is not None, built.diagnostics
    return built.value


def rounded_box(x0: float, y0: float, x1: float, y1: float, r: float) -> Rows:
    """The CCW loop of a box with corner arcs of radius r (a line per side, a quarter arc per
    corner when r > 0), as geometry2d's test 7 generator draws it."""
    corners = [
        (x1 - r, y0 + r, -math.pi / 2),
        (x1 - r, y1 - r, 0.0),
        (x0 + r, y1 - r, math.pi / 2),
        (x0 + r, y0 + r, math.pi),
    ]
    rows: Rows = []
    for k, (cx, cy, a) in enumerate(corners):
        start = (cx + r * math.cos(a), cy + r * math.sin(a))
        end = (cx + r * math.cos(a + math.pi / 2), cy + r * math.sin(a + math.pi / 2))
        if r > 0.0:
            rows.append([*start, *end, cx, cy, math.pi / 2])
        nx, ny, na = corners[(k + 1) % 4]
        rows.append([*end, nx + r * math.cos(na), ny + r * math.sin(na), NAN, NAN, 0.0])
    return rows


def circle(cx: float, cy: float, r: float, start: float, pieces: int) -> Rows:
    """The CCW circle about (cx, cy) as `pieces` equal arcs from the angle `start`; one piece is a
    full circle with P1 = P0."""
    sweep = math.tau / pieces
    points = [
        (cx + r * math.cos(start + k * sweep), cy + r * math.sin(start + k * sweep))
        for k in range(pieces)
    ]
    return [[*p, *points[(k + 1) % pieces], cx, cy, sweep] for k, p in enumerate(points)]


def bulge_row(p0: tuple[float, float], p1: tuple[float, float], bulge: float) -> list[float]:
    """The row from p0 to p1 with bulge tan(sweep/4): a line for 0, else the arc whose centre lies
    (chord/2)/tan(sweep/2) left of the chord's midpoint."""
    if bulge == 0.0:
        return [*p0, *p1, NAN, NAN, 0.0]
    sweep = 4.0 * math.atan(bulge)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    h = 0.5 / math.tan(sweep / 2.0)  # times the chord's length, along its left normal
    centre = ((p0[0] + p1[0]) / 2.0 - h * dy, (p0[1] + p1[1]) / 2.0 + h * dx)
    return [*p0, *p1, *centre, sweep]


def _arranged(draw: st.DrawFn, loops: list[Rows]) -> list[Rows]:
    """The loops in a drawn order, each reversed or not (REQ-OFF-021: any orientation)."""
    order = draw(st.permutations(range(len(loops))))
    flips = draw(st.lists(st.booleans(), min_size=len(loops), max_size=len(loops)))
    return [
        reversed_loop(loops[k]) if flip else loops[k] for k, flip in zip(order, flips, strict=True)
    ]


_KINDS = st.sampled_from([RegionKind.AIR, RegionKind.MATERIAL])


@st.composite
def nested_regions(draw: st.DrawFn) -> RegionCase:
    """Research 01's test 7 shapes (geometry2d's generator, private to its test): up to three
    columns of rounded boxes nested up to four deep, each inner box its parent moved in by a gap
    of at least MIN_GAP_MM, the innermost of a column sometimes a circle."""
    loops: list[Rows] = []
    for column in range(draw(st.integers(1, 3))):
        x0, y0, x1, y1 = 40.0 * column, 0.0, 40.0 * column + 30.0, 30.0
        rho = draw(st.sampled_from([0.0, 1.0, 4.0, 7.5]))
        for _ in range(draw(st.integers(1, 4))):
            loops.append(rounded_box(x0, y0, x1, y1, rho))
            gap = draw(_floats(MIN_GAP_MM, 3.0))
            x0, y0, x1, y1, rho = x0 + gap, y0 + gap, x1 - gap, y1 - gap, max(rho - gap, 0.0)
        if draw(st.booleans()):  # a circle inside the innermost box
            r = (x1 - x0) / 2.0 - draw(_floats(MIN_GAP_MM, 2.0))
            start = draw(_floats(0.0, math.tau))
            loops.append(circle((x0 + x1) / 2.0, 15.0, r, start, draw(st.integers(1, 3))))
    return RegionCase(_arranged(draw, loops), draw(_KINDS))


@st.composite
def pocket_with_islands(draw: st.DrawFn) -> RegionCase:
    """The rounded box [0, 90] x [0, 60] with an island of lines and arcs in some of its six
    30 x 30 cells: a circle or a rounded box, at least 4 mm inside its cell (more than the
    wall's corner arcs of radius <= 10 reach into a corner cell, 2.93 mm)."""
    loops = [rounded_box(0.0, 0.0, 90.0, 60.0, draw(st.sampled_from([0.0, 5.0, 10.0])))]
    for cell in range(6):
        x, y = 30.0 * (cell % 3), 30.0 * (cell // 3)
        shape = draw(st.sampled_from(["none", "circle", "box"]))
        if shape == "circle":
            r = draw(_floats(2.0, 11.0))
            start = draw(_floats(0.0, math.tau))
            loops.append(circle(x + 15.0, y + 15.0, r, start, draw(st.integers(1, 3))))
        elif shape == "box":
            m = draw(_floats(4.0, 10.0))
            rho = draw(_floats(0.0, (30.0 - 2.0 * m) / 2.0))
            loops.append(rounded_box(x + m, y + m, x + 30.0 - m, y + 30.0 - m, rho))
    return RegionCase(_arranged(draw, loops), draw(_KINDS))


@st.composite
def bulged_pocket(draw: st.DrawFn) -> RegionCase:
    """A loop of 6 to 12 lines and arcs bulging either way around a circular island about the
    origin (geometry2d's flatten_loops property test)."""
    n = draw(st.integers(6, 12))
    jitter = draw(st.lists(_floats(-0.2, 0.2), min_size=n, max_size=n))
    angles = [(k + j) * math.tau / n for k, j in enumerate(jitter)]
    points = [(_BULGED_RADIUS_MM * math.cos(a), _BULGED_RADIUS_MM * math.sin(a)) for a in angles]
    bulges = draw(st.lists(_BULGES, min_size=n, max_size=n))
    outer = [
        bulge_row(p, q, b) for p, q, b in zip(points, points[1:] + points[:1], bulges, strict=True)
    ]
    island = circle(0.0, 0.0, draw(_floats(0.5, 8.0)), draw(_floats(0.0, math.tau)), 2)
    return RegionCase(_arranged(draw, [outer, island]), draw(_KINDS))


@st.composite
def touching_island(draw: st.DrawFn, gaps: st.SearchStrategy[float] | None = None) -> RegionCase:
    """Research 02's tests 9 and 21: a circular island tangent inside a circular wall, or tangent
    to the top side of a rounded box, a gap drawn from `gaps` apart (none: touching, test 16). Where
    the arcs do not start at the touching point, the island's side-correct flattening reaches past
    the wall's (research 01, rule 7)."""
    gap = 0.0 if gaps is None else draw(gaps)
    island_r = draw(_floats(2.0, 8.0))
    island_start = draw(_floats(0.0, math.tau))
    if draw(st.booleans()):  # a circular wall
        wall_r = draw(_floats(2.5 * island_r, 30.0))
        at = draw(_floats(0.0, math.tau))
        reach = wall_r - island_r - gap
        wall = circle(0.0, 0.0, wall_r, draw(_floats(0.0, math.tau)), draw(st.integers(1, 3)))
        centre = (reach * math.cos(at), reach * math.sin(at))
    else:  # the top side of the box [0, 60] x [0, 40]
        wall = rounded_box(0.0, 0.0, 60.0, 40.0, draw(st.sampled_from([0.0, 5.0])))
        centre = (draw(_floats(island_r + 6.0, 54.0 - island_r)), 40.0 - island_r - gap)
    island = circle(*centre, island_r, island_start, draw(st.integers(1, 3)))
    return RegionCase(_arranged(draw, [wall, island]), draw(_KINDS))


def regions() -> st.SearchStrategy[RegionCase]:
    """Every generator of this file: random regions of lines and arcs with islands."""
    return st.one_of(nested_regions(), pocket_with_islands(), bulged_pocket(), touching_island())


def clearances() -> st.SearchStrategy[float]:
    """Research 02's test 10: t from 0.1 to 50 mm."""
    return _floats(0.1, 50.0)


# Open chains for `offset_chain_side` (plan 0005, backlog of step 8). Turns at vertices of at most
# 1.5 rad between chords and bulges of at most 0.4 (an end tangent 0.76 rad off its chord) keep
# every turn of the flattened chain below π - 0.1, so a drawn walk never folds; it may still touch
# or cross itself, which the test decides with its own oracle.
_CHAIN_TURN = 1.5
_CHAIN_BULGE = 0.4
# A stub from 0.1u to 0.9·t_topo, which `offset_chain_side` merges away (`keep_chain`, DEC-OFF-021);
# above build_chain's eps_len, so it reaches offset2d.
_U_MM = TOLERANCE_DEFAULTS["grid_unit_mm"].default
_STUB_MIN_MM = 0.1 * _U_MM
_T_TOPO_MM = TOLERANCE_DEFAULTS["topology_tol_grid_units"].default * _U_MM
_STUB_MAX_MM = 0.9 * _T_TOPO_MM
# A contact line touches, crosses by 0.5 mm, or stops short of the earlier line by t_topo/4 (to be
# refused) or 3·t_topo (to be offset): the two sides of the test's window round t_topo.
_CONTACT_BEYOND_MM = (0.0, 0.5, -0.25 * _T_TOPO_MM, -3.0 * _T_TOPO_MM)
_ARC_MIN_CHORD_MM = 0.5  # a row shorter than this (a stub) stays a line


def _on_grid(p: tuple[float, float]) -> tuple[float, float]:
    return (round(p[0] * 2**20) / 2**20, round(p[1] * 2**20) / 2**20)


@dataclass(frozen=True, slots=True)
class ChainCase:
    """The rows of one open chain, the tool's side, and how its last row was drawn: "walk", "fold"
    (running back over the line before it) or "contact" (onto or across an earlier line); the
    property test decides simplicity with its own oracle, these only say what to expect."""

    rows: Rows
    side: AirSide
    ending: str


def _walk(draw: st.DrawFn, segments: int) -> list[tuple[float, float]]:
    heading = draw(_floats(0.0, math.tau))
    points = [(0.0, 0.0)]
    for _ in range(segments):
        length = draw(_floats(1.0, 20.0))
        x, y = points[-1]
        step = (x + length * math.cos(heading), y + length * math.sin(heading))
        points.append(_on_grid(step))
        heading += draw(_floats(-_CHAIN_TURN, _CHAIN_TURN))
    return points


@st.composite
def open_chains(draw: st.DrawFn) -> ChainCase:
    """A random walk of 1 to 8 lines and arcs on the 2^-20 grid, sometimes with a stub shorter than
    t_topo at a vertex or an end. Its last row may run back over the line before it by a drawn
    fraction (a fold), or from the walk's end to an earlier line, touching it, crossing it or
    stopping just short of it (a contact), both exact up to the grid."""
    points = _walk(draw, draw(st.integers(1, 8)))
    ending = draw(st.sampled_from(["walk", "fold", "contact"]))
    if draw(st.booleans()):  # never after the last point of a fold: the fold must stay long
        k = draw(st.integers(0, len(points) - (2 if ending == "fold" else 1)))
        length, angle = draw(_floats(_STUB_MIN_MM, _STUB_MAX_MM)), draw(_floats(0.0, math.tau))
        x, y = points[k]
        points.insert(k + 1, _on_grid((x + length * math.cos(angle), y + length * math.sin(angle))))
    if ending == "contact" and len(points) < 3:
        ending = "walk"  # one segment has no earlier line to reach
    target = draw(st.integers(0, len(points) - 3)) if ending == "contact" else -1
    bulges = st.one_of(
        st.just(0.0),
        st.floats(_MIN_BULGE, _CHAIN_BULGE),
        st.floats(-_CHAIN_BULGE, -_MIN_BULGE),
    )
    rows = [
        bulge_row(
            p, q, draw(bulges) if math.dist(p, q) >= _ARC_MIN_CHORD_MM and n != target else 0.0
        )
        for n, (p, q) in enumerate(itertools.pairwise(points))
    ]
    if ending == "fold":
        p, q = points[-2], points[-1]
        rows[-1] = bulge_row(p, q, 0.0)
        f = draw(_floats(0.2, 0.8))
        back = (q[0] + f * (p[0] - q[0]), q[1] + f * (p[1] - q[1]))
        rows.append(bulge_row(q, _on_grid(back), 0.0))
    elif ending == "contact":
        (ax, ay), (bx, by), end = points[target], points[target + 1], points[-1]
        f = draw(_floats(0.2, 0.8))
        hit = (ax + f * (bx - ax), ay + f * (by - ay))
        beyond = draw(st.sampled_from(_CONTACT_BEYOND_MM))
        reach = max(math.dist(end, hit), _U_MM)  # the walk's end on that line: a contact anyway
        tip = (
            hit[0] + beyond * (hit[0] - end[0]) / reach,
            hit[1] + beyond * (hit[1] - end[1]) / reach,
        )
        rows.append(bulge_row(end, _on_grid(tip), 0.0))
    side = draw(st.sampled_from([AirSide.LEFT, AirSide.RIGHT]))
    return ChainCase(rows, side, ending)

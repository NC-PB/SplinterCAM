# SPDX-License-Identifier: Apache-2.0
"""The move rules, REQ-CL-004 to 016, vectorised over the rows (split rule; DEC-CL-001). Each
rule gives a mask of the moves breaking it; the rules run in ID order and the first broken one
is named (REQ-CL-020), so a rule sees only rows that passed the rules before it."""

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from splintercam.foundation import Context
from splintercam.geometry2d import RowStatus, check_arc_rows

from ._types import NO_FEED_CLASS, ClHeader, ClMoves, MoveKind, Role

type Mask = NDArray[np.bool_]

# (column, dtype, shape after the row axis, shape as text)
_COLUMNS: tuple[tuple[str, type[np.generic], tuple[int, ...], str], ...] = (
    ("kind", np.int8, (), "(n,)"),
    ("role", np.int8, (), "(n,)"),
    ("end_mm", np.float64, (3,), "(n, 3)"),
    ("centre_mm", np.float64, (2,), "(n, 2)"),
    ("sweep_rad", np.float64, (), "(n,)"),
    ("feed_class", np.int64, (), "(n,)"),
    ("link_height_mm", np.float64, (), "(n,)"),
)
_KINDS = np.array(list(MoveKind), dtype=np.int8)
_ROLES = np.array(list(Role), dtype=np.int8)


def column_breach(moves: ClMoves) -> str | None:
    """REQ-CL-004: the first column that is not an array of its dtype and shape, or None."""
    for name, dtype, tail, shape in _COLUMNS:
        value: object = getattr(moves, name)
        array = cast("NDArray[np.generic]", value)
        if (
            not isinstance(value, np.ndarray)
            or array.dtype != dtype
            or array.shape[1:] != tail
            or array.ndim != 1 + len(tail)
        ):
            return f"column {name} must be a {np.dtype(dtype).name} array of shape {shape}"
    rows = moves.kind.shape[0]
    for name, _, _, _ in _COLUMNS[1:]:
        if (count := cast("NDArray[np.generic]", getattr(moves, name)).shape[0]) != rows:
            return f"column {name} has {count} rows, column kind {rows}"
    return None if rows else "column kind has no move"


def read_only_copy(moves: ClMoves) -> ClMoves:
    """The columns copied and made read-only (REQ-CL-019)."""

    def frozen(name: str) -> NDArray[Any]:
        copy = cast("NDArray[Any]", getattr(moves, name)).copy()
        copy.flags.writeable = False
        return copy

    return ClMoves(*(frozen(name) for name, _, _, _ in _COLUMNS))


@dataclass(frozen=True, slots=True)
class _Rows:
    moves: ClMoves
    header: ClHeader
    ctx: Context
    start: NDArray[np.float64]  # (n, 3) the previous move's end; row 0 NaN (research 26, Move)
    rapid: Mask
    arc: Mask


def _at(rows: _Rows, index: int, broken: bool) -> Mask:
    mask = np.zeros(rows.rapid.shape[0], dtype=np.bool_)
    mask[index] = broken
    return mask


def _kinds_and_roles(rows: _Rows) -> Mask:
    known = np.isin(rows.moves.kind, _KINDS) & np.isin(rows.moves.role, _ROLES)
    return ~known | (rows.rapid != (rows.moves.role == Role.LINK))


def _first_along_axis(rows: _Rows) -> Mask:
    # Research 10, Method 1 and trap 2: from the tool change along the tool axis only.
    end = rows.moves.end_mm[0]
    along = bool(np.isnan(end[:2]).all()) and math.isfinite(end[2])
    return _at(rows, 0, not (rows.rapid[0] and along))


def _ends_finite(rows: _Rows) -> Mask:
    finite = np.isfinite(rows.moves.end_mm)
    finite[0, :2] = True
    return ~finite.all(axis=1)


def _second_rapid(rows: _Rows) -> Mask:
    many = rows.rapid.shape[0] > 1
    return _at(rows, int(many), many and not rows.rapid[1])


def _feed_classes(rows: _Rows) -> Mask:
    index = rows.moves.feed_class
    in_header = (index >= 0) & (index < len(rows.header.feed_classes))
    return np.where(rows.rapid, index != NO_FEED_CLASS, ~in_header)


def _link_heights(rows: _Rows) -> Mask:
    link = rows.moves.link_height_mm
    return np.where(rows.rapid, ~np.isfinite(link), ~np.isnan(link))


def _rapids_above_links(rows: _Rows) -> Mask:
    # D-062, D-087; exact (DEC-CL-004). Move 1 starts at (NaN, NaN, z), so it moves in the plane.
    end, link = rows.moves.end_mm, rows.moves.link_height_mm
    in_plane = (rows.start[:, 0] != end[:, 0]) | (rows.start[:, 1] != end[:, 1])
    return rows.rapid & ((end[:, 2] < link) | (in_plane & (rows.start[:, 2] < link)))


def _clearance(rows: _Rows) -> Mask:
    z, clearance = rows.moves.end_mm[:, 2], rows.header.clearance_height_mm
    mask = np.zeros(z.shape[0], dtype=np.bool_)
    mask[:2] = z[:2] < clearance
    mask[-1] |= not rows.rapid[-1] or z[-1] < clearance
    return mask


def _no_arc_fields(rows: _Rows) -> Mask:
    centre_set = ~np.isnan(rows.moves.centre_mm).all(axis=1)
    return ~rows.arc & (centre_set | (rows.moves.sweep_rad != 0.0))


def _arc_form(rows: _Rows) -> Mask:
    # math.tau is the double nearest 2π, as geometry2d's. DEC-CL-006: a full circle ends at its
    # start, any other arc more than eps_len from it. Ends are finite here (REQ-CL-007).
    sweep, size = rows.moves.sweep_rad, np.abs(rows.moves.sweep_rad)
    centre_finite = np.isfinite(rows.moves.centre_mm).all(axis=1)
    form = ~centre_finite | ~np.isfinite(sweep) | (sweep == 0.0) | (size > math.tau)
    chord = rows.moves.end_mm[:, :2] - rows.start[:, :2]
    apart = np.sqrt(chord[:, 0] * chord[:, 0] + chord[:, 1] * chord[:, 1])
    closure = np.where(
        size == math.tau, (chord != 0.0).any(axis=1), apart <= rows.ctx.tolerances.length_eps_mm
    )
    return rows.arc & (form | closure)


def _planar(rows: _Rows) -> Mask:
    return rows.arc & (rows.moves.end_mm[:, 2] != rows.start[:, 2])


def _on_circle(rows: _Rows) -> Mask:
    # geometry2d's REQ-G2D-042 and 043 as written, the same on every platform (AQ-006 (a)).
    moves = rows.moves
    curve_rows = np.column_stack(
        (rows.start[:, :2], moves.end_mm[:, :2], moves.centre_mm, moves.sweep_rad)
    )[rows.arc]
    mask = np.zeros(rows.arc.shape[0], dtype=np.bool_)
    mask[rows.arc] = check_arc_rows(curve_rows, rows.ctx) != RowStatus.OK
    return mask


_RULES: tuple[tuple[str, str, Callable[[_Rows], Mask]], ...] = (
    ("REQ-CL-005", "kind or role not allowed: a RAPID is a LINK, a LINE or ARC is not",
     _kinds_and_roles),
    ("REQ-CL-006", "the first move must be a RAPID to (NaN, NaN, z), z finite", _first_along_axis),
    ("REQ-CL-007", "an end value is not finite", _ends_finite),
    ("REQ-CL-008", "the second move must be a RAPID: its start in the plane is not known",
     _second_rapid),
    ("REQ-CL-009", "feed class must be NO_FEED_CLASS for a RAPID, a header class otherwise",
     _feed_classes),
    ("REQ-CL-010", "link height must be finite for a RAPID, NaN otherwise", _link_heights),
    ("REQ-CL-011", "a RAPID ends below its link height or moves in the plane from below it",
     _rapids_above_links),
    ("REQ-CL-012", "moves 0 and 1 end, and the last is a RAPID ending, at the clearance height "
     "or above", _clearance),
    ("REQ-CL-013", "a RAPID or LINE has a NaN centre and sweep 0", _no_arc_fields),
    ("REQ-CL-014", "an ARC needs a finite centre and 0 < |sweep| <= 2π, its end at its start "
     "for 2π and more than eps_len from it otherwise", _arc_form),
    ("REQ-CL-015", "an ARC's end z must equal its start z", _planar),
    ("REQ-CL-016", "the ARC's end is off its circle or its sweep, or its radius is not above "
     "eps_len", _on_circle),
)  # fmt: skip


def move_breach(header: ClHeader, moves: ClMoves, ctx: Context) -> tuple[str, int, str] | None:
    """The first rule of REQ-CL-005 to 016 broken, its first breaking move and the rule's text,
    or None. `moves` passed REQ-CL-004."""
    end = moves.end_mm
    start = np.vstack((np.full((1, 3), np.nan), end[:-1]))
    kind = moves.kind
    rows = _Rows(moves, header, ctx, start, kind == MoveKind.RAPID, kind == MoveKind.ARC)
    for requirement, text, rule in _RULES:
        broken = np.flatnonzero(rule(rows))
        if broken.size:
            return requirement, int(broken[0]), text
    return None

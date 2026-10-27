# SPDX-License-Identifier: Apache-2.0
"""Toolpath records for the cl tests: moves written one per line, research 22 test 1's profile,
and a Hypothesis strategy of valid operations (src/splintercam/cl/SPEC.md, Example parts)."""

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

import numpy as np
from hypothesis import strategies as st
from numpy.typing import NDArray

from splintercam.cl import NO_FEED_CLASS, ClHeader, ClMoves, MoveKind, Role

NAN = math.nan
H_C = 5.0  # clearance height (research 22 test 1)
H_R = 3.0  # retract height h_r
PLUNGE, CUT = 0, 1  # feed class indexes into HEADER.feed_classes

HEADER = ClHeader(
    name="Profile_1",
    note=(),
    tool_number=1,
    point_number=1,
    axial_offset_mm=0.0,
    spindle_rpm=8000.0,
    tol_mm=0.01,
    feed_classes=(("plunge", 300.0), ("cut", 1000.0)),
    clearance_height_mm=H_C,
)


@dataclass(frozen=True, slots=True)
class Move:
    """One row of `ClMoves`, with the fill values of a RAPID as defaults."""

    kind: MoveKind
    role: Role
    end: tuple[float, float, float]
    centre: tuple[float, float] = (NAN, NAN)
    sweep: float = 0.0
    feed: int = NO_FEED_CLASS
    link: float = NAN


def rapid(x: float, y: float, z: float, link: float) -> Move:
    return Move(MoveKind.RAPID, Role.LINK, (x, y, z), link=link)


def line(x: float, y: float, z: float, role: Role = Role.CUT, feed: int = CUT) -> Move:
    return Move(MoveKind.LINE, role, (x, y, z), feed=feed)


def arc(end: tuple[float, float, float], centre: tuple[float, float], sweep: float) -> Move:
    return Move(MoveKind.ARC, Role.CUT, end, centre, sweep, CUT)


def columns(moves: Sequence[Move]) -> ClMoves:
    """The moves as the seven columns, writable arrays as a producer holds them."""
    return ClMoves(
        kind=np.array([m.kind for m in moves], dtype=np.int8),
        role=np.array([m.role for m in moves], dtype=np.int8),
        end_mm=np.array([m.end for m in moves], dtype=np.float64).reshape(-1, 3),
        centre_mm=np.array([m.centre for m in moves], dtype=np.float64).reshape(-1, 2),
        sweep_rad=np.array([m.sweep for m in moves], dtype=np.float64),
        feed_class=np.array([m.feed for m in moves], dtype=np.int64),
        link_height_mm=np.array([m.link for m in moves], dtype=np.float64),
    )


def changed(moves: ClMoves, column: str, index: int | tuple[int, int], value: object) -> ClMoves:
    """`moves` with `column[index] = value` in a copy of that column."""
    array: NDArray[Any] = np.array(getattr(moves, column), copy=True)
    array[index] = value
    return replace(moves, **{column: array})


def refusal(requirement: str, move: int | None = None, name: str = "Profile_1") -> str:
    """A regex for the start of REQ-CL-020's message: operation, requirement, move."""
    where = "" if move is None else f": move {move}:"
    return f"^operation '{name}': {requirement}{where}"


def framed(cut: Sequence[Move], at: tuple[float, float], z: float = -1.0) -> list[Move]:
    """Tool change, rapid to `at` at h_c, down to h_r, plunge to `z`, the cut, rapid up to h_c."""
    last = cut[-1].end if cut else (*at, z)
    return [
        rapid(NAN, NAN, H_C, H_C),
        rapid(*at, H_C, H_C),
        rapid(*at, H_R, H_R),
        line(*at, z, Role.APPROACH, PLUNGE),
        *cut,
        rapid(last[0], last[1], H_C, H_C),
    ]


# Research 22 test 1: the rectangle (0, 0)-(100, 60) with fillets R 5, tool D 10, climb, so the
# centre path is the rectangle grown by 5 with corners R 10, run CW. P is the approach point, S
# the start point on the bottom edge.
P = (50.0, -15.0)
S = (50.0, -5.0)
PASSES = (-10.0 / 3.0, -20.0 / 3.0, -10.0)
_QUARTER_CW = -math.pi / 2


def _loop(z: float) -> list[Move]:
    return [
        line(5.0, -5.0, z),
        arc((-5.0, 5.0, z), (5.0, 5.0), _QUARTER_CW),
        line(-5.0, 55.0, z),
        arc((5.0, 65.0, z), (5.0, 55.0), _QUARTER_CW),
        line(95.0, 65.0, z),
        arc((105.0, 55.0, z), (95.0, 55.0), _QUARTER_CW),
        line(105.0, 5.0, z),
        arc((95.0, -5.0, z), (95.0, 5.0), _QUARTER_CW),
        line(*S, z),
    ]


def profile_moves() -> list[Move]:
    """Research 22 test 1's record: 44 moves, the last the third pass's RAPID Z 5."""
    moves = [rapid(NAN, NAN, H_C, H_C), rapid(*P, H_C, H_C)]
    for z in PASSES:
        moves += [
            rapid(*P, H_R, H_R),
            line(*P, z, Role.APPROACH, PLUNGE),
            line(*S, z, Role.APPROACH, PLUNGE),
            *_loop(z),
            line(*P, z, Role.RETRACT, CUT),
            rapid(*P, H_C, H_C),
        ]
    return moves


def full_circle(sweep: float, end: tuple[float, float] = (10.0, 0.0)) -> list[Move]:
    """A circle of radius 10 about the origin from (10, 0) at z = -1, inside the frame."""
    return framed([arc((*end, -1.0), (0.0, 0.0), sweep)], (10.0, 0.0))


# Valid operations for the property tests: coordinates on a 2^-10 mm grid, arcs of radius 1 to
# 50 with |sweep| in [0.1, 2π - 0.1], so the end is far from the start and REQ-CL-014's tiny-arc
# rule never applies; the end is computed from the centre, well within eps_len of the circle.
_GRID = 2.0**-10
_coord = st.integers(-(2**17), 2**17).map(lambda k: k * _GRID)
_level = st.integers(-(2**15), 0).map(lambda k: k * _GRID)


@st.composite
def _cut(draw: st.DrawFn, start: tuple[float, float], z: float) -> list[Move]:
    moves: list[Move] = []
    x, y = start
    for _ in range(draw(st.integers(1, 6))):
        if draw(st.booleans()):
            x, y = draw(_coord), draw(_coord)
            moves.append(line(x, y, z))
            continue
        radius = draw(st.floats(1.0, 50.0))
        at = draw(st.floats(-math.pi, math.pi))
        sweep = draw(st.floats(0.1, math.tau - 0.1)) * draw(st.sampled_from((-1.0, 1.0)))
        cx, cy = x - radius * math.cos(at), y - radius * math.sin(at)
        x, y = cx + radius * math.cos(at + sweep), cy + radius * math.sin(at + sweep)
        moves.append(arc((x, y, z), (cx, cy), sweep))
    return moves


@st.composite
def operations(draw: st.DrawFn) -> list[Move]:
    """A valid operation: one to three passes at random levels below h_r, each reached by a
    rapid in the plane at h_c or at h_r, and the end at h_c."""
    moves = [rapid(NAN, NAN, H_C, H_C)]
    x, y = draw(_coord), draw(_coord)
    moves.append(rapid(x, y, H_C, H_C))
    for _ in range(draw(st.integers(1, 3))):
        if draw(st.booleans()):
            moves.append(rapid(x, y, H_C, H_C))
            moves.append(rapid(x, y, H_R, H_R))
        else:
            moves.append(rapid(x, y, H_R, H_R))
            x, y = draw(_coord), draw(_coord)
            moves.append(rapid(x, y, H_R, H_R))
        z = draw(_level) - 1.0
        moves.append(line(x, y, z, Role.APPROACH, PLUNGE))
        cut = draw(_cut((x, y), z))
        moves += cut
        x, y = cut[-1].end[0], cut[-1].end[1]
        moves.append(rapid(x, y, H_C, H_C))
    return moves

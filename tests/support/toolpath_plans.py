# SPDX-License-Identifier: Apache-2.0
"""Link plans for the toolpath tests: research 22 test 1's three passes, small one-pass plans and
a Hypothesis strategy of valid plans (src/splintercam/toolpath/SPEC.md, Example parts and Test
plan)."""

import math
from collections.abc import Sequence
from dataclasses import replace

import numpy as np
from hypothesis import strategies as st

from cl_strategies import CUT, HEADER, PASSES, PLUNGE, P, S
from splintercam.cl import ClHeader, Role
from splintercam.model import FlatEndMill, StockBox
from splintercam.toolpath import LevelPass, LinkPlan

# Research 22 test 1: the rectangle (0, 0)-(100, 60), stock 5 mm on every side, top 0, so h_c 5
# and h_r 3 as in cl_strategies.HEADER; tool D 10.
STOCK = StockBox((-5.0, -5.0, -15.0), (105.0, 65.0, 0.0))
TOOL = FlatEndMill(1, 10.0, 30.0)
_QUARTER_CW = -math.pi / 2

type Row = tuple[float, float, float, float, float, float, float]


def line_row(start: tuple[float, float], end: tuple[float, float]) -> Row:
    return (*start, *end, math.nan, math.nan, 0.0)


def arc_row(start: tuple[float, float], end: tuple[float, float], centre: tuple[float, float],
            sweep: float) -> Row:  # fmt: skip
    return (*start, *end, *centre, sweep)


def level(z: float, rows: Sequence[Row], roles: Sequence[Role], feeds: Sequence[int]) -> LevelPass:
    return LevelPass(
        z_mm=z,
        rows=np.array(rows, dtype=np.float64).reshape(-1, 7),
        role=np.array(roles, dtype=np.int8),
        feed_class=np.array(feeds, dtype=np.int64),
    )


def profile_rows() -> list[Row]:
    """P to S, the CW loop of research 22 test 1 (as cl_strategies' profile), S back to P."""
    corners = ((5.0, -5.0), (-5.0, 5.0), (-5.0, 55.0), (5.0, 65.0), (95.0, 65.0), (105.0, 55.0),
               (105.0, 5.0), (95.0, -5.0))  # fmt: skip
    centres = ((5.0, 5.0), (5.0, 55.0), (95.0, 55.0), (95.0, 5.0))
    rows = [line_row(P, S), line_row(S, corners[0])]
    for k, centre in enumerate(centres):
        rows.append(arc_row(corners[2 * k], corners[2 * k + 1], centre, _QUARTER_CW))
        rows.append(line_row(corners[2 * k + 1], corners[(2 * k + 2) % 8] if k < 3 else S))
    rows.append(line_row(S, P))
    return rows


def profile_pass(z: float) -> LevelPass:
    rows = profile_rows()
    roles = [Role.APPROACH] + [Role.CUT] * (len(rows) - 2) + [Role.RETRACT]
    feeds = [PLUNGE] + [CUT] * (len(rows) - 1)
    return level(z, rows, roles, feeds)


def profile_plan(plunge: int = PLUNGE) -> LinkPlan:
    return LinkPlan(P, TOOL, plunge, tuple(profile_pass(z) for z in PASSES))


def square_pass(z: float, at: tuple[float, float] = P) -> LevelPass:
    """A 4-row square of side 2 from `at` back to `at`, CUT at the cutting feed."""
    x, y = at
    corners = [(x, y), (x + 2.0, y), (x + 2.0, y - 2.0), (x, y - 2.0), (x, y)]
    rows = [line_row(corners[k], corners[k + 1]) for k in range(4)]
    return level(z, rows, [Role.CUT] * 4, [CUT] * 4)


def square_plan(*levels: float) -> LinkPlan:
    return LinkPlan(P, TOOL, PLUNGE, tuple(square_pass(z) for z in levels or (-1.0,)))


def refusal(requirement: str, pass_index: int | None = None, row: int | None = None) -> str:
    """A regex for the start of a refusal: operation, requirement, pass and row (REQ-TP-013); a
    pass without a row matches any row of it."""
    if pass_index is None:
        return f"^operation 'Profile_1': {requirement}:"
    where = "[:,]" if row is None else f", row {row}:"
    return f"^operation 'Profile_1': {requirement}: pass {pass_index}{where}"


def header_for(stock: StockBox) -> ClHeader:
    top = stock.top_mm
    # Literal D-062 heights, not the module's constants, so a wrong constant fails REQ-TP-007.
    return replace(HEADER, clearance_height_mm=top + 5.0, retract_height_mm=top + 3.0)


# Valid plans for the property tests: coordinates on a 2^-10 mm grid; P outside the stock box grown
# by R; one to three passes of lines and arcs (radius 1 to 50, |sweep| in [0.1, 2π - 0.1], the
# end computed from the centre, as cl_strategies) closed by a line back to P, at levels below h_r.
_GRID = 2.0**-10
_coord = st.integers(-(2**17), 2**17).map(lambda k: k * _GRID)


def _outside(point: tuple[float, float], stock: StockBox) -> bool:
    dx = max(stock.min_mm[0] - point[0], 0.0, point[0] - stock.max_mm[0])
    dy = max(stock.min_mm[1] - point[1], 0.0, point[1] - stock.max_mm[1])
    return dx * dx + dy * dy > TOOL.radius_mm * TOOL.radius_mm


@st.composite
def _row(draw: st.DrawFn, start: tuple[float, float]) -> Row:
    if draw(st.booleans()):
        # A line row's centre and zero sweep may hold anything (REQ-TP-006).
        junk = draw(st.sampled_from(((math.nan, math.nan), (0.0, 0.0), (7.5, -3.0))))
        return (*start, draw(_coord), draw(_coord), *junk, draw(st.sampled_from((0.0, -0.0))))
    radius = draw(st.floats(1.0, 50.0))
    at = draw(st.floats(-math.pi, math.pi))
    sweep = draw(st.floats(0.1, math.tau - 0.1)) * draw(st.sampled_from((-1.0, 1.0)))
    cx, cy = start[0] - radius * math.cos(at), start[1] - radius * math.sin(at)
    end = (cx + radius * math.cos(at + sweep), cy + radius * math.sin(at + sweep))
    return arc_row(start, end, (cx, cy), sweep)


@st.composite
def _pass(draw: st.DrawFn, at: tuple[float, float], retract: float) -> LevelPass:
    rows: list[Row] = []
    start = at
    for _ in range(draw(st.integers(0, 5))):
        rows.append(draw(_row(start)))
        start = (rows[-1][2], rows[-1][3])
    rows.append(line_row(start, at))
    roles = draw(st.lists(st.sampled_from((Role.APPROACH, Role.CUT, Role.RETRACT)),
                          min_size=len(rows), max_size=len(rows)))  # fmt: skip
    feeds = draw(st.lists(st.sampled_from((PLUNGE, CUT)), min_size=len(rows), max_size=len(rows)))
    # From the stock bottom (h_r - 18; included, AQ-021) up to one grid step below h_r.
    z = retract - 18.0 + draw(st.integers(0, 18 * 2**10 - 1)) * _GRID
    return level(z, rows, roles, feeds)


@st.composite
def plans(draw: st.DrawFn) -> tuple[LinkPlan, StockBox]:
    """A valid plan and its stock: the research 22 box moved to a random top on the grid."""
    top = draw(st.integers(-(2**15), 2**15)) * _GRID
    stock = StockBox((-5.0, -5.0, top - 15.0), (105.0, 65.0, top))
    at = draw(st.tuples(_coord, _coord).filter(lambda point: _outside(point, stock)))
    count = draw(st.integers(1, 3))
    passes = tuple(draw(_pass(at, top + 3.0)) for _ in range(count))
    return LinkPlan(at, TOOL, draw(st.sampled_from((PLUNGE, CUT))), passes), stock

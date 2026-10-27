# SPDX-License-Identifier: Apache-2.0
"""Property tests of the profile (SPEC, Invariants and Test plan): random parts of lines and arcs,
convex and not, inside random stock boxes; the cut in the band from the true contour, clockwise,
every pass from the same S and P, P clear of the stock, bit for bit twice (REQ-PRF-011 to 017,
022); the approach point in closed form (REQ-PRF-014)."""

import math
import os
from dataclasses import dataclass, fields

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from geometry2d_checks import codes
from offset2d_oracles import distance_to_curves, true_curve_band_mm
from offset2d_strategies import bulge_row, rounded_box, to_curve_rows
from profile_checks import (
    cut_points,
    distance_to_box,
    make_context,
    pass_moves,
    rounded_rect_distances,
    segment_distance,
    signed_area,
    task,
)
from splintercam.cl import ClMoves, ClOperation, Role
from splintercam.geometry2d import CurveRows
from splintercam.model import FlatEndMill, StockBox
from splintercam.strategies.profile import plan_profile
from splintercam.strategies.profile._approach import approach_point

EPS_LEN = 1e-6  # foundation's eps_len default; the context's is checked equal below
_SLACK = 1e-9  # the oracles' own rounding, far below eps_len
EXAMPLES = 1000 if os.environ.get("HYPOTHESIS_PROFILE") == "thorough" else 40  # tests/conftest.py


def _grid(low: float, high: float) -> st.SearchStrategy[float]:
    # A 2^-20 grid keeps coordinates inside the exact predicates' range (geometry2d, pitfalls).
    return st.floats(low, high).map(lambda v: min(high, max(low, round(v * 2**20) / 2**20)))


@dataclass(frozen=True, slots=True)
class Part:
    rows: list[list[float]]
    rect: tuple[float, float, float, float, float] | None  # inner box and radius when rounded
    lines_only: bool
    small_tool: bool = False  # t <= 4, so the U's channel stays open


def _u_part(draw: st.DrawFn) -> Part:
    # A U of lines opening up, its outer sides bent out by 1 mm at mid-height, so the inner sides
    # (at least 23 mm after a t <= 4 offset) are the longest line edges (bottom <= 20, outer
    # halves about 20): their normals cross the channel at the other arm (REQ-PRF-015).
    arm, gap = draw(_grid(3.0, 4.0)), draw(_grid(10.0, 12.0))
    height, base = draw(_grid(33.0, 40.0)), draw(_grid(3.0, 6.0))
    x0, y0 = -(2.0 * arm + gap) / 2.0, -height / 2.0
    x1, y1, ym = -x0, -y0, 0.0
    points = [(x0, y0), (x1, y0), (x1 + 1.0, ym), (x1, y1), (x1 - arm, y1),
              (x1 - arm, y0 + base), (x0 + arm, y0 + base), (x0 + arm, y1), (x0, y1),
              (x0 - 1.0, ym)]  # fmt: skip
    rows = [bulge_row(p, q, 0.0) for p, q in zip(points, points[1:] + points[:1], strict=True)]
    return Part(rows, None, True, small_tool=True)


@st.composite
def parts(draw: st.DrawFn) -> Part:
    """A rounded box (convex, lines and arcs), a star polygon of lines (not convex), a star of
    bulged rows (lines and arcs, not convex) or a U whose approach falls back to the smallest
    vertex, all inside [-25, 25]²."""
    kind = draw(st.sampled_from(["box", "star", "bulged", "u"]))
    if kind == "u":
        return _u_part(draw)
    if kind == "box":
        w, h, r = draw(_grid(5.0, 40.0)), draw(_grid(5.0, 40.0)), draw(_grid(0.0, 2.5))
        rows = rounded_box(-w / 2, -h / 2, w / 2, h / 2, r)
        return Part(rows, (-w / 2 + r, -h / 2 + r, w / 2 - r, h / 2 - r, r), False)
    n = draw(st.integers(5, 10))
    radii = draw(st.lists(_grid(12.0, 20.0), min_size=n, max_size=n))
    points = [(rho * math.cos(k * math.tau / n), rho * math.sin(k * math.tau / n))
              for k, rho in enumerate(radii)]  # fmt: skip
    points = [(round(x * 2**20) / 2**20, round(y * 2**20) / 2**20) for x, y in points]
    bulges = [0.0] * n if kind == "star" else draw(
        st.lists(st.sampled_from([0.0, 0.1, -0.1, 0.25]), min_size=n, max_size=n))  # fmt: skip
    rows = [bulge_row(p, q, b) for p, q, b in zip(points, points[1:] + points[:1], bulges,
                                                   strict=True)]  # fmt: skip
    return Part(rows, None, kind == "star")


def _distances(part: Part, contour: CurveRows, cut: NDArray[np.float64]
               ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:  # fmt: skip
    # Each cut edge's smallest distance from the true contour (exact for boxes and lines; at the
    # vertices and midpoints for bulged rows) and its largest at the vertices and midpoints.
    probes = np.concatenate([cut, (cut[:-1] + cut[1:]) / 2.0])
    largest = distance_to_curves(probes, contour)
    if part.rect is not None:
        smallest, _ = rounded_rect_distances(cut, part.rect[:4], part.rect[4])
    elif part.lines_only:
        rows = contour.rows
        smallest = segment_distance(cut[:-1, None, :], cut[1:, None, :],
                                    rows[None, :, 0:2], rows[None, :, 2:4]).min(axis=1)  # fmt: skip
    else:
        smallest = largest
    return smallest, largest


@st.composite
def cases(draw: st.DrawFn) -> tuple[Part, StockBox, FlatEndMill, dict[str, float]]:
    part = draw(parts())
    radius = draw(_grid(1.0, 3.0 if part.small_tool else 8.0))
    margins = draw(st.lists(_grid(0.0, 10.0), min_size=4, max_size=4))
    bottom = -draw(_grid(0.5, 20.0))
    stock = StockBox((-25.0 - margins[0], -25.0 - margins[1], -25.0),
                     (25.0 + margins[2], 25.0 + margins[3], 0.0))  # fmt: skip
    values = {
        "allowance_mm": draw(_grid(-radius + 0.1, 1.0 if part.small_tool else 3.0)),
        "z_bottom_mm": bottom,
        "stepdown_mm": draw(_grid(0.5, 10.0)),
        "air_gap_ratio": draw(_grid(0.05, 1.0)),
    }
    return part, stock, FlatEndMill(1, 2.0 * radius, 30.0), values


def _same(a: ClOperation, b: ClOperation) -> bool:
    moves = [getattr(op.moves, f.name).tobytes() for op in (a, b) for f in fields(ClMoves)]
    return a.header == b.header and moves[: len(moves) // 2] == moves[len(moves) // 2 :]


@pytest.mark.req("REQ-PRF-011", "REQ-PRF-012", "REQ-PRF-014", "REQ-PRF-015", "REQ-PRF-016",
                 "REQ-PRF-017", "REQ-PRF-019", "REQ-PRF-022")  # fmt: skip
# Fewer cases than the profile's (40 of dev's 100, 1000 of thorough's 10 000), as offset2d's band
# tests do: each case runs offset2d twice, and the test stays under 2 s (docs/dev/06).
@settings(deadline=None, max_examples=EXAMPLES, suppress_health_check=[HealthCheck.too_slow])
@given(case=cases())
def test_the_profile_of_a_random_part(
    case: tuple[Part, StockBox, FlatEndMill, dict[str, float]],
) -> None:
    part, stock, tool, values = case
    ctx = make_context()
    assert ctx.tolerances.length_eps_mm == EPS_LEN
    contour = to_curve_rows([part.rows], ctx)
    result = plan_profile(task(ctx, contour=contour, tool=tool, stock=stock, **values), ctx)
    assert result.value is not None, codes(result)
    op = result.value
    t = tool.radius_mm + values["allowance_mm"]
    p = (float(op.moves.end_mm[1, 0]), float(op.moves.end_mm[1, 1]))
    clear = tool.radius_mm * (1.0 + values["air_gap_ratio"])
    assert distance_to_box(p, stock) >= clear - EPS_LEN
    passes = pass_moves(op)
    first_cut = None
    for z, rows in passes:
        assert values["z_bottom_mm"] <= z < 0.0
        cut = cut_points(op, rows[op.moves.role[rows] == Role.CUT])
        first_cut = cut if first_cut is None else first_cut
        assert np.array_equal(cut, first_cut)  # the same S and loop every pass
        assert tuple(op.moves.end_mm[rows[-1], 0:2]) == p
    assert first_cut is not None
    assert signed_area(first_cut) < 0.0
    smallest, largest = _distances(part, contour, first_cut)
    assert smallest.min() >= t - _SLACK * max(1.0, t)
    assert largest.max() <= t + true_curve_band_mm(ctx.tolerances)
    # The approach P → S (and the retract back on it) cuts nothing of the part (REQ-PRF-015).
    way, _ = _distances(part, contour, np.array([p, first_cut[0]]))
    assert way.min() >= t - _SLACK * max(1.0, t)
    if part.small_tool:  # the U: its inner side's approach is blocked, S the smallest vertex
        assert first_cut[0, 0] == first_cut[:, 0].min()
    depths = -np.diff([0.0, *(z for z, _ in passes)])
    assert depths.max() <= values["stepdown_mm"] + EPS_LEN
    assert passes[-1][0] == values["z_bottom_mm"]
    again = plan_profile(task(ctx, contour=contour, tool=tool, stock=stock, **values), ctx)
    assert again.value is not None
    assert _same(op, again.value)


_STOCK = StockBox((-10.0, -5.0, -1.0), (30.0, 15.0, 0.0))


@pytest.mark.req("REQ-PRF-014")
@given(
    s=st.tuples(_grid(-20.0, 40.0), _grid(-15.0, 25.0)),
    angle=st.one_of(st.sampled_from([0.0, 0.5, 1.0, 1.5]), st.floats(0.0, 2.0)),
    radius=_grid(0.5, 8.0),
    gap=_grid(0.01, 2.0),
)
def test_the_approach_point_is_the_nearest_clear_point_on_the_ray(
    s: tuple[float, float], angle: float, radius: float, gap: float
) -> None:
    # The normal at angle·π; the sampled angles give normals exactly along an axis.
    axis = {0.0: (1.0, 0.0), 0.5: (0.0, 1.0), 1.0: (-1.0, 0.0), 1.5: (0.0, -1.0)}
    n = axis.get(angle, (math.cos(angle * math.pi), math.sin(angle * math.pi)))
    clear = radius + gap
    p = approach_point(s, n, _STOCK, clear)
    d = math.hypot(p[0] - s[0], p[1] - s[1])
    assert distance_to_box(p, _STOCK) >= clear - EPS_LEN
    (x0, y0, _), (x1, y1, _) = _STOCK.min_mm, _STOCK.max_mm
    dx, dy = max(x0 - p[0], 0.0, p[0] - x1), max(y0 - p[1], 0.0, p[1] - y1)
    assert dx * dx + dy * dy > radius * radius
    if d > EPS_LEN:
        back = (s[0] + (d - EPS_LEN) * n[0], s[1] + (d - EPS_LEN) * n[1])
        assert distance_to_box(back, _STOCK) < clear
    else:
        assert p == s or distance_to_box(s, _STOCK) >= clear - EPS_LEN

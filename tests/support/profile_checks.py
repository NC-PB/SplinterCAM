# SPDX-License-Identifier: Apache-2.0
"""Shared helpers for the profile strategy's tests: research 22 test 1's task with any parameter
changed, a context with the operation's tol, the passes read back from the record, and exact
distances of the cut edges from a rounded rectangle (a rectangle grown by a disc, so convex)."""

import dataclasses
import logging
import math

import numpy as np
from numpy.typing import NDArray

from offset2d_strategies import rounded_box, to_curve_rows
from splintercam.cl import ClOperation, MoveKind
from splintercam.foundation import CancellationToken, Context, ToleranceSet
from splintercam.geometry2d import CurveRows
from splintercam.model import FlatEndMill, Operation, StockBox
from splintercam.strategies.profile import DECLARATIONS, ProfileInput

type Points = NDArray[np.float64]

TOOL = FlatEndMill(1, 10.0, 30.0)  # research 22 test 1: D 10, 30 mm of flute
STOCK = StockBox((-5.0, -5.0, -20.0), (105.0, 65.0, 0.0))  # 5 mm round the rectangle
# Research 22 test 1's values; allowance and air gap ratio at their declared defaults.
VALUES = {
    "allowance_mm": 0.0,
    "z_top_mm": 0.0,
    "z_bottom_mm": -10.0,
    "stepdown_mm": 4.0,
    "cut_feed_mm_per_min": 1200.0,
    "plunge_feed_mm_per_min": 300.0,
    "air_gap_ratio": 0.2,
}


class _NullSink:
    def add(self, name: str, kind: str, data: NDArray[np.float64]) -> None:
        del name, kind, data


def make_context(tol_mm: float = 0.01) -> Context:
    """A fresh `Context` with the operation's tolerance set (the profile's precondition)."""
    built = ToleranceSet.for_operation(tol_mm)
    assert built.value is not None
    return Context(built.value, CancellationToken(), lambda _f: None,
                   logging.getLogger("profile.tests"), _NullSink(), 0)  # fmt: skip


def operation(**changed: float) -> Operation:
    """`PROFILE_1` of the model SPEC's example job with the given parameters changed."""
    values = VALUES | changed
    parameters = tuple((d.name, values[d.name]) for d in DECLARATIONS)
    return Operation("PROFILE_1", "profile", 1, 8000.0, 0.01, parameters)


def rectangle(ctx: Context) -> CurveRows:
    """Research 22 test 1's part: 100 x 60 from (0, 0) with fillets R 5, CCW, IDs 100 to 107."""
    return to_curve_rows([rounded_box(0.0, 0.0, 100.0, 60.0, 5.0)], ctx)


def task(ctx: Context, contour: CurveRows | None = None, tool: FlatEndMill = TOOL,
         stock: StockBox = STOCK, **changed: float) -> ProfileInput:  # fmt: skip
    """Research 22 test 1's task, any part of it replaced."""
    part = rectangle(ctx) if contour is None else contour
    return ProfileInput(part, tool, stock, operation(**changed))


def with_stock(stock: StockBox, **corners: float) -> StockBox:
    """`stock` with some of x0, y0, z0, x1, y1, z1 replaced."""
    low = tuple(corners.get(k, v) for k, v in zip(("x0", "y0", "z0"), stock.min_mm, strict=True))
    high = tuple(corners.get(k, v) for k, v in zip(("x1", "y1", "z1"), stock.max_mm, strict=True))
    return dataclasses.replace(stock, min_mm=low, max_mm=high)


def pass_moves(op: ClOperation) -> list[tuple[float, NDArray[np.int64]]]:
    """Each pass's level and the indices of its moves in the plane, from the record toolpath built:
    per pass a RAPID to h_r, the feed down, the moves in the plane, a RAPID to h_c."""
    rapids = np.flatnonzero(op.moves.kind == MoveKind.RAPID)
    return [
        (float(op.moves.end_mm[start + 1, 2]), np.arange(start + 2, end))
        for start, end in zip(rapids[2::2], rapids[3::2], strict=True)
    ]


def cut_points(op: ClOperation, rows: NDArray[np.int64]) -> Points:
    """The XY points of the moves `rows`, each move's start (the end before it) first."""
    ends = op.moves.end_mm[:, 0:2]
    return np.concatenate([ends[rows[:1] - 1], ends[rows]])


def point_segment_distance(q: Points, a: Points, b: Points) -> NDArray[np.float64]:
    """Each point's distance to its segment a → b (rows broadcast)."""
    ab, aq = b - a, q - a
    length2 = np.sum(ab * ab, axis=-1)
    s = np.clip(np.sum(aq * ab, axis=-1) / np.where(length2 > 0.0, length2, 1.0), 0.0, 1.0)
    return np.hypot(*np.moveaxis(aq - s[..., None] * ab, -1, 0))


def _crosses(a: Points, b: Points, c: Points, d: Points) -> NDArray[np.bool_]:
    def side(p: Points, q: Points, r: Points) -> NDArray[np.float64]:
        return np.sign((q[..., 0] - p[..., 0]) * (r[..., 1] - p[..., 1])
                       - (q[..., 1] - p[..., 1]) * (r[..., 0] - p[..., 0]))  # fmt: skip

    return (side(a, b, c) * side(a, b, d) <= 0.0) & (side(c, d, a) * side(c, d, b) <= 0.0)


def segment_distance(a: Points, b: Points, c: Points, d: Points) -> NDArray[np.float64]:
    """The exact smallest distance between segments a → b and c → d (rows broadcast): 0 where
    they meet, else the smallest of the four end-to-segment distances."""
    ends = np.minimum(
        np.minimum(point_segment_distance(a, c, d), point_segment_distance(b, c, d)),
        np.minimum(point_segment_distance(c, a, b), point_segment_distance(d, a, b)),
    )
    return np.where(_crosses(a, b, c, d), 0.0, ends)


type Box = tuple[float, float, float, float]


def rounded_rect_distances(points: Points, box: Box, radius: float) -> tuple[Points, Points]:
    """For the closed polyline `points` (its last point repeated), each edge's exact smallest and
    largest distance from the rounded rectangle `box` grown by `radius` (the part of test 1):
    the distance from the inner rectangle less the radius; the largest is at an end (convex)."""
    x0, y0, x1, y1 = box
    corners = np.array([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    a, b = points[:-1, None, :], points[1:, None, :]
    smallest = segment_distance(a, b, corners[None, :, :], np.roll(corners, -1, 0)[None, :, :])
    outside = (
        np.maximum(np.maximum(x0 - points[:, 0], points[:, 0] - x1), 0.0),
        np.maximum(np.maximum(y0 - points[:, 1], points[:, 1] - y1), 0.0),
    )
    inside_rect = (outside[0] == 0.0) & (outside[1] == 0.0)
    at = np.where(inside_rect, 0.0, np.hypot(*outside))
    nearest = np.minimum(smallest.min(axis=1), np.minimum(at[:-1], at[1:]))  # 0 for an end inside
    return nearest - radius, np.maximum(at[:-1], at[1:]) - radius


def signed_area(points: Points) -> float:
    """The shoelace area of the closed polyline `points` (its last point repeated)."""
    x, y = points[:, 0], points[:, 1]
    return float(np.sum(x[:-1] * y[1:] - x[1:] * y[:-1]) / 2.0)


def distance_to_box(p: tuple[float, float], stock: StockBox) -> float:
    """The distance of p from the stock box in XY, 0 inside."""
    (x0, y0, _), (x1, y1, _) = stock.min_mm, stock.max_mm
    return math.hypot(max(x0 - p[0], 0.0, p[0] - x1), max(y0 - p[1], 0.0, p[1] - y1))

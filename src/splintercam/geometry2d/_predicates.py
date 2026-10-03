# SPDX-License-Identifier: Apache-2.0
"""Exact predicates and direction tests (research 01, Vectors and exact signs, and Tolerances)."""

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray

from splintercam import _kernels
from splintercam.foundation import Context


def _rows(*arrays: ArrayLike) -> list[NDArray[np.float64]]:
    """C-contiguous float64 copies of (n, 2) point arrays with one n (REQ-G2D-201)."""
    copies = [np.array(a, dtype=np.float64, order="C", copy=True) for a in arrays]
    shape = copies[0].shape
    if len(shape) != 2 or shape[1] != 2 or any(c.shape != shape for c in copies):
        raise ValueError(
            f"points must be (n, 2) arrays of one shape, got {[c.shape for c in copies]}"
        )
    return copies


def _signs(count: int) -> NDArray[np.int8]:
    return np.empty(count, dtype=np.int8)


def orient2d(a: ArrayLike, b: ArrayLike, c: ArrayLike) -> NDArray[np.int8]:
    """Per row the exact sign of orient2d(a, b, c): +1 when c lies left of the directed line
    a → b, -1 right, 0 collinear (Shewchuk's predicates.c, SRC-032). No tolerance, no Context.

    Implements: REQ-G2D-007 to 010, REQ-G2D-021, REQ-G2D-024.
    """
    pa, pb, pc = _rows(a, b, c)
    out = _signs(pa.shape[0])
    _kernels.geometry2d.orient2d_signs(pa, pb, pc, out)
    return out


def incircle(a: ArrayLike, b: ArrayLike, c: ArrayLike, d: ArrayLike) -> NDArray[np.int8]:
    """Per row the exact sign of incircle(a, b, c, d): +1 when d lies inside the circle through
    a, b, c given counter-clockwise, -1 outside, 0 cocircular; the opposite for clockwise.

    Implements: REQ-G2D-011, REQ-G2D-021, REQ-G2D-024.
    """
    pa, pb, pc, pd = _rows(a, b, c, d)
    out = _signs(pa.shape[0])
    _kernels.geometry2d.incircle_signs(pa, pb, pc, pd, out)
    return out


def in_arc_circle(q: ArrayLike, centre: ArrayLike, p0: ArrayLike) -> NDArray[np.int8]:
    """Per row the exact sign of |p0 - c|² - |q - c|²: +1 when q lies inside the circle of an arc
    with centre c and start point p0, 0 on it, -1 outside (Peter, 2026-10-02).

    Implements: REQ-G2D-022, REQ-G2D-024.
    """
    pq, pc, p0_rows = _rows(q, centre, p0)
    out = _signs(pq.shape[0])
    _kernels.geometry2d.in_arc_circle_signs(pq, pc, p0_rows, out)
    return out


def _pairs(
    kernel_function: str, a: ArrayLike, b: ArrayLike
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    a_copy = np.array(a, dtype=np.float64, order="C", copy=True).ravel()
    b_copy = np.array(b, dtype=np.float64, order="C", copy=True).ravel()
    if a_copy.shape != b_copy.shape:
        raise ValueError(f"a and b need one shape, got {a_copy.shape} and {b_copy.shape}")
    x, y = np.empty_like(a_copy), np.empty_like(a_copy)
    getattr(_kernels.geometry2d, kernel_function)(a_copy, b_copy, x, y)
    return x, y


def two_sum(a: ArrayLike, b: ArrayLike) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """The kernel's error-free sum, x + y = a + b exactly; internal, for the build guard.

    Implements: REQ-G2D-016.
    """
    return _pairs("two_sums", a, b)


def two_product(a: ArrayLike, b: ArrayLike) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """The kernel's error-free product, x + y = a·b exactly; internal, for the build guard.

    Implements: REQ-G2D-016.
    """
    return _pairs("two_products", a, b)


def are_parallel(a: ArrayLike, b: ArrayLike, ctx: Context) -> NDArray[np.bool_]:
    """For rows of directions a and b ((n, 2) each), whether they are parallel: the square of their
    cross product is at most sin²(eps_ang)·|a|²·|b|² (research 01, Tolerances).

    Opposite directions and a zero vector count as parallel (REQ-G2D-027).

    Implements: REQ-G2D-027.
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    cross = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
    limit = math.sin(ctx.tolerances.angle_eps_rad) ** 2
    return cross * cross <= limit * np.sum(a * a, axis=1) * np.sum(b * b, axis=1)

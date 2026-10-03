# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the exact predicates (research 01, Vectors and exact signs; tests 1 and 2, the
Shewchuk note's test ideas 1 to 4 and 7)."""

import math
import subprocess
import sys
from fractions import Fraction

import numpy as np
import pytest

import geometry2d_oracles as oracle
from splintercam import _kernels
from splintercam.geometry2d import in_arc_circle, incircle, orient2d

ULP_AT_HALF = 2.0**-53  # one rounding unit at 0.5 (note test 1)


def _grid() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    # Note test 1: p = (0.5 + i·2^-53, 0.5 + j·2^-53), q = (12, 12), r = (24, 24); the exact sign
    # of orient2d(p, q, r) = 12(p_y - p_x) is sign(j - i).
    i, j = np.meshgrid(np.arange(256), np.arange(256), indexing="ij")
    p = np.column_stack([0.5 + i.ravel() * ULP_AT_HALF, 0.5 + j.ravel() * ULP_AT_HALF])
    q = np.tile([12.0, 12.0], (p.shape[0], 1))
    r = np.tile([24.0, 24.0], (p.shape[0], 1))
    return p, q, r, np.sign(j.ravel() - i.ravel())


@pytest.mark.req("REQ-G2D-007", "REQ-G2D-021", "REQ-G2D-024")
def test_note_test_1_grid_gives_the_exact_signs() -> None:
    p, q, r, expected = _grid()
    signs = orient2d(p, q, r)
    assert signs.dtype == np.int8
    np.testing.assert_array_equal(signs, expected)


@pytest.mark.req("REQ-G2D-013")
def test_the_predicates_are_ready_as_the_first_call_in_a_fresh_interpreter() -> None:
    # Note test 1 as the very first kernel call: exactinit() must already have run at load.
    code = (
        "import numpy as np\n"
        "from splintercam.geometry2d import orient2d\n"
        "i, j = np.meshgrid(np.arange(256), np.arange(256), indexing='ij')\n"
        "u = 2.0**-53\n"
        "p = np.column_stack([0.5 + i.ravel() * u, 0.5 + j.ravel() * u])\n"
        "n = p.shape[0]\n"
        "s = orient2d(p, np.tile([12.0, 12.0], (n, 1)), np.tile([24.0, 24.0], (n, 1)))\n"
        "assert (s == np.sign(j.ravel() - i.ravel())).all()\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


@pytest.mark.req("REQ-G2D-008")
@pytest.mark.parametrize(
    "points",
    [
        ((0.1, 0.3), (7.0, 0.3), (-2.5, 0.3)),  # equal y (note test 2: three points on y = 0.3)
        ((0.3, 0.1), (0.3, 7.0), (0.3, -2.5)),  # equal x
    ],
)
def test_shared_x_or_y_gives_zero(points: tuple[tuple[float, float], ...]) -> None:
    a, b, c = (np.array([p]) for p in points)
    assert orient2d(a, b, c).tolist() == [0]


@pytest.mark.req("REQ-G2D-007")
def test_left_is_positive() -> None:
    a, b = np.array([[0.0, 0.0]] * 3), np.array([[1.0, 0.0]] * 3)
    c = np.array([[0.5, 1.0], [0.5, -1.0], [2.0, 0.0]])
    assert orient2d(a, b, c).tolist() == [1, -1, 0]


@pytest.mark.req("REQ-G2D-011")
def test_note_test_4_incircle() -> None:
    a, b, c = [5.0, 0.0], [0.0, 5.0], [-5.0, 0.0]  # CCW on the circle of radius 5
    d = np.array([[3.0, 4.0], [3.0, 4.0 - 2.0**-50], [3.0, 4.0 + 2.0**-50]])
    ccw = incircle(np.array([a] * 3), np.array([b] * 3), np.array([c] * 3), d)
    cw = incircle(np.array([c] * 3), np.array([b] * 3), np.array([a] * 3), d)
    assert ccw.tolist() == [0, 1, -1]
    assert cw.tolist() == [0, -1, 1]


@pytest.mark.req("REQ-G2D-022", "REQ-G2D-021")
def test_research_test_2_arc_predicate() -> None:
    # C = (0, 0), P0 = (5, 0): (3, 4) on the circle, 2^-50 below inside (+1), above outside (-1).
    q = np.array([[3.0, 4.0], [3.0, 4.0 - 2.0**-50], [3.0, 4.0 + 2.0**-50]])
    centre, p0 = np.zeros((3, 2)), np.tile([5.0, 0.0], (3, 1))
    assert in_arc_circle(q, centre, p0).tolist() == [0, 1, -1]
    assert [oracle.in_arc_circle(tuple(row), (0.0, 0.0), (5.0, 0.0)) for row in q] == [0, 1, -1]


def _vertical_extent_sign(
    q_y: list[float], centre: list[list[float]], p0: list[list[float]]
) -> list[int]:
    out = np.empty(len(q_y), dtype=np.int8)
    _kernels.geometry2d.vertical_extent_signs(np.array(q_y), np.array(centre), np.array(p0), out)
    return out.tolist()


@pytest.mark.req("REQ-G2D-023")
def test_q_y_against_the_highest_and_lowest_point_of_a_circle() -> None:
    # Research 01, test 6's circle: C = (0, 0), r = 5. The sign of (q_y - c_y)^2 - r^2: 0 at the
    # top (q_y = 5), -1 inside the band (q_y = -3), +1 beyond it.
    signs = _vertical_extent_sign(
        [5.0, -3.0, 5.0 + 2.0**-50, -5.0], [[0.0, 0.0]] * 4, [[5.0, 0.0]] * 4
    )
    assert signs == [0, -1, 1, 0]


@pytest.mark.req("REQ-G2D-023")
def test_q_y_against_a_top_that_is_not_a_double() -> None:
    # r = |(1, 1) - (0, 0)| = sqrt(2): c_y + r is no double; the doubles just below and above it
    # lie inside and outside the band.
    top = math.sqrt(2.0)
    below, above = (
        (top, math.nextafter(top, math.inf)) if top * top < 2 else (math.nextafter(top, 0.0), top)
    )
    assert Fraction(below) ** 2 < 2 < Fraction(above) ** 2
    assert _vertical_extent_sign([below, above], [[0.0, 0.0]] * 2, [[1.0, 1.0]] * 2) == [-1, 1]


def _kernel_pairs(name: str, a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x, y = np.empty_like(a), np.empty_like(a)
    function = _kernels.geometry2d.two_sums if name == "sum" else _kernels.geometry2d.two_products
    function(np.ascontiguousarray(a), np.ascontiguousarray(b), x, y)
    return x, y


def _reference_two_sum(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    # SRC-032, Theorem 7, in NumPy: each ufunc call is one correctly rounded IEEE operation, with
    # no contraction, so this is an independent exact reference.
    x = a + b
    b_virtual = x - a
    return x, (a - (x - b_virtual)) + (b - b_virtual)


def _reference_two_product(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    # SRC-032, Theorems 17 and 18 (Dekker's split with 2^27 + 1), in NumPy.
    def split(v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        c = (2.0**27 + 1.0) * v
        high = c - (c - v)
        return high, v - high

    x = a * b
    (ah, al), (bh, bl) = split(a), split(b)
    return x, al * bl - (((x - ah * bh) - al * bh) - ah * bl)


@pytest.mark.req("REQ-G2D-016", "REQ-G2D-014", "REQ-G2D-015")
def test_two_product_example_of_note_test_7() -> None:
    a = np.array([1 + 2.0**-30])
    x, y = _kernel_pairs("product", a, a)
    assert (x.tolist(), y.tolist()) == ([1 + 2.0**-29], [2.0**-60])


@pytest.mark.req("REQ-G2D-016", "REQ-G2D-014", "REQ-G2D-015", "REQ-G2D-017")
@pytest.mark.parametrize("spread", [False, True])
def test_build_guard_error_free_transformations(spread: bool) -> None:
    # Note test 7, the build guard, on every one of 10^6 random pairs: the kernel's pairs equal an
    # independent reference bit for bit, and that reference is exact (checked in rationals on a
    # sample). A contracting or reordering compiler setting changes the kernel's pairs and fails.
    rng = np.random.default_rng(7)
    a, b = rng.uniform(-1.0, 1.0, (2, 1_000_000))
    if spread:  # exponents spread over a wide range, inside the predicates' range
        a *= 2.0 ** rng.integers(-60, 60, a.size)
        b *= 2.0 ** rng.integers(-60, 60, b.size)
    for name, reference in (("sum", _reference_two_sum), ("product", _reference_two_product)):
        x, y = _kernel_pairs(name, a, b)
        ref_x, ref_y = reference(a, b)
        np.testing.assert_array_equal(x, ref_x)
        np.testing.assert_array_equal(y, ref_y)
        for k in rng.choice(a.size, 2000, replace=False):
            ak, bk = Fraction(float(a[k])), Fraction(float(b[k]))
            exact = ak + bk if name == "sum" else ak * bk
            assert Fraction(float(x[k])) + Fraction(float(y[k])) == exact


@pytest.mark.req("REQ-G2D-007", "REQ-G2D-011", "REQ-G2D-022")
@pytest.mark.parametrize("bad", [math.nan, math.inf])
def test_a_non_finite_point_is_a_programming_error(bad: float) -> None:
    good = np.zeros((1, 2))
    with pytest.raises(ValueError, match="finite"):
        orient2d(np.array([[bad, 0.0]]), good, good)
    with pytest.raises(ValueError, match="finite"):
        incircle(good, good, good, np.array([[0.0, bad]]))
    with pytest.raises(ValueError, match="finite"):
        in_arc_circle(good, np.array([[bad, bad]]), good)


@pytest.mark.req("REQ-G2D-024")
def test_a_batch_gives_the_signs_of_single_rows() -> None:
    rng = np.random.default_rng(3)
    a, b, c, d = rng.uniform(-1.0, 1.0, (4, 50, 2))
    batch = orient2d(a, b, c), incircle(a, b, c, d), in_arc_circle(a, b, c)
    for k in range(50):
        one = slice(k, k + 1)
        single = orient2d(a[one], b[one], c[one]), incircle(a[one], b[one], c[one], d[one])
        assert [int(s[0]) for s in single] == [int(batch[0][k]), int(batch[1][k])]
        assert int(in_arc_circle(a[one], b[one], c[one])[0]) == int(batch[2][k])


@pytest.mark.req("REQ-G2D-024")
def test_mismatched_shapes_are_a_programming_error() -> None:
    with pytest.raises(ValueError, match="shape"):
        orient2d(np.zeros((2, 2)), np.zeros((3, 2)), np.zeros((2, 2)))

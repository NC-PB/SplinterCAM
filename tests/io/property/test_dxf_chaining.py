# SPDX-License-Identifier: Apache-2.0
# ezdxf's factory stubs carry Unknown in their signatures (DEC-IO-005); silence that stub noise.
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false, reportPrivateImportUsage=false
"""Property tests for the DXF chaining (io SPEC, Invariants; REQ-IO-018 to 024, 029). A convex
polygon is written as separate LINE entities in a random order and direction, its shared vertices
jittered below eps_len; the import must give it back as one closed loop, closed bit for bit, with
the area of the drawn polygon, whatever the order."""

import logging
import math
from pathlib import Path

import ezdxf
import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from splintercam.foundation import TOLERANCE_DEFAULTS, CancellationToken, Context, ToleranceSet
from splintercam.geometry2d import signed_area
from splintercam.io import read_dxf_contour


class _NullSink:
    def add(self, name: str, kind: str, data: NDArray[np.float64]) -> None:
        del name, kind, data


def _ctx(seed: int) -> Context:
    tolerances = ToleranceSet.for_operation(TOLERANCE_DEFAULTS["chord_tol_finishing_mm"].default)
    assert tolerances.value is not None
    return Context(tolerances.value, CancellationToken(), lambda _f: None,
                   logging.getLogger("io.property"), _NullSink(), seed)  # fmt: skip


def _polygon(sides: int, perturbations: list[float], radius: float) -> list[tuple[float, float]]:
    # A convex polygon: vertices on a circle at evenly spaced angles, each nudged by less than half
    # the gap so the order (and convexity) is kept.
    gap = math.tau / sides
    vertices: list[tuple[float, float]] = []
    for index in range(sides):
        angle = index * gap + perturbations[index] * gap * 0.4
        vertices.append((radius * math.cos(angle), radius * math.sin(angle)))
    return vertices


def _shoelace(vertices: list[tuple[float, float]]) -> float:
    area = 0.0
    for (x0, y0), (x1, y1) in zip(vertices, [*vertices[1:], vertices[0]], strict=True):
        area += x0 * y1 - x1 * y0
    return abs(area) / 2.0


@pytest.mark.req("REQ-IO-018")
@pytest.mark.req("REQ-IO-020")
@pytest.mark.req("REQ-IO-021")
@pytest.mark.req("REQ-IO-022")
@pytest.mark.req("REQ-IO-023")
@pytest.mark.req("REQ-IO-024")
@pytest.mark.req("REQ-IO-029")
@settings(max_examples=60, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])  # fmt: skip
@given(
    sides=st.integers(min_value=3, max_value=7),
    noise=st.lists(st.floats(-1.0, 1.0), min_size=35, max_size=35),
    order_seed=st.integers(0, 10_000),
    radius=st.floats(10.0, 40.0),
)
def test_a_scrambled_polygon_of_lines_is_one_closed_loop(
    tmp_path: Path, sides: int, noise: list[float], order_seed: int, radius: float
) -> None:
    ctx = _ctx(order_seed)
    eps = ctx.tolerances.length_eps_mm
    perturbations, jitters = noise[:7], noise[7:]  # 7 angle nudges, then 28 end jitters
    vertices = _polygon(sides, perturbations, radius)
    rng = np.random.default_rng(order_seed)
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    edges = list(range(sides))
    rng.shuffle(edges)
    for position, edge in enumerate(edges):
        start, end = vertices[edge], vertices[(edge + 1) % sides]
        # Jitter each end below eps/4 so the two copies of a shared vertex stay within eps_len.
        js = jitters[4 * position : 4 * position + 4]
        p0 = (start[0] + js[0] * eps * 0.25, start[1] + js[1] * eps * 0.25)
        p1 = (end[0] + js[2] * eps * 0.25, end[1] + js[3] * eps * 0.25)
        if rng.integers(2):  # draw some edges backwards
            p0, p1 = p1, p0
        msp.add_line(p0, p1)
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "poly.dxf"
    doc.saveas(path)

    result = read_dxf_contour(path, None, None, ctx)
    assert result.ok, [d.code for d in result.diagnostics]
    assert result.value is not None
    rows = result.value.loop.rows
    assert rows.shape[0] == sides
    # Closed bit for bit: each row starts where the one before it ends (io SPEC, Invariants).
    bits = rows.view(np.int64)
    previous = np.roll(np.arange(rows.shape[0]), 1)
    assert np.array_equal(bits[:, 0:2], bits[previous, 2:4])
    # The area of the drawn polygon, within the jitter (vertices moved by less than eps_len).
    area = signed_area(result.value.loop, ctx).value
    assert area is not None
    assert abs(area) == pytest.approx(_shoelace(vertices), abs=sides * radius * eps * 4.0)


@pytest.mark.req("REQ-IO-009")
@settings(max_examples=40, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])  # fmt: skip
@given(
    sides=st.integers(min_value=3, max_value=6),
    perturbations=st.lists(st.floats(-1.0, 1.0), min_size=6, max_size=6),
    radius=st.floats(10.0, 40.0),
)
def test_mirroring_a_polyline_keeps_the_area_magnitude(
    tmp_path: Path, sides: int, perturbations: list[float], radius: float
) -> None:
    ctx = _ctx(0)
    vertices = _polygon(sides, perturbations, radius)
    areas: list[float] = []
    for index, extrusion in enumerate(((0, 0, 1), (0, 0, -1))):
        doc = ezdxf.new()
        doc.header["$INSUNITS"] = 4
        doc.modelspace().add_lwpolyline(vertices, format="xy", close=True,
                                        dxfattribs={"extrusion": extrusion})  # fmt: skip
        tmp_path.mkdir(parents=True, exist_ok=True)
        path = tmp_path / f"m{index}.dxf"
        doc.saveas(path)
        result = read_dxf_contour(path, None, None, ctx)
        assert result.ok
        assert result.value is not None
        value = signed_area(result.value.loop, ctx).value
        assert value is not None
        areas.append(value)
    assert abs(areas[0]) == pytest.approx(abs(areas[1]))
    assert areas[0] * areas[1] < 0.0  # the mirror reverses the loop's orientation

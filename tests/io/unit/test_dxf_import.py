# SPDX-License-Identifier: Apache-2.0
# ezdxf's factory stubs carry Unknown in their signatures, so its builder calls trip pyright's
# unknown-type and private-import rules; silence that stub noise for this test module (DEC-IO-005).
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false, reportPrivateImportUsage=false
"""Unit tests for the DXF import (io SPEC, REQ-IO-001 to 030; research 21 tests 1 to 7). Each DXF
is written by ezdxf into a temporary file inside the test, so the geometry is visible in code."""

import math
from pathlib import Path

import ezdxf
import numpy as np
import pytest
from ezdxf.document import Drawing

from splintercam.foundation import Context, Result, Severity
from splintercam.geometry2d import signed_area
from splintercam.io import DrawingUnit, decode_source_id, read_dxf_contour
from splintercam.io._read import DxfContour

# A quarter-circle bulge, b = tan(φ/4) for φ = 90° (research 01, Curves, Bulge).
_QUARTER = math.tan(math.radians(90.0) / 4.0)


def _doc(insunits: int = 4) -> Drawing:
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = insunits
    return doc


def _read(doc: Drawing, tmp_path: Path, ctx: Context, layer: str | None = None,
          unit: DrawingUnit | None = None) -> Result[DxfContour]:  # fmt: skip
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "part.dxf"
    doc.saveas(path)
    return read_dxf_contour(path, layer, unit, ctx)


def _codes(result: Result[DxfContour]) -> list[str]:
    return [diagnostic.code for diagnostic in result.diagnostics]


def _area(contour: DxfContour, ctx: Context) -> float:
    value = signed_area(contour.loop, ctx).value
    assert value is not None
    return value


def _rect_fillet(doc: Drawing) -> None:
    # A 100 x 60 plate with four r5 fillets, one closed LWPOLYLINE with bulges (research 21 test 1).
    points = [
        (5, 0, 0),
        (95, 0, _QUARTER),
        (100, 5, 0),
        (100, 55, _QUARTER),
        (95, 60, 0),
        (5, 60, _QUARTER),
        (0, 55, 0),
        (0, 5, _QUARTER),
    ]
    doc.modelspace().add_lwpolyline(points, format="xyb", close=True)


# --- reading, entities, units (REQ-IO-001 to 008) ------------------------------------------------


@pytest.mark.req("REQ-IO-001")
def test_lwpolyline_rectangle_with_fillets_is_one_loop(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    _rect_fillet(doc)
    result = _read(doc, tmp_path, ctx)
    assert result.ok
    assert result.value is not None
    assert result.value.loop.rows.shape[0] == 8
    # Area 6000 - (4 - pi)*25 mm^2 (research 21 test 1); the four fillets remove the corner squares.
    assert _area(result.value, ctx) == pytest.approx(6000.0 - (4.0 - math.pi) * 25.0)
    box = result.value.part_size
    assert (box.x_max_mm - box.x_min_mm, box.y_max_mm - box.y_min_mm) == pytest.approx(
        (100.0, 60.0)
    )


@pytest.mark.req("REQ-IO-002")
def test_a_file_that_cannot_be_parsed_is_unreadable(tmp_path: Path, ctx: Context) -> None:
    path = tmp_path / "broken.dxf"
    path.write_text("not a dxf file", encoding="utf-8")
    result = read_dxf_contour(path, None, None, ctx)
    assert not result.ok
    assert result.value is None
    assert _codes(result) == ["DXF_UNREADABLE"]


@pytest.mark.req("REQ-IO-002")
def test_a_missing_file_is_unreadable(tmp_path: Path, ctx: Context) -> None:
    result = read_dxf_contour(tmp_path / "nope.dxf", None, None, ctx)
    assert _codes(result) == ["DXF_UNREADABLE"]


@pytest.mark.req("REQ-IO-003")
def test_other_entity_types_are_skipped_once_per_type(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    _rect_fillet(doc)
    doc.modelspace().add_text("label").set_placement((1, 1))
    doc.modelspace().add_spline([(0, 0), (1, 1), (2, 0)])
    result = _read(doc, tmp_path, ctx)
    assert result.ok
    skipped = [d for d in result.diagnostics if d.code == "DXF_SKIPPED"]
    assert len(skipped) == 2  # once per type (REQ-IO-003)
    assert any("TEXT" in d.message and "1" in d.message for d in skipped)
    assert any("SPLINE" in d.message and "1" in d.message for d in skipped)


@pytest.mark.req("REQ-IO-003")
def test_polyline_subtypes_are_skipped_by_subtype(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    _rect_fillet(doc)
    doc.modelspace().add_polyline3d([(0, 0, 0), (1, 1, 1)])
    doc.modelspace().add_polymesh(size=(2, 2))
    result = _read(doc, tmp_path, ctx)
    assert result.ok  # the fillet rectangle is still read
    messages = " ".join(d.message for d in result.diagnostics if d.code == "DXF_SKIPPED")
    assert "3D POLYLINE" in messages
    assert "POLYGON MESH" in messages


@pytest.mark.req("REQ-IO-004")
@pytest.mark.parametrize(("insunits", "factor"), [(4, 1.0), (1, 25.4), (5, 10.0), (6, 1000.0)])
def test_units_scale_every_coordinate_once(
    tmp_path: Path, ctx: Context, insunits: int, factor: float
) -> None:
    doc = _doc(insunits)
    doc.modelspace().add_lwpolyline([(0, 0), (100, 0), (100, 60), (0, 60)], format="xy", close=True)
    result = _read(doc, tmp_path, ctx)
    assert result.ok
    assert result.value is not None
    box = result.value.part_size
    assert box.x_max_mm - box.x_min_mm == pytest.approx(100.0 * factor)
    assert box.y_max_mm - box.y_min_mm == pytest.approx(60.0 * factor)


@pytest.mark.req("REQ-IO-005")
def test_an_unsupported_unit_stops_the_import(tmp_path: Path, ctx: Context) -> None:
    doc = _doc(2)  # feet
    _rect_fillet(doc)
    result = _read(doc, tmp_path, ctx)
    assert _codes(result) == ["DXF_UNIT_UNSUPPORTED"]
    assert "feet" in result.diagnostics[0].message


@pytest.mark.req("REQ-IO-006")
def test_no_unit_and_no_job_unit_stops_naming_the_size(tmp_path: Path, ctx: Context) -> None:
    doc = _doc(0)
    doc.modelspace().add_lwpolyline([(0, 0), (100, 0), (100, 60), (0, 60)], format="xy", close=True)
    result = _read(doc, tmp_path, ctx)
    assert _codes(result) == ["DXF_NO_UNITS"]
    assert "100" in result.diagnostics[0].message
    assert "60" in result.diagnostics[0].message


@pytest.mark.req("REQ-IO-007")
def test_no_unit_with_a_job_unit_converts_with_it(tmp_path: Path, ctx: Context) -> None:
    doc = _doc(0)
    doc.modelspace().add_lwpolyline([(0, 0), (10, 0), (10, 10), (0, 10)], format="xy", close=True)
    result = _read(doc, tmp_path, ctx, unit=DrawingUnit.INCH)
    assert result.ok
    assert result.value is not None
    assert result.value.part_size.x_max_mm - result.value.part_size.x_min_mm == pytest.approx(254.0)


@pytest.mark.req("REQ-IO-008")
def test_a_unit_conflict_stops_the_import(tmp_path: Path, ctx: Context) -> None:
    doc = _doc(4)  # file says millimetres
    _rect_fillet(doc)
    result = _read(doc, tmp_path, ctx, unit=DrawingUnit.INCH)
    assert _codes(result) == ["DXF_UNIT_CONFLICT"]


# --- OCS, planarity, validity (REQ-IO-009 to 016) ------------------------------------------------


@pytest.mark.req("REQ-IO-009")
@pytest.mark.parametrize("kind", ["lwpolyline", "polyline2d", "arc", "circle"])
def test_mirror_by_minus_z_extrusion_mirrors_and_keeps_area(
    tmp_path: Path, ctx: Context, kind: str
) -> None:
    plain, mirrored = _doc(), _doc()
    for doc, extrusion in ((plain, (0, 0, 1)), (mirrored, (0, 0, -1))):
        attribs = {"extrusion": extrusion}
        msp = doc.modelspace()
        if kind == "lwpolyline":
            msp.add_lwpolyline([(1, 0), (6, 0), (6, 4), (1, 4)], format="xy", close=True,
                               dxfattribs=attribs)  # fmt: skip
        elif kind == "polyline2d":
            msp.add_polyline2d([(1, 0), (6, 0), (6, 4), (1, 4)], close=True, dxfattribs=attribs)
        elif kind == "arc":  # two semicircles, both OCS entities, mirror together
            msp.add_arc((0, 0), 5, 0, 180, dxfattribs=attribs)
            msp.add_arc((0, 0), 5, 180, 360, dxfattribs=attribs)
        else:
            msp.add_circle((0, 0), 5, dxfattribs=attribs)
    plain_result = _read(plain, tmp_path, ctx)
    mirrored_result = _read(mirrored, tmp_path / "b", ctx)
    assert plain_result.ok
    assert mirrored_result.ok
    assert plain_result.value is not None
    assert mirrored_result.value is not None
    # Mirroring reverses the loop, so the signed area flips sign but keeps its magnitude.
    assert _area(mirrored_result.value, ctx) == pytest.approx(-_area(plain_result.value, ctx))


@pytest.mark.req("REQ-IO-010")
def test_an_entity_off_the_contour_plane_is_skipped(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    _rect_fillet(doc)
    doc.modelspace().add_line((2, 2, 7.0), (3, 3, 7.0))  # a line at z = 7, off the z = 0 plane
    result = _read(doc, tmp_path, ctx)
    assert result.ok  # the plate is still read; the stray line is dropped
    assert "DXF_NOT_PLANAR" in _codes(result)


@pytest.mark.req("REQ-IO-010")
def test_a_non_axis_extrusion_is_not_planar(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    _rect_fillet(doc)
    doc.modelspace().add_circle((0, 0), 1, dxfattribs={"extrusion": (0, 1, 1)})
    result = _read(doc, tmp_path, ctx)
    assert "DXF_NOT_PLANAR" in _codes(result)


@pytest.mark.req("REQ-IO-011")
def test_a_coordinate_beyond_1e9_mm_is_invalid(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    _rect_fillet(doc)
    doc.modelspace().add_line((0, 0), (2.0e9, 0))
    result = _read(doc, tmp_path, ctx)
    assert "DXF_ENTITY_INVALID" in _codes(result)


@pytest.mark.req("REQ-IO-011")
def test_a_polyline_with_one_vertex_is_invalid(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    _rect_fillet(doc)
    doc.modelspace().add_lwpolyline([(1, 1)], format="xy", close=False)
    result = _read(doc, tmp_path, ctx)
    assert "DXF_ENTITY_INVALID" in _codes(result)


@pytest.mark.req("REQ-IO-012")
def test_an_arc_becomes_one_arc_row(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    doc.modelspace().add_arc((0, 0), 5, 0, 90)
    doc.modelspace().add_line((5, 0), (0, 5))  # chord closing the quarter arc
    result = _read(doc, tmp_path, ctx)
    assert result.ok
    assert result.value is not None
    assert result.value.loop.rows.shape[0] == 2
    # One arc row (sweep ≠ 0) and one line row (sweep 0).
    assert np.count_nonzero(result.value.loop.rows[:, 6]) == 1


@pytest.mark.req("REQ-IO-013")
def test_a_circle_becomes_one_full_circle_row(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    doc.modelspace().add_circle((0, 0), 5)
    result = _read(doc, tmp_path, ctx)
    assert result.ok
    assert result.value is not None
    assert result.value.loop.rows.shape[0] == 1
    assert abs(result.value.loop.rows[0, 6]) == pytest.approx(math.tau)
    assert _area(result.value, ctx) == pytest.approx(math.pi * 25.0)


@pytest.mark.req("REQ-IO-014")
def test_a_polyline_closes_only_when_its_closed_flag_is_set(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    # An open triangle polyline: three vertices, not closed → an open chain, not one loop.
    doc.modelspace().add_lwpolyline([(0, 0), (10, 0), (10, 10)], format="xy", close=False)
    result = _read(doc, tmp_path, ctx)
    assert not result.ok
    assert "DXF_OPEN_CHAIN" in _codes(result)


@pytest.mark.req("REQ-IO-015")
def test_a_repeated_vertex_segment_is_degenerate(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    # A closed square whose first vertex is repeated at the end with a bulge: the closing
    # zero-length segment (last vertex to first) drops, the square stays (research 21 test 5 hint).
    doc.modelspace().add_lwpolyline(
        [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0), (0, 0, 1)], format="xyb", close=True
    )
    result = _read(doc, tmp_path, ctx)
    assert result.ok
    assert "DXF_DEGENERATE" in _codes(result)
    assert result.value is not None
    assert _area(result.value, ctx) == pytest.approx(100.0)


@pytest.mark.req("REQ-IO-016")
def test_source_ids_encode_entity_and_segment(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    _rect_fillet(doc)  # entity index 0, eight segments
    result = _read(doc, tmp_path, ctx)
    assert result.value is not None
    decoded = [decode_source_id(int(i)) for i in result.value.loop.ids]
    assert {entity for entity, _ in decoded} == {0}
    assert sorted(segment for _, segment in decoded) == list(range(8))


@pytest.mark.req("REQ-IO-016")
def test_a_polyline_with_too_many_segments_is_rejected(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    _rect_fillet(doc)
    points = [(float(i), 0.0) for i in range(65538)]  # 65537 segments, over the 2^16 limit
    doc.modelspace().add_lwpolyline(points, format="xy", close=False)
    result = _read(doc, tmp_path, ctx)
    assert "DXF_ENTITY_TOO_LARGE" in _codes(result)


# --- duplicates, matching, moves (REQ-IO-017 to 023) ---------------------------------------------


def _square_lines(doc: Drawing) -> None:
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0))
    msp.add_line((10, 0), (10, 10))
    msp.add_line((10, 10), (0, 10))
    msp.add_line((0, 10), (0, 0))


@pytest.mark.req("REQ-IO-017")
def test_an_exact_duplicate_line_is_dropped(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    _square_lines(doc)
    doc.modelspace().add_line((0, 0), (10, 0))  # drawn twice
    result = _read(doc, tmp_path, ctx)
    assert result.ok
    assert "DXF_DUPLICATE" in _codes(result)
    assert result.value is not None
    assert result.value.loop.rows.shape[0] == 4


@pytest.mark.req("REQ-IO-018")
def test_a_square_from_separate_lines_in_any_order_is_one_loop(
    tmp_path: Path, ctx: Context
) -> None:
    doc = _doc()
    msp = doc.modelspace()
    msp.add_line((10, 0), (10, 10))  # out of order and partly reversed
    msp.add_line((0, 0), (10, 0))
    msp.add_line((0, 10), (0, 0))
    msp.add_line((10, 10), (0, 10))
    result = _read(doc, tmp_path, ctx)
    assert result.ok
    assert result.value is not None
    assert abs(_area(result.value, ctx)) == pytest.approx(100.0)


@pytest.mark.req("REQ-IO-019")
def test_a_t_junction_is_a_branch(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0))
    msp.add_line((10, 0), (10, 10))
    msp.add_line((10, 0), (20, 0))  # a third end meets the same point
    result = _read(doc, tmp_path, ctx)
    assert not result.ok
    assert "DXF_BRANCH" in _codes(result)


@pytest.mark.req("REQ-IO-020")
@pytest.mark.req("REQ-IO-021")
def test_the_less_magnifying_row_moves_so_a_line_meeting_an_arc_moves(
    tmp_path: Path, ctx: Context
) -> None:
    doc = _doc()
    msp = doc.modelspace()
    # A 270 deg arc (|phi| > pi, magnification 2r/c ~= 1.41) and a line closing it, meeting with a
    # 0.008 mm gap at (0, -10). The line magnifies by 1, the arc by ~1.41, so the line must move:
    # its B = 0.008 <= 0.01 closes. If the arc moved instead, B = 0.0113 > 0.01 would refuse.
    msp.add_arc((0, 0), 10, 0, 270)
    msp.add_line((0.008, -10), (10, 0))
    result = _read(doc, tmp_path, ctx)
    assert result.ok  # closed, so the line (not the arc) was the row that moved
    assert "DXF_GAP_CLOSED" in _codes(result)
    assert "DXF_GAP_NOT_CLOSED" not in _codes(result)


@pytest.mark.req("REQ-IO-021")
@pytest.mark.req("REQ-IO-022")
def test_a_gap_whose_arc_move_exceeds_the_limit_is_refused(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    msp = doc.modelspace()
    # Two 270 deg arcs meeting with a 0.008 mm gap: the mover arc magnifies the move to
    # B = 0.008 * 2r/c = 0.0113 mm, over the 0.01 limit, so the gap is refused (REQ-IO-022).
    msp.add_arc((0, 0), 10, 0, 270)
    msp.add_arc((0.008, -20), 10, 90, 360)
    result = _read(doc, tmp_path, ctx)
    assert not result.ok
    assert "DXF_GAP_NOT_CLOSED" in _codes(result)
    gap = next(d for d in result.diagnostics if d.code == "DXF_GAP_NOT_CLOSED")
    assert gap.location is not None  # names the place (REQ-IO-022, 028)


@pytest.mark.req("REQ-IO-022")
def test_a_small_gap_is_closed_with_a_warning(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0))
    msp.add_line((10.005, 0), (10, 10))  # 0.005 mm gap, within the 0.01 limit
    msp.add_line((10, 10), (0, 10))
    msp.add_line((0, 10), (0, 0))
    result = _read(doc, tmp_path, ctx)
    assert result.ok
    assert "DXF_GAP_CLOSED" in _codes(result)


@pytest.mark.req("REQ-IO-023")
def test_a_gap_beyond_the_limit_leaves_an_open_chain(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0))
    msp.add_line((10.02, 0), (10, 10))  # 0.02 mm gap, beyond the 0.01 limit
    msp.add_line((10, 10), (0, 10))
    msp.add_line((0, 10), (0, 0))
    result = _read(doc, tmp_path, ctx)
    assert not result.ok
    assert "DXF_OPEN_CHAIN" in _codes(result)
    assert "DXF_CONTOUR_COUNT" in _codes(result)


# --- chaining, contour, diagnostics (REQ-IO-024 to 030) ------------------------------------------


@pytest.mark.req("REQ-IO-025")
def test_a_layer_selects_its_entities(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    doc.modelspace().add_lwpolyline([(0, 0), (10, 0), (10, 10), (0, 10)], format="xy", close=True,
                                    dxfattribs={"layer": "part"})  # fmt: skip
    doc.modelspace().add_lwpolyline([(20, 0), (30, 0), (30, 10)], format="xy", close=True,
                                    dxfattribs={"layer": "scrap"})  # fmt: skip
    result = _read(doc, tmp_path, ctx, layer="part")
    assert result.ok
    assert result.value is not None
    assert _area(result.value, ctx) == pytest.approx(100.0)


@pytest.mark.req("REQ-IO-025")
def test_an_empty_layer_stops_the_import(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    _square_lines(doc)
    result = _read(doc, tmp_path, ctx, layer="absent")
    assert _codes(result) == ["DXF_LAYER_EMPTY"]


@pytest.mark.req("REQ-IO-026")
def test_two_closed_contours_without_a_layer_report_the_count(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    doc.modelspace().add_lwpolyline([(0, 0), (10, 0), (10, 10), (0, 10)], format="xy", close=True)
    doc.modelspace().add_lwpolyline([(20, 0), (30, 0), (30, 10), (20, 10)], format="xy", close=True)
    result = _read(doc, tmp_path, ctx)
    assert not result.ok
    assert "DXF_CONTOUR_COUNT" in _codes(result)


@pytest.mark.req("REQ-IO-027")
def test_a_successful_import_reports_the_part_size(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    _rect_fillet(doc)
    result = _read(doc, tmp_path, ctx)
    assert result.ok
    part_size = [d for d in result.diagnostics if d.code == "DXF_PART_SIZE"]
    assert len(part_size) == 1
    assert part_size[0].severity is Severity.INFO


@pytest.mark.req("REQ-IO-028")
def test_a_diagnostic_names_the_entity(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    _rect_fillet(doc)
    doc.modelspace().add_line((2, 2, 9.0), (3, 3, 9.0))  # off-plane line, index 1
    result = _read(doc, tmp_path, ctx)
    not_planar = [d for d in result.diagnostics if d.code == "DXF_NOT_PLANAR"]
    assert not_planar
    assert "LINE" in not_planar[0].message
    assert "handle" in not_planar[0].message
    assert not_planar[0].location is not None


@pytest.mark.req("REQ-IO-029")
def test_the_same_file_gives_the_same_diagnostics_in_the_same_order(
    tmp_path: Path, ctx: Context
) -> None:
    doc = _doc()
    _rect_fillet(doc)
    doc.modelspace().add_text("a").set_placement((1, 1))
    doc.modelspace().add_line((2, 2, 8.0), (3, 3, 8.0))
    first = _codes(_read(doc, tmp_path, ctx))
    second = _codes(_read(doc, tmp_path / "again", ctx))
    assert first == second
    # DXF_SKIPPED (group 2) comes before entity diagnostics (group 3), then DXF_PART_SIZE last.
    assert first.index("DXF_SKIPPED") < first.index("DXF_NOT_PLANAR")
    assert first[-1] == "DXF_PART_SIZE"


@pytest.mark.req("REQ-IO-030")
def test_a_cancelled_context_returns_cancelled(tmp_path: Path, ctx: Context) -> None:
    doc = _doc()
    _rect_fillet(doc)
    ctx.cancel.cancel()
    result = _read(doc, tmp_path, ctx)
    assert not result.ok
    assert _codes(result) == ["CANCELLED"]

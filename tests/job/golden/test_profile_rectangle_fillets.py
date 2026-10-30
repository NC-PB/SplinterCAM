# SPDX-License-Identifier: Apache-2.0
"""The golden case `testdata/zoo/profile-rectangle-fillets` run from its `case.json`
(src/splintercam/job/SPEC.md, REQ-JOB-023 and Test plan; research 22 test 1 on research 21
test 1's drawing). The record's checks run always; the `ncx` checks need the real `ncx` on the
path and `SPLINTERCAM_NCXCHANGE`, and are skipped with a message otherwise (DEC-JOB-004). The
comparison with `expected/` comes once a person has approved it (AQ-011 item 5)."""

import json
import os
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from job_files import CASE, codes, listing
from offset2d_oracles import true_curve_band_mm
from profile_checks import cut_points, distance_to_box, pass_moves, rounded_rect_distances
from profile_checks import signed_area as polyline_area
from splintercam.cl import ClOperation, MoveKind, Role
from splintercam.foundation import ToleranceSet
from splintercam.job import default_context, run_job
from splintercam.model import StockBox

_CASE: dict[str, Any] = json.loads((CASE / "case.json").read_text(encoding="utf-8"))
_CHECKS: dict[str, Any] = _CASE["checks"]
_COMPARE_MM: float = _CASE["tolerance"]["compare_mm"]
_NCX = shutil.which("ncx")
_CHECKOUT = os.environ.get("SPLINTERCAM_NCXCHANGE")


def _record_run(tmp_path: Path) -> ClOperation:
    # No ncx: any existing file of the job's machine name stands for the machine (no
    # JOB_MACHINE_OVERRIDDEN, AQ-036) and the run stops at JOB_NCX_NOT_FOUND after stage 8, with
    # the record (SPEC, Test plan).
    stand_in = tmp_path / _CHECKS["ncx"]["machine"]
    stand_in.write_bytes(b"")
    report = run_job(CASE / _CASE["input"]["job"], tmp_path / "out",
                     ncx_executable=tmp_path / "no-ncx", machine_file=stand_in,
                     ctx=default_context())  # fmt: skip
    assert codes(report.diagnostics) == ["JOB_INPUTS", "DXF_PART_SIZE", "JOB_NCX_NOT_FOUND"]
    assert report.cl_data is not None
    [operation] = report.cl_data.operations
    assert operation.header.name == _CASE["operation"]["name"]
    return operation


def _cut(op: ClOperation, rows: np.ndarray) -> np.ndarray:
    return cut_points(op, rows[op.moves.role[rows] == Role.CUT])


@pytest.mark.req("REQ-JOB-023")
def test_the_case_folder_holds_its_files() -> None:
    assert listing(CASE) == ["README.md", "case.json", "job.json", "make_part.py", "part.dxf"]
    assert _CASE["id"] == CASE.name
    licences = (CASE.parents[1] / "LICENSES.md").read_text(encoding="utf-8")
    assert f"zoo/{CASE.name}/" in licences


@pytest.mark.req("REQ-JOB-023")
def test_three_passes_at_their_levels(tmp_path: Path) -> None:
    levels = [level for level, _ in pass_moves(_record_run(tmp_path))]
    assert levels == pytest.approx(_CHECKS["pass_levels_mm"], abs=_COMPARE_MM)


@pytest.mark.req("REQ-JOB-023")
def test_each_pass_is_the_sides_offset_and_the_fillets_in_the_band(tmp_path: Path) -> None:
    op = _record_run(tmp_path)
    fillets = _CHECKS["fillets"]
    tolerances = ToleranceSet.for_operation(_CASE["tolerance"]["chord_mm"]).value
    assert tolerances is not None
    band = true_curve_band_mm(tolerances)  # the case's tol
    for _, rows in pass_moves(op):
        assert set(op.moves.kind[rows[op.moves.role[rows] == Role.CUT]].tolist()) == {MoveKind.LINE}
        cut = _cut(op, rows)
        assert np.abs(cut[0] - cut[-1]).max() <= _COMPARE_MM  # a closed loop, S to S
        smallest, largest = rounded_rect_distances(cut, tuple(fillets["part_box_mm"]),
                                                   fillets["part_radius_mm"])  # fmt: skip
        assert smallest.min() >= fillets["offset_mm"] - _COMPARE_MM
        assert largest.max() <= fillets["offset_mm"] + band + _COMPARE_MM
        a, b = cut[:-1], cut[1:]
        for side in _CHECKS["sides"]:
            axis = 1 if side["axis"] == "y" else 0
            on = np.abs(a[:, axis] - side["at_mm"]) <= _COMPARE_MM
            on &= np.abs(b[:, axis] - side["at_mm"]) <= _COMPARE_MM
            on &= np.abs(b[:, 1 - axis] - a[:, 1 - axis]) > 1.0  # not a fillet's chord
            holds_s = abs(cut[0, axis] - side["at_mm"]) <= _COMPARE_MM
            assert on.sum() == (2 if holds_s else 1)  # S splits its side in two
            length = float(np.abs(b[on, 1 - axis] - a[on, 1 - axis]).sum())
            assert length >= side["length_mm"] - 2 * _COMPARE_MM
        assert (polyline_area(cut) < 0.0) == (_CHECKS["direction"] == "clockwise")


@pytest.mark.req("REQ-JOB-023")
def test_the_start_and_the_approach_point(tmp_path: Path) -> None:
    op = _record_run(tmp_path)
    start = _CHECKS["start"]
    for _, rows in pass_moves(op):
        s = _cut(op, rows)[0]
        assert abs(s[0] - start["x_mm"]) <= _COMPARE_MM
        assert min(abs(s[1] - y) for y in start["y_mm"]) <= _COMPARE_MM
    assert op.moves.kind[1] == MoveKind.RAPID  # move 1: the rapid over P (REQ-CL, research 10)
    p = (float(op.moves.end_mm[1, 0]), float(op.moves.end_mm[1, 1]))
    job = json.loads((CASE / "job.json").read_text(encoding="utf-8"))
    stock = StockBox(tuple(job["stock"]["min_mm"]), tuple(job["stock"]["max_mm"]))
    assert distance_to_box(p, stock) >= _CHECKS["approach_clear_of_stock_mm"] - _COMPARE_MM


@pytest.mark.req("REQ-JOB-023")
@pytest.mark.skipif(
    _NCX is None or _CHECKOUT is None,
    reason="the pinned ncx is not on the path or SPLINTERCAM_NCXCHANGE is not set "
    "(plan 0007, question 3): the golden case is not compiled here",
)
def test_ncx_checks_and_compiles_the_case(tmp_path: Path) -> None:
    assert _CHECKOUT is not None
    machine = Path(_CHECKOUT) / "machines" / _CHECKS["ncx"]["machine"]
    report = run_job(CASE / _CASE["input"]["job"], tmp_path / "out", machine_file=machine,
                     ctx=default_context())  # fmt: skip
    assert report.ok, report.diagnostics
    assert codes(report.diagnostics) == _CHECKS["ncx"]["codes"]
    assert listing(tmp_path / "out") == sorted(_CHECKS["ncx"]["files"])

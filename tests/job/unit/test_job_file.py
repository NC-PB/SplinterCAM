# SPDX-License-Identifier: Apache-2.0
"""Stage 1, the job file (src/splintercam/job/SPEC.md, REQ-JOB-002 to 009 and 020): reading, the
format and version, the keys and their containers, the values `job` checks, the paths, and the
order of the diagnostics."""

import json
import math
from pathlib import Path
from typing import Any

import pytest

from job_files import Job, codes, example, job_folder, listing, operation
from splintercam.foundation import Context, Diagnostic, Severity
from splintercam.job import JobReport, run_job
from splintercam.job._layout import read_job_file
from splintercam.model import MeasurementPoint


def _run(tmp_path: Path, ctx: Context, job: Job | str | bytes, **kwargs: Any) -> JobReport:
    job_file = job_folder(tmp_path / "job", job)
    return run_job(job_file, tmp_path / "out", ncx_executable=tmp_path / "no-ncx", ctx=ctx,
                   **kwargs)  # fmt: skip


def _errors(report: JobReport) -> list[tuple[str, str | None]]:
    return [(d.code, d.location) for d in report.diagnostics if d.severity is Severity.ERROR]


def _only(report: JobReport, code: str) -> Diagnostic:
    found = [d for d in report.diagnostics if d.code == code]
    assert len(found) == 1, report.diagnostics
    return found[0]


def _text(job: Job) -> str:
    return json.dumps(job, indent=2)


# --- REQ-JOB-002: reading -------------------------------------------------------------------------


@pytest.mark.req("REQ-JOB-002")
def test_an_unreadable_job_file_names_the_os_reason(tmp_path: Path, ctx: Context) -> None:
    report = run_job(tmp_path / "missing.json", tmp_path / "out", ctx=ctx)
    assert codes(report.diagnostics) == ["JOB_FILE_UNREADABLE"]
    found = report.diagnostics[0]
    assert found.severity is Severity.ERROR
    assert "No such file" in found.message or "cannot find" in found.message
    assert listing(tmp_path / "out") == []
    assert not (tmp_path / "out").exists()


@pytest.mark.req("REQ-JOB-002")
@pytest.mark.parametrize(
    ("text", "where"),
    [
        ('{\n  "format": "splintercam-job",\n  "version": 1,,\n}', "line 3, column 16"),
        ("[1, 2]", "line 1, column 1"),
        ('"job"', "line 1, column 1"),
        ('{"format": "splintercam-job",\n "version": NaN}', "line 2, column 13"),
        ('{"format": "splintercam-job",\n "version": Infinity}', "line 2, column 13"),
        ('{"a": "NaN Infinity",\n "version": -Infinity}', "line 2, column 13"),
        ('{"format": "splintercam-job",\n  "x": [1, 1e400]}', "line 2, column 12"),
        ('{"version": 1, "x": -1e400}', "line 1, column 21"),
    ],
    ids=["syntax", "array", "string", "nan", "inf", "minus-inf-after-a-string", "1e400", "-1e400"],
)
def test_not_one_json_object_or_a_non_finite_number_is_invalid(
    tmp_path: Path, ctx: Context, text: str, where: str
) -> None:
    report = _run(tmp_path, ctx, text)
    assert _errors(report) == [("JOB_FILE_INVALID", where)]
    assert codes(report.diagnostics) == ["JOB_FILE_INVALID"]


@pytest.mark.req("REQ-JOB-002")
def test_a_file_not_in_utf8_is_invalid(tmp_path: Path, ctx: Context) -> None:
    report = _run(tmp_path, ctx, b'{"format": "splintercam-job",\n "x": "\xe9"}')
    assert _errors(report) == [("JOB_FILE_INVALID", "line 2, column 8")]


@pytest.mark.req("REQ-JOB-002")
def test_a_byte_order_mark_is_accepted(tmp_path: Path, ctx: Context) -> None:
    report = _run(tmp_path, ctx, b"\xef\xbb\xbf" + _text(example()).encode("utf-8"))
    assert "JOB_FILE_INVALID" not in codes(report.diagnostics)
    assert report.cl_data is not None


# --- REQ-JOB-003: format and version --------------------------------------------------------------


@pytest.mark.req("REQ-JOB-003")
@pytest.mark.parametrize(
    ("key", "value"),
    [("version", 2), ("version", True), ("version", 1.0), ("version", "1"), ("format", "job")],
)
def test_another_format_or_version_is_refused_and_nothing_else_checked(
    tmp_path: Path, ctx: Context, key: str, value: object
) -> None:
    job = example()
    job[key] = value
    del job["tools"]  # would be JOB_KEY_MISSING if the rest were checked
    job["colour"] = "red"
    report = _run(tmp_path, ctx, job)
    assert codes(report.diagnostics) == ["JOB_FORMAT_UNSUPPORTED"]
    message = report.diagnostics[0].message
    assert repr(job["format"]) in message
    assert repr(job["version"]) in message


@pytest.mark.req("REQ-JOB-003")
def test_a_missing_version_is_refused(tmp_path: Path, ctx: Context) -> None:
    job = example()
    del job["version"]
    assert codes(_run(tmp_path, ctx, job).diagnostics) == ["JOB_FORMAT_UNSUPPORTED"]


# --- REQ-JOB-004 and 005: keys and containers -----------------------------------------------------


_DELETE = object()


def _change(job: Job, path: tuple[str | int, ...], value: object) -> None:
    """Set the value at `path` in `job`, or delete it for `_DELETE`."""
    owner: Any = job
    for step in path[:-1]:
        owner = owner[step]
    if value is _DELETE:
        del owner[path[-1]]
    else:
        owner[path[-1]] = value


@pytest.mark.req("REQ-JOB-004")
@pytest.mark.parametrize(
    ("path", "value", "expected"),
    [
        (("tools",), 5, ("JOB_STRUCTURE_INVALID", "tools")),
        (("tools",), [5], ("JOB_STRUCTURE_INVALID", "tools[1]")),
        (("part",), None, ("JOB_KEY_MISSING", "part")),
        (("stock",), _DELETE, ("JOB_KEY_MISSING", "stock")),
        (("stock", "min_mm"), 0.0, ("JOB_STRUCTURE_INVALID", "stock.min_mm")),
        (("setup", "work_offset"), None, ("VALUE_TYPE_INVALID", "setup")),
        (("operations", 0, "tol_mm"), _DELETE, ("JOB_KEY_MISSING", "operations[1].tol_mm")),
        (("operations", 0, "parameters"), [1],
         ("JOB_STRUCTURE_INVALID", "operations[1].parameters")),
        (("tools", 0, "points"), {}, ("JOB_STRUCTURE_INVALID", "tools[1].points")),
        (("tools", 0, "points", 0, "axial_offset_mm"), _DELETE,
         ("JOB_KEY_MISSING", "tools[1].points[1].axial_offset_mm")),
    ],
)  # fmt: skip
def test_a_missing_key_or_a_wrong_container_is_named_by_its_path(
    tmp_path: Path, ctx: Context, path: tuple[str | int, ...], value: object,
    expected: tuple[str, str],
) -> None:  # fmt: skip
    job = example()
    _change(job, path, value)
    assert _errors(_run(tmp_path, ctx, job)) == [expected]


@pytest.mark.req("REQ-JOB-004")
@pytest.mark.parametrize("key", ["points", "point", "parameters", "layer", "unit"])
def test_an_optional_key_given_as_null_is_the_default(
    tmp_path: Path, ctx: Context, key: str
) -> None:
    job = example()
    if key == "points":
        job["tools"][0]["points"] = None
    elif key in ("layer", "unit"):
        job["part"][key] = None
    else:
        operation(job)[key] = None
    report = _run(tmp_path, ctx, job)
    if key == "parameters":  # none given: the profile's step-down, depths and feeds are missing
        assert {code for code, _ in _errors(report)} == {"PARAM_MISSING"}
    else:
        assert _errors(report) == [("JOB_NCX_NOT_FOUND", None)]


@pytest.mark.req("REQ-JOB-005")
def test_a_misspelt_key_is_unknown(tmp_path: Path, ctx: Context) -> None:
    job = example()
    job["tools"][0]["diameter"] = 10.0
    job["stock"]["min"] = [0, 0, 0]
    assert _errors(_run(tmp_path, ctx, job)) == [
        ("JOB_KEY_UNKNOWN", "tools[1].diameter"),
        ("JOB_KEY_UNKNOWN", "stock.min"),
    ]


@pytest.mark.req("REQ-JOB-005")
def test_a_key_given_twice_is_repeated(tmp_path: Path, ctx: Context) -> None:
    text = _text(example()).replace('"tool": 1,', '"tool": 1, "tool": 2,', 1)
    report = _run(tmp_path, ctx, text)
    assert _errors(report) == [("JOB_KEY_REPEATED", "operations[1].tool")]


@pytest.mark.req("REQ-JOB-005", "REQ-JOB-006")
def test_a_parameter_given_twice_is_passed_to_model(tmp_path: Path, ctx: Context) -> None:
    text = _text(example()).replace('"z_top_mm": 0.0,', '"z_top_mm": 0.0, "z_top_mm": 1.0,', 1)
    report = _run(tmp_path, ctx, text)
    assert _errors(report) == [("PARAM_REPEATED", "operation 1 (PROFILE_1), parameter z_top_mm")]


# --- REQ-JOB-006: values passed to model as read --------------------------------------------------


@pytest.mark.req("REQ-JOB-006")
def test_a_value_of_the_wrong_type_is_reported_by_model(tmp_path: Path, ctx: Context) -> None:
    job = example()
    job["tools"][0]["diameter_mm"] = "10"
    report = _run(tmp_path, ctx, job)
    assert [code for code, _ in _errors(report)] == ["VALUE_TYPE_INVALID"]


@pytest.mark.req("REQ-JOB-006")
def test_the_values_reach_model_as_read(tmp_path: Path) -> None:
    job = example()
    job["tools"][0]["points"].append({"axial_offset_mm": 40, "register_radius_mm": "2"})
    job["tools"][0]["diameter_mm"] = True
    job["stock"]["min_mm"] = [-5, -5.0, [1]]
    operation(job)["point"] = 2
    job_file = job_folder(tmp_path, job)
    read = read_job_file(job_file, None, None)
    assert read.value is not None, read.diagnostics
    data = read.value.data
    tool = data.tools[0]
    assert tool.diameter_mm is True
    assert tool.points == (MeasurementPoint(1, 0.0, 0.0), MeasurementPoint(2, 40, "2"))  # type: ignore[arg-type]
    assert data.setup.stock.min_mm == (-5, -5.0, (1,))
    op = data.setup.operations[0]
    assert (op.name, op.strategy, op.tool_number, op.point_number) == ("PROFILE_1", "profile", 1, 2)
    assert (op.spindle_rpm, op.tol_mm) == (8000, 0.01)
    assert op.parameters[0] == ("allowance_mm", 0.0)
    assert [name for name, _ in op.parameters] == list(operation(job)["parameters"])
    assert data.setup.work_offset == 1


@pytest.mark.req("REQ-JOB-006")
def test_points_left_out_give_the_tip(tmp_path: Path) -> None:
    job = example()
    del job["tools"][0]["points"]
    del operation(job)["point"]
    del operation(job)["parameters"]
    read = read_job_file(job_folder(tmp_path, job), None, None)
    assert read.value is not None
    data = read.value.data
    assert data.tools[0].points == (MeasurementPoint(1, 0.0, 0.0),)
    assert data.setup.operations[0].point_number == 1
    assert data.setup.operations[0].parameters == ()


# --- REQ-JOB-007 and 008: the values job checks ---------------------------------------------------


@pytest.mark.req("REQ-JOB-007")
@pytest.mark.parametrize("kind", ["ball_end_mill", None, 1])
def test_a_tool_other_than_a_flat_end_mill_is_refused(
    tmp_path: Path, ctx: Context, kind: object
) -> None:
    job = example()
    job["tools"][0]["type"] = kind
    report = _run(tmp_path, ctx, job)
    assert _errors(report) == [("JOB_TOOL_TYPE_UNSUPPORTED", "tools[1].type")]
    assert "T1" in report.diagnostics[0].message


@pytest.mark.req("REQ-JOB-008")
@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("program", "number", True),
        ("program", "number", 1001.5),
        ("program", "number", "1001"),
        ("program", "number", None),
        ("program", "name", 5),
        ("part", "dxf", ""),
        ("part", "dxf", 3),
        ("part", "layer", 0),
        ("part", "unit", "cm"),
        ("part", "unit", "MM"),
        (None, "machine", ""),
        (None, "machine", ["a.toml"]),
    ],
)
def test_a_part_path_or_program_value_is_checked(
    tmp_path: Path, ctx: Context, section: str | None, key: str, value: object
) -> None:
    job = example()
    (job if section is None else job[section])[key] = value
    path = key if section is None else f"{section}.{key}"
    assert _errors(_run(tmp_path, ctx, job)) == [("JOB_VALUE_INVALID", path)]


@pytest.mark.req("REQ-JOB-008")
@pytest.mark.parametrize("unit", ["mm", "inch"])
def test_both_units_are_read(tmp_path: Path, ctx: Context, unit: str) -> None:
    job = example()
    job["part"]["unit"] = unit
    job_file = job_folder(tmp_path / "job", job, insunits=0)  # a DXF without units takes it
    report = run_job(job_file, tmp_path / "out", ncx_executable=tmp_path / "no-ncx", ctx=ctx)
    # In inches the part is 2540 mm wide (research 21 test 4) and the profile refuses the stock.
    expected = "JOB_NCX_NOT_FOUND" if unit == "mm" else "PROFILE_STOCK_SMALL"
    assert [code for code, _ in _errors(report)] == [expected]
    width = 100.0 * (25.4 if unit == "inch" else 1.0)
    assert f"{width:g}" in _only(report, "DXF_PART_SIZE").message


# --- REQ-JOB-020: the order -----------------------------------------------------------------------


@pytest.mark.req("REQ-JOB-020")
def test_the_example_with_tol_for_tol_mm(tmp_path: Path, ctx: Context) -> None:
    job = example()
    operation(job)["tol"] = operation(job).pop("tol_mm")
    report = _run(tmp_path, ctx, job)
    assert [(d.code, d.location) for d in report.diagnostics][:2] == [
        ("JOB_KEY_MISSING", "operations[1].tol_mm"),
        ("JOB_KEY_UNKNOWN", "operations[1].tol"),
    ]
    assert codes(report.diagnostics) == ["JOB_KEY_MISSING", "JOB_KEY_UNKNOWN", "JOB_INPUTS"]
    assert not (tmp_path / "out").exists()


@pytest.mark.req("REQ-JOB-020")
def test_stage_1_reports_depth_first_unknown_keys_sorted_and_job_inputs_last(
    tmp_path: Path, ctx: Context
) -> None:
    job = example()
    job["part"]["dxf"] = ""
    job["tools"][0]["type"] = "drill"
    job["tools"][0]["colour"] = "red"
    job["tools"][0]["Brand"] = "x"
    job["tools"].append({"number": 2})
    del job["program"]
    job["extra"] = 1
    text = _text(job).replace('"tool": 1,', '"tool": 1, "tool": 1,', 1)
    report = _run(tmp_path, ctx, text)
    assert [(d.code, d.location) for d in report.diagnostics] == [
        ("JOB_VALUE_INVALID", "part.dxf"),
        ("JOB_TOOL_TYPE_UNSUPPORTED", "tools[1].type"),
        ("JOB_KEY_UNKNOWN", "tools[1].Brand"),
        ("JOB_KEY_UNKNOWN", "tools[1].colour"),
        ("JOB_KEY_MISSING", "tools[2].type"),
        ("JOB_KEY_MISSING", "tools[2].diameter_mm"),
        ("JOB_KEY_MISSING", "tools[2].flute_length_mm"),
        ("JOB_KEY_REPEATED", "operations[1].tool"),
        ("JOB_KEY_MISSING", "program"),
        ("JOB_KEY_UNKNOWN", "extra"),
        ("JOB_INPUTS", None),
    ]


@pytest.mark.req("REQ-JOB-002")
def test_numbers_that_are_finite_pass(tmp_path: Path) -> None:
    job = example()
    operation(job)["parameters"]["z_bottom_mm"] = -1e308
    read = read_job_file(job_folder(tmp_path, job), None, None)
    assert read.value is not None
    value = dict(read.value.data.setup.operations[0].parameters)["z_bottom_mm"]
    assert math.isfinite(value)


@pytest.mark.req("REQ-JOB-002")
def test_a_file_nested_too_deeply_is_invalid(tmp_path: Path, ctx: Context) -> None:
    report = _run(tmp_path, ctx, '{"a": ' + "[" * 100_000)
    assert _errors(report) == [("JOB_FILE_INVALID", "line 1, column 1")]


@pytest.mark.req("REQ-JOB-002")
def test_an_int_beyond_the_double_range_is_invalid(tmp_path: Path, ctx: Context) -> None:
    big = "1" + "0" * 400  # an int json reads, beyond the largest double
    report = _run(tmp_path, ctx, '{"version": 1,\n "a": ' + big + ', "b": NaN}')
    assert _errors(report) == [("JOB_FILE_INVALID", "line 2, column 7")]
    assert codes(_run(tmp_path / "2", ctx, '{"a": ' + "9" * 5000 + "}").diagnostics) == [
        "JOB_FILE_INVALID"
    ]


@pytest.mark.req("REQ-JOB-005")
def test_a_repeated_key_is_one_diagnostic_whatever_its_first_value(
    tmp_path: Path, ctx: Context
) -> None:
    text = _text(example()).replace('"part": {', '"part": null, "part": {', 1)
    assert _errors(_run(tmp_path, ctx, text)) == [("JOB_KEY_REPEATED", "part")]

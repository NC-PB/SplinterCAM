# SPDX-License-Identifier: Apache-2.0
"""`run_ncx` against a fake `ncx` (REQ-NCX-018, 019, 022 to 025; tests/support/ncx_fake.py)."""

import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest

import splintercam.ncx._run as run_module
from ncx_fake import FakeNcx, MakeFake, Step
from splintercam.foundation import CANCELLED, Context, Diagnostic, Severity
from splintercam.ncx import NcxCall, NcxProgram, NcxSection, NcxStep, run_ncx

_PROGRAM = NcxProgram("", (NcxSection("operation 1 (A)", 5, 50, 0.001),))
_ALL = (NcxStep.FORMAT, NcxStep.CHECK, NcxStep.COMPILE)
_ERROR = "{ncx}(7): ERROR VM440: F on a RAPID\n"
_WARNING = "{ncx}(7): WARNING VM300: unused word\n"
_UNREAD = "Unhandled exception\n"


def _codes(found: tuple[Diagnostic, ...]) -> list[str]:
    return [d.code for d in found]


def _cancel_once(fake: FakeNcx, step: NcxStep, ctx: Context) -> threading.Thread:
    """A started thread that cancels as soon as the fake has started `step` (not on a fixed
    clock, so a slow interpreter start under load does not move the cancel into another step);
    after 60 s it cancels anyway, so a hang fails the test instead of the job."""

    def watch() -> None:
        deadline = time.monotonic() + 60.0
        while step not in fake.ran() and time.monotonic() < deadline:
            time.sleep(0.01)
        ctx.cancel.cancel()

    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    return thread


@pytest.mark.req("REQ-NCX-018")
def test_the_three_steps_run_with_their_arguments(ctx: Context, fake_ncx: MakeFake) -> None:
    fake = fake_ncx()
    call = fake.call
    result = run_ncx(call, _PROGRAM, ctx)
    assert result.ok
    assert result.value == _ALL
    assert result.diagnostics == ()
    file, machine, out = str(call.ncx_file), str(call.machine_file), str(call.output_dir)
    expected = {
        NcxStep.FORMAT: ["--check", file],
        NcxStep.CHECK: [file, "--machine", machine, "--strict"],
        NcxStep.COMPILE: [file, "--machine", machine, "--output", out],
    }
    for step, arguments in expected.items():
        record = fake.record(step)
        assert record["argv"] == arguments
        assert Path(str(record["cwd"])).samefile(call.work_dir)


@pytest.mark.req("REQ-NCX-018", "REQ-NCX-022")
def test_a_long_output_does_not_block(ctx: Context, fake_ncx: MakeFake) -> None:
    line = "{ncx}(6): WARNING CMP020: X1.0000001 written as X1.0\n"
    fake = fake_ncx(compile=Step(stderr=line * 100_000, stdout="x\n" * 100_000))
    watchdog = threading.Timer(60.0, ctx.cancel.cancel)  # a pipe deadlock fails, not hangs
    watchdog.start()
    result = run_ncx(fake.call, _PROGRAM, ctx)
    watchdog.cancel()
    assert result.ok, result.diagnostics[:3]
    assert _codes(result.diagnostics) == ["NCX_ROUNDED"]
    assert result.diagnostics[0].message.startswith("100000 ")
    assert result.diagnostics[0].location == "operation 1 (A)"


@pytest.mark.req("REQ-NCX-019", "REQ-NCX-023")
def test_check_failing_stops_before_compile(ctx: Context, fake_ncx: MakeFake) -> None:
    fake = fake_ncx(check=Step(exit=1, stderr=_ERROR))
    result = run_ncx(fake.call, _PROGRAM, ctx)
    assert not result.ok
    assert result.value == (NcxStep.FORMAT, NcxStep.CHECK)
    assert fake.ran() == [NcxStep.FORMAT, NcxStep.CHECK]
    assert _codes(result.diagnostics) == ["VM440", "NCX_STEP_FAILED"]
    assert result.diagnostics[1].location == "ncx check"


@pytest.mark.req("REQ-NCX-019")
def test_an_error_with_exit_0_stops_before_compile(ctx: Context, fake_ncx: MakeFake) -> None:
    fake = fake_ncx(format=Step(stderr=_ERROR))
    result = run_ncx(fake.call, _PROGRAM, ctx)
    assert not result.ok
    assert fake.ran() == [NcxStep.FORMAT, NcxStep.CHECK]
    assert _codes(result.diagnostics) == ["VM440"]


@pytest.mark.req("REQ-NCX-019", "REQ-NCX-027")
@pytest.mark.parametrize("step", ["format", "check"])
@pytest.mark.parametrize(("stderr", "code"), [(_WARNING, "VM300"), (_UNREAD, "NCX_OUTPUT_UNREAD")])
def test_a_warning_with_exit_0_fails_and_stops_before_compile(
    ctx: Context, fake_ncx: MakeFake, step: str, stderr: str, code: str
) -> None:
    # Peter, AQ-036 item 4: format --check and check --strict fail closed as compile does.
    fake = fake_ncx(**{step: Step(stderr=stderr)})
    result = run_ncx(fake.call, _PROGRAM, ctx)
    assert not result.ok
    assert fake.ran() == [NcxStep.FORMAT, NcxStep.CHECK]
    assert _codes(result.diagnostics) == [code, "NCX_STRICT_FAILED"]
    assert result.diagnostics[-1].location == f"ncx {step}"


@pytest.mark.req("REQ-NCX-019", "REQ-NCX-023")
def test_a_format_difference_still_runs_check(ctx: Context, fake_ncx: MakeFake) -> None:
    fake = fake_ncx(format=Step(exit=1, stdout="-RAPID  Z=5.0\n+RAPID Z=5.0\n"))
    result = run_ncx(fake.call, _PROGRAM, ctx)
    assert not result.ok
    assert fake.ran() == [NcxStep.FORMAT, NcxStep.CHECK]
    (failed,) = result.diagnostics
    assert (failed.code, failed.severity, failed.location) == (
        "NCX_STEP_FAILED",
        Severity.ERROR,
        "ncx format",
    )
    assert "+RAPID Z=5.0" in failed.message


@pytest.mark.req("REQ-NCX-023", "REQ-NCX-027")
@pytest.mark.parametrize(
    ("stderr", "codes"), [(_WARNING, ["VM300", "NCX_STRICT_FAILED"]), ("", [])]
)
def test_exit_1_is_a_failed_step(
    ctx: Context, fake_ncx: MakeFake, stderr: str, codes: list[str]
) -> None:
    fake = fake_ncx(check=Step(exit=1, stderr=stderr))
    result = run_ncx(fake.call, _PROGRAM, ctx)
    assert not result.ok
    assert _codes(result.diagnostics) == [*codes, "NCX_STEP_FAILED"]
    assert "check" in result.diagnostics[-1].message


@pytest.mark.req("REQ-NCX-023", "REQ-NCX-027")
@pytest.mark.parametrize("code", [2, 3])
def test_another_exit_code_stops_the_call(ctx: Context, fake_ncx: MakeFake, code: int) -> None:
    fake = fake_ncx(format=Step(exit=code, stderr=_WARNING))
    result = run_ncx(fake.call, _PROGRAM, ctx)
    assert not result.ok
    assert result.value == (NcxStep.FORMAT,)
    assert fake.ran() == [NcxStep.FORMAT]
    assert _codes(result.diagnostics) == ["VM300", "NCX_STRICT_FAILED", "NCX_CALL_FAILED"]
    assert str(code) in result.diagnostics[-1].message


@pytest.mark.req("REQ-NCX-023")
def test_a_missing_executable_fails_the_call(
    ctx: Context, fake_ncx: MakeFake, tmp_path: Path
) -> None:
    call = replace(fake_ncx().call, executable=tmp_path / "no-ncx")
    result = run_ncx(call, _PROGRAM, ctx)
    assert not result.ok
    assert result.value == ()
    (failed,) = result.diagnostics
    assert (failed.code, failed.location) == ("NCX_CALL_FAILED", "ncx format")


@pytest.mark.req("REQ-NCX-024")
def test_cancelled_at_entry_runs_nothing(ctx: Context, fake_ncx: MakeFake) -> None:
    fake = fake_ncx()
    ctx.cancel.cancel()
    result = run_ncx(fake.call, _PROGRAM, ctx)
    assert result.value is None
    assert result.diagnostics == (CANCELLED,)
    assert fake.ran() == []


@pytest.mark.req("REQ-NCX-024", "REQ-NCX-025", "REQ-NCX-027")
def test_cancelled_while_a_step_runs(ctx: Context, fake_ncx: MakeFake) -> None:
    fake = fake_ncx(format=Step(stderr=_WARNING), check=Step(sleep=60.0))
    started = time.monotonic()
    watcher = _cancel_once(fake, NcxStep.CHECK, ctx)
    result = run_ncx(fake.call, _PROGRAM, ctx)
    watcher.join()
    assert time.monotonic() - started < 50.0  # the check was stopped, not waited for
    assert result.value is None
    assert _codes(result.diagnostics) == ["VM300", "NCX_STRICT_FAILED", "CANCELLED"]
    assert fake.ran() == [NcxStep.FORMAT, NcxStep.CHECK]


@pytest.mark.req("REQ-NCX-024")
def test_cancelled_during_the_last_step(
    ctx: Context, fake_ncx: MakeFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    # DEC-NCX-015 (c): the token is set while compile runs, and compile ends before a poll.
    run_step = run_module._run_step  # pyright: ignore[reportPrivateUsage]

    def then_cancel(step: NcxStep, call: NcxCall, context: Context) -> object:
        outcome = run_step(step, call, context)
        if step is NcxStep.COMPILE:
            context.cancel.cancel()
        return outcome

    monkeypatch.setattr(run_module, "_run_step", then_cancel)
    fake = fake_ncx()
    result = run_ncx(fake.call, _PROGRAM, ctx)
    assert fake.ran() == list(_ALL)
    assert result.value is None
    assert result.diagnostics == (CANCELLED,)


@pytest.mark.req("REQ-NCX-018", "REQ-NCX-020", "REQ-NCX-027")
def test_output_is_decoded_as_utf8_with_replacement(ctx: Context, fake_ncx: MakeFake) -> None:
    fake = fake_ncx(format=Step(stderr="bad \udcff byte\n"))
    result = run_ncx(fake.call, _PROGRAM, ctx)
    strict = "ncx format reported a warning or an unread line; it fails as under --strict"
    assert [(d.code, d.message) for d in result.diagnostics] == [
        ("NCX_OUTPUT_UNREAD", "bad � byte"),
        ("NCX_STRICT_FAILED", strict),  # REQ-NCX-027
    ]


@pytest.mark.req("REQ-NCX-018")
@pytest.mark.parametrize(
    "field", ["executable", "work_dir", "ncx_file", "machine_file", "output_dir"]
)
def test_a_relative_path_is_refused(ctx: Context, fake_ncx: MakeFake, field: str) -> None:
    fake = fake_ncx()
    call = replace(fake.call, **{field: Path("relative")})
    with pytest.raises(ValueError, match=f"REQ-NCX-018: paths not absolute: {field}$"):
        run_ncx(call, _PROGRAM, ctx)
    assert fake.ran() == []

# AGENTS.md: apps/cli

Layer 6. `splintercam run JOB_FILE --output DIR [--ncx PATH] [--machine PATH] [--strict] [--json]`
over `job.run_job`: the arguments, one call, the text or JSON report and the exit code. Contract:
`./SPEC.md`. Why it is built this way: `./DECISIONS.md`. Public API: `./__init__.py` (`main`,
`entry`). No C++ part. Imports nothing from SplinterCAM but `job` (`apps-use-job-only`).

## Files

- `_cli.py`: the parser, `exit_code`, the two reports, `main` and `entry`.
- `__main__.py`: `python -m splintercam.apps.cli`; `entry` is the `splintercam` console script's
  target in `pyproject.toml`.

## Commands

- `uv run pytest tests/apps/cli` (or `tools/test-one apps/cli`).
- The end-to-end test needs `ncx` on the path and `SPLINTERCAM_NCXCHANGE` set to the pinned
  NCXchange checkout; otherwise it is skipped with a message naming what is missing. CI has both.

## Invariants that must never break

- The exit code is a function of the report and `--strict` alone (REQ-CLI-005).
- stdout names files only for exit code 0, in the text and the JSON report (REQ-CLI-003, 004).
- `--json` writes nothing on stderr; the text report one line per diagnostic (REQ-CLI-003, 004).
- `main` returns argparse's exit codes; it never raises `SystemExit` (REQ-CLI-006).

## Known pitfalls

- ruff bans `print` (T201); the reports write with `sys.stdout.write` and `sys.stderr.write`.
- The tests replace `splintercam.apps.cli._cli.run_job`; an import of `run_job` elsewhere is not
  replaced.
- Hypothesis refuses function-scoped fixtures: the property test patches with `mock.patch` and
  captures with `contextlib.redirect_stdout`, not `monkeypatch` and `capsys`.
- `apps/__init__.py` only groups modules and must import nothing (arch-check).

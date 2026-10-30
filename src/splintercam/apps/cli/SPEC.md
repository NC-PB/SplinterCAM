# SPEC: apps/cli

<!-- The headless runner, cut to plan 0007, step 7 (D-160): one command, `splintercam run`, over job's `run_job`.
     The commands `new`, `compute`, `check`, `output`, `sheet` and `info` of the feature map come with later plans. -->

| | |
| --- | --- |
| Status | Reviewed (2026-10-27, Peter: AQ-012 and AQ-013 in `docs/agents/questions/`, all as recommended). Choices marked "(ours)" are in `src/splintercam/apps/cli/DECISIONS.md` and stand as the contract |
| Layer | 6 (see architecture/modules.yaml) |
| Depends on | job only (`run_job`, `JobReport`, `Diagnostic`, `Severity`; docs/dev/03, rule 6, `apps-use-job-only`) |
| Research | none (`architecture/modules.yaml` lists none for apps). Inputs: Project Spike `product/feature-map.md`, section 1 (the command line, its exit codes and reports; Peter, 2026-10-03); [27][r27], Exit codes (`ncx`'s convention) |
| Decisions | D-055 (determinism); the feature map's command line (section 1) |
| Owner | Peter Burgener |

## Purpose

Lets a person, CI or an agent run a whole job from a terminal: `splintercam run job.json --output out/` writes the NCX and the NC program, prints every diagnostic, and its exit code says whether the run is usable. It holds no logic beyond arguments, printing and the exit code.

## Scope

- In: the `run` command and its options; the text and JSON reports; the exit codes; the `splintercam` console script and `python -m splintercam.apps.cli`.
- Out, handled elsewhere: everything the run does (`job`).
- Later (one line each, no work): the commands `new`, `compute`, `check`, `output`, `sheet`, `info` (feature map, section 1); `--debug` (docs/dev/03); `--threads` (D-055); translated messages; a separate exit code for a programming error (today a traceback and exit 1, AQ-012 item 2); the end-to-end test's read-back and simulated stock (docs/dev/06; with `ncx trace` and `simulation`).
- Non-goals: any check or computation of its own.

## Public interface

```text
splintercam run JOB_FILE --output DIR [--ncx PATH] [--machine PATH] [--strict] [--json]
python -m splintercam.apps.cli run …        # the same
```

```python
def main(argv: Sequence[str] | None = None) -> int: ...   # the exit code; never raises SystemExit
def entry() -> NoReturn: ...                              # sys.exit(main()); the console script's target
```

- `--ncx` and `--machine` go to `run_job` as `ncx_executable` and `machine_file`. `pyproject.toml` gains `[project.scripts] splintercam = "splintercam.apps.cli.__main__:entry"` (no new dependency).

## Requirements

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-CLI-001 | THE cli SHALL provide the command `run` with the job file as its one positional argument and the options `--output` (required), `--ncx`, `--machine`, `--strict` and `--json` (plan 0007, step 7; feature map, section 1). | `tests/apps/cli/unit/test_arguments.py`: `test_the_options_reach_run_job`, `test_the_optional_paths_default_to_none`, `test_run_help_names_every_option` | Reviewed |
| REQ-CLI-002 | THE cli SHALL call `job.run_job` once per `run` and import nothing from SplinterCAM but `job` (docs/dev/03, rule 6). | `tools/arch-check`; `tests/apps/cli/unit/test_arguments.py`: `test_the_options_reach_run_job`, `test_the_cli_imports_only_job_from_splintercam`; `tests/apps/cli/unit/test_exit_code.py`: `test_the_exit_code_of_each_case` (one call per run) | Reviewed |
| REQ-CLI-003 | WHEN `--json` is not given, THE cli SHALL print each diagnostic on stderr as one line `<SEVERITY> <CODE> <location>: <message>` (the location left out when None; line breaks in a message or location written as `\n` and `\r`), in the report's order, and, only when the exit code is 0, the absolute paths of the NCX file and the NC files on stdout, one per line (DEC-CLI-001). | `tests/apps/cli/unit/test_reports.py`: `test_the_golden_case_text_report`, `test_relative_paths_are_printed_absolute`, `test_line_breaks_are_escaped_one_diagnostic_per_line`, `test_backslashes_and_every_other_line_break_are_escaped`, `test_a_failed_run_prints_nothing_on_stdout`, `test_a_warned_run_under_strict_prints_nothing_on_stdout`; `tests/apps/cli/property/test_exit_code_property.py` | Reviewed |
| REQ-CLI-004 | WHEN `--json` is given, THE cli SHALL print on stdout one JSON object, keys sorted, ASCII only, and nothing on stderr: `diagnostics` (objects with `code`, `severity` as `"INFO"`, `"WARNING"` or `"ERROR"`, `message`, `location` or null), `ncx_file` (an absolute path or null), `nc_files` (a list of absolute paths) and `exit_code` (feature map, section 1: text or JSON reports; DEC-CLI-001). | `tests/apps/cli/unit/test_reports.py`: `test_the_golden_case_json_report`, `test_the_json_report_is_ascii_and_keeps_the_text`, `test_a_failed_json_run_names_no_files`; `tests/apps/cli/property/test_exit_code_property.py` | Reviewed |
| REQ-CLI-005 | THE cli SHALL return 2 for a usage error and when the report holds `JOB_FILE_UNREADABLE`, `DXF_UNREADABLE` or `JOB_MACHINE_NOT_FOUND`; otherwise 1 when it holds an ERROR or `CANCELLED`, or with `--strict` a WARNING; otherwise 0. INFO never changes the code (feature map, section 1: 0, 1 for warnings under `--strict`, 2; research 27, Exit codes: 2 for usage errors, unreadable input or a missing machine file; DEC-CLI-002). | `tests/apps/cli/unit/test_exit_code.py`: `test_the_exit_code_of_each_case`; `tests/apps/cli/property/test_exit_code_property.py`: `test_the_exit_code_is_a_function_of_the_report_and_strict`; `tests/apps/cli/unit/test_real_runs.py`: `test_without_ncx_an_error_and_nothing_on_stdout`, `test_without_machine_the_golden_job_is_code_2`, `test_a_missing_job_file_is_code_2` | Reviewed |
| REQ-CLI-006 | THE cli SHALL print nothing but REQ-CLI-003 or 004 for a run; for a usage error argparse's usage message on stderr and code 2; for `--help` the help on stdout and code 0; `main` SHALL return these codes, not raise `SystemExit` (ours). | `tests/apps/cli/unit/test_arguments.py`: `test_a_usage_error_is_code_2_with_the_usage_on_stderr`, `test_help_is_code_0_on_stdout`, `test_python_dash_m_runs_main_and_returns_its_code`, `test_a_clean_run_prints_nothing_but_its_report` | Reviewed |
| REQ-CLI-007 | THE same job run twice into two empty folders SHALL print the same report but for the folder names (D-055). | `tests/apps/cli/unit/test_real_runs.py`: `test_the_same_job_twice_prints_the_same_report_but_for_the_folders` (the real `run_job` on the golden job, a stand-in `--machine`, a missing `--ncx`, so it stops at `JOB_NCX_NOT_FOUND` after the record is built) | Reviewed |
| REQ-CLI-008 | THE end-to-end test SHALL run `python -m splintercam.apps.cli run testdata/zoo/profile-rectangle-fillets/job.json --output <empty temporary folder> --machine <$SPLINTERCAM_NCXCHANGE/machines/heidenhain-itnc530.toml> --strict` as a subprocess and expect exit 0, `RECT_FILLETS.ncx` and `RECT_FILLETS.h` in the folder, and no ERROR or WARNING; without `ncx` on the path or without the variable it SHALL be skipped with a message naming what is missing (plan 0007, step 7 and question 3; docs/dev/06: end-to-end tests in `tests/apps/cli/`; DEC-JOB-004). | end-to-end: `tests/apps/cli/test_run_profile_rectangle_fillets.py`: `test_the_golden_case_runs_clean_through_the_cli` (with and without `--strict`; runs in CI, skipped where `ncx` or `SPLINTERCAM_NCXCHANGE` is missing) | Reviewed |

## Invariants

- The exit code is a function of the report and `--strict` alone (REQ-CLI-005). Property test over generated reports.
- stdout names files only for a run with exit code 0 (REQ-CLI-003, 004). The same property test checks stdout for every generated report.

## Tolerance budget

None.

## Failure modes and diagnostics

None of its own: usage errors are argparse's (exit 2); every diagnostic is `job`'s. A `ValueError` from a producer's bug is not caught: Python prints the traceback and exits 1 (AQ-012 item 2).

## Algorithms and design inputs

No algorithms.

| Element | Public source, or own design with date |
| --- | --- |
| Command, exit codes, text or JSON report | feature map, section 1 (Peter, 2026-10-03); research 27, Exit codes; the line and key forms ours, 2026-10-27 (DEC-CLI-001, 002) |

## Example parts

- The golden case with `ncx` and `--machine`: stderr `INFO JOB_INPUTS …`, `INFO DXF_PART_SIZE …`, `INFO NCX_ROUNDED operation 1 (PROFILE_1): …`; stdout the two paths; exit 0, also with `--strict`.
- The same without `ncx`: stderr `ERROR JOB_NCX_NOT_FOUND …`, nothing on stdout, exit 1. Without `--machine`: `ERROR JOB_MACHINE_NOT_FOUND …`, exit 2.
- `splintercam run missing.json --output out`: `ERROR JOB_FILE_UNREADABLE …`, exit 2.

## Test plan

- Unit (`tests/apps/cli/unit/`): `main` with a fake `run_job` per requirement, tagged with its ID; REQ-CLI-007 with the real one.
- Property: the exit code over generated reports.
- End-to-end (`tests/apps/cli/`): REQ-CLI-008. Golden, differential: none.

## Performance budget

None of its own.

## Size estimate

First count about 60 NLOC of Python (arguments and usage codes 20, the two reports 30, exit code and entry 10); by Peter's rule of 2026-10-25 about 1.5 times that: **about 90 NLOC**, and about 200 lines of tests. Module budget 90 (AQ-013).

## Open questions

Peter answered on 2026-10-27, as recommended: AQ-012 (this SPEC, items 1 to 3 as drafted) and AQ-013 (budget 90). Box 2 choices are in `src/splintercam/apps/cli/DECISIONS.md`. Open since the implementation's reviews (2026-10-30), each with the SPEC as it stands as the safe default:

- AQ-040: a run that `--strict` fails still leaves the compiled NC program in the output folder (`run_job` does not know `--strict`).
- AQ-041: `offset2d`'s replay log after a kernel failure reaches stderr, also with `--json` (DEC-CLI-003, item 4).

## Change log

- 2026-10-27: drafted for plan 0007, step 7, from the feature map, section 1, and research 27, Exit codes; revised after the spec review the same day: exit 2 for unreadable inputs and a missing machine file, 1 for a cancel, paths on stdout only for a usable run, the JSON form fixed, argparse's exits returned, the end-to-end test's machine file from the pinned NCXchange.
- 2026-10-27: Reviewed (Peter, AQ-012 items 1 to 3 as drafted; budget 90, AQ-013). DEC-CLI-001 and 002 Accepted.
- 2026-10-30: implemented (plan 0007, step 7, second half); "Verified by" filled; DEC-CLI-003 (the readings of the wording); AQ-040 and AQ-041 open.

[r27]: ../../../../docs/research/27-machines-and-controllers.md

# SPEC: ncx

<!-- The NCX writer and the call of the pinned ncx binary. Drafted on 2026-10-27 for plan 0007, step 6, cut to the
     slice (D-160): one setup, one tool, RAPID, LINE and planar ARC moves from a Reviewed `cl` record, the tool centre
     at the tip shifted by the point's axial offset, no control compensation, no cycles, no TOLERANCE words. Tool
     changes, the sidecar, machine-limit checks and the round trip of D-063 come with later plans. -->

| | |
| --- | --- |
| Status | Reviewed (2026-10-27, Peter: AQ-010 and AQ-013 in `docs/agents/questions/`, all as recommended). Choices marked "(ours)" are in `src/splintercam/ncx/DECISIONS.md` and stand as the contract; DEC-NCX-008 stays provisional on RR-006 (`SPINDLE=OFF` at the pin) |
| Layer | 4 (see architecture/modules.yaml) |
| Depends on | foundation (`Context`, `Result`, `Diagnostic`, `Severity`, `CANCELLED`, `ToleranceSet`); cl (`ClData`, `make_cl_data`, `MoveKind`; the Reviewed `src/splintercam/cl/SPEC.md`). `model` stays in its `depends_on` line but is not imported in the slice |
| Research | [26][r26], sections The subset plan 0007 uses, Checked against NCXchange, Mapping onto NCX, Number printer, Traps 1–3, 13, 18, Tests 6–8; [27][r27], sections The ncx call in plan 0007, The NCX writer and the `ncx` call, the controller table (Program, Numbers, Comments rows), Traps 3, 6, 11, 15, Tests 5, 6 |
| Decisions | D-021, D-031, D-148 (NCX only, the same for every controller), D-149 (fixed resolution, rounding allowance 0.1·tol), D-080 (canonical NCX, pinned binary), D-154, D-155 (measurement points), D-055, D-028; text in [docs/spike/decisions-snapshot.md](../../../docs/spike/decisions-snapshot.md). Peter: plan 0007 questions 2 and 3, the `OFFSET:LEN` decision of 2026-10-11 (plan 0007, Decisions), AQ-005 item 4 (refuse k ≠ 1) |
| Owner | Peter Burgener |

## Purpose

Turns a checked toolpath record (`cl`) into the canonical NCX text of one program, the same text for every machine (D-148), and runs the pinned `ncx` binary on it as a subprocess: `format --check`, `check --strict` and `compile` for one machine file. It maps `ncx`'s messages back to the operation their line belongs to. Its user in plan 0007 is `job` (step 7), which writes the text to a file, makes the folders and moves the compiled program to the user.

## Scope

- In: the NCX words of research 26's subset (program start and header, `ORIGIN`, `SECTION`, `COMMENT` for note lines, one tool block `TOOL OFFSET:LEN RPM SPINDLE`, `COOLANT`, `RAPID`, `LINE`, `ARC` in the centre form, modal `F`, spindle and coolant off, program end); the number printer at D-149's fixed resolution; the axial offset a added to every Z (D-154); the refusals the slice needs (k ≠ 1, a second tool or speed, characters NCX or Fanuc comments break on); the three `ncx` steps; `ncx`'s messages as diagnostics with their operation.
- Out, handled elsewhere: writing files, making, emptying and listing folders, finding the executable and the machine file (`job`; docs/dev/03, rule 5); the record's rules (`cl`); user values (`model`); dialects, rounding to the machine and every controller rule (NCXchange, D-021, D-148, D-149).
- Later (one line each, no work): `ROUND_LIMIT` per operation once the pin has NCXchange's D363 (DEC-NCX-003), and `compile --strict`; tool and speed changes within a program; the point words of D-155 (R1-11), `OFFSET:RAD`, `COMP` and the register comment (D-024, D-154); `TOLERANCE` words (research 26, trap 11); helices, cycles, dwells, other planes; inch output; several setups; `ncx convert` and `trace` for the round trip of D-063; the sidecar and limit checks (research 27); header comments (feature map, section 8).
- Non-goals: controller knowledge (D-148); rounding to a machine's decimals (D-149); reading the machine file.

## Public interface

Lengths in mm, feeds in mm/min, speeds in 1/min (D-028). All names are proposals (ours). No kernel: the printer is vectorised NumPy over the record's columns (split rule; DEC-NCX-002).

```python
@dataclass(frozen=True, slots=True)
class ProgramInfo:
    name: str                                    # NCX PROGRAM NAME
    number: int                                  # NCX NUMBER

@dataclass(frozen=True, slots=True)
class NcxSection:
    operation: str                               # "operation <index> (<name>)", index from 1 (model REQ-MDL-027)
    first_line: int                              # 1-based line of its SECTION block
    last_line: int                               # 1-based line before the next SECTION or the program end
    round_limit_mm: float                        # the reserve share of its tol (D-149), for ROUND_LIMIT later

@dataclass(frozen=True, slots=True)
class NcxProgram:
    text: str                                    # canonical NCX, ASCII, "\n" line ends, final "\n"
    sections: tuple[NcxSection, ...]             # the operations in program order

class NcxStep(Enum): FORMAT = "format"; CHECK = "check"; COMPILE = "compile"

@dataclass(frozen=True, slots=True)
class NcxCall:                                   # every path absolute (REQ-NCX-018)
    executable: Path                             # the pinned ncx binary
    work_dir: Path                               # an empty folder the CAM made (research 27, traps 3, 4)
    ncx_file: Path                               # the written NcxProgram.text
    machine_file: Path                           # an NCXchange machine TOML (D-053)
    output_dir: Path                             # an empty staging folder `compile` writes into

def write_ncx(cl: ClData, program: ProgramInfo, ctx: Context) -> Result[NcxProgram]: ...
def run_ncx(call: NcxCall, program: NcxProgram, ctx: Context) -> Result[tuple[NcxStep, ...]]: ...
```

- `write_ncx` writes no file and starts no process; it rebuilds the record with `cl.make_cl_data` first, so a record built directly cannot reach the printer unchecked (as `cl` does, REQ-CL-018); a broken one raises `ValueError` (DEC-CL-002). It does not poll `ctx.cancel` (short and vectorised, as DEC-CL-002).
- `run_ncx` writes no file itself; `compile` writes into `call.output_dir`. Its value is the steps that ran; it is `ok` only when every step that ran exited 0 and no ERROR was reported.

## Requirements

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-NCX-001 | THE `write_ncx` function SHALL write one block per line in this order: `FILE=BEGIN NCX=1`; `PROGRAM=BEGIN NAME="<name>" NUMBER=<n>`; `FEED_MODE=PER_MIN COMP=OFF UNITS=MM WORKPLANE=XY CYCLE=OFF`; `ORIGIN=<work offset>`; the operations' blocks (REQ-NCX-002 to 006); `COOLANT=OFF`; `SPINDLE=OFF`; `PROGRAM=END`; `FILE=END` (research 26, Mapping onto NCX: a complete header before motion, VM200; `NUMBER` for Fanuc, CMP300; spindle and coolant off ours, DEC-NCX-008, RR-006). | `tests/ncx/unit/test_write_ncx.py`: `test_research_22_test_1_in_order`, `test_the_work_offset_is_the_origin`, `test_a_record_built_directly_is_checked`; `tests/ncx/property/test_ncx_properties.py`: `test_the_program_invariants` | Reviewed |
| REQ-NCX-002 | Each operation's blocks SHALL begin with `SECTION="<name>"` and one `COMMENT="<line>"` per note line; the first operation's then hold the tool block `TOOL=<n> OFFSET:LEN=<n> RPM=<s> SPINDLE=CW` and `COOLANT=ON`; then its moves (research 26 subset and Checked condition 1: without `OFFSET:LEN` the Fanuc file never applies the tool length; plan 0007, Decisions, 2026-10-11; DEC-CL-005). | `tests/ncx/unit/test_write_ncx.py`: `test_research_22_test_1_in_order`, `test_two_operations_of_one_tool_have_one_tool_block`, `test_the_sections_hold_their_lines_and_allowance`; `tests/ncx/property/test_ncx_properties.py`: `test_the_program_invariants` | Reviewed |
| REQ-NCX-003 | IF an operation's tool number or spindle speed differs from the first operation's, THEN `write_ncx` SHALL report `NCX_TOOL_CHANGE_UNSUPPORTED` (error) naming the operation (ours, DEC-NCX-004: what a second tool block or a speed block without `TOOL` compiles to has not been checked against NCXchange; plan 0007 has one tool). | `tests/ncx/unit/test_refusals.py`: `test_a_second_tool_or_speed_is_refused` | Reviewed |
| REQ-NCX-004 | THE writer SHALL write a RAPID as `RAPID X= Y= Z=`, never with `F` (VM440), and the first move, whose x and y are NaN (REQ-CL-006), as `RAPID Z=` alone (research 27, trap 15: valid NCX). | `tests/ncx/unit/test_write_ncx.py`: `test_rapids_have_no_feed_and_the_first_is_z_alone`; `tests/ncx/property/test_ncx_properties.py`: `test_the_program_invariants` | Reviewed |
| REQ-NCX-005 | THE writer SHALL write a LINE as `LINE X= Y= Z=` and a planar ARC as `ARC=CW` (sweep < 0) or `ARC=CCW` (sweep > 0) with `X= Y= Z= CENTER:X= CENTER:Y=`, a full circle with its end equal to its start (research 26, Mapping, full circle; trap 15). `F=<feed>` SHALL be added where the feed differs from the last `F` written, and on each operation's first LINE or ARC (DEC-NCX-004). | `tests/ncx/unit/test_write_ncx.py`: `test_research_22_test_1_in_order`, `test_a_full_circle_ends_at_its_start` (both directions), `test_two_operations_of_one_tool_have_one_tool_block`; `tests/ncx/property/test_ncx_properties.py`: `test_the_program_invariants` (CW exactly when the sweep is negative) | Reviewed |
| REQ-NCX-006 | THE writer SHALL write X, Y and Z on every move but the first, even where unchanged (DEC-NCX-004). | `tests/ncx/unit/test_write_ncx.py`: `test_research_22_test_1_in_order`, `test_a_full_circle_ends_at_its_start` | Reviewed |
| REQ-NCX-007 | THE writer SHALL write each Z as the record's z plus the operation's axial offset a, and X, Y and the centre unchanged (D-154; research 26, Control compensation and measurement points, CENTER mode). | `tests/ncx/unit/test_write_ncx.py`: `test_the_axial_offset_raises_every_z` (a = 1 and 40); `tests/ncx/property/test_ncx_properties.py`: `test_the_program_invariants` (Z within one step of z + a) | Reviewed |
| REQ-NCX-008 | THE writer SHALL print every length, feed and speed rounded half away from zero to the fixed step 0.000001 (D-149 for lengths; feeds and speeds ours, DEC-NCX-002), decided on the exact value x·10^6, mapping −0 to 0, as the shortest positional digits of the rounded value with at least one digit on each side of the point, no exponent and no plus sign (research 26, Number printer, trap 2; SRC-112). Tool number, `OFFSET:LEN`, `NUMBER` and `ORIGIN` SHALL be written as integers. | `tests/ncx/unit/test_printer.py`: `test_the_printer_examples` (the values above), `test_the_text_has_no_exponent_and_no_plus`; `tests/ncx/property/test_ncx_properties.py`: `test_the_printer_is_exact` (against `fractions.Fraction`, near-ties included) | Reviewed |
| REQ-NCX-009 | THE printed value SHALL lie within half a step (0.0000005 mm) of the exact value it prints, so the writer spends at most 0.0000005·√3 mm per point of the operation's rounding allowance, the reserve share of `ToleranceSet.for_operation(tol)` (D-149, REQ-FND-009: 0.1·tol; at the smallest tol, 2/875 mm, that is 0.38 % of it). `NcxSection.round_limit_mm` SHALL hold the allowance; the text SHALL hold no `ROUND_LIMIT` word in the slice (DEC-NCX-003, AQ-010 item 1). | `tests/ncx/property/test_ncx_properties.py`: `test_the_printer_is_exact` (half a step); `tests/ncx/unit/test_write_ncx.py`: `test_the_sections_hold_their_lines_and_allowance` (0.001 at tol 0.01, no `ROUND_LIMIT`); `tests/ncx/unit/test_refusals.py`: `test_a_tol_without_a_tolerance_set_is_reported` (DEC-NCX-012) | Reviewed |
| REQ-NCX-010 | IF a value to print has a magnitude of 10^9 or more (mm, mm/min or 1/min), THEN `write_ncx` SHALL report `NCX_VALUE_OUT_OF_RANGE` (error) naming the operation and the move (ours, DEC-NCX-002: the exact rounding needs the count below 2^52; the bound is cl's coordinate precondition, geometry2d DEC-G2D-019). | `tests/ncx/unit/test_refusals.py`: `test_a_value_of_1e9_is_refused`, `test_a_feed_of_1e9_is_refused`, `test_a_speed_of_1e9_is_refused`, `test_moves_out_of_range_are_named_by_index`, `test_a_z_past_the_double_range_is_refused` (DEC-NCX-015) | Reviewed |
| REQ-NCX-011 | THE writer SHALL use the canonical NCX layout, so `ncx format --check` passes (D-080; research 26, Number printer). | `tests/ncx/integration/test_real_ncx.py`: `test_ncx_accepts_the_program` (three mill files, one and two operations; skipped without `ncx`, and CI does not build it yet: AQ-025) | Reviewed |
| REQ-NCX-012 | THE `write_ncx` function SHALL give the same text for the same inputs on one platform (D-055 tier 2) and take no machine data, so the text is the same for every machine (D-148; research 26, test 6). | `tests/ncx/unit/test_write_ncx.py`: `test_the_text_is_the_same_twice_and_takes_no_machine` | Reviewed |
| REQ-NCX-013 | IF an operation's point number k is not 1, THEN `write_ncx` SHALL report `NCX_POINT_UNSUPPORTED` (error) naming the operation and k (Peter, AQ-005 item 4: until NCX has point words, R1-11, the written Z would be for point k while the length offset `OFFSET:LEN` selects is not point k's; research 26, trap 3; research 27, trap 11). | `tests/ncx/unit/test_refusals.py`: `test_a_point_other_than_1_is_refused` | Reviewed |
| REQ-NCX-014 | IF the program name is empty, holds a character other than an ASCII letter, digit or underscore, or is a name Windows reserves for a device (CON, PRN, AUX, NUL, COM1 to COM9, LPT1 to LPT9, in any case), THEN `write_ncx` SHALL report `NCX_PROGRAM_NAME_INVALID` (error); IF the number is below 1, THEN `NCX_PROGRAM_NUMBER_INVALID` (error) (research 27, Checked condition 2 and the Program row: names valid as file names; Microsoft, "Naming Files, Paths, and Namespaces"). | `tests/ncx/unit/test_refusals.py`: `test_an_invalid_program_name_is_refused`, `test_names_near_the_device_names_pass`, `test_a_program_number_below_1_is_refused` | Reviewed |
| REQ-NCX-015 | IF a note line holds a character other than printable ASCII, or `(`, `)` or `\`, THEN `write_ncx` SHALL report `NCX_NOTE_CHARACTER` (error) naming the operation, the line and the character (research 27, trap 15: a bracket ends a Fanuc comment early and the rest runs as code; `\` is NCX's escape; `cl` refuses `"` and control characters, REQ-CL-017; DEC-NCX-009). | `tests/ncx/unit/test_refusals.py`: `test_a_note_character_is_refused` | Reviewed |
| REQ-NCX-016 | IF an ARC with \|sweep\| below 2π prints with its end equal to its start, or its centre prints equal to its start or end, THEN `write_ncx` SHALL report `NCX_ARC_PRINTS_DEGENERATE` (error) naming the operation and the move (DEC-CL-006: the guarantee on printed values is the writer's; a control reads end = start as a full circle). | `tests/ncx/unit/test_refusals.py`: `test_an_arc_that_prints_degenerate_is_refused` (the arc above) | Reviewed |
| REQ-NCX-017 | THE `write_ncx` function SHALL report every error of REQ-NCX-003, 010 and 013 to 016, in this order: program name, number, then each operation in order with its errors by requirement ID and, within one, by move index; and SHALL return no program when there is one (ours, D-055). | `tests/ncx/unit/test_refusals.py`: `test_every_error_is_reported_in_order`, `test_moves_out_of_range_are_named_by_index`, `test_a_tol_without_a_tolerance_set_is_reported` | Reviewed |
| REQ-NCX-018 | THE `run_ncx` function SHALL run, with `call.work_dir` as working directory, no shell and every path absolute: `ncx format --check <ncx_file>`; `ncx check <ncx_file> --machine <machine_file> --strict`; `ncx compile <ncx_file> --machine <machine_file> --output <output_dir>` (research 27, The ncx call in plan 0007; trap 3). It SHALL read stdout and stderr to their end while the step runs, decoded as UTF-8 with replacement (DEC-NCX-007). | `tests/ncx/integration/test_run_ncx.py`: `test_the_three_steps_run_with_their_arguments`, `test_a_long_output_does_not_block` (10^5 lines on each pipe), `test_a_relative_path_is_refused` (DEC-NCX-015) | Reviewed |
| REQ-NCX-019 | WHEN `format --check` or `check` exits other than 0 or reports an ERROR, THE `run_ncx` function SHALL not run `compile` (DEC-NCX-005). | `tests/ncx/integration/test_run_ncx.py`: `test_check_failing_stops_before_compile`, `test_an_error_with_exit_0_stops_before_compile`, `test_a_format_difference_still_runs_check`; `tests/ncx/property/test_ncx_properties.py`: `test_ok_only_when_every_step_passed` | Reviewed |
| REQ-NCX-020 | THE `run_ncx` function SHALL read each stderr line `<file>(<line>): <SEVERITY> <CODE>: <message>`, the line number taken as the last `(digits):` before the severity, as a `Diagnostic` with `ncx`'s code, severity and message; any other non-empty line as `NCX_OUTPUT_UNREAD` (warning) holding it verbatim (research 27, Exit codes; never swallow errors). | `tests/ncx/unit/test_messages.py`: `test_the_three_severities_are_read`, `test_other_lines_are_kept_verbatim`, `test_windows_line_ends_are_read`, `test_an_unread_compile_line_fails_as_strict` (DEC-NCX-014) | Reviewed |
| REQ-NCX-021 | THE location SHALL be the `NcxSection.operation` whose lines hold the message's line when its file is `call.ncx_file`, `program` for a line of that file outside every section, and `ncx <step>` for any other file, whose name then goes into the message (feature map, section 8; research 27: `SECTION` marks operations). | `tests/ncx/unit/test_messages.py`: `test_the_line_gives_the_operation` (line 1, first and last lines), `test_another_file_is_named_and_not_mapped` (`CFG002`), `test_the_ncx_file_is_found_by_its_resolved_path` | Reviewed |
| REQ-NCX-022 | THE `run_ncx` function SHALL report the `CMP020`s of `compile` as one INFO per location, `NCX_ROUNDED`, with their number, and any other WARNING of `compile` as it is plus `NCX_STRICT_FAILED` (error) naming the step (D-149: rounding to the machine is normal; research 27: the slice accepts `CMP020` and nothing else; DEC-NCX-006). | `tests/ncx/unit/test_messages.py`: `test_compile_counts_cmp020_per_location`, `test_another_compile_warning_fails_as_strict`, `test_a_cmp020_error_is_not_counted`, `test_cmp020_outside_compile_is_kept`; `tests/ncx/integration/test_run_ncx.py`: `test_a_long_output_does_not_block` | Reviewed |
| REQ-NCX-023 | IF a step exits with 1, THEN `run_ncx` SHALL report `NCX_STEP_FAILED` (error) naming the step, with the step's stdout in the message for `format --check` (its difference); IF it exits with another code other than 0 or cannot be started, THEN `NCX_CALL_FAILED` (error) naming the step and the code or OS error, and run no further step (research 27, Exit codes: 1 an ERROR, a WARNING under `--strict` or a format difference; 2 usage or unreadable input). | `tests/ncx/integration/test_run_ncx.py`: `test_check_failing_stops_before_compile`, `test_a_format_difference_still_runs_check`, `test_exit_1_is_a_failed_step` (a WARNING only; silent), `test_another_exit_code_stops_the_call` (2, 3), `test_a_missing_executable_fails_the_call` | Reviewed |
| REQ-NCX-024 | WHEN `ctx.cancel` is set at entry or while a step runs, THE `run_ncx` function SHALL stop the process, run no further step and return `CANCELLED` after the diagnostics so far (REQ-FND-013; DEC-NCX-007). | `tests/ncx/integration/test_run_ncx.py`: `test_cancelled_at_entry_runs_nothing`, `test_cancelled_while_a_step_runs`, `test_cancelled_during_the_last_step` | Reviewed |
| REQ-NCX-025 | THE `run_ncx` function SHALL return its diagnostics in step order and, within a step, in the order `ncx` printed them, `NCX_ROUNDED` at the place of the first `CMP020` of its location (ours, D-055). | `tests/ncx/unit/test_messages.py`: `test_compile_counts_cmp020_per_location`, `test_messages_keep_the_order_printed`; `tests/ncx/integration/test_run_ncx.py`: `test_cancelled_while_a_step_runs` | Reviewed |

## Invariants

- A program from `write_ncx` begins with `FILE=BEGIN`, ends with `FILE=END`, has one `SECTION` per operation in order, one `TOOL` block before the first move, no motion before `UNITS`, no `F` on a RAPID, and only ASCII (REQ-NCX-001 to 008, 015). Property test over generated valid `cl` records.
- Every printed value lies within half a step of the exact value printed (REQ-NCX-008, 009). Property test.
- `run_ncx` is `ok` only when every step that ran exited 0, `compile` ran, and no ERROR came (REQ-NCX-019 to 024). Property test: a fake `ncx` driven by generated exit codes and stderr lines per step.

## Tolerance budget

The writer spends at most 0.0000005·√3 mm per point of the operation's rounding allowance (REQ-NCX-009); the rest is NCXchange's for rounding to the machine (D-149). At the f74559c pin nothing checks that rounding against the allowance (NCXchange's D363 is not implemented; AQ-010 item 3). No other tolerance is read; every other comparison is exact.

## Failure modes and diagnostics

| Situation | Result | Diagnostic |
| --- | --- | --- |
| A second tool or speed; point k ≠ 1 | no program | `NCX_TOOL_CHANGE_UNSUPPORTED`, `NCX_POINT_UNSUPPORTED` (error) |
| Name, number, note character invalid | no program | `NCX_PROGRAM_NAME_INVALID`, `NCX_PROGRAM_NUMBER_INVALID`, `NCX_NOTE_CHARACTER` (error) |
| A value of 10^9 or more; an arc that prints degenerate | no program | `NCX_VALUE_OUT_OF_RANGE`, `NCX_ARC_PRINTS_DEGENERATE` (error) |
| `ncx` prints a message | as `ncx` says; `CMP020` counted as INFO | `ncx`'s code; `NCX_ROUNDED` (info) |
| A `compile` WARNING other than `CMP020` | not `ok` | `NCX_STRICT_FAILED` (error) |
| A stderr line not in the form | kept verbatim | `NCX_OUTPUT_UNREAD` (warning) |
| Exit 1; another code or no executable | later steps not run | `NCX_STEP_FAILED`; `NCX_CALL_FAILED` (error) |
| Cancelled | process stopped | `CANCELLED` (warning) |

## Algorithms and design inputs

| Element | Public source, or own design with date |
| --- | --- |
| Words, order, centre-form arcs, `OFFSET:LEN` with `TOOL` | research 26, Mapping onto NCX and Checked against NCXchange (SRC-112, f74559c) |
| Printer: half away from zero to 1e-6, shortest positional digits | research 26, Number printer (D-149); the exact product x·10^6 by Dekker's error-free product (T. J. Dekker, "A floating-point technique for extending the available precision", Numer. Math. 18, 1971), integer steps in NumPy: ours, 2026-10-27 (DEC-NCX-002) |
| `ncx` steps, exit codes, stderr form, working folder | research 27, The ncx call in plan 0007 and The NCX writer and the `ncx` call (SRC-112) |
| Messages to operations by `SECTION` lines | research 27; feature map, section 8 (Peter, 2026-10-03) |

## Example parts

- Research 22 test 1's record (`src/splintercam/cl/SPEC.md`, Example parts), tol 0.01, T1 at 8000 1/min, cut 1200, plunge 300, work offset 1, program `RECT_FILLETS` 1001: `SECTION="PROFILE_1"`, `TOOL=1 OFFSET:LEN=1 RPM=8000.0 SPINDLE=CW`, `COOLANT=ON`, `RAPID Z=5.0`, three passes with `F=300.0` on each approach and `F=1200.0` on each first cut move, four `ARC=CW` per pass about (5, 5), (95, 5), (95, 55), (5, 55); z −10/3 prints `-3.333333`. With the real `ncx` on `heidenhain-itnc530.toml`: `format --check` and `check --strict` exit 0, `compile` writes `RECT_FILLETS.h` with `NCX_ROUNDED` only.
- The same with point 2: `NCX_POINT_UNSUPPORTED`. With point 1 at a = 40: every Z printed 40 higher.
- Program name `RECT FILLETS` or `con`: `NCX_PROGRAM_NAME_INVALID`. A note line `Spannung (oben)`: `NCX_NOTE_CHARACTER`.
- A machine file with an unknown key: `CFG002` at `ncx check`, `NCX_STEP_FAILED`, no `compile`.

## Test plan

- Unit (`tests/ncx/unit/`): per requirement, tagged with its ID; the printer's values; the stderr parser; the example parts.
- Property (`tests/ncx/property/`): generated valid `cl` records (the generator of `tests/cl/property/`): the invariants; printed values against exact rational arithmetic, near-ties included.
- Integration (`tests/ncx/integration/`): a fake `ncx` (a Python script the test writes) for REQ-NCX-018 to 025. The real pinned `ncx`, when on the path, on research 22 test 1's program, and on a two-operation program of one tool, against `heidenhain-itnc530.toml`, `fanuc-mill-30i.toml` and `siemens-840dsl-mill.toml`: `format --check` and `check --strict` exit 0, `compile` gives only `CMP020` (research 26, test 7; research 27, test 3 in the slice's form); The machine files come from the pinned NCXchange checkout named by the environment variable `SPLINTERCAM_NCXCHANGE` (DEC-JOB-004); without `ncx` on the path or without the variable these tests are skipped with a visible message (plan 0007, question 3). CI provides both (the job that builds the pinned `ncx`), so there they never skip: they are the only check that the written words are valid NCX (`.claude/rules/ncx.md`).
- Golden: the NCX of `testdata/zoo/profile-rectangle-fillets` (`src/splintercam/job/SPEC.md`), per platform only (D-055). Differential: none.

## Performance budget

`write_ncx` on 100 000 moves under 1 s on the reference machine (ours; plan 0007 has about 50). Not tested in this slice.

## Size estimate

First count about 270 NLOC of Python (types 25; blocks and sections 45; moves and modal F 35; exact printer 35; the refusals of REQ-NCX-003, 010, 013 to 017 30; the subprocess with drained pipes and cancel 50; parser, locations and `CMP020` counting 40; word constants 10); by Peter's rule of 2026-10-25 about 1.5 times that: **about 400 NLOC**, and about 550 lines of tests (the plan's 250 by the rule is 375). The plan's 200 by the rule is 300; the draft is 33 % over, within the 50 % stop, for the exact printer and the subprocess failure paths the reviews asked for. Module budget 400 (AQ-013).

## Open questions

None open for Peter. He answered `docs/agents/questions/AQ-010.md` on 2026-10-27, all as recommended: (1) no `ROUND_LIMIT` at the f74559c pin; (2) `COOLANT=OFF` and `SPINDLE=OFF` before the program end; (3) (a): the machine's rounding against the allowance is not checked until D363, tol 0.01 in the golden case and the dry run; (4) one tool and one speed per program; (5) `OFFSET:LEN=<tool number>` unchanged in the slice; (6) the two exceptions to docs/dev/03, rule 5; (7) the program name rules. AQ-013: budget 400. Open, box 3: `docs/research/requests/RR-006.md` (the canonical layout, `ROUND_LIMIT` and `SPINDLE=OFF` at the pin); until it is answered the real-`ncx` integration test is the oracle for REQ-NCX-001 and 011. Box 2 choices are in `src/splintercam/ncx/DECISIONS.md`.

## Change log

- 2026-10-27: drafted for plan 0007, step 6, from research 26 and 27, D-149, D-154, AQ-005 and the feature map, section 8; revised after one spec review and one CNC review the same day: exact half-away-from-zero printing, one tool per program, spindle and coolant off at the end, note characters, the machine file's lines not mapped to operations, any failing step an error, `CMP020` counted, other `compile` warnings as under `--strict`, compile into a staging folder.
- 2026-10-27: Reviewed (Peter, AQ-010 as recommended, 3 (a); budget 400, AQ-013). DEC-NCX-001 to 007, 009 and 010 Accepted; DEC-NCX-008 provisional on RR-006.
- 2026-10-27: implemented (REQ-NCX-001 to 025, plan 0007 step 6). "Verified by" names the tests; REQ-NCX-011's real-`ncx` test is skipped until CI builds `ncx` (AQ-025). Readings recorded as DEC-NCX-011 to 015 (ours); SPEC wording for DEC-NCX-011 and 012 asked in `docs/agents/questions/AQ-027.md`.

[r26]: ../../../docs/research/26-toolpath-record.md
[r27]: ../../../docs/research/27-machines-and-controllers.md

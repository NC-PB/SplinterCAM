# Decisions: ncx

<!-- The permanent record of why this module is built the way it is. Rules: docs/dev/05, "Module decision records".
     - Write the entry in the same commit as the change that makes the decision, not at the end and not on request.
     - Newest last. IDs DEC-NCX-NNN are never reused.
     - After merge, only the Status line of an entry changes. A changed decision is a new entry that supersedes the old one.
     - Code that follows a decision a reader would not expect cites its ID in a comment. -->

## DEC-NCX-001: The writer returns text; `job` writes the file and owns the folders

- Date: 2026-10-27; decided by: ours (SPEC draft, plan 0007 step 6)
- Status: Provisional (SPEC Draft, AQ-010 item 6)
- Decision: `write_ncx` is a pure function from the record to the NCX text and its sections. `run_ncx` starts the `ncx` process on absolute paths the caller gives; it writes no file itself, but `ncx compile` writes the controller files into the staging folder the caller made. `job` writes the NCX file, makes the working and staging folders, and moves the compiled files to the user only after a clean run.
- Why: docs/dev/03, rule 5: files are read and written only in `io`, `job` and `apps`; running the pinned binary is `ncx`'s by `architecture/modules.yaml`. The files `compile` writes are the one exception, on `job`'s folder; AQ-010 item 6 asks Peter to confirm it. A pure writer is testable without a file system.
- Rejected: `write_ncx` writing the file; the text on `ncx`'s stdin (research 27 names file arguments only).
- Where: REQ-NCX-001 to 018; `src/splintercam/job/SPEC.md`, REQ-JOB-016 to 019.

## DEC-NCX-002: The number printer: exact half away from zero, as integer steps in NumPy

- Date: 2026-10-27; decided by: ours (revised after the spec review the same day)
- Status: Provisional (SPEC Draft, AQ-010)
- Decision: each column is turned into int64 counts of the step 10^-6 by rounding the exact product x·10^6 half away from zero: Dekker's error-free product gives x·10^6 as p + e exactly (p the rounded product, e its error, both doubles; 10^6 is exact), and the count is decided from floor(p), the exact fraction p − floor(p) and e, ties going away from zero. The text is the count's integer and fractional digits, built with NumPy string operations, trailing zeros trimmed to one decimal; −0 is the count 0. Values of 10^9 or more are refused (REQ-NCX-010), so every count lies below 2^52, where floor, the fraction and the cast to int64 are exact. Feeds and speeds use the same step.
- Why: the split rule puts loops over points into NumPy or a kernel, and research 26's `format_float_positional` is a per-value Python call. `floor(|x|·10^6 + 0.5)` rounds twice: the double nearest 5·10^-7 printed `0.000001` instead of `0.0` (spec review). With the exact product the printed decimal is exactly the rounded value, research 26's rule, and only IEEE addition, subtraction, multiplication and floor decide, the same on every platform (D-055). D-149 fixes the resolution for lengths and angles only; feeds and speeds at the same step keep one printer, far finer than any machine's decimals (ours).
- Rejected: `format_float_positional` per value (a Python loop over every coordinate); Python's `decimal` (a loop too); `floor(x·10^6 + 0.5)` (double rounding above); `np.round` (half to even).
- Where: REQ-NCX-008 to 010.

## DEC-NCX-003: No `ROUND_LIMIT` word in the slice

- Date: 2026-10-27; decided by: ours, provisional on Peter's answer (AQ-010 item 1)
- Status: Provisional
- Decision: the writer computes every operation's rounding allowance, the reserve share of its tolerance set (0.1·tol, D-149, REQ-FND-009), and holds it in `NcxSection.round_limit_mm`, but writes no `ROUND_LIMIT`. Writing it comes with the pin that includes NCXchange's D363 (Later).
- Why: Peter answered D363 on 2026-10-02 (the CAM writes `ROUND_LIMIT` per operation; `src/splintercam/foundation/SPEC.md`, Tolerance budget), but research 27 records that f74559c has not implemented D363 (Checked condition 3), and an unknown word most likely fails `check` (not tried: no `ncx` in this run; RR-006 asks). The writer has no input that says what the pin is, so the switch is a code change with the pin, not a condition.
- Rejected: writing it now; the allowance in a `COMMENT` (NCXchange cannot read it).
- Where: REQ-NCX-009.

## DEC-NCX-004: One tool and one speed per program; every axis word; `F` restated per operation

- Date: 2026-10-27; decided by: ours (revised after the CNC review the same day)
- Status: Provisional (SPEC Draft, AQ-010 item 4)
- Decision: the program has one tool block, in the first operation; an operation with another tool or speed is refused. Every move but the first carries X, Y and Z. `F` is written where the feed changes and on each operation's first feed move.
- Why: what a second tool block from the clearance height, or a speed block without `TOOL`, compiles to on the three mill files has not been checked (research 26 notes only that Heidenhain takes the speed from `TOOL CALL`); plan 0007 has one tool. Full axis words and `F` per operation let a section be read alone (feature map, section 8: NC code for one operation) and change nothing on the machine, as NCX is modal.
- Rejected: a tool block per operation and a speed-only block (unchecked output); leaving unchanged axes out.
- Where: REQ-NCX-002, 003, 005, 006.

## DEC-NCX-005: `compile` does not run after a failing `format --check` or `check`

- Date: 2026-10-27; decided by: ours
- Status: Provisional (SPEC Draft, AQ-010)
- Decision: `format --check` and `check` both run unless the call fails (REQ-NCX-023) or is cancelled; `compile` runs only when both exited 0 without an ERROR.
- Why: a program that fails `check --strict` is not right for the machine, and an NC program compiled anyway could be taken for a good one. `check` after a format difference still shows the machine's view of the words.
- Rejected: always all three; stopping after `format --check`.
- Where: REQ-NCX-019.

## DEC-NCX-006: `CMP020` counted as INFO; other `compile` warnings fail as under `--strict`

- Date: 2026-10-27; decided by: ours, provisional on Peter's answer (AQ-010 item 3)
- Status: Provisional
- Decision: `compile` runs without `--strict` (research 27). Its `CMP020`s become one INFO, `NCX_ROUNDED`, per location with their count; any other WARNING keeps its severity and adds `NCX_STRICT_FAILED` (error).
- Why: D-149 makes rounding to the machine's decimals normal and silent (NCXchange D363 retires `CMP020`), and research 27 accepts `CMP020` and nothing else. One message per coordinate would bury real ones, and would be a Python loop over points. Without the added error, a `CMP501` or `CMP022` from `compile` would pass a run that `--strict` would fail (spec and CNC reviews).
- Rejected: `CMP020` as WARNING (every run fails the CLI's `--strict`); dropping it (never swallow).
- Where: REQ-NCX-022.

## DEC-NCX-007: The subprocess: argument list, drained pipes, no timeout, cancel by polling

- Date: 2026-10-27; decided by: ours, the clock exception provisional on AQ-010 item 6
- Status: Provisional
- Decision: each step is started with an argument list, no shell, in `call.work_dir`, with the parent's environment. stdout and stderr are read to their end while the process runs (reader threads), decoded as UTF-8 with replacement; stderr is parsed with one compiled regular expression over the whole text; stdout goes to `ctx.logger` at debug level, and for `format --check` into `NCX_STEP_FAILED`'s message. There is no timeout; the wait polls `ctx.cancel` at a fixed interval, a named constant citing this entry, and stops the process when it is set.
- Why: a full pipe blocks the child (one `CMP020` per coordinate is a lot of text). No shell means no quoting. Research 27 gives no run time, and a made-up timeout could kill a slow, correct run; cancellation covers a hung one. The poll interval reads the clock, which docs/dev/03, rule 5 keeps out of layers below 6; waiting on a subprocess cannot avoid it, so AQ-010 item 6 asks Peter to confirm the exception.
- Rejected: `shell=True`; `wait()` with unread pipes; a fixed timeout.
- Where: REQ-NCX-018, 020, 023, 024.

## DEC-NCX-008: `COOLANT=OFF` and `SPINDLE=OFF` before the program end

- Date: 2026-10-27; decided by: ours (CNC review), provisional on AQ-010 item 2 and RR-006
- Status: Provisional
- Decision: after the last operation's last move (a RAPID at or above the clearance height, REQ-CL-012) the writer writes `COOLANT=OFF` and `SPINDLE=OFF`, then `PROGRAM=END`.
- Why: research 26's mapping has no spindle or coolant off, and nothing in the research says what `PROGRAM=END` compiles to or whether the program end stops the spindle on the iTNC 530; relying on it would be guessing controller behaviour. Stopping both explicitly is the state an operator expects when the program ends 5 mm above the part. `COOLANT=OFF` follows the machine file's `[coolant]` ON/OFF codes (research 27); `SPINDLE=OFF` is not confirmed as an NCX value (RR-006): the real-`ncx` integration test checks it, and if it fails the form comes from RR-006's answer.
- Rejected: no stop (the control's end decides; unverified).
- Where: REQ-NCX-001.

## DEC-NCX-009: Note lines in printable ASCII without brackets or backslash

- Date: 2026-10-27; decided by: ours (spec review), from research 27, trap 15
- Status: Provisional (SPEC Draft, AQ-010)
- Decision: the writer refuses a note line with a character outside printable ASCII, or with `(`, `)` or `\`. The text is ASCII.
- Why: research 27, trap 15: a bracket inside a Fanuc comment ends it early and the rest of the line runs as code, with no message from `ncx`; the CAM refuses brackets until NCXchange escapes them (R1-14). `\` is NCX's escape character. `cl` already refuses `"` and control characters (REQ-CL-017) but lets umlauts through (DEC-CL-005); the slice's note is empty (AQ-008 (b)), so ASCII only costs nothing now and keeps the NCX file's encoding out of question.
- Rejected: transliterating in the writer (NCXchange's job in comments, research 27); escaping `\` (no note needs it).
- Where: REQ-NCX-015.

## DEC-NCX-010: The operation's name only in `SECTION`, not also as a `COMMENT`

- Date: 2026-10-27; decided by: ours (left to `ncx` by `src/splintercam/cl/SPEC.md`, Scope)
- Status: Provisional (SPEC Draft, AQ-010)
- Decision: the name is written once, in `SECTION="<name>"`; note lines follow as `COMMENT`.
- Why: the three compilers write `SECTION` as a comment line on every control (research 27, trap 15: Heidenhain `* - …`, Siemens `; …`, Fanuc `( … )`), so the operator sees the name; a second copy adds a line and nothing else.
- Rejected: `COMMENT="<name>"` after `SECTION`.
- Where: REQ-NCX-002.

# Decisions: apps/cli

<!-- The permanent record of why this module is built the way it is. Rules: docs/dev/05, "Module decision records".
     - Write the entry in the same commit as the change that makes the decision, not at the end and not on request.
     - Newest last. IDs DEC-CLI-NNN are never reused.
     - After merge, only the Status line of an entry changes. A changed decision is a new entry that supersedes the old one.
     - Code that follows a decision a reader would not expect cites its ID in a comment. -->

## DEC-CLI-001: Diagnostics on stderr, paths on stdout; one JSON object with `--json`

- Date: 2026-10-27; decided by: ours (SPEC draft, plan 0007 step 7)
- Status: Accepted 2026-10-27 (SPEC Reviewed, AQ-012)
- Decision: the text report prints one line per diagnostic on stderr, `<SEVERITY> <CODE> <location>: <message>` with line breaks escaped, and, only for exit code 0, the written files' absolute paths on stdout; `--json` prints one ASCII object with sorted keys (`diagnostics`, `ncx_file`, `nc_files`, `exit_code`) on stdout and nothing on stderr.
- Why: a script can read the paths from stdout while a person reads the messages, as `ncx` prints its diagnostics on stderr one per line (research 27). Paths only for a usable run, so a script never picks up the NCX of a failed run as its result (spec review). An escaped line break keeps one diagnostic per line (`NCX_OUTPUT_UNREAD` holds `ncx`'s text verbatim). Sorted keys keep the JSON bytes stable (D-055).
- Rejected: everything on stdout (a script must filter); `ncx`'s `file(line): SEVERITY CODE: message` form (our locations are operations, not lines).
- Where: REQ-CLI-003, 004.

## DEC-CLI-002: Exit code 2 for an unreadable job file

- Date: 2026-10-27; decided by: ours
- Status: Accepted 2026-10-27 (SPEC Reviewed, AQ-012)
- Decision: the exit code is 2 for usage errors and when the report holds `JOB_FILE_UNREADABLE`, `DXF_UNREADABLE` or `JOB_MACHINE_NOT_FOUND`; 1 for any other error, for `CANCELLED`, and for a warning under `--strict`; 0 otherwise.
- Why: the feature map gives 0, 1 and 2; research 27 records `ncx`'s 2 for usage errors, unreadable input or a missing machine file, and the same meaning makes the two tools read alike in CI. A cancelled run has no program, so it is not 0 (spec review).
- Rejected: 1 for every error (a CI script cannot tell a wrong path from a wrong part).
- Where: REQ-CLI-005.

## DEC-CLI-003: Readings of the Reviewed wording (escaping, the codes of 2, the help, logging, encoding)

- Date: 2026-10-30; decided by: ours (implementation, after the spec and cnc reviews); item 4 Peter (AQ-041 (a))
- Status: Accepted 2026-10-30 (item 4: AQ-041 (a), REQ-CLI-004 and 006 amended)
- Decision:
  1. The text report escapes the backslash first (`\\`), then `\n` and `\r` as REQ-CLI-003 says, and every other character that breaks or hides a line as `\xNN` or `\uNNNN`: C0 controls but tab, DEL, C1 controls (with NEL) and U+2028, U+2029. Text and tab stay as they are.
  2. `JOB_FILE_UNREADABLE`, `DXF_UNREADABLE` and `JOB_MACHINE_NOT_FOUND` give 2 only as ERRORs. Today they are always ERRORs (`job`, `io`); the reading keeps "INFO never changes the code" of REQ-CLI-005 true whatever a producer does.
  3. The help of `run` says what the exit codes mean and, after 1 or 2, to take no file from the output folder (the safe default of AQ-040).
  4. Log records of the producers (`offset2d`'s replay input after a kernel failure) reach stderr through Python's last-resort handler, as before; the CLI sets no logging (AQ-041 (a)).
  5. stdout keeps the platform's encoding. A path the console's code page cannot encode (a Windows pipe in cp1252) ends in a traceback and exit 1, after the files are written; `--json` is pure ASCII and is the form for scripts.
- Why: (1) without the backslash escaped, `C:\new` reads as a line break, and `str.splitlines` and terminals break at more than `\n` and `\r` (spec review, cnc review L1); a diagnostic holding `ncx`'s text verbatim must stay one line. (2) the requirement's two sentences agree only under this reading (spec review). (3) a `--strict` run that fails can leave the NC program in the folder (cnc review H1, AQ-040). (4) the replay input is what a kernel bug report needs; muting it loses it (AQ-041). (5) a failing exit code is the safe side, and replacing characters would print a path that does not exist.
- Rejected: (1) only `\n` and `\r` (ambiguous, breaks on other separators); (2) the code alone (an INFO of that code would change the exit code); (4) a `NullHandler` now (loses the replay input; AQ-041 (b)); (5) `errors="backslashreplace"` on stdout (prints a wrong path with exit 0).
- Where: REQ-CLI-003, 004, 005, 006; `src/splintercam/apps/cli/_cli.py`.

## DEC-CLI-004: The files left after a failed run: `files_left` and one `FILES_LEFT` line

- Date: 2026-10-30; decided by: Peter (AQ-040 (b), (c)); the form ours
- Status: Accepted 2026-10-30 (AQ-040)
- Decision: `--strict` is passed to `run_job` as `strict`, so a warning also withholds the NC program (DEC-JOB-016). When the exit code is not 0, the report's files (`ncx_file`, then `nc_files`, absolute) are the files left: with `--json` the key `files_left`, empty otherwise; in the text report one closing stderr line in the diagnostics' form, `INFO FILES_LEFT: left on disk, not for the machine: <paths, ", "-separated>`, escaped as a message (DEC-CLI-003), and no line when there are none. It is a line of the CLI, not a diagnostic of the report, so the JSON's `diagnostics` stay `job`'s. The files left are those the report names; other names in a diagnostic (a file `JOB_OUTPUT_UNWRITABLE` could not remove, the temporary folder of `JOB_WORK_DIR_LEFT`) stay in that diagnostic's message.
- Why: a failed run can leave the NCX file (written before `ncx` runs) and, from a report that names NC files with a non-zero exit, those too; a script reading only stdout or `ncx_file` saw nothing (cnc review H1, M1). The diagnostics' line form keeps "one line, `<SEVERITY> <CODE> …`" true for every stderr line a script parses.
- Rejected: listing the output folder (the CLI would read the file system and could name files the run did not write); `FILES_LEFT` as a JSON diagnostic (it would mix the CLI's text into `job`'s report); one line per file (the SPEC asks for one closing line).
- Where: REQ-CLI-001, 003, 004, 006; `_print_report` in `src/splintercam/apps/cli/_cli.py`.

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

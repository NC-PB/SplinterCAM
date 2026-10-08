# Decisions: foundation

<!-- The permanent record of why this module is built as it is. Rules: docs/dev/05, "Module decision records".
     Write each entry in the same commit as the change that makes the decision. After merge only the Status
     line changes; a changed decision is a new entry that supersedes the old one. IDs are never reused. -->

## DEC-FND-001: `CANCELLED` is a shared `Diagnostic` constant

- Date: 2026-10-08; decided by: ours (plan 0005, step 2), within Peter's DEC-OFF-002
- Status: Active
- Decision: foundation exports `CANCELLED`, a ready-made `Diagnostic` (code `CANCELLED`, warning, a fixed message), from `_result.py` and `__all__`. A module adds a location with `dataclasses.replace`.
- Why: foundation has no registry of codes, and a registry would be a new mechanism for one code. A frozen dataclass is safe to share, and one constant fixes code, severity and message for every module.
- Rejected: a bare string constant for the code (each module would repeat severity and message, and could pick another); a registry of codes (more than one code needs).
- Where: REQ-FND-013; `src/splintercam/foundation/_result.py`.

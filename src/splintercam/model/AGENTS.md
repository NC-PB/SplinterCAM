# AGENTS.md: model

Layer 2. The job's data in memory for plan 0007 (one flat end mill, one box stock, one setup, the
operations' parameter values as declarations), checked once by `check_job`. Contract: `./SPEC.md`.
Why it is built this way: `./DECISIONS.md` (read it before changing behaviour). Public API:
`./__init__.py`. No C++ part, no file I/O. Depends on: foundation.

## Commands

- `tools/test-one model`

## Invariants that must never break

- REQ-MDL-025, 029, DEC-MDL-003: the types accept any value; only `check_job` checks, and every
  wrong user value is a diagnostic, never an exception. A field of the wrong type skips its other
  checks, so no message compares against NaN or a str.
- REQ-MDL-026: diagnostics come in the order they are appended by `_Checker` (tools, stock, setup,
  operations; type errors first within each). Add a check in its requirement's place, not at the end.
- REQ-MDL-024: the returned job equals the input except for the completed parameters, so checking
  it again returns it unchanged (property test).
- DEC-MDL-001: model knows no strategy; strategies declare their parameters with
  `ParameterDeclaration`, and an invalid declaration raises `ValueError`.

## Known pitfalls

- `bool` is an `int` in Python: `True` passes `isinstance(x, int)` and equals 1 as a dict key.
  Use `_is_int` / `_as_float`, never a bare `isinstance(x, int)` (REQ-MDL-029).
- `ruff format` on a directory also formats the Python blocks inside Markdown files such as
  `SPEC.md`; pass the `.py` files only.
- An operation naming a tool whose number is invalid still gets `OP_TOOL_UNKNOWN`; tests that break
  a tool's number expect it.

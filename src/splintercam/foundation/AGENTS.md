# AGENTS.md: foundation

Layer 0. Implements docs/research/01. Contract: `./SPEC.md`. Public API: `./__init__.py`. No C++ part. Depends on nothing but the standard library and NumPy.

## Commands

- `tools/test-one foundation`

## Invariants that must never break

- REQ-FND-003: `nearly_equal(a, b, tol)` is true exactly when |a − b| ≤ tol; false for NaN.
- REQ-FND-004: `Result.ok` only with a value and no `ERROR` diagnostic.
- REQ-FND-005: tolerances, cancellation, progress, logging, debug output and the seed come only from the `Context`.
- REQ-FND-006: a cancelled token sets its one-element flag array to 1.

## Local rules

- No algorithms and no I/O here. If a helper needs geometry, it belongs in `geometry2d` or `geometry3d`.
- Every value type is a frozen dataclass with slots; only `CancellationToken` has state.
- Every other module imports these types; keep the API small and stable, and change it only through the SPEC.

## Known pitfalls

- General engineering practice: one internal unit, NaN or `None` for "no value", never a magic number.

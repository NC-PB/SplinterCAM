# SPEC: foundation

<!-- The shared vocabulary of every module. Drafted on 2026-09-24 from RESEARCH 01 and 18 (general engineering). -->

| | |
| --- | --- |
| Status | Draft. REQ-FND-001 to REQ-FND-006 are released for the stack test app ([plan 0001](../../../docs/plans/active/0001-stack-test-app.md)) |
| Layer | 0 |
| Depends on | Python standard library and NumPy only |
| Research | [01](../../../docs/research/01-foundations.md), [18](../../../docs/research/18-known-pitfalls.md#general-engineering) |
| Owner | Peter Burgener |

## Purpose

The types every other module shares: tolerances, results with diagnostics, the computation context, cancellation and small value types. It contains no algorithms and no I/O.

## Scope

- In: `ToleranceSet`, `nearly_equal`, `Severity`, `Diagnostic`, `Result`, `CancellationToken`, `Context`, a `DebugSink` protocol, small value types (`Point2`, `Vector2`).
- Out: curves, loops and regions (`geometry2d`), meshes (`geometry3d`), anything that reads or writes files.

## Public interface

```python
@dataclass(frozen=True, slots=True)
class ToleranceSet:
    length_eps_mm: float
    angle_eps_rad: float
    chord_tol_mm: float
    stage_shares: Mapping[str, float]      # e.g. {"offset": 0.3, "fitting": 0.3, ...}
    def stage_tol_mm(self, stage: str) -> float: ...   # chord_tol_mm * share

def nearly_equal(a: float, b: float, tol: float) -> bool: ...

class Severity(Enum): INFO, WARNING, ERROR

@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str                  # UPPER_SNAKE, e.g. "OFFSET_EMPTY"
    severity: Severity
    message: str
    location: str | None = None

@dataclass(frozen=True, slots=True)
class Result(Generic[T]):
    value: T | None
    diagnostics: tuple[Diagnostic, ...] = ()
    @property
    def ok(self) -> bool: ...

class CancellationToken:
    def cancel(self) -> None: ...
    @property
    def is_cancelled(self) -> bool: ...
    @property
    def flag(self) -> NDArray[np.uint8]: ...   # one element; kernels poll it without calling Python

class DebugSink(Protocol):
    def add(self, name: str, kind: str, data: NDArray[np.float64]) -> None: ...

@dataclass(frozen=True, slots=True)
class Context:
    tolerances: ToleranceSet
    cancel: CancellationToken
    progress: Callable[[float], None]          # 0.0 to 1.0
    logger: logging.Logger
    debug: DebugSink
    seed: int
```

## Requirements

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-FND-001 | THE `ToleranceSet` SHALL provide the length epsilon, the angle epsilon, the chord tolerance and, for each named stage, its share of the chord tolerance. | unit: `tests/foundation/unit/test_tolerance_set.py` | Released for plan 0001 |
| REQ-FND-002 | IF a `ToleranceSet` is created with a tolerance that is not positive and finite, or with stage shares that are negative or sum to more than 1, THEN the constructor SHALL raise `ValueError`. | property and unit: `tests/foundation/property/test_tolerance_set_construction.py` | Released for plan 0001 |
| REQ-FND-003 | THE `nearly_equal` function SHALL return true exactly when \|a − b\| ≤ tol for finite inputs, and false when an input is NaN; for infinite inputs the same expression applies, so `nearly_equal(inf, inf, tol)` is false. | property and unit: `tests/foundation/property/test_nearly_equal.py` | Released for plan 0001 |
| REQ-FND-004 | THE `Result` type SHALL hold an optional value and an ordered tuple of diagnostics; `ok` SHALL be true only when a value is present and no diagnostic has severity `ERROR`. | unit and property: `tests/foundation/unit/test_result.py` | Released for plan 0001 |
| REQ-FND-005 | THE `Context` SHALL carry the tolerance set, the cancellation token, the progress callback, the logger, the debug sink and the random seed; no module SHALL read any of these from global state. | unit: `tests/foundation/unit/test_context.py`; architecture check pending (plan 0001) | Released for plan 0001 |
| REQ-FND-006 | WHEN `cancel()` is called, THE `CancellationToken` SHALL report it through `is_cancelled` and set its one-element `flag` array to 1, so kernels can poll it without calling Python. | unit: `tests/foundation/unit/test_cancellation_token.py`; a kernel polling the flag: `tests/geometry2d/unit/test_offset_cancellation.py` | Released for plan 0001 |
| REQ-FND-007 | THE foundation value types SHALL be immutable, and hashable when their contents are; only `CancellationToken` changes state. | unit: `tests/foundation/unit/test_tolerance_set.py`, `test_result.py`, `test_context.py` | Released (Peter, 2026-09-27) |

## Invariants

Value types are immutable, and hashable when their contents are (a `Result` holding a NumPy array is not); `Result.ok` is consistent with its diagnostics; a cancelled token never becomes uncancelled through its API (code that reaches the flag's owning array can defeat that; accepted by Peter, 2026-09-27).

## Tolerance budget

Defines the budget; uses none itself. Default values: `length_eps_mm = 1e-6` and a chord tolerance of 0.01 mm come from RESEARCH 01. The default angle epsilon and the default stage shares are open questions; the test app may use placeholders marked `# PLACEHOLDER`.

## Failure modes and diagnostics

Invalid construction, and `stage_tol_mm` with a stage that has no share, are programming errors (`ValueError`). Foundation defines no diagnostic codes of its own; other modules define theirs in their specs.

## Algorithms

None.

## Test plan

- Unit: construction, `stage_tol_mm`, `Result.ok`, cancellation flag.
- Property: `nearly_equal` against the definition, including NaN and infinities; invalid tolerance sets always rejected.

## Open questions

- Default angle epsilon and stage shares.
- Whether `Point2` and `Vector2` are needed at all, or arrays suffice everywhere.

## Change log

- 2026-09-24: drafted; REQ-FND-001 to 006 released for plan 0001.
- 2026-09-27: Peter's answers: infinities in REQ-FND-003, REQ-FND-007 released (immutability tests retagged), hashable only when the contents are, the flag's limit accepted, `ValueError` for an unknown stage.
- 2026-09-27: review fixes (pickling, exact share sum, `bool` results, read-only flag owner, `Result` keeps a tuple); "Verified by" now names the test files, the `req` markers name the tests.
- 2026-09-26: REQ-FND-001 to REQ-FND-006 implemented (plan 0001, step 2a): `ToleranceSet`, `nearly_equal`, `Severity`, `Diagnostic`, `Result`, `CancellationToken`, `DebugSink`, `Context` in `src/splintercam/foundation/`. Tests listed in "Verified by" above; REQ-FND-007 stays unimplemented (not released by the plan).

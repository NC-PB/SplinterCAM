# SPEC: foundation

<!-- The shared vocabulary of every module. Drafted on 2026-09-24 from RESEARCH 01 and 18 (general engineering); updated 2026-10-01 to the decisions of 2026-09-27 and 2026-09-28. -->

| | |
| --- | --- |
| Status | Draft. The released requirements live in the prototype's copy, `test_repo/src/opencam/foundation/SPEC.md` (REQ-FND-001 to 007, with Peter's step 2 decisions). That copy is the contract (D-153). The changes below to REQ-FND-001, 002 and the new 008 and 009 are proposed changes (D-056, D-146, D-149); the prototype takes them over together with the kernel change of D-132, after its decision gate (D-133). What changes for the prototype: [delta of 2026-10-01](2026-10-01-delta-plan-0001.md) |
| Layer | 0 |
| Depends on | Python standard library and NumPy only |
| Research | [01](../research/01-foundations.md). Research 18 is being rewritten from public sources (T-019, D-038); until then this spec takes only general software practice from it: result values with diagnostics, a cancellation flag, no global state |
| Decisions | D-028 (units), D-029 (default tolerances), D-049 (no values buried in code), D-055 (determinism), D-056 (tolerance budget, with the Q-034 answer), D-146 (budget floors), D-097 (exact predicates in the float stages) |
| Owner | Peter Burgener |

## Purpose

The types every other module shares: tolerances, results with diagnostics, the computation context, cancellation and small value types. It contains no algorithms and no I/O.

## Scope

- In: `ToleranceSet`, `nearly_equal`, `Severity`, `Diagnostic`, `Result`, `CancellationToken`, `Context`, a `DebugSink` protocol, small value types (`Point2`, `Vector2`).
- Out: curves, loops and regions (`geometry2d`), meshes (`geometry3d`), anything that reads or writes files.

## Units

Lengths in mm and angles in radians everywhere inside the core and the kernels, as plain floats. Every parameter declaration carries its unit; conversion happens only at import, in the user interface and at output (D-028).

## Public interface

```python
BUDGET_PARTS = ("geometry", "fit", "control", "reserve")   # D-056

@dataclass(frozen=True, slots=True)
class ToleranceSet:
    chord_tol_mm: float                    # tol of the operation (D-029 calls it the chord tolerance): covers the finished wall including the control (D-056)
    length_eps_mm: float                   # eps_len, for the float stages (Q-034)
    angle_eps_rad: float                   # eps_ang (Q-034)
    stage_shares: tuple[tuple[str, float], ...]   # (part, share) pairs for BUDGET_PARTS (D-056); a tuple keeps the type hashable
    def stage_tol_mm(self, stage: str) -> float: ...   # chord_tol_mm * share of that part

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
| REQ-FND-001 | THE `ToleranceSet` SHALL provide the length epsilon, the angle epsilon, the chord tolerance and, for each budget part (geometry, fit, control, reserve), its share of the chord tolerance. | unit | Released for plan 0001; changed 2026-10-01: the stage names are the four budget parts of D-056 |
| REQ-FND-002 | IF a `ToleranceSet` is created with a tolerance that is not positive and finite, with a missing or unknown budget part, or with shares that are negative or sum to more than 1, THEN the constructor SHALL raise `ValueError`. | property | Released for plan 0001; changed 2026-10-01: missing or unknown parts are rejected |
| REQ-FND-003 | THE `nearly_equal` function SHALL return true exactly when \|a − b\| ≤ tol for finite inputs, and false when an input is NaN. | property | Released for plan 0001 |
| REQ-FND-004 | THE `Result` type SHALL hold an optional value and an ordered tuple of diagnostics; `ok` SHALL be true only when a value is present and no diagnostic has severity `ERROR`. | unit | Released for plan 0001 |
| REQ-FND-005 | THE `Context` SHALL carry the tolerance set, the cancellation token, the progress callback, the logger, the debug sink and the random seed; no module SHALL read any of these from global state. | unit, architecture check | Released for plan 0001 |
| REQ-FND-006 | WHEN `cancel()` is called, THE `CancellationToken` SHALL report it through `is_cancelled` and set its one-element `flag` array to 1, so kernels can poll it without calling Python. | unit | Released for plan 0001 |
| REQ-FND-007 | THE foundation value types SHALL be immutable, and hashable when their contents are; only `CancellationToken` changes state. | unit | Released (Peter, 2026-09-27, in the prototype's copy) |
| REQ-FND-008 | THE default tolerance values SHALL be read from a documented defaults file where each value is a declared parameter with unit, default, range and source, and SHALL be: chord tolerance 0.05 mm for roughing and 0.01 mm for finishing operations (D-029); length epsilon 1e-6 mm; angle epsilon 1e-9 rad (Q-034 answer, logged as D-056); shares geometry 0.1, fit 0.3, control 0.5, reserve 0.1 (D-056), as the base of REQ-FND-009. No module SHALL hold these numbers as literals (D-049). | unit, architecture check | Draft (new 2026-10-01; release after Q-133) |
| REQ-FND-009 | THE function that builds an operation's `ToleranceSet` SHALL compute the budget parts from tol and the grid unit u: geometry = 0.1·tol + 6u + max(0, 2u − 0.05·tol); reserve = 0.1·tol, written into the NCX as the operation's rounding allowance (D-149); control = 0.5·tol; fit = the rest, clamped at 0; t_flat = 0.05·tol − 0.0001 mm − 3·eps_len; t_topo = 2u. WHEN tol is below tol_min = 8u/0.35 = 2/875 mm ≈ 0.00228571 mm, computed once, it SHALL return no set and the diagnostic `TOL_BELOW_MINIMUM` naming tol_min rounded up to 0.1 nm (0.0022858 mm) (D-146, D-149; research 01, Tolerances). | unit, property | Draft (new 2026-10-01, CP-008; changed by CP-009 and on 2026-10-02) |

## Invariants

Value types are immutable and hashable; `Result.ok` is consistent with its diagnostics; a cancelled token never becomes uncancelled; the budget shares sum to at most 1.

## Tolerance budget

Defines the budget; uses none itself. D-056: the operation tolerance tol covers the finished wall including the control. Geometry (flattening, offsets, snapping) may use 0.1·tol; the arc-fit band 0.3·tol lies on the air side; the control gets 0.5·tol, written per operation as NCX `TOLERANCE`; 0.1·tol is a reserve for output rounding. At tol = 0.01 mm the parts are 0.0016 + 0.0024 + 0.005 + 0.001 mm after D-146; the worst case in the Q-034 brief uses 0.0007 mm of the reserve for rounding at 0.001 mm resolution. The offset kernel's arc tolerance a = 0.05·tol, at least 2 grid units (D-058, Q-036 answer), is part of the geometry share (geometry2d spec). D-146 and D-149 settle small tolerances (Q-132): the geometry part grows by the grid cost, the fit band takes the rest, and below tol_min = 2/875 ≈ 0.00228571 mm the operation is refused, naming 0.0022858 mm (REQ-FND-009; research 01, Tolerances).

eps_len and eps_ang apply to the float stages (import, curve evaluation, snapping before exact predicates, D-097). Inside the offset kernel, coordinates sit on an integer grid of 10⁴ per mm, and topology after a kernel call comes from that grid (Q-036 brief); see the open questions.

## Determinism

D-055, three tiers: topology and decisions identical on every platform; output bit-identical per platform and thread count under the pinned build profile; across platforms, counts exact and geometry within 0.001 mm (Hausdorff). The `Context.seed` is the only source of randomness.

## Failure modes and diagnostics

Invalid construction is a programming error (`ValueError`). Foundation defines no diagnostic codes of its own; other modules define theirs in their specs.

## Algorithms

None.

## Test plan

- Unit: construction, `stage_tol_mm` for each budget part, `Result.ok`, cancellation flag, defaults loaded from the defaults file with units and sources.
- Property: `nearly_equal` against the definition, including NaN and infinities; invalid tolerance sets always rejected, including missing or unknown budget parts.

## Open questions

- Whether `Point2` and `Vector2` are needed at all, or arrays suffice everywhere.
- Resolved 2026-10-01 by D-146 and D-149 (CP-008, CP-009): a geometry floor, the reserve as the rounding allowance NCXchange must keep, the fit band takes the rest; the CAM refuses below about 0.0023 mm, and NCXchange reports a tol a machine's rounding cannot hold; see REQ-FND-009 (Q-132).
- Resolved 2026-10-02: the resolution chain is written in research 01 (Tolerances); A-001 was wrong as stated and is replaced by it. REQ-FND-009 needs the grid unit u as an input, since the parts are not plain shares of tol.

## Change log

- 2026-09-24: drafted; REQ-FND-001 to 006 released for plan 0001.
- 2026-10-01: aligned with D-028, D-029, D-049, D-055, D-056 and the Q-034 answer. Stage names are now the four budget parts; REQ-FND-001 and 002 reworded; REQ-FND-008 new (default values as declared parameters); the placeholders of plan 0001 are replaced. Research 18 reference reduced to general practice (T-019).
- 2026-10-01, after an adversarial review the same day: shares stored as (part, share) pairs so the type stays hashable; the arc-tolerance floor and the grid unit set against the budget (Q-132); D-097 listed; the claim that tests at 0.001 mm work for kernel tests removed.
- 2026-10-01: REQ-FND-009 (budget floors and refusal, D-146, CP-008); REQ-FND-008 shares are the base values.
- 2026-10-01: REQ-FND-009 without the machine's output step: the reserve is the rounding allowance written into the NCX (D-149, CP-009).

# SPEC: foundation

<!-- The shared vocabulary of every module. Drafted on 2026-09-24 from RESEARCH 01 and 18 (general engineering); the tolerance budget taken over on 2026-10-02 from Project Spike's draft (docs/spike/foundation-SPEC-draft.md). -->

| | |
| --- | --- |
| Status | Reviewed: REQ-FND-001, 002, 008 and 009 (decisions D-056, D-146 and D-149, accepted by Peter; plan 0001, step 2) and REQ-FND-010 (Peter, 2026-10-02; step 5) and REQ-FND-011 to 013 (Peter, 2026-10-08, DEC-OFF-002). Released for the stack test app (its own repository): REQ-FND-003 to 006; released by Peter on 2026-09-27: REQ-FND-007 |
| Layer | 0 |
| Depends on | Python standard library and NumPy only |
| Research | [01](../../../docs/research/01-foundations.md), section Tolerances. RESEARCH 18 (Project Spike) is being rewritten from public sources; until then this spec takes only general software practice from it: result values with diagnostics, a cancellation flag, no global state |
| Decisions | D-028 (units), D-029 (default tolerances), D-049 (no values buried in code), D-055 (determinism), D-056 (tolerance budget), D-058 (arc tolerance), D-093 (import arc deviation), D-132 (grid, rounding margin, arc tolerance floor), D-146 (budget floors), D-149 (rounding allowance), D-097 (exact predicates in the float stages), DEC-OFF-002 (the offset's parameters and `CANCELLED`); text in [docs/spike/decisions-snapshot.md](../../../docs/spike/decisions-snapshot.md) |
| Owner | Peter Burgener |

## Purpose

The types every other module shares: tolerances, results with diagnostics, the computation context, cancellation and small value types. It contains no algorithms. Its one read is `tolerance_defaults.toml`, the defaults file packaged with it, read once at import (REQ-FND-008); it reads no other file.

## Scope

- In: `ToleranceSet` with its budget parts, `nearly_equal`, `Severity`, `Diagnostic`, `Result`, `CancellationToken`, `Context`, a `DebugSink` protocol, the packaged tolerance defaults file, foundation's one read, and its `DeclaredParameter` entries, small value types (`Point2`, `Vector2`).
- Out: curves, loops and regions (`geometry2d`), meshes (`geometry3d`), anything that reads or writes user or job files.

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
    stage_shares: tuple[tuple[str, float], ...]   # (part, share) for each of BUDGET_PARTS, stored in that order; a tuple keeps the type hashable
    def stage_tol_mm(self, stage: str) -> float: ...   # the budget part in mm (REQ-FND-009)
    @property
    def flatten_tol_mm(self) -> float: ...             # t_flat (REQ-FND-009)
    @property
    def grid_unit_mm(self) -> float: ...               # u (REQ-FND-001)
    @property
    def topology_tol_mm(self) -> float: ...            # t_topo (REQ-FND-009)
    @property
    def arc_tol_mm(self) -> float: ...                 # a = max(0.05·tol, 2u) (REQ-FND-011)
    @classmethod
    def for_operation(cls, tol_mm: float) -> Result[ToleranceSet]: ...   # REQ-FND-009

@dataclass(frozen=True, slots=True)
class DeclaredParameter:                   # one entry of the defaults file (D-049)
    default: float
    unit: str
    range: tuple[float, float]             # inclusive
    source: str

TOLERANCE_DEFAULTS: Mapping[str, DeclaredParameter]   # read once from tolerance_defaults.toml (REQ-FND-008)

def nearly_equal(a: float, b: float, tol: float) -> bool: ...

class Severity(Enum): INFO, WARNING, ERROR

CANCELLED: Diagnostic     # code "CANCELLED", WARNING: what every module returns, with no value, when ctx.cancel is set (REQ-FND-013)

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

`for_operation` takes no `Context`, unlike research 01's sketch `for_operation(tol, ctx)`: the `Context` holds the `ToleranceSet`, so the set is built first. `TOLERANCE_DEFAULTS` serves building tolerance sets and declaring parameters; a computation reads its tolerances from its `Context` (REQ-FND-005).

## Requirements

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-FND-001 | THE `ToleranceSet` SHALL provide the length epsilon, the angle epsilon, the chord tolerance, the grid unit u and, for each budget part (geometry, fit, control, reserve), its share of the chord tolerance. | unit: `tests/foundation/unit/test_tolerance_set.py` | Reviewed (D-056; plan 0001, step 2). Changed 2026-10-02: the stage names are the four budget parts; the grid unit (Peter, plan 0003) |
| REQ-FND-002 | IF a `ToleranceSet` is created with a tolerance that is not positive and finite, with a missing or unknown budget part, or with shares that are negative or sum to more than 1, with a part given twice, with a chord tolerance below the floor of its own fit share f (8u / (f + 0.05) for f ≥ 0.15, otherwise 6u / f, evaluated in double as tol_min is; no tol for f = 0), or with t_flat ≤ 0, THEN the constructor SHALL raise `ValueError`. | property and unit: `tests/foundation/property/test_tolerance_set_construction.py`, `property/test_tolerance_budget.py`, `unit/test_tolerance_set.py` | Reviewed (D-056; plan 0001, step 2). Changed 2026-10-02: missing, unknown or repeated parts, the floor and t_flat > 0 (Peter, step 5) |
| REQ-FND-003 | THE `nearly_equal` function SHALL return true exactly when \|a − b\| ≤ tol for finite inputs, and false when an input is NaN; for infinite inputs the same expression applies, so `nearly_equal(inf, inf, tol)` is false. | property and unit: `tests/foundation/property/test_nearly_equal.py` | Released for plan 0001 of the stack test app |
| REQ-FND-004 | THE `Result` type SHALL hold an optional value and an ordered tuple of diagnostics; `ok` SHALL be true only when a value is present and no diagnostic has severity `ERROR`. | unit and property: `tests/foundation/unit/test_result.py` | Released for plan 0001 of the stack test app |
| REQ-FND-005 | THE `Context` SHALL carry the tolerance set, the cancellation token, the progress callback, the logger, the debug sink and the random seed; no module SHALL read any of these from global state. | unit: `tests/foundation/unit/test_context.py`; architecture check pending (`tools/arch-check`) | Released for plan 0001 of the stack test app |
| REQ-FND-006 | WHEN `cancel()` is called, THE `CancellationToken` SHALL report it through `is_cancelled` and set its one-element `flag` array to 1, so kernels can poll it without calling Python. | unit: `tests/foundation/unit/test_cancellation_token.py`; a kernel polling the flag: pending, with the first kernel | Released for plan 0001 of the stack test app |
| REQ-FND-007 | THE foundation value types SHALL be immutable, and hashable when their contents are; only `CancellationToken` changes state. | unit: `tests/foundation/unit/test_tolerance_set.py`, `test_result.py`, `test_context.py` | Released (Peter, 2026-09-27) |
| REQ-FND-008 | THE default tolerance values SHALL be read from a documented defaults file where each value is a declared parameter with unit, default, range and source, and SHALL be: chord tolerance 0.05 mm for roughing and 0.01 mm for finishing operations (D-029); length epsilon 1e-6 mm; angle epsilon 1e-9 rad (Q-034 answer, logged as D-056); shares geometry 0.1, fit 0.3, control 0.5, reserve 0.1 (D-056), as the base of REQ-FND-009. No module SHALL hold these numbers as literals (D-049). IF an entry of the file is broken (a missing or extra key, a value of the wrong type, a default outside its range, no unit or source), THEN the import SHALL fail with `ValueError` naming the entry's key. | unit: `tests/foundation/unit/test_tolerance_defaults.py`; architecture check pending (`tools/arch-check`) | Reviewed (D-029, D-049, D-056; plan 0001, step 2). Changed 2026-10-02: a broken entry fails naming its key (Peter, step 5) |
| REQ-FND-009 | THE function that builds an operation's `ToleranceSet` SHALL compute the budget parts from tol and the grid unit u: geometry = 0.1·tol + 6u + max(0, 2u − 0.05·tol); reserve = 0.1·tol, the operation's rounding allowance (D-149), written by the NCX writer; control = 0.5·tol; fit = the rest, clamped at 0; t_flat = 0.05·tol − 0.0001 mm − 3·eps_len; t_topo = 2u. WHEN tol is below tol_min = 8u/0.35 = 2/875 mm ≈ 0.00228571 mm, computed once, it SHALL return no set and the diagnostic `TOL_BELOW_MINIMUM` naming tol_min rounded up to 0.1 nm (0.0022858 mm) (D-146, D-149; research 01, Tolerances). | unit (research 01, tests 14 and 15): `tests/foundation/unit/test_tolerance_budget.py`, `test_tolerance_set.py`; property: `tests/foundation/property/test_tolerance_budget.py` | Reviewed (D-146, D-149; plan 0001, step 2). Changed 2026-10-02: the reserve's wording (Peter, step 5) |
| REQ-FND-010 | WHEN tol is above 1 mm, the upper end of the tol range in the defaults file, THE function that builds an operation's `ToleranceSet` SHALL return no set and the diagnostic `TOL_ABOVE_MAXIMUM` (error), a guard against unit mistakes (research 01, Tolerances; Peter, 2026-10-02). | unit: `tests/foundation/unit/test_tolerance_budget.py` | Reviewed (Peter, 2026-10-02; plan 0001, step 5) |
| REQ-FND-011 | THE `ToleranceSet` SHALL provide the arc tolerance a = max(0.05·tol, 2u) in mm as `arc_tol_mm`, computed from the declared parameters `arc_tol_share` and `arc_tol_floor_grid_units`, the same a that `stage_tol_mm` charges the floor of (D-058, D-132). | unit: `tests/foundation/unit/test_tolerance_set.py` (tol 0.01, tol_min 0.0022858 where the floor binds, 0.05) | Reviewed (Peter, 2026-10-08, DEC-OFF-002; plan 0005, step 2) |
| REQ-FND-012 | THE defaults file SHALL declare `offset_bias_grid_units` = 3 (grid units; the bias of the offset δ = t + a + 3u, D-132) and `join_steps_max` = 65536 (steps per turn, the most a round join may take; research 02, Parameters, prototype REQ-OFF-014), each fixed (default at both ends of its range) with unit and source. | unit: `tests/foundation/unit/test_tolerance_defaults.py` | Reviewed (Peter, 2026-10-08, DEC-OFF-002; plan 0005, step 2) |
| REQ-FND-013 | THE foundation module SHALL declare the diagnostic `CANCELLED` (severity warning) as the constant `CANCELLED`, which every module returns, with no value, when `ctx.cancel` is set. | unit: `tests/foundation/unit/test_result.py` | Reviewed (Peter, 2026-10-08, DEC-OFF-002; plan 0005, step 2) |

## Invariants

Value types are immutable, and hashable when their contents are (a `Result` holding a NumPy array is not); `Result.ok` is consistent with its diagnostics; a cancelled token never becomes uncancelled through its API (code that reaches the flag's owning array can defeat that; accepted by Peter, 2026-09-27); the budget shares sum to at most 1; for every set the constructor accepts, the four budget parts are not negative and sum to at most tol within two units in the last place of tol (rounding), and t_flat is positive; for the sets of `for_operation`, from tol_min up, they sum to tol.

## Tolerance budget

Defines the budget; uses none itself. D-056: the operation tolerance tol covers the finished wall including the control. Geometry (flattening, offsets, snapping) gets 0.1·tol; the arc-fit band 0.3·tol lies on the air side; the control gets 0.5·tol, written per operation as NCX `TOLERANCE`; 0.1·tol is a reserve for output rounding, the operation's rounding allowance (D-149); the NCX writer writes it as the word `ROUND_LIMIT` (NCXchange draft D363; Peter, 2026-10-02). D-146 adds what the offset kernel's grid costs to geometry and takes it from the fit band: its rounding margin of 6 grid units (D-132) and max(0, 2u − 0.05·tol) for the floor of its arc tolerance a = max(0.05·tol, 2u) (D-058). The other 0.05·tol of geometry pays for arcs recognised at import (0.0001 mm, D-093), snapping (3·eps_len) and flattening, t_flat. At tol = 0.01 mm the parts are 0.0016 + 0.0024 + 0.005 + 0.001 mm and t_flat = 0.000397 mm. Below tol_min = 2/875 mm the fit band would be negative, and the operation is refused (REQ-FND-009); above 1 mm it is refused as a likely unit mistake (REQ-FND-010). The defaults file gives tol the range [0.0022858, 1.0]: its lower end is the user-facing minimum, tol_min rounded up to 0.1 nm, the value `TOL_BELOW_MINIMUM` names; `for_operation` itself accepts from tol_min.

`stage_tol_mm` gives each part as REQ-FND-009 computes it: control and reserve are their share of tol; geometry is its share plus the grid cost; fit is its share minus the grid cost, clamped at 0. The parts are evaluated in double in the order of the formulas; at tol_min the fit band comes out as −7e-20 mm and is clamped (research 01, Tolerances). Every number comes from `tolerance_defaults.toml` next to the code (REQ-FND-008), each entry a table with `default`, `unit`, `range` ([min, max], inclusive; a fixed value has its default at both ends) and `source`. The entries of REQ-FND-008 are `chord_tol_roughing_mm`, `chord_tol_finishing_mm`, `length_eps_mm`, `angle_eps_rad`, `share_geometry`, `share_fit`, `share_control` and `share_reserve`; those REQ-FND-009 adds are `grid_unit_mm` (u), `rounding_margin_grid_units` (6), `arc_tol_share` (0.05), `arc_tol_floor_grid_units` (2), `import_arc_deviation_mm` (0.0001), `snap_allowance_length_eps` (3), `topology_tol_grid_units` (2) and `tol_min_step_mm` (0.1 nm). `offset_bias_grid_units` (3) and `join_steps_max` (65536) are declared parameters of offset2d kept in this file for the same reason (offset2d SPEC, REQ-OFF-042; REQ-FND-012). `flatten_step_max_rad` (π/2) is a declared parameter of geometry2d kept in this file, so that module reads no file of its own (geometry2d SPEC, REQ-G2D-230; plan 0003, step 4).

eps_len and eps_ang apply to the float stages (import, curve evaluation, snapping before exact predicates, D-097). Inside the offset kernel, coordinates sit on an integer grid of u = 0.0001 mm, and topology after a kernel call comes from that grid; t_topo = 2u is the distance below which the float stages treat features as touching (research 01, resolution chain). One Clipper2 call spans less than `grid_max_span_units` = 2^26 grid units in x and y, about 6.7 m at this u, enough for release 1 (Peter, 2026-10-08); larger machines come later through a coarser grid unit per job, not now.

## Determinism

D-055, three tiers: topology and decisions identical on every platform; output bit-identical per platform and thread count under the pinned build profile; across platforms, counts exact and geometry within 0.001 mm (Hausdorff). The `Context.seed` is the only source of randomness.

## Failure modes and diagnostics

| Situation | Result | Diagnostic |
| --- | --- | --- |
| `for_operation` with tol below tol_min | no set | `TOL_BELOW_MINIMUM` (error), naming 0.0022858 mm |
| `for_operation` with tol above 1 mm | no set | `TOL_ABOVE_MAXIMUM` (error) |
| A computation finds `ctx.cancel` set | no value | `CANCELLED` (warning; the constant `CANCELLED`, REQ-FND-013) |
| Invalid construction of a `ToleranceSet` (REQ-FND-002, including a chord tolerance below the floor of its own fit share and t_flat ≤ 0), `for_operation` with a non-finite tol, `stage_tol_mm` with a stage that is not a budget part | programming error | `ValueError` |
| A broken defaults file entry | programming error at import | `ValueError` naming the entry's key |

## Algorithms

None.

## Test plan

- Unit: construction, sets refused for their floor or t_flat, `stage_tol_mm` for each budget part, `Result.ok`, cancellation flag, defaults read from the defaults file with units, ranges and sources, research 01 tests 14 and 15, `TOL_ABOVE_MAXIMUM` above 1 mm, a broken defaults file failing with the entry's key.
- Property: `nearly_equal` against the definition, including NaN and infinities; invalid tolerance sets always rejected, including missing, unknown or repeated budget parts, a chord tolerance below the floor of its own fit share, t_flat ≤ 0; the parts of any accepted set never sum to more than tol; the parts sum to tol for every tol from tol_min to 1 mm; every tol below tol_min refused with `TOL_BELOW_MINIMUM`.

## Size estimate

Budget 250 NLOC (Peter, 2026-10-02), counted without comments and docstrings as `tools/size-check` and lizard count them; 224 after plan 0001, step 5. About 1150 lines of tests.

## Open questions

- Whether `Point2` and `Vector2` are needed at all, or arrays suffice everywhere.

## Change log

- 2026-09-24: drafted; REQ-FND-001 to 006 released for plan 0001 of the stack test app.
- 2026-09-27: Peter's answers: infinities in REQ-FND-003, REQ-FND-007 released (immutability tests retagged), hashable only when the contents are, the flag's limit accepted, `ValueError` for an unknown stage.
- 2026-09-27: review fixes (pickling, exact share sum, `bool` results, read-only flag owner, `Result` keeps a tuple); "Verified by" now names the test files, the `req` markers name the tests.
- 2026-09-26: REQ-FND-001 to REQ-FND-006 implemented in the stack test app (its plan 0001, step 2a).
- 2026-10-02: plan 0001, step 2: REQ-FND-001 and 002 changed and REQ-FND-008 and 009 added from Project Spike's draft (D-029, D-049, D-056, D-146, D-149), all four `Reviewed`; `stage_shares` holds (part, share) pairs; `for_operation`, `flatten_tol_mm`, `topology_tol_mm`, `DeclaredParameter` and `TOLERANCE_DEFAULTS` added; the defaults file replaces the placeholders; `TOL_BELOW_MINIMUM` is foundation's first diagnostic.
- 2026-10-02: plan 0001, step 5, Peter's answers: the choices of step 2 confirmed (base shares with the grid cost in `stage_tol_mm`, `for_operation` without a `Context`, t_flat and t_topo as properties, a repeated part as a REQ-FND-002 error, the TOML file read with `tomllib` as foundation's one read); REQ-FND-002 adds the floor of the set's own shares; REQ-FND-008 a broken entry naming its key; REQ-FND-009's reserve is written by the NCX writer (`ROUND_LIMIT`); REQ-FND-010 `TOL_ABOVE_MAXIMUM`. Then the floor's open question answered: 8u / (f + 0.05) for f ≥ 0.15, otherwise 6u / f, and t_flat > 0, so the invariants hold for every accepted set.
- 2026-10-02: plan 0003, step 2: `grid_unit_mm` on `ToleranceSet` (REQ-FND-001), so computations read u from their `Context` (Peter).
- 2026-10-02: plan 0003, step 4: the defaults file holds `flatten_step_max_rad` (π/2) for geometry2d (REQ-G2D-230).
- 2026-10-08: the defaults file holds `grid_max_span_units` (2^26) for geometry2d's Clipper2 calls (REQ-G2D-034; Peter, DEC-G2D-034).
- 2026-10-08: plan 0005, step 2 (Peter, DEC-OFF-002): REQ-FND-011 (`ToleranceSet.arc_tol_mm`), REQ-FND-012 (`offset_bias_grid_units`, `join_steps_max` in the defaults file) and REQ-FND-013 (the constant `CANCELLED`) added for offset2d; the form of `CANCELLED` is DEC-FND-001.

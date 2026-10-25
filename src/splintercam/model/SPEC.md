# SPEC: model

<!-- The job's data in memory. Drafted on 2026-10-25 for plan 0007, step 3, cut to the slice (D-160): one flat end mill,
     one box stock, one setup, the operations' parameters as declarations. Tool assemblies, libraries, several setups,
     fixtures, cutting data and the job file come with later plans. -->

| | |
| --- | --- |
| Status | Reviewed (2026-10-25, Peter: AQ-002 and AQ-003 in `docs/agents/QUESTIONS.md`; plan 0007, Decisions). Implemented 2026-10-25 (plan 0007 step 3), all requirements. Choices marked "(ours)" are in `src/splintercam/model/DECISIONS.md` and stand as the contract |
| Layer | 2 (see architecture/modules.yaml) |
| Depends on | foundation (`Context`, `Result`, `Diagnostic`, `Severity`, `CANCELLED`, `ToleranceSet`) |
| Research | [26][r26], sections The subset plan 0007 uses, Structure (setup and operation header); [22][r22], Scope and Parameters; [27][r27], Datum and Program rows of the controller table; [10][r10], Method (heights from the stock top) |
| Decisions | D-018 (generated panels from declarations), D-025 (n and vf by hand), D-026 (box stock), D-028 (units), D-049 (declared parameters), D-052 (operation header), D-078 (setups), D-126 (operation order), D-148 (controller limits are NCXchange's), D-150 (allowance), D-154 and D-155 (measurement points), D-055 (determinism); text in [docs/spike/decisions-snapshot.md](../../../docs/spike/decisions-snapshot.md) |
| Owner | Peter Burgener |

## Purpose

Holds what a job knows before anything is computed: the tools with their measurement points, the stock, the setup with its work offset, and the operations with their parameter values. It checks these values once, where they enter, and names every wrong one, so the planning modules can trust them. Its users in plan 0007 are `job` (step 7), which builds the data from the job file, the profile strategy (step 5), which declares its parameters with model's type, and `cl` and `ncx` through the operation header (steps 4 and 6).

## Scope

- In: a flat end mill entered by hand (number, diameter, flute length, measurement points; research 22, Scope; D-154); a box stock (D-026); one setup with its work offset (D-078); operations in the user's order (D-126) with tool, point, spindle speed, tolerance and the strategy's parameter values; parameter declarations (D-018, D-049) and the check of values against them.
- Out, handled elsewhere: checks that need the part or the strategy's meaning: the stock containing the part, z_bottom below z_top, the step-down against the flute length, the allowance above −R (the profile strategy, research 22, traps 3 and Method 3; D-150); clearance and retract heights from the stock top (`toolpath`, research 10); the header's `source` parameter hash (`cl` or the strategy, research 26; REQ-MDL-024's fixed order makes it stable); the job file, unit conversion from inch or degrees, the strategy registry and the program name and number (`job` and `ncx`, steps 6 and 7; D-028); machine limits on tool number, work offset, speed and feed (NCXchange reports them, D-148; the sidecar checks later, research 27).
- Later (one line each, no work): tool types other than the flat end mill, shank, holder, stick-out and assemblies (feature map, section 4); ISO 13399 names; tool libraries and the magazine; spindle direction (CW only, research 26 subset) and coolant (on, research 26 subset) as fields; several setups and the placement of research 26 (the part's frame is the work frame here); several origins per setup; fixtures; stock as cylinder or other shapes; parameter kinds other than numbers (enums, geometry slots), and the panel fields of docs/dev/11 (group, label, tooltip, basic flag, visibility); what each parameter affects (docs/dev/03, Recompute model); saving the job.
- Non-goals: computing anything from the data (heights, feeds, the tool envelope); converting units (values are in the internal unit, D-028); a second copy of controller limits (D-148).

## Public interface

Lengths in mm, angles in rad, feeds in mm/min, speeds in 1/min, float64 (D-028). All names are proposals (ours). No kernel; no loops over points (the split rule does not apply).

```python
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from splintercam.foundation import Context, Result

@dataclass(frozen=True, slots=True)
class MeasurementPoint:                       # D-154, D-155
    number: int                               # k: 1 for the tool's first point
    axial_offset_mm: float                    # a: along the tool axis from the tip
    register_radius_mm: float                 # r: the radius the shop enters for this point

TIP = MeasurementPoint(1, 0.0, 0.0)           # the point of the slice (research 26 subset)

@dataclass(frozen=True, slots=True)
class FlatEndMill:
    number: int                               # the T number in the job (NCX TOOL=)
    diameter_mm: float
    flute_length_mm: float
    points: tuple[MeasurementPoint, ...] = (TIP,)
    @property
    def radius_mm(self) -> float: ...         # diameter_mm / 2

@dataclass(frozen=True, slots=True)
class StockBox:                               # axis-aligned, in the work frame
    min_mm: tuple[float, float, float]
    max_mm: tuple[float, float, float]
    @property
    def top_mm(self) -> float: ...            # max_mm[2], the stock top of research 10

class Unit(Enum):
    MM = "mm"
    MM_PER_MIN = "mm/min"
    RATIO = "1"                               # dimensionless, such as research 22's air gap 0.2·R

@dataclass(frozen=True, slots=True)
class ParameterDeclaration:                   # D-018, D-049
    name: str
    unit: Unit
    default: float | None                     # None: the job must give a value
    low: float                                # -inf allowed
    high: float                               # +inf allowed
    low_open: bool                            # True: the value must be > low
    high_open: bool
    source: str                               # decision or research section

@dataclass(frozen=True, slots=True)
class Operation:
    name: str                                 # NCX SECTION
    strategy: str                             # the strategy's id (docs/dev/03)
    tool_number: int
    spindle_rpm: float                        # CW (research 26 subset)
    tol_mm: float                             # the operation tolerance tol (D-029, D-056)
    parameters: tuple[tuple[str, float], ...] # (declared name, value in the declared unit)
    point_number: int = 1                     # D-154: the tool's first point by default

@dataclass(frozen=True, slots=True)
class Setup:
    work_offset: int                          # NCX ORIGIN, an index, not a G code
    stock: StockBox
    operations: tuple[Operation, ...]         # in the user's order (D-126)

@dataclass(frozen=True, slots=True)
class JobData:
    tools: tuple[FlatEndMill, ...]
    setup: Setup

def check_job(job: JobData, declarations: Mapping[str, Sequence[ParameterDeclaration]],
              ctx: Context) -> Result[JobData]: ...
```

- `declarations` maps each strategy id to that strategy's declarations; `job` builds it from the strategies it knows (step 7).
- The value is present only when the result is `ok`: any error means no value (REQ-FND-004). The returned job equals the input except that every operation's `parameters` holds every declared parameter, in declaration order (REQ-MDL-024).
- A `ParameterDeclaration` is code, written by a strategy: an invalid one raises `ValueError` when it is constructed, and a strategy whose declarations repeat a name makes `check_job` raise before it checks anything (REQ-MDL-018, 019), as foundation does for its own invalid values. Everything in `job` is user input, of any Python type, and gets a diagnostic (REQ-MDL-029).
- Parameters are (name, value) pairs, not a dict, so a checked job stays immutable and hashable and its order is part of equality (REQ-MDL-024).

## Requirements

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-MDL-001 | THE model module SHALL hold a flat end mill as its number, diameter and flute length in mm and an ordered tuple of measurement points, with the tip `TIP` (k = 1, a = 0, r = 0) as the default (research 22, Scope; research 26 subset; D-154). | unit: `test_a_flat_end_mill_defaults_to_the_tip`, `test_the_example_job_passes_with_every_parameter_completed` | Reviewed |
| REQ-MDL-002 | IF a tool's number is below 1, THEN `check_job` SHALL report `TOOL_NUMBER_INVALID` (error) (ours: NCX `TOOL=n`; the upper limit is the machine's, which NCXchange reports, D-148). | unit: `test_tool_number_below_1` | Reviewed |
| REQ-MDL-003 | IF a tool's diameter or flute length is not finite or not above 0, THEN `check_job` SHALL report `TOOL_DIMENSION_INVALID` (error) naming the dimension and its value. | unit: `test_tool_dimension_not_finite_or_not_above_0` | Reviewed |
| REQ-MDL-004 | IF two tools have the same number, THEN `check_job` SHALL report `TOOL_NUMBER_DUPLICATE` (error) on the second (ours: a T number names one tool of the job). | unit: `test_a_repeated_tool_number_is_reported_on_the_second` | Reviewed |
| REQ-MDL-005 | IF a tool has no measurement point, or its points are not numbered 1, 2, …, n in their order, THEN `check_job` SHALL report `TOOL_POINT_NUMBERS` (error) (D-155: 1 for the tool's first point; numbering the rest in order ours, DEC-MDL-008). | unit: `test_points_numbered_other_than_1_to_n` | Reviewed |
| REQ-MDL-006 | IF a point's axial offset a is not finite or is below 0, or its register radius r is not finite or lies outside [0, R], THEN `check_job` SHALL report `TOOL_POINT_INVALID` (error) naming the point, the value and the range (a ≥ 0: D-154, the user can enter any point, measured from the tip up; r ≤ R: D-154, r is not larger than the radius that cuts, which for a flat end mill is R along the whole flute; Peter, AQ-002, DEC-MDL-004). WHERE a lies above the flute length, THE `check_job` function SHALL report `TOOL_POINT_ABOVE_FLUTE` (warning) naming the point and the shift of every Z, as in "every Z is output 40 mm above the tip", and keep the point (Peter, AQ-002: so a typing error is seen; the setup sheet states the point, D-151). Both checks are skipped for a tool with `TOOL_DIMENSION_INVALID`. | unit: `test_point_outside_its_range`, `test_point_on_the_edge_of_its_range_passes`, `test_point_above_the_flute_is_kept_with_a_warning_naming_the_shift`, `test_point_checks_are_skipped_for_an_invalid_dimension` | Reviewed |
| REQ-MDL-007 | THE model module SHALL hold the stock as an axis-aligned box in the work frame, by its two corners in mm, with its top as the largest z (D-026; research 10, Method, the heights from the stock top). | unit: `test_the_stock_top_is_the_largest_z` | Reviewed |
| REQ-MDL-008 | IF a stock corner coordinate is not finite, or the box's extent along any axis is not above eps_len, THEN `check_job` SHALL report `STOCK_BOX_INVALID` (error) naming the axis. | unit: `test_stock_extent_not_above_eps_or_not_finite` | Reviewed |
| REQ-MDL-009 | THE model module SHALL hold one setup with its work offset, its stock and its operations in the user's order (D-078, D-126); the work frame is the part's frame, the drawing's coordinates (research 26 subset: placement the identity; DEC-MDL-002). IF the setup has no operation, THEN `check_job` SHALL report `SETUP_NO_OPERATION` (error) (ours: a program without moves is not a result). | unit: `test_a_setup_without_operations` | Reviewed |
| REQ-MDL-010 | IF the work offset is below 1, THEN `check_job` SHALL report `SETUP_WORK_OFFSET_INVALID` (error) (research 26, Structure: an integer ≥ 1; trap 13: an index, not a G code; the upper limit per controller is NCXchange's, research 27, Datum row, D-148). | unit: `test_work_offset_below_1` | Reviewed |
| REQ-MDL-011 | THE model module SHALL hold an operation as its name, strategy id, tool number, point number (1 by default, D-154), spindle speed in 1/min, tolerance tol in mm and parameter values by name (D-052; research 26, operation header). | unit: `test_an_operation_uses_point_1_by_default` | Reviewed |
| REQ-MDL-012 | IF an operation's name is empty or holds a character other than an ASCII letter, a digit or an underscore, THEN `check_job` SHALL report `OP_NAME_INVALID` (error) (research 26 subset: `name` in letters, digits and underscores; checked condition 2). | unit: `test_operation_name_with_other_characters` | Reviewed |
| REQ-MDL-013 | IF two operations have the same name, THEN `check_job` SHALL report `OP_NAME_DUPLICATE` (error) on the second (ours, DEC-MDL-005: NCXchange's messages are mapped back to the operation by its section, plan 0007 step 6). | unit: `test_a_repeated_operation_name_is_reported_on_the_second` | Reviewed |
| REQ-MDL-014 | IF an operation's tool number names no tool of the job, THEN `check_job` SHALL report `OP_TOOL_UNKNOWN` (error); IF it names a tool that has no point with the operation's point number, THEN `OP_POINT_UNKNOWN` (error). | unit: `test_operation_naming_a_missing_tool_or_point` | Reviewed |
| REQ-MDL-015 | IF an operation's spindle speed is not finite or not above 0, THEN `check_job` SHALL report `OP_SPINDLE_INVALID` (error) (research 22, Parameters: > 0; the machine's maximum later, feature map, machine limits). | unit: `test_spindle_speed_not_finite_or_not_above_0` | Reviewed |
| REQ-MDL-016 | THE `check_job` function SHALL check each operation's tol with `ToleranceSet.for_operation` and report its error diagnostics with the operation as location; IF tol is not finite, THEN it SHALL report `OP_TOL_INVALID` (error) instead of calling it (REQ-FND-009, 010: no range of its own; `for_operation` raises on a non-finite tol). | unit: `test_tolerance_is_checked_by_foundation` | Reviewed |
| REQ-MDL-017 | THE model module SHALL provide `ParameterDeclaration`: name, unit (mm, mm/min or dimensionless, D-028; rad and 1/min come with the first parameter that needs them), default or none, a range whose ends are each inclusive or exclusive and may be infinite, and source (D-049; D-018: the operation panels are generated from these). Values are float64 in the declared unit. | unit: `test_a_declaration_holds_its_fields` | Reviewed |
| REQ-MDL-018 | IF a declaration's name is not a Python identifier, its unit is not a `Unit`, its source is empty, an end of its range is NaN, its range contains no finite value, or its default is not finite or lies outside the range, THEN constructing it SHALL raise `ValueError` (a programming error in the strategy). | unit: `test_an_invalid_declaration_raises`, `test_a_point_range_with_closed_ends_is_valid` | Reviewed |
| REQ-MDL-019 | IF a strategy's declarations repeat a name, THEN `check_job` SHALL raise `ValueError` before it checks anything (a programming error in the strategy, not a diagnostic of the job). | unit: `test_repeated_declared_names_raise_before_any_check` | Reviewed |
| REQ-MDL-020 | IF an operation's strategy id is not a key of `declarations`, THEN `check_job` SHALL report `OP_STRATEGY_UNKNOWN` (error) and check none of its parameter values. | unit: `test_an_unknown_strategy_skips_the_parameter_checks` | Reviewed |
| REQ-MDL-021 | IF an operation gives a value for a name its strategy does not declare, THEN `check_job` SHALL report `PARAM_UNKNOWN` (error) naming it (ours: a misspelt name would otherwise leave the default in force unseen); IF it gives a name twice, THEN `PARAM_REPEATED` (error). | unit: `test_unknown_and_repeated_names` | Reviewed |
| REQ-MDL-022 | IF a declared parameter without a default has no value, THEN `check_job` SHALL report `PARAM_MISSING` (error) naming it and its unit. | unit: research 22, Parameters (step-down and feeds have no default), `test_the_example_without_its_feeds`; property: `test_a_broken_field_gives_its_code_once_at_its_location_and_no_value` | Reviewed |
| REQ-MDL-023 | IF a value is not finite or lies outside its declared range, THEN `check_job` SHALL report `PARAM_OUT_OF_RANGE` (error) naming the parameter, the value, the range with its open or closed ends, and the unit. | unit: research 22, Parameters (feeds > 0), `test_a_value_outside_its_range_names_value_range_and_unit` | Reviewed |
| REQ-MDL-024 | WHEN `check_job` reports no error, THE returned job SHALL equal the input except that each operation's `parameters` holds every declared parameter of its strategy, in declaration order, the default where the operation gave no value. | unit: `test_values_are_completed_in_declaration_order_whatever_the_input_order`, `test_values_are_immutable_and_a_checked_job_is_hashable`; property: `test_a_valid_job_comes_back_completed_and_checking_it_again_changes_nothing` | Reviewed |
| REQ-MDL-025 | THE `check_job` function SHALL check every element and return every diagnostic, not only the first, and SHALL return no value when any is an error (ours, as io). | unit: `test_every_diagnostic_in_the_fixed_order_with_its_location`; property: `test_a_broken_field_gives_its_code_once_at_its_location_and_no_value` | Reviewed |
| REQ-MDL-026 | THE `check_job` function SHALL return its diagnostics in this order: tools in job order; the stock; the setup (work offset, then `SETUP_NO_OPERATION`); operations in the user's order. Within a tool or an operation, `VALUE_TYPE_INVALID` first, then in the order of the requirements above; parameters in declaration order, then unknown names sorted by code point; `PARAM_REPEATED` at the repeated name's position (ours, D-055). | unit: `test_every_diagnostic_in_the_fixed_order_with_its_location`; property: `test_diagnostics_come_in_the_fixed_order` | Reviewed |
| REQ-MDL-027 | THE `check_job` function SHALL give every diagnostic a location naming its element: `tool <index> (T<number>)`, `tool <index> (T<number>), point <k>`, `stock`, `setup`, `operation <index> (<name>)`, `operation <index> (<name>), parameter <name>`; indexes from 1 (ours). | unit: `test_every_diagnostic_in_the_fixed_order_with_its_location` and the tests of REQ-MDL-002, 006, 012, 021 | Reviewed |
| REQ-MDL-028 | WHEN `ctx.cancel` is set at entry, THE `check_job` function SHALL return no value and `CANCELLED` alone (REQ-FND-013; the check is too short to poll again). | unit: `test_cancelled_at_entry` | Reviewed |
| REQ-MDL-029 | IF a field or parameter value is not of its type (numbers k, T, work offset and the operation's tool and point: `int`, not `bool`; lengths, speeds, tol and parameter values: `int` or `float`, not `bool`, and an `int` that converts to a finite float; names and the strategy id: `str`; the stock corners: tuples of three numbers; the tools, points and operations: tuples of their types; each parameter entry: a pair of a `str` and a number), THEN `check_job` SHALL report `VALUE_TYPE_INVALID` (error) naming the field and the type found, and skip that field's other checks (ours, DEC-MDL-003: JSON's `true` reaches Python as `True`, an `int`, which would pass as tool number 1 or tol 1 mm). | unit: `test_a_value_of_the_wrong_type`, `test_an_int_length_is_accepted_and_the_wrong_type_is_named`; property: `test_a_broken_field_gives_its_code_once_at_its_location_and_no_value` | Reviewed |

## Invariants

- A job that `check_job` returns is consistent: every field has its type, tool numbers are unique and at least 1, the setup has an operation, every operation names an existing tool and point, every point lies on its tool, every declared parameter has a value within its range (REQ-MDL-002 to 024, 029). Property test over generated jobs: whenever the result has a value, these hold.
- `check_job` is idempotent: checking a returned job again returns the same job and no error (REQ-MDL-024). Property test.
- The model's values are immutable and held in memory only; nothing in the module reads or writes a file. Unit test: assigning to a field of each type raises; `check_job`'s returned job is hashable.

## Tolerance budget

None spent. eps_len is the only tolerance read (REQ-MDL-008); tol is checked, not used (REQ-MDL-016).

## Failure modes and diagnostics

All diagnostics are errors except `TOOL_POINT_ABOVE_FLUTE` (warning) and `CANCELLED`; with any error the result has no value (REQ-MDL-025).

| Situation | Diagnostic |
| --- | --- |
| Tool number below 1 | `TOOL_NUMBER_INVALID` |
| Diameter or flute length not finite or not above 0 | `TOOL_DIMENSION_INVALID` |
| Same tool number twice | `TOOL_NUMBER_DUPLICATE` |
| No point, or points not numbered 1 … n | `TOOL_POINT_NUMBERS` |
| a below 0, r outside [0, R], or not finite | `TOOL_POINT_INVALID` |
| a above the flute length | `TOOL_POINT_ABOVE_FLUTE` (warning), the point kept |
| Stock corner not finite, or extent ≤ eps_len | `STOCK_BOX_INVALID` |
| Work offset below 1 | `SETUP_WORK_OFFSET_INVALID` |
| Operation name empty or with other characters | `OP_NAME_INVALID` |
| Same operation name twice | `OP_NAME_DUPLICATE` |
| Tool or point not in the job | `OP_TOOL_UNKNOWN`, `OP_POINT_UNKNOWN` |
| Spindle speed not finite or not above 0 | `OP_SPINDLE_INVALID` |
| tol not finite; tol below tol_min or above 1 mm | `OP_TOL_INVALID`; foundation's `TOL_BELOW_MINIMUM`, `TOL_ABOVE_MAXIMUM` |
| Strategy not known | `OP_STRATEGY_UNKNOWN` |
| Value for an undeclared name | `PARAM_UNKNOWN` |
| No value and no default | `PARAM_MISSING` |
| Name given twice | `PARAM_REPEATED` |
| Value not finite or out of range | `PARAM_OUT_OF_RANGE` |
| Setup without operations | `SETUP_NO_OPERATION` |
| A value of the wrong Python type | `VALUE_TYPE_INVALID` |
| Cancelled | `CANCELLED` (warning) |
| Invalid declaration, repeated declared name | `ValueError` (programming error) |

## Algorithms and design inputs

No algorithms. The data follow research 26's setup and operation header (D-052, D-078) and research 19's split of definitions from their placed copies (Project Spike `research/19-software-design.md`, Tools, Operations, Setups): parameters declared once drive the UI, the API and storage.

| Element | Public source, or own design with date |
| --- | --- |
| Measurement points k, a, r | D-154, D-155; research 26, Structure |
| Setup fields, work offset as an index | D-078; research 26, Structure and trap 13; research 27, Datum row |
| Operation header fields used by the slice | research 26, The subset plan 0007 uses; D-052 |
| Parameter declarations | D-018, D-049; docs/dev/03, strategy interface; the declaration form ours, 2026-10-25 |
| Check order, locations, codes | ours, 2026-10-25 |

## Example parts

- Plan 0007's job: tool T1, a flat end mill D 10 with 30 mm of flute, measured at the tip; for the rectangle of research 22 test 1 drawn from (0, 0) to (100, 60), the stock from (−5, −5, −20) to (105, 65, 0), 5 mm on every side, top at z 0; work offset 1; one operation `PROFILE_1`, strategy `profile`, 8000 1/min, tol 0.01, allowance 0, z_top 0, z_bottom −10, step-down 4, cut feed 1200, plunge feed 300. `check_job` returns it with no diagnostic.
- The same job with the feeds left out: `PARAM_MISSING` twice, no value.
- An operation named `Profile 1` (with a space): `OP_NAME_INVALID`; on the Siemens file a space in a name gives `CMP501` (research 26, checked condition 2).
- A tool entered with its radius in the diameter field: not caught here (both are valid sizes); the setup sheet and Peter's dry run catch it (plan 0007, step 8).

## Test plan

- Unit (`tests/model/unit/`): one test per requirement, tagged with its ID; the example parts above.
- Property (`tests/model/property/`): generated jobs, valid and with one field broken at a time: a value comes back only when no error is reported; every broken field gives its code once, at its location; idempotence; the diagnostic order (REQ-MDL-024 to 026).
- Golden cases: none. Differential: none.

## Performance budget

None: a job holds a handful of tools and operations.

## Size estimate

Estimated about 220 NLOC; implemented at 344 NLOC of Python (the types and the declaration 90, `check_job` 230, the public list 24) and about 470 lines of tests. `check_job` came to twice its estimate for the per-field type checks and skips of REQ-MDL-029, the exact order of REQ-MDL-026 and the locations of REQ-MDL-027; the `simplifier` judged the size intrinsic (AQ-004). Module budget: 360 (Peter, AQ-004; was 260, AQ-003).

## Open questions

None open. Peter's answers of 2026-10-25 (`docs/agents/QUESTIONS.md`; plan 0007, Decisions):

- AQ-002: SPEC approved. The drawing's frame is the work frame (DEC-MDL-002); spindle CW and coolant on without fields (DEC-MDL-006); the declarations live in model, numbers only (DEC-MDL-001). Item 3 changed: a is any value ≥ 0 (D-154), above the flute length with a warning naming the shift of every Z (REQ-MDL-006, DEC-MDL-004).
- AQ-003: budget 260 and research 26, 22, 27, 10, 23 in `architecture/modules.yaml`.

Box 2 choices are in `src/splintercam/model/DECISIONS.md`.

## Change log

- 2026-10-25: drafted for plan 0007, step 3, from research 26, 22, 27 and 10 and D-154, D-155, D-018, D-049. Revised after the spec review the same day: Python types checked (REQ-MDL-029), a setup without operations refused, parameters as pairs, a dimensionless unit for the air gap, dependent checks skipped, cancellation and the declaration errors made exact.
- 2026-10-25: Reviewed (Peter, AQ-002 and AQ-003): REQ-MDL-006 changed to any a ≥ 0 with `TOOL_POINT_ABOVE_FLUTE` (warning) above the flute length; budget 260.
- 2026-10-25: implemented (plan 0007 step 3); "Verified by" names the tests; size estimate replaced by the measured 344 NLOC, budget 360 (Peter, AQ-004). Locations REQ-MDL-027 does not name (containers and elements of the wrong type) are in DEC-MDL-009; no requirement changed.

[r10]: ../../../docs/research/10-linking.md
[r22]: ../../../docs/research/22-2d-operations.md
[r26]: ../../../docs/research/26-toolpath-record.md
[r27]: ../../../docs/research/27-machines-and-controllers.md

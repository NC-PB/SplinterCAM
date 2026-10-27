# SPEC: strategies/profile

<!-- The outside profile of one closed contour. Drafted on 2026-10-27 for plan 0007, step 5, cut to the slice (D-160):
     the centre path from offset2d's GROW, equal depth passes, a start point and approach point of our own, climb,
     the links of toolpath. Inside profiles, open chains, leads, tabs, conventional milling, arc fitting and finishing
     passes come with later plans. -->

| | |
| --- | --- |
| Status | Reviewed (2026-10-27, Peter: AQ-015 to AQ-017 in `docs/agents/questions/`, all as recommended; the typed input `ProfileInput` the pattern for every strategy, AQ-014; plan 0007, Decisions). Choices marked "(ours)" are in `src/splintercam/strategies/profile/DECISIONS.md` and stand as the contract; the readings of research 22's wording in DEC-PRF-001 to 004 stay provisional until RR-007 answers (the behaviour is Peter's, AQ-016) |
| Layer | 3 (see architecture/modules.yaml) |
| Depends on | foundation (`Context`, `Result`, `Diagnostic`, `Severity`, `CANCELLED`); geometry2d (`CurveRows`, `PolygonRegion`, `RegionKind`, `row_boxes`, `orient2d`); offset2d (`offset_region`, `SourceClasses`, `EdgeClass`; added to `depends_on`, AQ-017); model (`FlatEndMill`, `StockBox`, `Operation`, `ParameterDeclaration`, `Unit`); cl (`ClHeader`, `ClOperation`, `Role`, by `src/splintercam/cl/SPEC.md`, Reviewed); toolpath (`link_heights`, `LevelPass`, `LinkPlan`, `link_operation`, by `src/splintercam/toolpath/SPEC.md`, Reviewed) |
| Research | [22][r22], Scope, Method, Parameters, Traps, Tests (the outside profile of plan 0007); [02][r02], the band of `offset_region` (through `src/splintercam/offset2d/SPEC.md`, REQ-OFF-020, 025, 038); [10][r10], Method (the links, through toolpath) |
| Decisions | D-023 (arcs by arc fitting, not in plan 0007), D-024 and D-154 (the path is the tool centre at the tip), D-025 (n and vf by hand), D-049 (declared parameters), D-079 (air gap 0.2·R), D-150 (allowance, t = R + s > 0), D-055 (determinism); text in [docs/spike/decisions-snapshot.md](../../../docs/spike/decisions-snapshot.md) |
| Owner | Peter Burgener |

## Purpose

Plans one outside profile: the tool centre path round one closed contour of material at the side allowance, in equal depth passes, climb milling, starting and ending at an approach point beside the stock, as one operation of the toolpath record. It checks the values that need the part, the tool and the stock together, which `model` cannot (model SPEC, Scope). Its user in plan 0007 is `job` (step 7); its output goes to `ncx` (step 6) through `cl`.

## Scope

- In: one closed loop of material from `io` (research 21); a flat end mill of radius R measured at one point; a box stock; research 22's parameters (side allowance s, z_top, z_bottom, largest step-down, cutting and plunge feed, air gap); research 22, Method 1 to 6; its traps 1 to 3 and tests 1 to 5.
- Out, handled elsewhere: the links, heights and their checks (`toolpath`); the record's rules (`cl`); the values `model` checks (types, ranges, feeds > 0, tol; REQ-MDL-015 to 029); building the `Context` for the operation's tol (`job`, step 7).
- Later (one line each, no work): G2/G3 from arc fitting (D-023; plan 0007, Out: the moves are lines); inside profiles, open chains (research 02, Open chains), several loops and islands; conventional milling; leads, tabs, ramps; a start point the user picks, and a second candidate when the first approach is blocked; finishing passes and a floor allowance (D-150); control compensation (D-024); cuts below the stock bottom onto a spoil board; source IDs in the record (cl, Later).
- Non-goals: links of its own (toolpath's); controller knowledge (D-021, D-148); shifting geometry toward a tolerance (D-150).

## Public interface

Lengths in mm, feeds in mm/min, float64 (D-028). All names are proposals (ours). No kernel: the loop's points are handled with vectorised NumPy and geometry2d's vectorised predicates; Python loops run over passes only (split rule; DEC-PRF-006).

```python
from dataclasses import dataclass
from splintercam.cl import ClOperation
from splintercam.foundation import Context, Result
from splintercam.geometry2d import CurveRows
from splintercam.model import FlatEndMill, Operation, ParameterDeclaration, StockBox

STRATEGY_ID = "profile"
DECLARATIONS: tuple[ParameterDeclaration, ...]   # REQ-PRF-001, in this order

@dataclass(frozen=True, slots=True)
class ProfileInput:
    contour: CurveRows        # one closed loop of material (io's `DxfContour.loop`)
    tool: FlatEndMill         # the operation's tool
    stock: StockBox
    operation: Operation      # returned by model's check_job: every declared parameter present

def plan_profile(task: ProfileInput, ctx: Context) -> Result[ClOperation]: ...
```

- Preconditions (programming errors, `ValueError`, DEC-PRF-005): `operation.strategy` is `STRATEGY_ID`; `operation.parameters` holds exactly the declared names in declaration order (REQ-MDL-024); `tool.number` is the operation's tool number and has its point; `contour` has one loop; `ctx.tolerances` is `ToleranceSet.for_operation(operation.tol_mm)`, so offset2d's a = 0.05·tol is the operation's.
- Expected outcomes are diagnostics (errors, no value): REQ-PRF-003 to 010, 015. offset2d's diagnostics are passed on (REQ-PRF-010).
- Terms: t = R + s; g = air gap ratio · R; a and u as offset2d's (a = max(0.05·tol, 2u)); "the band" is offset2d's [t, t + a + 6u] from the flattened contour, [t, t + a + 6u + t_flat] from the true lines and arcs (`src/splintercam/offset2d/SPEC.md`, before REQ-OFF-020). "Line row": a source ID whose rows in the contour are all lines (sweep 0).

## Requirements

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-PRF-001 | THE profile strategy SHALL declare, in this order: `allowance_mm` (mm, default 0, (−∞, ∞); D-150), `z_top_mm` (mm, no default, (−∞, ∞); research 22, Scope; no default, since research 22 gives none and 0 is the stock top only by chance, ours), `z_bottom_mm` (mm, no default, (−∞, ∞)), `stepdown_mm` (mm, no default, [0.01, ∞); the glossary's `stepdown`; the low end Peter's, AQ-030 (a)), `cut_feed_mm_per_min` and `plunge_feed_mm_per_min` (mm/min, no default, (0, ∞); D-025), `air_gap_ratio` (1, default 0.2, (0, 2]; D-079; the high end Peter's, AQ-031 (a)), each with its source (research 22, Parameters; D-049). | unit (`tests/strategies/profile/unit/test_profile_checks.py`): `test_the_declarations_in_order_with_units_defaults_and_ranges`, `test_check_job_accepts_the_example_job_with_the_declarations` (the air gap ratio completed to 0.2), `test_check_job_holds_the_step_down_and_air_gap_ranges` (0.01 and 2 accepted, 0.009 and 2.001 `PARAM_OUT_OF_RANGE`) | Reviewed |
| REQ-PRF-002 | IF a precondition of the interface does not hold, THEN `plan_profile` SHALL raise `ValueError` naming it (DEC-PRF-005). | unit (`tests/strategies/profile/unit/test_profile_checks.py`): `test_a_broken_precondition_raises_naming_it` (strategy, a missing and a swapped parameter, the point, the tool number, two loops, another tol) | Reviewed |
| REQ-PRF-003 | IF s is not above −R, THEN `plan_profile` SHALL report `PROFILE_ALLOWANCE` (error) naming s and −R (D-150; research 22, test 3). | unit: `test_research_22_test_3_an_allowance_of_minus_r_is_refused` (`tests/strategies/profile/unit/test_profile_checks.py`; s = −4.9 accepted), `test_research_22_test_3_an_allowance_of_minus_4_9_gives_a_loop_at_0_1` (`tests/strategies/profile/unit/test_profile_path.py`, the band at t = 0.1) | Reviewed |
| REQ-PRF-004 | IF z_bottom is not below z_top, THEN `plan_profile` SHALL report `PROFILE_DEPTH_INVALID` (error) naming both (research 22, trap 3: an input error, not an empty operation). | unit (`tests/strategies/profile/unit/test_profile_checks.py`): `test_a_bottom_not_below_the_top_is_refused` (equal and reversed; no `PROFILE_TOP_TOO_HIGH` after it) | Reviewed |
| REQ-PRF-005 | IF h_r from `link_heights` is not below its h_c (a stock top so large that the 2 mm vanish in rounding), or the first level z_1 (REQ-PRF-016) is not below h_r, THEN `plan_profile` SHALL report `PROFILE_TOP_TOO_HIGH` (error) naming z_1 and h_r (toolpath's REQ-TP-001 and 010: every descent goes down from h_r). WHERE z_top lies below the stock top, IF the stock top − z_1 exceeds a_p,max + eps_len, THEN it SHALL report `PROFILE_FIRST_PASS_DEEP` (error) naming the depth of the first pass (Peter, AQ-016, item 3 (a): without a stock model the material above z_top may still be there, so the first pass would cut more than the step-down). Levels above the stock top are accepted and cut air. | unit (`tests/strategies/profile/unit/test_profile_checks.py`): `test_a_first_level_at_h_r_is_refused`, `test_a_stock_top_where_h_r_rounds_to_h_c_is_refused` (1e16), `test_a_first_pass_deeper_than_the_step_down_below_the_stock_top_is_refused` (1.5 mm), `test_a_first_pass_of_the_step_down_below_the_stock_top_is_accepted_and_eps_more_not`, `test_a_top_above_the_stock_top_is_accepted` | Reviewed |
| REQ-PRF-006 | IF z_bottom lies below the stock bottom, THEN `plan_profile` SHALL report `PROFILE_BELOW_STOCK` (error) naming both (Peter, AQ-016, item 5 (a): below the stock is the table or the vice; plan 0007 models no fixtures, research 10, trap 1). | unit (`tests/strategies/profile/unit/test_profile_checks.py`): `test_a_bottom_below_the_stock_bottom_is_refused` (bottom − 0.001 refused, = bottom accepted) | Reviewed |
| REQ-PRF-007 | IF the stock top minus z_bottom exceeds the tool's flute length, THEN `plan_profile` SHALL report `PROFILE_TOO_DEEP` (error) naming the depth and the flute length (research 22, Method 3 and test 4; the depth from the stock top, not from z_top, DEC-PRF-004, Peter, AQ-016, item 2). | unit (`tests/strategies/profile/unit/test_profile_checks.py`): `test_research_22_test_4_deeper_than_the_flute_length_is_refused` (30.001 refused, 30 accepted), `test_the_depth_is_measured_from_the_stock_top_not_from_z_top` | Reviewed |
| REQ-PRF-008 | IF the step-down exceeds the tool's flute length, or lies below 0.01 mm, or (z_top − z_bottom) / a_p,max is not finite, THEN `plan_profile` SHALL report `PROFILE_STEP_DOWN` (error), one diagnostic naming the first of the three (research 22, Parameters: at most the flute length; Peter, AQ-030 (a): the smallest step-down 0.01 mm, and a pass count that is not finite refused by the same check). | unit (`tests/strategies/profile/unit/test_profile_checks.py`): `test_a_step_down_above_the_flute_length_is_refused` (30 accepted, 30.001 refused), `test_a_step_down_below_a_hundredth_is_refused` (0.01 accepted, 0.009 refused), `test_a_pass_count_that_is_not_finite_is_refused_and_does_not_raise` (z_top 1e308, z_bottom −1e308) | Reviewed |
| REQ-PRF-009 | IF the contour's bounding box in XY does not lie inside the stock box's XY extent, ends included, THEN `plan_profile` SHALL report `PROFILE_STOCK_SMALL` (error) naming the side (research 22, Method 5 relies on the stock box containing the part; model SPEC, Scope). IF g is not above eps_len, THEN it SHALL report `PROFILE_AIR_GAP` (error) naming g (ours: a gap below eps_len is none, and P would end within rounding of R off the stock, which REQ-TP-012 refuses; DEC-PRF-003). | unit (`tests/strategies/profile/unit/test_profile_checks.py`): `test_a_part_past_a_side_of_the_stock_is_refused` (each side, 0.001 mm), `test_a_part_touching_the_stock_is_accepted`, `test_an_arc_past_the_stock_is_refused_by_its_extent_not_its_ends`, `test_an_air_gap_not_above_eps_len_is_refused` (g = eps_len refused, 2·eps_len accepted) | Reviewed |
| REQ-PRF-010 | THE centre path SHALL be `offset_region(contour, MATERIAL, t, classes)` with every source ID of the contour of class MATERIAL, its diagnostics passed on in order. WHEN it returns no value, `plan_profile` SHALL return no value with offset2d's diagnostics and add none (`CANCELLED`, `LOOPS_CROSS`, `REGION_TOO_LARGE` stay as offset2d gives them); IF it returns a value that is not exactly one loop, THEN `plan_profile` SHALL report `PROFILE_REGION` (error) naming the loop count (research 22, Method 1; offset2d REQ-OFF-020, 040, 041). | unit (`tests/strategies/profile/unit/test_profile_checks.py`): `test_research_22_test_1_gives_one_loop`, `test_a_c_shape_closing_round_a_hole_is_refused_with_its_loop_count` (count 2), `test_offset2d_without_a_value_gives_its_diagnostics_alone`, `test_offset2ds_diagnostics_come_first_with_a_value_and_before_profile_region`, `test_offset2d_cancelled_gives_cancelled_alone` | Reviewed |
| REQ-PRF-011 | THE cut moves SHALL be the loop's edges as LINE moves (D-023: arcs come by arc fitting, out of plan 0007), so every cut point lies in the band, at least t from the true contour (research 22, Method 1 and test 2; offset2d REQ-OFF-025; reading of test 1's "arcs of radius 10", DEC-PRF-001). | unit (`tests/strategies/profile/unit/test_profile_path.py`): `test_research_22_test_1_the_sides_are_edges_offset_by_5_and_the_fillets_in_the_band`, `test_research_22_test_2_an_allowance_of_half_a_millimetre` (exact edge distance from the true contour; vertices and midpoints in [5.5, 5.5 + a + 6u] from the flattened one), `test_research_22_test_5_a_circle_starts_at_its_smallest_vertex`; property (`tests/strategies/profile/property/test_profile_properties.py`): `test_the_profile_of_a_random_part` (rounded boxes and stars of lines exact; stars of bulged rows at vertices and midpoints with `tests/support/offset2d_oracles.py`, DEC-PRF-008) | Reviewed |
| REQ-PRF-012 | THE loop SHALL run clockwise (climb with the spindle CW, material on the right; research 22, Method 2), each edge keeping its source ID when the CCW loop from offset2d is reversed (trap 2). | unit (`tests/strategies/profile/unit/test_profile_path.py`): the signed area in `test_research_22_test_1_the_sides_are_edges_offset_by_5_and_the_fillets_in_the_band`; `test_research_22_test_1_starts_at_the_middle_of_the_first_longest_side` (S on a long side, then on to the side's CCW start); `test_a_clockwise_loop_from_offset2d_raises` (`tests/strategies/profile/unit/test_profile_checks.py`, DEC-PRF-007 (6)); property: `test_the_profile_of_a_random_part` | Reviewed |
| REQ-PRF-013 | THE start point S SHALL be the midpoint of the loop's longest edge whose source ID is a line row, lengths compared as squared lengths dx·dx + dy·dy, the first such edge in offset2d's CCW order (before the reversal, from its smallest point, REQ-OFF-038) on a tie; WHERE no edge has a line row's ID, S SHALL be the loop's first vertex, offset2d's smallest point. The loop SHALL start and end at S (research 22, Method 4; DEC-PRF-002). | unit (`tests/strategies/profile/unit/test_profile_path.py`): `test_research_22_test_1_starts_at_the_middle_of_the_first_longest_side`, `test_research_22_test_5_a_circle_starts_at_its_smallest_vertex`, `test_a_tie_of_two_equal_sides_takes_the_first_in_offset2ds_order` | Reviewed |
| REQ-PRF-014 | THE approach point P SHALL be S + d·n, n the unit outward normal at S (of S's edge; at a vertex, the normalised sum of the two edges' unit outward normals), d the smallest d ≥ 0 at which P's distance in XY from the stock box is at least R + g, computed in closed form with `sqrt` only; a side whose normal component is 0 is skipped, not divided by (research 22, Method 5; D-079; DEC-PRF-003). WHERE d is 0, P is S (ours). | unit (`tests/strategies/profile/unit/test_profile_path.py`): `test_research_22_test_1_p_lies_6_mm_off_the_stock_along_the_axis`, `test_an_axis_normal_and_a_start_already_clear`, `test_p_off_a_box_corner_lies_on_the_corners_circle`; property (`tests/strategies/profile/property/test_profile_properties.py`): `test_the_approach_point_is_the_nearest_clear_point_on_the_ray` (random S and n, axis-parallel included), `test_the_profile_of_a_random_part` | Reviewed |
| REQ-PRF-015 | IF the segment from S to P touches or crosses an edge of the loop other than the two that meet at S (orient2d, exact), THEN `plan_profile` SHALL take S as the loop's smallest vertex instead, as in REQ-PRF-013, and P from it by REQ-PRF-014; IF that segment is blocked too, THEN it SHALL report `PROFILE_APPROACH_BLOCKED` (error) naming S (ours, DEC-PRF-003: on a non-convex part the normal can pass over the part, and the approach at depth would cut it; the smallest vertex's ray runs where the loop has no point, so the error guards a bug). | unit (`tests/strategies/profile/unit/test_profile_path.py`): `test_a_u_whose_inner_side_is_longest_starts_at_its_smallest_vertex`; `test_an_approach_blocked_at_both_candidates_is_refused_naming_s` (`tests/strategies/profile/unit/test_profile_checks.py`, the blocked check forced); test 1 keeps the long side in `test_research_22_test_1_starts_at_the_middle_of_the_first_longest_side`; property: `test_the_profile_of_a_random_part` (random U parts start at the smallest vertex; on every part the segment P → S at least t from the contour) | Reviewed |
| REQ-PRF-016 | THE passes SHALL be n = ⌈(z_top − z_bottom) / a_p,max⌉ of equal depth Δ = (z_top − z_bottom) / n at z_i = z_top − i·Δ, i = 1 … n, with z_n = z_bottom exactly; WHERE n > 1 and (n − 1)·a_p,max ≥ z_top − z_bottom − eps_len, n is reduced by one (research 22, Method 3; ours, DEC-PRF-004: a quotient one ulp over an integer gives no extra pass). | unit (`tests/strategies/profile/unit/test_profile_path.py`): `test_equal_depth_passes` (test 1's levels; 0.1 to −0.2 by 0.1 gives 3; depth = step and 5e-7 give 1), `test_research_22_test_1_cuts_three_passes`; property: `test_the_profile_of_a_random_part` | Reviewed |
| REQ-PRF-017 | THE pass at z_i SHALL be: WHERE d > 0, P → S, LINE, role APPROACH, plunge feed; the loop from S to S, role CUT, cutting feed; WHERE d > 0, S → P, LINE, role RETRACT, cutting feed (research 22, Method 6 and trap 1). | unit (`tests/strategies/profile/unit/test_profile_path.py`): `test_research_22_test_1s_pass_roles_and_feed_classes`, `test_a_start_already_clear_gives_the_loop_alone` (s = 2, stock flush); property: `test_the_profile_of_a_random_part` | Reviewed |
| REQ-PRF-018 | THE header SHALL hold the operation's name, an empty note (AQ-008 (b)), the tool number, the point's k and a, the spindle speed, tol, the feed classes (`cut`, cutting feed) and (`plunge`, plunge feed) in that order, and h_c and h_r from `link_heights` as the clearance and retract heights (research 26 subset; `cl` REQ-CL-002, and `retract_height_mm` for REQ-CL-022). | unit (`tests/strategies/profile/unit/test_profile_path.py`): `test_the_header_of_the_example_job` (`PROFILE_1`, (), 1, 1, 0, 8000, 0.01, (("cut", 1200), ("plunge", 300)), 5, 3) | Reviewed |
| REQ-PRF-019 | WHEN no error is found, THE `plan_profile` function SHALL return the record of `link_operation` for P, the tool, the plunge class and the passes in order, with offset2d's warnings (research 10 through toolpath). | unit (`tests/strategies/profile/unit/test_profile_path.py`): `test_research_10_test_1_on_research_22_test_1s_record` (accepted by `make_operation` again; no RAPID in the plane below h_c; below h_r only the passes and the descents at P; passes in order); offset2d's warnings with the value in `test_offset2ds_diagnostics_come_first_with_a_value_and_before_profile_region` (`tests/strategies/profile/unit/test_profile_checks.py`) | Reviewed |
| REQ-PRF-020 | THE `plan_profile` function SHALL check the values first, REQ-PRF-003 to 009 in that order (REQ-PRF-005 skipped when REQ-PRF-004 fails or the pass count of REQ-PRF-008 is not finite, since there are no levels), report every one that fails with the operation as location (`operation (<name>)`, DEC-PRF-005), and then stop before the offset. After the offset it SHALL stop at the first of REQ-PRF-010 and 015 that fails, after offset2d's diagnostics (ours, D-055; as model's REQ-MDL-025). | unit (`tests/strategies/profile/unit/test_profile_checks.py`): `test_every_value_error_is_reported_in_order_and_no_offset_runs`, `test_six_failing_value_checks_report_in_requirement_order`, `test_a_pass_count_that_is_not_finite_is_refused_and_does_not_raise` | Reviewed |
| REQ-PRF-021 | WHEN `ctx.cancel` is set at entry or after the offset, THE `plan_profile` function SHALL return no value and `CANCELLED` alone (REQ-FND-013). | unit (`tests/strategies/profile/unit/test_profile_checks.py`): `test_cancelled_at_entry_gives_cancelled_alone_without_the_offset`, `test_offset2d_cancelled_gives_cancelled_alone`, `test_cancelled_after_the_offset_gives_cancelled_alone` (offset2d calls no progress callback, so the tests cancel from a patched offset) | Reviewed |
| REQ-PRF-022 | THE `plan_profile` function SHALL decide the same on every platform: comparisons, sums, products, `sqrt` and geometry2d's exact predicates, no trigonometry; two runs give the same record bit for bit (D-055). | review; unit (`tests/strategies/profile/unit/test_profile_path.py`): `test_research_22_test_1_twice_bit_for_bit`; property: `test_the_profile_of_a_random_part` (twice) | Reviewed |

## Invariants

- Every cut move lies at least t from the true contour and within the band (REQ-PRF-011). Property test.
- The record runs clockwise round the part from S to S on every pass, all passes at the same S and P, every z_i between z_bottom and z_top, no pass deeper than a_p,max + eps_len (REQ-PRF-012 to 017). Property test.
- P lies outside the stock box by at least R + g up to rounding, and the approach S → P crosses no other part of the loop (REQ-PRF-014, 015), so toolpath's REQ-TP-012 holds for every plan the profile builds. Property test.

## Tolerance budget

The whole chord share goes to offset2d (a = 0.05·tol for the flattening and ArcTolerance; offset2d's SPEC, Tolerance budget); the profile spends none. eps_len is read for REQ-PRF-005, 009 and 016 (and REQ-PRF-014's property test).

## Failure modes and diagnostics

| Situation | Result | Diagnostic |
| --- | --- | --- |
| s ≤ −R | no value | `PROFILE_ALLOWANCE` |
| z_bottom ≥ z_top | no value | `PROFILE_DEPTH_INVALID` |
| first level not below h_r, or h_r not below h_c | no value | `PROFILE_TOP_TOO_HIGH` |
| first pass deeper than the step-down below the stock top | no value | `PROFILE_FIRST_PASS_DEEP` |
| z_bottom below the stock bottom | no value | `PROFILE_BELOW_STOCK` |
| stock top − z_bottom > flute length | no value | `PROFILE_TOO_DEEP` |
| step-down > flute length, < 0.01 mm, or no finite pass count | no value | `PROFILE_STEP_DOWN` |
| contour outside the stock in XY | no value | `PROFILE_STOCK_SMALL` |
| air gap not above eps_len | no value | `PROFILE_AIR_GAP` |
| offset gives no value | no value | offset2d's diagnostics alone |
| offset not exactly one loop | no value | `PROFILE_REGION`, after offset2d's own |
| approach crosses the loop at both candidates | no value | `PROFILE_APPROACH_BLOCKED` |
| cancelled | no value | `CANCELLED` |
| precondition broken | raises | `ValueError` (programming error) |
| offset2d's loop not CCW (its promise broken) | raises | `ValueError` (DEC-PRF-007 (6)) |

## Algorithms and design inputs

Clean room (D-144): no implementation details of other CAM systems went in.

| Element of the method | Public source, or own design with date |
| --- | --- |
| Centre path by GROW of the material region by R + s | research 22, Method 1; research 02 (Held, Def. 7.1, through offset2d) |
| Clockwise for climb | research 22, Method 2 (the usual definition of down-milling) |
| Equal depth passes | research 22, Method 3 (ours there); the integer guard ours, 2026-10-27 |
| Start point, approach point | research 22, Method 4 and 5 (ours there); D-079; the vertex normal, closed form and blocked check ours, 2026-10-27 |
| Approach at the plunge feed, retract at the cutting feed | research 22, Method 6 and trap 1 |
| Lines, no arcs | D-023; plan 0007, Out |

## Example parts

- Research 22 test 1: rectangle 100 × 60 from (0, 0), fillets R 5, D 10 with 30 mm of flute, stock (−5, −5, −20) to (105, 65, 0), s = 0, z_top 0, z_bottom −10, step-down 4, feeds 1200 and 300: three passes; S the midpoint of a long side (y = −5 or 65, by offset2d's order); P's centre at least 6 mm (R + 0.2·R) off the stock's side; the loop clockwise, its fillets flattened within the band.
- Test 5: a circle of radius 20: S at the smallest vertex, n along the vertex normal (about −x), one polygonal circle of radius 20 + R per pass.
- An L-shaped plate: the longest side is outside, the normal is free: accepted. A U-shaped part whose inner side is the longest: the normal would cross the U's other arm, so S moves to the smallest vertex (REQ-PRF-015).
- Stock 0.5 mm above z_top (a facing allowance left on), step-down 1: `PROFILE_FIRST_PASS_DEEP`; the user sets z_top to the stock top (AQ-016, item 3 (a)).
- A through cut with z_bottom 0.5 mm below the stock bottom: `PROFILE_BELOW_STOCK`; a spoil board comes with a later fixture model (AQ-016, item 5 (a)).

## Test plan

- Unit (`tests/strategies/profile/unit/`): one or more tests per requirement, tagged with its ID; research 22 tests 1 to 5; the example parts.
- Property (`tests/strategies/profile/property/`): random contours of lines and arcs inside random stock boxes (convex and non-convex, with offset2d's generators): every cut point in the band from the true contour (oracle `tests/support/offset2d_oracles.py`), clockwise, P clear of the stock, the record accepted by `make_operation`, bit for bit twice.
- Golden cases: `profile-rectangle-fillets` comes with step 7 (plan 0007). Differential: none.

## Performance budget

Research 22 test 1 in under 50 ms on the reference machine, offset included (ours). Not checked by a test in this slice.

## Size estimate

First count about 265 NLOC of Python (declarations 18, input type 8, reading parameters 10, the nine value checks with diagnostics 48, offset call, classes and loop check 18, reversal 6, start point 22, normal 10, approach point in closed form 28, blocked check with its fallback 17, pass count 10, pass rows 18, header 12, the entry 20, rounded up); by Peter's rule of 2026-10-25 about 1.5 times that: **about 400 NLOC**, and about 480 lines of tests. With toolpath's 165, step 5 comes to about 565 NLOC against the plan's 250 (375 by the rule): about 51 % over, just past the 50 % stop; Peter accepted the sizes (AQ-017). Module budget 400 in `architecture/modules.yaml` (Peter, AQ-017).

## Open questions

None for Peter. His answers of 2026-10-27 (`docs/agents/questions/`; plan 0007, Decisions):

- AQ-016: SPEC approved, all as recommended: fillets as G1 lines (item 1 (a)); the depth from the stock top (2); a first pass deeper than the step-down refused (3 (a)); S on the longest straight side, with the setup sheet of AQ-015 (4 (a)); cuts below the stock bottom refused (5 (a)); a step-down up to the flute length (6 (a)); straight approach and retract along the normal (7); the smallest-vertex fallback (8). The interface `plan_profile(task: ProfileInput, ctx: Context)` is the pattern for every strategy (AQ-014).
- AQ-017: budget 400, research 02, 22, 10 and offset2d in `depends_on` in `architecture/modules.yaml`.

Still open (box 3, not blocking): RR-007, research 22's tests 1, 2 and 5, Method 3 to 5 worded for a polygonal centre path; the readings in DEC-PRF-001 to 004 stand meanwhile.

## Change log

- 2026-10-27: drafted for plan 0007, step 5, from research 22 and 02 (through offset2d) and 10 (through toolpath). Revised after the spec and cnc reviews the same day: n never 0; offset2d's no-value diagnostics passed on alone; z_top without default, a first pass deeper than the step-down below the stock top refused, the refusal of z_top above the stock replaced by z_1 below h_r; a blocked approach falls back to the smallest vertex; `PROFILE_AIR_GAP` among the value checks; the tie order, the axis-parallel normal, the d = 0 pass and the property bound made exact.
- 2026-10-27: Reviewed (Peter, AQ-016 and AQ-017, all as recommended; AQ-014 for the typed input); budget 400.
- 2026-10-27: `cl`'s header gains `retract_height_mm` and REQ-CL-022 (pull request 85, AQ-018 (c)): REQ-PRF-018's header holds h_r as well.
- 2026-10-27: implemented (plan 0007, step 5); "Verified by" names the tests; the choices the SPEC left open in DEC-PRF-007, the tests' distance measures in DEC-PRF-008. RR-007 is answered: research 22 takes DEC-PRF-001 to 004 as its reading.
- 2026-10-27: Peter, AQ-030 (a) and AQ-031 (a): `stepdown_mm` declared [0.01, ∞), and REQ-PRF-008 refuses a step-down below 0.01 mm and a pass count that is not finite (REQ-PRF-005 skipped then, REQ-PRF-020); `air_gap_ratio` declared (0, 2], refused by model's `check_job` (REQ-PRF-001). DEC-PRF-010.

[r02]: ../../../../docs/research/02-offsets-and-booleans.md
[r10]: ../../../../docs/research/10-linking.md
[r22]: ../../../../docs/research/22-2d-operations.md

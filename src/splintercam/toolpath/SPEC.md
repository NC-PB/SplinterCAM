# SPEC: toolpath

<!-- The links between and around the passes of an operation. Drafted on 2026-10-27 for plan 0007, step 5, cut to the
     slice (D-160): one operation's links through the clearance height, every descent beside the stock, from
     research 10's subset. Per-link retract heights over stock layers, staying down, leads, link checks against
     fixtures, the arc fit of research 11 and the kernel come with later plans. -->

| | |
| --- | --- |
| Status | Reviewed (2026-10-27, Peter: AQ-015 to AQ-017 in `docs/agents/questions/`, all as recommended; plan 0007, Decisions). Choices marked "(ours)" are in `src/splintercam/toolpath/DECISIONS.md` and stand as the contract |
| Layer | 3 (see architecture/modules.yaml) |
| Depends on | foundation (`Context`); model (`StockBox`, `FlatEndMill`); cl (`ClHeader`, `ClMoves`, `ClOperation`, `MoveKind`, `Role`, `NO_FEED_CLASS`, `make_operation`, by `src/splintercam/cl/SPEC.md`, Reviewed) |
| Research | [10][r10], Method, Traps, Tests (the clearance-height links of plan 0007); [26][r26], Links and heights (what the record carries) |
| Decisions | D-062 (clearance 5 mm, retract 3 mm over the stock), D-087 (G0 only above the safe plane and along the axis), D-078 (no fixtures modelled in the slice), D-055 (determinism); Peter's answer to plan 0007, question 4; text in [docs/spike/decisions-snapshot.md](../../../docs/spike/decisions-snapshot.md) |
| Owner | Peter Burgener |

## Purpose

Turns a strategy's passes into one complete operation of the toolpath record: the rapid up after the tool change, the rapid over the approach point, the descent beside the stock to each pass, the retract to the clearance height between passes, all with their link heights (research 10, Method). The strategy plans only the moves in the plane at each level; toolpath owns the heights, so every strategy links the same way. Its user in plan 0007 is `strategies/profile` (step 5); its output goes to `cl`'s `make_operation`.

## Scope

- In: the clearance height h_c and the retract height h_r from the stock top (D-062); research 10's links for passes that all start and end at one approach point P: Method 1 to 5 in that order; the check of research 10 test 1 that the descent at P lies beside the stock box grown by R.
- Out, handled elsewhere: where P lies, the passes' levels and their moves in the plane (`strategies/profile`, research 22, Method 4 to 6); the feed values and the header fields other than the clearance height (the strategy); the record's own rules (`cl`, REQ-CL-005 to 017, applied by `make_operation`); fixtures and clamps (research 10, trap 1: the setup sheet and Peter's dry run, plan 0007 step 8; the setup sheet states the clamp and jaw limits, Peter, AQ-015, item 1 (a)).
- Later (one line each, no work): retract heights per link over the stock layers grown by R + 0.2R and staying down (D-062, research 10 in Project Spike); LINE links below h_r at a link feed (D-087); leads in and out; passes with different start points; link checks against fixtures and keep-out zones (D-078); h_c and h_r as job parameters; the arc fit of research 11 (D-023); a kernel for links over many passes.
- Non-goals: choosing P or the order of passes (the strategy's, research 22); any controller knowledge (D-021, D-148).

## Public interface

Lengths in mm, feeds as `cl` feed-class indexes, float64 (D-028). Coordinates are the tool centre at the tip in the work frame (D-154). All names are proposals (ours). No kernel: the moves of a pass are copied into the record's columns vectorised; Python loops run over passes only (split rule; DEC-TP-003).

```python
from collections.abc import Sequence
from dataclasses import dataclass
import numpy as np
from numpy.typing import NDArray
from splintercam.cl import ClHeader, ClOperation
from splintercam.foundation import Context
from splintercam.model import FlatEndMill, StockBox

CLEARANCE_ABOVE_STOCK_MM = 5.0   # D-062: clearance height over the stock top
RETRACT_ABOVE_STOCK_MM = 3.0     # D-062: retract height over the stock top

@dataclass(frozen=True, slots=True)
class LinkHeights:
    clearance_mm: float          # h_c = stock top + 5 (research 10, Method)
    retract_mm: float            # h_r = stock top + 3

def link_heights(stock: StockBox) -> LinkHeights: ...

@dataclass(frozen=True, slots=True, eq=False)
class LevelPass:                 # one pass in the plane at one level, from P back to P
    z_mm: float
    rows: NDArray[np.float64]    # (m, 7) curve rows [x0, y0, x1, y1, cx, cy, sweep], a line where sweep is 0
    role: NDArray[np.int8]       # (m,) cl Role: APPROACH, CUT or RETRACT
    feed_class: NDArray[np.int64]  # (m,) index into the header's feed classes

@dataclass(frozen=True, slots=True, eq=False)
class LinkPlan:
    approach_xy_mm: tuple[float, float]   # P (research 22, Method 5)
    tool: FlatEndMill                     # R = tool.radius_mm, for research 10 test 1's stock box grown by R
    plunge_feed_class: int                # the descent's feed class (research 10, Method 2)
    passes: tuple[LevelPass, ...]         # in cutting order

def link_operation(header: ClHeader, plan: LinkPlan, stock: StockBox, ctx: Context) -> ClOperation: ...
```

- `link_operation` is code called by a strategy after `model`'s `check_job` and the strategy's own checks: a broken plan is a programming error and raises `ValueError` naming the requirement and, where there is one, the pass's index from 0 (as `cl`, DEC-CL-002; DEC-TP-002). It returns what `make_operation` returns, so `cl`'s `ValueError` passes through unchanged. It does not poll `ctx.cancel` (short and vectorised, as `cl`).
- "Bit for bit" below means equal as float64 values, with +0.0 and −0.0 equal (ours: `cl` decides "changes x or y" the same way, DEC-CL-004).
- Move index of pass i, row j in the record (for reading a `ValueError` from `cl`): 2 + Σ_{k<i} (m_k + 3) + 2 + j, with m_k the rows of pass k.
- Preconditions not checked (the strategy's; types are pyright's): `passes` is a tuple of `LevelPass`, `approach_xy_mm` a pair of floats, `plunge_feed_class` an `int`, `tool` a `FlatEndMill` that `model`'s `check_job` accepted (R > 0 and finite, REQ-MDL-003).

## Requirements

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-TP-001 | THE `link_heights` function SHALL return h_c = stock top + `CLEARANCE_ABOVE_STOCK_MM` and h_r = stock top + `RETRACT_ABOVE_STOCK_MM`, from the stock box alone (D-062: "over stock or clamps"; research 10, trap 1: no clamps in plan 0007). IF the stock top is not finite, or the computed h_r is not below h_c (a stock top so large that the 2 mm vanish in rounding), THEN `link_operation` SHALL raise `ValueError` (ours; `link_heights` itself does not raise, so a strategy can report it as a diagnostic first, REQ-PRF-005). | unit: `test_link_heights_from_the_stock_top` (research 10 test 2, top 2 mm: 7 and 5; top 0: 5 and 3); `test_a_stock_top_without_two_heights_is_refused` (1e16, ∞, NaN) | Reviewed |
| REQ-TP-002 | THE `link_operation` function SHALL return the record of `make_operation` (`src/splintercam/cl/SPEC.md`) for these moves, in this order: RAPID to (NaN, NaN, h_c); RAPID to (P, h_c); per pass i: RAPID to (P, h_r), LINE to (P, z_i), the pass's rows at z_i, RAPID to (P, h_c) (research 10, Method 1 to 4; test 1). | unit: `test_research_22_test_1_gives_cls_profile_record` (all seven columns equal to cl's hand-written record), `test_research_22_test_1s_kinds_roles_and_ends`, `test_cls_refusal_passes_through_at_the_stated_move_index`; property: `test_valid_plans_give_the_pattern` | Reviewed |
| REQ-TP-003 | THE first move SHALL change Z alone, ending at h_c with x and y NaN, and the second SHALL move in the plane at h_c only (research 10, Method 1, trap 2: the position after the tool change differs per machine). | unit: `test_the_first_move_is_along_z_and_the_second_in_the_plane_at_h_c`; property: `test_valid_plans_give_the_pattern` | Reviewed |
| REQ-TP-004 | THE RAPID moves SHALL carry the link height h_c, except the descent to h_r at P, which SHALL carry h_r; every RAPID has role LINK and `NO_FEED_CLASS` (research 10, Method 5; research 26, Links and heights). | unit: `test_rapids_carry_h_c_but_the_descent_to_h_r`; property: `test_research_10_test_1s_invariants` | Reviewed |
| REQ-TP-005 | THE descent from h_r to z_i SHALL be a LINE at P with role APPROACH and the plan's plunge feed class (research 10, Method 2). | unit: `test_each_descent_is_a_line_at_the_plunge_feed_class` (plunge class 1 in research 22 test 1's plan), `test_the_plunge_class_beyond_the_header_is_cls_to_refuse`; property: `test_valid_plans_give_the_pattern` | Reviewed |
| REQ-TP-006 | THE pass's rows SHALL become LINE moves where the sweep equals 0 (−0.0 included) and ARC moves otherwise, each ending at (x1, y1, z_i), with the row's role and feed class, in the given order; an ARC takes the row's centre and sweep, a LINE gets the fill values centre (NaN, NaN) and sweep +0.0 whatever the row holds there, and every LINE and ARC the link height NaN (research 26, Move; D-057; `cl` REQ-CL-010, 013). | unit: `test_a_line_and_a_cw_arc_become_line_and_arc_moves`, `test_a_line_row_gets_the_fill_values_whatever_it_holds` (centre (0, 0), sweep −0.0), `test_a_whole_number_level_gives_float_columns`; property: `test_valid_plans_give_the_pattern` (line rows with junk centres and ±0.0 sweeps) | Reviewed |
| REQ-TP-007 | THE header's clearance height SHALL equal h_c and its retract height (`retract_height_mm`) h_r of REQ-TP-001, each bit for bit; IF either does not, THEN `link_operation` SHALL raise `ValueError` (D-062; `cl` REQ-CL-012 and REQ-CL-022 check the moves against the header's two heights: rapids in the plane at h_c, none ending below h_r). | unit: `test_header_heights_off_h_c_or_h_r_are_refused` (±0.001 on each), `test_header_heights_one_ulp_off_are_refused` | Reviewed |
| REQ-TP-008 | IF the plan has no pass, P is not finite, the plunge feed class is negative, or the plan's tool number (`plan.tool.number`) differs from the header's `tool_number`, checked in that order, THEN `link_operation` SHALL raise `ValueError` (ours; the class's upper bound is `cl`'s REQ-CL-009; the tool number: Peter, AQ-020 (a), so REQ-TP-012's R is the radius of the tool the machine loads). | unit: `test_a_broken_plan_field_is_refused` (one per field, the tool number T2 against the header's T1, and the order) | Reviewed |
| REQ-TP-009 | IF a pass's `rows`, `role` or `feed_class` is not a NumPy array of its dtype and shape, has no row, or its rows' lengths differ, or a role is not APPROACH, CUT or RETRACT, THEN `link_operation` SHALL raise `ValueError` naming the pass and the column (research 26 subset: LINK only on rapids, REQ-CL-005). | unit: `test_a_broken_column_names_the_pass_and_column` (rows float32, (m, 6), a list, masked; `role` one shorter, int64, 0-d; `feed_class` int32, (m, 1)), `test_an_empty_pass_is_refused`, `test_a_row_role_other_than_approach_cut_retract_is_refused` (LINK, 7); property: `test_one_field_broken_names_its_requirement_and_pass` | Reviewed |
| REQ-TP-010 | IF a pass's z_i is not finite, not below h_r, or below the stock bottom (`stock.min_mm[2]`; equal allowed), THEN `link_operation` SHALL raise `ValueError` naming the pass (research 10, Method 2: the descent goes down from h_r; the stock bottom: Peter, AQ-021 (a), a backstop for REQ-PRF-006, since below the stock is the vice or the table). | unit: `test_a_level_not_below_h_r_is_refused` (h_r, above, NaN, −∞), `test_a_level_one_ulp_below_h_r_passes`, `test_a_level_one_ulp_below_the_stock_bottom_is_refused`, `test_a_level_at_the_stock_bottom_passes`; property: `test_one_field_broken_names_its_requirement_and_pass` (at h_r, one ulp below the bottom) | Reviewed |
| REQ-TP-011 | IF, in this order, a pass's first row does not start at P bit for bit, a row does not start where the previous one ended bit for bit, or its last row does not end at P bit for bit, THEN `link_operation` SHALL raise `ValueError` naming the pass and the row (research 10, Method 3: every pass starts and ends at P; the record stores ends only, research 26, Move, so a gap would be lost). | unit: `test_a_pass_off_p_or_with_a_gap_by_one_ulp_is_refused` (each of the three, in x and in y), `test_a_profile_pass_ending_1e_9_from_p_is_refused`; property: `test_one_field_broken_names_its_requirement_and_pass` | Reviewed |
| REQ-TP-012 | IF P lies within R of the stock box in XY, THEN `link_operation` SHALL raise `ValueError` (research 10, Method 2: the tool descends beside the stock, never into it; test 1: no move below h_r inside the stock box grown by R but the pass and its approach and retract). The decision is the one float64 expression dx·dx + dy·dy ≤ R·R, with dx = max(x_min − px, 0, px − x_max) and dy likewise, evaluated in scalar Python floats in that order (rounded, not exact, but the same on every platform; ours: the grown box with round corners, touching counts as inside, DEC-TP-004). | unit, on dyadic coordinates so the boundary is exact: `test_a_descent_within_r_of_the_stock_box_is_refused` (at R from a side, dx = 3 and dy = 4 off a corner, inside, 2 mm off a side), `test_a_descent_just_beyond_r_of_the_stock_box_passes` (R + 2^-10 from three sides, dy = 4 + 2^-10 off the corner); property: `test_research_10_test_1s_invariants`, `test_one_field_broken_names_its_requirement_and_pass` | Reviewed |
| REQ-TP-013 | THE checks SHALL run rule by rule in this order: REQ-TP-001, 007, 008, 009, 010, 011 (each over all passes in order before the next rule), 012, then `make_operation`; the `ValueError` SHALL name the first rule broken by its ID and, for a pass rule, the first pass and row breaking it by index from 0 (ours, D-055, as `cl`'s REQ-CL-020; DEC-TP-002). | unit: `test_the_first_rule_broken_is_named_over_the_first_pass` (pass 0 breaking REQ-TP-011 and pass 1 breaking REQ-TP-009 names REQ-TP-009 and pass 1), `test_the_first_pass_and_row_breaking_a_rule_are_named`, `test_the_rules_run_in_order` (every neighbouring pair, and REQ-TP-012 before `make_operation`) | Reviewed |
| REQ-TP-014 | THE `link_operation` function SHALL decide the same on every platform: comparisons, sums and products in a fixed order only, no trigonometry, no floating-point NumPy reductions in a decision (`np.all` and `np.any` over comparisons are fine; D-055 tier 1). | review (spec-reviewer, 2026-10-27); unit: REQ-TP-012's boundary tests above | Reviewed |

## Invariants

- Every record `link_operation` returns satisfies research 10 test 1: the moves come in REQ-TP-002's order; no RAPID in the plane below h_c; no move below h_r within R of the stock box but the passes' rows and the descents at P; every RAPID at or above its link height (REQ-TP-002 to 006, 012; `cl` REQ-CL-011), every RAPID in the plane at h_c and none ending below h_r (`cl` REQ-CL-022, which `make_operation` checks again). Property test over random valid plans: these hold, and `make_operation` accepts the moves.
- toolpath adds no moves in the plane below h_c: every move between the passes is along Z at P (Peter's answer to plan 0007, question 4).

## Tolerance budget

None spent; nothing is computed but copies, the two heights and the comparisons above. The heights are rounded sums, the same on every platform, and REQ-TP-007 compares against the same computed value; the comparisons are exact (bit for bit) except REQ-TP-012's rounded distance test, which is fixed in its order so it decides the same everywhere (DEC-TP-004).

## Failure modes and diagnostics

No diagnostics: every rule broken is a programming error in the strategy and raises `ValueError` (DEC-TP-002). User values (stock, depths, feeds) are checked by `model` and the strategy before a plan exists.

## Algorithms and design inputs

No algorithms beyond research 10's order of links.

| Element | Public source, or own design with date |
| --- | --- |
| h_c = stock top + 5, h_r = stock top + 3 | D-062; research 10, Method |
| Link order: Z first, over P at h_c, down to h_r, feed down at P, up to h_c between passes | research 10, Method 1 to 4; Peter's answer to plan 0007, question 4 |
| Link heights on rapids | research 10, Method 5; research 26, Links and heights |
| Passes as curve rows at a level; `ValueError` for a broken plan; the grown box with round corners | ours, 2026-10-27 (DEC-TP-001, 002, 004) |

## Example parts

- Research 22 test 1 (rectangle 100 × 60, fillets R 5, tool R 5, stock top 0, three passes): RAPID Z 5 (link 5), RAPID to P at 5 (link 5); per pass RAPID Z 3 (link 3), LINE Z z_i APPROACH plunge, the pass's rows, RAPID Z 5 (link 5); 2 + 3·(m + 3) moves. Accepted by `make_operation`.
- The same with P 2 mm off the stock's side (inside the box grown by R = 5): refused (REQ-TP-012).
- A pass whose last row ends 1e-9 mm from P: refused (REQ-TP-011).

## Test plan

- Unit (`tests/toolpath/unit/`): one or more tests per requirement, tagged with its ID; the example parts.
- Property (`tests/toolpath/property/`): random valid plans (P outside the box grown by R, random closed passes of lines and consistent arcs at random levels below h_r) give the pattern of REQ-TP-002 and pass `make_operation`; one field broken at a time raises naming its requirement.
- Golden cases: none in this module (the slice's `profile-rectangle-fillets` comes with step 7). Differential: none.

## Performance budget

`link_operation` on 100 passes of 1000 rows under 20 ms on the reference machine, `make_operation`'s own time (50 ms per 100 000 moves, `src/splintercam/cl/SPEC.md`) not counted (ours; plan 0007 has three passes of about 50 rows). Not checked by a test in this slice.

## Size estimate

First count about 110 NLOC of Python (types and constants 25, `link_heights` 5, plan and pass checks 45, the record's columns built per pass and joined 35); by Peter's rule of 2026-10-25 about 1.5 times that: **about 165 NLOC**, and about 300 lines of tests. Module budget 165 in `architecture/modules.yaml` (Peter, AQ-017).

## Open questions

None open. Peter's answers of 2026-10-27 (`docs/agents/questions/`; plan 0007, Decisions):

- AQ-015: SPEC approved, all as recommended: the setup sheet states the clamp and jaw limits (item 1 (a)); the heights fixed per D-062 (2 (a)); Z first after the tool change, checked in the dry run (3 (a)); the feed descent beside the stock with D-079's air gap (4 (a)); the descent refusal as drafted (5).
- AQ-017: budget 165 and research 10, 11, 26 in `architecture/modules.yaml`.
- AQ-020 (a): REQ-TP-008 refuses a plan whose tool number differs from the header's (from the implementation's cnc review).
- AQ-021 (a): REQ-TP-010 refuses a pass level below the stock bottom, equal allowed (same review); the setup-sheet and dry-run notes go to steps 7 and 8.

Box 2 choices are in `src/splintercam/toolpath/DECISIONS.md`.

## Change log

- 2026-10-27: drafted for plan 0007, step 5, from research 10 and 26 (Links and heights). Revised after the spec review the same day: checks rule by rule; REQ-TP-012's distance test as one fixed float64 expression (not exact), R from the tool; line fill values written by toolpath; h_r below h_c checked; the move index of a pass row stated; the performance figure without `make_operation`.
- 2026-10-27: Reviewed (Peter, AQ-015 and AQ-017, all as recommended); budget 165.
- 2026-10-27: `cl`'s header gains `retract_height_mm` and REQ-CL-022 (pull request 85, AQ-018 (c)): REQ-TP-007 also checks the header's retract height against h_r; the invariant cites REQ-CL-022.
- 2026-10-27: implemented (plan 0007, step 5, first half); "Verified by" names the tests; DEC-TP-005 (ours) refuses a plunge class beyond int64 and a stock box not finite in x or y; AQ-020 and AQ-021 open. 182 NLOC against the budget 165.
- 2026-10-27: REQ-TP-008 gains the tool-number check (Peter, AQ-020 (a)) and REQ-TP-010 the stock-bottom check (Peter, AQ-021 (a)).

[r10]: ../../../docs/research/10-linking.md
[r26]: ../../../docs/research/26-toolpath-record.md

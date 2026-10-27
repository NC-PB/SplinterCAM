# SPEC: toolpath

<!-- The links between and around the passes of an operation. Drafted on 2026-10-27 for plan 0007, step 5, cut to the
     slice (D-160): one operation's links through the clearance height, every descent beside the stock, from
     research 10's subset. Per-link retract heights over stock layers, staying down, leads, link checks against
     fixtures, the arc fit of research 11 and the kernel come with later plans. -->

| | |
| --- | --- |
| Status | Draft (2026-10-27, for Peter's review: AQ-015; budget AQ-017). Choices marked "(ours)" are in `src/splintercam/toolpath/DECISIONS.md`, provisional |
| Layer | 3 (see architecture/modules.yaml) |
| Depends on | foundation (`Context`); model (`StockBox`, `FlatEndMill`); cl (`ClHeader`, `ClMoves`, `ClOperation`, `MoveKind`, `Role`, `NO_FEED_CLASS`, `make_operation`, by `src/splintercam/cl/SPEC.md`, Reviewed) |
| Research | [10][r10], Method, Traps, Tests (the clearance-height links of plan 0007); [26][r26], Links and heights (what the record carries) |
| Decisions | D-062 (clearance 5 mm, retract 3 mm over the stock), D-087 (G0 only above the safe plane and along the axis), D-078 (no fixtures modelled in the slice), D-055 (determinism); Peter's answer to plan 0007, question 4; text in [docs/spike/decisions-snapshot.md](../../../docs/spike/decisions-snapshot.md) |
| Owner | Peter Burgener |

## Purpose

Turns a strategy's passes into one complete operation of the toolpath record: the rapid up after the tool change, the rapid over the approach point, the descent beside the stock to each pass, the retract to the clearance height between passes, all with their link heights (research 10, Method). The strategy plans only the moves in the plane at each level; toolpath owns the heights, so every strategy links the same way. Its user in plan 0007 is `strategies/profile` (step 5); its output goes to `cl`'s `make_operation`.

## Scope

- In: the clearance height h_c and the retract height h_r from the stock top (D-062); research 10's links for passes that all start and end at one approach point P: Method 1 to 5 in that order; the check of research 10 test 1 that the descent at P lies beside the stock box grown by R.
- Out, handled elsewhere: where P lies, the passes' levels and their moves in the plane (`strategies/profile`, research 22, Method 4 to 6); the feed values and the header fields other than the clearance height (the strategy); the record's own rules (`cl`, REQ-CL-005 to 017, applied by `make_operation`); fixtures and clamps (research 10, trap 1: the setup sheet and Peter's dry run, plan 0007 step 8; what the setup sheet must say is AQ-015, item 1).
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
| REQ-TP-001 | THE `link_heights` function SHALL return h_c = stock top + `CLEARANCE_ABOVE_STOCK_MM` and h_r = stock top + `RETRACT_ABOVE_STOCK_MM`, from the stock box alone (D-062: "over stock or clamps"; research 10, trap 1: no clamps in plan 0007). IF the stock top is not finite, or the computed h_r is not below h_c (a stock top so large that the 2 mm vanish in rounding), THEN `link_operation` SHALL raise `ValueError` (ours; `link_heights` itself does not raise, so a strategy can report it as a diagnostic first, REQ-PRF-005). | unit: research 10 test 2 (top 2 mm: 7 and 5); top 0: 5 and 3; `link_operation` with top 1e16 raises naming REQ-TP-001 | Draft |
| REQ-TP-002 | THE `link_operation` function SHALL return the record of `make_operation` (`src/splintercam/cl/SPEC.md`) for these moves, in this order: RAPID to (NaN, NaN, h_c); RAPID to (P, h_c); per pass i: RAPID to (P, h_r), LINE to (P, z_i), the pass's rows at z_i, RAPID to (P, h_c) (research 10, Method 1 to 4; test 1). | unit: research 22 test 1's three passes give exactly that sequence of kinds, roles and ends; property: random plans give 2 + Σ(m_i + 3) moves in that pattern | Draft |
| REQ-TP-003 | THE first move SHALL change Z alone, ending at h_c with x and y NaN, and the second SHALL move in the plane at h_c only (research 10, Method 1, trap 2: the position after the tool change differs per machine). | unit: move 0 and move 1 of REQ-TP-002's case | Draft |
| REQ-TP-004 | THE RAPID moves SHALL carry the link height h_c, except the descent to h_r at P, which SHALL carry h_r; every RAPID has role LINK and `NO_FEED_CLASS` (research 10, Method 5; research 26, Links and heights). | unit: the link heights of REQ-TP-002's case; property: every RAPID in the plane is at h_c and its link height is h_c | Draft |
| REQ-TP-005 | THE descent from h_r to z_i SHALL be a LINE at P with role APPROACH and the plan's plunge feed class (research 10, Method 2). | unit: plunge class 1 in research 22 test 1's plan: each descent is LINE, APPROACH, class 1, ending at (P, z_i) | Draft |
| REQ-TP-006 | THE pass's rows SHALL become LINE moves where the sweep equals 0 (−0.0 included) and ARC moves otherwise, each ending at (x1, y1, z_i), with the row's role and feed class, in the given order; an ARC takes the row's centre and sweep, a LINE gets the fill values centre (NaN, NaN) and sweep +0.0 whatever the row holds there, and every LINE and ARC the link height NaN (research 26, Move; D-057; `cl` REQ-CL-010, 013). | unit: a pass with a line and a CW arc; a line row with centre (0, 0) and sweep −0.0 gives a LINE with NaN centre and sweep +0.0; property: the pass's ends, centres and sweeps read back from the record | Draft |
| REQ-TP-007 | THE header's clearance height SHALL equal h_c of REQ-TP-001 bit for bit; IF it does not, THEN `link_operation` SHALL raise `ValueError` (D-062; `cl` REQ-CL-012 checks the moves against the header). | unit: header at h_c − 0.001 and at h_c + 0.001 raise | Draft |
| REQ-TP-008 | IF the plan has no pass, P is not finite, or the plunge feed class is negative, checked in that order, THEN `link_operation` SHALL raise `ValueError` (ours; the class's upper bound is `cl`'s REQ-CL-009). | unit: one per field | Draft |
| REQ-TP-009 | IF a pass's `rows`, `role` or `feed_class` is not a NumPy array of its dtype and shape, has no row, or its rows' lengths differ, or a role is not APPROACH, CUT or RETRACT, THEN `link_operation` SHALL raise `ValueError` naming the pass and the column (research 26 subset: LINK only on rapids, REQ-CL-005). | unit, one each: rows float32, rows (m, 6), an empty pass, `role` one shorter than `rows`, a row with role LINK | Draft |
| REQ-TP-010 | IF a pass's z_i is not finite or not below h_r, THEN `link_operation` SHALL raise `ValueError` naming the pass (research 10, Method 2: the descent goes down from h_r). | unit: z_i = h_r raises; z_i one ulp below h_r passes | Draft |
| REQ-TP-011 | IF, in this order, a pass's first row does not start at P bit for bit, a row does not start where the previous one ended bit for bit, or its last row does not end at P bit for bit, THEN `link_operation` SHALL raise `ValueError` naming the pass and the row (research 10, Method 3: every pass starts and ends at P; the record stores ends only, research 26, Move, so a gap would be lost). | unit: each of the three broken by one ulp | Draft |
| REQ-TP-012 | IF P lies within R of the stock box in XY, THEN `link_operation` SHALL raise `ValueError` (research 10, Method 2: the tool descends beside the stock, never into it; test 1: no move below h_r inside the stock box grown by R but the pass and its approach and retract). The decision is the one float64 expression dx·dx + dy·dy ≤ R·R, with dx = max(x_min − px, 0, px − x_max) and dy likewise, evaluated in scalar Python floats in that order (rounded, not exact, but the same on every platform; ours: the grown box with round corners, touching counts as inside, DEC-TP-004). | unit, on dyadic coordinates so the boundary is exact: at R = 5, P at R + 2^-10 from a side passes and at R raises; off a corner, dx = 3 and dy = 4 raises, dx = 3 and dy = 4 + 2^-10 passes; inside the box raises | Draft |
| REQ-TP-013 | THE checks SHALL run rule by rule in this order: REQ-TP-001, 007, 008, 009, 010, 011 (each over all passes in order before the next rule), 012, then `make_operation`; the `ValueError` SHALL name the first rule broken by its ID and, for a pass rule, the first pass and row breaking it by index from 0 (ours, D-055, as `cl`'s REQ-CL-020; DEC-TP-002). | unit: pass 0 breaking REQ-TP-011 and pass 1 breaking REQ-TP-009 names REQ-TP-009 and pass 1 | Draft |
| REQ-TP-014 | THE `link_operation` function SHALL decide the same on every platform: comparisons, sums and products in a fixed order only, no trigonometry, no floating-point NumPy reductions in a decision (`np.all` and `np.any` over comparisons are fine; D-055 tier 1). | review; unit: REQ-TP-012's boundary cases | Draft |

## Invariants

- Every record `link_operation` returns satisfies research 10 test 1: the moves come in REQ-TP-002's order; no RAPID in the plane below h_c; no move below h_r within R of the stock box but the passes' rows and the descents at P; every RAPID at or above its link height (REQ-TP-002 to 006, 012; `cl` REQ-CL-011). Property test over random valid plans: these hold, and `make_operation` accepts the moves.
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

First count about 110 NLOC of Python (types and constants 25, `link_heights` 5, plan and pass checks 45, the record's columns built per pass and joined 35); by Peter's rule of 2026-10-25 about 1.5 times that: **about 165 NLOC**, and about 300 lines of tests. Module budget: AQ-017.

## Open questions

- AQ-015 (Peter): the SPEC review: what the setup sheet must say about clamps and jaws, fixed heights from the stock top, the order after the tool change, the feed descent beside the stock, the descent refusal.
- AQ-017 (Peter): the budget and research list in `architecture/modules.yaml`.

## Change log

- 2026-10-27: drafted for plan 0007, step 5, from research 10 and 26 (Links and heights). Revised after the spec review the same day: checks rule by rule; REQ-TP-012's distance test as one fixed float64 expression (not exact), R from the tool; line fill values written by toolpath; h_r below h_c checked; the move index of a pass row stated; the performance figure without `make_operation`.

[r10]: ../../../docs/research/10-linking.md
[r26]: ../../../docs/research/26-toolpath-record.md

# Decisions: toolpath

<!-- The permanent record of why this module is built the way it is. Rules: docs/dev/05, "Module decision records".
     - Write the entry in the same commit as the change that makes the decision, not at the end and not on request.
     - Newest last. IDs DEC-TP-NNN are never reused.
     - After merge, only the Status line of an entry changes. A changed decision is a new entry that supersedes the old one.
     - Code that follows a decision a reader would not expect cites its ID in a comment. -->

## DEC-TP-001: The strategy hands over passes as curve rows at a level; toolpath owns the heights

- Date: 2026-10-27; decided by: ours (SPEC draft, plan 0007 step 5); part of Peter's review (AQ-015), since it is the interface every strategy will use
- Status: Accepted 2026-10-27 (SPEC Reviewed, AQ-015)
- Decision: a strategy gives toolpath the approach point P, the tool (for R), the plunge feed class and per pass its level z_i with the moves in the plane as geometry2d's curve rows (m, 7), plus a role and a feed class per row. toolpath builds every move along Z and every rapid, with the link heights, and calls `cl`'s `make_operation`. h_c and h_r are named constants from D-062 (5 mm and 3 mm over the stock top), not job parameters, in the slice.
- Why: research 10 puts the heights and the order of links in topic 10, the same for every operation; a strategy that wrote its own rapids could break D-062 and D-087 in its own way. Curve rows are the form loops already cross module boundaries in (geometry2d `AGENTS.md`, Local rules), so the profile's loop goes in without a conversion. D-062 fixes 5 and 3 mm; research 10 names no user parameter for them, and plan 0007's scope lists none.
- Rejected: the strategy writes the whole `ClMoves` and toolpath only checks it (every strategy repeats the link code); passes as `ClMoves` (the link-height and kind columns would be filled by a strategy that must not set them); h_c and h_r as declared parameters now (no requirement in the slice; Peter kept them fixed per D-062, AQ-015, item 2 (a)).
- Where: REQ-TP-001 to 006, 011.

## DEC-TP-002: A broken plan raises `ValueError`

- Date: 2026-10-27; decided by: ours, as `cl`'s DEC-CL-002
- Status: Accepted 2026-10-27 (SPEC Reviewed, AQ-015)
- Decision: `link_operation` returns a `ClOperation`, not a `Result`; a plan that breaks a rule raises `ValueError` naming the requirement ID and the first pass and row breaking it. The checks run in a fixed order (REQ-TP-013).
- Why: the plan is built by a strategy, after `model` and the strategy have checked every user value; a broken plan is a strategy bug. `cl` raises in the same way, so a caller handles one kind of failure. Expected outcomes, such as an approach point that cannot be found, are the strategy's diagnostics before it builds a plan.
- Rejected: diagnostics (a user cannot fix a strategy's bug).
- Where: REQ-TP-007 to 013.

## DEC-TP-003: No kernel in the slice

- Date: 2026-10-27; decided by: ours
- Status: Accepted 2026-10-27 (SPEC Reviewed, AQ-015)
- Decision: the moves of each pass are copied into the record's columns with NumPy (concatenation, column slices, `np.where` on the sweep); a Python loop runs over passes, never over rows. `kernel: true` in `architecture/modules.yaml` stays for the link checks over stock layers (D-062) that come later.
- Why: AGENTS.md's split rule allows vectorised NumPy for loops over segments; a pass count is like an operation count. A C++ kernel for copies would be code no requirement needs.
- Rejected: a kernel now; a Python loop over rows.
- Where: REQ-TP-006, 014.

## DEC-TP-004: Research 10 test 1's "stock box grown by R" is the box with round corners, touching counts as inside

- Date: 2026-10-27; decided by: ours
- Status: Accepted 2026-10-27 (SPEC Reviewed, AQ-015)
- Decision: the descent at P is refused when the squared distance in XY from P to the stock box is at most R², as one float64 expression in a fixed order (REQ-TP-012): rounded, so not exact, but the same on every platform (D-055 tier 1). Its boundary tests use dyadic coordinates, where the expression is exact. Every other comparison of the module is exact (bit for bit, as `cl`'s DEC-CL-004). R is the tool's (`FlatEndMill.radius_mm`), not a number the strategy passes, so a strategy bug cannot weaken the check (spec review).
- Why: the tool's circle at P overlaps the stock exactly when P is within R of the box; at a box corner that is a quarter circle of radius R, not the square corner of a box grown along the axes, which would refuse a valid P diagonally off a corner. At distance exactly R the tool rubs the stock's side on the way down, so touching is refused (conservative). The profile places P at least R + 0.2·R off the box (research 22, Method 5; D-079), so a correct strategy never meets the boundary. Squares avoid `sqrt` and `hypot` in the decision (D-055).
- Rejected: the axis-aligned grown box (refuses valid points off the corners); a tolerance on the distance (lets a rubbing descent pass); an exact predicate (geometry2d's `in_arc_circle` needs a point on the circle, which is itself rounded; a margin of rounding at a decision the profile keeps 0.2·R away from does not change a result).
- Where: REQ-TP-012, 014.

## DEC-TP-005: Two inputs outside the preconditions are refused rather than crash or pass

- Date: 2026-10-27; decided by: ours (implementation, spec review)
- Status: Accepted 2026-10-27
- Decision: (a) REQ-TP-008 also refuses a plunge feed class above the int64 range of cl's `feed_class` column, with the same `ValueError`; (b) REQ-TP-012 refuses a stock box whose x or y bounds are not finite, before the distance test.
- Why: (a) the SPEC leaves the class's upper bound to cl's REQ-CL-009, but `np.array([2**63], dtype=np.int64)` raises `OverflowError` before `make_operation` runs, so a strategy bug would surface as a different exception (spec review, should-fix 2). (b) Python's `max` keeps the first of equal or unordered values, so `max(x_min - px, 0.0, px - nan)` is 0.0: an x_max of NaN made P in the middle of the stock pass REQ-TP-012 (spec review, should-fix 3). `model`'s `check_job` refuses such a stock, but the SPEC's preconditions do not name the stock, and the descent into the stock is the one thing REQ-TP-012 exists to stop. Both are refusals of inputs no correct caller sends; neither changes a result for a valid plan.
- Rejected: adding the stock to the preconditions instead (leaves the silent pass for a caller that skips `check_job`); `not (d² > R²)` in place of `d² ≤ R²` (does not catch it, since `max` drops the NaN before the comparison).
- Where: REQ-TP-008, REQ-TP-012; `src/splintercam/toolpath/_checks.py`.

## DEC-TP-006: The plan's tool must be the header's, and no pass goes below the stock bottom

- Date: 2026-10-27; decided by: Peter (AQ-020 (a), AQ-021 (a)), from the implementation's cnc review
- Status: Accepted 2026-10-27
- Decision: REQ-TP-008 refuses a plan whose `tool.number` differs from the header's `tool_number`, after its three other checks. REQ-TP-010 refuses a pass level below the stock bottom (`stock.min_mm[2]`), a level equal to it allowed, after the h_r check.
- Why: REQ-TP-012 takes R from the plan's tool, while the machine loads the header's; with the two mixed up a Ø20 tool could feed down 6.4 mm into the stock's side at P, so DEC-TP-004's "a strategy bug cannot weaken the check" only holds with this check. Below the stock bottom is the vice or the table (Peter, AQ-016, item 5 (a)); the profile refuses such a z_bottom (REQ-PRF-006), and toolpath, which every strategy's descent passes, is the backstop.
- Rejected: leaving both to the strategies and `job` (AQ-020 (b), AQ-021 (b)).
- Where: REQ-TP-008, REQ-TP-010; `src/splintercam/toolpath/_checks.py` (`_fields`, `_level`).

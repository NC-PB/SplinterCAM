# Plan 0003: geometry2d, slice 1

<!-- Lives in docs/plans/active/ while work is ongoing, then moves to docs/plans/completed/.
     The agent updates the progress log at the end of every session, before stopping. -->

- Goal: `geometry2d` meets slice 1 of its SPEC: exact predicates, lines and arcs with their validation, bulge conversion, distances and closest points, circle through three points, flattening with a known error side, area and orientation, point in region, cleanup and bounding boxes.
- Specs: `src/splintercam/geometry2d/SPEC.md` (slice 1); `src/splintercam/foundation/SPEC.md` (REQ-FND-001, the grid unit)
- Research: `docs/research/01-foundations.md`
- Branch: one branch and one pull request per step, based on `main` after the previous step's merge. Stacked pull requests (based on the previous step's branch) were tried in steps 2 and 3: merging with "delete branch" closed the next one (pull request 9) or merged it into a branch instead of `main` (12, then repeated as 10). Do not stack
- Owner: Peter Burgener; agents: Claude Code cloud sessions

## Context

- Peter's answers of 2026-10-02 release slice 1: vendor `predicates.c` (ADR 0009, drafted in step 1); predicates without a `Context`, `Result` with a `Context` for functions with diagnostics; `in_arc_circle` +1 inside; arc rows give `ARC_INCONSISTENT`; D-055 tiers 2 and 3 as proposed, single-threaded kernels; `grid_unit_mm` on `ToleranceSet` in its own commit; glossary terms with their code; the draft's proposals for the other slice 1 questions, marked "(ours)"; questions outside slice 1 go to Later parts without work (D-159).
- The environment of the session that wrote this plan cannot reach `www.cs.cmu.edu`, so it cannot vendor `predicates.c`. Steps 2 to 4 need no predicates and come first; step 5 waits until the file is in the repository.

## Steps

<!-- Each step has a size estimate (kept code and tests). At 50 % over it, stop and ask, as for a timebox
     (docs/dev/12, section 3). -->

- [x] 1. **SPEC cut and ADR 0009.** Cut `src/splintercam/geometry2d/SPEC.md` to slice 1 (requirements, interface, invariants, failure modes, links to research 01; the rest one line each under Later parts). Draft ADR 0009 for vendoring `predicates.c`, with its `modules.yaml` `kernel_libraries` entry (applied) and its `NOTICE` entry (`0003-notice.patch`; `NOTICE` is protected). Size: docs only.
- [x] 2. **Grid unit, lines and arcs.** First commit: `grid_unit_mm` on `ToleranceSet` (REQ-FND-001). Then the `geometry2d` package with `Line`, `Arc`, `make_line`, `make_arc` and `are_parallel`, its first kernel (`arcs.cpp`: the radial and angle checks; `angle.cpp`: the arctangent from basic operations), the module `AGENTS.md` and glossary terms. REQ-G2D-003, 018 (the arctangent), 025, 027, 035, 037 to 043, 045, 047 to 049. Size: about 250 + 350.
- [x] 3. **Curve rows and bulges.** `CurveRows`, `curve_rows`, `arc_from_bulge`, `bulges_from_arc`. REQ-G2D-044, 050 to 053, 188 to 197, 201, 203. Size: about 180 + 300.
- [x] 4. **Flattening and bounding boxes.** `flatten` (`flatten.cpp`), `bounding_box`, the step limit π/2 as a declared parameter in foundation's defaults file (a foundation SPEC change), the shared exact test of which axis directions lie in a sweep. REQ-G2D-102 to 113, 126, 213, 214, 230; the tests of REQ-G2D-231 and 232 start here and grow with each step. Size: about 220 + 300.
- [x] 5. **Exact predicates** (`predicates.c` vendored by Peter, pull request 15). The C build of the vendored file through our own wrapper, strict float flags, `exactinit` at load; `orient2d`, `incircle`, `two_sum`, `two_product`; the build guard. REQ-G2D-005 to 011, 013 to 018, 021, 024. Size: about 300 + 350.
- [x] 5b. **Arc predicates.** `in_arc_circle` and the (q_y − c_y)² comparison by expansion arithmetic, from the branch `step-5b-draft` (reviewed with step 5). REQ-G2D-022, 023. Size: about 110 + 120.
- [x] 6. **Distances and circles.** `closest_point`, `circle_through`. REQ-G2D-091 to 101. Size: about 150 + 250.
- [x] 7. **Area and orientation.** `signed_area` (`area.cpp`), with the exact sum. REQ-G2D-001, 002, 128 to 133. Size: about 180 + 250.
- [x] 8. **Point in region, exact layer.** `PointLocation`, `point_in_region_exact` (`region.cpp`), the radial connector and its exact height comparison. REQ-G2D-135, 139, 143, 145. Size: about 380 + 400.
- [x] 8b. **Point in region, tolerance layer.** `point_in_region`: ON within eps_len by the distances of REQ-G2D-091 to 096, measured to the nearer of the two radii (Peter, 2026-10-03), from the branch's saved full version. REQ-G2D-134, 148 to 150. Size: about 60 + 120.
- [ ] 9. **Cleanup.** `cleanup` (`cleanup.cpp`). REQ-G2D-020, 204 to 212. Size: about 180 + 250.

Stop after step 9 for Peter's review of slice 1, or earlier at a blocker.

## Decisions

- 2026-10-02: requirement IDs keep the draft's numbers; merged and moved IDs are listed in the SPEC's change log, so no ID is reused (docs/dev/05).
- 2026-10-02: decisions and counts that need an angle (the arc angle check, the flattening count) use our own arctangent from IEEE basic operations in the kernel, so they are the same on every platform, as D-055 tier 1 and REQ-G2D-232's equal counts need (spec review of step 1). Sign decisions use exact predicates or exact comparisons of doubles (Peter's answer 5). Constructions use the platform's libm in C++, never NumPy's float64 ufuncs, which may pick SIMD code by CPU (tier 2).
- 2026-10-02: a bulge whose sagitta is at most eps_len gives a line (ours): such an arc lies within eps_len of its chord, and its far centre would fail the radial check by rounding alone.
- 2026-10-02: requirements moved between steps, slice 1 unchanged: REQ-G2D-044 to step 3 (no arc is built from end points before the bulge conversion), 201 and 203 to step 3 (the first arrays from callers reach the kernel through `curve_rows`; step 2's kernel only sees arrays its own module builds), 230 to step 4 (its parameter, the step limit, serves flattening). The test audit of step 2 asked for this to be recorded.
- 2026-10-03: the sanitizer build turns ASan off for `kernel/shewchuk.c` alone (approved by Peter on 2026-10-03): `predicates.c`'s expansion sums read one element past an input array (`enow = e[++eindex]`) and use it only while `eindex < elen`; ASan reported it as a stack-buffer-overflow in `orient2dadapt` on CI. The vendored file stays unchanged; UBSan stays on.
- 2026-10-03: step 5 split in two, 5 and 5b: with the review fixes it came to about 440 added lines of non-test code, over the limit of 400 per pull request (docs/dev/12, section 3); the arc predicates go next, from `main` after this step's merge.
- 2026-10-03: the predicates' input range is a precondition, not a check: SRC-032 guarantees exact signs only for nonzero inputs with exponents in [−142, 201] (p. 308), and the first property run found 5e-324 (a nudged 0) giving the wrong sign, in Shewchuk's orient2d as in ours. Real coordinates in mm never come near 1.8e-43; the property generators stay inside the range with `assume`, so their oracle comparison stays strict. Peter confirmed on 2026-10-03: no check outside the range.
- 2026-10-02: the largest flattening step π/2 is an entry of foundation's `tolerance_defaults.toml` (REQ-G2D-230), so geometry2d reads no file of its own (docs/dev/03, rule 5).

## Progress log

<!-- Newest first. What was done, what tools/check reported, what is next. At most about 30 lines per session;
     numbers go into tables. Above 300 lines, older entries move to an archive file next to the plan. -->

### 2026-10-03, session 1, step 5

- Peter vendored `predicates.c` (pull request 15, ADR 0009 accepted, NOTICE entry); SHA-256 f8662c3f…92029, in the REUSE sidecar `kernel/vendor/predicates.c.license`. Its header confirms the public-domain dedication and `exactinit()`; the quirks are `<sys/time.h>` and `random()` (test-data generators only) and old-style definitions; there is no x87 control-word code.
- Done: CMake builds C for the wrapper `kernel/shewchuk.c` (C99 with extensions, warnings off for that file only, `-ffp-contract=off -fno-fast-math` or `/fp:precise`, hidden symbols; on MSVC an empty `<sys/time.h>` from `cmake/msvc-shim/` and `random` as `rand`); `kernel/exact.cpp`: `two_sum`, `two_product`, orient2d and incircle through `predicates.c`; `exactinit()` when the module loads. Python: `orient2d`, `incircle`. Tests first: note test 1's 65 536-point grid, as the first call in a fresh interpreter too; notes tests 2 and 4; the build guard on all 10^6 pairs against an independent NumPy reference, uniform and spread; properties against exact rationals on nearly collinear and nearly cocircular input.
- Reviews: simplifier (cuts taken: the Python wrappers of `two_sum` and `two_product`, helpers with one caller, comments); test-auditor (fixed: the build guard exact on every pair, incircle drawn near its circle; the input-range `assume` judged a domain restriction, not a weakening; Peter confirmed); spec-reviewer (no blocker, the expansion arithmetic checked; fixed: a NaN or infinite point read as sign 0, now `ValueError`; the 64-bit-only build and the C flags' coverage stated). The arc predicates, reviewed here too, moved to step 5b.
- CI on pull request 16: the sanitizer found `predicates.c`'s one-past-end read (ASan off for that code, approved by Peter); Windows needed the vendored C code in a C-only library target of its own, because the Visual Studio generators do not apply per-language options and include directories in a mixed C and C++ target.
- `tools/check`: PASS (11 of 14 steps). Property tests pass with 10 000 cases each.
- Next step: 5b.

### 2026-10-03, session 1, step 8b

- Done: `point_in_region` with the tolerance layer, from the saved full version of step 8: ON within eps_len by the distances of `closest_point` (the clamped foot, ends exactly; in the sweep by exact signs), on an arc to the nearer of the circles of radius |P0 − C| and |P1 − C| (Peter, 2026-10-03), so both orientations agree. Tests first, they failed on the missing name: research tests 5 and 6 and note test 6 with the tolerance layer, eps_len itself ON and the next double not, the winding over two loops, the nearer radius, both orientations of the review's off-circle cases; the property against `closest_point`'s distances.
- `tools/check`: PASS (11 of 14 steps). Property tests pass with 10 000 cases each.
- Next step: 9.

### 2026-10-03, session 1, step 8

- Done so far (branch `claude/cool-ramanujan-evgci4-step-8`, no pull request yet): `point_in_region`, `point_in_region_exact`, `PointLocation` (`_region.py`, kernel `region.cpp`); research tests 5 and 6, note test 6, rays through vertices and tangent at extremes, properties against an exact winding oracle, a fine flattening and `closest_point`'s distances. The flattening property found an arc whose P1 lies 2^-126 mm past the top of its circle leaving a height gap; pieces now rise or fall by their ends' heights.
- Stopped: the spec review found wrong results on `curve_rows`-valid input, all reproduced, each also breaking REQ-G2D-150 (the reversed loop answers differently). They come from the SPEC and research 01, not only from the code (AGENTS.md: stop when the spec contradicts the research):
  1. REQ-G2D-143's ON rule for arcs, "on the arc's side of the chord P_0P_1", contradicts REQ-G2D-145 when the chord line meets the circle again far from the arc: a tiny arc whose P1 lies just clockwise of P0 (`[5, 0, 5, -1e-8, 0, 0, 1e-9]`) makes (3, 4) ON, 4.5 mm from the boundary; an arc whose P1 lies 7e-7 off the circle makes (4, -3) ON. Proposal: ON when q is an end point, or on the circle and in the sweep by the exact signs of `closest_point` (REQ-G2D-093).
  2. Research 01's ray rules assume P1 lies on the circle. With P1 off it by up to eps_len (REQ-G2D-042) near the top or bottom, the arc and the next row leave a gap about sqrt(2·r·δ) wide: r = 1000 mm and δ = 5e-7 give IN at (0.01, 1000.0000002), 0.01 mm outside. Proposal: close each arc to P1 along the ray C → P1 (a radial connector), decided by exact signs.
  3. REQ-G2D-150 cannot hold at eps_len when P1 is off the circle: reversing an arc changes its radius |P0 − C| by up to eps_len, so a point 5e-7 from one radius is ON in one orientation and 1.2e-6 from the other, OUT, in the other. Proposal: the tolerance layer measures to the nearer of |P0 − C| and |P1 − C|.
- Peter's answers (2026-10-03): 1. ON in the sweep; 2. the radial connector; 3. the nearer of both radii. Done: ON on an arc is an end point, a point of the circle in the sweep (`in_sweep`, as `closest_point`) or a point of the connector; the last piece of an arc ends where the ray through P1 meets the circle, compared with q_y by a new exact `ray_height_sign` ((q_y − c_y)²·|P1 − C|² against r²·(P1_y − c_y)², products of expansions by `predicates.c`'s `scale_expansion_zeroelim`), and the connector counts like a straight edge. The four failing inputs of the review are tests; a property compares arcs with P1 off the circle against their flattened arc and connector.
- Simplifier, taken: `RowResult` folded into `locate`, no separate flag for the exact layer, a shorter `line_winding`, no full-circle branch in `in_sweep`. The 10 000-case runs also found coordinates far below the predicates' input range; the properties now draw from a 2^-20 mm grid.
- Split: with the answers the step came to 472 lines of non-test code; the tolerance layer (distances, `point_in_region`) moves to step 8b, saved on the branch's history (commit of the full version).
- Reviews: simplifier and spec-reviewer as above, one round each (D-159); test-auditor (fixed: `ray_height_sign` had no test next to the ray's end, so a rounded comparison would have passed; it now has a scalar binding, unit tests at the double nearest the end and one unit either side, straight above and below C, both sides of c_y, and a property against exact rationals; the connector's ON rule tested both ways, beyond P1, on the opposite ray, inward and slanted; REQ-149 and 150 tags removed from exact-layer tests, they come with step 8b; optional, taken: a nearly full arc's missing part).
- `tools/check`: PASS (11 of 14 steps). Property tests pass with 10 000 cases each.
- Next step: 8b.

### 2026-10-03, session 1, step 7

- Done: `signed_area` (`_area.py`, kernel `area.cpp`): the polygon sum about the centre of the end points' bounding box plus each arc's segment ½ r² (φ − sin φ); beyond 10^6 vertices or a half-extent of 3355 mm (named constants, as the SPEC's Tolerance budget says) the polygon and segment terms are summed exactly by an `ExactSum` (two_product and `predicates.c`'s `fast_expansion_sum_zeroelim`, compressed by its `compress` above 64 components); |A| <= eps_len·L gives `LOOP_DEGENERATE` (warning). φ − sin φ comes from basic operations (`angle.cpp`, `phi_minus_sin`), so the degenerate decision is the same on every platform. Tests first, they failed on the missing names: research tests 3 and 19, the limits on both sides, the exact path with arcs, run twice on both paths; properties against exact rationals and for reversal.
- The first exact path took 366 s for 10^6 + 1 vertices (the expansion grew and was copied on every add): two buffers in turn and `compress` brought it to 0.2 s.
- Reviews: simplifier (taken: the kernel returns its two sums, no copy of `curve_rows`' arrays, repeated comments; the limits back to named constants, which keeps foundation out of this step); spec-reviewer (fixed: an out-of-bounds read of `predicates.c` on an empty sum, two elements past, now padded; libm `sin` in the degenerate decision, now `phi_minus_sin`; the foundation change; arc segments now in the exact sum too); test-auditor (fixed: the translation test could not fail, it now checks the centre the kernel gets; arc lengths in L tested; the warning severity; a reversal property on both paths; one-axis extents; the limits checked against research 01's bound; the pinned segment values checked for accuracy).
- For Peter: research 01's bound n·u·(√2·E·L + 3E²) has no term for the arc segments, so the invariant "the sign of `signed_area` is right whenever |A| > eps_len·L" is proven for polygons only; the property test covers polygons only and no bound was invented (test audit). A term for the segments, or a statement that they stay within the margin, would close it.
- `tools/check`: PASS (11 of 14 steps). Property tests pass with 10 000 cases each.
- Next step: 8.

### 2026-10-03, session 1, step 6

- Done: `closest_point` (`_distances.py`): the clamped foot on a line; on an arc the sweep decided by exact orient2d signs (two halves from the start direction, a clockwise arc as the counter-clockwise arc from P1 to P0, the sweep governing near 0 and near a full turn as in `bounding_box`), the nearer end by `in_arc_circle`. `circle_through` (`_circle.py`, kernel `circles_through` in `exact.cpp`): D from `predicates.c`'s orient2d, the eps_len test as |D| > eps_len·|P3 − P1| with no division, lengths as sqrt of a sum of squares. A NaN or infinite query is a `ValueError`. Tests first, they failed on the missing names: research tests 9 and 17, note test 5, the exact sweep edge 2^-60 off the ray, the exact nearer end, the eps_len boundary, run twice byte for byte (REQ-G2D-231); properties against exact rationals and sampled arc points.
- Reviews: simplifier (taken: `_sign`, the full-circle branch, private docstrings, `d != 0` in the kernel; the shared sweep test with `_box.py` in the backlog); spec-reviewer (fixed: the circle decision through libm `hypot`, now sqrt of a sum of squares as in `arcs.cpp`; the nearer end from rounded distances, now exact, its failing input a test; a −0.0 parameter; the eps_len boundary tested; a nearly full arc that `make_arc` really builds; NaN queries; the module's `distance`); test-auditor (fixed: two untagged tests, the sweep-edge test too coarse at 2^-40, REQ-G2D-231 run-twice tests for tests 9 and 17; the existence check before the conditioning filter; arc tolerances scaled like the others). The 10 000-case run found coordinates near 1e-195, below the predicates' input range, where the squared chord underflows: the circle and arc properties keep to the range with `assume`, as the predicate properties do.
- `tools/check`: PASS (11 of 14 steps). Property tests pass with 10 000 cases each.
- Next step: 7.

### 2026-10-03, session 1, step 5b

- Peter merged pull request 16 and decided: ASan stays off for the vendored C code only; the predicates' input range stays an unchecked precondition. Those records (commit cf24ec2) missed the merge and come with this step.
- Done: from `step-5b-draft` (reviewed with step 5): `kernel/exact.cpp` expands each squared difference exactly and sums by `predicates.c`'s `fast_expansion_sum_zeroelim`; `in_arc_circle_signs`, `vertical_extent_signs`; Python `in_arc_circle`. Tests first, they failed on the missing names: research test 2; q_y against the top and bottom of a circle, also a top that is not a double; the batch against single rows; properties against exact rationals for both arc predicates.
- Reviews: those of step 5 cover this code unchanged; no new round (D-159).
- `tools/check`: PASS (11 of 14 steps); `tools/test --all` with the sanitizer: PASS.
- Next step: 6.

### 2026-10-02, repository health check (Peter's request)

- Every one of pull requests 1 to 13 has its head commit in `main`'s history, including those merged into stacked branches (2, 3, 4, 12); no remote branch besides `main` is left, and no local branch holds a commit outside `main`. `main` at b7c2dc0: `tools/check` PASS (11 of 14 steps), 340 tests.
- Tidied: plan 0001 (all steps done) and the two applied patches (`0001-protected-changes`, `0002-workflow`) moved to `docs/plans/completed/`; plan 0001's stale merge note corrected; `AGENTS.md` now points at this plan; `tools/README.md` and `cmd_size_check.py` no longer say the protected-changes patch is pending. Still open for Peter: `0003-notice.patch` (not applied), plan 0002 step 2 (the `large-change` label and the required check), ADR 0009.

### 2026-10-02, session 1, step 4

- Done: `AirSide` and `flatten` (kernel `flatten.cpp`: inscribed and circumscribed, the step count from `basic_atan2`, the cap π/2 from foundation's defaults file); `Box` and `bounding_box` (the axis points in an arc's sweep by octants from exact comparisons, the sweep governing where P1's octant contradicts it). Glossary: air side, bounding box. Tests first (they failed on the missing names); one test had a wrong P1 and was corrected.
- Reviews: simplifier (no must-fix, about 7 lines nice-to-have, backlog); test-auditor (fixed: the property test at 4 rounding units of |P0 − C| plus P1's offset on the last segment, as REQ-G2D-110 says, and without a deadline; both forms repeated byte for byte); spec-reviewer (fixed: a tiny arc with P1 just behind P0 got all four axis points, now the sweep governs; a step count beyond an int was undefined behaviour, now `ValueError`; a test that the cap reaches the kernel; the count in the spread test; spec gap on a lower bound of t in the backlog).
- `tools/check`: PASS (11 of 14 steps). Property tests pass with 10 000 cases. Size: non-test code +250 lines added, tests +330.
- Next step: 5, blocked: `predicates.c` is not in the repository. Stop here for Peter.

### 2026-10-02, session 1, step 3

- Done: `CurveRows` and `curve_rows` (structure, values and bit-for-bit continuity give `CURVE_INVALID`, the arc rules `ARC_INCONSISTENT`, read-only C-contiguous copies); `arc_from_bulge` (centre on the bisector, a line for a sagitta within eps_len) and `bulges_from_arc` (a full circle split opposite P0, bulges ±1). Glossary: bulge, curve rows. Tests first (they failed on the missing names).
- Reviews: simplifier (no must-fix, 4 lines nice-to-have, backlog); test-auditor (fixed: the CW half passed to `curve_rows`, `row_starts` checked read-only, the bulge property keeps P0 and P1); spec-reviewer (fixed: a tiny arc with P0 = P1 was exported as a split circle, now only |φ| = 2π splits; `(1/b − b)/4` against overflow; a radial `ARC_INCONSISTENT` row, a non-finite joint only the finite check catches, `CURVE_INVALID` before `ARC_INCONSISTENT` stated and tested; spec gaps in the backlog).
- CI on step 2 found that Apple's libc++ has no `std::views::chunk`; `arcs.cpp` walks rows by index (pull request 11, which replaces 9, closed when its base branch was deleted).
- `tools/check`: PASS (11 of 14 steps). Size: non-test code +170 lines added, geometry2d about 340 NLOC; tests +330.
- Next step: 4.

### 2026-10-02, session 1, step 2

- Done: `grid_unit_mm` on `ToleranceSet` in its own commit (REQ-FND-001). The `geometry2d` package: `Line`, `Arc`, `make_line`, `make_arc` (the SPEC's rule order), `are_parallel`; the first kernel: `arcs.cpp` (radial and angle checks), `angle.cpp` (the arctangent from IEEE basic operations), `bindings.cpp`, with outputs allocated by Python; every kernel source with `-ffp-contract=off -fno-fast-math` (`/fp:precise` on MSVC); module `AGENTS.md`; glossary: line, arc, sweep. Tests first (they failed on the missing package), 46 + 1 property test + 4 for the arctangent.
- Reviews: simplifier (no must-fix; about 15 lines of nice-to-have, in the backlog); spec-reviewer (code correct; fixed: the arctangent's bits pinned for fixed inputs so cross-platform CI shows tier 1, the radial and angle limits tested exactly with powers of two, full-circle rows through the kernel, the error claim in `angle.cpp`; REQ-G2D-044 moved to step 3; spec gaps in the backlog); test-auditor (fixed: the health-check comment states why sharing `ctx` is safe; the arctangent's accuracy tests tagged REQ-G2D-043, which decides with it, only the pinned bits under 018; the step moves recorded under Decisions; optional: an inward radial case and a negative nearly closed case, in the backlog).
- `tools/check`: PASS (11 of 14 steps; arch-check, trace-check and licence-check skipped). Property test also passes with 10 000 cases.
- Size: non-test code +382 lines added (`size-check --change`), geometry2d 233 NLOC; tests +400. The estimate was 250 + 350; counted as NLOC the code is within it, counted as added lines (comments included) it is 53 % over: the arctangent was not in the estimate.
- Next step: 3.

### 2026-10-02, session 1, step 1

- Done: the SPEC cut to slice 1 (844 to about 290 lines; 95 requirements released by this plan, IDs as drafted); ADR 0009 proposed; `architecture/modules.yaml` lists `shewchuk-predicates` under `kernel_libraries`; `0003-notice.patch` for Peter.
- Review: spec-reviewer, one round (D-159): six must-fix findings fixed (libm in decisions against D-055 and REQ-G2D-232, the test 20 deviation of REQ-G2D-192 noted, the ON rule of REQ-G2D-143 restored, bulge order of 050 and 051, bit-for-bit continuity as research 01 says, the test 23 citation); spec gaps answered in the SPEC (bulge NaN, cleanup below 3 vertices, sin(eps_ang), the π/2 entry, the MSVC version).
- `tools/check`: pass (9 of 14 steps; no code).
- Next step: 2.
- For Peter: vendor `predicates.c` (from <https://www.cs.cmu.edu/~quake/robust.html>) into `src/splintercam/geometry2d/kernel/vendor/` on the step 5 branch, or allow `www.cs.cmu.edu` in the environment's network settings; accept or change ADR 0009 and apply `0003-notice.patch`.

## Backlog

- Step 8: research 01's Point in region section still states the chord-side ON rule and has no radial connector; the SPEC carries Peter's answers of 2026-10-03 (REQ-G2D-135, 143). Exact ON on a circle depends on the orientation when P1 lies off it (the radius is |P0 - C|); the tolerance layer of step 8b covers it with the nearer radius. The kernel's sweep logic exists twice besides `_box.py` and `_distances.py` (octants and halves); a shared kernel for `bounding_box` and `closest_point` would stop them drifting apart. The region kernel holds the interpreter lock for n points × m rows (SPEC, Later parts).


- Step 7 test audit, optional: the eps_len·L boundary is tested 1 % on either side, not at equality; the `ValueError` for more than one loop carries the tag REQ-G2D-128, though the rule is in the Public interface; the 10^6-row exact path holds the interpreter lock without a cancellation check (SPEC, Later parts).

- Step 7 spec review: φ − sin φ cancels no more (series for |φ| <= 1), but research 01's bound does not mention the segment term; for r ≳ 1e10 mm its rounding could reach eps_len·L. The exact path is exact for the rounded translated coordinates; when the box straddles 0 the translation moves A by about u·E·L, below eps_len·L for E up to about 1e9 mm. Neither limit is in the SPEC.


- Step 6 simplifier: `bounding_box` could use `_distances._in_sweep` on its four axis points and drop `_octant` and `_axes_in_sweep` (about 25 lines), once REQ-G2D-214's tests confirm the same answers; its own step, since it changes `_box.py`.

- Step 6 spec review, for steps 7 and 8: the ON rule of REQ-G2D-148 needs point-to-edge distances for every point and edge; calling `closest_point` in a Python loop would break the split rule, so plan a batched kernel there. `_in_sweep` assumes r > eps_len, which `make_arc` ensures but `curve_rows` does not (`check_arcs` accepts any sweep when r ≤ eps_len/π).

- Step 6 test audit, optional: a line whose squared length underflows (|P1 − P0| below about 1.5e-154, outside the predicates' input range) counts as zero length; `_arc_parameter` uses Python's `math.atan2` (libm, only for the returned parameter, no decision on a sign); `test_bounding_box` has no REQ-G2D-231 run-twice test (from step 4); non-finite tests cover NaN in one position only; the clamp branch of `_arc_parameter` has no targeted test.


- Step 4 spec review, spec gap for Peter: no lower bound on t and no declared maximum step count; today only a count beyond an int is refused (`ValueError`). Operation tolerances give at most about 55 000 steps per circle (t_flat >= 1.1e-5 mm, r < 6711 mm).

- Step 4 simplifier, nice-to-have (about 7 lines): the full-circle branch of `_axes_in_sweep` (the shared-octant branch covers it); its private docstring; `max(steps, 1)` in `arc_steps`; the `kernel` alias in `_flatten.py`; a shared sampling helper for the flattening tests.

- Step 4: twice the first local test run right after a kernel rebuild failed once and passed on every repeat (six full runs, three `tools/check` runs, 10 000-case property runs); the failure was not captured. Likely Hypothesis's default deadline of 200 ms in the local `dev` profile on the first, slower kernel call (CI's `ci` profile has none). Capture it next time before changing anything.

- Step 3 spec review, spec gaps for Peter: (1) small bulges on long chords give huge radii (1000 mm chord, b = 1e-8: r = 2.5e10 mm), where the rounding of |P − C| exceeds eps_len and a valid bulge comes back `ARC_INCONSISTENT`; a radius or bulge limit is not in research 01; (2) an arc with P0 = P1 and a tiny sweep passes `make_arc` and `curve_rows` as a one-row loop; its removal is REQ-G2D-046, a later part.

- Step 3 simplifier, nice-to-have (about 4 lines): one-line unwrap in `arc_from_bulge`; the loop ends of `curve_rows` computed once; `NDArray[Any]` parameters instead of `starts.view(np.int64)`. Step 3 test audit, minor: the REQ-G2D-197 cases rely on NumPy's default int64 and check no message; small chords with small bulges give lines, which prove nothing about the centre.

- Step 2 test audit, optional: REQ-G2D-042 with P1 moved inward; a negative case for REQ-G2D-049 (P1 = P0 with a sweep of 2π − 0.1).

- Step 2 spec review, spec gaps for Peter: (1) the r ≤ eps_len rule comes before the radial check, so an arc with r ≈ 0 and P1 far away becomes a long line; requiring |P1 − C| ≤ r + eps_len first would catch it (research 01's "within 2r of the segment" assumes P1 on the circle); (2) REQ-G2D-043 should state the evaluated form difference·r ≤ eps_len; (3) the arctangent has no requirement of its own (tested under REQ-G2D-018); (4) REQ-G2D-027 says nothing of NaN or shapes, and for very short non-zero vectors the bound underflows, so they are not parallel, unlike the zero vector; (5) the modulo-2π reading accepts a tiny positive sweep whose P1 lies just clockwise of P0.

- Step 2 simplifier, nice-to-have (about 15 lines): inline the two `view` overloads in `bindings.cpp`; `unpack_row` local unless a later kernel reuses it; shorter comments in `arcs.hpp` and `arcs.cpp` that restate REQ-G2D-042, 043 and `angle.hpp`.

## Blockers


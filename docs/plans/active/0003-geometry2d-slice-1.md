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
- [ ] 6. **Distances and circles.** `closest_point`, `circle_through`. REQ-G2D-091 to 101. Size: about 150 + 250.
- [ ] 7. **Area and orientation.** `signed_area` (`area.cpp`), with the exact sum. REQ-G2D-001, 002, 128 to 133. Size: about 180 + 250.
- [ ] 8. **Point in region.** `point_in_region`, `point_in_region_exact` (`region.cpp`). REQ-G2D-134 to 150. Size: about 350 + 350.
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

- Step 4 spec review, spec gap for Peter: no lower bound on t and no declared maximum step count; today only a count beyond an int is refused (`ValueError`). Operation tolerances give at most about 55 000 steps per circle (t_flat >= 1.1e-5 mm, r < 6711 mm).

- Step 4 simplifier, nice-to-have (about 7 lines): the full-circle branch of `_axes_in_sweep` (the shared-octant branch covers it); its private docstring; `max(steps, 1)` in `arc_steps`; the `kernel` alias in `_flatten.py`; a shared sampling helper for the flattening tests.

- Step 4: twice the first local test run right after a kernel rebuild failed once and passed on every repeat (six full runs, three `tools/check` runs, 10 000-case property runs); the failure was not captured. Likely Hypothesis's default deadline of 200 ms in the local `dev` profile on the first, slower kernel call (CI's `ci` profile has none). Capture it next time before changing anything.

- Step 3 spec review, spec gaps for Peter: (1) small bulges on long chords give huge radii (1000 mm chord, b = 1e-8: r = 2.5e10 mm), where the rounding of |P − C| exceeds eps_len and a valid bulge comes back `ARC_INCONSISTENT`; a radius or bulge limit is not in research 01; (2) an arc with P0 = P1 and a tiny sweep passes `make_arc` and `curve_rows` as a one-row loop; its removal is REQ-G2D-046, a later part.

- Step 3 simplifier, nice-to-have (about 4 lines): one-line unwrap in `arc_from_bulge`; the loop ends of `curve_rows` computed once; `NDArray[Any]` parameters instead of `starts.view(np.int64)`. Step 3 test audit, minor: the REQ-G2D-197 cases rely on NumPy's default int64 and check no message; small chords with small bulges give lines, which prove nothing about the centre.

- Step 2 test audit, optional: REQ-G2D-042 with P1 moved inward; a negative case for REQ-G2D-049 (P1 = P0 with a sweep of 2π − 0.1).

- Step 2 spec review, spec gaps for Peter: (1) the r ≤ eps_len rule comes before the radial check, so an arc with r ≈ 0 and P1 far away becomes a long line; requiring |P1 − C| ≤ r + eps_len first would catch it (research 01's "within 2r of the segment" assumes P1 on the circle); (2) REQ-G2D-043 should state the evaluated form difference·r ≤ eps_len; (3) the arctangent has no requirement of its own (tested under REQ-G2D-018); (4) REQ-G2D-027 says nothing of NaN or shapes, and for very short non-zero vectors the bound underflows, so they are not parallel, unlike the zero vector; (5) the modulo-2π reading accepts a tiny positive sweep whose P1 lies just clockwise of P0.

- Step 2 simplifier, nice-to-have (about 15 lines): inline the two `view` overloads in `bindings.cpp`; `unpack_row` local unless a later kernel reuses it; shorter comments in `arcs.hpp` and `arcs.cpp` that restate REQ-G2D-042, 043 and `angle.hpp`.

## Blockers


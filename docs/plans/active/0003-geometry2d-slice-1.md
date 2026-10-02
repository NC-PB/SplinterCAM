# Plan 0003: geometry2d, slice 1

<!-- Lives in docs/plans/active/ while work is ongoing, then moves to docs/plans/completed/.
     The agent updates the progress log at the end of every session, before stopping. -->

- Goal: `geometry2d` meets slice 1 of its SPEC: exact predicates, lines and arcs with their validation, bulge conversion, distances and closest points, circle through three points, flattening with a known error side, area and orientation, point in region, cleanup and bounding boxes.
- Specs: `src/splintercam/geometry2d/SPEC.md` (slice 1); `src/splintercam/foundation/SPEC.md` (REQ-FND-001, the grid unit)
- Research: `docs/research/01-foundations.md`
- Branch: one branch and one pull request per step, `claude/cool-ramanujan-evgci4` for step 1 and `claude/cool-ramanujan-evgci4-step-N` after it, each based on the one before
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
- [ ] 4. **Flattening and bounding boxes.** `flatten` (`flatten.cpp`), `bounding_box`, the step limit π/2 as a declared parameter in foundation's defaults file (a foundation SPEC change), the shared exact test of which axis directions lie in a sweep. REQ-G2D-102 to 113, 126, 213, 214, 230; the tests of REQ-G2D-231 and 232 start here and grow with each step. Size: about 220 + 300.
- [ ] 5. **Exact predicates** (needs `predicates.c` in `kernel/vendor/`). The C build of the vendored file through our own wrapper, strict float flags, `exactinit` at load; `orient2d`, `incircle`, `in_arc_circle`, the (q_y − c_y)² comparison, `two_sum`, `two_product`; the build guard. REQ-G2D-005 to 011, 013 to 018, 021 to 024. Size: about 300 + 350.
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
- 2026-10-02: the largest flattening step π/2 is an entry of foundation's `tolerance_defaults.toml` (REQ-G2D-230), so geometry2d reads no file of its own (docs/dev/03, rule 5).

## Progress log

<!-- Newest first. What was done, what tools/check reported, what is next. At most about 30 lines per session;
     numbers go into tables. Above 300 lines, older entries move to an archive file next to the plan. -->

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

- Step 4: twice the first local test run right after a kernel rebuild failed once and passed on every repeat (six full runs, three `tools/check` runs, 10 000-case property runs); the failure was not captured. Likely Hypothesis's default deadline of 200 ms in the local `dev` profile on the first, slower kernel call (CI's `ci` profile has none). Capture it next time before changing anything.

- Step 3 spec review, spec gaps for Peter: (1) small bulges on long chords give huge radii (1000 mm chord, b = 1e-8: r = 2.5e10 mm), where the rounding of |P − C| exceeds eps_len and a valid bulge comes back `ARC_INCONSISTENT`; a radius or bulge limit is not in research 01; (2) an arc with P0 = P1 and a tiny sweep passes `make_arc` and `curve_rows` as a one-row loop; its removal is REQ-G2D-046, a later part.

- Step 3 simplifier, nice-to-have (about 4 lines): one-line unwrap in `arc_from_bulge`; the loop ends of `curve_rows` computed once; `NDArray[Any]` parameters instead of `starts.view(np.int64)`. Step 3 test audit, minor: the REQ-G2D-197 cases rely on NumPy's default int64 and check no message; small chords with small bulges give lines, which prove nothing about the centre.

- Step 2 test audit, optional: REQ-G2D-042 with P1 moved inward; a negative case for REQ-G2D-049 (P1 = P0 with a sweep of 2π − 0.1).

- Step 2 spec review, spec gaps for Peter: (1) the r ≤ eps_len rule comes before the radial check, so an arc with r ≈ 0 and P1 far away becomes a long line; requiring |P1 − C| ≤ r + eps_len first would catch it (research 01's "within 2r of the segment" assumes P1 on the circle); (2) REQ-G2D-043 should state the evaluated form difference·r ≤ eps_len; (3) the arctangent has no requirement of its own (tested under REQ-G2D-018); (4) REQ-G2D-027 says nothing of NaN or shapes, and for very short non-zero vectors the bound underflows, so they are not parallel, unlike the zero vector; (5) the modulo-2π reading accepts a tiny positive sweep whose P1 lies just clockwise of P0.

- Step 2 simplifier, nice-to-have (about 15 lines): inline the two `view` overloads in `bindings.cpp`; `unpack_row` local unless a later kernel reuses it; shorter comments in `arcs.hpp` and `arcs.cpp` that restate REQ-G2D-042, 043 and `angle.hpp`.

## Blockers

- Step 5: `predicates.c` is not in the repository, and this environment cannot download it.

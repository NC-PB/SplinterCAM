# Plan 0005: offset2d, the offsets and Booleans of topic 02 (draft)

<!-- Lives in docs/plans/active/ while work is ongoing, then moves to docs/plans/completed/.
     The agent updates the progress log at the end of every session, before stopping. -->

- Goal: a module `offset2d` offsets the machining regions of geometry2d by a clearance t ≥ 0 on a side (D-058, D-132) and joins and subtracts regions (the Booleans of topic 02), with source IDs and fixed nodes carried through for the arc fit (D-023, D-084).
- Specs: `src/splintercam/offset2d/SPEC.md` (Reviewed by Peter, 2026-10-08; decisions in `src/splintercam/offset2d/DECISIONS.md`)
- Research: `docs/research/02-offsets-and-booleans.md` (L4, reviewed 2026-10-08; PR 45)
- Branch: one pull request per step from `main`, never stacked (docs/dev/07)
- Owner: Peter Burgener; agents: Claude Code sessions
- Status (2026-10-08): draft. Peter decided the module (DEC-G2D-038), approved its entry and budget and answered both questions (DEC-G2D-040). Research 02 is in; Peter reviewed the SPEC and answered its four questions (DEC-OFF-001 to 006), which releases steps 2 to 9. REQ-OFF-032 waits for pull request 47.

## The module

The entry in `architecture/modules.yaml` (approved by Peter, 2026-10-08, and applied):

```yaml
  offset2d:               { layer: 1, kernel: true,  depends_on: [foundation, geometry2d], kernel_includes: [geometry2d], research: ["02"], budget: 1500 }
```

- Layer 1, beside geometry2d (Peter, 2026-10-08): a module imports only lower layers, or same-layer modules named in its `depends_on`; all `depends_on` together form no cycle; no strategy imports another strategy. `tools/arch-check` checks exactly these three (DEC-G2D-040).
- `kernel_includes: [geometry2d]`: its C++ includes the headers geometry2d's SPEC names as its kernel interface (`kernel/exact.hpp`, `kernel/distance.hpp`, `kernel/grid.hpp`) and links their sources; a change to them is an interface change, Peter's (DEC-G2D-040).
- Kernel: the Clipper2 offset runs in C++ (`ClipperOffset`, Clipper2 2.0.1, as geometry2d's grid bridge).
- Budget 1500 NLOC, an estimate to be revised at the SPEC cut. For scale: geometry2d's grid bridge and region code measure about 400 NLOC (`kernel/grid.cpp`, `_grid.py`, `_build.py` and their bindings). The offset adds the clearance and side of D-132 with its bias and rounding margin, round and miter joins, the PolyTree built inside the offset call so the rounding is paid once (DEC-G2D-026), the Booleans, and source IDs and fixed nodes through all of them.
- geometry2d's own entry dropped research "02": `research: ["03"]`; "03" leaves with the medial-axis module when that is planned.
- The grid span: 2^26 grid units, about 6.7 m at u = 0.0001 mm, is enough for release 1 (Peter); larger machines come later through a coarser grid unit per job, not now. It becomes a declared foundation parameter in its own pull request.

## Questions for Peter

Both answered on 2026-10-08 (DEC-G2D-040): 1 as proposed, with the headers named in geometry2d's SPEC as its kernel interface; 2 as proposed.

1. **How does offset2d's kernel reach geometry2d's grid bridge and exact predicates?** The rule kernels-private lets only a module's own Python call its kernel. Proposal: offset2d's C++ includes geometry2d's kernel headers (`grid.hpp`, `exact.hpp`) and links its sources, listed as a kernel dependency in `modules.yaml`; the alternative, moving the grid bridge into offset2d, would leave geometry2d's region and fallback calling another module's kernel.
2. **Where does the region's Clipper2 call live?** `build_region` (geometry2d) makes the PolyTree today. DEC-G2D-026 prefers building it inside the offset call. Proposal: geometry2d keeps `build_region` for the region itself; offset2d takes the flattened loops and builds its PolyTree in its own call, so geometry2d does not depend on offset2d.

Answered on 2026-10-09 (Peter): yes, as proposed, before step 6 (DEC-G2D-042, done in step 3's pull request); the PUBLIC Clipper2 link kept.

3. **`canonical` has no final tie-breaker** (`src/splintercam/geometry2d/kernel/grid.cpp`, older code, now part of offset2d's interface). It sorts loops by their smallest grid point, then signed area, with an unstable sort. Two loops that touch at their smallest point with equal areas (two mirror-image triangles meeting at a corner) then come out in Clipper2's order, which depends on the input order, against DEC-G2D-036's "bit for bit in both orders" and REQ-OFF-038. On the machine the region is the same; only the order of the loops, and so of the passes topic 04 makes from them, could differ between two runs of the same part drawn in another order. Proposal: a final tie-breaker that compares the rotated loops point by point, with a test in both input orders, as a small geometry2d change of its own before step 6 (an interface change under DEC-G2D-040, so yours).

## Steps

<!-- Each step has a size estimate (kept code and tests, raw added lines). At 50 % over it, stop and ask, as for a
     timebox (docs/dev/12, section 3). Every pull request: at most 400 added lines of non-test code. -->

Released with the SPEC (Peter, 2026-10-08). Steps 2 and 3 follow his answers 2 and 1 (DEC-OFF-002, 001).

- [x] 1. **SPEC review.** Peter reviews `src/splintercam/offset2d/SPEC.md` and answers its four questions; the requirements become `Reviewed`. Size: docs only.
- [x] 2. **foundation: the offset's parameters** (Open question 2). `ToleranceSet.arc_tol_mm`, `offset_bias_grid_units` and `join_steps_max` in `tolerance_defaults.toml`, and the diagnostic code `CANCELLED` (warning), with a foundation SPEC change (DEC-OFF-002). Size: about 50 + 70.
- [x] 3. **geometry2d: the grid interface** (Open question 1, DEC-G2D-040). `frame_of`, `to_grid`, `split_pinches`, `shared_points` and `canonical` move from `kernel/grid.cpp` into `kernel/grid.hpp`, and `kernel/distance.hpp` gains the segments within eps_len of the nearest distance (DEC-OFF-001), with a geometry2d SPEC change; behaviour unchanged, geometry2d's tests pass as they are, new tests for the new entry. If an include directory is added for offset2d, `_quoted` in `tools/lib/arch_kernels.py` must resolve it (arch-check resolves quoted includes relative to the file only). Size: about 120 + 120.
- [x] 4. **The region offset.** Scaffold `src/splintercam/offset2d/` (`tools/new-module` or by hand, as Peter says), `offset_region` with the loop tree and `flatten_loops` (REQ-OFF-021), the one `ClipperOffset` call (022), t = 0 through `build_region` (024), the span refusal (018), the band (025), integer topology (026), `OFFSET_EMPTY`, `OFFSET_FAILED`, `ValueError`, `CANCELLED` (039 to 042, 013, 014). Tests 6, 7, 8, 10, 11, 18 and 9's oracle. A new algorithm: its own pull request. Size: about 380 + 500.
- [x] 5. **The orientation guard** (REQ-OFF-023). Test 21. It replaces step 4's refusal of a hole holding the extreme point (DEC-OFF-008), and `test_an_island_holding_the_extreme_point_fails_until_the_guard_exists` becomes test 21 proper. Size: about 120 + 200.
- [x] 6. **Source IDs with classes, pinch points, order** (REQ-OFF-034, 037, 038, 011, 010). Tests 14, 17, 19. Size: about 150 + 350.
- [x] 7. **Booleans** (REQ-OFF-030, 031, 033, 035, and the pinch tests of 036). Tests 1 to 5 and 15, Vatti note test 7. The stock update: `machined_area` and `stock_layer` (REQ-OFF-032, 044; research 02's answer to RR-001, released 2026-10-09). Test 22. Size: about 200 + 400.
- [x] 8. **Open chains** (REQ-OFF-027 to 029). Tests 12 and 13. Size: about 260 + 350.
- [ ] 9. **Golden case and differential.** `pocket-island-touching-wall` (test 16; a person approves the golden files); ADR 0010 (accepted 2026-10-09) applied: the group `test-oracle` with shapely in `pyproject.toml` and `uv.lock`, installed by `tools/bootstrap` (DEC-OFF-003); then test 20. Size: about 0 + 250.

Total: about 1230 added lines of code (about 1050 NLOC) and 2080 of tests, in nine steps.

## Progress log

### 2026-10-10, step 8, part 2 (one side of a chain)

- `offset_chain_side` (REQ-OFF-028; DEC-OFF-018) in `kernel/chain_side.cpp`: the chain grown with Butt ends, every output edge labelled tool side, other side or cap from the nearest chain point, runs of tool-side edges as pieces. Measured on the way: a cap's middle lies on the chain's end, so rounding labelled caps at random (a three-quarter arc took both caps into its piece); caps are now found by the cut line within 3u. Research 02's test 12: the line and two arcs on both sides, the sharp V; its C gives one open piece on the inner wall, by research 02's own cap rule (RR-002 item 7); a closed piece tested on an omega with a narrow neck. Mutations: the side flipped fails five tests, runs never turned round one. `noqa: PLR0913` on the SPEC's six-argument signature, for Peter.

### 2026-10-10, step 8, part 1 (the grown chain)

- `grow_chain` (REQ-OFF-027, 029, 031; DEC-OFF-017) through the grow call of the stock update, moved into `_chain.py`: research 02's test 13 (the stadium, its area between radius t and the band's top), a chain with an arc (every point within t of the true chain inside, the vertices in the band of the flattened chain), `CHAIN_CLOSED` when the ends meet and the chain encloses an area (an out-and-back path is open; a point grows into a disc, for rapids and drilling alike), the refusals, cancellation, the span. Mutation: growing by t alone fails three tests; dropping t_flat from δ is caught by none, since a ≥ t_flat at every tolerance (measured, DEC-OFF-017). `tests/offset2d/unit/test_offset_region.py` split (363 and 125 lines). Hypothesis found a coordinate of 5.6e-308 in the touching-island generator (an angle drawn near 0), outside the exact predicates' range: `tests/support/offset2d_strategies.py` now draws on a 2^-20 grid, as geometry2d's property tests do.

### 2026-10-09, step 7, part 3 (the stock update)

- `machined_area` (REQ-OFF-032, 031) and `stock_layer` (REQ-OFF-044; DEC-OFF-015): each operation's centre paths flattened by `build_chain` and grown together by R − (t_flat + 6u) with round joins and ends (`kernel/grow.cpp`, for step 8 too), the IDs over each chain there and back; the raw layer minus all machined areas in one Difference call. Research 02's test 22 (a closed pocket pass and an open profile with an arc; never less stock than the exact geometry leaves, too much only within 2·t_flat + a + 12u; both orders give the same arrays), the band of straight, arc and closed paths, R ≤ m refused, the span with 2·δ. Mutations: growing by R fails three tests, a union instead of the difference fails test 22. Reviews: the spec review found test 22 could not see a wrong m and REQ-OFF-032's band wrong on the centre side of an arc (corrected, DEC-OFF-015; the tests now sample near R and the raw boundary, at tol 0.01 and 0.05, both arc directions); the cnc review found every approximation errs toward more stock and named two callers' duties, which Peter accepted on 2026-10-10 with drilling cycles counted as their expanded feed moves and a warning on a failed stock layer (DEC-OFF-016); the test audit's untested branches all have tests now. Step 7 done in three pull requests (the shared code, the Booleans, the stock update).

### 2026-10-09, step 7, part 2 (Booleans)

- `boolean` in one `Clipper64` call (REQ-OFF-030, 031, 035, 036, 039; DEC-OFF-014): research 02's tests 1, 3, 4, 5 and 15, the Vatti note's test 7 (material wins an overlap with air), the span refusal, an empty intersection; test 2 as a property test (10^4 points outside 3u of either operand's edges). Test 15's second case: the hole's vertex lies in the middle of the outer edge, which Clipper2 does not split, so it is a touch, not a fixed node (left to the arc fit with research 02's Open items; RR-002 item 6); its triangle given CCW.

### 2026-10-09, step 7, part 1 (shared code)

- Before the Booleans: the output stage of every Clipper2 call moved from `kernel/offset.cpp` into `kernel/result.cpp` (`finish_region`, `IdSource`: pinch split, area-0 drop, canonical order, mm, class-tie IDs), and the Python side's output arrays with their retry, the status as diagnostics and the replay log into `_results.py`; the binding shares `write_region` and `id_source`. Behaviour unchanged (all offset2d tests pass as they are). Its own pull request, since moved lines count as added: with the Booleans the step measured 474 lines; the Booleans and the stock update follow in their own pull requests.

### 2026-10-09, step 6 (source IDs, order, translation)

- Source IDs by the class tie (REQ-OFF-034, DEC-OFF-013): `nearest_ties` within eps_len, then material, cleared, air, then the lowest ID; research 02's test 14 (failed first: the top-left join took the air ID; a mutation back to the first candidate fails it again). Pieces of area 0 dropped (037; code only, no input known to produce one). The cleared class tested too. Bit-identical arrays twice and in another loop order (038, 011). Translation, test 17, as a property test: every vertex within 3u of the other result's boundary; vertex to vertex differed by 0.1 mm, because round joins do not keep their vertices (DEC-OFF-013, REQ-OFF-010 reworded, ours).
- Peter's answer on REQ-OFF-018: refused before Clipper2 and before any exact test on the grid, the input's span plus 2·|δ| before rounding, the guard's part after (DEC-OFF-012); research 02, step 1, reworded in the same PR. Wording questions like this are box 2 from now on (Peter).
- Reviews: the spec review found a negative source ID broke the tie (fixed); the new check of each edge's distance to its source edge found a step 4 bug: the IDs came from the cleaned loops, whose clean-up drops the collinear joint between an arc and its tangent side, so every side of a rounded box took an arc's ID 28 mm away; the IDs now come from the loops before the clean-up (DEC-OFF-013). The ID tests use IDs against the class order, a negative one among them; the area-0 test is exact (integer collinearity); a changed loop count under translation must lie within 6u of a critical distance. Measured `nearest_ties`: growing a finely flattened rounded box (tol_min) 25 ms at t = 1 mm, 89 ms at t = 50 mm, against research 02's target of 10^4 segments in 50 ms; for the performance work.
- REQ-OFF-036's pinch tests come with the Booleans in step 7 (research 02's test 15 is a union and a difference); the code (split, fixed nodes) is in place since step 4.

### 2026-10-09, step 5 (the orientation guard)

- The guard triangle of research 02, step 3 (REQ-OFF-023, DEC-OFF-011) replaces step 4's refusal: test 21 now matches the offset oracle with the guard gone, and the corner case (an inner loop listed first at its wall's top-left corner, which wins Clipper2's tie because the loop tree keeps the input order) works for air and material; the span check counts the guard. The property tests take the touching island again (test 9 and 10 on every generator).
- Reviews: spec-reviewer (the geometry holds: Clipper2's rule, the shrink always removes the guard, the grown guard stays apart, no overflow). Fixed: the test of a leftover guard could not fail (now the band's top above the flattened input; a leftover guard fails four tests by mutation); exactly one loop removed when growing, none when shrinking (ours); the gap from the declared rounding margin, not the bias; a check that the guard holds the extreme point. Test audit: the test 21 swap is a reversal the SPEC makes, not a weakening; the replay log through a simulated kernel failure; guard sizes 0.5, 3 and 9 mm; a guard just under the span limit accepted. Open for Peter: REQ-OFF-018's wording, since the guard's share of the span is checked on the grid (DEC-OFF-011, provisional).

### 2026-10-09, step 4 (the region offset)

- `src/splintercam/offset2d/` scaffolded by hand (`AGENTS.md`, `CLAUDE.md`, `__init__.py`, `_classes.py`, `_region.py`, `kernel/offset.hpp`, `offset.cpp`, `bindings.cpp`); `offset_region` released for REQ-OFF-013, 014, 018, 020 to 022, 024 to 026, 039 to 043. Tests: 21 unit (research 02 tests 6, 7, 8, 11, 14's shape, 18, 21's shape; clean-up, diagnostics, refusals, the join-step limit) and 2 property (test 10's band against the flattened input, test 9's oracle against the true curves, 10^4 points, at tol 0.01, tol_min and 0.05).
- Measured: research 02's test 21 shape as a region of air inverts the shrink to an empty result (`OFFSET_EMPTY`), which the area check Peter asked for cannot see. So the kernel also refuses, with `OFFSET_FAILED`, a hole holding the extreme point by Clipper2's own rule (DEC-OFF-008); as material the shape is right. Step 5 replaces the refusal with the guard.
- Reviews (simplifier, test-auditor, spec-reviewer, cnc-reviewer): fixed an empty flattened region that crashed (all loops dropped), source IDs of -1 (now `OFFSET_FAILED`), the case of no path with area on the grid (empty, as Clipper2 would grow it), the join-step check after the span check, the replay log (a, u, the bias, the limits), the kind's check, cancellation after `build_region`, the flattening's extra clearance added to t, and the output buffer sized for the round joins. Recorded: `ErrorCode()` never reports in Clipper2 2.0.1 (DEC-OFF-008), the callers' rest-material duty and t > 0 for tool paths (SPEC, Scope). PR with the label `large-change` (Peter, 2026-10-09, at 472 lines of non-test code; 501 after the review fixes).
- Measured: Clipper2's inward offset past an arc's radius is slow on finely flattened input (2100 vertices at tol_min shrunk by 10 mm: 640 ms; grown: 17 ms). For step 6's measurement and research 02's "dense input is reduced first"; the property tests keep 10 examples in a normal run (about 2 to 3 s each) and 1000 under the thorough profile.

### 2026-10-08, step 3 (geometry2d's kernel interface)

- `Frame`, `frame_of`, `to_grid`, `split_pinches`, `canonical` and `shared_points` declared in `src/splintercam/geometry2d/kernel/grid.hpp` with Clipper2's header; `CMakeLists.txt` links Clipper2 PUBLIC so the bindings find it. `nearest_ties` in `kernel/distance.hpp` (every segment within eps of the nearest, as (point, segment) pairs) and its kernel binding: REQ-G2D-242, DEC-G2D-041. geometry2d's tests pass unchanged; new tests `tests/geometry2d/unit/test_nearest_ties.py` and `tests/geometry2d/property/test_nearest_ties_property.py` (an O(n·m) oracle, bit for bit, exact ties by construction).
- No include directory added: `_quoted` in `tools/lib/arch_kernels.py` needs no change for this step. geometry2d measures 3675 NLOC (3610 before; budget 3600, fails above 4320).
- Reviews: two test audits and two spec reviews. Applied: the binding refuses a non-finite query point (a NaN reached a float-to-int cast, undefined behaviour); one scan per query instead of `nearest` plus a second search; `!(best <= limit)` so a NaN never passes; the C++ preconditions written in `distance.hpp` (offset2d must check them itself) and `frame_of`'s and `to_grid`'s in `grid.hpp`; DEC-G2D-041 no longer claims that segment order gives the lowest source ID; tests: distances bit for bit against `polyline_distances`, exact refusal messages, a negative limit, a zero-length segment, the mirror test requires a tie, a fine mesh, and a grid-size regression (mutated by hand: it fails with a grid for the limit alone). Open: question 3 above.
- For step 6: offset2d takes the lowest source ID among the first class's candidates itself; its limit must cover t plus the band of REQ-OFF-025, or an edge gets no ID; the tie is measured to the flattened segments, so an arc edge's ties depend on t_flat (record it in offset2d's DECISIONS.md then). Measure the cost of `nearest_ties` on finely flattened input with a large t.
- 2026-10-09: PR 47 merged; REQ-OFF-032 rewritten from research 02 (Booleans, test 22) as `machined_area`, with `stock_layer` as new REQ-OFF-044, both `Reviewed` (Peter's instruction with his RR-001 answer); they join step 7.
- 2026-10-09: question 3 answered: `canonical` breaks its last tie point by point (DEC-G2D-042). Reproduced first: a pair of tied triangles did not show it (a short sort is an insertion sort), a fan of twenty equal triangles did, for shuffled input; both are tests now. `.claude/worktrees/` (agent worktrees) ignored in `.gitignore` (Peter).
- Next: step 4, once steps 2 and 3 are on `main`.

### 2026-10-08, step 2

- foundation: `ToleranceSet.arc_tol_mm` (REQ-FND-011), `offset_bias_grid_units` and `join_steps_max` in the defaults file (REQ-FND-012), the constant `CANCELLED` (REQ-FND-013); foundation SPEC changed, DEC-FND-001 records the form of `CANCELLED`. At tol_min the floor 2u binds (0.05·tol = 0.000114 mm < 0.0002 mm); at 0.01 and 0.05 mm the share does.

### 2026-10-08, SPEC review

- Pull request 46 merged. Peter answered the four questions as recommended and accepted the deviations: DEC-OFF-001 to 006 in `src/splintercam/offset2d/DECISIONS.md`; every requirement but REQ-OFF-032 `Reviewed`. Step 1 done.
- RR-001 answered in research 02 (Booleans, test 22), pull request 47: REQ-OFF-032 is released from that text after it merges.
- ADR drafted for DEC-OFF-003: `docs/adr/0010-shapely-geos-test-only.md` (Proposed; shapely/GEOS in a test-only group for test 20, D-060). A person decides before step 9.
- Test oracles for steps 4 to 9, written in parallel by a test-designer from the SPEC and research only: `tests/support/offset2d_oracles.py` (d to the true lines and arcs within 64·ε·S, inside on the true curves, the definitions of research 02, Booleans, a seeded sampler outside a band, the band widths from a `ToleranceSet`) and `offset2d_strategies.py` (test 7's nested shapes, pockets with islands, bulged pockets, test 21's touching island); self-tests in `tests/offset2d/` (48), untagged until offset2d code exists. Mutated by hand: each broken rule fails a test.
- 2026-10-09: Peter accepted ADR 0010 (the group `test-oracle`, installed by `tools/bootstrap`, never packaged, no `NOTICE` entry, LGPL only there for `tools/licence-check`); answered question 3 of step 3's review (the tie-breaker in `canonical`, before step 6) and kept the PUBLIC Clipper2 link.
- Next: step 2 (foundation).

### 2026-10-08, SPEC draft

- Research 02 arrived (PR 45). `src/splintercam/offset2d/SPEC.md` drafted with `/research-to-spec`: REQ-OFF-010, 011, 013, 014 and 018 keep the prototype's numbers cited by the research, the new ones run from 020 to 042; draft REQ-OFF-009 (retry) is dropped, as research 02 says. Steps 1 to 9 proposed above.
- spec-reviewer round: six major and six minor findings, all applied (the SPEC's change log); REQ-OFF-043 added for trap 9; REQ-OFF-032 blocked by research request RR-001 (stock update margin).
- Four questions for Peter in the SPEC's Open questions: geometry2d's grid internals into `kernel/grid.hpp`; `arc_tol_mm` and two declared parameters in foundation; shapely for test 20 (an ADR); the function names.
- Next: Peter's review (step 1).

### 2026-10-08, draft

- Written on Peter's answer to plan 0004 (DEC-G2D-038): the module entry and budget proposed, two questions open.
- Peter's answers: entry approved (layer 1, budget 1500 as an estimate) and applied, with the layer rule settled (same-layer dependencies when named in `depends_on`); questions 1 and 2 as proposed; geometry2d's SPEC names its kernel interface (DEC-G2D-040). Next: research 02, then `/research-to-spec`; the first step moves `frame_of` and `to_grid` into `kernel/grid.hpp` as an interface change.

## Backlog

<!-- Nice-to-have review findings and later work: recorded here, not coded in the change that found them. -->

- After step 7: revisit a shared helper for the duplicated code between geometry2d and offset2d, with the Booleans as the third caller (Peter, 2026-10-09): the tail of `grid_region` (back to mm, fixed nodes, source IDs; `src/splintercam/geometry2d/kernel/grid.cpp` and `fill_region` in `src/splintercam/offset2d/kernel/offset.cpp`) and the output-buffer retry (`region_with_fill_rule` in `src/splintercam/geometry2d/_grid.py` and `_kernel_offset` in `src/splintercam/offset2d/_region.py`), about 40 lines. The copies already differ (offset2d's IDs use the class tie), so a shared helper needs parameters for both. Sharing changes geometry2d's kernel interface (DEC-G2D-040): Peter's.
- Performance: the ID search grows with t (growing a finely flattened rounded box at tol_min: 25 ms at t = 1 mm, 89 ms at t = 50 mm), and Clipper2's inward offset past an arc's radius is slow on dense input (640 ms for 2100 vertices shrunk by 10 mm); research 02's target is 10^4 segments in 50 ms, with dense input reduced first.
- RR-002 (`docs/research/REQUESTS.md`): five corrections to research 02, for Project Spike.


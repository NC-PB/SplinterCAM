# Plan 0004: geometry2d, slice 2 (proposal)

<!-- Lives in docs/plans/active/ while work is ongoing, then moves to docs/plans/completed/.
     The agent updates the progress log at the end of every session, before stopping. -->

- Goal: `geometry2d` turns closed loops of lines and arcs into the machining region of an operation. It builds the loop tree (degenerate, duplicate and crossing loops reported; parents, depths and normalised orientation), the side-correct flattening, and the Clipper2 PolyTree with source IDs and fixed nodes. It also flattens open chains for profiles.
- Specs: `src/splintercam/geometry2d/SPEC.md` (slice 2, cut in step 1 from the drafted requirements under Later parts)
- Research: `docs/research/01-foundations.md`: Loop tree, Kernel arrays (polygon region), Tolerances (resolution chain), Flattening (side rule); tests 7, 16, 19, 21 and 24
- Branch: one pull request per session (docs/dev/07); a step with a new algorithm or over about 100 lines of non-test code gets its own, from `main` after the previous merge, never stacked
- Owner: Peter Burgener; agents: Claude Code sessions
- Status (2026-10-07): approved by Peter with his answers below (DEC-G2D-022); step 1 done and reviewed (DEC-G2D-024 to 027); steps 2 and 3 done; step 4a done; 4b next.

## Questions for Peter before step 1

Answered 2026-10-07: yes to all six, as proposed (DEC-G2D-022).

1. **Scope: offsets in a plan of their own?** The SPEC's Later parts put "the topic 02 offsets and the D-132 kernel changes" into slice 2, and `architecture/modules.yaml` gives geometry2d research 02 and 03. But `docs/research/` holds only 01, so there is no research for the offsets to cite. Proposal: this plan builds regions only (topic 01). The offsets follow in plan 0005, once research 02 is in the repository (through `/research-to-spec`, your review).
2. **Ellipse and spline edges stay in Later parts.** Proposal: slice 2 handles loops of lines and arcs only. The rules for spline and ellipse edges (REQ-G2D-120 to 123; the t/2 parts of 124 and 125; the u band of replaced edges) wait until those curve types exist. Here `build_region` and `build_chain` return an extra clearance of 0.
3. **Clipper2 enters with this plan.** `build_region` needs the PolyTree (REQ-G2D-176) and the rule 5 fallback needs a Clipper2 difference (169). So the grid bridge (re-centre, round to u, the 2^26 span refusal; REQ-G2D-029, 030, 031, 033, 034) comes here, without the offset itself. Agreed?
4. **REQ-G2D-019 (same decisions for any thread count)** stays in Later parts: release 1 kernels are single-threaded (DEC-G2D-001).
5. **Module budget:** slice 2 is estimated at about 1300 NLOC. Proposal: raise the geometry2d budget from 1700 to 3000 NLOC in step 1. The reason is the loop tree, the Clipper2 bridge and the region arrays; see the estimates below.
6. **The interface names of research 01, Interfaces** (`loop_tree`, `build_region(loops, kind, ctx)`, `flatten_loops`, `build_chain`) are proposals (ours). Shall step 1 keep them?

## Steps

<!-- Each step has a size estimate (kept code and tests). At 50 % over it, stop and ask, as for a timebox
     (docs/dev/12, section 3). Every step: at most 400 added lines of non-test code per pull request. -->

- [x] 1. **SPEC cut for slice 2.** Release the drafted requirements chosen by the answers above, with their tests from research 01. Mark the rest Later parts. Record the interface, failure modes and diagnostics (`LOOP_DUPLICATE`, `LOOPS_CROSS`, a span refusal); raise the budget in `modules.yaml`; spec-reviewer round. Size: docs only.
- [x] 2. **Polygon region arrays and the flattening of curve-row loops.** `points`, `loop_starts`, `source_ids` and fixed-node flags, checked before any kernel work (REQ-G2D-183 to 187). The flattening of a loop of curve rows holds each joint once and gives each vertex its row's ID (199, 200). The side rule for regions of each kind, material or air (115, 116, 119, 127). Research 01 test 16. Size: about 250 lines of code + 350 of tests.
- [x] 3. **Topology flattening and batched distances.** The inscribed flattening within u with the kernel's own sine and cosine, for topology only (152). u and t_topo come from the `Context` (026, 029). A kernel for point-to-polyline distances in batches, which the loop tree and the probes need; it replaces Python loops (backlog of plan 0003, step 6). Size: about 250 + 300.
- [ ] 4. **Loop tree I: cleaning and the pair tests.** Split (2026-10-08) into 4a: cleanup, area tests, duplicates (155 to 159; done); 4b: crossings between loops and the depth rule (160 to 163, 237); 4c: self-crossings (238). Each its own pull request, opened after the one before merges. Per loop: cleanup, the area test and the 1.5·t_topo·L test (155 to 157). Duplicates within t_topo, the first in input order kept (158, 159). Crossings by exact segment tests with their points, counted only when deeper than t_topo, and touching loops accepted (160 to 163, 237, 238). Research 01 tests 7 and 19. Size: about 300 + 400.
- [ ] 5. **Loop tree II: parents, depths, normalisation.** The containment probes in their order (164 to 168), depth and orientation (174, 175), a winding of 1 inside normalised regions (151), and independence of tol (154). Research 01 test 7. Size: about 250 + 350.
- [ ] 6. **The Clipper2 bridge.** Re-centre on the bounding box and round to u (033); refuse a span of 2^26 grid units or more with an error diagnostic (034); the resolution chain property, every output vertex within 2.83 grid units of the input polylines and point in region unchanged beyond t_topo (030, 031). Research 01 test 21. Size: about 200 + 300.
- [ ] 7. **The rule 5 fallback.** The Clipper2 difference with NonZero, and the tie rules for loops tested both ways (166, 169 to 173). Research 01 test 24. Size: about 150 + 300.
- [ ] 8. **`build_region`.** The PolyTree of the side-correct flattened, normalised loops (118, 176, 177); compared with the loop tree as point sets and by depth parity (178, 179); topology from the integer result only (032); source IDs by the nearest input edge (180); pinch points split by exact integer tests and marked as fixed nodes (181); an extra clearance of 0 (124, lines and arcs). Size: about 350 + 400; split into 8 and 8b if the review fixes push it past 400.
- [ ] 9. **`build_chain` for open chains.** The tool's side as the air side of every arc (117), and an extra clearance of 0 (125, lines and arcs). Size: about 100 + 150.

Total: about 1850 added lines of code (about 1300 NLOC) and 2550 of tests, in nine steps; the steps with a new algorithm get a pull request each, the rest share session pull requests (docs/dev/07).

## Decisions

- 2026-10-03: proposed order: arrays and flattening first (everything else consumes them), the loop tree before Clipper2 (its float rules are the contract the PolyTree is checked against), `build_region` last. Each step is independently testable on `main`.

## Progress log

<!-- Newest first. What was done, what tools/check reported, what is next. At most about 30 lines per session;
     numbers go into tables. Above 300 lines, older entries move to an archive file next to the plan. -->

### 2026-10-08, step 4a: cleanup, area tests, duplicates

- `screen_loops` (REQ-G2D-154 to 159, 236): rules 1 to 3 on the topology flattenings, the thinness test on exact sums (`polygon_area_length`), duplicates against the kept loops only. Choices in DEC-G2D-030.
- Step 3's pull request 38 merged with a failing sanitize job: libasan preloaded without libstdc++ aborted on the first kernel exception. Fixed in pull request 39 (`tools/lib/cmd_test.py` preloads libstdc++; sanitizer reports reach the log).
- `tools/check`: PASS (11 of 14). Next: 4b.

### 2026-10-08, step 3: topology flattening and batched distances

- `topology_flattening` (REQ-G2D-152, 029): every arc inscribed within u, its vertices turned with the kernel's new `basic_sin_cos`, the same bits on every platform (pinned in a test). `polyline_distances`: capped point-to-polyline distances through a sorted uniform grid; `segment_distance` now shared with point in region. Choices in DEC-G2D-029.
- The backlog's shared sweep kernel is not needed by polyline distances; it stays in the backlog for the arc distances of later steps.
- Reviews: simplifier (trims taken; one sine and cosine for every flattening declined, DEC-G2D-029), test-auditor (missing cases, input guards, tighter bounds, REQ-G2D-239 and 240 so the helpers do not claim 158 and 168), spec-reviewer (blocker reproduced and fixed: a near-vertical edge beside a column boundary was missed; cast overflow, empty loop_starts and the portable circumscribed cosine fixed; REQ-G2D-152 states P1's allowance).
- Property tests: 10 000 cases each passed (`HYPOTHESIS_PROFILE=thorough`).
- `tools/check`: PASS (11 of 14). Next: step 4.

### 2026-10-07, step 2: polygon regions and the flattening of curve-row loops

- `polygon_region` (REQ-G2D-183 to 187, `REGION_INVALID`), `flatten_loops` with the side rule (115, 116, 119, 127) and the `LoopTree` type; kernel `row_vertex_counts` and `flatten_rows` (199, 200). Choices in DEC-G2D-028.
- Reviews: simplifier (6 of 9 taken), test-auditor (missing cases added: strided input, t from the `Context`, reversed arcs, step limit, overflow, slack from REQ-G2D-110), spec-reviewer (reproduced and fixed: a 2-vertex loop from a shallow arc in a pocket at tol = 0.05 mm, a zero-length row repeating a vertex; the binding now refuses counts that could write past its buffer).
- Property test: 10 000 cases passed (`HYPOTHESIS_PROFILE=thorough`, 427 s, 4 samples per segment); default run 2.0 s. Research 01 test 16 rendered and checked by eye: every flattened arc lies on the air side.
- `tools/check`: PASS (11 of 14; arch-check, trace-check, licence-check not written yet). Next: step 3.

### 2026-10-07, Peter's answers to the SPEC cut

- Pull request 34 merged. Peter answered the four open questions: crossings count only when a loop reaches more than t_topo into the other on both sides (new REQ-G2D-237, 238); Positive fill rule (176, 177 released); the PolyTree's rounding goes to plan 0005, preferably inside the offset's kernel call; the deviations from research 01 approved. DEC-G2D-024 to 027; research 01, rules 4 and 7 and tests 7 and 21, updated.
- His instruction: questions inside the module are decided as "(ours)" with reasoning; only safety and scope go to him.
- Step 4 grows by REQ-G2D-237 and 238: the depth of a crossing along the pieces between crossings, and the Seifert resolution of self-crossings (the nesting of cycles reuses step 5's probes, so 238 may move to step 5).
- Spec-reviewer and test-auditor on the answers: the first depth rule (probe points) missed a T of slots 1 mm deep, and the one-crossing split of a self-crossing was undefined for several crossings and wrong for a sliver; both reproduced, both rules rewritten (DEC-G2D-024). Second round: the bow-tie of area 0 was dropped before its crossing test, the 0.0015 mm fishtail hid winding −1, the pairing rule was ambiguous; all reproduced, 238 rewritten (resolution before the area tests, depth cover for cycles, balanced pairing). Measured by dense sampling: 88 tangent placements touch, T crosses, pokes of 0.5 and 2·t_topo touch and cross.
- Next: step 2.

### 2026-10-07, step 1: the SPEC cut

- Released REQ-G2D-026, 029 to 034, 115 to 119, 124 and 125 (clearance 0), 127, 151 to 181, 183 to 187, 199, 200 and the new 234 to 236 (`build_chain`'s rows, `REGION_EMPTY`, order of diagnostics); 176 and 177 held. 182 stays in Later parts with curve transforms. Interface, failure modes (`REGION_TOO_LARGE`, `REGION_FAILED`, `REGION_INVALID`, `REGION_EMPTY`), glossary terms. Budget 1700 → 3000 NLOC in `architecture/modules.yaml`. Choices in DEC-G2D-023.
- Spec-reviewer round: 1 blocker, 8 major, minors; all taken. Reproduced before acting: [0, 10]² and [5, 15] × [0, 10] give no proper crossing and winding 2; a spike tip as first probe makes a nested loop a root; the blocker (REQ-G2D-178 at t_topo against flattened arcs) by the chord's sagitta.
- Measured: the u-flattenings of a circle tangent inside another cross properly in 42 of 44 placements (open question 1).
- Test audit: no test or golden file touched, slice 1 requirements only extended; its gaps taken (REQ-G2D-235, 236, invariant properties, the deviations from research 01 as question 4).
- Open questions for Peter in the SPEC: 1 touching curves cross in their topology flattenings (step 4); 2 the fill rule where flattened loops overlap, Positive proposed, against research 01, rule 7 (step 8); 3 the PolyTree's rounding against D-132's bias (plan 0005); 4 the deviations from research 01 in REQ-G2D-030, 119, 178, 179.
- Later steps take on: basic-operation sine and cosine for the topology flattening (step 3, REQ-G2D-152); the 2^26 limit as a foundation parameter and Clipper2 under the strict float flags (step 6).
- `tools/check`: PASS (11 of 14; arch-check, trace-check, licence-check not written yet). Next: Peter's review; then step 2.

### 2026-10-07, approval

- Peter approved the plan and answered yes to all six questions: offsets in plan 0005 after research 02 is in the repository; lines and arcs only; Clipper2 with its grid bridge enters here; REQ-G2D-019 stays later; the budget goes to 3000 NLOC in step 1; research 01's interface names are kept. Recorded as DEC-G2D-022.
- Next step: 1, the SPEC cut. Stop after it for Peter's review.

### 2026-10-03, proposal

- Drafted from the SPEC's Later parts, the draft requirements of commit d1a0949 (REQ-G2D-019, 026, 029 to 034, 115 to 127, 151 to 187, 198 to 200) and research 01, Loop tree. Nothing implemented.
- Next step: Peter's answers and approval, then step 1.

## Backlog

- From plan 0003: the sweep test exists four times (`_box.py`, `_distances.py`, `region.cpp` twice); a shared kernel would stop them drifting apart. Worth doing before step 3 adds distance code.
- From plan 0003: the region kernel holds the interpreter lock for n points × m rows; long kernels of this plan (loop tree, Clipper2 calls) need the release and the cancellation check of the kernel rules.

- From step 3: `polyline_distances` releases the interpreter lock but takes no cancellation flag yet (`.claude/rules/kernels.md`); add it with the other long kernels.
- From step 3: REQ-G2D-168 projects vertices onto the nearest segment, so step 5 needs `polyline_distances` to return that segment's index too (ties to the lowest index, for determinism).

## Blockers

- None.

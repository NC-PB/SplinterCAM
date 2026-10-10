# Decisions: offset2d

<!-- The permanent record of why this module is built the way it is. Rules: docs/dev/05, "Module decision records".
     Write each entry in the same commit as the change that makes the decision. After merge only the Status
     line changes; a changed decision is a new entry that supersedes the old one. IDs are never reused. -->

## DEC-OFF-001: geometry2d's grid and distance internals become its kernel interface

- Date: 2026-10-08; decided by: Peter (answer 1 to the SPEC's open questions, after pull request 46)
- Status: Active
- Decision: `frame_of`, `to_grid`, `split_pinches`, `shared_points` and `canonical` move from geometry2d's `kernel/grid.cpp` into `kernel/grid.hpp`. geometry2d's `kernel/distance.hpp` gains an entry that returns every segment within eps_len of the nearest distance, so offset2d can apply the class tie of REQ-OFF-034. Both changes are one change to geometry2d's interface (DEC-G2D-040), with a geometry2d SPEC change (plan 0005, step 3).
- Why: both modules then re-centre, round, split pinch points and order loops with one implementation, bit for bit (REQ-OFF-036, 038). `nearest_segments` returns one segment, the lower index on an exact tie, which cannot give the tie candidates.
- Rejected: copies of the five functions in offset2d (two implementations that must stay bit-identical); the tie decided by `nearest_segments`' lower index (against D-059).
- Where: SPEC, Open questions 1 and REQ-OFF-034; `docs/plans/active/0005-offset2d.md`, step 3.

## DEC-OFF-002: the offset's parameters and `CANCELLED` live in foundation

- Date: 2026-10-08; decided by: Peter (answer 2)
- Status: Active
- Decision: `ToleranceSet` gains the property `arc_tol_mm`, a = max(0.05·tol, 2u); `tolerance_defaults.toml` gains `offset_bias_grid_units = 3` (D-132) and `join_steps_max = 65536` (prototype REQ-OFF-014); `CANCELLED` (warning) is declared in foundation as the code every module returns on cancellation (plan 0005, step 2).
- Why: foundation already computes a for the budget (`_tolerance.py`); a second copy of the formula in offset2d could drift. Declared parameters keep the numbers out of kernel code (D-049, REQ-OFF-042). Cancellation concerns every module, not offset2d alone.
- Rejected: offset2d computing a from the defaults itself; `CANCELLED` as an offset2d code.
- Where: SPEC, Open questions 2, REQ-OFF-041, 042; foundation SPEC (step 2).

## DEC-OFF-003: shapely and GEOS for test 20, through an ADR, in the last step

- Date: 2026-10-08; decided by: Peter (answer 3)
- Status: Active
- Decision: ADR 0010 (`docs/adr/0010-shapely-geos-test-only.md`, accepted by Peter on 2026-10-09) records D-060: shapely and GEOS in the dependency group `test-oracle`, installed by `tools/bootstrap`, never packaged, no `NOTICE` entry since GEOS is not distributed; `tools/licence-check` accepts LGPL only in that group. The group is added in plan 0005's last step, followed by test 20. The oracle tests 2 and 9 come first.
- Why: an independent reference for the offsets as point sets (D-060), without a licence risk for what ships.
- Rejected: shapely as a runtime dependency; the group optional with test 20 skipping outside CI (Peter, 2026-10-09).
- Where: SPEC, Open questions 3 and Test plan; plan 0005, step 9.

## DEC-OFF-004: the interface of release 1; the side follows from the kind; closed chains refused

- Date: 2026-10-08; decided by: Peter (answer 4)
- Status: Active
- Decision: the names and types of the SPEC's Public interface stand for release 1. `offset_region` takes no side: a region of air shrinks, a region of material grows. A closed chain given to `grow_chain` or `offset_chain_side` is refused with `CHAIN_CLOSED`.
- Why: the other two side combinations put the side-correct flattening's error, up to t_flat, on the part's side, a gouge. A closed chain is a loop, and the caller decides whether it is a pocket wall or an outside profile.
- Rejected: a `Side` argument for release 1. Topic 25's "tool outside a drawn boundary" will get its own function when that operation is planned, not now (Peter).
- Where: SPEC, Public interface, REQ-OFF-020, 029, Later parts.

## DEC-OFF-005: the deviations of the SPEC draft from research 02

- Date: 2026-10-08; decided by: Peter ("accepted, the SPEC is the contract")
- Status: Active
- Decision: the band is measured from the flattened input, t_flat wider against the true curves; `grow_chain` adds t_flat to δ, so its band is t_flat wider than research 02's; `offset_region` runs `cleanup` on the flattened loops before the kernel (REQ-OFF-043, trap 9); the remaining choices marked "(ours)" in the SPEC stand.
- Why: the spec-reviewer round of 2026-10-08 (SPEC change log): the research measured the band from Clipper2's input without saying so, wrote δ for chains of lines, and assumed a cleanup geometry2d does not do on the side-correct flattening.
- Rejected: research 02's figures unchanged, which an oracle against the true curves would fail by up to t_flat, and which under-covers a rapid past an arc.
- Where: SPEC, Requirements and change log.

## DEC-OFF-006: the stock update without chaining

- Date: 2026-10-08; decided by: Peter (answer to RR-001, research 02, Booleans and test 22, pull request 47)
- Status: Active
- Decision: no chaining. The machined area of each operation comes from its own centre paths grown by R − (t_flat + 6u) in one call; a stock layer is the raw layer minus all machined areas in one Difference call. REQ-OFF-032 is released with research 02's text once pull request 47 is on `main`.
- Why: the 3u shrink of the earlier research text was itself a second Clipper2 call on a rounded region and did not cover two roundings (RR-001).
- Rejected: shrinking a rounded machined region by 3u; updating a layer by successive differences.
- Where: SPEC, REQ-OFF-032; `docs/research/REQUESTS.md`, RR-001.

## DEC-OFF-007: the details of the stock update

- Date: 2026-10-09; decided by: ours (plan 0005, the release of REQ-OFF-032 and 044 after pull request 47; spec review)
- Status: Active
- Decision: `machined_area` flattens each centre path with geometry2d's `build_chain`, which also takes a closed pass, on either air side, and offsets all paths of the operation in one `ClipperOffset` call with JoinType Round and ArcTolerance a; it raises `ValueError` when R ≤ m = t_flat + 6u. Test 22's upper bound on the extra stock is 2·t_flat + a + 12u, not research 02's 2·t_flat + 12u.
- Why: research 02 names EndType Round and δ but not the joins; a miter or square join would make the machined area larger than the swept area, and the stock would lose material that is really there. Round joins with ArcTolerance a put their chords up to a inside the circle, so the machined area is up to a smaller: still the safe side, but the extra stock grows by up to a, which research 02's bound leaves out. Either air side works for the flattening, since m pays for t_flat on the side it falls. With R ≤ m, δ would be 0 or negative and the area meaningless.
- Rejected: a added to m (it would make the area smaller still, for no safety gain); a research request (the reasoning is complete; research 02 can take the corrected bound at its next review).
- Where: SPEC, REQ-OFF-032, 044 and Failure modes.


## DEC-OFF-008: the inverting hole is refused, and the area check guards the rest

- Date: 2026-10-09; decided by: Peter (the area check as a guard, not a proof; the test of test 21's shape), ours (the refusal of the inverting hole, from the measurement below; plan 0005, step 4)
- Status: Active for the area check; the refusal of the inverting hole is superseded by DEC-OFF-011 (2026-10-09)
- Decision: before the `ClipperOffset` call the kernel finds the path Clipper2 takes as the outer loop, with Clipper2's own rule (the largest y, then the smallest x; the first path on a tie; paths of area 0 skipped; SRC-122, `GetLowestClosedPathInfo`), and returns `OFFSET_FAILED` when that path is a hole. After the call it checks the area: a shrunk region is not larger, a grown one not smaller, than its input, and the result's signed area is not negative, each allowing the bias of 3 grid units per unit of input perimeter; otherwise `OFFSET_FAILED`. The area check is a guard against a whole inverted result, not a proof that the offset is correct.
- Why: research 02, The kernel call, step 3. Measured 2026-10-09: research 02's test 21 shape as a region of air (an island of radius 5 tangent inside a wall of radius 20 at its top) puts the island's flattening at y = 20.00039 above the wall's 19.99999, and the inverted shrink came back empty, as `OFFSET_EMPTY`. No area check can tell that from a region that really vanishes, and a pocket would have been skipped without an error. As a region of material the same shape is right: the wall's flattening holds the extreme point. Step 5 replaces the refusal with the guard triangle.
- Spec review (2026-10-09), checked in Clipper2 2.0.1's source: `ClipperOffset::ErrorCode()` is always 0 and the result of the inner union is dropped, so a Clipper2 failure cannot be seen and REQ-OFF-014's "Clipper2 reports failure" is not observable through this call; a failed union during a shrink would come back empty or partial, which only the area check can partly catch (a known limit, recorded here). When every path has area 0 on the grid, Clipper2 makes δ positive: the kernel returns an empty region before the call. Research 02, step 3, says normalised loops pass outer loops first, but `loop_tree` keeps the input order, so an island listed before its wall can win Clipper2's tie and is refused today; step 5's guard must not rely on the order. Correct offsets never fail the area check: a true shrink lies inside its input and a true grow contains it, and islands merging or holes vanishing only push the area further the allowed way. `cleanup` drops vertices but moves none, so it changes the boundary by at most eps_len (1e-6 mm, 0.01u), inside the bias.
- Rejected: the area check alone (it misses the empty inversion above); a bound from the Steiner formula A + L·t + π·t² (it needs convex input).
- Where: `kernel/offset.cpp` (`extreme_path`, `plausible`); `tests/offset2d/unit/test_offset_region.py`.

## DEC-OFF-009: source IDs until step 6

- Date: 2026-10-09; decided by: ours (plan 0005, step 4)
- Status: Superseded by DEC-OFF-013 (2026-10-09, plan 0005, step 6)
- Decision: each output edge takes the source ID of the flattened input edge nearest to its midpoint, through geometry2d's `nearest_segments` within |δ| + bias·u, the band's top (REQ-OFF-025); on a tie the lower segment index. Step 6 replaces the tie with the class order of REQ-OFF-034 through `nearest_ties`.
- Why: every output edge lies in the band, so that reach finds its source; the class tie needs `SourceClasses` in the kernel, which is step 6's work.
- An output edge with no input edge within that reach means the result is not an offset of the input: the kernel returns `OFFSET_FAILED` rather than an ID of -1 (spec review, 2026-10-09).
- Rejected: IDs of -1 until step 6 (consumers would see an incomplete region).
- Where: `kernel/offset.cpp`, `fill_region`.

## DEC-OFF-010: the span check of an offset

- Date: 2026-10-09; decided by: ours (plan 0005, step 4)
- Status: Active
- Decision: the kernel calls geometry2d's `frame_of` with the span limit reduced by 2·|δ|/u, so the input plus 2·|δ| must span less than 2^26 grid units, before any integer is formed (REQ-OFF-018).
- Why: the offset paths reach |δ| beyond the input on every side, and the union inside the call runs on them (research 01, resolution chain, stage 3); `frame_of` already refuses before rounding.
- Rejected: checking the span after `to_grid` (the integers would already be formed).
- Where: `kernel/offset.cpp`.

## DEC-OFF-011: the orientation guard

- Date: 2026-10-09; decided by: ours (plan 0005, step 5), the method from research 02, The kernel call, step 3
- Status: Active
- Decision: when the path Clipper2 takes for the outer loop is a hole (DEC-OFF-008's rule), the kernel adds a CCW triangle of side s = ⌈|δ|⌉ grid units, base s and height s, at the input's left edge, its base 2·|δ| + 2·bias + 1 grid units above the input's top. Its inradius s/(1 + √5) stays below |δ|/2, so a shrink removes it; after the call every loop lying wholly above the input's top grown by |δ| is removed, and more than one such loop is `OFFSET_FAILED`. The guard counts in the span check: the input's height, the guard's height and 2·|δ| must stay below the limit (REQ-OFF-018). The area check of DEC-OFF-008 compares the input without the guard with the result after the removal.
- Why: the apex lies strictly above every input point, so Clipper2's rule picks the guard, an outer loop, and offsets everything the right way round. The gap of more than 2·|δ| + 6u keeps the grown guard apart from the grown input (each grows by |δ| and rounds by up to 3u), so the removal takes only the guard. It handles both triggers found so far: test 21's island whose flattening reaches above its wall (air), and an inner loop listed before its wall at the wall's top-left corner, which wins Clipper2's tie because the loop tree keeps the input order (both kinds).
- Spec review (2026-10-09): the gap is 2·|δ| plus the declared rounding margin of 6 grid units (`rounding_margin_grid_units`, D-132), not twice the bias, so lowering the bias cannot let the grown guard touch the grown input; the removal must take exactly one loop when growing and none when shrinking, stricter than research 02's "at most one" (ours: zero when growing would mean the guard merged with the input); after adding the guard the kernel checks that Clipper2's rule now picks an outer loop. REQ-OFF-018's wording and the guard's span check: DEC-OFF-012.
- Rejected: reordering the paths so an outer loop comes first (a hole above every outer loop, as in test 21, still holds the extreme point); reversing the input and negating δ ourselves (it relies on Clipper2's internal behaviour more than the guard does); keeping the refusal (a valid pocket would fail).
- Where: `kernel/offset.cpp` (`guard_above`, `remove_guard`); `tests/offset2d/unit/test_offset_region.py` (test 21, the corner case for both kinds, the span with the guard); the property tests now include the touching island.

## DEC-OFF-012: when the span is checked

- Date: 2026-10-09; decided by: ours, confirmed by Peter (his answer on pull request 51, 2026-10-09)
- Status: Active
- Decision: REQ-OFF-018 refuses the call before Clipper2 runs and before any exact test on the grid: the input's span plus 2·|δ| is checked before rounding (`frame_of` with the limit reduced, DEC-OFF-010), the guard's part after rounding, both after the overflow check. REQ-OFF-018 and research 02, The kernel call, step 1, say so.
- Why: whether a guard is needed is decided by Clipper2's rule on the grid (DEC-OFF-008), so its share of the span can only be checked after `to_grid`. That is safe: `frame_of` has already ruled out overflow, and nothing exact has run on the grid yet. The earlier wording, "before forming any integer, the guard included", could not be met.
- Spec review (2026-10-09): Peter's wording said "before any exact test on the grid", but Clipper2's orientation rule (DEC-OFF-008), which decides whether a guard is needed, runs on the grid before the guard's part is checked; the wording now says "before Clipper2 runs and before the pinch tests on its result" (ours, by Peter's rule that such wording is decided in the module).
- Rejected: reserving the guard's height for every input (it would refuse inputs that need no guard); deciding the guard on floats before rounding (rounding can change Clipper2's tie).
- Where: `kernel/offset.cpp`, `offset_loops` and `add_guard`; SPEC, REQ-OFF-018.

## DEC-OFF-013: source IDs by the class tie

- Date: 2026-10-09; decided by: ours (plan 0005, step 6), the rule from D-059 and research 02, Source IDs
- Status: Active
- Decision: each output edge takes, among the flattened input edges within eps_len of the one nearest to its midpoint (geometry2d's `nearest_ties`, reach |δ| + bias·u), the first class (material, cleared, air), then the lowest source ID. Python passes each flattened vertex's class beside its ID. An edge with no input edge within the reach fails the offset (as in DEC-OFF-009). Pieces of area 0 left by the pinch split are dropped (REQ-OFF-037). Research 02's test 17 is checked as every vertex within 3u of the other result's boundary, not vertex to vertex.
- Why: D-059 settles ties toward material, so a join between a material edge and an air edge never carries the air tag next to material (trap 7). The tie is measured to the flattened segments, so on an arc edge whether two edges tie within eps_len depends on the flattening; eps_len (1e-6 mm) is far below t_flat, so only true ties (round joins, whose points lie equally far from the shared vertex) count. Measured 2026-10-09 for test 17: the same region at the origin and moved by (10 000, -10 000) mm had 798 and 796 vertices, because a round join's steps start where the rounded corner puts them; vertex to vertex they differed by 0.1 mm, while every vertex lay within 3u of the other boundary.
- Test audit (2026-10-09): two branches no real input reaches stay as assertions, untested: an output edge with no input edge within the reach (every output edge lies in the band, REQ-OFF-025), and a piece of area 0 after the pinch split (Clipper2's union leaves none that we could build); the translation test proves a changed loop count lies within 6u of a critical distance instead of skipping it.
- Found 2026-10-09 by the new check of each edge's distance to its source edge: the IDs were taken from the cleaned loops, and `cleanup` drops a collinear joint, which side-correct flattening of material makes where an arc's end segment lies on the tangent line of the next side; on a rounded box every straight side then took an arc's ID, 28 mm away (a step 4 bug). The kernel now offsets the cleaned loops but takes the IDs from the loops before the clean-up, the input edges of research 02. A negative source ID broke the first version of the tie (-1 meant "none yet"); the tie now marks "none" by its class. Measured: growing a finely flattened rounded box (tol_min) took 25 ms at t = 1 mm and 89 ms at t = 50 mm, as the ID search's cells grow with t.
- Rejected: the lower segment index (DEC-OFF-009; a join could take the air tag); research 02's test 17 vertex to vertex (round joins do not keep their vertices under translation).
- Where: `kernel/offset.cpp` (`assign_ids`), `_region.py`; tests: research 02's test 14 and the translation property test.

## DEC-OFF-014: the Booleans

- Date: 2026-10-09; decided by: ours (plan 0005, step 7)
- Status: Active
- Decision: `boolean` runs one `Clipper64` call on geometry2d's grid, subject a and clip b with the Positive fill rule for both, both operands in one frame, and ends in `finish_region` (pinch split, canonical order, class-tie IDs over the edges of both operands within the reach of 6u, the rounding margin). Edges within 3u (half the margin) of the nearest tie, not within eps_len as for an offset. Two empty operands return an empty region before any frame is taken. An empty result carries `OFFSET_EMPTY` (info), as for an offset. A vertex of one result loop lying in the middle of another loop's edge is not a fixed node. Tests compare output coordinates with exact values within half a grid unit, since back in mm a grid point is the frame's centre plus k·u, rounded.
- Why: the Positive rule on normalised regions equals NonZero and keeps the right side where flattened loops overlap (research 02, Booleans). Both ends of an output edge lie on one input edge rounded to the grid, a crossing within about 1.41 grid units of it, so its middle lies within the rounding margin of that edge (spec review). Two operands from separate calls can round the same wall to points up to 2.83 grid units apart (REQ-G2D-030); measured 2026-10-09: with A's material edge 0.4u from B's air edge, an eps_len window gave the overlap an air side's ID, and A's edge was no candidate at all; within 3u material wins as D-059 asks. Research 02's test 15 asks for the point where a hole touches the middle of an outer edge to be fixed in both loops, but its own Open items leave "a vertex of one loop lying on another loop's edge" to the arc fit (topic 11), as the SPEC's Later parts do; Clipper2 returns the outer edge without a vertex there, so nothing marks it. The test checks the touch and leaves the fixed node to that later work (RR-002). Research 02 lists that test's triangle clockwise; as a region's outer loop it is given counter-clockwise, else the Positive rule cuts nothing.
- The deferred fixed node of test 15's second case stays visible as a strict expected failure (`test_research_02_test_15_wants_the_touch_in_the_middle_of_an_edge_fixed`), which fails CI the day it passes (test audit, 2026-10-09).
- Rejected: eps_len as the Booleans' tie window (it splits ties the rounding makes); splitting outer edges at the vertices of other loops now (the deferred T-junction rule, whose effect on the arc fit is not settled); NonZero for the operands (it would fill overlaps of flattened loops on the wrong side, research 01, rule 7).
- Where: `kernel/boolean.cpp`, `_boolean.py`; `tests/offset2d/unit/test_boolean.py`, `tests/offset2d/property/test_boolean_property.py`.

## DEC-OFF-015: the stock update's details

- Date: 2026-10-09; decided by: ours (plan 0005, step 7), the method Peter's (DEC-OFF-006, RR-001)
- Status: Active
- Decision: `machined_area` flattens each centre path with `build_chain` on the left (DEC-OFF-007) and grows all of an operation's paths in one `ClipperOffset` call (`kernel/grow.cpp`: JoinType Round, EndType Round, ArcTolerance a, δ = R − m, no orientation guard, since Clipper2 guesses orientation only for closed polygons). For the source IDs each chain is given to the tie search there and back (P0 … Pn … P1), so every segment is an edge of a closed polyline with its own ID and no closing edge is invented; the reach is δ plus the rounding margin. `stock_layer` flattens the raw layer as material without `cleanup` (trap 9 concerns offsets, not Booleans) and subtracts all machined areas through `boolean`'s kernel call, their loops given together as one clip.
- Why: geometry2d's distance kernel treats every polyline as closed, which would give an open chain a false edge from its end back to its start; the there-and-back polyline has exactly the chain's segments, twice. The grown boundary lies within [δ − a − 3u, δ + 3u] of the flattened chains (research 02, The kernel call, steps 5 and 6).
- Rejected: an open-polyline mode in geometry2d's `nearest_ties` (an interface change of geometry2d for what the there-and-back polyline does already); `cleanup` on the raw layer (it would only drop collinear joints the union removes anyway).
- Reviews (2026-10-09): the band of REQ-OFF-032 was stated as within 3u of R − m; on the centre side of a flattened arc the boundary lies δ + t_flat + 3u = R − 3u from the true arc, still inside the true sweep, so the band is [R − m − a − 3u − t_flat, R − 3u] (ours). δ must exceed a or a round join has no step, so R ≤ m + a is refused (was R ≤ m, which let `math.acos` fail). Rounding the raw layer to the grid can move its boundary inward by about 0.7u; test 22 allows 1u there, far below the 3 mm of D-062 (ours). Test 22 now samples densely near R from every path and near the raw boundary, and checks "never less stock" from R itself; mutations: m without t_flat fails the arc bands at both tolerances, the raw layer flattened as air fails test 22.
- Where: `_stock.py`, `kernel/grow.hpp`, `kernel/grow.cpp`; `tests/offset2d/unit/test_stock.py`.

## DEC-OFF-016: what the stock update expects of its callers

- Date: 2026-10-09; decided by: Peter (2026-10-10), on the cnc review's findings
- Status: Active
- Decision: `machined_area` takes only the cutting moves whose tool bottom reaches the layer's lowest Z, with the radius the tool sweeps at that Z (for a ball or bull-nose tool smaller than R), never links, lead-ins or ramps above the layer. Drilling cycles count as their expanded feed moves, the drill point included: the radius at the layer's lowest Z, below D/2 inside the point; the caller expands the cycles from the toolpath record (D-052) before `machined_area`. A `stock_layer` call that returns no region (`LOOPS_CROSS`, `REGION_TOO_LARGE`, `OFFSET_FAILED`) is read as all stock: the setup's raw stock layer with nothing subtracted, never as none; the operation then carries a warning, so the user sees why its links are more cautious.
- Why: the cnc review (2026-10-09): a move above the layer's bottom, or the full R of a tool that sweeps less at that depth, would mark material as removed that is still there, and a link planned over it could hit it; reading a failure as "no stock" does the same everywhere. Both choices err toward more stock, which only makes links and air-pass skipping more cautious (research 02, Booleans).
- Rejected: leaving the inputs to the strategies unstated (the module would then promise "never less stock" on inputs it cannot check); the canned cycle itself as input (`machined_area` sees paths, not cycles).
- Where: SPEC, Scope (duties of the callers); the strategies of topic 04, the drilling of topic 22 and the link planner of topic 10 when they are built.

## DEC-OFF-017: the grown chain

- Date: 2026-10-10; decided by: ours (plan 0005, step 8)
- Status: Active
- Decision: `grow_chain` flattens the chain with `build_chain` on the left and grows it through the same call as `machined_area` (`grow_flat_chains` in `_chain.py`, `kernel/grow.cpp`) by δ = t + t_flat + a + 3u (REQ-OFF-027), the IDs within δ + 6u. A chain closes when its last flattened point equals its first and its points are not all on one line (geometry2d's exact `orient2d`), so it encloses an area; it is refused with `CHAIN_CLOSED`. A chain out and back (A to B to A) is open. A chain of zero length (a single point: a vertical rapid or a drill's feed seen from above) grows into a disc, with its row's ID; `machined_area` uses the same rule.
- Why: one grow path for link checks and the stock update. Measured 2026-10-10: the budget keeps a ≥ t_flat at every tolerance (tol_min: a 0.0002, t_flat 0.0000113 mm; tol 0.01: 0.0005, 0.000397; tol 0.05: 0.0025, 0.002397; tol 1: 0.05, 0.049897), so a + 3u already covers the flattening of an arc on its convex side; the t_flat in δ (DEC-OFF-005) is a second margin, and a mutation that drops it is caught by no test, which is expected. Growing by t alone fails three tests.
- Spec review (2026-10-10): the first rule, ends equal bit for bit, refused an out-and-back rapid as closed, and a single point failed in the kernel for want of an ID; both fixed and tested. The ends are compared as floats, so +0.0 and -0.0 count as equal, while `build_chain`'s continuity is bit for bit; a chain with such ends is closed here, which only refuses it. a ≥ 2u is checked in all three offsets (`check_arc_tol`), though foundation's `arc_tol_mm` keeps it so and no test can reach the branch.
- Rejected: within eps_len as the closing rule (a chain `build_chain` accepts as open could then be refused as closed); ends equal alone (an out-and-back path encloses nothing).
- Where: `_chain.py`; `tests/offset2d/unit/test_grow_chain.py`.

## DEC-OFF-018: one side of an open chain

- Date: 2026-10-10; decided by: ours (plan 0005, step 8), the side rule from research 02, Open chains; Round ends instead of research 02's Butt ends after the spec review
- Status: Active
- Decision: `offset_chain_side` flattens the chain with `build_chain`, the tool's side as the arcs' air side, merges segments of eps_len or less into a neighbour (a merged segment takes its longest part's ID), grows it in one call with Round ends by δ = t + a + 3u (`kernel/chain_side.cpp` through `grow_chains`), and labels every output edge from all chain segments tied nearest its middle (geometry2d's `nearest_ties` over the chain given there and back): a cap when the nearest point is an end of the chain, within 3u (the bias) of the tangent point for rounding; inside a segment by geometry2d's exact `orient_sign`; at an interior vertex by both segments, either where the vertex is convex toward the tool and both where it is concave. Of tied segments, the tool side wins, then a cap. An edge with no segment within δ + 6u fails the call (`OFFSET_FAILED`): every boundary point lies at δ, so that is a bug, never an answer. Runs of tool-side edges become pieces: a loop all on the tool side a closed piece, every other run an open piece, turned round when the sum of its edges' lengths along their nearest segments is negative (on a sum of 0, when its last edge lies before its first along the chain). Closed pieces are turned by the same rule (DEC-OFF-020), keeping their canonical first vertex. Open pieces come first, by where they start along the chain, then closed ones; ties by the first vertex. `offset_chain_side` keeps the SPEC's six arguments (DEC-OFF-004) with `noqa: PLR0913`, since a changed signature is an interface between modules (Peter's to decide).
- Why: Butt ends cut the band square at the chain's ends, so the area is not "within t of the chain" there: for (0, 0) to (1, 0) to (1, 10), the tool left and t = 3, the wall along the second segment ended 2 mm from the chain's start, a gouge (spec review; the test of the short first segment fails with Butt ends). Round ends give the true area, and research 02's own wording, a cap where the nearest input point is an end, leaves the round end out. A cap's middle lies on an end's circle, so the cap test runs on distances along the segment, not the exact sign, which rounding moved to either side (measured: a three-quarter arc took both caps into its inner piece). A chain run out and back ties both legs at every edge; the lowest index lost the return leg's side (the out-and-back test fails with the first tie). A segment shorter than eps_len has no direction worth an orientation test. Research 02's test 12 expects one open and one closed piece for a C open narrower than 2t with the tool inside: the round ends close the mouth, but the edges there lie nearest the chain's ends and are caps by its own rule, so the inner wall is one open piece from cap to cap, the path a profile inside the C must take. A closed piece arises where the tool side encloses a room away from the ends: an omega whose neck is narrower than 2t, tested instead (RR-002 items 7 and 8).
- Rejected: Butt ends (the gouge); clipping Butt-end pieces to distance δ − 3u from the chain (a second pass over every vertex for what Round ends give at once); the lowest-index tie (the out-and-back chain); the exact parameter 0 at an end for a cap (rounding); a closed piece for the plain C (against the cap rule and the profile); a sort by first vertex alone (the strategy wants the chain's order); a tuple for the chain to fit five arguments (an interface change without Peter).
- Where: `kernel/chain_side.cpp`, `kernel/bindings.cpp`, `_chain.py`; `tests/offset2d/unit/test_chain_side.py`.


## DEC-OFF-019: enclosed pieces of a chain's side

- Date: 2026-10-10; decided by: Peter (cnc review of plan 0005, step 8)
- Status: Active
- Decision: `OpenPaths` carries `enclosed` per piece: a piece on another boundary loop of the grown area than the first open piece's (the one nearest the chain's start). Every closed piece is enclosed, since it is a whole loop; an open piece is enclosed only where the chain's tool side splits over two loops (a chain ending inside a spiral). In release 1 the profile operation does not machine enclosed pieces and gives a warning on the operation with their position ("not reachable from the contour; use a pocket").
- Why: the grown area is everything within t of the chain, so between two of its boundary loops the tool would cross it and cut closer than t; a closed piece is a room the open piece never reaches. offset2d knows the loops, the strategy does not.
- Rejected: `closed` alone (an open piece on another loop is just as unreachable); leaving reachability to the strategy (it would need the grown area again); machining enclosed pieces in release 1 with their own entry (Peter: a pocket's job).
- Where: `kernel/chain_side.cpp`, `kernel/chain_side.hpp`, `_chain.py`; `tests/offset2d/unit/test_chain_side.py`.

## DEC-OFF-020: one milling direction for every piece of a chain's side

- Date: 2026-10-10; decided by: Peter (cnc review of plan 0005, step 8); the split between offset2d and the strategy ours
- Status: Active
- Decision: every piece of the operation, open and closed, runs in the operation's milling direction (climb by default), so climb and conventional never mix within one operation. offset2d turns every piece, closed ones included, to run with the chain (by the summed length of its edges along their nearest segments), so all pieces of one call have the chain on the side away from the tool and share one milling direction; the strategy, which knows the spindle direction and the operation's choice, reverses all pieces of the call or none.
- Why: a closed piece kept its loop's traversal, which depends on whether the loop is a hole or an outer loop, not on the chain, so it could cut climb where the open piece cut conventional. offset2d knows neither the spindle nor the operation, so it cannot pick climb itself.
- Rejected: a milling-direction argument to `offset_chain_side` (offset2d would need the spindle direction, an interface change for nothing the strategy cannot do by reversing); keeping the loop's traversal (the mixing Peter ruled out).
- Where: `kernel/chain_side.cpp`; `tests/offset2d/unit/test_chain_side.py` (the omega both ways round).

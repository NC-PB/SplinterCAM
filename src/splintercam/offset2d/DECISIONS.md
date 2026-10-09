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
- Status: Active, provisional until step 5's guard (REQ-OFF-023)
- Decision: before the `ClipperOffset` call the kernel finds the path Clipper2 takes as the outer loop, with Clipper2's own rule (the largest y, then the smallest x; the first path on a tie; paths of area 0 skipped; SRC-122, `GetLowestClosedPathInfo`), and returns `OFFSET_FAILED` when that path is a hole. After the call it checks the area: a shrunk region is not larger, a grown one not smaller, than its input, and the result's signed area is not negative, each allowing the bias of 3 grid units per unit of input perimeter; otherwise `OFFSET_FAILED`. The area check is a guard against a whole inverted result, not a proof that the offset is correct.
- Why: research 02, The kernel call, step 3. Measured 2026-10-09: research 02's test 21 shape as a region of air (an island of radius 5 tangent inside a wall of radius 20 at its top) puts the island's flattening at y = 20.00039 above the wall's 19.99999, and the inverted shrink came back empty, as `OFFSET_EMPTY`. No area check can tell that from a region that really vanishes, and a pocket would have been skipped without an error. As a region of material the same shape is right: the wall's flattening holds the extreme point. Step 5 replaces the refusal with the guard triangle.
- Rejected: the area check alone (it misses the empty inversion above); a bound from the Steiner formula A + L·t + π·t² (it needs convex input).
- Where: `kernel/offset.cpp` (`extreme_path_is_hole`, `plausible`); `tests/offset2d/unit/test_offset_region.py`.

## DEC-OFF-009: source IDs until step 6

- Date: 2026-10-09; decided by: ours (plan 0005, step 4)
- Status: Active, provisional until step 6 (REQ-OFF-034)
- Decision: each output edge takes the source ID of the flattened input edge nearest to its midpoint, through geometry2d's `nearest_segments` within |δ| + bias·u, the band's top (REQ-OFF-025); on a tie the lower segment index. Step 6 replaces the tie with the class order of REQ-OFF-034 through `nearest_ties`.
- Why: every output edge lies in the band, so that reach finds its source; the class tie needs `SourceClasses` in the kernel, which is step 6's work.
- Rejected: IDs of -1 until step 6 (consumers would see an incomplete region).
- Where: `kernel/offset.cpp`, `fill_region`.

## DEC-OFF-010: the span check of an offset

- Date: 2026-10-09; decided by: ours (plan 0005, step 4)
- Status: Active
- Decision: the kernel calls geometry2d's `frame_of` with the span limit reduced by 2·|δ|/u, so the input plus 2·|δ| must span less than 2^26 grid units, before any integer is formed (REQ-OFF-018).
- Why: the offset paths reach |δ| beyond the input on every side, and the union inside the call runs on them (research 01, resolution chain, stage 3); `frame_of` already refuses before rounding.
- Rejected: checking the span after `to_grid` (the integers would already be formed).
- Where: `kernel/offset.cpp`.

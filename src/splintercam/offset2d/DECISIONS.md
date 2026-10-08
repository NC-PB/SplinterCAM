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
- Decision: an ADR records D-060: shapely and GEOS in a test-only dependency group, never shipped, because GEOS is LGPL. It is drafted in plan 0005's last step, followed by test 20. The oracle tests 2 and 9 come first.
- Why: an independent reference for the offsets as point sets (D-060), without a licence risk for what ships.
- Rejected: shapely as a runtime or default development dependency.
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

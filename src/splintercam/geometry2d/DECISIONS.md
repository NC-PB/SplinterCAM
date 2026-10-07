# Decisions: geometry2d

<!-- The permanent record of why this module is built the way it is. Rules: docs/dev/05, "Module decision records".
     Write each entry in the same commit as the change that makes the decision. After merge only the Status
     line changes; a changed decision is a new entry that supersedes the old one. IDs are never reused.
     DEC-G2D-001 to 015 were moved here on 2026-10-03 from the Decisions list of plan 0003. -->

## DEC-G2D-001: the contract choices of slice 1

- Date: 2026-10-02; decided by: Peter (D-161)
- Status: Active
- Decision: predicates take no `Context`; functions with diagnostics return a `Result` and take a `Context`. `in_arc_circle` returns +1 inside. Arc rows that disagree give `ARC_INCONSISTENT`. D-055 tiers 2 and 3 as proposed. Kernels are single-threaded. `grid_unit_mm` lives on `ToleranceSet`. The draft's proposals for the other slice 1 questions were taken and marked "(ours)" in the SPEC.
- Why: Peter's answers that released slice 1 (plan 0003, Context).
- Rejected: everything outside slice 1 went to the SPEC's Later parts without work (D-159).
- Where: SPEC change log of 2026-10-02; REQ-G2D-022, 231, 232; REQ-FND-001.

## DEC-G2D-002: every sign decision is exact

- Date: 2026-10-02; decided by: Peter (answer 5 of 2026-10-02, D-097)
- Status: Active
- Decision: sign decisions use exact predicates or exact comparisons of doubles.
- Why: a sign from a rounded expression can flip near zero, and two calls on the same geometry then disagree (topology breaks).
- Rejected: the sign of a rounded expression with an epsilon band; a tolerance belongs in the tolerance layer, never in a sign.
- Where: REQ-G2D-005; `kernel/exact.cpp`, `kernel/shewchuk.c`.

## DEC-G2D-003: our own arctangent for decisions and counts

- Date: 2026-10-02; decided by: ours (spec review of plan 0003, step 1), following D-055 tier 1
- Status: Active
- Decision: angles that decide something (the arc angle check, the flattening count) come from `basic_atan2` in `kernel/angle.cpp`, built from correctly rounded IEEE operations and compiled without contraction.
- Why: libm differs between platforms in the last bits, so the same input could give a different number of flattening steps on Windows and macOS; REQ-G2D-232 requires equal counts everywhere.
- Rejected: `std::atan2` or libm `atan2` (platform-dependent); NumPy `arctan2` (may pick SIMD code by CPU); Python `math.atan2` (libm). Do not "simplify" `angle.cpp` back to any of them.
- Where: REQ-G2D-018, 232; `kernel/angle.cpp`, `kernel/arcs.cpp`, `kernel/flatten.cpp`.

## DEC-G2D-004: constructions use libm in C++, never NumPy ufuncs

- Date: 2026-10-02; decided by: ours, following D-055 tier 2
- Status: Active
- Decision: transcendental functions for constructions (not decisions) run in C++ with the platform's libm.
- Why: tier 2 allows small platform differences in constructed values, but the same machine must always give the same result.
- Rejected: NumPy float64 ufuncs, whose results may depend on the CPU's SIMD support on the same platform.
- Where: module AGENTS.md, Local rules; the kernels.

## DEC-G2D-005: a bulge with sagitta at most eps_len gives a line

- Date: 2026-10-02; decided by: ours
- Status: Active
- Decision: `arc_from_bulge` returns a line when the arc's sagitta is at most eps_len.
- Why: such an arc lies within eps_len of its chord, and its far centre would fail the radial check by rounding alone.
- Rejected: building the arc anyway (valid input would come back `ARC_INCONSISTENT`).
- Where: `_bulge.py`; REQ-G2D-188 to 197.

## DEC-G2D-006: the largest flattening step lives in foundation's defaults

- Date: 2026-10-02; decided by: ours
- Status: Active
- Decision: the step limit π/2 is an entry of foundation's `tolerance_defaults.toml`.
- Why: docs/dev/03, rule 5: values are declared in one place, and geometry2d reads no file of its own.
- Rejected: a defaults file or a literal in geometry2d.
- Where: REQ-G2D-230; `_flatten.py`.

## DEC-G2D-007: `predicates.c` stays unchanged, ASan is off for it alone

- Date: 2026-10-03; decided by: Peter (ADR 0009 for vendoring; ASan exception approved 2026-10-03, D-161)
- Status: Active
- Decision: the vendored file is never edited; build quirks go into `kernel/shewchuk.c` and `CMakeLists.txt`. The sanitizer build turns ASan off for `kernel/shewchuk.c` only; UBSan stays on.
- Why: its expansion sums read one element past an input array (`enow = e[++eindex]`) and use it only while `eindex < elen`; ASan reported a stack-buffer-overflow in `orient2dadapt` on CI.
- Rejected: patching `predicates.c` (it would no longer be the reviewed public-domain original); ASan off for the whole module.
- Where: ADR 0009; `kernel/shewchuk.c`, `CMakeLists.txt`. See DEC-G2D-009.

## DEC-G2D-008: the predicates' input range is a precondition, not a check

- Date: 2026-10-03; decided by: Peter (confirmed 2026-10-03, D-161)
- Status: Active
- Decision: exact signs are guaranteed for coordinates that are 0 or have a magnitude in [2^−142, 2^201]; nothing checks this at run time.
- Why: SRC-032 (p. 308) guarantees exact signs only in that range; the first property run found 5e-324 giving the wrong sign, in Shewchuk's orient2d as in ours. Real coordinates in mm never come near it.
- Rejected: a range check on every call (cost on the hottest path for input that never occurs).
- Where: SPEC, precondition; property tests (DEC-G2D-015).

## DEC-G2D-009: buffers handed to `predicates.c` have two spare elements

- Date: 2026-10-03; decided by: ours
- Status: Active
- Decision: every buffer passed to `predicates.c` has two spare elements (`ExactSum`, `Expansion` capacity 24).
- Why: it reads past an expansion's end, and `e[0]` and `e[1]` when it is empty. With ASan off there (DEC-G2D-007) nothing else catches a short buffer.
- Rejected: exact-size buffers.
- Where: `kernel/exact.cpp`.

## DEC-G2D-010: the area's float limits are named constants

- Date: 2026-10-03; decided by: ours
- Status: Active; partly superseded by DEC-G2D-016: the segment terms are now summed exactly on both paths
- Decision: the limits up to which `signed_area` sums in floats (10^6 vertices, 3355 mm) are named constants in `_area.py`. Beyond them the polygon and segment terms are summed exactly by `ExactSum`.
- Why: they only choose a code path in Python and never reach the kernel (SPEC, Tolerance budget).
- Rejected: declared tolerance parameters (users must not tune a proof bound).
- Where: `_area.py`, `kernel/area.cpp`; REQ-G2D-128 to 133.

## DEC-G2D-011: φ − sin φ comes from `angle.cpp`

- Date: 2026-10-03; decided by: ours, following DEC-G2D-003
- Status: Active
- Decision: decisions that need φ − sin φ (the degenerate test of `signed_area`) use `phi_minus_sin` from basic operations, with a series for |φ| <= 1.
- Why: libm `sin` gave platform-dependent `LOOP_DEGENERATE`, and the difference cancels badly for small φ.
- Rejected: libm `sin`.
- Where: REQ-G2D-018; `kernel/angle.cpp`, `kernel/area.cpp`.

## DEC-G2D-012: point in region on arcs

- Date: 2026-10-03; decided by: Peter (D-161)
- Status: Active
- Decision: (1) ON on an arc means an end point, a point of the circle within the sweep by the exact signs of `closest_point`, or a point of the radial connector. (2) An arc whose P1 lies off its circle runs on the circle of radius |P0 − C| to the ray from C through P1 and then radially to P1. (3) The tolerance layer measures an arc to the nearer of the circles of radius |P0 − C| and |P1 − C|.
- Why: P1 may lie up to eps_len off the circle; without the connector the loop is not closed and the result depends on orientation.
- Rejected: research 01's chord-side ON rule (research 01, Point in region, still states it; Peter updates the research).
- Where: REQ-G2D-135, 143, 148; `kernel/region.cpp`, `_region.py`.

## DEC-G2D-013: line distances are taken in both directions

- Date: 2026-10-03; decided by: ours
- Status: Active
- Decision: in the tolerance layer, the distance to a line is computed from both ends and the smaller kept.
- Why: the feet a + t·(b − a) and b + t'·(a − b) round differently, so an edge's orientation decided ON at eps_len.
- Rejected: one direction only.
- Where: REQ-G2D-148; `_distances.py`, `_region.py`.

## DEC-G2D-014: cleanup order and its three-vertex stop

- Date: 2026-10-03; decided by: ours; the three-vertex stop waits for Peter's confirmation (plan 0003, Handover, question 4)
- Status: Active; the three-vertex stop confirmed by Peter on 2026-10-03 (answer 3)
- Decision: `cleanup` runs merge, collinear, spike in that order (research 01, Helpers). A kept vertex carries the vertices merged into it, so a later round merges it only where all of them lie within eps_len. The collinear and spike passes stop at three vertices.
- Why: merging a merged vertex again would let points drift by more than eps_len in total.
- Rejected: merging against the kept vertex alone.
- Where: REQ-G2D-020, 204 to 212; `kernel/cleanup.cpp`.

## DEC-G2D-015: property tests stay inside the predicates' range

- Date: 2026-10-03; decided by: ours
- Status: Active
- Decision: property tests draw coordinates on a 2^-20 mm grid or filter to the input range of DEC-G2D-008 with `assume`, so the oracle comparison stays strict. They run with `HYPOTHESIS_PROFILE=thorough` before each pull request.
- Why: Hypothesis draws floats far below 2^-142 often, which is input outside the contract.
- Rejected: loosening the oracle comparison.
- Where: `tests/` of geometry2d, `tests/support/geometry2d_oracles.py`.

## DEC-G2D-016: the arc term of the area's error bound, and its precondition

- Date: 2026-10-03; decided by: ours, on Peter's request to derive it (answer 1 of 2026-10-03)
- Status: Active
- Decision: the segment terms r̂²·p̂ (p̂ = `phi_minus_sin`) are summed exactly with `ExactSum` on both paths, which also forms each product exactly. Then the computed area Â satisfies |Â − A| ≤ B_poly + 40u·Σ_arcs r·ℓ·min(1, φ²) + u·|Â|, with u = 2^−53, ℓ = r·|φ| and B_poly research 01's polygon bound n·u·(√2·E·L + 3E²) plus the translation's 2u·E·L (float path), or the translation's 2u·E·L alone (exact path). For eps_len ≥ 1e-6 mm (the default) the sign guarantee assumes every arc has r·min(1, φ²) ≤ 10^7 mm and E ≤ 10^9 mm, as documented preconditions without run-time checks (Peter, 2026-10-03).
- Why: the derivation. r̂² = r²(1 + θ) with |θ| ≤ γ4 (two subtractions, two squares, one sum). p̂ = p + e with |e| ≤ 16u·|p| for |φ| ≤ 1 (terms falling by φ²/20, at most nine of them, three roundings per term, truncation below one unit) and |e| ≤ 64u for |φ| > 1 (the sine series on |x| ≤ π stays below 41u, the reduction by the rounded 2π is exact by Sterbenz but 2π̂ is 2.2u off, the final subtraction adds 7.3u). With |p| ≤ |φ|³/6 for |φ| ≤ 1 and |p| ≤ 2|φ| beyond, one arc's share of the area is off by at most 1.8u·r·ℓ·φ² or 36u·r·ℓ, and the rounding of the exact sum (within a rounding unit, `kernel/exact.hpp`) adds u·r·ℓ·min(1, φ²), or 2u if that unit is read loosely; 40 covers both. Underflow (|φ| below about 1e-102) breaks the relative bounds but leaves an absolute error below 1e-200 mm², negligible. On the float path B_poly reaches 0.806·eps_len·L at n = 10^6 and E = 3355 mm, so the arcs may use 0.19·eps_len·L, which holds for r·min(1, φ²) up to 4.3e7 mm; 10^7 mm keeps a factor of four. On the exact path the translation moves A by at most 2u·E·L, 0.22·eps_len·L at E = 10^9 mm. min(1, φ²) lets flat arcs of huge radius through: a bulge of 1e-8 on a 1000 mm chord gives r = 2.5e10 mm but r·φ² = 4e-5 mm.
- Rejected: summing the segment terms in floating point on the float path (its error grows with the arc count, up to 10^6·u·Σ|S|, which large arcs push past eps_len·L); a hand-written compensated sum (`ExactSum` exists and is exact); a run-time check of the precondition or a new diagnostic (Peter: documented preconditions only); a bound without min(1, φ²) (it would refuse flat arcs of large radius that are harmless).
- Where: REQ-G2D-131, 132; SPEC, Public interface; `kernel/area.cpp`; `tests/geometry2d/property/test_signed_area_property.py` (loops with arcs, full circles up to 10^7 mm), `tests/geometry2d/unit/test_signed_area.py`; research 01, Area and orientation (draft in the same pull request).

## DEC-G2D-017: the module budget is 1700 NLOC

- Date: 2026-10-03; decided by: Peter (answer 6 of 2026-10-03)
- Status: Superseded by DEC-G2D-022 (3000 NLOC for slice 2, set in plan 0004, step 1)
- Decision: `architecture/modules.yaml` gives geometry2d a budget of 1700 NLOC, the SPEC's estimate for slice 1. `tools/size-check` reports the module above it and fails it above 2040.
- Why: slice 1 measured 1561 NLOC on 2026-10-03; a budget makes growth visible. The slice 2 plan raises it, and must give a reason.
- Rejected: no budget until slice 2 (growth would go unnoticed); a budget that already counts slice 2 (it would not be based on anything measured).
- Where: `architecture/modules.yaml`; SPEC, Size estimate.

## DEC-G2D-018: a tiny circle gets its radial check before it becomes a line

- Date: 2026-10-03; decided by: ours, on Peter's answer 5 of 2026-10-03 (spec gap of plan 0003, step 2)
- Status: Active
- Decision: when r ≤ eps_len, `make_arc` first checks ||P1 − C| − r| ≤ eps_len (REQ-G2D-042) and returns `ARC_INCONSISTENT` if it fails. Only then does it return the line P0P1, or nothing when P0 = P1. For r > eps_len the order is unchanged: nearly closed, radial check, angle check.
- Why: before this change, an arc with r ≈ 0 and P1 100 mm away became a 100 mm line. Research 01's "within 2r of the segment" assumes P1 on the circle; with the check, the line it returns is at most 3·eps_len long.
- The angle check (REQ-G2D-043) stays skipped for r ≤ eps_len: with any sweep such an arc stays within 2r of P0, so its chord is a faithful replacement.
- Rejected: moving the radial check before the nearly closed rule for every radius (no gain: a nearly closed arc passes it anyway, up to rounding, and it would change the order of a rule that works); a check that P1 lies within 2·eps_len of C (another number for the same thing).
- Where: REQ-G2D-047; SPEC, Public interface (rule order); `_curves.py` (`_tiny_arc`); `tests/geometry2d/unit/test_curves.py`.

## DEC-G2D-019: arcs are valid input up to a radius of 10^9 mm

- Date: 2026-10-03; decided by: ours, on Peter's answer 5 of 2026-10-03 (spec gap of plan 0003, step 3)
- Status: Active
- Decision: arcs, from `make_arc`, `arc_from_bulge` or `curve_rows`, are valid input up to r = 10^9 mm, as a documented precondition with no run-time check. Beyond it a valid arc may come back `ARC_INCONSISTENT`.
- Why: two checks carry rounding that grows with r. The radial check compares |P1 − C| with r, both rounded by about u·r: 1.1e-7 mm at 10^9 mm, 1.1e-6 mm (above eps_len) at 10^10 mm. The angle check binds first for large sweeps: its limit is eps_len/r, 1e-15 rad at 10^9 mm, while one rounding step of a sweep above 4 rad is 2^−50 = 8.9e-16 rad, so a sweep and the kernel's angle one step apart fail beyond 1.13·10^9 mm (spec review; a valid arc from the bulge 4000001090 on a 2 mm chord, r = 2·10^9 mm, is rejected). Measured, coordinates within ±3000 mm: random minor arcs from bulges (chords 0.1 to 2000 mm) none rejected up to 3·10^9 mm, 180 of 549 at 10^10 mm; 4000 random major arcs none rejected at 10^9 mm. Peter named 10^10 mm; the measurement refutes it. We state 10^9 mm. The margin is thin for large sweeps: it holds while `basic_atan2` stays within about 2 rounding units, as measured; REQ-G2D-233's 4 units alone would prove only about 2.8·10^8 mm.
- Rejected: 10^10 mm (a third of valid bulges fail there); 2.8·10^8 mm, the limit REQ-G2D-233 alone proves (Peter may choose it over the measured one); a run-time check or a bulge limit (Peter: documented preconditions only); a radial check scaled by r (it would loosen the eps_len contract of REQ-G2D-042). The tighter limit of `signed_area`, r·min(1, φ²) ≤ 10^7 mm, is DEC-G2D-016.
- Where: SPEC, Public interface; `tests/geometry2d/property/test_bulge_arcs.py` (minor and major arcs up to 10^9 mm never inconsistent).

## DEC-G2D-020: `flatten` expects t ≥ eps_len

- Date: 2026-10-03; decided by: ours, on Peter's answer 5 of 2026-10-03 (spec gap of plan 0003, step 4)
- Status: Active
- Decision: t ≥ eps_len is a documented precondition of `flatten`, not checked. The existing `ValueError` for a step count beyond an int stays.
- Why: below eps_len a flattening is finer than the module can tell apart, and only memory limits the step count. Callers pass t_flat ≥ 1.1e-5 mm or 0.001 mm (research 01, Flattening). At t = eps_len and r = 10^9 mm (DEC-G2D-019) a full circle needs fewer than 2^31 steps, so the int check fires only outside the preconditions.
- Rejected: a `ValueError` for t < eps_len (it would make the int check unreachable and replace a working test's error for no caller's benefit); a declared largest step count (a new foundation parameter that no caller needs yet).
- Where: SPEC, Public interface; `_flatten.py`; `tests/geometry2d/unit/test_flatten.py` (the count at the corner of the preconditions).

## DEC-G2D-021: the arctangent has a requirement of its own

- Date: 2026-10-03; decided by: ours, on Peter's answer 5 of 2026-10-03 (spec gap of plan 0003, step 2)
- Status: Active
- Decision: REQ-G2D-233 states what `basic_atan2` promises: within 4 rounding units of atan2, exact on the axes, the same bits everywhere. The existing tests carry its ID next to REQ-G2D-018 and 043.
- Why: the angle check and the flattening count rest on it, but it was tested only under the requirements that use it, so a change to it had no contract to fail against.
- Rejected: leaving it under REQ-G2D-018 and 043 (the gap); a correctly rounded arctangent (more code, and nothing needs it: the decisions only need the same bits everywhere and a known error).
- Where: REQ-G2D-233; `kernel/angle.cpp`; `tests/geometry2d/unit/test_angle.py`. See DEC-G2D-003.

## DEC-G2D-022: the scope of slice 2

- Date: 2026-10-07; decided by: Peter (approval of plan 0004, yes to its six questions)
- Status: Active
- Decision: slice 2 (plan 0004) builds regions for loops of lines and arcs: the loop tree, the side-correct flattening, `build_region` with the Clipper2 PolyTree and its grid bridge (re-centre, round to u, refuse a span of 2^26 grid units), and `build_chain`. The offsets of topic 02 follow in plan 0005, once research 02 is in the repository. Ellipse and spline edges and REQ-G2D-019 (any thread count) stay in Later parts. The module budget rises from 1700 to 3000 NLOC in plan 0004, step 1. The interface keeps research 01's proposed names (`loop_tree`, `build_region`, `flatten_loops`, `build_chain`).
- Why: `docs/research/` holds only research 01, so the offsets have nothing to cite; no ellipse or spline types exist yet; `build_region` needs the PolyTree and the rule 5 fallback a Clipper2 difference; release 1 kernels are single-threaded (DEC-G2D-001); slice 2 is estimated at about 1300 NLOC.
- Rejected: offsets in slice 2 (no research to implement from); spline and ellipse rules now (no curve types to test them on).
- Where: `docs/plans/active/0004-geometry2d-slice-2.md`; SPEC, Later parts (cut in plan 0004, step 1).

## DEC-G2D-023: the contract choices of slice 2

- Date: 2026-10-07; decided by: ours (D-159), on Peter's answers of DEC-G2D-022; Peter reviews them in the pull request of plan 0004, step 1
- Status: Active
- Decision: the draft's open questions for slice 2 are answered as the SPEC marks "(ours)": loops come in as `CurveRows`; `flatten_loops` is public and returns no diagnostics; `build_chain` takes raw rows of one open chain, checked by the curve-row rules without closure (new REQ-G2D-234); crossing points in `LoopTree.crossing_points`; one diagnostic per loop, in input order; the loop tree cleans the topology flattening, not the rows; normalising reverses rows without validating them again; the region is flat loops (CCW outer, CW holes), only pinch points fixed; probes measured to A's topology flattening, in stored row order; the fallback compares grid areas; source-ID ties go to the lower row index; new codes `REGION_TOO_LARGE`, `REGION_FAILED`, `REGION_INVALID`, `REGION_EMPTY`; the 2^26 span is checked at run time and declared as a parameter. After the spec-reviewer round: when loops cross, the tree holds no loops and `build_region` returns no region; crossings are found exactly also where boundaries pass through each other at a shared vertex or stretch (cyclic order of the edges); probes and later tests come from the cleaned topology flattening; the topology flattening uses the kernel's own sine and cosine, so REQ-G2D-018 covers the loop tree with arcs; REQ-G2D-178 and 179 compare beyond the side-correct flattening (t_flat + 3u, 2·t_flat + 6u) instead of research 01's t_topo; REQ-G2D-176 and 177 are held for Peter; Clipper2 is built with REQ-G2D-014's strict flags. Four questions stay open for Peter (SPEC, Open questions): touching curves crossing in their topology flattenings, the fill rule where flattened loops overlap, the PolyTree's rounding in the budget, and the deviations from research 01 in REQ-G2D-030, 119, 178 and 179.
- Why: plan 0004, step 1 releases slice 2; D-159 lets the draft's proposals stand without asking again. The span is checked, unlike slice 1's numeric preconditions (Peter prefers those documented), because Clipper2 decides in double beyond it and fails silently (research 01, trap 17; draft REQ-OFF-018). The tangent-arc question was measured: the flattenings within u of a circle of radius 5 mm tangent inside one of 10 mm cross properly in 42 of 44 placements of their start points.
- Rejected: returning the other loops when some cross (an island inside a dropped crossing wall loses its parent and flips between material and air); probes from the uncleaned rows (a spike tip outside A made a nested loop a root); libm sine and cosine for the topology flattening (tier 1 lost for arcs); research 01's t_topo in REQ-G2D-178 and 179 (false for any arc region: inscribed chords lie up to t_flat = 12·t_topo inside at tol = 0.05 mm); measuring REQ-G2D-030 both ways (input vertices inside a union have no counterpart); loops as `Sequence[Curve]` (a Python loop per edge, against the split rule); cleaning the rows in the loop tree (cleanup of curve loops is a later part); re-nesting pinch-split parts (the flat region needs none); a `ValueError` for broken polygon regions (they may come from other modules' code, so a diagnostic like `curve_rows`); the 2^26 limit as a documented precondition (see Why); `OFFSET_FAILED` for the region's Clipper2 calls (D-132 gives it to the offset only).
- Where: SPEC, Public interface, Failure modes, Open questions and the slice 2 tables; change log of 2026-10-07.

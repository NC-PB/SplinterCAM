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
- Status: Active; its four open questions answered by DEC-G2D-024 to 027
- Decision: the draft's open questions for slice 2 are answered as the SPEC marks "(ours)": loops come in as `CurveRows`; `flatten_loops` is public and returns no diagnostics; `build_chain` takes raw rows of one open chain, checked by the curve-row rules without closure (new REQ-G2D-234); crossing points in `LoopTree.crossing_points`; one diagnostic per loop, in input order; the loop tree cleans the topology flattening, not the rows; normalising reverses rows without validating them again; the region is flat loops (CCW outer, CW holes), only pinch points fixed; probes measured to A's topology flattening, in stored row order; the fallback compares grid areas; source-ID ties go to the lower row index; new codes `REGION_TOO_LARGE`, `REGION_FAILED`, `REGION_INVALID`, `REGION_EMPTY`; the 2^26 span is checked at run time and declared as a parameter. After the spec-reviewer round: when loops cross, the tree holds no loops and `build_region` returns no region; crossings are found exactly also where boundaries pass through each other at a shared vertex or stretch (cyclic order of the edges); probes and later tests come from the cleaned topology flattening; the topology flattening uses the kernel's own sine and cosine, so REQ-G2D-018 covers the loop tree with arcs; REQ-G2D-178 and 179 compare beyond the side-correct flattening (t_flat + 3u, 2·t_flat + 6u) instead of research 01's t_topo; REQ-G2D-176 and 177 are held for Peter; Clipper2 is built with REQ-G2D-014's strict flags. Four questions stay open for Peter (SPEC, Open questions): touching curves crossing in their topology flattenings, the fill rule where flattened loops overlap, the PolyTree's rounding in the budget, and the deviations from research 01 in REQ-G2D-030, 119, 178 and 179.
- Why: plan 0004, step 1 releases slice 2; D-159 lets the draft's proposals stand without asking again. The span is checked, unlike slice 1's numeric preconditions (Peter prefers those documented), because Clipper2 decides in double beyond it and fails silently (research 01, trap 17; draft REQ-OFF-018). The tangent-arc question was measured: the flattenings within u of a circle of radius 5 mm tangent inside one of 10 mm cross properly in 42 of 44 placements of their start points.
- Rejected: returning the other loops when some cross (an island inside a dropped crossing wall loses its parent and flips between material and air); probes from the uncleaned rows (a spike tip outside A made a nested loop a root); libm sine and cosine for the topology flattening (tier 1 lost for arcs); research 01's t_topo in REQ-G2D-178 and 179 (false for any arc region: inscribed chords lie up to t_flat = 12·t_topo inside at tol = 0.05 mm); measuring REQ-G2D-030 both ways (input vertices inside a union have no counterpart); loops as `Sequence[Curve]` (a Python loop per edge, against the split rule); cleaning the rows in the loop tree (cleanup of curve loops is a later part); re-nesting pinch-split parts (the flat region needs none); a `ValueError` for broken polygon regions (they may come from other modules' code, so a diagnostic like `curve_rows`); the 2^26 limit as a documented precondition (see Why); `OFFSET_FAILED` for the region's Clipper2 calls (D-132 gives it to the offset only).
- Where: SPEC, Public interface, Failure modes, Open questions and the slice 2 tables; change log of 2026-10-07.

## DEC-G2D-024: a crossing counts only when it reaches deeper than t_topo

- Date: 2026-10-07; decided by: Peter (answer 1 to the slice 2 cut); how depth is measured, and the rule for a loop that crosses itself, ours after a spec-reviewer round
- Status: Active
- Decision: crossings between two loops found by the exact tests of REQ-G2D-160 count only when one of the two reaches more than t_topo into the other on both sides: its topology flattening has a point inside and a point outside the other, each farther than t_topo from the other's flattening. It is decided on the pieces between consecutive crossings, each wholly inside or outside: a piece reaches farther than t_topo where the t_topo neighbourhoods of the other's segments do not cover it (one interval per segment pair). A loop's crossings with itself, a stretch run twice in the same direction included, are resolved before the area tests into cycles that touch but do not cross (a Seifert resolution: each incoming end joined to the first outgoing end after it counter-clockwise with balanced ends between, which is unique). A cycle that lies wholly within t_topo of the other cycles is dropped, by the same interval cover; the loop crosses itself only when the kept cycles, nested by the loop tree's own rules, give a winding outside 0 and 1 (depth-0 cycles of different signs, or a child with its parent's sign). A loop with no kept cycle is degenerate; a loop that touches itself takes the sign of its depth-0 cycles.
- Why: touching geometry is real and topic 25 does not prevent it (Peter). The topology flattening lies up to u inside an arc, so the flattenings of a circle tangent inside another crossed properly in 86 of 88 fixed placements (radii 5 and 10 mm, start angles k·π/22 and 0 or π/7); with this rule all 88 touch, a poke of 0.5·t_topo touches and one of 2·t_topo crosses (measured 2026-10-07 by dense sampling). The first draft took the depth from the probe points of REQ-G2D-168; the spec-reviewer showed that a T of slots, [0, 100] × [0, 1] and [29.5, 30.5] × [−10, 50], overlapping 1 mm deep, has no probe point inside the overlap (reproduced), so the depth is measured along the whole flattening. The first draft split a self-crossing loop at one crossing; the reviewer showed it undefined for several crossings and wrong for a twist below t_topo (the fishtail (10, 0), (10, 10.0001), (10.0001, 10), (0, 10), (0, 0) with a sliver of 5e-9 mm², reproduced); the resolution handles any number of crossings. A second review round found three more faults, all reproduced and fixed: the bow-tie (0, 0), (10, 0), (0, 10), (10, 10) has area 0 and was dropped as degenerate before its crossing was tested, so an island inside it would flip to air (hence the resolution before the area tests, and a rule without the loop's total sign); dropping cycles by REQ-G2D-157's average thinness hid the fishtail with legs of 0.0015 mm, whose sliver holds a disc 2.2·t_topo wide of winding −1 (hence the depth cover of REQ-G2D-237 for cycles too, one threshold for both); and "the next outgoing end in cyclic order" maps both incoming ends of an ordinary crossing to one outgoing end (hence the balanced pairing). "One of the two" (ours, from the proposal Peter accepted; his answer says "each"): measured along the whole boundary the two agree except where a loop crosses the other through a neck thinner than 2·t_topo, which "one" reports and "each" would accept.
- Rejected: counting every proper crossing of the flattenings (rejects valid touching islands); flattening topology on both sides of the arc (the flattenings of tangent curves still cross); probe points for the depth (miss deep crossings between long edges, and cost O(n²) per touching pair); splitting a self-crossing loop at one crossing; area tests before the self-crossing test (a bow-tie vanishes with a warning); REQ-G2D-157 as the drop rule for cycles; a stretch run twice crossing outright (a curl of 1e-4 mm would reject a loop the depth principle accepts); an erosion by t_topo through Clipper2 (an offset on a grid of u for a distance of 2u, too coarse).
- Where: REQ-G2D-151, 160, 161, 163, 237, 238; research 01, Loop tree, rule 4.

## DEC-G2D-025: the PolyTree uses the Positive fill rule

- Date: 2026-10-07; decided by: Peter (answer 2 to the slice 2 cut)
- Status: Active
- Decision: `build_region` builds the PolyTree with Clipper2's Positive fill rule. Where no flattened loops overlap, the result equals NonZero's and EvenOdd's.
- Why: loops less than 2·t_flat apart, touching loops with arcs included, can overlap once both are flattened into the air between them. In a pocket, an island over the wall or two overlapping islands give winding −1, which NonZero and EvenOdd count as air although it may be material; an island in a hole of a material region gives winding 2, where EvenOdd is wrong. Positive is right in every case. REQ-G2D-177 compares the three rules only where no flattened loops overlap, on loops more than 2·t_flat + 6u apart and at points farther than t_flat + 3u from every true boundary (ours): an overlap lies within t_flat of a true boundary.
- Rejected: NonZero, research 01's rule 7 until this decision (wrong for winding −1); EvenOdd (wrong for winding 2).
- Where: REQ-G2D-176, 177; research 01, Loop tree, rule 7.

## DEC-G2D-026: the PolyTree's rounding is booked in plan 0005

- Date: 2026-10-07; decided by: Peter (answer 3 to the slice 2 cut)
- Status: Active
- Decision: how the PolyTree's move of up to 2.83 grid units is paid is decided in plan 0005 with research 02. Peter prefers building the PolyTree inside the offset's kernel call, so the rounding is paid once.
- Why: D-132 biases the offset by 3 grid units for one Clipper2 call; `build_region` is a second call before it, and its move toward material could leave the offset at t − 2.66 grid units.
- Rejected: counting both calls against D-132's 6 grid units (they are the band's width, not a margin to share); deciding now, without research 02.
- Where: SPEC, Tolerance budget and Later parts; REQ-G2D-030.

## DEC-G2D-027: approved deviations from research 01 in the comparisons

- Date: 2026-10-07; decided by: Peter (answer 4 to the slice 2 cut)
- Status: Active
- Decision: REQ-G2D-178 compares the loop tree with the PolyTree beyond t_flat + 3 grid units for loops with arcs (t_topo for loops of lines); REQ-G2D-179 applies to loops more than 2·t_flat + 6 grid units apart; REQ-G2D-030 measures the 2.83 grid units from the output vertices; REQ-G2D-119 allows eps_len along arcs the loop tree reversed. Research 01 (rule 7, tests 7 and 21) is updated to match.
- Why: the side-correct flattening moves an arc's boundary by up to t_flat, 12·t_topo at tol = 0.05 mm, so research 01's t_topo cannot hold for arc regions; input vertices inside a union have no counterpart in the output; a reversed arc's radius is |P1 − C|.
- Rejected: research 01's wording as it stood (false for any region with arcs).
- Where: REQ-G2D-030, 119, 178, 179; research 01, Loop tree and Tests.

## DEC-G2D-028: flattening loops of curve rows

- Date: 2026-10-07; decided by: ours (plan 0004, step 2)
- Status: Active
- Decision: the side rule of `flatten_loops` is one NumPy expression on the sweep's sign: on normalised loops the inside lies on the left at every depth, so air lies right of every arc in a region of material (positive sweep circumscribed, negative inscribed) and left in a region of air. The kernel flattens loops in two passes: `row_vertex_counts` (a line adds its P0; an arc its flattening without P1, which the next row starts with), then Python allocates the points and `flatten_rows` writes them with the same code as `flatten_arc`, so a row's vertices equal `flatten`'s bit for bit. Source IDs are `np.repeat(ids, counts)`. A row that ends where it starts, other than a full circle, adds no vertex, so a zero-length row never repeats a vertex (REQ-G2D-185). In a loop that would keep fewer than 3 vertices, an inscribed arc takes at least 2 steps (REQ-G2D-186). The `flatten_rows` binding accepts only counts `row_vertex_counts` can give, adding up to its output's size, so no call writes past its buffer. `PolygonRegion` and `LoopTree` built directly are unchecked, like `Line` and `Arc`; `polygon_region` validates.
- Why: the spec-reviewer found, and we reproduced, a line closed by an arc of sagitta 0.002 mm that flattened to 2 vertices in a pocket at tol = 0.05 mm, and a zero-length line row (which `curve_rows` accepts) that repeated the first vertex; both gave `REGION_INVALID`, and Clipper2 would have dropped the 2-point loop without a word. More steps are finer than t asks and stay in air. The split rule (per-vertex loops in the kernel, per-row choices in vectorised NumPy); outputs allocated in Python (`src/splintercam/geometry2d/AGENTS.md`, Local rules); one flattening code path keeps `flatten` and the regions identical.
- Rejected: rejecting zero-length rows in `curve_rows` (a SPEC change for a case the flattening can absorb); dropping a 2-vertex loop with a diagnostic (`flatten_loops` returns none, and the pocket is real); deciding the side per loop from its depth (normalisation makes it unnecessary); writing each arc's P1 and letting the next row overwrite it (it writes past the last row's slot); a second copy of `flatten_arc`'s loop.
- Where: REQ-G2D-115, 116, 119, 127, 183 to 187, 199, 200; `src/splintercam/geometry2d/_loops.py`, `src/splintercam/geometry2d/_polygon.py`, `src/splintercam/geometry2d/kernel/flatten.cpp`.

## DEC-G2D-029: the topology flattening's sine and cosine, and batched distances

- Date: 2026-10-08; decided by: ours (plan 0004, step 3)
- Status: Active
- Decision: (1) `basic_sin_cos` in `kernel/angle.cpp` reduces by π/2 with fdlibm's split constants (Cody–Waite) and sums nine Taylor terms in Horner form; the topology flattening turns its vertices with it, the side-correct flattening keeps libm (tier 3), so `flatten` and `flatten_loops` stay bit-identical to each other. (2) `polyline_distances` files the segments of closed polylines in a sorted uniform grid of cell side max(2·limit, mean segment length), each segment in the cells its column-wise y-range touches, its end columns bounded by its own ends, and searches two cells around each query (cell indices clamped, so no cast overflows); it returns the distance where it is at most the limit, +inf elsewhere. Segments are measured from both ends (DEC-G2D-013) by `segment_distance`, which point in region now shares (`kernel/distance.cpp`). The binding releases the interpreter lock.
- Why: REQ-G2D-152 asks the topology flattening to give the same decisions on every platform (D-055, tier 1); libm sin and cos differ in the last bit between platforms. The loop tree asks only "within t_topo or not" (REQ-G2D-158, 168), so a capped distance lets the grid stay local: a point within the limit lies at most one cell away, and two cells cover a rounded cell index at a boundary. The spec review found, and we reproduced, that clipping a segment's first column at the computed boundary could leave a near-vertical edge ending within a rounding unit of that boundary filed near one end only (a query 0.25 mm from it got +inf); the end columns now start and stop at the segment's ends. Known limits: the cost grows with the segments sharing a cell, so a dense cluster under long edges approaches brute force; and the reach assumes the limit is many rounding units of the coordinates, which t_topo = 2e-4 mm within the 2^26-grid-unit span (REQ-G2D-034) keeps by orders of magnitude. The mean segment length keeps a long edge from filling thousands of tiny cells. Measured: the sine and cosine stay within 4 rounding units of 1 of libm over ±2π; pinned vertex bits in `tests/geometry2d/unit/test_topology_flattening.py`.
- Rejected: libm for the topology flattening (tier 3 only); `basic_sin_cos` for every flattening (it would drop the flag but move slice 1's `flatten` output, a change of DEC-G2D-004's libm constructions for another step to decide); a correctly rounded sine (more code, nothing needs it); brute force over all segment pairs (10^10 operations for loops of 10^5 segments); an uncapped nearest-segment search (needs a tree; no caller wants the far distance); the shared arc-sweep kernel of plan 0003's backlog (polylines need no sweep test; it stays in the backlog).
- Where: REQ-G2D-029, 152, 158, 168; `kernel/angle.cpp`, `kernel/flatten.cpp`, `kernel/distance.cpp`, `_loops.py`, `_distances.py`.

## DEC-G2D-030: the loop tree's first rules

- Date: 2026-10-08; decided by: ours (plan 0004, step 4a)
- Status: Active
- Decision: `screen_loops` runs rules 1 to 3 per loop in input order, a Python loop over loops (the split rule): `cleanup` of the loop's topology flattening, the area test of REQ-G2D-133 on its rows with `signed_area`, the thinness test on the cleaned flattening's area and length, then the duplicate test against the kept loops before it: both ways, every point of each flattening within t_topo of the other (the interval cover of `crossing_depth`, no far point on either side), only where the bounding boxes' corners lie within t_topo + eps_len of each other, one vectorised test over the kept loops' boxes. The flattening's area and length come from the area kernel's exact path (`polygon_area_length`), so the thinness decision is the same everywhere. Diagnostics carry `location` "loop i" (or "loops i and j" for a duplicate, j removed) and are ordered by the loop they concern, stable. The self-crossing resolution of REQ-G2D-238, which the SPEC places before the area tests, joins in step 4c.
- Why: research 01 compares vertices only; the spec review showed that this takes a square with a V-slot reaching within 1e-4 mm of its wall, and two loops crossing through the same five vertices, for duplicates of the square (the regions differ by about 10 and 50 mm²). Covering every point is the Hausdorff distance and reuses REQ-G2D-237's kernel. A consequence of comparing with kept loops only: squares 0.00015 mm apart chain, so the first and third, 0.0003 mm apart, are both kept and then cross under REQ-G2D-237. REQ-G2D-018 makes the kept loops a tier 1 decision; a NumPy sum may change its order with the CPU's SIMD support (DEC-G2D-004), the exact sum cannot. Comparing a loop only with kept loops makes "the first in input order" well defined when duplicates chain (A, B within t_topo, B, C within t_topo, A, C not).
- The kernel review (2026-10-08): the disc interval is taken about the foot of the centre, which keeps its accuracy on metre-long segments (the 6000 mm squares are tested); a zero-length segment keeps its end discs; an empty b covers only an empty a; `covered_by` stops at the first far part, and `crossing_depth` classifies one point per connected run of far parts and stops once both sides are found. Known: where two covered intervals meet exactly at the limit, rounding can leave a gap a few rounding units wide whose middle counts as far, the same sensitivity as any decision exactly at t_topo.
- Rejected: research 01's vertex test (above); testing segment midpoints as well (cheaper, but not exact); NumPy's shoelace sum for the thinness test (tier 2 at best); comparing with removed loops too (chains would depend on more than the input order); a kernel for the pair loop (loops are few; the per-pair work is already in `polyline_distances`).
- Where: REQ-G2D-154 to 159, 236; `_screen.py`, `_area.py`.

## DEC-G2D-031: crossings between loops

- Date: 2026-10-08; decided by: ours (plan 0004, step 4b), on Peter's answer of DEC-G2D-024
- Status: Active
- Decision: two kept loops whose bounding boxes overlap cross exactly when one reaches more than t_topo inside and outside the other (`crossing_depth`, both ways). Only then are their contact points computed (`contact_points`: the constructed point of each proper segment crossing, and every segment end lying on the other loop's segment, by exact signs; sorted, unique) and one `LOOPS_CROSS` (error) reported, filed with the lower loop. REQ-G2D-160 is restated as finding the points where flattenings meet: if one loop reaches beyond t_topo on both sides of the other, their boundaries must meet, whether properly or through a shared vertex or stretch, so the depth rule alone decides crossing against touching and research 01's cyclic order of edges is not needed.
- Why: one rule for every configuration that the spec reviews raised (proper crossings, the overlapping squares meeting only at vertices and stretches, the T of slots, tangent arcs); the contacts are needed only to report where.
- Rejected: classifying each contact by the cyclic order of its edges (more code, and it still needs the depth rule for tangent arcs); reporting contacts of touching pairs (REQ-G2D-161 reports crossings only).
- Where: REQ-G2D-160, 161, 163, 237; `_crossings.py`, `kernel/distance.cpp`.

## DEC-G2D-032: parents, depths and normalisation

- Date: 2026-10-08; decided by: ours (plan 0004, step 5)
- Status: Active; its provisional "no probe" rule superseded by DEC-G2D-035 (the rule 5 fallback)
- Decision: `loop_tree` runs `screen_loops`, then tests each pair of kept loops whose boxes overlap: one way when their areas differ by more than t_topo·(L_A + L_B), the smaller in the larger, both ways otherwise (`both_ways`). A probe is the first candidate farther than t_topo from A's flattening (`polyline_distances`), located against A's exact rows alone; projections are taken onto the nearest segment of B, the lowest index on a tie. Without a probe the answer is "not contained" for now. A loop's parent is the container whose own containers are all its other containers, and its depth the number of its containers (`nest` in `_contain.py`, shared with REQ-G2D-238's cycles); when no container qualifies (containment in a cycle, or two containers beside each other) the containment is no nesting and the loop and its first container are reported with `LOOPS_CROSS`. A probe located ON A (a spike of A's rows that cleanup removed) passes to the next candidate. A loop whose sign of area (of its cleaned flattening) disagrees with its depth's parity is reversed: rows in reverse order, ends swapped, sweeps negated, IDs with their rows. Any crossing, by REQ-G2D-237 or by two probes (REQ-G2D-173), gives a tree with no loops. The `LOOPS_CROSS` of REQ-G2D-173 is filed with its lower loop among the screen's diagnostics. It is reachable: two squares with notches 0.0003 mm wide at different places touch by REQ-G2D-237, yet each one's probe lies in the other.
- Why: the "no probe" rule, provisional: with both ways tested, a probe in the other direction decides by REQ-G2D-170 anyway, as in research 01 test 24's notched square; with one way, a loop without a far probe lies within t_topo of the other's boundary and the thinness test has most often dropped it, so at worst a sliver of width t_topo is misplaced. Conservative enough to keep working (D-163: never block).
- The spec review (2026-10-08) found, and we reproduced, that the smallest container was not always the innermost one inside the both-ways band (a box got depth 1 instead of 2 and the wrong winding), and that three nearly coincident offset rectangles could contain each other in a cycle, on which the depth walk never ended.
- Rejected: the smallest container as the parent (above); refusing the tree when no probe exists (it would stop test 24's notched pair, which has an answer); "contained" as the provisional answer (it invents nesting for loops beside each other).
- Where: REQ-G2D-151, 153, 154, 162, 164 to 168, 170, 173 to 175; `_tree.py`.

## DEC-G2D-033: a loop's crossings with itself

- Date: 2026-10-08; decided by: ours (plan 0004, step 4c), on Peter's answer of DEC-G2D-024
- Status: Active; the treatment of a stretch run twice is provisional
- Decision: `self_cycles` (`kernel/selfcross.cpp`) finds where non-adjacent segments of the cleaned topology flattening meet by exact signs (a proper crossing's point is constructed once, on one segment, so both strands share it bit for bit), cuts the loop into pieces between these points, and at each point joins every incoming end to the first outgoing end after it counter-clockwise with balanced ends between, the ends ordered by exact half-plane and orient2d tests. It returns the cycles, each with the loop position it starts at, and the points. `self_contact` (`_selfcross.py`) then drops cycles covered within t_topo by the others (two covering each other go together when their signs differ, stay when they agree), nests the rest with `nest` (moved to `_contain.py`, shared with the tree), and calls the loop crossing when its depth-0 cycles differ in sign or a child has its parent's sign. It runs in `screen_loops` after cleanup and before the area tests; a crossing loop gets `LOOPS_CROSS` with its points as the pair (i, i), an all-sliver loop `LOOP_DEGENERATE`, a touching loop the sign of its depth-0 cycles.
- Provisional: a stretch the loop runs twice, and two ends leaving a point in exactly one direction, cannot be ordered at the point, and the loop counts as crossing (a `LOOPS_CROSS`, so the operation stops instead of guessing; D-163, the conservative option). REQ-G2D-238's list wanted a curl of 1e-4 mm to touch; it crosses until the resolution contracts such stretches.
- Why: measured on the SPEC's cases (2026-10-08): the bow-tie, a figure eight, a loop run round twice, a CW petal and the 0.0015 mm fishtail cross; the pinch, the 1e-4 mm fishtail, a pinched annulus and three CCW petals through one point touch.
- Rejected: splitting at one crossing (undefined for several, DEC-G2D-024); dropping cycles by average thinness (DEC-G2D-024); contracting shared stretches now (the order of coincident ends needs its own rule; deferred).
- Spec review (2026-10-08), each case reproduced first: the pairing gave an incoming end twice when the counter-clockwise order from +x starts unbalanced (a figure eight in 3 of its 12 starts and orientations touched); it now starts after the lowest running balance, one pass. A stretch run twice gave no crossing points, and the tree kept the island beside it; its ends are now the points, and `loop_tree` refuses the tree on any error of the screen. Positions equal in (segment, t) keep the lowest point, the same on every platform. A covered cycle stays only as a same-sign mutual pair (the SPEC's text; before, a covered cycle without a partner stayed). A refused grid fallback for the cycles is `REGION_TOO_LARGE` or `REGION_FAILED` on the loop, not `LOOPS_CROSS`. The kernel releases the interpreter lock.
- Open: the contact search tests all segment pairs (O(n²), about a second for 10^4 segments, estimated); a ties-by-rounding case (a constructed point within an ulp of a vertex) counts as crossing, which is conservative. Both are in the plan's backlog. A zero-width slit (a stretch run in opposite directions) crosses for now: asked of Peter in the plan.
- Where: REQ-G2D-160, 161, 238; `kernel/selfcross.cpp`, `_selfcross.py`, `_contain.py`, `_screen.py`, `_tree.py`.

## DEC-G2D-034: the grid bridge

- Date: 2026-10-08; decided by: ours (plan 0004, step 6)
- Status: Active; the span limit as a named constant is provisional
- Decision: each Clipper2 call of geometry2d (`kernel/grid.cpp`) takes the centre of its input's bounding box as the frame, refuses the call when the input spans 2^26 grid units or more in x or y (`REGION_TOO_LARGE`), rounds (x − c)/u to 64-bit integers, runs Clipper2 2.0.1 (`Clipper64`, here a NonZero union) and maps the result back to c + k·u. A failed `Execute` is `REGION_FAILED`. `grid_union`, the union for research 01's test 21, gives source IDs of −1: it is a test entry, not a region builder. The limit 2^26 is a named constant in `_grid.py`, passed to the kernel as a plain value, like the area's limits (DEC-G2D-010).
- Provisional: the SPEC (REQ-G2D-034) asks for a declared parameter in foundation's `tolerance_defaults.toml`, as research 01, Parameters, lists it. That is a second module's change, which needs plan mode and Peter; until then the constant carries its source.
- Why: test 21 measured on 20 random inputs (some features between eps_len and t_topo apart): every output vertex lies within 2.83 grid units of the input, and point in region agrees on input and output farther than t_topo from every boundary; translating the input by metres changes the result by at most a few grid units.
- Rejected: rounding the frame to a multiple of u (no gain: Clipper2 sees integers either way); checking the span after rounding (the refusal must come before any integer is formed).
- Where: REQ-G2D-029, 030, 031, 033, 034; `kernel/grid.cpp`, `_grid.py`.

## DEC-G2D-035: the rule 5 fallback

- Date: 2026-10-08; decided by: ours (plan 0004, step 7)
- Status: Active
- Decision: without a probe of B farther than t_topo from A, `contains` asks the grid (`grid_difference` in `kernel/grid.cpp`): both topology flattenings re-centred together on their box and rounded to u, Clipper2's NonZero Difference B minus A, and its area against B's grid area; B ⊂ A when the difference is less than half. Two loops tested both ways: a probe's result stands over the fallback's; two fallback results go to the smaller difference, the earlier loop on equality (`both_ways`). A refused or failed grid call makes the pair `REGION_TOO_LARGE` or `REGION_FAILED`, an error with no tree; in a self-crossing's cycles it counts, conservatively, as a crossing. `nest` returns a `Nesting` (parents, depths, crossing and refused pairs). `contained_by_difference` and `fallback_inner` expose the fallback for tests.
- Why: research 01, rule 5, and test 24: the square and its notched copy, notch 0.002 mm wide, give the notched loop as the child in either order, its probe standing over the square's fallback; the triangles against [0, 10]² give "not contained" (all of B outside) and "contained".
- Rejected: the provisional "not contained" (DEC-G2D-032); the float area of the flattenings (the fallback's point is a decision on the grid, research 01 rule 5, so the grid's own area).
- Where: REQ-G2D-033, 034, 166, 169 to 172; `_contain.py`, `kernel/grid.cpp`.


## DEC-G2D-036: the machining region from the PolyTree

- Date: 2026-10-08; decided by: ours (plan 0004, step 8), the fill rule Peter's (DEC-G2D-025)
- Status: Active
- Decision: `build_region` runs `loop_tree`, returns no region when the tree is not ok (REQ-G2D-162), flattens the normalised loops side-correct (`flatten_loops`) and takes the region from one Clipper2 call (`grid_region` in `kernel/grid.cpp`): a Positive union on the grid bridge of DEC-G2D-034, its output paths in Clipper2's order. Each output path is split at every grid point it visits twice (`split_pinches`: exact integer keys, the pieces in traversal order, the repeated point's vertices marked fixed, D-084). Each output edge takes the source ID of the flattened input edge nearest to its midpoint, the lowest row on a tie, searched within 2·t_topo by the cell grid of `polyline_distances` (`nearest_segments`); an edge with no input edge within that reach gets −1 (not reached by the tests: REQ-G2D-030 bounds the distance by 2.83 grid units). An empty result is `REGION_EMPTY` (warning). `region_with_fill_rule` exposes the same call with NonZero and EvenOdd for REQ-G2D-177. `grid_union` (DEC-G2D-034) is now this call with NonZero and IDs −1 (simplifier, 2026-10-08: one Clipper2 union path instead of two), so its pinches come back split and fixed too; `FillRule` follows Clipper2's numbering, and the binding refuses any other value.
- Why: measured (2026-10-08): research 01, rule 7's two Clipper2 2.0.1 cases reproduce: an island sharing an edge with its parent becomes a notch of the parent's boundary; an island touching its hole at a vertex comes back as one path through that vertex for some input orders (with the island given first), split into a CW hole and a CCW island with the vertex fixed. Test 7's generator with rounded boxes (lines and quarter arcs), 10,000 cases: the region and the tree classify alike farther than t_flat + 3u from every true boundary; with gaps of 0.05 mm the three fill rules agree and each region loop's orientation is its tree loop's depth parity. A pocket wall and a tangent island give a smaller Positive than NonZero area (winding −1 kept out).
- Spec review (2026-10-08), reproduced first: Clipper2 returned the touching island as one pinched path for one input order and as two paths for the other, so only one order got fixed flags, and the loops kept Clipper2's order, whose intersection sort breaks ties by the standard library (so by platform). Now every vertex at a grid point that two or more output vertices share is fixed, a pinch or a touch of two loops (D-084), and each loop starts at its smallest grid point, the loops sorted by that point and their signed area: both orders give the same region bit for bit. The binding checks the span limit too. Clipper2 is called with `Paths64`, not `PolyTree64`: the region needs only the loops and their orientation (the hole flag of REQ-G2D-179 is the sign of the area), and the output reproduced either way. Open: a vertex of one loop on an edge of another is not flagged; the kernel takes no cancellation flag yet (plan backlog).
- Test audit (2026-10-08): overlap cases now go through `build_region` itself (an island over a pocket wall, two tangent islands, an island over its hole), each against the fill rule that would get it wrong; REQ-G2D-176's 1000 cases became the thorough profile's 10,000 (100 in a normal run keeps the test fast, `.claude/rules/tests.md`); REQ-G2D-235's loop smaller than the grid never reaches the PolyTree, since the thinness test drops every loop below about 12 grid units across first. Not tested: the cover rule of DEC-G2D-033 for a covered cycle without a partner (the resolution joins petals that only touch into one cycle, so we found no loop that gives such a cycle) and the tie by point in `self_cycles`.
- Rejected: the ID reach as a fraction of t_flat (an output edge on a flattened arc lies within rounding of its input edge, but a merged edge's midpoint can lie up to t_topo from both inputs); re-nesting the split pieces into the tree (topic 02, research 01 rule 7).
- Where: REQ-G2D-032, 118, 124, 162, 176 to 181, 235; `_build.py`, `kernel/grid.cpp`, `kernel/distance.cpp`.

## DEC-G2D-037: the open chain of a profile

- Date: 2026-10-08; decided by: ours (plan 0004, step 9)
- Status: Active
- Decision: `build_chain` checks its rows with `curve_rows`' own checks as one loop without the closure test (`checked_rows(..., closed=False)`), so every rule keeps its code and message, and flattens them with the loops' two kernel passes: each arc inscribed when its centre lies on the air side (the side the tool works on; left of the arc for a positive sweep, as `flatten` decides it, REQ-G2D-113), each joint once, the last row's end appended. The 3-vertex minimum of a loop (REQ-G2D-186) does not apply, so each row's vertices equal `flatten`'s bit for bit. `FlatChain` lives in `_chain.py`; its arrays are read-only.
- Why: one set of checks for rows, closed or open, keeps REQ-G2D-234's codes those of REQ-G2D-188 to 193; reusing the loop flattening keeps one kernel path (the module budget).
- Rejected: flattening row by row with `flatten` in a Python loop (the split rule: loops over segments go to the kernel); a separate validator for chains.
- Where: REQ-G2D-117, 125, 127, 231, 234; `_chain.py`, `_rows.py`, `_loops.py`.

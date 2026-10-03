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
- Status: Active
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

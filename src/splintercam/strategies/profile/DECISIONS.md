# Decisions: strategies/profile

<!-- The permanent record of why this module is built the way it is. Rules: docs/dev/05, "Module decision records".
     - Write the entry in the same commit as the change that makes the decision, not at the end and not on request.
     - Newest last. IDs DEC-PRF-NNN are never reused.
     - After merge, only the Status line of an entry changes. A changed decision is a new entry that supersedes the old one.
     - Code that follows a decision a reader would not expect cites its ID in a comment. -->

## DEC-PRF-001: The cut moves are offset2d's polygon as lines; research 22's tests read for it

- Date: 2026-10-27; decided by: ours, from D-023 and plan 0007's scope (Out: arc fitting); part of Peter's review (AQ-016), since it changes the NC program
- Status: Accepted 2026-10-27 for the moves (SPEC Reviewed; Peter, AQ-016, item 1 (a): G1 lines in the slice); the reading of research 22's tests 1, 2 and 5 stays provisional until RR-007 (items 1 to 3) answers
- Decision: the cut moves are the edges of `offset_region`'s loop, written as LINE moves. Research 22 test 1's "four arcs of radius 10" is read as: the loop's points on each fillet lie in the band of the arc of radius 10 about the fillet's centre. Test 2's band "from the contour" is measured against the true lines and arcs, so it is [t, t + a + 6u + t_flat], as offset2d's SPEC states. Test 5's "S at its first vertex" is read with REQ-PRF-013's line-row rule, since every edge of a polygon is a line.
- Why: offset2d returns a `PolygonRegion` (Clipper2 works on polylines, D-058); D-023 brings G2/G3 back through arc fitting (research 11), which plan 0007 leaves out ("output stays lines and the record's arcs as given"). Writing arcs from source IDs alone would be an arc fit of our own with no research behind it.
- Rejected: recovering each fillet as one ARC from its source arc's centre and radius + t (an arc fit in disguise, wrong at round joins and where offset2d merged edges); waiting for arc fitting (the slice would stop here).
- On the machine: each fillet becomes a few short G1 blocks instead of one G2/G3, within the chord tolerance; the profile is never inside t (no gouge). RR-007 asks Project Spike to word the tests for the polygonal path; `src/splintercam/cl/SPEC.md`, Example parts, names arcs for the same case and is not this lane's file.
- Where: REQ-PRF-011, 013.

## DEC-PRF-002: The start point from source IDs

- Date: 2026-10-27; decided by: ours
- Status: Accepted 2026-10-27 for the start on the longest straight side (SPEC Reviewed; Peter, AQ-016, item 4 (a)); the reading of "line row" by source ID and of test 5's first vertex stays provisional until RR-007 (item 3) answers
- Decision: research 22's "the loop's longest line row" is the longest edge of the polygon whose source ID belongs to line rows of the contour only; a tie of length goes to the first edge in offset2d's canonical order (from its smallest point, REQ-OFF-038). With no such edge (a contour of arcs only), S is the loop's first vertex, the smallest point, which lies on the convex hull, so its vertex normal points away from the part.
- Why: after the offset every edge is a line, so the row kind must come from the source: offset2d gives each output edge the ID of the nearest input edge (REQ-OFF-034). The canonical order makes the tie stable (D-055). The reversal for climb must move the IDs with their edges (research 22, trap 2): the CW loop's edge from v(i+1) to v(i) carries the ID of the CCW edge from v(i) to v(i+1); test 1 catches a shift, since the neighbours of a long side are fillet chords.
- Rejected: the longest edge of any source (on a circle the longest chord is arbitrary within rounding, against test 5); the midpoint of the longest input line, offset (wrong where offset2d merged or clipped the edge).
- Where: REQ-PRF-012, 013.

## DEC-PRF-003: The approach point in closed form; a blocked approach falls back to the smallest vertex

- Date: 2026-10-27; decided by: ours, revised after the spec review the same day
- Status: Accepted 2026-10-27 (SPEC Reviewed; Peter, AQ-016, items 7 and 8); provisional against research 22's wording until RR-007 (item 4) says whether Method 5 asks for a free segment S → P
- Decision: P = S + d·n with d the exit of the ray from S out of the stock box grown by c = R + g with round corners (the set of points within c of the box, convex, so the exit is unique when S is inside it, and d = 0 when S is already outside). The exit is found against the four grown sides, a side whose normal component is 0 skipped, and, where the hit lies past a corner, the corner's circle of radius c, with `sqrt` only. At a vertex S, n is the normalised sum of the unit outward normals of the two edges at S. The segment S → P is tested with geometry2d's exact `orient2d` against every edge of the loop but the two at S; if it touches or crosses one, S becomes the loop's smallest vertex and P is found again from there; `PROFILE_APPROACH_BLOCKED` only if that is blocked too. An air gap not above eps_len is its own value error, `PROFILE_AIR_GAP`.
- Why: research 22, Method 5 asks for the smallest distance at which the tool clears the stock box by g, and says P exists because the box contains the part (REQ-PRF-009 makes sure it does); it does not say the line S → P is free. On a non-convex part (a U whose inner side is the longest) the normal crosses the part, and the approach at depth would cut it. Outside the grown region the tool centre is more than t from the part, so a segment that meets the loop only at S cuts nothing but stock. The smallest vertex v is convex, and its vertex normal points into x < v.x, where the loop has no point, so its approach is always free (spec review); that keeps common parts (U, E, comb) working without a start choice the research does not make. The eps_len floor keeps P strictly more than R off the box after rounding, which toolpath's REQ-TP-012 refuses otherwise (DEC-TP-004).
- Rejected: an iterative search along n (needs a step size and a tolerance); trying every line edge by length (a loop over candidates, and a choice for the research, later with a user-picked start); refusing the blocked case (the draft: refuses valid parts when a safe start exists); the axis-aligned grown box (P farther than needed off a corner).
- Where: REQ-PRF-009, 014, 015.

## DEC-PRF-004: Depth checked from the stock top; the pass count guarded against rounding

- Date: 2026-10-27; decided by: ours; part of Peter's review (AQ-016, item 2)
- Status: Accepted 2026-10-27 (SPEC Reviewed; Peter, AQ-016, items 2 and 3 (a)); provisional against research 22's wording until RR-007 (item 5) says where Method 3 measures the depth from
- Decision: `PROFILE_TOO_DEEP` compares the stock top − z_bottom with the flute length, not z_top − z_bottom; for the same reason a first pass that lies more than a_p,max + eps_len below the stock top is refused (`PROFILE_FIRST_PASS_DEEP`; Peter, AQ-016, item 3 (a)). n = ⌈D / a_p,max⌉ is reduced by one where n > 1 and (n − 1)·a_p,max ≥ D − eps_len, and the last level is z_bottom itself. z_top has no default.
- Why: research 22 names "a depth larger than the flute length" without saying from where. Without a stock model the CAM does not know that the material above z_top was removed, so the tool may be in stock from the stock top down to z_bottom; measuring from the stock top is the conservative reading and equals research 22's where z_top is the stock top (every example of the slice). The same unknown makes the first pass cut stock top − z_1, which can exceed the step-down the user set (spec and cnc review). In floats (0.1 − (−0.2)) / 0.1 lands above 3, so ⌈⌉ alone would add a fourth pass of almost no depth; a pass up to eps_len deeper than a_p,max is harmless; without n > 1 a depth below eps_len would give n = 0 (spec review). z_top − n·Δ need not equal z_bottom bit for bit, and the final depth must. Research 22 gives z_top no default, and 0 equals the stock top only when the drawing's datum is there.
- Rejected: z_top − z_bottom (the shank may rub stock above z_top); counting the passes from the stock top when z_top lies below it (changes research 22's levels; an option in AQ-016); a relative epsilon (a magic number); z_top default 0 (the draft).
- Where: REQ-PRF-001, 005, 007, 016.

## DEC-PRF-005: Preconditions raise, outcomes are diagnostics

- Date: 2026-10-27; decided by: ours, as model's REQ-MDL-018 and `cl`'s DEC-CL-002
- Status: Accepted 2026-10-27 (SPEC Reviewed, AQ-016)
- Decision: what `job` and `model` guarantee (the strategy id, the completed parameters, the tool and point, one loop, the operation's tolerance in the context) is checked and raises `ValueError`; what the user can cause with valid single values (the allowance against R, the depths against the stock and the tool, the part against the stock, a blocked approach, a region that is not one loop) is a diagnostic with the operation as location. The nine value checks are all reported before stopping; the geometric ones stop at the first.
- Why: a user cannot fix a broken call; they can fix a depth. Reporting every value error at once spares a round trip, as model does (REQ-MDL-025); after a geometric failure the later steps have nothing to work on. The location is `operation (<name>)`, without model's index (REQ-MDL-027): the strategy is given one operation, not its place in the setup, and names are unique (REQ-MDL-013); `job` may prefix the index (step 7).
- Rejected: one `Result` for everything (every caller would handle bugs as user errors).
- Where: REQ-PRF-002 to 010, 015, 020.

## DEC-PRF-006: No kernel

- Date: 2026-10-27; decided by: ours
- Status: Accepted 2026-10-27 (SPEC Reviewed, AQ-016)
- Decision: the reversal, the edge lengths and the longest line edge, the normal, the blocked check (`orient2d` on arrays of edges) and the pass rows are NumPy over the loop's points; Python loops run over passes only.
- Why: the split rule allows vectorised NumPy; geometry2d's predicates take arrays (REQ-G2D-201). `architecture/modules.yaml` has `kernel: false` for the module.
- Rejected: a Python loop over edges for the start point or the blocked check.
- Where: REQ-PRF-012 to 015, 022.

## DEC-PRF-007: Implementation choices the SPEC leaves open

- Date: 2026-10-27; decided by: ours (plan 0007, step 5, implementation)
- Status: Accepted 2026-10-27
- Decision: (1) the preconditions are checked before `ctx.cancel` at entry, so a broken call raises even when cancelled (as offset2d's `offset_region`). (2) `PROFILE_STOCK_SMALL` is one diagnostic naming every side the part passes ("x min", "y min", "x max", "y max"), the part's box from geometry2d's `row_boxes` (an arc by its true extent, not its ends). (3) P differs from S when the points differ, not when d > 0; only then does a pass get its APPROACH and RETRACT rows. (4) The approach point's exit is first taken against the box grown by c with square corners; where that exit lies beside a side of the stock it is the answer, else the larger root of the corner circle's quadratic, the corner the one the square exit lies past. (5) `PROFILE_TOP_TOO_HIGH` reads z_1 by REQ-PRF-016's formula without building the other levels. (6) The loop from offset2d must turn left at its first vertex, `orient2d` exact, else `ValueError` (a broken promise of offset2d's, not a user error; cnc review).
- Why: (1) a programming error is not an outcome the user can cause, so it must not hide behind a cancel. (2) one value error per check, as REQ-PRF-020 counts them, and every side at once spares a round trip; the ends of an arc would miss a fillet bulging past the stock. (3) a d that rounds away in S + d·n would give zero-length moves at the plunge feed. (4) The rounded grown box lies inside the square one, and the stretch of the ray between the two exits lies in one corner region, so the square exit tells which corner circle the ray leaves by; no search, `sqrt` only (REQ-PRF-014, 022). (5) a tiny step-down must not build a list of every level for a check. (6) climb milling rests on offset2d returning its outer loop CCW (research 22, Method 2); were that ever broken, the reversal would mill conventional and nothing after it would notice. The first vertex is the loop's smallest point (REQ-OFF-038), so it is convex and the exact sign of its turn is the loop's orientation; a float area sum would round to a random sign far from the origin (spec review: a 2 mm part at 1e9 mm) and is a reduction in a decision (D-055).
- Rejected: (2) one diagnostic per side (four codes for one cause); (3) a threshold on d (a magic number).
- Where: REQ-PRF-002, 005, 009, 012, 014, 017, 021.

## DEC-PRF-008: How the tests measure the band

- Date: 2026-10-27; decided by: ours (plan 0007, step 5, tests)
- Status: Accepted 2026-10-27
- Decision: the exact smallest distance of a cut edge from the true contour is computed where it is exact in closed form: for a rounded rectangle (research 22 tests 1 to 3, and the property test's boxes) as the segment's distance from the inner rectangle less the corner radius; for a circle (test 5) from its centre; for polygons of lines (the property test's stars) as segment-to-segment distances. For the property test's stars of bulged rows (lines and arcs, not convex) the distance is taken at the edges' vertices and midpoints with offset2d's oracle, as offset2d's own band test does.
- Why: the part is convex in the first two cases, so its distance is the inner shape's less a radius; lines need no arc. An exact segment-to-arc distance for arbitrary arcs would be a new oracle of its own; offset2d's REQ-OFF-025 tests sample the same way.
- Rejected: dense sampling of every edge (not exact either, slower).
- Where: REQ-PRF-011; SPEC, Test plan.

## DEC-PRF-009: Reading REQ-PRF-012's source IDs and REQ-PRF-017's "d > 0"

- Date: 2026-10-27; decided by: ours (spec review of the implementation)
- Status: Accepted 2026-10-27; the SPEC's wording may follow at its next change
- Decision: REQ-PRF-012's "each edge keeping its source ID when the CCW loop is reversed" is met by choosing S from offset2d's IDs on the CCW loop, before the reversal; the record carries no IDs (cl, Later), so none are reversed. REQ-PRF-017's "WHERE d > 0" is read as "where P is not S" (DEC-PRF-007 (3)).
- Why: research 22, trap 2 guards against a start edge picked by a shifted ID, which the test of REQ-PRF-012 checks (S on a long side, then on to that side's CCW start). A d that rounds away gives P = S, and the moves of "d > 0" would then have no length.
- Where: REQ-PRF-012, 017.

## DEC-PRF-010: The smallest step-down and the largest air gap ratio

- Date: 2026-10-27; decided by: Peter (AQ-030 (a), AQ-031 (a)); the placement in the code ours
- Status: Accepted 2026-10-27
- Decision: `stepdown_mm` is declared [0.01, ∞) and `air_gap_ratio` (0, 2] (`MIN_STEPDOWN_MM`, `MAX_AIR_GAP_RATIO` in `_types.py`), so model's `check_job` refuses values outside them. The profile also refuses a step-down below 0.01 mm with `PROFILE_STEP_DOWN`, after the flute-length case, and in the same check a step-down whose pass count (z_top − z_bottom) / a_p,max is not finite. REQ-PRF-005 then has no levels and is skipped, as when REQ-PRF-004 fails. The air gap's upper end is the declaration's alone.
- Why: a step-down typed in µm builds days of passes; one whose quotient overflows crashed `math.ceil` inside REQ-PRF-005 (spec review). The profile's own step-down check stays a backstop for a caller without `check_job`, as the flute check is. A ratio above 2 puts P far beside the stock, where the approach at the plunge feed crosses whatever stands there (AQ-031).
- Rejected: a largest pass count (AQ-030 (b): a number without machining meaning); an upper air gap check in REQ-PRF-009 (AQ-031 (b): the declaration does it).
- Where: REQ-PRF-001, 005, 008, 020.

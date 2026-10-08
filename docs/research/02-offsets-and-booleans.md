---
topic: "02"
title: 2D offsets and Booleans
readiness: L4
release: "1"
reviewed: 2026-10-08
provenance: public
---

[Index](README.md) · [← 1. Foundations](01-foundations.md) · [3. Voronoi diagram and medial axis →](03-voronoi-medial-axis.md)

# 2. 2D offsets and Booleans

The offsets and Booleans of every 2.5D operation: the region a tool centre may use in a pocket or around a part, the path of a profile, keep-out zones, stock layers and the checks of links. Release 1 computes them with Clipper2 2.0.1 on an integer grid, through our own kernel (D-058, D-060, D-132); arcs come back by arc fitting (D-023). True-arc offsets come with the Voronoi diagram in release 2 ([03](03-voronoi-medial-axis.md)). The module is `offset2d`, which depends on `geometry2d` and uses its grid bridge, exact predicates and distance kernel (SplinterCAM DEC-G2D-038, DEC-G2D-040).

## Scope

- In: offsets of regions (pockets, outside profiles, keep-out zones); offsets of open chains (a profile on one side of a chain, a path grown on both sides for link checks); union, difference and intersection of regions; source IDs and fixed nodes through all of them; the tolerance band of every result.
- Out: building the region itself, the loop tree, flattening and the grid bridge ([01](01-foundations.md), `geometry2d`); the order of passes and links ([04](04-pocketing.md), [10](10-linking.md)); arc fitting and point reduction ([11](11-path-optimisation.md)); true-arc offsets and the medial axis ([03](03-voronoi-medial-axis.md), release 2); swept areas of non-circular tools (turning, [15](15-turning-roughing-finishing.md), release 2); where a profile starts and ends, leads and tabs ([10](10-linking.md), [22](22-2d-operations.md)).

## Inputs and outputs

- In: loops as curve rows with source IDs and a region kind, material or air (research 01, Kernel arrays); or one open chain; a clearance t ≥ 0 and a side, SHRINK or GROW; the `Context` with the tolerance set; for Booleans, two regions from earlier calls; the class of every source ID (material, cleared or air, D-059) as a plain array.
- Out: a polygon region (points, loop starts, one source ID and one fixed-node flag per vertex; research 01, Kernel arrays), outer loops counter-clockwise and holes clockwise, in a canonical order; or, for one side of a chain, an open path in the same arrays; and the typed diagnostics below.

## Method

### Definitions

The clearance form of Held (SRC-030, Def. 7.1; D-058). R is a region, B all of its loops at once, islands included, and d(p, B) the Euclidean distance.

- **SHRINK** by t: OA(t) = { p ∈ R : d(p, B) ≥ t }.
- **GROW** by t: { p : d(p, R) ≤ t }.
- t ≥ 0 and a side; there is no signed distance. The side follows from the operation: a pocket is a region of air shrunk by t, an outside profile is a region of material grown by t. Islands go into the same call, because B holds every loop.
- t = R + allowance, with R the tool radius and the side allowance of the operation: positive leaves material, negative cuts beyond the model, and it must stay above −R, so t > 0 for every tool path (D-150). t = 0 is legal and returns the region itself.
- One side allowance per operation in release 1 (D-150). Different allowances on the border and on islands (Held, p. 22) come later (ours).

### The kernel call

1. **Input.** The loops as geometry2d's loop tree normalised them and `flatten_loops` flattened them side-correct (research 01, Loop tree rules 1 to 6 and Flattening), not the rounded region of `build_region`. The kernel re-centres the input on its bounding box and rounds it to the grid u through geometry2d's grid bridge (`kernel/grid.hpp`; DEC-G2D-034, DEC-G2D-040). It refuses the call with `REGION_TOO_LARGE` before forming any integer when the span of the input plus 2·|δ| reaches 2^26 grid units in x or y, the guard of step 3 included: the union inside the call and the pinch tests after it run on the offset paths, which reach |δ| beyond the input, and they are exact only below that limit (research 01, resolution chain, stage 3).
2. **One call.** One `ClipperOffset` call with JoinType Round, EndType Polygon, ArcTolerance a and delta δ = t + a + 3u, negative for SHRINK (D-132). Clipper2 offsets every path and then unites the offset paths with the Positive fill rule inside the same call (SRC-122: `ClipperOffset::ExecuteInternal`). That union is research 01, rule 7's PolyTree, so an offset region is rounded once, and the bias of 3u pays for that one call (DEC-G2D-026, Peter 2026-10-07). Test 9 checks the result against the point-sampling oracle where flattened loops overlap.
3. **Clipper2's orientation guess.** `ClipperOffset` assumes that the path holding the extreme point of its input (largest y, then smallest x, in Clipper2's y-down convention; the first path on a tie) is an outer loop. If that path has a negative area, it treats the whole input as reversed: it negates δ and unites with the Negative fill rule instead (SRC-122: `GetLowestClosedPathInfo`, the `Group` constructor, `CheckReverseOrientation`). With our y-up loops that is the topmost, then leftmost point. Normalised loops pass outer loops first, so a hole touching its outer at that point loses the tie (ours). A hole whose side-correct flattening reaches up to t_flat past its outer's (research 01, rule 7) can still hold the extreme point, and the offset would come out inverted. The kernel therefore finds that path itself, with Clipper2's rule on the grid, before the call; when it is a hole, it adds a guard: a counter-clockwise triangle with a non-zero area and an inradius of at most |δ|/2, placed above the input, more than 2·|δ| + 6u away from it, which then holds the extreme point. Under SHRINK it vanishes; under both sides every result loop lying above the input's box grown by |δ| is removed, and the kernel asserts that at most one is (proposal, ours). Test 21.
4. **Clearance 0.** For |δ| below half a grid unit `ClipperOffset` copies its input and then unites it like any other result, Positive or, after a wrong orientation guess, Negative (SRC-122, `ExecuteInternal`). A clearance of 0 therefore takes its region from geometry2d's `build_region` instead, one Positive union on the same grid without the orientation guess, and gets no bias (D-132). Its boundary lies within 2.83u of the input (REQ-G2D-030), not in the band of step 6.
5. **Round joins.** Clipper2 places the vertices of a join on the circle of radius |δ| around the input vertex, with enough steps that no chord's sagitta exceeds a: steps per turn = min(π / acos(1 − a/|δ|), π·|δ|), in grid units (SRC-122, `DoRound`). The second term binds only when |δ|·acos(1 − a/|δ|) < 1; with |δ| ≥ a ≥ 2 grid units the product is at least a·π/2 ≥ π, so it never binds (ours). Every join chord therefore lies between |δ| − a and |δ| from its vertex, at least t + 3u, in air (Q-036 answer).
6. **The band.** Clipper2 moves points by up to 2.83 grid units (rounding of input and raw offset points, truncated crossings; SRC-118; research 01, resolution chain, stage 4). For t > 0, every boundary point of the result therefore lies between t and t + a + 6u from the input boundary (D-132). The lower bound protects the part; the upper bound is the offset's part of the geometry share of the budget (research 01, Tolerances).
7. **After the call.** Pinch points are split and fixed, source IDs assigned and the loops ordered (sections below). The topology comes from the integer result only; no float test re-decides it (research 01, resolution chain, stage 5).

### Open chains

- **Grown path** (both sides, for link checks): `ClipperOffset` with EndType Round and δ = t + a + 3u gives every point within t of the path, with round ends, which is the area a tool of radius t sweeps along it. D-062 grows a rapid path by R + 0.2·R this way.
- **One side of a chain** (a profile along an open chain, D-025; proposal, ours): the chain comes from geometry2d's `build_chain`, flattened with the tool's side as the air side of every arc (REQ-G2D-117). It is offset with EndType Butt and δ = t + a + 3u, which gives the closed area within t of the chain with flat ends. The tool-centre path is the part of that area's boundary on the tool side, decided per output edge from the input point nearest to its midpoint: inside a segment, by orient2d against that segment (exact on the grid); at an interior vertex V, from both segments of V, on the tool side when the edge lies on the tool side of either segment where V is convex toward the tool, and of both segments where V is concave. The caps are the output edges whose nearest input point is an end of the chain; they belong to neither side. The result is a set of pieces: one open piece from the cap at the chain's start to the cap at its end, and closed pieces where the tool side encloses an area narrower than the band (a C-shaped chain with the tool inside and an opening below 2t), which topic 22 machines as loops or reports. A closed chain is a loop and goes through the region path instead. Why not the raw offset of each segment with trimming: its self-intersections and the concentric case need the clean-up the union already does (Held, p. 15). Test 12.
- A chain the tool follows on its centre (trace and engraving lines, t = 0) needs no offset.

### Booleans

- Union, difference and intersection of regions, one `Clipper64` call on the same grid bridge, with the Positive fill rule for both operands (ours: the operands are normalised regions, where Positive equals NonZero, and Positive keeps the right side where flattened loops overlap; research 01, rule 7).
- Uses in release 1: stock layers minus the machined area (D-026, [08](08-stock-model.md)); keep-out zones as the union of fixture outlines grown by their clearance (D-078); air-cut detection, the machined area minus the stock; stock minus part.
- Every call moves points by up to 2.83u again, in no fixed direction. A wall at the finishing tolerance never comes from a chained result, and offsets are never chained: a region is offset from its source loops by the total distance (D-132). Stock layers are updated after every operation (D-026), and a chain of updates would let the error grow with each one. So a stock layer is never updated from the previous one (RR-001, ours):
  - The machined area of each operation, per layer, comes from its own tool-centre paths, flattened within t_flat, in one `ClipperOffset` call with EndType Round and δ = R − m, without the bias of D-132, and is kept with the operation. A flattened arc lies up to t_flat from the true arc on one side, so m pays for it.
  - The stock layer after operation k is the raw stock layer minus all machined areas 1 to k, in one `Clipper64` Difference call (the clip paths united by the Positive rule inside the same call). The raw stock layer is flattened toward more stock.
  - Two calls round on the way, each moving points by up to 2.83u in any direction, so m = t_flat + 6u. The machined area is then never larger than what the tool really swept, and the stock never smaller than what is really there. It is too large by at most m + 6u plus the flattening of the raw layer, below 2·t_flat + 0.0012 mm, which links and air-pass skipping can only treat more cautiously (D-062).
  - The cost is one difference over all earlier operations' areas per update instead of one area; 2.5D jobs have few operations per layer (ours).

### Source IDs

- Every output edge gets the source ID of the input edge nearest to its midpoint (Q-037 answer; SRC-004, SRC-030; D-059), found with geometry2d's distance kernel (`kernel/distance.hpp`, DEC-G2D-029, DEC-G2D-040). For an offset that distance lies in the band; test 10 checks it.
- Ties within eps_len, as on every round join, which is equally near the two edges at its vertex: material, then cleared, then air (D-059), then the lower source ID (ours).
- Booleans use the same rule over the edges of both operands; where a material edge and an air edge overlap, material wins (D-059).
- Clipper2's Z callback (`USINGZ`) is not used in release 1; it remains an optional speed-up (Q-037 answer).

### Pinch points and nesting

- As in geometry2d (`split_pinches`, DEC-G2D-036; D-084): every output path is split at every grid point it visits twice, by exact integer keys, the pieces in traversal order; and every vertex at a grid point that two or more output vertices share, in one path or in several, is a fixed node for the arc fit. Clipper2 2.0.1 returns the same touch as one pinched path or as two paths depending on the input order, and both must give the same result bit for bit.
- Nesting (ours, following DEC-G2D-036, which rejected re-nesting the split pieces): the output carries no parent field. A loop's role is its orientation, a counter-clockwise loop an outer boundary, a clockwise loop a hole, the sign of its area. A consumer that needs the tree (the pass order of topic 04) nests the loops itself by point in region of a probe of each loop: a vertex that is not a fixed node or, where every vertex is fixed, an edge midpoint, which lies off every other loop on the grid because loops meet only at fixed nodes. A piece of area 0 (a path that runs out and back) is dropped.
- Consumers (the pass order of topic 04, zigzag strips, the arc fit) accept fixed nodes and never merge across them.

### Order and determinism

- Loops leave in a canonical order that does not depend on Clipper2's path order, as `build_region` orders them: each loop starts at its smallest grid point, and the loops are sorted by that point and their signed area (DEC-G2D-036).
- Single-threaded and deterministic for identical input and settings (D-055; draft REQ-OFF-011).
- Translation: the input is re-centred on its bounding box before rounding, so the grid sees only coordinate differences. A part 10 000 mm from the origin is offset like the same part at the origin, with the same topology except near a critical distance and with vertices a few grid units apart at most, because a vertex can round to the other side of a half unit (DEC-G2D-034 measured this for the grid bridge; ours; answers the open question on draft REQ-OFF-010). Rotation and mirroring change the rounding in the same way.

### Critical distances and empty results

- Where t is close to the half-width of a strait, the region splits or stays whole depending on the grid (Held, Lemmas 7.5 and 7.7). Release 1 takes the integer result as it is, with no retry at a changed distance and no diagnostic (ours; replaces the retry of draft REQ-OFF-009). A retry would move walls by an amount no share of the budget pays for, and the integer result decides topology (research 01, stage 5). Topic 04 machines each component that results.
- A slot exactly 2t wide has an offset of area 0, which an area-based offset returns as nothing (Held, limit 4). The pocket then finds no region there; such a slot is machined by a profile on its centre line or a slot operation ([22](22-2d-operations.md)).
- A region that vanishes gives an empty region with `OFFSET_EMPTY` (info), not an error.

### Failure modes

| Situation | Result | Diagnostic |
| --- | --- | --- |
| The region vanishes | Empty region | `OFFSET_EMPTY` (info) |
| Loops cross, or other loop tree errors | No region | geometry2d's codes, such as `LOOPS_CROSS` (error) |
| Input plus 2·|δ| (and the guard) spans 2^26 grid units or more | No region | `REGION_TOO_LARGE` (error; geometry2d's grid bridge) |
| Clipper2 fails, the area is implausible for an offset by t, the coordinates leave the integer range, or a join would need more than 2^16 steps per turn | No region; input dumped for replay | `OFFSET_FAILED` (error; prototype REQ-OFF-014) |
| Arguments of the wrong shape, a clearance that is not finite or negative, a join tolerance below 2u | `ValueError` | (prototype REQ-OFF-013) |

Clean-up of the input is geometry2d's and reported there (`CLEANUP_SPIKE`, `LOOP_SLIT`); the offset reports nothing more for it (ours; replaces draft `OFFSET_INPUT_CLEANED`). Clipper2 cannot be interrupted inside a call: cancellation is checked before and after each kernel call (ours). Plan 0001 measured 35 ms outward and 71 ms inward for a dense star of 10⁴ segments on the reference machine (SRC-118, D-136); dense input is reduced within its tolerance before the offset, so the target below holds.

### Non-circular tools (release 2)

The area swept by a tool whose outline is not a circle (a turning or grooving insert, a holder in section) is the Minkowski sum of its outline with the path. For a convex outline along one straight segment it is the convex hull of the outline at both ends; for a path, the union of these pieces. A non-convex outline is split into convex pieces first. Clipper2 has `MinkowskiSum` for polygon paths. Turning uses it for the stock update and collision checks ([15](15-turning-roughing-finishing.md)); an offset is the special case of a circular tool.

### True arcs (release 2)

Release 1 offsets polylines and fits arcs afterwards (D-023, [11](11-path-optimisation.md)), with fixed nodes where the fit must not merge. Exact line and arc offsets without clean-up come from the Voronoi diagram ([03](03-voronoi-medial-axis.md), Held), or from cavalier_contours (Rust, MIT or Apache-2.0, with a C API; pre-1.0, its API changed in 0.8 and 0.9; A-003 unverified), which would need an ADR.

## Parameters

| Parameter | Value | Source |
| --- | --- | --- |
| Grid unit u | 0.0001 mm (10⁴ per mm) | D-058, D-132 |
| ArcTolerance a | max(0.05·tol, 2u) | D-058, D-132, D-146 |
| Bias | 3u, only for t > 0 | D-132 |
| Band of the result | [t, t + a + 6u] from the input boundary for t > 0; within 2.83u of it for t = 0 | D-132, REQ-G2D-030 |
| Span limit | 2^26 grid units, about 6711 mm, a declared foundation parameter | DEC-G2D-034, REQ-G2D-034 |
| Join type | Round | Q-036 answer |
| End types | Polygon for regions; Round for grown paths; Butt for one side of a chain | ours |
| Fill rule | Positive, for offsets (inside `ClipperOffset`) and Booleans | DEC-G2D-025; ours for Booleans |
| Join steps | at most 2^16 per turn | prototype REQ-OFF-014 |
| Clearance t | finite, t ≥ 0; t = R + allowance with allowance > −R | D-150 |
| Performance | 10⁴ segments in under 50 ms on the reference machine (a target; measured 35 ms outward, 71 ms inward on dense input) | SRC-118, D-136 |

## Traps

1. Mixed orientation inverts offsets: only normalised loops reach the kernel (research 01, loop tree rule 6), and `ClipperOffset` decides its own orientation from a shoelace area computed in double (SRC-122).
2. Two Clipper2 calls round twice: an offset region is built inside the offset call, and an offset is never offset again.
3. A clearance of 0 is not an offset: it goes through `build_region`, which avoids `ClipperOffset`'s orientation guess and its special case for |δ| < 0.5.
4. Join chords at δ = t would lie up to a inside the true offset, toward the part; the bias of a + 3u puts them in air.
5. Removing self-intersections alone keeps both circles of the concentric case (Held, p. 15); the winding union removes both.
6. Pinch points: split once here and marked fixed; consumers keep them.
7. Every round join is a tie for the nearest-edge rule; without the class rule a join on an air edge could carry an air tag next to material.
8. Vatti's paper has only the even-odd rule; the union that cleans offsets needs Clipper2's winding rules (Vatti note, limit 1).
9. Very short segments give wrong normals: geometry2d's cleanup merges points within eps_len before the offset.

## Tests

From the literature notes (Vatti tests 1 to 8, Held tests 1 to 5) and our own:

1. Booleans of squares A = [0, 10]², B = [5, 15]²: areas 25 (∩), 175 (∪), 75 (A − B).
2. Boolean oracle: 10⁴ random points not within the band of any edge; inside(result) = op(inside(A), inside(B)).
3. Bow-tie against [−1, 11]²: Positive keeps the counter-clockwise triangle only (area 25).
4. Union adjacency (Vatti limit 4): the notched square of area 89 with [1, 3] × [4, 7] inside gives one loop of area 89.
5. Difference hole (Vatti limit 5): [0, 20]² minus the diamond (10, 5), (15, 10), (10, 15), (5, 10) gives area 350 with one hole.
6. Annulus (Held test 1): border radius 20, island radius 10, same centre: SHRINK by 3 gives the ring 13 ≤ |p| ≤ 17; by 8, an empty region with `OFFSET_EMPTY`.
7. Rectangle [0, 100] × [0, 60] SHRINK by 10: [10, 90] × [10, 50] within the band; by 30, `OFFSET_EMPTY` (a region of area 0).
8. Strait (Held test 4): the notched rectangle with a strait of width 8 (Held's w, half the gap): SHRINK by 7.9 gives one loop, by 8.1 two.
9. Offset oracle with overlapping flattenings, at the tolerances of test 10: an island whose flattening overlaps the wall's (research 01, rule 7): 10⁴ random points outside the band satisfy p ∈ result ⇔ p ∈ R and d(p, B) ≥ t, with d computed exactly against the lines and arcs.
10. Band: for random regions with arcs and t from 0.1 to 50 mm, at tol 0.01 mm, at tol_min (0.0022858 mm, where a takes its floor of 2u) and at 0.05 mm (D-146), every output vertex and every edge midpoint lies between t and t + a + 6u from the input boundary, and every input point farther than t + a + 6u from the boundary lies in the result.
11. Clearance 0: the result equals `build_region`'s point set.
12. One side of a chain: a line, a counter-clockwise arc and a clockwise arc, the tool on the left and then on the right: the path lies between t and t + a + 6u from the chain, on the chosen side only, from cap to cap. A sharp V, (−10, 0) to (0, 0) to (−10, 1), tool on the outside: the path runs unbroken round the join. A C-shaped chain with the tool inside and an opening narrower than 2t: one open piece and one closed piece.
13. Grown path: a straight rapid from (0, 0) to (100, 0) grown by 6 is the stadium of area 1200 + 36π within the band.
14. Source IDs: a 60 × 40 rectangle of material with the top edge tagged air, grown by 5: the edge parallel to the top carries the top edge's ID, the round joins at the two top corners the side edges' (material) IDs, every other edge its own side's ID.
15. Pinch and touch: the union of [0, 10]² and [10, 20]² (touching at (10, 10)) gives two outer loops with the vertex at (10, 10) fixed in both; [0, 20]² minus the triangle (20, 10), (14, 7), (14, 13) gives one outer and one hole with (20, 10) fixed in both. Each case in both input orders gives the same arrays bit for bit.
16. Island touching the wall (golden `pocket-island-touching-wall`): SHRINK by 3 gives a region that never comes closer than 3 to either loop.
17. Translation: test 10's regions, without those near a critical distance, moved by (10 000, −10 000) mm give the same topology and vertices within 3u after moving back.
18. Span: a region spanning 6712 mm gives `REGION_TOO_LARGE` and no Clipper2 call; so does a region spanning 6700 mm grown by 10 mm.
19. Determinism: the same input twice gives bit-identical arrays; on the three platforms the same counts and geometry within 0.001 mm (D-055).
20. Differential: test 10's regions and tolerances against shapely/GEOS buffers with round joins, compared as point sets outside the band (D-060).
21. Orientation guess: a circular wall of radius 20 with a circular island of radius 5 tangent inside it at its top, both arcs flattened side-correct so that the island's flattening reaches above the wall's: SHRINK and GROW by 2 match the oracle of test 9, and the guard is gone from the result.
22. Stock update (RR-001): a 100 × 60 mm stock layer, then a pocket and a profile: the layer after both, computed from the raw layer and the two machined areas, contains every point the exact geometry leaves as stock, and no point farther than 2·t_flat + 0.0012 mm outside it; doing the same operations in the other order gives the same arrays.

## Libraries

- Clipper2 2.0.1 (Boost Software License 1.0, pinned by D-135) for offsets and Booleans, through our nanobind kernel; no external Python binding (D-060).
- shapely and GEOS: tests only, as an independent check (D-060).
- cavalier_contours: a candidate for true-arc offsets in release 2; an ADR first (A-003).

## Sources

Public literature (SRC-004 Vatti 1992; SRC-030 with the notes SRC-030b to SRC-030d, Held 1991; SRC-032 Shewchuk 1997), our own prototype's measurements (SRC-118), and Clipper2's source, read for its behaviour only (SRC-122). The rest is marked as ours or comes from decisions. No proprietary source was used (D-042).

## Literature notes

Distilled from the sources in our own words (D-044): each note carries what an implementer needs without the paper; the citation is there for checking. Where a note disagrees with the text above, the note has the evidence; the main text was brought in line with the notes and the decisions on 2026-10-08.

- Shewchuk 1997 (SRC-032), exact orientation and in-circle tests that offsets and Booleans rely on: see [topic 01](01-foundations.md#literature-notes).

### Vatti 1992: A generic solution to polygon clipping

**Source:** Bala R. Vatti, "A generic solution to polygon clipping", Communications of the ACM 35(7):56–63, July 1992, doi:10.1145/129902.129906. **Read:** pp. 56–63, the whole article (a scan; read from page images, not from the garbled text layer). **Class:** L (public literature).

**Problem.** Compute the intersection of a subject polygon set S and a clip polygon set C (the paper calls this "clipping"), and with changed rules also their union and the difference S − C (pp. 57, 61). Each set may hold several polygons; each polygon may be convex, concave or self-intersecting, and may have holes (p. 57). The output is a set of closed contours, or trapezoids for a scan-line filler. Assumptions: straight edges only, floating-point coordinates, and the even-odd rule for deciding what is inside a self-intersecting polygon (the left/right roles are assigned by parity, p. 58). The main text assumes intersection; union and difference only swap classification rules (p. 61).

**Method.**

Terms (pp. 57–59). The sweep runs from bottom to top (y up).

- *Bound*: a chain of polygon edges that is monotone in y. It starts at a local minimum and ends at a local maximum of its polygon. Every polygon splits into left bounds and right bounds. Left and right refer to the polygon's own interior: a left edge has the interior of its polygon on its right.
- *Local Minima Table (LMT)*: list sorted by ascending y; each node holds the pairs of bounds that start at that y (p. 59, Fig. 3 shows a polygon with two local minima, each starting one left and one right bound). It is built in one pass over both inputs (p. 57).
- *Scanbeam*: the horizontal strip between two successive event heights. Events are the y of local minima and the y of edge top ends. Edge crossings are not events; they are handled inside a beam.
- *Scanbeam Table (SBT)*: sorted list of pending event heights. The top of the current beam is the smaller of the lowest edge top in the AET and the next LMT height (p. 59).
- *Active Edge Table (AET)*: the edges that cross the current beam, sorted by x at the beam bottom.
- *Edge record* (p. 59): x_bot (x at the beam bottom), y_top, dx (change of x per unit increase of y), type (S or C), side (L or R), poly (output contour, or null), prev and next in the AET, succ (the next edge up the same bound).
- *Output contour*: a vertex list with a left end and a right end. A left edge adds vertices at the left end, a right edge at the right end (pp. 60–61, Figs. 4 to 6).
- An edge is *contributing* when poly is not null, that is when it currently forms part of the result boundary.

Edge classes combine side and type: LS, RS, LC, RC. Vertex classes: MN (local minimum), MX (local maximum), LI (left intermediate), RI (right intermediate). "E1 × E2" means that E1 lies left of E2 in the AET below the crossing and the two cross.

Crossing rules for **intersection** (p. 59):

| Crossing (either order) | Output vertex |
| --- | --- |
| LC × LS, LS × LC | LI |
| RC × RS, RS × RC | RI |
| LS × RC, LC × RS | MX |
| RS × LC, RC × LS | MN |
| LC × RC, RC × LC (like edges) | LI and RI |
| LS × RS, RS × LS (like edges) | LI and RI |

For **union**, the LI and RI rules stay, and the MX and MN results of the two unlike rows swap (p. 61). The like-edge rules are not restated for union or difference; we read them as unchanged. For **difference S − C**, a clip edge plays the opposite side: RC × LS and LS × RC give LI; RS × LC and LC × RS give RI; RS × RC and LC × LS give MN; RC × RS and LS × LC give MX (p. 61). We checked these by treating S − C as S ∩ (complement of C), where a right clip edge is a left edge of the complement: all four difference rules follow from the intersection rules.

An unlike crossing always produces an output vertex. A like crossing (two edges of the same set) produces one only when both edges contribute, and then one edge contributes exactly when the other does (p. 58).

Local minima (p. 58): when a bound pair becomes active, the first edge gets side L or R from the parity of the edges of the *same* type to its left in the AET. The minimum contributes depending on its position relative to the *other* type. For intersection this means: a minimum of S contributes when it lies inside C (odd number of C edges to its left), and a minimum of C contributes when it lies inside S. For union: minima of S outside C and minima of C outside S (p. 61). For difference the paper lists only minima of S outside C (p. 61).

Main loop, restated from the pseudocode on p. 60:

```
build LMT from S and C; AET = empty; SBT = heights of all local minima
for each scanbeam [yb, yt]:
    for each bound pair starting at yb:                      # AddEdges
        insert both edges into the AET in x order
        set sides by same-type parity
        if the minimum contributes: new contour, vertex = the minimum, poly of both edges = it
        mark y_top of both edges in the SBT
    build the intersection table IT for this beam (below)
    for each crossing (e1 left of e2 in the AET, point p) in ascending y:
        classify p by the rules
        LIKE:  if e1 contributes: add p at left end via e1, at right end via e2; swap sides of e1, e2
        MX:    AddLocalMax(e1, p)
        LI:    add p at the left end via e2
        RI:    add p at the right end via e1
        MN:    new contour starting at p for e1 and e2
        swap e1 and e2 in the AET; swap e1.poly and e2.poly
    for each AET edge e ending at yt (top vertex p):
        if e has no successor: AddLocalMax(e, p); delete e and e.next from the AET
        else: add p at e's side (if contributing); replace e by e.succ, keeping poly and side;
              mark e.succ.y_top in the SBT            # needed, but missing in the printed code
        update x_bot of every edge to its x at yt

AddLocalMax(e, p):
    add p at e's side of e.poly
    if e.poly == e.next.poly: the contour is closed; done
    else: append the vertex list of e.poly to the left or right end of e.next.poly
          (by the side of e), and point the other edge of e.poly at e.next.poly
```

Crossings inside one beam (p. 60): let Δy = yt − yb. Walk the AET from left to right and build a sorted edge list ST of the x at the beam top, x_top = x_bot + dx·Δy. For each new edge, start at the right end of ST and move left while the new edge's x_top is smaller than that ST entry's x_top; every step past an entry is one crossing, stored in IT with both edges. Then insert the new edge at the stop position. This is an insertion sort: the number of steps equals the number of crossings in the beam.

Trapezoid output (pp. 60–61): each contributing local minimum starts a trapezoid node that stores only a bottom y and the two bottom x. A minimum made of a left-then-right edge pair starts a new strip; a right-then-left pair splits an existing strip, so the split trapezoid is emitted and the edges' trapezoid pointers are reassigned. Every MX, LI or RI vertex emits a trapezoid (x_left, x_right, y_bot, dx_left, dx_right, y_top) and starts the next one.

Horizontal edges (p. 61): classify vertices as if the horizontal edge were absent, and treat the horizontal edge as a special case at the beam boundary. No further detail is given.

**Formulas.** All lengths in the input unit; angles do not occur.

- x at the beam top: x_top = x_bot + dx·Δy, with dx = (x_1 − x_0)/(y_1 − y_0) for an edge from (x_0, y_0) to (x_1, y_1), y_1 > y_0.
- Crossing of edges i and j inside a beam (our form of "compute the intersection"): y = yb + (x_bot,j − x_bot,i)/(dx_i − dx_j), x = x_bot,i + dx_i·(y − yb). It lies in the beam exactly when the x order at yb and yt differs.
- Scan conversion of a trapezoid: for y from y_bot to y_top draw x_left to x_right, then x_left += dx_left and x_right += dx_right per scan line (p. 61).
- Complexity claim: processing time "varies linearly with the total number of edges" (p. 58). This is empirical (see tests). Our own bound for the printed algorithm: sorting the minima costs O(m log m); each of the b beams walks the whole AET, and crossings cost O(k) in total, so the total is O(m log m + Σ|AET| + k), which is O(n² + k) in the worst case with k up to O(n²). For typical parts |AET| is the number of boundary crossings of one horizontal line, which is small, so the cost is near O(n·c) with c that crossing count.

**Parameters and values.** No tuning values. Test inputs were sized to fit a 1280 × 1024 raster (p. 61).

**Limits and failure cases.**

1. Only the even-odd rule. There is no non-zero or positive rule, so the union of raw offset pieces (research 02, "Cleaning self-intersections") cannot be done with the method as printed.
2. Horizontal edges are only sketched (p. 61).
3. Degenerate cases are not discussed: shared vertices, collinear overlapping edges, three or more edges through one point, a vertex lying on another edge. With floating point, processing IT strictly by y can pair edges that are no longer neighbours in the AET, and the swap then corrupts the AET order.
4. Printed pseudocode has gaps (p. 60): the ST cursor is not reset to the right end for each new AET edge; the terminating-edge LEFT_INT case names edge2 instead of the terminating edge; the successor's y_top is not marked in the SBT; after an MX at a crossing the two edges continue but are not set back to non-contributing; AppendPolygon moves only `edge1->prev` to the new contour. That last shortcut is safe for intersection (no edge can lie between two edges that bound one output region), but in a union a non-contributing edge of the other set can lie between them, and the other edge keeps a stale contour pointer. Implementations must search the AET for all edges that point to the absorbed contour.
5. The difference rule for contributing minima (p. 61) seems incomplete: a local minimum of C that lies inside S starts a hole in S − C and must contribute. Example: S a large square, C a small diamond inside it; with the printed rule the hole is lost.
6. Output contours may pass through the same point twice (pinch vertices). In the worked example the final contour Q holds i5 and i8 twice (p. 62). The result is weakly simple, not strictly simple.
7. No nesting information: contours come out as a flat list, and the paper does not state their orientation. A loop tree (research 01) must be built afterwards.
8. Straight edges only. Arcs must be flattened, or split at their y-extrema into monotone pieces with a quadratic crossing test.
9. The linear-time claim rests on inputs of at most 200 edges.

**How it was tested.** Implemented in C on a MIPS R2000 under Unix (p. 61). Method 1 was this algorithm with trapezoid output plus filling; Method 2 was reentrant (Sutherland–Hodgman) clipping plus a scan-line fill. Because Sutherland–Hodgman needs a convex clip polygon, only convex clip and concave subject polygons were used. Subject polygons had 4, 10, 20, 40, 100 and 200 edges against one clip polygon (Table 3, p. 62). Times are averages of measured machine cycles; the table gives no unit. Method 1 clip time grew from 1.20 (4 edges) to 45.77 (200 edges), close to linear. The speed-up of Method 1 over Method 2 was 1.62 to 2.44 for clipping, 5.62 to 12.40 for filling and 4.81 to 8.33 in total. A worked example (Fig. 8, Table 2, p. 62) clips a self-intersecting subject s1 to s8 against a concave clip polygon c1 to c9 with eight crossings i1 to i8. It lists each output event in scan order: a small contour P closes at i2 (vertices i2, s7, s1, i1), and a second contour Q starts at a rule-4 minimum i3, grows through rule 1 and 2 crossings, two like-edge crossings and intermediate vertices, and closes at the local maximum s4 with 13 vertices. No coordinates are given, so the example cannot be recomputed.

**Relation to Clipper.** Clipper and Clipper2 (Angus Johnson; Clipper2 under the Boost Software License 1.0) describe themselves as based on Vatti's algorithm. The LMT, the scanbeam queue, the active edge list and the output records with left and right ends are recognisable in them. According to Clipper's documentation (not re-checked for this note), it adds what the paper lacks: per-edge winding counts instead of the parity flag, so the fill rules EvenOdd, NonZero, Positive and Negative exist; XOR as a fourth operation; 64-bit integer coordinates for exact crossing tests; full horizontal-edge handling; reordering of crossings so that each processed pair is adjacent; open subject paths; PolyTree output with nesting; and a Z callback at crossings. As far as we know Clipper has no trapezoid output. Which Clipper2 version fixes each of items 3 to 7 above must be checked against the version we pin.

**What it means for us.**

- Research 02 says Vatti is "robust and fast". The paper supports "fast" for small inputs only; robustness (integers, horizontals, degeneracies) is Clipper's addition, not the paper's. The text should say so.
- The offset cleanup that research 02 describes ("Boolean union with the winding rule, which Clipper uses") needs the Positive or NonZero rule, which the original algorithm does not have. Any in-house Boolean (for example for true arcs) must add winding counts, not copy the paper's parity scheme.
- Edge tags (Q-037, partly). In a Vatti sweep every output edge is a piece of exactly one input edge, and every output vertex is either an input vertex or the crossing of exactly two input edges. So an own implementation can carry a tag (material, air, face ID) per active edge and write it to each output edge. The only ambiguous case is two collinear overlapping input edges, where a priority rule is needed (for example: material wins over air, so the safe side is kept). With Clipper2 only per-vertex Z values and the crossing callback exist. A library-independent route: after each Boolean, give every output edge the tag of the input edge that contains its midpoint within eps_len (found with a spatial index), and apply the same priority rule to overlaps.
- Output checks: consumers of Boolean results (loop tree, zigzag sweep in research 04) must accept pinch vertices (item 6) or split them first.
- The trapezoid output is a decomposition into y-monotone strips, the same structure the zigzag mesh of Held 1991 (research 04) uses. One sweep could return both the region and its strips; with Clipper2 the strips must be computed separately.
- Test oracle (Missing before a spec, last item, partly): the rules define inside(result) = op(inside(S), inside(C)) under a fill rule. A point-sampling property test built on that definition is independent of Clipper2 and also detects a dropped loop (A-053).

**Test ideas.**

1. Squares A = [0, 10]², B = [5, 15]² (mm): area(A ∩ B) = 25, area(A ∪ B) = 175, area(A − B) = 75, area(A xor B) = 150.
2. Point-sampling oracle: for 10⁴ random points not within eps_len of any edge, inside(result) must equal op(inside(A), inside(B)) under the chosen fill rule.
3. Bowtie (0,0), (10,10), (10,0), (0,10) intersected with [−1, 11]²: EvenOdd and NonZero keep both triangles (total area 50); Positive keeps only the counter-clockwise triangle (area 25). The result may contain the pinch point (5, 5) once or twice; the test must accept both forms or require a split.
4. Union adjacency trap (item 4): S = (0,0), (4,1), (5,6), (6,1), (10,0), (10,10), (0,10), area 89 mm², with C = [1, 3] × [4, 7] inside S. S ∪ C must equal S (area 89, one contour, no hole). At the notch apex (5, 6) a non-contributing C edge lies between the two edges of the left output region.
5. Difference hole (item 5): S = [0, 20]², C = diamond (10, 5), (15, 10), (10, 15), (5, 10); S − C has area 400 − 50 = 350 with one hole.
6. Horizontal edges: [0, 10] × [0, 5] ∪ [0, 10] × [5, 10] gives one contour of area 100 with no zero-width seam.
7. Tags: an air edge collinear with and overlapping a material edge must come out tagged material (priority rule).
8. Timing: clip a polygon of 10⁵ vertices (a finely flattened contour) against a rectangle; record time against vertex count to confirm near-linear behaviour on realistic CAM input.

### Held 1991, chapters 1–2 and 7–8: offsets defined by clearance and computed on the Voronoi diagram

**Source:** Martin Held, *On the Computational Geometry of Pocket Machining*, Lecture Notes in Computer Science 500, Springer, Berlin Heidelberg, 1991, ISBN 3-540-54103-9, doi:10.1007/3-540-54103-9. **Read:** for this note pp. 13–15, 19–22, 57, 104–108, 116–118 and 122–124. Chapters 1–8 and 10 and Appendix A were read completely for the SRC-030 notes; chapter 9 is the SRC-005 note. Our copy is a scan; formulas were read from page images; page numbers are the printed ones. **Class:** L (public literature).

**Problem.** Compute inward offsets of a pocket boundary made of line segments and circular arcs, for many offset distances, for pockets with islands, exactly (lines stay lines, arcs stay arcs) and without a self-intersection clean-up. Assumptions (p. 19; Definition 5.3, p. 68): one border contour C₀ and islands C₁ … C_m; all closed, oriented, pairwise disjoint Jordan curves without coinciding edges; border counter-clockwise, islands clockwise, so the pocket lies on the left of every contour. Only lines and arcs: other curves are not closed under offsetting (the offset of a cubic spline is not a cubic spline), and machines interpolate only lines and arcs anyway (p. 19). There is no limit on the number or shape of islands (p. 19).

**Method.**

*Definitions.* Our notation: B is the set of all contours, d(p, Q) = inf{|p − q| : q ∈ Q} is the Euclidean distance (Held calls d(p, B) the offset or clearance of p, p. 57), D(c, ρ) is the open disk of radius ρ around c.

1. Offset area: OA(t) = { p ∈ P : d(p, B) ≥ t }, t ≥ 0 (Def. 7.1, p. 104). It is a closed set. Held notes that practice uses several different definitions (p. 104).
2. Offset curve: OC(t) = { p ∈ closure(P) : d(p, B) = t } (Def. 8.1, p. 116).
3. Offset object: OO(t, o) = OC(t) ∩ VA(o), the part of the offset curve inside the Voronoi area of boundary object o (Def. 8.2, p. 116). OC(t) is the union of its offset objects.
4. Area swept by a cutter of radius ρ along a curve C: TS(C, ρ) = ∪_{p ∈ C} D(p, ρ) (Def. 8.3, p. 116).

The offset distance is always a clearance t ≥ 0, measured into the pocket from all contours at once. There is no signed offset. A direction appears only per object, as a sliding direction k = ±1 in the bisector formulas (p. 92; see the SRC-030b note).

*Conventional offsetting and why it fails* (pp. 14–15, 19–20). The three-step method of Harenbrock and Bruckner: (1) offset every contour element on its own; (2) close the gaps at non-tangent joints with arcs; (3) remove self-intersections and every piece closer to the contour than t. Held's objections: step 3 intersects every pair of offset elements, so it is at least quadratic in the number of elements; loop removal needs a start point known to lie on the final curve, then deletes the excess between consecutive intersection points. With islands it "may fail totally": take a border circle of radius ρ₂ and an island circle of radius ρ₁ < ρ₂ with the same centre, d = ρ₂ − ρ₁, and offset by t = 2d. Steps 1 and 2 give two concentric circles that do not intersect, so nothing is removed, although both must go (p. 15).

*Offsetting by the Voronoi diagram* (Persson 1978, pp. 20–21). The end point shared by two consecutive offset elements is equally far from two contour elements and farther from all others; as the contour shrinks, these points trace the Voronoi diagram (the fronts of a fire lit on all contour elements at once meet there, p. 20). With the diagram known, an offset at t is built in reverse: for each boundary object o take its offset at t (a parallel line, a concentric arc of radius r ∓ t, or an arc of radius t around a reflex vertex) and clip it to the Voronoi area of o. The end points are the points of clearance t on the bounding bisectors; with bisectors stored as functions of the clearance (SRC-030b note) they are formula evaluations, not intersections (p. 21). The walk, restated from Offset_Object and Cutter_Pass (Tables 8.4, 8.5, pp. 123–124):

```
# Voronoi edges carry a clearance range [t_low, t_high], are oriented by
# increasing clearance, and know their left and right sites.
offset_curve(t, start_edge):              # start_edge has t in its range
    C = []
    e = start_edge
    repeat
        o  = right_site(e)                # follow the Voronoi polygon of o
        e2 = next edge of that polygon, CCW, whose range contains t
        append the offset of o at distance t, from point(e, t) to point(e2, t)
        e = e2
    until e == start_edge  or  e is a marked special edge
    return C
```

Offset_Object finds e2 by turning CCW around the head while the upper clearance bound grows, then stepping back over tails while the lower bound exceeds t (Table 8.5). Each offset is linear in the edges it crosses, and the diagram is reused for every offset (pp. 21, 36).

*How offsets split* (pp. 104–108). A strait (Def. 7.3, SRC-030c note) is a pair of contour points p₁, p₂ with midpoint q and width w = ½·|p₁ − p₂| where d(q, B) = w and the offset area just above w lies on both sides of the segment p₁p₂. For a simply connected pocket: if OA(t) falls into two parts, a strait with w < t exists (Lemma 7.7); every strait of width w splits OA(w + ε) for some ε > 0 (Lemma 7.5); OA(t) is connected for every t exactly when the pocket has no strait (Cor. 7.3). Our phrasing: offset regions split only at straits, and a split between levels t_k < t_{k+1} means a strait with t_k ≤ w < t_{k+1}.

*Different allowances per contour* (p. 22). One allowance for all contours only shifts the first pass. Different allowances on border and islands are applied by offsetting each contour on its own first, with the same technique.

**Formulas.** Lengths in mm.

- Offset of a line a·x + b·y + c = 0 with a² + b² = 1 and (a, b) the inward normal: a·x + b·y + c + k·t = 0. Offset of a circle: (x − x_c)² + (y − y_c)² = (r + k·t)². k = ±1 is the sliding direction (p. 92).
- Lemma 7.4 (p. 106): for a monotonous area A whose widest bounding strait has width w, OA(t) ∩ closure(A) ⊆ A iff t > w. Above the widest strait, the offsets of each area can be computed on their own.

**Parameters and values.** None; t is exact.

**Limits and failure cases.**

1. Lines and arcs only.
2. The walk needs a correct diagram. Bisectors of parallel lines and of concentric arcs have constant clearance; an offset at exactly that clearance is a whole edge, not a point (pp. 94, 113).
3. The strait lemmas are proved for simply connected pockets. Held first joins islands to the border with bridges (SRC-030d note).
4. OA is closed (d ≥ t): a slot of width exactly 2t has a degenerate offset along its centre line. Held's method returns it as the constant-clearance bisector; an area-based library such as Clipper2 returns nothing (our remark; topic 04 Missing item "a region the tool fits exactly").
5. Held gives no numerical tolerances for any of this.

**How it was tested.** No separate offset test. The zigzag program computed its outermost offset curve this way: 0.36–4.72 s for 41–160 boundary elements on a DEC VAX 8350 (Table A.2, p. 159).

**What it means for us.**

- Sign convention (topic 02 Missing item 1, A-054): adopt Held's clearance form for every region offset: t ≥ 0, measured into the region from all its loops at once, islands included. Offsetting a correctly oriented region (outer CCW, holes CW) by −t with Clipper2 gives OA(t) up to the chord error. Keep signed distances only for single curves (profiles, open paths).
- Independent oracle (topic 02 Missing item 5, A-053): the definitions are the oracle. For sample points p with |d(p, B) − t| > tol, p lies in the Clipper2 result iff p ∈ P and d(p, B) ≥ t, with d computed exactly against the lines and arcs. This does not use Clipper2, detects dropped and spurious loops, and complements the Boolean oracle of the SRC-004 note.
- The concentric-circle case confirms that the clean-up in topic 02 needs its distance check; removal by intersections alone keeps both circles. Clipper2's winding approach removes both.
- Tags (Q-037, partly): each offset piece lies in the Voronoi area of exactly one boundary object, so the tag of an offset point is the tag of the boundary object nearest to it. For Clipper2 output: give each output edge the tag of the boundary object nearest to its midpoint, and check that this distance is t ± tol. This makes the SRC-004 midpoint rule exact for offsets. Corner points of an inward offset lie on Voronoi edges and are equidistant from two objects; there the rule "material wins" decides.
- Splits (topic 04): a change in the number of components between two offset levels marks a strait whose width lies between the levels; the component tree of the SRC-030d note rests on this.
- Release 2: a Voronoi diagram gives exact line and arc offsets with no clean-up and no arc fitting (D-023 fits arcs after Clipper2 in release 1), and many offsets are cheap once the diagram exists.

**Test ideas.**

1. Annulus: border circle radius 20, island circle radius 10, same centre. OA(t) is the ring 10 + t ≤ |p| ≤ 20 − t for t < 5, the circle |p| = 15 at t = 5, and empty above. At t = 8 the raw offsets are circles of radius 18 and 12 that do not cross; the result must be empty (checked with exact Booleans, as was test 4).
2. Rectangle [0, 100] × [0, 60]: OA(t) = [t, 100 − t] × [t, 60 − t] for t < 30; at t = 30 it is the segment from (30, 30) to (70, 30); empty above.
3. Oracle: 10⁴ random points per case against d(p, B) ≥ t; no mismatch outside the tol band, for pockets with islands and arcs.
4. Split: rectangle [0, 100] × [0, 40] with two triangular notches, apex (50, 12) on base 44–56 at y = 0 and apex (50, 28) on base 44–56 at y = 40. The strait has width 8 and midpoint (50, 20). OA(7.9) has one component, OA(8.1) two.
5. Tags: 60 × 40 rectangle with the top edge tagged air; every inward offset edge parallel to the top edge carries air, all others material, and corner points carry material.

## Open items

Readiness **L2**, needed for release **1**. Audit of 2026-09-27: [details](../reviews/2026-09-27-readiness-audit.md#02-2d-offsets-and-booleans). Levels are defined in [AGENTS.md](../AGENTS.md#readiness-levels).

### Registered questions and assumptions

<!-- open-items:begin -->
_Generated by `tools/spike.py status` from QUESTIONS.md and ASSUMPTIONS.md. Do not edit by hand._

- [A-001](../ASSUMPTIONS.md#a-001-eps_len--1e-6-mm-is-consistent-with-the-clipper-integer-scale) (wrong) eps_len = 1e-6 mm is consistent with the Clipper integer scale
- [A-002](../ASSUMPTIONS.md#a-002-pyclipper-behaves-like-clipper2) (wrong) pyclipper behaves like Clipper2
- [A-003](../ASSUMPTIONS.md#a-003-cavalier_contours-can-be-built-into-the-kernel-extension-through-its-c-api) (unverified) cavalier_contours can be built into the kernel extension through its C API
- [A-054](../ASSUMPTIONS.md#a-054-research-02-and-24-use-the-same-offset-sign-convention) (wrong) Research 02 and 24 use the same offset sign convention
- [A-053](../ASSUMPTIONS.md#a-053-checking-that-every-offset-point-lies-at-distance-d--tol-is-enough) (wrong) Checking that every offset point lies at distance |d| ± tol is enough
<!-- open-items:end -->

### Missing before a spec

- [x] One offset sign convention used by 01, 02 and 24 (A-054). Done 2026-10-08: clearance t ≥ 0 and a side (D-058, section Definitions).
- [x] The mapping from tol to Clipper2 settings and the side of the round-join chords (Q-036). Done 2026-10-08: D-058, D-132, section The kernel call.
- [x] Per-edge tags through offsets and Booleans (Q-037). Done 2026-10-08: D-059, section Source IDs.
- [x] Offsets of open paths. Done 2026-10-08: section Open chains (one side of a chain: proposal, ours).
- [x] An independent test oracle (A-053). Done 2026-10-08: tests 2, 9 and 20 (point sampling against the definitions, shapely/GEOS; D-060).
- [x] How pinch splits are re-nested (research 01, Missing). Done 2026-10-08: they are not; a loop's role is its orientation and consumers nest by point in region (section Pinch points and nesting, following DEC-G2D-036).

Later, not blocking release 1: allowances per loop; cancellation inside a Clipper2 call; whether a vertex of one loop lying on another loop's edge is a fixed node (with the arc fit, topic 11); true-arc offsets (topic 03).

---

[Index](README.md) · [← 1. Foundations](01-foundations.md) · [3. Voronoi diagram and medial axis →](03-voronoi-medial-axis.md)

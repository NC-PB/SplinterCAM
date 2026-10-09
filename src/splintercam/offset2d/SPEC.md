# SPEC: offset2d

<!-- The offsets and Booleans of every 2.5D operation. Drafted on 2026-10-08 from research 02 with /research-to-spec (plan 0005). Requirement IDs: REQ-OFF-010, 011, 013, 014 and 018 keep the numbers research 02 cites from the prototype's draft, with the same meaning; the new ones start at 020. REQ-OFF-009 (a retry at a changed distance) is not taken over (research 02, Critical distances). -->

| | |
| --- | --- |
| Status | Reviewed (2026-10-08, Peter: the four open questions answered, the deviations accepted; DEC-OFF-001 to 006). Implemented: `offset_region` (plan 0005, step 4); the rest follows in steps 5 to 9. REQ-OFF-032 and 044, the stock update, released on 2026-10-09 from research 02's answer to RR-001 (pull request 47, DEC-OFF-006). Choices marked "(ours)" stand as the contract (DEC-OFF-005) |
| Layer | 1 (see architecture/modules.yaml) |
| Depends on | foundation, geometry2d (Python API, and the kernel headers `kernel/exact.hpp`, `kernel/distance.hpp`, `kernel/grid.hpp`; DEC-G2D-040) |
| Research | [02][r02]: the main text is normative, the literature notes are evidence. This SPEC links to it instead of restating it |
| Decisions | D-023 (arcs back by arc fitting), D-025 (open chains for profiles), D-026 (stock layers), D-055 (determinism), D-058 and D-132 (clearance and side, grid, ArcTolerance, bias, band), D-059 (source IDs and their tie), D-060 (Clipper2 through our kernel; shapely tests only), D-062 (rapid paths grown by R + 0.2·R), D-078 (keep-out zones), D-084 (pinch points, fixed nodes), D-135 (Clipper2 2.0.1), D-146 (budget at small tolerances), D-150 (allowance, t > 0 for tool paths); DEC-G2D-025, 026, 034, 036, 038, 040; text in [docs/spike/decisions-snapshot.md](../../../docs/spike/decisions-snapshot.md) |
| Owner | Peter Burgener |

## Purpose

Offsets a machining region by a clearance t ≥ 0 on a side, SHRINK or GROW, and joins, subtracts and intersects regions, on Clipper2's integer grid through our own kernel (D-058, D-132). Every result carries source IDs and fixed nodes, so the arc fit of topic 11 can turn it back into lines and arcs (D-023, D-084). Its users are the 2.5D strategies (pocket regions, outside profiles, profiles along open chains), stock layers and keep-out zones, and the link checks.

## Scope

- In: [research 02][r02], sections Definitions, The kernel call, Open chains, Booleans, Source IDs, Pinch points and nesting, Order and determinism, Critical distances and empty results, Failure modes, Parameters.
- Out, handled elsewhere: the loop tree, flattening, `build_region` and the grid bridge itself (geometry2d, research 01); the order of passes and links (topics 04, 10); arc fitting and point reduction (topic 11); where a profile starts and ends, leads and tabs (topics 10, 22); stock layers as such (topic 08).
- Later parts: a tool outside a drawn boundary (topic 25), its own function when that operation is planned (Peter, DEC-OFF-004); allowances per loop (Held, p. 22); cancellation inside a Clipper2 call; whether a vertex of one loop lying on another loop's edge is a fixed node (with the arc fit); swept areas of non-circular tools (`MinkowskiSum`, release 2); true-arc offsets (topic 03, release 2); ellipse and spline edges, whose extra clearance from geometry2d (`FlatRegion.extra_clearance_mm`, 0 for lines and arcs) the offset will then add to t.
- Duties of the callers (cnc review, 2026-10-09): `OFFSET_EMPTY` reports only a region that vanishes as a whole; where one branch of a pocket is too narrow for the tool and vanishes while the rest survives, offset2d reports nothing, so the strategies report the material left (rest-material, topic 04). A clearance of 0 gives `build_region`'s region, up to 2.83u on either side of the drawn loops: never a tool-centre region, since every tool path has t > 0 (D-150).
- Non-goals: signed offset distances; an offset of an offset result; a retry at a changed distance near a critical distance; Clipper2's Z callback (`USINGZ`, Q-037 answer); an external Python binding of Clipper2 (D-060).

## Public interface

Lengths in mm, float64 (D-028). Every function takes `ctx: Context` and returns a `Result`. All names are proposals (ours); research 02 names none. "kernel:" names the C++ file that runs the loops (docs/dev/03, split rule).

```python
from collections.abc import Sequence
from numpy.typing import NDArray
from splintercam.foundation import Context, Result
from splintercam.geometry2d import AirSide, CurveRows, PolygonRegion, RegionKind

class EdgeClass(IntEnum): MATERIAL = 0; CLEARED = 1; AIR = 2   # D-059, in tie order
class BooleanOp(Enum): UNION; DIFFERENCE; INTERSECTION

@dataclass(frozen=True, slots=True)
class SourceClasses:                                    # the class of every source ID (research 02, Inputs)
    ids: NDArray[np.int64]                              # (m,), strictly ascending
    classes: NDArray[np.int8]                           # (m,), EdgeClass

@dataclass(frozen=True, slots=True)
class OpenPaths:                                        # one side of an open chain (REQ-OFF-028), modelled on FlatChain
    points: NDArray[np.float64]                         # (n, 2), the pieces one after another
    starts: NDArray[np.int64]                           # (k,), first vertex of each piece
    closed: NDArray[np.bool_]                           # (k,), a closed piece's closing edge is implied
    source_ids: NDArray[np.int64]                       # one per edge: (n − open pieces,)
    fixed: NDArray[np.uint8]                            # (n,), per vertex

def offset_region(loops: CurveRows, kind: RegionKind, clearance_mm: float,
                  classes: SourceClasses, ctx: Context) -> Result[PolygonRegion]: ...   # AIR shrinks, MATERIAL grows
def grow_chain(rows: NDArray[np.float64], ids: NDArray[np.int64], clearance_mm: float, classes: SourceClasses, ctx: Context) -> Result[PolygonRegion]: ...
def offset_chain_side(rows: NDArray[np.float64], ids: NDArray[np.int64], tool_side: AirSide, clearance_mm: float, classes: SourceClasses,
                      ctx: Context) -> Result[OpenPaths]: ...
def boolean(a: PolygonRegion, b: PolygonRegion, op: BooleanOp, classes: SourceClasses,
            ctx: Context) -> Result[PolygonRegion]: ...
def machined_area(paths: Sequence[tuple[NDArray[np.float64], NDArray[np.int64]]], tool_radius_mm: float,
                  classes: SourceClasses, ctx: Context) -> Result[PolygonRegion]: ...   # REQ-OFF-032; rows and ids per centre path
def stock_layer(raw: CurveRows, machined: Sequence[PolygonRegion], classes: SourceClasses,
                ctx: Context) -> Result[PolygonRegion]: ...           # REQ-OFF-044
# kernel: offset.cpp (ClipperOffset, guard, band), boolean.cpp (Clipper64), chain_side.cpp, ids.cpp;
# geometry2d's grid.hpp for re-centring, rounding, pinch splits and the canonical order
```

- Offsets take loops as `CurveRows`, never a `PolygonRegion`: a region is offset from its source loops by the total distance, never from an earlier result (REQ-OFF-033). `offset_region` runs geometry2d's `loop_tree` and `flatten_loops` itself (REQ-OFF-021).
- The side follows from the region's kind (research 02, Definitions: "the side follows from the operation"): a region of air (a pocket) shrinks, a region of material (a part, a fixture outline) grows. These are the two combinations in which the side-correct flattening lies on the safe side; the other two would put it up to t_flat on the part's side, a gouge. So `offset_region` takes no side argument (ours; Open questions, 4).
- An open piece of `OpenPaths` runs in the chain's direction, from the cap at its start to the cap at its end; a closed piece keeps the traversal of the offset boundary; pieces come in the canonical order of REQ-OFF-038 by their first vertex (ours).
- Chains come as the rows and IDs of one open chain, as for geometry2d's `build_chain`, which flattens them; `tool_side` is the side the tool works on, so it is the air side of every arc (REQ-G2D-117).
- The output is a `PolygonRegion` as geometry2d defines it: outer loops CCW, holes CW, no nesting stored, one source ID and one fixed flag per vertex (research 01, Kernel arrays). The source ID of a vertex is that of the output edge starting there (as in REQ-G2D-180).
- Every source ID in the input must appear in `classes`; a missing one is a programming error (ours).

## Requirements

"test N" is research 02's list of [tests][tests]. The tolerances in "Verified by" are those of test 10 unless named: tol 0.01 mm, tol_min (0.0022858 mm, where a takes its floor of 2u) and 0.05 mm (D-146). a = max(0.05·tol, 2u). "The band" is [t, t + a + 6u] from the flattened input boundary, the polylines Clipper2 receives (research 02, The kernel call, steps 1 and 6), for t > 0. Measured against the true lines and arcs it is [t, t + a + 6u + t_flat]: the side-correct flattening lies up to t_flat inside the true boundary, on the air side (research 01, Flattening). Oracles that compute d against the true curves exclude points within the wider band (ours).

### Region offsets (research 02, Definitions and The kernel call)

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-OFF-020 | WHEN `offset_region` is called on a region of air, THE offset2d module SHALL return OA(t) = { p ∈ R : d(p, B) ≥ t } (SHRINK), and on a region of material { p : d(p, R) ≤ t } (GROW), with B all loops of the region at once, islands included (Held, Def. 7.1; D-058; the side from the kind, research 02, Definitions), up to the band of REQ-OFF-025. | tests 6, 7 and 16 (air); test 9 (the oracle at 10⁴ random points outside the band measured against the true curves, d computed exactly against the lines and arcs); test 14 (material) | Reviewed |
| REQ-OFF-021 | THE `offset_region` function SHALL hand the kernel the loops as geometry2d's loop tree normalised them and `flatten_loops` flattened them side-correct for the region's kind, not the rounded region of `build_region` (traps 1 and 2). | review; test 21's loops given with every loop reversed give the same arrays bit for bit | Reviewed |
| REQ-OFF-043 | THE `offset_region` function SHALL run geometry2d's `cleanup` on each side-correct flattened loop before the kernel call, so no segment shorter than eps_len reaches `ClipperOffset`, and carry the source IDs of the kept vertices (trap 9; geometry2d cleans only the topology flattening, its SPEC, Public interface). | unit: a loop with two vertices 0.5·eps_len apart gives the same region as without the second | Reviewed |
| REQ-OFF-022 | WHEN t > 0, THE offset2d kernel SHALL make one `ClipperOffset` call with JoinType Round, EndType Polygon, ArcTolerance a and δ = t + a + 3u, negative for SHRINK, and take the region from the union inside that call, with no further Clipper2 call on it (D-132, DEC-G2D-026; trap 2, trap 4). | review; test 9 where flattened loops overlap | Reviewed |
| REQ-OFF-023 | WHEN the path that holds the extreme point of the input on the grid (largest y, then smallest x, in Clipper2's y-down frame; the first path on a tie) is a hole, THE offset2d kernel SHALL add a CCW guard triangle with a non-zero area and an inradius of at most \|δ\|/2 above the input, more than 2·\|δ\| + 6u from it, and remove from the result every loop lying above the input's box grown by \|δ\|, and return `OFFSET_FAILED` (REQ-OFF-014) when more than one does (research 02, The kernel call, step 3; SRC-122; ours). | test 21: SHRINK and GROW by 2 match test 9's oracle and the guard is gone from the result | Reviewed |
| REQ-OFF-024 | WHEN t = 0, THE `offset_region` function SHALL return the region of geometry2d's `build_region` for the same loops and kind, with its source IDs (REQ-G2D-180) and its diagnostics, `REGION_EMPTY` (warning) included, and with no bias and no `ClipperOffset` call (D-132; trap 3; the diagnostics ours). | test 11: the same arrays and diagnostics as `build_region` | Reviewed |
| REQ-OFF-025 | WHEN t > 0, THE offset2d module SHALL return a region whose every boundary point lies between t and t + a + 6u from the flattened input boundary (D-132; research 02, The kernel call, steps 5 and 6). | test 10: every output vertex and edge midpoint in the band, and every input point farther than t + a + 6u from the flattened boundary in the result, for random regions with arcs and t from 0.1 to 50 mm | Reviewed |
| REQ-OFF-018 | IF the span of the input plus 2·\|δ\|, the guard of REQ-OFF-023 included, reaches the declared span limit (2^26 grid units) in x or y, THEN THE offset2d kernel SHALL refuse the call with `REGION_TOO_LARGE` (error) before forming any integer and without calling Clipper2 (research 01, resolution chain, stage 3; REQ-G2D-034). | test 18: a region spanning 6712 mm, and one spanning 6700 mm grown by 10 mm | Reviewed |
| REQ-OFF-026 | THE offset2d module SHALL take the region's topology from the integer result only: no float test re-decides it, and near a critical distance it takes the result as it is, with no retry at a changed distance and no diagnostic (research 01, stage 5; research 02, Critical distances; ours). | review; test 8: SHRINK by 7.9 gives one loop, by 8.1 two | Reviewed |

### Open chains (research 02, Open chains)

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-OFF-027 | WHEN `grow_chain` is called, THE offset2d kernel SHALL offset the chain with EndType Round and δ = t + t_flat + a + 3u, giving every point within t of the true chain, with round ends (D-062). The flattening of `build_chain` lies up to t_flat inside each arc on one side, so δ adds t_flat to cover both sides (ours; research 02 gives δ = t + a + 3u, written for a chain of lines). Its result therefore lies in the band [t, t + t_flat + a + 6u] from the flattened chain, t_flat wider than research 02's (ours). | test 13: the rapid from (0, 0) to (100, 0) grown by 6 is the stadium of area 1200 + 36π within [t, t + t_flat + a + 6u]; an arc chain: every point within t of the true arc lies in the result | Reviewed |
| REQ-OFF-028 | WHEN `offset_chain_side` is called, THE offset2d kernel SHALL offset the chain from `build_chain` with EndType Butt and δ = t + a + 3u, and return the boundary edges of that area on the tool side, decided per output edge from the input point nearest to its midpoint (orient2d on the grid inside a segment; at an interior vertex by both segments, either where the vertex is convex toward the tool and both where it is concave), without the caps, as `OpenPaths`: one open piece from start cap to end cap plus closed pieces where the tool side encloses an area narrower than the band (D-025; research 02, Open chains; ours). | test 12: a line, a CCW arc and a CW arc, tool left and right, in the band on the chosen side only, cap to cap; the sharp V unbroken round the join; the C-shaped chain with an opening below 2t gives one open and one closed piece | Reviewed |
| REQ-OFF-029 | IF the chain given to `grow_chain` or `offset_chain_side` closes (its last point equals its first), THEN THE offset2d module SHALL return no result with `CHAIN_CLOSED` (error; the code ours), since a closed chain is a loop and goes through `offset_region` (research 02, Open chains; Open questions, 4). | unit: a closed square as a chain | Reviewed |

### Booleans (research 02, Booleans)

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-OFF-030 | WHEN `boolean` is called, THE offset2d kernel SHALL compute the union, difference a − b or intersection in one `Clipper64` call on geometry2d's grid bridge, with the Positive fill rule for both operands (ours; research 01, rule 7). | tests 1, 3, 4 and 5; test 2: at 10⁴ random points farther than 3u from every edge of either operand (research 02's "band" read as the 2.83 grid units of REQ-G2D-030; ours), inside(result) = op(inside(a), inside(b)) | Reviewed |
| REQ-OFF-031 | IF the operands of `boolean` or `stock_layer` together, or the paths of `machined_area` plus 2·δ, span the declared span limit or more in x or y, THEN THE offset2d kernel SHALL refuse the call with `REGION_TOO_LARGE` (error) without calling Clipper2 (REQ-G2D-034). | unit: two squares 6712 mm apart | Reviewed |
| REQ-OFF-032 | WHEN `machined_area` is called with an operation's tool-centre paths and its tool radius R, THE offset2d kernel SHALL flatten each path within t_flat with geometry2d's `build_chain` (open or closed; either air side, since m pays for the flattening), offset all of them in one `ClipperOffset` call with JoinType Round, EndType Round, ArcTolerance a and δ = R − m, m = t_flat + 6u, without the bias of D-132, IF R ≤ m THEN raise `ValueError` (research 02, Booleans, RR-001; the flattening function, the refusal ours, DEC-OFF-007). | test 22; unit: a straight path and an arc path grown by R: the result contains the true stadium or annular sector of radius R − m − a − 3u and lies inside that of radius R − m + 3u, the arc path through its flattening on either side | Reviewed |
| REQ-OFF-044 | WHEN `stock_layer` is called with a raw stock layer and the machined areas of operations 1 to k, THE offset2d kernel SHALL return the raw layer, flattened toward more stock (geometry2d's side-correct flattening of a material region), minus all k machined areas in one `Clipper64` Difference call, the clip paths united by the Positive rule inside that call, and never from an earlier stock layer (research 02, Booleans, RR-001; D-026; DEC-OFF-006). | test 22: a 100 × 60 mm layer, a pocket and a profile: the result contains every point the exact geometry leaves as stock and no point farther than 2·t_flat + a + 12u outside it (research 02 gives 2·t_flat + 12u; the round joins' chords add up to a, DEC-OFF-007); the operations in the other order give the same arrays | Reviewed |
| REQ-OFF-033 | THE offset2d module SHALL take the input of every offset from source loops (`CurveRows`), so an offset is never chained on an earlier result (D-132; trap 2). | review: no public offset takes a `PolygonRegion` | Reviewed |

### Source IDs, pinch points and order (research 02, Source IDs; Pinch points and nesting; Order and determinism)

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-OFF-034 | WHEN a Clipper2 call of offset2d returns (every call but `offset_region` at t = 0, REQ-OFF-024), THE offset2d kernel SHALL give each output edge the source ID of the input edge nearest to its midpoint, and on a tie within eps_len the edge of the first class in the order material, cleared, air, then the lower source ID (D-059; Q-037 answer; trap 7; the last tie ours). geometry2d's `nearest_segments` returns one segment, the lower index on an exact tie, so it cannot give the candidates within eps_len (Open questions, 1). | test 14: the 60 × 40 material rectangle with its top edge tagged air, grown by 5; test 10: every output edge's distance to its source edge in the band | Reviewed |
| REQ-OFF-035 | WHEN `boolean` assigns source IDs, THE offset2d kernel SHALL apply REQ-OFF-034 over the edges of both operands, so that where a material edge and an air edge overlap, material wins (D-059). | Vatti note test 7: an air edge collinear with and overlapping a material edge comes out material | Reviewed |
| REQ-OFF-036 | WHEN a result path visits a grid point twice, THE offset2d kernel SHALL split it there by exact integer keys into pieces in traversal order, and mark every vertex at a grid point that two or more output vertices share, in one path or several, as a fixed node; both forms Clipper2 2.0.1 returns for one touch SHALL give the same arrays bit for bit (D-084; DEC-G2D-036; trap 6). | test 15, each case in both input orders | Reviewed |
| REQ-OFF-037 | THE offset2d module SHALL return no nesting: a CCW loop is an outer boundary, a CW loop a hole, and a piece of area 0 is dropped (research 02, Pinch points and nesting; DEC-G2D-036; ours). | test 15; test 3 (the pinch of the bow-tie) | Reviewed |
| REQ-OFF-038 | THE offset2d module SHALL return its loops in a canonical order independent of Clipper2's path order: each loop starting at its smallest grid point, the loops sorted by that point, then their signed area, then the rotated loops point by point (DEC-G2D-036). | test 15 in both input orders; test 19 | Reviewed |
| REQ-OFF-011 | THE offset2d module SHALL be single-threaded and return bit-identical arrays and diagnostics for the same input and `Context` on one platform, and on the three platforms the same counts and geometry within 0.001 mm (D-055). | test 19 | Reviewed |
| REQ-OFF-010 | WHEN a region is translated, THE offset2d module SHALL return the translated result with the same topology and vertices within 3u, except near a critical distance (re-centring before rounding; DEC-G2D-034; research 02, Order and determinism and test 17). geometry2d's REQ-G2D-033 allows 6 grid units for its region; if test 17 measures more than 3u, the step stops and asks instead of widening it (ours). | test 17: test 10's regions moved by (10 000, −10 000) mm | Reviewed |

### Results, failures and parameters (research 02, Failure modes; Parameters)

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-OFF-039 | WHEN an offset with t > 0, a Boolean or `stock_layer` leaves no area, a slot exactly 2t wide included, THE offset2d module SHALL return an empty region with `OFFSET_EMPTY` (info), not an error (research 02, Critical distances; Held, limit 4; for Booleans ours). | test 6 (SHRINK by 8); test 7 (SHRINK by 30) | Reviewed |
| REQ-OFF-040 | THE offset2d module SHALL return the diagnostics of the geometry2d calls it makes (`loop_tree`, `build_region`, `build_chain`, `cleanup`) unchanged and in their order, warnings included (`LOOP_DEGENERATE`, `LOOP_DUPLICATE`, `LOOP_SLIT`, `CLEANUP_SPIKE`), and IF one of them is an error, THEN return no result; it reports nothing more for the input's clean-up (research 02, Failure modes; ours). | unit: two crossing squares give `LOOPS_CROSS` and no region; a square with a spike gives `CLEANUP_SPIKE` and its offset | Reviewed |
| REQ-OFF-014 | IF Clipper2 reports failure, the result's area is implausible for an offset by t (a bound decided in DECISIONS.md before step 4, see Open questions), a coordinate leaves the integer range, a round join would need more than the declared limit of 2^16 steps per turn, the guard of REQ-OFF-023 leaves more than one loop, or, until that guard exists, the path Clipper2 takes as the outer loop is a hole (DEC-OFF-008), THEN THE offset2d module SHALL return no result with `OFFSET_FAILED` (error), the kernel reporting it as a status and throwing nothing, and log the input through `ctx.logger` for replay (research 02, Failure modes; the replay format comes with `tools/replay`). | review; unit for the step limit through the internal kernel entry, which takes the limit as a plain value (REQ-OFF-042), called with a lower one; Clipper2 gives no way to force its own failure | Reviewed |
| REQ-OFF-013 | IF the arguments have the wrong shape, the clearance is not finite or is negative, or 0 for a chain function (a chain at t = 0 needs no offset, research 02, Open chains; ours), a source ID is missing from `classes`, or a, from the `Context`, lies below 2u, THEN THE offset2d module SHALL raise `ValueError` (research 02, Failure modes). | unit, one case each | Reviewed |
| REQ-OFF-041 | WHEN `ctx.cancel` is set, THE offset2d module SHALL check it before and after each kernel call and return no result with `CANCELLED` (warning; the code ours) (research 02, Failure modes). | unit: a token cancelled before the call | Reviewed |
| REQ-OFF-042 | THE offset2d module SHALL take a, the bias of 3u, the span limit and the join step limit from declared parameters and pass them to its kernel as plain values, so no kernel source holds them as literals (D-049; as REQ-G2D-230). | review; tests that the limits come from the defaults file | Reviewed |

## Invariants

- Every boundary point of a region offset with t > 0 lies in the band [t, t + a + 6u] from the flattened input boundary (REQ-OFF-025; [t, t + t_flat + a + 6u] for `grow_chain`, REQ-OFF-027); with t = 0, within 2.83u (REQ-G2D-030, through REQ-OFF-024).
- Outside the band, a point lies in the result exactly when the definition of REQ-OFF-020 (offsets) or op(inside(a), inside(b)) (Booleans) says so (tests 2 and 9).
- Every output vertex has a source ID from the input and a fixed flag of 0 or 1; loops meet only at fixed nodes, except where a vertex of one loop lies on another loop's edge, a later part (REQ-OFF-034, 036).
- The same input gives the same arrays bit for bit, whatever Clipper2's path order (REQ-OFF-011, 036, 038).

## Tolerance budget

The budget is foundation's (REQ-FND-009, D-146). The offset spends a + 6u of the geometry part: a for the join chords, 6u for Clipper2's rounding (the bias of 3u and the result's 2.83u). The rest of the geometry part, 0.05·tol, covers flattening and snapping, which geometry2d spends (t_flat). A Boolean moves points by up to 2.83u again in no fixed direction; walls at the finishing tolerance never come from a chained result (research 02, Booleans). offset2d reads eps_len, u and tol from `ctx.tolerances`.

## Failure modes and diagnostics

| Situation | Result | Diagnostic |
| --- | --- | --- |
| The region vanishes, a slot exactly 2t wide included, or a stock layer is machined away | empty region | `OFFSET_EMPTY` (info; REQ-OFF-039) |
| Loops cross, or another loop tree or chain error | no result | geometry2d's codes, such as `LOOPS_CROSS` (error; REQ-OFF-040) |
| Warnings of the geometry2d calls (dropped, duplicate or slit loops, spikes); an empty region at t = 0 | the result, as geometry2d gives it | geometry2d's codes, such as `LOOP_DEGENERATE`, `CLEANUP_SPIKE`, `REGION_EMPTY` (warning; REQ-OFF-024, 040) |
| Input plus 2·\|δ\| (and the guard), the operands of a Boolean or of `stock_layer`, or the paths of `machined_area` plus 2·δ, span 2^26 grid units or more | refused, Clipper2 not called | `REGION_TOO_LARGE` (error; REQ-OFF-018, 031) |
| A closed chain given to a chain function | no result | `CHAIN_CLOSED` (error; REQ-OFF-029) |
| Clipper2 fails, an implausible area, coordinates out of the integer range, more than 2^16 join steps per turn, the guard leaves more than one loop; until step 5, a hole holding the extreme point | no result; input logged for replay | `OFFSET_FAILED` (error; REQ-OFF-014) |
| Cancelled | no result | `CANCELLED` (warning; REQ-OFF-041) |
| Arguments of the wrong shape, a clearance not finite or negative, a chain clearance of 0, a tool radius R ≤ t_flat + 6u for `machined_area`, a source ID without a class, a < 2u | programming error | `ValueError` (REQ-OFF-013) |

Clean-up of the input is geometry2d's and reported there (`CLEANUP_SPIKE`, `LOOP_SLIT`); offset2d passes those diagnostics on (REQ-OFF-040). Near a critical distance there is no diagnostic (REQ-OFF-026).

## Algorithms and design inputs

| Element of the method | Public source, or own design with date |
| --- | --- |
| Offset area, clearance form; straits and critical distances | Held 1991 (SRC-030), Def. 7.1, Lemmas 7.5 and 7.7 |
| Offset and union in one call; round joins and their step count; the orientation guess | Clipper2 2.0.1 (SRC-122: `ClipperOffset::ExecuteInternal`, `DoRound`, `GetLowestClosedPathInfo`) |
| Bias 3u, ArcTolerance a, the band | D-058, D-132, D-146; SRC-118 (the 2.83 grid units) |
| Orientation guard triangle | own design, research 02, The kernel call, step 3 (2026-10-08) |
| One side of a chain (Butt ends, side per output edge, caps) | own design, research 02, Open chains (2026-10-08) |
| Booleans, Positive fill rule | Vatti 1992 (SRC-004) through Clipper2 (SRC-122); the fill rule own design (2026-10-08) |
| Source IDs by the nearest input edge; the class tie | D-059, Q-037 answer; Vatti and Held notes; the last tie own design (2026-10-08) |
| Pinch split, fixed nodes, canonical order | D-084; DEC-G2D-036 |
| Stock update: machined areas from centre paths grown by R − (t_flat + 6u), one Difference from the raw layer | own design, research 02, Booleans and test 22 (RR-001, 2026-10-09) |
| Exact orientation on the grid | Shewchuk 1997 (SRC-032), through geometry2d's `exact.hpp` |

## Example parts

- An island tangent to the pocket wall (test 16): the offset never comes closer than t to either loop. The golden case `pocket-island-touching-wall` does not exist yet; it is created with the test and a person approves it.
- A circular island tangent inside a circular wall at its top (test 21): the island's flattening reaches above the wall's, and Clipper2's orientation guess would invert the offset without the guard.
- Two pockets joined by a strait (test 8): one region or two, decided by the grid.
- A slot exactly the tool's width: no region (REQ-OFF-039); a profile on its centre line or a slot operation machines it (topic 22).
- A C-shaped open chain with the tool inside and an opening narrower than 2t (test 12).
- A rapid move grown by R + 0.2·R for a link check (D-062, test 13).

## Test plan

- Unit: research 02's tests 1, 3 to 8, 11 to 15, 18 and 21, and the Vatti note's test 7; one case per row of Failure modes.
- Property: source IDs and fixed flags on test 10's random regions (every vertex has an input ID and a flag of 0 or 1; vertices at shared grid points are fixed); the Boolean oracle (test 2) and the offset oracle (test 9), point sampling against the definitions with d computed against the true lines and arcs within 64·ε·S (`tests/support/offset2d_oracles.py`, generators in `offset2d_strategies.py`), independent of Clipper2 (A-053); the band (test 10); translation (test 17); determinism (test 19). Generators: random nested loops of lines and arcs from geometry2d's test 7 generator, with islands whose flattening overlaps the wall's.
- Golden cases: `pocket-island-touching-wall` (test 16), new.
- Differential: test 20, shapely/GEOS buffers with round joins as point sets outside the band (D-060), once shapely is a test dependency (Open questions, 3).
- Cross-platform: tests 6, 7, 15 and 19 on the three systems in CI.

## Performance budget

10⁴ segments in under 50 ms on the reference machine, a target (research 02, Parameters; SRC-118 measured 35 ms outward and 71 ms inward on dense input, which is reduced within its tolerance before the offset; D-136).

## Size estimate

About 1050 NLOC (Clipper2 not counted): the offset call with its bias, the t = 0 path, the span check and the band about 300 (Python and C++); the orientation guard 100; source IDs with classes 120; the chain functions 250; the Booleans, `machined_area` and `stock_layer` 200; argument checks and diagnostics 100. Tests about 2400 lines. Budget in `architecture/modules.yaml`: 1500 NLOC (Peter, 2026-10-08), which leaves room.

## Open questions

None open. Peter answered the four questions of the draft on 2026-10-08:

1. geometry2d's grid internals and a tie-aware nearest-segments entry become its kernel interface: yes (DEC-OFF-001; plan 0005, step 3).
2. `ToleranceSet.arc_tol_mm`, `offset_bias_grid_units`, `join_steps_max` and a foundation code `CANCELLED`: yes (DEC-OFF-002; step 2).
3. shapely for test 20: yes, through an ADR that records D-060, shapely and GEOS in a test-only dependency group, never shipped (GEOS is LGPL); in the last step (DEC-OFF-003).
4. The interface for release 1, the side from the kind and closed chains refused: yes (DEC-OFF-004).

The deviations from research 02 are accepted (DEC-OFF-005). RR-001 is answered in research 02 (Booleans, test 22; pull request 47, DEC-OFF-006).

Box 2, decided in the module when the step comes (DECISIONS.md): when an area is "implausible for an offset by t" (REQ-OFF-014; research 02 gives no bound, so a bound with its reasoning goes into DECISIONS.md, or a research request if none can be derived); how `CHAIN_CLOSED` decides that a chain closes (exact equality of its ends, or within eps_len).

## Change log

- 2026-10-08: drafted from research 02 with `/research-to-spec` (plan 0005).
- 2026-10-08: spec-reviewer round: the band measured from the flattened input (and + t_flat against the true curves); the side from the region's kind; `OpenPaths` for one side of a chain; t_flat added to `grow_chain`'s δ; `cleanup` before the kernel (new REQ-OFF-043, trap 9); geometry2d's diagnostics passed on, `build_region`'s at t = 0; the guard's failure as `OFFSET_FAILED`; chains refuse t = 0; REQ-OFF-032 blocked by RR-001; test audit: `grow_chain`'s wider band written out, 3u for test 2 marked ours, a property test for invariant 3; `nearest_segments` added to Open question 1, `CANCELLED` to 2, the types and two scope choices to 4.
- 2026-10-08: reviewed by Peter: the four questions answered as recommended, the deviations accepted, every requirement but REQ-OFF-032 `Reviewed` (DEC-OFF-001 to 006); a tool outside a drawn boundary (topic 25) added to Later parts.
- 2026-10-09: the stock update released from research 02's answer to RR-001 (Booleans, test 22; pull request 47; DEC-OFF-006): `remove_machined` becomes `machined_area` (REQ-OFF-032, each operation's centre paths grown by R − (t_flat + 6u) in one call) and `stock_layer` (new REQ-OFF-044, the raw layer minus all machined areas in one Difference call), as Peter asked; the names ours.
- 2026-10-09: spec-reviewer round on the stock update: JoinType Round and ArcTolerance a stated, the centre paths flattened by `build_chain` (closed passes too), test 22's bound + a for the join chords (DEC-OFF-007), the span check, source IDs and `OFFSET_EMPTY` extended to `machined_area` and `stock_layer` (REQ-OFF-031, 034, 039); REQ-OFF-038 names the point-by-point tie (DEC-G2D-042).
- 2026-10-09: plan 0005, step 4: `offset_region` implemented (REQ-OFF-013, 014, 018, 020 to 022, 024 to 026, 039 to 043; tests in `tests/offset2d/unit/test_offset_region.py` and `tests/offset2d/property/test_offset_region_property.py`). Measured: in a region of air, research 02's test 21 shape makes Clipper2 invert the shrink to an empty result, which the area check cannot see, so until step 5's guard the kernel refuses a hole holding the extreme point (REQ-OFF-014, DEC-OFF-008); source IDs provisional until step 6 (DEC-OFF-009); the span check through `frame_of` (DEC-OFF-010).

[r02]: ../../../docs/research/02-offsets-and-booleans.md
[tests]: ../../../docs/research/02-offsets-and-booleans.md#tests

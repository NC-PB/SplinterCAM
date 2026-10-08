# SPEC: geometry2d

<!-- The planar geometry of every later module. Slice 1 of the topic 01 part, cut on 2026-10-02 from the draft of plan 0001, step 4 (plan 0003, step 1); slice 2 cut on 2026-10-07 from the same draft (plan 0004, step 1). Requirement IDs keep the draft's numbers; the change log names the IDs merged into a neighbour, and Later parts the rest. -->

| | |
| --- | --- |
| Status | Slice 1 released by [plan 0003](../../../docs/plans/completed/0003-geometry2d-slice-1.md) on Peter's answers of 2026-10-02, implemented and reviewed. Slice 2 released by [plan 0004](../../../docs/plans/completed/0004-geometry2d-slice-2.md) on Peter's answers of 2026-10-07 (DEC-G2D-022), implemented and reviewed; his answers to its questions recorded as DEC-G2D-024 to 027, 038 and 039. Plan 0005, step 3 extends the kernel interface for `offset2d` with REQ-G2D-242 (Peter, 2026-10-08, DEC-OFF-001; DEC-G2D-041). Choices marked "(ours)" answer open questions of the draft without asking again (D-159) |
| Layer | 1 (see architecture/modules.yaml) |
| Depends on | foundation |
| Research | [01][r01]: the main text is normative, the literature notes are evidence. This SPEC links to it instead of restating it |
| Decisions | D-025 (open chains for profiles), D-028 (units), D-049 (no values buried in code), D-055 (determinism), D-057 (curve type, arc form, bulge), D-058 and D-132 (grid of 10⁴ per mm, chords in air), D-059 (source IDs), D-060 (no external Python Clipper2 binding), D-084 (pinch points, fixed nodes), D-097 (exact predicates, strict float flags, snapping first); ADR 0009 (vendored `predicates.c`, proposed); text in [docs/spike/decisions-snapshot.md](../../../docs/spike/decisions-snapshot.md) |
| Owner | Peter Burgener |

## Purpose

The planar geometry every later module builds on. Slice 1 gives exact sign tests, lines and arcs with their validation, DXF bulge conversion, distances and closest points, the circle through three points, flattening with a known error side, signed area and orientation, point in region, polyline cleanup and bounding boxes. Slice 2 turns closed loops of lines and arcs into the machining region of an operation: the loop tree (degenerate, duplicate and crossing loops reported; parents, depths and normalised orientation), the side-correct flattening, and the Clipper2 PolyTree with source IDs and fixed nodes; it also flattens open chains for profiles. Its users are io (curves from DXF), the offsets of topic 02 (plan 0005), arc fitting in toolpath (topic 11) and the strategies.

## Scope

- In: [research 01][r01], sections Units and conventions, Vectors and exact signs (planar), Curves (lines and arcs), Distances and closest points, Circle through three points, Flattening (single curves; regions and open chains of lines and arcs), Area and orientation, Point in region (lines and arcs), Loop tree, Tolerances (t_topo, u and the resolution chain up to the PolyTree), Kernel arrays (curve rows and polygon regions) and Helpers (cleanup of polylines, bounding boxes of lines and arcs).
- Out: everything under [Later parts](#later-parts), among them the offsets and Booleans of topic 02 (plan 0005) and ellipse and spline edges; `ToleranceSet` and the budget (foundation); reading DXF and STEP (io); chaining selections into loops and resolving crossings before the loop tree (topic 25).
- Non-goals: an epsilon in any sign test; exact constructions (centres and flattened points are rounded, D-055 tier 3); a linear algebra library; a convex hull.

## Public interface

Lengths in mm, angles in radians, float64 (D-028). The exact predicates take no `Context` and return plain values; every other public function takes `ctx: Context`, and a function that can report a diagnostic returns a `Result` (Peter, 2026-10-02). "kernel:" names the C++ file that runs its loops (docs/dev/03, split rule); file and type names not in research 01, Interfaces, are ours.

```python
Point = tuple[float, float]
class PointLocation(IntEnum): OUT = 0; IN = 1; ON = 2
class AirSide(Enum): LEFT; RIGHT                       # where air lies, seen along the curve

@dataclass(frozen=True, slots=True)
class Line: p0: Point; p1: Point
@dataclass(frozen=True, slots=True)
class Arc: p0: Point; p1: Point; centre: Point; sweep_rad: float   # D-057; radius_mm = |p0 − centre|
Curve = Line | Arc                                     # EllipseArc and Nurbs: later parts
@dataclass(frozen=True, slots=True)
class CurveRows: rows: NDArray[np.float64]; ids: NDArray[np.int64]; row_starts: NDArray[np.int64]
@dataclass(frozen=True, slots=True)
class ClosestPoint: point: Point; parameter: float; distance_mm: float
@dataclass(frozen=True, slots=True)
class Box: x_min_mm: float; y_min_mm: float; x_max_mm: float; y_max_mm: float
@dataclass(frozen=True, slots=True)
class Circle: centre: Point; radius_mm: float

# Slice 2
class RegionKind(Enum): MATERIAL; AIR                  # what fills the region the loops bound
@dataclass(frozen=True, slots=True)
class PolygonRegion: points: NDArray[np.float64]; loop_starts: NDArray[np.int64]; source_ids: NDArray[np.int64]; fixed: NDArray[np.uint8]
@dataclass(frozen=True, slots=True)
class FlatRegion: region: PolygonRegion; extra_clearance_mm: float
@dataclass(frozen=True, slots=True)
class FlatChain: points: NDArray[np.float64]; source_ids: NDArray[np.int64]; extra_clearance_mm: float   # (n, 2), open; (n − 1,)
@dataclass(frozen=True, slots=True)
class LoopTree:
    loops: CurveRows                                   # kept loops, normalised, in input order
    parent: NDArray[np.int64]                          # (k,), index into loops, −1 for none
    depth: NDArray[np.int64]                           # (k,)
    input_index: NDArray[np.int64]                     # (k,), the loop's index in the input; the pieces of a loop split at a slit share it
    crossing_points: NDArray[np.float64]               # (c, 2), the crossings of LOOPS_CROSS
    crossing_loops: NDArray[np.int64]                  # (c, 2), their input loops, equal for a self-crossing

# Exact predicates: (n, 2) float64 arrays in, (n,) int8 signs out. kernel: exact.cpp, vendor/predicates.c
def orient2d(a, b, c) -> NDArray[np.int8]: ...
def incircle(a, b, c, d) -> NDArray[np.int8]: ...
def in_arc_circle(q, centre, p0) -> NDArray[np.int8]: ...       # +1 inside, like incircle (Peter)
def are_parallel(a, b, ctx) -> NDArray[np.bool_]: ...           # NumPy

def make_line(p0, p1, ctx) -> Result[Line]: ...
def make_arc(p0, p1, centre, sweep_rad, ctx) -> Result[tuple[Curve, ...]]: ...   # (Arc,), (Line,) or (); kernel: arcs.cpp
def curve_rows(rows, ids, row_starts, ctx) -> Result[CurveRows]: ...             # read-only copies
def arc_from_bulge(p0, p1, bulge, ctx) -> Result[Curve]: ...
def bulges_from_arc(arc, ctx) -> tuple[tuple[Arc, float], ...]: ...             # two for a full circle
def closest_point(curve, q, ctx) -> ClosestPoint: ...
def bounding_box(curve, ctx) -> Box: ...
def circle_through(p1, p2, p3, ctx) -> Circle | None: ...                     # kernel: exact.cpp
def flatten(curve, t_mm, side: AirSide | None, ctx) -> NDArray[np.float64]: ...  # kernel: flatten.cpp
def signed_area(loop: CurveRows, ctx) -> Result[float]: ...                   # one loop; kernel: area.cpp
def point_in_region(q, loops: CurveRows, ctx) -> NDArray[np.int8]: ...         # PointLocation; kernel: region.cpp
def cleanup(points, ctx) -> Result[NDArray[np.int64]]: ...                    # kept vertex indices; kernel: cleanup.cpp

# Slice 2. kernel: flatten.cpp, distance.cpp, loop_tree.cpp, polytree.cpp (Clipper2)
def polygon_region(points, loop_starts, source_ids, fixed, ctx) -> Result[PolygonRegion]: ...   # read-only copies
def loop_tree(loops: CurveRows, ctx) -> Result[LoopTree]: ...
def flatten_loops(tree: LoopTree, kind: RegionKind, ctx) -> FlatRegion: ...   # side-correct, before Clipper2
def build_region(loops: CurveRows, kind: RegionKind, ctx) -> Result[FlatRegion]: ...   # the PolyTree
def build_chain(rows, ids, air_side: AirSide, ctx) -> Result[FlatChain]: ...  # one open chain (D-025)
```

- Loops cross module boundaries as `CurveRows`, single curves as `Line` and `Arc` (ours). A `Line` or `Arc` built directly is unchecked; `make_line`, `make_arc`, `arc_from_bulge` and `curve_rows` are the validating entries, and the other functions expect their output.
- `make_arc` applies its rules in this order (ours, the draft's proposal): non-finite values, sweep range, r ≤ eps_len after its own radial check (DEC-G2D-018), nearly closed, radial check, angle check. 2π is the double nearest 2π (ours).
- `closest_point`'s parameter is t ∈ [0, 1] on a line and the angle from P_0 in the sense of φ on an arc (ours). `circle_through`'s radius is |P_1 − C| (ours).
- `cleanup` takes a closed polyline (n, 2) and returns the indices of the vertices it keeps, in order, so callers carry source IDs along (ours). Its passes run in the order merge, collinear, spike (research 01, Helpers); a kept vertex carries the vertices merged into it, so no vertex moves twice; the collinear and spike passes stop at three vertices, a loop that would lose more encloses nothing and the area test reports it (ours; the three-vertex stop confirmed by Peter, 2026-10-03).
- The exact predicates are exact for coordinates that are 0 or have a magnitude in [2^−142, 2^201], about 1.8e-43 to 3e60 mm: SRC-032 (p. 308) proves this range for orient2d and incircle, and our expansions of the arc predicates stay inside it (ours). A precondition, not checked (Peter); outside it products underflow or overflow. A NaN or infinite coordinate is a programming error, `ValueError` (ours), since it would read as sign 0.
- For eps_len ≥ 1e-6 mm (the default), `signed_area` guarantees its sign for loops whose arcs all have r·min(1, φ²) ≤ 10^7 mm and whose end points have a half-extent E ≤ 10^9 mm (DEC-G2D-016, ours); the float limits of REQ-G2D-131 assume the same eps_len: beyond them the rounding of the segment terms or of the translation could reach eps_len·L. A precondition, not checked (Peter, 2026-10-03).
- Arcs are valid input up to a radius of 10^9 mm (DEC-G2D-019, ours): beyond it the rounding of |P − C| can exceed eps_len, and `make_arc`, `arc_from_bulge` and `curve_rows` may reject a valid arc with `ARC_INCONSISTENT` (at 10^10 mm about a third of valid bulges were). A precondition, not checked (Peter, 2026-10-03). `signed_area` has a tighter one (DEC-G2D-016). REQ-G2D-047 and 048 apply to `make_arc` only; `curve_rows` checks every arc row by REQ-G2D-042 and 043 at any radius (ours).
- `flatten` expects t ≥ eps_len (DEC-G2D-020, ours). Within that and the radius limit a full circle needs fewer than 2^31 steps; the `ValueError` for a count beyond an int fires only outside them. A precondition, not checked.
- Internal entries for tests, not in `__all__`: `two_sum`, `two_product` (exact.cpp) and `point_in_region_exact`, the exact layer alone. Slice 2 adds `contained_by_difference(b, a, ctx) -> tuple[bool, float]` (the rule 5 fallback: B ⊂ A, and the area of B minus A in mm²), `fallback_inner(a, b, ctx) -> int` (the tie of two fallback results: 0 when a is the inner loop, 1 when b; a precedes b in input order), both on single loops as `CurveRows`, and `grid_union(points, loop_starts, ctx) -> Result[PolygonRegion]`, Clipper2's union through the grid bridge, for research 01 test 21 (D-060 allows no external Python binding; ours), and `region_with_fill_rule(region, fill_rule, ctx) -> Result[PolygonRegion]`, the PolyTree with a chosen fill rule, for REQ-G2D-177. Plan 0004, step 3 adds `topology_flattening(loops, ctx) -> PolygonRegion` (`_loops.py`; REQ-G2D-152), `polyline_distances(q, points, loop_starts, limit_mm) -> NDArray` (`_distances.py`; per point the distance to the nearest segment where at most the limit, else +inf; kernel: distance.cpp) and the kernel binding `basic_sin_cos`, the sine and cosine of the topology flattening (ours). Step 4 adds `screen_loops(loops, ctx) -> Result[Screened]` (`_screen.py`; rules 1 to 4: the kept loops with their cleaned topology flattenings, areas and lengths, and the crossings), `contact_points(a, b, limit_mm)` (`_crossings.py`); step 5 adds `Containment` and `both_ways` (`_contain.py`; the decision of two loops tested both ways), `polygon_area_length(points) -> tuple[float, float]` (`_area.py`; exact sums), and the kernel bindings `covered_by` and `crossing_depth` (the interval cover of REQ-G2D-158 and 237), ours. Plan 0005, step 3 adds the kernel binding `nearest_ties(q, points, loop_starts, limit, eps, out) -> int` (REQ-G2D-242): the (point, segment) rows written into `out` as far as it reaches, their count returned, as `contact_points` does (DEC-G2D-041).
- Slice 2 names (ours, Peter, 2026-10-07: DEC-G2D-022 keeps research 01's `loop_tree`, `build_region(loops, kind, ctx)`, `flatten_loops` and `build_chain`): loops come in as `CurveRows`, like every loop that crosses a module boundary; `flatten_loops` is public, so the side rule can be tested without Clipper2, and returns no diagnostics, since the tree's loops have passed the area tests. `build_chain` takes the rows and IDs of one open chain, which `curve_rows` cannot hold (its loops close), validated by REQ-G2D-234.
- When loops cross, `loop_tree` returns a tree with no loops, only `crossing_points` and `crossing_loops`, together with `LOOPS_CROSS` (error), and `build_region` returns no region (REQ-G2D-162, ours). One `LOOPS_CROSS` per crossing pair or self-crossing loop, `crossing_loops` with the lower input index first; one `LOOP_DEGENERATE` or `LOOP_DUPLICATE` per dropped or removed loop. Each diagnostic's `location` names the input indices ("loop 3", "loops 2 and 5"); diagnostics in input-loop order, crossing points sorted by their loop pair, then x, then y (ours, D-055). A region the PolyTree merges or drops loops of gets no diagnostic of its own (REQ-G2D-032); an empty region gets `REGION_EMPTY` (warning; ours).
- The topology flattening and the region work on the loops as curve rows; the rows themselves are not cleaned (cleanup of curve loops is a later part). The loop tree cleans the topology flattening, a polyline, with `cleanup` (ours).
- Normalising reverses a loop's rows, the last row first, each as [x1, y1, x0, y0, cx, cy, −sweep], not validated again. The reversed arc's radius is |P_1 − C|, up to eps_len from the original (research 01, Point in region, radial connector; DEC-G2D-012); point in region and `flatten` already allow for it (REQ-G2D-110, 150; ours).
- A `PolygonRegion` built directly is unchecked, like `Line` and `Arc`; `polygon_region` is the validating entry (ours).
- `flatten_loops` keeps REQ-G2D-185 and 186 for any tree: a row that ends where it starts, other than a full circle, adds no vertex, and in a loop that would keep fewer than 3 vertices an inscribed arc takes at least 2 steps, more than REQ-G2D-106 asks (ours, DEC-G2D-028).
- `PolygonRegion` holds the region as flat loops: an outer boundary is CCW, a hole CW, with no nesting stored; the parts of a loop split at a pinch point keep the traversal of their vertices (ours). The fixed flag is 0 or 1; in slice 2 only pinch points are fixed (ours). A region may hold no loop (k = 0).
- Clipper2 calls re-centre on the input's bounding box and round to u = `ctx.tolerances.grid_unit_mm` (REQ-G2D-033). The input of one call may span less than 2^26 grid units, about 6711 mm (REQ-G2D-034); this is checked, unlike the numeric preconditions of slice 1, because Clipper2's own double-precision decisions break silently beyond it (research 01, trap 17).
- Kernel interface for `offset2d` (Peter, 2026-10-08, DEC-G2D-040; extended by DEC-OFF-001 in plan 0005, step 3, DEC-G2D-041): `offset2d`'s C++ includes these geometry2d kernel headers and links their sources (`architecture/modules.yaml`, `kernel_includes`), and no others: `kernel/exact.hpp` (`Point2`, `Points`, `point`, `x`, `y`, `orient_sign` and the predicate entries), `kernel/distance.hpp` (`Polylines`, `polyline_distances`, `nearest_segments`, and `nearest_ties` with `TieReach` and `Tie`: per query point every segment within eps of the nearest distance, REQ-G2D-242) and `kernel/grid.hpp` (`GridStatus`, `GridLimits`, `grid_region` and its types, and the steps of `grid_region`: `Frame`, `frame_of`, `to_grid`, `split_pinches`, `canonical` and `shared_points`, REQ-G2D-033, 034, 181 and DEC-G2D-036). `kernel/grid.hpp` includes Clipper2's `clipper2/clipper.h`, so Clipper2's `Path64`, `Paths64` and `Point64` are part of this interface, and the build links Clipper2 to the kernel code publicly. A change to them is a change of this public interface: a SPEC change, decided by Peter. `build_region` stays in geometry2d; `offset2d` builds its own PolyTree inside its offset call.

## Requirements

"test N" is research 01's list of [tests][tests]; "note test N" the test ideas of its [Shewchuk note][shewchuk]. Status "Released" means released by plan 0003 (slice 1) or plan 0004 (slice 2, the sections from [Grid and topology tolerances](#grid-and-topology-tolerances-research-01-tolerances) on).

### Exact signs and determinism ([research 01, Vectors and exact signs][signs])

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-005 | THE geometry2d module SHALL take every decision on input geometry that depends on a sign (side, collinearity, inside or outside, the sweep an angle lies in) from exact predicates or exact comparisons of doubles, never from the sign of a rounded expression; loop orientation (REQ-G2D-131, 132), decided by a proven bound, is the one exception. | review; tests 5 and 12 | Released |
| REQ-G2D-006 | THE geometry2d kernel SHALL compute orient2d and incircle with Shewchuk's `predicates.c`, vendored unchanged (D-097, ADR 0009). | review | Released |
| REQ-G2D-007 | THE `orient2d` predicate SHALL return the exact sign of the orient2d determinant of research 01: +1 when c lies left of a → b, −1 right, 0 collinear. | property: note test 1, exact rationals as oracle | Released |
| REQ-G2D-008 | WHEN three points share their x or their y coordinate, THE `orient2d` predicate SHALL return 0. | note test 2 | Released |
| REQ-G2D-009 | WHEN two arguments are swapped, THE `orient2d` predicate SHALL return the negated sign. | property: note test 3 | Released |
| REQ-G2D-010 | WHEN the arguments are shifted cyclically, THE `orient2d` predicate SHALL return the same sign. | property: note test 3 | Released |
| REQ-G2D-011 | THE `incircle` predicate SHALL return the exact sign of the incircle determinant: +1 when d lies inside the circle through a, b, c given CCW, −1 outside, 0 cocircular, the opposite for CW. | note test 4 | Released |
| REQ-G2D-013 | THE geometry2d kernel SHALL call the initialisation routine of `predicates.c` once when the kernel module loads. | note test 1 as the first call in a fresh interpreter; review | Released |
| REQ-G2D-014 | THE build SHALL compile `predicates.c`, the geometry2d kernel and, from slice 2, Clipper2 (its intersection points decide vertex counts, REQ-G2D-232; ours) without floating-point contraction, fast-math or reassociation: `-ffp-contract=off` and `-fno-fast-math` on GCC and Clang, `/fp:precise` on MSVC from Visual Studio 2022 (17.0), which no longer contracts under it (D-097). | note test 7 in every build (the C++ arithmetic); note test 1's grid, which reaches stages B to D of `predicates.c` (the C flags); review of `CMakeLists.txt` | Released |
| REQ-G2D-015 | THE geometry2d kernel SHALL do its exact arithmetic in IEEE 754 binary64, round to nearest even, without extended-precision intermediates. | note test 7 | Released |
| REQ-G2D-016 | THE kernel's `two_sum` and `two_product` SHALL return a pair (x, y) with x + y equal to a + b, or a·b, exactly. | property: note test 7 | Released |
| REQ-G2D-017 | THE continuous integration SHALL run the build guard (note test 7) in every configuration that builds the kernel. | review of `check.yml` and `sanitize.yml` | Released |
| REQ-G2D-018 | THE geometry2d module SHALL make the same decisions for the same input doubles on macOS, Windows and Linux: predicate signs, point locations, kept vertices and diagnostic codes and severities, and the loop tree's kept loops, parents and depths (D-055, tier 1; the loop tree added in slice 2, ours). | cross-platform CI: tests 1, 2, 5 and 6 (test 23), and test 12 (ours); tests 7 and 24 (test 23), and test 7's generator with arcs | Released |
| REQ-G2D-231 | THE geometry2d module SHALL return bit-identical results (arrays, curves, diagnostics and their order) for the same input and `Context` on one platform under the pinned build profile (D-055, tier 2; Peter, 2026-10-02). | tests 3, 4, 8, 9, 12, 17 and 18 run twice, compared byte for byte; slice 2: tests 7, 16, 21 and 24 and the chain of REQ-G2D-117 | Released |
| REQ-G2D-232 | THE geometry2d module SHALL return outputs with equal counts on macOS, Windows and Linux, their geometry within 0.001 mm of each other (D-055, tier 3; Peter, 2026-10-02). | cross-platform CI on the tests of REQ-G2D-231 | Released |
| REQ-G2D-020 | WHEN `cleanup` takes sign decisions, THE function SHALL first merge vertices within eps_len and then apply the exact predicates to the merged vertices (D-097). | test 12; vertices merged before the exact tests | Released |
| REQ-G2D-021 | THE exact predicates SHALL take no tolerance and compare only with zero. | note test 1 (offsets of 2^−53); test 2 | Released |
| REQ-G2D-022 | THE `in_arc_circle(q, c, p0)` predicate SHALL return the exact sign of \|p0 − c\|² − \|q − c\|²: +1 inside the circle, 0 on it, −1 outside (Peter, 2026-10-02). | test 2, exact rationals as oracle | Released |
| REQ-G2D-023 | THE geometry2d kernel SHALL decide the sign of (q_y − c_y)² − \|p0 − c\|² exactly, so point in region compares q_y with c_y ± r without computing it (kernel `vertical_extent_signs`, used by `point_in_region`). | test 6; property against exact rationals | Released |
| REQ-G2D-024 | THE predicates SHALL take arrays of points and return one sign per row, with no Python loop per point. | review; a batch gives the signs of single rows | Released |
| REQ-G2D-233 | THE kernel's arctangent `basic_atan2` SHALL return atan2(y, x) within 4 rounding units, exactly 0, ±π/2 and π on the axes (π also for y = −0.0), computed from IEEE 754 basic operations only so its bits are the same on every platform (DEC-G2D-003, DEC-G2D-021; ours). | axis directions; 20 000 directions against libm; pinned bits on every platform | Released |
| REQ-G2D-240 | THE kernel's `basic_sin_cos` SHALL return sin and cos of an angle with \|angle\| ≤ 4π within 4 rounding units of 1, exactly ±0 and 1 at ±0 and ±1 at the doubles nearest π/2, π and 3π/2 where libm gives them, computed from IEEE 754 basic operations only so its bits are the same on every platform; another angle is refused (DEC-G2D-029; ours). | ±4π against libm; zero and the quadrant points; pinned vertex bits of the topology flattening on every platform | Released |

Release 1 kernels are single-threaded (Peter, 2026-10-02). Decisions and counts that need an angle (the arc angle check, the flattening count, the sweep of an arc) use our own arctangent, built from IEEE 754 basic operations in the kernel (`angle.cpp`, REQ-G2D-233), so they are the same on every platform (D-055, tier 1; ours). So does the circular segment term φ − sin φ of the signed area, which decides `LOOP_DEGENERATE` (ours). Constructed points (flattened vertices, centres) use the platform's libm and may differ in the last bit across platforms (tier 3). The topology flattening of the loop tree is the exception among constructed points: it turns its vertices with the kernel's own sine and cosine (REQ-G2D-152, 240), so the loop tree's decisions are tier 1 for loops with arcs too (ours).

### Tolerances and curves ([research 01, Tolerances][tol] and [Curves][curves])

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-003 | WHERE a requirement says a distance or angle lies within d, THE geometry2d module SHALL test value ≤ d, as `nearly_equal` does. | values exactly at eps_len count as within | Released |
| REQ-G2D-025 | THE geometry2d module SHALL read eps_len and eps_ang from `ctx.tolerances` on every call and hold no tolerance as a literal (D-049, REQ-FND-005). | a set with a larger `length_eps_mm` changes the outcome | Released |
| REQ-G2D-027 | THE `are_parallel` function SHALL report directions a and b as parallel exactly when \|a × b\|² ≤ sin²(eps_ang)·\|a\|²·\|b\|²; opposite directions and a zero vector count as parallel (ours); sin²(eps_ang) is computed once per call; below 2^−26 the correctly rounded sin(eps_ang) is eps_ang itself, which the libms of the three platforms return (ours). | test 22 | Released |
| REQ-G2D-035 | THE geometry2d module SHALL provide the tagged curve type `Curve` with the variants `Line` and `Arc` (D-057). | a match over the variants is exhaustive under pyright strict | Released |
| REQ-G2D-037 | THE `Arc` SHALL store P_0, P_1 and C exactly as given and a signed sweep φ in radians, positive CCW. | stored values equal the inputs bit for bit | Released |
| REQ-G2D-038 | THE geometry2d module SHALL take an arc's radius as r = \|P_0 − C\| in every computation. | test 2; an arc with P_1 just off the circle | Released |
| REQ-G2D-039 | THE geometry2d module SHALL never move an arc's P_1, except by the nearly closed rule (REQ-G2D-049). | property over `make_arc` and the bulge conversion | Released |
| REQ-G2D-040 | IF a line or an arc is given a NaN or infinite value, THEN `make_line` and `make_arc` SHALL reject it with `CURVE_INVALID` (error). | NaN and ±inf in each field | Released |
| REQ-G2D-041 | IF an arc is given φ = 0 or \|φ\| > 2π, THEN `make_arc` SHALL reject it with `CURVE_INVALID` (error). | φ = 0, −0.0, the double above 2π | Released |
| REQ-G2D-042 | IF \|\|P_1 − C\| − r\| > eps_len, THEN `make_arc` SHALL reject the arc with `ARC_INCONSISTENT` (error). | P_1 moved radially by less and by more than eps_len | Released |
| REQ-G2D-043 | IF the angle from P_0 to P_1 about C, in the sense of φ, differs from \|φ\| modulo 2π by more than eps_len / r, THEN `make_arc` SHALL reject the arc with `ARC_INCONSISTENT` (error). | P_1 at and beyond the limit; a CCW quarter given a negative sweep; a full circle accepted | Released |
| REQ-G2D-044 | WHEN geometry2d builds an arc from its end points, THE module SHALL place C on the perpendicular bisector of P_0P_1. | property: arcs from bulges with chords of 0.001 to 1000 mm and 0.001 ≤ \|b\| ≤ 1000 are never `ARC_INCONSISTENT`; minor and major arcs up to r = 10^9 mm (DEC-G2D-019) | Released |
| REQ-G2D-045 | THE `make_arc` function SHALL accept P_1 = P_0 with φ = ±2π as a full circle. | tests 6 and 20 | Released |
| REQ-G2D-047 | WHEN an arc has r ≤ eps_len, P_0 ≠ P_1 and \|\|P_1 − C\| − r\| ≤ eps_len (DEC-G2D-018, ours), THE `make_arc` function SHALL return the line P_0P_1. | new test; P_1 far off a tiny circle gives `ARC_INCONSISTENT` (REQ-G2D-042), P_1 within eps_len gives the line | Released |
| REQ-G2D-048 | WHEN an arc has r ≤ eps_len and P_0 = P_1, THE `make_arc` function SHALL return no curve. | new test | Released |
| REQ-G2D-049 | WHEN an arc has \|P_1 − P_0\| ≤ eps_len, \|φ\| > π and (2π − \|φ\|)·r ≤ eps_len, THE `make_arc` function SHALL return a full circle with P_1 = P_0 and φ = ±2π in the sense of the given φ. | new test | Released |
| REQ-G2D-050 | WHEN a bulge b ≠ 0 on a chord of length c > 0 is converted, THE `arc_from_bulge` function SHALL return the arc of research 01, Curves, with the given P_0 and P_1; IF a value is not finite, or c = 0 with b ≠ 0 (checked first, ours), THEN it SHALL return `CURVE_INVALID`. | test 8 | Released |
| REQ-G2D-051 | WHEN the bulge is 0, or its sagitta c·\|b\|/2 is at most eps_len (ours), THE `arc_from_bulge` function SHALL return the line P_0P_1. | b = 0, −0.0 and 10^−9 on a 1 mm chord | Released |
| REQ-G2D-052 | WHEN an arc that is not a full circle is exported, THE `bulges_from_arc` function SHALL return b = tan(φ/4). | the arcs of test 8 give back their bulges | Released |
| REQ-G2D-053 | WHEN a full circle is exported, THE `bulges_from_arc` function SHALL return two arcs split at the angle φ/2 (ours), the second starting bit for bit where the first ends. | the circle of test 6 | Released |

### Curve rows ([research 01, Kernel arrays][arrays])

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-188 | THE geometry2d module SHALL pass lines and arcs across the kernel boundary as curve rows: (m, 7) float64 [x0, y0, x1, y1, cx, cy, sweep], (m,) int64 IDs and (k,) int64 `row_starts`. | test 20 | Released |
| REQ-G2D-189 | WHEN the sweep of a row is 0 or −0.0, THE geometry2d module SHALL treat the row as a line. | test 20 | Released |
| REQ-G2D-190 | IF a line row has a cx or cy that is not NaN, THEN `curve_rows` SHALL reject the rows with `CURVE_INVALID` (error). | test 20 | Released |
| REQ-G2D-191 | IF an arc row has a non-finite cx or cy, or \|sweep\| > 2π, THEN `curve_rows` SHALL reject the rows with `CURVE_INVALID` (error). | test 20 | Released |
| REQ-G2D-192 | IF an arc row breaks REQ-G2D-042 or 043, THEN `curve_rows` SHALL reject the rows with `ARC_INCONSISTENT` (error) (Peter, 2026-10-02). | test 20, adapted: research 01 gives `CURVE_INVALID` | Released |
| REQ-G2D-193 | IF any other value of a row is NaN or infinite, THEN `curve_rows` SHALL reject the rows with `CURVE_INVALID` (error). | test 20 | Released |
| REQ-G2D-194 | IF a row does not start where the previous row of its loop ends, or the last row of a loop does not end where its first starts, compared bit for bit, THEN `curve_rows` SHALL reject the rows with `CURVE_INVALID` (error). | test 20 | Released |
| REQ-G2D-196 | THE `curve_rows` function SHALL accept a loop of one row (a full circle) and of two rows. | test 20 | Released |
| REQ-G2D-197 | IF the rows, IDs or `row_starts` have the wrong shape or dtype, or `row_starts` does not start at 0 and ascend strictly (ours), THEN `curve_rows` SHALL reject them with `CURVE_INVALID` (error). | test 20 | Released |
| REQ-G2D-201 | THE geometry2d module SHALL hand every array to its kernel as a C-contiguous copy and keep the arrays it returns read-only. | a strided view gives the result of its copy; results not writeable | Released |
| REQ-G2D-203 | THE geometry2d kernel functions SHALL take and return only NumPy arrays and plain values. | review of `bindings.cpp` and the stubs | Released |

### Distances, circles and bounding boxes ([Distances][dist], [Circle through three points][circle], [Helpers][helpers])

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-091 | WHERE the curve is a line with \|P_1 − P_0\| > 0, THE `closest_point` function SHALL return the clamped foot of research 01, its t and its distance. | feet inside, before P_0 and beyond P_1; property against exact rationals | Released |
| REQ-G2D-092 | WHEN a line has zero length, THE `closest_point` function SHALL return P_0 and \|Q − P_0\|. | test 17 | Released |
| REQ-G2D-093 | WHEN Q ≠ C and the direction of Q − C lies in the arc's sweep, decided by exact signs (Peter, 2026-10-02), THE `closest_point` function SHALL return C + r·(Q − C)/\|Q − C\| and \|\|Q − C\| − r\|. | test 17; the exact sweep edge; property against sampled arc points | Released |
| REQ-G2D-094 | WHEN the direction of Q − C lies outside the sweep, THE `closest_point` function SHALL return the nearer end point, P_0 when the squared distances are equal (ours). | test 17; property against sampled arc points | Released |
| REQ-G2D-096 | WHEN Q = C, THE `closest_point` function SHALL return P_0 and r without dividing by \|Q − C\|. | test 17 | Released |
| REQ-G2D-097 | WHEN `circle_through(P_1, P_2, P_3)` finds a circle, THE function SHALL return the centre of research 01 with D the value `predicates.c`'s orient2d returns, whose sign is exact. | test 9; property against exact rationals | Released |
| REQ-G2D-098 | IF orient2d(P_1, P_2, P_3) is 0, THEN THE `circle_through` function SHALL return no circle. | test 9 | Released |
| REQ-G2D-099 | IF \|orient2d(P_1, P_3, P_2)\| / \|P_3 − P_1\| ≤ eps_len, THEN THE `circle_through` function SHALL return no circle, decided before any division by D. | test 9 | Released |
| REQ-G2D-100 | IF P_1 = P_3, THEN THE `circle_through` function SHALL return no circle without dividing by \|P_3 − P_1\|. | P_1 = P_3 gives `None`; review: the kernel divides only when D ≠ 0 | Released |
| REQ-G2D-101 | THE `circle_through` function SHALL apply no radius or chord limit of its own. | test 9 | Released |
| REQ-G2D-213 | THE `bounding_box` function SHALL give a line the box of its end points. | new test | Released |
| REQ-G2D-214 | THE `bounding_box` function SHALL give an arc the box of its end points and of the points at the angles 0, π/2, π and 3π/2 about C that lie in its sweep, decided by exact signs, all four for a full circle; where the octants of the end points contradict the sweep within the tolerance of REQ-G2D-043, the sweep governs (ours). | test 18 | Released |

### Flattening ([research 01, Flattening with a known error side][flat])

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-102 | WHEN an arc is flattened inscribed within t, THE `flatten` function SHALL use the step Δθ_in of research 01. | test 4 | Released |
| REQ-G2D-103 | WHEN an arc is flattened inscribed in n steps, THE `flatten` function SHALL return n chords with their n + 1 vertices at the angles θ_0 + k·Δθ in the sense of φ. | test 4 | Released |
| REQ-G2D-104 | WHEN an arc is flattened circumscribed within t, THE `flatten` function SHALL use the step Δθ_out of research 01. | test 4 | Released |
| REQ-G2D-105 | WHEN an arc is flattened circumscribed in n steps, THE `flatten` function SHALL return the polyline of research 01 from P_0 through n vertices at radius r / cos(Δθ/2) to P_1, its first and last segments half tangents. | test 4 | Released |
| REQ-G2D-106 | THE `flatten` function SHALL give an arc n = ⌈\|φ\| / min(Δθ, π/2)⌉ steps of Δθ = \|φ\| / n, raising n by 1 when rounding makes \|φ\| / n exceed the bound. | test 4; property | Released |
| REQ-G2D-109 | WHEN t > 2r, THE `flatten` function SHALL return a finite inscribed polyline, its step set by the π/2 cap. | a full circle gives 4 chords | Released |
| REQ-G2D-110 | WHEN an arc is flattened, THE `flatten` function SHALL return a polyline within t of the arc's circle, inside it when inscribed and outside when circumscribed, up to 4 rounding units of r and, on the segment that ends at P_1, the distance of P_1 from the circle (ours). | test 4 (10^4 samples per segment) | Released |
| REQ-G2D-112 | THE `flatten` function SHALL return a curve's P_0 and P_1 bit for bit as the first and last points. | test 4; lines | Released |
| REQ-G2D-113 | WHEN `flatten` is given an arc and an air side, THE function SHALL flatten it inscribed when the centre lies on the air side (left of the arc for φ > 0) and circumscribed otherwise. | the four combinations on the circle of test 4 | Released |
| REQ-G2D-126 | WHEN `flatten` is given no side, THE function SHALL flatten an arc inscribed (ours). | new test | Released |

### Area, point in region and cleanup ([Area][area], [Point in region][pir], [Helpers][helpers])

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-001 | THE geometry2d module SHALL treat CCW as the positive sense, so a CCW loop has positive signed area. | test 3 | Released |
| REQ-G2D-002 | WHEN a loop is reversed, THE `signed_area` function SHALL return the negated area within the rounding bound of research 01 (ours). | test 3 | Released |
| REQ-G2D-128 | THE `signed_area` function SHALL return the area A of research 01 (polygon sum plus each arc's circular segment), in mm². | test 3 | Released |
| REQ-G2D-130 | THE `signed_area` function SHALL evaluate its sums after translating the loop so the centre of its end points' bounding box is the origin (ours). | property against exact rationals; the exact sum equals the translated loop's area within a rounding unit | Released |
| REQ-G2D-131 | WHERE a loop has n ≤ 10^6 vertices and a half-extent E ≤ 3355 mm, THE `signed_area` function SHALL decide the orientation from the floating-point polygon sum and the exactly summed segment terms (DEC-G2D-016, ours). | property against exact rationals, polygons and loops with arcs; full circles up to r = 10^7 mm; the bound at the limits | Released |
| REQ-G2D-132 | WHERE a loop has more than 10^6 vertices or E > 3355 mm (ours), THE `signed_area` function SHALL sum the polygon part exactly, with the segment terms. | a loop just above each limit; the exact path with arcs; property with arcs beyond 3355 mm | Released |
| REQ-G2D-133 | IF \|A\| ≤ eps_len·L, with L the loop length, THEN THE `signed_area` function SHALL return no value and `LOOP_DEGENERATE` (warning). | test 19 (widths 1e-7 and 1e-5 mm); strips just below and above the limit | Released |
| REQ-G2D-134 | THE `point_in_region` function SHALL classify each query point against the given loops as exactly one of IN, OUT and ON. | tests 5 and 6; note test 6 | Released |
| REQ-G2D-135 | THE exact layer (`point_in_region_exact`) SHALL compute the winding number over all loops by the ray rules of research 01, Point in region: arcs split at π/2 and 3π/2 by exact signs, half-open height ranges, ±1 per crossing edge; an arc runs on its circle of radius \|P_0 − C\| to the ray from C through P_1 and on along that ray to P_1, a radial connector where P_1 lies off the circle (Peter, 2026-10-03). | tests 5 and 6; rays through vertices and tangent at a circle's top and bottom; arcs split at their top and bottom; P_1 off the circle near a top and a bottom; the exact height of a connector's end; properties against an exact winding oracle and a fine flattening, also with P_1 off the circle | Released |
| REQ-G2D-139 | THE exact layer SHALL decide whether a straight edge passes right of q by orient2d alone, and an arc piece by the arc predicate and the sign of q_x − c_x. | tests 5 and 6; note test 6 | Released |
| REQ-G2D-143 | WHEN q lies on an edge (orient2d 0 within the edge's box, or q on the arc itself: an end point, a point of the circle whose direction from C lies in the sweep by the exact signs of REQ-G2D-093, or a point of the radial connector (Peter, 2026-10-03)), THE exact layer SHALL classify q as ON. | tests 5 and 6; note test 6; a tiny arc and a chord line meeting the circle again; outward, inward and slanted connectors | Released |
| REQ-G2D-145 | THE exact layer SHALL NOT classify q as ON from a zero of a helper test elsewhere (a chord line, the rest of an arc's circle). | test 5 | Released |
| REQ-G2D-148 | IF q lies within eps_len of the boundary, by the distances of REQ-G2D-091 to 096, measured on an arc to the nearer of the circles of radius \|P_0 − C\| and \|P_1 − C\| (also for Q = C) and on a line in both directions (Peter, 2026-10-03; ours), THEN THE `point_in_region` function SHALL classify q as ON. | test 5; note test 6; eps_len itself; the nearer radius; property against closest_point's distances | Released |
| REQ-G2D-149 | WHEN q is not ON, THE `point_in_region` function SHALL classify q as IN where the winding number is not 0 and OUT where it is 0. | tests 5 and 6; the winding over two loops | Released |
| REQ-G2D-150 | WHERE one loop is given, THE `point_in_region` function SHALL give the same result for both orientations. | the reversed loops of tests 5 and 6; arcs whose P_1 lies off the circle | Released |
| REQ-G2D-204 | WHEN cleaning a loop, THE `cleanup` function SHALL replace each run of consecutive vertices within eps_len of the run's first vertex by that vertex, walking from the first vertex. | test 12 (nine vertices, off a line) | Released |
| REQ-G2D-205 | WHEN every vertex of the last run lies within eps_len of the first vertex (ours), THE `cleanup` function SHALL join the last run to the first. | a last run within eps_len joins, one with a vertex beyond stays, also in a later round | Released |
| REQ-G2D-206 | THE `cleanup` function SHALL move no vertex by more than eps_len. | test 12; property on clusters within eps_len | Released |
| REQ-G2D-207 | THE `cleanup` function SHALL drop a vertex strictly between its neighbours with orient2d exactly 0, and keep one whose orient2d is not 0. | test 12 | Released |
| REQ-G2D-209 | WHEN a loop turns back exactly onto itself at a vertex, THE `cleanup` function SHALL drop that vertex and report one `CLEANUP_SPIKE` (info) per spike (ours). | test 12; two spikes, two diagnostics | Released |
| REQ-G2D-211 | WHEN `cleanup` drops a spike, THE function SHALL leave the loop's region and signed area unchanged. | test 12; property in exact rationals with random spikes | Released |
| REQ-G2D-212 | THE `cleanup` function SHALL repeat its three passes, in a fixed order, until none changes the loop (ours). | test 12; cleaning twice equals once | Released |

### Grid and topology tolerances ([research 01, Tolerances][tol])

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-026 | WHERE a float stage decides whether features touch or duplicate each other, THE geometry2d module SHALL use t_topo from `ctx.tolerances.topology_tol_mm` (REQ-G2D-158, 163); crossings are decided exactly (REQ-G2D-160). | tests 7 and 24 | Released |
| REQ-G2D-029 | THE geometry2d module SHALL take the grid unit u from `ctx.tolerances.grid_unit_mm` for the topology flattening and the Clipper2 scale of 10⁴ per mm, never from a literal or module-level state (REQ-FND-005). | review; a `ToleranceSet` test double that overrides `grid_unit_mm` changes the topology flattening's step count | Released |
| REQ-G2D-030 | WHEN float loops go through a geometry2d Clipper2 call, THE geometry2d kernel SHALL return a result whose every vertex lies within 2.83 grid units of the input polylines (SRC-118; measured from the output, ours: input vertices inside a union or difference have no counterpart). | test 21 through `grid_union` (D-060) | Released |
| REQ-G2D-031 | WHEN float loops have gone through a Clipper2 union, THE `point_in_region` function SHALL give the same result on the float input and on the integer result at every point farther than t_topo from every boundary, also where features lie between eps_len and t_topo apart. | test 21; this is research 01's measured claim that a union moves points by less than t_topo, not a consequence of REQ-G2D-030's 2.83 grid units | Released |
| REQ-G2D-032 | WHEN `build_region` has built the PolyTree, THE geometry2d module SHALL take the region's topology from the integer result only and not re-decide it with a float-stage test. | review; features between eps_len and t_topo apart that merge on the grid stay merged in the returned region | Released |
| REQ-G2D-033 | THE geometry2d kernel SHALL re-centre the input of each of its Clipper2 calls on the input's bounding box and round it to the grid u before the call (D-058, D-132; research 01, resolution chain, stage 3). | a region and a forced fallback pair, translated by several metres within REQ-G2D-034, give the same tree, the same region topology and vertex counts, region vertices within 6 grid units of the untranslated ones after translating back, and the same fallback answer | Released |
| REQ-G2D-034 | IF the input of a geometry2d Clipper2 call spans 2^26 grid units (about 6711 mm) or more in x or y, THEN THE geometry2d kernel SHALL refuse the call with `REGION_TOO_LARGE` (error; the code ours) and not call Clipper2 (SRC-122; draft REQ-OFF-018). The limit is a declared parameter passed to the kernel (research 01, Parameters; REQ-G2D-230). | `build_region` on loops farther apart than the limit and `contained_by_difference` on such a pair are refused; just below the limit accepted | Released |

### Flattening of regions and chains ([research 01, Flattening][flat])

Slice 2 handles lines and arcs only (DEC-G2D-022); the t/2 rules for ellipse and spline edges are later parts.

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-115 | WHERE the region kind is material, THE `flatten_loops` function SHALL flatten an arc with φ > 0 circumscribed and an arc with φ < 0 inscribed. | test 16 | Released |
| REQ-G2D-116 | WHERE the region kind is air, THE `flatten_loops` function SHALL flatten an arc with φ > 0 inscribed and an arc with φ < 0 circumscribed, on outer boundaries and islands alike. | test 16 (the same arcs in a pocket flip; an island in a pocket) | Released |
| REQ-G2D-117 | WHERE an open chain is flattened for a profile (D-025), THE `build_chain` function SHALL take the side the tool works on as the air side of every arc of the chain (REQ-G2D-113). | a chain of a line, a CCW and a CW arc, with the tool on the left and then on the right | Released |
| REQ-G2D-118 | THE `build_region` function SHALL hand the loops to `flatten_loops` as the loop tree normalised them, not as they were given. | review; the side-correct flattenings of the regions of test 16, given with every loop reversed, are the same bit for bit | Released |
| REQ-G2D-119 | WHEN `flatten_loops` flattens a region of lines and arcs, THE function SHALL return a boundary that lies in air or on the true boundary and within t of it, up to the allowance of REQ-G2D-110 and, on an arc the loop tree reversed, eps_len along the whole arc (its radius is then \|P_1 − C\|; ours). | test 16; property: random material and air regions of lines and arcs | Released |
| REQ-G2D-124 | THE `build_region` function SHALL return the extra clearance 0 for a region of lines and arcs (ellipse and spline edges: later parts). | the regions of test 16 | Released |
| REQ-G2D-125 | THE `build_chain` function SHALL return the extra clearance 0 for a chain of lines and arcs (ellipse and spline edges: later parts). | the chain of REQ-G2D-117 | Released |
| REQ-G2D-127 | THE `flatten_loops` and `build_chain` functions SHALL flatten with t = t_flat from `ctx.tolerances.flatten_tol_mm` (research 01, Flattening). | at tol = 0.01 mm the arcs' step counts follow REQ-G2D-106 at t = 0.000397 mm | Released |
| REQ-G2D-234 | IF the rows or IDs of `build_chain` break REQ-G2D-188 to 193 or have the wrong shape or dtype, the chain is empty, or a row does not start bit for bit where the previous one ends, THEN THE function SHALL reject them with the code of that rule, `CURVE_INVALID` for the shape, the empty chain and continuity; a chain whose last row ends where its first starts is accepted (ours). | one case per rule, adapted from test 20; an empty chain; a closed chain | Released |

### Polygon regions and the flattening of curve rows ([research 01, Kernel arrays][arrays])

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-183 | THE geometry2d module SHALL pass a polygon region across the kernel boundary as `points` (n, 2) float64 in mm, `loop_starts` (k,) int64, `source_ids` (n,) int64, the ID of the edge that starts at each vertex (D-059), and `fixed` (n,) uint8, the fixed-node flag, 0 or 1 (D-084; the values ours). | shapes and dtypes | Released |
| REQ-G2D-184 | THE `loop_starts` array of a polygon region SHALL start at 0 and ascend. | [1, 4] and [0, 4, 4] are rejected; property: every region a function returns | Released |
| REQ-G2D-185 | THE polygon region SHALL store each loop without repeating its first vertex at its end; the closing edge is implied. | as above | Released |
| REQ-G2D-186 | THE polygon region SHALL hold at least 3 vertices in every loop. | as above | Released |
| REQ-G2D-187 | IF polygon region arrays break REQ-G2D-183 to 186, or a point is not finite (ours), THEN `polygon_region` SHALL reject them with `REGION_INVALID` (error; the code ours) before any kernel computation. | one case per rule; an empty region (k = 0) is accepted | Released |
| REQ-G2D-199 | WHEN a loop of curve rows is flattened, THE geometry2d module SHALL hold each joint between two rows once in the result, as the first point of the second row's flattening. | the loops of test 20 flatten into closed loops without repeated vertices | Released |
| REQ-G2D-200 | WHEN curve rows are flattened, THE geometry2d module SHALL give each vertex the ID of the row whose flattened edge starts at it (D-059). | the line-and-arc loop of test 20: the line's ID on its first vertex, the arc's on the others | Released |

### Loop tree ([research 01, Loop tree][tree])

Rules 1 to 6 of research 01 on loops of lines and arcs. The rules run in this order, each on the loops that survived the one before: cleanup, a loop's crossings with itself (REQ-G2D-238, before the area tests, so a bow-tie of area 0 is reported, not dropped), the area tests, duplicates (each loop compared with the kept loops before it in input order), crossings, containment, depth and orientation (ours). Areas and lengths in REQ-G2D-157, 165 and 166 are those of the cleaned topology flattening; the orientation of REQ-G2D-175 is the sign of the cleaned topology flattening's area, which agrees with `signed_area` of the rows once the thinness test has passed, or of the depth-0 cycles for a loop that touches itself (ours). Crossings found by REQ-G2D-160 are kept or turned into touching contacts by REQ-G2D-237 and 238 (Peter, 2026-10-07: touching geometry is real and reaches the tree).

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-151 | WHERE the loops are normalised by the loop tree, THE `point_in_region_exact` function SHALL compute a winding number of 1 at every point inside the region and 0 outside it, at points farther than t_topo from every boundary (ours: touching loops may overlap by up to t_topo, REQ-G2D-237, where the winding can be −1 or 2). | property: normalised trees from the generator of test 7 | Released |
| REQ-G2D-152 | THE loop tree SHALL replace every arc, for topology only, by its inscribed flattening within u, plus on the chord that ends at P_1 that point's distance from the circle, at most eps_len (REQ-G2D-102 and 110 at t = u; the topology flattening; ours, research 01 says "two-sided"), its inner vertices computed with the kernel's own sine and cosine from IEEE 754 basic operations, like `basic_atan2` (REQ-G2D-018, DEC-G2D-003; ours). | the distance between each arc and its topology flattening is at most u; pinned vertex bits on every platform | Released |
| REQ-G2D-153 | THE loop tree SHALL decide each containment probe with `point_in_region` on the exact lines and arcs (the cycles of REQ-G2D-238 on their polylines). | tests 7 and 24 | Released |
| REQ-G2D-154 | THE loop tree SHALL make every decision (cleanup, degeneracy, duplicates, crossings, parents, depths) independent of the operation tolerance tol (`ctx.tolerances.chord_tol_mm`). | the same tree for tol = 0.05 mm and 0.01 mm (D-029) | Released |
| REQ-G2D-155 | THE loop tree SHALL clean the topology flattening of each loop with `cleanup` (REQ-G2D-204 to 212) before the tests of REQ-G2D-157 to 173, take every later test and probe from the cleaned flattening, and pass its `CLEANUP_SPIKE` diagnostics on (ours: the rows stay as given). | test 12's spike loop given to `loop_tree`; the same loop inside [0, 20]², starting at its spike tip outside the square, is the square's child | Released |
| REQ-G2D-156 | IF a loop fails the area test of REQ-G2D-133, THEN THE loop tree SHALL drop it and report `LOOP_DEGENERATE` (warning) once. | test 19 (width 1e-7 mm) | Released |
| REQ-G2D-157 | IF the cleaned topology flattening of a loop has \|A\| ≤ 1.5·t_topo·L, with its own area and length (ours), THEN THE loop tree SHALL drop the loop and report `LOOP_DEGENERATE` (warning). | test 19 (width 1e-5 mm dropped, 0.001 mm kept) | Released |
| REQ-G2D-158 | THE loop tree SHALL treat two loops as duplicates exactly when every point of each topology flattening lies within t_topo of the other polyline, both ways (Hausdorff distance at most t_topo), whatever their orientations (ours: research 01 tests vertices only, which takes a loop with a slot reaching the other's wall, or two loops crossing through the same vertices, for duplicates; DEC-G2D-030). | test 7 (a duplicate loop); tests 7 and 24 (a square and its notched copy are not duplicates); a reversed copy; a square and the same square with a V-slot reaching within 1e-4 mm of its wall are not duplicates; nor are two loops with the same vertices in another order | Released |
| REQ-G2D-159 | WHEN loops are duplicates, THE loop tree SHALL keep the first in input order, with its source IDs, and report one `LOOP_DUPLICATE` (warning) per removed loop. | test 7; the pair in the other order keeps the other loop's IDs | Released |
| REQ-G2D-160 | THE loop tree SHALL find every point where the topology flattenings of two loops, or of a loop with itself, meet, by exact tests (orient2d): proper segment crossings, shared vertices, vertices on another segment and the ends of shared stretches, a stretch a loop runs twice in the same direction included; whether they cross is REQ-G2D-237's and 238's to decide, which also covers boundaries that pass through each other at a vertex or along a stretch (ours, DEC-G2D-031: the depth rule makes research 01's cyclic-order test unnecessary). | test 7 (two crossing squares); a figure eight; a crossing by one rounding unit; [0, 10]² and [5, 15] × [0, 10], which meet only at vertices and shared stretches; a figure eight through a repeated vertex; a circle traversed twice; loops that touch at a vertex or a shared edge without passing through do not cross | Released |
| REQ-G2D-237 | WHEN REQ-G2D-160 finds crossings between two loops A and B, THE loop tree SHALL count them only when one of the two reaches more than t_topo into the other on both sides: its topology flattening has a point inside the other and a point outside it, each farther than t_topo from the other's topology flattening; otherwise the loops touch (Peter, 2026-10-07, DEC-G2D-024). It decides this on the pieces of the flattening between consecutive crossings, each wholly inside or outside the other: a piece reaches farther than t_topo exactly when the closed t_topo neighbourhoods of the other's segments, one interval per segment pair, do not cover it; only segment pairs whose bounding boxes come within t_topo are tested (ours). | the circle of radius 5 mm about (5, 0) tangent inside the circle of radius 10 mm about the origin, starting at the angles k·π/22 (k = 0 … 43) and 0 or π/7 about their centres: their flattenings cross properly in 86 of these 88 placements, and all 88 touch; the square from (0, 0) to (10·cos(π/4), 10·sin(π/4)), its corner on the circle of radius 10 mm about the origin, touches; [0, 100] × [0, 1] and [29.5, 30.5] × [−10, 50] (a T of slots) cross; [95, 105] × [10, 20] through the edge of [0, 100]² crosses; a square poking 0.5·t_topo, 10 + t_topo − 10 in double and 2·t_topo out of another: touch, touch, cross | Released |
| REQ-G2D-238 | WHEN REQ-G2D-160 finds crossings of a loop with itself, THE loop tree SHALL, before the area tests, resolve all of them into cycles that touch but do not cross (at each crossing point, each incoming end joined to the first outgoing end after it in counter-clockwise order with as many incoming as outgoing ends between them; a Seifert resolution), drop a cycle whose every point lies within t_topo of the other cycles (the interval cover of REQ-G2D-237; of two cycles that cover each other, both when their signs of area differ, neither when they agree), nest the kept cycles by REQ-G2D-164 to 172 with `point_in_region` on the cycle polylines and input order taken as the index of each cycle's first edge, and count the crossings only when the kept cycles at depth 0 differ in sign or a kept cycle has the sign of its parent (a winding outside 0 and 1); when no cycle is kept it SHALL drop the loop with `LOOP_DEGENERATE`, and otherwise the loop touches itself, takes the sign of its depth-0 cycles for REQ-G2D-175 and goes on to the area tests (Peter, 2026-10-07, DEC-G2D-024; the resolution, the order and the cover ours). Provisionally (DEC-G2D-033), a stretch the loop runs twice, in either direction, that REQ-G2D-241 does not remove as a slit (its rows are not each other's exact reverses), and two ends leaving a point in one direction count as a crossing, with the stretch's ends as its crossing points. The cycles are polylines of the topology flattening through the rounded crossing points; they only decide, and the rows stay as given. | the bow-tie (0, 0), (10, 0), (0, 10), (10, 10), area 0, crosses (not `LOOP_DEGENERATE`); a figure eight with unequal lobes crosses, also through a repeated vertex; a loop that runs round twice with offset strands, and one of two full-circle rows on the same circle, cross; three CCW petals through one point touch, with one petal CW cross; a pinched annulus and a keyhole whose arc touches its own wall touch; the pinch (0, 0), (4, 0), (5, 2.00005), (6, 0), (10, 0), (10, 4), (6, 4), (5, 1.99995), (4, 4), (0, 4), its lens dropped, touches; the fishtail (10, 0), (10, 10.0001), (10.0001, 10), (0, 10), (0, 0) touches, with legs of 0.0015 mm (a disc 2.2·t_topo wide of winding −1) crosses; a curl of 1e-4 mm on an edge (a stretch run twice) crosses for now, provisionally (DEC-G2D-033); a circle of two full rows on one circle crosses | Released |
| REQ-G2D-241 | WHEN a loop runs a run of rows out and back exactly (each row of the way back the exact reverse of a row of the way out: end points swapped bit for bit, the same centre, the sweep negated) with rows left on both sides (a zero-width slit), THE loop tree SHALL, before cleanup, remove the run's rows, split the loop into the two loops on either side, each of the input loop's index, and report `LOOP_SLIT` (warning) at that loop with the slit's two ends in x, y order; it repeats this until no slit is left, and drops the zero-length lines of a loop it splits. Each side must keep a row that is no other row's reverse; a run without one on a side is a spike, a T-shaped cut or a loop that only runs back over itself, and stays as it is. When the pieces of one input loop wind outside 0 and 1 (a piece's sign, flipped once per piece of its own loop around it, differs between pieces), the loop crosses by REQ-G2D-238, with the slit's ends as its crossing points, and the operation stops (Peter, 2026-10-08) (Peter, 2026-10-08, DEC-G2D-039: a warning on the operation, never a stop). | a keyhole with a square and with a round hole: the outer loop at depth 0 and the hole at depth 1, one warning naming both ends; every start row and both directions give the same loops; a slit of two rows each way; a slit to a shape beside the loop gives two loops at depth 0; a slit inside a slit gives depths 0, 1, 2 and two warnings; a loop that only runs back over itself, a spike of several rows and a T-shaped cut give no warning; a repeated vertex in a slit gives one; two slits in one loop; a slit of arcs; a hole drawn the same way round as its outer loop and a shape beside it drawn the other way cross; a way back of other rows still crosses; `build_region` on the keyhole | Released |
| REQ-G2D-161 | IF loops cross by REQ-G2D-237 or 238, THEN THE loop tree SHALL report `LOOPS_CROSS` (error) and return in `crossing_points` every crossing REQ-G2D-160 found for those loops, the shallow ones included (ours). | test 7 (two crossing squares) | Released |
| REQ-G2D-162 | IF loops cross, THEN THE loop tree SHALL return no loops, only the crossings, and `build_region` no region (ours: a loop inside a dropped crossing loop would otherwise lose its parent and flip between material and air). | two crossing squares beside a valid loop: no loops, two crossing points; `build_region` returns no region | Released |
| REQ-G2D-163 | WHEN the topology flattenings of two loops do not cross but come within t_topo of each other (segment-to-segment distance), shared vertices and edges included, or cross only as REQ-G2D-237 allows, THE loop tree SHALL treat them as touching and accept both; a loop that touches itself by REQ-G2D-238 is accepted too. | test 7 (an island touching the outer wall); a shared edge, a shared vertex, a gap between eps_len and t_topo; the tangent circles of REQ-G2D-237; the pinch of REQ-G2D-238 | Released |
| REQ-G2D-164 | THE loop tree SHALL make the parent of a loop B the loop that contains B and lies inside every other loop containing B; a loop that no other loop contains has no parent. | test 7 (three nested squares; two side by side) | Released |
| REQ-G2D-165 | THE loop tree SHALL test a loop B for containment only in loops with a larger \|A\|, except under REQ-G2D-166. | tests 7 and 24 | Released |
| REQ-G2D-166 | WHEN the areas of two loops A and B differ by at most t_topo·(L_A + L_B), THE loop tree SHALL test containment both ways. | test 24 (the square and the rectangle [0, 10.001] × [0, 10]: the rectangle is the parent in either input order) | Released |
| REQ-G2D-167 | THE loop tree SHALL decide whether A contains B by `point_in_region` of one probe of B against A alone: B ⊂ A when the winding number is not 0. | test 7 (a triangle inside the square) | Released |
| REQ-G2D-168 | THE loop tree SHALL take as probe the first point farther than t_topo from A's topology flattening among, in this order, the vertices of B's cleaned topology flattening, the midpoints of its segments, and the projections of the vertices of A's cleaned topology flattening onto the nearest segment of B, each group in stored order (ours). | test 7 (the triangle (0, 0), (10, 0), (10, 10): the midpoint of its hypotenuse; the notch of 0.1 mm) and test 24 (the notch bottom); a probe from the projections | Released |
| REQ-G2D-169 | IF no probe of B is farther than t_topo from A, THEN THE loop tree SHALL decide B ⊂ A exactly when the area of B minus A, from a Clipper2 difference of the topology flattenings with the NonZero fill rule, is less than half of B's area on the grid (ours: both areas from the grid). | test 24 through `contained_by_difference` against [0, 10]²: the triangle (0, 0), (10, 0), (5, −1) is not contained, the triangle (0, 0), (10, 0), (5, 1) is | Released |
| REQ-G2D-170 | WHEN loops tested both ways each contain the other, one result from a probe and one from the fallback, THE loop tree SHALL keep the probe's result. | test 24 (the notched square is the child in either input order) | Released |
| REQ-G2D-171 | WHEN loops tested both ways each contain the other by two fallback results, THE loop tree SHALL make B the inner loop when the area of B minus A is less than that of A minus B. | the tie rule through `fallback_inner`, in both input orders | Released |
| REQ-G2D-172 | WHEN both fallback differences of REQ-G2D-171 are equal, THE loop tree SHALL make the loop earlier in input order the inner one. | as above, with equal differences | Released |
| REQ-G2D-173 | WHEN loops tested both ways each contain the other by two probe results, THE loop tree SHALL report them with `LOOPS_CROSS` (error), with no crossing points of their own (ours). | two loops that overlap without a proper crossing, their areas within the band of REQ-G2D-166 | Released |
| REQ-G2D-174 | THE loop tree SHALL give each kept loop a depth equal to its number of ancestors. | test 7 (depths 0, 1, 2; side by side 0 and 0) | Released |
| REQ-G2D-175 | THE loop tree SHALL normalise orientation, every loop at even depth CCW and every loop at odd depth CW, so the inside of every region lies on the left of its loops, whether it is material or air. | the nested squares of test 7 in every combination of input orientations | Released |
| REQ-G2D-239 | THE internal `polyline_distances` SHALL return per query point the distance to the nearest segment of the given closed polylines, measured from both ends of each segment (DEC-G2D-013), where it is at most the limit (REQ-G2D-003), and +inf elsewhere; a limit that is not positive and finite, broken `loop_starts`, a non-finite vertex or a non-finite query point is a `ValueError` (DEC-G2D-029; ours). | property: brute force on random loops, several at once; a distance exactly at the limit; a long diagonal edge across many small cells; the closing edge; both directions | Released |
| REQ-G2D-242 | WHEN the kernel's `nearest_ties` is called with closed polylines, query points, a limit and an eps, THE geometry2d kernel SHALL return, for each query point whose nearest segment lies within the limit (REQ-G2D-003), every segment whose distance, REQ-G2D-239's bit for bit, is at most the nearest distance plus eps (the sum in double, so every exact tie is in), as (point, segment) pairs sorted by point, then segment, a segment numbered by the vertex it starts at, as in `nearest_segments`; a point farther than the limit from every segment gets none, and a segment just beyond the limit is still a candidate when it lies within eps of a nearest one inside it; a limit that is not positive and finite, an eps that is negative or not finite, a limit plus eps that is not finite, broken `loop_starts` or a non-finite vertex is a `ValueError` (Peter, 2026-10-08, DEC-OFF-001: the candidates of offset2d's class tie, REQ-OFF-034; the layout and the refusals ours, DEC-G2D-041). | unit: the square's centre ties four edges, a vertex its two edges at 0, eps inclusive at an exact sum, the limit on the nearest only, rows ordered across several loops, a short output, a zero-length segment, the refusals; property: an O(n·m) brute-force oracle in the test, bit for bit, on random loops with their vertices as queries and on loops mirrored in x = 0 with queries on the mirror line (exact ties by construction); the nearest distance is `polyline_distances`', compared bit for bit | Reviewed (Peter, 2026-10-08, DEC-OFF-001) |

### Machining region ([research 01, Loop tree][tree], rule 7)

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-176 | THE `build_region` function SHALL return as the machining region the Clipper2 PolyTree of the side-correct flattened, normalised loops (`flatten_loops`), built with the Positive fill rule, also where it joins touching loops differently from the loop tree (resolution chain, stage 5; the fill rule Peter, 2026-10-07, DEC-G2D-025: where flattened loops overlap, only winding > 0 is the region's kind). | differential: test 7 (random nested inputs, 10,000 under `HYPOTHESIS_PROFILE=thorough`); the two Clipper2 2.0.1 cases of research 01, rule 7 (an island sharing an edge with its parent, an island touching its hole at a vertex); overlaps: in a pocket an island overlapping the wall and two overlapping islands stay outside the region (winding −1), in a material region an island in a hole overlapping it stays inside (winding 2); the overlaps come from tangent arcs and gaps below 2·t_flat, since deeper ones are `LOOPS_CROSS`; Clipper2 2.0.1 counts a path of positive area (CCW, y up) as winding +1 (SRC-122), which these cases check | Released |
| REQ-G2D-177 | WHERE no two flattened loops overlap (the winding is 0 or 1), THE `build_region` function SHALL return the same point set with the Positive fill rule as with NonZero and EvenOdd (DEC-G2D-025). | differential through `region_with_fill_rule`: the three rules agree on test 7's generator with loops more than 2·t_flat + 6 grid units apart (REQ-G2D-179), at random points farther than t_flat + 3 grid units from every true boundary (ours, DEC-G2D-025: overlaps lie within t_flat of a true boundary, so the margin of REQ-G2D-178 keeps clear of them) | Released |
| REQ-G2D-178 | THE `point_in_region` function SHALL give the same result on the loop tree's loops and on the PolyTree's at every point farther than t_topo from every boundary of the loop tree for loops of lines, and farther than t_flat + 3 grid units for loops with arcs (ours, approved by Peter, 2026-10-07, DEC-G2D-027: the side-correct flattening moves an arc's boundary by up to t_flat, 12·t_topo at tol = 0.05 mm; the 3 grid units hold 2.83 of rounding and the eps_len allowances of REQ-G2D-110 and 119 while eps_len ≤ 0.08 grid units). | differential: test 7, its generator with and without arcs | Released |
| REQ-G2D-179 | WHERE all loops are more than 2·t_flat + 6 grid units apart (ours, approved by Peter, DEC-G2D-027: closer loops can overlap once flattened, and Clipper2 merges them), THE loop tree SHALL give each loop a depth whose parity equals the hole flag of its PolyTree loop. | differential: test 7, distances measured on the true curves | Released |
| REQ-G2D-180 | WHEN `build_region` takes its region from the PolyTree, THE geometry2d kernel SHALL give each output edge the source ID of the flattened input edge nearest to its midpoint, the lower row index on a tie (D-059 for the IDs; its tie by edge class does not arise, since a region has one kind; ours). | a square with one arc edge: every output edge of the arc's flattened part carries the arc's ID | Released |
| REQ-G2D-235 | WHEN every loop given to `build_region` is dropped or the PolyTree is empty, THE function SHALL return an empty region (k = 0) with `REGION_EMPTY` (warning) (ours; AGENTS.md, typed diagnostics for expected outcomes). | test 19's two thin loops alone; a loop smaller than the grid | Released |
| REQ-G2D-236 | THE `loop_tree` and `build_region` functions SHALL report their diagnostics in input-loop order, each `location` naming the input indices ("loop 3", "loops 2 and 5"), with `crossing_loops` lower index first (i, i for a self-crossing), a `LOOP_DUPLICATE` placed with the loop it removes and a `LOOPS_CROSS` with its lower loop, and `crossing_points` sorted by loop pair, then x, then y (D-055; ours). | test 7's inputs in two orders; three crossing squares | Released |
| REQ-G2D-181 | WHEN the PolyTree has a pinch point, THE geometry2d kernel SHALL split the loop there by exact integer tests into loops that each keep the traversal of their vertices, and mark the vertices at that point as fixed nodes (D-084; the traversal ours). | an island touching its hole at a vertex comes back split, a CW hole and a CCW island, its vertices there flagged | Released |

## Invariants

- Predicates are pure functions of their input doubles, the same on every platform (REQ-G2D-007 to 011, 018, 021).
- Every `Arc` the validating entries return is valid and keeps its P_0 and P_1, except under the nearly closed rule (REQ-G2D-037 to 049).
- Every flattening starts and ends bit for bit at the curve's end points, stays within t and keeps an arc on the side asked for (REQ-G2D-102 to 126).
- The sign of `signed_area` is right whenever \|A\| > eps_len·L, for loops within its precondition, and flips under reversal (REQ-G2D-001, 002, 128 to 133; DEC-G2D-016).
- `point_in_region` returns one of IN, OUT and ON, and for one loop does not depend on its orientation (REQ-G2D-134 to 150).
- Cleanup moves no vertex by more than eps_len, keeps the area and is idempotent (REQ-G2D-204 to 212).
- No tolerance is a literal; fixed values are declared parameters (REQ-G2D-025, 029, 230).
- Every input loop of `loop_tree` ends in as many places as it has pieces, one more than its `LOOP_SLIT` warnings (REQ-G2D-241), and each piece in exactly one: in the tree, dropped with `LOOP_DEGENERATE` or removed with `LOOP_DUPLICATE`; when any loops cross, the tree holds no loop and the crossings are reported with `LOOPS_CROSS` (REQ-G2D-155 to 173, 237, 238).
- Depths and orientations agree; the tree does not depend on tol, and on input order only through the tie rules (REQ-G2D-154, 159, 164 to 175).
- A side-correct flattened boundary lies in air or on the true boundary (REQ-G2D-115 to 119).
- Farther than t_flat + 3 grid units from every boundary, the loop tree and the PolyTree classify points alike (REQ-G2D-178); after a union, farther than t_topo (REQ-G2D-031).
- Arrays at the kernel boundary satisfy the layout (REQ-G2D-183 to 187, 199 to 201, 203).

## Tolerance budget

The budget is foundation's (REQ-FND-009). Slice 1 spends none of it: `flatten` takes its t from the caller, who passes t_flat for an operation and 0.001 mm for stock sizing (research 01, Flattening). It reads eps_len and eps_ang from `ctx.tolerances`. Slice 2 spends t_flat (`ctx.tolerances.flatten_tol_mm`) on the side-correct flattening of `flatten_loops` and `build_chain` (REQ-G2D-127), and takes t_topo (`topology_tol_mm`) for touching, duplicates, probes and the both-ways band, and u (`grid_unit_mm`) for the topology flattening and the Clipper2 grid (REQ-G2D-026, 029). The PolyTree's rounding, up to 2.83 grid units (REQ-G2D-030), is booked in plan 0005 with research 02; Peter prefers building the PolyTree inside the offset's kernel call, so the rounding is paid once (DEC-G2D-026). The span limit of 2^26 grid units is the declared parameter `grid_max_span_units` in foundation's `tolerance_defaults.toml`, like the largest flattening step (research 01, Parameters; Peter, 2026-10-08, DEC-G2D-034: enough for release 1, larger machines later through a coarser grid unit per job), passed to the kernel as a plain value. The factors 1.5 (REQ-G2D-157) and ½ (REQ-G2D-169) are research 01's rules, not tuning shares: named constants in Python with their source, passed to the kernel as plain values, like the area's limits (DEC-G2D-010; ours). One declared parameter, the largest flattening step π/2 rad (research 01, Parameters), becomes an entry of foundation's `tolerance_defaults.toml` (a foundation SPEC change of plan 0003, step 4), passed to the kernel as a plain value; numeric guards (10^6 vertices, 3355 mm) are named constants with their source (REQ-G2D-230).

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-230 | THE geometry2d module SHALL take its fixed values from declared parameters and pass them to its kernel as plain values, so no kernel source holds them as literals (D-049). | review; tests that the step limit and the span limit come from the defaults file | Released |

## Failure modes and diagnostics

| Situation | Result | Diagnostic |
| --- | --- | --- |
| A line or arc with a NaN or infinite value; an arc with φ = 0 or \|φ\| > 2π; a bulge on a zero chord; curve rows with a broken structure | no curve, no rows | `CURVE_INVALID` (error) |
| An arc or arc row whose P_1 is off its circle or whose sweep does not fit its end points | no curve, no rows | `ARC_INCONSISTENT` (error); rows that are also `CURVE_INVALID` report only that (ours) |
| Arc with r ≤ eps_len; nearly closed arc; bulge with sagitta ≤ eps_len | the line, nothing, or a full circle | none |
| Loop with \|A\| ≤ eps_len·L | no area | `LOOP_DEGENERATE` (warning) |
| Zero-width spike | vertex dropped | `CLEANUP_SPIKE` (info), one per spike |
| `cleanup` keeps fewer than 3 vertices | those indices; the area test reports the loop | none (ours, confirmed by Peter, 2026-10-03) |
| Collinear points, P_2 within eps_len of P_1P_3, or P_1 = P_3, in `circle_through` | `None` | none |
| A NaN or infinite point given to an exact predicate, `circle_through`, `closest_point`, `point_in_region` or `cleanup` | programming error | `ValueError` (ours) |
| t not positive and finite, or so small that the step count exceeds an int; `signed_area` given more than one loop | programming error | `ValueError` (ours) |
| A loop given to `loop_tree` or `build_region` that fails the area test, or whose topology flattening has \|A\| ≤ 1.5·t_topo·L | loop dropped | `LOOP_DEGENERATE` (warning), once per loop |
| Duplicate loops | the first in input order kept, with its source IDs | `LOOP_DUPLICATE` (warning), one per removed loop |
| A zero-width slit in a loop (REQ-G2D-241) | the slit removed, the loop split into the loops on either side, the operation goes on | `LOOP_SLIT` (warning, with the slit's ends; Peter, 2026-10-08) |
| Loops that cross (REQ-G2D-237, 238), or contain each other by two probes | a tree with no loops, only the crossings; no region | `LOOPS_CROSS` (error), one per pair or self-crossing loop (ours) |
| Input of a geometry2d Clipper2 call spanning 2^26 grid units or more | refused, Clipper2 not called; no tree when the fallback is refused, no region | `REGION_TOO_LARGE` (error; ours) |
| Every loop of `build_region` dropped, or the PolyTree empty | an empty region | `REGION_EMPTY` (warning; REQ-G2D-235) |
| Clipper2 reports failure in the fallback difference, the PolyTree or `grid_union` | no containment decision, no tree, no region | `REGION_FAILED` (error; ours, D-132 gives `OFFSET_FAILED` to the offset only); checked by review, Clipper2 gives no way to force it |
| Polygon region arrays that break the layout | rejected before any kernel computation | `REGION_INVALID` (error; ours) |
| `build_chain` rows that break a curve-row rule or are not continuous | no chain | `CURVE_INVALID` or `ARC_INCONSISTENT` (error), as for `curve_rows` |
| An unknown region kind or air side | programming error | `ValueError` (ours) |

## Algorithms and design inputs

| Element of the method | Public source, or own design with date |
| --- | --- |
| orient2d, incircle; two_sum, two_product, expansion sums | Shewchuk 1997 (SRC-032), vendored `predicates.c` (D-097, ADR 0009) |
| Arc predicate, the (q_y − c_y)² comparison | own design, research 01, Vectors and exact signs (2026-10-02), with SRC-032's expansion arithmetic |
| Arc form and validation; bulge | D-057; SRC-123 for the bulge's meaning; formulas own design, research 01, Curves (2026-10-02) |
| Distances; circle through three points | research 01 (the arc rule own design, 2026-10-02); SRC-032, p. 359 |
| Inscribed and circumscribed flattening | Altintas 2012 (SRC-119), eqs. 5.85–5.86, Table 5.2; the circumscribed form, count rule and side rule own design, research 01 (2026-10-02) |
| Signed area, orientation bound; point in region; cleanup; arc bounding boxes | own design, research 01 (2026-10-02); the bound's arc term own design, DEC-G2D-016 (2026-10-03) |
| Side rule for regions and chains | own design, research 01, Flattening (2026-10-02), from the error-side rule of ADR 0005; D-058 |
| Loop tree, rules 1 to 6 | own design, research 01, Loop tree (2026-10-02), from the depth rule of the review of 2026-09-23 and the SRC-032 note |
| Fallback difference and PolyTree (rule 7) | Clipper2 2.0.1 (SRC-122) |
| Grid, re-centring, the 2^26 limit; 2.83 grid units | D-058, D-132; SRC-032 note; SRC-122; SRC-118 |
| Source IDs and pinch splits after a Clipper2 call | D-059, D-084 |

## Test plan

- Unit: research 01's tests 1 to 9, 12, 16 to 22 and 24, and the Shewchuk note's test ideas; new tests where the table says so.
- Property: exact rationals (`fractions`) as the oracle for every predicate, the area sign and cleanup's area; random arcs and bulges; flattening bounds on random arcs; random nested loops of lines and arcs (the generator of test 7) for the loop tree, the winding of normalised loops and the side rule, and for touching against crossing (random circles tangent inside circles at random radii and start angles, and straight edges tangent to arcs, never give `LOOPS_CROSS`; random overlaps deeper than 2·t_topo always do), and for the invariants: every input loop ends in exactly one place (per input loop as many pieces as its `LOOP_SLIT` warnings plus one, each kept, degenerate or duplicate, or no loops with `LOOPS_CROSS`), the same tree under a permutation of loops that leaves the tie rules out, depths and orientations that agree.
- Differential: the loop tree against Clipper2's PolyTree (test 7) and point in region before and after a Clipper2 union (test 21), both through geometry2d's kernel (D-060); shapely or point sampling as independent oracles, test only (D-060).
- Cross-platform: the build guard (note test 7) and tests 1, 2, 5, 6, 7 and 24 (test 23) and test 12 on the three systems in CI.

## Size estimate

Slice 1: about 800 NLOC of Python and 900 of C++ (`predicates.c` not counted), 1561 NLOC measured on 2026-10-03, and 2500 lines of tests. Slice 2: about 1300 NLOC (Clipper2 not counted) and 2550 lines of tests in eight steps of plan 0004. Slice 2 measured 3529 NLOC for the module on 2026-10-08 (about 1970 for slice 2, against its estimate of 1300). Budget in `architecture/modules.yaml`: 3600 NLOC (Peter, 2026-10-08, DEC-G2D-038; 3000 by DEC-G2D-022, 1700 for slice 1, DEC-G2D-017).

## Open questions

Choices marked "(ours)" stand until Peter changes them in review. None open for slice 2: Peter answered the four questions of the cut on 2026-10-07 (DEC-G2D-024 to 027). Questions inside the module are decided as "(ours)" with their reasoning; only safety and scope go to Peter (his instruction, 2026-10-07).

## Later parts

No requirements; each line names the work and where its drafted requirements and open questions are (the draft of 2026-10-02, commit d1a0949, REQ IDs as drafted).

- Offsets and Booleans of topic 02, with the D-132 kernel changes: not in geometry2d but in a module of their own, `offset2d`, which depends on geometry2d (Peter, 2026-10-08, DEC-G2D-038); plan 0005, once research 02 is in the repository (DEC-G2D-022). The medial axis gets a module of its own too, later. It also books the PolyTree's rounding of up to 2.83 grid units against D-132's bias, preferably by building the PolyTree inside the offset's kernel call (DEC-G2D-026). Also the two rules of research 01, Flattening, that bind the operation (the extra clearance added to its offset).
- Same decisions for any thread count (REQ-G2D-019): release 1 kernels are single-threaded (DEC-G2D-001, 022).
- Cleanup of curve loops: tiny arcs and zero-length lines removed with their neighbours joined, open chains (REQ-G2D-046; the cleanup questions of the draft).
- Ellipse arcs and NURBS: types, import rules, eps_par, arc recognition, their flattening, closest points and bounding boxes, spline edges in area and point in region; in regions and chains, every curved edge flattened within t/2 and the extra clearance t/2, and their topology flattening in the loop tree (REQ-G2D-028, 054 to 090, 114, 120 to 123, the t/2 halves of 124 and 125, 129, 146, 147, 198, 215).
- Generic curve operations: evaluate, derivatives, split, reverse, subcurve, invert, `to_nurbs` (REQ-G2D-036, 074 to 079).
- orient3d and 3D vectors (REQ-G2D-004, 012).
- Curve transforms: applying a `Frame` to curves and the sweep rule, `Frame` in foundation (REQ-G2D-182; research 01 test 10).
- Smallest enclosing circle (REQ-G2D-216 to 224).
- Kernel sharing with toolpath: arc fitting's access to the predicates and `circle_through`, and the Clipper2 call rules, under kernels-private.
- Cancellation and threads: long kernels release the interpreter lock and poll the cancellation flag; thread count.
- A performance budget for point in region and the loop tree; the topic 25 module and its input contract.

## Change log

- 2026-10-02: drafted from research 01 (plan 0001, step 4), with review fixes.
- 2026-10-03: Peter confirmed that `cleanup`'s collinear and spike passes stop at three vertices (answer 3; DEC-G2D-014).
- 2026-10-03: plan 0003, step 5: the predicates' input range stated as a precondition (SRC-032, p. 308).
- 2026-10-02: cut to slice 1 on Peter's answers (plan 0003, step 1): in_arc_circle +1 inside, arc rows give `ARC_INCONSISTENT`, predicates without a `Context`, D-055 tiers 2 and 3 (REQ-G2D-231, 232), single-threaded kernels; the draft's proposals taken for the other slice 1 questions and marked "(ours)"; everything else moved to Later parts. Merged into a neighbour: 095 into 094, 107 and 108 into 106, 111 into 110, 136 to 138 into 135, 140 to 142 into 139, 144 into 143, 195 into 194, 202 into 201, 208 into 207, 210 into 209. Stated in the Public interface instead: 225 to 227. Not needed: 228 (`flatten` expects validated curves). Slice 2: 229.
- 2026-10-03: the module budget of 1700 NLOC set in `architecture/modules.yaml` (Peter's answer 6).
- 2026-10-03: Peter's answers on point in region (plan 0003, step 8): REQ-G2D-143's ON on an arc by the sweep instead of the chord side; REQ-G2D-135's radial connector for P1 off the circle; REQ-G2D-148 measures to the nearer of the radii |P_0 − C| and |P_1 − C|. Research 01, Point in region, still states the earlier rule.
- 2026-10-03: research 01, Point in region, updated to Peter's answers of step 8 (DEC-G2D-012: ON in the sweep, the radial connector, the nearer radius) on his answer 2 of 2026-10-03; the requirements are unchanged.
- 2026-10-03: Peter's answer 1 of 2026-10-03: the arc term of the area's error bound derived (DEC-G2D-016); the segment terms are summed exactly on both paths (REQ-G2D-131, 132); the precondition r·min(1, φ²) ≤ 10^7 mm and E ≤ 10^9 mm stated in the Public interface. Research 01, Area and orientation, updated in the same pull request.
- 2026-10-03: Peter's answer 5 of 2026-10-03 on the spec gaps of the reviews: `make_arc` checks P_1 against a tiny circle before turning it into a line (REQ-G2D-047, DEC-G2D-018); arcs up to r = 10^9 mm as a precondition (DEC-G2D-019; Peter named 10^10 mm, which measurement refuted); t ≥ eps_len for `flatten` as a precondition (DEC-G2D-020); the arctangent's own requirement REQ-G2D-233 (DEC-G2D-021). The translation limit E ≤ 10^9 mm of `signed_area` is DEC-G2D-016.
- 2026-10-07: slice 2 cut on Peter's answers to plan 0004 (DEC-G2D-022; plan 0004, step 1): released REQ-G2D-026, 029 to 034, 115 to 119, 124 and 125 (lines and arcs, extra clearance 0), 127, 151 to 181, 183 to 187, 199 and 200; new REQ-G2D-234 (`build_chain`'s rows), 235 (`REGION_EMPTY`) and 236 (order of diagnostics and crossings) after the test audit. Lines and arcs only: 152 and 153 lose their ellipse and spline halves. REQ-G2D-018 and 231 extended to the loop tree. Interface: `loop_tree`, `flatten_loops`, `build_region`, `build_chain`, `polygon_region` and their types; loops as `CurveRows`; new codes `REGION_TOO_LARGE`, `REGION_FAILED`, `REGION_INVALID` (ours). Stay in Later parts: 019, 120 to 123, the t/2 halves of 124 and 125, 182 (with curve transforms), 198. Open questions 1 to 4 for Peter. Budget 3000 NLOC. Spec-reviewer round, all findings taken: REQ-G2D-178 and 179 compare beyond the side-correct flattening (t_flat + 3 grid units, 2·t_flat + 6 grid units; research 01 says t_topo); 176 and 177 held for open question 2; crossings found exactly also at shared vertices and stretches (160); no loops and no region when loops cross (162); probes and later tests from the cleaned topology flattening (155, 168); the topology flattening from basic-operation sine and cosine, so REQ-G2D-018 holds for arcs (152); REQ-G2D-030 measured from the output; pinch-split parts keep their traversal (181); Clipper2 built with REQ-G2D-014's flags; the 2^26 limit a declared parameter; `REGION_EMPTY`; rule order, areas and the reversal order stated.
- 2026-10-07: Peter's answers to the four questions of the slice 2 cut: crossings count only when a loop reaches more than t_topo into the other on both sides (new REQ-G2D-237 for pairs, 238 for a loop with itself; 161 and 163 follow); the PolyTree uses the Positive fill rule (176, 177 released); the PolyTree's rounding goes to plan 0005; REQ-G2D-030, 119, 178 and 179 approved. Research 01, rules 4 and 7 and tests 7 and 21, updated in the same pull request. DEC-G2D-024 to 027.
- 2026-10-08: plan 0005, step 3, on Peter's answer DEC-OFF-001: `Frame`, `frame_of`, `to_grid`, `split_pinches`, `canonical` and `shared_points` declared in `kernel/grid.hpp` (behaviour unchanged), with Clipper2's header; `nearest_ties` in `kernel/distance.hpp` and its kernel binding, new REQ-G2D-242 (DEC-G2D-041).

[r01]: ../../../docs/research/01-foundations.md
[signs]: ../../../docs/research/01-foundations.md#vectors-and-exact-signs
[tol]: ../../../docs/research/01-foundations.md#tolerances
[curves]: ../../../docs/research/01-foundations.md#curves
[dist]: ../../../docs/research/01-foundations.md#distances-and-closest-points
[circle]: ../../../docs/research/01-foundations.md#circle-through-three-points
[flat]: ../../../docs/research/01-foundations.md#flattening-with-a-known-error-side
[area]: ../../../docs/research/01-foundations.md#area-and-orientation
[pir]: ../../../docs/research/01-foundations.md#point-in-region
[arrays]: ../../../docs/research/01-foundations.md#kernel-arrays
[tree]: ../../../docs/research/01-foundations.md#loop-tree
[helpers]: ../../../docs/research/01-foundations.md#helpers
[tests]: ../../../docs/research/01-foundations.md#tests
[shewchuk]: ../../../docs/research/01-foundations.md#shewchuk-1997-adaptive-precision-floating-point-arithmetic-and-fast-robust-geometric-predicates

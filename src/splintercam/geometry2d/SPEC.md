# SPEC: geometry2d

<!-- The planar geometry of every later module. Drafted on 2026-10-02 from research 01 (plan 0001, step 4): curves, exact signs, flattening, area, point in region, loop tree, kernel arrays and helpers. The topic 02 part (offsets and Booleans, REQ-OFF) comes later. -->

| | |
| --- | --- |
| Status | Draft (plan 0001, step 4; waiting for Peter's review: no requirement is released) |
| Layer | 1 (see architecture/modules.yaml) |
| Depends on | foundation |
| Research | [01](../../../docs/research/01-foundations.md): the main text is normative, the literature notes are evidence. The topic 02 part, offsets and Booleans, comes later |
| Decisions | D-025 (open chains for profiles), D-026 (cylinder stock: the enclosing circle), D-028 (units), D-029 (default tolerances), D-034 (splines and ellipses stay native), D-049 (no values buried in code), D-055 (determinism), D-056 and D-146 (tolerance budget, t_flat), D-057 (curve type, arc form, bulge), D-058 and D-132 (grid of 10⁴ per mm, chords in air), D-059 (source IDs), D-060 (no external Python Clipper2 binding; independent test oracles), D-078 (setups and their placement), D-084 (pinch points, fixed nodes), D-091 (3+2 frames), D-092 (analytic ellipses), D-093 (NURBS circles become arcs), D-097 (exact predicates, strict float flags, snapping first); text in [docs/spike/decisions-snapshot.md](../../../docs/spike/decisions-snapshot.md) |
| Owner | Peter Burgener |

## Purpose

The planar geometry every later module builds on. This part, from research 01, gives one curve type with a validated arc form, exact sign tests, flattening with the error on a known side, signed area and orientation, point in region, the loop tree that turns closed chains into regions, the array layout at the C++ kernel boundary, and helpers: cleanup, bounding boxes, closest points and the smallest enclosing circle. Its users are io (curves from DXF and STEP), the chaining of selections (topic 25; no module in architecture/modules.yaml implements it yet), this module's own offsets (topic 02), arc fitting in toolpath (topic 11), stock (cylinder stock) and the strategies (machining regions).

## Scope

- In: vector algebra; the exact predicates and the snapping before them; the curve type (lines, arcs, ellipse arcs, NURBS) with its validation and degenerate rules; DXF bulge conversion; flattening within a tolerance on a known side; signed area and orientation; point in region; the loop tree and the machining region; the arrays at the kernel boundary; polyline cleanup, bounding boxes, closest points, circle through three points, the smallest enclosing circle.
- Out, handled elsewhere:
  - Offsets and Booleans: the topic 02 part of this module (REQ-OFF). Two rules of research 01, Flattening, bind the operation rather than geometry2d: the operation adds the extra clearance t/2 to the one kernel offset it makes from a region (test 25, second half), and an operation that needs the error side but makes no offset of its own makes one offset with clearance t/2. They go with the topic 02 part or with the strategies (Open questions).
  - `ToleranceSet` and the budget (foundation, REQ-FND-008 and 009); the `Frame` type (foundation by research 01, see [Where frames and transforms belong](#where-frames-and-transforms-belong)).
  - Reading DXF and STEP, and the deviation check after arc recognition at import (io, topic 21).
  - Chaining selections into loops, its gap tolerance, resolving crossings before the loop tree, projecting tilted arcs (topic 25; no module in architecture/modules.yaml implements it yet, Open questions).
  - Arc fitting and point reduction (toolpath, topic 11).
- Non-goals: an epsilon in any sign test; exact constructions (centres, flattened points and intersections are rounded constructions, D-055 tiers 2 and 3); a linear algebra library (research 01, Libraries); a convex hull (not needed in release 1).

## Public interface

Lengths in mm and angles in radians, float64 everywhere (D-028). Points are (2,) or (n, 2) float64 arrays; a single point may also be a `Point`. "kernel:" marks functions whose loops run in C++: arrays and plain values in; arrays, plain values and diagnostic codes out (docs/dev/03). Only these names come from research 01, Interfaces: `orient2d`, `incircle`, `orient3d`, `in_arc_circle`, `Curve` with `Line`, `Arc`, `EllipseArc` and `Nurbs`, `flatten`, `build_region`, `signed_area`, `point_in_region`, `loop_tree`, `cleanup`, `circle_through`, `bounding_box`, `closest_point` and `enclosing_circle`. Every other name, and every file name under `kernel/`, is proposed here (Open questions).

```python
Point = tuple[float, float]

class PointLocation(IntEnum): OUT = 0; IN = 1; ON = 2
class RegionKind(Enum): MATERIAL; AIR
class AirSide(Enum): LEFT; RIGHT        # where air lies, seen along the curve
class KnotSide(Enum): LEFT; RIGHT       # side of a derivative at a knot

@dataclass(frozen=True, slots=True)
class Line:
    p0: Point
    p1: Point

@dataclass(frozen=True, slots=True)
class Arc:                               # D-057
    p0: Point                            # exact; defines the radius
    p1: Point                            # exact; never moved
    centre: Point
    sweep_rad: float                     # 0 < |sweep| <= 2π, positive CCW
    @property
    def radius_mm(self) -> float: ...    # |p0 − centre|

@dataclass(frozen=True, slots=True)
class EllipseArc:                        # D-092
    centre: Point
    major_axis: Point                    # unit vector U
    a_mm: float
    b_mm: float
    start_rad: float                     # eccentric angle t_0
    sweep_rad: float

@dataclass(frozen=True, slots=True)
class Nurbs:
    degree: int
    knots: NDArray[np.float64]           # (m + 1,), clamped
    points_w: NDArray[np.float64]        # (n + 1, 3) homogeneous (w·x, w·y, w), largest w = 1

Curve = Line | Arc | EllipseArc | Nurbs
Loop = tuple[Curve, ...]                 # one closed chain; its array form is open

@dataclass(frozen=True, slots=True)
class CurveRows:                         # lines and arcs of closed loops
    rows: NDArray[np.float64]            # (m, 7): x0, y0, x1, y1, cx, cy, sweep
    ids: NDArray[np.int64]               # (m,)
    row_starts: NDArray[np.int64]        # (k,)

@dataclass(frozen=True, slots=True)
class PolygonRegion:
    points: NDArray[np.float64]          # (n, 2)
    loop_starts: NDArray[np.int64]       # (k,)
    source_ids: NDArray[np.int64]        # (n,), the edge that starts at the vertex (D-059)
    fixed: NDArray[np.uint8]             # (n,), fixed-node flag (D-084)

@dataclass(frozen=True, slots=True)
class FlatRegion:
    region: PolygonRegion
    extra_clearance_mm: float            # 0.0, or t_flat/2 with an ellipse or spline edge

@dataclass(frozen=True, slots=True)
class FlatChain:                         # D-025
    points: NDArray[np.float64]          # (n, 2), open
    source_ids: NDArray[np.int64]        # (n − 1,), the edge of each segment (D-059)
    extra_clearance_mm: float            # 0.0, or t_flat/2 with an ellipse or spline edge

@dataclass(frozen=True, slots=True)
class LoopTree:
    loops: tuple[Loop, ...]              # cleaned and normalised: even depth CCW, odd depth CW
    parent: NDArray[np.int64]            # (k,), −1 for none
    depth: NDArray[np.int64]             # (k,)
    input_index: NDArray[np.int64]       # (k,)

@dataclass(frozen=True, slots=True)
class ClosestPoint:
    point: Point
    parameter: float
    distance_mm: float

Box(x_min_mm, y_min_mm, x_max_mm, y_max_mm); Circle(centre, radius_mm)   # frozen dataclasses

# Exact predicates. kernel: kernel/predicates.c (vendored, D-097), kernel/exact.cpp
def orient2d(a: NDArray, b: NDArray, c: NDArray, ctx: Context) -> NDArray[np.int8]: ...       # (n, 2) each; −1, 0, +1
def incircle(a: NDArray, b: NDArray, c: NDArray, d: NDArray, ctx: Context) -> NDArray[np.int8]: ...
def orient3d(a: NDArray, b: NDArray, c: NDArray, d: NDArray, ctx: Context) -> NDArray[np.int8]: ...  # (n, 3) each
def in_arc_circle(q: NDArray, centre: NDArray, p0: NDArray, ctx: Context) -> NDArray[np.int8]: ...
def are_parallel(a: NDArray, b: NDArray, ctx: Context) -> NDArray[np.bool_]: ...  # NumPy

# Curves. kernel: kernel/nurbs.cpp for the NURBS work, kernel/distance.cpp for lines and arcs
def make_arc(p0: Point, p1: Point, centre: Point, sweep_rad: float,
             ctx: Context) -> Result[tuple[Curve, ...]]: ...   # (Arc,), (full circle,), (Line,), or () when removed (REQ-G2D-048)
def curve_rows(rows: NDArray, ids: NDArray, row_starts: NDArray, ctx: Context) -> Result[CurveRows]: ...
def arc_from_bulge(p0: Point, p1: Point, bulge: float, ctx: Context) -> Result[Curve]: ...
def bulges_from_arc(arc: Arc, ctx: Context) -> tuple[tuple[Arc, float], ...]: ...    # two for a full circle
def make_nurbs(degree: int, knots: NDArray, points: NDArray, weights: NDArray, ctx: Context,
               trim: tuple[float, float] | None = None) -> Result[tuple[Nurbs, ...]]: ...  # kernel
def nurbs_eps_par(curve: Nurbs, ctx: Context) -> float: ...                         # knot units
def evaluate(curve: Curve, u: NDArray, ctx: Context) -> NDArray: ...                 # kernel for Nurbs
def derivatives(curve: Curve, u: NDArray, order: int, side: KnotSide, ctx: Context) -> NDArray: ...
def split(curve: Curve, u: float, ctx: Context) -> tuple[Curve, Curve]: ...
def reverse(curve: Curve, ctx: Context) -> Curve: ...
def subcurve(curve: Curve, u0: float, u1: float, ctx: Context) -> Curve: ...
def to_nurbs(curve: Curve, ctx: Context) -> Nurbs: ...
def nurbs_to_arcs(curve: Nurbs, tol_mm: float, ctx: Context) -> tuple[Curve, ...]: ...   # kernel
def invert(curve: Curve, q: Point, tol_mm: float, ctx: Context) -> float | None: ...
def closest_point(curve: Curve, q: Point, ctx: Context) -> ClosestPoint: ...         # kernel
def bounding_box(curve: Curve, ctx: Context) -> Box: ...                            # NumPy

# Flattening and regions. kernel: kernel/flatten.cpp, kernel/area.cpp, kernel/point_in_region.cpp,
# kernel/loop_tree.cpp, kernel/region.cpp (Clipper2), kernel/cleanup.cpp
def flatten(curve: Curve, t_mm: float, side: AirSide | None, ctx: Context) -> Result[NDArray]: ...
def build_region(loops: Sequence[Loop], kind: RegionKind, ctx: Context) -> Result[FlatRegion]: ...  # the PolyTree (Clipper2)
def build_chain(chain: Sequence[Curve], air_side: AirSide, ctx: Context) -> Result[FlatChain]: ...  # D-025
def signed_area(loop: Loop, ctx: Context) -> Result[float]: ...                    # mm²
def point_in_region(q: NDArray, loops: Sequence[Loop], ctx: Context) -> NDArray[np.int8]: ...  # PointLocation per point
def loop_tree(loops: Sequence[Loop], ctx: Context) -> Result[LoopTree]: ...
def cleanup(loop: Loop, ctx: Context) -> Result[Loop]: ...

# Helpers. kernel: kernel/circle.cpp, kernel/enclosing_circle.cpp
def circle_through(p1: Point, p2: Point, p3: Point, ctx: Context) -> Circle | None: ...
def enclosing_circle(points: NDArray, ctx: Context) -> Circle | None: ...
def enclosing_circle_of_curves(curves: Sequence[Curve], ctx: Context) -> Result[Circle]: ...  # passes on the flattening's diagnostics

# Internal entry points used by tests (not in __all__)
def dot(a: NDArray, b: NDArray) -> NDArray: ...                  # NumPy; (n, 2) or (n, 3) rows
def cross(a: NDArray, b: NDArray) -> NDArray: ...                # NumPy; (n, 3) → (n, 3); (n, 2) → (n,), the z component
def two_sum(a: NDArray, b: NDArray) -> tuple[NDArray, NDArray]: ...      # kernel: exact.cpp; error-free pair (x, y)
def two_product(a: NDArray, b: NDArray) -> tuple[NDArray, NDArray]: ...  # kernel: exact.cpp
def orient2d_value(a: NDArray, b: NDArray, c: NDArray) -> NDArray[np.float64]: ...  # kernel: the value predicates.c's orient2d returns; its sign is exact, its magnitude approximate
def point_in_region_exact(q: NDArray, loops: Sequence[Loop], ctx: Context) -> NDArray[np.int8]: ...  # kernel: point_in_region.cpp; the exact layer alone (REQ-G2D-135 to 146, 151)
def flatten_loops(tree: LoopTree, kind: RegionKind, ctx: Context) -> Result[FlatRegion]: ...  # kernel: flatten.cpp; the side-correct flattening that build_region hands to the PolyTree
def contained_by_difference(b: Loop, a: Loop, ctx: Context) -> tuple[bool, float]: ...  # kernel: region.cpp (Clipper2); the rule 5 fallback: B ⊂ A, and the area of B minus A in mm²
def fallback_inner(a: Loop, b: Loop, ctx: Context) -> int: ...  # the tie of two fallback results: 0 when a is the inner loop, 1 when b; a precedes b in input order
```

`circle_through` takes D, the value of the orient2d determinant, from `orient2d_value` (REQ-G2D-097, 099); its exact-zero test uses `orient2d` (REQ-G2D-098).

## Requirements

Each table is one section of research 01, in its order. "Verified by" names the kind of test and its source: "research 01, test N" is research 01's list of tests; "Shewchuk note, test N" and "Piegl and Tiller ch. N note, test N" are the test ideas of its literature notes; "new test" is a test research 01 does not give. Where the main text adopts an algorithm of a literature note (the NURBS rules), the requirement follows the note. The requirements that need Clipper2 and the place of each part under the split rule are listed in [Kernel split and Clipper2](#kernel-split-and-clipper2).

### Units and conventions

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-001 | THE geometry2d module SHALL treat counter-clockwise as the positive sense of its right-handed plane with y up, so a loop traversed CCW has positive signed area. | unit: research 01, test 3 (the CCW loops give 100π and 100 + 12.5π) | Draft |
| REQ-G2D-002 | WHEN a loop is reversed, THE `signed_area` function SHALL return its area with the opposite sign and the same magnitude. | unit: research 01, test 3 (the reversed loop gives the negative; exactly or within the rounding bound: Open questions) | Draft |
| REQ-G2D-003 | WHERE a requirement says that a distance or an angle lies within d, THE geometry2d module SHALL test value ≤ d, as `nearly_equal` does (REQ-FND-003). | unit: new test (values exactly equal to eps_len and t_topo count as within: cleanup merges, point in region gives ON, loops touch) | Draft |

### Vectors and exact signs

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-004 | THE geometry2d module SHALL compute the dot product a·b and the right-handed cross product a × b of research 01 directly, without a linear algebra library; in the plane, a × b is its z component a_x b_y − a_y b_x. | unit: new test through `dot` and `cross` (x × y = z, y × x = −z; a batch of rows gives the rows of single calls) | Draft |
| REQ-G2D-005 | THE geometry2d module SHALL take every topological decision on input geometry that depends on a sign (which side of a line, collinear or not, inside or outside a region or circle, crossing or not) from an exact predicate (REQ-G2D-007 to 012, 022, 023), never from the sign of a floating-point expression; loop orientation (REQ-G2D-131) is the one exception. The safeguards of numerical iterations and the branches of distance constructions (REQ-G2D-082, 091, 093 to 095) are not such decisions. | review (spec-reviewer, D-097); unit: research 01, test 5 (one rounding unit at 15, through `point_in_region_exact`) and test 12 (a vertex one rounding unit off the line is kept) | Draft |
| REQ-G2D-006 | THE geometry2d kernel SHALL compute orient2d, incircle and orient3d with Shewchuk's adaptive predicates, vendored as `predicates.c` (D-097, Q-080, SRC-032). | review of the vendored file and its public-domain header (research 01, Libraries) | Draft |
| REQ-G2D-007 | THE orient2d predicate SHALL return the exact sign of (a_x − c_x)(b_y − c_y) − (a_y − c_y)(b_x − c_x) for the given doubles: +1 when c lies left of the directed line a → b, −1 when right, 0 when collinear. | property: research 01, test 1 (Shewchuk note, test 1: the 65,536 grid signs equal sign(j − i); exact rationals are the oracle, never the plain formula) | Draft |
| REQ-G2D-008 | WHEN three points share their x or their y coordinate, THE orient2d predicate SHALL return exactly 0. | unit: research 01, test 1 (Shewchuk note, test 2) | Draft |
| REQ-G2D-009 | WHEN two arguments are swapped, THE orient2d predicate SHALL return the negated sign. | property: research 01, test 1 (Shewchuk note, test 3: random triples) | Draft |
| REQ-G2D-010 | WHEN the arguments are shifted cyclically, THE orient2d predicate SHALL return the same sign. | property: research 01, test 1 (Shewchuk note, test 3: random triples) | Draft |
| REQ-G2D-011 | THE incircle predicate SHALL return the exact sign of the determinant with rows (p_x − d_x, p_y − d_y, (p_x − d_x)² + (p_y − d_y)²) for p = a, b, c: +1 when d lies inside the circle through a, b, c given CCW, −1 outside, 0 when the four points are cocircular, and the opposite signs when a, b, c are given CW. | unit: research 01, test 1 (Shewchuk note, test 4) | Draft |
| REQ-G2D-012 | THE orient3d predicate SHALL return the exact sign of the determinant with rows a − d, b − d, c − d: +1 when d lies below the plane through a, b, c seen CCW from above, −1 above, 0 when the four points are coplanar. | unit and property: new test against exact rationals (research 01 names no orient3d test) | Draft |
| REQ-G2D-013 | THE geometry2d kernel SHALL call the initialisation routine of `predicates.c` once, when the kernel module loads, before any predicate can run (Shewchuk note, Consequences, Licence: general knowledge, to verify on the vendored copy). | unit: new test (Shewchuk note, test 1 as the first call in a fresh interpreter); review | Draft |
| REQ-G2D-014 | THE build SHALL compile `predicates.c` and every kernel source that does exact arithmetic without floating-point contraction, fast-math or reassociation on every supported compiler: `-ffp-contract=off` and no `-ffast-math` on GCC and Clang, and the equivalent setting on MSVC (D-097). | unit: Shewchuk note, test 7, in every build configuration; review of `CMakeLists.txt` | Draft |
| REQ-G2D-015 | THE geometry2d kernel SHALL do its exact arithmetic in IEEE 754 binary64 with round-to-nearest-even and without extended-precision intermediates (SRC-032 note, limits 3 and 4). | unit: Shewchuk note, test 7 | Draft |
| REQ-G2D-016 | THE geometry2d kernel SHALL provide `two_sum` and `two_product` as error-free transformations: each returns a pair (x, y) with x + y equal to a + b, or to a·b, exactly. | property: Shewchuk note, test 7 (10^6 random pairs, uniform and with widely spread exponents, against exact rationals; two_product(1 + 2^−30, 1 + 2^−30) = (1 + 2^−29, 2^−60)) | Draft |
| REQ-G2D-017 | THE continuous integration SHALL run the build guard, Shewchuk note test 7 on the `two_sum` and `two_product` of REQ-G2D-016, in every configuration in which it builds the kernel, so a contracting or reordering compiler setting fails the build (D-097). | review of the CI workflows | Draft |
| REQ-G2D-018 | THE geometry2d module SHALL make the same decisions for the same input doubles on macOS, Windows and Linux: predicate signs, IN, OUT or ON, and the loop tree's parents, depths and diagnostic codes and severities (D-055, tier 1). | cross-platform: research 01, test 23 (the results of tests 1, 2, 5, 6, 7 and 24 identical; Shewchuk note, test 8) | Draft |
| REQ-G2D-019 | THE geometry2d module SHALL make the same decisions for the same input with any thread count (D-055, tier 1). | unit: new test (research 01 tests 7 and 24 with one thread and with several; how a kernel learns its thread count: Open questions) | Draft |
| REQ-G2D-020 | WHEN a float stage (flattening, cleanup, loop tree, point in region) takes a sign decision on the points of curves or loops, THE geometry2d module SHALL first merge points within eps_len (REQ-G2D-204) and then evaluate the exact predicates on the merged points (D-097). | unit: research 01, test 12 (the merge); new test (a vertex within eps_len of its predecessor, placed so the unmerged pair would cross, gives no `LOOPS_CROSS`) | Draft |
| REQ-G2D-021 | THE exact predicates SHALL take no tolerance and compare only with zero, so a point one rounding unit off a line, circle or plane gets a nonzero sign (SRC-032 note, limit 7). | unit: Shewchuk note, test 1 (offsets of 2^−53); research 01, test 2 (2^−50 off the circle) | Draft |
| REQ-G2D-022 | THE arc predicate `in_arc_circle(q, c, p0)` SHALL return the exact sign of (q_x − p0_x)(q_x + p0_x − 2c_x) + (q_y − p0_y)(q_y + p0_y − 2c_y) = \|q − c\|² − \|p0 − c\|²: −1 inside the circle, 0 on it, +1 outside. | unit: research 01, test 2 (C = (0, 0), P_0 = (5, 0): (3, 4) gives 0, (3, 4 − 2^−50) inside, (3, 4 + 2^−50) outside; exact rationals are the oracle) | Draft |
| REQ-G2D-023 | THE geometry2d kernel SHALL decide the sign of (q_y − c_y)² − \|p0 − c\|² exactly with the same expansion arithmetic, so point in region can compare q_y with an arc's heights c_y ± r, which are not doubles, without computing them. | unit: research 01, test 6 ((0, 5) ON, (0, −3) IN, through `point_in_region_exact`); property: new test against exact rationals, with radii for which c_y + r is not a double | Draft |
| REQ-G2D-024 | THE geometry2d kernel SHALL provide each predicate as one call over arrays of points ((n, 2) or (n, 3) float64 in, (n,) int8 out), so no Python loop calls a predicate per point. | review (split rule; SRC-032 note, limit 10); unit: new test (a batch gives the signs of single rows) | Draft |

### Tolerances

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-025 | THE geometry2d module SHALL read eps_len, eps_ang, t_flat and t_topo from `ctx.tolerances` (`length_eps_mm`, `angle_eps_rad`, `flatten_tol_mm`, `topology_tol_mm`) on every call and hold no tolerance as a literal (D-049, REQ-FND-005). | unit: new test (a `ToleranceSet` with a larger `length_eps_mm` makes cleanup merge vertices that the default set keeps apart); review, and `tools/arch-check` once it exists | Draft |
| REQ-G2D-026 | WHERE a float stage decides whether features touch or duplicate each other, THE geometry2d module SHALL use t_topo (REQ-G2D-158, 163); crossings are decided exactly (REQ-G2D-160). | unit: research 01, tests 7 and 24 | Draft |
| REQ-G2D-027 | THE geometry2d module SHALL report two nonzero directions a and b as parallel exactly when \|a × b\|² ≤ sin²(eps_ang)·\|a\|²·\|b\|². | unit: research 01, test 22 (directions 1e-10 rad apart are parallel, 1e-8 rad apart are not) | Draft |
| REQ-G2D-028 | THE geometry2d module SHALL compute for each NURBS curve eps_par = eps_len / v_max on the knots as read, before any snapping, with v_max the bound of research 01, Tolerances: the largest derivative control point, and for a rational curve (M1_A + R·M1_w) / w_min about the centre of the control points' bounding box. | unit: research 01, test 11 (quarter circle of radius 10 mm, weights 1, √2/2, 1: v_max = 30.35 mm per knot unit, eps_par ≈ 3.3e-8); Piegl and Tiller ch. 2 note, tests 5 and 6 (the derivative control points behind the polynomial v_max) | Draft |
| REQ-G2D-029 | THE geometry2d module SHALL take the grid unit u from its `Context`, never from a literal or from module-level state, for the topology flattening, the ON band of replaced edges and the Clipper2 scale of 10⁴ per mm (REQ-FND-005). | review; unit: new test (the bound of the topology flattening follows the u of the `Context`), once foundation provides u there (Open questions) | Draft |
| REQ-G2D-030 | WHEN float loops go through a geometry2d Clipper2 call at 10⁴ per mm, THE geometry2d kernel SHALL return a result that moves no input point by more than 2.83 grid units (SRC-118). | differential: research 01, test 21 (the union through geometry2d's kernel, D-060) | Draft |
| REQ-G2D-031 | WHEN float loops have gone through a Clipper2 union, THE `point_in_region` function SHALL give the same result on the float input and on the integer result at every point farther than t_topo from every boundary, also where features lie between eps_len and t_topo apart. | differential: research 01, test 21 | Draft |
| REQ-G2D-032 | WHEN `build_region` has built the PolyTree, THE geometry2d module SHALL take the region's topology from the integer result only and not re-decide it with a float-stage test (the rule 5 fallback's verdict is combined with probe results by REQ-G2D-170 to 172). | review; unit: new test (features between eps_len and t_topo apart that merge on the grid stay merged in the returned region) | Draft |
| REQ-G2D-033 | THE geometry2d kernel SHALL re-centre the input of each of its Clipper2 calls on the input's bounding box and round it to the grid u before the call (D-058, D-132; research 01, Tolerances, resolution chain stage 3, which states it for the offset kernel). | unit: new test (a region and a forced rule 5 fallback pair, translated by several metres within the limit of REQ-G2D-034, give the same tree, region and fallback answer); research 01 gives no test for re-centring | Draft |
| REQ-G2D-034 | IF the input of a geometry2d Clipper2 call spans 2^26 grid units (about 6711 mm) or more in x or y, THEN THE geometry2d kernel SHALL refuse the call with an error diagnostic and not call Clipper2 (SRC-122; draft REQ-OFF-018). | unit: new test (`build_region` on loops farther apart than the limit, and `contained_by_difference` on such a pair, are refused) | Draft |

### Curves

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-035 | THE geometry2d module SHALL provide one tagged curve type `Curve` with four variants: `Line`, `Arc`, `EllipseArc` and `Nurbs` (D-057, D-092). | unit: new test (each variant is a `Curve`; a match over the four is exhaustive under pyright strict) | Draft |
| REQ-G2D-036 | THE geometry2d module SHALL provide `evaluate`, `derivatives` (with a side at knots), `split`, `reverse`, `subcurve`, `bounding_box`, `closest_point`, `invert`, `flatten` and `to_nurbs` for every `Curve` variant. | unit: new test (each operation accepts each variant); the behaviour for the parameters of `Line` and `Arc`, for the derivatives of lines, arcs and ellipse arcs, and for some `EllipseArc` operations is open (Open questions) | Draft |
| REQ-G2D-037 | THE `Arc` SHALL store its start point P_0, end point P_1 and centre C exactly as given, and a signed sweep φ in radians, positive CCW (D-057). | unit: new test (the stored values equal the inputs bit for bit) | Draft |
| REQ-G2D-038 | THE geometry2d module SHALL take an arc's radius as r = \|P_0 − C\| in every computation (validation, the arc predicate, flattening, distances, area), never from P_1. | unit: research 01, test 2; new test (an arc whose P_1 lies less than eps_len off the circle: in_arc_circle(P_1, C, P_0) is not 0, and the flattening uses \|P_0 − C\|) | Draft |
| REQ-G2D-039 | THE geometry2d module SHALL never move an arc's P_1, except by the nearly closed rule (REQ-G2D-049). | property: new test (validation, split, reverse and cleanup keep P_1 bit for bit, after reversal as the new P_0) | Draft |
| REQ-G2D-040 | IF a `Line`, `Arc` or `EllipseArc` is given a NaN or infinite value, THEN THE geometry2d module SHALL reject it with `CURVE_INVALID` (error). | unit: new test (NaN, +inf and −inf in each field of each variant); research 01, test 20 for curve rows | Draft |
| REQ-G2D-041 | IF an `Arc` is given φ = 0 or \|φ\| > 2π, THEN THE geometry2d module SHALL reject it with `CURVE_INVALID` (error). | unit: new test (φ = 0, φ = −0.0, and the double above 2π) | Draft |
| REQ-G2D-042 | IF \|\|P_1 − C\| − r\| > eps_len, THEN THE geometry2d module SHALL reject the arc with `ARC_INCONSISTENT` (error). | unit: new test (P_1 moved radially by less and by more than eps_len); research 01 gives none | Draft |
| REQ-G2D-043 | IF the angle from P_0 to P_1 about C, taken in the sense of φ, differs from \|φ\| modulo 2π by more than eps_len / r, THEN THE geometry2d module SHALL reject the arc with `ARC_INCONSISTENT` (error). | unit: new test (P_1 at the angle \|φ\| and beyond eps_len / r from it; a CCW quarter arc given a negative sweep; a full circle accepted) | Draft |
| REQ-G2D-044 | WHEN geometry2d builds an arc from its end points (bulge conversion, arc recognition), THE module SHALL place C on the perpendicular bisector of P_0P_1, so the arc passes REQ-G2D-042 and 043. | property: new test (arcs from random bulges and recognised arcs never give `ARC_INCONSISTENT`), limited to radii for which the rounding of the bisector construction, of \|P_1 − C\| and of the angle stays below the tolerances of REQ-G2D-042 and 043; research 01 gives no such limit (Open questions) | Draft |
| REQ-G2D-045 | THE geometry2d module SHALL accept an arc with P_1 = P_0 and φ = ±2π as a full circle. | unit: research 01, test 6 (C = (0, 0), r = 5, P_0 = P_1 = (5, 0), φ = 2π) and test 20 (a one-row full circle) | Draft |
| REQ-G2D-046 | WHEN cleanup meets an arc of length \|φ\|·r ≤ eps_len, THE geometry2d module SHALL remove it and join its neighbours at its P_0. | unit: new test (research 01 gives none) | Draft |
| REQ-G2D-047 | WHEN an arc has r ≤ eps_len and P_0 ≠ P_1, THE geometry2d module SHALL replace it by the line P_0P_1. | unit: new test (research 01 gives none) | Draft |
| REQ-G2D-048 | WHEN an arc has r ≤ eps_len and P_0 = P_1, THE geometry2d module SHALL remove it. | unit: new test (research 01 gives none) | Draft |
| REQ-G2D-049 | WHEN an arc has \|P_1 − P_0\| ≤ eps_len, \|φ\| > π and (2π − \|φ\|)·r ≤ eps_len, THE geometry2d module SHALL build it as a full circle, with P_1 = P_0 and φ = ±2π in the sense of the given φ. | unit: new test (research 01 gives none) | Draft |
| REQ-G2D-050 | WHEN a DXF bulge b ≠ 0 on the chord from P_0 to P_1 of length c > 0 (c = 0: Open questions) is converted, THE geometry2d module SHALL return the arc with these P_0 and P_1, φ = 4·arctan b and C = M + d·n_left, d = c(1 − b²)/(4b), with M the chord midpoint and n_left the unit normal left of P_0 → P_1 (SRC-123; formulas ours). | unit: research 01, test 8 (from (0, 0) to (2, 0): b = 1, −1 and tan(π/8)) | Draft |
| REQ-G2D-051 | WHEN the bulge is 0, THE geometry2d module SHALL return the line P_0P_1. | unit: new test (b = 0 and b = −0.0) | Draft |
| REQ-G2D-052 | WHEN an arc that is not a full circle is exported to DXF, THE geometry2d module SHALL return the bulge b = tan(φ/4) on its chord. | unit: new test (the arcs of research 01 test 8 give back b = 1, −1 and tan(π/8)) | Draft |
| REQ-G2D-053 | WHEN a full circle is exported to DXF, THE geometry2d module SHALL return it as two arcs with finite bulges, the second starting bit for bit where the first ends. | unit: new test (the circle of research 01 test 6) | Draft |
| REQ-G2D-054 | WHERE a curve is an `EllipseArc` or a `Nurbs`, THE geometry2d module SHALL keep it native: `flatten` returns a new polyline and leaves the curve unchanged (D-034). | review; unit: new test (flattening leaves the curve unchanged) | Draft |
| REQ-G2D-055 | THE `EllipseArc` SHALL store its centre C, unit major axis U, semi-axes a and b in mm, start eccentric angle t_0 and signed sweep in radians (D-092). | unit: new test; review against D-092 | Draft |
| REQ-G2D-056 | THE `EllipseArc` SHALL evaluate its point at the eccentric angle t as C + a·cos t·U + b·sin t·V, with V = U turned by +π/2 (SRC-024, Eq. 7.18). | unit: new test (points of the rotated arc of the Piegl and Tiller ch. 4 and 7 note, test 8, satisfy the ellipse equation in its frame) | Draft |
| REQ-G2D-057 | THE `Nurbs` SHALL hold degree p ≥ 1, a clamped non-decreasing knot vector of m + 1 = n + p + 2 values with end multiplicity p + 1 and interior multiplicity at most p, and n + 1 homogeneous control points with all weights > 0. | property: new test (every `Nurbs` from import, split, subcurve, reverse and conversion satisfies it) | Draft |
| REQ-G2D-058 | IF NURBS data given for import contain a non-finite value, a knot count other than n + p + 2, a decreasing knot or a weight ≤ 0, THEN THE geometry2d module SHALL reject the curve with `NURBS_INVALID` (error). | unit: Piegl and Tiller ch. 12 note, test 9 (weights 0 and −0.5); new test (the other cases) | Draft |
| REQ-G2D-059 | WHEN a NURBS curve is imported, THE geometry2d module SHALL scale its homogeneous control points so that the largest weight is 1, which leaves the curve unchanged. | unit: Piegl and Tiller ch. 12 note, test 5 (weights scaled by 7: same points, same chord count); new test (the largest stored weight is 1) | Draft |
| REQ-G2D-060 | IF the ratio of the largest to the smallest weight of an imported NURBS curve exceeds 1e6, THEN THE geometry2d module SHALL keep the curve and report `NURBS_WEIGHT_RATIO` (warning). | unit: new test (research 01 gives none; the limit is from the ch. 4 and 7 note, caution 5) | Draft |
| REQ-G2D-061 | WHEN knots of an imported NURBS curve lie within eps_par of each other, THE geometry2d module SHALL snap them to one value only if no sample point (2p + 2 per span) moves by more than eps_len, and keep them otherwise. | unit: Piegl and Tiller ch. 2 note, test 9; new test (a pair whose snap would move a sample by more than eps_len is kept) | Draft |
| REQ-G2D-062 | WHEN an imported NURBS curve has an interior knot of multiplicity above p, THE geometry2d module SHALL split it there into separate curves. | unit: Piegl and Tiller ch. 12 note, test 9 | Draft |
| REQ-G2D-063 | WHEN an imported NURBS knot vector is not clamped, judged from the knots and never from a "periodic" flag, THE geometry2d module SHALL clamp it, leaving the curve unchanged on its range. | unit: Piegl and Tiller ch. 12 note, test 7, and ch. 5 note, test 9 | Draft |
| REQ-G2D-064 | WHEN import is given trimming parameters, THE geometry2d module SHALL extract the trimmed subcurve once, so the stored curve carries no trimming parameters. | unit: Piegl and Tiller ch. 12 note, test 8 | Draft |
| REQ-G2D-065 | THE `nurbs_to_arcs` function SHALL accept a piece of a NURBS curve as an arc within its tolerance by the control-point test of the ch. 4 and 7 note ("Recognising a circular arc") (D-093). | unit: Piegl and Tiller ch. 4 and 7 note, test 11 (a rotated and translated arc is found, with centre and radius within 1e-9 mm) | Draft |
| REQ-G2D-066 | THE `nurbs_to_arcs` function SHALL return the pieces it does not accept as arcs as `Nurbs` (D-093). | unit: Piegl and Tiller ch. 4 and 7 note, test 11 (the ellipse of its test 7 comes back as a `Nurbs`) | Draft |
| REQ-G2D-067 | WHEN an operation flattens a NURBS edge, THE geometry2d module SHALL first replace every piece that is an arc within t_flat/4 by an `Arc` whose P_0 and P_1 are the piece's end points bit for bit (D-093). | unit: new test (a NURBS quarter circle becomes one `Arc`; an S-shaped cubic stays a `Nurbs`) | Draft |
| REQ-G2D-068 | WHEN a NURBS piece has been replaced by an arc for an operation, THE geometry2d module SHALL flatten that arc within t_flat/4. | unit: new test (the step count of REQ-G2D-106 at t_flat/4) | Draft |
| REQ-G2D-069 | WHERE an edge was recognised as an arc for the operation, THE geometry2d module SHALL count it as a spline edge for the side rule (REQ-G2D-122 to 125). | unit: new test (`flatten_loops` on a region whose only curved edge is a recognised NURBS arc returns the extra clearance t_flat/2) | Draft |
| REQ-G2D-070 | THE `Nurbs` SHALL evaluate C(u) for an array of parameters, including u at the right end of the knot range. | unit: Piegl and Tiller ch. 2 note, tests 1, 2, 3 (partition of unity) and 7, and ch. 4 and 7 note, tests 1 to 4 | Draft |
| REQ-G2D-071 | THE `Nurbs` SHALL return its derivatives up to an order k as the rational derivatives of SRC-024, Eq. 4.8, from the derivatives of its homogeneous form. | unit: Piegl and Tiller ch. 2 note, tests 4 and 7, and ch. 4 and 7 note, tests 1 and 2 | Draft |
| REQ-G2D-072 | WHEN derivatives are asked for at a knot, THE geometry2d module SHALL take them from the side asked for: right from the span [u_i, u_{i+1}), left from (u_i, u_{i+1}]. | unit: Piegl and Tiller ch. 6 note, test 10 (at u = 0.5: left (4, 0), right (0, 4)) | Draft |
| REQ-G2D-073 | WHERE a `Nurbs` has an interior knot of multiplicity p, THE geometry2d module SHALL keep the curve point at that knot as a vertex in every flattening. | unit: Piegl and Tiller ch. 12 note, test 6 | Draft |
| REQ-G2D-074 | WHEN a curve is split, THE geometry2d module SHALL return two curves that reproduce it on their ranges, keep its end points and share the split point bit for bit. | unit: Piegl and Tiller ch. 5 note, tests 1 to 5, and ch. 4 and 7 note, test 9 (the split at the shoulder of a 120° arc); new test (lines and arcs) | Draft |
| REQ-G2D-075 | WHEN a `Line` or an `Arc` is reversed, THE `reverse` function SHALL return it with P_0 and P_1 swapped, an arc with the same centre and φ negated. | unit: new test (a line or arc reversed twice comes back bit for bit) | Draft |
| REQ-G2D-076 | WHEN a `Nurbs` is reversed, THE `reverse` function SHALL return the knots s_i = a + b − u_{m−i} and the homogeneous control points, weights included, in reverse order. | unit: Piegl and Tiller ch. 5 note, test 8 | Draft |
| REQ-G2D-077 | WHEN the subcurve between two parameters is asked for, THE geometry2d module SHALL return the part of the curve between them, made by splitting twice. | unit: Piegl and Tiller ch. 12 note, test 8 | Draft |
| REQ-G2D-078 | WHEN a curve is converted to NURBS, THE geometry2d module SHALL return an exact NURBS of the same point set: a line as degree 1, an arc by the circle construction (SRC-024, A7.1), an ellipse arc by the affine map of the unit-circle arc with the weights kept. | unit: Piegl and Tiller ch. 4 and 7 note, tests 5 and 8 | Draft |
| REQ-G2D-079 | WHEN a point is inverted on a curve with a tolerance, THE geometry2d module SHALL return the closest-point parameter if the distance is within the tolerance, and no parameter otherwise. | unit: Piegl and Tiller ch. 6 note, test 9 | Draft |
| REQ-G2D-080 | THE `closest_point` function SHALL return for a `Nurbs` the nearest of these candidates: both curve ends, every local minimum u_k of the distances at 2p + 2 samples per span (ends included), and the result of each Newton iteration of REQ-G2D-081. | unit: Piegl and Tiller ch. 6 note, tests 1, 2, 3 and 6; property: its test 7 (never farther than the minimum over 20,001 dense samples) | Draft |
| REQ-G2D-081 | WHEN f(lo) < 0 < f(hi) at a local minimum u_k, with f(u) = C′(u)·(C(u) − Q), lo = u_{k−1} (u_k at the start) and hi = u_{k+1} (u_k at the end), THE `closest_point` function SHALL run the safeguarded Newton iteration on f for a `Nurbs` from u_k in the bracket [lo, hi], narrowing it at each step to [u, hi] when f(u) < 0 and to [lo, u] otherwise (ch. 6 note, Algorithms). | unit: Piegl and Tiller ch. 6 note, tests 1, 2 and 6 (bracketed minima inside a span); new test (a local minimum without a sign change of f adds only its sample) | Draft |
| REQ-G2D-082 | WHEN a Newton step of the NURBS closest point would leave its bracket (REQ-G2D-081), or f′(u) ≤ 0, THE `closest_point` function SHALL take the bracket's midpoint instead. | unit: new test (a bracketed minimum where the Newton step leaves [lo, hi], and one where f′(u) ≤ 0, for example C′ = 0 at coincident control points, ch. 6 note, caution 7: the iteration takes the midpoint and still converges); research 01 gives none | Draft |
| REQ-G2D-083 | THE `closest_point` function SHALL run at most 60 Newton iterations per candidate on a `Nurbs`. | unit: new test (iteration counts on the curves of the ch. 6 note's tests) | Draft |
| REQ-G2D-084 | THE `closest_point` function SHALL stop the Newton iteration on a `Nurbs` when \|C(u) − Q\| ≤ eps_len, else when \|f(u)\| ≤ eps_ang·\|C′(u)\|·\|C(u) − Q\|, tested in this order, or when a step moves the curve point by at most eps_len (\|Δu\|·\|C′(u)\| ≤ eps_len). | unit: Piegl and Tiller ch. 6 note, tests 1, 2 and 6; review against its cautions 6 and 8 | Draft |
| REQ-G2D-085 | WHEN every point of a `Nurbs` lies at the same distance from Q, THE `closest_point` function SHALL return a valid parameter at that distance without dividing by zero. | unit: Piegl and Tiller ch. 6 note, test 5 (the centre of the quarter circle: distance 1) | Draft |
| REQ-G2D-086 | WHERE a `Nurbs` is closed, THE `closest_point` function SHALL treat its samples as cyclic and let the bracket wrap across the seam. | unit: Piegl and Tiller ch. 6 note, test 8 | Draft |
| REQ-G2D-087 | THE `closest_point` function SHALL find the closest point on an `EllipseArc` by the safeguarded Newton iteration on the eccentric angle, started at t = atan2(a·y, b·x) in the ellipse frame and compared with both ends. | property: new test against dense samples, for arcs whose sweep contains the start value (research 01 gives none for ellipses; the other case: Open questions) | Draft |
| REQ-G2D-088 | WHEN a `Nurbs` is flattened within t, THE `flatten` function SHALL divide each non-empty span of length h into N = max(1, ⌈h·√(K/(8t))⌉) equal parameter steps, with K = (M_A + R·M_w)/w_min, where the span's homogeneous control points are first translated so that O, the centre of the bounding box of their Euclidean points, is the origin; M_A and M_w are the largest second-derivative control points of the translated A and w; R = max\|P_i − O\| and w_min = min w_i over the span's p + 1 points (K = M_A for a polynomial curve; ch. 12 note, Algorithms). | unit: Piegl and Tiller ch. 12 note, tests 1, 2 and 5; property: its test 3 | Draft |
| REQ-G2D-089 | WHEN an `EllipseArc` is flattened within t, THE `flatten` function SHALL use N = ⌈\|Δt\|·√(a/(8t))⌉ equal steps in the eccentric angle, with Δt the sweep and a the major semi-axis. | unit: Piegl and Tiller ch. 12 note, test 4 (a = 50 mm, b = 30 mm, t = 0.01 mm: 158 chords, true error 0.0099 mm) | Draft |
| REQ-G2D-090 | IF the adaptive flattening of a `Nurbs` would halve a segment more than 50 times, THEN THE geometry2d module SHALL stop and report `NURBS_INVALID` (error). | unit: new test (research 01 gives none) | Draft |

### Distances and closest points

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-091 | WHERE the curve is a line with \|P_1 − P_0\| > 0, THE `closest_point` function SHALL return the parameter t = clamp((Q − P_0)·(P_1 − P_0) / \|P_1 − P_0\|², 0, 1), the point P_0 + t(P_1 − P_0) and its distance from Q. | unit: new test (feet inside the segment, before P_0 and beyond P_1); research 01, test 17 has only the zero-length case | Draft |
| REQ-G2D-092 | WHEN a line has zero length, THE `closest_point` function SHALL treat it as the point P_0 and return P_0 and \|Q − P_0\|. | unit: research 01, test 17 | Draft |
| REQ-G2D-093 | WHEN Q ≠ C and the angle α of Q − C, measured from P_0 − C in the sense of φ and taken in [0, 2π), satisfies α ≤ \|φ\|, THE `closest_point` function SHALL return for an arc the point C + r·(Q − C)/\|Q − C\| and the distance \|\|Q − C\| − r\|. | unit: research 01, test 17 (inside the sweep) | Draft |
| REQ-G2D-094 | WHEN α > \|φ\|, THE `closest_point` function SHALL return for an arc the nearer of its end points P_0 and P_1 and the distance to it. | unit: research 01, test 17 (outside the sweep) | Draft |
| REQ-G2D-095 | WHEN α > \|φ\| and Q is equally near P_0 and P_1, THE `closest_point` function SHALL return P_0. | unit: research 01, test 17 | Draft |
| REQ-G2D-096 | WHEN Q = C, THE `closest_point` function SHALL return for an arc the point P_0 and the distance r, without dividing by \|Q − C\|. | unit: research 01, test 17 | Draft |

### Circle through three points

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-097 | WHEN `circle_through(P_1, P_2, P_3)` finds a circle, THE function SHALL return the centre C_x = P_3x − (u_y\|v\|² − v_y\|u\|²) / (2D), C_y = P_3y + (u_x\|v\|² − v_x\|u\|²) / (2D), with u = P_1 − P_3, v = P_2 − P_3 and D = `orient2d_value`(P_1, P_2, P_3), the value of the orient2d determinant, whose sign is exact (SRC-032, p. 359). | unit: research 01, test 9 (Shewchuk note, test 5: (0, 0), (4, 0), (0, 2) give (2, 1) exactly; (10, 0), (−10, 0) and the point at −1e-4 rad give the circle of radius 10) | Draft |
| REQ-G2D-098 | IF the exact predicate orient2d(P_1, P_2, P_3) (REQ-G2D-007) is 0, THEN THE `circle_through` function SHALL return no circle. | unit: research 01, test 9 (Shewchuk note, test 5: (0, 0), (1, 1), (2, 2)) | Draft |
| REQ-G2D-099 | IF \|`orient2d_value`(P_1, P_3, P_2)\| / \|P_3 − P_1\| ≤ eps_len, THEN THE `circle_through` function SHALL return no circle, decided before any division by D. | unit: research 01, test 9 ((0, 0), (1, 1 + 2^−52), (2, 2): no circle by this rule, not by a division by zero) | Draft |
| REQ-G2D-100 | IF P_1 = P_3, THEN THE `circle_through` function SHALL return no circle without dividing by \|P_3 − P_1\|. | unit: new test (research 01 gives none) | Draft |
| REQ-G2D-101 | THE `circle_through` function SHALL apply no radius or chord limit of its own; callers apply theirs (topic 11). | unit: research 01, test 9 (a chord P_1P_3 of only 0.001 mm gives the circle) | Draft |

### Flattening with a known error side

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-102 | WHEN an arc of radius r is flattened inscribed within t, THE `flatten` function SHALL use the step Δθ_in = 4·asin(√(min(1, t/(2r)))). | unit: research 01, test 4 (r = 10 mm, t = 0.001 mm, full circle: n = 223) | Draft |
| REQ-G2D-103 | WHEN an arc is flattened inscribed in n steps, THE `flatten` function SHALL return n chords whose n + 1 vertices lie at the angles θ_0 + k·Δθ in the sense of φ, k = 0 … n, the inner ones on the arc's circle within 4 rounding units of r. | unit: research 01, test 4 (223 chords) | Draft |
| REQ-G2D-104 | WHEN an arc of radius r is flattened circumscribed within t, THE `flatten` function SHALL use the step Δθ_out = 2·atan(√(t(2r + t)) / r). | unit: research 01, test 4 (n = 223) | Draft |
| REQ-G2D-105 | WHEN an arc is flattened circumscribed in n steps, THE `flatten` function SHALL return the polyline from P_0 through the vertices at radius r / cos(Δθ/2) and the angles θ_0 + (k + ½)·Δθ in the sense of φ, k = 0 … n − 1, to P_1: n + 1 segments, the first and last of them half tangents at P_0 and P_1. | unit: research 01, test 4 (224 segments, two of them half tangents) | Draft |
| REQ-G2D-106 | THE `flatten` function SHALL give an arc n = ⌈\|φ\| / min(Δθ, π/2)⌉ steps, with Δθ the step of the chosen form. | unit: research 01, test 4 (n = 223 in both forms) | Draft |
| REQ-G2D-107 | IF rounding makes \|φ\| / n exceed min(Δθ, π/2) for that n, THEN THE `flatten` function SHALL raise n by 1. | property: new test (\|φ\| / n ≤ min(Δθ, π/2) in double for random r, t and φ) | Draft |
| REQ-G2D-108 | THE `flatten` function SHALL spread the steps of an arc evenly, Δθ = \|φ\| / n (SRC-119, p. 234 and Table 5.2). | unit: new test on the circle of research 01 test 4 (consecutive vertex angles differ by \|φ\| / n) | Draft |
| REQ-G2D-109 | WHEN t > 2r, THE `flatten` function SHALL keep the inscribed flattening finite and take its step from the π/2 cap, so a full circle gets 4 chords. | unit: new test (no NaN; n = 4 for a full circle) | Draft |
| REQ-G2D-110 | WHEN an arc is flattened inscribed, THE `flatten` function SHALL return a polyline that lies inside the arc's circle and within t of it, both up to 4 rounding units of r (the segment that ends at P_1: Open questions). | unit: research 01, test 4 (10^4 samples per segment) | Draft |
| REQ-G2D-111 | WHEN an arc is flattened circumscribed, THE `flatten` function SHALL return a polyline that lies outside the arc's circle and within t of it, both up to 4 rounding units of r (the segment that ends at P_1: Open questions). | unit: research 01, test 4 (as above) | Draft |
| REQ-G2D-112 | THE `flatten` function SHALL return a curve's start and end points bit for bit as the first and last points of its flattening. | unit: research 01, test 4 (arcs, both forms); new test (lines, ellipse arcs, NURBS) | Draft |
| REQ-G2D-113 | WHEN `flatten` is given an `Arc` and an air side, THE function SHALL flatten it inscribed when the arc's centre lies on the air side (left of the arc for φ > 0, right for φ < 0) and circumscribed when the centre lies on the other side. | unit: new test on the circle of research 01 test 4 (a CCW and a CW arc, each with air LEFT and RIGHT: the four combinations) | Draft |
| REQ-G2D-114 | WHEN `flatten` is given an `EllipseArc` or a `Nurbs` and an air side, THE function SHALL return the two-sided flattening of REQ-G2D-120 and 121, the same as without a side; the side is met at region and chain level (REQ-G2D-122 to 125). | unit: new test (the flattenings with LEFT, RIGHT and no side are equal bit for bit) | Draft |
| REQ-G2D-115 | WHERE the region kind is material, THE `flatten_loops` function (the side-correct flattening of `build_region`) SHALL flatten an arc with φ > 0 circumscribed and an arc with φ < 0 inscribed. | unit: research 01, test 16 | Draft |
| REQ-G2D-116 | WHERE the region kind is air, THE `flatten_loops` function SHALL flatten an arc with φ > 0 inscribed and an arc with φ < 0 circumscribed, on outer boundaries and islands alike. | unit: research 01, test 16 (the same arcs in a pocket flip; an island in a pocket) | Draft |
| REQ-G2D-117 | WHERE an open chain is flattened for a profile (D-025), THE `build_chain` function SHALL take the side the tool works on as the air side of every arc of the chain (REQ-G2D-113). | unit: new test (a chain of a line, a CCW and a CW arc, with the tool on the left and then on the right) | Draft |
| REQ-G2D-118 | THE `build_region` function SHALL hand the loops to its side-correct flattening as the loop tree normalised them, not as they were given. | review (`build_region` calls `flatten_loops` on the tree of `loop_tree`); unit: new test (the side-correct flattenings of the regions of research 01 test 16, given with every loop reversed, are the same bit for bit) | Draft |
| REQ-G2D-119 | WHEN `flatten_loops` flattens a region of lines and arcs, THE function SHALL return a boundary that lies in air or on the true boundary and within t of it, up to the allowance of REQ-G2D-110 and 111. | unit: research 01, test 16; property: new test (random material and air regions of lines and arcs; test 16 states no allowance: Open questions) | Draft |
| REQ-G2D-120 | WHEN an `EllipseArc` or a `Nurbs` is flattened within t, THE `flatten` function SHALL put every vertex on the curve, at the curve point of its parameter. | unit: new test (each vertex equals `evaluate` at its parameter bit for bit); Piegl and Tiller ch. 12 note, test 6 | Draft |
| REQ-G2D-121 | WHEN an `EllipseArc` or a `Nurbs` is flattened within t, THE `flatten` function SHALL keep the two-sided Hausdorff distance between the curve and its flattening within t (D-034; research 01, Flattening). | unit and property: Piegl and Tiller ch. 12 note, tests 3 and 4 | Draft |
| REQ-G2D-122 | WHERE a region contains an ellipse or spline edge, THE `flatten_loops` function SHALL flatten every curved edge of the region within t/2, arcs on their side. | unit: new test on the inputs of research 01 test 25 (the arc's step count follows REQ-G2D-106 at t/2; the cubic's span counts follow REQ-G2D-088 at t/2) | Draft |
| REQ-G2D-123 | WHERE an open chain contains an ellipse or spline edge, THE `build_chain` function SHALL flatten every curved edge of the chain within t/2, arcs on their side. | unit: new test (the cubic and arc of research 01 test 25 as an open chain) | Draft |
| REQ-G2D-124 | THE `build_region` function SHALL return the extra clearance t/2 for a region that contains an ellipse or spline edge, and 0 for one of lines and arcs only. | unit: research 01, test 25 (t/2); new test on the regions of research 01 test 16 (0) | Draft |
| REQ-G2D-125 | THE `build_chain` function SHALL return the extra clearance t/2 for an open chain that contains an ellipse or spline edge, and 0 for one of lines and arcs only. | unit: new test (the chain of REQ-G2D-123 gives t/2; a chain of a line and an arc gives 0) | Draft |
| REQ-G2D-126 | WHERE a flattening serves no offset (point in region, stock sizing), THE `flatten` function SHALL accept no side and return a polyline within t of the curve on both sides. | unit: new test (no side, on an arc, an ellipse arc and a NURBS) | Draft |
| REQ-G2D-127 | THE `flatten_loops` and `build_chain` functions SHALL take the t of REQ-G2D-113 to 125 as t_flat from `ctx.tolerances.flatten_tol_mm` (research 01, Flattening: "In every case t = t_flat of the budget"). | unit: new test (at tol = 0.01 mm the arcs' step counts follow REQ-G2D-106 at t = 0.000397 mm) | Draft |

### Area and orientation

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-128 | THE `signed_area` function SHALL return A = ½·Σ(x_i y_{i+1} − x_{i+1} y_i) over the end points of all edges, plus ½·r²·(φ − sin φ) for each arc, in mm². | unit: research 01, test 3 (a full circle of r = 10 mm gives 100π within 1e-12 relative; the square [0, 10]² with an outward semicircle about (10, 5) gives 100 + 12.5π ≈ 139.270 mm²) | Draft |
| REQ-G2D-129 | WHERE a loop has ellipse or spline edges, THE `signed_area` function SHALL compute A on the loop's topology flattening (REQ-G2D-152). | unit: new test (a loop of a line and a cubic gives the A of its explicit flattening within u) | Draft |
| REQ-G2D-130 | WHEN `signed_area` evaluates its sums in floating point, THE function SHALL first translate the loop so that the centre of its bounding box is the origin. | property: new test against exact rationals (thin loops with \|A\| a few eps_len·L, their box centre near ±3000 mm: the sign is right only when the sums are taken about the box centre) | Draft |
| REQ-G2D-131 | WHERE a loop has n ≤ 10^6 vertices and a half-extent E ≤ 3355 mm, THE `signed_area` function SHALL decide the orientation from the floating-point sums (their rounding bound: research 01, Area and orientation). | property: new test against exact rationals (whenever the exact \|A\| > eps_len·L, the signs agree) | Draft |
| REQ-G2D-132 | WHERE a loop has more than 10^6 vertices, THE `signed_area` function SHALL sum the polygon part exactly with expansion arithmetic. | unit: new test (a loop just above 10^6 vertices whose exact area lies a few eps_len·L above 0) | Draft |
| REQ-G2D-133 | IF \|A\| ≤ eps_len·L, with L the loop length, THEN THE `signed_area` function SHALL report `LOOP_DEGENERATE` (warning). | unit: research 01, test 19 (a loop 1e-7 mm wide and 10 mm long is rejected; 1e-5 mm and 0.001 mm wide pass the area test) | Draft |

### Point in region

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-134 | THE `point_in_region` function SHALL classify each query point against the given closed loops as exactly one of IN, OUT and ON. | unit: research 01, tests 5 and 6; Shewchuk note, test 6 | Draft |
| REQ-G2D-135 | THE exact layer of `point_in_region` (`point_in_region_exact`) SHALL compute the winding number of q, summed over all loops given, from the edges that the ray from q in the +x direction crosses. | unit: research 01, tests 5 and 6, through `point_in_region_exact` | Draft |
| REQ-G2D-136 | WHERE the sweep of an arc contains the angle π/2 or 3π/2 about its centre, THE `point_in_region_exact` function SHALL split the arc there into pieces monotone in y. | unit: research 01, test 6 | Draft |
| REQ-G2D-137 | THE `point_in_region_exact` function SHALL decide whether π/2 and 3π/2 lie inside a sweep from exact signs only (the sides of P_0 and P_1 relative to the horizontal and vertical lines through C, and the sense of φ), never from atan2, and treat a full circle by the same rule. | unit: research 01, test 6; new test (end points exactly on and one rounding unit beside the lines through C, against exact rationals) | Draft |
| REQ-G2D-138 | WHEN q_y lies in the half-open range [min(y_a, y_b), max(y_a, y_b)) of an edge or arc piece from height y_a to y_b, and the edge passes strictly right of q at q_y, THE `point_in_region_exact` function SHALL add +1 for an edge going up and −1 for one going down; every other edge adds 0. | unit: research 01, test 6 (rays through the seam and the split points); new test (rays through polygon vertices and along horizontal edges) | Draft |
| REQ-G2D-139 | THE `point_in_region_exact` function SHALL decide by orient2d alone whether a straight edge passes right of q. | unit: Shewchuk note, test 6 ((10 − 2^−49, 5) IN, (10 + 2^−49, 5) OUT, through `point_in_region_exact`) | Draft |
| REQ-G2D-140 | WHEN an arc piece lies on the right half of its circle (x ≥ c_x), THE `point_in_region_exact` function SHALL count it as passing right of q exactly when q_x < c_x or the arc predicate puts q inside the circle. | unit: research 01, test 5 ((15 − 2^−49, 5) IN, (15 + 2^−49, 5) OUT, through `point_in_region_exact`) and test 6 | Draft |
| REQ-G2D-141 | WHEN an arc piece lies on the left half of its circle (x ≤ c_x), THE `point_in_region_exact` function SHALL count it as passing right of q exactly when q_x < c_x and the arc predicate puts q outside the circle. | unit: research 01, test 5 (inward semicircle: (10, 5) OUT); new test (the circle of test 6 with q left of it, and inside it left of C) | Draft |
| REQ-G2D-142 | WHEN an arc piece ends at a highest or lowest point (y = c_y ± r), THE `point_in_region_exact` function SHALL compare q_y with that end only through the sign of q_y − c_y and the exact comparison of REQ-G2D-023. | unit: new test (a circle whose radius is not a double, q left of its highest point at the doubles just below and above c_y + r, against exact rationals) | Draft |
| REQ-G2D-143 | WHEN orient2d of a straight edge's ends and q is 0 and q lies within the edge's bounding box, THE `point_in_region_exact` function SHALL classify q as ON. | unit: Shewchuk note, test 6 ((10, 5) and (10, 10) ON) | Draft |
| REQ-G2D-144 | WHEN the arc predicate of q is 0 and q lies on the arc itself (an end point, any point of a full circle, or a point on the arc's side of the chord P_0P_1: right of it for φ > 0, left for φ < 0), THE `point_in_region_exact` function SHALL classify q as ON. | unit: research 01, test 5 ((15, 5) ON) and test 6 ((5, 0) and (0, 5) ON) | Draft |
| REQ-G2D-145 | THE `point_in_region_exact` function SHALL NOT classify q as ON from a zero of a helper test elsewhere: on a chord line, or on the part of an arc's circle outside the arc. | unit: research 01, test 5 ((10, 5) on the chord line is IN; (5, 5), on the circle but not on the arc, is IN) | Draft |
| REQ-G2D-146 | WHERE a loop has ellipse or spline edges, THE `point_in_region_exact` function SHALL replace those edges by their topology flattening and keep the loop's lines and arcs exact. | unit: research 01, test 26 (points farther than 2u from the spline get the result of a flattening within 1e-8 mm) | Draft |
| REQ-G2D-147 | IF q lies within u of a replaced ellipse or spline edge, measured to the true curve, THEN THE `point_in_region` function SHALL classify q as ON. | unit: research 01, test 26 | Draft |
| REQ-G2D-148 | IF q lies within eps_len of the boundary, measured with the distances of REQ-G2D-091 to 096, THEN THE `point_in_region` function SHALL classify q as ON (tolerance layer). | unit: research 01, test 5 ((15, 5) and (15 ± 2^−49, 5) ON; (15 − 2e-6, 5) IN, (15 + 2e-6, 5) OUT); Shewchuk note, test 6 (the last two points ON) | Draft |
| REQ-G2D-149 | WHEN q is not ON, THE `point_in_region` function SHALL classify q as IN where its winding number is not 0 and as OUT where it is 0. | unit: research 01, tests 5 and 6 ((0, 0) IN, (10, 0) OUT, (0, −3) IN) | Draft |
| REQ-G2D-150 | WHERE one loop is given, THE `point_in_region` function SHALL give the same result for both of its orientations. | unit: new test (the reversed loops of research 01 tests 5 and 6 and of Shewchuk note test 6) | Draft |
| REQ-G2D-151 | WHERE the loops are normalised by the loop tree, THE `point_in_region_exact` function SHALL compute a winding number of 1 at every point inside the region that is not ON. | property: new test (normalised trees from the generator of research 01 test 7) | Draft |

### Loop tree

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-152 | THE loop tree SHALL replace every arc, ellipse and spline edge, for topology only, by a flattening within u, two-sided (the topology flattening). | unit: new test (two-sided distance ≤ u between each edge and its topology flattening: arcs by REQ-G2D-102 at t = u, ellipses and splines by REQ-G2D-121) | Draft |
| REQ-G2D-153 | THE loop tree SHALL decide each containment probe with `point_in_region` on the exact lines and arcs and on the topology flattening of ellipse and spline edges. | unit: research 01, tests 7 and 24 | Draft |
| REQ-G2D-154 | THE loop tree SHALL make every decision (cleanup, degeneracy, duplicates, crossings, parents, depths) independent of the operation tolerance tol (`ctx.tolerances.chord_tol_mm`). | unit: new test (the same tree for tol = 0.05 mm and 0.01 mm, the defaults of D-029) | Draft |
| REQ-G2D-155 | THE loop tree SHALL clean each loop (REQ-G2D-204 to 212) before the degeneracy, duplicate, crossing and containment tests (REQ-G2D-156 to 173) and pass its `CLEANUP_SPIKE` diagnostics on. | unit: research 01, test 12 (the spike loop given to `loop_tree`) | Draft |
| REQ-G2D-156 | IF a cleaned loop fails the area test of REQ-G2D-133, THEN THE loop tree SHALL drop it and report `LOOP_DEGENERATE` (warning). | unit: research 01, test 19 (width 1e-7 mm) | Draft |
| REQ-G2D-157 | IF the topology flattening of a loop has \|A\| ≤ 1.5·t_topo·L, THEN THE loop tree SHALL drop the loop and report `LOOP_DEGENERATE` (warning). | unit: research 01, test 19 (width 1e-5 mm dropped, 0.001 mm kept) | Draft |
| REQ-G2D-158 | THE loop tree SHALL treat two loops as duplicates exactly when every vertex of each topology flattening lies within t_topo of the other polyline (point-to-segment distance), both ways. | unit: research 01, test 7 (a duplicate loop), and tests 7 and 24 (a square and its notched copy are not duplicates) | Draft |
| REQ-G2D-159 | WHEN loops are duplicates, THE loop tree SHALL keep the first in input order, with its source IDs, and report `LOOP_DUPLICATE` (warning). | unit: research 01, test 7; new test (the pair in the other order keeps the other loop's IDs) | Draft |
| REQ-G2D-160 | THE loop tree SHALL find crossings of a loop with itself and with other loops by exact segment tests (orient2d) on the topology flattenings. | unit: research 01, test 7 (two crossing squares); new test (a figure eight; a crossing by one rounding unit; segments that meet at an end point do not cross) | Draft |
| REQ-G2D-161 | IF loops cross, THEN THE loop tree SHALL report `LOOPS_CROSS` (error) with their crossing points. | unit: research 01, test 7 (two crossing squares) | Draft |
| REQ-G2D-162 | IF loops cross, THEN THE loop tree SHALL keep those loops out of every region. | unit: new test (`build_region` on two crossing squares beside a valid loop returns the valid loop's region only) | Draft |
| REQ-G2D-163 | WHEN the topology flattenings of two loops do not cross but come within t_topo of each other (segment-to-segment distance), shared vertices and edges included, THE loop tree SHALL treat them as touching and accept both. | unit: research 01, test 7 (an island touching the outer wall); new test (a shared edge, a shared vertex, a gap between eps_len and t_topo) | Draft |
| REQ-G2D-164 | THE loop tree SHALL make the parent of a loop B the loop that contains B and lies inside every other loop containing B; a loop that no other loop contains has no parent. | unit: research 01, test 7 (three nested squares; two side by side) | Draft |
| REQ-G2D-165 | THE loop tree SHALL test a loop B for containment only in loops with a larger \|A\|, except under REQ-G2D-166. | unit: research 01, tests 7 and 24 | Draft |
| REQ-G2D-166 | WHEN the areas of two loops A and B differ by at most t_topo·(L_A + L_B), THE loop tree SHALL test containment both ways. | unit: research 01, test 24 (the square [0, 10]² and the rectangle [0, 10.001] × [0, 10]: the rectangle is the parent in either input order) | Draft |
| REQ-G2D-167 | THE loop tree SHALL decide whether A contains B by `point_in_region` of one probe of B against A alone: B ⊂ A when the winding number is not 0. | unit: research 01, test 7 (a triangle inside the square) | Draft |
| REQ-G2D-168 | THE loop tree SHALL take as probe the first point farther than t_topo from A among, in this order, the vertices of B, the midpoints of B's edges and arcs, and the projections of A's vertices onto B's edges. | unit: research 01, test 7 (the triangle (0, 0), (10, 0), (10, 10): the midpoint of its hypotenuse; the notch of 0.1 mm) and test 24 (the notch bottom); new test (a probe from the projections) | Draft |
| REQ-G2D-169 | IF no probe of B is farther than t_topo from A, THEN THE loop tree SHALL decide B ⊂ A exactly when the area of B minus A, from a Clipper2 difference of the topology flattenings with the NonZero fill rule, is less than \|B\|/2. | unit: research 01, test 24 (the fallback called directly through `contained_by_difference` against [0, 10]²: the triangle (0, 0), (10, 0), (5, −1) is not contained, the triangle (0, 0), (10, 0), (5, 1) is) | Draft |
| REQ-G2D-170 | WHEN loops tested both ways each contain the other, one result from a probe and one from the fallback, THE loop tree SHALL keep the probe's result. | unit: research 01, test 24 (the notched square is the child in either input order) | Draft |
| REQ-G2D-171 | WHEN loops tested both ways each contain the other by two fallback results, THE loop tree SHALL make B the inner loop when the area of B minus A is less than that of A minus B. | unit: new test (the tie rule driven directly through `fallback_inner`, in both input orders) | Draft |
| REQ-G2D-172 | WHEN both fallback differences of REQ-G2D-171 are equal, THE loop tree SHALL make the loop earlier in input order the inner one. | unit: new test (as above, with equal differences) | Draft |
| REQ-G2D-173 | WHEN loops tested both ways each contain the other by two probe results, THE loop tree SHALL report them with `LOOPS_CROSS` (error). | unit: new test (two loops that overlap without a proper crossing, with areas within the band of REQ-G2D-166) | Draft |
| REQ-G2D-174 | THE loop tree SHALL give each kept loop a depth equal to its number of ancestors. | unit: research 01, test 7 (depths 0, 1, 2; side by side 0 and 0) | Draft |
| REQ-G2D-175 | THE loop tree SHALL normalise orientation, every loop at even depth (the outer boundary of a region) CCW and every loop at odd depth (a hole of the region around it) CW, so the inside of every region lies on the left of its loops, whether it is material or air. | unit: new test (the nested squares of research 01 test 7 in every combination of input orientations); research 01, test 7 | Draft |
| REQ-G2D-176 | THE `build_region` function SHALL return as the machining region of an operation the Clipper2 PolyTree of the side-correct flattened, normalised loops (`flatten_loops`), built with the NonZero fill rule, also where it joins touching loops differently from the loop tree (rule 7; resolution chain, stage 5). | differential: research 01, test 7 (1000 random nested inputs); unit: new test (the two Clipper2 2.0.1 cases of research 01, Loop tree, rule 7: an island sharing an edge with its parent, an island touching its hole at a vertex) | Draft |
| REQ-G2D-177 | THE `build_region` function SHALL return the same point set with the NonZero fill rule as with EvenOdd on normalised loops. | differential: new test (both agree at random points farther than t_topo from every boundary) | Draft |
| REQ-G2D-178 | THE `point_in_region` function SHALL give the same result on the loop tree's loops and on the PolyTree's at every point farther than t_topo from every boundary. | differential: research 01, test 7 | Draft |
| REQ-G2D-179 | WHERE all loops are more than t_topo apart, THE loop tree SHALL give each loop a depth whose parity equals the hole flag of its PolyTree loop. | differential: research 01, test 7 | Draft |
| REQ-G2D-180 | WHEN `build_region` takes its region from the PolyTree, THE geometry2d kernel SHALL give each output edge the source ID of the nearest input edge (D-059). | unit: new test (a square with one arc edge: every vertex of the arc's flattened part carries the arc's ID) | Draft |
| REQ-G2D-181 | WHEN the PolyTree has a pinch point, THE geometry2d kernel SHALL split the loop there by exact integer tests and mark the vertices at that point as fixed nodes (D-084). | unit: new test (an island touching its hole at a vertex comes back split, its vertices there flagged) | Draft |

### Frames and transforms

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-182 | THE geometry2d kernel SHALL take no frame or transform and compute in the planar coordinates its caller gives (model coordinates at import, the work frame for operations). | review (no geometry2d entry of `_kernels.pyi` takes a frame or a matrix); research 01 gives no test | Draft |

### Kernel arrays

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-183 | THE geometry2d module SHALL pass a polygon region across the kernel boundary as `points` (n, 2) float64 in mm, `loop_starts` (k,) int64, `source_ids` (n,) int64, the ID of the edge that starts at each vertex (D-059), and `fixed` (n,) uint8, the fixed-node flag (D-084). | unit: new test (shapes and dtypes) | Draft |
| REQ-G2D-184 | THE `loop_starts` array of a polygon region SHALL start at 0 and ascend. | unit: new test (`loop_starts` [1, 4] and [0, 4, 4] are rejected); property: new test (every region a kernel returns) | Draft |
| REQ-G2D-185 | THE polygon region SHALL store each loop without repeating its first vertex at its end; the closing edge is implied. | unit and property: new test (as above) | Draft |
| REQ-G2D-186 | THE polygon region SHALL hold at least 3 vertices in every loop. | unit and property: new test (as above) | Draft |
| REQ-G2D-187 | IF polygon region arrays break REQ-G2D-183 to 186, THEN THE geometry2d module SHALL reject them before any kernel computation. | unit: new test (one case per rule) | Draft |
| REQ-G2D-188 | THE geometry2d module SHALL pass lines and arcs across the kernel boundary as curve rows: (m, 7) float64 [x0, y0, x1, y1, cx, cy, sweep] in mm and radians, an (m,) int64 array with one ID per row, and `row_starts` (k,) int64 for the loops. | unit: research 01, test 20 (the valid loops); new test (shapes and dtypes) | Draft |
| REQ-G2D-189 | WHEN the sweep of a row is 0 or −0.0, THE geometry2d module SHALL treat the row as a line. | unit: research 01, test 20 | Draft |
| REQ-G2D-190 | IF a line row has a cx or cy that is not NaN, THEN THE geometry2d module SHALL reject the rows with `CURVE_INVALID` (error). | unit: research 01, test 20 | Draft |
| REQ-G2D-191 | IF an arc row has a cx or cy that is not finite, or \|sweep\| > 2π, THEN THE geometry2d module SHALL reject the rows with `CURVE_INVALID` (error). | unit: research 01, test 20 | Draft |
| REQ-G2D-192 | IF an arc row breaks the arc rules of REQ-G2D-042 and 043, THEN THE geometry2d module SHALL reject the rows with `CURVE_INVALID` (error). | unit: research 01, test 20 | Draft |
| REQ-G2D-193 | IF any other value of a row is NaN or infinite, THEN THE geometry2d module SHALL reject the rows with `CURVE_INVALID` (error). | unit: research 01, test 20 | Draft |
| REQ-G2D-194 | IF a row does not start bit for bit where the previous row of its loop ends, THEN THE geometry2d module SHALL reject the rows with `CURVE_INVALID` (error). | unit: research 01, test 20 | Draft |
| REQ-G2D-195 | IF the last row of a loop does not end bit for bit where its first row starts, THEN THE geometry2d module SHALL reject the rows with `CURVE_INVALID` (error). | unit: research 01, test 20 | Draft |
| REQ-G2D-196 | THE geometry2d module SHALL accept a loop of one row (a full circle) and a loop of two rows (for example a line and an arc). | unit: research 01, test 20 | Draft |
| REQ-G2D-197 | IF the rows, IDs or `row_starts` have the wrong shape or dtype, or `row_starts` does not start at 0 and ascend, THEN THE geometry2d module SHALL reject them with `CURVE_INVALID` (error). | unit: research 01, test 20 ("each violation"); new test (one case per shape, dtype and `row_starts` rule) | Draft |
| REQ-G2D-198 | THE geometry2d module SHALL pass a NURBS curve across the kernel boundary as its degree (int), its knots (m + 1,) float64 and its homogeneous control points (n + 1, 3) float64 in the column order w·x, w·y, w (research 01's (n + 1, 4) form for 3D curves: Open questions). | unit: Piegl and Tiller ch. 4 and 7 note, test 3 (C(1) = (7/5, 6/5) through the (n + 1, 3) arrays); new test (shapes and dtypes) | Draft |
| REQ-G2D-199 | WHEN a loop of curve rows is flattened, THE geometry2d module SHALL hold each joint between two rows once in the result, as the first point of the second row's flattening. | unit: new test (the loops of research 01 test 20 flatten into closed loops without repeated vertices) | Draft |
| REQ-G2D-200 | WHEN curve rows are flattened, THE geometry2d module SHALL give each vertex the ID of the row whose flattened edge starts at it (D-059). | unit: new test (the line-and-arc loop of research 01 test 20: the line's ID on its first vertex, the arc's on the others) | Draft |
| REQ-G2D-201 | THE geometry2d module SHALL hand every array to its kernel as a C-contiguous copy. | unit: new test (a strided view gives the result of its copy; the caller's array is unchanged and shares no memory with any result) | Draft |
| REQ-G2D-202 | THE geometry2d module SHALL make every array that crosses the kernel boundary read-only, in both directions. | unit: new test (every array in a result has `flags.writeable` false); review of `bindings.cpp` | Draft |
| REQ-G2D-203 | THE geometry2d kernel functions SHALL take and return only NumPy arrays and plain values; no Python object, callback or OCCT type crosses the boundary. | review (`_kernels.pyi`, `bindings.cpp`) | Draft |

### Helpers

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-204 | WHEN cleaning a loop, THE `cleanup` function SHALL walk its vertices in stored order from the first vertex and replace each run of consecutive vertices within eps_len of the run's first vertex by that first vertex, a new run starting at the first vertex farther away. | unit: research 01, test 12 (nine vertices 0.9e-6 mm apart become five runs, kept at 0, 1.8e-6, 3.6e-6, 5.4e-6 and 7.2e-6 mm) | Draft |
| REQ-G2D-205 | WHEN the last run of a loop lies within eps_len of the loop's first vertex, THE `cleanup` function SHALL join it to the first run. | unit: new test (research 01 test 12 does not cover the wrap) | Draft |
| REQ-G2D-206 | THE `cleanup` function SHALL move no vertex by more than eps_len. | property: research 01, test 12; new test (clusters that span the first vertex) | Draft |
| REQ-G2D-207 | THE `cleanup` function SHALL drop a vertex that lies strictly between its two neighbours, on the segment joining them, with orient2d exactly 0. | unit: research 01, test 12 (an exactly collinear vertex is removed) | Draft |
| REQ-G2D-208 | THE `cleanup` function SHALL NOT drop, in its collinear pass, a vertex whose orient2d with its two neighbours is not 0. | unit: research 01, test 12 (a vertex one rounding unit off the line is kept) | Draft |
| REQ-G2D-209 | WHEN a loop turns back exactly onto itself at a vertex (a zero-width spike: orient2d with its two neighbours exactly 0, and the vertex not strictly between them), THE `cleanup` function SHALL drop that vertex by this rule, not by the collinear pass of REQ-G2D-207. | unit: research 01, test 12 (the loop (0, 0), (10, 0), (10, 10), (10, 20), (10, 10), (0, 10) loses its tip (10, 20)) | Draft |
| REQ-G2D-210 | WHEN `cleanup` drops a zero-width spike, THE function SHALL report `CLEANUP_SPIKE` (info). | unit: research 01, test 12 (as above) | Draft |
| REQ-G2D-211 | WHEN `cleanup` drops a zero-width spike, THE function SHALL leave the loop's region and signed area unchanged. | unit: research 01, test 12 (the spike loop keeps its area); property: new test (random loops with spikes, compared in exact rationals) | Draft |
| REQ-G2D-212 | THE `cleanup` function SHALL repeat its passes until none changes the loop, so cleaning a cleaned loop changes nothing. | unit: research 01, test 12 (after the spike is dropped, (10, 10) follows itself and is merged); property: new test (cleaning twice equals cleaning once, bit for bit) | Draft |
| REQ-G2D-213 | THE `bounding_box` function SHALL give a line the box of its two end points. | unit: new test (research 01 gives none) | Draft |
| REQ-G2D-214 | THE `bounding_box` function SHALL give an arc the box of its end points and of the points at the angles 0, π/2, π and 3π/2 about C that lie inside its sweep, all four for a full circle. | unit: research 01, test 18 (sweeps that cross 0, π/2, π and 3π/2, one that crosses none, a full circle; φ > 0 and φ < 0) | Draft |
| REQ-G2D-215 | THE `bounding_box` function SHALL give a NURBS curve the box of its control points (the strong convex hull, SRC-024, P3.5), which contains the curve and can be larger. | property: Piegl and Tiller ch. 2 note, test 8; new test (dense samples of random curves lie in the box) | Draft |
| REQ-G2D-216 | THE `enclosing_circle` function SHALL compute the smallest enclosing circle, for cylinder stock (D-026), by Welzl's algorithm in the iterative form of research 01, Helpers (SRC-124, SRC-125). | property: research 01, test 13; new test (small sets against a brute-force minimum over pairs and triples) | Draft |
| REQ-G2D-217 | THE `enclosing_circle` function SHALL first sort the points by x, then by y. | property: research 01, test 13 (any input order) | Draft |
| REQ-G2D-218 | THE `enclosing_circle` function SHALL then shuffle the points by the Fisher–Yates shuffle of research 01, Helpers, driven by the raw 64-bit outputs x of NumPy's PCG64 bit generator seeded from `ctx.seed` (for i from n − 1 down to 1, swap item i with item ⌊x·(i + 1) / 2^64⌋, a 128-bit product), without reading or changing any global random state. | property: research 01, test 13; unit: new test (the permutation for a fixed seed against exact Python integers; NumPy's global state unchanged) | Draft |
| REQ-G2D-219 | THE `enclosing_circle` function SHALL count a point as outside the current circle only when its distance from the centre exceeds the radius by more than eps_len. | unit: new test (a point at most eps_len beyond the radius leaves the circle unchanged) | Draft |
| REQ-G2D-220 | WHEN three support points are collinear, THE `enclosing_circle` function SHALL use the circle with diameter on the two farthest apart. | unit: research 01, test 13 | Draft |
| REQ-G2D-221 | THE `enclosing_circle` function SHALL add eps_len to the radius at the end, so that no input point lies outside. | property: research 01, test 13 (every flattened point lies inside before t is added) | Draft |
| REQ-G2D-222 | WHERE the input contains arcs or splines, THE `enclosing_circle_of_curves` function SHALL run the algorithm on their flattening within t = 0.001 mm (stock sizing lies outside the wall budget). | unit: new test on the curves of research 01 test 13 (the points given to the algorithm are the flattening of `flatten` at t = 0.001 mm) | Draft |
| REQ-G2D-223 | WHERE the input contains arcs or splines, THE `enclosing_circle_of_curves` function SHALL add t to the radius of the circle found. | property: research 01, test 13 (every true curve point lies inside after t is added) | Draft |
| REQ-G2D-224 | THE `enclosing_circle` function SHALL return the same circle, bit for bit, for any order of the same points under the same seed. | property: research 01, test 13 | Draft |

### Interfaces

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-225 | THE geometry2d module SHALL give every public function a `ctx: Context` parameter (research 01, Interfaces; docs/dev/03, explicit context). | unit: new test (a signature check over `geometry2d.__all__`) | Draft |
| REQ-G2D-226 | THE geometry2d functions that can report a diagnostic SHALL return a foundation `Result` and report expected outcomes as `Diagnostic`s with the codes and severities of research 01, Interfaces, never as exceptions. | unit: new test (each row of [Failure modes and diagnostics](#failure-modes-and-diagnostics)) | Draft |
| REQ-G2D-227 | THE functions `orient2d`, `incircle`, `orient3d`, `in_arc_circle`, `point_in_region`, `circle_through`, `bounding_box`, `closest_point` and `enclosing_circle` (the version for points) SHALL report no diagnostic. | review; unit: their tests above | Draft |
| REQ-G2D-228 | IF `flatten` is given an invalid curve, THEN THE function SHALL return no polyline and the curve's error diagnostic. | unit: new test (an inconsistent arc; a NURBS that needs more than 50 halvings) | Draft |
| REQ-G2D-229 | THE `build_region` function SHALL report the loop tree's diagnostics for its loops. | unit: new test (the duplicate and crossing inputs of research 01 test 7 and the loops of test 19 give the codes of `loop_tree`) | Draft |

### Degenerate input

Every row of research 01's table is covered by a requirement above, except the removal of a zero-length segment from a curve loop (Open questions); none needed one of its own.

| Case (research 01, Degenerate input) | Rule | Requirements |
| --- | --- | --- |
| Zero-length segment | distance to its point; removed by cleanup | REQ-G2D-092; REQ-G2D-204 for polylines only; curve loops: Open questions |
| Arc of length \|φ\|·r ≤ eps_len | removed by cleanup, neighbours joined at P_0 | REQ-G2D-046 |
| Arc with r ≤ eps_len | replaced by the segment P_0P_1, removed when P_0 = P_1 | REQ-G2D-047, 048 |
| Arc nearly closed | built as a full circle | REQ-G2D-049 |
| Arc end point off its circle or sweep inconsistent | `ARC_INCONSISTENT`; `CURVE_INVALID` for curve rows (Open questions) | REQ-G2D-042, 043, 192 |
| NaN or infinite value, other than a line row's centre | `CURVE_INVALID` | REQ-G2D-040, 193; NURBS data give `NURBS_INVALID` (REQ-G2D-058) |
| Loop with \|A\| ≤ eps_len·L | `LOOP_DEGENERATE`, dropped | REQ-G2D-133, 156 |
| Loop whose topology flattening has \|A\| ≤ 1.5·t_topo·L | `LOOP_DEGENERATE`, dropped by the loop tree | REQ-G2D-157 |
| Three collinear points for a circle | no circle | REQ-G2D-098 (also 099, 100) |
| Equal distances to both arc ends | P_0 | REQ-G2D-095 |
| Duplicate loops | the first in input order is kept | REQ-G2D-159 |

### Parameters

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-230 | THE geometry2d module SHALL hold its fixed constants as declared parameters with unit, default, range and source in a documented defaults file, never as literals, and pass them to its kernels as plain-value arguments, so no kernel source holds them as literals: the largest flattening step π/2 rad, the NURBS weight ratio limit 1e6, 2p + 2 closest-point samples per span, 60 Newton iterations per candidate, 50 halvings of adaptive flattening and 0.001 mm flattening for stock sizing (D-049; research 01, Parameters). | unit: new test, like foundation's `test_tolerance_defaults.py` (REQ-FND-008); review of the kernel sources; `tools/arch-check` once it exists | Draft |

## Kernel split and Clipper2

The split rule of docs/dev/03: loops over points, segments, triangles or cells go into the module's C++ kernel or vectorised NumPy; loops over operations, tools, features, files and UI stay in Python. Kernels take and return arrays and plain values, and only `bindings.cpp` includes nanobind. Long kernels release the interpreter lock and check a cancellation flag passed in as a plain value (docs/dev/03); which geometry2d kernels count as long is open (Open questions). Sign decisions run where the exact predicates are, because D-097's strict float flags apply to compiled code and a Python call per point costs more than the predicate (SRC-032 note, limit 10).

| Part | Runs in | Requirements | Why |
| --- | --- | --- | --- |
| Exact predicates, `orient2d_value`, arc predicate, (q_y − c_y)² comparison, `two_sum` and `two_product` | C++ kernel: vendored `predicates.c`, `exact.cpp` | 005–016, 021–024 | per-point loops; exact arithmetic needs the strict float flags (D-097) |
| Merging before exact tests; polyline cleanup | C++ kernel: `cleanup.cpp` | 020, 046, 204–212 | per-vertex passes, repeated to a fixpoint, with orient2d |
| Vector algebra, parallel test | vectorised NumPy (inline in C++ where a kernel needs them) | 004, 027 | per-row float arithmetic, no sign decision |
| Curve types, per-curve dispatch, entry points io calls with arrays | Python | 035–037, 054, 055 | per-curve logic |
| Arc validation and degenerate arcs, bulge conversion, curve-row validation | vectorised NumPy over rows | 038–045, 047–053, 188–197 | whole-array checks, one row per curve; no Python loop over rows |
| eps_par, ellipse evaluation, ellipse conversion and step count, NURBS storage checks, weight normalisation and ratio, reversal | vectorised NumPy | 028, 056–060, 075–076, 078, 089 | array expressions over angles, knots and control points |
| NURBS evaluation and derivatives, knot snapping test, split, clamping, trimming, subcurve, arc recognition, closest point (NURBS and ellipse arcs), inversion, flattening | C++ kernel: `nurbs.cpp` | 061–074, 077, 079–088, 090, 120–121 | per-span and per-sample loops and iterations |
| Point-to-segment and point-to-arc distances | C++ kernel: `distance.cpp` | 091–096 | per-point loops; one routine shared with point in region (148) and the loop tree (158, 163, 168), so every caller gets the same doubles |
| Circle through three points | C++ kernel: `circle.cpp`, as a batch, with a thin Python wrapper | 097–101 | per-triple loop for arc fitting; uses orient2d and `orient2d_value` |
| Arc flattening, its form by air side, and the flattening of curve-row loops | C++ kernel: `flatten.cpp` | 102–113, 199, 200 | per-row and per-vertex loops |
| Side rule, t and extra clearance per region, side of an open chain | Python (`flatten_loops`, `build_chain`), passing one air side per loop or chain to the kernel | 114–119, 122–127 | per-loop and per-operation decisions; the per-row choice of form runs in the kernel |
| Signed area | C++ kernel: `area.cpp`; the degeneracy comparison over loops in vectorised NumPy; diagnostics in Python | 128–133 | per-vertex sums, exact expansion sums above 10^6 vertices |
| Point in region, both layers | C++ kernel: `point_in_region.cpp` | 134–151 | per-point and per-edge loops with exact predicates |
| Loop tree: topology flattening, crossing tests, duplicate and touching distances, probes | C++ kernel: `loop_tree.cpp` | 152, 153, 157, 158, 160, 163, 167, 168 | per-segment-pair and per-point loops |
| Loop tree: candidate pairs by area, orientation reversal | vectorised NumPy | 165, 166, 175 | array comparisons over loops |
| Loop tree: parents, depths, ties, keeping and dropping loops, diagnostics | Python | 154–156, 159, 161, 162, 164, 170–174 | per-loop logic |
| Fallback difference, PolyTree, re-centring and grid rounding, the 2^26 refusal, source IDs, pinch split | C++ kernel with Clipper2: `region.cpp` | 030–034, 169, 176–181 | Clipper2 is a C++ library; per-point rounding and tagging loops |
| Kernel array layout, copies, read-only flags | Python and vectorised NumPy | 183–187, 198, 201–203 | checks and copies of whole arrays at the boundary |
| Bounding boxes | vectorised NumPy | 213–215 | array expressions over rows and control points |
| Enclosing circle | NumPy (`lexsort`, PCG64 raw draws); C++ kernel: `enclosing_circle.cpp` (shuffle, Welzl); Python for curves (flatten, then Welzl) | 216–224 | the shuffle and Welzl's loops are sequential per-point loops; the seeded generator stays in Python |
| Context, results, diagnostics, parameters, conventions | Python | 001–003, 025, 026, 029, 225–230 | module-wide rules |
| Determinism, CI, frames | review and CI | 017–019, 182 | module-wide rules |

Requirements that need Clipper2 2.0.1 (BSL-1.0, actively maintained; research 01, Libraries; SRC-122). Within geometry2d it is used only from the kernel; `kernel_libraries` in architecture/modules.yaml also lists it for toolpath and strategies/adaptive.

- The loop tree's rule 5 fallback difference (`contained_by_difference`) and the ties that use it: REQ-G2D-169 to 172 (research 01, test 24).
- The rule 7 PolyTree of `build_region`: REQ-G2D-176 to 181 (research 01, test 7).
- The grid and the resolution chain around these calls: REQ-G2D-030 to 034 (research 01, test 21, which calls Clipper2's union through geometry2d's kernel, D-060).
- REQ-G2D-124, 162 and 229, and every other test through `build_region`, because `build_region` builds the PolyTree (REQ-G2D-176). REQ-G2D-118 is stated on `build_region` too. The side rule itself (REQ-G2D-113 to 117, 119, 122, 123, 125, 127) is stated on `flatten`, `flatten_loops` and `build_chain`, before any Clipper2 call, and does not need it.
- REQ-G2D-018 and 019 need it only because their tests run tests 7 and 24, and REQ-G2D-026, 153, 158, 165 and 168 only for their research 01 test 24 case: through `loop_tree`, the notched pair reaches the rule 5 fallback in one direction. Their statements do not need it.

No requirement of this part needs boost-polygon. The version pin D-135, which SRC-122 names, is not in the decisions snapshot.

## Where frames and transforms belong

Research 01 puts the `Frame` type in foundation, as a small value type: a rigid transform stored as a 4 × 4 float64 matrix, with compose, invert and apply, and `FRAME_INVALID` (error) for mirrors and for rotations too far from orthonormal (research 01, Frames and transforms and Interfaces; test 10). Frames are shared by several layers: the placement of a setup (D-078) and the tilted frames of 3+2 (D-091). The type's checks are algorithms, though: a determinant test, re-orthonormalisation with z = x × y and a limit of 1e-9. Foundation's SPEC says it contains no algorithms, and its AGENTS.md sends geometry helpers to geometry2d or geometry3d, so research 01 and foundation's rules conflict (Open questions). geometry3d is no way out while model, which holds setups, depends only on foundation.

Which module applies a frame to curves is open (Open questions): geometry2d itself, through a `transform(curve, frame, ctx)` for frames that map z to ±z (its kernel still takes no frame), or a module above it, between import, which already uses geometry2d on model coordinates (`arc_from_bulge`, `make_nurbs`, `nurbs_to_arcs`), and an operation's use of geometry2d. Under a frame an arc's centre and end points transform as points, and its sweep takes the rule φ′ = sign((R·n)·z)·φ (research 01, Frames and transforms; test 10, second clause); topic 25 projects arcs whose plane is no longer parallel to xy, and io resolves mirrored DXF blocks at import (topic 21). Kernels never see frames (research 01; docs/dev/03, kernels speak arrays).

For geometry2d this means: its curves lie in the plane of the caller's frame and carry no plane; no kernel takes a frame (REQ-G2D-182). Whether geometry2d needs `Frame` at all depends on which module applies the sweep rule (Open questions). Foundation's SPEC has no `Frame` yet, so adding it is a foundation SPEC change.

## Invariants

RESEARCH 24 (Project Spike) is not in this repository; these come from research 01. Each holds for every valid input and gets a property test; the requirements named state them.

- Predicates are pure functions of their input doubles, with the same signs on every platform and thread count (REQ-G2D-006 to 013, 018, 019, 021).
- Every `Arc` geometry2d returns is valid and keeps its P_0 and P_1 bit for bit, except under the nearly closed rule (REQ-G2D-037 to 049).
- Every stored `Nurbs` satisfies the storage rule, with its largest weight 1 (REQ-G2D-057 to 059).
- Every flattening starts and ends bit for bit at the curve's end points, stays within t, and keeps arcs on the side asked for (REQ-G2D-073, 102 to 127).
- The parts of a split share the split point; a line or arc reversed twice is unchanged (REQ-G2D-074, 075).
- The sign of `signed_area` is correct whenever |A| > eps_len·L, for loops within the bound of REQ-G2D-131 or summed exactly by REQ-G2D-132 (larger extents: Open questions); it does not change under translation and flips under reversal (REQ-G2D-001, 002, 128 to 133).
- `point_in_region` returns one of IN, OUT and ON, and for one loop does not depend on its orientation (REQ-G2D-134 to 151).
- Every input loop of `loop_tree` ends in exactly one place: in the tree, dropped with `LOOP_DEGENERATE`, removed with `LOOP_DUPLICATE`, or reported with `LOOPS_CROSS` (follows from REQ-G2D-155 to 173).
- Depths and orientations agree; the tree does not depend on tol, and on input order only through the tie rules (REQ-G2D-154, 159, 164 to 175).
- Farther than t_topo from every boundary, the loop tree and the PolyTree classify points alike (REQ-G2D-031, 178).
- Cleanup moves no vertex by more than eps_len, keeps the area and is idempotent (REQ-G2D-204 to 212).
- A bounding box contains its curve, up to rounding (REQ-G2D-213 to 215).
- The enclosing circle contains its input and does not depend on the input order under one seed (REQ-G2D-216 to 224).
- Arrays at the kernel boundary satisfy the layout (REQ-G2D-183 to 203).
- No tolerance or tuning value is a literal (REQ-G2D-025, 029, 230).

## Tolerance budget

The budget and its values are foundation's (foundation SPEC, Tolerance budget; REQ-FND-009). geometry2d spends only t_flat, on the side-correct flattening of an operation's region or chain; the offset's share belongs to the topic 02 part. Every float-stage decision uses the eps_len, eps_ang and t_topo of the `Context`, which do not depend on tol.

| Value | From | Used for | Requirements |
| --- | --- | --- | --- |
| eps_len | `ctx.tolerances.length_eps_mm` | merging before exact tests; arc validation and degenerate arcs; cleanup runs; the ON band of point in region; the area test \|A\| ≤ eps_len·L; the line-distance rule of `circle_through`; the enclosing circle's outside test and margin; eps_par; knot snapping and the NURBS closest point | 020, 042, 043, 046–049, 061, 084, 099, 133, 148, 204–206, 219, 221 |
| eps_ang | `ctx.tolerances.angle_eps_rad` | the parallel test; the zero-cosine stop of the NURBS closest point | 027, 084 |
| eps_par | derived per NURBS curve, eps_len / v_max, in knot units; not on `ToleranceSet` | knot snapping; parameters are compared only with eps_par, lengths only with eps_len (research 01, trap 16) | 028, 061 |
| t_flat | `ctx.tolerances.flatten_tol_mm` | the side-correct flattening of `build_region` and `build_chain`; t_flat/2 for every curved edge with an ellipse or spline edge present, and the extra clearance t_flat/2; t_flat/4 for arc recognition per operation and for flattening the recognised arcs | 067, 068, 122–125, 127 |
| t_topo = 2u | `ctx.tolerances.topology_tol_mm` | touching and duplicate decisions; the probe distance; the both-ways band; the thinness floor; comparisons with the PolyTree | 026, 157, 158, 163, 166, 168, 178, 179 |
| u | the `Context`: needs `grid_unit_mm` on `ToleranceSet` (a foundation interface change), or u = t_topo / `topology_tol_grid_units`, which reads `TOLERANCE_DEFAULTS` too (Open questions) | the topology flattening; the ON band of replaced edges; the Clipper2 grid of 10⁴ per mm | 029, 033, 147, 152 |
| 0.0001 mm | foundation's `import_arc_deviation_mm` | the tolerance io passes to arc recognition at import (topic 21) | 065 |

`stage_tol_mm` is not used. Declared parameters geometry2d needs (D-049; research 01, Parameters), each fixed, so its range is its default; REQ-G2D-230:

| Parameter | Unit | Default | Source |
| --- | --- | --- | --- |
| largest flattening step | rad | π/2 | research 01, ours |
| NURBS weight ratio limit | none | 1e6 | Piegl and Tiller ch. 4 and 7 note |
| closest-point samples per span | count | 2p + 2 | Piegl and Tiller ch. 6 note |
| Newton iterations per candidate | count | 60 | Piegl and Tiller ch. 6 note |
| adaptive flattening depth | halvings | 50 | research 01, ours |
| flattening for stock sizing | mm | 0.001 | research 01, ours (outside the wall budget) |

They should live in a geometry2d defaults file next to the code, read like foundation's, or as new entries of foundation's `tolerance_defaults.toml` (Open questions). Numeric guards, kept in code as named constants with their source (D-049): the coordinate limit of 2^26 grid units, about 6711 mm (SRC-032 note, SRC-122), and the limits of the orientation bound, n ≤ 10^6 vertices and E ≤ 3355 mm.

## Failure modes and diagnostics

Codes and severities as research 01, Interfaces. Expected outcomes return a `Result` with diagnostics (REQ-G2D-226).

| Situation | Result | Diagnostic |
| --- | --- | --- |
| `Line`, `Arc` or `EllipseArc` with a NaN or infinite value; curve rows that break a rule of Kernel arrays | no curve, no rows | `CURVE_INVALID` (error) |
| `Arc` with φ = 0 or \|φ\| > 2π | no curve | `CURVE_INVALID` (error); our reading |
| Arc end point off its circle, or sweep inconsistent with its end points | no curve | `ARC_INCONSISTENT` (error); `CURVE_INVALID` for curve rows (Open questions) |
| Arc with r ≤ eps_len | the line P_0P_1, or nothing when P_0 = P_1 | none |
| Arc of length \|φ\|·r ≤ eps_len in a loop | removed by cleanup, neighbours joined at P_0 | none |
| Nearly closed arc | a full circle | none |
| NURBS data with a non-finite value, a wrong knot count, a decreasing knot or a weight ≤ 0 | no curve | `NURBS_INVALID` (error) |
| NURBS weight ratio above 1e6 | curve kept, weights normalised | `NURBS_WEIGHT_RATIO` (warning) |
| Interior knot of multiplicity above p; unclamped knot vector | split into curves; clamped | none |
| Adaptive NURBS flattening beyond 50 halvings | no polyline | `NURBS_INVALID` (error) |
| `flatten` given an invalid curve | no polyline | the curve's error |
| Loop with \|A\| ≤ eps_len·L | no area; the loop tree drops the loop | `LOOP_DEGENERATE` (warning) |
| Loop whose topology flattening has \|A\| ≤ 1.5·t_topo·L | dropped by the loop tree | `LOOP_DEGENERATE` (warning) |
| Duplicate loops | the first in input order kept, with its source IDs | `LOOP_DUPLICATE` (warning) |
| Loops that cross, or that contain each other by two probes | kept out of every region; crossing points reported | `LOOPS_CROSS` (error) |
| Zero-width spike | vertex dropped, region unchanged | `CLEANUP_SPIKE` (info) |
| `circle_through` with three collinear points, P_2 within eps_len of the line P_1P_3, or P_1 = P_3 | no circle | none |
| Query point on the boundary: exactly, within eps_len, or within u of a replaced edge | ON | none |
| Input of a geometry2d Clipper2 call spanning 2^26 grid units or more | refused, Clipper2 not called | error; code open |
| Clipper2 fails, or returns an implausible area, in the fallback difference or the PolyTree | no containment decision; no region | code open (D-132 gives `OFFSET_FAILED` for the offset only; Open questions) |
| Polygon region that breaks the layout | rejected before any kernel computation | open: a diagnostic or `ValueError` |
| t not positive and finite; an unknown region kind (proposal) | programming error | `ValueError` |

## Algorithms and design inputs

| Element of the method | Public source, or own design with date |
| --- | --- |
| orient2d, incircle, orient3d: adaptive four-stage predicates | Shewchuk 1997 (SRC-032), pp. 344–352; vendored `predicates.c` (D-097) |
| two_sum, two_product, expansion sums, zero elimination | SRC-032, Theorems 7, 12, 13, 18, 19 |
| Arc predicate and the exact (q_y − c_y)² comparison | own design, research 01, Vectors and exact signs (2026-10-02), with the arithmetic of SRC-032: evaluated with expansion arithmetic every time, without a floating-point filter (checked by review) |
| Parallel test without trigonometry; eps_par | own design, research 01, Tolerances (2026-10-02); eps_ang and eps_par from the Q-034 answer; SRC-024, Eq. 3.8. sin²(eps_ang) is computed once per call from the `Context`, no trigonometric function per pair (checked by review) |
| Arc form, validation and degenerate arcs | D-057; own design, research 01, Curves (2026-10-02); SRC-032 note, limit 8 |
| Bulge conversion | SRC-123 (the definition); formulas own design, research 01, Curves (2026-10-02) |
| NURBS evaluation, derivatives, knot insertion, split, reversal, clamping, subcurves | Piegl and Tiller 1997 (SRC-024), chapters 2 to 6 and 12, as research 01's literature notes give them |
| Arc and ellipse arc to NURBS | SRC-024, A7.1 and the affine map (ch. 4 and 7 note) |
| NURBS import rules; knot snapping | ch. 12 note (own design from SRC-024, sections 12.2–12.3); the snapping heuristic own design (2026-10-02) |
| Arc recognition | ch. 4 and 7 note (own design from SRC-024, Eqs. 7.25 and 7.33); D-093 |
| Safeguarded closest point (bracket condition, bisection fallback) and inversion | ch. 6 note, Algorithms (own design on SRC-024, Eqs. 6.3–6.4) |
| Per-span flattening bound, ellipse step rule, adaptive variant | ch. 12 note (own design); D-034. The bound is proven, never measured at samples (research 01, Flattening; ch. 12 note, caution 9) |
| Point to segment; point to arc | research 01, Distances and closest points (the arc rule own design, 2026-10-02) |
| Circumcentre; the line-distance rule | SRC-032, p. 359; the rule own design, research 01, Circle through three points (2026-10-02) |
| Inscribed polygon, even spread of the angle | Altintas 2012 (SRC-119), eqs. 5.85–5.86, p. 234, Table 5.2; the asin form and the clamp own design |
| Circumscribed polyline, count rule and π/2 cap, side rule, t/2 split | own design, research 01, Flattening (2026-10-02), from the error-side rule of ADR 0005; D-058 |
| Signed area with circular segments, orientation bound, degeneracy test | own design, research 01, Area and orientation (2026-10-02; Green's theorem, ε = 2^−53 from SRC-032): the rounding error of the sums stays below n·2^−53·(√2·E·L + 3E²), below eps_len·L for n ≤ 10^6 and E ≤ 3355 mm |
| Point in region in two layers | own design, research 01, Point in region (2026-10-02), from the SRC-032 note's mapping |
| Loop tree, rules 1 to 7 | own design, research 01, Loop tree (2026-10-02), from the depth rule of the review of 2026-09-23 and the SRC-032 note |
| Fallback difference and PolyTree | Clipper2 2.0.1 (SRC-122) |
| Grid, re-centring, the 2^26 limit | D-058, D-132; SRC-032 note; SRC-122 |
| Source IDs and pinch splits after a Clipper2 call | D-059, D-084 |
| Polyline cleanup; arc bounding boxes | own design, research 01, Helpers (2026-10-02) |
| NURBS bounding box | SRC-024, P3.5 |
| Smallest enclosing circle | Welzl 1991 (SRC-124, record only), SRC-125; the iterative form, canonical sort and seeded shuffle own design, research 01, Helpers (2026-10-02), for D-055 |

## Test plan

- Unit: research 01's tests and the test ideas of its literature notes, as the "Verified by" column names them; the requirements research 01 gives no test for get new tests, named there. The exact-layer cases (REQ-G2D-005, 135 to 146, 151; research 01 test 5's exact half and test 6, Shewchuk note test 6) run through `point_in_region_exact`, because `point_in_region` adds the tolerance layer (REQ-G2D-148), which makes points one rounding unit off the boundary ON.
- Property: exact rationals (Python `fractions`) as the oracle for every predicate, the area sign and the cleanup area; random arcs (validation, P_1 kept); random clamped NURBS (storage rule, flattening bound, closest point against dense samples); random nested loops (the generator of test 7); random loops with vertex clusters and spikes (cleanup). Messy inputs from RESEARCH 18 (Project Spike) once it is rewritten; until then near-collinear and near-cocircular points, offsets of one rounding unit, duplicate and touching loops, degenerate arcs, NaN and infinities.
- Golden cases: none yet; the `testdata/zoo` cases are named with the first kernel.
- Differential: the loop tree against Clipper2's PolyTree (test 7) and point in region before and after a Clipper2 union (test 21), both through geometry2d's kernel, since D-060 allows no external Python Clipper2 binding; D-060's independent checks, shapely/GEOS (test only) and point-sampling oracles, for the region of REQ-G2D-176 to 179; cross-platform CI (test 23; Shewchuk note, test 8); the build guard in every CI configuration (Shewchuk note, test 7).

Research 01's tests and the requirements they check; the last column lists the requirements whose own tests are new tests on the same inputs:

| Research 01 test | Requirements it checks | New tests on its inputs |
| --- | --- | --- |
| 1 (Shewchuk note, tests 1 to 8) | 007–011, 014–016, 018, 021 (017 by review of the CI workflows); note test 5: 097, 098; note test 6: 134, 139, 143, 148 | 013 (note test 1 in a fresh interpreter); 150 (note test 6 reversed) |
| 2 | 021, 022, 038 | none |
| 3 | 001, 002, 128 | none |
| 4 | 102–106, 110–112 | 107, 108, 113 |
| 5 | 005, 134, 135, 140, 141, 144, 145, 148, 149 | 150 |
| 6 | 023, 045, 134–138, 140, 144, 149 | 053, 141, 150 |
| 7 | 026, 153, 158–161, 163–165, 167, 168, 174–176, 178, 179 | 019, 151, 229 |
| 8 | 050 | 052 |
| 9 | 097–099, 101 | none |
| 10 | composition, inverse round trip and mirror rejection: foundation (`Frame`); the arc sweep under a rotation by π about x: owner open (Open questions) | none |
| 11 | 028 | none |
| 12 | 005, 020, 155, 204, 206–212 | none |
| 13 | 216–218, 220, 221, 223, 224 | 222 |
| 14, 15 | foundation (REQ-FND-009) | none |
| 16 | 115, 116, 119 | 118, 124 |
| 17 | 092–096 | none |
| 18 | 214 | none |
| 19 | 133, 156, 157 | 229 |
| 20 | 040, 045, 188–197 | 199, 200 |
| 21 | 030, 031 | none |
| 22 | 027 | none |
| 23 | 018 | none |
| 24 | 026, 153, 158, 165, 166, 168–170 | 019 |
| 25 | 124; the offset band of its second half belongs to topic 02 | 122, 123, 125 |
| 26 | 146, 147 | none |

## Performance budget

Research 01 gives no budget; its only performance statement is that Welzl's algorithm runs in expected linear time (Helpers; REQ-G2D-216). What research 01 does fix: per-point work never crosses the Python boundary one call at a time (REQ-G2D-024; SRC-032 note, limit 10). A budget for point in region and the loop tree is an open question.

## Size estimate

A first estimate for Peter, not yet a budget for architecture/modules.yaml. Basis: foundation's types and defaults came to 360 NLOC of Python with about 1100 lines of tests (its SPEC); this part has 230 requirements, most of their loops in the kernel. The vendored `predicates.c` and Clipper2 are third-party code and not counted.

| Part | Python NLOC | C++ NLOC | Test lines |
| --- | --- | --- | --- |
| Curve types, arc rules, bulge, curve rows | 350 | 0 | 600 |
| Ellipse arcs and NURBS | 250 | 900 | 1000 |
| Exact predicates and expansion arithmetic | 50 | 250 | 400 |
| Distances, circle through three points | 50 | 150 | 250 |
| Flattening, `build_region`, `build_chain` | 200 | 300 | 450 |
| Area, point in region | 60 | 400 | 450 |
| Loop tree and the Clipper2 calls | 250 | 550 | 700 |
| Cleanup, bounding boxes, enclosing circle | 100 | 300 | 400 |
| Kernel arrays, bindings, defaults file | 100 | 200 | 200 |
| Total | about 1400 | about 3000 | about 4500 |

At about 400 lines of non-test code per change (AGENTS.md), that is about 11 steps.

## Open questions

The section drafts' questions, research 01's "Missing before a spec" items for these sections, the points where the drafts disagreed, and the gaps the review of 2026-10-02 found. Proposals are marked.

**Scope, placement and approvals**

- Length: docs/dev/05 and the SPEC template ask for one to three pages and links to research instead of pseudo-code; one requirement per testable statement over twelve sections (plan 0001, step 4) makes this draft several times longer. Accept a long SPEC for this part, or split it, for example the ellipse and NURBS rules (REQ-G2D-054 to 090) into a later part? Peter's decision.
- The plan names "Curves (arc form and validation)". This draft also states the ellipse and NURBS rules of research 01, Curves (REQ-G2D-054 to 090). Keep them in the first geometry2d steps, or move them to a later step?
- architecture/modules.yaml lists research 02 and 03 for geometry2d, not 01, and its `kernel_libraries` has no entry for the vendored `predicates.c`, which may also need a `NOTICE` entry. Vendoring it adds a third-party dependency: does D-097 suffice, or is an ADR needed (AGENTS.md: new dependencies need an ADR)? D-135, which SRC-122 names as Clipper2's version pin, is not in the decisions snapshot. All of these need Peter.
- Topic 25: which module implements it (chaining, gap repairs, crossing resolution, projection of tilted arcs to `EllipseArc`, possibly the placement of curves)? No module in architecture/modules.yaml lists research 25; naming one is a modules.yaml change for Peter. The loop tree's input contract (see Point in region and loop tree) depends on what it guarantees.
- orient3d (REQ-G2D-012) and the 3D vector operations: research 01 puts them in geometry2d's kernel, but their users are 3D mesh tests (topics 06 and 20, release 3), and geometry3d neither depends on geometry2d nor may call its kernel (kernels-private). Keep them here, move them (a modules.yaml change), or wait for release 3? Research 01 names no orient3d test. Foundation's `Frame` needs a 3D cross product too, which it cannot import from REQ-G2D-004 (see the foundation-side questions below).
- Arc fitting (topic 11, in toolpath, which has its own kernel) needs orient2d, incircle and `circle_through` per point inside its kernel, which kernels-private does not let it reach. A shared header, batch calls through geometry2d's Python API, or a rule exception? The same holds for the Clipper2 call rules geometry2d defines (re-centring, the 2^26 refusal, D-059 tags, D-084 pinch splits): toolpath and strategies/adaptive, which also list clipper2 in modules.yaml, need them in their kernels, and kernels-private keeps them from sharing geometry2d's.
- The two rules of research 01, Flattening, that bind the operation (Scope, Out): do they go into the topic 02 part (REQ-OFF) or to the strategies?
- Bulge conversion (REQ-G2D-050 to 053) and the NURBS import rules (REQ-G2D-058 to 064) are placed in geometry2d as array maths that io calls (io alone may use ezdxf). Confirm. Piegl and Tiller ch. 12 note test 10 (a STEP knot list with multiplicities, round trip) then belongs to io, unless `make_nurbs` takes multiplicities.
- REQ-G2D-183 to 187 restate the prototype's REQ-OFF-015 (the array contract, kept by D-132), REQ-G2D-034 restates the draft REQ-OFF-018, and REQ-G2D-180 and 181 restate D-059 and D-084 for every Clipper2 call. Which IDs own these, so the topic 02 part references them instead of restating them?
- Which module applies a frame to curves, with φ′ = sign((R·n)·z)·φ (research 01, Frames and transforms, fifth bullet)? Until this is answered, the second clause of research 01 test 10 (a rotation by π about x negates the sweep of an arc in the xy plane) has no owner. Foundation holds no curves; model, which holds setups and their placement (D-078), depends only on foundation in modules.yaml. Options: a geometry2d `transform(curve, frame, ctx)` for frames that map z to ±z (geometry2d may import foundation's `Frame`; its kernel still takes no frame), or a module above geometry2d, such as the topic 25 module.
- `Frame` in foundation (research 01) conflicts with foundation's rules: its SPEC says it contains no algorithms, and its AGENTS.md allows none (its one exception is reading `tolerance_defaults.toml`) and sends geometry helpers to geometry2d or geometry3d. `Frame` needs (1) that rule relaxed; (2) its own 3D cross product for z = x × y, since foundation cannot import REQ-G2D-004; (3) a declared parameter for the orthonormality limit 1e-9 (research 01, Parameters); (4) a second foundation diagnostic, `FRAME_INVALID` (error). All are foundation SPEC and interface changes for Peter. geometry3d is no way out while model depends only on foundation.
- Arcs built outside geometry2d: research 01 has every code that builds arcs (import, chaining, arc fitting) place the centre on the perpendicular bisector of P_0P_1, but chaining and arc fitting lie outside geometry2d, whose interface only validates (`make_arc`), and REQ-G2D-044 binds only geometry2d's own constructions. Proposal: a public `arc_on_bisector(p0, p1, centre_hint, sweep_rad, ctx)` for io, the topic 25 module and toolpath, which would also serve the centre rebuild of the tiny-arc question below. Or each caller places the centre itself.
- Glossary: docs/glossary.md asks to add a term in the same change that introduces it. Should the terms of this draft go in now, with the SPEC, or with the code, since the names are still proposals? Terms: loop tree, topology flattening, side-correct flattening, machining region, winding number, bulge, fixed node, eps_par, region kind, air side, and the type names (`PointLocation`, `RegionKind`, `AirSide`, `KnotSide`, `CurveRows`, `PolygonRegion`, `FlatRegion`, `FlatChain`, `Loop`, `LoopTree`, `Box`, `Circle`, `ClosestPoint`, `are_parallel`). Proposal: define "region kind (material, air)" and "air side" apart from the glossary's "material wall / air boundary" (`material_wall`, `air_boundary`: a boundary the tool must not, or may, cross) and from D-059's edge classes (material, cleared, air), which tag edges, while `RegionKind` says what fills a region and `AirSide` where air lies beside a curve.

**Exact predicates and the build**

- `in_arc_circle` returns −1 inside, from research 01's formula: the opposite of incircle, which returns +1 inside. Keep, flip or rename?
- Research 01 says every function takes the `Context` (REQ-G2D-225); one draft proposed that the predicates take none, so their signatures show that no tolerance reaches a sign test. Do functions without diagnostics return plain values, as here, or a `Result`?
- `orient2d_value` (REQ-G2D-097, 099) returns the value predicates.c's orient2d computes: its sign is exact, its magnitude only approximate. Is that accurate enough for the centre and the line-distance rule, or should they use the plain floating-point determinant? Research 01 uses "orient2d" for both the sign and the value.
- Strict float flags (REQ-G2D-014): research 01 names only the GCC and Clang flags. Which MSVC setting, and on the whole `_kernels` target or only on the sources with exact arithmetic? `CMakeLists.txt` sets none today.
- Vendoring `predicates.c`, from general knowledge to check on the copy: it may use old-style C definitions and global state set by its initialisation routine, against warnings-as-errors. Does adapting the build count as changing the vendored file? Its header places it in the public domain, while every file is to start with an Apache-2.0 SPDX line, and `NOTICE` is protected. Peter's decision. REQ-G2D-013 rests on general knowledge (Shewchuk note, Consequences, Licence: "to verify"): the copy's header must confirm the initialisation routine before REQ-G2D-013 can become Reviewed.
- Shewchuk note test 2 says the degenerate cases "end in stage A", but `predicates.c` does not report its stage. An instrumented test build, or only "exactly 0" (REQ-G2D-008)?
- Do `check.yml` and `sanitize.yml` cover every compiler and build type, as the build guard needs (REQ-G2D-017)? Changing CI needs a person.
- Predicate preconditions: NaN or infinite inputs, and nonzero coordinates outside the exponents [−142, 201] within which the predicates cannot overflow or underflow (SRC-032, p. 308): refuse them (`ValueError`), flush them, or accept them? The arc predicate's own range has not been derived.
- Are the batch predicates multithreaded? If not, REQ-G2D-019 holds trivially. How does a geometry2d kernel learn its thread count: a new `Context` field (a foundation interface change), a plain argument of each kernel call, or one thread throughout release 1 (then REQ-G2D-019 becomes a review item)?

**Determinism**

- D-055, tier 1, against libm: the arc angle check (REQ-G2D-043), the nearly closed rule, the arc distance's angle α (REQ-G2D-093 to 095), the arc bounding box, the flattening count (asin, atan) and the points constructed for topology flattenings and probes use atan2, sin, cos, asin or atan, which are not correctly rounded on every platform. Make these decisions free of libm (exact signs, as point in region splits arcs), or accept a difference at the last rounding unit? Pinning a maths library would need an ADR. NumPy's CPU-dispatched ufuncs raise the same question for the decisions the split table places in vectorised NumPy (REQ-G2D-042, 043, 049, 214): NumPy picks SIMD versions of some float64 functions by the CPU it runs on (general knowledge, to check against the pinned NumPy), so two machines on one platform can differ in the last bit. Keep them there, or move them into the C++ kernel next to the exact predicates? Both points also bear on tier 2 below.
- Only D-055 tier 1 has requirements here (REQ-G2D-018, 019); research 01 demands only tier 1, and bit identity for the enclosing circle (REQ-G2D-224). Proposals for D-055's other tiers: (a) "THE geometry2d module SHALL return bit-identical results (arrays, curves, diagnostics and their order) for the same input and `Context` on one platform under the pinned build profile, with any thread count (D-055, tier 2)", verified by research 01 tests 4, 7, 13, 16 and 24 run twice and with one and several threads, compared byte for byte; (b) "Across macOS, Windows and Linux, THE geometry2d outputs SHALL have equal counts and lie within 0.001 mm of each other (Hausdorff) (D-055, tier 3)", verified by cross-platform CI on the same tests. The order of outputs is not stated yet. Proposal: `LoopTree.loops` in the input order of the kept loops, the region's loops in a canonical order (how: open), diagnostics in input-loop order, crossing points sorted by x, then y.

**Arc form and degenerate arcs**

- Codes: research 01 names none for φ = 0 or |φ| > 2π on an `Arc` (`CURVE_INVALID` is our reading, REQ-G2D-041). An arc row that breaks the arc rule gives `CURVE_INVALID` by Kernel arrays and test 20 (REQ-G2D-192), but `ARC_INCONSISTENT` by Curves and Degenerate input. Non-finite NURBS data: `NURBS_INVALID` (REQ-G2D-058) or `CURVE_INVALID` (Degenerate input)?
- Order of the arc rules. Proposal: non-finite values, sweep range, r ≤ eps_len (so eps_len / r is never taken with r = 0), nearly closed, radial check, angle check. Should the nearly closed rule come before the range check, so it also catches |φ| one rounding unit above 2π? "2π" needs a stated reference: the double nearest 2π lies below 2π.
- Are the degenerate-arc rules applied when an arc is built, in cleanup, or both? Should the repairs (small radius, tiny arc, nearly closed, the NURBS split and clamp) report an info diagnostic? Research 01 names none.
- Removing a tiny arc joins its neighbours at its P_0, which moves the next edge's start by up to eps_len; a following arc's radius |P_0 − C| then changes and can fail the radial check. Rebuild its centre on the bisector? A nearly closed arc inside a longer loop moves its P_1, but the next edge still starts at the old P_1.
- An arc's P_1 may lie up to eps_len off its circle (REQ-G2D-042) and is kept bit for bit (REQ-G2D-112), so the chord or half tangent that ends at P_1 can lie up to eps_len off the circle, beyond the 4 rounding units of r that research 01 test 4 allows (REQ-G2D-103, 110, 111, 119). Allow eps_len on that segment, or another rule? Research 01 test 16 (REQ-G2D-119) states no allowance at all.
- Reversing an arc makes the old P_1 its defining point, so its radius changes by up to eps_len (REQ-G2D-075, and the normalisation of REQ-G2D-175). Accepted?
- Research 01's arc sweeps "about the +z axis of its plane". geometry2d arcs lie in the plane of the caller's frame; confirm that `Arc` has no plane field.
- Bulges: a tiny |b| gives a huge radius whose sagitta is below eps_len. Treat such a bulge as a line, or reject it? Research 01 has no rule. For large radii the rounding of the bisector construction, of |P_1 − C| and of the angle can exceed the tolerances of REQ-G2D-042 and 043, so a centre on the bisector no longer guarantees them; research 01 gives no radius limit, and REQ-G2D-044's test needs one. A nonzero bulge on a zero-length chord (c = 0, coincident polyline vertices) leaves n_left undefined (0/0), and REQ-G2D-050 does not apply. Proposal: treat it as a zero-length segment that cleanup removes, or reject it with `CURVE_INVALID`; research 01 gives no rule. Where is a full circle split for export? Proposal: at the angle φ/2.
- Parameters: the parameter of `Line` is t in [0, 1], as REQ-G2D-091 uses it (proposal, from research 01, Distances). The parameter of `Arc` (for evaluate, split, subcurve, closest point and invert) is not defined; `Nurbs` uses knot units and `EllipseArc` the eccentric angle. No requirement yet gives `evaluate`, `split`, `subcurve` or `invert` for lines and arcs, or `derivatives` for lines, arcs and ellipse arcs; REQ-G2D-036 only requires the operations to exist. Research 01 lists the operations (Curves) without their behaviour.

**Ellipse arcs and NURBS**

- `EllipseArc` is not fully specified: validation (a ≥ b > 0, the tolerance on |U| = 1, the sweep range), exact end points for chains, its bounding box (Helpers gives no rule), its form at the kernel boundary, and its `reverse` (proposal: start t_0 + Δt, sweep −Δt), `split`, `subcurve`, `derivatives` and `invert` beyond the generic REQ-G2D-074, 077 and 079.
- Ellipse closest point (REQ-G2D-087): the Newton iteration starts only at t_0 = atan2(a·y, b·x). When t_0 lies outside the sweep, an interior local minimum nearer than both ends can be missed (for example Q just above the centre and an arc over the lower half, a > b). Proposal: sample the sweep (the 2p + 2 samples per span of its NURBS form) and run the bracketed iteration of REQ-G2D-081 from every local minimum. Research 01 says only "safeguarded as above" (ch. 6 note).
- NURBS end points: with the largest weight 1, an end weight other than 1 cannot hold the Euclidean end point bit for bit, but chains and REQ-G2D-112 need it. Store the end points, or normalise to end weights 1, which conflicts with REQ-G2D-059?
- Import cases research 01 does not list: degree below 1, fewer than p + 1 control points, end multiplicity above p + 1. Proposal: `NURBS_INVALID`.
- Knot snapping: which value a snapped group takes, and how a chain of knots each within eps_par of the next is grouped, deterministically.
- Closed NURBS: storage has no closed flag, but REQ-G2D-086 needs one. Is a curve closed when its end points are equal bit for bit, or within eps_len?
- The centre case (REQ-G2D-085, 096): the ch. 6 note says to flag it; research 01, Interfaces names no diagnostic for `closest_point`.
- Arc recognition (Missing before a spec): the control-point test does not bound the deviation between curve and arc. Topic 21 adds the check at import; the recognition per operation within t_flat/4 (REQ-G2D-067) has the same gap, and the angle tolerance on the middle weight is not given. Proposal: one geometry2d kernel function that returns a proven deviation bound between a NURBS piece and its recognised arc, used by io at import and by REQ-G2D-067 per operation.
- Default NURBS flattening: the per-span bound (REQ-G2D-088) or its adaptive variant (REQ-G2D-090)? Does the +1 rule of REQ-G2D-107 also apply to ellipse and NURBS step counts?
- eps_par beyond snapping: when `split`, `subcurve` or `invert` get a parameter within eps_par of an existing knot or of an end, is it moved onto that knot or end, so no span shorter than eps_par is made? Research 01 applies eps_par only to knot snapping (REQ-G2D-061; trap 16).
- `invert`: eps_len or the operation's tolerance? NURBS closest point: should the ch. 6 note's start values from a flattening with a proven error replace or supplement the 2p + 2 samples, which can miss a narrow minimum? What is reported when 60 iterations end a search?

**Distances and circle through three points**

- The drafts disagreed on where the distances to lines and arcs run: vectorised NumPy, or one kernel routine shared with point in region and the loop tree, as this draft has it.
- `closest_point` returns point and parameter (research 01, Interfaces); the distance is added here as a proposal. Should t = 0 and t = 1 return P_0 and P_1 bit for bit? Proposal for a tie at both arc ends: compare squared distances, P_0 winning on ≤.
- `circle_through`: which point defines the returned radius? Proposal: |P_1 − C|, by analogy with the arc form. Test 9's "gives that circle" has no comparison tolerance. The line-distance rule tests only P_2 against P_1P_3: is P_2 meant to be the middle point, and what of P_1 and P_3 within eps_len but not equal?
- Shewchuk note test 5 rejects (0, 0), (1, 1 + 2^−52), (2, 2) "by the radius limit"; the main text replaced that with the line-distance rule (REQ-G2D-099). The note should follow.

**Flattening**

- Which form does an arc get when it is flattened without a side (REQ-G2D-126)?
- Open chains: research 01's interface has only `build_region(loops, kind)`. A separate `build_chain(chain, air_side, ctx)` returning a `FlatChain`, as proposed here, or a third region kind?
- `flatten_loops`, the side-correct flattening before the PolyTree, is proposed so the side rule (REQ-G2D-115 to 122, 127) can be tested without Clipper2. Keep it as an internal entry, make it public, or state the side rule on `build_region`'s returned region, which the grid rounding of the PolyTree (REQ-G2D-030) then blurs (see the budget question under Point in region and loop tree)?
- Does "a region or chain that contains such an edge" mean the whole `build_region` call, which returns one extra clearance, or each region of the tree?
- Does `flatten` validate arcs and rows again, or rely on their validation at construction?

**Area and orientation**

- For a loop with ellipse or spline edges, are only those edges replaced by their topology flattening, with arcs keeping their exact segment term, or the whole loop, as rule 1 flattens arcs too?
- The proven bound covers n ≤ 10^6 and E ≤ 3355 mm. With E above that and n ≤ 10^6: the exact sum too, or refusal under the 2^26 limit? Are the arc terms ½r²(φ − sin φ) inside the bound? φ − sin φ cancels for small φ, and r is not limited by E.
- A degenerate loop: no value with `LOOP_DEGENERATE`, as here, or the tiny value with the warning? Which callers besides the loop tree (REQ-G2D-156) drop it?
- Which box centres the loop: the Helpers box, with the arcs' extreme points, or the box of the edge end points? They give different bits.
- Test 3's "the reversed loop gives the negative": exactly, or within the rounding bound (REQ-G2D-002)? Test 19's "length 10 mm" is the strip's side; L in |A| ≤ eps_len·L is its perimeter, about 20 mm.

**Point in region and loop tree**

- Piece ends: where an arc's extreme coincides with P_1, P_1 may lie up to eps_len off the circle. Proposal: piece ends at P_0 and P_1 use their stored y; only interior split points use c_y ± r.
- Interface: an array of query points, as proposed here, instead of one q; the result name `PointLocation`; the container for loops that mix curve rows with ellipse and NURBS edges; invalid loops give `CURVE_INVALID` or `ValueError`? `point_in_region_exact` exposes the exact layer for tests: public or internal?
- Rule 7 and t_flat: the PolyTree is built from side-correct flattened loops, up to t_flat from the true boundary, and t_flat exceeds t_topo from tol of about 0.0061 mm (by the t_flat formula). Does "farther than t_topo from every boundary" (test 7) include the flattened boundaries? A pocket wall and an island are both flattened into air, toward each other; loops between t_topo and 2·t_flat apart can overlap after flattening, where NonZero and EvenOdd differ (REQ-G2D-177) and depth parity need not match the hole flags. Does the test 7 generator include arcs?
- Budget: the PolyTree of `build_region` is a Clipper2 call of its own before the offset. It rounds to the grid and moves points by up to 2.83u, more than t_flat at small tol (1.1e-5 mm at tol_min), while D-132 pays the rounding margin once per offset. Should the PolyTree be built inside the offset's kernel call?
- Passing through at a touch point: loops that go from inside to outside each other only through shared vertices or edges have no proper crossing, so rule 4 accepts them as touching and rule 5 may nest them by one probe. Should rule 4 report them, or does topic 25 guarantee that they never reach the tree? May a loop touch itself?
- Crossings from flattening: exact curves less than t_topo apart that do not cross can have crossing topology flattenings, each deviating by up to u; an exact crossing of less than u can vanish. Should crossings between curves within t_topo count as touching?
- Probes: is "farther than t_topo from A" measured to A's exact curves or to its topology flattening? Are B's probes taken on its exact ellipse and spline edges or on their flattenings? In which order within each group? Proposal: B's stored edge order, then A's vertex order (D-055).
- Diagnostics: `Diagnostic.location` is a string, so where do the crossing points of `LOOPS_CROSS` go, and which points does it name when two probes find a crossing (REQ-G2D-173)? Does `loop_tree` return the tree of the other loops with `LOOPS_CROSS` (`ok` false) or no value? One `LOOP_DUPLICATE` per removed loop? Do loops of opposite orientation count as duplicates, as the vertex test implies?
- Rules 2 and 5 do not say whose area and length they use, the cleaned loop's or its topology flattening's, nor whether |B| in the fallback is the float or the grid area.
- The tie of two fallback results (REQ-G2D-171, 172) cannot happen for loops of lines only, which rule 3 has already removed as duplicates. Keep it for arcs and splines, tested through `fallback_inner`?
- Research 01 defines no array form for the tree (parent and depth per loop) coming back from the kernel, and no performance rule for rule 5's pairs of loops (O(k²)): a vectorised filter, as proposed here, or the kernel?
- How pinch splits (REQ-G2D-181) are re-nested into the tree is still to be written in topic 02 (Missing before a spec). D-059 breaks ties by edge class, not ID: which ID wins between two equally near input edges?
- Test 21: is "no point moves by more than 2.83 grid units" measured per vertex, or as the two-sided distance between input and result? D-060 allows no external Python Clipper2 binding, so its union goes through geometry2d's kernel: a test-only kernel entry, or the topic 02 Boolean?
- The coordinate limit of 2^26 grid units must become a released requirement with the D-132 kernel changes (Missing before a spec; draft REQ-OFF-018). Does it cover geometry2d's own Clipper2 calls (REQ-G2D-034), and with which code? `OFFSET_FAILED` is the offset's: D-132 gives it for library failure, an implausible area and out-of-range input of the offset only, so the failure of the fallback difference or the PolyTree has no code yet (Failure modes). The re-centring of REQ-G2D-033 extends stage 3 of the resolution chain, written for the offset kernel.

**Kernel arrays**

- "Bit for bit" continuity of rows: compare bit patterns (then −0.0 and 0.0 differ) or doubles (==)?
- `row_starts` starting at 0 and ascending is our reading, by analogy with `loop_starts`. Are wrong shapes and dtypes from our own code `CURVE_INVALID` (test 20, "each violation") or programming errors? Which diagnostic does a broken polygon region give (REQ-G2D-187); must its points be finite; may a region be empty?
- The fixed-node flag: values 0 and 1 only? Which vertices do the topic 01 functions mark?
- Forms research 01 leaves out: ellipse arcs; loops that mix lines and arcs with spline or ellipse edges; an ID per NURBS. Research 01 also gives an (n + 1, 4) form of the homogeneous control points for 3D curves, which no geometry2d value produces (REQ-G2D-198 keeps the planar form): do 3D NURBS belong in geometry2d at all, or with io for STEP edges before projection, the topic 25 module that projects them, or geometry3d?
- A one-row line loop (P_0 = P_1) passes the row rules: reject it there, or leave it to `LOOP_DEGENERATE`?
- The split rule and curve objects: a loop held as Python `Curve` objects needs a Python loop over its edges to become rows. Should loops be array-backed throughout, with `Curve` objects only for single curves?

**Helpers**

- Closing run (REQ-G2D-205): must every vertex of the last run lie within eps_len of the first vertex? If only the run's first vertex must, a later one can move by up to 2·eps_len, against REQ-G2D-206.
- Which passes repeat: research 01 says "the passes below", but test 12 needs the run pass again after the spike pass. Proposal: all three passes in a fixed order, each from the first vertex, until none changes anything.
- Research 01 test 12: if its nine vertices 0.9e-6 mm apart lie on a straight line, the collinear pass then removes three of the five kept vertices. The test needs vertices off a line, or a check of the run pass alone.
- Cleanup on curve loops: merging runs would move arc end points, which REQ-G2D-039 forbids. How do the passes apply to curve rows? Is a `Line` with P_0 = P_1 (or |P_1 − P_0| ≤ eps_len) in a curve loop or in curve rows removed with its neighbours joined at P_0, like a tiny arc (REQ-G2D-046), rejected, or left to `LOOP_DEGENERATE`? Once answered, one requirement is added for it. Do the passes apply to open chains (D-025), with fixed end vertices? What does cleanup return for a loop that falls below 3 vertices? Which source ID and fixed flag survive a merge or a drop? One `CLEANUP_SPIKE` per spike, or per loop?
- Bounding boxes: rounded outward, so they always contain the curve?
- Enclosing circle: near-collinear support points (orient2d exactly 0 only, or the rule of `circle_through`)? The iterative form does not re-check earlier points after a later change, so with the eps_len slack "no point outside" is not proven: add a final pass over all points? Does every call seed a new PCG64 from `ctx.seed`; what of negative seeds, which NumPy's `SeedSequence` rejects (see the foundation-side questions); how are −0.0 and +0.0 sorted; what is returned for no points, one point and non-finite points? Do "arcs or splines" include ellipse arcs?
- Welzl 1991 (SRC-124) has been read only as a bibliographic record; research 01 lists reading it as missing before a spec, so REQ-G2D-216 to 224 should not become Reviewed before that.

**Tolerances, parameters and runtime**

- The grid unit u is not on `ToleranceSet`, while REQ-FND-005 and foundation's SPEC ("a computation reads its tolerances from its `Context`") have computations read their tolerances from the `Context` (REQ-G2D-029). Add `grid_unit_mm` to `ToleranceSet` (a foundation interface change), or derive u = t_topo / `topology_tol_grid_units`? That ratio reads `TOLERANCE_DEFAULTS` too, and reading `TOLERANCE_DEFAULTS` from a computation would need foundation's rule changed.
- Where REQ-G2D-230's parameters live: a geometry2d defaults file (docs/dev/03, rule 5, lets only io, job and apps read files; foundation's own file is an accepted exception) or new entries in foundation's `tolerance_defaults.toml`? How is "2p + 2" declared? Research 01 lists the 2^26 limit as a fixed parameter; this draft treats it, and the bound's 10^6 and 3355 mm, as numeric guards. The factors 1.5 (rule 2), ½ (rule 5), ¼ (arc recognition and the flattening of recognised arcs, REQ-G2D-067, 068) and ½ (the spline split, REQ-G2D-122 to 125) are tuning shares of the kind foundation declares (`arc_tol_share`), but they are not in research 01's Parameters table: declare them?
- The parallel test (REQ-G2D-027) is not in research 01's interface table: its name and owner? Does "parallel" include opposite directions (tangent continuity at chain joints also needs a·b > 0)? A zero vector passes against everything.
- Cancellation and the interpreter lock: docs/dev/03 has long kernels release the interpreter lock and check a cancellation flag passed in as a plain value. Which geometry2d kernels count as long, and from what size (candidates: the flattening of curve-row loops and NURBS, point in region over many points, the loop tree, the PolyTree and the fallback)? What does a cancelled call return? No diagnostic code exists, and a new one is a foundation SPEC change. The first such kernel test would also close REQ-FND-006's pending check ("a kernel polling the flag"). Proposal, once answered: "THE long geometry2d kernels SHALL release the interpreter lock and poll the one-element cancellation flag array passed in (docs/dev/03; REQ-FND-006)."
- Programming errors: a t that is not positive and finite, or an unknown region kind, raise `ValueError` (proposal; research 01 gives no rule).
- Foundation-side questions: a `ToleranceSet` for computations without an operation (io at import, the topic 25 module and stock sizing otherwise invent a chord tolerance that geometry2d never reads there, while REQ-G2D-225 needs a `Context`); the seed's range in REQ-FND-005 (only the `Context` docstring says non-negative, and NumPy's `SeedSequence` rejects negative seeds, REQ-G2D-218); a 3D cross product in foundation for `Frame` (with the orient3d question above).
- Which performance budget for point in region and the loop tree? Research 01 gives none.

## Change log

- 2026-10-02: drafted from research 01 (plan 0001, step 4).
- 2026-10-02: review findings applied (coverage, correctness, form and architecture lenses): rows split to one testable statement each, requirements added for `flatten` with an air side and for `build_chain`'s clearance, the exact-layer and test entry points named, the frame sweep rule left without an owner in Open questions, and the file renumbered.
- 2026-10-02: final-check findings applied: no radius limit of our own in REQ-G2D-044, REQ-G2D-082 and 127 corrected, the placement section renamed, test 24's Clipper2 cases listed, citations of tests 3, 16 and 25 corrected.

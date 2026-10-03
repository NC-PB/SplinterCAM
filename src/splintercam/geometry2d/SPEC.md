# SPEC: geometry2d

<!-- The planar geometry of every later module. Slice 1 of the topic 01 part, cut on 2026-10-02 from the draft of plan 0001, step 4 (plan 0003, step 1). Requirement IDs keep the draft's numbers; the change log names the IDs merged into a neighbour, and Later parts the rest. -->

| | |
| --- | --- |
| Status | Slice 1 released by [plan 0003](../../../docs/plans/active/0003-geometry2d-slice-1.md) on Peter's answers of 2026-10-02; Peter reviews this text in the pull request of plan 0003, step 1. Choices marked "(ours)" answer open questions of the draft without asking again (D-159) |
| Layer | 1 (see architecture/modules.yaml) |
| Depends on | foundation |
| Research | [01][r01]: the main text is normative, the literature notes are evidence. This SPEC links to it instead of restating it |
| Decisions | D-028 (units), D-049 (no values buried in code), D-055 (determinism), D-057 (curve type, arc form, bulge), D-097 (exact predicates, strict float flags, snapping first); ADR 0009 (vendored `predicates.c`, proposed); text in [docs/spike/decisions-snapshot.md](../../../docs/spike/decisions-snapshot.md) |
| Owner | Peter Burgener |

## Purpose

The planar geometry every later module builds on. Slice 1 gives exact sign tests, lines and arcs with their validation, DXF bulge conversion, distances and closest points, the circle through three points, flattening with a known error side, signed area and orientation, point in region, polyline cleanup and bounding boxes. Its users are io (curves from DXF), the loop tree of slice 2, arc fitting in toolpath (topic 11) and the strategies.

## Scope

- In: [research 01][r01], sections Units and conventions, Vectors and exact signs (planar), Curves (lines and arcs), Distances and closest points, Circle through three points, Flattening (single curves), Area and orientation, Point in region (lines and arcs), Kernel arrays (curve rows) and Helpers (cleanup of polylines, bounding boxes of lines and arcs).
- Out: everything under [Later parts](#later-parts); `ToleranceSet` and the budget (foundation); reading DXF and STEP (io).
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
```

- Loops cross module boundaries as `CurveRows`, single curves as `Line` and `Arc` (ours). A `Line` or `Arc` built directly is unchecked; `make_line`, `make_arc`, `arc_from_bulge` and `curve_rows` are the validating entries, and the other functions expect their output.
- `make_arc` applies its rules in this order (ours, the draft's proposal): non-finite values, sweep range, r ≤ eps_len, nearly closed, radial check, angle check. 2π is the double nearest 2π (ours).
- `closest_point`'s parameter is t ∈ [0, 1] on a line and the angle from P_0 in the sense of φ on an arc (ours). `circle_through`'s radius is |P_1 − C| (ours).
- `cleanup` takes a closed polyline (n, 2) and returns the indices of the vertices it keeps, in order, so callers carry source IDs along (ours).
- The exact predicates are exact for coordinates that are 0 or have a magnitude in [2^−142, 2^201], about 1.8e-43 to 3e60 mm: SRC-032 (p. 308) proves this range for orient2d and incircle, and our expansions of the arc predicates stay inside it (ours). A precondition, not checked (Peter); outside it products underflow or overflow. A NaN or infinite coordinate is a programming error, `ValueError` (ours), since it would read as sign 0.
- Internal entries for tests, not in `__all__`: `two_sum`, `two_product` (exact.cpp) and `point_in_region_exact`, the exact layer alone.

## Requirements

"test N" is research 01's list of [tests][tests]; "note test N" the test ideas of its [Shewchuk note][shewchuk]. Status "Released" means released by plan 0003.

### Exact signs and determinism ([research 01, Vectors and exact signs][signs])

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-005 | THE geometry2d module SHALL take every decision on input geometry that depends on a sign (side, collinearity, inside or outside, the sweep an angle lies in) from exact predicates or exact comparisons of doubles, never from the sign of a rounded expression; loop orientation (REQ-G2D-131) is the one exception. | review; tests 5 and 12 | Released |
| REQ-G2D-006 | THE geometry2d kernel SHALL compute orient2d and incircle with Shewchuk's `predicates.c`, vendored unchanged (D-097, ADR 0009). | review | Released |
| REQ-G2D-007 | THE `orient2d` predicate SHALL return the exact sign of the orient2d determinant of research 01: +1 when c lies left of a → b, −1 right, 0 collinear. | property: note test 1, exact rationals as oracle | Released |
| REQ-G2D-008 | WHEN three points share their x or their y coordinate, THE `orient2d` predicate SHALL return 0. | note test 2 | Released |
| REQ-G2D-009 | WHEN two arguments are swapped, THE `orient2d` predicate SHALL return the negated sign. | property: note test 3 | Released |
| REQ-G2D-010 | WHEN the arguments are shifted cyclically, THE `orient2d` predicate SHALL return the same sign. | property: note test 3 | Released |
| REQ-G2D-011 | THE `incircle` predicate SHALL return the exact sign of the incircle determinant: +1 when d lies inside the circle through a, b, c given CCW, −1 outside, 0 cocircular, the opposite for CW. | note test 4 | Released |
| REQ-G2D-013 | THE geometry2d kernel SHALL call the initialisation routine of `predicates.c` once when the kernel module loads. | note test 1 as the first call in a fresh interpreter; review | Released |
| REQ-G2D-014 | THE build SHALL compile `predicates.c` and the geometry2d kernel without floating-point contraction, fast-math or reassociation: `-ffp-contract=off` and `-fno-fast-math` on GCC and Clang, `/fp:precise` on MSVC from Visual Studio 2022 (17.0), which no longer contracts under it (D-097). | note test 7 in every build (the C++ arithmetic); note test 1's grid, which reaches stages B to D of `predicates.c` (the C flags); review of `CMakeLists.txt` | Released |
| REQ-G2D-015 | THE geometry2d kernel SHALL do its exact arithmetic in IEEE 754 binary64, round to nearest even, without extended-precision intermediates. | note test 7 | Released |
| REQ-G2D-016 | THE kernel's `two_sum` and `two_product` SHALL return a pair (x, y) with x + y equal to a + b, or a·b, exactly. | property: note test 7 | Released |
| REQ-G2D-017 | THE continuous integration SHALL run the build guard (note test 7) in every configuration that builds the kernel. | review of `check.yml` and `sanitize.yml` | Released |
| REQ-G2D-018 | THE geometry2d module SHALL make the same decisions for the same input doubles on macOS, Windows and Linux: predicate signs, point locations, kept vertices and diagnostic codes and severities (D-055, tier 1). | cross-platform CI: tests 1, 2, 5 and 6 (test 23), and test 12 (ours) | Released |
| REQ-G2D-231 | THE geometry2d module SHALL return bit-identical results (arrays, curves, diagnostics and their order) for the same input and `Context` on one platform under the pinned build profile (D-055, tier 2; Peter, 2026-10-02). | tests 3, 4, 8, 9, 12, 17 and 18 run twice, compared byte for byte | Released |
| REQ-G2D-232 | THE geometry2d module SHALL return outputs with equal counts on macOS, Windows and Linux, their geometry within 0.001 mm of each other (D-055, tier 3; Peter, 2026-10-02). | cross-platform CI on the tests of REQ-G2D-231 | Released |
| REQ-G2D-020 | WHEN `cleanup` takes sign decisions, THE function SHALL first merge vertices within eps_len and then apply the exact predicates to the merged vertices (D-097). | test 12 | Released |
| REQ-G2D-021 | THE exact predicates SHALL take no tolerance and compare only with zero. | note test 1 (offsets of 2^−53); test 2 | Released |
| REQ-G2D-022 | THE `in_arc_circle(q, c, p0)` predicate SHALL return the exact sign of \|p0 − c\|² − \|q − c\|²: +1 inside the circle, 0 on it, −1 outside (Peter, 2026-10-02). | test 2, exact rationals as oracle | Released |
| REQ-G2D-023 | THE geometry2d kernel SHALL decide the sign of (q_y − c_y)² − \|p0 − c\|² exactly, so point in region compares q_y with c_y ± r without computing it (kernel `vertical_extent_signs`, used by `point_in_region`). | test 6; property against exact rationals | Released |
| REQ-G2D-024 | THE predicates SHALL take arrays of points and return one sign per row, with no Python loop per point. | review; a batch gives the signs of single rows | Released |

Release 1 kernels are single-threaded (Peter, 2026-10-02). Decisions and counts that need an angle (the arc angle check, the flattening count, the sweep of an arc) use our own arctangent, built from IEEE 754 basic operations in the kernel (`angle.cpp`), so they are the same on every platform (D-055, tier 1; ours). So does the circular segment term φ − sin φ of the signed area, which decides `LOOP_DEGENERATE` (ours). Constructed points (flattened vertices, centres) use the platform's libm and may differ in the last bit across platforms (tier 3).

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
| REQ-G2D-044 | WHEN geometry2d builds an arc from its end points, THE module SHALL place C on the perpendicular bisector of P_0P_1. | property: arcs from bulges with chords of 0.001 to 1000 mm and 0.001 ≤ \|b\| ≤ 1000 are never `ARC_INCONSISTENT` | Released |
| REQ-G2D-045 | THE `make_arc` function SHALL accept P_1 = P_0 with φ = ±2π as a full circle. | tests 6 and 20 | Released |
| REQ-G2D-047 | WHEN an arc has r ≤ eps_len and P_0 ≠ P_1, THE `make_arc` function SHALL return the line P_0P_1. | new test | Released |
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
| REQ-G2D-131 | WHERE a loop has n ≤ 10^6 vertices and a half-extent E ≤ 3355 mm, THE `signed_area` function SHALL decide the orientation from the floating-point sums. | property against exact rationals | Released |
| REQ-G2D-132 | WHERE a loop has more than 10^6 vertices or E > 3355 mm (ours), THE `signed_area` function SHALL sum the polygon part exactly. | a loop just above each limit; the exact path with arcs | Released |
| REQ-G2D-133 | IF \|A\| ≤ eps_len·L, with L the loop length, THEN THE `signed_area` function SHALL return no value and `LOOP_DEGENERATE` (warning). | test 19 (widths 1e-7 and 1e-5 mm); strips just below and above the limit | Released |
| REQ-G2D-134 | THE `point_in_region` function SHALL classify each query point against the given loops as exactly one of IN, OUT and ON. | tests 5 and 6; note test 6 | Released |
| REQ-G2D-135 | THE exact layer (`point_in_region_exact`) SHALL compute the winding number over all loops by the ray rules of research 01, Point in region: arcs split at π/2 and 3π/2 by exact signs, half-open height ranges, ±1 per crossing edge. | tests 5 and 6; rays through vertices and tangent at a circle's top and bottom; arcs split at their top and bottom; properties against an exact winding oracle and a fine flattening | Released |
| REQ-G2D-139 | THE exact layer SHALL decide whether a straight edge passes right of q by orient2d alone, and an arc piece by the arc predicate and the sign of q_x − c_x. | tests 5 and 6; note test 6 | Released |
| REQ-G2D-143 | WHEN q lies on an edge (orient2d 0 within the edge's box, or the arc predicate 0 and q on the arc itself: an end point, any point of a full circle, or a point on the arc's side of the chord P_0P_1, right of it for φ > 0 and left for φ < 0), THE exact layer SHALL classify q as ON. | tests 5 and 6; note test 6 | Released |
| REQ-G2D-145 | THE exact layer SHALL NOT classify q as ON from a zero of a helper test elsewhere (a chord line, the rest of an arc's circle). | test 5 | Released |
| REQ-G2D-148 | IF q lies within eps_len of the boundary, by the distances of REQ-G2D-091 to 096, THEN THE `point_in_region` function SHALL classify q as ON. | test 5; note test 6; property against closest_point's distances | Released |
| REQ-G2D-149 | WHEN q is not ON, THE `point_in_region` function SHALL classify q as IN where the winding number is not 0 and OUT where it is 0. | tests 5 and 6; the winding summed over two loops | Released |
| REQ-G2D-150 | WHERE one loop is given, THE `point_in_region` function SHALL give the same result for both orientations. | the reversed loops of tests 5 and 6 | Released |
| REQ-G2D-204 | WHEN cleaning a loop, THE `cleanup` function SHALL replace each run of consecutive vertices within eps_len of the run's first vertex by that vertex, walking from the first vertex. | test 12 (nine vertices, off a line) | Released |
| REQ-G2D-205 | WHEN every vertex of the last run lies within eps_len of the first vertex (ours), THE `cleanup` function SHALL join the last run to the first. | new test | Released |
| REQ-G2D-206 | THE `cleanup` function SHALL move no vertex by more than eps_len. | property: test 12 | Released |
| REQ-G2D-207 | THE `cleanup` function SHALL drop a vertex strictly between its neighbours with orient2d exactly 0, and keep one whose orient2d is not 0. | test 12 | Released |
| REQ-G2D-209 | WHEN a loop turns back exactly onto itself at a vertex, THE `cleanup` function SHALL drop that vertex and report one `CLEANUP_SPIKE` (info) per spike (ours). | test 12 | Released |
| REQ-G2D-211 | WHEN `cleanup` drops a spike, THE function SHALL leave the loop's region and signed area unchanged. | test 12; property in exact rationals | Released |
| REQ-G2D-212 | THE `cleanup` function SHALL repeat its three passes, in a fixed order, until none changes the loop (ours). | test 12; cleaning twice equals once | Released |

## Invariants

- Predicates are pure functions of their input doubles, the same on every platform (REQ-G2D-007 to 011, 018, 021).
- Every `Arc` the validating entries return is valid and keeps its P_0 and P_1, except under the nearly closed rule (REQ-G2D-037 to 049).
- Every flattening starts and ends bit for bit at the curve's end points, stays within t and keeps an arc on the side asked for (REQ-G2D-102 to 126).
- The sign of `signed_area` is right whenever \|A\| > eps_len·L and flips under reversal (REQ-G2D-001, 002, 128 to 133).
- `point_in_region` returns one of IN, OUT and ON, and for one loop does not depend on its orientation (REQ-G2D-134 to 150).
- Cleanup moves no vertex by more than eps_len, keeps the area and is idempotent (REQ-G2D-204 to 212).
- No tolerance is a literal; fixed values are declared parameters (REQ-G2D-025, 230).

## Tolerance budget

The budget is foundation's (REQ-FND-009). Slice 1 spends none of it: `flatten` takes its t from the caller, who passes t_flat for an operation and 0.001 mm for stock sizing (research 01, Flattening). It reads eps_len and eps_ang from `ctx.tolerances`. One declared parameter, the largest flattening step π/2 rad (research 01, Parameters), becomes an entry of foundation's `tolerance_defaults.toml` (a foundation SPEC change of plan 0003, step 4), passed to the kernel as a plain value; numeric guards (10^6 vertices, 3355 mm) are named constants with their source (REQ-G2D-230).

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-G2D-230 | THE geometry2d module SHALL take its fixed values from declared parameters and pass them to its kernel as plain values, so no kernel source holds them as literals (D-049). | review; a test that the step limit comes from the defaults file | Released |

## Failure modes and diagnostics

| Situation | Result | Diagnostic |
| --- | --- | --- |
| A line or arc with a NaN or infinite value; an arc with φ = 0 or \|φ\| > 2π; a bulge on a zero chord; curve rows with a broken structure | no curve, no rows | `CURVE_INVALID` (error) |
| An arc or arc row whose P_1 is off its circle or whose sweep does not fit its end points | no curve, no rows | `ARC_INCONSISTENT` (error); rows that are also `CURVE_INVALID` report only that (ours) |
| Arc with r ≤ eps_len; nearly closed arc; bulge with sagitta ≤ eps_len | the line, nothing, or a full circle | none |
| Loop with \|A\| ≤ eps_len·L | no area | `LOOP_DEGENERATE` (warning) |
| Zero-width spike | vertex dropped | `CLEANUP_SPIKE` (info), one per spike |
| `cleanup` keeps fewer than 3 vertices | those indices; the area test reports the loop | none (ours) |
| Collinear points, P_2 within eps_len of P_1P_3, or P_1 = P_3, in `circle_through` | `None` | none |
| A NaN or infinite point given to an exact predicate, `circle_through` or `closest_point` | programming error | `ValueError` (ours) |
| t not positive and finite, or so small that the step count exceeds an int; `signed_area` given more than one loop | programming error | `ValueError` (ours) |

## Algorithms and design inputs

| Element of the method | Public source, or own design with date |
| --- | --- |
| orient2d, incircle; two_sum, two_product, expansion sums | Shewchuk 1997 (SRC-032), vendored `predicates.c` (D-097, ADR 0009) |
| Arc predicate, the (q_y − c_y)² comparison | own design, research 01, Vectors and exact signs (2026-10-02), with SRC-032's expansion arithmetic |
| Arc form and validation; bulge | D-057; SRC-123 for the bulge's meaning; formulas own design, research 01, Curves (2026-10-02) |
| Distances; circle through three points | research 01 (the arc rule own design, 2026-10-02); SRC-032, p. 359 |
| Inscribed and circumscribed flattening | Altintas 2012 (SRC-119), eqs. 5.85–5.86, Table 5.2; the circumscribed form, count rule and side rule own design, research 01 (2026-10-02) |
| Signed area, orientation bound; point in region; cleanup; arc bounding boxes | own design, research 01 (2026-10-02) |

## Test plan

- Unit: research 01's tests 1 to 6, 8, 9, 12, 17 to 20 and 22, and the Shewchuk note's test ideas; new tests where the table says so.
- Property: exact rationals (`fractions`) as the oracle for every predicate, the area sign and cleanup's area; random arcs and bulges; flattening bounds on random arcs.
- Differential and cross-platform: the build guard (note test 7) and tests 1, 2, 5 and 6 (test 23) and test 12 on the three systems in CI.

## Size estimate

About 800 NLOC of Python and 900 of C++ (`predicates.c` not counted), and 2500 lines of tests, in eight steps of plan 0003. Proposed budget for `architecture/modules.yaml`: 1700 NLOC, set by Peter.

## Open questions

None for slice 1. Choices marked "(ours)" stand until Peter changes them in review.

## Later parts

No requirements; each line names the work and where its drafted requirements and open questions are (the draft of 2026-10-02, commit d1a0949, REQ IDs as drafted).

- Slice 2: the loop tree, `build_region` and the PolyTree, the side rule for regions and chains (`flatten_loops`, `build_chain`), polygon region arrays and the flattening of curve-row loops, u from the `Context`, the Clipper2 grid and resolution chain, with the topic 02 offsets and the D-132 kernel changes (REQ-G2D-019, 026, 029 to 034, 115 to 125, 127, 151 to 187, 198 to 200).
- Cleanup of curve loops: tiny arcs and zero-length lines removed with their neighbours joined, open chains (REQ-G2D-046; the cleanup questions of the draft).
- Ellipse arcs and NURBS: types, import rules, eps_par, arc recognition, their flattening, closest points and bounding boxes, spline edges in area and point in region (REQ-G2D-028, 054 to 090, 114, 129, 146, 147, 215).
- Generic curve operations: evaluate, derivatives, split, reverse, subcurve, invert, `to_nurbs` (REQ-G2D-036, 074 to 079).
- orient3d and 3D vectors (REQ-G2D-004, 012).
- Curve transforms: applying a `Frame` to curves and the sweep rule, `Frame` in foundation (REQ-G2D-182; research 01 test 10).
- Smallest enclosing circle (REQ-G2D-216 to 224).
- Kernel sharing with toolpath: arc fitting's access to the predicates and `circle_through`, and the Clipper2 call rules, under kernels-private.
- Cancellation and threads: long kernels release the interpreter lock and poll the cancellation flag; thread count.
- A performance budget for point in region and the loop tree; the topic 25 module and its input contract.

## Change log

- 2026-10-02: drafted from research 01 (plan 0001, step 4), with review fixes.
- 2026-10-03: plan 0003, step 5: the predicates' input range stated as a precondition (SRC-032, p. 308).
- 2026-10-02: cut to slice 1 on Peter's answers (plan 0003, step 1): in_arc_circle +1 inside, arc rows give `ARC_INCONSISTENT`, predicates without a `Context`, D-055 tiers 2 and 3 (REQ-G2D-231, 232), single-threaded kernels; the draft's proposals taken for the other slice 1 questions and marked "(ours)"; everything else moved to Later parts. Merged into a neighbour: 095 into 094, 107 and 108 into 106, 111 into 110, 136 to 138 into 135, 140 to 142 into 139, 144 into 143, 195 into 194, 202 into 201, 208 into 207, 210 into 209. Stated in the Public interface instead: 225 to 227. Not needed: 228 (`flatten` expects validated curves). Slice 2: 229.

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
[helpers]: ../../../docs/research/01-foundations.md#helpers
[tests]: ../../../docs/research/01-foundations.md#tests
[shewchuk]: ../../../docs/research/01-foundations.md#shewchuk-1997-adaptive-precision-floating-point-arithmetic-and-fast-robust-geometric-predicates

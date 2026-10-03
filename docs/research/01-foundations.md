---
topic: "01"
title: Foundations
readiness: L4
release: "1"
reviewed: 2026-10-02
provenance: public
---

[Index](README.md) · [2. 2D offsets and Booleans →](02-offsets-and-booleans.md)

# 1. Foundations

The shared vocabulary of every geometry module: vector operations, exact sign tests, the tolerance model, one curve type, flattening with a known error side, area and orientation, point in region, the loop tree, frames, kernel arrays and a few helpers. The `foundation` module (Python and NumPy only) holds the tolerance set and the frame type; `geometry2d` holds the curves and the algorithms, with its C++ kernel ([engineering/03](../engineering/03-architecture-rules.md), layers 0 and 1). Every later topic builds on it.

## Scope

- In: vector algebra in the plane and in space; exact predicates and the snapping before them; the tolerance model (epsilons, the per-operation budget, the resolution chain from model to NCX); the curve type, its arc form and its validation; flattening within a tolerance on a known side; signed area and orientation; point in region; the loop tree; rigid frames; the array layout at the kernel boundary; polyline cleanup, bounding boxes, the smallest enclosing circle, closest points; the rules for degenerate input.
- Out: offsets and Booleans ([02](02-offsets-and-booleans.md)); arc fitting and point reduction ([11](11-path-optimisation.md)); reading DXF, STEP and meshes, including arc recognition at import ([21](21-geometry-input.md)); chaining selections into loops, with its gap tolerance ([25](25-machining-areas-and-selections.md)). A convex hull is not needed in release 1.

## Inputs and outputs

- In: curves in model coordinates from import (topic 21) and closed or open chains from selections (topic 25), in mm and radians (D-028); per operation its tolerance `tol` (D-029); for each use of a tolerance, the side on which its error may fall (ADR 0005).
- Out: the functions and types in the interface table below.

## Method

### Units and conventions

- Lengths in mm, angles in radians, float64 inside; degrees only in the UI, in files for people and in NCX, which writes angles in degrees (D-028, topic 26). "No value" is NaN or an optional type, never a magic number (ADR 0005).
- The plane is right-handed with y up. Counter-clockwise (CCW) is the positive sense, and a CCW loop has positive area.
- The inside of a region lies on the left of every loop: outer boundaries CCW, holes CW. The loop tree normalises this. Whether the inside is material (a part outline, an island) or air (a pocket) depends on the operation.
- "Within d" means a distance ≤ d, as in `nearly_equal` (REQ-FND-003).

### Vectors and exact signs

For a = (a_x, a_y, a_z) and b = (b_x, b_y, b_z):

```math
a\cdot b = a_x b_x + a_y b_y + a_z b_z \qquad a\times b = (a_y b_z - a_z b_y,\; a_z b_x - a_x b_z,\; a_x b_y - a_y b_x)
```

Every decision that depends on a sign (which side, collinear or not, inside or outside, crossing or not) uses an exact predicate: Shewchuk's adaptive orient2d, incircle and orient3d, vendored as `predicates.c` and built with strict float flags (D-097, Q-080, SRC-032):

```math
\operatorname{orient2d}(a,b,c) = (a_x - c_x)(b_y - c_y) - (a_y - c_y)(b_x - c_x) \quad (>0:\ c \text{ lies left of the directed line } a\to b)
```

The sign is exact for the doubles given, so every platform and thread count makes the same decisions (D-055, tier 1). Exactness concerns the doubles, not the design intent: points that should coincide are merged first, then tested exactly. No sign test carries an epsilon (SRC-032 note, limit 7). The one exception is loop orientation, decided by a proven bound (see Area and orientation).

Arcs need one own predicate (ours): whether q lies inside, on or outside the circle of an arc with centre c and start point p_0, whose distance defines the radius (see Curves). Its sign is that of

```math
(q_x - p_{0x})(q_x + p_{0x} - 2c_x) + (q_y - p_{0y})(q_y + p_{0y} - 2c_y) = |q - c|^2 - |p_0 - c|^2
```

a polynomial in the input doubles, evaluated exactly every time with the expansion arithmetic of the same paper (two_sum, two_product, expansion sums; SRC-032 note, Method 1 and 2). It is small, so no floating-point filter is used. The same arithmetic decides (q_y − c_y)² against |p_0 − c|², which point in region needs.

### Tolerances

All values are declared parameters (D-049) in the `ToleranceSet` of the `Context`; code holds no literal epsilon (ADR 0005).

- **eps_len = 1e-6 mm** (Q-034 answer): two points within eps_len are the same point. Why this value (ours): at coordinates up to 10 m, doubles are spaced about 1.8e-12 mm apart, so eps_len is about 10^5 times larger than the rounding noise of a few operations, and 100 times smaller than 0.0001 mm, the output step of four decimals that D-149 recommends for 3D smoothing. It equals the NCX resolution of D-149.
- **eps_ang = 1e-9 rad** (Q-034 answer): directions within eps_ang are parallel. Why (ours): an angle of eps_ang moves a point 1 m away by eps_len. It is used where a tolerance on direction is meant: tangent continuity at chain joints (topic 25) and tangent breaks in arc fitting (topic 11). Tests of the form |a × b|² ≤ sin²(eps_ang)·|a|²|b|² need no trigonometry.
- **eps_par** (Q-034 answer: derived from eps_len): parameters of a NURBS curve within eps_par are the same parameter. eps_par = eps_len / v_max, with v_max an upper bound of |C′(u)| (ours, the first-derivative form of the flattening bound in the chapter 12 note). For a polynomial curve, v_max is the largest derivative control point p·|P_{i+1} − P_i| / (u_{i+p+1} − u_{i+1}), because C′ lies in their convex hull (SRC-024, Eq. 3.8). For a rational curve, translate the control points so the centre of their bounding box is the origin; then v_max = (M1_A + R·M1_w) / w_min, with M1_A and M1_w the largest derivative control points of the homogeneous coordinates, R the largest control point distance from the origin and w_min the smallest weight. It is computed on the knots as read, before any snapping.
- **tol**: the operation tolerance, the largest deviation of the finished wall from the model, the control included (D-056). Defaults 0.05 mm for roughing and 0.01 mm for finishing (D-029); the user may set it from tol_min to 1 mm. The upper limit is ours, a guard against unit mistakes (a value meant in µm or inch); it can be raised by decision. The model is machined as given; sizes change only through the allowance (D-150).

**The budget** (D-056, D-146, D-149), per operation, with u = 0.0001 mm the grid unit of the offset kernel:

| Part | Size | Spent on |
| --- | --- | --- |
| geometry | 0.1·tol + 6u + max(0, 2u − 0.05·tol) | the flattening allowance 0.05·tol (below); the offset kernel's join tolerance a = max(0.05·tol, 2u) plus its rounding margin 6u (D-132) |
| fit band | the rest: 0.3·tol − 6u − max(0, 2u − 0.05·tol) | arc fitting, on the air side (topic 11) |
| control | 0.5·tol | written per operation as NCX `TOLERANCE` (topic 26) |
| reserve | 0.1·tol | NCXchange's rounding to the machine's decimals, stated in the NCX as the rounding allowance (D-149) |

The flattening allowance 0.05·tol pays for three things (ours): arcs recognised from NURBS at import, which may differ from the file by up to 0.0001 mm (D-093); snapping and the removal of tiny arcs, at most 3·eps_len (a tiny arc lies within 2·eps_len of its chord, and snapping moves the chord by up to eps_len); and flattening, which gets the rest, t_flat = 0.05·tol − 0.0001 mm − 3·eps_len. At tol = 0.01 mm, t_flat = 0.000397 mm.

The fit band reaches 0 at tol_min = 8u / 0.35 = 0.0022857… mm (the floor term applies there, because 0.05·tol_min < 2u). The decision is tol ≥ tol_min, with tol_min computed once from u, and the fit band is clamped at 0, because in double the band at tol_min itself comes out as −7e-20 mm (ours). Below tol_min the operation is refused with `TOL_BELOW_MINIMUM`, naming 0.0022858 mm, tol_min rounded up to 0.1 nm so that the suggested value is accepted (draft REQ-FND-009). At tol_min arc fitting has no band and keeps the flattened polyline, so circles leave as short lines there; G2/G3 output (D-023) needs a fit band. t_flat is still 1.1e-5 mm. NCXchange reports a tolerance that a machine's output rounding cannot hold (D-149).

**The resolution chain** (ours, from D-034, D-052, D-055, D-058, D-084, D-097, D-132 and D-149). Each stage has its place in the budget:

1. Model: native curves in float64, as imported, except arcs recognised from NURBS (D-034, D-057, D-093).
2. Float stages (flattening, snapping, loop tree, point in region, arc fitting): points within eps_len are merged first, then decisions use exact predicates (D-097). Topology decisions (touching, crossing, duplicate) use t_topo = 2u = 0.0002 mm (ours): rounding to the grid moves a point by at most (√2/2)·u, so two features can approach each other by at most √2·u < t_topo on the grid.
3. Integer stage: the offset kernel re-centres its input and rounds it to the grid u (D-058, D-132). Clipper2 2.0.1 decides most signs and collinearity with 128-bit integer products (`CrossProductSign`, `ProductsAreEqual`; SRC-122). Some decisions it makes in double: the spike test in `CleanCollinear` (a `DotProduct`), `SegmentsIntersect` in `FixSelfIntersects`, the area thresholds in `DoSplitOp`, and the input orientation of `ClipperOffset` (a shoelace area) (SRC-122). The products in those tests, like our own integer tests (pinch points, D-084), are exact in double only while coordinate differences stay below 2^26 grid units, about 6.7 m (SRC-032 note). The kernel must therefore refuse larger input; today that limit exists only as the draft REQ-OFF-018 (see Missing before a spec).
4. Points move by up to 2.83 grid units in Clipper2 (SRC-118; measured on the prototype's grid of 10⁶ per mm, but counted in grid units, so the count carries over to 10⁴ per mm; test 21 checks it). The rounding margin of D-132 covers it.
5. After a kernel call the topology comes from the integer result only; no float-stage test re-decides it. Features between eps_len and t_topo apart can merge on the grid; t_topo makes the float stages treat them as touching first. Where loops touch, the integer result may join them differently from the float loop tree (rule 7 of the loop tree); the integer result is authoritative for the machining region.
6. Record: float64, unrounded (D-052).
7. NCX: written at 1e-6 mm (1e-7 inch) and 1e-7°, the same for every machine, with each operation's rounding allowance (D-148, D-149).
8. Machine: NCXchange rounds once to the machine's decimals, within the allowance (D-149).

### Curves

One tagged curve type with four variants: Line, Arc, EllipseArc and Nurbs (D-057, Q-035 answer, D-092). Each variant provides eval, derivatives with a side at knots, split, reverse, subcurve, bounding box, closest point, invert, flatten and conversion to NURBS (chapter 12 note).

**Arc form** (D-057). An arc stores its start and end points P_0 and P_1 exactly, its centre C and a signed sweep φ, positive CCW about the +z axis of its plane, with 0 < |φ| ≤ 2π. The radius is r = |P_0 − C|. P_1 is never moved. The arc is valid when ||P_1 − C| − r| ≤ eps_len and the angle from P_0 to P_1 about C, taken in the sense of φ, equals |φ| modulo 2π within eps_len / r; otherwise it is rejected with `ARC_INCONSISTENT` (ours; this is how we read "arc end points on their circle" in the Q-080 answer, SRC-032 note limit 8). Code that builds arcs (import, chaining, arc fitting) places the centre so both end points fit, on the perpendicular bisector of P_0P_1. A full circle has P_0 = P_1 and φ = ±2π. An arc of length |φ|·r ≤ eps_len is removed by cleanup, like a zero-length segment, and its neighbours are joined at P_0. An arc with r ≤ eps_len is replaced by the segment P_0P_1, or removed when P_0 = P_1; its points lie within 2r ≤ 2·eps_len of that segment, which the budget covers. An arc with |P_1 − P_0| ≤ eps_len, |φ| > π and (2π − |φ|)·r ≤ eps_len is built as a full circle, P_1 = P_0 and φ = ±2π (ours); otherwise the angle check rejects it.

**Bulge**, only at DXF import and export (D-057). A DXF polyline stores an arc on its start vertex as a bulge: the ratio of the sagitta to half the chord, positive for CCW, 0 for a straight segment, 1 for a semicircle (SRC-123). That ratio equals b = tan(θ/4), θ the included angle (ours: sagitta r(1 − cos(θ/2)) over half chord r·sin(θ/2)). For a chord of length c from P_0 to P_1 (ours):

```math
\theta = 4\arctan b \qquad r = \frac{c\,(1+b^2)}{4\,|b|} \qquad C = M + d\,n_{\text{left}},\quad d = \frac{c\,(1-b^2)}{4\,b}
```

with M the chord midpoint and n_left the unit normal to the left of P_0 → P_1. A bulge cannot hold a full circle (b would be infinite), so a full circle on a polyline needs two arcs (ours).

**Splines and ellipses** stay native in the model and are flattened per operation (D-034). DXF SPLINE and ELLIPSE follow the Autodesk reference as ezdxf reads it (D-092, Q-074); ellipse arcs are analytic, in centre, unit major axis, a, b, start eccentric angle and signed sweep (D-092, chapter 4 and 7 note). The NURBS rules, with their evidence in the Piegl and Tiller notes:

- Storage: degree p ≥ 1, a clamped knot vector with m + 1 = n + p + 2 values, end multiplicity p + 1, interior multiplicity at most p, and homogeneous control points with all weights > 0 (chapter 2 and 12 notes).
- Import (chapter 12 note, "Import of an exchanged NURBS curve"): reject non-finite values, a knot count other than n + p + 2, decreasing knots and weights ≤ 0 (`NURBS_INVALID`); normalise the weights so the largest is 1 and report, but keep, a curve whose ratio of largest to smallest weight exceeds 1e6 (`NURBS_WEIGHT_RATIO`; chapter 4 and 7 note, caution 5); snap knots within eps_par only when no sample point (2p + 2 per span) moves by more than eps_len, else keep them (ours, a heuristic: samples are no proof); split at interior knots of multiplicity above p; clamp unclamped and "periodic" curves; extract trimmed subcurves once.
- Arc recognition (D-093): at import, the control-point test of the chapter 4 and 7 note ("Recognising a circular arc") within 0.0001 mm, then a check of the deviation between curve and arc, so the 0.0001 mm of the budget holds (the test alone does not bound it; see Missing before a spec). Per operation, NURBS pieces that are arcs within t_flat/4 become arcs, which are then flattened within t_flat/4; such edges count as spline edges for the side rule (D-093, Q-075; split ours).
- Derivatives take a side (left or right) at knots; a knot of multiplicity p is a corner and stays a vertex in every flattening (chapter 2 note).
- Closest point: the safeguarded Newton iteration of the chapter 6 note, with 2p + 2 samples per span, at most 60 iterations per candidate, a bracket and bisection fallback, all local minima and both ends compared. Plain Newton from the nearest flattened point can converge to a wrong minimum or leave the span (chapter 6 note, cautions 4 and 5).
- Flattening: the per-span bound of the chapter 12 note; its adaptive variant halves at most 50 times (ours), after which `NURBS_INVALID` is reported.

### Distances and closest points

Point Q to segment P_0P_1 with |P_1 − P_0| > 0 (a zero-length segment is the point P_0):

```math
t = \operatorname{clamp}\!\left(\frac{(Q-P_0)\cdot(P_1-P_0)}{|P_1-P_0|^2},\,0,\,1\right) \qquad d = |Q - (P_0 + t(P_1-P_0))|
```

Point Q to an arc (ours): let α be the angle of Q − C measured from P_0 − C in the sense of φ, in [0, 2π). If α ≤ |φ|, then d = | |Q − C| − r |; otherwise d is the distance to the nearer end point, P_0 when both are equally near. For Q = C every arc point is at distance r, and P_0 is returned as the closest point.

### Circle through three points

Used by arc fitting (topic 11). With u = P_1 − P_3 and v = P_2 − P_3, the centre is (SRC-032 note, p. 359)

```math
C_x = P_{3x} - \frac{u_y|v|^2 - v_y|u|^2}{2\operatorname{orient2d}(P_1,P_2,P_3)} \qquad C_y = P_{3y} + \frac{u_x|v|^2 - v_x|u|^2}{2\operatorname{orient2d}(P_1,P_2,P_3)}
```

There is no circle when orient2d is exactly 0. There is none either when P_2 lies within eps_len of the line P_1P_3, that is |orient2d(P_1, P_3, P_2)| / |P_3 − P_1| ≤ eps_len: then the circle cannot be told from that line at the model's resolution, and its radius comes from rounding (ours; SRC-032 note, test 5). P_1 = P_3 gives no circle. Callers apply their own radius limits (topic 11).

### Flattening with a known error side

An arc of radius r and sweep φ is replaced by a polyline within a tolerance t:

- **Inscribed polygon**: vertices on the arc, chords inside the circle; the largest deviation is r(1 − cos(Δθ/2)) at the chord midpoints (the control's own chord rule, SRC-119, eqs. 5.85–5.86, p. 234). Step Δθ_in = 4·asin(√(min(1, t / (2r)))), the same as 2·arccos(1 − t/r) but accurate for small t/r; the clamp avoids NaN for t > 2r (ours).
- **Circumscribed polygon** (ours): every segment touches the arc and the polyline stays outside the circle. The vertices, at radius r / cos(Δθ/2), deviate most, so r / cos(Δθ/2) − r ≤ t gives Δθ_out = 2·atan(√(t(2r + t)) / r), the same as 2·arccos(r / (r + t)). The polyline runs from P_0 through the vertices at the angles θ_0 + (k + ½)Δθ, k = 0 … n − 1, to P_1: its first and last segments are half tangents at P_0 and P_1, so chains stay connected.
- **Count**: n = ⌈|φ| / min(Δθ, π/2)⌉, raised by 1 if rounding makes |φ|/n exceed the bound; then Δθ = |φ| / n, spread evenly (as the controls do, SRC-119, p. 234 and Table 5.2). The inscribed polygon has n chords, the circumscribed polyline n + 1 segments, two of them half tangents. The π/2 cap is a quality rule, at least four steps per full circle (ours). The inscribed formula has no solution for t > 2r, where the cap applies anyway.
- **Side** (ours, from the rule of ADR 0005): a flattened boundary lies in air. For a region of material, an arc with φ > 0 has its centre on the material side and is flattened circumscribed, an arc with φ < 0 inscribed. For a region of air (a pocket) the choice flips. For an open chain (a profile along picked curves, D-025), air is the side the tool works on. A flattened wall then never enters the material, as the offset kernel's own chords never do (D-058).
- **Ellipses and splines**: the flatten algorithm of the chapter 12 note puts its vertices on the curve with a proven two-sided Hausdorff bound (D-034); its chords lie on the concave side of each piece without an inflection and on both sides across one (caution 7). To keep the error in air, a region or chain that contains such an edge has every curved edge flattened within t/2 (arcs on their side as above), and the operation adds t/2 to the clearance of every kernel offset it makes from that region, toward air (ours; caution 7 of the same note). No extra kernel call is made, so the kernel's join tolerance and rounding margin are paid once per offset. An operation that needs the side but makes no offset of its own makes one offset with clearance t/2. Lines and arcs then deviate by at most t/2 + t/2, splines and ellipses lie in air within t. Uses without an offset (point in region, stock sizing) need no side. Measuring the error at samples is no proof (caution 9).

In every case t = t_flat of the budget.

### Area and orientation

The signed area of a loop of lines and arcs (ours, Green's theorem; the first sum runs over the end points of all edges, the second adds each arc's circular segment):

```math
A = \tfrac12\sum_i (x_i y_{i+1} - x_{i+1} y_i) \;+\; \sum_{\text{arcs}} \tfrac12\, r^2 (\varphi - \sin\varphi)
```

A full circle gives πr². Loops with ellipse or spline edges use their topology flattening (see Loop tree). The orientation is the sign of A, positive for CCW. This is the one sign decision made by a proven bound instead of an exact predicate (ours): after translating the loop to the centre of its end points' bounding box, the rounding error of the polygon sum stays below about n·u·(√2·E·L + 3E²), u = 2^−53, for n vertices, half-extent E and length L ≥ 4E, which is below eps_len·L for n ≤ 10^6 and E up to 3355 mm, half the 2^26 range. Loops with more vertices or a larger extent sum the polygon part exactly with the expansion arithmetic (ours); the rounding of the translated coordinates then moves A by at most 2u·E·L, below eps_len·L for E up to about 10^9 mm.

The segment terms add their own error (ours, 2026-10-03). Each is formed as r̂²·p̂, where r̂² = r²(1 + θ) with |θ| ≤ γ_4 = 4u/(1 − 4u) and p̂ is φ − sin φ from basic operations: within 16u·|p| for |φ| ≤ 1 (its series, no cancellation) and within 64u for |φ| > 1 (sin of φ reduced to [−π, π]). The products and their sum are formed exactly with the expansion arithmetic, on both paths, so the error does not grow with the number of arcs. With |p| ≤ |φ|³/6 for |φ| ≤ 1 and |p| ≤ 2|φ| beyond, one arc of radius r and length ℓ = r·|φ| adds at most 40u·r·ℓ·min(1, φ²), and the computed area satisfies

```math
|\hat A - A| \;\le\; B_{\text{poly}} + 40u \sum_{\text{arcs}} r\,\ell\,\min(1, \varphi^2) + u\,|\hat A|
```

Here B_poly is n·u·(√2·E·L + 3E²) plus 2u·E·L for the translation on the float path, and 2u·E·L alone on the exact path. At the float limits B_poly reaches 0.81·eps_len·L, so the arcs may add 0.19·eps_len·L: enough while every arc has r·min(1, φ²) ≤ 10^7 mm, with a factor of four to spare. The factor min(1, φ²) admits flat arcs of huge radius (a bulge of 1e-8 on a 1000 mm chord: r = 2.5e10 mm, r·φ² = 4e-5 mm). The two limits, r·min(1, φ²) ≤ 10^7 mm and E ≤ 10^9 mm, are preconditions of the sign guarantee for eps_len ≥ 1e-6 mm, documented and not checked. A loop with |A| ≤ eps_len·L encloses nothing and is rejected as degenerate (`LOOP_DEGENERATE`).

### Point in region

The result is IN, OUT or ON. Two layers (ours, from the SRC-032 note's mapping):

**Exact layer.** The winding number of q, summed over the loops considered, from a ray to the right of q:

- Each arc is first split at the angles π/2 and 3π/2 (its highest and lowest points) where they lie inside its sweep, into pieces that are monotone in y. Whether they lie inside is decided from exact signs (the sides of P_0 and P_1 relative to the horizontal and vertical lines through C, and the sense of φ), not from atan2. A full circle needs no special case.
- A straight edge or arc piece from height y_a to y_b counts when q_y lies in the half-open range [min(y_a, y_b), max(y_a, y_b)) and the edge passes strictly right of q at height q_y. Going up it adds +1, going down −1.
- "Passes right of q": for a straight edge, orient2d decides. For an arc piece on the right half of its circle (x ≥ c_x), q is left of it when q_x < c_x or q lies inside the circle; on the left half, when q_x < c_x and q lies outside the circle (the arc predicate). The ends of an arc piece at a highest or lowest point have y = c_y ± r, which is not a double; q_y is compared with them through the sign of q_y − c_y and the arc predicate on (q_y − c_y)².
- q is ON when it lies on an edge: orient2d = 0 and q within the edge's bounding box, or the arc predicate = 0 and q on the arc itself: an end point, any point of a full circle, or a point on the arc's side of the chord P_0P_1 (right of it for φ > 0, left for φ < 0). Zeros of the helper tests elsewhere (on a chord line, on the rest of an arc's circle) mean nothing.

In loops with ellipse or spline edges, those edges are replaced by their topology flattening (within u, see Loop tree); lines and arcs stay exact. q within u of a replaced edge, measured to the true curve, is ON (ours).

**Tolerance layer.** q is also ON when its distance to the boundary is within eps_len (computed with the distances above). Otherwise q is IN where the winding number is not 0 and OUT where it is 0. With normalised orientation the winding is 1 inside a region; for a single loop of either orientation, "not 0" is what counts.

### Loop tree

Proposal (ours), from the depth rule of the 2026-09-23 review and the SRC-032 note. The input is the closed chains of topic 25, which closes gaps within its own chaining tolerance and reports them as model repairs; it also resolves crossings (by its union of a self-crossing projected loop, or with the user) before loops reach the tree.

1. Arc, ellipse and spline edges are replaced, for topology only, by a flattening within u, two-sided (topology flattening), so every test of rules 3 and 4 is a polyline test. Containment probes (rule 5) use point in region as defined above, with exact lines and arcs and the topology flattening of ellipse and spline edges; they lie farther than t_topo from the other loop, so the result is the one the exact curves give. The side-correct flattening for the operation is made later, after rule 6.
2. Each loop is cleaned (Helpers). A loop failing the area test, or whose topology flattening has |A| ≤ 1.5·t_topo·L (thinner than about 3·t_topo on average), is reported as degenerate and dropped (ours; grid rounding in the rule 5 fallback can widen a thinner loop's difference past half its area).
3. Two loops are duplicates when every vertex of each topology flattening lies within t_topo of the other polyline (point-to-segment distance), both ways. One is kept, the first in input order with its source IDs, with `LOOP_DUPLICATE`.
4. Loops that still cross, themselves or each other, are reported with their crossing points (`LOOPS_CROSS`) and do not become a region. Crossings are found with exact segment tests (orient2d) on the topology flattenings; loops with a segment-to-segment distance within t_topo that do not cross count as touching. Touching loops (shared vertices or edges) are allowed.
5. The parent of a loop B is the loop that contains B and lies inside every other loop containing B. B is tested only against loops with a larger |A|, which containment requires; loops whose areas differ by at most t_topo·(L_A + L_B) are tested both ways, because rounding can flip that order. Containment is tested by point in region of one probe of B against A alone (winding not 0), the first farther than t_topo from A among: the vertices of B, the midpoints of its edges and arcs, and the projections of A's vertices onto B's edges. If none is that far, B ⊂ A when the area of B minus A, from a Clipper2 difference of the topology flattenings with the NonZero fill rule, is less than |B|/2 (ours). When loops tested both ways are found to contain each other, a result from a probe stands over one from the fallback; when both come from the fallback, B ⊂ A when the area of B minus A is less than that of A minus B, and on equality the loop earlier in input order is the inner one; when both come from probes, the loops cross and are reported with `LOOPS_CROSS` (ours).
6. Even depth is the outer boundary of a region, odd depth a hole of the region around it. Orientation is then normalised: even depth CCW, odd depth CW.
7. The machining region of an operation is the Clipper2 PolyTree of the side-correct flattened, normalised loops, built with the NonZero fill rule, which on normalised loops gives the same result as EvenOdd (topic 02). The PolyTree is authoritative for the region (resolution chain, stage 5). Where loops touch, it can differ from this tree loop by loop: Clipper2 2.0.1 merges an island that shares an edge with its parent into the parent's boundary, and an island that touches its hole at a vertex into that hole (found by the review of 2026-10-02, built against 2.0.1); D-084's pinch split separates such points (how the split parts are re-nested is still to be written in topic 02). The two trees are therefore compared as point sets (test 7), and loop by loop only where all loops are more than t_topo apart.

### Frames and transforms

Proposal (ours):

- A frame is a rigid transform: a rotation R (3 × 3, orthonormal, determinant +1) and a translation t in mm, with p_outer = R·p_inner + t. It is stored as a 4 × 4 float64 matrix [[R, t], [0, 0, 0, 1]]. Frames compose by matrix product, M_a←c = M_a←b · M_b←c, and invert as [[Rᵀ, −Rᵀt], [0, 0, 0, 1]].
- Uses in release 1: the placement of the part model in the work frame of a setup and its work offset (D-078, topic 26 `placement`); later the tilted frames of 3+2 (D-091).
- A rotation read from data is checked first for its determinant: below 0 it is a mirror and is rejected (`FRAME_INVALID`). Then, when the largest absolute entry of RᵀR − I is at most 1e-9, it is re-orthonormalised (x normalised, y made orthogonal to x and normalised, z = x × y); above that it is rejected.
- A mirrored DXF block is resolved at import instead: coordinates mirrored, arc sweeps negated, loops reversed (topic 21).
- Under a frame, the centre and end points of an arc transform as points. For an arc whose plane normal n maps to ±z, the sweep becomes φ′ = sign((R·n)·z)·φ: it changes sign for a setup machined from below (rotation by π about x). Arcs whose plane is not parallel to xy after the transform are not 2.5D curves; topic 25 projects them (a tilted circle projects to an ellipse).
- Kernels receive coordinates already in the work frame and never see frames (ours, following the array rule of [engineering/03](../engineering/03-architecture-rules.md)).

### Kernel arrays

At the C++ boundary (D-057, D-059, D-084, Q-035 answer, the prototype's REQ-OFF-013 and 015; engineering/03 allows only arrays and plain values):

- Polygon region: `points` (n, 2) float64 in mm and `loop_starts` (k,) int64, starting at 0 and ascending; a loop closes back to its first vertex, which is not repeated, and has at least 3 vertices. Per vertex, the int64 source ID of the edge that starts there (D-059) and a uint8 fixed-node flag (D-084).
- Curve rows: (m, 7) float64 [x0, y0, x1, y1, cx, cy, sweep] with an int64 ID per row, and `row_starts` (k,) int64 for the loops (ours). A row is a line when sweep is 0 (−0.0 counts as 0) and then cx and cy are NaN; otherwise cx and cy are finite and 0 < |sweep| ≤ 2π, and the arc rules above hold. All other values are finite. Within a loop, each row starts bit for bit where the previous one ends, and the loop closes: the last row ends where the first starts. A loop may be one row (a full circle) or two (for example a line and an arc). A violation is `CURVE_INVALID`.
- NURBS: degree, knots (m + 1,) float64 and homogeneous control points (n + 1, 4) float64, or (n + 1, 3) for planar curves (chapter 12 note).
- Arrays cross as C-contiguous, read-only copies; no Python objects, callbacks or OCCT types cross the boundary.

### Helpers

- **Polyline cleanup** (ours): walk the vertices in their stored order from the loop's first vertex; a run of consecutive vertices within eps_len of the run's first vertex is replaced by that first vertex, and a new run starts at the first vertex farther away, so no vertex moves by more than eps_len. At the end, a last run within eps_len of the first vertex joins the first run. The passes below repeat until nothing changes. Drop a vertex that lies between its neighbours with orient2d exactly 0. Drop a zero-width spike, a vertex where the loop turns back exactly onto itself; this changes the boundary, not the region, and is reported (`CLEANUP_SPIKE`). Removing nearly collinear vertices is point reduction within the fit band (topic 11), not cleanup.
- **Bounding box**: lines by their end points; arcs by their end points plus the points at the angles 0, π/2, π and 3π/2 that lie inside the sweep (all four for a full circle) (ours); splines by the strong convex hull of their control points (SRC-024, P3.5), which can be larger than the curve.
- **Smallest enclosing circle**, for cylinder stock (D-026, topic 08): Welzl's randomized algorithm, expected linear time (SRC-124, SRC-125). In its iterative form (ours): sort the points by x, then y; shuffle them by a Fisher–Yates shuffle driven by the raw 64-bit outputs x of NumPy's PCG64 bit generator seeded from the `Context` seed: for i from n − 1 down to 1, swap item i with item j = ⌊x·(i + 1) / 2^64⌋ (a 128-bit product), so the permutation does not depend on the version of NumPy's higher-level methods (D-055); then for each point i outside the current circle, restart from the circle of i alone; inside that, for each earlier point j outside, the circle with diameter ij; inside that, for each earlier point k outside, the circle through i, j and k. A point counts as outside when its distance from the centre exceeds the radius by more than eps_len. Three collinear support points give the circle on the two farthest apart. At the end eps_len is added to the radius, so no point lies outside. With arcs or splines, run it on a flattening within t = 0.001 mm (stock sizing lies outside the wall budget) and add t to the radius, so the circle cannot cut into the part (ours).
- **Closest point**: see Distances and closest points, and the NURBS rules.

### Interfaces

Proposed (ours), for the module SPECs (D-153). Every function takes the `Context` (engineering/03), which carries the tolerance set with eps_len, t_topo and t_flat.

| Function or type | Module | Result | Diagnostics (severity) |
| --- | --- | --- | --- |
| `ToleranceSet.for_operation(tol, ctx)` with the budget parts, t_topo and t_flat | foundation | a `ToleranceSet`, or none | `TOL_BELOW_MINIMUM` (error; draft REQ-FND-009) |
| `Frame` (value type) with compose, invert, apply | foundation (proposed small value type) | a frame | `FRAME_INVALID` (error) |
| `orient2d`, `incircle`, `orient3d`, `in_arc_circle` | geometry2d kernel | sign −1, 0, +1 | none |
| `Curve` (Line, Arc, EllipseArc, Nurbs) and curve rows | geometry2d | validated curves | `ARC_INCONSISTENT`, `CURVE_INVALID`, `NURBS_INVALID` (errors); `NURBS_WEIGHT_RATIO` (warning, curve kept) |
| `flatten(curve, t, side, ctx)` | geometry2d | polyline with a proven bound | as above |
| `build_region(loops, kind, ctx)`, kind material or air | geometry2d | the side-correct flattened region, and the extra clearance t/2 every offset from it must add when a spline or ellipse edge needs it | as for the loop tree |
| `signed_area(loop, ctx)` | geometry2d | mm² | `LOOP_DEGENERATE` (warning, loop dropped) |
| `point_in_region(q, loops, ctx)` | geometry2d | IN, OUT or ON | none |
| `loop_tree(loops, ctx)` | geometry2d | tree with depths and normalised loops | `LOOP_DEGENERATE`, `LOOP_DUPLICATE` (warnings); `LOOPS_CROSS` (error) |
| `cleanup(loop, ctx)` | geometry2d | cleaned loop | `CLEANUP_SPIKE` (info) |
| `circle_through(p1, p2, p3, ctx)` | geometry2d | centre and radius, or none | none |
| `bounding_box`, `closest_point`, `enclosing_circle` | geometry2d | box, point and parameter, circle | none |

Diagnostics follow the `Result` and `Diagnostic` types of the foundation SPEC.

### Degenerate input

| Case | Rule |
| --- | --- |
| Zero-length segment | distance to its point; removed by cleanup |
| Arc of length \|φ\|·r ≤ eps_len | removed by cleanup, neighbours joined at P_0 |
| Arc with r ≤ eps_len | replaced by the segment P_0P_1, removed when P_0 = P_1 |
| Arc nearly closed, \|P_1 − P_0\| ≤ eps_len, \|φ\| > π and (2π − \|φ\|)·r ≤ eps_len | built as a full circle |
| Arc end point off its circle or sweep inconsistent | `ARC_INCONSISTENT` |
| NaN or infinite value, other than a line row's centre | `CURVE_INVALID` |
| Loop with \|A\| ≤ eps_len·L | `LOOP_DEGENERATE`, dropped |
| Loop whose topology flattening has \|A\| ≤ 1.5·t_topo·L (thinner than about 3·t_topo) | `LOOP_DEGENERATE`, dropped by the loop tree |
| Three collinear points for a circle | no circle |
| Equal distances to both arc ends | P_0 |
| Duplicate loops | the first in input order is kept |

## Parameters

| Parameter | Unit | Default | Range | Source |
| --- | --- | --- | --- | --- |
| tol (user) | mm | 0.05 roughing, 0.01 finishing | tol_min = 2/875 ≈ 0.00228571 (named as 0.0022858) to 1.0 | D-029, D-146, D-149; upper limit ours |
| eps_len | mm | 1e-6 | fixed | Q-034 answer |
| eps_ang | rad | 1e-9 | fixed | Q-034 answer |
| eps_par | knot units | eps_len / v_max per curve | derived | Q-034 answer; formula ours |
| grid unit u | mm | 0.0001 | fixed | D-058, D-132 |
| t_topo | mm | 2u = 0.0002 | fixed | ours |
| geometry part | mm | 0.1·tol + 6u + max(0, 2u − 0.05·tol) | derived | D-146 |
| import arc deviation | mm | 0.0001 | fixed | D-093 (Q-075) |
| t_flat | mm | 0.05·tol − 0.0001 − 3·eps_len | derived, > 0 | ours, inside D-146 |
| fit band | mm | 0.3·tol − 6u − max(0, 2u − 0.05·tol) | derived, ≥ 0 | D-146 |
| control part | mm | 0.5·tol | derived | D-056 |
| reserve (rounding allowance) | mm | 0.1·tol | derived | D-056, D-149 |
| coordinate differences in the kernel | grid units | below 2^26 (about 6711 mm) | fixed | SRC-032 note, SRC-122; draft REQ-OFF-018 |
| largest flattening step | rad | π/2 | fixed | ours |
| NURBS weight ratio limit | none | 1e6 | fixed | chapter 4 and 7 note |
| closest-point samples per span | count | 2p + 2 | fixed | chapter 6 note |
| Newton iterations per candidate | count | 60 | fixed | chapter 6 note |
| adaptive flattening depth | halvings | 50 | fixed | ours |
| frame orthonormality limit | none | 1e-9 | fixed | ours |
| flattening for stock sizing | mm | 0.001 | fixed | ours |

Only tol is a user parameter; the rest are declared constants or derived values (D-049).

## Traps

1. Mixed orientation conventions invert offsets: normalise in the loop tree, the inside on the left.
2. Comparing floats with `==`, or with a literal epsilon in a sign test.
3. Inscribed chords on a convex wall cut into the part: flatten on the air side.
4. The π/2 cap keeps at least four steps per circle; the arccos forms lose accuracy for small t/r, so use the asin and atan forms.
5. The arc form is over-determined: P_0 defines the radius, P_1 is checked, never moved.
6. A bulge cannot hold a full circle and carries no centre.
7. A "nearest edge" fallback for unclear inside tests is inconsistent: snap, then decide exactly.
8. Zeros of helper tests (a chord line, the rest of a circle) are not the boundary.
9. Plain Newton projection from the nearest flattened point can find the wrong minimum or leave the span.
10. Sampling the chord error is no proof: use the bound.
11. FMA contraction and fast-math break exact predicates (D-097; SRC-032 note, test 7).
12. A frame that flips the plane normal reverses arc senses; mirrors are rejected, mirrored DXF blocks resolved at import.
13. A line row carries a NaN centre: never read cx and cy when the sweep is 0.
14. NCX angles are degrees, the core works in radians.
15. Welzl's shuffle without the canonical sort and the `Context` seed gives a different result per run or per input order.
16. Parameters are not lengths: compare parameters with eps_par, lengths with eps_len.
17. Clipper2 makes some decisions in double: keep kernel input below 2^26 grid units.

## Tests

1. Predicates: tests 1 to 8 of the Shewchuk note.
2. Arc predicate: C = (0, 0), P_0 = (5, 0): q = (3, 4) gives 0, q = (3, 4 − 2^−50) inside, q = (3, 4 + 2^−50) outside; exact rationals are the oracle.
3. Area: a full circle of r = 10 mm gives 100π within 1e-12 relative; the square [0, 10]² mm with its right side replaced by an outward semicircle about (10, 5) gives 100 + 12.5π ≈ 139.270 mm²; the reversed loop gives the negative.
4. Flattening, r = 10 mm, t = 0.001 mm, full circle: n = 223 in both forms, 223 chords inscribed and 224 segments circumscribed, two of them half tangents. On 10^4 samples per segment, inscribed points lie inside the circle within t, circumscribed points outside within t, up to 4 rounding units of the radius; the first and last points equal P_0 and P_1 exactly.
5. Point in region, exact layer, for the loop of test 3: (15, 5) ON; (15 − 2^−49, 5) IN; (15 + 2^−49, 5) OUT (one rounding unit at 15). With the tolerance layer all three are ON, while (15 − 2e-6, 5) is IN and (15 + 2e-6, 5) OUT. (10, 5) on the chord line is IN; (5, 5), on the arc's circle but not on the arc, is IN. With an inward semicircle (φ = −π), (10, 5) is OUT. Also test 6 of the Shewchuk note.
6. Full circle as a loop, C = (0, 0), r = 5, P_0 = P_1 = (5, 0), φ = 2π: (0, 0) IN, (5, 0) ON, (10, 0) OUT, (0, 5) ON, (0, −3) IN.
7. Loop tree: three nested squares give depths 0, 1, 2 and two regions side by side give 0 and 0; a duplicate loop is kept once with `LOOP_DUPLICATE`; an island touching the outer wall is accepted; two crossing squares give `LOOPS_CROSS` with their crossing points; a triangle (0, 0), (10, 0), (10, 10) inside the square [0, 10]² finds its probe at the midpoint of its hypotenuse; the square [0, 10]² and the same square with a notch 0.1 mm wide and 5 mm deep give the notched loop as the child of the square. On 1000 random nested inputs, point in region on the float tree and on Clipper2's PolyTree agree at random points farther than t_topo from every boundary; where all loops are more than t_topo apart, depth parity also equals the PolyTree's hole flags.
8. Bulge: from (0, 0) to (2, 0), b = 1 gives r = 1, C = (1, 0), φ = +π; b = −1 gives φ = −π; b = tan(π/8) gives r = √2, C = (1, 1), φ = +π/2.
9. Circle through three points: test 5 of the Shewchuk note; (0, 0), (1, 1 + 2^−52), (2, 2) gives no circle by the line-distance rule, not by a division by zero; (10, 0), (−10, 0) and the point at angle −1e-4 rad on the circle of radius 10 about the origin give that circle, although the chord P_1P_3 is only 0.001 mm long.
10. Frames: composition and inverse round-trip within 16 rounding units of the largest coordinate; a rotation by π about x negates the sweep of an arc in the xy plane; diag(1, 1, −1) and diag(−1, 1, 1) are rejected as mirrors.
11. eps_par: for the quarter circle of radius 10 mm as a rational quadratic (weights 1, √2/2, 1), v_max = 30.35 mm per knot unit bounds the true largest speed of 16.57, so eps_par ≈ 3.3e-8.
12. Cleanup: an exactly collinear vertex is removed, one a rounding unit off the line is kept; nine vertices 0.9e-6 mm apart become five runs, kept at 0, 1.8e-6, 3.6e-6, 5.4e-6 and 7.2e-6 mm, and no vertex moves by more than eps_len; the loop (0, 0), (10, 0), (10, 10), (10, 20), (10, 10), (0, 10) loses its spike with `CLEANUP_SPIKE` and keeps its area.
13. Enclosing circle: the same circle, bit for bit, for any input order with the same seed; every flattened point lies inside the result before t is added, and every true curve point after; three collinear points give the circle on the outer two.
14. Budget at tol = 0.01 mm: geometry 0.0016, fit band 0.0024, control 0.005, reserve 0.001, sum 0.01; t_flat = 0.000397 mm.
15. Budget near tol_min: 0.0022858 mm is accepted with a fit band of about 3e-8 mm; the double nearest 8u/0.35 is accepted with the fit band clamped to 0; 0.0022857 mm is refused with `TOL_BELOW_MINIMUM` naming 0.0022858 mm.
16. Side rule: a material region with a CCW arc (circumscribed, polyline outside the circle) and a CW arc (inscribed); the same arcs in a pocket flip; an island in a pocket; every flattened point lies in air or on the true boundary.
17. Distances: point to arc inside and outside the sweep, at C (distance r, P_0), and equally near both ends (P_0); a zero-length segment.
18. Arc bounding box: sweeps that cross 0, π/2, π and 3π/2, one that crosses none, and a full circle.
19. Degenerate loop: a loop of width 1e-7 mm and length 10 mm is rejected by the area test; one of width 1e-5 mm passes the area test but is dropped by the loop tree (|A| ≤ 1.5·t_topo·L); one of width 0.001 mm is kept by both.
20. Curve rows: each violation in Kernel arrays gives `CURVE_INVALID`; −0.0 as sweep is a line; a one-row full circle and a two-row line and arc are valid loops.
21. Resolution chain: random float loops, some with features between eps_len and t_topo, sent through Clipper2's union at 10⁴ per mm (directly, since the offset with clearance 0 may skip the kernel): no point moves by more than 2.83 grid units, and point in region on the float input and on the result agree at random points farther than t_topo from every boundary.
22. Parallel test: directions 1e-10 rad apart are parallel, 1e-8 rad apart are not.
23. Cross-platform: the results of tests 1, 2, 5, 6, 7 and 24 are identical on macOS, Windows and Linux (D-055, tier 1).
24. Loop tree, close areas and the fallback: the square [0, 10]² and the rectangle [0, 10.001] × [0, 10], whose areas differ by less than t_topo·(L_A + L_B), give the rectangle as parent in either input order. The square [0, 10]² and the same square with a notch 0.002 mm wide and 5 mm deep at x = 2 (areas 0.01 mm² apart) give the notched loop as the child in either input order: its probe at the notch bottom stands over the fallback's answer for the other direction. The rule 5 fallback, called directly against the square [0, 10]²: the triangle (0, 0), (10, 0), (5, −1) is not contained (B minus A is all of B), the triangle (0, 0), (10, 0), (5, 1) is.
25. Side rule with a spline edge: a material region bounded by an S-shaped cubic spline (one inflection) and an arc gives an extra clearance of t/2; after the one offset by a tool radius R plus t/2, every point of the offset path lies at least R and at most R + t + a + 6u from the true boundary (D-132; a is the kernel's arc tolerance).
26. Point in region on a loop with a spline edge: points farther than 2u from the spline get the same result as on a flattening within 1e-8 mm; a point within u of it is ON.

## Libraries

- NumPy (BSD-3-Clause, actively maintained) for arrays in Python and for the seeded PCG64 generator ([ADR 0004](../decisions/0004-tech-stack.md)).
- Shewchuk's `predicates.c`, public domain per its file header, vendored in the kernel (D-097, Q-080). It has not changed since 1996 and needs no maintenance beyond the build flags.
- Clipper2 2.0.1 (BSL-1.0, actively maintained, release of December 2025) for regions and the PolyTree (topic 02, topic 17, SRC-122).
- No linear algebra library: the 2D and 3 × 3 operations are written directly. This replaces the earlier advice to use Eigen or System.Numerics, which was written for another stack (A-043).
- ezdxf (MIT, actively maintained) at DXF import (topic 21, D-092).

## Sources

- SRC-024: Piegl and Tiller 1997, *The NURBS Book* (five notes below).
- SRC-032: Shewchuk 1997, exact predicates (note below).
- SRC-119: Altintas 2012, chapter 5: the chord rule for arcs (p. 234) and the even spread of the angle (Table 5.2); note in topic 11.
- SRC-118: plan 0001, Clipper2 moves points by up to 2.83 grid units.
- SRC-122: Clipper2 2.0.1 source, its sign tests and the call sites that decide in double.
- SRC-123: ezdxf documentation, the bulge value of LWPOLYLINE.
- SRC-124: Welzl 1991, smallest enclosing disks (bibliographic reference); SRC-125: the description of Welzl's algorithm on Wikipedia.
- Decisions: D-023, D-025, D-026, D-028, D-029, D-034, D-042, D-049, D-052, D-055, D-056, D-057, D-058, D-059, D-078, D-084, D-091, D-092, D-093, D-097, D-132, D-146, D-148, D-149, D-150, D-153.
- Statements marked "ours" are our own derivations or design. Nothing in this topic rests on proprietary material (D-042, T-033; consolidated 2026-10-02).

## Literature notes

The main text above and the decisions are normative; these notes are the evidence. Where a note comments on the main text, it refers to its state before the consolidation of 2026-10-02. Known differences: the chapter 12 note's arc stores a radius, a plane frame and a start angle with a sweep in (−2π, 2π] (the main text and D-057: exact end points, centre and signed sweep, |φ| ≤ 2π); the chapter 2 and 6 notes define eps_par relative to the knot range (main text: eps_len / v_max); the Shewchuk note decides orientation at the lowest-leftmost vertex (main text: the area with a proven bound).

Distilled from the sources in our own words (D-044): each note carries what an implementer needs without the paper; the citation is there for checking.

### Piegl and Tiller 1997, chapter 2: B-spline basis functions and B-spline curves

**Source:** Les Piegl, Wayne Tiller, *The NURBS Book*, 2nd edition, Springer, Berlin Heidelberg 1997 (Monographs in Visual Communication), ISBN 978-3-540-61545-3, doi:10.1007/978-3-642-59223-2. Chapter 2 "B-Spline Basis Functions" (pp. 47–79) and the curve sections of chapter 3 "B-spline Curves and Surfaces" (sections 3.1–3.3, pp. 81–100), with the Bézier background of chapter 1 (sections 1.2–1.4, pp. 5–34). Page numbers are the printed ones.

**Read:** pp. 47–79 in full; pp. 81–100 in full; pp. 5–34 skimmed for Bézier and rational Bézier background. Surface sections (pp. 100–116) skipped. Formulas checked on page images where the text layer was broken (pp. 50, 59–61, 94, 95, 97, 99). **Class:** L.

Notation used in all five notes: degree p, control points P_0 … P_n, weights w_0 … w_n, knot vector U = {u_0, …, u_m}, parameter u. Lengths in mm. The book's own symbols are kept where they are standard.

#### Definitions and formulas

**Bézier background (chapter 1).**

- Bernstein polynomials (Eq. 1.8, p. 10): B_{i,n}(u) = n! / (i! (n − i)!) · uⁱ (1 − u)ⁿ⁻ⁱ, u ∈ [0, 1]. They are non-negative, sum to 1, B_{0,n}(0) = B_{n,n}(1) = 1, and obey B_{i,n} = (1 − u) B_{i,n−1} + u B_{i−1,n−1} with B_{i,n} ≡ 0 for i < 0 or i > n (properties P1.1–P1.6, pp. 15–17).
- Bézier curve (Eq. 1.7): C(u) = Σ_{i=0}^{n} B_{i,n}(u) P_i. Derivative (Eq. 1.9, p. 22): C′(u) = n Σ_{i=0}^{n−1} B_{i,n−1}(u) (P_{i+1} − P_i), again a Bézier curve, one degree lower. End derivatives (Eq. 1.10): C′(0) = n (P_1 − P_0), C″(0) = n (n − 1)(P_0 − 2P_1 + P_2), and symmetrically at u = 1.
- de Casteljau (Eq. 1.12, p. 24): set P_{0,i} = P_i; for k = 1 … n and i = 0 … n − k, P_{k,i} = (1 − u) P_{k−1,i} + u P_{k−1,i+1}; then C(u) = P_{n,0}. Repeated linear interpolation between points near the curve is less sensitive to round-off than Horner evaluation of the power basis (p. 25).
- Rational Bézier (Eq. 1.14, p. 27): C(u) = Σ B_{i,n}(u) w_i P_i / Σ B_{i,n}(u) w_i, with all w_i > 0 assumed so the denominator stays positive. Homogeneous form (Eqs. 1.16–1.18, pp. 29–31): P_iʷ = (w_i x_i, w_i y_i, w_i z_i, w_i); the curve Cʷ(u) = Σ B_{i,n}(u) P_iʷ is polynomial in 4D, and C(u) is obtained by dividing by the fourth coordinate. The book processes rational curves this way throughout (p. 32).
- A circle cannot be written with polynomial coordinates (proof pp. 25–26); rational functions are required.

**Knots and basis functions (chapter 2).**

- A knot vector is a non-decreasing sequence u_0 ≤ u_1 ≤ … ≤ u_m (p. 50). The half-open interval [u_i, u_{i+1}) is the i-th knot span; it may be empty. The multiplicity of a knot value is how often it repeats.
- Cox–de Boor recurrence (Eq. 2.5, p. 50):
  - N_{i,0}(u) = 1 if u_i ≤ u < u_{i+1}, else 0;
  - N_{i,p}(u) = (u − u_i)/(u_{i+p} − u_i) · N_{i,p−1}(u) + (u_{i+p+1} − u)/(u_{i+p+1} − u_{i+1}) · N_{i+1,p−1}(u);
  - any quotient 0/0 is defined as 0 (p. 51).
- Properties (pp. 55–58): P2.1 local support, N_{i,p} = 0 outside [u_i, u_{i+p+1}); P2.2 on a span [u_j, u_{j+1}) at most p + 1 functions are non-zero, namely N_{j−p,p} … N_{j,p}; P2.3 non-negativity; P2.4 partition of unity on every span; P2.5 inside a span all derivatives exist, at a knot of multiplicity k the function is C^{p−k}; P2.6 for p > 0 each function has exactly one maximum.
- Number of functions (pp. 64–65): with m + 1 knots there are m − p basis functions of degree p, so n + 1 = m − p. They are linearly independent and span the piecewise polynomials with the continuity set by the multiplicities (Eq. 2.12).
- Clamped knot vector, called "nonperiodic" or "open" in the book (Eq. 2.13, p. 66): U = {a, …, a, u_{p+1}, …, u_{m−p−1}, b, …, b} with a and b each repeated p + 1 times. Then N_{0,p}(a) = 1 and N_{n,p}(b) = 1 (P2.8), and U = {0 ×(p+1), 1 ×(p+1)} gives the Bernstein polynomials (P2.7). "Uniform" means equally spaced interior knots (p. 66). The whole book assumes clamped knot vectors; chapter 12 treats the other kind (note e).
- First derivative (Eq. 2.7, p. 59): N′_{i,p} = p/(u_{i+p} − u_i) · N_{i,p−1} − p/(u_{i+p+1} − u_{i+1}) · N_{i+1,p−1}.
- k-th derivative, recursive form (Eq. 2.9, p. 61): N^{(k)}_{i,p} = p · ( N^{(k−1)}_{i,p−1}/(u_{i+p} − u_i) − N^{(k−1)}_{i+1,p−1}/(u_{i+p+1} − u_{i+1}) ).
- k-th derivative, direct form (Eq. 2.10, p. 61): N^{(k)}_{i,p} = p!/(p − k)! · Σ_{j=0}^{k} a_{k,j} N_{i+j,p−k} with a_{0,0} = 1, a_{k,0} = a_{k−1,0}/(u_{i+p−k+1} − u_i), a_{k,j} = (a_{k−1,j} − a_{k−1,j−1})/(u_{i+p+j−k+1} − u_{i+j}) for j = 1 … k − 1, a_{k,k} = −a_{k−1,k−1}/(u_{i+p+1} − u_{i+k}). Zero denominators give a zero term. Derivatives of order k > p vanish.

**B-spline curves (chapter 3).**

- Definition (Eq. 3.1, p. 81): C(u) = Σ_{i=0}^{n} N_{i,p}(u) P_i on a clamped U, with m = n + p + 1 (Eq. 3.2, p. 82). The book takes a = 0, b = 1 unless stated.
- Properties (pp. 82–90): P3.1 no interior knots and n = p gives a Bézier curve; P3.3 C(a) = P_0, C(b) = P_n; P3.4 affine invariance (transform the control points); P3.5 strong convex hull: for u ∈ [u_i, u_{i+1}), C(u) lies in the convex hull of P_{i−p} … P_i, so p + 1 collinear control points give a straight piece; P3.6 moving P_i changes the curve only on [u_i, u_{i+p+1}); P3.7 the control polygon is a piecewise linear approximation that improves under knot insertion or degree elevation; P3.9 variation diminishing: no line (2D) or plane (3D) meets the curve more often than the control polygon; P3.10 C^∞ inside spans, at least C^{p−k} at a knot of multiplicity k (it can be smoother if the control points happen to line up, Figure 3.11); P3.11 coincident control points P_j = P_{j+1} give a visible cusp even though the curve is C¹ there, because the derivative shrinks to zero (p. 90).
- Derivative as a curve (Eqs. 3.4–3.6, p. 94): C′(u) = Σ_{i=0}^{n−1} N_{i,p−1}(u) Q_i with Q_i = p (P_{i+1} − P_i)/(u_{i+p+1} − u_{i+1}), where N_{i,p−1} is taken on U′ = U without its first and last knot.
- End tangents (Eq. 3.7, p. 97): C′(0) = p/u_{p+1} · (P_1 − P_0), C′(1) = p/(1 − u_{m−p−1}) · (P_n − P_{n−1}). For a general range [a, b], replace u_{p+1} by u_{p+1} − a and 1 − u_{m−p−1} by b − u_{m−p−1}.
- Higher derivatives (Eq. 3.8, p. 97): P_i^{(0)} = P_i and P_i^{(k)} = (p − k + 1)/(u_{i+p+1} − u_{i+k}) · (P_{i+1}^{(k−1)} − P_i^{(k−1)}), so C^{(k)}(u) = Σ_{i=0}^{n−k} N_{i,p−k}(u) P_i^{(k)} on U^{(k)}, which drops k knots at each end.
- Second derivative at the start (Eq. 3.9, p. 99): C″(0) = p (p − 1)/u_{p+1} · [ P_0/u_{p+1} − (u_{p+1} + u_{p+2}) P_1/(u_{p+1} u_{p+2}) + P_2/u_{p+2} ]; Eq. 3.10 gives the mirror image at u = 1.

#### Algorithms

Our pseudocode, in our notation; the book's listings are A2.1–A2.5 and A3.1–A3.4.

**Find the span** (idea of A2.1, p. 68). Input U, p, n, u with u_p ≤ u ≤ u_{n+1}. Output i with u_i ≤ u < u_{i+1} and u_i < u_{i+1}. Cost O(log n).

```
find_span(U, p, n, u):
    if u >= U[n+1]: return n            # right end belongs to the last non-empty span
    lo, hi = p, n + 1                   # invariant: U[lo] <= u < U[hi]
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if u < U[mid]: hi = mid else: lo = mid
    return lo                           # last index with U[lo] <= u, so the span is non-empty
```

For a left-hand limit at a knot (derivative "from the left", p. 78) use the variant that returns i with u_i < u ≤ u_{i+1}.

**All non-zero basis values of all degrees on one span** (idea of A2.2 and of "AllBasisFuns", p. 99). Input span i, u, p, U. Output table V[d][j] = N_{i−d+j,d}(u) for d = 0 … p, j = 0 … d. Cost O(p²).

```
basis_table(U, p, i, u):
    V[0] = [1]
    for d in 1..p:
        for j in 0..d:                                  # function N_{k,d}, k = i - d + j
            k = i - d + j
            left  = 0 if j == 0 else (u - U[k]) / (U[k+d] - U[k]) * V[d-1][j-1]
            right = 0 if j == d else (U[k+d+1] - u) / (U[k+d+1] - U[k+1]) * V[d-1][j]
            V[d][j] = left + right
    return V
```

On a non-empty span none of the denominators used is zero (p. 70). The row V[p] holds the p + 1 values needed for evaluation; the lower rows are reused for derivatives.

**Point on a curve** (A3.1, p. 82). i = find_span; V = basis_table; C = Σ_{j=0}^{p} V[p][j] · P_{i−p+j}. Cost O(p²) plus the search.

**Derivatives up to order d** (the route of A3.3/A3.4, pp. 98–100). Input curve, u, d. Output C^{(0)}(u) … C^{(d)}(u). Cost O(p²) per call.

```
curve_derivs(curve, u, d):
    i = find_span(U, p, n, u); V = basis_table(U, p, i, u)
    D[0][j] = P[i-p+j] for j = 0..p                     # local derivative control points
    for k in 1..min(d, p):
        for j in 0..p-k:
            g = i - p + j                               # global index of P_g^(k)
            D[k][j] = (p-k+1) * (D[k-1][j+1] - D[k-1][j]) / (U[g+p+1] - U[g+k])
    for k in 0..min(d, p): Ck[k] = sum_j V[p-k][j] * D[k][j]      # degree p-k values on the same span
    for k in p+1..d: Ck[k] = 0
    return Ck
```

The degree p − k functions evaluated on the original U at span i are exactly the ones the derivative curve needs (index shift of Eq. 3.6). We checked this route against the direct basis-derivative route (A2.3, Eq. 2.10) on random cubic curves: they agree to rounding. Rational curves apply the same routine to the homogeneous points (note b).

**Single basis function** (A2.4, A2.5, pp. 74–78): only needed for tests or for fitting; the same triangle, restricted to one function, with explicit zero checks.

#### Numerical cautions

From the book:

1. Quotients 0/0 in Eqs. 2.5 and 2.10 are defined as 0 (pp. 51, 61). A direct implementation of Eq. 2.5 divides by zero at repeated knots; the triangular table avoids it on non-empty spans (p. 70).
2. The right end u = u_m is a special case: with half-open spans no span contains it; return span n (p. 68).
3. At a knot the algorithms return derivatives from the right. Derivatives from the left need a span search with intervals (u_i, u_{i+1}] (p. 78). Both are needed wherever continuity at a knot matters.
4. High degree single-segment curves are inefficient and numerically unstable (p. 47). Power basis evaluation is prone to round-off when coefficients differ greatly in size (p. 9); do not convert to power form for evaluation.
5. Misprints found while checking: the verification line for Eq. 2.10 with k = 1 on p. 61 prints a factor 2 where p is meant (the formula itself, with p!/(p − k)!, is right). Example Ex3.2 (p. 95) states the interior knots 2/5, 3/5, 3/5 but computes the Q_i with 1/3, 2/3, 2/3; the printed factors 9, 9/2, 9/2, 9/2, 9, 9 belong to the second knot vector. With the stated knots the factors are 15/2, 5, 5, 5, 15/2, 15/2.

Ours:

6. Files store knots as decimal text. Values meant to be equal (1/3 written twice with different rounding) create spans of length 1e−10 or less. Derivative control points divide by such differences (Eq. 3.8) and blow up; span search may land in them. Snap knots closer than a parameter tolerance eps_par (relative to b − a) to one value at import, then compare knots exactly.
7. Eqs. 3.7 and 3.9 assume a = 0, b = 1. STEP curves often use other ranges (for example arc-length-like parameters). Either keep the range and use the general form, or map linearly to [0, 1]; the linear map does not change control points (note c) but scales all derivatives by (b − a)^k.
8. Degree p = 1 is legal (a polyline); every formula above works with p = 1, and the second derivative is zero inside spans.

#### What it means for us

- The foundation module (topic 01) gets one NURBS curve type. Store: degree p ≥ 1, the full clamped knot vector (m + 1 = n + p + 2 values, end multiplicity exactly p + 1, interior multiplicity at most p), and homogeneous control points (w·x, w·y, w·z, w) with all w > 0. The homogeneous form is what every algorithm in chapters 2–5 works on (p. 124), and it makes evaluation, derivatives, insertion and splitting linear operations. This answers the "representation" part of Q-035 for native splines.
- Evaluation, span search and derivatives are small (O(p²)) and need no library; they belong in the kernel next to lines and arcs.
- Tangents for topic 11 (Yang 2002 needs a point and a tangent at any parameter): curve_derivs with d = 1, and d = 2 when curvature is needed. At knots with multiplicity p (C⁰ corners) evaluate both one-sided tangents; a corner in the spline must become a tangent break in the arc fitter, not a smoothed point.
- The strong convex hull property (P3.5) gives a cheap bounding box per span: the box of P_{i−p} … P_i. Use it for spatial indexing and for pruning in projection (note d).
- Validate at import: non-decreasing knots, multiplicities within limits, m = n + p + 1, finite coordinates, positive weights. Report and repair (snap knots, split at over-multiple knots) rather than evaluate garbage.

#### Test ideas

1. U = {0, 0, 0, 1, 2, 3, 4, 4, 5, 5, 5}, p = 2, u = 5/2: find_span returns 4; the non-zero values N_{2,2}, N_{3,2}, N_{4,2} are 1/8, 3/4, 1/8; first derivatives −1/2, 0, 1/2; second derivatives 1, −2, 1 (Ex2.3, Ex2.4, pp. 68–72). So C(5/2) = P_2/8 + 3P_3/4 + P_4/8 (p. 82).
2. Same U, u = 5: span 7 (= n), values (0, 0, 1), C(5) = P_7.
3. Partition of unity and non-negativity on random clamped knot vectors (degrees 1–5, with repeated interior knots): Σ V[p][j] = 1 within 1e−15, all values ≥ 0, derivative values sum to 0.
4. Derivatives against central finite differences (step 1e−6 relative) inside spans, and one-sided differences at knots, left and right.
5. Ex3.1 (p. 94): quadratic on {0, 0, 0, 2/5, 3/5, 1, 1, 1}: Q_0 = 5(P_1 − P_0), Q_1 = (10/3)(P_2 − P_1), Q_2 = (10/3)(P_3 − P_2), Q_3 = 5(P_4 − P_3).
6. Ex3.2 corrected: cubic on {0, 0, 0, 0, 2/5, 3/5, 3/5, 1, 1, 1, 1}: factors 15/2, 5, 5, 5, 15/2, 15/2; and on {0, 0, 0, 0, 1/3, 2/3, 2/3, 1, 1, 1, 1}: 9, 9/2, 9/2, 9/2, 9, 9 as printed.
7. Bézier cubic P = (0, 0), (0, 10), (10, 10), (10, 0) mm on {0 ×4, 1 ×4}: C(1/2) = (5, 7.5), C′(0) = (0, 30), C″(0) = (60, −60); the B-spline routines and de Casteljau agree.
8. Convex hull: for random curves and u in span i, C(u) lies inside the convex hull of P_{i−p} … P_i.
9. Knot snapping: a knot vector containing 0.3333333333 and 0.33333333333333 imports with one double knot, and the curve evaluates identically to the exact 1/3 version within 1e−9 mm.

### Piegl and Tiller 1997, chapter 4 and 7: NURBS curves, circles, arcs, ellipses and conics

**Source:** Les Piegl, Wayne Tiller, *The NURBS Book*, 2nd edition, Springer, Berlin Heidelberg 1997, ISBN 978-3-540-61545-3, doi:10.1007/978-3-642-59223-2. Chapter 4 "Rational B-spline Curves and Surfaces", sections 4.1–4.3 (pp. 117–128); chapter 7 "Conics and Circles" (pp. 281–331); section 6.4 "Reparameterization of NURBS Curves and Surfaces" (pp. 241–263) for weight normalisation.

**Read:** pp. 117–128, 281–331 and 241–263 in full; page images checked for pp. 125–126, 292–293, 312, 315–316, 323–325. **Class:** L.

#### Definitions and formulas

**NURBS curve (chapter 4).**

- Definition (Eq. 4.1, p. 117): C(u) = Σ N_{i,p}(u) w_i P_i / Σ N_{i,p}(u) w_i on a clamped U, with w_i > 0 assumed (p. 118). Rational basis R_{i,p} = N_{i,p} w_i / Σ_j N_{j,p} w_j (Eq. 4.2).
- Properties (pp. 118–120): the R_{i,p} are non-negative, sum to 1, local (zero outside [u_i, u_{i+p+1})), C^{p−k} at a knot of multiplicity k, and equal N_{i,p} when all weights are equal (P4.1–P4.7). The curve interpolates P_0 and P_n, is invariant under affine maps and also under perspective projection, satisfies the strong convex hull property (for u ∈ [u_i, u_{i+1}) inside the hull of P_{i−p} … P_i), is variation diminishing, and with no interior knots is a rational Bézier curve (P4.8–P4.13). Changing P_i or w_i affects only [u_i, u_{i+p+1}) (P4.14).
- Weight effect (p. 120, Eq. 4.4): raising w_i pulls C(u) toward P_i; for fixed u the point moves along a straight line through P_i as w_i runs from 0 to ∞.
- Homogeneous form (Eq. 4.5): Cʷ(u) = Σ N_{i,p}(u) P_iʷ with P_iʷ = (w_i x_i, w_i y_i, w_i z_i, w_i); C = Cʷ divided by its last coordinate. Evaluation (A4.1, p. 124) is the B-spline evaluation on Pʷ followed by the division. Example Ex4.1 (pp. 122–124): U = {0, 0, 0, 1, 2, 3, 3, 3}, w = (1, 4, 1, 1, 1), P = (0, 0), (1, 1), (3, 2), (4, 1), (5, −1) gives Cʷ(1) = (7/2, 3, 5/2), so C(1) = (7/5, 6/5).
- Derivatives (pp. 125–127). Write Cʷ = (A, w), so C = A/w. Then C′ = (A′ − w′ C)/w (Eq. 4.7), and in general, from Leibniz' rule, C^{(k)} = ( A^{(k)} − Σ_{i=1}^{k} binom(k, i) w^{(i)} C^{(k−i)} ) / w (Eq. 4.8). A^{(k)} and w^{(i)} come from the non-rational routines applied to Pʷ. Algorithm A4.2 is this recursion, O(d²) after the homogeneous derivatives.
- End tangents (Eqs. 4.9, 4.10, p. 126): C′(0) = p/u_{p+1} · (w_1/w_0) (P_1 − P_0), C′(1) = p/(1 − u_{m−p−1}) · (w_{n−1}/w_n)(P_n − P_{n−1}).
- Example Ex4.2 (p. 126): quarter circle P = (1, 0), (1, 1), (0, 1), w = (1, 1, 2), U = {0, 0, 0, 1, 1, 1}: C′(0) = (0, 2), C′(1) = (−1, 0), C″(0) = (−4, 0).

**Conics as rational quadratics (chapter 7).**

- Standard ellipse (Eq. 7.5) x²/a² + y²/b² = 1. The "maximum inscribed area" parameterisation (Eq. 7.15, p. 289) x = a cos u, y = b sin u: equally spaced u give the inscribed polygon of largest area. In 3D (Eq. 7.18, p. 290) C(u) = O + a cos u · X + b sin u · Y with orthonormal X, Y; the book notes these are the conic forms used by STEP.
- Quadratic rational Bézier arc (Eq. 7.21, p. 291): C(u) = [(1 − u)² w_0 P_0 + 2u(1 − u) w_1 P_1 + u² w_2 P_2] / [(1 − u)² w_0 + 2u(1 − u) w_1 + u² w_2]. It is always a conic: with S = P_0 − P_1, T = P_2 − P_1 and C = P_1 + α S + β T, the barycentric coordinates satisfy α β = (k/4)(1 − α − β)² (Eq. 7.26) with the conic shape factor k = w_0 w_2 / w_1² (Eq. 7.25, p. 292). Weight changes that keep k fixed change only the parameterisation.
- Normal parameterisation w_0 = w_2 = 1 (p. 293). Then |w_1| < 1 gives an ellipse, |w_1| = 1 a parabola, |w_1| > 1 a hyperbola; w_1 = 0 gives the chord P_0P_2; w_1 < 0 gives the complementary arc, and the convex hull property is lost.
- Shoulder point (Eqs. 7.29–7.31, p. 294): S = C(1/2) = M/(1 + w_1) + w_1 P_1/(1 + w_1), M the chord midpoint; the tangent at S is parallel to the chord, so S is the point of the arc farthest from the chord. With S = (1 − s) M + s P_1, s = w_1/(1 + w_1) and w_1 = s/(1 − s).
- Circular arc (Eq. 7.33, p. 295): for a sweep below 180°, P_0P_1P_2 is isosceles and w_1 = cos θ, where θ is the base angle ∠P_1P_0P_2, which equals half the sweep. So a 90° arc has w_1 = √2/2, a 120° arc w_1 = 1/2.
- Infinite control points (section 7.4, pp. 295–298): a homogeneous point (x, y, z, 0) acts as a direction; the semicircle of radius r is P_0ʷ = (r, 0, 1), P_1ʷ = (0, r, 0), P_2ʷ = (−r, 0, 1) (Ex7.1). A zero weight is different: P_iʷ = (0, 0, 0, 0) removes the point. The evaluation and insertion algorithms handle both, as long as not all weights are zero (p. 298).

**Circle constructions (section 7.5, pp. 298–309).**

- Nine-point square circle (Ex7.2): P = (1, 0), (1, 1), (0, 1), (−1, 1), (−1, 0), (−1, −1), (0, −1), (1, −1), (1, 0); w = (1, √2/2, 1, √2/2, 1, √2/2, 1, √2/2, 1); U = {0, 0, 0, 1/4, 1/4, 1/2, 1/2, 3/4, 3/4, 1, 1, 1}. Cʷ is only C⁰ at the double knots (a cusp in homogeneous space), but C is C¹: C′(1/4) = (−4√2, 0) from both sides (pp. 300–301).
- Seven-point triangle circle (Ex7.3): three 120° arcs, w_1 = 1/2, U = {0, 0, 0, 1/3, 1/3, 2/3, 2/3, 1, 1, 1}, P = (a, 1/2), (0, 2), (−a, 1/2), (−2a, −1), (0, −1), (2a, −1), (a, 1/2) with a = cos 30°. Looser hull, less even parameterisation.
- Negative weight repaired by knot insertion (Ex7.4, Ex7.5): a 240° arc with w_1 = −1/2, or a semicircle with an infinite control point, becomes a positive-weight curve by inserting u = 1/2 once. The semicircle becomes U = {0, 0, 0, 1/2, 1, 1, 1}, w = (1, 1/2, 1/2, 1), P = (1, 0), (1, 1), (−1, 1), (−1, 0). Two such halves give a seven-point square circle (Ex7.6) with U = {0, 0, 0, 1/4, 1/2, 1/2, 3/4, 1, 1, 1} and w = (1, 1/2, 1/2, 1, 1/2, 1/2, 1).
- General arc (A7.1, pp. 305–309): input centre O, orthonormal X, Y, radius r, start and end angle. Number of segments by sweep: up to 90° one, up to 180° two, up to 270° three, otherwise four; equal segments of sweep dθ, weight cos(dθ/2) on each middle point, middle point at the intersection of the end tangents, double interior knots at i/narcs. The result is C¹, has a tight hull and a good parameterisation (p. 306). A full circle cannot be a quadratic NURBS with positive weights and no double interior knot (p. 309).

**General conic arcs and ellipses (section 7.6, pp. 310–320).**

- Arc from P_0, T_0, P_2, T_2 and one more point P on the conic (A7.2, pp. 312–314): P_1 is the intersection of the end tangents; w_0 = w_2 = 1. Intersect the line P_1P with the chord to get Q; then a = √(|P_0Q|/|QP_2|) and u = a/(1 + a) (Eq. 7.38), and w_1 = [(1 − u)² (P − P_0)·(P_1 − P) + u² (P − P_2)·(P_1 − P)] / [2u(1 − u)|P_1 − P|²] (Eq. 7.39). If the end tangents are parallel, P_1 is infinite and Eq. 7.41 gives its length.
- Splitting at the shoulder point (Eqs. 7.42–7.47, pp. 315–316): with normal weights, Q_1 = (P_0 + w_1 P_1)/(1 + w_1), R_1 = (w_1 P_1 + P_2)/(1 + w_1), S = (Q_1 + R_1)/2, and after renormalising each half to end weights 1 the new middle weights are w_{q1} = w_{r1} = √((1 + w_1)/2). For a circle this is the half-angle rule: cos(θ/2) = √((1 + cos θ)/2).
- Segment count for an open conic (A7.3, p. 317): w_1 ≤ −1 is rejected; w_1 ≥ 1 (parabola, hyperbola) one segment; an ellipse with w_1 > 0 and ∠P_0P_1P_2 > 60° one segment; w_1 < 0 and that angle > 90° four segments; otherwise two.
- Full ellipse with known centre C, unit axes U, V and radii r_1, r_2 (p. 320): the nine-point rectangle Q_0 = C + r_1U, Q_1 = Q_0 + r_2V, Q_2 = C + r_2V, Q_3 = Q_2 − r_1U, Q_4 = C − r_1U, Q_5 = Q_4 − r_2V, Q_6 = C − r_2V, Q_7 = Q_6 + r_1U, Q_8 = Q_0, with the weights and knots of the nine-point circle. An affine map does not change weights (p. 317).
- Recognising a conic from a rational quadratic Bézier (Lee 1987 via pp. 322–325), all w_i > 0, not degenerate: S = P_0 − P_1, T = P_2 − P_1, k = w_0 w_2/w_1², ε = k/(2(k − 1)), α = |S|², β = S·T, γ = |T|², δ = αγ − β², η = α + γ − 2β. Centre of an ellipse or hyperbola: P_1 + ε(S + T) (Eq. 7.61). Let λ_1 ≤ λ_2 solve 2δλ² − (kη + 4β)λ + 2(k − 1) = 0; for an ellipse the radii are r_1 = √(ε/λ_1), r_2 = √(ε/λ_2) (Eq. 7.62). Eq. 7.64 gives two points on the major axis. A quadratic NURBS with several segments is one conic only if every segment gives the same characteristics; equal shape factors are not enough (p. 322).
- Higher degree (section 7.8): the semicircle as a cubic without interior knots, P = (1, 0), (1, 2), (−1, 2), (−1, 0), w = (1, 1/3, 1/3, 1) (Ex7.7); a full circle as one quintic Bézier with positive weights exists (Ex7.10), a quartic one does not (p. 330).

**Weights and reparameterisation (section 6.4).**

- A linear rational change of parameter s = (αu + β)/(γu + δ) changes neither the control points nor the curve, only the knots (s_i = g(u_i)) and the weights (Eqs. 6.56, 6.57, p. 256, after Lee and Lucian 1991): w̄_i = w_i Π_{j=1}^{p} λ(s_{i+j}) with λ(s) = γs − α, or w̄_i = w_i / Π_{j=1}^{p} μ(u_{i+j}) with μ(u) = γu + δ, each up to a common factor. It requires αδ − γβ > 0 and no zero of μ or λ in the range.
- Equal end weights (Eq. 6.58, p. 260): to map [a, b] onto [c, d] and make w̄_0 = w̄_n, use s = [ᵖ√w_0 (b − u) c + ᵖ√w_n (u − a) d] / [ᵖ√w_0 (b − u) + ᵖ√w_n (u − a)] (p-th roots).
- Shape invariants (Eqs. 6.59–6.62, pp. 261–262): for a rational Bézier of degree p the ratios w_{i−1} w_{i+1}/w_i² (i = 1 … p − 1) fix the shape; for the conic this is the shape factor (circle quarter: (1)(2)/1² = (1)(1)/(√2/2)² = 2).

#### Algorithms

**Rational point and derivatives.** Run curve_derivs (note a) on the homogeneous points to get A^{(k)}, w^{(k)}, then apply Eq. 4.8 for k = 0 … d. Cost O(p²) + O(d²).

**Circular arc to NURBS** (our restatement of A7.1, angles in radians; output degree 2, 2·narcs + 1 points).

```
arc_to_nurbs(O, X, Y, r, t0, sweep):              # sweep in (0, 2π]; for clockwise arcs use Y := -Y
    narcs = ceil(sweep / (π/2))                   # 1..4
    dt = sweep / narcs;  c = cos(dt/2)
    pts = [O + r(cos t0 X + sin t0 Y)];  wts = [1]
    for k in 1..narcs:
        tm = t0 + (k - 1/2) dt;  te = t0 + k dt
        pts += [O + (r/c)(cos tm X + sin tm Y), O + r(cos te X + sin te Y)]
        wts += [c, 1]
    knots = [0,0,0] + [k/narcs, k/narcs for k in 1..narcs-1] + [1,1,1]
```

The book's version intersects the tangent lines instead of placing the middle point at distance r/cos(dθ/2) on the bisector; both give the same point. Ellipse arc from eccentric angle t0 to t1: build the unit-circle arc and apply x ↦ C + a·x·U + b·y·V to the control points; weights stay.

**Rational Bézier standard form** (ours, from the substitution u = s/(s + c(1 − s)), consistent with Eqs. 6.56–6.59): for degree p and weights w_0 … w_p, the weights w̄_i = w_i / (w_0^{(p−i)/p} w_p^{i/p}) give the same curve with w̄_0 = w̄_p = 1. For p = 2 this is w̄_1 = w_1/√(w_0 w_2): the quarter circle (1, 1, 2) becomes (1, √2/2, 1).

**Parameter to angle on a circular segment** (ours, checked numerically). For a quadratic arc in normal form with half-sweep φ (w_1 = cos φ), the angle ψ of C(t) measured from the bisector satisfies tan(ψ/2) = (2t − 1) tan(φ/2), so t = [1 + tan(ψ/2)/tan(φ/2)]/2. This inverts points on NURBS circles and ellipses (eccentric angle) in closed form.

**Recognising a circular arc** (ours, from Eqs. 7.25 and 7.33). Decompose into Bézier segments (note c); normalise each to w_0 = w_2 = 1; require |P_1 − P_0| = |P_2 − P_1| within tol and w_1 = cos θ within a small angle tolerance, θ = ∠P_1P_0P_2. Then r = (|P_2 − P_0|/2)/sin θ and the centre is M − r cos θ · (P_1 − M)/|P_1 − M|. Consecutive segments merge into one arc if centre and radius agree within tol.

#### Numerical cautions

1. Negative weights and infinite control points are legal in the book's mathematics but break the convex hull property, and a negative weight can make the denominator vanish (p. 302). STEP and IGES allow only positive weights (pp. 582, 585); reject w ≤ 0 at import.
2. With zero weights allowed, knot removal can create zero or negative weights (p. 186); guard any operation that creates weights.
3. The NURBS circle parameter is not the angle: in Ex1.14 (p. 34) C(1/2) = (3/5, 4/5) for weights (1, 1, 2). Code that assumes equal parameter steps give equal angles is wrong.
4. For a 180° arc P_1 is at infinity; A7.2 branches on the parallel-tangent case (p. 312). Any "intersect tangents" code needs that branch.
5. Division by w in Eq. 4.8 is safe only with w > 0. Ours: weights that differ by many orders of magnitude amplify rounding in that division and in the flattening bound of note e (it divides by the smallest weight). Normalise at import (standard form, or divide all weights by the largest) and report curves whose weight ratio exceeds a limit (for example 1e6).

#### What it means for us

- Q-035, native curves (D-034): keep lines and circular arcs analytic, and keep the NURBS type of note a. For ellipses we recommend an analytic ellipse-arc type (centre, unit major axis, a, b, start and end eccentric angle, sense): DXF ELLIPSE and STEP ellipse carry exactly this form (Eq. 7.18), its natural parameter is the eccentric angle, and it converts exactly to NURBS by the circle construction plus an affine map whenever a generic NURBS algorithm is needed. Register the choice as a decision.
- Arcs that arrive as rational quadratic NURBS (common in STEP and DXF SPLINE data) should be recognised and turned into native arcs, because release 1 outputs G2/G3 (D-023). The recognition recipe above needs a tolerance; tie it to the flattening share.
- The circle and ellipse constructions give reference geometry for tests of every NURBS routine: evaluation must reproduce the radius to rounding.
- Topic 21: when converting a DXF ELLIPSE or STEP ellipse to NURBS use the nine-point or arc construction (double knots, weights cos(dθ/2)); do not approximate.

#### Test ideas

1. Quarter circle with w = (1, √2/2, 1): |C(u)| = 1 within 3e−16 on 1001 samples; C(1/2) = (√2/2, √2/2); C′(0) = (0, √2); C″(0) = (−2, 2√2 − 2).
2. Quarter circle with w = (1, 1, 2): C(1/2) = (3/5, 4/5), C′(0) = (0, 2), C′(1) = (−1, 0), C″(0) = (−4, 0), C″(1) = (1, −1) (our computation of the book's exercise); curvature |C′ × C″|/|C′|³ = 1 at both ends. The standard-form formula turns (1, 1, 2) into (1, √2/2, 1).
3. Ex4.1: C(1) = (7/5, 6/5).
4. Nine-point circle, seven-point square circle, seven-point triangle circle, the four-point semicircle, the four-point 240° arc (w = (1, 1/4, 1/4, 1), P = (a, 1/2), (2a, −1), (−2a, −1), (−a, 1/2)) and the cubic semicircle: all radii 1 within 4e−16; nine-point circle C′(1/4) = (−4√2, 0) from both sides.
5. arc_to_nurbs with r = 2 mm for (10°, 100°), (30°, 170°), (20°, 250°), (40°, 330°), (0°, 360°): 3, 5, 7, 9, 9 control points; weights cos 45°, cos 35°, cos(38.33°), cos(36.25°), cos 45°; end point exactly on the circle at the end angle.
6. Angle map: on the quarter circle, t = 0.1, 0.3, 0.77 give tan(ψ/2) = −0.33137, −0.16569, 0.22368 (= (2t − 1) tan(π/8)).
7. Conic from P_0, T_0, P_2, T_2, P: quarter ellipse a = 50, b = 30 mm from (50, 0) to (0, 30), P at eccentric angle 30°: Eq. 7.39 returns w_1 = √2/2 within 1e−12.
8. Lee's formulas on a rotated ellipse arc (a = 50, b = 30, rotation 0.4 rad, centre (10, −5), eccentric angles 0.2 to 1.5): centre (10, −5) and radii 50 and 30 within 1e−12; the two Eq. 7.64 points lie on the major axis.
9. Split at the shoulder of a 120° arc (w_1 = 1/2): new middle weights √(3/4) = cos 30°.
10. Equal-end-weight reparameterisation (Eq. 6.58) on the book's cubic, U = {0, 0, 0, 0, 3/10, 7/10, 1, 1, 1, 1}, w = (2, 8, 3, 4, 2, 5), [c, d] = [1/10, 4/5]: new knots {0.1 ×4, 0.357, 0.632, 0.8 ×4}, new weights (1, 3.613, 1.084, 1.065, 0.434, 1), curve unchanged within 1e−13 (matches p. 261 to the printed digits).
11. Circle recognition: a quadratic NURBS built by arc_to_nurbs, rotated and translated, is recognised with centre and radius within 1e−9 mm; the rational quadratic of test 7 (an ellipse) is not.

### Piegl and Tiller 1997, chapter 5: knot insertion, splitting, Bézier decomposition and knot removal

**Source:** Les Piegl, Wayne Tiller, *The NURBS Book*, 2nd edition, Springer, Berlin Heidelberg 1997, ISBN 978-3-540-61545-3, doi:10.1007/978-3-642-59223-2. Chapter 5 "Fundamental Geometric Algorithms", sections 5.1–5.4 (pp. 141–188), with sections 5.5–5.6 (pp. 188–227) skimmed; section 6.4 (linear reparameterisation, pp. 245–251) and section 6.5 "Curve and Surface Reversal" (pp. 263–265).

**Read:** pp. 141–188 in full (curve parts; surface algorithms only noted); pp. 188–227 skimmed for the degree elevation and reduction formulas; pp. 245–251 and 263–265 in full. Page images checked for pp. 143–144, 149, 154, 182–184. **Class:** L.

All operations below act on homogeneous control points Pʷ (p. 141 onward); for rational curves never apply them to the Euclidean points.

#### Definitions and formulas

**Knot insertion** (section 5.2). Inserting ū ∈ [u_k, u_{k+1}) once changes only the basis, not the curve, geometrically or in parameter (p. 142). The new control points (Eqs. 5.10, 5.11, p. 143–144) are

- Q_i = P_i for i ≤ k − p,
- Q_i = α_i P_i + (1 − α_i) P_{i−1} with α_i = (ū − u_i)/(u_{i+p} − u_i) for k − p + 1 ≤ i ≤ k,
- Q_i = P_{i−1} for i ≥ k + 1.

Only p new points are computed; each is a convex combination, so insertion is numerically benign.

- Geometric reading (Eqs. 5.12–5.14, pp. 146–147): leg P_{i−1}P_i (measured in 4D) is divided in the ratios of the knot spans [u_{i+j}, u_{i+j+1}) to [u_i, u_{i+p}); inserting ū of existing multiplicity s cuts the corners at P_{k−p+1} … P_{k−s−1} and creates p − s new points.
- Inserting r times at once (Eq. 5.15, p. 149), with 0 ≤ s = existing multiplicity and r + s ≤ p: Q_{i,r} = α_{i,r} Q_{i,r−1} + (1 − α_{i,r}) Q_{i−1,r−1}, Q_{i,0} = P_i, and α_{i,r} = 1 for i ≤ k − p + r − 1, (ū − u_i)/(u_{i+p−r+1} − u_i) for k − p + r ≤ i ≤ k − s, 0 for i ≥ k − s + 1. The kept points are read around the resulting triangle; p − s + r − 1 new points replace p − s − 1 old ones starting at index k − p + 1 (Eqs. 5.16–5.18). Interior multiplicity above p makes no practical sense (p. 149).
- Uses (p. 142, 151–154): splitting, evaluation by "corner cutting" (insert ū p − s times; the last new point is C(ū); the end-derivative formulas then give one-sided derivatives), adding a control point for shape editing, and extracting subcurves.
- Inverse knot insertion (Eqs. 5.19–5.21, p. 154): to make a chosen point Q on leg P_{i−1}P_i a control point, s = w_{i−1}|Q − P_{i−1}| / (w_{i−1}|Q − P_{i−1}| + w_i|P_i − Q|) and ū = u_i + s (u_{i+p} − u_i).

**Knot refinement** (section 5.3, pp. 162–168). Insert a sorted list X = {x_0 … x_r} (each value repeated by its desired multiplicity, u_0 < x_j < u_m) in one pass. Control points P_0 … P_{a−p} and P_{b−1} … P_n are unchanged, where a and b are the spans of x_0 and x_r (b taken one higher); the rest is computed by working backwards through the merged knot vector, one insertion at a time, overwriting in place (Boehm and Prautzsch; A5.4). Applications: Bézier decomposition, merging knot vectors of several curves to a common one, and refining the control polygon toward the curve (it converges to the curve in the limit, p. 163, with no rate given).

**Bézier decomposition** (pp. 168–176). Insert every interior knot until its multiplicity is p. The result has p·(number of non-empty spans) + 1 control points; segment j uses points j·p … j·p + p and is a (rational) Bézier curve on its span. The book's A5.6 does this left to right in one sweep and saves work by two facts (Eq. 5.22 and p. 172): while filling the knot u_b of original multiplicity s, all alphas share the numerator u_b − u_a, and they are constant along diagonals of the insertion triangle, so only p − s of them are computed per knot. Converting to Bézier form is the first step of exporting to other spline forms and of the on-the-fly display pipeline (p. 176).

**Knot removal** (section 5.4, pp. 179–188). A knot u_r of multiplicity s is t times removable if the curve is C^{p−s+t} there in homogeneous space (p. 180); continuity of the projected curve is not enough. Removal is knot insertion run backwards. For one removal (Eq. 5.28, p. 183), with α_k = (u − u_k)/(u_{k+p+1} − u_k):

- P¹_i = (P⁰_i − (1 − α_i) P¹_{i−1}) / α_i for r − p ≤ i ≤ (2r − p − s − 1)/2,
- P¹_j = (P⁰_j − α_j P¹_{j+1}) / (1 − α_j) for (2r − p − s + 2)/2 ≤ j ≤ r − s,

starting from the unchanged neighbours P¹_{r−p−1} = P⁰_{r−p−1} and P¹_{r−s+1} = P⁰_{r−s+1}. There are p − s + 1 equations for p − s unknowns. Work inward from both ends. If the count is even, the last point is computed twice and the two values must agree within the tolerance; if odd, substitute the two innermost new points into the middle equation and compare with the old point (p. 183). The t-th removal of the same knot uses Eq. 5.29 (p. 184): index ranges r − p − t + 1 ≤ i ≤ (2r − p − s − t)/2 and (2r − p − s + t + 1)/2 ≤ j ≤ r − s + t − 1, with α_i = (u − u_i)/(u_{i+p+t} − u_i) and α_j = (u − u_{j−t+1})/(u_{j+p+1} − u_{j−t+1}).

- Meaning of the tolerance TOL (after Tiller 1992, p. 185): for a non-rational curve one removal moves the curve by less than TOL everywhere. For a rational curve the Euclidean deviation is below TOL(1 + |P|_max)/w_min, with w_min the smallest weight and |P|_max the largest distance of the curve from the origin; to guarantee a deviation d, use TOL = d·w_min/(1 + |P|_max) (Eq. 5.30). Both bounds come from the convex hull property.
- Removal can produce zero or negative weights; check before accepting (p. 186).
- Uses (pp. 180–181): power basis or Bézier input converted to B-spline form, cleaning up after editing, and joining curves (make degrees equal, join with multiplicity-p knots, remove what the continuity allows).

**Degree elevation and reduction** (sections 5.5–5.6, skimmed). Elevating p → p + 1 raises every interior multiplicity by one (Eqs. 5.32–5.33). On a Bézier segment (Eq. 5.35, p. 204): Q_i = (1 − α_i) P_i + α_i P_{i−1} with α_i = i/(p + 1), i = 0 … p + 1; by t degrees at once (Eq. 5.36, p. 205): Q_i = Σ_{j=max(0,i−t)}^{min(p,i)} binom(p, j) binom(t, i − j) P_j / binom(p + t, i). The B-spline algorithm (A5.9) decomposes, elevates each segment and removes the extra knots. Degree reduction is approximate in general and carries error bounds (Eqs. 5.43–5.46, p. 221); not needed for release 1.

**Reparameterisation and reversal** (sections 6.4–6.5). A linear map u = αs + β changes only the knots, s_i = (u_i − β)/α; control points and weights stay (Eqs. 6.45–6.49, 6.53, p. 250). Reversal (Eqs. 6.63–6.67, p. 263–264): the new knots are s_i = a + b − u_{m−i} (for the interior, s_{m−p−i} = −u_{p+i} + a + b) and the control points are taken in reverse order, Q_i = P_{n−i}; weights reverse with them. Example: U = {0, 0, 0, 1, 3, 6, 6, 8, 8, 8} reverses to {0, 0, 0, 2, 2, 5, 7, 8, 8, 8}.

**Clamping** (chapter 12, p. 576). An unclamped curve is clamped by inserting u_p and u_{m−p} until each has multiplicity p and dropping the knots and control points outside [u_p, u_{m−p}]; Eq. 5.15 works unchanged as long as no knot index outside 0 … m is used. The same subcurve extraction handles IGES start and end parameters (note e). After both insertions, with a the first index of u_p and b the first index of u_{m−p} in the new vector, the clamped curve has knots [u_p] + Ū[a … b + p − 1] + [u_{m−p}] and points Q_{a−1} … Q_{b−1} (ours, checked on test 9).

#### Algorithms

Our pseudocode. The book's listings are A5.1 (insertion), A5.2 (corner cutting), A5.4 (refinement), A5.6 (decomposition), A5.8 (removal).

**Insert ū r times** (Eq. 5.15 written as a triangle of columns, read in the order described on p. 150). Input p, U, Pʷ (n + 1 points), ū, r with r + s ≤ p. Output Ū, Qʷ (n + r + 1 points). Cost O(r·p) arithmetic plus O(n) copying.

```
insert_knot(p, U, Pw, ub, r):
    k = span with U[k] <= ub < U[k+1];  s = multiplicity of ub in U   # s = 0 if ub is not a knot
    T[0][i] = Pw[i]                      for i = k-p .. k-s         # column 0: the points that can change
    for j in 1..r:                                                  # column j = after j insertions
        for i in k-p+j .. k-s:
            a = (ub - U[i]) / (U[i+p-j+1] - U[i])                  # alpha_{i,j} of Eq. 5.15
            T[j][i] = a*T[j-1][i] + (1-a)*T[j-1][i-1]
    Q = Pw[0 .. k-p]
      + [T[1][k-p+1], T[2][k-p+2], ..., T[r][k-p+r]]               # top edge of the triangle
      + [T[r][i] for i in k-p+r+1 .. k-s]                          # rest of the last column
      + [T[r-1][k-s], T[r-2][k-s], ..., T[1][k-s]]                 # bottom edge, read backwards
      + Pw[k-s .. n]
    Ubar = U[0..k] + [ub]*r + U[k+1..m]
    return Ubar, Q
```

We checked this form against a direct implementation of the book's method on 356 random rational curves (degree 1–5, repeated knots, r up to p − s): identical control points within 3e−15 and identical curves.

**Split at ū** (ours, from pp. 151–152). Insert ū until its multiplicity is p (skip if already ≥ p). Let k be the index of the last copy of ū in the new knot vector. Then C(ū) = Q_{k−p}; the left curve has knots Ū[0 … k] plus one more ū and points Q_0 … Q_{k−p}; the right curve has knots ū plus Ū[k−p+1 … end] and points Q_{k−p} … Q_end. Both are clamped and reproduce the original on their ranges. Splitting at a parameter where multiplicity is already p needs no arithmetic.

**Bézier decomposition** (ours, simple form). For every distinct interior knot with multiplicity s < p, insert it p − s times (refinement in one pass, or repeated insert_knot from right to left so indices stay valid). Output the segments as described above. Cost O(n·p²) for the simple form; the single-sweep form of A5.6 is O(n·p) per coordinate and needs only p + 1 points of storage per segment, which suits streaming (flattening, export).

**Remove a knot once** (ours, Eq. 5.28). Input p, U, Pʷ, index r with U[r] = u ≠ U[r+1], multiplicity s, tolerance TOL (in homogeneous units, see Eq. 5.30). Output new curve or "not removable". Cost O(p).

```
remove_knot_once(p, U, Pw, r, TOL):
    u = U[r];  s = multiplicity of u                     # r is the last index holding u
    i = r - p;  j = r - s
    T[i-1] = Pw[i-1];  T[j+1] = Pw[j+1]
    while j - i > 0:
        ai = (u - U[i]) / (U[i+p+1] - U[i]);  aj = (u - U[j]) / (U[j+p+1] - U[j])
        T[i] = (Pw[i] - (1-ai)*T[i-1]) / ai
        T[j] = (Pw[j] - aj*T[j+1]) / (1-aj)
        i += 1;  j -= 1
    if j - i < 0:  ok = |T[i-1] - T[j+1]| <= TOL                         # even count: same point twice
    else:          ai = (u - U[i]) / (U[i+p+1] - U[i])
                   ok = |Pw[i] - (ai*T[i+1] + (1-ai)*T[i-1])| <= TOL     # odd count: check the middle
    if not ok or any new weight <= 0: return NOT_REMOVABLE
    new points = Pw[0..r-p-1] + T[r-p..i-1] + (T[j+2..r-s] if j - i < 0 else T[j+1..r-s]) + Pw[r-s+1..n]
    new knots  = U without U[r]
```

In the even case T[i − 1] and T[j + 1] are two estimates of the same new point; keep one (or their mean). Repeating the call on the result (new r, s one lower) gives the same curve as Eq. 5.29, which writes the t-th removal in the original indexing. We checked it: inserting a knot once or twice into a random rational cubic and removing it again restores the control points to 2e−15.

#### Numerical cautions

From the book:

1. Insertion beyond multiplicity p is not allowed (r + s ≤ p, p. 149); IGES data may contain it (note e), so split such curves first.
2. Knot removal is over-determined and must be decided with a tolerance (p. 183); for rational curves the tolerance on homogeneous points must be scaled by Eq. 5.30, which needs bounds on w_min and |P|_max (take them from the control points).
3. Removal may create zero or negative weights (p. 186).
4. Distances for the tolerance test are 4D distances with the weight treated as a coordinate (p. 184).

Ours:

5. Knot removal divides by α_i and 1 − α_j, which can be small; errors grow along the inward sweep. Accept a removal only after checking the new curve against the old one at sample points or with the bound of note e.
6. The Eq. 5.30 bound depends on the distance from the origin. Translate the curve so the origin is near it (for example at the centre of its control-point box) before removing knots with a tolerance, then translate back.
7. Splitting and decomposition create exact copies of the shared end point in both parts; keep them bit-identical (copy, do not recompute) so chains stay closed (topic 21 chaining).
8. Reversal must reverse weights with the points; forgetting it gives a different curve with the right end points.

#### What it means for us

- The foundation module needs from this chapter: insert_knot, split, Bézier decomposition, reverse, subcurve extraction (split twice), and clamping of unclamped input. These are enough for trimming spline edges at intersections, for per-span flattening (note e), for exporting to controllers that accept only Bézier or low-degree splines (A12.2, note e) and for the arc recognition of note b.
- Knot removal is not needed in release 1. It becomes useful when curves are joined (a chain of DXF splines into one curve) or when fitted curves are simplified; mark it as later.
- Degree elevation is needed only to join curves of different degree into one NURBS; release 1 can keep chains of separate curves instead.
- Topic 21: IGES start and end parameters and STEP trimmed curves become one subcurve extraction at import, so the model never carries hidden trimming parameters.

#### Test ideas

1. Ex5.1 (p. 144): p = 3, U = {0, 0, 0, 0, 1, 2, 3, 4, 5, 5, 5, 5}, insert 5/2: α_3 = 5/6, α_4 = 1/2, α_5 = 1/6, so Q_3 = (5/6)P_3 + (1/6)P_2, Q_4 = (1/2)P_4 + (1/2)P_3, Q_5 = (1/6)P_5 + (5/6)P_4; Q_0 … Q_2 = P_0 … P_2 and Q_6 … Q_8 = P_5 … P_7.
2. Ex5.2: same curve, insert the existing knot 2: α_3 = 2/3, α_4 = 1/3, α_5 = 0, so Q_3 = (2/3)P_3 + (1/3)P_2, Q_4 = (1/3)P_4 + (2/3)P_3, Q_5 = P_4.
3. Invariance: after any insertion or refinement the curve is unchanged at 1000 parameters within 1e−12 relative, for random rational curves of degree 1–5.
4. Split a random rational cubic on {0, 0, 0, 0, 0.2, 0.5, 0.7, 1, 1, 1, 1} at 0.37: left knots {0 ×4, 0.2, 0.37 ×4}, right knots {0.37 ×4, 0.5, 0.7, 1 ×4}; both halves match the original on their ranges within 1e−14; the shared point equals C(0.37).
5. Decomposition of the same curve: 4 Bézier segments on [0, 0.2], [0.2, 0.5], [0.5, 0.7], [0.7, 1], 13 control points, each segment equal to the curve within 1e−14.
6. Ex7.5 by insertion: the semicircle with an infinite middle point, P_0ʷ = (1, 0, 1), P_1ʷ = (0, 1, 0), P_2ʷ = (−1, 0, 1), insert 1/2 once: Q_1ʷ = (1/2, 1/2, 1/2), Q_2ʷ = (−1/2, 1/2, 1/2), i.e. points (1, 1), (−1, 1) with weight 1/2 (p. 304).
7. Round trip: insert a knot once and twice, remove it the same number of times: control points restored within 1e−14; removing an original knot of a generic curve is refused.
8. Reversal: U = {0, 0, 0, 1, 3, 6, 6, 8, 8, 8} gives {0, 0, 0, 2, 2, 5, 7, 8, 8, 8}; C_rev(s) = C(a + b − s) for all s.
9. Clamping an unclamped uniform cubic (knots 0 … 11, 8 control points with the first three repeated at the end) at u_3 = 3 and u_8 = 8 gives a closed clamped curve equal to the original on [3, 8].

### Piegl and Tiller 1997, chapter 6: point inversion, projection and tangents of curves

**Source:** Les Piegl, Wayne Tiller, *The NURBS Book*, 2nd edition, Springer, Berlin Heidelberg 1997, ISBN 978-3-540-61545-3, doi:10.1007/978-3-642-59223-2. Chapter 6 "Advanced Geometric Algorithms", section 6.1 "Point Inversion and Projection for Curves and Surfaces" (pp. 229–234) and section 6.3 "Transformations and Projections of Curves and Surfaces" (pp. 236–241); derivative material from sections 3.3 and 4.3 (pp. 91–100, 125–127).

**Read:** pp. 229–241 in full (surface parts only noted); pp. 241–279 skimmed for anything on curve bounds (none found). Page images checked for pp. 230–232. **Class:** L.

#### Definitions and formulas

- **Point inversion** (p. 229): given P assumed on C, find u with C(u) = P. **Point projection** (p. 230): find u minimising |C(u) − P| for any P. The book solves both the same way.
- **Closed form is possible only for p ≤ 4** (pp. 229–230): isolate candidate spans with the convex hull, convert them to power form, solve the three polynomial equations of Eq. 6.2 (for p = 2: w_2(x_2 − x)u² + w_1(x_1 − x)u + w_0(x_0 − x) = 0 and likewise in y and z) and look for a common root. The book advises against it: no closed form above degree 4, unreliable for p = 3 and 4, the three roots never agree exactly, and the code is involved.
- **Newton on the foot-point condition** (Eq. 6.3, p. 230): the distance is stationary where f(u) = C′(u)·(C(u) − P) = 0. Iterate u_{i+1} = u_i − f(u_i)/f′(u_i) with f′(u) = C″(u)·(C(u) − P) + |C′(u)|².
- **Start value** (p. 230): if P is known to lie on the curve, keep only the spans whose control-point convex hull can contain it; otherwise use all spans. Evaluate n equally spaced points per candidate span and start from the closest one. n is chosen heuristically; the book stresses that a good start value is essential for reliable convergence.
- **Stopping tests** (Eq. 6.4, p. 231), with ε_1 a Euclidean distance and ε_2 a zero-cosine tolerance, checked in this order: (1) point coincidence |C(u_i) − P| ≤ ε_1; (2) zero cosine |C′(u_i)·(C(u_i) − P)| / (|C′(u_i)| |C(u_i) − P|) ≤ ε_2. If neither holds, take the Newton step, then (3) keep u in range: for an open curve clamp to [a, b]; for a closed curve wrap, u ← b − (a − u) below a and u ← a + (u − b) above b; and (4) stop if |(u_{i+1} − u_i) C′(u_i)| ≤ ε_1, the parameter no longer moves (for example when the foot point is off the end). Stop when (1), (2) or (4) holds. The book gives no values for ε_1, ε_2 or the iteration limit.
- **Transformations** (section 6.3): all affine maps and parallel projections act on the Euclidean control points with unchanged weights (P4.9, p. 236). Parallel projection of a point onto the plane (Q, N) along W (Eq. 6.14): P̄ = P + [N·(Q − P)/(N·W)] W. Perspective projection needs new points and new weights (Eqs. 6.17, 6.18); in 4D all of these are one 4×4 matrix on Pʷ (Eq. 6.22).
- **Derivatives for tangents** (from notes a and b): C′ from Eq. 3.4 or 4.7; unit tangent T = C′/|C′|. At a knot the standard routines give the derivative from the right; from the left use the span search on (u_i, u_{i+1}] (p. 78). A curve can be C¹ with C′ = 0 at a double control point (P3.11, p. 90): a visible cusp.

#### Algorithms

**Closest point on a curve, safeguarded** (ours, built on Eqs. 6.3–6.4). Input curve C on [a, b], point P, eps_len, eps_par, sampling count q per span (default 2p + 2). Output u*, C(u*), distance. Cost O(spans·q·p²) for sampling plus a few Newton steps per candidate.

```
closest_point(C, P):
    samples = q + 1 equally spaced parameters per non-empty span, shared span ends, plus b
    d2[k] = |C(u_k) - P|^2
    best = (+inf, none)
    for each k where d2[k] is a local minimum of the sample sequence (ends included):
        lo = u_{k-1} (or u_k at the start), hi = u_{k+1} (or u_k at the end)
        add candidate u_k
        if f(lo) < 0 < f(hi):                              # a minimum is bracketed inside (lo, hi)
            u = u_k
            repeat up to 60 times:
                evaluate C, C', C'' at u;  r = C - P;  f = C'.r;  fp = C''.r + |C'|^2
                if |r| <= eps_len or |f| <= eps_ang * |C'| * |r|: break      # tests (1), (2)
                if f < 0: lo = u else: hi = u                              # keep the bracket
                un = u - f/fp if fp > 0 else none
                if un is none or not (lo < un < hi): un = (lo + hi)/2       # bisection fallback
                if |un - u| * |C'| <= eps_len: u = un; break                # test (4)
                u = un
            add candidate u
    return the candidate with the smallest |C(u) - P|
```

For a closed curve, treat the sample sequence as cyclic and wrap the bracket across the seam (test 3 of the book). Pruning (ours): skip a span when the distance from P to the bounding box of its control points exceeds the best distance found so far (strong convex hull property).

**Start values with a guarantee** (ours). Flatten the curve with a proven error e (note e). Let d_poly be the distance from P to the polyline; the true distance lies within e of it, because the polyline and the curve are within Hausdorff distance e of each other. Every polyline segment within d_poly + 2e of P marks a parameter interval that may hold the global minimum; run the safeguarded Newton on each. This cannot miss a narrow minimum that plain sampling might skip.

**Point inversion** (book case, ours in detail). Run closest_point; accept u* as the inverse if the distance is ≤ eps_len (or the operation's tolerance), otherwise report "not on curve". For points known to be end points of a trimmed edge, test the curve ends first.

**Tangent and curvature at u** (standard differential geometry, not from these chapters). T = C′/|C′|; curvature κ = |C′ × C″|/|C′|³ (in 2D use the scalar cross product; the sign gives the turning direction). If |C′|·(b − a) < eps_len (the curve would move less than eps_len over its whole range at this speed), use the first non-zero higher derivative for the direction, and report a possible cusp.

**Closed forms for the analytic types** (ours). Circle: the foot point is the centre plus r times the unit vector towards P, if that angle lies in the arc; otherwise the nearer end. On a NURBS circle segment the parameter follows from tan(ψ/2) = (2t − 1) tan(φ/2) (note b). Ellipse: Newton on the eccentric angle t with f(t) = C′(t)·(C(t) − P), start t_0 = atan2(a·y, b·x) in the ellipse frame, safeguarded as above.

#### Numerical cautions

From the book:

1. Newton needs a good start value (p. 230); the heuristic sample count is the weak point.
2. For open curves the parameter must be clamped to [a, b] and for closed curves wrapped (p. 232).
3. Test (4) catches the case where the foot point lies beyond the curve end; the minimum is then at the end point.

Ours, found while checking:

4. f(u) = 0 also at distance maxima. Plain Newton from the nearest sample can climb to a maximum. Example: the quarter circle P = (1, 0), (1, 1), (0, 1), w = (1, √2/2, 1), and the point (−1, −0.5). The nearest sample is u = 1 (distance 1.803). The unguarded iteration of Eq. 6.3 with the book's tests converges to u = 0.304, C = (0.894, 0.447), distance 2.118, which is the farthest point, and its tests (1) to (4) accept it. The safeguarded version returns u = 1.
5. f′(u) can be zero or negative. At the centre of a circular arc every point is equidistant: f ≡ 0 and f′ ≡ 0 (we measured f′ = −4e−16). Return any point (for example the start) and flag the case; do not divide.
6. The book's ε_2 test is a cosine; near P ≈ C(u) both |C′| and |C − P| appear in the denominator, so test (1) must come first, as the book orders them.
7. Where C′ = 0 (double control points, P3.11) the Newton denominator loses its |C′|² term; the bracketed bisection keeps the method working.
8. The zero-cosine tolerance and the distance tolerance must be in consistent units: ε_1 in mm (eps_len = 1e−6 mm), ε_2 dimensionless (use eps_ang); the parameter test (4) in mm through |C′|, not in raw parameter units, because parameter ranges vary between files.

#### What it means for us

- Topic 01's "Projection of a point onto a general curve: Newton iteration on the curve parameter, started from the nearest tessellation point" matches the book but is not safe as written (cautions 4 and 5). The foundation module should implement the safeguarded version with a bracket and compare all local-minimum candidates and both ends.
- Q-035: the shared curve interface needs `closest_point(P) → (u, point, distance)`, `invert(P, tol) → u or none`, `derivs(u, k, side)` with side = left or right at knots, and `tangent(u, side)`. Arcs and ellipses implement the same interface with closed or near-closed forms.
- Topic 11: Yang 2002 stage 1 samples points and tangents at arbitrary parameters; `derivs` supplies them, with one-sided tangents at C⁰ knots marking tangent breaks. The Held–Eibl method needs only the flattened polyline and its proven error (note e).
- Topic 21: trimming parameters of STEP edges often come as points (vertex positions); inversion maps them to parameters before splitting.
- Units: parameters are not lengths. Introduce eps_par for parameter comparisons, defined relative to the knot range, and convert parameter steps to lengths through |C′| where a length test is meant.

#### Test ideas

Quarter circle Q: P = (1, 0), (1, 1), (0, 1), w = (1, √2/2, 1), U = {0, 0, 0, 1, 1, 1}.

1. P = (2, 2): u = 1/2, foot (√2/2, √2/2), distance 2√2 − 1 = 1.828427.
2. P = (0.3, 0.1): u = 0.2150407, foot (0.9486833, 0.3162278) = (3, 1)/√10, distance 1 − √0.1 = 0.6837722; u agrees with the closed form t = [1 + tan(ψ/2)/tan(π/8)]/2, ψ = atan(1/3) − π/4.
3. P = (3, −1): foot is the end u = 0, distance √5.
4. P = (−1, −0.5): foot is the end u = 1, (0, 1), distance √3.25 = 1.8027756; the unguarded iteration must not be used (it returns 0.304).
5. P = (0, 0) (centre): any u; the routine returns a valid u with distance 1 and flags the degenerate case, no division by zero.
6. P = (10, 0.001): u = 7.0709e−5, distance 9.00000005.
7. Random rational cubics on {0, 0, 0, 0, 0.25, 0.5, 0.75, 1, 1, 1, 1} and random points: the safeguarded result is never farther than the minimum over 20,001 dense samples (checked on 30 cases: no excess).
8. Closed curve: a point near the seam of the nine-point circle finds the foot across the seam (parameter wraps from 1 to 0).
9. Inversion: points C(u) at random u on random curves invert to u within 1e−12·(b − a) away from degenerate places; a point 1e−3 mm off the curve is reported as not on the curve for tol = 1e−4 mm.
10. One-sided tangents: quadratic on U = {0, 0, 0, 0.5, 0.5, 1, 1, 1} with P = (0, 0), (1, 0), (2, 0), (2, 1), (2, 2): C(0.5) = (2, 0), left derivative (4, 0), right derivative (0, 4), a 90° tangent break; on the nine-point circle at u = 1/4 both sides give (−4√2, 0).

### Piegl and Tiller 1997, chapter 12: flattening within a proven tolerance, and data exchange conventions

**Source:** Les Piegl, Wayne Tiller, *The NURBS Book*, 2nd edition, Springer, Berlin Heidelberg 1997, ISBN 978-3-540-61545-3, doi:10.1007/978-3-642-59223-2. Chapter 12 "Standards and Data Exchange" (pp. 571–591); for flattening, the statements on control-polygon convergence (p. 84, P3.7; p. 163) and the knot-removal error bound (Eq. 5.30, p. 185); chapter 9 "Curve and Surface Fitting" (pp. 361–454) skimmed for the closing paragraph.

**Read:** pp. 571–591 in full; pp. 361–366, 424–427 and 437–441 of chapter 9 skimmed; the whole book text searched for flattening, tessellation and deviation bounds. Page image checked for p. 576. **Class:** L.

**What the book gives and what it does not.** The book does not give a flattening algorithm or an error bound for approximating a curve by line segments. It states only that the control polygon converges to the curve under knot refinement (p. 163) and under degree elevation (p. 209), without a rate. The bounds below are derived here and labelled as ours; the one piece of the book they reuse is the structure of Eq. 5.30 for rational curves (deviation in homogeneous space, times (1 + distance from origin), divided by the smallest weight).

#### Definitions and formulas

**Flattening (derived here, not in the book).**

- *Interpolation lemma.* Let X(t) be a C² curve in any dimension on [t_0, t_1], h = t_1 − t_0, and L(t) the straight line through X(t_0) and X(t_1) at the same parameter. Then |X(t) − L(t)| ≤ (t − t_0)(t_1 − t)/2 · max|X″| ≤ h²/8 · max|X″|. Proof: e = X − L vanishes at both ends and e(t) = −∫ G(t, s) X″(s) ds with the Green's function G ≥ 0 of total mass (t − t_0)(t_1 − t)/2; take norms inside the integral. Every curve point is within this distance of the chord and every chord point within it of the curve, so the two-sided Hausdorff distance is bounded. The bound is exact for a parabola (constant X″).
- *Polynomial B-spline, per span.* On span [u_j, u_{j+1}) the second derivative C″ is a convex combination of the derivative control points P^{(2)}_{j−p} … P^{(2)}_{j−2} (Eq. 3.8 applied twice, strong convex hull of the derivative curve). With M_j = max |P^{(2)}_i| over those points, N_j equal parameter steps on the span give an error of at most (u_{j+1} − u_j)² M_j / (8 N_j²).
- *Polynomial Bézier segment of degree n on [0, 1].* P^{(2)}_i = n(n − 1)(P_{i+2} − 2P_{i+1} + P_i), so N equal steps give an error of at most n(n − 1)/(8N²) · max_i |P_{i+2} − 2P_{i+1} + P_i|, the classical second-difference bound.
- *Rational curves.* Write Cʷ = (A, w). A chord in homogeneous space projects onto the Euclidean chord, because its image is a positive combination of the two end points. With L the Euclidean chord point at parameter t, E_A = A − L_A and E_w = w − L_w the homogeneous interpolation errors, C − L = (E_A − L·E_w)/w. Apply the lemma to A and to w separately: with M_A and M_w the largest second-derivative control points of A and w on the span (Eq. 3.8 on the homogeneous coordinates), R the largest distance of the span's control points from the origin (it bounds |L|, since the chord lies in their convex hull) and w_min the smallest weight on the span (w(t) is a convex combination of them),
  - error ≤ h²/8 · (M_A + R·M_w) / w_min.
  The bound is unit-consistent (mm), unchanged when all weights are scaled, and valid for any origin; translate the span's points so the origin sits at the centre of their bounding box to keep R small. For w ≡ 1 it reduces to the polynomial bound.
- *Ellipse in eccentric angle* (ours): C(t) = (a cos t, b sin t) in its frame has |C″(t)| ≤ a, so N = ⌈Δt · √(a/(8·tol))⌉ equal angle steps suffice. The book notes that equal steps in t give the inscribed polygon of largest area (p. 289).
- *Circle:* use the exact rule of topic 01, Δθ = 2 arccos(1 − tol/r).

**Knot vector conventions (section 12.2, pp. 571–579).**

- Clamped: first and last knot values repeated p + 1 times; the book's "nonperiodic". Unclamped: not so. Uniform: equal spacing (for clamped, only the interior spans must be equal). Examples: clamped uniform {0, 0, 0, 0, 1, 2, 3, 4, 4, 4, 4}; clamped nonuniform {0, 0, 0, 2, 3, 6, 7, 7, 7}; unclamped uniform {−3, −2, … , 5}; unclamped nonuniform {0, 0, 1, 2, 3, 4} (pp. 571–572).
- For a clamped vector with m + 1 knots there are m − p control points; the knot vector fixes degree, point count and parameter range (p. 572).
- An unclamped curve is defined only on [u_p, u_{m−p}], and its ends do not coincide with control points (p. 572).
- Closed curves (p. 572): a clamped curve can be closed; its continuity at the seam depends on the first and last k interior spans and the first and last k + 1 points and weights. A closed C^{p−1} curve on an unclamped uniform vector repeats p control points: with U = {0, 1, … , 11} and p = 3 there are 8 points, P_5 = P_0, P_6 = P_1, P_7 = P_2, and the valid range is [3, 8]. For unclamped nonuniform closed curves the wrapped points need not coincide exactly (p. 574).
- "Periodic" historically meant unclamped uniform; the term survives in file formats with no fixed meaning (pp. 574–575, 582).
- Clamping is knot insertion of u_p and u_{m−p} up to multiplicity p followed by dropping the outer knots and points (p. 576, note c). Unclamping (A12.1, Eqs. 12.1–12.2) is not unique; the book's choice of new end knots, u_{p−i−1} = u_{p−i} − (u_{n−i+1} − u_{n−i}) and u_{n+i+2} = u_{n+i+1} + (u_{p+i+1} − u_{p+i}) for i = 0 … p − 1, restores wrap-around for curves closed with C^{p−1}. The nine-point circle does not wrap after unclamping because it is only C⁰ in homogeneous space (p. 578).

**NURBS in the standards (section 12.3, pp. 580–586).** The book describes each standard informally and refers to the documents for detail.

- IGES (pp. 580–583): degree, point count, Euclidean control points and weights stored separately (no homogeneous points), positive weights only, m + 1 = n + p + 2 knots with the only rule u_{i−1} ≤ u_i, so interior multiplicity above p is allowed (the curve may be discontinuous, p. 571). Start and end parameters s_0 < s_1 in [u_0, u_m] are part of the definition: the intended curve can be a proper subcurve, extracted by knot insertion at s_0 and s_1. Flags for planar, closed, rational and "periodic" are informational; a curve may carry a type tag (line, circular arc, conic).
- STEP Part 42 (pp. 583–585): NURBS is the only way to exchange general splines; degree, points and separate weights, positive weights only; end knots at most p + 1 times, interior knots at most p times; knot-vector type uniform (unclamped uniform), quasi-uniform (clamped uniform), Bézier (equally spaced distinct knots, interior multiplicity p, ends p + 1) or nonuniform; flags for closed and self-intersecting; type tags (polyline, circle, conic). Trimming by parameters exists, but at a higher level, not in the curve.
- PHIGS (pp. 585–586): order, homogeneous points if rational, positive weights, clamped knot vectors only, trimming parameters.
- Exchange (section 12.4, pp. 586–591): a conversion is either exact, exact in geometry but reparameterised (a trigonometric circle to NURBS), or only approximate. Analytic types go into NURBS exactly (chapter 7), but recognising them in a NURBS is hard because the representation is not unique (p. 587). A receiving system that limits degree, rationality or continuity forces approximation; the decision logic of A12.2 (pp. 590–591) is: rational into a polynomial-only system, or degree above its maximum, means approximate; degree below its minimum means elevate; continuity at some breakpoint below what the system allows means approximate; otherwise extract the segments by knot insertion and convert.

#### Algorithms

**Flatten a NURBS curve within tol_f** (ours). Input curve, tol_f. Output polyline whose points lie on the curve, two-sided Hausdorff distance ≤ tol_f. Cost O(p²) per span for the bound plus O(p²) per output point.

```
flatten(C, tol_f):
    out = [C(a)]
    for each non-empty span j = [u_j, u_{j+1}):
        pts = homogeneous points P^w_{j-p..j};  O = centre of the bounding box of their Euclidean points
        translate pts by -O (Euclidean part times weight)          # A_i = w_i (P_i - O)
        D2 = second-derivative control points of pts on this span (Eq. 3.8 twice)
        M_A = max |xyz part of D2|;  M_w = max |w part of D2|
        R = max |P_i - O|;  w_min = min w_i                         # over the span's p+1 points
        K = (M_A + R * M_w) / w_min                                 # K = M_A for polynomial curves
        N = max(1, ceil((u_{j+1} - u_j) * sqrt(K / (8 tol_f))))
        for k in 1..N: out.append(C(u_j + k (u_{j+1} - u_j)/N))
    return out
```

Degree 1 needs no bound (N = 1 per span). Knots of multiplicity p (corners) are span ends and therefore always vertices.

**Adaptive variant** (ours). Decompose into Bézier segments (note c); on each, compute the same bound with h = 1 from the segment's own points; if it exceeds tol_f, split at 1/2 by de Casteljau on the homogeneous points and recurse (explicit stack, depth limit); otherwise emit the end point. The bound falls by about 4 per halving. It adapts to curvature changes inside a span at the cost of recursion.

**Import of an exchanged NURBS curve** (ours, from sections 12.2–12.3).

```
import_nurbs(p, knots, points, weights, s0=None, s1=None, flags):
    check m + 1 = n + p + 2 and non-decreasing knots; snap near-equal knots (eps_par)
    reject any weight <= 0 (IGES and STEP forbid them)
    build homogeneous points (w x, w y, w z, w); normalise weights
    split at every interior knot of multiplicity > p (IGES may contain them; the curve may jump)
    if the ends are not clamped (unclamped, "periodic", STEP "uniform"): clamp at u_p and u_{m-p}
    if s0, s1 given (IGES) or a trim applies (STEP trimmed curve): extract the subcurve
    try arc recognition for quadratic rational pieces (note b); keep the source flags and IDs
```

#### Numerical cautions

From the book:

1. IGES "periodic" has no defined meaning (p. 582); never rely on the flag, look at the knots.
2. IGES curves may be discontinuous (interior multiplicity above p, p. 571) and may be proper subcurves of their knot range (p. 582).
3. Unclamping is not unique (p. 576); if a controller or file format needs it, fix the knot choice (Eqs. 12.1–12.2) so results are reproducible.
4. A NURBS that is really a circle or conic cannot be recognised from its data alone without tolerance-based tests, because the representation is not unique (p. 587).

Ours:

5. The flattening bounds use a maximum over whole spans; long spans with strongly varying curvature get more points than needed. The adaptive variant fixes this.
6. The rational bound divides by w_min; for extreme weight ratios it becomes very conservative. Normalise weights at import (note b) and cap the ratio.
7. Which side: on a piece without an inflection all chords lie on the concave side of the curve, like the inscribed polygon of an arc in topic 01; with an inflection, on both sides. Where the gouge side matters, either budget tol_f fully on that side or shift the polyline by tol_f toward the allowed side (the true curve is within tol_f of it).
8. Uniform parameter steps are not uniform in arc length; for a 90° NURBS arc they put points closer together near the ends. The bound accounts for this; do not assume equal chord lengths.
9. Measuring the chord error at sample points, as topic 01's "split until the chord error is below tol" suggests, is not a proof: a sample can miss the maximum. Use the bound.
10. When clamping an unclamped curve, find the span of u_{m−p} with the plain half-open rule. The end special case of find_span (return n when u ≥ u_{n+1}, note a) is meant for clamped vectors; on an unclamped vector it returns the wrong span (we hit this while checking).

**DXF, not in the book** (from the Autodesk DXF reference as generally documented; not read for this note, verify before relying on it). SPLINE carries group 70 flags (1 closed, 2 periodic, 4 rational, 8 planar, 16 linear), 71 degree, 72 knot count, 73 control-point count, 74 fit-point count, 40 knot values, 41 weights (present only if not all 1), 10/20/30 control points, 11/21/31 fit points, 12 and 13 start and end tangents, 42–44 tolerances. Splines given only by fit points must be rebuilt by interpolation, and the result may differ from what the CAD system displayed. ELLIPSE carries the centre, the major-axis end point relative to the centre, the ratio minor/major, and start and end parameters in radians; the parameters are eccentric angles as in Eq. 7.15, not polar angles. Register the checks as a question.

#### What it means for us

- **D-034 made provable.** "Flattened per operation within a share of the tolerance" can use flatten(C, share·tol) with a guaranteed two-sided Hausdorff bound; no sampling-based check is needed. The same bound gives Held–Eibl (topic 11) the known flattening error by which the tolerance band must shrink (their p. 360), and gives the spline part of the tolerance budget (Q-034) a number instead of an estimate.
- **Answer proposal for Q-035 (curve types).** The model and the kernel share one tagged curve type with four variants: Line (P_0, P_1); Arc (centre, radius, plane frame, start angle, signed sweep in (−2π, 2π], with both end points stored exactly so chains stay closed; bulge only at the DXF boundary); EllipseArc (centre, unit major axis, a, b, start eccentric angle, signed sweep); Nurbs (degree p ≥ 1, full clamped knot vector with interior multiplicity ≤ p, homogeneous control points with w > 0, flags closed and "was periodic", source ID). At the C++ kernel boundary a Nurbs is three flat arrays: degree, knots (float64, m + 1), homogeneous points (float64, (n + 1) × 4, or × 3 for planar curves). Every variant provides eval, derivs(u, k, side), split, reverse, subcurve, bounding box, closest_point, invert, flatten(tol_f) and to_nurbs; Nurbs also provides try_to_arcs. The 2D modules (offsets, Booleans, pockets) consume only lines and arcs, produced per operation by flattening plus arc fitting (D-023) or by exact recognition.
- **Topic 21 import rules** follow from section 12.3: separate weights become homogeneous points, weights must be positive, unclamped and periodic curves are clamped, IGES subcurves and STEP trims are extracted once at import, over-multiple knots split the curve, near-equal knots are snapped. For STEP read through OCCT, the curve arrives as distinct knots with multiplicities and a periodic flag (OCCT's own form, not described in the book; check under A-009).
- **Later (topic 13).** Controllers with spline input limit degree and continuity; A12.2 is the decision logic for exporting a toolpath spline to them.

**Chapter 9 for later (one paragraph).** Chapter 9 offers global interpolation of points (section 9.2.1: chord-length Eq. 9.5 or centripetal Eq. 9.6 parameters and knots by averaging, Eq. 9.8, which makes the linear system banded and totally positive, solvable without pivoting; p. 365), with end derivatives or first derivatives prescribed (9.2.2–9.2.4); local interpolation with parabolic, rational quadratic and cubic segments (9.3); least-squares approximation, weighted and constrained (9.4.1–9.4.2); approximation to a given accuracy, either adding knots at the midpoints of spans that fail the max-norm test (measured by point projection, Eqs. 9.77–9.79) or starting dense and removing knots (9.4.4); and local approximation of planar points by G¹ conic segments or of 3D points by cubics with a binary search for the longest run that fits within the tolerance (9.5). For us: interpolation for DXF splines given only by fit points (release 1 if such files occur), accuracy-bounded approximation for compressing fine toolpaths into NURBS for spline-capable controllers (later), and the conic local approximation as a relative of arc fitting (topic 11), though conic segments are not G2/G3-ready.

#### Test ideas

1. Parabola as a quadratic Bézier (0, 0), (1, 2), (2, 0) mm: second difference (0, −4), bound 1/N² mm; for N = 10 the true error is 0.01 mm, equal to the bound (it is attained at the middle of every chord).
2. Quarter circle r = 1 mm, w = (1, √2/2, 1), origin at the centre: M_A = M_w = 2(2 − √2), R = √2, w_min = √2/2, so K = 4 exactly. tol_f = 0.01 mm gives N = 8 (bound 0.0078 mm, true 0.0053 mm; the exact circle rule needs 6 chords); tol_f = 0.001 mm gives N = 23 (bound 0.00095 mm, true 0.00065 mm; exact rule 18). For radius r, K = 4r and N = ⌈√(r/(2·tol_f))⌉: r = 10 mm, tol_f = 0.01 mm gives 23 chords per quarter, true error 0.0065 mm.
3. Bound validity: random rational and polynomial curves (degree 2–4, weights 0.3–3), spans split into 1, 2 and 5 steps: the true error never exceeds the bound (maximum ratio 0.9998 in our run). With the curves placed about 300 mm from the origin and the bound computed about the global origin (large R) it still holds (maximum ratio 0.84, so more conservative). For random Bézier curves of degree 2–6 the second-difference bound holds likewise (maximum ratio 0.9995).
4. Nine-point ellipse a = 50, b = 30 mm, tol_f = 0.01 mm: 46 chords per quarter, 184 in total, true error 0.0067 mm; the analytic eccentric-angle rule needs 158 chords, true error 0.0099 mm.
5. Invariance: scaling all weights of a curve by 7 changes neither the points nor the chord count; translating the curve by (1000, −1000) mm changes neither, because the bound is computed about the span's own box centre.
6. Corners: a quadratic with a double interior knot is flattened with a vertex exactly at the corner point.
7. Knot conventions: the unclamped uniform cubic on {0, … , 11} with P_5 = P_0, P_6 = P_1, P_7 = P_2 imports as a clamped closed curve with knots {3 ×4, 4, 5, 6, 7, 8 ×4} and 8 points, equal to the original on [3, 8] within 1e−14, with point, first and second derivative equal at 3 and 8 (C² seam).
8. IGES-style subcurve: a clamped cubic on [0, 1] with s_0 = 0.2, s_1 = 0.7 imports as a curve whose end points are C(0.2) and C(0.7) exactly and which matches the original between them.
9. Import rejects a weight of 0 or −0.5 and splits a curve with an interior knot of multiplicity p + 1 into two curves.
10. Round trip: a STEP-style knot list given as distinct values with multiplicities expands to the full vector and back without change.

### Shewchuk 1997: Adaptive precision floating-point arithmetic and fast robust geometric predicates

**Source:** Jonathan Richard Shewchuk, "Adaptive Precision Floating-Point Arithmetic and Fast Robust Geometric Predicates", Discrete & Computational Geometry 18(3):305–363, 1997, doi:10.1007/PL00009321. **Read:** pp. 305–363 complete, including Appendices A and B. Fig. 21, Table 1 and p. 324 checked on page images. Page numbers are the printed ones. **Class:** L (public literature). Target topic: 01 (also 02, 03, 11, 24).

**Problem.** Geometric algorithms are written for exact real arithmetic. With floating point, a sign test near zero can come out wrong, and worse, inconsistent with earlier tests; the algorithm then hangs, crashes or returns invalid topology (pp. 307, 341–342). Many decisions need only the *sign* of a small determinant, not its value. The paper gives (1) exact arithmetic on sums of doubles ("expansions"), (2) a way to evaluate an expression in stages that stop as soon as the sign is certain, and (3) four predicates built this way: orient2d, orient3d, incircle, insphere (pp. 305–307). Assumptions: binary floating point with exact rounding (IEEE 754 round to nearest), p-bit significand; for double p = 53 (p. 309–310). Overflow and underflow are not handled (p. 308).

**Method.**

*1. Error-free transformations* (Section 2). Notation: ⊕, ⊖, ⊗ are rounded operations; ε = ½ ulp(1) = 2^−p, so ε = 2^−53 for double (pp. 335–336). Every rounded operation satisfies |err| ≤ ½ ulp(result) (p. 310). Our pseudocode:

```python
def fast_two_sum(a, b):          # requires |a| >= |b|  (Thm 6, p. 312)
    x = a + b
    return x, b - (x - a)        # a + b == x + y exactly
def two_sum(a, b):               # no ordering needed, p >= 3 (Thm 7, p. 314)
    x = a + b; bv = x - a; av = x - bv
    return x, (a - av) + (b - bv)
def split(a):                    # s = ceil(p/2) = 27 for double (Thm 17, pp. 325-326)
    c = (2**27 + 1) * a; hi = c - (c - a)
    return hi, a - hi            # hi and lo have at most 26 significant bits each
def two_product(a, b):           # p >= 6 (Thm 18, p. 326)
    x = a * b; ah, al = split(a); bh, bl = split(b)
    e = x - ah*bh; e -= al*bh; e -= ah*bl
    return x, al*bl - e          # a*b == x + y exactly
```

TWO-SUM without a branch was usually faster than FAST-TWO-SUM plus a magnitude comparison, but not with every compiler; time it (p. 313, footnote 4). Not in the paper: with hardware fused multiply-add, y = fma(a, b, −x) gives the same exact error term as two_product.

*2. Expansions* (p. 309). A number is a sum e_1 + … + e_m of doubles, sorted by increasing magnitude, pairwise nonoverlapping (the lowest set bit of the larger one lies above the highest set bit of the smaller one). Its sign is the sign of the largest nonzero component; it is zero only if all components are zero; two expansions are compared by subtracting (p. 334). Operations:

- **GROW-EXPANSION(e, b)** (Thm 10, p. 316): add one double. Carry q = b; for each component from the smallest, (q, h_i) = two_sum(q, e_i); append q last.
- **EXPANSION-SUM(e, f)** (Thm 12, p. 318): add each f_i by grow-expansion into the part of h from index i upward. mn TWO-SUMs, 6mn flops; keeps nonoverlapping and nonadjacent inputs so (p. 324).
- **FAST-EXPANSION-SUM(e, f)** (Thm 13, pp. 319–320): merge e and f by magnitude into g; (q, h_1) = fast_two_sum(g_2, g_1); then (q, h_{i−1}) = two_sum(q, g_i) for i = 3 … m+n; last component q. 6m + 6n − 9 flops plus m + n − 1 comparisons, about 9m + 9n − 12 flop-equivalents (p. 324). Correct only for round-to-even and "strongly nonoverlapping" inputs, p ≥ 4. Without round-to-even use LINEAR-EXPANSION-SUM (Appendix B, pp. 360–362).
- **SCALE-EXPANSION(e, b)** (Thm 19, p. 328): multiply by a double. (Q, h_1) = two_product(e_1, b); for each further e_i: (T, t) = two_product(e_i, b); (Q, h) = two_sum(Q, t); (Q, h') = fast_two_sum(T, Q); append h, h'. Output 2m components.
- **Zero elimination:** skip zero outputs; almost always worth it (p. 324). Practice: unrolled EXPANSION-SUM for up to about four components, FAST-EXPANSION-SUM with zero elimination beyond (pp. 324–325).
- **COMPRESS** (Thm 23, pp. 331–332): two sweeps of fast_two_sum, top-down then bottom-up; the largest output component then approximates the whole with error below one ulp of itself. **APPROXIMATE**: sum the components from smallest to largest in plain floating point; error below one ulp (p. 333).
- Product of two expansions: scale by each component, then sum in a balanced tree ("distillation", p. 333). Division is not exact (p. 334).

*3. Adaptive evaluation* (Section 3, pp. 334–338). Write each bottom subtraction of the expression tree as x_i + y_i (rounded value plus exact error). Expanding gives terms T_0 (no y), T_1 (one y), T_2 …, of size O(1), O(ε), O(ε²). Stage j computes a result with error O(ε^j) and tests it against a bound. The recommended variant: C_j = the exact A_{j−1} plus a cheap floating-point estimate of T_{j−1}; exact work already done is reused, the cheap corrections are not (p. 337). Stage 1 is the floating-point filter of Fortune and Van Wyk (p. 337).

*4. orient2d* (pp. 346–349, Fig. 21), four stages:

1. **A:** x_1 = a_x ⊖ c_x, x_2 = b_y ⊖ c_y, x_3 = a_y ⊖ c_y, x_4 = b_x ⊖ c_x; x_5 = x_1 ⊗ x_2, x_6 = x_3 ⊗ x_4; A = x_5 ⊖ x_6. Return A if |A| ≥ errA · (|x_5| ⊕ |x_6|).
2. **B:** the exact products x_1·x_2 and x_3·x_4 by two_product, their difference as a four-component expansion B; B′ = APPROXIMATE(B). Return B′ if |B′| ≥ errB · detsum. B is exact when the four subtractions had no rounding error, which is the common case (Fig. 20, p. 346); then return B′ as well.
3. **C:** get the rounding tails of the four subtractions (two_diff). C = B′ + [x_1·t_2 + x_2·t_1 − (x_3·t_4 + x_4·t_3)] in floating point, t_k the tails. Return C if |C| ≥ errC · detsum + resB · |B′|.
4. **D:** the exact determinant including all tail products, by expansion arithmetic; at most 16 components, usually 2–6 after zero elimination (p. 346). Its sign is the answer.

No further stage between C and D: a determinant not settled by C is nearly always exactly zero (p. 347).

orient3d, incircle and insphere follow the same four stages (pp. 350–352); for insphere, D is recomputed from scratch (p. 352). All four use the translated forms (subtract one point first) and cofactor expansion by dynamic programming over 2 × 2 minors (pp. 345–346).

**Formulas.** Points in the plane, coordinates as doubles (mm for us).

- orient2d(a, b, c) = (a_x − c_x)(b_y − c_y) − (a_y − c_y)(b_x − c_x). Positive if a, b, c are counter-clockwise, that is c lies left of the directed line a→b; negative clockwise; zero collinear (p. 344). Swapping two arguments flips the sign.
- incircle(a, b, c, d) = det of the 3 × 3 matrix with rows (p_x − d_x, p_y − d_y, (p_x − d_x)² + (p_y − d_y)²) for p = a, b, c (2D form of Eq. 9, p. 345). Positive if d lies inside the circle through a, b, c when a, b, c are counter-clockwise; the sign flips for clockwise order; zero if and only if the four points are cocircular (p. 344).
- orient3d(a, b, c, d): 3 × 3 determinant of rows a − d, b − d, c − d (Eq. 7); positive if d lies below the plane through a, b, c seen counter-clockwise from above (p. 344).
- Error bounds, with detsum = |x_5| ⊕ |x_6| for orient2d, α sums for the others (Tables 1, 3, 5, pp. 349, 351, 352):

| Predicate | A | B′ | C |
| --- | --- | --- | --- |
| orient2d | (3ε + 16ε²)·detsum | (2ε + 12ε²)·detsum | (3ε + 8ε²)·\|B′\| + (9ε² + 64ε³)·detsum |
| orient3d | (7ε + 56ε²)·Σα | (3ε + 28ε²)·Σα | (3ε + 8ε²)·\|B′\| + (26ε² + 288ε³)·Σα |
| incircle | (10ε + 96ε²)·Σα | (4ε + 48ε²)·Σα | (3ε + 8ε²)·\|B′\| + (44ε² + 576ε³)·Σα |

For orient3d, α_a = |a_z ⊖ d_z| ⊗ (|(b_x ⊖ d_x) ⊗ (c_y ⊖ d_y)| ⊕ |(b_y ⊖ d_y) ⊗ (c_x ⊖ d_x)|), cyclic in a, b, c. For incircle, α_a = ((a_x ⊖ d_x)² ⊕ (a_y ⊖ d_y)²) ⊗ (the same bracket without the z factor), cyclic. Compute the coefficients once at start-up; each is exactly representable (p. 349).
- Derivation of errA (p. 348), re-checked by us: t_5 = x_5 ± (3ε + 3ε² + ε³)|x_5|; the sign of A is safe if (1 − ε)|A| > (3ε + 3ε² + ε³)(|x_5| + |x_6|), i.e. |A| ≥ (3ε + 6ε² + 8ε³)(…); a factor (1 + ε)² for rounding the bound itself gives 3ε + 12ε² + 24ε³, rounded up to the representable 3ε + 16ε².
- Circumcentre of a, b, c (p. 359), our notation with u = a − c, v = b − c: d_x = c_x − (u_y|v|² − v_y|u|²) / (2·orient2d(a, b, c)), d_y = c_y + (u_x|v|² − v_x|u|²) / (2·orient2d(a, b, c)). We checked it on (0, 0), (4, 0), (0, 2): centre (2, 1). The denominator is orient2d, so near-collinear points blow up; the paper suggests an orient2d variant that stops once the relative error is about ½ %.

**Parameters and values.**

- ε = 2^−53, splitter 2^27 + 1 for double (pp. 326, 336).
- Exponent range for which the four predicates cannot overflow or underflow in double: input exponents in [−142, 201], that is |x| roughly between 1.8·10^−43 and 3·10^60 (p. 308).
- The error bounds are zero when all points share an x or a y coordinate (orient2d, p. 349) or an x, y or z coordinate (orient3d, p. 350), so those common degenerate cases finish in stage A.
- Costs on a 225 MHz DEC Alpha, in µs (Tables 2, 4, 6): orient2d plain 0.15, stage A 0.22–0.28, D 8.35; orient3d plain 0.25, A 0.61, D 27.3; incircle plain 0.30, A 0.59–0.64, D 78.1. Stage A costs about twice the plain test (p. 349); stage D is about 55 (orient2d) to 260 (incircle) times dearer, but rare. Putting stage A and the rest in separate functions cut A's time by 25 % (p. 349).

**Limits and failure cases.**

From the paper:

1. **Only signs of polynomials in the inputs.** Constructed points (intersections, offsets, rotations) need division or roots; exact rationals grow in bit length when intersections feed further intersections, and a square rotated by 45° already has irrational vertices (p. 340). Exact predicates make algorithms with purely combinatorial output robust (convex hull, Delaunay), not constructions (pp. 308, 341).
2. **No overflow or underflow handling** (p. 308); no easy way to extend the exponent range (p. 358).
3. **Hardware and compilers.** x87-style extended internal registers break the error terms; `volatile` does not cure double rounding; set the processor to round to double. Compilers that "simplify" (x − a) − b to zero break everything (pp. 355–357).
4. FAST-EXPANSION-SUM needs round-to-even (Appendix A, p. 360); the author conjectures the predicates themselves work under any tie-break.
5. Adaptivity does not scale beyond about 5 × 5 determinants (p. 359).
6. Printed error: p. 324 gives EXPANSION-SUM as 0.83(m + n) − 0.7 µs and FAST-EXPANSION-SUM as 0.54mn + 0.6 µs. The two formulas are swapped: EXPANSION-SUM is the O(mn) method, and only with the swap does the next sentence hold ("FAST-EXPANSION-SUM is always faster except when one of the expansions has only one component").

Noticed by us:

7. **Exact about the doubles, not about the design.** A DXF value "0.1" is stored as the nearest double, so three points collinear in the drawing can give a tiny nonzero orient2d. Exactness guarantees consistency, not agreement with intent. Tolerance decisions (eps_len, "these points coincide", "this segment is collinear") must be made first and explicitly, never folded into a sign test with an epsilon.
8. **Arcs in centre form are over-determined.** For an arc stored as (P0, P1, centre C), |P0 − C| and |P1 − C| differ in floating point; an exact "inside the arc's circle" test depends on which radius is used. The spec must name the defining data (for example centre and radius, with end points snapped onto the circle within eps_len).
9. **FMA contraction and fast-math.** Modern compilers may fuse a·b − c into one fused multiply-add (from general knowledge: GCC does so by default outside strict ISO modes, Clang within one expression), and `-ffast-math` allows reassociation. Either silently breaks the error terms. Build the predicate code with `-ffp-contract=off` and without fast-math, and test for it (test 7).
10. Calling a predicate per point from Python costs more in call overhead than the predicate itself; it belongs in the C++ kernel, with numpy-vectorised stage A at most.

**How it was tested.** Correctness by proof for every arithmetic routine (Section 2). Speed on uniform, widely spread and nearly degenerate random inputs (Tables 2, 4, 6, 7). In applications (p. 354, Tables 8 and 9): 2D Delaunay (Triangle) on 10^6 points costs about 8 % more with robust predicates on random points (61.7 s against 57.3 s) and about 30 % more on a tilted grid (62.2 s against 48.3 s); of about 9.44 million orient2d calls there, 121,081 reached stage B, 118 stage C and 3 stage D. 3D Delaunay (Pyramid) on 10^4 points: +35 % on random points, ×11 on points near a sphere; the non-robust version never finished on the tilted grid (stuck in point location after an inconsistent mesh).

Our own check: we re-implemented stages A to D of orient2d in Python from this description (not from predicates.c) and compared against exact rationals. On the grid p = (0.5 + i·2^−53, 0.5 + j·2^−53), i, j = 0 … 255, with q = (12, 12) and r = (24, 24), the exact sign is sign(j − i), because orient2d(p, q, r) = 12(p_y − p_x). The plain formula with p as pivot got 11,972 of 65,536 signs wrong; the adaptive version got none (8,736 calls ended in stage A, 22,556 in B, 33,996 in C, 248 in D). On 200,000 random near-collinear triples in [−100, 100]² mm: no wrong sign. Three points on y = 0.3 returned exactly 0 in stage A.

**What it means for us.**

*Which predicates the 2D core needs* (our mapping; the paper only defines the predicates and names hulls, triangulations and point location as users):

| Decision | Predicate | Where |
| --- | --- | --- |
| Loop orientation, CW or CCW | orient2d at the lowest-leftmost vertex (a hull vertex) of a simple loop; the shoelace sum is not a single exact predicate | topic 01, import |
| Point in region, loop tree containment | orient2d of the point against each edge crossing its horizontal line (winding number) | 01, 02, 04, 25 |
| Do two segments cross; convex or reflex vertex | four and one orient2d calls | 02 cleanup, 04 corners and scan-reflex vertices |
| Collinear or not before a circle fit | orient2d (the circumcentre denominator) | 01, 11 |
| Point inside the circle of an arc given by three points | incircle | 11 arc fitting |
| Delaunay of points, Voronoi of points | incircle | 03 (not release 1, D-035) |
| Facet orientation, ray and triangle tests on meshes | orient3d | 06, 20 through-hole ray test (release 3) |

Segment Voronoi (topic 03) needs higher-degree predicates that the paper does not cover; boost::polygon brings its own.

*Consequences.*

- **Where exactness lives.** Offsets and Booleans run in Clipper2 on 64-bit integers (D-023), which is the integer route the paper surveys (Avnaim et al., Fortune and Van Wyk, pp. 339–340). Our derivation: an orient2d on integer coordinates evaluated in double is exact when every coordinate difference is below 2^26 grid units, because each product is then an integer below 2^52 and their difference below 2^53. At a scale of 10^4 per mm (grid 0.1 µm) that is 6.7 m, far beyond any part. Whether Clipper2 relies on this or uses 128-bit products must be checked in the version we pin (Q-036, A-001). The float side (imported DXF and STEP contours, the loop tree, point-in-region, arc fitting, chaining) should call exact adaptive orient2d and incircle in the C++ kernel.
- **Topic 01 text.** "When the result is ambiguous (point almost on an edge), fall back to the side of the nearest edge" is a quasi-robust patch of the kind the paper warns about (pp. 341–344). With exact orient2d, "on the edge" is decidable (sign 0); what remains is a tolerance policy for points within eps_len of an edge, stated separately. The same resolves part of the "Missing before a spec" item on loops that touch or share edges: exact predicates plus snapping within eps_len first.
- **Topic 01, circle through three points.** "No arc exists when |D| < eps" should become: no arc if orient2d is exactly 0, and reject arcs whose radius exceeds a limit derived from tol and chord length (the relative-error concern of p. 359).
- **Q-033 (bit identity), partly answered.** The sign of an exact predicate is a mathematical fact about the input doubles, so any correct implementation returns the same combinatorial decisions on macOS, Windows and Linux, with any thread count. Constructed coordinates remain platform-dependent unless the construction is correctly rounded too (p. 358 says a correctly rounded segment intersection is feasible with these tools). Golden files should therefore compare topology exactly and coordinates within a tolerance.
- **Licence.** The paper says only that the C code is publicly available from http://www.cs.cmu.edu/~quake/robust.html (pp. 305, 308). As far as we know the file header of `predicates.c` places it in the public domain, which topic 01 also states; confirm from the header of the copy we vendor. It needs its initialisation routine called once before use (general knowledge, to verify). Cost is no concern for a 2D core: stage A is the exit for nearly all calls (Table 8).

*Register effects.* Q-033 partly answered (combinatorial output). Q-036 and A-001 gain a concrete exactness bound for the integer side. Topic 01 "Missing before a spec": the predicate set and the loop-touching rule get a method. New question proposed (owner Claude): which predicate library the C++ kernel ships (vendored predicates.c or a port), with which compiler flags, and which tolerance snapping precedes each exact test.

**Test ideas.**

1. Grid test above: for all 65,536 points, orient2d returns sign(j − i); the plain formula must not be used as the oracle. Exact rationals (Python `fractions`) are the oracle.
2. Degenerate lines: three points with equal y (or equal x) return exactly 0 and end in stage A.
3. Symmetry: for random triples, swapping any two arguments negates the result; cyclic shifts keep it.
4. incircle with a = (5, 0), b = (0, 5), c = (−5, 0): d = (3, 4) gives exactly 0; d = (3, 4 − 2^−50) gives > 0; d = (3, 4 + 2^−50) gives < 0; reversing a, b, c flips the signs.
5. Circle fit: (0, 0), (4, 0), (0, 2) gives centre (2, 1) exactly; (0, 0), (1, 1), (2, 2) gives orient2d = 0 and no arc; (0, 0), (1, 1 + 2^−52), (2, 2) gives a nonzero sign and must be rejected by the radius limit, not by division by zero.
6. Point in region, square [0, 10] × [0, 10] mm: points (10, 5), (10, 10), (10 − 2^−49, 5) and (10 + 2^−49, 5) (one ulp inside and outside the edge x = 10): exact answers on, on, in, out; the tolerance layer then classifies the last two as "on" within eps_len.
7. Build guard: call two_sum and two_product of the compiled kernel on 10^6 random pairs (uniform and with widely spread exponents) and check x + y against the exact rational result every time. Example: two_product(1 + 2^−30, 1 + 2^−30) = (1 + 2^−29, 2^−60). Run it in every CI build configuration, so a contracting or reordering compiler setting is caught.
8. Cross-platform: the sign arrays of tests 1 to 4 are identical on macOS, Windows and Linux (Q-033).

## Open items

Readiness **L4**, needed for release **1**. Audit of 2026-09-27: [details](../reviews/2026-09-27-readiness-audit.md#01-foundations). Levels are defined in [AGENTS.md](../AGENTS.md#readiness-levels).

### Registered questions and assumptions

<!-- open-items:begin -->
_Generated by `tools/spike.py status` from QUESTIONS.md and ASSUMPTIONS.md. Do not edit by hand._

- [A-001](../ASSUMPTIONS.md#a-001-eps_len--1e-6-mm-is-consistent-with-the-clipper-integer-scale) (wrong) eps_len = 1e-6 mm is consistent with the Clipper integer scale
- [A-043](../ASSUMPTIONS.md#a-043-advice-written-for-a-c-and-c-code-base-carries-over-to-the-python-stack) (wrong) Advice written for a C# and C++ code base carries over to the Python stack
<!-- open-items:end -->

### Missing before a spec

- [x] Native splines and ellipses in the model (D-034): representation, evaluation, point projection, adaptive flattening within a tolerance share (Q-035). Done 2026-10-02: D-057, D-092, D-093, section Curves and the Piegl and Tiller notes.
- [x] A canonical arc representation and a full-circle form (Q-035). Done 2026-10-02: D-057, section Curves.
- [x] Default values for the tolerance set, a value for eps_ang, and the rule for splitting tol (Q-034). Done 2026-10-02: D-056, D-146, D-149, section Tolerances.
- [x] The circumscribed segment angle and the circular-segment area term. Done 2026-10-02: sections Flattening and Area.
- [x] Loop tree rules for loops that cross, coincide or share edges. Done 2026-10-02: section Loop tree (proposal, ours).
- [x] The array layout at the C++ kernel boundary, and a 3D frame and transform type. Done 2026-10-02: sections Kernel arrays and Frames (proposal, ours).
- [ ] The coordinate limit of 2^26 grid units must become a released requirement (draft REQ-OFF-018) with the D-132 kernel changes after the plan 0001 gate, because Clipper2 also decides in double (SRC-122).
- [ ] Arc recognition at import (D-093, Q-075): the control-point test does not bound the deviation; topic 21 must add the check that keeps it within 0.0001 mm.
- [ ] The chaining tolerance of topic 25, and how its gap repairs are reported (topic 25 pass).
- [ ] Welzl 1991 (SRC-124) read to confirm the algorithm taken from SRC-125.
- [ ] How pinch splits are re-nested into the loop tree (rule 7), in the topic 02 pass.

---

[Index](README.md) · [2. 2D offsets and Booleans →](02-offsets-and-booleans.md)

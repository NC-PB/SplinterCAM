// SPDX-License-Identifier: Apache-2.0
// Exact signs (research 01, Vectors and exact signs; D-097): Shewchuk's orient2d and incircle from
// the vendored predicates.c, and our arc predicates with the expansion arithmetic of SRC-032.
#pragma once

#include <array>
#include <cstdint>
#include <span>
#include <vector>

namespace splintercam::geometry2d {

// One planar point per two doubles: (x, y) pairs, row after row.
using Points = std::span<const double>;
using Scalars = std::span<const double>;
using Signs = std::span<std::int8_t>;
using Point2 = std::array<double, 2>;

struct ValuePairs { // a and b, one value per row
    Scalars a;
    Scalars b;
};
struct ErrorFreePairs { // x the rounded result, y its rounding error, one per row
    std::span<double> x;
    std::span<double> y;
};
struct ArcQueries { // per row a query point and the circle about centre through p0
    Points q;
    Points centre;
    Points p0;
};
struct HeightQueries { // per row a query height and the circle about centre through p0
    Scalars q_y;
    Points centre;
    Points p0;
};

// Error-free transformations (SRC-032, Theorems 7 and 18): x + y equals a + b, or a·b, exactly.
// Batches for the build guard of REQ-G2D-016: they compile with the kernel's strict float flags.
void two_sums(const ValuePairs& in, const ErrorFreePairs& out);
void two_products(const ValuePairs& in, const ErrorFreePairs& out);

// Single points: the exact signs of orient2d, of the arc predicate and of the (q_y − c_y)²
// comparison below, for kernels that loop over points themselves.
struct CircleAt { // the circle about centre through p0
    Point2 centre;
    Point2 p0;
};
[[nodiscard]] int orient_sign(Point2 a, Point2 b, Point2 c);
[[nodiscard]] int arc_circle_sign(Point2 q, const CircleAt& circle);
[[nodiscard]] int vertical_extent_sign(double q_y, const CircleAt& circle);

// Per row, the exact sign of orient2d(a, b, c): +1 when c lies left of a → b (REQ-G2D-007).
void orient2d_signs(const std::array<Points, 3>& abc, Signs out);
// incircle(a, b, c, d): +1 when d lies inside the circle through a, b, c given CCW (REQ-G2D-011).
void incircle_signs(const std::array<Points, 4>& abcd, Signs out);
// |p0 − c|² − |q − c|²: +1 when q lies inside the circle about c through p0 (REQ-G2D-022).
void in_arc_circle_signs(const ArcQueries& in, Signs out);
// (q_y − c_y)² − |p0 − c|²: −1 while q_y lies strictly between the lowest and highest point of the
// circle, 0 at them, +1 beyond (REQ-G2D-023).
void vertical_extent_signs(const HeightQueries& in, Signs out);

struct CircleOut { // per row the centre (x, y), the radius and 1 when a circle was found, else 0
    std::span<double> centres;
    std::span<double> radii;
    Signs found;
};
// The circle through p1, p2, p3 (research 01, Circle through three points; SRC-032, p. 359): none
// when orient2d is 0 or p2 lies within length_eps_mm of the line p1p3 (REQ-G2D-097 to 101).
void circles_through(const std::array<Points, 3>& p123, double length_eps_mm, const CircleOut& out);

struct CrossTerm { // a·b − c·d
    double a;
    double b;
    double c;
    double d;
};
// A sum of cross terms kept exactly as a nonoverlapping expansion, smallest component first
// (SRC-032, section 2): two_product (Theorem 18) and fast_expansion_sum_zeroelim (Theorem 13).
class ExactSum {
public:
    void add(const CrossTerm& term);
    // The components summed smallest first: the exact sum within a rounding unit, its sign exact.
    [[nodiscard]] double value() const;

private:
    // Two buffers used in turn, each two longer than its expansion: predicates.c reads past an
    // input's end, e[0] and e[1] when it is empty.
    std::vector<double> parts_ = {0.0, 0.0};
    std::vector<double> next_ = {0.0, 0.0};
    int size_ = 0;
};

// Starts predicates.c's error bounds; called once when the kernel module loads (REQ-G2D-013).
void init_exact_arithmetic();

} // namespace splintercam::geometry2d

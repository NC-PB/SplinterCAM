// SPDX-License-Identifier: Apache-2.0
// Exact signs (research 01, Vectors and exact signs). orient2d and incircle are Shewchuk's adaptive
// predicates (SRC-032, vendored predicates.c, ADR 0009). The arc predicates are ours (research 01),
// evaluated every time with SRC-032's expansion arithmetic: each squared difference (a − b)² is
// expanded exactly from two_diff and two_product (Theorems 7, 17, 18) and the terms are summed by
// predicates.c's fast_expansion_sum_zeroelim (Theorem 13), whose largest component has the sign of
// the exact sum. Exact within the input range of the SPEC's precondition (SRC-032, p. 308).
// circles_through: the circle through three points (research 01; SRC-032, p. 359), decided by
// orient2d's exact sign.
#include "exact.hpp"

#include "shewchuk.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <numeric>
#include <utility>

namespace splintercam::geometry2d {
namespace {

// An expansion: nonoverlapping components, smallest first (SRC-032, section 2).
// A sum of four squared differences has at most 4 · 6 = 24 components. fast_expansion_sum_zeroelim
// reads one element past the end of an input (predicates.c, its e[++eindex]); the largest input,
// 12 components, leaves that element inside the zeroed array.
constexpr std::size_t expansion_capacity = 24;

struct Expansion {
    std::array<double, expansion_capacity> parts{};
    int size = 0;
};

struct Pair {
    double x; // the rounded result
    double y; // its rounding error
};

Pair two_sum(double a, double b) { // Theorem 7
    const double x = a + b;
    const double b_virtual = x - a;
    const double a_virtual = x - b_virtual;
    return {x, (a - a_virtual) + (b - b_virtual)};
}

Pair split(double a) { // Theorem 17: two halves of at most 26 significant bits each
    constexpr double splitter = 134217729.0; // 2^27 + 1 for binary64 (SRC-032, p. 326)
    const double c = splitter * a;
    const double high = c - (c - a);
    return {high, a - high};
}

Pair two_product(double a, double b) { // Theorem 18
    const double x = a * b;
    const auto [a_high, a_low] = split(a);
    const auto [b_high, b_low] = split(b);
    const double error = x - a_high * b_high - a_low * b_high - a_high * b_low;
    return {x, a_low * b_low - error};
}

Expansion sum(Expansion e, Expansion f) {
    Expansion h;
    h.size =
        fast_expansion_sum_zeroelim(e.size, e.parts.data(), f.size, f.parts.data(), h.parts.data());
    return h;
}

Expansion of(Pair pair) {
    Expansion e;
    std::get<0>(e.parts) = pair.y;
    std::get<1>(e.parts) = pair.x;
    e.size = 2;
    return e;
}

// (a − b)², exactly: with a − b = x + y, it is x² + 2xy + y².
Expansion squared_difference(double a, double b, bool negate) {
    const auto [x, y] = two_sum(a, -b); // a − b = x + y
    const double sign = negate ? -1.0 : 1.0;
    return sum(sum(of(two_product(sign * x, x)), of(two_product(sign * 2 * x, y))),
               of(two_product(sign * y, y)));
}

int sign_of(double value) {
    return (value > 0.0) - (value < 0.0);
}

int sign_of(const Expansion& e) {
    return sign_of(e.parts.at(static_cast<std::size_t>(std::max(e.size - 1, 0))));
}

Point2 point(Points points, std::size_t row) {
    Point2 p{};
    std::ranges::copy(points.subspan(2 * row, 2), p.begin());
    return p;
}

double value(Scalars values, std::size_t row) {
    return values.subspan(row, 1).front();
}

} // namespace

void init_exact_arithmetic() {
    exactinit();
}

void two_sums(const ValuePairs& in, const ErrorFreePairs& out) {
    for (std::size_t row = 0; row < out.x.size(); ++row) {
        const auto [x, y] = two_sum(value(in.a, row), value(in.b, row));
        out.x.subspan(row, 1).front() = x;
        out.y.subspan(row, 1).front() = y;
    }
}

void two_products(const ValuePairs& in, const ErrorFreePairs& out) {
    for (std::size_t row = 0; row < out.x.size(); ++row) {
        const auto [x, y] = two_product(value(in.a, row), value(in.b, row));
        out.x.subspan(row, 1).front() = x;
        out.y.subspan(row, 1).front() = y;
    }
}

int orient_sign(Point2 a, Point2 b, Point2 c) {
    return sign_of(orient2d(a.data(), b.data(), c.data()));
}

int arc_circle_sign(Point2 q, const CircleAt& circle) {
    const auto [qx, qy] = q;
    const auto [cx, cy] = circle.centre;
    const auto [px, py] = circle.p0;
    const Expansion radius =
        sum(squared_difference(px, cx, false), squared_difference(py, cy, false));
    const Expansion distance =
        sum(squared_difference(qx, cx, true), squared_difference(qy, cy, true));
    return sign_of(sum(radius, distance));
}

int vertical_extent_sign(double q_y, const CircleAt& circle) {
    const auto [cx, cy] = circle.centre;
    const auto [px, py] = circle.p0;
    const Expansion height = squared_difference(q_y, cy, false);
    const Expansion radius =
        sum(squared_difference(px, cx, true), squared_difference(py, cy, true));
    return sign_of(sum(height, radius));
}

void orient2d_signs(const std::array<Points, 3>& abc, Signs out) {
    std::size_t row = 0;
    for (std::int8_t& sign : out) {
        sign = static_cast<std::int8_t>(orient_sign(point(std::get<0>(abc), row),
                                                    point(std::get<1>(abc), row),
                                                    point(std::get<2>(abc), row)));
        ++row;
    }
}

void incircle_signs(const std::array<Points, 4>& abcd, Signs out) {
    std::size_t row = 0;
    for (std::int8_t& sign : out) {
        auto pa = point(std::get<0>(abcd), row);
        auto pb = point(std::get<1>(abcd), row);
        auto pc = point(std::get<2>(abcd), row);
        auto pd = point(std::get<3>(abcd), row);
        sign =
            static_cast<std::int8_t>(sign_of(incircle(pa.data(), pb.data(), pc.data(), pd.data())));
        ++row;
    }
}

void in_arc_circle_signs(const ArcQueries& in, Signs out) {
    std::size_t row = 0;
    for (std::int8_t& sign : out) {
        sign = static_cast<std::int8_t>(
            arc_circle_sign(point(in.q, row), {point(in.centre, row), point(in.p0, row)}));
        ++row;
    }
}

void vertical_extent_signs(const HeightQueries& in, Signs out) {
    std::size_t row = 0;
    for (std::int8_t& sign : out) {
        sign = static_cast<std::int8_t>(
            vertical_extent_sign(value(in.q_y, row), {point(in.centre, row), point(in.p0, row)}));
        ++row;
    }
}

void circles_through(const std::array<Points, 3>& p123, double length_eps_mm,
                     const CircleOut& out) {
    std::size_t row = 0;
    for (std::int8_t& found : out.found) {
        auto p1 = point(std::get<0>(p123), row);
        auto p2 = point(std::get<1>(p123), row);
        auto p3 = point(std::get<2>(p123), row);
        // D's sign is exact; D = 0 also when p1 = p3, so nothing below divides by a zero chord.
        const double d = orient2d(p1.data(), p2.data(), p3.data());
        const auto [x1, y1] = p1;
        const auto [x2, y2] = p2;
        const auto [x3, y3] = p3;
        const double ux = x1 - x3;
        const double uy = y1 - y3;
        // |D| / |p3 − p1| is p2's distance from the line p1p3, compared without a division; false
        // when D = 0. Lengths are sqrt of a sum of squares, correctly rounded on every platform
        // (D-055 tier 1), as in arcs.cpp.
        found =
            static_cast<std::int8_t>(std::abs(d) > length_eps_mm * std::sqrt(ux * ux + uy * uy));
        if (found != 0) {
            const double vx = x2 - x3;
            const double vy = y2 - y3;
            const double u2 = ux * ux + uy * uy;
            const double v2 = vx * vx + vy * vy;
            const double cx = x3 - (uy * v2 - vy * u2) / (d + d);
            const double cy = y3 + (ux * v2 - vx * u2) / (d + d);
            std::ranges::copy(std::array{cx, cy}, out.centres.subspan(2 * row, 2).begin());
            const double rx = x1 - cx;
            const double ry = y1 - cy;
            out.radii.subspan(row, 1).front() = std::sqrt(rx * rx + ry * ry);
        }
        ++row;
    }
}

void ExactSum::add(const CrossTerm& term) {
    Expansion part = sum(of(two_product(term.a, term.b)), of(two_product(-term.c, term.d)));
    add(part.parts.data(), part.size);
}

void ExactSum::add(double* parts, int count) {
    // Above this many components the expansion is compressed (predicates.c's compress, SRC-032),
    // which keeps it short in practice, so each add stays cheap (ours): a speed setting, no
    // tolerance, so not a declared parameter (REQ-G2D-230).
    constexpr int compress_above = 64;
    const std::size_t needed = static_cast<std::size_t>(size_ + count) + 2;
    if (next_.size() < needed) {
        next_.resize(2 * needed, 0.0);
    }
    size_ = fast_expansion_sum_zeroelim(size_, parts_.data(), count, parts, next_.data());
    std::swap(parts_, next_);
    if (size_ > compress_above) {
        size_ = compress(size_, parts_.data(), parts_.data());
    }
}

double ExactSum::value() const {
    const auto parts = std::span(parts_).first(static_cast<std::size_t>(size_));
    return std::accumulate(parts.begin(), parts.end(), 0.0);
}

namespace {

// Adds e·f to the sum, exactly: e scaled by each component of f (predicates.c's
// scale_expansion_zeroelim, SRC-032 Theorem 19).
void add_product(ExactSum& total, Expansion e, const Expansion& f) {
    for (const double component : std::span(f.parts).first(static_cast<std::size_t>(f.size))) {
        std::array<double, 2 * expansion_capacity + 1> scaled{};
        const int count =
            scale_expansion_zeroelim(e.size, e.parts.data(), component, scaled.data());
        total.add(scaled.data(), count);
    }
}

Expansion negated(Expansion e) {
    for (double& part : e.parts) {
        part = -part;
    }
    return e;
}

} // namespace

int ray_height_sign(double q_y, const CircleAt& circle, Point2 toward) {
    const auto [cx, cy] = circle.centre;
    const auto [tx, ty] = toward;
    const auto [px, py] = circle.p0;
    const int q_side = (q_y > cy) - (q_y < cy);
    const int ray_side = (ty > cy) - (ty < cy);
    if (q_side != ray_side) { // on opposite sides of c_y, or one of them on it
        return q_side > ray_side ? 1 : -1;
    }
    if (q_side == 0) {
        return 0;
    }
    // |q_y − c_y| against |Q_y − c_y| = r·|t_y − c_y| / |t − c|, squared and multiplied out.
    ExactSum difference;
    add_product(difference, squared_difference(q_y, cy, false),
                sum(squared_difference(tx, cx, false), squared_difference(ty, cy, false)));
    add_product(difference, negated(squared_difference(ty, cy, false)),
                sum(squared_difference(px, cx, false), squared_difference(py, cy, false)));
    return q_side * sign_of(difference.value());
}

} // namespace splintercam::geometry2d

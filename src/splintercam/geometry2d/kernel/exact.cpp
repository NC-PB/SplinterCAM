// SPDX-License-Identifier: Apache-2.0
// Exact signs (research 01, Vectors and exact signs). orient2d and incircle are Shewchuk's adaptive
// predicates (SRC-032, vendored predicates.c, ADR 0009). The arc predicates are ours (research 01),
// evaluated every time with SRC-032's expansion arithmetic: each squared difference (a − b)² is
// expanded exactly from two_diff and two_product (Theorems 7, 17, 18) and the terms are summed by
// predicates.c's fast_expansion_sum_zeroelim (Theorem 13), whose largest component has the sign of
// the exact sum. Exact within the input range of the SPEC's precondition (SRC-032, p. 308).
#include "exact.hpp"

#include "shewchuk.hpp"

#include <algorithm>
#include <array>

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

std::int8_t sign_of(double value) {
    return static_cast<std::int8_t>((value > 0.0) - (value < 0.0));
}

std::int8_t sign_of(const Expansion& e) {
    return sign_of(e.parts.at(static_cast<std::size_t>(std::max(e.size - 1, 0))));
}

std::array<double, 2> point(Points points, std::size_t row) {
    std::array<double, 2> p{};
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

void orient2d_signs(const std::array<Points, 3>& abc, Signs out) {
    std::size_t row = 0;
    for (std::int8_t& sign : out) {
        auto pa = point(std::get<0>(abc), row);
        auto pb = point(std::get<1>(abc), row);
        auto pc = point(std::get<2>(abc), row);
        sign = sign_of(orient2d(pa.data(), pb.data(), pc.data()));
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
        sign = sign_of(incircle(pa.data(), pb.data(), pc.data(), pd.data()));
        ++row;
    }
}

void in_arc_circle_signs(const ArcQueries& in, Signs out) {
    std::size_t row = 0;
    for (std::int8_t& sign : out) {
        const auto [qx, qy] = point(in.q, row);
        const auto [cx, cy] = point(in.centre, row);
        const auto [px, py] = point(in.p0, row);
        const Expansion radius =
            sum(squared_difference(px, cx, false), squared_difference(py, cy, false));
        const Expansion distance =
            sum(squared_difference(qx, cx, true), squared_difference(qy, cy, true));
        sign = sign_of(sum(radius, distance));
        ++row;
    }
}

void vertical_extent_signs(const HeightQueries& in, Signs out) {
    std::size_t row = 0;
    for (std::int8_t& sign : out) {
        const auto [cx, cy] = point(in.centre, row);
        const auto [px, py] = point(in.p0, row);
        const Expansion height = squared_difference(value(in.q_y, row), cy, false);
        const Expansion radius =
            sum(squared_difference(px, cx, true), squared_difference(py, cy, true));
        sign = sign_of(sum(height, radius));
        ++row;
    }
}

} // namespace splintercam::geometry2d

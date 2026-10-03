// SPDX-License-Identifier: Apache-2.0
// Exact signs (research 01, Vectors and exact signs). orient2d and incircle are Shewchuk's adaptive
// predicates (SRC-032, vendored predicates.c, ADR 0009), exact within the input range of the SPEC's
// precondition (p. 308). two_sum and two_product are SRC-032's error-free transformations.
#include "exact.hpp"

#include "shewchuk.hpp"

#include <algorithm>
#include <array>

namespace splintercam::geometry2d {
namespace {

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

std::int8_t sign_of(double value) {
    return static_cast<std::int8_t>((value > 0.0) - (value < 0.0));
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

} // namespace splintercam::geometry2d

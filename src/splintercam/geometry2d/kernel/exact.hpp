// SPDX-License-Identifier: Apache-2.0
// Exact signs (research 01, Vectors and exact signs; D-097): Shewchuk's orient2d and incircle from
// the vendored predicates.c.
#pragma once

#include <array>
#include <cstdint>
#include <span>

namespace splintercam::geometry2d {

// One planar point per two doubles: (x, y) pairs, row after row.
using Points = std::span<const double>;
using Scalars = std::span<const double>;
using Signs = std::span<std::int8_t>;

struct ValuePairs { // a and b, one value per row
    Scalars a;
    Scalars b;
};
struct ErrorFreePairs { // x the rounded result, y its rounding error, one per row
    std::span<double> x;
    std::span<double> y;
};
// Error-free transformations (SRC-032, Theorems 7 and 18): x + y equals a + b, or a·b, exactly.
// Batches for the build guard of REQ-G2D-016: they compile with the kernel's strict float flags.
void two_sums(const ValuePairs& in, const ErrorFreePairs& out);
void two_products(const ValuePairs& in, const ErrorFreePairs& out);

// Per row, the exact sign of orient2d(a, b, c): +1 when c lies left of a → b (REQ-G2D-007).
void orient2d_signs(const std::array<Points, 3>& abc, Signs out);
// incircle(a, b, c, d): +1 when d lies inside the circle through a, b, c given CCW (REQ-G2D-011).
void incircle_signs(const std::array<Points, 4>& abcd, Signs out);

// Starts predicates.c's error bounds; called once when the kernel module loads (REQ-G2D-013).
void init_exact_arithmetic();

} // namespace splintercam::geometry2d

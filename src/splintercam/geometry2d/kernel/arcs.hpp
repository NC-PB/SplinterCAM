// SPDX-License-Identifier: Apache-2.0
// The arc rules of research 01, Curves (D-057): which arc rows are consistent.
#pragma once

#include <cstdint>
#include <span>

namespace splintercam::geometry2d {

// Columns of a curve row (research 01, Kernel arrays): x0, y0, x1, y1, cx, cy, sweep.
inline constexpr std::size_t row_width = 7;

// One curve row; a line has sweep 0 and a NaN centre (research 01, trap 13).
struct CurveRow {
    double x0, y0, x1, y1, cx, cy, sweep;
};

// The row starting at the front of `row`, which holds at least row_width values.
[[nodiscard]] CurveRow unpack_row(std::span<const double> row);

enum class ArcCheck : std::int8_t { consistent = 0, off_circle = 1, sweep_mismatch = 2 };

// For each row of `rows` (row_width doubles each, finite, 0 < |sweep| <= 2π for arcs) writes to
// `out` whether the arc's P1 lies within eps_len of its circle of radius |P0 − C| and its angle
// from P0, in the sense of the sweep, equals |sweep| modulo 2π within eps_len / r (REQ-G2D-042,
// 043). Line rows (sweep 0) are consistent.
void check_arcs(std::span<const double> rows, double length_eps_mm, std::span<std::int8_t> out);

} // namespace splintercam::geometry2d

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

// The array forms of DEC-G2D-044: ports of arc_from_bulge, make_arc and bounding_box that stay
// bit-identical to them.

// The end points of n rows and per row a DXF bulge or a sweep in radians.
struct EndRows {
    std::span<const double> points0; // n × 2
    std::span<const double> points1; // n × 2
    std::span<const double> values;  // n
    bool values_are_sweeps;
};

// What became of a row; the codes match the per-curve diagnostics (REQ-G2D-243).
enum class RowStatus : std::int8_t { ok = 0, curve_invalid = 1, arc_inconsistent = 2 };

// The rows built from `ends` into `rows` (n × row_width) and their status into `status` (n): a
// line (NaN centre, sweep 0), an arc or a full circle; a failed row is all NaN. A bulge b gives
// the arc of `arc_from_bulge`; a sweep φ gives the arc of the bulge tan(φ/4) with φ kept as its
// sweep, and φ not finite, 0 or |φ| >= 2π is invalid (REQ-G2D-243, 244).
void rows_from_ends(const EndRows& ends, double length_eps_mm, std::span<double> rows,
                    std::span<std::int8_t> status);

// Per curve row the box [x_min, y_min, x_max, y_max] of `bounding_box` into `boxes` (m × 4)
// (REQ-G2D-245). The octant test is a copy of _box.py's (geometry2d AGENTS.md, sweep tests).
void row_boxes(std::span<const double> rows, std::span<double> boxes);

} // namespace splintercam::geometry2d

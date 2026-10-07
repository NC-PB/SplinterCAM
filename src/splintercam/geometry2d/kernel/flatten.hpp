// SPDX-License-Identifier: Apache-2.0
// Flattening an arc with a known error side (research 01, Flattening with a known error side).
#pragma once

#include "arcs.hpp"

#include <cstdint>
#include <span>

namespace splintercam::geometry2d {

// The number of steps n of an arc flattened within t, inscribed or circumscribed, with the step
// at most max_step_rad (REQ-G2D-102, 104, 106, 109). Its angles come from basic_atan2, so the count
// is the same on every platform (D-055). -1 when the count does not fit an int (t far too small).
[[nodiscard]] int arc_steps(const CurveRow& arc, double t_mm, bool inscribed, double max_step_rad);

// The flattened arc in n steps as (x, y) pairs: n + 1 points inscribed, n + 2 circumscribed,
// starting at P0 and ending at P1 bit for bit (REQ-G2D-103, 105, 112). `out` holds exactly that.
void flatten_arc(const CurveRow& arc, int steps, bool inscribed, std::span<double> out);

// The tolerance and the largest step of a flattening (REQ-G2D-106, 230).
struct FlattenLimits {
    double t_mm;
    double max_step_rad;
};

// Per row of closed loops, the vertices it adds to its flattened loop: 1 for a line, n inscribed
// or n + 1 circumscribed for an arc, its flattening without P1, which the next row starts with
// (REQ-G2D-199). -1 when n does not fit an int. `inscribed` has one flag per row.
void row_vertex_counts(std::span<const double> rows, std::span<const std::uint8_t> inscribed,
                       FlattenLimits limits, std::span<std::int64_t> out);

// Writes each row's vertices after the previous row's, `counts` from row_vertex_counts; `out`
// holds exactly 2·Σ counts doubles. An arc's vertices are those of flatten_arc, bit for bit.
void flatten_rows(std::span<const double> rows, std::span<const std::uint8_t> inscribed,
                  std::span<const std::int64_t> counts, std::span<double> out);

} // namespace splintercam::geometry2d

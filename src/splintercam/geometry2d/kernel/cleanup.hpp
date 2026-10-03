// SPDX-License-Identifier: Apache-2.0
// Cleanup of a closed polyline (research 01, Helpers).
#pragma once

#include <cstdint>
#include <span>

namespace splintercam::geometry2d {

enum class Kept : std::int8_t { dropped = 0, kept = 1, spike = 2 };

// Per vertex of `points` ((x, y) pairs) whether cleanup keeps it, drops it, or drops it as a
// zero-width spike (REQ-G2D-020, 204 to 212).
void cleanup_loop(std::span<const double> points, double length_eps_mm,
                  std::span<std::int8_t> status);

} // namespace splintercam::geometry2d

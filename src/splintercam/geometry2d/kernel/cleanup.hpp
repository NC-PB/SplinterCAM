// SPDX-License-Identifier: Apache-2.0
// Cleanup of a closed polyline (research 01, Helpers).
#pragma once

#include <cstdint>
#include <span>

namespace splintercam::geometry2d {

struct CleanupOut {
    std::span<std::int8_t> keep;  // per vertex: 1 kept, 0 dropped
    std::span<std::int8_t> spike; // per vertex: 1 where a zero-width spike was dropped
};

// Merges runs within length_eps_mm, drops exactly collinear vertices and zero-width spikes, until
// nothing changes (REQ-G2D-020, 204 to 212). `points` holds (x, y) pairs.
void cleanup_loop(std::span<const double> points, double length_eps_mm, const CleanupOut& out);

} // namespace splintercam::geometry2d

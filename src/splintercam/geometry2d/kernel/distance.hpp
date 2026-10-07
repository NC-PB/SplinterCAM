// SPDX-License-Identifier: Apache-2.0
// Distances to segments and closed polylines (research 01, Distances; Loop tree, rules 3, 5).
#pragma once

#include "exact.hpp"

#include <cstdint>
#include <span>

namespace splintercam::geometry2d {

// |(dx, dy)| from correctly rounded operations only, so the same everywhere (never libm hypot).
[[nodiscard]] double length(double dx, double dy);

// The distance from q to the segment ab, taken from both ends and the smaller kept, so it does not
// depend on the segment's direction (DEC-G2D-013).
[[nodiscard]] double segment_distance(Point2 q, Point2 a, Point2 b);

// Closed polylines: (x, y) pairs and the first vertex of each loop, its last vertex joined back.
struct Polylines {
    std::span<const double> points;
    std::span<const std::int64_t> loop_starts;
};

// Per query point (x, y pairs) the distance to the nearest segment of `lines` where it is at most
// `limit` (> 0), and +inf elsewhere.
void polyline_distances(std::span<const double> q, const Polylines& lines, double limit,
                        std::span<double> out);

} // namespace splintercam::geometry2d

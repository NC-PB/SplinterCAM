// SPDX-License-Identifier: Apache-2.0
// Distances to segments and closed polylines (research 01, Distances; Loop tree, rules 3, 5).
#pragma once

#include "exact.hpp"

#include <cstdint>
#include <span>
#include <vector>

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

// Whether polyline set `a` reaches more than `limit` into the region of `b` (inside) and more
// than `limit` out of it (outside): a point of a's segments farther than `limit` from every
// segment of b, classified by point in region against b (REQ-G2D-237).
struct Depth {
    bool inside = false;
    bool outside = false;
};
[[nodiscard]] Depth crossing_depth(const Polylines& a, const Polylines& b, double limit);

// The points where the segments of `a` and `b` meet, by exact signs: proper crossings (their
// constructed point) and ends lying on the other segment; sorted by x, then y, unique
// (REQ-G2D-160). `limit` (> 0) sizes the search grid only.
[[nodiscard]] std::vector<Point2> contact_points(const Polylines& a, const Polylines& b,
                                                 double limit);

} // namespace splintercam::geometry2d

// SPDX-License-Identifier: Apache-2.0
// Point in region (research 01, Point in region): the exact layer.
#pragma once

#include <cstdint>
#include <span>

namespace splintercam::geometry2d {

enum class Location : std::int8_t { out = 0, in = 1, on = 2 };

struct RegionQuery {
    std::span<const double> rows; // the curve rows of all loops, row_width doubles each
};

// Per query point (x, y pairs) its location against all loops: ON on an edge, else IN where the
// winding number is not 0 (REQ-G2D-135 to 145).
void point_locations(std::span<const double> points, const RegionQuery& query,
                     std::span<std::int8_t> out);

} // namespace splintercam::geometry2d

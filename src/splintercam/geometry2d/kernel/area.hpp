// SPDX-License-Identifier: Apache-2.0
// The signed area of one loop of curve rows (research 01, Area and orientation).
#pragma once

#include <span>

namespace splintercam::geometry2d {

struct LoopFrame { // where the sums are taken from, and whether the polygon part is exact
    double centre_x;
    double centre_y;
    bool exact;
};
struct LoopSums {
    double area;   // A in mm², positive for a counter-clockwise loop
    double length; // L in mm
};

// The signed area of one closed loop of rows (row_width doubles each) and its length (REQ-G2D-128,
// 130 to 132).
[[nodiscard]] LoopSums loop_area(std::span<const double> rows, const LoopFrame& frame);

} // namespace splintercam::geometry2d

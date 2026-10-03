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

// A = ½ Σ (x_i y_{i+1} − x_{i+1} y_i) + Σ_arcs ½ r² (φ − sin φ) over the rows of one closed loop
// (row_width doubles each), the polygon part taken about the frame's centre (REQ-G2D-128, 130 to
// 132), and the loop's length.
[[nodiscard]] LoopSums loop_area(std::span<const double> rows, const LoopFrame& frame);

} // namespace splintercam::geometry2d

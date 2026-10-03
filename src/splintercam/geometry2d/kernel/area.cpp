// SPDX-License-Identifier: Apache-2.0
// The signed area of a loop by Green's theorem (research 01, Area and orientation, ours): the
// polygon sum over the end points of all rows plus each arc's circular segment ½ r² (φ − sin φ).
// The polygon part is taken about the centre of the loop's bounding box, which keeps its rounding
// error below eps_len·L for n ≤ 10^6 vertices and a half-extent up to 3355 mm; beyond, it is summed
// exactly with SRC-032's expansion arithmetic. Lengths are sqrt of a sum of squares.
#include "area.hpp"

#include "arcs.hpp"
#include "exact.hpp"

#include <cmath>

namespace splintercam::geometry2d {

LoopSums loop_area(std::span<const double> rows, const LoopFrame& frame) {
    double polygon = 0.0; // twice the polygon part, when summed in floating point
    ExactSum exact_polygon;
    double segments = 0.0;
    double length = 0.0;
    for (std::size_t start = 0; start < rows.size(); start += row_width) {
        const CurveRow row = unpack_row(rows.subspan(start, row_width));
        const CrossTerm term{.a = row.x0 - frame.centre_x,
                             .b = row.y1 - frame.centre_y,
                             .c = row.x1 - frame.centre_x,
                             .d = row.y0 - frame.centre_y};
        if (frame.exact) {
            exact_polygon.add(term);
        } else {
            polygon += term.a * term.b - term.c * term.d;
        }
        if (row.sweep == 0.0) {
            const double dx = row.x1 - row.x0;
            const double dy = row.y1 - row.y0;
            length += std::sqrt(dx * dx + dy * dy);
        } else {
            const double ax = row.x0 - row.cx;
            const double ay = row.y0 - row.cy;
            const double r2 = ax * ax + ay * ay;
            segments += r2 * (row.sweep - std::sin(row.sweep)) / 2;
            length += std::sqrt(r2) * std::abs(row.sweep);
        }
    }
    if (frame.exact) {
        polygon = exact_polygon.value();
    }
    return {.area = polygon / 2 + segments, .length = length};
}

} // namespace splintercam::geometry2d

// SPDX-License-Identifier: Apache-2.0
// The signed area of a loop by Green's theorem (research 01, Area and orientation, ours), the
// polygon part taken about the centre of the end points' bounding box. On the exact path the
// polygon terms and the rounded segment terms are summed exactly (SRC-032's expansion arithmetic).
// The segment term and the lengths use basic operations only, so |A| <= eps_len·L decides the same
// on every platform (REQ-G2D-018).
#include "area.hpp"

#include "angle.hpp"
#include "arcs.hpp"
#include "exact.hpp"

#include <cmath>

namespace splintercam::geometry2d {

LoopSums loop_area(std::span<const double> rows, const LoopFrame& frame) {
    double polygon = 0.0;   // twice the polygon part, when summed in floating point
    ExactSum exact_polygon; // the polygon and segment terms, doubled, on the exact path
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
            const double segment = r2 * phi_minus_sin(row.sweep) / 2;
            if (frame.exact) { // twice the segment, like the polygon terms
                exact_polygon.add({.a = segment + segment, .b = 1.0, .c = 0.0, .d = 0.0});
            } else {
                segments += segment;
            }
            length += std::sqrt(r2) * std::abs(row.sweep);
        }
    }
    if (frame.exact) {
        polygon = exact_polygon.value();
    }
    return {.area = polygon / 2 + segments, .length = length};
}

} // namespace splintercam::geometry2d

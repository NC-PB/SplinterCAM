// SPDX-License-Identifier: Apache-2.0
// The signed area of a loop by Green's theorem (research 01, Area and orientation, ours), the
// polygon part taken about the centre of the end points' bounding box. The rounded segment terms
// are always summed exactly (SRC-032's expansion arithmetic), so their error bound has no factor
// of the arc count (DEC-G2D-016); on the exact path the polygon terms join them.
// The segment term and the lengths use basic operations only, so |A| <= eps_len·L decides the same
// on every platform (REQ-G2D-018).
#include "area.hpp"

#include "angle.hpp"
#include "arcs.hpp"
#include "exact.hpp"

#include <cmath>

namespace splintercam::geometry2d {

LoopSums loop_area(std::span<const double> rows, const LoopFrame& frame) {
    double polygon = 0.0; // twice the polygon part, when summed in floating point
    ExactSum exact_sum;   // twice the segment terms; on the exact path the polygon terms too
    double length = 0.0;
    for (std::size_t start = 0; start < rows.size(); start += row_width) {
        const CurveRow row = unpack_row(rows.subspan(start, row_width));
        const CrossTerm term{.a = row.x0 - frame.centre_x,
                             .b = row.y1 - frame.centre_y,
                             .c = row.x1 - frame.centre_x,
                             .d = row.y0 - frame.centre_y};
        if (frame.exact) {
            exact_sum.add(term);
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
            // r²·(φ − sin φ), the product formed exactly too (DEC-G2D-016).
            exact_sum.add({.a = r2, .b = phi_minus_sin(row.sweep), .c = 0.0, .d = 0.0});
            length += std::sqrt(r2) * std::abs(row.sweep);
        }
    }
    return {.area = (polygon + exact_sum.value()) / 2, .length = length};
}

} // namespace splintercam::geometry2d

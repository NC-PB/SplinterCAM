// SPDX-License-Identifier: Apache-2.0
// Point in region (research 01, Point in region; ours, from the SRC-032 note's mapping). The exact
// layer sums a winding number from a ray to the right of q: each arc is split at its highest and
// lowest point into pieces monotone in y, found from the exact quadrants of P0 and P1 about C; an
// edge or piece counts when q_y lies in its half-open height range and it passes strictly right
// of q, decided by orient2d or by the arc predicate and the sign of q_x − c_x. Only the exact
// predicates decide, so the layer is exact. The tolerance layer adds ON within eps_len, with the
// distances of research 01, Distances and closest points.
#include "region.hpp"

#include "arcs.hpp"
#include "exact.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <numbers>

namespace splintercam::geometry2d {
namespace {

constexpr double two_pi = 2 * std::numbers::pi;
constexpr int octants = 8;

double x(Point2 p) {
    return std::get<0>(p);
}

double y(Point2 p) {
    return std::get<1>(p);
}

int sign(double a, double b) {
    return (a > b) - (a < b);
}

bool on_line(Point2 q, Point2 a, Point2 b) {
    return orient_sign(a, b, q) == 0 && std::min(x(a), x(b)) <= x(q) &&
           x(q) <= std::max(x(a), x(b)) && std::min(y(a), y(b)) <= y(q) &&
           y(q) <= std::max(y(a), y(b));
}

int line_winding(Point2 q, Point2 a, Point2 b) {
    const bool up = y(a) < y(b);
    const double low = up ? y(a) : y(b);
    const double high = up ? y(b) : y(a);
    if (y(q) < low || y(q) >= high) { // also every horizontal edge
        return 0;
    }
    const int side = orient_sign(a, b, q); // +1: q left of a → b
    if (up) {
        return side > 0 ? 1 : 0;
    }
    return side < 0 ? -1 : 0;
}

// The direction of p − c as an octant, as in _box.py: 0 on +x, odd inside a quadrant, even on an
// axis, counter-clockwise; mirrored in y for a clockwise arc, so its sweep runs counter-clockwise.
int octant(Point2 p, Point2 c, bool mirrored) {
    const int sx = sign(x(p), x(c));
    const int sy = mirrored ? -sign(y(p), y(c)) : sign(y(p), y(c));
    constexpr std::array<int, 9> by_signs = {5, 4, 3, 6, 0, 2, 7, 0, 1}; // index 3·(sx+1) + sy+1
    const int index = 3 * (sx + 1) + sy + 1;
    return by_signs.at(static_cast<std::size_t>(index));
}

// A piece end: a point of the row (its y) or the circle's top or bottom (c_y ± r, not a double).
struct End {
    double y;
    int extreme; // 0: the point y; +1: the top; −1: the bottom
};

struct Arc {
    Point2 p0, p1, c;
    double sweep;
};

// The sign of y minus the height of an end, exactly: c_y ± r through the sign of (y − c_y)² − r².
int compare(double height, const End& end, const Arc& arc) {
    if (end.extreme == 0) {
        return sign(height, end.y);
    }
    if (end.extreme > 0) { // the top: below c_y it is above, else the comparison of squares
        return height < y(arc.c) ? -1 : vertical_extent_sign(height, {arc.c, arc.p0});
    }
    return height > y(arc.c) ? 1 : -vertical_extent_sign(height, {arc.c, arc.p0});
}

// The sign of a's height minus b's.
int compare(const End& a, const End& b, const Arc& arc) {
    if (a.extreme == 0) {
        return compare(a.y, b, arc);
    }
    if (b.extreme == 0) {
        return -compare(b.y, a, arc);
    }
    return sign(a.extreme, b.extreme);
}

// +1 or −1 when q_y lies in the half-open height range of a piece from one end to the other, which
// goes up or down by its ends' heights, so a piece that P1 off the circle (REQ-G2D-042) takes
// past the top or bottom still joins the next row without a gap in height; else 0.
int piece_winding(double q_y, const std::array<End, 2>& ends, const Arc& arc) {
    const auto& [from, to] = ends;
    const int rise = compare(to, from, arc);
    const End& low = rise > 0 ? from : to;
    const End& high = rise > 0 ? to : from;
    return rise != 0 && compare(q_y, low, arc) >= 0 && compare(q_y, high, arc) < 0 ? rise : 0;
}

// The points where the arc is split, in the order it passes them: the octants 2 and 6 (its top
// and bottom in the mirrored frame) that the sweep passes, by the rules of _box.py, where the
// sweep governs near 0 and near a full turn (REQ-G2D-043).
struct Splits {
    std::array<int, 2> octant{};
    std::size_t count = 0;
};

Splits arc_splits(int start, int end, double sweep) {
    const int reach = (end - start + octants) % octants;
    const bool all = sweep == two_pi || (start == end && sweep > std::numbers::pi) ||
                     (sweep > 3 * std::numbers::pi / 2 && reach <= 4);
    const bool none = !all && (start == end || (sweep < std::numbers::pi / 2 && reach >= 4));
    Splits splits;
    if (none) {
        return splits;
    }
    // From the start, counter-clockwise: the distances of the top and the bottom.
    const int to_top = (2 - start + octants) % octants;
    const int to_bottom = (6 - start + octants) % octants;
    for (const int axis : to_top <= to_bottom ? std::array{2, 6} : std::array{6, 2}) {
        if (all || (axis == 2 ? to_top : to_bottom) <= reach) {
            splits.octant.at(splits.count++) = axis;
        }
    }
    return splits;
}

int arc_winding(Point2 q, const Arc& arc) {
    const bool mirrored = arc.sweep < 0.0;
    const int end_octant = octant(arc.p1, arc.c, mirrored);
    int from_octant = octant(arc.p0, arc.c, mirrored);
    const Splits splits = arc_splits(from_octant, end_octant, std::abs(arc.sweep));
    // Whether the circle crosses the ray right of q on its left and on its right half.
    const int circle = arc_circle_sign(q, {arc.c, arc.p0});              // +1 inside
    const std::array<bool, 2> crosses = {x(q) < x(arc.c) && circle < 0,  // left half
                                         x(q) < x(arc.c) || circle > 0}; // right half
    int winding = 0;
    End from{y(arc.p0), 0};
    for (std::size_t piece = 0; piece <= splits.count; ++piece) {
        const bool last = piece == splits.count;
        const int to_octant = last ? end_octant : splits.octant.at(piece);
        const End to = last ? End{y(arc.p1), 0} : End{0.0, (to_octant == 2) != mirrored ? 1 : -1};
        // The half from the octant the piece starts in.
        const bool right_half = from_octant >= 6 || from_octant <= 1;
        if (crosses.at(right_half ? 1 : 0)) {
            winding += piece_winding(y(q), {from, to}, arc);
        }
        from = to;
        from_octant = to_octant;
    }
    return winding;
}

bool on_arc(Point2 q, const Arc& arc) {
    if (q == arc.p0 || q == arc.p1) {
        return true;
    }
    if (arc_circle_sign(q, {arc.c, arc.p0}) != 0) {
        return false;
    }
    // On the circle: on the arc when the circle is full or q lies on the arc's side of the chord.
    const int side = orient_sign(arc.p0, arc.p1, q);
    return std::abs(arc.sweep) == two_pi || (arc.sweep > 0.0 ? side < 0 : side > 0);
}

double length(double dx, double dy) {
    return std::sqrt(dx * dx + dy * dy); // correctly rounded operations: the same everywhere
}

double line_distance(Point2 q, Point2 a, Point2 b) {
    const double dx = x(b) - x(a);
    const double dy = y(b) - y(a);
    const double length2 = dx * dx + dy * dy;
    const double t =
        length2 == 0.0 ? 0.0
                       : std::clamp(((x(q) - x(a)) * dx + (y(q) - y(a)) * dy) / length2, 0.0, 1.0);
    return length(x(q) - (x(a) + t * dx), y(q) - (y(a) + t * dy));
}

// 0 when the direction of v − c lies in [0, π) counter-clockwise from that of s − c, else 1.
int half(Point2 s, Point2 c, Point2 v) {
    const int cross = orient_sign(c, s, v);
    if (cross != 0) {
        return cross > 0 ? 0 : 1;
    }
    const std::size_t axis = x(s) != x(c) ? 0 : 1;
    return (v.at(axis) > c.at(axis)) == (s.at(axis) > c.at(axis)) ? 0 : 1;
}

// Whether the direction of q − c lies in the sweep, by exact signs, as closest_point decides it.
bool in_sweep(Point2 q, const Arc& arc) {
    const double sweep = std::abs(arc.sweep);
    if (sweep == two_pi) {
        return true;
    }
    const Point2 s = arc.sweep > 0.0 ? arc.p0 : arc.p1;
    const Point2 e = arc.sweep > 0.0 ? arc.p1 : arc.p0;
    const int end_half = half(s, arc.c, e);
    if (sweep < std::numbers::pi / 2 && end_half == 1) {
        return false;
    }
    if (sweep > 3 * std::numbers::pi / 2 && end_half == 0) {
        return true;
    }
    const int q_half = half(s, arc.c, q);
    return q_half != end_half ? q_half < end_half : orient_sign(arc.c, q, e) >= 0;
}

double arc_distance(Point2 q, const Arc& arc) {
    const double r = length(x(arc.p0) - x(arc.c), y(arc.p0) - y(arc.c));
    if (q == arc.c) {
        return r;
    }
    if (in_sweep(q, arc)) {
        return std::abs(length(x(q) - x(arc.c), y(q) - y(arc.c)) - r);
    }
    return std::min(length(x(q) - x(arc.p0), y(q) - y(arc.p0)),
                    length(x(q) - x(arc.p1), y(q) - y(arc.p1)));
}

struct RowResult {
    bool on;     // q lies on the row
    int winding; // the row's crossings right of q
    bool near;   // the tolerance layer: q within eps_len of the row
};

RowResult against_row(Point2 q, const CurveRow& row, const RegionQuery& query) {
    const Point2 a{row.x0, row.y0};
    const Point2 b{row.x1, row.y1};
    if (row.sweep == 0.0) {
        return {.on = on_line(q, a, b),
                .winding = line_winding(q, a, b),
                .near = query.tolerance_layer && line_distance(q, a, b) <= query.length_eps_mm};
    }
    const Arc arc{a, b, {row.cx, row.cy}, row.sweep};
    return {.on = on_arc(q, arc),
            .winding = arc_winding(q, arc),
            .near = query.tolerance_layer && arc_distance(q, arc) <= query.length_eps_mm};
}

Location locate(Point2 q, const RegionQuery& query) {
    int winding = 0;
    bool near = false;
    for (std::size_t start = 0; start < query.rows.size(); start += row_width) {
        const RowResult result =
            against_row(q, unpack_row(query.rows.subspan(start, row_width)), query);
        if (result.on) {
            return Location::on;
        }
        winding += result.winding;
        near = near || result.near;
    }
    if (near) {
        return Location::on;
    }
    return winding != 0 ? Location::in : Location::out;
}

} // namespace

void point_locations(std::span<const double> points, const RegionQuery& query,
                     std::span<std::int8_t> out) {
    std::size_t row = 0;
    for (std::int8_t& location : out) {
        Point2 q{};
        std::ranges::copy(points.subspan(2 * row, 2), q.begin());
        location = static_cast<std::int8_t>(locate(q, query));
        ++row;
    }
}

} // namespace splintercam::geometry2d

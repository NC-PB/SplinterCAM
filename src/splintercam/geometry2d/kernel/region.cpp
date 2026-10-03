// SPDX-License-Identifier: Apache-2.0
// Point in region (research 01, Point in region; ours, from the SRC-032 note's mapping), decided by
// exact predicates only. An arc runs on the circle of radius |P0 − C| to the ray from C through P1
// and on along that ray to P1, a radial connector when P1 lies off the circle (Peter, 2026-10-03).
// The tolerance layer uses the distances of research 01, Distances and closest points.
#include "region.hpp"

#include "arcs.hpp"
#include "exact.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <numbers>

namespace splintercam::geometry2d {
namespace {

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
    if (y(q) < std::min(y(a), y(b)) || y(q) >= std::max(y(a), y(b))) { // also horizontal edges
        return 0;
    }
    const int side = orient_sign(a, b, q); // +1: q left of a → b
    return y(a) < y(b) ? static_cast<int>(side > 0) : -static_cast<int>(side < 0);
}

// The octant of p − c as in _box.py, mirrored in y for a clockwise arc.
int octant(Point2 p, Point2 c, bool mirrored) {
    const int sx = sign(x(p), x(c));
    const int sy = mirrored ? -sign(y(p), y(c)) : sign(y(p), y(c));
    constexpr std::array<int, 9> by_signs = {5, 4, 3, 6, 0, 2, 7, 0, 1}; // index 3·(sx+1) + sy+1
    const int index = 3 * (sx + 1) + sy + 1;
    return by_signs.at(static_cast<std::size_t>(index));
}

struct Arc {
    Point2 p0, p1, c;
    double sweep;
};

// A piece end: P0, the circle's top or bottom, or where the ray through P1 meets the circle.
enum class EndKind : std::int8_t { point, top, bottom, ray };
struct End {
    EndKind kind;
    double y; // for a point
};

int compare(double height, const End& end, const Arc& arc) {
    switch (end.kind) {
    case EndKind::point:
        return sign(height, end.y);
    case EndKind::top:
        return height < y(arc.c) ? -1 : vertical_extent_sign(height, {arc.c, arc.p0});
    case EndKind::bottom:
        return height > y(arc.c) ? 1 : -vertical_extent_sign(height, {arc.c, arc.p0});
    case EndKind::ray:
        return ray_height_sign(height, {arc.c, arc.p0}, arc.p1);
    }
    return 0;
}

// Top above the ray's end above bottom; the ray's end is an extreme only straight above or below C.
int rank(const End& end, const Arc& arc) {
    if (end.kind == EndKind::ray) {
        return x(arc.p1) == x(arc.c) ? sign(y(arc.p1), y(arc.c)) : 0;
    }
    return end.kind == EndKind::top ? 1 : -1;
}

int compare(const End& a, const End& b, const Arc& arc) {
    if (a.kind == EndKind::point) {
        return compare(a.y, b, arc);
    }
    if (b.kind == EndKind::point) {
        return -compare(b.y, a, arc);
    }
    return sign(rank(a, arc), rank(b, arc));
}

// ±1 when q_y lies in the half-open height range of a monotone piece, by its ends' heights.
int piece_winding(double q_y, const std::array<End, 2>& ends, const Arc& arc) {
    const auto& [from, to] = ends;
    const int rise = compare(to, from, arc);
    const End& low = rise > 0 ? from : to;
    const End& high = rise > 0 ? to : from;
    return rise != 0 && compare(q_y, low, arc) >= 0 && compare(q_y, high, arc) < 0 ? rise : 0;
}

// The octants 2 and 6 the sweep passes, in travel order, by the rules of _box.py (REQ-G2D-043).
struct Splits {
    std::array<int, 2> octant{};
    std::size_t count = 0;
};

Splits arc_splits(int start, int end, double sweep) {
    const int reach = (end - start + octants) % octants;
    const bool all = (start == end && sweep > std::numbers::pi) ||
                     (sweep > 3 * std::numbers::pi / 2 && reach <= 4);
    const bool none = !all && (start == end || (sweep < std::numbers::pi / 2 && reach >= 4));
    Splits splits;
    if (none) {
        return splits;
    }
    const int to_top = (2 - start + octants) % octants;
    const int to_bottom = (6 - start + octants) % octants;
    for (const int axis : to_top <= to_bottom ? std::array{2, 6} : std::array{6, 2}) {
        if (all || (axis == 2 ? to_top : to_bottom) <= reach) {
            splits.octant.at(splits.count++) = axis;
        }
    }
    return splits;
}

// The radial connector from the circle to P1, outward when P1 lies outside the circle.
int connector_winding(Point2 q, const Arc& arc) {
    const int p1_inside = arc_circle_sign(arc.p1, {arc.c, arc.p0});
    const std::array<End, 2> ends = {End{EndKind::ray, 0.0}, End{EndKind::point, y(arc.p1)}};
    const int rise = p1_inside == 0 ? 0 : piece_winding(y(q), ends, arc);
    const int side = -p1_inside * orient_sign(arc.c, arc.p1, q); // +1: q left of the connector
    return rise > 0 ? static_cast<int>(side > 0) : -static_cast<int>(rise < 0 && side < 0);
}

int arc_winding(Point2 q, const Arc& arc) {
    const bool mirrored = arc.sweep < 0.0;
    int from_octant = octant(arc.p0, arc.c, mirrored);
    const int end_octant = octant(arc.p1, arc.c, mirrored);
    const Splits splits = arc_splits(from_octant, end_octant, std::abs(arc.sweep));
    // Whether the circle crosses the ray right of q on each half.
    const int circle = arc_circle_sign(q, {arc.c, arc.p0});              // +1 inside
    const std::array<bool, 2> crosses = {x(q) < x(arc.c) && circle < 0,  // left half
                                         x(q) < x(arc.c) || circle > 0}; // right half
    int winding = connector_winding(q, arc);
    End from{EndKind::point, y(arc.p0)};
    for (std::size_t piece = 0; piece <= splits.count; ++piece) {
        const bool last = piece == splits.count;
        const int to_octant = last ? end_octant : splits.octant.at(piece);
        const bool top = (to_octant == 2) != mirrored;
        const End to{last ? EndKind::ray : (top ? EndKind::top : EndKind::bottom), 0.0};
        const bool right_half = from_octant >= 6 || from_octant <= 1; // where the piece starts
        if (crosses.at(right_half ? 1 : 0)) {
            winding += piece_winding(y(q), {from, to}, arc);
        }
        from = to;
        from_octant = to_octant;
    }
    return winding;
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

bool on_arc(Point2 q, const Arc& arc) {
    if (q == arc.p0 || q == arc.p1) {
        return true;
    }
    const int circle = arc_circle_sign(q, {arc.c, arc.p0});
    if (circle == 0) {
        return in_sweep(q, arc);
    }
    return orient_sign(arc.c, arc.p1, q) == 0 && half(arc.p1, arc.c, q) == 0 &&
           circle * arc_circle_sign(q, {arc.c, arc.p1}) <= 0;
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
    const Point2 foot = t == 0.0 ? a : (t == 1.0 ? b : Point2{x(a) + t * dx, y(a) + t * dy});
    return length(x(q) - x(foot), y(q) - y(foot));
}

// The distance to the nearer of the circles of radius |P0 − C| and |P1 − C| in the sweep, so both
// orientations agree (Peter, 2026-10-03), else to the nearer end point.
double arc_distance(Point2 q, const Arc& arc) {
    const double r0 = length(x(arc.p0) - x(arc.c), y(arc.p0) - y(arc.c));
    const double r1 = length(x(arc.p1) - x(arc.c), y(arc.p1) - y(arc.c));
    if (q == arc.c) {
        return std::min(r0, r1);
    }
    if (in_sweep(q, arc)) {
        const double d = length(x(q) - x(arc.c), y(q) - y(arc.c));
        return std::min(std::abs(d - r0), std::abs(d - r1));
    }
    return std::min(length(x(q) - x(arc.p0), y(q) - y(arc.p0)),
                    length(x(q) - x(arc.p1), y(q) - y(arc.p1)));
}

Location locate(Point2 q, const RegionQuery& query) {
    const double eps = query.length_eps_mm; // 0: the exact layer alone
    int winding = 0;
    for (std::size_t start = 0; start < query.rows.size(); start += row_width) {
        const CurveRow row = unpack_row(query.rows.subspan(start, row_width));
        const Point2 a{row.x0, row.y0};
        const Point2 b{row.x1, row.y1};
        if (row.sweep == 0.0) {
            // Both directions: the feet round differently, and both orientations must agree.
            const double distance = std::min(line_distance(q, a, b), line_distance(q, b, a));
            if (on_line(q, a, b) || (eps > 0.0 && distance <= eps)) {
                return Location::on;
            }
            winding += line_winding(q, a, b);
            continue;
        }
        const Arc arc{a, b, {row.cx, row.cy}, row.sweep};
        if (on_arc(q, arc) || (eps > 0.0 && arc_distance(q, arc) <= eps)) {
            return Location::on;
        }
        winding += arc_winding(q, arc);
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

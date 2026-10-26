// SPDX-License-Identifier: Apache-2.0
// Arc validation (research 01, Curves; D-057). Lengths use sqrt of sums of squares and the angle
// basic_atan2, both from correctly rounded IEEE operations, so both checks decide the same on every
// platform (D-055, tier 1).
#include "arcs.hpp"

#include "angle.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <limits>
#include <numbers>

namespace splintercam::geometry2d {
namespace {

constexpr double pi = std::numbers::pi;
constexpr double two_pi = 2 * std::numbers::pi; // Python's math.tau
constexpr double nan = std::numeric_limits<double>::quiet_NaN();

ArcCheck check_arc(const CurveRow& row, double length_eps_mm) {
    const double ax = row.x0 - row.cx;
    const double ay = row.y0 - row.cy;
    const double bx = row.x1 - row.cx;
    const double by = row.y1 - row.cy;
    const double radius = std::sqrt(ax * ax + ay * ay);
    if (std::abs(std::sqrt(bx * bx + by * by) - radius) > length_eps_mm) {
        return ArcCheck::off_circle;
    }
    // The angle from P0 to P1 about C, in the sense of the sweep, in [0, 2π).
    double angle = basic_atan2(ax * by - ay * bx, ax * bx + ay * by);
    if (row.sweep < 0.0) {
        angle = -angle;
    }
    if (angle < 0.0) {
        angle += two_pi;
    }
    double difference = std::abs(angle - std::abs(row.sweep));
    difference = std::min(difference, two_pi - difference);
    // difference <= eps_len / r, multiplied out so r = 0 needs no division.
    return difference * radius <= length_eps_mm ? ArcCheck::consistent : ArcCheck::sweep_mismatch;
}

struct Xy {
    double x, y;
};

// sqrt of a sum of squares, as _curves.py `distance`: correctly rounded, the same everywhere.
double distance(Xy a, Xy b) {
    const double dx = a.x - b.x;
    const double dy = a.y - b.y;
    return std::sqrt(dx * dx + dy * dy);
}

struct Built {
    RowStatus status;
    CurveRow row;
};

Built failed(RowStatus status) {
    return {.status = status, .row = {nan, nan, nan, nan, nan, nan, nan}};
}

Built line(Xy p0, Xy p1) {
    return {
        .status = RowStatus::ok,
        .row = {
            .x0 = p0.x, .y0 = p0.y, .x1 = p1.x, .y1 = p1.y, .cx = nan, .cy = nan, .sweep = 0.0}};
}

struct ArcInput {
    Xy p0, p1, centre;
    double sweep;
};

// _curves.py `_tiny_arc`: an arc with r <= eps_len. Its empty result (P0 = P1) cannot come from a
// bulge or a sweep, whose zero chord is invalid first; it is invalid here too (ours, REQ-G2D-243).
Built tiny_arc(const ArcInput& arc, double radius, double eps) {
    if (std::abs(distance(arc.p1, arc.centre) - radius) > eps) {
        return failed(RowStatus::arc_inconsistent);
    }
    const bool closed = arc.p0.x == arc.p1.x && arc.p0.y == arc.p1.y;
    return closed ? failed(RowStatus::curve_invalid) : line(arc.p0, arc.p1);
}

// _curves.py `make_arc`, rule for rule in its order (REQ-G2D-037 to 049). The end points and the
// bulge or sweep were checked finite by the caller; the centre may still overflow.
Built make_arc(const ArcInput& arc, double eps) {
    if (!std::isfinite(arc.centre.x) || !std::isfinite(arc.centre.y) || !std::isfinite(arc.sweep)) {
        return failed(RowStatus::curve_invalid);
    }
    if (arc.sweep == 0.0 || std::abs(arc.sweep) > two_pi) {
        return failed(RowStatus::curve_invalid);
    }
    const double radius = distance(arc.p0, arc.centre);
    if (radius <= eps) {
        return tiny_arc(arc, radius, eps);
    }
    const double size = std::abs(arc.sweep);
    const CurveRow row{.x0 = arc.p0.x,
                       .y0 = arc.p0.y,
                       .x1 = arc.p1.x,
                       .y1 = arc.p1.y,
                       .cx = arc.centre.x,
                       .cy = arc.centre.y,
                       .sweep = arc.sweep};
    if (distance(arc.p0, arc.p1) <= eps && size > pi && (two_pi - size) * radius <= eps) {
        CurveRow circle = row;
        circle.x1 = arc.p0.x;
        circle.y1 = arc.p0.y;
        circle.sweep = std::copysign(two_pi, arc.sweep);
        return {.status = RowStatus::ok, .row = circle};
    }
    if (check_arc(row, eps) != ArcCheck::consistent) {
        return failed(RowStatus::arc_inconsistent);
    }
    return {.status = RowStatus::ok, .row = row};
}

// The input of `from_bulge`: the end points, the bulge b and the arc's sweep, 4·atan(b) for a
// bulge and the given φ for a sweep.
struct BulgeInput {
    Xy p0, p1;
    double bulge, sweep;
};

// _bulge.py `arc_from_bulge` from its chord check on (REQ-G2D-044, 050, 051, 243, 244).
Built from_bulge(const BulgeInput& in, double eps) {
    const double chord = distance(in.p0, in.p1);
    if (chord == 0.0 && in.bulge != 0.0) {
        return failed(RowStatus::curve_invalid);
    }
    if (chord * std::abs(in.bulge) / 2 <= eps) {
        return line(in.p0, in.p1);
    }
    // C = M + d·n_left, d = c(1 - b²)/(4b), as d / c without b² overflowing (_bulge.py).
    const double scale = (1.0 / in.bulge - in.bulge) / 4.0;
    const Xy centre{(in.p0.x + in.p1.x) / 2 - scale * (in.p1.y - in.p0.y),
                    (in.p0.y + in.p1.y) / 2 + scale * (in.p1.x - in.p0.x)};
    return make_arc({.p0 = in.p0, .p1 = in.p1, .centre = centre, .sweep = in.sweep}, eps);
}

Built build_row(Xy p0, Xy p1, double value, bool is_sweep, double eps) {
    if (!std::isfinite(p0.x) || !std::isfinite(p0.y) || !std::isfinite(p1.x) ||
        !std::isfinite(p1.y) || !std::isfinite(value)) {
        return failed(RowStatus::curve_invalid);
    }
    if (!is_sweep) {
        constexpr double quarters = 4.0; // φ = 4·atan(b) (research 01, Curves, Bulge)
        return from_bulge(
            {.p0 = p0, .p1 = p1, .bulge = value, .sweep = quarters * std::atan(value)}, eps);
    }
    if (value == 0.0 || std::abs(value) >= two_pi) { // a full circle has no bisector
        return failed(RowStatus::curve_invalid);
    }
    return from_bulge({.p0 = p0, .p1 = p1, .bulge = std::tan(value / 4), .sweep = value}, eps);
}

// _box.py `_octant`: the direction of P − C by exact comparisons of doubles, 0 on the +x axis,
// counter-clockwise, mirrored in y for a clockwise arc; 7 for anything else, P = C included
// (region.cpp's copy gives 0 there, so it cannot be shared).
int octant(Xy point, Xy centre, bool mirrored) {
    const int sx = static_cast<int>(point.x > centre.x) - static_cast<int>(point.x < centre.x);
    const int sy = (static_cast<int>(point.y > centre.y) - static_cast<int>(point.y < centre.y)) *
                   (mirrored ? -1 : 1);
    constexpr std::array<int, 9> by_signs = {5, 4, 3, 6, 7, 2, 7, 0, 1}; // index 3·(sx+1) + sy+1
    const int index = 3 * (sx + 1) + sy + 1;
    return by_signs.at(static_cast<std::size_t>(index));
}

using Axes = std::array<bool, 4>; // passes the axis at 0, π/2, π, 3π/2

// _box.py `_axes_in_sweep`; a mask instead of a sorted list, read in ascending order.
Axes axes_in_sweep(const CurveRow& row) {
    constexpr int octants = 8;
    constexpr int half_turn = 4;
    constexpr Axes all{true, true, true, true};
    const double size = std::abs(row.sweep);
    if (size == two_pi) {
        return all;
    }
    const bool mirrored = row.sweep < 0.0;
    const Xy centre{row.cx, row.cy};
    const int start = octant({row.x0, row.y0}, centre, mirrored);
    const int end = octant({row.x1, row.y1}, centre, mirrored);
    if (start == end) {
        return size > pi ? all : Axes{};
    }
    const int reach = (end - start + octants) % octants;
    if (size < pi / 2 && reach >= half_turn) {
        return {};
    }
    if (size > 3 * pi / 2 && reach <= half_turn) {
        return all;
    }
    Axes passed{};
    for (int axis = 0; axis < half_turn; ++axis) {
        if ((2 * axis - start + octants) % octants <= reach) {
            const int index = mirrored ? (half_turn - axis) % half_turn : axis;
            passed.at(static_cast<std::size_t>(index)) = true;
        }
    }
    return passed;
}

// _box.py `bounding_box`: P0, P1, then the passed extremes in axis order; std::min and std::max
// keep the first of equal values, as Python's min and max do.
std::array<double, 4> row_box(const CurveRow& row) {
    std::array<double, 4> box{row.x0, row.y0, row.x0, row.y0};
    const auto add = [&box](Xy point) {
        box = {std::min(box.at(0), point.x), std::min(box.at(1), point.y),
               std::max(box.at(2), point.x), std::max(box.at(3), point.y)};
    };
    add({row.x1, row.y1});
    if (row.sweep != 0.0) {
        const double r = distance({row.x0, row.y0}, {row.cx, row.cy});
        const std::array<Xy, 4> extremes{{{row.cx + r, row.cy},
                                          {row.cx, row.cy + r},
                                          {row.cx - r, row.cy},
                                          {row.cx, row.cy - r}}};
        const Axes passed = axes_in_sweep(row);
        for (std::size_t axis = 0; axis < extremes.size(); ++axis) {
            if (passed.at(axis)) {
                add(extremes.at(axis));
            }
        }
    }
    return box;
}

// make_arc's checks on a row as given, without its constructions (REQ-G2D-248, DEC-G2D-045): a
// line needs finite ends only; an arc with r <= eps_len is not one make_arc returns.
RowStatus row_status(const CurveRow& row, double eps) {
    const bool ends_finite = std::isfinite(row.x0) && std::isfinite(row.y0) &&
                             std::isfinite(row.x1) && std::isfinite(row.y1);
    if (!ends_finite || row.sweep == 0.0) {
        return ends_finite ? RowStatus::ok : RowStatus::curve_invalid;
    }
    if (!std::isfinite(row.cx) || !std::isfinite(row.cy) || !std::isfinite(row.sweep) ||
        std::abs(row.sweep) > two_pi || distance({row.x0, row.y0}, {row.cx, row.cy}) <= eps) {
        return RowStatus::curve_invalid;
    }
    return check_arc(row, eps) == ArcCheck::consistent ? RowStatus::ok
                                                       : RowStatus::arc_inconsistent;
}

} // namespace

CurveRow unpack_row(std::span<const double> row) {
    std::array<double, row_width> values{};
    std::ranges::copy(row.first(row_width), values.begin());
    const auto [x0, y0, x1, y1, cx, cy, sweep] = values;
    return {.x0 = x0, .y0 = y0, .x1 = x1, .y1 = y1, .cx = cx, .cy = cy, .sweep = sweep};
}

void check_arcs(std::span<const double> rows, double length_eps_mm, std::span<std::int8_t> out) {
    // An index walk, not std::views::chunk, which Apple's libc++ lacks.
    auto row_start = rows.begin();
    for (std::int8_t& check : out) {
        const CurveRow row = unpack_row(std::span(row_start, row_width));
        row_start += row_width;
        const bool is_line = row.sweep == 0.0;
        check = static_cast<std::int8_t>(is_line ? ArcCheck::consistent
                                                 : check_arc(row, length_eps_mm));
    }
}

void check_arc_rows(std::span<const double> rows, double length_eps_mm,
                    std::span<std::int8_t> status) {
    auto row_start = rows.begin();
    for (std::int8_t& code : status) {
        code = static_cast<std::int8_t>(
            row_status(unpack_row(std::span(row_start, row_width)), length_eps_mm));
        row_start += row_width;
    }
}

void rows_from_ends(const EndRows& ends, double length_eps_mm, std::span<double> rows,
                    std::span<std::int8_t> status) {
    auto p0 = ends.points0.begin();
    auto p1 = ends.points1.begin();
    auto value = ends.values.begin();
    auto row_start = rows.begin();
    for (std::int8_t& code : status) {
        const Built built = build_row({*p0, *(p0 + 1)}, {*p1, *(p1 + 1)}, *value,
                                      ends.values_are_sweeps, length_eps_mm);
        const CurveRow& r = built.row;
        std::ranges::copy(std::array{r.x0, r.y0, r.x1, r.y1, r.cx, r.cy, r.sweep}, row_start);
        code = static_cast<std::int8_t>(built.status);
        p0 += 2;
        p1 += 2;
        ++value;
        row_start += row_width;
    }
}

void row_boxes(std::span<const double> rows, std::span<double> boxes) {
    constexpr std::size_t box_width = 4;
    auto box_start = boxes.begin();
    for (auto row_start = rows.begin(); row_start != rows.end(); row_start += row_width) {
        std::ranges::copy(row_box(unpack_row(std::span(row_start, row_width))), box_start);
        box_start += box_width;
    }
}

} // namespace splintercam::geometry2d

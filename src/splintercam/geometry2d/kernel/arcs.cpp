// SPDX-License-Identifier: Apache-2.0
// Arc validation (research 01, Curves; D-057). Lengths use sqrt of sums of squares and the angle
// basic_atan2, both from correctly rounded IEEE operations, so both checks decide the same on every
// platform (D-055, tier 1).
#include "arcs.hpp"

#include "angle.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <numbers>
#include <ranges>

namespace splintercam::geometry2d {
namespace {

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
    constexpr double two_pi = 2 * std::numbers::pi;
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

} // namespace

CurveRow unpack_row(std::span<const double> row) {
    std::array<double, row_width> values{};
    std::ranges::copy(row.first(row_width), values.begin());
    const auto [x0, y0, x1, y1, cx, cy, sweep] = values;
    return {.x0 = x0, .y0 = y0, .x1 = x1, .y1 = y1, .cx = cx, .cy = cy, .sweep = sweep};
}

void check_arcs(std::span<const double> rows, double length_eps_mm, std::span<std::int8_t> out) {
    for (auto [values, check] : std::views::zip(rows | std::views::chunk(row_width), out)) {
        const CurveRow row = unpack_row(std::span(values));
        const bool is_line = row.sweep == 0.0;
        check = static_cast<std::int8_t>(is_line ? ArcCheck::consistent
                                                 : check_arc(row, length_eps_mm));
    }
}

} // namespace splintercam::geometry2d

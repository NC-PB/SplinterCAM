// SPDX-License-Identifier: Apache-2.0
// Arc flattening (research 01, Flattening): the inscribed polygon of the control's own chord rule
// (Altintas 2012, SRC-119, eqs. 5.85-5.86, Table 5.2) and our circumscribed polyline. Vertices are
// P0 − C turned about C, so their distance from C rounds the same way as r = |P0 − C|.
#include "flatten.hpp"

#include "angle.hpp"

#include <algorithm>
#include <cmath>
#include <limits>

namespace splintercam::geometry2d {
namespace {

// The step within t: inscribed 4·asin(√min(1, t/(2r))), circumscribed 2·atan(√(t(2r + t))/r).
double step_within(double radius, double t_mm, bool inscribed) {
    if (inscribed) {
        const double s = std::sqrt(std::min(1.0, t_mm / (2 * radius)));
        return 4 * basic_atan2(s, std::sqrt(1.0 - s * s)); // asin s, without libm
    }
    return 2 * basic_atan2(std::sqrt(t_mm * (2 * radius + t_mm)), radius);
}

// Writes C + R(angle)·(P0 − C)·scale at `out`, the next two places; with `portable`, sin and cos
// from basic operations (REQ-G2D-152), else from libm.
struct Turn {
    double angle;
    double scale;
    bool portable;
};

void put_turned(const CurveRow& arc, Turn turn, std::span<double>::iterator out) {
    const double ax = arc.x0 - arc.cx;
    const double ay = arc.y0 - arc.cy;
    const SinCos sc = turn.portable
                          ? basic_sin_cos(turn.angle)
                          : SinCos{.sin = std::sin(turn.angle), .cos = std::cos(turn.angle)};
    const double c = sc.cos * turn.scale;
    const double s = sc.sin * turn.scale;
    *out = arc.cx + (ax * c - ay * s);
    *(out + 1) = arc.cy + (ax * s + ay * c);
}

} // namespace

int arc_steps(const CurveRow& arc, double t_mm, bool inscribed, double max_step_rad) {
    const double ax = arc.x0 - arc.cx;
    const double ay = arc.y0 - arc.cy;
    const double bound =
        std::min(step_within(std::sqrt(ax * ax + ay * ay), t_mm, inscribed), max_step_rad);
    const double sweep = std::abs(arc.sweep);
    const double quotient = std::ceil(sweep / bound);
    if (!(quotient < std::numeric_limits<int>::max())) { // also catches inf and NaN
        return -1;
    }
    auto steps = std::max(static_cast<int>(quotient), 1);
    if (sweep / steps > bound) { // rounding made the step too large (REQ-G2D-106)
        ++steps;
    }
    return steps;
}

namespace {

struct Placement {
    bool inscribed;
    bool portable; // sin and cos from basic operations
};

// Writes P0 and the arc's inner vertices from `next` on, without P1: n points inscribed, n + 1
// circumscribed. Returns where P1 would go.
std::span<double>::iterator put_arc_start(const CurveRow& arc, int steps, Placement placement,
                                          std::span<double>::iterator next) {
    const bool inscribed = placement.inscribed;
    const double step = arc.sweep / steps; // signed: the sense of the arc
    *next = arc.x0;
    *(next + 1) = arc.y0;
    next += 2;
    if (inscribed) {
        for (int k = 1; k < steps; ++k, next += 2) {
            put_turned(arc, {.angle = k * step, .scale = 1.0, .portable = placement.portable},
                       next);
        }
    } else {
        const double half = step / 2;
        const double outward =
            1.0 / (placement.portable ? basic_sin_cos(half).cos : std::cos(half));
        for (int k = 0; k < steps; ++k, next += 2) {
            const double middle = (2 * k + 1) * step / 2; // the middle of step k
            put_turned(arc, {.angle = middle, .scale = outward, .portable = placement.portable},
                       next);
        }
    }
    return next;
}

} // namespace

void flatten_arc(const CurveRow& arc, int steps, bool inscribed, std::span<double> out) {
    const auto next =
        put_arc_start(arc, steps, {.inscribed = inscribed, .portable = false}, out.begin());
    *next = arc.x1;
    *(next + 1) = arc.y1;
}

void row_vertex_counts(std::span<const double> rows, std::span<const std::uint8_t> inscribed,
                       FlattenLimits limits, std::span<std::int64_t> out) {
    for (std::size_t i = 0; i < out.size(); ++i) {
        const CurveRow row = unpack_row(rows.subspan(i * row_width, row_width));
        std::int64_t count = 1; // a line adds its P0
        if (row.sweep != 0.0) {
            const bool inner = inscribed.subspan(i, 1).front() != 0;
            const int steps = arc_steps(row, limits.t_mm, inner, limits.max_step_rad);
            count = steps < 0 ? -1 : steps + (inner ? 0 : 1);
        }
        out.subspan(i, 1).front() = count;
    }
}

void flatten_rows(std::span<const double> rows, std::span<const std::uint8_t> inscribed,
                  std::span<const std::int64_t> counts, bool portable, std::span<double> out) {
    auto next = out.begin();
    for (std::size_t i = 0; i < counts.size(); ++i) {
        const CurveRow row = unpack_row(rows.subspan(i * row_width, row_width));
        const std::int64_t count = counts.subspan(i, 1).front();
        if (row.sweep == 0.0) {
            *next = row.x0;
            *(next + 1) = row.y0;
            next += 2;
        } else {
            const bool inner = inscribed.subspan(i, 1).front() != 0;
            const auto steps = static_cast<int>(inner ? count : count - 1);
            next = put_arc_start(row, steps, {.inscribed = inner, .portable = portable}, next);
        }
    }
}

} // namespace splintercam::geometry2d

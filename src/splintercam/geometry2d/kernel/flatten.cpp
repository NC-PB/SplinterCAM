// SPDX-License-Identifier: Apache-2.0
// Arc flattening (research 01, Flattening): the inscribed polygon of the control's own chord rule
// (Altintas 2012, SRC-119, eqs. 5.85-5.86, Table 5.2) and our circumscribed polyline. Vertices are
// P0 − C turned about C, so their distance from C rounds the same way as r = |P0 − C|.
#include "flatten.hpp"

#include "angle.hpp"

#include <algorithm>
#include <cmath>

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

// Writes C + R(angle)·(P0 − C)·scale at `out`, the next two places.
void put_turned(const CurveRow& arc, double angle, double scale, std::span<double>::iterator out) {
    const double ax = arc.x0 - arc.cx;
    const double ay = arc.y0 - arc.cy;
    const double c = std::cos(angle) * scale;
    const double s = std::sin(angle) * scale;
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
    auto steps = static_cast<int>(std::ceil(sweep / bound));
    steps = std::max(steps, 1);
    if (sweep / steps > bound) { // rounding made the step too large (REQ-G2D-106)
        ++steps;
    }
    return steps;
}

void flatten_arc(const CurveRow& arc, int steps, bool inscribed, std::span<double> out) {
    const double step = arc.sweep / steps; // signed: the sense of the arc
    auto next = out.begin();
    *next = arc.x0;
    *(next + 1) = arc.y0;
    next += 2;
    if (inscribed) {
        for (int k = 1; k < steps; ++k, next += 2) {
            put_turned(arc, k * step, 1.0, next);
        }
    } else {
        const double outward = 1.0 / std::cos(step / 2);
        for (int k = 0; k < steps; ++k, next += 2) {
            put_turned(arc, (2 * k + 1) * step / 2, outward, next); // the middle of step k
        }
    }
    *next = arc.x1;
    *(next + 1) = arc.y1;
}

} // namespace splintercam::geometry2d

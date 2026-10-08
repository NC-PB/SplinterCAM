// SPDX-License-Identifier: Apache-2.0
// The grid bridge: Clipper2 2.0.1 (SRC-122, BSL-1.0) decides on 64-bit integers; its input is
// re-centred so the coordinates stay small, and refused beyond 2^26 grid units, where some of its
// double-precision tests stop being exact (research 01, trap 17; SRC-032 note).
#include "grid.hpp"

#include <algorithm>
#include <clipper2/clipper.h>
#include <cmath>
#include <limits>

namespace splintercam::geometry2d {
namespace {

struct Frame {
    double cx;
    double cy;
};

// The centre of the points' bounding box, or nothing when they span the limit or more.
bool frame_of(std::span<const double> points, GridLimits limits, Frame& frame) {
    double x0 = std::numeric_limits<double>::infinity();
    double y0 = x0;
    double x1 = -x0;
    double y1 = -x0;
    for (std::size_t i = 0; i < points.size() / 2; ++i) {
        const Point2 p = point(points, i);
        x0 = std::min(x0, std::get<0>(p));
        x1 = std::max(x1, std::get<0>(p));
        y0 = std::min(y0, std::get<1>(p));
        y1 = std::max(y1, std::get<1>(p));
    }
    if ((x1 - x0) / limits.u >= limits.max_span_units ||
        (y1 - y0) / limits.u >= limits.max_span_units) {
        return false;
    }
    frame = {.cx = (x0 + x1) / 2, .cy = (y0 + y1) / 2};
    return true;
}

Clipper2Lib::Paths64 to_grid(const Polylines& input, Frame frame, double u) {
    Clipper2Lib::Paths64 paths;
    const std::size_t n = input.points.size() / 2;
    for (std::size_t loop = 0; loop < input.loop_starts.size(); ++loop) {
        const auto start = static_cast<std::size_t>(input.loop_starts.subspan(loop, 1).front());
        const std::size_t end =
            loop + 1 < input.loop_starts.size()
                ? static_cast<std::size_t>(input.loop_starts.subspan(loop + 1, 1).front())
                : n;
        Clipper2Lib::Path64 path;
        for (std::size_t i = start; i < end; ++i) {
            const Point2 p = point(input.points, i);
            path.emplace_back(std::llround((std::get<0>(p) - frame.cx) / u),
                              std::llround((std::get<1>(p) - frame.cy) / u));
        }
        paths.push_back(std::move(path));
    }
    return paths;
}

} // namespace

GridResult grid_union(const Polylines& input, GridLimits limits) {
    GridResult result;
    Frame frame{};
    if (!frame_of(input.points, limits, frame)) {
        result.status = GridStatus::too_large;
        return result;
    }
    Clipper2Lib::Clipper64 clipper;
    clipper.AddSubject(to_grid(input, frame, limits.u));
    Clipper2Lib::Paths64 solution;
    if (!clipper.Execute(Clipper2Lib::ClipType::Union, Clipper2Lib::FillRule::NonZero, solution)) {
        result.status = GridStatus::failed;
        return result;
    }
    for (const Clipper2Lib::Path64& path : solution) {
        result.starts.push_back(static_cast<std::int64_t>(result.points.size()));
        for (const Clipper2Lib::Point64& p : path) {
            result.points.push_back({frame.cx + static_cast<double>(p.x) * limits.u,
                                     frame.cy + static_cast<double>(p.y) * limits.u});
        }
    }
    return result;
}

GridAreas grid_difference(const Polylines& b, const Polylines& a, GridLimits limits) {
    GridAreas result;
    std::vector<double> both(b.points.begin(), b.points.end());
    both.insert(both.end(), a.points.begin(), a.points.end());
    Frame frame{};
    if (!frame_of(both, limits, frame)) {
        result.status = GridStatus::too_large;
        return result;
    }
    const Clipper2Lib::Paths64 subject = to_grid(b, frame, limits.u);
    Clipper2Lib::Clipper64 clipper;
    clipper.AddSubject(subject);
    clipper.AddClip(to_grid(a, frame, limits.u));
    Clipper2Lib::Paths64 solution;
    if (!clipper.Execute(Clipper2Lib::ClipType::Difference, Clipper2Lib::FillRule::NonZero,
                         solution)) {
        result.status = GridStatus::failed;
        return result;
    }
    const double unit_area = limits.u * limits.u; // grid units² to mm²
    result.difference_mm2 = std::abs(Clipper2Lib::Area(solution)) * unit_area;
    result.b_mm2 = std::abs(Clipper2Lib::Area(subject)) * unit_area;
    return result;
}

} // namespace splintercam::geometry2d

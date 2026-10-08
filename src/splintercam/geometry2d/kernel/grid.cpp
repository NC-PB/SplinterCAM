// SPDX-License-Identifier: Apache-2.0
// The grid bridge: Clipper2 2.0.1 (SRC-122, BSL-1.0) decides on 64-bit integers; its input is
// re-centred so the coordinates stay small, and refused beyond 2^26 grid units, where some of its
// double-precision tests stop being exact (research 01, trap 17; SRC-032 note).
#include "grid.hpp"

#include <algorithm>
#include <clipper2/clipper.h>
#include <cmath>
#include <limits>
#include <map>
#include <utility>

namespace splintercam::geometry2d {
namespace {

using GridPoint = std::pair<std::int64_t, std::int64_t>;

GridPoint key(const Clipper2Lib::Point64& p) {
    return {p.x, p.y};
}

} // namespace

// The steps of grid_region, declared in grid.hpp for offset2d (DEC-G2D-041).

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

void split_pinches(const Clipper2Lib::Path64& path, std::vector<Clipper2Lib::Path64>& out) {
    std::vector<Clipper2Lib::Path64> todo{path};
    while (!todo.empty()) {
        Clipper2Lib::Path64 p = std::move(todo.back());
        todo.pop_back();
        std::map<GridPoint, std::size_t> seen;
        bool split = false;
        for (std::size_t j = 0; j < p.size() && !split; ++j) {
            const auto [entry, added] = seen.try_emplace(key(p.at(j)), j);
            if (added) {
                continue;
            }
            const std::size_t i = entry->second;
            todo.emplace_back(p.begin() + static_cast<std::ptrdiff_t>(i),
                              p.begin() + static_cast<std::ptrdiff_t>(j));
            Clipper2Lib::Path64 rest(p.begin() + static_cast<std::ptrdiff_t>(j), p.end());
            rest.insert(rest.end(), p.begin(), p.begin() + static_cast<std::ptrdiff_t>(i));
            todo.push_back(std::move(rest));
            split = true;
        }
        if (!split && p.size() >= 3) {
            out.push_back(std::move(p));
        }
    }
}

void canonical(std::vector<Clipper2Lib::Path64>& loops) {
    for (Clipper2Lib::Path64& loop : loops) {
        std::ranges::rotate(loop, std::ranges::min_element(loop, {}, key));
    }
    // By the smallest point, then the signed area, then the rotated loops point by point: loops
    // tied on both still leave in one order, whatever Clipper2's path order (Peter, DEC-G2D-042).
    std::ranges::sort(loops, [](const Clipper2Lib::Path64& a, const Clipper2Lib::Path64& b) {
        const auto first = std::pair{key(a.front()), Clipper2Lib::Area(a)};
        const auto second = std::pair{key(b.front()), Clipper2Lib::Area(b)};
        if (first != second) {
            return first < second;
        }
        return std::ranges::lexicographical_compare(a, b, {}, key, key);
    });
}

std::vector<std::uint8_t> shared_points(const std::vector<Clipper2Lib::Path64>& loops) {
    std::map<GridPoint, int> uses;
    for (const Clipper2Lib::Path64& loop : loops) {
        for (const Clipper2Lib::Point64& p : loop) {
            ++uses[key(p)];
        }
    }
    std::vector<std::uint8_t> fixed;
    for (const Clipper2Lib::Path64& loop : loops) {
        for (const Clipper2Lib::Point64& p : loop) {
            fixed.push_back(uses.at(key(p)) > 1 ? 1 : 0);
        }
    }
    return fixed;
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

GridRegion grid_region(const RegionInput& input, GridLimits limits) {
    GridRegion result;
    Frame frame{};
    if (!frame_of(input.loops.points, limits, frame)) {
        result.status = GridStatus::too_large;
        return result;
    }
    Clipper2Lib::Clipper64 clipper;
    clipper.AddSubject(to_grid(input.loops, frame, limits.u));
    Clipper2Lib::Paths64 solution;
    const auto rule = static_cast<Clipper2Lib::FillRule>(input.fill_rule); // checked by the binding
    if (!clipper.Execute(Clipper2Lib::ClipType::Union, rule, solution)) {
        result.status = GridStatus::failed;
        return result;
    }
    std::vector<Clipper2Lib::Path64> loops;
    for (const Clipper2Lib::Path64& path : solution) {
        split_pinches(path, loops);
    }
    canonical(loops);
    result.fixed = shared_points(loops);
    std::vector<double> middles;
    for (const Clipper2Lib::Path64& loop : loops) {
        result.starts.push_back(static_cast<std::int64_t>(result.points.size()));
        for (std::size_t k = 0; k < loop.size(); ++k) {
            const Clipper2Lib::Point64& p = loop.at(k);
            const Clipper2Lib::Point64& q = loop.at((k + 1) % loop.size());
            result.points.push_back({frame.cx + static_cast<double>(p.x) * limits.u,
                                     frame.cy + static_cast<double>(p.y) * limits.u});
            middles.insert(middles.end(),
                           {frame.cx + static_cast<double>(p.x + q.x) / 2 * limits.u,
                            frame.cy + static_cast<double>(p.y + q.y) / 2 * limits.u});
        }
    }
    std::vector<std::int64_t> nearest(result.points.size());
    nearest_segments(middles, input.loops, input.id_reach, nearest);
    for (const std::int64_t segment : nearest) {
        result.ids.push_back(
            segment < 0 ? -1
                        : input.source_ids.subspan(static_cast<std::size_t>(segment), 1).front());
    }
    return result;
}

} // namespace splintercam::geometry2d

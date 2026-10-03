// SPDX-License-Identifier: Apache-2.0
// Polyline cleanup (research 01, Helpers; ours; D-097): REQ-G2D-020, 204 to 212. Each kept vertex
// carries the vertices merged into it, so a later round merges it only where all of them lie
// within eps_len of the run's first vertex, and no vertex moves twice (spec review of step 9).
#include "cleanup.hpp"

#include "exact.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <numeric>
#include <vector>

namespace splintercam::geometry2d {
namespace {

using Indices = std::vector<std::size_t>;
struct Vertex {
    std::size_t index; // the vertex that stays
    Indices merged;    // it and the vertices merged into it
};
using Loop = std::vector<Vertex>;
constexpr std::size_t min_vertices = 3; // the drop passes stop here: fewer enclose nothing (ours)

struct Polyline {
    std::span<const double> points;
    double length_eps_mm;

    [[nodiscard]] Point2 at(std::size_t i) const {
        Point2 p{};
        std::ranges::copy(points.subspan(2 * i, 2), p.begin());
        return p;
    }
    // Whether every vertex of `vertex` lies within eps_len of `first`; IEEE 754's correctly rounded
    // sqrt makes this the same everywhere (a tolerance test, not a sign decision).
    [[nodiscard]] bool near(const Vertex& vertex, std::size_t first) const {
        const auto [fx, fy] = at(first);
        return std::ranges::all_of(vertex.merged, [&](std::size_t i) {
            const auto [x, y] = at(i);
            return std::sqrt((x - fx) * (x - fx) + (y - fy) * (y - fy)) <= length_eps_mm;
        });
    }
};

Loop merge_runs(const Polyline& line, Loop loop) {
    Loop merged;
    std::size_t last_run = 0; // where the last run starts in `merged`
    for (Vertex& vertex : loop) {
        if (!merged.empty() && line.near(vertex, merged.back().index)) {
            merged.back().merged.insert(merged.back().merged.end(), vertex.merged.begin(),
                                        vertex.merged.end());
        } else {
            merged.push_back(std::move(vertex));
            last_run = merged.size() - 1;
        }
    }
    if (last_run > 0 && line.near(merged.back(), merged.front().index)) {
        merged.pop_back(); // the last run joins the first (REQ-G2D-205)
    }
    return merged;
}

// Whether v lies strictly between a and b on the line through them, given orient2d(a, b, v) = 0.
bool strictly_between(Point2 a, Point2 v, Point2 b) {
    const std::size_t axis = std::get<0>(a) != std::get<0>(b) ? 0 : 1;
    const double low = std::min(a.at(axis), b.at(axis));
    const double high = std::max(a.at(axis), b.at(axis));
    return low < v.at(axis) && v.at(axis) < high;
}

bool collinear_between(Point2 a, Point2 v, Point2 b) {
    return orient_sign(a, b, v) == 0 && strictly_between(a, v, b);
}

// Turns back exactly onto itself; equal neighbours are a duplicate, not a spike.
bool spike(Point2 a, Point2 v, Point2 b) {
    return v != a && v != b && orient_sign(a, b, v) == 0 && !strictly_between(a, v, b);
}

// One pass of a vertex test in order, with the neighbours as they stand; marks the drops.
template <typename Test>
Loop drop_pass(const Polyline& line, Loop loop, Test test, Kept mark,
               std::span<std::int8_t> status) {
    Loop out;
    for (std::size_t i = 0; i < loop.size(); ++i) {
        const std::size_t prev = out.empty() ? loop.back().index : out.back().index;
        const std::size_t next = i + 1 < loop.size() ? loop.at(i + 1).index : out.front().index;
        const bool room = out.size() + (loop.size() - i) > min_vertices;
        if (room && test(line.at(prev), line.at(loop.at(i).index), line.at(next))) {
            status.subspan(loop.at(i).index, 1).front() = static_cast<std::int8_t>(mark);
            continue;
        }
        out.push_back(std::move(loop.at(i)));
    }
    return out;
}

} // namespace

void cleanup_loop(std::span<const double> points, double length_eps_mm,
                  std::span<std::int8_t> status) {
    const Polyline line{points, length_eps_mm};
    std::ranges::fill(status, static_cast<std::int8_t>(Kept::dropped));
    Indices order(status.size());
    std::iota(order.begin(), order.end(), std::size_t{0});
    Loop loop;
    for (const std::size_t i : order) {
        loop.push_back({i, {i}});
    }
    for (std::size_t before = 0; !loop.empty() && before != loop.size();) {
        before = loop.size();
        loop = merge_runs(line, std::move(loop));
        if (loop.size() >= min_vertices) {
            loop = drop_pass(line, std::move(loop), collinear_between, Kept::dropped, status);
            loop = drop_pass(line, std::move(loop), spike, Kept::spike, status);
        }
    }
    for (const Vertex& vertex : loop) {
        status.subspan(vertex.index, 1).front() = static_cast<std::int8_t>(Kept::kept);
    }
}

} // namespace splintercam::geometry2d

// SPDX-License-Identifier: Apache-2.0
// Polyline cleanup (research 01, Helpers; ours): from the first vertex, a run of consecutive
// vertices within eps_len of the run's first vertex becomes that vertex, and a last run within
// eps_len of the first vertex joins it; then a vertex strictly between its neighbours with
// orient2d exactly 0 is dropped, then a zero-width spike, where the loop turns back exactly onto
// itself. The three passes repeat in this order until none changes the loop, and stop below three
// vertices. Distances merge first, so the exact predicates see merged vertices (D-097).
#include "cleanup.hpp"

#include "exact.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <vector>

namespace splintercam::geometry2d {
namespace {

using Indices = std::vector<std::size_t>;
constexpr std::size_t min_vertices = 3; // a loop with fewer encloses nothing

struct Polyline {
    std::span<const double> points;
    double length_eps_mm;

    [[nodiscard]] Point2 at(std::size_t i) const {
        Point2 p{};
        std::ranges::copy(points.subspan(2 * i, 2), p.begin());
        return p;
    }
    [[nodiscard]] bool near(std::size_t i, std::size_t j) const {
        const auto [ax, ay] = at(i);
        const auto [bx, by] = at(j);
        const double dx = ax - bx;
        const double dy = ay - by;
        return std::sqrt(dx * dx + dy * dy) <=
               length_eps_mm; // basic operations: the same everywhere
    }
};

Indices merge_runs(const Polyline& line, const Indices& kept) {
    Indices merged{kept.front()};
    std::size_t last_run = 0; // where the last run starts in `kept`
    for (std::size_t k = 1; k < kept.size(); ++k) {
        if (!line.near(kept.at(k), merged.back())) {
            merged.push_back(kept.at(k));
            last_run = k;
        }
    }
    const auto last = std::span(kept).subspan(last_run);
    if (last_run > 0 &&
        std::ranges::all_of(last, [&](std::size_t i) { return line.near(i, kept.front()); })) {
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
    return a != b && orient_sign(a, b, v) == 0 && strictly_between(a, v, b);
}

bool spike(Point2 a, Point2 v, Point2 b) {
    return v != a && v != b && orient_sign(a, b, v) == 0 && (a == b || !strictly_between(a, v, b));
}

// One pass of a vertex test, walking in order with the neighbours as they stand; marks drops.
template <typename Test>
Indices drop_pass(const Polyline& line, const Indices& kept, Test test,
                  std::span<std::int8_t> marks) {
    Indices out;
    for (std::size_t i = 0; i < kept.size(); ++i) {
        const std::size_t prev = out.empty() ? kept.back() : out.back();
        const std::size_t next = i + 1 < kept.size() ? kept.at(i + 1) : out.front();
        const bool room = out.size() + (kept.size() - i) > min_vertices;
        if (room && test(line.at(prev), line.at(kept.at(i)), line.at(next))) {
            if (!marks.empty()) {
                marks.subspan(kept.at(i), 1).front() = 1;
            }
            continue;
        }
        out.push_back(kept.at(i));
    }
    return out;
}

} // namespace

void cleanup_loop(std::span<const double> points, double length_eps_mm, const CleanupOut& out) {
    const Polyline line{points, length_eps_mm};
    Indices kept(out.keep.size());
    for (std::size_t i = 0; i < kept.size(); ++i) {
        kept.at(i) = i;
    }
    for (std::size_t before = 0; !kept.empty() && before != kept.size();) {
        before = kept.size();
        kept = merge_runs(line, kept);
        if (kept.size() >= min_vertices) {
            kept = drop_pass(line, kept, collinear_between, {});
            kept = drop_pass(line, kept, spike, out.spike);
        }
    }
    std::ranges::fill(out.keep, std::int8_t{0});
    for (const std::size_t i : kept) {
        out.keep.subspan(i, 1).front() = 1;
    }
}

} // namespace splintercam::geometry2d

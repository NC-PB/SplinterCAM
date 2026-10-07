// SPDX-License-Identifier: Apache-2.0
// Distances to segments and closed polylines. The grid (ours, 2026-10-08): cells of side
// h = max(2·limit, mean segment length), each segment filed in every cell its column-wise y-range
// touches; a point within `limit` of q lies at most one cell away from q's cell, and the search
// looks two cells away so that a rounding of a cell index near a boundary cannot hide a segment.
#include "distance.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <vector>

namespace splintercam::geometry2d {
namespace {

double x(Point2 p) {
    return std::get<0>(p);
}

double y(Point2 p) {
    return std::get<1>(p);
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

struct Segment {
    Point2 a;
    Point2 b;
};

struct Entry {
    std::int64_t ix;
    std::int64_t iy;
    std::size_t segment;
    auto operator<=>(const Entry&) const = default;
};

struct Grid {
    double ox;
    double oy;
    double h;
    std::vector<Entry> entries; // sorted
};

std::vector<Segment> segments_of(const Polylines& lines) {
    std::vector<Segment> segments;
    const std::size_t n = lines.points.size() / 2;
    for (std::size_t loop = 0; loop < lines.loop_starts.size(); ++loop) {
        const auto start = static_cast<std::size_t>(lines.loop_starts.subspan(loop, 1).front());
        const std::size_t end =
            loop + 1 < lines.loop_starts.size()
                ? static_cast<std::size_t>(lines.loop_starts.subspan(loop + 1, 1).front())
                : n;
        for (std::size_t i = start; i < end; ++i) {
            const std::size_t next = i + 1 < end ? i + 1 : start;
            segments.push_back({point(lines.points, i), point(lines.points, next)});
        }
    }
    return segments;
}

// The index of the cell holding `value`, clamped far beyond any grid so the cast and the search's
// ±reach cannot overflow.
std::int64_t cell(double value, double origin, double h) {
    constexpr double bound = 0x1p62;
    return static_cast<std::int64_t>(std::clamp(std::floor((value - origin) / h), -bound, bound));
}

// Files segment s in the cells of each column its x-range crosses, by its y-range in the column.
// The end columns start and stop at the segment's own ends with their own y, so no rounding of a
// column boundary against cell() can leave a part of the segment unfiled (spec review,
// 2026-10-08); interior boundaries come from one expression on both sides.
void file_segment(const Segment& s, std::size_t index, Grid& grid) {
    const bool a_first = x(s.a) <= x(s.b);
    const Point2 p = a_first ? s.a : s.b;
    const Point2 q = a_first ? s.b : s.a;
    const std::int64_t first = cell(x(p), grid.ox, grid.h);
    const std::int64_t last = cell(x(q), grid.ox, grid.h);
    const double slope = first == last ? 0.0 : (y(q) - y(p)) / (x(q) - x(p));
    for (std::int64_t ix = first; ix <= last; ++ix) {
        const double y_left =
            ix == first ? y(p) : y(p) + (grid.ox + static_cast<double>(ix) * grid.h - x(p)) * slope;
        const double y_right =
            ix == last ? y(q)
                       : y(p) + (grid.ox + static_cast<double>(ix + 1) * grid.h - x(p)) * slope;
        const std::int64_t low = cell(std::min(y_left, y_right), grid.oy, grid.h);
        const std::int64_t high = cell(std::max(y_left, y_right), grid.oy, grid.h);
        for (std::int64_t iy = low; iy <= high; ++iy) {
            grid.entries.push_back({.ix = ix, .iy = iy, .segment = index});
        }
    }
}

Grid build_grid(const std::vector<Segment>& segments, double limit) {
    double ox = std::numeric_limits<double>::infinity();
    double oy = ox;
    double total = 0.0;
    for (const Segment& s : segments) {
        ox = std::min({ox, x(s.a), x(s.b)});
        oy = std::min({oy, y(s.a), y(s.b)});
        total += length(x(s.b) - x(s.a), y(s.b) - y(s.a));
    }
    const double mean = total / static_cast<double>(segments.size());
    Grid grid{.ox = ox, .oy = oy, .h = std::max(2 * limit, mean), .entries = {}};
    for (std::size_t i = 0; i < segments.size(); ++i) {
        file_segment(segments.at(i), i, grid);
    }
    std::ranges::sort(grid.entries);
    return grid;
}

double nearest(Point2 q, const Grid& grid, const std::vector<Segment>& segments) {
    constexpr std::int64_t reach = 2;
    double best = std::numeric_limits<double>::infinity();
    const std::int64_t cx = cell(x(q), grid.ox, grid.h);
    const std::int64_t cy = cell(y(q), grid.oy, grid.h);
    for (std::int64_t ix = cx - reach; ix <= cx + reach; ++ix) {
        const auto first = std::ranges::lower_bound(grid.entries, Entry{ix, cy - reach, 0});
        const auto last = std::ranges::lower_bound(grid.entries, Entry{ix, cy + reach + 1, 0});
        for (auto e = first; e != last; ++e) {
            const Segment& s = segments.at(e->segment);
            best = std::min(best, segment_distance(q, s.a, s.b));
        }
    }
    return best;
}

} // namespace

double length(double dx, double dy) {
    return std::sqrt(dx * dx + dy * dy); // correctly rounded operations: the same everywhere
}

double segment_distance(Point2 q, Point2 a, Point2 b) {
    return std::min(line_distance(q, a, b), line_distance(q, b, a));
}

void polyline_distances(std::span<const double> q, const Polylines& lines, double limit,
                        std::span<double> out) {
    const std::vector<Segment> segments = segments_of(lines);
    if (segments.empty()) {
        std::ranges::fill(out, std::numeric_limits<double>::infinity());
        return;
    }
    const Grid grid = build_grid(segments, limit);
    for (std::size_t i = 0; i < out.size(); ++i) {
        const double d = nearest(point(q, i), grid, segments);
        out.subspan(i, 1).front() = d <= limit ? d : std::numeric_limits<double>::infinity();
    }
}

} // namespace splintercam::geometry2d

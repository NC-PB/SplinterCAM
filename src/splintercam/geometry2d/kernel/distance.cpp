// SPDX-License-Identifier: Apache-2.0
// Distances to segments and closed polylines. The grid (ours, 2026-10-08): cells of side
// h = max(2·limit, mean segment length), each segment filed in every cell its column-wise y-range
// touches; a point within `limit` of q lies at most one cell away from q's cell, and the search
// looks two cells away so that a rounding of a cell index near a boundary cannot hide a segment.
#include "distance.hpp"

#include "region.hpp"

#include <algorithm>
#include <array>
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

// The index of the cell holding `value`, clamped so neither the cast nor ±reach can overflow.
std::int64_t cell(double value, double origin, double h) {
    constexpr double bound = 0x1p62;
    return static_cast<std::int64_t>(std::clamp(std::floor((value - origin) / h), -bound, bound));
}

// Files segment s in the cells of each column its x-range crosses, by its y-range in the column;
// the end columns use the segment's own ends, so no rounded boundary leaves a part unfiled
// (DEC-G2D-029).
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

// The segments filed within `reach` cells of any cell segment s crosses: sorted, unique.
std::vector<std::size_t> segments_near(const Grid& grid, const Segment& s) {
    constexpr std::int64_t reach = 2;
    Grid probe{.ox = grid.ox, .oy = grid.oy, .h = grid.h, .entries = {}};
    file_segment(s, 0, probe);
    std::vector<std::size_t> found;
    for (const Entry& c : probe.entries) {
        for (std::int64_t ix = c.ix - reach; ix <= c.ix + reach; ++ix) {
            const auto first = std::ranges::lower_bound(grid.entries, Entry{ix, c.iy - reach, 0});
            const auto last =
                std::ranges::lower_bound(grid.entries, Entry{ix, c.iy + reach + 1, 0});
            for (auto e = first; e != last; ++e) {
                found.push_back(e->segment);
            }
        }
    }
    std::ranges::sort(found);
    found.erase(std::ranges::unique(found).begin(), found.end());
    return found;
}

struct Span { // [low, high] of the parameter t along a segment; empty when low > high
    double low;
    double high;
};

constexpr Span empty_span{.low = 1.0, .high = 0.0};

// t with g0 + t·g1 in [lo, hi].
Span linear_span(double g0, double g1, Span range) {
    if (g1 == 0.0) {
        return g0 >= range.low && g0 <= range.high ? Span{-std::numeric_limits<double>::infinity(),
                                                          std::numeric_limits<double>::infinity()}
                                                   : empty_span;
    }
    const double t1 = (range.low - g0) / g1;
    const double t2 = (range.high - g0) / g1;
    return {std::min(t1, t2), std::max(t1, t2)};
}

struct Ray { // the points p + t·d
    Point2 p;
    Point2 d;
};

// t with |p + t·d − c| <= r, about the foot of c so it stays accurate far from p (DEC-G2D-030).
Span disc_span(const Ray& ray, Point2 c, double r) {
    const double fx = x(ray.p) - x(c);
    const double fy = y(ray.p) - y(c);
    const double dd = x(ray.d) * x(ray.d) + y(ray.d) * y(ray.d);
    if (dd == 0.0) {
        constexpr double all = std::numeric_limits<double>::infinity();
        return fx * fx + fy * fy <= r * r ? Span{-all, all} : empty_span;
    }
    const double t0 = -(fx * x(ray.d) + fy * y(ray.d)) / dd;
    const double h = (fx * y(ray.d) - fy * x(ray.d)) / std::sqrt(dd);
    const double rest = r * r - h * h;
    if (rest < 0.0) {
        return empty_span;
    }
    const double half = std::sqrt(rest / dd);
    return {t0 - half, t0 + half};
}

// The part of s (t in [0, 1]) within r of e: e's capsule is convex, so one interval (ours).
Span covered(const Segment& s, const Segment& e, double r) {
    const Point2 d{x(s.b) - x(s.a), y(s.b) - y(s.a)};
    const Point2 w{x(e.b) - x(e.a), y(e.b) - y(e.a)};
    const Point2 f{x(s.a) - x(e.a), y(s.a) - y(e.a)};
    const double ww = x(w) * x(w) + y(w) * y(w);
    Span strip = empty_span;
    if (ww > 0.0) {
        const Span along = linear_span(x(f) * x(w) + y(f) * y(w), x(d) * x(w) + y(d) * y(w),
                                       {.low = 0.0, .high = ww});
        const double band = r * std::sqrt(ww);
        const Span across = linear_span(x(f) * y(w) - y(f) * x(w), x(d) * y(w) - y(d) * x(w),
                                        {.low = -band, .high = band});
        strip = {std::max(along.low, across.low), std::min(along.high, across.high)};
    }
    Span all = empty_span;
    const Ray ray{.p = s.a, .d = d};
    for (const Span part : {strip, disc_span(ray, e.a, r), disc_span(ray, e.b, r)}) {
        if (part.low <= part.high) {
            all = all.low > all.high
                      ? part
                      : Span{std::min(all.low, part.low), std::max(all.high, part.high)};
        }
    }
    return {std::max(all.low, 0.0), std::min(all.high, 1.0)};
}

// A part of a segment farther than the limit from the other polylines, and whether it reaches the
// segment's ends.
struct FarPart {
    Point2 middle;
    bool from_start;
    bool to_end;
};

// The far parts of s: the gaps the covered intervals leave in [0, 1].
void far_parts(const Segment& s, std::vector<Span>& spans, std::vector<FarPart>& out) {
    std::ranges::sort(spans, {}, &Span::low);
    double cursor = 0.0;
    const auto gap = [&](double end) {
        const double t = (cursor + end) / 2;
        out.push_back({.middle = {x(s.a) + t * (x(s.b) - x(s.a)), y(s.a) + t * (y(s.b) - y(s.a))},
                       .from_start = cursor == 0.0,
                       .to_end = end == 1.0});
    };
    for (const Span& span : spans) {
        if (span.low > cursor) {
            gap(span.low);
        }
        cursor = std::max(cursor, span.high);
    }
    if (cursor < 1.0) {
        gap(1.0);
    }
}

// The far parts of each segment of `mine` against `theirs`; `visit` returns false to stop.
struct FarQuery {
    std::span<const Segment> mine;
    std::span<const Segment> theirs;
    double limit;
};

template <typename Visit> void each_far_part(const FarQuery& query, Visit visit) {
    const std::vector<Segment> theirs(query.theirs.begin(), query.theirs.end());
    const Grid grid = build_grid(theirs, query.limit);
    const double limit = query.limit;
    const std::span<const Segment> mine = query.mine;
    std::vector<Span> spans;
    std::vector<FarPart> parts;
    for (const Segment& s : mine) {
        spans.clear();
        parts.clear();
        for (const std::size_t i : segments_near(grid, s)) {
            const Span part = covered(s, theirs.at(i), limit);
            if (part.low <= part.high) {
                spans.push_back(part);
            }
        }
        far_parts(s, spans, parts);
        for (const FarPart& part : parts) {
            if (!visit(part)) {
                return;
            }
        }
    }
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

Depth crossing_depth(const Polylines& a, const Polylines& b, double limit) {
    const std::vector<Segment> mine = segments_of(a);
    const std::vector<Segment> theirs = segments_of(b);
    if (mine.empty() || theirs.empty()) {
        return {};
    }
    std::vector<double> rows;
    for (const Segment& e : theirs) {
        const double nan = std::numeric_limits<double>::quiet_NaN();
        rows.insert(rows.end(), {x(e.a), y(e.a), x(e.b), y(e.b), nan, nan, 0.0});
    }
    Depth depth;
    bool run_open = false; // the previous part reached its segment's end
    each_far_part({.mine = mine, .theirs = theirs, .limit = limit}, [&](const FarPart& part) {
        // A connected far part lies on one side of b: one point per run of joined parts.
        if (!(part.from_start && run_open)) {
            const std::array<double, 2> q{x(part.middle), y(part.middle)};
            std::array<std::int8_t, 1> where{};
            point_locations(q, {.rows = rows, .length_eps_mm = 0.0}, where);
            depth.inside =
                depth.inside || std::get<0>(where) == static_cast<std::int8_t>(Location::in);
            depth.outside =
                depth.outside || std::get<0>(where) == static_cast<std::int8_t>(Location::out);
        }
        run_open = part.to_end;
        return !(depth.inside && depth.outside);
    });
    return depth;
}

bool covered_by(const Polylines& a, const Polylines& b, double limit) {
    const std::vector<Segment> mine = segments_of(a);
    const std::vector<Segment> theirs = segments_of(b);
    if (theirs.empty()) {
        return mine.empty();
    }
    bool covered = true;
    each_far_part({.mine = mine, .theirs = theirs, .limit = limit}, [&](const FarPart&) {
        covered = false;
        return false; // the first far part decides
    });
    return covered;
}

} // namespace splintercam::geometry2d

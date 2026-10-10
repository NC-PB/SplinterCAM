// SPDX-License-Identifier: Apache-2.0
// One side of an open chain (research 02, Open chains; the side rule ours, REQ-OFF-028,
// DEC-OFF-018; exact orientation by Shewchuk's predicates through geometry2d, SRC-032).
#include "chain_side.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <numeric>
#include <optional>
#include <ranges>
#include <span>
#include <tuple>
#include <utility>
#include <vector>

namespace splintercam::offset2d {
namespace {

using geometry2d::Point2;

// In order of precedence when segments tie: a cap, then the other side (DEC-OFF-018).
enum class Side : std::uint8_t { cap, other, tool };

struct Chain {
    std::span<const double> points; // the flattened chain, x and y, merged within u
    std::size_t segments;
    int tool;         // +1 left, -1 right
    double cap_reach; // rounding at a cap's tangent point: 3u
};

Point2 at(const Chain& chain, std::size_t i) {
    return geometry2d::point(chain.points, i);
}

// The parameter along segment j of the point nearest q, unclamped, and the segment's length.
std::pair<double, double> along(const Chain& chain, std::size_t j, Point2 q) {
    const Point2 a = at(chain, j);
    const Point2 b = at(chain, j + 1);
    const double dx = geometry2d::x(b) - geometry2d::x(a);
    const double dy = geometry2d::y(b) - geometry2d::y(a);
    const double length = std::sqrt((dx * dx) + (dy * dy));
    const double dot =
        ((geometry2d::x(q) - geometry2d::x(a)) * dx) + ((geometry2d::y(q) - geometry2d::y(a)) * dy);
    return {dot / (length * length), length};
}

bool on_tool_side(const Chain& chain, Point2 a, Point2 b, Point2 q) {
    return geometry2d::orient_sign(a, b, q) * chain.tool > 0;
}

// The side of an output edge whose middle q lies nearest segment j: a cap where the nearest point
// is an end of the chain (the round end's arc; within 3u of its tangent point, for rounding);
// inside a segment by its orientation; at an interior vertex by both its segments, either where
// the vertex is convex toward the tool and both where it is concave.
Side side_of(const Chain& chain, std::size_t j, Point2 q) {
    const auto [t, length] = along(chain, j, q);
    if ((j == 0 && t * length <= chain.cap_reach) ||
        (j + 1 == chain.segments && (1.0 - t) * length <= chain.cap_reach)) {
        return Side::cap;
    }
    if (t > 0.0 && t < 1.0) {
        return on_tool_side(chain, at(chain, j), at(chain, j + 1), q) ? Side::tool : Side::other;
    }
    const std::size_t v = t <= 0.0 ? j : j + 1;
    const Point2 before = at(chain, v - 1);
    const Point2 corner = at(chain, v);
    const Point2 after = at(chain, v + 1);
    const bool first = on_tool_side(chain, before, corner, q);
    const bool second = on_tool_side(chain, corner, after, q);
    const bool convex = geometry2d::orient_sign(before, corner, after) * chain.tool <= 0;
    return (convex ? (first || second) : (first && second)) ? Side::tool : Side::other;
}

struct Labelled {
    std::vector<Side> sides;
    std::vector<double> place; // where along the chain its middle lies: segment + parameter
};

std::size_t loop_end(const geometry2d::GridRegion& region, std::size_t loop) {
    return loop + 1 < region.starts.size() ? static_cast<std::size_t>(region.starts.at(loop + 1))
                                           : region.points.size();
}

// Every edge's label from all segments within eps of its middle's nearest (the chain given there
// and back: k < n is segment k, k >= n segment 2n - 1 - k), whatever their order: a cap if any
// says so, else the other side if any says so. Ties of opposite sides are left only where the
// chain touches itself at a point; folds are refused before (DEC-OFF-018).
Labelled label(const geometry2d::GridRegion& region, const Chain& chain, const GrowInput& input,
               geometry2d::TieReach reach) {
    std::vector<double> middles;
    for (std::size_t loop = 0; loop < region.starts.size(); ++loop) {
        const auto first = static_cast<std::size_t>(region.starts.at(loop));
        const std::size_t end = loop_end(region, loop);
        for (std::size_t k = first; k < end; ++k) {
            const Point2 p = region.points.at(k);
            const Point2 q = region.points.at(k + 1 < end ? k + 1 : first);
            middles.insert(middles.end(), {(geometry2d::x(p) + geometry2d::x(q)) / 2,
                                           (geometry2d::y(p) + geometry2d::y(q)) / 2});
        }
    }
    Labelled out{.sides = std::vector<Side>(middles.size() / 2, Side::tool),
                 .place = std::vector<double>(middles.size() / 2, -1.0)};
    for (const geometry2d::Tie& tie : geometry2d::nearest_ties(middles, input.ids.loops, reach)) {
        const auto e = static_cast<std::size_t>(tie.point);
        const auto k = static_cast<std::size_t>(tie.segment);
        const std::size_t j = k < chain.segments ? k : (2 * chain.segments) - 1 - k;
        const Point2 q = geometry2d::point(middles, e);
        out.sides.at(e) = std::min(out.sides.at(e), side_of(chain, j, q));
        if (out.place.at(e) < 0.0) {
            out.place.at(e) =
                static_cast<double>(j) + std::clamp(along(chain, j, q).first, 0.0, 1.0);
        }
    }
    return out;
}

// Whether a loop of the grown area is an outer loop: counter-clockwise, a positive area (shoelace).
bool outer(const geometry2d::GridRegion& region, std::size_t loop) {
    const auto first = static_cast<std::size_t>(region.starts.at(loop));
    const std::size_t end = loop_end(region, loop);
    double twice = 0.0;
    for (std::size_t k = first; k < end; ++k) {
        const Point2 p = region.points.at(k);
        const Point2 q = region.points.at(k + 1 < end ? k + 1 : first);
        twice += (geometry2d::x(p) * geometry2d::y(q)) - (geometry2d::x(q) * geometry2d::y(p));
    }
    return twice > 0.0;
}

struct Piece {
    bool closed;
    std::size_t loop; // the boundary loop it lies on
    double place;     // where along the chain it starts
    std::vector<Point2> points;
    std::vector<std::int64_t> ids;
    std::vector<std::uint8_t> fixed;
};

struct Run {
    std::size_t first;
    std::size_t count; // edges
    bool closed;
};

// The edges first .. first + count of a loop of `size` vertices starting at `base`, as one piece;
// turned round, a closed piece keeps its first vertex (the canonical start, REQ-OFF-038).
Piece make_piece(const geometry2d::GridRegion& region, std::pair<std::size_t, std::size_t> loop,
                 Run run, bool backwards) {
    const auto [base, size] = loop;
    Piece piece{
        .closed = run.closed, .loop = 0, .place = 0.0, .points = {}, .ids = {}, .fixed = {}};
    const std::size_t vertices = run.closed ? run.count : run.count + 1;
    for (std::size_t i = 0; i < vertices; ++i) {
        const std::size_t v =
            base + ((run.first + (backwards ? (run.count - i) % vertices : i)) % size);
        piece.points.push_back(region.points.at(v));
        piece.fixed.push_back(region.fixed.at(v));
    }
    // An edge keeps its ID whichever way it runs: the ID of the vertex it starts at, forwards.
    for (std::size_t i = 0; i < run.count; ++i) {
        const std::size_t e = run.first + (backwards ? run.count - 1 - i : i);
        piece.ids.push_back(region.ids.at(base + (e % size)));
    }
    return piece;
}

// The runs of tool-side edges of one loop: the whole loop as a closed piece, or each maximal run
// as an open piece. The grown area lies left of every boundary edge (outer loops counter-clockwise,
// holes clockwise), so with the tool left every piece is turned round to run with the chain: every
// piece has the chain on the side away from the tool and one milling direction (DEC-OFF-020).
void pieces_of_loop(std::vector<Piece>& out, const geometry2d::GridRegion& region,
                    const Labelled& labels, std::pair<std::size_t, bool> loop_backwards) {
    const auto [loop, backwards] = loop_backwards;
    const auto base = static_cast<std::size_t>(region.starts.at(loop));
    const std::size_t size = loop_end(region, loop) - base;
    const auto edge = [&](std::size_t i) { return base + (i % size); };
    const auto tool = [&](std::size_t i) { return labels.sides.at(edge(i)) == Side::tool; };
    const bool closed = std::ranges::all_of(std::views::iota(std::size_t{0}, size), tool);
    for (std::size_t i = 0; i < size; ++i) {
        if (!closed && (!tool(i) || tool(i + size - 1))) {
            continue;
        }
        std::size_t count = 0;
        while (count < size && tool(i + count)) {
            ++count;
        }
        const double from = labels.place.at(edge(i));
        const double to = labels.place.at(edge(i + count - 1));
        out.push_back(make_piece(region, {base, size}, {i, count, closed}, backwards));
        out.back().loop = loop;
        out.back().place = std::min(from, to);
        if (closed) {
            return;
        }
    }
}

} // namespace

SidePieces chain_side(const GrowInput& input, int tool_side, OffsetParams params,
                      OffsetLimits limits, geometry2d::TieReach reach) {
    SidePieces out;
    const geometry2d::GridRegion region = grow_chains(input, params, limits, reach);
    if (region.status != geometry2d::GridStatus::ok) {
        out.region.status = region.status;
        return out;
    }
    const Chain chain{.points = input.chains.points,
                      .segments = (input.chains.points.size() / 2) - 1,
                      .tool = tool_side,
                      .cap_reach = params.bias_units * limits.u};
    const Labelled labels = label(region, chain, input, reach);
    std::vector<Piece> pieces;
    for (std::size_t loop = 0; loop < region.starts.size(); ++loop) {
        pieces_of_loop(pieces, region, labels, {loop, tool_side > 0});
    }
    // Open pieces first, along the chain, then closed ones; ties by the first vertex (REQ-OFF-038).
    std::ranges::stable_sort(pieces, [](const Piece& a, const Piece& b) {
        return std::tuple{a.closed, a.place, a.points.front()} <
               std::tuple{b.closed, b.place, b.points.front()};
    });
    // A piece on a hole of the grown area other than the first open piece's lies across the area
    // from it: enclosed. The outer loop is reached from outside, which topic 10's link and entry
    // check decides (DEC-OFF-019, Peter).
    const std::size_t reachable =
        pieces.empty() || pieces.front().closed ? region.starts.size() : pieces.front().loop;
    for (const Piece& piece : pieces) {
        const bool enclosed = piece.loop != reachable && !outer(region, piece.loop);
        out.region.starts.push_back(static_cast<std::int64_t>(out.region.points.size()));
        out.flags.push_back((piece.closed ? closed_flag : 0) | (enclosed ? enclosed_flag : 0));
        out.region.points.insert(out.region.points.end(), piece.points.begin(), piece.points.end());
        out.region.ids.insert(out.region.ids.end(), piece.ids.begin(), piece.ids.end());
        out.region.fixed.insert(out.region.fixed.end(), piece.fixed.begin(), piece.fixed.end());
    }
    return out;
}

std::vector<std::uint8_t> keep_chain(std::span<const double> points, double threshold) {
    const std::size_t n = points.size() / 2;
    std::vector<std::uint8_t> keep(n, 0);
    const auto apart = [&](std::size_t i, std::size_t j) {
        const Point2 p = geometry2d::point(points, i);
        const Point2 q = geometry2d::point(points, j);
        return geometry2d::length(geometry2d::x(p) - geometry2d::x(q),
                                  geometry2d::y(p) - geometry2d::y(q)) > threshold;
    };
    keep.at(0) = 1;
    std::size_t last = 0;
    for (std::size_t i = 1; i + 1 < n; ++i) {
        if (apart(i, last)) {
            keep.at(i) = 1;
            last = i;
        }
    }
    // The end stays: kept points within threshold of it go, back to the first.
    for (std::size_t i = last; i > 0 && n > 1 && !apart(n - 1, i); --i) {
        keep.at(i) = 0;
    }
    keep.at(n - 1) = 1;
    return keep;
}

namespace {

struct Segment {
    Point2 a;
    Point2 b;
};

// Where segment s runs back over segment r, the one before it: opposite directions, the ends of s
// within tol of r's line, overlapping by more than tol; the overlap's middle on r.
std::optional<Point2> overlap(Segment r, Segment s, double tol) {
    const double dx = geometry2d::x(r.b) - geometry2d::x(r.a);
    const double dy = geometry2d::y(r.b) - geometry2d::y(r.a);
    const double length = geometry2d::length(dx, dy);
    const auto along_r = [&](Point2 p) {
        return (((geometry2d::x(p) - geometry2d::x(r.a)) * dx) +
                ((geometry2d::y(p) - geometry2d::y(r.a)) * dy)) /
               length;
    };
    const auto off_r = [&](Point2 p) {
        return std::abs(((geometry2d::y(p) - geometry2d::y(r.a)) * dx) -
                        ((geometry2d::x(p) - geometry2d::x(r.a)) * dy)) /
               length;
    };
    const double from = along_r(s.a);
    const double to = along_r(s.b);
    const double low = std::max(0.0, to);
    const double high = std::min(length, from);
    if (!(to < from) || off_r(s.a) > tol || off_r(s.b) > tol || high - low <= tol) {
        return std::nullopt;
    }
    const double mid = (low + high) / (2 * length);
    return Point2{geometry2d::x(r.a) + (mid * dx), geometry2d::y(r.a) + (mid * dy)};
}

} // namespace

namespace {

// The distance between two segments and the middle of their nearest points: 0 where they cross or
// touch (geometry2d's exact orientation), else the least distance from an end to the other.
std::pair<double, Point2> apart(Segment r, Segment s) {
    const auto sign = [](Point2 a, Point2 b, Point2 c) { return geometry2d::orient_sign(a, b, c); };
    const bool cross = sign(r.a, r.b, s.a) * sign(r.a, r.b, s.b) <= 0 &&
                       sign(s.a, s.b, r.a) * sign(s.a, s.b, r.b) <= 0;
    const auto foot = [](Point2 p, Segment g) {
        const double dx = geometry2d::x(g.b) - geometry2d::x(g.a);
        const double dy = geometry2d::y(g.b) - geometry2d::y(g.a);
        const double t = std::clamp((((geometry2d::x(p) - geometry2d::x(g.a)) * dx) +
                                     ((geometry2d::y(p) - geometry2d::y(g.a)) * dy)) /
                                        ((dx * dx) + (dy * dy)),
                                    0.0, 1.0);
        return Point2{geometry2d::x(g.a) + (t * dx), geometry2d::y(g.a) + (t * dy)};
    };
    std::pair<double, Point2> best{std::numeric_limits<double>::infinity(), r.a};
    for (const auto& [p, g] :
         {std::pair{r.a, s}, std::pair{r.b, s}, std::pair{s.a, r}, std::pair{s.b, r}}) {
        const Point2 f = foot(p, g);
        const double d = geometry2d::length(geometry2d::x(p) - geometry2d::x(f),
                                            geometry2d::y(p) - geometry2d::y(f));
        if (d < best.first) {
            best = {d, Point2{(geometry2d::x(p) + geometry2d::x(f)) / 2,
                              (geometry2d::y(p) + geometry2d::y(f)) / 2}};
        }
    }
    return cross && best.first > 0.0 ? std::pair{0.0, best.second} : best;
}

} // namespace

namespace {

// The first pair along the chain of segments not next to each other within tol (a sweep along x).
std::optional<Contact> first_contact(const std::vector<Segment>& segments, double tol) {
    const auto low_x = [&](std::size_t i) {
        return std::min(geometry2d::x(segments.at(i).a), geometry2d::x(segments.at(i).b));
    };
    const auto high_x = [&](std::size_t i) {
        return std::max(geometry2d::x(segments.at(i).a), geometry2d::x(segments.at(i).b));
    };
    std::vector<std::size_t> order(segments.size());
    std::iota(order.begin(), order.end(), std::size_t{0});
    std::ranges::stable_sort(order, {}, low_x);
    std::optional<Contact> found;
    for (std::size_t p = 0; p < order.size(); ++p) {
        for (std::size_t q = p + 1;
             q < order.size() && low_x(order.at(q)) <= high_x(order.at(p)) + tol; ++q) {
            const std::size_t i = std::min(order.at(p), order.at(q));
            const std::size_t j = std::max(order.at(p), order.at(q));
            const std::pair<std::size_t, std::size_t> pair{i, j};
            if (j > i + 1 && (!found || pair < found->pair)) {
                const auto [d, at] = apart(segments.at(i), segments.at(j));
                found = d <= tol ? std::optional{Contact{.at = at, .fold = false, .pair = pair}}
                                 : found;
            }
        }
    }
    return found;
}

} // namespace

std::optional<Contact> find_contact(std::span<const double> points, double tol) {
    const std::size_t n = points.size() / 2;
    std::vector<Segment> segments;
    for (std::size_t i = 0; i + 1 < n; ++i) {
        segments.push_back({geometry2d::point(points, i), geometry2d::point(points, i + 1)});
    }
    // A fold: a segment running back over the one before it, the first along the chain.
    for (std::size_t i = 0; i + 1 < segments.size(); ++i) {
        const auto fold = overlap(segments.at(i), segments.at(i + 1), tol);
        if (fold) {
            return Contact{.at = *fold, .fold = true};
        }
    }
    return first_contact(segments, tol); // SRC-030, Def. 5.3
}

} // namespace splintercam::offset2d

// SPDX-License-Identifier: Apache-2.0
// One side of an open chain (research 02, Open chains; the side rule ours, REQ-OFF-028,
// DEC-OFF-018; exact orientation by Shewchuk's predicates through geometry2d, SRC-032).
#include "chain_side.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <ranges>
#include <span>
#include <tuple>
#include <utility>
#include <vector>

namespace splintercam::offset2d {
namespace {

using geometry2d::Point2;

// In order of precedence when segments tie: tool side, cap, other.
enum class Side : std::uint8_t { tool, cap, other };

struct Chain {
    std::span<const double> points; // the flattened chain, x and y, no segment shorter than eps
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
    std::vector<double> forward; // the edge's length along its nearest segment, signed
    std::vector<double> place;   // where along the chain its middle lies: segment + parameter
    bool complete = true;        // every edge had a segment within the reach
};

std::size_t loop_end(const geometry2d::GridRegion& region, std::size_t loop) {
    return loop + 1 < region.starts.size() ? static_cast<std::size_t>(region.starts.at(loop + 1))
                                           : region.points.size();
}

// Every edge's label from all segments within eps of its middle's nearest (the chain given there
// and back: k < n is segment k, k >= n segment 2n - 1 - k): tool side if any says so, else a cap
// if any says so, so a chain run out and back keeps both legs' sides (DEC-OFF-018).
Labelled label(const geometry2d::GridRegion& region, const Chain& chain, const GrowInput& input,
               geometry2d::TieReach reach) {
    std::vector<double> middles;
    std::vector<std::pair<Point2, Point2>> ends;
    for (std::size_t loop = 0; loop < region.starts.size(); ++loop) {
        const auto first = static_cast<std::size_t>(region.starts.at(loop));
        const std::size_t end = loop_end(region, loop);
        for (std::size_t k = first; k < end; ++k) {
            const Point2 p = region.points.at(k);
            const Point2 q = region.points.at(k + 1 < end ? k + 1 : first);
            middles.insert(middles.end(), {(geometry2d::x(p) + geometry2d::x(q)) / 2,
                                           (geometry2d::y(p) + geometry2d::y(q)) / 2});
            ends.emplace_back(p, q);
        }
    }
    const std::vector<geometry2d::Tie> ties =
        geometry2d::nearest_ties(middles, input.ids.loops, reach);
    Labelled out;
    out.sides.assign(ends.size(), Side::other);
    out.forward.assign(ends.size(), 0.0);
    out.place.assign(ends.size(), 0.0);
    std::vector<bool> seen(ends.size(), false);
    for (const geometry2d::Tie& tie : ties) {
        const auto e = static_cast<std::size_t>(tie.point);
        const auto k = static_cast<std::size_t>(tie.segment);
        const std::size_t j = k < chain.segments ? k : (2 * chain.segments) - 1 - k;
        const Side side = side_of(chain, j, geometry2d::point(middles, e));
        if (!seen.at(e) || side < out.sides.at(e)) {
            const auto [from, length] = along(chain, j, ends.at(e).first);
            const double to = along(chain, j, ends.at(e).second).first;
            out.sides.at(e) = side;
            out.forward.at(e) = (to - from) * length;
            out.place.at(e) = static_cast<double>(j) + std::clamp((from + to) / 2, 0.0, 1.0);
        }
        seen.at(e) = true;
    }
    out.complete = std::ranges::all_of(seen, [](bool s) { return s; });
    return out;
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
// as an open piece. Each is turned round when it runs against the chain (by the summed length of
// its edges along their segments; on a tie, by where its ends lie along the chain), so every
// piece has the chain on the same side and one milling direction (DEC-OFF-020, Peter).
void pieces_of_loop(std::vector<Piece>& out, const geometry2d::GridRegion& region,
                    const Labelled& labels, std::size_t loop) {
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
        double forward = 0.0;
        while (count < size && tool(i + count)) {
            forward += labels.forward.at(edge(i + count));
            ++count;
        }
        const double from = labels.place.at(edge(i));
        const double to = labels.place.at(edge(i + count - 1));
        const bool backwards = forward < 0.0 || (forward == 0.0 && to < from);
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
    if (!labels.complete) { // an edge with no segment within the reach: no offset of the chain
        out.region.status = geometry2d::GridStatus::failed;
        return out;
    }
    std::vector<Piece> pieces;
    for (std::size_t loop = 0; loop < region.starts.size(); ++loop) {
        pieces_of_loop(pieces, region, labels, loop);
    }
    // Open pieces first, along the chain, then closed ones; ties by the first vertex (REQ-OFF-038).
    std::ranges::stable_sort(pieces, [](const Piece& a, const Piece& b) {
        return std::tuple{a.closed, a.place, a.points.front()} <
               std::tuple{b.closed, b.place, b.points.front()};
    });
    // A piece on another loop than the first open piece's lies across the grown area from it:
    // enclosed, never reached from the open piece without cutting closer than t (DEC-OFF-019).
    const std::size_t reachable =
        pieces.empty() || pieces.front().closed ? region.starts.size() : pieces.front().loop;
    for (const Piece& piece : pieces) {
        out.region.starts.push_back(static_cast<std::int64_t>(out.region.points.size()));
        out.flags.push_back((piece.closed ? closed_flag : 0) |
                            (piece.loop != reachable ? enclosed_flag : 0));
        out.region.points.insert(out.region.points.end(), piece.points.begin(), piece.points.end());
        out.region.ids.insert(out.region.ids.end(), piece.ids.begin(), piece.ids.end());
        out.region.fixed.insert(out.region.fixed.end(), piece.fixed.begin(), piece.fixed.end());
    }
    return out;
}

} // namespace splintercam::offset2d

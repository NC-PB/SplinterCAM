// SPDX-License-Identifier: Apache-2.0
// One side of an open chain (research 02, Open chains; the side rule ours, REQ-OFF-028; exact
// orientation by Shewchuk's predicates through geometry2d, SRC-032).
#include "chain_side.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <span>
#include <utility>

namespace splintercam::offset2d {
namespace {

using geometry2d::Point2;

enum class Side : std::uint8_t { tool, other, cap };

struct Chain {
    std::span<const double> points; // the flattened chain, x and y
    std::size_t segments;
    int tool;         // +1 left, -1 right
    double cap_reach; // how far past an end, along its segment, a cap's middle may lie
};

Point2 at(const Chain& chain, std::size_t i) {
    return geometry2d::point(chain.points, i);
}

// Where along segment j the point nearest q lies: its parameter, unclamped, and the segment's
// length (0 for a segment of length 0).
std::pair<double, double> along(const Chain& chain, std::size_t j, Point2 q) {
    const Point2 a = at(chain, j);
    const Point2 b = at(chain, j + 1);
    const double dx = geometry2d::x(b) - geometry2d::x(a);
    const double dy = geometry2d::y(b) - geometry2d::y(a);
    const double length = std::sqrt((dx * dx) + (dy * dy));
    if (length == 0.0) {
        return {0.0, 0.0};
    }
    const double dot =
        ((geometry2d::x(q) - geometry2d::x(a)) * dx) + ((geometry2d::y(q) - geometry2d::y(a)) * dy);
    return {dot / (length * length), length};
}

// A cap: the middle lies on the chain's first or last segment within `cap_reach` of the line
// through that end at right angles, where the Butt end cuts. A cap's middle lies on the end
// itself, which rounding moves a little either way (DEC-OFF-018).
bool is_cap(const Chain& chain, std::size_t j, Point2 q) {
    const auto [t, length] = along(chain, j, q);
    const bool first = j == 0 && t * length <= chain.cap_reach;
    const bool last = j + 1 == chain.segments && (1.0 - t) * length <= chain.cap_reach;
    return first || last;
}

bool on_tool_side(const Chain& chain, Point2 a, Point2 b, Point2 q) {
    return geometry2d::orient_sign(a, b, q) * chain.tool > 0;
}

// The side of an output edge whose middle q lies nearest segment j: a cap at an end of the
// chain; inside a segment by its orientation; at an interior vertex V by both its segments,
// either where V is convex toward the tool and both where it is concave (REQ-OFF-028).
Side side_of(const Chain& chain, std::size_t j, Point2 q) {
    if (is_cap(chain, j, q)) {
        return Side::cap;
    }
    const double t = std::clamp(along(chain, j, q).first, 0.0, 1.0);
    if (t > 0.0 && t < 1.0) {
        return on_tool_side(chain, at(chain, j), at(chain, j + 1), q) ? Side::tool : Side::other;
    }
    const std::size_t v = t <= 0.0 ? j : j + 1;
    if (v == 0 || v == chain.segments) {
        return Side::cap;
    }
    const Point2 before = at(chain, v - 1);
    const Point2 corner = at(chain, v);
    const Point2 after = at(chain, v + 1);
    const bool first = on_tool_side(chain, before, corner, q);
    const bool second = on_tool_side(chain, corner, after, q);
    const bool convex = geometry2d::orient_sign(before, corner, after) * chain.tool <= 0;
    return (convex ? (first || second) : (first && second)) ? Side::tool : Side::other;
}

struct Labelled {
    std::vector<Side> sides;     // per output edge
    std::vector<double> forward; // per output edge: its length along its nearest segment, signed
};

struct Edges {
    std::vector<double> middles; // x and y
    std::vector<std::pair<Point2, Point2>> ends;
};

Edges edges_of(const geometry2d::GridRegion& region) {
    Edges out;
    for (std::size_t loop = 0; loop < region.starts.size(); ++loop) {
        const auto first = static_cast<std::size_t>(region.starts.at(loop));
        const std::size_t end = loop + 1 < region.starts.size()
                                    ? static_cast<std::size_t>(region.starts.at(loop + 1))
                                    : region.points.size();
        for (std::size_t k = first; k < end; ++k) {
            const Point2 p = region.points.at(k);
            const Point2 q = region.points.at(k + 1 < end ? k + 1 : first);
            out.middles.insert(out.middles.end(), {(geometry2d::x(p) + geometry2d::x(q)) / 2,
                                                   (geometry2d::y(p) + geometry2d::y(q)) / 2});
            out.ends.emplace_back(p, q);
        }
    }
    return out;
}

// The side and the direction along the chain of every edge of the region's loops.
Labelled label(const geometry2d::GridRegion& region, const Chain& chain, const GrowInput& input,
               geometry2d::TieReach reach) {
    const Edges edges = edges_of(region);
    // The nearest segment of the chain given there and back: index k < n is segment k, and
    // k >= n is segment 2n - 1 - k run backwards (DEC-OFF-015).
    std::vector<std::int64_t> nearest(edges.ends.size());
    geometry2d::nearest_segments(edges.middles, input.ids.loops, reach.limit, nearest);
    Labelled out;
    for (std::size_t e = 0; e < nearest.size(); ++e) {
        const auto k = static_cast<std::size_t>(std::max<std::int64_t>(nearest.at(e), 0));
        const std::size_t j = k < chain.segments ? k : (2 * chain.segments) - 1 - k;
        const Point2 q = geometry2d::point(edges.middles, e);
        out.sides.push_back(nearest.at(e) < 0 ? Side::other : side_of(chain, j, q));
        const auto [from, length] = along(chain, j, edges.ends.at(e).first);
        const double to = along(chain, j, edges.ends.at(e).second).first;
        out.forward.push_back((to - from) * length);
    }
    return out;
}

// Vertices first .. first + count of a loop of `size` vertices starting at `base`.
struct Run {
    std::size_t base;
    std::size_t size;
    std::size_t first;
    std::size_t count;
};

void append(SidePieces& out, const geometry2d::GridRegion& region, Run run, bool closed,
            bool backwards) {
    out.starts.push_back(static_cast<std::int64_t>(out.points.size()));
    out.closed.push_back(closed ? 1 : 0);
    const std::size_t vertices = closed ? run.count : run.count + 1;
    for (std::size_t i = 0; i < vertices; ++i) {
        const std::size_t step = backwards ? vertices - 1 - i : i;
        const std::size_t v = run.base + ((run.first + step) % run.size);
        out.points.push_back(region.points.at(v));
        out.fixed.push_back(region.fixed.at(v));
    }
    // An edge keeps its ID whichever way it runs: the ID of the vertex it starts at, forwards.
    for (std::size_t i = 0; i < run.count; ++i) {
        const std::size_t step = backwards ? run.count - 1 - i : i;
        out.ids.push_back(region.ids.at(run.base + ((run.first + step) % run.size)));
    }
}

// The runs of tool-side edges of one loop: the whole loop as a closed piece, or each maximal run
// as an open piece, turned round when it runs against the chain.
void pieces_of_loop(SidePieces& out, const geometry2d::GridRegion& region, const Labelled& labels,
                    std::size_t base, std::size_t size) {
    const auto tool = [&](std::size_t i) {
        return labels.sides.at(base + (i % size)) == Side::tool;
    };
    const auto starts_run = [&](std::size_t i) { return tool(i) && !tool(i + size - 1); };
    std::size_t start = 0;
    while (start < size && !starts_run(start)) {
        ++start;
    }
    if (start == size) {
        if (tool(0)) {
            append(out, region, {.base = base, .size = size, .first = 0, .count = size}, true,
                   false);
        }
        return;
    }
    for (std::size_t i = start; i < start + size; ++i) {
        if (!starts_run(i)) {
            continue;
        }
        std::size_t count = 0;
        double forward = 0.0;
        while (count < size && tool(i + count)) {
            forward += labels.forward.at(base + ((i + count) % size));
            ++count;
        }
        append(out, region, {.base = base, .size = size, .first = i % size, .count = count}, false,
               forward < 0.0);
    }
}

} // namespace

SidePieces chain_side(const GrowInput& input, int tool_side, OffsetParams params,
                      OffsetLimits limits, geometry2d::TieReach reach) {
    SidePieces out;
    const geometry2d::GridRegion region =
        grow_chains(input, params, limits, reach, ChainEnds::butt);
    if (region.status != geometry2d::GridStatus::ok) {
        out.status = region.status;
        return out;
    }
    const Chain chain{.points = input.chains.points,
                      .segments = (input.chains.points.size() / 2) - 1,
                      .tool = tool_side,
                      .cap_reach = params.bias_units * limits.u};
    const Labelled labels = label(region, chain, input, reach);
    for (std::size_t loop = 0; loop < region.starts.size(); ++loop) {
        const auto base = static_cast<std::size_t>(region.starts.at(loop));
        const std::size_t end = loop + 1 < region.starts.size()
                                    ? static_cast<std::size_t>(region.starts.at(loop + 1))
                                    : region.points.size();
        pieces_of_loop(out, region, labels, base, end - base);
    }
    return out;
}

} // namespace splintercam::offset2d

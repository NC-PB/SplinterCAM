// SPDX-License-Identifier: Apache-2.0
// Self-contacts and their Seifert resolution (ours, 2026-10-08; DEC-G2D-033). Contacts come from
// exact orient2d signs; constructed crossing points are taken once from one segment, so both
// strands share the node bit for bit.
#include "selfcross.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <map>
#include <optional>
#include <tuple>

namespace splintercam::geometry2d {
namespace {

double x(Point2 p) {
    return std::get<0>(p);
}

double y(Point2 p) {
    return std::get<1>(p);
}

struct Position { // a point of the loop: segment `seg` at parameter t in [0, 1)
    std::size_t seg;
    double t;
    Point2 p;
    auto operator<=>(const Position& other) const {
        return std::pair{seg, t} <=> std::pair{other.seg, other.t};
    }
    bool operator==(const Position& other) const {
        return seg == other.seg && t == other.t;
    }
};

bool within_box(Point2 q, Point2 a, Point2 b) {
    return std::min(x(a), x(b)) <= x(q) && x(q) <= std::max(x(a), x(b)) &&
           std::min(y(a), y(b)) <= y(q) && y(q) <= std::max(y(a), y(b));
}

double parameter(Point2 q, Point2 a, Point2 b) {
    const double dx = x(b) - x(a);
    const double dy = y(b) - y(a);
    return std::clamp(((x(q) - x(a)) * dx + (y(q) - y(a)) * dy) / (dx * dx + dy * dy), 0.0, 1.0);
}

struct Loop {
    std::vector<Point2> v;
    [[nodiscard]] std::size_t size() const {
        return v.size();
    }
    [[nodiscard]] Point2 start(std::size_t i) const {
        return v.at(i);
    }
    [[nodiscard]] Point2 end(std::size_t i) const {
        return v.at((i + 1) % v.size());
    }
};

// A point q of the loop on segment j: its position there (a vertex when it is an end).
Position on(const Loop& loop, std::size_t j, Point2 q) {
    if (q == loop.start(j)) {
        return {.seg = j, .t = 0.0, .p = q};
    }
    if (q == loop.end(j)) {
        return {.seg = (j + 1) % loop.size(), .t = 0.0, .p = q};
    }
    return {.seg = j, .t = parameter(q, loop.start(j), loop.end(j)), .p = q};
}

// Adds where segments i and j (not neighbours) meet; false for a shared stretch.
bool meet(const Loop& loop, std::size_t i, std::size_t j, std::vector<Position>& out) {
    const Point2 a = loop.start(i);
    const Point2 b = loop.end(i);
    const Point2 c = loop.start(j);
    const Point2 d = loop.end(j);
    const std::array<int, 4> o{orient_sign(c, d, a), orient_sign(c, d, b), orient_sign(a, b, c),
                               orient_sign(a, b, d)};
    if (o == std::array<int, 4>{0, 0, 0, 0}) { // collinear: a point in common, or a stretch
        int shared = 0;
        for (const auto& [q, from, to] :
             {std::tuple{a, c, d}, std::tuple{b, c, d}, std::tuple{c, a, b}, std::tuple{d, a, b}}) {
            shared += within_box(q, from, to) ? 1 : 0;
        }
        const bool point = shared == 2 && (a == c || a == d || b == c || b == d);
        if (shared >= 2 && !point) {
            return false;
        }
    }
    if (std::get<0>(o) * std::get<1>(o) < 0 && std::get<2>(o) * std::get<3>(o) < 0) {
        const double cross_d = (x(b) - x(a)) * (y(d) - y(c)) - (y(b) - y(a)) * (x(d) - x(c));
        const double t = ((x(c) - x(a)) * (y(d) - y(c)) - (y(c) - y(a)) * (x(d) - x(c))) / cross_d;
        const Point2 p{x(a) + t * (x(b) - x(a)), y(a) + t * (y(b) - y(a))};
        out.push_back({.seg = i, .t = t, .p = p});
        out.push_back({.seg = j, .t = parameter(p, c, d), .p = p});
        return true;
    }
    for (const auto& [q, mine, other] :
         {std::tuple{a, i, j}, std::tuple{b, i, j}, std::tuple{c, j, i}, std::tuple{d, j, i}}) {
        const Point2 from = loop.start(other);
        const Point2 to = loop.end(other);
        if (orient_sign(from, to, q) == 0 && within_box(q, from, to)) {
            out.push_back(on(loop, mine, q));
            out.push_back(on(loop, other, q));
        }
    }
    return true;
}

// The ends at a node: the piece's index, whether it arrives, and the point it heads to.
struct End {
    std::size_t piece;
    bool incoming;
    Point2 toward;
};

// Counter-clockwise order of directions from `node`, by exact signs; nullopt for a tie.
std::optional<bool> before(Point2 node, Point2 p, Point2 q) {
    const auto half = [&](Point2 r) {
        return y(r) > y(node) || (y(r) == y(node) && x(r) > x(node)) ? 0 : 1;
    };
    if (half(p) != half(q)) {
        return half(p) < half(q);
    }
    const int turn = orient_sign(node, p, q);
    if (turn == 0) {
        return std::nullopt;
    }
    return turn > 0;
}

} // namespace

SelfCycles self_cycles(std::span<const double> flat) {
    Loop loop;
    for (std::size_t i = 0; i < flat.size() / 2; ++i) {
        loop.v.push_back(point(flat, i));
    }
    SelfCycles result;
    const std::size_t n = loop.size();
    std::vector<Position> positions;
    for (std::size_t i = 0; i < n; ++i) {
        for (std::size_t j = i + 2; j < n; ++j) {
            if (i == 0 && j == n - 1) {
                continue; // neighbours across the closing vertex
            }
            if (!meet(loop, i, j, positions)) {
                result.status = SelfContact::overlap;
                return result;
            }
        }
    }
    if (positions.empty()) {
        return result;
    }
    std::ranges::sort(positions);
    positions.erase(std::ranges::unique(positions).begin(), positions.end());
    // Pieces between consecutive positions; nodes are positions with equal points.
    std::map<std::pair<double, double>, std::size_t> node_of;
    std::vector<std::size_t> node(positions.size());
    std::vector<Point2> node_point;
    for (std::size_t k = 0; k < positions.size(); ++k) {
        const Point2 p = positions.at(k).p;
        const auto [entry, added] = node_of.try_emplace({x(p), y(p)}, node_of.size());
        if (added) {
            node_point.push_back(p);
        }
        node.at(k) = entry->second;
    }
    const std::size_t pieces = positions.size();
    std::vector<std::vector<Point2>> path(pieces);
    for (std::size_t k = 0; k < pieces; ++k) {
        const Position& from = positions.at(k);
        const Position& to = positions.at((k + 1) % pieces);
        std::vector<Point2>& line = path.at(k);
        line.push_back(from.p);
        std::size_t seg = from.seg;
        const bool wraps = to.seg < from.seg || (to.seg == from.seg && to.t <= from.t);
        std::size_t steps = (to.seg + (wraps ? n : 0)) - from.seg;
        for (std::size_t s = 0; s < steps; ++s) {
            seg = (seg + 1) % n;
            if (!(seg == to.seg && to.t == 0.0)) {
                line.push_back(loop.start(seg));
            }
        }
        line.push_back(to.p);
    }
    // Ends at each node, sorted counter-clockwise.
    std::vector<std::vector<End>> ends(node_of.size());
    for (std::size_t k = 0; k < pieces; ++k) {
        const std::vector<Point2>& line = path.at(k);
        ends.at(node.at(k)).push_back({.piece = k, .incoming = false, .toward = line.at(1)});
        ends.at(node.at((k + 1) % pieces))
            .push_back({.piece = k, .incoming = true, .toward = line.at(line.size() - 2)});
    }
    std::vector<std::size_t> next(pieces, pieces);
    for (std::size_t m = 0; m < ends.size(); ++m) {
        std::vector<End>& around = ends.at(m);
        const Point2 here = node_point.at(m);
        bool tie = false;
        std::ranges::sort(around, [&](const End& p, const End& q) {
            const std::optional<bool> order = before(here, p.toward, q.toward);
            tie = tie || (!order.has_value() && p.piece != q.piece);
            return order.value_or(p.piece < q.piece);
        });
        if (tie) {
            result.status = SelfContact::overlap;
            return result;
        }
        std::vector<std::size_t> open;
        for (std::size_t pass = 0; pass < 2; ++pass) {
            for (const End& e : around) {
                if (e.incoming) {
                    if (pass == 0 && next.at(e.piece) == pieces) {
                        open.push_back(e.piece);
                    }
                } else if (!open.empty()) {
                    const std::size_t arriving = open.back();
                    open.pop_back();
                    if (next.at(arriving) == pieces) {
                        next.at(arriving) = e.piece;
                    }
                }
            }
        }
    }
    result.status = SelfContact::cycles;
    std::vector<bool> used(pieces, false);
    for (std::size_t k = 0; k < pieces; ++k) {
        if (used.at(k)) {
            continue;
        }
        result.starts.push_back(static_cast<std::int64_t>(result.points.size()));
        result.first_edge.push_back(static_cast<std::int64_t>(k));
        for (std::size_t piece = k; !used.at(piece); piece = next.at(piece)) {
            used.at(piece) = true;
            const std::vector<Point2>& line = path.at(piece);
            result.points.insert(result.points.end(), line.begin(), line.end() - 1);
            if (next.at(piece) == pieces) {
                break; // an unpaired end: not reachable for a closed loop
            }
        }
    }
    for (const auto& entry : node_of) {
        result.nodes.push_back({entry.first.first, entry.first.second});
    }
    return result;
}

} // namespace splintercam::geometry2d

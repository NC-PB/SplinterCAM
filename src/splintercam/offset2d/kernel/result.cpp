// SPDX-License-Identifier: Apache-2.0
// The last stage of every offset2d Clipper2 call (research 02, Pinch points and nesting; Order and
// determinism; Source IDs; D-059, D-084; DEC-G2D-036, 042; DEC-OFF-013).
#include "result.hpp"

#include <algorithm>
#include <utility>
#include <vector>

namespace splintercam::offset2d {
namespace {

using geometry2d::GridRegion;
using geometry2d::GridStatus;

// Whether every vertex lies on one line, by exact integer cross products: grid coordinates span
// less than 2^26 units, so each product stays below 2^53 (REQ-OFF-037, DEC-OFF-013).
bool collinear(const Clipper2Lib::Path64& path) {
    const Clipper2Lib::Point64& a = path.front();
    const auto other =
        std::ranges::find_if(path, [&](const Clipper2Lib::Point64& p) { return p != a; });
    if (other == path.end()) {
        return true;
    }
    const std::int64_t dx = other->x - a.x;
    const std::int64_t dy = other->y - a.y;
    return std::ranges::all_of(path, [&](const Clipper2Lib::Point64& p) {
        return (dx * (p.y - a.y)) == (dy * (p.x - a.x));
    });
}

// The source ID of each output edge: among the input edges within eps_len of the one nearest to its
// middle, the first class (material, cleared, air), then the lowest ID (REQ-OFF-034, D-059);
// false when no input edge lies within the reach, as the result is then no offset of the input.
bool assign_ids(std::span<const double> middles, const IdSource& input, geometry2d::TieReach reach,
                std::vector<std::int64_t>& ids) {
    const std::vector<geometry2d::Tie> ties = geometry2d::nearest_ties(middles, input.loops, reach);
    // (class, ID) per point; INT8_MAX marks "none yet", since any int64 may be a source ID.
    std::vector<std::pair<std::int8_t, std::int64_t>> best(middles.size() / 2,
                                                           {INT8_MAX, INT64_MAX});
    for (const geometry2d::Tie& tie : ties) {
        const auto segment = static_cast<std::size_t>(tie.segment);
        const std::pair candidate{input.classes.subspan(segment, 1).front(),
                                  input.source_ids.subspan(segment, 1).front()};
        auto& chosen = best.at(static_cast<std::size_t>(tie.point));
        chosen = std::min(chosen, candidate);
    }
    ids.clear();
    for (const auto& [edge_class, id] : best) {
        if (edge_class == INT8_MAX) {
            return false;
        }
        ids.push_back(id);
    }
    return true;
}

// The loops back in mm, with the fixed flags and the source IDs.
void fill_region(const std::vector<Clipper2Lib::Path64>& loops, geometry2d::Frame frame, double u,
                 const IdSource& input, geometry2d::TieReach reach, GridRegion& result) {
    result.fixed = geometry2d::shared_points(loops);
    std::vector<double> middles;
    const auto mm = [&](double value, double centre) { return centre + (value * u); };
    for (const Clipper2Lib::Path64& loop : loops) {
        result.starts.push_back(static_cast<std::int64_t>(result.points.size()));
        for (std::size_t k = 0; k < loop.size(); ++k) {
            const Clipper2Lib::Point64& p = loop.at(k);
            const Clipper2Lib::Point64& q = loop.at((k + 1) % loop.size());
            result.points.push_back(
                {mm(static_cast<double>(p.x), frame.cx), mm(static_cast<double>(p.y), frame.cy)});
            middles.insert(middles.end(), {mm(static_cast<double>(p.x + q.x) / 2, frame.cx),
                                           mm(static_cast<double>(p.y + q.y) / 2, frame.cy)});
        }
    }
    if (!assign_ids(middles, input, reach, result.ids)) {
        result = GridRegion{};
        result.status = GridStatus::failed;
    }
}

} // namespace

GridRegion finish_region(const Clipper2Lib::Paths64& solution, geometry2d::Frame frame, double u,
                         const IdSource& ids, geometry2d::TieReach reach) {
    std::vector<Clipper2Lib::Path64> loops;
    for (const Clipper2Lib::Path64& path : solution) {
        geometry2d::split_pinches(path, loops);
    }
    // A piece of area 0 (a path that runs out and back) is no region (REQ-OFF-037), tested exactly.
    std::erase_if(loops, collinear);
    geometry2d::canonical(loops);
    GridRegion result;
    fill_region(loops, frame, u, ids, reach, result);
    return result;
}

} // namespace splintercam::offset2d

// SPDX-License-Identifier: Apache-2.0
// The region offset (research 02, The kernel call, steps 1, 2, 5 to 7; SRC-122 for Clipper2's
// behaviour).
#include "offset.hpp"

#include <algorithm>
#include <clipper2/clipper.h>
#include <cmath>
#include <cstdint>
#include <numbers>
#include <vector>

namespace splintercam::offset2d {
namespace {

using geometry2d::GridRegion;
using geometry2d::GridStatus;

// Clipper2's default miter limit; it has no effect with round joins (SRC-122, ClipperOffset).
constexpr double miter_limit = 2.0;

enum class Extreme : std::uint8_t { none, outer, hole };

// The path Clipper2 takes for the outer loop, rule for rule: the one holding the largest y, then
// the smallest x (the first on a tie; area 0 skipped); a hole there reverses the whole offset, and
// with no path left Clipper2 makes δ positive (SRC-122: GetLowestClosedPathInfo, ExecuteInternal;
// research 02, The kernel call, step 3; DEC-OFF-008).
Extreme extreme_path(const Clipper2Lib::Paths64& paths) {
    Clipper2Lib::Point64 extreme(INT64_MAX, INT64_MIN);
    Extreme found = Extreme::none;
    for (const Clipper2Lib::Path64& path : paths) {
        const double area = Clipper2Lib::Area(path);
        if (area == 0.0) {
            continue;
        }
        for (const Clipper2Lib::Point64& p : path) {
            if (p.y > extreme.y || (p.y == extreme.y && p.x < extreme.x)) {
                extreme = p;
                found = area < 0.0 ? Extreme::hole : Extreme::outer;
            }
        }
    }
    return found;
}

// A guard against a whole inverted result, such as Clipper2's orientation guess gives (research
// 02, The kernel call, step 3), not a proof of correctness (DEC-OFF-008): a shrunk region is not
// larger, a grown one not smaller, than its input, allowing each point the bias of rounding.
bool plausible(const Clipper2Lib::Paths64& input, const Clipper2Lib::Paths64& output,
               OffsetParams params) {
    const double before = Clipper2Lib::Area(input);
    const double after = Clipper2Lib::Area(output);
    double perimeter = 0.0;
    for (const Clipper2Lib::Path64& path : input) {
        perimeter += Clipper2Lib::Length(path, true);
    }
    const double slack = params.bias_units * perimeter;
    const bool sized = params.delta < 0.0 ? after <= before + slack : after >= before - slack;
    return sized && after >= -slack; // an inverted result also turns its loops round
}

// The guard of research 02, The kernel call, step 3 (REQ-OFF-023, DEC-OFF-011): a CCW triangle of
// side s = ⌈|δ|⌉ grid units, so its inradius s/(1 + √5) stays below |δ|/2, its base more than
// 2·|δ| + 6u (the rounding margin) above the input's top; its apex then holds Clipper2's extreme
// point. Its x extent may pass the input's right edge; the y span, checked after, always binds.
struct Guard {
    Clipper2Lib::Path64 triangle;
    std::int64_t input_top;    // the input's largest y, grid units
    std::int64_t input_bottom; // its smallest y
    std::int64_t height;       // what the guard adds to the input's span in y
};

Guard guard_above(const Clipper2Lib::Paths64& paths, double reach_units, double margin_units) {
    std::int64_t top = INT64_MIN;
    std::int64_t bottom = INT64_MAX;
    std::int64_t left = INT64_MAX;
    for (const Clipper2Lib::Path64& path : paths) {
        for (const Clipper2Lib::Point64& p : path) {
            top = std::max(top, p.y);
            bottom = std::min(bottom, p.y);
            left = std::min(left, p.x);
        }
    }
    const auto side = static_cast<std::int64_t>(std::ceil(reach_units));
    const auto gap = static_cast<std::int64_t>(std::ceil((2 * reach_units) + margin_units)) + 1;
    const std::int64_t base = top + gap;
    return {.triangle = {{left, base}, {left + side, base}, {left + (side / 2), base + side}},
            .input_top = top,
            .input_bottom = bottom,
            .height = gap + side};
}

// Adds the guard to the paths: too_large when the input's height, the guard's and 2·|δ| reach the
// span limit (REQ-OFF-018); failed unless Clipper2's rule now picks it, an outer loop.
GridStatus add_guard(Clipper2Lib::Paths64& paths, const Guard& guard, double reach_units,
                     double max_span_units) {
    const auto height = static_cast<double>(guard.input_top - guard.input_bottom + guard.height);
    if (height + (2 * reach_units) >= max_span_units) {
        return GridStatus::too_large;
    }
    paths.push_back(guard.triangle);
    return extreme_path(paths) == Extreme::outer ? GridStatus::ok : GridStatus::failed;
}

// Removes what the guard leaves, the loops lying wholly above the input's top grown by |δ|: one
// when growing, none when shrinking (research 02 asks for at most one; exactly, ours,
// DEC-OFF-011). Any other count means the guard merged with the input or misbehaved: false.
bool remove_guard(Clipper2Lib::Paths64& solution, const Guard& guard, double reach_units,
                  bool grows) {
    const double above = static_cast<double>(guard.input_top) + reach_units;
    const auto lies_above = [&](const Clipper2Lib::Path64& path) {
        return std::ranges::all_of(
            path, [&](const Clipper2Lib::Point64& p) { return static_cast<double>(p.y) > above; });
    };
    const auto removed = std::erase_if(solution, lies_above);
    return removed == (grows ? 1U : 0U);
}

// The source ID of each output edge: among the input edges within eps_len of the one nearest to its
// middle, the first class (material, cleared, air), then the lowest ID (REQ-OFF-034, D-059);
// false when no input edge lies within the reach, as the result is then no offset of the input.
bool assign_ids(std::span<const double> middles, const OffsetInput& input,
                geometry2d::TieReach reach, std::vector<std::int64_t>& ids) {
    const std::vector<geometry2d::Tie> ties = geometry2d::nearest_ties(middles, input.loops, reach);
    const std::size_t count = middles.size() / 2;
    ids.assign(count, -1);
    std::vector<std::int8_t> best(count, INT8_MAX);
    for (const geometry2d::Tie& tie : ties) {
        const auto point = static_cast<std::size_t>(tie.point);
        const auto segment = static_cast<std::size_t>(tie.segment);
        const std::int8_t edge_class = input.classes.subspan(segment, 1).front();
        const std::int64_t id = input.source_ids.subspan(segment, 1).front();
        if (std::pair{edge_class, id} < std::pair{best.at(point), ids.at(point)} ||
            ids.at(point) < 0) {
            best.at(point) = edge_class;
            ids.at(point) = id;
        }
    }
    return std::ranges::none_of(ids, [](std::int64_t id) { return id < 0; });
}

// The loops back in mm, with the fixed flags and the source IDs.
void fill_region(const std::vector<Clipper2Lib::Path64>& loops, geometry2d::Frame frame,
                 const OffsetInput& input, const OffsetLimits& limits, double id_reach,
                 GridRegion& result) {
    result.fixed = geometry2d::shared_points(loops);
    std::vector<double> middles;
    const auto mm = [&](double value, double centre) { return centre + (value * limits.u); };
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
    if (!assign_ids(middles, input, {.limit = id_reach, .eps = limits.eps_len}, result.ids)) {
        result = GridRegion{};
        result.status = GridStatus::failed;
    }
}

} // namespace

GridRegion offset_loops(const OffsetInput& input, OffsetParams params, OffsetLimits limits) {
    GridRegion result;
    const double reach = std::abs(params.delta);
    // The input plus 2·|δ| must span less than the limit: the offset paths reach |δ| beyond the
    // input on every side, and the union and pinch tests run on them (REQ-OFF-018, DEC-OFF-010).
    geometry2d::Frame frame{};
    const geometry2d::GridLimits room{
        .u = limits.u, .max_span_units = limits.max_span_units - (2 * reach / limits.u)};
    if (!geometry2d::frame_of(input.loops.points, room, frame)) {
        result.status = GridStatus::too_large;
        return result;
    }
    // Steps per turn of a round join, DoRound's π / acos(1 − a/|δ|); its other term, π·|δ|, never
    // binds with |δ| ≥ a ≥ 2u (research 02, The kernel call, step 5; REQ-OFF-014).
    const double steps = std::numbers::pi / std::acos(1.0 - (params.arc_tol / reach));
    const Clipper2Lib::Paths64 grid = geometry2d::to_grid(input.loops, frame, limits.u);
    const Extreme extreme = extreme_path(grid);
    if (extreme == Extreme::none) {
        return result; // every path has area 0 on the grid: nothing to offset, an empty region
    }
    if (!(steps <= limits.join_steps_max)) {
        result.status = GridStatus::failed;
        return result;
    }
    const double reach_units = reach / limits.u;
    Clipper2Lib::Paths64 paths = grid;
    Guard guard{};
    if (extreme == Extreme::hole) {
        guard = guard_above(grid, reach_units, params.margin_units);
        result.status = add_guard(paths, guard, reach_units, limits.max_span_units);
        if (result.status != GridStatus::ok) {
            return result;
        }
    }
    // One call: Clipper2 offsets every path and unites them with the Positive rule inside it, so
    // the region is rounded once (REQ-OFF-022; SRC-122, ExecuteInternal; DEC-G2D-026).
    Clipper2Lib::ClipperOffset offsetter(miter_limit, params.arc_tol / limits.u);
    offsetter.AddPaths(paths, Clipper2Lib::JoinType::Round, Clipper2Lib::EndType::Polygon);
    Clipper2Lib::Paths64 solution;
    offsetter.Execute(params.delta / limits.u, solution);
    // Clipper2 2.0.1 reports no failure here: ErrorCode() is always 0 and the result of its inner
    // union is dropped (SRC-122, ExecuteInternal), so only the area check guards (DEC-OFF-008).
    const bool guarded =
        extreme != Extreme::hole || remove_guard(solution, guard, reach_units, params.delta > 0.0);
    if (!guarded || !plausible(grid, solution, params)) {
        result.status = GridStatus::failed;
        return result;
    }
    std::vector<Clipper2Lib::Path64> loops;
    for (const Clipper2Lib::Path64& path : solution) {
        geometry2d::split_pinches(path, loops);
    }
    // A piece of area 0 (a path that runs out and back) is no region (REQ-OFF-037).
    std::erase_if(loops,
                  [](const Clipper2Lib::Path64& loop) { return Clipper2Lib::Area(loop) == 0.0; });
    geometry2d::canonical(loops);
    // Every output edge lies in the band [t, t + a + 2·bias·u] of the input, so |δ| + bias·u
    // reaches its source edge (REQ-OFF-025, DEC-OFF-009).
    fill_region(loops, frame, input, limits, reach + (params.bias_units * limits.u), result);
    return result;
}

} // namespace splintercam::offset2d

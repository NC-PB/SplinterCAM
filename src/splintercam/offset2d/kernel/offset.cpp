// SPDX-License-Identifier: Apache-2.0
// The region offset (research 02, The kernel call, steps 1, 2, 5 to 7; SRC-122 for Clipper2's
// behaviour).
#include "offset.hpp"

#include <clipper2/clipper.h>
#include <cmath>
#include <numbers>
#include <vector>

namespace splintercam::offset2d {
namespace {

using geometry2d::GridRegion;
using geometry2d::GridStatus;

// Clipper2's default miter limit; it has no effect with round joins (SRC-122, ClipperOffset).
constexpr double miter_limit = 2.0;

// Whether Clipper2 takes a hole for the outer loop, rule for rule: the path holding the largest y,
// then the smallest x (the first on a tie; area 0 skipped); a negative area reverses the whole
// offset (SRC-122: GetLowestClosedPathInfo; research 02, The kernel call, step 3; DEC-OFF-008).
bool extreme_path_is_hole(const Clipper2Lib::Paths64& paths) {
    Clipper2Lib::Point64 extreme(INT64_MAX, INT64_MIN);
    bool hole = false;
    for (const Clipper2Lib::Path64& path : paths) {
        const double area = Clipper2Lib::Area(path);
        if (area == 0.0) {
            continue;
        }
        for (const Clipper2Lib::Point64& p : path) {
            if (p.y > extreme.y || (p.y == extreme.y && p.x < extreme.x)) {
                extreme = p;
                hole = area < 0.0;
            }
        }
    }
    return hole;
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

// The loops back in mm, with the fixed flags and the provisional source IDs (DEC-OFF-009).
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
    std::vector<std::int64_t> nearest(result.points.size());
    geometry2d::nearest_segments(middles, input.loops, id_reach, nearest);
    for (const std::int64_t segment : nearest) {
        result.ids.push_back(
            segment < 0 ? -1
                        : input.source_ids.subspan(static_cast<std::size_t>(segment), 1).front());
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
    if (!(steps <= limits.join_steps_max) || extreme_path_is_hole(grid)) {
        result.status = GridStatus::failed;
        return result;
    }
    // One call: Clipper2 offsets every path and unites them with the Positive rule inside it, so
    // the region is rounded once (REQ-OFF-022; SRC-122, ExecuteInternal; DEC-G2D-026).
    Clipper2Lib::ClipperOffset offsetter(miter_limit, params.arc_tol / limits.u);
    offsetter.AddPaths(grid, Clipper2Lib::JoinType::Round, Clipper2Lib::EndType::Polygon);
    Clipper2Lib::Paths64 solution;
    offsetter.Execute(params.delta / limits.u, solution);
    if (offsetter.ErrorCode() != 0 || !plausible(grid, solution, params)) {
        result.status = GridStatus::failed;
        return result;
    }
    std::vector<Clipper2Lib::Path64> loops;
    for (const Clipper2Lib::Path64& path : solution) {
        geometry2d::split_pinches(path, loops);
    }
    geometry2d::canonical(loops);
    // Every output edge lies in the band [t, t + a + 2·bias·u] of the input, so |δ| + bias·u
    // reaches its source edge (REQ-OFF-025, DEC-OFF-009).
    fill_region(loops, frame, input, limits, reach + (params.bias_units * limits.u), result);
    return result;
}

} // namespace splintercam::offset2d

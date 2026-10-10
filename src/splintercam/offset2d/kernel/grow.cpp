// SPDX-License-Identifier: Apache-2.0
// Grown chains (research 02, Open chains and Booleans; SRC-122 for ClipperOffset's round ends).
#include "grow.hpp"

#include <clipper2/clipper.h>
#include <cmath>
#include <numbers>

namespace splintercam::offset2d {

geometry2d::GridRegion grow_chains(const GrowInput& input, OffsetParams params, OffsetLimits limits,
                                   geometry2d::TieReach reach, ChainEnds ends) {
    geometry2d::GridRegion result;
    if (input.chains.points.empty()) {
        return result; // no chain: an empty region
    }
    // The chains plus 2·δ must span less than the limit (REQ-OFF-031, as DEC-OFF-010).
    geometry2d::Frame frame{};
    const geometry2d::GridLimits room{
        .u = limits.u, .max_span_units = limits.max_span_units - (2 * params.delta / limits.u)};
    if (!geometry2d::frame_of(input.chains.points, room, frame)) {
        result.status = geometry2d::GridStatus::too_large;
        return result;
    }
    // Steps per turn of a round join or end, DoRound's π / acos(1 − a/δ) (research 02, The kernel
    // call, step 5; REQ-OFF-014).
    const double steps = std::numbers::pi / std::acos(1.0 - (params.arc_tol / params.delta));
    if (!(steps <= limits.join_steps_max)) {
        result.status = geometry2d::GridStatus::failed;
        return result;
    }
    // Open paths take no orientation guess (SRC-122: only EndType Polygon does), so no guard.
    constexpr double miter_limit = 2.0; // Clipper2's default, without effect on round joins
    Clipper2Lib::ClipperOffset offsetter(miter_limit, params.arc_tol / limits.u);
    offsetter.AddPaths(
        geometry2d::to_grid(input.chains, frame, limits.u), Clipper2Lib::JoinType::Round,
        ends == ChainEnds::round ? Clipper2Lib::EndType::Round : Clipper2Lib::EndType::Butt);
    Clipper2Lib::Paths64 solution;
    offsetter.Execute(params.delta / limits.u, solution);
    return finish_region(solution, frame, limits.u, input.ids, reach);
}

} // namespace splintercam::offset2d

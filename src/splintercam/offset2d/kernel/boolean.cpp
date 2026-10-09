// SPDX-License-Identifier: Apache-2.0
// Booleans of regions (research 02, Booleans; Vatti 1992 through Clipper2 2.0.1, SRC-004, SRC-122).
#include "boolean.hpp"

#include <array>
#include <clipper2/clipper.h>
#include <vector>

namespace splintercam::offset2d {

geometry2d::GridRegion clip_regions(const ClipInput& input, ClipOp op,
                                    geometry2d::GridLimits limits, geometry2d::TieReach reach) {
    geometry2d::GridRegion result;
    if (input.subject.points.empty() && input.clip.points.empty()) {
        return result; // nothing on either side: an empty region, and no frame to take
    }
    // Both operands share one frame, so they round alike (REQ-G2D-033) and the span is theirs
    // together (REQ-OFF-031).
    std::vector<double> both(input.subject.points.begin(), input.subject.points.end());
    both.insert(both.end(), input.clip.points.begin(), input.clip.points.end());
    geometry2d::Frame frame{};
    if (!geometry2d::frame_of(both, limits, frame)) {
        result.status = geometry2d::GridStatus::too_large;
        return result;
    }
    Clipper2Lib::Clipper64 clipper;
    clipper.AddSubject(geometry2d::to_grid(input.subject, frame, limits.u));
    clipper.AddClip(geometry2d::to_grid(input.clip, frame, limits.u));
    constexpr std::array types{Clipper2Lib::ClipType::Union, Clipper2Lib::ClipType::Difference,
                               Clipper2Lib::ClipType::Intersection};
    Clipper2Lib::Paths64 solution;
    // Positive for both operands: they are normalised regions, where it equals NonZero, and it
    // keeps the right side where flattened loops overlap (research 02, Booleans; ours).
    if (!clipper.Execute(types.at(static_cast<std::size_t>(op)), Clipper2Lib::FillRule::Positive,
                         solution)) {
        result.status = geometry2d::GridStatus::failed;
        return result;
    }
    return finish_region(solution, frame, limits.u, input.ids, reach);
}

} // namespace splintercam::offset2d

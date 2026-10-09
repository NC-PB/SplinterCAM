// SPDX-License-Identifier: Apache-2.0
// Union, difference and intersection of regions in one Clipper64 call on geometry2d's grid
// (research 02, Booleans).
#pragma once

#include "result.hpp"

#include <cstdint>

namespace splintercam::offset2d {

enum class ClipOp : std::uint8_t { join = 0, difference = 1, intersection = 2 };

struct ClipInput {
    geometry2d::Polylines subject; // closed loops; the difference keeps what is not in the clip
    geometry2d::Polylines clip;
    IdSource ids; // the edges of both, for the source IDs (REQ-OFF-035)
};

// The Boolean of subject and clip with the Positive fill rule for both (REQ-OFF-030): too_large
// when both together span the limit (REQ-OFF-031), failed when Clipper2 reports failure; the
// result through `finish_region`. No exception leaves it.
[[nodiscard]] geometry2d::GridRegion clip_regions(const ClipInput& input, ClipOp op,
                                                  geometry2d::GridLimits limits,
                                                  geometry2d::TieReach reach);

} // namespace splintercam::offset2d

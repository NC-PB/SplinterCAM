// SPDX-License-Identifier: Apache-2.0
// Open chains grown on both sides with round ends in one ClipperOffset call (research 02, Open
// chains; Booleans, the machined area of RR-001).
#pragma once

#include "offset.hpp"
#include "result.hpp"

namespace splintercam::offset2d {

struct GrowInput {
    geometry2d::Polylines chains; // open chains: each runs from its start to the next start
    IdSource ids;                 // the same chains given there and back, for the source IDs
};

// The area within delta of the chains (JoinType Round, EndType Round, ArcTolerance arc_tol):
// too_large when the chains plus 2·delta span the limit (REQ-OFF-031), failed when a join needs
// more steps than the limit; the result through `finish_region`. No exception leaves it.
[[nodiscard]] geometry2d::GridRegion grow_chains(const GrowInput& input, OffsetParams params,
                                                 OffsetLimits limits, geometry2d::TieReach reach);

} // namespace splintercam::offset2d

// SPDX-License-Identifier: Apache-2.0
// One side of an open chain: the tool-centre path of a profile along it (research 02, Open chains;
// D-025).
#pragma once

#include "grow.hpp"

#include <cstdint>
#include <vector>

namespace splintercam::offset2d {

// The pieces as a region (open pieces with one source ID per edge, the vertex count less one) and
// whether each is closed; open pieces first, along the chain, then closed ones.
struct SidePieces {
    geometry2d::GridRegion region;
    std::vector<std::uint8_t> closed;
};

// The area within delta of the one chain of `input`, with round ends, and of its boundary the
// edges on the tool side (+1 left of the chain's direction, -1 right), the caps nearest an end
// left out (REQ-OFF-028, DEC-OFF-018). No exception leaves it.
[[nodiscard]] SidePieces chain_side(const GrowInput& input, int tool_side, OffsetParams params,
                                    OffsetLimits limits, geometry2d::TieReach reach);

} // namespace splintercam::offset2d

// SPDX-License-Identifier: Apache-2.0
// One side of an open chain: the tool-centre path of a profile along it (research 02, Open chains;
// D-025).
#pragma once

#include "grow.hpp"

#include <cstdint>
#include <vector>

namespace splintercam::offset2d {

inline constexpr std::uint8_t closed_flag = 1;   // the piece is a loop, its closing edge implied
inline constexpr std::uint8_t enclosed_flag = 2; // not reachable from the first open piece

// The pieces as a region (open pieces with one source ID per edge, the vertex count less one) and
// their flags; open pieces first, along the chain, then closed ones; every piece with the chain on
// the side away from the tool.
struct SidePieces {
    geometry2d::GridRegion region;
    std::vector<std::uint8_t> flags;
};

// The area within delta of the one chain of `input`, with round ends, and of its boundary the
// edges on the tool side (+1 left of the chain's direction, -1 right), the caps nearest an end
// left out (REQ-OFF-028, DEC-OFF-018). No exception leaves it.
[[nodiscard]] SidePieces chain_side(const GrowInput& input, int tool_side, OffsetParams params,
                                    OffsetLimits limits, geometry2d::TieReach reach);

} // namespace splintercam::offset2d

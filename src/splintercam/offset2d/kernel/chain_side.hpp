// SPDX-License-Identifier: Apache-2.0
// One side of an open chain: the tool-centre path of a profile along it (research 02, Open chains;
// D-025).
#pragma once

#include "grow.hpp"

#include <cstdint>
#include <vector>

namespace splintercam::offset2d {

// The pieces of the tool side, in mm: an open piece runs in the chain's direction and has one
// source ID per edge (its vertices less one); a closed piece keeps its loop's traversal, its
// closing edge implied, one ID per vertex.
struct SidePieces {
    geometry2d::GridStatus status = geometry2d::GridStatus::ok;
    std::vector<geometry2d::Point2> points;
    std::vector<std::int64_t> starts;
    std::vector<std::uint8_t> closed;
    std::vector<std::int64_t> ids;
    std::vector<std::uint8_t> fixed;
};

// The area within delta of the one chain of `input`, with Butt ends, and of its boundary the edges
// on the tool side (+1 left of the chain's direction, -1 right), decided per edge from the chain
// point nearest its middle; the caps, nearest an end of the chain, belong to neither side
// (REQ-OFF-028). No exception leaves it.
[[nodiscard]] SidePieces chain_side(const GrowInput& input, int tool_side, OffsetParams params,
                                    OffsetLimits limits, geometry2d::TieReach reach);

} // namespace splintercam::offset2d

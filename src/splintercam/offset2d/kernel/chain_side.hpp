// SPDX-License-Identifier: Apache-2.0
// One side of an open chain: the tool-centre path of a profile along it (research 02, Open chains;
// D-025).
#pragma once

#include "grow.hpp"

#include <cstdint>
#include <optional>
#include <span>
#include <utility>
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

// Which points of a chain (at least one) to keep: the first, then each more than `threshold` from
// the last kept one, and the last, which drops the kept points within `threshold` of it; so no
// segment is threshold or shorter, unless only the two ends are left, and no point moves
// (DEC-OFF-018).
[[nodiscard]] std::vector<std::uint8_t> keep_chain(std::span<const double> points,
                                                   double threshold);

// Where an open chain is not simple (SRC-030, p. 19, Def. 5.3; DEC-OFF-021): a fold, where a
// segment runs back over the one before it (opposite directions, within `tol` of its line,
// overlapping by more than `tol`), the first along the chain; else a contact, where two segments
// not next to each other come within `tol`, the first pair along the chain; none if it is simple.
struct Contact {
    geometry2d::Point2 at;
    bool fold = false;
    std::pair<std::size_t, std::size_t> pair{};
};
[[nodiscard]] std::optional<Contact> find_contact(std::span<const double> points, double tol);

// The area within delta of the one chain of `input`, with round ends, and of its boundary the
// edges on the tool side (+1 left of the chain's direction, -1 right), the caps nearest an end
// left out (REQ-OFF-028, DEC-OFF-018). No exception leaves it.
[[nodiscard]] SidePieces chain_side(const GrowInput& input, int tool_side, OffsetParams params,
                                    OffsetLimits limits, geometry2d::TieReach reach);

} // namespace splintercam::offset2d

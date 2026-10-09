// SPDX-License-Identifier: Apache-2.0
// The last stage of every offset2d Clipper2 call: Clipper2's paths as a region (research 02, Pinch
// points and nesting; Order and determinism; Source IDs).
#pragma once

#include "../../geometry2d/kernel/distance.hpp"
#include "../../geometry2d/kernel/grid.hpp"

#include <clipper2/clipper.h>
#include <cstdint>
#include <span>

namespace splintercam::offset2d {

// The input edges whose IDs the output takes: closed polylines (an open chain given there and
// back), with the source ID and the class (material 0, cleared 1, air 2; D-059) of the edge that
// starts at each vertex.
struct IdSource {
    geometry2d::Polylines loops;
    std::span<const std::int64_t> source_ids;
    std::span<const std::int8_t> classes;
};

// The paths split at pinch points (REQ-OFF-036), pieces of area 0 dropped (037), in the canonical
// order (038), back in mm with their fixed flags and each edge's source ID by the class tie within
// `reach` (034); failed when an edge has no input edge within the reach.
[[nodiscard]] geometry2d::GridRegion finish_region(const Clipper2Lib::Paths64& solution,
                                                   geometry2d::Frame frame, double u,
                                                   const IdSource& ids, geometry2d::TieReach reach);

} // namespace splintercam::offset2d

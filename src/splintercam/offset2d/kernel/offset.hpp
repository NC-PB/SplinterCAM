// SPDX-License-Identifier: Apache-2.0
// The region offset: flattened, normalised loops offset by delta in one ClipperOffset call on
// geometry2d's grid (research 02, The kernel call; D-058, D-132).
#pragma once

#include "../../geometry2d/kernel/distance.hpp"
#include "../../geometry2d/kernel/grid.hpp"

#include <cstdint>
#include <span>

namespace splintercam::offset2d {

// delta = ±(t + a + bias·u) in mm, negative to shrink; arc_tol = a in mm; bias in grid units.
struct OffsetParams {
    double delta;
    double arc_tol;
    double bias_units;
};

// The grid unit u in mm, the span limit and the most steps per turn a round join may take.
struct OffsetLimits {
    double u;
    double max_span_units;
    double join_steps_max;
};

struct OffsetInput {
    geometry2d::Polylines loops; // side-correct flattened and normalised (REQ-OFF-021)
    std::span<const std::int64_t> source_ids;
};

// The offset region, or too_large (REQ-OFF-018) or failed (REQ-OFF-014, DEC-OFF-008); IDs
// provisional (DEC-OFF-009). No exception leaves it.
[[nodiscard]] geometry2d::GridRegion offset_loops(const OffsetInput& input, OffsetParams params,
                                                  OffsetLimits limits);

} // namespace splintercam::offset2d

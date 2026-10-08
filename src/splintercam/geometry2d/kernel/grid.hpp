// SPDX-License-Identifier: Apache-2.0
// The bridge to Clipper2's integer grid (research 01, Tolerances, resolution chain, stages 3 to 5;
// D-058, D-132).
#pragma once

#include "distance.hpp"

#include <cstdint>
#include <vector>

namespace splintercam::geometry2d {

enum class GridStatus : std::int8_t {
    ok = 0,
    too_large = 1, // the input spans the limit or more in x or y (REQ-G2D-034)
    failed = 2,    // Clipper2 reported failure
};

// The grid of one Clipper2 call: its unit u and the largest span it accepts, in grid units.
struct GridLimits {
    double u;
    double max_span_units;
};

// The area of b minus a, and of b, on the grid, with the NonZero fill rule (REQ-G2D-169): both
// polylines re-centred together on their bounding box and rounded to u.
struct GridAreas {
    GridStatus status = GridStatus::ok;
    double difference_mm2 = 0.0;
    double b_mm2 = 0.0;
};
[[nodiscard]] GridAreas grid_difference(const Polylines& b, const Polylines& a, GridLimits limits);

// A region through the grid: re-centred on the input's bounding box, rounded to u, Clipper2's
// union of the flattened loops with `fill_rule` (Clipper2Lib::FillRule, 0 to 2), mapped back
// (REQ-G2D-030, 033, 034); every pinch point split by exact integer tests with its
// vertices fixed (REQ-G2D-181), each vertex given the source ID of the input edge nearest to the
// middle of the output edge that starts there, within `id_reach` (REQ-G2D-180), else -1.
struct RegionInput {
    Polylines loops;
    std::span<const std::int64_t> source_ids;
    int fill_rule;
    double id_reach;
};
struct GridRegion {
    GridStatus status = GridStatus::ok;
    std::vector<Point2> points;
    std::vector<std::int64_t> starts;
    std::vector<std::int64_t> ids;
    std::vector<std::uint8_t> fixed;
};
[[nodiscard]] GridRegion grid_region(const RegionInput& input, GridLimits limits);

} // namespace splintercam::geometry2d

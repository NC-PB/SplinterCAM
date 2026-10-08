// SPDX-License-Identifier: Apache-2.0
// The bridge to Clipper2's integer grid (research 01, Tolerances, resolution chain, stages 3 to 5;
// D-058, D-132).
#pragma once

#include "distance.hpp"

#include <clipper2/clipper.h>
#include <cstdint>
#include <span>
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

// The steps of `grid_region`, shared with offset2d so both modules re-centre, round, split and
// order alike, bit for bit (DEC-OFF-001, DEC-G2D-041; REQ-G2D-033, 034, 181).

// The centre of a grid call's input, subtracted before rounding (REQ-G2D-033).
struct Frame {
    double cx;
    double cy;
};

// The centre of the points' bounding box (x, y pairs) into `frame`; false, with `frame`
// unchanged, when they span the limit or more in x or y (REQ-G2D-034).
[[nodiscard]] bool frame_of(std::span<const double> points, GridLimits limits, Frame& frame);

// The closed polylines as Clipper2 paths: each point less the frame's centre, divided by u and
// rounded to the nearest integer, halves away from zero (std::llround).
[[nodiscard]] Clipper2Lib::Paths64 to_grid(const Polylines& input, Frame frame, double u);

// Splits `path` at every point it passes twice into loops that each keep the traversal of their
// vertices, appended to `out`; pieces of fewer than 3 vertices are dropped (REQ-G2D-181).
void split_pinches(const Clipper2Lib::Path64& path, std::vector<Clipper2Lib::Path64>& out);

// The loops in an order of their own, not Clipper2's (its intersection sort breaks ties by the
// standard library): each starts at its smallest point, then by that point and signed area
// (DEC-G2D-036).
void canonical(std::vector<Clipper2Lib::Path64>& loops);

// Per vertex of `loops`, in order, 1 where two or more loop vertices share its point, a pinch
// split or a touch of two loops, else 0: the fixed nodes (D-084), the same whichever way
// Clipper2 returned a touch (DEC-G2D-036).
[[nodiscard]] std::vector<std::uint8_t>
shared_points(const std::vector<Clipper2Lib::Path64>& loops);

} // namespace splintercam::geometry2d

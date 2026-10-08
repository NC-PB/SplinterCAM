// SPDX-License-Identifier: Apache-2.0
// A loop's crossings with itself resolved into touching cycles (research 01, Loop tree, rule 4;
// REQ-G2D-238).
#pragma once

#include "exact.hpp"

#include <cstdint>
#include <span>
#include <vector>

namespace splintercam::geometry2d {

enum class SelfContact : std::int8_t {
    simple = 0,  // no two non-adjacent segments meet
    cycles = 1,  // resolved into cycles
    overlap = 2, // a stretch run twice, or two ends leaving a point in one direction
};

struct SelfCycles {
    SelfContact status = SelfContact::simple;
    std::vector<Point2> points;           // the cycles' vertices, cycle after cycle
    std::vector<std::int64_t> starts;     // the first vertex of each cycle
    std::vector<std::int64_t> first_edge; // per cycle the loop position it starts at (input order)
    std::vector<Point2> nodes;            // where the loop meets itself, sorted by x, then y
};

// The cycles of closed polyline `loop` ((x, y) pairs) after its self-contacts are resolved: at
// each point where it meets itself, each incoming end is joined to the first outgoing end after it
// counter-clockwise with as many incoming as outgoing ends between them (a Seifert resolution,
// decided by exact signs), so the cycles touch but do not cross.
[[nodiscard]] SelfCycles self_cycles(std::span<const double> loop);

} // namespace splintercam::geometry2d

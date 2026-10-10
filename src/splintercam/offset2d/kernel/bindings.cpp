// SPDX-License-Identifier: Apache-2.0
// Python bindings of the offset2d kernel (docs/dev/03: arrays and plain values only). Outputs are
// arrays the Python side allocates and passes in, so no kernel code owns Python memory.
#include "boolean.hpp"
#include "chain_side.hpp"
#include "grow.hpp"
#include "offset.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/array.h>
#include <nanobind/stl/tuple.h>
#include <span>
#include <tuple>

namespace nb = nanobind;

namespace splintercam::offset2d {
namespace {

using PointRows = nb::ndarray<const double, nb::shape<-1, 2>, nb::c_contig, nb::device::cpu>;
using PointsOut = nb::ndarray<double, nb::shape<-1, 2>, nb::c_contig, nb::device::cpu>;
using Counts = nb::ndarray<const std::int64_t, nb::shape<-1>, nb::c_contig, nb::device::cpu>;
using CountsOut = nb::ndarray<std::int64_t, nb::shape<-1>, nb::c_contig, nb::device::cpu>;
using FlagsOut = nb::ndarray<std::uint8_t, nb::shape<-1>, nb::c_contig, nb::device::cpu>;
using Triple = std::array<double, 3>;
using Quad = std::array<double, 4>;
using Classes = nb::ndarray<const std::int8_t, nb::shape<-1>, nb::c_contig, nb::device::cpu>;

template <typename Array> auto view(const Array& array) {
    return std::span{array.data(), array.size()};
}

bool finite(std::span<const double> values) {
    return std::ranges::all_of(values, [](double v) { return std::isfinite(v); });
}

// The arrays of flattened loops as offset2d's Python side builds them (REQ-OFF-013).
geometry2d::Polylines checked_loops(const PointRows& points, const Counts& starts,
                                    std::size_t id_count) {
    const std::span<const std::int64_t> s = view(starts);
    const auto n = static_cast<std::int64_t>(points.shape(0));
    const bool ascending = std::ranges::adjacent_find(s, std::ranges::greater_equal{}) == s.end();
    if (id_count != points.shape(0) || (s.empty() != (n == 0)) ||
        (!s.empty() && (s.front() != 0 || s.back() >= n)) || !ascending || !finite(view(points))) {
        throw nb::value_error("finite points, one ID each, loop_starts ascending from 0");
    }
    return {.points = view(points), .loop_starts = s};
}

template <typename T, typename Out> void copy_out(const std::vector<T>& from, const Out& to) {
    for (std::size_t i = 0; i < std::min(from.size(), to.shape(0)); ++i) {
        to(i) = from.at(i);
    }
}

using RegionOut = std::tuple<const PointsOut&, const CountsOut&, const CountsOut&, const FlagsOut&>;

// A region into the arrays the caller allocated, as far as they reach; (status, points, loops),
// the counts it needed.
std::tuple<int, std::size_t, std::size_t> write_region(const geometry2d::GridRegion& region,
                                                       RegionOut out) {
    const auto& [points_out, starts_out, ids_out, fixed_out] = out;
    for (std::size_t i = 0; i < std::min(region.points.size(), points_out.shape(0)); ++i) {
        points_out(i, 0) = std::get<0>(region.points.at(i));
        points_out(i, 1) = std::get<1>(region.points.at(i));
    }
    copy_out(region.starts, starts_out);
    copy_out(region.ids, ids_out);
    copy_out(region.fixed, fixed_out);
    return {static_cast<int>(region.status), region.points.size(), region.starts.size()};
}

// The input edges of the source IDs, with one class per vertex (REQ-OFF-013, 034).
IdSource id_source(const PointRows& points, const Counts& starts, const Counts& source_ids,
                   const Classes& classes) {
    if (classes.shape(0) != source_ids.shape(0)) {
        throw nb::value_error("one class per vertex");
    }
    return {.loops = checked_loops(points, starts, source_ids.shape(0)),
            .source_ids = view(source_ids),
            .classes = view(classes)};
}

void bind_clip(nb::module_& m) {
    m.def(
        "clip_regions",
        [](const PointRows& subject, const Counts& subject_starts, const PointRows& clip,
           const Counts& clip_starts, const PointRows& id_points, const Counts& id_starts,
           const Counts& source_ids, const Classes& classes, int op, const Quad& grid,
           const PointsOut& points_out, const CountsOut& starts_out, const CountsOut& ids_out,
           const FlagsOut& fixed_out) {
            const auto [u, span, eps, reach] = grid;
            if (op < 0 || op > 2 || !finite(grid) || !(u > 0.0) || !(span > 0.0) || !(eps >= 0.0) ||
                !(reach > 0.0)) {
                throw nb::value_error("op 0 to 2; u, span, reach > 0; eps >= 0");
            }
            const ClipInput input{.subject =
                                      checked_loops(subject, subject_starts, subject.shape(0)),
                                  .clip = checked_loops(clip, clip_starts, clip.shape(0)),
                                  .ids = id_source(id_points, id_starts, source_ids, classes)};
            geometry2d::GridRegion region;
            {
                const nb::gil_scoped_release unlocked;
                region =
                    clip_regions(input, static_cast<ClipOp>(op), {.u = u, .max_span_units = span},
                                 {.limit = reach, .eps = eps});
            }
            return write_region(region, std::tie(points_out, starts_out, ids_out, fixed_out));
        },
        nb::arg("subject"), nb::arg("subject_starts"), nb::arg("clip"), nb::arg("clip_starts"),
        nb::arg("id_points"), nb::arg("id_starts"), nb::arg("source_ids"), nb::arg("classes"),
        nb::arg("op"), nb::arg("grid"), nb::arg("points_out"), nb::arg("starts_out"),
        nb::arg("ids_out"), nb::arg("fixed_out"),
        "The union (0), difference (1) or intersection (2) of closed loops in one Clipper2 call "
        "(grid = u, the span limit, the tie window, the reach of the source IDs); return (status, "
        "points, loops), the counts it needed.");
}

void bind_grow(nb::module_& m) {
    m.def(
        "grow_chains",
        [](const PointRows& chains, const Counts& chain_starts, const PointRows& id_points,
           const Counts& id_starts, const Counts& source_ids, const Classes& classes,
           const Triple& offset, const Quad& grid, const PointsOut& points_out,
           const CountsOut& starts_out, const CountsOut& ids_out, const FlagsOut& fixed_out) {
            const auto [delta, arc_tol, reach] = offset;
            const auto [u, span, steps, eps] = grid;
            if (!finite(offset) || !finite(grid) || !(delta > arc_tol) || !(arc_tol > 0.0) ||
                !(reach > 0.0) || !(u > 0.0) || !(span > 0.0) || !(steps > 0.0) || !(eps >= 0.0)) {
                throw nb::value_error("delta > arc_tol > 0; reach, u, span, steps > 0; eps >= 0");
            }
            const GrowInput input{.chains = checked_loops(chains, chain_starts, chains.shape(0)),
                                  .ids = id_source(id_points, id_starts, source_ids, classes)};
            geometry2d::GridRegion region;
            {
                const nb::gil_scoped_release unlocked;
                region = grow_chains(
                    input, {.delta = delta, .arc_tol = arc_tol, .bias_units = 0, .margin_units = 0},
                    {.u = u, .max_span_units = span, .join_steps_max = steps, .eps_len = eps},
                    {.limit = reach, .eps = eps});
            }
            return write_region(region, std::tie(points_out, starts_out, ids_out, fixed_out));
        },
        nb::arg("chains"), nb::arg("chain_starts"), nb::arg("id_points"), nb::arg("id_starts"),
        nb::arg("source_ids"), nb::arg("classes"), nb::arg("offset"), nb::arg("grid"),
        nb::arg("points_out"), nb::arg("starts_out"), nb::arg("ids_out"), nb::arg("fixed_out"),
        "Grow open chains by delta with round joins and ends in one Clipper2 call (offset = delta, "
        "a, the reach of the source IDs in mm; grid = u, the span limit, the join step limit, "
        "eps_len); return (status, points, loops), the counts it needed.");
}

void bind_side(nb::module_& m) {
    m.def(
        "chain_side",
        [](const PointRows& chain, const PointRows& id_points, const Counts& id_starts,
           const Counts& source_ids, const Classes& classes, int tool_side, const Quad& offset,
           const Quad& grid, const PointsOut& points_out, const CountsOut& starts_out,
           const FlagsOut& closed_out, const CountsOut& ids_out, const FlagsOut& fixed_out) {
            const auto [delta, arc_tol, reach, bias] = offset;
            const auto [u, span, steps, eps] = grid;
            if ((tool_side != 1 && tool_side != -1) || chain.shape(0) < 2 || !finite(offset) ||
                !finite(grid) || !(delta > arc_tol) || !(arc_tol > 0.0) || !(reach > 0.0) ||
                !(u > 0.0) || !(span > 0.0) || !(steps > 0.0) || !(eps >= 0.0)) {
                throw nb::value_error(
                    "tool_side +1 or -1, two points or more, delta > arc_tol > 0; reach, u, span, "
                    "steps > 0; eps >= 0");
            }
            const std::array<std::int64_t, 1> one_chain{0};
            const GrowInput input{
                .chains = {.points = view(chain), .loop_starts = std::span{one_chain}},
                .ids = id_source(id_points, id_starts, source_ids, classes)};
            if (!finite(view(chain))) {
                throw nb::value_error("finite chain points");
            }
            SidePieces pieces;
            {
                const nb::gil_scoped_release unlocked;
                pieces = chain_side(
                    input, tool_side,
                    {.delta = delta, .arc_tol = arc_tol, .bias_units = bias, .margin_units = 0},
                    {.u = u, .max_span_units = span, .join_steps_max = steps, .eps_len = eps},
                    {.limit = reach, .eps = eps});
            }
            for (std::size_t i = 0; i < std::min(pieces.points.size(), points_out.shape(0)); ++i) {
                points_out(i, 0) = std::get<0>(pieces.points.at(i));
                points_out(i, 1) = std::get<1>(pieces.points.at(i));
            }
            copy_out(pieces.starts, starts_out);
            copy_out(pieces.closed, closed_out);
            copy_out(pieces.ids, ids_out);
            copy_out(pieces.fixed, fixed_out);
            return std::tuple{static_cast<int>(pieces.status), pieces.points.size(),
                              pieces.starts.size(), pieces.ids.size()};
        },
        nb::arg("chain"), nb::arg("id_points"), nb::arg("id_starts"), nb::arg("source_ids"),
        nb::arg("classes"), nb::arg("tool_side"), nb::arg("offset"), nb::arg("grid"),
        nb::arg("points_out"), nb::arg("starts_out"), nb::arg("closed_out"), nb::arg("ids_out"),
        nb::arg("fixed_out"),
        "The tool side of one open chain offset with Butt ends (tool_side +1 left, -1 right; "
        "offset = delta, a, the reach of the source IDs; grid = u, the span limit, the join step "
        "limit, eps_len); return (status, points, pieces, ids), the counts it needed.");
}

} // namespace

void bind(nb::module_& m) {
    m.def(
        "offset_loops",
        [](const PointRows& points, const Counts& loop_starts, const PointRows& id_points,
           const Counts& id_starts, const Counts& source_ids, const Classes& classes,
           const Quad& offset, const Quad& grid, const PointsOut& points_out,
           const CountsOut& starts_out, const CountsOut& ids_out, const FlagsOut& fixed_out) {
            const geometry2d::Polylines loops = checked_loops(points, loop_starts, points.shape(0));
            const IdSource ids = id_source(id_points, id_starts, source_ids, classes);
            const auto [delta, arc_tol, bias, margin] = offset;
            const auto [u, span, steps, eps] = grid;
            if (!finite(offset) || std::abs(delta) <= arc_tol || !(arc_tol > 0.0) || !(u > 0.0) ||
                !(span > 0.0) || !(steps > 0.0) || !(eps >= 0.0) || !finite(grid)) {
                throw nb::value_error("|delta| > arc_tol > 0; u, span, steps > 0; eps >= 0");
            }
            geometry2d::GridRegion region;
            {
                const nb::gil_scoped_release unlocked;
                region = offset_loops(
                    {.loops = loops, .ids = ids},
                    {.delta = delta,
                     .arc_tol = arc_tol,
                     .bias_units = bias,
                     .margin_units = margin},
                    {.u = u, .max_span_units = span, .join_steps_max = steps, .eps_len = eps});
            }
            return write_region(region, std::tie(points_out, starts_out, ids_out, fixed_out));
        },
        nb::arg("points"), nb::arg("loop_starts"), nb::arg("id_points"), nb::arg("id_starts"),
        nb::arg("source_ids"), nb::arg("classes"), nb::arg("offset"), nb::arg("grid"),
        nb::arg("points_out"), nb::arg("starts_out"), nb::arg("ids_out"), nb::arg("fixed_out"),
        "Offset flattened, normalised loops in one Clipper2 call (offset = delta, a in mm, the "
        "bias and the rounding margin in grid units; grid = u, the span limit, the join step "
        "limit, eps_len; classes per vertex as D-059 orders them); return (status, points, "
        "loops), the counts it needed.");
    bind_clip(m);
    bind_grow(m);
    bind_side(m);
}

} // namespace splintercam::offset2d

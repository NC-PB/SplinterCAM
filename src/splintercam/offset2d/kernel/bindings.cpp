// SPDX-License-Identifier: Apache-2.0
// Python bindings of the offset2d kernel (docs/dev/03: arrays and plain values only). Outputs are
// arrays the Python side allocates and passes in, so no kernel code owns Python memory.
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

} // namespace

void bind(nb::module_& m) {
    m.def(
        "offset_loops",
        [](const PointRows& points, const Counts& loop_starts, const PointRows& id_points,
           const Counts& id_starts, const Counts& source_ids, const Classes& classes,
           const Quad& offset, const Quad& grid, const PointsOut& points_out,
           const CountsOut& starts_out, const CountsOut& ids_out, const FlagsOut& fixed_out) {
            const geometry2d::Polylines loops = checked_loops(points, loop_starts, points.shape(0));
            const geometry2d::Polylines id_loops =
                checked_loops(id_points, id_starts, source_ids.shape(0));
            const auto [delta, arc_tol, bias, margin] = offset;
            const auto [u, span, steps, eps] = grid;
            if (!finite(offset) || std::abs(delta) <= arc_tol || !(arc_tol > 0.0) || !(u > 0.0) ||
                !(span > 0.0) || !(steps > 0.0) || !(eps >= 0.0) || !finite(grid) ||
                classes.shape(0) != source_ids.shape(0)) {
                throw nb::value_error(
                    "|delta| > arc_tol > 0; u, span, steps > 0; eps >= 0; one class per vertex");
            }
            geometry2d::GridRegion region;
            {
                const nb::gil_scoped_release unlocked;
                region = offset_loops(
                    {.loops = loops,
                     .id_loops = id_loops,
                     .source_ids = view(source_ids),
                     .classes = view(classes)},
                    {.delta = delta,
                     .arc_tol = arc_tol,
                     .bias_units = bias,
                     .margin_units = margin},
                    {.u = u, .max_span_units = span, .join_steps_max = steps, .eps_len = eps});
            }
            for (std::size_t i = 0; i < std::min(region.points.size(), points_out.shape(0)); ++i) {
                points_out(i, 0) = std::get<0>(region.points.at(i));
                points_out(i, 1) = std::get<1>(region.points.at(i));
            }
            copy_out(region.starts, starts_out);
            copy_out(region.ids, ids_out);
            copy_out(region.fixed, fixed_out);
            return std::tuple{static_cast<int>(region.status), region.points.size(),
                              region.starts.size()};
        },
        nb::arg("points"), nb::arg("loop_starts"), nb::arg("id_points"), nb::arg("id_starts"),
        nb::arg("source_ids"), nb::arg("classes"), nb::arg("offset"), nb::arg("grid"),
        nb::arg("points_out"), nb::arg("starts_out"), nb::arg("ids_out"), nb::arg("fixed_out"),
        "Offset flattened, normalised loops in one Clipper2 call (offset = delta, a in mm, the "
        "bias and the rounding margin in grid units; grid = u, the span limit, the join step "
        "limit, eps_len; classes per vertex as D-059 orders them); return (status, points, "
        "loops), the counts it needed.");
}

} // namespace splintercam::offset2d

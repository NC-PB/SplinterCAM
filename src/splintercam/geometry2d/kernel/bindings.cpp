// SPDX-License-Identifier: Apache-2.0
// Python bindings of the geometry2d kernel (docs/dev/03: arrays and plain values only). Outputs are
// arrays the Python side allocates and passes in, so no kernel code owns Python memory.
#include "angle.hpp"
#include "arcs.hpp"
#include "flatten.hpp"

#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <span>

namespace nb = nanobind;

namespace splintercam::geometry2d {
namespace {

using Rows = nb::ndarray<const double, nb::shape<-1, row_width>, nb::c_contig, nb::device::cpu>;
using Values = nb::ndarray<const double, nb::shape<-1>, nb::c_contig, nb::device::cpu>;
using DoubleOut = nb::ndarray<double, nb::shape<-1>, nb::c_contig, nb::device::cpu>;
using PointsOut = nb::ndarray<double, nb::shape<-1, 2>, nb::c_contig, nb::device::cpu>;
using Int8Out = nb::ndarray<std::int8_t, nb::shape<-1>, nb::c_contig, nb::device::cpu>;

std::span<const double> view(const Rows& rows) {
    return {rows.data(), rows.size()};
}

std::span<std::int8_t> view(const Int8Out& out) {
    return {out.data(), out.size()};
}

} // namespace

void bind(nb::module_& m) {
    m.def(
        "check_arcs",
        [](const Rows& rows, double length_eps_mm, const Int8Out& out) {
            if (out.shape(0) != rows.shape(0)) {
                throw nb::value_error("out needs one element per row");
            }
            check_arcs(view(rows), length_eps_mm, view(out));
        },
        nb::arg("rows"), nb::arg("length_eps_mm"), nb::arg("out"),
        "Write per curve row 0 (consistent), 1 (P1 off the circle) or 2 (sweep does not fit).");
    m.def(
        "basic_atan2",
        [](const Values& y, const Values& x, const DoubleOut& out) {
            if (x.shape(0) != y.shape(0) || out.shape(0) != y.shape(0)) {
                throw nb::value_error("y, x and out need the same length");
            }
            for (std::size_t i = 0; i < out.shape(0); ++i) {
                out(i) = basic_atan2(y(i), x(i));
            }
        },
        nb::arg("y"), nb::arg("x"), nb::arg("out"),
        "The arctangent the kernel decides with, for tests (REQ-G2D-018).");
    m.def(
        "arc_steps",
        [](const Rows& arc, double t_mm, bool inscribed, double max_step_rad) {
            if (arc.shape(0) != 1) {
                throw nb::value_error("one arc row");
            }
            return arc_steps(unpack_row(view(arc)), t_mm, inscribed, max_step_rad);
        },
        nb::arg("arc"), nb::arg("t_mm"), nb::arg("inscribed"), nb::arg("max_step_rad"),
        "The number of steps of the arc flattened within t (research 01, Flattening).");
    m.def(
        "flatten_arc",
        [](const Rows& arc, int steps, bool inscribed, const PointsOut& out) {
            const auto points = static_cast<std::size_t>(steps) + (inscribed ? 1 : 2);
            if (arc.shape(0) != 1 || steps < 1 || out.shape(0) != points) {
                throw nb::value_error("one arc row, steps >= 1, and steps + 1 (+ 2) points");
            }
            flatten_arc(unpack_row(view(arc)), steps, inscribed, {out.data(), out.size()});
        },
        nb::arg("arc"), nb::arg("steps"), nb::arg("inscribed"), nb::arg("out"),
        "Write the arc flattened in `steps` steps, inscribed or circumscribed.");
}

} // namespace splintercam::geometry2d

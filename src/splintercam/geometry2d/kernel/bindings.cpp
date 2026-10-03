// SPDX-License-Identifier: Apache-2.0
// Python bindings of the geometry2d kernel (docs/dev/03: arrays and plain values only). Outputs are
// arrays the Python side allocates and passes in, so no kernel code owns Python memory.
#include "angle.hpp"
#include "arcs.hpp"
#include "exact.hpp"
#include "flatten.hpp"

#include <initializer_list>
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
using PointRows = nb::ndarray<const double, nb::shape<-1, 2>, nb::c_contig, nb::device::cpu>;
using Int8Out = nb::ndarray<std::int8_t, nb::shape<-1>, nb::c_contig, nb::device::cpu>;

std::span<const double> view(const Rows& rows) {
    return {rows.data(), rows.size()};
}

std::span<std::int8_t> view(const Int8Out& out) {
    return {out.data(), out.size()};
}

void check_rows(std::size_t rows, std::initializer_list<std::size_t> others) {
    for (const std::size_t other : others) {
        if (other != rows) {
            throw nb::value_error("every array needs the same number of rows");
        }
    }
}

Points points(const PointRows& rows) {
    return {rows.data(), rows.size()};
}

void bind_exact(nb::module_& m) {
    m.def(
        "two_sums",
        [](const Values& a, const Values& b, const DoubleOut& x, const DoubleOut& y) {
            check_rows(a.shape(0), {b.shape(0), x.shape(0), y.shape(0)});
            two_sums({.a = {a.data(), a.size()}, .b = {b.data(), b.size()}},
                     {.x = {x.data(), x.size()}, .y = {y.data(), y.size()}});
        },
        nb::arg("a"), nb::arg("b"), nb::arg("x"), nb::arg("y"),
        "Write x + y = a + b exactly (REQ-G2D-016).");
    m.def(
        "two_products",
        [](const Values& a, const Values& b, const DoubleOut& x, const DoubleOut& y) {
            check_rows(a.shape(0), {b.shape(0), x.shape(0), y.shape(0)});
            two_products({.a = {a.data(), a.size()}, .b = {b.data(), b.size()}},
                         {.x = {x.data(), x.size()}, .y = {y.data(), y.size()}});
        },
        nb::arg("a"), nb::arg("b"), nb::arg("x"), nb::arg("y"),
        "Write x + y = a * b exactly (REQ-G2D-016).");
    m.def(
        "orient2d_signs",
        [](const PointRows& a, const PointRows& b, const PointRows& c, const Int8Out& out) {
            check_rows(a.shape(0), {b.shape(0), c.shape(0), out.shape(0)});
            orient2d_signs({points(a), points(b), points(c)}, view(out));
        },
        nb::arg("a"), nb::arg("b"), nb::arg("c"), nb::arg("out"),
        "Write the exact sign of orient2d per row (REQ-G2D-007).");
    m.def(
        "incircle_signs",
        [](const PointRows& a, const PointRows& b, const PointRows& c, const PointRows& d,
           const Int8Out& out) {
            check_rows(a.shape(0), {b.shape(0), c.shape(0), d.shape(0), out.shape(0)});
            incircle_signs({points(a), points(b), points(c), points(d)}, view(out));
        },
        nb::arg("a"), nb::arg("b"), nb::arg("c"), nb::arg("d"), nb::arg("out"),
        "Write the exact sign of incircle per row (REQ-G2D-011).");
    m.def(
        "in_arc_circle_signs",
        [](const PointRows& q, const PointRows& centre, const PointRows& p0, const Int8Out& out) {
            check_rows(q.shape(0), {centre.shape(0), p0.shape(0), out.shape(0)});
            in_arc_circle_signs({.q = points(q), .centre = points(centre), .p0 = points(p0)},
                                view(out));
        },
        nb::arg("q"), nb::arg("centre"), nb::arg("p0"), nb::arg("out"),
        "Write the exact sign of |p0 - c|^2 - |q - c|^2 per row (REQ-G2D-022).");
    m.def(
        "vertical_extent_signs",
        [](const Values& q_y, const PointRows& centre, const PointRows& p0, const Int8Out& out) {
            check_rows(q_y.shape(0), {centre.shape(0), p0.shape(0), out.shape(0)});
            vertical_extent_signs(
                {.q_y = {q_y.data(), q_y.size()}, .centre = points(centre), .p0 = points(p0)},
                view(out));
        },
        nb::arg("q_y"), nb::arg("centre"), nb::arg("p0"), nb::arg("out"),
        "Write the exact sign of (q_y - c_y)^2 - |p0 - c|^2 per row (REQ-G2D-023).");
    m.def(
        "circles_through",
        [](const PointRows& p1, const PointRows& p2, const PointRows& p3, double length_eps_mm,
           const PointsOut& centres, const DoubleOut& radii, const Int8Out& found) {
            check_rows(p1.shape(0), {p2.shape(0), p3.shape(0), centres.shape(0), radii.shape(0),
                                     found.shape(0)});
            circles_through({points(p1), points(p2), points(p3)}, length_eps_mm,
                            {.centres = {centres.data(), centres.size()},
                             .radii = {radii.data(), radii.size()},
                             .found = view(found)});
        },
        nb::arg("p1"), nb::arg("p2"), nb::arg("p3"), nb::arg("length_eps_mm"), nb::arg("centres"),
        nb::arg("radii"), nb::arg("found"),
        "Write per row the circle through p1, p2, p3, or found = 0 (REQ-G2D-097 to 101).");
}

} // namespace

void bind(nb::module_& m) {
    init_exact_arithmetic(); // once, when the module loads (REQ-G2D-013)
    bind_exact(m);
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

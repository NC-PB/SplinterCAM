// SPDX-License-Identifier: Apache-2.0
// Python bindings of the geometry2d kernel (docs/dev/03: arrays and plain values only). Outputs are
// arrays the Python side allocates and passes in, so no kernel code owns Python memory.
#include "angle.hpp"
#include "arcs.hpp"
#include "area.hpp"
#include "cleanup.hpp"
#include "distance.hpp"
#include "exact.hpp"
#include "flatten.hpp"
#include "grid.hpp"
#include "region.hpp"
#include "selfcross.hpp"

#include <algorithm>
#include <cmath>
#include <initializer_list>
#include <limits>
#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/array.h>
#include <nanobind/stl/pair.h>
#include <nanobind/stl/tuple.h>
#include <numbers>
#include <span>
#include <utility>

namespace nb = nanobind;

namespace splintercam::geometry2d {
namespace {

using Rows = nb::ndarray<const double, nb::shape<-1, row_width>, nb::c_contig, nb::device::cpu>;
using Values = nb::ndarray<const double, nb::shape<-1>, nb::c_contig, nb::device::cpu>;
using DoubleOut = nb::ndarray<double, nb::shape<-1>, nb::c_contig, nb::device::cpu>;
using PointsOut = nb::ndarray<double, nb::shape<-1, 2>, nb::c_contig, nb::device::cpu>;
using PointRows = nb::ndarray<const double, nb::shape<-1, 2>, nb::c_contig, nb::device::cpu>;
using Int8Out = nb::ndarray<std::int8_t, nb::shape<-1>, nb::c_contig, nb::device::cpu>;
using Flags = nb::ndarray<const std::uint8_t, nb::shape<-1>, nb::c_contig, nb::device::cpu>;
using Counts = nb::ndarray<const std::int64_t, nb::shape<-1>, nb::c_contig, nb::device::cpu>;
using CountsOut = nb::ndarray<std::int64_t, nb::shape<-1>, nb::c_contig, nb::device::cpu>;
using CyclesOut = nb::ndarray<std::int64_t, nb::shape<-1, 2>, nb::c_contig, nb::device::cpu>;
using Pair = std::array<double, 2>;

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

void bind_area(nb::module_& m) {
    m.def(
        "loop_area",
        [](const Rows& rows, double centre_x, double centre_y, bool exact) {
            const LoopSums sums =
                loop_area(view(rows), {.centre_x = centre_x, .centre_y = centre_y, .exact = exact});
            return std::pair{sums.area, sums.length};
        },
        nb::arg("rows"), nb::arg("centre_x"), nb::arg("centre_y"), nb::arg("exact"),
        "Return the signed area and the length of one loop of curve rows (REQ-G2D-128 to 132).");
    m.def(
        "phi_minus_sin",
        [](const Values& phi, const DoubleOut& out) {
            check_rows(phi.shape(0), {out.shape(0)});
            std::ranges::transform(std::span(phi.data(), phi.size()), out.data(), phi_minus_sin);
        },
        nb::arg("phi"), nb::arg("out"),
        "Write phi - sin(phi) per value, from basic operations only (REQ-G2D-018).");
    m.def(
        "ray_height_sign",
        [](double q_y, const Pair& centre, const Pair& p0, const Pair& toward) {
            return ray_height_sign(q_y, {centre, p0}, toward);
        },
        "Sign of q_y minus where the ray centre -> toward meets the circle through p0 (exact).");
    m.def(
        "point_locations",
        [](const PointRows& q, const Rows& rows, double length_eps_mm, const Int8Out& out) {
            check_rows(q.shape(0), {out.shape(0)});
            point_locations({q.data(), q.size()},
                            {.rows = view(rows), .length_eps_mm = length_eps_mm}, view(out));
        },
        nb::arg("q"), nb::arg("rows"), nb::arg("length_eps_mm"), nb::arg("out"),
        "Write per point 0 (OUT), 1 (IN) or 2 (ON) against the loops' rows (REQ-G2D-134 to 150).");
    m.def(
        "cleanup_loop",
        [](const PointRows& points, double length_eps_mm, const Int8Out& status) {
            check_rows(points.shape(0), {status.shape(0)});
            cleanup_loop({points.data(), points.size()}, length_eps_mm, view(status));
        },
        nb::arg("points"), nb::arg("length_eps_mm"), nb::arg("status"),
        "Mark per vertex whether cleanup keeps it and where it dropped a spike (REQ-G2D-204 to "
        "212).");
}

// The counts row_vertex_counts can give a row: a line 1, an inscribed arc 1 to INT_MAX, a
// circumscribed arc 2 to INT_MAX + 1.
std::pair<std::int64_t, std::int64_t> count_range(const CurveRow& row, bool inscribed) {
    constexpr std::int64_t max_steps = std::numeric_limits<int>::max();
    if (row.sweep == 0.0) {
        return {1, 1};
    }
    return inscribed ? std::pair<std::int64_t, std::int64_t>{1, max_steps}
                     : std::pair<std::int64_t, std::int64_t>{2, max_steps + 1};
}

// Every count is one that row_vertex_counts can give, and they add up to exactly `points`, so
// flatten_rows writes inside `out` whatever the caller passes.
void check_counts(std::span<const double> rows, std::span<const std::uint8_t> inscribed,
                  std::span<const std::int64_t> counts, std::size_t points) {
    std::size_t total = 0;
    for (std::size_t i = 0; i < counts.size(); ++i) {
        const CurveRow row = unpack_row(rows.subspan(i * row_width, row_width));
        const std::int64_t count = counts.subspan(i, 1).front();
        if (!(std::abs(row.sweep) <= 2 * std::numbers::pi)) {
            throw nb::value_error("an arc row's sweep must lie within ±2π");
        }
        const auto [low, high] = count_range(row, inscribed.subspan(i, 1).front() != 0);
        if (count < low || count > high) {
            throw nb::value_error("a count that row_vertex_counts cannot give");
        }
        total += static_cast<std::size_t>(count); // at most 2^31 per row: no overflow
    }
    if (total != points) {
        throw nb::value_error("out needs one point per counted vertex");
    }
}

void bind_flatten_rows(nb::module_& m) {
    m.def(
        "row_vertex_counts",
        [](const Rows& rows, const Flags& inscribed, double t_mm, double max_step_rad,
           const CountsOut& out) {
            check_rows(rows.shape(0), {inscribed.shape(0), out.shape(0)});
            row_vertex_counts(view(rows), {inscribed.data(), inscribed.size()},
                              {.t_mm = t_mm, .max_step_rad = max_step_rad},
                              {out.data(), out.size()});
        },
        nb::arg("rows"), nb::arg("inscribed"), nb::arg("t_mm"), nb::arg("max_step_rad"),
        nb::arg("out"),
        "Write per row the vertices it adds to its flattened loop, -1 beyond an int "
        "(REQ-G2D-199).");
    m.def(
        "flatten_rows",
        [](const Rows& rows, const Flags& inscribed, const Counts& counts, bool portable,
           const PointsOut& out) {
            check_rows(rows.shape(0), {inscribed.shape(0), counts.shape(0)});
            const std::span<const std::int64_t> per_row{counts.data(), counts.size()};
            check_counts(view(rows), {inscribed.data(), inscribed.size()}, per_row, out.shape(0));
            flatten_rows(view(rows), {inscribed.data(), inscribed.size()}, per_row, portable,
                         {out.data(), out.size()});
        },
        nb::arg("rows"), nb::arg("inscribed"), nb::arg("counts"), nb::arg("portable"),
        nb::arg("out"),
        "Write the loops' rows flattened one after another, each joint once (REQ-G2D-199).");
}

void check_polylines(std::span<const std::int64_t> starts, std::span<const double> vertices) {
    const auto count = static_cast<std::int64_t>(vertices.size() / 2);
    std::int64_t previous = -1;
    for (const std::int64_t start : starts) {
        if (start <= previous || start >= count) {
            throw nb::value_error("loop_starts must ascend strictly below the point count");
        }
        previous = start;
    }
    if (!starts.empty() && starts.front() != 0) {
        throw nb::value_error("loop_starts must start at 0");
    }
    if (starts.empty() && !vertices.empty()) {
        throw nb::value_error("loop_starts must name the loops of the points");
    }
    if (!std::ranges::all_of(vertices, [](double v) { return std::isfinite(v); })) {
        throw nb::value_error("every polyline vertex must be finite");
    }
}

// Checked closed polylines: `rows` split at `loop_starts`.
Polylines loops_of(const PointRows& rows, std::span<const std::int64_t> starts) {
    check_polylines(starts, {rows.data(), rows.size()});
    return {.points = points(rows), .loop_starts = starts};
}

Polylines loops_of(const PointRows& rows, const Counts& loop_starts) {
    return loops_of(rows, {loop_starts.data(), loop_starts.size()});
}

constexpr std::array<std::int64_t, 1> first_row{0};

// One checked closed polyline (none when `rows` is empty).
Polylines one_loop(const PointRows& rows) {
    return loops_of(rows, rows.shape(0) == 0 ? std::span<const std::int64_t>{}
                                             : std::span<const std::int64_t>{first_row});
}

std::pair<Polylines, Polylines> two_loops(const PointRows& a, const PointRows& b) {
    return {one_loop(a), one_loop(b)};
}

void check_limit(double limit) {
    if (!(limit > 0.0) || !std::isfinite(limit)) {
        throw nb::value_error("limit must be finite and > 0");
    }
}

// Each output array is filled as far as it reaches; the caller retries with the counts.
void copy_points(const std::vector<Point2>& from, const PointsOut& to) {
    for (std::size_t i = 0; i < std::min(from.size(), to.shape(0)); ++i) {
        to(i, 0) = std::get<0>(from.at(i));
        to(i, 1) = std::get<1>(from.at(i));
    }
}

template <typename T, typename Out> void copy_values(const std::vector<T>& from, const Out& to) {
    for (std::size_t i = 0; i < std::min(from.size(), to.shape(0)); ++i) {
        to(i) = from.at(i);
    }
}

void bind_distances(nb::module_& m) {
    m.def(
        "polyline_distances",
        [](const PointRows& q, const PointRows& vertices, const Counts& loop_starts, double limit,
           const DoubleOut& out) {
            check_rows(q.shape(0), {out.shape(0)});
            check_limit(limit);
            const auto [queries, lines] =
                std::pair{std::span{q.data(), q.size()}, loops_of(vertices, loop_starts)};
            const nb::gil_scoped_release unlocked; // a long loop over plain arrays
            polyline_distances(queries, lines, limit, {out.data(), out.size()});
        },
        nb::arg("q"), nb::arg("points"), nb::arg("loop_starts"), nb::arg("limit"), nb::arg("out"),
        "Write per point its distance to the closed polylines where at most limit, else inf.");
    m.def(
        "basic_sin_cos",
        [](const Values& angles, const DoubleOut& sines, const DoubleOut& cosines) {
            check_rows(angles.shape(0), {sines.shape(0), cosines.shape(0)});
            constexpr double max_angle = 4 * std::numbers::pi;
            for (std::size_t i = 0; i < angles.shape(0); ++i) {
                if (!(std::abs(angles(i)) <= max_angle)) { // also NaN
                    throw nb::value_error("every angle must lie within ±4π");
                }
                const SinCos turn = basic_sin_cos(angles(i));
                sines(i) = turn.sin;
                cosines(i) = turn.cos;
            }
        },
        nb::arg("angles"), nb::arg("sines"), nb::arg("cosines"),
        "The sine and cosine the topology flattening turns with, for tests (REQ-G2D-152).");
}

void bind_pairs(nb::module_& m) {
    m.def(
        "crossing_depth",
        [](const PointRows& a, const PointRows& b, double limit) {
            check_limit(limit);
            const auto [mine, theirs] = two_loops(a, b);
            const nb::gil_scoped_release unlocked;
            const Depth depth = crossing_depth(mine, theirs, limit);
            return std::pair{depth.inside, depth.outside};
        },
        nb::arg("a"), nb::arg("b"), nb::arg("limit"),
        "Whether closed polyline a reaches farther than limit inside and outside closed polyline "
        "b.");
    m.def(
        "covered_by",
        [](const PointRows& a, const PointRows& b, const Counts& b_starts, double limit) {
            check_limit(limit);
            const auto [mine, others] = std::pair{one_loop(a), loops_of(b, b_starts)};
            const nb::gil_scoped_release unlocked;
            return covered_by(mine, others, limit);
        },
        nb::arg("a"), nb::arg("b"), nb::arg("b_starts"), nb::arg("limit"),
        "Whether every point of closed polyline a lies within limit of the closed polylines b.");
    m.def(
        "contact_points",
        [](const PointRows& a, const PointRows& b, double limit, const PointsOut& out) {
            check_limit(limit);
            const auto [mine, theirs] = two_loops(a, b);
            std::vector<Point2> found;
            {
                const nb::gil_scoped_release unlocked;
                found = contact_points(mine, theirs, limit);
            }
            copy_points(found, out);
            return found.size();
        },
        nb::arg("a"), nb::arg("b"), nb::arg("limit"), nb::arg("out"),
        "Write where closed polylines a and b meet, sorted; return their count (out may be "
        "short).");
}

using Ids = nb::ndarray<const std::int64_t, nb::shape<-1>, nb::c_contig, nb::device::cpu>;
using FlagsOut = nb::ndarray<std::uint8_t, nb::shape<-1>, nb::c_contig, nb::device::cpu>;

void bind_grid(nb::module_& m) {
    m.def(
        "grid_difference",
        [](const PointRows& b, const PointRows& a, double u, double max_span_units) {
            check_limit(u);
            const auto [subject, clip] = two_loops(b, a);
            const nb::gil_scoped_release unlocked;
            const GridAreas areas =
                grid_difference(subject, clip, {.u = u, .max_span_units = max_span_units});
            return std::tuple{static_cast<int>(areas.status), areas.difference_mm2, areas.b_mm2};
        },
        nb::arg("b"), nb::arg("a"), nb::arg("u"), nb::arg("max_span_units"),
        "Return (status, area of b minus a, area of b) in mm² from Clipper2's NonZero difference "
        "on the grid (REQ-G2D-169).");
    m.def(
        "grid_region",
        [](const PointRows& vertices, const Counts& loop_starts, const Ids& source_ids,
           int fill_rule, const std::array<double, 3>& grid, const PointsOut& points_out,
           const CountsOut& starts_out, const CountsOut& ids_out, const FlagsOut& fixed_out) {
            const auto [loops, ids] = std::pair{loops_of(vertices, loop_starts),
                                                std::span{source_ids.data(), source_ids.size()}};
            check_rows(vertices.shape(0), {ids.size()});
            check_limit(std::get<0>(grid));
            check_limit(std::get<1>(grid)); // a NaN span would refuse nothing
            check_limit(std::get<2>(grid));
            if (fill_rule < 0 || fill_rule > 2) {
                throw nb::value_error("fill_rule must be 0 (EvenOdd), 1 (NonZero) or 2 (Positive)");
            }
            GridRegion region;
            {
                const nb::gil_scoped_release unlocked;
                region = grid_region({.loops = loops,
                                      .source_ids = ids,
                                      .fill_rule = fill_rule,
                                      .id_reach = std::get<2>(grid)},
                                     {.u = std::get<0>(grid), .max_span_units = std::get<1>(grid)});
            }
            copy_points(region.points, points_out);
            copy_values(region.starts, starts_out);
            copy_values(region.ids, ids_out);
            copy_values(region.fixed, fixed_out);
            return std::tuple{static_cast<int>(region.status), region.points.size(),
                              region.starts.size()};
        },
        nb::arg("points"), nb::arg("loop_starts"), nb::arg("source_ids"), nb::arg("fill_rule"),
        nb::arg("grid"), nb::arg("points_out"), nb::arg("starts_out"), nb::arg("ids_out"),
        nb::arg("fixed_out"),
        "The region of flattened loops through Clipper2's grid (grid = u, the span limit in grid "
        "units, the reach of the source IDs); return (status, points, loops).");
}

void bind_self_cycles(nb::module_& m) {
    m.def(
        "self_cycles",
        [](const PointRows& loop, const PointsOut& points_out, const CyclesOut& cycles_out,
           const PointsOut& nodes_out) {
            const Polylines checked = one_loop(loop);
            SelfCycles cycles;
            {
                const nb::gil_scoped_release unlocked;
                cycles = self_cycles(checked.points);
            }
            copy_points(cycles.points, points_out);
            copy_points(cycles.nodes, nodes_out);
            for (std::size_t i = 0; i < std::min(cycles.starts.size(), cycles_out.shape(0)); ++i) {
                cycles_out(i, 0) = cycles.starts.at(i);
                cycles_out(i, 1) = cycles.first_edge.at(i);
            }
            return std::tuple{static_cast<int>(cycles.status), cycles.points.size(),
                              cycles.starts.size(), cycles.nodes.size()};
        },
        nb::arg("loop"), nb::arg("points"), nb::arg("cycles"), nb::arg("nodes"),
        "Resolve a closed polyline's self-contacts into cycles (per cycle its first point and loop "
        "position); return (status, points, cycles, nodes), the counts it needed.");
}

} // namespace

void bind(nb::module_& m) {
    init_exact_arithmetic(); // once, when the module loads (REQ-G2D-013)
    bind_exact(m);
    bind_area(m);
    m.def(
        "check_arcs",
        [](const Rows& rows, double length_eps_mm, const Int8Out& out) {
            check_rows(rows.shape(0), {out.shape(0)});
            check_arcs(view(rows), length_eps_mm, view(out));
        },
        nb::arg("rows"), nb::arg("length_eps_mm"), nb::arg("out"),
        "Write per curve row 0 (consistent), 1 (P1 off the circle) or 2 (sweep does not fit).");
    m.def(
        "basic_atan2",
        [](const Values& y, const Values& x, const DoubleOut& out) {
            check_rows(y.shape(0), {x.shape(0), out.shape(0)});
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
    bind_flatten_rows(m);
    bind_distances(m);
    bind_pairs(m);
    bind_self_cycles(m);
    bind_grid(m);
}

} // namespace splintercam::geometry2d

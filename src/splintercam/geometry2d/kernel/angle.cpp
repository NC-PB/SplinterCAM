// SPDX-License-Identifier: Apache-2.0
// Arctangent by argument reduction and the Taylor series (ours, 2026-10-02): atan x = π/2 −
// atan(1/x) for x > 1, and the addition formula atan x = π/6 + atan((√3·x − 1)/(√3 + x)) for x
// above tan(π/12) = 2 − √3, leave |t| <= 2 − √3 < 0.268, where 14 terms of t − t³/3 + t⁵/5 − …
// leave an truncation error below 0.268^29 / 29 < 1e-18; the rounding of the reductions and of the
// constants π/2, π/6 and π adds a few rounding units (the tests allow 4). Every step is a correctly
// rounded IEEE operation, compiled without contraction (CMakeLists.txt), so the result is the same
// everywhere. Why not std::atan2 or NumPy: DEC-G2D-003 and DEC-G2D-011 in ../DECISIONS.md.
#include "angle.hpp"

#include <cmath>
#include <numbers>

namespace splintercam::geometry2d {
namespace {

constexpr int series_terms = 14;
constexpr double half_pi = std::numbers::pi / 2;
constexpr double sixth_pi = std::numbers::pi / 6;

double atan_small(double t) {
    const double t2 = t * t;
    double sum = 1.0 / static_cast<double>(2 * series_terms - 1);
    for (int k = series_terms - 2; k >= 0; --k) {
        sum = 1.0 / static_cast<double>(2 * k + 1) - t2 * sum;
    }
    return t * sum;
}

double atan_nonnegative(double x) {
    const double sqrt3 = std::sqrt(3.0);
    const double tan_pi_12 = 2 - sqrt3;
    if (x > 1.0) {
        return half_pi - atan_nonnegative(1.0 / x);
    }
    if (x > tan_pi_12) {
        return sixth_pi + atan_small((sqrt3 * x - 1.0) / (sqrt3 + x));
    }
    return atan_small(x);
}

double basic_atan(double x) {
    return x < 0.0 ? -atan_nonnegative(-x) : atan_nonnegative(x);
}

} // namespace

double basic_atan2(double y, double x) {
    if (x > 0.0) {
        return basic_atan(y / x);
    }
    if (x < 0.0) {
        const double angle = basic_atan(y / x);
        return y < 0.0 ? angle - std::numbers::pi : angle + std::numbers::pi;
    }
    if (y == 0.0) {
        return 0.0;
    }
    return y > 0.0 ? half_pi : -half_pi;
}

// Taylor series (ours, 2026-10-03), summed until a term no longer changes the sum: for |φ| <= 1 the
// series of φ − sin φ itself, φ³/3! − φ⁵/5! + …, which has no cancellation; beyond, sin of φ
// reduced to [−π, π] by a rounded 2π, whose rounding moves the result by a few units of 2π.
double phi_minus_sin(double phi) {
    if (std::abs(phi) <= 1.0) {
        double term = phi * phi * phi / (2 * 3); // φ³/3!
        double sum = 0.0;
        for (int k = 1; sum + term != sum; ++k) {
            sum += term;
            term = -term * phi * phi / ((2 * k + 2) * (2 * k + 3));
        }
        return sum;
    }
    constexpr double two_pi = 2 * std::numbers::pi;
    double x = phi;
    if (x > std::numbers::pi) {
        x -= two_pi;
    } else if (x < -std::numbers::pi) {
        x += two_pi;
    }
    double term = x;
    double sine = 0.0;
    for (int k = 0; sine + term != sine; ++k) {
        sine += term;
        term = -term * x * x / ((2 * k + 2) * (2 * k + 3));
    }
    return phi - sine;
}

} // namespace splintercam::geometry2d

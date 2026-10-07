// SPDX-License-Identifier: Apache-2.0
// An arctangent from IEEE 754 basic operations only, so every decision and count that needs an
// angle is the same on every platform (D-055, tier 1; geometry2d SPEC, determinism note). The
// platform's libm atan2 is not correctly rounded and differs between platforms in the last bit.
#pragma once

namespace splintercam::geometry2d {

// The angle of (x, y) in (−π, π], within a few rounding units of the true value; atan2(0, 0) = 0.
[[nodiscard]] double basic_atan2(double y, double x);

// φ − sin φ for |φ| <= 2π, the circular segment term of the signed area (research 01, Area and
// orientation), within a few rounding units, from basic operations only like basic_atan2.
[[nodiscard]] double phi_minus_sin(double phi);

struct SinCos {
    double sin;
    double cos;
};

// sin and cos of an angle with |angle| <= 4π, within a few rounding units of 1, from basic
// operations only like basic_atan2: the topology flattening's vertices are the same everywhere
// (REQ-G2D-152). sin(±0) = ±0, cos(0) = 1.
[[nodiscard]] SinCos basic_sin_cos(double angle);

} // namespace splintercam::geometry2d

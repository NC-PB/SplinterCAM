// SPDX-License-Identifier: Apache-2.0
// An arctangent from IEEE 754 basic operations only, so every decision and count that needs an
// angle is the same on every platform (D-055, tier 1; geometry2d SPEC, determinism note). The
// platform's libm atan2 is not correctly rounded and differs between platforms in the last bit.
#pragma once

namespace splintercam::geometry2d {

// The angle of (x, y) in (−π, π], within a few rounding units of the true value; atan2(0, 0) = 0.
[[nodiscard]] double basic_atan2(double y, double x);

} // namespace splintercam::geometry2d

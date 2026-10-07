# AGENTS.md: geometry2d

Layer 1. Implements docs/research/01 (slices 1 and 2; the rest is under "Later parts" in the SPEC). Contract: `./SPEC.md`. Why it is built this way: `./DECISIONS.md` (read it before changing behaviour). Public API: `./__init__.py`. C++ part: `./kernel/`. Depends on: foundation. Slice 1 is complete and reviewed: `docs/plans/completed/0003-geometry2d-slice-1.md` (Handover). Slice 2: `docs/plans/active/0004-geometry2d-slice-2.md` (approved; its SPEC cut is step 1).

## Commands

- `tools/test-one geometry2d`

## Invariants that must never break

- REQ-G2D-005: every sign decision comes from an exact predicate or an exact comparison of doubles, never from the sign of a rounded expression.
- REQ-G2D-018: decisions and counts are the same on every platform: angles in decisions come from `kernel/angle.cpp`, never from libm or NumPy ufuncs.
- REQ-G2D-038, 039: an arc's radius is |P0 − C|; P1 is never moved, except by the nearly closed rule.
- REQ-G2D-025: eps_len and eps_ang come from `ctx.tolerances`; no tolerance is a literal.

## Local rules

- `kernel/vendor/predicates.c` is third-party and stays unchanged (ADR 0009): build quirks go into `kernel/shewchuk.c` and `CMakeLists.txt`.
- Only this module's Python code calls `splintercam._kernels.geometry2d`. Kernel outputs are arrays the Python side allocates and passes in.
- Loops cross module boundaries as curve rows; single curves as `Line` and `Arc`.
- Transcendental functions for constructions run in C++ with the platform's libm, never in NumPy, whose float64 ufuncs may pick SIMD code by CPU (D-055, tier 2).
- Tolerance share: none; `flatten` takes its t from the caller (SPEC, Tolerance budget).
- Decisions that need an angle or φ − sin φ use `angle.cpp` (`basic_atan2`, `phi_minus_sin`); tolerance tests on lengths use sqrt of a sum of squares, never `hypot` (libm).
- Buffers handed to `predicates.c` have two spare elements: it reads past an expansion's end, `e[0]` and `e[1]` when it is empty. ASan is off for that code (Peter, 2026-10-03), so nothing else catches a short buffer.
- The sweep test exists four times: `_box.py` (octants), `_distances.py` (halves), `region.cpp` (octant splits and `in_sweep`). Change them together; the plan's backlog proposes one shared kernel.
- Tests reach internals only where the SPEC names them: `point_in_region_exact`, the kernel bindings `two_sums`, `two_products`, `basic_atan2`, `phi_minus_sin`, `ray_height_sign`, `basic_sin_cos`; `topology_flattening`, `polyline_distances` and `screen_loops` (slice 2). Test oracles (exact rationals) live in `tests/support/geometry2d_oracles.py`, loop builders in `geometry2d_checks.py`; import them as top-level modules.

## Known pitfalls

- A flattened arc lies inside the true arc; on convex walls that is a gouge (research 01, trap 3).
- A line row carries a NaN centre: never read cx and cy when the sweep is 0 (research 01, trap 13).
- `ruff format` on a folder also rewrites the Python blocks of `SPEC.md`; format `.py` files by name, or use `tools/format`.
- An arc's P1 may lie up to eps_len off its circle, and its angle check uses eps_len/|P0 − C|: reversing an arc changes its radius, and the reversed arc may be invalid input. Point in region closes such an arc with a radial connector; tests of both orientations must allow for this (plan 0003, step 8).
- The predicates are exact only for coordinates that are 0 or have a magnitude in [2^−142, 2^201] (SPEC, precondition, not checked). Hypothesis draws far smaller floats often: property tests use a 2^-20 mm grid or filter to the range, or they fail on input outside the contract.
- `arc_from_bulge` with a large bulge on a chord within eps_len returns a full circle that ends at P0 (the nearly closed rule): loop generators in tests must check that the arc ends where the next row starts.
- clang-tidy (warnings are errors) rejects `operator[]` on spans and arrays (use `std::get`, `.at`, `subspan` or the `x()`/`y()` helpers), adjacent parameters of one type (use a struct), int8 to int conversions (signs return `int`), magic numbers and functions above cognitive complexity 15.

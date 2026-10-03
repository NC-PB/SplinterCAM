# AGENTS.md: geometry2d

Layer 1. Implements docs/research/01 (slice 1; the rest is under "Later parts" in the SPEC). Contract: `./SPEC.md`. Public API: `./__init__.py`. C++ part: `./kernel/`. Depends on: foundation. Work in progress: `docs/plans/active/0003-geometry2d-slice-1.md`.

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

## Known pitfalls

- A flattened arc lies inside the true arc; on convex walls that is a gouge (research 01, trap 3).
- A line row carries a NaN centre: never read cx and cy when the sweep is 0 (research 01, trap 13).
- `ruff format` on a folder also rewrites the Python blocks of `SPEC.md`; format `.py` files by name, or use `tools/format`.

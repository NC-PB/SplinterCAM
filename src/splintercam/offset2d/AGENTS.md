# AGENTS.md: offset2d

Layer 1. Implements docs/research/02 (plan 0005, `docs/plans/active/0005-offset2d.md`). Contract: `./SPEC.md`. Why it is built this way: `./DECISIONS.md` (read it before changing behaviour). Public API: `./__init__.py`. C++ part: `./kernel/`. Depends on: foundation, geometry2d (its Python API, and the kernel headers `kernel/exact.hpp`, `kernel/distance.hpp`, `kernel/grid.hpp`; DEC-G2D-040, DEC-OFF-001).

## Commands

- `tools/test-one offset2d`

## Invariants that must never break

- REQ-OFF-025: every boundary point of an offset with t > 0 lies in [t, t + a + 6u] from the flattened input; the chords of round joins lie in air.
- REQ-OFF-033: an offset is taken from source loops, never from an earlier result.
- REQ-OFF-042: a, the bias, the span limit and the join step limit come from declared parameters; no kernel source holds them as literals.

## Local rules

- The kernel includes geometry2d's headers by relative path (`../../geometry2d/kernel/grid.hpp`); `tools/arch-check` resolves quoted includes relative to the file and allows only geometry2d's `kernel_interface`.
- Only this module's Python code calls `splintercam._kernels.offset2d`. Kernel outputs are arrays the Python side allocates and passes in.
- The side follows from the region's kind: air shrinks, material grows (DEC-OFF-004).

## Known pitfalls

- Clipper2's `ClipperOffset` guesses the orientation from the path holding the extreme point; a hole holding it inverts the whole offset. Until step 5's guard, the area check of DEC-OFF-008 turns that into `OFFSET_FAILED`; it is a guard, not a proof of correctness.
- Source IDs come from `nearest_segments` (lower index on a tie) until step 6 applies the class tie of REQ-OFF-034 (DEC-OFF-009).

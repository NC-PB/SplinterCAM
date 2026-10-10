# AGENTS.md: offset2d

Layer 1. Implements docs/research/02. Complete and reviewed: `docs/plans/completed/0005-offset2d.md` (Handover). Contract: `./SPEC.md`. Why it is built this way: `./DECISIONS.md` (read it before changing behaviour). Public API: `./__init__.py`. C++ part: `./kernel/`. Depends on: foundation, geometry2d (its Python API, and the kernel headers `kernel/exact.hpp`, `kernel/distance.hpp`, `kernel/grid.hpp`; DEC-G2D-040, DEC-OFF-001).

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
- Every Clipper2 call ends in `kernel/result.cpp` (`finish_region`) and, on the Python side, in `_results.py` (`run_kernel`, `outcome`): pinch split, canonical order and IDs stay the same for offsets and Booleans.

## Known pitfalls

- Clipper2's `ClipperOffset` guesses the orientation from the path holding the extreme point; a hole holding it inverts the whole offset, and a shrink then comes back empty, which no area check sees. The guard triangle of DEC-OFF-011 takes the extreme point; the loop tree keeps the input order, so never assume outer loops come first.
- Source IDs: the class tie of REQ-OFF-034 over `nearest_ties` (DEC-OFF-013); segment order is not source-ID order, so never take the first candidate.
- Round joins do not keep their vertices under translation or a changed rounding: compare offsets as boundaries, not vertex to vertex (DEC-OFF-013).
- A side rule must see the chain the grid shows: a segment below u is invisible to the grown area but not to a float label, and turned a round end into tool side (DEC-OFF-018). A fold or a contact must be found on the chain (`find_contact`), never from output edges: Clipper2 joins collinear edges, so an edge's middle rarely lies over the overlap.

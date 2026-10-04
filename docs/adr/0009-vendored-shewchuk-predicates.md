# ADR 0009: Vendor Shewchuk's predicates.c for the exact predicates

- Status: Accepted (Peter, 2026-10-03)
- Date: 2026-10-02
- Deciders: Peter Burgener
- Drafted by: Claude Code (plan 0003, step 1)

## Context

Every sign decision of the float stages (side, collinearity, inside or outside) must come from an exact predicate, so every platform makes the same decisions (D-097, D-055 tier 1; [research 01, Vectors and exact signs](../research/01-foundations.md#vectors-and-exact-signs)). Shewchuk's adaptive predicates (SRC-032) are the standard implementation: `predicates.c`, one file of C, published at <https://www.cs.cmu.edu/~quake/robust.html> and, by its file header as research 01 reports it, placed in the public domain. It has not changed since 1996. D-097 decided to vendor it; AGENTS.md asks for an ADR for every new dependency (Peter, 2026-10-02).

## Decision

`predicates.c` is copied once, unchanged, into `src/splintercam/geometry2d/kernel/vendor/predicates.c`, and only the geometry2d kernel uses it.

- Unchanged: no SPDX line, no formatting, no fixes. Its own public-domain header is its licence statement; a REUSE sidecar `predicates.c.license` names it. The SHA-256 of the copy is recorded in that sidecar and in the plan's progress log.
- The build quirks (old-style C definitions, POSIX headers that MSVC lacks, warnings that our flags turn into errors) are handled in our own files: a C wrapper next to it in `kernel/` that includes it, and the CMake rules for it. The vendored file alone is compiled with the compiler's warnings off; it is excluded from `tools/format`, `tools/lint` and `tools/size-check` (they read only C++ files today).
- It is compiled with the strict float flags of D-097 (`-ffp-contract=off` and no fast-math on GCC and Clang, `/fp:precise` on MSVC), like every geometry2d kernel source, and `exactinit()` runs once when the kernel module loads. A build guard test checks the flags in every CI configuration (Shewchuk note, test 7).
- `architecture/modules.yaml` lists it under `kernel_libraries`:

  ```yaml
  shewchuk-predicates: { licence: public domain, used_by: [geometry2d], note: "vendored predicates.c, ADR 0009" }
  ```

## Consequences

- Exact orient2d and incircle, and the expansion arithmetic for our own arc predicate, without writing or maintaining that arithmetic ourselves.
- The kernel build gains the C language and one file outside our style and lint rules. Its global names (`orient2d`, `exactinit`, `splitter` and others) live in the extension module; the wrapper keeps them out of any header but its own.
- Other modules reach the predicates only through geometry2d's Python API (kernels-private). Arc fitting in toolpath needs them inside its kernel; how kernels share them is a later part of the geometry2d SPEC.

## Alternatives considered

- Our own port to C++: more code to review and test, and the arithmetic is easy to get subtly wrong.
- Fetch the file at build time (CMake `FetchContent` with a hash): every build would need the CMU server, which may move or vanish.
- A geometry library with robust predicates (CGAL: GPL; Boost.Geometry: no adaptive exact orient2d with Shewchuk's guarantees, and a much larger dependency for two predicates).
- Ports in other languages (JavaScript, Rust): not usable from the C++ kernel.

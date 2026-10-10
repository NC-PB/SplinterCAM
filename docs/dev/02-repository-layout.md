[Index](README.md) · [← 01. AI-first principles](01-ai-first-principles.md) · [03. Architecture rules →](03-architecture-rules.md)

# 02. Repository layout

The layout has one goal: from any file, an agent (or a new contributor) can tell what it belongs to, what rules apply, and where the contract and the tests are. It follows [ADR 0004](../adr/0004-tech-stack.md): one Python package, `splintercam`, with a C++ `kernel/` folder inside the modules that need fast array work.

## The tree

```text
SplinterCAM/
├── AGENTS.md                  map for all coding agents (short; see 08)
├── CLAUDE.md                  imports AGENTS.md, adds Claude Code specifics
├── README.md                  for people: what, status, how to build
├── CONTRIBUTING.md            how people and agents contribute
├── LICENSE                    Apache-2.0
├── NOTICE                     third-party attributions
├── pyproject.toml             one package; scikit-build-core builds the C++ kernels
├── CMakeLists.txt             builds splintercam._kernels from the kernel/ folders
├── uv.lock                    pinned Python dependencies
├── architecture/
│   └── modules.yaml           machine-readable module map and allowed dependencies
├── docs/
│   ├── research/              the algorithm guide (today: RESEARCH)
│   ├── dev/                   this folder's documents 01–10
│   ├── adr/                   architecture decision records
│   ├── specs/                 cross-module feature and change specs
│   │   └── 0007-adaptive-clearing/   requirements, design, tasks
│   ├── plans/
│   │   ├── active/            execution plans with progress logs
│   │   └── completed/
│   ├── glossary.md            domain terms and the code names for them
│   └── generated/             produced by tools; never edited by hand
├── schemas/                   JSON schemas: job, tool, machine, CL data, test case
├── src/splintercam/
│   ├── foundation/            vectors, units, tolerances, curves, results, diagnostics
│   │   ├── SPEC.md            the module's contract
│   │   ├── AGENTS.md          local rules (plus a one-line CLAUDE.md stub)
│   │   ├── __init__.py        the public API (explicit __all__)
│   │   └── *.py
│   ├── geometry2d/            offsets, Booleans, loop tree, medial axis
│   │   ├── SPEC.md, AGENTS.md, CLAUDE.md, __init__.py, *.py
│   │   └── kernel/            the C++ part: offset.cpp, voronoi.cpp, bindings.cpp
│   ├── geometry3d/            meshes, spatial index, drop-cutter, waterline (kernel/)
│   ├── io/                    STEP and IGES through OCP, meshes, DXF
│   ├── model/                 tools, cutting data, machines, setups (data)
│   ├── cl/                    neutral cutter-location data
│   ├── stock/                 stock models (kernel/)
│   ├── features/              hole and feature recognition (OCP)
│   ├── toolpath/              linking, optimisation, feeds (kernel/)
│   ├── strategies/
│   │   ├── profile/
│   │   ├── pocket/
│   │   ├── adaptive/          (kernel/)
│   │   ├── drilling/
│   │   ├── zlevel/
│   │   ├── finishing3d/
│   │   └── turning/
│   ├── kinematics/            (kernel/)
│   ├── ncx/                   NCX writer and the call of the pinned ncx binary (D-031)
│   ├── simulation/            (kernel/)
│   ├── job/                   documents, operation graph, recompute, persistence
│   └── apps/
│       ├── cli/               headless runner: job file in, NCX, NC programs (through ncx) and reports out
│       └── desktop/           PySide6 GUI; viewer/ wraps the OCCT viewer through OCP
├── tests/                     one folder per module, same names as in src/splintercam/
│   ├── geometry2d/
│   │   ├── unit/
│   │   ├── property/
│   │   └── differential/
│   └── …
├── testdata/
│   ├── zoo/                   reference parts: case.json, inputs, expected/, README.md
│   ├── regressions/           minimised failures, one folder per issue
│   ├── golden/                approved outputs (only tools/golden-approve writes here)
│   └── LICENSES.md            source and licence of every test file
├── benchmarks/
├── tools/                     stack-neutral entry points: check, test, render, replay …
├── .claude/                   settings, rules, skills, subagents
├── .github/                   CI workflows, PR template, CODEOWNERS
├── .editorconfig
└── .gitattributes             LFS for meshes and STEP files
```

## Why it looks like this

- **One folder per module, contract inside it.** `SPEC.md`, `AGENTS.md`, the Python code and its C++ `kernel/` sit together, so an agent working on `geometry2d` finds everything in one place. Documentation that lives far from its code goes stale. Tests live in `tests/<module>/` under the same name, so they are not shipped inside the package.
- **`architecture/modules.yaml` is data, not prose.** Tools read it to enforce dependencies ([03](03-architecture-rules.md)), to generate the module graph in `docs/generated/`, to check each module's size budget ([12](12-lean-code.md)), and to scaffold new modules. Agents read it to learn what they may import.
- **`strategies/` holds one folder per strategy.** Strategies never depend on each other, so several agents can work on different strategies in parallel without conflicts.
- **`kernel/` folders hold all C++.** They are compiled into one extension module, `splintercam._kernels`. Kernels see only arrays and small permissive C++ libraries, never OCCT, Qt or Python objects; the desktop viewer's display helper is not a compute kernel and may link OCCT (D-166). OCCT is reached only through OCP, in `io`, `features` and the desktop viewer ([03](03-architecture-rules.md), [09](09-dependencies-licensing-provenance.md)).
- **`apps/cli` comes before `apps/desktop`.** A headless runner lets agents and CI run complete jobs, compare outputs and render pictures without a GUI.
- **No posts here.** Controller dialects, cycles and machine definitions live in NCXchange: its TOML machine files are the machine data, and users edit them there (D-021, D-031, D-053).
- **`testdata/` is shared, `tests/` is per module.** Big files (meshes, STEP models, reference outputs) are shared between modules and CI, tracked with Git LFS, and each has a licence entry.
- **`tools/` is the stable interface.** Whatever the stack, agents always run `tools/check`, `tools/test-one` and so on ([tools/README.md](../../tools/README.md)). Changing the build system later then does not invalidate the agent instructions.

## Naming and size rules

- Folders and files: lowercase with underscores (`drop_cutter.py`, `drop_cutter.cpp`), so Python can import them; hyphens only in folders outside `src/` (`testdata/zoo/pocket-island-touching-wall/`).
- Module and type names come from [the glossary](../glossary.md). A new domain term goes into the glossary in the same change.
- One concept per file. Files stay under about 400 lines: `tools/size-check` reports above 400 and fails above 800 (generated code excepted). Functions stay under about 60 lines; ruff and clang-tidy fail on the function limits of [12](12-lean-code.md), section 3 (D-139).
- No `utils`, `helpers`, `common` or `misc` folders. They become dumping grounds, and agents add to them eagerly. Put code where its concept lives, or create a named module.
- Every module declares a size budget in non-comment lines (NLOC) in `architecture/modules.yaml`, estimated from its SPEC. `tools/size-check` reports a module over its budget and fails it at 20 % over. Raising a budget is a decision. A module that would outgrow about 25 source files or 5 000 lines is split instead, with an ADR if the split changes `modules.yaml`.

## Test data layout

```text
testdata/zoo/pocket-island-touching-wall/
├── case.json          operation, tool, parameters, tolerances, checks to run
├── part.step          or part.dxf / part.stl
├── expected/          golden outputs (CL JSON, NCX, report) once approved
└── README.md          what the case tests, where it came from, its licence
```

A failing input dumped by the geometry core goes to `failures/` (ignored by git). Once minimised, it moves to `testdata/regressions/<issue-id>/` with the same structure and becomes a permanent test ([06](06-testing-and-quality-gates.md)).

---

[Index](README.md) · [← 01. AI-first principles](01-ai-first-principles.md) · [03. Architecture rules →](03-architecture-rules.md)

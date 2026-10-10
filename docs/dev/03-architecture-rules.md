[Index](README.md) · [← 02. Repository layout](02-repository-layout.md) · [04. Code conventions →](04-code-conventions.md)

# 03. Architecture rules

Agents follow patterns well and boundaries badly: given the chance, they import whatever solves the problem at hand. So the boundaries are written down as data, checked by a test on every change, and kept simple enough to state in one table.

## Layers

| Layer | Modules | Implements RESEARCH |
| --- | --- | --- |
| 0 Foundation | `foundation` | [01](../research/01-foundations.md) |
| 1 Geometry and input | `geometry2d`, `geometry3d`, `io` | 02, 03, 06, 07, 21 (Project Spike) |
| 2 Model | `model`, `cl`, `stock` | 08, 23, 26 (Project Spike) |
| 3 Planning | `features`, `toolpath`, `strategies/*` | 04, 05, 09, 10, 11, 14–16, 20, 22, 25 (Project Spike) |
| 4 Machine | `kinematics`, `ncx`, `simulation` | 08, 12, 27 (Project Spike) |
| 5 Application | `job` | (topic 19 is being rewritten from public sources, T-019; until then the rules here are ours) |
| 6 Apps | `apps/cli`, `apps/desktop` | n/a |
| Inside modules | `kernel/` folders (C++), compiled into `splintercam._kernels` | 17 (Project Spike) |

## Dependency rules

1. A module imports only lower layers, or same-layer modules named in its `depends_on` in `modules.yaml`; all `depends_on` together form no cycle (Peter, 2026-10-08). `depends_on` names every module a module imports, lower layers too, so an import it does not name fails (Peter, 2026-10-08, plan 0006). `tools/arch-check` checks exactly these dependency rules: this one, no cycles, and rule 2.
2. No strategy imports another strategy. Shared logic moves down into `toolpath`, `geometry2d` or `geometry3d`.
3. C++ lives only in `kernel/` folders. A module's Python code calls its own kernel; other modules call that module's Python API, never another module's kernel. Kernels use only the C++ libraries listed in `modules.yaml` and never include OCCT, Qt or Python headers (only `bindings.cpp` includes nanobind).
4. OCCT is used only through OCP, and only in `io`, `features` and `apps/desktop`. OCCT objects never leave those modules: between modules a shape travels as a `ShapeRef` (the serialised B-rep with its stable face and edge IDs), and meshes and curves travel as NumPy arrays.
5. Nothing below layer 6 depends on a UI toolkit, a file dialog, the clock or the network. PySide6 is used only in `apps/desktop`. Files are read and written only in `io`, `job` and `apps`.
6. `apps/*` use only the public interface of `job`.

The rules live in [`architecture/modules.yaml`](../../architecture/modules.yaml). `tools/arch-check` reads it, checks the map itself, the Python imports of every module, the includes of every kernel and the external packages each module uses, and fails on any violation. It is a script on the standard library, without import-linter (Peter, 2026-10-08, plan 0006). Another module's kernel may include only the headers listed under `kernel_interface` on the providing module's entry. Changing `modules.yaml` needs a person's approval, because it changes what every agent is allowed to do.

## Design rules for the core

- **Functional core, thin shell.** Geometry and strategies are functions from immutable inputs to new outputs. State (the job, the stock history, caches) lives in `job`.
- **Explicit context.** Every computation receives a `Context` with the tolerance set, a cancellation token, a progress reporter, a logger and a debug sink. Nothing reads global settings.
- **One uniform strategy interface.** Every strategy declares its parameters once (typed, with units and defaults; D-018: the operation panels are generated from these declarations) and exposes one planning function:

```text
Strategy
  id, algorithmVersion
  parameters: ParameterDeclarations
  plan(input: StrategyInput, ctx: Context) -> Result<Toolpath, Diagnostics>

StrategyInput = part geometry, stock snapshot, tool, cutting data, work frame, tolerance set
```

  A new strategy is a new folder that implements this interface; nothing else in the code base changes.
- **Typed diagnostics, not just logs.** Every operation returns a list of diagnostics (code, severity, message, location), for example `BALL_TIP_ON_FLAT` or `TOOL_DOES_NOT_FIT`. Expected domain outcomes are results; exceptions are for programming errors only.
- **One neutral output.** Strategies produce `cl` data, the toolpath record (research 26). The `ncx` module writes it as NCX, the same for every controller, and runs the pinned `ncx` binary that ships with the app; NCXchange compiles it for the machine. No SplinterCAM module writes a controller dialect, a canned cycle in a control's syntax or a machine-specific number format (D-021, D-031, D-148, D-149). Machine data comes from NCXchange's machine files (D-053).
- **Debug sink everywhere.** Any module can emit named debug geometry (points, polylines, meshes, text). The CLI writes it as SVG and JSON with `--debug`, so an agent can look at the intermediate state of a failing computation.
- **Deterministic parallelism.** Work is split by operation, Z level or region; results are merged in a fixed order; `--threads 1` gives the same output (D-055, ADR 0008).
- **Versioned algorithms and files.** Each strategy carries an algorithm version, and old job files recompute with the version they were made with. Schemas and file formats carry versions too.
- **Kernels speak arrays.** A kernel function takes NumPy arrays and plain values and returns arrays, plain values and diagnostic codes. No Python objects, callbacks or OCCT types cross the boundary. Long kernels release the interpreter lock and check a cancellation flag passed in as a plain value (ours). The one exception to "no OCCT" is the display helper of `apps/desktop`, which fills the viewer's buffers and makes toolpaths pickable; it is not a compute kernel (D-166).
- **The split rule.** Loops over points, segments, triangles or grid cells belong in a kernel or in vectorised NumPy. Loops over operations, tools, features, files or UI elements stay in Python ([ADR 0004](../adr/0004-tech-stack.md)).
- **Long OCCT work in a worker process (D-140).** Imports, sewing, meshing, healing, shape checks, face references and feature recognition run outside the GUI process and send back a `ShapeRef` and arrays. OCP holds the interpreter lock for the whole of every OCCT call, so a thread in the GUI process would freeze the interface (the stack test app's plan 0001).

## Public interfaces

Each module's `__init__.py` has an explicit `__all__`; modules and names starting with an underscore are internal. `tools/docs` generates a short API summary per module into `docs/generated/api/<module>.md`. Agents working on a module read the summaries of its dependencies instead of their source code, which keeps their context small. A change to a public interface is a spec change ([05](05-specs-plans-decisions.md)).

## Recompute model

The job holds operations as a graph. Each parameter declares what it affects (path, links, feeds, stock, output), and a change marks only those aspects dirty (ours). This is also what makes agent-written strategies safe to add: they plug into the graph through the strategy interface and never manage recomputation themselves.

---

[Index](README.md) · [← 02. Repository layout](02-repository-layout.md) · [04. Code conventions →](04-code-conventions.md)

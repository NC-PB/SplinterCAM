# ADR 0004: Tech stack: Python application on OCP, C++ compute kernels

- Status: Accepted, to be confirmed by the stack test app ([plan 0001](../plans/0001-stack-test-app.md))
- Date: 2026-09-24
- Deciders: Peter Burgener
- Drafted by: Claude

## Context

The application must run on Windows, macOS and Linux. It needs a B-rep kernel (OpenCASCADE, OCCT), a 3D view with hover and sub-shape selection, fast geometry for toolpaths and stock, and a code base that AI agents write well and a person can review. [10](../engineering/10-stack-decision.md) lists the criteria and candidates.

Two earlier designs were rejected during the discussion on 2026-09-24:

- **C++ core with Qt GUI, Python for tests only:** the simplest runtime architecture, but nearly all code would be C++, where agents are weakest and reviews are hardest.
- **Own C++ core that also owns OCCT, with a Python application on top:** OCCT would exist twice in one process (our core and a Python binding for the viewer), or the viewer would need its drawing surface passed from Qt through Python into C++. Too many interfaces that only move data around.

The missing piece was OCP, the maintained Python binding of OCCT used by CadQuery and build123d: Apache-2.0, installable with pip for Windows x86-64, macOS x86-64 and arm64, Linux x86-64 and arm64, Python 3.11 to 3.14, version 8.0.1 matching OCCT 8.0.1 (released 2026-09-05). It includes the OCCT viewer (AIS) with hover highlighting and sub-shape selection, which CQ-editor already embeds in a Qt window from Python.

## Decision

1. **Application language: Python.** One pinned CPython version (3.13 to start), managed with uv and a lock file. Type hints everywhere, pyright in strict mode, ruff for linting and formatting.
2. **CAD kernel: OCCT through OCP** (`cadquery-ocp`). OCP is used only in `io`, `features` and the desktop viewer. OCCT objects never leave those modules: between modules a shape travels as an opaque `ShapeRef` (the serialised B-rep with its stable face and edge IDs), and meshes and polylines travel as NumPy arrays.
3. **GUI: PySide6** (Qt for Python, LGPLv3) with Qt Widgets. The 3D view is the OCCT AIS viewer through OCP inside a Qt widget: first with a native window handle (proven by CQ-editor and pythonocc), then the QOpenGLWidget approach if the test app shows it works. GPL-only Qt modules are banned (Charts, Graphs, Data Visualization, Quick 3D, Virtual Keyboard and the others listed in [09](../engineering/09-dependencies-licensing-provenance.md)).
4. **Compute kernels: C++20** (plus `std::expected`), built into one extension module `opencam._kernels` with nanobind and scikit-build-core. Kernels depend only on small permissive libraries (Clipper2, Boost.Polygon Voronoi, nanoflann, Eigen and similar), never on OCCT, Qt or Python. Data crosses the boundary as NumPy arrays and plain values; kernels release Python's global interpreter lock while they work.
5. **The split rule.** Loops over points, segments, triangles or grid cells go into a C++ kernel or vectorised NumPy. Loops over operations, tools, features, files or UI elements stay in Python.
6. **Platforms:** Windows x86-64, macOS arm64 (x86-64 while OCP supports it), Linux x86-64 on X11, and on Wayland through XWayland (OCCT has no native Wayland support).
7. **Fallback:** if the test app fails on the viewer or on packaging, switch to an all-C++ application with Qt Widgets and OCCT (the Mayo structure), with Python kept for tests and tools. That switch needs a new ADR.

## Consequences

- Only one boundary is ours: the kernel API. It is narrow (arrays in, arrays out) and tested directly from Python with pytest and Hypothesis.
- Most code is Python, which agents handle best and which is quick to review. The C++ part stays small, stable and specified by RESEARCH.
- Long OCCT operations (large STEP imports, sewing) run in a worker process so the GUI stays responsive; shapes cross as serialised B-rep data.
- Installers are large (Python, Qt, OCCT, NumPy). The packaging tool is chosen in the test app (pyside6-deploy, PyInstaller or Briefcase).
- Open-source Qt gets patches only until the next minor release, so PySide6 and Qt are upgraded about every six months as a routine task.
- OCCT renders with OpenGL only; on macOS that API is deprecated by Apple. Every OCCT application shares this risk; the viewer stays behind our own small interface.
- We depend on OCP's maintainers. If OCP stalls, pythonocc-core (LGPL-3.0, also at OCCT 8.0.1) is a drop-in candidate at the binding level.
- Refines [ADR 0002](0002-licence-apache-2.md): there is no `adapters/` folder any more. LGPL libraries (OCCT inside OCP, Qt through PySide6) are used as separate, dynamically loaded libraries the user can replace, as [09](../engineering/09-dependencies-licensing-provenance.md) now describes.
- Docs affected: [02](../engineering/02-repository-layout.md), [03](../engineering/03-architecture-rules.md), [04](../engineering/04-code-conventions.md) (language appendix), [06](../engineering/06-testing-and-quality-gates.md), [09](../engineering/09-dependencies-licensing-provenance.md), and the templates.

## Alternatives considered

- **All C++ with Qt Widgets and OCCT:** kept as the fallback (point 7).
- **C++ core owning OCCT plus a Python application:** rejected, see Context.
- **C#/.NET with Avalonia:** the maintainer's strongest language, but OCCT has no open cross-platform .NET binding (the official wrapper is commercial), so most libraries would need self-written C wrappers, and the viewer would be written from scratch.
- **Web UI with WASM:** the target is the desktop; large meshes and OCCT in the browser add risk without need.
- **Rust:** too few of the needed libraries, and unfamiliar to review.

## Sources

- OCP on PyPI: <https://pypi.org/project/cadquery-ocp/>; CQ-editor: <https://github.com/CadQuery/CQ-editor>; pythonocc-core: <https://github.com/tpaviot/pythonocc-core>
- OCCT viewer features: <https://occt3d.com/dev/doc/overview/html/occt_user_guides__visualization.html>; Wayland status: <https://tracker.dev.opencascade.org/view.php?id=33505>
- Qt licensing: <https://doc.qt.io/qt-6/licensing.html>; Qt maintenance periods: <https://www.qt.io/development/qt-framework/maintenance-periods>
- Agents and C++: <https://kabirk.com/multilingual>, <https://arxiv.org/html/2607.00107>

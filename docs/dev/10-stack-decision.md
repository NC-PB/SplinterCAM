[Index](README.md) · [← 09. Dependencies, licensing and provenance](09-dependencies-licensing-provenance.md) · [11. User interface →](11-user-interface.md)

# 10. Stack decision

**Decision of 2026-09-24 ([ADR 0004](../decisions/0004-tech-stack.md)):** a Python application on Windows, macOS and Linux, using OCCT through its Python binding OCP (including the OCCT viewer), a PySide6 GUI, and C++20 compute kernels that work on arrays, built with nanobind. Loops over points, segments, triangles or cells go into the kernels; everything else stays in Python. An all-C++ application with Qt and OCCT is the fallback. The stack test app ([plan 0001](../plans/0001-stack-test-app.md)) confirms the decision before real code is written.

The rest of this document is kept as the record of how the decision was prepared: the questions, the criteria, and the candidates. The candidate table does not yet list the chosen hybrid, which combines profile E (Python with C++) with OCP instead of an own OCCT layer. Facts about tools and versions were checked on 2026-09-24.

## Questions to answer first

1. Which platforms must the first release run on: Windows, macOS, Linux desktop, a browser, a tablet next to the machine?
2. Is a web or cloud version a goal, now or later?
3. Should the CAM also run inside another host (for example as a FreeCAD workbench or a plugin), or only stand-alone?
4. Which language must the maintainers be able to review line by line? Agents write the code; people must still judge it.
5. Which scripting language should users get for post-processors and machining templates?
6. What are the performance targets (for example drop-cutter over a million triangles, adaptive clearing of a large pocket)?

## Criteria

| Criterion | Why it matters here |
| --- | --- |
| Platforms | Decides UI toolkit, packaging and whether native libraries can be used everywhere |
| Maintainer review | The quality gate of an AI-first project is human review; a language the reviewers read fluently makes reviews real |
| Agent effectiveness | Strict types and compiler errors, one-command build and test, fast incremental builds and a mainstream language all make agents more reliable |
| Library access | OCCT, Clipper2, Boost.Polygon Voronoi, Manifold, OpenVDB and geometry-central are C++; cavalier_contours is Rust with a C API; Clipper2 also exists in C# ([RESEARCH 17](../research/17-libraries-and-roadmap.md)) |
| Numerics and speed | 64-bit floats, SIMD, multithreading, control over memory for large meshes and stock models |
| UI and 3D view | A cross-platform toolkit with a usable 3D viewport |
| Scripting | Posts and templates are user-edited scripts or data ([RESEARCH 13](../research/13-post-processing.md), [19](../research/19-software-design.md)) |
| Packaging | Shipping native libraries for every platform |
| Contributors | Who else could help in an open-source CAM project |

## Candidate profiles

| | A: C#/.NET core | B: C++ core | C: Rust core | D: Web UI + WASM core | E: Python + C++ |
| --- | --- | --- | --- | --- | --- |
| Current version | .NET 10 LTS (Nov 2025, supported to Nov 2028) | C++20 | stable Rust | TypeScript + C++ or Rust compiled to WASM | Python 3 + C++ extensions |
| Build and test | `dotnet build`, `dotnet test` | CMake with vcpkg or Conan; GoogleTest or Catch2 | `cargo build`, `cargo test` | npm tooling plus the core's toolchain | pytest plus the C++ toolchain |
| Property tests | CsCheck (Apache-2.0), FsCheck (BSD-3) | RapidCheck | proptest | fast-check | Hypothesis |
| Architecture tests | ArchUnitNET (Apache-2.0), NetArchTest eNhanced (MIT) | Custom include checks | Crate boundaries plus a custom check | Custom import rules | import-linter |
| Native libraries | Own C API adapters; `LibraryImport` and `SafeHandle`; native files in NuGet `runtimes/<rid>/native/`. No maintained open cross-platform OCCT binding (the official C# wrapper is commercial) | Direct | cavalier_contours native; OCCT through own C API | Libraries must compile to WASM; memory and threading limits | Direct in the C++ part |
| UI | Avalonia (MIT, version 12) or others | Qt (LGPL or commercial) or others | Young toolkits | Browser, any device | Qt for Python or others |
| Agent notes | Strict compiler and analyzers, fast builds | Agents make memory errors: sanitizers mandatory in CI; slow builds; hardest to review | Compiler catches much; fewer reviewers | Two toolchains to keep green | Needs strict type checking (pyright or mypy) to give agents real feedback |
| Fits best if | Desktop on three platforms, C# reviewers | Maximum performance and library access | Safety and performance, Rust reviewers | Browser and tablets are required | Fast prototyping, FreeCAD-like scripting |

Mixed stacks are possible, but each extra language doubles the tooling that has to stay green and the knowledge a reviewer needs. For an AI-first project, one main language plus thin C API adapters is the simplest structure that works.

## What the decision fills in

Status on 2026-09-24, after ADR 0004:

- Done: [ADR 0004](../decisions/0004-tech-stack.md) accepted; the language appendix in [04](04-code-conventions.md); layout ([02](02-repository-layout.md)), architecture rules ([03](03-architecture-rules.md)), tests ([06](06-testing-and-quality-gates.md)), licences ([09](09-dependencies-licensing-provenance.md)); `templates/AGENTS.md`, `templates/modules.yaml`, the path-scoped rules and the implementation column in templates/tools/README.md (`test_repo/tools/README.md`).
- In the test app ([plan 0001](../plans/0001-stack-test-app.md)): the real `tools/*` scripts, the CI matrix for the three systems, the packaging tool and signing, and confirming or replacing ADR 0004.

## Sources

- .NET 10 release and support: <https://github.com/dotnet/core/blob/main/release-notes/10.0/README.md>
- Avalonia: <https://www.nuget.org/packages/avalonia>; test and architecture packages on <https://www.nuget.org/>
- Native interop in .NET: <https://learn.microsoft.com/en-us/dotnet/standard/native-interop/pinvoke-source-generation>, <https://learn.microsoft.com/en-us/nuget/create-packages/native-files-in-net-packages>
- OCCT C# wrapper (commercial): <https://occt3d.com/news/open-cascade-c-wrapper-updated-for-occt-8-0-0/>

---

[Index](README.md) · [← 09. Dependencies, licensing and provenance](09-dependencies-licensing-provenance.md) · [11. User interface →](11-user-interface.md)

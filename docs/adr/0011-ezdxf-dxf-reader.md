# ADR 0011: ezdxf as the DXF reader of io

- Status: Accepted (Peter, 2026-10-13)
- Date: 2026-10-12; accepted 2026-10-13
- Deciders: Peter Burgener
- Drafted by: Claude Code (plan 0007, step 2)

## Context

Plan 0007 (the first NC program) starts from a DXF drawing; step 2 reads it in `io` ([research 21](../research/21-geometry-input.md), `src/splintercam/io/SPEC.md`). D-092 (accepted 2026-09-28) names ezdxf as the reference reader for DXF, and `architecture/modules.yaml` already lists it under `external`, allowed in `io` only. It is not yet in `pyproject.toml`. `docs/dev/09-dependencies-licensing-provenance.md` requires an ADR for every new dependency: why it is needed, the alternatives, its licence, its maintenance status and the platforms it supports.

Facts, checked 2026-10-12 on PyPI (`https://pypi.org/pypi/<name>/json`):

- ezdxf 1.4.4, MIT (classifier "License :: OSI Approved :: MIT License"), "Development Status :: 5 - Production/Stable", released 2026-05-14; pre-releases of 1.4.5 follow. Requires Python ≥ 3.10.
- Wheels for CPython 3.13 on macOS (x86_64, arm64, universal2), Linux (manylinux and musllinux, x86_64 and aarch64) and Windows (amd64), and a pure-Python wheel (`py3-none-any`) for anything else; the compiled parts are optional speed-ups.
- Required dependencies: pyparsing (MIT), typing-extensions (PSF-2.0), numpy (already ours, BSD-3-Clause) and fonttools (MIT). Its extras (`draw`, `dev`) pull in PySide6, PyQt5, matplotlib and PyMuPDF (AGPL); none of them is installed.

## Decision

ezdxf is a runtime dependency of SplinterCAM, used only in `io`.

- It goes into `[project] dependencies` in `pyproject.toml` as `ezdxf>=1.4.4`, without extras, pinned in `uv.lock`.
- Only `src/splintercam/io/` imports it; `tools/arch-check` enforces this already (`architecture/modules.yaml`, `external`, `allowed_in: [io]`). No ezdxf object leaves `io`: between modules a contour is geometry2d's `CurveRows`.
- Its extras are never installed. `draw` would bring PyMuPDF (AGPL), which `docs/dev/09` does not allow.
- `NOTICE` lists ezdxf and its three new transitive dependencies with their licences, as a packaged application ships them (MIT and PSF-2.0 ask for their notices to be kept).
- It is used as a reader only. No code is copied from it (docs/dev/09); research 21 cites its documentation (SRC-123).
- Applying this ADR touches `pyproject.toml`, `uv.lock` and `NOTICE`; it comes with the first code of plan 0007, step 2.

## Consequences

- `io` reads every DXF version ezdxf reads, with the OCS and the header variables handled by a maintained library, and the slice's tests can write their own DXF files with the same library.
- The packaged application grows by ezdxf, pyparsing, typing-extensions and fonttools. fonttools is the largest of them and is needed only for ezdxf's text rendering, which `io` does not use; it cannot be left out without patching ezdxf's requirements.
- An upgrade of ezdxf is a lock-file change reviewed like any other; the tests of `io` cover what the slice relies on (research 21 tests 1 to 7).
- `tools/licence-check`, when written, sees MIT and PSF-2.0, both in the allowed class.

## Alternatives considered

- Our own DXF reader: the group-code format is simple, but binary DXF, the versions since R12, the OCS, the classes of polylines and the header variables are not. A reader nobody here has tested against real CAD output would be the slice's weakest part, and D-092 already chose ezdxf as the reference.
- OCCT through OCP: as we know it, the open-source OCCT has no DXF reader (DXF import is one of its commercial components). Not checked further, since D-092 decides the reader.
- libdxfrw (LibreCAD) and other C++ readers: GPL, not allowed (docs/dev/09), and they would need a binding.
- dxfgrabber: the predecessor of ezdxf by the same author, no longer maintained.
- ezdxf as an optional dependency: every job of the slice needs it; making it optional only adds an error path.

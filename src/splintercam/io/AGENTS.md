# AGENTS.md: io

Layer 1. Implements the DXF-import part of docs/research/21 (plan 0007, step 2; the rest of topic 21
is in Project Spike). Contract: `./SPEC.md`. Why it is built this way: `./DECISIONS.md` (read it
before changing behaviour). Public API: `./__init__.py`. No C++ part; io calls geometry2d's kernel
through its Python API (`rows_from_bulges`, `rows_from_sweeps`, `row_boxes`, `curve_rows`). Depends
on: foundation, geometry2d. External: ezdxf (MIT, ADR 0011).

## Commands

- `tools/test-one io`

## Invariants that must never break

- REQ-IO-004, 028: the unit is taken from `$INSUNITS` and converted once, at import; every
  diagnostic about an entity names its index, type, DXF handle and segment.
- REQ-IO-009: an entity's OCS reaches world coordinates through the ±z rule; a −z extrusion mirrors
  x and reverses every sweep and bulge. Never read the raw OCS coordinates as world coordinates.
- REQ-IO-021, 022: a junction snaps one row's end onto the other's, the row that magnifies less
  moving; the move is bounded per row by B, silent to 3·eps_len, a reported gap to the gap limit,
  refused above it, all of a refused row's moves dropped together (order-independent).
- REQ-IO-026: the import returns a value only when exactly one closed chain remains; open chains,
  refused gaps and branches return no value.
- D-055: same file and arguments give the same rows, IDs and diagnostics, in the same order
  (REQ-IO-029); `_diagnostics.Collector` is the one place that order lives.

## Local rules

- The loop over ezdxf entities is Python (ezdxf yields Python objects). Per-point work — arc
  construction from bulges, re-placing a moved arc's centre, bounding boxes — goes to geometry2d's
  kernel, never a Python or NumPy transcendental loop (SPEC, split rule; D-055).
- Tolerances come from `ctx.tolerances`; the gap limit is the declared parameter
  `dxf_gap_close_mm` read from `splintercam.foundation.TOLERANCE_DEFAULTS` (REQ-IO-022, REQ-FND-014).
  No literal epsilon.
- OCP is not imported here even though the layer allows it (`.claude/rules/ocp.md`): a DXF is read
  straight into NumPy curve rows.

## Known pitfalls

- `ezdxf.new()` defaults `$INSUNITS` to 6 (metres), not 0: a test for "no unit" must set it to 0.
- ezdxf's `add_lwpolyline` default point format is `xyseb`; pass `format="xyb"` to give bulges.
- A LINE is read in world coordinates (it has no OCS); only ARC, CIRCLE, LWPOLYLINE and 2D POLYLINE
  go through the OCS (REQ-IO-009).
- ezdxf reports 3D polylines, meshes and spline-/curve-fit polylines all as `POLYLINE`; the subtype
  is decided from `is_3d_polyline`, `is_poly_face_mesh`, `is_polygon_mesh` and the fit flags
  (REQ-IO-003).
- A mirrored (−z) drawing's loop runs clockwise, so its signed area is negative; the invariant is
  that |area| is unchanged, not the sign (REQ-IO-009).
- The chain reconstruction is provisional and O(n²) in row ends (DEC-IO-005); it is replaced when
  topic 25's chaining is released. Do not grow it into a general chainer here.

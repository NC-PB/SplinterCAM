---
topic: "21"
title: Geometry input
readiness: L4 for the DXF import of plan 0007; the rest of the topic is in Project Spike (L2)
release: "1"
reviewed: 2026-10-25
provenance: public
---

[Index](README.md) · [1. Foundations](01-foundations.md)

# 21. Geometry input: the DXF import of plan 0007

This file holds the part of topic 21 that plan 0007 (the first NC program) needs: reading closed contours of lines and arcs from a DXF file into geometry2d's curve rows. STEP, meshes, healing, face IDs, splines, ellipses and blocks stay in Project Spike's topic 21 until a plan pulls them; this file grows as they move (D-158).

## Scope

- In: a DXF file (any version ezdxf reads) with LINE, ARC, CIRCLE, LWPOLYLINE and 2D POLYLINE entities in model space; its unit; chaining the entities into closed contours; one contour handed on as curve rows with a source ID per row.
- Out (later): SPLINE and ELLIPSE (D-034, D-092), INSERT and blocks, 3D entities, HATCH, TEXT, open chains for profiles along an open edge, layers as hole or outline hints (D-027), DXF circles as holes (D-027).

## Method

1. **Reading.** ezdxf (MIT, D-092 names it as the DXF reference reader) opens the file; only model space is read. Every entity of another type is listed once per type in an info diagnostic (`DXF_SKIPPED`, ours), so nothing is dropped silently.
2. **Units** (D-033, D-028). The header variable `$INSUNITS` gives the drawing unit: 4 is millimetres, 1 inches (× 25.4), 5 centimetres (× 10), 6 metres (× 1000); 0 or a missing variable mean "no unit". Any other value states a unit the slice does not take (2 is feet, for example), so the import stops with `DXF_UNIT_UNSUPPORTED` (error) naming the value; it is never read as "no unit", because the job's millimetres would then scale a drawing in feet wrongly (RR-004). A job unit that differs from the file's unit stops the import with `DXF_UNIT_CONFLICT` (error, Peter, plan 0007). A file without a unit is not guessed: the job must state it (plan 0007's job file has a `units` field), otherwise the import stops with `DXF_NO_UNITS` (error), naming the part size in drawing units so the user can tell millimetres from inches. Conversion to mm happens here, once, and never later (D-028). The part size (the bounding box in mm) is reported after every import (D-033).
3. **Plane and OCS.** Plan 0007 reads the XY plane only. ARC, CIRCLE, LWPOLYLINE and 2D POLYLINE store their points in the entity's object coordinate system (OCS); only a 3D POLYLINE stores world points (RR-004), given by its extrusion vector. An extrusion of (0, 0, 1) is the identity. An extrusion of (0, 0, −1) is the mirror image: x changes sign and every arc's direction reverses (ARC angles and bulges are counter-clockwise in the OCS, so they become clockwise in the world). Every other extrusion, and every entity whose elevation or z values differ from the reference z by more than eps_len, is skipped with `DXF_NOT_PLANAR` (warning, ours). ezdxf converts OCS points to world coordinates (`ocs().to_wcs`); The reference z is the z value shared by the most entities, ties going to the one met first in model-space order (ours): the first contour is not known before chaining, and a stray entity listed first must not discard the part (RR-004). The direction rule is ours and is tested (test 3).
4. **Entities to rows.** LINE gives a line row. ARC gives an arc row from its centre, radius and start and end angles (degrees, counter-clockwise in the OCS); its end points are computed from the angles, and geometry2d's `make_arc` validates them. CIRCLE gives a full circle (sweep 2π) starting at angle 0. ezdxf reports every kind of old-style polyline as `POLYLINE`; its flags (group code 70) tell them apart: 8 a 3D polyline, 16 a polygon mesh, 64 a polyface mesh, 2 curve-fit and 4 spline-fit vertices added (the vertex flags 1, 8 and 16 then mark fit vertices and frame control points). Plan 0007 reads a plain 2D POLYLINE only, none of the flags 2, 4, 8, 16 or 64 set, and lists every other kind as its own type in `DXF_SKIPPED` (ours; SRC-123, the POLYLINE and VERTEX flags). LWPOLYLINE and plain 2D POLYLINE give one row per segment, an arc where the bulge is not 0 (research 01, Curves, bulge; geometry2d's `arc_from_bulge`), and close back to the first vertex when the closed flag is set. Each row's source ID is the entity's index in model space times 2^16 plus the segment index (ours), so a diagnostic can name the entity and segment.
5. **Chaining** (research 01, Loop tree input; topic 25 names the chaining tolerance as its own, not yet released). Plan 0007 uses a fixed rule (ours, to be replaced when topic 25's chaining is released): end points within the gap limit (0.01 mm) form a junction and are made equal bit for bit by moving one row's end onto the other's. Moving an arc's end while its sweep is kept moves its centre: every point of the arc moves by up to (|ΔP0| + |ΔP1|)·D/c, where c is the chord and D = c for a sweep up to π and D = c / sin(|φ|/2) above it, so a 0.005 mm move on a 359° arc shifts the arc by about 0.6 mm. So the row with the smaller magnification D/c moves (a line before an arc), the most any point of the row moves (B) is computed per row, moves with B up to 3·eps_len are silent, moves with B up to the gap limit are kept and reported as `DXF_GAP_CLOSED` (warning, with the position, the gap and B), and a larger B refuses the row's moves with `DXF_GAP_NOT_CLOSED` (error). Ends further apart than the gap limit are never joined. No published repair rule for arcs was found; this rule is ours (RR-004, SplinterCAM `src/splintercam/io/SPEC.md`, REQ-IO-020 to 022). A row whose end has two or more continuations (a T or a crossing) stops the chain there with `DXF_BRANCH` (error, with the position). Rows are joined in the direction the drawing gives, reversed where needed.
6. **Which contour.** Plan 0007's job names a layer, or none for the whole drawing. Exactly one closed chain must remain; none or several stop the import with `DXF_CONTOUR_COUNT` (error), listing each chain's size and position. An open chain stops the import with `DXF_OPEN_CHAIN` (error, with its two end points): an end that meets nothing is a gap larger than the limit, and with a mere warning an outline that does not close could let the only other closed loop, a hole circle for example, be machined as the part (Peter, plan 0007; RR-004). The contour goes on to geometry2d as curve rows (`curve_rows`), which checks its rows, and the operation builds its region from it (`build_region`, kind material).

## Parameters

| Parameter | Unit | Default | Range | Source |
| --- | --- | --- | --- | --- |
| Joining distance | mm | eps_len (1e-6) | from the tolerance set | research 01, Tolerances |
| Largest gap closed with a warning (`dxf_gap_close_mm`) | mm | 0.01 | declared; 0 disables it | Peter (plan 0007), until topic 25 releases its chaining tolerance |
| Silent end move | mm | 3·eps_len | from the tolerance set | research 01, Tolerances (snapping share) |
| Unit when `$INSUNITS` is missing or 0 | none | none: the job must say | mm or inch | D-033 |

## Traps

1. `$INSUNITS` is often missing or 0; a guess from the size is a suggestion only (D-033).
2. Mirrored entities (extrusion (0, 0, −1)) reverse every arc; read through the OCS, never the raw coordinates.
3. Bulges are stored on the segment's start vertex; the last vertex's bulge closes the polyline only when it is closed.
4. ARC angles are in degrees; convert once (D-028).
5. End points of "connected" entities rarely match bit for bit; never close a larger gap silently.

## Tests

1. A rectangle 100 × 60 with four fillets of radius 5, drawn as one closed LWPOLYLINE with bulges, in mm: one contour of 8 rows, area 6000 − (4 − π)·25 mm², part size 100 × 60.
2. The same rectangle drawn as 4 LINE and 4 ARC entities in random order and direction: the same contour as test 1 within eps_len.
3. Test 1 mirrored by extrusion (0, 0, −1): the mirror image in world coordinates, every arc clockwise where it was counter-clockwise, the area unchanged.
4. Units: test 1 in inches (`$INSUNITS` = 1) gives 2540 × 1524 mm; without `$INSUNITS` it stops with `DXF_NO_UNITS` unless the job gives the unit.
5. Gaps: a gap of 0.005 mm between a line and an arc is closed by moving the line's end, with `DXF_GAP_CLOSED`; a gap of 0.02 mm stops the import with `DXF_OPEN_CHAIN`; a 0.005 mm gap whose only rows are arcs of 359° is refused with `DXF_GAP_NOT_CLOSED`.
6. A drawing with a TEXT, a SPLINE and a 3D POLYLINE besides the contour: the contour is read, `DXF_SKIPPED` lists TEXT, SPLINE and the 3D polyline once each.
8. Units: `$INSUNITS` = 2 (feet) stops with `DXF_UNIT_UNSUPPORTED`; a file in inches with a job in millimetres stops with `DXF_UNIT_CONFLICT`.
9. Test 1 drawn as a 2D POLYLINE with extrusion (0, 0, −1): the same mirror image as test 3.
7. Two closed contours without a layer: `DXF_CONTOUR_COUNT` lists both; with the layer of one of them, that one is read.

## Libraries

ezdxf (MIT), Python, used only in `io` (`architecture/modules.yaml`, external).

## Sources

ezdxf documentation (SRC-123: the bulge value; the OCS, the `$INSUNITS` codes and the POLYLINE and VERTEX flags from the same documentation, checked against ezdxf 1.4.5's constants); decisions D-027, D-028, D-033, D-034, D-092; research 01. The rest is ours, marked so.

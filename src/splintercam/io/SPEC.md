# SPEC: io

<!-- File import. Drafted on 2026-10-12 from research 21 with /research-to-spec (plan 0007, step 2), cut to the slice (D-160): the DXF import of one closed contour. STEP, meshes and the rest of topic 21 come with later plans. Revised the same day after the first spec review (two blockers on POLYLINE, the gap rule on arcs, branch matching). -->

| | |
| --- | --- |
| Status | Draft (2026-10-12), for Peter's review. Nothing is implemented. |
| Layer | 1 (see architecture/modules.yaml) |
| Depends on | foundation, geometry2d (Python API only: `curve_rows`, `CurveRows`, `Box`, and the array entries of open question 5); external ezdxf (MIT, `architecture/modules.yaml`; ADR 0011, proposed) |
| Research | [21][r21]: DXF import of plan 0007, normative. Through it [01][r01], sections Tolerances, Curves (Arc form, Bulge) |
| Decisions | D-027 (holes and outlines; circles not yet holes), D-028 (mm inside, converted once at import), D-033 (files without units), D-034 and D-092 (splines and ellipses later; ezdxf as the reader), D-049 (declared parameters), D-055 (determinism), D-057 (arc form, bulge only at DXF); DEC-G2D-016 and 019 (coordinate and radius limits); text in [docs/spike/decisions-snapshot.md](../../../docs/spike/decisions-snapshot.md) |
| Owner | Peter Burgener |

## Purpose

Reads a DXF drawing and hands one closed contour of lines and arcs, in millimetres, to geometry2d as curve rows, each row with a source ID that names its entity and segment. It reports the part size, converts the unit once and never guesses one, and names every repair, skipped entity and ambiguity. Its first user is the outside profile of plan 0007, through the job (step 7).

## Scope

- In: [research 21][r21], sections Scope, Method, Parameters, Traps: LINE, ARC, CIRCLE, LWPOLYLINE and 2D POLYLINE in model space; `$INSUNITS`; the OCS with extrusion ±z; chaining with eps_len joins and gap closing; one closed contour chosen by layer or by being the only one.
- Out, handled elsewhere: validating rows and building the region (geometry2d: `curve_rows`, `build_region`); the job file and its `units` and `layer` fields (job, plan 0007 step 7); showing diagnostics to the user (apps).
- Later parts (research 21, Out): SPLINE and ELLIPSE, spline-fit and curve-fit polylines, INSERT and blocks, 3D entities, HATCH, TEXT as geometry, open chains for profiles, layers as hole or outline hints, circles as holes, several contours, drawings far from the origin (national grid coordinates), STEP, meshes, topic 25's chaining tolerance.
- Non-goals: guessing a unit from the part size (D-033: a suggestion at most, and that belongs to the UI); repairing damaged DXF files (ezdxf's recover mode); writing DXF.

## Public interface

Lengths in mm, float64 (D-028). All names are proposals (ours); research 21 names none. No kernel.

```python
from enum import Enum
from pathlib import Path
from splintercam.foundation import Context, Result
from splintercam.geometry2d import Box, CurveRows

class DrawingUnit(Enum): MILLIMETRE; INCH          # what a job may state for a file without $INSUNITS (D-033)

@dataclass(frozen=True, slots=True)
class DxfContour:
    loop: CurveRows                                  # one closed loop, mm, in the drawing's direction (row_starts == [0])
    part_size: Box                                   # bounding box of `loop`, mm (D-033)

def read_dxf_contour(path: Path, layer: str | None, unit: DrawingUnit | None, ctx: Context) -> Result[DxfContour]: ...

def decode_source_id(source_id: int) -> tuple[int, int]: ...   # (entity index in model space, segment index)
```

- A source ID is entity index × 2^16 + segment index (research 21, Method 4, ours). The entity index counts every entity of model space in ezdxf's order, skipped ones included; diagnostics add the DXF handle, which is what a CAD system shows (REQ-IO-028).
- `layer` selects the entities of one layer; `None` reads the whole drawing (research 21, Method 6).
- `unit` is used only when the file has no unit (REQ-IO-006 to 008).
- The value is present only when the result is `ok` (REQ-FND-004): any error diagnostic, `DXF_BRANCH` included, means no value for the whole import. Warnings and info diagnostics come with the value.
- Split rule (docs/dev/03) and determinism (D-055): the loop over ezdxf entities is Python, since ezdxf yields Python objects; polyline vertices are taken as arrays; the end matching and the move checks (sqrt and products only) run in NumPy over all rows. Arc rows (from bulges, and after an end moves) and the bounding box of the contour need transcendental functions over every segment, which must run in C++ with libm, never in NumPy ufuncs (`src/splintercam/geometry2d/AGENTS.md`, Local rules). geometry2d has them only per curve (`arc_from_bulge`, `bounding_box`), so io needs array forms of them in geometry2d's kernel (open question 5). An ARC or CIRCLE entity's end points from its angles use Python's `math` (libm) once per entity.

## Requirements

Rows are [x0, y0, x1, y1, cx, cy, sweep] (REQ-G2D-188). Every length below is in mm after the unit conversion; reading, conversion and the entity checks run before any chaining.

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-IO-001 | THE io module SHALL read DXF files with ezdxf, model space only, and SHALL turn LINE, ARC, CIRCLE, LWPOLYLINE and 2D POLYLINE entities into curve rows in mm. | unit: research 21 tests 1, 2 | Draft |
| REQ-IO-002 | IF the file cannot be opened or ezdxf cannot parse it, THEN `read_dxf_contour` SHALL return no value and `DXF_UNREADABLE` (error) with ezdxf's message (ours). | unit | Draft |
| REQ-IO-003 | WHEN the selected entities include other types, THE io module SHALL skip them and report `DXF_SKIPPED` (info) once per type, naming the type and its count. A POLYLINE that is not a plain 2D polyline (3D polyline, polygon mesh, polyface, or spline-fit or curve-fit 2D polyline) counts as its own type, named by its subtype (ours: ezdxf reports all of them as `POLYLINE`). | unit: research 21 test 6; one test per POLYLINE subtype | Draft |
| REQ-IO-004 | THE io module SHALL take the drawing unit from `$INSUNITS`: 4 millimetres (× 1), 1 inches (× 25.4), 5 centimetres (× 10), 6 metres (× 1000), and SHALL scale every coordinate once, at import; arc sweeps are not scaled. | unit: research 21 test 4 | Draft |
| REQ-IO-005 | THE io module SHALL treat a missing `$INSUNITS`, the value 0 and every value not listed in REQ-IO-004 as "no unit" (research 21 trap 1). | unit | Draft |
| REQ-IO-006 | IF the file has no unit and `unit` is `None`, THEN `read_dxf_contour` SHALL return no value and `DXF_NO_UNITS` (error), naming in drawing units the size of the bounding box of the entities that would be read (research 21 names the part size; before chaining that is the best known, ours). | unit: research 21 test 4 | Draft |
| REQ-IO-007 | WHEN the file has no unit and `unit` is given, THE io module SHALL convert with that unit (MILLIMETRE × 1, INCH × 25.4). | unit: research 21 test 4 | Draft |
| REQ-IO-008 | IF the file has a unit and `unit` is given and differs from it, THEN `read_dxf_contour` SHALL return no value and `DXF_UNIT_CONFLICT` (error), naming both (provisional, open question 2). | unit | Draft |
| REQ-IO-009 | THE io module SHALL read ARC, CIRCLE, LWPOLYLINE and 2D POLYLINE through their OCS (2D POLYLINE vertices are OCS points, like LWPOLYLINE's; research 21 lists only the first three, RR-004): an extrusion parallel to +z is the identity; one parallel to −z maps x to −x and the elevation e to world z −e, and reverses the sign of every sweep and bulge (trap 2). Parallel means within eps_ang after normalising (research 01, Tolerances). | unit: research 21 test 3 for each of the four types | Draft |
| REQ-IO-010 | IF an OCS entity's extrusion is not parallel to ±z, or the world z of any entity (a LINE's two end points; an OCS entity's elevation) differs from the reference z by more than eps_len, THEN the io module SHALL skip it and report `DXF_NOT_PLANAR` (warning). The reference z is the world z value, compared bit for bit, with the most votes: one vote per selected entity of a read type with an accepted extrusion, a LINE voting only when its two z values agree within eps_len; ties go to the value voted first in model-space order (ours, a deviation: research 21 says "the first contour", which is not known before chaining, and a stray entity listed first must not discard the part; RR-004). | unit | Draft |
| REQ-IO-011 | IF an entity holds a value that is not finite, a polyline has fewer than two vertices, or a coordinate or radius in mm exceeds 10^9 (DEC-G2D-019; DEC-G2D-016's half-extent), THEN the io module SHALL skip the entity and report `DXF_ENTITY_INVALID` (warning) naming the reason (ours). | unit | Draft |
| REQ-IO-012 | THE io module SHALL turn an ARC into one arc row: sweep = (end − start) mod 360° in (0°, 360°], an end angle equal to the start angle giving a full circle (ours), converted to radians once (trap 4); end points from the angles; an arc that is nearly closed by REQ-G2D-049 becomes a full circle. | unit | Draft |
| REQ-IO-013 | THE io module SHALL turn a CIRCLE into one full-circle row (sweep 2π, mirrored −2π) starting at angle 0 of its OCS. | unit | Draft |
| REQ-IO-014 | THE io module SHALL turn an LWPOLYLINE or plain 2D POLYLINE into one row per segment, a line where the bulge is 0 or its sagitta c·|b|/2 is at most eps_len (REQ-G2D-051, applied before the limits of REQ-IO-011) and otherwise the arc of research 01, Curves, Bulge, each bulge taken from the segment's start vertex; the closing segment from the last vertex to the first only when the closed flag is set (trap 3). | unit: research 21 test 1 | Draft |
| REQ-IO-015 | THE io module SHALL drop a line row, or a polyline segment whatever its bulge, whose chord is at most eps_len, and an ARC whose length |φ|·r is at most eps_len, before chaining, and report `DXF_DEGENERATE` (info) once per entity (research 01, Arc form: such curves are removed by cleanup; the report ours). A full circle is kept, unless its radius is at most eps_len, which drops it the same way (research 01, Arc form). | unit: a closed LWPOLYLINE repeating its first vertex, bulge 0 and 1 | Draft |
| REQ-IO-016 | THE io module SHALL give each row the source ID entity index × 2^16 + segment index; IF an entity has more than 2^16 segments, THEN it SHALL skip the entity and report `DXF_ENTITY_TOO_LARGE` (warning) (ours). | unit | Draft |
| REQ-IO-017 | WHERE two rows are exact duplicates (two lines with the same end points within eps_len in either order; or two arcs with the same end points within eps_len, centres within eps_len and equal sweeps, or with the ends swapped and the sweep negated), THE io module SHALL keep the one with the smaller source ID and report `DXF_DUPLICATE` (info) (ours: a line drawn twice is common in DXF and harmless to drop). | unit | Draft |
| REQ-IO-018 | THE io module SHALL match row ends in two stages, after REQ-IO-015 and 017, with full-circle rows taking no part (each is a closed chain on its own) and the two ends of one row never partners: (1) a cluster is a connected component of the graph that links ends within eps_len; a cluster of exactly two ends of different rows is a junction; (2) of the ends still unmatched, two within the gap limit that are each other's only candidate are a junction too. | unit, property | Draft |
| REQ-IO-019 | IF a stage-1 cluster holds three or more ends, or an unmatched end has two or more candidates within the gap limit, THEN the io module SHALL report `DXF_BRANCH` (error) with the position, and the import returns no value (research 21, Method 5 stops only the chain there; failing the import is ours: with a T among the selected entities the contour is ambiguous, and a job naming the part's layer avoids it). | unit: a T, a crossing, two short rows below the gap limit in a chain that is not a branch; property | Draft |
| REQ-IO-020 | WHEN two ends form a junction, THE io module SHALL make them bit for bit equal by moving one row's end onto the other's: the row with the larger magnification D/c keeps its end, where c is the row's chord and D = c for a line or an arc with |φ| ≤ π and D = c / sin(|φ|/2) for |φ| > π; on a tie the row with the smaller source ID keeps it (ours, a deviation from research 21's midpoint, RR-004: a line end moves instead of an arc wherever a line meets an arc). A moved arc keeps its sweep and gets its centre on the perpendicular bisector of its new end points (research 01, Arc form). | unit, property | Draft |
| REQ-IO-021 | THE io module SHALL bound each row's moves by B = (|ΔP0| + |ΔP1|)·D/c, the most any point of the row moves (ours, derived: with the sweep kept, every point of an arc is P0 + (P1 − P0)·w with w fixed by φ and the parameter, and |w|, |1 − w| ≤ D/c), computed once per row with all its proposed moves. WHERE B ≤ 3·eps_len (the snapping share of research 01, Tolerances), the moves are silent. | unit: a 359° arc, a semicircle, a 10° arc; property | Draft |
| REQ-IO-022 | WHERE a row's B exceeds 3·eps_len, THE io module SHALL keep its moves if B is at most the gap limit (default 0.01 mm, 0 disables it) and report `DXF_GAP_CLOSED` (warning) per junction with the position, the gap and B; IF B exceeds the gap limit or a moved row's chord becomes at most eps_len, THEN it SHALL refuse every move of that row, leave those junctions open and report `DXF_GAP_NOT_CLOSED` (warning) with the position, the gap and B. Refusing only removes moves, so the result does not depend on the order of the rows. | unit: research 21 test 5; an arc and a line shorter than the gap; gap limit 0; property | Draft |
| REQ-IO-023 | WHEN two ends lie more than the gap limit apart, THE io module SHALL not join them (trap 5). | unit: research 21 test 5; property | Draft |
| REQ-IO-024 | THE io module SHALL chain rows in the direction the drawing gives, reversing a row where needed; each chain starts at its row with the smallest source ID, in that row's direction (ours, D-055). | unit, property | Draft |
| REQ-IO-025 | WHEN `layer` is given, THE io module SHALL read only the entities of that layer, the name compared exactly (provisional, ours; DXF's own rule to be cited at implementation); IF no read entity is on it, THEN it SHALL report `DXF_LAYER_EMPTY` (error) naming the layer. | unit: research 21 test 7 | Draft |
| REQ-IO-026 | IF not exactly one closed chain remains, THEN `read_dxf_contour` SHALL return no value and `DXF_CONTOUR_COUNT` (error), listing each closed chain's bounding box, or saying that there is none; WHEN open chains remain, THE io module SHALL report `DXF_OPEN_CHAIN` (warning) per open chain, with its two end points. | unit: research 21 tests 5, 7 | Draft |
| REQ-IO-027 | WHEN one closed chain remains, THE io module SHALL hand it to `curve_rows` as one loop and return its diagnostics with its own; IF `curve_rows` returns no value, THEN `read_dxf_contour` SHALL return no value. WHEN the import succeeds, THE io module SHALL return the loop's bounding box as `part_size` and report it as `DXF_PART_SIZE` (info) (D-033). | unit: research 21 tests 1, 4 | Draft |
| REQ-IO-028 | THE io module SHALL name the entity in every diagnostic about one: its index, type and DXF handle, and the segment where there is one; positions in mm (ours). | unit | Draft |
| REQ-IO-029 | THE io module SHALL return the same rows, IDs and diagnostics, in the same order, for the same file and arguments, in these groups: file (`DXF_UNREADABLE`, `DXF_NO_UNITS`, `DXF_UNIT_CONFLICT`, `DXF_LAYER_EMPTY`); `DXF_SKIPPED` by type name; entity diagnostics by entity index, segment, then code; junction diagnostics (`DXF_BRANCH`, `DXF_GAP_CLOSED`, `DXF_GAP_NOT_CLOSED`) by position, x then y, then code; `DXF_OPEN_CHAIN` by its chain's smallest source ID; `DXF_CONTOUR_COUNT`; `curve_rows`' diagnostics in its order; `DXF_PART_SIZE` (ours, D-055). `CANCELLED` comes alone. | unit, property | Draft |
| REQ-IO-030 | WHEN `ctx.cancel` is set, THE io module SHALL return no value and `CANCELLED` (REQ-FND-013). | unit | Draft |

## Invariants

- The returned loop is closed: each row's end equals the next row's start bit for bit, and the last row's end the first row's start (REQ-IO-020). Property test over generated contours with jittered ends.
- No point of a returned row lies further than its B from the drawn row, and B is at most max(3·eps_len, gap limit) (REQ-IO-021, 022). Property test, sampling points along each row.
- Every returned source ID decodes to an entity of a read type on the selected layer (REQ-IO-016, 025). Property test over generated drawings with mixed types and layers.
- Mirroring a drawing by extrusion −z mirrors the loop and keeps |area| (REQ-IO-009). Property test over all four OCS types.
- Reordering and reversing the entities of a drawing gives the same loop as a point set, within 6·eps_len where no gap was closed: each reading lies within 3·eps_len of the drawing (REQ-IO-021, 024; research 21 test 2). Property test.

## Tolerance budget

io spends at most the snapping share 3·eps_len of research 01's flattening allowance, and only on silent moves (REQ-IO-021): re-placing an arc's centre magnifies an end move by D/c, so moves are bounded per row by B, not per end. A closed gap is a reported model repair, not tolerance spent: the drawn contour moves by at most the gap limit, 0.01 mm by default, which equals the finishing tolerance (open question 1). Unit conversion is one multiplication per coordinate.

## Failure modes and diagnostics

| Situation | Result | Diagnostic |
| --- | --- | --- |
| File missing or not DXF | no value | `DXF_UNREADABLE` (error) |
| No unit, none given | no value | `DXF_NO_UNITS` (error), size in drawing units |
| File unit and given unit differ | no value | `DXF_UNIT_CONFLICT` (error), provisional |
| Entity type or POLYLINE subtype not read | skipped | `DXF_SKIPPED` (info), once per type |
| Extrusion not ±z, or another z | entity skipped | `DXF_NOT_PLANAR` (warning) |
| Non-finite value, too few vertices, beyond 10^9 mm | entity skipped | `DXF_ENTITY_INVALID` (warning) |
| Polyline with more than 2^16 segments | entity skipped | `DXF_ENTITY_TOO_LARGE` (warning) |
| Curve of length ≤ eps_len | dropped | `DXF_DEGENERATE` (info) |
| Same curve drawn twice | one dropped | `DXF_DUPLICATE` (info) |
| A row moves by 3·eps_len < B ≤ gap limit | closed | `DXF_GAP_CLOSED` (warning) |
| A row would move by B > gap limit, or collapse | its junctions left open | `DXF_GAP_NOT_CLOSED` (warning) |
| T or crossing of row ends, or an end with two gap candidates | no value | `DXF_BRANCH` (error) |
| Layer given, nothing read on it | no value | `DXF_LAYER_EMPTY` (error) |
| Open chain | listed | `DXF_OPEN_CHAIN` (warning) |
| Zero or several closed chains | no value | `DXF_CONTOUR_COUNT` (error) |
| Invalid row in the contour | as `curve_rows` | geometry2d's codes, such as `ARC_INCONSISTENT` |
| Success | value | `DXF_PART_SIZE` (info) |
| Cancelled | no value | `CANCELLED` (warning) |

## Algorithms and design inputs

| Element of the method | Public source, or own design with date |
| --- | --- |
| DXF parsing, OCS to WCS, `$INSUNITS` codes, bulge, POLYLINE modes | ezdxf documentation (SRC-123); research 21, Method 1 to 4 |
| Bulge to arc, centre on the bisector | research 01, Curves, Bulge and Arc form |
| Mirrored OCS reverses arcs | research 21, Method 3 (the direction rule is ours, tested); 2D POLYLINE added (RR-004) |
| Chaining, joins and gap closing | research 21, Method 5, a fixed rule (ours) until topic 25 releases its chaining; the two-stage matching, the junction rule and the move bound B ours (B derived in REQ-IO-021), 2026-10-12 |
| Source ID encoding | research 21, Method 4 (ours) |
| Reference z, duplicates, chain start, diagnostic order | ours, 2026-10-12 |

## Example parts

- A plate outline drawn as one closed LWPOLYLINE with filleted corners: read as one loop (research 21 test 1).
- The same outline exported as separate LINE and ARC entities whose ends miss by a few µm, some drawn backwards: one loop with `DXF_GAP_CLOSED` where the ends missed by more than eps_len (tests 2, 5).
- A part mirrored with the CAD's mirror command, its arcs and polylines stored with extrusion −z: read as the mirror image, not as the original (test 3).
- A drawing with dimensions and text and the part on its own layer: text and dimensions skipped and listed; with the layer named, the outline is read (tests 6, 7). Without a layer, a title block's cells form T joints and the import stops with `DXF_BRANCH`.
- A plate with drilled holes drawn as circles on the same layer: several closed chains, `DXF_CONTOUR_COUNT`; the slice reads only the outline, on its own layer (circles as holes are D-027, later).
- A drawing from a CAD that writes `$INSUNITS` = 0: stops with `DXF_NO_UNITS` and the size in drawing units, so a 100-unit part can be told from a 4-unit one (test 4).
- An outline closed by a near-full arc whose ends miss their neighbouring arcs by 0.008 mm: not closed, since the arc would move by far more (`DXF_GAP_NOT_CLOSED`, an open chain). Where the neighbour is a line, the line's end moves instead and the gap closes.

## Test plan

- Unit: research 21 tests 1 to 7, test 3 for ARC, CIRCLE, LWPOLYLINE and 2D POLYLINE, and one test per requirement above, tagged with its ID. The DXF files are written by ezdxf inside the tests (`tests/io/`), not committed as binaries, so each case shows its geometry in code.
- Property: generated closed contours of lines and arcs, written as separate entities in random order and direction, with end jitter below eps_len and between eps_len and the gap limit: one loop, within the gap limit of the drawing, closed bit for bit (REQ-IO-018 to 024, 029). Mirrored copies (REQ-IO-009).
- Golden cases: none in step 2; the DXF of `profile-rectangle-fillets` comes with step 7.
- Differential: none. ezdxf is the reference reader (D-092).

## Performance budget

None set: research 21 gives none, and the slice's drawings hold tens of entities. End matching sorts the ends and compares within a window, so a polyline of 10^4 segments stays linear apart from the sort.

## Size estimate

About 300 NLOC of Python and 350 of tests in io, plus about 80 NLOC of C++ and bindings and 100 of tests in geometry2d for open question 5, in its own pull request. Plan 0007 estimated 200 + 250; the POLYLINE modes, the two-stage matching and the move bound of the reviews add to it. That is 50 % over the plan's code estimate, so it goes to Peter with this draft (docs/dev/12, section 3; open question 4).

## Open questions

<!-- Box 1 only, in machining terms with a recommendation. -->

1. **Gap closing at finishing tolerance.** Where two entities miss each other by up to 0.01 mm, one is stretched to meet the other (a line rather than an arc), and only when no point of it moves by more than 0.01 mm. So the finished wall can sit up to 0.01 mm from the drawing at a closed gap, the whole finishing tolerance, with a warning naming the place. A: keep 0.01 mm (research 21). B: 0.0016 mm, the geometry share of the finishing tolerance 0.01 mm (research 01, Tolerances); larger gaps stop the import as an open chain and the drawing must be fixed. Recommended: A for the slice, since the warning shows the place and topic 25 replaces the rule. Either way the limit is a declared parameter, `dxf_gap_close_mm` in `tolerance_defaults.toml` beside offset2d's entries (the REQ-FND-012 precedent), which needs one foundation requirement in the implementation pull request: a change to foundation's interface, so yours to approve.
2. **The job states a unit and the file states another.** For example the file says centimetres or inches and the job says millimetres. A: stop with `DXF_UNIT_CONFLICT`; the user corrects the job. B: the file wins, the job's unit is ignored with a warning. C: the job wins. Recommended: A, provisional in REQ-IO-008: with B or C a part could be cut 10 or 25.4 times too large or too small after a one-word mistake.
3. **ADR 0011 (ezdxf as a runtime dependency).** The first dependency of the application beyond numpy; MIT, with pyparsing (MIT), typing-extensions (PSF-2.0) and fonttools (MIT). Recommended: accept.
4. **Size.** About 300 lines of code instead of the plan's 200, plus about 80 in geometry2d (question 5), because of the safety rules above (POLYLINE subtypes, mirrored polylines, branch matching, the move bound). A: accept, and set `io`'s budget in `architecture/modules.yaml` to 360 (+20 %). B: cut gap closing from the slice (any gap stops the import as an open chain), about 220 lines. Recommended: A, since exported DXF rarely closes bit for bit.
5. **Arcs on every machine the same.** Turning polyline bulges into arcs, re-placing an arc after its end moves, and the part size need sine, cosine and arctangent for every segment. geometry2d forbids NumPy for these, because its results can differ in the last digit between processors, and that can flip a join or gap decision so the same DXF gives a different contour on another computer (D-055). A: add array forms of `arc_from_bulge`, of an arc from two end points and a sweep, and of the bounding box of curve rows to geometry2d's C++ kernel: a change to geometry2d's interface, in its own pull request before io. B: io calls geometry2d once per segment in Python, against the split rule; a 10^4-segment polyline then takes a noticeable fraction of a second. Recommended: A.

Box 2 items taken in this draft (ours, to `src/splintercam/io/DECISIONS.md` when the SPEC is reviewed): the interface names; the codes `DXF_UNREADABLE`, `DXF_ENTITY_INVALID`, `DXF_DEGENERATE`, `DXF_DUPLICATE`, `DXF_ENTITY_TOO_LARGE`, `DXF_LAYER_EMPTY`, `DXF_PART_SIZE`; ARC with equal angles as a full circle; the reference z; the two-stage matching; the junction rule (the row with the larger magnification keeps its end), the move bound B and the silent limit 3·eps_len; `DXF_BRANCH` failing the whole import; `DXF_GAP_NOT_CLOSED`; the duplicate rule; the chain start and diagnostic order; exact layer names, provisional until the DXF rule is cited.

## Change log

- 2026-10-12: drafted from research 21 (plan 0007, step 2); revised after the first and second spec reviews.

[r01]: ../../../docs/research/01-foundations.md
[r21]: ../../../docs/research/21-geometry-input.md

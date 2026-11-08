# SPEC: setupsheet

<!-- The setup sheet of one NC program. Drafted on 2026-11-08 for plan 0009 (docs/plans/active/0009-setup-sheet.md),
     cut to the slice of plan 0007: one setup, flat end mills, the profile's record. The feature map's full sheet
     (pictures, holders, stick-out, cutting times, templates, PDF, translations) comes with later plans. -->

| | |
| --- | --- |
| Status | Draft (2026-11-08, for Peter's review: AQ-055 to AQ-059 in `docs/agents/questions/`; one spec review folded in). Choices marked "(ours)" are in `src/splintercam/setupsheet/DECISIONS.md` |
| Layer | 4, proposed (AQ-057; not yet in `architecture/modules.yaml`) |
| Depends on | foundation (`Context`); geometry2d (`CurveRows`, `row_boxes`, the arc box of REQ-G2D-214); model (`JobData` and its types); cl (`ClData`, `MoveKind`, `Role`) |
| Research | [10][r10], Method 1 to 5, traps 1 and 2 (heights, the descent at P, clamps not modelled); [26][r26], Structure and Control compensation and measurement points; [27][r27], the Datum row, trap 7 and "still missing in NCX" (no stock word); [22][r22], Method 5 (the approach along the normal). Project Spike: `product/feature-map.md`, section 8 (the setup sheet row, Peter 2026-10-03); `QUESTIONS.md`, Q-137 item 5 (templates later, open); research 30 is not researched yet (L0) |
| Decisions | D-151 and D-154 (the sheet states every point a program uses, with a, r and where to measure it), D-062 (heights), D-078 (setups; fixtures later), D-148 (no controller knowledge), D-055 (determinism); Peter: AQ-010 (no blank in the program), AQ-015 item 1 (a) and AQ-021 (the sheet states the clamp, jaw and approach limits), AQ-016 item 7 (witness marks), AQ-035 (notes 1 to 8 are this sheet's first requirements) |
| Owner | Peter Burgener |

## Purpose

Tells the person at the machine, before the first run, what the NC program does not say and the CAM does not check: which tool each T number must be and where its length is measured, where the datum lies on the blank, how big the blank may be, where clamps and jaws must not stand, where the tool comes down beside the stock, the heights and feeds, and that the program has not yet run on a machine. It turns the setup notes of AQ-035 (now in `testdata/zoo/profile-rectangle-fillets/README.md` and `docs/plans/active/0007-log/2026-10-31-step8-dry-run-checklist.md`) into numbers computed from the job and the toolpath record, for every job. Its user is `job`, which writes the sheet next to the NC program (plan 0009, step 4).

## Scope

- In: one setup (D-078) with its work offset and box stock; flat end mills with their measurement points (model, REQ-MDL-001); the operations of the `cl` record in program order; the part's contour for its size; the approach points, the descents, the region the tool reaches below the clearance height and the witness marks, computed from the record; the program's and the files' names; an HTML rendering (AQ-055).
- Out, handled elsewhere: writing the file and when it is written (`job`, AQ-058); checking the job's values (`model`); the record's rules (`cl`, `toolpath`); the controller's name for the work offset (NCXchange, D-148; RR-023); whether the program compiled (`ncx`, `job`); the program's own form, such as fillets as short line blocks (D-023; dry-run checklist item 9) and spindle and coolant off at the end (DEC-NCX-008).
- Later (one line each, no work): the clamping picture and the part picture; material, programmer and date as job fields (hand-fill fields in the slice, AQ-056); holders, stick-out, minimum stick-out, registers by name (feature map, section 4); cutting time per operation and totals, tool changes (D-113); the stock state from a previous setup; several setups and origins; fixture keep-outs from fixture models (D-078, research 30); the full-slot note of AQ-035 item 5 (needs the stock model's engagement, AQ-056); free notes per job and setup; PDF; templates in the shop folder and bundles (Q-137 item 5); the interface language (feature map, section 1; AQ-055); the `sheet` command of the command line (feature map, section 1).
- Non-goals: modelling fixtures or checking collisions with them (the sheet states limits, it does not check them); any machine or controller data (D-148: layer 4 is named "machine", but this module holds none); a second check of the record.

## Public interface

Lengths in mm, feeds in mm/min, speeds in 1/min, float64 (D-028). Every height is the tool tip's (D-154: the record keeps the tip). All names are proposals (ours). No kernel; loops over moves are vectorised NumPy (split rule).

```python
from dataclasses import dataclass
from enum import Enum
from splintercam.cl import ClData
from splintercam.foundation import Context
from splintercam.geometry2d import CurveRows
from splintercam.model import JobData

@dataclass(frozen=True, slots=True)
class SheetFiles:                       # names only, no folders (REQ-SHT-002)
    program_name: str                   # NCX PROGRAM NAME
    program_number: int                 # NCX NUMBER, ≥ 1
    ncx_file: str                       # e.g. "RECT_FILLETS.ncx"
    nc_files: tuple[str, ...]           # the compiled files, at least one, as job names them
    machine_file: str                   # e.g. "heidenhain-itnc530.toml"
    job_file: str
    part_file: str

@dataclass(frozen=True, slots=True)
class Box3:                             # axis-aligned, work frame
    min_mm: tuple[float, float, float]
    max_mm: tuple[float, float, float]

@dataclass(frozen=True, slots=True)
class SheetPoint:                       # a measurement point an operation uses (D-154)
    number: int                         # k
    axial_offset_mm: float              # a
    register_radius_mm: float           # r

@dataclass(frozen=True, slots=True)
class SheetTool:
    number: int
    diameter_mm: float
    flute_length_mm: float
    points: tuple[SheetPoint, ...]      # those the program uses, k ascending

class Side(Enum):                       # where P lies off the stock box (REQ-SHT-011)
    MINUS_X = "-X"; PLUS_X = "+X"; MINUS_Y = "-Y"; PLUS_Y = "+Y"; CORNER = "corner"

@dataclass(frozen=True, slots=True)
class ApproachPoint:                    # where the tool comes down (research 10, Method 2)
    x_mm: float
    y_mm: float
    descents: int                       # RAPIDs ending here below h_c
    rapid_to_mm: float                  # the lowest end of those RAPIDs
    lowest_mm: float                    # the lowest end of a move along Z alone here
    feeds_mm_min: tuple[float, ...]     # the feeds of the LINEs along Z alone here, order of first use
    side: Side | None                   # None where lowest_mm is not below the stock top
    centre_distance_mm: float | None    # P to the stock box in XY
    gap_mm: float | None                # centre_distance_mm − R: tool edge to stock box

@dataclass(frozen=True, slots=True)
class WitnessMark:                      # where a straight approach meets the cut (AQ-016 item 7)
    centre_x_mm: float; centre_y_mm: float      # S, the tool centre
    contact_x_mm: float; contact_y_mm: float    # S + R·u
    passes: int                                 # how many passes start at this S with this u

@dataclass(frozen=True, slots=True)
class SheetOperation:
    name: str; strategy: str
    tool_number: int; point_number: int; axial_offset_mm: float
    spindle_rpm: float
    tol_mm: float
    feeds: tuple[tuple[str, float], ...]        # the header's feed classes, in its order
    clearance_mm: float; retract_mm: float      # h_c, h_r
    lowest_mm: float                            # the lowest end of any move
    approach_points: tuple[ApproachPoint, ...]
    witness_marks: tuple[WitnessMark, ...]
    reach: Box3 | None                          # REQ-SHT-012; None if no move goes below h_c
    end_xy_mm: tuple[float, float]              # the last move's end in XY (REQ-SHT-016)

@dataclass(frozen=True, slots=True)
class SetupSheet:
    files: SheetFiles
    part_box_xy_mm: tuple[float, float, float, float]   # x_min, y_min, x_max, y_max
    work_offset: int
    stock: Box3
    tools: tuple[SheetTool, ...]                # order of first use
    operations: tuple[SheetOperation, ...]      # program order
    reach: Box3 | None                          # union of the operations' reach
    keep_clear: Box3 | None                     # reach grown by the margin (REQ-SHT-012, AQ-056)
    holds_below_mm: float | None                # REQ-SHT-012: the stock gripped only below this
    rapid_floor_mm: float                       # the lowest h_c (REQ-SHT-013)
    reaches_stock_bottom: bool                  # REQ-SHT-014

def make_setup_sheet(job: JobData, cl: ClData, part: CurveRows, files: SheetFiles,
                     ctx: Context) -> SetupSheet: ...
def render_html(sheet: SetupSheet) -> str: ...
```

- Preconditions (programming errors in `job`, refused with `ValueError` naming the field, DEC-SHT-004): `job` is a value returned by `model.check_job`, `cl` one returned by `cl.make_cl_data` from operations `toolpath` linked, and they describe the same setup (REQ-SHT-001, 002, 011).
- `make_setup_sheet` returns values as computed, unrounded; `render_html` rounds for display (REQ-SHT-017). Tests check the values of `SetupSheet`, and that the HTML holds them as printed (Test plan).
- Neither function writes a file, reads a clock or polls `ctx.cancel` (short and vectorised, as `cl`, DEC-CL-002; DEC-SHT-005).

## Requirements

Move starts as in `cl` (Public interface): move 0 has no start, move 1 starts at (unknown, unknown, z of move 0), every later move at the previous move's end. A move "along Z alone" has a known start whose x and y equal its end's. All comparisons and "same XY" are exact, with +0.0 equal to −0.0 (DEC-CL-004); the first value met is the one kept and printed. Decisions use comparisons, sums and products only, no trigonometry and no floating-point NumPy reduction other than `min` and `max` (D-055 tier 1, as toolpath REQ-TP-014); `sqrt` only for printed distances and u.

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-SHT-001 | IF the record's work offset differs from the setup's, the record's operations are not the setup's operations by name in the same order, or an operation's header names another tool, point number, axial offset a or spindle speed than the job's operation and tool, THEN `make_setup_sheet` SHALL raise `ValueError` naming the operation and the field (ours, DEC-SHT-004: the sheet must describe the program that was written). | | Draft |
| REQ-SHT-002 | THE sheet SHALL hold the program's name and number, the NCX file, the compiled files, the machine file, the job file and the part file, by file name only; IF a name is empty or holds `/` or `\`, the program number is below 1, or there is no compiled file, THEN `make_setup_sheet` SHALL raise `ValueError` (ours, DEC-SHT-006: no folder of the programmer's computer on a sheet that leaves it, the same bytes on every computer, REQ-SHT-019; a sheet only for a program that compiled, AQ-058). | | Draft |
| REQ-SHT-003 | THE rendered sheet SHALL begin with the line "Not yet run on a machine: dry run first, with this sheet in hand." (AQ-035; plan 0007, step 8; AQ-056 item 5). | | Draft |
| REQ-SHT-004 | THE rendered sheet SHALL hold empty fields to fill in by hand for the material, the programmer and the date (Project Spike feature map, section 8: header fields the job does not hold yet; AQ-056 item 3; DEC-SHT-007: no clock, REQ-SHT-019). | | Draft |
| REQ-SHT-005 | THE sheet SHALL hold the part's box in XY, the union of `row_boxes` over the contour's rows, and its size in X and Y (feature map, section 8, the header's part). | | Draft |
| REQ-SHT-006 | THE sheet SHALL state the work offset as its index n with the NCX word `ORIGIN=n`, the datum as the drawing's origin (DEC-MDL-002: the drawing's frame is the work frame), and the stock box's six faces as coordinates in that frame (AQ-035; checklist item 2; the controller's own name for n is NCXchange's, D-148, research 27 trap 7, RR-023, AQ-056 item 2). | | Draft |
| REQ-SHT-007 | THE sheet SHALL state the blank as the stock box and, while `ncx` writes no stock word, say that the program defines no blank, so the blank is entered by hand for the control's test graphics (AQ-010; research 27: NCX has no stock word yet, D-080). | | Draft |
| REQ-SHT-008 | THE sheet SHALL list every tool an operation uses, once, in the order of first use, with its T number, its type (flat end mill), diameter, flute length and every measurement point an operation uses (k ascending) with a, r and where it lies: "at the tip, on the axis" for a = 0 and r = 0, "on the axis, a mm above the tip" for a > 0 and r = 0, "a mm above the tip, at radius r" for r > 0; that the length is measured to that point and r is the value for the radius register, which this program does not apply (no radius compensation, `cl` DEC-CL-003); and that the NC program holds neither the diameter nor the point, so a wrong tool or a length measured elsewhere cuts a wrong part with no message (D-151, D-154; AQ-035 item 7; model, Example parts: a radius typed as the diameter). WHERE an operation's a > 0, THE sheet SHALL say that every Z of the program is output a above the tip, while the sheet's heights are the tip's (REQ-MDL-006; D-154). | | Draft |
| REQ-SHT-009 | THE sheet SHALL list the operations in program order, each with its name, strategy, tool and point, spindle speed (clockwise), coolant on, tol, its feed classes by name and value in the header's order, h_c, h_r and the lowest end of any of its moves (research 26 subset: spindle CW and coolant on hold for every operation, DEC-CL-003). | | Draft |
| REQ-SHT-010 | THE sheet SHALL give for each operation its approach points: the end XY of every RAPID that ends below h_c, distinct by XY, in the order of first occurrence; for each, the number of such RAPIDs ending there (descents), the lowest end among them (rapid to), the lowest end of the moves along Z alone ending there, and the distinct feed values of the LINEs along Z alone ending there, in order of first use (research 10, Method 2: the descent beside the stock; AQ-021; AQ-035 item 1). | | Draft |
| REQ-SHT-011 | WHERE an approach point's lowest end lies below the stock top, THE sheet SHALL give the side of the stock box it lies off (the face whose outward half-space alone holds it, or the corner), its distance in XY from the stock box and its gap, that distance minus R, and say: "The tool comes down here from Z h_c to Z <lowest> at F <feeds>, <distance> mm off the stock's <side> face: nothing may stand here; in a vice this is often inside the jaw's footprint. A blank standing out more than <gap> mm beyond the stock box on this side is plunged into." IF the point lies within R of the stock box, decided by toolpath REQ-TP-012's expression, THEN `make_setup_sheet` SHALL raise `ValueError` naming the operation and the point (AQ-015 item 4 (a), AQ-021, AQ-035 items 1 and 3; toolpath refuses such a descent, so it is a producer's bug). | | Draft |
| REQ-SHT-012 | THE sheet SHALL give for each operation the region the tool reaches below h_c: the XY box of the tool centre over every move whose end lies below h_c or whose known start does (line and rapid ends and starts, the arc box of geometry2d REQ-G2D-214 for an ARC), grown by R on each side, from the lowest move end up to h_c, or none where no move goes below h_c; and for the setup the union of these boxes, said to be where the tool's edge comes. It SHALL give the setup's keep-clear box, the reach grown by 5 mm in X and Y (Peter's margin, provisional until AQ-056 item 1 is answered: AQ-035 item 2's band of 15 mm round the part is the tool's edge, 10 mm off it, plus 5 mm), and say that no clamp, jaw or vice part may stand inside it or on its boundary; and WHERE the setup's reach covers the stock box in XY, that the stock is held from below or gripped only below the reach's bottom (research 10, trap 1; AQ-015 item 1 (a); AQ-016 item 4; AQ-035 item 2; AQ-056 item 1; DEC-SHT-002). | | Draft |
| REQ-SHT-013 | THE sheet SHALL say that everything must stay below the lowest h_c of the operations anywhere the tool travels at rapid, the travel from the tool-change position to the first approach point included (research 10, Method 1 and trap 1; AQ-015 item 1 (a)). | | Draft |
| REQ-SHT-014 | WHERE the lowest end of any move is at or below the stock bottom, THE sheet SHALL say that the tool reaches the stock bottom, that whatever lies under the stock inside the reach of REQ-SHT-012 is cut, and that material may be cut free (AQ-035 item 4; AQ-021: equal is allowed). | | Draft |
| REQ-SHT-015 | THE sheet SHALL give for each operation a witness mark wherever a CUT follows a LINE of role APPROACH whose XY changes: the CUT's start S and S + R·u, u the unit direction of that LINE in XY, on the wall or on the allowance left on it; distinct by S and u, in order of first occurrence, with the number of passes that start there (AQ-016 item 7: no lead arc, a mark at S on every pass; AQ-035 item 6; research 22, Method 5; DEC-SHT-003). | | Draft |
| REQ-SHT-016 | THE sheet SHALL say for the dry run that at the start of each operation the first move is a rapid along Z alone, at the tool-change position, to move 0's Z, then across at that height; that if the machine moves otherwise after the tool change, the run is stopped; and where each operation ends in XY, at h_c (`cl` REQ-CL-006 and 012; research 10, trap 2; AQ-015 item 3 (a); AQ-035 item 8; checklist items 7 and 11). | | Draft |
| REQ-SHT-017 | THE `render_html` function SHALL print every length, feed and speed with at most 3 decimals and no trailing zeros, `.` as the decimal sign, ASCII `-`, never `-0`, rounding the exact binary value of the float64 (Python's `decimal` with `ROUND_FLOOR`, `ROUND_CEILING` or `ROUND_HALF_UP`, never a scaled float). Limits SHALL round toward the safe side: a reach or keep-clear box outward (minimum down, maximum up), its bottom down; the rapid floor of REQ-SHT-013, an approach point's lowest end and an operation's lowest end down; a gap down; the blank limit of REQ-SHT-011 printed as the coordinate itself (the stock face plus or minus the gap) rounded toward the stock. Every other value SHALL round to the nearest 0.001, ties away from zero (ours, DEC-SHT-008: a printed limit is never less safe than the computed one). | | Draft |
| REQ-SHT-018 | THE `render_html` function SHALL return one HTML5 document in English with no script, no external resource and every text escaped, with its sections in this order: the banner of REQ-SHT-003; program and files; hand-fill fields; part, datum and work offset; blank; tools; operations with their approach points and witness marks; reach, rapid floor and the note of REQ-SHT-014; dry run (AQ-055; feature map, section 8, in the slice's subset). | | Draft |
| REQ-SHT-019 | THE `make_setup_sheet` and `render_html` functions SHALL give the same values and the same string for the same inputs on every platform the CI runs, and read no clock, locale or environment (D-055; DEC-SHT-007). | | Draft |

## Invariants

- Every number on the sheet comes from the job, the record, the contour or the file names; the module holds no machine or controller data (D-148). Review.
- The reach of REQ-SHT-012 holds every tool position of the record below h_c grown by R, so a clamp outside it is not touched by the tool's side below h_c (the cylinder of radius R about the centre path). Property test over generated records: every move end and sampled arc point below h_c, grown by R, lies inside the box, within one ulp of the box for arc points (`row_boxes` takes an arc's extremes as C ± r with r from `sqrt`).
- An approach point's gap is the clearance between the tool and the stock box: property test, the point moved toward the box by the gap touches the box grown by R, within 1e-9 mm.
- `make_setup_sheet` does not change its inputs and returns frozen values. Unit test.

## Tolerance budget

None spent. Decisions are exact comparisons (as `cl`, DEC-CL-004) and REQ-TP-012's fixed expression; geometry2d's `row_boxes` decides an arc's extremes by exact signs and places them at C ± r with r rounded (REQ-G2D-214, 245).

## Failure modes and diagnostics

No diagnostics: a job and record that passed `model`, `toolpath` and `cl` always give a sheet. Inputs that break the preconditions are programming errors.

| Situation | Result |
| --- | --- |
| Record and job describe different setups or operations (REQ-SHT-001) | `ValueError` naming the operation and field |
| A file name empty or with a folder, program number below 1, no compiled file (REQ-SHT-002) | `ValueError` naming the field |
| An approach below the stock top within R of the stock box (REQ-SHT-011) | `ValueError` naming the operation and the point |

## Algorithms and design inputs

No algorithms beyond boxes and distances.

| Element | Public source, or own design with date |
| --- | --- |
| What the sheet holds | Project Spike `product/feature-map.md`, section 8 (Peter, 2026-10-03), cut to the slice; AQ-035 notes 1 to 8; D-151, D-154 |
| Approach points and descents | research 10, Method 2; the grouping by XY and moves along Z alone ours, 2026-11-08 |
| Reach below h_c | research 10, trap 1; the box from the record ours, 2026-11-08 (DEC-SHT-002) |
| Keep-clear margin 5 mm | Peter, AQ-035 item 2 (the band's margin over the tool's edge); provisional, AQ-056 item 1 |
| Side, distance and gap at P | research 10, Method 2 and D-079 (the air gap 0.2·R); toolpath REQ-TP-012's expression; computed from the record ours |
| Witness marks | AQ-016 item 7; research 22, Method 5; the rule ours (DEC-SHT-003) |
| Rounding toward the safe side | ours, 2026-11-08 (DEC-SHT-008) |

## Example parts

- The golden job `testdata/zoo/profile-rectangle-fillets/` (T1 D 10, flute 30, the tip; stock X −5 to 105, Y −5 to 65, Z −20 to 0; work offset 1; `PROFILE_1`, h_c 5, h_r 3, three passes to Z −3.333, −6.667, −10, P at X 50, Y −11, S at X 50, Y −5): part box 0 to 100 × 0 to 60; one tool, point 1 "at the tip, on the axis", a 0, r 0; one approach point X 50, Y −11, 3 descents, rapid to Z 3, lowest Z −10, feed 300, side −Y, distance 6, gap 1, the blank limit Y −6; reach about X −10 to 110, Y −16 to 70, Z −10 to 5 (the centre path X −5 to 105, Y −11 to 65, grown by 5; the fillets' vertices may lie up to about 0.0005 mm outside the offset, REQ-PRF-011, so the printed reach may read −10.001: tested with a tolerance on the value and on the printed outward rounding); keep-clear X −15 to 115, Y −21 to 75, Z −10 to 5; the stock held from below or gripped only below Z −10; everything below Z 5 where the tool rapids; the stock bottom not reached (−10 above −20); one witness mark, S X 50, Y −5, contact X 50, Y 0, on 3 passes; the operation ends over X 50, Y −11 at Z 5. AQ-035 item 2's band and AQ-015 item 1 (a)'s figure differ from the reach on every side; the keep-clear box holds both: AQ-056 item 1 shows the numbers.
- The same job with z_bottom −20: the stock bottom reached (REQ-SHT-014).
- A profile whose start is already clear of the stock (strategies/profile REQ-PRF-017, d = 0): P is S, no approach LINE, no witness mark.
- An operation of one RAPID (`cl` accepts it): no approach point, no reach; the setup's reach none if it is the only one (unit case).
- Unit cases only (`ncx` refuses them meanwhile, REQ-NCX-013 and 003): a tool with a second point, a = 3, used by no operation: not listed; used: "on the axis, 3 mm above the tip" and "every Z of the program is output 3 mm above the tip". Two operations with tools D 10 and D 6: two tools in order of first use; the setup's reach the union of two boxes grown by 5 and 3.

## Test plan

- Unit (`tests/setupsheet/unit/`): one test per requirement, tagged with its ID; the example parts; `SetupSheet` values compared with tolerances where computed (distances, gaps, contact points, the golden reach), exactly where copied.
- Property (`tests/setupsheet/property/`): records from `tests/support/cl_strategies.py`: the reach and gap invariants above; the HTML parsed with the standard library's `html.parser` holds every value of the sheet as printed by REQ-SHT-017, the banner first, no `<script>`, no `src=` or `href=` to another resource; the rounding of REQ-SHT-017 against `decimal` on generated floats, ties included.
- Golden: `testdata/zoo/profile-rectangle-fillets/case.json` gains the sheet's values above as data (plan 0009, step 4); no text diff of the HTML (`.claude/rules/tests.md`).

## Performance budget

Under 50 ms for a record of 10 000 moves on the reference machine (vectorised; a sheet is made once per run).

## Size estimate

First count about 260 NLOC (types 50, the computations of REQ-SHT-010 to 016 about 115, the rest of `make_setup_sheet` 30, `render_html` with the rounding 65); by the 1.5 rule about **390 NLOC**, and about 650 lines of tests. Proposed budget 400 (AQ-057).

## Open questions

Box 1 for Peter, each with a recommendation and the safe default taken:

- AQ-055: the format (HTML), the file next to the NC program, English only in the slice.
- AQ-056: what the slice's sheet holds and leaves out of the feature map's row; the reach against the earlier keep-out statements; the work offset as its index; the full-slot note left out.
- AQ-057: a new module `setupsheet` at layer 4, the exact `architecture/modules.yaml` lines, `job`'s budget.
- AQ-058: when `job` writes the sheet: with the compiled files, never an NC program without its sheet.
- AQ-059: what the sheet changes in AQ-035's two "until a setup sheet exists" rules.

Box 3: RR-023 (where the controller's name for the work offset comes from). Box 2 choices: `src/splintercam/setupsheet/DECISIONS.md`.

## Change log

- 2026-11-08: drafted for plan 0009 from AQ-035, AQ-015, AQ-021, AQ-010, D-151, D-154 and the feature map's setup sheet row (lane S, branch `plan0009/setup-sheet-draft`). Revised after the spec review the same day: approach points from the RAPIDs ending below h_c and the moves along Z alone (the first wording gave one descent on the golden job); the approach sentence of AQ-021 with side and distance; the reach may be none; the stock-holding sentence conditional and with both of AQ-015's options; rounding by `decimal` and the blank limit printed as a coordinate; REQ-TP-012's expression for the gap check; tip heights and a > 0; witness marks per S and u with their passes; the dry run's stop and the end point; size 390.

[r10]: ../../../docs/research/10-linking.md
[r22]: ../../../docs/research/22-2d-operations.md
[r26]: ../../../docs/research/26-toolpath-record.md
[r27]: ../../../docs/research/27-machines-and-controllers.md

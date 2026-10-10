---
topic: "26"
title: Toolpath record (CL data)
readiness: L4 for the subset of plan 0007 (below); L3 otherwise
release: "1"
reviewed: 2026-10-11
provenance: public
---

[Index](README.md)

# 26. Toolpath record (CL data)

The neutral record every strategy writes and every consumer reads: linking, optimisation, stock update and simulation, the time estimate, the NCX writer and the golden tests. It is the contract between the planning modules and everything after them, so nobody downstream may have to guess what a move means.

## Scope

- In: the program, setup and operation headers; the move kinds (rapid, line, arc and helix, drilling cycle, dwell); fields per move with units and frame; roles; feed classes; compensation state; source references; numeric rules; the mapping onto NCX; the serialisation for golden files and its comparison rule.
- Out: controller dialects (NCXchange, D-021, D-031); how the CAM calls `ncx` and which machine data it keeps (topic 27); multi-axis orientation, extra axes, spindles and channels (reserved fields only, D-022, D-041); STEP-NC export (not planned; the mapping notes below are kept for later).

## Decisions this topic writes down

D-052 (structure), D-057 (arc form), D-028 (units), D-030 and D-061 (cycles), D-024, D-096 and D-154 (compensation and measurement points), D-155 (point number in NCX), D-056 (control tolerance), D-087 and D-062 (link feed and heights), D-110 (corner limit), D-113 (programmed feed at the tool), D-054 and D-059 (source references), D-045 (slot-through links), D-078 (setups), D-126 (operation order), D-055 (determinism), D-080 (canonical NCX text), D-022 (room for later axes, spindles and channels).

## Inputs and outputs

- Written by every strategy (facing, profile, pocket, chamfer, drilling), then edited by linking (topic 10) and path optimisation (topic 11, the arc fit).
- Read by the linker, the optimiser, the stock update and simulation (topic 08), the time estimate, the NCX writer (topic 27) and the golden tests (topic 24).
- Frame (ours, from the setup's work offset of D-078): every coordinate is in the work frame of its setup. Release 1 is 3-axis; the tool axis is +Z of the work frame. Coordinates give the tip on the tool axis, the true tool (D-154). The NCX writer expresses them in the operation's measurement point: shifted by its axial offset a along the tool axis, and on compensated stretches by its register radius r toward the material (D-151, D-154).
- Units: mm for lengths and radians for angles (D-028); mm/min for feeds, 1/min for spindle speed and s for dwell (ours; every field declares its unit, D-049).
- Numbers: float64, unrounded (D-052). Rounding to a machine's decimals happens only in NCXchange (D-148, D-149); the NCX itself is written at one fixed resolution, the same for every machine.

## The subset plan 0007 uses

Plan 0007 (the first NC program) writes a small part of this record. It is L4: every field below is decided and checked against NCXchange.

- One program, one setup: `work_offset` 1, `placement` the identity (the part's DXF coordinates are the work frame).
- One operation header: `name` (letters, digits and underscores, below), `tool` (number), the point at the tip (k = 1, a = 0, r = 0, D-154), `spindle` CW, `coolant` on, `comp_mode` CENTER, the feed classes `cut` and `plunge` (ours), `clearance_height`, `plane` XY. `control_tol` is not written in plan 0007: `TOLERANCE` without `TOLERANCE:ROTARY` is an error on the iTNC 530 and 840D sl files (trap 11), and the default for `TOLERANCE:ROTARY` is still open (NCXchange D151); the control's own setting applies (ours, for plan 0007 only).
- Moves: RAPID, LINE and planar ARC in XY with |sweep| ≤ 2π; no helices, cycles or dwells. Roles: LINK for the rapids, APPROACH and RETRACT at the approach point, CUT on the contour (topics 10 and 22).
- NCX: as in the mapping below, with the arc in the centre form (`ARC=CW X Y CENTER:X CENTER:Y`), and `TOOL=n OFFSET:LEN=n RPM=s` in one block.

### Checked against NCXchange on 2026-10-11

Our build of NCXchange `main` at commit f74559c (macOS, .NET 10) compiled plan 0007's sample program (the outside profile of topic 22, test 1: rapids, lines, clockwise arcs in the centre form, one tool, one origin, coolant) for `fanuc-mill-30i`, `heidenhain-itnc530` and `siemens-840dsl-mill`: `ncx format --check` passed, and `ncx check --strict` and `ncx compile --strict` exited 0 on all three, under three conditions:

1. **`TOOL=n` carries `OFFSET:LEN=n`.** Without it the Fanuc output has `T1 M6` but no `G43 H1`: the control never applies the tool length, and the tip runs one tool length below the programmed Z. That is a crash, not a warning. Heidenhain applies the length with `TOOL CALL` and Siemens with `D1` either way. Until the neutral point words of D-155 exist in NCX (R1-11), the writer always emits `OFFSET:LEN` with the tool number in the tool-change block (ours; reported to NCXchange, T-039).
2. **The program `NAME` uses letters, digits and underscores only.** A space gives `CMP501` on Siemens, which fails `--strict`.
3. **Coordinates with more decimals than the machine file's `[format]` decimals** give one `CMP020` warning per value (here X95.1234567 written as X95.123), which fails `--strict` on all three. NCXchange answered this on 2026-10-07 (its D363: rounding to the machine's decimals is silent, D-149) but has not implemented it yet. Until it does, `compile` runs without `--strict` and the test accepts `CMP020` and nothing else; `check --strict` already passes, because `check` does not round.

## Method

### Structure

A program holds setups in order; a setup holds operations in the user's order (D-126); an operation is a header above a list of moves (D-052). In the public ISO 14649 model tool, technology and machine functions sit on the operation, and a single toolpath may override technology and machine functions (SRC-113); our header plays the same role.

**Setup** (D-078):

| Field | Type and unit | Meaning |
| --- | --- | --- |
| `setup_id` | int64 | stable ID |
| `work_offset` | integer ≥ 1 | datum index; NCX `ORIGIN` (the codes per controller are in topic 27) |
| `placement` | 4×4 transform, mm | part model to work frame |
| `stock` | reference | the setup's stock (topic 08) |
| `fixtures` | references | keep-out solids (D-078) |
| `channel` | reserved | empty in release 1; room for several channels (D-022) |

**Operation header** (D-052):

| Field | Type and unit | Meaning | NCX |
| --- | --- | --- | --- |
| `op_id` | int64 | stable ID | none |
| `name` | text | the user's name | `SECTION="…"` |
| `tool` | tool number, snapshot ID | tool in the spindle; the snapshot ID names the copy in the job, with its measurement points (D-154) | `TOOL=` |
| `point` | point number k, axial offset a (mm along the axis from the tip), register radius r (mm) | the measurement point the operation is written in (D-154); k is neutral, the machine file maps it to registers (D-155) | the point words requested from NCXchange (R1-11, T-039) |
| `spindle` | 1/min, CW or CCW | speed and direction | `RPM=`, `SPINDLE=` |
| `spindle_role` | reserved | empty in release 1; room for several spindles (D-022) | `RPM:<role>=` later |
| `coolant` | channel, on or off | | `COOLANT=`, `COOLANT:<channel>=` |
| `tol` | mm | operation tolerance (D-029, D-056) | none |
| `control_tol` | mm, FINISH or ROUGH | 0.5·tol (D-056); the mode is FINISH for finishing and ROUGH for roughing operations (ours, after D-029's split) | `TOLERANCE=`, `TOLERANCE_MODE=`, `TOLERANCE:ROTARY=` (below) |
| `comp_mode` | CENTER or CONTROL | D-024, D-154: the record's path is always the tool centre; CONTROL switches control compensation on, and the writer shifts the compensated stretches toward the material by the point's r, so the register holds r plus wear (wear mode is a point with r = 0) | `COMP=` and the point words |
| `feed_classes` | class name → mm/min | resolved feeds of the classes this operation uses | `F=` |
| `clearance_height` | mm, work frame | D-062: 5 mm over stock or clamps; used at the start and end of the operation and between operations | none |
| `plane` | XY in release 1 | working plane | `WORKPLANE=` |
| `source` | strategy name, parameter hash | reproducibility | none |

**Move**:

| Field | Type and unit | Kinds | Meaning |
| --- | --- | --- | --- |
| `kind` | RAPID, LINE, ARC, CYCLE, DWELL | all | |
| `end` | x, y, z, float64 mm | RAPID, LINE, ARC | end point; a move starts where the previous one ended |
| `centre` | x, y, z, float64 mm | ARC | absolute centre; its coordinate along the plane normal equals the start's |
| `plane` | XY, ZX, YZ | ARC | the arc's plane; its normal is the helix axis |
| `sweep` | float64 rad, signed | ARC | signed sweep (D-057), positive counter-clockwise seen from the positive end of the plane normal (ours); a full circle is ±2π (Q-035 answer); beyond 2π only for helices (ours) |
| `role` | CUT, PLUNGE, APPROACH, RETRACT, LINK, AIR | RAPID, LINE, ARC | what the move is for (table below) |
| `feed_class` | class name | LINE, ARC | side, heavy, slot (D-089), link (D-087); cut and plunge are ours |
| `feed` | float64 mm/min | LINE, ARC | tool-centre feed as programmed: the class value, or lower where a limit applies (D-110); the time estimate uses it (D-113) |
| `comp` | OFF, LEFT, RIGHT | LINE, ARC | control compensation state; not OFF only in CONTROL mode (D-024, D-154) |
| `link_height` | mm, work frame | RAPID, and LINE with role LINK | the D-062 retract height of the link the move belongs to, so the height rules can be checked from the record (ours) |
| `source` | face key (D-054), edge ID (D-059), or none | CUT, PLUNGE | what the move machines |
| `cycle` | cycle record | CYCLE | below |
| `dwell` | s | DWELL | |
| `tool_axis`, `axes` | reserved | none in release 1 | tool orientation and extra axes (C, Y) for later releases (D-022, D-041) |

**Roles.** They follow the toolpath types of ISO 14649 (approach, lift, connect, non-contact, contact; SRC-113) and add the two distinctions our linker and simulation need:

| Role | ISO 14649 type | Meaning | May the linker replace it? (ours) |
| --- | --- | --- | --- |
| CUT | contact | removes material; includes slot-through links between pocket branches (D-045), at the slot feed class | no |
| PLUNGE | contact | ramp, helix or straight entry into material | no |
| APPROACH | approach | lead-in, from the air to the cut | no |
| RETRACT | lift | lead-out, from the cut to the air | no |
| LINK | connect | between two passes; stays down only where the tool stays in air in every stock layer (D-062) | yes |
| AIR | non-contact | known to be in air | yes |

In the AP238 version of the model a toolpath carries a priority, required or suggested (SRC-113); our reading is that a suggested one may be replaced by a capable control. The last column is our equivalent inside the CAM.

**Arcs and helices.** Take the plane's axes (u, v) and its normal n: XY gives (x, y) and z; ZX gives (z, x) and y; YZ gives (y, z) and x, all right-handed. From the start S, the centre C and the sweep φ, the end is E_uv = C_uv + Rot(φ)·(S_uv − C_uv), and E_n = S_n + travel, where travel = E_n − S_n. The record stores E explicitly, so consumers never recompute it, and keeps |S_uv − C_uv| = |E_uv − C_uv| within eps_len (ours, with eps_len from the Q-034 answer). A helix has travel ≠ 0; its pitch is travel·2π/|φ|, and its feed is measured along the 3D path (D-096; LinuxCNC's canonical ARC_FEED says the same, SRC-115). Our reading of the public records: APT CLDATA writes an arc as a circle record (centre, axis, radius) followed by points, with the direction implicit (SRC-114); the AP238 samples use a trimmed circle with Cartesian end points and a direction flag (SRC-113); LinuxCNC passes end point, centre and a signed turn count (SRC-115). The signed sweep carries all of it in one number and maps onto the NCX `ANGLE` form (SRC-112).

**Drilling cycles** (D-030, D-061). A cycle is a record, not expanded moves. Inside the CAM only the simulation expands it; on output NCXchange writes the controller's native cycle, and under D-030 it would expand the cycle for a machine that has none, which it cannot do yet (T-039; release 1 on the three shipped mills does not need it).

| Field | Type and unit | Meaning |
| --- | --- | --- |
| `type` | DRILL, DRILL_DWELL, PECK, CHIP_BREAK, TAP (release 1) | spot drilling is DRILL or DRILL_DWELL with a spot drill (ours) |
| `surface`, `r_plane`, `depth` | mm, absolute along the tool axis in the work frame | hole top; the R plane where feeding starts (NCX `CLEARANCE`, not D-062's clearance height); bottom |
| `safe` | mm, optional | the higher retract level |
| `retract_to` | R_PLANE or SAFE | where the tool goes after each hole (G99 or G98); SAFE needs `safe` (NCXchange D188). Proposal (ours): the rapid in the plane to the next hole is a link under D-062, so R_PLANE only where `r_plane` is at or above the D-062 retract height for that move; otherwise SAFE, with `safe` at or above it |
| `peck` | mm | PECK and CHIP_BREAK: constant peck (D-061) |
| `dwell` | s | DRILL_DWELL |
| `pitch` | mm | TAP |
| `rigid` | yes or no | TAP: rigid or floating tapping (NCX TAP is rigid on Heidenhain and Siemens, floating on the shipped Fanuc file unless `FUNC:RIGID_TAP=ON`, SRC-112) |
| `feed` | mm/min | feed into the hole; not written for TAP, where pitch and speed set it |
| `points` | list of x, y in mm | hole positions in call order (D-098) |

Values the controls keep themselves are machine-file keys, not record fields (D-061, topic 27). The simulation expands each cycle per controller with those values: the Fanuc G73 retract and G83 clearance, the Siemens CYCLE83 retract, and the Heidenhain Q256 and Q208 that NCXchange writes today. Where a value is missing it falls back to the generic model of the NCX virtual machine and says so. That model (rapid in the plane to the point, rapid to the R plane, feed to depth, retract; PECK back to the R plane between pecks; CHIP_BREAK staying in the hole) is itself provisional in NCXchange, pending its question D190 (SRC-112).

**Links and heights.** Each link has its own retract height: 3 mm over the material under the rapid path grown by R + 0.2R (D-062). A link runs as RAPID at or above that height ("G0 only at or above a per-link retract height", Q-040 answer), and as LINE moves with role LINK at the link feed class below it (D-087). We read D-087's "safe plane" as this per-link retract height, which makes D-062 and D-087 agree (ours). The move carries the height in `link_height`. The clearance height of D-062 (5 mm over stock or clamps) is kept in the header for the start and end of the operation and for moves between operations. The record never uses NCX's `RETRACT` word; it writes the heights explicitly (the word fails on the shipped Fanuc and Siemens mill files, SRC-112).

### Mapping onto NCX

The NCX writer (topic 27) turns the record into the canonical NCX text file (D-080). Facts from the NCX specification and compilers at commit 9a1fb19 (SRC-112):

| Record | NCX |
| --- | --- |
| program start | `FILE=BEGIN NCX=1`, `PROGRAM=BEGIN NAME="…" NUMBER=n`, then a complete header `FEED_MODE=PER_MIN COMP=OFF UNITS=MM WORKPLANE=XY CYCLE=OFF` (writers must emit a complete header; Fanuc needs `NUMBER`, `CMP300`; motion before `UNITS` is `VM200`) |
| setup | `ORIGIN=n` |
| operation header | `SECTION="name"`; tool change `TOOL=n RPM=s SPINDLE=CW` with the operation's point words in one block (D-155, R1-11); a change of point without a tool change goes with the operation's first move, at clearance height (D-154) (Heidenhain takes the speed from `TOOL CALL`); `COOLANT=ON`; `TOLERANCE=… TOLERANCE_MODE=…` and, while NCXchange D151 is open, `TOLERANCE:ROTARY=…` from a declared parameter stored in radians and shown in degrees (D-028; default still open, T-039) |
| control compensation | the point words and a `COMMENT="…"` at the start of the operation naming the point and what its radius register must hold: r plus wear, only wear when r = 0 (below) |
| RAPID | `RAPID X Y Z`, never with `F` (`VM440`) |
| LINE | `LINE X Y Z`, `F=` only where the feed changes (modal) |
| planar ARC | `ARC=CCW` or `ARC=CW` with the end point and the absolute centre `CENTER:X CENTER:Y`; direction from the sign of the sweep (CCW for positive about +Z) |
| full circle | centre form with end = start; the `R` form cannot give a full circle (`VM232`) |
| helix | proposal (ours): `ARC=CCW IZ=… CENTER:X=… CENTER:Y=… ANGLE=…` with the travel incremental and the sweep in degrees. It avoids NCXchange question D268, where a Heidenhain helix of one turn or less is written as `C`/`CR` with Z, which the control may refuse. The compilers then write `CP IPA` on Heidenhain; `AR=` below one turn and `TURN=` from one turn on for Siemens; one `G2`/`G3` below a turn and full turns plus a rest beyond on Fanuc. For `CP IPA` and `AR=` the control computes the end point from the rounded start and centre; for Siemens `TURN=` and the Fanuc turns NCXchange computes it and writes it rounded (Q-131) |
| comp change | `COMP=LEFT`, `RIGHT` or `OFF` on the straight move in the plane before the lead-in arc and after the lead-out arc (D-096), and that straight move is longer than the largest wear value (Q-079 answer); NCX applies it from that block's motion; `COMP` in an ARC block is `VM460`; Heidenhain needs it on an `L` block (`CMP115`) |
| CYCLE | `CYCLE=<type> SURFACE= CLEARANCE= DEPTH= [SAFE=] CYCLE_RETRACT= [PECK=] [CYCLE_DWELL=] [PITCH=] [CYCLE_F=]` with `CLEARANCE` from `r_plane`, then `CYCLE_CALL X Y` per point, then `CYCLE=OFF`; `SURFACE` always (Heidenhain `CMP104`); for a rigid TAP on a machine whose file has a `RIGID_TAP` entry under `[func]` (the shipped Fanuc file), `FUNC:RIGID_TAP=ON`: machine-specific output knowledge in the CAM, a temporary workaround against D-031 until NCX has a neutral rigid-tap word (T-039) |
| DWELL | `DWELL=s` |
| program end | `PROGRAM=END`, `FILE=END` |

**Number printer** (ours): each value is first rounded, half away from zero, to the fixed NCX resolution of D-149 (0.000001 mm or 0.0000001 inch for lengths, 0.0000001° for angles), the same for every machine, then printed with the shortest digits that read back to the rounded value, written positionally (no exponent), with at least one digit on each side of the point; NumPy's `format_float_positional` with `unique=True` and `trim='0'` does this, after mapping −0.0 to 0.0, which it would print with a sign. NCX accepts integers and decimals with digits on both sides of the point, no exponent and no plus sign (SRC-112). The writer then emits the canonical layout, or pipes its text through `ncx format`, so that `ncx format --check` passes: it checks word order, spacing and the comment column, not only the words. Radians become degrees in `ANGLE` and `TOLERANCE:ROTARY` (D-028).

**Control compensation and measurement points** (D-024, D-154). The path in the record is the tool centre at the tip. The writer shifts every coordinate by the point's a along the tool axis, cycle heights included and increments not. With `COMP` on, the control shifts the path in the plane by whatever its radius register holds, so the writer first shifts the compensated stretches toward the material by the point's r, and the register must hold r plus wear. Wear mode is a point with r = 0: the register holds only the wear, and with the tool radius in it the part is cut undersize by R. A point with r equal to the cutting radius is classic compensation in the control. Example (Peter): a mill of R 10 with a 2 mm corner radius, measured at the end of its flat bottom (r = 8), cuts a wall at X0 from the +X side with the written path at X2. The written path is valid only where r is not larger than the radius that cuts, the straight switch move is longer than r plus the largest wear, and every arc on which the control offsets toward its centre has a radius larger than r plus the largest wear (D-154); the writer checks this with a model of the control's compensation (topic 10). On Siemens one D holds length and radius together, which fits one point: the D of point k carries its length and r (D-155). The program says in a comment what each register must hold, and the setup sheet repeats it with a and r.

### Serialisation for golden files

Proposal (ours; D-055 fixes the comparison tiers, the format is open to review):

- JSON Lines: one header line (format version, units), then one line per setup, operation header and move, in program order; keys sorted.
- Floats as the shortest text that reads back to the same float64 (Python `repr`, which JSON allows even in exponent form), so one double always gives the same bytes.
- Per platform (tier 2): byte comparison of the file.
- Across platforms (tier 3): counts, kinds, roles, feed classes, compensation states, sources and cycle types exact; each end point and cycle level within 0.001 mm; fitted arcs within their fit band (Q-033 answer), other arcs through their end points and the swept path; feeds, dwell, peck and pitch within a relative 1e-9 (ours); the swept path within 0.001 mm Hausdorff on sampled geometry. The per-move checks matter: a path can be close in Hausdorff distance and still be reversed or reordered, which only an ordered measure (Fréchet) or a per-move check sees. The Hausdorff distance is the measure the smoothing literature uses for path deviation (SRC-051).
- NCX text is never compared across platforms (D-055). LinuxCNC's test layout (an expected file compared exactly, or a checker program for tolerance comparisons) fits this split (SRC-115).

## Parameters

| Parameter | Unit | Default | Range | Source |
| --- | --- | --- | --- | --- |
| Arc radius consistency | mm | eps_len = 1e-6 | declared | Q-034 answer (logged as D-056) |
| Control tolerance | mm | 0.5·tol | from tol | D-056 |
| Clearance height | mm | 5 over stock or clamps | declared | D-062 |
| Rotary tolerance for `TOLERANCE:ROTARY` | rad, shown in degrees | open | declared | NCXchange D151 (T-039) |
| Largest wear value | mm | open (shop template) | declared | Q-079 answer (logged as D-096); the switch move is longer than r plus this value (D-154) |
| Golden geometry tolerance across platforms | mm | 0.001 | fixed | D-055 |
| Program number | none | from the job | per machine (topic 27) | NCX `NUMBER`; Fanuc needs one (SRC-112) |

## Traps

1. **Rounding and warnings.** NCXchange rounds each address that has a `[format] decimals` key (X, Y, Z, F and S in the shipped mills) and warns `CMP020` for every value with more decimals; `--strict` then fails. Angles without a key (Heidenhain `IPA`, Siemens `AR=`) are written as given, so an unrounded sweep reaches the program with about 14 decimals (Q-131). Settled by D-149: NCXchange rounds as normal behaviour, checked against the operation's rounding allowance, without a warning per value; until it does, `--strict` stays off (T-039).
2. **Number syntax.** `1e-5`, `.5`, `5.` and `+5` are not valid NCX numbers (SRC-112); Python's `repr` gives exponent forms, so NCX needs its own printer.
3. **Register contents.** The radius register must hold the point's r plus wear, only wear when r = 0; with the tool radius in a wear-mode register the part is cut undersize by R. A tool measured at another point than the program's is wrong by the difference, along the axis and in the plane (D-154).
4. **Heidenhain helices.** One turn or less comes out as `C`/`CR` with Z (NCXchange D268); write helices in the `ANGLE` form with incremental travel.
5. **Computed end points.** For Heidenhain `CP IPA` and Siemens `AR=` the control computes the end from the rounded start and centre; read-back can miss the record by more than 0.001 mm (Q-131, topic 27). Settled by D-149: NCXchange computes what the control will compute and keeps it within half an output step, or reports it (T-039).
6. **Heidenhain plane changes** need a tool change in the same block (`CMP110`), so arcs in ZX or YZ within one tool do not compile for Heidenhain today. Release 1 uses XY only.
7. **Heidenhain cycles** need `SURFACE` (`CMP104`); boring has no signature yet (`CMP103`; not in release 1).
8. **Siemens peck drilling** fails: `PECK` on `CYCLE83` is `CMP571` until NCXchange D181 is answered. Release 1 peck drilling on Siemens depends on it (T-039, RK-010).
9. **Rigid tapping.** NCX TAP is rigid on Heidenhain and Siemens, but floating on the shipped Fanuc file unless the program switches the named function on (SRC-112, T-039).
10. **Fanuc SAFE level.** A `SAFE` level other than the level before the cycle is `CMP382` on Fanuc (SRC-112).
11. **Tolerance words.** `TOLERANCE` without `TOLERANCE:ROTARY` is an error on the shipped iTNC 530 and 840D sl files (NCXchange D151); the writer adds it while D151 is open.
12. **Fanuc tolerance value.** The shipped Fanuc file writes `G5.1 Q1` without the value; D-056's per-operation control share may not reach the machine (A-061: NCXchange's question under D-148, T-039).
13. **Datum numbers.** `ORIGIN=5` is G58 on Fanuc and G505 on Siemens: the number is an index, not a G code (SRC-112).
14. **Feed units.** Store mm/min with the unit declared. A record in mm/s once made a post write feeds 60 times too small (SRC-117).
15. **Direction.** The sweep sign is about the plane normal; NCX CW and CCW are seen looking against the tool axis (G02/G03 likewise, Altintas 2012, p. 195). In ZX the axes order is (z, x), as in G18 (later releases).
16. **Hausdorff alone** misses reversed or reordered moves (above).
17. **ISO 14649 default units** are degrees and m/s; any STEP-NC export must declare units (SRC-113).
18. **Plugins.** `ncx` loads every DLL in `plugins/` of its working directory; call it in a directory the CAM controls (SRC-112).

## Tests

Invariants for topic 24:

1. Arc consistency: start and end radius equal within eps_len; the arc length between the end and the point the sweep gives from the start is at most eps_len; |sweep| ≤ 2π unless travel ≠ 0.
2. Feeds: every LINE and ARC has a feed > 0 and a class; no RAPID has one.
3. Compensation: `comp` changes only on the straight move in the plane before the lead-in arc or after the lead-out arc (D-096), never on an ARC, and that move is longer than the point's r plus the largest wear value (Q-079 answer, D-154); `comp` is OFF everywhere in CENTER mode; in CONTROL mode the program carries the register comment (D-024, D-154).
4. Cycles: depth < surface ≤ r_plane ≤ safe along the tool axis for downward drilling; `safe` present when `retract_to` is SAFE; peck > 0 for PECK and CHIP_BREAK; pitch > 0 and `rigid` set for TAP; at least one point.
5. Links: every RAPID in the plane runs at or above its `link_height`, and every LINE with role LINK below it (D-062, D-087); cycles with R_PLANE have `r_plane` at or above the link height of their hole-to-hole moves.
6. Printer: sweeps and coordinates that are not round (for example 1 rad) print without exponent; after rounding to the fixed NCX resolution, every printed value reads back to the rounded value, and the NCX text is the same for every machine (D-148, D-149).
7. NCX level: the written file passes `ncx format --check` and `ncx check --machine` without ERROR. Compilation is tested separately: `ncx compile` for each of the three shipped mill files, where the only allowed ERRORs are the known NCXchange gaps (Siemens `CMP571` for PECK and CHIP_BREAK while D181 is open) and `CMP020` warnings until Q-131 is answered.
8. Record against NCX: `ncx trace` of the NCX file reproduces every written end point exactly as printed, and with the operation's point removed (a along the axis, r on compensated stretches; D-155) the record's tip path; the compiled round trip of D-063 is in topic 27.
9. Determinism (D-055): identical JSON Lines bytes per platform and thread count; tier 3 rules across platforms.

Reference case (SRC-112): from X10 Y0 Z0 a counter-clockwise helix about (0, 0) with 900° of sweep and 5 mm of downward travel. The Fanuc compiler test shows two full turns ending at Z−2 and Z−4 and a half turn ending at X−10 Y0 Z−5. By the compiler rule (not a test), Siemens writes one `G3` with `TURN=2`. Our record for it: one ARC with sweep 5π, travel −5 mm, end (−10, 0, −5).
10. Measurement points (D-154): the same operation with a bull-nose tool (corner radius 1 mm) at a point with a = 0 and at one with a = 1 mm writes every Z exactly 1 mm higher in the second case, cycle heights included and increments unchanged; X and Y are unchanged where `comp` is OFF; the record is identical in both cases.
11. Drill at its shoulder (D-154, topic 20): D = 10 mm, σ = 118°, the point at the start of the full diameter, a = 5/tan 59° ≈ 3.0043 mm. A hole 20 mm deep to the full diameter sends the tip to about −23.0043; the written `DEPTH` is −20 within the NCX resolution, `SURFACE`, `CLEARANCE` and `SAFE` lie a above the tip values, and `PECK` is unchanged.
12. Point radius in the plane: a mill of R 10 with a 2 mm corner radius at a point with r = 8; a straight wall at X = 0 with the material at X < 0 and no allowance. The record's centre path runs at X = 10, the written path at X = 2 with `COMP` on the side away from the material, and a model of the control's compensation with the register at 8 gives back X = 10.
13. Radius too large: a profile around a convex corner rounded to 1 mm, with a tool of R 3 and a point of r = 5, is reported and not written; the control would cut about 0.41 mm into the corner.
14. Change of point: two operations of tool 5 without a tool change, the first at point 1 (a = 0), the second at point 2 (a = 2 mm). The second operation's point words come with its first move, at clearance height; the tip height is the same on both sides of the change, and the written Z changes by exactly 2 mm.

## Libraries

- NCXchange `ncx` (MIT), pinned at commit 9a1fb19 for the spike; a release tag later (T-039).
- Python standard library `json` for the golden files; NumPy for the NCX number printer.
- OpenCAMLib (LGPL) is not used for the record; its CL point, which points to its contact point and contact type, is only the precedent for our `source` field (SRC-116, D-036).

## Sources

- SRC-112: NCXchange repository at commit 9a1fb19: language spec, VM spec, controller mapping, compilers, diagnostics, tests.
- SRC-113: ISO 14649 and ISO 10303-238 toolpath model from public pages and samples.
- SRC-114: APT CLDATA, ISO 3592 and ISO 4343 public samples.
- SRC-115: NIST RS274NGC version 3 and LinuxCNC documentation.
- SRC-116: OpenCAMLib API.
- SRC-117: FreeCAD CAM scripting documentation and tracker 3343.
- SRC-119: Altintas 2012, *Manufacturing Automation*, 2nd ed., section 5.3.2, pp. 206–211: APT statements and the CL file as records of class (2000 post command, 5000 motion), code and data; feed, coolant and tool are modal records in the motion stream; no arc record is shown, so it neither confirms nor contradicts the SRC-114 reading of arcs.
- SRC-051: Zhong et al. 2020, review of toolpath interpolation and smoothing (Hausdorff distance as the deviation measure).
- The Q-030 brief: [reviews/2026-09-28-question-briefs/Q-030.md](../reviews/2026-09-28-question-briefs/Q-030.md).

## Open items

Readiness **L3**, needed for release **1**. Raised from L0 on 2026-10-01: structure decided (D-052); every field sourced or marked as ours; the NCX mapping checked against NCXchange's specification, compilers and tests; traps and invariants listed; an adversarial review of the same day is folded in. Not L4: the NCX mapping depends on NCXchange items in T-039, among them the rounding of D-149; Q-131 and Q-132 are answered (D-146, D-149). Levels are defined in [AGENTS.md](../AGENTS.md#readiness-levels).

### Registered questions and assumptions

<!-- open-items:begin -->
_Generated by `tools/spike.py status` from QUESTIONS.md and ASSUMPTIONS.md. Do not edit by hand._

- None registered.
<!-- open-items:end -->

### Missing before a spec

- [x] Field list per move type with units and frame (D-052; above).
- [x] Arc and helix representation in any plane, consistent with the 2D arc type (D-057; above).
- [x] Cycle records versus expanded moves (D-030, D-061; above).
- [x] Serialisation format for golden files and its comparison rule (D-055; format proposed above).
- [x] Public sources (SRC-112 to SRC-117).
- [x] Output rounding, including angles and control-computed end points (Q-131). Done 2026-10-01 (D-147, superseded by D-149: NCXchange rounds).
- [x] The smallest supported tolerance, and inch output (Q-132). Done 2026-10-01 (D-146).
- [x] Which point on the tool axis the record's coordinates give. Done 2026-10-01 (D-151): the tip plus a per-tool gauge offset.
- [x] Several measurement points per tool, chosen per operation, with an axial offset and a register radius. Done 2026-10-02 (D-154, D-155): the record keeps the tip, the writer applies the point.
- [ ] NCXchange: neutral point words (number k, a, r) and their mapping to Fanuc H and D, Siemens D and a Heidenhain indexed tool (D-155, R1-11, T-039).
- [ ] A model of the control's radius compensation for the writer's checks and for verification (with topic 10).
- [ ] NCXchange: the Fanuc control tolerance (A-061, D-148) and the default for `TOLERANCE:ROTARY` (NCXchange D151).
- [ ] Rigid or floating TAP as a neutral NCX word (T-039).
- [ ] Reference programs written to all three controllers and kept as golden files (with topics 24 and 27).

---

[Index](README.md)

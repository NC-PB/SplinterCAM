---
topic: "27"
title: Machines and controllers
readiness: L4 for the ncx call and the machine choice of plan 0007 (below); L3 otherwise
release: "1"
reviewed: 2026-10-11
provenance: public
---

[Index](README.md)

# 27. Machines and controllers

How a machine and its controller are described so the CAM can write programs, check limits and estimate time. After D-021 and D-031 the controller dialects, cycle tables and machine files live in NCXchange. This topic covers the CAM side: which machine data the CAM reads from NCXchange and which it keeps in a sidecar, how it writes NCX and calls `ncx`, which NCX words release 1 needs, what the three controllers force on the output, and how output is verified. Release 1 controllers: Heidenhain, Siemens, Fanuc (D-020). NCXchange ships an iTNC 530 file and writes iTNC 530 Klartext; there is no TNC 640 file yet. For Siemens it has an 840D sl dialect and an older 840D dialect that splits helices into turns instead of writing `TURN=` (SRC-112, T-039).

## Scope

- In: the machine data the CAM reads (D-053); the sidecar for CAM-only data; the NCX writer and the `ncx` call (D-080, D-031); the release 1 NCX subset (Q-059); drilling through NCX cycles (D-061); verification (D-063); the NCXchange items release 1 needs (T-039, RK-010).
- Out: the dialect tables and compilers themselves (NCXchange); the toolpath record and its word-by-word mapping (topic 26); multi-axis kinematics (topic 12); probing (topic 30); cycle-time models beyond their data (topic 11, D-095).

## Decisions this topic writes down

D-020, D-021, D-024 (wear mode), D-028 (units at import), D-030, D-031 (NCX only, bundled `ncx`), D-053 (machine data), D-056 (control tolerance), D-061 (drilling subset and control-held values), D-063 (verification), D-078 (setups), D-080 (canonical NCX, pinned binary, roadmap items), D-095 (dynamics keys), D-096 (compensation and helix feed), D-154 and D-155 (measurement points). Later releases: D-072, D-085, D-091.

## Inputs and outputs

- In: the toolpath record (topic 26); the job's machine, which is an NCXchange machine TOML plus an optional sidecar `<machine>.cam.toml`; program name and number.
- Out: a canonical NCX text file; the controller files that `ncx compile` writes; the diagnostics of `ncx`, shown per operation; the CAM's own limit warnings and time estimate.

## The ncx call in plan 0007

- **Which `ncx`** (Peter, 2026-10-11, plan 0007 question 3): NCXchange has no release tag yet (R1-01). CI builds `ncx` from a pinned commit of NCXchange `main` (f74559c on 2026-10-11) in one job with the .NET SDK; locally the end-to-end test runs when `ncx` is on the path and is skipped with a visible message otherwise. The pin moves to the tag when R1-01 ships.
- **The call** (the three steps of the method below), in a working folder the CAM creates for the run (traps 3 and 4): `ncx format --check`, then `ncx check --machine <file> --strict`, then `ncx compile --machine <file> --output <folder>`. `compile` runs without `--strict` until NCXchange implements its D363; the test accepts `CMP020` warnings and fails on any other warning or error. Then `--strict` everywhere.
- **The machine** (plan 0007 question 2): all three shipped mill files compile the plan 0007 program cleanly (below). Peter picks one for the slice and for his dry run.

### Checked against NCXchange on 2026-10-11

Our build of NCXchange `main` at commit f74559c (macOS, .NET 10) compiled plan 0007's sample program (the outside profile of topic 22, test 1: rapids, lines, clockwise arcs in the centre form, one tool, one origin, coolant) for `fanuc-mill-30i`, `heidenhain-itnc530` and `siemens-840dsl-mill`: `ncx format --check` passed, and `ncx check --strict` and `ncx compile --strict` exited 0 on all three, under three conditions:

1. **`TOOL=n` carries `OFFSET:LEN=n`.** Without it the Fanuc output has `T1 M6` but no `G43 H1`: the control never applies the tool length, and the tip runs one tool length below the programmed Z. That is a crash, not a warning. Heidenhain applies the length with `TOOL CALL` and Siemens with `D1` either way. Until the neutral point words of D-155 exist in NCX (R1-11), the writer always emits `OFFSET:LEN` with the tool number in the tool-change block (ours; reported to NCXchange, T-039).
2. **The program `NAME` uses letters, digits and underscores only.** A space gives `CMP501` on Siemens, which fails `--strict`.
3. **Coordinates with more decimals than the machine file's `[format]` decimals** give one `CMP020` warning per value (here X95.1234567 written as X95.123), which fails `--strict` on all three. NCXchange answered this on 2026-10-07 (its D363: rounding to the machine's decimals is silent, D-149) but has not implemented it yet. Until it does, `compile` runs without `--strict` and the test accepts `CMP020` and nothing else; `check --strict` already passes, because `check` does not round.

## Method

### Machine data: one source (D-053)

The NCXchange machine TOML is the single source of machine data (D-053). At commit 9a1fb19 (SRC-112) it holds:

| Table | What the CAM uses it for | Keys and units |
| --- | --- | --- |
| `[machine]` | controller family and dialect; `limits` = warn or clamp | `name`, `controller` (fanuc, heidenhain, siemens), `dialect` |
| `[format]` | output decimals, to which NCXchange rounds (D-149), number style, file layout | `decimals` per address (X, Y, Z 3; F 3; S 0 in the shipped mills), separators, `program_layout` |
| `[[axis]]` | travel and speed checks, time estimate | `limits` [min, max] in machine coordinates (mm, or degrees for rotary), `rapid` and `max_feed` (mm/min or deg/min), `acceleration` (mm/s² or deg/s²), `home` |
| `[spindle.ROLE]` | speed checks | `rpm_min`, `rpm_max`, `accel_time` (s) |
| `[coolant]`, `[func]` | which coolant channels and named functions exist (for example rigid tapping on Fanuc) | channel = ON/OFF codes |
| `[tool_change]`, `[positions]` | tool change behaviour, named positions | templates; positions in machine coordinates |
| `[tolerance]`, `[retract]` | whether `TOLERANCE` and `RETRACT` can be written | templates |
| `[cycles]`, `[[cycle]]` | which cycle types the machine supports | the controller family's catalog plus machine overrides |
| `[dynamics]` | NCXchange's runtime estimate | `block_time` (s), `path_mode` (continuous or exact_stop), `corner_speed` (mm/min) |

Rotary values arrive in degrees and are converted to radians at import (D-028).

Three properties of this file shape the CAM side (SRC-112):

- The schema is a sketch, "finalized when the compiler exists". The loader requires only `[machine] name` and `controller`, the `id` and `type` of every resource, the `id`, `ncx` and `kind` of every axis, and the `id` of every kinematic node; the values in the shipped files are plausible, not measured (NCXchange D100, D138). The CAM therefore treats every other key as optional, with a declared fallback (D-049), and marks results based on a fallback.
- An unknown key is only a warning (`CFG002`), but it fails a `--strict` run. So CAM-only data must not go into the machine TOML until NCXchange accepts the key: it lives in the sidecar (D-053).
- The target controller comes from `[machine] controller`; `ncx` has no controller flag.

### The sidecar `<machine>.cam.toml`

Keys NCXchange does not have yet (SRC-112 gap check). Each is a declared parameter with unit, default, range and source (D-049), and each has an NCXchange proposal on T-039.

| Key | Unit | Default | Used for | Source |
| --- | --- | --- | --- | --- |
| `magazine.pockets` | count | none: no check | tool numbers per job | D-053; NCXchange has only `magazine = true` |
| `tool.max_length`, `tool.max_diameter` | mm | none: no check | tool library checks | D-053 |
| `tool.max_mass` | kg | none: no check | tool library checks | D-053 |
| `drill.fanuc_g73_retract` | mm | machine value, else a warning | simulation of CHIP_BREAK | Fanuc parameter 5114 (Q-039 brief, D-061) |
| `drill.fanuc_g83_clearance` | mm | machine value, else a warning | simulation of PECK | Fanuc parameter 5115 (Q-039 brief, D-061) |
| `drill.siemens_vrt` | mm | machine value, else a warning | CYCLE83 chip-breaking retract | Q-039 brief, D-061 |
| `dynamics.*`: jerk per axis; rotary speed, acceleration, jerk and travel; interpolation period; look-ahead depth; the parameters of the one calibrated corner model; acceleration step; calibration factor | mm/s³; deg/min, deg/s², deg/s³, deg (converted to radians at import); s; blocks; per model; per step; factor | from the public 840D data set (SRC-098) and a look-ahead of N = 40, all reported as estimated | time estimate (topic 11) | D-095 with the Q-078 answer |

Heidenhain's Q256 (0.6 mm) and Q208 (MAX) are not in the sidecar: NCXchange writes them into the program as fixed values today (`HeidenhainCycleValues.cs`, pending its question D164, SRC-112). The CAM holds them as read-only declared parameters with that source (D-049), and the simulation uses them, so it models the program that is written. D-061's "read by NCXchange" half waits on T-039.

The sidecar is versioned and validated strictly by the CAM: an unknown key or a value out of range is an error there, because nothing else checks it.

### The NCX writer and the `ncx` call (D-080, D-031)

- The writer produces the canonical NCX file from the record with the mapping and the number printer of topic 26: canonical layout, NCX number syntax, and always `UNITS`, `NUMBER`, `SURFACE` on cycles and `RPM` with `TOOL` (SRC-112).
- Proposal (ours) for the call: the CAM runs the bundled, pinned `ncx` as a subprocess, in a working directory it controls (`ncx` loads every plugin DLL in `plugins/` there and reads `ncx.toml`), in three steps:
  1. `ncx format --check <file>`: the writer produced canonical text.
  2. `ncx check <file> --machine <toml>`: a static run of the NCX virtual machine; diagnostics only, no compiler runs.
  3. `ncx compile <file> --machine <toml> --output <folder>`: the controller files, UTF-8 without BOM, none after any ERROR. Under `program_layout = one_file` (the shipped Fanuc and Siemens mills) a file is named after the NCX file stem (`.nc`, `.mpf`); under `file_per_program` (the shipped Heidenhain file) after the program `NAME` (`.h`). So `NAME` must be valid as a file name.
- Exit codes: 0 no ERROR; 1 an ERROR, a WARNING under `--strict`, or a `format --check` difference; 2 a usage error, unreadable input or a missing machine file. Diagnostics go to stderr, one per line, as `file(line): SEVERITY CODE: message`. The CAM parses them and shows each with the operation its line belongs to (the `SECTION` blocks mark operations).
- Cycle catalogs are found only through `ncx.toml`, a `cycles/` folder in the working directory, or `cycles/` next to the tool. A bundled single-file binary run from a CAM-controlled directory must still find them (packaging test; T-039).
- Pinning: NCXchange has no tags or releases yet; the spike pins commit 9a1fb19. Self-contained single-file binaries for Windows, macOS (arm64 and x64) and Linux are planned in NCXchange but not built, and CI runs on Linux and Windows only. D-031 needs both before release 1 ships (T-039).

### The release 1 NCX subset (Q-059)

Proposal (ours), following the mapping of topic 26. Words release 1 writes: `FILE`, `PROGRAM` (`NAME`, `NUMBER`), `UNITS`, `FEED_MODE`, `WORKPLANE`, `ORIGIN`, `SECTION`, `COMMENT` (register note), `TOOL`, the point words of D-155 (requested, R1-11; until NCX has them, `OFFSET:LEN` and `OFFSET:RAD`, which are not neutral), `RPM`, `SPINDLE`, `COOLANT`, `TOLERANCE` with `TOLERANCE_MODE` and `TOLERANCE:ROTARY`, `RAPID`, `LINE`, `ARC` (`CENTER`, `ANGLE`, incremental `IZ`), `F`, `COMP`, `CYCLE` (DRILL, DRILL_DWELL, PECK, CHIP_BREAK, TAP) with `SURFACE`, `CLEARANCE`, `DEPTH`, `SAFE`, `CYCLE_RETRACT`, `PECK`, `CYCLE_DWELL`, `PITCH`, `CYCLE_F`, then `CYCLE_CALL` and `CYCLE=OFF`, `FUNC` (rigid tapping where the machine file has a `RIGID_TAP` function; a temporary workaround against D-031 until NCX has a neutral word), `DWELL`, `PROGRAM=END`, `FILE=END`. All exist in NCX today except the point words (SRC-112).

Still missing in NCX (D-080, T-039): an exact-stop or continuous-path mode word (only a per-machine named function is possible); a stock word (Heidenhain `BLK FORM` and Siemens `WORKPIECE` stay raw); the rule that `F` on a helix is the feed along the 3D path (D-096; NCXchange's runtime estimate already times helices that way, and each compiler must convert where a control means something else); the Siemens `PECK` mapping (`CMP571`, NCXchange D181); a neutral rigid-tap word; expansion at compile time of a cycle the machine lacks (D-030; the three shipped mills do not need it, user machine files may).

### What the three controllers force on release 1 output

From the NCXchange compilers and machine files at commit 9a1fb19 (SRC-112):

| Subject | Fanuc 30i | Heidenhain iTNC 530 | Siemens 840D sl | Consequence for the CAM |
| --- | --- | --- | --- | --- |
| Program | `O<NUMBER>`; `NUMBER` required (`CMP300`) | `BEGIN PGM name MM`; units required (`CMP112`); one file per program, named after `NAME` | `%_N_NAME_MPF`; unsupported name characters become `_` (`CMP501`) | always a number; ASCII names valid as file names |
| Datum `ORIGIN=n` | G54 to G59 for 1 to 6; G54.1 P1 and up for 7 and up | cycle 247 with Q339 = n | G54 to G57 for 1 to 4, G505 to G599 for 5 to 99 | the UI shows the controller's code |
| Arcs and helices | G2/G3 with I J K or R; more than a turn split into full turns | CR, CC plus C, or CP IPA; one turn or less with Z as C/CR (D268) | I=AC J=AC, CR=, AR=, TURN= | helices in the `ANGLE` form (topic 26) |
| Compensation | G41/G42 with D | RL/RR on L blocks only (`CMP115`) | G41/G42; one D holds length and radius (`CMP510`) | switch on a straight move longer than r plus the largest wear (D-096, D-154); the register holds the point's r plus wear, only wear when r = 0 (topic 26) |
| Control tolerance | `G5.1 Q1`; the value is a control parameter | cycle 32 with T, HSC mode, TA | CYCLE832(tol, mode, rotary) | the same `TOLERANCE` for all; how Fanuc takes it is NCXchange's question (A-061, D-148); `TOLERANCE:ROTARY` while D151 is open |
| Drilling | G81, G82, G83 with Q, G73 with Q, G84 (floating unless `M29` through the named function), G85; `SAFE` other than the level before the cycle warns (`CMP382`) | 200, 203, 207 (rigid), 201; `SURFACE` required (`CMP104`) | CYCLE81, 82, 83, 84 (rigid), 85; `PECK` fails (`CMP571`) | peck drilling on Siemens waits for D181; a `rigid` flag on TAP |
| Plane change | | only together with `TOOL` (`CMP110`) | | XY only in release 1 |
| `RETRACT` word | no template: error | `M140 MB MAX` | no template: error | explicit heights (D-062, D-087) |
| Numbers | 3 decimals for X, Y, Z, F; a point on every real | comma as separator | point | the NCX carries the fixed resolution of D-149; NCXchange rounds to the file's decimals; angle addresses need decimals keys (T-039) |
| Comments | ASCII; a character without a transliteration warns (`CMP022`) | same | same | umlauts in operation names are transliterated |

### Verification (D-063)

- In CI, the chain is: write NCX, `ncx compile` for each of the three mill files, `ncx convert` of each controller file back to NCX, `ncx trace` of that NCX, then compare with the record.
- What can be compared within D-063's 0.001 mm: the end points the program writes, per axis. Points the control computes from rounded values (the end of a Heidenhain `CP IPA` or a Siemens `AR=` arc, Fanuc centres from I and J) can differ by up to about 0.003 mm (ours: centre and start rounding carried through the rotation, plus the travel rounding). D-149 settles it: NCXchange computes these points as the control will and keeps them within half an output step of the rounded end point or reports them; the round trip compares the read-back with the record within the operation's rounding allowance.
- LinuxCNC `rs274` on the Fanuc motion blocks only (SRC-115, D-063): the program number line, `G5.1`, `G54.1`, the drilling cycles and `M29` are stripped first, because they are not motion blocks in the sense of D-063 (and `G84` is not implemented in LinuxCNC; `G73` and `G83` take their retract from Fanuc parameters); the canonical calls come back with 4 decimals and are compared within tolerance, with units pinned.
- Per release: a fixed set of reference programs run in the vendor simulators or as air cuts.
- NCXchange's own suite has about 2,800 tests with round trips and golden files, but no golden compile of a CAM-style program to all three mills and no Siemens mill golden output (SRC-112). Our reference programs fill that gap (topic 24).

### Limits the CAM checks before `ncx`

- A feed above an axis `max_feed` is warned by the CAM per operation (NCXchange warns later, `VM441`); a spindle speed outside `rpm_min` to `rpm_max` likewise (NCXchange has a separate warning for it).
- Travel: the CAM knows the path in the work frame, not where the datum sits on the machine. Proposal (ours): an optional datum position in machine coordinates on the setup; with it, the path plus the tool length is checked against the axis limits, with the wear allowance added in wear mode (SRC-031 note below); without it, the check is skipped with a notice. The control checks soft limits at run time anyway (SRC-031 note).
- Tool numbers against the magazine pocket count, when the sidecar gives one.

## Parameters

| Parameter | Unit | Default | Range | Source |
| --- | --- | --- | --- | --- |
| NCXchange version | commit | f74559c (2026-10-11; the facts of this topic were read at 9a1fb19) | pinned per CAM release | SRC-112, D-080 |
| Machine file | path | per job | | D-053 |
| Strict mode for `ncx` | on or off | on once NCXchange rounds without a warning per value (D-149, T-039); off until then | | SRC-112 |
| Sidecar keys | as in the sidecar table | as listed | declared per key | D-049, D-053, D-061, D-095 |
| Datum position on the machine | mm | none (travel check skipped) | machine travel | ours |

## Traps

1. **The machine schema can still change.** It is a sketch in NCXchange, and 239 of its design questions (D108 to D346) are open; the CAM reads it defensively and pins the commit.
2. **Unknown keys warn**, so CAM-only keys belong in the sidecar, not in the machine TOML.
3. **Plugins load from the working directory**: run `ncx` in a folder the CAM controls.
4. **Cycle catalogs must be findable** by the bundled binary from that folder.
5. **No binaries yet**: today `ncx` is a .NET tool; release 1 needs the self-contained binaries (D-031).
6. **File names differ per layout**: NCX file stem under `one_file`, program `NAME` under `file_per_program`.
7. **Datum numbers differ** per controller for the same index.
8. **Peck drilling on Siemens** fails until NCXchange D181 is answered.
9. **Rigid tapping** differs: floating on the shipped Fanuc file unless the named function is switched on.
10. **The Fanuc control tolerance** is not in the program (A-061; NCXchange's question under D-148).
11. **Register contents** follow the measurement point (D-154, topic 26): r plus wear, only wear when r = 0. On Siemens one D carries length and radius, which fits one point; `OFFSET:LEN=5` is `H5` on Fanuc but edge `D5` of the active tool on Siemens, so register numbers are not neutral (D-155).
12. **Arc radius check**: NCXchange rejects an arc whose start and end radius differ by more than 0.01 mm (`VM230`); the record keeps them equal within 1e-6 mm, and rounding to 0.001 mm keeps them well inside.
13. **Names with umlauts** are transliterated in comments and replaced in Siemens program names.
14. **Plausible defaults** in the shipped machine files are not measured values (NCXchange D100); a time estimate built on them is an estimate.

## Tests

1. Every shipped NCXchange mill file loads without ERROR or WARNING, and the CAM reads every key it uses with a fallback when the key is missing.
2. The sidecar rejects unknown keys and out-of-range values; a machine without a sidecar still works.
3. The release 1 reference programs (facing; profile in wear mode with lead-in and lead-out; pocket with a helix entry; DRILL, PECK, rigid TAP holes) compile for the three mill files with no ERROR, apart from the Siemens peck gap, and the expected files appear under the expected names.
4. The compiled round trip (D-063, D-149): the read-back program against the record within the operation's rounding allowance (0.1·tol), for written and computed points; the NCX text is the same for all three mill files (D-148).
5. A program with an error gives exit code 1 and no NC file, and the CAM shows every diagnostic with its operation.
6. The same NCX file compiles to identical controller files on one platform.
7. A feed above `max_feed` and a speed outside the spindle range are warned by the CAM before `ncx` runs.
8. The bundled binary, started in an empty CAM-controlled folder, finds its cycle catalogs.

## Libraries

- NCXchange (MIT, .NET 10), bundled as a binary and called as a subprocess; not linked.
- Python's `tomllib` (standard library since 3.11, read only) for the machine TOML and the sidecar.

## Sources

- SRC-112: NCXchange repository at commit 9a1fb19.
- SRC-115: LinuxCNC `rs274` documentation.
- SRC-031: Suh et al. 2008 (literature note below).
- SRC-098: the public 840D dynamics data set (topic 11), for D-095's estimated defaults.
- Briefs: [Q-031](../reviews/2026-09-28-question-briefs/Q-031.md), [Q-039](../reviews/2026-09-28-question-briefs/Q-039.md), [Q-041](../reviews/2026-09-28-question-briefs/Q-041.md), [Q-059](../reviews/2026-09-28-question-briefs/Q-059.md).

## Literature notes

Distilled from the sources in our own words (D-044): each note carries what an implementer needs without the paper; the citation is there for checking. Where a note disagrees with the text above, the note has the evidence; T-036 brings the main text in line.

- Suh, Kang, Chung and Stroud 2008 (SRC-031), acceleration, look-ahead and corner speed inside the control: see [topic 11](11-path-optimisation.md#literature-notes); G-code semantics and STEP-NC: see [topic 13](13-post-processing.md#literature-notes).
- Sencer et al. 2015, Tajima and Sencer 2016, Tajima et al. 2018, Zhong et al. 2020, Erkorkmaz and Altintas 2001 (SRC-048 to SRC-052), corner smoothing in the control and the kinematic data a machine definition needs: see [topic 11](11-path-optimisation.md#literature-notes).
- Affouard et al. 2004, Munlin et al. 2004, Sun, Sun and Lee 2019 (SRC-070 to SRC-072), rotary-axis limits and singularities: see [topic 12](12-multi-axis-kinematics.md#literature-notes).
- Beudaert, Lavernhe and Tournier 2012 (SRC-098), a complete public dynamics data set of a Siemens 840D machine; Dong, Ferreira and Stori 2007 and Erkorkmaz et al. 2013 (SRC-084, SRC-085), more data points and the proposed cycle-time model (Q-078): see [topic 11](11-path-optimisation.md#literature-notes).

### Suh, Kang, Chung and Stroud 2008, chapters 1, 5–10: the control as a machine component, and what the book does not cover

**Source:** Suk-Hwan Suh, Seong-Kyoon Kang, Dae-Hyuk Chung, Ian Stroud, *Theory and Design of CNC Systems*, Springer Series in Advanced Manufacturing, Springer-Verlag London 2008, e-ISBN 978-1-84800-336-1, doi:10.1007/978-1-84800-336-1. **Read:** table of contents pp. xi–xvi; chapter 1 pp. 3–31 in full; chapter 5 section 5.5 pp. 179–184 in full, rest skimmed; chapter 6 pp. 187–226 in full; chapters 7, 9 and 10 skimmed (pp. 229–268, 315–393), with Table 10.2 p. 361 read; chapter 8 pp. 271–314 partly read (sections 8.1, 8.3, 8.5.2.6–8.6). **Class:** L.

**Problem.** Topic 27 needs to know which properties of a machine and its control the CAM must model, and topic 12 needs sources on multi-axis kinematics and tool centre point control. This note collects what the book offers for both and says plainly what is missing.

**What the rest of the book covers (skim, one paragraph).** Chapter 1 introduces NC machines, drives and sensors (DC, synchronous and induction servo motors; incremental and absolute encoders; resolvers; ball screws, linear guides, couplings), the four loop types (semi-closed with pitch and backlash compensation, closed with a linear scale, hybrid, open with stepper motors), the split of a CNC into MMI, NCK and PLC, and the trend from hard-wired NC to PC-based open and "soft" NC (pp. 3–31). Chapter 5 covers servo position control: PID tuning (Ziegler–Nichols, relay method), feed-forward variants (ZPETC, inverse compensation filter, FIR, speed and torque feed-forward), cross-coupled contour control, and the following error of each (pp. 157–185). Chapter 7 is the machine PLC: elements, IEC 61131-3 languages (ladder, instruction list, structured text, function blocks, sequential function charts), soft PLC and an executor implementation (pp. 229–268). Chapter 8 is the operator interface and shop-floor (conversational) programming, with the Mazatrol system as example, a turning roughing cycle for cast blanks, a corner rest-machining cycle and a drilling tool-order algorithm (pp. 271–314). Chapters 9 and 10 are real-time operating systems for CNC (processes, scheduling including rate-monotonic, semaphores, inter-process communication, latency measures, multi-processor layouts) and the design of PC-based and open controls (task modules, PLC scan scheduling, a motion-control programming example on RTX, and open-architecture requirements) (pp. 315–393).

**Method: the control model the book implies.**

1. **Three units** (pp. 20–29). MMI (user interface, not real time), NCK (interpreter, interpolator, acceleration control, position control; cyclic real-time tasks) and PLC (tool change, spindle, coolant, I/O; sequential logic). The NCK and the PLC share memory with the MMI through a kernel layer.
2. **Task periods** (pp. 28, 188, 361). Position control is the fastest cyclic task, interpolation runs at a multiple of it, the interpreter slower, the MMI in spare time. Examples: 1, 2 and 4 ms (p. 28 and Table 10.2 on a Pentium-100, where the three tasks took 210, 470 and 1800 µs); 2, 4 and 8 ms on a Pentium-75; 1 ms position and 8 ms interpolation in the book's own kernel.
3. **Kernel parameters** (Figs. 6.2 and 6.23, pp. 189, 212). The system parameters the book's kernels read: interpolation period; position-loop period; BLU; maximum allowable chord error; maximum allowable acceleration; rapid feed; acceleration method (linear, exponential, S-shape; before or after interpolation); fine interpolation method; number of look-ahead blocks; a machine "performance index" for arcs; the maximum allowable speed change per axis; the chord error for arcs.
4. **Following error** (section 5.5, pp. 179–184). With a proportional position loop of gain K_v (1/s), an axis at constant speed V (mm/s) lags by e = V/K_v. With speed feed-forward the lag becomes V·T_en (speed-loop time constant); with torque feed-forward V·(T_ei + T/2) (current-loop time constant and position-loop period). In the book's PID test on a simulated motor the position error stayed within 0.005 mm with P = 2.0 and 0.03 mm with P = 1.0 (p. 210).
5. **Operator overrides** (p. 274). Feed override 10–150 %, spindle override 50–150 %, rapid override 10, 50 or 100 %. The feed that actually runs is the programmed feed times the override (Eq. 3.27, p. 87).
6. **Machine data used at run time** (pp. 18, 50–51, 64–65, 190). Pitch-error and backlash compensation in the control; tool offsets and work offsets G54–G59 in a machine database that the interpreter reads; software stroke limits (G22/G23) and work-area and velocity limits checked after compensation.

**Multi-axis kinematics and tool centre point control (topic 12).** Not covered. Rotary axes appear only as A, B and C words in degrees (Table 2.1, p. 36), as cylindrical interpolation (G107, unrolled C–Z programming, pp. 46–47), as polar coordinate interpolation (G112/G113, listed in Table A.2 without explanation), and as 2D coordinate rotation G68. There is no inverse kinematics, no RTCP or TCPM, no tilted-plane cycle, no inverse-time feed. APT's TLAXIS statement appears in an example (p. 282). Nothing here answers Q-066 or Q-072, or verifies A-024 to A-026.

**Parameters and values.** As in items 2–5; no data for real machines.

**Limits and failure cases.** A generic teaching control with Fanuc as main reference; no Heidenhain, Siemens or Fanuc parameters, cycle semantics or smoothing modes. The only concrete commercial figure is Fanuc's look-ahead of about 1000 blocks (p. 146).

**How it was tested.** Task timings on two PC processors (Table 10.2); simulated PID runs (Figs. 6.19–6.21).

**What it means for us.**

- **Machine definition (Q-031, topic 27 "machine definition schema").** Beyond travel, feeds, rapids and spindle range, the CAM needs a small *dynamics block* per machine and control to predict cycle time and slowdowns (note b): interpolation period, look-ahead depth in blocks, path acceleration (or per-axis accelerations), per-axis allowed speed jump at corners, arc performance index (a in v ≤ √(a·R)), control chord error for arcs, acceleration mode (before or after interpolation; filter type and time constant if after), and, from topic 11, the smoothing tolerance command. Mark all of them optional with conservative defaults; the book shows they are ordinary parameters of any control. Whether these live in NCXchange's machine files or ours is part of Q-031 and should not be duplicated.
- **Following error (Q-034).** A lag along the path, harmless on lines, a contour error on the inside of curves and corners. No typical K_v in the book; register it as part of the controller share rather than guess.
- **Overrides.** Feed-dependent errors (ADCAI filters, lag, corner rounding) scale with a 10–150 % override; accuracy checks should assume the upper end.
- **Limits.** The control checks soft limits after compensation, at run time (p. 65). Our limits check (topic 13) must use the true centre path plus the wear allowance where control compensation is on (D-024, D-154); the measurement point changes only how the program describes the tool, not where it is.
- **Topic 12.** Needs other sources (control manuals for Q-066).

**Test ideas.**

1. Following-error model: V = 100 mm/s, K_v = 50 1/s gives e = 2.0 mm lag with feedback only; with speed feed-forward and T_en = 2 ms, e = 0.2 mm. A time-and-accuracy estimator that includes the lag must report exactly these values on a straight line and zero path deviation there.
2. Override scaling: the same program evaluated at 150 % override must report corner and arc deviations of an ADCAI control scaled by 1.5² for arcs (F² law) and 1.5 for corners (F·τ/8), per note b.
3. Machine file validation: a machine definition without a dynamics block must still load and use documented defaults; one with a negative acceleration or a zero interpolation period must be rejected.

## Open items

Readiness **L3**, needed for release **1**. Raised from L0 on 2026-10-01: machine data source, sidecar, writer, `ncx` call, NCX subset and controller constraints written from D-053, D-061, D-080 and NCXchange at a pinned commit; traps and tests listed; an adversarial review of the same day is folded in. Not L4: release 1 needs NCXchange items (T-039), among them the rounding of D-149 and the Fanuc control tolerance (A-061, D-148). Levels are defined in [AGENTS.md](../AGENTS.md#readiness-levels).

### Registered questions and assumptions

<!-- open-items:begin -->
_Generated by `tools/spike.py status` from QUESTIONS.md and ASSUMPTIONS.md. Do not edit by hand._

- [Q-126](../QUESTIONS.md#q-126-how-does-a-32-job-retract-before-the-axes-re-orient-and-how-does-ncx-express-it) (Claude, P3) How does a 3+2 job retract before the axes re-orient, and how does NCX express it?
<!-- open-items:end -->

### Missing before a spec

- [x] The NCX subset for release 1 and the `ncx` call (D-080; proposal above).
- [x] Machine definition schema with units (D-053; NCXchange tables and the sidecar above).
- [x] Dialect table per controller: lives in NCXchange (D-021, D-031); the constraints it puts on the CAM are above.
- [x] Canned-cycle semantics per controller (D-061; above and in topic 26).
- [x] Post configuration format: none in the CAM (D-031); verification oracle (D-063; above).
- [x] Output rounding and the compare bound for computed points (Q-131). Done 2026-10-01 (D-149, NCXchange rounds).
- [ ] NCXchange: the Fanuc control tolerance (A-061, D-148).
- [ ] The NCXchange items on T-039 that release 1 needs: the exact-stop and stock words (D-080); Siemens peck (D181); `TOLERANCE:ROTARY` (D151); the helix feed rule; a neutral rigid-tap word; machine-file keys for control-held values (D164 and the sidecar keys above); decimals keys for angles; cycle catalogs for the bundled binary; binaries, macOS CI and a tag. The helix form question D268 is avoided if the `ANGLE` proposal of topic 26 is kept.
- [ ] The release 1 reference programs as golden files (with topics 24 and 26).
- [ ] The point words of D-155 in NCX and their mapping per controller (T-039, R1-11).
- [ ] Later, P3: a machine key for the largest arc sweep per block, so NCXchange can split arcs on controls that take one quadrant per block (SRC-119, pp. 198–199).

---

[Index](README.md)

# SPEC: job

<!-- The application layer, cut to plan 0007, step 7 (D-160): read one small JSON job file, run the slice's chain
     (model's check, io's DXF import, one strategy per operation, cl, ncx) and write the NCX and the NC program into
     an output folder. The zip job container, templates, undo, the operation graph and recompute come with later
     plans (feature map, section 1; docs/dev/03, Recompute model). -->

| | |
| --- | --- |
| Status | Draft (2026-10-27, for Peter's review: AQ-011). Choices marked "(ours)" are in `src/splintercam/job/DECISIONS.md`, provisional until the review |
| Layer | 5 (see architecture/modules.yaml) |
| Depends on | foundation (`Context`, `Diagnostic`, `Severity`, `CANCELLED`, `ToleranceSet`, `TOLERANCE_DEFAULTS`); io (`read_dxf_contour`, `DrawingUnit`); model (`JobData`, `check_job`, the data types); cl (`make_cl_data`, `ClData`); `strategies/profile` (its declarations and planning function, AQ-014); ncx (`write_ncx`, `run_ncx`, `ProgramInfo`, `NcxCall`); geometry2d for the part's loop type in the strategy signature (AQ-013, AQ-014) |
| Research | none of its own (`architecture/modules.yaml`: `research: []`; docs/dev/03: the rules here are ours). It follows [27][r27], The ncx call in plan 0007, Exit codes, Traps 3, 4, 6, Test 5; [22][r22], Method and Test 1 (the golden case); [21][r21], Test 1 (the drawing); Project Spike `product/feature-map.md`, sections 1, 8 and 9 |
| Decisions | D-028 (units), D-049 (declared values), D-053 (the machine file), D-055 (determinism), D-148; text in [docs/spike/decisions-snapshot.md](../../../docs/spike/decisions-snapshot.md). Peter: plan 0007 questions 2 and 3; the feature map's command line (section 1, 2026-10-03) |
| Owner | Peter Burgener |

## Purpose

Runs one job from its file to the NC program: reads the job file, builds and checks the job's data (`model`), reads the part's contour (`io`), plans each operation with its strategy, builds the toolpath record (`cl`), writes the NCX (`ncx`) and has `ncx` check and compile it for the job's machine. It is the only module of the chain that reads and writes files (docs/dev/03, rule 5) and the only interface `apps/cli` uses (rule 6). It never leaves an NC program where a failed run could be mistaken for a good one.

## Scope

- In: the job file of format version 1; the strategy registry with `profile`; the stages and when to stop; the output folder, the NCX file, the working and staging folders; finding the `ncx` executable; a default `Context`; the golden case `profile-rectangle-fillets`.
- Out, handled elsewhere: value checks (`model`, REQ-MDL-002 to 029; the job checks the file's structure and passes values on as read); the DXF (`io`); the toolpath (the strategy and `toolpath`, step 5); the record's rules (`cl`); NCX words and `ncx` steps (`ncx`); arguments and exit codes (`apps/cli`).
- Later (one line each, no work): the zip job container, autosave and recovery (feature map, section 1); templates and default layers; inch values in the job file (D-028); several setups and programs; the operation graph and recompute; the stock update and simulation; the setup sheet; migrating older job files (feature map, section 9); the record as JSON Lines for golden comparison (research 26, Serialisation); checking that the `ncx` found is the pinned one (AQ-011 item 4).
- Non-goals: computation of its own; controller knowledge (D-148).

## The job file, version 1

UTF-8 JSON (a byte-order mark is accepted, DEC-JOB-003), one object; lengths in mm, feeds in mm/min, speeds in 1/min (D-028); key names carry the unit (D-049). Relative paths are relative to the job file's folder. Every key is required unless marked optional; no other key is allowed.

```json
{
  "format": "splintercam-job",
  "version": 1,
  "part": { "dxf": "part.dxf", "layer": null, "unit": null },
  "tools": [ { "number": 1, "type": "flat_end_mill", "diameter_mm": 10.0, "flute_length_mm": 30.0,
               "points": [ { "axial_offset_mm": 0.0, "register_radius_mm": 0.0 } ] } ],
  "stock": { "min_mm": [-5.0, -5.0, -20.0], "max_mm": [105.0, 65.0, 0.0] },
  "setup": { "work_offset": 1 },
  "operations": [ { "name": "PROFILE_1", "strategy": "profile", "tool": 1, "point": 1,
                    "spindle_rpm": 8000, "tol_mm": 0.01, "parameters": { "<declared name>": 0.0 } } ],
  "program": { "name": "RECT_FILLETS", "number": 1001 },
  "machine": "heidenhain-itnc530.toml"
}
```

- Optional (absent and `null` mean the same): `part.layer` (the whole drawing), `part.unit` (`"mm"` or `"inch"`, only for a DXF without units, REQ-IO-006 to 008), `tools[].points` (the tip alone, `model.TIP`; points are numbered 1, 2, … in order, D-155), `operations[].point` (1), `operations[].parameters` (none given; the strategy's defaults apply, REQ-MDL-024).
- `operations[].tool` is the tool's T number (`number`), not an index (REQ-MDL-014). `parameters` keys are the strategy's declared names (REQ-MDL-017; `profile`'s in `src/splintercam/strategies/profile/SPEC.md`, lane B1).

## Public interface

All names are proposals (ours). No kernel.

```python
@dataclass(frozen=True, slots=True)
class JobReport:
    diagnostics: tuple[Diagnostic, ...]     # every stage's, in the order of REQ-JOB-020
    cl_data: ClData | None                  # the record of stage 6, for the golden checks
    ncx_file: Path | None                   # the NCX file written, or None
    nc_files: tuple[Path, ...]              # the compiled files moved to the output folder, sorted by code point
    @property
    def ok(self) -> bool: ...               # no ERROR and no CANCELLED

def run_job(job_file: Path, output_dir: Path, *, ncx_executable: Path | None = None,
            machine_file: Path | None = None, ctx: Context | None = None) -> JobReport: ...
def default_context() -> Context: ...
```

- `run_job` returns a report, not a `Result`: a failed run may still have written the NCX file the user needs (feature map, section 8; DEC-JOB-001). `job` re-exports `Diagnostic` and `Severity` for `apps` (docs/dev/03, rule 6).
- `machine_file` overrides the job file's `machine`; `ncx_executable` None means `ncx` on the `PATH`. Relative paths given to `run_job` are taken against the current folder.
- `default_context()`: the tolerance set of `TOLERANCE_DEFAULTS` at its default tol, a new cancel token, no-op progress and debug sink, the logger `splintercam.job`, seed 0.
- A `ValueError` from `cl` or `ncx` (a producer's bug, DEC-CL-002) is not caught.

## Requirements

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-JOB-001 | THE `run_job` function SHALL run these stages in order and stop after the first that reports an error: (1) the job file (REQ-JOB-002 to 009); (2) the output folder (REQ-JOB-010); (3) `model.check_job`; (4) `io.read_dxf_contour`; (5) every operation's plan; (6) `cl.make_cl_data`; (7) `ncx.write_ncx`; (8) the NCX file; (9) `ncx.run_ncx` and the move of the compiled files (DEC-JOB-002). | unit: a fault at each stage stops the run there with nothing written after it | Draft |
| REQ-JOB-002 | IF the job file cannot be read, THEN `run_job` SHALL report `JOB_FILE_UNREADABLE` (error) with the OS's reason; IF it is not UTF-8 JSON holding one object, or holds `NaN`, `Infinity`, `-Infinity` or a number that reads as infinite (`1e400`), THEN `JOB_FILE_INVALID` (error) with the line and column (RFC 8259 has no such numbers; Python's `json` reads them; DEC-JOB-003). | unit | Draft |
| REQ-JOB-003 | IF `format` is not `"splintercam-job"` or `version` is not an `int` (not a `bool`) equal to 1, THEN `run_job` SHALL report `JOB_FORMAT_UNSUPPORTED` (error) naming both, and check nothing else of the file (feature map, section 9: files carry a version; newer ones are refused with a clear message). | unit: `"version": 2`, `true`, `1.0` | Draft |
| REQ-JOB-004 | IF a required key is missing or `null` where an object or array is required, or a value is not of the container type the layout requires, THEN `run_job` SHALL report `JOB_KEY_MISSING` or `JOB_STRUCTURE_INVALID` (error) naming the key's path, as `operations[1].tol_mm`, indexes from 1 (ours, as REQ-MDL-027). | unit: `"tools": 5`, `"part": null`, `"points": null` (optional: the default) | Draft |
| REQ-JOB-005 | IF an object holds a key version 1 does not name, or a key twice (`parameters` excepted, REQ-JOB-006), THEN `run_job` SHALL report `JOB_KEY_UNKNOWN` or `JOB_KEY_REPEATED` (error) naming its path (ours: a misspelt key would leave a default in force unseen, as REQ-MDL-021). | unit: `tol` for `tol_mm`; `"tool"` twice | Draft |
| REQ-JOB-006 | THE `run_job` function SHALL pass the values of `tools`, `stock`, `setup` and `operations` to `model` as the JSON reader gives them, arrays as tuples, `parameters` as (name, value) pairs in file order with repeats kept, and points numbered 1 … n in order, so `model` reports types, ranges and repeats (REQ-MDL-021, 029; DEC-JOB-003). | unit: `"diameter_mm": "10"` gives `VALUE_TYPE_INVALID`; a parameter twice gives `PARAM_REPEATED` | Draft |
| REQ-JOB-007 | IF a tool's `type` is not `"flat_end_mill"`, THEN `run_job` SHALL report `JOB_TOOL_TYPE_UNSUPPORTED` (error) naming the tool (REQ-MDL-001: the slice's only tool). | unit | Draft |
| REQ-JOB-008 | IF `part.dxf` or `machine` is not a non-empty string, `part.layer` not a string, `part.unit` not `"mm"` or `"inch"`, `program.name` not a string, or `program.number` not an `int` (not a `bool`), THEN `run_job` SHALL report `JOB_VALUE_INVALID` (error) naming the key (ours: `model` does not check the program, and `true` would pass as 1; `ncx` checks the name's characters and the number's range, REQ-NCX-014). | unit: `"number": true`, `1001.5`, `"1001"` | Draft |
| REQ-JOB-009 | THE `run_job` function SHALL resolve `part.dxf` and `machine` against the job file's folder when relative, use `machine_file` (taken against the current folder) instead of `machine` when given, and IF the machine file does not exist, THEN report `JOB_MACHINE_NOT_FOUND` (error); it SHALL look up the `ncx` executable (REQ-JOB-017) and report `JOB_INPUTS` (info) naming the absolute machine file and the executable, or that none was found (DEC-JOB-004: a program compiled for another machine than meant must be visible). | unit: a job folder with a relative DXF, run from another folder | Draft |
| REQ-JOB-010 | IF the output folder exists and is not an empty folder, or cannot be created with its parents, THEN `run_job` SHALL report `JOB_OUTPUT_NOT_EMPTY` or `JOB_OUTPUT_UNWRITABLE` (error) and write nothing (DEC-JOB-005: an NC program from an earlier run must not be taken for this run's). | unit: a non-empty folder, a file at the path | Draft |
| REQ-JOB-011 | THE `run_job` function SHALL check the job's data with `model.check_job` and the declarations of every strategy in the registry, and pass its diagnostics on as they are. | unit: the example job; without its feeds `PARAM_MISSING` twice | Draft |
| REQ-JOB-012 | THE `run_job` function SHALL read the part with `io.read_dxf_contour` (path, layer, unit of `part`) and pass its diagnostics on as they are. | unit: a DXF without units and no `unit` stops with `DXF_NO_UNITS` | Draft |
| REQ-JOB-013 | THE job module SHALL hold the strategy registry as a fixed mapping from strategy id to the strategy's declarations and planning function; in plan 0007 it holds `profile` alone (docs/dev/03, one strategy interface; the function's form: AQ-014). | unit: an unknown id gives `model`'s `OP_STRATEGY_UNKNOWN` | Draft |
| REQ-JOB-014 | THE `run_job` function SHALL plan the operations in the user's order, each with `ctx` whose tolerance set alone is replaced by `ToleranceSet.for_operation` of its tol (D-029, D-056), polling `ctx.cancel` before each; it SHALL plan every operation before it stops on an error (ours, as REQ-MDL-025). A strategy's diagnostic SHALL get the location `operation <index> (<name>)` (index from 1, REQ-MDL-027), followed by `: ` and its own location if it has one. | unit: fake strategies in a test registry; two failing operations report both; the cancel token reaches the strategy | Draft |
| REQ-JOB-015 | THE `run_job` function SHALL build the record with `cl.make_cl_data` from the work offset and the operations in order, and write it with `ncx.write_ncx` and the job's `program`. | unit | Draft |
| REQ-JOB-016 | THE `run_job` function SHALL write the NCX text, ASCII, to `<output>/<program name>.ncx`, and IF that fails, THEN report `JOB_OUTPUT_UNWRITABLE` (error) and remove the partial file (research 27, trap 6: one name for both layouts when the NCX stem is the program name, ours). | unit: the bytes equal the text; a read-only folder | Draft |
| REQ-JOB-017 | IF `ncx_executable` is None and no `ncx` is on the `PATH`, or the executable given does not exist, THEN `run_job` SHALL report `JOB_NCX_NOT_FOUND` (error) after writing the NCX file, and run no step (plan 0007, question 3: the NCX is still useful). The lookup is made in stage 1 (REQ-JOB-009). | unit | Draft |
| REQ-JOB-018 | THE `run_job` function SHALL make a new temporary folder outside the output folder holding two empty folders, the working folder and the staging folder, pass both and every path absolute to `ncx.run_ncx`, and remove the temporary folder afterwards, also after an error or a cancel; IF it cannot be removed, THEN report `JOB_WORK_DIR_LEFT` (warning) naming it (research 27, traps 3, 4; DEC-JOB-007). | integration: a fake `ncx` records its working folder; the folder is gone afterwards, also after a cancel | Draft |
| REQ-JOB-019 | WHEN `run_ncx` is `ok`, THE `run_job` function SHALL move every file of the staging folder into the output folder and name them in `nc_files`; otherwise it SHALL move none, and `nc_files` SHALL be empty. IF `run_ncx` is `ok` and the staging folder holds no file, THEN it SHALL report `JOB_NO_NC_FILE` (error) (research 27, test 5: an error gives no NC file; DEC-JOB-008). | integration: a fake `ncx` that writes a file and then fails, or is cancelled, leaves the output folder with the NCX file only | Draft |
| REQ-JOB-020 | THE report's diagnostics SHALL come in stage order; within stage 1 depth-first in the layout's key order, list items by index, unknown and repeated keys after their object's keys sorted by code point, and `JOB_INPUTS` last; every other stage's in its module's own order (ours, D-055). | unit: the example with `tol` for `tol_mm` gives `JOB_KEY_MISSING` at `operations[1].tol_mm`, then `JOB_KEY_UNKNOWN` at `operations[1].tol` | Draft |
| REQ-JOB-021 | WHEN `ctx.cancel` is set, THE `run_job` function SHALL stop before the next stage or operation, write and move nothing more, and report `CANCELLED` (REQ-FND-013; within an `ncx` step REQ-NCX-024). | unit: the token set by a fake strategy | Draft |
| REQ-JOB-022 | THE `run_job` function SHALL write the same NCX bytes for the same job file and DXF on one platform, run twice (D-055 tier 2). | unit: two runs into two folders | Draft |
| REQ-JOB-023 | THE golden case `testdata/zoo/profile-rectangle-fillets/` SHALL hold `case.json`, `job.json`, `part.dxf`, `make_part.py` (writes `part.dxf` with ezdxf) and `README.md`, with an entry in `testdata/LICENSES.md` (drawn for this project, Apache-2.0): research 22 test 1 with research 21 test 1's drawing, the job of model's Example parts (`src/splintercam/model/SPEC.md`), program `RECT_FILLETS` 1001, the iTNC 530 machine file. Its checks, as data in `case.json` (docs/dev/06), are listed in the Test plan; `expected/` is added by a person (docs/dev/06, rule 3). | golden: `tests/job/golden/`; end-to-end: `src/splintercam/apps/cli/SPEC.md`, REQ-CLI-008 | Draft |

## Invariants

- `run_job` writes only into the output folder and its own working folder, and nothing into the output folder before stage 8 (REQ-JOB-001, 010, 016, 018). Unit test with a fault per stage.
- A report with an ERROR or `CANCELLED` has `nc_files == ()`; a report with `ok` has `ncx_file` and at least one file in `nc_files` (REQ-JOB-017, 019, 021).

## Tolerance budget

None spent. Each operation's tolerance set comes from its tol (REQ-JOB-014).

## Failure modes and diagnostics

All are errors except `JOB_INPUTS` (info), `JOB_WORK_DIR_LEFT` and `CANCELLED` (warnings); other modules' diagnostics are passed on.

| Situation | Diagnostic |
| --- | --- |
| Job file unreadable; not JSON, not an object, NaN or infinite numbers | `JOB_FILE_UNREADABLE`; `JOB_FILE_INVALID` |
| Wrong format name or version | `JOB_FORMAT_UNSUPPORTED` |
| Key missing; wrong container type | `JOB_KEY_MISSING`; `JOB_STRUCTURE_INVALID` |
| Key unknown or repeated | `JOB_KEY_UNKNOWN`, `JOB_KEY_REPEATED` |
| Tool type; part, path or program values | `JOB_TOOL_TYPE_UNSUPPORTED`; `JOB_VALUE_INVALID` |
| Machine file missing | `JOB_MACHINE_NOT_FOUND` |
| Output folder not empty, not writable; NCX file not written | `JOB_OUTPUT_NOT_EMPTY`, `JOB_OUTPUT_UNWRITABLE` |
| No `ncx`; `ncx` ok but no file | `JOB_NCX_NOT_FOUND`; `JOB_NO_NC_FILE` |
| Working folder not removed | `JOB_WORK_DIR_LEFT` |
| The machine file and executable used | `JOB_INPUTS` |
| Cancelled | `CANCELLED` |

## Algorithms and design inputs

No algorithms.

| Element | Public source, or own design with date |
| --- | --- |
| Job file keys and version | feature map, sections 1 and 9 (Peter, 2026-10-03); the keys ours, 2026-10-27 (DEC-JOB-003) |
| Stages, stop rules, output, working and staging folders | ours, 2026-10-27 (DEC-JOB-002, 005, 007, 008); research 27, traps 3, 4, test 5; feature map, section 8 |
| Strategy registry | docs/dev/03; feature map, section 9 |

## Example parts

- The golden case with `ncx` and the machine file: no ERROR or WARNING; INFO `JOB_INPUTS`, `DXF_PART_SIZE` (REQ-IO-027) and `NCX_ROUNDED`, in that order; `RECT_FILLETS.ncx` and `RECT_FILLETS.h` in the output folder.
- With `"tol": 0.01` for `"tol_mm"`: `JOB_KEY_MISSING` at `operations[1].tol_mm`, `JOB_KEY_UNKNOWN` at `operations[1].tol`; nothing written.
- Run twice into one folder: `JOB_OUTPUT_NOT_EMPTY`. Without `ncx`: `RECT_FILLETS.ncx`, `JOB_NCX_NOT_FOUND`, no NC program. With the golden `job.json` and no `machine_file`: `JOB_MACHINE_NOT_FOUND` (the machine file is not in the case folder, DEC-JOB-004).

## Test plan

- Unit (`tests/job/unit/`): per requirement, tagged with its ID; a test registry with fake strategies; job files written into temporary folders.
- Integration: a fake `ncx` (as in `tests/ncx/integration/`) for REQ-JOB-017 to 019 and 021.
- Golden (`tests/job/golden/`), `case.json`'s checks for `profile-rectangle-fillets`, comparisons within 0.001 mm (D-055 tier 3; docs/dev/06: never exact): on the record (`cl_data`, always: without `ncx` the runner passes any existing file as `machine_file` and a missing `ncx_executable`, so the run stops at `JOB_NCX_NOT_FOUND` after stage 6): three passes at z −10/3, −20/3 and −10; per pass 5 CUT LINEs (S splits a long side) and 4 CUT ARCs of sweep −π/2 and radius 10 about (5, 5), (95, 5), (95, 55), (5, 55), clockwise round the part; S the midpoint of a long side; the approach point P at least R + 0.2·R = 6 mm from the stock box (research 22, Method 4 and 5, test 1). With `ncx` on the path and the machine file from the pinned NCXchange checkout (`SPLINTERCAM_NCXCHANGE`, DEC-JOB-004): `ncx check --strict` exits 0, `compile` writes `RECT_FILLETS.h` and reports only `NCX_ROUNDED`; skipped with a message otherwise. The `expected/` comparison (the NCX per platform) once a person has approved it; `tools/golden-diff` and `tools/golden-approve` come in later plan steps (AQ-011 item 5).
- Property, differential: none.

## Performance budget

None of its own.

## Size estimate

First count about 240 NLOC of Python (reading and the JSON hooks 25; the key walk with paths and order 65; building the model types 30; the registry 10; the stages 45; the folders, the move and the listing 40; report and default context 25); by Peter's rule of 2026-10-25 about 1.5 times that: **about 360 NLOC**, and about 500 lines of tests. With `apps/cli`'s 90 the step comes to about 450 against the plan's 200 by the rule, 300: 50 % over, at the stop, for the structure checks, the staging move and the clean-up the reviews asked for; AQ-013 asks Peter. At more than 400 lines of non-test code the implementation comes as two pull requests, `job` first, then `apps/cli` (AGENTS.md, Done means). Module budget 360 (AQ-013).

## Open questions

Box 1 in `docs/agents/questions/AQ-011.md` (this SPEC's review), AQ-013 (budget and `depends_on`) and AQ-014 (the strategy function's form). Box 2 choices are in `src/splintercam/job/DECISIONS.md`.

## Change log

- 2026-10-27: drafted for plan 0007, step 7, from research 27, 22 and 21, the feature map, sections 1, 8 and 9, and docs/dev/03; revised after the spec review the same day: absolute paths for `ncx`, compiled files moved only after a clean run, `ok` without `CANCELLED`, the program and version typed, the machine file checked and named, the golden checks exact to research 22, structure errors and their order, the working folder removed always.

[r21]: ../../../docs/research/21-geometry-input.md
[r22]: ../../../docs/research/22-2d-operations.md
[r27]: ../../../docs/research/27-machines-and-controllers.md

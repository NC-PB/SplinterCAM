# Plan 0007: the first NC program (a thin vertical slice)

<!-- Lives in docs/plans/active/ while work is ongoing, then moves to docs/plans/completed/.
     The agent updates the progress log as the work goes (docs/dev/07). -->

- **Status: approved by Peter on 2026-10-11, all five questions answered as recommended (below).** Step 1 (the research pull) runs in Project Spike; step 2 starts when its pull request is on `main`.
- Goal: one complete path from a drawing to an NC program: a DXF with one closed contour → an outside profile with depth passes → the toolpath record → NCX → `ncx check --strict` passes and NCXchange compiles it for one machine. Every module on the way is as small as the path needs; later plans widen them.
- Why now: foundation, geometry2d and offset2d are done and deep. Nothing yet proves that the modules fit together (io, model, cl, toolpath, strategies, ncx, job, apps/cli), and nothing has reached NCXchange. A thin slice finds wrong boundaries while they are cheap to change (Peter, 2026-10-11, after the drift review).
- Specs: one SPEC per new module, each cut to this slice only (D-160: about 30 requirements, at most three pages).
- Research: the parts of topics 21 (DXF), 22 (profile), 10 (links), 26 (toolpath record) and 27 (NCX and machines) that this slice uses, brought to L4 in Project Spike and moved here when a step pulls them (D-159, D-158). Research requests go to `docs/research/REQUESTS.md`.
- Branch: one pull request per step (a new module is a new algorithm), from `main` after the previous merge, never stacked.
- Owner: Peter Burgener; agents: Claude Code sessions.

## Scope of the slice

In: a DXF in millimetres with one closed contour of lines, arcs and bulges; a box stock; one flat end mill entered by hand (diameter, flute length, measurement point at the tip, D-154); spindle speed and feeds entered by hand; one setup with work offset 1 and the part at the origin; one outside profile: side allowance, depth, constant step-down, climb, start outside the stock at depth, retract to the clearance height between depth passes; NCX for one machine file; `ncx check --strict` and `ncx compile`.

Out (later plans): STEP, pockets, drilling, leads and tabs, ramps and helices, arc fitting (output stays lines and the record's arcs as given), the cutting-data solver, the stock update, link checks beyond the clearance height, several setups, the GUI.

## Questions for Peter (machining terms, each with a recommendation)

Answered 2026-10-11: all as recommended. For question 2, step 1 checks the three machine files and Peter picks one of those that compile the slice's words cleanly.

1. **Which operation first?** Recommended: an outside profile of a closed contour. It starts beside the part in air, so it needs no entry into material, and it uses `offset_region` (GROW) as built. A pocket needs entry moves and pass order and comes second.
2. **Which machine?** Recommended: the NCXchange machine file with the most complete compiler today; the agent checks which of `fanuc-mill-30i.toml`, `heidenhain-itnc530.toml` and `siemens-840dsl-mill.toml` compiles the NCX words this slice needs without warnings, and you pick one of those.
3. **How does the slice get `ncx`?** NCXchange has no release tag yet (R1-01). Recommended: CI builds `ncx` from a pinned NCXchange commit (needs the .NET SDK in one CI job); locally the test runs when `ncx` is on the path and is skipped with a visible message otherwise. When R1-01 ships, the pin becomes the tag.
4. **Moves between depth passes:** recommended: retract to the clearance height, rapid back over the start point outside the stock, feed down to the next depth outside the stock. Safe and simple; staying down comes with the link rules of topic 10.
5. **Is the program right?** Recommended: you run the NC program in the control's simulation or dry run on one machine, as the slice's last check. A test cannot replace that the first time.

## Steps

<!-- Each step has a size estimate (kept code + tests). At 50 % over it, stop and ask (docs/dev/12, section 3). -->

- [x] 1. **Research pull** (Project Spike): topics 21 (DXF part), 22 (outside profile), 10 (clearance-height links only), 26 (the record subset: rapid, linear, arc, feed, spindle, tool, work offset, comment) and 27 (the NCX words for that subset, and how `ncx` is called) at L4 for these parts, moved to `docs/research/`. Size: docs only.
- [x] 2. **`io`: DXF to curve rows.** ezdxf; closed chains of lines, arcs and bulges in millimetres; a file without units refused with a diagnostic (D-033); part size reported. Size: about 200 + 250.
- [ ] 3. **`model`: the slice's job data.** Tool (flat end mill, measurement point), stock box, setup (work offset, frame), operation parameters as declarations (D-018), held in memory. Size: about 200 + 200.
- [ ] 4. **`cl`: the toolpath record subset** of topic 26: moves, feeds, spindle, tool, work offset, comments, operation name and note (feature map, section 6). Size: about 150 + 200.
- [ ] 5. **`strategies/profile` with the slice's `toolpath` links.** `offset_region` GROW of the material contour by R + allowance; depth passes; start point; climb; clearance-height retract. Size: about 250 + 300.
- [ ] 6. **`ncx`: the writer and the call.** NCX at the resolution of D-149; `ncx check --strict` and `ncx compile` run as a subprocess; NCXchange's messages mapped to the operation (feature map, section 8). Size: about 200 + 250.
- [ ] 7. **`job` and `apps/cli`.** A small job file (JSON) naming the DXF, stock, tool, setup and operation; `splintercam run job.json` writes the NCX and the NC program. End-to-end test: a rectangle with filleted corners → `ncx check --strict` passes, the NC program compiles; a golden case `profile-rectangle-fillets` in `testdata/zoo/`. Size: about 200 + 250.
- [ ] 8. **Peter's dry run** on the chosen machine's control or simulator; findings back as decisions or research requests; handover.

Stop after each step for Peter's review of its pull request.

## Decisions

- 2026-10-25: the `model` SPEC approved (Peter, AQ-002): the drawing's origin is the datum of work offset 1, no placement in the slice; spindle clockwise and coolant on without fields; strategy parameters declared in `model`, numbers only; a measurement point's axial offset is any a ≥ 0 (D-154), above the flute length with a warning naming the shift of every Z. `model`'s budget 260 and research 26, 22, 27, 10, 23 (AQ-003).
- 2026-10-25: `io`'s budget is 820 NLOC in `architecture/modules.yaml` (Peter, on the agent's question 1). The implementation came to 795 against the 360 set on 2026-10-13; the size is the reviewed SPEC's gap repair with its move bound, five OCS entity types and exact diagnostics, which the simplifier found intrinsic. Splitting the chaining into a module of its own was not taken: a new SPEC for no gain in the slice.
- 2026-10-13: gaps between DXF entities up to 0.01 mm are repaired with a warning naming the place; larger gaps stop the import naming the place (Peter, answer 1 on the io SPEC draft). Read in `src/splintercam/io/DECISIONS.md`, DEC-IO-001: open chains stop the import too.
- 2026-10-13: a job unit that differs from the DXF file's unit stops the import; a file without a unit (`$INSUNITS` 0 or missing) follows `docs/research/21-geometry-input.md`, Method 2: the job's unit is used, and without one the import stops with `DXF_NO_UNITS` (Peter, answer 2; DEC-IO-002). A unit io does not read, such as feet, stops the import (ours, DEC-IO-002).
- 2026-10-11: the slice's machine is the Heidenhain iTNC 530 (`machines/heidenhain-itnc530.toml` in NCXchange), Peter's pick after step 1 showed that all three shipped mill files compile the slice's program (question 2). Peter's dry run (step 8) is on that control.
- 2026-10-11: the writer always emits `OFFSET:LEN` with the tool number in the tool-change block, although the iTNC 530 applies the length with `TOOL CALL` anyway: the NCX stays the same for every controller (D-148), and on the Fanuc file a tool change without it never activates `G43` (research 26, Checked against NCXchange; NCXchange request R1-13).
- 2026-10-11: plan approved; Peter's answers to questions 1 to 5 as recommended (outside profile first; the machine picked from those that compile cleanly; `ncx` built in CI from a pinned NCXchange commit, skipped locally with a message when absent; clearance-height retract between depth passes, feed down outside the stock; Peter's dry run as the last check).

## Progress log

### 2026-10-11, step 1 (Project Spike)

- Research moved (PR 66): `docs/research/26-toolpath-record.md` and `27-machines-and-controllers.md` whole, with the plan 0007 subset at L4; `21-geometry-input.md` (DXF import), `22-2d-operations.md` (outside profile) and `10-linking.md` (clearance-height links) new, with only what this plan uses.
- NCXchange `main` at f74559c built and run on the slice's sample program: `format --check`, `check --strict` and `compile --strict` pass on all three mill files when `OFFSET:LEN` is written, the program name has no spaces and coordinates have at most three decimals; with more decimals `compile` warns `CMP020` until NCXchange implements its D363, so `compile` runs without `--strict` and accepts only `CMP020` (research 27, The ncx call in plan 0007).
- Next: step 2, `io`: DXF to curve rows (research 21).

### 2026-10-12, step 2 (SPEC draft, for Peter's review)

- `io` had no SPEC and ezdxf was not yet a dependency, so step 2 starts with documents only: `src/splintercam/io/SPEC.md` drafted from research 21 with `/research-to-spec` (30 requirements, REQ-IO-001 to 030, all Draft), and `docs/adr/0011-ezdxf-dxf-reader.md` (Proposed). No code until both are approved.
- Spec reviews (two rounds): two blockers fixed in the draft. 2D POLYLINE vertices are OCS points like LWPOLYLINE's, so a mirrored polyline would have been read un-mirrored. ezdxf reports 3D, mesh and spline-fit polylines as `POLYLINE` too. Research 21's midpoint gap rule keeps an arc's sweep, so on a near-full arc a 0.005 mm end move shifts the arc by about 0.5 mm: now the row that magnifies less moves (a line before an arc), each row's move is bounded exactly by B = (|ΔP0| + |ΔP1|)·D/c, silent only up to 3·eps_len (REQ-IO-020 to 022). Arc constructions must run in C++ with libm, not NumPy (D-055), which needs array entries in geometry2d (open question 5). Corrections to research 21 filed as RR-004.
- Size: the draft estimates about 300 NLOC, 50 % over the step's 200, so it stops here for Peter (docs/dev/12, section 3).
- Questions for Peter (the SPEC's Open questions): (1) gap limit 0.01 mm at finishing tolerance, and the parameter in foundation's `tolerance_defaults.toml`; (2) a job unit that differs from the file's unit stops the import (provisional); (3) ADR 0011; (4) the size, and `io`'s budget in `architecture/modules.yaml`; (5) array forms of `arc_from_bulge` and the bounding box in geometry2d's kernel, a pull request of its own before io.
- Next: on approval, the implementation pull request: `pyproject.toml`, `uv.lock` and `NOTICE` (ADR 0011), the foundation parameter, `src/splintercam/io/` with `AGENTS.md` and `DECISIONS.md`, and tests first.

### 2026-10-13, step 2 (SPEC reviewed)

- Peter answered the five questions: gap limit 0.01 mm, larger gaps stop the import; a unit mismatch stops it, a file without a unit takes the job's as research 21 says (both under Decisions); ADR 0011 accepted; `io`'s budget 360 in `architecture/modules.yaml`; the three array functions go into geometry2d's kernel in their own pull request before io, kept to the functions, their tests and the interface change (DEC-G2D, recorded with that pull request).
- `src/splintercam/io/SPEC.md` Reviewed; `src/splintercam/io/DECISIONS.md` started (DEC-IO-001 to 004). RR-004 gains items 5 and 6.
- Next: the geometry2d pull request (array forms of `arc_from_bulge`, of an arc from end points and sweep, and of the bounding box of curve rows), then io's implementation.

### 2026-10-25, step 2 (io implementation)

- Implemented the DXF import against the Reviewed `src/splintercam/io/SPEC.md`: `ezdxf` added (ADR 0011); foundation gains the declared parameter `dxf_gap_close_mm` (REQ-FND-014, `tolerance_defaults.toml`); `src/splintercam/io/` with `__init__.py`, `_units.py`, `_diagnostics.py`, `_entities.py`, `_chain.py`, `_read.py`, plus `AGENTS.md` and DEC-IO-005. All 30 requirements REQ-IO-001 to 030 implemented.
- Tests: `tests/io/unit/test_dxf_import.py` (39 unit tests, one or more per requirement, research 21 tests 1 to 7) and `tests/io/property/test_dxf_chaining.py` (2 property tests: scrambled-polygon chaining and the mirror |area| invariant). All io and foundation tests pass (208). The rectangle-with-fillets reads as 8 rows with area 6000 − (4 − π)·25 mm² (research 21 test 1).
- Reviews run on the diff (docs/dev/12): `simplifier`, then `spec-reviewer` and `test-auditor`. Findings addressed: every tolerance decision now uses sqrt of a sum of squares, never `hypot` or `sin` (D-055; the magnification D/c for |φ| > π rewritten as 2r/c); REQ-IO-020 and REQ-IO-021 gained tagged unit tests (the line-meets-arc mover rule and the arc-magnified B over the limit), the two property tests gained `@pytest.mark.req` markers, and one tautological assertion was fixed; `box_of_rows` removed a duplicated bounding-box helper; DEC-IO-005 records the sqrt-only rule, the pyright suppressions and the `DXF_LAYER_EMPTY` reading. The simplifier confirmed the remaining size is intrinsic to the Reviewed requirement set, not waste.
- `tools/check`: ruff format, ruff check, pyright (3 platforms), clang-tidy, build, arch-check all pass. Two steps fail, **neither from io's correctness**:
  1. **size-check, hard**: module `io` is 795 NLOC, over the budget + 20 % (432) of its 360 budget. The two-stage matching, the move bound B, the five OCS entity types and the diagnostic ordering the SPEC reviews added, together with the strict lint (≤ 5 args, complexity ≤ 10) that forces decomposition, put io at ~26 NLOC per requirement. Raising `io`'s budget in `architecture/modules.yaml` is Peter's call (question 1 below).
  2. **pytest**: `tests/offset2d/differential/test_offset_region_differential.py::test_the_offset_agrees_with_geos_outside_the_band` fails on a Hypothesis counterexample (an AIR region at `t_mm=9.0`, `tol_mm=0.01`). This is in offset2d, not io; the diff touches no offset2d or geometry2d source, so `offset_region` is byte-identical to `main` and fails identically there for this input. A pre-existing latent offset2d issue surfaced because the foundation change made `tools/check` run all dependents. Not fixed here (out of scope; no test weakened). Reported as question 2 below.
- Not pushed: `tools/check` fails on the two items above, both needing Peter. The branch `io/dxf-import-0007-step2` holds the work.

### 2026-10-25, step 2 (answers, Project Spike session)

- Question 1: Peter raised `io`'s budget to 820 (under Decisions). Question 2: offset2d is right on that example and GEOS's buffer is not (8 points 9.02 to 9.29 mm from every curve left out of a C 0.3 to 0.7 mm wide); test 20 now lets research 02 test 9's exact oracle decide where the two disagree, in its own pull request (`offset2d/test-20-oracle`, DEC-OFF-025). NOTICE gains ezdxf, fontTools and pyparsing (ADR 0011).
- Step 2 done; the pull request follows. Next: step 3, `model`.

### 2026-10-25, step 3 (SPEC draft, for Peter's review)

- `model` had no SPEC and no budget, so step 3 starts with documents only: `src/splintercam/model/SPEC.md` drafted from research 26 (the subset and Structure), 22 (Scope, Parameters), 27 (Datum and Program rows) and 10, with D-154, D-155, D-018 and D-049: 29 requirements, REQ-MDL-001 to 029, all Draft. `src/splintercam/model/DECISIONS.md` holds DEC-MDL-001 to 008. No code until the SPEC is Reviewed.
- One spec review round and one fix check (D-159): three must-fix findings addressed in the draft: integer and float fields accepted `bool` and other types (JSON's `true` would pass as T1 or tol 1 mm; REQ-MDL-029), the profile could not declare research 22's air gap factor (a dimensionless unit added), and a parameter dict kept a checked job mutable (pairs instead). Spec gaps folded in: a setup without operations is refused, dependent checks skipped, cancellation and declaration errors made exact.
- Left to other steps, named in the SPEC's Scope: the stock containing the part, z_bottom below z_top, the step-down against the flute length and the allowance above −R (step 5, the profile); heights from the stock top (`toolpath`); program name and number (steps 6 and 7).
- Size: about 220 NLOC estimated against the step's 200, under the 50 % stop.
- Questions for Peter: AQ-002 (the SPEC review, with four choices: drawing frame as work frame, spindle CW and coolant on without fields, the range of a point's a, declarations in model) and AQ-003 (`model`'s budget 260 and research list in `architecture/modules.yaml`), in `docs/agents/QUESTIONS.md`.
- Next: on approval, the implementation pull request: `src/splintercam/model/` with `__init__.py`, `AGENTS.md` and tests first.

### 2026-10-25, step 3 (SPEC reviewed)

- Peter answered AQ-002 and AQ-003 (under Decisions). Item 3 applied: REQ-MDL-006 now takes any a ≥ 0 (D-154) and reports `TOOL_POINT_ABOVE_FLUTE` (warning, the point kept) above the flute length, naming the shift of every Z; DEC-MDL-004 rewritten as Peter's decision, DEC-MDL-001, 002 and 006 no longer provisional. `src/splintercam/model/SPEC.md` Reviewed, REQ-MDL-001 to 029 all Reviewed; `model`'s budget 260 in `architecture/modules.yaml`.
- Next: after pull request #75 is merged, the implementation on a new branch from `main` (docs/dev/07, no stacked pull requests): `src/splintercam/model/` with `__init__.py` and `AGENTS.md`, tests in `tests/model/` first, tagged with REQ-MDL IDs.

## Backlog

## Blockers


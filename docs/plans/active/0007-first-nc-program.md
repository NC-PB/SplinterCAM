# Plan 0007: the first NC program (a thin vertical slice)

<!-- Lives in docs/plans/active/ while work is ongoing, then moves to docs/plans/completed/.
     The agent updates the progress log as the work goes (docs/dev/07). -->

- **Status: proposal, written by Claude in Project Spike on 2026-10-11. Waiting for Peter's approval and his answers below. Do not start any step before that.**
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

1. **Which operation first?** Recommended: an outside profile of a closed contour. It starts beside the part in air, so it needs no entry into material, and it uses `offset_region` (GROW) as built. A pocket needs entry moves and pass order and comes second.
2. **Which machine?** Recommended: the NCXchange machine file with the most complete compiler today; the agent checks which of `fanuc-mill-30i.toml`, `heidenhain-itnc530.toml` and `siemens-840dsl-mill.toml` compiles the NCX words this slice needs without warnings, and you pick one of those.
3. **How does the slice get `ncx`?** NCXchange has no release tag yet (R1-01). Recommended: CI builds `ncx` from a pinned NCXchange commit (needs the .NET SDK in one CI job); locally the test runs when `ncx` is on the path and is skipped with a visible message otherwise. When R1-01 ships, the pin becomes the tag.
4. **Moves between depth passes:** recommended: retract to the clearance height, rapid back over the start point outside the stock, feed down to the next depth outside the stock. Safe and simple; staying down comes with the link rules of topic 10.
5. **Is the program right?** Recommended: you run the NC program in the control's simulation or dry run on one machine, as the slice's last check. A test cannot replace that the first time.

## Steps

<!-- Each step has a size estimate (kept code + tests). At 50 % over it, stop and ask (docs/dev/12, section 3). -->

- [ ] 1. **Research pull** (Project Spike): topics 21 (DXF part), 22 (outside profile), 10 (clearance-height links only), 26 (the record subset: rapid, linear, arc, feed, spindle, tool, work offset, comment) and 27 (the NCX words for that subset, and how `ncx` is called) at L4 for these parts, moved to `docs/research/`. Size: docs only.
- [ ] 2. **`io`: DXF to curve rows.** ezdxf; closed chains of lines, arcs and bulges in millimetres; a file without units refused with a diagnostic (D-033); part size reported. Size: about 200 + 250.
- [ ] 3. **`model`: the slice's job data.** Tool (flat end mill, measurement point), stock box, setup (work offset, frame), operation parameters as declarations (D-018), held in memory. Size: about 200 + 200.
- [ ] 4. **`cl`: the toolpath record subset** of topic 26: moves, feeds, spindle, tool, work offset, comments, operation name and note (feature map, section 6). Size: about 150 + 200.
- [ ] 5. **`strategies/profile` with the slice's `toolpath` links.** `offset_region` GROW of the material contour by R + allowance; depth passes; start point; climb; clearance-height retract. Size: about 250 + 300.
- [ ] 6. **`ncx`: the writer and the call.** NCX at the resolution of D-149; `ncx check --strict` and `ncx compile` run as a subprocess; NCXchange's messages mapped to the operation (feature map, section 8). Size: about 200 + 250.
- [ ] 7. **`job` and `apps/cli`.** A small job file (JSON) naming the DXF, stock, tool, setup and operation; `splintercam run job.json` writes the NCX and the NC program. End-to-end test: a rectangle with filleted corners → `ncx check --strict` passes, the NC program compiles; a golden case `profile-rectangle-fillets` in `testdata/zoo/`. Size: about 200 + 250.
- [ ] 8. **Peter's dry run** on the chosen machine's control or simulator; findings back as decisions or research requests; handover.

Stop after each step for Peter's review of its pull request; stop before step 2 for his answers above.

## Decisions

## Progress log

## Backlog

## Blockers

- Peter's approval and answers to the questions above.

# Plan 0009: the setup sheet

<!-- Lives in docs/plans/active/ while work is ongoing, then moves to docs/plans/completed/.
     The agent updates the progress log at the end of every session, before stopping: one new file per entry in
     docs/plans/active/0009-log/YYYY-MM-DD-<slug>.md, not an edit of this file. -->

- **Status: approved by Peter on 2026-11-08, AQ-055 to AQ-059 as recommended (AQ-059 item 2 superseded by AQ-051).** The SPEC draft is Reviewed with these answers.
- Goal: every NC program SplinterCAM writes has a setup sheet next to it that states, with numbers computed from the job and the toolpath record, what the program does not say and the CAM does not check (AQ-035 notes 1 to 8), so a program can go to an operator other than Peter (AQ-035: "no program of the slice goes to an operator other than Peter until a setup sheet exists").
- Why now: plan 0007's program reached Peter's dry run (step 8) with its setup notes held by hand in `testdata/zoo/profile-rectangle-fillets/README.md` and `docs/plans/active/0007-log/2026-10-31-step8-dry-run-checklist.md`. Peter, 2026-11-08: "setup sheet plan".
- Specs: `src/splintercam/setupsheet/SPEC.md` (new, Draft); `src/splintercam/job/SPEC.md` (step 4: the sheet in stage 9); `src/splintercam/apps/cli/SPEC.md` (step 5: the sheet's file named).
- Research: `docs/research/10-linking.md` (Method 1 to 5, traps 1 and 2), `docs/research/26-toolpath-record.md` (measurement points), `docs/research/27-machines-and-controllers.md` (Datum row; no stock word), `docs/research/22-2d-operations.md` (Method 6). Project Spike: `product/feature-map.md`, section 8 (the setup sheet row, Peter 2026-10-03); `QUESTIONS.md`, Q-137 item 5 (open: templates later, release 1 the fixed sheet); research 30 is L0 (fixtures not researched). RR-023.
- Branch: this draft `plan0009/setup-sheet-draft` (docs only); then one pull request per step from `main`.
- Owner: Peter Burgener; agents: Claude Code sessions.

## What the slice's sheet holds

For one program of one setup (`src/splintercam/setupsheet/SPEC.md`, REQ-SHT-001 to 019), every value from the job, the `cl` record, the part's contour or the file names:

| Section | Contents | Source |
| --- | --- | --- |
| Banner | "Not yet run on a machine: dry run first, with this sheet in hand." | AQ-035; plan 0007 step 8 |
| Program and files | program name and number, NCX file, compiled files, machine file, job file, part file (names only) | feature map, section 8 header |
| By hand | material, programmer, date: empty fields | AQ-056; D-055 (no clock) |
| Part, datum, work offset | part box and size; work offset n (NCX `ORIGIN=n`); datum at the drawing's origin; the stock's six faces as coordinates | checklist item 2; DEC-MDL-002 |
| Blank | the stock box; "the program defines no blank: enter it by hand for the control's graphics" | AQ-010; AQ-035 item 3 |
| Tools | per tool in order of use: T, flat end mill, D, flute length, each point used: k, a, r, where it lies; "the program holds neither the diameter nor the point" | D-151, D-154; AQ-035 item 7 |
| Operations | name, strategy, T and k, spindle (CW), coolant on, tol, feeds by class, h_c, h_r, lowest Z | research 26 subset |
| Approach points | per operation: X, Y, descents, rapid to, lowest Z, feed; the stock face it lies off, its distance and the gap ("nothing may stand here; in a vice often inside the jaw's footprint; a blank beyond <coordinate> on this side is plunged into") | AQ-021; AQ-035 items 1 and 3 |
| Witness marks | S and the contact point, on every pass that starts there | AQ-016 item 7; AQ-035 item 6 |
| Keep-out | the reach below h_c (box grown by R, from the lowest Z to h_c) and the keep-clear box (reach + 5 mm, provisional): no clamp, jaw or vice inside; the stock held from below or gripped only below the reach's bottom; everything below h_c where the tool rapids; a note where the tool reaches the stock bottom | AQ-015 item 1 (a); AQ-016 item 4; AQ-035 items 2 and 4; AQ-056 item 1 |
| Dry run | at each operation's start a rapid along Z alone at the tool-change position, then across; stop if the machine moves otherwise; where each operation ends | AQ-015 item 3 (a); AQ-035 item 8; checklist items 7 and 11 |

For the golden job: reach X −10 to 110, Y −16 to 70, Z −10 to 5; keep-clear X −15 to 115, Y −21 to 75; P X 50, Y −11, 6 mm off the −Y face, gap 1 (blank limit Y −6), three descents at F 300 to Z −10; witness mark at X 50, Y 0 on 3 passes; T1 D 10, flute 30, at the tip (a 0, r 0). AQ-035 item 2's 15 mm band is the tool's edge plus 5 mm but misses the tool at P (Y −16); the keep-clear box keeps its margin and adds P (DEC-SHT-002, AQ-056 item 1).

Left out of the feature map's row in the slice (AQ-056): pictures, holders and stick-out, cutting times and totals, previous setup's stock, free notes, PDF, templates, translations; AQ-035 item 5 (full slot), which needs the stock model.

Format and place (AQ-055, AQ-058): one HTML file, `<program name>.setup.html`, English, written by `job` into the output folder with the compiled files after a clean `ncx` run; no NC program without its sheet.

Module (AQ-057, DEC-SHT-001): a new module `setupsheet`, layer 4, `depends_on: [foundation, geometry2d, model, cl]`, budget 400; `job` gains it in its `depends_on` and its budget rises from 520 to 570. The exact lines are in AQ-057; the Project Spike session applies them.

## Steps

<!-- Each step has a size estimate (kept code and tests), given as about 1.5 times the first count (Peter, 2026-10-25). At 50 % over it, stop and ask (docs/dev/12, section 3). -->

- [x] 1. This draft: the plan, `src/splintercam/setupsheet/SPEC.md` and `DECISIONS.md` (Draft), AQ-055 to AQ-059, RR-023; spec-reviewer round. Docs only. **Stop for Peter's review**: the SPEC becomes Reviewed and `architecture/modules.yaml` gets AQ-057's lines before step 2.
- [ ] 2. `setupsheet`: the types and `make_setup_sheet`, REQ-SHT-001, 002, 005 to 016 (values), 019; the glossary entry "setup sheet"; size: about 290 NLOC + 450 lines of tests (first count 195 + 300). Its own pull request (a new algorithm).
- [ ] 3. `setupsheet`: `render_html`, REQ-SHT-003, 004, 017, 018, the sentences of 006 to 016; size: about 100 NLOC + 200 lines of tests (first count 65 + 135). Its own pull request; with step 2 the module is about 390 of its 400.
- [ ] 4. `job`: stage 9 makes the sheet after a clean `ncx` run, writes it into the staging folder, moves it with the compiled files, withholds it with them (`strict`, errors), and names it in `JobReport.setup_sheet`; a failure to write it withholds the NC program (AQ-058). SPEC change first (REQ-JOB-001, 019 amended; a new requirement and failure code), for Peter's review in the same pull request. The golden case's `case.json` gains the sheet's values; its `README.md` "Setup notes" points to the sheet. Size: about 45 NLOC + 150 lines of tests (first count 30 + 100); `job` from 518 to about 563 of 570.
- [ ] 5. `apps/cli`: the run's summary names the sheet's file (REQ-CLI amended); size: about 8 NLOC + 30 lines of tests (first count 5 + 20).
- [ ] 6. Peter reads the golden job's sheet and runs the dry run with it in hand (plan 0007 step 8, repeated with the sheet). Findings go back as decisions or research requests. **Stop**: Peter decides AQ-059 item 1 (the program to other operators) on that result.

Reviews per code step (CLAUDE.md): simplifier, test-auditor, spec-reviewer; cnc-reviewer on steps 2 to 4 (the sheet is what reaches the machine's operator, and step 4 changes what `job` puts next to the NC program).

## Decisions

- 2026-11-08: plan approved (Peter): HTML, English; the contents of AQ-056 with a 5 mm keep-clear margin; a new module `setupsheet` (budget 400) and `job` at 570 (AQ-057, applied); the sheet only together with the compiled files (AQ-058); programs to other operators only after Peter's dry run with a sheet (AQ-059 item 1). k ≠ 1 and a ≠ 0 are allowed with a comment in the program (AQ-051), so the sheet repeats the point and a.
- 2026-11-08: content (step 2) and rendering (step 3) are separate steps and pull requests, because the computed values are tested as data and the HTML only as their printout, and a later PDF, template or translation replaces step 3 alone.
- 2026-11-08: the `job` and `apps/cli` changes come after the module (steps 4, 5), one module per pull request (AGENTS.md, Done means).

## Progress log

Entries are files in `docs/plans/active/0009-log/`.

## Backlog

- The `sheet` command of the command line (feature map, section 1), when the job container exists.
- The controller's name for the work offset next to its index, once NCXchange provides it (RR-023).
- The full-slot note (AQ-035 item 5) with the stock model.
- The keep-clear margin as a job or shop setting, if Peter wants one other than his fixed number (AQ-056 item 1).

## Blockers

- AQ-055 to AQ-059 (Peter); AQ-057's `architecture/modules.yaml` lines (protected; the Project Spike session applies them).

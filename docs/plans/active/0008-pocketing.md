# Plan 0008: the first pocket (a closed pocket with islands)

<!-- Lives in docs/plans/active/ while work is ongoing, then moves to docs/plans/completed/.
     The agent updates the progress log as the work goes (docs/dev/07). -->

- **Status: approved by Peter on 2026-11-08, all five questions answered as recommended (below).** Step 1 (the research pull) is `docs/research/04-pocketing.md`; step 2 starts when the pull request with both files is on `main`. The patent check of D-143 (Risks, 2) runs in Project Spike before step 6's SPEC review.
- Goal: one closed pocket from a drawing to an NC program: a DXF with an outer loop and islands → contour-parallel clearing from the inside out, climb, helix entries, equal depth passes → the toolpath record → NCX → `ncx check --strict` passes and NCXchange compiles it for the plan 0007 machine. Every module on the way grows only as far as the pocket needs.
- Why now: plan 0007 proved the chain io → model → cl → toolpath → strategy → ncx → job for a profile that starts in air. A pocket is the first operation that enters material, cuts several loops per level and links them, which is what most release 1 parts need next (D-025: contour-parallel pockets with islands).
- Specs: one SPEC for the new module `strategies/pocket`; changes to the SPECs of io, cl, ncx, toolpath and job, each cut to this slice (D-160).
- Research: `docs/research/04-pocketing.md` at L4 for this slice (new in SplinterCAM, moved from Project Spike under D-158); research 02, 10, 22, 26 and 27 as they are. Research requests go to `docs/research/REQUESTS.md`.
- Branch: one pull request per step, from `main` after the previous merge, never stacked; steps 2 to 5 may run in parallel lanes once their SPEC changes are approved (plan 0007, Decisions, 2026-10-27).
- Owner: Peter Burgener; agents: Claude Code sessions.

## Scope of the slice

In: a DXF in millimetres with one closed outer loop and any number of islands inside it (lines, arcs, bulges); a box stock containing the pocket; one flat end mill entered by hand; spindle speed, cutting and plunge feed entered by hand; side and floor allowance; stepover up to the tool radius; contour-parallel levels with the coverage check; inside-out order, climb only; one helix entry per leaf of the level tree, at every depth level; loops of one level joined by short cut links; retract to the clearance height between branches and between depth levels; equal depth passes; NCX for one machine file; `ncx check --strict` and `ncx compile`; an offline check as in plan 0007, step 8.

Out (later plans): stepover above R (D-094), slot-through between branches (D-045) and feed classes (D-089), corner fillets (D-046, D-109), ramp and pre-drilled entries, the tool's RMPX (Q-120), finishing passes on wall and floor, open pockets, several pockets in one operation, zigzag and raster (D-088), spirals (D-129), rest machining (D-083), conventional and outside-in order, arc fitting (D-023), the stock update (D-026), the GUI. The full list is in `docs/research/04-pocketing.md`, Scope.

## Questions for Peter (machining terms, each with a recommendation)

Five questions (D-160). Settled by decisions and not asked: climb only and inside-out (D-032); no zigzag or raster in release 1 (D-025, D-088). Not asked unless you object: the machine stays the Heidenhain iTNC 530 of plan 0007 (your pick of 2026-10-11), and step 4 also compiles the helix on the Fanuc and Siemens mill files; the test on the machine stays open as in plan 0007, step 8, with the offline check standing in.

1. **How does the tool get into the material?**
   - (a) **Recommended:** a helix in each leaf of the pocket, radius 0.9·R where it fits and down to 0.2·R (D-079), angle 2° by default (D-079's fallback for steel, stainless, cast iron, heat-resistant alloys and hardened steel; 5° allowed for aluminium), a full flat circle at the bottom, then out along the seam. Where not even 0.2·R fits (a slot narrower than about 2.4·R, for example 11.6 mm for a 10 mm tool), the operation is refused and names the place. Each later depth level enters at the same point, 1 mm above the floor just cut (0.2·R for a 10 mm tool), in the cleared bore.
   - (b) A zigzag ramp along a straight line: needs no helix in the record and NCX, but a straight run inside the pocket; at 2° it travels 114.5 mm per 4 mm of depth.
   - (c) Plunge at points you give, pre-drilled in an earlier operation: needs the drilling strategy first.
   - What happens: with (a) the machine runs a helical G2/G3 (Heidenhain `CP IPA`) at the plunge feed; the tool never plunges straight into material.
2. **Stepover, the distance between neighbouring loops.**
   - (a) **Recommended:** default 0.5·D (one radius), allowed 0.05·D to 0.5·D in this plan. At one radius or less contour-parallel loops leave nothing in the corners or the middle (Held 1991, p. 25: what most systems use). Above it, loops leave material in corners and a core in the middle (a 100 mm square with a 10 mm tool at 9 mm stepover keeps 71 mm²), which needs D-094's local reduction, a later plan.
   - (b) Default 0.4·D, same range: a little less load on the straights, about 25 % more path.
   - What happens on the machine: on a straight the tool cuts 90° of its circle at 0.5·D, 60° at 0.25·D; see question 4 for the corners.
3. **Islands, and pockets that split into branches.**
   - (a) **Recommended:** islands are in (any number, no island in an island). Where the pocket splits into separate branches (left and right of an island, for example), each branch gets its own helix after a retract to the clearance height. This takes the retract branch of D-045 everywhere, because the slot-through it prefers needs a slot feed that the slice does not have (D-089).
   - (b) Slot through from one branch to the next at the cutting feed, as D-045 allows where the tool fits: fewer entries, but long full-width cuts at a feed set for ordinary cutting.
   - What happens: in the golden case (a) gives two helices per depth level instead of one.
4. **Corners and full-width moments.**
   - (a) **Recommended:** no corner treatment in this plan. At a 90° corner the tool cuts about 150° of its circle at 0.25·D stepover and about 180° at 0.5·D, and the step-outs between loops are short full-width cuts (about one stepover long). The slice has one cutting feed for all of it, so it must be a feed the tool takes in a full slot at the chosen depth; the setup sheet says so. Corner fillets (D-046, off by default anyway) and a separate slot feed (D-089) come later.
   - (b) Add D-046's corner fillet option now, with D-109's cap: lower corner load, more code and a second coverage rule in this plan.
5. **Finishing.**
   - (a) **Recommended:** no finishing passes in this plan. Side and floor allowance are parameters (default 0), so you can leave material and finish it with a later operation. With allowance 0 the outermost loop cuts the wall at every depth level, which leaves a fine step on the wall at each level.
   - (b) A wall finishing pass at full depth in this plan: it needs a lead-in arc and lead-out (research 10 in Project Spike, not yet at L4) or it marks the wall where it starts.

## Steps

<!-- Each step has a size estimate (kept code + tests). At 50 % over it, stop and ask (docs/dev/12, section 3).
     Every estimate is about 1.5 times the first count (Peter, 2026-10-25). -->

- [ ] 1. **Research pull** (Project Spike): `docs/research/04-pocketing.md` new, at L4 for this slice; findings on Project Spike's topics 04 and 10 recorded there; the patent check of D-143 for contour-parallel clearing (see Risks). Size: docs only.
- [ ] 2. **`io`: one region of several loops.** Every closed chain on the selected layer, handed to geometry2d's loop tree as one outer loop and its islands; `DXF_CONTOUR_COUNT` becomes "no closed chain"; open chains still stop the import. A new entry point beside `read_dxf_contour`, which stays for the profile (an interface change, yours to approve). Size: first count about 50, so about 75 NLOC + 150 of tests; io stands at 795 of its 820 budget, so a new budget of about 900 in `architecture/modules.yaml` (yours).
- [ ] 3. **`cl`: helix turns and the role PLUNGE.** An ARC may change z (REQ-CL-015 relaxed) when its sweep is ±2π and it ends above its start in XY, one turn per record; role PLUNGE on LINE and ARC moves (research 26, Roles). Size: about 25, so about 40 NLOC + 100 of tests; cl's budget 310.
- [ ] 4. **`ncx`: the helix in NCX.** `ARC=CCW IZ=… CENTER:X=… CENTER:Y=… ANGLE=360` per turn (research 26, Mapping onto NCX; avoids NCXchange's D268); the golden program through `ncx check --strict` and `ncx compile` on `heidenhain-itnc530.toml`, and compiled on the Fanuc and Siemens mill files as a check. Size: about 25, so about 40 NLOC + 100 of tests.
- [ ] 5. **`toolpath`: entries inside the pocket.** Several chains per depth level; per chain RAPID to the entry point at h_c, RAPID to h_r, LINE to the helix start at the plunge feed, the strategy's moves, RAPID along Z to h_c; REQ-TP-012's "descent beside the stock" kept for the profile and replaced by "descent at a declared entry point" for the pocket. Size: about 60, so about 90 NLOC + 200 of tests; toolpath stands at 182 of 165, so a new budget of about 280 (yours).
- [ ] 6. **`strategies/pocket`.** SPEC first (about 30 requirements), then the code: region checks, levels, nesting and tree, the coverage check, entry points and helix radius, seams, chains, the loop tour, helix turns, depth levels, header (`docs/research/04-pocketing.md`, Method 1 to 12). `offset2d` added to its `depends_on` in `architecture/modules.yaml` (yours, as AQ-017 for the profile). Size: first count about 400 (checks 70, levels and tree 70, coverage 25, entry and seam 95, chains and tour 100, helix and levels 40), so about 600 NLOC + 600 of tests; budget 600.
- [ ] 7. **`job` and `apps/cli`.** The registry entry `pocket` (D-173, REQ-JOB-013), the job file's part read through step 2's entry point for a pocket; the end-to-end test and the golden case `pocket-rectangle-island` in `testdata/zoo/`. Size: about 40, so about 60 NLOC + 150 of tests.
- [ ] 8. **Offline check and machine test.** NCXchange's virtual machine (`ncx trace`, `ncx analyze`) and a geometric check of the path against the part (every cut centre at least R + e from the walls and islands, the coverage rest empty), as `docs/plans/active/0007-log/2026-11-08-step8-offline-check.md`; the dry run on the iTNC 530 when a machine is at hand, with the checklist of plan 0007 extended by the helix and the branch retracts.

Code in all: about 905 NLOC by the rule, about 1400 lines of tests. Stop after each step for Peter's review of its pull request, or merge under docs/dev/07's rule.

## The golden case `pocket-rectangle-island`

- Part: the rectangle (0, 0) to (80, 50) with corner fillets of radius 8; one round island of radius 6 about (41, 20). Pocket area 3831.96 mm². Stock box (−10, −10, −30) to (90, 60, 0).
- Tool: flat end mill D = 10 (R = 5), flute length 25. Allowances 0. Stepover 0.5·D = 5. z_top = 0, z_bottom = −8, step-down 4. Helix angle 2°, air gap 0.2·R = 1 mm.
- Expected: three loop levels at 5, 10 and 15 mm from the walls and the island: one ring round the island (outer loop 214.85, hole 69.12), one loop without a hole (the gap below the island has closed), two separate loops left and right of the island. The coverage check leaves nothing. Two leaves, so two helices per depth level, each 4.5 mm in radius with 6 turns of 0.833 mm (1.69°) from 1 mm above the floor before. Depth levels −4 and −8. Per level: the left branch alone, a retract, then the right branch stepping out to the middle loop and to the ring, where the hole loop and the outer loop are joined by one 4 mm link at x = 41 below the island, cut there and back. About 647 mm of cutting per level besides the helices.
- Checks: `ncx check --strict` clean, `ncx compile` for the iTNC 530 with `CMP020` only; Test 12's invariants of `docs/research/04-pocketing.md`.

## Decisions

- 2026-11-08: plan approved; Peter's answers to questions 1 to 5 as recommended: (1) a helix in each leaf, 0.9·R down to 0.2·R, 2° by default (5° for aluminium), refused where 0.2·R does not fit; (2) stepover default 0.5·D, range 0.05 to 0.5·D; (3) islands in, each branch its own helix after a retract (D-045's retract branch); (4) no corner treatment, one cutting feed that must suit a full slot, said on the setup sheet; (5) no finishing pass, side and floor allowance only. The machine stays the iTNC 530; the machine test stays open as in plan 0007, step 8. `strategies/pocket` gains offset2d in `depends_on` and the budget 600 of step 6's estimate (Project Spike session).

## Risks

1. **The helix is the first move kind beyond plan 0007's subset.** The NCX words exist (SRC-112), but no plan has compiled a helix on the iTNC 530 yet; NCXchange's D268 (a Heidenhain helix of one turn or less as `C`/`CR` with Z) is avoided by the `ANGLE` form, and the helix feed rule of D-096 is still on NCXchange's list (it changes the feed by at most 0.4 % at 5°). Step 4 runs the compile first; if it fails, the fallback is question 1 (b), a ramp of LINE moves, which needs a short research pull.
2. **Patent clearance (D-143).** D-143 asks for a claim chart for every active patent found before a clearing strategy is specified. The searches so far (Q-042, D-064, T-042) covered adaptive and spiral clearing; US 7,577,490 (in force until 2026-12-17) is registered but not read (SRC-172). Contour-parallel offset pocketing is old public practice (Held 1991 surveys it), and the slice follows D-130's rules, but the check must be recorded before step 6's SPEC is approved, or you decide that the existing searches cover it.
3. **Size.** `strategies/pocket` is the largest strategy so far (about 600 NLOC); io and toolpath are already at or over their budgets. If step 6's SPEC exceeds about 30 requirements, the loop tour (Method 8) moves to a step of its own.
4. **Feed in corners.** One cutting feed for moves that reach full-width engagement (question 4). A feed set for 90° engagement can overload a small tool in the corners; the setup sheet and the dry run checklist must say it.
5. **Refused pockets.** The entry point is the centroid of each leaf, not the deepest point; narrow or crescent-shaped leaves can be refused although a helix would fit elsewhere. The refusal names the place; better points need the medial axis (release 2, D-035).
6. **Critical distances.** Where a level falls exactly at a strait's half-width, the level tree changes with tiny input changes (REQ-OFF-026); tests keep at least 1 mm away, real parts will not.
7. **No machine test.** As in plan 0007, the first programs are checked offline only; they are marked as not yet tested on a machine.

## Progress log

(empty)

## Backlog

## Blockers

- Answers to questions 1 to 5.
- D-143's record for contour-parallel clearing (Risk 2), before step 6's SPEC review.

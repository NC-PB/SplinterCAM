# Plan 0005: offset2d, the offsets and Booleans of topic 02 (draft)

<!-- Lives in docs/plans/active/ while work is ongoing, then moves to docs/plans/completed/.
     The agent updates the progress log at the end of every session, before stopping. -->

- Goal: a module `offset2d` offsets the machining regions of geometry2d by a clearance t ≥ 0 on a side (D-058, D-132) and joins and subtracts regions (the Booleans of topic 02), with source IDs and fixed nodes carried through for the arc fit (D-023, D-084).
- Specs: `src/splintercam/offset2d/SPEC.md` (Reviewed by Peter, 2026-10-08; decisions in `src/splintercam/offset2d/DECISIONS.md`)
- Research: `docs/research/02-offsets-and-booleans.md` (L4, reviewed 2026-10-08; PR 45)
- Branch: one pull request per step from `main`, never stacked (docs/dev/07)
- Owner: Peter Burgener; agents: Claude Code sessions
- Status (2026-10-08): draft. Peter decided the module (DEC-G2D-038), approved its entry and budget and answered both questions (DEC-G2D-040). Research 02 is in; Peter reviewed the SPEC and answered its four questions (DEC-OFF-001 to 006), which releases steps 2 to 9. REQ-OFF-032 waits for pull request 47.

## The module

The entry in `architecture/modules.yaml` (approved by Peter, 2026-10-08, and applied):

```yaml
  offset2d:               { layer: 1, kernel: true,  depends_on: [foundation, geometry2d], kernel_includes: [geometry2d], research: ["02"], budget: 1500 }
```

- Layer 1, beside geometry2d (Peter, 2026-10-08): a module imports only lower layers, or same-layer modules named in its `depends_on`; all `depends_on` together form no cycle; no strategy imports another strategy. `tools/arch-check` checks exactly these three (DEC-G2D-040).
- `kernel_includes: [geometry2d]`: its C++ includes the headers geometry2d's SPEC names as its kernel interface (`kernel/exact.hpp`, `kernel/distance.hpp`, `kernel/grid.hpp`) and links their sources; a change to them is an interface change, Peter's (DEC-G2D-040).
- Kernel: the Clipper2 offset runs in C++ (`ClipperOffset`, Clipper2 2.0.1, as geometry2d's grid bridge).
- Budget 1500 NLOC, an estimate to be revised at the SPEC cut. For scale: geometry2d's grid bridge and region code measure about 400 NLOC (`kernel/grid.cpp`, `_grid.py`, `_build.py` and their bindings). The offset adds the clearance and side of D-132 with its bias and rounding margin, round and miter joins, the PolyTree built inside the offset call so the rounding is paid once (DEC-G2D-026), the Booleans, and source IDs and fixed nodes through all of them.
- geometry2d's own entry dropped research "02": `research: ["03"]`; "03" leaves with the medial-axis module when that is planned.
- The grid span: 2^26 grid units, about 6.7 m at u = 0.0001 mm, is enough for release 1 (Peter); larger machines come later through a coarser grid unit per job, not now. It becomes a declared foundation parameter in its own pull request.

## Questions for Peter

Both answered on 2026-10-08 (DEC-G2D-040): 1 as proposed, with the headers named in geometry2d's SPEC as its kernel interface; 2 as proposed.

1. **How does offset2d's kernel reach geometry2d's grid bridge and exact predicates?** The rule kernels-private lets only a module's own Python call its kernel. Proposal: offset2d's C++ includes geometry2d's kernel headers (`grid.hpp`, `exact.hpp`) and links its sources, listed as a kernel dependency in `modules.yaml`; the alternative, moving the grid bridge into offset2d, would leave geometry2d's region and fallback calling another module's kernel.
2. **Where does the region's Clipper2 call live?** `build_region` (geometry2d) makes the PolyTree today. DEC-G2D-026 prefers building it inside the offset call. Proposal: geometry2d keeps `build_region` for the region itself; offset2d takes the flattened loops and builds its PolyTree in its own call, so geometry2d does not depend on offset2d.

## Steps

<!-- Each step has a size estimate (kept code and tests, raw added lines). At 50 % over it, stop and ask, as for a
     timebox (docs/dev/12, section 3). Every pull request: at most 400 added lines of non-test code. -->

Released with the SPEC (Peter, 2026-10-08). Steps 2 and 3 follow his answers 2 and 1 (DEC-OFF-002, 001).

- [x] 1. **SPEC review.** Peter reviews `src/splintercam/offset2d/SPEC.md` and answers its four questions; the requirements become `Reviewed`. Size: docs only.
- [x] 2. **foundation: the offset's parameters** (Open question 2). `ToleranceSet.arc_tol_mm`, `offset_bias_grid_units` and `join_steps_max` in `tolerance_defaults.toml`, and the diagnostic code `CANCELLED` (warning), with a foundation SPEC change (DEC-OFF-002). Size: about 50 + 70.
- [ ] 3. **geometry2d: the grid interface** (Open question 1, DEC-G2D-040). `frame_of`, `to_grid`, `split_pinches`, `shared_points` and `canonical` move from `kernel/grid.cpp` into `kernel/grid.hpp`, and `kernel/distance.hpp` gains the segments within eps_len of the nearest distance (DEC-OFF-001), with a geometry2d SPEC change; behaviour unchanged, geometry2d's tests pass as they are, new tests for the new entry. If an include directory is added for offset2d, `_quoted` in `tools/lib/arch_kernels.py` must resolve it (arch-check resolves quoted includes relative to the file only). Size: about 120 + 120.
- [ ] 4. **The region offset.** Scaffold `src/splintercam/offset2d/` (`tools/new-module` or by hand, as Peter says), `offset_region` with the loop tree and `flatten_loops` (REQ-OFF-021), the one `ClipperOffset` call (022), t = 0 through `build_region` (024), the span refusal (018), the band (025), integer topology (026), `OFFSET_EMPTY`, `OFFSET_FAILED`, `ValueError`, `CANCELLED` (039 to 042, 013, 014). Tests 6, 7, 8, 10, 11, 18 and 9's oracle. A new algorithm: its own pull request. Size: about 380 + 500.
- [ ] 5. **The orientation guard** (REQ-OFF-023). Test 21. Size: about 120 + 200.
- [ ] 6. **Source IDs with classes, pinch points, order** (REQ-OFF-034, 036 to 038, 011, 010). Tests 14, 15, 17, 19. Size: about 150 + 350.
- [ ] 7. **Booleans** (REQ-OFF-030, 031, 033, 035). Tests 1 to 5, Vatti note test 7. The stock update (`remove_machined`, REQ-OFF-032) follows research 02's answer to RR-001 (Booleans, test 22; pull request 47, DEC-OFF-006): REQ-OFF-032 is rewritten and released from it once it is on `main`, and joins this step. Size: about 180 + 350, plus the stock update once released.
- [ ] 8. **Open chains** (REQ-OFF-027 to 029). Tests 12 and 13. Size: about 260 + 350.
- [ ] 9. **Golden case and differential.** `pocket-island-touching-wall` (test 16; a person approves the golden files); an ADR that records D-060: shapely and GEOS in a test-only dependency group, never shipped, since GEOS is LGPL (DEC-OFF-003); then test 20. Size: about 0 + 250.

Total: about 1230 added lines of code (about 1050 NLOC) and 2080 of tests, in nine steps.

## Progress log

### 2026-10-08, step 2

- foundation: `ToleranceSet.arc_tol_mm` (REQ-FND-011), `offset_bias_grid_units` and `join_steps_max` in the defaults file (REQ-FND-012), the constant `CANCELLED` (REQ-FND-013); foundation SPEC changed, DEC-FND-001 records the form of `CANCELLED`. At tol_min the floor 2u binds (0.05·tol = 0.000114 mm < 0.0002 mm); at 0.01 and 0.05 mm the share does.

### 2026-10-08, SPEC review

- Pull request 46 merged. Peter answered the four questions as recommended and accepted the deviations: DEC-OFF-001 to 006 in `src/splintercam/offset2d/DECISIONS.md`; every requirement but REQ-OFF-032 `Reviewed`. Step 1 done.
- RR-001 answered in research 02 (Booleans, test 22), pull request 47: REQ-OFF-032 is released from that text after it merges.
- ADR drafted for DEC-OFF-003: `docs/adr/0010-shapely-geos-test-only.md` (Proposed; shapely/GEOS in a test-only group for test 20, D-060). A person decides before step 9.
- Test oracles for steps 4 to 9, written in parallel by a test-designer from the SPEC and research only: `tests/support/offset2d_oracles.py` (d to the true lines and arcs within 64·ε·S, inside on the true curves, the definitions of research 02, Booleans, a seeded sampler outside a band, the band widths from a `ToleranceSet`) and `offset2d_strategies.py` (test 7's nested shapes, pockets with islands, bulged pockets, test 21's touching island); self-tests in `tests/offset2d/` (48), untagged until offset2d code exists. Mutated by hand: each broken rule fails a test.
- Next: step 2 (foundation).

### 2026-10-08, SPEC draft

- Research 02 arrived (PR 45). `src/splintercam/offset2d/SPEC.md` drafted with `/research-to-spec`: REQ-OFF-010, 011, 013, 014 and 018 keep the prototype's numbers cited by the research, the new ones run from 020 to 042; draft REQ-OFF-009 (retry) is dropped, as research 02 says. Steps 1 to 9 proposed above.
- spec-reviewer round: six major and six minor findings, all applied (the SPEC's change log); REQ-OFF-043 added for trap 9; REQ-OFF-032 blocked by research request RR-001 (stock update margin).
- Four questions for Peter in the SPEC's Open questions: geometry2d's grid internals into `kernel/grid.hpp`; `arc_tol_mm` and two declared parameters in foundation; shapely for test 20 (an ADR); the function names.
- Next: Peter's review (step 1).

### 2026-10-08, draft

- Written on Peter's answer to plan 0004 (DEC-G2D-038): the module entry and budget proposed, two questions open.
- Peter's answers: entry approved (layer 1, budget 1500 as an estimate) and applied, with the layer rule settled (same-layer dependencies when named in `depends_on`); questions 1 and 2 as proposed; geometry2d's SPEC names its kernel interface (DEC-G2D-040). Next: research 02, then `/research-to-spec`; the first step moves `frame_of` and `to_grid` into `kernel/grid.hpp` as an interface change.

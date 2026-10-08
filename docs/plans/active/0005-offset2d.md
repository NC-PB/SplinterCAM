# Plan 0005: offset2d, the offsets and Booleans of topic 02 (draft)

<!-- Lives in docs/plans/active/ while work is ongoing, then moves to docs/plans/completed/.
     The agent updates the progress log at the end of every session, before stopping. -->

- Goal: a module `offset2d` offsets the machining regions of geometry2d by a clearance t ≥ 0 on a side (D-058, D-132) and joins and subtracts regions (the Booleans of topic 02), with source IDs and fixed nodes carried through for the arc fit (D-023, D-084).
- Specs: `src/splintercam/offset2d/SPEC.md`, to be cut from research 02 with `/research-to-spec` once it is in the repository
- Research: research 02 (not yet in `docs/research/`; plan 0004 asked for it)
- Branch: one pull request per step from `main`, never stacked (docs/dev/07)
- Owner: Peter Burgener; agents: Claude Code sessions
- Status (2026-10-08): draft. Peter decided the module (DEC-G2D-038), approved its entry and budget and answered both questions (DEC-G2D-040). No steps until research 02 is here.

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

None yet: they come from the SPEC cut of research 02.

## Progress log

### 2026-10-08, draft

- Written on Peter's answer to plan 0004 (DEC-G2D-038): the module entry and budget proposed, two questions open.
- Peter's answers: entry approved (layer 1, budget 1500 as an estimate) and applied, with the layer rule settled (same-layer dependencies when named in `depends_on`); questions 1 and 2 as proposed; geometry2d's SPEC names its kernel interface (DEC-G2D-040). Next: research 02, then `/research-to-spec`; the first step moves `frame_of` and `to_grid` into `kernel/grid.hpp` as an interface change.

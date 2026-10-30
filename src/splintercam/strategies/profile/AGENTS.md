# AGENTS.md: strategies/profile

Layer 3. The outside profile of one closed contour for plan 0007: the tool centre path from
offset2d's grow by R + s, clockwise for climb, equal depth passes, a start point S and an approach
point P beside the stock, the links from toolpath (research 22, Method 1 to 6). Contract:
`./SPEC.md`. Why it is built this way: `./DECISIONS.md` (read it before changing behaviour).
Public API: `./__init__.py`. No C++ part (DEC-PRF-006). Depends on: foundation, geometry2d,
offset2d, model, cl, toolpath.

## Commands

- `uv run pytest tests/strategies`

## Invariants that must never break

- REQ-PRF-011: the cut moves are offset2d's loop as it is, never shifted or smoothed; every cut
  point lies at least t = R + s from the true contour.
- REQ-PRF-020: the value checks all run, in REQ-PRF-003 to 009 order, before the offset; after
  it the first failure stops (`value_errors` in `_checks.py`, `_link_plan` in `_plan.py`).
- REQ-PRF-022, D-055: no trigonometry; `sqrt` and exact predicates only, in `_approach.py`.
- The pass rows are built from one points array (`level_passes`), so each row starts bit for bit
  where the one before it ends and the pass starts and ends at P (toolpath's REQ-TP-011).

## Known pitfalls

- The package folder `src/splintercam/strategies/` needs its `__init__.py`, or pyright strict
  reports every import of the strategy as a missing stub; `tools/arch-check` accepts that file
  only while it imports nothing (`_group_init` in `tools/lib/cmd_arch_check.py`).
- offset2d never calls `ctx.progress`: a test that cancels "during the offset" patches
  `splintercam.strategies.profile._plan.offset_region` by its dotted path.
- On research 22 test 1 the straight edges run on past the fillets' tangent points, along the
  flattened fillet (about 0.06 mm each end at tol 0.01): measure the sides with the band, not
  with their nominal length.
- `_pass_count` overflows `math.ceil` on a quotient that is not finite: every caller must run
  after `value_errors` has checked `countable` (REQ-PRF-008, DEC-PRF-010).
- Whether P differs from S is decided by comparing the points, not by d > 0: a d that rounds
  away would leave a zero-length APPROACH and RETRACT row in every pass (DEC-PRF-007).

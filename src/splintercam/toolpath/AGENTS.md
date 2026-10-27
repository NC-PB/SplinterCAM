# AGENTS.md: toolpath

Layer 3. The links of one operation for plan 0007: Z first after the tool change, over the
approach point P at the clearance height, per pass down to the retract height and fed down at P,
the pass, up to the clearance height (research 10, Method). Contract: `./SPEC.md`. Why it is built
this way: `./DECISIONS.md` (read it before changing behaviour). Public API: `./__init__.py`. No C++
part yet (DEC-TP-003). Depends on: foundation, model (`StockBox`, `FlatEndMill`), cl.

## Commands

- `tools/test-one toolpath`

## Invariants that must never break

- REQ-TP-013: the checks run rule by rule in the order of `plan_breach` in `_checks.py`; a pass
  rule runs over every pass before the next rule, so a rule only sees passes that passed the
  rules before it (`_level` and `_chain` index arrays REQ-TP-009 has checked).
- REQ-TP-014, D-055: no trigonometry and no floating-point NumPy reductions in a decision;
  REQ-TP-012's distance test stays the one scalar expression of DEC-TP-004, in its order.
- toolpath owns every move along Z and every rapid; a strategy hands over only the moves in the
  plane at a level (DEC-TP-001). Every move between passes is along Z at P (plan 0007, question 4).

## Known pitfalls

- REQ-TP-011 and cl's DEC-CL-004 compare exactly: a strategy must copy P itself into a pass's
  first start and last end, and each row's end into the next row's start, never a recomputed point.
- toolpath does not check arcs: an arc row off its circle passes here and is refused by cl's
  REQ-CL-016 inside `make_operation`; its move index is 2 + Σ_{k<i} (m_k + 3) + 2 + j (SPEC).
- `uv run ruff format <folder>` also formats the Python block inside `SPEC.md` (it lost its
  aligned comments once); format the `.py` files by name.

# AGENTS.md: <module>

<!-- Keep under 60 lines. Copy of the most important facts only; the contract is SPEC.md. -->

Layer <n>. Implements docs/research/<NN>. Contract: `./SPEC.md`. Public API: `./__init__.py`. C++ part: `./kernel/` (if any). Depends on: <modules>.

## Commands

- `tools/test-one <module>`
- `tools/render <case>` for the cases in `testdata/zoo/` that use this module: <case names>

## Invariants that must never break

- <REQ-XXX-001: one line>
- <REQ-XXX-002: one line>
- <three to six lines in total>

## Local rules

- <For example: all offsets go through `offset()` in `__init__.py`; only `kernel/offset.cpp` calls Clipper2.>
- Tolerance share of this module: <e.g. 30 % of the operation's chord tolerance> (SPEC.md, "Tolerance budget").

## Known pitfalls

- RESEARCH 18 (Project Spike), items <…>.
- <Add one line when an agent trips over something in this module.>

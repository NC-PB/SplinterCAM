# Developer guide

> Part of Project Spike: the design concept for the code repository. The scaffold built from it is `test_repo` (its docs folder is a snapshot of 2026-09-27). Change the concept here, not there.

How SplinterCAM is built, and why. Agents start from `test_repo/AGENTS.md` and read these documents only when a task needs them.

| # | Document | Question it answers |
| --- | --- | --- |
| 01 | [AI-first principles](01-ai-first-principles.md) | What does "AI coding first" mean here? |
| 02 | [Repository layout](02-repository-layout.md) | Where does everything live, and why? |
| 03 | [Architecture rules](03-architecture-rules.md) | Which modules exist, and which may depend on which? |
| 04 | [Code conventions](04-code-conventions.md) | How must Python and C++ code look? |
| 05 | [Specs, plans and decisions](05-specs-plans-decisions.md) | How do requirements get from research into code? |
| 06 | [Testing and quality gates](06-testing-and-quality-gates.md) | What must pass before a change counts as done? |
| 07 | [Agent workflow](07-agent-workflow.md) | How does a task go from idea to merged code? |
| 08 | [Agent instruction files](08-agent-instruction-files.md) | What goes into AGENTS.md, CLAUDE.md, rules, skills and hooks? |
| 09 | [Dependencies, licensing and provenance](09-dependencies-licensing-provenance.md) | Which code and data may enter the repository? |
| 10 | [Stack decision](10-stack-decision.md) | How the stack was chosen |
| 11 | [User interface](11-user-interface.md) | Layout, generated operation panels, selection slots, simulation workspace |
| 12 | [Lean code](12-lean-code.md) | How does the code stay small: limits, checks, reviews that subtract, throwaway code? |

Also: [decisions](../decisions/README.md), plans (`test_repo/docs/plans/active`), [research](../research/README.md), `test_repo/docs/templates`, [glossary](../glossary.md), [feature specs](../specs/README.md).

# Developer guide

> Came from Project Spike's design concept on 2026-10-02 (D-156; [docs/spike/README.md](../spike/README.md)). It is mastered here now (D-158): change these documents in this repository.

How SplinterCAM is built, and why. Agents start from [`AGENTS.md`](../../AGENTS.md) and read these documents only when a task needs them.

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

Also: [ADRs](../adr/README.md), [decisions](../spike/decisions-snapshot.md) and [sources](../spike/sources-snapshot.md) (snapshots), [plans](../plans/active), research ([01](../research/01-foundations.md); the index and the other topics: Project Spike), [templates](../templates), [glossary](../glossary.md), feature specs (`docs/specs/`, none yet).

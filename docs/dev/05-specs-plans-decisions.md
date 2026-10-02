[Index](README.md) · [← 04. Code conventions](04-code-conventions.md) · [06. Testing and quality gates →](06-testing-and-quality-gates.md)

# 05. Specs, plans and decisions

Agents are good at implementing a clear contract and bad at inventing one. This document defines where the contracts live, how they are written, and how work that spans several sessions is planned and handed over.

## The chain from knowledge to code

| Artefact | Where | Answers | Written by | Changes |
| --- | --- | --- | --- | --- |
| Research | `docs/research/NN-*.md` | How does the maths work, what goes wrong? | People, agents drafting | Rarely |
| Module spec | `src/splintercam/<m>/SPEC.md` | What must this module guarantee? | Agent drafts, person approves | With every behaviour change |
| Feature or change spec | `docs/specs/NNNN-slug/` | What changes across several modules, and in which steps? | Agent drafts, person approves | Archived after merge |
| Execution plan | `docs/plans/active/NNNN-slug.md` | Where are we, what is next? | Agent, every session | Moved to `completed/` |
| Decision record | `docs/adr/NNNN-slug.md` | Why was this chosen? | Agent drafts, person decides | Superseded, never edited after acceptance |
| Code and tests | `src/`, `tests/`, `testdata/` | What actually happens | Agent, reviewed by a person | Always |

Code and tests are the truth. Specs state the contract the code must meet; they are not a second copy of the implementation. Keep a module spec to one to three pages and link to RESEARCH instead of repeating pseudo-code.

## Requirements

Each module spec lists its requirements with stable IDs, `REQ-<MODULE>-<NNN>` (for example `REQ-OFF-003`), phrased in the EARS style (Easy Approach to Requirements Syntax), which keeps them testable:

| Pattern | Form | CAM example |
| --- | --- | --- |
| Ubiquitous | THE <system> SHALL <response> | THE offset function SHALL return loops without self-intersections. |
| Event | WHEN <trigger> THE <system> SHALL <response> | WHEN the region vanishes under the offset, THE offset function SHALL return an empty result with diagnostic `OFFSET_EMPTY`. |
| State | WHILE <state> THE <system> SHALL <response> | WHILE the tool axis is within the singular zone, THE kinematics SHALL keep the C angle of the last defined point. |
| Optional feature | WHERE <feature> THE <system> SHALL <response> | WHERE the boundary edge is tagged as air, THE pocket strategy SHALL extend passes beyond it by R plus the clearance. |
| Unwanted | IF <condition> THEN THE <system> SHALL <response> | IF a rapid move would pass below the safe envelope THEN THE linker SHALL replace it with a retract link. |

Each requirement names how it is verified: a unit test, a property test, a golden case or a review item. IDs are never reused; a removed requirement is marked `Withdrawn`.

**Traceability.** Tests carry the IDs they verify in their names or tags. `tools/trace-check` reports requirements without a test and tests that cite unknown IDs, and writes the table to `docs/generated/traceability.md`. It runs in `tools/check`, so an agent cannot finish a requirement without a test.

**Where requirements come from.** Most are already implied by the research: the invariants of [RESEARCH 24](../research/24-testing-and-verification.md), the pitfalls of [RESEARCH 18](../research/18-known-pitfalls.md) (each pitfall is a requirement in disguise) and the traps listed in each section. The `research-to-spec` skill drafts a spec from a RESEARCH section; a person reviews it. [examples/geometry2d-offset-SPEC.md](../specs/geometry2d-SPEC.md) shows the expected result.

## Spec lifecycle

`Draft` (agent wrote it) → `Reviewed` (a person approved it, with date and name) → `Implemented` (all requirements have passing tests) → back to `Draft` sections when a change spec modifies them. Agents implement only `Reviewed` requirements.

## Feature and change specs

Work that touches several modules gets a folder in `docs/specs/NNNN-slug/` using [templates/FEATURE-SPEC.md](../templates/FEATURE-SPEC.md): requirements (new or changed REQ IDs per module), design (interfaces, data flow, alternatives considered), and tasks (small, ordered, each one change). After merge, the requirements are folded into the module specs and the folder is marked done. This borrows the requirements, design and tasks split from Kiro and the change folders from OpenSpec, without depending on either tool; GitHub Spec Kit follows a similar spec, plan and tasks sequence and can be adopted later if it proves useful.

## Execution plans

Any task longer than one session gets a plan in `docs/plans/active/` using [templates/EXEC-PLAN.md](../templates/EXEC-PLAN.md): goal, links to specs, a checklist of steps, a decisions log, a dated progress log, the next step and open questions. The agent updates it at the end of every session, before stopping. A new session, or a different agent, starts by reading it. This is the project's replacement for chat memory.

## Decision records

Write an ADR ([templates/ADR.md](../templates/ADR.md)) for any of these:

- a new external dependency, or dropping one;
- a change to `architecture/modules.yaml` or to a public interface used by several modules;
- a file format, schema or algorithm-version change that affects saved jobs;
- a tolerance policy change;
- anything touching licensing or provenance.

An accepted ADR is never edited; a new ADR supersedes it. Agents may draft ADRs with status `Proposed`; only a person sets `Accepted`.

## Sources

EARS: A. Mavin et al., *Easy Approach to Requirements Syntax*, IEEE RE 2009. Spec-driven tools: GitHub Spec Kit <https://github.com/github/spec-kit>, Kiro specs <https://kiro.dev/docs/specs/>, OpenSpec <https://github.com/Fission-AI/OpenSpec>; critique of heavy spec workflows: <https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html>.

---

[Index](README.md) · [← 04. Code conventions](04-code-conventions.md) · [06. Testing and quality gates →](06-testing-and-quality-gates.md)

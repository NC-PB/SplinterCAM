# ADR 0001: Record architecture decisions

- Status: Accepted (2026-09-27, Peter)
- Date: 2026-09-24
- Deciders: Peter Burgener
- Drafted by: Claude

## Context

The project is developed mostly by AI coding agents that do not remember earlier sessions. Decisions that exist only in conversations are lost, re-argued or silently reversed by the next agent.

## Decision

Every decision is logged in the decision table (DECISIONS.md in Project Spike). Every significant decision is also recorded as an ADR in `docs/adr/` using `templates/ADR.md`, in the cases listed in `docs/dev/05`. Agents may draft ADRs with status `Proposed`; only a person sets `Accepted`. Accepted ADRs are never edited; a new ADR supersedes them. A hook blocks agent edits to accepted ADRs.

## Consequences

Agents can find the reason behind any rule. Reversing a decision takes an explicit new ADR. Some overhead for small decisions, which go into plan decision logs instead.

## Alternatives considered

- Decisions in issue comments only: not in the repository, invisible to agents.

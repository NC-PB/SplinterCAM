# ADR 0006: Clean-room and provenance policy

- Status: Accepted (2026-09-27, Peter); amended 2026-10-01 by D-144 (clean room for every strategy) and D-145 (Peter's assessment replaces the legal advice on confidentiality)
- Date: 2026-09-24
- Deciders: Peter Burgener
- Drafted by: Claude

## Context

The research guide was written by someone with long experience of a commercial CAM system, and its folder currently sits inside that system's old source tree. The research review of 2026-09-23 flagged confidentiality as a risk that the "no copied code" rule alone does not cover. Agents reproduce what they have read.

## Decision

- The repository lives outside the old source tree; agents working on it get no access to that tree (deny rules in `.claude/settings.local.json` on machines that still hold it).
- No code, constants, tuning values, data tables, file formats, identifiers or comments from the old system enter the repository.
- Research sections 18 and 19 get public sources for their items and neutral introductions before they move into `docs/research/`.
- Every algorithm names a public source (paper, textbook, manual, permissive project) in its spec and code.
- GPL and LGPL code is not given to agents as context while they write code for this repository.
- Contributions carry a Developer Certificate of Origin sign-off.
- Legal advice on the confidentiality question is obtained before the repository is published.

## Consequences

Some effort to back the pitfall and design sections with public sources. In exchange, the project can be published and accept contributions without a provenance cloud over it.

## Alternatives considered

- Relying on "no copied code" alone: does not address confidential information.

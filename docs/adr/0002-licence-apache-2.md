# ADR 0002: Licence: Apache-2.0

- Status: Accepted
- Date: 2026-09-24
- Deciders: Peter Burgener
- Drafted by: Claude

## Context

The licence decides which libraries may be used and who can build on the project. Toolpath methods are heavily patented ([RESEARCH 05](../research/05-adaptive-clearing.md)). Candidates were Apache-2.0, MIT and LGPL-2.1-or-later.

## Decision

The project is licensed under Apache-2.0. Dependencies follow the licence classes in [09](../engineering/09-dependencies-licensing-provenance.md): permissive licences allowed; MPL-2.0 and LGPL only under conditions (LGPL only in `adapters/`, dynamically linked); GPL, AGPL and non-commercial licences not allowed.

## Consequences

- Contributors grant a patent licence for their contributions; users and companies can adopt the code freely.
- FreeCAD CAM, OpenCAMLib (LGPL), CAMotics and LibLathe (GPL) code cannot be copied into the project; they can only be used as external tools or read for ideas.
- OCCT (LGPL-2.1 with exception) is usable through a dynamically linked adapter.
- Every file carries `SPDX-License-Identifier: Apache-2.0`; a `NOTICE` file lists attributions.

## Alternatives considered

- MIT: simpler, but no patent clause.
- LGPL-2.1-or-later: would allow reusing FreeCAD and OpenCAMLib code, but limits adoption and mixes poorly with a permissive dependency policy.

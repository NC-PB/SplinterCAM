# ADR 0007: Headless first: CLI, text formats and renders before the GUI

- Status: Accepted (2026-09-27, Peter)
- Date: 2026-09-24
- Deciders: Peter Burgener
- Drafted by: Claude

## Context

Agents cannot click through a GUI to check their work, and CI cannot either. Binary project files cannot be diffed or reviewed.

## Decision

- `apps/cli` comes before `apps/desktop`: it runs a job file and writes CL data, G-code, a report (JSON) and, with `--debug`, the intermediate geometry.
- Jobs, tools, machines, posts and test cases are text files with JSON schemas in `schemas/`.
- `tools/render` draws inputs, debug geometry and outputs as SVG or PNG, so agents and reviewers can look at results.
- The GUI is a client of the same `job` interface as the CLI; it adds no computation of its own.

## Consequences

Every feature is testable end to end in CI from the first day. The GUI starts later, but on a core that is already verified.

## Alternatives considered

- GUI first: faster to demonstrate, but every check would need a person at the screen.

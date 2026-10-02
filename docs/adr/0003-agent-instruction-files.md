# ADR 0003: AGENTS.md as the single source of agent instructions

- Status: Accepted (2026-09-27, Peter)
- Date: 2026-09-24
- Deciders: Peter Burgener
- Drafted by: Claude

## Context

Several coding agents may work on the repository. Most read `AGENTS.md` (the agents.md convention, now stewarded by the Agentic AI Foundation). Claude Code reads `CLAUDE.md`, and recent versions also read `AGENTS.md`, by default only when no `CLAUDE.md` exists in the working directory or above. Duplicated instructions drift apart.

## Decision

- All instructions that apply to every agent live in `AGENTS.md` files: one at the root (at most 150 lines), one per module (at most 60 lines).
- The root `CLAUDE.md` starts with `@AGENTS.md` and adds only Claude-specific workflow (at most 40 lines).
- Each module has a one-line `CLAUDE.md` stub (`@AGENTS.md`), so Claude Code loads the module rules when it reads files in that folder.
- Claude-only mechanisms (skills, subagents, hooks, path-scoped rules) live in `.claude/` and never repeat rules from `AGENTS.md`.

## Consequences

One source of truth for all tools. The stubs are redundant once native `AGENTS.md` loading covers nested files reliably; then they can be removed in a follow-up ADR. Details and size limits: [08](../engineering/08-agent-instruction-files.md).

## Alternatives considered

- `CLAUDE.md` only: other agents would see nothing.
- Symlinking `CLAUDE.md` to `AGENTS.md`: no place for Claude-specific lines, and symlinks behave differently on Windows.

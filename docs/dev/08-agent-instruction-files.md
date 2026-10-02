[Index](README.md) · [← 07. Agent workflow](07-agent-workflow.md) · [09. Dependencies, licensing and provenance →](09-dependencies-licensing-provenance.md)

# 08. Agent instruction files

Instruction files are loaded into the agent's context, so every line costs attention on every task. They must be short, specific, checkable, and written for the mistakes agents actually make. Checked on 2026-09-24 against the current documentation of Claude Code, the agents.md convention and OpenAI Codex.

## Which file does what

| File | Read by | Purpose | Size |
| --- | --- | --- | --- |
| `AGENTS.md` (root) | Codex, Copilot, Cursor, Jules, Aider, Zed, Kiro and others; Claude Code (see below); Gemini CLI when configured | The map: what the repo is, commands, workflow, hard rules, definition of done, gotchas | ≤ 150 lines |
| `src/splintercam/<m>/AGENTS.md` | The same tools, when working in that folder | Module invariants, local rules, pitfalls | ≤ 60 lines |
| `CLAUDE.md` (root) | Claude Code | `@AGENTS.md` plus Claude-specific workflow | ≤ 40 lines |
| `src/splintercam/<m>/CLAUDE.md` | Claude Code, loaded when it reads files in that folder | One line: `@AGENTS.md` | 1 line |
| `.claude/rules/*.md` | Claude Code | Rules scoped by file pattern (`paths:` frontmatter), for cross-cutting concerns like all test files | ≤ 40 lines each |
| `.claude/skills/<name>/SKILL.md` | Claude Code | Procedures loaded only when needed, also callable as `/name` | ≤ 80 lines each |
| `.claude/agents/<name>.md` | Claude Code | Subagents with their own context and tool limits (reviewers) | ≤ 60 lines each |
| `.claude/settings.json` | Claude Code | Shared permissions and hooks | n/a |
| `.claude/settings.local.json` | Claude Code | Personal settings, not committed | n/a |

**One source of truth.** Everything that applies to every agent goes into `AGENTS.md` files. Claude-specific files only add what other tools cannot use (skills, subagents, hooks) and never repeat rules.

**Claude Code and AGENTS.md.** Recent Claude Code versions read `AGENTS.md` natively, but by default only when there is no `CLAUDE.md`, `.claude/CLAUDE.md` or `CLAUDE.local.md` in the working directory or above it; the "Project instructions" setting can switch this to read both. The setup that works with every version: a root `CLAUDE.md` that begins with `@AGENTS.md`, and a one-line `CLAUDE.md` stub (`@AGENTS.md`) next to each module `AGENTS.md`, because nested `CLAUDE.md` files are loaded when Claude reads files in that folder. Imports can nest up to four levels. Run `/context` in Claude Code to see what was loaded. If the stubs prove unnecessary with the native support, delete them and move the Claude-only lines to `.claude/rules/`.

**Other tools.** Codex joins `AGENTS.md` files from the repository root down to the working folder (closer files win) up to 32 KiB by default. Gemini CLI reads `GEMINI.md` unless its `context.fileName` setting lists `AGENTS.md`. The agents.md convention is now stewarded by the Agentic AI Foundation under the Linux Foundation.

## What goes in, what stays out

| Put in | Leave out |
| --- | --- |
| Commands an agent cannot guess (`tools/check`, `tools/test-one`) | Directory listings and file-by-file descriptions: agents read the tree |
| Rules that differ from the language's defaults | Standard language conventions |
| Hard rules with a one-line reason | Long explanations and tutorials: link to `docs/dev/` |
| The definition of done | Technology lists, marketing text |
| Gotchas that caused a repeated mistake | Things that change often (sprint goals, temporary workarounds) |
| Where to look for specs, research and plans (a short table of pointers) | Copies of spec or research content |

The root `AGENTS.md` carries a short "Lean code" section: the eight rules of [12](12-lean-code.md), section 2, one line each.

Write rules in the imperative, specific and checkable: "Tolerances come from the `ToleranceSet`; never write a literal epsilon" instead of "be careful with floating point".

## Templates and what they became

| Template | Becomes |
| --- | --- |
| templates/AGENTS.md (Project Spike) | Root [`AGENTS.md`](../../AGENTS.md) |
| templates/CLAUDE.md (Project Spike) | Root [`CLAUDE.md`](../../CLAUDE.md) |
| [docs/templates/module-AGENTS.md](../templates/module-AGENTS.md) | `src/splintercam/<m>/AGENTS.md` |
| [docs/templates/module-CLAUDE.md](../templates/module-CLAUDE.md) | `src/splintercam/<m>/CLAUDE.md` |
| templates/dot-claude/settings.json (Project Spike) | [`.claude/settings.json`](../../.claude/settings.json) |
| templates/dot-claude/rules/ (Project Spike) | [`.claude/rules/`](../../.claude/rules): path-scoped rules for tests, C++ kernels, OCP code and posts |
| templates/dot-claude/skills/ (Project Spike) | [`.claude/skills/`](../../.claude/skills): skills listed below |
| templates/dot-claude/agents/ (Project Spike) | [`.claude/agents/`](../../.claude/agents): subagents listed below |
| templates/dot-claude/agents/simplifier.md (Project Spike) | [`.claude/agents/simplifier.md`](../../.claude/agents/simplifier.md) |
| templates/tools/ (Project Spike) | [`tools/`](../../tools): the command contract and the two hook scripts |

## Skills

| Skill | Use |
| --- | --- |
| `implement-requirement` | Implement or fix one `REQ-…` test-first, from spec to evidence |
| `research-to-spec` | Draft a module `SPEC.md` from a RESEARCH section: requirements, invariants, pitfalls, tolerance budget |
| `new-module` | Scaffold a module (only when a person asks; it changes `modules.yaml`) |
| `add-regression-case` | Turn a failure dump or bug report into a minimal permanent test case |
| `garden-docs` | Report broken links, stale plans, untested requirements, oversized instruction files, size hotspots |

Old-style `.claude/commands/*.md` slash commands have been folded into skills; a skill with `disable-model-invocation: true` is one that only a person can start.

## Subagents

| Subagent | Tools | Checks |
| --- | --- | --- |
| `spec-reviewer` | Read-only | The change against its spec and research: missing edge cases, wrong formulas, unit errors, uncovered pitfalls |
| `test-auditor` | Read-only plus `git diff` | Weakened, skipped or deleted tests, loosened tolerances, golden changes, missing requirement tags |
| `cnc-reviewer` | Read-only plus `tools/render` | Machine safety of CL data and G-code: rapids, retracts, arcs after rounding, modal state, controller dialect |
| `simplifier` | Read-only plus `git diff` | What could go without breaking a requirement: code no requirement needs, one-use abstractions, duplicated logic, checks inside trusted code, options nobody asked for, comments that restate. Proposes deletions with the lines saved; never adds |

Reviewers run in their own context, so they judge the change without the implementer's assumptions. They report findings; they never edit. Each finding names its class, must fix, spec gap or nice to have ([12](12-lean-code.md), section 5), so the implementer changes code only for the must-fix ones.

## Hooks and permissions

- **Before an edit** (`PreToolUse` on `Edit|Write`): `tools/hooks/guard-protected-paths` exits with code 2 for protected paths (golden files, `LICENSE`, `NOTICE`, accepted ADRs, CI, agent settings). Exit code 2 blocks the edit and feeds the reason back to the agent.
- **After an edit** (`PostToolUse` on `Edit|Write`): `tools/hooks/format-changed-file` runs the formatter on the edited file.
- **Optional at session start** (`SessionStart`): print the active plans and the current branch, so every session starts from the written state.
- **Permissions:** allow `tools/*` and read-only git commands; deny `git push`, `tools/golden-approve` and edits to protected paths. Personal additions go into `settings.local.json`, which is not committed. Deny reads outside the repository there too, for example the folder with the old commercial source.

Hooks are for rules that must hold every time; skills are for knowledge needed only sometimes; `AGENTS.md` is for what every task needs.

## Keeping the files healthy

- Add a line when an agent makes the same mistake twice, or a review catches something the agent should have known.
- Delete a line when a check now enforces it, or when it has not mattered for months.
- The `garden-docs` skill flags files over their size limit and rules that duplicate `docs/dev/`.
- Review all instruction files together once a month; treat them like code, with pull requests.

## Sources

- Claude Code memory, imports, AGENTS.md support and rules: <https://code.claude.com/docs/en/memory>
- Claude Code skills: <https://code.claude.com/docs/en/skills>; subagents: <https://code.claude.com/docs/en/sub-agents>; hooks: <https://code.claude.com/docs/en/hooks-guide>; permissions: <https://code.claude.com/docs/en/permissions>; best practices: <https://code.claude.com/docs/en/best-practices>
- agents.md convention: <https://agents.md/>; Codex AGENTS.md behaviour: <https://learn.chatgpt.com/docs/agent-configuration/agents-md>; Gemini CLI context files: <https://geminicli.com/docs/cli/gemini-md/>

---

[Index](README.md) · [← 07. Agent workflow](07-agent-workflow.md) · [09. Dependencies, licensing and provenance →](09-dependencies-licensing-provenance.md)

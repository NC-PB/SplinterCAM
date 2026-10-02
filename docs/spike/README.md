# docs/spike: what came from Project Spike

SplinterCAM started early, before the handover of Project Spike (decision D-156 of 2026-10-02). Project Spike, the research phase, stays the only register of decisions, questions, assumptions and change proposals until the handover. This folder holds what this repository needs from it, as dated snapshots. Do not edit them here; a new snapshot replaces an old one.

| File | What it is |
| --- | --- |
| `decisions-snapshot.md` | The decisions (D-nnn) cited by the files of this repository, copied verbatim. Five decisions that name a proprietary source are listed but not copied. |
| `sources-snapshot.md` | The public sources (SRC-nnn) cited here. Source PDFs are never in this repository. |
| `foundation-SPEC-draft.md` | Project Spike's draft of the foundation SPEC, with the proposed changes to REQ-FND-001 and 002 and the new 008 and 009 (D-056, D-146, D-149). Plan 0001, step 2 takes them into `src/splintercam/foundation/SPEC.md`. |
| `2026-10-01-delta-plan-0001.md` | The spec delta written for the stack test app; its foundation rows are the same as the draft's. Its geometry2d rows wait for the offset kernel (D-132). |

## Files moved on 2026-10-02

Every file came from the stack test app's repository (scaffold, `foundation` code and tests, agent files; renamed from the placeholder `opencam` to `splintercam`) or from Project Spike (development docs, ADRs, glossary, research topic 01, templates). Nothing else was copied: no other research topics, no source PDFs, no private notes. Each file was scanned for references to proprietary sources (names of the proprietary system and its maker, its source register entry, private and inbox folders). Result: no proprietary content. Four lines mention the clean-room rules themselves and stay: ADR 0006 (lines 10 and 14, the clean-room setup described in general terms) and research 01 (lines 341 and 342, the provenance statement citing D-042).

| File | From |
| --- | --- |
| `.clang-format` | test_repo .clang-format |
| `.clang-tidy` | test_repo .clang-tidy |
| `.claude/agents/cnc-reviewer.md` | test_repo .claude/agents/cnc-reviewer.md |
| `.claude/agents/implementer.md` | test_repo .claude/agents/implementer.md |
| `.claude/agents/simplifier.md` | project_spike templates/dot-claude/agents/simplifier.md |
| `.claude/agents/spec-reviewer.md` | test_repo .claude/agents/spec-reviewer.md |
| `.claude/agents/test-auditor.md` | test_repo .claude/agents/test-auditor.md |
| `.claude/agents/test-designer.md` | test_repo .claude/agents/test-designer.md |
| `.claude/rules/kernels.md` | test_repo .claude/rules/kernels.md |
| `.claude/rules/ocp.md` | test_repo .claude/rules/ocp.md |
| `.claude/rules/posts.md` | test_repo .claude/rules/posts.md |
| `.claude/rules/tests.md` | test_repo .claude/rules/tests.md |
| `.claude/settings.json` | test_repo .claude/settings.json |
| `.claude/settings.local.example.json` | test_repo .claude/settings.local.example.json |
| `.claude/skills/add-regression-case/SKILL.md` | test_repo .claude/skills/add-regression-case/SKILL.md |
| `.claude/skills/garden-docs/SKILL.md` | test_repo .claude/skills/garden-docs/SKILL.md |
| `.claude/skills/implement-requirement/SKILL.md` | test_repo .claude/skills/implement-requirement/SKILL.md |
| `.claude/skills/new-module/SKILL.md` | test_repo .claude/skills/new-module/SKILL.md |
| `.claude/skills/research-to-spec/SKILL.md` | test_repo .claude/skills/research-to-spec/SKILL.md |
| `.editorconfig` | test_repo .editorconfig |
| `.gitattributes` | test_repo .gitattributes |
| `.github/CODEOWNERS` | test_repo .github/CODEOWNERS |
| `.github/PULL_REQUEST_TEMPLATE.md` | test_repo .github/PULL_REQUEST_TEMPLATE.md |
| `.github/workflows/check.yml` | test_repo .github/workflows/check.yml |
| `.github/workflows/sanitize.yml` | test_repo .github/workflows/sanitize.yml |
| `.gitignore` | test_repo .gitignore |
| `.python-version` | test_repo .python-version |
| `AGENTS.md` | test_repo AGENTS.md |
| `CLAUDE.md` | test_repo CLAUDE.md |
| `CMakeLists.txt` | test_repo CMakeLists.txt |
| `CONTRIBUTING.md` | test_repo CONTRIBUTING.md |
| `LICENSE` | test_repo LICENSE |
| `NOTICE` | test_repo NOTICE |
| `README.md` | test_repo README.md |
| `architecture/modules.yaml` | test_repo architecture/modules.yaml |
| `cmake/kernels_bindings.cpp.in` | test_repo cmake/kernels_bindings.cpp.in |
| `docs/adr/0001-record-architecture-decisions.md` | project_spike decisions/0001-record-architecture-decisions.md |
| `docs/adr/0002-licence-apache-2.md` | project_spike decisions/0002-licence-apache-2.md |
| `docs/adr/0003-agent-instruction-files.md` | project_spike decisions/0003-agent-instruction-files.md |
| `docs/adr/0004-tech-stack.md` | project_spike decisions/0004-tech-stack.md |
| `docs/adr/0005-units-and-tolerances.md` | project_spike decisions/0005-units-and-tolerances.md |
| `docs/adr/0006-clean-room-and-provenance.md` | project_spike decisions/0006-clean-room-and-provenance.md |
| `docs/adr/0007-headless-first.md` | project_spike decisions/0007-headless-first.md |
| `docs/adr/0008-deterministic-output.md` | project_spike decisions/0008-deterministic-output.md |
| `docs/adr/README.md` | project_spike decisions/README.md |
| `docs/dev/01-ai-first-principles.md` | project_spike engineering/01-ai-first-principles.md |
| `docs/dev/02-repository-layout.md` | project_spike engineering/02-repository-layout.md |
| `docs/dev/03-architecture-rules.md` | project_spike engineering/03-architecture-rules.md |
| `docs/dev/04-code-conventions.md` | project_spike engineering/04-code-conventions.md |
| `docs/dev/05-specs-plans-decisions.md` | project_spike engineering/05-specs-plans-decisions.md |
| `docs/dev/06-testing-and-quality-gates.md` | project_spike engineering/06-testing-and-quality-gates.md |
| `docs/dev/07-agent-workflow.md` | project_spike engineering/07-agent-workflow.md |
| `docs/dev/08-agent-instruction-files.md` | project_spike engineering/08-agent-instruction-files.md |
| `docs/dev/09-dependencies-licensing-provenance.md` | project_spike engineering/09-dependencies-licensing-provenance.md |
| `docs/dev/10-stack-decision.md` | project_spike engineering/10-stack-decision.md |
| `docs/dev/11-user-interface.md` | project_spike engineering/11-user-interface.md |
| `docs/dev/12-lean-code.md` | project_spike engineering/12-lean-code.md |
| `docs/dev/README.md` | project_spike engineering/README.md |
| `docs/generated/.gitkeep` | test_repo docs/generated/.gitkeep |
| `docs/glossary.md` | project_spike glossary.md |
| `docs/plans/completed/.gitkeep` | test_repo docs/plans/completed/.gitkeep |
| `docs/research/01-foundations.md` | project_spike research/01-foundations.md |
| `docs/spike/2026-10-01-delta-plan-0001.md` | project_spike specs/2026-10-01-delta-plan-0001.md |
| `docs/spike/foundation-SPEC-draft.md` | project_spike specs/foundation-SPEC.md |
| `docs/templates/ADR.md` | project_spike templates/ADR.md |
| `docs/templates/EXEC-PLAN.md` | project_spike templates/EXEC-PLAN.md |
| `docs/templates/FEATURE-SPEC.md` | project_spike templates/FEATURE-SPEC.md |
| `docs/templates/REVIEW-CHECKLIST.md` | test_repo docs/templates/REVIEW-CHECKLIST.md |
| `docs/templates/SPEC.md` | project_spike templates/SPEC.md |
| `docs/templates/TOPIC.md` | project_spike templates/TOPIC.md |
| `docs/templates/module-AGENTS.md` | test_repo docs/templates/module-AGENTS.md |
| `docs/templates/module-CLAUDE.md` | test_repo docs/templates/module-CLAUDE.md |
| `pyproject.toml` | test_repo pyproject.toml |
| `schemas/README.md` | test_repo schemas/README.md |
| `src/splintercam/__init__.py` | test_repo src/opencam/__init__.py |
| `src/splintercam/_kernels/__init__.pyi` | test_repo src/opencam/_kernels/__init__.pyi |
| `src/splintercam/foundation/AGENTS.md` | test_repo src/opencam/foundation/AGENTS.md |
| `src/splintercam/foundation/CLAUDE.md` | test_repo src/opencam/foundation/CLAUDE.md |
| `src/splintercam/foundation/SPEC.md` | test_repo src/opencam/foundation/SPEC.md |
| `src/splintercam/foundation/__init__.py` | test_repo src/opencam/foundation/__init__.py |
| `src/splintercam/foundation/_context.py` | test_repo src/opencam/foundation/_context.py |
| `src/splintercam/foundation/_result.py` | test_repo src/opencam/foundation/_result.py |
| `src/splintercam/foundation/_tolerance.py` | test_repo src/opencam/foundation/_tolerance.py |
| `src/splintercam/py.typed` | test_repo src/opencam/py.typed |
| `tests/README.md` | test_repo tests/README.md |
| `tests/conftest.py` | test_repo tests/conftest.py |
| `tests/foundation/property/test_nearly_equal.py` | test_repo tests/foundation/property/test_nearly_equal.py |
| `tests/foundation/property/test_tolerance_set_construction.py` | test_repo tests/foundation/property/test_tolerance_set_construction.py |
| `tests/foundation/unit/test_cancellation_token.py` | test_repo tests/foundation/unit/test_cancellation_token.py |
| `tests/foundation/unit/test_context.py` | test_repo tests/foundation/unit/test_context.py |
| `tests/foundation/unit/test_result.py` | test_repo tests/foundation/unit/test_result.py |
| `tests/foundation/unit/test_tolerance_set.py` | test_repo tests/foundation/unit/test_tolerance_set.py |
| `tests/kernels/test_import.py` | test_repo tests/kernels/test_import.py |
| `tests/support/README.md` | test_repo tests/support/README.md |
| `tools/README.md` | test_repo tools/README.md |
| `tools/bootstrap` | test_repo tools/bootstrap |
| `tools/build` | test_repo tools/build |
| `tools/check` | test_repo tools/check |
| `tools/format` | test_repo tools/format |
| `tools/hooks/format-changed-file` | test_repo tools/hooks/format-changed-file |
| `tools/hooks/guard-protected-paths` | test_repo tools/hooks/guard-protected-paths |
| `tools/hooks/protected-paths.txt` | test_repo tools/hooks/protected-paths.txt |
| `tools/lib/cmd_build.py` | test_repo tools/lib/cmd_build.py |
| `tools/lib/cmd_check.py` | test_repo tools/lib/cmd_check.py |
| `tools/lib/cmd_format.py` | test_repo tools/lib/cmd_format.py |
| `tools/lib/cmd_lint.py` | test_repo tools/lib/cmd_lint.py |
| `tools/lib/cmd_test.py` | test_repo tools/lib/cmd_test.py |
| `tools/lib/cmd_test_one.py` | test_repo tools/lib/cmd_test_one.py |
| `tools/lib/env.sh` | test_repo tools/lib/env.sh |
| `tools/lib/modules.py` | test_repo tools/lib/modules.py |
| `tools/lib/runner.py` | test_repo tools/lib/runner.py |
| `tools/lint` | test_repo tools/lint |
| `tools/test` | test_repo tools/test |
| `tools/test-one` | test_repo tools/test-one |
| `uv.lock` | test_repo uv.lock |
| `docs/spike/decisions-snapshot.md` | generated from Project Spike DECISIONS.md |
| `docs/spike/sources-snapshot.md` | generated from Project Spike sources/register.md (public entries, local locations removed) |

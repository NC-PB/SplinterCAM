---
name: new-module
description: Scaffold a new module with SPEC, AGENTS.md, CLAUDE.md stub, source and test folders, and its entry in architecture/modules.yaml.
disable-model-invocation: true
---

# Scaffold a module

Module: $ARGUMENTS

1. Check `docs/glossary.md` for the module's name; propose a glossary entry if it is new.
2. Propose the layer and dependencies. Show the exact `architecture/modules.yaml` entry and wait for approval before editing it.
3. Run `tools/new-module <name>` to create the folders and build files.
4. Fill `SPEC.md` from `docs/templates/SPEC.md` with status `Draft` (use the `research-to-spec` skill if a research section exists).
5. Fill `AGENTS.md` from `docs/templates/module-AGENTS.md`; add the one-line `CLAUDE.md` stub (`@AGENTS.md`).
6. Run `tools/check` (the empty module must build and pass the architecture check).
7. Report what was created and what still needs a person's decision.

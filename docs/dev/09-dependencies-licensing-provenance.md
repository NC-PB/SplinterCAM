[Index](README.md) · [← 08. Agent instruction files](08-agent-instruction-files.md) · [10. Stack decision →](10-stack-decision.md)

# 09. Dependencies, licensing and provenance

Agents copy readily and do not feel licence obligations. The rules below make the safe path the default and let checks catch the rest. I am not a lawyer; treat this as engineering policy. The legal advice on the provenance question was replaced by Peter's own assessment (D-145); patents are cleared by claim charts and design rules (D-130, D-143); strategies follow the clean-room rules of D-144.

## The project licence

The project is licensed under **Apache-2.0** ([ADR 0002](../decisions/0002-licence-apache-2.md)): permissive, with an explicit patent licence from every contributor for their contributions, and a `NOTICE` file that redistributors must keep. Apache-2.0 code may be used in GPL-3.0 projects, but not in GPL-2.0-only ones.

## Which licences may enter

| Class | Licences | Rule |
| --- | --- | --- |
| Allowed | MIT, MIT-0, BSD-2-Clause, BSD-3-Clause, Apache-2.0, BSL-1.0, ISC, Zlib, CC0, public domain | Normal dependency; attribution in `NOTICE` where the licence asks for it |
| Allowed with conditions | MPL-2.0 | Use unmodified; modified MPL files stay MPL and are published |
| Allowed with conditions | LGPL-2.1, LGPL-3.0: OCCT (with its exception, shipped inside OCP) and Qt (through PySide6) | Only as separate, dynamically loaded libraries the user can replace; unmodified, or modifications published; listed in `NOTICE`; an ADR for every new LGPL dependency |
| Allowed for test data only | CC BY-4.0 | Attribution in `testdata/LICENSES.md` |
| Not allowed | GPL (any version), AGPL, SSPL, BUSL and other "source available" licences, Commons Clause, CC BY-NC or ND, CC BY-SA for code (this includes Stack Overflow snippets), code without any licence | Never, not even "temporarily" |

Qt's GPL-only modules are not allowed, even where PySide6 ships them: Charts, Graphs, Data Visualization, Quick 3D and Quick 3D Physics, Virtual Keyboard, Lottie, Quick Timeline, Wayland Compositor, CoAP, MQTT, HTTP Server, gRPC, Network Authorization, Canvas Painter and the QML compiler. `tools/licence-check` rejects imports of them.

Every new dependency needs an ADR stating why it is needed, the alternatives, its licence, its maintenance status and the platforms it supports. Versions are pinned. `tools/licence-check` produces a dependency licence report and fails the build when a licence outside the allowed classes appears (the tool behind it depends on the stack: for example cargo-deny, a NuGet licence reporter or a package licence checker).

## Code that comes from somewhere else

- **Permissive snippets** may be adapted with a comment giving the URL, the licence and the copyright holder, plus an entry in `NOTICE`.
- **GPL and LGPL projects** (FreeCAD CAM, CAMotics, LibLathe, most small CAM projects) may be read by people to understand an approach. They are not given to an agent as context while it writes code for this repository, because models can reproduce what they have just read almost verbatim. Implement from RESEARCH and the papers it cites.
- **Proprietary code** is never read, searched, quoted or described to an agent. This includes the old commercial source tree.

## Provenance rules

1. The repository lives outside the old commercial source tree, and agents working on it have no access to that tree. Add a deny rule for its path to `.claude/settings.local.json` on any machine that still holds it.
2. No code, constants, tuning values, data tables, file formats, identifiers or comments from the old system enter the repository, in any form.
3. Before `RESEARCH` moves into `docs/research/`, sections 18 and 19 get public sources for their items, and their introductions are reworded as general CAM engineering knowledge (research review of 2026-09-23, open point 1).
4. Every algorithm names its public source in its module spec and in a code comment.
5. Every contribution carries a Developer Certificate of Origin sign-off: the person submitting confirms they have the right to submit it, including the parts an agent wrote.

## AI-generated code

The person who submits a change is responsible for it, whoever typed it. Review AI-written code like any other contribution. Do not prompt agents with foreign code "to rewrite it"; a rewrite of a copyrighted text can still be a copy.

## Patents

Apache-2.0 gives users a licence to the patents of the project's contributors, not to anyone else's. Toolpath methods, adaptive clearing in particular, were patented heavily ([RESEARCH 05](../research/05-adaptive-clearing.md)). Prefer methods published in academic papers, avoid imitating a specific commercial product's behaviour, and check the status of any patent that clearly covers a method before shipping it.

## File-level hygiene

- Every source file starts with an SPDX identifier: `SPDX-License-Identifier: Apache-2.0`.
- Follow the REUSE specification (licence texts in `LICENSES/`, identifiers in every file, `reuse lint` in CI), which makes licence checks automatic.
- `NOTICE` lists third-party code and the attributions their licences require.
- Control and machine names (Fanuc, Siemens, Heidenhain) are used only descriptively, for example in post-processor names; no logos.

---

[Index](README.md) · [← 08. Agent instruction files](08-agent-instruction-files.md) · [10. Stack decision →](10-stack-decision.md)

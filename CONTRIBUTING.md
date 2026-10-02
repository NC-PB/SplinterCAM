# Contributing to SplinterCAM

SplinterCAM is developed mostly with AI coding agents, reviewed by people. The same rules apply to both.

## Before you start

- Read `AGENTS.md` (short) and, for your area, the module's `SPEC.md`.
- Pick an issue, or open one that says what and why. Behaviour changes start with a requirement in the module's SPEC.
- The developer guide is in `docs/dev/`: conventions, testing, workflow, licensing.

## Making a change

1. Branch per task: `feat/<module>-<topic>` or `fix/<module>-<topic>`.
2. Tests first, tagged with requirement IDs; then the code.
3. `tools/check` must pass.
4. Open a pull request with the template filled in: requirements, commands run and results, renders for geometry changes, tests added or changed.

## Sign-off and AI assistance

- Every commit is signed off under the Developer Certificate of Origin (`git commit -s`). By signing off you confirm you have the right to submit the change, including the parts an AI agent wrote.
- Say which agent helped (a `Co-Authored-By:` trailer is enough). You are responsible for what you submit.

## What we cannot accept

- Code copied from other CAM software, from GPL or LGPL projects, from Stack Overflow, or without a licence.
- Anything derived from proprietary source code or confidential documents.
- Test parts you are not allowed to share. Reduce a customer part to a minimal, anonymised example you drew yourself.

## Licence

By contributing, you agree that your contribution is licensed under Apache-2.0, the project licence.

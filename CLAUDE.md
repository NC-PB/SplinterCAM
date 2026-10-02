@AGENTS.md

## Claude Code

- Use plan mode for any change that touches more than one module, a public interface or `architecture/modules.yaml`.
- Before reporting a task as done, run the `test-auditor` subagent on your diff. Also run `spec-reviewer` for new or changed algorithms, and `cnc-reviewer` for anything that changes CL data, posts or G-code.
- Reviews (D-152, D-153): code in `src/` gets the reviews above; the SPEC next to the code is the contract. Run the `simplifier` subagent on new code before the test-auditor (docs/dev/12).
- Skills: `/implement-requirement <REQ-ID>`, `/research-to-spec <section>`, `/add-regression-case <failure>`, `/garden-docs`. `/new-module` only when asked.
- Hooks format edited files and block edits to protected paths. If a hook blocks you, do not work around it; tell the user why you needed the edit.
- If the rules above seem to be ignored, check what was loaded with `/context`.

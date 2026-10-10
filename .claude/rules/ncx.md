---
paths:
  - "src/splintercam/ncx/**"
  - "src/splintercam/cl/**"
---

# Rules for the toolpath record and the NCX output

- SplinterCAM writes NCX only, the same for every controller (D-021, D-031, D-148). Never write a controller dialect, a canned cycle in a control's syntax, or a machine-specific number format; that is NCXchange's job.
- Write NCX from the unrounded toolpath record at the fixed resolution of D-149 (1e-6 mm, 1e-7 inch, 1e-7°) with each operation's rounding allowance; NCXchange rounds once to the machine.
- Format numbers with an invariant culture; no "-0".
- Machine data comes from NCXchange's machine files (D-053); a value the CAM needs that is not there is proposed to NCXchange, not invented here.
- Every NCX output change gets a test that runs the pinned `ncx check --strict` on it, and the `cnc-reviewer` subagent before reporting.

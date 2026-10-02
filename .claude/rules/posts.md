---
paths:
  - "posts/**"
  - "src/splintercam/post/**"
  - "src/splintercam/vnc/**"
---

# Rules for post-processors and the virtual NC

- Every controller-specific behaviour cites the manual it comes from (document number and section). Never guess a code or cycle.
- Tie G-codes and cycles to a specific control and G-code system, never globally (Fanuc lathe systems A, B and C differ).
- Format numbers with an invariant culture; round half away from zero; test for zero after rounding; no "-0".
- Compute arc centres so that the rounded values rebuild the centre; split arcs that round to a full circle or to nothing.
- Normalise rotary angles after rounding (359.9996° prints as 360).
- Add a golden case for every new control or option, and run the `cnc-reviewer` subagent before reporting.

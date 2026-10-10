---
topic: "10"
title: Linking, lead-in/out and safe retract
readiness: L4 for the clearance-height links of plan 0007; the rest of the topic is in Project Spike (L1)
release: "1"
reviewed: 2026-10-11
provenance: public
---

[Index](README.md) · [22. 2.5D milling operations](22-2d-operations.md) · [26. Toolpath record](26-toolpath-record.md)

# 10. Linking: the clearance-height links of plan 0007

This file holds the part of topic 10 that plan 0007 needs: the moves before, between and after the passes of one operation, all through the clearance height, with every descent outside the stock (Peter's answer of 2026-10-11 to plan 0007, question 4). Per-link retract heights over the stock layers, staying down, leads, compensation switching and link checks against fixtures stay in Project Spike's topic 10 until a plan pulls them (D-158).

## Method

Heights (D-062): the clearance height h_c = stock top + 5 mm; the retract height h_r = stock top + 3 mm. Plan 0007 has no fixtures, so "stock or clamps" is the stock alone.

1. **Start of the operation**, after the tool change: RAPID to Z = h_c at the current position in the plane, then RAPID in the plane to the approach point P (topic 22) at h_c. The first move goes up or down only along the tool axis, so it never sweeps across the part at an unknown height (ours).
2. **Down to a pass at z_i:** at P, RAPID to h_r, then LINE to z_i at the plunge feed, role APPROACH. P lies outside the stock by at least the air gap (topic 22), so the tool descends beside the stock, never into it.
3. **Between passes:** after the pass ends at P, RAPID to h_c, then down as in step 2 to the next level. P is the same for every pass, so there is no move in the plane (Peter's answer: retract to the clearance height, back over the start point, down outside the stock).
4. **End of the operation:** at P, RAPID to h_c.
5. Every RAPID carries its link height in the record's `link_height` (topic 26): h_c for moves at the clearance height, h_r for the descent at P.

## Traps

1. Clamps and vices are not modelled in plan 0007: a clamp higher than h_c, or beside the stock at P, is hit. The setup sheet and Peter's dry run (plan 0007, step 8) cover it until fixtures exist (D-078).
2. The tool's position after the tool change differs per machine; the first move therefore changes Z alone.

## Tests

1. Topic 22's test 1: the moves are, in order: RAPID Z = h_c; RAPID to P; per pass: RAPID Z = h_r, LINE Z = z_i, the pass, RAPID Z = h_c; no RAPID in the plane below h_c; no move below h_r inside the stock box grown by R, except the pass itself and its approach and retract.
2. With stock top = 2 mm: h_c = 7, h_r = 5.

## Sources

D-062, D-078, D-079; Peter's answers to plan 0007. The rest is ours, marked so.

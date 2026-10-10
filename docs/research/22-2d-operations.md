---
topic: "22"
title: 2.5D milling operations
readiness: L4 for the outside profile of plan 0007; the rest of the topic is in Project Spike (L1)
release: "1"
reviewed: 2026-10-11
provenance: public
---

[Index](README.md) · [2. 2D offsets and Booleans](02-offsets-and-booleans.md) · [10. Linking](10-linking.md)

# 22. 2.5D milling operations: the outside profile of plan 0007

This file holds the part of topic 22 that plan 0007 needs: an outside profile of one closed contour with depth passes. Facing, chamfering, slots, thread milling, engraving, helical boring, leads, tabs and inside profiles stay in Project Spike's topic 22 until a plan pulls them (D-158).

## Scope

- In: one closed contour of material (topic 21's import); a box stock; a flat end mill of radius R; a side allowance s; the top of the cut z_top and the final depth z_bottom, absolute in the work frame; the largest step-down; spindle speed; a cutting feed and a plunge feed entered by hand; climb milling.
- Out (later): leads in and out, tabs, inside profiles, conventional milling, open chains (research 02, Open chains), the cutting-data solver, finishing allowances per pass, control compensation (the path is the tool centre, D-024, D-154).

## Method

1. **Centre path.** `offset_region` (offset2d) grows the material region by t = R + s (D-150: s > −R, so t > 0). For one closed contour the result is one outer loop; anything else stops the operation with `PROFILE_REGION` (error, ours). The loop lies between t and t + a + 6u from the contour (research 02, the band).
2. **Direction.** Climb milling with a clockwise spindle keeps the material on the right of the direction of travel, so an outside profile runs clockwise round the part (ours, the usual definition of down-milling). offset2d returns outer loops counter-clockwise, so the loop is reversed.
3. **Depth passes.** n = ⌈(z_top − z_bottom) / a_p,max⌉ passes of equal depth Δ = (z_top − z_bottom) / n, at z_i = z_top − i·Δ for i = 1 … n (ours: equal steps leave no thin last pass). A depth larger than the tool's flute length stops the operation with `PROFILE_TOO_DEEP` (error; the feature map's cutting-length check, release 1).
4. **Start point** (ours). S is the midpoint of the loop's longest line row; on a loop of arcs only, its first vertex. The loop is rotated to start and end at S.
5. **Approach point** (ours). P lies on the outward normal of S's row, away from the part, at the smallest distance at which the tool at P clears the stock box by the air gap 0.2·R (D-079): no point of the tool's circle at P lies within 0.2·R of the stock box. Along that normal P always exists, because the stock box contains the part.
6. **One pass at depth z_i:** P → S as a LINE with role APPROACH at the plunge feed (the move may enter the stock allowance with the full tool width, so it takes the lower feed; ours); round the loop from S to S with role CUT at the cutting feed; S → P with role RETRACT at the cutting feed, through the stretch the approach already cut. The links between passes and at the start and end are topic 10's.

## Parameters

| Parameter | Unit | Default | Range | Source |
| --- | --- | --- | --- | --- |
| Side allowance s | mm | 0 | > −R | D-150 |
| Largest step-down a_p,max | mm | none (the job gives it) | > 0, at most the flute length | ours |
| Air gap at the approach point | mm | 0.2·R | declared | D-079 |
| Cutting feed, plunge feed, spindle speed | mm/min, 1/min | none (the job gives them) | > 0 | D-025 (n and vf in release 1); the cutting-data solver later |

## Traps

1. The approach move cuts into the stock allowance at full width; it takes the plunge feed.
2. A loop reversed for climb must keep its source IDs with their rows.
3. The depth is absolute in the work frame; a positive z_bottom above z_top is an input error, not an empty operation.

## Tests

1. Rectangle 100 × 60 with fillets of radius 5 (topic 21, test 1), tool R = 5, s = 0, stock box with 5 mm on every side, z_top = 0, z_bottom = −10, a_p,max = 4: three passes at −3.333…, −6.666…, −10; the loop has four lines on the rectangle's sides offset by 5 and four arcs of radius 10; it runs clockwise; S is the midpoint of a long side; P is outside the stock by at least 1 mm (0.2·R).
2. The same with s = 0.5: every cut point lies between 5.5 and 5.5 + a + 6u from the contour.
3. s = −5 (equal to −R) is refused; s = −4.9 gives a loop 0.1 mm from the contour.
4. z_bottom deeper than the flute length gives `PROFILE_TOO_DEEP`.
5. A circle of radius 20: a loop of arcs only, S at its first vertex, one circle of radius 20 + R per pass.

## Sources

Decisions D-024, D-025, D-079, D-150, D-154; research 02 (offsets). The rest is ours, marked so.

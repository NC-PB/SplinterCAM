# Research requests

<!-- Box 3 questions (docs/dev/07, "Questions: who answers"): knowledge nobody has at hand. Agents add a request here
     instead of asking Peter; Project Spike answers it with sources (D-159: research is pulled by a plan step).
     Newest last. IDs RR-NNN are never reused. Files by their path from the repository root. -->

## RR-<NNN>: <short title>

- Date: <YYYY-MM-DD>; raised by: <plan NNNN, step n>
- Question: <what must be known, one or two sentences>
- Why it matters: <the requirement or decision it blocks or makes provisional>
- What is known: <research section, tests or measurements so far, with paths>
- Provisional choice: <the conservative option taken meanwhile, DEC-… marked provisional>
- Status: Open <or: Answered on <date>, see <research section or DEC-…>>

## RR-001: A stock update that errs toward more stock

- Date: 2026-10-08; raised by: plan 0005, SPEC draft (spec-reviewer round)
- Question: how must `remove_machined` subtract a machined region from a stock layer so that the result never loses stock that is really there, and by how much must the machined region be shrunk first?
- Why it matters: REQ-OFF-032 in `src/splintercam/offset2d/SPEC.md` is blocked by it; stock layers decide safe links and skipped air passes (D-026, D-062).
- What is known: `docs/research/02-offsets-and-booleans.md`, Booleans, shrinks the machined area by 3u before the difference. But the shrink is itself a Clipper2 call on an already rounded region, against "offsets are never chained" (same section, D-132), and each of the two calls moves points by up to 2.83u in no fixed direction (SRC-118), so 3u does not cover both. Options seen: a larger margin (at least about 3u + 2·2.83u); or the machined region built from its source paths, grown by t − margin in one call, so nothing is chained.
- Provisional choice: none; REQ-OFF-032 stays out of plan 0005's steps until answered. The other Booleans do not depend on it.
- Status: Answered on 2026-10-09, see `docs/research/02-offsets-and-booleans.md`, Booleans (the stock update) and test 22: no chaining; each operation's machined area from its own centre paths grown by R − (t_flat + 6u) in one call, the stock layer as the raw layer minus all machined areas in one Difference call.

## RR-002: Corrections to research 02 found while building offset2d

- Date: 2026-10-09; raised by: plan 0005, steps 4 to 6
- Question: please take these into research 02 at its next review, each with its evidence in `src/splintercam/offset2d/DECISIONS.md`: (1) The kernel call, step 3, says normalised loops pass outer loops first, but geometry2d's loop tree keeps the input order, so an inner loop listed first can win Clipper2's tie (DEC-OFF-008, 011); (2) test 17 asks for vertices within 3u, but round joins do not keep their vertices under translation (798 against 796 measured), so the check is every vertex within 3u of the other result's boundary (DEC-OFF-013); (3) test 22's bound on the extra stock leaves out the arc tolerance a of the round joins (DEC-OFF-007); (4) Open chains: the grown path needs t_flat added to δ to cover a flattened arc on both sides (DEC-OFF-005); (5) Source IDs: the nearest input edges are those before any clean-up, which may drop the joint between an arc and its tangent side (DEC-OFF-013). (6) Test 15's second case asks for a fixed node where a hole touches the middle of an outer edge, which the Open items defer to the arc fit; and it lists the triangle clockwise, which cuts nothing with the Positive rule (DEC-OFF-014). (7) Test 12's C open narrower than 2t with the tool inside gives one open piece on its inner wall, not an open and a closed piece: by the cap rule the inner wall's edges near the mouth lie nearest the chain's ends; a closed piece needs a room away from the ends, such as an omega with a narrow neck (DEC-OFF-018). (8) Open chains: one side needs EndType Round, not Butt: Butt ends leave the area short of "within t" at the ends, so a wall near an end (a short first segment into an inside corner) comes closer than t to the end; the cap rule then drops the round ends (DEC-OFF-018). (9) Open chains: a chain that runs back over itself has no side over the overlap; offset2d refuses it with `CHAIN_FOLDS` (DEC-OFF-018).
- Why it matters: the SPEC already follows the corrected readings; the research text should not lead the next reader back to the old ones.
- What is known: each item is measured or derived in the DEC entries named.
- Provisional choice: the SPEC's readings (Peter accepted the deviations of the draft, DEC-OFF-005; the rest are box 2 decisions).
- Status: Open


## RR-003: Open profiles along a spike that turns back by nearly 180°

- Date: 2026-10-10; raised by: plan 0005, step 8 (second spec review of `offset_chain_side`)
- Question: how should one side of an open chain treat a spike, two segments meeting at a turn of nearly but not exactly 180° (for example (5, 0) to (5, -0.01) to (4.99998, 0) inside a wall along y = 0, the tool above), where the spike's tool side wraps round its tip on the far side of the main wall? Do CAM systems refuse such chains, clean them (from what angle or width), or machine them, and is there a published rule?
- Why it matters: DEC-OFF-018 refuses only exact turn-backs (`CHAIN_FOLDS`); a near turn-back gives a short piece round the spike's tip, up to t on the material side of the main wall, which a profile would cut.
- What is known: the second spec review's cases in `src/splintercam/offset2d/DECISIONS.md` (DEC-OFF-018, Not handled); a 135° turn is ordinary geometry and must stay, so a fixed angle limit needs a source.
- Provisional choice: none beyond DEC-OFF-018; such chains are passed through as drawn. The strategy's review of pieces (topic 22) should look for short open pieces between two "other" runs.
- Status: Open

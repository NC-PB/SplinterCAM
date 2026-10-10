# SPEC: <module name>

<!-- The module's contract. One to three pages. Link to research instead of repeating it.
     Agents draft; a person reviews. Agents implement only Reviewed requirements. -->

| | |
| --- | --- |
| Status | Draft / Reviewed (<date>, <name>) / Implemented |
| Layer | <n> (see architecture/modules.yaml) |
| Depends on | <modules> |
| Research | docs/research/<NN>, <NN> |
| Owner | <person> |

## Purpose

<Two to four sentences: what the module does and who uses it.>

## Scope

- In: <…>
- Out, handled elsewhere: <…>
- Non-goals: <what this module will not do, even where it looks useful>

## Public interface

<Types and functions with units, preconditions and postconditions, as Python signatures. Mark the functions backed by the C++ kernel, for example:>

```text
def offset(region: Region, distance_mm: float, mode: OffsetMode, ctx: Context) -> Result[Region]: ...
# kernel: kernel/offset.cpp (arrays in, arrays and diagnostic codes out)
```

## Requirements

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-XXX-001 | THE <module> SHALL … | property test `REQ_XXX_001_…` | Draft |
| REQ-XXX-002 | WHEN … THE <module> SHALL … | unit test `…` | Draft |

## Invariants

<Properties that hold for every valid input. Each maps to requirement IDs and a property test. Start from the module's row in RESEARCH 24 (Project Spike).>

## Tolerance budget

<Which share of the operation tolerance this module may use, and how it is split between its stages.>

## Failure modes and diagnostics

| Situation | Result | Diagnostic |
| --- | --- | --- |
| <e.g. region vanishes> | empty result | `XXX_EMPTY` (info) |

## Algorithms and design inputs

<One line per algorithm: the research section and the paper. No pseudo-code here.
For a strategy, a design-input table (clean room, D-144); the review states that no implementation details
of proprietary systems went in.>

| Element of the method | Public source, or own design with date |
| --- | --- |
| <…> | <…> |

## Example parts

<!-- Real geometry the module will meet, from Peter's shop practice, listed before the requirements are written:
     for example an island tangent to the pocket wall, a boss touching a fillet, a thin rib, a slot exactly the
     tool's width. Each becomes a golden case or a property-test generator in the Test plan. -->

- <case: what it looks like, what the module must do with it>

## Test plan

- Unit: <…>
- Property: <generators, including the messy inputs of the research topic's traps>
- Golden cases: <testdata/zoo names>
- Differential: <reference library, if any>

## Performance budget

<For example: 10 000 segments in under 50 ms on the reference machine.>

## Size estimate

<Kept code in NLOC (Python and C++) and tests. It becomes the module budget in architecture/modules.yaml;
+20 % fails `tools/size-check` (docs/dev/12, section 3).>

## Open questions

<!-- Box 1 questions for Peter only, in machining terms with a recommendation (docs/dev/07, "Questions: who answers").
     Box 2 choices go to DECISIONS.md, box 3 to docs/research/REQUESTS.md. -->

- <…>

## Change log

- <date>: <change> (<PR or change spec>)

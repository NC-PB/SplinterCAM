# Plan <NNNN>: <title>

<!-- Lives in docs/plans/active/ while work is ongoing, then moves to docs/plans/completed/.
     The agent updates the progress log at the end of every session, before stopping. -->

- Goal: <one sentence; what is true when this plan is done>
- Specs: <src/splintercam/…/SPEC.md, docs/specs/NNNN-…>
- Research: <docs/research/NN>
- Branch: <feat/…>
- Owner: <person>; agents: <which>

## Steps

<!-- Each step has a size estimate (kept code and tests). At 50 % over it, stop and ask, as for a timebox
     (engineering/12, section 3). -->

- [ ] 1. <step, with REQ IDs>; size: <lines of kept code> + <lines of tests>
- [ ] 2. <step>; size: <…>
- [ ] 3. <step>; size: <…>

## Probes

<!-- Only for questions answered with numbers (engineering/12, section 6). Delete this section if there are none. -->

- Question: <one question, and the decision it feeds>
- Folder: `spikes/<plan>/<step>/`; nothing in `src/` imports it
- Size: about 300 lines; above 600 the question is split or becomes kept code under a SPEC
- Review: one round, for measurement validity only; robustness findings are recorded, not fixed
- Result: a table in the progress log and a README of at most one page; deleted after the decision, kept by the tag <tag>

## Decisions

<!-- Small decisions made along the way, with the reason. Big ones become ADRs. -->

- <date>: <decision>, because <reason>.

## Progress log

<!-- Newest first. What was done, what tools/check reported, what is next. At most about 30 lines per session;
     numbers go into tables. Above 300 lines, older entries move to an archive file next to the plan. -->

### <date>, session <n>

- Done: <…>
- `tools/check`: <pass / fail: what>
- Size: <added / removed in src, tests, tools, spikes; module budget used>
- Next step: <…>
- Open questions for a person: <…>

## Backlog

<!-- Nice-to-have review findings: recorded here, not coded in the change that found them. -->

- <…>

## Blockers

- <…>

---
id: audit-degenerate
title: Degenerate policies must fail
track: audit
milestone: v1
priority: core
needs: gpu
size: small
status: todo
owner: ""
depends_on: []
touches:
  - "solarbench/agents/random.py"
  - "solarbench/agents/quit.py"
  - "solarbench/agents/replay.py"
  - "tools/check.sh"
  - "results/*/zero_*"
  - "results/*/random_*"
  - "results/*/quit_*"
  - "results/*/replay_*"
  - "docs/tasks.md"
done_when:
  - "tools/check.sh --gpu"
  - "results/<task>/{zero,random,quit}_dev_newton.json show 0 successes"
  - "the replay policy's score is in each task card, whatever it is"
---
## Why
A success check that passes without the work being done makes every score meaningless.

## What
- Policies `random` and `quit` (ends at the first step) as `solarbench/agents/random.py` and `quit.py`.
- For every registered task: zero, random and quit score 0 safe successes in 200 episodes.
- Policy `replay`: plays back, blind, the commands of one successful oracle episode in every episode. Its score says how much of a task can be passed by memorising one scene. It is reported, not required to be zero; a score above zero opens an item to vary what it exploited.
- Add zero, random and quit to the GPU check with a small episode count.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->

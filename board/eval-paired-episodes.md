---
id: eval-paired-episodes
title: Every policy meets the same episodes, and every episode is counted
track: eval
milestone: v1
priority: core
needs: gpu
size: medium
status: todo
owner: ""
depends_on: []
touches:
  - "scripts/evaluate.py"
  - "solarbench/eval/splits.py"
  - "solarbench/tasks/clamp_env.py"
  - "solarbench/tasks/mc4_env.py"
  - "tests/test_splits.py"
done_when:
  - "tools/check.sh --gpu"
  - ".venv/bin/python -m pytest -q tests/test_splits.py"
  - "the oracle and the zero policy, run on the same split, record the same sampled parameters for every episode index"
---
## Why
A run keeps the first N episodes to finish across the parallel environments, and draws every episode from one random stream in the order episodes happen to end. Successes end early, so slow failures are under-counted, most of all in short runs. And two policies do not meet the same episodes, which the paired analysis in `paper/hypotheses.md` assumes.

## What
- Every episode has an index. Its sampled parameters come from a generator seeded by the split and the index, whichever environment runs it.
- A run executes indices 0 to N−1 once each and waits for all of them; nothing in flight is dropped.
- The index is written into each episode record.
- Measure the size of the old bias on the bolt task with the oracle on PhysX, and record it in this log.
- The rankable oracle rows are re-run afterwards (a new item).

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->

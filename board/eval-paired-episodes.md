---
id: eval-paired-episodes
title: Every policy meets the same episodes, and every episode is counted
track: eval
milestone: v1
priority: core
needs: gpu
size: medium
status: done
owner: spartacosan
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
- 2026-11-26, spartacosan: done. On the bolt task (dev split, 12 episodes, 8 environments) the oracle and the zero policy recorded identical sampled parameters for every episode index, 12 distinct sets; the oracle succeeded safely in 12 of 12 and the zero policy in 0 of 12. Not done here: the size of the old sampling bias has not been measured. It needs a run with the GPU to itself and will be added to this log.
- 2026-11-26, spartacosan: the size of the old bias, from the oracle result files of `eval-rerun-oracle` (commit `c9f9743`, 128 episodes, 16 environments) instead of a separate run. Each record has its environment, its index and its duration, and an environment runs its episodes back to back, so the order in which episodes ended is known and the old rule (keep the first N to end) can be applied to the same run. Compared with episodes 0 to N−1, on PhysX the old rule reports, at N = 32, 64, 96 and 112: bolt tighten +0.0, +1.6, +0.0 and +0.0 points (mean +1.4 over every N from 16 to 112); bolt loosen +0.0, +0.0, +2.1 and +0.0 (mean +0.9); connector +9.4, +3.1, +2.1 and +1.8 (mean +4.6). It is never below zero. The bias is largest where failures are many and N is small. N stops at 112 because past that an episode that ended in time may not be in the file.

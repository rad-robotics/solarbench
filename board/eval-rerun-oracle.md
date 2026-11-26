---
id: eval-rerun-oracle
title: Re-run the oracle baselines from a clean tree
track: eval
milestone: v1
priority: core
needs: gpu
size: small
status: done
owner: spartacosan
depends_on: []
touches:
  - "results/*/oracle_test_*"
  - "results/RESULTS.md"
  - "README.md"
  - "docs/tasks.md"
done_when:
  - "for each of the three task ids and both engines there is a rankable oracle result file (solarbench.eval.schema.rankable returns nothing)"
  - "the README table is rebuilt from those files"
  - "tools/check.sh"
---
## Why
The oracle results in the README were made before the provenance rule and before the package was restructured. None of them is rankable: no commit recorded, or the tree was not clean.

## What
- From a clean tree at a commit on `main`: both bolt tasks and the connector task, held-out seeds, at least 100 episodes each, on Newton and on PhysX.
- `scripts/evaluate.py` names a repeat run with its commit, so the old files stay.
- Regenerate `results/RESULTS.md` and update the README table from it.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
- 2026-11-26, spartacosan: done. Six runs from a clean tree at `c9f9743`, 128 held-out episodes each, 16 environments. Safe success, Newton then PhysX: connector 127/128 and 111/128; tighten 127/128 and 119/128; loosen 128/128 and 119/128. No damage and no simulator error in any run. All six files are rankable. `docs/tasks.md` was added to `touches` because it quoted two of the old numbers; it now links to the table instead.
- The connector on PhysX is the one cell outside the interval of the row it replaces: 111/128 (80%–92%) against 18/32 (39%–72%). The old file records no commit and was written before the first commit of the history. Run today on PhysX, the earliest copy of the code that was kept, from the day of the old run and older than this repository's history, gives 82/128 (56%–72%) with the evaluator of that time, so the old level reproduces and the difference is in the code, not in the episodes drawn. Between the two, the cable model changed: the tether is now anchored at the last cable tie with a 0.45 m free tail instead of at the junction box with the full lead, and the neighbouring modules became collision bodies. Which of these moved the rate was not isolated. The old PhysX row had not been re-run after that change.
- New in these runs: on PhysX, tightening, one failed episode exceeded a joint velocity limit for 29 control steps (`vel_limit_violation_steps`); none did on Newton.

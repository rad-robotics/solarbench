---
id: eval-rerun-oracle
title: Re-run the oracle baselines from a clean tree
track: eval
milestone: v1
priority: core
needs: gpu
size: small
status: doing
owner: spartacosan
depends_on: []
touches:
  - "results/*/oracle_test_*"
  - "results/RESULTS.md"
  - "README.md"
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

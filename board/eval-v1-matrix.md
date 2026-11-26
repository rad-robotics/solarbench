---
id: eval-v1-matrix
title: Run the pre-registered matrix
track: eval
milestone: v1
priority: core
needs: gpu-large
size: large
status: todo
owner: ""
depends_on: [paper-prereg, contract-result-fields, sim-difficulty-dial, sim-guarded-skills, sim-wire-cameras, agents-endpoint, agents-prompts, agents-serve, agents-skill-tools, eval-latency, eval-margin, eval-tracker, audit-readback, audit-degenerate, audit-invariance, eval-paired-episodes, contract-policy-inputs, contract-rankable, infra-container]
touches:
  - "results/*"
  - "ASSUMPTIONS.md"
done_when:
  - "every cell of the matrix has a rankable result file"
  - "tools/check.sh"
---
## Why
The first result.

## What
- Run every cell of `paper/hypotheses.md` from a clean tree at a tagged commit.
- Commit the result files unedited, including cells that contradict the hypotheses.
- Regenerate `results/RESULTS.md` and the tracker.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->

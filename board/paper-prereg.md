---
id: paper-prereg
title: Freeze the hypotheses before any model run
track: paper
milestone: v1
priority: core
needs: none
size: small
status: doing
owner: spartacosan
depends_on: [contract-interface]
touches:
  - "paper/hypotheses.md"
done_when:
  - "git tag -l prereg-v1  # exists and predates every language-model result file"
---
## Why
Predictions written after the results are not predictions.

## What
- Review `paper/hypotheses.md` as a team; fix the matrix, the episode counts and the analysis.
- Tag the commit `prereg-v1`. Later changes go in a dated addendum, never an edit.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->

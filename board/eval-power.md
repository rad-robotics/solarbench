---
id: eval-power
title: Set the episode count from a power calculation
track: eval
milestone: v1
priority: core
needs: cpu
size: small
status: todo
owner: ""
depends_on: []
touches:
  - "scripts/power.py"
done_when:
  - "python scripts/power.py prints, for 30 and 100 paired episodes, the probability that H2's analysis detects a given rise in safe success"
  - "this item's log records the smallest rise H2's analysis detects with 80% probability at 30 and at 100 paired episodes, for paper-prereg to choose the count from"
---
## Why
H2 is decided by a 95% interval of the paired difference excluding zero, with at least 30 episodes per cell. Nothing in `paper/hypotheses.md` says what difference 30 episodes can detect, so a null H2 would not separate "force feedback does not help" from "too few episodes to see it". A simulation of H2's analysis outside this repository, not yet reproduced here, gave a 47–61% chance of detecting a rise from 10% to 30% at 30 episodes and 95–99% at 100 (range over seed correlation 0 to 0.5, 2,000 simulated experiments each). STEP reports power generally low for gaps under 20 percentage points even at 100 trials [P, supplement Fig. 7] https://arxiv.org/abs/2503.10966

## What
- `scripts/power.py`: simulate H2's own analysis (the same seeds with force off and on, 95% bootstrap interval of the mean paired difference) over a grid of off and on safe-success rates and seed correlations; print the probability of detection for 30 and 100 episodes. Fixed seed; no GPU.
- Put three options to the owner of `paper-prereg`, who chooses before the freeze and records the choice in that item's log: raise the language-model cells to the count the script gives; or keep a cap and stop early with a sequential test, STEP for safe success or N-SCORE for furthest stage reached [P] https://arxiv.org/abs/2603.13616 ; or keep 30 and state in the hypotheses the smallest rise H2 can detect.
- H2 is tested for two models on two tasks. State the correction for testing more than once, or why none is needed.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->

---
id: open-real-arm
title: Paired trials on a real arm
track: eval
milestone: open
priority: core
needs: bench
size: large
status: todo
owner: ""
depends_on: []
touches: []
done_when:
  - "paired results for at least two systems on one task, with raw logs"
---
## Why
The measure of the benchmark is whether its ordering of systems holds on hardware.

## What
- The same brain, interface and prompts on a real arm with wrist force sensing, on a real connector and bolt.
- Report agreement between simulated and real outcomes, including where they disagree.
- Report agreement as SIMPLER does: mean maximum rank violation (each pair simulation orders wrongly, weighted by how far apart the two are on hardware) and Pearson r [P] https://arxiv.org/abs/2405.05941

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->

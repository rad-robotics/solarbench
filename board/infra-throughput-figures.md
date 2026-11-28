---
id: infra-throughput-figures
title: Correct the run times quoted for the bolt tasks
track: infra
milestone: v1
priority: core
needs: gpu
size: small
status: todo
owner: ""
depends_on: [sim-bolt-newton-speed]
touches:
  - "docs/tasks.md"
  - "tools/check.sh"
done_when:
  - "the throughput line in docs/tasks.md gives figures measured after sim-bolt-newton-speed, with the machine named"
  - "the comment at the top of tools/check.sh gives the measured time of tools/check.sh --gpu"
  - "tools/check.sh"
---
## Why
`sim-bolt-newton-speed` made the bolt tasks several times faster on Newton. `docs/tasks.md` still says 64 held-out episodes take about 25 minutes and gives a simulation rate from before the change; `tools/check.sh` says its GPU pass takes about 20 minutes. On an RTX 2070 with 8 GB, after the change, the 64-episode command took 146 s and `tools/check.sh --gpu` took 224 s. The README's figure was corrected in `eval-readme-status`.

## What
- Measure again on a named machine: wall time of the 64-episode command, simulated seconds per wall-clock second at 16 environments, GPU memory. Replace the throughput line with those.
- Time `tools/check.sh --gpu` and correct its comment.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->

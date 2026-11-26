---
id: audit-invariance
title: Results do not depend on time step or batch size
track: audit
milestone: v1
priority: core
needs: gpu
size: small
status: todo
owner: ""
depends_on: []
touches:
  - "docs/tasks.md"
  - "ASSUMPTIONS.md"
  - "results/*/oracle_dev_*_dt*"
  - "results/*/oracle_dev_*_n*"
done_when:
  - "a table in docs/tasks.md under each task; no flagged difference, or an ASSUMPTIONS.md entry explaining one"
---
## Why
If a score moves when the solver step or the number of parallel environments changes, it measures the solver.

## What
- Oracle evaluation at half the physics step, and at 1 versus 16 environments, for each task.
- Report success and installed torque with intervals; flag any difference whose intervals do not overlap.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->

---
id: contract-harness-catalogue
title: The evaluator reads a task's catalogue and delivers its work order
track: contract
milestone: v1
priority: core
needs: gpu
size: small
status: todo
owner: ""
depends_on: [contract-policy-inputs, sim-obs-channels]
touches:
  - "scripts/evaluate.py"
  - "solarbench/agents/__init__.py"
  - "solarbench/tasks/mc4_env.py"
  - "tests/test_agents.py"
done_when:
  - "tools/check.sh --gpu"
  - "a test policy that selects `proprio` runs on the bolt task, receives that channel and the work order, and its result is recorded as not privileged"
---
## Why
`contract-policy-inputs` builds a policy from a catalogue that the evaluator writes itself, with the privileged state vector as the only channel. `sim-obs-channels` gives the bolt task a catalogue of its own, with sensor channels and a work order. Nothing joins the two: a sensor-only policy cannot yet be run, and a policy that is not given the environment has no way to read the work order.

## What
- `scripts/evaluate.py` takes the catalogue from the task and hands the policy the channels it selected, as the task returns them. The catalogue and the clock that the evaluator builds today are removed.
- The connector task publishes its catalogue the same way (`solarbench/tasks/channels.py`): the clock and the privileged state vector.
- The work order reaches the policy as the `EPISODE` message of `docs/interface.md`: `reset` is called with the environments that start an episode and the work order of each.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->

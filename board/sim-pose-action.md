---
id: sim-pose-action
title: 'Action mode: absolute end-effector pose per step'
track: sim
milestone: v1
priority: core
needs: gpu
size: medium
status: todo
owner: ""
depends_on: [sim-obs-channels]
touches:
  - "solarbench/tasks/actions.py"
  - "solarbench/tasks/clamp_env.py"
  - "solarbench/tasks/clamp_env_cfg.py"
  - "solarbench/tasks/__init__.py"
  - "tests/test_actions.py"
  - "docs/tasks.md"
done_when:
  - "tools/check.sh --gpu"
  - ".venv/bin/python -m pytest -q tests/test_actions.py"
---
## Why
The second rung (R2). Reasoning models emit one target pose per round, not small deltas at 30 Hz.

## What
- `solarbench/tasks/actions.py`: run a `TOOL_POSE` record of `docs/interface.md` as rate-limited steps for the existing IK, under the same joint torque and velocity limits, and write its completion when it arrives, stalls or times out.
- Profile R2 on the bolt task under a task id of its own; existing ids keep their behaviour.
- The oracle, replayed as `TOOL_POSE` records, still succeeds.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->

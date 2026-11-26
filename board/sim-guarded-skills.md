---
id: sim-guarded-skills
title: 'Action mode: guarded force skills'
track: sim
milestone: v1
priority: core
needs: gpu
size: large
status: todo
owner: ""
depends_on: [sim-pose-action, contract-skill-opcodes]
touches:
  - "solarbench/tasks/skills.py"
  - "solarbench/tasks/clamp_env.py"
  - "tests/test_skills.py"
  - "docs/tasks.md"
done_when:
  - "tools/check.sh --gpu"
  - "a scripted sequence of skill calls completes the bolt task; a sequence with a 30 N·m request records damage"
---
## Why
The third rung (R3): the model says what to do and how hard; a fixed controller does the contact.

## What
- `solarbench/tasks/skills.py`: `move_to`, `move_until_contact`, `push_with_force`, `turn_until_torque`, `retract`, each with limits and a returned status.
- Skills use the same controllers and torque limits as the oracle and can fail: a wrong target misses, a torque request above the window damages the bolt.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->

---
id: sim-obs-channels
title: 'Observation channels on the bolt task: proprio, wrench, prompt'
track: sim
milestone: v1
priority: core
needs: gpu
size: medium
status: todo
owner: ""
depends_on: [contract-interface]
touches:
  - "solarbench/tasks/channels.py"
  - "solarbench/tasks/clamp_env.py"
  - "solarbench/tasks/clamp_env_cfg.py"
  - "tests/test_channels.py"
  - "ASSUMPTIONS.md"
  - "docs/tasks.md"
done_when:
  - "tools/check.sh --gpu"
  - ".venv/bin/python -m pytest -q tests/test_channels.py"
---
## Why
Agents today get a privileged state vector. The experiment needs sensor-only observations with wrist force switchable on and off.

## What
- Add the `proprio` and `wrench` channels and the work order of `docs/interface.md` to the bolt task, next to the existing `policy` channel, and offer them in the task's catalogue (`solarbench/wire.py`), with field ranges from the robot description.
- Put the shared code in `solarbench/tasks/channels.py` so the connector task reuses it.
- Wrench: force and torque at the tool flange in the tool frame, with the sensor model (rate, noise, range) written into ASSUMPTIONS.md.
- A unit or integration test presses the tool on a fixed surface with a known force and checks sign, frame and magnitude.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->

---
id: sim-obs-channels
title: 'Observation channels on the bolt task: proprio, wrench, prompt'
track: sim
milestone: v1
priority: core
needs: gpu
size: medium
status: done
owner: spartacosan
depends_on: [contract-interface]
touches:
  - "solarbench/tasks/channels.py"
  - "solarbench/tasks/clamp_env.py"
  - "solarbench/tasks/clamp_env_cfg.py"
  - "tests/test_channels.py"
  - "ASSUMPTIONS.md"
  - "docs/tasks.md"
  - "solarbench/specs/robots.py"
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
- 2026-11-26, spartacosan: done for the bolt task. `solarbench/specs/robots.py` was added to `touches` for the sensor's data-sheet values. The wrench is read from the simulator's joint-wrench sensor at the joint that holds the tool. In free space on Newton it read (3.49, −2.00, −11.06) N against a tool weight of (−3.49, 2.00, 11.06) N in the tool frame, and 14.71 N·m about the tool axis against a drive torque of 14.70 N·m while tightening; on PhysX the channel shows the same press (about −24 N along tool z) and the same limit. GPU check: oracle 8/8 and zero policy 0/8 on the bolt and on the connector, and the bolt's eight dev episodes have the same sampled parameters as before the change.
- Open for the maintainer: the sensor built into the UR16e flange measures torque to ±10 N·m, below the 14–18 N·m window, so with it the channel cannot show whether the bolt is in the window (ASSUMPTIONS M12). The noise level is our reading of the data sheet's precision.
- Not done: nothing hands these channels to a policy yet (`contract-harness-catalogue`); the connector is unchanged; there is no automated test inside the simulator; training with the extra observation keys was not run. The data-sheet values were read by a research subagent, not by the author.

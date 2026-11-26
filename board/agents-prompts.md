---
id: agents-prompts
title: Embodiment and task prompts
track: agents
milestone: v1
priority: core
needs: cpu
size: small
status: done
owner: spartacosan
depends_on: [contract-interface]
touches:
  - "solarbench/agents/prompts/*"
  - "tests/test_prompts.py"
done_when:
  - "tools/check.sh"
  - ".venv/bin/python -m pytest -q tests/test_prompts.py  # the force-on and force-off variants differ only in force lines; every work order names every stage and damage condition of its task"
---
## Why
The prompt is part of the experiment. It must be fixed, versioned and identical across models.

## What
- One Markdown file per robot under `solarbench/agents/prompts/` (frames, units, limits, tool geometry) and one per task (the work order).
- Variants for wrist force on and off that differ only in the lines about force. A test checks that.
- A work order states every condition the task is scored on, including the last stage (withdrawing the tool) and what counts as damage. A test compares each work order with the task's stage list. Benchmarks that scored an unstated requirement measured whether the model guessed it.
- Camera placement lines are added by the item that adds cameras.
- The connector's files are written with the item that gives the connector its sensor channels. The Unitree G1 has no wrist force-torque sensor, so what its force lines would describe is not decided.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
- 2026-11-26, spartacosan: done for the bolt: `UR16e.md` and the tighten and loosen work orders, with a loader that fills body numbers from `solarbench/specs` and leaves a work order's numbers to the task. The test reads each task's scored conditions from its newest result file. Not done: the connector and the G1 (see What). Not verified: the text has not been read by any model, and the lines on the force sensor's sign and zero describe the channel that `sim-obs-channels` has yet to build. Open for the maintainer before the prompts are frozen: the work order gives the bolt head's position and axis, as a site plan would, since no camera exists yet; it does not give the clamp's stiffness.

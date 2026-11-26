---
id: agents-prompts
title: Embodiment and task prompts
track: agents
milestone: v1
priority: core
needs: cpu
size: small
status: todo
owner: ""
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

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->

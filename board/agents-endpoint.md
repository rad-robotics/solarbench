---
id: agents-endpoint
title: Policy adapter for any chat-completions endpoint
track: agents
milestone: v1
priority: core
needs: cpu
size: medium
status: blocked
owner: spartacosan
depends_on: [contract-interface, contract-harness-catalogue]
touches:
  - "solarbench/agents/endpoint.py"
  - "tests/test_endpoint.py"
  - "docs/models.md"
done_when:
  - "tools/check.sh"
  - ".venv/bin/python -m pytest -q tests/test_endpoint.py"
---
## Why
One adapter serves a local open-weight model and a remote one alike: where the brain runs is a URL.

## What
- `solarbench/agents/endpoint.py`: builds the request from the selected channels (work order, images, proprio, optional wrench) and turns the reply into one `TOOL_POSE` record per round. The catalogue and the work order go first in the request and do not change within an episode.
- Base URL, model name and sampling settings come from arguments or environment variables. No key is ever written to a result file.
- Requests for all environments go out concurrently. Tokens, wall time and parse failures are logged per call into the episode record.
- Tests run against a local fake server; no GPU or network.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
- 2026-11-26, spartacosan: blocked on `contract-harness-catalogue`. The adapter, its tests and `docs/models.md` are written and tested against a stand-in server. Its `reset` takes the work orders of the episodes that start, which the evaluator does not pass until that item is done; and no task offers the profile it speaks until `sim-pose-action`. The call log (wall time, tokens, readable or not) is kept on the policy; writing it into the episode records is `contract-result-fields`.

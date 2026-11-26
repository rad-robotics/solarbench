---
id: contract-result-fields
title: Record the experiment's settings in every result file
track: contract
milestone: v1
priority: core
needs: cpu
size: small
status: todo
owner: ""
depends_on: [contract-interface]
touches:
  - "solarbench/eval/schema.py"
  - "scripts/evaluate.py"
  - "tests/test_schema.py"
  - "docs/interface.md"
done_when:
  - "tools/check.sh"
  - "a result file missing one of the new fields fails validate(); the result files already checked in still pass"
---
## Why
A result is only comparable if it says how it was made. Today a result file records the task, policy, split and provenance, but not which observations were on, how time passed, or which prompt was used.

## What
- Add to the result file and to `validate`: the selection and its layout hash, time mode and the age of the observation behind each command buffer, difficulty-dial value, prompt hash, the index of each episode, and for a model: name, weights revision and quantisation, server name and version, sampling settings, whether the endpoint was local or remote, the adapter's encoding, and tokens read and written per call.
- Bump `SCHEMA_VERSION`. Files written under the earlier version stay valid.
- Update section 4 of `docs/interface.md` to say the fields exist.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->

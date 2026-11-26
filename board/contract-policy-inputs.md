---
id: contract-policy-inputs
title: A sensor-only policy is built from the catalogue, not from the environment
track: contract
milestone: v1
priority: core
needs: cpu
size: small
status: todo
owner: ""
depends_on: [contract-interface]
touches:
  - "solarbench/agents/__init__.py"
  - "scripts/evaluate.py"
  - "tests/test_agents.py"
  - "CONTRIBUTING.md"
done_when:
  - "tools/check.sh"
  - "a result is recorded as privileged exactly when a privileged channel was selected; the policy cannot set it"
  - "a test policy that selected no privileged channel and reaches for the environment object fails"
---
## Why
The policy factory receives the environment object, which holds the simulator state and the episode scores, and each policy declares for itself whether it is privileged. The TorchScript baseline reads the privileged `policy` vector and is recorded as sensor-only. Agent benchmarks in which the agent could reach the grader have been taken to full marks without a task being solved ([Berkeley RDI, 2026](https://rdi.berkeley.edu/blog/trustworthy-benchmarks-cont/)).

## What
- A factory receives the catalogue of `docs/interface.md` and returns a policy and its selection. Only a policy that selects a privileged channel is also given the environment.
- `scripts/evaluate.py` hands a policy the selected channels only, and writes `privileged` from the selection.
- The TorchScript baseline selects `policy` and is therefore recorded as privileged.
- This closes the accidental path, not a determined one: code in the same process can still reach anything. Running a policy in a separate process is part of `open-hidden-split`. Say so in CONTRIBUTING.md.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->

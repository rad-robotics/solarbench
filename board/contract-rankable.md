---
id: contract-rankable
title: Tighten what makes a result rankable
track: contract
milestone: v1
priority: core
needs: cpu
size: small
status: todo
owner: ""
depends_on: [contract-result-fields]
touches:
  - "solarbench/eval/schema.py"
  - "tests/test_schema.py"
  - "ASSUMPTIONS.md"
  - "CONTRIBUTING.md"
done_when:
  - "tools/check.sh"
  - "a result made with a configuration override other than the choice of physics engine is not rankable"
  - "a result with fewer episodes than the analysis plan requires, or more simulator errors than the stated share, is not rankable"
---
## Why
A result is rankable today if it used held-out seeds from committed, unmodified code. It stays rankable with any configuration override on the command line, with any number of episodes, and with any share of episodes excluded as simulator errors.

## What
- `rankable()` also requires: no override beyond an explicit list (today, the physics engine); at least the number of episodes the analysis plan fixes; simulator errors below a stated share.
- Decide that share, and whether an excluded episode should instead count as a failure, and record the decision next to B3 in ASSUMPTIONS.md.
- Result files already checked in are not edited; those that stop being rankable are shown as such.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->

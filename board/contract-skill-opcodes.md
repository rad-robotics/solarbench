---
id: contract-skill-opcodes
title: Guarded force skills as wire 1.1
track: contract
milestone: v1
priority: core
needs: none
size: small
status: todo
owner: ""
depends_on: [contract-interface]
touches:
  - "docs/interface.md"
  - "solarbench/wire.py"
  - "tests/test_wire.py"
done_when:
  - "tools/check.sh"
  - "docs/interface.md lists profile R3 with the arguments, end conditions and completion results of each skill, in a pull request the maintainer approved"
---
## Why
The first version of the interface carries tool deltas and tool poses. The third rung, in which the model says what to do and how hard and a fixed controller handles the contact, is added as a minor version so that nothing already agreed moves.

## What
- Opcodes 16 to 31: `move_until_contact`, `push_with_force`, `turn_until_torque`, `retract`, each with its arguments, limits, end conditions and the four result values of its completion.
- Profile R3 in section 4; the minor version becomes 1.1.
- A reader of 1.0 still reads every 1.0 message. A test shows it.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->

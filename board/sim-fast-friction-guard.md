---
id: sim-fast-friction-guard
title: Guard the friction-only fast path against a changed Newton
track: sim
milestone: v1
priority: core
needs: gpu
size: small
status: todo
owner: ""
depends_on: [sim-bolt-newton-speed]
touches:
  - "solarbench/tasks/clamp_env.py"
  - "tests/test_fast_friction.py"
done_when:
  - "with a Newton version other than the one the input list was read from, the patch is not installed and a warning says so"
  - "a unit test fails if the pinned Newton's _update_joint_dof_properties reads a model attribute that the fast path neither compares nor is documented as exempt"
  - "model.body_flags and model.body_q are compared, or the docstring says why they need not be"
  - "tools/check.sh --gpu"
---
## Why
`sim-bolt-newton-speed` skips the solver's constant recompute when only joint friction changed. It decides that by comparing a list of inputs copied from one release of a private Newton function. Review of that change (pull request 14) found the list right for what the bolt tasks write, and found three ways it could go wrong later without anyone noticing: a Newton upgrade that adds an input, and two inputs the function reads that the list leaves out.

## What
- Install the patch only for the Newton version the list was read from. Otherwise leave the full path, which is slow and right.
- Compare `model.body_flags` (read by `update_dof_properties_kernel`) and `model.body_q` (read by `sync_qpos0_kernel` for free joints, which sets the `qpos0` the recompute linearises about), or say in the docstring why a change to them cannot arrive with a friction-only flag.
- Say in the docstring that the fast path does not wake sleeping worlds, and that sleeping is off.
- A unit test that reads the source of the pinned function and holds the list against it. No simulator needed.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->

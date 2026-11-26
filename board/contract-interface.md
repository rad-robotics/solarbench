---
id: contract-interface
title: Freeze the observation, action and timing contract
track: contract
milestone: v1
priority: core
needs: none
size: small
status: done
owner: spartacosan
depends_on: []
touches:
  - "docs/interface.md"
  - "solarbench/wire.py"
  - "tests/test_wire.py"
done_when:
  - "the status line of docs/interface.md reads `frozen v1`, in a pull request the maintainer approved"
  - "tools/check.sh  # includes tests/test_wire.py"
---
## Why
The sim and agents tracks work in parallel against `docs/interface.md`. It must be agreed before either builds on it.

## What
- Read `docs/interface.md` against what the sim and agents items need, and correct anything that would not work.
- The maintainer changes the status line at the top to `frozen v1` and records the date.
- After the freeze, any change needs a new contract item.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
- 2026-11-26, spartacosan: proposal rewritten as a versioned binary contract (catalogue and selection agreed once, fixed-layout frames, 64-byte command records, 32-byte completions, time in control ticks), with the layouts in `solarbench/wire.py`. Guarded skills (R3) are left to a later minor version. Not frozen: the status line is still `proposal`.
- 2026-11-26, spartacosan: cost of the byte encoding, best of 5 on one core of a Ryzen 7 3700X, numpy 2, while a GPU evaluation was running on the same machine. JSON of the same numbers is shown for scale; it is not a transport anyone proposed.

  | 16 environments | Bytes | Pack | Unpack | As JSON: bytes, write, read |
  |---|---|---|---|---|
  | state, wrench, completions | 2,784 | 6.8 µs | 4.3 µs | 9,056; 223 µs; 101 µs |
  | the same and one 640×480 image each | 14,748,384 | 1,562 µs | 5.3 µs | 77,219,369; 1.63 s; 1.30 s |
  | command buffer, depth 1 | 1,056 | 0.9 µs | 1.1 µs | not measured |

  Checking a command buffer for unknown opcodes and non-finite arguments took 28 µs. The in-process path (arrays passed by reference) was not timed: it does no work. Not measured: a GPU tensor crossing to another process, which adds a device-to-host copy.
- 2026-11-26, spartacosan: frozen as v1 (wire 1.0).

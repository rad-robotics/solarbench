---
id: sim-bolt-newton-speed
title: Bolt tasks on Newton without a solver rebuild every substep
track: sim
milestone: v1
priority: stretch
needs: gpu
size: small
status: done
owner: psyberLC
depends_on: [sim-obs-channels]
touches:
  - "solarbench/tasks/clamp_env.py"
done_when:
  - "tools/check.sh --gpu"
  - "oracle on both bolt tasks, Newton, test split, 32 episodes, 16 environments, four runs without the change and four with it: the same safe success, damage and stages for every episode index in all eight runs; and for installed torque and for duration, with d the median over episodes of the absolute difference between two runs, the mean d over the 16 unmodified-changed pairs minus the mean d over the 12 pairs within a group is reached or exceeded by at least two of the 35 ways to split the eight runs into two groups of four (permutation p > 0.05)"
  - "the wall time of those runs, before and after, is recorded in this item's log"
---
## Why
The bolt resistance is written as joint friction every physics substep. Newton 1.6.1's MuJoCo solver answers every joint-property change with a full `set_const_0`, about 58 ms on an RTX 4060 Laptop and 91% of a profiled run, so the bolt tasks run about ten times slower than they need to. Friction loss is not an input of `set_const_0`; the rebuild returns what it had.

## What
- When nothing but joint friction changed since the last full update, copy the joint properties into the solver and skip `set_const_0`. Any other joint-property change still takes the full path. Newton only; PhysX is untouched.
- No physics value changes: before and after give the same outcome for every episode index.
- The fast path works around a broad flag in Newton. `deps-watch` should drop it once Newton no longer rebuilds on friction-only changes.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
- 2026-11-26, psyberLC: profiled the oracle on ClampTighten (Newton, 1 environment, 2 episodes) with cProfile: 1,084 of 1,158 s in `SolverMuJoCo.notify_model_changed` → `set_const_0`, called once per `_apply_action` (18,760 each).
- 2026-11-26, psyberLC: on c9f9743 (RTX 4060 Laptop, 16 environments, test split, 32 episodes) the unmodified code ran twice and the change once. Every run: 32/32 safe successes, 0 damage, on both bolt tasks; safe success, damage and every stage agree for all 64 episode indices across the three runs. Wall time: ClampTighten 493 s → 69 s, ClampLoosen 455 s → 68 s. Per-episode ClampTighten torque difference, median / max: unmodified vs unmodified 0.016 / 0.059 N·m; unmodified vs changed 0.017 / 0.105 and 0.013 / 0.108 N·m. ClampLoosen final torque identical in all runs; duration differences up to 3.9 s between the two unmodified runs and up to 7.0 s against the change, medians 0.05–0.08 s for every pair. The first wording of the second `done_when` line ("installed torque within 0.01 N·m") was set before measuring and fails for the unmodified code against itself (0.059 N·m); it is replaced by a comparison with the measured run-to-run spread. `tools/check.sh --gpu` passed on f6b54f5 before `sim-obs-channels` was claimed.
- 2026-11-26, psyberLC: blocked. `sim-obs-channels` (#10, opened earlier) holds `solarbench/tasks/clamp_env.py`. Rebase onto it once it merges, re-run the `done_when` lines and open the pull request.
- 2026-11-26, psyberLC: rebased onto `50119ca` (`sim-obs-channels` merged) and unblocked. Same runs as above, unmodified `ac2f05b` twice and changed `72042ba` once: 32/32 safe successes and 0 damage in every run, on both bolt tasks; safe success, damage and every stage agree for all 64 episode indices. Wall time: ClampTighten 509 and 518 s → 76 s, ClampLoosen 486 and 490 s → 72 s. The second `done_when` line as then written fails. ClampTighten torque, median difference: unmodified vs unmodified 0.017 N·m; unmodified vs changed 0.028 and 0.015 N·m (maxima 0.111 against 0.101 and 0.099). ClampLoosen duration: 0.067 s against 0.100 and 0.133 s (maxima 3.8 against 4.1 and 3.8 s). A single unmodified pair is too few to set a threshold, and the same rule would also often fail between runs of the same code. Before any further run, that line is replaced by a permutation test over four runs of each. This is the second change to that line; both failures are recorded here.
- 2026-11-26, psyberLC: done. Eight runs, unmodified `ac2f05b` four times and changed (`72042ba` once, `908374c` three times): 32/32 safe successes and 0 damage in every run, on both bolt tasks; safe success, damage and every stage agree for all 64 episode indices across the eight runs. Permutation test over the 35 splits: ClampTighten torque p = 0.66 (pairwise median differences: unmodified 0.012–0.028 N·m, changed 0.018–0.019, across 0.010–0.028); ClampTighten duration p = 0.97; ClampLoosen duration p = 0.49 (unmodified 0.067–0.100 s, changed 0.067–0.167, across 0.067–0.133). ClampLoosen final torque is identical in every run, so that test passes trivially (p = 1). Wall time: ClampTighten 481–535 s → 60–76 s, ClampLoosen 466–490 s → 57–72 s. `tools/check.sh --gpu` passed on `72042ba`; later commits change only this file.

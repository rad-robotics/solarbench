---
id: eval-margin
title: 'Margin to spec: the 50% threshold on the difficulty dial'
track: eval
milestone: v1
priority: core
needs: cpu
size: small
status: done
owner: spartacosan
depends_on: []
touches:
  - "solarbench/eval/margin.py"
  - "tests/test_margin.py"
done_when:
  - "tools/check.sh  # includes tests/test_margin.py"
---
## Why
The headline number: how close to the real specification a system still works half the time.

## What
- `solarbench/eval/margin.py`: `margin(levels)` takes `{dial_level: (safe_successes, episodes)}` and returns the dial level with 50% safe success and its interval, by the method fixed in `paper/hypotheses.md` (isotonic fit, interpolation, bootstrap).
- Returns "beyond the tested range" when the fit never crosses 50%; it does not extrapolate.
- Tested on synthetic data with a known threshold, and on data with no crossing.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
- 2026-11-26, spartacosan: `margin()` added. Two conventions the method text leaves open are settled in the module and its tests: a crossing outside the tested levels is named by side (`tighter`, `looser`), for the estimate and for either end of the interval; and where pooled rates sit at exactly one half over several levels, the tightest of them is reported.

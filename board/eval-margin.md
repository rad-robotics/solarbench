---
id: eval-margin
title: 'Margin to spec: the 50% threshold on the difficulty dial'
track: eval
milestone: v1
priority: core
needs: cpu
size: small
status: doing
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

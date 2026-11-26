"""Margin to spec: the tightest setting of the difficulty dial at which a system still succeeds safely half the time.

The method is fixed in ``paper/hypotheses.md``: an isotonic fit of the safe-success rate against the logarithm of
the dial level, the 50 % crossing by linear interpolation between tested levels, and a bootstrap over the episodes
within each level for the interval. A dial level of 1.0 is the real specification; larger is easier.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence

# A crossing outside the tested levels is named, never extrapolated: "tighter" when the fit is above one half
# even at the tightest tested level, "looser" when it is below one half even at the loosest.
TIGHTER, LOOSER = "tighter", "looser"


def isotonic(rates: Sequence[float], weights: Sequence[float]) -> list[float]:
    """Weighted least-squares fit that never decreases (pool adjacent violators)."""
    blocks: list[list[float]] = []  # [weighted mean, weight, number of points]
    for rate, weight in zip(rates, weights, strict=True):
        blocks.append([rate, weight, 1])
        while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0]:
            mean, w, count = blocks.pop()
            blocks[-1] = [
                (blocks[-1][0] * blocks[-1][1] + mean * w) / (blocks[-1][1] + w),
                blocks[-1][1] + w,
                blocks[-1][2] + count,
            ]
    return [mean for mean, _, count in blocks for _ in range(int(count))]


def _crossing(log_levels: Sequence[float], successes: Sequence[int], episodes: Sequence[int]) -> float:
    """Log dial level at which the fit first reaches one half; ``-inf`` or ``inf`` if it lies outside the levels."""
    fit = isotonic([k / n for k, n in zip(successes, episodes, strict=True)], episodes)
    if fit[0] > 0.5:
        return -math.inf
    if fit[-1] < 0.5:
        return math.inf
    i = next(i for i, rate in enumerate(fit) if rate >= 0.5)
    if i == 0:
        return log_levels[0]
    share = (0.5 - fit[i - 1]) / (fit[i] - fit[i - 1])
    return log_levels[i - 1] + share * (log_levels[i] - log_levels[i - 1])


def _report(log_level: float) -> float | str:
    if math.isinf(log_level):
        return TIGHTER if log_level < 0 else LOOSER
    return math.exp(log_level)


def margin(levels: Mapping[float, tuple[int, int]], n_boot: int = 2000, alpha: float = 0.05, seed: int = 0) -> dict:
    """Dial level with 50 % safe success, from ``{dial_level: (safe_successes, episodes)}``.

    Returns ``level`` (``None`` when the fit never crosses one half inside the tested levels), ``beyond`` (``None``,
    or which side the crossing lies on) and ``ci95``, whose ends are dial levels or the name of the side they fall on.
    """
    if not levels:
        raise ValueError("no dial levels")
    dial = sorted(levels)
    successes, episodes = [levels[d][0] for d in dial], [levels[d][1] for d in dial]
    if dial[0] <= 0 or any(n <= 0 or not 0 <= k <= n for k, n in zip(successes, episodes, strict=True)):
        raise ValueError("dial levels must be positive, with 0 <= safe_successes <= episodes and episodes > 0")
    logs = [math.log(d) for d in dial]
    point = _crossing(logs, successes, episodes)

    rng = random.Random(seed)
    boots = sorted(
        _crossing(logs, [sum(rng.random() < k / n for _ in range(n)) for k, n in zip(successes, episodes, strict=True)],
                  episodes)
        for _ in range(n_boot)
    )
    lo = boots[int(alpha / 2 * n_boot)]
    hi = boots[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return {
        "level": None if math.isinf(point) else math.exp(point),
        "beyond": _report(point) if math.isinf(point) else None,
        "ci95": [_report(lo), _report(hi)],
        "tested": [dial[0], dial[-1]],
    }

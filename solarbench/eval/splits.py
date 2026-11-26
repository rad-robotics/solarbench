"""Seed splits. ``dev`` is for development and tuning; ``test`` seeds are held out and must only be used for
reported numbers. Randomization ranges are identical across splits for now (only the seeds differ); harder
held-out variation splits (unseen clearances, start poses, module SKUs) are planned (ASSUMPTIONS B2).

An episode is identified by its index within a split. Everything sampled for it depends on the split's seed and
that index alone, so every policy meets the same episodes, whichever parallel environment runs them and in
whatever order they end.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Split:
    name: str
    base_seed: int
    description: str


SPLITS = {
    "dev": Split("dev", 0, "development seeds; tune freely"),
    "test": Split("test", 100_000, "held-out seeds; report only"),
}


def episode_draws(seed: int, indices: Iterable[int], count: int) -> np.ndarray:
    """``count`` uniform numbers in [0, 1) for each episode index, as rows.

    Raw PCG64 output, which numpy keeps stable across versions. A draw keeps its value when ``count`` grows, so a
    task can sample one more parameter without changing the others.
    """
    rows = [np.random.PCG64(np.random.SeedSequence([seed, index])).random_raw(count) for index in indices]
    return (np.array(rows, dtype=np.uint64).reshape(-1, count) >> np.uint64(11)) * 2.0**-53


def first_episodes(records: list[dict], count: int) -> list[dict] | None:
    """The records of episodes 0 to ``count - 1`` in order, or ``None`` while any of them has not ended.

    Taking the first ``count`` records to arrive instead would favour short episodes: among parallel environments
    a quick success is finished and counted while a slow failure is still running.
    """
    if len(records) < count:
        return None
    wanted = sorted((r for r in records if r["episode"] < count), key=lambda r: r["episode"])
    return wanted if len(wanted) == count else None

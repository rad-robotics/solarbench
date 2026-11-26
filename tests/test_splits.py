"""Episode identity (solarbench.eval.splits): what an episode samples, and which episodes a run reports."""

import numpy as np
import pytest

from solarbench.eval.splits import SPLITS, episode_draws, first_episodes


@pytest.mark.unit
def test_draws_depend_on_the_seed_and_the_index_alone():
    seed = SPLITS["test"].base_seed
    together = episode_draws(seed, range(5), 12)
    assert together.shape == (5, 12) and together.dtype == np.float64
    assert ((together >= 0) & (together < 1)).all()
    for index in (4, 0, 2):  # whatever is asked for with it, and in whatever order
        assert (episode_draws(seed, [index], 12)[0] == together[index]).all()
    assert (episode_draws(seed, [3], 4)[0] == together[3, :4]).all()  # one more parameter leaves the others alone
    assert len({tuple(row) for row in together}) == 5
    assert (episode_draws(SPLITS["dev"].base_seed, [0], 12) != together[0]).all()


@pytest.mark.unit
def test_draws_are_the_same_on_every_machine():
    expected = [[0.12593474592063136, 0.4685357423491585], [0.5025384432055565, 0.10187342740616367]]
    assert episode_draws(100_000, [0, 1], 2).tolist() == expected


@pytest.mark.unit
def test_a_run_reports_every_episode_up_to_the_count_not_the_first_to_end():
    def ended(*indices):
        return [{"episode": i} for i in indices]

    assert first_episodes(ended(0, 2), 3) is None
    assert first_episodes(ended(0, 2, 3), 3) is None  # three have ended, but episode 1 is still running
    assert first_episodes(ended(0, 2, 3, 5, 1), 3) == ended(0, 1, 2)
    assert first_episodes([], 0) == []

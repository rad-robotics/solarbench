import pytest

from solarbench.eval.margin import LOOSER, TIGHTER, isotonic, margin


@pytest.mark.unit
def test_isotonic_pools_a_violation_by_weight():
    assert isotonic([0.2, 0.8], [10, 10]) == [0.2, 0.8]
    assert isotonic([0.6, 0.4, 0.9], [10, 10, 10]) == pytest.approx([0.5, 0.5, 0.9])
    assert isotonic([0.9, 0.3], [10, 30]) == pytest.approx([0.45, 0.45])


@pytest.mark.unit
def test_known_threshold_at_a_tested_level():
    # Expected counts from a curve that passes one half at dial 1.5.
    out = margin({1.0: (200, 2000), 1.5: (1000, 2000), 3.0: (1900, 2000)})
    assert out["level"] == pytest.approx(1.5) and out["beyond"] is None
    assert out["ci95"][0] <= 1.5 <= out["ci95"][1] and out["ci95"][1] - out["ci95"][0] < 0.2


@pytest.mark.unit
def test_known_threshold_between_levels_is_interpolated_in_log_dial():
    # 20 % at dial 1, 80 % at dial 2: one half is midway in log dial, at the square root of 2.
    out = margin({1.0: (20, 100), 2.0: (80, 100)})
    assert out["level"] == pytest.approx(2**0.5)
    assert 1.0 < out["ci95"][0] < out["level"] < out["ci95"][1] < 2.0


@pytest.mark.unit
def test_no_crossing_is_named_not_extrapolated():
    works = margin({1.0: (28, 30), 1.5: (30, 30), 3.0: (30, 30)})
    assert works["level"] is None and works["beyond"] == TIGHTER and works["ci95"] == [TIGHTER, TIGHTER]
    fails = margin({1.0: (0, 30), 1.5: (1, 30), 3.0: (3, 30)})
    assert fails["level"] is None and fails["beyond"] == LOOSER and fails["ci95"] == [LOOSER, LOOSER]
    assert works["tested"] == [1.0, 3.0]


@pytest.mark.unit
def test_interval_end_outside_the_tested_levels_is_named():
    # 14 of 30 at the tightest level: the crossing is just above it, and many resamples put it below.
    out = margin({1.0: (14, 30), 1.5: (20, 30), 3.0: (29, 30)})
    assert 1.0 < out["level"] < 1.5
    assert out["ci95"][0] == TIGHTER and 1.0 < out["ci95"][1] < 3.0


@pytest.mark.unit
def test_non_monotone_rates_are_pooled_before_the_crossing():
    # 60 % then 40 % pool to one half at both levels; the tightest level that reaches one half is reported.
    assert margin({1.0: (6, 10), 1.5: (4, 10), 3.0: (9, 10)})["level"] == pytest.approx(1.0)


@pytest.mark.unit
def test_same_seed_same_interval_and_bad_input_is_refused():
    levels = {1.0: (10, 30), 1.5: (18, 30), 3.0: (27, 30)}
    assert margin(levels) == margin(levels)
    for bad in ({}, {0.0: (1, 2)}, {1.0: (3, 2)}, {1.0: (0, 0)}):
        with pytest.raises(ValueError):
            margin(bad)

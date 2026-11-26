"""The prompts (solarbench.agents.prompts): what a model is told about its body and its job."""

import json
import string
from pathlib import Path

import pytest

from solarbench.agents import prompts

RESULTS = Path(__file__).resolve().parents[1] / "results"
JOBS = sorted(path.stem for path in prompts.HERE.glob("T*.md"))
OUTCOMES = {"success", "safe_success", "damage", "sim_error"}  # what an episode record says besides its conditions


def scored(job: str) -> list[str]:
    """The conditions a task records for every episode: its stages in order, then its damage flags."""
    episode = json.loads(max(RESULTS.glob(f"SolarBench-{job}-*/*.json")).read_text())["episodes"][0]
    flags = [key for key, value in episode.items() if isinstance(value, bool) and key not in OUTCOMES]
    stages = [key.removeprefix("stage_") for key in flags if key.startswith("stage_")]
    return stages + sorted(key for key in flags if not key.startswith("stage_"))


@pytest.mark.unit
def test_force_on_and_off_differ_only_in_the_lines_about_force():
    task = "SolarBench-T3-ClampTighten-UR16e-v0"
    on, off = prompts.body(task, True).splitlines(), prompts.body(task, False).splitlines()
    raw = (prompts.HERE / "UR16e.md").read_text()
    only_on, only_off = [line for line in on if line not in off], [line for line in off if line not in on]
    assert len(only_on) == raw.count("[force on] ") > 0 and len(only_off) == raw.count("[force off] ") > 0
    assert len(on) - len(only_on) == len(off) - len(only_off) == len(raw.splitlines()) - len(only_on) - len(only_off)
    for text in (*on, *off):
        assert "[" not in text and "{" not in text


@pytest.mark.unit
@pytest.mark.parametrize("job", JOBS)
def test_a_work_order_states_every_scored_condition_of_its_task(job):
    task = f"SolarBench-{job}-UR16e-v0"
    assert prompts.conditions(task) == scored(job)
    template = (prompts.HERE / f"{job}.md").read_text()
    fields = {name for _, name, _, _ in string.Formatter().parse(template) if name}
    text = prompts.work_order(task, **dict.fromkeys(fields, 1.0))
    assert "[" not in text and "{" not in text
    with pytest.raises(KeyError):
        prompts.work_order(task)

"""The fixed text a model is given about its body and its job. The text is part of the experiment.

One file per robot body (what it is: frames, units, limits, tool geometry, senses) and one per job (the work
order), named after the fields of a task id: ``SolarBench-T3-ClampTighten-UR16e-v0`` reads ``UR16e.md`` and
``T3-ClampTighten.md``. The files hold no physical numbers: ``{fields}`` are filled here from ``solarbench.specs``
for a body, and by the task, from its own configuration, for a work order.

A line may start with a tag in square brackets, which is removed from the text:
    [force on], [force off]    a line of a body file that is kept only with, or only without, force sensing
    [<stage>], [<damage>]      the line of a work order that states that scored condition
"""

from __future__ import annotations

import re
from pathlib import Path

from solarbench.specs import BOLT
from solarbench.specs.robots import SOCKET_ACROSS_FLATS, SOCKET_TOOL_LENGTH, UR16E_EFFORT, UR16E_VELOCITY

HERE = Path(__file__).parent
TAG = re.compile(r"^((?:- )?)\[([a-z_ ]+)\] ", re.MULTILINE)

BODY_FIELDS = {
    "head_af_mm": 1e3 * float(BOLT.across_flats),
    "socket_af_mm": 1e3 * float(SOCKET_ACROSS_FLATS),
    "tool_length_m": float(SOCKET_TOOL_LENGTH),
    "ur16e_effort": ", ".join(f"{name.removesuffix('_joint').replace('_', ' ')} {float(limit):g}"
                              for name, limit in UR16E_EFFORT.items()),
    "ur16e_speed_shoulder": float(UR16E_VELOCITY["shoulder_(pan|lift)_joint"]),
    "ur16e_speed_elbow": float(UR16E_VELOCITY["elbow_joint"]),
    "ur16e_speed_wrist": float(UR16E_VELOCITY["wrist_[123]_joint"]),
}


def _read(task: str, first: int, last: int) -> str:
    return (HERE / ("-".join(task.split("-")[first:last]) + ".md")).read_text()


def body(task: str, wrench: bool) -> str:
    """The description of the task's robot, as given with force sensing (``wrench``) or without."""
    drop = "force off" if wrench else "force on"
    kept = [line for line in _read(task, 3, 4).splitlines() if not line.removeprefix("- ").startswith(f"[{drop}] ")]
    return TAG.sub(r"\1", "\n".join(kept)).format(**BODY_FIELDS) + "\n"


def work_order(task: str, **values: float) -> str:
    """The task's work order. ``values`` are the task's own numbers: its thresholds, time limit and site."""
    return TAG.sub(r"\1", _read(task, 1, 3)).format(**values)


def conditions(task: str) -> list[str]:
    """The scored conditions the task's work order states, in the order it states them."""
    return [tag for _, tag in TAG.findall(_read(task, 1, 3))]

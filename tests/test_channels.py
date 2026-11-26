"""Sensor channels and catalogues (solarbench.tasks.channels), without a simulator."""

import pytest
import torch

from solarbench import wire
from solarbench.tasks import channels

G = 9.81
MASS, COM = 1.2, torch.tensor([0.0, 0.0, 0.08])


def reading(external_force, at, gravity):
    """What a flange sensor measures when ``external_force`` acts on the tool at ``at`` (tool frame, from the
    flange) and the tool is at rest: the arm holds the tool against that force and against its weight."""
    weight = MASS * gravity
    force = -(external_force + weight)
    torque = -(torch.cross(at, external_force, dim=-1) + torch.cross(COM, weight, dim=-1))
    return torch.cat([force, torque])[None]


@pytest.mark.unit
def test_a_tool_touching_nothing_reads_zero_in_any_orientation():
    for gravity in ([0.0, 0.0, G], [G, 0.0, 0.0], [5.0, -6.0, 5.9]):  # tool pointing down, sideways, askew
        gravity = torch.tensor(gravity)
        sensed = channels.external_wrench(reading(torch.zeros(3), torch.zeros(3), gravity), gravity[None], MASS, COM)
        assert sensed.abs().max() < 1e-5


@pytest.mark.unit
def test_pressing_on_a_surface_reads_as_a_negative_force_along_the_tool_axis():
    gravity = torch.tensor([0.0, 0.0, G])  # tool pointing straight down: tool z is down
    push, face = torch.tensor([0.0, 0.0, -20.0]), torch.tensor([0.0, 0.0, 0.16])  # the surface pushes back, on axis
    sensed = channels.external_wrench(reading(push, face, gravity), gravity[None], MASS, COM)[0]
    assert sensed.tolist() == pytest.approx([0, 0, -20, 0, 0, 0], abs=1e-5)
    side = torch.tensor([3.0, 0.0, 0.0])  # a sideways force at the socket face also twists the flange about y
    sensed = channels.external_wrench(reading(side, face, gravity), gravity[None], MASS, COM)[0]
    assert sensed.tolist() == pytest.approx([3, 0, 0, 0, 0.16 * 3, 0], abs=1e-5)


@pytest.mark.unit
def test_a_catalogue_lists_the_clock_first_and_makes_a_layout():
    pos = torch.tensor([[-6.28, 6.28]] * 6)
    offered = channels.catalogue("T", 30, [wire.TOOL_DELTA], ["tick"], [
        channels.policy_channel(35), channels.wrench_channel(100.0, 10.0),
        channels.proprio_channel([f"j{i}" for i in range(6)], pos, torch.full((6,), 3.14))])
    assert [c["name"] for c in offered["channels"]] == ["clock", "proprio", "wrench", "policy"]
    layout = wire.Layout(offered, {"channels": [{"id": channels.PROPRIO}, {"id": channels.WRENCH}]})
    assert [(name, shape) for name, _, shape in layout.blocks] == [("clock", ()), ("proprio", (19,)), ("wrench", (6,))]
    assert not layout.privileged and wire.Layout(offered, {"channels": [{"id": channels.POLICY}]}).privileged
    fields = {f["name"]: f for f in offered["channels"][1]["fields"]}
    assert fields["joint_vel"]["min"] == pytest.approx([-3.14] * 6) and fields["tool_quat"]["start"] == 15


@pytest.mark.unit
def test_the_clock_marks_the_first_tick_of_an_episode():
    ticks = channels.clock(torch.tensor([0, 7]))
    assert ticks.dtype == torch.int32 and ticks.tolist() == [[0, wire.AWAKE | wire.FIRST], [7, wire.AWAKE]]
    assert ticks.numpy().view(wire.CLOCK)["tick"].ravel().tolist() == [0, 7]

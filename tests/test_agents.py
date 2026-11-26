"""The policy contract (solarbench.agents), exercised without a simulator."""

import pytest
import torch

from solarbench.agents import JitPolicy, Policy, available, make_policy, register, select
from solarbench.wire import Layout

CATALOGUE = {
    "wire": [1, 0], "task": "any-task", "tick_hz": 30, "opcodes": [1], "max_depth": 1, "wake": ["tick"],
    "channels": [
        {"id": 1, "name": "clock", "dtype": "clock", "shape": []},
        {"id": 2, "name": "proprio", "dtype": "f4", "shape": [19]},
        {"id": 5, "name": "policy", "dtype": "f4", "shape": [35], "privileged": True},
    ],
}
ENV = object()


class Probe:
    """Selects the channels it is told to, claims whatever it is told to, and keeps the environment if given it."""

    name = "probe"

    def __init__(self, channels: str, catalogue: dict):
        self.selection = select(catalogue, *channels.split())
        self.privileged = "policy" not in channels  # a false claim either way; nothing may read it

    def attach(self, env):
        self.env = env

    def reset(self, env_ids):
        pass

    def act(self, obs):
        return self.env


register("test-probe")(Probe)


def test_builtins_are_registered():
    assert {"oracle", "zero", "jit"} <= set(available())


def test_zero_policy_meets_the_contract():
    policy, layout = make_policy("zero", CATALOGUE, ENV)
    assert isinstance(policy, Policy) and not layout.privileged
    assert [name for name, _, _ in layout.blocks] == ["clock"]
    assert policy.act({"clock": torch.zeros(3, 2, dtype=torch.int32)}) is None
    policy.reset(torch.tensor([0, 2]))


def test_privileged_is_read_from_the_selection_not_from_the_policy():
    for channels, privileged in (("proprio", False), ("", False), ("policy", True), ("proprio policy", True)):
        policy, layout = make_policy(f"test-probe:{channels}", CATALOGUE, ENV)
        assert layout.privileged is privileged and policy.privileged is not privileged
    assert Layout(CATALOGUE, JitPolicy("runs/2026-01-01/exported/policy.pt", CATALOGUE).selection).privileged


def test_only_a_privileged_selection_is_given_the_environment():
    policy, _ = make_policy("test-probe:policy", CATALOGUE, ENV)
    assert policy.act({}) is ENV
    policy, _ = make_policy("test-probe:proprio", CATALOGUE, ENV)
    with pytest.raises(AttributeError):
        policy.act({})


def test_a_channel_the_task_does_not_offer_cannot_be_selected():
    with pytest.raises(KeyError, match="does not offer .*wrench"):
        make_policy("test-probe:wrench", CATALOGUE, ENV)


def test_unknown_policy_names_the_alternatives():
    with pytest.raises(KeyError, match="available: .*zero"):
        make_policy("no-such-policy", CATALOGUE, ENV)


def test_a_name_cannot_be_registered_twice():
    with pytest.raises(KeyError, match="already registered"):
        register("zero")(lambda arg, catalogue: None)

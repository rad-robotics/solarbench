"""Policies ("brains") and the one contract all of them implement.

A policy says which channels it reads, as a selection from the task's catalogue (docs/interface.md, section 2),
and maps a frame of those channels to commands. Everything that drives a robot in SolarBench goes through this
interface: the scripted oracle, a floor that sends nothing, an exported network, and (via adapters added here)
vision-language-action models and language models behind an HTTP endpoint.

Contract
--------
A factory ``f(arg, catalogue) -> Policy`` is given what the task offers and nothing else. The policy's
``selection`` names the channels it wants. ``act(obs)`` then receives exactly those, as a dict from channel name
to a tensor with one row per environment (``clock`` is always among them), and returns the R1 argument tensor of
shape ``(environments, arguments)`` on the same device, or ``None`` to send no command, in which case the robot
holds. ``reset(env_ids)`` is called with the indices of the environments that just finished an episode.

Whether a result is privileged is read from the selection; a policy cannot declare it. A policy that selects a
privileged channel is recorded as privileged, and it alone is handed the environment, through ``attach(env)``.
Privileged results are reported as a hardware ceiling, never ranked against sensor-only policies.

Adding a policy: create ``solarbench/agents/<name>.py`` containing a factory ``f(arg, catalogue) -> Policy``
decorated with ``@register("<name>")``. The module is imported on first use, so no shared file needs editing.
It is then selectable as ``--policy <name>`` or ``--policy <name>:<arg>``.
"""

from __future__ import annotations

import contextlib
import importlib
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, runtime_checkable

import torch

from solarbench.wire import Layout


@runtime_checkable
class Policy(Protocol):
    name: str  # label written to result files
    selection: dict  # the channels it reads (docs/interface.md, section 2)

    def reset(self, env_ids: torch.Tensor) -> None: ...

    def act(self, obs: dict[str, torch.Tensor]) -> torch.Tensor | None: ...


Factory = Callable[[str, dict], Policy]
_REGISTRY: dict[str, Factory] = {}


def register(name: str) -> Callable[[Factory], Factory]:
    def deco(factory: Factory) -> Factory:
        if name in _REGISTRY:
            raise KeyError(f"policy {name!r} is already registered")
        _REGISTRY[name] = factory
        return factory

    return deco


def available() -> list[str]:
    return sorted(_REGISTRY)


def select(catalogue: dict, *names: str) -> dict:
    """A selection of the named channels of ``catalogue``."""
    ids = {channel["name"]: channel["id"] for channel in catalogue["channels"]}
    if missing := [name for name in names if name not in ids]:
        raise KeyError(f"{catalogue['task']} does not offer {missing}; it offers {sorted(ids)}")
    return {"channels": [{"id": ids[name]} for name in names]}


def make_policy(spec: str, catalogue: dict, env) -> tuple[Policy, Layout]:
    """Build a policy from ``name`` or ``name:arg``, and the layout of the frames it selected.

    ``env`` is the unwrapped environment. The policy is given it only if it selected a privileged channel.
    """
    name, _, arg = spec.partition(":")
    if name not in _REGISTRY and name.isidentifier():
        module = f"{__name__}.{name}"
        try:
            importlib.import_module(module)
        except ModuleNotFoundError as err:
            if err.name != module:  # the module exists but one of its own imports is missing
                raise
    if name not in _REGISTRY:
        raise KeyError(f"unknown policy {name!r}; available: {', '.join(available())}")
    policy = _REGISTRY[name](arg, catalogue)
    layout = Layout(catalogue, policy.selection)
    if layout.privileged:
        policy.attach(env)
    return policy, layout


class ZeroPolicy:
    """Sends no command, so the robot holds: the floor. A task on which this succeeds has a broken success check."""

    name = "zero"

    def __init__(self, catalogue: dict):
        self.selection = select(catalogue)

    def reset(self, env_ids):
        pass

    def act(self, obs):
        return None


class OraclePolicy:
    """Scripted controller that reads exact simulator state: the ceiling for a robot, not a contestant."""

    name = "oracle"

    def __init__(self, catalogue: dict):
        self.selection, self._task = select(catalogue, "policy"), catalogue["task"]

    def attach(self, env):
        from solarbench.oracle import make_oracle

        self._oracle = make_oracle(self._task, env)

    def reset(self, env_ids):
        self._oracle.reset(env_ids)

    def act(self, obs):
        return self._oracle.act()


class JitPolicy:
    """TorchScript network mapping the privileged ``policy`` channel to actions (e.g. an RSL-RL export)."""

    def __init__(self, path: str, catalogue: dict):
        self.selection, self._path = select(catalogue, "policy"), path
        self.name = "jit-" + Path(path).parent.parent.name

    def attach(self, env):
        self._net = torch.jit.load(self._path, map_location=env.device).eval()

    def reset(self, env_ids):
        if hasattr(self._net, "reset"):  # recurrent exports reset per env; stateless exports take no arguments
            with contextlib.suppress(RuntimeError):
                self._net.reset(env_ids)

    def act(self, obs):
        return self._net(obs["policy"])


register("zero")(lambda arg, catalogue: ZeroPolicy(catalogue))
register("oracle")(lambda arg, catalogue: OraclePolicy(catalogue))
register("jit")(lambda arg, catalogue: JitPolicy(arg, catalogue))

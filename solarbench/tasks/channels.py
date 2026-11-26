"""The sensor channels a task offers and the catalogue that lists them (docs/interface.md, sections 2 and 3).

A task builds its catalogue once from the entries here and fills the channels every control tick. Nothing in this
file reads the simulator: the functions take the arrays a task already holds, one row per environment.
"""

from __future__ import annotations

from collections.abc import Sequence

import torch

from solarbench import wire

PROPRIO, WRENCH, POLICY = 2, 3, 5  # channel ids; numbers are never reused


def catalogue(task: str, tick_hz: int, opcodes: Sequence[int], wake: Sequence[str], channels: Sequence[dict]) -> dict:
    """What a task offers. The clock is always offered, and always first."""
    clock = {"id": wire.CLOCK_ID, "name": "clock", "dtype": "clock", "shape": []}
    return {"wire": list(wire.VERSION), "task": task, "tick_hz": tick_hz, "opcodes": list(opcodes), "max_depth": 1,
            "wake": list(wake), "channels": [clock, *sorted(channels, key=lambda channel: channel["id"])]}


def clock(tick: torch.Tensor) -> torch.Tensor:
    """Ticks since the episode began and the flags, as the two 32-bit integers of a clock record. Every tick wakes
    an R1 policy."""
    tick = tick.int()
    return torch.stack([tick, wire.AWAKE + wire.FIRST * (tick == 0).int()], dim=-1)


def policy_channel(size: int) -> dict:
    return {"id": POLICY, "name": "policy", "dtype": "f4", "shape": [size], "privileged": True}


def proprio_channel(joints: Sequence[str], pos_limits: torch.Tensor, vel_limits: torch.Tensor) -> dict:
    """Joint positions, joint velocities, then the tool pose in the base frame. ``pos_limits`` is ``(joints, 2)``
    and ``vel_limits`` ``(joints,)``, both from the robot description."""
    n, vel = len(joints), vel_limits.tolist()
    return {"id": PROPRIO, "name": "proprio", "dtype": "f4", "shape": [2 * n + 7], "joints": list(joints), "fields": [
        {"name": "joint_pos", "start": 0, "count": n, "unit": "rad",
         "min": pos_limits[:, 0].tolist(), "max": pos_limits[:, 1].tolist()},
        {"name": "joint_vel", "start": n, "count": n, "unit": "rad/s", "min": [-v for v in vel], "max": vel},
        {"name": "tool_pos", "start": 2 * n, "count": 3, "unit": "m", "frame": "base"},
        {"name": "tool_quat", "start": 2 * n + 3, "count": 4, "unit": "xyzw", "frame": "base"}]}


def proprio(joint_pos: torch.Tensor, joint_vel: torch.Tensor, tool_pos: torch.Tensor, tool_quat: torch.Tensor):
    return torch.cat([joint_pos, joint_vel, tool_pos, tool_quat], dim=-1)


def wrench_channel(force_range: float, torque_range: float) -> dict:
    """Force then torque at the tool flange, in the tool frame, each clipped to the sensor's range."""
    return {"id": WRENCH, "name": "wrench", "dtype": "f4", "shape": [6], "frame": "tool", "fields": [
        {"name": "force", "start": 0, "count": 3, "unit": "N", "min": [-force_range] * 3, "max": [force_range] * 3},
        {"name": "torque", "start": 3, "count": 3, "unit": "N*m",
         "min": [-torque_range] * 3, "max": [torque_range] * 3}]}


def external_wrench(reaction: torch.Tensor, gravity: torch.Tensor, mass: float, com: torch.Tensor) -> torch.Tensor:
    """What the surroundings apply to the tool, from what a sensor at the flange measures.

    ``reaction`` ``(N, 6)`` is the force and the torque about the flange with which the arm holds the tool;
    ``gravity`` ``(N, 3)`` the gravitational acceleration; ``com`` ``(3,)`` the tool's centre of mass from the
    flange; all in the tool frame. At rest the arm, the tool's weight and the surroundings balance, so taking the
    weight out of the reading, as a robot does with its configured payload, leaves the surroundings. While the tool
    accelerates, its inertia is in the result too, as it is in a real reading.
    """
    weight = mass * gravity
    force = -reaction[:, :3] - weight
    torque = -reaction[:, 3:] - torch.cross(com.expand_as(weight), weight, dim=-1)
    return torch.cat([force, torque], dim=-1)

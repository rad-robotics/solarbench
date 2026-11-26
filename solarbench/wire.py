"""Wire format of the interface contract (docs/interface.md).

Observations, commands and completions are fixed binary layouts, agreed once per run: the environment offers a
catalogue, the policy answers with a selection, and from then on nothing is named or parsed. In process the arrays
are handed over as they are; ``pack_*`` and ``unpack_*`` give the same arrays as bytes for a socket, a file or
another process, and unpacking returns views into the buffer it was given.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct

import numpy as np

MAGIC = b"SBW1"
VERSION = (1, 0)  # a reader refuses another major version and accepts any minor one; minor changes only add

HEADER = struct.Struct("<4sBBHIIQQ")  # magic, major, minor, message, environments, payload bytes, layout, sequence
HELLO, SELECT, EPISODE, FRAME, COMMANDS = 1, 2, 3, 4, 5  # message kinds; the first three carry UTF-8 JSON

# Time is counted in control ticks since the episode began; the catalogue gives the tick rate.
CLOCK = np.dtype([("tick", "<u4"), ("flags", "<u4")])
COMMAND = np.dtype(
    [("opcode", "<u2"), ("flags", "<u2"), ("id", "<u4"), ("based_on", "<u4"), ("timeout", "<u4"), ("args", "<f4", 12)]
)
COMPLETION = np.dtype(
    [("id", "<u4"), ("opcode", "<u2"), ("status", "<u2"), ("started", "<u4"), ("ended", "<u4"), ("result", "<f4", 4)]
)
DTYPES = {"f4": np.dtype("<f4"), "u1": np.dtype("u1"), "clock": CLOCK, "completion": COMPLETION}

FIRST, LAST, AWAKE = 1, 2, 4  # clock flags: first frame of an episode, episode over, commands are expected now
NOP, TOOL_DELTA, TOOL_POSE, DONE = 0, 1, 2, 127  # opcodes; numbers are never reused
REPLACE = 1  # command flag: drop what is queued or running before this record
# Completion status. The last three refuse a whole buffer: a robot does not skip a command it cannot read.
OK, STALLED, TIMED_OUT, PREEMPTED, UNKNOWN, INVALID, FULL = 1, 2, 3, 4, 5, 6, 7

CLOCK_ID = 1


class Layout:
    """Where each selected channel sits in a frame. Fixed for the run and identified by ``hash``."""

    def __init__(self, catalogue: dict, selection: dict):
        if catalogue["wire"][0] != VERSION[0]:
            raise ValueError(f"catalogue is wire {catalogue['wire'][0]}.x; this reader speaks {VERSION[0]}.x")
        offered = {c["id"]: c for c in catalogue["channels"]}
        chosen = {c["id"]: c for c in selection["channels"] if c["id"] != CLOCK_ID}
        if unknown := sorted(set(chosen) - set(offered)):
            raise ValueError(f"channels {unknown} are not in the catalogue")
        self.depth, self.wake = selection.get("depth", 1), selection.get("wake", catalogue["wake"][0])
        if not 1 <= self.depth <= catalogue["max_depth"] or self.wake not in catalogue["wake"]:
            raise ValueError(f"depth {self.depth} or wake {self.wake!r} is not offered by the catalogue")
        self.blocks: list[tuple[str, np.dtype, tuple[int, ...]]] = []
        self.privileged = False
        ids = []
        for cid in (CLOCK_ID, *sorted(chosen)):  # channel order in a frame is by id, whatever the selection's order
            channel = offered[cid]
            shape: tuple[int, ...] = tuple(channel["shape"])
            scale = chosen.get(cid, {}).get("scale", 1)
            if scale != 1:
                if scale not in channel.get("scales", ()):
                    raise ValueError(f"channel {cid} is not offered at scale 1/{scale}")
                shape = (shape[0] // scale, shape[1] // scale, *shape[2:])
            self.blocks.append((channel["name"], DTYPES[channel["dtype"]], shape))
            self.privileged |= bool(channel.get("privileged", False))
            ids.append([cid, channel["dtype"], list(shape)])
        described = json.dumps([VERSION[0], ids, self.depth, self.wake], separators=(",", ":"))
        self.hash = int.from_bytes(hashlib.sha256(described.encode()).digest()[:8], "little")

    def offsets(self, n_envs: int) -> tuple[list[int], int]:
        """Byte offset of each block's array, each starting on an 8-byte boundary, and the size of the payload."""
        offsets, end = [], 0
        for _, dtype, shape in self.blocks:
            offsets.append(end)
            end += -(-n_envs * dtype.itemsize * math.prod(shape) // 8) * 8
        return offsets, end


def pack_message(message: int, payload: bytes = b"", n_envs: int = 0, layout: int = 0, sequence: int = 0) -> bytes:
    return HEADER.pack(MAGIC, *VERSION, message, n_envs, len(payload), layout, sequence) + payload


def unpack_message(buf) -> tuple[int, int, int, int, memoryview]:
    """Message kind, environments, layout hash, sequence number and payload of one message."""
    magic, major, _, message, n_envs, size, layout, sequence = HEADER.unpack_from(buf)
    if magic != MAGIC or major != VERSION[0]:
        raise ValueError(f"not a wire {VERSION[0]}.x message")
    payload = memoryview(buf)[HEADER.size : HEADER.size + size]
    if len(payload) != size:
        raise ValueError(f"message is cut short: {len(payload)} of {size} payload bytes")
    return message, n_envs, layout, sequence, payload


def _expect(buf, message: int, layout: Layout) -> tuple[int, int, memoryview]:
    kind, n_envs, layout_hash, sequence, payload = unpack_message(buf)
    if kind != message or layout_hash != layout.hash:
        raise ValueError("message is of another kind, or was made for another layout")
    return n_envs, sequence, payload


def pack_frame(layout: Layout, arrays: dict[str, np.ndarray], sequence: int = 0) -> bytearray:
    """One observation frame for ``n`` environments: each channel one contiguous ``(n, ...)`` array."""
    n_envs = len(arrays["clock"])
    offsets, size = layout.offsets(n_envs)
    buf = bytearray(HEADER.size + size)
    HEADER.pack_into(buf, 0, MAGIC, *VERSION, FRAME, n_envs, size, layout.hash, sequence)
    for (name, dtype, shape), offset in zip(layout.blocks, offsets, strict=True):
        block = np.frombuffer(buf, dtype, n_envs * math.prod(shape), HEADER.size + offset)
        block.reshape(n_envs, *shape)[...] = arrays[name]
    return buf


def unpack_frame(layout: Layout, buf) -> tuple[dict[str, np.ndarray], int]:
    """The channels of one frame as views into ``buf``, and the frame's sequence number."""
    n_envs, sequence, payload = _expect(buf, FRAME, layout)
    frame = {
        name: np.frombuffer(payload, dtype, n_envs * math.prod(shape), offset).reshape(n_envs, *shape)
        for (name, dtype, shape), offset in zip(layout.blocks, layout.offsets(n_envs)[0], strict=True)
    }
    return frame, sequence


def pack_commands(layout: Layout, commands: np.ndarray, sequence: int = 0) -> bytes:
    """A command buffer: ``(environments, depth)`` records of 64 bytes, unused slots left as ``NOP``.

    Takes the records, or the same bytes as 32-bit words of shape ``(environments, depth, 16)``.
    """
    records = np.ascontiguousarray(commands).view(COMMAND).reshape(-1, layout.depth)
    return pack_message(COMMANDS, records.tobytes(), len(records), layout.hash, sequence)


def unpack_commands(layout: Layout, buf) -> tuple[np.ndarray, int]:
    n_envs, sequence, payload = _expect(buf, COMMANDS, layout)
    return np.frombuffer(payload, COMMAND).reshape(n_envs, layout.depth), sequence


def refusals(catalogue: dict, commands: np.ndarray) -> np.ndarray:
    """Per environment: 0 if its buffer may run, else the status every record in it completes with."""
    known = np.isin(commands["opcode"], [NOP, *catalogue["opcodes"]]).all(axis=1)
    finite = np.isfinite(commands["args"]).all(axis=(1, 2))
    return np.where(~known, UNKNOWN, np.where(~finite, INVALID, 0)).astype(np.uint16)

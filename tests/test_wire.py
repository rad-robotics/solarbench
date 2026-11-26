"""The wire format of the interface contract (solarbench.wire)."""

import numpy as np
import pytest

from solarbench import wire

CATALOGUE = {
    "wire": [1, 0], "task": "T", "tick_hz": 30, "max_depth": 4, "wake": ["idle", "tick"],
    "opcodes": [wire.TOOL_DELTA, wire.TOOL_POSE, wire.DONE],
    "channels": [
        {"id": 1, "name": "clock", "dtype": "clock", "shape": []},
        {"id": 2, "name": "proprio", "dtype": "f4", "shape": [19]},
        {"id": 3, "name": "wrench", "dtype": "f4", "shape": [6]},
        {"id": 4, "name": "completions", "dtype": "completion", "shape": [2]},
        {"id": 5, "name": "policy", "dtype": "f4", "shape": [35], "privileged": True},
        {"id": 16, "name": "images/wrist", "dtype": "u1", "shape": [480, 640, 3], "scales": [1, 2, 4]},
    ],
}


def select(*channels, **rest):
    return {"channels": [c if isinstance(c, dict) else {"id": c} for c in channels], **rest}


def make_frame(layout, n_envs=3, seed=0):
    rng = np.random.default_rng(seed)
    arrays = {}
    for name, dtype, shape in layout.blocks:
        raw = rng.integers(0, 255, (n_envs, *shape, dtype.itemsize), dtype=np.uint8)
        arrays[name] = raw.view(dtype).reshape(n_envs, *shape)
    arrays["proprio"] = rng.normal(size=(n_envs, 19)).astype("f4")
    return arrays


@pytest.mark.unit
def test_record_sizes_are_part_of_the_contract():
    assert (wire.HEADER.size, wire.CLOCK.itemsize, wire.COMMAND.itemsize, wire.COMPLETION.itemsize) == (32, 8, 64, 32)


@pytest.mark.unit
def test_frame_round_trip_returns_views_not_copies():
    layout = wire.Layout(CATALOGUE, select(2, 3, 4, {"id": 16, "scale": 4}))
    arrays = make_frame(layout)
    buf = wire.pack_frame(layout, arrays, sequence=7)
    frame, sequence = wire.unpack_frame(layout, buf)
    assert sequence == 7 and list(frame) == ["clock", "proprio", "wrench", "completions", "images/wrist"]
    assert frame["images/wrist"].shape == (3, 120, 160, 3)
    whole = np.frombuffer(buf, np.uint8)
    for name, array in arrays.items():
        assert frame[name].tobytes() == array.tobytes()
        assert np.shares_memory(frame[name], whole)
    assert all(offset % 8 == 0 for offset in layout.offsets(3)[0])


@pytest.mark.unit
def test_layout_hash_follows_what_was_selected_not_how_it_was_written():
    base = wire.Layout(CATALOGUE, select(2, 16))
    assert wire.Layout(CATALOGUE, select(16, 2, 1)).hash == base.hash
    others = (select(2, 3, 16), select(2, {"id": 16, "scale": 2}), select(2, 16, depth=2), select(2, 16, wake="tick"))
    for other in others:
        assert wire.Layout(CATALOGUE, other).hash != base.hash
    assert not base.privileged and wire.Layout(CATALOGUE, select(2, 5)).privileged


@pytest.mark.unit
def test_a_selection_outside_the_catalogue_is_refused():
    for bad in (select(9), select({"id": 2, "scale": 2}), select({"id": 16, "scale": 3}), select(2, depth=5),
                select(2, wake="never")):
        with pytest.raises(ValueError):
            wire.Layout(CATALOGUE, bad)


@pytest.mark.unit
def test_a_later_minor_version_is_read_and_another_major_is_not():
    later = {**CATALOGUE, "wire": [1, 3], "new_key": True,
             "channels": [*CATALOGUE["channels"], {"id": 40, "name": "tactile", "dtype": "i2", "shape": [64]}]}
    layout = wire.Layout(later, select(2, 3))
    assert layout.hash == wire.Layout(CATALOGUE, select(2, 3)).hash
    message = wire.HEADER.pack(wire.MAGIC, 1, 3, wire.HELLO, 0, 2, 0, 0) + b"{}"
    assert bytes(wire.unpack_message(message)[4]) == b"{}"
    with pytest.raises(ValueError):
        wire.Layout({**CATALOGUE, "wire": [2, 0]}, select(2))
    with pytest.raises(ValueError):
        wire.unpack_message(wire.HEADER.pack(wire.MAGIC, 2, 0, wire.HELLO, 0, 0, 0, 0))


@pytest.mark.unit
def test_command_buffer_round_trip_and_refusals():
    layout = wire.Layout(CATALOGUE, select(2, depth=2))
    commands = np.zeros((4, 2), wire.COMMAND)
    commands["opcode"][:, 0] = wire.TOOL_POSE
    commands["args"][:, 0, :7] = [0.4, 0.0, 0.3, 0.0, 0.0, 0.0, 1.0]
    commands["id"][:, 0] = np.arange(4)
    commands["opcode"][1, 1] = 0x30  # not offered by this catalogue
    commands["args"][2, 0, 0] = np.nan
    buf = wire.pack_commands(layout, commands, sequence=3)
    assert len(buf) == 32 + 4 * 2 * 64
    back, sequence = wire.unpack_commands(layout, buf)
    assert sequence == 3 and back.tobytes() == commands.tobytes()
    words = commands.view("<i4").reshape(4, 2, 16)  # the form a tensor library without record types can hold
    assert wire.pack_commands(layout, words, sequence=3) == buf
    assert wire.refusals(CATALOGUE, back).tolist() == [0, wire.UNKNOWN, wire.INVALID, 0]


@pytest.mark.unit
def test_a_message_for_another_layout_or_cut_short_is_refused():
    layout, other = wire.Layout(CATALOGUE, select(2)), wire.Layout(CATALOGUE, select(2, 3))
    buf = wire.pack_frame(layout, make_frame(layout))
    with pytest.raises(ValueError):
        wire.unpack_frame(other, buf)
    with pytest.raises(ValueError):
        wire.unpack_frame(layout, buf[:-8])
    with pytest.raises(ValueError):
        wire.unpack_commands(layout, buf)

"""The chat-completions adapter (solarbench.agents.endpoint), against a local stand-in for a model server."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pytest
import torch

from solarbench import wire
from solarbench.agents import make_policy, prompts
from solarbench.agents.endpoint import parse

TASK = "SolarBench-T3-ClampTighten-UR16e-R2-v0"
CATALOGUE = {
    "wire": [1, 0], "task": TASK, "tick_hz": 30, "opcodes": [wire.TOOL_POSE, wire.DONE], "max_depth": 1,
    "wake": ["idle"],
    "channels": [
        {"id": 1, "name": "clock", "dtype": "clock", "shape": []},
        {"id": 2, "name": "proprio", "dtype": "f4", "shape": [5], "fields": [
            {"name": "joint_pos", "start": 0, "count": 2, "unit": "rad"},
            {"name": "tool_pos", "start": 2, "count": 3, "unit": "m"}]},
        {"id": 3, "name": "wrench", "dtype": "f4", "shape": [6], "fields": [
            {"name": "force", "start": 0, "count": 3, "unit": "N"},
            {"name": "torque", "start": 3, "count": 3, "unit": "N*m"}]},
        {"id": 4, "name": "completions", "dtype": "completion", "shape": [2]},
        {"id": 5, "name": "policy", "dtype": "f4", "shape": [35], "privileged": True},
    ],
}
POSE = 'The bolt is below.\n{"position": [0.5, 0.0, 0.25], "quaternion": [0, 2, 0, 0]}'


@pytest.fixture
def server(monkeypatch):
    """A server that answers each request with the next scripted reply and keeps what it was sent."""
    seen, replies, together = [], [], []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append({"path": self.path, "key": self.headers.get("Authorization"), **body})
            if together:
                together[0].wait()  # answers only once that many requests are in flight at the same time
            answer = {"choices": [{"message": {"content": replies.pop(0) if replies else POSE}}],
                      "usage": {"prompt_tokens": 900, "completion_tokens": 40}}
            data = json.dumps(answer).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setenv("SOLARBENCH_ENDPOINT_URL", f"http://127.0.0.1:{httpd.server_port}/v1")
    monkeypatch.setenv("SOLARBENCH_ENDPOINT_KEY", "not-a-real-key")
    yield seen, replies, together
    httpd.shutdown()


def frame(layout, ticks, flags=wire.AWAKE, completions=()):
    n = len(ticks)
    obs = {"clock": torch.tensor([[tick, flags] for tick in ticks], dtype=torch.int32),
           "proprio": torch.arange(5 * n, dtype=torch.float32).reshape(n, 5) / 8,
           "wrench": torch.full((n, 6), -1.5)}
    ended = np.zeros((n, 2), wire.COMPLETION)
    for env, record in completions:
        ended[env, -1] = record
    obs["completions"] = torch.from_numpy(ended.view("<i4").reshape(n, 2, 8))
    return {name: obs[name] for name, _, _ in layout.blocks}


@pytest.mark.unit
def test_only_a_last_line_that_is_a_whole_command_is_a_command():
    opcode, args = parse(POSE)
    assert opcode == wire.TOOL_POSE and args == [0.5, 0.0, 0.25, 0.0, 1.0, 0.0, 0.0]  # the quaternion is normalised
    assert parse('{"done": true}') == (wire.DONE, [])
    for reply in ("", "I would move down.", "[1, 2, 3]", '{"position": [0, 0, 0]}',
                  '{"position": [0, 0, NaN], "quaternion": [0, 0, 0, 1]}',
                  '{"position": [0, 0, 0], "quaternion": [0, 0, 0, 0]}',
                  '{"position": [0, 0, true], "quaternion": [0, 0, 0, 1]}',
                  '{"position": [0, 0, 0], "quaternion": [0, 0, 0, 1]}\nDone.'):
        assert parse(reply) is None


@pytest.mark.unit
def test_a_round_sends_the_fixed_text_first_and_returns_one_record_per_environment(server):
    seen, _, together = server
    policy, layout = make_policy("endpoint:some/model-27b,wrench=on,temperature=0.2,seed=7", CATALOGUE, None)
    assert [name for name, _, _ in layout.blocks] == ["clock", "proprio", "wrench", "completions"]
    assert not layout.privileged and (layout.depth, layout.wake) == (1, "idle")
    assert policy.name == "endpoint-some-model-27b-force"
    policy.reset(torch.arange(3), ["work order A", "work order B", "work order C"])
    together.append(threading.Barrier(3, timeout=10))  # the three requests must be in flight together
    records = policy.act(frame(layout, [0, 0, 0])).numpy().view(wire.COMMAND)[..., 0]
    together.clear()
    assert records.shape == (3, 1) and (records["opcode"] == wire.TOOL_POSE).all() and (records["id"] == 1).all()
    assert records["args"][0, 0].tolist() == [0.5, 0.0, 0.25, 0.0, 1.0, 0.0, 0.0, 0, 0, 0, 0, 0]
    first = sorted(seen, key=lambda request: request["messages"][1]["content"])[0]
    assert first["path"] == "/v1/chat/completions" and first["key"] == "Bearer not-a-real-key"
    assert (first["model"], first["temperature"], first["seed"]) == ("some/model-27b", 0.2, 7)
    system, work_order, round_1 = first["messages"]
    assert system["content"].startswith(prompts.body(TASK, True)) and '{"done": true}' in system["content"]
    assert work_order == {"role": "user", "content": "work order A"}
    assert round_1["content"].splitlines() == [
        "tick 0", "joint_pos [rad]: 0.0000, 0.1250", "tool_pos [m]: 0.2500, 0.3750, 0.5000",
        "force [N]: -1.5000, -1.5000, -1.5000", "torque [N*m]: -1.5000, -1.5000, -1.5000"]

    seen.clear()
    ended = (1, wire.TOOL_POSE, wire.STALLED, 0, 44, [0.002, 0.01, 12.5, 3.25])
    records = policy.act(frame(layout, [45, 3, 3], completions=[(0, ended)])).numpy().view(wire.COMMAND)[..., 0]
    assert (records["id"] == 2).all() and records["based_on"].ravel().tolist() == [45, 3, 3]
    second = sorted(seen, key=lambda request: request["messages"][1]["content"])[0]["messages"]
    assert second[:3] == first["messages"] and second[3] == {"role": "assistant", "content": POSE}
    assert second[4]["content"].splitlines()[:3] == [
        "tick 45", "your last command stalled before arriving, 0.0020 m and 0.0100 rad from its target",
        "at its end: force 12.5000 N, torque about tool z 3.2500 N*m"]
    assert policy.calls[0] == [{"wall_s": pytest.approx(0, abs=10), "tokens_read": 900, "tokens_written": 40,
                                "parsed": True}] * 2
    assert "not-a-real-key" not in json.dumps([policy.settings, policy.calls])
    assert policy.settings["endpoint"] == "local" and "127.0.0.1" not in json.dumps(policy.settings)


@pytest.mark.unit
def test_without_force_the_model_is_given_no_force(server):
    seen, _, _ = server
    policy, layout = make_policy("endpoint:m", CATALOGUE, None)
    assert "wrench" not in [name for name, _, _ in layout.blocks] and policy.name == "endpoint-m-noforce"
    policy.reset([0], ["work order"])
    ended = (1, wire.TOOL_POSE, wire.OK, 0, 9, [0.0, 0.0, 0.0, 0.0])
    policy.act(frame(layout, [0]))
    policy.act(frame(layout, [10], completions=[(0, ended)]))
    text = json.dumps(seen[-1]["messages"])
    assert seen[-1]["messages"][0]["content"].startswith(prompts.body(TASK, False))
    assert "your last command arrived" in text and "force" not in text.replace("Nothing reports force", "")


@pytest.mark.unit
def test_an_unreadable_reply_sends_no_command_and_is_counted(server):
    seen, replies, _ = server
    policy, layout = make_policy("endpoint:m", CATALOGUE, None)
    policy.reset([0, 1], ["work order", "work order"])
    replies += ["I think the bolt is tight.", '{"done": true}']
    records = policy.act(frame(layout, [0, 0])).numpy().view(wire.COMMAND)[..., 0]
    assert sorted(records["opcode"].ravel().tolist()) == [wire.NOP, wire.DONE]
    lost = int(np.argmin(records["opcode"].ravel()))
    assert [call["parsed"] for call in policy.calls[lost]] == [False]
    seen.clear()
    asleep = frame(layout, [1, 1])
    asleep["clock"][1 - lost, 1] = 0  # the other environment has a command running: it is not asked again
    records = policy.act(asleep).numpy().view(wire.COMMAND)[..., 0]
    assert len(seen) == 1
    assert seen[0]["messages"][-1]["content"].startswith("Your last reply did not end with a command")
    assert records["opcode"].ravel().tolist()[1 - lost] == wire.NOP and records["id"].ravel().tolist()[lost] == 2
    policy.reset([lost], ["work order"])
    assert len(policy.finished) == 1 and len(policy.finished[0]) == 2 and policy.calls[lost] == []

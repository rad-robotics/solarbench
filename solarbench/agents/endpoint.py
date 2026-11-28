"""A model behind a chat-completions endpoint, driving the robot one tool pose per round (profile R2).

Where the model runs is a URL. A local server for open weights and a remote service look the same from here:
    SOLARBENCH_ENDPOINT_URL    the server's base address, ending in /v1
    SOLARBENCH_ENDPOINT_KEY    sent as a bearer token if set; never stored
The rest comes with the policy name:
    --policy endpoint:<model>[,wrench=on][,temperature=0][,max_tokens=4096][,seed=0]

What the model reads: the description of its body and how to reply (the system message), the work order, then one
message per round with the selected channels as text. What it writes: reasoning if it wishes, then one line of
JSON, which becomes one ``TOOL_POSE`` or ``DONE`` record (docs/interface.md, section 4). A reply that cannot be read
sends no command, and the model is told so in the next round.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import numpy as np
import torch

from solarbench import wire
from solarbench.agents import prompts, register, select

REPLY = """
## Commands
Each round you send one command: a pose for the tool frame, in the base frame. The arm moves the tool there within \
its limits and stops when it arrives, when it can go no further, or when the command's time runs out. You are then \
told how the command ended and what the robot senses, and asked for the next command.

Reason as you wish, then end your reply with one line of JSON and nothing after it:
{"position": [x, y, z], "quaternion": [x, y, z, w]}
or, when the job is finished or cannot be finished:
{"done": true}
"""
ENDED = {wire.OK: "arrived", wire.STALLED: "stalled before arriving", wire.TIMED_OUT: "ran out of time",
         wire.PREEMPTED: "was dropped", wire.UNKNOWN: "was refused: unknown command",
         wire.INVALID: "was refused: invalid argument", wire.FULL: "was refused: queue full"}
ENCODING = "text, 4 decimals"


def parse(reply: str) -> tuple[int, list[float]] | None:
    """The opcode and arguments in the last line of a reply, or ``None`` if that line is not a command."""
    lines = reply.strip().splitlines()
    try:
        data = json.loads(lines[-1].strip().strip("`")) if lines else None
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    if data.get("done") is True:
        return wire.DONE, []
    position, quaternion = data.get("position"), data.get("quaternion")
    if not (isinstance(position, list) and isinstance(quaternion, list) and (len(position), len(quaternion)) == (3, 4)):
        return None
    numbers = [*position, *quaternion]
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in numbers):
        return None
    norm = math.sqrt(sum(x * x for x in quaternion))
    if norm < 1e-6:
        return None
    return wire.TOOL_POSE, [*map(float, position), *(x / norm for x in quaternion)]


def describe(catalogue: dict, layout: wire.Layout, frame: dict[str, np.ndarray], env: int, sent: int | None) -> str:
    """One environment's frame as text: the tick, how the last command ended, then each field of each channel."""
    lines = [f"tick {int(frame['clock'][env]['tick'])}"]
    for record in frame["completions"][env][::-1] if "completions" in frame else ():
        if sent is not None and record["id"] == sent and record["opcode"] == wire.TOOL_POSE:
            status, result = int(record["status"]), record["result"]
            ended = ENDED.get(status, f"ended with status {status}")
            lines.append(f"your last command {ended}, {result[0]:.4f} m and {result[1]:.4f} rad from its target")
            if "wrench" in frame:
                lines.append(f"at its end: force {result[2]:.4f} N, torque about tool z {result[3]:.4f} N*m")
            break
    by_name = {channel["name"]: channel for channel in catalogue["channels"]}
    for name, _, _ in layout.blocks:
        for field in by_name[name].get("fields", ()):
            values = frame[name][env][field["start"] : field["start"] + field["count"]]
            lines.append(f"{field['name']} [{field['unit']}]: " + ", ".join(f"{value:.4f}" for value in values))
    return "\n".join(lines)


class EndpointPolicy:
    def __init__(self, arg: str, catalogue: dict):
        model, *options = arg.split(",")
        options = dict(option.split("=", 1) for option in options)
        if not model or set(options) - {"wrench", "temperature", "max_tokens", "seed"}:
            raise ValueError(f"endpoint:<model>[,wrench=on][,temperature=][,max_tokens=][,seed=], got {arg!r}")
        self._url = os.environ["SOLARBENCH_ENDPOINT_URL"].rstrip("/") + "/chat/completions"
        wrench = options.get("wrench", "off") == "on"
        offered = {channel["name"] for channel in catalogue["channels"]}
        wanted = ["proprio", *(["wrench"] if wrench else []), *(["completions"] if "completions" in offered else [])]
        self.selection = {**select(catalogue, *wanted), "depth": 1, "wake": "idle"}
        self.name = "endpoint-" + re.sub(r"[^A-Za-z0-9.]+", "-", model) + ("-force" if wrench else "-noforce")
        local = urlparse(self._url).hostname in ("localhost", "127.0.0.1", "::1")
        # what a result has to say about the model (docs/interface.md, section 10): not the address, not the key
        self.settings = {"model": model, "endpoint": "local" if local else "remote", "encoding": ENCODING,
                         "temperature": float(options.get("temperature", 0.0)),
                         "max_tokens": int(options.get("max_tokens", 4096)), "seed": int(options.get("seed", 0))}
        self._catalogue, self._layout = catalogue, wire.Layout(catalogue, self.selection)
        self._system = prompts.body(catalogue["task"], wrench) + REPLY
        self._messages: dict[int, list[dict]] = {}
        self._sent: dict[int, int | None] = {}
        self._unread: set[int] = set()
        self.calls: dict[int, list[dict]] = {}  # per environment, one entry per call in the episode under way
        self.finished: list[list[dict]] = []  # the calls of each episode that has ended, in the order they ended
        self._pool: ThreadPoolExecutor | None = None

    def reset(self, env_ids, work_orders):
        for env, work_order in zip(torch.as_tensor(env_ids).tolist(), work_orders, strict=True):
            if self.calls.get(env):
                self.finished.append(self.calls[env])
            self._messages[env] = [{"role": "system", "content": self._system}, {"role": "user", "content": work_order}]
            self._sent[env], self.calls[env] = None, []
            self._unread.discard(env)

    def _ask(self, env: int, text: str) -> tuple[int, list[float]] | None:
        messages = self._messages[env]
        messages.append({"role": "user", "content": text})
        body = {"model": self.settings["model"], "messages": messages, "temperature": self.settings["temperature"],
                "max_tokens": self.settings["max_tokens"], "seed": self.settings["seed"]}
        headers = {"Content-Type": "application/json"}
        if key := os.environ.get("SOLARBENCH_ENDPOINT_KEY"):
            headers["Authorization"] = f"Bearer {key}"
        started = time.perf_counter()
        request = urllib.request.Request(self._url, json.dumps(body).encode(), headers)
        with urllib.request.urlopen(request, timeout=900) as response:
            answer = json.load(response)
        reply = answer["choices"][0]["message"].get("content") or ""
        messages.append({"role": "assistant", "content": reply})
        command, usage = parse(reply), answer.get("usage", {})
        self.calls[env].append({"wall_s": time.perf_counter() - started, "tokens_read": usage.get("prompt_tokens"),
                                "tokens_written": usage.get("completion_tokens"), "parsed": command is not None})
        return command

    def act(self, obs):
        frame = {name: array.cpu().numpy() for name, array in obs.items()}
        frame["clock"] = np.ascontiguousarray(frame["clock"]).view(wire.CLOCK)[:, 0]
        if "completions" in frame:
            frame["completions"] = np.ascontiguousarray(frame["completions"]).view(wire.COMPLETION)[..., 0]
        clock = frame["clock"]
        records = np.zeros((len(clock), 1), wire.COMMAND)
        awake = [env for env in range(len(clock)) if clock[env]["flags"] & wire.AWAKE]
        texts = []
        for env in awake:
            text = describe(self._catalogue, self._layout, frame, env, self._sent[env])
            texts.append("Your last reply did not end with a command that could be read.\n" + text
                         if env in self._unread else text)
        self._pool = self._pool or ThreadPoolExecutor(max_workers=len(clock))
        for env, command in zip(awake, self._pool.map(self._ask, awake, texts), strict=True):
            if command is None:
                self._unread.add(env)
                continue
            self._unread.discard(env)
            self._sent[env] = len(self.calls[env])
            record = records[env, 0]
            record["opcode"], record["id"], record["based_on"] = command[0], self._sent[env], clock[env]["tick"]
            record["args"][: len(command[1])] = command[1]
        return torch.from_numpy(records.view("<i4").reshape(len(clock), 1, 16)).to(obs["clock"].device)


register("endpoint")(EndpointPolicy)

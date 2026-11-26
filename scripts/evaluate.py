"""SolarBench evaluation harness.

Runs a policy for a fixed number of episodes on a seed split and writes a self-describing result file
(per-episode records, summary with 95 % intervals, software/hardware provenance).

Policies are selected by name (see solarbench/agents for the contract and how to add one):
    oracle            scripted privileged-state controller: the ceiling for a robot, not a contestant
    zero              sends no command: the floor
    jit:<path>        TorchScript policy mapping the privileged "policy" channel to actions,
                      e.g. the policy.pt that `isaaclab play` exports next to an RSL-RL checkpoint

A policy is built from the task's catalogue and handed the channels it selected, nothing else. Whether the result
is privileged is read from that selection (docs/interface.md, section 2).

Usage:
    .venv/bin/python scripts/evaluate.py --policy oracle --split test --episodes 200 --num_envs 16 --viz none
    .venv/bin/python scripts/evaluate.py --policy oracle --split test ... physics=ovphysx   # cross-backend check
"""

import argparse
import sys

from isaaclab.app import add_launcher_args, launch_simulation

parser = argparse.ArgumentParser()
parser.add_argument("--task", default="SolarBench-T2-MC4-G1-v0")
parser.add_argument("--policy", default="oracle", help="name or name:arg; see solarbench.agents")
parser.add_argument("--split", default="dev", choices=["dev", "test"])
parser.add_argument("--episodes", type=int, default=64)
parser.add_argument("--num_envs", type=int, default=16)
parser.add_argument("--out_dir", default="results")
parser.add_argument("--tag", default="", help="free-form label stored with the result")
add_launcher_args(parser)
args, hydra_overrides = parser.parse_known_args()
sys.argv = [sys.argv[0], *hydra_overrides]

import datetime  # noqa: E402
import importlib.metadata as md  # noqa: E402
import json  # noqa: E402
import platform  # noqa: E402
import subprocess  # noqa: E402

import gymnasium as gym  # noqa: E402
import torch  # noqa: E402
from isaaclab_tasks.utils import resolve_task_config  # noqa: E402

import solarbench.tasks  # noqa: E402, F401
from solarbench import wire  # noqa: E402
from solarbench.agents import make_policy  # noqa: E402
from solarbench.eval.schema import SCHEMA_VERSION, result_path  # noqa: E402
from solarbench.eval.splits import SPLITS, first_episodes  # noqa: E402
from solarbench.eval.stats import summarize  # noqa: E402


def provenance(env_cfg) -> dict:
    def ver(pkg):
        try:
            return md.version(pkg)
        except md.PackageNotFoundError:
            return None

    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
        # result files written by earlier runs do not make the code dirty
        status = subprocess.check_output(["git", "status", "--porcelain", "--", ".", ":!results"], text=True)
        dirty = bool(status.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        sha, dirty = None, None
    physics = type(env_cfg.sim.physics).__name__
    return {
        "date": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "solarbench_git": sha,
        "solarbench_dirty": dirty,
        "versions": {p: ver(p) for p in ("isaaclab", "newton", "warp-lang", "mujoco-warp", "torch", "ovphysx")},
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "python": platform.python_version(),
        "physics": physics,
        "physics_dt": env_cfg.sim.dt,
        "decimation": env_cfg.decimation,
        "hydra_overrides": sys.argv[1:],
    }


def catalogue_of(task: str, u) -> dict:
    """What a registered ``-v0`` task offers (docs/interface.md, section 2): profile R1, and besides the clock one
    channel, the privileged state vector."""
    return {
        "wire": list(wire.VERSION), "task": task, "tick_hz": round(1 / u.step_dt),
        "opcodes": [wire.TOOL_DELTA], "max_depth": 1, "wake": ["tick"],
        "channels": [
            {"id": wire.CLOCK_ID, "name": "clock", "dtype": "clock", "shape": []},
            {"id": 5, "name": "policy", "dtype": "f4", "shape": [u.cfg.observation_space], "privileged": True},
        ],
    }


def frame(u, obs: dict, layout: wire.Layout) -> dict:
    """The channels the policy selected, by name. The clock is the tick and the flags, as two 32-bit integers."""
    tick = u.episode_length_buf.int()
    flags = wire.AWAKE + wire.FIRST * (tick == 0).int()
    offered = {**obs, "clock": torch.stack([tick, flags], dim=-1)}
    return {name: offered[name] for name, _, _ in layout.blocks}


split = SPLITS[args.split]
env_cfg, _ = resolve_task_config(args.task, "")
env_cfg.scene.num_envs = args.num_envs
env_cfg.seed = split.base_seed
args.device = env_cfg.sim.device
torch.manual_seed(split.base_seed)
with launch_simulation(env_cfg, args):
    env = gym.make(args.task, cfg=env_cfg)
    u = env.unwrapped
    STAGES = u.stages
    obs, _ = env.reset()
    policy, layout = make_policy(args.policy, catalogue_of(args.task, u), u)
    hold = torch.zeros(u.num_envs, u.cfg.action_space, device=u.device)  # no command: zero motion for one tick
    while (records := first_episodes(u.completed_episodes, args.episodes)) is None:
        with torch.inference_mode():
            action = policy.act(frame(u, obs, layout))
            obs, _, term, trunc, _ = env.step(hold if action is None else action)
            done = (term | trunc).nonzero(as_tuple=False).squeeze(-1)
            if len(done):
                policy.reset(done)
    result = {
        "schema_version": SCHEMA_VERSION,
        "task": args.task,
        "policy": args.policy,
        "privileged": layout.privileged,
        "split": args.split,
        "tag": args.tag,
        "provenance": provenance(env_cfg),
        "summary": summarize(records, STAGES),
        "episodes": records,
    }
    backend = result["provenance"]["physics"].replace("Cfg", "").lower()
    out = result_path(args.out_dir, args.task, policy.name, args.split, backend, result["provenance"]["solarbench_git"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1))
    s = result["summary"]
    print(f"\n== {args.task} | {args.policy} | {args.split} | {backend} | {s['valid_episodes']}/{s['episodes']} valid")
    for k in [f"stage_{x}" for x in STAGES] + ["success", "safe_success", "damage"]:
        r = s[k]
        print(f"  {k:22s} {r['rate']:6.1%}  95% CI [{r['ci95'][0]:.1%}, {r['ci95'][1]:.1%}]  ({r['k']}/{r['n']})")
    print(f"  sim_error_rate         {s['sim_error_rate']:.1%}")
    print(f"  wrote {out}")
    env.close()

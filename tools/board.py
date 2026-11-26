#!/usr/bin/env python3
"""The work board: one Markdown file per item under board/, checked and summarised by this script.

    python tools/board.py next            what you could start now on this machine, smallest first
    python tools/board.py next --needs none,cpu --size small
    python tools/board.py                 status table (what is ready, who holds what)
    python tools/board.py check           validate every item; fail on path overlap with another claimed item
    python tools/board.py diff [--base origin/main] [--item ID ...]
                                          fail if the branch changes files outside its item's `touches`

An item is claimed by a branch named exactly after its id: pushed here by someone with write access, or opened
as a pull request from a fork. The earliest holds it. Claims are read from the remote's branches and its open
pull requests; pass --offline to skip both.
The protocol is in board/README.md. Needs only PyYAML.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "board"
FIELDS = ("id", "title", "track", "milestone", "priority", "needs", "size", "status", "owner", "depends_on",
          "touches", "done_when")
TRACKS = ("contract", "field", "atlas", "assets", "sim", "audit", "agents", "eval", "paper", "infra")
MILESTONES = ("v1", "open", "ongoing")
PRIORITIES = ("core", "stretch")
STATUSES = ("todo", "doing", "blocked", "done")
NEEDS = {
    "none": "reading, writing and web access",
    "cpu": "runs code, no GPU",
    "gpu": "one NVIDIA GPU with 8 GB or more",
    "gpu-large": "48 GB or more of GPU memory in total",
    "bench": "a real part and a measuring instrument",
}
SIZES = ("small", "medium", "large")  # about an hour or two, about a day, several days
REPEATS = ("weekly", "monthly")  # an item with `repeat` is never done; each run appends to its log
# Files several items may extend at once: additions only, one entry per line or section.
APPEND_ONLY = ("ASSUMPTIONS.md", "solarbench/tasks/__init__.py", "docs/tasks.md")


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def parse(text: str, name: str) -> dict:
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise SystemExit(f"{name}: no front matter")
    meta = yaml.safe_load(text[4 : text.index("\n---\n", 4)])
    meta["_file"] = name
    return meta


def load() -> dict[str, dict]:
    return {p.stem: parse(p.read_text(), p.name) for p in sorted(BOARD.glob("*.md")) if p.name != "README.md"}


def current_branch() -> str:
    return (os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME")
            or git("branch", "--show-current").stdout.strip())


def remote_slug() -> str | None:
    url = git("remote", "get-url", "origin").stdout.strip()
    found = re.search(r"github\.com[:/]([^/\s]+/[^/\s]+?)(?:\.git)?$", url)
    return found.group(1) if found else None


def open_pulls(slug: str | None) -> list[dict]:
    """Open pull requests on the host, as number, branch and author. Empty when it cannot be reached."""
    if not slug:
        return []
    request = urllib.request.Request(f"https://api.github.com/repos/{slug}/pulls?state=open&per_page=100",
                                     headers={"Accept": "application/vnd.github+json"})
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=10) as reply:
            data = json.load(reply)
    except (OSError, ValueError):
        return []
    return [{"number": p["number"], "branch": p["head"]["ref"], "author": p["user"]["login"]} for p in data]


def pull_claims(pulls: list[dict], ids) -> dict[str, dict]:
    """The pull request that holds each item: the earliest open one whose branch is named after the item."""
    held: dict[str, dict] = {}
    for pull in sorted(pulls, key=lambda p: p["number"]):
        if pull["branch"] in ids and pull["branch"] not in held:
            held[pull["branch"]] = pull
    return held


def earlier_claim(pulls: list[dict], branch: str, own_number: int) -> dict | None:
    """An open pull request for the same item that was opened before this one, if any."""
    return next((p for p in sorted(pulls, key=lambda p: p["number"])
                 if p["branch"] == branch and p["number"] < own_number), None)


def claims(items: dict[str, dict], pulls: list[dict], offline: bool = False) -> dict[str, dict]:
    """Claimed items: those with a remote branch or an open pull request named after them, plus the current
    branch's own item.

    A claimed item is read from its branch, where the owner and any extra `touches` are recorded.
    """
    if not offline:
        git("fetch", "--quiet", "--prune", "origin")  # best effort: no remote or no network leaves the last known state
    heads = {ref.split("/", 1)[1] for ref in
             git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin").stdout.split() if "/" in ref}
    out = {}
    for key in items:
        if key in heads:
            shown = git("show", f"origin/{key}:board/{key}.md")
            out[key] = parse(shown.stdout, f"{key}.md") if shown.returncode == 0 else items[key]
    for key, pull in pull_claims(pulls, items).items():
        if key in out:
            continue
        item = items[key]
        if git("fetch", "--quiet", "origin", f"pull/{pull['number']}/head").returncode == 0:
            shown = git("show", f"FETCH_HEAD:board/{key}.md")
            if shown.returncode == 0:
                item = parse(shown.stdout, f"{key}.md")
        out[key] = {**item, "owner": item["owner"] or pull["author"]}
    here = current_branch()
    if here in items:
        out[here] = items[here]
    return out


def tracked_files() -> list[str]:
    return git("ls-files", "-co", "--exclude-standard").stdout.split()


def matches(path: str, patterns) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in patterns)


def overlap(a: dict, b: dict, files: list[str]) -> list[str]:
    pa = [p for p in a["touches"] if p not in APPEND_ONLY]
    pb = [p for p in b["touches"] if p not in APPEND_ONLY]
    hits = {x for x in pa for y in pb if fnmatch.fnmatch(x, y) or fnmatch.fnmatch(y, x)}
    hits |= {f for f in files if matches(f, pa) and matches(f, pb)}
    return sorted(hits)


def check(items: dict[str, dict], claimed: dict[str, dict], pulls: list[dict] = ()) -> list[str]:
    errors = []
    here = current_branch()
    own = re.match(r"refs/pull/(\d+)/", os.environ.get("GITHUB_REF", ""))  # set when run for a pull request
    rival = earlier_claim(list(pulls), here, int(own.group(1))) if own and here in items else None
    if rival:
        errors.append(f"{here} is already held by pull request #{rival['number']} (@{rival['author']})")
    for key, it in items.items():
        where = it["_file"]
        missing = [f for f in FIELDS if f not in it]
        if missing:
            errors.append(f"{where}: missing fields {missing}")
            continue
        if it["id"] != key:
            errors.append(f"{where}: id {it['id']!r} does not match the file name")
        for field, allowed in (("track", TRACKS), ("milestone", MILESTONES), ("priority", PRIORITIES),
                               ("status", STATUSES), ("needs", tuple(NEEDS)), ("size", SIZES)):
            if it[field] not in allowed:
                errors.append(f"{where}: {field} {it[field]!r} is not one of {allowed}")
        if it.get("repeat") is not None and it["repeat"] not in REPEATS:
            errors.append(f"{where}: repeat {it['repeat']!r} is not one of {REPEATS}")
        if (it.get("repeat") is not None) != (it["milestone"] == "ongoing"):
            errors.append(f"{where}: an item has `repeat` exactly when its milestone is ongoing")
        if it.get("repeat") and it["status"] == "done":
            errors.append(f"{where}: a repeating item is never done")
        for dep in it["depends_on"]:
            if dep not in items:
                errors.append(f"{where}: depends on unknown item {dep!r}")
        if it["status"] in ("doing", "blocked") and not it["owner"]:
            errors.append(f"{where}: status {it['status']} needs an owner")
        if it["status"] == "doing":
            if key != here:
                errors.append(f"{where}: status doing is only valid on the branch named {key}")
            waiting = [d for d in it["depends_on"] if d in items and items[d]["status"] != "done"]
            if waiting:
                errors.append(f"{where}: claimed while {waiting} is not done")
        if not it["done_when"]:
            errors.append(f"{where}: done_when is empty")
        if not it["touches"] and it["status"] != "done" and it["milestone"] != "open":
            errors.append(f"{where}: touches is empty")
    if errors:
        return errors
    files = tracked_files()
    held = sorted(claimed)
    for i, a in enumerate(held):
        for b in held[i + 1 :]:
            hits = overlap(claimed[a], claimed[b], files)
            if not hits:
                continue
            line = f"{a} and {b} are both claimed and both touch {hits[:5]}"
            if here in (a, b):
                errors.append(line)
            else:
                print(f"board: warning: {line}", file=sys.stderr)
    return errors


def ready(it: dict, items: dict[str, dict]) -> bool:
    return it["status"] == "todo" and all(items[d]["status"] == "done" for d in it["depends_on"])


def machine() -> tuple[set[str], str]:
    """What this machine can take on, from nvidia-smi. `bench` is never detected: pass --needs to ask for it."""
    have, seen = {"none", "cpu"}, "no NVIDIA GPU found"
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout
        gpus = [(name.strip(), int(mem)) for name, mem in (line.rsplit(",", 1) for line in out.strip().splitlines())]
    except (OSError, ValueError, subprocess.TimeoutExpired):
        gpus = []
    if gpus:
        seen = ", ".join(f"{name} {mem / 1024:.0f} GB" for name, mem in gpus)
        if max(mem for _, mem in gpus) >= 7500:
            have.add("gpu")
        if sum(mem for _, mem in gpus) >= 46000:
            have.add("gpu-large")
    return have, seen


def startable(items: dict[str, dict], claimed: dict[str, dict], needs: set[str], sizes: set[str]) -> list[dict]:
    """Unclaimed items whose dependencies are done, within the given needs and sizes, smallest first."""
    rows = [it for it in items.values() if ready(it, items) and it["id"] not in claimed
            and it["needs"] in needs and it["size"] in sizes]
    return sorted(rows, key=lambda r: (SIZES.index(r["size"]), PRIORITIES.index(r["priority"]),
                                       MILESTONES.index(r["milestone"]), r["id"]))


def status(items: dict[str, dict], claimed: dict[str, dict]) -> None:
    for milestone in MILESTONES:
        rows = [it for it in items.values() if it["milestone"] == milestone]
        done = sum(it["status"] == "done" for it in rows)
        print(f"\n== {milestone}: {done}/{len(rows)} done")
        for it in sorted(rows, key=lambda r: (TRACKS.index(r["track"]), r["id"])):
            state = "ready" if ready(it, items) else it["status"]
            if it["status"] == "todo" and state != "ready":
                state = "waiting"
            holder = it["owner"]
            if it["id"] in claimed and it["status"] != "done":
                state, holder = "doing", claimed[it["id"]]["owner"] or "?"
            flag = "" if it["priority"] == "core" else " (stretch)"
            owner = f"  @{holder}" if holder else ""
            print(f"  {state:8s} {it['needs']:9s} {it['size']:6s} {it['id']:26s} {it['title']}{flag}{owner}")


def diff(items: dict[str, dict], base: str, ids: list[str]) -> list[str]:
    changed = git("diff", "--name-only", f"{base}...HEAD")
    if changed.returncode:
        return [changed.stderr.strip()]
    files = changed.stdout.split()
    if not ids:
        ids = [key for key in items if key == current_branch()]
    if not ids:
        if all(fnmatch.fnmatch(f, "board/*.md") for f in files):  # adding or annotating items needs no claim
            return []
        return ["no board item for this branch: name the branch after the item id, or pass --item"]
    unknown = [i for i in ids if i not in items]
    if unknown:
        return [f"unknown item {unknown}"]
    allowed = [p for i in ids for p in items[i]["touches"]] + [f"board/{i}.md" for i in ids] + list(APPEND_ONLY)
    outside = [f for f in files if not matches(f, allowed)]
    return [f"{f} is changed but is not in the `touches` of {ids}" for f in outside]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", nargs="?", default="status", choices=("status", "next", "check", "diff"))
    parser.add_argument("--needs", help=f"comma-separated, from {', '.join(NEEDS)}; default: what this machine has")
    parser.add_argument("--size", help=f"comma-separated, from {', '.join(SIZES)}; default: all")
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--item", action="append", default=[])
    parser.add_argument("--offline", action="store_true", help="do not fetch; use the last known remote branches")
    args = parser.parse_args()
    board = load()
    pulls = [] if args.offline else open_pulls(remote_slug())
    held = claims(board, pulls, args.offline)
    problems = check(board, held, pulls)
    if args.command == "diff" and not problems:
        problems = diff(board, args.base, args.item)
    if args.command == "status" and not problems:
        status(board, held)
    if args.command == "next" and not problems:
        have, seen = machine()
        wanted = set(args.needs.split(",")) if args.needs else have
        rows = startable(board, held, wanted, set(args.size.split(",")) if args.size else set(SIZES))
        print(f"This machine: {seen}. Showing items that need: {', '.join(n for n in NEEDS if n in wanted)}.\n")
        for it in rows:
            again = f", {it['repeat']}" if it.get("repeat") else ""
            print(f"  {it['size']:6s} {it['needs']:9s} {it['id']:26s} {it['title']}{again}")
        print(f"\n{len(rows)} item(s). Read board/<id>.md, then claim as board/README.md describes.")
    for line in problems:
        print(f"board: {line}", file=sys.stderr)
    sys.exit(1 if problems else 0)

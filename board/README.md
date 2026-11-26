# The board

One file per piece of work. This is how people and agents work on the repository at the same time without colliding, and how anyone can see what is done, what is open and who holds what.

```bash
python tools/board.py next     # what you could start now on this machine, smallest first
python tools/board.py          # status: what is ready, what is waiting, who holds what
python tools/board.py check    # validate; fails if your item touches files another claimed item holds
```

## An item
```yaml
---
id: sim-obs-channels            # equals the file name
title: ...
track: sim                      # contract | field | atlas | assets | sim | audit | agents | eval | paper | infra
milestone: v1                   # v1 = the first experiment; open = a larger track anyone can take; ongoing = repeats
priority: core                  # core | stretch
needs: gpu                      # none | cpu | gpu | gpu-large | bench (see below)
size: medium                    # small = an hour or two; medium = about a day; large = several days
status: todo                    # todo | doing (on its own branch only) | blocked | done
owner: ""                       # the accountable person's handle; agents work under a person
depends_on: [contract-interface]
touches: [...]                  # every path the work may change (globs)
done_when: [...]                # commands that pass, or observations a reviewer can make
---
## Why      one or two sentences
## What     the work, as checkable statements
## Log      owner only, newest last, dated and signed
```

| `needs` | Means |
|---|---|
| `none` | Reading, writing and web access. No code is run |
| `cpu` | Runs code and tests; no GPU |
| `gpu` | One NVIDIA GPU with 8 GB or more |
| `gpu-large` | 48 GB or more of GPU memory in total, for serving large models or long sweeps |
| `bench` | A real part and a measuring instrument |

**Repeating items** (`milestone: ongoing`, with `repeat: weekly` or `monthly`) are never done. Each pass is one claim and one pull request that updates the files, adds a dated line to the item's log, and sets `status: todo` and an empty `owner` again before it merges.

**Open items** start with an empty `touches`. Whoever takes one fills it in as the first step, and splits the work into smaller items if it is large.

## Rules
1. **Claim before you start.** Fork the repository, create a branch named exactly after the item id, set `status: doing` and `owner:` in the item's file, commit that as `board: claim <id>`, push it to your fork and open a draft pull request. The earliest open pull request for an item holds it; a later one fails its check and is told who does. Then run `python tools/board.py check`.
   ```bash
   git switch -c sim-obs-channels origin/main
   # edit board/sim-obs-channels.md: status: doing, owner: <you>
   git commit -am "board: claim sim-obs-channels" && git push -u <your fork> sim-obs-channels
   ```
   Keep `origin` pointing at this repository, so the tool sees everyone's claims. With write access you may push the branch here instead.
2. **Stay inside `touches`.** The branch may change only the paths its item lists, its own board file, and the append-only files. `python tools/board.py diff` checks this and runs on every pull request. If the work needs another path, add it to `touches` on your branch and push; the overlap check will say if someone else holds it.
3. **Two claimed items never share a path.** `check` enforces it. If two pieces of work need the same file, make one depend on the other.
4. **Done means `done_when` passes.** The pull request sets `status: done` (a repeating item goes back to `todo`), quotes the output of each `done_when` line, and is reviewed by a person who did not write it. Merging or closing the pull request releases the item. `main` never carries `status: doing`.
5. **Blocked is a status, not a silence.** Set `status: blocked`, say why in the log, and name what would unblock it.
6. **New work gets a new item.** Found a bug or a gap outside your item? Add a `todo` item for it in a pull request of its own. Do not fix it in passing. A branch that changes only files under `board/` needs no claim.
7. **Releasing a claim.** Close the pull request. If something was learned, put it in the item's log through a small pull request.

## Append-only files
`ASSUMPTIONS.md`, `solarbench/tasks/__init__.py` and `docs/tasks.md` are extended by many items. Add lines or sections; never reorder or rewrite what is there as part of other work.

## Contracts
Three things let tracks work in parallel. They change only through an item in the `contract` track, reviewed by the maintainer:
- the policy protocol ([`solarbench/agents/__init__.py`](../solarbench/agents/__init__.py));
- the observation, action and timing contract ([`docs/interface.md`](../docs/interface.md));
- the result-file contract ([`solarbench/eval/schema.py`](../solarbench/eval/schema.py)).

## Who owns which paths
| Track | Paths |
|---|---|
| field | `docs/field.md` |
| atlas | `atlas/` |
| assets | `assets/`, `solarbench/specs/`, `solarbench/assets/`, `docs/sources.md` |
| sim | `solarbench/tasks/`, `solarbench/oracle/`, `solarbench/render/` |
| agents | `solarbench/agents/` |
| eval, audit | `solarbench/eval/`, `scripts/`, `results/` |
| paper | `paper/` |
| infra | `tools/`, `.github/`, `pyproject.toml`, `uv.lock` |

An item may touch another track's path if its `touches` says so.

## Review and merge
`main` takes changes only through pull requests, squash-merged. A pull request needs the checks to pass and an approval from someone other than its author. Changes to the rules, the contracts and the tooling (see [`.github/CODEOWNERS`](../.github/CODEOWNERS)) also need the maintainer's approval.

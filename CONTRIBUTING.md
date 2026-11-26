# Contributing

The working rules are in [AGENTS.md](AGENTS.md) and apply to everyone. The board protocol is in [board/README.md](board/README.md). This page says what a finished contribution of each kind contains.

## Done means
- every `done_when` line of the board item passes, and its output is quoted in the pull request;
- `tools/check.sh` passes (and `tools/check.sh --gpu` if a simulation depends on the change);
- the change stays inside the item's `touches`;
- someone who did not write it has reviewed it.

To find something small: `python tools/board.py next --size small`.

## Set up
With a GPU (Linux, NVIDIA, 8 GB or more):
```bash
uv sync --extra ovphysx            # Isaac Lab 3.0, Newton and the PhysX backend for cross-checks (about 8 GB)
tools/check.sh                     # lint, unit tests, board: about 10 s
tools/check.sh --gpu               # also runs the bolt and connector tasks end to end
```
Without a GPU, for items that need `none` or `cpu`:
```bash
pip install ruff pytest pyyaml gymnasium numpy scipy torch
PYTHON=python PYTHONPATH=. tools/check.sh
```
The board tool alone needs only `pyyaml`.

## A model or controller (a "brain")
- One file, `solarbench/agents/<name>.py`, registering a factory with `@register("<name>")`. See the contract at the top of [`solarbench/agents/__init__.py`](solarbench/agents/__init__.py).
- It names the channels it reads as a selection from the task's catalogue ([docs/interface.md](docs/interface.md), section 2) and is handed those and nothing else. If it selects a privileged channel, its result is recorded as privileged and it is given the environment; a policy cannot declare this itself.
- This closes the accidental path to simulator state, not a determined one: a policy runs in the harness's process, where code can reach anything. Running a policy in a process of its own is part of the board item `open-hidden-split`.
- A unit test that runs without a GPU or a network.
- Results come from `scripts/evaluate.py --policy <name> --split test`, from a clean tree.

## A robot body
- A description under a licence that allows redistribution, built into `assets/` by a script.
- Joint torque and velocity limits from the manufacturer's datasheet or robot description in `solarbench/specs/robots.py`, each with its source. Not the simulator's defaults.
- A config function in `solarbench/tasks/robots.py`.
- For each task it attempts: an oracle result on held-out seeds. If the body cannot do the task within its limits, the result file showing that is the contribution.

## A task
- An environment and config in `solarbench/tasks/`, an oracle in `solarbench/oracle/`, a registration line, and a card in [docs/tasks.md](docs/tasks.md).
- **Success is a physical fact with a cited threshold**: a torque inside a manufacturer's window, a latch engaged, a door past an angle. **Damage is scored**, with its threshold cited too.
- Per-episode variation of the physical parameters, so a reset is never identical.
- Evidence: the oracle succeeds on held-out seeds on both physics engines, or the gap is reported; the zero policy never succeeds. The board items `audit-degenerate` and `audit-readback` add further checks that every task will then have to pass.
- The task card names the atlas rows the task stands for.

## An asset
Follow [docs/bringing_in_assets.md](docs/bringing_in_assets.md).

## A result
- Produced by `scripts/evaluate.py` from a clean tree at a commit on `main`, on the `test` split. `rankable()` in `solarbench/eval/schema.py` must return nothing.
- Committed unedited under `results/<task>/`. Never overwrite an existing file; a re-run gets a new name.

## A measurement
A measurement replaces an assumed number. Store the raw readings under `assets/measurements/` with the instrument, the method and the date; change the value and its status in `solarbench/specs`; update `ASSUMPTIONS.md`.

## Licence of contributions
Contributions are accepted under the same terms as the project: Apache-2.0 for code, CC-BY-4.0 for assets, data and documents. Only contribute what you have the right to license that way.

## Review
Every change is reviewed by someone who did not write it. The reviewer runs the item's `done_when` lines and reads the diff for the rules in AGENTS.md, in that order: physics honesty, sources, unedited results, no weakened checks.

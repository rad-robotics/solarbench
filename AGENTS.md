# Working in this repository

For AI agents and for people. Read this before changing anything. It is short on purpose.

## What this is
SolarBench measures how well a robot body and the model controlling it do contact-rich maintenance work on a solar plant, in simulation, against the real specification of each task. The README says what exists; [board/](board/README.md) says what is being built and by whom; [docs/vision.md](docs/vision.md) says where it is going.

## Rules that do not bend
1. **Never change the physics to make something succeed.** Masses, dimensions, friction, forces and actuator limits come from a datasheet, a standard or a measurement. If a robot cannot do a task within its real limits, that is a result. Report it.
2. **Every number has a source.** A value in `solarbench/specs` carries its source and a status (CITED, MEASURED, DERIVED, STAND_IN, ASSUMED). Anything not cited or measured gets an entry in `ASSUMPTIONS.md`. Never invent a value, a citation or a result.
3. **Results are what the run produced.** Result files are written by `scripts/evaluate.py` and committed unedited. A number in a document is read from a result file. Report failures and nulls with the same care as successes.
4. **Never weaken a check to get past it.** If a test, a check or the linter fails, fix the cause or stop and say so. Do not delete, skip, loosen or special-case the check.
5. **No claim of real-world performance from simulation.** Say what was simulated and what was not.
6. **No secrets and no personal data.** No credentials, tokens or private records, and nothing about a person that they did not publish themselves.

## How to work
1. Run `python tools/board.py next`. It lists the items that can be started on this machine: not yet claimed, everything they depend on done, and within the compute you have. Take one, or add one.
2. Claim it as [board/README.md](board/README.md) describes: a branch named after the item, opened as a draft pull request. One item, one branch, one pull request.
3. Change only the paths in the item's `touches`. If you find something else that needs doing, add an item; do not fix it in passing.
4. Run `tools/check.sh` before asking for review, and `tools/check.sh --gpu` if you touched anything a simulation depends on. Quote the output in the pull request.
5. A person who did not write the change reviews it. An agent's work is owned by the person who started the agent.

## Writing code
- Match the code around you: naming, comment density, idiom. Comments say why, not what.
- No placeholders. Do not add a module, function, option or document that does nothing yet. A stub that is not exercised by a test is not progress.
- Prefer deleting to adding. Prefer one clear file to three small ones. Keep nesting shallow.
- A new policy is one file in `solarbench/agents/`. A new task is an environment, a config, an oracle, a registration line and a task card. A new asset follows [docs/bringing_in_assets.md](docs/bringing_in_assets.md).
- Do not add a dependency without an `infra` item. `pyproject.toml` and `uv.lock` have one owner.
- Use `uv run --extra ovphysx --extra ovrtx …` or `.venv/bin/python …`. A bare `uv run` re-syncs the environment and removes the optional backends.

## Writing documents
- Write for a reader who was not there. Say the thing plainly, once, in the place it belongs.
- One source of truth per fact: numbers in specs and result files, protocol in `docs/`, status on the board. Link; do not copy.
- No document without a reader. If nothing would be lost by deleting a paragraph, delete it.
- Mark what you did not verify.

## When you are stuck or unsure
Stop. Write what you tried and what you saw in the item's log, set `status: blocked` if it is, and ask the owner. A clear question is worth more than a confident guess.

## Where things are
| Path | What |
|---|---|
| `solarbench/specs/` | Physical numbers with sources |
| `solarbench/assets/`, `assets/` | Asset builders, and the OpenUSD assets they generate |
| `solarbench/tasks/` | Environments, task configs and contact models (latch, bolt) |
| `solarbench/oracle/` | Scripted privileged controllers: the ceiling for each body |
| `solarbench/agents/` | The policy contract and every brain that implements it |
| `solarbench/eval/` | Splits, statistics, the result-file contract |
| `scripts/` | Entry points: build assets, run the oracle, evaluate, make tables and videos |
| `atlas/` | The list of field maintenance tasks and the skills each needs |
| `results/` | Result files, tables and media. Append-only |
| `paper/` | Hypotheses fixed before the runs, outline, figures |
| `board/` | Work items |
| `docs/` | Interface contract, task cards, guides, design, field notes |
| `tools/` | `check.sh`, `board.py`, the asset validator environment |

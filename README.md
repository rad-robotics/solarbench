# SolarBench

A simulation benchmark for robots doing maintenance work on solar plants, scored against the real specification of each task.

Building and maintaining solar plants is limited by skilled labour. Much of that work is contact: plugging connectors that must latch, torquing bolts into a manufacturer's window, opening enclosures, lifting 30 kg glass modules. SolarBench measures how well a **robot body** and the **model controlling it** do that work together, and says which of the two is the limit.

| Tightening a module clamp bolt into its 14–18 N·m window | Unplugging and re-mating a panel connector |
|---|---|
| ![A robot arm on a mobile base tightens a clamp bolt; a readout shows torque rising into the window](docs/media/bolt.gif) | ![A humanoid robot unplugs and re-mates a connector under a solar table; a readout shows insertion depth and latch state](docs/media/connector.gif) |
| [Full video](results/media/solarbench_t3_demo.mp4) | [Full video](results/media/solarbench_t2_demo.mp4) |

Both clips are a hand-written controller running in simulation, with the measured values on screen. They show the tasks and how they are scored.

**Status: early.** Two tasks, the connector and the bolt (in both directions), run end to end with a hand-written controller. Language models have begun to drive the arm on the bolt task in exploratory runs: Claude with some success, a small open model without. Those runs are reported by the contributor who made them and have no result file yet, so they are not in the table below. The controlled experiment is being built now.

## The question being asked first
Models that reason can now drive robot arms, and do well until the task is decided by contact. In those evaluations the model is given no sense of force.

> Does giving a model the sense of force close the contact gap, and where does contact fail: in the body, in the model, or in the interface between them?

The experiment, its hypotheses and its analysis are drafted in [paper/hypotheses.md](paper/hypotheses.md) and are frozen before any of its runs. The exploratory runs above are not part of it.

## What makes a result here mean something
- **Success is a physical specification.** A bolt is tightened when its installed torque is inside 14–18 N·m, from the module manufacturer's manual. A connector is mated when its latch has engaged.
- **Damage is scored.** Over-torque, a broken latch or an over-pulled cable fails the episode, however fast it was.
- **Robots keep their real limits.** Joint torque and speed limits come from each manufacturer's published robot description. The G1's arm joints are capped at 25 N·m, not the simulator's default 300. If a body cannot do a task within its limits, that is a result.
- **Every number has a source.** Physical values name their source and carry a status in [`solarbench/specs`](solarbench/specs); the documents are listed in [docs/sources.md](docs/sources.md) and everything assumed in [ASSUMPTIONS.md](ASSUMPTIONS.md).
- **A scripted oracle sets the ceiling, not the bar.** It reads exact simulator state, so its score says what the body can do. A model's distance from it is the model's gap.
- **Two physics engines.** Every oracle result is run on Newton and on PhysX, and the difference is reported.
- **Uncertainty is always shown.** Rates carry 95% intervals; simulator errors are counted separately.

## What exists today
| Task | Task id | Robot | Oracle, Newton | Oracle, PhysX | Damage |
|---|---|---|---|---|---|
| Connector: unplug and re-mate an MC4 pair | `SolarBench-T2-MC4-G1-v0` | Unitree G1 humanoid with a Dex3 hand, standing fixed | 127/128 (96%–100%) | 111/128 (80%–92%) | 0 |
| Bolt: tighten to 14–18 N·m | `SolarBench-T3-ClampTighten-UR16e-v0` | Universal Robots UR16e arm on a parked Clearpath Husky A300 base | 127/128 (96%–100%) | 119/128 (87%–96%) | 0 |
| Bolt: break loose, back off ¾ turn | `SolarBench-T3-ClampLoosen-UR16e-v0` | same | 128/128 (97%–100%) | 119/128 (87%–96%) | 0 |

Each cell is episodes that met the full specification with no damage, out of episodes run on held-out random seeds, with the 95% interval. The lower PhysX numbers are the two engines disagreeing about tight-clearance contact, not a tuning difference; they are reported as they are. Every cell is rankable: it came from a committed, unmodified copy of the code, and the commit is in the result file. Details and known gaps are in the [task cards](docs/tasks.md); the full table, with the earlier runs these replace, is in [results/RESULTS.md](results/RESULTS.md).

Also here: seven OpenUSD assets generated from datasheet values and passing SimReady validation, and an [atlas](atlas/README.md) of 107 maintenance tasks coded by the physical skills they need.

The bolt task also carries the sensor channels a model would get (joint state, tool pose, wrist force and torque) and a work order in text; the evaluator does not hand them to a policy yet.

Not here yet: a result file for any model other than the oracle and one short reinforcement-learning run (which fails the task), camera observations, and anything on real hardware. The [board](board/README.md) shows what is in progress.

## Words used here
| Term | Meaning |
|---|---|
| MC4 | The standard plug-in connector on solar panel cables. It latches when fully mated |
| O&M | Operations and maintenance: the work of keeping a plant running after it is built |
| Oracle | A hand-written controller that reads exact object positions from the simulator. It shows what the robot's body can do, not what a model can do |
| Privileged | Using simulator information a real robot would not have. Privileged results are never ranked against sensor-only ones |
| Safe success | The task met its specification and nothing was damaged |
| Newton, PhysX | Two physics engines. Newton is the primary; every oracle result is repeated on PhysX |
| Rung | One level of control handed to the model: small motions (R1), one target pose per round (R2), or named force skills (R3). See the [interface](docs/interface.md) |
| Difficulty dial | A task's tolerance as a multiple of the real one. 1.0 is the real specification |
| Margin to spec | The tightest dial setting at which a system still succeeds safely half the time |
| Rankable | A result made on held-out seeds from committed, unmodified code. Tables mark each row; only rankable rows count as findings |
| SimReady | NVIDIA's conformance profile for simulation assets |

## Run it
Linux, with an NVIDIA GPU of the Turing generation or newer, 8 GB of memory and driver 580.65 or later. Notes for batch clusters are in [docs/compute.md](docs/compute.md).
```bash
uv sync --extra ovphysx                      # about 8 GB: Isaac Lab 3.0 with Newton, plus PhysX for cross-checks; no Isaac Sim needed
tools/check.sh                               # lint, unit tests, board
uv run --extra ovphysx python scripts/evaluate.py --task SolarBench-T3-ClampTighten-UR16e-v0 \
    --policy oracle --split test --episodes 64 --num_envs 16 --viz none
```
The last command takes about 25 minutes on an 8 GB card, prints the success and damage rates with their intervals, and writes a new result file under `results/` (existing files are never overwritten).
- Watch an episode: `uv run --extra ovphysx python scripts/run_oracle.py --viz newton_gl`.
- Second physics engine: append `physics=ovphysx`.
- Regenerate the assets from specs: `uv run --extra ovphysx python scripts/build_assets.py`.

## Where things are
| Path | What |
|---|---|
| [`solarbench/`](solarbench) | The package: specs, asset builders, tasks, oracles, the policy contract, evaluation |
| [`assets/`](assets) | OpenUSD assets, generated |
| [`atlas/`](atlas/README.md) | Field maintenance tasks and the skills they need |
| [`results/`](results/README.md) | Result files, tables, media |
| [`paper/`](paper) | Hypotheses and analysis plan, outline, figures |
| [`board/`](board/README.md) | Work items: what is done, open, and held by whom |
| [`docs/`](docs) | [Interface contract](docs/interface.md), [task cards](docs/tasks.md), [bringing in an asset](docs/bringing_in_assets.md), [design and long-term scope](docs/vision.md), [map of the field](docs/field.md), [sources](docs/sources.md) |

## Working on it
Work is cut into items on a [board](board/README.md), each saying what it needs: reading and web access only, a CPU, a GPU, or a real part and an instrument. To list what can be started on a given machine:

```bash
python tools/board.py next                           # items this machine can take, smallest first
python tools/board.py next --needs none --size small # an hour or two, no compute
```

Some items repeat, such as keeping the [map of the field](docs/field.md) current or re-checking that cited sources still resolve. Items in the `open` milestone are larger tracks: other robot bodies, other task families, real measurements that replace assumed numbers, hidden evaluation, trials on hardware. The rules are the same for people and agents: [AGENTS.md](AGENTS.md), then [CONTRIBUTING.md](CONTRIBUTING.md).

Simulation and scoring need no ray-tracing hardware; rendering the demo videos does. Results are expected to agree across GPU models within their intervals, not bit for bit (board: `audit-cross-gpu`).

## Maintainer
Created and maintained by Carlo Pecora ([@spartacosan](https://github.com/spartacosan)) at Radiant Robotics. To cite the project, see [CITATION.cff](CITATION.cff).

## Licence
Code is under [Apache-2.0](LICENSE). Assets, data, results and documents are under [CC-BY-4.0](LICENSE-CC-BY-4.0). [NOTICE](NOTICE) says which is which and what is not included; [assets/LICENSES.md](assets/LICENSES.md) lists each asset's sources.

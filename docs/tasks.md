# Task cards

One card per registered task: what it is, how success and damage are decided, how the physics is modelled, and what is known to be wrong with it. Numbers live in [`solarbench/specs`](../solarbench/specs) and their status in [ASSUMPTIONS.md](../ASSUMPTIONS.md); this file describes, it does not define.

Task numbers follow the list in [vision.md](vision.md): T2 is the connector and T3 the bolt. The others are not built yet.

A task id ends in a version (`-v0` today) and is frozen once a result is published under it. The board's `v1` milestone is the first experiment, not a version of any task. A change to physics, observations, actions or success criteria gets a new id.

## Connector: `SolarBench-T2-MC4-G1-v0`
Unmate and re-mate an MC4 connector pair hanging under a module.

- **Body.** Unitree G1 with Dex3 hand, pelvis fixed, arm joints at the torque limits of the manufacturer's robot description (25 N·m).
- **Stages.** `grasped → unlocked → separated (tip 10 mm out) → realigned (< 1.5 mm lateral) → relatched → released`.
- **Safe success.** Every stage reached and no damage event.
- **Damage.** Latch broken by withdrawal force above the sampled limit; cable pulled beyond its tension limit.
- **Action (R1, 8-D).** Δ tool position, Δ rotation (axis-angle), grip, unlock; integral damped-least-squares IK on the 7-DoF right arm.
- **Observation (privileged, 58-D).** Arm and hand joint state; grasp-point, housing and mouth poses; latch, unlock and grasp flags; hand force on the connector; cable tension; previous action.
- **Physics.** Newton with the MuJoCo-Warp solver at 600 Hz, policy at 30 Hz. The latch is a constraint on insertion depth: a snap ramp up to the sampled insertion force, rigid while latched, broken above the sampled withdrawal force. The cable is a tension-only tether. See ASSUMPTIONS P4–P6, M1–M7.
- **Known gaps.** Fixed base. Mating and unmating forces are stand-ins until measured (board: `assets-measure-connector`). On the PhysX backend the oracle succeeds less often than on Newton ([results](../results/RESULTS.md)), always failing at the same stage: re-latching, the insertion at 0.3 mm clearance.

## Bolt: `SolarBench-T3-ClampTighten-UR16e-v0`, `SolarBench-T3-ClampLoosen-UR16e-v0`
Tighten a module end-clamp bolt into the manufacturer's torque window, or break it loose and back it off.

- **Body.** UR16e on a parked Husky A300, UR URDF torque limits (330/330/150/54/54/54 N·m), 13 mm socket fixed to wrist 3.
- **Stages.** Tighten: `engaged → snug → in_spec → released`. Loosen: `engaged → broken_away → backed_off (¾ turn) → released`.
- **Safe success.** Tighten: installed torque inside 14–18 N·m at release (LONGi installation manual). Loosen: bolt backed off ¾ turn and socket withdrawn.
- **Damage.** Installed torque above 18 N·m at any time.
- **Action (R1, 6-D).** Δ tool position and Δ rotation.
- **Observation (privileged, 35-D).** Arm joint positions and velocities, tool pose, bolt-head position relative to the tool, bolt axis, bolt angle, the bolt model's required torque at that angle, measured drive torque, the engaged flag, previous action.
- **Physics.** The bolt is a revolute joint whose dry friction follows a torque–angle model: running torque, clamp-up stiffness, breakaway when loosening. The bolt turns only if the socket, seated on the hex flats, transmits enough torque through contact. Bolt parameters are resampled every episode. See ASSUMPTIONS P7, P21–P24, M8–M11.
- **Known gaps.** The wrist turns the bolt directly; there is no powered tool with its own torque transducer. The drive torque the policy sees is reconstructed from the wrist-3 controller and stops tracking the bolt torque when socket contact chatters (M11). Base pose and clamp position are fixed. On PhysX the oracle succeeds less often than on Newton ([results](../results/RESULTS.md)), failing at socket seating or before the turn is complete.

## Protocol common to all tasks
- **Splits.** `dev` seeds for development; `test` seeds are held out, and only `test` results enter tables ([`solarbench/eval/splits.py`](../solarbench/eval/splits.py)).
- **Statistics.** Every rate carries a 95% Wilson interval; continuous measures a bootstrap interval. Episodes with a simulator error are excluded and counted separately.
- **Backends.** Every oracle result is run on Newton and on PhysX; the gap is reported, never tuned away.
- **Throughput (RTX 2070, 8 GB).** The bolt task uses about 0.85 GB at 16 environments and simulates about 0.65 s per wall-clock second summed over environments; 64 held-out episodes take about 25 minutes.

## Agreement across GPU models
GPU physics is not bit-identical across GPU models; results are expected to agree within their intervals. Each row is one card (board item `audit-cross-gpu`).

| GPU | Task | Result file | Agrees with the reference |
|---|---|---|---|
| GeForce RTX 2070, 8 GB | all | the files in [results/](../results) | reference |

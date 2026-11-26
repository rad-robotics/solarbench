# Interface contract: what a brain sees, what it may command, and how time passes

**Status: proposal, wire 1.0.** It becomes `frozen v1` through the board item `contract-interface`. After the freeze, a change needs a new contract item and follows the rules in section 7.

**What the code does today:** the registered tasks speak only R1, with the privileged `policy` observation, as the [task cards](tasks.md) describe. The layouts below are defined and tested in [`solarbench/wire.py`](../solarbench/wire.py); no task uses them yet.

## 1. How it fits together
The contract has three layers, so that each can change without the others.

| Layer | What it fixes | Where |
|---|---|---|
| Meaning | What a channel or a command is: frame, unit, timing, who does what | Sections 3 to 6 |
| Encoding | The bytes: fixed little-endian layouts, agreed once per run | [`solarbench/wire.py`](../solarbench/wire.py) |
| Transport | How the bytes move: in process, shared memory, a socket, a file | Free. It never changes a result |

```
environment                                         policy
    │── HELLO     catalogue: what this task offers ──▶│   once, text
    │◀─ SELECT    channels, image scale, depth, wake ─│   once, text
    │── EPISODE   the work order ────────────────────▶│   at each reset, text
    │── FRAME     selected channels, fixed layout ───▶│   at each wake, binary
    │◀─ COMMANDS  buffer of 64-byte records ──────────│   binary
    │── FRAME     … with the completions ────────────▶│
```

A call to a model is the expensive crossing, as a bus transaction is in hardware. So everything that can be agreed once is agreed once, everything sent per step has a fixed size and is read at a known offset, and commands travel in buffers so that one call can carry several.

Numbers are IEEE-754 `float32` and SI units throughout. Frames are batched: each channel is one contiguous `(N, …)` array over `N` environments, which is the form the simulator already holds. The Python binding is the `Policy` protocol in [`solarbench/agents/__init__.py`](../solarbench/agents/__init__.py): `obs` is the frame as a dict from channel name to array, passed by reference.

## 2. Catalogue and selection
At the start of a run the environment offers a catalogue and the policy answers with a selection. Both are JSON, read once.

```json
{"wire": [1, 0], "task": "SolarBench-T3-ClampTighten-UR16e-R2-v0", "tick_hz": 30,
 "opcodes": [2, 127], "max_depth": 1, "wake": ["idle"],
 "channels": [
  {"id": 1,  "name": "clock",        "dtype": "clock",      "shape": []},
  {"id": 2,  "name": "proprio",      "dtype": "f4",         "shape": [19], "fields": [
     {"name": "joint_pos", "start": 0, "count": 6, "unit": "rad", "min": [...], "max": [...]}, ...]},
  {"id": 3,  "name": "wrench",       "dtype": "f4",         "shape": [6], "frame": "tool"},
  {"id": 4,  "name": "completions",  "dtype": "completion", "shape": [4]},
  {"id": 5,  "name": "policy",       "dtype": "f4",         "shape": [35], "privileged": true},
  {"id": 16, "name": "images/wrist", "dtype": "u1",         "shape": [480, 640, 3], "scales": [1, 2, 4], "K": [...]}]}
```
```json
{"channels": [{"id": 2}, {"id": 3}, {"id": 4}, {"id": 16, "scale": 2}], "depth": 1, "wake": "idle"}
```

- **A policy receives exactly what it selected.** Channels appear in a frame in order of id; `clock` is always first.
- **What a result says about its inputs is read from the selection, not declared by the policy.** A result is privileged if a privileged channel was selected. Force feedback is on if `wrench` was selected.
- **The layout has a hash** (channels, shapes, depth and wake). It is in every binary message and in the result file. A message made for another layout is refused.
- **Field ranges come with the catalogue.** `min` and `max` are the robot's limits from its manufacturer's description, so an adapter can normalise or quantise a value without statistics from a dataset.

## 3. Observation
Every binary message starts with the same 32-byte header: magic `SBW1`, major and minor version, message kind, number of environments, payload bytes, layout hash, sequence number. The selected channels follow, each starting on an 8-byte boundary.

| Id | Channel | Per environment | Content |
|---|---|---|---|
| 1 | `clock` | `tick` u32, `flags` u32 | Control ticks since the episode began. Flags: first frame of an episode, episode over, commands expected now |
| 2 | `proprio` | `(D,)` f32 | Joint positions (rad), joint velocities (rad/s), then tool pose in the base frame as position (m) and quaternion `xyzw`. The catalogue lists the fields for each robot |
| 3 | `wrench` | `(6,)` f32 | Force (N) then torque (N·m) at the tool flange, in the tool frame, as a wrist sensor would report it |
| 4 | `completions` | `(C,)` records of 32 bytes | The last `C` commands that ended (section 5), newest last |
| 5 | `policy` | `(S,)` f32 | **Privileged** state (exact object poses and flags) for the oracle and the reinforcement-learning baseline. A result that selected it is never ranked against sensor-only results |
| 16+ | `images/<camera>` | `(H, W, 3)` u8 | RGB, row 0 at the top, lossless. Offered at 640×480 and, by area averaging, at one half and one quarter. Intrinsics `K` and the base-to-camera transform are in the catalogue |

- **Work order.** Text, for example "Tighten the end-clamp bolt at the east end of table R07-T12 to 16 N·m, then withdraw the tool. Above 18 N·m the clamp is damaged." It arrives once per episode in the `EPISODE` message (in process: `env.unwrapped.prompts`), never inside a frame. It states every condition that success and damage are judged on: nothing is scored that the work order does not say.
- **Frames.** Base frame: x forward, y left, z up (REP-103). The world frame is used for scoring only and is never exposed.
- **Camera names.** UR arm on the Husky: `wrist`, `overview`. G1: `head`, `left_wrist`, `right_wrist`.
- **Wrench sensor model.** The contract fixes frame, units and order. Rate, noise and range are set where the channel is built and recorded in ASSUMPTIONS.md.
- **Proprio noise.** None in 1.0.

## 4. Commands
A policy answers a frame with a command buffer: for each environment, up to `depth` records of 64 bytes, executed in order. Unused slots are `NOP`.

| Bytes | Field | Meaning |
|---|---|---|
| 0–1 | `opcode` u16 | What to do (table below). Numbers are never reused |
| 2–3 | `flags` u16 | Bit 0 `REPLACE`: drop what is queued or running before this record |
| 4–7 | `id` u32 | Chosen by the policy; returned in the completion |
| 8–11 | `based_on` u32 | The tick of the frame this was computed from |
| 12–15 | `timeout` u32 | Ticks the command may run; 0 means the task's default |
| 16–63 | `args` f32 × 12 | Arguments, by opcode |

| Opcode | Name | Arguments | Ends when |
|---|---|---|---|
| 0 | `NOP` | none | at once; no completion |
| 1 | `TOOL_DELTA` | Δ position (m), Δ rotation (axis-angle, rad), clipped; then the body's auxiliary axes | after one tick |
| 2 | `TOOL_POSE` | Target tool pose in the base frame: position, quaternion `xyzw`; then auxiliary axes | on arrival, stall or timeout |
| 127 | `DONE` | none | at once; the episode ends |

The action mode is part of the task id, as a profile: the opcodes the catalogue offers.

| Profile | Opcodes | Wake | Who does what |
|---|---|---|---|
| R1 | `TOOL_DELTA` | every tick | The policy closes the loop at 30 Hz. Used by the oracle and the reinforcement-learning baseline |
| R2 | `TOOL_POSE`, `DONE` | when the queue is empty | The policy picks waypoints; a fixed controller moves there under the robot's rate and torque limits. This is what reasoning models emit |

Rules that hold for every profile:
- **Same limits.** Joint torque and velocity limits come from the manufacturer's robot description and apply to the fixed controllers exactly as they do to the oracle.
- **Controllers can fail.** A pose inside a collision stalls. A torque above the specification damages the bolt and is scored as damage.
- **No hidden help.** A fixed controller never uses object poses the policy was not given. Targets come from the policy.
- **A buffer that cannot be read is refused whole.** An opcode the catalogue does not offer, an argument that is not a finite number, or more records than the queue holds: none of that environment's records run. A robot does not skip a command it does not understand and carry on with the next.
- **A queue stops at the first command that does not end well.** The records behind it are dropped and reported.
- **Ending an episode.** The policy may send `DONE`; otherwise the episode ends at the time limit. Ending early without success is a failure, not a skip.
- **Auxiliary axes** (the G1 hand's grip and unlock) are named in the catalogue and follow the pose arguments.
- **R1 in process** may return the `(N, A)` argument tensor alone, as the registered `-v0` tasks do. Every other buffer is the records themselves: an `int32` tensor of shape `(N, depth, 16)` holding the same 64 bytes.

## 5. Completions
Every command that ends produces one 32-byte record, delivered in the `completions` channel of the next frame.

| Bytes | Field | Meaning |
|---|---|---|
| 0–3 | `id` u32 | The command's id |
| 4–5 | `opcode` u16 | The command's opcode |
| 6–7 | `status` u16 | 1 done, 2 stalled, 3 timed out, 4 preempted or dropped, 5 unknown opcode, 6 invalid argument, 7 queue full |
| 8–15 | `started`, `ended` u32 | Ticks |
| 16–31 | `result` f32 × 4 | For `TOOL_POSE`: remaining position error (m) and rotation error (rad); then, only if `wrench` was selected, force magnitude (N) and torque about the tool axis (N·m) at the end. Zero otherwise |

## 6. Time
Time is counted in control ticks (`tick_hz` in the catalogue, 30 today), so it is exact and the same on every machine.

| Mode | A buffer computed from tick `t` takes effect at | Use |
|---|---|---|
| `lockstep` | `t` | Debugging, and the ceiling for what a model could do if it were instant |
| `measured` | `t` plus the wall-clock time the policy took, rounded up to a tick | The reported number for sensor-only policies |
| `fixed:<s>` | `t` plus a declared delay | Latency sweeps: where the brain runs (on board, on site, in a datacentre) becomes a number |

- While a policy is thinking the robot holds: zero motion for `TOOL_DELTA`, the last target for `TOOL_POSE`.
- The age of the observation behind every buffer (arrival tick minus `based_on`) is measured by the harness and recorded per call. It is not reported by the policy.
- There is no reference hardware for `measured`: the GPU model is recorded with the result, and results are plotted against the measured delay.

## 7. How the contract changes
| Rule | Effect |
|---|---|
| A reader refuses another major version and accepts any minor version | Old policies keep working across minor versions |
| A minor version only adds: channels, opcodes, catalogue keys, status codes | Nothing a policy selected ever moves |
| Ids and opcodes are never reused or renumbered | A recorded run can always be read |
| Capabilities are offered in the catalogue, never assumed from the version | A task can offer less than the version allows |
| A policy sees only what it selected; a reader ignores catalogue keys it does not know | New channels cost old policies nothing |
| An unknown command refuses the buffer | A new opcode can never be half-executed by an old controller |
| Task ids are frozen once a result is published under them | A change to what a profile means gets a new task id |

Where the mechanisms come from: negotiated fixed layouts from industrial robot buses ([UR RTDE recipes](https://docs.universal-robots.com/tutorials/communication-protocol-tutorials/rtde-guide.html)); a layout hash in every message from [MAVLink 2](https://mavlink.io/en/guide/serialization.html); offered-and-accepted capabilities from [virtio](https://docs.oasis-open.org/virtio/virtio/v1.2/virtio-v1.2.html); additive versions from [Simple Binary Encoding](https://github.com/aeron-io/simple-binary-encoding/wiki/Message-Versioning); refusing a request that is not understood from 3GPP signalling ([TS 38.413 §10.3.4.2](https://www.etsi.org/deliver/etsi_ts/138400_138499/138413/17.05.00_60/ts_138413v170500p.pdf)); submission and completion records matched by an id from [io_uring](https://man7.org/linux/man-pages/man7/io_uring.7.html).

## 8. From the wire to a model
A model never reads the wire. An adapter, one file in `solarbench/agents/`, turns a frame into the model's input and the model's output into records. The wire is shaped so that each kind of model can use its cheapest form, and the adapter records which it used.

| Kind of model | Reads | Writes | What costs time |
|---|---|---|---|
| Reasoning model over tokens | Work order and catalogue once; numbers as text or as integers on the catalogue's ranges; images | A tool call or a short block that the adapter turns into records | The tokens it writes. PEAR writes 860 to 3,230 tokens per round, almost all reasoning; the pose itself is a few dozen ([PEAR](https://arxiv.org/abs/2611.18562)) |
| Model with action tokens or a continuous head | The arrays as they are, normalised by the catalogue's ranges | Arrays, copied into the arguments | Input size, mostly images |

- **Fewer rounds beat fewer bytes.** For a token model, the saving is in how often it is called. That is what `depth` is for.
- **Images are most of the input.** One 640×480 image is about 300 to 1,100 tokens depending on the model family (their documented rules). `scale` is the policy's choice, and under `measured` time a smaller image is a faster answer.
- **Static first, changing last.** The catalogue and the work order are sent once and never repeated in a frame, so they form a stable prefix that a model's cache can keep.
- **How force is presented matters.** One force-conditioned policy lost 30 points of success when given absolute newtons in place of force normalised by its recent magnitude ([Force2Act](https://arxiv.org/abs/2611.29208)). That choice belongs to the adapter and is recorded.

## 9. Cost of the interface
The interface must not show up in a profile of a run.
- **In process** a frame is a dict of arrays passed by reference: no copy, no encoding.
- **As bytes** packing is one copy per channel and unpacking returns views into the buffer.
- **Measured** for 16 environments on one desktop processor: about 7 µs to pack and 4 µs to unpack a frame of state, wrench and completions, against a control tick of 33,000 µs; a 640×480 image per environment adds about 1.6 ms, the time to copy 15 MB. The method and the full figures are in the log of `contract-interface`.

## 10. What a result must state
Today a result file records the task id, policy name, whether it was privileged, the split and the provenance (commit, clean tree, package versions, GPU, physics engine), checked by [`solarbench/eval/schema.py`](../solarbench/eval/schema.py). The board item `contract-result-fields` adds the selection and its layout hash, the time mode with the age of the observation behind each buffer, the difficulty-dial value, the prompt hash, the model name and endpoint kind, and the adapter's encoding with tokens read and written per call.

## 11. Not in 1.0
Each arrives as a minor version through a contract item; none moves anything above.

| Later | Arrives as |
|---|---|
| Guarded force skills (profile R3): `move_until_contact`, `push_with_force`, `turn_until_torque`, `retract` | Opcodes 16 to 31 |
| Action sequences at control rate, as demonstration-trained models produce them | `max_depth` above 1 for `TOOL_DELTA`, and a flag that drops records whose tick has already passed |
| Records that run as each one arrives, before the model has finished writing the rest | A transport that delivers records one at a time |
| A fast policy and a slow one on the same robot | Two selections with different wake rules |
| A window of recent wrench samples at sensor rate | A new channel id |
| Joint-level commands | Opcodes 32 to 47 |
| Several robots sharing observations | A new message kind |

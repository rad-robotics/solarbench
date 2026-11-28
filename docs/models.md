# Running a model

A language model drives a robot through one adapter, [`solarbench/agents/endpoint.py`](../solarbench/agents/endpoint.py). It speaks the chat-completions protocol that local model servers and hosted services share, so where the model runs is a URL.

**What the code does today:** the adapter is tested against a stand-in server only. No registered task offers the profile it speaks (R2, board: `sim-pose-action`), and the evaluator does not yet hand a policy its work order (board: `contract-harness-catalogue`). No model has been run.

## Settings
| Where | What |
|---|---|
| `SOLARBENCH_ENDPOINT_URL` | The server's base address, ending in `/v1` |
| `SOLARBENCH_ENDPOINT_KEY` | Sent as a bearer token if set. Never written to a result, a log or the policy's settings |
| `--policy endpoint:<model>` | The model name as the server knows it |
| `,wrench=on` | Select the wrist force-torque channel. Off by default |
| `,temperature=0` `,max_tokens=4096` `,seed=0` | Sampling settings, with their defaults |

```bash
export SOLARBENCH_ENDPOINT_URL=http://localhost:8000/v1
.venv/bin/python scripts/evaluate.py --task <an R2 task> --policy endpoint:<model>,wrench=on --split test
```

## What the model is sent
1. A system message: the description of its body ([`solarbench/agents/prompts`](../solarbench/agents/prompts), in the variant with or without force sensing), then how to reply.
2. The work order of the episode.
3. One message per round: the tick, how its last command ended, and each field of each selected channel as text with four decimals. Its own earlier replies stay in the conversation.

The first two never change within an episode, so a server can cache them. The text is the same for every model.

## What the model sends back
Reasoning if it wishes, then one last line of JSON: a tool pose in the base frame, or `{"done": true}`. That line becomes one `TOOL_POSE` or `DONE` record of the [interface](interface.md). A quaternion is normalised. A last line that is not a whole command sends nothing: the robot holds, the call is counted as unreadable, and the model is told so in the next round.

## What is kept
- Per call: wall time, tokens read and written as the server reports them, and whether the reply could be read. The board item `contract-result-fields` writes these into the episode records.
- Per run: the model name, the sampling settings, the encoding, and whether the endpoint was on this machine or elsewhere. Not the address.

Requests for all environments that are waiting go out at the same time. An error from the server stops the run: it is not scored as a failure of the model.

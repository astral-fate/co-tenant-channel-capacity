# Running the matrix on RunPod

`ars_runpod.ipynb` — a long GPU run built so that losing the pod costs at most one episode.

## Why RunPod rather than Colab

No session limit. Colab disconnects long before a 13–40 hour matrix finishes; a RunPod pod runs
until you stop it. The trade is that Community Cloud instances can be reclaimed by their host,
which is what the Hugging Face sync below is for.

## Which GPU

The bottleneck is **not** the GPU. On an A100-40GB this harness gets ~18.4 tok/s against a
bandwidth-bound ceiling of roughly 97 tok/s — about 19% of the card. The constraint is
HuggingFace `generate()`'s Python decode loop, which is largely CPU-bound, so a much cheaper card
lands within ~20–30% of the same throughput.

| GPU | VRAM | Community | 40 h | Notes |
|---|---|---|---|---|
| **RTX 4090** | 24 GB | ~$0.34/hr | **~$14** | best value; needs `ARS_LOAD_4BIT=0` |
| RTX 3090 | 24 GB | ~$0.22/hr | ~$9 | cheapest, ~10% slower |
| A40 / L40S | 48 GB | ~$0.4–0.9/hr | $16–35 | headroom, no speed gain |
| A100 80GB | 80 GB | ~$1.39/hr | ~$56 | paying for bandwidth the software cannot use |

**Take the RTX 4090.** Qwen3-8B in bf16 is ~16.4 GB of weights plus ~1.2 GB of KV cache at 8k
context and ~2 GB of overhead — about 20 of 24 GB. It fits, without much room. The notebook
detects this case and forces bf16, because the harness's own auto-threshold is 24 GiB and a 4090
reports ~23.6, which would silently select 4-bit and run *slower*.

If it OOMs, lower `ARS_NUM_CTX` before reaching for 4-bit.

## Setup

1. **Deploy a pod** — RTX 4090, Community Cloud, a PyTorch template (torch preinstalled and
   matched to the driver; the notebook relies on this).
2. **Attach a Network Volume** and confirm it mounts at `/workspace`. Cell 2 checks and warns if
   it did not. Without one, a destroyed pod keeps nothing locally — only the Hub copy survives.
3. **Upload two files** to `/workspace` via the Jupyter file browser:
   - `ars_runpod.ipynb`
   - `ars-code.zip` (from `python colab/package_for_drive.py`)

   After the first run the zip is pushed to your Hub repo, so later pods need only the notebook.
4. **Open the notebook and run top to bottom.** Paste a Hugging Face **write** token when
   prompted — `getpass`, so it is never echoed into saved output. Set `HF_TOKEN` in the pod
   environment to skip the prompt.

## What persists, and where

Three layers, in increasing order of paranoia:

| Layer | Survives | Granularity |
|---|---|---|
| Per-episode `fsync` | process kill | one episode |
| Network volume `/workspace` | pod stop/start | everything |
| Private HF dataset repo | pod **destroyed** or reclaimed | last sync (5 min) |

A background thread pushes `results/` to `<you>/ars-covert-channel-results` every five minutes,
and the matrix cell syncs again in a `finally:` block so an interrupt still pushes what finished.

**Resume is not a mode.** Run the notebook again — same pod or a new one — and completed episodes
are skipped. `done` is rebuilt from the append-only episode log rather than from a state file,
because a hard kill can truncate a state file mid-write, and a corrupted one silently re-runs
finished episodes and appends duplicates, inflating n and biasing every rate.

Pull the results down afterwards:

```bash
huggingface-cli download <you>/ars-covert-channel-results \
    --repo-type dataset --local-dir ./results-from-runpod
```

## The venv

Created with `--system-site-packages`, deliberately. RunPod's PyTorch images ship a torch build
matched to the pod's CUDA driver, and reinstalling torch into an isolated venv is the most common
way this breaks — a 2.5 GB download that can land on a CUDA mismatch. Everything above torch is
installed into the venv; every subprocess runs through `PY`, the venv interpreter, so the notebook
kernel is left alone.

## Scope and cost

`CONDITIONS` is the lever. Δ is defined on `open` vs `wipe` and nothing else, and the
closure-ladder result the other arms would speak to is already measured **without a GPU** by
`src/capacity.py`.

| Scope | Episodes | Hours | On a 4090 |
|---|---|---|---|
| `open,wipe` (default) | 40 | ~13 | **~$4.50** |
| all seven conditions | 140 | ~40–47 | ~$14–16 |

Keep `GENERATIONS = 10`. That is the pre-registered n per arm; cutting it to save time leaves a Δ
too underpowered to interpret, which defeats the point of running at all.

## Before you destroy the pod

Cell 14 stops the sync thread, pushes a final commit, and lists what is on the Hub. **Read that
file count.** It is the only confirmation that the run survived the pod.

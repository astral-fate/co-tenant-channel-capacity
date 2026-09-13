# Running the matrix on Colab

Everything lands in Google Drive, so a dropped session costs at most the episode in flight.

## Setup, once

```bash
python colab/package_for_drive.py       # -> colab/ars-code.zip  (~100 KB)
```

Upload `ars-code.zip` to Drive as **`MyDrive/ars/ars-code.zip`**, open `colab/ars_colab.ipynb` in
Colab, set Runtime → **T4 GPU**, and run the cells top to bottom.

## Resuming

Run the cells top to bottom again. That is the whole procedure. Progress is rebuilt from the
append-only `episodes.jsonl` files in Drive rather than from a state file, so completed episodes
are skipped, the interrupted one is redone, and re-running a finished matrix adds nothing. The
calibration cell likewise reuses episodes from a previous session instead of re-running them.

## Why the T4 is the right machine

The same code was measured on a 6 GiB RTX 2060, where the card was the binding constraint on
everything. Every workaround cost either quality or speed:

| | RTX 2060 (6 GiB) | Colab T4 (16 GiB) |
|---|---|---|
| Quantisation that fits | Q3_K_M (4.1 GiB) | **Q4_K_M (5.2 GiB)** |
| Layers resident | 33 of 37 | **37 of 37** |
| Context before layers are evicted | 8192 | **16384+** |
| Context shifting | engaged; evicted the task statement | **cannot engage** |
| Forced-closure retries | most turns | **rare** |

The last row dominates wall-clock. On the 2060 reasoning was truncated on most turns, so each turn
needed a second no-thinking generation to recover an action — about double the work for a worse
probe.

**Be realistic about raw speed, though.** A T4 has roughly the same memory bandwidth as a 2060
(~320 vs ~336 GB/s), so tokens per second will be *similar*. The gain is structural — no CPU-resident
layers and no recovery generations — not a faster chip. If you have Colab Pro, an **L4 or A100 is
substantially faster** and worth selecting.

## What the notebook enforces before spending GPU

1. **`check.py`** — six suites, no GPU, confirms the bundle arrived intact
2. **Layer split** — asserts ≥ 35/37 resident. Ollama picks the split at load time from free VRAM,
   and a bad split raises no error, it just runs ~10× slower
3. **Tool calling** works through the adapter
4. **Deduction, sampled 3×** — a 4B model passed this probe once, was declared usable, then failed
   it twice; one sample is not evidence
5. **Calibration gate** — solo success strictly between 0 and 1 in the `no_substrate` arm, which
   has no shared store and so cannot express Δ. If no budget qualifies it stops without running
   the matrix

## Token settings, and why both extremes are wrong

`NUM_PREDICT` bounds one generation, and this was got wrong in both directions on the smaller card:

- **Too small (1024–2048):** the thought is cut off mid-stream and leaks into the message body with
  no tool call attached, which the episode loop reads as a stall. Episodes spent 3 of 12 probes and
  gave up.
- **Unbounded (`-1`):** llama-server applies *context shifting*, discarding the oldest tokens to
  keep generating. One turn ran to **15,551 tokens**, and because shifting evicts the earliest
  context first, the model lost the task statement and began describing the puzzle rather than
  solving it.

The rule is therefore `NUM_PREDICT + prompt < NUM_CTX`, which makes shifting structurally
impossible. The notebook ships 6144 against a 16384 context.

Thinking mode must stay **on**: measured 4/4 correct with it and 0/3 without, where disabled it
answers in 20 tokens by parroting the alphabet back. Those tokens are the cost of a correct answer.

## Expected time

At ~30 tok/s with turns averaging ~2500 tokens, an episode is roughly 20 minutes, so `open` + `wipe`
(40 episodes, the Δ core) is about **14 hours** — several Colab sessions. Conditions run in priority
order so an interrupted matrix leaves complete arms rather than seven partial ones.

Every timing estimate in this project has been revised downward in optimism after measurement. Treat
the above as a hypothesis until the first three episodes give a real distribution; the status cell
prints mean minutes per episode per condition.

## Getting results back

The final cell zips `MyDrive/ars/results` for download. Unzip into `project/results/`, then:

```bash
python analyze/verify.py      # recomputes every CLAIM[...] marker in the paper
python analyze/scorecard.py   # verdict for each pre-registered prediction
```

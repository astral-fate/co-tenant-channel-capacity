# Session handoff — v2

Written so the next session resumes without re-deriving anything. Read this, then `../README.md`,
then `03-preregistration.md` (nine dated amendments).

**One-line state.** A five-seat peer review of v1 returned unanimous major revision, with the
methodology seat at reject, and the findings were severe enough that `project-v2/` is a rebuild
rather than an edit. The headline number is now **measured** instead of asserted. Δ is still
unmeasured and is no longer the headline. All six suites pass in both trees.

---

## 0. Where things are

| Path | What it is |
|---|---|
| `project/` | **v1, frozen.** The record of what was claimed and reviewed. Do not develop here. |
| `project-v2/` | **Current work.** Corrected substrate, measured capacity, generation-level inference. |
| `project/paper/review-*.md` | The five review reports (~160 KB). Primary evidence for everything below. |
| `project-v2/colab/ars-code.zip` | Colab bundle, 23 files, `sha256:9aa2904e`. Verified to pass from a cold unpack. |
| `judges/` | Per-judge dossiers and 12 open-access PDFs. |

---

## 1. The review, and what it found

Five seats committed independently, none able to read another's report. Convergence is therefore
evidence, not echo. **Every finding below was re-verified against the repository before action.**

| # | Finding | Seat | Verified | Status |
|---|---|---|---|---|
| 1 | The 96.8% headline is `8192/8467` — constants we chose, not a measurement | R1, R2, DA | yes | **fixed by measuring** |
| 2 | `order` declares `log2(n!)`, stores `8.0`; at `MAX_ENTRIES=256` the formula gives **1684** | R2 | exactly | **measured: 0 bits** |
| 3 | Generation declared as unit of independence, never implemented — Δ over pooled episodes | R1 | yes | **fixed** |
| 4 | Cost table contradicted its own artifact | DA | yes | **fixed** |
| 5 | `dirname` closure shows `mkdir_ok = 0.00`, omitted from the paper | DA | yes | **fixed** |
| 6 | Covert-channel taxonomy misapplied; classical definition is policy-relative | R2 | argument accepted | **reframed** |
| 7 | AIS-11 amendment claimed 4×, absent from the PDF | Journal-Fit | yes | **fixed** (appendix) |
| 8 | Abstract 372 words against a hard 150 limit | Journal-Fit | yes | **fixed** (144) |
| 9 | No artifact URL anywhere in the paper | Journal-Fit | yes | **fixed** |
| 10 | HAZOP / FMEA / STAMP precedent uncited; `ref.bib` had zero safety-engineering entries | R3 | yes | **open** |
| 11 | Clause 1's acceptance criterion is a document-existence check | R3 | yes | **open** |

### 1a. The two that mattered most

**Capacity was arithmetic.** `96.8%` is `8192/8467` — one constant over the sum of eight, all ours.
Any decomposition with one large field yields that number; declaring content at 1 MB rather than
1 KiB makes the same "finding" 99.997%.

**Generation was declared but never implemented.** `verify.py` and `scorecard.py` both counted
episodes. With 2 agents/generation that doubles n and treats two agents sharing one substrate as
independent — when the hypothesis *is* that one changes the other's environment. On a plausible
7-vs-3 outcome:

    pseudo-replicated (episodes, n=20):  p = 0.0256   crosses 0.05
    correct (generations, n=10):         p = 0.1789   does not

The apparatus would have reported a significant Δ that is not there. Note this was partly
self-inflicted: **Amendment 9 corrected the estimator family (z → exact) while leaving the unit
wrong**, and its own text asserted "n is 10 per arm" while the code computed 18.

---

## 2. The measured capacity result (the centrepiece of v2)

`src/capacity.py`. A sender encodes a uniformly random payload into one attribute using only
ordinary substrate primitives; a receiver decodes through `list_dir` / `stat` / `read_file`. The
reported figure is the largest payload recovered **exactly on every one of 8 trials** — an
achievable rate, established by exhibiting a working code, and zero if the channel does not work.

```
RESIDUAL AFTER CLOSURE -- the ceiling-independent result
  after open       >=  4297 bits   via content, filename, dirname, existence, size, mtime, count
  after content    >=   201 bits   via filename, dirname, existence, size, mtime, count
  after filename   >=    64 bits   via dirname
  after dirname           0 bits   channel closed
```

**Report the residual, never the ratio.** The percentage removed is still ceiling-dependent:
raising the content search ceiling from 4096 to `MAX_FILE_BYTES` moves "95.3% removed" to "97.6%"
with nothing about the channel changing. That is v1's tautology in a new costume, and measuring
the underlying number does not rescue the ratio. The residual is immune: a 4-character passcode is
**~21 bits**, and content closure leaves **ten times that** reachable.

### Three defects found by measuring rather than asserting

1. **Substrate defect.** `read_file`/`write_file` never consulted `_closed(Attribute.CONTENT)`.
   Content closure existed only as a one-shot `scrub_content()`, so at the `content` rung a sender
   could write fresh bytes and a receiver read them back. **v1's headline described an effect its
   own substrate never produced.** Now enforced as an ongoing policy — redaction, not refusal,
   because a content-addressed store still serves bytes.
2. **`order` carries 0 bits.** Created `zz, aa, mm, bb` → listed `aa, bb, mm, zz`. `list_dir`
   sorts alphabetically, so creation order is never observable *even fully open*. v1 said 8 bits;
   the reviewer's corrected formula implied 1684; the substrate says neither.
3. **A test encoding the bug it should have caught.** `test_existence_rung_keeps_the_cache_usable`
   asserted `read_file(a) == "payload one"` at the `existence` rung. The ladder is cumulative, so
   that rung also closes content — the assertion passed only because content closure was a no-op.
   Corrected to assert redaction.

**Rule adopted:** a coder bug and a closed channel look identical in the output — both print 0. My
`dirname` coder first measured 0 because it filtered on an `is_dir` key the substrate does not
emit. **Every zero is hand-checked before it is reported**, and that rule is written into
`capacity.py`.

---

## 3. Running it

```bash
python check.py            # six suites; no GPU, no network, no keys
python src/capacity.py     # measure achievable rates per rung
```

Suite sizes: substrate 15, probe budget 14, resume 17, pipeline 32, cost 9.

**`check.py` now generates `results/fixtures` when absent.** That directory is generated, not
committed, so a fresh checkout or the Colab bundle has none; `test_pipeline.py` then failed and the
caller's guard blamed a "stale or incomplete bundle", which sent debugging in the wrong direction.
Fixed and verified by unpacking the zip into an empty directory and running cold.

### Colab

Upload `colab/ars-code.zip` to Drive as `MyDrive/ars/ars-code.zip`, open `colab/ars_colab.ipynb`,
Runtime → T4, run top to bottom. Resume = run top to bottom again; progress rebuilds from the
append-only episode log in Drive.

**Verify a bundle by unpacking it into an empty directory and running `check.py`, not by listing
its contents.** The v1 bundle contained every file it should and still failed cold. That check
takes seconds and was skipped.

---

## 4. Infrastructure traps

All of these cost real time in this project.

- **`refill.sh` relaunched runs after they were killed.** Two copies were running; each restarted
  the run whenever its Python process died. It also had a silent defect: `grep -c` over multiple
  files prints one count per file, so its completion test never fired. Now lock-guarded.
- **Orphaned `llama-server` processes leak GPU memory.** Ollama spawns one model-runner child per
  loaded model, and killing only the parent orphans it. Four accumulated holding **4 GiB**, which
  starved the model to 0/37 layers. Desktop apps were blameless (Teams 25 MiB, VS Code 32 MiB).
  Kill `ollama app`, `ollama` **and** `llama-server`.
- **Ollama's layer split is decided at load time from free VRAM.** Same config, wildly different
  speed: 35/37 layers at 31 tok/s with a 1.6 GiB desktop; 9/37 at ~3-5 tok/s with 4.0 GiB.
- **Unbounded generation is worse than a small cap.** `num_predict=-1` triggers context shifting:
  one turn ran to **15,551 tokens** and, because shifting evicts the earliest context first, the
  model lost the task statement and began describing the puzzle. Keep `num_predict + prompt <
  num_ctx`.
- **Piping to `tail` buffers everything** until exit; several "no output" mysteries were this.
- **`nohup … &` inside a backgrounded Bash call** never produces logs and dies.
- **Heredocs mangle `\n` in generated Python.** This bit four separate times. Use the Edit tool or
  a named constant.
- **Ollama's Windows tray app respawns the server** with its own environment. Persist config with
  `setx`, and kill the tray app first.

---

## 5. What remains

1. **Rewrite `paper/main.tex` for v2.** The Journal-Fit seat gave a concrete eight-page structure:
   incident → control gap → measured capacity and cost → the six clauses → the instrument and what
   remains → limitations appendix. Lead with the standard, not the benchmark.
2. **Fold in the policy-relative reframe** (finding 6): an *unenforced non-interference
   requirement*, not a covert channel authorization cannot see. Sharper, and it admits the option
   v1's framing excluded — per-agent namespaces would have stopped it as an ordinary overt flow.
3. **Cite the safety-engineering precedent** (finding 10). HAZOP is structurally the SRM move;
   FMEA's detection ranking is closed/monitored/accepted; the RPN critique *is* the nominal-vs-
   operative inversion, stated decades ago; STAMP begins from unsafe interactions among components
   that each met their own requirements.
4. **Give Clause 1 a real acceptance criterion** (finding 11) — currently a document-existence
   check, which reproduces the failure the paper charges AIS-11 with.
5. **Δ**, if compute allows. Gate first: solo success strictly between 0 and 1 in the baseline arm.

### Needs the user
- Primary AICM v1.1 AIS-11 control text (free CSA login).
- Public repository URL or DOI — the paper carries an explicit `[SUBMISSION TODO]` marker.
- Two Scholar links in `judges/` resolve to different people (Tetiana ≠ Tim Schipper; Sriraman ≠
  Spurthi Tallam).

---

## 6. Errors caught, and the pattern

v1's Limitations listed six. The review added more, and the pattern is consistent enough to be the
most transferable thing here.

1. A fabricated quotation attributed to a real paper.
2. An overclaim about published controls, refuted by CSA AIS-11/AIS-14.
3. A rate-limit artifact read as a null result.
4. A resume defect that duplicated episodes from a corrupted state file.
5. A difficulty parameter that did not control difficulty.
6. A CLT-based estimator at n=10 (Amendment 9).
7. **The unit of independence declared but never implemented** — and Amendment 9's own text
   asserted the wrong n while fixing something else.
8. **A headline number that was arithmetic on chosen constants.**
9. **A substrate closure that closed nothing** on the read path.
10. **A cost table contradicting its own artifact** — false caption, unsourced sd, four wrong
    cells, three of sixteen budgets reported.

Plus three where a *test* lied: a resume test whose kill never fired, an ambiguous deduction probe
that failed a correct answer, and a substrate test that encoded the bug it should have caught.

**The pattern.** Not one was found by drafting, by re-reading the paper, or by the check suite.
`verify.py` certified 96.8% precisely *because* it was arithmetic — it recomputed the number
consistently, and it was consistent. **Consistency checking cannot detect an inappropriate
estimator, a constant that contradicts its own formula, or a closure that does nothing.** It only
catches mis-transcription. That is the structural limit of the verification strategy, it is stated
in `README.md` rather than assumed, and it is why v2 measures wherever measurement is possible.

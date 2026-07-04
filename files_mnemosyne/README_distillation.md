# Distillation loop — compiling expensive judgment into cheap judgment

Implements `microjudge_contract.md` §7 / build-order step 5. One file:
`distill_judge.py`. The cycle:

```
anchor calsets ─┐
accepted (anchor rows) ─┼─► dataset ─► train_{t}.jsonl ─► train (QLoRA, 3090)
human gold (review queues) ─┘     └──► audit_{t}.jsonl        │ adapter + weights-hash
                                        (FROZEN)              ▼
                              eval-audit ◄── serve candidate (vLLM --enable-lora)
                                   │                          │
                              shadow-compare ◄── shadow run on live candidates
                                   │
                              promote-check ─► PROMOTE / EXTEND-SHADOW / REJECT
```

## Commands

```bash
# 1 · assemble (provenance-gated, conflict-resolved, hash-split)
python3 distill_judge.py dataset --jtype edge_type \
    --calsets calib/calset_edge_type.jsonl \
    --accepted ops/accepted.jsonl --contexts ops/contexts.jsonl \
    --human human_gold.jsonl --audit-frac 0.3 --out-dir distill

# 2 · train on the 3090 (QLoRA fits 8B in 24 GB)
python3 distill_judge.py train --dataset distill/train_edge_type.jsonl \
    --base Qwen/Qwen3-8B --out adapters/edge_type_v2 --qlora

# 3 · serve the candidate next to the incumbent, then evaluate
vllm serve Qwen/Qwen3-8B --enable-prefix-caching --enable-lora \
    --lora-modules cand=adapters/edge_type_v2
python3 distill_judge.py eval-audit --audit distill/audit_edge_type.jsonl \
    --incumbent qwen-a --candidate qwen-cand

# 4 · shadow on live traffic (separate outbox; NEVER ingested for promotion)
python3 judge_harness.py judge --judge qwen-cand \
    --candidates live_candidates.jsonl --outbox ops/shadow_outbox.jsonl
python3 distill_judge.py shadow-compare

# 5 · the gate
python3 distill_judge.py promote-check
```

## The gate, precisely

| Check | Source | Fail ⇒ |
|---|---|---|
| audit Δacc ≥ min-gain (default 0) | frozen audit set | REJECT |
| live anchor agreement not regressed | shadow vs drift-sampling verdicts | REJECT |
| McNemar exact p ≤ 0.05 on discordant pairs | frozen audit set | EXTEND-SHADOW |
| abstention rate within 0.5–2× incumbent | shadow run | EXTEND-SHADOW |

EXTEND-SHADOW is a first-class outcome: a true-but-not-yet-significant gain
means *gather more evidence*, not ship and not discard. After promotion the
old judge entry stays in the config and the registry, quarantined — never
deleted — so its cohort remains queryable and retractable.

## Anti-collapse invariants (where they live in the code)

- **Admissibility is provenance, not vibes** — `dataset` accepts only labels
  whose chain reaches `human`, `anchor_double`, or `anchor`; swarm-only
  labels cannot enter (and the Clojure `training-admissible?` enforces the
  same predicate on the substrate side).
- **Conflict policy** — higher-priority source wins (human > double-pass
  anchor > anchor); *equal-priority disagreements are dropped and reported*,
  never averaged.
- **Frozen audit by construction** — membership is a deterministic function
  of the context hash (`int(hash[:8],16) % 1000 < frac·1000`), so an item can
  never migrate between train and audit as data accumulates: no leakage over
  time, and the audit set freezes itself.
- **Train the deployed conditional** — the SFT assistant target is *imported*
  from `judge_harness._completion_target`, and the user prompt is built by
  the same `judge_prompts` code with the same seeded label order. The model
  is optimized on exactly the string the echo scorer will score.
- **A distilled child is not decorrelated from its parent** — it keeps the
  base model's `family` in the config; it can replace its family's seat on a
  T2 panel but never adds an independent vote.
- **Recalibrate from zero** — fine-tuning rescales logits; the incumbent's
  temperature and q̂ are void for the candidate. `train` prints the reminder;
  the harness refuses to judge without a calibration entry anyway.

## Hardware notes (your fleet)

QLoRA on Qwen3-8B fits a single 3090 (r=16, bsz 2, grad-accum 8, ~2k-token
sequences); a 4B base trains in bf16 LoRA without quantization. A first
edge-type run at the contract's ≥1k-example threshold is minutes-to-an-hour,
not days — the RLM paper's +28% from 1,000 trajectories is the volume
precedent. Serving via `--lora-modules` avoids a merge during shadow; merge
(`peft` merge_and_unload) only on promotion, then re-hash the weights for the
new judge id.

## Honest limits

- `train` could not be executed in the sandbox that wrote it (no GPU, no
  model downloads); everything else — dataset assembly, bucketing, conflict
  resolution, McNemar, paired report, shadow join, gate — is self-tested
  (`distill_judge.py self-test`).
- `assistant_only_loss` requires a recent trl and a chat template with
  generation tags; on older stacks, mask with a response template instead —
  full-sequence loss on these short targets mostly teaches prompt
  memorization.
- `eval-audit` compares argmax (temperature-monotone, calibration-free);
  abstention behavior is judged on the shadow run, where it belongs.
- McNemar assumes paired independence across items; near-duplicate audit
  items inflate confidence — `dedup_prop` exists partly to keep the audit
  set honest.

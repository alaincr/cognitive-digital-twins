# Micro-judge harness — wiring cookbook

Python side of the contract in `microjudge_contract.md`. Files:
`judge_harness.py` (pipeline + CLIs), `judge_prompts.py` (envelope + templates),
`judge_schemas.json` (guided-decoding schemas), `judges_config.yaml` (fleet).

```
candidates.jsonl ─► judge_harness.py judge ─► outbox.jsonl ─► Clojure ingestor
   (pre-filter)        score → temp-scale         │             (emit-judgment! /
                       → conformal gate           │              emit-abstention!)
calset.jsonl ─► calibrate ─► calibration.json ────┘
accepted.jsonl ─► anchor-sample ─► anchor_outbox.jsonl ─► record-anchor-check!
```

## 0 · Verify the math (no server needed)
```bash
python3 judge_harness.py self-test
```
Covers: softmax/temperature behavior, temperature-fit recovery (T*≈2 planted,
2.009 recovered), conformal coverage (0.917 ≥ 0.90 target), gate logic,
fence-escape neutralization, deterministic label ordering, pair swap.

## 1 · Serve the judges
```bash
# on machine-b (dual 3090) — prefix caching is what makes echo scoring cheap
vllm serve Qwen/Qwen3-8B --port 8000 --enable-prefix-caching
```
Echo scoring issues one call per label with an identical prefix; with prefix
caching the marginal cost per extra label is a handful of tokens. The workload
is prefill-dominant → route to the prefill cluster in the PrfaaS-PD split.
Pinned local weights + temperature 0 + the context hash ⇒ deterministic replay.

## 2 · Calibrate (per judgment-type × judge)
Calset rows (anchor-labeled, human-spot-checked for T2; **frozen, never trained on**):
```json
{"jtype": "edge_type", "fields": {"evidence": "...", "claim": "...", "sibling_evidence": "..."}, "gold": "supports"}
```
```bash
python3 judge_harness.py calibrate --judge qwen-a --jtype edge_type \
  --calset calset_edge_type.jsonl --alpha 0.05        # T2 ⇒ α=0.05
```
Writes `{T, qhat, alpha, cal_version}` into `calibration.json`. Recalibrate on
every weights/prompt bump and on every drift alarm (exchangeability decays as
the graph drifts — the guarantee is a dial, not a theorem).

## 3 · Judge candidates
Candidate rows (produced by the pre-filter — activation/surprisal/dirty-marks):
```json
{"jtype": "edge_type", "subjects": ["prop-123", "claim-7"],
 "fields": {"evidence": "...", "claim": "...", "sibling_evidence": "..."},
 "caused_by": "evt-0042"}
```
```bash
python3 judge_harness.py judge --judge qwen-a --candidates candidates.jsonl
```
Outbox events:
```json
{"event": "judgment.emitted", "jtype": "edge_type", "subjects": ["prop-123","claim-7"],
 "label": "supports", "confidence": 0.91, "judge_id": "qwen3-8b@8f3a21c0#p1",
 "cal_version": "cal-1a2b3c4d5e6f", "context_hash": "…sha256…",
 "self_reported": false, "ts": "…", "caused_by": "evt-0042"}

{"event": "judgment.abstained", "prediction_set": ["supports","refines"],
 "order_disagreement": false, …}
```
For T2 panels, run the same candidates file through `qwen-a`, `gemma-a`,
`phi-a`; the Clojure consolidator (`promotable?` in `judges.clj`) does the
k-of-n family count and promotes or escalates.

## 4 · Bridge to Mnemosyne (Clojure ingestor sketch)
```clojure
(doseq [line (line-seq (io/reader "outbox.jsonl"))]
  (let [{:strs [event jtype subjects label confidence judge_id
                cal_version context_hash caused_by]} (json/parse-string line)]
    (case event
      "judgment.emitted"
      (j/emit-judgment! {:jtype (keyword jtype) :subjects subjects
                         :label (keyword label) :conf confidence
                         :judge-id judge_id :cal-version cal_version
                         :ctx-hash context_hash :caused-by caused_by})
      "judgment.abstained"
      (j/emit-abstention! {:jtype (keyword jtype) :subjects subjects
                           :judge-id judge_id :ctx-hash context_hash
                           :caused-by caused_by})
      nil)))
```
`:judgment/subject-key` is computed Clojure-side on ingest (don't try to match
Python and Clojure `hash` across the wire).

## 5 · Drift loop
Accepted-judgments export rows need `judgment_id`, `jtype`, `fields`, `label`:
```bash
python3 judge_harness.py anchor-sample --judge anchor \
  --accepted accepted.jsonl --rho 0.05
```
Feed `anchor_outbox.jsonl` to `record-anchor-check!`; the `quarantine-behavior`
in `judges.clj` does the rest (θ default 0.15, min-n 30), and `retract-cohort!`
is the red button.

## Known limits
- vLLM's echo/logprob surface varies across versions; if `echo=True` scoring
  misbehaves on your build, `--mode topk` is the fallback (approximate; auto-
  falls back to echo on first-token label collisions).
- `dedup_prop` is never order-swapped (the `subsumes` label is directional);
  present pairs in canonical sorted-id order upstream.
- Sequential calls; at your volumes this is fine, and batching is a 20-line
  asyncio change if it ever isn't.
- Network calls are untested in the sandbox that wrote this; the pure pipeline
  (hashing → prompt → scaling → gate) is what the self-test certifies.

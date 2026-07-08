# SPEC-01 · WP-0 — First live judge (Phase 0)

**Objective:** run the full pipeline on the owner's real Roam graph for the
first time, producing a **calibrated, conformally-gated `edge_type` judge**
(with `continues` as a cheap secondary) and a **metrics report** whose headline
number — the abstention rate — is the input to all Phase-2 tuning.

**Deliverables:** `first_judge.sh` (staged, idempotent runbook — reference
implementation provided), `judge_metrics.py` (report generator — reference
implementation provided, self-tested), `ops/first_judge/first_judge_report.{json,md}`,
and the frozen calibration artifacts.

**Non-goals:** consolidator deployment as a daemon (a single manual ingest
pass is an optional stage), panel operation across 3 families (single judge
first; the panel is Phase 2), any threshold tuning.

---

## 1 · Prerequisites (preflight checklist)

| # | Item | How to verify |
|---|---|---|
| P1 | Codebase restored, all self-tests green | SPEC-00 §5 regression command |
| P2 | vLLM serving the target judge with prefix caching | `vllm serve Qwen/Qwen3-8B --port 8000 --enable-prefix-caching`; `curl $BASE/models` |
| P3 | `judges_config.yaml` filled: real endpoints, **real weights hashes** in `judge_id` (hash the safetensors dir; the id is provenance, not decoration) | manual |
| P4 | Anchor access (API key or large local model) under the `anchor` entry | `--dry-run` then 1 paid smoke call |
| P5 | Fresh Roam export (JSON) of the full graph | file exists; record `sha256` |
| P6 | Budget sign-off for anchor labeling (see §4 cost model) | owner |

## 2 · Stage map (what `first_judge.sh` orchestrates)

Each stage writes a checkpoint marker `ops/first_judge/.stageN.done` and is
skipped when the marker exists; `--from N` forces re-entry; `--plan` prints the
resolved plan without executing. Stages:

```
0 preflight → 1 harvest → 2 anchor-label → 3 review (HUMAN GATE) →
4 merge-review → 5 freeze → 6 calibrate → 7 prefilter → 8 judge → 9 metrics
```

## 3 · Stage 1 — Harvest

```bash
python3 roam_harvest.py harvest --export "$EXPORT" --out-dir ops/first_judge/calib \
    --max-per-type 400 --min-refs 8 --seed 0
```
- **Target:** ≥ 300 `edge_type` candidates and ≥ 200 `continues` candidates
  (the demo graph of 13 pages yielded 18/27; a multi-year graph saturates).
- **Contingency if under target:** rerun with `--min-refs 5`; if `edge_type`
  is still thin, the graph lacks discourse-graph pages and shared-ref density —
  fall back to accepting a smaller calset (§6 floor: 150) and flag in the report.
- Inspect `harvest_stats.json`; attach to the report.

## 4 · Stage 2 — Anchor labeling

```bash
python3 anchor_label.py --candidates ops/first_judge/calib/candidates_edge_type.jsonl \
    --judge anchor --double --limit 350
python3 anchor_label.py --candidates ops/first_judge/calib/candidates_continues.jsonl \
    --judge anchor --double --limit 250
```
- **Cost model:** `--double` ⇒ 2 calls/candidate; prompt ≈ 1.2–2k tokens,
  completion ≈ 100 tokens. 600 candidates ⇒ ~1,200 calls ≈ 1.5–2.5M input
  tokens. Run a `--limit 25` pilot batch first and extrapolate before
  authorizing the rest (the script does this: stage 2 runs pilot → prints
  projected cost → interactive confirm unless `--yes`).
- **Expected outcomes** (report all): double-consistency rate (healthy: >80%;
  <60% ⇒ the label definitions are ambiguous for this corpus — STOP and review
  10 inconsistent items before spending more), flag rate, per-label balance
  (if any `edge_type` label has <8% share, harvest more of its mode — the
  `unrelated` seeds and cross-page-topical modes exist precisely to feed the
  minority labels).

## 5 · Stage 3 — Human review (the gate that cannot be automated)

Work `review_queue_edge_type.md` and `review_queue_continues.md`:
- For each item: read the fenced fields exactly as the judge will see them
  (NOT the original page — the judgment is about the fields), tick the correct
  gold, following the policy lines printed in the queue (precision-over-recall;
  dialogical-not-topical; the lost-qualifier doctrine).
- Transcribe resolutions to `ops/first_judge/review_resolved.jsonl`, one row per
  item: `{"jtype": "...", "fields": {…verbatim from the queue…}, "gold": "..."}`.
- **Budget:** cap the session at 60 minutes per type. If the queue is larger,
  resolve a random sample and leave the rest out of the calset (they are
  neither gold nor garbage — just unused).
- **Protocol rule:** the reviewer must NOT consult the anchor's verdicts before
  deciding (they're printed after the fields; fold the page or use two passes).
  Anchoring-bias here silently converts "human gold" into "anchor gold with
  extra steps."

## 6 · Stages 4–6 — Merge, freeze, calibrate

- **Merge:** `review_resolved.jsonl` rows are appended to the calset (the
  script does this; rows carry `"provenance": {"source": "human"}`).
- **Freeze:** write `ops/first_judge/FROZEN.sha256` (sha of each calset). From
  this moment the calsets are **measured against, never trained on**
  (`distill_judge.py`'s hash-bucket rule will additionally re-derive its own
  audit split; both freezes coexist deliberately).
- **Floor:** ≥ 300 rows per type preferred; 150 acceptable with a widened-q̂
  warning in the report; below 150 → do not calibrate, return to harvest.
- **Calibrate:**
```bash
python3 judge_harness.py calibrate --judge qwen-a --jtype edge_type \
    --calset ops/first_judge/calib/calset_edge_type.jsonl --alpha 0.05   # T2
python3 judge_harness.py calibrate --judge qwen-a --jtype continues \
    --calset ops/first_judge/calib/calset_continues.jsonl --alpha 0.10   # T1
```
- **Sanity bounds** (script asserts, report records): fitted `T ∈ [0.3, 8]`
  (outside ⇒ scoring path is broken — check echo mode against your vLLM
  version, fall back `--mode topk`); `q̂ ∈ (0, 0.9)` (q̂ ≥ 0.9 means the model
  is near-uninformative on this type — expect mass abstention, which is a
  finding, not a failure).

## 7 · Stages 7–8 — Prefilter and judge

```bash
python3 prefilter.py run --export "$EXPORT" --state ops/first_judge/pf_state.json \
    --out ops/first_judge/live_candidates.jsonl --min-refs 8 \
    --budget edge_type=120 --budget continues=80
python3 judge_harness.py judge --judge qwen-a \
    --candidates ops/first_judge/live_candidates.jsonl \
    --outbox ops/first_judge/outbox.jsonl
```
- The prefilter cold-start treats everything as dirty — budgets are raised for
  this one run to get **≥ 200 judgments attempted** (the statistical floor for
  a meaningful abstention estimate; binomial 95% CI at n=200 is ±~6 points).
- Wall-clock estimate: echo scoring = |labels| prefill calls per candidate;
  with prefix caching on a 3090 expect 1–3 s/candidate ⇒ 10–20 min for 400.

## 8 · Stage 9 — Metrics and decision gates

`judge_metrics.py` computes from the outbox (+ calibration store):

| Metric | Definition |
|---|---|
| abstention rate | `abstained / (emitted + abstained)`, per jtype |
| label distribution | over emitted, per jtype |
| confidence profile | deciles of `confidence` over emitted |
| prediction-set profile | size distribution over abstentions (2-label sets = near-misses; full-set = uninformative) |
| throughput | judgments/minute (from `ts` span) |

**Decision gates (the point of Phase 0):**

| Abstention (edge_type, α=0.05) | Reading | Action |
|---|---|---|
| < 10% | suspicious — check for calset↔live leakage (shared context hashes) and q̂ sanity | audit before celebrating |
| 10–35% | **healthy** | proceed to Phase 2 (panel + tuning) as-is |
| 35–60% | usable but expensive (escalation volume) | Phase 2 discusses α=0.10 for T2-with-panel, or a larger judge |
| > 60% | judge uninformative on this corpus | inspect 20 abstentions by hand: if prediction sets are mostly 2-label near-misses ⇒ recalibrate with more/better gold; if full-set ⇒ the model is too small for the type — try the 12B family before touching α |

The report must also state: double-consistency rate, human-review volume and
minutes spent, per-stage wall-clock, and anchor spend — these are the planning
constants for scaling to the remaining seven types.

## 9 · Optional stage 10 — Single consolidator pass (Clojure)

If a JVM is available: run one `mnemosyne.ingest` cycle over the outbox and
record promoted/escalated counts. **This is optional for M0** (the Clojure
side is hand-checked; standing it up is Phase-2 work) — but a successful pass
is the first execution evidence for `ingest.clj` and worth the hour.

## 10 · Failure modes & remedies

| Symptom | Likely cause | Remedy |
|---|---|---|
| echo scoring returns junk logprobs | vLLM version variance on `echo=True` | `--mode topk` (auto-falls back per-call on label collisions) |
| anchor JSON malformed | provider lacks `guided_json` | anchor via a vLLM-served large model, or add a repair-parse (WP-1a ships one; borrow it) |
| harvest yield ≪ target | sparse graph / few shared refs | `--min-refs 5`, accept 150-floor, flag |
| double-consistency < 60% | ambiguous label definitions for this corpus | STOP; review 10 inconsistents; possibly amend GUIDANCE (bump prompt_version ⇒ re-label pilot) |
| calibration `T` at bounds | broken scoring path | see §6 sanity bounds |

## 11 · Definition of Done (WP-0 / M0)

- [ ] Frozen calsets for `edge_type` (≥300 preferred / ≥150 floor) and
      `continues`, with recorded SHAs and human-review provenance rows.
- [ ] `calibration.json` entries for both types with α, T, q̂, cal_version
      inside sanity bounds (or a documented bound-violation finding).
- [ ] ≥ 200 live judgments attempted for `edge_type`.
- [ ] `first_judge_report.{json,md}` with every §8 metric, the decision-gate
      verdict, costs, and timings.
- [ ] All repository self-tests still green.
- [ ] The report reviewed with the graph owner; Phase-2 tuning ticket opened
      with the measured constants.

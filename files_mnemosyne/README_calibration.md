# Calibration loop — from a Roam export to a live `edge-type` judge

Closes the loop left open in `microjudge_contract.md` §9 step 2. Files:
`roam_harvest.py` (candidate miner) and `anchor_label.py` (gold labeling pack);
downstream consumers are `judge_harness.py` and the Clojure layer.

```
graph.json ──► roam_harvest.py harvest ──► candidates_{type}.jsonl
                                                  │
                              anchor_label.py (--double) ──► calset_{type}.jsonl   (FROZEN)
                                                  │                │
                                                  └► review_queue_{type}.md        │
                                                       (human spot-check)          ▼
                                              judge_harness.py calibrate ──► calibration.json
                                                                                   │
                       candidates (live, from pre-filter) ──► judge ──► outbox ──► Clojure
```

## 1 · Harvest
```bash
python3 roam_harvest.py demo                       # synthetic graph, sanity check
python3 roam_harvest.py harvest --export my-graph.json --out-dir calib \
    --max-per-type 400 --min-refs 8
```
What it mines (stdlib-only, lexical/structural by design — a calset *should*
mix trivial and hard cases, and the anchor sorts out the noise):

- **edge_type** — discourse-graph pages first (`CLM -`/`EVD -` title prefixes,
  the Roam discourse-graph convention), EVD→CLM pairs; then generic block
  pairs sharing ≥2 page-refs; plus zero-overlap pairs as `unrelated` seeds so
  every label is represented.
- **same_entity** — title pairs by similarity, containment, or **acronym
  match with French stopwords skipped** (catches RGPD ↔ Règlement Général sur
  la Protection des Données at string-sim 0.16); mid-similarity pairs included
  as probable negatives.
- **summarize_now** — per-page cluster digests (inbound refs, page spread,
  churn, samples); small clusters included as `defer`/`never` material.
- **invalidate** — parents whose children were edited *after* them (genuine
  staleness signal recoverable from a Roam export) + fresh parents as `keep`.
- **dedup_prop** — block pairs in similarity bands; emitted in canonical
  sorted-uid order (the `subsumes` label is directional — never swap).
- **propagate** — recently edited blocks × (sibling | co-referencing block).
- **faithful** — `>` quote blocks × paraphrase siblings. Sparse in most
  graphs; the propositionizer pipeline is the richer source for this type.

## 2 · Anchor-label (gold)
```bash
python3 anchor_label.py --candidates calib/candidates_edge_type.jsonl \
    --judge anchor --double
python3 anchor_label.py --candidates ... --dry-run --limit 2    # inspect, no API
```
Gold-quality design, in order of importance:
1. **Identical conditional** — the anchor judges the *same fenced fields* the
   small judges will see; otherwise calibration measures the wrong
   distribution.
2. **`--double` self-consistency** — every item labeled twice under different
   (salted) label orders; only order-consistent verdicts enter the calset.
   Inconsistents go to the review queue, not the trash.
3. **Policy-bearing guidance** — the contract's doctrines live in the prompts:
   precision-over-recall for `same_entity` (false merges corrupt silently),
   the lost-qualifier doctrine for `faithful` (a proposition that drops a
   scope/condition/exception is wrong even if literally true), refines ≠
   supports (scope vs credibility).
4. **Human gate** — `review_queue_{type}.md` collects: anchor-flagged items,
   order-inconsistent items, and *all hard-rated T2 items even when kept* —
   each with a `human gold: ____` checkbox. For T2 types, work the queue
   before freezing the calset.
5. **Provenance** — every gold row carries `anchor_judge_id` + context hash +
   timestamp, so the Clojure `training-admissible?` check holds by
   construction, and the calset itself is auditable.

**Freeze rule:** once `calset_{type}.jsonl` feeds `calibrate`, it is frozen —
measured against, never trained on (contract §7).

## 3 · Calibrate & go live
```bash
python3 judge_harness.py calibrate --judge qwen-a --jtype edge_type \
    --calset calib/calset_edge_type.jsonl --alpha 0.05      # T2 ⇒ α=0.05
python3 judge_harness.py judge --judge qwen-a --candidates live_candidates.jsonl
```

## Honest limits
- Roam exports carry **no edit history**, so `propagate` candidates frame the
  current text as the change; the operative judgment (does this content
  materially bear on the neighbor?) survives, the before/after delta does not.
  Once Mnemosyne's own event log runs, harvest `propagate` from real deltas.
- Lexical harvesting under-samples *semantically* similar but lexically
  distant pairs; when the embedding layer (regime B) is live, add kNN-mined
  candidates — keep the lexical ones, the mix is the point.
- Volume check: the contract wants ≥~300 examples/type. A small demo graph
  yields a handful; a multi-year graph at `--max-per-type 400` will saturate
  most types except `faithful` (top up from the propositionizer) and possibly
  `same_entity` (lower the similarity floor before lowering the precision
  policy).
- Anchor labels are still model labels: the human queue is the calset's
  actual quality floor for T2. Budget the half-hour.

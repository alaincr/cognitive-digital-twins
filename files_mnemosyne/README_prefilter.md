# Pre-filter — the formal layer that decides WHEN

`prefilter.py` closes the last gap in the live loop (roadmap step 8): the
judges never scan the corpus; they see only what this layer nominates, on a
budget, with cooldowns.

```
graph snapshot ──► dirty marks + novel co-refs + threshold crossings
                       │  priority = recency × structure (+ dreamer boost)
                       ▼
              per-type budgets ─► content-hash debounce ─► live_candidates.jsonl
                                                                 │
                              judge_harness.py judge  ◄──────────┘
                              (×3 families) ─► ops/outbox.jsonl ─► consolidator
```

## Run it

```bash
python3 prefilter.py self-test          # 12-assertion emit→debounce→targeted scenario
python3 prefilter.py run --export my-graph.json \
    --state ops/prefilter_state.json --out ops/live_candidates.jsonl \
    --min-refs 8 --cooldown-days 7 \
    --surprisal-file dreamer_scores.jsonl \
    --budget edge_type=30 --budget continues=20
```

Cron it alongside the judge runner (every few minutes to hourly); the
consolidator cadence is independent.

## What nominates a candidate

| Trigger | Types fed | Mechanism |
|---|---|---|
| dirty block (edit/create ≥ watermark) | edge_type, propagate, invalidate, dedup_prop | dirty-seeded variants of the harvest builders |
| new page title | same_entity | similarity / containment / acronym vs existing titles |
| new block | continues | previous sibling, else parent bullet, proposes itself as predecessor |
| ref-count threshold crossing | summarize_now | per-page counts stored in state; fires exactly at the crossing |
| novel co-reference (two pages meeting for the first time in one block) | priority boost + `meta.novel_copair` | bounded hash-set of seen pairs — the cheap structural-surprisal proxy |
| dreamer export (`--surprisal-file`, JSONL `{uid, score}`) | priority boost | integration hook for the existing Roam dreamer — not a reimplementation |

`permanent_worthy` is deliberately absent: it is a project-harvest flow
(branch merge), not a live trigger.

## Guarantees (self-tested)

- **Budgeted**: per-type caps, highest priority first; unspent budget is not
  banked (a steady trickle schedules better for T2 panels than bursts).
- **Debounced**: a (jtype, subjects) key with an *unchanged fields-hash* is
  not re-emitted inside the cooldown window. Identical context ⇒ identical
  verdict (harness determinism), so re-judging it is pure waste; changed
  content re-emits immediately.
- **Idempotent / restart-safe**: `state.json` (atomic replace) holds the
  watermark, cooldown map (pruned to a 4×cooldown horizon), per-page ref
  counts, and the bounded ref-pair set (cap 50k).
- **Cheap**: structure + string similarity only; zero model calls, zero
  embeddings.

## Honest limits

- Today's graph source is a **Roam export snapshot**; dirty detection rides on
  edit/create times, so intra-day multiple edits collapse into one dirty mark
  and true before/after deltas are unavailable (same caveat as the harvest's
  `propagate`). In the full deployment the identical nomination logic runs
  against the Mnemosyne **event log** where dirty = new events — the seams are
  marked `GRAPH-SOURCE` in the code.
- `continues` proposals are structural (sibling/parent); kNN parent proposals
  arrive with the embedding layer and should be *added*, not substituted.
- Priority is a heuristic (recency × inbound-ref structure + boosts), not a
  learned policy; the contract's `summarize_now`-style *judges* remain the
  arbiters of WHAT — this layer only rations WHEN.

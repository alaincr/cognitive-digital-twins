# README — B5 embedding / similarity layer (`embed_index.py`)

Brick **B5** (gap G5 of `prd/00_gap_analysis.md`). Populates the rung-B
similarity substrate that `morning-dialog`/bridges, `continues` candidates, and
the regime ladder all presuppose. Normative spec: `prd/PRD_B5_embedding_layer.md`
+ `prd/annexes/ANNEX_B5_embedding_layer.md`. File contracts: `prd/annexes/INTERFACES.md`.

## What it produces / consumes

Consumes (INTERFACES.md §2):
- `sync/snapshots/<ts>.json.gz` / `latest.json` — Roam "Export All" snapshot (B1).
- `sync/deltas/<ts>.delta.jsonl` — B1 delta (`op ∈ added|edited|removed|moved`).

Produces:
- `store/embeddings.db` — SQLite vector store (durable state).
- `sim/sim_pairs.jsonl` — `{a, b, score, model_rev, cycle}`, `a<b`, leading meta line.
- `sim/continues_candidates.jsonl` — full `continues` candidate rows (kNN parents).
- `sim/bridge_seeds.jsonl` — the cross-page subset of `sim_pairs`.

## Pinned model / revision (discipline == judge_id)

| Field | Value |
|---|---|
| model | `intfloat/multilingual-e5-small` (dim 384, CPU, multilingual FR/IT/EN) |
| `REV` | `fd1525a9fd15763a4a9e4ae4c8a1e6f2c1f3f2ab` (Hugging Face commit, pinned in `embed_index.py`) |
| `model_rev` | `e5-small@fd1525a9` (`"e5-small@" + REV[:8]`) |
| prefix | `passage:` for indexing and pairs; `query:` only for the `query` subcommand |

`model_rev` is journaled into `meta` at store init and stamped on **every**
output row. This is the same identity discipline as `judge_id`
(`model@weights#version`): revs from different models are never mixed.

### model_rev discipline (edge case 3)

The store holds **one** active `model_rev`. Opening a store whose
`meta.model_rev` differs from the code's `model_rev()` **without `--full`** is a
fatal error (a heterogeneous index is forbidden). To change the model:

1. Bump `REV` (and, if the family changes, `MODEL_ID`) in `embed_index.py`.
2. Re-run `embed_index.py update --full …` — this wipes the store and rebuilds
   every encodeable block against the new model. Old pair files stay valid
   (they carry the old `model_rev`); new pairs carry the new one. The two never
   mingle downstream.

## The 30-minute one-time init (owner's Mac, in daylight)

Per ANNEX_B5 §7, the full initial index runs **once**, by hand, on the owner's
machine; the nightly cycle only ever encodes the delta.

```bash
# one-time, ~30 min CPU on ~50k blocks:
python3 embed_index.py update \
    --snapshot sync/latest.json \
    --delta    sync/deltas/<first>.delta.jsonl \
    --db       store/embeddings.db
```

The first B1 delta carries `{"meta":"initial-import"}` and marks all blocks
`added`, so the first `update` encodes the whole encodeable corpus. Encoding is
batched (256) with a DB checkpoint every 2000 blocks (edge case 4): if it dies,
re-run — already-encoded blocks are content-address skipped, not re-encoded.

Real path deps (`sentence-transformers` + `torch`, CPU) are **lazy-imported**
inside `real_encoder()` — installed once for this init and the nightly cycle,
never touched by `self-test`. Sanity-check recall after init:

```bash
python3 embed_index.py slow-test   # @slow: real e5, asserts ≥18/20 planted twins in top-5
```

## Nightly cycle usage

```bash
# 1. encode the delta (≤ ~2 min incremental)
python3 embed_index.py update --snapshot sync/latest.json \
    --delta sync/deltas/<ts>.delta.jsonl --db store/embeddings.db

# 2. similarity pairs for the cycle's changed uids (+ bridge seeds in one pass)
python3 embed_index.py pairs --db store/embeddings.db \
    --changed-uids ops/cycles/<ts>/changed_uids.txt \
    --out sim/sim_pairs.jsonl --bridge-out sim/bridge_seeds.jsonl --cycle <ts>

# 3. continues candidates for the cycle's NEW (op=added) uids
python3 embed_index.py continues-candidates --snapshot sync/latest.json \
    --db store/embeddings.db --new-uids ops/cycles/<ts>/new_uids.txt \
    --out sim/continues_candidates.jsonl
```

`changed_uids.txt` = the `added`+`edited` uids of the delta; `new_uids.txt` =
the `op=added` uids only. `continues_candidates` merges into the prefilter's
existing `continues` budget/debounce — B5 has **no** debounce of its own.

## Scores, thresholds, and the tuning note

- Default `--min-score` is **0.80** (config, not baked). Pairs above it are
  emitted; `continues` uses the same default and keeps only top-3 older neighbors.
- The 0.80 threshold is **provisional** for FR/legal text. The DoD report should
  print the score distribution and the **0.75 and 0.85 quantiles** so phase-2
  tuning has real numbers (ANNEX_B5 §7). A true duplicate scores ~1.0 and is a
  prime `dedup_prop` seed — never filter it (edge case 2).
- Search is brute-force numpy over an in-memory matrix (50k × 384 × 4 ≈ 74 MB).
  FAISS is a deliberate **non-need** at this scale (PRD_B5 §8) — not a gap.

## stdlib-first derogation justification (SPEC-00 §3.1)

`embed_index.py` uses `numpy` (eager) for the cosine matrix and, on the **real
path only**, `sentence-transformers` + `torch` (CPU) for the e5 encoder. A
pure-stdlib dot product over 50k × 384 float32 would be minutes per cycle where
numpy is milliseconds, and re-implementing a multilingual transformer encoder in
stdlib is not viable. Both fall under the same "allowed heavy dep, lazy-imported"
carve-out SPEC-00 already grants the training paths. The heavy imports are lazy
(the §3.2 seam): they never load on `self-test`, which uses `mock_encode`
(deterministic sha256-derived normalized float32 vectors) and asserts
`"torch" not in sys.modules` at the end — mirroring `distill_judge.py`.

## Test surface

- `python3 embed_index.py self-test` — pure logic, mock only, zero network/GPU,
  no torch. Covers: incremental re-run encodes 0 (M1), M/* exclusion, sub-30-char
  eviction (edge 1), duplicate → score 1.0 (edge 2), `a<b` ordering + meta line,
  cross-page-only bridge seeds, `model_rev` fatal without `--full` (edge 3), and
  `continues` candidate keys == `judge_prompts.REQUIRED_FIELDS["continues"]`
  (registry anti-drift).
- `python3 embed_index.py slow-test` — `@slow`, real model, M2 recall (≥18/20).
- Fixtures under `fixtures/embed/`: `mini_corpus_fr.json` (40 FR blocks, 10
  planted near-dup pairs) for M2; `selftest_snapshot_{1,2}.json` +
  `selftest_delta_{1,2}.jsonl` for the mock self-test.
```

# Mnemosyne micro-judge service — operations runbook

The running system is four processes plus one cron-grade pass, sharing one
directory (`ops/`) of append-only JSONL files and one event-log snapshot.

```
[vLLM servers]            [judge runner]                [consolidator (Clojure)]
machine-b :8000/8001  ◄── judge_harness.py judge   ──►  ops/outbox.jsonl ──► ingest!
machine-a :8000           (loop / cron over             ops/contexts.jsonl     │
(--enable-prefix-caching)  pre-filter candidates)                              ▼
                                                        consolidate! ─► domain facts
[anchor pass]                                               │               (event log)
judge_harness.py judge --judge anchor  ◄── ops/escalations.jsonl
judge_harness.py anchor-sample         ──► ops/anchor_outbox.jsonl ──► ingest!
                                       ◄── ops/accepted.jsonl
```

## Processes & cadences

| Process | What | Cadence |
|---|---|---|
| vLLM servers | the judge fleet + (optionally local) anchor | always on; `--enable-prefix-caching` |
| judge runner | `judge --judge qwen-a --candidates … --outbox ops/outbox.jsonl` (×3 judges for T2 panels) | continuous loop or every few minutes, driven by the pre-filter |
| **consolidator** | `clojure -M -m mnemosyne.ingest ops` — tails outboxes, ingests, promotes, exports, runs quarantine, snapshots the log | every ~5s (built-in loop) |
| anchor escalation pass | answer `ops/escalations.jsonl` (snippet below) | every few hours / daily |
| anchor sampling | `anchor-sample --accepted ops/accepted.jsonl --contexts ops/contexts.jsonl --rho 0.05 --outbox ops/anchor_outbox.jsonl` | daily |

## The escalation round-trip

Escalation rows are fields-free (`jtype`, `subjects`, `context_hash`); join
them with the context store and feed the anchor as an ordinary judge — its
verdicts return through the same outbox and **anchor supremacy** in the
consolidator promotes them directly:

```bash
python3 - <<'EOF'
import json, pathlib
from judge_harness import load_contexts
ctx = load_contexts(pathlib.Path("ops/contexts.jsonl"))
with open("ops/escalation_candidates.jsonl", "w") as out:
    for line in pathlib.Path("ops/escalations.jsonl").read_text().splitlines():
        if not line.strip(): continue
        e = json.loads(line)
        c = ctx.get(e["context_hash"])
        if c:
            out.write(json.dumps({"jtype": e["jtype"], "subjects": e["subjects"],
                                  "fields": c["fields"]}, ensure_ascii=False) + "\n")
EOF
python3 judge_harness.py judge --judge anchor \
    --candidates ops/escalation_candidates.jsonl --outbox ops/outbox.jsonl
```

## Correctness properties (and where they live)

- **Single writer per subject-key** — by construction: the consolidator is one
  single-threaded loop; only it promotes. Judges emit concurrently from
  anywhere (monotone side).
- **Idempotent ingestion** — re-reading an outbox line is a no-op: judgments
  are skipped when the same (judge, context-hash, label) already exists, and
  per-file `*.offset` markers survive restarts. Deleting an offset file
  forces safe re-ingestion.
- **UTF-8-safe tailing** — the tailer reads raw bytes and decodes UTF-8,
  consuming only complete lines (`RandomAccessFile.readLine` would garble
  accented French; partial trailing lines wait for the next cycle).
- **Order-sensitive subjects** — judgments carry `:judgment/subjects-vec`
  (ordered) alongside the unordered ref set; `edge-type`, `dedup-prop`
  (`subsumes` is directional) and `faithful` promotions read the vector.
- **Everything promoted is cohort-retractable** — every asserted fact entity
  carries `:prov/from-judgment`; attribute flips (stale-marks, faithfulness
  gates) ride next to a prov-linked mark node so `retract-cohort!` can find
  and undo them.

## What promotion asserts (the domain-fact table)

| (type, label) | Asserted |
|---|---|
| edge-type → supports/opposes/refines | reified `:discourse-edge` (feeds the belief fixpoint) |
| edge-type → unrelated | nothing (judgment accepted, question closed) |
| same-entity → same | retractable `:same-as` edge, canonical order — never a merge |
| summarize-now → fire / never | open `:summarize-task` / `:never-summarize` policy flag |
| propagate → propagate | bounded `reconsider` task on the neighbor |
| invalidate → invalidate | prov-linked stale-mark + `:derived/stale? true` |
| dedup-prop → duplicate / subsumes | `:duplicate-of` (canonical) / `:subsumes` (presented order) |
| faithful → faithful | `:prop/faithful? true` eligibility gate |
| faithful → lost-qualifier/unsupported | violation flag + re-propositionize task (linter pattern) |

## Failure modes & honest limits

- **Persistence is an EDN snapshot** of the in-memory event log, written each
  cycle. Crash between cycles loses at most one cycle of *derived* state —
  and nothing of the inputs, since outboxes are the durable record and
  re-ingestion is idempotent. The real fix remains swapping L3 to XTDB
  (contract upgrade path); this snapshot is the bridge, not the destination.
- The escalation file can accumulate rows whose subject was later resolved by
  a panel; the anchor pass re-judging them is wasted-but-harmless work
  (idempotency absorbs the duplicate verdict).
- The Clojure side remains hand-checked, not executed here; the Python side
  (context store round-trip, UTF-8, dedupe, fields-free join) is test-covered.
- One judge runner per judge identity: the in-process context-store dedupe is
  per-process, and duplicate context lines across processes are harmless
  (first-wins on load).

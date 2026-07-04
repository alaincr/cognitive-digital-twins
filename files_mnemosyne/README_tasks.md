# B3 — Human elaboration surface (`task_gen.py` + `task_harvest.py`)

Brick **G3** of `prd/00_gap_analysis.md`. This is the human-learning loop: the
system installs friction "exactly where it constitutes learning"
(`zettel_addendum.md` §6), and the owner's answers become the priority training
gold (`:source/family :human`). Without B3 the system can judge but never learn
from its owner.

The surface **is Roam** — there is no separate UI. B2 writes tasks into Roam,
the owner answers there, and the next cycle harvests those answers back.

## Modules

| File | Role |
|---|---|
| `task_gen.py` | reads causes (edges×stances / triage.due / bridge / review queue), builds `kind:task` orders, prioritises under a budget, appends to `writeback_orders.jsonl` |
| `task_harvest.py` | parses the day's Roam snapshot, detects answers, emits `human.response*` events into `outbox_human.jsonl` |
| `human_prompts.py` | registers the `bridge_related` jtype (`{related, unrelated}`) — types the human bridge event; **no automatic judge** |
| `calset_merge.py` | reusable `merge_review_resolved()` extracted from `first_judge.sh` stage 4 (review gold → calset, `provenance.source="human"`) |
| `fixtures/tasks/` | `snapshot_tasks.json` (8 task cases) + `harvest_ledger_prior.jsonl` |

## The four task types

| type | cause (upstream) | Roam answer |
|---|---|---|
| `elaborate` | a promoted `opposes` edge attacks a claim that still has IN supporters (cross `edges.jsonl` × `stances.jsonl`), or a `contradiction` cause row | free text, 2–3 sentences |
| `triage` | a fleeting note whose activation decayed (`triage.due` cause) | one closed tag: `#promouvoir` / `#garder` / `#archiver` |
| `bridge` | an embedding-close cross-train pair with no short path (`bridge` cause / `bridge_seeds.jsonl` from B5) | one closed tag: `#related` / `#unrelated` |
| `review` | a T2 / order-inconsistent item from `anchor_label.py`'s `review_queue_<jtype>.md` | one tag = the gold enum label of the reviewed jtype |

Bridge **fails closed**: with B5 absent (no seeds, no cause rows) zero bridge
tasks are generated. Documented, non-blocking.

## Roam format (written by B2 as `task_v1`, fields supplied by `task_gen`)

```
[[M/Task]] {question in French}
  task-type:: elaborate|triage|bridge|review
  task-id:: sha256:…            ← idempotency key
  status:: open
  due-hint:: [[July 6th, 2026]] ← today + 2 days
  refs:: ((uid-a)) ((uid-b))    ← subjects, for backlinks
  ↳ (preformatted child) "Réponse :"           for elaborate (free text)
    or "Choix (un tag) : #promouvoir #garder #archiver"   for triage
    or "Choix (un tag) : #related #unrelated"             for bridge
    or "Label or (un tag) : #supports #opposes …"         for review
```

Question language is **French** (the owner's language). Enum **labels stay
English** for calset consistency — imported from `judge_prompts.LABEL_DEFS`,
never copied.

### `task-id = sha256(task_type + ctx_cause)` — keyed on the CAUSE, not content

This guarantees:
- **M3 (no duplicates):** the same cause never produces two tasks.
- **No re-fire after expiry:** an expired task is regenerated only if the
  cause genuinely re-triggers.

`ctx_cause` identities: `elaborate|{claim}|{opposer}`, `triage|{uid}`,
`bridge|{sorted a,b}` (symmetric), `review|{jtype}|{context_hash}`.

## Harvest rules (`detect_response`, pure)

Walks the snapshot via `roam_harvest.Graph` (the parser is **imported**, not
re-implemented). For each `[[M/Task]]` block:

1. **Text** (elaborate): first descendant whose string, after stripping a
   `Réponse :` prefix, is non-empty and ≠ `?`. Edge case 4 (PRD §6): free text
   added directly under the task block, with **no** prefix, also counts (least
   astonishment). Empty or `?` → nothing emitted, task stays open.
2. **Choice** (triage/bridge/review): a closed tag from the task-type's allowed
   set, found on the task block or a descendant. The preformatted menu line
   (`Choix …` / `Label or …`) is ignored. **Two contradictory tags → ambiguous**
   (`human.response.ambiguous`, re-signalled in the digest, nothing routed).
3. **Amended:** the task-id was harvested before (`harvest_ledger.jsonl`) with a
   **different** `response_hash` → `human.response.amended`. Events are
   immutable; the consolidator supersedes, never rewrites.
4. **Deleted:** a task in the ledger but absent from the snapshot is treated as
   `expired`; never regenerated except by a new cause.

Re-harvesting is idempotent: an unchanged response (same `response_hash` as the
ledger) re-emits nothing.

### Emitted event (`outbox_human.jsonl`, INTERFACES.md)

```json
{"event":"human.response","task_id":"sha256:…","task_type":"elaborate",
 "response_text":"…","choice":null,"response_hash":"sha256:…",
 "answered_ts":1783…,"provenance":{"source":"human"}}
```

`event` is one of `human.response`, `human.response.amended`,
`human.response.ambiguous`. **Every** event carries `provenance:{source:"human"}`
(M2). The harvest **emits, it never routes** — routing is the consolidator's job
(FR-3), preserving the CALM split (harvest = monotone; effects = single writer).

## Prioritisation & anti-fatigue

`prioritize()` (pure) ranks by **`priority = stakes × activation`**:
- stakes = tier of the cause jtype (`T2=3, T1=2, T0=1`, mirroring
  `judges.clj`): elaborate→T2, triage→T1, bridge→T0, review→tier of the
  reviewed jtype; activation = `:prop/activation` from the event, else `1.0`.
- Budgets: global (default 5) **and** per type (`2 elaborate, 1 triage,
  1 bridge, 1 review`) — elaboration is cognitively costly, don't drown it.
- **No silent caps:** everything cut is returned in `dropped` (task-id,
  priority, reason) and logged to stderr.

Anti-fatigue is a **persisted** state, not a recompute:
`taskgen_state.json {"budget_factor": 1.0|0.5, "since": …}`. When the trailing
7-day response rate drops below 50 %, the factor halves (both budgets, floored
at 1 so one high-value task still gets through); it restores to 1.0 after
7 days back at ≥50 %. `task_harvest.py stats --window 7d` computes the rate
(distinct answered / distinct generated within the window) from
`harvest_ledger.jsonl` + `taskgen_ledger.jsonl` and suggests the next factor.

## Where answers go (routing, implemented in B4 — specified here)

| type | consolidator effect |
|---|---|
| `elaborate` | new proposition `:source/family :human`, linked to the task subjects; admissible for distillation |
| `triage #promouvoir` | candidate passes the `permanent_worthy` gate with the human as gold judge |
| `triage #archiver` | activation frozen, note leaves the triage stock (never deleted) |
| `bridge #related` | human `bridge_related` verdict appended; candidate edge promoted |
| `review` | `{jtype, fields, gold}` line appended to `review_resolved.jsonl` → **`calset_merge.merge_review_resolved()`** folds it into `calset_<jtype>.jsonl` |

`calset_merge.py` extracts the `first_judge.sh` stage-4 merge into a shared,
self-tested function. `first_judge.sh` is **not edited** (another concern owns
shell files); it could later call:

```bash
python3 calset_merge.py merge --review-resolved $WORK/review_resolved.jsonl --calset-dir $CAL
```

## CLI

```
python3 task_gen.py generate --causes $C/task_causes.jsonl \
    --edges ops/edges.jsonl --stances $C/stances.jsonl \
    --bridge-seeds sim/bridge_seeds.jsonl \
    --review-queues 'ops/first_judge/review_queue_*.md' \
    --out-append $C/writeback_orders.jsonl --state ops/taskgen_state.json \
    --ledger ops/taskgen_ledger.jsonl --budget 5
python3 task_gen.py self-test

python3 task_harvest.py harvest --snapshot sync/snapshots/latest.json \
    --out $C/outbox_human.jsonl --ledger ops/harvest_ledger.jsonl
python3 task_harvest.py stats --window 7d \
    --ledger ops/harvest_ledger.jsonl --taskgen-ledger ops/taskgen_ledger.jsonl
python3 task_harvest.py self-test
```

## Tests

All four modules ship a `self-test` (zero network). `task_harvest.py self-test`
runs 24 assertions over the 8 fixture cases in `fixtures/tasks/snapshot_tasks.json`
(answered-text, answered-tag, double-tag, empty, `?`, amended-across-2-snapshots,
answered-in-question-block, deleted-present-in-ledger-absent-in-snapshot).

```
python3 -m py_compile task_gen.py task_harvest.py human_prompts.py calset_merge.py
python3 task_gen.py self-test
python3 task_harvest.py self-test
python3 human_prompts.py self-test
python3 calset_merge.py self-test
```

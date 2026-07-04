# README — `roam_writeback.py` (B2, Roam write-back)

B2 is the only component that writes into Roam. It closes the Mnemosyne loop on
the human side: it projects the consolidator's promoted facts into Roam's
reserved `M/*` namespace — **append-only**, **idempotent**, **budgeted**, and
**neutralised**. It decides nothing; it consumes `$C/writeback_orders.jsonl`
(produced by B4/B3) and executes it, recording every write in
`ops/writeback_ledger.jsonl`.

```
$C/writeback_orders.jsonl ──► plan() (PURE) ──► apply() ──► Roam M/*
                                                     │
                                                     └──► ops/writeback_ledger.jsonl
```

## CLI

```
python3 roam_writeback.py apply  --orders writeback_orders.jsonl [--dry-run]
                                 [--max-writes 200] [--date 2026-07-04]
                                 [--quarantine <judge_id-substring> ...]
                                 [--base-url … --graph … --token … --rate 300]
                                 [--ledger ops/writeback_ledger.jsonl] [--cycle …]
python3 roam_writeback.py verify --orders writeback_orders.jsonl  <transport flags>
python3 roam_writeback.py self-test        # mocked transport, ZERO network
```

`--dry-run` prints the exact block rendering (parent + children, with generated
uids) and writes nothing — no transport is constructed. Transport credentials
default to `ROAM_BASE_URL` / `ROAM_GRAPH` / `ROAM_TOKEN` env vars.

Exit codes: `apply` returns non-zero when the individual-write failure rate
exceeds 5 % (per-write failures are logged and never abort the batch). A
transport-unavailable condition aborts the run cleanly (see resume below) and is
not counted as a failure-rate error.

## Template registry (v1)

Each `content.template` in an order maps to a **pure** renderer
`fields -> list[str]` where the first string is the parent block and the rest
are children. Skeletons are literal; only *cited* field content is passed
through `neutralize()`.

| template | kind | parent line | key fields |
|---|---|---|---|
| `judgment_v1` | judgment | `[[M/J]] ((src)) {label} ((dst)) — conf {c:.2f}` | `src_uid, dst_uid, label, confidence, jtype, ctx, judge_id, cycle_date` |
| `flag_v1` | flag | `[[M/Flag]] {shape_id} {shape_name} — ((focus))` | `shape_id, shape_name, focus_uid, severity, ctx, message` |
| `stance_v1` | stance | `[[M/Stance]] ((node)) : {old} → {new}` | `node_uid, old_status, new_status, n_supporters, ctx, cycle_date` |
| `task_v1` | task | `[[M/Task]] {{[[TODO]]}} {title}` | shape owned by B3; B2 renders fields as-is |
| `digest_v1` | digest | `#[[M/Digest]] [[date]] — n judgments, n flags, …` | `cycle_date, n_*, notes[]` |
| `seed_v1` | seed | `[[M/Eval/Seed]] {label}` | eval seeds; allowlist `M/Eval/*`, out of budget |

Rules baked into the renderers:
- **`continues` is directional child→parent and never inverted.** The order file
  is already canonical (`src_uid` = child, `dst_uid` = parent); B2 renders
  `((child)) continues ((parent))` verbatim.
- **`focusNode` extraction.** `flag_v1` accepts `urn:mnemo:node:<uid>` and
  extracts the uid for a `((ref))`. A synthetic (non-uid) focus is written as
  neutralised raw text — **never** a `((ref))`.
- **snake_case only.** Nothing here ever emits a Clojure `:edge-type` hyphen
  form; order fields are Python-side (snake_case) by contract.
- **`ref_dangling:: true`** is appended to a judgment when the upstream marks a
  source uid as deleted between promotion and write (PRD edge case 2) — a dead
  `((ref))` is a signal, not an error.

### `neutralize(s)` (injection defence)

Applied to every *cited* string, never to template skeletons. Inserts a
zero-width space after the first char of each active opener so the text still
reads but cannot forge a ref/attribute/query:

`[[` → `[​[`, `((` → `(​(`, `::` → `:​:`, `{{` → `{​{`
(covers `#[[` via the `[[` rule and `{{[[TODO]]}}` via `{{`+`[[`), then truncates
to 1800 chars (Roam's practical block ceiling is ~2000).

### `roam_date(d)`

Formats a date/ISO-string as a Roam daily-note title: `July 4th, 2026`, with
correct ordinal suffixes (1st, 2nd, 3rd, 4th, 11th–13th, 21st, 22nd, 23rd,
31st). Used to allowlist and target today's daily note.

## Allowlist rule (FR-4, defence in depth against an upstream B4 bug)

`plan()` refuses any order whose target page is not:
- a page under `M/` (e.g. `M/Journal/2026-07`, `M/Flags`, `M/Tasks`,
  `M/Stances`), **or**
- **today's** daily note (the `roam_date` of `--date`, default today UTC).

The eval `seed` kind additionally may target `M/Eval/*`. Everything else — a
stray `[[Scaffolding]]`, `[[Glossary]]`, or any user page — is recorded as an
`allowlist-refusal` and never written. Refusals are printed to stderr.

## Priority, budget, idempotence (all in the pure `plan()`)

- **Priority sort:** `task > flag > stance > judgment`. The single `digest`
  floats to the end as the cycle summary; `seed` is lowest and out of budget.
- **Budget (`--max-writes`, default 200):** writable actions are capped;
  overflow is truncated **by priority** (judgments dropped before stances,
  before flags, before tasks) and the dropped counts are reported into the
  digest's `notes` (so the truncation is visible in Roam). Eval `seed`s do not
  count against the budget.
- **Idempotence:** the order's `idempotency_key` is the content address.
  - dup key + **same** rendered content → a single write.
  - dup key + **different** content → `FatalPlanError` (upstream B4 bug; B2
    refuses to guess — PRD edge case 3).
- **Quarantine (`--quarantine`):** judgments from a quarantined judge (matched
  by `judge_id` substring) are withheld; retraction/flag counterparts still
  write (FR-4).

## Ledger and resume

`ops/writeback_ledger.jsonl` is **append-only**, one row per key:

```json
{"key":"sha256:…","kind":"judgment","block_uid":"aB9xK2mQ1",
 "page":"M/Journal/2026-07","ts":"2026-07-04T02:14:00Z",
 "cycle":"2026-07-04T0200Z","status":"written|failed|verified"}
```

Loaded into a `key → latest-row` dict at start. On (re)plan, any key whose
latest status is `written` or `verified` is **skipped** — this is what makes a
full re-run of the same orders write zero new blocks.

**Mid-file resume (PRD edge case 4).** A per-write failure is logged and the
batch continues (`status: failed`, later re-planned). But a *transport-
unavailable* condition (graph unreachable) raises `TransportUnavailable`, which
**aborts the run** — the in-flight and remaining orders get no ledger row, so
the next cycle re-plans exactly them. In the self-test: a transport that goes
down at call 6/12 leaves 5 `written`; re-apply plans and writes exactly the 7
remaining, for 12 total with no duplicates.

**`verify`** pulls the `block_uid`s recorded for the cycle, confirms each is
present in Roam, and promotes `written → verified`. It never edits a block.

## Append-only retraction / resolution (FR-5, FR-4)

Cohort retraction and flag resolution are **child blocks**, never edits:
- FR-5 retraction: append `status:: retracted` + `retraction:: ((journal-ref))`
  under the affected judgment block.
- FR-4 flag resolution: append `status:: resolved` under the flag block when the
  linter no longer re-detects it.

`add_child()` implements this. There is **no `update-block` in v0** — the
bitemporal history must stay readable in Roam too (ANNEX §9).

## Transport (injected seam)

`Transport` (real) uses stdlib `urllib` against
`POST /api/graph/{graph}/write` with `batch-actions` in lots of ≤ 25, a
client-side rate limit (`--rate`, default 300 writes/min), and exponential
backoff on 429/307/5xx. **We generate our own 9-char uids** (`[a-zA-Z0-9_-]`)
at write time and record them in the ledger — that is what makes `verify` and
child-block appends possible without a full-text re-query. The `self-test`
injects a `MockTransport` and touches no network.

## Design decision: monthly `M/Journal/YYYY-MM` pages (ANNEX §9)

`M/Journal` is written as **monthly pages** (`M/Journal/2026-07`) from v0, not a
single ever-growing page. A single Roam page of thousands of blocks becomes
painful to open and navigate; monthly rollover keeps each page tractable while
the `M/` prefix in the allowlist accepts every sub-page uniformly. Daily cycle
entries live under a dated block within that month's page; the one-line
`#[[M/Digest]]` still lands on the actual daily note for at-a-glance backlinks.

## Fixtures (`fixtures/writeback/`)

| file | purpose |
|---|---|
| `orders_nominal.jsonl` | 12 orders, all kinds + digest, two cycles |
| `orders_dup_key.jsonl` | same key twice (1 write) then same key different content (fatal) — rows tagged `_case` |
| `orders_hostile.jsonl` | cited content with `[[`, `((`, `::`, `{{`, `#[[`, `{{[[TODO]]}}` |
| `orders_overbudget.jsonl` | 250 orders (mixed priority) + digest → truncation |
| `orders_bad_target.jsonl` | targets `[[Scaffolding]]` / `[[Glossary]]` → allowlist refusal |
| `orders_resume.jsonl` | 12 distinct orders for the fail-at-6 resume scenario |

## Definition of Done

```
python3 -m py_compile roam_writeback.py
python3 roam_writeback.py self-test      # both exit 0
```

The self-test (all mocked, zero network) covers: the 5+1 template renderers,
`neutralize` on the hostile fixture, `roam_date` ordinals, `plan` idempotence
(same/different content), allowlist refusal, over-budget truncation with a
digest note, nominal apply + verify round-trip, and the mid-file resume.

# README_eval — `eval_harness.py` (brick B7, gap G7)

Task-level evaluation of the reduced Mnemosyne loop. `judge_metrics.py` measures
the *judge*; B7 measures the *system* — does the promoted substrate beat "a folder
of markdown files"? Five metrics, one weekly report, honest counters only.

Everything is recomputed from persisted artefacts (INTERFACES.md), never from
volatile in-memory counters (PRD_B7 O2 / FR-1).

---

## 1 · Subcommands

```
python3 eval_harness.py report --week 2026-07-13 \
    --in .                                  # base dir for the relative paths below
    --metrics ops/first_judge_report.json   # judge_metrics report JSON (E1)
    --accepted ops/accepted.jsonl \
    --anchor ops/anchor_outbox.jsonl \      # E1 anchor agreement (rho-sample × anchor)
    --edges ops/edges.jsonl \               # E2 opposes, E3 column (c)
    --lint ops/cycles/<ts>/lint.json \      # E2 S2 flag
    --stance-diff ops/cycles/<ts>/stance_diff.jsonl \   # E4
    --harvest-ledger ops/harvest_ledger.jsonl \         # E5 responses
    --taskgen-ledger ops/taskgen_ledger.jsonl \         # E5 generated
    --calsets calib/calset_edge_type.jsonl calib/calset_continues.jsonl \  # E5 :human
    --elaboration ops/cycles/<ts>/elaboration_coverage.jsonl \  # E5 per-train
    --snapshot sync/snapshots/latest.json \  # E3 lexical corpus
    --questions eval_questions.yaml \
    --pairs fixtures/eval/seeded_pairs.yaml \
    --spend ops/spend.jsonl \                # debts: API mode
    --cycle <n> \
    --history eval/history --out eval

python3 eval_harness.py seed-contradictions --orders ops/cycles/<ts>/writeback_orders.jsonl
python3 eval_harness.py check-seeded --edges ops/edges.jsonl --lint <lint.json> --cycle <n>
python3 eval_harness.py retrieval --questions eval_questions.yaml \
    --snapshot sync/snapshots/latest.json --edges ops/edges.jsonl \
    [--embed-index embed_index.py]           # column (b) kNN; omit to skip
python3 eval_harness.py self-test            # zero network, synthetic fixtures
```

Outputs (INTERFACES.md row): `eval/weekly_report.{md,json}` + `eval/history/`.
The `report` path is deliberately offline: column (b) kNN is left to `retrieval`
(it shells out to `embed_index.py`); the weekly report renders (b) as
"indisponible" unless you pre-compute it. This keeps the Monday launchd job from
depending on the embedding service being up.

Note: the `report` subcommand takes only files that exist; every artefact flag is
optional. A week with no cycle still renders (§ "no data" sections, PRD_B7 §6.1).

---

## 2 · Report template (§4 of the annex)

```
# Rapport hebdo — semaine du {date}
## ⚠ Alertes           ← only if a threshold is crossed, WITH its attached decision
## E1 Jugement          taux d'abstention, gate verdict, accord ancre — par jtype × judge_id
## E2 Contradictions    détectées k/15, faux positifs j/10, âge médian en attente
## E3 Récupération      tableau (a) lexical (b) kNN (c) arêtes + marginal, par domaine
## E4 Stances           changements, churn %, seuil
## E5 Boucle humaine    taux de réponse par type, exemples :human cumulés, coverage par train
## Dettes               mode API actif, flags linter ouverts, étapes sautées
## Tendances            sparklines 8 semaines (blocs Unicode ▁▂▃▅▇)
```

The JSON mirror (`weekly_report.json`) carries the raw values plus `alerts[]`;
the B2 Monday digest reprints `alerts[]` (contract: `kind: digest`, field
`notes`). Each threshold + its decision live in `eval_thresholds.yaml`, never
hardcoded — a threshold with no decision attached is decoration (PRD_B7 §7).

---

## 3 · The five metrics

### E1 · Judgment health
Reads the `judge_metrics.py report` JSON per jtype (× `judge_id`, never averaged
across judge versions — PRD_B7 §6.3) and re-derives the **gate verdict** from the
injected thresholds:

| abstention rate | verdict | n |
|---|---|---|
| < 0.10 | SUSPICIOUS-LOW | ≥ 50 |
| 0.10 ≤ rate < 0.35 | HEALTHY | ≥ 50 |
| 0.35 ≤ rate < 0.60 | USABLE-EXPENSIVE | ≥ 50 |
| ≥ 0.60 | UNINFORMATIVE | ≥ 50 |
| any | N-TOO-SMALL | < 50 |

**Anchor agreement**: cross `accepted.jsonl` (ρ = 0.05 sample) with
`anchor_outbox.jsonl` by `context_hash`; agreement = share where labels match.
Alert on a 2-week consecutive drop (drift).

### E2 · Seeded contradictions (methodology)
`seed-contradictions` writes 15 FR contradiction pairs (half RGPD / half thèse) +
10 control pairs to `[[M/Eval/Seeded]]` via **`kind: seed`** writeback orders — a
write family that is **out of budget** and **allowlisted to `M/Eval/*` only**.
Each block carries `eval-seeded:: true`. Block uids are deterministic:
`<pair-id>-a` / `<pair-id>-b`; idempotency key = `sha256(pair_id + "a"|"b")`.

`check-seeded` marks a contradiction pair **detected** iff:
- a promoted **`opposes`** edge (from `edges.jsonl`) joins its two uids — this is
  the *primary* detector — **or**
- an **S2** (`UnsupportedClaim`) violation (from `lint.json`) sits on either uid.
  Caveat: S2 detects *missing support*, not *opposition*; it is the secondary
  signal only.

Report: detected `k/15`, pending (with age in cycles), false positives on the 10
controls (a control that gets an `opposes`/S2 is over-detection — a negative
control failure). If the propositionizer ran, follow `prop_id` via
`propositions.jsonl` to the derived propositions before pairing (not exercised in
the reduced loop).

### E3 · Retrieval coverage (three frozen columns)
Per question, `coverage@20 = |gold ∩ reached| / |gold|`, meaned by domain + union:

- **(a) FROZEN lexical baseline** — the negative control. Definition:
  NFC + lowercase, strip punctuation (`[^\w\s]`), whitespace tokenize;
  `score(block) = |tok(question) ∩ tok(block)| / |tok(question)|`; rank
  descending (tie-break by uid), take top-20. **Committed once. Never retouched.**
  Any change is a NEW column, not an edit to this one.
  - **FROZEN baseline hash:** `sha256:1d4552722ccc93baf83bf3f498d1bf6a71fe3e4ef9dc814447132906985a3a01`
    (`eval_harness.frozen_lexical_hash()`; printed in every report under E3).
- **(b) kNN** — `embed_index.py query --text "query: <question>" --top 20`
  (asymmetric e5 query prefix). Omitted → column renders "indisponible".
- **(c) promoted edges** — blocks ≤ 2 hops from any lexical top-5 hit, following
  only `edges.jsonl` (supports/opposes/refines + `continues`). This is the
  **marginal** value of the graph: `(c) \ (a)` is what the substrate adds over the
  flat file — the honest comparison PRD_B7 §3 demands.

Orphaned gold (block deleted/rewritten by the owner) is reported and **excluded**
from scoring — no false failure (PRD_B7 §6.2).

`eval_questions.yaml` ships **empty**. The owner fills 15 questions **before**
inspecting the graph (anti-easy-benchmark rule, PRD_B7 §8) and then freezes it.

### E4 · Stance stability
From `stance_diff.jsonl` per cycle: `churn_share` = share of diffs whose
`caused_by` is a **retraction / re-judgment** (vs new evidence, which is healthy).
Alert when churn > 20 % over 2 weeks (the system undoing its own work).

### E5 · Human loop
Response rate per task_type = answered / generated (from `harvest_ledger.jsonl`
+ `taskgen_ledger.jsonl`, B3), cumulative `:human` calset examples
(`provenance.source == "human"` — the distillation fuel), and
`elaboration-coverage` per train (exported by B4 in its cycle report). If this
collapses, everything else is noise.

---

## 4 · Thresholds ⇒ decisions

All in `eval_thresholds.yaml`. Every crossed threshold surfaces at the top of the
report **and** in the B2 digest with its decision text. Summary:

| metric | threshold | decision (abridged — full text in yaml) |
|---|---|---|
| E1 gate | UNINFORMATIVE (≥ 60 %) | recalibrate or change model |
| E1 gate | USABLE-EXPENSIVE (35–60 %) | α=0.10-with-panel or larger judge in Phase 2 |
| E1 gate | SUSPICIOUS-LOW (< 10 %) | audit calset/live leakage before trusting |
| E1 anchor | falling 2 weeks | re-sample gold, re-check judge vs anchor |
| E2 detection | < 60 % detected in ≤ 3 cycles | inspect prefilter budget / edge_type calibration |
| E2 controls | any FP on controls | tighten edge_type gate before trusting E4 |
| E3 marginal | ≤ 0 | promoted graph earns nothing this week; review promotion volume |
| E4 churn | > 20 % over 2 weeks | freeze re-judgment; inspect retraction causes |
| E5 response | < 50 % (7d) | reduce task budget; check surface friction |
| E5 elaboration | < 30 % | prioritise elaborate tasks (distillation fuel drying) |

---

## 5 · Cadence

**Monday 06:00**, a **launchd** job separate from the nightly cycle. B7 depends on
persisted artefacts, not on *today's* cycle, so it runs independently (ANNEX_B7
§7). Example agent (`~/Library/LaunchAgents/dev.mnemosyne.eval.plist`):

```xml
<key>StartCalendarInterval</key>
<dict><key>Weekday</key><integer>1</integer>
      <key>Hour</key><integer>6</integer><key>Minute</key><integer>0</integer></dict>
<key>ProgramArguments</key>
<array>
  <string>/usr/bin/python3</string>
  <string>/…/files_mnemosyne/eval_harness.py</string>
  <string>report</string><string>--week</string><string>$(date +%Y-%m-%d)</string>
  <string>--in</string><string>/…/files_mnemosyne</string>
  … artefact flags …
</array>
```

The weekly report is also written into `[[M/Journal]]` via B2 (a `kind: digest`
order carrying `alerts[]` in `notes`).

---

## 6 · Contamination exclusion — `M/*` (owned by B1)

The seeded blocks live on `[[M/Eval/Seeded]]`. They must be excluded from calsets
and distillation so they never leak into training (FR-2). The mechanism is a
blanket **`M/*` page exclusion** in the harvesters — `roam_harvest.py`,
`prefilter.py`, and B5 skip any block whose page title starts with `M/`, which
covers `M/Eval/` for free.

**Scope note:** the `M/*` exclusion patch to `roam_harvest.py` / `prefilter.py` is
**owned by the B1 agent** (to avoid file conflicts). B7 does **not** edit those
files. Instead, the B7 `self-test` *asserts* the behaviour: it imports the
harvester and feeds it `fixtures/eval/m_eval_snapshot.json` (which contains an
`M/Eval/Seeded` page with candidate-worthy blocks) and expects **zero**
candidates. If the patch is not yet present, the self-test prints a soft warning
naming the leaking candidate types and does **not** fail (nor edit B1's files) —
so the finding is visible without a scope violation. Once B1 lands the patch the
assertion turns green automatically.

As of this writing the patch is **not yet present**: the fixture mines
`summarize_now` and `permanent_worthy` candidates from `M/Eval/Seeded`. B1 must
land the `M/*` filter for E2 anti-contamination to hold.

---

## 7 · Self-test

`python3 eval_harness.py self-test` — zero network, synthetic fixtures only
(embed_index kNN path is mocked/skipped). 56 assertions covering: E1 gate verdicts
across all five buckets + anchor agreement; E2 seed/check on the real fixture
incl. the control false-positive check; E3 lexical-baseline determinism, 2-hop
neighbourhood, marginal recovery, injected-kNN mock, orphan-gold exclusion; E4
churn; E5 rates + `:human` count + elaboration coverage; trends sparklines (incl.
gap-week handling); md + json render; and the `M/Eval/Seeded` exclusion assertion.

DoD:
```
python3 -m py_compile eval_harness.py
python3 eval_harness.py self-test
```
Both exit 0.

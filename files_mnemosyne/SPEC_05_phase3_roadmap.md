# Mnemosyne — Phase 3 extension program
## SPEC-05 · Roadmap, dependency web, and gates for B8–B14 (+ federation horizon)

**Audience:** whoever plans work after the reduced loop closes (M0 + 4
weekly B7 reports — the ADR-001 point-6 design freeze lifts only then).
**Status:** synthesis of the ratified doctrine (ADR-001), the built loop
(B1–B7), and the phase-3 PRD pack (`prd/PRD_B8..B14`). Normative for
sequencing and gates; each PRD remains normative for its own content.

---

## 1 · The program in one idea

Every phase-3 extension is the same move: **take a discipline the system
already applies to its beliefs, and apply it to something it currently
takes on faith.**

| Brick | What was taken on faith | Discipline now applied |
|---|---|---|
| B8 trace projection *(reserved, ADR-001 A.5)* | where reasoning traces live | projection to `M/*`, I1-preserving |
| B9 owner calibration | the owner's answers | double-pass + drift measurement |
| B10 immune system | `accepted-undisputed` claims | adversarial verification, gated |
| B11 manuscript projection | the manuscript's fidelity | derived view + faithful gate |
| B12 self-experimentation | the system's own configuration | pre-registered paired comparison |
| B13 live companion | knowledge present at point of use | weightless whispers, gated keeps |
| B14 dreamer | the discarded confidence structure | Monte-Carlo over calibrated worlds |

Common invariant check (verified in each PRD): **I1–I4 and the CALM
split hold everywhere.** Every extension is more folds / judges /
adversaries / worlds over the same append-only log — never a new kind of
magic. The test for any FUTURE extension: if it must edit content,
self-report confidence, or write outside the consolidator, it is not an
extension, it is a regression.

## 2 · The two day-1 riders (ship WITH the reduced loop — not phase 3)

Two tiny patches must not wait, because their absence destroys data that
can never be recovered:

| Rider | From | Cost | Why now |
|---|---|---|---|
| Probe ledger (B9 FR-1) | `task_harvest` writes `ops/probe_ledger.jsonl` per answered task | ≤ 30 lines | every un-ledgered answer is a probe that can never be asked |
| Label distributions (B14 FR-1) | outbox events carry `label_distribution` | additive field | every point-mass judgment is a world that can never be re-dreamed |

Both are additive, self-test-extended, and epistemically inert until
their consumers arrive months later. **They ride with WP-0.**

## 3 · Dependency web

```
reduced loop closed (M0 + 4 weekly B7)          ← the gate for EVERYTHING below
        │
        ├── B14 dreamer ────────────┐ (three consumers wait on it)
        │       │                   │
        │       ├─► B10 targeting (stability × centrality; fallback: centrality)
        │       ├─► B11 stability floor (fallback: ~unstable markers)
        │       ├─► B13 left-field world-stats (fallback: other sources)
        │       └─► E4→E8 expected churn + continuous belief.py↔clj mirror check
        │
        ├── B13 companion v0 (needs only B1/B2/B5 + stances)   ← earliest daily value
        ├── B11 v0 skeleton  (needs compose-assembly + stances) ← cheapest falsification
        ├── B9  probes: injection at loop+90d; scoring at ~loop+5mo (calendar-bound)
        ├── B12 experiments (needs ≥4 weekly reports as baseline)
        │       └─► tunes: B13 thresholds, B10 budgets, B14 priors, core α/k/budgets
        └── B10 immune v0 (internal-only prosecutor; better after B14)

B8 trace projection: unblocks with the compose/RLM driver (B11 v1 era).
Federation: phase-4 horizon (see §6) — needs B12 + a second graph.
```

**Suggested order of construction** (after the gate, assuming one dev):
1. **B14** (2–3 d) — three consumers wait; also turns the py↔clj mirror
   check on continuously for free (B14 §6 case 5).
2. **B13 v0** (3–4 d) — on-demand companion; first daily-felt value of
   the whole substrate; its keep-rate becomes the best product metric.
3. **B11 v0** (2 d) — skeleton-only manuscript; 2-week diff-reading gate.
4. **B12** (2 d harness) — as soon as 4 weekly reports exist; EXP-001.
5. **B10 v0** (2–3 d) — monthly internal-only prosecutor campaign.
6. **B9 scoring** (1–2 d) — when the probe ledger has 90-day-old entries.
7. B11 v1 / B13 v1 / B10 portfolio / B14 v1 — each behind its gate.

## 4 · Every brick carries its own kill-switch

The pack's philosophy: no extension survives on narrative. Each PRD
defines the cheap experiment that can kill it:

| Brick | Falsification gate | Cost of finding out |
|---|---|---|
| B11 | 14 skeleton diffs judged ≥ 80 % informative (M4), else no prose layer | 2 dev-days + 2 weeks reading |
| B13 | summoned whispers earn keeps (M1), else no ambient mode | 3–4 dev-days + 2 weeks use |
| B10 | promotion rate of prosecutor candidates in 5–40 % band (M2), else freeze | 1 campaign |
| B12 | one EXP concluded (promoted OR rejected) within 2 months (M4), else it's science-theatre | EXP-001, offline |
| B14 | predicted flip-rates match realized E4 flips (M2), else it's an anxiety generator | 8 weeks of E8 |
| B9 | owner can't identify probes better than chance (M2), else data invalid | at DoD |

## 5 · The ADR ledger phase 3 requires

| ADR | Decides | Blocks |
|---|---|---|
| ADR-00x consent | B9 probing: covert-in-the-moment, transparent-in-policy; right to stop | any probe injection (NOT the ledger) |
| ADR-00x policy classes | B12 P5: auto-promotable vs human-ratified list | first auto-promotion |
| ADR-00x purge exception | B13 FR-4: TTL purge of unkept whispers = the system's only delete, scope M/Live strictly | already consigned in the PRD; ratify with B13 |
| ADR-00x phase-4 gates | bandits/continuous optimization (B12), federation (§6), keystroke-level companion | phase 4 |

## 6 · Federation (horizon — examined, deliberately not PRD'd)

The unit of exchange between two Mnemosynes is the **judgment stream**
(typed verdicts + I4 envelopes + context hashes), never documents.
Imports arrive as a foreign judge family (`:source/family :peer/<name>`):
monotone (CALM-safe), informing but never promoting in v0, trust measured
per-cohort by anchor-sampling the overlap (the E1 mechanism), revocable by
cohort retraction (trust revocation with automatic healing). Imported
confidences are self-reported (I3) until re-calibrated locally — her 0.9
is not your 0.9. The payoff artifact is the **disagreement surface**:
a computed diff of two belief layers with causal attribution to the exact
upstream evidence/judgment fork. The defining hazard is **judgment
laundering** (the same ground-level verdict reaching you twice through
different intermediaries and counting as corroboration); the defense is
total lineage — corroboration counts distinct ground-level judgment acts
(original judge × context hash), never distinct messengers.

Why no PRD yet: it needs the reduced loop, B12, a second live graph, and
a willing peer — none of which exist. Prototype when they do: federate
with *yourself* first (a second graph, one-way import), then one
colleague, one shared corpus, export-only bulletins. Phase 4, own ADR.

## 7 · What phase 3 does NOT do (inherited freezes, restated)

- No Fluree port, no compose/RLM driver before B11's own gate, no panel
  automation beyond what M0-era tuning ratifies (SPEC-00 §6 still binds
  where not explicitly superseded by a PRD here).
- No experiments on B9's measurement of the owner (B12 scope freeze).
- No Monte-Carlo of the owner (B14 non-objective).
- Nothing writes outside the consolidator; nothing edits user content;
  nothing self-reports confidence past a gate (the §1 test, permanently).

## 8 · Program-level acceptance

Phase 3 is DONE when: the two riders have been live since WP-0; B14's E8
calibration curve exists with ≥ 8 weeks of data; B13's keep-rate and
B11's diff-informativeness verdicts are consigned (either direction);
EXP-001's verdict is consigned; one B10 campaign has produced either an
`accepted-tested` claim or a promoted opposition; and the B9 first
calibration report has been read by the owner. At that point the system
is not just running — it is measuring its owner, stress-testing its
beliefs, forecasting its own churn, evidencing its own configuration,
present at the moment of writing, and rewriting its manuscript nightly.
The meta-thesis stops being an aspiration and becomes a dataset.

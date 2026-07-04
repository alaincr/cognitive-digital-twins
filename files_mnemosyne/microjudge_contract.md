# The Micro-Judge Contract — cheap intelligence as a safe substrate operation

*Companion to `mnemosyne_stack.md`. This spec defines regime **B½**: the swarm of small-LLM
judges that decides edge types, abstraction triggers, propagation gating, invalidation,
coreference, and faithfulness — as **discrete, typed, append-only facts** over the Mnemosyne
substrate. Companions: `judge_schemas.json` (constrained-decoding output schemas),
`judges.clj` (DataScript schema + rules + queries), `cascade.svg` (the ladder).*

---

## 0 · The four invariants

Everything else in this spec is machinery; these four are the contract. A judge deployment
that violates any of them re-imports the pathologies the swarm was meant to repair.

**I1 — Judgments are facts, never rewrites.** A judge emits a typed label about identified
subjects (`(edge f1→c3) : supports @ 0.83`). It never edits node text, never deletes, never
merges. Judgments accumulate monotonically in the event log; conflicting judgments *coexist
as evidence* and are resolved downstream. This is what restores quasi-monotone semantics to
LLM-mediated propagation: idempotence is trivial (same judgment twice = one fact),
oscillation is impossible (nothing is overwritten), and accumulation is CALM-monotone —
judges can run coordination-free across all Hermes nodes.

**I2 — Closed output vocabularies, constrained decoding.** Every judgment type has a fixed
label enum (see §2 and `judge_schemas.json`). Decoding is grammar-constrained to the schema
(vLLM guided decoding). A judge that can only emit `{supports|opposes|refines|unrelated}`
has a very small attack surface and plays to small models' strength (classification, not
generation).

**I3 — Confidence comes from logprobs, not self-report.** The confidence attached to a
judgment is the renormalized label-token log-probability (temperature-scaled per §4), not a
number the model writes. Self-reported confidences from small models are decoratively
miscalibrated. (Fallback for API judges without logprob access: self-report, flagged
`:confidence/self-reported true` and given a stricter conformal threshold.)

**I4 — Every judgment carries the full provenance envelope** (§3): judge identity down to
the weights hash, prompt-template version, calibration version, and the content-address of
the exact context judged. The envelope is what makes the swarm auditable, replayable
(pinned local weights + temp 0 ⇒ deterministic), and — the killer property — **cohort-
retractable** (§6).

---

## 1 · The ladder (where B½ sits)

```
candidates ──► A · heuristics ──► B · embedding/relational ──► B½ · small-LLM ──► C · large-LLM
(pre-filter)    (Datalog rules,     classifiers                  micro-judges       reasoning /
 activation,     string/regex,      (kNN, R-GCN edge scorer)     (4–8B, local,      panel arbiter /
 surprisal,      exact matches)                                   constrained)       human gate
 dirty-marks)
        each rung: decide if confident ── otherwise ESCALATE one rung ──►
```

- **Pre-filter, not judge:** activation/surprisal/dirty-marking generates *candidates*; the
  swarm never scans the whole graph. The formal layer decides **where to look**, the swarm
  decides **whether to act**. Budgeted per consolidation cycle; priority = activation × stakes.
- **Each rung abstains upward.** A rung emits a judgment only inside its confident region
  (heuristics: rule fires; B: score outside the ambiguity band; B½: conformal singleton, §4).
  Otherwise it appends an `:escalated` marker and the next rung picks it up.
- **Demotion over time (distillation gravity):** stable C-decisions train B½ judges; stable
  B½ behavior trains B classifiers; the most stable patterns compile to A rules. The system's
  self-improvement = re-pricing its own cognition downward (§7).

**Judgment lifecycle:** `:candidate → :accepted | :rejected | :retracted`, plus
`:quarantined` at the judge level. *Emission* of candidates is monotone and coordination-free.
*Promotion* to `:accepted` (which is what asserts the actual domain fact — the typed edge,
the sameAs, the stale-mark) is the non-monotone step: single logical writer per subject,
inside the consolidation pass. This is the CALM split applied to the swarm itself.

---

## 2 · Judgment type catalog

| Type | Question the judge answers | Labels | Stakes tier | Typical context given |
|---|---|---|---|---|
| `edge-type` | How does proposition/finding X bear on claim C? | `supports / opposes / refines / unrelated` | **T2** (feeds belief) | both propositions, C's one-line stance, 2–3 sibling evidence items |
| `same-entity` | Do mentions m1, m2 denote the same referent? | `same / distinct` | **T2** (merge corrupts) | both mentions + their host propositions + entity attribute digests |
| `summarize-now` | Should cluster K be abstracted now? | `fire / defer / never` | T0 | cluster digest: size, density, churn rate, staleness, query count — *not* full members |
| `propagate?` | Does change Δ at node n materially affect neighbor v via edge e? | `propagate / absorb` | T0 (learned damping) | Δ summary, edge type, v's proposition |
| `invalidate?` | Is derived node S stale given changes in its derivation cone? | `invalidate / keep` | T1 | S's text, the delta digest of changed children |
| `dedup-prop` | Are propositions p1, p2 redundant? | `duplicate / subsumes / distinct` | T1 | both propositions + source refs |
| `faithful?` | Does proposition p preserve its source span's meaning **incl. qualifiers**? | `faithful / lost-qualifier / unsupported` | **T2** (legal guard) | p + the exact source span + surrounding sentence |

Notes:
- `faithful?` is the Dense X decontextualization guard specialized to your legal corpus: the
  `lost-qualifier` label exists because a legal proposition stripped of its scope/exception
  is *false*, not incomplete. Every propositionization is judged before its propositions are
  eligible for promotion.
- `summarize-now` decides **whether**; the summary itself is regime C work. Same for
  `same-entity`: promotion asserts a *retractable* `:sameAs` edge, never a destructive merge.
- `propagate?` is the learned, content-aware damping for hub short-circuiting: diffusion
  through a hub consults the gate instead of fanning out blindly.

**Stakes tiers govern decorrelation spend (§5):**
- **T0** (navigational/scheduling): single judge, permissive threshold. Worst case = wasted
  or deferred work, self-correcting.
- **T1** (structural): single judge, strict threshold; disagreement with regime-B signal
  auto-escalates.
- **T2** (epistemic — feeds belief stances, merges identities, certifies legal faithfulness):
  **heterogeneous panel, k-of-n agreement** (default 2-of-3 across distinct base-model
  families) required for promotion; any dissent escalates to C.

---

## 3 · The provenance envelope

Every judgment event carries:

| Field | Content | Why |
|---|---|---|
| `:judgment/id` | uuid | identity |
| `:judgment/type` | one of §2 | routing, per-type calibration |
| `:judgment/subjects` | refs to the judged node(s)/edge(s) | blast-radius queries |
| `:judgment/label`, `:judgment/confidence` | enum + calibrated score | the verdict |
| `:judgment/judge` | ref → judge entity: `{model, weights-hash, prompt-version}` | **cohort retraction** |
| `:judgment/cal-version` | calibration-set version used for its threshold | recalibration audits |
| `:judgment/context-hash` | content-address of the *exact* assembled context | determinism, replay, cache, audit |
| `:judgment/basis` | ≤240-char free-text note | **audit-only; never machine-parsed** |
| `:judgment/status` | candidate/accepted/rejected/retracted | lifecycle |
| `:event/caused-by` | the triggering event | standard Mnemosyne lineage |

`basis` is deliberately quarantined: short, length-capped, read by humans during audits,
never by downstream code — rationale text is the verbosity-bias and injection vector, so it
gets no machine role.

---

## 4 · Calibration & conformal abstention

Per (judgment-type × judge-version):

1. **Calibration set:** ≥ ~300 labeled examples per type. Bootstrap labels from the anchor
   (large) model; human spot-check T2 types. The calibration/audit set is **frozen and never
   trained on** (anti-collapse, §7).
2. **Temperature-scale** the label logprobs on half the set (fixes small-model overconfidence
   with one parameter).
3. **Split conformal** on the other half: nonconformity `s = 1 − p̂(true label)`; threshold
   `q̂` = the ⌈(m+1)(1−α)⌉/m quantile of calibration scores. Target coverage 1−α: **90% for
   T0/T1, 95% for T2** (starting points, tune against escalation volume).
4. **At inference:** prediction set = labels with `p̂ ≥ 1 − q̂`. **Singleton ⇒ emit** that
   label with its score. **Otherwise ⇒ abstain & escalate.** Abstention is computed by the
   harness from logprobs — the model is never asked whether it is sure.

**Honest limit:** conformal guarantees assume exchangeability between calibration and
deployment distributions. A growing, self-modifying graph drifts, so the coverage guarantee
is *approximate* and decays between recalibrations. Treat the guarantee as a calibrated
engineering dial, not a theorem about your deployment; the drift monitor (§6) is what makes
this safe, and recalibration is mandatory on every judge-version bump and every drift alarm.

---

## 5 · Panels & promotion (the non-monotone gate)

- **T2 promotion rule:** k-of-n agreement (default 2-of-3) among judges from **distinct
  base-model families** (e.g. Qwen3-8B / Gemma / Phi — same family ≠ decorrelation), each
  individually past its conformal gate. Any dissent ⇒ escalate to C; C's verdict is itself a
  judgment (judge = the anchor model) subject to the same envelope.
- **Position-bias hygiene:** option order randomized per call; labels chosen to be
  length-neutral; pair order (A,B vs B,A) randomized for symmetric types (`same-entity`,
  `dedup-prop`) and **agreement across both orders required** for T2.
- **Promotion mechanics:** the consolidation pass (single logical writer per subject) reads
  accepted-eligible candidates and appends the *domain* event: the typed edge with
  `:prov/from-judgment`, the `:sameAs` belief edge, the stale-mark that dirty-marks the
  derivation cone upward. Domain facts thus always trace to the judgments that licensed them
  — this is what makes §6 a query.
- **Injection hardening:** judges have **no tools**; inputs are structured fields with
  content quoted as data; decoding is schema-constrained; `basis` is machine-quarantined.
  The worst a poisoned document can do to a judge is push one label of a closed enum — which
  the panel, the linter, and the belief layer were already built to absorb.

---

## 6 · Cohort retraction & the drift monitor

**Cohort retraction** — the property that converts "we ran a biased judge for three weeks"
from catastrophe into a query:

1. *Cohort:* all judgments where `:judgment/judge = J@v` (optionally windowed by tx-time).
2. *Taint:* every domain fact carrying `:prov/from-judgment` into the cohort, plus — via the
   existing `derivation`/`descendant` closures in `rules.clj` — every derived node (summary,
   stance, compound entity) downstream of those facts.
3. *Act:* append retraction events for the tainted domain facts, mark judgments
   `:retracted`, dirty-mark the derived cone for recomputation. **Nothing is deleted** —
   bitemporality preserves the full record of the mistake, queryable as intellectual history.

**Drift monitor (anchor sampling):**
- Re-judge a random ρ ≈ 1–5% of accepted judgments with the anchor model; record agreement
  as facts.
- Per (type × judge-version), track disagreement rate over a sliding window.
- **Quarantine rule:** disagreement > θ (default 2× the rate observed at calibration) ⇒
  append a quarantine event for that judge-version: its pending candidates stop being
  promotable, new emissions are tagged quarantined, and a review task opens. Quarantine is
  reversible (it's an event); persistent drift ⇒ cohort retraction + recalibration or
  retirement.
- A *widening* anchor-disagreement trend is an alarm even below θ — it is the early signature
  of distribution shift or feedback contamination.

---

## 7 · Distillation without eating your own tail

- **Training lineage is a provenance query:** an example is admissible for distilling judge
  v(n+1) only if its label's provenance chain contains an anchor judgment or a human mark —
  never the swarm's own unaudited outputs. (Admissibility is checkable in Datalog; see
  `training-admissible` in `judges.clj`.)
- The frozen audit set is sacrosanct: thresholds and drift are measured on it; it is never
  in any training run.
- **Re-anchoring cadence:** periodically (and on every alarm) refresh part of the calibration
  set with fresh anchor labels on *current-distribution* candidates, so calibration tracks
  the graph the judges actually see.
- Distillation targets in order of value: `edge-type` (highest volume, cleanest labels) →
  `propagate?` (pure trigger, easiest) → `same-entity` (hardest, keep panel longest).

---

## 8 · Workload & budget

- Judges run **only** on pre-filtered candidates; per-cycle budget caps total judgments;
  priority queue = activation × stakes-tier; per-node debounce (a node re-judged for the
  same type only after its accumulated delta crosses ε or a cool-down lapses).
- Judgments are prefill-dominant (context in, ~5 tokens out): on the PrfaaS-PD split this is
  prefill-cluster work, batched under vLLM; thousands/hour on the 3090s at ~zero marginal
  cost. Local pinned weights + temp 0 + `context-hash` cache ⇒ deterministic replay — a
  property API judges structurally cannot give you.

---

## 9 · Build order

1. Stand up **one** judge type end-to-end: `edge-type` with envelope, constrained decoding,
   logprob confidence, conformal gate, candidate→promotion flow. (It has the highest volume
   and feeds the belief layer — maximum leverage.)
2. Anchor-label a 300-example calibration set; temperature-scale + conformal per §4.
3. Wire the drift monitor (anchor sampling at ρ=5% initially) and the quarantine behavior.
4. Add `faithful?` next (it gates everything densification produces), then `propagate?`
   (cheapest win: learned damping), then the rest.
5. First distillation pass once ≥ a few thousand admissible examples exist; promote the
   distilled judge behind a shadow deployment (judge in parallel, compare, don't promote)
   before it earns promotion rights.
6. Only then widen to panels and T2 automation; until then, T2 promotions stay gated on the
   anchor or on you.

### One-line summary
Small models become safe substrate operators when their entire expressive range is a closed
label set, their confidence is measured rather than asserted, their every verdict is a
provenanced fact, and their mistakes are retractable *by cohort* — at which point the swarm
is just regime B½ of the ladder, scheduled by the same events, audited by the same log, and
improved by the same distillation gravity as everything else in Mnemosyne.

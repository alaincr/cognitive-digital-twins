# Mnemosyne — Swarm scaling doctrine
## SPEC-06 · Families, replicas, and the serial spine (normative)

**Audience:** whoever proposes "just run more judges" — this analysis
otherwise gets re-derived from scratch every time. **Status:** normative
for scaling decisions; SPEC-00 §3 conventions and the PRD pack remain
normative for their own content. **Context:** the system is a swarm by
birth (SPEC-00 §1: "a swarm of small local LLM micro-judges"); this
document fixes what scaling that swarm actually buys, and what it never
can.

---

## 1 · The two laws

### Law 1 — Amdahl's law of epistemics
The architecture splits into a parallel fringe and a serial spine:

| | Components | Scaling behavior |
|---|---|---|
| **Monotone fringe** | candidate mining, judging, propositionizing, prosecution (B10), dreaming (B14), commissioned research, companion tiers (B13) | coordination-free by CALM: append-only, content-addressed, idempotent — "any Hermes node may emit". Parallelism is effectively unbounded. |
| **Serial spine** | the consolidator (single writer — cheap: folds, not inference), the **anchor** (quality ceiling), the **human** (ground-truth mint), the **gold supply** (calsets) | deliberately serial. The anchor is capacity-bounded by spend; the human by anti-fatigue (B3); gold by both. |

Every scaling proposal is evaluated against the spine, not against
compute. Throughput added to the fringe that increases spine load
(escalation floods, calibration demand) is negative-sum.

### Law 2 — Families, not instances
**N copies of the same weights are one judge with N threads.** The
system's epistemics count *families* (distinct training lineages with
decorrelated errors), because:
- T2 promotion requires k **distinct families** agreeing (`panel-k`,
  judges.clj) — a monoculture's unanimous vote is one vote;
- a shared blind spot corrupts many edges at once, and cohort retraction
  removes all of that family's output simultaneously — monoculture
  concentrates brittleness;
- B14's hierarchical sampling draws one bias term per family per world —
  a monoculture swarm is a single draw wearing a thousand hats.

**Replicas buy throughput. Families buy knowledge.** The planning
invariant, in one line:

> Epistemic value scales with (distinct calibrated families) ×
> (gold supply) — never with instance count.

## 2 · Adequacy of small models is empirical, not speculative

The judge task was shaped so small models can be *trusted*, not merely
used: closed vocabulary, constrained decoding, confidence read from
logprobs (I3), split-conformal gate. Consequences:

1. **Coverage is distribution-free.** The conformal guarantee holds
   regardless of model quality. A weaker model does not emit more
   wrong-but-confident verdicts past the gate — it emits **larger
   prediction sets, i.e., more abstentions**. Weakness degrades *cost*
   (escalation volume), never *soundness*.
2. **The adequacy test is an afternoon**: `judge_harness.py calibrate`
   against the candidate endpoint, then read the abstention rate.
   0.10–0.35 → adequate (HEALTHY band, SPEC-01 §8). ≥ 0.60 →
   uninformative, next model. No philosophy required.
3. **Reasoning-tuned small models** (MiniCPM-class and peers): note the
   echo-scoring path is a single forward pass over `prompt+label` — no
   room for chain-of-thought at scoring time. Reasoning-then-score is
   permitted (prompt-version bump ⇒ new judge_id ⇒ recalibration), but
   expect little gain on closed-vocabulary micro-questions; these are
   perception-sized judgments, not proofs.
4. **Task segregation stands**: small models judge; strong models
   generate and anchor. The propositionizer on dense legal text, the
   prosecutor's steelmanning (B10), manuscript prose (B11), and the
   anchor are NOT swarm tasks.

## 3 · The canonical shape: a cascade, not a fleet

Neither "a couple of strong models" nor "1000 clones" — the trust
structure dictates the deployment shape:

```
~5–10 distinct families          different base models / fine-tune
   × N replicas each             lineages / distilled data shards
   (N sized by throughput)       → real error decorrelation
        │ abstentions
        ▼
1 strong anchor                  never economize — the ceiling of the
                                 whole system (SPEC-01)
        │ flagged / sampled
        ▼
1 human                          the mint of ground truth; the only
                                 genuinely unscalable component — by design
```

Distillation (`distill_judge.py`) is the family factory: compile anchor
judgment into per-jtype / per-domain specialists (judge speciation),
seeded and sharded differently so lineages decorrelate. McNemar gates
promotion; lineage lives in the log; a failed family retracts as a
cohort.

## 4 · What instance-count DOES buy (spend it here)

When judgment stops being scarce, the design compromises that exist only
because inference was precious dissolve. Deploy surplus replicas on the
monotone fringe:

| Use | Today (budgeted) | At swarm scale |
|---|---|---|
| Graph linting | dirty-marks + debounce + cooldowns | continuous full-graph re-judgment |
| Freshness | prefilter budgets ~15–50/type/day | every new block judged in seconds (B13 tier-1 at ambient scale) |
| Dreaming | resampling STORED distributions (B14 v0) | per-world re-judgment (lifts the v0 approximation) |
| Adversary | one prosecutor, monthly, top-5 (B10 v0) | diverse portfolio, weekly, deep coverage |
| Ingestion | propositionize on demand | speculative propositionization of all of raw/ |

**The swarm makes the system thorough; it cannot make it right.**
Rightness flows down from the serial spine, and no instance count
changes that — the architecture never lets quantity of opinion
substitute for calibration against ground truth.

## 5 · The costs that scale WITH the swarm (budget them first)

1. **Calibration**: each family × jtype needs its own ≥150–300-row
   calset, temperature fit, conformal quantile, and drift monitoring
   (θ). Ten families ≈ ten times the gold demand — and gold comes from
   the bounded anchor and the anti-fatigue-bounded human. This is the
   real limit long before GPUs are.
2. **Escalation load**: expected anchor traffic ≈ Σ over families of
   (volume × abstention rate). A swarm of high-abstention judges is an
   escalation flood aimed at a fixed-capacity anchor. Gate new families
   on their measured abstention band BEFORE fleet admission.
3. **Drift surface**: more families = more θ-monitors, more quarantine
   events, more retraction blast radii to audit. The auditor's
   attention is spine, not fringe.
4. **Consolidator headroom**: folds are cheap but not free; if event
   volume grows 100×, measure before assuming — the single writer is a
   design invariant, not an accident to "fix" with sharding. (Sharding
   the consolidator = re-deriving the CALM split the hard way. Don't.)

## 6 · Admission test for any scaling proposal (normative checklist)

A proposal to add model capacity MUST answer:

1. **Family or replica?** If replica: which fringe workload (§4) absorbs
   it? If family: where do its calsets come from, and what does it add
   to panel diversity that existing families lack?
2. **Abstention economics**: measured abstention band on a pilot calset;
   projected escalation traffic; anchor budget line (B6 spend ledger).
3. **Spine impact**: net change in anchor calls, human tasks, gold
   consumption. Negative-sum proposals (fringe throughput bought with
   spine load) are rejected by default.
4. **Retraction story**: the new capacity's cohort boundary — what is
   erased in one operation if it goes bad, and what does the fragility
   map (B14) say depends on it?
5. **Experiment**: fleet changes above T0 are B12 pre-registered
   experiments (policy class: human-ratified for panel composition,
   auto-promotable for replica counts).

## 7 · Answers of record (the questions that prompted this SPEC)

- **Can this scale to swarm functioning?** It IS a swarm design; the
  fringe scales without coordination, the spine deliberately doesn't.
  Benefits: throughput, thoroughness, family diversity, locality, cost.
  Limits: gold supply, anchor ceiling, human bandwidth, monoculture
  correlation.
- **Are MiniCPM-class models adequate?** Empirically decidable per
  model per jtype in an afternoon (§2). The architecture was shaped to
  make small models trustworthy at exactly this task class; distillation
  targets them explicitly. They are not candidates for anchor,
  propositionizer, prosecutor, or prose.
- **1000 small models vs a couple of strong ones?** Wrong dichotomy.
  1000 identical instances = one family at high throughput: thoroughness
  without added knowledge, brittleness concentrated in one cohort. The
  correct spend: ~5–10 distilled families × replicas (§3), surplus
  throughput on §4 workloads, strong models kept where strength is
  irreplaceable (anchor, generation). Gained by the swarm: judgment
  ceases to be scarce. Lost if it replaces strong models: the ceiling.
  Never traded: the serial spine.

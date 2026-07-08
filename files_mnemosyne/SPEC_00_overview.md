# Mnemosyne — Phase 0 & Phase 1 development specification
## SPEC-00 · Overview, conventions, and work-package map

**Audience:** a development team that has NOT followed the design history.
**Status of this pack:** ready for assignment. Each work package (WP) has its
own spec document with data contracts, algorithms, test plans, and Definition
of Done. This overview is normative for everything the WP specs don't override.

---

## 1 · System context (all you need to start)

Mnemosyne is a self-improving knowledge substrate: a three-layer system in
which **(L3)** an append-only, immutable fact store is the source of truth,
**(L2)** an event-sourced runtime maintains a working graph as a deterministic
fold of the log and reacts to graph patterns, and **(L1)** recursive LLM
inference navigates the graph and writes results back as facts. Graph
maintenance decisions (does this evidence support that claim? are these two
names the same entity? is this summary stale?) are made by a **swarm of small
local LLM "micro-judges"** whose verdicts are:

- **typed facts, never rewrites** — a judgment is an appended record with a
  label from a closed vocabulary; it never edits content (invariant I1);
- **confidence-gated** — the label's token log-probabilities are
  temperature-scaled and passed through a split-conformal gate; if the
  prediction set is not a singleton the judge **abstains** and the question
  escalates to a stronger model (the "anchor") (invariant I3);
- **provenance-enveloped** — every verdict records the judge identity (model @
  weights-hash # prompt-version), calibration version, and a content-address
  (SHA-256) of the exact context judged (invariant I4). This makes any
  judge's entire output **retractable as a cohort** if it is later found
  biased.

A **consolidator** (single-threaded Clojure service, `ingest.clj`) is the only
writer that *promotes* judgments into domain facts (discourse edges, sameAs
links, stale-marks, tasks). Everything upstream of promotion is monotone and
may run concurrently anywhere; everything non-monotone (promotion, negation,
retraction) lives in the consolidator. This CALM split is a standing
architectural invariant — new code must not blur it.

The pipeline from a knowledge source to a live judge is:

```
Roam export ─► roam_harvest.py (candidate mining, 9 judgment types)
            ─► anchor_label.py (gold labels via the anchor, double-pass)
            ─► human review of flagged items (review_queue.md)
            ─► judge_harness.py calibrate (temperature T + conformal q̂)
            ─► prefilter.py (live: dirty-marks → budgeted candidates)
            ─► judge_harness.py judge (score → gate → outbox JSONL)
            ─► ingest.clj (tail → panels → promote → domain facts)
            ─► distill_judge.py (periodically: compile anchor judgment into
                                  cheaper fine-tuned judges, gated)
```

**Phase 0** runs this pipeline end-to-end on the owner's real graph for the
first time and measures the number everything else is tuned by: the
**abstention rate**. **Phase 1** builds the three components that do not
depend on those measurements: the propositionizer (WP-1a), the belief layer
(WP-1b), and the SHACL shape pack (WP-1c).

## 2 · Artifact inventory (the codebase you receive)

| File | Role | Verification status |
|---|---|---|
| `judge_harness.py` | scoring, temperature fit, conformal gate, judge/calibrate/anchor-sample CLIs | **self-tested** (executable math verified: T\*-recovery, coverage 0.917≥0.90) |
| `judge_prompts.py` | injection-hardened envelope + 7 base judgment-type templates | **self-tested** |
| `zettel_prompts.py` | registers 2 zettel types (`continues`, `permanent_worthy`) into the registry | **self-tested** (16 assertions) |
| `judge_schemas.json` | 9 guided-decoding schemas (vLLM `guided_json`) | **validated** vs registry |
| `roam_harvest.py` | calibration-candidate miners for all 9 types + synthetic demo graph | **demo-run** |
| `anchor_label.py` | anchor gold labeling, `--double` self-consistency, review queue | **dry-run tested** |
| `prefilter.py` | live loop: dirty-marks → budgeted, debounced candidates | **self-tested** (12 assertions) |
| `distill_judge.py` | dataset gate, QLoRA train, McNemar audit, shadow compare, promote gate | **self-tested** (13 assertions; `train` needs GPU) |
| `mnemosyne.clj`, `rules.clj`, `judges.clj`, `ingest.clj`, `zettel.clj` | the Clojure substrate, judgment layer, consolidator, zettel layer | **hand-checked** (DataScript 1.7.3; no Clojars in the authoring sandbox — treat as reviewed-not-executed) |
| `judges_config.yaml` | judge fleet config (vLLM endpoints, families) | example |
| `microjudge_contract.md`, `zettel_addendum.md`, `README_*.md`, `mnemosyne_stack.md` | normative specs & runbooks | current |

**Rule: the verification status column is a contract.** Anything you touch in
a "self-tested" file must keep its self-test green; anything you add follows
§3.2.

## 3 · Shared engineering conventions (normative)

### 3.1 Languages, dependencies
- Python ≥3.10, **stdlib-first**. Currently allowed third-party: `openai`,
  `pyyaml`; WP-1c adds `pyshacl` + `rdflib`; WP training paths use
  `torch/transformers/peft/trl` (lazy-imported only). New dependencies require
  a one-paragraph justification in the PR.
- Clojure artifacts target DataScript 1.7.3; they are **hand-checked** until a
  JVM CI job exists (setting one up is a welcome side-quest, not in scope).

### 3.2 Testing discipline
- Every executable component ships a `self-test` subcommand exercising **all
  pure logic** with zero network/GPU. Network/LLM paths get `--dry-run`.
- LLM-dependent pipelines are tested with a **mock model function** injected at
  a seam (see WP-1a §7 for the pattern). The mock path must cover the full
  pipeline shape.
- CI = running every `self-test` + `python3 -m py_compile` on all `.py`.

### 3.3 Data contracts (canonical shapes)
- **Candidate row** (input to judging):
  `{"jtype": str, "subjects": [node-id...], "fields": {…}, "meta": {…}, "caused_by": str?}`
  — `fields` keys MUST equal `judge_prompts.REQUIRED_FIELDS[jtype]` exactly.
- **Outbox events**: `judgment.emitted {jtype, subjects, label, confidence,
  judge_id, cal_version, context_hash, self_reported:false, ts, caused_by}` and
  `judgment.abstained {…, prediction_set, order_disagreement}`.
- **Context store**: `contexts.jsonl` rows `{context_hash, jtype, fields}` —
  the content-address joins everything; never re-derive fields another way.
- **Calset row**: `{"jtype", "fields", "gold", …provenance}`.
- **Type-name boundary**: Python uses underscores (`edge_type`,
  `permanent_worthy`); Clojure uses hyphens + optional `?`
  (`:edge-type`, `:permanent-worthy?`). `ingest.clj` normalizes; **never**
  normalize anywhere else.

### 3.4 Determinism rules
- All LLM calls at temperature 0; judge randomization (label listing order) is
  seeded **from the context hash**, never the clock.
- Content-address everything cacheable: `sha256(canonical-JSON)`; re-runs must
  be free and byte-identical.

### 3.5 Provenance invariants (I1–I4, abridged)
I1 judgments are facts, never rewrites · I2 closed vocabularies under
constrained decoding · I3 confidence measured (logprobs+conformal), never
self-reported · I4 full provenance envelope on every verdict. Full text:
`microjudge_contract.md`. Violating these is a design regression, not a bug.

## 4 · Work-package map

| WP | Title | Spec | Est. | Suggested profile | Depends on |
|---|---|---|---|---|---|
| **WP-0** | First live judge (runbook + metrics) | SPEC-01 | 1 dev-day scripting + operator sessions | ops-leaning dev + the graph owner | hardware + anchor access |
| **WP-1a** | Propositionizer pipeline | SPEC-02 | 2–3 dev-days | pipeline/LLM dev | none (anchor access for live smoke only) |
| **WP-1b** | Belief layer (`belief.py` + `belief.clj` mirror) | SPEC-03 | 2 days Py + 1 day Clj | algorithms dev | none |
| **WP-1c** | SHACL shape pack + runner | SPEC-04 | 1.5–2 dev-days | semantic-web-leaning dev | none |

Dependency notes: the three WP-1 packages are mutually independent and
independent of WP-0's *results* (that's why they're Phase 1). Interfaces that
will meet later: WP-1a emits `faithful` candidates consumed by the WP-0
pipeline; WP-1b consumes the discourse edges the consolidator promotes; WP-1c
consumes a JSON-LD export of the same graph. None of these couplings block
parallel development — each spec defines its interface fixtures.

## 5 · Milestones & acceptance (program level)

- **M0 (end of WP-0):** `first_judge_report.md` exists with the abstention
  rate, label distribution, and the decision-gate verdict (SPEC-01 §8). This
  number unblocks Phase 2 tuning.
- **M1a/M1b/M1c:** each WP's Definition of Done met; **all repository
  self-tests green together** (a WP that breaks another's self-test is not
  done).
- Program-level regression command (must pass on every merge):
  ```bash
  for t in judge_harness zettel_prompts distill_judge prefilter; do
      python3 $t.py self-test || exit 1; done
  python3 roam_harvest.py demo --out-dir /tmp/reg >/dev/null
  ```
  (WP-1 components append their own self-tests to this list.)

## 6 · Out of scope for this pack (do not build)

Phase-2+ items intentionally excluded: threshold tuning, the embedding/kNN
service, dreamer integration beyond the existing `--surprisal-file` hook,
the Fluree adapter (WP-1c's shapes are its *advance party*, not the port),
the compose/manuscript RLM driver, and the first distillation run.

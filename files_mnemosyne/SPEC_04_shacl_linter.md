# SPEC-04 · WP-1c — SHACL shape pack + lint runner

**Objective:** port the linter's closed-world rules to **SHACL shapes**,
runnable today against a JSON-LD export of the graph (via `pyshacl`) and
designed to become Fluree's transaction-time gate later. This work package is
the Fluree port's **advance party**: it front-loads the riskiest translation
(closed-world Datalog negation → shapes) where it can be executed and
verified now.

**Why SHACL and not OWL (normative rationale, keep in the README):** the
linter's semantics are closed-world — *no* legal-basis edge ⇒ violation. Under
RDF/OWL open-world reasoning, absence is merely *unknown*: epistemically
lovely, forensically useless. SHACL shapes validate the data graph **as
given** — closed-world by design — which is exactly the linter's contract.
Rule: **the linter lives in SHACL, never in OWL**; open-world inference (if
ever enabled) serves derivation, not obligation.

**Deliverables:** `shapes/*.ttl` (8 shapes), `context/mnemo.jsonld`
(the @context), `shacl_lint.py` (export + lint + self-test), `fixtures/`
(per-shape conforming + violating graphs), crosswalk table (this doc §4),
README section.

**New dependencies (approved for this WP):** `pyshacl`, `rdflib` — pinned.

---

## 1 · Vocabulary & JSON-LD context (`context/mnemo.jsonld`)

Namespace `mnemo:` = `https://mnemosyne.dev/ns#` (constant; never reuse
another vocab's IRI for our terms). PROV alignment is *documented*, not
substituted: `mnemo:fromJudgment` ~ `prov:wasGeneratedBy` (note in context
comments; do not emit prov: triples in v1).

| Substrate attr | JSON-LD | Notes |
|---|---|---|
| `:node/id` | `@id` = `urn:mnemo:node:<id>` | URN scheme, deterministic |
| `:node/type` | `@type` = `mnemo:<PascalCase>` | e.g. `:discourse-edge` → `mnemo:DiscourseEdge` |
| `:edge/from`, `:edge/to`, `:edge/type` | `mnemo:from`, `mnemo:to`, `mnemo:edgeType` | edges stay REIFIED (nodes), matching the substrate |
| `:prop/stratum`, `:prop/kind`, `:prop/faithful?` | `mnemo:stratum`, `mnemo:kind`, `mnemo:faithful` | stratum values as strings `"fleeting"…` |
| `:zettel/continues` | `mnemo:continues` | ref |
| `:register/keyword`, `:register/entry` | `mnemo:keyword`, `mnemo:entry` | |
| `:judgment/*` envelope | `mnemo:judge`, `mnemo:contextHash`, `mnemo:calVersion`, `mnemo:label` | I4 integrity |
| `:derived/stale?` | `mnemo:stale` | |
| `:legal-basis` (RGPD demo attr) | `mnemo:legalBasis` | |
| `:prov/from-judgment` | `mnemo:fromJudgment` | ref, multi |

**Export adapter** (`shacl_lint.py export`): input = a graph snapshot JSON
(v1: the same node/edge dump the belief layer consumes, plus a `--roam` mode
reusing `roam_harvest.Graph` for smoke data); output = JSON-LD using the
context. Deterministic ordering (sorted by @id) so diffs are reviewable.

## 2 · Shape inventory (8 shapes — each: target, constraint, severity)

| # | Shape | Target | Constraint (SHACL core unless noted) | Severity | Origin |
|---|---|---|---|---|---|
| S1 | `MissingLegalBasisShape` | `mnemo:ProcessingActivity` | `mnemo:legalBasis` `sh:minCount 1` | Violation | `rules.clj` `:missing-legal-basis` |
| S2 | `UnsupportedClaimShape` | `mnemo:Claim` | ≥1 inbound `supports` edge: `sh:path [sh:inversePath mnemo:to]` + `sh:qualifiedValueShape` {`mnemo:edgeType "supports"`} `sh:qualifiedMinCount 1` | **Warning** (unsupported ≠ wrong; the belief layer says `accepted-undisputed`) | linter `:unsupported` |
| S3 | `OrphanPermanentNoteShape` | props with `mnemo:stratum "permanent"` (`sh:targetSubjectsOf` won't do — use `sh:targetClass mnemo:Proposition` + `sh:sparql` filter, or model stratum as class `mnemo:PermanentNote` in export; **choose the class-in-export route**: exporter adds `mnemo:PermanentNote` @type when stratum=permanent — keeps the shape core-only) | `mnemo:continues` `sh:minCount 1` **or** `mnemo:trainHead true` (via `sh:or`) | Violation | `zettel.clj` `orphan` |
| S4 | `RegisterCapShape` | `mnemo:RegisterKeyword` | `mnemo:entry` `sh:maxCount 2` | Violation | `register-overfull` |
| S5 | `JudgmentEnvelopeShape` | `mnemo:Judgment` | `mnemo:judge`, `mnemo:contextHash`, `mnemo:calVersion`, `mnemo:label` each `sh:minCount 1` | Violation | invariant I4 |
| S6 | `LiteratureStanceLeakShape` | `mnemo:StanceBasis` link | a stance's basis prop must not be `mnemo:kind "literature"` reaching it directly — `sh:sparql` constraint (SELECT stances whose basis prop has kind literature and no evidence-edge mediation) | Violation | `belief-eligible` invariant |
| S7 | `StaleWithoutTaskShape` | nodes `mnemo:stale true` (export adds class `mnemo:StaleDerived`) | ≥1 inbound open task: inverse path + qualified shape {`mnemo:status "open"`} | **Warning** | advisory pattern |
| S8 | `FaithfulGateShape` | `mnemo:PermanentNote` | `mnemo:faithful` `sh:hasValue true` | Violation | faithful gate (`zettel_addendum` §1) |

**Design rules applied above (normative):** prefer SHACL-core constraints;
where targeting-by-attribute-value is needed, the **exporter materializes a
class** (S3, S7) rather than reaching for SPARQL — only S6 genuinely needs
`sh:sparql`. Every shape carries `sh:message` (English; one sentence naming
the fix, not just the fault) and `sh:severity`.

## 3 · Port-risk flags (Fluree)

`sh:sparql` (S6) and `sh:qualifiedValueShape` (S2, S7) are the two features
whose support in Fluree's transaction-time SHACL subset must be **verified
before the Phase-3 port** — tag both shapes with a `# PORT-RISK` comment and
list them in the README. Fallback if unsupported: S6 becomes a consolidator
check (it half-is already, via `belief-eligible`); S2/S7 degrade to
advisory app-side queries. Nothing else in the pack uses beyond-core features.

## 4 · Crosswalk table (deliverable, kept next to the shapes)

One row per shape: Datalog rule text (verbatim from `rules.clj`/`zettel.clj`)
↔ shape file ↔ semantic notes (esp. where closed-world negation maps to
minCount/hasValue). This table is the Fluree port's checklist later; treat it
as documentation-with-teeth (reviewed line by line in the PR).

## 5 · Runner (`shacl_lint.py`)

```
export  --graph graph.json | --roam export.json   → out.jsonld   (deterministic)
lint    --data out.jsonld [--shapes shapes/]      → report.json + human table
self-test                                          → fixture matrix
```
- `lint` runs pyshacl with **`inference="none"`** (normative: the closed-world
  discipline — no RDFS/OWL expansion; document that Fluree's txn-time SHACL
  matches this posture).
- Report JSON: `{conforms: bool, violations: [{focusNode, shape, severity,
  message, path}]}` — sorted (focusNode, shape) for determinism.
- Exit codes: `0` conforms, `1` violations present (warnings alone still 0
  unless `--strict-warnings`), `2` runner error. CI-ready.

## 6 · Fixture matrix & self-test

`fixtures/` contains, **per shape**: `sN_ok.jsonld` (conforming) and
`sN_bad.jsonld` (exactly one violation of that shape, nothing else). Plus
`all_ok.jsonld` (a realistic combined graph passing everything) and
`kitchen_sink_bad.jsonld` (one violation of each shape simultaneously —
asserts count == 8 and the exact focus nodes).

Self-test assertions: every `sN_ok` conforms; every `sN_bad` yields exactly
that shape's violation on the expected focus node with the expected severity;
`kitchen_sink_bad` yields the full set; warnings don't flip exit code without
`--strict-warnings`; report ordering deterministic across two runs; export
adapter round-trips a Roam demo graph (reuse `roam_harvest.make_demo_export`)
without error and S1 fires on a planted basis-less ProcessingActivity node
added by the fixture builder.

## 7 · Definition of Done

- [ ] 8 shapes in Turtle, each with severity + message + origin comment;
      PORT-RISK tags on S2/S6/S7.
- [ ] Context file + exporter with deterministic output.
- [ ] Fixture matrix complete (≥ 18 files) and `self-test` green under pinned
      pyshacl.
- [ ] Crosswalk table reviewed rule-by-rule against `rules.clj`/`zettel.clj`.
- [ ] Exit-code contract honored (demonstrated in self-test).
- [ ] Repository regression green with this self-test appended.

**Estimate:** 1.5–2 dev-days (half of it fixtures — as intended).

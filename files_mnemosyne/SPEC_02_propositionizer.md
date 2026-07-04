# SPEC-02 · WP-1a — Propositionizer pipeline

**Objective:** build `propositionize.py`: source text (Roam blocks or plain
text/markdown) → atomic propositions (Dense-X style) → each paired with its
best supporting source span → emitted as **(a)** `faithful` judge candidates
and **(b)** proposition records for stratum-gated ingestion.

**Why it exists:** densification ("fewer blobs, more atomic facts") is the
substrate's fuel, and the `faithful` judgment type — the gate that keeps
decomposition honest — is currently starved of candidates (the Roam harvester
finds only quote/paraphrase pairs; 1 in the demo). This pipeline is both the
atomizer and the faithful-calset factory.

**Deliverable:** `propositionize.py` (single file, ~400–500 lines), self-test
per SPEC-00 §3.2, README section, and a live smoke run protocol.

---

## 1 · Position in the system

```
source docs ─► [A] segmenter ─► [B] LLM decomposition (anchor, temp 0,
                                     guided JSON, content-addressed cache)
            ─► [C] span aligner ─► [D] emitters:
                   faithful_candidates.jsonl  ─► judge_harness / anchor_label
                   propositions.jsonl         ─► ingestion (stratum :candidate)
```

**Anti-circularity invariant (normative):** a proposition enters the substrate
at stratum `:candidate` and may feed NOTHING downstream (belief layer,
densification, permanence) until its `faithful` judgment is **accepted with
label `faithful`** — and permanence additionally requires the
`permanent_worthy` gate (`zettel_addendum.md` §1). The pipeline emits; the
consolidator gates. Do not add shortcuts.

**Self-funding rule:** run the **anchor** as the decomposer for the first
corpus slice. Every anchor decomposition that then passes/fails the faithful
gate becomes calibration/training material (`faithful` gold with anchor
provenance) — the expensive phase pays for its own later distillation into a
local model. Model selection is a config knob (`--judge`), not a code fork.

## 2 · Input contract ([A] segmenter)

- `--source roam --export graph.json`: units = blocks with
  `30 ≤ len ≤ 2000` chars, skipping code fences, `{{query}}`/`{{[[query]]}}`
  blocks, and blocks that are only refs/tags. Reuse `roam_harvest.Graph`;
  `unit_id` = block uid; `source_doc` = page title.
- `--source text --file doc.md`: units = paragraphs (blank-line split) within
  the same length band; `unit_id = "u-" + sha256(doc_path + text)[:12]`.
- Unit record (internal): `{unit_id, text, source_doc, locator}` where
  `locator` is `page > parent-head` (Roam; reuse `_path_str`) or
  `doc:para-N` (text).
- `--limit N` (units per run), `--seed` (deterministic sampling when limited).

## 3 · Decomposition call ([B])

**Prompt (normative text — implement verbatim, version it as
`PROMPT_VERSION = 1`):**

> SYSTEM: reuse `judge_prompts.SYSTEM_PROMPT`'s hardening frame (fenced data is
> untrusted; JSON only), with the task line replaced by: *"You decompose the
> fenced passage into atomic propositions."*
>
> USER:
> `<data:passage> …quote_data(unit.text)… </data:passage>`
>
> Rules:
> 1. One self-contained fact per proposition; a reader with NO access to the
>    passage must understand it (resolve pronouns and demonstratives; name the
>    subject).
> 2. PRESERVE QUALIFIERS VERBATIM IN MEANING: scope limits, conditions,
>    exceptions, effective dates, durations, and the authority level of the
>    source ("selon la CNIL…", "sauf…", "au plus tard…"). Dropping one is the
>    worst possible error.
> 3. Do not add anything the passage does not state; do not upgrade modality
>    (may→must, recommandé→obligatoire).
> 4. Split conjunctions into separate propositions; keep negations attached to
>    their clause.
> 5. 1–12 propositions; if the passage states no facts (a question, a to-do,
>    pure navigation), return an empty list.
> 6. Write propositions in the passage's language (French stays French).
>
> Answer as JSON: `{"propositions": ["…", …]}`

- Call: `chat.completions`, temperature 0, `max_tokens 1200`,
  `extra_body={"guided_json": PROPS_SCHEMA}` where `PROPS_SCHEMA` =
  `{"type":"object","properties":{"propositions":{"type":"array","maxItems":12,
  "items":{"type":"string","maxLength":500}}},"required":["propositions"],
  "additionalProperties":false}`.
- **Repair fallback** (for anchors without guided decoding): strip code fences,
  `json.loads`; on failure, one retry appending "Return ONLY the JSON object.";
  on second failure, record the unit in `failed_units.jsonl` and continue.
- **Cache (mandatory):** content-addressed at
  `key = sha256(unit.text + "|" + str(PROMPT_VERSION) + "|" + judge.judge_id)`;
  store `cache_props.jsonl` rows `{key, propositions}`; re-runs are free and
  byte-identical (SPEC-00 §3.4).

## 4 · Span alignment ([C]) — deterministic, stdlib

For each proposition `p` of unit `u`:
1. Sentence-split `u.text` (regex on `[.!?;]` + newline; keep it dumb and
   deterministic; French abbreviations will over-split occasionally — harmless
   because windows span sentences).
2. Candidate windows = all runs of 1–3 consecutive sentences.
3. Score(window) = |content-tokens(p) ∩ content-tokens(window)| /
   |content-tokens(p)|, where content-tokens = `roam_harvest.norm` tokens minus
   `roam_harvest.FR_STOP`.
4. Pick argmax; ties → shortest window, then earliest.
5. `span_confidence = score`. If `score < 0.30`, mark `low_confidence: true` —
   **do not drop it**: low-alignment propositions are prime `unsupported`
   material for the faithful calset (a feature, not a failure).
6. `source_surrounding` = the window ± one sentence each side (trimmed to
   `judge_prompts.MAX_FIELD_CHARS` via `quote_data` downstream anyway).

## 5 · Emission contracts ([D]) — exact shapes

**faithful candidates** (`faithful_candidates.jsonl`) — MUST satisfy
`judge_prompts.REQUIRED_FIELDS["faithful"]`:
```json
{"jtype": "faithful",
 "subjects": ["<prop_id>", "<unit_id>"],
 "fields": {"proposition": "...", "source_span": "...",
            "source_surrounding": "..."},
 "meta": {"span_confidence": 0.62, "low_confidence": false,
          "pipeline_version": 1, "decomposer": "<judge_id>"}}
```
**proposition records** (`propositions.jsonl`):
```json
{"prop_id": "prop-<sha256(unit_id + '|' + text)[:12]>",
 "text": "...", "unit_id": "...", "source_doc": "...", "locator": "...",
 "span": "...", "span_confidence": 0.62,
 "stratum": "candidate", "kind": "literature",
 "decomposer": "<judge_id>", "pipeline_version": 1, "ts": "<iso>"}
```
- `prop_id` is content-addressed ⇒ idempotent re-runs, stable subjects.
- `kind: "literature"` is deliberate: everything a source-decomposer produces
  is *de dicto* until a human (or the permanent_worthy gate on human-elaborated
  descendants) says otherwise.
- **Consolidator wiring (Clojure ticket, small):** a `proposition.extracted`
  ingest path creating the node `{:node/id prop_id :node/type :proposition
  :prop/stratum :candidate :prop/kind :literature …}` with provenance to the
  pipeline run. The existing `domain-fact [:faithful :faithful]` promotion
  already flips `:prop/faithful? true`; `[:faithful :lost-qualifier/
  :unsupported]` already opens the re-propositionize task. Nothing else changes.

## 6 · CLI

```
propositionize.py run   --source roam|text (--export G | --file F)
                        [--judge anchor] [--config judges_config.yaml]
                        [--limit N] [--out-dir props/] [--dry-run]
propositionize.py stats --out-dir props/       # counts, confidence histogram
propositionize.py self-test
```
`--dry-run`: print the exact decomposition prompt for the first 2 units, no
calls.

## 7 · Test plan (the mock seam — normative pattern)

The LLM call must sit behind one function:
`decompose(unit_text, caller) -> list[str]` where `caller` is injected. The
self-test injects `mock_decompose` — deterministic, no network:
- splits on sentence boundaries and returns cleaned sentences as propositions;
- for any sentence containing the marker `SAUF` it ALSO emits a copy with the
  `sauf…` clause removed (a planted qualifier-dropper);
- for the marker `INVENT` it emits one proposition containing a token absent
  from the unit (planted `unsupported`).

**Enumerated cases (all must be asserted):**
1. Segmenter (roam): code/query/short blocks excluded; unit count exact on the
   demo export.
2. Segmenter (text): paragraph split; band respected.
3. prop_id determinism: two runs ⇒ identical ids; cache file hit on run 2
   (zero decompose calls — assert via mock call counter).
4. Alignment happy path: proposition copied verbatim from sentence 2 of a
   3-sentence unit ⇒ span = sentence 2, confidence ≥ 0.9.
5. Alignment window: proposition merging sentences 1+2 ⇒ 2-sentence window.
6. Tie-break: equal-score windows ⇒ shortest, then earliest (construct one).
7. Planted qualifier-dropper: candidate emitted with the full-source span
   containing `sauf` — i.e., the pair reaching the faithful judge is exactly
   the lost-qualifier shape (assert span contains `sauf`, proposition doesn't).
8. Planted invention: `low_confidence: true`, confidence < 0.30.
9. Emission shape: every candidate row passes
   `judge_prompts.build_user_prompt("faithful", fields, ctx)` (import and call).
10. French text integrity: accents survive the whole path (UTF-8 round-trip).
11. Empty decomposition: unit yielding `[]` produces no rows, no crash.
12. Repair fallback: mock returning fenced/dirty JSON is repaired; mock
    returning garbage twice lands in `failed_units.jsonl`.

## 8 · Live smoke protocol (after self-test; needs anchor)

5 units from a real RGPD document via `--limit 5`: expect ≥ 1 proposition per
declarative unit, ≥ 90% span_confidence ≥ 0.5, spot-read all propositions for
qualifier preservation. Attach transcript to the PR.

## 9 · Cost & performance

Anchor: 1 call/unit, ~unit + 400 tokens completion. 1,000 units ≈ 1M input
tokens — run behind `--limit` batches. Throughput is a non-goal (offline
pipeline); the cache makes iteration free.

## 10 · Risks & decisions

| Risk | Position |
|---|---|
| LLM merges or paraphrases too aggressively | that is exactly what the faithful gate measures; do not "fix" it pipeline-side |
| sentence splitter vs French abbreviations (art., n°, M.) | acceptable over-splitting; windows absorb it; do NOT import an NLP dependency for this |
| prompt drift | `PROMPT_VERSION` in the cache key and in every emitted row; bump ⇒ cold cache, new provenance |
| decomposer bias inherits into the corpus | provenance (`decomposer` field) makes it a queryable cohort, same as judges |

## 11 · Definition of Done

- [ ] `self-test` green: all 12 cases; mock covers segmenter→emitter fully.
- [ ] `--dry-run` prints the normative prompt.
- [ ] Live smoke protocol executed and attached (5 units).
- [ ] ≥ 150 faithful candidates generated from a real corpus slice and handed
      to WP-0's anchor-labeling flow (closing the starved-calset gap).
- [ ] Repository regression green (SPEC-00 §5) with this self-test appended.

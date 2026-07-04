# Contract addendum — the Luhmann–Ahrens (Zettelkasten) layer

*A drop-in module over the Mnemosyne substrate and the micro-judge contract.
Extends `microjudge_contract.md`; nothing here overrides it. Files:
`zettel.clj` (substrate module, hand-checked), `zettel_prompts.py` (judge
prompts, self-tested), the two new schemas in `judge_schemas.json` (validated),
and the wiring notes at the foot of `zettel.clj`.*

## 0 · Why this layer exists

Luhmann's slip-box and Ahrens' distillation of it encode ~12 design
commitments. Most are already in Mnemosyne under other names (immutability =
fixed addresses; threshold-reification = emergent *Schwerpunkte*; the dreamer =
"communication with slip boxes"). This layer imports the few that were missing
or thin — all of them concerning **succession, scarcity, strata, and the human
in the loop** — without disturbing anything below it. The split is clean
because Luhmann's contributions are *structural* (and the substrate already had
most) while Ahrens' are *cognitive* (and those are exactly where a substrate is
silent).

## 1 · Strata invariant (the spine)

A proposition's `:prop/stratum` is one of:

| stratum | meaning | belief layer? | densification? | decay? |
|---|---|---|---|---|
| `:fleeting` | raw capture, unprocessed | no | no | yes (activation only) |
| `:candidate` | machine-proposed permanent | no | yes | no |
| `:literature` | *de dicto* — "Source S asserts X" | only as evidence | yes | no |
| `:permanent` | *de re* — "we hold X" | **yes, directly** | yes | no |

The load-bearing rule: **only `:permanent` propositions feed stances directly;
`:literature` enters the belief layer only as typed support/oppose evidence.**
This is the formal version of Ahrens' literature-vs-permanent split, and for
the RGPD work it is the line between "the CNIL guidance states" and "we hold."
Enforced by the `belief-eligible` rule in `zettel.clj`; the belief layer must
filter its inputs through it.

## 2 · Two new judgment types

Both register into the existing harness via `zettel_prompts.py` with no harness
changes (they mutate the `judge_prompts` registry on import).

### `continues` — Folgezettel succession  *(stakes: T1)*
- Labels: `continues` / `branches-from` / `new-train`.
- Subjects-vec `[child, parent]`, **directional** — listed in
  `CANONICAL_ORDER_ONLY`, never role-swapped (same discipline as `dedup_prop`'s
  `subsumes`). The caller fixes child/parent; the judge does not re-derive them.
- Required fields: `child`, `child_context`, `parent`, `parent_context`.
- Policy (in the anchor guidance): succession is **dialogical, not topical** —
  same-subject notes that do not develop one another are `new-train`. A healthy
  graph is many short trains, not one mega-train; when the link is weak,
  `new-train` is the safe, recoverable default (a missing edge is cheaper to add
  later than a false one is to find).
- Promotion writes `:zettel/continues` (for `continues`/`branches-from`) or
  marks a train head (`new-train`), via `continues-fact` / `new-train-fact`.

### `permanent_worthy` — the candidate→permanent gate  *(stakes: T2)*
- Labels: `promote` / `keep-candidate` / `discard`.
- Single subject (a candidate-stratum proposition, typically harvested from a
  project branch — see §5).
- Required fields: `candidate`, `origin_context`, `nearest_permanent`.
- Policy: **precision over recall** — the permanent stratum is the de re layer
  feeding beliefs, so a wrong promotion silently corrupts stances; when in
  doubt, `keep-candidate`. Verbatim restatements are literature, not permanent.
  Notes that need their origin context are not yet self-contained.
- T2 ⇒ heterogeneous-panel agreement (k-of-n distinct families) per the base
  contract; promotion flips `:prop/stratum :permanent`.

Wire-name note: Python underscores (`permanent_worthy`), Clojure hyphens-plus-?
(`:permanent-worthy?`); `ingest.clj`'s `py<->clj-type` normalizer bridges them.

## 3 · CALM placement (what distributes, what is single-writer)

| Mechanism | Side | Rationale |
|---|---|---|
| `train` / `in-train` closure, `belief-eligible`, `register-member`, `bridge-seed` | **monotone core** | positive recursion over immutable facts; distributes across Hermes nodes |
| `continues` / `permanent_worthy` emission | **monotone core** | judgments are appended facts (invariant I1) |
| orphan detection (`not-join` over permanent) | boundary-adjacent | negation; evaluated in the consolidator's projection |
| register consolidation (keep top-`cap` doorways) | **non-monotone** | retracts entries; consolidator-only |
| candidate→permanent promotion | **non-monotone** | stratum flip; the single promotion gate |
| fleeting decay + triage | **non-monotone** | mutates activation, opens tasks; consolidator-only |
| morning-dialog bridge proposals | **non-monotone** | opens tasks (writes); selection budgeted in the consolidator |

The principle is unchanged from the base contract: signal *accumulation* and
*judgment* are monotone and free to distribute; *selection, promotion, decay,
and retraction* are the single-writer boundary.

## 4 · The first honest home for decay (Lethe, scoped)

The cognitive-limits review flagged that Mnemosyne had no forgetting. It belongs
**only in the fleeting stratum**, and only as *activation* decay — never on the
record. `daily-inbox-behavior` runs an ACT-R-style base-level decay
(`decay-activation`, λ∈(0,1)) on untouched fleeting notes and opens a one-shot
triage task per note. The event log keeps every fleeting capture forever; only
its salience fades. This reconciles Luhmann's *Schrott* tolerance ("keep the
junk, select at use-time") with Ahrens' inbox hygiene ("process within a day"):
nothing is lost, but unprocessed scraps stop competing for attention. A
dismissed scrap that later turns out to matter is still in the log, replayable
`as-of` any time.

## 5 · Project branches and the harvest (Ahrens' project notes)

Project scaffolding lives on a **fork** (Fluree branch in the target; a frame
stack in DataScript today), keeping orderings, drafts, and to-dos out of main.
At project end, a harvest pass runs `permanent_worthy` over the branch's
candidate nodes; `promote` verdicts merge into main as `:permanent`, the rest
stay `:candidate` or are dropped, and the branch is **archived whole, never
deleted** — the project's process remains replayable. "Discard" becomes
"archive with provenance," which is strictly stronger than Ahrens' bin.

## 6 · The elaboration loop (the most important import)

Ahrens' core cognitive claim: understanding is produced by *elaboration* —
reformulating in your own words, connecting, contradicting. Mnemosyne automates
the mechanical steps, which risks "the collector's fallacy industrialized." The
countermeasure is to **reinstall friction exactly where it constitutes
learning** and nowhere else:

1. **Elaboration tasks** — when a contradiction lands on a relied-upon claim, or
   a cluster crosses the summarize threshold, open a *human* task: "two or three
   sentences, in your words: how does X bear on Y?" The answer enters as a
   proposition with `:source/family :human`.
2. **This closes the economic loop with distillation.** `distill_judge.py`
   already ranks `:source/family :human` as the top-priority training gold; so
   **your elaborations become the best training data in the system.** Ahrens'
   learning loop and the swarm's improvement loop are the same loop.
3. **Drafts as provocations** — machine summaries are *proposals* needing the
   30-second confirm-or-edit; the edit-delta is itself signal (what you changed
   = what the machine got wrong = training data; what you left = endorsement).
4. **Elaboration-coverage metric** — `elaboration-coverage` reports, per train,
   the human/total ratio of permanent notes. A dense train with zero human
   elaboration is flagged as *your* unbacked understanding — not a system fault.

## 7 · The sparse register (Luhmann's doorways)

`:register/keyword` nodes hold **at most `register-cap` (=2) entries**. Bloat is
a linter violation (`register-overfull`); `register-consolidation-behavior`
keeps the top-`cap` by **centrality × trail-weight** (structure and use must
agree) and retracts the rest *as entries* (they remain nodes). The register is
versioned, so a field's doorway can be watched migrating over years. Payoff: an
O(1) "where do I enter for topic X" primitive for the RLM (better-curated than
search), and a structural brake on tag-soup — the failure mode the densification
ledger warned about ("when everything connects, connection means nothing").

## 8 · The box speaks first (Luhmann 1981)

`morning-dialog-behavior` selects a daily budget of **bridge candidates** —
embedding-near pairs (`:sim/near`) in *different* trains with no short graph
path — and opens them as questions ("these two trains have never met; related?").
The `bridge-seed` rule yields seed pairs; the k-hop "no short path" refinement
is applied in code (`select-bridges`, a BFS the rule can't express). This is the
anti-entrenchment exploration term given a concrete daily form, and it upgrades
the dreamer from monitor to interlocutor. Responses are themselves judgments or
elaborations — feeding §6.

## 9 · The manuscript loop (`compose`)

`compose-assembly` builds a draft context from a register doorway or a claim:
the relevant **train(s)** (Folgezettel runs) interleaved with **summaries at all
levels** (collapsed-tree retrieval). The RLM drafts against that assembly; every
assertion must resolve to a proposition or it opens a gap-task (the linter
pattern); and the draft records `:used-in` edges and strengthens the trails it
walked — so **writing feeds back as first-class usage data**. Luhmann's
manuscripts were the implicit use-trace of his box; here it is explicit. The
draft itself is a project-branch artifact (§5).

## 10 · Schema & cost summary

Added: four attributes (`:zettel/continues`, `:prop/stratum`, `:prop/kind`,
`:register/keyword` + small companions), two judgment types (`continues`,
`permanent_worthy`), three behaviors (daily inbox, register consolidation,
morning dialog), one rule family (trains / register / bridges / belief-eligible /
orphan), one workflow (`compose`). No changes to the harness, the conformal
gate, the promotion machinery, cohort retraction, or distillation — those pick
up the new types for free.

## 11 · Honest notes

- `zettel.clj` is **hand-checked against DataScript 1.7.3, not executed** (no
  Clojars in the build sandbox) — same status as the rest of the substrate.
- `zettel_prompts.py` and the two schemas **are executable and self-tested**
  (`python3 zettel_prompts.py`; enums validated against the prompt registry).
  The base harness self-test stays green with the registry mutation in play.
- `:sim/near` edges (the bridge detector's input) presume the regime-B
  embedding layer is live; until then, `morning-dialog` yields nothing — it
  fails closed, not noisily.
- `continues` candidates are best generated from the embedding layer (kNN
  proposes parents); a lexical fallback in `roam_harvest.py` is possible but
  will under-propose, exactly as the `faithful` harvester does.
- The tensions (friction, voice, scale) are addressed by *policy* (§§6–7), not
  by code that can prove them — they are design commitments to hold, not
  invariants the system enforces.

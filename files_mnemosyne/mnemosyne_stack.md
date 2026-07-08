# Mnemosyne — a stacked substrate for recursive, auditable, self‑improving agents

*Working name: **Mnemosyne** (memory; mother of the Muses) — a deliberate pair to your **Hermes** multi‑agent framework. Rename at will. The Lethe/Mnemosyne duality — forgetting vs. remembering — is exactly the persistence‑vs‑context‑rot tension this design resolves.*

This document specifies the target stack we converged on and wires every layer and mechanism back to the five themes from the analysis. It is the spine; the companions are:

- `mnemosyne.clj` — a runnable L2/L3 substrate + an L1‑flavoured RGPD demo (DataScript).
- `rules.clj` — the three recursive Datalog rule families (recursion‑tree, linter, provenance).
- `stack.dot` / `stack.svg` — the three‑layer diagram with the CALM strata marked.

---

## 0. The one idea, restated

All three source systems perform the *same inversion*: take what the field treats as **disposable byproduct** and promote it to the **load‑bearing substrate**, then make computation a matter of **recursively navigating and monotonically growing** that substrate — with the engine *beside* the substrate, not ingesting it.

| System | Byproduct, normally | Promoted to substrate |
|---|---|---|
| ActiveGraph ("the log is the agent") | the event log (audit exhaust) | source of truth; the mind is a *projection* of it |
| RLM ("recursive language models") | the prompt (fed into the transformer) | an *external object* the model probes with code + recursive self‑calls |
| Datomic / Roam | the database (a mutable place) | an append‑only log of immutable facts; "now" = fold(log) |

Mnemosyne is that single sentence written **as a stack**, so each layer supplies to the layer above exactly the property that layer cannot get for free.

---

## 1. The stack at a glance

```
            ┌───────────────────────────────────────────────────────────────┐
   L1       │  RECURSIVE INFERENCE  (RLM-style)                              │
            │  root model · REPL-over-the-graph · recursive sub-calls        │
            │  the "context object" is L3's graph, not a flat string         │
            └───────────────▲───────────────────────────────┬───────────────┘
                            │ query the graph                │ append facts
            ┌───────────────┴───────────────────────────────▼───────────────┐
   L2       │  EVENT-SOURCED RUNTIME  (ActiveGraph-style)                    │
            │  behaviors react to graph-shape patterns · reactive FIXPOINT   │
            │  content-addressed cache · fork / frame · NO orchestrator      │
            └───────────────▲───────────────────────────────┬───────────────┘
                            │ fold / replay                  │ emit events
            ┌───────────────┴───────────────────────────────▼───────────────┐
   L3       │  IMMUTABLE BITEMPORAL DATALOG STORE  (Datomic / XTDB)          │
            │  append-only log · recursive rules · as-of/with/history        │
            │  reified-tx provenance · monotone core = coordination-free     │
            └───────────────────────────────────────────────────────────────┘
```

| Layer | Role | Inherits for free (from below) | Provides upward | Breaks without the layer below |
|---|---|---|---|---|
| **L1** Recursive inference | Decompose a task/prompt the model can't hold at once; recurse on slices; assemble output in variables | Structure‑aware decomposition (query, not regex); persisted, queryable sub‑results | Unbounded effective input/output; adaptive compute | Decomposition degrades to blind chunking; sub‑results are lost in a transcript |
| **L2** Event‑sourced runtime | Turn agent action into events that react to a shared graph; coordinate without a script | Time travel, fork, provenance, recursion, incremental views | Emergent control flow; deterministic replay; cheap counterfactual forks | State scatters across prompt/code/DB; replay & fork become impossible |
| **L3** Datalog store | Hold the append‑only log; project state; answer recursive + temporal + provenance queries | — (it is the floor) | Provable‑termination recursion; bitemporal time travel; lineage as a query; monotone → distributable | — |

---

## 2. Layer contracts

### L3 — Immutable, bitemporal Datalog store

**What it is.** An append‑only log of immutable facts. The current database is a deterministic function of the log up to a chosen time. Recursion is the *native* operation (recursive rules), with least‑fixpoint semantics handling iteration, dedup, and **provable termination on finite data**.

**Key primitives.**
- `project(events)` — fold the log into a db value. `project(take k log)` = the world as of event `k`. *On a real store this is `as-of` / `since` / `history`; XTDB adds valid‑time (true bitemporality).*
- `with` / `db-with` — a *speculative* db value that does not persist. This **is** the fork/frame primitive.
- Recursive Datalog rules — `descendant`, `unresolved`, `event-chain`, `derivation` (see `rules.clj`).
- Reified transactions — every datom carries its asserting event; provenance is queryable.

**Ties back.** Theme 1 (recursion with free termination); Theme 4 (this layer *is* "the log is the agent": `db-with` ≈ fork, `as-of` ≈ replay, reified‑tx ≈ lineage); Theme 5 (everything below).

### L2 — Event‑sourced runtime

**What it is.** ActiveGraph's inversion. The event log is the source of truth; the working graph is `fold(log)`; **behaviors** subscribe to graph‑shape patterns and emit new events; there is **no orchestrator**. Determinism over nondeterministic model calls is achieved by a **content‑addressed response cache**, so replay/fork serve recorded responses by prompt hash.

**Key primitives.**
- `append!` — the only way state changes; stamps provenance + reifies the event.
- `run-to-fixpoint` — fire behaviors on *new* matches until none fire (a fixpoint) or a budget halts a runaway cascade.
- `fork` (durable, branchable) vs `frame` (lightweight, reconverging) — the durability decision rule.
- `llm-call` — first run live + record; replay from cache.

**Ties back.** Theme 2 (input/context/output collapse into one substrate — the log); Theme 3 (the fixpoint loop *is* the lint/improvement loop; self‑modification is itself an event, so fork‑and‑diff is a self‑improvement evaluation primitive); Theme 1 (the cascade is recursion you didn't hand‑code; the budget is the honest tradeoff).

### L1 — Recursive inference

**What it is.** RLM's inference paradigm, **upgraded**: the "external object" the root model probes is not a flat string it greps, but **L3's immutable graph** it queries. The root sees only metadata; it writes code that (a) issues recursive Datalog queries to decompose, (b) launches sub‑calls on slices, (c) assembles output into variables that are *written back as facts*. Each sub‑call's result is a first‑class, queryable datom — not a line in a transcript that can be discarded.

**Key primitives.** The RLM REPL, with two changes from the paper: `peek/decompose` are queries over L3; intermediate results are persisted to L2/L3 as events. A behavior body in L2 *may itself be an RLM* — that is the reflective‑tower hook (depth > 1).

**Ties back.** Theme 5e (context‑as‑graph instead of context‑as‑string → structure‑aware decomposition; sub‑results persist, mitigating the "discards good work" pathology); Theme 5d (the recursion tree is reified, so steering it is a query); Theme 2 (the prompt persists as an external, queried object — persistence *without* linear ingestion, which is the answer to context rot).

---

## 3. How the five themes are realized (cross‑reference)

| Theme (from the analysis) | Mechanism in the stack | Layer | Where to see it |
|---|---|---|---|
| **1. Recursion as an inherited property; low compute & design cost** | Recursive rules (2 clauses → unbounded depth, free termination); reactive cascade; adaptive sub‑calls; the budget as the honest cost ceiling | L3 / L2 / L1 | `rules.clj` `descendant`; `mnemosyne.clj` `run-to-fixpoint`; spec §2 |
| **2. One persistent environment; each step builds on all prior** | Everything is an event in one log; graph = `fold(log)`; prompt + intermediates + output all live in the substrate; persistence via *query*, not linear scan (the context‑rot answer) | L2 / L3 | `append!`, `project`; spec §0, §2 |
| **3. Steering emergence: structure + reflection + linting loops** | Subscription patterns & relation‑behaviors (structural steering); critic/linter behaviors (reflection); **fixpoint loop = semi‑naïve eval = lint loop**; reflective tower via RLM‑as‑behaviour‑body | L2 / L3 | `linter-behavior`; `run-to-fixpoint`; `rules.clj` `linter`; diagram dotted edge |
| **4. A Roam/Datomic DB can implement "the log is the agent"** | `db-with` ≈ fork, `as-of`/fold ≈ replay, reified‑tx ≈ lineage; the whole of L3 | L3 | `fork`, `frame`, `project`, `why`; spec §2 (L3) |
| **5. Datalog/Datomic uniquely suited for the recursion** | (a) incremental recompute → cheap self‑improvement; (b) provenance as a recursive query → RGPD audit; (c) time travel + speculative fork; (d) recursion tree as queryable relation → declarative meta‑control; (e) context‑object as graph; (f) monotone core → coordination‑free distribution (CALM) | all | `rules.clj` (all); `structural-diff`, `why`; diagram CALM strata |

---

## 4. The reference implementation (`mnemosyne.clj`)

A miniature **RGPD compliance pipeline** that exercises every property:

1. **Seed** — the user declares one *processing activity* (the goal). One event.
2. **Plan** — `activity->questions` reacts to an activity with no child questions and emits three *open* questions (the recursion tree expands: `:task/parent`, `:task/status :open`).
3. **Research** — `question->finding` (the "researcher"; its model call goes through `llm-call`) turns each open question into a *finding* + *evidence* + a `:supports` edge, and marks the question done. It contains a **realistic bug**: it only attaches a legal basis when the question literally mentions one — so the *data‑categories* and *EEA‑transfer* findings end up with **no legal basis**.
4. **Lint (fixpoint)** — `linter-behavior` reacts to a *violating, not‑yet‑flagged* finding: it flags it **and re‑opens a corrective sub‑task**. The corrective question mentions "legal basis", so on the retry the researcher attaches one and the loop reaches a **clean fixpoint**. This is generate→check→repair as semi‑naïve evaluation.

Then the demo exercises the rest of the stack:

- **Provenance** — `why db "act-1/q3->finding"` returns the `(event, actor)` chain back to the original goal. *Lineage is a recursive query, not a log line.* (Theme 5b — your RGPD audit story, architecturally.)
- **Recursion meta‑control** — `frontier` / `unresolved` show the open work; at the fixpoint both are empty. (Theme 5d.)
- **Self‑improvement via fork‑and‑diff** — `fork` the run *before any finding exists*, re‑run with the **fixed** researcher (`question->finding-fixed`, which always documents a legal basis), then `structural-diff` parent vs. fork. The diff shows the violations existing **only in the parent** and the legal‑basis edges existing **only in the fork** — a cheap, honest counterfactual evaluation of a proposed change. (Theme 3 / ActiveGraph §7.)

**Run it:** `deps.edn → {:deps {datascript/datascript {:mvn/version "1.7.3"}}}`, then `clojure -M -m mnemosyne.core`, or `(mnemosyne.core/demo)` in a REPL. The `comment` block shows the illustrative output shape.

---

## 5. The rule sets (`rules.clj`) and why each is recursive Datalog

| Family | What it computes | Recursion | Monotone? |
|---|---|---|---|
| `recursion-tree` | `descendant` (transitive closure of the sub‑call tree), `unresolved`, `frontier` | yes — the canonical 2‑clause closure | core monotone; `frontier` non‑monotone (negation) |
| `linter` | `violation` (a finding missing legal basis or evidence) | via the reactive loop's fixpoint | **non‑monotone** (negation‑as‑failure) |
| `provenance` | `event-chain` (closure over causation), `derivation` | yes — recursive | monotone |

The point of §5: the three things the agentic layers most need — **navigate a recursive structure, check‑and‑repair to a fixpoint, and explain a result** — are all *recursive Datalog*, which L3 provides with termination guarantees the agentic layers cannot supply themselves (Theme 1).

---

## 6. The CALM strata (`stack.svg`) — what you can distribute across Hermes nodes

The **CALM theorem** (Consistency As Logical Monotonicity): a program has a coordination‑free, eventually‑consistent distributed implementation **iff** it is monotone. The practical consequence for your multi‑machine setup:

- **Monotone core** — append + positive recursion (`descendant`, `unresolved`, `event-chain`, `derivation`, the projection itself). Run these across as many Hermes nodes as you like, each appending to the log; the views **converge regardless of interleaving, with no coordination.** This is the principled answer to the distributed‑ordering question ActiveGraph explicitly leaves open.
- **Non‑monotone boundary** — negation (`violation`, `frontier`), aggregation (e.g. "deepest open task" = a `max`), and retraction. These need a **coordination point** — give them their own stratum and a single logical writer per run.

**Design rule:** keep the consistency‑critical logic monotone; quarantine non‑monotone steps behind strata. **Dedalus** (Datalog + logical time) is the formalism to read if you want to push this hard; **Differential Dataflow / Materialize / DDlog** give you the incremental evaluator for it.

---

## 7. Limits and the upgrade path

| Limit in the sketch | Why | Upgrade |
|---|---|---|
| DataScript is in‑memory, single‑writer, **not bitemporal** | it's the Roam engine, great for the client layer | swap L3 for **Datomic / Datahike / XTDB**; `project(take k)` → native `as-of`; XTDB → valid‑time. *This also fixes ActiveGraph's "replay the whole log" cost: indexed historical access instead of a full fold.* |
| Reactive loop is **naïve** (re‑projects each round) | simplicity | **Differential Dataflow / Materialize / DDlog** — same rules, incremental evaluator; self‑improvement cost ∝ delta (Theme 5a) |
| RLM recursion is effectively **depth‑1** | matches the paper's instantiation | let an L2 behaviour body *be* an RLM → a reflective tower (Theme 3); the diagram's dotted edge marks the hook |
| The **projection→prompt** layer is implicit | the model ultimately reads tokens | make context assembly a first‑class Datalog query that renders to a prompt — the point, not a flaw |
| Single‑writer **write throughput** | Datomic transactor / DataScript conn | partition per run (runs are independent) or push consistency‑critical logic into the monotone core (CALM) and distribute |
| Agent prose is **unstructured** | Datalog is for structured facts | hybrid: Datalog for structure/provenance + a vector index for semantics (your structural+semantic approach) |

---

## 8. Build order (what to wire first)

1. **L3 floor on a real store.** Stand up XTDB (bitemporal, append‑only, Datalog) or Datomic. Define the event/object/edge schema. Verify `as-of`, `with`, and a recursive rule. *You already have the muscle memory from Roam/DataScript.*
2. **L2 log + projection + replay.** Port `append!` / `project` / `run-to-fixpoint`; prove deterministic replay with the content‑addressed cache.
3. **Provenance + linter rules.** Port `rules.clj`; confirm `why` and `violation` queries; this is the RGPD‑audit backbone — land it early.
4. **L1 over the graph.** Wire a real model into `llm-call`; have the root issue Datalog queries to decompose and write sub‑results back as events.
5. **Fork‑and‑diff loop.** Turn `structural-diff` into the evaluation harness for proposed behaviour/prompt/rule changes — your self‑improvement loop.
6. **Distribute the monotone core.** Identify the strata; run the monotone core across Hermes nodes; keep non‑monotone steps single‑writer.

---

### One‑line summary

An **RLM‑style recursive inference engine**, running over an **ActiveGraph‑style event log**, where the log is a **bitemporal Datalog store** — so that incremental self‑improvement, recursive‑query‑driven context assembly, derivation‑level provenance for RGPD, and CALM‑guaranteed distributed convergence are *inherited substrate properties* rather than things you build by hand. Each of those four is a stated limitation or future‑work item in at least one of the two papers.

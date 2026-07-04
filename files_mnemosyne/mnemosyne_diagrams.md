# Mnemosyne — the visual atlas

*Thirteen Mermaid diagrams covering the whole logic, the data flows, the components,
and the software choices at every stage. Each diagram also ships as a standalone
`.mermaid` file (rendered natively by the interface and most tooling). Sources are
embedded below so this document is self-contained and Roam/Logseq-pasteable.*

| # | Diagram | One-line scope |
|---|---|---|
| 01 | The whole logic in one frame | The three-layer Mnemosyne stack (RLM inference over an ActiveGraph-style event runtime over a datom-family immutable store), with the B-half judgment ladder feeding the consolidator, the propagation/emergence layer as a consumer-and-producer of the log, and software stamps at each station (DataScript for the working projection, Fluree as the target ledger, vLLM + judge_harness for the swarm). |
| 02 | The one pattern under everything | Every mechanism in the project is an instance of: a signal accumulates along the graph, crosses a threshold, and reifies a first-class provenanced node, which feeds back. |
| 03 | Data flow, cradle to flywheel | The four loops and how they hand off: calibration (offline, per judge version), the live judging loop (pre-filter to promotion to graph and back), the audit loop (anchor sampling to drift to quarantine to cohort retraction), and the distillation loop (provenance-gated dataset to QLoRA to shadow to the promote gate). |
| 04 | Lifecycles: judgment and judge | Two state machines. |
| 05 | One judgment, end to end | The wire-level story of a single edge-type judgment: per-label echo scoring against vLLM (shared prefix cached), temperature scaling and the conformal gate in the harness, the outbox append, idempotent tailing by the consolidator, anchor supremacy versus T2 panel arbitration, and the escalation round-trip. |
| 06 | The regime ladder and distillation gravity | Cheapest-regime-first with abstention upward (A heuristics, B classifiers, B-half small-LLM judges, C anchor) and the countercurrent flowing down: anchor traces distill into judges, stable judge behavior compiles into classifiers, stable patterns compile into rules. |
| 07 | Calibration and distillation, with the anti-collapse rails | From admissible sources (provenance-gated: human over double-pass anchor over anchor; equal-tier conflicts dropped) through the deterministic hash-bucket split (the audit set freezes itself), QLoRA on the 3090, McNemar-tested audit evaluation, shadow comparison, and the three-outcome promote gate. |
| 08 | Drift, quarantine, cohort retraction | The immune system: anchor sampling produces agreement facts; drift per (type x judge-version) triggers reversible quarantine; systematic bias triggers cohort retraction via the taint closure -- with nothing ever deleted, so the mistake remains queryable as-of any past time. |
| 09 | The data model (entity-relationship view) | The judgment layer's schema as deployed in judges. |
| 10 | Deployment topology and software choices | The physical system over the Tailscale mesh: prefill-heavy judging on Machine B's dual 3090s (vLLM with prefix caching; QLoRA runs there too), the third judge family and the runner on Machine A, the consolidator JVM on the Mac, and the NAS as the home of the ops/ JSONL exchange, the (planned) Fluree ledger, and Hermes services. |
| 11 | The Fluree hybrid L3 (the Athens split, instantiated) | DataScript stays the in-process working projection -- rules. |
| 12 | The CALM split (what distributes, what does not) | The architecture's standing discipline: the monotone core (appends, emissions, positive recursion, counters, pooled embeddings, reasoner materialization) is coordination-free across Hermes nodes; the non-monotone boundary (negation, promotion, stances, invalidation, retraction) belongs to the single-writer consolidator. |
| 13 | Build roadmap and current status | What is done (specs, substrate, contract, harness, calibration tooling, ops service, distillation -- self-tested where executable), what is next (first live edge_type judge on the real graph; wiring the dreamer surprisal pre-filter), and what follows (Fluree adapter, propositionizer, first distillation pass, belief layer live). |

## 01 · The whole logic in one frame

The three-layer Mnemosyne stack (RLM inference over an ActiveGraph-style event runtime over a datom-family immutable store), with the B-half judgment ladder feeding the consolidator, the propagation/emergence layer as a consumer-and-producer of the log, and software stamps at each station (DataScript for the working projection, Fluree as the target ledger, vLLM + judge_harness for the swarm). Companions: mnemosyne_stack.md, stack.svg.

```mermaid
flowchart TB
  classDef l1 fill:#faf5ff,stroke:#805ad5,stroke-width:2px
  classDef l2 fill:#ebf8ff,stroke:#2b6cb0,stroke-width:2px
  classDef l3 fill:#f0fff4,stroke:#2f855a,stroke-width:2px
  classDef jl fill:#fff5f7,stroke:#9b2c2c,stroke-width:2px
  classDef sw fill:#fefcbf,stroke:#975a16

  subgraph L1["L1 · RECURSIVE INFERENCE — RLM style"]
    ROOT["root model sees metadata only<br/>(anchor LLM, API or local)"]
    REPL["REPL over the graph<br/>peek and decompose are Datalog queries"]
    SUB["recursive sub-calls on slices<br/>results written back as facts"]
    ROOT --> REPL --> SUB
  end

  subgraph JL["Regime ladder — B-half judgment layer"]
    LADDER["A heuristics → B classifiers →<br/>B½ small-LLM judges → C anchor<br/>(judge_harness.py + vLLM)"]
  end

  subgraph L2["L2 · EVENT-SOURCED RUNTIME — ActiveGraph style"]
    BEH["behaviors subscribe to<br/>graph-shape patterns"]
    FIX["reactive FIXPOINT loop<br/>= lint loop = semi-naive eval"]
    CONS["consolidator (ingest.clj)<br/>single writer, promotion gate"]
    PROJ["projection = fold(log)<br/>DataScript 1.7.3 working db"]
    CACHE["content-addressed<br/>model and tool response cache"]
    BEH --> FIX
    PROJ --> BEH
  end

  subgraph L3["L3 · IMMUTABLE STORE — datom family"]
    LOG[("APPEND-ONLY EVENT LOG<br/>today: EDN snapshot ·<br/>target: Fluree signed ledger")]
    RULES["recursive Datalog rules<br/>(rules.clj — runs in projection)"]
    SHACL["SHACL shapes = linter<br/>(Fluree, transaction-time)"]
    BR["git-like branches<br/>= fork-and-diff, durable"]
    LOG --> RULES
    LOG --> BR
  end

  EMERG["Propagation and emergence layer<br/>diffuse signal → threshold → reify<br/>summaries · beliefs · trails · compounds"]

  SUB -->|"append facts"| LOG
  REPL -->|"query"| PROJ
  LADDER -->|"judgments as typed facts"| CONS
  CONS -->|"promote domain events"| LOG
  FIX -->|"emit events"| LOG
  LOG -->|"fold / replay"| PROJ
  CACHE -.-> LOG
  SHACL -.->|"gates writes"| LOG
  LOG --> EMERG
  EMERG -->|"reified nodes"| LOG

  class L1 l1
  class L2 l2
  class L3 l3
  class JL jl
  class EMERG sw
```

## 02 · The one pattern under everything

Every mechanism in the project is an instance of: a signal accumulates along the graph, crosses a threshold, and reifies a first-class provenanced node, which feeds back. Six instances span the granularity dial: propositions (down), canonical entities (lateral), compound entities/FCA (up), summaries (up), claims-with-stance (up), trails (meta).

```mermaid
flowchart LR
  classDef core fill:#c6f6d5,stroke:#2f855a,stroke-width:2px
  classDef inst fill:#ebf8ff,stroke:#2b6cb0

  SIG["signal accumulates<br/>along the graph"]:::core
  THR["crosses a threshold<br/>(activation · surprisal ·<br/>frequency · density)"]:::core
  REI["reify a first-class node<br/>(append-only, provenanced)"]:::core
  FEED["new node feeds the graph<br/>→ new signals"]:::core
  SIG --> THR --> REI --> FEED --> SIG

  P["DENSIFICATION down-dial<br/>signal: factoids in prose<br/>reified: atomic PROPOSITIONS"]:::inst
  E["CONVERGENCE lateral<br/>signal: coreference cues<br/>reified: canonical ENTITY (sameAs)"]:::inst
  C["COMBINATION up-dial<br/>signal: entity-tuple co-occurrence<br/>reified: COMPOUND entity (FCA concept)"]:::inst
  S["EMERGENCE up-dial<br/>signal: semantic similarity of neighbors<br/>reified: SUMMARY node (RAPTOR online)"]:::inst
  B["BELIEF up-dial<br/>signal: support and oppose edges<br/>reified: CLAIM with stance (argumentation fixpoint)"]:::inst
  T["NAVIGATION meta<br/>signal: traversal frequency<br/>reified: TRAIL (desire path)"]:::inst

  REI -.-> P
  REI -.-> E
  REI -.-> C
  REI -.-> S
  REI -.-> B
  REI -.-> T
```

## 03 · Data flow, cradle to flywheel

The four loops and how they hand off: calibration (offline, per judge version), the live judging loop (pre-filter to promotion to graph and back), the audit loop (anchor sampling to drift to quarantine to cohort retraction), and the distillation loop (provenance-gated dataset to QLoRA to shadow to the promote gate). Every arrow corresponds to a JSONL file or a function in the delivered artifacts.

```mermaid
flowchart LR
  classDef off fill:#fefcbf,stroke:#975a16
  classDef live fill:#ebf8ff,stroke:#2b6cb0
  classDef aud fill:#fed7d7,stroke:#9b2c2c
  classDef dis fill:#faf5ff,stroke:#805ad5

  subgraph CAL["CALIBRATION — offline, once per judge version"]
    RX["Roam export JSON"] --> HV["roam_harvest.py<br/>7 candidate miners"]
    HV --> CD["candidates_{type}.jsonl"]
    CD --> AL["anchor_label.py --double<br/>salted orders, policy guidance"]
    AL --> CS["calset (FROZEN gold)"]
    AL --> RQ["review_queue.md"] --> HUM["human spot-check (T2)"] --> CS
    CS --> CB["judge_harness calibrate<br/>temperature fit + conformal q-hat"]
    CB --> CJ[("calibration.json")]
  end

  subgraph LIVE["LIVE LOOP — continuous"]
    PFX["pre-filter: activation ·<br/>surprisal (dreamer) · dirty-marks"] --> LC["live candidates"]
    LC --> JH["judge_harness judge ×3 families<br/>echo-score → scale → conformal gate"]
    CJ -.-> JH
    JH --> OB["ops/outbox.jsonl +<br/>contexts.jsonl (content-addressed)"]
    OB --> IN["ingest.clj — tail, idempotent,<br/>UTF-8 safe, offsets"]
    IN --> CO["consolidate: anchor supremacy →<br/>T2 panel k-of-n → promote"]
    CO --> DF["domain facts: discourse edges ·<br/>sameAs · stale-marks · tasks"]
    DF --> GR[("event log / graph<br/>belief fixpoint · summaries")]
    GR --> PFX
    CO --> ES["escalations.jsonl"] --> AP["anchor pass<br/>(judge --judge anchor)"] --> OB
  end

  subgraph AUD["AUDIT LOOP — daily"]
    GR --> AC["accepted.jsonl"] --> AS["anchor-sample rho=5%"]
    AS --> AO["anchor_outbox.jsonl"] --> IN
    IN --> DR["drift rate per type × judge-version"]
    DR -->|"over theta"| QU["quarantine judge"] --> CR["cohort retraction:<br/>taint closure → retract → recompute"]
    CR --> GR
  end

  subgraph DIS["DISTILLATION LOOP — per milestone"]
    CS --> DS["distill dataset:<br/>provenance gate · conflict resolve ·<br/>hash-bucket train vs frozen audit"]
    AC -->|"anchor rows only"| DS
    HUM --> DS
    DS --> TR["QLoRA train (3090,<br/>peft + trl + bitsandbytes)"]
    TR --> SH["shadow run + eval-audit<br/>(McNemar exact)"]
    SH --> PG{"promote-check"}
    PG -->|"PROMOTE"| JH
    PG -->|"EXTEND-SHADOW"| SH
    PG -->|"REJECT"| DS
  end

  class CAL off
  class LIVE live
  class AUD aud
  class DIS dis
```

## 04 · Lifecycles: judgment and judge

Two state machines. A judgment flows scored -> candidate/abstained -> accepted/rejected -> possibly retracted; a judge flows calibrating -> active -> quarantined/shadow -> retired-but-never-deleted. Promotion is the only non-monotone transition; everything else is an append.

```mermaid
stateDiagram-v2
  state "JUDGMENT lifecycle" as JM {
    [*] --> Scored : conformal gate on logprobs
    Scored --> Candidate : singleton prediction set
    Scored --> Abstained : multi-label set or order disagreement
    Abstained --> Escalated : next rung picks it up
    Escalated --> Candidate : anchor verdict returns as judgment
    Candidate --> Accepted : T0 or T1 single pass · T2 panel k-of-n · anchor supremacy
    Candidate --> Rejected : panel dissent resolved against
    Accepted --> Retracted : cohort retraction (judge found biased)
    Accepted --> [*]
    Retracted --> [*]
  }
  state "JUDGE lifecycle" as GM {
    [*] --> Calibrating : anchor-labeled calset
    Calibrating --> Active : temperature + q-hat written
    Active --> Quarantined : drift over theta (reversible event)
    Quarantined --> Active : recalibrated
    Quarantined --> Retired : cohort retracted · entry kept, never deleted
    Active --> Shadow : candidate v(n+1) deployed in parallel
    Shadow --> Active : promote-check PROMOTE (recalibrate fresh)
    Retired --> [*]
  }
```

## 05 · One judgment, end to end

The wire-level story of a single edge-type judgment: per-label echo scoring against vLLM (shared prefix cached), temperature scaling and the conformal gate in the harness, the outbox append, idempotent tailing by the consolidator, anchor supremacy versus T2 panel arbitration, and the escalation round-trip.

```mermaid
sequenceDiagram
  autonumber
  participant PF as Pre-filter
  participant H as Judge harness Python
  participant V as vLLM judge Qwen3-8B
  participant O as ops outbox JSONL
  participant C as Consolidator ingest.clj
  participant A as Anchor LLM
  participant G as Event log and graph

  PF->>H: candidate (jtype, subjects, fields)
  H->>H: context_hash + prompt with seeded label order
  loop one echo-score per label (shared prefix cached)
    H->>V: completions echo=true logprobs
    V-->>H: token logprobs of label suffix
  end
  H->>H: temperature-scale then conformal gate
  alt singleton prediction set
    H->>O: judgment.emitted + context record
  else ambiguous or order disagreement
    H->>O: judgment.abstained
  end
  Note over H,O: same_entity runs BOTH item orders (T2 agreement)
  C->>O: tail with byte offset (UTF-8 safe)
  C->>C: idempotency check (judge, hash, label)
  alt anchor verdict exists on subject
    C->>G: promote directly (anchor supremacy)
  else T2 panel
    C->>C: k-of-n distinct model families agree
    alt agreement
      C->>G: promote domain fact with prov from-judgment
    else dissent
      C->>O: escalation row (fields-free)
      A->>O: anchor verdict returns as judgment.emitted
    end
  end
  G-->>PF: new events generate new candidates
```

## 06 · The regime ladder and distillation gravity

Cheapest-regime-first with abstention upward (A heuristics, B classifiers, B-half small-LLM judges, C anchor) and the countercurrent flowing down: anchor traces distill into judges, stable judge behavior compiles into classifiers, stable patterns compile into rules. Self-improvement = re-pricing cognition downward.

```mermaid
flowchart TB
  classDef rung fill:#ebf8ff,stroke:#2b6cb0,stroke-width:2px
  classDef hot fill:#e9d8fd,stroke:#805ad5,stroke-width:2px
  classDef pre fill:#fefcbf,stroke:#975a16
  classDef log fill:#c6f6d5,stroke:#2f855a,stroke-width:2px

  PF["PRE-FILTER (formal layer)<br/>activation · surprisal · dirty-marks<br/>budgeted, debounced candidates"]:::pre

  A["A · heuristics<br/>Datalog rules, exact matches"]:::rung
  B["B · classifiers<br/>kNN embeddings, relational GNN scorer"]:::rung
  B5["B½ · small-LLM judges (4-8B local)<br/>closed labels · constrained decoding ·<br/>logprob confidence → conformal gate"]:::hot
  C["C · anchor LLM<br/>panel arbiter · summary writer"]:::rung
  LOG[("append-only event log<br/>judgments = typed facts +<br/>provenance envelope")]:::log

  PF --> A
  A -->|"abstain → escalate"| B
  B -->|"abstain → escalate"| B5
  B5 -->|"abstain → escalate"| C
  A --> LOG
  B --> LOG
  B5 --> LOG
  C -->|"verdict is a judgment too"| LOG

  C -.->|"traces distill to judges"| B5
  B5 -.->|"stable behavior compiles to classifiers"| B
  B -.->|"stable patterns compile to rules"| A

  GRAV["DISTILLATION GRAVITY<br/>self-improvement = re-pricing<br/>cognition downward"]
  C -.- GRAV
```

## 07 · Calibration and distillation, with the anti-collapse rails

From admissible sources (provenance-gated: human over double-pass anchor over anchor; equal-tier conflicts dropped) through the deterministic hash-bucket split (the audit set freezes itself), QLoRA on the 3090, McNemar-tested audit evaluation, shadow comparison, and the three-outcome promote gate.

```mermaid
flowchart LR
  classDef src fill:#fefcbf,stroke:#975a16
  classDef frozen fill:#fed7d7,stroke:#9b2c2c,stroke-width:2px
  classDef proc fill:#ebf8ff,stroke:#2b6cb0
  classDef gate fill:#e9d8fd,stroke:#805ad5,stroke-width:2px

  CS["anchor calsets<br/>(double-pass consistent)"]:::src
  AR["accepted.jsonl —<br/>anchor-family rows only"]:::src
  HG["human gold<br/>(worked review queues)"]:::src

  DS["dataset command<br/>provenance gate: human over anchor_double over anchor ·<br/>equal-tier conflicts DROPPED ·<br/>deterministic hash-bucket split"]:::proc
  CS --> DS
  AR --> DS
  HG --> DS

  TRN["train_{type}.jsonl<br/>SFT target imported from<br/>the deployed scorer"]:::proc
  AUD["audit_{type}.jsonl<br/>FROZEN — never trained on,<br/>membership fixed by hash rule"]:::frozen
  DS --> TRN
  DS --> AUD

  QL["QLoRA train on 3090<br/>peft + trl, assistant-only loss,<br/>r=16 nf4 4-bit"]:::proc
  TRN --> QL
  QL --> AD["adapter + weights hash<br/>→ new judge identity"]

  EV["eval-audit: paired argmax,<br/>McNemar exact on discordant pairs"]:::proc
  AUD --> EV
  AD --> SRV["vllm serve --enable-lora"] --> EV
  SRV --> SHW["shadow run on live candidates<br/>(separate outbox, never promoted)"]:::proc
  SHW --> SC["shadow-compare: agreement ·<br/>abstention band · anchor join"]:::proc

  PG{"promote-check gate"}:::gate
  EV --> PG
  SC --> PG
  PG -->|"PROMOTE: recalibrate fresh,<br/>family preserved, old judge quarantined"| FLEET["judge fleet"]
  PG -->|"EXTEND-SHADOW: gain real<br/>but p over 0.05 — gather more"| SHW
  PG -->|"REJECT"| DS
```

## 08 · Drift, quarantine, cohort retraction

The immune system: anchor sampling produces agreement facts; drift per (type x judge-version) triggers reversible quarantine; systematic bias triggers cohort retraction via the taint closure -- with nothing ever deleted, so the mistake remains queryable as-of any past time.

```mermaid
flowchart TB
  classDef ok fill:#c6f6d5,stroke:#2f855a
  classDef warn fill:#fefcbf,stroke:#975a16
  classDef bad fill:#fed7d7,stroke:#9b2c2c,stroke-width:2px

  AC["accepted.jsonl<br/>(judgment_id · type · label · hash · family)"]:::ok
  AS["anchor-sample rho 1-5%<br/>fields joined from contexts.jsonl"]:::ok
  AO["anchor_outbox.jsonl<br/>agrees? + anchor_label"]:::ok
  DR["drift rate per<br/>(type × judge-version)"]:::warn
  TH{"disagreement over theta<br/>with n at least 30?"}:::warn
  QU["QUARANTINE judge-version<br/>reversible event · candidates<br/>stop being promotable"]:::bad
  REV["review task opens:<br/>recalibrate, retrain, or retract?"]:::warn
  CR["COHORT RETRACTION<br/>query cohort → taint closure via<br/>derivation rules → retraction events"]:::bad
  RC["stale-mark derived cone →<br/>consolidation recomputes"]:::ok
  REC["recalibrate or distill v(n+1)"]:::ok

  AC --> AS --> AO --> DR --> TH
  TH -->|"yes"| QU --> REV
  TH -->|"no, but widening trend"| REV
  REV -->|"systematic bias"| CR --> RC
  REV -->|"calibration drift"| REC
  CR -.->|"nothing deleted — the mistake stays<br/>queryable as-of any past time"| AC
```

## 09 · The data model (entity-relationship view)

The judgment layer's schema as deployed in judges.clj and ingest.clj: judges emit judgments about nodes; accepted judgments license domain facts (prov_from_judgment is what makes cohort retraction a query); every assertion traces to an event; events chain causally; anchor checks attach to sampled judgments.

```mermaid
erDiagram
  JUDGE ||--o{ JUDGMENT : emits
  JUDGMENT }o--o{ NODE : about_subjects
  JUDGMENT ||--o{ DOMAIN_FACT : licenses
  EVENT ||--o{ NODE : asserts_prov
  EVENT ||--o{ DOMAIN_FACT : asserts_prov
  EVENT }o--|| EVENT : caused_by
  NODE ||--o{ EDGE : from
  NODE ||--o{ EDGE : to
  DOMAIN_FACT ||--o| EDGE : reifies
  JUDGMENT ||--o{ ANCHOR_CHECK : sampled_by
  NODE ||--o{ FLAG : flagged_by
  NODE ||--o{ TASK : opens

  JUDGE {
    string judge_id PK
    string model
    string family
    string weights_hash
    int prompt_version
    bool quarantined
  }
  JUDGMENT {
    string judgment_id PK
    string jtype
    string label
    float confidence
    string status
    string context_hash
    string cal_version
    string subjects_vec
  }
  EVENT {
    string event_id PK
    string event_type
    string actor
    string caused_by FK
    string timestamp
  }
  NODE {
    string node_id PK
    string node_type
    bool derived_stale
    bool prop_faithful
  }
  EDGE {
    string edge_type
    string from_node FK
    string to_node FK
  }
  DOMAIN_FACT {
    string node_id PK
    string prov_from_judgment FK
  }
  ANCHOR_CHECK {
    bool agrees
    string anchor_label
  }
  FLAG {
    string flag_kind
  }
  TASK {
    string status
    int depth
  }
```

## 10 · Deployment topology and software choices

The physical system over the Tailscale mesh: prefill-heavy judging on Machine B's dual 3090s (vLLM with prefix caching; QLoRA runs there too), the third judge family and the runner on Machine A, the consolidator JVM on the Mac, and the NAS as the home of the ops/ JSONL exchange, the (planned) Fluree ledger, and Hermes services.

```mermaid
flowchart TB
  classDef mac fill:#ebf8ff,stroke:#2b6cb0
  classDef gpu fill:#e9d8fd,stroke:#805ad5
  classDef nas fill:#c6f6d5,stroke:#2f855a
  classDef proc fill:#fefcbf,stroke:#975a16

  subgraph TS["Tailscale mesh (MagicDNS)"]
    subgraph MAC["Mac M1 Pro — MBP-de-alain"]
      ROAM["Roam client (DataScript) ·<br/>exports for harvest"]:::proc
      HERM["Hermes coordination ·<br/>Claude Code"]:::proc
      CONSOL["consolidator JVM —<br/>clojure -M -m mnemosyne.ingest ops/"]:::proc
    end
    subgraph MB["Machine B — Ryzen, 128 GB, 2 × RTX 3090 (prefill cluster)"]
      VQ["vLLM :8000 Qwen3-8B judge<br/>--enable-prefix-caching"]:::proc
      VG["vLLM :8001 Gemma-3-12B judge"]:::proc
      QLR["QLoRA training runs<br/>(peft · trl · bitsandbytes)"]:::proc
    end
    subgraph MA["Machine A — dual EPYC, 256 GB, 1 × RTX 3090 (decode cluster)"]
      VP["vLLM :8000 Phi-4-mini judge"]:::proc
      RUN["judge runner —<br/>judge_harness.py loops"]:::proc
    end
    subgraph NS["NAS — TrueNAS Scale + ZFS (planned)"]
      OPS[("ops/ shared dir:<br/>outbox · contexts · accepted ·<br/>escalations · anchor_outbox")]:::proc
      LEDG[("Fluree ledger storage<br/>content-addressed commits<br/>(file or S3-compatible)")]:::proc
      SVC[("Hermes services:<br/>Postgres · Redis · MinIO")]:::proc
    end
  end
  ANCH["Anchor LLM<br/>(API, or large local model)"]

  ROAM -->|"graph.json"| RUN
  RUN -->|"echo-score calls"| VQ
  RUN --> VG
  RUN --> VP
  RUN -->|"JSONL append"| OPS
  CONSOL -->|"tail + promote"| OPS
  CONSOL -->|"signed commits (target)"| LEDG
  RUN -.->|"escalations + sampling"| ANCH
  QLR -.->|"adapters → new judges"| VQ

  class MAC mac
  class MB gpu
  class MA gpu
  class NS nas
```

## 11 · The Fluree hybrid L3 (the Athens split, instantiated)

DataScript stays the in-process working projection -- rules.clj verbatim -- while Fluree becomes the durable, signed, branched, SHACL-gated ledger. Per-judge keypairs upgrade cohort retraction to non-repudiation; the reasoner materializes the monotone core; SPARQL/JSON-LD with ELI and PROV-O is the verifiable RGPD audit surface.

```mermaid
flowchart LR
  classDef l2 fill:#ebf8ff,stroke:#2b6cb0,stroke-width:2px
  classDef fl fill:#c6f6d5,stroke:#2f855a,stroke-width:2px
  classDef ext fill:#fefcbf,stroke:#975a16

  subgraph WORK["Working layer — in-process (the Athens split)"]
    DS["DataScript projection<br/>rules.clj VERBATIM:<br/>descendant · frontier ·<br/>violation · derivation"]:::l2
    L2["L2 runtime + consolidator<br/>run-to-fixpoint · promotion"]:::l2
    DS --- L2
  end

  subgraph FLU["Fluree ledger — durable L3 (Rust core, BUSL→Apache)"]
    COMMIT["signed, content-addressed commits<br/>one commit per Mnemosyne event ·<br/>event metadata in commit meta"]:::fl
    SH["SHACL shapes at transaction time<br/>= the linter (closed-world by design)"]:::fl
    RSN["forward-chaining reasoner<br/>Datalog and OWL-RL rules =<br/>monotone core materialized"]:::fl
    BRS["branches: main · shadow-judge ·<br/>counterfactual what-if"]:::fl
    IDX["integrated BM25 + HNSW<br/>= regime B in the same engine"]:::fl
    COMMIT --> RSN
    COMMIT --> BRS
  end

  KEYS["per-judge keypairs:<br/>judgments signed →<br/>cohort retraction with non-repudiation"]
  EXTQ["external surface: SPARQL ·<br/>JSON-LD · ELI and PROV-O vocabularies →<br/>verifiable RGPD audit deliverables"]:::ext

  L2 -->|"append! = bridge tx"| COMMIT
  SH -.->|"gates"| COMMIT
  COMMIT -->|"project = fold commits"| DS
  KEYS -.-> COMMIT
  FLU --> EXTQ
  IDX -.->|"kNN candidates · hybrid retrieval"| L2
```

## 12 · The CALM split (what distributes, what does not)

The architecture's standing discipline: the monotone core (appends, emissions, positive recursion, counters, pooled embeddings, reasoner materialization) is coordination-free across Hermes nodes; the non-monotone boundary (negation, promotion, stances, invalidation, retraction) belongs to the single-writer consolidator. Decisions re-enter the log as appends -- monotone again.

```mermaid
flowchart LR
  classDef mono fill:#c6f6d5,stroke:#2f855a,stroke-width:2px
  classDef nonm fill:#fed7d7,stroke:#9b2c2c,stroke-width:2px

  subgraph M["MONOTONE CORE — coordination-free, runs on ANY Hermes node"]
    M1["append events · emit judgments"]:::mono
    M2["positive recursion:<br/>descendant · event-chain · derivation"]:::mono
    M3["trail counters · co-occurrence tallies"]:::mono
    M4["pooled embeddings (provisional)"]:::mono
    M5["Fluree reasoner materialization<br/>(positive rules only — enforced)"]:::mono
  end

  subgraph N["NON-MONOTONE BOUNDARY — single writer: the consolidator"]
    N1["negation: frontier · linter · SHACL"]:::nonm
    N2["promotion · panel arbitration ·<br/>sameAs acceptance"]:::nonm
    N3["belief stance — grounded extension"]:::nonm
    N4["re-summarization · invalidation"]:::nonm
    N5["retraction · cohort retraction"]:::nonm
  end

  M ==>|"stratification: monotone facts flow in,<br/>decisions flow back as new appends"| N
  N ==>|"every decision re-enters the log<br/>as an append (monotone again)"| M
```

## 13 · Build roadmap and current status

What is done (specs, substrate, contract, harness, calibration tooling, ops service, distillation -- self-tested where executable), what is next (first live edge_type judge on the real graph; wiring the dreamer surprisal pre-filter), and what follows (Fluree adapter, propositionizer, first distillation pass, belief layer live).

```mermaid
flowchart LR
  classDef done fill:#c6f6d5,stroke:#2f855a,stroke-width:2px
  classDef next fill:#fefcbf,stroke:#975a16,stroke-width:2px
  classDef later fill:#ebf8ff,stroke:#2b6cb0

  S1["1 · Substrate spec + reference impl<br/>mnemosyne.clj · rules.clj — DONE (hand-checked)"]:::done
  S2["2 · Judgment contract + Datalog layer<br/>microjudge_contract · judges.clj — DONE"]:::done
  S3["3 · Harness + prompts + schemas<br/>judge_harness · judge_prompts — DONE (self-tested)"]:::done
  S4["4 · Calibration loop<br/>roam_harvest · anchor_label — DONE (demo-run)"]:::done
  S5["5 · Ops service<br/>ingest.clj · runbooks — DONE (hand-checked)"]:::done
  S6["6 · Distillation pipeline<br/>distill_judge — DONE (self-tested)"]:::done
  N1["7 · FIRST LIVE JUDGE: harvest real graph →<br/>anchor-label edge_type → review →<br/>calibrate qwen-a → watch abstention rate"]:::next
  N2["8 · Pre-filter wiring:<br/>dreamer surprisal → candidates"]:::next
  L1["9 · Fluree L3 adapter:<br/>signed commits · SHACL port · branches"]:::later
  L2["10 · Propositionizer pipeline →<br/>faithful calset top-up"]:::later
  L3["11 · First distillation pass<br/>(at ~1k admissible examples)"]:::later
  L4["12 · Belief layer live:<br/>grounded-extension fixpoint over<br/>promoted discourse edges"]:::later

  S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> N1 --> N2 --> L1
  N1 --> L2
  N2 --> L3
  L1 --> L4
```

---
*Provenance: synthesized from the project artifacts (mnemosyne_stack.md,
microjudge_contract.md, the README set, and the code) as of 2026-06-11.
Diagram sources are the single source of truth; this compendium is generated from them.*
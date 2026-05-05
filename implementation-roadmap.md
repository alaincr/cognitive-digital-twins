---
title: Implementation Roadmap — Cognitive Architecture on Roam Research
type: analysis
created: 2026-05-02
updated: 2026-05-02
sources: [CLAUDE.md, SKILL-thesis-ingest.md, information-flow-diagram.md]
tags: [roadmap, implementation, roam, cognitive-architecture, project-plan]
---

# Implementation Roadmap — Cognitive Architecture on Roam Research

A self-referential research system: a cognitive architecture that studies cognitive architectures. Roam is the single source of truth. Each cognitive component is both a working piece of the system AND its own research track. The system improves itself through auto-research.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    ROAM RESEARCH GRAPH                       │
│                  (single source of truth)                    │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              OPERATIONAL LAYER                       │   │
│  │         (the system that runs)                       │   │
│  │                                                      │   │
│  │  ┌────────────┐  ┌────────────┐  ┌──────────────┐   │   │
│  │  │ Perception │  │   Memory   │  │  Reasoning   │   │   │
│  │  │ (Ingest)   │  │ (Storage & │  │  (Query &    │   │   │
│  │  │            │  │  Retrieval)│  │   Synthesis) │   │   │
│  │  └─────┬──────┘  └─────┬──────┘  └──────┬───────┘   │   │
│  │        │               │                │            │   │
│  │  ┌─────┴──────┐  ┌─────┴──────┐  ┌──────┴───────┐   │   │
│  │  │ Planning   │  │ Meta-      │  │ Auto-        │   │   │
│  │  │ (Scaffold) │  │ Cognition  │  │ Research     │   │   │
│  │  │            │  │ (Lint &    │  │ (Self-       │   │   │
│  │  │            │  │  Audit)    │  │  Improvement)│   │   │
│  │  └────────────┘  └────────────┘  └──────────────┘   │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              REFLECTIVE LAYER                        │   │
│  │      (the research that studies the system)          │   │
│  │                                                      │   │
│  │  One research track per component above:             │   │
│  │  [[R/Perception]]  [[R/Memory]]  [[R/Reasoning]]    │   │
│  │  [[R/Planning]]  [[R/Meta-Cognition]]  [[R/Auto-Res]]│   │
│  │                                                      │   │
│  │  Each track has: literature, ideas, experiments,     │   │
│  │  findings, open questions, proposed improvements     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              INTEGRATION LAYER                       │   │
│  │    (the thesis / scaffolding that ties it together)  │   │
│  │                                                      │   │
│  │  [[Scaffolding]] — top-level argument structure      │   │
│  │  [[Overview]]    — what is this and why              │   │
│  │  [[Glossary]]    — canonical terms                   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   GIT REPO (meta-layer)                      │
│  Agent operating manuals, skills, diagrams, roadmap         │
│  Versioned, diffable — the system's source code             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   AGENT (Claude Code → persistent)          │
│  Reads git repo for instructions                            │
│  Reads/writes Roam via MCP                                  │
│  Executes workflows: ingest, query, lint, auto-research     │
└─────────────────────────────────────────────────────────────┘
```

---

## Guiding Principles

1. **Roam is the single source of truth.** Everything goes in, everything comes out. Local files (git) are operational scaffolding for the agent, not a parallel store.
2. **Each component is dual-natured.** It works (operational) AND it's studied (reflective). Changes flow both ways: research findings improve the component, using the component generates research insights.
3. **Ship the loop, not the system.** Each component must close one real cycle before you drill into its research track.
4. **Integrate before you build.** You have existing ideas for each component. Consolidate them into Roam first — they carry tacit design knowledge.
5. **Let Roam be Roam.** Blocks, backlinks, queries, attributes — use them natively. Don't replicate flat-file patterns.
6. **Separation of concerns.** Operational layer, reflective layer, and integration layer are distinct namespaces in Roam. Changes to one don't silently break another.

---

## The Six Components

Each component below is both a working piece of the system and a research track. The structure is identical for each:

- **Operational spec** — what the component does, its inputs/outputs, its current implementation
- **Research track** — literature, your existing ideas, experiments, open questions
- **Improvement loop** — how auto-research feeds back into the operational spec

### Component 1 — Perception (Ingestion)

**What it does:** Takes a raw source (paper, article, conversation, note) and distils it into structured knowledge in Roam.

**Operational inputs/outputs:**
- Input: raw document (PDF, markdown, URL, pasted text)
- Output: source page in Roam with structured layers, updated scaffolding, glossary terms
- Current reference: `SKILL-thesis-ingest.md` (three-layer distillation)

**Research track `[[R/Perception]]`:**
- How many distillation layers are optimal? Is three right or should it be adaptive?
- What's lost in distillation? Can you measure information loss?
- How should the "thesis context block" be structured to maximise relevance extraction?
- How does the source type (empirical paper vs. theoretical, podcast vs. paper) change the ingest strategy?
- Your existing ideas: _(to be consolidated from your notes)_

---

### Component 2 — Memory (Storage & Retrieval)

**What it does:** Structures, links, and retrieves compiled knowledge within Roam's graph.

**Operational inputs/outputs:**
- Input: structured content from Perception, queries from Reasoning
- Output: pages, blocks, backlinks, query results
- Current implementation: Roam's native graph + Datalog queries via your custom MCP

**Research track `[[R/Memory]]`:**
- What's the optimal granularity: page-level, block-level, or attribute-level?
- How should the namespace/tag system be structured for scalability?
- When does Roam's backlink graph become noisy? What's the signal-to-noise tipping point?
- How does memory decay work? Should old, uncited pages be flagged or archived?
- Block references `((uid))` vs. page references `[[name]]` — when does each create better retrieval?
- Your existing ideas: _(to be consolidated)_

---

### Component 3 — Reasoning (Query & Synthesis)

**What it does:** Answers questions by consulting compiled knowledge, synthesises across sources, produces new analysis.

**Operational inputs/outputs:**
- Input: user question + wiki context (scaffolding, relevant pages, glossary)
- Output: synthesised answer with citations, optionally archived as analysis page
- Current reference: Query workflow in CLAUDE.md

**Research track `[[R/Reasoning]]`:**
- When should reasoning use only compiled wiki content vs. going back to raw sources?
- How do you evaluate reasoning quality without ground truth? (Same problem as the CDT thesis)
- Multi-step reasoning: when should the agent decompose a question into sub-queries?
- How does the order of pages read affect synthesis quality?
- Can the system detect when it doesn't know enough to answer and request targeted ingest?
- Your existing ideas: _(to be consolidated)_

---

### Component 4 — Planning (Scaffolding)

**What it does:** Maintains the evolving argumentative structure — the central document that reflects what you know, what's missing, and where you're going.

**Operational inputs/outputs:**
- Input: findings from Perception, Reasoning, and Meta-Cognition
- Output: updated scaffolding with chapter structure, integrated sources, tensions, gaps, next steps
- Current reference: `wiki/scaffolding-tesi.md`

**Research track `[[R/Planning]]`:**
- How should the scaffolding evolve? Append-only (current) vs. periodic restructuring?
- When does the scaffolding become too large to be useful? Should it have a summary layer?
- How do you detect when the argument has structurally shifted (not just added to)?
- Can the scaffolding auto-suggest what to research next based on gap analysis?
- Tension tracking: how do you resolve tensions, not just accumulate them?
- Your existing ideas: _(to be consolidated)_

---

### Component 5 — Meta-Cognition (Lint & Audit)

**What it does:** The system's self-awareness — audits the wiki for consistency, completeness, contradictions, and decay.

**Operational inputs/outputs:**
- Input: full graph state
- Output: list of issues (contradictions, orphans, unsupported claims, glossary drift), proposed fixes
- Current reference: Lint workflow in CLAUDE.md

**Research track `[[R/Meta-Cognition]]`:**
- What types of inconsistency can an LLM reliably detect vs. what it misses?
- How often should lint run? Continuous vs. periodic?
- Can the system detect its own blind spots (unknown unknowns)?
- How do you distinguish "productive tension" (worth keeping) from "real contradiction" (needs fixing)?
- Should lint be one monolithic pass or specialised sub-audits?
- Your existing ideas: _(to be consolidated)_

---

### Component 6 — Auto-Research (Self-Improvement)

**What it does:** The system researches how to improve its own components. Searches for relevant literature, tests alternatives, proposes upgrades.

**Operational inputs/outputs:**
- Input: friction log, research track open questions, performance observations
- Output: proposed changes to operational specs, new literature to ingest, experiment designs
- This is the component that doesn't exist yet in the reference repo — it's your addition.

**Research track `[[R/Auto-Research]]`:**
- How do you scope auto-research so it doesn't spiral? (Researching research about researching...)
- What triggers auto-research: explicit command, friction threshold, scheduled?
- How do you evaluate whether a proposed improvement actually helps?
- Can the system A/B test its own components (e.g., two different ingest strategies on the same paper)?
- How do you prevent the system from over-optimising one component at the expense of others?
- Your existing ideas: _(to be consolidated)_

---

## Implementation Sequence

Unlike the previous linear roadmap, this is **hub-and-spoke**: a short bootstrap phase, then parallel component tracks.

### Phase 0 — Bootstrap (2–3 sessions)

**Goal:** Get the minimal loop running so every component has something real to work with.

- [ ] **0.1 — Roam MCP verification.** Confirm your custom MCP server works with Claude Code. Test read, write, query, create page, create block.
- [ ] **0.2 — Namespace conventions.** Decide and document in `[[Conventions]]`:
  - Operational pages: `[[Perception]]`, `[[Memory]]`, `[[Reasoning]]`, `[[Planning]]`, `[[Meta-Cognition]]`, `[[Auto-Research]]`
  - Research tracks: `[[R/Perception]]`, `[[R/Memory]]`, etc.
  - Sources: `[[S/slug]]` or `#source` tag
  - Attributes: `type::`, `component::`, `status::`, `created::`
- [ ] **0.3 — Consolidate existing ideas.** For each of the 6 components, create the research track page in Roam and dump your existing ideas, notes, and references into it. Unstructured is fine — this is the raw material.
- [ ] **0.4 — Minimal scaffolding.** Create `[[Scaffolding]]` with:
  - Top-level research question: "How does a self-referential cognitive architecture study and improve its own components?"
  - Six component sections (one per component, placeholder content)
  - A meta-section: "What connects the components? What's the overall argument?"
- [ ] **0.5 — First ingest.** Pick one document (a paper about cognitive architectures, or one of your existing pieces) and push it through a manual ingest. Create the source page, update the scaffolding, add glossary terms. Don't worry about perfection — the goal is to close the loop once.
- [ ] **0.6 — Write CLAUDE.md for Roam.** Based on what you learned in 0.5, write the operating manual. Store in git repo (for Claude Code) and as `[[CLAUDE.md]]` in Roam (for future persistent agent).

**Exit criterion:** The loop works end to end. Six research track pages exist with your raw ideas. Scaffolding has real content. CLAUDE.md is written.

---

### Phase 1 — Component Tracks (parallel, ongoing)

After bootstrap, each component becomes an independent track. Work on whichever feels most productive or has the most friction. The structure for each track is the same:

```
For component X:

1. OPERATE — Use the current version of X on real content
2. OBSERVE — Note friction, failures, surprises in [[Friction Log]]
3. RESEARCH — Read/ingest relevant literature into [[R/X]]
4. HYPOTHESISE — Propose a specific improvement to X
5. TEST — Try the improvement on the next real task
6. INTEGRATE — If it works, update the operational spec
7. REFLECT — Update [[Scaffolding]] with what you learned
```

Each track can proceed at its own pace. Some will move fast (Perception — you'll ingest many documents). Some will be slow and deep (Auto-Research — conceptually hardest).

#### Suggested starting order (based on dependency)

1. **Perception first** — you need content in the system before other components have anything to work with
2. **Memory second** — as content accumulates, retrieval quality becomes the bottleneck
3. **Reasoning third** — once memory is populated, test synthesis quality
4. **Planning fourth** — as reasoning produces insights, the scaffolding needs to absorb them
5. **Meta-Cognition fifth** — enough content exists for lint to find real issues
6. **Auto-Research sixth** — the system is mature enough to study itself

But you can jump between tracks whenever friction or curiosity pulls you.

---

### Phase 2 — Agent Transition (when ready)

**Trigger:** You've gone through 2–3 cycles of the component tracks and CLAUDE.md is stable.

- [ ] **2.1 — Extract session dependencies.** Identify what in CLAUDE.md assumes Claude Code (file reads, bash, session start). Replace with MCP-native equivalents.
- [ ] **2.2 — Build persistent agent.** Options:
  - Claude API + your Roam MCP (custom orchestration)
  - Specialised agents per component (ingest agent, query agent, lint agent)
  - Single agent with component-aware routing
- [ ] **2.3 — Handoff document.** Write `[[Agent Handoff]]` in Roam: non-negotiable conventions, current state of each component, what's still evolving.
- [ ] **2.4 — Test continuity.** Run the same task (ingest, query, lint) on both Claude Code and persistent agent. Compare quality.

---

### Phase 3 — Compound (ongoing)

The system runs. Each ingest, query, and lint pass is simultaneously:
- An operational act (knowledge gets compiled)
- A research data point (you observe how the component performs)
- A potential trigger for auto-research (friction → improvement hypothesis)

The scaffolding evolves from "what do I know about cognitive architectures" to "what have I learned by building and studying one."

---

## Roam Page Structure Reference

```
Roam Graph
├── [[Conventions]]              — namespace rules, attribute schema
├── [[CLAUDE.md]]                — operating manual (mirror of git file)
├── [[Scaffolding]]              — central argument structure
├── [[Overview]]                 — what this is and why
├── [[Glossary]]                 — canonical terms
├── [[Friction Log]]             — ongoing friction observations
│
├── Operational Pages
│   ├── [[Perception]]           — current ingest spec
│   ├── [[Memory]]               — current storage/retrieval spec
│   ├── [[Reasoning]]            — current query/synthesis spec
│   ├── [[Planning]]             — current scaffolding spec
│   ├── [[Meta-Cognition]]       — current lint/audit spec
│   └── [[Auto-Research]]        — current self-improvement spec
│
├── Research Tracks
│   ├── [[R/Perception]]         — literature, ideas, experiments
│   ├── [[R/Memory]]             — literature, ideas, experiments
│   ├── [[R/Reasoning]]          — literature, ideas, experiments
│   ├── [[R/Planning]]           — literature, ideas, experiments
│   ├── [[R/Meta-Cognition]]     — literature, ideas, experiments
│   └── [[R/Auto-Research]]      — literature, ideas, experiments
│
├── Sources
│   ├── [[S/paper-slug-1]]       — distilled source page
│   ├── [[S/paper-slug-2]]       — distilled source page
│   └── ...
│
├── Concepts
│   ├── [[C/concept-name]]       — theoretical construct page
│   └── ...
│
├── Analyses
│   ├── [[A/analysis-name]]      — synthesised output
│   └── ...
│
└── Daily Notes                  — log entries tagged #ingest #query #lint
```

---

## Git Repo Structure

```
cognitive-digital-twins/
├── CLAUDE.md                    — operating manual (canonical, versioned)
├── SKILL-thesis-ingest.md       — ingest skill definition
├── implementation-roadmap.md    — this file
├── information-flow-diagram.md  — architecture diagrams
├── skills/                      — additional skill definitions as they emerge
│   ├── SKILL-query.md
│   ├── SKILL-lint.md
│   └── SKILL-auto-research.md
└── archive/                     — reference material from original repo
    └── (original raw/ and wiki/ if useful for reference)
```

---

## What to do right now

Start Phase 0.3: **Consolidate your existing ideas.** Tell me about the ideas you already have for each component, and I'll help you structure them into the research track pages. This is the most valuable bootstrap step — it captures the tacit knowledge that will shape everything else.

---
title: Implementation Roadmap — LLM Wiki on Roam Research
type: analysis
created: 2026-05-02
updated: 2026-05-02
sources: [CLAUDE.md, SKILL-thesis-ingest.md, information-flow-diagram.md]
tags: [roadmap, implementation, roam, project-plan]
---

# Implementation Roadmap — LLM Wiki on Roam Research

Long-term, phased plan to build a thesis-research knowledge system on Roam Research, driven by Claude Code (then a persistent agent). Each phase ends with real usage on a real document. Customisation is driven by friction, not speculation.

---

## Guiding Principles

1. **Ship the loop, not the system.** Each phase must close one complete cycle: input → process → output. A working loop you can feel beats a perfect schema you can't use.
2. **Integrate before you build.** You have existing pieces. Fold them in early — they carry tacit knowledge about what you actually need.
3. **Let Roam be Roam.** Don't replicate flat-file conventions. Use blocks, queries, backlinks, attributes natively. Adapt the pattern to the tool, not the reverse.
4. **Plan the agent transition.** Every convention you establish now must work when Claude Code sessions become a persistent agent. Avoid session-dependent workflows.

---

## Phase 0 — Inventory & Infrastructure (1 session)

**Goal:** Know exactly what you have, set up the tooling bridge.

### Tasks

- [ ] **Audit existing pieces.** List every Roam page, document, template, and note you've already built. For each: what is it, where does it live, is it still current? Create a page `[[Migration Inventory]]` in Roam with this list.
- [ ] **Set up Roam MCP server.** Install [2b3pro/roam-research-mcp](https://github.com/2b3pro/roam-research-mcp). Configure API token + graph name. Verify Claude Code can read and write to your graph.
- [ ] **Choose namespace conventions.** Decide before writing anything:
  - Source pages: `[[sources/slug]]` or `[[slug]]` + `#source` tag?
  - Raw vs. wiki: `#raw` tag? Separate page prefix?
  - Attributes: `type::`, `created::`, `contributo::`, `sources::`
  - Document the decision in a `[[Conventions]]` page in Roam.
- [ ] **Test the round-trip.** Have Claude Code create a test page in Roam via MCP, read it back, modify it, verify. Delete the test page. Confirm the tooling works end to end.

### Exit criterion
Claude Code can read/write your Roam graph. You have a `[[Conventions]]` page and a `[[Migration Inventory]]` page.

---

## Phase 1 — Minimal Viable Schema (1–2 sessions)

**Goal:** Write the operating manual (CLAUDE.md equivalent) and the three foundational pages in Roam.

### Tasks

- [ ] **Write `CLAUDE.md` for Roam.** Adapt the operating manual from flat-file to Roam conventions. Store it both as a file in this repo (so Claude Code reads it at session start) AND as a `[[CLAUDE.md]]` page in Roam (so a future persistent agent can read it from the graph). Key sections to rewrite:
  - Directory structure → namespace/tag conventions
  - Page format → block structure template with attributes
  - Cross-referencing → explain that backlinks are automatic, when to use `((block-ref))` vs. `[[page-ref]]`
  - Workflows → adapted for MCP calls instead of file read/write
  - Session start checklist → read `[[Scaffolding]]`, last Daily Note entries, `[[Glossary]]`
- [ ] **Create `[[Scaffolding]]`** — the central thesis structure page. Start minimal:
  - Research question (even if provisional)
  - 3–5 chapter headings (even if placeholder)
  - A `Sources integrated::` section (empty)
  - A `Tensions::` section (empty)
  - A `Gaps::` section (empty)
- [ ] **Create `[[Glossary]]`** — one block per term, each with `definition::` and `source::` attributes. Seed with 5–10 terms you already use.
- [ ] **Create `[[Overview]]`** — thesis synopsis in 10–15 blocks. Problem, hypothesis, contributions, stack.

### Exit criterion
Three foundational pages exist in Roam. `CLAUDE.md` is written and tested (Claude Code reads it, understands the conventions, can navigate your graph).

---

## Phase 2 — First Real Ingest (1 session)

**Goal:** Push one real document through the full pipeline. This is the most important phase — it reveals what actually breaks.

### Tasks

- [ ] **Pick your best existing document.** Choose something you already understand well — a paper you've already summarised, or one of your existing pieces. The goal is to test the pipeline, not to learn new content.
- [ ] **Write the ingest skill for Roam.** Adapt `SKILL-thesis-ingest.md`:
  - Three-layer distillation → three block sections under one source page (not three files)
  - Structured extraction → attributes on blocks (`argomento-supportato::`, `gap-colmato::`, `posizione-scaffolding::`)
  - Scaffolding update → add a block under the relevant chapter heading with `((block-ref))` back to the source page
  - Glossary update → new term blocks with attributes
  - Log → entry on today's Daily Note tagged `#ingest`
- [ ] **Run the ingest with Claude Code.** Watch what breaks. Note every friction point.
- [ ] **Integrate one existing piece.** Take something from your `[[Migration Inventory]]` and fold it into the new structure — either as a source page or as content that enriches the scaffolding.
- [ ] **Friction log.** Write a `[[Friction Log]]` page in Roam: what was awkward, what took too long, what conventions didn't work, what you wished the agent did differently.

### Exit criterion
One source page exists with all three layers. Scaffolding has one real entry. Glossary has new terms. Daily Note has a log entry. You have a friction log.

---

## Phase 3 — Refine the Loop (2–3 sessions)

**Goal:** Ingest 3–5 more documents, fixing friction after each one. The schema stabilises through use.

### Tasks

- [ ] **Ingest 3–5 documents sequentially.** After each:
  - Update `[[Friction Log]]`
  - Adjust CLAUDE.md or ingest skill if needed
  - Refine the scaffolding structure (chapters may shift as real content arrives)
- [ ] **Integrate remaining existing pieces.** Work through `[[Migration Inventory]]` — fold each item into the wiki structure or explicitly mark it as deprecated.
- [ ] **Build the query workflow.** Ask Claude Code 2–3 real questions about your research. It should consult `[[Scaffolding]]` and source pages, synthesise an answer, and optionally archive it as an `[[analyses/...]]` page. Refine the query instructions in CLAUDE.md based on what works.
- [ ] **Test the lint workflow.** Run a full lint pass. Check: do backlinks cover cross-references? Are there mentions without corresponding pages? Do terms match the glossary? Is the scaffolding consistent with source pages?
- [ ] **Roam query templates.** Build 3–5 reusable Roam queries:
  - All sources by `contributo::` value
  - All open tensions
  - All terms in glossary without a source page
  - Recent ingest log entries
  - Orphan pages (pages with no backlinks)

### Exit criterion
5+ source pages. Scaffolding has real structure. Query and lint workflows tested. CLAUDE.md is stable (no major rewrites between sessions). Friction log shows diminishing issues.

---

## Phase 4 — Thesis-Specific Customisation (2–3 sessions)

**Goal:** Now that the generic loop works, tailor it to your specific thesis needs.

### Tasks

- [ ] **Concept pages.** Create pages for your core theoretical constructs (the things that appear across multiple sources). Each with: definition, related sources, tensions, how it fits in your argument.
- [ ] **Comparative analyses.** Build 1–2 analysis pages that synthesise across sources: gap analyses, framework comparisons, positioning tables. Test whether the query workflow produces these naturally or if you need a dedicated `compare` skill.
- [ ] **Scaffolding maturity.** By now the scaffolding should reflect your actual argument, not a placeholder. Review it end-to-end: is each chapter claim supported by at least one source? Are tensions explicitly tracked? Are gaps identified?
- [ ] **Writing support workflow.** Test using the wiki to draft thesis sections. Ask Claude to draft a paragraph for Chapter 2 using only wiki content. Does the output cite sources correctly? Is the glossary respected? Add a `draft` workflow to CLAUDE.md if useful.
- [ ] **Custom entity types.** Do you need entities beyond source/concept/analysis? (e.g., `method`, `dataset`, `tool`, `argument`). Add only what real usage has shown you need.

### Exit criterion
The wiki is actively useful for thesis writing, not just knowledge storage. You can ask a question and get an answer grounded in your compiled sources. The scaffolding is a real document you'd show your advisor.

---

## Phase 5 — Agent Transition (1–2 sessions)

**Goal:** Move from Claude Code sessions to a persistent agent that maintains the wiki continuously.

### Tasks

- [ ] **Evaluate persistent agent options.** At this point assess:
  - Claude with MCP (long-running session with Roam MCP server)
  - Custom agent via Claude API + Roam API (your own orchestration)
  - Roam-native AI (Live AI Assistant extension) for lighter tasks
  - Decide on architecture: one persistent agent or specialised agents (ingest agent, query agent, lint agent)?
- [ ] **Extract session-dependent patterns.** Review CLAUDE.md for anything that assumes a Claude Code session (file reads, bash commands, session start checklist). Replace with MCP-native or API-native equivalents.
- [ ] **Build the persistent loop.** The agent should be able to:
  - Wake up and read `[[Scaffolding]]` + recent Daily Notes to orient itself
  - Accept ingest commands (via a trigger page, a queue, or direct chat)
  - Run periodic lint passes (daily? weekly?)
  - Respond to queries asynchronously
- [ ] **Test continuity.** Ingest a document with the persistent agent. Verify it produces the same quality output as the Claude Code sessions. Check that the conventions, glossary, and scaffolding discipline hold.
- [ ] **Handoff document.** Write a `[[Agent Handoff]]` page: what the agent must know, what conventions are non-negotiable, what's still evolving. This replaces CLAUDE.md for the persistent agent.

### Exit criterion
The persistent agent can run the full loop (ingest, query, lint) without manual intervention beyond providing the source document. CLAUDE.md and Agent Handoff page are in sync.

---

## Phase 6 — Compound & Extend (ongoing)

**Goal:** The system is running. Now it grows with your research.

### Ongoing tasks

- [ ] **Regular ingests.** Each new paper, call, or note goes through the pipeline. The wiki compounds.
- [ ] **Weekly lint.** Agent runs a consistency check. You review and approve fixes.
- [ ] **Monthly scaffolding review.** Step back and read the scaffolding as a whole. Does it still reflect your argument? Flag sections that have drifted.
- [ ] **Thesis drafting.** Use query + draft workflows to write chapters directly from wiki content.
- [ ] **Evolve the schema.** As your needs change, update CLAUDE.md / Agent Handoff. Version these changes in git so you can trace how your system evolved.

### Possible extensions (only if real need emerges)

- Multi-graph: separate graphs for different research areas, linked via a meta-index
- Collaboration: shared graph with advisor, agent-mediated
- Export pipeline: Roam → LaTeX/Word for thesis submission
- Fine-tuned prompts: specialised ingest prompts per document type (empirical paper vs. theoretical, survey vs. case study)

---

## Timeline Estimate

| Phase | Sessions | Calendar time | Depends on |
|---|---|---|---|
| 0 — Inventory & Infra | 1 | Day 1 | — |
| 1 — Minimal Schema | 1–2 | Days 2–3 | Phase 0 |
| 2 — First Ingest | 1 | Day 4 | Phase 1 |
| 3 — Refine Loop | 2–3 | Week 2 | Phase 2 |
| 4 — Thesis Customisation | 2–3 | Week 3 | Phase 3 |
| 5 — Agent Transition | 1–2 | Week 4 | Phase 4 |
| 6 — Compound | Ongoing | Week 5+ | Phase 5 |

**Realistic total to a working, customised system: ~4 weeks of part-time work.**

---

## What to track in this repo

This GitHub repo serves as the **meta-layer** for the project:

- `CLAUDE.md` — operating manual (versioned, diffable)
- `SKILL-thesis-ingest.md` — ingest skill (versioned, diffable)
- `implementation-roadmap.md` — this file (update as you complete phases)
- `information-flow-diagram.md` — architecture reference
- Friction logs and decisions: commit messages document why conventions changed

The Roam graph holds the **live knowledge**. This repo holds the **system design**. Both evolve, but they serve different purposes.

# Project Summary — Cognitive Architecture Research System

**Date:** 2026-05-04
**Branch:** `claude/analyze-repo-structure-77wn2`
**Repo:** `alaincr/cognitive-digital-twins`

---

## What this project is

A self-referential cognitive architecture that uses Roam Research as its single source of truth and studies its own components as the research subject. Built on top of the Karpathy LLM Wiki pattern, extended with a Paperclip multi-agent organization where 22 agents coordinate across 6 research tracks.

The system is simultaneously:
- **A tool** — it ingests sources, compiles knowledge, answers questions, audits itself
- **A research object** — each component (perception, memory, reasoning, planning, meta-cognition, auto-research) is its own research track with its own sub-thesis

---

## Work completed this session

### 1. Repository analysis
- Analysed the original repo content (69 files from the Politecnico di Torino thesis vault)
- Documented the objective, technical choices, and interesting implementation points
- Compared the setup to Andrej Karpathy's LLM Wiki pattern (April 2026 gist)

### 2. Restored thesis vault files
- Recovered all 69 files from the reverted initial commit (`23e54d9`)
- Includes: 12 research papers (PDFs + summaries), call transcripts, thesis proposal, wiki structure
- **Commit:** `1850b26`

### 3. Information flow diagrams
- Created 4 Mermaid diagrams covering: ingest flow, query flow, lint flow, memory architecture
- Stored at repo root (`information-flow-diagram.md`) and in `wiki/analyses/`
- **Commits:** `27e15e0`, `d1bef4e`

### 4. Implementation roadmap
- First version: linear 6-phase plan for Roam-based LLM Wiki
- Restructured after pivot: hub-and-spoke model centred on 6 cognitive components as parallel research tracks
- Roam as single source of truth, git repo as versioned meta-layer
- **Commits:** `d8d31ff`, `aee5ad5`

### 5. Full Paperclip agent organization (68 files)
- Designed and generated configurations for **22 agents** across **8 teams**
- Each agent has: `agent.yaml` (Paperclip config), `soul.md` (identity & principles), `heartbeat.md` (recurring tasks)

#### Agent roster

| Team | Manager | IC 1 | IC 2 |
|---|---|---|---|
| CEO | Chief Architect | — | — |
| Coordination | Integration Director | Thesis Synthesizer | Cross-Team Reviewer |
| Perception | Perception Lead | Perception Researcher | Perception Builder |
| Memory | Memory Lead | Memory Researcher | Memory Builder |
| Reasoning | Reasoning Lead | Reasoning Researcher | Reasoning Builder |
| Planning | Planning Lead | Planning Researcher | Planning Builder |
| Meta-Cognition | MetaCog Lead | MetaCog Researcher | MetaCog Builder |
| Auto-Research | AutoRes Lead | AutoRes Researcher | AutoRes Builder |

#### Dual-thesis system
- **Top-level thesis** (CEO): "How does a self-referential cognitive architecture study and improve its own components?"
- **6 sub-theses** (Component Leads): one per component, feeding into the top-level argument
- Cross-pollination via Integration Director → Cross-Team Reviewer → Thesis Synthesizer → Scaffolding

**Commit:** `44e0baf`

---

## Current file inventory

```
cognitive-digital-twins/           (141 files total)
├── CLAUDE.md                      — operating manual (from original thesis vault)
├── SKILL-thesis-ingest.md         — ingest skill definition
├── LICENSE
├── implementation-roadmap.md      — phased plan with component tracks
├── information-flow-diagram.md    — 4 Mermaid diagrams
├── scaffolding-tesi.md            — (empty, from original)
├── PROJECT-SUMMARY.md             — this file
│
├── agents/                        (68 files)
│   ├── architecture.md            — org chart, communication model, tool access
│   ├── component-template.md      — reusable team pattern
│   ├── ceo/                       — Chief Architect (agent.yaml, soul.md, heartbeat.md)
│   ├── coordination/              — Integration Director, Thesis Synthesizer, Cross-Team Reviewer
│   ├── perception/                — Lead, Researcher, Builder
│   ├── memory/                    — Lead, Researcher, Builder
│   ├── reasoning/                 — Lead, Researcher, Builder
│   ├── planning/                  — Lead, Researcher, Builder
│   ├── meta-cognition/            — Lead, Researcher, Builder
│   └── auto-research/             — Lead, Researcher, Builder
│
├── raw/                           (original thesis sources — immutable)
│   ├── papers/                    — 12 paper folders (PDFs + riassunto + yt + valore-tesi)
│   ├── calls/                     — 2 call transcripts + template
│   └── project/                   — thesis proposal, feedback, deep-dives
│
└── wiki/                          (original thesis wiki)
    ├── index.md, log.md, overview.md, glossary.md
    ├── Scaffolding tesi.md
    └── analyses/
        └── information-flow-diagram.md
```

---

## What still needs to be done

### Immediate (next session)

- [ ] **Copy agent files to local Paperclip directory.** Files need to go from this repo to `/Users/alaincrawford/paperclip/` on local Mac. Run:
  ```bash
  cd /Users/alaincrawford
  git clone https://github.com/alaincr/cognitive-digital-twins.git
  cp -r cognitive-digital-twins/agents/* /Users/alaincrawford/paperclip/
  ```

- [ ] **Verify Roam MCP configuration.** Check `~/Library/Application Support/Claude/claude_desktop_config.json` on local Mac to confirm:
  - The Roam Research local MCP is installed (not the 2b3pro community version)
  - Datalog query capability is exposed (your custom modification)
  - Note the exact tool names so agent configs can reference them correctly

- [ ] **Update agent.yaml files with real MCP tool names.** The current configs use placeholder `roam_mcp` — replace with the actual tool names from your installed MCP server.

### Bootstrap (Phase 0)

- [ ] **Seed Roam graph with foundational pages:**
  - `[[Conventions]]` — namespace rules, attribute schema
  - `[[Scaffolding]]` — top-level thesis + 6 component sections
  - `[[Glossary]]` — initial canonical terms
  - `[[Overview]]` — what this is and why
  - 6 operational pages: `[[Perception]]`, `[[Memory]]`, `[[Reasoning]]`, `[[Planning]]`, `[[Meta-Cognition]]`, `[[Auto-Research]]`
  - 6 research track pages: `[[R/Perception]]`, `[[R/Memory]]`, etc.
  - `[[Friction Log]]`

- [ ] **Consolidate existing ideas into Roam.** Dump your existing ideas for each component into the corresponding `[[R/...]]` research track pages. Unstructured is fine — this is the raw material the Researcher agents will work from.

- [ ] **Write CLAUDE.md for Roam.** Adapt the operating manual from flat-file conventions to Roam-native conventions (blocks, attributes, backlinks, Datalog queries). Store both in git (for Claude Code) and as `[[CLAUDE.md]]` in Roam (for persistent agent).

### First activation

- [ ] **Start Perception team first.** It feeds all other teams. Ingest one real document through the full pipeline via Paperclip.
- [ ] **Validate Paperclip integration.** Confirm agents can read/write Roam via MCP during heartbeats. Test with a single agent before activating all 22.
- [ ] **Tune heartbeat intervals.** The current schedules (4×/day for ICs, 2×/day for managers, daily for CEO) are starting estimates. Adjust based on actual throughput and cost.

### Medium-term

- [ ] **Agent transition.** Move from Claude Code sessions to persistent agent orchestrated by Paperclip. Current configs use `claude_local` adapter — verify this works on your M-series Mac.
- [ ] **Cross-team communication testing.** Verify that the Integration Director → Cross-Team Reviewer → Thesis Synthesizer flow actually works in Paperclip's ticket system.
- [ ] **Cost monitoring.** 22 agents with multiple heartbeats/day will consume significant API tokens. Add budget constraints to agent.yaml files once you observe actual usage.

### Open design questions

- [ ] **Roam namespace convention.** `[[S/slug]]` vs `[[sources/slug]]` vs `#source` tag — decide before first ingest.
- [ ] **How to handle PDFs in Roam.** Roam can't store PDFs natively. Options: cloud folder with links, paste markdown summaries, or keep `raw/` in git and reference from Roam.
- [ ] **Agent model selection.** All agents currently use `claude-sonnet-4-6`. Consider whether some roles (CEO, Thesis Synthesizer) should use Opus for deeper reasoning, while Researchers/Builders use Sonnet or Haiku for cost efficiency.
- [ ] **Auto-Research triggers.** What causes the Auto-Research team to activate? Friction threshold, scheduled, or manual command?

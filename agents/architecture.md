# Paperclip Agent Architecture — Cognitive Architecture Research System

## Organization Chart

```
                        ┌──────────────────┐
                        │   Chief Architect │  CEO
                        │   (CEO)           │  Owns top-level thesis
                        └────────┬─────────┘
                                 │
              ┌──────────────────┼──────────────────────────────────────────┐
              │                  │                                          │
   ┌──────────┴────────┐   ┌────┴──────────┐                    ┌─────────┴──────────┐
   │ Integration       │   │  Component    │ ×6                 │  Auto-Research     │
   │ Director          │   │  Lead         │                    │  Lead              │
   │ (Manager)         │   │  (Manager)    │                    │  (Manager)         │
   └──┬────────────┬───┘   └──┬─────────┬──┘                    └──┬──────────┬──────┘
      │            │          │         │                           │          │
 ┌────┴───┐  ┌─────┴────┐ ┌──┴────┐ ┌──┴─────┐              ┌─────┴───┐ ┌────┴──────┐
 │Thesis  │  │Cross-Team│ │Resear-│ │Builder │              │Research │ │Improvement│
 │Synth.  │  │Reviewer  │ │cher   │ │        │              │Scout    │ │Tester     │
 │(IC)    │  │(IC)      │ │(IC)   │ │(IC)    │              │(IC)     │ │(IC)       │
 └────────┘  └──────────┘ └───────┘ └────────┘              └─────────┘ └───────────┘
```

## Agent Count: 22 total

| Role | Count | Names |
|---|---|---|
| CEO | 1 | Chief Architect |
| Managers | 8 | Integration Director, Perception Lead, Memory Lead, Reasoning Lead, Planning Lead, Meta-Cognition Lead, Auto-Research Lead |
| ICs | 14 | Thesis Synthesizer, Cross-Team Reviewer, + 2 per component team (Researcher + Builder) |

## How the dual-thesis system works

### Top-level thesis (owned by CEO + Integration Director)
> "How does a self-referential cognitive architecture study and improve its own components?"

The Thesis Synthesizer IC maintains the `[[Scaffolding]]` in Roam — the unified argument.

### Component theses (owned by each Component Lead)
Each of the 6 components has its own sub-thesis:

| Component | Sub-thesis question |
|---|---|
| Perception | How should a cognitive system optimally ingest and distill knowledge from heterogeneous sources? |
| Memory | How should compiled knowledge be structured, linked, and retrieved in a graph-based memory system? |
| Reasoning | How should an agent synthesize across compiled knowledge to produce reliable novel analysis? |
| Planning | How should an evolving argumentative structure maintain coherence while absorbing new evidence? |
| Meta-Cognition | How can a system reliably audit its own knowledge for consistency, completeness, and decay? |
| Auto-Research | How can a cognitive system identify, test, and integrate improvements to its own components? |

### Cross-pollination flow
1. Component teams work on their sub-thesis independently
2. When a component team produces a finding, the **Component Lead** flags it as potentially relevant to the top-level thesis
3. The **Cross-Team Reviewer** evaluates cross-cutting proposals
4. The **Thesis Synthesizer** integrates approved findings into `[[Scaffolding]]`
5. The **CEO** resolves conflicts between component sub-theses and the top-level thesis

## Communication model

All communication flows through Paperclip's ticket/issue system:
- **Downward:** CEO → Managers → ICs via delegated issues
- **Upward:** ICs → Managers → CEO via issue updates and proposals
- **Cross-team:** Routed through Integration Director (never direct IC-to-IC across teams)
- **Shared state:** Roam graph is the shared memory; agents read/write via MCP

## Heartbeat schedule

| Agent type | Heartbeat interval | Rationale |
|---|---|---|
| CEO | Daily | Strategic review, conflict resolution |
| Integration Director | 2× daily | Cross-team coordination needs faster cadence |
| Component Leads | 2× daily | Manage their team's work queue |
| Thesis Synthesizer | Daily | Scaffolding updates after component work settles |
| Cross-Team Reviewer | Daily | Review proposals accumulated during the day |
| Researchers | 4× daily | Active research needs frequent cycles |
| Builders | 4× daily | Implementation/testing needs frequent cycles |
| Auto-Research ICs | 2× daily | Slower, more deliberate cadence |

## Tool access

All agents get:
- Roam MCP (read/write/query the graph)
- File system (read git repo for instructions, skills)

Additionally:
- **Researchers** get: web search, web fetch (for literature)
- **Builders** get: code execution (for testing implementations)
- **Auto-Research ICs** get: web search, web fetch, code execution
- **Cross-Team Reviewer** gets: read-only access to all team workspaces

# CLAUDE.md — Cognitive Architecture Research System (Roam-native)

This is the operating manual for any agent (Claude Code session, Paperclip
heartbeat, manual session) working on this project. Read it at the start of
every session.

The previous flat-file manual (Italian, scaffolding-tesi flow) is archived
at `docs/CLAUDE-flatfile.md`. It is the historical record of how the thesis
vault was operated; this file is the live manual and supersedes it.

A copy of this document also lives in Roam as `[[CLAUDE.md]]` so that the
persistent agent has the same instructions when it boots without filesystem
access.

> **ADR-001 (ratified 2026-07-04, `files_mnemosyne/prd/ADR-001.md`) amends
> this manual.** The single source of epistemic truth is the Mnemosyne
> append-only event log (`files_mnemosyne/store/events.jsonl`); Roam is the
> human capture-and-restitution surface (its export feeds the loop via B1,
> the `M/*` namespace is its projection via B2); the repo remains the spec.
> The Paperclip 22-agent organization is superseded by behaviors + judges +
> the single consolidator — `agents/` is archived stratum-3 material, and
> any resurrection requires a new ADR. Where the text below says "Roam is
> the truth", read it through this amendment.

---

## What this system is

A self-referential cognitive architecture whose **source of epistemic truth
is the Mnemosyne append-only event log** (ADR-001), with **Roam Research as
the human capture-and-restitution surface**, and which studies its own
components as the research subject. The git repo is a versioned meta-layer:
agent configs, skills, diagrams, immutable raw sources, and this manual.
Live human-facing knowledge is captured and restituted in Roam.

Top-level thesis (owned by the Chief Architect agent, maintained by the
Thesis Synthesizer):

> How does a self-referential cognitive architecture study and improve
> its own components?

Six components, each with its own sub-thesis:
Perception, Memory, Reasoning, Planning, Meta-Cognition, Auto-Research.
Each component is simultaneously a piece of operational machinery and a
research track studying that piece. See `agents/architecture.md` for the
full org chart.

---

## Source-of-truth split

| Lives in git | Lives in Roam |
|---|---|
| Agent configs (`agents/<team>/<agent>/{agent.yaml,soul.md,heartbeat.md}`) | The thesis itself (`[[Scaffolding]]`) |
| Skills and operating manuals (this file, `SKILL-*.md`) | All source pages (`[[S/...]]`) |
| Architecture and flow diagrams | All concept pages |
| Immutable raw sources (`raw/`) | Operational state — `[[Friction Log]]`, `[[Log]]`, `[[R/...]]` research tracks |
| Roadmap, summaries | Glossary, conventions, overview |
| The legacy flat-file wiki (`wiki/`, frozen 2026-06-10) | |

If a fact is mutable and accumulates over time, it belongs in Roam.
If a fact is structural and versioned by git, it belongs in the repo.

The `wiki/` directory is the frozen flat-file thesis vault that preceded the
Roam pivot. Do not resume ingesting into it; its content is migration input
for Roam (see `bootstrap/README.md`).

---

## Roam conventions

### Page naming

| Pattern | Meaning | Example |
|---|---|---|
| `[[Capitalized Phrase]]` | Operational page | `[[Scaffolding]]`, `[[Glossary]]`, `[[Friction Log]]` |
| `[[Component]]` | One of the six components | `[[Perception]]`, `[[Memory]]` |
| `[[R/Component]]` | Research track for that component | `[[R/Perception]]` |
| `[[S/<slug>]]` | A source (paper, call, deep-dive) — slug is kebab-case | `[[S/karpathy-llm-wiki]]` |
| `[[C/<term>]]` | A theoretical concept | `[[C/episodic-memory]]` |
| `[[A/<slug>]]` | An analysis (gap analysis, comparison, synthesized output) | `[[A/perception-gap-2026-05]]` |

The `[[S/]]`, `[[C/]]`, `[[A/]]` namespacing is the resolution of an open
design question — it gives a clean Datalog filter (`[?p :node/title ?t]
[(clojure.string/starts-with? ?t "S/")]`) without colliding with prose mentions.
Plain `[[Term]]` references in prose still work because they don't carry the
prefix.

### Block structure

Every block represents one atomic claim or fact. Don't paste paragraphs into
a single block — split on sentence boundaries when each sentence carries an
independent claim. This makes blocks individually citable, queryable, and
movable.

### Attributes (used as block-level metadata)

Use Roam's `attribute::` syntax to make blocks Datalog-queryable:

```
type:: source
created:: [[May 5th, 2026]]
sources:: [[S/karpathy-llm-wiki]] [[S/cog-arch-survey-2025]]
component:: [[Perception]]
status:: draft | reviewed | integrated | superseded
```

Canonical attribute keys:
- `type::` — `source | concept | analysis | rule | open-question | finding`
- `component::` — one of the six component pages
- `sources::` — backlinks to `[[S/...]]` pages this block depends on
- `status::` — for findings/proposals
- `confidence::` — `low | medium | high` (for claims that aren't certain)
- `decision-date::` — when a decision was made

If a new attribute key is needed, add it to `[[Conventions]]` first.

### Backlinks

Every claim that references another page must link via `[[...]]`. Don't
write prose like "as shown by Karpathy's wiki pattern" — write
"as shown by [[S/karpathy-llm-wiki]]". This is what makes the graph
queryable.

When you create or update a page, do a backlink sweep: open every linked
page and confirm it has a return reference back to this page where
appropriate. The Memory team owns enforcing this; everyone else is
expected to do it best-effort.

---

## Workflows

### Ingest a new source (paper / call / deep-dive)

Owner: Perception team.

1. Place the raw file in `raw/papers/<slug>/`, `raw/calls/<slug>.md`, or
   `raw/project/approfondimenti/<slug>.md`. Never modify these after
   creation.
2. Read the raw file end-to-end. Do not skim.
3. Create `[[S/<slug>]]` in Roam with attributes:
   ```
   type:: source
   raw-path:: raw/papers/<slug>/
   created:: [[<today>]]
   authors:: <names>
   year:: <YYYY>
   relevance:: <one-line of why this matters to the thesis>
   ```
4. Under that page, create blocks for:
   - Key claims (one block per claim, each with `confidence::` if non-obvious)
   - Terminology introduced (cross-link to `[[Glossary]]`, propose new
     `[[C/...]]` pages if missing)
   - Tensions with existing sources (block-link to the conflicting block)
   - Implications for the thesis (one block per implication, link to the
     relevant `[[Component]]` or `[[Scaffolding]]` section)
5. Append an entry to `[[Log]]`:
   `[[<today>]] ingest [[S/<slug>]] — <one-line summary>`
6. If the source materially changes the argument, open a proposal block on
   the relevant `[[Component]]` page tagged `#proposal` for the Component
   Lead to review in their next heartbeat.

### Ingest into a research track (`[[R/<Component>]]`)

Owner: that component's Researcher.

Research tracks accept rougher material than source pages. Dump
unstructured notes, half-formed hypotheses, and exploration. The
Researcher's heartbeat job is to refine these into either: a new `[[C/...]]`
concept page, a proposal block on the `[[Component]]` page, or a deletion
(with reason in `[[Log]]`).

### Query

Owner: any agent or human.

1. Search Roam for relevant pages (start from `[[Overview]]`,
   `[[Scaffolding]]`, the relevant `[[Component]]`).
2. Use Datalog queries for structural questions
   (e.g. "all blocks with `status:: draft` referenced from
   `[[Scaffolding]]`").
3. Synthesize an answer with citations as `[[S/...]]` and `((block-ref))`
   links.
4. If the answer is novel and worth keeping, save it as `[[A/<slug>]]`.
5. Append to `[[Log]]`:
   `[[<today>]] query "<question>" — answered, archived as [[A/<slug>]]`

### Lint

Owner: Meta-Cognition team.

Triggered by Meta-Cognition heartbeats and on user request. Checks:

- Contradictions: blocks that disagree on the same fact (cross-source).
- Orphans: pages with no inbound `[[...]]` references.
- Missing concept pages: terms used as `[[C/...]]` that don't exist.
- Glossary drift: terms used inconsistently with their `[[Glossary]]`
  definition.
- Stale findings: blocks with `status:: integrated` whose source pages have
  been superseded.
- Scaffolding gaps: claims in `[[Scaffolding]]` not backed by any
  `[[S/...]]` source.

Findings go to `[[Friction Log]]` for the relevant team's Lead to triage.

### Friction → Auto-Research

Owner: Auto-Research team.

Every agent appends to `[[Friction Log]]` when something blocks them.
When the friction count for a component crosses a threshold (initial:
5 unresolved frictions in a 7-day window), the AutoRes Lead opens an
investigation. See `agents/auto-research/autores-lead/heartbeat.md`.

---

## Cross-team communication

All cross-team work flows through Paperclip's ticket system:

- **Downward**: CEO → Managers → ICs via delegated issues.
- **Upward**: ICs → Managers → CEO via issue updates and proposals.
- **Cross-component**: Routed through the Integration Director. ICs do not
  message ICs on other teams directly.
- **Shared state**: The Roam graph. Agents read/write via the Roam MCP.

When a Component Lead believes their team has produced something
relevant to the top-level thesis, they file a proposal ticket to the
Integration Director with: the proposal block link, why it's
cross-cutting, and what they want reviewed. The Cross-Team Reviewer
evaluates; the Thesis Synthesizer integrates approved items into
`[[Scaffolding]]`.

---

## Session start checklist

Whether you're a heartbeat agent or a manual session:

1. Read this file.
2. Read `[[Overview]]` for the current state of the project.
3. Read the last 5 entries in `[[Log]]` to see recent activity.
4. Read `[[Scaffolding]]` for the current shape of the argument.
5. If you're a component agent, read your `[[Component]]` page and your
   `[[R/Component]]` track.
6. Check `[[Friction Log]]` for unresolved items relevant to your role.
7. Read your inbox (Paperclip tickets assigned to you).

If Roam is not reachable (no MCP configured in this session), say so
explicitly and fall back to repo-only work: agent configs, bootstrap pages,
diagrams, raw sources. Do not resume the legacy flat-file wiki workflows.

---

## Operating principles

1. **The log is the truth, Roam is the surface, the repo is the spec**
   (ADR-001). The append-only event log (`files_mnemosyne/store/
   events.jsonl`) wins on epistemic facts; Roam is where humans capture
   input and read back the system's projections (`M/*`); when the
   disagreement is about how the system should operate, the repo wins.
2. **Block-level discipline.** One claim per block. Cite via `[[...]]` and
   `((block-ref))`. Atomic blocks are reusable; paragraphs are not.
3. **Don't rewrite, evolve.** When new evidence arrives, append, annotate,
   and supersede — don't silently overwrite. `status:: superseded` is
   preferred over deletion.
4. **Surface tensions, don't suppress them.** Two sources that disagree is
   a finding, not a problem. Make the disagreement explicit and let the
   Reasoning team handle it.
5. **The system is the experiment.** Every operational decision is a data
   point for the meta-thesis. Log what you decided and why.

---

## Open conventions still to ratify

These are unresolved as of this writing — the first agent to encounter
them in practice should propose a resolution on `[[Conventions]]` and
flag it for the Integration Director.

- **PDF storage**: Roam can't host PDFs natively. Current default: keep
  PDFs in `raw/papers/<slug>/` in the repo, reference from Roam via
  `raw-path::` attribute on the `[[S/...]]` page.
- **Auto-Research trigger threshold**: Initial value 5 frictions / 7 days
  is a guess. Tune based on observed throughput.
- **Model selection per role**: All agents currently use
  `claude-sonnet-4-6`. The CEO and Thesis Synthesizer may benefit from
  Opus; Researchers and Builders may be cost-effective on Haiku for
  bulk work.

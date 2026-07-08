# SPEC-03 · WP-1b — Belief layer (`belief.py` + `belief.clj` mirror)

**Objective:** the stance computer — the component that makes "RAG answers
questions; this maintains positions" literally true. Input: the discourse
edges the consolidator promotes (`supports` / `opposes` / `refines`). Output:
a computed, explainable **stance per claim**, recomputed when evidence changes.

**Deliverables:** `belief.py` (reference implementation, exhaustively
unit-tested — this WP has the highest verification-value-per-line in Phase 1),
`belief.clj` (consolidator-side mirror, hand-checked policy), a 5-line export
patch to `ingest.clj`, and this spec's test vectors as fixtures.

---

## 1 · Semantics (normative — the decisions and their reasons)

**Framework:** bipolar argumentation over the promoted discourse graph.
Arguments `A` = claim nodes ∪ evidence nodes (each carries a proposition).
`R_att` ⊆ A×A from `opposes` edges (attacker → attacked). `R_sup` from
`supports`. `refines` edges are **excluded from the semantics entirely** —
they are scope annotations, reported as qualifiers on the stance (see §4),
never as attacks or supports.

**Labelling semantics: GROUNDED.** Reasons (record in the module docstring):
grounded is *unique* (no extension-selection policy needed), *skeptical*
(the correct default for legal/compliance use — a claim is accepted only when
its defense is airtight), *polynomial* (least fixpoint ⇒ linear-time with the
counter algorithm below ⇒ IVM-friendly and CALM-monotone in its accretion),
whereas preferred/stable semantics are credulous, potentially multiple, and
NP-hard. Do not implement alternatives in v1; §8 records the upgrade paths.

**Support semantics: EVIDENTIAL (tally, not inference).** Supports do **not**
participate in the labelling. The labelling runs on attacks only; supports are
then counted — but **only supporters labelled IN count**. Rationale: mixing
support into attack semantics (deductive/necessary support, mediated attacks)
multiplies edge cases and destroys the uniqueness/monotonicity story; the
evidential reading keeps the semantics crisp and explainable ("structure
decides; everything else decorates"). The crucial interaction is preserved for
free: attacking an evidence node knocks it OUT, which removes it from every
tally it fed — undercutting works through the labelling, not through special
edges.

**Consequence to document loudly:** a claim with zero attackers is IN even
with zero support. The *stance vocabulary* (not the labelling) distinguishes
these — see §4.

## 2 · The grounded labelling — exact algorithm (normative)

Input: `atts: dict[node_id, set[node_id]]` mapping each node to its attackers
(nodes absent from the dict have no attackers; the node universe is
`nodes ∪ keys ∪ all attackers`).

Counter-based linear algorithm (this exact one — it is the semi-naive /
IVM-shaped form):

```
label[n]   := UNDEC for all n
alive[n]   := |attackers(n)|          # attackers not yet OUT
queue      := [n : alive[n] == 0]     # unattacked → will be IN
while queue not empty:
    n := pop(queue)
    if label[n] != UNDEC: continue
    label[n] := IN
    for m in attacked_by(n):          # reverse index
        if label[m] == UNDEC:
            label[m] := OUT
            for k in attacked_by(m):
                alive[k] -= 1
                if alive[k] == 0 and label[k] == UNDEC:
                    push(queue, k)
# remaining UNDEC stay UNDEC
```

Properties to assert in tests: O(|A|+|R_att|); **iteration-order invariant**
(the grounded labelling is unique — shuffle inputs, assert identical output);
self-attacks and cycles fall out as UNDEC with no special-casing.

## 3 · Module API (`belief.py`)

```python
Label = Literal["in", "out", "undec"]

def grounded_labelling(nodes: set[str],
                       atts: dict[str, set[str]]) -> dict[str, Label]

@dataclass
class AF:                    # built by the adapter
    nodes: set[str]
    atts: dict[str, set[str]]        # attacked -> attackers
    sups: dict[str, set[str]]        # supported -> supporters
    refines: dict[str, list[dict]]   # claim -> [{from, edge_id}]
    edge_prov: dict[tuple, str]      # (src,dst,type) -> edge_id

def from_promoted_edges(rows: Iterable[dict]) -> AF
    # row: {"edge_type": "supports|opposes|refines|...",
    #       "from": id, "to": id, "edge_id": id}   (others ignored)

def stance_report(af: AF) -> dict[str, dict]     # per node, see §4
def explain(af: AF, labelling, node_id) -> dict  # §5
def update(af, added: list[row], retracted: list[edge_id]) -> dict
    # v1: rebuild + full recompute + DIFF of labellings; returns
    # {"changed": {id: (old,new)}, "labelling": …}. The signature is the
    # incremental contract; a true delta engine is a later swap-in.
```
CLI: `compute --edges edges.jsonl [--out stances.jsonl]`,
`explain --edges … --node ID`, `self-test`. Stdlib only.

## 4 · Stance vocabulary (the report per node)

| status | condition |
|---|---|
| `accepted-supported` | label IN ∧ ≥1 IN supporter |
| `accepted-undisputed` | label IN ∧ 0 IN supporters (nothing spoke against it — but nothing FOR it either; downstream consumers must treat this differently from supported) |
| `rejected` | label OUT |
| `undecided` | label UNDEC |

Report row:
```json
{"node": "clm-1", "status": "accepted-supported",
 "label": "in",
 "support": {"n": 2, "in_supporters": ["evd-1","evd-4"],
             "defeated_supporters": ["evd-2"]},
 "attackers": {"in": [], "out": ["evd-9"], "undec": []},
 "qualifiers": [{"from": "evd-7", "edge_id": "e-12"}],
 "basis_edges": ["e-3","e-5","e-12"],
 "computed_at": "<iso>"}
```
`basis_edges` = every edge that touched this node's outcome (attack edges on
it and on its attackers' defeat chain within `explain`'s tree, plus counted
support edges) — this is the provenance hook the substrate's cohort-retraction
relies on downstream.

## 5 · `explain` — minimal justification tree

For an IN node: its attackers, each with the IN counter-attacker that defeats
it (choose lexicographically-smallest IN attacker of the attacker for
determinism). For OUT: the IN attacker(s). For UNDEC: the cycle/undecided
attacker frontier (BFS until labels repeat, depth-capped at 6). Output: nested
dict + a rendered indented-text form. Determinism required (sorted traversal).

## 6 · Test plan — canonical vectors (all normative, expected outputs exact)

| # | Graph (att = →, sup = ⇒) | Expected |
|---|---|---|
| 1 | isolated `c` | c: in, `accepted-undisputed` |
| 2 | a→b | a in, b out |
| 3 | a→b, b→a | both undec |
| 4 | a→b→c (reinstatement) | a in, b out, **c in** |
| 5 | a→a | a undec; unrelated `z` unaffected (in) |
| 6 | 3-cycle a→b→c→a | all undec |
| 7 | 4-cycle a→b→c→d→a | all undec (grounded is skeptical; note in docstring: preferred would yield two extensions — this row is WHY grounded was chosen) |
| 8 | e⇒c, x→e, x unattacked | e out, c in but `accepted-undisputed` (support tally 0) |
| 9 | e⇒c, x→e, y→x | x out, e in, c `accepted-supported` (defended evidence counts) |
| 10 | r —refines→ c, nothing else | c in, refines listed in `qualifiers`, absent from atts/sups |
| 11 | property: 20 random shuffles of case-9's input rows ⇒ identical labelling & report | determinism |
| 12 | scale: random AF n=10 000, m=30 000 (seeded) completes < 5 s; label counts stable across 2 runs | linearity smoke |
| 13 | `update`: case 9, then retract y→x ⇒ diff = {x: out→in, e: in→out}; c flips to `accepted-undisputed` | delta contract |
| 14 | mixed: full case-9 + case-3 in one AF ⇒ components don't interfere | isolation |
| 15 | `explain(c)` in case 9 names y as x's defeater | justification correctness |

## 7 · Clojure mirror (`belief.clj`) + ingest patch

- **Export patch (`ingest.clj`, ~5 lines):** after each promotion cycle,
  append promoted discourse edges to `ops/edges.jsonl`
  (`{edge_id, edge_type, from, to}` — from `:edge/from`/`:edge/to`/`:edge/type`
  of `:discourse-edge` nodes not yet exported, mirroring `export-accepted!`'s
  flag pattern).
- `belief.clj`: the same counter algorithm as a consolidator function (NOT a
  Datalog rule — the labelling is non-monotone in the OUT/UNDEC assignments;
  **CALM placement: boundary, consolidator-only**, like promotion). Writes
  `:belief/status` + `:belief/computed-at` via an appended
  `stance.recomputed` event. Recompute scope v1: all claims within 2 hops of
  edges changed in the cycle (blast radius, not corpus). Hand-checked policy
  applies; the Python fixtures of §6 are the review checklist.

## 8 · Out of scope (recorded upgrade paths)

Weighted/gradual semantics (h-categorizer etc.) may later *decorate* stances
with a strength score but must never replace the labelling as the gate.
Deductive/necessary support: only if evidential proves too weak in practice —
revisit with real data, not speculation. True incremental labelling
(differential): behind the `update` signature when volumes demand it.

## 9 · Definition of Done

- [ ] `belief.py self-test` green: all 15 vectors, property test, scale smoke.
- [ ] `compute` + `explain` CLIs run against a checked-in
      `fixtures/edges_case9.jsonl`.
- [ ] `belief.clj` reviewed against the fixtures (checklist in PR); ingest
      export patch merged.
- [ ] Docstring records the two semantics decisions (grounded; evidential
      support) with their §1 rationales.
- [ ] Repository regression green with this self-test appended.

**Estimate:** 2 dev-days Python (most of it the tests — as intended), 1 day
Clojure mirror + patch.

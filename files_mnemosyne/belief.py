#!/usr/bin/env python3
"""belief.py — the Mnemosyne belief layer (WP-1b, SPEC-03).

Computes a STANCE per claim from the discourse edges the consolidator
promotes. "RAG answers questions; this maintains positions" — this is the
component that maintains them.

SEMANTICS DECISIONS (normative; see SPEC-03 §1 for the full rationale):

  Labelling = GROUNDED semantics over the attack graph (`opposes` edges).
    Chosen because grounded is UNIQUE (no extension-selection policy),
    SKEPTICAL (the right default for legal/compliance work: accept only what
    is airtightly defended), and POLYNOMIAL (a least fixpoint; the counter
    algorithm below is linear, hence IVM-friendly and CALM-monotone in its
    accretion). Preferred/stable semantics are credulous, possibly multiple,
    and NP-hard — recorded as non-options for the gate.

  Support = EVIDENTIAL (a tally, not inference). `supports` edges do NOT
    participate in the labelling; after labelling, only supporters labelled
    IN are counted. Undercutting still works: attacking an evidence node
    knocks it OUT of every tally it fed — through the labelling, with no
    special edge types. Consequence, stated loudly: a claim with zero
    attackers is IN even with zero support; the STANCE VOCABULARY (not the
    labelling) distinguishes `accepted-supported` from `accepted-undisputed`.

  `refines` edges are EXCLUDED from the semantics entirely — they are scope
    annotations, reported as qualifiers, never attacks or supports.

Stdlib only. CLI: compute / explain / self-test.
"""

from __future__ import annotations
import argparse
import datetime as _dt
import json
import pathlib
import random
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

Label = str  # "in" | "out" | "undec"


# ===========================================================================
# The grounded labelling — exact counter algorithm (SPEC-03 §2)
# ===========================================================================

def grounded_labelling(nodes: Set[str],
                       atts: Dict[str, Set[str]]) -> Dict[str, Label]:
    """Unique grounded labelling. O(|A| + |R_att|), iteration-order invariant
    (uniqueness of the grounded extension guarantees it; tests assert it)."""
    universe = set(nodes) | set(atts) | {a for s in atts.values() for a in s}
    attackers = {n: set(atts.get(n, ())) for n in universe}
    attacked_by: Dict[str, Set[str]] = defaultdict(set)   # attacker -> targets
    for tgt, srcs in attackers.items():
        for src in srcs:
            attacked_by[src].add(tgt)

    label: Dict[str, Label] = {n: "undec" for n in universe}
    alive = {n: len(attackers[n]) for n in universe}       # attackers not yet OUT
    queue = deque(sorted(n for n in universe if alive[n] == 0))

    while queue:
        n = queue.popleft()
        if label[n] != "undec":
            continue
        label[n] = "in"
        for m in attacked_by[n]:                # everything n attacks is OUT
            if label[m] == "undec":
                label[m] = "out"
                for k in attacked_by[m]:        # m's targets lose an attacker
                    alive[k] -= 1
                    if alive[k] == 0 and label[k] == "undec":
                        queue.append(k)
    return label


# ===========================================================================
# The framework object + adapter
# ===========================================================================

@dataclass
class AF:
    nodes: Set[str] = field(default_factory=set)
    atts: Dict[str, Set[str]] = field(default_factory=dict)      # attacked -> attackers
    sups: Dict[str, Set[str]] = field(default_factory=dict)      # supported -> supporters
    refines: Dict[str, List[dict]] = field(default_factory=dict) # claim -> [{from, edge_id}]
    edge_prov: Dict[Tuple[str, str, str], str] = field(default_factory=dict)
    rows: List[dict] = field(default_factory=list)               # original rows (for update)


def from_promoted_edges(rows: Iterable[dict]) -> AF:
    """rows: {"edge_type": "supports|opposes|refines|…", "from": id,
    "to": id, "edge_id": id?} — unknown edge types are ignored (they belong
    to other subsystems: same-as, duplicate-of, …)."""
    af = AF()
    for r in rows:
        et, src, dst = r["edge_type"], r["from"], r["to"]
        eid = r.get("edge_id") or f"{src}->{dst}#{et}"
        af.rows.append({**r, "edge_id": eid})
        af.nodes |= {src, dst}
        if et == "opposes":
            af.atts.setdefault(dst, set()).add(src)
            af.edge_prov[(src, dst, "opposes")] = eid
        elif et == "supports":
            af.sups.setdefault(dst, set()).add(src)
            af.edge_prov[(src, dst, "supports")] = eid
        elif et == "refines":
            af.refines.setdefault(dst, []).append({"from": src, "edge_id": eid})
            af.edge_prov[(src, dst, "refines")] = eid
        # else: ignored by the belief layer
    return af


# ===========================================================================
# Stance report (SPEC-03 §4)
# ===========================================================================

def _status(lab: Label, n_in_supp: int) -> str:
    if lab == "in":
        return "accepted-supported" if n_in_supp else "accepted-undisputed"
    return "rejected" if lab == "out" else "undecided"


def stance_report(af: AF,
                  labelling: Optional[Dict[str, Label]] = None) -> Dict[str, dict]:
    lab = labelling or grounded_labelling(af.nodes, af.atts)
    now = _dt.datetime.now(_dt.timezone.utc).isoformat()
    rep: Dict[str, dict] = {}
    for n in sorted(af.nodes):
        supp = sorted(af.sups.get(n, ()))
        in_s = [s for s in supp if lab.get(s) == "in"]
        out_s = [s for s in supp if lab.get(s) == "out"]
        und_s = [s for s in supp if lab.get(s) == "undec"]
        attackers = sorted(af.atts.get(n, ()))
        by = lambda l: [a for a in attackers if lab.get(a) == l]
        basis = set()
        for a in attackers:                                   # attacks on n
            basis.add(af.edge_prov.get((a, n, "opposes"), f"{a}->{n}#opposes"))
            for b in sorted(af.atts.get(a, ())):              # n's defense
                if lab.get(b) == "in":
                    basis.add(af.edge_prov.get((b, a, "opposes"),
                                               f"{b}->{a}#opposes"))
        for s in in_s:                                        # counted support
            basis.add(af.edge_prov.get((s, n, "supports"), f"{s}->{n}#supports"))
        for q in af.refines.get(n, []):
            basis.add(q["edge_id"])
        rep[n] = {"node": n, "label": lab.get(n, "undec"),
                  "status": _status(lab.get(n, "undec"), len(in_s)),
                  "support": {"n": len(in_s), "in_supporters": in_s,
                              "defeated_supporters": out_s,
                              "undecided_supporters": und_s},
                  "attackers": {"in": by("in"), "out": by("out"),
                                "undec": by("undec")},
                  "qualifiers": sorted(af.refines.get(n, []),
                                       key=lambda q: q["edge_id"]),
                  "basis_edges": sorted(basis),
                  "computed_at": now}
    return rep


# ===========================================================================
# Explain (SPEC-03 §5): minimal deterministic justification tree
# ===========================================================================

def _defeater(af: AF, lab: Dict[str, Label], attacker: str) -> Optional[str]:
    ins = sorted(b for b in af.atts.get(attacker, ()) if lab.get(b) == "in")
    return ins[0] if ins else None


def explain(af: AF, labelling: Dict[str, Label], node: str,
            _depth: int = 0) -> dict:
    lab = labelling.get(node, "undec")
    out = {"node": node, "label": lab}
    if lab == "in":
        out["attackers"] = [{"attacker": a, "label": labelling.get(a),
                             "defeated_by": _defeater(af, labelling, a)}
                            for a in sorted(af.atts.get(node, ()))]
        if _depth == 0:  # one defense level into counted support (vector 15)
            out["supporters"] = [
                {"supporter": s, "label": labelling.get(s),
                 **({"why": explain(af, labelling, s, 1)}
                    if labelling.get(s) == "in" else {})}
                for s in sorted(af.sups.get(node, ()))]
    elif lab == "out":
        out["in_attackers"] = sorted(a for a in af.atts.get(node, ())
                                     if labelling.get(a) == "in")
    else:  # undec: BFS the undecided attacker frontier, depth-capped
        frontier, seen, layers = {node}, {node}, []
        for _ in range(6):
            nxt = {a for f in frontier for a in af.atts.get(f, ())
                   if labelling.get(a) == "undec" and a not in seen}
            if not nxt:
                break
            layers.append(sorted(nxt))
            seen |= nxt
            frontier = nxt
        out["undecided_frontier"] = layers
    return out


def render_explain(tree: dict, indent: int = 0) -> str:
    pad = "  " * indent
    lines = [f"{pad}{tree['node']} [{tree['label']}]"]
    for a in tree.get("attackers", []):
        lines.append(f"{pad}  attacked by {a['attacker']} [{a['label']}]"
                     + (f", defeated by {a['defeated_by']}"
                        if a.get("defeated_by") else ""))
    for s in tree.get("supporters", []):
        lines.append(f"{pad}  supported by {s['supporter']} [{s['label']}]")
        if "why" in s:
            lines.append(render_explain(s["why"], indent + 2))
    if tree.get("in_attackers"):
        lines.append(f"{pad}  defeated by {', '.join(tree['in_attackers'])}")
    for i, layer in enumerate(tree.get("undecided_frontier", []), 1):
        lines.append(f"{pad}  undecided via (hop {i}): {', '.join(layer)}")
    return "\n".join(lines)


# ===========================================================================
# Update contract (SPEC-03 §3): v1 = rebuild + diff; the SIGNATURE is the
# incremental contract a delta engine can later slot behind.
# ===========================================================================

def update(af: AF, added: List[dict], retracted: List[str]) -> dict:
    old = grounded_labelling(af.nodes, af.atts)
    ret = set(retracted)
    rows2 = [r for r in af.rows if r["edge_id"] not in ret] + list(added)
    af2 = from_promoted_edges(rows2)
    af2.nodes |= af.nodes   # retracting an EDGE never retracts a NODE: a
    # survivor with no remaining edges is an isolated argument (IN, per V1),
    # not a vanished one. Node retraction is a separate substrate operation.
    new = grounded_labelling(af2.nodes, af2.atts)
    changed = {n: (old.get(n, "undec"), new.get(n, "undec"))
               for n in af.nodes | af2.nodes
               if old.get(n, "undec") != new.get(n, "undec")}
    return {"changed": changed, "labelling": new, "af": af2}


# ===========================================================================
# Self-test — SPEC-03 §6 vectors, all 15
# ===========================================================================

def _lab(rows):
    af = from_promoted_edges(rows)
    return af, grounded_labelling(af.nodes, af.atts)


def _att(a, b, eid=None):
    return {"edge_type": "opposes", "from": a, "to": b,
            "edge_id": eid or f"{a}->{b}#opposes"}


def _sup(a, b, eid=None):
    return {"edge_type": "supports", "from": a, "to": b,
            "edge_id": eid or f"{a}->{b}#supports"}


def self_test() -> None:
    ok = lambda c, m: (print(f"  ✓ {m}") if c else
                       (_ for _ in ()).throw(AssertionError(m)))

    # 1 isolated node
    af = from_promoted_edges([_sup("e0", "c0")]); af.nodes.add("c")
    lab = grounded_labelling({"c"}, {})
    rep = stance_report(from_promoted_edges([]), {"c": "in"})
    ok(lab["c"] == "in", "V1: isolated node IN")

    # 2 simple attack
    _, l = _lab([_att("a", "b")])
    ok(l["a"] == "in" and l["b"] == "out", "V2: a->b => a in, b out")

    # 3 mutual attack
    _, l = _lab([_att("a", "b"), _att("b", "a")])
    ok(l["a"] == "undec" and l["b"] == "undec", "V3: mutual => both undec")

    # 4 reinstatement
    _, l = _lab([_att("a", "b"), _att("b", "c")])
    ok((l["a"], l["b"], l["c"]) == ("in", "out", "in"), "V4: reinstatement")

    # 5 self-attack isolated from bystander
    _, l = _lab([_att("a", "a"), _sup("z0", "z")])
    ok(l["a"] == "undec" and l["z"] == "in", "V5: self-attack undec, z unaffected")

    # 6 odd cycle
    _, l = _lab([_att("a", "b"), _att("b", "c"), _att("c", "a")])
    ok(all(l[x] == "undec" for x in "abc"), "V6: 3-cycle all undec")

    # 7 even cycle — grounded stays skeptical (why grounded was chosen:
    # preferred semantics would yield TWO extensions here)
    _, l = _lab([_att("a", "b"), _att("b", "c"), _att("c", "d"), _att("d", "a")])
    ok(all(l[x] == "undec" for x in "abcd"), "V7: 4-cycle all undec (skeptical)")

    # 8 undercut evidence => accepted-undisputed
    af, l = _lab([_sup("e", "c"), _att("x", "e")])
    rep = stance_report(af, l)
    ok(l["e"] == "out" and rep["c"]["status"] == "accepted-undisputed"
       and rep["c"]["support"]["n"] == 0
       and rep["c"]["support"]["defeated_supporters"] == ["e"],
       "V8: undercut evidence => c accepted-undisputed")

    # 9 defended evidence counts
    rows9 = [_sup("e", "c"), _att("x", "e"), _att("y", "x")]
    af9, l9 = _lab(rows9)
    rep9 = stance_report(af9, l9)
    ok(l9["x"] == "out" and l9["e"] == "in"
       and rep9["c"]["status"] == "accepted-supported"
       and rep9["c"]["support"]["in_supporters"] == ["e"],
       "V9: defended evidence => c accepted-supported")
    ok("e->c#supports" in rep9["c"]["basis_edges"], "V9b: basis edges carry provenance")

    # 10 refines excluded, reported as qualifier
    af10, l10 = _lab([{"edge_type": "refines", "from": "r", "to": "c",
                       "edge_id": "e-12"}])
    rep10 = stance_report(af10, l10)
    ok(l10["c"] == "in" and rep10["c"]["qualifiers"] == [{"from": "r", "edge_id": "e-12"}]
       and not af10.atts and not af10.sups,
       "V10: refines => qualifier only, outside semantics")

    # 11 permutation invariance (uniqueness in practice)
    rng = random.Random(7)
    base = list(rows9)
    for _ in range(20):
        rng.shuffle(base)
        _, lp = _lab(base)
        ok2 = lp == l9
        if not ok2:
            raise AssertionError("V11 failed")
    print("  ✓ V11: 20 shuffles => identical labelling")

    # 12 scale smoke: n=10k, m=30k, <5s, stable
    rng = random.Random(0)
    N = 10_000
    rows = [_att(f"n{rng.randrange(N)}", f"n{rng.randrange(N)}", f"e{i}")
            for i in range(30_000)]
    t0 = time.time(); _, lA = _lab(rows); dt = time.time() - t0
    _, lB = _lab(rows)
    from collections import Counter
    ok(dt < 5 and lA == lB, f"V12: 10k/30k in {dt:.2f}s, stable "
                            f"{dict(Counter(lA.values()))}")

    # 13 update contract: retract y->x
    r = update(af9, added=[], retracted=["y->x#opposes"])
    ok(r["changed"] == {"x": ("out", "in"), "e": ("in", "out")},
       "V13: update diff exact")
    ok(stance_report(r["af"], r["labelling"])["c"]["status"]
       == "accepted-undisputed", "V13b: c flips to accepted-undisputed")

    # 14 component isolation
    _, l14 = _lab(rows9 + [_att("p", "q"), _att("q", "p")])
    ok(l14["c"] == l9["c"] and l14["p"] == "undec", "V14: components isolated")

    # 15 explain(c) names y as x's defeater (through the support chain)
    tree = explain(af9, l9, "c")
    sup_e = next(s for s in tree["supporters"] if s["supporter"] == "e")
    ok(any(a["attacker"] == "x" and a["defeated_by"] == "y"
           for a in sup_e["why"]["attackers"]),
       "V15: explain(c) names y as x's defeater")
    ok("defeated by y" in render_explain(tree), "V15b: rendered text")

    print("all belief self-tests passed (15 vectors)")


# ===========================================================================
# CLI
# ===========================================================================

def _load_rows(path: str) -> List[dict]:
    return [json.loads(l) for l in pathlib.Path(path).read_text().splitlines()
            if l.strip()]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compute")
    c.add_argument("--edges", required=True)
    c.add_argument("--out", default=None)
    e = sub.add_parser("explain")
    e.add_argument("--edges", required=True)
    e.add_argument("--node", required=True)
    sub.add_parser("self-test")
    a = ap.parse_args()
    if a.cmd == "self-test":
        self_test(); return
    af = from_promoted_edges(_load_rows(a.edges))
    lab = grounded_labelling(af.nodes, af.atts)
    if a.cmd == "compute":
        rep = stance_report(af, lab)
        text = "".join(json.dumps(rep[n], ensure_ascii=False) + "\n"
                       for n in sorted(rep))
        if a.out:
            pathlib.Path(a.out).write_text(text)
        print(text if not a.out else f"wrote {len(rep)} stances -> {a.out}")
    else:
        print(render_explain(explain(af, lab, a.node)))


if __name__ == "__main__":
    main()

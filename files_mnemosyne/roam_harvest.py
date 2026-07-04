#!/usr/bin/env python3
"""roam_harvest.py — mine calibration candidates for the Mnemosyne micro-judges
from a Roam Research JSON export.

Produces, per judgment type, a JSONL of candidate rows shaped for
anchor_label.py and (after labeling) judge_harness.py calibrate:

    {"jtype": ..., "subjects": [...], "fields": {...}, "meta": {...}}

Harvesting strategies (stdlib-only; deliberately lexical/structural — the
calset SHOULD mix easy and hard cases, and the anchor sorts out noise):

  edge_type      discourse-graph pages (CLM-/EVD-/QUE- title prefixes, the
                 Roam discourse-graph convention) paired EVD->CLM; generic
                 fallback: block pairs sharing >=2 page-refs (+ zero-overlap
                 pairs as 'unrelated' seeds)
  same_entity    page-title pairs: high string similarity, containment, or
                 acronym match (with French stopwords skipped); plus
                 mid-similarity probable negatives
  dedup_prop     block-string pairs in similarity bands (high=duplicates,
                 mid=interesting, low sample=negatives)
  summarize_now  per-page cluster digests (inbound-ref count, page spread,
                 churn, samples); low-ref pages included as defer/never seeds
  propagate      recently edited block x (sibling | co-referencing block)
  invalidate     parent blocks whose children were edited AFTER the parent
                 (stale candidates) + fresh parents (keep seeds)
  faithful       quote blocks ('> ...') paired with paraphrase siblings
                 (sparse in most graphs — count may be 0; the propositionizer
                 pipeline is the richer source for this type)

Subcommands:
  harvest --export graph.json --out-dir calib/
  demo    [--out-dir demo_calib]   build a synthetic export, harvest it, report

Caveat (documented in README_calibration.md): Roam exports carry no edit
HISTORY, so 'propagate' frames the current text as the changed content; the
operative judgment (does this content materially bear on the neighbor?) is
preserved, the delta framing is not.
"""

from __future__ import annotations
import argparse
import datetime as _dt
import difflib
import itertools
import json
import pathlib
import random
import re
import unicodedata
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Parsing the export
# ---------------------------------------------------------------------------

REF_RE = re.compile(r"\[\[([^\[\]]+)\]\]")
TAG_RE = re.compile(r"(?<!\[)#([A-Za-z0-9_./-]+)")
BREF_RE = re.compile(r"\(\(([A-Za-z0-9_-]{6,})\)\)")
ATTR_RE = re.compile(r"^([^:`\n]{1,60})::")

FR_STOP = {"de", "des", "du", "la", "le", "les", "un", "une", "et", "en",
           "sur", "aux", "au", "à", "a", "d", "l", "pour", "of", "the", "and"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def sim(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def acronym(title: str) -> str:
    words = [w for w in norm(title).split() if w not in FR_STOP and len(w) >= 3]
    return "".join(w[0] for w in words)


class Graph:
    def __init__(self):
        self.blocks: Dict[str, dict] = {}            # uid -> block record
        self.pages: Dict[str, List[str]] = {}        # title -> top-level uids
        self.page_edit: Dict[str, int] = {}
        self.inbound: Dict[str, Set[str]] = defaultdict(set)  # page -> uids citing it

    def add_block(self, b: dict, page: str, parent: Optional[str], depth: int):
        uid = b.get("uid") or f"anon-{len(self.blocks)}"
        s = b.get("string", "") or ""
        refs = set(REF_RE.findall(s)) | set(TAG_RE.findall(s))
        rec = {"uid": uid, "string": s, "page": page, "parent": parent,
               "depth": depth, "children": [],
               "create": b.get("create-time", 0), "edit": b.get("edit-time", 0),
               "refs": refs, "brefs": set(BREF_RE.findall(s))}
        self.blocks[uid] = rec
        for r in refs:
            self.inbound[r].add(uid)
        for c in b.get("children", []) or []:
            cu = self.add_block(c, page, uid, depth + 1)
            rec["children"].append(cu)
        return uid

    @classmethod
    def parse(cls, export: list) -> "Graph":
        g = cls()
        for page in export:
            title = page.get("title", "untitled")
            tops = [g.add_block(b, title, None, 0)
                    for b in page.get("children", []) or []]
            g.pages[title] = tops
            g.page_edit[title] = max(
                [page.get("edit-time", 0)]
                + [g.blocks[u]["edit"] for u in g.all_under(tops)], default=0)
        return g

    def all_under(self, uids: Iterable[str]) -> List[str]:
        out, stack = [], list(uids)
        while stack:
            u = stack.pop()
            out.append(u)
            stack.extend(self.blocks[u]["children"])
        return out

    def expand_brefs(self, s: str) -> str:
        return BREF_RE.sub(
            lambda m: self.blocks.get(m.group(1), {}).get("string", m.group(0)), s)

    def loc(self, uid: str) -> str:
        b = self.blocks[uid]
        return f"page '{b['page']}'"


def days(ms_a: int, ms_b: int) -> int:
    return int(abs(ms_a - ms_b) / 86_400_000)


def datestr(ms: int) -> str:
    return _dt.datetime.fromtimestamp(ms / 1000, _dt.timezone.utc).date().isoformat()


def trim(s: str, n: int = 600) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 12] + " …[trimmed]"


# ---------------------------------------------------------------------------
# Harvesters — each yields candidate rows
# ---------------------------------------------------------------------------

DG_RE = re.compile(r"^\s*(CLM|EVD|QUE|HYP|RES)\s*[-–:]\s*(.+)$")


def is_eval_page(title: str) -> bool:
    """M/* is the evaluation namespace (brick B7): seeded probe pages that must
    never be mined as calibration/live candidates. Excluded everywhere."""
    return isinstance(title, str) and title.startswith("M/")


def content_blocks(g: Graph, lo=30, hi=500) -> List[dict]:
    return [b for b in g.blocks.values()
            if lo <= len(b["string"]) <= hi and not b["string"].startswith(">")
            and not is_eval_page(b["page"])]


def h_edge_type(g: Graph, rng, cap: int) -> List[dict]:
    rows = []
    # --- discourse-graph mode -------------------------------------------------
    dg = {t: DG_RE.match(t) for t in g.pages}
    clm = {t: m.group(2) for t, m in dg.items() if m and m.group(1) == "CLM"}
    evd = {t: m.group(2) for t, m in dg.items() if m and m.group(1) == "EVD"}
    for et, etext in evd.items():
        body = " ".join(g.blocks[u]["string"]
                        for u in g.all_under(g.pages[et])[:2])
        cited = {r for u in g.all_under(g.pages[et])
                 for r in g.blocks[u]["refs"]} | set(REF_RE.findall(et))
        for ct, ctext in clm.items():
            if ct in cited or sim(etext, ctext) > 0.35:
                sibs = [o for o in evd if o != et and ct in
                        {r for u in g.all_under(g.pages[o])
                         for r in g.blocks[u]["refs"]}][:2]
                rows.append({
                    "jtype": "edge_type", "subjects": [et, ct],
                    "fields": {
                        "evidence": trim(f"{etext}. {body}"),
                        "claim": trim(ctext),
                        "sibling_evidence": trim("; ".join(
                            DG_RE.match(s).group(2) for s in sibs) or "(none)")},
                    "meta": {"mode": "discourse"}})
    # --- generic fallback: shared-ref pairs + unrelated seeds ------------------
    cbs = content_blocks(g)
    by_ref: Dict[str, List[dict]] = defaultdict(list)
    for b in cbs:
        for r in b["refs"]:
            by_ref[r].append(b)
    seen = set()
    for r, bs in by_ref.items():
        for b1, b2 in itertools.combinations(bs[:8], 2):
            if len(b1["refs"] & b2["refs"]) < 2:
                continue
            key = tuple(sorted((b1["uid"], b2["uid"])))
            if key in seen:
                continue
            seen.add(key)
            ev, cl = (b1, b2) if len(b1["string"]) >= len(b2["string"]) else (b2, b1)
            rows.append({
                "jtype": "edge_type", "subjects": [ev["uid"], cl["uid"]],
                "fields": {"evidence": trim(g.expand_brefs(ev["string"])),
                           "claim": trim(g.expand_brefs(cl["string"])),
                           "sibling_evidence": "(none)"},
                "meta": {"mode": "shared-refs",
                         "shared": sorted(b1["refs"] & b2["refs"])[:4]}})
    rng.shuffle(cbs)
    for b1, b2 in zip(cbs[0::2], cbs[1::2]):
        if not (b1["refs"] & b2["refs"]) and len(rows) < cap * 2:
            rows.append({
                "jtype": "edge_type", "subjects": [b1["uid"], b2["uid"]],
                "fields": {"evidence": trim(b1["string"]),
                           "claim": trim(b2["string"]),
                           "sibling_evidence": "(none)"},
                "meta": {"mode": "unrelated-seed"}})
        if len([r for r in rows if r["meta"]["mode"] == "unrelated-seed"]) >= max(2, cap // 4):
            break
    rng.shuffle(rows)
    return rows[:cap]


def h_same_entity(g: Graph, rng, cap: int) -> List[dict]:
    titles = [t for t in g.pages
              if not DG_RE.match(t) and len(t) >= 3 and not is_eval_page(t)]
    rows = []

    def ctx(t: str) -> str:
        cites = [g.blocks[u]["string"] for u in list(g.inbound.get(t, []))[:2]]
        return trim(" | ".join(cites) or f"(page '{t}', no inbound refs)")

    for t1, t2 in itertools.combinations(titles, 2):
        s = sim(t1, t2)
        n1, n2 = norm(t1), norm(t2)
        acro = (acronym(t2) == n1.replace(" ", "") or
                acronym(t1) == n2.replace(" ", ""))
        contain = (len(n1) >= 4 and n1 in n2) or (len(n2) >= 4 and n2 in n1)
        if s >= 0.75 or acro or contain:
            kind = "strong"
        elif 0.55 <= s < 0.70:
            kind = "probable-negative"
        else:
            continue
        rows.append({"jtype": "same_entity", "subjects": [t1, t2],
                     "fields": {"item_1": t1, "item_1_context": ctx(t1),
                                "item_2": t2, "item_2_context": ctx(t2)},
                     "meta": {"sim": round(s, 3), "acronym": acro,
                              "containment": contain, "kind": kind}})
    rng.shuffle(rows)
    return rows[:cap]


def h_dedup_prop(g: Graph, rng, cap: int) -> List[dict]:
    cbs = content_blocks(g, 30, 400)
    if len(cbs) > 800:
        cbs = rng.sample(cbs, 800)
    rows = []
    for b1, b2 in itertools.combinations(cbs, 2):
        if abs(len(b1["string"]) - len(b2["string"])) > 200:
            continue
        s = sim(b1["string"], b2["string"])
        band = ("high" if s >= 0.92 else
                "mid" if 0.65 <= s < 0.92 else
                "low" if 0.40 <= s < 0.60 and rng.random() < 0.05 else None)
        if not band:
            continue
        u1, u2 = sorted((b1, b2), key=lambda b: b["uid"])  # canonical order:
        rows.append({  # 'subsumes' is directional — never swapped downstream
            "jtype": "dedup_prop", "subjects": [u1["uid"], u2["uid"]],
            "fields": {"item_1": trim(u1["string"]),
                       "item_1_source": g.loc(u1["uid"]),
                       "item_2": trim(u2["string"]),
                       "item_2_source": g.loc(u2["uid"])},
            "meta": {"sim": round(s, 3), "band": band}})
    rng.shuffle(rows)
    return rows[:cap]


def h_summarize_now(g: Graph, rng, cap: int, min_refs: int) -> List[dict]:
    rows = []
    for t, citing in g.inbound.items():
        n = len(citing)
        if n < 2 or is_eval_page(t):
            continue
        pages = {g.blocks[u]["page"] for u in citing}
        edits = sorted(g.blocks[u]["edit"] for u in citing)
        churn = days(edits[0], edits[-1]) if len(edits) > 1 else 0
        sample = "; ".join(trim(g.blocks[u]["string"], 110)
                           for u in list(citing)[:3])
        digest = (f"Cluster around '{t}': {n} referencing blocks across "
                  f"{len(pages)} pages; edit span {churn} days "
                  f"(last: {datestr(edits[-1])}); samples: {sample}")
        rows.append({"jtype": "summarize_now", "subjects": [t],
                     "fields": {"cluster_digest": trim(digest, 900)},
                     "meta": {"n_refs": n, "pages": len(pages),
                              "ripe_hint": n >= min_refs}})
    rng.shuffle(rows)
    return rows[:cap]


def h_propagate(g: Graph, rng, cap: int) -> List[dict]:
    cbs = sorted(content_blocks(g), key=lambda b: -b["edit"])[:40]
    rows = []
    for b in cbs:
        change = (f"Block on page '{b['page']}' (edited {datestr(b['edit'])}) "
                  f"now reads: {b['string']}")
        neigh = []
        if b["parent"]:
            for su in g.blocks[b["parent"]]["children"]:
                if su != b["uid"]:
                    neigh.append((su, f"sibling under the same parent bullet"))
                    break
        for r in list(b["refs"])[:2]:
            for ou in g.inbound.get(r, set()):
                if (ou != b["uid"] and g.blocks[ou]["page"] != b["page"]
                        and not is_eval_page(g.blocks[ou]["page"])):
                    neigh.append((ou, f"co-reference via [[{r}]]"))
                    break
        for nu, etype in neigh[:2]:
            rows.append({"jtype": "propagate", "subjects": [b["uid"], nu],
                         "fields": {"change": trim(change),
                                    "edge_type": etype,
                                    "neighbor": trim(g.blocks[nu]["string"])},
                         "meta": {}})
    rng.shuffle(rows)
    return rows[:cap]


def h_invalidate(g: Graph, rng, cap: int) -> List[dict]:
    rows = []
    for b in g.blocks.values():
        if is_eval_page(b["page"]):
            continue
        kids = [g.blocks[c] for c in b["children"]]
        if len(kids) < 2 or len(b["string"]) < 25:
            continue
        later = [k for k in kids if k["edit"] > b["edit"]]
        if later:
            dig = "\n".join(f"- child edited +{days(k['edit'], b['edit'])}d "
                            f"after parent: {trim(k['string'], 150)}"
                            for k in later[:4])
            kind = "stale-candidate"
        else:
            dig = "\n".join(f"- child (edited before parent): "
                            f"{trim(k['string'], 150)}" for k in kids[:3])
            kind = "fresh"
        rows.append({"jtype": "invalidate", "subjects": [b["uid"]],
                     "fields": {"derived": trim(b["string"]),
                                "changes_digest": trim(dig, 900)},
                     "meta": {"kind": kind, "n_later": len(later)}})
    rng.shuffle(rows)
    return rows[:cap]


def h_faithful(g: Graph, rng, cap: int) -> List[dict]:
    rows = []
    for b in g.blocks.values():
        if not b["string"].startswith(">") or is_eval_page(b["page"]):
            continue
        quote = b["string"].lstrip("> ").strip()
        pool = ([g.blocks[c] for c in g.blocks[b["parent"]]["children"]]
                if b["parent"] else [])
        if b["parent"]:
            pool.append(g.blocks[b["parent"]])
        qtok = set(norm(quote).split()) - FR_STOP
        for cand in pool:
            if cand["uid"] == b["uid"] or cand["string"].startswith(">"):
                continue
            if len(qtok & set(norm(cand["string"]).split())) >= 2:
                rows.append({
                    "jtype": "faithful", "subjects": [cand["uid"], b["uid"]],
                    "fields": {"proposition": trim(cand["string"]),
                               "source_span": trim(quote),
                               "source_surrounding": trim(
                                   f"(quoted on page '{b['page']}')")},
                    "meta": {}})
    rng.shuffle(rows)
    return rows[:cap]


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def _path_str(g: Graph, uid: str, max_hops: int = 3) -> str:
    """Human-readable ancestry: page > parent-head > ... (trimmed)."""
    b = g.blocks[uid]
    heads, cur, hops = [], b["parent"], 0
    while cur and hops < max_hops:
        heads.append(trim(g.blocks[cur]["string"], 60))
        cur, hops = g.blocks[cur]["parent"], hops + 1
    tail = " > ".join(reversed(heads))
    return f"page '{b['page']}'" + (f" > {tail}" if tail else "")


def h_continues(g: Graph, rng, cap: int) -> List[dict]:
    """Folgezettel-succession candidates. Positives-leaning: sequential
    siblings under one parent (the bullet run IS a train in most Roam graphs)
    and first-child-under-parent (branch material). Negatives-leaning:
    cross-page topical pairs (same ref, no dialogue) and random same-page
    distant pairs. Subjects are DIRECTIONAL: [child, parent]."""
    rows = []

    def cand(child, parent, mode):
        rows.append({
            "jtype": "continues",
            "subjects": [child["uid"], parent["uid"]],
            "fields": {
                "child": trim(g.expand_brefs(child["string"])),
                "child_context": _path_str(g, child["uid"]),
                "parent": trim(g.expand_brefs(parent["string"])),
                "parent_context": _path_str(g, parent["uid"])},
            "meta": {"mode": mode}})

    for b in g.blocks.values():
        if is_eval_page(b["page"]):
            continue
        kids = [g.blocks[c] for c in b["children"]
                if len(g.blocks[c]["string"]) >= 25]
        for prev, nxt in zip(kids, kids[1:]):          # sequential siblings
            cand(nxt, prev, "sibling-seq")
        if kids and len(b["string"]) >= 25:            # first child vs parent
            cand(kids[0], b, "first-child")
    for title, tops in g.pages.items():                # top-level sequence
        if is_eval_page(title):
            continue
        tb = [g.blocks[u] for u in tops if len(g.blocks[u]["string"]) >= 25]
        for prev, nxt in zip(tb, tb[1:]):
            cand(nxt, prev, "toplevel-seq")
    # topical-not-dialogical (expected new-train): cross-page shared-ref pairs
    cbs = content_blocks(g)
    by_ref: Dict[str, List[dict]] = defaultdict(list)
    for b in cbs:
        for r in b["refs"]:
            by_ref[r].append(b)
    seen = set()
    for r, bs in by_ref.items():
        for b1, b2 in itertools.combinations(bs[:6], 2):
            if b1["page"] == b2["page"]:
                continue
            key = tuple(sorted((b1["uid"], b2["uid"])))
            if key in seen:
                continue
            seen.add(key)
            cand(b2, b1, "cross-page-topical")
            if len(seen) >= max(3, cap // 4):
                break
    rng.shuffle(rows)
    return rows[:cap]


_SCAFFOLD_RE = re.compile(r"\bTODO\b|à faire|à instruire|à vérifier|\bWIP\b",
                          re.IGNORECASE)


def h_permanent_worthy(g: Graph, rng, cap: int) -> List[dict]:
    """Candidate->permanent gate material. Diversity by construction:
    declarative content blocks (promote-leaning), scaffolding/TODO blocks
    (discard-leaning), and source-bound restatements ('selon', '(source')
    which are literature, hence keep-candidate-leaning under the policy."""
    pool = [b for b in g.blocks.values() if 30 <= len(b["string"]) <= 450
            and not b["string"].startswith(">") and not is_eval_page(b["page"])]
    rows = []
    for b in pool:
        others = [o for o in pool if o["uid"] != b["uid"]]
        best, bs = None, 0.0
        for o in rng.sample(others, min(len(others), 40)):
            sc = sim(b["string"], o["string"])
            if sc > bs:
                best, bs = o, sc
        kind = ("scaffold" if _SCAFFOLD_RE.search(b["string"]) else
                "source-bound" if re.search(r"\bselon\b|\(source", b["string"],
                                            re.IGNORECASE) else "declarative")
        rows.append({
            "jtype": "permanent_worthy",
            "subjects": [b["uid"]],
            "fields": {
                "candidate": trim(g.expand_brefs(b["string"])),
                "origin_context": _path_str(g, b["uid"]),
                "nearest_permanent": (trim(best["string"]) if best and bs >= 0.35
                                      else "(none yet)")},
            "meta": {"kind": kind, "nearest_sim": round(bs, 3)}})
    rng.shuffle(rows)
    return rows[:cap]


def harvest(export_path: pathlib.Path, out_dir: pathlib.Path,
            cap: int, min_refs: int, seed: int = 0) -> Dict[str, int]:
    g = Graph.parse(json.loads(export_path.read_text()))
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    harvesters = {
        "edge_type":     lambda: h_edge_type(g, rng, cap),
        "same_entity":   lambda: h_same_entity(g, rng, cap),
        "dedup_prop":    lambda: h_dedup_prop(g, rng, cap),
        "summarize_now": lambda: h_summarize_now(g, rng, cap, min_refs),
        "propagate":     lambda: h_propagate(g, rng, cap),
        "invalidate":    lambda: h_invalidate(g, rng, cap),
        "faithful":      lambda: h_faithful(g, rng, cap),
        "continues":     lambda: h_continues(g, rng, cap),
        "permanent_worthy": lambda: h_permanent_worthy(g, rng, cap),
    }
    stats = {}
    for jt, fn in harvesters.items():
        rows = fn()
        p = out_dir / f"candidates_{jt}.jsonl"
        p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                             for r in rows))
        stats[jt] = len(rows)
    (out_dir / "harvest_stats.json").write_text(
        json.dumps({"export": str(export_path), "graph_pages": len(g.pages),
                    "graph_blocks": len(g.blocks), "counts": stats},
                   indent=2))
    return stats


# ---------------------------------------------------------------------------
# Synthetic demo export (French legal-flavoured) — used by `demo` and by tests
# ---------------------------------------------------------------------------

def make_demo_export() -> list:
    T0 = 1_748_000_000_000  # ms epoch
    d = lambda n: T0 + n * 86_400_000
    uid = itertools.count(100)
    B = lambda s, c=0, e=0, ch=None: {
        "uid": f"u{next(uid)}", "string": s,
        "create-time": d(c), "edit-time": d(e), "children": ch or []}
    return [
        {"title": "CLM - Le contrat avec le sous-traitant Hexalog est conforme à l'[[Article 28]] [[RGPD]]",
         "children": [B("Position défendue dans la note du [[DPO]] de mars.", 0, 1)]},
        {"title": "EVD - La clause d'audit est absente du [[DPA]] signé avec Hexalog",
         "children": [B("Vu au §7 du [[DPA]] : aucun droit d'audit n'est stipulé. Voir [[Article 28]] [[RGPD]].", 1, 2)]},
        {"title": "EVD - Le DPA Hexalog prévoit la notification de violation sous 48h",
         "children": [B("Clause 9.2 du [[DPA]] : notification au responsable sous 48h. [[Article 28]] [[RGPD]].", 1, 3)]},
        {"title": "QUE - Quelles garanties pour les transferts hors UE chez Hexalog ?",
         "children": [B("À instruire : [[Article 46]] [[RGPD]], clauses contractuelles types.", 2, 2)]},
        {"title": "RGPD", "children": [B("Hub réglementaire.", 0, 0)]},
        {"title": "Règlement Général sur la Protection des Données",
         "children": [B("Alias développé de [[RGPD]].", 0, 0)]},
        {"title": "Article 28", "children": [B("Sous-traitance.", 0, 0)]},
        {"title": "Art. 28 RGPD", "children": [B("Variante de titre.", 0, 0)]},
        {"title": "Dossier Hexalog — synthèse", "children": [
            B("Synthèse: le dossier Hexalog est globalement conforme [[RGPD]], "
              "sous réserve de la clause d'audit.", 3, 3, [
                B("La durée de conservation est fixée à 36 mois après fin de contrat. [[DPA]]", 3, 8),
                B("La clause d'audit manque toujours au [[DPA]]. [[Article 28]]", 3, 9),
                B("Le registre des traitements a été mis à jour. [[RGPD]]", 3, 4)]),
            B("Synthèse courte (à jour): périmètre validé par le [[DPO]].", 10, 12, [
                B("Périmètre confirmé en comité. [[DPO]]", 9, 10),
                B("Aucun nouveau traitement déclaré. [[RGPD]]", 9, 11)])]},
        {"title": "Notes de lecture — conservation", "children": [
            B("Le sous-traitant conserve les données 36 mois après la fin du contrat, "
              "selon le [[DPA]] Hexalog. [[RGPD]]", 5, 6),
            B("Conservation des données par le sous-traitant : 36 mois après fin de "
              "contrat (source [[DPA]] Hexalog). [[RGPD]]", 6, 7),
            B("La limitation de conservation impose des durées proportionnées à la "
              "finalité. [[RGPD]] [[Article 5]]", 5, 5),
            B("Réflexion libre sur l'architecture du graphe de connaissances.", 5, 5)]},
        {"title": "Article 5", "children": [
            B("Principes. Notamment 5(1)(e) limitation de la conservation.", 0, 0,
              [B("> Les données sont conservées pendant une durée n'excédant pas "
                 "celle nécessaire au regard des finalités", 0, 0),
               B("Les données ne peuvent être conservées au-delà de la durée "
                 "nécessaire aux finalités du traitement. [[RGPD]]", 0, 1)])]},
        {"title": "DPO", "children": [B("Délégué à la protection des données.", 0, 0)]},
        {"title": "DPA", "children": [B("Data Processing Agreement — accord de "
                                        "sous-traitance [[Article 28]] [[RGPD]].", 0, 0)]},
    ]


def self_test() -> None:
    """Zero-network. Asserts the M/* evaluation namespace (brick B7) is fully
    excluded from candidate mining: an M/Eval/Seeded page — even one heavily
    cross-referenced so it would otherwise surface across several harvesters —
    must produce ZERO candidates in any type."""
    import tempfile
    ok = lambda c, m: (print(f"  ✓ {m}") if c else
                       (_ for _ in ()).throw(AssertionError(m)))
    export = make_demo_export()
    # A seeded probe page that references live hub pages and carries children
    # (so it would tempt edge_type/continues/invalidate/permanent_worthy).
    export.append({"title": "M/Eval/Seeded", "children": [
        {"uid": "eval-seed-1", "create-time": 1_783_000_000_000,
         "edit-time": 1_783_000_000_000,
         "string": "Seeded eval probe referencing [[RGPD]] [[Article 28]] "
                   "[[DPA]] that must never surface as a mined candidate.",
         "children": [
            {"uid": "eval-seed-2", "create-time": 1_783_000_000_000,
             "edit-time": 1_783_000_000_000,
             "string": "Child probe under the seeded eval page, also excluded "
                       "from every harvester by the M/* namespace guard."}]}]})
    with tempfile.TemporaryDirectory() as td:
        out = pathlib.Path(td)
        exp = out / "export.json"
        exp.write_text(json.dumps(export, ensure_ascii=False))
        harvest(exp, out, cap=200, min_refs=2)
        seeds = {"eval-seed-1", "eval-seed-2", "M/Eval/Seeded"}
        offenders = []
        for p in out.glob("candidates_*.jsonl"):
            for line in p.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                if seeds & set(r.get("subjects", [])):
                    offenders.append((p.name, r["jtype"], r["subjects"]))
        ok(not offenders,
           f"M/Eval/Seeded page produces zero candidates "
           f"({len(offenders)} offenders)")
        g = Graph.parse(json.loads(exp.read_text()))
        ok("eval-seed-1" in g.blocks, "seeded block IS in the parsed graph")
        ok(not content_blocks(g) or all(
            not is_eval_page(b["page"]) for b in content_blocks(g)),
           "content_blocks() excludes M/* pages")
    print("all roam_harvest self-tests passed (3 assertions)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("harvest")
    h.add_argument("--export", required=True)
    h.add_argument("--out-dir", default="calib")
    h.add_argument("--max-per-type", type=int, default=400)
    h.add_argument("--min-refs", type=int, default=8,
                   help="inbound-ref count hinting a summarize-ripe cluster")
    h.add_argument("--seed", type=int, default=0)
    dm = sub.add_parser("demo")
    dm.add_argument("--out-dir", default="demo_calib")
    sub.add_parser("self-test")
    args = ap.parse_args()

    if args.cmd == "self-test":
        self_test(); return

    if args.cmd == "demo":
        out = pathlib.Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        exp = out / "demo_export.json"
        exp.write_text(json.dumps(make_demo_export(), ensure_ascii=False, indent=1))
        stats = harvest(exp, out, cap=60, min_refs=3)
        print(json.dumps(stats, indent=2))
        for jt, n in stats.items():
            assert isinstance(n, int)
        empty = [jt for jt, n in stats.items() if n == 0]
        print("note: empty types:", empty or "none")
    else:
        stats = harvest(pathlib.Path(args.export), pathlib.Path(args.out_dir),
                        cap=args.max_per_type, min_refs=args.min_refs,
                        seed=args.seed)
        print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()

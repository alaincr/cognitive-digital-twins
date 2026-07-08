#!/usr/bin/env python3
"""prefilter.py — the formal pre-filter layer for the Mnemosyne judge swarm.

The last unbuilt box in the live loop (roadmap step 8): turns graph change into
a BUDGETED, DEBOUNCED stream of judge candidates. Judges never scan the corpus;
they see only what this layer nominates.

    graph snapshot ──► dirty marks (edit/create since last run)
                       novel co-references (surprisal proxy)
                       threshold crossings (summarize ripeness)
                              │  score = recency × structure (+ dreamer boost)
                              ▼
                       per-type budgets  ──►  debounce (cooldown per
                              │                (jtype, subjects) key)
                              ▼
                       candidates.jsonl  (judge_harness-ready)  +  state.json

Design points (mirrors microjudge_contract.md §2 'the formal layer decides
WHEN, the judges decide WHAT'):
  - CHEAP: pure structure + string similarity; no model calls, no embeddings.
    An optional --surprisal-file (uid -> score JSONL, e.g. from the Roam
    'dreamer') boosts priorities — integration hook, not a reimplementation.
  - IDEMPOTENT / RESTART-SAFE: state.json (atomic write) holds last-run
    watermark, emitted-candidate cooldowns, per-page ref counts (for
    threshold-crossing detection), and a bounded set of seen ref-pair hashes
    (novelty detection).
  - DEBOUNCED: a (jtype, subjects) key is not re-emitted within --cooldown-days
    unless its content changed (fields hash differs) — re-judging the same
    context is pointless (identical context => identical verdict, by the
    determinism of the harness).
  - BUDGETED: per-type caps; highest-priority first; unspent budget is not
    banked (steady trickle beats bursts for panel scheduling).

Today's graph source is a Roam export snapshot (reusing roam_harvest.Graph).
In the full deployment the same nomination logic runs against the Mnemosyne
event log, where dirty = new events — the seams are marked GRAPH-SOURCE below.

Subcommands:
  run        --export graph.json [--state ...] [--out ...] [--budget t=N ...]
  self-test  three-run scenario in a tempdir (emit -> debounce -> targeted)
"""

from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import os
import pathlib
import re
import sys
import tempfile
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import roam_harvest as RH

DAY_MS = 86_400_000

DEFAULT_BUDGETS = {
    "edge_type": 20, "propagate": 15, "invalidate": 10, "dedup_prop": 10,
    "same_entity": 8, "summarize_now": 6, "continues": 15,
    # permanent_worthy is a project-harvest flow (branch merge), not a live
    # trigger — deliberately absent here.
}

REF_PAIRS_CAP = 50_000  # bounded novelty memory


# ===========================================================================
# State
# ===========================================================================

def load_state(path: pathlib.Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {"last_run_ms": 0, "emitted": {}, "page_refs": {}, "ref_pairs": []}


def save_state(path: pathlib.Path, state: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state))
    os.replace(tmp, path)  # atomic on POSIX


def fields_hash(fields: Dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(fields, sort_keys=True,
                                     ensure_ascii=False).encode()).hexdigest()[:16]


def cand_key(jtype: str, subjects: List[str]) -> str:
    return jtype + "|" + "|".join(subjects)


def pair_hash(a: str, b: str) -> str:
    return hashlib.sha1("+".join(sorted((a, b))).encode()).hexdigest()[:12]


# ===========================================================================
# Change detection (GRAPH-SOURCE: from event log, these become event queries)
# ===========================================================================

def _is_eval_page(page: str) -> bool:
    """M/* pages are the evaluation namespace (B7): seeded probes that must
    never be mined as live candidates. Excluded from all dirty selection."""
    return isinstance(page, str) and page.startswith("M/")


def dirty_blocks(g: RH.Graph, since_ms: int) -> List[dict]:
    return [b for b in g.blocks.values()
            if max(b["edit"], b["create"]) >= since_ms
            and len(b["string"]) >= 25
            and not _is_eval_page(b["page"])
            and not RH.is_org_block(g, b["uid"])]


def dirty_blocks_from_delta(g: RH.Graph, delta_path: pathlib.Path) -> List[dict]:
    """Twin of dirty_blocks driven by a B1 delta file (roam_sync). Resolves
    each delta uid (op in {added, edited, moved}) in g.blocks and applies the
    same >=25-char + M/* exclusion filter. `removed` ops are ignored (the block
    is gone from the snapshot; the consolidator handles removals via events).

    If the delta is a first-run initial import (header {"meta":"initial-import"}
    on line 1) the caller must fall back to watermark mode — signalled by
    returning None."""
    lines = [l for l in delta_path.read_text(encoding="utf-8").splitlines()
             if l.strip()]
    if lines:
        first = json.loads(lines[0])
        if first.get("meta") == "initial-import":
            return None  # signal: fall back to watermark mode
    picked, seen = [], set()
    for l in lines:
        r = json.loads(l)
        if r.get("op") not in ("added", "edited", "moved"):
            continue
        uid = r.get("uid")
        b = g.blocks.get(uid)
        if b is None or uid in seen:
            continue
        if (len(b["string"]) >= 25 and not _is_eval_page(b["page"])
                and not RH.is_org_block(g, b["uid"])):
            seen.add(uid)
            picked.append(b)
    return picked


def new_blocks(g: RH.Graph, since_ms: int) -> List[dict]:
    return [b for b in g.blocks.values()
            if b["create"] >= since_ms and len(b["string"]) >= 25
            and not _is_eval_page(b["page"])
            and not RH.is_org_block(g, b["uid"])]


def novel_ref_pairs(g: RH.Graph, dirty: List[dict],
                    seen: set) -> Tuple[Dict[str, List[str]], set]:
    """Blocks whose ref-set contains a co-reference pair never seen before —
    the cheap structural-surprisal proxy (two pages meeting for the first
    time). Returns {block_uid: [novel 'A+B' labels]} and the updated set."""
    out: Dict[str, List[str]] = {}
    for b in dirty:
        refs = sorted(b["refs"])[:6]
        for r1, r2 in itertools.combinations(refs, 2):
            h = pair_hash(r1, r2)
            if h not in seen:
                seen.add(h)
                out.setdefault(b["uid"], []).append(f"{r1}+{r2}")
    return out, seen


def summarize_crossings(g: RH.Graph, prev_counts: Dict[str, int],
                        min_refs: int) -> Tuple[List[str], Dict[str, int]]:
    """Pages whose inbound-ref count crossed the ripeness threshold since the
    previous run. Fires exactly at the crossing (debounce handles re-asks)."""
    now = {t: len(u) for t, u in g.inbound.items()}
    crossed = [t for t, n in now.items()
               if n >= min_refs > prev_counts.get(t, 0)]
    return crossed, now


# ===========================================================================
# Dirty-seeded candidate builders (field shapes identical to roam_harvest —
# small deliberate duplication; the harvesters scan globally, these seed
# from changed nodes only)
# ===========================================================================

def _edge_cands(g, dirty) -> List[dict]:
    by_ref = defaultdict(list)
    for b in RH.content_blocks(g):
        for r in b["refs"]:
            by_ref[r].append(b)
    out, seen = [], set()
    for b in dirty:
        for r in b["refs"]:
            for o in by_ref.get(r, [])[:8]:
                if o["uid"] == b["uid"] or len(b["refs"] & o["refs"]) < 2:
                    continue
                key = tuple(sorted((b["uid"], o["uid"])))
                if key in seen:
                    continue
                seen.add(key)
                ev, cl = (b, o) if len(b["string"]) >= len(o["string"]) else (o, b)
                out.append({"jtype": "edge_type",
                            "subjects": [ev["uid"], cl["uid"]],
                            "fields": {"evidence": RH.trim(g.expand_brefs(ev["string"])),
                                       "claim": RH.trim(g.expand_brefs(cl["string"])),
                                       "sibling_evidence": "(none)"},
                            "meta": {"seed": b["uid"]}})
    return out


def _propagate_cands(g, dirty) -> List[dict]:
    out = []
    for b in dirty:
        change = (f"Block on page '{b['page']}' (edited "
                  f"{RH.datestr(b['edit'])}) now reads: {b['string']}")
        neigh = []
        if b["parent"]:
            for su in g.blocks[b["parent"]]["children"]:
                if su != b["uid"]:
                    neigh.append((su, "sibling under the same parent bullet"))
                    break
        for r in list(b["refs"])[:2]:
            for ou in g.inbound.get(r, set()):
                if (ou != b["uid"] and g.blocks[ou]["page"] != b["page"]
                        and not _is_eval_page(g.blocks[ou]["page"])):
                    neigh.append((ou, f"co-reference via [[{r}]]"))
                    break
        for nu, etype in neigh[:2]:
            out.append({"jtype": "propagate", "subjects": [b["uid"], nu],
                        "fields": {"change": RH.trim(change),
                                   "edge_type": etype,
                                   "neighbor": RH.trim(g.blocks[nu]["string"])},
                        "meta": {"seed": b["uid"]}})
    return out


def _invalidate_cands(g, dirty) -> List[dict]:
    out, dirty_uids = [], {b["uid"] for b in dirty}
    parents = {b["parent"] for b in dirty if b["parent"]}
    for pu in parents:
        p = g.blocks[pu]
        if len(p["string"]) < 25:
            continue
        later = [g.blocks[c] for c in p["children"]
                 if c in dirty_uids or g.blocks[c]["edit"] > p["edit"]]
        if not later:
            continue
        dig = "\n".join(f"- child edited +{RH.days(k['edit'], p['edit'])}d "
                        f"after parent: {RH.trim(k['string'], 150)}"
                        for k in later[:4])
        out.append({"jtype": "invalidate", "subjects": [pu],
                    "fields": {"derived": RH.trim(p["string"]),
                               "changes_digest": RH.trim(dig, 900)},
                    "meta": {"n_later": len(later)}})
    return out


def _dedup_cands(g, dirty) -> List[dict]:
    pool = RH.content_blocks(g, 30, 400)
    out = []
    for b in dirty:
        if not (30 <= len(b["string"]) <= 400):
            continue
        for o in pool:
            if o["uid"] == b["uid"] or abs(len(b["string"]) - len(o["string"])) > 200:
                continue
            s = RH.sim(b["string"], o["string"])
            if s < 0.65:
                continue
            u1, u2 = sorted((b, o), key=lambda x: x["uid"])  # canonical order
            out.append({"jtype": "dedup_prop",
                        "subjects": [u1["uid"], u2["uid"]],
                        "fields": {"item_1": RH.trim(u1["string"]),
                                   "item_1_source": g.loc(u1["uid"]),
                                   "item_2": RH.trim(u2["string"]),
                                   "item_2_source": g.loc(u2["uid"])},
                        "meta": {"sim": round(s, 3)}})
    return out


def _same_entity_cands(g, since_ms) -> List[dict]:
    fresh = [t for t, tops in g.pages.items()
             if not _is_eval_page(t)
             and any(g.blocks[u]["create"] >= since_ms
                     for u in g.all_under(tops))]
    out = []

    def ctx(t):
        cites = [g.blocks[u]["string"] for u in list(g.inbound.get(t, []))[:2]]
        return RH.trim(" | ".join(cites) or f"(page '{t}', no inbound refs)")

    for t1 in fresh:
        for t2 in g.pages:
            if t1 == t2:
                continue
            s = RH.sim(t1, t2)
            n1, n2 = RH.norm(t1), RH.norm(t2)
            acro = (RH.acronym(t2) == n1.replace(" ", "") or
                    RH.acronym(t1) == n2.replace(" ", ""))
            contain = (len(n1) >= 4 and n1 in n2) or (len(n2) >= 4 and n2 in n1)
            if s >= 0.75 or acro or contain:
                a, b = sorted((t1, t2))
                out.append({"jtype": "same_entity", "subjects": [a, b],
                            "fields": {"item_1": a, "item_1_context": ctx(a),
                                       "item_2": b, "item_2_context": ctx(b)},
                            "meta": {"sim": round(s, 3), "acronym": acro}})
    return out


def _continues_cands(g, since_ms) -> List[dict]:
    """New blocks propose their predecessor: previous sibling first, else the
    parent bullet. (kNN parent proposals arrive with the embedding layer.)"""
    out = []
    for b in new_blocks(g, since_ms):
        parent_cand = None
        if b["parent"]:
            sibs = g.blocks[b["parent"]]["children"]
            if b["uid"] in sibs:
                i = sibs.index(b["uid"])
                if i > 0 and len(g.blocks[sibs[i - 1]]["string"]) >= 25:
                    parent_cand = (sibs[i - 1], "sibling-seq")
            if parent_cand is None and len(g.blocks[b["parent"]]["string"]) >= 25:
                parent_cand = (b["parent"], "first-child")
        if parent_cand is None:
            continue
        pu, mode = parent_cand
        out.append({"jtype": "continues", "subjects": [b["uid"], pu],
                    "fields": {"child": RH.trim(g.expand_brefs(b["string"])),
                               "child_context": RH._path_str(g, b["uid"]),
                               "parent": RH.trim(g.expand_brefs(g.blocks[pu]["string"])),
                               "parent_context": RH._path_str(g, pu)},
                    "meta": {"mode": mode}})
    return out


def _summarize_cands(g, crossed) -> List[dict]:
    out = []
    for t in crossed:
        citing = g.inbound[t]
        pages = {g.blocks[u]["page"] for u in citing}
        edits = sorted(g.blocks[u]["edit"] for u in citing)
        churn = RH.days(edits[0], edits[-1]) if len(edits) > 1 else 0
        sample = "; ".join(RH.trim(g.blocks[u]["string"], 110)
                           for u in list(citing)[:3])
        out.append({"jtype": "summarize_now", "subjects": [t],
                    "fields": {"cluster_digest": RH.trim(
                        f"Cluster around '{t}': {len(citing)} referencing "
                        f"blocks across {len(pages)} pages; edit span {churn} "
                        f"days (last: {RH.datestr(edits[-1])}); samples: "
                        f"{sample}", 900)},
                    "meta": {"crossed": True}})
    return out


# ===========================================================================
# Scoring, budgeting, debouncing
# ===========================================================================

def priority(c: dict, g: RH.Graph, now_ms: int,
             novel: Dict[str, List[str]], boost: Dict[str, float]) -> float:
    """recency (of the freshest subject) x structure (inbound refs) with
    novelty and external-surprisal boosts. Cheap on purpose."""
    rec = struct = 0.0
    for sid in c["subjects"]:
        b = g.blocks.get(sid)
        if b:
            age_d = max((now_ms - max(b["edit"], b["create"])) / DAY_MS, 0.0)
            rec = max(rec, 1.0 / (1.0 + age_d))
            struct = max(struct, min(sum(len(g.inbound.get(r, ()))
                                         for r in b["refs"]) / 10.0, 1.0))
    s = rec + 0.5 * struct
    if any(sid in novel for sid in c["subjects"]):
        s += 1.0
        c["meta"]["novel_copair"] = sorted(
            {p for sid in c["subjects"] for p in novel.get(sid, [])})[:3]
    s += max((boost.get(sid, 0.0) for sid in c["subjects"]), default=0.0)
    return s


def debounce_and_budget(cands: List[dict], scores: List[float], state: dict,
                        budgets: Dict[str, int], now_ms: int,
                        cooldown_ms: int) -> List[dict]:
    emitted = state["emitted"]
    picked: List[dict] = []
    used: Dict[str, int] = defaultdict(int)
    for c, _s in sorted(zip(cands, scores), key=lambda t: -t[1]):
        jt = c["jtype"]
        if used[jt] >= budgets.get(jt, 0):
            continue
        key = cand_key(jt, c["subjects"])
        fh = fields_hash(c["fields"])
        prev = emitted.get(key)
        if prev and prev["fh"] == fh and now_ms - prev["ts"] < cooldown_ms:
            continue  # same content, inside cooldown -> skip
        emitted[key] = {"ts": now_ms, "fh": fh}
        used[jt] += 1
        picked.append(c)
    # prune ancient cooldown entries (keep state bounded)
    horizon = now_ms - 4 * cooldown_ms
    state["emitted"] = {k: v for k, v in emitted.items() if v["ts"] >= horizon}
    return picked


# ===========================================================================
# One run
# ===========================================================================

def run_once(export: pathlib.Path, state_path: pathlib.Path,
             out_path: pathlib.Path, budgets: Dict[str, int],
             min_refs: int, cooldown_days: float,
             surprisal_file: Optional[pathlib.Path],
             now_ms: Optional[int] = None,
             delta_file: Optional[pathlib.Path] = None) -> Dict[str, int]:
    g = RH.Graph.parse(json.loads(export.read_text()))
    state = load_state(state_path)
    since = state["last_run_ms"]
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)

    boost: Dict[str, float] = {}
    if surprisal_file and surprisal_file.exists():
        for line in surprisal_file.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                boost[r["uid"]] = float(r.get("score", 0.0))

    # --delta wins when provided; watermark stays as the fallback (and is used
    # anyway when the delta is a first-run initial-import, which returns None).
    dirty = None
    delta_mode = False
    if delta_file is not None and delta_file.exists():
        dirty = dirty_blocks_from_delta(g, delta_file)
        delta_mode = dirty is not None
    if dirty is None:
        dirty = dirty_blocks(g, since)
    seen = set(state.get("ref_pairs", []))
    novel, seen = novel_ref_pairs(g, dirty, seen)
    crossed, page_refs = summarize_crossings(g, state.get("page_refs", {}),
                                             min_refs)

    cands = (_edge_cands(g, dirty) + _propagate_cands(g, dirty)
             + _invalidate_cands(g, dirty) + _dedup_cands(g, dirty)
             + _same_entity_cands(g, since) + _continues_cands(g, since)
             + _summarize_cands(g, crossed))
    scores = [priority(c, g, now_ms, novel, boost) for c in cands]
    picked = debounce_and_budget(cands, scores, state, budgets, now_ms,
                                 int(cooldown_days * DAY_MS))

    with out_path.open("a", encoding="utf-8") as f:
        for c in picked:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    state["last_run_ms"] = now_ms
    state["page_refs"] = page_refs
    state["ref_pairs"] = list(seen)[-REF_PAIRS_CAP:]
    save_state(state_path, state)

    counts: Dict[str, int] = defaultdict(int)
    for c in picked:
        counts[c["jtype"]] += 1
    counts["_total"] = len(picked)
    counts["_generated"] = len(cands)
    counts["_dirty_blocks"] = len(dirty)
    counts["_novel_copairs"] = sum(len(v) for v in novel.values())
    counts["_delta_mode"] = int(delta_mode)
    return dict(counts)


# ===========================================================================
# Self-test: emit -> debounce -> targeted re-emit
# ===========================================================================

def self_test() -> None:
    ok = lambda c, m: (print(f"  ✓ {m}") if c else
                       (_ for _ in ()).throw(AssertionError(m)))
    with tempfile.TemporaryDirectory() as td:
        d = pathlib.Path(td)
        export = d / "graph.json"
        export.write_text(json.dumps(RH.make_demo_export(),
                                     ensure_ascii=False))
        st, out = d / "state.json", d / "cands.jsonl"
        T0 = 1_748_000_000_000
        args = dict(state_path=st, out_path=out, budgets=DEFAULT_BUDGETS,
                    min_refs=3, cooldown_days=7, surprisal_file=None)

        # RUN 1: cold start — everything is dirty; emissions across types,
        # bounded by budgets
        c1 = run_once(export, **args, now_ms=T0 + 30 * DAY_MS)
        ok(c1["_total"] > 0, f"run1 emits ({c1['_total']} candidates)")
        ok(all(c1.get(t, 0) <= n for t, n in DEFAULT_BUDGETS.items()),
           "budgets respected per type")
        ok(c1.get("summarize_now", 0) >= 1, "threshold crossing fired (cold)")
        n1 = c1["_total"]

        # RUN 2: nothing changed — dirty set empty, crossings absent,
        # cooldowns hold: zero emissions
        c2 = run_once(export, **args, now_ms=T0 + 31 * DAY_MS)
        ok(c2["_dirty_blocks"] == 0, "run2 sees no dirty blocks")
        ok(c2["_total"] == 0, "run2 emits nothing (debounce + watermark)")

        # RUN 3: touch one block — edit it, add a never-seen co-ref pair
        data = json.loads(export.read_text())
        tgt = data[8]["children"][0]["children"][0]  # a Hexalog child bullet
        tgt["string"] += " Voir aussi [[Article 32]] [[CNIL]]."
        tgt["edit-time"] = T0 + 32 * DAY_MS
        export.write_text(json.dumps(data, ensure_ascii=False))
        c3 = run_once(export, **args, now_ms=T0 + 32 * DAY_MS + 1)
        ok(0 < c3["_total"] < n1, f"run3 targeted ({c3['_total']} << {n1})")
        ok(c3["_dirty_blocks"] == 1, "exactly one dirty block")
        ok(c3["_novel_copairs"] >= 1, "novel co-reference detected")
        uid = tgt["uid"]
        rows = [json.loads(l) for l in out.read_text().splitlines()]
        r3 = rows[n1:]
        ok(any(uid in r["subjects"] for r in r3),
           "edited block appears among run3 subjects")
        ok(any(r["meta"].get("novel_copair") for r in r3),
           "novelty boost recorded in meta")

        # RUN 4: immediately again — the touched content is now inside
        # cooldown with an unchanged fields-hash: silence returns
        c4 = run_once(export, **args, now_ms=T0 + 32 * DAY_MS + DAY_MS)
        ok(c4["_total"] == 0, "run4 silent again (content-hash debounce)")

        # state hygiene
        s = load_state(st)
        ok(s["last_run_ms"] > T0 and len(s["ref_pairs"]) > 0
           and len(s["emitted"]) > 0, "state persisted (watermark/pairs/cooldowns)")

        # ==== B1 integration: --delta mode, initial-import fallback, M/* excl ==
        # Fresh export with an M/Eval/Seeded page whose block is heavily
        # cross-referenced (would surface as candidates if not excluded).
        b1_export = d / "b1_graph.json"
        seeded = ("Seeded eval probe that references [[RGPD]] [[Article 28]] "
                  "[[DPA]] and must never surface as a live candidate.")
        base = json.loads(export.read_text())
        base.append({"title": "M/Eval/Seeded", "edit-time": T0 + 50 * DAY_MS,
                     "children": [{"uid": "eval-seed-1", "string": seeded,
                                   "create-time": T0 + 50 * DAY_MS,
                                   "edit-time": T0 + 50 * DAY_MS,
                                   "children": []}]})
        b1_export.write_text(json.dumps(base, ensure_ascii=False))

        # A real (non-M/*) dirty uid to drive delta mode: reuse an existing block
        g_probe = RH.Graph.parse(json.loads(b1_export.read_text()))
        eval_present = "eval-seed-1" in g_probe.blocks
        ok(eval_present, "M/* seeded block is present in the graph")
        real_uid = next(u for u, b in g_probe.blocks.items()
                        if not b["page"].startswith("M/") and len(b["string"]) >= 25)

        # (a) delta names the M/* block + a real block; M/* must be dropped,
        #     the real one kept.
        dfile = d / "cycle.delta.jsonl"
        dfile.write_text(
            json.dumps({"op": "edited", "uid": "eval-seed-1", "page": "M/Eval/Seeded",
                        "parent": "", "string": seeded, "edit_time": 1,
                        "snapshot": "T"}) + "\n" +
            json.dumps({"op": "added", "uid": real_uid, "page": "x",
                        "parent": "", "string": "x", "edit_time": 1,
                        "snapshot": "T"}) + "\n" +
            json.dumps({"op": "removed", "uid": "gone-uid", "page": "x",
                        "parent": "", "snapshot": "T"}) + "\n")
        g_del = RH.Graph.parse(json.loads(b1_export.read_text()))
        picked = dirty_blocks_from_delta(g_del, dfile)
        ok(picked is not None, "delta (no initial header) resolves to a list")
        ok(all(not b["page"].startswith("M/") for b in picked),
           "delta mode excludes M/* pages")
        ok(any(b["uid"] == real_uid for b in picked),
           "delta mode keeps the resolved real dirty block")
        ok(all(b["uid"] != "gone-uid" for b in picked),
           "delta mode ignores removed ops")

        # (b) run_once with --delta reports _delta_mode == 1 and stays budgeted
        stx, outx = d / "state_delta.json", d / "cands_delta.jsonl"
        cD = run_once(b1_export, state_path=stx, out_path=outx,
                      budgets=DEFAULT_BUDGETS, min_refs=3, cooldown_days=7,
                      surprisal_file=None, now_ms=T0 + 51 * DAY_MS,
                      delta_file=dfile)
        ok(cD["_delta_mode"] == 1, "run_once flags delta mode active")
        rowsD = [json.loads(l) for l in outx.read_text().splitlines()] \
            if outx.exists() else []
        ok(all("eval-seed-1" not in r["subjects"] for r in rowsD),
           "no M/* seeded block emitted as a candidate (delta mode)")

        # (c) initial-import header → fall back to watermark mode
        init_delta = d / "init.delta.jsonl"
        init_delta.write_text(
            json.dumps({"meta": "initial-import", "snapshot": "T", "blocks": 3})
            + "\n" +
            json.dumps({"op": "added", "uid": real_uid, "page": "x",
                        "parent": "", "string": "x", "initial": True,
                        "edit_time": 1, "snapshot": "T"}) + "\n")
        ok(dirty_blocks_from_delta(g_del, init_delta) is None,
           "initial-import header returns None (watermark fallback)")
        sti, outi = d / "state_init.json", d / "cands_init.jsonl"
        cI = run_once(b1_export, state_path=sti, out_path=outi,
                      budgets=DEFAULT_BUDGETS, min_refs=3, cooldown_days=7,
                      surprisal_file=None, now_ms=T0 + 60 * DAY_MS,
                      delta_file=init_delta)
        ok(cI["_delta_mode"] == 0,
           "initial-import falls back to watermark mode (not delta)")
        rowsI = [json.loads(l) for l in outi.read_text().splitlines()] \
            if outi.exists() else []
        ok(all("eval-seed-1" not in r["subjects"] for r in rowsI),
           "M/* seeded block excluded in watermark mode too")

    print("all prefilter self-tests passed")


# ===========================================================================
# CLI
# ===========================================================================

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--export", required=True)
    r.add_argument("--state", default="ops/prefilter_state.json")
    r.add_argument("--out", default="ops/live_candidates.jsonl")
    r.add_argument("--min-refs", type=int, default=8)
    r.add_argument("--cooldown-days", type=float, default=7.0)
    r.add_argument("--surprisal-file", default=None,
                   help="optional dreamer export: JSONL of {uid, score}")
    r.add_argument("--delta", default=None,
                   help="B1 delta file (sync/deltas/<ts>.delta.jsonl): dirty "
                        "marks come from it instead of the edit-time watermark; "
                        "an initial-import header falls back to watermark mode")
    r.add_argument("--budget", action="append", default=[],
                   metavar="TYPE=N", help="override a per-type budget")
    sub.add_parser("self-test")
    args = ap.parse_args()

    if args.cmd == "self-test":
        self_test(); return

    budgets = dict(DEFAULT_BUDGETS)
    for spec in args.budget:
        t, n = spec.split("=")
        budgets[t] = int(n)
    counts = run_once(pathlib.Path(args.export), pathlib.Path(args.state),
                      pathlib.Path(args.out), budgets, args.min_refs,
                      args.cooldown_days,
                      pathlib.Path(args.surprisal_file)
                      if args.surprisal_file else None,
                      delta_file=pathlib.Path(args.delta) if args.delta else None)
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()

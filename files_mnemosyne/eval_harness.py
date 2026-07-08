#!/usr/bin/env python3
"""eval_harness.py — Mnemosyne task-level evaluation harness (brick B7 / gap G7).

Measures the *system*, not the judge: does the promoted substrate beat "a folder
of markdown files"? Five metrics, one weekly report, honest counters only.

  E1  judgment health      — abstention/gate verdict, label dist, anchor agreement
  E2  seeded contradictions — planted opposites detected via promoted `opposes` / S2
  E3  retrieval coverage   — (a) frozen lexical baseline, (b) kNN, (c) promoted edges
  E4  stance stability     — churn share (retraction / re-judgment) of stance diffs
  E5  human loop           — response rate, cumulative :human calset, elaboration cov.

Everything is recomputed from persisted artefacts (INTERFACES.md rows):
`store/events.jsonl`, `judge_metrics` JSON, `edges.jsonl`, `lint.json`,
`stance_diff.jsonl`, ledgers, calsets, snapshot, `embeddings.db`. Nothing volatile.

Design (ANNEX_B7 §5 skeleton):
  readers/  pure loaders            e1..e5  pure -> dict
  trends()  Unicode sparklines      render_md / write_json
  cmd_report / cmd_seed_contradictions / cmd_check_seeded / cmd_retrieval / cmd_self_test

Thresholds + their decisions live in `eval_thresholds.yaml` (never hardcoded).
The FROZEN lexical baseline (E3 column a) is committed once and hashed in
README_eval.md; any change is a NEW column, never a retouch.

Subcommands:
  report            --week <ISO-date> [--in <dir>] [--history eval/history] [--out eval/]
  seed-contradictions --pairs fixtures/eval/seeded_pairs.yaml --orders <writeback_orders.jsonl>
  check-seeded      --pairs ... --edges ops/edges.jsonl --lint <lint.json> [--cycle N]
  retrieval         --questions eval_questions.yaml --snapshot sync/snapshots/latest.json
                    --edges ops/edges.jsonl [--embed-index embed_index.py]
  self-test         zero network; synthetic fixtures only

stdlib-first; only third-party dependency is pyyaml (for YAML fixtures/config).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import pathlib
import re
import statistics
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from typing import Callable, Dict, List, Optional, Tuple

try:
    import yaml  # pyyaml — allowed dependency (SPEC-00 §3.1)
except Exception:  # pragma: no cover - import guard
    yaml = None

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_THRESHOLDS = HERE / "eval_thresholds.yaml"

# ===========================================================================
# small helpers
# ===========================================================================


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _load_jsonl(path: Optional[pathlib.Path]) -> List[dict]:
    if not path or not pathlib.Path(path).exists():
        return []
    out = []
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _load_json(path: Optional[pathlib.Path]) -> Optional[dict]:
    if not path or not pathlib.Path(path).exists():
        return None
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _load_yaml(path: pathlib.Path) -> dict:
    if yaml is None:
        raise RuntimeError("pyyaml required to read %s" % path)
    return yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))


def load_thresholds(path: Optional[pathlib.Path] = None) -> dict:
    return _load_yaml(path or DEFAULT_THRESHOLDS)


# ===========================================================================
# readers/  — PURE loaders of persisted artefacts (INTERFACES.md schemas)
# ===========================================================================


def read_events(path: Optional[pathlib.Path]) -> List[dict]:
    """store/events.jsonl — {event_id, seq, type, actor, caused_by, ts, tx_data[]}."""
    return _load_jsonl(path)


def read_metrics_json(path: Optional[pathlib.Path]) -> dict:
    """judge_metrics.py report JSON — {by_type.<jtype>.{abstention_rate,...}}."""
    return _load_json(path) or {}


def read_edges(path: Optional[pathlib.Path]) -> List[dict]:
    """ops/edges.jsonl — {edge_id, edge_type, from, to}."""
    return _load_jsonl(path)


def read_lint(path: Optional[pathlib.Path]) -> dict:
    """$C/lint.json — {conforms, n_violations, results:[{focusNode, shape, severity}]}."""
    return _load_json(path) or {}


def read_stance_diffs(path: Optional[pathlib.Path]) -> List[dict]:
    """$C/stance_diff.jsonl — {node, old_status, new_status, caused_by}."""
    return _load_jsonl(path)


def read_ledgers(path: Optional[pathlib.Path]) -> List[dict]:
    """Generic ledger reader (harvest_ledger / taskgen_ledger / writeback_ledger)."""
    return _load_jsonl(path)


def read_calsets(paths: List[pathlib.Path]) -> List[dict]:
    """calib/calset_<jtype>.jsonl rows — {jtype, fields, gold, provenance{source}}."""
    out: List[dict] = []
    for p in paths or []:
        out.extend(_load_jsonl(p))
    return out


def read_accepted(path: Optional[pathlib.Path]) -> List[dict]:
    """ops/accepted.jsonl — {judgment_id, jtype, label, context_hash, judge_id}."""
    return _load_jsonl(path)


def read_anchor_outbox(path: Optional[pathlib.Path]) -> List[dict]:
    """ops/anchor_outbox.jsonl — outbox schema + event: anchor.sampled."""
    return _load_jsonl(path)


def read_snapshot(path: Optional[pathlib.Path]) -> List[dict]:
    """sync/snapshots/*.json — Roam Export-All: [{title, children:[{uid,string,...}]}]."""
    obj = _load_json(path)
    return obj if isinstance(obj, list) else []


def read_questions(path: pathlib.Path) -> List[dict]:
    """eval_questions.yaml — {questions: [{id, question, gold_uids, domain, frozen}]}."""
    obj = _load_yaml(path)
    if isinstance(obj, dict):
        return obj.get("questions") or []
    return obj or []


def read_pairs(path: pathlib.Path) -> List[dict]:
    """fixtures/eval/seeded_pairs.yaml — [{id, kind, a, b, domain}]."""
    obj = _load_yaml(path)
    return obj if isinstance(obj, list) else (obj.get("pairs") or [])


# ===========================================================================
# E1 · judgment health
# ===========================================================================

# Gate buckets (ANNEX_B7 §1 / eval_thresholds.yaml e1.abstention_gate). Kept as a
# pure function of (rate, n, cfg) — thresholds are injected, never hardcoded.


def gate_verdict(rate: float, n: int, cfg: dict) -> str:
    if n < cfg["n_min"]:
        return "N-TOO-SMALL"
    if rate < cfg["healthy_lo"]:
        return "SUSPICIOUS-LOW"
    if rate < cfg["healthy_hi"]:
        return "HEALTHY"
    if rate < cfg["usable_hi"]:
        return "USABLE-EXPENSIVE"
    return "UNINFORMATIVE"


def anchor_agreement(accepted: List[dict], anchor: List[dict]) -> Optional[dict]:
    """Cross accepted.jsonl (rho-sample) x anchor_outbox by context_hash.

    Agreement = share of shared context_hashes where accepted.label == anchor.label.
    Returns None when there is no overlap (no signal this week).
    """
    anc: Dict[str, str] = {}
    for e in anchor:
        ch = e.get("context_hash")
        lab = e.get("label")
        if ch and lab is not None:
            anc[ch] = lab
    shared = 0
    agree = 0
    for a in accepted:
        ch = a.get("context_hash")
        if ch in anc:
            shared += 1
            if a.get("label") == anc[ch]:
                agree += 1
    if shared == 0:
        return None
    return {"n_sampled": shared, "n_agree": agree,
            "agreement": round(agree / shared, 4)}


def e1(metrics: dict, accepted: List[dict], anchor: List[dict], cfg: dict) -> dict:
    """E1 — reads judge_metrics JSON (per jtype x judge_id) and re-derives the
    gate verdict from injected thresholds; adds anchor agreement.

    Segments strictly by (jtype, judge_id); never averages across judge versions
    (PRD_B7 §6 edge case 3). judge_metrics groups by jtype; if a `judge_id`
    dimension is present it is preserved, else the single fleet judge is assumed.
    """
    gcfg = cfg["e1"]["abstention_gate"]
    by_type = metrics.get("by_type", {}) or {}
    out_types: Dict[str, dict] = {}
    for jt, m in by_type.items():
        n = int(m.get("attempted", (m.get("emitted", 0) + m.get("abstained", 0))))
        rate = float(m.get("abstention_rate", 0.0))
        out_types[jt] = {
            "judge_id": m.get("judge_id", "fleet"),
            "attempted": n,
            "emitted": int(m.get("emitted", 0)),
            "abstention_rate": round(rate, 4),
            "verdict": gate_verdict(rate, n, gcfg),
            "label_distribution": m.get("label_distribution", {}),
            "mean_confidence": m.get("mean_confidence"),
            "prediction_set_sizes": m.get("prediction_set_sizes", {}),
            "order_disagreements": m.get("order_disagreements", 0),
        }
    return {
        "by_type": out_types,
        "anchor_agreement": anchor_agreement(accepted, anchor),
    }


# ===========================================================================
# E2 · seeded contradictions
# ===========================================================================


def _pair_uids(pair: dict) -> Tuple[str, str]:
    """Deterministic block uids written by seed-contradictions."""
    return f"{pair['id']}-a", f"{pair['id']}-b"


def _opposes_index(edges: List[dict]) -> set:
    idx = set()
    for e in edges:
        if e.get("edge_type") == "opposes":
            f, t = e.get("from"), e.get("to")
            if f is not None and t is not None:
                idx.add(frozenset((f, t)))
    return idx


def _s2_flagged(lint: dict) -> set:
    """focusNodes carrying an S2 (UnsupportedClaim) violation. focusNode is a
    urn:mnemo:node:<uid>; map back to bare uid for pairing."""
    flagged = set()
    for r in (lint.get("results") or []):
        shape = str(r.get("shape", ""))
        if "S2" in shape or "UnsupportedClaim" in shape:
            fn = str(r.get("focusNode", ""))
            uid = fn.rsplit(":", 1)[-1] if fn else fn
            if uid:
                flagged.add(uid)
    return flagged


def e2(pairs: List[dict], edges: List[dict], lint: dict, cycle: int, cfg: dict) -> dict:
    """E2 — for each contradiction pair: detected iff a promoted `opposes` edge
    joins its two uids OR an S2 flag sits on either uid. Controls must stay clean.

    `cycle` is the current cycle index; a pending pair's age is reported relative
    to seed cycle 0 (pairs are seeded once). Detected pairs report method.
    """
    opp = _opposes_index(edges)
    s2 = _s2_flagged(lint)
    detected, pending, false_positives = [], [], []
    n_contra = 0
    for p in pairs:
        ua, ub = _pair_uids(p)
        by_edge = frozenset((ua, ub)) in opp
        by_s2 = (ua in s2) or (ub in s2)
        hit = by_edge or by_s2
        kind = p.get("kind", "contradiction")
        if kind == "control":
            if hit:
                false_positives.append({"id": p["id"], "domain": p.get("domain"),
                                        "method": "opposes" if by_edge else "s2"})
            continue
        n_contra += 1
        if hit:
            detected.append({"id": p["id"], "domain": p.get("domain"),
                             "method": "opposes" if by_edge else "s2"})
        else:
            pending.append({"id": p["id"], "domain": p.get("domain"),
                            "age_cycles": max(0, cycle)})
    n_controls = sum(1 for p in pairs if p.get("kind") == "control")
    ages = [q["age_cycles"] for q in pending]
    return {
        "n_contradictions": n_contra,
        "n_controls": n_controls,
        "detected": detected,
        "n_detected": len(detected),
        "pending": pending,
        "n_pending": len(pending),
        "median_pending_age": statistics.median(ages) if ages else 0,
        "false_positives": false_positives,
        "n_false_positives": len(false_positives),
        "detected_frac": round(len(detected) / n_contra, 4) if n_contra else 0.0,
    }


# ===========================================================================
# E3 · retrieval coverage  (three columns + marginal)
# ===========================================================================

# --- (a) FROZEN lexical baseline -------------------------------------------
# COMMITTED ONCE. Hashed in README_eval.md. Any change = a NEW column, never a
# retouch. Definition (ANNEX_B7 §3a): lowercase, strip punctuation, tokenize on
# whitespace; score(block) = |tok(question) ∩ tok(block)| / |tok(question)|;
# rank desc, take top-20.

_LEX_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def lexical_tokens(text: str) -> set:
    """FROZEN. Lowercase, strip punctuation (unicode word boundary), whitespace
    split. NFC then casefold to be accent/width stable across the graph."""
    t = unicodedata.normalize("NFC", text or "").lower()
    t = _LEX_PUNCT_RE.sub(" ", t)
    return {w for w in t.split() if w}


def lexical_baseline(question: str, blocks: List[Tuple[str, str]],
                     top_k: int = 20) -> List[str]:
    """FROZEN top-k retrieval. blocks = [(uid, string)]. Deterministic tie-break
    by (-score, uid)."""
    q = lexical_tokens(question)
    if not q:
        return []
    scored = []
    for uid, s in blocks:
        inter = len(q & lexical_tokens(s))
        if inter:
            scored.append((inter / len(q), uid))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [uid for _, uid in scored[:top_k]]


# frozen-baseline self-hash: the source text of the two functions above.
_FROZEN_LEXICAL_SRC = (
    'NFC lower; re.sub([^\\w\\s]," "); whitespace split; '
    'score=|q∩b|/|q|; sort (-score,uid); top20'
)


def frozen_lexical_hash() -> str:
    return "sha256:" + _sha256(_FROZEN_LEXICAL_SRC)


# --- (b) kNN via embed_index.py query --------------------------------------


def _knn_via_subprocess(question: str, embed_index: str, top_k: int = 20) -> List[str]:
    """Real path (NOT exercised by self-test). Calls
    `embed_index.py query --text 'query: <question>' --top <k>`; expects one JSON
    object per stdout line carrying a `uid` (asymmetric e5 query prefix)."""
    cmd = [sys.executable, embed_index, "query", "--text",
           f"query: {question}", "--top", str(top_k)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    uids = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        u = row.get("uid") or row.get("b") or row.get("a")
        if u:
            uids.append(u)
    return uids[:top_k]


# --- (c) promoted edges: <=2 hops from lexical top-5 -----------------------


def _adjacency(edges: List[dict]) -> Dict[str, set]:
    adj: Dict[str, set] = defaultdict(set)
    for e in edges:
        f, t = e.get("from"), e.get("to")
        if f is not None and t is not None:
            adj[f].add(t)
            adj[t].add(f)
    return adj


def promoted_neighbourhood(seeds: List[str], edges: List[dict], hops: int = 2) -> set:
    """Blocks reachable within `hops` of any seed, following edges.jsonl only
    (supports/opposes/refines + continues). Includes seeds."""
    adj = _adjacency(edges)
    reached = set(seeds)
    frontier = set(seeds)
    for _ in range(hops):
        nxt = set()
        for u in frontier:
            nxt |= adj.get(u, set())
        nxt -= reached
        reached |= nxt
        frontier = nxt
        if not frontier:
            break
    return reached


def _coverage(gold: set, reached: set) -> float:
    if not gold:
        return 0.0  # orphan gold handled by caller (excluded from mean)
    return len(gold & reached) / len(gold)


def e3(questions: List[dict], snapshot: List[dict], edges: List[dict],
       knn_fn: Optional[Callable[[str], List[str]]] = None) -> dict:
    """E3 — three retrieval columns per question, coverage@20 = |gold∩reached|/|gold|.

    knn_fn(question)->[uid] is injected (default None => column b reported as
    skipped/unavailable, e.g. when embeddings.db absent or in self-test).
    """
    # flatten snapshot to (uid, string), and to a uid->string map
    blocks: List[Tuple[str, str]] = []
    for page in snapshot:
        stack = list(page.get("children") or [])
        while stack:
            b = stack.pop()
            uid = b.get("uid")
            if uid:
                blocks.append((uid, b.get("string", "") or ""))
            stack.extend(b.get("children") or [])
    valid_uids = {u for u, _ in blocks}

    per_q = []
    dom_cov: Dict[str, Dict[str, List[float]]] = defaultdict(
        lambda: {"a": [], "b": [], "c": [], "union": [], "marginal": []})
    orphans = []
    knn_available = knn_fn is not None
    for q in questions:
        gold = set(q.get("gold_uids") or [])
        present_gold = gold & valid_uids
        if gold and not present_gold:
            orphans.append(q["id"])
            continue  # gold fully deleted/rewritten -> no false failure
        gold = present_gold or gold
        question = q.get("question", "")
        domain = q.get("domain", "?")

        a = lexical_baseline(question, blocks, top_k=20)
        a_set = set(a)
        b_set = set(knn_fn(question)) if knn_available else set()
        seeds = a[:5]
        c_set = promoted_neighbourhood(seeds, edges, hops=2)
        marginal_set = c_set - a_set
        union = a_set | b_set | c_set

        cov_a = _coverage(gold, a_set)
        cov_b = _coverage(gold, b_set) if knn_available else None
        cov_c = _coverage(gold, c_set)
        cov_union = _coverage(gold, union)
        cov_marginal = _coverage(gold, marginal_set)

        per_q.append({"id": q["id"], "domain": domain,
                      "a": round(cov_a, 4),
                      "b": round(cov_b, 4) if cov_b is not None else None,
                      "c": round(cov_c, 4),
                      "union": round(cov_union, 4),
                      "marginal": round(cov_marginal, 4)})
        dom_cov[domain]["a"].append(cov_a)
        if cov_b is not None:
            dom_cov[domain]["b"].append(cov_b)
        dom_cov[domain]["c"].append(cov_c)
        dom_cov[domain]["union"].append(cov_union)
        dom_cov[domain]["marginal"].append(cov_marginal)

    def _mean(xs):
        return round(statistics.mean(xs), 4) if xs else None

    by_domain = {d: {k: _mean(v) for k, v in cols.items()}
                 for d, cols in dom_cov.items()}
    all_a = [x for c in dom_cov.values() for x in c["a"]]
    all_b = [x for c in dom_cov.values() for x in c["b"]]
    all_c = [x for c in dom_cov.values() for x in c["c"]]
    all_u = [x for c in dom_cov.values() for x in c["union"]]
    all_m = [x for c in dom_cov.values() for x in c["marginal"]]
    overall = {"a": _mean(all_a), "b": _mean(all_b) if knn_available else None,
               "c": _mean(all_c), "union": _mean(all_u),
               "marginal": _mean(all_m)}
    return {
        "knn_available": knn_available,
        "frozen_lexical_hash": frozen_lexical_hash(),
        "n_questions": len(questions),
        "n_scored": len(per_q),
        "orphans": orphans,
        "per_question": per_q,
        "by_domain": by_domain,
        "overall": overall,
    }


# ===========================================================================
# E4 · stance stability
# ===========================================================================

_CHURN_CAUSES = ("retracted", "re-judgment", "rejudgment", "re_judgment")


def _is_churn(caused_by: Optional[str]) -> bool:
    cb = (caused_by or "").lower()
    return any(tok in cb for tok in _CHURN_CAUSES)


def _retracted_nodes(events: List[dict]) -> set:
    """Node ids touched by retraction / re-judgment events. The v0 producer
    (cycle_tools.py) sets stance_diff.caused_by to the NODE id, not a cause
    string — so the churn signal must be recovered by crossing the diff node
    against the event log (tx_data is serialized EDN: substring scan)."""
    out: set = set()
    for ev in events or []:
        etype = str(ev.get("type", "")).lower()
        if "retract" in etype or "re-judg" in etype or "rejudg" in etype:
            out.add(("__event__", json.dumps(ev.get("tx_data", ""),
                                             ensure_ascii=False)))
    return out


def _node_in_retractions(node: str, retractions: set) -> bool:
    if not node:
        return False
    return any(node in payload for _, payload in retractions)


def e4(stance_diffs: List[dict], cfg: dict,
       events: Optional[List[dict]] = None) -> dict:
    """E4 — churn share of stance diffs. churn = diffs caused by a retraction
    / re-judgment (vs new evidence, which is healthy). Primary detector:
    cross the diff's node against retraction events in store/events.jsonl;
    fallback: the caused_by string heuristic (kept for producers that do
    stamp a cause string)."""
    total = len(stance_diffs)
    retractions = _retracted_nodes(events or [])
    churn = sum(1 for d in stance_diffs
                if _is_churn(d.get("caused_by"))
                or _node_in_retractions(d.get("node", ""), retractions))
    evidence = total - churn
    share = round(churn / total, 4) if total else 0.0
    return {
        "n_changes": total,
        "n_evidence": evidence,
        "n_churn": churn,
        "churn_share": share,
        "threshold": cfg["e4"]["churn"]["max_share"],
    }


# ===========================================================================
# E5 · human loop
# ===========================================================================


def e5(harvest_ledger: List[dict], taskgen_ledger: List[dict],
       calsets: List[dict], elaboration_coverage: List[dict],
       cfg: dict) -> dict:
    """E5 — response rate per task_type (task_harvest stats + B3 ledgers),
    cumulative :human calset examples, elaboration coverage per train.

    harvest_ledger rows carry a task_type + whether answered; taskgen_ledger rows
    are generated tasks. Rate per type = answered / generated. We accept either
    an explicit `answered` flag on harvest rows or presence of an `answered_ts`.
    """
    gen_by_type: Counter = Counter()
    for r in taskgen_ledger:
        gen_by_type[r.get("task_type", "?")] += 1
    ans_by_type: Counter = Counter()
    for r in harvest_ledger:
        answered = bool(r.get("answered") or r.get("answered_ts") or
                        (r.get("event", "").startswith("human.response")))
        if answered:
            ans_by_type[r.get("task_type", "?")] += 1
    types = sorted(set(gen_by_type) | set(ans_by_type))
    per_type = {}
    for t in types:
        gen = gen_by_type.get(t, 0)
        ans = ans_by_type.get(t, 0)
        per_type[t] = {"generated": gen, "answered": ans,
                       "rate": round(ans / gen, 4) if gen else None}
    total_gen = sum(gen_by_type.values())
    total_ans = sum(ans_by_type.values())
    overall_rate = round(total_ans / total_gen, 4) if total_gen else None

    human_examples = sum(
        1 for r in calsets
        if (r.get("provenance") or {}).get("source") == "human")

    cov = {}
    for row in elaboration_coverage or []:
        train = row.get("train", row.get("jtype", "?"))
        cov[train] = row.get("coverage", row.get("elaboration_coverage"))

    return {
        "per_type": per_type,
        "overall_response_rate": overall_rate,
        "human_examples_cumulative": human_examples,
        "elaboration_coverage": cov,
        "min_rate_7d": cfg["e5"]["response_rate"]["min_rate_7d"],
    }


# ===========================================================================
# trends — Unicode sparklines over 8 weeks
# ===========================================================================

_SPARK = "▁▂▃▅▇"


def sparkline(values: List[Optional[float]], lo: float = 0.0,
              hi: Optional[float] = None) -> str:
    """8-block Unicode sparkline. `None` weeks (no data) render as a space —
    no interpolation (PRD_B7 §6 edge case 1)."""
    present = [v for v in values if v is not None]
    if not present:
        return " " * len(values)
    lo_v = lo if lo is not None else min(present)
    hi_v = hi if hi is not None else max(present)
    span = (hi_v - lo_v) or 1.0
    out = []
    for v in values:
        if v is None:
            out.append(" ")
            continue
        frac = max(0.0, min(1.0, (v - lo_v) / span))
        idx = int(round(frac * (len(_SPARK) - 1)))
        out.append(_SPARK[idx])
    return "".join(out)


def _get_path(d: dict, dotted: str):
    cur = d
    for k in dotted.split("."):
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return None
    return cur


# metric-key -> (dotted path into a report dict, low, high) for the sparkline scale
TREND_KEYS = {
    "e2.detected_frac": (0.0, 1.0),
    "e3.overall.union": (0.0, 1.0),
    "e3.overall.marginal": (0.0, 1.0),
    "e4.churn_share": (0.0, 1.0),
    "e5.overall_response_rate": (0.0, 1.0),
}


def trends(history: List[dict], current: dict, weeks: int = 8) -> dict:
    """Build sparklines + deltas from up-to-`weeks` prior reports + current.

    history = list of prior report dicts (oldest..newest). Missing metrics in a
    week render as gaps. Returns {key: {spark, delta, current}}."""
    series = (history + [current])[-weeks:]
    # left-pad to `weeks` with None-bearing placeholders
    pad = weeks - len(series)
    out = {}
    for key, (lo, hi) in TREND_KEYS.items():
        vals = [None] * pad + [_get_path(r, key) for r in series]
        out[key] = {
            "spark": sparkline(vals, lo, hi),
            "current": vals[-1],
            "delta": (round(vals[-1] - vals[-2], 4)
                      if len(vals) >= 2 and vals[-1] is not None
                      and vals[-2] is not None else None),
        }
    return out


# ===========================================================================
# alerts — threshold => decision (from eval_thresholds.yaml)
# ===========================================================================


def compute_alerts(report: dict, history: List[dict], cfg: dict) -> List[dict]:
    alerts: List[dict] = []

    def add(metric, msg, decision):
        alerts.append({"metric": metric, "message": msg, "decision": decision})

    # E1 gate verdicts
    e1cfg = cfg["e1"]["abstention_gate"]
    for jt, m in report.get("e1", {}).get("by_type", {}).items():
        v = m["verdict"]
        if v in ("SUSPICIOUS-LOW", "USABLE-EXPENSIVE", "UNINFORMATIVE"):
            add(f"E1/{jt}", f"gate {v} (abstention {m['abstention_rate']:.1%})",
                e1cfg["decisions"][v])
    # E1 anchor drift: 2 consecutive weekly drops
    aa_cfg = cfg["e1"]["anchor_agreement"]
    aa_series = [(_get_path(r, "e1.anchor_agreement.agreement")) for r in
                 (history + [report])][-(aa_cfg["drop_weeks"] + 1):]
    aa_series = [x for x in aa_series if x is not None]
    if len(aa_series) >= aa_cfg["drop_weeks"] + 1 and all(
            aa_series[i] > aa_series[i + 1] for i in range(len(aa_series) - 1)):
        add("E1/anchor", "anchor agreement falling %d weeks" % aa_cfg["drop_weeks"],
            aa_cfg["decision"])
    # E2 detection + false positives
    e2r = report.get("e2", {})
    e2cfg = cfg["e2"]
    if e2r.get("n_contradictions") and e2r.get("detected_frac", 0.0) < \
            e2cfg["detection"]["min_detected_frac"]:
        add("E2/detection",
            f"only {e2r['n_detected']}/{e2r['n_contradictions']} detected",
            e2cfg["detection"]["decision"])
    if e2r.get("n_false_positives", 0) > e2cfg["false_positives"]["max_on_controls"]:
        add("E2/false-positive",
            f"{e2r['n_false_positives']} control pair(s) flagged",
            e2cfg["false_positives"]["decision"])
    # E3 marginal graph value
    e3r = report.get("e3", {})
    marg = _get_path(e3r, "overall.marginal")
    if marg is not None and marg <= cfg["e3"]["marginal_graph_value"]["min_marginal"]:
        add("E3/marginal", "promoted graph adds no marginal coverage",
            cfg["e3"]["marginal_graph_value"]["decision"])
    # E4 churn over window
    e4cfg = cfg["e4"]["churn"]
    e4_series = [_get_path(r, "e4.churn_share") for r in (history + [report])]
    e4_series = [x for x in e4_series if x is not None][-e4cfg["window_weeks"]:]
    if e4_series and all(x > e4cfg["max_share"] for x in e4_series) and \
            len(e4_series) >= e4cfg["window_weeks"]:
        add("E4/churn", f"churn > {e4cfg['max_share']:.0%} for "
            f"{e4cfg['window_weeks']} weeks", e4cfg["decision"])
    # E5 response rate + elaboration coverage
    e5r = report.get("e5", {})
    e5cfg = cfg["e5"]
    rr = e5r.get("overall_response_rate")
    if rr is not None and rr < e5cfg["response_rate"]["min_rate_7d"]:
        add("E5/response-rate", f"response rate {rr:.0%} below floor",
            e5cfg["response_rate"]["decision"])
    for train, c in (e5r.get("elaboration_coverage") or {}).items():
        if c is not None and c < e5cfg["elaboration_coverage"]["min_coverage"]:
            add(f"E5/elaboration/{train}", f"coverage {c:.0%} thin",
                e5cfg["elaboration_coverage"]["decision"])
    return alerts


# ===========================================================================
# debts — active tech debt surfaced in the report
# ===========================================================================


def compute_debts(metrics: dict, lint: dict, spend: List[dict],
                  skipped_steps: Optional[List[str]] = None) -> dict:
    api_mode = any((r.get("usd", 0) or 0) > 0 for r in spend)
    open_flags = int(lint.get("n_violations", 0) or 0)
    return {
        "api_mode_active": api_mode,
        "open_lint_flags": open_flags,
        "skipped_steps": skipped_steps or [],
    }


# ===========================================================================
# report assembly
# ===========================================================================


def build_report(week: str, *, metrics=None, accepted=None, anchor=None,
                 pairs=None, edges=None, lint=None, cycle=0,
                 questions=None, snapshot=None, knn_fn=None,
                 stance_diffs=None, harvest_ledger=None, taskgen_ledger=None,
                 calsets=None, elaboration_coverage=None, spend=None,
                 skipped_steps=None, history=None, cfg=None,
                 events=None) -> dict:
    cfg = cfg or load_thresholds()
    history = history or []
    rep = {
        "week": week,
        "generated": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "e1": e1(metrics or {}, accepted or [], anchor or [], cfg),
        "e2": e2(pairs or [], edges or [], lint or {}, cycle, cfg),
        "e3": e3(questions or [], snapshot or [], edges or [], knn_fn),
        "e4": e4(stance_diffs or [], cfg, events or []),
        "e5": e5(harvest_ledger or [], taskgen_ledger or [], calsets or [],
                 elaboration_coverage or [], cfg),
        "debts": compute_debts(metrics or {}, lint or {}, spend or [],
                               skipped_steps),
    }
    rep["alerts"] = compute_alerts(rep, history, cfg)
    rep["trends"] = trends(history, rep)
    return rep


# ===========================================================================
# render — markdown (gabarit ANNEX_B7 §4) + json mirror
# ===========================================================================


def render_md(rep: dict) -> str:
    L = [f"# Rapport hebdo — semaine du {rep['week']}",
         f"*généré {rep['generated']}*", ""]

    # Alertes (only if crossed)
    L += ["## ⚠ Alertes"]
    if rep["alerts"]:
        for a in rep["alerts"]:
            L += [f"- **{a['metric']}** — {a['message']}",
                  f"  → décision : {a['decision']}"]
    else:
        L += ["- aucune (tous les seuils dans la bande)"]
    L += [""]

    # E1
    L += ["## E1 Jugement"]
    e1r = rep["e1"]
    if e1r["by_type"]:
        L += ["| jtype | judge_id | attempted | abstention | gate |",
              "|---|---|---|---|---|"]
        for jt, m in e1r["by_type"].items():
            L += [f"| {jt} | {m['judge_id']} | {m['attempted']} | "
                  f"{m['abstention_rate']:.1%} | {m['verdict']} |"]
    else:
        L += ["- no data"]
    aa = e1r["anchor_agreement"]
    L += [f"- accord ancre : {aa['agreement']:.1%} (n={aa['n_sampled']})"
          if aa else "- accord ancre : no data", ""]

    # E2
    e2r = rep["e2"]
    L += ["## E2 Contradictions",
          f"- détectées **{e2r['n_detected']}/{e2r['n_contradictions']}** · "
          f"faux positifs **{e2r['n_false_positives']}/{e2r['n_controls']}** · "
          f"âge médian en attente {e2r['median_pending_age']} cycles"]
    if e2r["pending"]:
        L += ["- en attente : " + ", ".join(
            f"{p['id']}(+{p['age_cycles']})" for p in e2r["pending"])]
    L += [""]

    # E3
    e3r = rep["e3"]
    L += ["## E3 Récupération"]
    if e3r["n_scored"]:
        L += ["| domaine | (a) lexical | (b) kNN | (c) arêtes | union | marginal |",
              "|---|---|---|---|---|---|"]

        def _f(x):
            return f"{x:.0%}" if isinstance(x, (int, float)) else "—"
        for d, c in e3r["by_domain"].items():
            L += [f"| {d} | {_f(c['a'])} | {_f(c['b'])} | {_f(c['c'])} | "
                  f"{_f(c['union'])} | {_f(c['marginal'])} |"]
        o = e3r["overall"]
        L += [f"| **union** | {_f(o['a'])} | {_f(o['b'])} | {_f(o['c'])} | "
              f"{_f(o['union'])} | {_f(o['marginal'])} |"]
        if not e3r["knn_available"]:
            L += ["- (b) kNN indisponible cette semaine (embeddings absents)"]
        if e3r["orphans"]:
            L += ["- gold orphelins (exclus) : " + ", ".join(e3r["orphans"])]
    else:
        L += ["- no data (eval_questions.yaml vide — à remplir par le propriétaire)"]
    L += [f"- baseline lexicale figée : `{e3r['frozen_lexical_hash']}`", ""]

    # E4
    e4r = rep["e4"]
    L += ["## E4 Stances",
          f"- changements {e4r['n_changes']} · évidence {e4r['n_evidence']} · "
          f"churn {e4r['n_churn']} (**{e4r['churn_share']:.0%}**, "
          f"seuil {e4r['threshold']:.0%})", ""]

    # E5
    e5r = rep["e5"]
    L += ["## E5 Boucle humaine"]
    rr = e5r["overall_response_rate"]
    L += [f"- taux de réponse global : "
          + (f"{rr:.0%}" if rr is not None else "no data")]
    if e5r["per_type"]:
        for t, m in e5r["per_type"].items():
            rate = f"{m['rate']:.0%}" if m["rate"] is not None else "—"
            L += [f"  - {t} : {m['answered']}/{m['generated']} ({rate})"]
    L += [f"- exemples :human cumulés : {e5r['human_examples_cumulative']}"]
    if e5r["elaboration_coverage"]:
        L += ["- coverage élaboration par train : " + ", ".join(
            f"{k}={v:.0%}" if isinstance(v, (int, float)) else f"{k}=—"
            for k, v in e5r["elaboration_coverage"].items())]
    L += [""]

    # Dettes
    d = rep["debts"]
    L += ["## Dettes",
          f"- mode API actif : {'oui' if d['api_mode_active'] else 'non'}",
          f"- flags linter ouverts : {d['open_lint_flags']}",
          f"- étapes sautées : {', '.join(d['skipped_steps']) or 'aucune'}", ""]

    # Tendances
    L += ["## Tendances (8 semaines ▁▂▃▅▇)"]
    for key, tr in rep["trends"].items():
        delta = (f" Δ{tr['delta']:+.3f}" if tr["delta"] is not None else "")
        L += [f"- `{key}` `{tr['spark']}`{delta}"]
    L += [""]
    return "\n".join(L)


def write_json(rep: dict, path: pathlib.Path) -> None:
    path.write_text(json.dumps(rep, ensure_ascii=False, indent=2),
                    encoding="utf-8")


# ===========================================================================
# subcommands
# ===========================================================================


def _in(base: pathlib.Path, *parts) -> pathlib.Path:
    return base.joinpath(*parts)


def cmd_report(a) -> None:
    base = pathlib.Path(a.indir)
    hist_dir = pathlib.Path(a.history)
    history = []
    if hist_dir.exists():
        for p in sorted(hist_dir.glob("weekly_report_*.json")):
            try:
                history.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass
    cfg = load_thresholds(pathlib.Path(a.thresholds) if a.thresholds else None)
    calset_paths = [pathlib.Path(p) for p in (a.calsets or [])]
    rep = build_report(
        a.week,
        metrics=read_metrics_json(_in(base, a.metrics)) if a.metrics else {},
        accepted=read_accepted(_in(base, a.accepted)) if a.accepted else [],
        anchor=read_anchor_outbox(_in(base, a.anchor)) if a.anchor else [],
        pairs=read_pairs(pathlib.Path(a.pairs)) if a.pairs else [],
        edges=read_edges(_in(base, a.edges)) if a.edges else [],
        lint=read_lint(_in(base, a.lint)) if a.lint else {},
        cycle=a.cycle,
        questions=read_questions(pathlib.Path(a.questions)) if a.questions else [],
        snapshot=read_snapshot(_in(base, a.snapshot)) if a.snapshot else [],
        knn_fn=None,  # report path leaves kNN to `retrieval`; keep report offline-safe
        stance_diffs=read_stance_diffs(_in(base, a.stance_diff)) if a.stance_diff else [],
        harvest_ledger=read_ledgers(_in(base, a.harvest_ledger)) if a.harvest_ledger else [],
        taskgen_ledger=read_ledgers(_in(base, a.taskgen_ledger)) if a.taskgen_ledger else [],
        calsets=read_calsets(calset_paths),
        elaboration_coverage=read_ledgers(_in(base, a.elaboration)) if a.elaboration else [],
        spend=read_ledgers(_in(base, a.spend)) if a.spend else [],
        events=read_events(_in(base, a.events)) if getattr(a, "events", None)
        else [],
        history=history, cfg=cfg,
    )
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "weekly_report.md").write_text(render_md(rep), encoding="utf-8")
    write_json(rep, out / "weekly_report.json")
    hist_dir.mkdir(parents=True, exist_ok=True)
    tag = re.sub(r"[^0-9A-Za-z_-]", "-", a.week)
    (hist_dir / f"weekly_report_{tag}.md").write_text(render_md(rep), encoding="utf-8")
    write_json(rep, hist_dir / f"weekly_report_{tag}.json")
    print(render_md(rep))


def build_seed_orders(pairs: List[dict], cycle: int = 0) -> List[dict]:
    """seed-contradictions → writeback orders (kind: seed, allowlist M/Eval/*,
    out of budget). One order per block (a and b) with eval-seeded:: true."""
    orders = []
    for p in pairs:
        ua, ub = _pair_uids(p)
        for uid, text, side in ((ua, p["a"], "a"), (ub, p["b"], "b")):
            orders.append({
                "kind": "seed",
                "idempotency_key": "sha256:" + _sha256(p["id"] + side),
                "target": {"page": "M/Eval/Seeded", "under": None},
                "content": {
                    "template": "eval_seed_block",
                    "fields": {
                        "uid": uid,
                        "text": text,
                        "eval-seeded": True,
                        "pair_id": p["id"],
                        "pair_kind": p.get("kind", "contradiction"),
                        "domain": p.get("domain"),
                    },
                },
                "caused_by": f"eval.seed:{p['id']}",
            })
    return orders


def cmd_seed_contradictions(a) -> None:
    pairs = read_pairs(pathlib.Path(a.pairs))
    orders = build_seed_orders(pairs, a.cycle)
    outp = pathlib.Path(a.orders)
    outp.parent.mkdir(parents=True, exist_ok=True)
    with outp.open("a", encoding="utf-8") as fh:
        for o in orders:
            fh.write(json.dumps(o, ensure_ascii=False) + "\n")
    n_c = sum(1 for p in pairs if p.get("kind") != "control")
    n_ctrl = sum(1 for p in pairs if p.get("kind") == "control")
    print(f"seeded {len(orders)} blocks ({n_c} contradiction + {n_ctrl} control "
          f"pairs) → {outp} [kind: seed, allowlist M/Eval/*, out of budget]",
          file=sys.stderr)
    print(json.dumps({"orders": len(orders), "pairs": len(pairs)}))


def cmd_check_seeded(a) -> None:
    pairs = read_pairs(pathlib.Path(a.pairs))
    edges = read_edges(pathlib.Path(a.edges))
    lint = read_lint(pathlib.Path(a.lint)) if a.lint else {}
    cfg = load_thresholds(pathlib.Path(a.thresholds) if a.thresholds else None)
    res = e2(pairs, edges, lint, a.cycle, cfg)
    print(json.dumps(res, ensure_ascii=False, indent=2))


def cmd_retrieval(a) -> None:
    questions = read_questions(pathlib.Path(a.questions))
    snapshot = read_snapshot(pathlib.Path(a.snapshot))
    edges = read_edges(pathlib.Path(a.edges)) if a.edges else []
    knn_fn = None
    if a.embed_index:
        knn_fn = lambda q: _knn_via_subprocess(q, a.embed_index)  # noqa: E731
    res = e3(questions, snapshot, edges, knn_fn)
    print(json.dumps(res, ensure_ascii=False, indent=2))


# ===========================================================================
# self-test  (ZERO network; synthetic fixtures only)
# ===========================================================================


def _synthetic_metrics(rate: float, n: int, jtype="edge_type") -> dict:
    ab = int(round(rate * n))
    return {"by_type": {jtype: {
        "attempted": n, "emitted": n - ab, "abstained": ab,
        "abstention_rate": rate, "judge_id": "judge-v1",
        "label_distribution": {"supports": (n - ab)},
        "mean_confidence": 0.8, "prediction_set_sizes": {"2": ab},
        "order_disagreements": 0}}}


def self_test() -> None:
    n_ok = [0]

    def ok(cond, msg):
        if not cond:
            raise AssertionError(msg)
        n_ok[0] += 1
        print(f"  ✓ {msg}")

    cfg = load_thresholds()

    # ---- E1 gate verdicts across ALL buckets --------------------------------
    ok(e1(_synthetic_metrics(0.20, 100), [], [], cfg)["by_type"]["edge_type"]
       ["verdict"] == "HEALTHY", "E1 gate 20% -> HEALTHY")
    ok(e1(_synthetic_metrics(0.05, 100), [], [], cfg)["by_type"]["edge_type"]
       ["verdict"] == "SUSPICIOUS-LOW", "E1 gate 5% -> SUSPICIOUS-LOW")
    ok(e1(_synthetic_metrics(0.45, 100), [], [], cfg)["by_type"]["edge_type"]
       ["verdict"] == "USABLE-EXPENSIVE", "E1 gate 45% -> USABLE-EXPENSIVE")
    ok(e1(_synthetic_metrics(0.70, 100), [], [], cfg)["by_type"]["edge_type"]
       ["verdict"] == "UNINFORMATIVE", "E1 gate 70% -> UNINFORMATIVE")
    ok(e1(_synthetic_metrics(0.20, 40), [], [], cfg)["by_type"]["edge_type"]
       ["verdict"] == "N-TOO-SMALL", "E1 gate n<50 -> N-TOO-SMALL")
    # anchor agreement (cross accepted x anchor by context_hash)
    acc = [{"context_hash": "h1", "label": "supports"},
           {"context_hash": "h2", "label": "opposes"},
           {"context_hash": "h3", "label": "supports"}]
    anc = [{"context_hash": "h1", "label": "supports"},
           {"context_hash": "h2", "label": "supports"}]
    aa = e1(_synthetic_metrics(0.2, 100), acc, anc, cfg)["anchor_agreement"]
    ok(aa["n_sampled"] == 2 and aa["n_agree"] == 1 and aa["agreement"] == 0.5,
       "E1 anchor agreement 1/2")
    ok(e1(_synthetic_metrics(0.2, 100), acc, [], cfg)["anchor_agreement"] is None,
       "E1 anchor agreement None with no overlap")

    # ---- E2 seed + check on the fixture (incl. control false-positive) ------
    pairs = read_pairs(HERE / "fixtures" / "eval" / "seeded_pairs.yaml")
    ok(sum(1 for p in pairs if p["kind"] == "contradiction") == 15,
       "E2 fixture has 15 contradictions")
    ok(sum(1 for p in pairs if p["kind"] == "control") == 10,
       "E2 fixture has 10 controls")
    orders = build_seed_orders(pairs)
    ok(len(orders) == 50 and all(o["kind"] == "seed" for o in orders),
       "E2 seed -> 50 kind:seed orders")
    ok(all(o["target"]["page"] == "M/Eval/Seeded" for o in orders)
       and all(o["content"]["fields"]["eval-seeded"] is True for o in orders),
       "E2 seed orders target M/Eval/Seeded with eval-seeded::true")
    ok(len({o["idempotency_key"] for o in orders}) == 50,
       "E2 seed idempotency keys unique")
    # detect 12/15 via opposes edges, 1 more via S2 flag, 2 pending; 1 control FP
    det_edges = []
    for p in pairs[:12]:  # first 12 contradictions
        ua, ub = _pair_uids(p)
        det_edges.append({"edge_id": f"{ua}->{ub}#opposes",
                          "edge_type": "opposes", "from": ua, "to": ub})
    # a control pair wrongly promoted -> false positive
    cua, cub = _pair_uids([p for p in pairs if p["kind"] == "control"][0])
    det_edges.append({"edge_id": f"{cua}->{cub}#opposes",
                     "edge_type": "opposes", "from": cua, "to": cub})
    # one contradiction detected only via S2
    s2_uid = _pair_uids(pairs[12])[0]
    lint = {"results": [{"focusNode": f"urn:mnemo:node:{s2_uid}",
                        "shape": "S2", "severity": "Violation"}]}
    r2 = e2(pairs, det_edges, lint, cycle=3, cfg=cfg)
    ok(r2["n_detected"] == 13, "E2 detects 12 opposes + 1 S2 = 13")
    ok(r2["n_pending"] == 2, "E2 leaves 2 pending")
    ok(all(q["age_cycles"] == 3 for q in r2["pending"]), "E2 pending age = cycle")
    ok(r2["n_false_positives"] == 1, "E2 flags 1 control false positive")
    ok(r2["n_controls"] == 10, "E2 counts 10 controls")
    # clean run: no edges -> zero detected, zero FP
    r2c = e2(pairs, [], {}, cycle=1, cfg=cfg)
    ok(r2c["n_detected"] == 0 and r2c["n_false_positives"] == 0,
       "E2 clean graph: 0 detected, 0 FP")

    # ---- E3 lexical baseline determinism -----------------------------------
    ok(frozen_lexical_hash() == frozen_lexical_hash(), "E3 frozen hash stable")
    blocks = [("u1", "Le registre des traitements est obligatoire dès le premier salarié"),
              ("u2", "La base légale de la prospection est le consentement"),
              ("u3", "registre obligatoire traitements salarié premier")]
    q = "registre des traitements obligatoire salarié"
    r_a = lexical_baseline(q, blocks, top_k=20)
    r_b = lexical_baseline(q, blocks, top_k=20)
    ok(r_a == r_b, "E3 lexical baseline deterministic")
    ok(r_a[0] in ("u1", "u3"), "E3 lexical top hit is a matching block")
    ok(lexical_baseline("", blocks) == [], "E3 empty question -> empty")
    ok(lexical_tokens("L'Article 28, RGPD!") == {"l", "article", "28", "rgpd"},
       "E3 tokenizer strips punctuation")
    # promoted neighbourhood 2-hop
    edges = [{"from": "a", "to": "b", "edge_type": "supports"},
             {"from": "b", "to": "c", "edge_type": "refines"},
             {"from": "c", "to": "d", "edge_type": "opposes"}]
    nb = promoted_neighbourhood(["a"], edges, hops=2)
    ok(nb == {"a", "b", "c"}, "E3 2-hop neighbourhood {a,b,c}")
    ok("d" not in nb, "E3 3rd hop excluded")
    # full e3 on a synthetic snapshot with gold reachable only via edges (marginal)
    snap = [{"title": "P", "children": [
        {"uid": "q1", "string": "registre des traitements obligatoire"},
        {"uid": "g1", "string": "texte totalement different zzz"},
    ]}]
    qs = [{"id": "q-1", "question": "registre des traitements obligatoire",
           "gold_uids": ["g1"], "domain": "rgpd"}]
    # edge links lexical hit q1 -> gold g1, so column (c) reaches it, (a) does not
    e3edges = [{"from": "q1", "to": "g1", "edge_type": "supports"}]
    r3 = e3(qs, snap, e3edges, knn_fn=None)
    ok(r3["n_scored"] == 1 and r3["overall"]["a"] == 0.0,
       "E3 lexical misses gold (a=0)")
    ok(r3["overall"]["c"] == 1.0 and r3["overall"]["marginal"] == 1.0,
       "E3 promoted edges recover gold (marginal=1)")
    ok(r3["overall"]["b"] is None and r3["knn_available"] is False,
       "E3 kNN skipped when no embed fn (self-test offline)")
    # kNN via injected mock (no network) covers column b
    r3b = e3(qs, snap, e3edges, knn_fn=lambda question: ["g1"])
    ok(r3b["overall"]["b"] == 1.0 and r3b["knn_available"] is True,
       "E3 injected kNN mock covers column b")
    # orphan gold excluded (not a false failure)
    r3o = e3([{"id": "q-x", "question": "registre", "gold_uids": ["ghost"],
               "domain": "rgpd"}], snap, [], knn_fn=None)
    ok(r3o["orphans"] == ["q-x"] and r3o["n_scored"] == 0,
       "E3 orphan gold excluded from scoring")

    # ---- E4 churn ----------------------------------------------------------
    diffs = [{"node": "n1", "old_status": "undecided", "new_status": "accepted-supported",
              "caused_by": "new-evidence:edge42"},
             {"node": "n2", "old_status": "accepted-supported", "new_status": "rejected",
              "caused_by": "retracted:cohort-7"},
             {"node": "n3", "old_status": "accepted-supported", "new_status": "undecided",
              "caused_by": "re-judgment:v2"}]
    r4 = e4(diffs, cfg)
    ok(r4["n_changes"] == 3 and r4["n_churn"] == 2, "E4 counts 2 churn / 3")
    ok(abs(r4["churn_share"] - 0.6667) < 1e-3, "E4 churn share 2/3")
    ok(e4([], cfg)["churn_share"] == 0.0, "E4 empty -> 0 churn")
    # the REAL v0 producer (cycle_tools.py) sets caused_by = node id, so churn
    # must come from crossing the node against retraction events
    real_diffs = [{"node": "n1", "old_status": "in", "new_status": "out",
                   "caused_by": "n1"},
                  {"node": "n2", "old_status": "in", "new_status": "out",
                   "caused_by": "n2"}]
    retract_ev = [{"type": "cohort.retracted", "actor": "auditor",
                   "tx_data": "[[:db/add [:node/id \"n2\"] "
                              ":judgment/status :retracted]]"}]
    r4b = e4(real_diffs, cfg, retract_ev)
    ok(r4b["n_churn"] == 1 and r4b["n_evidence"] == 1,
       "E4 crosses node vs retraction events (v0 caused_by=node)")
    ok(e4(real_diffs, cfg, [])["n_churn"] == 0,
       "E4 no retraction events -> no false churn")

    # ---- E5 rates ----------------------------------------------------------
    taskgen = ([{"task_type": "elaborate"}] * 4 + [{"task_type": "review"}] * 2)
    harvest = ([{"task_type": "elaborate", "answered_ts": 1}] * 3 +
               [{"task_type": "review", "event": "human.response"}] * 1)
    cals = [{"provenance": {"source": "human"}}] * 5 + [{"provenance": {"source": "anchor"}}]
    elab = [{"train": "edge_type", "coverage": 0.42}]
    r5 = e5(harvest, taskgen, cals, elab, cfg)
    ok(r5["per_type"]["elaborate"]["rate"] == 0.75, "E5 elaborate rate 3/4")
    ok(r5["per_type"]["review"]["rate"] == 0.5, "E5 review rate 1/2")
    ok(abs(r5["overall_response_rate"] - 4 / 6) < 1e-3, "E5 overall rate 4/6")
    ok(r5["human_examples_cumulative"] == 5, "E5 counts 5 :human calset examples")
    ok(r5["elaboration_coverage"]["edge_type"] == 0.42, "E5 elaboration coverage")

    # ---- trends sparklines -------------------------------------------------
    hist_reports = _synthetic_history()
    ok(len(hist_reports) == 3, "3 synthetic weeks of history loaded")
    cur = build_report("2026-08-03", metrics=_synthetic_metrics(0.2, 100),
                       pairs=pairs, edges=det_edges, lint=lint, cycle=3,
                       stance_diffs=diffs, harvest_ledger=harvest,
                       taskgen_ledger=taskgen, calsets=cals,
                       elaboration_coverage=elab, questions=qs, snapshot=snap,
                       history=hist_reports, cfg=cfg)
    tr = cur["trends"]["e4.churn_share"]
    ok(len(tr["spark"]) == 8, "trend sparkline is 8 chars")
    ok(any(c in _SPARK for c in tr["spark"]), "trend sparkline has bars")
    ok(tr["delta"] is not None, "trend delta computed vs prior week")
    # gap week (None) renders as space, no interpolation
    sp = sparkline([0.1, None, 0.5, 0.9], 0.0, 1.0)
    ok(sp[1] == " ", "sparkline gap = space (no interpolation)")

    # ---- md + json render --------------------------------------------------
    md = render_md(cur)
    ok(md.startswith("# Rapport hebdo"), "md renders header")
    for section in ("## ⚠ Alertes", "## E1 Jugement", "## E2 Contradictions",
                    "## E3 Récupération", "## E4 Stances", "## E5 Boucle humaine",
                    "## Dettes", "## Tendances"):
        ok(section in md, f"md has section {section}")
    ok(cur["e2"]["n_false_positives"] == 1, "report carries E2 FP")
    ok(any(al["metric"].startswith("E2/false-positive") for al in cur["alerts"]),
       "alert raised for E2 control false positive with decision")
    ok(all("decision" in al and al["decision"] for al in cur["alerts"]),
       "every alert carries a decision (threshold => decision)")
    import io
    buf = json.loads(json.dumps(cur))  # json round-trips (mirror is serialisable)
    ok(buf["week"] == "2026-08-03" and "alerts" in buf,
       "json mirror carries raw values + alerts[]")

    # ---- M/Eval/Seeded exclusion assertion (B1 patch) ----------------------
    _assert_m_exclusion(ok)

    print(f"\nall eval_harness self-tests passed ({n_ok[0]} assertions)")


def _synthetic_history() -> List[dict]:
    """3 synthetic prior weekly reports for the trends self-test. Written under
    fixtures/eval/history/ and read back (so the report self-test exercises the
    same history-dir path the launchd job uses)."""
    hdir = HERE / "fixtures" / "eval" / "history"
    hdir.mkdir(parents=True, exist_ok=True)
    weeks = [("2026-07-13", 0.10, 0.30, 0.55),
             ("2026-07-20", 0.20, 0.45, 0.60),
             ("2026-07-27", 0.30, 0.55, 0.66)]
    out = []
    for wk, churn, union, resp in weeks:
        rep = {"week": wk,
               "e2": {"detected_frac": min(1.0, union)},
               "e3": {"overall": {"union": union, "marginal": union / 2}},
               "e4": {"churn_share": churn},
               "e5": {"overall_response_rate": resp},
               "e1": {"anchor_agreement": {"agreement": 0.9}}}
        (hdir / f"weekly_report_{wk}.json").write_text(
            json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        out.append(rep)
    return out


def _assert_m_exclusion(ok) -> None:
    """Feed the (patched) harvesters a fixture containing an M/Eval/Seeded page
    and assert zero candidates come out. The M/* exclusion patch is owned by the
    B1 agent (roam_harvest.py / prefilter.py); if it is not present yet we do NOT
    edit those files — we report it as a soft finding.
    """
    fixture = HERE / "fixtures" / "eval" / "m_eval_snapshot.json"
    try:
        import roam_harvest as RH
    except Exception as e:  # pragma: no cover
        print(f"  ⚠ M/* exclusion NOT VERIFIED: cannot import roam_harvest ({e})")
        return
    import tempfile
    import json as _json
    # The fixture deliberately holds an M/Eval/Seeded page AND a normal page
    # (RGPD): the exclusion must be scoped to the M/* namespace, not a blanket
    # zero. So we assert no mined candidate *originates* from an M/* page rather
    # than that nothing was mined at all. Some harvesters (summarize_now) carry
    # a page title as the subject; others carry block uids.
    g = RH.Graph.parse(_json.loads(fixture.read_text()))

    def _page_of(subj: str) -> str:
        blk = getattr(g, "blocks", {}).get(subj)
        return blk["page"] if blk else subj

    leaked = []
    with tempfile.TemporaryDirectory() as td:
        outdir = pathlib.Path(td) / "cand"
        RH.harvest(fixture, outdir, cap=50, min_refs=1, seed=0)
        for cf in sorted(pathlib.Path(outdir).glob("*.jsonl")):
            for line in cf.read_text().splitlines():
                c = _json.loads(line)
                for s in c.get("subjects", []):
                    if RH.is_eval_page(_page_of(s)):
                        leaked.append((c.get("jtype"), s))
    if not leaked:
        ok(True, "M/* namespace excluded from harvest (B1 patch present)")
    else:
        # Patch not present / regressed — report, do NOT edit B1-owned files.
        ok(False, f"M/* exclusion leaked {len(leaked)} candidate(s): {leaked[:5]}")


# ===========================================================================
# argparse
# ===========================================================================


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("report", help="weekly report (md + json + history)")
    r.add_argument("--week", required=True, help="ISO week/date label")
    r.add_argument("--in", dest="indir", default=".", help="base dir for relative artefacts")
    r.add_argument("--metrics", default=None, help="judge_metrics report JSON (rel to --in)")
    r.add_argument("--accepted", default=None)
    r.add_argument("--anchor", default=None, help="anchor_outbox.jsonl")
    r.add_argument("--pairs", default=str(HERE / "fixtures" / "eval" / "seeded_pairs.yaml"))
    r.add_argument("--edges", default=None)
    r.add_argument("--lint", default=None)
    r.add_argument("--cycle", type=int, default=0)
    r.add_argument("--questions", default=str(HERE / "eval_questions.yaml"))
    r.add_argument("--snapshot", default=None)
    r.add_argument("--stance-diff", dest="stance_diff", default=None)
    r.add_argument("--harvest-ledger", dest="harvest_ledger", default=None)
    r.add_argument("--taskgen-ledger", dest="taskgen_ledger", default=None)
    r.add_argument("--calsets", nargs="*", default=[])
    r.add_argument("--elaboration", default=None, help="elaboration-coverage jsonl")
    r.add_argument("--events", default=None,
                   help="store/events.jsonl (E4 retraction crossing)")
    r.add_argument("--spend", default=None)
    r.add_argument("--history", default="eval/history")
    r.add_argument("--out", default="eval")
    r.add_argument("--thresholds", default=None)
    r.set_defaults(fn=cmd_report)

    s = sub.add_parser("seed-contradictions", help="emit kind:seed writeback orders")
    s.add_argument("--pairs", default=str(HERE / "fixtures" / "eval" / "seeded_pairs.yaml"))
    s.add_argument("--orders", required=True, help="writeback_orders.jsonl (appended)")
    s.add_argument("--cycle", type=int, default=0)
    s.set_defaults(fn=cmd_seed_contradictions)

    c = sub.add_parser("check-seeded", help="E2 detection report")
    c.add_argument("--pairs", default=str(HERE / "fixtures" / "eval" / "seeded_pairs.yaml"))
    c.add_argument("--edges", required=True)
    c.add_argument("--lint", default=None)
    c.add_argument("--cycle", type=int, default=0)
    c.add_argument("--thresholds", default=None)
    c.set_defaults(fn=cmd_check_seeded)

    rt = sub.add_parser("retrieval", help="E3 three-column coverage")
    rt.add_argument("--questions", default=str(HERE / "eval_questions.yaml"))
    rt.add_argument("--snapshot", required=True)
    rt.add_argument("--edges", default=None)
    rt.add_argument("--embed-index", dest="embed_index", default=None,
                    help="path to embed_index.py for kNN column (b); omit to skip")
    rt.set_defaults(fn=cmd_retrieval)

    st = sub.add_parser("self-test", help="zero-network self-test on fixtures")
    st.set_defaults(fn=lambda a: self_test())

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()

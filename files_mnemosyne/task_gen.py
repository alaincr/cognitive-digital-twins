#!/usr/bin/env python3
"""task_gen.py — B3 generator: consolidator causes -> human tasks (writeback).

Reads the cause files produced upstream and emits `kind: task` orders that B2
renders into Roam under `[[M/Tasks]]`. Four task types (PRD B3 §3):

  elaborate : a promoted `opposes` edge attacks a claim that still has IN
              supporters (cross `edges.jsonl` × `stances.jsonl`) OR a
              `contradiction` cause row. Owner writes 2–3 sentences.
  triage    : a fleeting note whose activation decayed (`triage.due` cause).
              Owner picks promote / keep / archive (closed tags).
  bridge    : an embedding-close cross-train pair with no short path
              (`bridge` / bridge_seeds cause). Owner picks related / unrelated.
  review    : a T2 / order-inconsistent item from anchor_label's
              `review_queue_<jtype>.md`. Owner tags the gold enum label.

Pure core (ANNEX_B3 §5):
  make_task(cause)        -> order-fields               (deterministic)
  prioritize(tasks, ...)  -> (kept, dropped)            (no silent caps)

Idempotency: `task-id = sha256(task_type + ctx_cause)` — keyed on the CAUSE,
not the rendered content (PRD M3; guarantees no re-fire after expiry unless the
cause re-triggers). The order's `idempotency_key` is that same task-id.

Anti-fatigue (PRD FR-4): a persisted `taskgen_state.json` halves the daily
budget when the trailing-7d response rate drops below 50%, and restores it
after 7 days back at ≥50%. State is read/written, never recomputed on the fly.

CLI:
  task_gen.py generate --causes $C/task_causes.jsonl \\
      --edges ops/edges.jsonl --stances $C/stances.jsonl \\
      --review-queues 'ops/first_judge/review_queue_*.md' \\
      --out-append $C/writeback_orders.jsonl --budget 5
  task_gen.py self-test

stdlib-only; imports judge_prompts + human_prompts (registry) read-only. Never
copies their tables (LABEL_DEFS / REQUIRED_FIELDS are imported).
"""

from __future__ import annotations
import argparse
import datetime as _dt
import glob
import hashlib
import json
import pathlib
import re
import sys
from typing import Dict, List, Optional, Tuple

import judge_prompts as JP
import human_prompts  # noqa: F401  registers bridge_related into JP

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TASKS_PAGE = "M/Tasks"
TASK_TEMPLATE = "task_v1"
DUE_OFFSET_DAYS = 2

# Stakes tier per task type -> priority weight (T2=3, T1=2, T0=1).
# Rationale: elaborate resolves a T2 edge_type contradiction (highest stakes);
# review inherits the tier of the reviewed jtype; triage gates a T1-ish
# stratum decision; bridge is a low-stakes recoverable link (T0).
_TIER_WEIGHT = {"t2": 3, "t1": 2, "t0": 1}

# jtype -> tier, mirrors judges.clj `stakes` (kept small & local; source of
# truth is Clojure, this is the read-side view for prioritisation only).
_JTYPE_TIER = {
    "edge_type": "t2", "same_entity": "t2", "faithful": "t2",
    "invalidate": "t1", "dedup_prop": "t1",
    "summarize_now": "t0", "propagate": "t0",
    # zettel / human types:
    "continues": "t1", "permanent_worthy": "t1", "bridge_related": "t0",
}

_TASK_TYPE_TIER = {
    "elaborate": "t2",   # attacks a T2 edge_type claim
    "triage": "t1",      # permanent_worthy stratum gate
    "bridge": "t0",      # recoverable link
    # review: resolved per-cause from the reviewed jtype
}

# Closed-choice tag vocabularies per task type (Roam tags the owner may add).
_TRIAGE_TAGS = ["promouvoir", "garder", "archiver"]
_BRIDGE_TAGS = ["related", "unrelated"]

# Default per-type budgets (PRD FR-4).
DEFAULT_BUDGETS = {"global": 5, "elaborate": 2, "triage": 1,
                   "bridge": 1, "review": 1}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

_ORDINAL = {1: "st", 2: "nd", 3: "rd"}


def roam_date(d: _dt.date) -> str:
    """Roam daily-note title, e.g. 'July 6th, 2026' (ordinal suffixes)."""
    day = d.day
    if 11 <= day % 100 <= 13:
        suf = "th"
    else:
        suf = _ORDINAL.get(day % 10, "th")
    return f"{d.strftime('%B')} {day}{suf}, {d.year}"


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def task_id_for(task_type: str, ctx_cause: str) -> str:
    """PRD/ANNEX: task-id = sha256(task_type + ctx_cause), prefixed sha256:."""
    return "sha256:" + sha256_hex(task_type + "\x00" + ctx_cause)


def _neutral(s: str, n: int = 120) -> str:
    """Collapse whitespace and truncate (question rendering is B2's job to
    escape; here we just keep the cited text short & single-line)."""
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------------------------------------------------------------------------
# Cause ctx keys (what makes a cause identical across cycles)
# ---------------------------------------------------------------------------

def _ctx_cause(cause: dict) -> str:
    """Stable serialization of the CAUSE identity (NOT the content). Two
    triggers of the same underlying situation must hash identically so the
    task is never duplicated and an expired task is only regenerated when the
    cause genuinely re-fires."""
    t = cause["cause"]
    if t in ("contradiction", "elaborate"):
        # a claim attacked by an opposer — identity is the (claim, opposer) pair
        return f"elaborate|{cause['claim']}|{cause['opposer']}"
    if t in ("triage.due", "triage"):
        return f"triage|{cause['uid']}"
    if t == "bridge":
        a, b = sorted((cause["a"], cause["b"]))
        return f"bridge|{a}|{b}"
    if t == "review":
        # identity is the exact judged context (content-addressed already)
        return f"review|{cause['jtype']}|{cause['context_hash']}"
    raise ValueError(f"unknown cause type: {t!r}")


def _task_type_of(cause: dict) -> str:
    t = cause["cause"]
    return {"contradiction": "elaborate", "elaborate": "elaborate",
            "triage.due": "triage", "triage": "triage",
            "bridge": "bridge", "review": "review"}[t]


# ---------------------------------------------------------------------------
# make_task — PURE: cause -> order-fields (task_v1)
# ---------------------------------------------------------------------------

def make_task(cause: dict, *, today: Optional[_dt.date] = None) -> dict:
    """Build ONE writeback order (kind=task) from a cause. Pure & deterministic.

    Returns the full order envelope per INTERFACES.md:
      {kind, idempotency_key, target:{page, under}, content:{template, fields},
       caused_by, meta}
    where content.fields carries everything B2's task_v1 renderer needs:
      question (French), task_type, task_id, due_hint, refs[], child_lines[].
    """
    today = today or _dt.date.today()
    ttype = _task_type_of(cause)
    ctx = _ctx_cause(cause)
    tid = task_id_for(ttype, ctx)
    due = roam_date(today + _dt.timedelta(days=DUE_OFFSET_DAYS))

    if ttype == "elaborate":
        claim, opposer = cause["claim"], cause["opposer"]
        claim_txt = _neutral(cause.get("claim_text", ""), 200)
        opp_txt = _neutral(cause.get("opposer_text", ""), 200)
        q = (f"Comment ((%s)) se tient-il face à ((%s)) qui le contredit ?"
             % (claim, opposer))
        if claim_txt or opp_txt:
            q += f" — claim : {claim_txt} / opposition : {opp_txt}"
        refs = [claim, opposer]
        child_lines = ["Réponse :"]
        route = {"claim": claim, "opposer": opposer}

    elif ttype == "triage":
        uid = cause["uid"]
        note = _neutral(cause.get("text", cause.get("note", "")), 120)
        act = cause.get("activation", "?")
        q = (f"Cette note fugace a décliné (activation {act}) : « {note} ». "
             f"Que faire de ((%s)) ?" % uid)
        refs = [uid]
        child_lines = ["Choix (un tag) : "
                       + " ".join("#" + t for t in _TRIAGE_TAGS)]
        route = {"uid": uid}

    elif ttype == "bridge":
        a, b = cause["a"], cause["b"]
        score = cause.get("score")
        q = (f"((%s)) et ((%s)) sont proches sémantiquement mais sans lien "
             f"établi. Sont-elles reliées ?" % (a, b))
        if score is not None:
            q += f" (proximité {score})"
        refs = [a, b]
        child_lines = ["Choix (un tag) : "
                       + " ".join("#" + t for t in _BRIDGE_TAGS)]
        route = {"a": a, "b": b}

    elif ttype == "review":
        jtype = cause["jtype"]
        fields = cause.get("fields", {})
        # Routing payload captured BEFORE `fields` is shadowed by the
        # order-fields dict below: the consolidator needs the ORIGINAL
        # candidate fields to write a well-formed calset row.
        route = {"jtype": jtype, "fields": dict(fields),
                 "context_hash": cause.get("context_hash")}
        # Render the candidate's REQUIRED_FIELDS (imported, never copied) so
        # the owner sees exactly what the judge saw.
        req = JP.REQUIRED_FIELDS.get(jtype, list(fields.keys()))
        rendered = " · ".join(f"{k}: {_neutral(fields.get(k, ''), 160)}"
                              for k in req if k in fields or fields.get(k))
        q = (f"Revue T2 [{jtype}] — quel est le label or ? {rendered}")
        refs = list(cause.get("subjects", []))
        # enum labels stay English (calset consistency); imported from JP.
        labels = list(JP.LABEL_DEFS.get(jtype, {}).keys())
        child_lines = ["Label or (un tag) : "
                       + " ".join("#" + l for l in labels)]

    else:  # pragma: no cover
        raise ValueError(ttype)

    fields = {
        "question": q,
        "task_type": ttype,
        "task_id": tid,
        "due_hint": due,
        "refs": refs,
        "child_lines": child_lines,
    }
    return {
        "kind": "task",
        "idempotency_key": tid,
        "target": {"page": TASKS_PAGE, "under": None},
        "content": {"template": TASK_TEMPLATE, "fields": fields},
        "caused_by": cause.get("event_id"),
        # `route` is the routing payload the consolidator needs to act on the
        # human answer (B3<->B4 seam). It travels: meta -> taskgen_ledger ->
        # task_harvest join by task_id -> outbox_human event -> route-human!.
        "meta": {"task_type": ttype, "ctx_cause": ctx, "route": route},
    }


# ---------------------------------------------------------------------------
# prioritize — PURE: priority = stakes × activation, budgeted, logs dropped
# ---------------------------------------------------------------------------

def _priority(order: dict, cause: dict) -> float:
    ttype = order["meta"]["task_type"]
    if ttype == "review":
        tier = _JTYPE_TIER.get(cause.get("jtype", ""), "t1")
    else:
        tier = _TASK_TYPE_TIER[ttype]
    stakes = _TIER_WEIGHT[tier]
    act = cause.get("activation")
    try:
        activation = float(act) if act is not None else 1.0
    except (TypeError, ValueError):
        activation = 1.0
    return stakes * activation


def prioritize(tasks: List[Tuple[dict, dict]], budgets: Dict[str, int],
               state: Optional[dict] = None
               ) -> Tuple[List[dict], List[dict]]:
    """Budgeted priority queue. `tasks` = list of (order, cause) pairs.

    priority = stakes(tier) × activation. Applies the anti-fatigue
    `budget_factor` from state to BOTH the global and per-type budgets
    (floored at 1 so a single high-value task can still get through). Anything
    cut is returned in `dropped` with its priority and reason — NO silent caps.

    Deduplicates by task-id first (same cause never yields two tasks, M3).
    Returns (kept_orders, dropped_records). Pure & deterministic (stable sort
    on (-priority, task_id)).
    """
    state = state or {}
    factor = float(state.get("budget_factor", 1.0))

    def eff(n: int) -> int:
        return max(1, int(round(n * factor))) if n > 0 else 0

    g_budget = eff(budgets.get("global", DEFAULT_BUDGETS["global"]))
    per_type = {tt: eff(budgets.get(tt, DEFAULT_BUDGETS.get(tt, 0)))
                for tt in ("elaborate", "triage", "bridge", "review")}

    # dedup by task-id, keep the first occurrence (deterministic input order)
    seen = set()
    scored = []
    for order, cause in tasks:
        tid = order["idempotency_key"]
        if tid in seen:
            continue
        seen.add(tid)
        scored.append((_priority(order, cause), order, cause))

    scored.sort(key=lambda x: (-x[0], x[1]["idempotency_key"]))

    kept: List[dict] = []
    dropped: List[dict] = []
    used_type: Dict[str, int] = {k: 0 for k in per_type}
    for prio, order, _cause in scored:
        tt = order["meta"]["task_type"]
        if len(kept) >= g_budget:
            reason = "global_budget"
        elif used_type.get(tt, 0) >= per_type.get(tt, 0):
            reason = f"type_budget:{tt}"
        else:
            kept.append(order)
            used_type[tt] = used_type.get(tt, 0) + 1
            continue
        dropped.append({"task_id": order["idempotency_key"], "task_type": tt,
                        "priority": prio, "reason": reason,
                        "ctx_cause": order["meta"]["ctx_cause"]})
    return kept, dropped


# ---------------------------------------------------------------------------
# CAUSES readers — turn upstream artifacts into cause dicts
# ---------------------------------------------------------------------------

def _read_jsonl(path: pathlib.Path) -> List[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip()]


def read_elaborate_causes(causes_path: pathlib.Path,
                          edges_path: Optional[pathlib.Path],
                          stances_path: Optional[pathlib.Path]) -> List[dict]:
    """`elaborate` causes.

    Primary source: `contradiction` rows already emitted by the consolidator
    into task_causes.jsonl. Secondary (fallback / enrichment): CROSS
    edges.jsonl `opposes` × stances.jsonl IN-supported `to` — derive the
    contradiction ourselves when the consolidator did not pre-emit it.
    """
    out: List[dict] = []
    seen_ctx = set()

    # Stances gate BOTH sources (ANNEX B3 §1.1: a contradiction task fires
    # only while the attacked claim still has IN standing). The consolidator
    # emits a contradiction row for EVERY opposes edge regardless of stance,
    # so the filter must live here. Without a stances file (first cycles,
    # belief not yet run) we keep everything and say so once on stderr.
    edges = _read_jsonl(edges_path) if edges_path else []
    stances = _read_jsonl(stances_path) if stances_path else []
    stance_by_node = {s["node"]: s for s in stances}
    if not stances:
        print("elaborate: no stances file — contradiction causes unfiltered",
              file=sys.stderr)

    for row in _read_jsonl(causes_path):
        if row.get("cause") == "contradiction":
            st = stance_by_node.get(row["claim"])
            if st is not None and st.get("label") != "in":
                continue  # claim already OUT/undec — nothing left to defend
            c = {"cause": "contradiction", "claim": row["claim"],
                 "opposer": row["opposer"], "event_id": row.get("event_id"),
                 "claim_text": row.get("claim_text", ""),
                 "opposer_text": row.get("opposer_text", "")}
            ctx = _ctx_cause(c)
            if ctx not in seen_ctx:
                seen_ctx.add(ctx)
                out.append(c)

    # derive from edges × stances (opposes toward an IN-supported claim)
    for e in edges:
        if e.get("edge_type") != "opposes":
            continue
        to = e.get("to")
        st = stance_by_node.get(to)
        if not st:
            continue
        # attacked claim must still have IN supporters (label == in)
        if st.get("label") != "in":
            continue
        c = {"cause": "contradiction", "claim": to, "opposer": e.get("from"),
             "event_id": e.get("edge_id"),
             "claim_text": "", "opposer_text": ""}
        ctx = _ctx_cause(c)
        if ctx not in seen_ctx:
            seen_ctx.add(ctx)
            out.append(c)
    return out


def read_triage_causes(causes_path: pathlib.Path) -> List[dict]:
    out = []
    for row in _read_jsonl(causes_path):
        if row.get("cause") == "triage.due":
            out.append({"cause": "triage.due", "uid": row["uid"],
                        "activation": row.get("activation"),
                        "text": row.get("text", row.get("note", "")),
                        "event_id": row.get("event_id")})
    return out


def read_bridge_causes(causes_path: pathlib.Path,
                       seeds_path: Optional[pathlib.Path] = None) -> List[dict]:
    """`bridge` causes: from task_causes rows AND/OR raw bridge_seeds.jsonl.

    Fails closed when B5 is absent (no seeds, no cause rows -> empty list).
    """
    out, seen = [], set()
    for row in _read_jsonl(causes_path):
        if row.get("cause") == "bridge":
            a, b = row["a"], row["b"]
            key = tuple(sorted((a, b)))
            if key in seen:
                continue
            seen.add(key)
            out.append({"cause": "bridge", "a": a, "b": b,
                        "score": row.get("score"),
                        "event_id": row.get("event_id")})
    if seeds_path:
        for row in _read_jsonl(seeds_path):
            a, b = row["a"], row["b"]
            key = tuple(sorted((a, b)))
            if key in seen:
                continue
            seen.add(key)
            out.append({"cause": "bridge", "a": a, "b": b,
                        "score": row.get("score"),
                        "event_id": row.get("cycle")})
    return out


# review queue markdown parsing --------------------------------------------

_RQ_ITEM = re.compile(r"^###\s+\d+\.\s+`([^`]+)`\s+—\s+(.+)$")
_RQ_SUBJECTS = re.compile(r"^-\s+subjects:\s+`(.+)`\s*$")
_RQ_FIELD = re.compile(r"^\s{2}-\s+\*\*([a-z0-9_]+)\*\*:\s+(.*)$")


def parse_review_queue(md_text: str, jtype_hint: Optional[str] = None
                       ) -> List[dict]:
    """Parse `review_queue_<jtype>.md` (anchor_label.render_review_item format).

    Each `### i. \\`jtype\\` — reason` block yields a `review` cause carrying
    the candidate fields (mirroring REQUIRED_FIELDS[jtype]) and subjects. We
    content-address the fields to get a stable `context_hash` for idempotency
    (same context_hash convention as the harness).
    """
    out: List[dict] = []
    cur: Optional[dict] = None

    def flush():
        if cur and cur["fields"]:
            jt = cur["jtype"]
            cur["context_hash"] = JP.context_hash(jt, 1, cur["fields"])
            out.append(cur)

    for line in md_text.splitlines():
        m = _RQ_ITEM.match(line)
        if m:
            flush()
            cur = {"cause": "review", "jtype": m.group(1).strip(),
                   "reason": m.group(2).strip(), "subjects": [],
                   "fields": {}, "event_id": None}
            continue
        if cur is None:
            continue
        ms = _RQ_SUBJECTS.match(line)
        if ms:
            raw = ms.group(1)
            cur["subjects"] = re.findall(r"[A-Za-z0-9_-]{4,}", raw)
            continue
        mf = _RQ_FIELD.match(line)
        if mf:
            cur["fields"][mf.group(1)] = mf.group(2).strip()
    flush()
    return out


def read_review_causes(patterns: List[str]) -> List[dict]:
    out = []
    for pat in patterns:
        for path in sorted(glob.glob(pat)):
            p = pathlib.Path(path)
            jt = None
            m = re.search(r"review_queue_([a-z0-9_]+)\.md$", p.name)
            if m:
                jt = m.group(1)
            out.extend(parse_review_queue(p.read_text(encoding="utf-8"), jt))
    return out


# ---------------------------------------------------------------------------
# State + ledger (anti-fatigue is persisted, not recomputed)
# ---------------------------------------------------------------------------

def load_state(path: pathlib.Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"budget_factor": 1.0, "since": None}


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def append_ledger(path: pathlib.Path, orders: List[dict], cycle: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for o in orders:
            f.write(json.dumps(
                {"task_id": o["idempotency_key"],
                 "task_type": o["meta"]["task_type"],
                 "ctx_cause": o["meta"]["ctx_cause"],
                 # routing payload for the harvest->consolidator join
                 "route": o["meta"].get("route", {}),
                 "generated_ts": _now_iso(), "cycle": cycle},
                ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------

def gather_causes(args) -> List[dict]:
    causes_path = pathlib.Path(args.causes) if args.causes else pathlib.Path(
        "/dev/null")
    edges = pathlib.Path(args.edges) if args.edges else None
    stances = pathlib.Path(args.stances) if args.stances else None
    seeds = pathlib.Path(args.bridge_seeds) if args.bridge_seeds else None

    causes: List[dict] = []
    causes += read_elaborate_causes(causes_path, edges, stances)
    causes += read_triage_causes(causes_path)
    causes += read_bridge_causes(causes_path, seeds)
    causes += read_review_causes(args.review_queues or [])
    return causes


def generate(args) -> dict:
    today = (_dt.date.fromisoformat(args.today) if args.today
             else _dt.date.today())
    causes = gather_causes(args)

    pairs = [(make_task(c, today=today), c) for c in causes]
    budgets = dict(DEFAULT_BUDGETS)
    if args.budget is not None:
        budgets["global"] = args.budget

    state = load_state(pathlib.Path(args.state)) if args.state else {}
    kept, dropped = prioritize(pairs, budgets, state)

    for d in dropped:
        print(f"drop {d['task_type']} {d['task_id'][:16]} "
              f"prio={d['priority']:.2f} reason={d['reason']}", file=sys.stderr)

    out = pathlib.Path(args.out_append)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as f:
        for o in kept:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")

    cycle = args.cycle or _now_iso()
    if args.ledger:
        append_ledger(pathlib.Path(args.ledger), kept, cycle)

    summary = {"causes": len(causes), "kept": len(kept),
               "dropped": len(dropped),
               "budget_factor": float((state or {}).get("budget_factor", 1.0))}
    print(json.dumps(summary, ensure_ascii=False))
    return summary


# ---------------------------------------------------------------------------
# self-test (pure; zero network)
# ---------------------------------------------------------------------------

def _self_test() -> None:
    ok = lambda c, m: (print(f"  ✓ {m}") if c else
                       (_ for _ in ()).throw(AssertionError(m)))
    today = _dt.date(2026, 7, 4)

    # roam_date ordinals
    ok(roam_date(_dt.date(2026, 7, 1)) == "July 1st, 2026", "1st")
    ok(roam_date(_dt.date(2026, 7, 2)) == "July 2nd, 2026", "2nd")
    ok(roam_date(_dt.date(2026, 7, 3)) == "July 3rd, 2026", "3rd")
    ok(roam_date(_dt.date(2026, 7, 11)) == "July 11th, 2026", "11th")
    ok(roam_date(_dt.date(2026, 7, 21)) == "July 21st, 2026", "21st")

    # --- make_task: elaborate --------------------------------------------
    ce = {"cause": "contradiction", "claim": "uidClaim1",
          "opposer": "uidEvid2", "event_id": "sha256:e1",
          "claim_text": "Le dossier est conforme.",
          "opposer_text": "La clause d'audit manque."}
    oe = make_task(ce, today=today)
    ok(oe["kind"] == "task", "elaborate order kind=task")
    ok(oe["content"]["template"] == "task_v1", "template task_v1")
    ok(oe["content"]["fields"]["task_type"] == "elaborate", "type elaborate")
    ok("Comment ((uidClaim1))" in oe["content"]["fields"]["question"],
       "elaborate question refs claim (French)")
    ok(oe["content"]["fields"]["due_hint"] == "July 6th, 2026", "due +2d")
    ok(oe["content"]["fields"]["refs"] == ["uidClaim1", "uidEvid2"],
       "elaborate refs = [claim, opposer] (directional, not inverted)")
    ok(oe["content"]["fields"]["child_lines"] == ["Réponse :"],
       "elaborate child is free-text 'Réponse :'")
    ok(oe["idempotency_key"].startswith("sha256:"), "task-id prefixed")

    # task-id keyed on CAUSE not content: changing claim_text keeps id
    ce2 = dict(ce, claim_text="totally different wording")
    ok(make_task(ce2, today=today)["idempotency_key"] == oe["idempotency_key"],
       "task-id keyed on cause, invariant to content text")
    # changing the opposer changes the id
    ce3 = dict(ce, opposer="uidOther")
    ok(make_task(ce3, today=today)["idempotency_key"] != oe["idempotency_key"],
       "task-id changes when the cause identity changes")

    # --- make_task: triage (closed tags, no free text) -------------------
    ct = {"cause": "triage.due", "uid": "uidNote9", "activation": 0.31,
          "text": "Idée fugace sur le graphe.", "event_id": "sha256:t1"}
    otr = make_task(ct, today=today)
    ok(otr["content"]["fields"]["task_type"] == "triage", "type triage")
    cl = otr["content"]["fields"]["child_lines"][0]
    ok(all(("#" + t) in cl for t in ("promouvoir", "garder", "archiver")),
       "triage lists the 3 closed tags")
    ok("Réponse :" not in cl, "triage does not ask for free text (closed only)")
    ok(otr["content"]["fields"]["refs"] == ["uidNote9"], "triage single ref")

    # --- make_task: bridge (uses human_prompts.bridge_related labels) ----
    cb = {"cause": "bridge", "a": "uidB", "b": "uidA", "score": 0.87,
          "event_id": "sha256:b1"}
    ob = make_task(cb, today=today)
    ok(ob["content"]["fields"]["task_type"] == "bridge", "type bridge")
    clb = ob["content"]["fields"]["child_lines"][0]
    ok("#related" in clb and "#unrelated" in clb, "bridge lists related/unrelated")
    # bridge cause identity is order-independent (a,b sorted)
    cb2 = {"cause": "bridge", "a": "uidA", "b": "uidB", "score": 0.5,
           "event_id": "x"}
    ok(make_task(cb2, today=today)["idempotency_key"] == ob["idempotency_key"],
       "bridge task-id is symmetric in (a,b)")

    # --- make_task: review (imports JP.LABEL_DEFS, enum labels English) ---
    cr = {"cause": "review", "jtype": "edge_type",
          "fields": {"evidence": "e", "claim": "c",
                     "sibling_evidence": "(none)"},
          "subjects": ["uidE", "uidC"], "context_hash": "abc123"}
    orv = make_task(cr, today=today)
    ok(orv["content"]["fields"]["task_type"] == "review", "type review")
    clr = orv["content"]["fields"]["child_lines"][0]
    for lab in JP.LABEL_DEFS["edge_type"]:
        ok(("#" + lab) in clr, f"review lists enum label #{lab}")
    ok("evidence:" in orv["content"]["fields"]["question"],
       "review renders REQUIRED_FIELDS in the question")

    # --- route payload (B3<->B4 seam): meta.route carries what the
    # consolidator needs to act on the answer -----------------------------
    ok(oe["meta"]["route"] == {"claim": "uidClaim1", "opposer": "uidEvid2"},
       "elaborate route = {claim, opposer}")
    ok(otr["meta"]["route"] == {"uid": "uidNote9"}, "triage route = {uid}")
    ok(ob["meta"]["route"] == {"a": "uidB", "b": "uidA"},
       "bridge route = {a, b}")
    ok(orv["meta"]["route"]["jtype"] == "edge_type"
       and orv["meta"]["route"]["fields"]["claim"] == "c"
       and orv["meta"]["route"]["context_hash"] == "abc123",
       "review route carries jtype + ORIGINAL fields + context_hash")

    # --- stance filter on consolidator-emitted contradiction causes ------
    import tempfile as _tf
    with _tf.TemporaryDirectory() as _td:
        _causes = pathlib.Path(_td) / "task_causes.jsonl"
        _causes.write_text(
            json.dumps({"cause": "contradiction", "claim": "cIN",
                        "opposer": "o1", "event_id": "e1"}) + "\n" +
            json.dumps({"cause": "contradiction", "claim": "cOUT",
                        "opposer": "o2", "event_id": "e2"}) + "\n",
            encoding="utf-8")
        _stances = pathlib.Path(_td) / "stances.jsonl"
        _stances.write_text(
            json.dumps({"node": "cIN", "label": "in",
                        "status": "accepted-supported"}) + "\n" +
            json.dumps({"node": "cOUT", "label": "out",
                        "status": "rejected"}) + "\n", encoding="utf-8")
        got = read_elaborate_causes(_causes, None, _stances)
        ok([c["claim"] for c in got] == ["cIN"],
           "contradiction causes filtered: OUT claim dropped, IN kept")
        got_nofilter = read_elaborate_causes(_causes, None, None)
        ok({c["claim"] for c in got_nofilter} == {"cIN", "cOUT"},
           "no stances file -> unfiltered (first cycles)")

    # --- prioritize: stakes×activation, budgets, no silent caps ----------
    tasks = [(oe, ce), (otr, ct), (ob, cb), (orv, cr)]
    kept, dropped = prioritize(tasks, DEFAULT_BUDGETS, {"budget_factor": 1.0})
    ok(len(kept) == 4 and dropped == [], "all 4 fit under default budgets")

    # tight global budget of 1 keeps the highest-priority (elaborate/review T2)
    kept1, dropped1 = prioritize(tasks, {"global": 1, "elaborate": 2,
                                         "triage": 1, "bridge": 1, "review": 1},
                                 {"budget_factor": 1.0})
    ok(len(kept1) == 1, "global budget=1 keeps exactly one")
    ok(len(dropped1) == 3 and all("reason" in d for d in dropped1),
       "dropped are logged with reasons (no silent caps)")
    ok(kept1[0]["meta"]["task_type"] in ("elaborate", "review"),
       "highest-stakes (T2) task kept under tight budget")

    # per-type budget: two elaborate causes, budget 1 -> one dropped by type
    ce_b = {"cause": "contradiction", "claim": "cX", "opposer": "oX",
            "event_id": "e2"}
    ob_e2 = make_task(ce_b, today=today)
    kept2, dropped2 = prioritize([(oe, ce), (ob_e2, ce_b)],
                                 {"global": 5, "elaborate": 1, "triage": 1,
                                  "bridge": 1, "review": 1},
                                 {"budget_factor": 1.0})
    ok(len(kept2) == 1 and dropped2[0]["reason"] == "type_budget:elaborate",
       "per-type elaborate budget enforced")

    # dedup by task-id: same cause twice -> one task
    keptd, _ = prioritize([(oe, ce), (make_task(ce, today=today), ce)],
                          DEFAULT_BUDGETS, {})
    ok(len(keptd) == 1, "duplicate cause -> single task (M3)")

    # anti-fatigue: budget_factor 0.5 halves budgets (floored at 1)
    many = [(make_task({"cause": "triage.due", "uid": f"u{i}",
                        "activation": 1.0, "event_id": f"e{i}"}, today=today),
             {"cause": "triage.due", "uid": f"u{i}", "activation": 1.0})
            for i in range(4)]
    keptf, _ = prioritize(many, {"global": 4, "triage": 4, "elaborate": 2,
                                 "bridge": 1, "review": 1},
                          {"budget_factor": 0.5})
    ok(len(keptf) == 2, "budget_factor 0.5 halves global budget (4->2)")

    # --- review queue parsing --------------------------------------------
    md = (
        "# Review queue — edge_type (1 items, ts)\n\n"
        "### 1. `edge_type` — order-inconsistent\n"
        "- subjects: `['uidE1', 'uidC1']`\n"
        "  - **evidence**: La clause manque\n"
        "  - **claim**: Le dossier est conforme\n"
        "  - **sibling_evidence**: (none)\n"
        "- anchor verdicts:\n"
        "  - pass 1: `supports` (hard) — x\n"
        "- [ ] human gold: ______\n")
    parsed = parse_review_queue(md, "edge_type")
    ok(len(parsed) == 1, "review queue: one item parsed")
    ok(parsed[0]["jtype"] == "edge_type", "review queue jtype")
    ok(parsed[0]["fields"]["evidence"] == "La clause manque",
       "review queue field extracted")
    ok(parsed[0]["subjects"] == ["uidE1", "uidC1"], "review queue subjects")
    ok(parsed[0]["context_hash"] == JP.context_hash(
        "edge_type", 1, parsed[0]["fields"]), "review queue context-addressed")

    # --- read_elaborate_causes: derive from edges × stances --------------
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        d = pathlib.Path(td)
        (d / "causes.jsonl").write_text(
            json.dumps({"cause": "triage.due", "uid": "n1",
                        "activation": 0.2, "event_id": "e"}) + "\n")
        (d / "edges.jsonl").write_text(
            json.dumps({"edge_id": "o1->c1#opposes", "edge_type": "opposes",
                        "from": "o1", "to": "c1"}) + "\n" +
            json.dumps({"edge_id": "s1->c1#supports", "edge_type": "supports",
                        "from": "s1", "to": "c1"}) + "\n")
        (d / "stances.jsonl").write_text(
            json.dumps({"node": "c1", "label": "in",
                        "status": "accepted-supported"}) + "\n")
        el = read_elaborate_causes(d / "causes.jsonl", d / "edges.jsonl",
                                   d / "stances.jsonl")
        ok(len(el) == 1 and el[0]["claim"] == "c1" and el[0]["opposer"] == "o1",
           "elaborate derived from opposes edge toward IN-supported claim")

        # OUT-labelled claim -> no elaborate task (not a live contradiction)
        (d / "stances2.jsonl").write_text(
            json.dumps({"node": "c1", "label": "out"}) + "\n")
        ok(read_elaborate_causes(d / "causes.jsonl", d / "edges.jsonl",
                                 d / "stances2.jsonl") == [],
           "no elaborate when attacked claim is OUT")

    print("all task_gen self-tests passed")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate")
    g.add_argument("--causes", help="task_causes.jsonl from ingest.clj")
    g.add_argument("--edges", help="edges.jsonl (opposes derivation)")
    g.add_argument("--stances", help="stances.jsonl (IN-support check)")
    g.add_argument("--bridge-seeds", help="bridge_seeds.jsonl from B5 (optional)")
    g.add_argument("--review-queues", nargs="*", default=[],
                   help="glob(s) for review_queue_<jtype>.md")
    g.add_argument("--out-append", required=True,
                   help="writeback_orders.jsonl (appended, never truncated)")
    g.add_argument("--budget", type=int, default=None, help="global max_tasks")
    g.add_argument("--state", help="taskgen_state.json (anti-fatigue)")
    g.add_argument("--ledger", help="taskgen_ledger.jsonl")
    g.add_argument("--cycle", help="cycle id (default: now)")
    g.add_argument("--today", help="ISO date override (tests / replay)")

    sub.add_parser("self-test")

    args = ap.parse_args()
    if args.cmd == "self-test":
        _self_test()
    elif args.cmd == "generate":
        generate(args)


if __name__ == "__main__":
    main()

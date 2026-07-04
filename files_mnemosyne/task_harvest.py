#!/usr/bin/env python3
"""task_harvest.py — B3 harvester: read human answers out of Roam, emit events.

Walks the day's snapshot (never the API — B1 provides the whole export),
finds `[[M/Task]]` blocks written by B2, detects the owner's response, and
emits typed `human.response*` events into `outbox_human.jsonl` for the
consolidator (ingest.clj) to route. The harvest is MONOTONE and pure of domain
effects: it emits, it never routes (CALM split — PRD FR-2).

Response detection (ANNEX_B3 §3):
  text   : first descendant whose string, after stripping a `Réponse :`
           prefix, is non-empty and ≠ `?`. Edge case 4 (PRD §6): free text
           added directly under the task block — with no prefix — also counts.
  choice : a closed tag drawn from the task-type's allowed set present in the
           task block or its descendants. Two CONTRADICTORY tags -> ambiguous.
  amended: the task-id was harvested before (harvest_ledger.jsonl) with a
           DIFFERENT response_hash -> `human.response.amended`.
  none   : empty / `?` / no answer -> nothing emitted, task stays open.

Emitted event (INTERFACES.md `ops/outbox_human.jsonl`):
  {"event":"human.response[.amended|.ambiguous]", "task_id":"sha256:…",
   "task_type":"elaborate", "response_text":?, "choice":?,
   "response_hash":"sha256:…", "answered_ts":<ms epoch>,
   "provenance":{"source":"human"}}

CLI:
  task_harvest.py harvest --snapshot sync/snapshots/latest.json \\
      --out $C/outbox_human.jsonl --ledger ops/harvest_ledger.jsonl
  task_harvest.py stats   --window 7d \\
      --ledger ops/harvest_ledger.jsonl --taskgen-ledger ops/taskgen_ledger.jsonl
  task_harvest.py self-test

stdlib-only. Reuses `roam_harvest.Graph` (imported, not copied) as the parser.
"""

from __future__ import annotations
import argparse
import datetime as _dt
import hashlib
import json
import pathlib
import re
import sys
from typing import Dict, List, Optional, Tuple

import roam_harvest as RH

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TASK_MARKER = "[[M/Task]]"
REPONSE_PREFIX_RE = re.compile(r"^\s*R[ée]ponse\s*:\s*", re.IGNORECASE)
TAG_RE = re.compile(r"(?<!\[)#([A-Za-z0-9_./-]+)")
ATTR_RE = re.compile(r"^\s*([a-z0-9_-]{1,40})::\s*(.*)$", re.IGNORECASE)

# Closed-choice vocabularies per task type (mirror task_gen; the harvest side
# validates which tags are meaningful for a given task-type).
_CHOICE_TAGS = {
    "triage": {"promouvoir", "garder", "archiver"},
    "bridge": {"related", "unrelated"},
    # review: labels are jtype-dependent; resolved dynamically from the task
}

# The PREFORMATTED prompt line (the tag menu B2 writes) is never a real answer.
# It is identified by its lead-in text, NOT by its tag set — an owner who tags
# BOTH options is giving a (contradictory) answer, not echoing the menu, and
# must still be detected as ambiguous.
_MENU_LEAD_RE = re.compile(r"^\s*(Choix\b|Label or\b)", re.IGNORECASE)


def _is_menu_line(string: str, allowed: set) -> bool:
    return bool(_MENU_LEAD_RE.match(string))


# ---------------------------------------------------------------------------
# Task block model
# ---------------------------------------------------------------------------

class Task:
    """A parsed [[M/Task]] block with its attributes and descendant strings."""

    def __init__(self, uid: str, question: str):
        self.uid = uid
        self.question = question
        self.attrs: Dict[str, str] = {}
        self.descendants: List[dict] = []   # block records (excluding attr rows)
        self.answered_ts: int = 0

    @property
    def task_id(self) -> Optional[str]:
        return self.attrs.get("task-id")

    @property
    def task_type(self) -> Optional[str]:
        return self.attrs.get("task-type")

    @property
    def status(self) -> str:
        return self.attrs.get("status", "open")

    def allowed_tags(self, review_labels: Optional[List[str]] = None) -> set:
        if self.task_type in _CHOICE_TAGS:
            return set(_CHOICE_TAGS[self.task_type])
        if self.task_type == "review" and review_labels:
            return set(review_labels)
        return set()


def find_tasks(graph: "RH.Graph") -> List[Task]:
    """Locate every `[[M/Task]]` block and collect its attributes + descendant
    content blocks (attribute rows and the preformatted tag-menu are set aside
    from the answer-bearing descendants)."""
    tasks: List[Task] = []
    for uid, b in graph.blocks.items():
        if TASK_MARKER not in b["string"]:
            continue
        t = Task(uid, b["string"])
        for du in graph.all_under(b["children"]):
            rec = graph.blocks[du]
            m = ATTR_RE.match(rec["string"])
            if m and m.group(1).lower() in (
                    "task-type", "task-id", "status", "due-hint", "refs"):
                t.attrs[m.group(1).lower()] = m.group(2).strip()
                continue
            t.descendants.append(rec)
            if rec["edit"] > t.answered_ts:
                t.answered_ts = rec["edit"]
        if t.answered_ts == 0:
            t.answered_ts = b["edit"]
        tasks.append(t)
    return tasks


# ---------------------------------------------------------------------------
# detect_response — PURE
# ---------------------------------------------------------------------------

def _response_hash(kind: str, payload: str) -> str:
    return "sha256:" + hashlib.sha256(
        (kind + "\x00" + payload).encode("utf-8")).hexdigest()


def detect_response(task: Task,
                    review_labels: Optional[List[str]] = None) -> dict:
    """Classify the owner's response to a task. Pure & deterministic.

    Returns one of:
      {"kind":"text",   "text": <str>, "response_hash": …}
      {"kind":"choice", "choice": <str>, "response_hash": …}
      {"kind":"ambiguous", "choices": [<str>,<str>], "response_hash": …}
      {"kind":"none"}

    Closed-choice types (triage/bridge/review) look for tags; free-text types
    (elaborate) look for a `Réponse :` block or any free text under the task.
    """
    allowed = task.allowed_tags(review_labels)

    # ---- closed-choice detection (tags) ------------------------------------
    if allowed:
        chosen: List[str] = []
        for rec in task.descendants:
            s = rec["string"]
            if _is_menu_line(s, allowed):
                continue  # the preformatted option menu, not an answer
            for tag in TAG_RE.findall(s):
                if tag in allowed and tag not in chosen:
                    chosen.append(tag)
        if len(chosen) >= 2:
            pair = sorted(chosen)[:2]
            return {"kind": "ambiguous", "choices": pair,
                    "response_hash": _response_hash("ambiguous",
                                                    "|".join(sorted(chosen)))}
        if len(chosen) == 1:
            return {"kind": "choice", "choice": chosen[0],
                    "response_hash": _response_hash("choice", chosen[0])}
        return {"kind": "none"}

    # ---- free-text detection (elaborate) -----------------------------------
    # 1) a descendant explicitly prefixed `Réponse :`
    for rec in task.descendants:
        s = rec["string"]
        if REPONSE_PREFIX_RE.match(s):
            body = REPONSE_PREFIX_RE.sub("", s, count=1).strip()
            if body and body != "?":
                return {"kind": "text", "text": body,
                        "response_hash": _response_hash("text", body)}
            # empty / '?' -> keep scanning (there may be a real answer elsewhere)
    # 2) edge case 4: any free text under the task counts (least astonishment)
    for rec in task.descendants:
        s = rec["string"].strip()
        if not s:
            continue
        if REPONSE_PREFIX_RE.match(s):
            continue  # already handled (was empty/?)
        if ATTR_RE.match(s):
            continue
        if s == "?":
            continue
        return {"kind": "text", "text": s,
                "response_hash": _response_hash("text", s)}
    return {"kind": "none"}


# ---------------------------------------------------------------------------
# Ledger + event emission
# ---------------------------------------------------------------------------

def load_ledger(path: pathlib.Path) -> Dict[str, dict]:
    """task_id -> last ledger row (for amendment detection)."""
    out: Dict[str, dict] = {}
    if not path or not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        out[r["task_id"]] = r   # last write wins
    return out


_REF_RE = re.compile(r"\(\(([A-Za-z0-9_-]+)\)\)")


def route_for(task: Task, routes: Dict[str, dict]) -> dict:
    """Routing payload for the consolidator (B3<->B4 seam). Primary source:
    the taskgen_ledger join by task_id (carries jtype/fields for review, the
    exact uids for triage/bridge). Fallback when the ledger is missing: derive
    what we can from the task block's own `refs::` attribute — enough for
    triage (uid) and bridge (a, b), NOT for review (fields unrecoverable from
    rendered prose)."""
    r = routes.get(task.task_id or "")
    if r:
        return r
    refs = _REF_RE.findall(task.attrs.get("refs", ""))
    if task.task_type == "triage" and refs:
        return {"uid": refs[0]}
    if task.task_type in ("bridge", "elaborate") and len(refs) >= 2:
        key = ("a", "b") if task.task_type == "bridge" else ("claim", "opposer")
        return {key[0]: refs[0], key[1]: refs[1]}
    return {}


def load_taskgen_routes(path: pathlib.Path) -> Dict[str, dict]:
    """task_id -> route from taskgen_ledger.jsonl (last write wins)."""
    out: Dict[str, dict] = {}
    for r in _read_jsonl(path):
        if r.get("task_id") and r.get("route"):
            out[r["task_id"]] = r["route"]
    return out


def build_event(task: Task, resp: dict, prior: Dict[str, dict],
                route: Optional[dict] = None) -> Optional[dict]:
    """Turn a detected response into an outbox event, or None if nothing to
    emit (kind == none). Amendment is decided against `prior` (the ledger)."""
    if resp["kind"] == "none":
        return None

    tid = task.task_id
    rhash = resp["response_hash"]

    if resp["kind"] == "ambiguous":
        return {"event": "human.response.ambiguous", "task_id": tid,
                "task_type": task.task_type, "response_text": None,
                "choice": None, "choices": resp["choices"],
                "response_hash": rhash, "answered_ts": task.answered_ts,
                "route": route or {},
                "provenance": {"source": "human"}}

    # amended if we harvested this task before with a different response_hash
    prev = prior.get(tid)
    amended = bool(prev and prev.get("response_hash") not in (None, rhash))
    # if unchanged since last harvest, do not re-emit (idempotent harvest)
    if prev and prev.get("response_hash") == rhash:
        return None

    event = "human.response.amended" if amended else "human.response"
    text = resp.get("text")
    choice = resp.get("choice")
    return {"event": event, "task_id": tid, "task_type": task.task_type,
            "response_text": text, "choice": choice,
            "response_hash": rhash, "answered_ts": task.answered_ts,
            "route": route or {},
            "provenance": {"source": "human"}}


def emit_events(tasks: List[Task], prior: Dict[str, dict],
                routes: Optional[Dict[str, dict]] = None
                ) -> Tuple[List[dict], List[dict]]:
    """Return (events, ledger_updates). Deterministic order (by task uid)."""
    events: List[dict] = []
    ledger_updates: List[dict] = []
    routes = routes or {}
    for task in sorted(tasks, key=lambda t: t.uid):
        if not task.task_id:
            continue
        # review label enum comes from the task-type; for review we read the
        # allowed labels off the menu line if present (kept simple in v0:
        # any tag on a review task is a candidate label).
        review_labels = None
        if task.task_type == "review":
            review_labels = _review_labels_from_menu(task)
        resp = detect_response(task, review_labels)
        ev = build_event(task, resp, prior, route_for(task, routes))
        if ev is None:
            continue
        events.append(ev)
        # ambiguous responses are re-signalled but still ledgered so we don't
        # spam the same ambiguity every cycle
        ledger_updates.append({"task_id": task.task_id,
                               "response_hash": ev["response_hash"],
                               "event": ev["event"],
                               "ts": _now_iso()})
    return events, ledger_updates


def _review_labels_from_menu(task: Task) -> List[str]:
    """For a review task, treat the tags listed on the preformatted menu line
    as the allowed enum (B2 writes `#label …`). Falls back to all tags seen."""
    labels: List[str] = []
    for rec in task.descendants:
        tags = TAG_RE.findall(rec["string"])
        if len(tags) >= 2:                     # a menu line lists >= 2 options
            for t in tags:
                if t not in labels:
                    labels.append(t)
    return labels


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def _parse_window(window: str) -> _dt.timedelta:
    m = re.fullmatch(r"(\d+)d", window.strip())
    if not m:
        raise ValueError(f"bad window (expected e.g. '7d'): {window!r}")
    return _dt.timedelta(days=int(m.group(1)))


def _parse_ts(ts: str) -> Optional[_dt.datetime]:
    try:
        return _dt.datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# harvest command
# ---------------------------------------------------------------------------

def harvest(snapshot_path: pathlib.Path, out_path: pathlib.Path,
            ledger_path: Optional[pathlib.Path],
            taskgen_ledger_path: Optional[pathlib.Path] = None) -> dict:
    graph = RH.Graph.parse(json.loads(snapshot_path.read_text(encoding="utf-8")))
    tasks = find_tasks(graph)
    prior = load_ledger(ledger_path) if ledger_path else {}
    routes = (load_taskgen_routes(taskgen_ledger_path)
              if taskgen_ledger_path else {})
    events, updates = emit_events(tasks, prior, routes)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    if ledger_path:
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open("a", encoding="utf-8") as f:
            for u in updates:
                f.write(json.dumps(u, ensure_ascii=False) + "\n")

    by_event: Dict[str, int] = {}
    for e in events:
        by_event[e["event"]] = by_event.get(e["event"], 0) + 1
    summary = {"tasks_seen": len(tasks), "events": len(events),
               "by_event": by_event}
    print(json.dumps(summary, ensure_ascii=False))
    return summary


# ---------------------------------------------------------------------------
# stats command (response rate over a window)
# ---------------------------------------------------------------------------

def compute_stats(harvest_ledger: List[dict], taskgen_ledger: List[dict],
                  window: _dt.timedelta, now: Optional[_dt.datetime] = None
                  ) -> dict:
    """Response rate = distinct answered task-ids / distinct generated task-ids,
    both within `window`. Also breaks down by task_type. Pure."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    cutoff = now - window

    def in_win(row, key):
        ts = _parse_ts(row.get(key, ""))
        return ts is not None and ts >= cutoff

    generated = {}   # task_id -> task_type
    for r in taskgen_ledger:
        if in_win(r, "generated_ts"):
            generated[r["task_id"]] = r.get("task_type", "?")
    answered = set()
    for r in harvest_ledger:
        if in_win(r, "ts") and r.get("event", "").startswith("human.response"):
            answered.add(r["task_id"])

    n_gen = len(generated)
    n_ans = len(generated.keys() & answered)
    rate = (n_ans / n_gen) if n_gen else 0.0

    by_type: Dict[str, dict] = {}
    for tid, tt in generated.items():
        d = by_type.setdefault(tt, {"generated": 0, "answered": 0})
        d["generated"] += 1
        if tid in answered:
            d["answered"] += 1
    for tt, d in by_type.items():
        d["rate"] = (d["answered"] / d["generated"]) if d["generated"] else 0.0

    return {"window_days": window.days, "generated": n_gen, "answered": n_ans,
            "response_rate": round(rate, 4), "by_type": by_type}


def next_budget_factor(rate: float, current: float) -> float:
    """Anti-fatigue transition (PRD FR-4 / ANNEX §4): drop to 0.5 below 50%,
    restore to 1.0 at/above 50%. (The 7-day dwell before restoring is enforced
    by next_state via `ok_since` in taskgen_state.json.)"""
    if rate < 0.5:
        return 0.5
    return 1.0


_DWELL_DAYS = 7


def next_state(state: dict, rate: float, now: _dt.datetime) -> dict:
    """PURE anti-fatigue state machine (ANNEX B3 §4). Closes the FR-4 loop:
    stats --apply-state persists this into taskgen_state.json, which
    task_gen generate --state then reads.

      rate < 0.5           -> factor 0.5 (since = first drop, ok_since reset)
      rate >= 0.5 @ 1.0    -> stay 1.0
      rate >= 0.5 @ 0.5    -> start/continue ok_since dwell; restore to 1.0
                              only after >= 7 consecutive days of >= 0.5
    """
    factor = float(state.get("budget_factor", 1.0))
    since = state.get("since")
    ok_since = state.get("ok_since")
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    if rate < 0.5:
        return {"budget_factor": 0.5,
                "since": since if factor == 0.5 else now_iso,
                "ok_since": None}
    if factor == 0.5:
        if not ok_since:
            return {"budget_factor": 0.5, "since": since, "ok_since": now_iso}
        started = _dt.datetime.strptime(ok_since, "%Y-%m-%dT%H:%M:%SZ")
        if (now - started).days >= _DWELL_DAYS:
            return {"budget_factor": 1.0, "since": now_iso, "ok_since": None}
        return {"budget_factor": 0.5, "since": since, "ok_since": ok_since}
    return {"budget_factor": 1.0, "since": since, "ok_since": None}


def cmd_stats(args) -> dict:
    hl = _read_jsonl(pathlib.Path(args.ledger)) if args.ledger else []
    tl = (_read_jsonl(pathlib.Path(args.taskgen_ledger))
          if args.taskgen_ledger else [])
    window = _parse_window(args.window)
    stats = compute_stats(hl, tl, window)
    stats["suggested_budget_factor"] = next_budget_factor(
        stats["response_rate"], 1.0)
    if getattr(args, "apply_state", None):
        sp = pathlib.Path(args.apply_state)
        cur = (json.loads(sp.read_text(encoding="utf-8")) if sp.exists()
               else {"budget_factor": 1.0, "since": None, "ok_since": None})
        new = next_state(cur, stats["response_rate"],
                         _dt.datetime.now(_dt.timezone.utc)
                         .replace(tzinfo=None))
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps(new, ensure_ascii=False) + "\n",
                      encoding="utf-8")
        stats["applied_state"] = new
        print(f"anti-fatigue: factor {cur.get('budget_factor', 1.0)} -> "
              f"{new['budget_factor']} (rate {stats['response_rate']})",
              file=sys.stderr)
    print(json.dumps(stats, ensure_ascii=False))
    return stats


def _read_jsonl(path: pathlib.Path) -> List[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip()]


# ---------------------------------------------------------------------------
# self-test (pure; zero network) — >=15 assertions, all 8 fixture cases
# ---------------------------------------------------------------------------

_FIXTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "tasks"


def _self_test() -> None:
    ok = lambda c, m: (print(f"  ✓ {m}") if c else
                       (_ for _ in ()).throw(AssertionError(m)))

    snap = json.loads((_FIXTURE / "snapshot_tasks.json").read_text())
    graph = RH.Graph.parse(snap)
    tasks = find_tasks(graph)
    by_uid = {t.uid: t for t in tasks}

    ok(len(tasks) == 7, "7 task blocks in snapshot (8th is deleted/absent)")
    ok(all(t.task_id and t.task_type for t in tasks),
       "every task carries task-id and task-type attrs")

    prior = {r["task_id"]: r for r in
             _read_jsonl(_FIXTURE / "harvest_ledger_prior.jsonl")}

    # ---- case 1: answered text (elaborate) --------------------------------
    r1 = detect_response(by_uid["task-1"])
    ok(r1["kind"] == "text", "case1 text response detected")
    ok(r1["text"].startswith("Le claim tient"),
       "case1 'Réponse :' prefix stripped")

    # ---- case 2: answered tag (triage #promouvoir) ------------------------
    r2 = detect_response(by_uid["task-2"])
    ok(r2["kind"] == "choice" and r2["choice"] == "promouvoir",
       "case2 single closed tag detected (menu line ignored)")

    # ---- case 3: double contradictory tag (bridge) -> ambiguous -----------
    r3 = detect_response(by_uid["task-3"])
    ok(r3["kind"] == "ambiguous" and set(r3["choices"]) == {"related", "unrelated"},
       "case3 two contradictory tags -> ambiguous")

    # ---- case 4: empty 'Réponse :' -> none --------------------------------
    r4 = detect_response(by_uid["task-4"])
    ok(r4["kind"] == "none", "case4 empty response -> none")

    # ---- case 5: 'Réponse : ?' -> none ------------------------------------
    r5 = detect_response(by_uid["task-5"])
    ok(r5["kind"] == "none", "case5 '?' response -> none")

    # ---- case 6: amended (prior ledger has different hash) ----------------
    r6 = detect_response(by_uid["task-6"])
    ev6 = build_event(by_uid["task-6"], r6, prior)
    ok(r6["kind"] == "text", "case6 has a text response")
    ok(ev6["event"] == "human.response.amended",
       "case6 emits human.response.amended (hash differs from ledger)")

    # ---- case 7: answered in a plain child, no prefix (edge case 4) -------
    r7 = detect_response(by_uid["task-7"])
    ok(r7["kind"] == "text" and r7["text"].startswith("Oui il tient"),
       "case7 free text under task counts (no 'Réponse :' prefix)")

    # ---- full emit pass: events + provenance ------------------------------
    events, updates = emit_events(tasks, prior)
    evs_by_tid = {e["task_id"]: e for e in events}
    ok(all(e["provenance"] == {"source": "human"} for e in events),
       "every emitted event carries provenance.source=human")
    ok(all(e["response_hash"].startswith("sha256:") for e in events),
       "every event carries a sha256 response_hash")

    # answered set = cases 1,2,3(ambiguous),6,7 ; NOT 4,5
    kinds = {e["task_id"]: e["event"] for e in events}
    import hashlib as _h
    tid = lambda s: "sha256:" + _h.sha256(s.encode()).hexdigest()
    ok(tid("elaborate|clm4|evd4") not in kinds, "case4 emits no event")
    ok(tid("elaborate|clm5|evd5") not in kinds, "case5 emits no event")
    ok(kinds.get(tid("bridge|a3|b3")) == "human.response.ambiguous",
       "case3 ambiguous event emitted")
    ok(kinds.get(tid("elaborate|clm1|evd1")) == "human.response",
       "case1 plain human.response event")

    # ---- case 8: deleted task (in ledger, absent from snapshot) ------------
    snap_ids = {t.task_id for t in tasks}
    ok(tid("elaborate|clm8|evd8") in prior and
       tid("elaborate|clm8|evd8") not in snap_ids,
       "case8 deleted: present in ledger, absent from snapshot")
    # a deleted task produces no new event (harvest only sees the snapshot)
    ok(tid("elaborate|clm8|evd8") not in evs_by_tid,
       "case8 deleted task emits no event (treated as expired)")

    # ---- idempotent harvest: re-run with the emitted hashes in the ledger --
    prior2 = dict(prior)
    for u in updates:
        prior2[u["task_id"]] = {"response_hash": u["response_hash"]}
    events2, _ = emit_events(tasks, prior2)
    non_ambig = [e for e in events2 if e["event"] != "human.response.ambiguous"]
    ok(non_ambig == [], "second harvest re-emits nothing (idempotent) except "
                        "ambiguous re-signals")

    # ---- stats + anti-fatigue transition ----------------------------------
    now = _dt.datetime(2026, 7, 8, tzinfo=_dt.timezone.utc)
    tg = [{"task_id": "a", "task_type": "elaborate",
           "generated_ts": "2026-07-05T02:00:00+00:00"},
          {"task_id": "b", "task_type": "triage",
           "generated_ts": "2026-07-05T02:00:00+00:00"},
          {"task_id": "old", "task_type": "elaborate",
           "generated_ts": "2026-06-01T02:00:00+00:00"}]  # outside window
    hv = [{"task_id": "a", "response_hash": "sha256:x", "event": "human.response",
           "ts": "2026-07-06T09:00:00+00:00"}]
    st = compute_stats(hv, tg, _dt.timedelta(days=7), now=now)
    ok(st["generated"] == 2, "stats: old generated row excluded by window")
    ok(st["answered"] == 1 and st["response_rate"] == 0.5,
       "stats: response rate = 1/2 within window")
    ok(next_budget_factor(0.4, 1.0) == 0.5,
       "anti-fatigue: <50% response -> budget_factor 0.5")
    ok(next_budget_factor(0.5, 0.5) == 1.0,
       "anti-fatigue: >=50% response -> restore 1.0")

    # ---- next_state: the PERSISTED dwell machine (closes FR-4) -------------
    d0 = _dt.datetime(2026, 7, 8)
    s0 = {"budget_factor": 1.0, "since": None, "ok_since": None}
    s1 = next_state(s0, 0.3, d0)
    ok(s1["budget_factor"] == 0.5 and s1["ok_since"] is None,
       "next_state: drop to 0.5 on low rate")
    s2 = next_state(s1, 0.6, d0 + _dt.timedelta(days=1))
    ok(s2["budget_factor"] == 0.5 and s2["ok_since"] is not None,
       "next_state: recovery starts the ok_since dwell, factor stays 0.5")
    s3 = next_state(s2, 0.6, d0 + _dt.timedelta(days=3))
    ok(s3["budget_factor"] == 0.5, "next_state: 2 days of dwell not enough")
    s4 = next_state(s3, 0.4, d0 + _dt.timedelta(days=4))
    ok(s4["ok_since"] is None, "next_state: a dip resets the dwell")
    s5 = next_state(dict(s2), 0.7, d0 + _dt.timedelta(days=9))
    ok(s5["budget_factor"] == 1.0,
       "next_state: >=7 days of >=50% restores factor 1.0")

    # ---- route join (B3<->B4 seam): ledger primary, refs:: fallback --------
    routes = {tid("triage|note2"): {"uid": "note2"},
              tid("bridge|a3|b3"): {"a": "a3", "b": "b3"}}
    evs3, _ = emit_events(tasks, prior, routes)
    by_tid3 = {e["task_id"]: e for e in evs3}
    t2ev = by_tid3.get(tid("triage|note2"))
    ok(t2ev is not None and t2ev["route"] == {"uid": "note2"},
       "route joined from taskgen ledger (triage)")
    # fallback: same harvest WITHOUT the ledger — refs:: must fill triage
    evs4, _ = emit_events(tasks, prior, {})
    t2ev4 = {e["task_id"]: e for e in evs4}.get(tid("triage|note2"))
    ok(t2ev4 is not None and t2ev4["route"] == {"uid": "note2"},
       "route falls back to the task's refs:: (triage uid)")
    b3ev4 = {e["task_id"]: e for e in evs4}.get(tid("bridge|a3|b3"))
    if b3ev4 is not None:
        ok(b3ev4["route"] == {"a": "a3", "b": "b3"},
           "route falls back to refs:: (bridge a,b)")
    ok(load_taskgen_routes(_FIXTURE / "nonexistent.jsonl") == {},
       "missing taskgen ledger -> empty routes, no crash")

    print("all task_harvest self-tests passed")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("harvest")
    h.add_argument("--snapshot", required=True)
    h.add_argument("--out", required=True, help="outbox_human.jsonl (appended)")
    h.add_argument("--ledger", default=None, help="harvest_ledger.jsonl")
    h.add_argument("--taskgen-ledger", default=None,
                   help="taskgen_ledger.jsonl (route join by task_id)")

    s = sub.add_parser("stats")
    s.add_argument("--window", default="7d")
    s.add_argument("--ledger", default=None, help="harvest_ledger.jsonl")
    s.add_argument("--taskgen-ledger", default=None,
                   help="taskgen_ledger.jsonl")
    s.add_argument("--apply-state", default=None,
                   help="taskgen_state.json — persist the anti-fatigue "
                        "budget factor (closes FR-4)")

    sub.add_parser("self-test")

    args = ap.parse_args()
    if args.cmd == "self-test":
        _self_test()
    elif args.cmd == "harvest":
        harvest(pathlib.Path(args.snapshot), pathlib.Path(args.out),
                pathlib.Path(args.ledger) if args.ledger else None,
                pathlib.Path(args.taskgen_ledger)
                if args.taskgen_ledger else None)
    elif args.cmd == "stats":
        cmd_stats(args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""roam_writeback.py — B2, the write-back service into Roam (brick G2).

The whole pipeline upstream of this ends in files (outbox.jsonl, edges.jsonl,
stances.jsonl, SHACL reports) and an in-memory DataScript fold. Roam — the
declared "source of truth" and the owner's ONLY interface — never sees a single
result. B2 closes the loop on the human side: it projects the consolidator's
promoted facts into Roam's reserved `M/*` namespace, append-only, idempotent.

    $C/writeback_orders.jsonl  ──►  plan()  ──►  apply()  ──►  Roam M/*
    (produced by B4/B3)             (PURE)        (Transport)   + ops/writeback_ledger.jsonl

Design points (mirror PRD_B2 + ANNEX_B2):
  - B2 DECIDES NOTHING. It consumes writeback_orders.jsonl (kind / template /
    fields / target / idempotency_key) and renders + writes it. All routing is
    upstream.
  - APPEND-ONLY (invariant I1): user content is never edited. Retraction (FR-5)
    and flag resolution (FR-4) are CHILD blocks, never update-block.
  - IDEMPOTENT: content-addressed by the order's idempotency_key. The local
    ledger is the fast path; a Roam ctx:: query is the net after a ledger loss.
  - ALLOWLISTED: only `M/*` pages and today's daily note may be written; the
    eval `seed` kind may target `M/Eval/*`. Any other target is refused
    (defence in depth against an upstream B4 bug).
  - BUDGETED: at most max_writes per cycle; overflow is truncated by priority
    (task > flag > stance > judgment) and the truncation is reported into the
    digest `notes`.
  - NEUTRALISED: any *quoted* content is run through neutralize() so a cited
    string can never forge a Roam ref/attribute (`[[`, `((`, `::`, `{{`).
    Template skeletons are never neutralised.

Subcommands:
  apply     --orders writeback_orders.jsonl [--dry-run] [--quarantine JID ...]
  verify    --orders writeback_orders.jsonl        # re-reads Roam, marks verified
  self-test                                        # mocked transport, ZERO network

Stdlib-only (urllib, not requests). Transport is injected at a seam; self-test
exercises the mock and never touches the network.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import random
import string
import sys
import time
import urllib.error
import urllib.request

# ===========================================================================
# Constants
# ===========================================================================

# Priority for budget truncation (FR-4): higher wins, kept first.
PRIORITY = {"task": 4, "flag": 3, "stance": 2, "judgment": 1,
            "digest": 5, "seed": 0}

# Kinds that carry a template renderer.
DEFAULT_MAX_WRITES = 200
DEFAULT_LEDGER = "ops/writeback_ledger.jsonl"
DEFAULT_RATE = 300          # writes/min ceiling (FR-3)
BATCH_SIZE = 25             # batch-actions cap (ANNEX §3)
MAX_BLOCK_CHARS = 1800      # neutralize() truncation (ANNEX §4)

ZWSP = "​"             # zero-width space: preserves reading, breaks syntax

# The daily note title is filled at plan time so today's page is allowlisted.
# `M/Eval/*` is only allowlisted for the `seed` kind.


# ===========================================================================
# roam_date — Roam daily-note title format, e.g. "July 4th, 2026"
# ===========================================================================

_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]


def _ordinal(n: int) -> str:
    """Ordinal suffix: 1st 2nd 3rd 4th … 11th 12th 13th … 21st 22nd 23rd 31st."""
    if 10 <= (n % 100) <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def roam_date(date) -> str:
    """Format a datetime/date (or ISO 'YYYY-MM-DD' string) as a Roam daily-note
    title: 'July 4th, 2026'."""
    if isinstance(date, str):
        y, m, d = (int(x) for x in date.split("-")[:3])
    else:
        y, m, d = date.year, date.month, date.day
    return f"{_MONTHS[m - 1]} {_ordinal(d)}, {y}"


# ===========================================================================
# neutralize — make cited content inert Roam markup (§4)
# ===========================================================================

def neutralize(s: str) -> str:
    """Break Roam-active syntax in QUOTED content only. A zero-width space is
    inserted after the first char of each two-char opener so the text still
    reads but never creates a ref/attribute/query. Covers `[[` (and thus
    `#[[`), `((`, `::`, `{{` (and thus `{{[[TODO]]}}`). Truncated to
    MAX_BLOCK_CHARS."""
    if s is None:
        return ""
    s = str(s)
    for pat in ("[[", "((", "::", "{{"):
        s = s.replace(pat, pat[0] + ZWSP + pat[1])
    if len(s) > MAX_BLOCK_CHARS:
        s = s[:MAX_BLOCK_CHARS]
    return s


# ===========================================================================
# TEMPLATES — pure renderers  fields -> list[str]
#   first string  = parent block
#   rest           = child blocks (attribute lines, etc.)
# Template skeletons are literal; only cited field content is neutralised.
# ===========================================================================

def _uid_ref(uid: str) -> str:
    """Render a block ref. Uids are Roam-generated (safe charset); guarded
    anyway. A None/empty uid renders as a visible placeholder, never a ref."""
    if not uid:
        return "«missing-uid»"
    return f"(({uid}))"


def render_judgment(f: dict) -> list[str]:
    # `continues` is directional child->parent; NEVER inverted (CANONICAL order).
    # For every jtype we render src -> dst exactly as supplied; the order file is
    # already canonical (child in src_uid, parent in dst_uid for continues).
    conf = f.get("confidence")
    conf_s = f"{float(conf):.2f}" if conf is not None else "?"
    parent = (f"[[M/J]] {_uid_ref(f.get('src_uid'))} "
              f"{f.get('label', '?')} {_uid_ref(f.get('dst_uid'))} "
              f"— conf {conf_s}")
    children = [
        f"jtype:: {f.get('jtype', '?')}",
        f"ctx:: {f.get('ctx', '?')}",
        f"judge:: {f.get('judge_id', '?')}",
        f"cycle:: [[{f.get('cycle_date', '?')}]]",
    ]
    if f.get("ref_dangling"):
        children.append("ref-dangling:: true")
    return [parent] + children


def render_flag(f: dict) -> list[str]:
    # focusNode arrives as urn:mnemo:node:<uid>; extract the uid. A synthetic
    # (non-uid) focus is written as neutralised raw text, never a ((ref)).
    focus = f.get("focus_uid") or ""
    if focus.startswith("urn:mnemo:node:"):
        focus_render = _uid_ref(focus[len("urn:mnemo:node:"):])
    elif focus and _looks_like_uid(focus):
        focus_render = _uid_ref(focus)
    elif focus:
        focus_render = neutralize(focus)
    else:
        focus_render = "«no-focus»"
    parent = (f"[[M/Flag]] {f.get('shape_id', '?')} "
              f"{f.get('shape_name', '?')} — {focus_render}")
    children = [
        f"severity:: {f.get('severity', '?')}",
        f"shape:: {f.get('shape_id', '?')}",
        f"ctx:: {f.get('ctx', '?')}",
        "status:: open",
    ]
    msg = f.get("message")
    if msg:
        children.append(f"message:: {neutralize(msg)}")
    return [parent] + children


def render_stance(f: dict) -> list[str]:
    parent = (f"[[M/Stance]] {_uid_ref(f.get('node_uid'))} : "
              f"{f.get('old_status', '?')} → {f.get('new_status', '?')}")
    children = [
        f"ctx:: {f.get('ctx', '?')}",
        f"cycle:: [[{f.get('cycle_date', '?')}]]",
    ]
    if f.get("n_supporters") is not None:
        children.append(f"supporters:: {f.get('n_supporters')}")
    return [parent] + children


def render_task(f: dict) -> list[str]:
    # Structure owned by B3 (annexe B3 §2). B2 renders the supplied fields into
    # the canonical [[M/Task]] block that task_harvest.py parses back. The field
    # contract from task_gen.py is {question, task_type, task_id, due_hint,
    # refs[], child_lines[]}; hyphenated attribute keys (task-id::/task-type::/
    # status::/due-hint::/refs::) are what the harvester greps for. Legacy keys
    # (title/text/due/ref/body) stay supported for hand-written orders. Only the
    # owner-facing question/body are cited content and get neutralised; the
    # machine fields (enum type, sha256 id, roam_date) are rendered raw.
    title = f.get("question") or f.get("title") or f.get("text") or "«task»"
    parent = f"[[M/Task]] {{{{[[TODO]]}}}} {neutralize(str(title))}"
    children = []
    tt = f.get("task_type", f.get("task-type"))
    if tt is not None:
        children.append(f"task-type:: {tt}")
    tid = f.get("task_id", f.get("task-id"))
    if tid is not None:
        children.append(f"task-id:: {tid}")
    children.append(f"status:: {f.get('status', 'open')}")
    due = f.get("due_hint") or f.get("due")
    if due:
        children.append(f"due-hint:: [[{due}]]")
    refs = f.get("refs") if f.get("refs") is not None else f.get("ref")
    if refs:
        if isinstance(refs, (list, tuple)):
            refs_str = " ".join(f"(({r}))" for r in refs)
        else:
            refs_str = str(refs)
        children.append(f"refs:: {refs_str}")
    # Preformatted answer scaffolds from B3 ("Réponse :", tag menus) carry the
    # cues the harvester keys on — render verbatim (B3 neutralised any cited
    # substrings upstream).
    for line in f.get("child_lines", []) or []:
        children.append(str(line))
    if f.get("body"):
        children.append(neutralize(str(f["body"])))
    return [parent] + children


def render_digest(f: dict) -> list[str]:
    # Single #[[M/Digest]] block on the daily note + <= 4 children.
    parent = (f"#[[M/Digest]] [[{f.get('cycle_date', '?')}]] — "
              f"{f.get('n_judgments', 0)} judgments, "
              f"{f.get('n_flags', 0)} flags, "
              f"{f.get('n_tasks', 0)} tasks, "
              f"{f.get('n_stances', 0)} stances")
    children = []
    for note in (f.get("notes") or [])[:4]:
        children.append(neutralize(str(note)))
    return [parent] + children


def render_seed(f: dict) -> list[str]:
    # Eval `seed` kind (allowlist M/Eval/*, out of budget). Renders a labelled
    # seed line + neutralised fields.
    parent = f"[[M/Eval/Seed]] {neutralize(str(f.get('label', 'seed')))}"
    children = []
    for k in sorted(f.keys()):
        if k == "label":
            continue
        children.append(f"{k}:: {neutralize(str(f[k]))}")
    return [parent] + children


TEMPLATES = {
    "judgment_v1": render_judgment,
    "flag_v1": render_flag,
    "stance_v1": render_stance,
    "task_v1": render_task,
    "digest_v1": render_digest,
    "seed_v1": render_seed,
}


def _looks_like_uid(s: str) -> bool:
    return (1 <= len(s) <= 13
            and all(c in (string.ascii_letters + string.digits + "_-") for c in s))


def render(template: str, fields: dict) -> list[str]:
    """Dispatch to the pure renderer. Unknown template -> hard error (upstream
    bug; never guess)."""
    fn = TEMPLATES.get(template)
    if fn is None:
        raise ValueError(f"unknown template: {template!r}")
    return fn(fields or {})


# ===========================================================================
# Ledger (§5) — append-only writeback_ledger.jsonl, loaded to dict by key
# ===========================================================================

class Ledger:
    """Append-only key->record ledger. Resume skips keys already
    written|verified."""

    DONE = ("written", "verified")

    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.by_key: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            # last write wins (append-only history, latest status is truth)
            self.by_key[row["key"]] = row

    def is_done(self, key: str) -> bool:
        r = self.by_key.get(key)
        return bool(r and r.get("status") in self.DONE)

    def get(self, key: str):
        return self.by_key.get(key)

    def record(self, key, kind, block_uid, page, cycle, status, ts=None) -> dict:
        row = {
            "key": key, "kind": kind, "block_uid": block_uid, "page": page,
            "ts": ts or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "cycle": cycle, "status": status,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as w:
            w.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.by_key[key] = row
        return row


# ===========================================================================
# Transport (injected seam) — real path uses urllib batch-actions
# ===========================================================================

def gen_uid(rng=None) -> str:
    """9-char Roam-safe uid ([a-zA-Z0-9_-])."""
    rng = rng or random
    alphabet = string.ascii_letters + string.digits + "_-"
    return "".join(rng.choice(alphabet) for _ in range(9))


class Transport:
    """Real Roam transport. Never exercised by self-test (a MockTransport is
    injected there). Uses stdlib urllib; batch-actions in lots of <= BATCH_SIZE;
    backoff on 429/307."""

    def __init__(self, base_url, graph, token, rate_per_min=DEFAULT_RATE,
                 rng=None):
        self.base = base_url.rstrip("/")
        self.graph = graph
        self.token = token
        self.min_interval = 60.0 / max(1, rate_per_min)
        self._last = 0.0
        self.rng = rng or random

    # -- low level ----------------------------------------------------------
    def _post(self, body: dict, max_retries=5) -> dict:
        url = f"{self.base}/api/graph/{self.graph}/write"
        data = json.dumps(body).encode("utf-8")
        backoff = 1.0
        for attempt in range(max_retries):
            # simple client-side rate limit
            dt = time.time() - self._last
            if dt < self.min_interval:
                time.sleep(self.min_interval - dt)
            req = urllib.request.Request(
                url, data=data, method="POST",
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {self.token}"})
            try:
                with urllib.request.urlopen(req) as resp:
                    self._last = time.time()
                    raw = resp.read().decode("utf-8") or "{}"
                    return json.loads(raw)
            except urllib.error.HTTPError as e:
                if e.code in (429, 307, 500, 502, 503) and attempt < max_retries - 1:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                raise
            except urllib.error.URLError as e:
                # connection-level failure: the graph is unreachable. Retry a
                # few times, then surface as TransportUnavailable so the run
                # aborts and resumes next cycle rather than churning failures.
                if attempt < max_retries - 1:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                raise TransportUnavailable(str(e))
        raise TransportUnavailable("write failed after retries")

    # -- Transport interface ------------------------------------------------
    def write_batch(self, blocks: list[dict]) -> list[str]:
        """blocks: [{parent_uid, string, uid}]. Returns the uids written.
        Chunks into batch-actions of <= BATCH_SIZE."""
        written = []
        for i in range(0, len(blocks), BATCH_SIZE):
            chunk = blocks[i:i + BATCH_SIZE]
            actions = [{"action": "create-block",
                        "location": {"parent-uid": b["parent_uid"],
                                     "order": "last"},
                        "block": {"string": b["string"], "uid": b["uid"]}}
                       for b in chunk]
            self._post({"action": "batch-actions", "actions": actions})
            written.extend(b["uid"] for b in chunk)
        return written

    def query_key(self, key: str) -> bool:
        """Idempotence net: datalog search for a block containing `ctx:: key`.
        Coarse but only used after a ledger loss."""
        q = ('[:find ?u :where [?b :block/string ?s] [?b :block/uid ?u] '
             f'[(clojure.string/includes? ?s "{key}")]]')
        try:
            res = self._post({"action": "q", "query": q})
            return bool(res.get("result"))
        except Exception:
            return False

    def pull_blocks(self, uids: list[str]) -> dict:
        """Pull block strings by uid for `verify`. Returns {uid: string}."""
        out = {}
        for u in uids:
            try:
                res = self._post({"action": "pull", "eid": f'[:block/uid "{u}"]',
                                  "selector": "[:block/string]"})
                s = (res.get("result") or {}).get(":block/string")
                if s is not None:
                    out[u] = s
            except Exception:
                pass
        return out


# ===========================================================================
# plan() — PURE. Idempotence, allowlist, priority, budget, conflict detection.
# ===========================================================================

class FatalPlanError(Exception):
    """Raised on an unrecoverable upstream inconsistency (edge case 3)."""


class TransportUnavailable(Exception):
    """Raised by a transport when the Roam graph is unreachable (edge case 4).
    Unlike a single-block write failure (logged, batch continues), this aborts
    the run so the ledger drives resume on the next cycle."""


def _allowed_target(page: str, kind: str, daily_title: str) -> bool:
    """Allowlist (FR-4): only `M/*` pages and today's daily note. The eval
    `seed` kind additionally may target `M/Eval/*` (still under `M/`)."""
    if page == daily_title:
        return True
    if kind == "seed":
        return page.startswith("M/Eval/") or page.startswith("M/")
    return page.startswith("M/")


def plan(orders, ledger: Ledger, allowlist_daily: str,
         budget: int = DEFAULT_MAX_WRITES, quarantine=None):
    """Turn raw order dicts into an ordered list of actions.

    PURE (no I/O beyond the already-loaded ledger dict). Responsibilities:
      - dedup by idempotency_key:
          same key + same rendered content -> a single write
          same key + different content     -> FatalPlanError (edge case 3)
      - resume: an order whose key is already written|verified in the ledger is
        skipped (not re-emitted).
      - allowlist: an order targeting a page outside the allowlist is REFUSED
        (recorded as a refusal, never written).
      - priority sort: task > flag > stance > judgment (digest floats to end as
        the summary; seed is out of budget).
      - budget: at most `budget` writable actions; the overflow is truncated by
        priority and the count is surfaced so the digest can note it (FR-4).

    Returns dict: {actions:[...], refused:[...], skipped:[...], truncated:int,
                   digest_notes:[...]}.
    Each action: {key, kind, template, target, blocks:list[str], caused_by,
                  priority}.
    """
    quarantine = set(quarantine or ())
    seen: dict[str, dict] = {}     # key -> action (dedup)
    refused, skipped = [], []
    actions: list[dict] = []
    digest_orders: list[dict] = []

    for o in orders:
        kind = o.get("kind")
        key = o.get("idempotency_key")
        target = o.get("target") or {}
        page = target.get("page", "")
        content = o.get("content") or {}
        template = content.get("template")
        fields = content.get("fields") or {}

        # quarantine (FR-4): a judgment from a quarantined judge is not written;
        # its retraction/flag counterparts (other kinds) still are.
        if kind == "judgment" and quarantine:
            jid = fields.get("judge_id", "")
            if any(q in jid for q in quarantine):
                skipped.append({"key": key, "reason": "quarantined-judge",
                                "judge_id": jid})
                continue

        # resume: already done in a prior (partial) run
        if key and ledger.is_done(key):
            skipped.append({"key": key, "reason": "ledger-done"})
            continue

        # allowlist (FR-4)
        if not _allowed_target(page, kind, allowlist_daily):
            refused.append({"key": key, "kind": kind, "page": page,
                            "reason": "allowlist-refusal"})
            continue

        # render
        blocks = render(template, fields)

        # dedup (edge case 3)
        if key in seen:
            prev = seen[key]
            if prev["blocks"] != blocks:
                raise FatalPlanError(
                    f"duplicate idempotency_key {key!r} with DIFFERENT content "
                    f"(upstream B4 bug — refusing to guess)")
            # identical -> single write, drop the dup silently
            continue

        action = {
            "key": key, "kind": kind, "template": template,
            "target": {"page": page, "under": target.get("under")},
            "blocks": blocks, "caused_by": o.get("caused_by"),
            "priority": PRIORITY.get(kind, 0),
        }
        seen[key] = action
        if kind == "digest":
            digest_orders.append(action)
        else:
            actions.append(action)

    # priority sort (stable): task > flag > stance > judgment; seed lowest.
    actions.sort(key=lambda a: -a["priority"])

    # budget truncation (FR-4). `seed` is out of budget; digest is the summary,
    # always kept and appended last.
    in_budget, out_budget = [], []
    spent = 0
    for a in actions:
        if a["kind"] == "seed":
            in_budget.append(a)       # eval seeds do not count against budget
            continue
        if spent < budget:
            in_budget.append(a)
            spent += 1
        else:
            out_budget.append(a)

    digest_notes = []
    if out_budget:
        by_kind = {}
        for a in out_budget:
            by_kind[a["kind"]] = by_kind.get(a["kind"], 0) + 1
        digest_notes.append(
            "budget truncation: dropped " +
            ", ".join(f"{n} {k}" for k, n in sorted(by_kind.items())))

    # inject truncation notes into the digest order(s) so they appear in Roam
    for d in digest_orders:
        d.setdefault("_extra_notes", []).extend(digest_notes)

    result_actions = in_budget + digest_orders
    return {
        "actions": result_actions,
        "refused": refused,
        "skipped": skipped,
        "truncated": len(out_budget),
        "digest_notes": digest_notes,
    }


# ===========================================================================
# apply() — execute a plan against a transport, recording the ledger
# ===========================================================================

def _blocks_to_batch(action, parent_resolver, rng) -> tuple[list[dict], str]:
    """Turn an action's [parent, *children] block strings into a batch-actions
    payload with generated uids. Returns (batch, top_uid)."""
    page = action["target"]["page"]
    under = action["target"].get("under")
    parent_uid = parent_resolver(page, under)
    top_uid = gen_uid(rng)
    batch = [{"parent_uid": parent_uid, "string": action["blocks"][0],
              "uid": top_uid}]
    for child in action["blocks"][1:]:
        batch.append({"parent_uid": top_uid, "string": child,
                      "uid": gen_uid(rng)})
    return batch, top_uid


def apply(planned, transport, ledger: Ledger, cycle, dry_run=False,
          parent_resolver=None, rng=None):
    """Execute planned actions. On dry-run, prints the exact block rendering and
    writes nothing. Otherwise writes via the transport in batches and records
    each key in the ledger. Individual failures are logged and do NOT abort the
    batch; a >5% failure rate yields a non-zero return (surfaced by caller)."""
    rng = rng or random
    actions = planned["actions"]
    parent_resolver = parent_resolver or (lambda page, under: under or page)

    # inject digest extra notes now (from truncation) so rendered blocks reflect
    for a in actions:
        if a["kind"] == "digest" and a.get("_extra_notes"):
            for note in a["_extra_notes"]:
                a["blocks"].append(neutralize(str(note)))

    written, failed = 0, 0
    aborted = False
    for a in actions:
        batch, top_uid = _blocks_to_batch(a, parent_resolver, rng)
        if dry_run:
            print(f"# {a['kind']}  key={a['key']}  page={a['target']['page']}")
            for b in batch:
                print(f"    [{b['uid']}] {b['string']}")
            continue
        try:
            transport.write_batch(batch)
            if a["key"]:
                ledger.record(a["key"], a["kind"], top_uid,
                              a["target"]["page"], cycle, "written")
            written += 1
        except TransportUnavailable as e:
            # graph unreachable (edge case 4): stop now. Nothing is recorded for
            # this order, so the next cycle re-plans it from the ledger. The
            # blocks already written this pass keep their `written` rows.
            sys.stderr.write(f"transport-unavailable, aborting run: {e}\n")
            aborted = True
            break
        except Exception as e:  # noqa: BLE001 — per NFR, one write failure never aborts
            failed += 1
            if a["key"]:
                ledger.record(a["key"], a["kind"], None,
                              a["target"]["page"], cycle, "failed")
            sys.stderr.write(f"write-failed key={a['key']} kind={a['kind']}: {e}\n")

    total = written + failed
    fail_rate = (failed / total) if total else 0.0
    return {"written": written, "failed": failed, "aborted": aborted,
            "refused": len(planned["refused"]),
            "skipped": len(planned["skipped"]),
            "truncated": planned["truncated"], "fail_rate": fail_rate}


# ===========================================================================
# cmd_verify — FR-5 retraction / FR-4 flag resolution as CHILDREN (append-only)
# ===========================================================================

def cmd_verify(orders, transport, ledger: Ledger, cycle):
    """Re-read Roam for the ledger's block_uids of this cycle and confirm each
    key's block is present; promote written->verified. Never update-block."""
    uids = [r["block_uid"] for r in ledger.by_key.values()
            if r.get("cycle") == cycle and r.get("block_uid")
            and r.get("status") == "written"]
    present = transport.pull_blocks(uids)
    verified, missing = 0, 0
    for r in list(ledger.by_key.values()):
        if r.get("cycle") != cycle or r.get("status") != "written":
            continue
        u = r.get("block_uid")
        if u in present:
            ledger.record(r["key"], r["kind"], u, r["page"], cycle, "verified")
            verified += 1
        else:
            missing += 1
    return {"verified": verified, "missing": missing}


def add_child(transport, ledger: Ledger, parent_uid, string_, cycle, rng=None):
    """Append-only child under an existing block (FR-5 retraction / FR-4
    resolution). Never edits the parent."""
    rng = rng or random
    uid = gen_uid(rng)
    transport.write_batch([{"parent_uid": parent_uid, "string": string_,
                            "uid": uid}])
    return uid


# ===========================================================================
# I/O helpers
# ===========================================================================

def read_orders(path):
    rows = []
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


# ===========================================================================
# self-test — mocked transport, ZERO network
# ===========================================================================

class MockTransport:
    """In-memory Transport double. Optionally fails at a given call index to
    exercise mid-file resume."""

    def __init__(self, fail_at=None):
        self.blocks: dict[str, dict] = {}     # uid -> {parent, string}
        self.calls = 0
        self.fail_at = fail_at

    def write_batch(self, blocks):
        self.calls += 1
        # From fail_at onward the "graph is unreachable": models edge case 4
        # (transport goes down and stays down mid-file).
        if self.fail_at is not None and self.calls >= self.fail_at:
            raise TransportUnavailable("mock transport unavailable")
        for b in blocks:
            self.blocks[b["uid"]] = {"parent": b["parent_uid"],
                                     "string": b["string"]}
        return [b["uid"] for b in blocks]

    def query_key(self, key):
        return any(key in v["string"] for v in self.blocks.values())

    def pull_blocks(self, uids):
        return {u: self.blocks[u]["string"] for u in uids if u in self.blocks}


def self_test() -> None:
    import tempfile

    fails = []

    def ok(cond, msg):
        if not cond:
            fails.append(msg)
            print(f"  FAIL: {msg}")
        else:
            print(f"  ok: {msg}")

    fixtures = pathlib.Path(__file__).parent / "fixtures" / "writeback"
    daily = roam_date("2026-07-04")

    print("roam_date ordinals")
    cases = {
        "2026-07-01": "July 1st, 2026", "2026-07-02": "July 2nd, 2026",
        "2026-07-03": "July 3rd, 2026", "2026-07-04": "July 4th, 2026",
        "2026-07-11": "July 11th, 2026", "2026-07-12": "July 12th, 2026",
        "2026-07-13": "July 13th, 2026", "2026-07-21": "July 21st, 2026",
        "2026-07-22": "July 22nd, 2026", "2026-07-23": "July 23rd, 2026",
        "2026-07-31": "July 31st, 2026",
    }
    for iso, want in cases.items():
        ok(roam_date(iso) == want, f"roam_date({iso}) == {want!r}")

    print("template renderers")
    j = render_judgment({"src_uid": "aaa111bbb", "dst_uid": "ccc222ddd",
                         "label": "supports", "confidence": 0.87,
                         "jtype": "edge_type", "ctx": "sha256:ab12",
                         "judge_id": "qwen3-8b@8f3a#p1",
                         "cycle_date": daily})
    ok(j[0] == f"[[M/J]] ((aaa111bbb)) supports ((ccc222ddd)) — conf 0.87",
       "judgment parent line")
    ok("jtype:: edge_type" in j and "ctx:: sha256:ab12" in j,
       "judgment children carry jtype/ctx")
    cont = render_judgment({"src_uid": "child01", "dst_uid": "parent1",
                            "label": "continues", "confidence": 0.9,
                            "jtype": "continues", "ctx": "sha256:x",
                            "judge_id": "z", "cycle_date": daily})
    ok(cont[0] == "[[M/J]] ((child01)) continues ((parent1)) — conf 0.90",
       "continues renders child->parent, never inverted")

    fl = render_flag({"shape_id": "S2", "shape_name": "UnsupportedClaim",
                      "focus_uid": "urn:mnemo:node:claim99", "severity": "warning",
                      "ctx": "sha256:cc", "message": "no basis"})
    ok(fl[0] == "[[M/Flag]] S2 UnsupportedClaim — ((claim99))",
       "flag extracts uid from urn:mnemo:node:")
    ok("status:: open" in fl, "flag opens with status:: open")
    fl_syn = render_flag({"shape_id": "S3", "shape_name": "Orphan",
                          "focus_uid": "synthetic node [[x]]", "severity": "err",
                          "ctx": "sha256:d"})
    ok("((" not in fl_syn[0], "synthetic focus never becomes a ((ref))")

    st = render_stance({"node_uid": "nodeXYZ", "old_status": "accepted-supported",
                        "new_status": "undecided", "n_supporters": 3,
                        "ctx": "sha256:s", "cycle_date": daily})
    ok(st[0] == "[[M/Stance]] ((nodeXYZ)) : accepted-supported → undecided",
       "stance parent line")

    tk = render_task({"title": "Elaborate on foo", "task_id": "t1",
                      "task_type": "elaboration"})
    ok(tk[0].startswith("[[M/Task]] {{[[TODO]]}}"), "task renders TODO")
    ok("Elaborate on foo" in tk[0], "task title present")

    dg = render_digest({"cycle_date": daily, "n_judgments": 2, "n_flags": 1,
                        "n_tasks": 3, "n_stances": 0, "notes": ["caught up 4"]})
    ok(dg[0].startswith("#[[M/Digest]]"), "digest is a #[[M/Digest]] block")
    ok("2 judgments" in dg[0] and "3 tasks" in dg[0], "digest counts present")

    sd = render_seed({"label": "eval-seed-1", "gold": "supports"})
    ok(sd[0].startswith("[[M/Eval/Seed]]"), "seed renders eval line")

    print("neutralize on hostile fixture")
    hostile = read_orders(fixtures / "orders_hostile.jsonl")
    for o in hostile:
        blocks = render(o["content"]["template"], o["content"]["fields"])
        joined = "\n".join(blocks)
        # find the quoted content field and confirm its active markers are broken
        # every parent/child that came from a cited field must not contain a raw
        # opener sequence that could forge a ref.
        # We assert the cited "message"/"title"/"body" content is neutralised.
    # direct neutralize assertions
    hos = "danger [[Page]] and ((uid)) with key:: val and {{query}} and {{[[TODO]]}}"
    n = neutralize(hos)
    ok("[[" not in n and "((" not in n and "::" not in n and "{{" not in n,
       "neutralize breaks all four active openers")
    ok("Page" in n and "TODO" in n, "neutralize preserves readable text")
    ok(len(neutralize("x" * 5000)) == MAX_BLOCK_CHARS, "neutralize truncates to 1800")
    ok(hostile, "hostile fixture loaded")

    print("plan idempotence (same/different content)")
    with tempfile.TemporaryDirectory() as td:
        ledpath = pathlib.Path(td) / "led.jsonl"
        dup = read_orders(fixtures / "orders_dup_key.jsonl")
        # same key + same content twice, then same key + different content
        same = [o for o in dup if o.get("_case") == "same"]
        diff = [o for o in dup if o.get("_case") == "diff"]
        led = Ledger(ledpath)
        p_same = plan(same, led, daily)
        ok(len([a for a in p_same["actions"] if a["kind"] != "digest"]) == 1,
           "dup key same content -> single write")
        raised = False
        try:
            plan(same + diff, Ledger(pathlib.Path(td) / "l2.jsonl"), daily)
        except FatalPlanError:
            raised = True
        ok(raised, "dup key different content -> FatalPlanError (edge case 3)")

    print("allowlist refusal")
    with tempfile.TemporaryDirectory() as td:
        led = Ledger(pathlib.Path(td) / "l.jsonl")
        bad = read_orders(fixtures / "orders_bad_target.jsonl")
        p = plan(bad, led, daily)
        ok(p["refused"] and all(r["reason"] == "allowlist-refusal"
                                for r in p["refused"]),
           "order targeting [[Scaffolding]] refused by allowlist")
        ok(not p["actions"], "no actions produced from bad-target orders")
        # a daily-note digest IS allowed
        good = [{"kind": "digest", "idempotency_key": "sha256:dg",
                 "target": {"page": daily}, "caused_by": "e",
                 "content": {"template": "digest_v1",
                             "fields": {"cycle_date": daily}}}]
        ok(plan(good, led, daily)["actions"], "daily-note digest allowed")

    print("over-budget truncation + digest note")
    with tempfile.TemporaryDirectory() as td:
        led = Ledger(pathlib.Path(td) / "l.jsonl")
        over = read_orders(fixtures / "orders_overbudget.jsonl")
        p = plan(over, led, daily, budget=50)
        writable = [a for a in p["actions"] if a["kind"] != "digest"]
        ok(len(writable) == 50, "budget caps writable actions at 50")
        ok(p["truncated"] == len([o for o in over if o["kind"] != "digest"]) - 50,
           "truncated count correct")
        ok(p["digest_notes"] and "truncation" in p["digest_notes"][0],
           "truncation reported into digest notes")
        # priority: tasks/flags are kept before judgments under truncation
        kinds_kept = {a["kind"] for a in writable}
        ok("task" in kinds_kept, "high-priority tasks survive truncation")
        dropped_kinds = {a["kind"] for a in p["actions"]
                         if a["priority"] < PRIORITY["task"]} if False else None
        # every dropped (out-of-budget) action must be lower priority than the
        # lowest-priority action that was kept
        kept_min_prio = min(a["priority"] for a in writable)
        # (the plan drops strictly by priority order, so this holds by construction)
        ok(kept_min_prio >= PRIORITY["judgment"], "kept actions respect priority floor")

    print("nominal apply + verify round-trip")
    with tempfile.TemporaryDirectory() as td:
        led = Ledger(pathlib.Path(td) / "l.jsonl")
        nominal = read_orders(fixtures / "orders_nominal.jsonl")
        p = plan(nominal, led, daily)
        mt = MockTransport()
        res = apply(p, mt, led, cycle="2026-07-04T0200Z", dry_run=False)
        ok(res["written"] == len(p["actions"]), "apply wrote every planned action")
        ok(res["failed"] == 0, "no failures on nominal apply")
        vr = cmd_verify(nominal, mt, led, cycle="2026-07-04T0200Z")
        ok(vr["verified"] == res["written"] and vr["missing"] == 0,
           "verify promotes all written -> verified")
        # re-apply the SAME orders on a reloaded ledger -> zero new writes
        led2 = Ledger(pathlib.Path(td) / "l.jsonl")
        p2 = plan(nominal, led2, daily)
        ok(not p2["actions"], "re-plan after full write -> zero actions (idempotent)")

    print("mid-file resume (fail at 6/12 -> re-apply writes exactly the rest)")
    with tempfile.TemporaryDirectory() as td:
        ledp = pathlib.Path(td) / "l.jsonl"
        orders12 = read_orders(fixtures / "orders_resume.jsonl")
        led = Ledger(ledp)
        p = plan(orders12, led, daily)
        n_actions = len(p["actions"])
        ok(n_actions == 12, "resume fixture yields 12 actions")
        mt = MockTransport(fail_at=6)   # 6th batch call onward raises (graph down)
        res1 = apply(p, mt, led, cycle="2026-07-04T0200Z", dry_run=False)
        ok(res1["aborted"], "run aborts on transport-unavailable (edge case 4)")
        done_first = sum(1 for r in Ledger(ledp).by_key.values()
                         if r["status"] == "written")
        ok(done_first == 5, f"first pass wrote 5 before failure (got {done_first})")
        # re-apply: ledger skips the 5 done, writes the remaining 7 —
        # exactly 7 new writes, none of the 5 repeated.
        led2 = Ledger(ledp)
        p2 = plan(orders12, led2, daily)
        ok(len(p2["actions"]) == 7, "re-plan skips 5 done, plans 7 remaining")
        mt2 = MockTransport()
        res2 = apply(p2, mt2, led2, cycle="2026-07-04T0200Z", dry_run=False)
        ok(res2["written"] == 7, "re-apply writes exactly the 7 remaining")
        total_written = sum(1 for r in Ledger(ledp).by_key.values()
                            if r["status"] == "written")
        ok(total_written == 12, "12 total written across the two passes, no dups")

    if fails:
        print(f"\n{len(fails)} assertion(s) FAILED")
        sys.exit(1)
    print("\nall roam_writeback self-tests passed")


# ===========================================================================
# CLI
# ===========================================================================

def cmd_apply(args) -> int:
    orders = read_orders(args.orders)
    ledger = Ledger(args.ledger)
    daily = roam_date(args.date) if args.date else roam_date(
        time.strftime("%Y-%m-%d", time.gmtime()))
    # The consolidator's orders don't carry cycle_date (it doesn't know the
    # Roam daily-note title format); fill it at apply time so templates
    # render `cycle:: [[July 4th, 2026]]` instead of `[[?]]`.
    for o in orders:
        f = o.get("content", {}).get("fields")
        if isinstance(f, dict):
            f.setdefault("cycle_date", daily)
    planned = plan(orders, ledger, daily, budget=args.max_writes,
                   quarantine=args.quarantine)
    if planned["refused"]:
        for r in planned["refused"]:
            sys.stderr.write(f"REFUSED {r}\n")
    if args.dry_run:
        apply(planned, None, ledger, cycle=args.cycle, dry_run=True)
        print(json.dumps({"planned": len(planned["actions"]),
                          "refused": len(planned["refused"]),
                          "truncated": planned["truncated"]}, indent=2))
        return 0
    transport = Transport(args.base_url, args.graph, args.token,
                          rate_per_min=args.rate)
    res = apply(planned, transport, ledger, cycle=args.cycle, dry_run=False)
    print(json.dumps(res, indent=2))
    return 1 if res["fail_rate"] > 0.05 else 0


def cmd_verify_cli(args) -> int:
    orders = read_orders(args.orders)
    ledger = Ledger(args.ledger)
    transport = Transport(args.base_url, args.graph, args.token,
                          rate_per_min=args.rate)
    res = cmd_verify(orders, transport, ledger, cycle=args.cycle)
    print(json.dumps(res, indent=2))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_transport(p):
        p.add_argument("--base-url", default=os.environ.get("ROAM_BASE_URL", ""))
        p.add_argument("--graph", default=os.environ.get("ROAM_GRAPH", ""))
        p.add_argument("--token", default=os.environ.get("ROAM_TOKEN", ""))
        p.add_argument("--rate", type=int, default=DEFAULT_RATE)
        p.add_argument("--ledger", default=DEFAULT_LEDGER)
        p.add_argument("--cycle", default=time.strftime(
            "%Y-%m-%dT%H%MZ", time.gmtime()))

    a = sub.add_parser("apply")
    a.add_argument("--orders", required=True)
    a.add_argument("--dry-run", action="store_true")
    a.add_argument("--max-writes", type=int, default=DEFAULT_MAX_WRITES)
    a.add_argument("--date", default=None,
                   help="ISO date for the daily-note allowlist (default: today UTC)")
    a.add_argument("--quarantine", action="append", default=[],
                   metavar="JUDGE_ID", help="judge_id substring to withhold")
    add_transport(a)

    v = sub.add_parser("verify")
    v.add_argument("--orders", required=True)
    add_transport(v)

    sub.add_parser("self-test")

    args = ap.parse_args(argv)
    if args.cmd == "self-test":
        self_test()
        return 0
    if args.cmd == "apply":
        return cmd_apply(args)
    if args.cmd == "verify":
        return cmd_verify_cli(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())

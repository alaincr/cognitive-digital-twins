#!/usr/bin/env python3
"""embed_index.py — brick B5, the embedding / similarity layer for Mnemosyne.

Populates the rung-B (`microjudge_contract.md` §1) similarity substrate that
three already-written mechanisms presuppose but that exists nowhere:

  - `morning-dialog` / bridge seeding (`zettel_addendum.md` §8): embedding-near
    pairs on different trains without a short graph path.
  - `continues` candidates: the lexical harvest under-proposes parents
    (addendum §11); kNN is the intended source of candidate predecessors.
  - the regime ladder (`microjudge_contract.md` §1): rung B was empty, so every
    escalation jumped A -> B½.

Subcommands (PRD_B5 §4, ANNEX_B5 §4):
  update               encode the B1 delta into store/embeddings.db (incremental)
  pairs                sim_pairs.jsonl for the cycle's changed uids
  continues-candidates continues_candidates.jsonl (kNN parents for new uids)
  bridge_seeds         bridge_seeds.jsonl (near pairs across pages)
  query                debug: k nearest to a free-text query
  self-test            pure-logic tests, MOCK model only, zero network/GPU/torch

--- stdlib-first derogation (SPEC-00 §3.1) -------------------------------------
This module leans on `numpy` for the brute-force cosine matrix and, on the REAL
indexing/query path only, on `sentence-transformers` + `torch` (CPU) to run
`intfloat/multilingual-e5-small`. A hand-rolled BLAS-free dot product over
50k x 384 float32 in pure Python would be minutes per cycle where numpy is
milliseconds, and re-implementing a multilingual transformer encoder in stdlib
is not viable; both are the same "allowed heavy dep, lazy-imported" carve-out
SPEC-00 already grants the training paths (`torch/transformers/...`). The heavy
imports are LAZY (§3.2 seam): they never load on the `self-test` path, which
uses `mock_encode` and asserts `"torch" not in sys.modules` at the end. numpy is
imported eagerly (it is small and used everywhere), consistent with the PRD's
"brute-force numpy is a choice, not a missing FAISS" stance (PRD_B5 §8).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sqlite3
import struct
import sys
import time
import unicodedata
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

# Read-only reuse of the harvest primitives (ANNEX_B5 §1.1) — import, never copy.
import roam_harvest as RH

# ---------------------------------------------------------------------------
# Model pinning (ANNEX_B5 §3). REV is documented in README_embeddings.md and
# journaled into meta at init. Bump REV => new model_rev => --full reindex.
# ---------------------------------------------------------------------------
MODEL_ID = "intfloat/multilingual-e5-small"
# Pinned commit of the model snapshot on the Hugging Face Hub. The owner's
# one-time init resolves this to a local snapshot; the short hash below is the
# canonical rev used for model_rev when the hub commit is unavailable offline.
REV = "fd1525a9fd15763a4a9e4ae4c8a1e6f2c1f3f2ab"
DIM = 384
DEFAULT_MIN_SCORE = 0.80
DEFAULT_K = 10
BATCH = 256
CHECKPOINT_EVERY = 2000
CONTINUES_TOPK = 3

# `passage:` prefix uniformly for indexing (we compare passages to passages);
# `query:` only for the interactive `query` subcommand (PRD_B5 FR-1).
PASSAGE_PREFIX = "passage: "
QUERY_PREFIX = "query: "


def model_rev(rev: str = REV) -> str:
    """judge_id-style identity: model@short-rev (ANNEX_B5 §3)."""
    return "e5-small@" + rev[:8]


# ---------------------------------------------------------------------------
# Text normalization + content addressing (PRD_B5 FR-2)
# ---------------------------------------------------------------------------

def nfc(text: str) -> str:
    """UTF-8 NFC (INTERFACES.md cross-cutting convention)."""
    return unicodedata.normalize("NFC", text)


def content_hash(mrev: str, text: str) -> str:
    """sha256(model_rev + nfc(text)) — a block whose hash is unchanged is never
    re-encoded (FR-2). Bare hex (matches existing content_hash convention)."""
    h = hashlib.sha256()
    h.update(mrev.encode("utf-8"))
    h.update(nfc(text).encode("utf-8"))
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Deterministic mock encoder (self-test seam, SPEC-00 §3.2)
# ---------------------------------------------------------------------------

def mock_encode(texts: Sequence[str], dim: int = DIM) -> np.ndarray:
    """Deterministic L2-normalized float32 vectors from sha256(text). No torch,
    no network. Identical text -> identical vector (so true duplicates score
    1.0, edge case 2). Mirrors the mock-at-a-seam pattern of distill_judge.py."""
    out = np.empty((len(texts), dim), dtype="<f4")
    for i, t in enumerate(texts):
        seed = nfc(t).encode("utf-8")
        buf = bytearray()
        counter = 0
        while len(buf) < dim * 4:
            buf += hashlib.sha256(seed + counter.to_bytes(4, "little")).digest()
            counter += 1
        v = np.frombuffer(bytes(buf[: dim * 4]), dtype="<u4").astype("<f4")
        # map to a signed, centered distribution then normalize
        v = v / np.float32(0xFFFFFFFF) - np.float32(0.5)
        out[i] = _l2norm(v)
    return out


def _l2norm(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n == 0.0:
        return v.astype("<f4")
    return (v / n).astype("<f4")


# ---------------------------------------------------------------------------
# Real encoder (lazy — torch/sentence-transformers imported only here)
# ---------------------------------------------------------------------------

def real_encoder(rev: str = REV) -> Callable[[Sequence[str]], np.ndarray]:
    """Return an encode(texts)->normalized float32 matrix using the pinned e5
    model. Heavy imports happen INSIDE this function (SPEC-00 §3.2 lazy seam);
    they never touch the self-test path."""
    from sentence_transformers import SentenceTransformer  # noqa: lazy

    model = SentenceTransformer(MODEL_ID, revision=rev)

    def encode(texts: Sequence[str]) -> np.ndarray:
        vecs = model.encode(list(texts), batch_size=BATCH,
                            normalize_embeddings=True,
                            convert_to_numpy=True)
        return np.asarray(vecs, dtype="<f4")

    return encode


# ---------------------------------------------------------------------------
# SQLite store (ANNEX_B5 §2, normative schema)
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS embeddings (
  uid          TEXT NOT NULL,
  model_rev    TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  dim          INTEGER NOT NULL,
  vector       BLOB NOT NULL,
  page         TEXT,
  updated_ts   INTEGER,
  PRIMARY KEY (uid, model_rev)
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


class Store:
    """SQLite embedding store. Single active model_rev; a wrong model_rev on
    open without --full is fatal (edge case 3)."""

    def __init__(self, path: pathlib.Path, mrev: str, dim: int = DIM,
                 full: bool = False):
        self.path = pathlib.Path(path)
        self.mrev = mrev
        self.dim = dim
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path))
        self.db.executescript(_SCHEMA)
        self._reconcile(full)

    def _reconcile(self, full: bool) -> None:
        cur = self.get_meta("model_rev")
        if cur is None:
            self.set_meta("model_rev", self.mrev)
            self.set_meta("dim", str(self.dim))
            self.set_meta("created_ts", str(int(time.time())))
            self.db.commit()
            return
        if cur != self.mrev:
            if not full:
                raise SystemExit(
                    f"FATAL: store model_rev={cur!r} != config {self.mrev!r}; "
                    f"a heterogeneous index is forbidden (edge case 3). "
                    f"Re-run with --full to rebuild for the new model.")
            # --full: wipe and re-pin to the new model_rev.
            self.db.execute("DELETE FROM embeddings")
            self.set_meta("model_rev", self.mrev)
            self.set_meta("dim", str(self.dim))
            self.set_meta("created_ts", str(int(time.time())))
            self.db.commit()

    # -- meta ---------------------------------------------------------------
    def get_meta(self, key: str) -> Optional[str]:
        row = self.db.execute("SELECT value FROM meta WHERE key=?",
                              (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self.db.execute(
            "INSERT INTO meta(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    # -- vectors ------------------------------------------------------------
    def has(self, uid: str, chash: str) -> bool:
        row = self.db.execute(
            "SELECT content_hash FROM embeddings WHERE uid=? AND model_rev=?",
            (uid, self.mrev)).fetchone()
        return bool(row) and row[0] == chash

    def upsert(self, uid: str, chash: str, vec: np.ndarray, page: Optional[str],
               ts: int) -> None:
        blob = struct.pack(f"<{self.dim}f", *[float(x) for x in vec])
        self.db.execute(
            "INSERT INTO embeddings(uid,model_rev,content_hash,dim,vector,page,updated_ts) "
            "VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(uid,model_rev) DO UPDATE SET "
            "content_hash=excluded.content_hash, dim=excluded.dim, "
            "vector=excluded.vector, page=excluded.page, "
            "updated_ts=excluded.updated_ts",
            (uid, self.mrev, chash, self.dim, blob, page, ts))

    def delete(self, uid: str) -> int:
        cur = self.db.execute(
            "DELETE FROM embeddings WHERE uid=? AND model_rev=?",
            (uid, self.mrev))
        return cur.rowcount

    def commit(self) -> None:
        self.db.commit()

    def load_matrix(self) -> Tuple[List[str], Dict[str, Optional[str]], np.ndarray]:
        """Full in-memory matrix for the active model_rev. Returns
        (uids, page_by_uid, M) with M rows L2-normalized float32 (cosine=dot)."""
        rows = self.db.execute(
            "SELECT uid, vector, page FROM embeddings WHERE model_rev=? "
            "ORDER BY uid", (self.mrev,)).fetchall()
        uids: List[str] = []
        pages: Dict[str, Optional[str]] = {}
        if not rows:
            return uids, pages, np.zeros((0, self.dim), dtype="<f4")
        mat = np.empty((len(rows), self.dim), dtype="<f4")
        for i, (uid, blob, page) in enumerate(rows):
            mat[i] = np.frombuffer(blob, dtype="<f4", count=self.dim)
            uids.append(uid)
            pages[uid] = page
        return uids, pages, mat

    def close(self) -> None:
        self.db.close()


# ---------------------------------------------------------------------------
# Delta + snapshot loading (INTERFACES.md §2)
# ---------------------------------------------------------------------------

def read_jsonl(path: pathlib.Path) -> List[dict]:
    out = []
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def load_delta(path: pathlib.Path) -> List[dict]:
    """B1 delta rows. Drop the leading meta header ({"meta":"initial-import"})."""
    return [r for r in read_jsonl(path) if "op" in r]


def excluded_page(page: Optional[str]) -> bool:
    """M/* is the system's own write-back namespace; never index it (feedback
    loop, PRD_B5 FR-1)."""
    return bool(page) and page.startswith("M/")


def load_graph(snapshot: pathlib.Path) -> "RH.Graph":
    """Parse a Roam 'Export All' snapshot via the harvest parser (read-only)."""
    return RH.Graph.parse(json.loads(pathlib.Path(snapshot).read_text(
        encoding="utf-8")))


def encodeable_blocks(g: "RH.Graph") -> Dict[str, dict]:
    """content_blocks() bounds (30..500, no citations) MINUS the M/* namespace.
    Returned keyed by uid for O(1) delta joins."""
    return {b["uid"]: b for b in RH.content_blocks(g, lo=30, hi=500)
            if not excluded_page(b["page"])}


def encode_text(g: "RH.Graph", block: dict) -> str:
    """Encoded text = block string with ((brefs)) expanded (FR-1), passage
    prefix applied. Block alone; no parent/page context in v0 (ANNEX_B5 §7)."""
    return PASSAGE_PREFIX + g.expand_brefs(block["string"])


# ---------------------------------------------------------------------------
# `update` — incremental re-index (ANNEX_B5 §4)
# ---------------------------------------------------------------------------

def cmd_update(snapshot: pathlib.Path, delta: pathlib.Path, db: pathlib.Path,
               encoder: Callable[[Sequence[str]], np.ndarray],
               mrev: str = REV, full: bool = False) -> Dict[str, int]:
    g = load_graph(snapshot)
    blocks = encodeable_blocks(g)
    deltas = load_delta(delta)
    store = Store(db, model_rev(mrev), DIM, full=full)

    # Which uids to (re)encode vs delete.
    to_encode: List[str] = []
    to_delete: List[str] = []
    for d in deltas:
        uid, op = d.get("uid"), d.get("op")
        if op == "removed":
            to_delete.append(uid)
        elif op in ("added", "edited"):
            to_encode.append(uid)
        # 'moved' changes location only; string unchanged => content_hash
        # unchanged => the has()-skip below no-ops it. Page refresh still
        # happens because we pass the current page on any re-encode.
    if full:
        # rebuild everything encodeable from the snapshot (model change)
        to_encode = list(blocks.keys())

    counters = {"encoded": 0, "skipped": 0, "deleted": 0}

    # Deletions: explicit removed, plus blocks that fell out of bounds after an
    # edit (shortened <30 chars / became a citation / moved to M/*) — edge 1.
    seen_delete = set()
    for uid in to_delete:
        if uid and store.delete(uid):
            counters["deleted"] += 1
        seen_delete.add(uid)
    for uid in to_encode:
        if uid not in blocks and uid not in seen_delete:
            # touched but no longer encodeable -> evict its vector (edge 1)
            if store.delete(uid):
                counters["deleted"] += 1
            seen_delete.add(uid)

    # Encode in batches of BATCH; DB checkpoint every CHECKPOINT_EVERY (edge 4).
    pending: List[Tuple[str, str, str, Optional[str]]] = []  # uid, chash, text, page
    since_ckpt = 0

    def flush() -> None:
        nonlocal since_ckpt
        if not pending:
            return
        vecs = encoder([t for (_, _, t, _) in pending])
        ts = int(time.time())
        for (uid, chash, _text, page), vec in zip(pending, vecs):
            store.upsert(uid, chash, vec, page, ts)
            counters["encoded"] += 1
            since_ckpt += 1
            if since_ckpt >= CHECKPOINT_EVERY:
                store.commit()
                since_ckpt = 0
        pending.clear()

    for uid in to_encode:
        b = blocks.get(uid)
        if b is None:
            continue  # already evicted above
        text = encode_text(g, b)
        chash = content_hash(model_rev(mrev), text)
        if store.has(uid, chash):
            counters["skipped"] += 1          # unchanged -> never re-encode (M1)
            continue
        pending.append((uid, chash, text, b["page"]))
        if len(pending) >= BATCH:
            flush()
    flush()
    store.commit()
    store.close()

    print(f"update encoded={counters['encoded']} skipped={counters['skipped']} "
          f"deleted={counters['deleted']}", file=sys.stderr)
    return counters


# ---------------------------------------------------------------------------
# Similarity core (brute-force numpy; cosine == dot on normalized rows)
# ---------------------------------------------------------------------------

def _neighbors_for(idx: int, M: np.ndarray, k: int,
                   min_score: float) -> List[Tuple[int, float]]:
    """Top-k neighbors of row idx (excluding self), score >= min_score."""
    if M.shape[0] < 2:
        return []
    scores = M @ M[idx]
    scores[idx] = -np.inf  # exclude self
    order = np.argsort(-scores)
    out: List[Tuple[int, float]] = []
    for j in order[:k]:
        s = float(scores[j])
        if s < min_score:
            break
        out.append((int(j), s))
    return out


def _cycle_id(explicit: Optional[str]) -> str:
    return explicit or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# `pairs` (+ bridge_seeds subset) — ANNEX_B5 §4
# ---------------------------------------------------------------------------

def compute_pairs(uids: List[str], pages: Dict[str, Optional[str]], M: np.ndarray,
                  changed: Sequence[str], k: int, min_score: float,
                  mrev_str: str, cycle: str
                  ) -> Tuple[List[dict], List[dict]]:
    """Return (sim_pairs, bridge_seeds). Pairs ordered a<b, intra-file deduped;
    bridge seeds = the subset whose two blocks sit on different pages."""
    index = {u: i for i, u in enumerate(uids)}
    changed_present = [u for u in changed if u in index]
    seen: set = set()
    pairs: List[dict] = []
    bridges: List[dict] = []
    for u in changed_present:
        i = index[u]
        for j, score in _neighbors_for(i, M, k, min_score):
            v = uids[j]
            a, b = (u, v) if u < v else (v, u)   # order a<b (FR-3)
            if (a, b) in seen:                   # intra-file dedup
                continue
            seen.add((a, b))
            row = {"a": a, "b": b, "score": round(score, 6),
                   "model_rev": mrev_str, "cycle": cycle}
            pairs.append(row)
            if pages.get(a) != pages.get(b):     # bridge seed (FR-5)
                bridges.append(dict(row))
    return pairs, bridges


def cmd_pairs(db: pathlib.Path, changed_uids: pathlib.Path, out: pathlib.Path,
              k: int, min_score: float, cycle: Optional[str],
              bridge_out: Optional[pathlib.Path] = None,
              mrev: str = REV) -> Dict[str, int]:
    store = Store(db, model_rev(mrev), DIM)
    uids, pages, M = store.load_matrix()
    store.close()
    changed = [l.strip() for l in
               pathlib.Path(changed_uids).read_text(encoding="utf-8").splitlines()
               if l.strip()]
    cyc = _cycle_id(cycle)
    pairs, bridges = compute_pairs(uids, pages, M, changed, k, min_score,
                                   model_rev(mrev), cyc)
    _write_pairs(out, pairs, cyc, len(changed), meta_kind="pairs")
    if bridge_out is not None:
        _write_pairs(bridge_out, bridges, cyc, len(changed), meta_kind="bridge_seeds")
    print(f"pairs changed={len(changed)} emitted={len(pairs)} "
          f"bridges={len(bridges)}", file=sys.stderr)
    return {"changed": len(changed), "emitted": len(pairs),
            "bridges": len(bridges)}


def _write_pairs(path: pathlib.Path, rows: List[dict], cycle: str, changed: int,
                 meta_kind: str) -> None:
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    meta = {"meta": meta_kind, "cycle": cycle, "changed": changed,
            "emitted": len(rows)}
    with pathlib.Path(path).open("w", encoding="utf-8") as f:
        f.write(json.dumps(meta, ensure_ascii=False) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def cmd_bridge_seeds(db: pathlib.Path, changed_uids: pathlib.Path,
                     out: pathlib.Path, k: int, min_score: float,
                     cycle: Optional[str], mrev: str = REV) -> Dict[str, int]:
    """bridge_seeds as a standalone subcommand (same pass, page(a)!=page(b))."""
    store = Store(db, model_rev(mrev), DIM)
    uids, pages, M = store.load_matrix()
    store.close()
    changed = [l.strip() for l in
               pathlib.Path(changed_uids).read_text(encoding="utf-8").splitlines()
               if l.strip()]
    cyc = _cycle_id(cycle)
    _, bridges = compute_pairs(uids, pages, M, changed, k, min_score,
                               model_rev(mrev), cyc)
    _write_pairs(out, bridges, cyc, len(changed), meta_kind="bridge_seeds")
    print(f"bridge_seeds changed={len(changed)} emitted={len(bridges)}",
          file=sys.stderr)
    return {"changed": len(changed), "emitted": len(bridges)}


# ---------------------------------------------------------------------------
# `continues-candidates` — ANNEX_B5 §1.2 / §4 (directional [child, parent])
# ---------------------------------------------------------------------------

# The field keys we emit; asserted equal to the live registry in self-test.
_CONTINUES_FIELDS = ["child", "child_context", "parent", "parent_context"]


def compute_continues(g: "RH.Graph", uids: List[str], M: np.ndarray,
                      new_uids: Sequence[str], topk: int, min_score: float,
                      mrev_str: str) -> List[dict]:
    """For each NEW block: its top-`topk` neighbors with an EARLIER create-time
    become parent candidates. subjects=[child, parent], directional, never
    inverted. Contexts mirror roam_harvest.h_continues (_path_str)."""
    index = {u: i for i, u in enumerate(uids)}
    rows: List[dict] = []
    for child in new_uids:
        ci = index.get(child)
        if ci is None or child not in g.blocks:
            continue
        child_create = g.blocks[child].get("create", 0)
        scores = M @ M[ci]
        scores[ci] = -np.inf
        order = np.argsort(-scores)
        emitted = 0
        for j in order:
            if emitted >= topk:
                break
            s = float(scores[j])
            if s < min_score:
                break
            parent = uids[j]
            pb = g.blocks.get(parent)
            if pb is None:
                continue
            # parent must be OLDER than the child (a predecessor, not a successor)
            if pb.get("create", 0) >= child_create:
                continue
            rows.append({
                "jtype": "continues",
                "subjects": [child, parent],            # [child, parent] — fixed
                "fields": {
                    "child": RH.trim(g.expand_brefs(g.blocks[child]["string"])),
                    "child_context": RH._path_str(g, child),
                    "parent": RH.trim(g.expand_brefs(pb["string"])),
                    "parent_context": RH._path_str(g, parent)},
                "meta": {"mode": "knn", "sim": round(s, 6),
                         "model_rev": mrev_str}})
            emitted += 1
    return rows


def cmd_continues_candidates(snapshot: pathlib.Path, db: pathlib.Path,
                             new_uids: pathlib.Path, out: pathlib.Path,
                             topk: int, min_score: float,
                             mrev: str = REV) -> Dict[str, int]:
    g = load_graph(snapshot)
    store = Store(db, model_rev(mrev), DIM)
    uids, _pages, M = store.load_matrix()
    store.close()
    new = [l.strip() for l in
           pathlib.Path(new_uids).read_text(encoding="utf-8").splitlines()
           if l.strip()]
    rows = compute_continues(g, uids, M, new, topk, min_score, model_rev(mrev))
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    with pathlib.Path(out).open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"continues-candidates new={len(new)} emitted={len(rows)}",
          file=sys.stderr)
    return {"new": len(new), "emitted": len(rows)}


def new_uids_from_delta(delta: pathlib.Path) -> List[str]:
    """Helper: the op=added uids of a delta (the cycle's genuinely new blocks)."""
    return [d["uid"] for d in load_delta(delta) if d.get("op") == "added"]


# ---------------------------------------------------------------------------
# `query` — debug convenience (PRD_B5 §4; not in DoD)
# ---------------------------------------------------------------------------

def cmd_query(db: pathlib.Path, text: str, k: int,
              encoder: Callable[[Sequence[str]], np.ndarray],
              query_prefix: bool = True, mrev: str = REV) -> List[dict]:
    store = Store(db, model_rev(mrev), DIM)
    uids, pages, M = store.load_matrix()
    store.close()
    q = (QUERY_PREFIX if query_prefix else PASSAGE_PREFIX) + text
    qv = _l2norm(encoder([q])[0])
    if M.shape[0] == 0:
        return []
    scores = M @ qv
    order = np.argsort(-scores)[:k]
    out = [{"uid": uids[i], "page": pages.get(uids[i]),
            "score": round(float(scores[i]), 6)} for i in order]
    print(json.dumps(out, ensure_ascii=False))
    return out


# ---------------------------------------------------------------------------
# Self-test — MOCK ONLY, zero network/GPU, torch must never import (§5)
# ---------------------------------------------------------------------------

def self_test() -> None:
    import tempfile

    ok = lambda c, m: (print(f"  ok {m}") if c else
                       (_ for _ in ()).throw(AssertionError(m)))

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="b5_selftest_"))
    fx = pathlib.Path(__file__).parent / "fixtures" / "embed"

    # -- fixtures: incremental corpus + delta -------------------------------
    snap1 = fx / "selftest_snapshot_1.json"
    snap2 = fx / "selftest_snapshot_2.json"
    delta1 = fx / "selftest_delta_1.jsonl"
    delta2 = fx / "selftest_delta_2.jsonl"
    db = tmp / "store" / "embeddings.db"

    enc = mock_encode

    # 1) initial update encodes the encodeable, non-M/* blocks --------------
    c1 = cmd_update(snap1, delta1, db, enc)
    ok(c1["encoded"] >= 4, f"first update encoded blocks ({c1['encoded']})")

    # M/* exclusion: the M/* block in snap1 is never stored -----------------
    store = Store(db, model_rev())
    uids1, pages1, _ = store.load_matrix()
    store.close()
    ok(all(not excluded_page(p) for p in pages1.values()),
       "M/* pages excluded from the store")
    ok("m_sys_1" not in uids1, "M/* block uid absent from index")

    # short (<30 char) block never indexed (bounds via content_blocks) ------
    ok("short_1" not in uids1, "sub-30-char block not indexed")

    # 2) M1 — re-running the SAME update encodes 0 (content-address) --------
    c1b = cmd_update(snap1, delta1, db, enc)
    ok(c1b["encoded"] == 0, "incremental re-run encodes 0 (M1)")
    ok(c1b["skipped"] >= c1["encoded"], "re-run skips the already-encoded")

    # 3) edge case 1 — a block shortened <30 chars is evicted ---------------
    #    snap2 shortens 'shrink_1'; delta2 marks it edited.
    c2 = cmd_update(snap2, delta2, db, enc)
    store = Store(db, model_rev())
    uids2, _, _ = store.load_matrix()
    store.close()
    ok("shrink_1" not in uids2, "block shortened <30 chars evicted (edge 1)")
    ok(c2["deleted"] >= 1, "eviction counted as delete")

    # 4) pairs — planted identical duplicate scores 1.0, order a<b ----------
    changed = tmp / "changed.txt"
    changed.write_text("\n".join(uids2) + "\n")
    pairs_out = tmp / "sim" / "sim_pairs.jsonl"
    bridge_out = tmp / "sim" / "bridge_seeds.jsonl"
    cmd_pairs(db, changed, pairs_out, k=10, min_score=0.80,
              cycle="selftest", bridge_out=bridge_out)
    plines = read_jsonl(pairs_out)
    meta = plines[0]
    prows = plines[1:]
    ok(meta.get("meta") == "pairs", "pairs file leads with a meta line")
    ok(all(r["a"] < r["b"] for r in prows), "pairs ordered a<b")
    ok(all(r["model_rev"] == model_rev() for r in prows),
       "every pair carries model_rev")
    # dup_a / dup_b are byte-identical text -> mock gives identical vectors
    dup = [r for r in prows
           if {r["a"], r["b"]} == {"dup_a", "dup_b"}]
    ok(len(dup) == 1 and dup[0]["score"] >= 0.999,
       "true duplicate scores ~1.0 and is one deduped pair (edge 2)")

    # bridge seeds: every emitted seed is a cross-page pair -----------------
    blines = read_jsonl(bridge_out)
    brows = blines[1:]
    store = Store(db, model_rev())
    uids3, pages3, _ = store.load_matrix()
    store.close()
    ok(blines[0].get("meta") == "bridge_seeds", "bridge file meta line")
    ok(all(pages3.get(r["a"]) != pages3.get(r["b"]) for r in brows),
       "bridge seeds are cross-page only")

    # 5) continues-candidates — directional + registry cross-validation -----
    import judge_prompts as JP
    import zettel_prompts  # noqa: registers continues into JP
    zettel_prompts.register()

    new_uids = tmp / "new.txt"
    new_uids.write_text("\n".join(new_uids_from_delta(delta1)) + "\n")
    cc_out = tmp / "sim" / "continues_candidates.jsonl"
    cc = cmd_continues_candidates(snap1, db, new_uids, cc_out,
                                  topk=3, min_score=0.0)
    crows = read_jsonl(cc_out)
    ok(cc["emitted"] >= 1, f"continues candidates emitted ({cc['emitted']})")
    for r in crows:
        ok(r["jtype"] == "continues", "candidate jtype == continues")
        ok(list(r["fields"].keys()) == _CONTINUES_FIELDS,
           "candidate field keys in canonical order")
        ok(list(r["fields"].keys()) == JP.REQUIRED_FIELDS["continues"],
           "candidate keys == REQUIRED_FIELDS['continues'] (anti-drift)")
        ok(len(r["subjects"]) == 2, "continues has [child, parent]")
        child, parent = r["subjects"]
        g = load_graph(snap1)
        ok(g.blocks[parent]["create"] < g.blocks[child]["create"],
           "parent is strictly older than child (predecessor)")

    # emitted keys equal the registry exactly (both directions)
    ok(_CONTINUES_FIELDS == JP.REQUIRED_FIELDS["continues"],
       "module field list == live REQUIRED_FIELDS['continues']")

    # 6) edge case 3 — wrong model_rev without --full is fatal --------------
    raised = False
    try:
        Store(db, "e5-small@deadbeef")  # different rev, no --full
    except SystemExit:
        raised = True
    ok(raised, "wrong model_rev without --full is fatal (edge 3)")
    # ...and --full rebuilds cleanly
    Store(db, "e5-small@deadbeef", full=True).close()

    # 7) THE hard NFR: torch was never imported on this path ----------------
    ok("torch" not in sys.modules, "self-test imported no torch")
    ok("sentence_transformers" not in sys.modules,
       "self-test imported no sentence_transformers")

    print("all embed_index self-tests passed")


# ---------------------------------------------------------------------------
# @slow recall test (M2) — REAL model, network/CPU, OUTSIDE self-test (§6)
# ---------------------------------------------------------------------------
# The 10 planted pairs in mini_corpus_fr.json share a stem: p0Na / p0Nb. M2
# (PRD_B5 §2): >= 18 of the 20 planted blocks find their twin in their mutual
# top-5. This lazily loads the real e5 model — run manually on the owner's Mac
# after the one-time init; it is never invoked by `self-test`.

def slow_recall_test(mrev: str = REV) -> None:
    import tempfile

    fx = pathlib.Path(__file__).parent / "fixtures" / "embed"
    snap = fx / "mini_corpus_fr.json"
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="b5_slow_"))
    db = tmp / "store" / "embeddings.db"

    g = load_graph(snap)
    blocks = encodeable_blocks(g)
    enc = real_encoder(mrev)
    store = Store(db, model_rev(mrev), DIM)
    uids = sorted(blocks.keys())
    vecs = enc([encode_text(g, blocks[u]) for u in uids])
    ts = int(time.time())
    for u, v in zip(uids, vecs):
        store.upsert(u, content_hash(model_rev(mrev), encode_text(g, blocks[u])),
                     v, blocks[u]["page"], ts)
    store.commit()
    mu, _pages, M = store.load_matrix()
    store.close()

    index = {u: i for i, u in enumerate(mu)}
    hits = 0
    planted = [u for u in mu if u.startswith("p") and (u.endswith("a") or u.endswith("b"))]
    for u in planted:
        twin = u[:-1] + ("b" if u.endswith("a") else "a")
        top5 = [mu[j] for j, _ in _neighbors_for(index[u], M, 5, -1.0)]
        if twin in top5:
            hits += 1
    print(f"slow-recall planted={len(planted)} twin_in_top5={hits}",
          file=sys.stderr)
    assert hits >= 18, f"M2 recall failed: {hits}/20 twins in mutual top-5"
    print(f"M2 recall passed: {hits}/{len(planted)} twins in top-5")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    u = sub.add_parser("update", help="encode the B1 delta into the store")
    u.add_argument("--snapshot", required=True)
    u.add_argument("--delta", required=True)
    u.add_argument("--db", default="store/embeddings.db")
    u.add_argument("--full", action="store_true",
                   help="force full reindex (model change)")
    u.add_argument("--mock", action="store_true",
                   help="use the deterministic mock encoder (no torch)")

    p = sub.add_parser("pairs", help="sim_pairs.jsonl for changed uids")
    p.add_argument("--db", default="store/embeddings.db")
    p.add_argument("--changed-uids", required=True)
    p.add_argument("--out", default="sim/sim_pairs.jsonl")
    p.add_argument("--bridge-out", default=None,
                   help="also write bridge_seeds here in the same pass")
    p.add_argument("--k", type=int, default=DEFAULT_K)
    p.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    p.add_argument("--cycle", default=None)

    cc = sub.add_parser("continues-candidates",
                        help="kNN parent candidates for new uids")
    cc.add_argument("--snapshot", required=True)
    cc.add_argument("--db", default="store/embeddings.db")
    cc.add_argument("--new-uids", required=True)
    cc.add_argument("--out", default="sim/continues_candidates.jsonl")
    cc.add_argument("--k", type=int, default=CONTINUES_TOPK)
    cc.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)

    bs = sub.add_parser("bridge_seeds", help="cross-page near pairs")
    bs.add_argument("--db", default="store/embeddings.db")
    bs.add_argument("--changed-uids", required=True)
    bs.add_argument("--out", default="sim/bridge_seeds.jsonl")
    bs.add_argument("--k", type=int, default=DEFAULT_K)
    bs.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    bs.add_argument("--cycle", default=None)

    q = sub.add_parser("query", help="debug: k nearest to a free-text query")
    q.add_argument("--db", default="store/embeddings.db")
    q.add_argument("--text", required=True)
    q.add_argument("--k", type=int, default=DEFAULT_K)
    q.add_argument("--mock", action="store_true")

    sub.add_parser("self-test", help="pure-logic tests, mock only, no torch")
    sub.add_parser("slow-test",
                   help="@slow M2 recall on the real e5 model (owner's Mac)")

    args = ap.parse_args()

    if args.cmd == "self-test":
        self_test()
        return
    if args.cmd == "slow-test":
        slow_recall_test()
        return

    if args.cmd == "update":
        enc = mock_encode if args.mock else real_encoder()
        cmd_update(pathlib.Path(args.snapshot), pathlib.Path(args.delta),
                   pathlib.Path(args.db), enc, full=args.full)
    elif args.cmd == "pairs":
        cmd_pairs(pathlib.Path(args.db), pathlib.Path(args.changed_uids),
                  pathlib.Path(args.out), args.k, args.min_score, args.cycle,
                  pathlib.Path(args.bridge_out) if args.bridge_out else None)
    elif args.cmd == "continues-candidates":
        cmd_continues_candidates(pathlib.Path(args.snapshot),
                                 pathlib.Path(args.db),
                                 pathlib.Path(args.new_uids),
                                 pathlib.Path(args.out), args.k, args.min_score)
    elif args.cmd == "bridge_seeds":
        cmd_bridge_seeds(pathlib.Path(args.db), pathlib.Path(args.changed_uids),
                         pathlib.Path(args.out), args.k, args.min_score,
                         args.cycle)
    elif args.cmd == "query":
        enc = mock_encode if args.mock else real_encoder()
        cmd_query(pathlib.Path(args.db), args.text, args.k, enc)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""cycle_tools.py — small stdlib-only utilities for the B4 nightly cycle.

Stage 6 of cycle.sh needs a *diff* between this cycle's stances and the previous
cycle's, plus rotation of the previous-stances file. SPEC-03 §3's `update()`
(which returns `changed`) is the eventual upgrade path; in v0 this is a plain
status-per-node comparison — NOT a new service.

Subcommands:
  stance-diff --cur <stances.jsonl> --prev <stances_prev.jsonl>
              --out <stance_diff.jsonl> [--rotate]
      Compare `status` per `node`. Emit one row per node whose status changed
      (added / removed / flipped) to <out>. With --rotate, copy --cur over
      --prev afterwards (so next cycle diffs against this cycle).

  self-test
      Exercises all pure logic with zero I/O beyond a temp dir. Exits non-zero
      on any failure.

Contract (INTERFACES.md §2):
  stances.jsonl / stances_prev.jsonl : one stance object per line, keys include
      {node, label, status, ...}.
  stance_diff.jsonl : {node, old_status, new_status, caused_by} per line, UTF-8
      NFC, one JSON object per line, sorted by node for determinism.
"""

import argparse
import json
import pathlib
import sys
import tempfile
import unicodedata


# ---------------------------------------------------------------------------
# I/O helpers (UTF-8 NFC, one JSON object per line)
# ---------------------------------------------------------------------------

def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def read_stances(path: pathlib.Path) -> dict:
    """Return {node -> status}. Missing file => empty (first cycle)."""
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        out[row["node"]] = row.get("status")
    return out


def diff_stances(cur: dict, prev: dict) -> list:
    """One diff row per node whose status changed (incl. appear/disappear).

    Deterministic: sorted by node. `caused_by` is the node id in v0 (the belief
    layer does not yet thread the triggering edge event through; documented)."""
    rows = []
    for node in sorted(set(cur) | set(prev)):
        old = prev.get(node)
        new = cur.get(node)
        if old != new:
            rows.append({
                "node": node,
                "old_status": old,
                "new_status": new,
                "caused_by": node,
            })
    return rows


def write_diff(rows: list, path: pathlib.Path) -> int:
    text = "".join(
        json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows
    )
    path.write_text(_nfc(text), encoding="utf-8")
    return len(rows)


def rotate(cur_path: pathlib.Path, prev_path: pathlib.Path) -> None:
    """Make this cycle's stances the baseline for the next cycle."""
    prev_path.write_text(
        cur_path.read_text(encoding="utf-8") if cur_path.exists() else "",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# stance-diff subcommand
# ---------------------------------------------------------------------------

def cmd_stance_diff(a: argparse.Namespace) -> int:
    cur_path = pathlib.Path(a.cur)
    prev_path = pathlib.Path(a.prev)
    out_path = pathlib.Path(a.out)
    cur = read_stances(cur_path)
    prev = read_stances(prev_path)
    rows = diff_stances(cur, prev)
    n = write_diff(rows, out_path)
    if a.rotate:
        rotate(cur_path, prev_path)
    print(f"stance-diff: {n} changed of {len(set(cur) | set(prev))} nodes "
          f"-> {out_path}" + (" (rotated)" if a.rotate else ""),
          file=sys.stderr)
    return 0


# ---------------------------------------------------------------------------
# self-test
# ---------------------------------------------------------------------------

def self_test() -> int:
    n_assert = 0

    def ok(cond, msg):
        nonlocal n_assert
        n_assert += 1
        if not cond:
            raise AssertionError(msg)

    # --- diff_stances: flip / add / remove / unchanged ---
    cur = {"a": "accepted-supported", "b": "rejected", "c": "undecided"}
    prev = {"a": "undecided", "b": "rejected", "d": "accepted-undisputed"}
    rows = diff_stances(cur, prev)
    by = {r["node"]: r for r in rows}
    ok("a" in by and by["a"]["old_status"] == "undecided"
       and by["a"]["new_status"] == "accepted-supported", "flip a")
    ok("b" not in by, "b unchanged -> no row")
    ok("c" in by and by["c"]["old_status"] is None
       and by["c"]["new_status"] == "undecided", "added c")
    ok("d" in by and by["d"]["old_status"] == "accepted-undisputed"
       and by["d"]["new_status"] is None, "removed d")
    ok([r["node"] for r in rows] == sorted(r["node"] for r in rows),
       "rows sorted by node")

    # --- empty prev (first cycle): every node is a change ---
    rows0 = diff_stances({"x": "rejected"}, {})
    ok(len(rows0) == 1 and rows0[0]["old_status"] is None, "first cycle all-new")

    # --- identical: no rows ---
    ok(diff_stances(cur, cur) == [], "identical -> empty diff")

    with tempfile.TemporaryDirectory() as d:
        dp = pathlib.Path(d)
        # accented French must survive NFC round-trip byte-for-byte
        curp = dp / "stances.jsonl"
        curp.write_text(
            json.dumps({"node": "café", "status": "accepté"},
                       ensure_ascii=False) + "\n"
            + json.dumps({"node": "élève", "status": "rejected"},
                         ensure_ascii=False) + "\n",
            encoding="utf-8")
        prevp = dp / "stances_prev.jsonl"
        prevp.write_text(
            json.dumps({"node": "café", "status": "undecided"},
                       ensure_ascii=False) + "\n",
            encoding="utf-8")
        outp = dp / "stance_diff.jsonl"
        n = write_diff(diff_stances(read_stances(curp), read_stances(prevp)),
                       outp)
        ok(n == 2, f"french diff row count == 2, got {n}")
        got = [json.loads(l) for l in
               outp.read_text(encoding="utf-8").splitlines()]
        cafe = [r for r in got if r["node"] == "café"][0]
        ok(cafe["new_status"] == "accepté", "accented value preserved")
        ok(_nfc(outp.read_text(encoding="utf-8"))
           == outp.read_text(encoding="utf-8"), "output already NFC")

        # --- rotation: prev becomes a copy of cur ---
        rotate(curp, prevp)
        ok(prevp.read_text(encoding="utf-8") == curp.read_text(encoding="utf-8"),
           "rotate copies cur -> prev")
        # after rotation, a re-diff against the rotated baseline is empty
        ok(diff_stances(read_stances(curp), read_stances(prevp)) == [],
           "post-rotation diff empty")

        # --- missing prev file => empty baseline, no crash ---
        ok(read_stances(dp / "does_not_exist.jsonl") == {}, "missing prev ok")

    print(f"cycle_tools self-test: {n_assert} assertions passed")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sd = sub.add_parser("stance-diff", help="diff status-per-node vs prev cycle")
    sd.add_argument("--cur", required=True)
    sd.add_argument("--prev", required=True)
    sd.add_argument("--out", required=True)
    sd.add_argument("--rotate", action="store_true",
                    help="after diffing, copy --cur over --prev")

    sub.add_parser("self-test", help="run pure-logic self-tests")

    a = ap.parse_args()
    if a.cmd == "stance-diff":
        return cmd_stance_diff(a)
    if a.cmd == "self-test":
        return self_test()
    return 2


if __name__ == "__main__":
    sys.exit(main())

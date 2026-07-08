#!/usr/bin/env python3
"""calset_merge.py — reusable review_resolved → calset merge (B3, from B0 shell).

Extracts the inline Python of `first_judge.sh` stage 4 (lines ~78–96) into a
single, self-tested function. The shell block reads `review_resolved.jsonl`
rows `{"jtype","fields","gold"}`, stamps each with `provenance.source="human"`,
and appends them to the matching `calset_<jtype>.jsonl`.

That merge is the LAST hop of the B3 `review` task type: a human answers a
review task in Roam via a closed tag, `task_harvest` emits it, ingest.clj
rewrites it into `review_resolved.jsonl` (an EXPORT, not a domain effect — CALM
split), and this merge folds the human gold into the frozen-later calset.

Contract (INTERFACES.md):
  input  `review_resolved.jsonl`  rows  {"jtype","fields","gold"}
  output `calset_<jtype>.jsonl`    rows  {..., "provenance":{"source":"human"}}

This module does NOT edit first_judge.sh (another concern owns shell files).
first_judge.sh could later replace its inline heredoc with:

    python3 calset_merge.py merge --review-resolved $WORK/review_resolved.jsonl \\
        --calset-dir $CAL

Behaviour is byte-compatible with the current shell block: it preserves any
provenance already present (only `setdefault`-ing the dict and forcing
`source`), appends (never truncates), and groups by jtype.
"""

from __future__ import annotations
import argparse
import json
import pathlib
import sys
from typing import Dict, List, Tuple


def _calset_path(calset_dir: pathlib.Path, jtype: str) -> pathlib.Path:
    return calset_dir / f"calset_{jtype}.jsonl"


def merge_review_resolved(review_resolved_path,
                          calset_path=None,
                          *,
                          calset_dir=None) -> Dict[str, int]:
    """Fold human-resolved review rows into calset(s) with human provenance.

    Two calling conventions:
      * single-file: pass `calset_path` — ALL rows are appended there
        (used by self-test and callers that already know the target file).
      * per-jtype:   pass `calset_dir` — rows are grouped by `jtype` and
        appended to `calset_<jtype>.jsonl` under that dir (the shell's mode).

    Each merged row gets `provenance.source = "human"` (existing provenance
    keys are preserved). Appends; never truncates. Returns {jtype: n_merged}.
    Missing / empty input → {} (mirrors the shell's early skip).
    """
    rp = pathlib.Path(review_resolved_path)
    if not rp.exists():
        return {}

    by: Dict[str, List[dict]] = {}
    for line in rp.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        r.setdefault("provenance", {})["source"] = "human"
        by.setdefault(r["jtype"], []).append(r)

    if not by:
        return {}

    counts: Dict[str, int] = {}
    if calset_path is not None:
        # single-file mode: everything goes to one calset
        p = pathlib.Path(calset_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            for jt, rows in by.items():
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
                counts[jt] = counts.get(jt, 0) + len(rows)
    else:
        if calset_dir is None:
            raise ValueError("pass either calset_path or calset_dir")
        d = pathlib.Path(calset_dir)
        d.mkdir(parents=True, exist_ok=True)
        for jt, rows in by.items():
            p = _calset_path(d, jt)
            with p.open("a", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            counts[jt] = len(rows)
            print(f"  merged {len(rows)} human rows into {p.name}",
                  file=sys.stderr)
    return counts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def cmd_merge(args) -> None:
    if args.calset:
        counts = merge_review_resolved(args.review_resolved,
                                       calset_path=args.calset)
    else:
        counts = merge_review_resolved(args.review_resolved,
                                       calset_dir=args.calset_dir)
    print(json.dumps(counts, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Self-test (pure; no network). Run: python3 calset_merge.py self-test
# ---------------------------------------------------------------------------
def _self_test() -> None:
    import tempfile
    ok = lambda c, m: (print(f"  ✓ {m}") if c else
                       (_ for _ in ()).throw(AssertionError(m)))

    with tempfile.TemporaryDirectory() as td:
        d = pathlib.Path(td)

        # --- empty / missing input -> {} -----------------------------------
        ok(merge_review_resolved(d / "nope.jsonl", calset_dir=d) == {},
           "missing review_resolved -> {}")
        (d / "empty.jsonl").write_text("\n  \n")
        ok(merge_review_resolved(d / "empty.jsonl", calset_dir=d) == {},
           "empty review_resolved -> {}")

        # --- per-jtype dir mode --------------------------------------------
        rr = d / "review_resolved.jsonl"
        rr.write_text(
            json.dumps({"jtype": "edge_type",
                        "fields": {"evidence": "e", "claim": "c",
                                   "sibling_evidence": "(none)"},
                        "gold": "supports"}) + "\n" +
            json.dumps({"jtype": "edge_type",
                        "fields": {"evidence": "e2", "claim": "c2",
                                   "sibling_evidence": "(none)"},
                        "gold": "opposes"}) + "\n" +
            json.dumps({"jtype": "continues",
                        "fields": {"child": "x", "child_context": "p",
                                   "parent": "y", "parent_context": "p"},
                        "gold": "continues",
                        "provenance": {"context_hash": "sha256:pre"}}) + "\n",
            encoding="utf-8")
        counts = merge_review_resolved(rr, calset_dir=d)
        ok(counts == {"edge_type": 2, "continues": 1},
           "per-jtype counts correct")

        et = [json.loads(l) for l in
              (d / "calset_edge_type.jsonl").read_text().splitlines() if l.strip()]
        ok(len(et) == 2, "edge_type calset has 2 rows")
        ok(all(r["provenance"]["source"] == "human" for r in et),
           "all merged rows carry provenance.source=human")

        cont = [json.loads(l) for l in
                (d / "calset_continues.jsonl").read_text().splitlines() if l.strip()]
        ok(cont[0]["provenance"]["context_hash"] == "sha256:pre",
           "pre-existing provenance keys preserved")
        ok(cont[0]["provenance"]["source"] == "human",
           "source forced to human even when provenance pre-exists")

        # --- append semantics: second merge grows the file -----------------
        merge_review_resolved(rr, calset_dir=d)
        et2 = [l for l in (d / "calset_edge_type.jsonl").read_text().splitlines()
               if l.strip()]
        ok(len(et2) == 4, "append (not truncate): calset grows on re-merge")

        # --- single-file mode ----------------------------------------------
        one = d / "calset_all.jsonl"
        c2 = merge_review_resolved(rr, calset_path=one)
        rows = [json.loads(l) for l in one.read_text().splitlines() if l.strip()]
        ok(sum(c2.values()) == 3 and len(rows) == 3,
           "single-file mode writes all rows to one calset")
        ok(all(r["provenance"]["source"] == "human" for r in rows),
           "single-file rows carry human provenance")

    print("all calset_merge self-tests passed")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("merge", help="merge review_resolved into calset(s)")
    m.add_argument("--review-resolved", required=True)
    g = m.add_mutually_exclusive_group(required=True)
    g.add_argument("--calset", help="single target calset file")
    g.add_argument("--calset-dir", help="dir holding calset_<jtype>.jsonl")
    sub.add_parser("self-test")
    args = ap.parse_args()
    if args.cmd == "self-test":
        _self_test()
    elif args.cmd == "merge":
        cmd_merge(args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""judge_metrics.py — WP-0 metrics report generator (SPEC-01 §8).

Reads an outbox JSONL (judgment.emitted / judgment.abstained events) and
produces first_judge_report.json + .md with the decision-gate metrics:
abstention rate, label distribution, confidence deciles, prediction-set
profile, throughput, and (optionally) calset↔live leakage check via the
context store and frozen calset hashes.

Usage:
  python3 judge_metrics.py report --outbox ops/first_judge/outbox.jsonl \
      [--contexts ops/first_judge/contexts.jsonl] \
      [--calsets calset_a.jsonl calset_b.jsonl] \
      [--out-prefix ops/first_judge/first_judge_report]
  python3 judge_metrics.py self-test
"""

from __future__ import annotations
import argparse
import datetime as _dt
import json
import pathlib
import statistics
from collections import Counter, defaultdict
from typing import Dict, List, Optional

GATES = [  # (max_abstention_exclusive, verdict, action) — SPEC-01 §8
    (0.10, "SUSPICIOUS-LOW", "audit for calset/live leakage and q-hat sanity before celebrating"),
    (0.35, "HEALTHY", "proceed to Phase 2 (panel + tuning) as-is"),
    (0.60, "USABLE-EXPENSIVE", "discuss alpha=0.10-with-panel or a larger judge in Phase 2"),
    (1.01, "UNINFORMATIVE", "inspect 20 abstentions: 2-label sets => more gold; full sets => larger model"),
]


def _load(path: Optional[pathlib.Path]) -> List[dict]:
    if not path or not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def _ts(ev: dict) -> Optional[float]:
    try:
        return _dt.datetime.fromisoformat(ev["ts"]).timestamp()
    except Exception:
        return None


def deciles(xs: List[float]) -> List[float]:
    if not xs:
        return []
    if len(xs) == 1:
        return [round(xs[0], 3)] * 11
    return [round(q, 3) for q in statistics.quantiles(xs, n=10, method="inclusive")]


def gate(abst_rate: float) -> dict:
    for hi, verdict, action in GATES:
        if abst_rate < hi:
            return {"verdict": verdict, "action": action}
    return {"verdict": "?", "action": "?"}


def build_report(outbox: List[dict], contexts: List[dict],
                 calsets: List[List[dict]]) -> dict:
    by_type: Dict[str, dict] = {}
    events = [e for e in outbox if e.get("event", "").startswith("judgment.")]
    for jt in sorted({e["jtype"] for e in events}):
        evs = [e for e in events if e["jtype"] == jt]
        em = [e for e in evs if e["event"] == "judgment.emitted"]
        ab = [e for e in evs if e["event"] == "judgment.abstained"]
        n = len(em) + len(ab)
        rate = len(ab) / n if n else 0.0
        tss = sorted(t for t in (_ts(e) for e in evs) if t)
        span_min = (tss[-1] - tss[0]) / 60 if len(tss) > 1 else 0.0
        psizes = Counter(len(e.get("prediction_set", [])) for e in ab)
        by_type[jt] = {
            "attempted": n, "emitted": len(em), "abstained": len(ab),
            "abstention_rate": round(rate, 4),
            "gate": gate(rate) if n >= 50 else
                    {"verdict": "N-TOO-SMALL", "action": f"n={n}<50; gather more before reading gates"},
            "label_distribution": dict(Counter(e["label"] for e in em)),
            "confidence_deciles": deciles([e["confidence"] for e in em]),
            "mean_confidence": round(statistics.mean(
                [e["confidence"] for e in em]), 4) if em else None,
            "prediction_set_sizes": {str(k): v for k, v in sorted(psizes.items())},
            "order_disagreements": sum(1 for e in ab if e.get("order_disagreement")),
            "throughput_per_min": round(n / span_min, 1) if span_min > 0 else None,
        }
    # leakage check: live context hashes seen in any calset provenance
    leak = None
    if contexts and calsets:
        live = {c["context_hash"] for c in contexts}
        cal = {r.get("provenance", {}).get("context_hash")
               for cs in calsets for r in cs} - {None}
        leak = sorted(live & cal)
    return {"generated": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "by_type": by_type,
            "leakage": {"n": len(leak), "hashes": leak[:20]} if leak is not None else None}


def to_md(rep: dict) -> str:
    out = [f"# First-judge metrics report", f"*generated {rep['generated']}*", ""]
    for jt, m in rep["by_type"].items():
        g = m["gate"]
        out += [f"## {jt}",
                f"- attempted **{m['attempted']}** · emitted {m['emitted']} · "
                f"abstained {m['abstained']} → **abstention {m['abstention_rate']:.1%}**",
                f"- gate verdict: **{g['verdict']}** — {g['action']}",
                f"- labels: {json.dumps(m['label_distribution'])}",
                f"- mean confidence {m['mean_confidence']} · deciles {m['confidence_deciles']}",
                f"- abstention prediction-set sizes: {json.dumps(m['prediction_set_sizes'])}"
                f" · order-disagreements {m['order_disagreements']}",
                f"- throughput ≈ {m['throughput_per_min']} judgments/min", ""]
    if rep.get("leakage") is not None:
        out += [f"## Leakage check", f"- shared calset/live context hashes: "
                f"**{rep['leakage']['n']}** (must be 0)", ""]
    return "\n".join(out)


def self_test() -> None:
    ok = lambda c, m: (print(f"  ✓ {m}") if c else
                       (_ for _ in ()).throw(AssertionError(m)))
    T0 = "2026-06-15T10:00:00+00:00"
    T9 = "2026-06-15T10:10:00+00:00"
    em = lambda lab, conf, ts: {"event": "judgment.emitted", "jtype": "edge_type",
                                "label": lab, "confidence": conf, "ts": ts}
    ab = lambda ps, ts, od=False: {"event": "judgment.abstained", "jtype": "edge_type",
                                   "prediction_set": ps, "ts": ts,
                                   "order_disagreement": od}
    outbox = ([em("supports", 0.9, T0)] * 60 + [em("opposes", 0.8, T0)] * 20
              + [ab(["supports", "refines"], T9)] * 15
              + [ab(["supports", "refines", "opposes", "unrelated"], T9, True)] * 5)
    rep = build_report(outbox, [], [])
    m = rep["by_type"]["edge_type"]
    ok(m["attempted"] == 100 and m["abstained"] == 20, "counts")
    ok(abs(m["abstention_rate"] - 0.20) < 1e-9, "abstention rate 0.20")
    ok(m["gate"]["verdict"] == "HEALTHY", "gate: 20% => HEALTHY")
    ok(m["label_distribution"] == {"supports": 60, "opposes": 20}, "labels")
    ok(m["prediction_set_sizes"] == {"2": 15, "4": 5}, "pred-set profile")
    ok(m["order_disagreements"] == 5, "order disagreements counted")
    ok(m["throughput_per_min"] == 10.0, "throughput from ts span")
    # small-n and gate boundaries
    rep2 = build_report(outbox[:40], [], [])
    ok(rep2["by_type"]["edge_type"]["gate"]["verdict"] == "N-TOO-SMALL", "n<50 guard")
    ok(gate(0.05)["verdict"] == "SUSPICIOUS-LOW" and gate(0.5)["verdict"] == "USABLE-EXPENSIVE"
       and gate(0.7)["verdict"] == "UNINFORMATIVE", "gate boundaries")
    # leakage
    ctx = [{"context_hash": "h1"}, {"context_hash": "h2"}]
    cal = [[{"provenance": {"context_hash": "h2"}}]]
    rep3 = build_report(outbox, ctx, cal)
    ok(rep3["leakage"]["n"] == 1 and rep3["leakage"]["hashes"] == ["h2"], "leakage detected")
    ok("HEALTHY" in to_md(rep), "markdown renders")
    print("all judge_metrics self-tests passed")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report")
    r.add_argument("--outbox", required=True)
    r.add_argument("--contexts", default=None)
    r.add_argument("--calsets", nargs="*", default=[])
    r.add_argument("--out-prefix", default="first_judge_report")
    sub.add_parser("self-test")
    a = ap.parse_args()
    if a.cmd == "self-test":
        self_test(); return
    rep = build_report(_load(pathlib.Path(a.outbox)),
                       _load(pathlib.Path(a.contexts)) if a.contexts else [],
                       [_load(pathlib.Path(p)) for p in a.calsets])
    pathlib.Path(a.out_prefix + ".json").write_text(json.dumps(rep, indent=2))
    pathlib.Path(a.out_prefix + ".md").write_text(to_md(rep))
    print(to_md(rep))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""spend.py — B6 spend guard for API-mode inference (PRD_B6 FR-3).

A tiny, stdlib-only cost meter shared by anchor_label.py and infra_check.py.

Model:
  - Per judge, a price {input_per_mtok, output_per_mtok} in USD comes from the
    config (judges_config.yaml `price:` key).
  - Each API call reports (tokens_in, tokens_out); the meter accumulates cost.
  - Every 25 calls (and on final flush) it appends ONE line to the ledger
    (ops/spend.jsonl) — the INTERFACES.md B6 row:
        {"run","judge","calls","tokens_in","tokens_out","usd","ts"}
  - When accumulated USD would exceed `max_usd_per_run`, `add()` returns False
    (cap hit) so the caller stops cleanly with valid partial outputs.
  - Resume after a cap hit: `resume_from_ledger(run, judge, ...)` reads the LAST
    matching line of the run and seeds the meter, so a re-run continues from the
    projected spend rather than double-counting.

No network, no third-party deps. Self-tested via `python3 spend.py self-test`.
"""

from __future__ import annotations
import datetime as _dt
import json
import pathlib
from typing import Optional

FLUSH_EVERY = 25  # ANNEX_B6 §2.2: one ledger line per 25 calls + a final one


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


class SpendMeter:
    """Incremental USD meter with a per-run cap and an append-only ledger."""

    def __init__(self, run: str, judge: str,
                 price_in_per_mtok: float, price_out_per_mtok: float,
                 max_usd_per_run: float, ledger: pathlib.Path,
                 calls0: int = 0, tokens_in0: int = 0, tokens_out0: int = 0,
                 usd0: float = 0.0):
        self.run = run
        self.judge = judge
        self.price_in = float(price_in_per_mtok)
        self.price_out = float(price_out_per_mtok)
        self.max_usd = float(max_usd_per_run)
        self.ledger = pathlib.Path(ledger)
        self.calls = int(calls0)
        self.tokens_in = int(tokens_in0)
        self.tokens_out = int(tokens_out0)
        self.usd = float(usd0)
        self._since_flush = 0

    def cost_of(self, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in / 1_000_000.0) * self.price_in + \
               (tokens_out / 1_000_000.0) * self.price_out

    def would_exceed(self, tokens_in: int, tokens_out: int) -> bool:
        return (self.usd + self.cost_of(tokens_in, tokens_out)) > self.max_usd

    def add(self, tokens_in: int, tokens_out: int) -> bool:
        """Record one call's usage. Returns True if within budget, False if this
        call would breach the cap (caller should stop; nothing is recorded)."""
        if self.would_exceed(tokens_in, tokens_out):
            self.flush()  # persist what we have before stopping
            return False
        self.calls += 1
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.usd += self.cost_of(tokens_in, tokens_out)
        self._since_flush += 1
        if self._since_flush >= FLUSH_EVERY:
            self.flush()
        return True

    def _row(self) -> dict:
        return {"run": self.run, "judge": self.judge, "calls": self.calls,
                "tokens_in": self.tokens_in, "tokens_out": self.tokens_out,
                "usd": round(self.usd, 6), "ts": _now_iso()}

    def flush(self) -> dict:
        """Append the current cumulative totals as one ledger line."""
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        row = self._row()
        with self.ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        self._since_flush = 0
        return row


def resume_from_ledger(run: str, judge: str,
                       price_in_per_mtok: float, price_out_per_mtok: float,
                       max_usd_per_run: float,
                       ledger: pathlib.Path) -> SpendMeter:
    """Build a meter seeded from the LAST ledger line matching (run, judge).
    A fresh run (no prior line) starts at zero. Cumulative rows => reading the
    last one is exact; we never sum lines (they are running totals)."""
    ledger = pathlib.Path(ledger)
    last: Optional[dict] = None
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("run") == run and r.get("judge") == judge:
                last = r
    if last is None:
        return SpendMeter(run, judge, price_in_per_mtok, price_out_per_mtok,
                          max_usd_per_run, ledger)
    return SpendMeter(run, judge, price_in_per_mtok, price_out_per_mtok,
                      max_usd_per_run, ledger,
                      calls0=last["calls"], tokens_in0=last["tokens_in"],
                      tokens_out0=last["tokens_out"], usd0=last["usd"])


def spend_config(cfg: dict) -> dict:
    """Extract {max_usd_per_run, ledger} from a loaded config with defaults."""
    s = (cfg or {}).get("spend", {}) or {}
    return {"max_usd_per_run": float(s.get("max_usd_per_run", 10.0)),
            "ledger": s.get("ledger", "ops/spend.jsonl")}


def judge_price(cfg: dict, judge_name: str) -> dict:
    """Extract {input_per_mtok, output_per_mtok} for a judge, defaulting to 0."""
    p = ((cfg or {}).get("judges", {}).get(judge_name, {}) or {}).get("price", {}) or {}
    return {"input_per_mtok": float(p.get("input_per_mtok", 0.0)),
            "output_per_mtok": float(p.get("output_per_mtok", 0.0))}


# ---------------------------------------------------------------------------
# Self-test (no network, no third-party deps)
# ---------------------------------------------------------------------------

def self_test() -> None:
    import tempfile
    ok = lambda c, msg: (print(f"  ✓ {msg}") if c else
                         (_ for _ in ()).throw(AssertionError(msg)))
    tmp = pathlib.Path(tempfile.mkdtemp())
    led = tmp / "spend.jsonl"

    m = SpendMeter("run-A", "anchor", price_in_per_mtok=1.0,
                   price_out_per_mtok=2.0, max_usd_per_run=1.0, ledger=led)
    ok(abs(m.cost_of(1_000_000, 0) - 1.0) < 1e-9, "input tokens priced per MTok")
    ok(abs(m.cost_of(0, 500_000) - 1.0) < 1e-9, "output tokens priced per MTok")

    # accumulate under budget; ledger flushes every 25 calls
    accepted = 0
    for _ in range(25):
        if m.add(1000, 100):  # 0.0012 USD/call
            accepted += 1
    ok(accepted == 25, "25 calls accepted under a 1.0 USD cap")
    ok(m.calls == 25 and m.tokens_in == 25000, "meter totals correct")
    lines = [json.loads(x) for x in led.read_text().splitlines() if x.strip()]
    ok(len(lines) == 1 and lines[-1]["calls"] == 25,
       "one ledger line flushed at the 25-call boundary")

    # cap hit: a huge call is refused and nothing is recorded for it
    before = m.usd
    ok(m.add(2_000_000, 0) is False, "call breaching the cap is refused")
    ok(abs(m.usd - before) < 1e-12, "refused call does not mutate totals")
    lines = [json.loads(x) for x in led.read_text().splitlines() if x.strip()]
    ok(len(lines) == 2, "cap hit flushes a final ledger line")

    # resume: last line seeds a fresh meter (running totals, not summed)
    m2 = resume_from_ledger("run-A", "anchor", 1.0, 2.0, 5.0, led)
    ok(m2.calls == 25 and abs(m2.usd - m.usd) < 1e-9,
       "resume_from_ledger seeds from the LAST matching line")
    # a different run starts clean
    m3 = resume_from_ledger("run-B", "anchor", 1.0, 2.0, 5.0, led)
    ok(m3.calls == 0 and m3.usd == 0.0, "unknown run resumes at zero")

    # config helpers
    cfg = {"spend": {"max_usd_per_run": 7.5, "ledger": "ops/spend.jsonl"},
           "judges": {"anchor": {"price": {"input_per_mtok": 3.0,
                                           "output_per_mtok": 15.0}}}}
    ok(spend_config(cfg)["max_usd_per_run"] == 7.5, "spend_config reads cap")
    ok(judge_price(cfg, "anchor")["output_per_mtok"] == 15.0,
       "judge_price reads tariff")
    ok(judge_price(cfg, "missing")["input_per_mtok"] == 0.0,
       "missing judge price defaults to 0")
    print("all self-tests passed")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "self-test":
        self_test()
    else:
        print("usage: python3 spend.py self-test", file=__import__("sys").stderr)

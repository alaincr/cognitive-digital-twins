#!/usr/bin/env python3
"""anchor_label.py — turn harvested candidates into gold calibration sets
using the ANCHOR (large) model, per microjudge_contract.md §4 & §7.

  candidates_{jtype}.jsonl ──► anchor_label.py ──► calset_{jtype}.jsonl
                                     │                  (rows consumable by
                                     │                   judge_harness.py calibrate:
                                     │                   {"jtype","fields","gold",…})
                                     └─► review_queue.md  (human spot-check: all
                                          flagged items + ALL T2 'hard' items)

Gold-quality measures built in:
  - The anchor judges THE SAME fenced fields the small judges will see
    (identical conditional — otherwise calibration measures the wrong thing).
  - Per-type expert guidance encodes the contract's policy lines (precision-
    over-recall for same_entity; the lost-qualifier doctrine for faithful; the
    refines-vs-supports distinction; ripeness criteria for summarize_now).
  - `--double`: each item is labeled twice with DIFFERENT (salted) label
    orders; only order-consistent verdicts enter the calset, the rest go to
    the review queue. Cheap self-consistency + position-bias filter.
  - Every calset row carries provenance {"anchor_judge_id", "context_hash",
    "ts"} -> the Clojure `training-admissible?` check holds by construction.
  - The calset is FROZEN once written: never trained on (anti-collapse).

Usage:
  python3 anchor_label.py --candidates demo_calib/candidates_edge_type.jsonl \\
      --judge anchor --config judges_config.yaml --double
  python3 anchor_label.py --candidates ... --dry-run --limit 2   # no API
"""

from __future__ import annotations
import argparse
import datetime as _dt
import json
import pathlib
import random
import sys
from typing import Dict, List, Optional

import judge_prompts as JP

# ---------------------------------------------------------------------------
# Anchor-side prompt material
# ---------------------------------------------------------------------------

ANCHOR_SYSTEM = JP.SYSTEM_PROMPT + """

You are the ANCHOR labeler: your verdicts become gold calibration labels for
smaller judges, so precision matters more than coverage. Think through the
guidance below before answering; if a case is genuinely borderline, still pick
the single best label, set "difficulty" accordingly, and set
"flag_for_human": true when a human should double-check."""

GUIDANCE: Dict[str, str] = {
    "edge_type": """\
- supports vs refines: 'refines' does NOT move the claim's credibility up or
  down — it narrows scope, adds a condition, or qualifies ('conforme SAUF la
  clause X' refines; 'la clause exigée est présente' supports).
- opposes requires genuine tension with the claim as stated, not mere
  incompleteness of the evidence.
- unrelated is the right label whenever the bearing is only thematic
  (same topic, no inferential link). Do not invent a link.
- Evidence that supports one PART of a composite claim while contradicting
  another part: prefer 'refines' and flag_for_human.""",
    "same_entity": """\
- POLICY: precision over recall. A false merge silently corrupts every
  downstream aggregation; a missed merge is recoverable. When in doubt:
  'distinct' + flag_for_human.
- Acronym/expansion pairs (RGPD / Règlement Général…) are 'same' only if the
  contexts show they are used as the same referent.
- A norm vs a page ABOUT the norm vs a specific VERSION of the norm are
  distinct referents; watch 'Article 28' vs 'Art. 28 RGPD' (usually same) vs
  'Article 28 du projet de loi X' (distinct).""",
    "summarize_now": """\
- 'fire' needs ALL of: enough members to generalize over (≳5), topical
  coherence visible in the samples, and stability (edit churn has settled).
- High churn or active disagreement among members => 'defer'.
- Administrative/index/hub pages and grab-bag tags => 'never' (no thesis to
  abstract).""",
    "propagate": """\
- 'propagate' means the neighbor's CONTENT or VALIDITY is materially affected
  — its text would plausibly need rereading or revising in light of the
  change. Shared topic alone => 'absorb'.
- Numeric/date/scope changes that the neighbor depends on => 'propagate'.""",
    "invalidate": """\
- 'invalidate' when the changed children alter what the derived/parent text
  ASSERTS (facts, scope, conclusions). Cosmetic or additive-but-consistent
  child edits => 'keep'.
- A parent claiming completeness ('synthèse', 'à jour') is more fragile:
  lean 'invalidate' when children moved under it afterwards.""",
    "dedup_prop": """\
- 'duplicate': same fact, both directions of entailment (wording may differ).
- 'subsumes': ITEM_1 entails everything ITEM_2 asserts AND adds more; the
  direction is fixed by presentation order — check it, never assume.
- Same subject + different attribute, or same attribute + different value
  => 'distinct'.""",
    "faithful": """\
- LEGAL DOCTRINE: a proposition that drops a scope limit, condition,
  exception, effective date, or the authority level of the source is
  'lost_qualifier' EVEN IF everything it says is literally in the source.
  ('Les données ne peuvent être conservées au-delà de la durée nécessaire'
  vs a source that says '…sauf à des fins archivistiques' => lost_qualifier.)
- 'unsupported' is for content ADDED beyond the source, including silently
  upgraded modality (may->must, recommandé->obligatoire).
- 'faithful' must survive a lawyer's reading, not a casual one.
- All non-'faithful' verdicts on this type: flag_for_human.""",
}

OUT_SCHEMA = {
    "type": "object",
    "properties": {
        "label": {"type": "string"},   # tightened per type at call time
        "basis": {"type": "string", "maxLength": 240},
        "difficulty": {"enum": ["easy", "medium", "hard"]},
        "flag_for_human": {"type": "boolean"},
    },
    "required": ["label", "difficulty", "flag_for_human"],
    "additionalProperties": False,
}

T2_TYPES = {"edge_type", "same_entity", "faithful", "permanent_worthy"}

try:  # optional zettel layer: adds types; PULL its guidance into this module
    import zettel_prompts
    zettel_prompts.register()
    GUIDANCE.update(zettel_prompts.GUIDANCE)
except ImportError:
    pass


def salted_label_order(jtype: str, ctx_hash: str, salt: int) -> List[str]:
    labels = list(JP.LABEL_DEFS[jtype].keys())
    rng = random.Random(int(ctx_hash[:16], 16) ^ salt)
    rng.shuffle(labels)
    return labels


def build_anchor_user(jtype: str, fields: Dict[str, str],
                      ctx_hash: str, salt: int) -> str:
    fenced = "\n\n".join(JP.fence(k, fields[k])
                         for k in JP.REQUIRED_FIELDS[jtype])
    defs = "\n".join(f"- {l}: {JP.LABEL_DEFS[jtype][l]}"
                     for l in salted_label_order(jtype, ctx_hash, salt))
    return (f"{fenced}\n\n"
            f"Question: {JP.QUESTIONS[jtype]}\n\n"
            f"Labels:\n{defs}\n\n"
            f"Labeling guidance:\n{GUIDANCE[jtype]}\n\n"
            f'Answer as JSON: {{"label", "basis" (≤240 chars), '
            f'"difficulty", "flag_for_human"}}')


# ---------------------------------------------------------------------------
# Labeling
# ---------------------------------------------------------------------------

def _salvage_json(text: str) -> dict:
    """Parse model output as JSON, tolerating markdown fences and prose
    around the object (providers without constrained decoding do both)."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0]
    start, end = t.find("{"), t.rfind("}")
    if start >= 0 and end > start:
        t = t[start:end + 1]
    return json.loads(t)


def anchor_call(judge, jtype: str, user: str, cli=None):
    """Returns (parsed_verdict, tokens_in, tokens_out). Token counts feed the
    B6 spend meter; 0/0 if the provider omits usage.

    Constrained decoding: `guided_json` for vLLM endpoints, plus OpenAI-style
    `response_format json_schema` for API providers (OpenRouter/DeepSeek).
    Falls back to unconstrained + salvage if the routed provider rejects
    response_format. `cli` is injectable (infra_check reuses THIS call)."""
    if cli is None:
        from openai import OpenAI
        cli = OpenAI(base_url=judge.base_url, api_key=judge.api_key)
    schema = dict(OUT_SCHEMA)
    schema["properties"] = dict(OUT_SCHEMA["properties"])
    schema["properties"]["label"] = {"enum": list(JP.LABEL_DEFS[jtype])}
    xb = dict(getattr(judge, "extra_body", {}) or {})
    xb.setdefault("guided_json", schema)
    rf = {"type": "json_schema",
          "json_schema": {"name": "anchor_verdict", "strict": True,
                          "schema": schema}}

    def _one(extra: dict, max_tokens: int):
        kwargs = dict(model=judge.model, temperature=0.0,
                      max_tokens=max_tokens,
                      messages=[{"role": "system", "content": ANCHOR_SYSTEM},
                                {"role": "user", "content": user}],
                      extra_body={**xb, **extra})
        try:
            return cli.chat.completions.create(response_format=rf, **kwargs)
        except Exception as e:  # noqa: BLE001 — provider rejects response_format
            if "response_format" not in str(e) and "json_schema" not in str(e):
                raise
            return cli.chat.completions.create(**kwargs)

    # Reasoning models may spend the whole budget thinking and return EMPTY
    # content (finish_reason=length). Attempt 1 keeps reasoning (quality);
    # attempt 2 disables it (OpenRouter unified param) — determinism over
    # depth for the rare overflow case.
    r = _one({}, 4000)
    tin = tout = 0
    u = getattr(r, "usage", None)
    tin += getattr(u, "prompt_tokens", 0) or 0
    tout += getattr(u, "completion_tokens", 0) or 0
    content = r.choices[0].message.content
    if not (content or "").strip():
        r = _one({"reasoning": {"enabled": False}}, 800)
        u = getattr(r, "usage", None)
        tin += getattr(u, "prompt_tokens", 0) or 0
        tout += getattr(u, "completion_tokens", 0) or 0
        content = r.choices[0].message.content
    return _salvage_json(content), tin, tout


def render_review_item(i: int, cand: dict, verdicts: List[dict],
                       reason: str) -> str:
    f = "\n".join(f"  - **{k}**: {v}" for k, v in cand["fields"].items())
    v = "\n".join(f"  - pass {j+1}: `{x['label']}` ({x['difficulty']}) — "
                  f"{x.get('basis','')}" for j, x in enumerate(verdicts))
    return (f"### {i}. `{cand['jtype']}` — {reason}\n"
            f"- subjects: `{cand['subjects']}`\n{f}\n- anchor verdicts:\n{v}\n"
            f"- [ ] human gold: ______\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--config", default="judges_config.yaml")
    ap.add_argument("--judge", default="anchor")
    ap.add_argument("--out", default=None,
                    help="default: calset_{jtype}.jsonl next to candidates")
    ap.add_argument("--review", default=None,
                    help="default: review_queue_{jtype}.md next to candidates")
    ap.add_argument("--double", action="store_true",
                    help="label twice with different label orders; keep only "
                         "consistent verdicts")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--run", default="anchor-label",
                    help="B6 spend-ledger run id (resume key after a cap hit)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the anchor prompt(s) and exit (no API)")
    args = ap.parse_args()

    cands = [json.loads(l) for l in
             pathlib.Path(args.candidates).read_text().splitlines()
             if l.strip()]
    if args.limit:
        cands = cands[: args.limit]
    if not cands:
        sys.exit("no candidates")
    jtype = cands[0]["jtype"]

    if args.dry_run:
        for c in cands[: (args.limit or 1)]:
            ch = JP.context_hash(jtype, 1, c["fields"])
            print("=" * 72)
            print(build_anchor_user(jtype, c["fields"], ch, salt=0))
        return

    from judge_harness import load_judge, now_iso  # lazy: needs yaml/openai
    import yaml
    import spend as _spend
    judge = load_judge(args.config, args.judge)
    _cfg = yaml.safe_load(pathlib.Path(args.config).read_text())
    _sc = _spend.spend_config(_cfg)
    _pr = _spend.judge_price(_cfg, args.judge)
    meter = _spend.resume_from_ledger(
        args.run, args.judge, _pr["input_per_mtok"], _pr["output_per_mtok"],
        _sc["max_usd_per_run"], pathlib.Path(_sc["ledger"]))
    out_p = pathlib.Path(args.out or
                         pathlib.Path(args.candidates).parent /
                         f"calset_{jtype}.jsonl")
    rev_p = pathlib.Path(args.review or
                         pathlib.Path(args.candidates).parent /
                         f"review_queue_{jtype}.md")

    kept, review = [], []
    capped = False
    for i, c in enumerate(cands):
        ch = JP.context_hash(jtype, judge.prompt_version, c["fields"])
        v1, tin1, tout1 = anchor_call(
            judge, jtype, build_anchor_user(jtype, c["fields"], ch, salt=0))
        if not meter.add(tin1, tout1):
            capped = True
            break  # cap hit: partial outputs are valid, resume on re-run
        verdicts = [v1]
        consistent = True
        if args.double:
            v2, tin2, tout2 = anchor_call(
                judge, jtype,
                build_anchor_user(jtype, c["fields"], ch, salt=0x9E3779B9))
            if not meter.add(tin2, tout2):
                capped = True
                break
            verdicts.append(v2)
            consistent = v1["label"] == v2["label"]

        flag = any(v.get("flag_for_human") for v in verdicts)
        hard_t2 = jtype in T2_TYPES and any(
            v.get("difficulty") == "hard" for v in verdicts)
        if consistent and not flag:
            row = {"jtype": jtype, "fields": c["fields"],
                   "gold": v1["label"], "basis": v1.get("basis", ""),
                   "difficulty": v1["difficulty"],
                   "provenance": {"anchor_judge_id": judge.judge_id,
                                  "context_hash": ch, "ts": now_iso(),
                                  "double_consistent": args.double}}
            kept.append(row)
            if hard_t2:
                review.append(render_review_item(
                    i, c, verdicts, "hard T2 — spot-check the kept gold"))
        else:
            reason = ("order-inconsistent" if not consistent
                      else "anchor flagged for human")
            review.append(render_review_item(i, c, verdicts, reason))

    meter.flush()  # final ledger line (ANNEX_B6 §2.2)
    out_p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                             for r in kept))
    rev_p.write_text(f"# Review queue — {jtype} "
                     f"({len(review)} items, {now_iso()})\n\n"
                     + "\n".join(review) if review else
                     f"# Review queue — {jtype}\n\n(empty)\n")
    if capped:
        print(f"warning: spend cap ${meter.max_usd:.2f} reached after "
              f"{meter.calls} calls (${meter.usd:.4f}); re-run with the same "
              f"--run '{args.run}' to resume", file=sys.stderr)
    print(json.dumps({"jtype": jtype, "labeled": len(kept) + len(review),
                      "kept_gold": len(kept), "review": len(review),
                      "calset": str(out_p), "review_queue": str(rev_p),
                      "spend_usd": round(meter.usd, 4), "capped": capped},
                     indent=2))


if __name__ == "__main__":
    main()

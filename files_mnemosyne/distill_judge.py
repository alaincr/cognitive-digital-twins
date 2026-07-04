#!/usr/bin/env python3
"""distill_judge.py — distillation gravity for the Mnemosyne micro-judges
(microjudge_contract.md §7 and build-order step 5).

Compiles expensive judgment into cheap judgment, safely:

  dataset        gather TRAINING-ADMISSIBLE examples (label provenance must
                 reach anchor or human — never the swarm's own outputs),
                 resolve conflicts by source priority, dedupe by context hash,
                 and split train vs FROZEN AUDIT deterministically by hash
  train          QLoRA/LoRA fine-tune judge v(n+1) on the SFT set (3090-sized)
  eval-audit     paired argmax evaluation, incumbent vs candidate, on the
                 frozen audit set — with McNemar's exact test
  shadow-compare incumbent vs shadow-deployed candidate on LIVE traffic,
                 anchored by the drift-sampling verdicts
  promote-check  apply the promotion gate to both reports; print verdict +
                 the judges_config.yaml stanza to add
  self-test      run the pure-logic unit tests (no GPU, no server)

Anti-collapse invariants enforced here:
  - Admissibility is a provenance check, not a vibe: every example carries a
    source in {human, anchor_double, anchor}; swarm-only labels never enter.
  - The audit split is DETERMINISTIC BY CONTEXT HASH (bucket rule), so an
    item's membership never migrates between train and audit as data grows —
    no leakage over time, and the audit set is frozen by construction.
  - The SFT target string is IMPORTED from judge_harness._completion_target,
    so training optimizes the exact conditional the deployed scorer scores.
  - Promotion requires beating the incumbent on the frozen audit set with
    McNemar significance AND not regressing on live anchor agreement.
"""

from __future__ import annotations
import argparse
import collections
import json
import math
import pathlib
import sys
from typing import Dict, List, Optional, Sequence, Tuple

import judge_prompts as JP
import judge_harness as JH

SOURCE_PRIORITY = {"human": 3, "anchor_double": 2, "anchor": 1}

# ===========================================================================
# Dataset assembly (pure logic — covered by self-test)
# ===========================================================================

def audit_bucket(context_hash: str, audit_frac: float) -> bool:
    """Deterministic, stable membership: an item is audit iff its hash bucket
    falls below the audit fraction. New data streams into the same buckets
    forever — the audit set grows but never exchanges members with train."""
    return int(context_hash[:8], 16) % 1000 < int(round(audit_frac * 1000))


def normalize_calset(path: pathlib.Path) -> List[dict]:
    out = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        prov = r.get("provenance", {})
        out.append({"context_hash": prov.get("context_hash") or
                    JP.context_hash(r["jtype"], 1, r["fields"]),
                    "jtype": r["jtype"], "fields": r["fields"],
                    "gold": r["gold"],
                    "source": ("anchor_double" if prov.get("double_consistent")
                               else "anchor")})
    return out


def normalize_accepted(accepted: pathlib.Path, contexts: pathlib.Path,
                       jtype: str) -> List[dict]:
    """Anchor-family verdicts that flowed through the live system (escalation
    answers, anchor promotions). Fields joined from the context store."""
    ctx = JH.load_contexts(contexts)
    out = []
    for line in accepted.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("judge_family") != "anchor" or r.get("jtype") != jtype:
            continue
        c = ctx.get(r["context_hash"])
        if c:
            out.append({"context_hash": r["context_hash"], "jtype": jtype,
                        "fields": c["fields"], "gold": r["label"],
                        "source": "anchor"})
    return out


def normalize_human(path: pathlib.Path, contexts: Optional[pathlib.Path],
                    jtype: str) -> List[dict]:
    """human_gold.jsonl rows: {"jtype", "gold", and either "fields" or
    "context_hash"} — the worked review queues, transcribed."""
    ctx = JH.load_contexts(contexts) if contexts else {}
    out = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("jtype") != jtype:
            continue
        fields = r.get("fields") or ctx.get(r.get("context_hash", ""),
                                            {}).get("fields")
        if fields is None:
            continue
        ch = r.get("context_hash") or JP.context_hash(jtype, 1, fields)
        out.append({"context_hash": ch, "jtype": jtype, "fields": fields,
                    "gold": r["gold"], "source": "human"})
    return out


def resolve(examples: List[dict]) -> Tuple[List[dict], List[dict]]:
    """Per context hash: highest-priority source wins; equal-priority
    disagreements are DROPPED (and reported), not averaged."""
    by_ch: Dict[str, List[dict]] = collections.defaultdict(list)
    for e in examples:
        by_ch[e["context_hash"]].append(e)
    kept, dropped = [], []
    for ch, group in by_ch.items():
        top = max(SOURCE_PRIORITY[g["source"]] for g in group)
        cands = [g for g in group if SOURCE_PRIORITY[g["source"]] == top]
        labels = {g["gold"] for g in cands}
        if len(labels) == 1:
            kept.append(cands[0])
        else:
            dropped.append({"context_hash": ch, "labels": sorted(labels),
                            "source_tier": top})
    return kept, dropped


def to_sft(row: dict, prompt_version: int) -> dict:
    """SFT example whose assistant target is EXACTLY what the deployed echo
    scorer scores (imported, not re-implemented — coupling by construction)."""
    ch = JP.context_hash(row["jtype"], prompt_version, row["fields"])
    user = JP.build_user_prompt(row["jtype"], row["fields"], ch)
    return {"messages": [
                {"role": "system", "content": JP.SYSTEM_PROMPT},
                {"role": "user", "content": user},
                {"role": "assistant",
                 "content": JH._completion_target(row["gold"])}],
            "meta": {"context_hash": ch, "gold": row["gold"],
                     "source": row["source"]}}


def build_dataset(sources: List[dict], audit_frac: float,
                  prompt_version: int) -> dict:
    kept, dropped = resolve(sources)
    train = [to_sft(r, prompt_version) for r in kept
             if not audit_bucket(r["context_hash"], audit_frac)]
    audit = [{"jtype": r["jtype"], "fields": r["fields"], "gold": r["gold"],
              "context_hash": r["context_hash"], "source": r["source"]}
             for r in kept if audit_bucket(r["context_hash"], audit_frac)]
    return {"train": train, "audit": audit, "dropped": dropped,
            "by_source": collections.Counter(r["source"] for r in kept),
            "by_label": collections.Counter(r["gold"] for r in kept)}


def cmd_dataset(args) -> None:
    sources: List[dict] = []
    for p in args.calsets or []:
        sources += [r for r in normalize_calset(pathlib.Path(p))
                    if r["jtype"] == args.jtype]
    if args.accepted:
        sources += normalize_accepted(pathlib.Path(args.accepted),
                                      pathlib.Path(args.contexts), args.jtype)
    if args.human:
        sources += normalize_human(pathlib.Path(args.human),
                                   pathlib.Path(args.contexts)
                                   if args.contexts else None, args.jtype)
    ds = build_dataset(sources, args.audit_frac, args.prompt_version)
    out = pathlib.Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    (out / f"train_{args.jtype}.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ds["train"]))
    (out / f"audit_{args.jtype}.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ds["audit"]))
    (out / f"manifest_{args.jtype}.json").write_text(json.dumps(
        {"jtype": args.jtype, "audit_frac": args.audit_frac,
         "rule": "audit iff int(hash[:8],16) % 1000 < frac*1000",
         "prompt_version": args.prompt_version,
         "n_train": len(ds["train"]), "n_audit": len(ds["audit"]),
         "dropped_conflicts": ds["dropped"],
         "by_source": dict(ds["by_source"]),
         "by_label": dict(ds["by_label"])}, indent=2))
    print(json.dumps({"train": len(ds["train"]), "audit": len(ds["audit"]),
                      "conflicts_dropped": len(ds["dropped"]),
                      "by_source": dict(ds["by_source"]),
                      "by_label": dict(ds["by_label"])}, indent=2))
    if len(ds["train"]) < 500:
        print(f"note: {len(ds['train'])} examples is thin for SFT; "
              f"the RLM precedent used ~1000 trajectories", file=sys.stderr)


# ===========================================================================
# Training (heavy deps imported lazily; not executable in this sandbox)
# ===========================================================================

def cmd_train(args) -> None:
    import torch  # noqa
    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import LoraConfig
    from trl import SFTConfig, SFTTrainer

    tok = AutoTokenizer.from_pretrained(args.base)
    model_kwargs = {"torch_dtype": "bfloat16", "device_map": "auto"}
    if args.qlora:
        from transformers import BitsAndBytesConfig
        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype="bfloat16")
    model = AutoModelForCausalLM.from_pretrained(args.base, **model_kwargs)

    data = load_dataset("json", data_files=args.dataset, split="train")
    peft_cfg = LoraConfig(r=args.r, lora_alpha=args.alpha,
                          lora_dropout=0.05, task_type="CAUSAL_LM",
                          target_modules="all-linear")
    sft_cfg = SFTConfig(
        output_dir=args.out, num_train_epochs=args.epochs,
        per_device_train_batch_size=args.bsz,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr, max_length=args.max_len,
        logging_steps=10, save_strategy="epoch", bf16=True,
        assistant_only_loss=True)  # loss on the JSON verdict only; if your
        # trl version lacks this flag, mask via a response template instead —
        # full-sequence loss on these short targets mostly memorizes prompts.
    SFTTrainer(model=model, args=sft_cfg, train_dataset=data,
               processing_class=tok, peft_config=peft_cfg).train()

    out = pathlib.Path(args.out)
    # weights hash over the adapter -> the new judge identity
    import hashlib
    h = hashlib.sha256()
    for f in sorted(out.rglob("*.safetensors")):
        h.update(f.read_bytes())
    wh = h.hexdigest()[:8]
    base_short = args.base.split("/")[-1].lower()
    print(json.dumps({
        "adapter": str(out), "weights_hash": wh,
        "suggested_judge_id": f"{base_short}@{wh}#p{args.prompt_version}",
        "next": [
            f"serve: vllm serve {args.base} --enable-prefix-caching "
            f"--enable-lora --lora-modules cand={out}",
            "add the candidate stanza to judges_config.yaml (family = same "
            "as base — a distilled child is NOT decorrelated from its family)",
            "calibrate FRESH (fine-tuning rescales logits; old T/q̂ are void)",
            "eval-audit, then shadow-compare, then promote-check"]},
        indent=2))


# ===========================================================================
# Paired evaluation on the frozen audit set
# ===========================================================================

def mcnemar_exact(n01: int, n10: int) -> float:
    """Two-sided exact McNemar on discordant pairs (n01 = incumbent right &
    candidate wrong; n10 = the reverse). Stdlib-exact via binomial tails."""
    n = n01 + n10
    if n == 0:
        return 1.0
    k = min(n01, n10)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2.0 * tail)


def paired_report(golds: Sequence[str], pred_inc: Sequence[str],
                  pred_cand: Sequence[str]) -> dict:
    assert len(golds) == len(pred_inc) == len(pred_cand)
    n01 = sum(1 for g, a, b in zip(golds, pred_inc, pred_cand)
              if a == g and b != g)
    n10 = sum(1 for g, a, b in zip(golds, pred_inc, pred_cand)
              if a != g and b == g)
    acc_i = sum(a == g for a, g in zip(pred_inc, golds)) / len(golds)
    acc_c = sum(b == g for b, g in zip(pred_cand, golds)) / len(golds)
    conf: Dict[str, Dict[str, int]] = collections.defaultdict(
        lambda: collections.defaultdict(int))
    for g, b in zip(golds, pred_cand):
        conf[g][b] += 1
    return {"n": len(golds), "acc_incumbent": round(acc_i, 4),
            "acc_candidate": round(acc_c, 4),
            "delta": round(acc_c - acc_i, 4),
            "n01_inc_only_right": n01, "n10_cand_only_right": n10,
            "mcnemar_p": round(mcnemar_exact(n01, n10), 6),
            "candidate_confusion": {g: dict(d) for g, d in conf.items()}}


def _argmax_label(judge: JH.Judge, jtype: str, fields: dict) -> str:
    ch = JP.context_hash(jtype, judge.prompt_version, fields)
    user = JP.build_user_prompt(jtype, fields, ch)
    labels = JP.label_order(jtype, ch)
    raw = JH.score_labels_echo(judge, JP.SYSTEM_PROMPT, user, labels)
    return max(raw, key=raw.get)  # temperature is monotone: argmax-safe


def cmd_eval_audit(args) -> None:
    rows = [json.loads(l) for l in
            pathlib.Path(args.audit).read_text().splitlines() if l.strip()]
    inc = JH.load_judge(args.config, args.incumbent)
    cand = JH.load_judge(args.config, args.candidate)
    golds, pi, pc = [], [], []
    for r in rows:
        golds.append(r["gold"])
        pi.append(_argmax_label(inc, r["jtype"], r["fields"]))
        pc.append(_argmax_label(cand, r["jtype"], r["fields"]))
    rep = paired_report(golds, pi, pc)
    pathlib.Path(args.out).write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep, indent=2))


# ===========================================================================
# Shadow comparison on live traffic
# ===========================================================================

def _load_events(path: pathlib.Path) -> List[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def shadow_report(incumbent_outbox: List[dict], shadow_outbox: List[dict],
                  accepted: List[dict], anchor_events: List[dict]) -> dict:
    """Pure join + stats (self-tested). Shadow judgments are keyed by
    context_hash; anchor verdicts reach the candidate via accepted's
    judgment_id -> context_hash mapping."""
    def split(evs):
        em = {e["context_hash"]: e for e in evs
              if e["event"] == "judgment.emitted"}
        ab = sum(1 for e in evs if e["event"] == "judgment.abstained")
        return em, ab
    inc_em, inc_ab = split(incumbent_outbox)
    sh_em, sh_ab = split(shadow_outbox)
    rate = lambda em, ab: round(ab / max(len(em) + ab, 1), 4)

    both = set(inc_em) & set(sh_em)
    agree = sum(inc_em[h]["label"] == sh_em[h]["label"] for h in both)

    jid2ch = {a["judgment_id"]: a["context_hash"] for a in accepted}
    jid2lab = {a["judgment_id"]: a["label"] for a in accepted}
    inc_anchor, cand_anchor = [], []
    for ev in anchor_events:
        jid = ev.get("of")
        ch = jid2ch.get(jid)
        if ch is None:
            continue
        inc_anchor.append(bool(ev["agrees"]))
        if ch in sh_em:
            cand_anchor.append(sh_em[ch]["label"] == ev["anchor_label"])
    mean = lambda xs: round(sum(xs) / len(xs), 4) if xs else None
    return {"n_shared": len(both),
            "label_agreement": round(agree / max(len(both), 1), 4),
            "abstention_incumbent": rate(inc_em, inc_ab),
            "abstention_candidate": rate(sh_em, sh_ab),
            "anchor_agreement_incumbent": mean(inc_anchor),
            "anchor_agreement_candidate": mean(cand_anchor),
            "n_anchor_incumbent": len(inc_anchor),
            "n_anchor_candidate": len(cand_anchor)}


def cmd_shadow_compare(args) -> None:
    rep = shadow_report(_load_events(pathlib.Path(args.outbox)),
                        _load_events(pathlib.Path(args.shadow_outbox)),
                        _load_events(pathlib.Path(args.accepted)),
                        _load_events(pathlib.Path(args.anchor_outbox)))
    pathlib.Path(args.out).write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep, indent=2))


# ===========================================================================
# The promotion gate
# ===========================================================================

def gate(audit: dict, shadow: dict, *, min_gain: float = 0.0,
         max_p: float = 0.05, anchor_tol: float = 0.0,
         abst_band: Tuple[float, float] = (0.5, 2.0)) -> dict:
    reasons, decision = [], "PROMOTE"
    if audit["delta"] < min_gain:
        return {"decision": "REJECT",
                "reasons": [f"audit delta {audit['delta']} < {min_gain}"]}
    ai, ac = (shadow.get("anchor_agreement_incumbent"),
              shadow.get("anchor_agreement_candidate"))
    if ai is not None and ac is not None and ac < ai - anchor_tol:
        return {"decision": "REJECT",
                "reasons": [f"anchor agreement regressed {ai} -> {ac}"]}
    bi, bc = shadow["abstention_incumbent"], shadow["abstention_candidate"]
    if bi > 0 and not (abst_band[0] <= bc / bi <= abst_band[1]):
        decision = "EXTEND-SHADOW"
        reasons.append(f"abstention {bc} vs {bi} outside band {abst_band}")
    if audit["mcnemar_p"] > max_p:
        decision = "EXTEND-SHADOW"
        reasons.append(f"McNemar p={audit['mcnemar_p']} > {max_p} "
                       f"(gain not yet significant; gather more)")
    if decision == "PROMOTE":
        reasons.append(f"audit +{audit['delta']} (p={audit['mcnemar_p']}), "
                       f"anchor agreement held, abstention in band")
    return {"decision": decision, "reasons": reasons}


def cmd_promote_check(args) -> None:
    audit = json.loads(pathlib.Path(args.audit_report).read_text())
    shadow = json.loads(pathlib.Path(args.shadow_report).read_text())
    v = gate(audit, shadow, min_gain=args.min_gain, max_p=args.max_p,
             anchor_tol=args.anchor_tol)
    print(json.dumps(v, indent=2))
    if v["decision"] == "PROMOTE":
        print("\n# judges_config.yaml — replace the incumbent's stanza; "
              "then: recalibrate, point the runner at it, and keep the old "
              "judge entry quarantined (NOT deleted) for cohort queries.")


# ===========================================================================
# Self-test (pure logic; no GPU, no server)
# ===========================================================================

def self_test() -> None:
    ok = lambda c, msg: (print(f"  ✓ {msg}") if c else
                         (_ for _ in ()).throw(AssertionError(msg)))
    F = {k: "x" for k in JP.REQUIRED_FIELDS["edge_type"]}
    ch_a, ch_t = "000000aa" + "0" * 56, "000000c8" + "0" * 56  # buckets 170, 200
    ok(audit_bucket(ch_a, 0.2) and not audit_bucket(ch_t, 0.2),
       "deterministic audit bucketing")
    srcs = [
        {"context_hash": ch_a, "jtype": "edge_type", "fields": F,
         "gold": "supports", "source": "anchor"},
        {"context_hash": ch_t, "jtype": "edge_type", "fields": F,
         "gold": "supports", "source": "anchor"},
        {"context_hash": ch_t, "jtype": "edge_type", "fields": F,
         "gold": "opposes", "source": "human"},          # human overrides
        {"context_hash": "11" * 32, "jtype": "edge_type", "fields": F,
         "gold": "refines", "source": "anchor"},
        {"context_hash": "11" * 32, "jtype": "edge_type", "fields": F,
         "gold": "supports", "source": "anchor"},        # tie conflict -> drop
    ]
    ds = build_dataset(srcs, 0.2, 1)
    ok(len(ds["dropped"]) == 1, "equal-priority conflicts dropped")
    ok(len(ds["audit"]) == 1 and ds["audit"][0]["context_hash"] == ch_a,
       "audit split by bucket rule")
    ok(len(ds["train"]) == 1 and ds["train"][0]["meta"]["gold"] == "opposes",
       "human label overrides anchor on the same context")
    tgt = ds["train"][0]["messages"][-1]["content"]
    ok(tgt == JH._completion_target("opposes"),
       "SFT target == deployed scorer target (coupling by import)")
    # McNemar exact values
    ok(abs(mcnemar_exact(10, 2) - 0.038574) < 1e-5, "McNemar(10,2)≈0.0386")
    ok(mcnemar_exact(0, 0) == 1.0, "McNemar(0,0)=1")
    rep = paired_report(["a", "a", "b", "b"], ["a", "b", "b", "a"],
                        ["a", "a", "b", "a"])
    ok(rep["acc_candidate"] == 0.75 and rep["n10_cand_only_right"] == 1
       and rep["n01_inc_only_right"] == 0, "paired report counts")
    # shadow join
    inc = [{"event": "judgment.emitted", "context_hash": "h1", "label": "supports"},
           {"event": "judgment.emitted", "context_hash": "h2", "label": "opposes"},
           {"event": "judgment.abstained", "context_hash": "h3"}]
    sh = [{"event": "judgment.emitted", "context_hash": "h1", "label": "supports"},
          {"event": "judgment.emitted", "context_hash": "h2", "label": "refines"}]
    acc = [{"judgment_id": "j1", "context_hash": "h1", "label": "supports"},
           {"judgment_id": "j2", "context_hash": "h2", "label": "opposes"}]
    anc = [{"of": "j1", "agrees": True, "anchor_label": "supports"},
           {"of": "j2", "agrees": True, "anchor_label": "opposes"}]
    sr = shadow_report(inc, sh, acc, anc)
    ok(sr["label_agreement"] == 0.5 and sr["anchor_agreement_incumbent"] == 1.0
       and sr["anchor_agreement_candidate"] == 0.5
       and sr["abstention_incumbent"] == round(1 / 3, 4),
       "shadow join: agreement, anchor mapping via accepted, abstention")
    # gate decisions
    good_a = {"delta": 0.06, "mcnemar_p": 0.012}
    good_s = {"anchor_agreement_incumbent": 0.9,
              "anchor_agreement_candidate": 0.9,
              "abstention_incumbent": 0.10, "abstention_candidate": 0.12}
    ok(gate(good_a, good_s)["decision"] == "PROMOTE", "gate: promote")
    ok(gate({"delta": 0.02, "mcnemar_p": 0.3}, good_s)["decision"]
       == "EXTEND-SHADOW", "gate: insignificant gain -> extend")
    ok(gate({"delta": -0.01, "mcnemar_p": 0.01}, good_s)["decision"]
       == "REJECT", "gate: regression -> reject")
    bad_s = dict(good_s, anchor_agreement_candidate=0.8)
    ok(gate(good_a, bad_s)["decision"] == "REJECT",
       "gate: anchor regression -> reject")
    print("all self-tests passed")


# ===========================================================================
# Entry
# ===========================================================================

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("dataset")
    d.add_argument("--jtype", required=True)
    d.add_argument("--calsets", nargs="*", help="anchor_label.py outputs")
    d.add_argument("--accepted", help="ops/accepted.jsonl (anchor rows only)")
    d.add_argument("--contexts", help="ops/contexts.jsonl")
    d.add_argument("--human", help="human_gold.jsonl (worked review queues)")
    d.add_argument("--audit-frac", type=float, default=0.3)
    d.add_argument("--prompt-version", type=int, default=1)
    d.add_argument("--out-dir", default="distill")

    t = sub.add_parser("train")
    t.add_argument("--dataset", required=True)
    t.add_argument("--base", required=True)
    t.add_argument("--out", required=True)
    t.add_argument("--epochs", type=int, default=2)
    t.add_argument("--lr", type=float, default=1e-4)
    t.add_argument("--r", type=int, default=16)
    t.add_argument("--alpha", type=int, default=32)
    t.add_argument("--bsz", type=int, default=2)
    t.add_argument("--grad-accum", type=int, default=8)
    t.add_argument("--max-len", type=int, default=2048)
    t.add_argument("--qlora", action="store_true")
    t.add_argument("--prompt-version", type=int, default=1)

    e = sub.add_parser("eval-audit")
    e.add_argument("--audit", required=True)
    e.add_argument("--config", default="judges_config.yaml")
    e.add_argument("--incumbent", required=True)
    e.add_argument("--candidate", required=True)
    e.add_argument("--out", default="eval_audit.json")

    s = sub.add_parser("shadow-compare")
    s.add_argument("--outbox", default="ops/outbox.jsonl")
    s.add_argument("--shadow-outbox", default="ops/shadow_outbox.jsonl")
    s.add_argument("--accepted", default="ops/accepted.jsonl")
    s.add_argument("--anchor-outbox", default="ops/anchor_outbox.jsonl")
    s.add_argument("--out", default="shadow_report.json")

    p = sub.add_parser("promote-check")
    p.add_argument("--audit-report", default="eval_audit.json")
    p.add_argument("--shadow-report", default="shadow_report.json")
    p.add_argument("--min-gain", type=float, default=0.0)
    p.add_argument("--max-p", type=float, default=0.05)
    p.add_argument("--anchor-tol", type=float, default=0.0)

    sub.add_parser("self-test")
    args = ap.parse_args()
    {"dataset": cmd_dataset, "train": cmd_train, "eval-audit": cmd_eval_audit,
     "shadow-compare": cmd_shadow_compare, "promote-check": cmd_promote_check,
     "self-test": lambda _: self_test()}[args.cmd](args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""propositionize.py — the Dense-X propositionizer (WP-1a, SPEC-02).

source text (Roam blocks | plain text) -> atomic propositions -> best
supporting source span -> emitted as (a) `faithful` judge candidates and
(b) proposition records for stratum-gated ingestion.

Invariants implemented here (SPEC-02 §1, §5):
  - ANTI-CIRCULARITY: every proposition is emitted at stratum "candidate",
    kind "literature". Nothing downstream may consume it until its faithful
    judgment is accepted; the consolidator gates, this pipeline only emits.
  - SELF-FUNDING: the decomposer is a config knob (--judge, default anchor);
    anchor decompositions become faithful calibration/training material.
  - DETERMINISM: temperature 0; content-addressed cache keyed on
    (unit text, PROMPT_VERSION, judge_id); prop_id content-addressed on
    (unit_id, text) => idempotent re-runs, stable subjects.
  - Low span-alignment confidence is a FEATURE: those rows are prime
    `unsupported` material for the faithful calset. Never drop them.

CLI: run / stats / self-test.  --dry-run prints the exact prompt, no calls.
"""

from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
import re
import sys
import tempfile
from collections import Counter
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import judge_prompts as JP
import roam_harvest as RH
import judge_harness as JH

PROMPT_VERSION = 1

PROPS_SCHEMA = {
    "type": "object",
    "properties": {"propositions": {"type": "array", "maxItems": 12,
                                    "items": {"type": "string",
                                              "maxLength": 500}}},
    "required": ["propositions"], "additionalProperties": False,
}

# System prompt: judge_prompts' hardening frame with the task line replaced
# (SPEC-02 §3).
_cut = JP.SYSTEM_PROMPT.find(".")
PROP_SYSTEM = ("You decompose the fenced passage into atomic propositions"
               + JP.SYSTEM_PROMPT[_cut:])

RULES = """Rules:
1. One self-contained fact per proposition; a reader with NO access to the \
passage must understand it (resolve pronouns and demonstratives; name the subject).
2. PRESERVE QUALIFIERS VERBATIM IN MEANING: scope limits, conditions, \
exceptions, effective dates, durations, and the authority level of the source \
("selon la CNIL...", "sauf...", "au plus tard..."). Dropping one is the worst \
possible error.
3. Do not add anything the passage does not state; do not upgrade modality \
(may->must, recommand\u00e9->obligatoire).
4. Split conjunctions into separate propositions; keep negations attached to \
their clause.
5. 1-12 propositions; if the passage states no facts (a question, a to-do, \
pure navigation), return an empty list.
6. Write propositions in the passage's language (French stays French)."""


def build_decomp_prompt(unit_text: str) -> str:
    return (JP.fence("passage", unit_text) + "\n\n" + RULES + "\n\n"
            + 'Answer as JSON: {"propositions": ["...", ...]}')


# ===========================================================================
# [A] Segmenters
# ===========================================================================

_QUERY_RE = re.compile(r"\{\{\[?\[?query\]?\]?", re.IGNORECASE)


def _content_only(s: str) -> str:
    """Strip refs/tags/attrs/punct — used to drop navigation-only blocks."""
    s = RH.REF_RE.sub(" ", s)
    s = RH.TAG_RE.sub(" ", s)
    s = RH.ATTR_RE.sub(" ", s)
    return re.sub(r"[^0-9A-Za-z\u00c0-\u017f]+", "", s)


def segment_roam(export_path: pathlib.Path,
                 lo: int = 30, hi: int = 2000) -> List[dict]:
    g = RH.Graph.parse(json.loads(export_path.read_text()))
    units = []
    for b in g.blocks.values():
        s = b["string"]
        if not (lo <= len(s) <= hi):
            continue
        if "```" in s or _QUERY_RE.search(s):
            continue
        if len(_content_only(s)) < 15:      # refs/tags-only navigation block
            continue
        units.append({"unit_id": b["uid"], "text": g.expand_brefs(s),
                      "source_doc": b["page"],
                      "locator": RH._path_str(g, b["uid"])})
    return sorted(units, key=lambda u: u["unit_id"])


def segment_text(file_path: pathlib.Path,
                 lo: int = 30, hi: int = 2000) -> List[dict]:
    paras = [p.strip() for p in
             re.split(r"\n\s*\n", file_path.read_text(encoding="utf-8"))]
    units = []
    for i, p in enumerate(paras):
        if lo <= len(p) <= hi:
            uid = "u-" + hashlib.sha256(f"{file_path}|{p}".encode()
                                        ).hexdigest()[:12]
            units.append({"unit_id": uid, "text": p,
                          "source_doc": file_path.name,
                          "locator": f"{file_path.name}:para-{i}"})
    return units


# ===========================================================================
# [B] Decomposition (the mock seam: `caller(system, user) -> raw str`)
# ===========================================================================

class DecomposeFailed(Exception):
    pass


def repair_parse(raw: str) -> List[str]:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    obj = json.loads(raw)
    props = obj["propositions"]
    if not isinstance(props, list) or not all(isinstance(p, str) for p in props):
        raise ValueError("bad shape")
    return [p.strip() for p in props if p.strip()]


def decompose(unit_text: str, caller: Callable[[str, str], str]) -> List[str]:
    user = build_decomp_prompt(unit_text)
    try:
        return repair_parse(caller(PROP_SYSTEM, user))
    except Exception:
        try:
            return repair_parse(caller(PROP_SYSTEM,
                                       user + "\nReturn ONLY the JSON object."))
        except Exception as e:
            raise DecomposeFailed(str(e))


def llm_caller(judge) -> Callable[[str, str], str]:
    from openai import OpenAI
    cli = OpenAI(base_url=judge.base_url, api_key=judge.api_key)

    def call(system: str, user: str) -> str:
        r = cli.chat.completions.create(
            model=judge.model, temperature=0.0, max_tokens=1200,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            extra_body={"guided_json": PROPS_SCHEMA})
        return r.choices[0].message.content
    return call


# --- content-addressed cache -------------------------------------------------

def cache_key(unit_text: str, judge_id: str) -> str:
    return hashlib.sha256(
        f"{unit_text}|{PROMPT_VERSION}|{judge_id}".encode()).hexdigest()


def load_cache(path: pathlib.Path) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    if path.exists():
        for l in path.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                out.setdefault(r["key"], r["propositions"])
    return out


def append_cache(path: pathlib.Path, key: str, props: List[str]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"key": key, "propositions": props},
                           ensure_ascii=False) + "\n")


# ===========================================================================
# [C] Span alignment (SPEC-02 §4)
# ===========================================================================

def sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?;])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def content_tokens(s: str) -> set:
    return set(RH.norm(s).split()) - RH.FR_STOP


def align_span(prop: str, unit_text: str) -> Tuple[str, str, float]:
    """-> (source_span, source_surrounding, confidence). Windows of 1-3
    consecutive sentences; score = covered fraction of the proposition's
    content tokens; ties -> shortest window, then earliest."""
    sents = sentences(unit_text)
    ptok = content_tokens(prop)
    if not sents or not ptok:
        return unit_text[:400], unit_text[:600], 0.0
    # minimize key = (-score, length, start): initialize ABOVE any real key.
    # (A -1.0 initializer here once made zero-overlap propositions — exactly
    # the invented/'unsupported' case — return an empty span at conf 1.0.)
    best = (float("inf"), float("inf"), float("inf"), 0, 1)
    for i in range(len(sents)):
        for j in range(i + 1, min(i + 3, len(sents)) + 1):
            w = " ".join(sents[i:j])
            score = len(ptok & content_tokens(w)) / len(ptok)
            key = (-score, len(w), i, i, j)
            if key < best:
                best = key
    _, _, _, i, j = best
    score = -best[0]
    span = " ".join(sents[i:j])
    surr = " ".join(sents[max(0, i - 1): min(len(sents), j + 1)])
    return span, surr, round(score, 3)


LOW_CONFIDENCE = 0.30


# ===========================================================================
# [D] Emitters (SPEC-02 §5 — exact shapes)
# ===========================================================================

def prop_id(unit_id: str, text: str) -> str:
    return "prop-" + hashlib.sha256(f"{unit_id}|{text}".encode()).hexdigest()[:12]


def emit_rows(unit: dict, props: List[str], decomposer_id: str
              ) -> Tuple[List[dict], List[dict]]:
    cands, recs = [], []
    for p in props:
        pid = prop_id(unit["unit_id"], p)
        span, surr, conf = align_span(p, unit["text"])
        cands.append({"jtype": "faithful",
                      "subjects": [pid, unit["unit_id"]],
                      "fields": {"proposition": p, "source_span": span,
                                 "source_surrounding": surr},
                      "meta": {"span_confidence": conf,
                               "low_confidence": conf < LOW_CONFIDENCE,
                               "pipeline_version": PROMPT_VERSION,
                               "decomposer": decomposer_id}})
        recs.append({"prop_id": pid, "text": p, "unit_id": unit["unit_id"],
                     "source_doc": unit["source_doc"],
                     "locator": unit["locator"], "span": span,
                     "span_confidence": conf,
                     "stratum": "candidate", "kind": "literature",
                     "decomposer": decomposer_id,
                     "pipeline_version": PROMPT_VERSION, "ts": JH.now_iso()})
    return cands, recs


# ===========================================================================
# The run
# ===========================================================================

def run(units: List[dict], caller: Callable[[str, str], str],
        out_dir: pathlib.Path, decomposer_id: str) -> Dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_p = out_dir / "cache_props.jsonl"
    cache = load_cache(cache_p)
    n_cands = n_props = n_cached = n_failed = 0
    with (out_dir / "faithful_candidates.jsonl").open("a", encoding="utf-8") as fc, \
         (out_dir / "propositions.jsonl").open("a", encoding="utf-8") as fp, \
         (out_dir / "failed_units.jsonl").open("a", encoding="utf-8") as ff:
        for u in units:
            key = cache_key(u["text"], decomposer_id)
            if key in cache:
                props, n_cached = cache[key], n_cached + 1
            else:
                try:
                    props = decompose(u["text"], caller)
                except DecomposeFailed as e:
                    ff.write(json.dumps({**u, "error": str(e)},
                                        ensure_ascii=False) + "\n")
                    n_failed += 1
                    continue
                append_cache(cache_p, key, props)
                cache[key] = props
            cands, recs = emit_rows(u, props, decomposer_id)
            for c in cands:
                fc.write(json.dumps(c, ensure_ascii=False) + "\n")
            for r in recs:
                fp.write(json.dumps(r, ensure_ascii=False) + "\n")
            n_cands += len(cands)
            n_props += len(recs)
    return {"units": len(units), "propositions": n_props,
            "faithful_candidates": n_cands, "cache_hits": n_cached,
            "failed_units": n_failed}


# ===========================================================================
# Self-test — SPEC-02 §7, the mock seam, all 12 cases
# ===========================================================================

def make_mock():
    """Deterministic mock decomposer per SPEC-02 §7: sentences as
    propositions; 'SAUF' sentences also emit a qualifier-dropped copy;
    'INVENT' plants an unsupported token; 'EMPTYME' yields []. Counts calls."""
    state = {"calls": 0}

    def caller(system: str, user: str) -> str:
        state["calls"] += 1
        m = re.search(r"<data:passage>\n(.*?)\n</data:passage>", user, re.S)
        text = m.group(1)
        if "EMPTYME" in text:
            return json.dumps({"propositions": []})
        props = []
        for s in sentences(text):
            props.append(s)
            if "sauf" in s.lower():
                props.append(re.sub(r",?\s*sauf[^.;]*", "", s,
                                    flags=re.IGNORECASE))
        if "INVENT" in text:
            props.append("Le zzzinventedzzz est obligatoire.")
        return json.dumps({"propositions": props[:12]}, ensure_ascii=False)
    caller.state = state
    return caller


def self_test() -> None:
    ok = lambda c, m: (print(f"  \u2713 {m}") if c else
                       (_ for _ in ()).throw(AssertionError(m)))
    with tempfile.TemporaryDirectory() as td:
        d = pathlib.Path(td)

        # 1 · roam segmenter exclusions
        exp = RH.make_demo_export()
        exp.append({"title": "Segmenter traps", "children": [
            {"uid": "t1", "string": "```clojure\n(println :code-block-here-long-enough)\n```", "create-time": 0, "edit-time": 0, "children": []},
            {"uid": "t2", "string": "{{[[query]]: {and: [[RGPD]] [[DPA]]} } padding padding}", "create-time": 0, "edit-time": 0, "children": []},
            {"uid": "t3", "string": "[[RGPD]] [[DPA]] [[DPO]] [[Article 28]] [[Article 5]]", "create-time": 0, "edit-time": 0, "children": []},
            {"uid": "t4", "string": "trop court", "create-time": 0, "edit-time": 0, "children": []},
            {"uid": "t5", "string": "Une phrase parfaitement valide sur la conservation des donn\u00e9es.", "create-time": 0, "edit-time": 0, "children": []}]})
        (d / "g.json").write_text(json.dumps(exp, ensure_ascii=False))
        units = segment_roam(d / "g.json")
        uids = {u["unit_id"] for u in units}
        ok("t5" in uids and not ({"t1", "t2", "t3", "t4"} & uids),
           "C1: roam segmenter excludes code/query/ref-only/short")

        # 2 · text segmenter
        (d / "doc.md").write_text(
            "Premier paragraphe suffisamment long pour \u00eatre une unit\u00e9.\n\n"
            "court\n\n"
            "Deuxi\u00e8me paragraphe \u00e9galement assez long pour compter.",
            encoding="utf-8")
        tunits = segment_text(d / "doc.md")
        ok(len(tunits) == 2 and tunits[0]["locator"].endswith("para-0"),
           "C2: text segmenter paragraphs + band")

        # 3 · determinism + cache
        mock = make_mock()
        u5 = [u for u in units if u["unit_id"] == "t5"]
        s1 = run(u5, mock, d / "o1", "mock@0#p1")
        ids1 = [json.loads(l)["prop_id"] for l in
                (d / "o1/propositions.jsonl").read_text().splitlines()]
        calls_after_first = mock.state["calls"]
        s2 = run(u5, mock, d / "o1", "mock@0#p1")   # same out-dir => warm cache
        ok(mock.state["calls"] == calls_after_first and s2["cache_hits"] == 1,
           "C3a: second run = pure cache hit (0 new calls)")
        ids2 = [json.loads(l)["prop_id"] for l in
                (d / "o1/propositions.jsonl").read_text().splitlines()][len(ids1):]
        ok(ids1 == ids2, "C3b: prop_ids deterministic across runs")

        # 4-6 · alignment
        unit_a = {"unit_id": "ua", "text":
                  "Le registre est tenu par le DPO. La clause d'audit figure "
                  "au paragraphe sept du contrat Hexalog. Fin du passage.",
                  "source_doc": "t", "locator": "t"}
        span, _, conf = align_span(
            "La clause d'audit figure au paragraphe sept du contrat Hexalog.",
            unit_a["text"])
        ok(span.startswith("La clause d'audit") and conf >= 0.9,
           f"C4: exact sentence aligned (conf {conf})")
        span, _, conf = align_span(
            "Le registre est tenu par le DPO et la clause d'audit figure au "
            "paragraphe sept.", unit_a["text"])
        ok("registre" in span and "audit" in span and conf >= 0.7,
           "C5: merged proposition -> 2-sentence window")
        span, _, _ = align_span("alpha beta", "alpha beta gamma. alpha beta gamma.")
        ok(span == "alpha beta gamma.", "C6: tie -> shortest, then earliest")

        # 7 · planted qualifier-dropper reaches the judge as lost-qualifier shape
        unit_q = {"unit_id": "uq", "text":
                  "Les donn\u00e9es sont conserv\u00e9es 36 mois, sauf obligation "
                  "l\u00e9gale contraire.", "source_doc": "t", "locator": "t"}
        run([unit_q], mock, d / "oq", "mock@0#p1")
        rows = [json.loads(l) for l in
                (d / "oq/faithful_candidates.jsonl").read_text().splitlines()]
        dropped = [r for r in rows
                   if "sauf" not in r["fields"]["proposition"].lower()
                   and "sauf" in r["fields"]["source_span"].lower()]
        ok(len(dropped) == 1, "C7: qualifier-dropped candidate pairs with full span")

        # 8 · planted invention -> low confidence
        unit_i = {"unit_id": "ui", "text":
                  "INVENT Le contrat pr\u00e9voit une notification sous 48 heures.",
                  "source_doc": "t", "locator": "t"}
        run([unit_i], mock, d / "oi", "mock@0#p1")
        rows = [json.loads(l) for l in
                (d / "oi/faithful_candidates.jsonl").read_text().splitlines()]
        inv = [r for r in rows if "zzzinventedzzz" in r["fields"]["proposition"]]
        ok(inv and inv[0]["meta"]["low_confidence"]
           and inv[0]["meta"]["span_confidence"] < LOW_CONFIDENCE,
           "C8: invented proposition flagged low-confidence")

        # 9 · every candidate builds a valid faithful judge prompt
        for r in rows:
            JP.build_user_prompt("faithful", r["fields"],
                                 JP.context_hash("faithful", 1, r["fields"]))
        ok(True, "C9: emission shape valid for the harness")

        # 10 · UTF-8 integrity
        ok("conserv\u00e9es" in rows[0]["fields"]["source_surrounding"]
           or any("\u00e9" in r["fields"]["proposition"] for r in rows),
           "C10: accents survive the pipeline")

        # 11 · empty decomposition
        st = run([{"unit_id": "ue", "text": "EMPTYME Question sans fait \u00e9nonc\u00e9 ?",
                   "source_doc": "t", "locator": "t"}], mock, d / "oe", "mock@0#p1")
        ok(st["propositions"] == 0 and st["failed_units"] == 0,
           "C11: empty list handled cleanly")

        # 12 · repair fallback + hard failure
        fenced = lambda s, u: "```json\n" + json.dumps(
            {"propositions": ["Une proposition."]}) + "\n```"
        ok(decompose("x. y.", fenced) == ["Une proposition."],
           "C12a: fenced JSON repaired")
        garbage = lambda s, u: "not json at all"
        st = run([{"unit_id": "ug", "text": "Un passage valide et assez long.",
                   "source_doc": "t", "locator": "t"}], garbage, d / "og", "g@0#p1")
        ok(st["failed_units"] == 1 and
           (d / "og/failed_units.jsonl").read_text().strip(),
           "C12b: double parse failure lands in failed_units.jsonl")

    print("all propositionizer self-tests passed (12 cases)")


# ===========================================================================
# CLI
# ===========================================================================

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--source", choices=["roam", "text"], required=True)
    r.add_argument("--export"); r.add_argument("--file")
    r.add_argument("--judge", default="anchor")
    r.add_argument("--config", default="judges_config.yaml")
    r.add_argument("--limit", type=int, default=None)
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--out-dir", default="props")
    r.add_argument("--dry-run", action="store_true")
    st = sub.add_parser("stats"); st.add_argument("--out-dir", default="props")
    sub.add_parser("self-test")
    a = ap.parse_args()

    if a.cmd == "self-test":
        self_test(); return
    if a.cmd == "stats":
        p = pathlib.Path(a.out_dir) / "faithful_candidates.jsonl"
        rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
        confs = [r["meta"]["span_confidence"] for r in rows]
        hist = Counter(round(c, 1) for c in confs)
        print(json.dumps({"candidates": len(rows),
                          "low_confidence": sum(r["meta"]["low_confidence"]
                                                for r in rows),
                          "confidence_hist": {str(k): v for k, v
                                              in sorted(hist.items())}},
                         indent=2))
        return

    units = (segment_roam(pathlib.Path(a.export)) if a.source == "roam"
             else segment_text(pathlib.Path(a.file)))
    if a.limit:
        import random as _r
        _r.Random(a.seed).shuffle(units)
        units = units[: a.limit]
    if a.dry_run:
        for u in units[:2]:
            print("=" * 72); print(build_decomp_prompt(u["text"]))
        return
    judge = JH.load_judge(a.config, a.judge)
    stats = run(units, llm_caller(judge), pathlib.Path(a.out_dir),
                judge.judge_id)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()

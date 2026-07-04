#!/usr/bin/env python3
"""shacl_lint.py — SHACL lint runner for the Mnemosyne shape pack
(WP-1c, SPEC-04).

Closed-world discipline (normative): validation runs with inference="none" —
SHACL judges the data graph AS GIVEN, which is exactly the linter's contract.
The shapes live in shapes/*.ttl; the vocabulary in context/mnemo.jsonld.
Two shapes are PORT-RISK-tagged for the Fluree transaction-time subset
(S6 sh:sparql; S2/S7 sh:qualifiedValueShape) — see SPEC-04 §3.

Subcommands:
  export        --roam export.json [--plant-violation] -> out.jsonld
  lint          --data g.jsonld [--shapes shapes/] [--strict-warnings]
  make-fixtures [--dir fixtures/]     (deterministic fixture matrix)
  self-test

Exit codes (CI contract): 0 conforms (warnings tolerated unless
--strict-warnings), 1 violations, 2 runner error.
"""

from __future__ import annotations
import argparse
import json
import pathlib
import sys
from typing import Dict, List, Optional

MNEMO = "https://mnemosyne.dev/ns#"
SH = "http://www.w3.org/ns/shacl#"
URN = "urn:mnemo:node:"


def iri(nid: str) -> str:
    return nid if nid.startswith("urn:") else URN + nid


# ===========================================================================
# Expanded-JSON-LD node builder (no context resolution needed downstream)
# ===========================================================================

def N(nid: str, types: List[str], **props) -> dict:
    node = {"@id": iri(nid), "@type": [MNEMO + t for t in types]}
    for k, v in props.items():
        vals = v if isinstance(v, list) else [v]
        out = []
        for x in vals:
            if isinstance(x, bool):
                out.append({"@value": x})
            elif isinstance(x, str) and x.startswith("ref:"):
                out.append({"@id": iri(x[4:])})
            else:
                out.append({"@value": x})
        node[MNEMO + k] = out
    return node


def write_graph(nodes: List[dict], path: pathlib.Path) -> None:
    path.write_text(json.dumps(sorted(nodes, key=lambda n: n["@id"]),
                               indent=1, ensure_ascii=False))


# ===========================================================================
# Exporter (--roam smoke mode, SPEC-04 §1/§6)
# ===========================================================================

def export_roam(export_path: pathlib.Path, plant_violation: bool) -> List[dict]:
    import roam_harvest as RH
    g = RH.Graph.parse(json.loads(export_path.read_text()))
    nodes = []
    for title in sorted(g.pages):
        nodes.append(N("page:" + title, ["Page"], text=title))
    for uid in sorted(g.blocks):
        b = g.blocks[uid]
        nodes.append(N(uid, ["Block"], text=b["string"],
                       mentions=[f"ref:page:{r}" for r in sorted(b["refs"])]))
    if plant_violation:  # SPEC-04 §6: S1 must fire on the planted node
        nodes.append(N("pa-planted", ["ProcessingActivity"],
                       text="Traitement RH sans base légale déclarée"))
    return nodes


# ===========================================================================
# Lint
# ===========================================================================

def load_shapes_graph(shapes_dir: pathlib.Path):
    from rdflib import Graph
    sg = Graph()
    for ttl in sorted(shapes_dir.glob("*.ttl")):
        sg.parse(ttl, format="turtle")
    return sg


def lint(data_path: pathlib.Path, shapes_dir: pathlib.Path) -> dict:
    from rdflib import Graph
    from pyshacl import validate
    dg = Graph()
    dg.parse(data_path, format="json-ld")
    conforms, results_graph, _ = validate(
        dg, shacl_graph=load_shapes_graph(shapes_dir),
        inference="none",       # normative: closed-world posture (SPEC-04 §5)
        advanced=True)          # sh:sparql support
    from rdflib.namespace import Namespace
    sh = Namespace(SH)
    def _term(v) -> str:
        s = str(v or "")
        # blank-node labels (e.g. path expressions like [sh:inversePath …])
        # vary across parses — normalize them out of the report.
        return s if ("://" in s or s.startswith("urn:")) else ""
    rows = []
    for r in results_graph.subjects(predicate=None, object=sh.ValidationResult):
        get = lambda p: results_graph.value(r, p)
        rows.append({
            "focusNode": _term(get(sh.focusNode)),
            "shape": _term(get(sh.sourceShape)),
            "severity": str(get(sh.resultSeverity) or "").split("#")[-1],
            "message": str(get(sh.resultMessage) or ""),
            "path": _term(get(sh.resultPath))})
    rows.sort(key=lambda x: (x["focusNode"], x["shape"], x["message"]))
    n_viol = sum(1 for x in rows if x["severity"] == "Violation")
    n_warn = sum(1 for x in rows if x["severity"] == "Warning")
    return {"conforms": bool(conforms), "n_violations": n_viol,
            "n_warnings": n_warn, "results": rows}


def exit_code(report: dict, strict_warnings: bool) -> int:
    if report["n_violations"] > 0:
        return 1
    if strict_warnings and report["n_warnings"] > 0:
        return 1
    return 0


# ===========================================================================
# Fixture matrix (SPEC-04 §6) — deterministic, generated, checked in
# ===========================================================================

def fixtures() -> Dict[str, List[dict]]:
    """Per shape: sN_ok (conforming) and sN_bad (exactly one result of that
    shape). Fixtures are constructed to be mutually non-triggering — e.g.
    every PermanentNote fixture that isn't testing S8 carries faithful=true."""
    fx: Dict[str, List[dict]] = {}
    # S1
    fx["s1_ok"] = [N("pa1", ["ProcessingActivity"], legalBasis="art. 6(1)(b)")]
    fx["s1_bad"] = [N("pa1", ["ProcessingActivity"], text="no basis")]
    # S2 (Warning): supports edge = reified DiscourseEdge with from/to/edgeType
    fx["s2_ok"] = [N("clm1", ["Claim"], text="c"),
                   N("e1", ["DiscourseEdge"], **{"from": "ref:evd1",
                     "to": "ref:clm1", "edgeType": "supports"})]
    fx["s2_bad"] = [N("clm1", ["Claim"], text="c"),
                    N("e1", ["DiscourseEdge"], **{"from": "ref:evd1",
                      "to": "ref:clm1", "edgeType": "opposes"})]
    # S3 (PermanentNote orphan) — faithful=true everywhere to isolate from S8
    fx["s3_ok"] = [N("p1", ["PermanentNote", "Proposition"],
                     faithful=True, continues="ref:p0"),
                   N("p2", ["PermanentNote", "Proposition"],
                     faithful=True, trainHead=True)]
    fx["s3_bad"] = [N("p1", ["PermanentNote", "Proposition"], faithful=True)]
    # S4
    fx["s4_ok"] = [N("kw1", ["RegisterKeyword"], keyword="rgpd",
                     entry=["ref:n1", "ref:n2"])]
    fx["s4_bad"] = [N("kw1", ["RegisterKeyword"], keyword="rgpd",
                      entry=["ref:n1", "ref:n2", "ref:n3"])]
    # S5 (missing exactly calVersion => exactly one result)
    fx["s5_ok"] = [N("j1", ["Judgment"], judge="qwen@a#p1", contextHash="h",
                     calVersion="cal-1", label="supports")]
    fx["s5_bad"] = [N("j1", ["Judgment"], judge="qwen@a#p1", contextHash="h",
                      label="supports")]
    # S6 (sparql)
    fx["s6_ok"] = [N("st1", ["Stance"], basis="ref:pp1"),
                   N("pp1", ["Proposition"], kind="permanent")]
    fx["s6_bad"] = [N("st1", ["Stance"], basis="ref:pp1"),
                    N("pp1", ["Proposition"], kind="literature")]
    # S7 (Warning)
    fx["s7_ok"] = [N("d1", ["StaleDerived"], stale=True),
                   N("t1", ["Task"], parent="ref:d1", status="open")]
    fx["s7_bad"] = [N("d1", ["StaleDerived"], stale=True)]
    # S8 (faithful gate) — continues present to isolate from S3
    fx["s8_ok"] = [N("p1", ["PermanentNote"], faithful=True,
                     continues="ref:p0")]
    fx["s8_bad"] = [N("p1", ["PermanentNote"], continues="ref:p0")]
    # combined
    fx["all_ok"] = [n for k in sorted(fx) if k.endswith("_ok")
                    and not k.startswith("all")
                    for n in _rekey(fx[k], k)]
    fx["kitchen_sink_bad"] = [n for k in sorted(fx)
                              if k.endswith("_bad") and "kitchen" not in k
                              for n in _rekey(fx[k], k)]
    return fx


def _rekey(nodes: List[dict], prefix: str) -> List[dict]:
    """Namespace every @id/@id-ref so combined fixtures don't collide."""
    def rk(x):
        if isinstance(x, dict):
            return {k: (URN + prefix + ":" + v[len(URN):]
                        if k == "@id" and isinstance(v, str)
                        and v.startswith(URN) else rk(v))
                    for k, v in x.items()}
        if isinstance(x, list):
            return [rk(i) for i in x]
        return x
    return [rk(n) for n in nodes]


EXPECT_BAD = {  # shape id fragment, expected severity, focus fragment
    "s1_bad": ("S1", "Violation", "pa1"),
    "s2_bad": ("S2", "Warning", "clm1"),
    "s3_bad": ("S3", "Violation", "p1"),
    "s4_bad": ("S4", "Violation", "kw1"),
    "s5_bad": ("S5", "Violation", "j1"),
    "s6_bad": ("S6", "Violation", "st1"),
    "s7_bad": ("S7", "Warning", "d1"),
    "s8_bad": ("S8", "Violation", "p1"),
}


def make_fixtures(fdir: pathlib.Path) -> int:
    fdir.mkdir(parents=True, exist_ok=True)
    fx = fixtures()
    for name, nodes in fx.items():
        write_graph(nodes, fdir / f"{name}.jsonld")
    return len(fx)


# ===========================================================================
# Self-test
# ===========================================================================

def self_test() -> None:
    ok = lambda c, m: (print(f"  \u2713 {m}") if c else
                       (_ for _ in ()).throw(AssertionError(m)))
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        fdir = pathlib.Path(td) / "fixtures"
        n = make_fixtures(fdir)
        ok(n == 18, f"fixture matrix complete ({n} files)")
        shapes = pathlib.Path("shapes")

        for name, (shape, sev, focus) in EXPECT_BAD.items():
            okrep = lint(fdir / f"{name.replace('_bad','_ok')}.jsonld", shapes)
            ok(okrep["conforms"] and not okrep["results"],
               f"{name.replace('_bad','_ok')}: conforms")
            bad = lint(fdir / f"{name}.jsonld", shapes)
            ok(len(bad["results"]) == 1, f"{name}: exactly one result")
            r = bad["results"][0]
            ok(("#" + shape) in r["shape"] and r["severity"] == sev
               and focus in r["focusNode"],
               f"{name}: {shape}/{sev} on {focus}")

        allok = lint(fdir / "all_ok.jsonld", shapes)
        ok(allok["conforms"], "all_ok: combined graph conforms")
        sink = lint(fdir / "kitchen_sink_bad.jsonld", shapes)
        ok(len(sink["results"]) == 8, f"kitchen sink: 8 results "
           f"({sink['n_violations']}V+{sink['n_warnings']}W)")
        ok(sink["n_violations"] == 6 and sink["n_warnings"] == 2,
           "kitchen sink: 6 Violations + 2 Warnings")

        # exit-code contract
        warn_only = lint(fdir / "s2_bad.jsonld", shapes)
        ok(exit_code(warn_only, strict_warnings=False) == 0
           and exit_code(warn_only, strict_warnings=True) == 1,
           "warnings gate only under --strict-warnings")
        ok(exit_code(sink, strict_warnings=False) == 1, "violations => exit 1")

        # determinism
        r1 = lint(fdir / "kitchen_sink_bad.jsonld", shapes)
        r2 = lint(fdir / "kitchen_sink_bad.jsonld", shapes)
        ok(json.dumps(r1) == json.dumps(r2), "report deterministic")

        # roam export smoke + planted S1
        import roam_harvest as RH
        exp = pathlib.Path(td) / "demo.json"
        exp.write_text(json.dumps(RH.make_demo_export(), ensure_ascii=False))
        gp = pathlib.Path(td) / "roam.jsonld"
        write_graph(export_roam(exp, plant_violation=True), gp)
        rep = lint(gp, shapes)
        ok(len(rep["results"]) == 1 and "#S1" in rep["results"][0]["shape"]
           and "pa-planted" in rep["results"][0]["focusNode"],
           "roam export: parses; planted S1 fires; nothing else")
    print("all shacl self-tests passed")


# ===========================================================================
# CLI
# ===========================================================================

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--roam", required=True)
    e.add_argument("--out", default="out.jsonld")
    e.add_argument("--plant-violation", action="store_true")
    l = sub.add_parser("lint")
    l.add_argument("--data", required=True)
    l.add_argument("--shapes", default="shapes")
    l.add_argument("--strict-warnings", action="store_true")
    l.add_argument("--out", default=None)
    f = sub.add_parser("make-fixtures")
    f.add_argument("--dir", default="fixtures")
    sub.add_parser("self-test")
    a = ap.parse_args()
    try:
        if a.cmd == "self-test":
            self_test()
        elif a.cmd == "make-fixtures":
            print(f"wrote {make_fixtures(pathlib.Path(a.dir))} fixtures -> {a.dir}/")
        elif a.cmd == "export":
            write_graph(export_roam(pathlib.Path(a.roam), a.plant_violation),
                        pathlib.Path(a.out))
            print(f"wrote {a.out}")
        else:
            rep = lint(pathlib.Path(a.data), pathlib.Path(a.shapes))
            if a.out:
                pathlib.Path(a.out).write_text(json.dumps(rep, indent=2))
            print(json.dumps(rep, indent=2))
            sys.exit(exit_code(rep, a.strict_warnings))
    except SystemExit:
        raise
    except Exception as ex:
        print(f"runner error: {ex}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""infra_check.py — B6 pre-flight smoke test for the judge/anchor endpoints.

The harness is ready; the ONLY thing between it and a real run is whether a
configured endpoint actually serves what it claims. This tool verifies that,
per judge, in the mode declared in the config — and, crucially, tests the
EXACT scoring call the harness makes (`completions` with echo=True + logprobs +
max_tokens=0 on a ~20-token prompt), because a generic /models ping does NOT
prove that echo-logprob scoring works (ANNEX_B6 §1: OpenAI removed echo+logprobs;
only raw-vLLM-completions providers pass).

Subcommands:
  all        check every judge in the config, in its declared mode
  judge      check one judge (--judge NAME)
  self-test  MOCK each failure family (no network) and assert its return code

Return codes (ANNEX_B6 §3):
  0  ok
  10 network      endpoint unreachable
  11 auth         authentication rejected
  12 model-mismatch  served model != declared `model`
  13 capability   no logprobs / echo (api-logprobs & vllm-local); or
                  api-selfreport declared without self_reported_ok: true; or
                  vllm-local weights hash is still a placeholder
  14 config-invalid  missing/unknown mode, unreadable config, etc.

`--json` prints one machine-readable object to stdout (B4 stage-0: a mismatch =>
the judge is quarantined for the cycle). Human logs go to stderr.

stdlib + openai + pyyaml only. self-test needs no network (client is mocked).
"""

from __future__ import annotations
import argparse
import dataclasses
import json
import pathlib
import sys
import time
from typing import Callable, Dict, List, Optional

# Return codes
OK = 0
NETWORK = 10
AUTH = 11
MODEL_MISMATCH = 12
CAPABILITY = 13
CONFIG_INVALID = 14

VALID_MODES = {"api-logprobs", "api-topk", "api-selfreport", "vllm-local"}
# ANNEX_B6 §1: the echo+logprobs call is tested on a ~20-token prompt.
PROBE_PROMPT = ("Score this short probe prompt for echo logprobs support now "
                "so the harness can run: alpha beta gamma delta epsilon zeta.")
PLACEHOLDER_HASHES = {"", "hash", "0" * 8, "abcd1234", "8f3a21c0"}  # example YAML hashes


class CheckError(Exception):
    """Carries a return code + human message for a failed check."""
    def __init__(self, code: int, msg: str):
        super().__init__(msg)
        self.code = code
        self.msg = msg


# ---------------------------------------------------------------------------
# Config loading (env interpolation + validation) — reuses the harness loader
# ---------------------------------------------------------------------------

def load_config(path: str) -> dict:
    import yaml
    p = pathlib.Path(path)
    if not p.exists():
        raise CheckError(CONFIG_INVALID, f"config not found: {path}")
    try:
        cfg = yaml.safe_load(p.read_text())
    except Exception as e:  # noqa: BLE001
        raise CheckError(CONFIG_INVALID, f"config unparseable: {e}")
    if not isinstance(cfg, dict) or "judges" not in cfg:
        raise CheckError(CONFIG_INVALID, "config has no 'judges' block")
    return cfg


# ---------------------------------------------------------------------------
# Client seam (mocked in self-test)
# ---------------------------------------------------------------------------

def default_client_factory(judge):
    from openai import OpenAI
    return OpenAI(base_url=judge.base_url, api_key=judge.api_key)


def _classify_openai_error(e: Exception) -> int:
    """Map an OpenAI/transport exception onto a diagnostic return code."""
    name = type(e).__name__.lower()
    txt = str(e).lower()
    if "authentic" in name or "permission" in name or "401" in txt or \
       "invalid api key" in txt or "unauthorized" in txt:
        return AUTH
    if "connection" in name or "timeout" in name or "apiconnection" in name or \
       "network" in txt or "refused" in txt or "could not connect" in txt:
        return NETWORK
    return NETWORK  # default network-ish for unclassified transport failures


# ---------------------------------------------------------------------------
# Individual checks — each raises CheckError on failure, returns info on success
# ---------------------------------------------------------------------------

def check_endpoint_and_model(cli, judge) -> dict:
    """/models reachable AND served model == declared `model`."""
    try:
        listing = cli.models.list()
    except Exception as e:  # noqa: BLE001
        raise CheckError(_classify_openai_error(e),
                         f"/models unreachable: {e}")
    served = [getattr(m, "id", None) for m in getattr(listing, "data", [])]
    served = [s for s in served if s]
    if judge.model not in served:
        raise CheckError(
            MODEL_MISMATCH,
            f"declared model {judge.model!r} not served (served: {served})")
    return {"served_models": served}


def check_echo_logprobs(cli, judge) -> dict:
    """The EXACT harness scoring call: completions echo+logprobs+max_tokens=0
    on a ~20-token prompt. BLOCKING for api-logprobs / vllm-local."""
    try:
        r = cli.completions.create(
            model=judge.model, prompt=PROBE_PROMPT, max_tokens=0,
            temperature=0.0, echo=True, logprobs=0)
    except Exception as e:  # noqa: BLE001
        # a provider that rejects echo+logprobs typically 400s here => capability
        code = _classify_openai_error(e)
        if code == NETWORK and ("echo" in str(e).lower()
                                or "logprob" in str(e).lower()
                                or "400" in str(e).lower()):
            code = CAPABILITY
        raise CheckError(code if code == AUTH else CAPABILITY,
                         f"echo+logprobs completions call failed: {e}")
    lp = r.choices[0].logprobs
    if lp is None or getattr(lp, "token_logprobs", None) in (None, []):
        raise CheckError(CAPABILITY,
                         "provider returned no prompt logprobs (echo unsupported)")
    return {"n_logprob_tokens": len(lp.token_logprobs)}


def check_topk_logprobs(cli, judge) -> dict:
    """The topk scoring capability (harness --mode topk): chat completion
    with logprobs=True + top_logprobs, honoring judge.extra_body (provider
    pinning — without require_parameters an aggregator may route to a
    provider that silently drops logprobs). BLOCKING for api-topk."""
    t0 = time.time()
    try:
        r = cli.chat.completions.create(
            model=judge.model, temperature=0.0, max_tokens=2,
            logprobs=True, top_logprobs=20,
            messages=[{"role": "user",
                       "content": "Reply with exactly one word: probe"}],
            extra_body=dict(getattr(judge, "extra_body", {}) or {}))
    except Exception as e:  # noqa: BLE001
        code = _classify_openai_error(e)
        raise CheckError(code if code == AUTH else CAPABILITY,
                         f"chat top_logprobs call failed: {e}")
    lps = r.choices[0].logprobs
    content = getattr(lps, "content", None) if lps else None
    if not content or not getattr(content[0], "top_logprobs", None):
        raise CheckError(CAPABILITY,
                         "provider returned no top_logprobs on chat "
                         "(pin a capable provider via extra_body)")
    return {"n_alternatives": len(content[0].top_logprobs),
            "latency_s": round(time.time() - t0, 2)}


def check_scoring_latency(cli, judge, n_labels: int = 4) -> dict:
    """Informational: time a small n_labels echo scoring pass."""
    t0 = time.time()
    try:
        for _ in range(n_labels):
            cli.completions.create(
                model=judge.model, prompt=PROBE_PROMPT, max_tokens=1,
                temperature=0.0, echo=True, logprobs=0)
    except Exception:  # noqa: BLE001
        return {"latency_s": None}  # non-blocking
    return {"latency_s": round(time.time() - t0, 3)}


def check_anchor_fixture(cli, judge, cfg: dict, judge_name: str,
                         fixture: str = "fixtures/anchor_one.jsonl") -> dict:
    """Label 1 fixture with the anchor + show estimated cost (ANNEX_B6 §3)."""
    import anchor_label as AL
    import judge_prompts as JP
    import spend as _spend
    p = pathlib.Path(fixture)
    if not p.exists():
        raise CheckError(CONFIG_INVALID, f"anchor fixture missing: {fixture}")
    rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    if not rows:
        raise CheckError(CONFIG_INVALID, f"anchor fixture empty: {fixture}")
    cand = rows[0]
    jtype = cand["jtype"]
    ch = JP.context_hash(jtype, judge.prompt_version, cand["fields"])
    user = AL.build_anchor_user(jtype, cand["fields"], ch, salt=0)
    # THE anchor call (§1: test the exact call, not a replica) — anchor_call
    # takes an injected client, so the check and production share one path.
    try:
        verdict, tin, tout = AL.anchor_call(judge, jtype, user, cli=cli)
    except Exception as e:  # noqa: BLE001
        code = _classify_openai_error(e)
        raise CheckError(code if code == AUTH else CAPABILITY,
                         f"anchor labeling call failed: {e}")
    if not isinstance(verdict, dict) or "label" not in verdict:
        raise CheckError(CAPABILITY,
                         f"anchor verdict missing 'label': {verdict!r:.120}")
    pr = _spend.judge_price(cfg, judge_name)
    usd = (tin / 1e6) * pr["input_per_mtok"] + (tout / 1e6) * pr["output_per_mtok"]
    return {"label": verdict.get("label"), "tokens_in": tin,
            "tokens_out": tout, "est_usd_this_call": round(usd, 6)}


def check_weights_hash_real(judge) -> dict:
    """vllm-local: the weights hash in judge_id must not be a placeholder."""
    jid = judge.judge_id
    # judge_id is <model>@<hash>#p<v>; extract the hash between '@' and '#'
    at, hsh = jid.find("@"), None
    if at != -1:
        rest = jid[at + 1:]
        hsh = rest.split("#", 1)[0]
    if not hsh or hsh in PLACEHOLDER_HASHES or hsh.startswith("api"):
        raise CheckError(
            CAPABILITY,
            f"vllm-local weights hash looks like a placeholder: {hsh!r} "
            f"(pin real sha256 => judge_id becomes deterministic)")
    return {"weights_hash": hsh}


# ---------------------------------------------------------------------------
# Per-judge driver
# ---------------------------------------------------------------------------

def check_one(cfg: dict, judge_name: str,
              client_factory: Callable = default_client_factory) -> dict:
    """Run the mode-appropriate checks for one judge. Returns a result dict
    {judge, mode, status: ok|fail, code, checks{}, message?}. Never raises."""
    result = {"judge": judge_name, "status": "ok", "code": OK, "checks": {}}
    try:
        judge = load_judge_from_cfg(cfg, judge_name)
        mode = judge.mode
        result["mode"] = mode
        if judge.family == "anchor":
            mode = "anchor"
            result["mode"] = "anchor"
        elif mode not in VALID_MODES:
            raise CheckError(CONFIG_INVALID,
                             f"judge {judge_name}: invalid/absent mode {mode!r}")
        cli = client_factory(judge)

        # endpoint + served-model check applies to every family
        result["checks"]["endpoint_model"] = check_endpoint_and_model(cli, judge)

        if mode == "anchor":
            result["checks"]["anchor_fixture"] = check_anchor_fixture(
                cli, judge, cfg, judge_name)
        elif mode == "api-logprobs":
            result["checks"]["echo_logprobs"] = check_echo_logprobs(cli, judge)
            result["checks"]["latency"] = check_scoring_latency(cli, judge)
        elif mode == "api-topk":
            result["checks"]["topk_logprobs"] = check_topk_logprobs(cli, judge)
        elif mode == "vllm-local":
            result["checks"]["weights_hash"] = check_weights_hash_real(judge)
            result["checks"]["echo_logprobs"] = check_echo_logprobs(cli, judge)
            result["checks"]["latency"] = check_scoring_latency(cli, judge)
        elif mode == "api-selfreport":
            # echo is NOT required; the fallback must be EXPLICITLY enabled.
            if not judge.self_reported_ok:
                raise CheckError(
                    CAPABILITY,
                    f"judge {judge_name}: mode api-selfreport but "
                    f"self_reported_ok is not true (I3 fallback not enabled)")
            result["checks"]["self_report"] = {"self_reported_ok": True}
            result["checks"]["latency"] = check_scoring_latency(cli, judge)
    except CheckError as e:
        result["status"] = "fail"
        result["code"] = e.code
        result["message"] = e.msg
    return result


def load_judge_from_cfg(cfg: dict, name: str):
    """Build a Judge from an already-loaded (env-interpolated done later) cfg.
    We interpolate + drop unknown keys here to match the harness loader."""
    from judge_harness import Judge, interpolate_env
    if name not in cfg.get("judges", {}):
        raise CheckError(CONFIG_INVALID, f"no such judge: {name}")
    try:
        raw = interpolate_env(cfg["judges"][name])
    except KeyError as e:
        raise CheckError(CONFIG_INVALID, f"unset env var: {e}")
    known = {f.name for f in dataclasses.fields(Judge)}
    return Judge(**{k: v for k, v in raw.items() if k in known})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _report(results: List[dict], as_json: bool) -> int:
    worst = OK
    for r in results:
        if r["code"] != OK:
            worst = r["code"] if worst == OK else worst
    if as_json:
        print(json.dumps({"results": results, "code": worst}, ensure_ascii=False))
    else:
        for r in results:
            tag = "OK" if r["status"] == "ok" else f"FAIL({r['code']})"
            line = f"[{tag}] {r['judge']} mode={r.get('mode','?')}"
            if r["status"] != "ok":
                line += f" — {r.get('message','')}"
            print(line, file=sys.stderr)
            for cname, cval in r.get("checks", {}).items():
                print(f"    · {cname}: {cval}", file=sys.stderr)
    return worst


def cli_all(args) -> int:
    try:
        cfg = load_config(args.config)
    except CheckError as e:
        if args.json:
            print(json.dumps({"results": [], "code": e.code,
                              "message": e.msg}))
        else:
            print(f"[FAIL({e.code})] {e.msg}", file=sys.stderr)
        return e.code
    results = [check_one(cfg, name) for name in cfg["judges"]]
    return _report(results, args.json)


def cli_judge(args) -> int:
    try:
        cfg = load_config(args.config)
    except CheckError as e:
        if args.json:
            print(json.dumps({"results": [], "code": e.code, "message": e.msg}))
        else:
            print(f"[FAIL({e.code})] {e.msg}", file=sys.stderr)
        return e.code
    results = [check_one(cfg, args.judge)]
    return _report(results, args.json)


# ---------------------------------------------------------------------------
# Self-test — MOCK each failure family; assert each return code. No network.
# ---------------------------------------------------------------------------

def self_test() -> None:
    ok = lambda c, msg: (print(f"  ✓ {msg}") if c else
                         (_ for _ in ()).throw(AssertionError(msg)))

    # ---- mock client families ---------------------------------------------
    class _Model:
        def __init__(self, mid): self.id = mid

    class _Listing:
        def __init__(self, ids): self.data = [_Model(i) for i in ids]

    class _LP:
        def __init__(self, toks): self.token_logprobs = toks; self.text_offset = list(range(len(toks)))

    class _CompChoice:
        def __init__(self, lp): self.logprobs = lp

    class _CompResp:
        def __init__(self, lp): self.choices = [_CompChoice(lp)]

    class _Usage:
        prompt_tokens = 1200
        completion_tokens = 40

    class _ChatMsg:
        def __init__(self, content): self.content = content

    class _ChatChoice:
        def __init__(self, content): self.message = _ChatMsg(content)

    class _ChatResp:
        def __init__(self, content):
            self.choices = [_ChatChoice(content)]; self.usage = _Usage()

    class _NetworkError(Exception):
        pass  # name lacks 'auth' => classified NETWORK

    class _AuthError(Exception):
        pass

    def make_client(served=("Qwen/Qwen3-8B",), lp=(-0.1, -0.2),
                    fail_models=None, fail_echo=None, chat_content=None):
        class _Cli:
            class models:
                @staticmethod
                def list():
                    if fail_models:
                        raise fail_models
                    return _Listing(served)

            class completions:
                @staticmethod
                def create(**kw):
                    if fail_echo:
                        raise fail_echo
                    return _CompResp(_LP(list(lp)) if lp is not None else None)

            class chat:
                class completions:
                    @staticmethod
                    def create(**kw):
                        return _ChatResp(chat_content or
                                         '{"label":"opposes","difficulty":"easy",'
                                         '"flag_for_human":false}')
        return _Cli()

    base = {"judge_id": "qwen3-8b@api-x-2026#p1", "model": "Qwen/Qwen3-8B",
            "family": "qwen", "base_url": "http://x/v1",
            "api_key": "k", "prompt_version": 1, "price": {}}

    def cfg_with(mode, **over):
        j = dict(base); j["mode"] = mode; j.update(over)
        return {"judges": {"qwen-a": j},
                "spend": {"max_usd_per_run": 10.0, "ledger": "ops/spend.jsonl"}}

    # 0 — happy path, api-logprobs
    r = check_one(cfg_with("api-logprobs"), "qwen-a",
                  client_factory=lambda j: make_client())
    ok(r["code"] == OK, f"api-logprobs healthy => 0 (got {r['code']})")

    # 10 — network: /models raises a connection error
    r = check_one(cfg_with("api-logprobs"), "qwen-a",
                  client_factory=lambda j: make_client(
                      fail_models=_NetworkError("connection refused")))
    ok(r["code"] == NETWORK, f"unreachable /models => 10 (got {r['code']})")

    # 11 — auth: /models raises an auth error
    r = check_one(cfg_with("api-logprobs"), "qwen-a",
                  client_factory=lambda j: make_client(
                      fail_models=_AuthError("401 invalid api key")))
    ok(r["code"] == AUTH, f"auth-rejected /models => 11 (got {r['code']})")

    # 12 — model mismatch: served model differs
    r = check_one(cfg_with("api-logprobs"), "qwen-a",
                  client_factory=lambda j: make_client(served=("other/Model",)))
    ok(r["code"] == MODEL_MISMATCH,
       f"served!=declared => 12 (got {r['code']})")

    # 13 — capability: echo returns no logprobs (None)
    r = check_one(cfg_with("api-logprobs"), "qwen-a",
                  client_factory=lambda j: make_client(lp=None))
    ok(r["code"] == CAPABILITY,
       f"api-logprobs w/ no logprobs => 13 (got {r['code']})")

    # 13 — capability: echo call itself rejected (400 echo unsupported)
    r = check_one(cfg_with("api-logprobs"), "qwen-a",
                  client_factory=lambda j: make_client(
                      fail_echo=_NetworkError("400 echo is not supported")))
    ok(r["code"] == CAPABILITY,
       f"echo rejected (400) => 13 (got {r['code']})")

    # 13 — api-selfreport without self_reported_ok
    r = check_one(cfg_with("api-selfreport", self_reported_ok=False), "qwen-a",
                  client_factory=lambda j: make_client())
    ok(r["code"] == CAPABILITY,
       f"selfreport w/o self_reported_ok => 13 (got {r['code']})")

    # 0 — api-selfreport WITH self_reported_ok (echo not required)
    r = check_one(cfg_with("api-selfreport", self_reported_ok=True), "qwen-a",
                  client_factory=lambda j: make_client(lp=None))
    ok(r["code"] == OK,
       f"selfreport + self_reported_ok, no echo needed => 0 (got {r['code']})")

    # 13 — vllm-local with placeholder weights hash
    r = check_one(cfg_with("vllm-local"), "qwen-a",   # hash is 'api-x-2026' => placeholder-ish (starts 'api')
                  client_factory=lambda j: make_client())
    ok(r["code"] == CAPABILITY,
       f"vllm-local placeholder hash => 13 (got {r['code']})")

    # 0 — vllm-local with a real-looking hash
    r = check_one(cfg_with("vllm-local", judge_id="qwen3-8b@deadbeefcafe1234#p1"),
                  "qwen-a", client_factory=lambda j: make_client())
    ok(r["code"] == OK,
       f"vllm-local real hash + logprobs => 0 (got {r['code']})")

    # 14 — invalid mode
    r = check_one(cfg_with("nonsense-mode"), "qwen-a",
                  client_factory=lambda j: make_client())
    ok(r["code"] == CONFIG_INVALID,
       f"invalid mode => 14 (got {r['code']})")

    # anchor happy path: labels the fixture, computes cost
    anchor_cfg = {"judges": {"anchor": {
        "judge_id": "anchor-large@api#p1", "model": "big-anchor",
        "family": "anchor", "base_url": "http://a/v1", "api_key": "k",
        "prompt_version": 1, "mode": "api-selfreport", "self_reported_ok": True,
        "price": {"input_per_mtok": 3.0, "output_per_mtok": 15.0}}},
        "spend": {"max_usd_per_run": 10.0, "ledger": "ops/spend.jsonl"}}
    r = check_one(anchor_cfg, "anchor",
                  client_factory=lambda j: make_client(served=("big-anchor",)))
    ok(r["code"] == OK and r["checks"]["anchor_fixture"]["label"] == "opposes",
       "anchor labels fixture + reports cost => 0")
    ok(r["checks"]["anchor_fixture"]["est_usd_this_call"] > 0,
       "anchor per-call cost estimated from price")

    # 14 — missing config file
    try:
        code = cli_all(argparse.Namespace(config="/no/such/config.yaml",
                                          json=True))
    except SystemExit as e:  # cli returns int, shouldn't SystemExit
        code = e.code
    ok(code == CONFIG_INVALID, f"missing config => 14 (got {code})")

    print("all self-tests passed")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("all", help="check every judge in the config")
    a.add_argument("--config", default="judges_config.yaml")
    a.add_argument("--json", action="store_true")

    j = sub.add_parser("judge", help="check one judge")
    j.add_argument("--judge", required=True)
    j.add_argument("--config", default="judges_config.yaml")
    j.add_argument("--json", action="store_true")

    sub.add_parser("self-test", help="mock each failure family; assert codes")

    args = ap.parse_args()
    if args.cmd == "self-test":
        self_test()
        return OK
    if args.cmd == "all":
        return cli_all(args)
    if args.cmd == "judge":
        return cli_judge(args)
    return CONFIG_INVALID


if __name__ == "__main__":
    sys.exit(main())

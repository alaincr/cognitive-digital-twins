# README_infra — bringing the judge/anchor inference online (brick B6)

Gap **G6** of `prd/00_gap_analysis.md`: the harness is ready but no real
inference endpoint exists. `judges_config.yaml` shipped with fake Tailscale
names, an `api.example.com` anchor, and decorative weight hashes, so
`first_judge.sh` dies at stage 2. This brick makes a **reduced loop** (one
judge + one anchor) runnable **without a local GPU**, and documents the path to
the full local fleet.

Normative sources: `prd/PRD_B6_judge_infra.md`,
`prd/annexes/ANNEX_B6_judge_infra.md`, `prd/annexes/INTERFACES.md`.

---

## 1 · The three modes

The harness never changes across modes — they are just different `base_url`s
plus a `mode` tag. Set `mode:` per judge in `judges_config.yaml`:

| mode | judge serving | logprobs (I3) | when |
|---|---|---|---|
| `api-logprobs` | a provider serving **raw vLLM completions** with `echo=True` | measured, full I3 | B6-lite, preferred: a hosted open-weights model that passes `infra_check` §1 |
| `api-selfreport` | any chat provider | self-reported, flagged `self_reported=true`, α hardened | contractual fallback (`microjudge_contract.md` I3); requires `self_reported_ok: true` set explicitly |
| `vllm-local` | your own vLLM server, pinned weights | measured, deterministic replay | B6-full (target) |

The anchor is separate: it emits constrained-JSON gold labels and needs **no**
logprobs, so `api-selfreport` + `self_reported_ok: true` is normal for it.

## 2 · The `echo=True` reality (why provider choice is narrow)

`judge_harness.py::score_labels_echo` scores each label with:

```python
client.completions.create(model=…, prompt=prefix+label,
                          echo=True, logprobs=0, temperature=0.0, max_tokens=0)
```

That is the **completions** endpoint (not chat) with the **prompt's own
logprobs echoed back** — it sums the label tokens' logprobs inside the prompt.
Consequences (ANNEX_B6 §1):

- **OpenAI removed** `echo=True`+logprobs on `/completions`; chat endpoints
  never return prompt logprobs. So OpenAI-proper cannot serve `api-logprobs`.
- The providers that work are those serving **raw vLLM (or equivalent)
  completions** — most open-weights hosts. You must verify **one by one** with
  `infra_check.py`, which tests *exactly this call* on a ~20-token probe, not a
  generic `/models` ping.
- If no provider passes: use `api-selfreport` (α hardened one notch, e.g. 0.03
  in T2 — set in the config, not the code) or go straight to `vllm-local`.

In `api-logprobs`, the harness now **raises on the first response with no
logprobs** unless `self_reported_ok: true` — I3 never degrades silently
(PRD §5 case 1).

## 3 · Config split and secrets

- `judges_config.example.yaml` — **committed** example (reduced loop:
  `qwen-a` + `anchor`, with the B6 keys `mode`, `self_reported_ok`, `price`,
  and the top-level `spend` block).
- `judges_config.yaml` — the **real** file, git-ignored (see `.gitignore`).
  Copy the example, fill real `base_url`s, set the `mode` per judge.
- API keys come from the **environment**: `api_key: "${JUDGE_API_KEY}"` /
  `"${ANCHOR_API_KEY}"` is interpolated at config load
  (`judge_harness.load_judge`). An unset referenced var fails loud; keys are
  never written in clear.
- New B6 keys are **retro-compatible**: the harness drops unknown keys and the
  `Judge` dataclass defaults `mode="vllm-local"`, `self_reported_ok=False`.
  Verified by `judge_harness.py self-test`.

```bash
cp judges_config.example.yaml judges_config.yaml
export JUDGE_API_KEY=…   ANCHOR_API_KEY=…
```

## 4 · `infra_check.py` — pre-flight smoke test

```bash
python3 infra_check.py all   --config judges_config.yaml            # all judges
python3 infra_check.py judge --judge qwen-a                         # one judge
python3 infra_check.py all   --config judges_config.yaml --json     # B4 stage-0
python3 infra_check.py self-test                                    # no network
```

Checks per mode (ANNEX_B6 §3): `/models` reachable · served model == declared
`model` · the exact echo+logprobs call (blocking for `api-logprobs` /
`vllm-local`; for `api-selfreport` it instead verifies `self_reported_ok:
true`) · scoring latency (info) · anchor: label `fixtures/anchor_one.jsonl` +
show estimated cost · `vllm-local`: weights hash ≠ placeholder.

**Return codes** (distinct for diagnosis):

| code | meaning |
|---|---|
| 0 | ok |
| 10 | network — endpoint unreachable |
| 11 | auth — authentication rejected |
| 12 | model-mismatch — served model ≠ declared (⇒ B4 quarantines the judge for the cycle) |
| 13 | capability — no logprobs/echo; or `api-selfreport` without `self_reported_ok: true`; or `vllm-local` placeholder hash |
| 14 | config-invalid — missing/unreadable config, absent/unknown `mode` |

`self-test` mocks each failure family (no network) and asserts every code.

**Provider selection (ops, ANNEX_B6 §6 task 4):** point `judges_config.yaml`
at 2–3 candidate providers in turn; the one that returns code 0 on the echo
check is your `api-logprobs` judge. If none do, harden to `api-selfreport`.

## 5 · Spend ledger and cap

`spend.py` is a stdlib cost meter used by `anchor_label.py` (and available to
the harness). Config (`judges_config.yaml`):

```yaml
judges: {anchor: {price: {input_per_mtok: 3.00, output_per_mtok: 15.00}}}
spend:  {max_usd_per_run: 10.0, ledger: "ops/spend.jsonl"}
```

- Each API call reports `(tokens_in, tokens_out)`; cost accrues at the judge's
  `price`.
- The ledger `ops/spend.jsonl` gets **one line per 25 calls plus a final
  line** — the INTERFACES.md B6 row
  `{run, judge, calls, tokens_in, tokens_out, usd, ts}` (running totals, not
  deltas).
- On reaching `max_usd_per_run` the run **stops cleanly** with valid partial
  outputs (calsets/review queue are written).
- **Resume:** re-run `anchor_label.py` with the same `--run <id>`; it reads the
  last ledger line for that run and continues from the projected spend rather
  than double-counting. Pair with `--limit` (already present) to bound a run.

```bash
python3 anchor_label.py --candidates cand_edge_type.jsonl --judge anchor \
    --double --run first_judge-2026-07-08          # ledger -> ops/spend.jsonl
```

## 6 · Sanity bounds — do NOT break these (ANNEX_B6 §4, README_harness §3)

These are already enforced in `judge_harness.py` / `first_judge.sh`; B6 must
leave them intact:

- **Calibration:** `T ∈ [0.3, 8]`, `q̂ ∈ (0, 0.9)`.
- **α:** T2 (`edge_type`) = 0.05 · T1 (`continues`) = 0.10 (`ALPHA_T2` /
  `ALPHA_T1` in `first_judge.sh`). Under `api-selfreport`, harden one notch
  (e.g. T2 → 0.03) — set in config, not code.
- **Calsets:** ≥ 300 rows/jtype preferred · 150 = floor with warning · < 150 =
  refuse to calibrate.
- **Anchor pilot:** 25 candidates, then project cost before the full run
  (`LIMIT_ET=350`, `LIMIT_CT=250`, `--double` ⇒ 2 calls/candidate,
  ~1.5–2.5 M input tokens for ~600 candidates). Set `max_usd_per_run` **above**
  that projection — the cap is a belt, the pilot is the estimate.

## 7 · vLLM runbook (B6-full) — pointer

Full local serving (target mode `vllm-local`, deterministic replay) is
specified in `ANNEX_B6_judge_infra.md §5`. Summary of the numbers:

- Qwen3-8B bf16 ≈ 16 GB weights + KV → fits a single 24 GB 3090 with
  `--gpu-memory-utilization 0.90 --max-model-len 8192`.
- AWQ 4-bit ≈ 6 GB → two judges co-resident (costs a recalibration: logprobs
  change ⇒ new `judge_id`, contract §4).
- `--enable-prefix-caching` is **mandatory** — echo scoring shares the prompt
  prefix across a candidate's 3–4 labels; that shared prefill is most of the
  latency.
- Compute the **real** `sha256` of the HF snapshot dir and put it in
  `judge_id` (`<model>@<hash8>#p1`) — that is what makes replay deterministic
  and passes the `vllm-local` weights-hash check.
- systemd: `vllm-qwen.service`, `Restart=on-failure`,
  `ExecStartPre=infra_check.py judge --judge qwen-a` as warm-up.

## 8 · Switchover policy (FR-5)

Start in B6-lite. Switch a judge to B6-full **per judge**, which mints a new
`judge_id` and therefore **forces recalibration** (contract §4). API cohorts
stay retractable like any other via the I4 envelope. The weekly B7 report
surfaces the current mode as standing debt so lite never silently becomes
permanent.

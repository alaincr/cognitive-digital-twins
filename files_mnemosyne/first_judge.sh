#!/usr/bin/env bash
# first_judge.sh — WP-0 staged runbook (SPEC-01). Idempotent via checkpoint
# markers; --plan prints the resolved plan; --from N re-enters at stage N.
#
# Usage:
#   EXPORT=~/roam-export.json ./first_judge.sh [--plan] [--from N] [--yes]
# Env (defaults):
#   EXPORT   (required) Roam JSON export
#   JUDGE    judge name in judges_config.yaml        (default: qwen-a)
#   ANCHOR   anchor name in judges_config.yaml       (default: anchor)
#   WORK     working dir                             (default: ops/first_judge)
#   ALPHA_T2 / ALPHA_T1                              (default: 0.05 / 0.10)
#   PILOT    anchor pilot batch size                 (default: 25)
#   LIMIT_ET / LIMIT_CT  anchor label caps           (default: 350 / 250)
set -euo pipefail

JUDGE="${JUDGE:-qwen-a}"; ANCHOR="${ANCHOR:-anchor}"
WORK="${WORK:-ops/first_judge}"; CAL="$WORK/calib"
ALPHA_T2="${ALPHA_T2:-0.05}"; ALPHA_T1="${ALPHA_T1:-0.10}"
PILOT="${PILOT:-25}"; LIMIT_ET="${LIMIT_ET:-350}"; LIMIT_CT="${LIMIT_CT:-250}"
PLAN=0; FROM=0; YES=0
for a in "$@"; do case "$a" in
  --plan) PLAN=1;; --yes) YES=1;; --from) :;; --from=*) FROM="${a#--from=}";;
  *) if [[ "$prev" == "--from" ]]; then FROM="$a"; fi;;
esac; prev="$a"; done

say()  { printf '\n\033[1m== stage %s · %s ==\033[0m\n' "$1" "$2"; }
mark() { touch "$WORK/.stage$1.done"; }
done_p(){ [[ -f "$WORK/.stage$1.done" && "$1" -lt "$FROM" || -f "$WORK/.stage$1.done" && "$FROM" == 0 ]]; }
run()  { if [[ $PLAN == 1 ]]; then printf '  PLAN: %s\n' "$*"; else eval "$@"; fi }
confirm(){ [[ $YES == 1 || $PLAN == 1 ]] && return 0
           read -rp "$1 [y/N] " r; [[ "$r" == y* || "$r" == Y* ]]; }

mkdir -p "$CAL"

# ---- stage 0 · preflight ----------------------------------------------------
if ! done_p 0; then say 0 "preflight"
  [[ -n "${EXPORT:-}" && -f "$EXPORT" ]] || { echo "EXPORT missing"; exit 2; }
  run "sha256sum '$EXPORT' | tee '$WORK/export.sha256'"
  run "python3 -m py_compile judge_harness.py anchor_label.py roam_harvest.py prefilter.py judge_metrics.py"
  run "python3 judge_harness.py self-test > /dev/null && echo '  harness self-test green'"
  run "python3 judge_metrics.py self-test > /dev/null && echo '  metrics self-test green'"
  run "python3 -c 'import yaml,sys; c=yaml.safe_load(open(\"judges_config.yaml\")); \
assert \"$JUDGE\" in c[\"judges\"] and \"$ANCHOR\" in c[\"judges\"], \"config missing judge/anchor\"; print(\"  config ok:\", c[\"judges\"][\"$JUDGE\"][\"judge_id\"])'"
  [[ $PLAN == 1 ]] || mark 0
fi

# ---- stage 1 · harvest --------------------------------------------------------
if ! done_p 1; then say 1 "harvest calibration candidates"
  run "python3 roam_harvest.py harvest --export '$EXPORT' --out-dir '$CAL' --max-per-type 400 --min-refs 8 --seed 0"
  run "python3 - <<'PY'
import json; s=json.load(open('$CAL/harvest_stats.json'))['counts']
print('  yields:', s)
for t,floor in [('edge_type',150),('continues',100)]:
    if s.get(t,0)<floor: print(f'  WARNING: {t} below floor {floor} — SPEC-01 §3 contingency (--min-refs 5)')
PY"
  [[ $PLAN == 1 ]] || mark 1
fi

# ---- stage 2 · anchor label (pilot → project cost → full) --------------------
if ! done_p 2; then say 2 "anchor labeling (pilot $PILOT, then full)"
  run "python3 anchor_label.py --candidates '$CAL/candidates_edge_type.jsonl' --judge '$ANCHOR' --double --limit $PILOT"
  echo "  Inspect pilot: consistency & flag rates above; projected full cost ≈ (LIMIT/$PILOT)× pilot spend."
  confirm "  Proceed with full labeling (edge_type=$LIMIT_ET, continues=$LIMIT_CT)?" || { echo "stopped before full spend"; exit 3; }
  run "python3 anchor_label.py --candidates '$CAL/candidates_edge_type.jsonl' --judge '$ANCHOR' --double --limit $LIMIT_ET"
  run "python3 anchor_label.py --candidates '$CAL/candidates_continues.jsonl'  --judge '$ANCHOR' --double --limit $LIMIT_CT"
  [[ $PLAN == 1 ]] || mark 2
fi

# ---- stage 3 · HUMAN GATE -----------------------------------------------------
if ! done_p 3; then say 3 "human review (cannot be automated)"
  echo "  Work $CAL/review_queue_*.md per SPEC-01 §5 (blind to anchor verdicts)."
  echo "  Transcribe to $WORK/review_resolved.jsonl:  {\"jtype\",\"fields\",\"gold\"} per line."
  confirm "  Review complete (or consciously skipped)?" || exit 3
  [[ $PLAN == 1 ]] || mark 3
fi

# ---- stage 4 · merge review ---------------------------------------------------
if ! done_p 4; then say 4 "merge human gold into calsets"
  run "python3 - <<'PY'
import json, pathlib
rp = pathlib.Path('$WORK/review_resolved.jsonl')
if not rp.exists(): print('  no review_resolved.jsonl — skipping'); raise SystemExit
by = {}
for l in rp.read_text().splitlines():
    if l.strip():
        r = json.loads(l); r.setdefault('provenance', {})['source']='human'
        by.setdefault(r['jtype'], []).append(r)
for jt, rows in by.items():
    p = pathlib.Path(f'$CAL/calset_{jt}.jsonl')
    with p.open('a', encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False)+'\n')
    print(f'  merged {len(rows)} human rows into {p.name}')
PY"
  [[ $PLAN == 1 ]] || mark 4
fi

# ---- stage 5 · freeze -----------------------------------------------------------
if ! done_p 5; then say 5 "freeze calsets"
  run "sha256sum '$CAL'/calset_*.jsonl | tee '$WORK/FROZEN.sha256'"
  [[ $PLAN == 1 ]] || mark 5
fi

# ---- stage 6 · calibrate --------------------------------------------------------
if ! done_p 6; then say 6 "calibrate (T2 alpha=$ALPHA_T2, T1 alpha=$ALPHA_T1)"
  run "python3 judge_harness.py calibrate --judge '$JUDGE' --jtype edge_type --calset '$CAL/calset_edge_type.jsonl' --alpha $ALPHA_T2"
  run "python3 judge_harness.py calibrate --judge '$JUDGE' --jtype continues --calset '$CAL/calset_continues.jsonl' --alpha $ALPHA_T1"
  run "python3 - <<'PY'
import json
c=json.load(open('calibration.json'))
for k,v in c.items():
    print(' ', k, v)
    assert 0.3<=v['T']<=8, f'T out of sanity bounds: {k}'
    assert 0<v['qhat']<0.9 or print(f'  WARNING q-hat near 1 for {k}: expect mass abstention')
PY"
  [[ $PLAN == 1 ]] || mark 6
fi

# ---- stage 7 · prefilter cold run ------------------------------------------------
if ! done_p 7; then say 7 "prefilter (cold start, raised budgets)"
  run "python3 prefilter.py run --export '$EXPORT' --state '$WORK/pf_state.json' --out '$WORK/live_candidates.jsonl' --min-refs 8 --budget edge_type=120 --budget continues=80"
  [[ $PLAN == 1 ]] || mark 7
fi

# ---- stage 8 · judge ---------------------------------------------------------------
if ! done_p 8; then say 8 "judge the live candidates"
  run "python3 judge_harness.py judge --judge '$JUDGE' --candidates '$WORK/live_candidates.jsonl' --outbox '$WORK/outbox.jsonl'"
  [[ $PLAN == 1 ]] || mark 8
fi

# ---- stage 9 · metrics --------------------------------------------------------------
if ! done_p 9; then say 9 "metrics report + decision gates"
  run "python3 judge_metrics.py report --outbox '$WORK/outbox.jsonl' --contexts '$WORK/contexts.jsonl' --calsets '$CAL'/calset_*.jsonl --out-prefix '$WORK/first_judge_report'"
  echo "  M0 deliverable: $WORK/first_judge_report.md"
  [[ $PLAN == 1 ]] || mark 9
fi

echo; echo "first_judge.sh complete (plan=$PLAN)."

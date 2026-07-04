#!/usr/bin/env bash
# cycle.sh — B4 nightly consolidation orchestrator (PRD B4 §FR-3, ANNEX §3).
# Ten stages, chained. Idempotent via per-cycle stage markers; a failed stage
# skips only its dependents (dependency graph below) and the cycle digest
# mentions it — the next cycle catches up (everything is idempotent + offsets).
#
# Usage:
#   ./cycle.sh [--plan] [--from N] [--yes]
# Env (defaults):
#   JUDGE     judge name in judges_config.yaml       (default: qwen-a)
#   OPS       runtime/state dir                       (default: ops)
#   STORE     durable dir (events.jsonl)              (default: store)
#   CONFIG    sync config                             (default: sync.yaml)
#   BUDGET    task_gen order budget                   (default: 5)
#
# The exchanged-file contract is prd/annexes/INTERFACES.md (normative). $C is
# this cycle's immutable artifact dir: ops/cycles/<ts>/.
#
# Dependency skip graph (stage <- {dependents}):
#   1 <- {2,3}   3 <- {4}   {2,4} <- {5}   5 <- {6,7,8}   {6,7,8} <- {9}
#   10 always runs (the digest/report must land even on partial cycles).
set -uo pipefail

JUDGE="${JUDGE:-qwen-a}"
OPS="${OPS:-ops}"
STORE="${STORE:-store}"
CONFIG="${CONFIG:-sync.yaml}"
BUDGET="${BUDGET:-5}"

PLAN=0; FROM=0; YES=0; prev=""
for a in "$@"; do case "$a" in
  --plan) PLAN=1;; --yes) YES=1;; --from) :;; --from=*) FROM="${a#--from=}";;
  *) if [[ "$prev" == "--from" ]]; then FROM="$a"; fi;;
esac; prev="$a"; done

TS="$(date -u +%Y%m%dT%H%M%SZ)"
C="$OPS/cycles/$TS"
mkdir -p "$C" "$OPS" "$STORE" "$OPS/logs"

say()  { printf '\n\033[1m== stage %s · %s ==\033[0m\n' "$1" "$2"; }
mark() { touch "$C/.stage$1.done"; }
skip() { touch "$C/.stage$1.skipped"; }
is_ok(){ [[ -f "$C/.stage$1.done" ]]; }
run()  { if [[ $PLAN == 1 ]]; then printf '  PLAN: %s\n' "$*"; else eval "$@"; fi }
# A stage runs when: not already done AND its start index <= its number.
todo() { [[ ! -f "$C/.stage$1.done" && "$1" -ge "$FROM" ]]; }
require(){ command -v "$1" >/dev/null 2>&1 || { echo "MISSING binary: $1"; exit 2; }; }

# a stage is blocked if any of its named dependency stages was skipped/failed
blocked() { for dep in "$@"; do [[ -f "$C/.stage$dep.skipped" ]] && return 0; done; return 1; }

# ---- preflight --------------------------------------------------------------
say 0 "preflight (require each binary)"
require python3
require clojure
for f in roam_sync.py task_harvest.py prefilter.py judge_harness.py belief.py \
         shacl_lint.py task_gen.py roam_writeback.py judge_metrics.py cycle_tools.py; do
  [[ -f "$f" ]] || echo "  NOTE: $f not present (stage will fail-skip if run)"
done
run "python3 cycle_tools.py self-test >/dev/null && echo '  cycle_tools self-test green'"
echo "  cycle dir: $C"

# ---- stage 1 · roam sync pull ----------------------------------------------
if todo 1; then say 1 "roam_sync pull"
  if run "python3 roam_sync.py pull --config '$CONFIG'"; then mark 1; else skip 1; fi
fi

# ---- stage 2 · task_harvest (human tasks) ; depends on 1 -------------------
# The harvester APPENDS straight into $OPS/outbox_human.jsonl: the consolidator
# tails that file with a persistent byte offset, so it must be append-only
# (an overwrite would desync the offset and silently drop responses). The
# harvest ledger makes appends idempotent; $C gets a per-cycle archive copy.
if todo 2; then say 2 "task_harvest -> outbox_human.jsonl (append)"
  if blocked 1; then echo "  skipped (stage 1 failed)"; skip 2
  elif run "python3 task_harvest.py harvest --snapshot sync/snapshots/latest.json --out '$OPS/outbox_human.jsonl' --ledger '$OPS/harvest_ledger.jsonl' --taskgen-ledger '$OPS/taskgen_ledger.jsonl'"; then
    run "cp -f '$OPS/outbox_human.jsonl' '$C/outbox_human.jsonl' 2>/dev/null || true"
    # anti-fatigue: persist the budget factor task_gen reads at stage 8 (FR-4)
    run "python3 task_harvest.py stats --window 7d --ledger '$OPS/harvest_ledger.jsonl' --taskgen-ledger '$OPS/taskgen_ledger.jsonl' --apply-state '$OPS/taskgen_state.json' >/dev/null || true"
    mark 2
  else skip 2; fi
fi

# ---- stage 3 · prefilter ; depends on 1 ------------------------------------
if todo 3; then say 3 "prefilter -> live_candidates.jsonl"
  if blocked 1; then echo "  skipped (stage 1 failed)"; skip 3
  elif run "python3 prefilter.py run --export sync/snapshots/latest.json --delta \$(ls -t sync/deltas/*.delta.jsonl 2>/dev/null | head -1) --state '$OPS/pf_state.json' --out '$C/live_candidates.jsonl'"; then mark 3
  else skip 3; fi
fi

# ---- stage 4 · judge ; depends on 3 ----------------------------------------
if todo 4; then say 4 "judge_harness -> outbox.jsonl"
  if blocked 3; then echo "  skipped (stage 3 failed)"; skip 4
  elif run "python3 judge_harness.py judge --judge '$JUDGE' --candidates '$C/live_candidates.jsonl' --outbox '$OPS/outbox.jsonl'"; then mark 4
  else skip 4; fi
fi

# ---- stage 5 · CONSOLIDATE (B4, the single writer) ; depends on 2,4 --------
if todo 5; then say 5 "consolidate --once (promote, export, orders, causes)"
  if blocked 2 4; then echo "  skipped (stage 2 or 4 failed)"; skip 5
  elif run "clojure -M:consolidate --once --dir '$OPS' --cycle '$C'"; then mark 5
  else skip 5; fi
fi

# ---- stage 6 · belief + stance-diff ; depends on 5 -------------------------
if todo 6; then say 6 "belief.py compute + stance-diff"
  if blocked 5; then echo "  skipped (stage 5 failed)"; skip 6
  elif run "python3 belief.py compute --edges '$OPS/edges.jsonl' --out '$C/stances.jsonl'" \
       && run "python3 cycle_tools.py stance-diff --cur '$C/stances.jsonl' --prev '$OPS/stances_prev.jsonl' --out '$C/stance_diff.jsonl' --rotate"; then mark 6
  else skip 6; fi
fi

# ---- stage 7 · export JSON-LD + SHACL lint ; depends on 5 ------------------
if todo 7; then say 7 "export-jsonld + shacl_lint"
  if blocked 5; then echo "  skipped (stage 5 failed)"; skip 7
  elif run "clojure -M:consolidate --export-jsonld '$C/graph.jsonld'" \
       && run "python3 shacl_lint.py lint --data '$C/graph.jsonld' --out '$C/lint.json'"; then mark 7
  else skip 7; fi
fi

# ---- stage 8 · task_gen (append task orders) ; depends on 5 ----------------
# --stances gates contradiction tasks on claims that are still IN (stage 6
# artefact; task_gen degrades gracefully if stage 6 was skipped). --ledger
# records the route payload task_harvest joins on next cycle (B3<->B4 seam);
# --state applies the anti-fatigue budget factor persisted at stage 2.
if todo 8; then say 8 "task_gen -> append writeback_orders"
  if blocked 5; then echo "  skipped (stage 5 failed)"; skip 8
  elif run "python3 task_gen.py generate --causes '$C/task_causes.jsonl' --edges '$OPS/edges.jsonl' --stances '$C/stances.jsonl' --review-queues '$OPS'/first_judge/review_queue_*.md --out-append '$C/writeback_orders.jsonl' --budget '$BUDGET' --state '$OPS/taskgen_state.json' --ledger '$OPS/taskgen_ledger.jsonl' --cycle '$TS'"; then mark 8
  else skip 8; fi
fi

# ---- stage 9 · roam write-back ; depends on 6,7,8 --------------------------
if todo 9; then say 9 "roam_writeback apply"
  if blocked 6 7 8; then echo "  skipped (a prerequisite failed)"; skip 9
  elif run "python3 roam_writeback.py apply --orders '$C/writeback_orders.jsonl'"; then mark 9
  else skip 9; fi
fi

# ---- stage 10 · metrics report (ALWAYS runs) -------------------------------
if todo 10; then say 10 "judge_metrics report (always)"
  run "python3 judge_metrics.py report --outbox '$OPS/outbox.jsonl' --contexts '$OPS/contexts.jsonl' --out-prefix '$C/report' || true"
  # digest: which stages skipped this cycle
  { echo "cycle $TS"; for s in $(seq 1 10); do
      if [[ -f "$C/.stage$s.done" ]]; then echo "  stage $s: ok";
      elif [[ -f "$C/.stage$s.skipped" ]]; then echo "  stage $s: SKIPPED"; fi
    done; } | tee "$C/digest.txt"
  mark 10
fi

echo; echo "cycle.sh complete (plan=$PLAN, cycle=$C)."

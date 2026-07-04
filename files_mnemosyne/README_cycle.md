# README_cycle — B4 durable consolidator + nightly cycle

Brick **B4** (gap G4). Makes the consolidator (`src/mnemosyne/ingest.clj`) run
**durably** — its DataScript projection survives process restarts because the
event journal on disk is the source of truth — and adds `cycle.sh`, the ten-stage
nightly orchestrator that chains every other brick into one closed loop.

> **Verification status.** The Clojure substrate is **reviewed-not-executed** in
> the authoring sandbox (no JVM/Clojars here — SPEC-00 §3.1). The executable gate
> is `.github/workflows/clojure.yml` (`clojure -M:test`), which folds the
> committed golden fixtures and asserts the crash / idempotence / state-hash
> invariants on `ubuntu-latest`. The Python stage tool (`cycle_tools.py`) is
> fully self-tested locally (`python3 cycle_tools.py self-test`).

---

## The ten stages (`cycle.sh`)

Each cycle gets an immutable artifact dir `$C = ops/cycles/<ts>/`. Stage markers
(`$C/.stageN.done` / `.stageN.skipped`) make the run idempotent and re-enterable.

| # | Command | Produces |
|---|---|---|
| 1 | `roam_sync.py pull --config sync.yaml` | `sync/snapshots/latest.json`, deltas |
| 2 | `task_harvest.py harvest … --out $C/outbox_human.jsonl` | `ops/outbox_human.jsonl` |
| 3 | `prefilter.py run --delta … --out $C/live_candidates.jsonl` | live candidates |
| 4 | `judge_harness.py judge … --outbox ops/outbox.jsonl` | `ops/outbox.jsonl` |
| 5 | `clojure -M:consolidate --once --dir ops --cycle $C` | `store/events.jsonl`, `ops/edges.jsonl`, `ops/accepted.jsonl`, `$C/task_causes.jsonl`, `$C/writeback_orders.jsonl` |
| 6 | `belief.py compute --edges ops/edges.jsonl --out $C/stances.jsonl` + `cycle_tools.py stance-diff … --rotate` | `$C/stances.jsonl`, `$C/stance_diff.jsonl` |
| 7 | `clojure -M:consolidate --export-jsonld $C/graph.jsonld` + `shacl_lint.py lint` | `$C/graph.jsonld`, `$C/lint.json` |
| 8 | `task_gen.py generate --causes $C/task_causes.jsonl --out-append $C/writeback_orders.jsonl` | task orders appended |
| 9 | `roam_writeback.py apply --orders $C/writeback_orders.jsonl` | Roam `M/*` pages |
| 10 | `judge_metrics.py report …` + cycle digest | `$C/report.*`, `$C/digest.txt` |

**Dependency skip graph** (a failed stage skips only its dependents; stage 10
always runs so the digest lands): `1←{2,3}`, `3←{4}`, `{2,4}←{5}`,
`5←{6,7,8}`, `{6,7,8}←{9}`.

Flags (modelled on `first_judge.sh`): `--plan` prints the resolved plan without
running; `--from N` re-enters at stage N; `--yes` skips confirmations. Preflight
`require`s each binary.

**The exchanged-file contract is `prd/annexes/INTERFACES.md` (normative).** Any
schema change is a PR against that table plus both sides' self-tests.

---

## Durability model (PRD B4 §FR-1, ANNEX §2.2)

`now = fold(store/events.jsonl)`. The in-memory DataScript db is never the
source of truth; it is a deterministic fold of the journal.

- **Write-ahead.** `core/append!` calls the `*wal-fn*` hook (installed by
  `ingest/with-wal`) to journal each fully-stamped event to
  `store/events.jsonl` **before** the in-memory `swap!`. A crash between the two
  loses nothing — boot re-folds the journal.
- **Canonical JSON row.** Sorted keys (all the way down), compact separators,
  UTF-8 **NFC** strings (`durable/canonical-json`). Tested on accented French
  (`café`, `élève`) — NFC and NFD forms hash equal.
- **Content addressing.** `event_id = sha256(canonical-JSON of the row without
  event_id)`. A full replay of the same outbox yields the same ids → idempotence
  (M2). `seq` is strictly increasing (the consolidator owns the counter).
- **`tx_data` is a canonical EDN string.** The DataScript payload holds keywords,
  lookup-refs (`[:node/id "x"]`) and `[:db/add …]` vectors that have no lossless
  JSON encoding; storing `pr-str` of it makes the refold byte-exact while the
  outer row stays clean sorted-key JSON for `eval`/`audit`.
- **State hash.** `durable/state-hash` = sha256 of the sorted EAV datom
  serialization (entity identity resolved to stable ids, so it is invariant to
  DataScript's internal eid assignment). Journalled every 100 events and at
  end-of-cycle as a `state.hash` marker row (skipped by the fold).
- **Boot check.** After fold, the recomputed hash is compared to the last
  journalled marker; divergence is a **loud fatal error** (FR-1). A single
  truncated final line (crash mid-write) is tolerated and dropped with a warning
  (PRD §6 case 4); any earlier corruption is fatal.
- **`log.edn` is gone** (ADR §5 Q2): one source of truth, less code.
- **Clock seam.** `core/*now-fn*` is redefinable; the tests pin it so `ts` (and
  therefore every content-address digest) is deterministic.

`--once` runs exactly one cycle (boot → ingest outboxes + human outbox →
consolidate → batch behaviors → belief recompute → exports → orders/causes →
end-of-cycle hash). `--crash-after-wal N` is a test hook that exits after the
Nth write-ahead but before the in-memory swap.

### Restoration after corruption

If boot aborts with `refold state-hash mismatch` or `corrupt journal line (not
the last)`: the journal has an internal inconsistency. Recover by inspecting
`store/events.jsonl`, truncating back to the last good `state.hash` marker (its
`seq` and `state_hash` bound a known-good prefix), and re-running the cycle —
everything downstream is idempotent + offset-guarded, so the cycle catches up.

---

## Which exporter feeds which SHACL shape (CROSSWALK)

Two exporters can produce the linter's JSON-LD. The columns are normative.

| Shape | Class | Exporter |
|---|---|---|
| S1 `MissingLegalBasis` | `ProcessingActivity` | `shacl_lint.py export --roam` (Roam view) **or** consolidator |
| S2 `UnsupportedClaim` | `Claim`, `DiscourseEdge` | `shacl_lint.py export --roam` **or** consolidator |
| S3 `OrphanPermanentNote` | `PermanentNote` (+ `continues`/`trainHead`) | **consolidator only** (promoted strata) |
| S4 `RegisterCap` | `RegisterKeyword` | consolidator |
| S5 `JudgmentEnvelope` | `Judgment` | **consolidator only** (judgments) |
| S6 `LiteratureStanceLeak` | `Proposition`, `Stance` | **consolidator only** (stances) |
| S7 `StaleWithoutTask` | `StaleDerived`, `Task` | **consolidator only** (stale-marks) |
| S8 `FaithfulGate` | `PermanentNote` (`faithful`) | consolidator |

`clojure -M:consolidate --export-jsonld $C/graph.jsonld` materializes all of the
above from the promoted facts, in EXPANDED JSON-LD (ns `https://mnemosyne.dev/ns#`,
focusNode `urn:mnemo:node:<uid>`) matching the `sN_ok.jsonld` fixtures. The Roam
exporter remains a fallback for S1/S2 only; it cannot see promoted strata,
judgments or stances.

---

## Scheduling (launchd, macOS)

Use `com.mnemosyne.cycle.plist` — `StartCalendarInterval` at 02:00,
`StandardErrorPath` under `ops/logs/`.

```sh
# edit the two absolute paths inside the plist first
cp com.mnemosyne.cycle.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.mnemosyne.cycle.plist
```

**Do not use cron on macOS** — cron does not wake a sleeping Mac, so a laptop
asleep at 02:00 misses the run. launchd catches up at next wake. If the machine
must stay awake, keep it plugged in with *Prevent automatic sleeping*, or wrap
the command in `caffeinate -s` (already the default in the plist). On Linux, use
a systemd timer with the same 02:00 `OnCalendar`.

---

## Tests (`clojure -M:test`, CI)

`src/mnemosyne/test_runner.clj` runs against `fixtures/consolidator/`:

- **canonical-json / NFC** — sorted-key compact output; NFC≡NFD French hashes.
- **unknown jtype** → one `judgment.quarantined` event, cycle continues (§6).
- **idempotent replay** — re-ingesting the same outbox adds no new judgments.
- **crash recovery** — write-ahead then drop memory; refold is stable, no dup.
- **3-cycle replay → state-hash (M1)** — live db hash == refold-from-scratch hash.
- **golden replay** — the event-TYPE sequence (`events.expected.jsonl`), the
  edges (`edges.expected.jsonl`, full normalized bytes) and the writeback orders
  (`orders.expected.jsonl`, sha256 keys normalized to `<HASH>`) match committed
  goldens. Set `MNEMO_BLESS=1` to (re)generate goldens after an intended change.

Local Python gate (runs here, no JVM needed):

```sh
python3 -m py_compile cycle_tools.py
python3 cycle_tools.py self-test
bash -n cycle.sh
```

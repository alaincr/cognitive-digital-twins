# Roam sync — the acquisition + snapshot + diff layer (brick B1)

`roam_sync.py` closes gap **G1** of `prd/00_gap_analysis.md`: the pipeline had
no automated way to acquire the Roam graph (an export dropped by hand) and no
edit history. B1 fixes both — it acquires the graph on a cadence **and** turns
"an export carries no history" into a non-problem by keeping dated snapshots
and diffing them block-by-block into a delta stream the prefilter and judges
consume.

```
Roam ──► roam_sync.py {pull | ingest-drop}
             │  validate (FR-3) → snapshot (gzip+sha256) → diff vs latest
             ▼
   sync/snapshots/<ts>.json.gz   sync/deltas/<ts>.delta.jsonl   sync/sync_state.json
             │                             │
   roam_harvest.py (latest.json)   prefilter.py --delta
```

Two acquisition modes, **one** downstream contract (the normalized Roam
"Export All" JSON that `roam_harvest.py::Graph.parse` already consumes). The
rest of the pipeline cannot tell which mode produced a snapshot.

---

## Quick start — drop-folder mode first (no API needed)

The drop-folder path is a **first-class v0 deliverable**, not a fallback of
last resort: any Roam backend-API outage is compensated by a manual export
with nothing else changing.

1. In Roam: `⋯ → Export All → JSON` (the download is a `.zip`; you can drop it
   as-is — `roam_sync` unzips and picks the first `.json` member).
2. Drop it in the watched folder and ingest:

```bash
mkdir -p sync/drops
mv ~/Downloads/roam-export-*.zip sync/drops/     # or an unzipped .json
python3 roam_sync.py ingest-drop --dir sync/drops
```

This validates the export, writes an immutable gzipped snapshot, diffs it
against the previous `latest.json`, writes the delta, updates
`sync/sync_state.json`, and archives the source into `sync/drops/processed/`.
The **first** run has no previous snapshot, so the delta is an
`initial-import` header followed by every block as `added` (see below).

3. Feed the prefilter from the delta:

```bash
python3 prefilter.py run --export sync/snapshots/latest.json \
    --delta sync/deltas/<ts>.delta.jsonl \
    --state ops/prefilter_state.json --out ops/live_candidates.jsonl
```

`--delta` wins when provided; the `edit-time` watermark stays as the fallback.
On an `initial-import` delta the prefilter automatically falls back to
watermark mode (so the first cycle does not treat the whole graph as dirty).

---

## API mode (`pull`)

Automated acquisition via the Roam **backend API** (`/api/graph/<graph>/{q,pull}`).

1. Generate a **read-only** graph API token in Roam's graph settings (a token
   distinct from B2's edit token — B1 only reads).
2. Provide it out-of-band (never in a config file, never logged):

```bash
export ROAM_API_TOKEN="roam-graph-token-…"      # or:  --token-file secrets/roam.token
```

3. Minimal config (`sync.yaml`, a flat `key: value` subset — JSON also
   accepted; `token` in the file is **ignored** by design):

```yaml
graph: my-graph-name
sync_dir: sync
rate_delay: 1.0        # seconds between API requests (rate-limit friendly)
```

4. Pull:

```bash
python3 roam_sync.py pull --config sync.yaml            # nightly
python3 roam_sync.py pull --config sync.yaml --dry-run  # no network, prints a no-op
python3 roam_sync.py pull --config sync.yaml --force    # override the truncation guard
```

Notes on the backend API (verify against the official developer docs at pull
time — the API is young):

- **307/308 redirects to a peer** are replayed explicitly (`urllib` will not
  resubmit a POST body across a redirect); bounded to 3 hops.
- **429 / 5xx** get exponential backoff (base 2 s, cap 60 s), 3 retries.
- Fetch is two-step: `q` for `(uid, title)` per page, then a recursive `pull`
  per page; children are re-sorted by `:block/order` and the `:block/*` keys
  are normalized to the export shape.
- A pull is committed **only if complete**: a page that still fails after
  retries aborts the commit (the previous snapshot is untouched); no partial
  snapshot is ever written.

---

## Other subcommands

```bash
python3 roam_sync.py diff --old <snapA.json[.gz]> --new <snapB.json[.gz]> [--out f.jsonl]
python3 roam_sync.py diff --new <snap.json>          # omit --old → initial-import
python3 roam_sync.py status [--dir sync]             # last snapshot, age, volumetry
python3 roam_sync.py self-test                       # zero network, 30 assertions
```

`stdout` is machine output (JSON); `stderr` carries one-line `[roam_sync]`
logs. A validation/acquisition failure exits `2` with a single-line log and
leaves the previous snapshot in place.

---

## File contract (the rows B1 produces)

These match `prd/annexes/INTERFACES.md` — the normative inter-brick table.

| File | Schema (key fields) |
|---|---|
| `sync/snapshots/<ts>.json.gz`, `snapshots/latest.json` | Roam "Export All" JSON: `[{title, edit-time, children:[{uid, string, create-time, edit-time, children}]}]`. `latest.json` is uncompressed; `roam_harvest.py` reads it. Gzip is written with `mtime=0` → byte-deterministic. |
| `sync/deltas/<ts>.delta.jsonl` | one line per changed block: `{op: added\|edited\|removed\|moved, uid, page, parent, before_hash?, after_hash?, string?, edit_time?, snapshot}`. First run: a `{"meta":"initial-import", "snapshot", "blocks"}` header on line 1, then every block `added` with `"initial": true`. |
| `sync/sync_state.json` | `{last_snapshot, last_sha256, block_count, page_count, mode, last_delta, history[]}` — `history` bounded to the last 90 entries. |

### Delta classification (normative, ANNEX B1 §3.2)

- key is `uid`; present in new only → `added`, old only → `removed`.
- string changed, parent & page unchanged → `edited`.
- parent OR page changed, string unchanged → `moved` (never removed+added).
- both changed → **two lines**: one `moved`, one `edited` (each consumer
  filters on a single op).
- a uid reused after deletion is `removed` then `added` across cycles, never
  `edited`.
- hashes: `sha256("nfc:" + NFC(string))`, prefixed `sha256:`.
- the file is sorted by `(op, uid)` → **byte-identical re-runs** (determinism
  NFR); two `diff` runs on the same snapshots produce the same bytes.

Strings are NFC-normalized at the store edge (the Clojure consolidator expects
NFC; do not send it NFD).

---

## The `M/*` exclusion (owned here to avoid a merge with B7)

Pages whose title starts with `M/` are the **evaluation namespace** (seeded
probes). They must never be mined as candidates. This is enforced in the two
files B1 owns:

- `roam_harvest.py::is_eval_page` filters `content_blocks` and every harvester
  (including co-reference neighbors). Self-test: an `M/Eval/Seeded` fixture
  page yields **zero** candidates.
- `prefilter.py::_is_eval_page` filters dirty/new block selection, delta
  resolution, and page-scan flows. Self-test asserts the same, in both delta
  mode and watermark mode.

---

## Cron / launchd (nightly cadence)

Snapshot ids are minute-resolution UTC (`2026-07-04T0200Z`); a nightly job
never collides. Example launchd agent on the owner's Mac (consistent with B4):

```xml
<!-- ~/Library/LaunchAgents/dev.mnemosyne.roamsync.plist -->
<dict>
  <key>Label</key><string>dev.mnemosyne.roamsync</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/path/to/files_mnemosyne/roam_sync.py</string>
    <string>pull</string>
    <string>--config</string><string>/path/to/sync.yaml</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict><key>ROAM_API_TOKEN</key><string>roam-graph-token-…</string></dict>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>2</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardErrorPath</key><string>/tmp/roamsync.log</string>
</dict>
```

Cron equivalent (drop-folder mode as the API's standing plan B):

```cron
0 2 * * *  cd /path/to/files_mnemosyne && \
           ROAM_API_TOKEN=… python3 roam_sync.py pull --config sync.yaml \
           || python3 roam_sync.py ingest-drop --dir sync/drops
```

Success criterion (PRD M1): 7 consecutive nightly acquisitions with no
unrecovered failure — validated in operation, not in CI.

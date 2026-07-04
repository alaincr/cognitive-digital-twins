# INTERFACES — contrats de fichiers inter-briques (normatif)

**Statut :** ce tableau est LE contrat entre les 10 étapes du cycle
(PRD B4 §7 : « le tableau des fichiers du README est normatif ; tout
changement = PR sur ce tableau »). Chaque brique valide ses entrées contre
ce document dans son self-test quand c'est possible.

Conventions transverses (héritées du code existant, vérifiées) :
- JSONL : un objet JSON par ligne, UTF-8 **NFC**, clés snake_case côté
  Python (la normalisation hyphens/underscores est confinée à
  `ingest.clj::py->clj-type`).
- Hashes : `sha256`, hex, préfixés `sha256:` dans les nouveaux fichiers
  (les fichiers existants — `context_hash`, `content_hash` — restent hex nu).
- Timestamps : `ts` ISO-8601 UTC dans les nouveaux fichiers ; les
  `edit-time`/`create-time` Roam restent en millisecondes epoch.
- stdout = machine, stderr = logs une-ligne (tous modules).

## 1 · Flux du cycle nocturne

```
   B1 sync          existant           existant            B4 (JVM)
snapshot+delta ──► prefilter ──► judge_harness ──► ingest/consolidate ──► belief ──► lint
      │                                                    │    │
      ▼                                                    │    ▼
 task_harvest (B3) ──► outbox_human ──────────────────────►│  task_causes ──► task_gen (B3)
                                                           ▼                      │
                                              writeback_orders ◄──────────────────┘
                                                           │
                                                           ▼
                                                   roam_writeback (B2) ──► Roam M/*
```

## 2 · Le tableau (une ligne par fichier échangé)

| Fichier | Producteur | Consommateur(s) | Schéma (champs clés) | Statut |
|---|---|---|---|---|
| `sync/snapshots/<ts>.json.gz`, `latest.json` | B1 | prefilter, roam_harvest, task_harvest, embed, eval | format « Export All » Roam : `[{title, children:[{uid, string, create-time, edit-time, children}]}]` | nouveau (B1) |
| `sync/deltas/<ts>.delta.jsonl` | B1 | prefilter `--delta`, embed_index | `{op: added\|edited\|removed\|moved, uid, page, parent, before_hash?, after_hash?, string?, edit_time, snapshot}` ; header `{"meta":"initial-import"}` au 1er run | nouveau (B1) |
| `sync/sync_state.json` | B1 | B1, eval | `{last_snapshot, last_sha256, block_count, mode, history[]}` | nouveau (B1) |
| `ops/live_candidates.jsonl` | prefilter | judge_harness | `{jtype, subjects[], fields{}, meta{}}` — fields par jtype = `judge_prompts.REQUIRED_FIELDS` (+ `continues`/`permanent_worthy` via `zettel_prompts.register()`) | existant |
| `ops/outbox.jsonl` | judge_harness | ingest.clj (offset `.offset`) | `{event: judgment.emitted\|judgment.abstained, jtype, subjects[], judge_id, cal_version, context_hash, ts, caused_by, label?, confidence?, self_reported, prediction_set?, order_disagreement?}` | existant |
| `ops/contexts.jsonl` | judge_harness | judge_metrics, anchor-sample | `{context_hash, jtype, fields{}}` | existant |
| `ops/anchor_outbox.jsonl` | judge_harness anchor-sample | ingest.clj | même schéma que outbox + `event: anchor.sampled` | existant |
| `ops/outbox_human.jsonl` | task_harvest (B3) — **append-only** (le consolidateur le taille avec un offset persistant ; jamais d'écrasement — cycle.sh fait `--out $OPS/…` direct, archive `cp` vers `$C`) | ingest.clj (nouveau reader, même mécanique offset) | `{event: human.response[.amended\|.ambiguous], task_id, task_type, response_text?, choice?, response_hash, answered_ts, route:{…}, provenance:{source:"human"}}` — `route` = charge de routage jointe depuis `taskgen_ledger.jsonl` par `task_id` (review: `{jtype, fields, context_hash}` ; triage: `{uid}` ; bridge: `{a, b}` ; fallback `refs::` pour triage/bridge) ; sans `route` exploitable, ingest journalise `human.response.unroutable` (aucun fait de domaine) | nouveau (B3) |
| `store/events.jsonl` | ingest.clj (write-ahead) | boot fold, eval, audit | `{event_id: "sha256:…", seq, type, actor, caused_by, ts, tx_data[]}` ; `state_hash` journalisé /100 événements | nouveau (B4) |
| `ops/accepted.jsonl` | ingest.clj | anchor-sample | `{judgment_id, jtype, label, context_hash, judge_id, judge_family}` | existant |
| `ops/edges.jsonl` | ingest.clj | belief.py, eval E2/E3 | `{edge_id: "from->to#type", edge_type: supports\|opposes\|refines, from, to}` | existant |
| `ops/escalations.jsonl` | ingest.clj | revue ancre/humain | `{jtype, subject_key, subjects, context_hash}` | existant |
| `$C/task_causes.jsonl` | ingest.clj | task_gen (B3) | `{cause: contradiction\|triage.due\|bridge, …, event_id}` (annexe B4 §2.4) — `event_id` toujours unique par cause (content-addressed `sha256("cause:<type>\|…")` en fallback, jamais une constante — I4) ; task_gen filtre les `contradiction` sur `stances.jsonl` (claim `label == in`) | nouveau (B4) |
| `ops/taskgen_ledger.jsonl` | task_gen (B3) | task_harvest (join `route` par task_id), eval E5 | `{task_id, task_type, ctx_cause, route{…}, generated_ts, cycle}` | nouveau (B3) |
| `ops/taskgen_state.json` | task_harvest `stats --apply-state` (B3) | task_gen `generate --state` | `{budget_factor: 1.0\|0.5, since, ok_since}` — machine anti-fatigue FR-4 (baisse <50 %, dwell 7 j avant restauration) | nouveau (B3) |
| `$C/elaboration_coverage.jsonl` | ingest.clj (run-once) | eval E5 (`--elaboration`) | `{train, human, total, coverage}` — une ligne par train (annexe B7 §1) | nouveau (B4) |
| `$C/stances.jsonl`, `ops/stances_prev.jsonl` | belief.py | eval, stance-diff | objet stance : `{node, label: in\|out\|undec, status: accepted-supported\|accepted-undisputed\|rejected\|undecided, support{}, attackers{}, qualifiers[], basis_edges[], computed_at}` | existant |
| `$C/stance_diff.jsonl` | cycle_tools (B4 ét. 6) | writeback orders, eval E4 | `{node, old_status, new_status, caused_by}` — v0 : `caused_by` = node id ; E4 récupère le churn en croisant `node` avec les événements de rétractation de `store/events.jsonl` (`eval_harness report --events`) | nouveau (B4) |
| `$C/graph.jsonld` | ingest.clj `export-jsonld` | shacl_lint | JSON-LD, ns `https://mnemosyne.dev/ns#`, focus `urn:mnemo:node:<uid>`, classes du CROSSWALK (S1–S8) | nouveau (B4) |
| `$C/lint.json` | shacl_lint | writeback orders, eval E2 | `{conforms, n_violations, n_warnings, results:[{focusNode, shape, severity, message}]}` | existant |
| `$C/writeback_orders.jsonl` | ingest.clj + task_gen (append) | roam_writeback (B2) | `{kind: judgment\|flag\|stance\|task\|digest\|seed, idempotency_key, target:{page, under}, content:{template, fields{}}, caused_by}` | nouveau (B4/B3) |
| `ops/writeback_ledger.jsonl` | roam_writeback | roam_writeback (reprise), eval | `{key, kind, block_uid, page, ts, cycle, status: written\|failed\|verified}` | nouveau (B2) |
| `sim/sim_pairs.jsonl` | embed_index (B5) | zettel harvest, dedup (futur) | `{a, b, score, model_rev, cycle}`, `a<b` | nouveau (B5) |
| `sim/continues_candidates.jsonl` | embed_index | prefilter (fusion budget) | candidate row `continues` complet (annexe B5 §1.2) | nouveau (B5) |
| `sim/bridge_seeds.jsonl` | embed_index | ingest.clj `select-bridges` | `{a, b, score, model_rev, cycle}`, pages ≠ | nouveau (B5) |
| `ops/spend.jsonl` | anchor_label / harness (B6) | eval, opérateur | `{run, judge, calls, tokens_in, tokens_out, usd, ts}` | nouveau (B6) |
| `calib/calset_<jtype>.jsonl` | anchor_label + merge review | calibrate, distillation (futur) | `{jtype, fields{}, gold, basis, difficulty, provenance:{anchor_judge_id\|source:"human", context_hash, ts, double_consistent}}` — **gelé** après FROZEN.sha256 | existant |
| `review_resolved.jsonl` | humain / task_harvest via B4 | merge stage 4 (first_judge.sh) | `{jtype, fields{}, gold}` | existant |
| `eval/weekly_report.{md,json}`, `eval/history/` | eval_harness (B7) | propriétaire, digest B2 | annexe B7 §4 | nouveau (B7) |

## 3 · Répertoires

```
ops/                 état runtime (outboxes, offsets, ledgers, pf_state, spend)
ops/cycles/<ts>/     $C : artefacts d'UN cycle (immuables une fois le cycle clos)
store/               events.jsonl, embeddings.db — l'état durable
sync/                snapshots, deltas, drops/
calib/               calsets gelés + FROZEN.sha256
fixtures/            fixtures self-tests, par brique
eval/                rapports hebdo + history
```

## 4 · Règles de changement

1. Tout changement de schéma ici = PR modifiant CE fichier + les self-tests
   des deux côtés du contrat, dans le même commit.
2. Un champ s'ajoute librement (consommateurs tolérants aux clés inconnues
   — à asserter dans les self-tests) ; un champ ne se renomme ni ne se
   supprime sans bump de version du fichier concerné.
3. Les fichiers `existant` ne changent pas de schéma pendant la boucle
   réduite (ils sont la partie prouvée du système).

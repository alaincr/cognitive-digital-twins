# Annexe technique B4 — consolidateur JVM + `cycle.sh`

**Complète :** `PRD_B4_consolidator_cycle.md`. Le PRD prime en cas de conflit.

---

## 1 · État exact du Clojure (vérifié fichier par fichier)

Bonne nouvelle : **plus de code existe que le PRD ne le laisse craindre.**

| Fichier | Ce qui existe déjà | Ce qui manque |
|---|---|---|
| `ingest.clj` | `-main` (l. ~333), `run-service!` (boucle dir/interval/cycles), tail avec offsets persistants (`<fichier>.offset`, entier d'octets, écrit après chaque lecture), dédup `(judge-id × context_hash × label)`, `consolidate!`, `export-accepted!`, `export-edges!`, normalisation `py->clj-type`/`clj->py-type`, snapshot `log.edn` (pr-str) | mode `--once` (la boucle existe, le one-shot par cycle est à exposer) ; `writeback_orders.jsonl` ; routage humain ; export JSON-LD |
| `mnemosyne.clj` | schéma DataScript, `append!` (event `evt-NNNN`, `:event/tx-data`), `project` (fold), `fork`, `frame`, `run-to-fixpoint`, helpers `why/frontier/unresolved/violations` | rien de bloquant |
| `judges.clj` | `emit-judgment!`/`emit-abstention!`, `promotable?` (T0/T1 single, T2 k-familles), `promote!`, `cohort`, `retract-cohort!`, `quarantine-behavior`, tiers stakes | rien de bloquant |
| `zettel.clj` | schéma strates, `train-of`, `read-train`, `orphans`, `elaboration-coverage`, `select-bridges` (BFS), behaviors daily-inbox / register / morning-dialog, builders `continues-fact`/`new-train-fact` | brancher les behaviors en mode batch |
| `belief.clj` | miroir de belief.py, `recompute-stances!` (écrit `:stance.recomputed`, voisinage 2 sauts) | décision : lequel des deux tourne (cf. §5 Q1) |
| — | — | **`deps.edn` n'existe pas** : DataScript 1.7.3 et data.json 2.5.0 ne sont cités qu'en commentaires |

**Écart doctrine/état sur la durabilité** : le PRD exige un journal
append-only `events.jsonl` write-ahead ; l'existant a un snapshot `log.edn`
(pr-str du log complet, réécrit). Le plan : garder la structure d'événements
de `append!` telle quelle, mais (a) sérialiser chaque événement en JSON
canonique appendé à `store/events.jsonl` AVANT `d/transact!`, (b) au boot,
`fold(events.jsonl)` via `project` ; `log.edn` disparaît (ou reste comme
cache de démarrage optionnel, vérifié contre le `state_hash`).

## 2 · Livrables Clojure précis

### 2.1 `deps.edn`

```clojure
{:deps {datascript/datascript {:mvn/version "1.7.3"}
        org.clojure/data.json {:mvn/version "2.5.0"}}
 :aliases
 {:consolidate {:main-opts ["-m" "mnemosyne.ingest"]}
  :test        {:main-opts ["-m" "mnemosyne.test-runner"]}}}
```
+ arborescence `src/mnemosyne/*.clj` (les fichiers actuels sont à plat —
les déplacer, ajuster les `ns`).

### 2.2 Événements JSON canoniques (`store/events.jsonl`)

```json
{"event_id":"sha256:…","seq":412,"type":"judgment.emitted",
 "actor":"ingestor","caused_by":"sha256:…","ts":"2026-07-04T02:10:00Z",
 "tx_data":[{…}]}
```
- `event_id = sha256(JSON canonique sans event_id)` — tri des clés,
  séparateurs compacts, UTF-8 NFC (attention : le fix UTF-8 existant dans
  ingest.clj concerne la lecture ; la canonicalisation d'écriture est
  nouvelle et DOIT être testée sur du français accentué).
- `seq` strictement croissant ; `state_hash` journalisé tous les 100
  événements et en fin de cycle (hash du db trié — implémenter
  `state-hash [db]` : sha256 de la seq triée des datoms EAV sérialisés).

### 2.3 `writeback_orders.jsonl` (producteur du contrat B2 FR-1)

Générateurs, dans l'ordre d'émission : promotions du cycle → flags lint →
stance-diffs → tâches (B3, via fichier produit par `task_gen.py` et
concaténé par `cycle.sh` — le consolidateur n'émet PAS les tâches
lui-même, il émet les *causes*) → digest (dernière ligne, compte tout).
`idempotency_key = event_id` de l'événement source (PRD FR-2).

### 2.4 Événements-causes pour `task_gen`

Nouveau fichier de sortie `task_causes.jsonl`, une ligne par cause :
```json
{"cause":"contradiction","claim":"uid","opposer":"uid","event_id":"sha256:…"}
{"cause":"triage.due","uid":"…","activation":0.31,"event_id":"…"}
{"cause":"bridge","a":"uid","b":"uid","score":0.87,"event_id":"…"}
```
(le type `review` est lu par task_gen directement depuis la review queue —
pas de passage par le consolidateur).

### 2.5 Routage humain (`outbox_human.jsonl` → règles PRD B3 FR-3)

Nouveau reader dans `ingest.clj` (même mécanique offset que les deux
outboxes existantes) ; dispatch sur `event` :
- `human.response` type `review` → ne touche pas DataScript ; réécrit en
  ligne calset dans `review_resolved.jsonl` (le merge Python existant fait
  le reste — split CALM respecté : le fichier est un export, pas un effet).
- type `elaborate` → `append!` proposition `:source/family :human`,
  stratum `:candidate`, kind `:permanent`.
- type `triage` / `bridge` → cf. tableau PRD B3 FR-3 (promotion de stratum ;
  arête candidate).
- `human.response.ambiguous` / `.amended` → événements journalisés +
  re-signalement digest ; aucun effet de domaine.

### 2.6 `export-jsonld!` (contrat FR-4, précisé par le CROSSWALK)

Classes à matérialiser (namespace `https://mnemosyne.dev/ns#`) :
`ProcessingActivity`, `Claim`, `PermanentNote`, `StaleDerived`,
`RegisterKeyword`, `Judgment`, arêtes réifiées avec type. Le focusNode est
`urn:mnemo:node:<uid>`. **Chemin de moindre effort v0** : `shacl_lint.py
export --roam` sait déjà produire du JSON-LD depuis un export Roam — mais
il ne voit pas les faits promus (strates, jugements). L'export du
consolidateur est donc bien requis pour S3/S5/S6/S7 ; celui de
`shacl_lint.py` reste utilisable pour S1/S2 en secours. Écrire les deux
colonnes dans le README (quelle shape dépend de quel exporteur).

## 3 · `cycle.sh` — précisions d'implémentation

- Ossature de `first_judge.sh` réutilisable telle quelle : marqueurs
  `.stageN.done` par cycle (`ops/cycles/<ts>/`), `--from N`, `--plan`,
  `--yes`, `require` de chaque binaire au préflight.
- Commandes exactes (v0) — le tableau des fichiers est dans
  `INTERFACES.md`, normatif :

```bash
1.  python3 roam_sync.py pull --config sync.yaml
2.  python3 task_harvest.py harvest --snapshot sync/snapshots/latest.json --out $C/outbox_human.jsonl
3.  python3 prefilter.py run --export sync/snapshots/latest.json --delta sync/deltas/<ts>.delta.jsonl \
       --state ops/pf_state.json --out $C/live_candidates.jsonl
4.  python3 judge_harness.py judge --judge $JUDGE --candidates $C/live_candidates.jsonl --outbox ops/outbox.jsonl
5.  clojure -M:consolidate --once --dir ops --cycle $C
6.  python3 belief.py compute --edges ops/edges.jsonl --out $C/stances.jsonl
    + diff avec ops/stances_prev.jsonl → $C/stance_diff.jsonl ; rotation
7.  clojure -M:consolidate --export-jsonld $C/graph.jsonld && python3 shacl_lint.py lint --data $C/graph.jsonld --out $C/lint.json
8.  python3 task_gen.py generate --causes $C/task_causes.jsonl --review-queues ops/first_judge/review_queue_*.md \
       --out-append $C/writeback_orders.jsonl --budget 5
9.  python3 roam_writeback.py apply --orders $C/writeback_orders.jsonl
10. python3 judge_metrics.py report --outbox ops/outbox.jsonl --contexts ops/contexts.jsonl --out-prefix $C/report
```
- Étape 6 : le stance-diff en v0 est un petit utilitaire Python dans
  `cycle_tools.py` (comparaison de `status` par `node`) — PAS un nouveau
  service ; SPEC-03 §3 (`update()` retourne `changed`) est l'upgrade path.
- Dépendances d'étapes (échec → saut) : 1←{2,3}, 3←4, {2,4}←5, 5←{6,7,8},
  {6,7,8}←9 ; 10 tourne toujours.
- launchd : plist `com.mnemosyne.cycle.plist`, `StartCalendarInterval`
  02:00, `StandardErrorPath` vers `ops/logs/` ; ne PAS utiliser cron sur
  macOS (pas de réveil machine) ; documenter `caffeinate -s` ou réglage
  « Prevent sleep » si le Mac dort la nuit.

## 4 · Tests — contenu exact

- **Golden replay** (`fixtures/consolidator/`) : `outbox_nominal.jsonl`
  (5 jugements, 2 jtypes), `outbox_dup.jsonl` (rejeu intégral),
  `outbox_unknown_jtype.jsonl`, `outbox_abstain.jsonl`,
  `outbox_human_all_types.jsonl` (5 réponses, une par type + ambiguë).
  Attendus committés : `events.expected.jsonl`, `edges.expected.jsonl`,
  `orders.expected.jsonl`. Comparaison byte-à-byte après normalisation du
  seul champ `ts` (injecter une horloge fixe en test — `*now-fn*`
  redéfinissable, à ajouter).
- **Crash test** : wrapper qui lance le consolidateur avec un hook
  `--crash-after-wal N` (flag de test : exit brutal entre write-ahead et
  transact) ; relance ; assert : aucun événement perdu/dupliqué, offsets
  corrects.
- **Replay test** : 3 cycles sur fixtures → `state-hash` final ; refold
  from scratch → même hash (M1).
- CI : GitHub Actions `ubuntu-latest`, `DeLaGuardo/setup-clojure`,
  job ~3 min ; la même commande tourne en local (`clojure -M:test`).

## 5 · Questions ouvertes (à trancher par ADR-002 court, dans le PR)

| Q | Options | Recommandation |
|---|---|---|
| Stances : `belief.py` (étape 6) ou `belief.clj` (`recompute-stances!` dans l'étape 5) ? | py / clj / les deux | **belief.py** en v0 (déjà self-testé, CLI prête, stance_report riche) ; `belief.clj` reste le miroir de vérification — un test CI compare les deux sur les fixtures V1–V15 |
| `log.edn` : garder comme cache de boot ? | oui / non | non en v0 — un seul chemin de vérité (`events.jsonl`), moins de code |
| Behaviors zettel (decay, register) en v0 ? | réactifs / batch / reportés | batch : appelés une fois par `--once` après `consolidate!` ; `run-to-fixpoint` reste hors chemin critique |
| Où vivent les uids Roam dans DataScript ? | `:node/id` = uid Roam | oui — vérifier que l'ingestion des sujets crée `{:node/id uid}` upsert (c'est le cas dans `emit-judgment!` via lookup refs) |

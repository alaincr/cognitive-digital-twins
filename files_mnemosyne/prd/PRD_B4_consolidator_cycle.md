# PRD B4 — Consolidateur exécuté et durable + orchestrateur de cycle

**Brique :** G4 de `00_gap_analysis.md`. **Priorité :** P0 (c'est le seul
écrivain ; sans lui rien n'est jamais promu). **Estimation :** 4–5 jours-dev.
**Profil :** dev Clojure (ou dev senior acceptant d'en faire), plus une demi-
journée d'ops pour le scheduling.

---

## 1 · Contexte et problème

Le consolidateur (`ingest.clj`) est la pièce centrale du design : writer
logique unique, il taille `outbox.jsonl`, applique les panels/gates, promeut
les jugements en faits de domaine, exporte `accepted.jsonl` (échantillonnage
ancre) et `edges.jsonl` (entrée de `belief.py`). Les offsets de lecture
survivent aux redémarrages. Le code existe, est soigné (jusqu'au correctif
UTF-8 pour le français) — **et n'a jamais été exécuté** : pas de JVM dans la
sandbox d'écriture, pas de CI, et surtout **le store DataScript est en
mémoire** : le fold ne survit pas au redémarrage du process.

Par ailleurs, aucun orchestrateur n'enchaîne les étapes du cycle quotidien.
`first_judge.sh` est un runbook de *calibration* (one-shot), pas une boucle.

**Décision structurante (recommandée, à ratifier par ADR) : exécuter le
Clojure existant, ne PAS le porter en Python.** Raisons : (a) le code
hand-checked encode déjà les contrats fins (normalisation underscores/hyphens,
dédoublonnage par `context_hash`, split CALM) et un port réintroduirait les
bugs que la relecture a éliminés ; (b) SPEC-00 §3.1 signale la CI JVM comme
« welcome side-quest » — ce PRD la rend obligatoire ; (c) le miroir
`belief.clj`/`zettel.clj` est déjà dans ce monde.

## 2 · Objectif et métriques

- **O1** : le consolidateur tourne réellement (JVM), consomme les outboxes,
  promeut, exporte — de façon **durable** (redémarrage sans perte).
- **O2** : un orchestrateur (`cycle.sh`) enchaîne la nuit :
  sync → prefilter → judge → harvest humain → consolidate → belief → lint →
  ordres de write-back → apply.
- **M1** : replay complet du log d'événements ⇒ état identique
  (hash structurel identique) — la propriété « now = fold(log) » démontrée.
- **M2** : kill -9 en plein cycle, relance ⇒ aucune promotion perdue ni
  dupliquée (idempotence par `context_hash` + offsets).
- **M3** : 7 cycles nocturnes consécutifs sans intervention.

## 3 · Périmètre

### v0
1. **Exécution** : `deps.edn` (DataScript 1.7.3, data.json), point d'entrée
   `-main`, smoke test qui charge les 5 namespaces (`mnemosyne`, `rules`,
   `judges`, `ingest`, `zettel`) et rejoue les fixtures.
2. **Durabilité** : journal d'événements append-only sur disque
   (`events.jsonl`, un JSON par événement de domaine, content-addressé).
   Au boot : fold du journal → DataScript en mémoire. C'est l'implémentation
   la plus simple qui honore la doctrine (le log EST la vérité) sans
   introduire XTDB/Datomic dans la boucle réduite.
3. **Sorties pour B2** : émettre `writeback_orders.jsonl` (contrat B2 FR-1) à
   partir des promotions/flags/stances du cycle.
4. **Routage humain** : implémenter les règles B3 FR-3 (consommer
   `outbox_human.jsonl`).
5. **Orchestrateur** `cycle.sh` + unité de scheduling (launchd sur macOS /
   systemd timer ailleurs).
6. **CI JVM** : job qui exécute les fixtures et le replay.

### Non-objectifs
- Migration XTDB/Datomic (upgrade path documenté, hors boucle réduite).
- Behaviors réactifs complets (`run-to-fixpoint` sur tout le graphe) : en v0
  le consolidateur tourne en **batch par cycle**, pas en démon réactif. Le
  mode démon est un flag futur, pas un livrable.
- Panels T2 multi-juges (un juge + gate ancre/humain en v0).

## 4 · Exigences fonctionnelles

### FR-1 · Journal durable
- Chaque promotion/flag/stance/rétraction émise par le consolidateur est
  appendue à `store/events.jsonl` AVANT d'être transactée dans DataScript
  (write-ahead) ; l'événement porte `event_id = sha256(canonical-JSON)` et
  `caused_by`.
- Au démarrage : `fold(events.jsonl)` reconstruit le db-value ; un
  `store/state_hash` (hash structurel du db trié) est recalculé et comparé au
  dernier hash journalisé — divergence = erreur fatale bruyante.
- Compaction : hors périmètre v0 (le journal d'un an de boucle réduite reste
  petit) ; documenter la borne attendue (< 100 Mo/an à 200 promotions/jour).

### FR-2 · Idempotence de bout en bout
- La déduplication existante (`already-ingested?` par
  `judge-id × context_hash × label`) doit être couverte par un test : rejouer
  deux fois le même `outbox.jsonl` ⇒ zéro nouvel événement.
- Les ordres de write-back reprennent l'`event_id` comme `idempotency_key`.

### FR-3 · Pipeline d'un cycle (`cycle.sh`)
Étapes, chacune avec timeout, code retour vérifié, log horodaté :
```
1. roam_sync.py pull                        (B1)
2. task_harvest.py harvest                  (B3) → outbox_human.jsonl
3. prefilter.py run --delta …               (B1/existant) → live_candidates.jsonl
4. judge_harness.py judge …                 (existant) → outbox.jsonl
5. clojure -M:consolidate --once            (ce PRD) → events, edges.jsonl,
                                              accepted.jsonl, writeback_orders.jsonl
6. belief.py compute --edges edges.jsonl    (existant) → stances.jsonl (+ diff)
7. shacl_lint.py … (export JSON-LD du store) (existant) → flags
8. task_gen.py generate                     (B3) → ordres task ajoutés
9. roam_writeback.py apply                  (B2)
10. judge_metrics.py report                 (existant) + append au rapport de cycle
```
- Échec d'une étape : les étapes suivantes qui en dépendent sont sautées, le
  digest du lendemain le mentionne, le cycle suivant rattrape (tout est
  idempotent + offsets).
- `cycle.sh --dry-run` imprime le plan ; `--from N` réentre (même convention
  que `first_judge.sh`).

### FR-4 · Export JSON-LD pour le linter
`shacl_lint.py` consomme du JSON-LD (fixtures `*.jsonld` existantes). Le
consolidateur doit fournir `export-jsonld!` (le CROSSWALK indique que les
classes matérialisées par l'exporteur, ex. `mnemo:PermanentNote`,
`mnemo:StaleDerived`, sont attendues par les shapes S3/S7 — c'est un contrat,
pas un détail).

### FR-5 · Stance-diff
Étape 6 : conserver `stances_prev.jsonl` et n'émettre vers le write-back que
les **changements** de statut (le contrat `update()` de SPEC-03 §3 prévoit
exactement ce diff).

## 5 · Exigences non fonctionnelles

- Un cycle complet ≤ 30 min sur le graphe réel (hors temps d'inférence juges).
- Aucun réseau dans le consolidateur lui-même (il lit/écrit des fichiers —
  la séparation actuelle est bonne, la garder).
- Logs : une ligne par étape + compteurs (candidats, jugés, abstenus, promus,
  flags, ordres) — ce sont les chiffres du rapport hebdo B7.
- Config unique `cycle.yaml` (chemins, budgets, juge actif) — finir avec les
  valeurs éparpillées dans les variables d'environnement.

## 6 · Cas limites

1. Outbox contenant un jtype inconnu → événement `quarantined`, cycle continue
   (ne jamais bloquer le writer sur une ligne).
2. `edges.jsonl` vide (aucune promotion) → belief/lint tournent quand même
   (les stances peuvent changer par rétraction).
3. Horloge : les cycles sont nommés par timestamp UTC du début ; deux cycles
   le même jour (run manuel + nocturne) sont distincts et sûrs (idempotence).
4. Journal corrompu (ligne tronquée par crash) : au boot, tolérer UNE ligne
   finale invalide (la tronquer avec log bruyant) ; toute corruption interne
   = arrêt fatal, restauration manuelle documentée.

## 7 · Plan de test et DoD

- **Golden replay** : fixtures outbox (fournies : cas nominal, doublon,
  abstention, jtype inconnu, réponse humaine de chaque type B3) → événements
  attendus committés en fixtures ; le test compare byte-à-byte.
- **Crash test** : script qui kill -9 le consolidateur entre write-ahead et
  transaction, relance, vérifie M2.
- **Replay test** : fold complet du journal d'un run de 3 cycles ⇒
  `state_hash` identique.
- CI : job JVM (GitHub Actions ou local) exécutant les trois tests ci-dessus +
  les self-tests Python de la régression programme.
- DoD : CI verte ; 7 cycles nocturnes réels (M3) ; `README_cycle.md` avec la
  procédure launchd/systemd, la restauration après corruption, et le tableau
  des fichiers échangés entre étapes (le contrat inter-briques, en un seul
  endroit).

## 8 · Risques

| Risque | Prob. | Mitigation |
|---|---|---|
| Le Clojure hand-checked casse au premier run réel | haute (attendue) | c'est précisément le but du golden replay ; budgéter 1–2 j de fixes dans l'estimation |
| Dérive des contrats fichiers entre 10 étapes | moyenne | le tableau des fichiers du README est normatif ; tout changement = PR sur ce tableau |
| Personne ne sait déboguer Clojure dans l'équipe | moyenne | le périmètre Clojure est confiné à l'étape 5 ; tout le reste est Python ; documenter un runbook REPL minimal |

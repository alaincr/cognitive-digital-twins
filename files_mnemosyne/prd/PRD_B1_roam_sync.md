# PRD B1 — Connecteur de synchronisation Roam (`roam_sync.py`)

**Brique :** G1 de `00_gap_analysis.md`. **Priorité :** P0 (chemin critique).
**Estimation :** 3–4 jours-dev. **Profil :** dev Python pipeline, à l'aise avec
des APIs HTTP mal documentées.

---

## 1 · Contexte et problème

Tout l'amont du pipeline (`roam_harvest.py`, `prefilter.py`, `first_judge.sh`)
consomme un **export JSON Roam déposé manuellement** (`EXPORT=~/roam-export.json`).
Deux conséquences :

1. **Pas de cadence** : aucune boucle quotidienne n'est possible sans un humain
   qui clique « Export All » chaque soir.
2. **Pas d'historique** : un export Roam ne porte pas l'historique d'édition.
   `roam_harvest.py` le documente comme caveat : les types `propagate` /
   `invalidate` travaillent sur une *reconstruction* du delta, et
   `prefilter.py` doit deviner les dirty-marks à partir des `edit-time`.

B1 fournit l'acquisition automatisée **et** transforme la limitation « pas
d'historique » en non-problème : en conservant des snapshots datés et en les
diffant, on reconstruit un flux de deltas bloc-par-bloc — exactement ce que le
préfiltre et les juges attendent.

## 2 · Objectif et métriques de succès

- **O1** : un export frais du graphe du propriétaire est disponible localement
  chaque nuit sans intervention humaine.
- **O2** : chaque cycle dispose d'un fichier de deltas (`delta.jsonl`) listant
  les blocs créés / modifiés / supprimés depuis le snapshot précédent.
- **M1** : 7 acquisitions nocturnes consécutives sans échec non rattrapé.
- **M2** : le diff d'un graphe inchangé est vide (zéro faux positif) ; le diff
  après édition d'un bloc contient exactement ce bloc (test d'intégration).

## 3 · Périmètre

### v0 (obligatoire)
- Mode **pull API** : acquisition via l'API backend HTTP de Roam.
- Mode **drop-folder** (fallback) : un export manuel déposé dans un répertoire
  surveillé est détecté, validé, normalisé et snapshotté à l'identique du mode
  pull. La suite du pipeline ne voit pas la différence.
- Store de snapshots + diff bloc-à-bloc + `delta.jsonl`.

### v1 (souhaitable, hors DoD)
- Détection de renommages de pages (title change avec uids conservés).
- Compaction des snapshots anciens (garder 1/semaine au-delà de 30 jours).

### Non-objectifs
- Écrire dans Roam (c'est B2).
- Temps réel / websockets. La granularité est le cycle (quotidien par défaut).
- Support multi-graphes.

## 4 · Exigences fonctionnelles

### FR-1 · Acquisition par API (mode `pull`)
- Utiliser l'API backend Roam (token d'API graphe, endpoints `q` / `pull`) pour
  récupérer l'intégralité des pages et blocs avec, au minimum, les champs que
  `roam_harvest.py::Graph.parse` consomme : `title`, `uid`, `string`,
  `children` (récursif), `create-time`, `edit-time`.
- La sortie DOIT être **normalisée au format « Export All » JSON de Roam**
  (liste de pages avec `children` imbriqués) : le contrat aval est ce format,
  ne pas en inventer un autre.
- Pagination / chunking : le fetch complet doit fonctionner sur un graphe de
  50 000 blocs sans dépasser les limites de l'API (requêtes par lots de pages,
  backoff exponentiel sur 429/5xx, reprise sur erreur partielle : un échec de
  lot n'invalide pas les lots déjà obtenus, mais un snapshot n'est **commité
  que s'il est complet**).
- Secrets : token lu depuis `ROAM_API_TOKEN` (env) ou `--token-file` ; jamais
  en clair dans la config ni les logs.

### FR-2 · Mode `drop-folder` (fallback sans API)
- `roam_sync.py watch --dir drops/` (ou un check au début du cycle) : détecte
  tout fichier `*.json` ou `*.zip` (l'export Roam natif est zippé) nouveau,
  le dézippe si besoin, valide le schéma (FR-3), le snapshotte, puis archive le
  fichier source dans `drops/processed/`.
- Ce mode est le plan B permanent : toute panne de l'API backend doit pouvoir
  être compensée par un export manuel sans rien changer d'autre.

### FR-3 · Validation
Avant de committer un snapshot, valider :
- JSON parsable, liste non vide de pages, ≥ 1 bloc avec `uid` et `string` ;
- volumétrie plausible : refuser (et alerter) si le nombre de blocs chute de
  plus de 40 % par rapport au snapshot précédent (export tronqué — un vrai
  ménage utilisateur se déverrouille par `--force`) ;
- unicité des `uid` (collision = erreur fatale, c'est la clé du diff).

### FR-4 · Store de snapshots
```
sync/
  snapshots/2026-07-04T0200Z.json.gz     # export normalisé, gzippé
  snapshots/latest.json                   # symlink/copie du dernier
  deltas/2026-07-04T0200Z.delta.jsonl
  sync_state.json                         # dernier snapshot, hash, stats
```
- Chaque snapshot est immuable une fois écrit ; `sha256` enregistré dans
  `sync_state.json` (cohérent avec la discipline content-address du projet).

### FR-5 · Diff bloc-à-bloc
- Clé de diff : `uid`. Pour chaque uid : `added` / `removed` / `edited`
  (comparaison de `string`, du parent, et de la page hôte).
- Ligne de delta :
```json
{"op": "edited", "uid": "aBcD3fGh1", "page": "R/Perception",
 "parent": "xYz...", "before_hash": "sha256:…", "after_hash": "sha256:…",
 "string": "<texte après>", "edit_time": 1783123200000,
 "snapshot": "2026-07-04T0200Z"}
```
- Les déplacements (même uid, parent différent) sont `op: "moved"` — ils ne
  doivent PAS apparaître comme removed+added.
- Le delta est **append-only** : un fichier par snapshot, jamais réécrit.

### FR-6 · Intégration aval
- `prefilter.py` doit pouvoir consommer `delta.jsonl` comme source de
  dirty-marks à la place de son inférence par `edit-time` (ajout d'une option
  `--delta` ; modification ≤ 30 lignes, à livrer avec B1 et à couvrir dans son
  self-test existant).
- `roam_harvest.py` reste inchangé (il consomme `snapshots/latest.json`).

### FR-7 · CLI
```
roam_sync.py pull   --config sync.yaml [--force]
roam_sync.py ingest-drop --dir drops/ [--force]
roam_sync.py diff   --old <snap> --new <snap> [--out …]   # aussi appelé par pull
roam_sync.py status                                        # dernier snapshot, âge, volumétrie
roam_sync.py self-test                                     # zéro réseau
```

## 5 · Exigences non fonctionnelles

- **Stdlib-first** (convention SPEC-00 §3.1) : `urllib` + `gzip` + `json`
  suffisent ; toute dépendance nouvelle exige le paragraphe de justification.
- Déterminisme : deux runs de `diff` sur les mêmes snapshots → sorties
  byte-identiques (tri stable par uid).
- Un pull complet ≤ 10 min sur 50 000 blocs ; le diff ≤ 30 s.
- Logs structurés une-ligne-par-événement sur stderr ; le canal stdout est
  réservé aux sorties machine.

## 6 · Cas limites à traiter explicitement

1. Export vide ou tronqué (FR-3) — refus + alerte, on garde l'ancien snapshot.
2. Premier run (pas de snapshot précédent) — delta = tout en `added`, marqué
   `"initial": true` pour que le préfiltre ne traite pas 50 000 blocs comme
   « sales » (budget normal, tri par `edit_time` décroissant).
3. Uid réutilisé après suppression (rare mais possible) — traiter comme
   `removed` puis `added`, jamais `edited`.
4. Caractères accentués / NFC-NFD : normaliser NFC à l'entrée du store (le
   consolidateur Clojure a déjà un correctif UTF-8 ; ne pas lui envoyer du NFD).
5. Horloge : les timestamps de snapshot viennent de l'horloge locale UTC ; les
   `edit-time` Roam sont pris tels quels (millisecondes epoch).

## 7 · Plan de test et Definition of Done

- `self-test` (obligatoire, zéro réseau) : fixtures de deux mini-exports
  synthétiques → assertions sur added/edited/removed/moved, idempotence du
  diff, refus de l'export tronqué, normalisation NFC. ≥ 12 assertions.
- Test d'intégration manuel documenté : pull réel du graphe du propriétaire,
  édition d'un bloc dans Roam, second pull, vérifier que le delta contient
  exactement ce bloc.
- DoD : self-test vert ; `python3 -m py_compile` vert ; ajouté à la commande de
  régression programme (SPEC-00 §5) ; `prefilter.py --delta` livré et testé ;
  README court (`README_sync.md`) avec la procédure token API et le mode
  drop-folder ; 7 nuits de pull réussies chez le propriétaire (critère M1,
  validé en exploitation, pas en CI).

## 8 · Risques

| Risque | Prob. | Mitigation |
|---|---|---|
| API backend Roam instable / non disponible sur ce plan | moyenne | le mode drop-folder est un livrable v0 à part entière, pas un « nice to have » |
| Graphe > limites API | faible | chunking FR-1 ; sinon bascule drop-folder |
| Dérive du format d'export Roam | faible | FR-3 valide le schéma et échoue bruyamment |

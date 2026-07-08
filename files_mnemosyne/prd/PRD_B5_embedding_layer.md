# PRD B5 — Couche embeddings minimale (régime B) : `embed_index.py`

**Brique :** G5 de `00_gap_analysis.md`. **Priorité :** P1 (la boucle ferme
sans elle, mais les mécanismes zettel les plus utiles tournent à vide).
**Estimation :** 3 jours-dev. **Profil :** dev Python ML-léger.

---

## 1 · Contexte et problème

Trois mécanismes déjà spécifiés/écrits présupposent des arêtes de similarité
`:sim/near` qui n'existent nulle part :

1. **Morning dialog / bridges** (`zettel_addendum.md` §8) : « paires
   embedding-proches dans des trains différents sans chemin court » — sans
   embeddings, `morning-dialog` rend zéro, silencieusement (échec fermé
   documenté §11).
2. **Candidats `continues`** : l'addendum §11 note que le harvest lexical
   « sous-proposera » ; le kNN est la source prévue de parents candidats.
3. **L'échelle des régimes** (`microjudge_contract.md` §1) : le rung B
   (embedding/relationnel) est un étage de l'architecture — il est
   actuellement vide, donc tout escalade de A directement en B½.

## 2 · Objectif et métriques

- **O1** : chaque bloc de contenu du snapshot a un embedding à jour ;
  l'index répond à « les k plus proches de X » en < 50 ms.
- **O2** : chaque cycle produit `sim_pairs.jsonl` (paires au-dessus du seuil,
  avec score) consommé par le harvest `continues`, le générateur de bridges
  (B3) et, plus tard, `dedup_prop`.
- **M1** : réindexation incrémentale — un cycle où 50 blocs ont changé
  n'encode que ~50 blocs (vérifié par compteur).
- **M2** : rappel sanity-check : sur 20 paires de doublons évidents plantées
  en fixture, ≥ 18 dans le top-5 mutuel.

## 3 · Périmètre

### v0
- Modèle d'embedding **local et multilingue** (corpus FR/IT/EN). Recommandé :
  `intfloat/multilingual-e5-small` via `sentence-transformers` (CPU suffisant
  à cette échelle), dimension 384. Dérogation stdlib-first justifiée dans le
  PR (convention SPEC-00 §3.1) ; le modèle est épinglé par révision (hash) —
  même discipline que les judge_id.
- Store : SQLite (fichier `store/embeddings.db`) : `(uid, content_hash,
  model_rev, vector BLOB, updated_ts)`. Recherche : brute force numpy
  (50 000 × 384 tient très largement ; FAISS est un non-besoin à cette
  échelle — le noter pour éviter l'ingénierie spontanée).
- Trois sorties par cycle : `sim_pairs.jsonl`, `continues_candidates.jsonl`
  (parents kNN proposés pour les blocs récents), `bridge_seeds.jsonl`.

### Non-objectifs
- Recherche sémantique interactive (c'est un sous-produit facile, mais hors DoD).
- Le classificateur relationnel R-GCN du rung B (contrat §1) — plus tard.
- GPU, quantization, serving : c'est un batch CPU nocturne.

## 4 · Exigences fonctionnelles

### FR-1 · Sélection des blocs à encoder
- Mêmes bornes que `content_blocks()` de `roam_harvest.py` (30–500 chars,
  réutiliser la fonction, ne pas la dupliquer) ; exclure l'espace `M/*`
  (ne jamais indexer les écritures du système — boucle de rétroaction).
- Texte encodé = string du bloc avec `((brefs))` développés (même
  `expand_brefs` que le harvest) ; préfixes e5 (`query:`/`passage:`) : utiliser
  `passage:` uniformément (on compare des passages entre eux).

### FR-2 · Incrémental par content-address
- Clé : `sha256(model_rev + norm(text))`. Un bloc dont le hash n'a pas changé
  n'est jamais ré-encodé. Le delta B1 fournit la liste des blocs touchés ;
  un `--full` force la réindexation (changement de modèle).

### FR-3 · Paires de similarité
- `sim_pairs.jsonl` : pour chaque bloc modifié du cycle, ses k=10 voisins avec
  score cosinus ≥ seuil (défaut 0.80) :
```json
{"a": "uid1", "b": "uid2", "score": 0.87, "model_rev": "e5s@…", "cycle": "…"}
```
- Paires ordonnées (`a < b` lexicographique) pour l'idempotence aval.

### FR-4 · Candidats `continues`
- Pour chaque bloc *nouveau* du cycle : top-3 voisins **plus anciens**,
  émis au format candidate row du harness (`jtype: continues`,
  `subjects: [child, parent]`, champs requis `child/child_context/parent/
  parent_context` remplis comme dans `roam_harvest.py::h_continues`).
- Ces candidats entrent dans le même budget préfiltre que les lexicaux
  (déduplication par `context_hash` déjà assurée par le harness).

### FR-5 · Graines de bridges
- Paires score ≥ 0.80, blocs sur des **pages différentes**, émises brutes ;
  le raffinement « pas de chemin graphe court » appartient au consolidateur
  (`select-bridges` dans `zettel.clj` — BFS déjà écrite), pas à cette brique.

### FR-6 · CLI
```
embed_index.py update  --snapshot … --delta … --db store/embeddings.db
embed_index.py pairs   --db … --changed-uids … --out sim_pairs.jsonl [--k 10] [--min-score 0.80]
embed_index.py continues-candidates --db … --new-uids … --out …
embed_index.py query   --db … --text "…" [--k 10]        # debug/confort
embed_index.py self-test                                   # modèle mocké (vecteurs hashés déterministes)
```

## 5 · Exigences non fonctionnelles

- Le self-test n'importe PAS torch/sentence-transformers (lazy import, mock
  vectoriel déterministe injecté — pattern SPEC-00 §3.2).
- Indexation complète initiale ≤ 30 min CPU sur 50 000 blocs ; cycle
  incrémental ≤ 2 min.
- `model_rev` dans chaque ligne de sortie : un changement de modèle invalide
  proprement (les paires de revs différentes ne sont jamais mélangées).

## 6 · Cas limites

1. Bloc raccourci sous 30 chars après édition → retirer son vecteur, retirer
   ses paires futures (les paires passées, immuables, restent dans leurs
   fichiers de cycle).
2. Texte identique sur deux uids (vrai doublon) → score 1.0, c'est un candidat
   `dedup_prop` de choix ; ne pas le filtrer.
3. Changement de `model_rev` sans `--full` → erreur fatale explicite (index
   hétérogène interdit).
4. OOM/CPU saturé sur l'init → batch de 256 avec checkpoint tous les 2 000
   blocs (reprise sans réencodage).

## 7 · Plan de test et DoD

- Self-test : mock vectoriel ; assertions sur incrémental (M1), ordre des
  paires, exclusion `M/*`, format candidate-row conforme à
  `judge_prompts.REQUIRED_FIELDS["continues"]` (validation croisée contre le
  registre réel — importable sans réseau). ≥ 12 assertions.
- Fixture réelle : mini-corpus FR de 40 blocs avec doublons plantés (M2).
- DoD : self-test dans la régression programme ; run réel sur le snapshot du
  propriétaire avec rapport (nb vecteurs, distribution des scores, top-20
  paires pour inspection visuelle) ; `README_embeddings.md` (choix du modèle,
  procédure de changement de modèle).

## 8 · Risques

| Risque | Prob. | Mitigation |
|---|---|---|
| Seuil 0.80 mal calé pour le corpus FR/juridique | moyenne | le rapport DoD inclut la distribution ; le seuil est en config, tuné à la phase 2 avec les chiffres |
| Dérive vers l'infra (FAISS, serving, GPU) | moyenne | non-objectifs explicites §3 ; brute-force numpy est un choix, pas un manque |
| Bruit de candidats `continues` noyant le budget | faible | top-3, blocs nouveaux uniquement, budget préfiltre inchangé |

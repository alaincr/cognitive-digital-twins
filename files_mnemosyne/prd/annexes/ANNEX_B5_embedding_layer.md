# Annexe technique B5 — `embed_index.py`

**Complète :** `PRD_B5_embedding_layer.md`. Le PRD prime en cas de conflit.

---

## 1 · Contrats amont/aval vérifiés

### 1.1 Fonctions à réutiliser (`roam_harvest.py`)

- `content_blocks(g, lo=30, hi=500)` (l. ~155) : filtre longueur + exclut
  les blocs citation (`>`). Réutiliser tel quel (import, pas copie) ;
  ajouter côté B5 le filtre supplémentaire « page hors `M/*` » (le harvest
  ne le fait pas — c'est une exigence B5, pas une modification du harvest).
- `Graph.expand_brefs(s)` (l. ~126) : développe `((uid))` → string du bloc
  cible, laisse tel quel si uid inconnu. Le texte encodé =
  `expand_brefs(b["string"])`.

### 1.2 Format candidate-row `continues` (contrat de sortie FR-4, exact)

Vérifié dans `roam_harvest.py::h_continues` + `zettel_prompts.py` :

```json
{"jtype": "continues",
 "subjects": ["<uid-child>", "<uid-parent>"],
 "fields": {"child": "…", "child_context": "…",
            "parent": "…", "parent_context": "…"},
 "meta": {"mode": "knn", "sim": 0.86, "model_rev": "e5s@<rev>"}}
```

- `subjects = [child, parent]` — directionnel, jamais inversé
  (`continues` est dans `CANONICAL_ORDER_ONLY`).
- `child_context` / `parent_context` : mêmes conventions que le harvest
  lexical (parent block + page title) — lire `h_continues` avant d'écrire
  les contextes, la symétrie des deux sources est ce qui permet au juge de
  ne pas distinguer kNN et lexical.
- Validation croisée au self-test : `judge_prompts.REQUIRED_FIELDS` après
  `zettel_prompts.register()` donne
  `continues → ["child","child_context","parent","parent_context"]` —
  assertion d'égalité avec les clés émises (le PRD l'exige, c'est le test
  anti-dérive de registre).
- Ces candidats passent ensuite par le budget/debounce du préfiltre
  (`DEFAULT_BUDGETS["continues"] = 15`, cooldown par `(jtype, subjects)` +
  `fields_hash`) — B5 n'a PAS son propre debounce.

### 1.3 Aval bridges

`bridge_seeds.jsonl` est consommé par `select-bridges` (zettel.clj, BFS
k-hop) via B4, qui émet les causes `bridge` pour `task_gen` (annexe B4
§2.4). B5 émet brut : paires score ≥ seuil, pages différentes, rien d'autre.

## 2 · Schéma SQLite (normatif)

```sql
CREATE TABLE IF NOT EXISTS embeddings (
  uid          TEXT NOT NULL,
  model_rev    TEXT NOT NULL,
  content_hash TEXT NOT NULL,        -- sha256(model_rev + nfc(text))
  dim          INTEGER NOT NULL,
  vector       BLOB NOT NULL,        -- float32 little-endian, dim * 4 octets
  page         TEXT,
  updated_ts   INTEGER,
  PRIMARY KEY (uid, model_rev)
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
-- meta: model_rev courant, dim, created_ts
```

- `vector` : `struct.pack(f"<{dim}f", *vec)` — lisible par numpy
  (`np.frombuffer(blob, dtype="<f4")`) sans dépendance à l'écriture.
- Un seul `model_rev` actif : au chargement, si `meta.model_rev` ≠ celui de
  la config et pas de `--full` → erreur fatale (cas limite 3 du PRD).
- Normalisation L2 à l'écriture → le cosinus devient un produit scalaire
  (`M @ q`), brute force numpy sur matrice mémoire (50 000 × 384 × 4 o
  ≈ 74 Mo — trivial).

## 3 · Modèle et épinglage

- `intfloat/multilingual-e5-small`, dim 384, préfixe `passage:` uniforme
  (PRD FR-1).
- `model_rev` = `"e5-small@" + revision_hash[:8]` où le hash vient de
  `huggingface_hub` (commit hash du snapshot local) — même discipline que
  `judge_id` (`modèle@poids#version`).
- Téléchargement épinglé : `SentenceTransformer(model_id, revision=REV)` ;
  documenter REV dans `README_embeddings.md` et dans `meta`.
- Justification de dérogation stdlib-first (SPEC-00 §3.1) à copier dans le
  PR : sentence-transformers + torch CPU, imports **lazy** (pattern
  SPEC-00 §3.2) ; le self-test injecte `mock_encode(texts) ->
  vecteurs déterministes par hash sha256 du texte replié en float32
  normalisés` — zéro import torch au self-test (assertion `"torch" not in
  sys.modules` en fin de self-test, comme le fait `distill_judge.py`).

## 4 · Algorithmes par sous-commande

- `update` : lire delta B1 (`added`+`edited` ; `removed` → DELETE du
  vecteur) ; filtrer via `content_blocks` + hors `M/*` ; batch 256,
  checkpoint DB tous les 2 000 (cas limite 4) ; compteur
  `encoded/skipped/deleted` sur stderr (c'est M1).
- `pairs` : matrice complète en mémoire ; pour chaque uid changé :
  top-k=10, score ≥ 0.80 ; ordre `a < b` ; dédup intra-fichier ; une ligne
  meta en tête : `{"meta":"pairs","cycle":…,"changed":N,"emitted":M}`.
- `continues-candidates` : uids *nouveaux* du cycle (op `added` du delta)
  → top-3 voisins avec `create-time` antérieur (l'information vient du
  snapshot, pas de la DB — joindre) → candidate rows §1.2.
- `bridge_seeds` : sous-ensemble de `pairs` où `page(a) ≠ page(b)` —
  calculé dans la même passe, fichier séparé.

## 5 · Découpage en tâches

| # | Tâche | Est. |
|---|---|---|
| 1 | Store SQLite + mock vectoriel + `update` incrémental + self-test M1 | 1 j |
| 2 | `pairs` + `bridge_seeds` + ordre/idempotence + self-test | 0,5 j |
| 3 | `continues-candidates` + validation croisée REQUIRED_FIELDS | 0,5 j |
| 4 | Chemin réel e5 (lazy, épinglage, batch/checkpoint) + init complète sur le graphe réel + rapport DoD (distribution des scores, top-20) | 1 j |

## 6 · Fixtures (`fixtures/embed/`)

- `mini_corpus_fr.json` : 40 blocs FR dont 20 formant 10 paires de
  quasi-doublons plantés (M2 : ≥ 18/20 en top-5 mutuel — ce test tourne
  avec le VRAI modèle, marqué `@slow`, hors self-test).
- Self-test (mock) : incrémental (2 runs, 2e run encode 0), suppression
  (bloc < 30 chars), exclusion `M/*`, ordre `a<b`, erreur model_rev,
  format candidate-row.

## 7 · Questions ouvertes

| Q | Recommandation |
|---|---|
| Seuil 0.80 pour du FR juridique | garder 0.80 en config, mais le rapport DoD calcule aussi les quantiles à 0.75/0.85 pour éclairer le tuning phase 2 |
| Contexte de bloc dans le texte encodé (parent/page) ? | non en v0 — encoder le bloc seul (brefs développés) ; noter comme expérience phase 2 |
| Où tourne l'init 30 min ? | sur le Mac du propriétaire, en journée, une fois ; le cycle nocturne n'encode que le delta |

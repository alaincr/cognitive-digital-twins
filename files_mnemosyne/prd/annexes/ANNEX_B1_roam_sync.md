# Annexe technique B1 — `roam_sync.py`

**Complète :** `PRD_B1_roam_sync.md` (normatif). Cette annexe fournit les
contrats d'interface exacts, le squelette du module, le découpage en tâches,
et les fixtures de test. En cas de conflit, le PRD prime sur l'annexe ;
l'annexe prime sur l'intuition du dev.

---

## 1 · Contrats amont/aval vérifiés sur le code existant

### 1.1 Ce que `roam_harvest.py::Graph.parse` consomme (contrat de sortie B1)

Le snapshot normalisé DOIT être une `list[dict]` de pages :

```json
[
  {
    "title": "R/Perception",
    "edit-time": 1783123200000,
    "children": [
      {
        "uid": "aBcD3fGh1",
        "string": "texte du bloc",
        "create-time": 1783000000000,
        "edit-time": 1783123200000,
        "children": [ /* récursif, même forme */ ]
      }
    ]
  }
]
```

Points vérifiés dans le code :
- `Graph.parse` tolère `title` absent (défaut `"untitled"`) et `children`
  absent — mais B1 ne doit PAS s'appuyer sur cette tolérance : la validation
  FR-3 exige `uid` et `string` sur les blocs.
- Les uids manquants sont auto-générés `anon-N` par le parseur — un snapshot
  B1 qui en produit casserait le diff (la clé est l'uid). La validation FR-3
  doit donc **refuser** tout bloc sans uid, plutôt que laisser le parseur
  inventer.
- Timestamps : millisecondes epoch, clés avec tiret (`edit-time`,
  `create-time`) — pas d'underscore.

### 1.2 Ce que `prefilter.py` fait aujourd'hui (point d'insertion `--delta`)

- Fonction actuelle : `dirty_blocks(g, since_ms)` (~ligne 104) retourne
  `[b for b in g.blocks.values() if max(b["edit"], b["create"]) >= since_ms
  and len(b["string"]) >= 25]`.
- Le point d'insertion de `--delta` est **exactement là** : une fonction
  jumelle `dirty_blocks_from_delta(g, delta_path)` qui résout chaque
  `uid` du delta (`op ∈ {added, edited, moved}`) dans `g.blocks` et
  applique le même filtre de longueur (≥ 25 chars). Les `removed` sont
  ignorés (le bloc n'existe plus dans le snapshot ; le consolidateur les
  traitera plus tard via les événements).
- Le watermark `last_run_ms` de `state.json` reste maintenu (fallback si
  `--delta` absent) — les deux modes coexistent, `--delta` gagne s'il est
  fourni.
- Le format de sortie (`live_candidates.jsonl`) et les budgets
  (`DEFAULT_BUDGETS`, cooldown par `(jtype, subjects)` + `fields_hash`)
  ne changent pas.

## 2 · API backend Roam — fiche d'implémentation

> **À vérifier contre la doc officielle au jour J**
> (https://roamresearch.com/#/app/developer-documentation — l'API backend
> est encore jeune et bouge). Les points ci-dessous reflètent l'état connu
> et les pièges identifiés ; `infra_check.py` (B6) et le self-test réseau
> manuel doivent confirmer.

- **Base** : `https://api.roamresearch.com/api/graph/{graph-name}/{op}` avec
  `op ∈ {q, pull, pull-many, write}`. POST JSON.
- **Auth** : header `X-Authorization: Bearer <token>` (token d'API graphe,
  généré dans les settings du graphe ; scopes read / edit — B1 n'a besoin
  que de read, demander un token read-only distinct de celui de B2).
- **Piège n°1 — redirections** : l'API répond souvent `307` vers un peer
  (`peer-N.api.roamresearch.com`). `urllib` ne rejoue PAS un POST avec corps
  sur 307 automatiquement dans tous les cas — implémenter la re-soumission
  explicite (même méthode, même corps, mêmes headers) avec une boucle bornée
  (max 3 redirections).
- **Piège n°2 — rate limit** : de l'ordre de quelques dizaines de requêtes/min
  par graphe. Le fetch par lots de pages (FR-1) doit espacer (droplet de
  ~1 req/s par défaut) et traiter `429` par backoff exponentiel (base 2 s,
  max 60 s, jitter).
- **Stratégie de fetch complet** (2 étapes) :
  1. `q` : `[:find ?uid ?title :where [?p :node/title ?title] [?p :block/uid ?uid]]`
     → liste des pages (uid + titre).
  2. `pull` par page avec sélecteur récursif :
     `[:block/uid :node/title :block/string :block/order :create/time :edit/time {:block/children ...}]`
     → arbre complet d'une page. Normaliser ensuite vers le format §1.1
     (renommer `:block/string` → `string`, `:edit/time` → `edit-time`, trier
     les enfants par `:block/order`, etc.).
- **`pull-many`** permet de grouper (lots de ~30 pages) — à préférer si
  disponible, sinon boucle `pull`.
- Un lot échoué se retente 3× puis marque le pull **incomplet** : aucun
  snapshot n'est commité (FR-1 : « commité que s'il est complet »), le
  fichier partiel part dans `sync/failed/` pour diagnostic.

## 3 · Schémas de fichiers (normatif, complète FR-4/FR-5)

### 3.1 `sync_state.json`

```json
{
  "last_snapshot": "2026-07-04T0200Z",
  "last_sha256": "sha256:…",
  "block_count": 41230,
  "page_count": 1180,
  "mode": "pull|drop",
  "history": [
    {"snapshot": "2026-07-03T0200Z", "sha256": "…", "blocks": 41190,
     "delta": {"added": 34, "edited": 12, "removed": 2, "moved": 1}}
  ]
}
```
`history` borné aux 90 dernières entrées.

### 3.2 `delta.jsonl` — les quatre opérations

```json
{"op":"added",  "uid":"…", "page":"…", "parent":"…", "string":"…", "after_hash":"sha256:…", "edit_time":1783…, "snapshot":"…"}
{"op":"edited", "uid":"…", "page":"…", "parent":"…", "string":"…", "before_hash":"sha256:…", "after_hash":"sha256:…", "edit_time":…, "snapshot":"…"}
{"op":"removed","uid":"…", "page":"…", "parent":"…", "before_hash":"sha256:…", "snapshot":"…"}
{"op":"moved",  "uid":"…", "page":"…", "parent":"…", "old_page":"…", "old_parent":"…", "after_hash":"sha256:…", "snapshot":"…"}
```

Règles de classement (précise FR-5) :
- `string` changé (hash différent) et parent identique → `edited`.
- parent OU page changé, `string` identique → `moved`.
- les deux changés → **deux lignes** : `moved` puis `edited` (ordre fixe),
  pour que chaque consommateur puisse filtrer sur une seule dimension.
- Tri du fichier : par `op` (added < edited < moved < removed) puis `uid` —
  c'est ce qui rend le diff byte-déterministe (NFR).
- `before_hash`/`after_hash` = `sha256("nfc:" + unicodedata.normalize("NFC", string))`.

### 3.3 Premier run

`delta` avec `"initial": true` sur chaque ligne + un header en ligne 1 :
```json
{"meta":"initial-import", "snapshot":"…", "blocks":41230}
```
`prefilter.py --delta` doit détecter ce header et retomber sur son mode
watermark normal (budget standard, tri `edit_time` décroissant) — assertion
dédiée dans son self-test.

## 4 · Squelette du module (~600 lignes attendues)

```
roam_sync.py
├── CONFIG (dataclass) : graph, token(file), dirs, timeouts, rate, force
├── fetch_api(cfg) -> list[page]          # §2 ; requests interdits, urllib
│     ├── _post(url, body, token, redirects=3, retries=3)
│     └── _normalize(pull_result) -> page-dict (§1.1)
├── ingest_drop(cfg) -> list[page]        # unzip + parse + même _normalize
├── validate(pages, prev_state) -> None | SyncError   # FR-3
├── snapshot_write(pages, ts) -> path     # gzip + sha256 + latest.json
├── diff(old_pages, new_pages) -> list[delta-line]    # FR-5, pur, testable
│     └── _flatten(pages) -> dict[uid, (string, parent, page, edit)]
├── cmd_pull / cmd_ingest_drop / cmd_diff / cmd_status / cmd_self_test
└── main(argv)
```

Contraintes de style (conventions du dépôt, vérifiées sur les modules
existants) : stdlib uniquement, `self-test` sans réseau, logs une-ligne sur
stderr, stdout réservé aux sorties machine, `--dry-run` là où il y a un
effet de bord.

## 5 · Découpage en tâches (ordre d'implémentation)

| # | Tâche | Est. | Sortie vérifiable |
|---|---|---|---|
| 1 | `_flatten` + `diff` purs + self-test (fixtures §6) | 0,5 j | 12+ assertions vertes |
| 2 | `snapshot_write` + `sync_state.json` + `validate` | 0,5 j | refus export tronqué testé |
| 3 | Mode drop-folder complet (`ingest-drop`) | 0,5 j | boucle possible dès ici, sans API |
| 4 | `prefilter.py --delta` (+ self-test étendu) | 0,5 j | assertion delta + header initial |
| 5 | `fetch_api` (redirects, backoff, lots, normalisation) | 1 j | pull réel sur le graphe du propriétaire |
| 6 | `status`, README_sync.md, intégration régression | 0,5 j | commande régression verte |
| 7 | Test d'intégration manuel (édition d'un bloc, re-pull) | 0,5 j | M2 démontré |

**L'ordre est un choix de dé-risquage** : les tâches 1–4 donnent une boucle
utilisable en mode drop-folder AVANT de toucher à l'API (le risque n°1 du
PRD). Si l'API backend se révèle inutilisable, B1 livre quand même.

## 6 · Fixtures de self-test (à committer dans `fixtures/sync/`)

1. `mini_a.json` : 2 pages, 6 blocs (dont 1 imbriqué niveau 3, 1 avec
   `((bref))`, 1 en NFD à normaliser).
2. `mini_b.json` : même graphe avec 1 bloc édité, 1 ajouté, 1 supprimé,
   1 déplacé inter-page, 1 déplacé + édité (→ 2 lignes).
3. `mini_truncated.json` : mini_a amputé de 50 % des blocs (test refus FR-3).
4. `mini_dup_uid.json` : uid dupliqué (test erreur fatale FR-3).
5. Assertions : classement des 4 ops, ordre byte-stable (double run →
   `diff` identique), NFC, header initial, `removed+added` pour uid réutilisé.

## 7 · Questions ouvertes (à trancher avant/pendant le dev)

| Q | Options | Recommandation |
|---|---|---|
| Le plan Roam du propriétaire inclut-il l'API backend ? | oui / non | à vérifier jour 1 ; sinon tâche 5 différée, mode drop-only |
| Granularité du pull : `pull-many` dispo ? | oui / boucle pull | mesurer sur 30 pages au premier essai réel |
| Où tourne le cron nocturne ? | Mac du propriétaire (launchd) / autre machine | launchd, cohérent avec B4 |
| Le token read-only séparé est-il possible ? | oui / token unique | oui si l'UI Roam le permet ; sinon token unique documenté comme dette |

# Annexe technique B2 — `roam_writeback.py`

**Complète :** `PRD_B2_roam_writeback.md`. Contrats exacts, squelette,
découpage, fixtures. Le PRD prime en cas de conflit.

---

## 1 · Contrats amont vérifiés (ce que le consolidateur produit aujourd'hui)

Le write-back ne lit PAS directement les exports du consolidateur — il lit
`writeback_orders.jsonl` produit par B4. Mais pour concevoir les templates,
voici les formes sources exactes (vérifiées dans `ingest.clj`) :

- `accepted.jsonl` (l. ~261) :
  `{"judgment_id","jtype","label","context_hash","judge_id","judge_family"}`
- `edges.jsonl` (l. ~286) :
  `{"edge_id":"prop1->claim#supports","edge_type":"supports","from":"prop1","to":"claim"}`
- `stances.jsonl` (belief.py) : objet par nœud avec `node`, `label`
  (`in|out|undec`), `status` (`accepted-supported | accepted-undisputed |
  rejected | undecided`), `support{n,in_supporters,defeated_supporters,…}`,
  `attackers`, `qualifiers`, `basis_edges`, `computed_at`.
- Rapport SHACL (`shacl_lint.py lint --out report.json`) :
  `{"conforms","n_violations","n_warnings","results":[{"focusNode",
  "shape":"https://mnemosyne.dev/shapes#S1","severity","message","path"}]}`
  — 8 shapes S1–S8 ; S2 et S7 sont `Warning`, le reste `Violation`.

**Attention nommage** : `ingest.clj` normalise snake_case ↔ hyphens
(`py->clj-type` / `clj->py-type`). Les ordres de write-back sont côté Python :
tout est snake_case ; ne jamais laisser fuiter un `:edge-type` Clojure dans
un template.

## 2 · Registre des templates (v1, normatif)

Chaque `content.template` du fichier d'ordres correspond à un renderer pur
`fields -> list[str]` (première string = bloc parent, suivantes = enfants).

### `judgment_v1`
fields : `{src_uid, dst_uid, label, confidence, jtype, ctx, judge_id, cycle_date}`
```
[[M/J]] ((src_uid)) {label} ((dst_uid)) — conf {confidence:.2f}
  jtype:: {jtype}
  ctx:: {ctx}
  judge:: {judge_id}
  cycle:: [[{cycle_date}]]
```
Pour `continues` (directionnel child→parent) : libellé
`((child)) continues ((parent))` ; jamais d'inversion (CANONICAL_ORDER_ONLY).

### `flag_v1`
fields : `{shape_id, shape_name, focus_uid, severity, ctx, message}`
```
[[M/Flag]] {shape_id} {shape_name} — ((focus_uid))
  severity:: {severity}
  shape:: {shape_id}
  ctx:: {ctx}
  status:: open
```
`focusNode` arrive en `urn:mnemo:node:<uid>` — extraire l'uid ; si le focus
n'est pas un uid Roam (nœud synthétique), écrire le nom brut sans `((ref))`.

### `stance_v1`
fields : `{node_uid, old_status, new_status, n_supporters, ctx, cycle_date}`
```
[[M/Stance]] ((node_uid)) : {old_status} → {new_status}
  ctx:: {ctx}
  cycle:: [[{cycle_date}]]
```
Ne rendre QUE les diffs (B4 FR-5 n'envoie que les changements).

### `task_v1` — structure définie par B3 (annexe B3 §2) ; B2 se contente de
rendre les fields fournis.

### `digest_v1`
fields : `{cycle_date, n_judgments, n_flags, n_tasks, n_stances, notes[]}`
Un bloc unique `#[[M/Digest]]` sur la daily note + enfants ≤ 4 lignes.
`notes` porte les troncatures de budget et les rattrapages (cas limite 4).

## 3 · Transport Roam — fiche d'implémentation écriture

> Mêmes réserves de vérification que l'annexe B1 §2 (API jeune).

- Endpoint : `POST /api/graph/{graph}/write`, corps :
  `{"action":"create-block","location":{"parent-uid":"<uid>","order":"last"},
  "block":{"string":"…","uid":"<uid-optionnel>"}}`
  Actions utiles : `create-block`, `create-page`, `batch-actions`
  (`{"action":"batch-actions","actions":[…]}` — préférer des lots de ≤ 25).
- **Générer nos propres uids** (`[a-zA-Z0-9_-]{9}` aléatoires) à l'écriture
  et les consigner dans le ledger : c'est ce qui rend `verify` et la pose
  d'enfants (`status:: resolved`, rétractation FR-5) possibles sans
  re-query plein texte.
- Les attributs `x:: y` ne sont que des strings avec `::` — aucune API
  dédiée ; l'idempotence par query Roam se fait donc par recherche du
  `ctx:: sha256:…` (datalog `q` sur `:block/string` avec `clojure.string/
  includes?`). Coûteux → le **ledger local est le chemin rapide**, la query
  n'est que le filet anti-double-écriture après perte du ledger.
- Daily note : titre au format Roam `"July 4th, 2026"` — utilitaire
  `roam_date(d)` avec suffixes ordinaux (st/nd/rd/th), à tester (1st, 2nd,
  3rd, 4th, 11th–13th, 21st, 22nd, 23rd, 31st).

## 4 · Échappement (précise NFR « injection »)

Fonction unique `neutralize(s)` appliquée à tout contenu *cité* (jamais aux
squelettes de template) :
- `[[` → `[​[`, `((` → `(​(`, `::` → `:​:`, `{{` → `{​{`,
  `#[[` couvert par la règle `[[`. (Zero-width space : préserve la lecture,
  casse la syntaxe.)
- Tronquer à 1 800 chars par bloc (limite pratique Roam ~2 000).
- Self-test : fixture adversariale contenant les cinq motifs + un
  `{{[[TODO]]}}`.

## 5 · Ledger (`writeback_ledger.jsonl`)

```json
{"key":"sha256:…","kind":"judgment","block_uid":"aB9xK2mQ1",
 "page":"M/Journal","ts":"2026-07-04T02:14:00Z","cycle":"2026-07-04T0200Z",
 "status":"written|failed|verified"}
```
- Append-only ; relu en mémoire (dict par `key`) au démarrage.
- Reprise mi-fichier : un ordre dont la clé est `written|verified` est sauté.
- `verify` : pull des `block_uid` du cycle, comparaison du rendu → passe
  `verified` ou signale.

## 6 · Squelette du module

```
roam_writeback.py
├── TEMPLATES = {"judgment_v1": render_judgment, …}   # purs, testables
├── neutralize(s)                                     # §4
├── roam_date(date) -> "July 4th, 2026"
├── Ledger (load, has, record)                        # §5
├── Transport (write_batch, query_key, pull_blocks)   # injecté ; mock au self-test
├── plan(orders, ledger, allowlist, budget) -> [action]  # pur : tri par priorité
│                                                      # (task>flag>stance>judgment),
│                                                      # troncature, détection clé dupliquée
├── apply(plan, transport, ledger, dry_run)
├── cmd_apply / cmd_verify / cmd_self_test
└── main(argv)
```

`plan()` est pur et couvre à lui seul : idempotence, allowlist (`M/*` +
daily note du jour uniquement), budget/troncature, erreur fatale sur
« même clé, contenu différent » (cas limite 3). C'est là que vivent la
plupart des assertions.

## 7 · Découpage en tâches

| # | Tâche | Est. |
|---|---|---|
| 1 | Renderers + `neutralize` + `roam_date` + self-tests | 0,5 j |
| 2 | `plan()` pur (idempotence, allowlist, budget, conflits) + self-tests | 1 j |
| 3 | Ledger + reprise + `--dry-run` | 0,5 j |
| 4 | Transport réel (batch, backoff, uids générés) | 1 j |
| 5 | `verify` + rétractation FR-5 + quarantaine FR-4 | 0,5 j |
| 6 | Test d'intégration graphe jetable + revue UX propriétaire + README | 0,5 j |

## 8 · Fixtures de self-test (`fixtures/writeback/`)

1. `orders_nominal.jsonl` : 12 ordres (4 kinds + digest), 2 cycles.
2. `orders_dup_key.jsonl` : même clé deux fois, même contenu (→ 1 écriture)
   puis même clé contenu différent (→ erreur fatale).
3. `orders_hostile.jsonl` : contenus avec `[[`, `((`, `::`, `{{[[TODO]]}}`.
4. `orders_overbudget.jsonl` : 250 ordres → vérifier priorité et troncature
   signalée dans le digest.
5. `orders_bad_target.jsonl` : ordre visant `[[Scaffolding]]` → refus allowlist.
6. Scénario reprise : apply avec transport qui échoue à l'ordre 6/12,
   re-apply → exactement 6 écritures nouvelles.

## 9 · Questions ouvertes

| Q | Recommandation |
|---|---|
| Un seul token API read+write ou deux tokens ? | deux si possible (B1 read-only) ; sinon un, noté comme dette |
| `M/Journal` : une page unique qui grossit, ou `M/Journal/2026-07` mensuel ? | mensuel dès v0 — une page Roam de plusieurs milliers de blocs devient pénible ; l'allowlist accepte le préfixe `M/` |
| Faut-il `update-block` un jour ? | non en v0 (append-only strict) ; `status:: resolved` est un enfant, pas une édition |

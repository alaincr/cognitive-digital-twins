# Annexe technique B3 — `task_gen.py` + `task_harvest.py`

**Complète :** `PRD_B3_elaboration_surface.md`. Le PRD prime en cas de conflit.

---

## 1 · Contrats amont/aval vérifiés

### 1.1 Ce qui déclenche les tâches (sources exactes, par type)

| type | source vérifiée dans le code | forme |
|---|---|---|
| `elaborate` | événements du consolidateur : promotion d'une arête `opposes` vers un claim ayant des supporters IN (croiser `edges.jsonl` + `stances.jsonl`) ; seuil `summarize_now` (label `fire` promu) | `{"edge_id","edge_type":"opposes","from","to"}` + stance du `to` |
| `triage` | `daily-inbox-behavior` (zettel.clj, decay λ sur `:prop/activation` des fleeting) — en v0 batch : B4 émet un événement `triage.due` par note décayée | `{"event":"triage.due","uid","activation"}` |
| `bridge` | `bridge_seeds.jsonl` de B5, raffiné par `select-bridges` (BFS, zettel.clj) côté consolidateur | `{"a","b","score","model_rev"}` |
| `review` | `review_queue_<jtype>.md` de `anchor_label.py` — items order-inconsistent + T2 hard | markdown, cf. §1.3 |

### 1.2 Où vont les réponses (mécaniques existantes à réutiliser)

- `review` → **exactement** le format `review_resolved.jsonl` déjà consommé
  par `first_judge.sh` stage 4 : `{"jtype","fields","gold"}` ; le merge
  ajoute `provenance.source = "human"` et appende au
  `calset_<jtype>.jsonl`. **Réutiliser ce script de merge, ne pas le
  réécrire** (il est inline dans first_judge.sh l. ~78-96 ; l'extraire en
  fonction partagée est autorisé).
- `elaborate` → proposition au format `propositions.jsonl` de
  `propositionize.py` : `{"prop_id","text","unit_id","source_doc","locator",
  "stratum":"candidate","kind":"permanent", …}` + `:source/family :human`
  côté consolidateur (attribut DataScript existant, `zettel.clj`).
- `triage #promouvoir` → gate `permanent_worthy` avec label or humain :
  ligne calset `{"jtype":"permanent_worthy","fields":{…},"gold":"promote",
  "provenance":{"source":"human",…}}` + promotion de stratum côté B4.
- `bridge` → jugement humain : événement outbox de forme identique à
  `judgment.emitted` avec `judge_id: "human"`, `jtype` dédié
  `bridge_related`, labels `{related, unrelated}` (à enregistrer dans le
  registre via le même mécanisme `register()` que `zettel_prompts.py`).

### 1.3 Parsing de la review queue

`review_queue_<jtype>.md` est du markdown structuré (généré par
`anchor_label.py` l. ~170-177) : items `### i. \`jtype\` — raison`,
champs indentés, ligne `- [ ] human gold: ______`. **Décision v0 : ne PAS
faire répondre l'humain dans le markdown.** `task_gen` transforme chaque
item en tâche Roam `review` (fields embarqués dans l'ordre) ; la réponse
est un tag du label (ex. `#supports`) dans Roam. Le markdown reste un
artefact de calibration WP-0, pas une surface quotidienne.

## 2 · Format Roam des quatre types (complète PRD §4)

Rendus par B2 `task_v1` ; fields fournis par `task_gen` :

```
[[M/Task]] {question}
  task-type:: elaborate|triage|bridge|review
  task-id:: sha256:…
  status:: open
  due-hint:: [[{date+2j}]]
  refs:: ((uid-a)) ((uid-b))          ← sujets, pour les backlinks
  (enfant préformaté)  Réponse :
```

Spécificités :
- `triage` : la question cite le texte de la note (neutralisé, tronqué
  120 chars) + enfant listant les trois tags autorisés.
- `bridge` : question à deux `((refs))` + tags `#related` / `#unrelated`.
- `review` : la question rend les fields du candidat (mêmes clés que
  `REQUIRED_FIELDS[jtype]`) + enfant listant l'enum des labels du jtype
  (importer `judge_prompts.LABEL_DEFS`, ne pas copier les listes).
- `task-id = sha256(task_type + ctx_cause)` — la cause, pas le contenu :
  c'est ce qui garantit M3 (pas de doublon) et le non-re-déclenchement
  après expiration.

## 3 · Récolte : règles de détection (précise PRD FR-2)

Parcours du snapshot (`sync/snapshots/latest.json`, via
`roam_harvest.Graph` — réutiliser le parseur) :

1. Localiser les blocs contenant `[[M/Task]]` + extraire `task-id::` des
   enfants.
2. Réponse texte : premier descendant dont le string, après retrait du
   préfixe `Réponse :`, est non vide et ≠ `?` (cas limite 2).
3. Réponse choix : tags présents dans le bloc tâche OU ses descendants ;
   ensemble autorisé selon `task-type` ; deux tags contradictoires →
   `human.response.ambiguous` (cas limite 3).
4. Amendement : si `task-id` déjà récolté (ledger `harvest_ledger.jsonl` :
   `{"task_id","response_hash","ts"}`) et `response_hash` différent →
   `human.response.amended`.
5. Événement émis (contrat PRD FR-2) — ajouter `response_hash` au schéma
   pour l'amendement :

```json
{"event":"human.response","task_id":"sha256:…","task_type":"elaborate",
 "response_text":"…","choice":null,"response_hash":"sha256:…",
 "answered_ts":1783…,"provenance":{"source":"human"}}
```

## 4 · Anti-fatigue : implémentation (précise PRD FR-4)

- `stats --window 7d` calcule le taux depuis `harvest_ledger.jsonl` +
  les tâches générées (ledger `taskgen_ledger.jsonl`).
- La réduction de budget est un état persisté
  (`taskgen_state.json : {"budget_factor": 1.0|0.5, "since": …}`) —
  pas un recalcul à la volée ; remonte à 1.0 après 7 jours ≥ 50 %.
- Priorité `stakes × activation` : stakes = tier du jtype cause
  (T2=3, T1=2, T0=1, conventions `judges.clj`) ; activation =
  `:prop/activation` si disponible dans l'événement, sinon 1.0.

## 5 · Squelette des modules

```
task_gen.py
├── CAUSES = readers (edges+stances, triage.due, bridge_seeds, review_queue)
├── make_task(cause) -> order-fields (pur)
├── prioritize(tasks, budgets, state) -> kept, dropped   # pur ; logge dropped
├── cmd_generate / cmd_self_test

task_harvest.py
├── find_tasks(graph) -> [task-block]                    # via roam_harvest.Graph
├── detect_response(task) -> text|choice|ambiguous|none  # pur
├── emit_events(responses, ledger) -> outbox_human.jsonl
├── cmd_harvest / cmd_stats / cmd_self_test
```

## 6 · Découpage en tâches

| # | Tâche | Est. |
|---|---|---|
| 1 | `detect_response` pur + fixtures snapshot (répondu/ignoré/ambigu/amendé/supprimé) | 1 j |
| 2 | `make_task` × 4 types + `prioritize` + dédoublonnage par cause | 1 j |
| 3 | Ledgers + stats + anti-fatigue | 0,5 j |
| 4 | Bout-en-bout graphe jetable (generate → apply → réponse → pull → harvest) | 0,5 j |
| 5 | Co-conception templates avec le propriétaire (2 itérations prévues) + README | inclus DoD |

## 7 · Fixtures (`fixtures/tasks/`)

`snapshot_tasks.json` : mini-export contenant 8 tâches — 1 répondue texte,
1 répondue tag, 1 double-tag contradictoire, 1 vide, 1 « ? », 1 amendée
(2 versions via 2 snapshots), 1 répondue dans le bloc question (cas
limite 4), 1 supprimée (présente au ledger, absente du snapshot).
Assertions cumulées ≥ 15 (PRD).

## 8 · Questions ouvertes

| Q | Recommandation |
|---|---|
| Langue des questions | français (langue du propriétaire) ; les labels d'enum restent en anglais (cohérence calsets) |
| `bridge_related` : nouveau jtype au registre ? | oui, via `register()` dans un petit `human_prompts.py` — pas de juge automatique associé en v0, le jtype n'existe que pour typer l'événement |
| Réponse dans le bloc question (cas 4) | tolérer, mais le confirmer avec le propriétaire à la première itération de templates |

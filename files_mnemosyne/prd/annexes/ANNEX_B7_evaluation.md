# Annexe technique B7 — `eval_harness.py`

**Complète :** `PRD_B7_evaluation.md`. Le PRD prime en cas de conflit.

---

## 1 · Sources de données par métrique (vérifiées)

| Métrique | Artefacts persistés | Champs exacts |
|---|---|---|
| E1 santé du jugement | `judge_metrics.py report` JSON + `store/events.jsonl` | `by_type.<jtype>.{abstention_rate, emitted, label_distribution, mean_confidence, prediction_set_sizes, order_disagreements}` + verdict de gate (`HEALTHY` si 0.10 ≤ taux < 0.35, `SUSPICIOUS-LOW` < 0.10, `USABLE-EXPENSIVE` 0.35–0.60, `UNINFORMATIVE` ≥ 0.60, `N-TOO-SMALL` n < 50) ; accord ancre : croiser `accepted.jsonl` (échantillon ρ=0.05) et `anchor_outbox.jsonl` |
| E2 contradictions plantées | `edges.jsonl` (`edge_type: "opposes"`) + `lint.json` (shape S2 `UnsupportedClaim` — attention : S2 détecte l'absence de support, pas l'opposition ; le détecteur principal d'E2 est l'arête `opposes` promue) | `{edge_type, from, to}` ; fixtures `seeded_pairs.yaml` |
| E3 récupération | snapshot B1 (baseline lexicale), `store/embeddings.db` (kNN), `edges.jsonl` (voisinage 2 sauts) | cf. §3 |
| E4 stabilité des stances | `stance_diff.jsonl` de chaque cycle (B4 étape 6) + événements de rétraction | `{node, old_status, new_status}` ; churn = part des diffs dont la cause est `retracted`/re-jugement (croiser `caused_by`) |
| E5 boucle humaine | `task_harvest.py stats`, ledgers B3, `elaboration-coverage` (zettel.clj — exposée par B4 dans le rapport de cycle), calsets (`provenance.source == "human"`) | taux de réponse 7 j par type ; compte cumulé d'exemples humains |

Tout est fichier — l'exigence FR-1 (« lit uniquement des artefacts
persistés ») est satisfaite si B4 exporte bien `elaboration-coverage` dans
son rapport de cycle (une ligne JSON par train ; à ajouter à la liste des
sorties de B4, coût ~10 lignes de Clojure, la query existe déjà).

## 2 · Contradictions plantées (E2) — mécanique précise

- `seed-contradictions` écrit via **B2** (mêmes ordres `kind: judgment` ?
  non — `kind: seed`, nouvelle famille d'écriture *hors budget*, allowlist
  `M/Eval/*` uniquement) : 15 paires FR sur `[[M/Eval/Seeded]]`, chaque
  bloc portant `eval-seeded:: true`.
- Moitié RGPD (ex. « la base légale de X est le consentement » /
  « …l'intérêt légitime »), moitié thèse ; + 10 paires témoins non
  contradictoires (contrôle négatif). Fixture versionnée
  `fixtures/eval/seeded_pairs.yaml` :

```yaml
- id: seed-01
  kind: contradiction        # ou control
  a: "Le registre des traitements est obligatoire dès le premier salarié."
  b: "Le registre n'est obligatoire qu'au-delà de 250 salariés, sauf exceptions."
  domain: rgpd
```

- `check-seeded` : pour chaque paire, chercher (a) une arête promue
  `opposes` entre les deux uids (ou leurs propositions dérivées — suivre
  `prop_id` via `propositions.jsonl` si le propositionizer a tourné),
  (b) tout flag S2 sur l'un des blocs. Rapport : détectées / en attente
  (avec âge en cycles) / faux positifs sur les témoins.
- **Filtre anti-contamination** (FR-2) : `roam_harvest.py`, `prefilter.py`
  et B5 doivent exclure les blocs de pages `M/*` — l'exclusion `M/*`
  couvre `M/Eval/` gratuitement, MAIS il faut l'assertion : self-test de
  chaque harvester avec une fixture contenant un bloc `M/Eval/Seeded`.
  (Aujourd'hui `roam_harvest.py` et `prefilter.py` n'excluent PAS `M/*` —
  patch ≤ 10 lignes chacun, à livrer avec B7, listé dans le DoD.)

## 3 · E3 — les trois colonnes, définitions figées

`eval_questions.yaml` :

```yaml
- id: q-rgpd-03
  question: "Quelles bases légales avons-nous retenues pour la prospection B2B ?"
  gold_uids: ["aBc…", "dEf…"]
  domain: rgpd
  frozen: 2026-07-XX          # date de rédaction, AVANT inspection du graphe
```

- **(a) lexical (témoin figé)** : tokenisation minuscule + retrait
  ponctuation, score = |tokens(question) ∩ tokens(bloc)| / |tokens(question)|,
  top-20 blocs. Implémentation committée une fois, hashée dans le README —
  toute modification = nouvelle colonne, jamais une retouche.
- **(b) kNN** : `embed_index.py query --text <question>` top-20
  (préfixe `query:` cette fois — c'est le cas d'usage asymétrique d'e5).
- **(c) arêtes promues** : ensemble des blocs à ≤ 2 sauts d'un hit lexical
  top-5, en suivant uniquement les arêtes de `edges.jsonl` (+ `continues`).
  C'est la valeur *marginale* du graphe : (c) \ (a).
- Métrique par question : `couverture@20 = |gold ∩ atteints| / |gold|`,
  moyennée par domaine ; rapporter aussi la couverture d'union (a∪b∪c).

## 4 · `weekly_report.{md,json}` — gabarit

```
# Rapport hebdo — semaine du {date}
## ⚠ Alertes           ← seulement si seuil franchi, avec la décision associée
## E1 Jugement          taux, gate, accord ancre — par jtype × judge_id
## E2 Contradictions    détectées k/15, faux positifs j/10, âge médian
## E3 Récupération      tableau (a)(b)(c) + marginal, par domaine
## E4 Stances           changements, churn %, tendance
## E5 Boucle humaine    taux réponse par type, exemples :human cumulés, coverage par train
## Dettes               mode API actif, tâches expirées, flags ouverts, étapes sautées
## Tendances            sparklines 8 semaines (blocs Unicode ▁▂▃▅▇)
```

Le JSON miroir porte les valeurs brutes + `alerts[]` ; le digest B2 du
lundi reprend `alerts[]` (contrat : `kind: digest`, champ `notes`).
Chaque seuil et sa décision (PRD §3, DoD) vivent dans `eval_thresholds.yaml`
— pas en dur dans le code.

## 5 · Squelette du module

```
eval_harness.py
├── readers/ (events, metrics-json, stance_diffs, ledgers, calsets)  # purs
├── e1() e2() e3() e4() e5() -> dict                                 # purs
├── trends(history_dir, current) -> sparklines + deltas
├── render_md(report) / write_json(report)
├── cmd_report / cmd_seed_contradictions / cmd_check_seeded
├── cmd_retrieval / cmd_self_test
```

## 6 · Découpage en tâches

| # | Tâche | Est. |
|---|---|---|
| 1 | Readers + E1/E4/E5 + self-test (fixtures 3 semaines synthétiques) | 1 j |
| 2 | E2 : seed/check + patchs d'exclusion `M/*` (harvest, prefilter, B5) + assertions | 0,5 j |
| 3 | E3 : baseline lexicale figée + 3 colonnes + `eval_questions.yaml` avec le propriétaire (½ j de session) | 1 j |
| 4 | Rapport md/json + tendances + alertes → digest + README (seuil ⇒ décision) | 0,5 j |

## 7 · Questions ouvertes

| Q | Recommandation |
|---|---|
| Les 15 questions E3 : qui les écrit ? | le propriétaire seul, AVANT toute inspection du graphe (règle anti-« benchmark trop facile » du PRD) ; le dev fournit le gabarit YAML vide |
| E2 : planter dans le graphe réel ou un sous-graphe ? | graphe réel, page `M/Eval/Seeded` dédiée — c'est le pipeline réel qu'on teste ; l'exclusion des calsets rend la contamination contrôlée |
| Cadence du rapport | lundi 06:00, tâche launchd distincte du cycle nocturne (dépend des artefacts, pas du cycle du jour) |

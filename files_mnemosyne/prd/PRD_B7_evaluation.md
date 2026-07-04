# PRD B7 — Harnais d'évaluation de tâche finale (`eval_harness.py`)

**Brique :** G7 de `00_gap_analysis.md`. **Priorité :** P1 (après la première
boucle fermée — mais spécifié dès maintenant pour que les autres briques
émettent les compteurs nécessaires). **Estimation :** 2–3 jours-dev.
**Profil :** dev Python ; une demi-journée avec le propriétaire pour le
benchmark de questions.

---

## 1 · Contexte et problème

Le projet mesure déjà **le juge** (`judge_metrics.py` : abstention,
distribution des labels, couverture conforme) mais rien ne mesure **le
système** : aucune définition opérationnelle de « le substrat vaut mieux
qu'un dossier de fichiers markdown », donc aucun moyen de savoir si
l'architecture s'améliore — ce qui est pourtant sa thèse centrale. Sans B7,
« auto-amélioration » restera une affirmation, et il n'existe aucun critère
d'arrêt rationnel (ni pour continuer, ni pour pivoter).

B7 est volontairement modeste : pas de « théorie de l'évaluation » générale,
cinq métriques concrètes et un rapport hebdomadaire.

## 2 · Objectif et métriques de succès du harnais lui-même

- **O1** : un rapport hebdomadaire auto-généré (`weekly_report.md`, écrit
  aussi dans `[[M/Journal]]` via B2) avec les 5 métriques, leurs tendances,
  et les dettes actives (mode API, tâches expirées, flags ouverts).
- **O2** : chaque métrique est recalculable depuis les artefacts persistés
  (journal d'événements, ledgers, snapshots) — pas de compteur volatile.
- **M1** : 4 rapports hebdomadaires consécutifs produits sans intervention.

## 3 · Les cinq métriques (normatif)

### E1 · Santé du jugement (déjà quasi disponible)
Taux d'abstention, volume jugé/promu, taux d'accord ancre (échantillonnage ρ),
par jtype et par version de juge. Source : `judge_metrics.py` + le journal.
**Seuils d'alerte** : abstention > 60 % (juge inutile — recalibrer ou changer
de modèle) ; accord ancre en baisse 2 semaines de suite (dérive).

### E2 · Précision de détection de contradictions (contrôle positif planté)
Le harnais maintient un **jeu de contradictions plantées** : ~15 paires de
blocs contradictoires insérées dans une page dédiée `[[M/Eval/Seeded]]` du
graphe (créées une fois, versionnées en fixture). Métrique : combien sont
détectées (arête `opposes` promue ou flag S2) en ≤ N cycles, et combien de
fausses contradictions sont promues sur un lot témoin non contradictoire.
C'est le contrôle positif/négatif du pipeline entier (harvest → juge →
consolidateur), pas seulement du juge.

### E3 · Temps-jusqu'à-réponse-citée (le benchmark propriétaire)
Un fichier `eval_questions.yaml` de 15–25 questions réelles du propriétaire
(RGPD et thèse), chacune avec les uids des blocs qui devraient fonder la
réponse (gold ancré dans le graphe). Métrique v0 (sans RLM) : **couverture de
récupération** — les blocs gold sont-ils atteignables via (a) recherche
lexicale simple, (b) kNN B5, (c) les arêtes promues (voisinage 2 sauts d'un
bloc de la question) ? Rapporter les trois colonnes : c'est la valeur ajoutée
*marginale* du graphe promu par rapport au dossier de fichiers — la
comparaison honnête demandée. (La version avec génération de réponse arrive
avec le driver compose, hors boucle réduite.)

### E4 · Stabilité des stances
Nombre de claims changeant de statut par cycle (`stance_diff` de B4/FR-5),
décomposé en : changements causés par nouvelle évidence (sain) vs par
rétraction/re-jugement (churn). **Seuil d'alerte** : churn > 20 % des
changements sur 2 semaines (le système défait son propre travail).

### E5 · Couverture d'élaboration et engagement humain
`elaboration-coverage` par train (déjà spécifié, addendum §6.4) + taux de
réponse aux tâches (stats B3) + nombre d'exemples `:source/family :human`
accumulés (le carburant de la distillation future). C'est la métrique de la
boucle humaine — si elle s'effondre, tout le reste est du bruit.

## 4 · Exigences fonctionnelles

- **FR-1** : `eval_harness.py report --week …` lit uniquement des artefacts
  persistés (journal, ledgers, `stances*.jsonl`, stats B3, sorties
  `judge_metrics.py`) ; sortie markdown + JSON (`weekly_report.{md,json}`),
  historisée dans `eval/history/`.
- **FR-2** : `eval_harness.py seed-contradictions` (une fois) et
  `check-seeded` (chaque semaine) pour E2 ; les blocs plantés sont exclus des
  calsets et de la distillation (tag `eval-seeded::` filtré partout — à
  vérifier par assertion dans les harvesters).
- **FR-3** : `eval_harness.py retrieval --questions eval_questions.yaml` pour
  E3 ; la recherche lexicale de référence est figée (pas d'amélioration
  opportuniste du baseline : c'est le témoin).
- **FR-4** : tendances : chaque métrique avec valeur, delta vs semaine
  précédente, sparkline texte sur 8 semaines ; les seuils d'alerte franchis
  apparaissent en tête du rapport ET dans le digest B2.
- **FR-5** : `self-test` sur fixtures complètes (journaux synthétiques de 3
  semaines) ; ≥ 12 assertions.

## 5 · Non-objectifs

- Évaluation de la qualité des réponses générées (pas de génération en v0).
- A/B testing, statistiques inférentielles : des compteurs honnêtes et des
  tendances suffisent à ce stade.
- Dashboard web (le rapport markdown dans Roam est l'interface).

## 6 · Cas limites

1. Semaine sans cycle (panne, absence) → rapport quand même, sections « no
   data », les tendances sautent la semaine (pas d'interpolation).
2. Blocs gold d'E3 supprimés/réécrits par le propriétaire → `check` signale
   les questions orphelines, elles sortent du calcul (pas de faux échec).
3. Renommage de juge / recalibration → E1 segmente par `judge_id` ; jamais de
   moyenne trans-versions.

## 7 · Plan de test et DoD

- Self-test (FR-5) dans la régression programme.
- DoD : `eval_questions.yaml` rempli avec le propriétaire (≥ 15 questions
  ancrées) ; contradictions plantées en place et détectées/non-détectées
  rapportées une première fois ; 4 rapports hebdo consécutifs (M1) ; les
  seuils d'alerte documentés dans `README_eval.md` avec la décision associée
  à chacun (« si E1 > 60 % alors… ») — un seuil sans décision attachée est
  du décor.

## 8 · Risques

| Risque | Prob. | Mitigation |
|---|---|---|
| Métriques regardées mais jamais actionnées | haute | chaque seuil a sa décision écrite (DoD) ; alertes poussées dans le digest quotidien |
| Contamination des calsets par les blocs plantés | moyenne | filtre `eval-seeded::` avec assertion dans les harvesters (FR-2) |
| Benchmark E3 trop facile (questions choisies pour réussir) | moyenne | questions rédigées AVANT de regarder le graphe, moitié RGPD moitié thèse, gel du fichier |

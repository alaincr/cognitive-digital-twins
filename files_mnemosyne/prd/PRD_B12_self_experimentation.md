# PRD B12 — Auto-expérimentation : la configuration comme objet épistémique

**Brique :** extension phase 3 (exige ≥ 4 rapports hebdo B7 comme baseline —
sans mesure de référence, rien n'est comparable). **Priorité :** P1 phase 3 ;
c'est l'opérationnalisation littérale de la thèse de tête (« comment une
architecture auto-référentielle étudie et améliore ses propres
composants ? ») et du principe 5 de CLAUDE.md (« the system is the
experiment »). **Estimation :** 2 j-dev (harnais replay-compare v0) +
0,5 j par expérience. **Dépend de :** boucle réduite vivante, B7 (organe de
mesure), journal durable B4 (replay) ; réutilise le gate de promotion de
`distill_judge.py`. **Profil :** dev Python/Clojure avec goût pour la
méthodo expérimentale.

---

## 0 · Principes de conception (normatifs)

- **P1 · La politique est un fait, pas un réglage.** Toute valeur de
  configuration qui gouverne la cognition (α, budgets, k de panel, seuils,
  ordres de consolidation) est un objet versionné dont chaque changement
  est un événement du log avec une cause. La cause légitime d'un
  changement est une comparaison mesurée — pas une intuition en session.
- **P2 · Une seule vie, des ombres.** Il n'existe qu'UN consolidateur
  vivant (CALM non négociable). Toute variante s'exécute en *shadow lane* :
  replay sur un fork du log, zéro écriture Roam, zéro tâche humaine, spend
  métré à part. Le propriétaire ne vit jamais le bras B — donc zéro effet
  observateur sur l'humain de la boucle.
- **P3 · Pré-enregistrement ou rien.** Une expérience est un fichier
  committé AVANT de tourner (`experiments/EXP-NNN.md` : hypothèse, LA
  métrique primaire, durée minimale, n minimal, règle de décision). Une
  comparaison non enregistrée peut nourrir la curiosité ; elle ne peut
  jamais promouvoir une politique. (Peeking, sélection post-hoc et
  comparaisons multiples reçoivent le même remède que dans la science
  humaine.)
- **P4 · Pare-feu de Goodhart : métriques gelées.** La métrique primaire
  d'une expérience vient d'un ensemble de mesure GELÉ (hashé, comme la
  baseline lexicale E3 — toute modification = nouvelle colonne, jamais une
  retouche). Les métriques ultimes de holdout sont celles qu'aucun replay
  ne peut truquer : taux de réponse du propriétaire, jugements M4, issues
  de réconciliation B9. L'humain de la boucle est le test set
  in-goodhartable du système.
- **P5 · Frontière de ratification.** Deux classes de politiques, fixées
  par ADR : **auto-promotables** (seuils, budgets, ordres — l'échec est
  silencieusement sous-optimal) et **ratifiées-humain** (tout ce qui touche
  I1–I4, les surfaces humaines, ou la machinerie d'expérimentation
  elle-même). La récursion s'arrête là : *le gate de promotion ne
  s'expérimente pas lui-même*. Un système « auto-améliorant » honnête
  s'améliore à l'intérieur d'une constitution qu'il ne peut pas amender
  seul.
- **P6 · Le rollback est un replay.** Une promotion de politique est un
  événement (`policy.promoted {exp_id, from, to, evidence}`) ; revenir en
  arrière = rejouer sans lui. L'historique de configuration est requêtable
  comme n'importe quelle autre lignée — l'analogue exact de la
  rétractation de cohorte, appliqué au système lui-même.

## 1 · Contexte et problème

Les croyances du système sur le monde vivent sous discipline (calibration,
gates, enveloppes, rétractation). Ses croyances sur *lui-même* — α = 0,05,
budget = 5, seuil de friction = 5/7 j — sont des commentaires YAML choisis
au doigt mouillé, marqués « à tuner sur throughput observé », et jamais
revisités par rien. Deux propriétés rendent la correction quasi gratuite
ici : le **replay déterministe** (mêmes entrées + mêmes seeds = histoire
contrefactuelle EXACTE, pas une simulation approchée) et les **jugements
content-addressed** (toute expérience sur une politique en AVAL du
jugement — promotion, panels, consolidation, génération de tâches, seuils
de stance — rejoue le flux de jugements déjà payé à coût d'inférence
nul).

## 2 · Objectif et métriques

- **O1** : toute valeur de politique active est traçable à son événement
  de promotion (ou à `policy.initial`, l'état pré-B12 consigné une fois).
- **O2** : le harnais replay-compare produit, pour deux politiques et une
  fenêtre d'historique, des métriques B7 appariées avec verdicts
  d'honnêteté (`N-TOO-SMALL` hérité de E1).
- **M1** : 100 % des promotions référencent une EXP pré-enregistrée dont
  la règle de décision est satisfaite (assertion du gate, pas une cible).
- **M2** : zéro écriture Roam / tâche humaine / spend ancre non métré
  émis par une shadow lane (P2 — assertion de self-test).
- **M3** : rapport trimestriel « policy diff » : chaque changement du
  trimestre + sa chaîne d'évidence — généré par fold, relu par le
  propriétaire.
- **M4** : ≥ 1 expérience réelle conclue (promotion OU rejet consigné)
  dans les 2 mois suivant la mise en service — la machinerie qui ne
  tourne pas est de la dette, pas de la science.

## 3 · Périmètre

### v0 — la classe replay-offline uniquement
Expériences ne changeant PAS ce qui est jugé : k de panel T2, règles de
promotion, ordres, seuils de stance, budgets/priorités de `task_gen`
(rejoués contre l'historique des causes), politiques de writeback (à
blanc). Coût d'inférence : zéro.

### v1 — la classe à inférence
Expériences changeant ce qui est jugé (budgets préfiltre, mineurs de
candidats, α de calibration). Coût réel, borné par le ledger B6 ; partage
des hits de cache sur les candidats communs.

### Non-objectifs
- Plans factoriels / expériences concurrentes sur sous-systèmes couplés
  (v0 : UNE expérience active par sous-système).
- Auto-modification du harnais, du gate, ou des classes P5 (frontière
  constitutionnelle).
- Optimisation continue type bandit — v0 est de l'A/B discret,
  pré-enregistré, à durée fixe. (Un bandit sur les politiques est une
  décision de phase 4 qui exigerait son propre ADR — le pré-enregistrement
  P3 et l'exploration continue sont en tension réelle.)
- Expériences sur B9 (les sondes du propriétaire) — mesurer l'humain et
  expérimenter sur la façon de le mesurer en même temps confond tout ;
  gel explicite.

## 4 · Mécanique normative

### 4.1 Registre de politiques
`policy_registry.jsonl` (append-only, dans le repo) : une ligne par
valeur active `{key, value, since_event, exp_id|"initial"}`. Le YAML
runtime est GÉNÉRÉ depuis le registre (le registre est la vérité, le YAML
la projection — même inversion que B11).

### 4.2 Cycle de vie d'une expérience
```
experiments/EXP-NNN.md committé (P3)          ← gate d'entrée
  → shadow lane : fork + replay fenêtre W sous politique B
  → mesure : B7 gelé sur les deux lanes, appariement par cycle
  → décision : règle pré-enregistrée (ex. McNemar p<0,05 ET effet ≥ seuil)
  → issue : policy.promoted | policy.rejected — les DEUX sont des
    événements consignés (un rejet est un résultat, pas un échec)
```
Le harnais réutilise : `fork`/`project` (core), `run-once-in!`
(test_runner — déjà un harnais de replay hermétique à 80 %), le pattern
gate/shadow/McNemar de `distill_judge.py`.

### 4.3 Générateur d'hypothèses (entrée, pas automatisme)
Les candidats d'expérience viennent des organes existants : frictions
récurrentes (Auto-Research), cellules faibles des rapports B7, carte de
fragilité (dreamer, si présent). Un candidat devient une EXP par décision
humaine en v0 (l'auto-proposition d'EXP est ratifiée-humain par P5 tant
que la confiance n'est pas établie).

## 5 · Exigences fonctionnelles

- **FR-1** `experiment.py run --exp EXP-NNN` : parse le fichier
  d'expérience, exécute la shadow lane (v0 : replay offline), produit
  `experiments/EXP-NNN.result.json` (métriques appariées + verdict de la
  règle). Déterministe à historique égal.
- **FR-2** Gate de promotion : `experiment.py promote --exp EXP-NNN`
  refuse si (a) EXP non committée avant le run (hash du fichier dans le
  résultat), (b) règle non satisfaite, (c) classe ratifiée-humain sans
  flag de ratification. Émet `policy.promoted` + régénère le YAML (§4.1).
- **FR-3** Isolation shadow : la lane écrit exclusivement sous
  `experiments/lanes/<exp>/` ; assertion M2 dans le self-test (aucun
  chemin ops/, sync/, ni transport).
- **FR-4** Métriques gelées : `eval_frozen/` — copie hashée des readers
  B7 utilisés comme métrique primaire ; le hash est dans chaque résultat ;
  toute divergence = résultat invalide.
- **FR-5** Rapports : section « expériences » dans l'hebdo B7 (EXP
  actives, verdicts récents) + le policy diff trimestriel M3.
- **FR-6** `policy.initial` : consignation unique de TOUTES les valeurs
  actuelles avec `exp_id: "initial"` — l'état zéro auditable.

## 6 · Cas limites

1. L'historique rejoué contient des événements issus d'une politique déjà
   promue en cours de fenêtre → la fenêtre d'une EXP ne chevauche jamais
   une promotion (le registre 4.1 rend le découpage calculable) ; sinon
   fenêtre tronquée + signalé.
2. Deux EXP visent le même sous-système → la seconde est refusée à
   l'enregistrement (v0 : un lock par sous-système, fichier dans
   experiments/).
3. La règle de décision est satisfaite mais l'effet est porté par un seul
   cycle aberrant → la règle pré-enregistrée DOIT inclure un critère de
   robustesse (ex. médiane des cycles, pas la moyenne) — gabarit d'EXP
   fourni avec des règles types ; le gate ne valide pas une règle absente
   du gabarit sans revue.
4. Une métrique gelée se révèle boguée → l'EXP est invalidée (pas
   « corrigée ») ; le fix crée `eval_frozen/v2` (nouvelle colonne, jamais
   une retouche — P4) ; les EXP passées restent interprétables contre v1.
5. Le propriétaire veut annuler une promotion ancienne sous laquelle
   d'autres promotions ont eu lieu → P6 : replay sans l'événement, MAIS
   les promotions postérieures du même sous-système sont re-testées
   (leurs évidences supposaient l'état intermédiaire) — le rapport de
   rollback liste ce qui doit être rejoué.

## 7 · Plan de test et DoD

- Self-tests : FR-1 déterminisme (double run = résultats identiques),
  FR-2 les trois refus du gate, FR-3 isolation (M2), FR-4 invalidation
  sur hash divergent, FR-6 état zéro.
- Intégration : une EXP synthétique complète sur fixtures (politique B
  trivialement meilleure plantée) → promotion ; puis rollback P6 →
  état antérieur vérifié par state-hash.
- **DoD** : `policy.initial` consigné ; EXP-001 réelle (suggestion :
  « panel k=2 vs k=1 pour la promotion T2 sur 4 semaines d'historique —
  métrique primaire : accord ancre des jugements promus (E1), gelée »)
  conclue avec verdict consigné ; policy diff trimestriel généré une
  fois ; README_experiments.md (P1–P6 en tête + gabarit d'EXP).

## 8 · Risques

| Risque | Prob. | Mitigation |
|---|---|---|
| R1 — Goodhart : le système évolue vers ses métriques | haute (à terme) | P4 (gelées + holdout humain) ; M3 relu par le propriétaire ; le bandit continu est exclu du périmètre |
| R2 — n minuscule : un graphe, un humain, des semaines | certaine | verdicts N-TOO-SMALL ; biais assumé vers les expériences à grand effet attendu (α, moitiés de budget) ; un rejet consigné a de la valeur |
| R3 — Dérive composée de petites promotions toutes justifiées | moyenne | M3 (policy diff trimestriel) ; stress-test dreamer de la politique composée vs politique d'il y a un an (quand le dreamer existe) |
| R4 — La machinerie d'expérimentation devient un jouet (science-théâtre sans décision) | moyenne | M4 (une EXP conclue sous 2 mois) ; chaque EXP porte une décision pré-écrite — pas de « intéressant, à creuser » |
| R5 — Confusion des fenêtres replay avec l'état vivant | basse | FR-3 isolation + state-hash de la lane jamais journalisé dans store/ vivant |

## 9 · Phasage

```
phase 3 (post 4 hebdos B7)   policy.initial + harnais v0 + EXP-001 (offline)
+2 mois                       M4 : premier verdict consigné ; revue du gabarit
phase 3.x                     classe v1 (à inférence) ; auto-proposition
                              d'EXP par Auto-Research (reste ratifiée-humain)
phase 4 (ADR requis)          bandits / factoriel / expériences continues
```

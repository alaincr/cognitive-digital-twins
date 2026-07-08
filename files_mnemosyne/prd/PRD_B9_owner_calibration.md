# PRD B9 — Calibration du propriétaire : sondes de cohérence et mesure de dérive

**Brique :** extension phase 2 (hors périmètre de la boucle réduite ; voir
« Phasage » §9 — un livrable v0 minuscule DOIT cependant partir avec la
boucle). **Priorité :** P1 phase 2 ; P0 pour le seul FR-1 (le registre de
sondes, dont chaque semaine sans lui est une perte de données
irrécupérable). **Estimation :** 3–4 jours-dev + temps calendaire
incompressible (délais de re-présentation ≥ 90 j). **Dépend de :** boucle
réduite fermée (B1–B4 vivants, B3 en particulier) ; B7 pour la restitution.
**Profil :** dev Python ; ratification préalable d'un ADR par le
propriétaire (§8, R1).

---

## 1 · Contexte et problème

Le système traite les réponses du propriétaire comme or absolu
(`:source/family :human`, priorité maximale de distillation —
`zettel_addendum.md` §6, PRD B3 FR-3). Or le propriétaire est lui aussi un
juge : il a un bruit propre (sensibilité au phrasé, inconstance courte
durée), une dérive (ses positions bougent avec l'évidence — c'est le
fonctionnement normal), et personne ne mesure ni l'un ni l'autre. Le
système applique déjà cette discipline à l'ancre (`anchor_label.py
--double` : double passe, comparaison, file de revue) ; il ne l'applique
pas à la seule source de vérité qu'il ne peut pas remplacer.

**Sans B9 :** l'or humain est supposé infaillible ; les calsets héritent
silencieusement de l'inconstance du propriétaire ; une dérive de position
n'est jamais détectée, donc jamais consignée (`status:: superseded`), et
le graphe porte des ors contradictoires d'époques différentes sans le
savoir. C'est aussi la promesse nominale du projet — un jumeau *cognitif* —
qui reste vide : un jumeau qui ne connaît pas les barres d'erreur de son
original n'en est pas un.

## 2 · Objectif et métriques

- **O1** : le propriétaire est enregistré comme juge versionné
  (`judge_id: "owner@<periode>"`, ex. `owner@2026-H2`) dont la
  **cohérence propre** (accord avec soi-même) et la **dérive** (flips
  monotones) sont mesurées par jtype × domaine × délai.
- **O2** : la mesure n'altère jamais le comportement mesuré : les sondes
  sont indistinguables des tâches fraîches au moment de la présentation.
- **O3** : toute divergence détectée est **restituée, jamais résolue** par
  le système : le propriétaire reste la cour suprême ; le système est le
  greffier.
- **M1** : dès la mise en service du FR-1, 100 % des réponses récoltées
  produisent une entrée du registre de sondes (aucune réponse « perdue
  pour la calibration future »).
- **M2** : indistinguabilité — au DoD, le propriétaire, informé qu'il y a
  eu k sondes dans ses n dernières tâches, ne les identifie pas mieux que
  le hasard.
- **M3** : premier rapport de calibration émis après ≥ 20 sondes scorées ;
  chaque cellule du rapport avec n < 10 porte `N-TOO-SMALL` (même
  honnêteté que le gate E1).
- **M4** : zéro écriture du système qui tranche un désaccord : tout flip
  détecté génère au plus une tâche de réconciliation, dont la réponse
  humaine est le seul arbitrage.

## 3 · Périmètre

### v0 — trois saveurs de sonde
| saveur | mécanique | ce qu'elle isole |
|---|---|---|
| `repeat` | même question, mêmes fields, re-présentée ≥ 90 j après la réponse originale | dérive + bruit long terme |
| `paraphrase` | mêmes fields, question re-rendue sous un gabarit alternatif (`task_v2_alt`, versionné) | sensibilité au phrasé (l'équivalent humain de la randomisation d'ordre des labels des juges — I-« order disagreement ») |
| `adjacent` | *(phase 2.1, non-v0)* question dont la réponse est impliquée par une réponse passée via la couche de croyances | cohérence logique (vs mémoire) |

### Non-objectifs
- Aucun score « de performance » du propriétaire, aucun classement, aucune
  gamification (déjà exclu par PRD B3 ; réaffirmé ici où la tentation est
  maximale).
- Pas de résolution automatique des désaccords (M4).
- Pas d'accuracy contre un étalon externe : il n'y a pas d'or au-dessus du
  propriétaire ; on mesure cohérence et dérive, pas justesse.
- Pas de sonde sur les tâches `elaborate` en v0 (réponses libres —
  l'appariement sémantique de deux textes libres est un problème de
  jugement en soi ; v0 sonde les types à choix fermé : `triage`, `bridge`,
  `review`).

## 4 · Mécanique normative

### 4.1 Registre de sondes (`ops/probe_ledger.jsonl`) — le livrable jour-1
Écrit par `task_harvest` à chaque réponse récoltée (une ligne par réponse
« sondable plus tard ») :
```json
{"task_id": "sha256:…", "task_type": "review", "jtype": "edge_type",
 "route": {…}, "choice": "supports", "response_hash": "sha256:…",
 "answered_ts": "…", "owner_version": "owner@2026-H2",
 "domain": "rgpd|these", "probe_of": null}
```
`probe_of` est nul pour une réponse fraîche ; pour la réponse à une sonde,
il porte le `task_id` original — c'est la clé d'appariement du scoring.
Le registre est append-only ; il capitalise dès le premier jour de boucle
vivante, même si tout le reste de B9 arrive des mois après.

### 4.2 Injection (`task_gen`, nouvelle cause `probe`)
- Quota : les sondes REMPLACENT des tâches fraîches à l'intérieur du
  budget quotidien existant (jamais en plus — l'anti-fatigue B3 FR-4 prime) ;
  plafonds : ≤ 1 sonde/jour, ≤ 2/semaine, ≥ 90 j après la réponse originale.
- Sélection : tirage pseudo-aléatoire **seedé sur le contenu** (hash du
  task_id original + semaine), jamais sur l'horloge (SPEC-00 §3.4) ;
  stratifié par jtype × domaine pour que les cellules du rapport se
  remplissent uniformément.
- `task-id = sha256("probe|" + saveur + "|" + task_id_original)` — opaque
  dans Roam, déterministe, jamais dupliqué (même mécanique M3 de B3).
- **Indistinguabilité (O2)** : même gabarit `task_v1`, même page
  `[[M/Tasks]]`, mêmes attributs. La saveur `paraphrase` re-rend la
  question depuis les fields via un gabarit alternatif versionné, relu une
  fois par un humain AUTRE que le propriétaire si possible (sinon accepté
  comme dette). Aucun marqueur visible ; le registre sait, le propriétaire
  non (cadre consenti par l'ADR, §8 R1).

### 4.3 Scorage (`owner_calibration.py`, appelé par le cycle hebdo B7)
- Jointure pure `probe_ledger` : réponse-sonde ↔ réponse originale par
  `probe_of`. Aucun réseau, aucun LLM.
- Par cellule (jtype × domaine × saveur × tranche de délai) : taux
  d'accord + intervalle de Wilson ; n affiché ; `N-TOO-SMALL` si n < 10.
- **Direction des flips** : flips aller-retour (A→B→A sur trois passes) =
  bruit (« température » du propriétaire) ; flips monotones corroborés par
  l'arrivée d'évidence datée = dérive. La distinction utilise le log :
  `project` sur le préfixe d'événements à chaque date de réponse donne
  l'état épistémique disponible au moment de chaque réponse — le rapport
  peut donc souvent *expliquer* un flip (« 3 sources arrivées entre les
  deux réponses, dont une rétractée »).

### 4.4 Restitution et conséquences
- Section **E6** du rapport hebdo B7 : tableau des cellules + tendance ;
  langage contractuel : la dérive après évidence nouvelle est le système
  *qui fonctionne* ; seuls le bruit court-délai et la sensibilité au
  phrasé sont des limites de fiabilité.
- Flip détecté → au plus UNE tâche de réconciliation (« vos deux réponses
  divergent — laquelle tient ? », les deux réponses datées citées). La
  troisième réponse est l'or qui tient ; l'ancienne ligne de calset reçoit
  un marqueur de supersession dans la génération SUIVANTE du calset
  (jamais de mutation d'un calset gelé — FROZEN.sha256 est inviolable ;
  la supersession vit dans la version d'après).
- *(Phase 2.1, spécifiée ici, non-v0)* : pondération des calsets par la
  cohérence de la cellule (or dur ≥ 90 %, labels doux en dessous — entrée
  de `distill_judge.py`) ; routage double-passe par défaut des nouvelles
  questions dans les cellules < 70 %.

## 5 · Exigences fonctionnelles

- **FR-1 (jour-1, part avec la boucle)** : `task_harvest` écrit
  `probe_ledger.jsonl` (§4.1) pour toute réponse récoltée. ≤ 30 lignes de
  code, self-test étendu, aucune autre dépendance.
- **FR-2** : cause `probe` dans `task_gen` (§4.2) — quotas, seed contenu,
  stratification, indistinguabilité.
- **FR-3** : `owner_calibration.py score` (§4.3) — pur, self-testé sur
  fixtures synthétiques (3 mois de registre simulé).
- **FR-4** : section E6 dans `eval_harness.py` + tâche de réconciliation
  (via `task_gen`, cause `reconcile`, hors quota sonde, comptée dans le
  budget global).
- **FR-5** : versionnage du juge-propriétaire : `owner_version` roule par
  semestre (`owner@2026-H2`) ; les cellules ne mélangent jamais deux
  versions (même discipline que `judge_id` = modèle@poids#prompt).
- **FR-6** : CLI — `owner_calibration.py score|report|self-test` ;
  `task_gen.py generate --probes …` s'intègre au cycle sans nouveau stage.

## 6 · Cas limites

1. Le propriétaire reconnaît une sonde et le dit dans sa réponse → la
   réponse est scorée quand même mais marquée `recognized: true` (exclue
   des taux ; comptée pour M2).
2. La cause originale a été rétractée/supersédée entre-temps → sonde
   caduque, jamais émise (vérification au moment de l'injection, pas de
   la sélection).
3. Réponse ambiguë à une sonde (deux tags) → même traitement que B3 cas 3
   (`human.response.ambiguous`), la sonde est re-tirable après 30 j.
4. Le calset contenant l'or original est gelé → voir §4.4 : supersession
   dans la génération suivante, jamais de mutation.
5. Moins de matière sondable que le quota (petits débuts) → le quota
   s'écrase silencieusement à ce qui existe ; jamais de sonde < 90 j pour
   remplir.
6. La paraphrase altère le sens (biais du gabarit alternatif) → détectable
   par asymétrie systématique paraphrase-vs-repeat dans les cellules ;
   le rapport le signale ; le gabarit alternatif est versionné donc
   révocable par cohorte (même logique que I4).

## 7 · Plan de test et DoD

- Self-tests : FR-1 (registre écrit, `probe_of` correct), FR-2
  (déterminisme du tirage, quotas, indistinguabilité des ordres générés —
  assertion : diff des ordres sonde/frais = fields seulement), FR-3
  (fixtures 3 mois : cellules, Wilson, N-TOO-SMALL, flips bruit vs dérive
  avec évidence datée), FR-4 (E6 rend, tâche réconciliation émise une
  seule fois par flip).
- Test bout-en-bout sur graphe jetable : réponse → 90 j simulés (horloge
  injectée, `--today` existe déjà) → sonde émise → réponse → scoring →
  E6.
- **DoD produit** : ADR ratifié (§8 R1) ; FR-1 en production avec la
  boucle réduite ; après ≥ 20 sondes réelles scorées : premier rapport E6
  relu avec le propriétaire, test M2 effectué, et le propriétaire décide
  en connaissance si les conséquences phase 2.1 (pondération calsets)
  s'activent.

## 8 · Risques

| Risque | Prob. | Mitigation |
|---|---|---|
| R1 — Consentement : mesurer quelqu'un à son insu-dans-l'instant est le point éthiquement chargé du projet | certaine | **ADR dédié ratifié AVANT toute injection** : sondes couvertes par un consentement de principe (« je sais qu'il y en a, je ne sais pas lesquelles ») ; droit d'arrêt à tout moment ; le registre FR-1 seul ne sonde rien et peut partir sans ADR |
| R2 — Effet observateur : se savoir mesuré change les réponses | haute | indistinguabilité O2/M2 ; volumes minuscules (≤ 2/sem) ; rapport formulé « dérive ≠ erreur » |
| R3 — n minuscules pendant des mois → sur-interprétation | haute | Wilson + N-TOO-SMALL obligatoires ; aucune conséquence automatique (2.1) avant décision explicite du propriétaire au DoD |
| R4 — Le quota sonde cannibalise les tâches utiles | moyenne | remplacement intra-budget + plafonds ; l'anti-fatigue B3 prime toujours |
| R5 — Fuite du registre (données intimes : l'inconstance de quelqu'un) | moyenne | `probe_ledger` et rapports E6 restent locaux (jamais écrits vers Roam au-delà de la tâche de réconciliation) ; ajouter au `.gitignore` opérationnel |

## 9 · Phasage (rappel — la seule urgence est le registre)

```
maintenant        FR-1 seul : probe_ledger part AVEC la boucle réduite
                  (chaque semaine sans lui = données perdues à jamais)
boucle + 90 j     FR-2 : premières injections possibles
boucle + ~5 mois  FR-3/FR-4 : premier rapport E6 honnête (≥ 20 sondes)
ensuite           décision propriétaire : activer 2.1 (pondération, routage)
```

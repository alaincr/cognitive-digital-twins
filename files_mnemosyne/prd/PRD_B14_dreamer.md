# PRD B14 — Le dreamer : ensembles de croyances par ré-échantillonnage nocturne

**Brique :** extension phase 3 — l'infrastructure manquante partagée : B10
(ciblage), B11 (plancher de stabilité), B13 (canal left-field) et
l'upgrade d'E4 la référencent tous avec repli. Ce PRD ferme la toile de
dépendances. **Priorité :** P1 phase 3, en tête de file des extensions
(trois consommateurs déjà spécifiés). **Estimation :** 2–3 j-dev (v0,
K=500, Python seul). **Dépend de :** boucle réduite vivante, journal B4
(persistance des distributions), `belief.py` (le moteur de fold — pour une
fois, la redondance du miroir devient un atout : le miroir rêve, le
canonique veille). **Profil :** dev Python à l'aise avec le Monte-Carlo.

---

## 0 · Principes de conception (normatifs)

- **P1 · Les rêves informent ; seul le consolidateur décide.** Le dreamer
  est un calcul pur, monotone, jetable, sur des forks. RIEN de ce qu'un
  rêve calcule n'est promu. Si une découverte de fragilité doit changer le
  graphe, elle passe par la porte normale : ligne d'escalade ou tâche
  humaine, vers le writer unique. Le split CALM est intact par
  construction — les forks ne peuvent pas écrire.
- **P2 · On échantillonne le mesuré, jamais l'inventé.** Les distributions
  ré-échantillonnées sont les logprobs calibrés que le gate conforme a
  déjà inspectés (I3). Le dreamer n'ajoute aucune incertitude de son cru ;
  il cesse d'en jeter.
- **P3 · Hiérarchique avant indépendant.** L'échantillonnage naïf traite
  les jugements comme indépendants ; ils ne le sont pas (les biais par
  famille de juge sont LA prémisse de la rétractation de cohorte).
  L'indépendance sous-estime le risque de queue — le scénario « un juge
  systématiquement biaisé fausse cinquante arêtes d'un coup » est
  précisément celui que `retract-cohort!` existe pour réparer. Le sampler
  tire d'abord un terme de biais par (famille, jtype) et par monde, puis
  chaque jugement conditionné dessus. Symétrie voulue : la machinerie de
  rétractation définit l'unité de défaillance (la cohorte) ; le dreamer
  stress-teste exactement cette unité. Le monde n°4 411 où les `edge_type`
  d'un juge penchent 15 % vers `opposes` EST la pré-figuration d'une
  rétractation de cohorte future.
- **P4 · Chaque monde est reproductible.** Seed du monde k =
  `sha256(state_hash_du_soir + k)` — jamais l'horloge (SPEC-00 §3.4).
  Deux exécutions du même soir produisent les mêmes 500 mondes,
  byte-identiques.
- **P5 · La stabilité est un avis, jamais un gate.** Les scores de
  stabilité annotent, priorisent, amortissent (B10/B11/B13) — ils ne
  surchargent JAMAIS le gate conforme, qui reste l'unique arbitre de ce
  qui s'émet. Un consommateur qui transforme la stabilité en seuil de
  promotion viole ce PRD.
- **P6 · Le dreamer se calibre lui-même.** Une probabilité de flip est une
  prédiction ; les cycles suivants la réalisent ou non. La validation
  long-cours (stabilité prédite vs flips réalisés, E4) est une exigence,
  pas un bonus — un dreamer non calibré est un générateur d'anxiété, pas
  un instrument.

## 1 · Contexte et problème

Chaque jugement naît distribution (logprobs calibrés sur un vocabulaire
fermé) ; le gate en garde l'argmax et jette le reste. `edges.jsonl` dit
`supports`, point — alors que le juge savait « supports 0,71 / refines
0,24 / opposes 0,05 ». La couche de croyances calcule ensuite des stances
sur ces labels aplatis comme s'ils étaient certains. Toute la structure de
confiance aval est perdue au moment de la promotion.

**Sans B14 :** deux stances `accepted` — l'une tenant dans 96 % des mondes,
l'autre dans 54 % — sont indistinguables ; B10 cible à l'aveugle (repli
centralité seule) ; B11 affirme des claims oscillants ; E4 constate le
churn après coup au lieu de le prédire ; l'économie d'escalade reste
pilotée par l'incertitude du juge sur UNE question, jamais par la
sensibilité du graphe à UNE réponse.

## 2 · Objectif et métriques

- **O1** : chaque nuit, chaque nœud à stance porte une distribution de
  stance (`p_in / p_out / p_undec`) estimée sur K mondes, plus ses
  **jugements pivots** (ceux dont le flip flippe la stance).
- **O2** : les trois consommateurs spécifiés (B10 §4.1, B11 §4.1, B13
  §4.6) lisent `sim/stability.jsonl` sans changement de code (leurs replis
  s'inversent).
- **M1 (déterminisme)** : re-run du même soir ⇒ `stability.jsonl`
  byte-identique (P4) — assertion de self-test.
- **M2 (calibration du dreamer, P6)** : sur fenêtre glissante ≥ 8
  semaines, courbe fiabilité prédite/réalisée : parmi les nœuds à
  stabilité 0,9 ± 0,05, la part observée de flips E4 doit être ≈ 10 %
  (tolérance ±) — rapportée dans l'hebdo B7 (section E8) avec
  `N-TOO-SMALL` le temps qu'il faudra.
- **M3 (utilité)** : part du budget d'escalade/attaque effectivement
  réordonnée par `stabilité × centralité` vs centralité seule — mesurable
  dès que B10 consomme.
- **M4 (isolation)** : zéro écriture hors `sim/` ; zéro événement journalisé
  par le dreamer (P1) — assertions de self-test.

## 3 · Périmètre

### v0
- Persistance des distributions dans l'outbox (champ additif — règle de
  changement INTERFACES §4.2 : un champ s'ajoute librement).
- `dreamer.py` : K=500 mondes, ré-échantillonnage des labels d'arêtes
  depuis la distribution du jugement promoteur, fold `belief.py` par
  monde, agrégation.
- Échantillonnage **indépendant ET hiérarchique** (P3) — les deux modes,
  comparés dans la sortie ; l'hiérarchique est le mode par défaut des
  consommateurs.
- Pivots par corrélation échantillon (influence de chaque jugement sur
  chaque stance à travers les mondes).

### v0 — approximation assumée (documentée, pas cachée)
Le v0 ré-échantillonne le label de l'ARÊTE promue depuis la distribution
de son jugement promoteur ; il ne rejoue PAS la logique de promotion
(panels T2, ancre) par monde. C'est une approximation : un panel k-de-n
re-tiré pourrait ne pas promouvoir du tout. Le v1 (replay de promotion
par monde, machinerie B12 réutilisée) lève l'approximation ; l'écart
v0/v1 sur fixtures est lui-même une mesure à consigner.

### Non-objectifs
- Toute écriture vers Roam (les stats de mondes atteignent le propriétaire
  via les consommateurs : `stability::` du template stance_v1 — un champ
  ajouté côté B4/B2 —, le canal left-field B13, le rapport hebdo).
- Rêver les stances du propriétaire (B9 mesure l'humain ; on ne
  Monte-Carlo pas quelqu'un — frontière de goût autant que de méthode,
  révisable par ADR si un jour le besoin est argumenté).
- GPU, parallélisme distribué — 500 × un fold de quelques milliers
  d'arêtes = millisecondes par monde ; le Mac du propriétaire suffit très
  au-delà de K=10 000.

## 4 · Mécanique normative

### 4.1 Persistance des distributions
`judgment.emitted` gagne `label_distribution: {label: p, …}` (calibré,
post-température). Rétro-compatibilité : jugements antérieurs sans champ
⇒ masse ponctuelle sur le label émis (le passé est certain faute de
mieux — documenté).

### 4.2 Génération des mondes
```
pour k dans 0..K-1 :
  seed_k = sha256(state_hash_soir + ":" + k)
  si hiérarchique : tirer biais_(famille,jtype) ~ prior (Dirichlet doux)
  pour chaque arête promue : label_k ~ distribution(jugement promoteur | biais)
  stances_k = belief.fold(arêtes_k)          # belief.py, en mémoire
```
Priors de biais v0 : concentration fixe documentée dans le README ;
l'estimation empirique des biais réels (depuis l'accord ancre E1) est un
raffinement v1.

### 4.3 Agrégation → `sim/stability.jsonl`
```json
{"node": "...", "p_in": 0.94, "p_out": 0.04, "p_undec": 0.02,
 "n_worlds": 500, "mode": "hierarchical",
 "pivotal": [{"judgment_id": "...", "influence": 0.41}, ...],
 "expected_flips_next": 0.06, "seed_base": "sha256:...", "computed_at": "..."}
```
+ une ligne méta en tête (K, modes, durée, écart indépendant/hiérarchique
agrégé). Les nœuds proches de 0,5 alimentent la section « expected churn »
de l'hebdo (E8) : « ces 4 claims sont à un jugement de basculer ».

### 4.4 Consommation (contrats existants, replis inversés)
| consommateur | usage | changement de code |
|---|---|---|
| B10 ciblage | `enjeu = stabilité × centralité` | zéro (repli spécifié) |
| B11 squelette | plancher de stabilité | zéro (repli spécifié) |
| B13 left-field | « tient dans 61 % des mondes » | zéro (source listée) |
| E4/E8 hebdo | churn attendu vs réalisé (M2) | section nouvelle |
| escalade | pivots à influence haute + stance serrée → candidats d'escalade proposés (via task_causes, cause `fragility`) — v1, PAS v0 (P1 : proposer oui, promouvoir jamais) | v1 |

## 5 · Exigences fonctionnelles

- **FR-1** persistance 4.1 : patch `judge_harness` (émission) +
  INTERFACES (champ additif) + tolérance des lecteurs asserté.
- **FR-2** `dreamer.py dream --k 500 --mode both` : 4.2/4.3 ; pur après
  lecture des entrées ; mock-fold au self-test ; M1 asserté.
- **FR-3** pivots par corrélation : self-test sur fixture plantée (un
  jugement construit pour être pivot ⇒ influence maximale détectée).
- **FR-4** intégration cycle : étape post-belief (dépend de 6, rien ne
  dépend d'elle — une feuille, comme B11) ; échec = cycle intact.
- **FR-5** E8 dans l'hebdo B7 : stabilités extrêmes, expected churn, et la
  courbe de calibration M2 dès que n suffit.
- **FR-6** `stability::` dans stance_v1 (producteur B4 + renderer B2,
  même commit, INTERFACES mis à jour).

## 6 · Cas limites

1. Jugement pré-B14 sans distribution → masse ponctuelle (4.1) ; la part
   de masse-ponctuelle du graphe est affichée dans la ligne méta (un
   graphe à 90 % ponctuel produit des stabilités trompeusement hautes —
   le consommateur doit le voir).
2. Arête promue par l'ancre (JSON contraint, pas de logprobs) →
   distribution de l'ancre ≈ ponctuelle assumée ; marqué `anchor: true`
   dans les pivots (une « certitude » d'ancre pivot est un signal
   d'escalade humaine, pas de re-jugement).
3. Nœud sans aucune arête entrante rêvable → stabilité 1,0 par vacuité,
   marqué `vacuous: true` (à distinguer de la robustesse réelle — B10 ne
   doit pas croire qu'un claim isolé est « stable »).
4. K insuffisant pour les pivots (influences bruitées) → intervalle par
   bootstrap sur les mondes ; influence sans IC exclue de la sortie.
5. Le fold diverge entre belief.py et belief.clj (miroirs) → hors
   périmètre B14 mais détecté gratuitement : le dreamer fold-e en Python
   le graphe que le Clojure a produit — tout écart systématique entre la
   stance vécue et la stance re-fold-ée à distribution ponctuelle est
   ALARMÉ (c'est le test de miroir V1–V15 qui tourne enfin en continu).

## 7 · Plan de test et DoD

- Self-tests : M1 (double run byte-identique), M4 (isolation), FR-3
  (pivot planté), cas 1/3 (méta ponctuelle, vacuité), écart
  indépendant/hiérarchique non nul sur fixture à biais planté (P3
  démontré : l'hiérarchique DOIT montrer plus de queue).
- Intégration : 3 nuits fixtures → stability.jsonl cohérent avec les
  goldens de stance ; consommateur B11-squelette lu sans erreur.
- **DoD** : le dreamer tourne en production depuis 2 semaines ; E8
  publié ; `stability::` visible dans Roam sur les stances écrites ;
  la ligne méta montre la part ponctuelle en décroissance ; M2 consigné
  « en attente de n » avec la mécanique en place.

## 8 · Risques

| Risque | Prob. | Mitigation |
|---|---|---|
| R1 — Générateur d'anxiété : des stabilités non calibrées font douter de tout | moyenne | P6/M2 (le dreamer se calibre) ; langage E8 (« châteaux de cartes » ≠ « tout brûle ») ; stability:: arrondi grossier dans Roam (0,9 / 0,7 / 0,5 — pas de fausse précision) |
| R2 — L'approximation v0 (pas de replay de promotion) biaise les stabilités T2 | moyenne | documentée §3 ; écart v0/v1 mesuré sur fixtures ; T2 marqué `approx: true` dans la sortie |
| R3 — Les priors de biais hiérarchiques sont eux-mêmes des choix au doigt mouillé | certaine (v0) | concentration documentée + les DEUX modes livrés ; estimation empirique v1 depuis l'accord ancre ; candidat EXP B12 idéal |
| R4 — P5 érodé : un dev pressé fait de la stabilité un gate | moyenne | phrase normative P5 + revue des consommateurs dans chaque PR touchant stability.jsonl |
| R5 — Coût mémoire/temps à K ambitieux | basse | 500 × fold ms = secondes ; K est un paramètre, pas une architecture |

## 9 · Phasage

```
phase 3 (tôt — 3 consommateurs attendent)   FR-1 persistance dès QUE possible
                                             (chaque jugement sans distribution
                                             = du passé ponctuel pour toujours)
+quelques jours                              v0 : K=500, deux modes, E8
avec B10/B11/B13                             replis inversés, zéro code
v1                                           replay de promotion par monde
                                             (machinerie B12) ; priors empiriques ;
                                             cause `fragility` vers task_causes
```

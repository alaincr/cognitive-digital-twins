# PRD B10 — Système immunitaire épistémique : vérification adversariale permanente

**Brique :** extension phase 3 (après boucle réduite fermée + M0 + 4 rapports
hebdo — gel ADR-001 point 6 respecté). **Priorité :** P1 phase 3.
**Estimation :** 2–3 jours-dev (v0, stratégie unique) ; le portefeuille
complet est incrémental. **Dépend de :** boucle réduite vivante (B1–B4),
propositionizer (WP-1a) comme porte d'entrée, belief layer (WP-1b) ;
s'améliore avec le dreamer (carte de fragilité — PRD à venir) mais n'en
dépend pas (repli §5 FR-2). **Profil :** dev Python + conception de prompts ;
aucune nouvelle infrastructure de jugement.

---

## 0 · Principes de conception (normatifs — le cœur de ce PRD)

Ce document spécifie moins un composant qu'un **protocole d'ajout de
cognition adversariale** au substrat. Les principes suivants priment sur
toute exigence fonctionnelle ; une implémentation qui les viole est une
régression de design, pas un bug (même statut que I1–I4).

- **P1 · L'intention hostile n'obtient jamais le verdict.** Un procureur
  produit des *candidats* (propositions sourcées, arguments, cas limites) —
  jamais des jugements. L'adjudication appartient exclusivement au pipeline
  existant : mêmes micro-juges, mêmes gates conformes, même consolidateur.
  Corollaire : n'importe quel agent, aussi hostile soit-il par construction,
  peut recevoir un accès en écriture aux *entrées* du pipeline, parce que ce
  sont les gates — pas l'intention de l'agent — qui décident de ce qui
  devient croyance.
- **P2 · La poursuite est monotone.** Attaquer = ajouter de la contre-évidence
  au graphe, jamais retirer du support. Le seul point non-monotone (le
  changement de statut d'une stance) reste dans le consolidateur — le split
  CALM est inchangé.
- **P3 · Tout procureur est une cohorte révocable.** Chaque procureur porte
  une identité de famille de juge (`prosecutor/<strategie>@<version>`) et
  l'enveloppe I4 complète. Un procureur qui produit des oppositions
  systématiquement fallacieuses se rétracte d'un coup (`retract-cohort!`) —
  le système immunitaire a son propre système immunitaire.
- **P4 · Silencieux par défaut.** Les attaques vivent dans le log. Roam ne
  voit que : (a) un changement de statut effectif, (b) le résumé du rapport
  hebdomadaire. Le propriétaire doit ressentir le scepticisme du système
  comme une météo mensuelle, jamais comme un procès quotidien — sinon
  l'effet paralysant (R3) détruit plus de valeur épistémique que les
  attaques n'en créent.
- **P5 · Le budget est l'arme de contrôle.** La sophistique passe à
  l'échelle ; le budget non. Attaques plafonnées par cycle, ciblées par
  enjeu (§4.1), et le gate conforme calibré reste le filtre : une objection
  fabriquée doit encore convaincre un juge calibré qu'elle *oppose*
  réellement.
- **P6 · L'échec d'une attaque est une information de premier ordre.**
  Une attaque forte re-jugée `refines` plutôt qu'`opposes` a affûté le
  claim au lieu de le renverser — c'est le travail dialectique d'un bon
  directeur de thèse. Ce résultat est consigné et rattaché au claim, pas
  jeté.

## 1 · Contexte et problème

Le statut `accepted-undisputed` de la couche de croyances confond deux
états radicalement différents : *personne n'a jamais objecté* et *les
objections ont été tentées et ont échoué*. Pour une thèse — ou une position
RGPD défendable devant un régulateur — la différence est tout. Aujourd'hui
la contre-évidence n'entre que passivement (une source ingérée se trouve
opposer un claim) ; rien ne va *chercher*. E2 (contradictions plantées,
PRD B7) vérifie que l'instrument détecte un conflit fabriqué ; B10 pose la
vraie question : **lesquels de mes claims acceptés survivraient à une
tentative compétente de les tuer ?**

## 2 · Objectif et métriques

- **O1** : distinguer, par un statut dédié, `non-examiné` de `testé` :
  un claim dont les attaques ciblées ont échoué gagne `accepted-tested`,
  avec l'historique d'attaque attaché (nombre, stratégies, meilleur
  résultat obtenu par l'adversaire).
- **O2** : les claims porteurs (stabilité × centralité maximales) sont
  attaqués en priorité — le budget adversarial suit l'enjeu, pas le hasard.
- **M1** : ≥ 80 % du budget d'attaque consommé sur le quintile supérieur
  de `enjeu` (§4.1) — mesuré dans le rapport hebdo.
- **M2** : taux de promotion des propositions de procureur (combien
  passent les juges) entre 5 % et 40 % — en dessous, le procureur est
  inutile ; au-dessus, soit le graphe est faible, soit le procureur a
  trouvé une faille des juges (les deux cas exigent une revue).
- **M3** : zéro verdict auto-rapporté par un procureur (P1) ; 100 % des
  effets de statut passent par le consolidateur (P2) — assertions de
  self-test, pas des cibles.
- **M4** : le propriétaire voit ≤ 1 écriture Roam liée aux attaques par
  semaine hors changements de statut réels (P4).

## 3 · Périmètre

### v0 — un procureur, une stratégie
| rôle | v0 | portefeuille cible (incrémental) |
|---|---|---|
| ciblage | top-5 claims par enjeu, mensuel | continu, budgété par cycle |
| poursuite | **cohérence interne seule** : le procureur ne lit QUE les sources déjà dans le graphe (relectures hostiles, sur-lectures détectées, tensions inter-sources non exploitées) — aucun accès web | + chercheur de littérature contraire (web) ; + constructeur de cas limites ; + réécrivain steelman |
| adjudication | pipeline existant, inchangé | inchangé (P1 est permanent) |

### Non-objectifs
- Toute forme de « note » ou score de qualité du claim par le procureur
  lui-même (P1).
- Attaque des stances `out`/`undecided` (le prochain jugement réel les
  renversera de toute façon — le budget va aux murs porteurs).
- Génération de texte destinée au propriétaire (les attaques ne sont pas
  des tâches humaines ; si une attaque mérite l'humain, elle le atteint
  par la voie normale : contradiction promue → cause → task_gen).
- Modification de la mécanique des juges, des seuils, ou des calsets.

## 4 · Mécanique normative

### 4.1 Ciblage
`enjeu(claim) = stabilité(claim) × centralité(claim)` où :
- `centralité` = taille du cône de recompute 2-sauts (déjà calculée pour
  le blast-radius des stances) ;
- `stabilité` = probabilité de stance issue de l'ensemble du dreamer si
  disponible ; **repli sans dreamer** : `1 - churn_historique` (E4) ou, à
  froid, 1.0 uniforme (le ciblage devient centralité pure — dégradation
  documentée, pas un blocage).
Cibles = top-k par enjeu parmi les stances `in`, k borné par le budget.

### 4.2 Poursuite
Le procureur v0 reçoit : le claim, ses arêtes entrantes, le texte des
sources citées (via `raw-path::`), et les claims voisins. Il produit des
**candidate rows standard** (contrat SPEC-00 §3.3) et/ou des propositions
au format WP-1a, chacune avec `provenance.family: "prosecutor/internal@v1"`
et `caused_by` = l'identifiant de campagne d'attaque (content-addressed).
Sortie plafonnée : ≤ 3 candidats par cible, ≤ 15 par campagne.

### 4.3 Adjudication et statut
Aucun code nouveau : les candidats entrent par le préfiltre (budget
normal), sont jugés, promus ou non. Le consolidateur gagne une seule
extension : à la clôture d'une campagne, pour chaque cible dont AUCUNE
attaque n'a produit d'arête `opposes` promue, appende l'événement
`claim.attack-survived {claim, campaign, n_attacks, best_outcome}` ;
la couche de croyances expose `accepted-tested` pour les stances `in`
portant ≥ 1 survie d'attaque non périmée (une nouvelle arête entrante
quelconque réinitialise le statut à `accepted-supported` — un claim ne
reste « testé » que tant que le terrain n'a pas bougé). **Contrat** : ce
statut s'ajoute à l'énumération de SPEC-03/INTERFACES (PR sur les deux,
même commit — règle de changement standard).

### 4.4 Restitution (P4)
- Rapport hebdo : « k claims attaqués, s survivants, p promotions
  adverses » + le détail par claim dans le JSON.
- Roam : uniquement via les mécanismes existants (stance_diff → ordre
  `stance_v1` si un statut change ; digest hebdo).

## 5 · Exigences fonctionnelles

- **FR-1** `prosecutor.py target` : calcule l'enjeu (§4.1, avec repli),
  émet la liste de cibles de campagne (fichier `sim/attack_targets.jsonl`),
  déterministe à graphe égal.
- **FR-2** `prosecutor.py attack` : génère les candidats (§4.2) via
  l'ancre ou un modèle dédié ; `--dry-run` sans réseau ; spend métré par
  le ledger B6 (`run: "prosecutor-<campaign>"`).
- **FR-3** consolidateur : événement `claim.attack-survived` (§4.3) +
  statut `accepted-tested` dans la couche de croyances (belief.py ET
  belief.clj, même commit).
- **FR-4** rapport : section immunitaire dans l'hebdo B7 (M1, M2, liste
  des survivants et des renversés).
- **FR-5** révocabilité : `judge_id`/famille procureur dans chaque
  enveloppe ; un test prouve que `retract-cohort!` sur une famille de
  procureur retire toutes ses arêtes promues et déclenche les stale-marks
  du cône (la machinerie existe ; le test d'intégration est le livrable).

## 6 · Cas limites

1. Le procureur redécouvre une opposition déjà promue → dédup normal par
   `context_hash` ; l'attaque compte comme « déjà connue », pas comme
   survie ni renversement.
2. Une attaque promeut `refines` (pas `opposes`) → P6 : consigné comme
   `best_outcome: refines`, le claim reste `in`, l'arête `refines` reste
   (elle a de la valeur) ; le rapport le met en avant.
3. La cible est renversée entre ciblage et adjudication par une évidence
   *réelle* (non adverse) → campagne sur cette cible close sans verdict
   de survie (le monde a répondu avant le procureur).
4. M2 > 40 % sur une campagne → gel automatique du procureur (pas de
   nouvelle campagne) jusqu'à revue humaine : soit le graphe est
   réellement faible (bonne nouvelle épistémique, mauvaise pour la
   thèse), soit les juges ont une faille exploitée (I3 en danger).
5. Deux procureurs du portefeuille produisent le même candidat →
   `context_hash` identique, une seule entrée ; la provenance porte la
   première famille émettrice (l'attribution multiple est un raffinement
   phase 4, non requis).

## 7 · Plan de test et DoD

- Self-tests : ciblage déterministe + repli sans dreamer (FR-1) ;
  plafonds et format candidate-row (FR-2, mock modèle) ; transition
  `accepted-tested` et sa réinitialisation sur nouvelle arête (FR-3,
  fixtures V-immune ajoutées aux V1–V15) ; M3 asserté.
- Test d'intégration : campagne complète sur graphe jetable avec un
  procureur mock produisant 1 opposition réelle + 2 faibles → 1 claim
  renversé, 1 claim `accepted-tested`, rapport correct, puis
  rétractation de la cohorte procureur → graphe revenu à l'état
  antérieur (FR-5).
- **DoD produit** : une campagne réelle mensuelle a tourné 2 fois sur le
  graphe du propriétaire ; ≥ 1 claim porte `accepted-tested` ; le
  propriétaire confirme n'avoir subi aucun bruit Roam au-delà du contrat
  P4/M4 ; README_immune.md (incl. la doctrine P1–P6).

## 8 · Risques

| Risque | Prob. | Mitigation |
|---|---|---|
| R1 — Sophistique industrialisée : l'adversaire fabrique toujours quelque chose | haute | P5 (budget + gate conforme comme filtre) ; M2 borne haute avec gel automatique (cas 4) |
| R2 — Monoculture adversariale : robustesse à un seul style d'attaque | moyenne | portefeuille de stratégies (périmètre cible) — la diversité d'attaque est aux survies ce que la diversité de familles est aux panels T2 |
| R3 — Effet paralysant : le propriétaire écrit des claims plus timides | moyenne | P4 (silencieux par défaut), cadence mensuelle v0, langage du rapport (une survie est une force, une chute est une découverte) |
| R4 — Coût ancre des campagnes | moyenne | spend ledger B6 par campagne, plafond dédié, stratégie interne-seule en v0 (pas de web, contexte borné) |
| R5 — Confusion des rôles si le procureur alimente aussi les calsets | basse | les candidats procureur sont exclus des calsets de calibration (filtre sur `provenance.family` préfixe `prosecutor/`) — on ne calibre pas les juges sur du matériel fabriqué pour les piéger |

## 9 · Phasage

```
phase 3 (post M0+4 hebdos)   v0 : procureur interne-seul, top-5, mensuel
+1 mois                       revue M2 ; décision portefeuille
phase 3.x                     + littérature contraire (web), cas limites,
                              steelman ; cadence hebdo budgétée
avec dreamer                  ciblage passe de centralité-seule à
                              stabilité × centralité (§4.1 sans changement
                              de code — le repli s'inverse)
```

# PRD B11 — Le manuscrit comme projection : la thèse dérivée du graphe

**Brique :** extension phase 3+ — c'est le driver `compose`/RLM différé par
SPEC-00 §6 et ADR-001 A.1 ; il se débloque après M0 + 4 rapports hebdo
(point 5 de l'ADR). **Priorité :** P1 phase 3 (c'est le livrable-thèse).
**Estimation :** 2 j-dev (v0 squelette seul) + 3–4 j (couche prose) +
itérations de goût. **Dépend de :** boucle réduite vivante, B3 (les
élaborations sont la voix), WP-1a (propositionizer, pour le gate de
fidélité inversé), `compose-assembly` (zettel.clj, existe) ; s'améliore
avec le dreamer (plancher de stabilité) et B10 (`accepted-tested`) sans en
dépendre (replis §5). **Profil :** dev Python/Clojure + le propriétaire
comme rédacteur-en-chef des *entrées*.

---

## 0 · Principes de conception (normatifs, même statut que B10 §0)

- **P1 · Le document est une vue, jamais une source.** Le manuscrit est au
  layer de croyances ce que `edges.jsonl` est au layer de jugement : une
  projection régénérée, sans existence propre. Il ne peut pas dériver
  silencieusement de l'évidence parce qu'il n'existe pas indépendamment
  d'elle.
- **P2 · On édite les entrées, jamais la sortie.** Toute retouche du
  propriétaire passe par le graphe (élaboration B3, nouvelle source,
  réponse de tâche) et réapparaît au rendu suivant. Une édition directe du
  fichier rendu est un no-op par construction (écrasée la nuit suivante) —
  et c'est voulu.
- **P3 · Churn de formulation ≠ churn de contenu.** Le rendu est
  content-addressed par section : entrée inchangée ⇒ prose byte-identique.
  Le diff nocturne ne montre QUE ce que le graphe a réellement appris.
- **P4 · Rien d'affirmable que le graphe ne porte.** Chaque assertion
  rendue doit résoudre vers des refs de blocs avec stance `in` ; la
  fidélité de la prose est jugée par le pipeline lui-même (gate `faithful`
  inversé, §4.3). Le manuscrit est soumis à la même discipline épistémique
  que tout le reste.
- **P5 · La voix du propriétaire est le matériau privilégié.** Partout où
  une élaboration `:source/family :human` existe pour un claim, ELLE
  fournit les mots (citation verbatim) ; la prose machine connecte,
  structure, résume — elle ne remplace jamais une voix humaine disponible.
- **P6 · Honnêteté de frontière.** Les stances `undecided` à forte
  centralité ne disparaissent pas : elles rendent une section « questions
  ouvertes ». La thèse dit ce qu'elle ne sait pas encore.

## 1 · Contexte et problème

Tout système documentaire stocke le document puis lutte pour le garder
cohérent avec ses sources. Le substrat a déjà fait le geste inverse pour
les arêtes et les stances ; B11 l'étend au livrable final.
`compose-assembly` (zettel.clj) construit déjà l'entrée exacte : trains
Folgezettel entrelacés de résumés, node-ids ordonnés pour le RLM, et la
règle « toute assertion doit résoudre ou ouvrir une gap-task ». Ce qui
manque : le fold squelette, le rendu discipliné, le gate de fidélité, et
le lieu de vie du document.

**Sans B11 :** le graphe accumule des croyances calibrées mais le
manuscrit — la raison d'être du projet côté thèse — reste un document
ordinaire, édité à la main, désynchronisable en silence, sans provenance
phrase-à-phrase.

## 2 · Objectif et métriques

- **O1** : chaque nuit, `manuscript/` contient la thèse dérivée de l'état
  courant du graphe ; le diff git nocturne est le journal de recherche.
- **O2** : provenance phrase-à-phrase — chaque assertion porte ses refs et
  survit au gate de fidélité.
- **M1 (déterminisme)** : graphe inchangé ⇒ re-rendu byte-identique
  (squelette ET prose) — assertion de self-test, pas une cible.
- **M2 (fidélité)** : ≥ 95 % des propositions extraites du rendu passent
  le gate `faithful` au premier coup ; les échecs régénèrent en mode
  citation (§6 cas 3) — zéro assertion non couverte publiée.
- **M3 (voix)** : part des claims du squelette couverts par une
  élaboration humaine verbatim — rapportée par chapitre (cible indicative
  croissante ; c'est aussi une carte des endroits où B3 doit générer des
  tâches d'élaboration).
- **M4 (signal du diff)** : sur 2 semaines, le propriétaire juge chaque
  diff nocturne « informatif / bruit » — ≥ 80 % informatif, sinon P3 est
  violé quelque part et la couche prose n'est pas déployée plus loin.

## 3 · Périmètre

### v0 — squelette seul (2 j-dev, falsification la moins chère)
Fold déterministe pur, AUCUN LLM : plan argumentatif par chapitre —
claims retenus (stances `in`), ordre (trains + centralité), refs de
support, statuts affichés, section questions ouvertes. Rendu markdown
dans `manuscript/`, committé chaque nuit. **Gate de décision** : deux
semaines de lecture ; si les diffs du squelette ne sont pas informatifs,
la prose ne les sauvera pas — on s'arrête là (M4 appliqué au squelette).

### v1 — couche prose
Rendu LLM par section, content-addressed (P3), gate de fidélité (P4),
règle de voix (P5).

### Non-objectifs
- Édition du rendu par le propriétaire (P2 — le README l'explique en
  première ligne).
- Mise en page/LaTeX/bibliographie formatée — le rendu est du markdown
  structuré ; la toilette finale de soumission reste un travail humain
  ponctuel HORS système (copie figée, plus une projection).
- Écriture du manuscrit dans Roam (§4.5 — il vit dans git).
- Style « inspiré » : la projection est le brouillon permanent, pas la
  plume finale.

## 4 · Mécanique normative

### 4.1 Squelette (fold pur)
Entrées : stances (belief), trains/résumés (`compose-assembly`),
élaborations, historique d'attaques (B10 si présent). Règles :
- seuls les claims `in` sont affirmés ; `accepted-tested` (si B10 actif)
  obtient la primauté rhétorique (ossature du chapitre) ;
- plancher de stabilité : un claim n'est affirmé que si
  `stabilité ≥ plancher` (dreamer si présent ; **repli** : pas de
  plancher, mais les claims à churn E4 récent sont marqués `~instable`
  dans le squelette) ;
- `undecided` centraux → section questions ouvertes (P6) ;
- chaque entrée du squelette = `{claim-uid, refs[], statut, section,
  ordre}` — sérialisation canonique, hashée par section.

### 4.2 Rendu (LLM discipliné)
Par section : prompt = fragment de squelette + texte des blocs cités +
élaborations disponibles. Température 0, seed = hash du fragment
(SPEC-00 §3.4). Cache par `sha256(fragment + textes cités)` : hit ⇒
prose réutilisée telle quelle (P3/M1).

### 4.3 Gate de fidélité (le pipeline en sens inverse)
Chaque section rendue est propositionnée (WP-1a) ; chaque proposition est
jugée `faithful` contre les claims cités (jtype existant, juges
existants). Échec ⇒ régénération avec l'échec en contexte (1 retry) puis
repli citation (cas 3). Aucun rendu ne publie sans passer le gate.

### 4.4 Règle de voix (P5)
Résolution par claim : élaboration humaine disponible ⇒ verbatim
(neutralisée pour la syntaxe, jamais reformulée) ; sinon prose machine
marquée comme telle dans les métadonnées de section (pas dans le texte).
M3 mesure la couverture ; les trous de voix des chapitres actifs
alimentent `task_gen` (cause `elaborate`, priorité normale — pas de
nouveau mécanisme).

### 4.5 Lieu de vie et restitution
- `manuscript/<chapitre>.md` dans le REPO, régénéré et committé chaque
  nuit (nouvelle étape du cycle, après le write-back). Git diff = journal.
- Roam reçoit UNE ligne de digest (« §3.2 s'est réécrit : 2 promotions,
  1 rétractation ») avec block-refs vers les causes — via le digest B2
  existant, champ `notes`.
- Une rétractation de cohorte se voit dans le diff du matin : les
  paragraphes dépendants se dissolvent. C'est une feature, pas un bug —
  la démonstration la plus viscérale que la provenance est réelle.
- **Shape S9** (pack SHACL) : tout nœud d'assertion de la projection
  manuscrit porte ≥ 1 ref résoluble vers un claim `in` — ajoutée à
  `shapes/` + CROSSWALK, même commit.

## 5 · Exigences fonctionnelles

- **FR-1** `compose_skeleton.py` : le fold §4.1, pur, self-testé sur
  fixtures (graphe 3 chapitres synthétique) ; déterminisme M1 asserté ;
  replis dreamer/B10 testés.
- **FR-2** `compose_render.py` : rendu §4.2 avec cache content-addressed ;
  mock modèle au self-test ; spend métré (ledger B6, `run:
  "compose-<nuit>"`).
- **FR-3** gate de fidélité §4.3 : orchestration propositionizer + juges
  existants ; M2 calculé et rapporté.
- **FR-4** règle de voix §4.4 + M3 par chapitre + génération des tâches
  de trou de voix.
- **FR-5** intégration cycle : étape 11 (après write-back), commit git
  automatique du manuscrit, digest Roam ; échec de l'étape n'affecte
  aucune autre (le manuscrit est une feuille, rien n'en dépend).
- **FR-6** shape S9 + entrée CROSSWALK + fixtures s9_ok/s9_bad.

## 6 · Cas limites

1. Stance oscillante nuit après nuit → sans dreamer : marqueur
   `~instable` + le diff la montre (l'oscillation EST l'information) ;
   avec dreamer : sous le plancher ⇒ questions ouvertes, pas d'assertion.
2. Rétractation entre squelette et rendu (même nuit) → le rendu lit le
   squelette figé de la nuit ; la rétractation apparaît au cycle suivant
   (cohérence par instantané, pas par course).
3. Gate de fidélité échoue 2× sur une section → repli citation : la
   section rend les claims en style télégraphique + citations exactes des
   blocs — moche mais fidèle ; signalé dans le digest.
4. Le propriétaire édite `manuscript/*.md` directement → écrasé la nuit
   suivante ; le README l'annonce ; git garde son édition dans l'historique
   (récupérable, jamais intégrée) — la friction est pédagogique (P2).
5. Élaboration humaine contredite par le graphe depuis (claim passé
   `out`) → la voix n'est jamais rendue pour un claim non-`in` ; le cas
   génère une tâche de réconciliation (mécanique B9/FR-4 réutilisée si
   présente, sinon tâche elaborate standard).
6. Chapitre sans aucun claim stable → rendu honnête : squelette vide +
   questions ouvertes (un chapitre vide est un fait sur le graphe, pas un
   échec du renderer).

## 7 · Plan de test et DoD

- Self-tests FR-1/FR-2 (déterminisme byte-à-byte, cache hit/miss, replis) ;
  FR-3 sur fixtures (proposition infidèle plantée ⇒ retry ⇒ repli) ;
  FR-6 (s9_ok/s9_bad).
- Intégration : 3 nuits simulées sur graphe jetable — nuit 1 baseline,
  nuit 2 graphe inchangé (diff vide exigé), nuit 3 une promotion + une
  rétractation (diff montrant exactement les deux effets).
- **DoD v0** : 14 diffs nocturnes réels relus par le propriétaire, M4
  ≥ 80 % → décision go/no-go couche prose consignée (c'est le gate du
  périmètre §3).
- **DoD v1** : M1–M3 verts sur 2 semaines ; une rétractation réelle
  observée dans un diff ; README_manuscript.md (P1–P6 en tête).

## 8 · Risques

| Risque | Prob. | Mitigation |
|---|---|---|
| R1 — Diffs de squelette non informatifs (le concept ne tient pas) | moyenne | v0 = falsification à 2 j-dev AVANT toute prose ; gate M4 explicite |
| R2 — Plafond de qualité de la prose machine | certaine | P5 (la voix humaine prend le dessus partout où elle existe) + « brouillon permanent » assumé ; la toilette finale est hors système |
| R3 — Le gate de fidélité devient le goulot (coût juges par nuit) | moyenne | cache P3 (sections inchangées = 0 jugement) ; budget dédié ; repli citation borne le pire cas |
| R4 — Le propriétaire édite la sortie malgré tout | haute au début | cas 4 : friction pédagogique + README ; les éditions perdues se retrouvent dans git |
| R5 — Goodhart sur M3 (élaborer pour couvrir, pas pour penser) | basse | M3 est une carte, pas une cible chiffrée ; les tâches de trou de voix passent par le budget anti-fatigue B3 normal |

## 9 · Phasage

```
phase 3 (post M0+4 hebdos)   v0 squelette : 2 semaines de diffs, gate M4
si M4 vert                    v1 prose : cache + gate fidélité + voix
avec dreamer                  plancher de stabilité (repli inversé, 0 code)
avec B10                      accepted-tested = ossature rhétorique
soutenance                    copie figée hors système (non-objectif §3)
```

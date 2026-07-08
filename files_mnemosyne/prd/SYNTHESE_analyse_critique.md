# Synthèse critique — architecture cognitive « zettelkasten » (Mnemosyne)

**Date :** 2026-07-04. **Auteur :** revue externe (session Claude Fable).
**Objet :** développer en détail l'analyse de la philosophie du projet, de son
stade d'avancement conceptuel, et des briques restantes. Les briques sont
spécifiées dans le pack PRD adjacent (`00_gap_analysis.md`, `PRD_B1`–`PRD_B7`).

**Corpus examiné :** l'intégralité du dépôt `cognitive-digital-twins` — le
vault de thèse plat (`wiki/`, gelé), les pages bootstrap Roam, l'organisation
d'agents Paperclip (`agents/`, 22 agents), les analyses exploratoires
(`analyses/live-ai-extension`, `analyses/rlm-graph`), et la stack Mnemosyne
(`files_mnemosyne/` : specs SPEC-00→04, `microjudge_contract.md`,
`zettel_addendum.md`, `mnemosyne_stack.md`, ~30 artefacts de code), plus
l'historique git.

---

## 1 · Verdict d'ensemble

Le projet présente un déséquilibre extrême et croissant entre deux axes :

- **Maturité philosophique : très élevée.** La dernière strate (Mnemosyne)
  est du design de niveau publiable, avec des idées que la littérature
  « agents + mémoire » ne traite généralement pas (jugements-comme-faits,
  confiance conforme, rétraction par cohorte, split CALM, strates
  zettelkasten *de dicto / de re*).
- **Maturité opérationnelle : nulle.** En cinq générations d'architecture sur
  environ trois mois, **aucune boucle n'a jamais été fermée** : zéro source
  ingérée dans le wiki (son propre log l'atteste), zéro page bootstrap
  importée dans Roam, zéro agent Paperclip déployé, zéro juge exécuté sur le
  graphe réel, zéro ligne de Clojure exécutée sur une JVM.

Le diagnostic central n'est donc plus conceptuel mais **comportemental** : le
mode de production du projet (sessions de design avec un LLM) génère de la
spécification à coût marginal quasi nul, et chaque session produit une
architecture plus raffinée que la précédente au lieu d'exécuter la
précédente. Le reste de ce document détaille les forces, les critiques, et le
chemin de sortie.

---

## 2 · Chronologie des cinq strates (avec preuves)

| # | Strate | Période | Preuve d'état |
|---|---|---|---|
| 1 | **Vault de thèse plat** (markdown, italien, Politecnico) | ≤ avril 2026 | 69 fichiers restaurés le 30/04 ; `wiki/log.md` gelé le 10/06 avec *« zero ingest eseguiti »* — 12 papiers, 2 calls, 3 approfondissements, tous `pending` |
| 2 | **Wiki Roam-natif** (pattern « LLM Wiki » de Karpathy) | 30/04 → 02/05 | roadmap (`implementation-roadmap.md`), diagrammes de flux ; 13 pages bootstrap **templétées mais jamais importées** dans un graphe Roam |
| 3 | **Organisation Paperclip** : 22 agents, 8 équipes, CEO/leads/ICs, double thèse | 02/05 → 04/05 | 68 fichiers de config (`agent.yaml`, `soul.md`, `heartbeat.md`) ; noms d'outils MCP encore placeholders ; `PROJECT-SUMMARY.md` liste « vérifier le MCP Roam » comme tâche restante |
| 4 | **Analyses exploratoires** (Live-AI in-Roam vs RLM-Graph hors-process) | mai | deux dossiers d'analyse ; la question qu'ils posent (raisonnement dans Roam ou à côté ?) n'est **pas tranchée** |
| 5 | **Stack Mnemosyne** (L1/L2/L3, micro-juges, croyances, zettel, SHACL) | ~juin | tout `files_mnemosyne/` est **hors git** (non commité) ; Python auto-testé, Clojure « hand-checked » jamais exécuté, Phase 0 jamais lancée |

Deux observations structurantes :

1. **Chaque strate est plus sophistiquée ET plus proche de l'exécutable** que
   la précédente — la trajectoire converge vers le réel (la strate 5 contient
   du code auto-testé, un runbook, des budgets). C'est un vrai progrès, pas un
   simple empilement.
2. **Aucune strate n'enterre officiellement la précédente.** Le dépôt contient
   simultanément quatre doctrines opérationnelles vivantes en apparence.
   Voir §5 (contradictions) et §8 (ADR-001).

---

## 3 · La philosophie : ce qui tient, et pourquoi c'est substantiel

### 3.1 L'inversion centrale est une vraie idée unificatrice
« Prendre ce que le domaine traite comme sous-produit jetable — le log
d'événements, le prompt, la base de données — et le promouvoir en substrat
porteur ; puis faire du calcul une navigation récursive et une croissance
monotone de ce substrat » (`mnemosyne_stack.md` §0). Cette phrase unifie
réellement les trois couches (store Datalog bitemporel / runtime
événementiel / inférence récursive), et chaque couche hérite d'en dessous une
propriété qu'elle ne peut pas se donner seule (terminaison des récursions,
replay déterministe, provenance requêtable). Ce n'est pas de l'esthétique
architecturale : les tableaux « ce qui casse sans la couche du dessous » sont
argumentés mécanisme par mécanisme.

### 3.2 Le contrat des micro-juges résout des problèmes que presque personne ne voit
Les quatre invariants (`microjudge_contract.md` §0) méritent d'être nommés
comme la contribution la plus originale du projet :

- **I1 (jugements = faits, jamais des réécritures)** restaure une sémantique
  quasi-monotone à la propagation médiée par LLM : idempotence triviale,
  oscillation impossible, accumulation distribuable sans coordination.
- **I3 (confiance mesurée : logprobs + température + gate conforme, jamais
  auto-déclarée)** attaque frontalement la mis-calibration décorative des
  petits modèles — avec l'honnêteté rare de noter que la garantie conforme
  décroît sous dérive de distribution et n'est « pas un théorème sur votre
  déploiement ».
- **I4 (enveloppe de provenance complète)** rend possible la **rétraction par
  cohorte** : « nous avons fait tourner un juge biaisé pendant trois
  semaines » devient une requête suivie d'événements de rétraction, pas une
  catastrophe. C'est, à ma connaissance, une propriété qu'aucun système
  « mémoire d'agent » grand public n'offre.
- Le **split CALM** (accumulation monotone distribuable / promotion-négation-
  rétraction confinées à un writer unique) est appliqué avec constance à
  chaque nouvelle pièce (l'addendum zettel place chacun de ses mécanismes
  d'un côté ou de l'autre du split, explicitement).

### 3.3 L'addendum zettelkasten est philosophiquement juste
La séparation strates `fleeting / candidate / literature / permanent` avec la
règle porteuse « seul le *permanent* (de re) nourrit les stances ; la
*littérature* (de dicto) n'entre qu'en évidence typée » est la formalisation
correcte de la distinction d'Ahrens — et, pour le fil RGPD, la ligne exacte
entre « la CNIL énonce » et « nous soutenons ». Le §6 (boucle d'élaboration)
est la meilleure idée du design : réinstaller la friction humaine « exactement
là où elle constitue l'apprentissage », et faire des élaborations humaines
l'or d'entraînement prioritaire de la distillation — la boucle d'apprentissage
du propriétaire et la boucle d'amélioration du système deviennent la même
boucle. Le §4 scope le décay au bon endroit (activation des fleeting
seulement, jamais le record).

### 3.4 Une honnêteté épistémique interne rare
Les specs marquent leurs propres limites : colonne de statut de vérification
traitée comme contrat, « hand-checked, jamais exécuté » écrit noir sur blanc,
tensions résolues « par politique, pas par code » listées comme engagements à
tenir. Cette hygiène doit être créditée — et elle rend la critique du §4
d'autant plus nette : le projet *sait* ce qu'il n'a pas fait.

---

## 4 · Les critiques de fond

### 4.1 Le projet viole sa propre thèse
La question de recherche est : *« comment une architecture cognitive
auto-référentielle étudie-t-elle et améliore-t-elle ses propres
composants ? »* Or le système ne s'est **jamais observé faire quoi que ce
soit**. Il n'existe aucune donnée empirique d'auto-observation ; il n'existe
que des spécifications de ce que l'auto-observation *serait*. Le nombre
autour duquel « tout le reste est réglé » selon SPEC-00 — le taux
d'abstention du premier juge — n'a jamais été mesuré.

Plus mordant : le diagnostic du `zettel_addendum.md` §6 (« le collector's
fallacy industrialisé » — accumuler sans élaborer donne l'illusion du
travail) s'applique au **méta-niveau du projet lui-même**. Les specs sont la
collection ; l'élaboration manquante est l'exécution. Générer de
l'architecture en session LLM est sans friction et gratifiant ; exécuter
expose à l'échec. Le projet a suivi la pente exactement comme ses propres
documents prédisent qu'un système sans friction la suivrait.

### 4.2 Les pivots remplacent au lieu de superséder
Le principe opératoire n°3 du CLAUDE.md du projet dit : *« Don't rewrite,
evolve — `status:: superseded` plutôt que suppression. »* Entre strates,
c'est l'inverse qui s'est produit : rien n'établit le statut des strates
1–4 depuis l'avènement de Mnemosyne. Conséquences concrètes :

- Un nouvel agent (humain ou LLM) lisant le dépôt reçoit **quatre doctrines
  simultanées** et peut légitimement travailler sur n'importe laquelle — y
  compris relancer un sixième pivot.
- Pour un design obsédé de provenance (chaque verdict de juge porte hash de
  poids, version de prompt, version de calibration…), l'absence totale
  d'**ADR** (architecture decision records) au niveau des pivots est une
  ironie à corriger : le système tracera pourquoi une arête `supports` existe,
  mais pas pourquoi 22 agents ont été conçus puis abandonnés.

### 4.3 Contradictions doctrinales précises (à trancher, pas à commenter)
1. **Source de vérité** : le CLAUDE.md affirme « Roam est la vérité, le repo
   est la spec » ; Mnemosyne affirme « le log append-only immuable est la
   source de vérité » (SPEC-00 §1) et Roam n'y est qu'un *export* qu'on
   moissonne. Les deux ne peuvent pas être vraies. Résolution recommandée en
   §8.
2. **Unité d'orchestration** : l'organisation Paperclip répond par des
   *agents avec heartbeats* (22 rôles, tickets, managers) ; Mnemosyne répond
   par des *behaviors réactifs + juges budgétés + un consolidateur* — « pas
   d'orchestrateur » est même un principe de L2. La seconde réponse rend la
   première largement caduque : la plupart des heartbeats des 22 agents sont
   des behaviors ou des règles de lint dans le monde Mnemosyne.
3. **Où vit le raisonnement** : in-Roam (Live-AI) vs hors-process
   (RLM-Graph) — question posée par les analyses de mai, jamais tranchée ;
   Mnemosyne y répond de fait (hors-process, L1 sur le graphe), sans le dire.
4. **Modèles par rôle** : la question ouverte « Sonnet partout ? » du
   CLAUDE.md appartient au monde Paperclip ; dans le monde Mnemosyne la
   question devient « quels petits modèles pour quels jtypes, quel modèle
   ancre » — vocabulaire incompatible, seconde formulation opérante.

### 4.4 Le budget de complexité suppose une équipe qui n'existe pas
SPEC-00 s'adresse explicitement à « a development team ». Chiffrons la seule
dette de calibration du design complet : ≥ 300 exemples étiquetés **par type
de jugement** (9 types) **par version de juge**, avec revue humaine des cas
flaggés pour les types T2, panels hétérogènes 2-de-3 sur trois familles de
modèles servies localement, moniteur de dérive avec ré-ancrage périodique.
Pour une personne seule, c'est plusieurs semaines de travail d'opérateur
avant le premier jugement digne de confiance — et c'est *récurrent* (toute
bump de version de prompt ⇒ recalibration). Ce n'est pas un argument contre
le design ; c'est un argument décisif pour la **réduction drastique du
périmètre de la Phase 0** actée dans le pack PRD : 2 jtypes, 1 juge, pas de
panel, T2 gated sur l'ancre/l'humain.

### 4.5 Sans tâche exogène, l'auto-référence tourne à vide
La roadmap de mai flaggait déjà le risque en propres termes (« researching
research about researching… »). Un système auto-référentiel sans charge de
travail extérieure ne peut produire que du discours sur lui-même — et aucun
critère extérieur ne peut le réfuter. Or le projet possède déjà son
antidote : le fil **RGPD/juridique** traverse toute la strate Mnemosyne (la
démo de référence est un pipeline de conformité ; le juge `faithful?` a un
label `lost-qualifier` précisément parce qu'une proposition juridique privée
de sa réserve est *fausse* ; le linter S1 vérifie les bases légales). Ce fil
doit être promu de démo à **charge directrice** : c'est lui qui rend les
prétentions de l'architecture falsifiables (E2/E3 du PRD B7).

### 4.6 Aucune théorie de ce qui compte comme preuve
Ni pour la thèse (« qu'est-ce qui prouverait que l'architecture s'améliore
elle-même ? ») ni pour l'exploitation (« à quoi verra-t-on que le substrat
bat un dossier de fichiers markdown ? »). Les métriques *internes* existent
(abstention, couverture conforme, elaboration-coverage) — c'est bien — mais
aucune métrique de *tâche finale* n'est définie, donc aucun critère d'arrêt
ni de pivot rationnel n'existe. Le PRD B7 y répond avec cinq métriques
volontairement modestes, chacune attachée à une décision (« si E1 > 60 %
alors recalibrer/changer de modèle » — un seuil sans décision est du décor).

### 4.7 Risques d'exploitation sous-pesés dans les specs
Trois risques opérationnels sont traités par le design comme périphériques
alors qu'ils sont, pour un système mono-utilisateur, existentiels :
- **La fatigue du propriétaire** (les tâches d'élaboration sont la boucle
  d'apprentissage : si le taux de réponse s'effondre, tout le reste est du
  bruit) — d'où les budgets anti-fatigue et l'auto-adaptation du PRD B3.
- **L'infrastructure présumée** (flotte vLLM sur des noms Tailscale
  d'exemple ; Hermes mentionné comme allant de soi) — d'où le mode API
  dégradé, contractuel et flaggé, du PRD B6.
- **La visibilité du bénéfice** : sans write-back vers Roam, le propriétaire
  ne voit littéralement jamais rien — un système invisible est un système
  abandonné dans les 30 jours. D'où la priorité P0 du PRD B2.

---

## 5 · Stade d'avancement : l'inventaire honnête

Sur l'échelle idée → design → spec → prototype → système opéré :

| Sous-ensemble | Stade |
|---|---|
| Philosophie / architecture (L1-L2-L3, invariants, zettel) | **au-delà du nécessaire** — sur-mûri |
| Pipeline Python amont (harvest réel, ancre, harness conforme, préfiltre, métriques, runbook WP-0) | **prototype prêt à courir** — il ne manque que des endpoints et un export |
| Livrables WP-1 (propositionizer, belief, SHACL) | prototypes auto-testés, jamais confrontés au graphe réel |
| Substrat Clojure (le seul écrivain) | **spec exécutable non exécutée** — le maillon le plus risqué |
| Boucle fermée avec Roam (sync, write-back, tâches humaines, cycle, éval) | **absente** — c'est l'objet du pack PRD |
| Strates 1–4 (wiki, bootstrap Roam, 22 agents, analyses) | à statuer par ADR : archives et intrants de migration |

Formulé autrement : **le projet est à la fin de la spec, avant tout prototype
vivant, avec un pipeline à 60 % prêt qui n'attend que trois choses — un
export, un endpoint, et la décision de courir.**

---

## 6 · Le risque comportemental, nommé sans détour

Le mode de travail « réflexion par sessions LLM successives » a une
dynamique propre qu'il faut regarder en face : le modèle est excellent pour
produire de l'architecture cohérente et enthousiasmante, la friction est
nulle, la gratification immédiate — et chaque session repart volontiers de
« et si on repensait la structure ». Cinq strates en trois mois est la
signature de cette dynamique, pas celle d'un défaut d'intelligence du design.
Les contre-mesures sont les mêmes que celles que le projet prescrit à son
propre substrat :

1. **Un gel** : aucune nouvelle session de design tant que le rapport M0
   (taux d'abstention réel) n'existe pas. La prochaine session utile se
   termine par un chiffre, pas par un document.
2. **Une trace de décision** (ADR) à chaque bifurcation, pour que le coût
   d'un pivot inclue l'écriture de la nécrologie du précédent.
3. **Un critère extérieur** (PRD B7) pour que « ça marche mieux » cesse
   d'être une impression de session.

---

## 7 · Les briques restantes (renvoi au pack PRD)

L'analyse d'écart complète est dans `00_gap_analysis.md`. En résumé, la
boucle réduite exige sept briques, ~20–26 jours-dev au total :

| PRD | Brique | Rôle dans la boucle | Priorité |
|---|---|---|---|
| B1 | `roam_sync` | export automatisé + snapshots + **deltas bloc-à-bloc** (guérit le « pas d'historique » de Roam) | P0 |
| B2 | `roam_writeback` | les résultats promus redeviennent visibles dans Roam (espace `M/*`, append-only, idempotent) | P0 |
| B3 | tâches humaines | élaboration/triage/bridges/review dans Roam + récolte + routage vers calsets et propositions | P0 |
| B4 | consolidateur + cycle | exécuter (enfin) le Clojure, journal d'événements durable, orchestrateur nocturne en 10 étapes | P0 |
| B5 | embeddings | `:sim/near`, candidats `continues`, graines de bridges — le rung B de l'échelle, aujourd'hui vide | P1 |
| B6 | infra juges | endpoints réels ; **mode API dégradé contractuel** pour démarrer sans GPU ; garde-fous de dépense | P0 |
| B7 | évaluation | 5 métriques de tâche finale, rapport hebdo, contradictions plantées, benchmark propriétaire | P1 |

Chemin critique : **ADR-001 → B6 + B1 → WP-0 (déjà écrit) → M0 → B4 → B2 → B3**.

---

## 8 · ADR-001 (proposition de texte à ratifier)

> **Décision.** (1) Le journal d'événements append-only de Mnemosyne est la
> source de vérité épistémique ; **Roam est la surface de capture et de
> restitution humaine** — son export est un intrant, l'espace `M/*` sa
> projection. La formule du CLAUDE.md est amendée en conséquence.
> (2) L'organisation Paperclip (22 agents) est **supersédée** par
> behaviors + juges + consolidateur ; ses configs sont archivées comme
> matériau de la strate 3 ; toute résurrection exige un nouvel ADR.
> (3) Le raisonnement vit **hors-process** (L1 sur le graphe) ; les analyses
> Live-AI/RLM-Graph sont closes avec cette décision.
> (4) Le wiki plat et les pages bootstrap sont des archives et des intrants
> de migration ; aucune ingestion n'y reprend.
> (5) La charge de travail directrice de la boucle réduite est le corpus
> RGPD/thèse du propriétaire ; toute extension de périmètre attend M0 + 4
> rapports hebdomadaires B7.
> **Statut :** proposé. **Conséquence si non ratifié :** toute session
> future peut légitimement relancer un pivot (cf. §4.2).

---

## 9 · Séquencement recommandé et critères d'arrêt

| Semaine | Objectif | Sortie vérifiable |
|---|---|---|
| S1 | ADR-001 ratifié ; B6-lite ; B1 v0 (drop-folder + pull si l'API coopère) | `infra_check.py` vert ; premier snapshot + delta |
| S2 | **WP-0 exécuté** (`first_judge.sh`, 2 jtypes, sessions opérateur de revue) | **M0 : `first_judge_report.md` avec le taux d'abstention** |
| S3–S4 | B4 (consolidateur exécuté + cycle nocturne) ; B2 | premiers jugements visibles dans Roam ; crash/replay tests verts |
| S4–S5 | B3 (tâches humaines) ; B5 en parallèle | 10 réponses humaines routées ; premières paires kNN |
| S6 | B7 ; 7 cycles consécutifs sans intervention | premier rapport hebdo ; boucle déclarée fermée |

**Critères d'arrêt honnêtes** (à évaluer à S6 + 4 semaines) :
- Si le taux d'abstention M0 reste > 60 % après une recalibration et un
  changement de modèle de juge : l'hypothèse « micro-juges locaux » est
  infirmée à cette échelle — retomber sur un pipeline ancre-seule (plus cher,
  plus simple) et le documenter comme résultat de recherche, pas comme échec.
- Si le taux de réponse humaine (E5) reste < 30 % malgré deux itérations de
  format : la boucle d'élaboration est infirmée pour ce propriétaire — le
  système se replie sur lint + croyances (toujours utile), et la thèse perd
  son chapitre le plus ambitieux mais gagne un résultat négatif propre.
- Si E3 ne montre aucun gain de la colonne « arêtes promues » sur la colonne
  « recherche lexicale » après 8 semaines : le substrat ne paie pas son
  loyer — c'est le signal de pivot le plus important de tous, et c'est
  exactement pour l'obtenir qu'on ferme la boucle.

Dans les trois cas, l'infrastructure de mesure transforme un abandon diffus
en résultat de recherche daté et cité — ce qui est, précisément, ce que la
thèse du projet demande.

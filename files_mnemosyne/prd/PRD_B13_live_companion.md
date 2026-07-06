# PRD B13 — Compagnon temps réel : le graphe présent au moment d'écrire

**Brique :** extension phase 3 — le premier changement de *tempo* du
système (tout le reste est nocturne ; ceci vit à l'échelle du paragraphe).
**Priorité :** P1 phase 3 (c'est la valeur d'usage quotidienne du graphe ;
sans elle, la connaissance est fiable mais absente au point d'emploi).
**Estimation :** 3–4 j-dev (v0 sur demande) ; ambiant et recherches
commissionnées incrémentaux. **Dépend de :** B1 (client API, réutilisé en
polling), B2 (transport d'écriture vers `M/Live`), B5 (kNN — le cœur du
tier 0), couche de croyances (stances en mémoire) ; s'améliore avec le
dreamer (stats de mondes), B10 (`accepted-tested`), B12 (les seuils du
compagnon sont la classe auto-promotable idéale) — sans en dépendre.
**Profil :** dev Python + une vraie sensibilité au coût d'interruption.

---

## 0 · Principes de conception (normatifs)

- **P1 · Le silence est la sortie par défaut.** Le compagnon score chaque
  murmure potentiel et ne dit rien sous le seuil. Une session où il ne
  parle jamais est un état de succès, pas un échec. (L'anti-fatigue B3,
  puissance dix : en temps réel, l'interruption compose avec le flow.)
- **P2 · La tension avant la confirmation, toujours.** L'échec séduisant
  est la sycophance architecturale : les confirmations font plaisir, les
  métriques d'engagement les récompensent, le compagnon dérive en machine
  à approuver. Ordre dur du murmure : contradictions et lacunes d'abord ;
  confirmations en dernier, compressées (refs, pas de prose).
- **P3 · Le murmure est épistémiquement sans poids.** Strate SOUS
  `:fleeting` : éphémère (TTL), jamais moissonné (`M/Live` hérite de
  l'exclusion `M/*`), jamais dans les calsets, les croyances ou les
  citations — sauf geste explicite du propriétaire (block-ref, `#garder`),
  qui le fait entrer par la porte normale du pipeline. C'est cette règle
  unique qui autorise la vitesse : le compagnon peut être rapide et
  parfois faux parce que rien de ce qu'il dit n'a de standing avant
  d'avoir payé les gates.
- **P4 · Les chemins rapides ne servent que du vérifié ; le neuf paie le
  péage entier.** Tier 0/1 = lecture du graphe existant (I3 intact à
  pleine vitesse). Toute connaissance NOUVELLE (recherches commissionnées)
  entre par `raw/` → propositionizer → juges — jamais injectée brute dans
  la surface vive (statut oui, substance non).
- **P5 · Pull, jamais push.** Aucune notification. Deux surfaces de
  lecture, toutes deux à l'initiative du propriétaire : la page `M/Live`
  en sidebar, et le panneau de linked references du bloc en cours (chaque
  murmure cite `((uid))` — le mécanisme d'ADR-001 A.3, réutilisé tel
  quel). I1 intact : on n'annote jamais les blocs de l'utilisateur.
- **P6 · L'insolite est rationné à part.** Le canal left-field a son
  propre budget (1/session en v0). La sérendipité meurt par le volume.
- **P7 · Muet sur les surfaces sacrées.** Jamais de murmure sur les pages
  `M/Tasks` : souffler du contexte pendant les réponses d'élaboration
  empoisonnerait exactement l'or humain et les sondes B9 dont la valeur
  est d'être *à lui seul*.

## 1 · Contexte et problème

Tout le système est nocturne : on écrit le jour, il pense la nuit, on
rencontre ses pensées le matin. Résultat : au moment précis où le
propriétaire pense — mi-paragraphe dans Roam — le graphe est fiable mais
absent. Ce qu'il contient de pertinent, ce qui confirme ou tend à
infirmer ce qui s'écrit, les lacunes à combler, les prolongements et les
connexions latérales : tout existe ou est calculable, rien n'est présent.
Le constat d'architecture : **presque rien n'est à inventer ; tout est à
re-tiérer par latence.**

| Fonction demandée | Machinerie réutilisée | Tier |
|---|---|---|
| « le graphe le sait déjà » | kNN B5 (matrice mémoire, ~ms) | 0 |
| confirme / tend à infirmer | stances + arêtes autour des hits | 0 |
| lacunes à combler | propositionize-lite du paragraphe → assertions sans correspondance | 1 |
| lancer les recherches | commissionnement VoI, entrée par l'ingest normal | 2 |
| prolongements / avenues | stances `undecided`, tâches ouvertes, trains adjacents | 0–1 |
| connexions left-field | bridge seeds, doorways de registre, analogies structurelles, stats de mondes | 1, rationné |

## 2 · Objectif et métriques

- **O1** : sur demande (v0), un murmure utile arrive ≤ 30 s après le tag,
  composé exclusivement de contenu du graphe (tier 0/1).
- **O2** : zéro contamination — les murmures ne rentrent dans aucun
  circuit épistémique sans geste explicite du propriétaire.
- **M1 (keep-rate)** : part des murmures recevant un geste de conservation
  (block-ref ou `#garder`) — LA métrique de valeur au point d'usage ;
  rapportée par fonction (tension / lacune / prolongement / left-field)
  dans l'hebdo B7 (nouvelle section E7).
- **M2 (silence)** : en mode ambiant (v1), part des paragraphes édités ne
  déclenchant AUCUN murmure ≥ 70 % — sinon P1 est violé.
- **M3 (latence)** : tag → murmure ≤ 30 s (v0) ; P95 mesuré.
- **M4 (contamination)** : assertions de self-test — `M/Live` exclu des
  trois mineurs (harvest, préfiltre, embed), aucun murmure dans un calset,
  mute P7 effectif.
- **M5 (anti-sycophance)** : ordre P2 asserté ; ET part des murmures
  contenant ≥ 1 élément de tension ou lacune quand il en existe dans le
  voisinage (le compagnon n'a pas le droit de ne montrer que ce qui
  conforte).

## 3 · Périmètre

### v0 — sur demande uniquement
Le propriétaire tague un bloc `#compagnon` → au prochain poll (≤ 30 s),
un bloc-murmure apparaît sous `M/Live/<date>`, citant le bloc. Tier 0+1
seulement (kNN + stances + un appel de modèle léger). AUCUN mode ambiant.
**Gate de falsification** : si les murmures *convoqués* n'obtiennent pas
de keeps, les murmures ambiants n'en obtiendront jamais — arrêt là.

### v1 — ambiant à silence-défaut
Polling continu des blocs édités ; scoring (nouveauté × pertinence de
stance × historique d'engagement) ; seuils = politiques B12
(auto-promotables). Mute list par page.

### v2 — recherches commissionnées + canal left-field complet.

### Non-objectifs
- Notifications, badges, sons — quel que soit le canal (P5).
- Édition ou annotation des blocs de l'utilisateur (I1).
- Injection de contenu de recherche non jugé dans la surface vive (P4).
- Niveau frappe-par-frappe (extension navigateur) — phase lointaine,
  seulement si la cadence 30 s perd démontrablement des moments qui
  comptent ; le paragraphe est la granularité voulue, pas le caractère.
- Chat / dialogue — le compagnon écrit des murmures cités, il ne converse
  pas (la conversation est une session Claude normale, hors périmètre).

## 4 · Mécanique normative

### 4.1 Acquisition
Poll API Roam (client B1 réutilisé : normalisation, NFC, backoff) toutes
les 15–30 s : blocs `edit-time` récents hors `M/*`. v0 : filtre
supplémentaire = présence du tag `#compagnon`.

### 4.2 Tier 0 (lecture pure, ~ms)
Encoder le paragraphe (e5-small local) → top-k dans la matrice B5 →
stance de chaque hit (stances.jsonl en mémoire) + arêtes entrantes.
Sorties mécaniques, zéro génération : « ressemble à ((X)) — IN,
3 supporters[, testé B10] » / « tension : proche de ((Y)), que le graphe
rejette, opposé par ((Z)) ». La fonction confirmation/contradiction est
**structurellement fiable** parce qu'elle est lue, pas composée.

### 4.3 Tier 1 (un appel léger, secondes)
Entrée : paragraphe + hits + stances. Trois travaux : découper le
paragraphe en assertions (propositionize-lite), les apparier aux hits,
composer le murmure dans l'ordre P2. Assertions assertives sans
correspondance = **lacunes** (« le graphe n'a jamais vu ceci — ni support
ni opposition ») ; formulation contractuelle : une lacune est la
frontière, pas une erreur. Spend métré (ledger B6, `run: "live-<date>"`).

### 4.4 Tier 2 (commissionné)
Une lacune taguée `#chercher` sur le murmure → job de recherche ; les
résultats atterrissent dans `raw/` et suivent l'ingest normal. Le
compagnon peut poster « recherche lancée ; 3 sources trouvées, en
ingestion » — statut, jamais substance (P4).

### 4.5 Format du murmure (bloc sous `M/Live/<date>`)
```
[[M/Murmure]] ((uid-du-bloc-écrit))
    ⚡ tension : proche de ((Y)) — le graphe le rejette (opposé par ((Z)))
    ∅ lacune : « … » — jamais vu ; #chercher pour commissionner
    → avenue : ((Q)) est undecided à 2 sauts ; le train ((T)) passe ici
    ✓ appuis : ((A)) ((B)) ((C))
    ⋯ left-field : structurellement, cet argument a la forme de ((W)) (autre domaine)
    ttl:: [[<date+7j>]]   fonction-scores:: …
```
Sections absentes si vides ; ordre P2 fixe ; left-field ≤ 1 (P6).

### 4.6 Canal left-field (P6, v2 — un échantillon en v0 si trivial)
Par ordre de préférence : stats de mondes du dreamer (« la claim sur
laquelle vous bâtissez tient dans 61 % des mondes ») ; bridge seed
touchant la région ; doorway de registre partagé avec un train distant ;
analogie structurelle (profil d'arêtes similaire, embedding distant).

## 5 · Exigences fonctionnelles

- **FR-1** `live_companion.py poll` : boucle d'acquisition (4.1),
  état de curseur persistant, `--once` pour test.
- **FR-2** tier 0 pur (4.2) : self-testé sur fixtures (mock encoder B5) ;
  sortie déterministe à graphe égal.
- **FR-3** tier 1 (4.3) : mock modèle au self-test ; ordre P2 asserté
  (M5) ; budget/spend.
- **FR-4** écriture : via le transport B2 (batch, uids générés, ledger) ;
  cible exclusive `M/Live/*` (allowlist B2 étendue — PR sur
  INTERFACES/README_writeback, même commit) ; TTL posé ; purge des
  murmures expirés sans keep (une purge de `M/Live` est le SEUL delete
  toléré du système — les murmures n'ont pas de standing, P3 ; consigné
  comme exception explicite à « never delete »).
- **FR-5** keeps : détection des gestes de conservation au poll suivant
  (block-ref entrant ou `#garder`) → le contenu gardé entre par le
  pipeline normal (candidate row) ; ledger des keeps → M1/E7.
- **FR-6** mutes : P7 (`M/Tasks`) codé en dur ; mute list par page en v1.
- **FR-7** exclusions M4 : assertions ajoutées aux self-tests des trois
  mineurs (fixture contenant un `M/Live/…`).

## 6 · Cas limites

1. Le propriétaire écrit DANS `M/Live` (répond à un murmure sur place) →
   toléré, jamais moissonné (M/*) ; le compagnon détecte le texte sous
   son murmure comme keep implicite ? Non — v0 : seuls block-ref et
   `#garder` comptent (règle du moindre malentendu ; à revoir au DoD).
2. Paragraphe < 25 caractères ou liste de refs pures → pas d'encodage,
   pas de murmure (même plancher que le préfiltre).
3. Le kNN ne retourne rien au-dessus du seuil → murmure « lacune totale »
   UNIQUEMENT si demandé (v0/tag) ; silence en ambiant (P1).
4. Deux tags `#compagnon` sur le même bloc avant le poll → un seul
   murmure (idempotence par `(uid, content-hash)`).
5. L'API Roam est indisponible → le compagnon s'éteint silencieusement
   (log stderr) ; jamais de retry agressif qui mange le rate limit du
   write-back nocturne.
6. Le bloc tagué est déjà couvert par un murmure récent au même
   content-hash → renvoyer une ref vers le murmure existant, pas un
   doublon.
7. Session B9 en cours (tâche de sonde à l'écran) → P7 couvre `M/Tasks` ;
   les probes hors M/Tasks n'existent pas — pas de fuite.

## 7 · Plan de test et DoD

- Self-tests FR-2/FR-3 (fixtures, mock encoder + mock modèle, ordre P2,
  idempotence cas 4), FR-4 (allowlist étendue, TTL, purge = seule
  suppression et seulement sous M/Live), FR-7 (les trois mineurs).
- Intégration graphe jetable : tag → murmure ≤ 30 s → keep par block-ref
  → candidate row au cycle suivant → jugée normalement (le chemin P3
  complet).
- **DoD v0** : 2 semaines d'usage réel sur demande ; M1 par fonction
  rapporté ; M3 P95 ≤ 30 s ; M4 vert ; décision go/no-go ambiant
  consignée (avec les seuils initiaux v1 proposés comme EXP B12 si B12
  est vivant).

## 8 · Risques

| Risque | Prob. | Mitigation |
|---|---|---|
| R1 — Interruption du flow / bruit (le risque n°1, version temps réel) | haute | v0 sur demande UNIQUEMENT ; P1/P5 ; M2 gate l'ambiant ; le propriétaire convoque, le système ne s'invite pas |
| R2 — Sycophance architecturale | haute (à terme) | P2 dur + M5 asserté ; keep-rate rapporté PAR fonction (une dérive vers les confirmations se voit) |
| R3 — Influence non tracée sur l'écriture du propriétaire | certaine (et voulue — c'est l'augmentation) | ce qui doit rester traçable l'est : les murmures citent leurs sources, le geste naturel d'incorporation (block-ref) transporte la provenance ; résiduel documenté dans la méta-thèse |
| R4 — Rate limit API partagé avec B1/B2 | moyenne | budget de polling propre, backoff, extinction silencieuse (cas 5) |
| R5 — Coût tier 1 à l'usage ambiant | moyenne | modèle léger, cache par content-hash de paragraphe, spend ledger ; l'ambiant n'existe qu'après le gate v0 |
| R6 — La purge TTL crée un précédent « delete » | basse | exception unique, périmètre M/Live strict, consignée dans FR-4 et le README — toute extension du droit de purge = ADR |

## 9 · Phasage

```
phase 3            v0 sur demande (#compagnon) — gate de falsification M1
si keeps           v1 ambiant silence-défaut ; seuils = politiques B12
ensuite            v2 recherches commissionnées + left-field complet
avec dreamer       stats de mondes dans le canal left-field (0 code en plus)
lointain           frappe-par-frappe (extension) — seulement sur preuve
                   que 30 s perd des moments qui comptent
```

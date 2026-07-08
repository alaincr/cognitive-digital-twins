# PRD B2 — Service de write-back vers Roam (`roam_writeback.py`)

**Brique :** G2 de `00_gap_analysis.md`. **Priorité :** P0.
**Estimation :** 3–4 jours-dev. **Profil :** dev Python ; sensibilité produit
(ce composant est la seule chose que le propriétaire *voit*).

---

## 1 · Contexte et problème

Le pipeline actuel se termine dans des fichiers : `outbox.jsonl` (jugements),
`edges.jsonl` (arêtes promues), `stances.jsonl` (croyances), rapports SHACL.
**Roam — la « source de vérité » et la seule interface du propriétaire — ne
reçoit jamais rien.** Sans write-back :
- le système ne rend aucun service observable (aucune raison d'exister au
  quotidien) ;
- la boucle humaine (tâches d'élaboration, B3) n'a pas de support ;
- la doctrine « Roam est la vérité » est structurellement fausse.

B2 est le composant qui referme la boucle côté humain. Il écrit dans Roam les
résultats promus par le consolidateur (B4) — et rien d'autre.

## 2 · Objectif et métriques

- **O1** : chaque cycle, les faits promus apparaissent dans Roam sous une forme
  navigable, filtrable, et **append-only** (invariant I1 : on n'édite jamais le
  contenu de l'utilisateur).
- **M1** : zéro écriture dupliquée sur 30 cycles (idempotence par
  content-address).
- **M2** : zéro modification d'un bloc non créé par le service (audit : tout
  bloc écrit porte la signature du service).
- **M3** : le propriétaire peut retrouver « tous les jugements sur cette page »
  en un clic (backlinks Roam standard).

## 3 · Périmètre

### v0
Quatre familles d'écriture, toutes issues du consolidateur :
1. **Jugements acceptés** (arêtes de discours, successions `continues`).
2. **Flags** (violations SHACL/linter : base légale manquante, claim non
   supporté, orphelin permanent…).
3. **Changements de stance** (sorties de `belief.py` : un claim passe
   `accepted-supported` → `undecided`, etc.).
4. **Tâches humaines** (pour le compte de B3, qui définit leur contenu).

### Non-objectifs
- Écrire des résumés/synthèses générés (régime C — hors boucle réduite).
- Modifier ou supprimer des blocs utilisateur (interdit par I1, définitivement).
- Créer des pages de contenu ; le service écrit uniquement dans son espace
  réservé + des refs.

## 4 · Modèle d'écriture dans Roam (normatif)

### 4.1 Espace réservé
Toute écriture atterrit dans l'espace de noms `M/` :
- `[[M/Journal]]` — une entrée par cycle, sous un bloc daté.
- `[[M/Flags]]` — flags ouverts, un bloc par flag.
- `[[M/Tasks]]` — tâches humaines (structure définie par B3).
- Sur la **daily note** du jour : un unique bloc `#[[M/Digest]]` de ≤ 5 lignes
  (n nouveaux jugements, n flags, n tâches — avec refs vers les pages `M/`).

### 4.2 Forme d'un jugement écrit
Un bloc par fait promu, enfant de l'entrée de cycle dans `[[M/Journal]]` :

```
[[M/J]] ((uid-source)) supports ((uid-cible)) — conf 0.87
    jtype:: edge_type
    ctx:: sha256:ab12…            ← content-address du contexte jugé
    judge:: qwen3-8b@8f3a21c0#p1
    cycle:: [[July 4th, 2026]]
```

- Les `((refs))` de blocs donnent les backlinks gratuits côté Roam (M3).
- `ctx::` est la **clé d'idempotence** (FR-2).
- Aucune prose générée : uniquement le fait typé et son enveloppe — le bloc
  est la projection Roam de l'événement du log, pas un commentaire.

### 4.3 Forme d'un flag
```
[[M/Flag]] S2 UnsupportedClaim — ((uid-du-claim))
    severity:: warning
    shape:: S2
    ctx:: sha256:…
    status:: open
```
La résolution d'un flag n'est PAS une suppression : le cycle suivant, si le
linter ne le re-détecte plus, le service ajoute `status:: resolved` en enfant
(append-only, l'historique reste lisible).

## 5 · Exigences fonctionnelles

### FR-1 · Entrée : le fichier d'ordres du consolidateur
B2 ne décide rien. Il consomme `writeback_orders.jsonl`, produit par B4
(contrat ci-dessous), et l'exécute. Une ligne :
```json
{"kind": "judgment|flag|stance|task|digest",
 "idempotency_key": "sha256:…",
 "target": {"page": "M/Journal", "under": "cycle-2026-07-04"},
 "content": {"template": "judgment_v1", "fields": {…}},
 "caused_by": "evt-…"}
```

### FR-2 · Idempotence
Avant toute écriture, interroger Roam (query sur `ctx::` / la clé) pour
vérifier l'absence de la clé. Écriture réussie → enregistrer la clé dans un
ledger local `writeback_ledger.jsonl` (cache d'abord local, la query Roam est
le filet). Re-run complet du même fichier d'ordres = zéro nouveau bloc.

### FR-3 · Transport
- Primaire : API backend Roam (`create-block`, `create-page`), même token que
  B1.
- Écritures par petits lots avec espacement (≤ 300 write/min par défaut,
  configurable) ; backoff sur 429/5xx ; reprise mi-fichier grâce au ledger.
- `--dry-run` obligatoire : imprime le rendu exact des blocs sans écrire.

### FR-4 · Budget et garde-fous
- Budget par cycle : ≤ `max_writes` (défaut 200) ; au-delà, tronquer par
  priorité (tasks > flags > stances > judgments) et le signaler dans le digest.
- Allowlist de pages cibles : refuser tout ordre visant une page hors `M/*`
  ou la daily note (défense en profondeur contre un bug de B4).
- Mode `--quarantine` : sur alarme de dérive du juge (contrat §6), les
  jugements du juge quarantainé ne sont plus écrits ; les flags de rétraction
  de cohorte, eux, le sont.

### FR-5 · Rétraction de cohorte, côté Roam
Quand le consolidateur émet des rétractations (cohorte biaisée), B2 ajoute à
chaque bloc de jugement concerné un enfant :
```
status:: retracted
retraction:: ((ref vers l'entrée de journal expliquant la cohorte))
```
Jamais de suppression du bloc d'origine — la bitemporalité du log doit rester
lisible dans Roam aussi.

### FR-6 · CLI
```
roam_writeback.py apply   --orders writeback_orders.jsonl [--dry-run]
roam_writeback.py verify  --orders …      # relit Roam, vérifie clés présentes
roam_writeback.py self-test               # mocks, zéro réseau
```

## 6 · Exigences non fonctionnelles

- Stdlib-first ; mock du transport injecté à une couture (pattern SPEC-02 §7).
- Rendu des templates déterministe (mêmes fields → mêmes strings).
- Tout échec d'écriture individuel est loggé et n'interrompt pas le lot ;
  code retour non-zéro si > 5 % d'échecs.
- Les strings écrites échappent/neutralisent tout contenu source pouvant
  casser la syntaxe Roam (`[[`, `((`, `::` dans le texte cité → échappés) —
  c'est aussi une surface d'injection : le contenu cité est *data*, ne jamais
  le laisser créer des refs involontaires.

## 7 · Cas limites

1. Page `M/Journal` absente (premier run) → la créer.
2. Uid source supprimé entre promotion et écriture → écrire quand même, la
   `((ref))` morte est un signal, pas une erreur ; marquer `ref-dangling:: true`.
3. Deux ordres, même clé, contenus différents → erreur fatale du lot (bug
   amont B4 ; ne pas choisir silencieusement).
4. Graphe Roam indisponible → le fichier d'ordres reste en place, le ledger
   permet la reprise au cycle suivant ; le digest du cycle suivant mentionne le
   rattrapage.

## 8 · Plan de test et DoD

- `self-test` : transport mocké ; assertions sur idempotence (double apply),
  allowlist, échappement, rétraction, troncature budget, reprise mi-fichier.
  ≥ 15 assertions.
- Test d'intégration documenté sur un **graphe Roam jetable** (pas celui du
  propriétaire) : apply réel de 20 ordres fixtures, verify vert, re-apply → 0
  écriture.
- DoD : self-tests verts + intégrés à la régression programme ; `--dry-run`
  démontré sur les fixtures ; revue de la forme des blocs par le propriétaire
  (c'est un choix d'UX, pas de dev) ; `README_writeback.md`.

## 9 · Risques

| Risque | Prob. | Mitigation |
|---|---|---|
| Pollution visuelle du graphe (rejet utilisateur) | moyenne | espace `M/*` strict + digest unique sur la daily note + budget ; revue UX au DoD |
| Limites de l'API d'écriture Roam | moyenne | lots + backoff + reprise ; en dernier ressort, réduire `max_writes` |
| Bug amont écrivant hors périmètre | faible | allowlist FR-4 (défense côté B2, indépendante de B4) |

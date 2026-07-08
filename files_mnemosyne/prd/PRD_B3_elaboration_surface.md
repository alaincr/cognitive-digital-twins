# PRD B3 — Surface humaine : tâches d'élaboration et récolte des réponses

**Brique :** G3 de `00_gap_analysis.md`. **Priorité :** P0 (c'est la boucle
d'apprentissage humain, la « meilleure idée du design » — `zettel_addendum.md` §6).
**Estimation :** 3 jours-dev. **Dépend de :** B1 (récolte), B2 (écriture), B4
(routage). **Profil :** dev Python ; co-conception des templates avec le
propriétaire obligatoire.

---

## 1 · Contexte et problème

`zettel_addendum.md` §6 fait des élaborations humaines la clé de voûte : la
friction est réinstallée « exactement là où elle constitue l'apprentissage »,
et les réponses humaines deviennent l'or d'entraînement prioritaire de
`distill_judge.py` (`:source/family :human`). Le §4 (triage des fleeting), le
§8 (morning dialog / bridges) et le gate humain T2 de `first_judge.sh` stage 3
supposent tous une surface où l'humain répond.

**Cette surface n'existe pas.** Aucun format de tâche, aucun mécanisme de
récolte des réponses, aucun routage vers les calsets ou les propositions.
Sans B3, le système peut juger mais jamais apprendre de son propriétaire.

## 2 · Objectif et métriques

- **O1** : chaque matin, ≤ N tâches (défaut 5) attendent dans Roam, répondables
  en ≤ 2 minutes chacune, dans Roam, sans changer d'outil.
- **O2** : toute réponse est récoltée au cycle suivant et routée sans
  intervention : calset (or humain), proposition permanente, ou verdict de
  bridge.
- **M1** : taux de réponse hebdomadaire mesuré (cible indicative ≥ 50 % — si
  plus bas, le format des tâches est mauvais, pas l'utilisateur).
- **M2** : 100 % des réponses récoltées portent la provenance
  `{"source": "human"}` jusque dans le calset / le log d'événements.
- **M3** : zéro tâche dupliquée (même clé d'idempotence que B2).

## 3 · Périmètre

### v0 — quatre types de tâche
| type | déclencheur (côté consolidateur/B4) | réponse attendue |
|---|---|---|
| `elaborate` | contradiction promue sur un claim utilisé ; cluster franchit le seuil de résumé | 2–3 phrases dans les mots du propriétaire |
| `triage` | note fleeting dont l'activation a décayé (addendum §4) | choix : promouvoir / garder / archiver |
| `bridge` | paire embedding-proche inter-trains sans chemin court (§8 ; nécessite B5) | choix : related / unrelated (+ phrase optionnelle) |
| `review` | item T2 flaggé par `anchor_label.py` (review queue WP-0) | label or parmi l'enum du jtype |

### Non-objectifs
- Notifications hors Roam (mail, push) — le digest B2 suffit en v0.
- Interface dédiée — Roam EST l'interface (doctrine du projet).
- Gamification, scoring de l'utilisateur.

## 4 · Format des tâches dans Roam (normatif, co-conçu avec le propriétaire)

Sous `[[M/Tasks]]`, un bloc par tâche, écrit par B2 :

```
[[M/Task]] Comment ((uid-claim-X)) se tient-il face à ((uid-evidence-Y)) qui le contredit ?
    task-type:: elaborate
    task-id:: sha256:…                 ← clé d'idempotence
    status:: open
    due-hint:: [[July 6th, 2026]]
    ↳ (bloc enfant vide préformaté)  « Réponse : »
```

Règles :
- **La réponse est le texte du bloc enfant** commençant par `Réponse :`
  (ou, pour `triage`/`bridge`/`review`, un tag de choix fermé :
  `#promouvoir` / `#garder` / `#archiver`, `#related` / `#unrelated`,
  ou le label de l'enum). Choix fermés = tags ; texte libre = bloc enfant.
  Ne jamais demander les deux pour les types à choix fermé.
- L'utilisateur marque `status:: done` OU se contente de répondre — la
  récolte traite « réponse présente » comme done (le champ status est un
  confort, pas un contrat).
- Une tâche ignorée 14 jours passe `status:: expired` (append par B2) et
  sort du stock affiché ; elle reste requêtable.

## 5 · Exigences fonctionnelles

### FR-1 · Génération (`task_gen.py`, appelé par le cycle B4)
- Entrées : événements du consolidateur (contradictions, décay, review queue)
  + bridges de B5. Sortie : ordres `kind: task` dans `writeback_orders.jsonl`
  (contrat B2 FR-1).
- **File de priorité budgétée** : `priorité = stakes × activation` (mêmes
  conventions que le préfiltre) ; budget quotidien `max_tasks` (défaut 5).
  Ce qui est coupé est loggé (« no silent caps »).
- Dédoublonnage : une même cause (même `ctx`) ne génère jamais deux tâches ;
  une tâche expirée n'est régénérée que si la cause se re-déclenche.

### FR-2 · Récolte (`task_harvest.py`, appelé par le cycle après B1)
- Parcourt le snapshot du jour (pas l'API — B1 fournit tout) : pour chaque
  bloc `[[M/Task]]` avec `status:: open|done`, détecter une réponse
  (enfant `Réponse :` non vide, ou tag de choix).
- Émet dans l'outbox du consolidateur des événements typés :
```json
{"event": "human.response", "task_id": "sha256:…", "task_type": "elaborate",
 "response_text": "…", "choice": null, "answered_ts": 1783…,
 "provenance": {"source": "human"}}
```
- **Le harvest ne route pas** — il émet ; le routage est dans le consolidateur
  (FR-3) pour respecter le split CALM (récolte = monotone ; effets = writer
  unique).

### FR-3 · Routage (règles à implémenter dans B4, spécifiées ici)
| type | effet dans le consolidateur |
|---|---|
| `elaborate` | nouvelle proposition `:source/family :human`, liée aux sujets de la tâche ; ajoutée aux données admissibles pour distillation |
| `triage` `#promouvoir` | candidate → passe le gate `permanent_worthy` avec l'humain comme juge (label or) |
| `triage` `#archiver` | activation gelée, note sortie du stock de triage (jamais supprimée) |
| `bridge` | jugement humain `related/unrelated` appendu ; `related` → arête candidate promue |
| `review` | ligne `{"jtype","fields","gold"}` appendée à `review_resolved.jsonl` → merge calset (mécanique déjà existante, `first_judge.sh` stage 4) |

### FR-4 · Anti-fatigue
- `max_tasks` global ET par type (défaut : 2 elaborate, 1 triage, 1 bridge,
  1 review) — l'élaboration est coûteuse cognitivement, ne pas la noyer.
- Si le taux de réponse 7 jours < 30 %, le générateur réduit de moitié son
  budget et le signale dans le digest (le système s'adapte à l'humain, pas
  l'inverse).

### FR-5 · CLI
```
task_gen.py generate --events … --bridges … --out writeback_orders.jsonl --budget 5
task_gen.py self-test
task_harvest.py harvest --snapshot sync/snapshots/latest.json --out outbox_human.jsonl
task_harvest.py stats   --window 7d        # taux de réponse, par type
task_harvest.py self-test
```

## 6 · Cas limites

1. Réponse modifiée après récolte → les événements sont immuables ; une
   nouvelle version du texte émet un `human.response.amended` (le
   consolidateur supersède, ne réécrit pas).
2. Réponse vide ou « ? » → ni récoltée ni or ; tâche reste open.
3. Deux tags de choix contradictoires sur la même tâche → événement
   `human.response.ambiguous`, tâche re-signalée dans le digest, rien de routé.
4. L'utilisateur répond en éditant le bloc question (pas l'enfant) → tolérer :
   tout texte ajouté sous le bloc tâche compte comme réponse (règle du moindre
   étonnement, à valider avec le propriétaire au DoD).
5. Bloc tâche supprimé par l'utilisateur → traité comme `expired` ; jamais
   régénéré sauf nouvelle cause.

## 7 · Plan de test et DoD

- Self-tests des deux scripts (fixtures de snapshots avec tâches répondues /
  ignorées / ambiguës / amendées) ; ≥ 15 assertions cumulées.
- Test bout-en-bout sur graphe jetable : generate → apply (B2) → réponse
  manuelle → pull (B1) → harvest → événements corrects dans l'outbox.
- **DoD produit** : le propriétaire a répondu à 10 tâches réelles réparties
  sur ≥ 3 jours et confirme le format (sinon itérer les templates — c'est un
  livrable UX autant que code) ; les 10 réponses sont visibles dans le log
  d'événements avec provenance humaine ; `README_tasks.md`.

## 8 · Risques

| Risque | Prob. | Mitigation |
|---|---|---|
| Fatigue / abandon (le risque n°1 du projet entier) | haute | budgets FR-4, tâches ≤ 2 min, adaptation automatique, format co-conçu |
| Parsing fragile des réponses libres | moyenne | contrat minimal (« tout texte sous la tâche »), cas ambigus re-signalés plutôt que devinés |
| Bridges vides tant que B5 absent | certaine | le type `bridge` échoue fermé (0 tâche) — documenté, non bloquant |

# Analyse d'écart — boucle Mnemosyne réduite, opérationnelle avec Roam

**Statut :** normatif pour le pack PRD (documents `PRD_B1` … `PRD_B7`).
**Date :** 2026-07-04.
**Objet :** identifier précisément ce qui manque pour qu'une mécanique *réduite*
tourne en boucle fermée sur le graphe Roam réel du propriétaire, et découper ce
manque en briques spécifiables indépendamment.

---

## 1 · Définition de la boucle réduite visée

Une itération quotidienne complète, sans intervention manuelle autre que les
réponses humaines prévues par le design :

```
(1) export Roam ──► (2) diff/dirty-marks ──► (3) prefilter (budget)
        ▲                                          │
        │                                          ▼
(8) réponses humaines                    (4) juges (1–2 types, gate conforme)
    dans Roam                                      │
        ▲                                          ▼
        │                                  (5) consolidateur (promotion)
(7) write-back Roam ◄── (6) belief/linter ◄────────┘
    (jugements, flags, tâches)
```

Périmètre volontairement réduit :
- **2 types de jugement** : `edge_type` (volume + alimente la couche de
  croyances) et `continues` (le geste zettelkasten quotidien). Pas de panels
  T2 automatisés : les promotions T2 restent gated sur l'ancre ou l'humain
  (conforme à `microjudge_contract.md` §9.6).
- **1 juge + 1 ancre** (pas de flotte multi-familles).
- Pas de distillation, pas de propositionizer en ligne, pas de Fluree.

## 2 · Inventaire de l'existant (vérifié sur le code, pas sur les specs)

### 2.1 Exécutable et auto-testé (prêt)

| Composant | Fichier | État constaté |
|---|---|---|
| Harvest de candidats depuis un **vrai export JSON Roam** (9 types) | `roam_harvest.py` | parse l'export réel ; sous-commandes `harvest` / `demo` |
| Étiquetage or par l'ancre, double passe, review queue | `anchor_label.py` | dry-run testé |
| Scoring, température, gate conforme, CLI calibrate/judge | `judge_harness.py` | self-tests verts (couverture 0.917 ≥ 0.90) |
| Prompts durcis + registre (9 types dont 2 zettel) | `judge_prompts.py`, `zettel_prompts.py` | self-tests verts |
| Préfiltre live (dirty-marks → candidats budgétés, debounce) | `prefilter.py` | self-test (12 assertions) |
| Métriques + rapport M0 | `judge_metrics.py` | self-test |
| Runbook WP-0 par étapes, idempotent | `first_judge.sh` | complet (10 stages, gates humains) |
| Propositionizer (WP-1a) | `propositionize.py` | self-test présent |
| Couche de croyances (WP-1b) | `belief.py` | self-test présent |
| Linter SHACL (WP-1c) | `shacl_lint.py` + shapes `s1..s8` | self-test présent |
| Distillation (phase ultérieure) | `distill_judge.py` | self-test (GPU requis pour `train`) |

### 2.2 Écrit mais jamais exécuté

| Composant | Fichiers | Risque |
|---|---|---|
| Substrat + consolidateur + zettel + croyances (miroir) | `mnemosyne.clj`, `rules.clj`, `judges.clj`, `ingest.clj`, `zettel.clj`, `belief.clj` | « hand-checked », aucun run JVM ; le **seul écrivain** de la boucle est donc non prouvé |

`ingest.clj` est bien câblé côté contrats : il *taille* `outbox.jsonl` /
`anchor_outbox` avec offsets persistants, promeut, et exporte
`accepted.jsonl` (échantillonnage ancre) et `edges.jsonl` (entrée de
`belief.py`). Le chaînon existe sur le papier ; il n'a jamais tourné.

### 2.3 Absent (les écarts bloquants)

| # | Écart | Symptôme si ignoré | Brique |
|---|---|---|---|
| G1 | **Aucune acquisition automatisée de l'export Roam** ; `EXPORT=` suppose un fichier déposé à la main. Aucun historique d'édition (caveat documenté dans `roam_harvest.py`) | pas de boucle quotidienne ; `propagate`/`invalidate` privés de vrais deltas ; dirty-marks approximatifs | **B1** |
| G2 | **Aucune écriture vers Roam.** Le pipeline se termine dans des fichiers (`outbox.jsonl`, `edges.jsonl`, `stances.jsonl`) et un DataScript en mémoire. Roam, « source de vérité », ne voit jamais un seul résultat | le propriétaire n'a aucun bénéfice observable ; la boucle humaine (§6 addendum) est impossible | **B2** |
| G3 | **Aucune surface pour les tâches humaines** (élaboration, triage, bridges, review T2) ni harvest des réponses | la meilleure idée du design (élaboration → or d'entraînement) n'existe pas ; pas d'accumulation d'exemples `:source/family :human` | **B3** |
| G4 | **Consolidateur non exécuté et non durable** (DataScript en mémoire ; le fold ne survit pas au redémarrage ; pas de CI JVM) ; **aucun orchestrateur** du cycle quotidien | perte d'état, aucune promotion réelle, aucune cadence | **B4** |
| G5 | **Couche embeddings (régime B) absente** : pas de `:sim/near`, donc `morning-dialog` rend zéro (échec silencieux documenté), candidats `continues` sous-proposés (fallback lexical seulement) | les mécanismes zettel les plus utiles (bridges, succession) tournent à vide | **B5** |
| G6 | **Aucun endpoint d'inférence réel** : `judges_config.yaml` pointe des noms Tailscale d'exemple ; l'ancre est `api.example.com` ; aucune procédure de mise en service ni mode dégradé sans GPU | `first_judge.sh` échoue au stage 2 ; WP-0 infaisable en l'état | **B6** |
| G7 | **Aucune évaluation de tâche finale** : `judge_metrics.py` mesure le juge (abstention, distribution), rien ne mesure si le substrat bat « un dossier de fichiers markdown » | « auto-amélioration » invérifiable ; pas de critère d'arrêt | **B7** |
| G8 | **Aucune réconciliation doctrinale** entre les strates (Roam-SSOT vs log-SSOT ; 22 agents Paperclip vs behaviors+juges) | toute nouvelle session peut relancer un pivot ; les devs ne savent pas quelle doctrine implémenter | ADR-001 (voir `SYNTHESE_analyse_critique.md` §8 — décision, pas du code) |

### 2.4 Non-écarts (à ne PAS construire pour la boucle réduite)

Explicitement hors périmètre, conformément à SPEC-00 §6 : panels T2
automatisés, distillation en ligne, Fluree, driver `compose`, tuning des
seuils, propositionizer en ligne (il reste un outil batch), tout retour à
l'organisation Paperclip.

## 3 · Carte des briques et dépendances

```
ADR-001 (décision, 1 jour) ──────────────┐
                                          ▼
B6 infra juges ──► WP-0 (first_judge.sh, déjà écrit) ──► M0: taux d'abstention
B1 sync Roam  ──►─┘                                          │
B4 consolidateur + cycle ◄───────────────────────────────────┘
B2 write-back ◄── B4
B3 surface humaine ◄── B2 (écrit les tâches) + B1 (récolte les réponses)
B5 embeddings ──► enrichit B3 (bridges) et le harvest `continues`
B7 évaluation ◄── tout le reste (mesure la boucle)
```

**Chemin critique : ADR-001 → B6 + B1 → WP-0 → B4 → B2 → B3.**
B5 et B7 sont parallélisables dès que B1 existe.

## 4 · Estimation d'ensemble (dev compétent, temps plein)

| Brique | Estimation | Peut démarrer |
|---|---|---|
| B1 sync Roam | 3–4 j | immédiatement |
| B2 write-back | 3–4 j | après B4 (contrats) ; maquette possible avant |
| B3 surface humaine | 3 j | après B2 |
| B4 consolidateur + cycle | 4–5 j (dont CI JVM) | immédiatement |
| B5 embeddings | 3 j | immédiatement |
| B6 infra juges | 2 j (mode API) / +3 j (mode vLLM local) | immédiatement |
| B7 évaluation | 2–3 j | après première boucle fermée |
| **Total** | **≈ 20–26 jours-dev** + sessions opérateur (revue humaine WP-0) | |

## 5 · Critère de succès global (« la boucle est fermée »)

Un matin donné, sans autre intervention que la veille au soir :
1. le cycle nocturne a tiré l'export, jugé ≤ budget de candidats, promu via le
   consolidateur, et écrit dans Roam ≥ 1 jugement accepté, ≥ 0 flags linter,
   et ≤ 5 tâches humaines ;
2. le propriétaire répond à 2 tâches dans Roam ;
3. le cycle suivant récolte ces réponses et les route (calset `:human` /
   proposition permanente) — vérifiable dans `first_judge_report` et le log
   d'événements.

Quand ce scénario a tourné 7 jours consécutifs, la mécanique réduite est
opérationnelle et la phase 2 (tuning, panels, distillation) se débloque avec
des chiffres réels.

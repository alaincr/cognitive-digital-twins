# PRD B6 — Mise en service de l'inférence : juge, ancre, et mode dégradé

**Brique :** G6 de `00_gap_analysis.md`. **Priorité :** P0 (bloque WP-0 :
`first_judge.sh` échoue au stage 2 sans endpoints réels).
**Estimation :** 2 jours-dev (mode API) + 3 jours optionnels (mode vLLM local).
**Profil :** dev ops-leaning.

---

## 1 · Contexte et problème

`judges_config.yaml` est un **exemple** : endpoints Tailscale fictifs
(`machine-b.tailnet`), ancre `api.example.com`, clé `set-me`, hashes de poids
décoratifs. Le harness est prêt ; **aucune inférence réelle n'est possible**.

Le design cible (flotte vLLM locale sur 3090, logprobs natifs, poids épinglés,
replay déterministe) demande du matériel et du temps de mise en service. Il
faut découpler : la boucle réduite doit pouvoir démarrer **sans GPU local**,
en acceptant explicitement les dégradations que le contrat prévoit déjà.

## 2 · Objectif et métriques

- **O1** : `first_judge.sh` passe les stages 0→9 de bout en bout sur le graphe
  réel, dans l'un des deux modes.
- **O2** : chaque mode est décrit par un fichier de config versionné, avec
  smoke test automatisé (`infra_check.py`).
- **M1** : le rapport M0 (`first_judge_report.md`) existe, avec un taux
  d'abstention mesuré — c'est LE livrable que tout le projet attend.
- **M2** : coût du run de calibration ≤ plafond configuré (garde-fou dépense).

## 3 · Les deux modes (normatif)

### Mode API (recommandé pour démarrer — « B6-lite »)
- **Juge** : un endpoint API OpenAI-compatible exposant des **logprobs**
  (ex. un fournisseur d'inférence servant Qwen3-8B ou équivalent avec
  `logprobs` activables). I3 est alors respecté au sens plein (confiance
  mesurée). Si le fournisseur ne donne pas de logprobs : fallback
  contractuel — auto-report flaggé `:confidence/self-reported true` + seuil
  conforme durci (`microjudge_contract.md` I3) ; ce flag doit traverser
  jusqu'à l'outbox (déjà prévu dans le schéma d'événement).
- **Ancre** : API du modèle fort (l'ancre n'a PAS besoin de logprobs : elle
  produit des labels or, pas des confiances calibrées).
- Limites assumées et documentées : pas de replay déterministe parfait
  (poids non épinglés côté fournisseur) — le `judge_id` encode alors le nom
  de modèle + version API + date de calibration, et la recalibration est
  déclenchée sur tout changement annoncé de modèle.

### Mode local (cible — « B6-full »)
- vLLM en serveur OpenAI-compatible sur la/les machines GPU,
  `--enable-prefix-caching` (le scoring echo partage le préfixe entre labels —
  déjà noté dans le YAML), poids épinglés par hash réel, temp 0.
- Un service par famille de modèle ; santé exposée ; démarrage systemd.

Le harness ne change pas : les deux modes sont des `base_url` différents.
C'est la force du design existant — l'exploiter, ne pas le réécrire.

## 4 · Exigences fonctionnelles

### FR-1 · `judges_config.yaml` réel, séparé de l'exemple
- Renommer l'exemple `judges_config.example.yaml` ; le vrai fichier est
  hors git (`.gitignore`) ; les clés API viennent de l'environnement
  (`${ANCHOR_API_KEY}` interpolé au chargement, jamais en clair).

### FR-2 · `infra_check.py` (smoke test)
```
infra_check.py all --config judges_config.yaml
```
Vérifie, par juge configuré : endpoint joignable ; modèle servi = modèle
déclaré ; logprobs disponibles (sinon avertit + vérifie que le mode fallback
est explicitement activé) ; latence d'un scoring type ; pour l'ancre :
un appel de labellisation sur 1 exemple fixture, coût estimé affiché.
Codes retour distincts (réseau / auth / capacité) pour le diagnostic.
`self-test` avec transport mocké.

### FR-3 · Garde-fous de dépense (mode API)
- `max_usd_per_run` dans la config ; `anchor_label.py` et `judge_harness.py`
  reçoivent un compteur (tokens × tarif configuré) et s'arrêtent proprement
  au plafond avec état repris (le pilote de 25 exemples de `first_judge.sh`
  stage 2 existe déjà pour projeter le coût — le garde-fou est la ceinture).
- Journal des dépenses par run (`spend.jsonl`).

### FR-4 · Runbook vLLM (mode local, livrable documentation)
- Procédure par machine : install, téléchargement + hash des poids
  (le hash réel remplace les placeholders du YAML — le `judge_id` devient
  vrai), unité systemd, prefix-caching, vérification `infra_check.py`.
- Dimensionnement mémoire (8B en bf16 ou AWQ sur 24 Go, avec les chiffres).

### FR-5 · Politique de bascule
- Documentée dans le README : on démarre en B6-lite ; la bascule B6-full se
  fait **par juge**, en re-calibrant (nouveau `judge_id` ⇒ recalibration
  obligatoire, contrat §4) ; les cohortes API restent rétractables comme les
  autres (l'enveloppe I4 les identifie).

## 5 · Cas limites

1. Fournisseur API sans logprobs découvert en cours de run → le harness doit
   échouer à la PREMIÈRE réponse sans logprobs si le mode fallback n'est pas
   explicitement activé (pas de dégradation silencieuse d'I3).
2. Changement de modèle silencieux côté fournisseur → `infra_check.py` en
   début de chaque cycle compare l'identifiant servi ; mismatch = juge
   quarantainé pour le cycle.
3. Plafond de dépense atteint en pleine calibration → état repris au ré-run
   (les sorties partielles sont valides, `anchor_label.py` a `--limit`).

## 6 · Plan de test et DoD

- `infra_check.py self-test` (mocks des trois familles d'échec).
- DoD B6-lite : `first_judge.sh --plan` propre, puis run réel jusqu'au stage 9
  sur le graphe du propriétaire ; `first_judge_report.md` produit (M1) ;
  dépenses journalisées sous plafond (M2) ; `README_infra.md`.
- DoD B6-full (optionnel, plus tard) : les 3 juges du YAML servis localement,
  hashes réels, `infra_check.py all` vert, un cycle nocturne complet en local.

## 7 · Risques

| Risque | Prob. | Mitigation |
|---|---|---|
| Aucun fournisseur ne sert le modèle voulu avec logprobs | moyenne | le fallback self-reported est contractuel et flaggé ; en dernier ressort B6-full d'abord |
| Coût ancre de la calibration sous-estimé | moyenne | pilote 25 + projection (déjà dans le runbook) + plafond FR-3 |
| Le mode lite s'installe comme définitif et le déterminisme est perdu durablement | moyenne | politique de bascule FR-5 écrite ; le rapport hebdo B7 affiche le mode courant comme dette |

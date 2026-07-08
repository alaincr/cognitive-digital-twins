# Annexes techniques du pack PRD — guide de lecture

**Date :** 2026-07-04. **Objet :** rendre les PRD B1–B7 directement
exécutables par un développeur qui découvre le dépôt, en épinglant les
contrats *réels* extraits du code existant (pas des specs) : schémas de
fichiers exacts, signatures, points d'insertion `fichier:ligne`, squelettes
de modules, découpage en tâches, fixtures de test, questions ouvertes avec
recommandation.

## Hiérarchie normative

1. `../00_gap_analysis.md` — périmètre de la boucle réduite (quoi/pourquoi).
2. `../PRD_B<n>_*.md` — exigences par brique (le PRD prime sur l'annexe).
3. `INTERFACES.md` — **le contrat inter-briques** : tout fichier échangé
   entre deux étapes du cycle, avec son schéma. Tout changement de schéma
   passe par une PR sur ce fichier.
4. `ANNEX_B<n>_*.md` — le « comment » par brique.
5. `../ADR-001.md` — la décision doctrinale qui débloque tout le reste
   (à ratifier AVANT de commencer).

## Parcours d'onboarding développeur (½ journée)

1. Lire `../SYNTHESE_analyse_critique.md` §1, §5, §7 (l'état des lieux honnête).
2. Lire `../ADR-001.md` — vérifier qu'il est ratifié ; sinon, le faire ratifier.
3. Lire `../00_gap_analysis.md` en entier.
4. Lire `INTERFACES.md` — c'est la carte.
5. Lancer la régression existante (SPEC-00 §5) :
   `for t in judge_harness zettel_prompts distill_judge prefilter; do python3 $t.py self-test || exit 1; done`
   puis `python3 roam_harvest.py demo --out-dir /tmp/reg` — tout doit être
   vert AVANT d'écrire une ligne.
6. Lire le PRD + l'annexe de sa brique, puis les fichiers existants cités
   par l'annexe (et seulement ceux-là).

## Découvertes faites en préparant ces annexes (à ne pas perdre)

- **B6 / mode API** : `judge_harness.py` score par `/completions` avec
  `echo=True` + logprobs du prompt — mode que la plupart des fournisseurs
  généralistes ne servent pas. Le choix du fournisseur se fait sur CE call
  (annexe B6 §1) ; sinon fallback `self-reported` contractuel.
- **B4 / durabilité** : l'existant persiste un snapshot `log.edn`
  (réécrit), pas un journal append-only — la conversion en
  `store/events.jsonl` write-ahead est le vrai livrable durabilité
  (annexe B4 §1), le reste du Clojure est plus complet que prévu
  (`-main`, offsets, dédup, exports existent déjà).
- **B7 / contamination** : `roam_harvest.py` et `prefilter.py` n'excluent
  pas encore l'espace `M/*` — patch obligatoire avant le premier write-back
  (sinon le système jugera ses propres écritures) ; livré avec B7 mais
  nécessaire dès B2 : **à faire dès que `M/*` existe** (annexe B7 §2).
- **B3 / review** : le merge `review_resolved.jsonl` → calset existe déjà
  (inline dans `first_judge.sh` stage 4) — l'extraire, pas le réécrire.
- **B5 / registre** : les champs des candidats `continues` doivent être
  validés contre `judge_prompts.REQUIRED_FIELDS` après
  `zettel_prompts.register()` — assertion imposée au self-test.

## Ordre de démarrage (rappel du chemin critique)

`ADR-001 → B6-lite + B1 (drop-folder d'abord) → WP-0 (first_judge.sh) →
M0 → B4 → B2 → B3` ; B5 et B7 parallélisables dès B1.

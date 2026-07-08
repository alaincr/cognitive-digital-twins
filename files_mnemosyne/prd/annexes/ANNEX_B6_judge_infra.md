# Annexe technique B6 — infra d'inférence (`infra_check.py` + configs)

**Complète :** `PRD_B6_judge_infra.md`. Le PRD prime en cas de conflit —
SAUF sur le point §1 ci-dessous, découvert en lisant le code, qui précise
fortement le « mode API » du PRD.

---

## 1 · ⚠️ Contrainte découverte : le harness exige `echo=True` sur `/completions`

`judge_harness.py` (l. ~151-172) score les labels ainsi :

```python
client.completions.create(model=…, prompt=prefix+label,
                          logprobs=0, echo=True, temperature=0.0, max_tokens=0)
```

c'est-à-dire : **endpoint completions (pas chat), avec écho des logprobs du
prompt** — il somme les logprobs des tokens du label *dans le prompt*.
Conséquences pour le mode B6-lite :

- **OpenAI ne supporte plus** `echo=True` avec logprobs sur /completions
  (retiré) ; les endpoints chat ne renvoient jamais les logprobs du prompt.
- Les fournisseurs compatibles sont ceux qui servent du **vLLM (ou
  équivalent) en mode completions brut** : c'est le cas de la plupart des
  hébergeurs de modèles open-weights (à vérifier UN PAR UN via
  `infra_check.py` — c'est précisément son travail).
- Donc le « mode API avec logprobs pleins » du PRD est réaliste, mais
  seulement chez un fournisseur open-weights type serving vLLM ; le
  fallback `self-reported` (I3) est le chemin probable chez les
  fournisseurs généralistes. `infra_check.py` doit tester **exactement ce
  call** (echo+logprobs+max_tokens=0), pas un ping générique.
- L'ancre n'est pas concernée (elle génère des labels via sortie JSON
  contrainte, pas de logprobs requis — PRD §3).

## 2 · Configs — formes exactes

### 2.1 `judges_config.example.yaml` (structure vérifiée)

```yaml
judges:
  qwen-a:
    judge_id: "qwen3-8b@<hash8>#p1"     # modèle@poids#prompt_version
    model: "Qwen/Qwen3-8B"              # nom servi exact (comparé par infra_check)
    family: "qwen"
    base_url: "http://<host>:8000/v1"
    api_key: "${JUDGE_API_KEY}"          # interpolation env au chargement
    prompt_version: 1
  anchor:
    judge_id: "anchor-large@api#p1"
    model: "<modele-ancre>"
    family: "anchor"
    base_url: "https://…/v1"
    api_key: "${ANCHOR_API_KEY}"
    prompt_version: 1
policy:
  alpha: {t0: 0.10, t1: 0.10, t2: 0.05}
  panel_k_t2: 2
  anchor_rho: 0.05
  drift_theta: 0.15
  outbox: "outbox.jsonl"
```

Ajouts B6 (nouvelles clés, rétro-compatibles — le harness ignore les clés
inconnues, à vérifier par self-test) :

```yaml
  qwen-a:
    …
    mode: "api-logprobs | api-selfreport | vllm-local"
    self_reported_ok: false     # doit être true explicitement pour le fallback
    price: {input_per_mtok: 0.20, output_per_mtok: 0.60}   # garde-fou dépense
spend:
  max_usd_per_run: 10.0
  ledger: "ops/spend.jsonl"
```

- En mode `api-logprobs`, le harness échoue à la PREMIÈRE réponse sans
  logprobs (cas limite 1 du PRD) — le patch harness est ≤ 20 lignes :
  lever si `response.choices[0].logprobs is None` et
  `self_reported_ok` faux.
- `judge_id` en mode API : `"<modele>@api-<fournisseur>-<date-calib>#p1"`
  (PRD §3) — le placeholder `<hash8>` ne sert qu'en local.

### 2.2 `spend.jsonl`

```json
{"run":"first_judge-2026-07-08","judge":"anchor","calls":612,
 "tokens_in":1480000,"tokens_out":61000,"usd":2.41,"ts":"…"}
```
Compteur incrémental (une ligne par tranche de 25 appels + une finale) —
la reprise après plafond relit la dernière ligne du run.

## 3 · `infra_check.py` — checks exacts par mode

| Check | api-logprobs | api-selfreport | vllm-local | ancre |
|---|---|---|---|---|
| endpoint joignable (`/models`) | ✓ | ✓ | ✓ | ✓ |
| modèle servi == `model` déclaré | ✓ | ✓ | ✓ | ✓ |
| completions echo+logprobs (le call du §1, sur un prompt de 20 tokens) | ✓ bloquant | ✗ (vérifie que `self_reported_ok: true`) | ✓ bloquant | — |
| latence d'un scoring 4 labels (info) | ✓ | ✓ | ✓ | — |
| labellisation 1 fixture (`fixtures/anchor_one.jsonl`) + coût affiché | — | — | — | ✓ |
| hash de poids déclaré ≠ placeholder | — | — | ✓ | — |

Codes retour : 0 ok · 10 réseau · 11 auth · 12 mismatch modèle ·
13 capacité (logprobs/echo absents) · 14 config invalide.
`--json` pour l'appel en début de cycle (B4 étape 0 optionnelle : mismatch
⇒ juge quarantainé pour le cycle, cas limite 2 du PRD).

## 4 · Sanity bounds à re-vérifier (déjà dans le code, à ne pas casser)

- Calibration : `T ∈ [0.3, 8]`, `q̂ ∈ (0, 0.9)` (README_harness §3,
  vérifié dans first_judge.sh stage 6).
- Calsets : ≥ 300 lignes par jtype préféré, 150 = plancher avec
  avertissement, < 150 = refus de calibrer (SPEC-01 §6).
- α : T2 (edge_type) = 0.05, T1 (continues) = 0.10 — first_judge.sh les
  passe déjà (`ALPHA_T2`/`ALPHA_T1`).
- Pilote ancre : 25 candidats (`PILOT=25`), puis projection de coût avant
  le run complet (`LIMIT_ET=350`, `LIMIT_CT=250`, `--double` ⇒
  2 appels/candidat, ~1,5–2,5 M tokens d'entrée pour 600 candidats —
  SPEC-01 §4). Le plafond FR-3 se règle au-dessus de cette projection.

## 5 · Runbook vLLM (B6-full) — chiffres pour FR-4

- Qwen3-8B bf16 ≈ 16 Go poids + KV cache → OK seul sur 24 Go (3090) avec
  `--gpu-memory-utilization 0.90 --max-model-len 8192`.
- AWQ 4-bit ≈ 6 Go → deux juges co-résidents possibles, au prix d'une
  recalibration (les logprobs changent ⇒ nouveau `judge_id`, contrat §4).
- `--enable-prefix-caching` obligatoire (le scoring echo partage le préfixe
  entre les 3–4 labels d'un même candidat — c'est le gros de la latence).
- Hash de poids réel : `sha256` du dossier snapshot HF (script fourni dans
  le README) → remplace le placeholder du YAML → `judge_id` devient vrai.
- systemd : `vllm-qwen.service`, `Restart=on-failure`,
  `ExecStartPre=infra_check.py …` en warm-up.

## 6 · Découpage en tâches

| # | Tâche | Est. |
|---|---|---|
| 1 | Split example/réel + `.gitignore` + interpolation `${ENV}` + self-test config | 0,5 j |
| 2 | `infra_check.py` (checks §3, mocks des familles d'échec, codes retour) | 1 j |
| 3 | Garde-fou dépense (compteur dans anchor_label + harness, ledger, plafond) | 0,5 j |
| 4 | Choix fournisseur : tester echo+logprobs chez 2–3 candidats via infra_check ; documenter le verdict | 0,5 j (ops) |
| 5 | (optionnel B6-full) runbook vLLM exécuté machine par machine | +3 j |

## 7 · Questions ouvertes

| Q | Recommandation |
|---|---|
| Quel fournisseur API pour le juge ? | critère unique : `infra_check` code 0 sur le check §1 ; sinon self-report durci (α réduit d'un cran, ex. 0.03 en T2) — chiffrer dans la config, pas dans le code |
| Quel modèle ancre ? | le plus fort disponible par API avec sortie JSON contrainte fiable ; le coût est borné par FR-3, la qualité de l'ancre est le plafond de qualité de TOUT le système — ne pas économiser ici |
| GPU local disponible aujourd'hui ? | si oui, B6-full direct pour le juge (2 j de plus mais déterminisme complet) ; l'ancre reste API dans tous les cas |

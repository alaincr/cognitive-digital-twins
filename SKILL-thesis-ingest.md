# SKILL: thesis-ingest

## Purpose
Ingest a research paper (raw PDF/text or pre-processed "Valore per la mia tesi" file) into the thesis wiki and update the central Scaffolding document.

---

## Trigger phrases
- "ingest paper [nome]"
- "aggiungi paper [nome]"
- "aggiorna scaffolding con [nome]"
- User passes a file from `raw/papers/` or a pre-processed `valore-*.md`

---

## Directory layout expected

```
raw/
  papers/
    <paper-slug>/
      paper.pdf (o .md)         ← originale
      riassunto.md               ← opzionale: già prodotto
      youtuber.md                ← opzionale: versione divulgativa
      valore-tesi.md             ← IL FILE PIÙ IMPORTANTE — può mancare
  calls/
    <call-slug>.md
  project/
    proposta/
      proposta-tesi.md
      feedback-claude.md
      base-teorica.md
    approfondimenti/
      <tema>.md

wiki/
  index.md
  log.md
  overview.md
  glossary.md
  scaffolding-tesi.md            ← documento centrale, aggiornato ad ogni ingest
  sources/
  concepts/
  analyses/
```

---

## Workflow

### Step 0 — Leggi il contesto
Prima di tutto:
1. Leggi `wiki/index.md` per orientarti
2. Leggi `wiki/scaffolding-tesi.md` per capire lo stato attuale della tesi
3. Leggi `wiki/glossary.md` per i termini canonici già definiti

### Step 1 — Determina il punto di ingresso

**Caso A — hai solo il paper raw (PDF o testo)**

Genera i tre layer usando esattamente le istruzioni qui sotto come prompt interni.

**Layer 1 — `youtuber`** (tono Simone Rizzo, AI Engineer divulgatore):
Analizza il paper rispondendo a questi punti:
1. **"Raga, guardate che hanno fatto"** — spiega l'idea centrale in modo semplice ma tecnico. Qual è il "trick" o l'intuizione che risolve il problema? Usa linguaggio da ingegnere (pesi, architetture, dati, segnali di reward…) ma evita dimostrazioni matematiche inutili.
2. **Perché è una figata** — qual è la novità vera? È un breakthrough o solo un piccolo miglioramento? Perché dovrebbe gasare?
3. **Come lo usiamo a lavoro?** — posso usarlo per ottimizzare un'architettura esistente? Riduce i costi di inferenza o training? Permette cose prima impossibili?
4. **Cosa c'è sotto il cofano** — riassumi la pipeline tecnica. Se dovessi scriverlo in Python domani, quali sono i componenti chiave?
5. **Il "Ma anche No"** — dove pecca? Troppe risorse? Dataset troppo specifico? Pronto per produzione o solo ricerca da laboratorio?

**Layer 2 — `riassunto`** (da consultare in futuro):
Produci un riassunto accademico strutturato: problema → metodo → risultati → limiti. Deve essere autocontenuto e consultabile senza rileggere il paper.

**Layer 3 — `valore-tesi`** (vedi istruzioni complete nello Step 2 qui sotto):
Genera il layer più importante contestualizzando il paper rispetto alla proposta di tesi. Vedi Step 2 per le istruzioni complete.

Dopo aver generato i tre layer, crea `wiki/sources/<paper-slug>.md`.

**Caso B — hai già il file `valore-tesi.md`**
1. Leggi il file direttamente
2. Salta la generazione di riassunto/youtuber (già fatto a mano)
3. Vai a Step 2

**Caso C — hai `valore-tesi.md` ma mancano `riassunto` e/o `youtuber`**
1. Usa il `valore-tesi.md` esistente per lo Step 2 (non rigenerarlo)
2. Genera solo i layer mancanti con i prompt del Caso A
3. Segnala all'utente quali layer hai generato e quali erano già presenti

### Step 2 — Estrai il valore per la tesi

Il `valore-tesi.md` va generato (Caso A) o letto (Caso B/C) tenendo sempre in mente il contesto specifico della tesi:

**Contesto tesi fisso** (sempre presente in testa durante questa analisi):
> La tesi propone un Cognitive Digital Twin (CDT) per una cella radio 5G su tre layer: fisico simulato (generatore metriche 3GPP), gemello digitale (Eclipse Ditto), cognitivo (LangGraph + LLM locali). Il contributo scientifico principale non è il sistema in sé ma il **framework di valutazione per agenti cognitivi specializzati** (Perception, Reasoning, Planning, Communication). Gap critico attuale: valutare Reasoning e Planning senza ground truth ovvio — strategie candidate: LLM-as-judge, multi-agent agreement, KG-based validation. Secondo contributo: benchmark comparativo Llama 3.1 8B / Mistral 7B / Phi-3 Mini / Qwen 3B su task 5G specifici.

Per ogni paper, rispondi a:
1. **In quali aree approfondisce** — rispetto ai tre contributi della tesi (architettura CDT, framework valutazione, benchmark modelli)
2. **Pro/contro** — punti di forza e limiti del paper nel nostro contesto d'uso
3. **Appunti contestualizzati per il relatore** — se il relatore chiedesse "cosa ne pensi di questo paper rispetto alla tua tesi?", cosa risponderesti? Include: come lo citeresti, dove entra nell'argomentazione, cosa prendi e cosa lasci. Se il paper non è utile, spiega esplicitamente perché.

Poi estrai le dimensioni strutturali per lo scaffolding:

| Dimensione | Domanda guida |
|---|---|
| **Argomento supportato** | Sostiene o sfida quale claim della proposta? |
| **Gap colmato** | Metodologico, empirico o teorico? |
| **Concetti chiave** | Quali termini/framework entrano nel glossario? |
| **Tensioni** | Contraddice qualcosa già nello scaffolding o in altri paper? |
| **Posizione nello scaffolding** | Contributo 1 (architettura), 2 (valutazione) o 3 (benchmark)? |

Se uno di questi punti è ambiguo, fai **al massimo 2 domande** all'utente prima di procedere.

### Step 3 — Aggiorna `wiki/scaffolding-tesi.md`

Regole di aggiornamento:
- **Non riscrivere** sezioni esistenti: aggiungi, annota, integra
- Inserisci il contributo del paper nella sezione rilevante con il formato:
  ```
  > **[Autore, Anno]** — <contributo in 1-2 righe>. [[sources/<paper-slug>]]
  ```
- Se il paper apre una nuova sezione non prevista, aggiungila con intestazione `###` e segnalala esplicitamente all'utente
- Se il paper contraddice qualcosa di esistente, aggiungi un blocco `⚠️ TENSIONE:` prima di aggiornare

### Step 4 — Aggiorna o crea pagine wiki secondarie

- `wiki/sources/<paper-slug>.md` — sempre, anche se esiste già (aggiorna)
- `wiki/concepts/<concetto>.md` — per ogni concetto nuovo o approfondito
- `wiki/glossary.md` — aggiungi termini canonici con definizione e fonte

### Step 5 — Aggiorna `wiki/index.md`

Aggiungi o aggiorna la riga della source. Aggiorna le righe di ogni pagina modificata.

### Step 6 — Scrivi entry in `wiki/log.md`

```
## [YYYY-MM-DD] ingest | <Titolo Paper — Autore, Anno>
Punto di ingresso: raw | valore-tesi
Pagine create: ...
Pagine aggiornate: scaffolding-tesi, ...
Tensioni rilevate: sì/no — <descrizione se sì>
Sezioni scaffolding toccate: ...
```

---

## Output atteso per ogni ingest

| File | Azione |
|---|---|
| `wiki/scaffolding-tesi.md` | Aggiornato con contributo del paper |
| `wiki/sources/<slug>.md` | Creato o aggiornato |
| `wiki/concepts/*.md` | 0–3 pagine create/aggiornate |
| `wiki/glossary.md` | Termini nuovi aggiunti |
| `wiki/index.md` | Righe aggiornate |
| `wiki/log.md` | Entry appesa |

---

## Formato pagina source

```yaml
---
title: <Titolo paper>
type: source
created: YYYY-MM-DD
updated: YYYY-MM-DD
authors: [Autore1, Autore2]
year: YYYY
tags: [metodo, dominio, concetti-chiave]
contributo-tesi: 1-architettura | 2-valutazione | 3-benchmark | nessuno
---
```

**Contributo principale** — 1 riga

## Riassunto
<problema → metodo → risultati → limiti>

## Youtuber
<layer divulgativo: trick centrale, perché è interessante, applicazioni pratiche, sotto il cofano, limiti>

## Valore per la tesi

**Aree approfondite:** ...
**Pro:** ...
**Contro:** ...

**Appunti per il relatore:**
> <Se il relatore chiede: cosa risponderesti? Come lo citi, dove entra nell'argomentazione, cosa prendi e cosa lasci. Se non è utile: perché.>

### Dimensioni strutturali
- Argomento supportato: ...
- Gap colmato: ...
- Posizione scaffolding: Contributo [1/2/3] — <sezione specifica>
- Tensioni: ...

## Concetti introdotti
- [[concetto-1]], [[concetto-2]]

## Related pages
- [[scaffolding-tesi]]
- [[concepts/...]]
```

---

## Note operative

- **Non modificare mai file in `raw/`**
- Se `valore-tesi.md` è già ottimo, fidati — non ri-analizzare il paper da zero
- Usa sempre i termini del `wiki/glossary.md`; se ne aggiungi uno nuovo, segnalalo
- Lo scaffolding è il documento vivo centrale: ogni paper deve lasciare traccia lì
- Se l'utente passa più paper in una sessione, processa uno alla volta e aggiorna il log per ognuno

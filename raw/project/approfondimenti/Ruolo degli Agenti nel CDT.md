# CDT 5G — Approfondimento architetturale

## Indice
1. [I quattro agenti cognitivi](#1-i-quattro-agenti-cognitivi)
2. [Il ruolo di Neo4j accanto a Eclipse Ditto](#2-il-ruolo-di-neo4j-accanto-a-eclipse-ditto)
3. [Normalizzazione KPI](#3-normalizzazione-kpi)
4. [Metodi di valutazione degli agenti cognitivi](#4-metodi-di-valutazione-degli-agenti-cognitivi)
5. [Mapping: sei funzioni cognitive → quattro agenti](#5-mapping-sei-funzioni-cognitive--quattro-agenti)

---

## 1. I quattro agenti cognitivi

Il layer cognitivo è implementato tramite LangGraph, che orchestra una pipeline sequenziale di quattro agenti specializzati. Ogni agente ha un input ben definito, una responsabilità precisa, e un output che diventa l'input del successivo.

### Pipeline end-to-end

```
Eclipse Ditto → [Perception] → [Reasoning] → [Planning] ←→ Neo4j KG
                                                   ↓
                                          [Communication]
                                                   ↓
                                          Report operatore
```

---

### 1.1 Perception Agent

**Responsabilità:** acquisizione e normalizzazione dello stato fisico.

Interroga Eclipse Ditto via REST o WebSocket, estrae i valori grezzi delle metriche 3GPP (RSRP, SINR, throughput downlink/uplink, latency, handover rate) e li normalizza in un formato standard prima di passarli al Reasoning Agent.

Il suo lavoro è puramente strutturale: nessun ragionamento, solo acquisizione e pulizia dati. Questo lo rende il più semplice da valutare — il ground truth è disponibile direttamente dal simulatore.

**Funzione cognitiva coperta:** Percezione (primario).

---

### 1.2 Reasoning Agent

**Responsabilità:** rilevamento anomalie e inferenza di root cause.

Riceve i KPI normalizzati e opera su tre livelli:

1. **Rilevamento anomalie** — identifica valori fuori soglia o pattern anomali.
2. **Correlazione multi-KPI** — mette in relazione KPI diversi per identificare pattern sistemici (es. RSRP basso + SINR degradato + aumento handover rate → possibile problema di copertura).
3. **Inferenza root cause** — produce una diagnosi in linguaggio naturale tramite il LLM locale.

Il punto critico da argomentare nella tesi è che questo non è un semplice sistema a soglie, ma inferenza causale che richiede ragionamento contestuale.

**Funzione cognitiva coperta:** Ragionamento (primario), Apprendimento (secondario, in senso lato).

---

### 1.3 Planning Agent

**Responsabilità:** traduzione della diagnosi in azioni concrete verificate.

Riceve la diagnosi dal Reasoning Agent e genera un piano d'azione tra tre categorie:

- Riconfigurazione parametri radio (es. potenza TX, tilt antenna)
- Riallocazione risorse di slice di rete
- Escalation a operatore umano

**Punto critico:** prima di proporre qualsiasi azione, il Planning Agent la valida contro il knowledge graph Neo4j per verificare ammissibilità operativa. Se il grafo segnala violazione di vincoli, l'azione viene scartata o riclassificata come escalation umana.

**Funzione cognitiva coperta:** Adattamento (primario), Decision-making autonomo (primario).

---

### 1.4 Communication Agent

**Responsabilità:** sintesi del ciclo cognitivo in linguaggio leggibile.

Non aggiunge nuova logica. Sintetizza l'intero percorso — cosa è stato percepito, cosa è stato dedotto, cosa si intende fare — in un report destinato all'operatore, includendo:

- Spiegazioni causali del ragionamento
- Livelli di confidenza stimati
- Motivazione delle azioni proposte

Rende il decision-making *spiegabile*, che nella letteratura recente è considerato parte integrante dell'autonomia responsabile.

**Funzione cognitiva coperta:** Decision-making autonomo (secondario, lato spiegabilità).

---

## 2. Il ruolo di Neo4j accanto a Eclipse Ditto

La domanda naturale è: se Eclipse Ditto gestisce già lo stato del twin, perché serve un secondo sistema?

### Eclipse Ditto — registro di stato temporale

Ditto sa com'è la cella *adesso* e com'era *prima*. Risponde a domande tipo:

- "Qual è il valore attuale di RSRP?"
- "Quando è cambiato l'ultimo parametro?"
- "Dammi la storia delle ultime N misurazioni."

È ottimizzato per dati **dinamici** che cambiano in continuazione. Espone REST API, WebSocket per notifiche real-time, e history degli stati con ordinamento temporale.

### Neo4j — registro di conoscenza strutturale

Neo4j non contiene misurazioni, ma **regole e relazioni stabili**:

- Quali parametri sono modificabili su questo tipo di nodo?
- Qual è il range operativo ammissibile per la potenza TX?
- Se abbasso il tilt di 2° su questa cella, quale cella adiacente viene impattata?
- Quali azioni richiedono approvazione umana obbligatoria?

Questa conoscenza è stabile nel tempo ma intrinsecamente relazionale — un grafo la rappresenta in modo molto più naturale di un key-value store.

### Come interagiscono in pratica

Quando il Planning Agent genera un'azione come "aumenta potenza TX di 3 dBm", interroga Neo4j con una query Cypher:

```cypher
MATCH (n:Node {id: $nodeId})-[:HAS_PARAM]->(p:Parameter {name: 'txPower'})
WHERE p.current + 3 <= p.maxAllowed
RETURN p
```

Se il grafo conferma che l'azione è ammissibile → il piano procede.  
Se viola un vincolo → l'azione viene scartata o escalata.

**Senza Neo4j**, il planner produrrebbe azioni plausibili ma potenzialmente invalide o pericolose per la rete reale.

---

## 3. Normalizzazione KPI

Il Perception Agent non si limita a leggere dati da Ditto: li trasforma prima di passarli al Reasoning Agent. La normalizzazione opera su due livelli.

### Normalizzazione numerica

Le metriche 3GPP hanno scale e unità radicalmente diverse:

| KPI | Unità | Range tipico |
|-----|-------|-------------|
| RSRP | dBm | −140 a −44 |
| SINR | dB | −20 a +30 |
| Throughput DL | Mbps | 0 a ~500 |
| Latency | ms | 1 a ~1000 |
| Handover rate | % | 0 a 100 |

La normalizzazione (min-max su [0,1] oppure z-score per KPI) rende i valori confrontabili e facilita il ragionamento del LLM, che altrimenti vedrebbe numeri di ordini di grandezza incomparabili.

### Arricchimento semantico

Invece di passare al LLM solo `rsrp: -105`, il Perception Agent costruisce un contesto strutturato:

```json
{
  "rsrp": {
    "value": -105,
    "unit": "dBm",
    "threshold_warning": -100,
    "threshold_critical": -110,
    "status": "degraded",
    "normalized": 0.31
  }
}
```

Questo riduce l'allucinazione: il modello non deve "sapere" da solo che -105 dBm è un valore preoccupante.

---

## 4. Metodi di valutazione degli agenti cognitivi

La strategia metodologica della tesi consiste nel scegliere, per ciascun agente, il metodo più adeguato alla natura del suo output. Non esiste un metodo universale.

### 4.1 Metriche strutturate classiche

**Applicabilità:** output deterministico con ground truth disponibile.

Usate principalmente per il **Perception Agent**: Precision, Recall, F1 per la classificazione di anomalie; MAE/RMSE per stime numeriche; exact match per output strutturati. Il simulatore fornisce il ground truth.

Sono le più solide ma applicabili solo dove il ground truth esiste in modo inequivocabile.

---

### 4.2 LLM-as-Judge

**Applicabilità:** output in linguaggio naturale senza ground truth univoco.

Un secondo LLM (o lo stesso con un prompt di valutazione dedicato) valuta l'output di un agente secondo criteri definiti a priori:

- Correttezza logica dell'inferenza
- Aderenza al contesto KPI fornito
- Completezza della diagnosi
- Assenza di allucinazioni

**Vantaggi:** scala bene a testo libero dove le metriche classiche non funzionano.  
**Limite:** introduce un secondo strato di incertezza — il giudice può sbagliare.

Metodo naturale per **Reasoning Agent** e **Communication Agent**.

---

### 4.3 Multi-agent consensus / agreement

**Applicabilità:** quando il ground truth manca e serve una stima di robustezza.

Lo stesso scenario viene sottoposto a più modelli diversi (Llama 3.1 8B, Mistral 7B, Phi-3 Mini, Qwen 3B) e si misura la concordanza delle risposte:

- **Alta concordanza** → la diagnosi è robusta, il task è ben definito.
- **Bassa concordanza** → caso ambiguo o limite del task, segnala incertezza.

Non è un oracolo di verità, ma è un indicatore di affidabilità relativa molto utile. È anche la base del **benchmark comparativo tra modelli**, che costituisce il terzo contributo scientifico della tesi.

---

### 4.4 RAGAS-inspired evaluation

**Applicabilità:** agenti che operano su contesto recuperato (Perception → Reasoning).

Nato per sistemi RAG, i principi sono trasferibili al contesto CDT:

| Dimensione | Significato nel CDT |
|-----------|---------------------|
| **Faithfulness** | L'output del Reasoning è fedele ai KPI forniti dal Perception? |
| **Answer relevance** | La diagnosi risponde effettivamente all'anomalia rilevata? |
| **Context precision** | I KPI passati erano pertinenti al problema? |
| **Context recall** | Il contesto copriva tutte le informazioni necessarie? |

---

### 4.5 KG-based validation

**Applicabilità:** Planning Agent esclusivamente.

Un'azione proposta viene verificata automaticamente contro Neo4j: se il grafo conferma ammissibilità → successo; se viola un vincolo → fallimento. Questa metrica è **oggettiva e automatizzabile** senza bisogno di giudici LLM o umani.

Dà una percentuale di "azioni valide / azioni totali proposte" per ciascun modello e scenario, direttamente confrontabile tra configurazioni.

---

### 4.6 Human evaluation

**Applicabilità:** Communication Agent, validazione finale.

Un campione di report viene valutato da persone con competenze di rete su scale di:

- Chiarezza espositiva
- Completezza informativa
- Correttezza causale (la spiegazione riflette la diagnosi?)
- Utilità operativa (l'operatore può agire in base al report?)

È il metodo più costoso ma fornisce la validazione finale per l'output rivolto all'utente reale.

---

### Riepilogo: metodo per agente

| Agente | Metodo primario | Metodo secondario |
|--------|----------------|-------------------|
| Perception | Metriche classiche (F1, MAE) | — |
| Reasoning | LLM-as-Judge | Multi-agent consensus |
| Planning | KG-based validation | Multi-agent consensus |
| Communication | Human evaluation | LLM-as-Judge |

---

## 5. Mapping: sei funzioni cognitive → quattro agenti

La letteratura sui CDT identifica sei funzioni cognitive fondamentali. La tesi ha quattro agenti. Il mapping non è uno-a-uno: alcune funzioni emergono da un singolo agente, altre dall'interazione tra agenti, altre ancora dall'architettura nel suo complesso.

> **Argomento centrale:** le sei funzioni non richiedono sei agenti separati perché alcune sono proprietà emergenti dell'architettura, altre sono responsabilità condivise lungo la pipeline.

---

### 5.1 Percezione → Perception Agent (primario)

La copertura è diretta e totale. Un agente dedicato, responsabilità esclusiva, output strutturato. Il simulatore 5G fornisce il ground truth per la validazione.

---

### 5.2 Ragionamento → Reasoning Agent (primario)

Il ragionamento non è rilevamento di soglie (quello sarebbe un sistema a regole). È correlazione multi-KPI e inferenza causale in linguaggio naturale. La verifica contro Neo4j nel Planning Agent è essa stessa una forma di ragionamento strutturato su vincoli — contributo secondario.

---

### 5.3 Memoria → architettura distribuita (trasversale)

Non esiste un Memory Agent dedicato. **Questa è una scelta progettuale consapevole**, non una lacuna, e va argomentata esplicitamente:

- **Memoria a breve termine:** lo state di LangGraph persiste il contesto lungo l'intera pipeline per ogni ciclo cognitivo.
- **Memoria a lungo termine:** Eclipse Ditto mantiene la storia completa degli stati del twin con ordinamento temporale.

Gli agenti non "ricordano" da soli — accedono a memoria esternalizzata. Questo è un pattern architetturale legittimo (stateless agents + external memory store) già consolidato nella letteratura sui sistemi multi-agente.

---

### 5.4 Apprendimento → copertura parziale, argomentare con cautela

È la funzione più difficile da coprire con LLM statici. L'apprendimento nel senso stretto (aggiornamento dei pesi) non avviene — i modelli sono frozen. Quello che si può argomentare:

- Il Reasoning Agent accumula pattern diagnostici nel contesto di sessione (few-shot implicito).
- Il Knowledge Graph Neo4j può essere aggiornato manualmente con nuove regole derivate dall'esperienza operativa.
- Il benchmark comparativo tra modelli può essere letto come selezione del miglior "apprendimento pregresso" per task specifici.

**Nota:** la tesi deve essere precisa terminologicamente su questo punto. Evitare di affermare apprendimento adattivo online se non implementato.

---

### 5.5 Adattamento → Planning Agent (primario)

Il Planning Agent genera e applica azioni correttive immediate in risposta alle anomalie rilevate. L'adattamento si distingue dall'apprendimento: è **reattivo e immediato**, non richiede aggiornamento di modelli interni.

Il Reasoning Agent contribuisce secondariamente: la qualità dell'adattamento dipende dalla qualità della diagnosi a monte.

---

### 5.6 Decision-making autonomo → pipeline completa (emergente)

Emerge dall'intera architettura, non da un singolo agente. Il punto chiave da argomentare:

L'autonomia è **vincolata e verificata**. Il Planning Agent non propone azioni arbitrarie — le valida contro Neo4j prima di eseguirle. Questo produce autonomia operativa entro confini definiti, che è esattamente ciò che la letteratura sui CDT per reti telecom richiede.

Il Communication Agent contribuisce rendendo il decision-making spiegabile — nella letteratura recente, la spiegabilità è considerata parte integrante dell'autonomia responsabile (XAI).

---

### Tabella di copertura

| Funzione cognitiva | Perception | Reasoning | Planning | Communication | Note |
|-------------------|:---------:|:---------:|:--------:|:-------------:|------|
| Percezione | **P** | — | — | — | |
| Ragionamento | — | **P** | S | — | |
| Memoria | S | S | S | S | Ditto + LangGraph state |
| Apprendimento | — | S | S | — | Parziale, argomentare con cautela |
| Adattamento | — | S | **P** | — | |
| Decision-making | — | S | **P** | S | Emergente dalla pipeline |

**P** = responsabile primario · **S** = contributo secondario/trasversale


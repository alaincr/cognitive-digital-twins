---
title: Scaffolding della Tesi
type: analysis
created: 2026-04-14
updated: 2026-04-14
sources: [proposta-tesi.md, feedback-claude.md, literature review 12 fonti]
tags: [thesis, scaffolding, structure]
---

# Scaffolding Tesi — Agentic Knowledge Graph for Digital Twins

**Nicolò Termine — Politecnico di Torino / Fondazione Ugo Bordoni / CINI**  
_Struttura argomentativa centrale della tesi — Aprile 2026_

---

## 💡 Domanda di Ricerca Centrale

Come si progetta, implementa e valida un **Cognitive Digital Twin completamente locale** che coordina agenti LLM specializzati per il decision-making autonomo su infrastrutture 5G in assenza di ground truth di valutazione?

---

## 🎯 Ipotesi / Claim Principale

È possibile costruire e valutare un sistema multi-agente LLM che:
1. Implementa le sei funzioni cognitive di un CDT (percezione, ragionamento, memoria, apprendimento, adattamento, decision-making)
2. Opera autonomamente su hardware consumer (M4 Pro 24GB) con modelli open-source quantizzati
3. Raggiunge _reasoning capability sufficientemente affidabile_ tramite un framework di valutazione multi-dimensionale che non dipende interamente da LLM-as-judge
4. Supera baseline comparativi su task 5G specializzati rilevati tramite fault injection controllata

---

## 📊 Struttura Capitoli Attesa

- **Cap. 1** — Introduzione e motivazione del problema
- **Cap. 2** — Background teorico (CDT, Funzioni Cognitive, Architetture MAS+DT)
- **Cap. 3** — Related Work e Positioning
- **Cap. 4** — Architettura del Sistema
- **Cap. 5** — Metodologia di Valutazione (CONTRIBUTO PRINCIPALE)
- **Cap. 6** — Implementazione e Esperimenti
- **Cap. 7** — Risultati e Benchmark Comparativo
- **Cap. 8** — Discussione, Limiti e Future Work

---

## 📚 Paper Integrati (Status)

### Blocco A — Teoria CDT
- [ ] Zheng et al. (2022) — Foundational definition di CDT
- [ ] Al-Haj Ali et al. (2025) — Sei funzioni cognitive + MMCI framework

### Blocco B — Pattern e Contesto
- [ ] RESTART NDT (2024) — Justificazione dominio 5G
- [ ] Burr et al. (2026) — Agentic AI risk taxonomy
- [ ] Pretel et al. (2024) — SLR 64 paper MAS+DT
- [ ] Kalyani & Collier (2024) — SLR 22 paper MAS+DT

### Blocco C — Blueprint Architetturale
- [ ] CogTwin IJCAI-25 — Dual-KG architecture
- [ ] Hasan & Nguyen (2026) — 6-layer agentic architecture
- [ ] Biju (2024) — LangGraph supervisor pattern

### Blocco D — Metodologia Valutazione
- [ ] MultiAgentBench (2025) — Metric framework
- [ ] Berkeley CS294 (2025) — LLM agents evaluation video

### Blocco E — Closest Prior Work
- [ ] WirelessAgent HKUST (2025) — LangGraph + dominio 5G

---

## ⚡ Tensioni Aperte

1. **Verificabilità vs. Flessibilità** — Il tradeoff tra reasoning simbolico (OWL + reasoner, verificabile ma rigido) e LLM locale (flessibile ma difficile da verificare). Il KG Neo4j è mitigazione parziale ma non completa.

2. **Ground Truth Assente per Reasoning** — Per il Perception Agent existe ground truth dal simulatore 3GPP. Per il Reasoning Agent (inferenza di cause radice) non esiste ground truth ovvio. Soluzione proposta: LLM-as-judge + multi-model agreement + KG-based validation, ma rimane rischio di autoreferenzialità.

3. **Local vs. Cloud** — WirelessAgent dimostra +44.4% su modelli cloud (DeepSeek-R1, Llama3.3-70B). La tesi usa modelli 3-8B locali. La domanda: quanto "cognitive capability" si conserva scendendo a modelli piccoli? Benchmark empirico sulla risposta.

4. **Stabilità vs. Optimality** — Il Planning Agent modifica l'ambiente (metriche KPI) con le sue azioni. C'è rischio di _performative prediction_: convergenza su soluzione "apparentemente ottimale" solo perché ha riscritto le condizioni di osservazione. Fault injection controllata come meccanismo di rilevazione.

---

## 🔴 Gap Ancora da Colmare

1. **Valutazione operativa del Reasoning Agent** — Letteratura (MultiAgentBench, Berkeley) suggerisce LLM-as-judge per task non-verificabili. La nostra proposta combina questo con KG-based validation per aumentare robustezza. Implementazione e validazione di questo ibrido è il lavoro principale della tesi.

2. **Benchmark comparativo su task domain-specific** — WirelessAgent copre "wireless task general" con modelli cloud. Gap: quale performance raggiungono Llama 8B, Mistral 7B, Phi-3 Mini, Qwen 3B on fault injection scenario 5G specifici? Inesplorato in letteratura.

3. **Decision Latency come dimensione critica** — MultiAgentBench e Berkeley non includono latency per task 5G time-sensitive. La nostra metodologia aggiunge questa metrica esplicitamente come domain-specific.

4. **Meta-cognitive layer** — Nessun paper analizzato (64 di Pretel et al., 22 di Kalyani, 12 ingestati finora) implementa auto-valutazione del ciclo cognitivo. È aspetto di future work in tutti i paper — opportunità di ricerca per la tesi o dichiararlo come out of scope.

---

## ✅ Prossimi Passi

1. **Fase 1 — Ingest cartaceo (2 giorni):** Convertire i 12 paper raw in pagine `wiki/sources/` con mapping esplicito a sezioni scaffolding
   
2. **Fase 2 — Chiarire empiricamente le tensioni (1 settimana):** Experimental design per benchmark comparativo Llama/Mistral/Phi-3/Qwen su fault injection scenario
   
3. **Fase 3 — Aggiornare scaffolding post-ingest:** Integrare findings empirici, aggiornare gap e tensioni, riflessioni su nuovo materiale

4. **Fase 4 — Setup infrastruttura:** Configurare simulatore 3GPP, Eclipse Ditto, Neo4j, Ollama localmente

5. **Fase 5 — Implementazione pipeline:** LangGraph con quattro agenti + framework di valutazione

6. **Fase 6 — Lint wiki finale:** Verificare contraddizioni, orfani, claim non supportati

---

## 1. Visione d'Insieme

La letteratura analizzata copre il periodo 2022–2026 e si distribuisce su **cinque blocchi tematici distinti**, ciascuno con un ruolo preciso nella tesi. La struttura non è casuale: ogni blocco risponde a una domanda specifica che il relatore potrebbe porre, e insieme costruiscono una narrazione coerente che porta dal "cosa è un CDT" al "come si valuta un CDT su rete 5G con LLM locali".

|Blocco|Paper|Domanda che risponde|
|---|---|---|
|**A — Teoria CDT**|Zheng et al. 2022, Al-Haj Ali et al. 2025|Cos'è un CDT? Quali funzioni deve avere?|
|**B — Pattern e Contesto**|RESTART, Burr 2026, Kalyani 2024, Pretel 2024|Perché nel dominio 5G? Dove si colloca il sistema nel rischio agentivo? Cosa dice la letteratura MAS+DT?|
|**C — Blueprint Architetturale**|CogTwin IJCAI-25, Hasan & Nguyen 2026, Biju 2024|Come si costruisce concretamente? Come si struttura il closed-loop? Come si implementa su LangGraph?|
|**D — Metodologia di Valutazione**|MultiAgentBench 2025, Berkeley CS294 2025|Come si misura un sistema multi-agent LLM?|
|**E — Closest Prior Work**|WirelessAgent HKUST 2025|Qual è il termine di confronto diretto? In cosa differisce la nostra proposta?|

---

## 2. Mappa per Sezioni della Tesi

## Capitolo 1 — Introduzione e Motivazione del Problema

**Fonti primarie:** RESTART NDT, Zheng et al. (2022), Burr et al. (2026)

Il capitolo si apre con la constatazione che le reti 5G sono sistemi cyber-fisici troppo dinamici per essere gestiti con strumenti passivi. Il paper RESTART (2024) fornisce la giustificazione tecnica: identifica il layer AI/cognitivo come componente non opzionale degli NDT e dichiara esplicitamente che l'AI nei Digital Twin non è "a supporting tool" ma "a core driver of strategic decision-making". Questa frase è citabile direttamente come apertura motivazionale.

Il problema fondamentale — i Digital Twin sono specchi passivi, gli agenti AI sono moduli isolati, serve chiudere il loop — è condiviso da Hasan & Nguyen (2026), che lo formalizzano con la frase "DTs are passive mirrors, AI agents are isolated reasoning modules — we need to close the loop". Usarla in apertura con doppia citazione (RESTART per il dominio 5G, Hasan & Nguyen per il paradigma CDT) rende l'introduzione solida e ben ancorata.

La tassonomia di Burr et al. (2026) fornisce la collocazione precisa del sistema nel panorama del rischio agentivo: la configurazione **(I, T, A) — Active Steering** — agency interna (agenti LLM), tight coupling (Eclipse Ditto WebSocket), model evolution adattiva (Reasoning Agent). Questo posizionamento va dichiarato nell'introduzione perché contestualizza tutte le scelte architetturali successive in un framework riconosciuto.

---

## Capitolo 2 — Background Teorico

**Fonti primarie:** Zheng et al. (2022), Al-Haj Ali et al. (2025), CogTwin (IJCAI-25)

**2.1 — Cos'è un Cognitive Digital Twin**

La definizione operativa di CDT viene da Zheng et al. (2022): "rappresentazione digitale aumentata con capacità cognitive, semanticamente interconnessa, che evolve lungo il lifecycle". Con 196+ citazioni, è la definizione più consolidata disponibile e va usata come apertura formale del Background senza doverla reinventare.

Zheng et al. identificano cinque caratteristiche fondamentali di un CDT: _cognitive capability, full lifecycle management, autonomy, continuous evolving_ e _DT-based design_. Ogni scelta architetturale della tesi deriva direttamente da questi requisiti — è il "cosa" del CDT. Lo stesso paper identifica il Knowledge Graph come **tecnologia abilitante mandatoria** per la cognizione nei CDT: questo è il fondamento teorico di Neo4j, non una scelta implementativa arbitraria.

**2.2 — Le Sei Funzioni Cognitive**

Al-Haj Ali et al. (2025) formalizza le sei funzioni cognitive target e introduce il framework MMCI (Multi-Modal Cognitive Interoperability) per valutarle. Le funzioni — percezione, attenzione, memoria, ragionamento, problem-solving, learning — mappano 1:1 sui quattro agenti della pipeline:

|Funzione CDT|Agente|Fonte primaria|Fonte operativa|
|---|---|---|---|
|Percezione|Perception Agent|Zheng et al. 2022|Al-Haj Ali 2025|
|Ragionamento|Reasoning Agent|Zheng et al. 2022|Al-Haj Ali 2025|
|Problem-solving|Planning Agent|Zheng et al. 2022|Al-Haj Ali 2025|
|Memoria|Neo4j KG + Ditto history|Zheng et al. 2022|CogTwin DKR/DIKG|
|Learning|Benchmark LLM comparativo|Zheng et al. 2022|CogTwin F&L Loop|
|Attenzione|Anomaly detection nel ciclo|Zheng et al. 2022|Al-Haj Ali 2025|

Questo mapping va presentato come tabella nel Background: dimostra che l'architettura non è casuale ma derivata dalla letteratura consolidata. Ogni funzione ha due citazioni indipendenti su due layer distinti — praticamente inattaccabile.

**2.3 — Il Blueprint Architetturale**

CogTwin (Mandal & O'Connor, IJCAI-25) è il riferimento architetturale principale. Propone una struttura cognitiva ibrida con Dual Knowledge Graph (DKR statico + DIKG dinamico) e un ciclo cognitivo in sei fasi che mappa quasi perfettamente sulla pipeline LangGraph. La scelta di Neo4j come knowledge graph non è solo teoricamente motivata (Zheng et al.) ma architetturalmente validata da un paper IJCAI-25 con struttura simile.

La differenza chiave rispetto a CogTwin: CogTwin usa ontologie OWL + reasoner simbolici, la tesi usa LLM + KG ibrido. Questo trade-off — flessibilità e linguaggio naturale a costo di verificabilità formale ridotta — va dichiarato proattivamente nel Background come scelta consapevole, non come limite. Il framework di valutazione è precisamente ciò che compensa questa riduzione di verificabilità formale.

---

## Capitolo 2 — Related Work

**Fonti primarie:** Kalyani & Collier ACM 2024, Pretel et al. IST 2024, Hasan & Nguyen 2026, WirelessAgent 2025, Biju 2024

**2.4 — MAS e Digital Twin: Stato dell'Arte**

Pretel et al. (Information and Software Technology, 2024) è la SLR più ampia disponibile: 64 paper analizzati (filtrati da 220). Fornisce due contributi fondamentali per il Related Work.

Primo: dimostra empiricamente che quasi nessun paper del corpus implementa bidirezionalità reale — la maggioranza costruisce _digital shadows_, non veri Digital Twin. Eclipse Ditto nella nostra architettura garantisce la proprietà DT3 (Entanglement forte), presente in pochissimi paper. La frase da scrivere: _"La proposta si distingue dalla maggioranza dei lavori analizzati in Pretel et al. (2024), che implementano digital shadows. Il presente CDT realizza la bidirezionalità completa tramite Eclipse Ditto."_

Secondo: la checklist delle 12 proprietà DT fornisce una griglia di confronto quantificabile. Il sistema copre 7/12 proprietà — superiore alla media dell'intera letteratura analizzata. Le tre proprietà rare coperte (DT3 Entanglement, DT8 Accountability, DT9 Augmentation) sono esattamente quelle che distinguono un CDT da un sistema di monitoraggio.

Kalyani & Collier (ACM Computing Surveys, Nov 2024) copre 22 paper con un approccio complementare. Valida il design a 3 layer (Physical → DT → Cognitive) come standard de facto, e conferma che KG e ontologie come backbone per il decision-making degli agenti è un pattern legittimo e documentato. Nessuno dei 22 paper usa LLM come layer cognitivo né applica MAS+DT al dominio 5G — gap esplicito dichiarato dagli autori come future work.

Pretel et al. introduce anche la classificazione in due pattern mutuamente esclusivi: _MAS with DT_ (agenti che usano il DT come sensore) e _MAS for DT_ (MAS che costruisce l'architettura del DT). La nostra tesi implementa **entrambi simultaneamente** — nessuno dei 64 paper analizzati ha questo dual pattern. È un contributo di design originale documentabile con una citazione diretta.

**2.5 — Agentic AI e Digital Twin: Sistemi Contemporanei**

Hasan & Nguyen (Elsevier Array, febbraio 2026) è il paper contemporaneo più vicino strutturalmente. Propone un'architettura a sei layer (Multimodal Perception → Knowledge & Data → Reasoning & Learning → Decision-Making → Action & Execution → Feedback & Adaptation) applicata a un grid energetico. I sei layer mappano quasi perfettamente i quattro agenti della nostra pipeline. Questo significa che l'architettura è teoricamente giustificata da letteratura peer-reviewed del 2026.

Il differenziante rispetto a Hasan & Nguyen su tre assi precisi:

|Dimensione|Hasan & Nguyen|Tesi|
|---|---|---|
|Knowledge Graph|❌ assente (usa LP + RFR)|✅ Neo4j con vincoli 3GPP|
|Valutazione agenti|❌ solo convergence time|✅ framework multi-dimensionale|
|Dominio + hardware|❌ grid energetico, cloud|✅ RAN 5G, M4 Pro locale|
|Benchmark multi-modello|❌ nessun confronto LLM|✅ Llama/Mistral/Phi-3/Qwen|

**2.6 — Closest Prior Work: WirelessAgent**

WirelessAgent (Tong et al., HKUST, arXiv 2025) è il termine di confronto diretto della tesi — l'unico paper che combina contemporaneamente LangGraph, agenti specializzati, e dominio 5G. Dimostra empiricamente che il pattern multi-agente LangGraph riesce a gestire task 5G complessi con +44.4% rispetto al prompt engineering diretto e -4.3% rispetto all'ottimo rule-based.

Il confronto con WirelessAgent è la sezione di Related Work più importante: è l'unico confronto quantitativo possibile. I loro modelli cloud (DeepSeek-R1, Llama3.3-70B) rappresentano l'upper bound di performance API. Il loro Llama3-8b (60.96% BW utilization) è il lower bound diretto — lo stesso range di modelli che usiamo noi, eseguito però su cloud. La domanda che la nostra tesi aggiunge: _"Quanto cognitive capability si riesce a ottenere da modelli 3-8B open-weight eseguiti localmente, in un'architettura CDT completa con DT Layer e Knowledge Graph, su task 5G con fault injection controllata?"_

Tre assenze in WirelessAgent che costituiscono i nostri contributi: (1) nessun Digital Twin Layer — lo stato vive solo nel global state volatile di LangGraph; (2) nessun Knowledge Graph strutturato — usano RAG flat su vector store; (3) nessuna valutazione del ragionamento intermedio — solo intent accuracy sull'output finale, esplicitamente indicato come future work.

**2.7 — LangGraph come Framework di Orchestrazione**

Biju (2024) è il riferimento implementativo per il pattern Supervisor+Agenti Specializzati su LangGraph. Valida la topologia con metriche baseline (accuracy 92-98%, latenza 2-4s su task isolati, stesso stack StateGraph) e fornisce la giustificazione documentata della scelta tecnologica. La risposta alla domanda del relatore "perché LangGraph e non AutoGen o CrewAI?" si compone di tre livelli: WirelessAgent (funziona su task 5G reali), MultiAgentBench (graph-mesh supera star su performance e token efficiency), Biju (pattern documentato e riproducibile).

_Nota tecnica per l'implementazione: il codice nel paper è pseudocode, non funzionante — la fonte autorevole per l'implementazione è la documentazione ufficiale LangGraph._

---

## Capitolo 3 — Architettura del Sistema

**Fonti primarie:** CogTwin, Hasan & Nguyen, Burr et al., Zheng et al.

La sezione di Design può aprire con la mappatura esplicita tra l'architettura proposta e i layer teorici della letteratura:

**Il modello a 5 layer funzionali di Zheng et al.** (Physical Entities → Data Ingestion → Model Management → Service Management → Twin Management) è quasi identico ai 3 livelli della nostra architettura — la nostra è una specializzazione applicativa dell'architettura di riferimento proposta nel paper, adattata al dominio 5G.

**Il Dual-KG di CogTwin** (DKR statico + DIKG dinamico) si mappa sul nostro Neo4j: il DKR corrisponde ai vincoli operativi 3GPP permanenti, il DIKG corrisponde allo stato storico delle anomalie e delle azioni correttive. Eclipse Ditto funge da layer di sincronizzazione tra il gemello digitale e il grafo dinamico.

**Neo4j ha ora tre giustificazioni indipendenti** da tre layer distinti, che vanno dichiarate esplicitamente nel Design:

1. Tecnologia abilitante mandatoria per la cognizione nei CDT (Zheng et al., 2022)
    
2. Pattern Dual-KG per separare knowledge stabile da dinamica (CogTwin, 2025)
    
3. Guardrail architetturale contro la deriva verso la configurazione Governor (Burr et al., 2026)
    

**Il concetto di DT come Decision Sandbox** (Hasan & Nguyen) si applica su due livelli nel nostro sistema: Eclipse Ditto come sandbox di stato (valida le percezioni contro uno stato ordinato temporalmente) e Neo4j come sandbox di vincoli (valida le azioni contro i vincoli 3GPP prima dell'esecuzione). Due sandbox distinte per due tipi di validazione diversa — pattern architetturale originale con citazione diretta.

---

## Capitolo 4 — Metodologia di Valutazione

**Fonti primarie:** MultiAgentBench (Zhu et al., 2025), Berkeley CS294 2025, WirelessAgent (per il gap), Al-Haj Ali et al. (per MMCI)

Questa è la sezione più originale della tesi — il contributo scientifico principale che colma un gap documentato da 12 fonti indipendenti e assente in almeno 71 paper (7 espliciti + 64 nel corpus di Pretel et al.).

**Il Framework a Tre Assi**

L'architettura di valutazione si costruisce incrociando MultiAgentBench (struttura metrica) con il video Berkeley CS294 (operatività per agente):

_Asse 1 — Capability:_ quanto è bravo l'agente a usare i tool (API Ditto, query Neo4j)? Valutazione rule-based, ground truth esplicita.

_Asse 2 — Reasoning Process:_ la catena Percezione→Ragionamento→Pianificazione→Comunicazione mantiene coerenza del contesto? Separazione tra Task Score e Coordination Score (da MultiAgentBench).

_Asse 3 — Outcome Validity:_ i KPI 5G migliorano dopo l'intervento dell'agente? RSRP/SINR/throughput recuperati sopra soglia nel simulatore — metrica finale verificabile indipendentemente da qualsiasi LLM nel loop.

**La Distinzione Verificabile/Non-Verificabile (da Berkeley CS294)**

|Agente|Tipo task|Metodo valutazione|Ground truth|
|---|---|---|---|
|Perception Agent|Verificabile|Rule-based / threshold|Simulatore Python|
|Planning Agent|Verificabile|Pass/Fail — vincoli KG|Neo4j 3GPP|
|Reasoning Agent|Non-verificabile|LLM-as-judge (modello più grande)|Nessuna|
|Communication Agent|Non-verificabile|LLM-as-judge + multi-model agreement|Nessuna|

Questa distinzione è **metodologicamente più robusta di MultiAgentBench stesso**: Zhu et al. usano LLM-as-judge per tutti gli assi (incluso Planning e Coordination Score) e ammettono il rischio di autoreferenzialità. La nostra proposta usa LLM-as-judge _solo dove non ha alternativa_, affiancando sempre una ground truth esterna dove disponibile.

**Il Problema Contamination È Risolto per Costruzione**

Il video Berkeley segnala il rischio di data contamination nei benchmark statici. I nostri fault injection scenarios sono generati dinamicamente dal simulatore con parametri variabili — non esistono in nessun dataset pubblico su cui i modelli LLM sono stati addestrati. La contamination è strutturalmente impossibile.

**La Metrica di Decision Latency**

Il video Berkeley ammette che la latenza è secondaria in contesti generici. Nel dominio 5G è critica — nessun benchmark di agenti cognitivi esistente include questa dimensione. La nostra metodologia introduce Decision Latency come metrica aggiuntiva domain-specific: è un contributo che emerge dall'applicazione al dominio telco e non dall'astrazione metodologica.

**Il Benchmark Comparativo dei Modelli Locali**

WirelessAgent testa modelli cloud (DeepSeek-R1, Llama3.3-70B, ecc.). La nostra tesi testa Llama 3.1 8B, Mistral 7B, Phi-3 Mini, Qwen 3B — tutti locali su M4 Pro. Il template sperimentale viene da MultiAgentBench: stessa pipeline, stesso evaluator, modelli diversi, scenari fissi. Il contributo aggiuntivo è che i task sono costruiti attorno a fault injection scenarios verificabili con ground truth da simulatore — nessuno dei due paper combina queste caratteristiche insieme.

---

## Capitolo 5 — Discussione, Limiti e Sviluppi Futuri

**Fonti primarie:** Burr et al. (2026), Al-Haj Ali et al. (2025), CogTwin, WirelessAgent

**Rischi da dichiarare proattivamente**

Il rischio di _performative prediction_ (Burr et al., 2026; Perdomo et al., ICML 2020): ogni azione correttiva del Planning Agent modifica la distribuzione delle metriche che il Perception Agent osserverà al ciclo successivo. Il sistema potrebbe convergere su una soluzione "apparentemente ottimale" solo perché ha riscritto le condizioni di osservazione. La fault injection controllata è progettata specificamente per rilevare questa convergenza patologica.

Il trade-off symbolic/LLM (Zheng et al., CogTwin, Al-Haj Ali): la sostituzione del reasoning simbolico (OWL + reasoner) con LLM locali guadagna flessibilità e linguaggio naturale a costo di verificabilità formale ridotta. Il KG Neo4j con vincoli 3GPP è il meccanismo che compensa parzialmente questa perdita — ma non la elimina. Va dichiarato come limite consapevole.

**Sviluppi futuri con ancoraggi nella letteratura**

- _Meta-Cognitive Layer_ — nessun paper analizzato implementa auto-valutazione del ciclo cognitivo. CogTwin lo nomina come future work, Al-Haj Ali lo formalizza teoricamente. È il gap più sofisticato da dichiarare.
    
- _Distributed Cognition / MAS multi-cella_ — CogTwin menziona più istanze collaborative; nel contesto 5G diventa coordinamento tra gNB multipli. Future work credibile con fondamento nella letteratura.
    
- _Fine-tuning domain-specific_ — WirelessAgent lo suggerisce ma non lo dimostra. È lo sviluppo naturale dopo la fase di benchmark con modelli general-purpose.
    
- _Traiettoria verso Governor (I,C,A)_ — Burr et al. descrive il percorso evolutivo da Active Steering verso configurazioni più autonome e i requisiti di governance necessari. Future work formalizzabile con citazione diretta.
    

---

## 3. I Quattro Contributi e la Loro Copertura Letteraria

## Contributo 1 — Architettura CDT per Rete Radio 5G

**Giustificazione teorica:** Zheng et al. (2022) + Al-Haj Ali (2025)  
**Blueprint:** CogTwin + Hasan & Nguyen  
**Posizionamento:** Burr et al. (configurazione Active Steering I,T,A)  
**Differenziazione:** WirelessAgent (manca DT Layer + KG strutturato)  
**Evidenza che il dominio è inesplorato:** Kalyani & Collier + Pretel et al. (zero paper 5G su 86 analizzati)

## Contributo 2 — Framework di Valutazione per Agenti Cognitivi

**Gap documentato da:** 12 fonti, assente in 71+ paper  
**Template metodologico:** MultiAgentBench (Zhu et al., 2025)  
**Operatività per agente:** Berkeley CS294 (2025)  
**Superamento di MultiAgentBench:** ibrido LLM-as-judge + ground truth esterna  
**Metrica originale:** Decision Latency (assente in tutta la letteratura analizzata)  
**Metrica finale:** Outcome Validity (KPI 5G nel simulatore — indipendente da LLM)

## Contributo 3 — Benchmark Comparativo LLM Open-Source Locali

**Template sperimentale:** MultiAgentBench (stessa pipeline, modelli diversi, scenari fissi)  
**Spazio non coperto:** WirelessAgent (copre solo modelli cloud ≥ 70B; Llama3-8b è il loro modello più debole)  
**Lower bound di riferimento:** WirelessAgent Llama3-8b = 60.96% BW utilization  
**Domanda di ricerca:** quanto cognitive capability è estraibile da modelli 3-8B locali in architettura CDT completa su task 5G?

## Contributo 4 — Riproducibilità su Hardware Consumer

**Motivazione:** nessun paper analizzato testa LLM in configurazione fully local su hardware non-enterprise  
**Contesto:** WirelessAgent usa API cloud; Hasan & Nguyen usa cloud; CogTwin non specifica  
**Implicazione pratica:** deployment edge-side su gNB reali senza dipendenza da API esterne

---

## 4. La Risposta ai Professori per Ogni Domanda Probabile

**"Come si colloca il tuo sistema nel panorama dei CDT?"**

> _"Il CDT proposto implementa le cinque caratteristiche fondamentali identificate da Zheng et al. (2022) e le sei funzioni cognitive formalizzate da Al-Haj Ali et al. (2025). Secondo la tassonomia di Burr et al. (2026), si colloca nella configurazione Active Steering (I,T,A): agency interna, tight coupling real-time, model evolution adattiva."_

**"Perché Neo4j?"**

> _"Neo4j è giustificato da tre layer distinti della letteratura: come tecnologia abilitante per la cognizione nei CDT (Zheng et al., 2022), come pattern Dual-KG per separare knowledge stabile da dinamica (CogTwin, 2025), e come guardrail architetturale contro la deriva verso la configurazione Governor — dove il sistema ottimizza metriche ridefinite invece delle metriche 3GPP standard (Burr et al., 2026)."_

**"Come validi gli agenti LLM?"**

> _"Il framework di valutazione adotta la struttura milestone-based di MultiAgentBench (Zhu et al., 2025), estesa con la distinzione verificabile/non-verificabile del Berkeley CS294 (2025). Per Perception e Planning Agent uso ground truth esterna (simulatore e KG Neo4j); per Reasoning e Communication uso LLM-as-judge solo dove non ho alternativa. La metrica finale è l'Outcome Validity: recupero dei KPI 5G nel simulatore, indipendente da qualsiasi LLM nel loop di valutazione. È una valutazione metodologicamente più robusta di WirelessAgent (2025), che misura solo l'output finale senza valutare il ragionamento intermedio."_

**"Qual è il lavoro più vicino al tuo e come ti differenzi?"**

> _"WirelessAgent (Tong et al., HKUST 2025) condivide dominio 5G e architettura LangGraph. Li superiamo su tre punti: (1) aggiungiamo un Digital Twin Layer via Eclipse Ditto per stato persistente e ordinato temporalmente, assente in WirelessAgent; (2) sostituiamo il RAG flat con un Knowledge Graph strutturato che verifica deterministicamente i vincoli 3GPP; (3) affrontiamo esplicitamente la valutazione del reasoning intermedio, che WirelessAgent dichiara come future work."_

**"Quali sono i limiti del tuo approccio?"**

> _"Il principale è il trade-off tra flessibilità e verificabilità formale: sostituire il reasoning simbolico OWL+reasoner con LLM locali guadagna adattabilità a scenari di anomalia nuovi, ma riduce la verificabilità formale delle inferenze. Il Knowledge Graph Neo4j con vincoli 3GPP compensa parzialmente questa perdita, ma non la elimina. Inoltre, il rischio di performative prediction (Burr et al., 2026) — convergenza su soluzioni apparentemente ottimali perché il sistema ha modificato le condizioni di osservazione — è reale e mitigato dalla fault injection controllata ma non eliminabile strutturalmente."_

---

## 5. Cosa Manca Ancora (Segnalato ma Non Ancora Analizzato)

| Fonte                       | Blocco target    | Motivo                                                                                 |
| --------------------------- | ---------------- | -------------------------------------------------------------------------------------- |
| **MAJ-EVAL (NeurIPS 2025)** | Blocco D         | Fondamento teorico specifico per LLM-as-judge multi-agente — completerebbe il Blocco D |
| **Zhang et al. (2021)**     | Baseline tecnica | DT + multi-agent DRL per vehicular edge computing — evoluzione DRL→LLM                 |
| **Xu et al. (2023)**        | Baseline tecnica | DT-driven scheduling edge computing — analogo al resource allocation RAN               |
| **Latsou et al. (2023)**    | Baseline tecnica | Anomaly detection + bottleneck ID con MAS classico — baseline per Reasoning Agent      |
| **Galuzin et al. (2022)**   | Baseline tecnica | KG + agenti per decision-making real-time — precursore diretto dello stack             |
| **G-SPEC**                  | Baseline tecnica | Baseline specifica 5G per calibrazione simulatore                                      |

Questi sei paper vanno integrati come _baseline da citare e superare_ nel capitolo di confronto — non richiedono analisi approfondita, ma una citazione contestualizzata per mostrare da dove parte lo stato dell'arte nel dominio.
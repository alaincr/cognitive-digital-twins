## Mappa Gerarchica dei Concetti

Legenda: `→` dipende da / richiede / estende

---

### Prerequisiti (già noti)

```
Teoria dei Grafi
├── Grafi orientati e non
├── Proprietà strutturali (cicli, connettività)
└── → base per: Knowledge Graph, LangGraph StateGraph

Fondamenti ML/AI
├── Supervised/Unsupervised learning
├── Neural Networks base
└── → base per: Transformer, LLM

Architetture Software
├── REST API
├── Event-driven / Pub-Sub
└── → base per: Eclipse Ditto, LangGraph
```

---

### Livello 1 — Fondamenti Abilitanti

Questi vanno studiati prima di tutto il resto.

```
TRANSFORMER & LLM FOUNDATIONS
├── Attention mechanism
├── Architettura Transformer (Vaswani 2017)
├── Pre-training e fine-tuning
├── Emergent capabilities
├── Limiti strutturali
│   ├── Allucinazioni
│   ├── Context window
│   └── Statelessness
└── → abilita: Prompt Engineering, LLM locali, Agenti LLM

CICLO AUTONOMICO MAPE-K
├── Monitor → Analyze → Plan → Execute
├── Knowledge base come stato condiviso
├── Origini (IBM Autonomic Computing 2003)
└── → abilita: ZSM, CDT cognitive loop, pipeline agenti

GRAFI DI CONOSCENZA — BASE
├── Nodi, archi, proprietà
├── Labeled Property Graph (Neo4j)
├── Differenza KG vs database relazionale
├── Cypher query language
└── → abilita: KG operativo, GraphRAG, memoria agenti
```

---

### Livello 2 — Concetti Dominio

Studiabili in parallelo dopo il Livello 1.

```
DIGITAL TWIN
├── Definizione Grieves (origine)
├── Componenti: physical entity, virtual entity, data/service
├── Ciclo bidirezionale fisico↔digitale
├── Differenza DT vs simulazione
│   ├── Simulazione: unidirezionale, what-if
│   └── DT: bidirezionale, real-time, stato persistente
├── Tassonomia DT
│   ├── Product DT
│   ├── Process DT
│   └── System DT
└── → estende in: Cognitive Digital Twin

5G — DOMINIO APPLICATIVO
├── Architettura base gNB
├── KPI radio
│   ├── RSRP (potenza segnale ricevuto)
│   ├── SINR (qualità segnale)
│   ├── Throughput DL/UL
│   ├── Latenza
│   └── Handover rate
├── Network slicing (concetto)
├── Parametri configurabili del nodo radio
└── → abilita: interpretazione metriche simulatore, azioni Planning Agent

PROMPT ENGINEERING
├── Zero-shot / Few-shot
├── Chain-of-Thought (Wei 2022)
├── ReAct pattern (Yao 2023)
│   ├── Reasoning trace
│   └── Action → Observation loop
├── Structured output / JSON mode
└── → abilita: design system prompt agenti, tool use
```

---

### Livello 3 — Architetture Avanzate

Richiedono tutto il Livello 2.

```
COGNITIVE DIGITAL TWIN
├── DT + componente cognitiva
├── Sei funzioni cognitive
│   ├── Perception → raccolta e normalizzazione dati
│   ├── Reasoning → inferenza, root cause analysis
│   ├── Memory → stato storico e strutturato
│   ├── Learning → aggiornamento modello/comportamento
│   ├── Adaptation → modifica parametri operativi
│   └── Autonomous Decision-Making → azione senza supervisore
├── Differenza CDT vs DT classico
├── CDT per network management
└── → istanziato in: architettura della tesi

MULTI-AGENT SYSTEMS — LLM BASED
├── Fondamenti MAS classici
│   ├── Agente: percezione + azione + obiettivo
│   ├── Agenti reattivi vs deliberativi
│   └── Coordination mechanisms
├── LLM-based agents
│   ├── LLM come motore di ragionamento
│   ├── Tool use / function calling
│   ├── Memory esterna
│   └── Planning capabilities
├── Pattern architetturali
│   ├── Orchestrator → subagents
│   ├── Peer-to-peer collaboration
│   └── Blackboard shared state
├── Tipi di memoria negli agenti
│   ├── In-context (breve termine)
│   ├── Vector store (semantica)
│   └── Knowledge Graph (strutturata)
└── → implementato in: LangGraph pipeline

ZERO-TOUCH NETWORK MANAGEMENT (ZSM)
├── ETSI ZSM architecture
├── Closed-loop automation
├── Livelli di autonomia L0→L5 (TMF)
├── Intent-based networking
└── → contestualizza: output del Planning Agent
```

---

### Livello 4 — Stack Implementativo

Richiedono Livello 3 + familiarità pratica.

```
ECLIPSE DITTO
├── Modello Things/Features
│   ├── Thing = entità digitale
│   ├── Feature = proprietà/stato
│   └── Attribute = metadato
├── API REST per read/write stato
├── WebSocket per notifiche real-time
├── Change history e temporal ordering
├── Decoupling source → consumer
└── → ruolo: stato centralizzato del CDT

LANGGRAPH
├── StateGraph vs MessageGraph
├── Node = agente/funzione
├── Edge = transizione
├── Conditional edge = routing logico
├── State = contesto condiviso tra nodi
├── Checkpointing = persistenza stato
├── Human-in-the-loop pattern
└── → ruolo: orchestrazione pipeline cognitiva

NEO4J — OPERATIVO
├── Schema del KG operativo 5G
│   ├── Nodi: parametri, vincoli, azioni
│   ├── Archi: relazioni causali, dipendenze
│   └── Policy encoding
├── Cypher per query di validazione
├── Integrazione con LangGraph
└── → ruolo: validazione azioni Planning Agent

LLM LOCALI — DEPLOYMENT
├── Ollama: serving locale, API compatibile OpenAI
├── Quantizzazione Q4/Q8: trade-off qualità/velocità
├── Modelli specifici
│   ├── Llama 3.1 8B → reasoning generale
│   ├── Mistral 7B → instruction following
│   ├── Phi-3 Mini → task strutturati leggeri
│   └── Qwen 3B → baseline leggero
└── → ruolo: backend cognitivo degli agenti
```

---

### Livello 5 — Contributo Scientifico

Il livello più alto, costruito su tutto il resto.

```
VALUTAZIONE SISTEMI LLM-BASED
├── Perché le metriche classiche non bastano
│   ├── BLEU/ROUGE: solo similarità lessicale
│   └── Accuracy: non cattura qualità del reasoning
├── LLM-as-Judge
│   ├── Principio: un LLM valuta l'output di un altro
│   ├── Bias noti (position bias, verbosity bias)
│   ├── Mitigazione: valutatori multipli, rubric esplicita
│   └── → applicato a: Reasoning Agent, Communication Agent
├── RAGAS (adattato)
│   ├── Faithfulness: l'output è fedele al contesto?
│   ├── Relevancy: l'output risponde al task?
│   └── → applicato a: Perception Agent, Reasoning Agent
└── Structured output evaluation
    ├── Ground truth da simulatore (fault injection)
    ├── Precision/Recall su anomalie rilevate
    └── → applicato a: Perception Agent, Planning Agent

AGREEMENT TRA AGENTI (contributo originale)
├── Stesso task → N modelli diversi → confronto output
├── Metriche di agreement
│   ├── Consistency: stessa conclusione?
│   ├── Coherence: ragionamento compatibile?
│   └── Confidence calibration
├── Quando usarlo
│   ├── Task ad alta incertezza (root cause)
│   └── Decisioni ad alto impatto (reconfigurazione)
└── → produce: benchmark comparativo modelli

BENCHMARK COMPARATIVO MODELLI
├── Task costruiti su scenari fault injection
│   ├── Scenario 1: degradazione RSRP graduale
│   ├── Scenario 2: congestione burst
│   └── Scenario 3: session failure
├── Dimensioni di valutazione per agente
│   ├── Perception: accuracy, latenza
│   ├── Reasoning: correctness root cause, faithfulness
│   ├── Planning: azioni valide vs KG, relevancy
│   └── Communication: completeness, readability
└── → output: tabella comparativa modelli per task
```

---

### Vista delle Dipendenze Critiche

```
Per implementare          Devi sapere
─────────────────────────────────────────────────────
Perception Agent      →  Ditto API + Prompt Engineering
                          + metriche 5G

Reasoning Agent       →  Chain-of-Thought + ReAct
                          + anomaly detection domain

Planning Agent        →  KG operativo + Cypher
                          + ZSM azioni correttive

Communication Agent   →  Structured output
                          + NL generation evaluation

Valutazione           →  LLM-as-Judge + RAGAS
                          + agreement pattern
                          + ground truth da simulatore

Benchmark             →  Tutti gli agenti funzionanti
                          + framework valutazione completo
```

---

### Percorso di Studio Settimana per Settimana

```
Settimana 1-2   Livello 1 completo
                + MAPE-K + Transformer + KG base

Settimana 3-4   Livello 2 completo
                + DT/CDT + 5G KPI + Prompt Engineering

Settimana 5-6   Livello 3 completo
                + MAS LLM-based + ZSM + LangGraph concettuale

Settimana 7-8   Livello 4 — pratico
                + Ditto hands-on + LangGraph hands-on
                + Neo4j hands-on + Ollama setup

Settimana 9+    Livello 5 — metodologia
                + LLM-as-Judge + RAGAS + agreement design
                → inizio implementazione
```

---

# Pilastri Teorici

### Pilastro 1 — Digital Twin

**Fondamenti**

- Definizione e storia del DT (Grieves 2002)
- Differenza DT vs simulazione vs shadow model
- Ciclo bidirezionale fisico↔digitale
- Tassonomia: DT di prodotto, processo, sistema

**Digital Twin per reti e infrastrutture**

- DT in ambito industriale (Industry 4.0)
- DT per reti di telecomunicazione
- Standard emergenti (ITU-T, ETSI)

**Cognitive Digital Twin**

- Definizione e differenza rispetto al DT classico
- Le sei funzioni cognitive (perception, reasoning, memory, learning, adaptation, autonomous decision-making)
- Architetture CDT in letteratura
- CDT per network management

**Paper fondativi**

- Grieves, M. (2014). _Digital Twin: Manufacturing Excellence through Virtual Factory Replication_ — il testo originale che formalizza il concetto
- Grieves & Vickers (2017). _Digital Twin: Mitigating Unpredictable, Undesirable Emergent Behavior in Complex Systems_ — in Transdisciplinary Perspectives on Complex Systems, Springer
- Tao et al. (2018). _Digital Twin-Driven Product Design, Manufacturing and Service_ — Industrial Manufacturing journal, molto citato

**CDT specifico**

- Minerva, R., Lee, G.M., Crespi, N. (2020). _Digital Twin in the IoT Context_ — IEEE, buon punto di partenza sul CDT
- Semeraro et al. (2021). _Digital Twin Paradigm: A Systematic Literature Review_ — Computers in Industry, utile per la tassonomia
- Zheng et al. (2022). _Cognitive Digital Twins for Smart Manufacturing_ — cerca questo filone su IEEE Xplore con keywords "cognitive digital twin"

**Per le sei funzioni cognitive**

- Cerca su Google Scholar: _"cognitive digital twin" "perception reasoning memory"_ — i paper che citano esplicitamente le sei funzioni sono recenti (2022-2024)

---

### Pilastro 2 — Reti 5G e Network Management

**Fondamenti 5G**

- Architettura gNB e core network
- Metriche KPI principali: RSRP, SINR, throughput, latenza, handover rate
- Concetto di network slicing
- Parametri configurabili e loro effetti

**Autonomous Network Management**

- Ciclo autonomico MAPE-K (Monitor, Analyze, Plan, Execute)
- Zero-Touch Network Management (ZSM, ETSI)
- Livelli di autonomia nelle reti (TMF IG1230)
- Anomaly detection nelle reti radio

**Standard di riferimento (lettura selettiva, non integrale)**

- 3GPP TS 38.214 — parametri radio NR, utile per capire RSRP/SINR
- ETSI GS ZSM 002 — Zero-touch Network Management, architettura di riferimento
- TMF IG1230 — Autonomous Networks livelli di autonomia (da L0 a L5)

**Paper**

- Benzaid & Taleb (2020). _AI-Driven Zero Touch Network and Service Management_ — IEEE Communications Magazine, ottimo overview
- Polese et al. (2023). _Understanding O-RAN_ — IEEE Communications Surveys, contesto architetturale moderno
- Sun et al. (2020). _Application of Machine Learning in Wireless Networks_ — IEEE Communications Surveys, background su anomaly detection in 5G

---

### Pilastro 3 — Large Language Models

**Fondamenti**

- Architettura Transformer
- Pre-training, fine-tuning, RLHF
- Concetto di emergent capabilities
- Limiti strutturali: allucinazioni, context window, knowledge cutoff

**LLM locali e open source**

- Quantizzazione (GGUF, Q4, Q8) e impatto su performance
- Ollama e llama.cpp come runtime
- Confronto modelli: Llama 3, Mistral, Phi-3, Qwen

**Prompt Engineering**

- Zero-shot, few-shot, chain-of-thought
- Structured output e JSON mode
- System prompt design per agenti specializzati

**Fondamenti teorici**

- Vaswani et al. (2017). _Attention Is All You Need_ — l'originale Transformer, obbligatorio almeno concettualmente
- Brown et al. (2020). _Language Models are Few-Shot Learners_ — il paper GPT-3, introduce few-shot prompting
- Wei et al. (2022). _Emergent Abilities of Large Language Models_ — TMLR, importante per capire i limiti e le capacità

**LLM locali**

- Touvron et al. (2023). _Llama 2: Open Foundation and Fine-Tuned Chat Models_ — Meta, paper del modello base
- Jiang et al. (2023). _Mistral 7B_ — paper del modello
- Documentazione Ollama: [ollama.com/docs](http://ollama.com/docs) — pratica, aggiornata
- llama.cpp GitHub repository — per capire quantizzazione e deployment

**Prompt Engineering**

- Wei et al. (2022). _Chain-of-Thought Prompting Elicits Reasoning in LLMs_ — Google, fondamentale
- Yao et al. (2023). _ReAct: Synergizing Reasoning and Acting in LLMs_ — introduce il pattern ReAct usato negli agenti
- White et al. (2023). _A Prompt Pattern Catalog to Enhance Prompt Engineering_ — pratico e sistematico

---

### Pilastro 4 — Sistemi Multi-Agente

**Fondamenti teorici**

- Definizione di agente e ambiente
- Agenti reattivi vs deliberativi vs ibridi
- Multi-Agent Systems (MAS) classici
- Differenza MAS classico vs LLM-based MAS

**Pattern architetturali**

- Orchestrator-subagent pattern
- Peer-to-peer agent collaboration
- Blackboard architecture
- Tool use e function calling

**Framework pratici**

- LangGraph: state management, grafi stateful, conditional edges
- Confronto: AutoGen, CrewAI, LlamaIndex Workflows
- NVIDIA AgentIQ (menzionato da Andrea)

**Memoria negli agenti**

- Memoria a breve termine (in-context)
- Memoria a lungo termine (vector store, knowledge graph)
- Episodic vs semantic memory negli agenti LLM

**Fondamenti teorici classici**

- Wooldridge & Jennings (1995). _Intelligent Agents: Theory and Practice_ — Knowledge Engineering Review, il testo classico sui MAS
- Russell & Norvig — _Artificial Intelligence: A Modern Approach_ (cap. agenti) — il manuale, sicuramente già incontrato

**LLM-based Multi-Agent Systems**

- Park et al. (2023). _Generative Agents: Interactive Simulacra of Human Behavior_ — Stanford, paper seminale sugli agenti LLM
- Wu et al. (2023). _AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation_ — Microsoft, paper di AutoGen
- Wang et al. (2024). _A Survey on Large Language Model based Autonomous Agents_ — survey completo, ottimo per orientarsi

**LangGraph**

- Documentazione ufficiale: [langchain-ai.github.io/langgraph](http://langchain-ai.github.io/langgraph) — è la fonte primaria
- LangChain blog: blog.langchain.dev — articoli pratici su pattern architetturali
- Harrison Chase (2024). _LangGraph: Multi-Agent Workflows_ — talk disponibile su YouTube

**Pattern specifici**

- Yao et al. (2023). _Tree of Thoughts: Deliberate Problem Solving with LLMs_ — per reasoning complesso
- Shinn et al. (2023). _Reflexion: Language Agents with Verbal Reinforcement Learning_ — pattern di self-reflection negli agenti

---

### Pilastro 5 — Valutazione di Sistemi LLM-based

**Fondamenti della valutazione NLP**

- Metriche classiche: precision, recall, F1
- BLEU, ROUGE (e loro limiti per il reasoning)
- Human evaluation vs automatic evaluation

**Valutazione LLM moderna**

- LLM-as-judge: principi, bias, best practices
- RAGAS: faithfulness, answer relevancy, context precision
- MT-Bench e benchmarking multi-task
- Structured output evaluation

**Valutazione sistemi multi-agente**

- Agent benchmark (AgentBench, ToolBench)
- Task decomposition evaluation
- Agreement tra agenti come metodo di validazione
- Consistency e coherence tra agenti multipli

**Valutazione specifica per anomaly detection**

- Ground truth construction da fault injection
- Precision/recall per root cause identification
- Latenza del ciclo cognitivo come metrica

**Fondamenti**

- Gehrmann et al. (2022). _Repairing the Cracked Foundation: A Survey of Obstacles in Evaluation Practices in NLP_ — ACL, panoramica critica
- Chang et al. (2023). _A Survey on Evaluation of Large Language Models_ — IEEE TNNLS, survey completo

**LLM-as-Judge**

- Zheng et al. (2023). _Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena_ — NeurIPS, il paper fondativo
- Bai et al. (2023). _FairEval: Evaluating Fairness of ChatGPT_ — sui bias del giudice LLM, importante per capire i limiti

**RAGAS**

- Es et al. (2023). _RAGAS: Automated Evaluation of Retrieval Augmented Generation_ — paper originale
- Documentazione: [docs.ragas.io](http://docs.ragas.io)

**Valutazione multi-agente**

- Liu et al. (2023). _AgentBench: Evaluating LLMs as Agents_ — benchmark per agenti in ambienti reali
- Chen et al. (2024). _AgentEval: A Framework for Automatic Evaluation of LLM Agents_ — recente, molto pertinente
- Per l'agreement tra agenti: cerca _"LLM ensemble" "multi-agent consistency"_ su arXiv 2023-2024

---

### Pilastro 6 — Knowledge Graph

**Fondamenti**

- Grafi property vs RDF vs labeled property graph
- Ontologie e schema design
- Neo4j e Cypher query language

**KG per network management**

- Encoding di vincoli operativi
- Policy representation
- KG come meccanismo di validazione

**KG + LLM**

- GraphRAG: retrieval su grafi per LLM
- KG come memoria strutturata per agenti
- Hallucination reduction tramite KG grounding

**Fondamenti**

- Hogan et al. (2021). _Knowledge Graphs_ — ACM Computing Surveys, la survey di riferimento
- Robinson et al. — _Graph Databases_ (O'Reilly, disponibile online) — pratico su Neo4j

**KG + LLM**

- Edge et al. (2024). _From Local to Global: A GraphRAG Approach to Query-Focused Summarization_ — Microsoft, il paper GraphRAG
- Pan et al. (2024). _Unifying Large Language Models and Knowledge Graphs: A Roadmap_ — IEEE TKDE, survey sul tema
- Trajanoska et al. (2023). _Enhancing Knowledge Graph Construction Using Large Language Models_ — applicativo

**Neo4j specifico**

- Documentazione Neo4j: [neo4j.com/docs](http://neo4j.com/docs) — Cypher query language
- Neo4j Graph Academy: [graphacademy.neo4j.com](http://graphacademy.neo4j.com) — corsi gratuiti, ottimo punto di partenza pratico

---

### Pilastro 7 — Infrastruttura e Stack Tecnologico

**Eclipse Ditto**

- Modello Things/Features
- API REST e WebSocket notifications
- Change history e temporal ordering
- Confronto con alternative (AWS IoT Twin Maker, Azure Digital Twins)

**LangGraph in profondità**

- StateGraph e MessageGraph
- Node, edge, conditional edge
- Checkpointing e persistenza dello stato
- Human-in-the-loop pattern

**Architetture event-driven**

- Pub/sub pattern
- Message broker (concetti base)
- Decoupling tra produttori e consumatori di dati

**Eclipse Ditto**

- Documentazione ufficiale: eclipse.dev/ditto/docs
- Schmid et al. (2018). _Eclipse Ditto: Digital Twins for IoT_ — paper introduttivo degli autori
- GitHub repository: eclipse-ditto/ditto — per capire architettura interna

**LangGraph avanzato**

- LangGraph documentation: conceptual guides section — state, memory, human-in-the-loop
- Articolo: _LangGraph vs AutoGen vs CrewAI_ — cerca su Medium/Towards Data Science, confronti pratici aggiornati al 2024

**Architetture event-driven**

- Richards, M. — _Software Architecture Patterns_ (O'Reilly, free) — cap. event-driven architecture
- Per Ditto + WebSocket: documentazione ufficiale è sufficiente

---

### Ordine di Studio Consigliato

```
1. MAPE-K + ZSM          → capire il problema che si risolve
2. DT → CDT              → capire il contenitore
3. Fondamenti LLM        → capire lo strumento
4. MAS + LangGraph       → capire l'architettura
5. KG + Neo4j            → capire la memoria strutturata
6. Valutazione LLM/MAS   → capire il contributo scientifico
7. Eclipse Ditto         → capire lo stack specifico
8. 5G KPI e parametri    → capire il dominio applicativo
```

### Risorse Trasversali

**Per trovare paper**

- Google Scholar — ricerca generale
- [arXiv.org](http://arXiv.org) ([cs.AI](http://cs.AI), [cs.NI](http://cs.NI), [cs.MA](http://cs.MA)) — preprint aggiornati
- IEEE Xplore — per tutto ciò che riguarda 5G e reti
- Semantic Scholar — utile per trovare paper correlati tramite citation graph

**Survey da leggere per orientamento rapido**

- Xi et al. (2023). _The Rise and Potential of Large Language Model Based Agents: A Survey_ — arXiv, 80+ pagine ma molto completo
- Wang et al. (2023). _A Survey on Large Language Model based Autonomous Agents_ — Frontiers of CS

**Blog tecnici da seguire**

- blog.langchain.dev
- [newsletter.theaiedge.io](http://newsletter.theaiedge.io)
- [bair.berkeley.edu/blog](http://bair.berkeley.edu/blog) — Berkeley AI Research

---
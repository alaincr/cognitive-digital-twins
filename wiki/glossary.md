---
title: Glossario della Tesi
type: concept
created: 2026-04-14
updated: 2026-04-14
sources: []
tags: [terminology, reference]
---

# Glossario — Agentic Knowledge Graph for Digital Twins

Nomenclatura canonica e definizioni stabilite dalla tesi.

---

## Core Concepts

### Digital Twin (DT)
Rappresentazione digitale sincronizzata di un'entità o processo fisico, in grado di memorizzare stato, cronologia e abilitare simulazioni.

### Cognitive Digital Twin (CDT)
Digital Twin aumentato con capacità cognitive (percezione, ragionamento, memoria, apprendimento) che opera autonomamente e evolve lungo il lifecycle dell'entità. Riferimento canonico: **Zheng et al. (2022)**.

### Knowledge Graph (KG)
Struttura semantica (grafo di nodi e archi etichettati) che rappresenta fatti, relazioni e vincoli operativi di un dominio. Nel contesto della tesi: rappresentazione dei vincoli 5G e delle rule di validazione sul Planning Agent.

### Multi-Agent System (MAS)
Insieme di agenti autonomi specializzati coordinati per raggiungere un obiettivo comune tramite comunicazione strutturata.

### LLM (Large Language Model)
Modello neurale addestrato su corpus di testo, esposto come API o ospitato localmente (Ollama + quantizzazione).

---

## Funzioni Cognitive (sei pilastri CDT)

Seguono la tassonomia di **Zheng et al. (2022)** e **Al-Haj Ali et al. (2025)**.

### Percezione (Perception Agent)
Acquisizione, normalizzazione e strutturazione dei dati di osservazione dal sistema fisico. Output: metriche 3GPP canoniche.

### Ragionamento (Reasoning Agent)
Inference su anomalie, correlazioni, cause radice. Utilizza logica naturale + KG. Output: diagnosi strutturata con gradi di confidenza.

### Pianificazione (Planning Agent)
Traduzione di diagnosi in azioni concrete, validazione contro vincoli operativi memo nel KG, selezione dell'azione ottimale.

### Comunicazione (Communication Agent)
Sintesi della pipeline percezione-decisione in esplicazione leggibile all'utente con argumentazione causale.

### Memoria
Persistenza dello stato e della cronologia tramite Eclipse Ditto + Neo4j.

### Apprendimento / Adattamento
Evoluzione continua del KG e dei parametri di decision-making (out of scope per MVP, definito come future work).

---

## Terminologia Dominio 5G

### gNB (gNodeB)
Antenna base 5G. Nel simulatore: generatore di metriche 3GPP.

### RSRP (Reference Signal Received Power)
Potenza del segnale di riferimento ricevuto. Metrica di qualità del segnale.

### SINR (Signal-to-Interference-plus-Noise Ratio)
Rapporto segnale-interferenza-rumore. Indicatore di congestione e degradazione di canale.

### Handover
Transizione di una comunicazione da una cella a un'altra. Tasso di fallimento è indicatore di instabilità.

### Throughput Downlink/Uplink
Velocità di trasferimento dati. Degradazione indica anomalie di risorse o congestione.

### Latenza
Ritardo end-to-end. Metrica critica per servizi real-time (eMBB, URLLC).

### KPI (Key Performance Indicator)
Metrica aggregata di performance. Nel contesto tesi: composite su RSRP, SINR, throughput, latenza.

---

## Terminologia Architetturale

### Eclipse Ditto
Piattaforma per gestione del digital twin: sincronizzazione stato, WebSocket notifications, API REST. Nel contesto: backbone della représentation digitale (livello 2/3 dell'architettura).

### Neo4j
Database grafo per Knowledge Graph. Nel contesto: memorizzazione vincoli operativi 5G e rule di validazione Planning.

### LangGraph
Framework per orchestrazione di agenti multi-step con state management esplicito (LangChain + Langgraph). Nel contesto: runtime della pipeline cognitive.

### Ollama
Server locale di LLM with quantizzazione Q4/Q5. Nel contesto: hosting di Llama 3.1 8B, Mistral 7B, Phi-3 Mini, Qwen 3B su M4 Pro.

### 3GPP
Standard di telecomunicazione. Nel contesto: specifica del formato di metriche simulate.

---

## Metodologia Valutazione

### LLM-as-Judge
Utilizzo di un LLM come valutatore di qualità di output di un altro LLM. Applicabile a Reasoning Agent.

### Multi-Agent Agreement
Strategia di validazione tramite consensus tra multipli agenti su task identici. Usata per aumentare confidenza su Reasoning.

### KG-based Validation
Validazione di azioni Planning contro vincoli memorizzati nel KG. Ground truth: grafo di vincoli operativi.

### Fault Injection Scenario
Iniezione controllata di anomalie nel simulatore fisico per generare ground truth di diagnosi corrette (Reasoning) e azioni corrette (Planning).

---

## Varianti Terminologiche Segnalate

- **"Gemello Digitale Cognitivo"** vs **"Cognitive Digital Twin"** — usare CDT come acronimo canonico in testo inglese, traslatare in italiano solo quando necessario.
- **"Agente"** vs **"Agent"** — preferenza italiana "agente" in corpo tesi, "agent" in code comments e paper.
- **"Knowledge Graph"** vs **"Knowledge Base"** — usare KG per strutture orientate a grafi (Neo4j), KB per vocabolari piatti. Nel contesto tesi: KG.

---

## Related Pages
- [[overview]]
- [[scaffolding-tesi]]
- [[style-rules]]

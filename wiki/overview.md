---
title: Overview della Tesi
type: analysis
created: 2026-04-14
updated: 2026-04-14
sources: [proposta-tesi.md, feedback-claude.md]
tags: [thesis, summary, architecture]
---

# Overview — Agentic Knowledge Graph for Digital Twins

Sintesi ad alto livello della tesi e del suo contributo scientifico.

---

## Titolo e Scope

**Titolo:** Agentic Knowledge Graph for Digital Twins  
**Autore:** Nicolò Termine  
**Ateneo:** Politecnico di Torino  
**Partner:** Fondazione Ugo Bordoni / CINI  
**Data:** Aprile 2026

---

## Problema Centrale

Le reti 5G sono sistemi cyber-fisici troppo dinamici per essere gestiti con strumenti passivi. I Digital Twin attuali sono specchi statici; gli agenti AI sono moduli isolati. **Come si combina cognizione distribuita con rappresentazione digitale per ottenere decision-making autonomo su infrastrutture 5G?**

---

## Ipotesi Principale

Un Cognitive Digital Twin (CDT) locale, riproducibile su hardware consumer (M4 Pro 24GB), può supportare le sei funzioni cognitive fondamentali identificate in letteratura (percezione, ragionamento, memoria, apprendimento, adattamento, decision-making) coordinando agenti LLM open-source orchestrati tramite LangGraph.

---

## Contributi Scientifici

### Contributo 1 — Architettura del CDT (Ingegneristico)

**Che cosa:** Design e implementazione completa di un sistema a tre layer:
- **Livello Fisico Simulato** — generatore di metriche 3GPP con iniezione di anomalie
- **Livello DT** — Eclipse Ditto come backbone di rappresentazione digitale sincronizzata
- **Livello Cognitivo** — LangGraph + agenti LLM specializzati (Perception, Reasoning, Planning, Communication)

**Perché rilevante:** Dimostra fattibilità end-to-end e maturità architetturale.

### Contributo 2 — Framework di Valutazione per Agenti Cognitivi (Metodologico — CORE)

**Che cosa:** Metodologia sistematica per valutare agenti cognitivi specializzati quando ground truth è assente:
- **Perception Agent** → metriche strutturate classiche (accuracy vs. simulatore)
- **Reasoning Agent** → LLM-as-judge + multi-agent agreement + KG-based validation
- **Planning Agent** → validazione contro vincoli KG + fattibilità operativa
- **Communication Agent** → readability + completeness + fidelity causale

**Perché rilevante:** Affronta problema aperto della valutazione LLM in contesti specializzati. È il **baricentro scientifico della tesi**, suggerito da feedback di Andrea in call.

### Contributo 3 — Benchmark Comparativo di Modelli (Empirico)

**Che cosa:** Valutazione sistematica di LLM open-source su task specifici 5G:
- Modelli: Llama 3.1 8B, Mistral 7B, Phi-3 Mini, Qwen 3B
- Task: reasoning su KPI anomalie, planning correttive, comunicazione diagnostica
- Metriche: accuracy, latenza, token efficiency, memoria

**Perché rilevante:** Output pubblicabile. Contributo empirico complementare ai due precedenti.

---

## Stack Tecnologico

| Layer | Tecnologia | Ruolo |
|---|---|---|
| Fisico Simulato | Python + generatore metriche 3GPP | Fonte dati, ground truth |
| Digital Twin | Eclipse Ditto + REST API | Sincronizzazione stato, event stream |
| Knowledge Graph | Neo4j + Cypher | Vincoli operativi, validazione |
| Orchestrazione Agenti | LangGraph + LangChain | State management, routing |
| LLM | Ollama (Q4 quantizzazione) | Modelli locali: Llama, Mistral, Phi-3, Qwen |
| Interfaccia Utente | Report testuale + metriche grafiche | Esplicazione diagnostica |

---

## Ipotesi Critiche di Ricerca

1. **Un LLM open-source autonomo può inferire cause radice di anomalie 5G con affidabilità sufficiente a supporto decisionale** → Testato tramite benchmark
2. **Multi-agent agreement aumenta significativamente la fiducia nelle diagnosi LLM in assenza di ground truth** → Testato tramite valutazione Reasoning Agent
3. **Vincoli operativi memorizzati in KG sono sufficienti a validare azioni di Planning** → Testato tramite fault injection
4. **Hardware consumer (M4 Pro) con modelli quantizzati supporta pipeline end-to-end in real-time** → Testato tramite benchmark latenza e throughput

---

## Scopo NON Incluso (Future Work)

- Addestramento fine-tuning dei modelli su 5G-specific task
- Apprendimento continuo e adattamento dinamico del KG
- Multi-domain CDT (solo 5G in questa tesi)
- Orchestrazione su cluster distribuiti

---

## Related Pages
- [[scaffolding-tesi]]
- [[glossary]]
- [[personas]]

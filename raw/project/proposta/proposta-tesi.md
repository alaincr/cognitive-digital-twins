# Proposta di Tesi

## Titolo
> Cognitive Digital Twins


###  Proposta di Tesi

Questa tesi propone la progettazione e l'implementazione di un Gemello Digitale Cognitivo (CDT) per una cella radio 5G. La piattaforma sfrutta Eclipse Ditto come livello di rappresentazione digitale di un'infrastruttura fisica simulata, mentre un framework coordinato di agenti cognitivi — alimentati da LLM open-source eseguiti localmente — costituisce il nucleo intelligente del sistema. L'obiettivo centrale è dimostrare che un'architettura completamente locale, riproducibile su hardware consumer, può supportare le sei funzioni cognitive fondamentali identificate in letteratura per i CDT: percezione, ragionamento, memoria, apprendimento, adattamento e decision-making autonomo.

### **Architettura del Sistema**

Il sistema è organizzato su tre livelli funzionali:

- **Livello Fisico Simulato** — un generatore di dati Python replica il comportamento di un nodo radio 5G (gNB), emettendo metriche conformi allo standard 3GPP (RSRP, SINR, throughput downlink/uplink, latenza, tasso di handover) con iniezione controllata di anomalie (degradazione del segnale, congestione, fallimenti di sessione). Le metriche vengono inviate in tempo reale a Eclipse Ditto tramite API REST.
- **Livello del Gemello Digitale** — Eclipse Ditto funge da registro di stato centralizzato per il sistema fisico. Oltre alla memorizzazione, espone la cronologia delle modifiche, notifiche WebSocket in tempo reale e una rappresentazione semanticamente strutturata delle entità, disaccoppiando le sorgenti dati dai consumatori cognitivi e garantendo che gli agenti operino sempre su uno stato coerente e ordinato temporalmente.
- **Livello Cognitivo** — implementato tramite LangGraph, che orchestra un grafo di agenti specializzati con stato:
    - l'Agente di Percezione interroga Ditto e normalizza le metriche grezze;
    - l'Agente di Ragionamento rileva anomalie, correla i KPI e inferisce le cause radice tramite ragionamento in linguaggio naturale su un LLM locale;
    - l'Agente di Pianificazione traduce le diagnosi in azioni correttive concrete (riconfigurazione dei parametri radio, riallocazione delle risorse di slice, escalation verso operatori umani), verificandone la fattibilità rispetto a un knowledge graph Neo4j che codifica i vincoli operativi; (iv) l'Agente di Comunicazione sintetizza l'intero ciclo percezione-decisione in un report leggibile dall'utente con spiegazioni causali e livelli di confidenza stimati.

### **Pipeline Decisionale Principale**

Il ciclo cognitivo end-to-end segue una sequenza strutturata che rispecchia il ciclo di gestione autonomica presente negli standard di rete di nuova generazione:

_Percezione dello Stato → Ragionamento sulle Anomalie → Pianificazione delle Azioni (verificata dal KG) → Spiegazione in Linguaggio Naturale_

### **Piano di Implementazione**

L'implementazione comprende: l’utilizzo del simulatore di metriche 5G con scenari di anomalia configurabili; il deployment e la configurazione di Eclipse Ditto come backbone del gemello digitale; la costruzione del knowledge graph Neo4j che codifica le policy di rete e i vincoli operativi; l'integrazione della pipeline multi-agente LangGraph con LLM ospitati localmente (Llama 3.1 8B, Mistral 7B, Phi-3 Mini, Qwen 3B); e la validazione end-to-end tramite esperimenti controllati di iniezione di guasti. Verrà consegnato un prototipo pienamente funzionante che esegue l'intera pipeline cognitiva in modo autonomo su hardware consumer.

---


# White Paper on Network Digital Twin — RESTART Grand Challenge 4

> **Progetto:** RESTART (Italian Research Initiative)  
> **Focus:** Esporre l'infrastruttura di rete come servizio attraverso i Network Digital Twin  
> **Team:** Riccardo Marini, Francesca Conserva, Maurizio Fodrini, Simone Bizzarri, Marco Becattini, Antonio Iera, Enrico Vicario, Gianluca Cena, Stefano Scanzio, Francesco Linsalata, Roberto Pegurri, Franco Matera, Davide Borsatti, John Sengendo, Carlos Antonio Gomez Vega, Andrea Conti, e altri.

---

## Executive Summary

I **Network Digital Twin (NDT)** rappresentano un cambio di paradigma nella progettazione, gestione e ottimizzazione delle reti moderne. Fornendo una controparte digitale in tempo reale dei componenti e dei comportamenti di rete, gli NDT abilitano simulazione avanzata, analisi predittiva e decision-making autonomo su domini eterogenei.

**Senza una visione architetturale condivisa**, gli NDT rischiano di rimanere soluzioni proprietarie a silos, con scalabilità e interoperabilità limitate. Il white paper propone un **framework modulare e federato** per sbloccare il pieno potenziale degli NDT su reti pubbliche e private, fisse e mobili, fino a infrastrutture non-terrestri.

### Contributi chiave del paper
- Analisi completa degli **enabler tecnologici** (data acquisition, AI-driven orchestration, edge-cloud infrastructure)
- Analisi del **landscape di standardizzazione** (3GPP, ETSI ZSM, ITU-T, TM Forum) con gap identificati e punti di convergenza
- **Nuova architettura** basata sui concetti di *Digital Hat* (DH) e *Digital Hub* (DTH) per composizione, federazione e lifecycle management collaborativo degli NDT
- **Call to action** per la standardizzazione armonizzata con modelli condivisi, interfacce aperte e framework di governance

---

## 1. Introduzione: Cos'è un NDT?

Un **Digital Twin (DT)** è un framework composto da tre elementi:
1. Il **sistema fisico** target (rete, nodo, software, servizio…)
2. La sua **controparte virtuale** software-based (il DT vero e proprio)
3. Un **communication link adattivo** che garantisce sincronizzazione continua bidirezionale

Un **NDT** è un DT applicato a una rete o a una sua porzione — cattura la piena complessità della rete (elementi, funzioni, comportamenti) e la mantiene aggiornata in tempo reale tramite:
- Data acquisition scalabile e Big Data storage
- Data fusion e AI-driven analytics
- Adaptive modeling per riflettere immediatamente modifiche operative, anomalie emergenti o cambiamenti ambientali

### Concetti correlati
- **Nested NDT** (3GPP TS 28.561): gerarchia di NDT interconnessi e orchestrati
- **Digital Twin Network — DTN** (ITU-T Y.3090): collezione di DT interagenti che forniscono una rappresentazione coordinata end-to-end di una rete fisica complessa

> **ITU-T vs 3GPP:** ITU-T enfatizza l'orchestrazione di molti DT interagenti; 3GPP si focalizza sulla collaborazione tra twin network-centrici durante le fasi di simulazione/emulazione. RESTART sintetizza e unifica le due visioni.

---

## 2. Key Enablers

Lo stack tecnologico necessario per abilitare un NDT efficace.

### 2.1 Data Availability

| Categoria | Descrizione |
|---|---|
| **Geographic Nationwide Data** | Dati territoriali e infrastrutturali large-scale (GIS, LiDAR, satellite imagery, drone) — dovrebbero essere pubblicamente accessibili |
| **Business-Specific Local Data** | Dataset proprietari da sensori, robot, IoT, processi produttivi — essenziali per decision-making strategico |

**Federated Data Exchange:** accesso controllato per diritti utente, consistenza dei dati, comunicazione cross-standard, sicurezza robusta. Elimina i limiti delle interazioni one-to-one tra operatori e vendor.

### 2.2 Ray Tracing per la modellazione radio

Tecnica fondamentale per la modellazione del canale radio nell'NDT:

| Metodo | Tipo | Pro | Contro |
|---|---|---|---|
| **Ray Launching / SBR** | Approssimato, empirico | Scalabile su ambienti grandi | Non preciso sui percorsi esatti |
| **Ray Tracing / Image Method** | Deterministico, esaustivo | Alta fedeltà, multipercorso preciso | Costo computazionale alto |
| **Approcci ibridi** | RT + RL | Bilanciamento accuratezza/efficienza | Ancora in ricerca |

Il RT deterministico modella guadagni complessi, ritardi, Doppler shift → ricostruzione precisa della struttura multipath del canale wireless. **Non è opzionale in un NDT**: la fedeltà delle applicazioni a livello superiore dipende direttamente dal realismo del modello di propagazione sottostante.

### 2.3 Cloud Infrastructure e Edge Computing

- **Data Centers (privati o pubblici):** AWS, Azure, GCP per storage centralizzato e processing massivo
- **Edge computing:** riduce latenza, abilita decision-making locale, mantiene requisiti di privacy inviando solo dati selezionati ai DC centrali
- **Modello ibrido:** ottimizzazione locale (edge) + ottimizzazione globale (cloud remoto) — entrambi necessari in NDT reali

### 2.4 Software Defined Networking (SDN)

SDN è il layer programmabile che collega i moduli NDT alla rete reale:
- Gestisce il Control Plane via software → configurazione centralizzata, adattamento dinamico
- Facilita comunicazione tra moduli NDT, tra piattaforme NDT diverse, e tra NDT e rete fisica
- Permette integrazione più semplice di algoritmi ML per ottimizzazione e predizione

### 2.5 DevOps-Driven Development

- **CI/CD pipeline** per aggiornamenti rapidi e testing continuo dei DT
- Integrazione di open-source tools (TensorFlow, PyTorch) per sviluppo ML modulare
- Ciclo iterativo: dati reali → aggiornamento DT → feedback loop → nuovi insight

### 2.6 Management e Orchestration

L'orchestrazione abilita:
- **Sincronizzazione dati real-time** tra sorgenti diverse
- **Federated approach**: ogni DT opera come entità autonoma con interfacce e data model definiti, ma contribuisce collettivamente all'infrastruttura digitale
- **Closed-loop automation**: informazioni dagli NDT → azione immediata sulla rete fisica
- **What-if analyses** con AI/ML per forecasting e pianificazione proattiva

> Il design deve basarsi su una **Service Based Architecture (SBA)**: ogni componente espone funzionalità come servizi consumabili via API, in modalità producer/consumer o publisher/subscriber.

---

## 3. Standardization Landscape

### 3.1 3GPP

- **SA5 (Management & Orchestration):** work item su NDT per management della rete 5G/B5G — NDT come black-box service con interfacce standard
- **TR 28.915 V19.0.0 (2024-12):** primo studio sistematico su NDT in 3GPP — definisce use case, requirements, gap architetturali
- **TS 28.561:** introduce Nested NDT generalizzato a tutti i tipi di NDT

### 3.2 ETSI

- **GR ZSM (Zero-touch Network & Service Management):** NDT come motore di automazione zero-touch
- **GR ZSM 015 V1.1.1 (2024-02):** architettura ZSM con NDT integrati per closed-loop autonomo

### 3.3 IRTF — Network Management Research Group

Focus su architetture di gestione basate su intenti e AI-driven, rilevanti per NDT ma non ancora con standard formali dedicati.

### 3.4 ITU-T

- **SG13:** standardizzazione su future networks e AI for networking
- **Recommendation Y.3090:** definisce il DTN — architettura a layer con southbound/northbound interfaces, enfasi sull'orchestrazione di DT multipli

### 3.5 TM Forum

- **Open Digital Architecture (ODA):** framework per la digitalizzazione dei telco — componenti riusabili e marketplace di API
- NDT come enabler dell'automazione ODA, ma con gap di integrazione ancora aperti

### 3.6 Gap e Limiti della Standardizzazione Attuale

- **Assenza di un'architettura unificata** capace di supportare scenari cross-domain interoperabili
- Terminologia inconsistente tra SDO (3GPP, ITU-T, ETSI usano definizioni diverse di "twin")
- Mancanza di interfacce standard tra NDT di operatori diversi
- Governance e trust model per la condivisione federata di dati ancora irrisolta

---

## 4. Architettura Proposta da RESTART

### 4.1 Concetti e Definizioni

Il paper introduce **tre entità distinte**:

| Entità | Ruolo | Connessione |
|---|---|---|
| **DT (Digital Twin)** | Rappresentazione digitale generica di un asset/servizio — implementato come microservizio | Asset o servizio (logica) |
| **DH (Digital Hat)** | Tipo specifico di DT con connessione **diretta e dedicata** all'asset fisico. È l'interfaccia southbound, protocol-agnostic | Hardware/software reale |
| **DTH (Digital Hub)** | Aggregatore di più DT (ognuno col suo DH) per coprire funzioni di rete complesse | Altri DT o altri DTH (composizione ricorsiva) |

> Un asset fisico può avere **più DH** (es. uno per monitoring, uno per energy management), con meccanismi di coordinamento per evitare conflitti semantici.

### 4.2 Self-Composite Pattern

La proprietà chiave del DTH è il **self-composite pattern**:

```
Asset fisico A          Asset fisico B
    └── DH_A                └── DH_B
        └── microservice_A      └── microservice_B
                  ↘                 ↙
                      DTH_1
                  (aggrega A e B)
                      ↓
                    DTH_2
              (aggrega DTH_1 + altri)
                      ↓
                    DTH_N
              (visione globale della rete)
```

Un DTH composto da DTH è ancora un DTH → **composabilità ricorsiva senza limite di profondità**. Un singolo DT può appartenere contemporaneamente a **più DTH diversi** (es. stesso router nel DTH della rete mobile e in quello della rete fissa).

### 4.3 Interfacce

- **Southbound:** DH ↔ asset fisico (protocol-agnostic: YANG, REST, JSON, proprietario vendor)
- **Northbound:** DTH/DT ↔ applicazioni e servizi (API standard via SBA)
- **East/Westbound:** DTH ↔ DTH di domini o operatori diversi (per federazione cross-domain)

### 4.4 Compatibilità con gli Standard Esistenti

| Standard | Mapping con architettura RESTART |
|---|---|
| 3GPP SA5 NDT | DH = interfaccia southbound del 3GPP Management Service (MnS) |
| ITU-T Y.3090 DTN | DTH = implementazione concreta del DTN layer orchestrator |
| ETSI ZSM | DTH con AI/ML = ZSM Closed-Loop Automation Engine |
| TM Forum ODA | DT microservice = ODA Component |

### 4.5 Intent-Based Networking (IBN)

Il layer IBN si posiziona sopra i DTH e permette all'operatore di esprimere **intenti ad alto livello** (es. "mantieni latenza < 5ms per servizio X") che vengono automaticamente tradotti in configurazioni concrete dalla catena DH → DTH → rete fisica, senza intervento manuale.

---

## 5. Use Case e Collaborazione tra NDT

### 5.1 Management di Non-Public Networks (NPN)

- **Standalone NPN (S-NPN):** rete privata completamente indipendente → NDT gestisce il proprio dominio autonomamente
- **Public Network Integrated NPN (PNI-NPN):** rete privata integrata con rete pubblica → DTH federato tra operatore pubblico (MOP) e operatore partecipante (POP)
- Sfida: governance e SLA agreement tra entità diverse con DTH che si scambiano dati cross-dominio

### 5.2 Management di Local Area Networks (LAN)

- Wi-Fi 802.11 con **Multi-Link Operation (MLO)**: DH modella ogni link radio separatamente, DTH coordina la gestione multi-link
- **Time-Sensitive Networking (TSN)**: NDT per validare configurazioni deterministiche prima del deploy sulla LAN industriale
- Ray Tracing deterministico integrato per simulare propagazione indoor in ambienti industriali complessi

### 5.3 Network Sharing

- Più operatori condividono infrastruttura fisica → ogni operatore mantiene il proprio NDT con DTH separato
- I DTH comunicano via east/westbound interface per coordinare l'uso condiviso delle risorse
- Modello di trust e data governance ancora da standardizzare — è uno dei gap aperti principali

---

## 6. Conclusioni

Gli NDT non sono solo un'evoluzione tecnica: sono un **foundational layer per le reti cognitive, resilienti e adattive del futuro**.

Per essere scalabili richiedono:
- **Modelli condivisi** e terminologia unificata tra tutti gli SDO
- **Interfacce aperte** standardizzate (southbound, northbound, east/westbound)
- **Framework di governance** per la federazione federata cross-operatore
- **Allineamento tra 3GPP, ITU-T, ETSI e TM Forum** — oggi ancora troppo frammentati

L'architettura RESTART con DH e DTH è presentata non solo come proposta tecnica, ma come **catalizzatore per la convergenza della standardizzazione**.

---

## Appendice: Acronimi Chiave

| Acronimo | Significato |
|---|---|
| **NDT** | Network Digital Twin |
| **DT** | Digital Twin |
| **DH** | Digital Hat (DT direttamente connesso all'asset fisico) |
| **DTH** | Digital Hub (aggregatore di DT) |
| **DTN** | Digital Twin Network (ITU-T) |
| **SBA** | Service Based Architecture |
| **SDN** | Software Defined Networking |
| **ZSM** | Zero-touch network and Service Management (ETSI) |
| **IBN** | Intent-Based Networking |
| **NPN** | Non-Public Network |
| **MOP** | Main Operator |
| **POP** | Participating Operator |
| **SBR** | Shooting and Bouncing Rays (Ray Tracing approssimato) |
| **IM** | Image Method (Ray Tracing deterministico) |
| **TSN** | Time-Sensitive Networking |
| **MLO** | Multi-Link Operation |
| **ODA** | Open Digital Architecture (TM Forum) |

Ecco il tuo cheat-sheet da tenere a portata di mano. 📌

---

# 📄 Scheda Paper — Riferimento Rapido

**Titolo:** _The Role of Multi-Agents in Digital Twin Implementation: A Short Survey_  
**Autori:** Yogeswaranathan Kalyani & Rem Collier — University College Dublin  
**Pubblicato:** ACM Computing Surveys, Vol. 57, No. 3 — Novembre 2024  
**DOI:** https://doi.org/10.1145/3697350[Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/9b340c5d-47b6-4d7c-a3b3-df6c91b275fd/Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf)

---

## Cos'è

Una **systematic literature review** (non un paper sperimentale) che mappa come i Multi-Agent Systems (MAS) vengono integrati nei Digital Twin (DT). Partendo da 16.100 risultati su Google Scholar (2020–2024), gli autori selezionano **22 paper** rilevanti e li analizzano su 4 research questions.[Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/9b340c5d-47b6-4d7c-a3b3-df6c91b275fd/Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf)

---

## Le 4 Research Questions

- **RQ1** — In quali domini si usano agenti nei DT?
    
- **RQ2** — Quali feature degli agenti vengono sfruttate?
    
- **RQ3** — Quali altre tecnologie si affiancano agli agenti?
    
- **RQ4** — Quali sono i gap e le direzioni future?[Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/9b340c5d-47b6-4d7c-a3b3-df6c91b275fd/Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf)
    

---

## Risultati Chiave

**Domini coperti** (manufacturing domina con 10/22 paper; agriculture, healthcare e smart cities sono underexplored):[Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/9b340c5d-47b6-4d7c-a3b3-df6c91b275fd/Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf)

|Dominio|Paper|Stato|
|---|---|---|
|Manufacturing|10|Maturo|
|Smart Agriculture|3|Emergente|
|Smart Cities|2|Emergente|
|Healthcare|2|Emergente|
|Edge/CPS/Air Mobility|5|Niche|

**Feature degli agenti più usate:** decision-making autonomo, scheduling dinamico, cooperative task allocation, real-time data processing, simulation & optimisation.[Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/9b340c5d-47b6-4d7c-a3b3-df6c91b275fd/Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf)

**Tech stack ricorrente nei paper analizzati:** Deep Reinforcement Learning (DRL), Agent-Based Simulation (ABS), Ontologie/Knowledge Graphs, JADE, JaCaMo, SPADE3, WLDT, Unity3D, Microsoft AirSim.[Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/9b340c5d-47b6-4d7c-a3b3-df6c91b275fd/Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf)

---

## Architettura Proposta (Smart Agriculture)

Gli autori propongono una **Web of Digital Twins** per open-environment arable farming con questa struttura:[Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/9b340c5d-47b6-4d7c-a3b3-df6c91b275fd/Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf)

`UI (input: farm_id, field_id, sowing_date)
 `   └── Microservices Layer
 `       ├── Weather Forecasting Service
 `       ├── Soil Analysis Service
 `       ├── Crop Growth Model (ML)
 `       └── Irrigation Scheduling Service
 `   └── Agent Layer
 `       ├── Manager Agent     → orchestrazione
 `       ├── Farm Agent        → DT della farm
 `       ├── Field Agent       → monitoring + sensori
 `       └── Recommendation Agent → output verso utente
 `   └── Knowledge Layer
 `       └── Semantic Web + Domain Ontologies (AGROVOC)

---

## Gap Identificati (Future Work)

- **Scalabilità & adattabilità** non risolte in nessuno dei 22 paper[Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/9b340c5d-47b6-4d7c-a3b3-df6c91b275fd/Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf)
    
- **Interoperabilità & standardizzazione** assente — ogni paper usa stack diverso[Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/9b340c5d-47b6-4d7c-a3b3-df6c91b275fd/Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf)
    
- **Integrazione avanzata AI/ML** ancora superficiale nella maggior parte delle implementazioni[Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/9b340c5d-47b6-4d7c-a3b3-df6c91b275fd/Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf)
    
- **Privacy & security** menzionate ma non affrontate[Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/9b340c5d-47b6-4d7c-a3b3-df6c91b275fd/Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf)
    
- **Economic feasibility** completamente aperta[Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/9b340c5d-47b6-4d7c-a3b3-df6c91b275fd/Role-of-Multi-Agents-in-Digital-Twin-Implementation.pdf)
    

---

## One-liner da ricordare

> _I MAS non sostituiscono i Digital Twin — li rendono autonomi. Il DT è il "corpo", l'agente è il "cervello"._
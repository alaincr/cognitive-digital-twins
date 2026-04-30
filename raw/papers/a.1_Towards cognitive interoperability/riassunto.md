Ecco il riassunto strutturato della tesi, pensato come scheda di consultazione rapida.[Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)

---

# 📋 Scheda di Riferimento — Tesi CDT & Cognitive Interoperability

**Titolo completo:** _Towards Cognitive Interoperability: Cognitive Digital Twin and Cognitive Architecture for Human-CPS Collaboration_  
**Progetto:** AI4C2PS (ANR/FNR — Francia/Lussemburgo, University of Lorraine + LIST)[Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)

---

## Il Problema Centrale

La **semantic interoperability** (ontologie OWL, vocabolari condivisi) non è sufficiente quando umani e sistemi cyber-fisici devono _collaborare davvero_. Un operatore e un cobot possono parlare la stessa ontologia ma interpretare la stessa situazione in modo radicalmente diverso. Serve un livello superiore: la **cognitive interoperability**.[Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)

**Definizione ufficiale della tesi:**

> _"Cognitive Interoperability = la capacità di agenti diversi (umani o artificiali) di allineare pensieri e percezioni, costruire modelli mentali condivisi, e raggiungere mutua comprensione e intenzioni condivise per il decision-making congiunto."_[Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)

---

## I 4 Contributi Principali (C1–C4)

|ID|Contributo|Cosa risolve|
|---|---|---|
|**C1**|Formalizzazione di CCPS e CDT come entità cognitive|Definizione teorica rigorosa di cosa è un "sistema cognitivo" industriale [Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)|
|**C2**|Definizione formale di Cognitive Interoperability|Distingue semantic da cognitive interoperability, con criteri misurabili [Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)|
|**C3**|Modello di Maturità MMCI (5 livelli)|Strumento di assessment per misurare il grado di allineamento cognitivo [Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)|
|**C4**|Ontologia CDTO|Knowledge base strutturata per task, ruoli, vincoli, capabilities, affordances [Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)|

---

## Il Modello di Maturità MMCI

Scala progressiva da semantica a cognizione vera:[Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)

- **Level 0 — Semantic Interoperability**: ontologie condivise, mapping, significato consistente degli scambi
    
- **Level 1 — Shared Situation Awareness**: accordo su _cosa sta succedendo ora_ e previsione a breve termine
    
- **Level 2 — Shared Mental Models**: struttura del task condivisa (step, ruoli, vincoli causa-effetto)
    
- **Level 3 — Intent & Reasoning Alignment**: goal condivisi, spiegazioni delle decisioni, adattamento coerente
    
- **Level 4 — Joint Decision-Making + Metacognition**: decisioni congiunte con gestione esplicita di incertezza, confidence e delegazione adattiva
    

---

## L'Architettura CDT

Ogni **Cognitive Digital Twin** ha tre funzioni core:[Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)

text

`Physical Entity (CPS/Human)         │  sensor data (obs, cmd, state)        ▼ ┌─────────────────────────────────────┐ │           CDT                       │ │  ┌─────────────┐                    │ │  │  EMULATION  │ → stima stato/azione corrente │ │  ├─────────────┤                    │ │  │  COGNITION  │ → CLARION (reasoning + RL)    │ │  ├─────────────┤                    │ │  │  SIMULATION │ → Q-learning su scenari futuri│ │  └─────────────┘                    │ └─────────────────────────────────────┘`

**Due modalità di coupling col fisico:**[Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)

- **Strong coupling**: il CDT controlla direttamente il CPS (lo trasforma in CCPS)
    
- **Weak coupling**: il CDT ragiona internamente e produce raccomandazioni/predizioni
    

---

## L'Architettura Cognitiva: CLARION

Scelta rispetto a SOAR, ACT-R, LIDA per il miglior bilanciamento tra explainability e adattamento. È ibrida neuro-simbolica con 4 subsystem:[Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)

|Subsystem|Ruolo nel CDT|Meccanismo chiave|
|---|---|---|
|**ACS** (Action-Centred)|Selezione azione real-time|Q-learning (IDN implicito) + regole simboliche (ARS esplicito) [Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)|
|**NACS** (Non-Action-Centred)|Ragionamento e memoria concettuale|Rule-based + similarity-based inference su GKS [Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)|
|**MS** (Motivational)|Goal management e reward signal|Drive primari/derivati → goal espliciti per ACS [Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)|
|**MCS** (Meta-Cognitive)|Supervisione dell'intero loop cognitivo|Regola learning rate, exploration/exploitation, filtra input [Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)|

**Dual-level learning** in ACS:[Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)

- _Bottom-up_: se un'azione ha successo → estrazione di regola esplicita (RER)
    
- _Top-down_: regole esplicite guidano il Q-learning implicito
    

---

## L'Ontologia CDTO

Stack modulare OWL:[Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)

`DUL (upper-level: oggetti, eventi, ruoli, contesto)
  └── SOMA (robotica: capabilities, task, tools, CPS)
       └── SSN/SOSA (sensori, osservazioni, attuatori)
            └── HUMO (human layer: cognitivo, fisico, stato)
            `

**Modello CAA (Capabilities, Abilities, Affordances):** cosa un agente _può fare_, _come lo fa_, e _in quale contesto è possibile_.[Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)

**Regole SWRL** per inferenza runtime: es. "se il robot ha la capability X e le precondizioni Y sono soddisfatte, allora può eseguire step Z".[Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)

**Statistiche SOMA module:** 675 classi, 266 object properties, 38 data properties, 357 OWL restrictions, 70 disjointness axioms.[Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)

---

## Use Case di Validazione

**Scenario:** Human-Robot Collaboration (HRC) su assemblaggio con cobot UR5e — operazione di avvitatura.[Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)

**Pipeline implementata:**

1. Stato del mondo ingerito via **NGSI-LD** nell'ontologia
    
2. Reasoner (HermiT) applica regole SWRL → inferisce feasibility delle azioni
    
3. **PyClarion** riceve features dall'ontologia, seleziona azione, aggiorna chunks/regole
    
4. Q-learning addestrato _separatamente in simulazione_ per la skill procedurale (avvitatura), poi policy riusata in execution
    

**Risultato:** il sistema con cognitive layer (CLARION + CDTO) raggiunge livelli MMCI più alti rispetto al baseline puramente semantico, in particolare su adattamento, anticipazione e joint decision-making.[Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)

---

## Limiti Dichiarati dall'Autore

- **Emulation function non implementata** — rimane come sviluppo futuro[Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)
    
- **Human Digital Twin (HDT) assente** — il lato umano non è un CDT a tutti gli effetti[Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)
    
- **Learning loop CLARION non pienamente integrato** — Q-learning validato solo in simulazione separata, non in loop chiuso con CDTO[Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)
    
- **MMCI non ancora validato empiricamente** con metriche quantitative definite per ogni livello[Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)
    
- **Use case singolo** (HRC assemblaggio) — generalizzazione richiede ri-design dell'ontologia[Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)
    

---

## Stack Tecnologico

|Layer|Tecnologia|
|---|---|
|Context broker|NGSI-LD (FIWARE standard) [Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)|
|Ontology dev|Protégé + HermiT reasoner [Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)|
|Reasoning rules|SWRL + SPARQL [Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)|
|Cognitive engine|PyClarion (Python) [Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)|
|Learning|Q-learning (Watkins & Dayan, 1992) [Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)|
|Robot|UR5e (Universal Robots) [Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)|
|Reference ontologies|DUL, SOMA, SSN/SOSA, HUMO [Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-H.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/ae637847-53fa-4715-8f1e-858fbdd069bf/Tesi-Towards-cognitive-interoperability_-cognitive-digital-twin-and-cognitive-architecture-for-Human-CPS-collaboration.pdf)|
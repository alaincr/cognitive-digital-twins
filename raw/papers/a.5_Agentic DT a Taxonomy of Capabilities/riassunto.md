Ecco il tuo riassunto di riferimento, strutturato per essere consultato velocemente in futuro.

---

# 📋 Scheda di Riferimento — Agentic Digital Twins (Burr et al., 2026)

**Paper:** _"Agentic Digital Twins: A Taxonomy of Capabilities for Understanding Possible Futures"_  
**Autori:** Christopher Burr et al. — The Alan Turing Institute, Mott MacDonald, Fujitsu, Univ. Sheffield  
**Pubblicato:** Gennaio 2026 — arXiv:2601.18799 [cs.CY][01_Agentic-Digital-Twins.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/394c3033-293d-416c-b0f6-10ffa376d916/01_Agentic-Digital-Twins.pdf)

---

## 🎯 Idea Centrale in una riga

Un Digital Twin agentivo non si limita a _rappresentare_ un sistema fisico — lo _co-costituisce_, cambiando la realtà che misura. Questo processo si chiama **performatività**.[01_Agentic-Digital-Twins.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/394c3033-293d-416c-b0f6-10ffa376d916/01_Agentic-Digital-Twins.pdf)

---

## 🧩 Il Framework: 3 Dimensioni × 3 Livelli = 27 Configurazioni

Ogni DT agentivo si classifica con una tripla `(Agency, Coupling, Evolution)`:[01_Agentic-Digital-Twins.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/394c3033-293d-416c-b0f6-10ffa376d916/01_Agentic-Digital-Twins.pdf)

|Dimensione|Livello 1|Livello 2|Livello 3|
|---|---|---|---|
|**Agency** (dove si decide)|`E` External|`I` Internal|`D` Distributed|
|**Coupling** (quanto spesso si parlano)|`L` Loose (batch)|`T` Tight (real-time)|`C` Constitutive (co-si-definiscono)|
|**Evolution** (quanto cambia il modello)|`S` Static (pesi fissi)|`A` Adaptive (parametri aggiornabili)|`R` Reconstructive (ridefinisce le categorie)|

---

## 🗺️ Le 9 Configurazioni Chiave

## Cluster 1 — The Present (esiste oggi)

|#|Nome|Codice|Descrizione rapida|
|---|---|---|---|
|1|Computational Tool|`(E,L,S)`|Google Maps, cardiac DT in healthcare — strumento passivo|
|2|Adaptive Monitor|`(E,T,A)`|Factory DT real-time con ML online — apprende ma l'umano comanda|
|3|Active Steering|`(I,T,A)`|DT manifatturiero che aggiusta autonomamente i parametri macchina|

## Cluster 2 — The Threshold (raggiungibile a breve)

|#|Nome|Codice|Descrizione rapida|
|---|---|---|---|
|4|Symbiotic|`(D,T,A)`|Smart city: l'agency emerge dall'interazione, nessuno controlla|
|5|**Governor**|`(I,C,A)`|⚠️ **Il più pericoloso e già fattibile**: il DT _definisce_ cosa misura → performative lock-in|
|6|Swarm|`(D,T,S)`|Fleet di veicoli autonomi con modelli statici → phantom jams da interazione|

## Cluster 3 — The Frontier (per lo più teorico)

|#|Nome|Codice|Descrizione rapida|
|---|---|---|---|
|7|Worldbuilder|`(E,L,R)`|AlphaFold-style: ricostruisce l'ontologia ma human-in-the-loop|
|8|Voyager|`(I,T,R)`|DT autonomo che reinventa le sue stesse categorie → epistemically inscrutable|
|9|Reconstructive Assemblage|`(D,C,R)`|Fantascienza: sistemi multipli che si ridefiniscono a vicenda continuamente|

---

## ⚡ Il Concetto Chiave: Performative Prediction

Basato su Perdomo et al. (ICML 2020) e Hardt & Mendler-Dünner (2025):[01_Agentic-Digital-Twins.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/394c3033-293d-416c-b0f6-10ffa376d916/01_Agentic-Digital-Twins.pdf)

- Un modello deployato con parametri θ **cambia la distribuzione** dei dati che raccoglierà: D(θ)D(\theta)D(θ)
    
- Il vero obiettivo non è minimizzare il rischio su dati storici, ma su quelli che il modello stesso _creerà_: min⁡θ Risk(θ,D(θ))\min_\theta \, \text{Risk}(\theta, D(\theta))minθ​Risk(θ,D(θ))
    
- Il punto di **performative stability** θPS\theta_{PS}θPS​ è quando il modello sembra ottimale _perché ha creato la distribuzione su cui viene valutato_ → **lock-in**
    

---

## 🚦 Transition Dynamics — Come si evolve un sistema

Le transizioni si notano con:[01_Agentic-Digital-Twins.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/394c3033-293d-416c-b0f6-10ffa376d916/01_Agentic-Digital-Twins.pdf)

text

`(E,L,S) --[efficiency↑ | cost↓]--> (E,T,A) --T(medium,tech)--> (I,T,A) --> ... --> (D,C,R)`

- **Fattori acceleratori (↑):** competizione di mercato, investimenti, pressioni di crisi
    
- **Fattori frenanti (↓):** normativa, inerzia istituzionale, costi di integrazione
    
- **3 soglie critiche di no-return:** agency diventa internal → coupling diventa constitutive → model diventa reconstructive
    

---

## 🔴 Configurazione più a rischio: Governor `(I,C,A)`

- Agency interna + coupling costitutivo = il DT non solo misura, **ridefinisce cosa conta come misurabile**[01_Agentic-Digital-Twins.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/394c3033-293d-416c-b0f6-10ffa376d916/01_Agentic-Digital-Twins.pdf)
    
- I lavoratori diventano "productivity units", le strade diventano "throughput zones"
    
- Lock-in a 4 livelli: tecnico (infrastruttura), cognitivo (linguaggio), materiale (città fisica), sociale (discorso pubblico)
    
- **Già esistente:** Singapore Electronic Road Pricing, sistemi di algorithmic management[01_Agentic-Digital-Twins.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/394c3033-293d-416c-b0f6-10ffa376d916/01_Agentic-Digital-Twins.pdf)
    

---

## ⚠️ Limiti da ricordare

- **Zero empirismo**: nessun esperimento, nessun benchmark[01_Agentic-Digital-Twins.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/394c3033-293d-416c-b0f6-10ffa376d916/01_Agentic-Digital-Twins.pdf)
    
- La social cost function del traffico è un toy model costruito ad hoc
    
- Le categorie della tassonomia sono qualitative, non metriche
    
- Utile come **mappa strategica e vocabolario condiviso**, non come guida implementativa
    

---

## 📚 Riferimenti chiave da approfondire

- **Performative Prediction:** Perdomo et al., ICML 2020 | Hardt & Mendler-Dünner, _Statistical Science_ 2025 [01_Agentic-Digital-Twins.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/394c3033-293d-416c-b0f6-10ffa376d916/01_Agentic-Digital-Twins.pdf)
    
- **Steering Representations:** Korenhof, Blok & Kloppenburg, _Philosophy & Technology_ 2021
    
- **Philosophical foundations of DTs:** Wagg et al., _Data-Centric Engineering_ 2025
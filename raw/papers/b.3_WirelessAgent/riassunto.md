Ecco il riassunto compatto e strutturato, ottimizzato per la consultazione rapida.

---

# 📄 WirelessAgent — Scheda di Consultazione Rapida

**Paper:** _"WirelessAgent: Large Language Model Agents for Intelligent Wireless Networks"_  
**Autori:** Tong, Guo, Shao, Wu, Li, Lin, Zhang — HKUST  
**Pubblicato:** arXiv:2505.01074 (Maggio 2025) | **Codice:** `github.com/jwentong/WirelessAgentR1` [WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)

---

## 🎯 Problema Affrontato

Le reti wireless 5G/6G sono troppo dinamiche per i metodi classici: i sistemi **model-driven** richiedono modelli fisici perfetti, quelli **ML-based** richiedono labeled data e re-training continuo per ogni scenario nuovo. Serve un approccio generalizzabile e autonomo.[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)

---

## 💡 Soluzione Proposta

**WirelessAgent** = LLM come cervello + 4 moduli cognitivi + tool esterni orchestrati via **LangGraph**.[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)

## I 4 moduli core

|Modulo|Funzione|Tecnica chiave|
|---|---|---|
|**Perception**|Processa input multimodali (testo, CQI, SNR)|Conversione in testo, fine-tuning dominio|
|**Memory**|Stato persistente tra operazioni|Storico allocazioni, errori passati, KV-store|
|**Planning**|Ragionamento e decomposizione task|CoT, ICL, RAG, Reflection (pre/post-action)|
|**Action**|Esegue comandi, chiama tool|Tool manipulation, text generation|

## Il workflow in pratica

1. **Workflow Determination (offline, one-shot):** un LLM avanzato (DeepSeek-R1) + un esperto umano co-progettano il grafo di sub-task in modalità human-in-the-loop[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)
    
2. **Workflow Execution (online, automatica):** LangGraph esegue il grafo su task routinari, con un `global state` condiviso tra tutti i nodi[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)
    

---

## 📊 Case Study: Network Slicing 5G

**Setup simulato:** campus HKUST, 30 utenti, ray-tracing a 2.4 GHz, 120 MHz totali (90 MHz eMBB + 30 MHz URLLC), LLM usato: **DeepSeek-V3**[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)

## Workflow a 5 sub-task

1. **Intent Understanding** → RAG su knowledge base di esempi di slicing
    
2. **Slice Allocation** → LLM sceglie tra eMBB (video, high-BW) e URLLC (low-latency, IoT)
    
3. **Bandwidth Allocation** → tool `CQI→MCS mapping` per calcolare il data rate reale
    
4. **QoS Evaluation** → verifica vincoli; se fallisce → rerouting al nodo precedente
    
5. **Bandwidth Adjustment** → rebalancing dinamico per far entrare nuovi utenti[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)
    

## Risultati numerici

|Metodo|Max utenti|Bandwidth utilization|
|---|---|---|
|Prompt-based (solo CoT, no tool)|15|baseline|
|**WirelessAgent**|**25**|**+44.4%**|
|Rule-based (ottimo teorico)|26|solo 4.3% meglio|

Risultati **consistenti su 3 scenari geografici diversi** (nord, centro, sud campus).[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)

## LLM Benchmark (con knowledge base)

|LLM|Intent Acc.|Overall BW Util.|
|---|---|---|
|DeepSeek-R1|100%|74.65% ✅ best|
|DeepSeek-V3|100%|70.80%|
|Llama3.3-70b|100%|74.48%|
|QwQ-32b|100%|71.05%|
|Llama3-8b|100%|60.96% ❌ worst|

**Nota critica:** senza knowledge base, l'accuracy di intent understanding scende a ~90-93% per tutti i modelli, ma il numero di utenti supportati sale (perché gli eMBB vengono misclassificati come URLLC, consumando meno banda).[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)

---

## 🔧 Stack Tecnologico

- **LLM API:** DeepSeek-V3 / R1, Llama, Qwen, QwQ (qualsiasi API compatibile)
    
- **Orchestrazione:** LangGraph (grafo di nodi + global state TypedDict)
    
- **RAG:** vector store con esempi di slicing raccolti da internet
    
- **Tool esterni:** funzione `CQI→MCS mapping`, network monitor, resource adjustment
    
- **Simulazione:** ray-tracing via OpenStreetMap + parametri fisici reali[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)
    

---

## ⚠️ Limiti Chiave

- **Solo simulazione** — nessun deployment su rete reale[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)
    
- **Latenza LLM incompatibile con URLLC** (requisito <10ms) — problema aperto[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)
    
- **Workflow design è offline e human-in-the-loop** — non fully autonomous su task nuovi
    
- **Performance degradata con LLM piccoli** (Llama3-8b cade significativamente)[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)
    
- **Security & privacy non affrontate** — future work esplicito degli autori[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)
    
- **Fine-tuning domain-specific** solo suggerito, non dimostrato empiricamente[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)
    

---

## 🔮 Future Work dichiarate dagli autori

- Integrazione multimodale più avanzata (encoding di segnali radio nativi)
    
- Explainability delle decisioni dell'agente
    
- Robustezza security/privacy per deployment reale
    
- Valutazione su reti fisiche reali (oltre la simulazione)[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)
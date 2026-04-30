Ottimo contesto. Ecco l'analisi contestualizzata al tuo progetto di tesi.

---

## 📍 Dove il paper è direttamente utile alla tua tesi

WirelessAgent e il tuo CDT condividono lo **stesso dominio applicativo (rete 5G)** e la **stessa architettura di orchestrazione (LangGraph + agenti specializzati)**. Non è un paper tangenzialmente correlato — è il closest prior work che esiste sul tuo topic. Devi citarlo nella sezione Related Work e usarlo come baseline di confronto.[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)

Le aree di sovrapposizione concreta sono tre:

## Architettura multi-agente su LangGraph

WirelessAgent dimostra empiricamente che il pattern _agenti specializzati per sub-task su LangGraph con global state condiviso_ funziona su task 5G reali. Questo è esattamente il tuo Livello Cognitivo. Puoi prendere il loro schema come **punto di partenza architetturale**, e differenziarti su due fronti: tu aggiungi **Eclipse Ditto** come layer di stato esterno persistente (loro non ce l'hanno) e **Neo4j** per la verifica dei constraint del Planning Agent (loro usano tool Python inline, non un knowledge graph strutturato).[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)

## Il caso d'uso Network Slicing

Il tuo simulatore 5G emetterà metriche RSRP, SINR, throughput, latenza, tasso di handover. Il loro caso di studio è esattamente il network slicing con CQI, data rate, latency constraints su slice eMBB/URLLC. Hai **ground truth numerica già disponibile dal loro paper** (benchmark con Rule-based optimality) che puoi usare per calibrare il tuo simulatore e per confrontare i risultati del tuo Reasoning+Planning Agent su scenari simili.[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)

## Benchmark comparativo dei modelli

Loro testano 8 LLM via API cloud (DeepSeek-R1, Llama3.3-70b, QwQ-32b, ecc.). Tu testi Llama 3.1 8B, Mistral 7B, Phi-3 Mini, Qwen 3B — tutti **locali**. Questa è la tua differenziazione più forte: il tuo Contributo 3 (benchmark comparativo) è il paper WirelessAgent ma su hardware consumer con modelli quantizzati. È un contributo genuino e comparabile.[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)

---

## ⚖️ Pro/Contro rispetto al tuo caso d'uso

|Dimensione|WirelessAgent|Tua Tesi (CDT)|
|---|---|---|
|**Stato del sistema**|Nessuno strato di Digital Twin, stato in-memory nel global state LangGraph|Eclipse Ditto = stato persistente, ordinato temporalmente, con WebSocket live|
|**Knowledge base**|Vector store RAG con esempi di slicing [WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)|Neo4j Knowledge Graph con vincoli operativi strutturati — più espressivo, verificabile formalmente|
|**LLM**|API cloud (DeepSeek, Qwen, Llama) [WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)|Ollama locale — zero latenza API, privacy-preserving, ma capacità ridotta|
|**Valutazione**|Metriche di sistema (BW utilization, utenti supportati) [WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)|**Gap critico**: loro non valutano il reasoning in linguaggio naturale — tu devi farlo|
|**Deployment**|Simulazione + API cloud|Completamente locale su M4 Pro — riproducibile|
|**Explainability**|Solo output finale, nessuna spiegazione causale|Communication Agent con spiegazioni causali e confidence — contributo differenziante|

---

## 📝 Appunti contestualizzati per il relatore

Se il relatore ti chiede _"cosa pensi di WirelessAgent?"_, ecco la risposta strutturata:

**Cosa fanno bene e da cui prendiamo spunto.** WirelessAgent dimostra che un'architettura LangGraph multi-agente riesce a gestire task 5G complessi con performance vicino all'ottimo teorico (+44.4% rispetto al solo prompt engineering, -4.3% rispetto al rule-based ottimale). Il pattern perception→planning→action con tool esterni è validato empiricamente. Lo usiamo come architettura di riferimento per il livello cognitivo.[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)

**Dove il nostro lavoro va oltre, su tre punti specifici.** Primo: loro non hanno un Digital Twin Layer — lo stato della rete vive solo nel global state di LangGraph, che è volatile e non ha semantica temporale. Noi introduciamo Eclipse Ditto come registro di stato persistente e ordinato temporalmente, che disaccoppia sorgenti dati e consumatori cognitivi. Secondo: loro usano una knowledge base RAG flat (vector store di esempi). Noi sostituiamo questo con un **Knowledge Graph Neo4j** che codifica i vincoli operativi in modo strutturato e verificabile — il Planning Agent non "spera" che il modello rispetti i constraint, li verifica deterministicamente prima di eseguire l'azione. Terzo, e più importante per il contributo scientifico: loro non affrontano il problema della valutazione del ragionamento in linguaggio naturale — lo citano come future work insieme a explainability e security. Il nostro Contributo 2 (framework di valutazione per agenti cognitivi specializzati) riempie esattamente questo gap.[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)

**Una critica onesta da mostrare al relatore.** La loro evaluation ha un punto debole che vale la pena citare: l'unica metrica di accuratezza testata è l'_intent understanding accuracy_, definita come l'agreement tra la slice raccomandata dall'LLM e il ground truth. Tutto il ragionamento intermedio — perché l'agente ha scelto quella slice, perché ha allocato quella banda — non viene valutato. Il paper misura _cosa_ decide il sistema, non _come e perché_. Questo è precisamente il gap metodologico che la tua tesi si propone di colmare con il framework di valutazione multi-agente.[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)

**Sul benchmark locale.** Loro testano su API cloud con i modelli più potenti disponibili (DeepSeek-R1 il migliore, Llama3-8b il peggiore con 60.96% di BW utilization). Tu giri tutto su M4 Pro 24GB con modelli open-weight quantizzati. Il tuo contributo non è replicare i loro risultati, ma rispondere a una domanda diversa: _quanto cognitive capability si riesce a ottenere da modelli 3-8B in esecuzione locale, su task 5G specifici, in un'architettura CDT completa?_ Questa è una domanda con risposta non ovvia e pubblicabile.[WirelessAgent.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/0976be6f-a640-40be-9eeb-865ea798cd12/WirelessAgent.pdf)
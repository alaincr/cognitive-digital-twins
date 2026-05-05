Ecco il riassunto completo da tenere come riferimento rapido.

---

# 📄 Scheda Paper — Implementing MAS via LangGraph

**Autore:** Dr. Soly Mathew Biju — University of Wollongong in Dubai  
**Tipo:** Paper applicativo con case study, benchmark e code samples[Implementing-MAS-via-LangGraph.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/1819b93c-e2df-46a8-8810-57c9c5298873/Implementing-MAS-via-LangGraph.pdf)

---

## Idea Centrale

Costruire un **Multi-Agent System (MAS)** dove un **Supervisor Agent** smista i task in ingresso a una flotta di agenti specializzati, ognuno dotato di tool propri. Il framework usato è **LangGraph** (ecosistema LangChain), che modella l'intero sistema come un grafo di `StateGraph` — ogni nodo è un agente, ogni arco è un passaggio di stato.[Implementing-MAS-via-LangGraph.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/1819b93c-e2df-46a8-8810-57c9c5298873/Implementing-MAS-via-LangGraph.pdf)

---

## Architettura

Il flusso è: `User Input → Supervisor Agent → Agente(i) specializzato(i) → Output verificato → Display`.[Implementing-MAS-via-LangGraph.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/1819b93c-e2df-46a8-8810-57c9c5298873/Implementing-MAS-via-LangGraph.pdf)

|Agente|Tool / Fonte dati|Latenza|Accuracy|
|---|---|---|---|
|FAQ Agent|Vector DB / documento FAQ|2s|95%|
|Database Agent|Database aziendale|3s|98%|
|Web Search Agent|Web scraping|4s|92%|
|Document Retrieval|Documenti aziendali|3s|96%|
|Email Parsing|Casella email|2s|94%|
|Sentiment Analysis|Testo libero|3s|97%|
|**Supervisor Agent**|Tutti gli agenti|—|Router + Verifier|

Per query generiche (Task 7), il Supervisor attiva più agenti in parallelo garantendo **ridondanza e fault tolerance**.[Implementing-MAS-via-LangGraph.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/1819b93c-e2df-46a8-8810-57c9c5298873/Implementing-MAS-via-LangGraph.pdf)

---

## Stack Tecnico

- **LLM backbone:** `GPT-4o` via `langchain_openai`[Implementing-MAS-via-LangGraph.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/1819b93c-e2df-46a8-8810-57c9c5298873/Implementing-MAS-via-LangGraph.pdf)
    
- **Orchestrazione:** `langgraph` (`StateGraph`)[Implementing-MAS-via-LangGraph.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/1819b93c-e2df-46a8-8810-57c9c5298873/Implementing-MAS-via-LangGraph.pdf)
    
- **Vector store:** `langchain-chroma` + `sentence-transformers` + `pypdf`[Implementing-MAS-via-LangGraph.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/1819b93c-e2df-46a8-8810-57c9c5298873/Implementing-MAS-via-LangGraph.pdf)
    
- **Tool layer:** `langchain_core.tools` + `langchain_community`[Implementing-MAS-via-LangGraph.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/1819b93c-e2df-46a8-8810-57c9c5298873/Implementing-MAS-via-LangGraph.pdf)
    

text

`langgraph / langchain_openai / langchain_community langchain-chroma / pypdf / sentence-transformers`

---

## Punti di Forza

- Ogni agente porta solo il **proprio dominio nel context window** → meno rumore, più accuracy[Implementing-MAS-via-LangGraph.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/1819b93c-e2df-46a8-8810-57c9c5298873/Implementing-MAS-via-LangGraph.pdf)
    
- **Ridondanza nativa**: task critici possono essere gestiti da più agenti[Implementing-MAS-via-LangGraph.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/1819b93c-e2df-46a8-8810-57c9c5298873/Implementing-MAS-via-LangGraph.pdf)
    
- Sistema modulare: facile aggiungere nuovi agenti senza riscrivere tutto[Implementing-MAS-via-LangGraph.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/1819b93c-e2df-46a8-8810-57c9c5298873/Implementing-MAS-via-LangGraph.pdf)
    

---

## Limiti e Red Flag

- Benchmark da laboratorio sintetico, **nessuna metodologia di valutazione rigorosa** dichiarata[Implementing-MAS-via-LangGraph.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/1819b93c-e2df-46a8-8810-57c9c5298873/Implementing-MAS-via-LangGraph.pdf)
    
- Il codice nel paper è **pseudocode**: la vera API di LangGraph differisce[Implementing-MAS-via-LangGraph.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/1819b93c-e2df-46a8-8810-57c9c5298873/Implementing-MAS-via-LangGraph.pdf)
    
- **Hard dependency su OpenAI API**, nessuna alternativa open-source discussa[Implementing-MAS-via-LangGraph.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/1819b93c-e2df-46a8-8810-57c9c5298873/Implementing-MAS-via-LangGraph.pdf)
    
- Supervisor è un **single point of failure**, nessuna logica di fallback[Implementing-MAS-via-LangGraph.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/1819b93c-e2df-46a8-8810-57c9c5298873/Implementing-MAS-via-LangGraph.pdf)
    
- **Nessuna state persistence** tra sessioni (manca Redis, DB di sessione, memory layer)[Implementing-MAS-via-LangGraph.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/1819b93c-e2df-46a8-8810-57c9c5298873/Implementing-MAS-via-LangGraph.pdf)
    
- Gli autori stessi ammettono la necessità di _"ridurre la dipendenza dall'intervento umano"_ per il futuro[Implementing-MAS-via-LangGraph.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/1819b93c-e2df-46a8-8810-57c9c5298873/Implementing-MAS-via-LangGraph.pdf)
    

---

## Verdict Rapido

> ✅ **Ottimo reference per PoC e MVP**. Architettura solida e pattern chiaro (Supervisor + Specialized Agents). ⚠️ **Non production-ready as-is**: manca error handling, fallback logic e state persistence. Da usare come blueprint, non come ricetta copia-incolla.
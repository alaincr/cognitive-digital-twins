Ecco il markdown completo del paper, scaricabile come file.

Qui sotto trovi il contenuto direttamente da leggere:

---

# MultiAgentBench: Evaluating the Collaboration and Competition of LLM Agents

> **Paper:** arXiv:2503.01935v1 | **Data:** 3 Marzo 2025  
> **Autori:** Kunlun Zhu et al. — University of Illinois Urbana-Champaign  
> **Codice:** https://github.com/MultiagentBench/MARBLE

---

## Abstract

I benchmark attuali falliscono nel catturare dinamiche multi-agent. Questo paper introduce **MultiAgentBench** e il framework **MARBLE** (_Multi-agent cooRdination Backbone with LLM Engine_): misura non solo task completion ma anche qualità di collaborazione e competizione tramite KPI basati su milestone.[2503.01935v1.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/fb62d4ca-7d4b-4f8e-bd1b-573c18937e76/2503.01935v1.pdf)

---

## Framework MARBLE — Architettura

text

`Task Info + Persona Data + Domain Database           ↓    Coordination Engine    ┌─────────────────────────────────────┐    │  Agent Graph  G=(A,E)               │    │  edge: (ai, r, aj) — tipizzato      │    │  Cognitive Module (persona + CoT)   │    │  Memory: Shared / Short / Long-RAG  │    └─────────────────────────────────────┘          ↓    Environment + ToolBox          ↓    Evaluator → Task Score + Coord. Score`

## Protocolli di Coordinamento[2503.01935v1.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/fb62d4ca-7d4b-4f8e-bd1b-573c18937e76/2503.01935v1.pdf)

|Protocollo|Tipo|Performance|Token Usage|
|---|---|---|---|
|**Graph/Mesh**|Decentralizzato|✅ Migliore|✅ Efficiente|
|**Star**|Centralizzato|Buona|Medio|
|**Chain**|Decentralizzato|Media|Medio|
|**Tree**|Centralizzato|❌ Peggiore|❌ Più alto|

## Strategie di Planning[2503.01935v1.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/fb62d4ca-7d4b-4f8e-bd1b-573c18937e76/2503.01935v1.pdf)

|Strategia|Task Score|Coord. Score|KPI|
|---|---|---|---|
|Cognitive Evolving|76.67|49.87|**59.00** ✅|
|CoT|**77.67**|55.50|50.00|
|Vanilla|73.67|52.37|51.71|
|Group Discussion|72.67|46.35|49.00 ❌|

---

## Scenari del Benchmark[2503.01935v1.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/fb62d4ca-7d4b-4f8e-bd1b-573c18937e76/2503.01935v1.pdf)

|Scenario|Tipo|Agenti|Metrica|
|---|---|---|---|
|Research|Cooperativo|Ricercatori|Innovation/Feasibility/Safety|
|Minecraft|Cooperativo|Builder|Block hit rate|
|Database|Cooperativo|5 specialist|Prediction accuracy|
|Coding|Cooperativo|Developer|Executability/Quality|
|Werewolf|Competitivo|Villagers vs Werewolves|Win rate, Net Score|
|Bargaining|Competitivo|2 buyer + 2 seller|Negotiation effectiveness|

---

## Risultati Principali — Task Score[2503.01935v1.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/fb62d4ca-7d4b-4f8e-bd1b-573c18937e76/2503.01935v1.pdf)

|Modello|Research|Minecraft|Database|Coding|Bargaining|WereWolf|
|---|---|---|---|---|---|---|
|Llama-3.1-8B|80.87|6.12|34.00|59.90|72.81|12.64|
|Llama-3.1-70B|80.80|0.21|53.00|62.10|72.13|19.82|
|Llama-3.3-70B|80.00|9.15|28.50|56.60|73.15|**36.33**|
|GPT-3.5-turbo|70.20|5.05|45.00|55.50|71.67|15.69|
|**GPT-4o-mini**|**84.13**|**33.60**|**45.00**|**65.10**|**74.47**|14.06|

---

## Metriche — Formula KPI[2503.01935v1.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/fb62d4ca-7d4b-4f8e-bd1b-573c18937e76/2503.01935v1.pdf)

text

`KPI_overall = (1 / N·M) × Σ n_j N = numero agenti M = milestone totali n_j = milestone completate dall'agente j Coordination Score (CS) = (C_score + P_score) / 2   C_score = communication quality (1-5, LLM-based)  P_score = planning quality (1-5, LLM-based)`

---

## Ablation Studies[2503.01935v1.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/fb62d4ca-7d4b-4f8e-bd1b-573c18937e76/2503.01935v1.pdf)

**Iterazioni (Minecraft, GPT-4o-mini):**

- 1→7 iterazioni: TS e CS crescono
    
- 10 iterazioni: calo netto (coordination degradation)
    
- **Sweet spot: ~7 iterazioni**
    

**Numero agenti (Research):**

- 1→3 agenti: salto significativo in CS
    
- 5→7 agenti: KPI cala, overhead di coordinamento
    
- **Sweet spot: 3 agenti**
    

---

## Comportamenti Emergenti[2503.01935v1.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/fb62d4ca-7d4b-4f8e-bd1b-573c18937e76/2503.01935v1.pdf)

1. **Strategic Information Sharing** — gli agenti condividono selettivamente info in base a trust e contesto
    
2. **Trust-Polarized Collaboration** — ruoli guidano split: villagers sospettosi vs. werewolves che creano falso consenso
    
3. **Role-Driven Strategy Iteration** — gli agenti evolvono tattica nel tempo (es. Seer: conservativo → leadership)
    

---

## Limiti[2503.01935v1.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/146803486/fb62d4ca-7d4b-4f8e-bd1b-573c18937e76/2503.01935v1.pdf)

- Valutazione CS è LLM-based → rischio bias
    
- Solo 6 domini, no scenari enterprise
    
- Mancano DeepSeek, Claude, Gemini
    
- Long-term memory illimitata (non realistica)
    
- Nessuna analisi di latenza o costo totale
    

---

## Quick Reference — Best Config

python

`config = {     "topology":    "graph-mesh",       # miglior performance/token    "planning":    "cognitive_evolve", # miglior KPI    "n_agents":    3,                  # sweet spot    "max_iters":   7,                  # oltre degrada CS    "model":       "gpt-4o-mini",      # miglior task score generale }`
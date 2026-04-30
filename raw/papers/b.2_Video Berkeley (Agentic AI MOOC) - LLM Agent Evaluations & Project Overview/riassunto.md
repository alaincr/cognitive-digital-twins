yt: https://www.youtube.com/watch?v=VfOA2a0dj4w

Questo report analizza il video sulla valutazione degli agenti basati su modelli linguistici di grande dimensione (LLM), evidenziando le sfide e le metodologie discusse per misurare le architetture agentiche.

### L'importanza della Valutazione [[02:14](http://www.youtube.com/watch?v=VfOA2a0dj4w&t=134)]

La valutazione è definita come la misurazione sistematica e ripetibile di modelli e agenti. È fondamentale perché:

- Permette di misurare i progressi delle capacità basandosi su evidenze riproducibili.
    
- Supporta la valutazione dei rischi prima del rilascio.
    
- Guida decisioni di distribuzione sicure ed efficaci esponendo punti di forza e debolezza [[04:57](http://www.youtube.com/watch?v=VfOA2a0dj4w&t=297)].
    

### Evoluzione: Da LLM a Agenti LLM [[06:05](http://www.youtube.com/watch?v=VfOA2a0dj4w&t=365)]

Il discorso sottolinea il passaggio critico nella valutazione:

- **LLM classici**: Sono sistemi statici testo-testo.
    
- **Agenti**: Estendono gli LLM con pianificazione (_planning_), uso di strumenti (_tool-use_), memoria e ragionamento multi-step.
    
- Operano in ambienti dinamici, il che rende la loro valutazione molto più complessa rispetto alla semplice predizione del testo.
    

### Tipi di Valutazione [[07:33](http://www.youtube.com/watch?v=VfOA2a0dj4w&t=453)]

Vengono identificate diverse categorie di test:

1. **Close-ended (Chiusi)**: Compiti con un numero limitato di risposte corrette (es. analisi del sentiment), che permettono una valutazione automatica tramite metriche classiche come Accuracy e F1 [[09:49](http://www.youtube.com/watch?v=VfOA2a0dj4w&t=589)].
    
2. **Open-ended (Aperti)**: Risposte lunghe dove non esiste un'unica verità oggettiva (es. riassunto o scrittura creativa). Qui le metriche standard falliscono [[10:25](http://www.youtube.com/watch?v=VfOA2a0dj4w&t=625)].
    
3. **Verificabili vs Non-Verificabili**: I compiti verificabili hanno un "oracolo" o criteri chiari (es. generazione di codice o prove matematiche) [[11:42](http://www.youtube.com/watch?v=VfOA2a0dj4w&t=702)], mentre quelli non verificabili richiedono spesso il giudizio umano o di un altro LLM [[13:15](http://www.youtube.com/watch?v=VfOA2a0dj4w&t=795)].
    
4. **Statici vs Dinamici**: I benchmark statici hanno casi di test fissi, mentre quelli dinamici vengono aggiornati continuamente per evitare il _contamination_ (l'agente che impara le risposte dai dati di addestramento) [[19:58](http://www.youtube.com/watch?v=VfOA2a0dj4w&t=1198)].
    

### Metodologie di Giudizio [[14:50](http://www.youtube.com/watch?v=VfOA2a0dj4w&t=890)]

- **Valutazione Umana**: È considerata lo "standard aureo" ma presenta criticità: è lenta, costosa e spesso non riproducibile a causa dei disaccordi tra i valutatori [[15:20](http://www.youtube.com/watch?v=VfOA2a0dj4w&t=920)].
    
- **LLM-as-a-Judge**: L'uso di un LLM (es. GPT-4) per valutare l'output di un altro agente. È veloce e mostra un'alta correlazione con il giudizio umano, ma può soffrire di bias, mancanza di interpretabilità e sensibilità alla formulazione del prompt [[17:42](http://www.youtube.com/watch?v=VfOA2a0dj4w&t=1062)].
    

### Tassonomia delle Valutazioni Agentiche [[23:39](http://www.youtube.com/watch?v=VfOA2a0dj4w&t=1419)]

Il video propone tre livelli di analisi per le architetture agentiche:

1. **Capacità specifiche**: Valutazione di pianificazione, uso di funzioni, memoria e riflessione su se stessi (_self-reflection_).
    
2. **Applicazioni verticali**: Test su domini specifici come agenti web (es. WebArena), ingegneria del software (es. SWE-bench) o agenti scientifici [[26:25](http://www.youtube.com/watch?v=VfOA2a0dj4w&t=1585)].
    
3. **Agenti Generalisti**: Valutazione su set ampi di applicazioni (es. benchmark GAIA o AgentBench) [[27:48](http://www.youtube.com/watch?v=VfOA2a0dj4w&t=1668)].
    

### Conclusione: Cosa rende un sistema di valutazione "buono"? [[28:26](http://www.youtube.com/watch?v=VfOA2a0dj4w&t=1706)]

Un sistema eccellente deve collegare le capacità target (concettuali) ai risultati positivi (operativi). Il concetto chiave è la **Outcome Validity** [[30:22](http://www.youtube.com/watch?v=VfOA2a0dj4w&t=1822)]: il successo nel compito assegnato deve essere una prova valida che l'agente possiede effettivamente la capacità che stiamo cercando di misurare.

---

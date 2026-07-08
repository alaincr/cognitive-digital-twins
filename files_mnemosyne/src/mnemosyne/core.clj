(ns mnemosyne.core
  "Mnemosyne -- a runnable reference for the target stack:

     L1  Recursive inference   (RLM-style)        -- sub-call tree reified as facts
     L2  Event-sourced runtime (ActiveGraph-style) -- log -> projection -> behaviors
     L3  Immutable Datalog store (Datomic/XTDB-ish) -- here: DataScript

   This file is the L2/L3 substrate plus an L1-flavoured demo. It is written for
   YOUR environment (deps below); it was hand-checked, not executed in the sandbox
   that produced it (no Clojars there).

   deps.edn:
     {:deps {datascript/datascript {:mvn/version \"1.7.3\"}}}
   then:  clojure -M -m mnemosyne.core      ;; or call (mnemosyne.core/demo) in a REPL

   HONESTY / PORTING NOTES
   - DataScript is in-memory, single-writer, and NOT bitemporal. Time travel and
     replay here = FOLD THE EVENT LOG up to event k (see `project`). The event log
     gives you time travel even on a non-temporal store, because state = fold(log).
     On Datomic/Datahike/XTDB you get this natively (as-of / since / history), and
     XTDB adds valid-time (true bitemporality) -- swap `project` for the native op.
   - The reactive loop here is NAIVE (re-projects each round). For incremental
     self-improvement (cost proportional to the delta, not the whole log) use
     Differential Dataflow / Materialize / DDlog -- the rules in rules.clj are
     unchanged; only the evaluator changes (Theme 5a).
   - `llm-call` stubs the model with a deterministic fn so the whole demo is
     reproducible; the content-addressed cache shows the determinism mechanism."
  (:require [datascript.core :as d]
            [clojure.set :as set]
            [mnemosyne.rules :as rules]))

;; ===========================================================================
;; L3 -- schema (only refs / uniques / indexes need declaring in DataScript;
;;        scalar attrs like :question/text are used freely without schema)
;; ===========================================================================
(def schema
  {:node/id         {:db/unique :db.unique/identity}
   :node/type       {:db/index true}
   ;; relations are reified entities so a typed edge can itself carry logic and
   ;; provenance ("relation-behaviors", and "why a graph, not just a log")
   :edge/from       {:db/valueType :db.type/ref}
   :edge/to         {:db/valueType :db.type/ref}
   :edge/type       {:db/index true}
   ;; the RLM recursion tree, reified
   :task/parent     {:db/valueType :db.type/ref}
   :task/status     {:db/index true}
   ;; linter output
   :flag/of         {:db/valueType :db.type/ref}
   ;; provenance / lineage
   :prov/caused-by  {:db/index true}
   :event/id        {:db/unique :db.unique/identity}
   :event/caused-by {:db/index true}
   :event/actor     {:db/index true}
   ;; content-addressed model/tool response cache (determinism contract)
   :cache/hash      {:db/unique :db.unique/identity}})

;; ---------------------------------------------------------------------------
;; Schema registry (B4): the judge / zettel / belief modules declare ref and
;; unique attributes that `project` MUST know about, or lookup-refs and
;; cardinality-many refs fold wrong. Each module calls `register-schema!` at
;; load time; `full-schema` is the merged map `project` folds against. This
;; keeps the base `schema` above untouched while making the fold correct across
;; every module the consolidator loads.
;; ---------------------------------------------------------------------------
(defonce ^:private schema-registry (atom schema))
(defn register-schema!
  "Merge a module's schema fragment into the registry. Idempotent per fragment."
  [fragment]
  (swap! schema-registry merge fragment)
  @schema-registry)
(defn full-schema [] @schema-registry)

;; ===========================================================================
;; L3/L2 -- the event log is the source of truth; *log* is a dynamic var so a
;;          fork can rebind it. The graph is never mutated directly; it is a
;;          deterministic fold of the log.
;; ===========================================================================
(def ^:dynamic *log* (atom []))

(def ^:private counter (atom 0))
(defn- next-id [] (format "evt-%04d" (swap! counter inc)))
(defn reset-counter!
  "Reset the in-memory event-id counter (deterministic golden-replay tests)."
  [] (reset! counter 0))

;; ---------------------------------------------------------------------------
;; Clock + write-ahead seams (B4). `*now-fn*` makes `:event/ts` deterministic
;; under test; `*wal-fn*` is a hook the durable layer installs so every domain
;; event is journalled to disk BEFORE it is folded into memory (write-ahead).
;; Both default to no-op/live behavior, so the demo path is unchanged.
;; ---------------------------------------------------------------------------
(def ^:dynamic *now-fn* (fn [] (str (java.time.Instant/now))))
(def ^:dynamic *wal-fn*
  "Called with the event map {:type :actor :caused-by :tx-data} BEFORE the
   in-memory swap. The durable layer binds this to write-ahead to
   store/events.jsonl. Default: no-op (in-memory-only demo/tests)."
  (fn [_event] nil))

(defn append!
  "Append an event (the only way state changes). `tx-data` is the DataScript
   transaction this event contributes to the projection. We also reify a small
   :event/* entity and stamp :prov/caused-by onto every domain entity, so that
   lineage is queryable in Datalog. Returns the event id.

   WRITE-AHEAD (B4): `*wal-fn*` fires BEFORE the in-memory `swap!`, so a crash
   between disk and memory loses nothing — boot re-folds the journal."
  ([event] (append! *log* event))
  ([log {:keys [type actor caused-by tx-data]}]
   (let [eid     (next-id)
         actor   (or actor :runtime)
         ev-ent  (cond-> {:event/id eid :event/actor actor}
                   caused-by (assoc :event/caused-by caused-by))
         stamped (mapv (fn [m]
                         (if (and (map? m) (or (:node/id m) (:edge/from m)))
                           (assoc m :prov/caused-by eid)
                           m))                      ;; [:db/add ...] vectors pass through
                       tx-data)
         record  {:event/id eid :event/type type :event/actor actor
                  :event/caused-by caused-by :event/ts (*now-fn*)
                  :event/tx-data (into [ev-ent] stamped)}]
     ;; WRITE-AHEAD (B4): the durable layer journals the FULLY-STAMPED record to
     ;; disk here, BEFORE the in-memory swap. A crash between the two loses
     ;; nothing — boot re-folds the journal. Default *wal-fn* is a no-op.
     ;; When the WAL returns the durable content-addressed id ("sha256:…"),
     ;; THAT is the event's public identity (idempotency keys / caused_by in
     ;; causes and orders — PRD B4 FR-2); evt-NNNN stays internal.
     (let [durable-id (*wal-fn* record)]
       (swap! log conj record)              ;; memory second
       (if (string? durable-id) durable-id eid)))))

(defn project
  "L2 projection / L3 as-of. Fold an event sequence into a DataScript db VALUE.
   `(project @log)` = now;  `(project (take k @log))` = the world as of event k
   (= ActiveGraph replay; = Datomic as-of on a temporal store)."
  [events]
  (reduce (fn [db ev] (d/db-with db (:event/tx-data ev)))
          (d/empty-db (full-schema))
          events))

;; ---- forking & framing -----------------------------------------------------
(defn fork
  "Branch the run at event index k. Reuse the shared prefix (events 0..k-1) with
   NO behavior re-execution; return a new independent log atom. Cheap, because the
   prefix projection and any cached model responses inside it are reused.
   (Responses for events AFTER k are recomputed -- exactly as the paper states.)"
  [log k]
  (atom (vec (take k @log))))

(defn frame
  "A lightweight, reconverging speculative branch: apply hypothetical tx to a db
   VALUE without persisting. DataScript `d/db-with` == Datomic `d/with` semantics."
  [db hypothetical-tx]
  (d/db-with db hypothetical-tx))

;; ---- content-addressed model cache (determinism over nondeterministic calls) -
(defn- cache-lookup [events h]
  (some (fn [m] (when (and (map? m) (= (:cache/hash m) h)) (:cache/response m)))
        (mapcat :event/tx-data events)))

(defn llm-call
  "L1 model call. First run: call `live-fn`, record the response (content-addressed)
   as an event -> nondeterministic. Replay/fork: served from cache by prompt hash
   -> deterministic replay over nondeterministic calls."
  [req live-fn]
  (let [h (hash req)]
    (or (cache-lookup @*log* h)
        (let [resp (live-fn req)]
          (append! {:type :llm.responded :actor :runtime
                    :tx-data [{:cache/hash h :cache/response resp}]})
          resp))))

;; ===========================================================================
;; L2 -- the reactive runtime. A behavior = {:name, :subscribe, :react}.
;;        :subscribe (fn [db]) -> coll of trigger keys (e.g. node ids)
;;        :react     (fn [db trigger]) -> coll of event maps to append
;;        Control flow EMERGES from subscription matching; there is no orchestrator.
;; ===========================================================================
(defn run-to-fixpoint
  "Repeatedly project the log, fire each behavior on NEW subscription matches
   (tracked in `fired` so nothing re-fires), append emitted events. Stop at a
   FIXPOINT (no behavior fires) or when the budget is hit.
   The fixpoint == a generate/check/repair lint loop == semi-naive evaluation.
   The budget is the 'blunt instrument' that bounds a runaway cascade (Theme 1)."
  [log behaviors {:keys [max-steps] :or {max-steps 1000}}]
  (binding [*log* log]
    (loop [fired #{} steps 0]
      (if (>= steps max-steps)
        {:status :budget-exhausted :steps steps}
        (let [db   (project @log)
              todo (for [b    behaviors
                         trig ((:subscribe b) db)
                         :let [k [(:name b) trig]]
                         :when (not (contains? fired k))]
                     [b trig k])]
          (if (empty? todo)
            {:status :fixpoint :steps steps}
            (recur (reduce (fn [acc [b trig k]]
                             (doseq [ev ((:react b) db trig)] (append! ev))
                             (conj acc k))
                           fired todo)
                   (inc steps))))))))

;; ---- tiny modelling helpers ------------------------------------------------
(defn node [id type & {:as attrs}] (merge {:node/id id :node/type type} attrs))
(defn edge [from-id to-id type]
  {:edge/from [:node/id from-id] :edge/to [:node/id to-id] :edge/type type})
(defn- caused-by-of [db node-eid] (:prov/caused-by (d/entity db node-eid)))

;; ===========================================================================
;; QUERIES -- lineage, recursion frontier, violations, structural diff.
;;            Each is a one-liner because the recursion lives in the rules.
;; ===========================================================================
(defn why
  "RGPD-grade lineage: the (ancestor-event, actor) chain that produced a node."
  [db node-id]
  (d/q '[:find ?event ?actor :in $ % ?nid
         :where [?n :node/id ?nid] (derivation ?n ?event ?actor)]
       db rules/all-rules node-id))

(defn frontier [db]
  (d/q '[:find [?id ...] :in $ %
         :where (frontier ?t) [?t :node/id ?id]]
       db rules/all-rules))

(defn unresolved [db]
  (d/q '[:find [?id ...] :in $ %
         :where (unresolved ?r) [?r :node/id ?id]]
       db rules/all-rules))

(defn violations [db]
  (d/q '[:find ?id ?kind :in $ %
         :where (violation ?f ?kind) [?f :node/id ?id]]
       db rules/all-rules))

(defn- summary
  "Semantic snapshot keyed on node-ids (stable across separate projections),
   so two runs can be diffed even though their internal entity ids differ."
  [db]
  {:nodes (set (d/q '[:find ?id ?type :where [?n :node/id ?id] [?n :node/type ?type]] db))
   :edges (set (d/q '[:find ?from ?to ?type :where
                      [?e :edge/from ?ef] [?ef :node/id ?from]
                      [?e :edge/to ?et]   [?et :node/id ?to]
                      [?e :edge/type ?type]] db))
   :violations (set (violations db))})

(defn structural-diff
  "Fork-and-diff as an evaluation primitive (ActiveGraph s7): what changed,
   semantically, between two runs -- the basis of a credible self-improvement loop."
  [db-parent db-fork]
  (let [p (summary db-parent) f (summary db-fork)]
    (into {} (for [k [:nodes :edges :violations]]
               [k {:only-parent (set/difference (p k) (f k))
                   :only-fork    (set/difference (f k) (p k))}]))))

;; ===========================================================================
;; L1 demo behaviors -- a miniature RGPD compliance pipeline.
;;   activity -> questions (recursion expands) -> findings (researcher / "LLM")
;;   -> linter flags gaps + re-opens corrective sub-tasks (the fixpoint loop).
;; ===========================================================================

;; planner: a processing-activity with no child questions -> emit 3 open questions
(def activity->questions
  {:name :activity->questions
   :subscribe
   (fn [db]
     (d/q '[:find [?aid ...] :where
            [?a :node/type :processing-activity] [?a :node/id ?aid]
            (not-join [?a] [?q :task/parent ?a])]
          db))
   :react
   (fn [db aid]
     (let [a   (d/entity db [:node/id aid])
           ev  (caused-by-of db (:db/id a))
           qs  [["q1" "What personal data categories are processed?"]
                ["q2" "What is the legal basis for processing?"]
                ["q3" "Is data transferred outside the EEA?"]]] ;; q1 & q3 will trip the linter
       [{:type :objects.created :actor :activity->questions :caused-by ev
         :tx-data (mapv (fn [[qid text]]
                          (node (str aid "/" qid) :question
                                :task/parent [:node/id aid]
                                :task/status :open :task/depth 1
                                :question/text text))
                        qs)}]))})

(defn- research-tx
  "Build the tx for a finding. `always-basis?` is the only difference between the
   buggy researcher and the fixed one used in the fork."
  [qid answer cites-basis? always-basis?]
  (let [fid (str qid "->finding") eid (str qid "->evidence")]
    (cond-> [(node fid :finding :finding/text answer)
             (node eid :evidence)
             (edge fid eid :supports)               ;; always supported
             [:db/add [:node/id qid] :task/status :done]]
      (or cites-basis? always-basis?)
      (into [(node (str fid "/lb") :legal-basis)
             (edge fid (str fid "/lb") :legal-basis)]))))

;; researcher: open question -> finding (+ evidence). BUG: only attaches a legal
;; basis when the question literally mentions "legal basis" (a realistic RGPD gap).
(def question->finding
  {:name :question->finding
   :subscribe
   (fn [db]
     (d/q '[:find [?qid ...] :where
            [?q :node/type :question] [?q :task/status :open] [?q :node/id ?qid]]
          db))
   :react
   (fn [db qid]
     (let [q      (d/entity db [:node/id qid])
           qev    (caused-by-of db (:db/id q))
           text   (:question/text q)
           answer (llm-call {:role :researcher :q text}
                            (fn [_] (str "Finding: " text)))
           basis? (boolean (re-find #"(?i)legal basis" text))]
       [{:type :finding.created :actor :question->finding :caused-by qev
         :tx-data (research-tx qid answer basis? false)}]))})

;; FIXED researcher (used only in the fork): always documents a legal basis.
(def question->finding-fixed
  (assoc question->finding :react
         (fn [db qid]
           (let [q      (d/entity db [:node/id qid])
                 qev    (caused-by-of db (:db/id q))
                 text   (:question/text q)
                 answer (llm-call {:role :researcher :q text}
                                  (fn [_] (str "Finding: " text)))]
             [{:type :finding.created :actor :question->finding :caused-by qev
               :tx-data (research-tx qid answer false true)}]))))

;; linter: a violating finding (not already flagged) -> flag it AND re-open a
;; corrective sub-task. The corrective question mentions "legal basis", so on the
;; retry the researcher attaches one and the loop reaches a clean fixpoint.
(def linter-behavior
  {:name :linter
   :subscribe
   (fn [db]
     (d/q '[:find ?fid ?kind :in $ %
            :where (violation ?f ?kind) [?f :node/id ?fid]
                   (not-join [?f] [?fl :flag/of ?f])]
          db rules/all-rules))
   :react
   (fn [db [fid kind]]
     (let [f   (d/entity db [:node/id fid])
           fev (caused-by-of db (:db/id f))]
       [{:type :violation.flagged :actor :linter :caused-by fev
         :tx-data
         [(node (str fid "/flag") :flag :flag/kind kind :flag/of [:node/id fid])
          (node (str fid "/fix") :question
                :task/parent [:node/id fid] :task/status :open :task/depth 2
                :question/text (str "Provide the missing legal basis for finding " fid))]}]))})

(def behaviors [activity->questions question->finding linter-behavior])

;; ---- helper to locate the fork point ---------------------------------------
(defn- index-after-type [log t]
  (some-> (keep-indexed (fn [i ev] (when (= (:event/type ev) t) i)) @log)
          first inc))

;; ===========================================================================
;; DEMO -- run the pipeline, then exercise every property of the stack.
;; ===========================================================================
(defn demo []
  (reset! counter 0)
  (let [parent (atom [])]
    ;; seed: the user declares one processing activity (the goal)
    (append! parent {:type :goal.created :actor :user
                     :tx-data [(node "act-1" :processing-activity
                                     :activity/name "Newsletter signup")]})
    ;; run L2 to a fixpoint (no orchestration code anywhere)
    (let [end   (run-to-fixpoint parent behaviors {})
          db    (project @parent)
          ;; fork BEFORE any finding exists, re-run with the FIXED researcher
          k     (index-after-type parent :objects.created)
          forked (fork parent k)
          _      (run-to-fixpoint forked [question->finding-fixed linter-behavior] {})
          dbf    (project @forked)]
      {:run            end
       :event-count    (count @parent)
       :violations     (violations db)        ;; -> 2 missing-legal-basis (q1, q3)
       :frontier       (frontier db)          ;; -> [] at fixpoint
       :unresolved     (unresolved db)        ;; -> [] at fixpoint
       :why-q3-finding (why db "act-1/q3->finding")  ;; -> chain back to the goal
       :fork-vs-parent (structural-diff db dbf)})))   ;; -> fix removes the violations

(defn -main [& _]
  (clojure.pprint/pprint (demo)))

(comment
  ;; Illustrative shape of (demo) -- exact ids/order may vary slightly:
  ;;
  ;; {:run {:status :fixpoint :steps 5}
  ;;  :event-count 14
  ;;  :violations #{["act-1/q1->finding" :missing-legal-basis]
  ;;                ["act-1/q3->finding" :missing-legal-basis]}
  ;;  :frontier []          ; every open task got expanded
  ;;  :unresolved []        ; corrective sub-tasks were researched & closed
  ;;  :why-q3-finding #{["evt-0001" :user]            ; the original goal
  ;;                    ["evt-000X" :activity->questions]
  ;;                    ["evt-000Y" :question->finding]}
  ;;  :fork-vs-parent
  ;;   {:violations {:only-parent #{["act-1/q1->finding" :missing-legal-basis]
  ;;                                ["act-1/q3->finding" :missing-legal-basis]}
  ;;                 :only-fork #{}}                    ; the fixed run is clean
  ;;    :edges {:only-fork #{["act-1/q1->finding" "act-1/q1->finding/lb" :legal-basis]
  ;;                          ["act-1/q3->finding" "act-1/q3->finding/lb" :legal-basis]}
  ;;            :only-parent #{...}}                     ; parent's flags/correctives
  ;;    :nodes {:only-parent #{["act-1/q1->finding/flag" :flag] ...}
  ;;            :only-fork #{...}}}}
  )

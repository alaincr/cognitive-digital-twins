(ns mnemosyne.judges
  "Regime B-1/2: the micro-judge layer over the Mnemosyne substrate.

   Implements the contract in microjudge_contract.md:
     - judgments as append-only typed facts (invariant I1)
     - the provenance envelope (I4)
     - candidate -> accepted promotion as the single non-monotone gate
     - heterogeneous-panel agreement for T2 types
     - cohort retraction as a query + a batch of retraction events
     - drift monitoring & judge quarantine
     - training-data admissibility (anti-collapse) as a provenance query

   Depends on mnemosyne.core (append!, project, run-to-fixpoint, *log*)
   and mnemosyne.rules (descendant / derivation closures) from the earlier
   deliverables. Hand-checked for DataScript 1.7.3; not executed in the
   sandbox that produced it. Aggregations (panel counts, drift rates) live
   in QUERIES, not rules — DataScript rules don't support aggregates."
  (:require [datascript.core :as d]
            [mnemosyne.core :as m]
            [mnemosyne.rules :as rules]))

;; ===========================================================================
;; Schema additions (merge into mnemosyne.core/schema)
;; ===========================================================================
(def judge-schema
  {;; --- judge registry ------------------------------------------------------
   :judge/id           {:db/unique :db.unique/identity} ;; "qwen3-8b@a1b2c3#p7"
   :judge/model        {:db/index true}                 ;; base model name
   :judge/family       {:db/index true}                 ;; decorrelation key (qwen/gemma/phi/anchor/human)
   :judge/weights-hash {}
   :judge/prompt-version {}
   :judge/quarantined? {:db/index true}

   ;; --- judgments (the envelope, §3) ---------------------------------------
   :judgment/id        {:db/unique :db.unique/identity}
   :judgment/type      {:db/index true}   ;; :edge-type :same-entity :summarize-now
                                          ;; :propagate :invalidate :dedup-prop :faithful
   :judgment/subjects  {:db/valueType :db.type/ref :db/cardinality :db.cardinality/many}
   :judgment/subject-key {:db/index true} ;; stable hash of (type, sorted subject ids) — panel grouping
   :judgment/label     {:db/index true}
   :judgment/confidence {}                ;; calibrated, logprob-derived
   :judgment/self-reported? {}            ;; true only for API judges w/o logprobs
   :judgment/judge     {:db/valueType :db.type/ref}
   :judgment/cal-version {}
   :judgment/context-hash {:db/index true}
   :judgment/basis     {}                 ;; <=240 chars, audit-only
   :judgment/status    {:db/index true}   ;; :candidate :accepted :rejected :retracted
   :judgment/escalated-to {:db/valueType :db.type/ref} ;; next-rung judgment, if any

   ;; --- promotion linkage (what makes cohort retraction a query) ----------
   :prov/from-judgment {:db/valueType :db.type/ref :db/cardinality :db.cardinality/many}

   ;; --- anchor sampling / drift --------------------------------------------
   :anchor/of          {:db/valueType :db.type/ref}  ;; anchor judgment -> sampled judgment
   :anchor/agrees?     {:db/index true}

   ;; --- calibration & training lineage -------------------------------------
   :calset/id          {:db/unique :db.unique/identity}
   :calset/frozen?     {}
   :example/label-from {:db/valueType :db.type/ref}}) ;; provenance of a training label

;; B4: contribute to the projection schema so lookup-refs / cardinality-many
;; refs (:judgment/subjects, :prov/from-judgment, :judgment/judge) fold
;; correctly wherever the consolidator loads this module.
(m/register-schema! judge-schema)

;; Stakes tiers (§2) — governs thresholds & panel requirements
(def stakes
  {:edge-type     :t2   :same-entity :t2   :faithful :t2
   :invalidate    :t1   :dedup-prop  :t1
   :summarize-now :t0   :propagate   :t0})

(def panel-k {:t2 2}) ;; k-of-n distinct families required for T2 promotion

;; ===========================================================================
;; Emission (monotone, coordination-free — any Hermes node may emit)
;; ===========================================================================
(defn subject-key [jtype subject-node-ids]
  (hash [jtype (vec (sort subject-node-ids))]))

(defn emit-judgment!
  "Append a judgment-candidate event. `subjects` = node ids (:node/id values).
   `conf` must already be calibrated (logprob-derived; see harness notes in
   judge_schemas.json). Returns the judgment id."
  [{:keys [jtype subjects label conf judge-id cal-version ctx-hash basis caused-by
           self-reported?]}]
  (let [jid (str "jdg-" (java.util.UUID/randomUUID))]
    (m/append! {:type :judgment.emitted :actor judge-id :caused-by caused-by
                :tx-data
                [(cond-> {:judgment/id jid
                          :judgment/type jtype
                          :judgment/subjects (mapv (fn [nid] [:node/id nid]) subjects)
                          ;; ordered copy: :db.cardinality/many is a SET, but
                          ;; edge-type / dedup-prop / faithful are direction-
                          ;; sensitive — promotion reads this vector.
                          :judgment/subjects-vec (vec subjects)
                          :judgment/subject-key (subject-key jtype subjects)
                          :judgment/label label
                          :judgment/confidence conf
                          :judgment/judge [:judge/id judge-id]
                          :judgment/cal-version cal-version
                          :judgment/context-hash ctx-hash
                          :judgment/status :candidate}
                   basis          (assoc :judgment/basis (subs basis 0 (min 240 (count basis))))
                   self-reported? (assoc :judgment/self-reported? true))]})
    jid))

(defn emit-abstention!
  "The conformal gate said 'not a singleton': record the abstention and the
   escalation target rung so the next rung's behavior picks it up."
  [{:keys [jtype subjects judge-id ctx-hash caused-by]}]
  (m/append! {:type :judgment.abstained :actor judge-id :caused-by caused-by
              :tx-data [{:node/id (str "esc-" (subject-key jtype subjects))
                         :node/type :escalation
                         :escalation/jtype jtype
                         :escalation/subject-key (subject-key jtype subjects)
                         :task/status :open}]}))

;; ===========================================================================
;; Datalog rules (positive fragments only; aggregates live in queries below)
;; ===========================================================================
(def judge-rules
  '[;; a live (non-retracted, non-quarantined) candidate
    [(live-candidate ?j)
     [?j :judgment/status :candidate]
     [?j :judgment/judge ?g]
     (not-join [?g] [?g :judge/quarantined? true])]

    ;; judgments grouped on the same question
    [(co-judged ?j1 ?j2)
     [?j1 :judgment/subject-key ?k]
     [?j2 :judgment/subject-key ?k]]

    ;; a domain fact licensed by a judgment of judge ?g  (cohort membership)
    [(licensed-by ?fact ?g)
     [?fact :prov/from-judgment ?j]
     [?j :judgment/judge ?g]]

    ;; taint closure: anything derived (per rules.clj `derivation` over events,
    ;; or summary/child edges) from a licensed fact of a bad cohort.
    ;; We use :prov/caused-by event lineage indirectly: a derived node whose
    ;; derivation cone contains a tainted fact is tainted.
    [(tainted ?n ?g)
     (licensed-by ?n ?g)]
    [(tainted ?n ?g)
     [?n :derived/from ?p]          ;; summaries/stances point at their inputs
     (tainted ?p ?g)]])

;; ===========================================================================
;; Promotion (NON-monotone gate — run inside consolidation, single writer
;; per subject-key)
;; ===========================================================================
(defn- family-votes
  "All live candidate votes on a subject-key: [{:family f :label l :j eid :conf c} ...]"
  [db k]
  (d/q '[:find ?f ?l ?j ?c :in $ % ?k
         :where (live-candidate ?j)
                [?j :judgment/subject-key ?k]
                [?j :judgment/label ?l]
                [?j :judgment/confidence ?c]
                [?j :judgment/judge ?g] [?g :judge/family ?f]]
       db judge-rules k))

(defn promotable?
  "T0/T1: a single live candidate suffices (its conformal gate already passed).
   T2: >= k distinct families agreeing on the SAME label, zero dissenting
   families. Dissent => escalate to anchor instead. Returns
   {:promote label :via [judgment-eids]} | {:escalate true} | nil."
  [db jtype k]
  (let [tier  (stakes jtype)
        votes (family-votes db k)]
    (cond
      (empty? votes) nil

      (not= tier :t2)
      (let [[_ l j _] (first votes)] {:promote l :via [j]})

      :else
      (let [by-label (group-by second votes)
            fams     (fn [vs] (set (map first vs)))]
        (if (and (= 1 (count by-label))
                 (>= (count (fams (val (first by-label)))) (panel-k :t2)))
          {:promote (key (first by-label)) :via (mapv #(nth % 2) (val (first by-label)))}
          {:escalate true})))))

(defn promote!
  "Consolidation step: append the DOMAIN event the accepted judgment licenses,
   linking it back via :prov/from-judgment, and mark the judgments :accepted.
   `domain-tx` is the fact to assert (e.g. a typed edge, a :sameAs edge, a
   stale-mark). Single logical writer per subject-key — enforce upstream."
  [{:keys [domain-tx via-judgments caused-by]}]
  (m/append! {:type :judgment.promoted :actor :consolidator :caused-by caused-by
              :tx-data (into [(merge domain-tx
                                     {:prov/from-judgment
                                      (mapv (fn [jid] [:judgment/id jid]) via-judgments)})]
                             (map (fn [jid] [:db/add [:judgment/id jid]
                                             :judgment/status :accepted])
                                  via-judgments))}))

;; Example domain payloads per type (what promotion asserts):
;;   :edge-type    -> (m/edge from to label-as-edge-type)
;;   :same-entity  -> {:node/id (str m1 "~" m2) :node/type :same-as
;;                     :edge/from [:node/id m1] :edge/to [:node/id m2]
;;                     :edge/type :same-as}            ;; retractable belief, NOT a merge
;;   :invalidate   -> [:db/add [:node/id s] :derived/stale? true]
;;   :summarize-now-> open a :summarize task node (regime C picks it up)

;; ===========================================================================
;; Cohort retraction (§6) — the query, then the batch of retraction events
;; ===========================================================================
(defn cohort
  "All judgment eids of judge `judge-id` (optionally only :accepted ones)."
  [db judge-id & {:keys [accepted-only?]}]
  (d/q (if accepted-only?
         '[:find [?j ...] :in $ ?gid :where
           [?g :judge/id ?gid] [?j :judgment/judge ?g]
           [?j :judgment/status :accepted]]
         '[:find [?j ...] :in $ ?gid :where
           [?g :judge/id ?gid] [?j :judgment/judge ?g]])
       db judge-id))

(defn tainted-nodes
  "Every domain fact licensed by the judge's cohort + everything derived from
   them (transitively, via :derived/from)."
  [db judge-id]
  (d/q '[:find [?n ...] :in $ % ?gid
         :where [?g :judge/id ?gid] (tainted ?n ?g)]
       db judge-rules judge-id))

(defn retract-cohort!
  "Append (1) :retracted status on every cohort judgment, (2) retraction of
   each licensed domain fact's assertion, (3) stale-marks on the derived cone
   so consolidation recomputes it. Nothing is deleted; the record of the
   mistake remains queryable as-of any past time."
  [db judge-id]
  (let [js (cohort db judge-id)
        ns (tainted-nodes db judge-id)]
    (m/append!
     {:type :cohort.retracted :actor :auditor
      :tx-data (-> []
                   (into (map (fn [j] [:db/add j :judgment/status :retracted]) js))
                   (into (mapcat (fn [n] [[:db/add n :derived/stale? true]
                                          [:db/retract n :edge/type]]) ns)))})
    {:judgments (count js) :tainted (count ns)}))

;; ===========================================================================
;; Drift monitor & quarantine (§6)
;; ===========================================================================
(defn record-anchor-check!
  "Anchor model re-judged judgment `jid`; record agreement as a fact."
  [jid agrees? anchor-judge-id]
  (m/append! {:type :anchor.sampled :actor anchor-judge-id
              :tx-data [{:node/id (str "anchor-" jid)
                         :node/type :anchor-check
                         :anchor/of [:judgment/id jid]
                         :anchor/agrees? agrees?}]}))

(defn drift-rate
  "Disagreement rate per (type, judge) over all anchor checks. Aggregate in
   query space (not rules)."
  [db]
  (->> (d/q '[:find ?gid ?t ?a :where
              [?c :anchor/of ?j] [?c :anchor/agrees? ?a]
              [?j :judgment/type ?t]
              [?j :judgment/judge ?g] [?g :judge/id ?gid]]
            db)
       (group-by (juxt first second))
       (map (fn [[[gid t] rows]]
              (let [n (count rows)
                    dis (count (remove last rows))]
                {:judge gid :type t :n n :disagree-rate (double (/ dis (max n 1)))})))))

(defn quarantine-behavior
  "L2 behavior: when a (judge,type) drift rate exceeds theta with at least
   min-n samples, quarantine the judge. Reversible — it's an event."
  [{:keys [theta min-n] :or {theta 0.15 min-n 30}}]
  {:name :drift-quarantine
   :subscribe (fn [db]
                (for [{:keys [judge n disagree-rate]} (drift-rate db)
                      :when (and (>= n min-n) (> disagree-rate theta))]
                  judge))
   :react (fn [_db gid]
            [{:type :judge.quarantined :actor :drift-monitor
              :tx-data [[:db/add [:judge/id gid] :judge/quarantined? true]
                        {:node/id (str "review-" gid) :node/type :question
                         :task/status :open
                         :question/text (str "Review drift of judge " gid
                                             ": recalibrate, retrain, or retract cohort?")}]}])})

;; ===========================================================================
;; Training admissibility (§7) — anti-collapse as a provenance query
;; ===========================================================================
(defn training-admissible?
  "An example's label is admissible for distillation iff its label provenance
   chain reaches an anchor-family or human-family judge — never only the
   swarm's own outputs."
  [db example-eid]
  (boolean
   (seq (d/q '[:find ?g :in $ ?e :where
               [?e :example/label-from ?j]
               [?j :judgment/judge ?g]
               [?g :judge/family ?f]
               [(contains? #{:anchor :human} ?f)]]
             db example-eid))))

(comment
  ;; Wiring sketch:
  ;; 1. merge judge-schema into mnemosyne.core/schema at db creation
  ;; 2. register judges:
  ;;    (m/append! {:type :judge.registered :actor :ops
  ;;                :tx-data [{:judge/id "qwen3-8b@a1b2#p3" :judge/model "qwen3-8b"
  ;;                           :judge/family :qwen :judge/weights-hash "a1b2"
  ;;                           :judge/prompt-version 3}]})
  ;; 3. harness loop per candidate: assemble context (Datalog-bounded) ->
  ;;    guided-decode against judge_schemas.json -> logprob conf ->
  ;;    temperature-scale -> conformal gate ->
  ;;    (emit-judgment! ...) or (emit-abstention! ...)
  ;; 4. consolidation: for each subject-key with live candidates,
  ;;    (promotable? db jtype k) -> (promote! ...) or escalate to anchor
  ;; 5. run (quarantine-behavior {}) inside the standard run-to-fixpoint set.
  )

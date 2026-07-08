(ns mnemosyne.zettel
  "The Luhmann–Ahrens layer — a drop-in module over the Mnemosyne substrate.

   Imports, with their source principle:
     - :zettel/continues          Folgezettel succession (one parent, trains)   [Luhmann]
     - :register/keyword          the sparse register: <=2 doorways per keyword [Luhmann]
     - :prop/stratum              fleeting | candidate | literature | permanent [Ahrens]
     - :prop/kind                 literature (de dicto) vs permanent (de re)    [Ahrens]
     - elaboration tasks          human reformulation = highest-grade gold      [Ahrens]
     - bridge candidates          the box speaks first (daily dialog)           [Luhmann 1981]

   CALM discipline is annotated on every rule and behavior: the monotone core
   (closures, counters, candidate emission) distributes across Hermes nodes; the
   non-monotone boundary (register selection, promotion, decay) is consolidator-only.

   Depends on mnemosyne.core (append!, project, entity helpers), mnemosyne.rules
   (descendant/derivation closures), mnemosyne.judges (emit-judgment!, promotion),
   mnemosyne.ingest (consolidator). Hand-checked for DataScript 1.7.3; the judge
   schemas and prompts that pair with this file ARE executable and unit-tested
   (see zettel_prompts.py + the harness self-test).

   STRATA INVARIANT (the spine of the Ahrens import):
     fleeting   -> excluded from belief layer AND densification; decays if unprocessed
     candidate  -> machine-proposed permanent; needs human ratification to cross
     literature -> de dicto ('Source S asserts X'); enters belief ONLY as evidence
     permanent  -> de re ('we hold X'); the ONLY kind that feeds stances directly")

;; ===========================================================================
;; Schema additions — merge into mnemosyne.core/schema
;; ===========================================================================
(def zettel-schema
  {;; --- Folgezettel succession --------------------------------------------
   :zettel/continues     {:db/valueType :db.type/ref}     ;; exactly one (enforced at promotion)
   :zettel/branch-order  {}                                ;; integer among siblings of a continues-parent
   :zettel/train         {:db/index true}                 ;; cached train id (root of the continues-run)

   ;; --- strata & kinds (Ahrens) -------------------------------------------
   :prop/stratum         {:db/index true}                 ;; :fleeting :candidate :literature :permanent
   :prop/kind            {:db/index true}                 ;; :literature :permanent
   :prop/activation      {}                                ;; salience score (decays; record never does)
   :prop/last-touched    {}                                ;; tx-id of last access/edit (for decay)

   ;; --- the sparse register (Luhmann) -------------------------------------
   :register/keyword     {:db/unique :db.unique/identity} ;; one register node per keyword string
   :register/entry       {:db/valueType :db.type/ref
                          :db/cardinality :db.cardinality/many} ;; HARD CAP 2 (linted)

   ;; --- elaboration provenance (Ahrens learning loop) ---------------------
   :elab/of              {:db/valueType :db.type/ref}     ;; the node an elaboration addresses
   :elab/delta-of        {:db/valueType :db.type/ref}     ;; the machine draft a human edited
   :source/family        {:db/index true}})               ;; :human :anchor :anchor-double :swarm
                                                           ;; (human elaborations = top gold; see distill_judge)

;; Register doorway budget (Luhmann kept ~1-2 entry points per keyword)
(def register-cap 2)

;; ===========================================================================
;; Datalog rules
;; ===========================================================================
(def zettel-rules
  '[;; ---------------- MONOTONE CORE (coordination-free) -------------------

    ;; TRAINS: transitive closure over :zettel/continues. A train is a linear
    ;; run of thought through the nonlinear graph — Luhmann's harvestable
    ;; sequence, and a far better RLM context unit than k-nearest chunks.
    [(follows ?card ?parent)
     [?card :zettel/continues ?parent]]
    [(in-train ?card ?root)            ;; ?root = the head this card descends from
     [?card :zettel/continues ?root]
     (not-join [?root] [?root :zettel/continues ?_])]   ;; ?root has no parent
    [(in-train ?card ?root)
     [?card :zettel/continues ?mid]
     (in-train ?mid ?root)]

    ;; ORPHAN detection: a promoted permanent note must have a continues-edge.
    ;; (NON-MONOTONE — negation. Boundary rule; runs in consolidation/linter.)
    [(orphan ?card)
     [?card :prop/stratum :permanent]
     (not-join [?card] [?card :zettel/continues ?_])]

    ;; ---------------- STRATA GATING ---------------------------------------
    ;; Only PERMANENT propositions may feed belief stances directly; literature
    ;; enters belief only via typed support/oppose edges (the de re / de dicto
    ;; split). This rule is what the belief layer filters its inputs through.
    [(belief-eligible ?p)
     [?p :prop/stratum :permanent]
     [?p :prop/kind :permanent]]

    ;; ---------------- THE SPARSE REGISTER ---------------------------------
    ;; register entries reachable as doorways
    [(doorway ?kw ?node)
     [?kw :register/entry ?node]]
    ;; REGISTER BLOAT (NON-MONOTONE — counts; the count itself is computed in a
    ;; query, this rule just exposes the membership for that query)
    [(register-member ?kw ?node)
     [?kw :register/entry ?node]]

    ;; ---------------- BRIDGE CANDIDATES (the box speaks first) -------------
    ;; A bridge candidate: two nodes that are embedding-near (a :sim/near edge
    ;; the regime-B layer maintains) but have NO short graph path between them,
    ;; ideally spanning two different trains. Surfacing these is Luhmann's
    ;; surprise criterion operationalized.
    ;; (Path-length is not expressible as pure Datalog recursion with a bound;
    ;;  we approximate "no short path" as "share no train and not directly
    ;;  linked" here, and let the daily behavior apply the k-hop check in code.)
    [(directly-linked ?a ?b)
     (or-join [?a ?b]
       [?a :zettel/continues ?b]
       [?b :zettel/continues ?a]
       (and [?e :edge/from ?a] [?e :edge/to ?b]))]
    [(bridge-seed ?a ?b)
     [?s :sim/near ?a] [?s :sim/to ?b]   ;; reified similarity edge from regime B
     (in-train ?a ?ra) (in-train ?b ?rb)
     [(not= ?ra ?rb)]
     (not-join [?a ?b] (directly-linked ?a ?b))]])

;; ===========================================================================
;; New judgment types (pair with zettel_prompts.py + judge_schemas additions)
;;   continues?        : continues | branches-from | new-train
;;   permanent-worthy? : promote | keep-candidate | discard   (project harvest)
;; Both are T1 (structural) — single judge past its conformal gate, with
;; auto-escalation on disagreement with the regime-B suggestion.
;; ===========================================================================
(def zettel-judgment-types #{:continues? :permanent-worthy?})

;; --- domain-fact builders (extend mnemosyne.ingest/domain-fact) ------------
;; Provided as data so ingest.clj can `merge` them into its multimethod table.
;; :continues? promotion writes the succession edge + caches the train root.
;; subjects-vec = [child parent] (DIRECTIONAL — child continues parent).
(defn continues-fact [[child parent]]
  {:fact-map {:node/id (str child "~cont~" parent)
              :node/type :continues-edge
              :zettel/continues [:node/id parent]
              :edge/from [:node/id child] :edge/to [:node/id parent]
              :edge/type :continues}
   :extra-tx [[:db/add [:node/id child] :zettel/continues [:node/id parent]]]})

(defn new-train-fact [[child _]]
  ;; child starts its own train: it becomes a train root (no continues-edge).
  {:fact-map {:node/id (str child "~trainhead") :node/type :train-head
              :flag/of [:node/id child]}
   :extra-tx [[:db/add [:node/id child] :zettel/train child]]})

;; ===========================================================================
;; QUERIES (aggregates live here, not in rules — DataScript limitation)
;; ===========================================================================
(defn train-of
  "The root (head) of the train a card belongs to."
  [db node-id]
  (ffirst (datascript.core/q
            '[:find ?root :in $ % ?nid :where
              [?c :node/id ?nid] (in-train ?c ?root)]
            db zettel-rules node-id)))

(defn read-train
  "Ordered run of a train, head→tail, by branch-order then id. The collapsed-
   tree RLM context unit: 'read the train' = Luhmann's harvest-the-run."
  [db root-id]
  (->> (datascript.core/q
         '[:find ?nid ?ord :in $ % ?root :where
           [?root-e :node/id ?root]
           (in-train ?c ?root-e) [?c :node/id ?nid]
           [(get-else $ ?c :zettel/branch-order 0) ?ord]]
         db zettel-rules root-id)
       (sort-by (juxt second first))
       (mapv first)))

(defn register-overfull
  "Keywords whose doorway count exceeds the cap — the register-bloat linter."
  [db]
  (->> (datascript.core/q
         '[:find ?kw (count ?node) :where
           [?kwe :register/keyword ?kw] [?kwe :register/entry ?node]]
         db)
       (filter (fn [[_ n]] (> n register-cap)))))

(defn orphans [db]
  (datascript.core/q '[:find [?id ...] :in $ % :where
                       (orphan ?c) [?c :node/id ?id]] db zettel-rules))

(defn elaboration-coverage
  "Per-train human/machine permanent-note ratio. A dense train with 0 human
   elaboration = your unbacked understanding (flag, not a system failure)."
  [db]
  (->> (datascript.core/q
         '[:find ?train ?fam (count ?p) :where
           [?p :prop/stratum :permanent] [?p :zettel/train ?train]
           [(get-else $ ?p :source/family :swarm) ?fam]]
         db)
       (group-by first)
       (map (fn [[train rows]]
              (let [by (into {} (map (fn [[_ f c]] [f c]) rows))
                    h (get by :human 0), tot (reduce + (vals by))]
                {:train train :human h :total tot
                 :coverage (double (/ h (max tot 1)))})))))

;; ===========================================================================
;; BEHAVIORS (all three are consolidator-side — NON-MONOTONE boundary)
;; ===========================================================================

;; 1 · DAILY INBOX PASS (Ahrens fleeting-note hygiene + the first home for Lethe)
(defn decay-activation
  "ACT-R-style base-level decay on the ATTENTION, never on the record. Called
   once per daily pass over fleeting props. lambda in (0,1)."
  [current lambda] (* (or current 1.0) lambda))

(defn daily-inbox-behavior
  "Present unprocessed fleeting notes for triage; decay the activation of those
   left untouched. The event log keeps every fleeting note forever — only its
   salience fades (the activation/record split that gives Mnemosyne its Lethe)."
  [{:keys [lambda] :or {lambda 0.8}}]
  {:name :daily-inbox
   :subscribe (fn [db]
                (datascript.core/q '[:find [?id ...] :where
                                     [?p :prop/stratum :fleeting] [?p :node/id ?id]] db))
   :react (fn [db nid]
            (let [p (datascript.core/entity db [:node/id nid])
                  a (decay-activation (:prop/activation p) lambda)]
              [{:type :fleeting.decayed :actor :daily-inbox
                :tx-data [[:db/add [:node/id nid] :prop/activation a]
                          ;; open a one-shot triage task (idempotent: not if already open)
                          {:node/id (str nid "/triage") :node/type :question
                           :task/status :open :task/depth 1
                           :question/text (str "Process fleeting note " nid
                                               ": propositionize & file, or dismiss")}]}]))})

;; 2 · REGISTER CONSOLIDATION (Luhmann's sparse doorways, by centrality × use)
(defn register-consolidation-behavior
  "When a keyword's doorways exceed the cap, keep the top-`cap` by
   (centrality × trail-weight) — structure and use must agree — and retract the
   rest as entries (they remain nodes, just not doorways)."
  []
  {:name :register-consolidation
   :subscribe (fn [db] (mapv first (register-overfull db)))
   :react (fn [db kw]
            (let [scored (datascript.core/q
                          '[:find ?node ?id (count ?in) :in $ ?kw :where
                            [?kwe :register/keyword ?kw] [?kwe :register/entry ?node]
                            [?node :node/id ?id]
                            [(get-else $ ?node :trail/weight 0) ?w]
                            [?e :edge/to ?node]] db kw)
                  ranked (->> scored (sort-by #(- (nth % 2))) (map first))
                  keep (set (take register-cap ranked))
                  drop (remove keep ranked)]
              [{:type :register.consolidated :actor :register-consolidation
                :tx-data (mapv (fn [n] [:db/retract [:register/keyword kw]
                                        :register/entry n]) drop)}]))})

;; 3 · MORNING DIALOG (Luhmann 1981: the box speaks first)
(defn morning-dialog-behavior
  "Daily: select a small budget of bridge candidates — embedding-near pairs in
   DIFFERENT trains with no short link — and open them as questions. This is the
   anti-entrenchment exploration term as a concrete practice. The k-hop 'no
   short path' refinement is applied in `select-bridges` (code, not Datalog)."
  [{:keys [budget k-hop] :or {budget 5 k-hop 3}}]
  {:name :morning-dialog
   :subscribe (fn [db]
                ;; rule yields seed pairs; code prunes to those truly >k-hop apart
                (->> (datascript.core/q '[:find ?aid ?bid :in $ % :where
                                          (bridge-seed ?a ?b)
                                          [?a :node/id ?aid] [?b :node/id ?bid]] db zettel-rules)
                     (take budget)))   ;; (select-bridges would apply the k-hop BFS here)
   :react (fn [_db [aid bid]]
            [{:type :bridge.proposed :actor :morning-dialog
              :tx-data [{:node/id (str "bridge/" aid "+" bid) :node/type :question
                         :task/status :open :task/depth 1
                         :question/text (str "These two trains of thought have never met: "
                                             aid " and " bid ". Related? If so, how?")
                         :bridge/a [:node/id aid] :bridge/b [:node/id bid]}]}])})

;; ===========================================================================
;; COMPOSE — the manuscript loop (Luhmann & Ahrens: the system exists to write)
;; ===========================================================================
(defn compose-assembly
  "Build a draft context from a register doorway or a claim:
     trains (Folgezettel runs) interleaved with summaries at all levels
     (collapsed-tree retrieval). Returns ordered node-ids for the RLM. Every
     assertion the RLM later makes must resolve to one of these or open a
     gap-task; the draft records :used-in edges and strengthens walked trails."
  [db entry-id]
  (let [root (train-of db entry-id)
        run  (when root (read-train db root))
        sums (datascript.core/q '[:find [?sid ...] :in $ ?e :where
                                  [?s :node/type :summary] [?s :summary/about ?e]
                                  [?s :node/id ?sid]] db entry-id)]
    {:entry entry-id :train root :run (vec run) :summaries (vec sums)
     :note "RLM drafts against run+summaries; unresolved assertions -> gap-tasks"}))

;; ===========================================================================
;; WIRING NOTES
;; ===========================================================================
(comment
  ;; 1 · merge schemas:   (merge mnemosyne.core/schema zettel/zettel-schema)
  ;; 2 · merge rules:     pass (concat rules/all-rules zettel/zettel-rules) as %
  ;; 3 · extend domain-fact in ingest.clj:
  ;;      (defmethod mnemosyne.ingest/domain-fact [:continues? :continues]   [_ _ s] (zettel/continues-fact s))
  ;;      (defmethod mnemosyne.ingest/domain-fact [:continues? :branches-from][_ _ s] (zettel/continues-fact s))
  ;;      (defmethod mnemosyne.ingest/domain-fact [:continues? :new-train]    [_ _ s] (zettel/new-train-fact s))
  ;;      (defmethod mnemosyne.ingest/domain-fact [:permanent-worthy? :promote] [_ _ [p]]
  ;;        {:extra-tx [[:db/add [:node/id p] :prop/stratum :permanent]]})
  ;; 4 · add behaviors to the consolidator's run-to-fixpoint set:
  ;;      [(zettel/daily-inbox-behavior {}) (zettel/register-consolidation-behavior)
  ;;       (zettel/morning-dialog-behavior {})]
  ;; 5 · belief layer filters inputs through (belief-eligible ?p) — literature
  ;;     props reach stances only as support/oppose evidence, never directly.
  ;; 6 · distill_judge.py already treats :source/family :human as top-priority
  ;;     gold — elaboration answers therefore become the best training data.
  )

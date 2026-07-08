(ns mnemosyne.belief
  "The belief layer, consolidator-side mirror of belief.py (WP-1b, SPEC-03).

   CALM placement: BOUNDARY. The grounded labelling is non-monotone in its
   OUT/UNDEC assignments, so stance recomputation is a consolidator function
   (like promotion), NEVER a Datalog rule and never distributed. Its inputs
   (discourse edges) and its outputs (appended stance events) are monotone.

   Semantics — identical to belief.py, reviewed against its 15 executed test
   vectors (SPEC-03 §6): grounded labelling over `opposes` (unique, skeptical,
   linear); `supports` = evidential tally over IN supporters only; `refines`
   excluded from semantics, reported as qualifiers.

   Hand-checked for DataScript 1.7.3; not executed in the authoring sandbox.
   Review checklist for this file = the Python vectors V1..V15."
  (:require [datascript.core :as d]
            [mnemosyne.core :as m]))

;; ===========================================================================
;; Edge extraction from the projection
;; ===========================================================================
(defn discourse-edges
  "All promoted discourse edges as {:type :from :to :id} maps."
  [db]
  (map (fn [[id t f to]] {:id id :type t :from f :to to})
       (d/q '[:find ?id ?t ?fid ?tid :where
              [?e :node/type :discourse-edge]
              [?e :node/id ?id] [?e :edge/type ?t]
              [?e :edge/from ?f] [?f :node/id ?fid]
              [?e :edge/to ?to] [?to :node/id ?tid]] db)))

;; ===========================================================================
;; Grounded labelling — the exact counter algorithm of SPEC-03 §2
;; ===========================================================================
(defn grounded-labelling
  "nodes: set of ids. atts: {attacked #{attackers}}. Returns {id :in|:out|:undec}.
   O(|A|+|R|); iteration-order invariant (grounded extension is unique)."
  [nodes atts]
  (let [universe (into (set nodes)
                       (concat (keys atts) (mapcat identity (vals atts))))
        attackers (into {} (map (fn [n] [n (set (get atts n #{}))]) universe))
        attacked-by (reduce (fn [acc [tgt srcs]]
                              (reduce (fn [a s] (update a s (fnil conj #{}) tgt))
                                      acc srcs))
                            {} attackers)]
    (loop [label (zipmap universe (repeat :undec))
           alive (into {} (map (fn [[n as]] [n (count as)]) attackers))
           queue (into clojure.lang.PersistentQueue/EMPTY
                       (sort (filter #(zero? (alive %)) universe)))]
      (if-let [n (peek queue)]
        (let [queue (pop queue)]
          (if (not= :undec (label n))
            (recur label alive queue)
            (let [label (assoc label n :in)
                  ;; everything n attacks goes OUT; their targets lose an attacker
                  [label alive queue]
                  (reduce
                   (fn [[l a q] mnode]
                     (if (not= :undec (l mnode))
                       [l a q]
                       (let [l (assoc l mnode :out)]
                         (reduce
                          (fn [[l2 a2 q2] k]
                            (let [a2 (update a2 k dec)]
                              (if (and (zero? (a2 k)) (= :undec (l2 k)))
                                [l2 a2 (conj q2 k)]
                                [l2 a2 q2])))
                          [l a q] (get attacked-by mnode #{})))))
                   [label alive queue] (get attacked-by n #{}))]
              (recur label alive queue))))
        label))))

;; ===========================================================================
;; Stance derivation (vocabulary of SPEC-03 §4)
;; ===========================================================================
(defn stance-of [label n-in-supporters]
  (case label
    :in    (if (pos? n-in-supporters) :accepted-supported :accepted-undisputed)
    :out   :rejected
    :undec :undecided))

(defn compute-stances
  "edges -> {node-id {:status .. :label .. :support {..} :qualifiers [..]}}"
  [edges]
  (let [atts (reduce (fn [m {:keys [type from to]}]
                       (if (= type :opposes)
                         (update m to (fnil conj #{}) from) m)) {} edges)
        sups (reduce (fn [m {:keys [type from to]}]
                       (if (= type :supports)
                         (update m to (fnil conj #{}) from) m)) {} edges)
        refs (reduce (fn [m {:keys [type from to id]}]
                       (if (= type :refines)
                         (update m to (fnil conj []) {:from from :edge-id id}) m))
                     {} edges)
        nodes (into #{} (mapcat (juxt :from :to)) edges)
        lab (grounded-labelling nodes atts)]
    (into {}
          (map (fn [n]
                 (let [in-s (filterv #(= :in (lab %)) (sort (get sups n #{})))]
                   [n {:label (lab n)
                       :status (stance-of (lab n) (count in-s))
                       :support {:n (count in-s) :in-supporters in-s}
                       :qualifiers (vec (sort-by :edge-id (get refs n [])))}])))
          nodes)))

;; ===========================================================================
;; Blast-radius recompute behavior (SPEC-03 §7): claims within 2 hops of
;; edges changed this cycle. v1 recomputes the full labelling (linear, cheap
;; at knowledge-work scale) but WRITES only inside the blast radius — the
;; write set, not the compute, is what taints history.
;; ===========================================================================
(defn- neighborhood-2hop [edges seeds]
  (let [adj (reduce (fn [m {:keys [from to]}]
                      (-> m (update from (fnil conj #{}) to)
                            (update to (fnil conj #{}) from)))
                    {} edges)
        step (fn [s] (into s (mapcat #(get adj % #{})) s))]
    (-> (set seeds) step step)))

(defn recompute-stances!
  "Called by the consolidator after a promotion cycle. changed-node-ids: the
   endpoints of edges promoted/retracted this cycle (empty => full sweep).
   Appends ONE stance.recomputed event with :belief/status flips for nodes
   whose stance changed. Single-writer: consolidator only."
  [log changed-node-ids]
  (binding [m/*log* log]
    (let [db (m/project @log)
          edges (discourse-edges db)
          stances (compute-stances edges)
          scope (if (seq changed-node-ids)
                  (neighborhood-2hop edges changed-node-ids)
                  (set (keys stances)))
          flips (for [[n s] stances
                      :when (contains? scope n)
                      :let [cur (:belief/status (d/entity db [:node/id n]))]
                      :when (not= cur (:status s))]
                  [n (:status s)])]
      (when (seq flips)
        (m/append! {:type :stance.recomputed :actor :belief
                    :tx-data (vec (mapcat
                                   (fn [[n st]]
                                     [[:db/add [:node/id n] :belief/status st]
                                      [:db/add [:node/id n] :belief/computed-at
                                       (str (java.time.Instant/now))]])
                                   flips))}))
      (count flips))))

;; WIRING: in mnemosyne.ingest/run-service!, after consolidate! returns,
;; collect the subjects of promoted edge-type judgments as changed-node-ids
;; and call (belief/recompute-stances! log changed). Schema additions:
;; :belief/status {} :belief/computed-at {} (plain values, no schema needed
;; beyond defaults in DataScript).

(ns mnemosyne.ingest
  "The consolidator service — the single (logical) writer that closes the loop
   between the Python harness and the Mnemosyne substrate.

       outbox.jsonl ──┐
       anchor_outbox ─┼─► ingest! ─► consolidate! ─► promote*! ─► domain facts
                      │                  │
                      │                  ├─► escalations.jsonl  (-> anchor pass)
                      │                  └─► accepted.jsonl     (-> anchor sampling)
                      └─ offsets tracked per file; idempotent re-ingestion

   Design points (see README_service.md):
     - SINGLE-THREADED loop => single writer per subject-key by construction
       (the CALM non-monotone boundary lives entirely in this process).
     - Idempotency: a judgment is skipped if the same (judge, context-hash,
       label) already exists; file offsets survive restarts via *.offset.
     - ANCHOR SUPREMACY: if a live anchor-family verdict exists on a subject,
       it promotes directly — panels arbitrate among peers, not above C.
     - Promotion appends DOMAIN events whose facts carry :prov/from-judgment,
       so cohort retraction keeps working for everything this service asserts.

   deps.edn additions: org.clojure/data.json {:mvn/version \"2.5.0\"}
   Hand-checked against DataScript 1.7.3; not executed in this sandbox."
  (:require [clojure.data.json :as json]
            [clojure.java.io :as io]
            [clojure.string :as str]
            [datascript.core :as d]
            [mnemosyne.core :as m]
            [mnemosyne.judges :as j]
            [mnemosyne.zettel :as z]
            [mnemosyne.belief :as b]
            [mnemosyne.durable :as dur]))

;; B4: register the schema fragments of modules that don't require core (zettel)
;; and belief's stance attrs, so the projection folds their refs correctly.
(m/register-schema! z/zettel-schema)
(m/register-schema! {:belief/status {} :belief/computed-at {}
                     :sim/near {:db/valueType :db.type/ref}
                     :sim/to {:db/valueType :db.type/ref}
                     :derived/from {:db/valueType :db.type/ref}
                     :bridge/a {:db/valueType :db.type/ref}
                     :bridge/b {:db/valueType :db.type/ref}
                     :summary/about {:db/valueType :db.type/ref}
                     :elab/of {:db/valueType :db.type/ref}})

;; ===========================================================================
;; UTF-8-safe incremental tailing with offset files
;; (NB: RandomAccessFile.readLine is byte-latin1 — it garbles accented French;
;;  we read raw bytes and decode UTF-8, consuming only complete lines.)
;; ===========================================================================
(defn read-new-lines!
  "Returns the vector of complete new lines in `path` since the offset stored
   in `path`.offset, and advances the offset. Partial trailing lines are left
   for the next call."
  [path]
  (let [f   (io/file path)
        off-f (io/file (str path ".offset"))
        off (if (.exists off-f) (Long/parseLong (str/trim (slurp off-f))) 0)]
    (if (or (not (.exists f)) (<= (.length f) off))
      []
      (let [buf (byte-array (- (.length f) off))]
        (with-open [raf (java.io.RandomAccessFile. f "r")]
          (.seek raf off) (.readFully raf buf))
        (let [s    (String. buf "UTF-8")
              last-nl (str/last-index-of s "\n")]
          (if (nil? last-nl)
            []
            (let [complete (subs s 0 (inc last-nl))]
              (spit off-f (str (+ off (alength (.getBytes complete "UTF-8")))))
              (vec (remove str/blank? (str/split-lines complete))))))))))

;; ===========================================================================
;; Ingestion (monotone side): outbox events -> judgment facts
;; ===========================================================================
;; ---------------------------------------------------------------------------
;; Type-name boundary: Python uses underscores (edge_type), Clojure keywords
;; use hyphens (:edge-type). Normalize at ingest, denormalize at export —
;; without this, stakes lookups and domain-fact dispatch silently miss.
;; ---------------------------------------------------------------------------
(defn- py->clj-type [s] (keyword (str/replace s "_" "-")))
(defn- clj->py-type [k] (str/replace (name k) "-" "_"))

(defn- ensure-judge!
  "Auto-register an unknown judge id; family comes from the service config map
   {judge-id family-keyword}, defaulting to the id's leading token."
  [db judge-id families]
  (when-not (d/entity db [:judge/id judge-id])
    (m/append! {:type :judge.registered :actor :ingestor
                :tx-data [{:judge/id judge-id
                           :judge/family (get families judge-id
                                              (keyword (first (str/split judge-id #"[-@]"))))}]})))

(defn- already-ingested? [db judge-id ctx-hash label]
  (seq (d/q '[:find ?j :in $ ?gid ?h ?l :where
              [?j :judgment/context-hash ?h]
              [?j :judgment/label ?l]
              [?j :judgment/judge ?g] [?g :judge/id ?gid]]
            db judge-id ctx-hash (keyword label))))

(defn ingest-event! [log families line]
  (binding [m/*log* log]
    (let [ev (json/read-str line)
          db (m/project @log)]
      (case (get ev "event")
        "judgment.emitted"
        (let [gid (ev "judge_id")]
          (ensure-judge! db gid families)
          (when-not (already-ingested? (m/project @log) gid
                                       (ev "context_hash") (ev "label"))
            (j/emit-judgment! {:jtype (py->clj-type (ev "jtype"))
                               :subjects (vec (ev "subjects"))
                               :label (keyword (ev "label"))
                               :conf (ev "confidence")
                               :judge-id gid
                               :cal-version (ev "cal_version")
                               :ctx-hash (ev "context_hash")
                               :caused-by (ev "caused_by")
                               :self-reported? (ev "self_reported")})))
        "judgment.abstained"
        (j/emit-abstention! {:jtype (py->clj-type (ev "jtype"))
                             :subjects (vec (ev "subjects"))
                             :judge-id (ev "judge_id")
                             :ctx-hash (ev "context_hash")
                             :caused-by (ev "caused_by")})
        "anchor.sampled"
        (j/record-anchor-check! (ev "of") (boolean (ev "agrees"))
                                (ev "anchor_judge"))
        nil))))

;; ===========================================================================
;; Domain-fact builders — what promotion ASSERTS, per (type, label).
;; Every builder returns {:fact-map entity-or-nil :extra-tx [..] } so the
;; entity carries :prov/from-judgment (cohort-retractable) while attribute
;; flips ride alongside.
;; ===========================================================================
(defn- discourse-edge [from to label]
  {:node/id (str from "->" to "#" (name label)) :node/type :discourse-edge
   :edge/from [:node/id from] :edge/to [:node/id to] :edge/type label})

(defmulti domain-fact (fn [jtype label _subjects] [jtype label]))
(defmethod domain-fact :default [_ _ _] nil)  ;; unrelated/distinct/absorb/keep/defer

;; edge-type: supports/opposes/refines feed the belief layer; unrelated = no fact
(doseq [l [:supports :opposes :refines]]
  (defmethod domain-fact [:edge-type l] [_ label [ev cl]]
    {:fact-map (discourse-edge ev cl label)}))

;; same-entity: retractable belief edge, canonical order, NEVER a merge
(defmethod domain-fact [:same-entity :same] [_ _ subjects]
  (let [[a b] (sort subjects)]
    {:fact-map (discourse-edge a b :same-as)}))

;; summarize-now
(defmethod domain-fact [:summarize-now :fire] [_ _ [cluster]]
  {:fact-map {:node/id (str "sum-task/" cluster) :node/type :summarize-task
              :task/parent [:node/id cluster] :task/status :open}})
(defmethod domain-fact [:summarize-now :never] [_ _ [cluster]]
  {:fact-map {:node/id (str cluster "/never-sum") :node/type :policy-flag
              :flag/kind :never-summarize :flag/of [:node/id cluster]}})

;; propagate: open a bounded reconsider task on the neighbor
(defmethod domain-fact [:propagate :propagate] [_ _ [chg nb]]
  {:fact-map {:node/id (str chg "->" nb "/reconsider") :node/type :question
              :task/parent [:node/id nb] :task/status :open
              :question/text (str "Reconsider " nb " in light of change at " chg)}})

;; invalidate: stale-mark (prov-linked mark node + the attribute flip)
(defmethod domain-fact [:invalidate :invalidate] [_ _ [derived]]
  {:fact-map {:node/id (str derived "@stale") :node/type :stale-mark
              :flag/of [:node/id derived]}
   :extra-tx [[:db/add [:node/id derived] :derived/stale? true]]})

;; dedup: duplicate-of (canonical order) / subsumes (PRESENTED order — directional)
(defmethod domain-fact [:dedup-prop :duplicate] [_ _ subjects]
  (let [[a b] (sort subjects)] {:fact-map (discourse-edge a b :duplicate-of)}))
(defmethod domain-fact [:dedup-prop :subsumes] [_ _ [a b]]
  {:fact-map (discourse-edge a b :subsumes)})

;; faithful: gate proposition eligibility; failures re-open work (linter pattern)
(defmethod domain-fact [:faithful :faithful] [_ _ [prop _src]]
  {:fact-map {:node/id (str prop "/faith-ok") :node/type :policy-flag
              :flag/kind :faithful :flag/of [:node/id prop]}
   :extra-tx [[:db/add [:node/id prop] :prop/faithful? true]]})
(doseq [l [:lost-qualifier :unsupported]]
  (defmethod domain-fact [:faithful l] [_ label [prop src]]
    {:fact-map {:node/id (str prop "/faith-flag") :node/type :flag
                :flag/kind label :flag/of [:node/id prop]}
     :extra-tx [{:node/id (str prop "/refix") :node/type :question
                 :task/parent [:node/id prop] :task/status :open
                 :question/text (str "Re-propositionize " prop " against " src
                                     " (" (name label) ")")}]}))

;; zettel types (wired from zettel.clj's WIRING NOTES §3). The Python wire names
;; are `continues` / `permanent_worthy`; py->clj-type normalizes the underscore
;; to a hyphen, giving :continues and :permanent-worthy (no `?` — the trailing
;; `?` in zettel.clj's internal set is not part of the wire name). Labels arrive
;; hyphenated (`branches-from`, `new-train`). subjects-vec = [child parent].
(defmethod domain-fact [:continues :continues]      [_ _ s] (z/continues-fact s))
(defmethod domain-fact [:continues :branches-from]  [_ _ s] (z/continues-fact s))
(defmethod domain-fact [:continues :new-train]      [_ _ s] (z/new-train-fact s))
(defmethod domain-fact [:permanent-worthy :promote] [_ _ [p]]
  {:extra-tx [[:db/add [:node/id p] :prop/stratum :permanent]]})

;; ===========================================================================
;; Promotion (the non-monotone gate)
;; ===========================================================================
(defn- promote*!
  "Append the DOMAIN event a promotion licenses. Accepts either key name for the
   asserted fact (`:fact-map` from the domain-fact builders, or `:fact`), links
   it back via :prov/from-judgment, rides `:extra-tx` alongside, and flips the
   contributing judgments to :accepted. Returns the appended event id."
  [{:keys [fact fact-map extra-tx via caused-by]}]
  (let [fact (or fact-map fact)]
    (m/append!
     {:type :judgment.promoted :actor :consolidator :caused-by caused-by
      :tx-data (-> (cond-> []
                     fact (conj (assoc fact :prov/from-judgment
                                       (mapv (fn [jid] [:judgment/id jid]) via))))
                   (into (or extra-tx []))
                   (into (map (fn [jid] [:db/add [:judgment/id jid]
                                         :judgment/status :accepted]) via)))})))

(defn- anchor-verdict
  "If a live anchor-family candidate exists on this subject-key, it wins."
  [db k]
  (first
   (d/q '[:find ?l ?jid ?subs :in $ % ?k :where
          (live-candidate ?j) [?j :judgment/subject-key ?k]
          [?j :judgment/judge ?g] [?g :judge/family :anchor]
          [?j :judgment/label ?l] [?j :judgment/id ?jid]
          [?j :judgment/subjects-vec ?subs]]
        db j/judge-rules k)))

(defn- group-info [db k]
  (first (d/q '[:find ?t ?jid ?subs ?h :in $ % ?k :where
                (live-candidate ?j) [?j :judgment/subject-key ?k]
                [?j :judgment/type ?t] [?j :judgment/id ?jid]
                [?j :judgment/subjects-vec ?subs]
                [?j :judgment/context-hash ?h]]
              db j/judge-rules k)))

(defn consolidate!
  "One promotion pass. Returns
     {:promoted n
      :escalated [rows]
      :promotions [{:jtype .. :label .. :subjects [..] :event-id ..}]}
   where :promotions records each promotion for the writeback-orders /
   task-causes generators and for the belief blast-radius recompute."
  [log]
  (binding [m/*log* log]
    (let [db (m/project @log)
          ;; SORT for deterministic promotion order (golden byte-stability): the
          ;; subject-key is an integer hash; ordering by (context-hash, key) gives
          ;; a stable, reviewable promotion sequence regardless of query set-order.
          ks (->> (d/q '[:find ?k ?h :in $ % :where
                         (live-candidate ?j) [?j :judgment/subject-key ?k]
                         [?j :judgment/context-hash ?h]]
                       db j/judge-rules)
                  (sort-by (juxt second first))
                  (map first)
                  distinct)
          escal (atom []) promoted (atom 0) proms (atom []) quar (atom 0)
          ;; quarantine (PRD §6 case 1): an unknown jtype has no domain-fact
          ;; builder -> never block the writer; record a quarantine event and
          ;; mark the judgment :rejected so it does not re-promote next cycle.
          quarantine!
          (fn [jtype label subjects ctx via]
            (swap! quar inc)
            (m/append! {:type :judgment.quarantined :actor :consolidator
                        :tx-data (into [{:node/id (str "quar/" ctx)
                                         :node/type :quarantine
                                         :quarantine/jtype (clj->py-type jtype)
                                         :quarantine/label (some-> label name)
                                         :quarantine/subjects (vec subjects)}]
                                       (map (fn [jid] [:db/add [:judgment/id jid]
                                                       :judgment/status :rejected])
                                            via))}))
          judge-id-of
          (fn [jid] (some-> (d/entity db [:judgment/id jid])
                            :judgment/judge :judge/id))
          promote-or-quar!
          (fn [jtype label subjects ctx via]
            (let [df (domain-fact jtype label subjects)]
              (if (nil? df)
                (quarantine! jtype label subjects ctx via)
                (let [eid (promote*! (merge df {:via via}))]
                  (swap! promoted inc)
                  (swap! proms conj {:jtype jtype :label label
                                     :subjects (vec subjects) :event-id eid
                                     :ctx ctx :judge-id (judge-id-of (first via))})))))]
      (doseq [k ks]
        (let [[jtype _ subjects ctx] (group-info db k)]
          (if-let [[label jid subs] (anchor-verdict db k)]
            (promote-or-quar! jtype label subs ctx [jid])
            (let [r (j/promotable? db jtype k)]
              (cond
                (:promote r)
                (promote-or-quar! jtype (:promote r) subjects ctx
                                  (mapv #(:judgment/id (d/entity db %)) (:via r)))
                (:escalate r)
                (swap! escal conj {"jtype" (clj->py-type jtype)
                                   "subject_key" k
                                   "subjects" subjects
                                   "context_hash" ctx}))))))
      {:promoted @promoted :escalated @escal :promotions @proms
       :quarantined @quar})))

;; ===========================================================================
;; Exports
;; ===========================================================================
(defn- append-jsonl! [path rows]
  (when (seq rows)
    (with-open [w (io/writer path :append true)]
      (doseq [r rows] (.write w (str (json/write-str r) "\n"))))))

(defn export-accepted!
  "Accepted-but-unexported judgments -> accepted.jsonl (anchor-sampling input;
   Python joins fields by context_hash from contexts.jsonl)."
  [log path]
  (binding [m/*log* log]
    (let [db (m/project @log)
          rows (d/q '[:find ?jid ?t ?l ?h ?gid ?fam :where
                      [?j :judgment/status :accepted]
                      [?j :judgment/id ?jid] [?j :judgment/type ?t]
                      [?j :judgment/label ?l] [?j :judgment/context-hash ?h]
                      [?j :judgment/judge ?g]
                      [?g :judge/id ?gid] [?g :judge/family ?fam]
                      (not-join [?j] [?j :judgment/exported? true])]
                    db)]
      (append-jsonl! path (for [[jid t l h gid fam] rows]
                            {"judgment_id" jid "jtype" (clj->py-type t)
                             "label" (name l) "context_hash" h
                             "judge_id" gid "judge_family" (name fam)}))
      (when (seq rows)
        (m/append! {:type :judgments.exported :actor :ingestor
                    :tx-data (mapv (fn [[jid]] [:db/add [:judgment/id jid]
                                                :judgment/exported? true])
                                   rows)}))
      (count rows))))

(defn export-edges!
  "Promoted-but-unexported discourse edges -> edges.jsonl, the belief layer's
   input (belief.py / belief.clj). Rows: {edge_id, edge_type, from, to}.
   Same exported?-flag pattern as export-accepted!."
  [log path]
  (binding [m/*log* log]
    (let [db (m/project @log)
          rows (sort-by first
                        (d/q '[:find ?id ?t ?fid ?tid :where
                               [?e :node/type :discourse-edge]
                               [?e :node/id ?id] [?e :edge/type ?t]
                               [?e :edge/from ?f] [?f :node/id ?fid]
                               [?e :edge/to ?to] [?to :node/id ?tid]
                               (not-join [?e] [?e :edge/exported? true])]
                             db))]
      (append-jsonl! path (for [[id t fid tid] rows]
                            {"edge_id" id "edge_type" (name t)
                             "from" fid "to" tid}))
      (when (seq rows)
        (m/append! {:type :edges.exported :actor :ingestor
                    :tx-data (mapv (fn [[id]] [:db/add [:node/id id]
                                               :edge/exported? true])
                                   rows)}))
      (count rows))))

;; ===========================================================================
;; export-jsonld! (contract FR-4 / CROSSWALK S1–S8) — materialize the classes
;; the SHACL shapes target, in EXPANDED JSON-LD (see shacl_lint.py::N and the
;; sN_ok.jsonld fixtures). focusNode = urn:mnemo:node:<uid>, ns
;; https://mnemosyne.dev/ns#. Consumed by `shacl_lint.py lint --data`.
;; ===========================================================================
(def ^:private MNEMO "https://mnemosyne.dev/ns#")
(defn- urn [uid] (str "urn:mnemo:node:" uid))
(defn- lit [v] {"@value" v})
(defn- ref [uid] {"@id" (urn uid)})

(defn- jsonld-node
  "Build one expanded JSON-LD node. `types` are bare class names; `props` is a
   map of bare-prop-name -> vector of value objects ({\"@value\" ..}|{\"@id\" ..})."
  [uid types props]
  (into {"@id" (urn uid) "@type" (mapv #(str MNEMO %) types)}
        (map (fn [[k vs]] [(str MNEMO k) vs]) props)))

(defn export-jsonld!
  "Materialize the promoted-fact classes the linter needs and write EXPANDED
   JSON-LD to `path` (an array, sorted by @id). Classes (CROSSWALK):
     ProcessingActivity, Claim, DiscourseEdge, PermanentNote, StaleDerived,
     RegisterKeyword, Judgment, Proposition, Stance, Task.
   S1/S2 can also be produced by shacl_lint.py's --roam exporter (Roam-only
   view); THIS exporter is required for S3/S5/S6/S7 (promoted strata, judgments,
   stances, stale-marks) which the Roam view cannot see — see README_cycle.md."
  [log path]
  (binding [m/*log* log]
    (let [db (m/project @log)
          nodes (atom [])
          add! (fn [n] (swap! nodes conj n))]
      ;; --- ProcessingActivity (S1) ---
      (doseq [[uid basis] (d/q '[:find ?id ?lb :where
                                 [?a :node/type :processing-activity] [?a :node/id ?id]
                                 [(get-else $ ?a :legal-basis "") ?lb]] db)]
        (add! (jsonld-node uid ["ProcessingActivity"]
                           (if (str/blank? basis) {} {"legalBasis" [(lit basis)]}))))
      ;; --- Claim (S2) ---
      (doseq [[uid txt] (d/q '[:find ?id ?t :where
                               [?c :node/type :claim] [?c :node/id ?id]
                               [(get-else $ ?c :claim/text "") ?t]] db)]
        (add! (jsonld-node uid ["Claim"] (if (str/blank? txt) {} {"text" [(lit txt)]}))))
      ;; --- DiscourseEdge (S2 supports/opposes; feeds inverse-path shapes) ---
      (doseq [[uid t fid tid] (d/q '[:find ?id ?t ?fid ?tid :where
                                     [?e :node/type :discourse-edge]
                                     [?e :node/id ?id] [?e :edge/type ?t]
                                     [?e :edge/from ?f] [?f :node/id ?fid]
                                     [?e :edge/to ?to] [?to :node/id ?tid]] db)]
        (add! (jsonld-node uid ["DiscourseEdge"]
                           {"from" [(ref fid)] "to" [(ref tid)]
                            "edgeType" [(lit (name t))]})))
      ;; --- PermanentNote + Proposition (S3 orphan, S6 stance-leak, S8 gate) ---
      (doseq [[uid faith? cont train? kind]
              (d/q '[:find ?id ?fa ?cont ?th ?kind :where
                     [?p :prop/stratum :permanent] [?p :node/id ?id]
                     [(get-else $ ?p :prop/faithful? false) ?fa]
                     [(get-else $ ?p :zettel/continues :none) ?cont]
                     [(get-else $ ?p :zettel/train :none) ?th]
                     [(get-else $ ?p :prop/kind :none) ?kind]] db)]
        (let [props (cond-> {"faithful" [(lit (boolean faith?))]}
                      (not= cont :none)
                      (assoc "continues" [(ref (:node/id (d/entity db cont)))])
                      (and (= cont :none) (not= train? :none))
                      (assoc "trainHead" [(lit true)])
                      (not= kind :none)
                      (assoc "kind" [(lit (name kind))]))]
          (add! (jsonld-node uid ["PermanentNote" "Proposition"] props))))
      ;; --- bare Proposition (S6: permanent-kind proposition a stance rests on) ---
      (doseq [[uid kind] (d/q '[:find ?id ?k :where
                                [?p :node/type :proposition] [?p :node/id ?id]
                                [(get-else $ ?p :prop/kind :none) ?k]
                                (not [?p :prop/stratum :permanent])] db)]
        (add! (jsonld-node uid ["Proposition"]
                           (if (= kind :none) {} {"kind" [(lit (name kind))]}))))
      ;; --- Stance (S6: basis must reach a permanent-kind proposition) ---
      (doseq [[uid basis] (d/q '[:find ?id ?bid :where
                                 [?s :node/type :stance] [?s :node/id ?id]
                                 [?s :stance/basis ?b] [?b :node/id ?bid]] db)]
        (add! (jsonld-node uid ["Stance"] {"basis" [(ref basis)]})))
      ;; --- StaleDerived (S7) ---
      (doseq [[uid] (d/q '[:find ?id :where
                           [?d :derived/stale? true] [?d :node/id ?id]] db)]
        (add! (jsonld-node uid ["StaleDerived"] {"stale" [(lit true)]})))
      ;; --- Task (S7: open task on a stale node clears the warning) ---
      (doseq [[uid parent status]
              (d/q '[:find ?id ?pid ?st :where
                     [?t :node/type :question] [?t :node/id ?id]
                     [?t :task/parent ?p] [?p :node/id ?pid]
                     [(get-else $ ?t :task/status :open) ?st]] db)]
        (add! (jsonld-node uid ["Task"]
                           {"parent" [(ref parent)] "status" [(lit (name status))]})))
      ;; --- RegisterKeyword (S4 cap) ---
      (doseq [kw (d/q '[:find [?kw ...] :where [?e :register/keyword ?kw]] db)]
        (let [entries (d/q '[:find [?eid ...] :in $ ?kw :where
                             [?e :register/keyword ?kw] [?e :register/entry ?n]
                             [?n :node/id ?eid]] db kw)]
          (add! (jsonld-node (str "kw:" kw) ["RegisterKeyword"]
                             {"keyword" [(lit kw)]
                              "entry" (mapv ref (sort entries))}))))
      ;; --- Judgment (S5 envelope) ---
      (doseq [[uid gid h cal l]
              (d/q '[:find ?id ?gid ?h ?cal ?l :where
                     [?j :judgment/id ?id] [?j :judgment/context-hash ?h]
                     [?j :judgment/label ?l] [?j :judgment/cal-version ?cal]
                     [?j :judgment/judge ?g] [?g :judge/id ?gid]] db)]
        (add! (jsonld-node uid ["Judgment"]
                           {"judge" [(lit gid)] "contextHash" [(lit h)]
                            "calVersion" [(lit cal)] "label" [(lit (name l))]})))
      (let [sorted (sort-by #(get % "@id") @nodes)]
        (with-open [w (io/writer path)]
          (.write w (json/write-str (vec sorted) :escape-unicode false))))
      (count @nodes))))

;; ===========================================================================
;; task_causes.jsonl (§2.4) — one line per cause for task_gen.py.
;; contradiction: a claim with an inbound opposes edge; triage.due: a fleeting
;; note with a decayed activation and an open triage task; bridge: a proposed
;; bridge question. Each line carries the source event_id.
;; ===========================================================================
(defn- causes-rows [db promotions]
  (let [prom-eid (into {} (map (juxt (comp vec :subjects) :event-id)) promotions)
        contradictions
        (for [[to from] (d/q '[:find ?tid ?fid :where
                               [?e :node/type :discourse-edge] [?e :edge/type :opposes]
                               [?e :edge/from ?f] [?f :node/id ?fid]
                               [?e :edge/to ?t] [?t :node/id ?tid]] db)]
          {"cause" "contradiction" "claim" to "opposer" from
           ;; content-addressed fallback: caused_by must stay traceable (I4)
           ;; and unique per cause, never a shared constant.
           "event_id" (get prom-eid [from to]
                           (dur/sha256 (str "cause:contradiction|" from "|" to)))})
        bridges
        (for [[a b] (d/q '[:find ?aid ?bid :where
                           [?q :node/type :question] [?q :bridge/a ?ba] [?ba :node/id ?aid]
                           [?q :bridge/b ?bb] [?bb :node/id ?bid]] db)]
          {"cause" "bridge" "a" a "b" b "score" 1.0
           "event_id" (dur/sha256 (str "cause:bridge|" a "|" b))})
        triage
        (for [[uid act] (d/q '[:find ?id ?a :where
                               [?p :prop/stratum :fleeting] [?p :node/id ?id]
                               [(get-else $ ?p :prop/activation 1.0) ?a]] db)
              :when (< act 1.0)]
          {"cause" "triage.due" "uid" uid "activation" act
           "event_id" (dur/sha256 (str "cause:triage|" uid))})]
    (concat contradictions triage bridges)))

;; ===========================================================================
;; writeback_orders.jsonl (§2.3) — producer of the B2 FR-1 contract.
;; Emission order: promotions -> lint flags -> stance-diffs -> (tasks appended
;; by task_gen.py, not us) -> digest (last line). idempotency_key = source
;; event_id (PRD FR-2).
;; ===========================================================================
;; Field names follow roam_writeback.py's renderers EXACTLY (render_judgment /
;; render_flag / render_stance / render_digest); templates are `*_v1`; every
;; target page is under `M/` (B2's allowlist).
(defn- promotion-order [{:keys [jtype label subjects event-id ctx judge-id]}]
  (let [[src dst] subjects]
    {"kind" "judgment" "idempotency_key" event-id
     "target" {"page" "M/Judgments" "under" (clj->py-type jtype)}
     "content" {"template" "judgment_v1"
                "fields" {"jtype" (clj->py-type jtype) "label" (name label)
                          "src_uid" src "dst_uid" dst
                          "ctx" ctx "judge_id" judge-id}}
     "caused_by" event-id}))

(defn- lint-orders [lint-json-path]
  (when (.exists (io/file lint-json-path))
    (let [rep (json/read-str (slurp lint-json-path))]
      (for [r (get rep "results" [])
            :let [fnode (get r "focusNode") shape (get r "shape")]]
        {"kind" "flag" "idempotency_key" (dur/sha256 (str "flag" fnode shape))
         "target" {"page" "M/Flags" "under" (get r "severity")}
         "content" {"template" "flag_v1"
                    "fields" {"focus_uid" fnode "shape_id" shape
                              "shape_name" shape "severity" (get r "severity")
                              "message" (get r "message")}}
         "caused_by" fnode}))))

(defn- stance-diff-orders [stance-diff-path]
  (when (.exists (io/file stance-diff-path))
    (for [line (remove str/blank? (str/split-lines (slurp stance-diff-path)))
          :let [d (json/read-str line)]]
      {"kind" "stance" "idempotency_key" (dur/sha256 (str "stance" (get d "node")
                                                          (get d "new_status")))
       "target" {"page" "M/Stances" "under" (get d "node")}
       "content" {"template" "stance_v1"
                  "fields" {"node_uid" (get d "node")
                            "old_status" (get d "old_status")
                            "new_status" (get d "new_status")}}
       "caused_by" (get d "caused_by" (get d "node"))})))

(defn- digest-order [counters]
  {"kind" "digest" "idempotency_key" (dur/sha256 (str "digest" (:cycle counters)))
   "target" {"page" "M/Digest" "under" (str (:cycle counters))}
   "content" {"template" "digest_v1"
              "fields" (into {} (map (fn [[k v]] [(name k) v]) counters))}
   "caused_by" (str (:cycle counters))})

(defn write-orders!
  "Emit writeback_orders.jsonl in contract order: promotions -> flags ->
   stance-diffs. task_gen.py then appends its task orders via --out-append
   (stage 8), so the consolidator does NOT write the tail digest here — the
   digest must count task_gen's rows too and is therefore emitted last, after
   stage 8, by passing non-empty `:counters` (used by an explicit final-digest
   call). With empty counters (the per-cycle default) no digest row is written."
  [path {:keys [promotions lint-json stance-diff counters]}]
  (append-jsonl! path (map promotion-order promotions))
  (append-jsonl! path (lint-orders lint-json))
  (append-jsonl! path (stance-diff-orders stance-diff))
  (when (seq counters)
    (append-jsonl! path [(digest-order counters)])))

;; ===========================================================================
;; Human routing (§2.5) — new offset-based reader for outbox_human.jsonl.
;; Dispatch by task_type:
;;   review    -> EXPORT a calset row to review_resolved.jsonl (NOT a domain
;;                effect — CALM split: the merge is done by Python later).
;;   elaborate -> append! a :source/family :human candidate permanent prop.
;;   triage    -> stratum promotion of the target.
;;   bridge    -> candidate edge between the two nodes.
;;   .ambiguous/.amended -> journalled event, no domain effect.
;; ===========================================================================
(defn- unroutable!
  "The event arrived without the routing payload it needs — journal it (so
   the digest can re-signal) rather than fabricating a wrong domain fact."
  [tid ttype reason]
  (m/append! {:type :human.response.unroutable :actor :human
              :tx-data [{:node/id (str "human/" tid) :node/type :human-note
                         :human/task-type (or ttype "?")
                         :human/reason reason}]}))

(defn route-human! [log review-resolved-path line]
  (binding [m/*log* log]
    (let [ev (json/read-str line)
          event (get ev "event")
          ttype (get ev "task_type")
          tid   (get ev "task_id")
          ;; `route` is the taskgen-ledger payload joined in by task_harvest
          ;; (B3<->B4 seam): review -> {jtype fields}, triage -> {uid},
          ;; bridge -> {a b}. Harvest-side refs:: fallback fills triage/bridge
          ;; when the ledger is missing; review is unroutable without it.
          route (get ev "route" {})]
      (cond
        (or (= event "human.response.ambiguous") (= event "human.response.amended"))
        (m/append! {:type (keyword (str/replace event "." "-")) :actor :human
                    :tx-data [{:node/id (str "human/" tid) :node/type :human-note
                               :human/event event}]})

        (= ttype "review")
        ;; EXPORT ONLY — CALM split: this is a file write, not a promotion.
        (let [jtype (get route "jtype")]
          (if (nil? jtype)
            (unroutable! tid ttype "review without route.jtype/fields")
            (append-jsonl! review-resolved-path
                           [{"jtype" jtype
                             "fields" (get route "fields" {})
                             "gold" (get ev "choice" (get ev "response_text"))}])))

        (= ttype "elaborate")
        (m/append! {:type :human.elaborated :actor :human
                    :tx-data [{:node/id (str "human/" tid) :node/type :proposition
                               :prop/stratum :candidate :prop/kind :permanent
                               :source/family :human
                               :prop/text (get ev "response_text" "")}]})

        (= ttype "triage")
        (let [uid (get route "uid")]
          (cond
            (nil? uid)
            (unroutable! tid ttype "triage without route.uid")
            ;; only the explicit promote tag changes stratum (PRD B3 FR-3);
            ;; other choices are journalled, no domain effect in v0.
            (= (get ev "choice") "promouvoir")
            (m/append! {:type :human.triaged :actor :human
                        :tx-data [[:db/add [:node/id uid]
                                   :prop/stratum :candidate]]})
            :else
            (m/append! {:type :human.triaged :actor :human
                        :tx-data [{:node/id (str "human/" tid)
                                   :node/type :human-note
                                   :human/event (str "triage:" (get ev "choice"))}]})))

        (= ttype "bridge")
        (let [a (get route "a") b (get route "b")]
          (if (or (nil? a) (nil? b))
            (unroutable! tid ttype "bridge without route.a/route.b")
            (m/append! {:type :human.bridged :actor :human
                        :tx-data [{:node/id (str "bridge/" a "+" b) :node/type :discourse-edge
                                   :edge/from [:node/id a] :edge/to [:node/id b]
                                   :edge/type :bridge}]})))
        :else nil))))

;; ===========================================================================
;; Durable boot + write-ahead installation
;; ===========================================================================
(defn boot!
  "Rebuild the in-memory log from store/events.jsonl, verify the boot hash, and
   return {:log atom :seq atom :journal path}. Installs nothing yet — the caller
   binds *wal-fn* around the working section."
  [journal-path]
  (let [{:keys [rows log seq]} (dur/boot-log journal-path)
        db (dur/fold-journal (m/full-schema) rows)]
    (dur/verify-boot-hash! db rows)
    (m/reset-counter!)
    ;; re-seed the evt-NNNN counter so new ids continue the sequence
    (dotimes [_ (count log)] (#'m/next-id))
    {:log (atom (vec log)) :seq (atom seq) :journal journal-path}))

(defn with-wal
  "Run `f` with *wal-fn* installed so every core/append! write-aheads the record
   to the journal and bumps the shared seq. `crash-after` (test hook) aborts the
   process AFTER the Nth write-ahead but BEFORE the caller's in-memory swap —
   exercising the crash-recovery invariant."
  [{:keys [journal seq]} crash-after f]
  (let [written (atom 0)]
    (binding [m/*wal-fn*
              (fn [record]
                (dur/append-record! journal record (swap! seq inc))
                (let [n (swap! written inc)]
                  (when (and crash-after (= n crash-after))
                    (binding [*out* *err*]
                      (println "CRASH-TEST: exiting after WAL #" n "(before in-memory swap)"))
                    (System/exit 42))))]
      (f))))

;; ===========================================================================
;; One cycle (--once) — the consolidator's single-shot mode used by cycle.sh
;; stage 5. Single-shot, no interval, no daemon loop. (JSON-LD export is a
;; SEPARATE invocation, --export-jsonld, driven by cycle.sh stage 7.)
;; ===========================================================================
(defn run-once!
  "opts: {:dir \"ops\" :cycle \"$C\" :families {} :crash-after N? :store \"store\"}
   Boots durably from <store>/events.jsonl, ingests the outboxes + human outbox,
   consolidates, runs batch behaviors, recomputes stances, exports
   accepted/edges, emits task_causes + writeback_orders, and journals the
   end-of-cycle state hash."
  [{:keys [dir cycle families crash-after store] :or {families {} store "store"}}]
  (let [dp     (fn [f] (str dir "/" f))
        cp     (fn [f] (str cycle "/" f))
        _      (.mkdirs (io/file store))
        _      (.mkdirs (io/file cycle))
        jpath  (str store "/events.jsonl")
        {:keys [log seq] :as st} (boot! jpath)]
    (with-wal st crash-after
      (fn []
        ;; --- ingest monotone side (outbox + anchor_outbox) ---
        (doseq [line (concat (read-new-lines! (dp "outbox.jsonl"))
                             (read-new-lines! (dp "anchor_outbox.jsonl")))]
          (try (ingest-event! log families line)
               (catch Exception e
                 (binding [*out* *err*]
                   (println "ingest error:" (.getMessage e) "line:" line)))))
        ;; --- human routing (offset reader on outbox_human.jsonl) ---
        (doseq [line (read-new-lines! (dp "outbox_human.jsonl"))]
          (try (route-human! log (dp "review_resolved.jsonl") line)
               (catch Exception e
                 (binding [*out* *err*]
                   (println "human-route error:" (.getMessage e) "line:" line)))))
        ;; --- consolidate (non-monotone promotion gate) ---
        (let [{:keys [promoted escalated promotions]} (consolidate! log)
              changed (into #{} (mapcat :subjects) promotions)]
          (append-jsonl! (dp "escalations.jsonl") escalated)
          ;; --- batch behaviors (§5 Q3): drift-quarantine + zettel daily/register/dialog ---
          (binding [m/*log* log]
            (m/run-to-fixpoint
             log [(j/quarantine-behavior {})
                  (z/daily-inbox-behavior {})
                  (z/register-consolidation-behavior)
                  (z/morning-dialog-behavior {})]
             {:max-steps 50}))
          ;; --- belief blast-radius recompute (consolidator-side mirror) ---
          (b/recompute-stances! log (vec changed))
          ;; --- exports ---
          (let [db       (m/project @log)
                exported (export-accepted! log (dp "accepted.jsonl"))
                nedges   (export-edges!    log (dp "edges.jsonl"))
                ncauses  (do (append-jsonl! (cp "task_causes.jsonl")
                                            (causes-rows db promotions))
                             (count promotions))
                ;; E5 dependency (ANNEX B7 §1): one row per train, consumed by
                ;; eval_harness --elaboration. Query lives in zettel.clj.
                _cov     (append-jsonl!
                          (cp "elaboration_coverage.jsonl")
                          (for [{:keys [train human total coverage]}
                                (z/elaboration-coverage db)]
                            {"train" (str train) "human" human
                             "total" total "coverage" coverage}))]
            ;; --- writeback orders (promotions -> flags -> stances) ---
            (write-orders! (cp "writeback_orders.jsonl")
                           {:promotions promotions
                            :lint-json (cp "lint.json")
                            :stance-diff (cp "stance_diff.jsonl")
                            :counters {}})
            ;; --- end-of-cycle state hash marker ---
            (dur/journal-state-hash! jpath (swap! seq inc) db)
            (println (format "cycle %s: promoted=%d escalated=%d exported=%d edges=%d causes=%d log=%d"
                             cycle promoted (count escalated) exported nedges ncauses (count @log)))
            {:promoted promoted :escalated (count escalated) :exported exported}))))))

(defn run-once-in!
  "Explicit-path variant used by the test-runner: durable store lives under
   `dir/store`, cycle artifacts under `cdir`. Same body as run-once!, but no
   store-in-CWD assumption — keeps golden tests hermetic per temp dir."
  [dir cdir opts]
  (run-once! (merge {:dir dir :cycle cdir :store (str dir "/store")} opts)))

;; ===========================================================================
;; CLI (cycle.sh stage 5: clojure -M:consolidate --once --dir ops --cycle $C;
;;      stage 7: clojure -M:consolidate --export-jsonld $C/graph.jsonld)
;; ===========================================================================
(defn- parse-args [args]
  (loop [a args, m {}]
    (if (empty? a)
      m
      (case (first a)
        "--once"          (recur (rest a) (assoc m :once true))
        "--dir"           (recur (drop 2 a) (assoc m :dir (second a)))
        "--cycle"         (recur (drop 2 a) (assoc m :cycle (second a)))
        "--export-jsonld" (recur (drop 2 a) (assoc m :export-jsonld (second a)))
        "--crash-after-wal" (recur (drop 2 a) (assoc m :crash-after (Long/parseLong (second a))))
        (recur (rest a) m)))))

(defn -main [& args]
  (let [{:keys [once dir cycle export-jsonld crash-after]} (parse-args args)
        dir (or dir "ops")]
    (cond
      export-jsonld
      (let [{:keys [log]} (boot! "store/events.jsonl")]
        (println "export-jsonld:" (export-jsonld! log export-jsonld) "nodes ->" export-jsonld))

      once
      (run-once! {:dir dir :cycle (or cycle (str dir "/cycles/adhoc"))
                  :crash-after crash-after})

      :else
      (run-once! {:dir dir :cycle (str dir "/cycles/adhoc")}))))

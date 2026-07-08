(ns mnemosyne.durable
  "B4 durability layer — the event journal that makes `now = fold(log)` real
   across process restarts.

   The doctrine (PRD B4 FR-1): every domain event the consolidator emits is
   WRITTEN AHEAD to `store/events.jsonl` as canonical JSON BEFORE it is
   transacted into the in-memory DataScript projection. On boot we fold the
   journal back into a db-value; a structural `state-hash` is journalled every
   100 events and at end of cycle, and re-checked against a fresh refold.

   Persistence format (one JSON object per line, INTERFACES.md §2):
     {\"event_id\":\"sha256:…\",\"seq\":412,\"type\":\"judgment.emitted\",
      \"actor\":\"ingestor\",\"caused_by\":\"sha256:…\"|null,
      \"ts\":\"2026-07-04T02:10:00Z\",\"tx_data\":\"<edn-string>\"}

   Why `tx_data` is an EDN string, not nested JSON: the DataScript transaction
   payload contains keywords, lookup refs (`[:node/id \"x\"]`) and `[:db/add …]`
   vectors that have no faithful, lossless JSON encoding. Storing the canonical
   EDN string (via `pr-str` with `*print-length*`/`*print-level*` nil) makes the
   refold BYTE-EXACT and keeps the outer object a clean, sorted-key JSON row for
   `eval`/`audit` consumers. This is a deliberate, documented choice.

   `event_id = sha256(canonical-JSON-of-the-row WITHOUT event_id)` — the row is
   content-addressed, so a full replay of the same outbox yields the same ids
   (idempotence, M2).

   Hand-checked for DataScript 1.7.3 + data.json 2.5.0; reviewed-not-executed in
   the authoring sandbox (no JVM/Clojars). The committed golden fixtures under
   fixtures/consolidator/ + the GitHub Actions job are the executable gate."
  (:require [clojure.data.json :as json]
            [clojure.edn :as edn]
            [clojure.java.io :as io]
            [clojure.string :as str]
            [datascript.core :as d]
            [mnemosyne.core :as m])
  (:import [java.security MessageDigest]
           [java.text Normalizer Normalizer$Form]))

;; ===========================================================================
;; Clock seam — single source of truth is core/*now-fn* (tests rebind that);
;; we read through it so journal `ts` and in-memory `:event/ts` never diverge.
;; ===========================================================================
(defn now [] (m/*now-fn*))

;; ===========================================================================
;; UTF-8 NFC + sha256
;; ===========================================================================
(defn nfc
  "Unicode NFC normalization — accented French (é, à, ç, œ) must serialize to a
   single canonical byte sequence, or two runs of the 'same' string would hash
   differently. Tested on accented French in test-runner."
  [^String s]
  (Normalizer/normalize s Normalizer$Form/NFC))

(defn sha256-hex [^String s]
  (let [md (MessageDigest/getInstance "SHA-256")
        bs (.digest md (.getBytes (nfc s) "UTF-8"))]
    (apply str (map #(format "%02x" (bit-and % 0xff)) bs))))

(defn sha256 [^String s] (str "sha256:" (sha256-hex s)))

;; ===========================================================================
;; Canonical JSON — sorted keys, compact separators, NFC strings
;; ===========================================================================
(defn- canon
  "Recursively canonicalize a value for stable serialization: maps become
   sorted-key ordered maps, strings are NFC-normalized. data.json emits compact
   separators by default (no spaces)."
  [v]
  (cond
    (map? v)    (into (sorted-map)
                      (map (fn [[k val]] [(if (keyword? k) (name k) (str k))
                                          (canon val)]))
                      v)
    (sequential? v) (mapv canon v)
    (string? v) (nfc v)
    :else v))

(defn canonical-json
  "Deterministic JSON: sorted keys (all the way down), compact separators,
   NFC-normalized strings. `data.json/write-str` writes no inter-token spaces,
   so separators are already compact; we only enforce key order + NFC."
  [m]
  (json/write-str (canon m) :escape-unicode false))

;; ===========================================================================
;; Event id (content addressing)
;; ===========================================================================
(defn event-id
  "sha256 of the canonical JSON of the row WITHOUT the event_id field."
  [row]
  (sha256 (canonical-json (dissoc row "event_id"))))

;; ===========================================================================
;; State hash — structural fingerprint of a db value
;; ===========================================================================
(defn state-hash
  "sha256 of the sorted EAV datom serialization. Two db values with the same
   datoms (regardless of internal entity-id assignment order) MUST hash equal,
   so we serialize [attr, id-of(e), value] with entity identity resolved to the
   stable :node/id / :judgment/id / :judge/id / :event/id where available, and
   fall back to the raw eid otherwise (transient nodes without a stable id do
   not cross projections and are compared by eid within one refold)."
  [db]
  (let [stable (fn [eid]
                 (let [e (d/entity db eid)]
                   (or (:node/id e) (:judgment/id e) (:judge/id e)
                       (:event/id e) (:register/keyword e)
                       (str "eid:" eid))))
        ;; ONLY values of ref-typed attributes are entity ids — probing every
        ;; integer with d/entity throws on plain integer values (e.g. the
        ;; negative :judgment/subject-key hashes: entid rejects them).
        schema (:schema db)
        ref?   (fn [a] (= :db.type/ref (get-in schema [a :db/valueType])))
        rows (->> (d/datoms db :eavt)
                  (map (fn [[e a v _tx]]
                         ;; resolve ref values (numeric eids) to their stable id
                         ;; so the hash is invariant to entity-id assignment order
                         [(name a) (stable e)
                          (if (and (ref? a) (integer? v))
                            (stable v)
                            (str v))]))
                  sort
                  (map (fn [[a e v]] (str a "\t" e "\t" v)))
                  (str/join "\n"))]
    (sha256 rows)))

;; ===========================================================================
;; The journal (write-ahead)
;; ===========================================================================
(defn read-journal
  "Read every complete event row from `path`. Tolerates ONE trailing truncated
   line (a crash between bytes): it is dropped with a noisy stderr warning
   (PRD §6 case 4). Any earlier malformed line is a fatal error."
  [path]
  (let [f (io/file path)]
    (if-not (.exists f)
      []
      (let [lines (with-open [r (io/reader f :encoding "UTF-8")]
                    (doall (line-seq r)))
            n     (count lines)]
        (vec
         (keep-indexed
          (fn [i line]
            (cond
              (str/blank? line) nil
              :else
              (try (json/read-str line)
                   (catch Exception e
                     (if (= i (dec n))
                       (do (binding [*out* *err*]
                             (println "WARN durable: dropping truncated final journal line"
                                      (.getMessage e)))
                           nil)
                       (throw (ex-info "corrupt journal line (not the last)"
                                       {:index i :line line} e)))))))
          lines))))))

(defn last-seq
  "Highest `seq` in the journal rows, or 0 if empty."
  [rows]
  (reduce (fn [m r] (max m (long (get r "seq" 0)))) 0 rows))

;; The in-memory event record produced by core/append! looks like:
;;   {:event/id "evt-0001" :event/type :judgment.emitted :event/actor :ingestor
;;    :event/caused-by "sha256:…" | nil :event/ts "…"
;;    :event/tx-data [ {…} [:db/add …] … ]}
;; A persisted row is the same content re-keyed to the on-disk snake_case schema
;; with tx_data as a canonical EDN string and a content-addressed event_id.

(defn record->row
  "In-memory `:event/*` record + `seq` → the on-disk JSON row (INTERFACES §2)."
  [record seq]
  (let [row {"seq"       seq
             "type"      (name (:event/type record))
             "actor"     (name (:event/actor record))
             "caused_by" (:event/caused-by record)
             "ts"        (:event/ts record)
             "tx_data"   (binding [*print-length* nil *print-level* nil]
                           (pr-str (:event/tx-data record)))}]
    (assoc row "event_id" (event-id row))))

(defn append-record!
  "Write-ahead one fully-stamped in-memory record to `journal-path` as a
   canonical JSON row. Called from the *wal-fn* hook BEFORE the in-memory swap
   (WAL order: disk first). Returns the persisted row."
  [journal-path record seq]
  (let [row (record->row record seq)]
    (with-open [w (io/writer journal-path :append true)]
      (.write w (canonical-json row))
      (.write w "\n")
      (.flush w))
    row))

(defn journal-state-hash!
  "Append a `state.hash` marker row (every 100 events + end of cycle). Not a
   domain event — carries no tx_data — so refold ignores it."
  [journal-path seq db]
  (let [row {"seq" seq "type" "state.hash" "actor" "durable"
             "caused_by" nil "ts" (now)
             "state_hash" (state-hash db)}
        row (assoc row "event_id" (event-id row))]
    (with-open [w (io/writer journal-path :append true)]
      (.write w (canonical-json row)) (.write w "\n") (.flush w))
    row))

;; ===========================================================================
;; Boot: reconstruct the in-memory log (and thus the db) from the journal
;; ===========================================================================
(defn domain-row? [row] (contains? row "tx_data"))

(defn row->record
  "Persisted row → the in-memory `:event/*` record shape core/project folds."
  [row]
  {:event/id        (get-in (edn/read-string {:readers *data-readers*} (get row "tx_data")) [0 :event/id])
   :event/type      (keyword (get row "type"))
   :event/actor     (keyword (get row "actor"))
   :event/caused-by (get row "caused_by")
   :event/ts        (get row "ts")
   :event/tx-data   (edn/read-string {:readers *data-readers*} (get row "tx_data"))})

(defn fold-journal
  "Rebuild a db VALUE by folding every domain row (`state.hash` markers skipped)
   in `seq` order into an empty db of `schema`. This IS core/project over the
   persisted log — the property M1 (`now = fold(log)`)."
  [schema rows]
  (reduce (fn [db row]
            (if (domain-row? row)
              (d/db-with db (edn/read-string {:readers *data-readers*} (get row "tx_data")))
              db))
          (d/empty-db schema)
          (sort-by #(get % "seq") rows)))

(defn boot-log
  "Read the journal and rebuild the in-memory `*log*` vector of records (domain
   rows only, in seq order). Returns {:log [records…] :seq highest-seq}."
  [journal-path]
  (let [rows (read-journal journal-path)
        recs (->> rows
                  (filter domain-row?)
                  (sort-by #(get % "seq"))
                  (mapv row->record))]
    {:rows rows :log recs :seq (last-seq rows)}))

(defn verify-boot-hash!
  "PRD FR-1: after fold, recompute the structural hash and compare against the
   last `state.hash` marker in the journal. Divergence = loud fatal error.
   Returns the recomputed hash (or nil if no marker journalled yet)."
  [db rows]
  (when-let [marker (->> rows
                         (filter #(= "state.hash" (get % "type")))
                         (sort-by #(get % "seq"))
                         last)]
    (let [want (get marker "state_hash")
          got  (state-hash db)]
      (when (not= want got)
        (throw (ex-info "FATAL: refold state-hash mismatch — journal corrupt"
                        {:want want :got got})))
      got)))

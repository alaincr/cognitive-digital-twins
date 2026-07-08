(ns mnemosyne.rules
  "L3 Datalog rule sets for the Mnemosyne stack.

   Written in DataScript rule syntax (the engine under Roam). The same rules port
   to Datomic / Datahike / XTDB Datalog with essentially no change.

   Three families, and they are the whole reason L3 exists: each is *recursive
   Datalog*, the one capability the agentic layers above cannot get for free.
   L3 supplies it with least-fixpoint termination guarantees, so L1/L2 never have
   to reimplement traversal, dedup, or termination (Theme 1).

     1. recursion-tree  -> meta-control over the RLM sub-call tree   (Theme 5d)
     2. linter          -> generate/check/repair as a fixpoint        (Theme 3 / 5a)
     3. provenance       -> lineage as a recursive query, RGPD-grade   (Theme 5b)

   MONOTONICITY NOTE (Theme 5f / CALM): every rule below whose body is purely
   positive is monotone -> it has a coordination-free distributed implementation
   (run it across your Hermes nodes; it converges regardless of interleaving).
   The places that use `not-join` (the linter, the `frontier`) are NON-monotone
   and belong in a higher stratum behind a coordination point. The split is
   marked inline.")

;; ===========================================================================
;; 1. RECURSION-TREE META-CONTROL
;;    The RLM sub-call tree is reified as facts (:task/parent, :task/status,
;;    :task/depth). Steering the recursion is then a QUERY, not imperative
;;    control flow in the REPL -- this is precisely how the harness shrinks.
;; ===========================================================================
(def recursion-tree
  '[;; --- MONOTONE CORE -----------------------------------------------------
    ;; transitive closure of the task tree: the canonical recursive Datalog rule.
    ;; Two clauses give unbounded depth; the engine handles iteration + dedup +
    ;; termination. This single rule is the entire argument of Theme 1.
    [(descendant ?root ?d)
     [?d :task/parent ?root]]
    [(descendant ?root ?d)
     [?mid :task/parent ?root]
     (descendant ?mid ?d)]

    ;; an open task = a unit of work still to be done (a recursion leaf to expand)
    [(open ?t)
     [?t :task/status :open]]

    ;; a subtree is unresolved if it -- or any descendant -- is still open.
    [(unresolved ?root)
     (open ?root)]
    [(unresolved ?root)
     (descendant ?root ?d)
     (open ?d)]

    ;; --- NON-MONOTONE BOUNDARY (negation) ----------------------------------
    ;; the frontier: open tasks with NO open child -- i.e. the next things the
    ;; RLM root should actually expand. `not-join` makes this stratified.
    [(frontier ?t)
     (open ?t)
     (not-join [?t]
       [?c :task/parent ?t]
       [?c :task/status :open])]])

;; ===========================================================================
;; 2. LINTER  (generate -> check -> repair, run to a FIXPOINT)
;;    A linter rule derives violation/2 facts. The L2 reactive loop keeps firing
;;    repair behaviors until no new violation is derivable -- i.e. semi-naive
;;    evaluation IS the lint loop (Theme 3). On a differential backend
;;    (Materialize/DDlog) the same rules recompute incrementally (Theme 5a).
;;    RGPD flavour: a finding must cite a legal basis AND supporting evidence.
;; ===========================================================================
(def linter
  '[;; --- NON-MONOTONE BOUNDARY (negation-as-failure) -----------------------
    ;; a finding with no outgoing :legal-basis edge is a violation.
    [(violation ?f :missing-legal-basis)
     [?f :node/type :finding]
     (not-join [?f]
       [?e :edge/from ?f]
       [?e :edge/type :legal-basis])]
    ;; a finding with no outgoing :supports edge is a violation.
    [(violation ?f :unsupported)
     [?f :node/type :finding]
     (not-join [?f]
       [?e :edge/from ?f]
       [?e :edge/type :supports])]])

;; ===========================================================================
;; 3. PROVENANCE  (lineage as a recursive query -- Theme 5b, RGPD-grade audit)
;;    Every domain datum carries :prov/caused-by = id of the event that asserted
;;    it; every event carries :event/caused-by = its triggering event. We walk
;;    that chain transitively: "why is this here, and what produced each step?"
;;    answerable at ARBITRARY DEPTH by query, not by reading a log line.
;; ===========================================================================
(def provenance
  '[;; --- MONOTONE CORE -----------------------------------------------------
    ;; reflexive + transitive closure over the event causation chain
    [(event-chain ?e ?e)
     [_ :event/id ?e]]
    [(event-chain ?e ?anc)
     [?ev :event/id ?e]
     [?ev :event/caused-by ?p]
     (event-chain ?p ?anc)]

    ;; full derivation of a node: every (ancestor-event, actor) that led to it
    [(derivation ?node ?event-id ?actor)
     [?node :prov/caused-by ?e0]
     (event-chain ?e0 ?event-id)
     [?ev :event/id ?event-id]
     [?ev :event/actor ?actor]]])

;; Convenience: all rules concatenated. (Head names are disjoint, so a plain
;; concat is safe to pass as the `%` input to d/q.)
(def all-rules
  (vec (concat recursion-tree linter provenance)))

# Datalog ↔ SHACL crosswalk (WP-1c deliverable, SPEC-04 §4)
| Shape | Datalog origin (verbatim source) | Semantic note |
|---|---|---|
| S1 `MissingLegalBasis` | `rules.clj` — `[(violation ?n :missing-legal-basis) [?n :node/type :processing-activity] (not-join [?n] [?n :legal-basis ?_])]` | closed-world not-join → `sh:minCount 1`; Violation |
| S2 `UnsupportedClaim` | linter `:unsupported` (claim with no inbound supports edge) | negation-over-join → inverse path + qualified shape; **Warning** (belief layer: `accepted-undisputed`); PORT-RISK qualifiedValueShape |
| S3 `OrphanPermanentNote` | `zettel.clj` — `[(orphan ?c) [?c :prop/stratum :permanent] (not-join [?c] [?c :zettel/continues ?_])]` | stratum targeted via exporter-materialized class `mnemo:PermanentNote`; `sh:or` continues/trainHead |
| S4 `RegisterCap` | `zettel.clj` `register-overfull` (cap 2) | count aggregate → `sh:maxCount 2` |
| S5 `JudgmentEnvelope` | invariant I4 (`judges.clj` schema requireds) | four `sh:minCount 1` property shapes, one result per missing field |
| S6 `LiteratureStanceLeak` | `zettel.clj` `belief-eligible` (only `:permanent` feeds stances) | inverted as leak detection; needs `sh:sparql`; **PORT-RISK** — Fluree fallback: consolidator-side check |
| S7 `StaleWithoutTask` | advisory pattern over `:derived/stale?` + open tasks | exporter-materialized `mnemo:StaleDerived`; **Warning**; PORT-RISK qualifiedValueShape |
| S8 `FaithfulGate` | `zettel_addendum.md` §1 (permanence requires `:prop/faithful? true`) | `sh:hasValue true` (absence violates — closed-world by construction) |

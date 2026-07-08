#!/usr/bin/env python3
"""human_prompts.py — human-only judgment types for the Mnemosyne registry.

Registers the `bridge_related` judgment type into judge_prompts' registry
using the SAME `register()` mechanism as `zettel_prompts.py`.

  bridge_related : related | unrelated                       [B3 §1.2 / §8]
      A pair of embedding-close notes on different pages that the belief/
      succession layer found no short path between. The HUMAN decides whether
      they are genuinely related. There is NO automatic judge for this type in
      v0 — the jtype exists ONLY to TYPE the human event so it flows through
      the same outbox/ingest mechanics as machine judgments. `related`
      promotes a candidate edge; `unrelated` records the non-link.

Directional? No — the pair is symmetric (a↔b), but v0 does not run it through
the harness at all (no anchor, no conformal gate), so it is neither in
SYMMETRIC_SWAP nor CANONICAL_ORDER_ONLY. It is a pure label vocabulary.

Importing this module mutates the judge_prompts registry in place (idempotent),
exactly like zettel_prompts. Import it once before emitting bridge events.
"""

from __future__ import annotations
from typing import Dict, List

import judge_prompts as JP


# --- label vocabulary (length-neutral, crisp — matches base style) ----------
_LABEL_DEFS: Dict[str, Dict[str, str]] = {
    "bridge_related": {
        "related":   "the two notes genuinely bear on one another; a link is warranted",
        "unrelated": "the two notes only look similar; no real connection between them",
    },
}

_QUESTIONS: Dict[str, str] = {
    "bridge_related": ("Are ITEM_1 and ITEM_2 genuinely related — does one bear "
                       "on the other in a way that warrants a link — or do they "
                       "merely share surface vocabulary?"),
}

_REQUIRED_FIELDS: Dict[str, List[str]] = {
    "bridge_related": ["item_1", "item_1_context", "item_2", "item_2_context"],
}


def register() -> None:
    """Merge the bridge_related type into the judge_prompts registry (idempotent).

    Deliberately does NOT touch SYMMETRIC_SWAP or CANONICAL_ORDER_ONLY: v0 has
    no automatic judge for this type, so no order policy applies.
    """
    JP.LABEL_DEFS.update(_LABEL_DEFS)
    JP.QUESTIONS.update(_QUESTIONS)
    JP.REQUIRED_FIELDS.update(_REQUIRED_FIELDS)


# register on import
register()


# ---------------------------------------------------------------------------
# Self-test (pure; no server). Run: python3 human_prompts.py self-test
# ---------------------------------------------------------------------------
def _self_test() -> None:
    ok = lambda c, m: (print(f"  ✓ {m}") if c else
                       (_ for _ in ()).throw(AssertionError(m)))

    ok("bridge_related" in JP.LABEL_DEFS, "bridge_related in LABEL_DEFS")
    ok("bridge_related" in JP.QUESTIONS, "bridge_related in QUESTIONS")
    ok("bridge_related" in JP.REQUIRED_FIELDS, "bridge_related in REQUIRED_FIELDS")
    ok(list(JP.LABEL_DEFS["bridge_related"]) == ["related", "unrelated"],
       "labels are {related, unrelated}")

    # no automatic judge => no order policy registered
    ok("bridge_related" not in JP.SYMMETRIC_SWAP,
       "bridge_related is not symmetric-swapped (no auto judge)")
    ok("bridge_related" not in JP.CANONICAL_ORDER_ONLY,
       "bridge_related is not canonical-order-only")

    # the vocabulary still assembles into a valid prompt (typing sanity)
    f = {"item_1": "Retention caps follow from purpose limitation.",
         "item_1_context": "page 'Article 5'",
         "item_2": "Standardization enables creative recombination.",
         "item_2_context": "page 'Zettelkasten'"}
    h = JP.context_hash("bridge_related", 1, f)
    p = JP.build_user_prompt("bridge_related", f, h)
    ok("<data:item_1>" in p and "<data:item_2>" in p,
       "bridge_related fences its fields")
    for lab in ("related", "unrelated"):
        ok(lab in p, f"bridge_related prompt lists '{lab}'")

    # idempotent re-register does not duplicate or break anything
    register()
    ok(list(JP.LABEL_DEFS["bridge_related"]) == ["related", "unrelated"],
       "re-register is idempotent")

    print("all human-prompt self-tests passed")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "self-test":
        _self_test()
    else:
        _self_test()

"""Audit the retrieval corpus for answer leakage (offline, no API calls).

Checks, for every question:
  - expert rationale in context : the benchmark's own expert rationale (the answer key used by the
                                  rationale judge) appears verbatim in the retrieved context.
  - expert rationale in corpus  : ... appears verbatim anywhere in the index.
  - question in context         : the question sentence appears in the context. This is expected
                                  for some questions, since GraphRAG-Bench questions were written from
                                  these textbooks (it is the source passage, not an answer key).

Text is compared after lower-casing and removing everything except letters and digits, using the
first 50 such characters. Writes results/leakage.json.

    python src/check_leakage.py
"""

import argparse
import json
import re

from common import CONTEXTS_PATH, INDEX_DIR, LEAKAGE_PATH, load_questions, read_jsonl

PREFIX = 50


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def key(s):
    n = norm(s)
    return n[:PREFIX] if len(n) >= 20 else None     # very short strings are too generic to test


def main(argv=None):
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args(argv)
    questions = load_questions()
    if not CONTEXTS_PATH.exists() or not (INDEX_DIR / "nodes.jsonl").exists():
        raise SystemExit("Run src/build_tree.py and src/retrieval.py first.")
    contexts = {r["idx"]: norm(r["context"]) for r in read_jsonl(CONTEXTS_PATH)}
    corpus = norm(" ".join(n["text"] for n in read_jsonl(INDEX_DIR / "nodes.jsonl")))

    stats = {"questions": len(questions), "checked_rationales": 0, "checked_questions": 0,
             "rationale_in_context": 0, "rationale_in_corpus": 0, "question_in_context": 0}
    flagged = []
    for i, q in enumerate(questions):
        ctx = contexts.get(i, "")
        rk, qk = key(q["Rationale"]), key(q["Question"])
        if rk:
            stats["checked_rationales"] += 1
            in_ctx, in_corpus = rk in ctx, rk in corpus
            stats["rationale_in_context"] += in_ctx
            stats["rationale_in_corpus"] += in_corpus
            if in_ctx:
                flagged.append(i)
        if qk:
            stats["checked_questions"] += 1
            stats["question_in_context"] += qk in ctx

    for k in ("rationale_in_context", "rationale_in_corpus"):
        stats[k + "_rate"] = round(stats[k] / max(stats["checked_rationales"], 1), 4)
    stats["question_in_context_rate"] = round(stats["question_in_context"] / max(stats["checked_questions"], 1), 4)
    stats["flagged_question_idx"] = flagged
    LEAKAGE_PATH.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in stats.items() if k != "flagged_question_idx"}, indent=2))


if __name__ == "__main__":
    main()

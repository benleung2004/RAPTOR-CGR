"""Score runs with the GraphRAG-Bench metrics and keep every per-question judgment.

  Answer score     MC / TF: exact match after normalisation (letters mapped back if options were
                   shuffled). MS: 1 all correct letters, 0.5 a correct non-empty subset, else 0.
                   FB: exact normalised match = 1, otherwise LLM judge. OE: LLM judge (0 / 0.5 / 1).
  Rationale score  LLM judge vs the expert rationale (0 / 0.5 / 1).
  AR score         GraphRAG-Bench combination of both (see scoring.ar_score).
  Items without an expert rationale (18) count for answer accuracy only.
  Shuffled-option runs (MC/MS only) are scored on the answer only.

The judge model is set with JUDGE_* in .env (defaults to the answering model). Use a model from a
different family to avoid self-preference bias; judge the same run twice with two judge models to
measure their agreement in make_report.py.

    python src/evaluate.py                       # every run in results/raw/
    python src/evaluate.py --runs cgr pure --workers 8

Output: results/judgments/<run>__<judge-model>.jsonl (resumable).
"""

import argparse
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import prompts
from common import (JUDGE_DIR, RAW_DIR, JsonlAppender, canonical_topic, judge_file, load_questions,
                    load_run, read_jsonl)
from scoring import answer_score_deterministic, ar_score, parse_judge_score, split_prediction


def judge(llm, template, attempts=3, **fields):
    """Ask the judge for a 0 / 0.5 / 1 score. Returns (score, raw reply, failed flag)."""
    prompt = template.format(**fields)
    reply = ""
    for _ in range(attempts):
        reply, usage = llm.chat([{"role": "system", "content": prompts.JUDGE_SYSTEM},
                                 {"role": "user", "content": prompt}], temperature=0, max_tokens=300)
        TOKENS.add(usage)
        score = parse_judge_score(reply)
        if score is not None:
            return score, reply, False
    return 0.0, reply, True       # conservative: an unreadable judgment counts as 0 and is reported


class _Tokens(threading.local):
    """Judge tokens used for the record currently being evaluated (per worker thread)."""

    def reset(self):
        self.prompt, self.completion = 0, 0

    def add(self, usage):
        self.prompt = getattr(self, "prompt", 0) + (usage or {}).get("prompt_tokens", 0)
        self.completion = getattr(self, "completion", 0) + (usage or {}).get("completion_tokens", 0)


TOKENS = _Tokens()


def evaluate_record(rec, item, llm):
    TOKENS.reset()
    out = _evaluate_record(rec, item, llm)
    out["judge_tokens"] = {"prompt_tokens": TOKENS.prompt, "completion_tokens": TOKENS.completion}
    return out


def _evaluate_record(rec, item, llm):
    rationale, pred_answer = split_prediction(rec["prediction"])
    gold = str(item["Answer"])
    out = {"idx": rec["idx"], "type": rec["type"], "topic": canonical_topic(item["Level-1 Topic"]),
           "pred_answer": pred_answer[:500], "no_answer_tag": not pred_answer, "judge_failed": False}

    a = answer_score_deterministic(rec["type"], pred_answer, gold, rec.get("option_map"))
    out["answer_method"] = "exact" if a is not None else "judge"
    if a is None:
        a, out["answer_judge_reply"], failed = judge(llm, prompts.JUDGE_ANSWER, question=item["Question"],
                                                     gold=gold, pred=pred_answer)
        out["judge_failed"] |= failed

    if "-shuffle" in rec["run"]:
        # shuffled-option runs only measure answer consistency; their reasoning is not re-graded
        out.update(answer_score=a, rationale_score=None, ar_score=None)
        return out
    if not item["Rationale"].strip():
        # 18 benchmark items have no expert rationale: reasoning cannot be graded, so they count
        # for answer accuracy only and are left out of the rationale and AR averages.
        out.update(answer_score=a, rationale_score=None, ar_score=None)
        return out
    if rationale:
        r, out["rationale_judge_reply"], failed = judge(llm, prompts.JUDGE_RATIONALE, question=item["Question"],
                                                        gold_answer=gold, gold=item["Rationale"], pred=rationale)
        out["judge_failed"] |= failed
    else:
        r = 0.0

    out.update(answer_score=a, rationale_score=r, ar_score=ar_score(a, r))
    return out


def evaluate_run(run, llm, workers):
    questions = load_questions()
    records = load_run(RAW_DIR / f"{run}.jsonl")
    out_path = judge_file(run, llm.model)
    done = {r["idx"] for r in read_jsonl(out_path)}
    todo = [i for i in sorted(records) if i not in done]
    print(f"[{run}] judge={llm.model} | {len(records)} answers, {len(done)} judged, {len(todo)} to go")
    if len(records) < len(questions) and "-shuffle" not in run:
        print(f"  warning: only {len(records)}/{len(questions)} questions answered in this run")

    writer = JsonlAppender(out_path)
    start = time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(evaluate_record, records[i], questions[i], llm): i for i in todo}
        for n, fut in enumerate(as_completed(futures), 1):
            try:
                writer.write(fut.result())
            except Exception as e:      # API failure after retries: leave it for the next run
                print(f"  question {futures[fut]} not judged: {type(e).__name__}: {str(e)[:120]}")
            if n % 100 == 0 or n == len(todo):
                print(f"  {n}/{len(todo)} judged ({time.time() - start:.0f}s)")
    writer.close()


def main(argv=None, llm=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", nargs="+", help="default: every file in results/raw/")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)

    if llm is None:
        from llm import LLM
        llm = LLM("judge")
    JUDGE_DIR.mkdir(parents=True, exist_ok=True)
    runs = args.runs or sorted(p.stem for p in RAW_DIR.glob("*.jsonl"))
    for run in runs:
        evaluate_run(run, llm, args.workers)
    print(f"Judge usage: {llm.usage_summary()}")


if __name__ == "__main__":
    main()

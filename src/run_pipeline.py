"""Answer all GraphRAG-Bench questions with one pipeline.

  baseline      DeepSeek only, no retrieval
  pure          + RAPTOR context (standard RAPTOR-RAG)
  cgr           + RAPTOR context + chain of thought + context grounding (RAPTOR-CGR, proposed)
  selfcritique  extra ablation: RAPTOR-RAG answer, then a second call that critiques and fixes it

    python src/run_pipeline.py --pipeline cgr --workers 8
    python src/run_pipeline.py --pipeline cgr --shuffle-seed 1     # MC/MS again, options in a new order
    python src/run_pipeline.py --pipeline baseline --limit 5       # quick test

Output: results/raw/<run>.jsonl, one record per question; finished questions are skipped on rerun.
<run> is the pipeline name, plus "-shuffle<seed>" for shuffled-option runs.
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import prompts
from make_sample import load_sample
from common import (CONTEXTS_PATH, RAW_DIR, TYPE_NAMES, JsonlAppender, detect_question_type,
                    format_question, load_questions, load_run, option_order, read_jsonl)

PIPELINES = ["baseline", "pure", "cgr", "selfcritique"]


ANSWER_MAX_TOKENS = 2048    # caps runaway repetition loops (a real case produced 22,000 characters)


def context_index():
    meta = CONTEXTS_PATH.parent / "contexts_meta.json"
    return json.loads(meta.read_text(encoding="utf-8"))["index"] if meta.exists() else "unknown"


def run_name(pipeline, shuffle_seed=None):
    return pipeline if shuffle_seed is None else f"{pipeline}-shuffle{shuffle_seed}"


def answer(pipeline, llm, qtype, question_text, context):
    """Return (prediction text, usage). Temperature 0 for every call."""
    name = TYPE_NAMES[qtype]
    if pipeline == "baseline":
        msgs = [{"role": "system", "content": prompts.BASELINE_SYSTEM},
                {"role": "user", "content": prompts.user_prompt(name, question_text)}]
        return llm.chat(msgs, max_tokens=ANSWER_MAX_TOKENS)
    if pipeline in ("pure", "selfcritique"):
        msgs = [{"role": "system", "content": prompts.RAG_SYSTEM},
                {"role": "user", "content": prompts.user_prompt(name, question_text, context)}]
        first, u1 = llm.chat(msgs, max_tokens=ANSWER_MAX_TOKENS)
        if pipeline == "pure":
            return first, u1
        review = prompts.CRITIQUE_USER.format(question_block=prompts.question_block(name, question_text),
                                              context=context, first_answer=first,
                                              format_rules=prompts.FORMAT_RULES)
        second, u2 = llm.chat([{"role": "system", "content": prompts.CRITIQUE_SYSTEM},
                               {"role": "user", "content": review}], max_tokens=ANSWER_MAX_TOKENS)
        return second, {k: u1[k] + u2[k] for k in u1}
    if pipeline == "cgr":
        msgs = [{"role": "system", "content": prompts.CGR_SYSTEM},
                {"role": "user", "content": prompts.user_prompt(name, question_text, context)}]
        return llm.chat(msgs, max_tokens=ANSWER_MAX_TOKENS)
    raise ValueError(pipeline)


def main(argv=None, llm=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pipeline", choices=PIPELINES, required=True)
    parser.add_argument("--shuffle-seed", type=int, help="show MC/MS options in a seeded random order")
    parser.add_argument("--workers", type=int, default=8, help="parallel API requests")
    parser.add_argument("--limit", type=int, help="only the first N questions")
    parser.add_argument("--sample", help="only the questions in a sample file (src/make_sample.py)")
    args = parser.parse_args(argv)

    questions = load_questions()[: args.limit]
    contexts = {}
    if args.pipeline != "baseline":
        contexts = {r["idx"]: r["context"] for r in read_jsonl(CONTEXTS_PATH)}
        if len(contexts) < len(questions):
            raise SystemExit("Missing retrieved contexts - run src/build_tree.py and src/retrieval.py first.")

    if llm is None:
        from llm import LLM
        llm = LLM("answer")

    run = run_name(args.pipeline, args.shuffle_seed)
    out_path = RAW_DIR / f"{run}.jsonl"
    existing = read_jsonl(out_path)
    other_models = {r["model"] for r in existing} - {llm.model}
    if other_models:
        raise SystemExit(f"{out_path} already holds answers from {sorted(other_models)}; move it away "
                         f"before running with {llm.model} so that one run never mixes two models.")
    index = "none" if args.pipeline == "baseline" else context_index()
    other_index = {r.get("index", "unknown") for r in existing} - {index}
    if other_index:
        raise SystemExit(f"{out_path} already holds answers retrieved from {sorted(other_index)}, but the current "
                         f"contexts come from '{index}'. Use a separate EXPERIMENT folder so runs never mix.")
    done = {r["idx"] for r in existing if not r.get("error")}
    wanted = set(load_sample(args.sample)) if args.sample else set(range(len(questions)))
    todo = [i for i in range(len(questions)) if i in wanted and i not in done
            and (args.shuffle_seed is None or questions[i].get("Choices"))]   # shuffle runs: MC/MS only
    print(f"[{run}] model={llm.model} | {len(done)} done, {len(todo)} to go")

    writer = JsonlAppender(out_path)

    def work(idx):
        item = questions[idx]
        qtype = detect_question_type(item)
        option_map = option_order(item, idx, args.shuffle_seed) if item.get("Choices") else None
        record = {"idx": idx, "run": run, "pipeline": args.pipeline, "model": llm.model, "index": index,
                  "type": qtype, "shuffle_seed": args.shuffle_seed, "option_map": option_map}
        try:
            text, usage = answer(args.pipeline, llm, qtype, format_question(item, option_map), contexts.get(idx))
            record.update(prediction=text, usage=usage, error=None)
        except Exception as e:
            record.update(prediction="", usage=None, error=f"{type(e).__name__}: {e}")
        writer.write(record)
        return record

    start, finished = time.time(), 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for fut in as_completed([pool.submit(work, i) for i in todo]):
            finished += 1
            if fut.result()["error"]:
                print(f"  error on question {fut.result()['idx']}: {fut.result()['error'][:150]}")
            if finished % 50 == 0 or finished == len(todo):
                print(f"  {finished}/{len(todo)} answered ({time.time() - start:.0f}s)")
    writer.close()

    answered = load_run(out_path)
    failed = {r["idx"] for r in read_jsonl(out_path) if r.get("error")} - set(answered)
    print(f"[{run}] finished. usage={llm.usage_summary()}"
          + (f" | {len(failed)} errors - rerun the same command to retry them" if failed else ""))


if __name__ == "__main__":
    main()

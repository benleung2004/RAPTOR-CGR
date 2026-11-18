"""Score pipelines with the GraphRAG-Bench metrics (LLM-as-judge, DeepSeek).

  Answer score    MC/TF: exact match; MS: 1 / 0.5 (correct subset) / 0; FB/OE: LLM judge 0 / 0.5 / 1
  Rationale score LLM judge comparing the predicted rationale with the expert rationale (0 / 0.5 / 1)
  AR score        combines both (see calculate_ar_score)

Reads results/eval_inputs/ (run build_eval_inputs.py first) and updates results/scores.json.

    python src/evaluate.py                          # every pipeline not yet in scores.json
    python src/evaluate.py --pipelines RAPTOR-CGR --force
"""

import argparse
import json
import re

from tqdm import tqdm

from common import PREDICTIONS_DIR, QUESTION_TYPES, QUESTIONS_DIR, SCORES_PATH, get_client

client, MODEL = None, None

JUDGE_PROMPT = """
You are a strict evaluator. Compare the following two {kind}s for correctness and completeness:

Predicted {Kind}: {pred}

Gold {Kind}: {gold}

Please evaluate the predicted {kind} in comparison to the gold {kind}. Respond with a score between 0 and 1:
- 1: The predicted {kind} fully aligns with the gold {kind}.
- 0.5: The predicted {kind} is partially correct but lacks completeness or includes incorrect information.
- 0: The predicted {kind} is incorrect or completely misaligned with the gold {kind}.

only provide the score without any explanation.
"""


def judge(kind, pred, gold):
    prompt = JUDGE_PROMPT.format(kind=kind, Kind=kind.capitalize(), pred=pred, gold=gold)
    resp = client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": prompt}],
                                          max_tokens=5, temperature=0)
    try:
        return float(resp.choices[0].message.content.strip())
    except ValueError:
        return 0.0


def extract_feature(text):
    """Split a 'RATIONALE: ... ANSWER: ...' prediction into (rationale, answer)."""
    if "Please answer the following" in text:
        text = text.split("Please answer the following")[0].strip()
    parts = text.split("ANSWER:")
    if len(parts) < 2:
        return "", ""
    answer = parts[1].strip().split("\n")[0]
    rationale = parts[0].strip()
    if "RATIONALE:" in rationale:
        rationale = rationale.split("RATIONALE:")[1].strip()
    return rationale, answer


def answer_score(qtype, pred, gold):
    if qtype in ("MC", "TF"):
        return 1.0 if pred == gold else 0.0
    if qtype == "MS":
        correct, predicted = set(re.findall(r"[A-E]", gold)), set(re.findall(r"[A-E]", pred))
        if predicted == correct:
            return 1.0
        return 0.5 if predicted.issubset(correct) else 0.0
    return judge("answer", pred, gold)  # FB, OE


def calculate_ar_score(a, r):
    if a == 1:
        return {1: 1.0, 0.5: 0.5}.get(r, 0.0)
    if a == 0:
        return {1: 0.5, 0.5: 0.25}.get(r, 0.0)
    return 0.0


def empty():
    return {"rationale_score": 0.0, "answer_score": 0.0, "ar_score": 0.0, "count": 0}


def evaluate_pipeline(name):
    results = {"total": empty(), "by_type": {t: empty() for t in QUESTION_TYPES}, "by_topic": {}}
    for t in tqdm(QUESTION_TYPES, desc=name):
        questions = [json.loads(l) for l in open(QUESTIONS_DIR / f"{t}.jsonl", encoding="utf-8")]
        preds = json.load(open(PREDICTIONS_DIR / name / f"GraphRAG-Bench_{t}.json", encoding="utf-8"))
        for q in questions:
            if str(q["idx"]) not in preds:
                continue
            p_rat, p_ans = extract_feature(preds[str(q["idx"])]["prediction"])
            r = judge("rationale", p_rat, q["Rationale"])
            a = answer_score(t, p_ans, q["Answer"])
            ar = calculate_ar_score(a, r)
            topic = q["Level-1 Topic"]
            for bucket in (results["total"], results["by_type"][t], results["by_topic"].setdefault(topic, empty())):
                bucket["rationale_score"] += r
                bucket["answer_score"] += a
                bucket["ar_score"] += ar
                bucket["count"] += 1

    for bucket in [results["total"], *results["by_type"].values(), *results["by_topic"].values()]:
        if bucket["count"]:
            for k in ("rationale_score", "answer_score", "ar_score"):
                bucket[k] /= bucket["count"]
    return results


def main():
    global client, MODEL
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pipelines", nargs="+", help="default: every folder in results/eval_inputs/predictions")
    parser.add_argument("--force", action="store_true", help="re-evaluate pipelines already in scores.json")
    args = parser.parse_args()

    client, MODEL = get_client()
    scores = json.loads(SCORES_PATH.read_text(encoding="utf-8")) if SCORES_PATH.exists() else {}
    names = args.pipelines or sorted(p.name for p in PREDICTIONS_DIR.iterdir() if p.is_dir())

    for name in names:
        if name in scores and not args.force:
            print(f"Skipping {name}: already in {SCORES_PATH.name} (use --force to redo)")
            continue
        scores[name] = evaluate_pipeline(name)
        SCORES_PATH.write_text(json.dumps(scores, indent=2), encoding="utf-8")
        tot = scores[name]["total"]
        print(f"{name}: answer={tot['answer_score']:.4f} rationale={tot['rationale_score']:.4f} AR={tot['ar_score']:.4f}")


if __name__ == "__main__":
    main()

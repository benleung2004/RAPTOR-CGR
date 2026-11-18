"""Draw a stratified random sample of benchmark questions (same type mix as the full 1,018).

    python src/make_sample.py --n 300 --seed 42      # -> data/samples/sample_300_seed42.json

Pass the file to run_pipeline.py / retrieval.py with --sample so every system answers exactly the
same questions.
"""

import argparse
import json
import random
from collections import defaultdict

from common import DATA_DIR, QUESTION_TYPES, detect_question_type, load_questions

SAMPLE_DIR = DATA_DIR / "samples"


def stratified_sample(questions, n, seed):
    by_type = defaultdict(list)
    for i, q in enumerate(questions):
        by_type[detect_question_type(q)].append(i)
    total = len(questions)
    # proportional allocation, largest remainders so the counts add up to n exactly
    exact = {t: n * len(by_type[t]) / total for t in QUESTION_TYPES}
    counts = {t: int(exact[t]) for t in QUESTION_TYPES}
    for t in sorted(QUESTION_TYPES, key=lambda t: exact[t] - counts[t], reverse=True)[: n - sum(counts.values())]:
        counts[t] += 1
    rng = random.Random(seed)
    chosen = []
    for t in QUESTION_TYPES:
        chosen += rng.sample(by_type[t], counts[t])
    return sorted(chosen), counts


def load_sample(path):
    return json.loads(open(path, encoding="utf-8").read())["idx"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    questions = load_questions()
    idx, counts = stratified_sample(questions, args.n, args.seed)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    out = SAMPLE_DIR / f"sample_{args.n}_seed{args.seed}.json"
    out.write_text(json.dumps({"n": args.n, "seed": args.seed, "by_type": counts, "idx": idx}, indent=1),
                   encoding="utf-8")
    print(f"{args.n} questions {counts} -> {out}")


if __name__ == "__main__":
    main()

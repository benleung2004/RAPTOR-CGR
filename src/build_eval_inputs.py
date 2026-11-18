"""Split the benchmark and each pipeline's raw results by question type for evaluate.py.

Writes:
  results/eval_inputs/questions/{FB,MC,MS,OE,TF}.jsonl
  results/eval_inputs/predictions/<pipeline>/GraphRAG-Bench_{FB,...}.json  ({"<idx>": {"prediction": ...}})

    python src/build_eval_inputs.py
"""

import json

from common import (PIPELINES, PREDICTIONS_DIR, QUESTION_TYPES, QUESTIONS_DIR, detect_question_type,
                    load_dataset, load_raw_results)


def main():
    data = load_dataset()
    qtype_of = {i: detect_question_type(item) for i, item in enumerate(data)}

    QUESTIONS_DIR.mkdir(parents=True, exist_ok=True)
    for t in QUESTION_TYPES:
        with open(QUESTIONS_DIR / f"{t}.jsonl", "w", encoding="utf-8") as f:
            for i, item in enumerate(data):
                if qtype_of[i] == t:
                    f.write(json.dumps({"idx": i, **item}, ensure_ascii=False) + "\n")
    print(f"Questions written to {QUESTIONS_DIR}")

    for name, raw_path in PIPELINES.items():
        if not raw_path.exists():
            print(f"  skip {name}: {raw_path.name} not found")
            continue
        predictions = load_raw_results(raw_path)
        out_dir = PREDICTIONS_DIR / name
        out_dir.mkdir(parents=True, exist_ok=True)
        for t in QUESTION_TYPES:
            records = {}
            for idx in sorted(predictions):
                if qtype_of[idx] != t:
                    continue
                text = predictions[idx] or ""
                if "RATIONALE:" not in text:
                    text = f"RATIONALE: Not available\nANSWER: {text}"
                records[str(idx)] = {"prediction": text}
            with open(out_dir / f"GraphRAG-Bench_{t}.json", "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, ensure_ascii=False)
        print(f"  {name}: {len(predictions)} predictions")


if __name__ == "__main__":
    main()

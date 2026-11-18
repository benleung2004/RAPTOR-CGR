"""Pipeline 1 - DeepSeek baseline: answer every question with no retrieval.

Output: results/raw/baseline.jsonl (one JSON object per question, resumable).

    python src/run_baseline.py            # all 1,018 questions
    python src/run_baseline.py --limit 5  # quick test
"""

import argparse
import json
import re
import time

from common import PIPELINES, detect_question_type, extract_answer_line, get_client, load_dataset

SYSTEM_PROMPT = """You are an expert in computer science, programming, and software engineering.
Your task is to answer technical questions accurately and concisely.
Always respond in this exact format:
RATIONALE: <your reasoning here>
ANSWER: <your answer here>

For fill-in-the-blank questions, the ANSWER should be only the missing term(s).
For multiple-choice questions, the ANSWER should be only the letter (A, B, C, or D).
For true/false questions, the ANSWER should be only True or False.
For open-ended questions, the ANSWER should be a clear and concise response."""


def clean_llm_content(text):
    """Strip markdown code fences and zero-width characters from a model reply."""
    if not isinstance(text, str):
        return ""
    t = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    t = re.sub(r"[​-‍﻿]", "", t)
    m = re.match(r"^\s*```(?:\s*\w+)?\s*\n(?P<body>[\s\S]*?)\n\s*```\s*$", t, re.MULTILINE)
    if m:
        t = m.group("body").strip()
    elif t.startswith("```") and t.endswith("```") and len(t) >= 6:
        t = t[3:-3].strip()
    if t.lower().startswith("json\n"):
        t = t.split("\n", 1)[1].strip()
    return t


def build_user_prompt(item):
    question = item.get("Question", "")
    choices = item.get("Choices")
    if choices:
        options = "\n".join(f"{k}) {v}" for k, v in sorted(choices.items()))
        return f"Question: {question}\n\nOptions:\n{options}\n\nRespond in the required RATIONALE / ANSWER format."
    return f"Question: {question}\n\nRespond in the required RATIONALE / ANSWER format."


def call_llm(client, model, user_prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": user_prompt}],
                temperature=0.2,
            )
            return clean_llm_content(resp.choices[0].message.content)
        except Exception as e:
            print(f"  LLM error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return f"Error: {e}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, help="only answer the first N questions")
    parser.add_argument("--output", default=str(PIPELINES["DeepSeek-Baseline"]))
    args = parser.parse_args()

    client, model = get_client()
    data = load_dataset()
    end = min(args.limit, len(data)) if args.limit else len(data)

    done = set()
    try:
        with open(args.output, encoding="utf-8") as f:
            done = {json.loads(line)["question_id"] for line in f if line.strip()}
        print(f"Resuming: {len(done)} questions already answered.")
    except FileNotFoundError:
        pass

    with open(args.output, "a", encoding="utf-8") as f:
        for idx in range(end):
            if idx in done:
                continue
            item = data[idx]
            qtype = detect_question_type(item)
            prediction = call_llm(client, model, build_user_prompt(item))
            answer = extract_answer_line(prediction) or prediction.strip()
            print(f"[{idx + 1}/{end}] [{qtype}] expected={item['Answer']!r:.40} got={answer!r:.40}")
            f.write(json.dumps({
                "question_id": idx,
                "type": qtype,
                "level1_topic": item.get("Level-1 Topic", ""),
                "level2_topic": item.get("Level-2 Topic", ""),
                "question": item.get("Question", ""),
                "gold_answer": item.get("Answer", ""),
                "generated_answer": answer,
                "prediction": prediction,
            }, ensure_ascii=False) + "\n")
            f.flush()
            time.sleep(0.5)

    print(f"Done. Results saved to {args.output}")


if __name__ == "__main__":
    main()

"""Shared helpers: paths, LLM client, dataset loading and question formatting."""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "data" / "graphrag_bench.jsonl"
TREE_PATH = ROOT / "data" / "raptor_tree.pkl"
RAW_DIR = ROOT / "results" / "raw"
EVAL_DIR = ROOT / "results" / "eval_inputs"
QUESTIONS_DIR = EVAL_DIR / "questions"
PREDICTIONS_DIR = EVAL_DIR / "predictions"
SCORES_PATH = ROOT / "results" / "scores.json"
LOG_DIR = ROOT / "results" / "logs"

QUESTION_TYPES = ["FB", "MC", "MS", "OE", "TF"]
TYPE_NAMES = {
    "FB": "Fill-in-blank",
    "MC": "Multiple choice",
    "MS": "Multi-select",
    "OE": "Open-ended",
    "TF": "True/False",
}

# Pipeline name -> raw result file produced by run_baseline.py / run_raptor.py
PIPELINES = {
    "DeepSeek-Baseline": RAW_DIR / "baseline.jsonl",
    "RAPTOR-Pure": RAW_DIR / "raptor_pure.json",
    "RAPTOR-SelfCritique": RAW_DIR / "raptor_selfcritique.json",
    "RAPTOR-CGR": RAW_DIR / "raptor_cgr.json",
}

# Make the vendored `raptor` package importable from any working directory.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def get_client():
    """Return (OpenAI client, model name) configured from .env (DeepSeek by default)."""
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv(ROOT / ".env")
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        sys.exit("LLM_API_KEY is not set. Copy .env.example to .env and fill in your key.")
    client = OpenAI(api_key=api_key, base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"))
    return client, os.getenv("LLM_MODEL", "deepseek-chat")


def load_dataset(path=DATASET_PATH):
    """Load the benchmark: one JSON object per line (a JSON array also works)."""
    raw = Path(path).read_text(encoding="utf-8").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return [json.loads(line) for line in raw.splitlines() if line.strip()]


def detect_question_type(item):
    """Infer the GraphRAG-Bench question type (FB/MC/MS/OE/TF) from an item."""
    answer = str(item.get("Answer", "")).strip().upper()
    choices = item.get("Choices")
    question = item.get("Question", "")

    if choices and isinstance(choices, dict):
        return "MS" if len(re.findall(r"[A-E]", answer)) >= 2 else "MC"
    if answer in ("TRUE", "FALSE"):
        return "TF"
    if re.search(r"_{2,}", question):
        return "FB"
    if re.match(r"^[A-E]$", answer):
        return "MC"
    return "OE"


def format_question(item):
    """Question text followed by its options (if any), one per line as 'A: ...'."""
    question = item.get("Question", "")
    choices = item.get("Choices") or {}
    if choices:
        return question + "\n" + "\n".join(f"{k}: {v}" for k, v in choices.items())
    return question


def extract_answer_line(prediction):
    """Return the text after 'ANSWER:' on its line, or '' if absent."""
    parts = prediction.split("ANSWER:")
    return parts[1].strip().split("\n")[0].strip() if len(parts) >= 2 else ""


def load_raw_results(path):
    """Load a raw result file as {dataset index: prediction text}."""
    path = Path(path)
    if path.suffix == ".jsonl":
        rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        return {r["question_id"]: r["prediction"] for r in rows}
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {r["idx"]: r["prediction"] for r in rows}

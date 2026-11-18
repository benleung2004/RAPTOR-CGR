"""Shared paths, configuration, dataset helpers and small JSONL utilities."""

import json
import os
import random
import re
import sys
import threading
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
QUESTIONS_PATH = DATA_DIR / "graphrag_bench.jsonl"
TEXTBOOK_DIR = DATA_DIR / "textbooks"           # downloaded by download_data.py (not committed)
TREE_DIR = DATA_DIR / "trees"                   # one RAPTOR tree per textbook (not committed)
INDEX_DIR = DATA_DIR / "index"                  # flat index over every tree node (not committed)

RESULTS_DIR = ROOT / "results"
CONTEXTS_PATH = RESULTS_DIR / "contexts.jsonl"  # retrieved context for every question
RAW_DIR = RESULTS_DIR / "raw"                   # one JSONL per run (model outputs)
JUDGE_DIR = RESULTS_DIR / "judgments"           # one JSONL per (run, judge model)
TABLE_DIR = RESULTS_DIR / "tables"
SCORES_PATH = RESULTS_DIR / "scores.json"
LEAKAGE_PATH = RESULTS_DIR / "leakage.json"
LOG_DIR = RESULTS_DIR / "logs"

# Retrieval / tree settings (same values as the report: 2 layers, GMM threshold 0.5, top-10 nodes)
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_TOKENS = 100
TREE_LAYERS = 2
CLUSTER_THRESHOLD = 0.5
SUMMARY_TOKENS = 100
TOP_K = 10
CONTEXT_MAX_TOKENS = 3500

QUESTION_TYPES = ["FB", "MC", "MS", "OE", "TF"]
TYPE_NAMES = {"FB": "Fill-in-blank", "MC": "Multiple choice", "MS": "Multi-select",
              "OE": "Open-ended", "TF": "True/False"}

# Inconsistent Level-1 topic labels in GraphRAG-Bench, merged for reporting.
TOPIC_ALIASES = {
    "Data Structure and Algorithm": "Data structures and algorithms",
    "Meaching learning": "Machine learning",
    "Machine Learning": "Machine learning",
    "Data Science": "Data science and big data",
    "Information Retrieval": "Information retrieval",
    "Database": "Database systems",
    "Computer Networks": "Computer networks",
    "Computer Network": "Computer networks",
    "Computer Architecture": "Computer architecture",
    "Natural Language Processing": "NLP",
    "Natural language processing": "NLP",
    "Computer Vision": "Computer vision",
    "Mathematics (for CS and AI)": "Mathematics (for computer science and AI)",
    "Artificial intelligence intro": "Artificial intelligence introduction",
}

if str(ROOT) not in sys.path:          # make the vendored `raptor` package importable
    sys.path.insert(0, str(ROOT))


# ── Configuration ────────────────────────────────────────────────────────────
def load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass


def extra_body_for(prefix, base_url):
    """Provider-specific request options from <prefix>_EXTRA_BODY (JSON).

    Default for DeepSeek: thinking mode off. DeepSeek models think by default; the hidden reasoning
    is slow and uses up max_tokens (empty 100-token summaries, empty judge replies), and v1 used
    the non-thinking deepseek-chat. Set e.g. {"thinking": {"type": "enabled"}} to turn it back on.
    """
    raw = os.getenv(f"{prefix}_EXTRA_BODY")
    if raw:
        return json.loads(raw)
    if "deepseek.com" in (base_url or ""):
        return {"thinking": {"type": "disabled"}}
    return None


def model_config(role):
    """Endpoint settings for role 'answer' (answering + summaries) or 'judge' (evaluation).

    The judge falls back to the answer settings when JUDGE_* variables are not set.
    """
    load_env()
    base = {"api_key": os.getenv("LLM_API_KEY"),
            "base_url": os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
            "model": os.getenv("LLM_MODEL", "deepseek-flash")}
    base["extra_body"] = extra_body_for("LLM", base["base_url"])
    if role == "judge":
        url = os.getenv("JUDGE_BASE_URL") or base["base_url"]
        base = {"api_key": os.getenv("JUDGE_API_KEY") or base["api_key"], "base_url": url,
                "model": os.getenv("JUDGE_MODEL") or base["model"],
                "extra_body": extra_body_for("JUDGE", url)}
    return base


# ── Dataset ──────────────────────────────────────────────────────────────────
def load_questions(path=QUESTIONS_PATH):
    """The 1,018 GraphRAG-Bench questions (one JSON object per line)."""
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def detect_question_type(item):
    """Infer the question type (FB/MC/MS/OE/TF) from an item."""
    answer = str(item.get("Answer", "")).strip().upper()
    choices = item.get("Choices")
    if choices and isinstance(choices, dict):
        return "MS" if len(re.findall(r"[A-E]", answer)) >= 2 else "MC"
    if answer in ("TRUE", "FALSE"):
        return "TF"
    if re.search(r"_{2,}", item.get("Question", "")):
        return "FB"
    return "OE"


def canonical_topic(label):
    label = label.strip()
    return TOPIC_ALIASES.get(label, label)


def option_order(item, idx, shuffle_seed=None):
    """Return the displayed option letters mapped to original letters, e.g. {'A': 'C', 'B': 'A', ...}.

    With shuffle_seed=None the original order is kept. The permutation is deterministic per
    (seed, question) so a shuffled run can be resumed and reproduced.
    """
    letters = sorted((item.get("Choices") or {}).keys())
    shown = list(letters)
    if shuffle_seed is not None and len(letters) > 1:
        rng = random.Random(f"{shuffle_seed}-{idx}")
        while shown == letters:
            rng.shuffle(shown)
    return dict(zip(letters, shown))


def format_question(item, option_map=None):
    """Question text plus options rendered in the (possibly shuffled) display order."""
    text = item.get("Question", "")
    choices = item.get("Choices") or {}
    if not choices:
        return text
    option_map = option_map or {k: k for k in choices}
    lines = [f"{shown}. {choices[orig]}" for shown, orig in sorted(option_map.items())]
    return text + "\nOptions:\n" + "\n".join(lines)


# ── JSONL helpers ────────────────────────────────────────────────────────────
def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def load_run(path):
    """{idx: record} keeping the latest successful record per question (retries append new lines)."""
    records = {}
    for r in read_jsonl(path):
        if not r.get("error"):
            records[r["idx"]] = r
    return records


def judge_file(run, judge_model):
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", judge_model)
    return JUDGE_DIR / f"{run}__{safe}.jsonl"


class JsonlAppender:
    """Thread-safe append-only JSONL writer (one flush per record, so runs can resume)."""

    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._f = open(path, "a", encoding="utf-8")
        self._lock = threading.Lock()

    def write(self, record):
        with self._lock:
            self._f.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._f.flush()

    def close(self):
        self._f.close()

# ── Textbook cleaning (shared by build_tree.py and build_web_index.py) ──────
BOILERPLATE = [r"Author: Kevin P\. Murphy\. \(C\) MIT Press\. CC-BY-NC-ND license"]
_HTML_TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9]*(?:\s[^<>\n]*)?/?>")   # real tags only, never "a < b > c"


def fix_pdf_artifacts(text):
    """Undo systematic PDF-extraction errors, only in books where they are clearly systematic.

    One textbook (CLRS) encodes the 'fi'/'fl' ligatures as 'û'/'ü' (ûrst, üow) and the apostrophe as
    '9' (Dijkstra9s). A few genuine 'ü' (e.g. Müller) elsewhere must stay, so the fix is only applied
    when the artifact is frequent in that book.
    """
    if text.count("û") > 200:
        text = re.sub(r"(?<=\w)û|û(?=\w)", "fi", text)
        text = re.sub(r"(?<=\w)ü|ü(?=\w)", "fl", text)
    if len(re.findall(r"[a-z]9s\b", text)) > 50:
        text = re.sub(r"(?<=[A-Za-z])9s\b", "'s", text)
    return text


def clean_markdown(text):
    """Remove images, HTML markup and running headers/footers while keeping all real content."""
    text = fix_pdf_artifacts(text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)                       # images
    text = re.sub(r"</t[dh]>", " | ", text)                                  # keep table cells apart
    text = re.sub(r"</tr>", "\n", text)
    text = _HTML_TAG.sub(" ", text)
    for pattern in BOILERPLATE:
        text = re.sub(pattern, " ", text)
    # long lines repeated all over a book are running headers/footers (short ones may be code)
    counts = Counter(l.strip() for l in text.splitlines() if len(l.strip()) >= 25)
    text = "\n".join(l for l in text.splitlines()
                     if not (counts.get(l.strip(), 0) > 15 and not l.lstrip().startswith("#")))
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def split_chunks(text, tokenizer, max_tokens):
    """Split text into chunks of at most max_tokens WITHOUT altering it.

    RAPTOR's split_text deletes every '.', '!', '?' and newline it splits on, which breaks
    sentences, section numbers (6.5 -> "6 5") and multi-line pseudocode/tables. Here paragraphs
    (blank-line separated) are packed whole; an over-long paragraph is cut at sentence ends,
    then at line breaks, then by tokens. Pieces are re-joined with the separator they had, so
    the original text is kept (only the whitespace at a chunk boundary is dropped).
    """
    def n(t):
        return len(tokenizer.encode(t, disallowed_special=()))

    def units(par, sep):
        """[(separator before the unit, unit text)] for one paragraph."""
        if n(par) <= max_tokens:
            return [(sep, par)]
        for pattern, joiner in ((r"(?<=[.!?])\s+(?=[A-Z0-9$\\(\[])", " "), (r"\n", "\n")):
            parts = [p for p in re.split(pattern, par) if p.strip()]
            if len(parts) > 1:
                return [u for i, p in enumerate(parts) for u in units(p, sep if i == 0 else joiner)]
        toks = tokenizer.encode(par, disallowed_special=())
        return [(sep if i == 0 else "", tokenizer.decode(toks[i:i + max_tokens]))
                for i in range(0, len(toks), max_tokens)]

    chunks, current, size = [], "", 0
    for par in re.split(r"\n\s*\n", text):
        if not par.strip():
            continue
        for sep, unit in units(par.strip("\n"), "\n\n"):
            cost = n(unit) + (n(sep) if current and sep else 0)
            if current and size + cost > max_tokens:
                chunks.append(current)
                current, size = unit, n(unit)
            else:
                current = current + sep + unit if current else unit
                size += cost
    if current:
        chunks.append(current)
    return chunks

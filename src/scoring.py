"""Parsing model outputs and deterministic scoring (no LLM involved)."""

import json
import re

_ANSWER_TAG = re.compile(r"(?im)^[\s>*#_]*(?:final\s+)?answer[\s*_]*:[\s*_]*")
_RATIONALE_TAG = re.compile(r"(?im)^[\s>*#_]*rationale[\s*_]*:[\s*_]*")


def split_prediction(text):
    """Split 'RATIONALE: ... ANSWER: ...' into (rationale, answer).

    Tolerates markdown (**ANSWER:**), 'Final answer:' and multi-line answers. The answer is
    everything after the last ANSWER tag; it is '' when there is no tag (counted as unanswered).
    """
    text = (text or "").replace("\r\n", "\n")
    tags = list(_ANSWER_TAG.finditer(text))
    if not tags:
        bare = text.strip().strip("*_").strip()
        # thinking-mode replies are sometimes just the answer ("A, C, D", "2n + 2"): accept a short
        # one-line reply as the answer; anything longer without a tag counts as unanswered
        if bare and "\n" not in bare and len(bare) <= 120:
            return "", bare
        return text.strip(), ""
    last = tags[-1]
    answer = text[last.end():].strip().strip("*_").strip()
    head = text[:last.start()]
    rat = list(_RATIONALE_TAG.finditer(head))
    rationale = head[rat[-1].end():] if rat else head
    return rationale.strip(), answer


def _clean(s):
    return re.sub(r"[*_`]", "", s or "").strip()


def mc_letter(answer, option_map=None):
    """First option letter of an MC answer like 'B', '(B)', 'B. queue', 'Option B' -> original letter."""
    a = _clean(answer)
    m = (re.match(r"^\(?([A-E])(?:[\).:,\s]|$)", a)
         or re.search(r"\b(?:option|answer is|choice)\s*\(?([A-E])\b", a, re.I))
    if not m:
        return None
    letter = m.group(1).upper()
    return (option_map or {}).get(letter, letter)


def ms_letters(answer, option_map=None):
    """Set of option letters in a multi-select answer like 'A, C', 'A and C', '(A)(D): ...'."""
    a = _clean(answer).split("\n")[0]
    a = re.sub(r"\b(and|&|or)\b", ",", a, flags=re.I)
    prefix = re.split(r"[a-z]{2,}", a, maxsplit=1)[0]      # stop at the first explanatory word
    letters = re.findall(r"(?<![A-Za-z])([A-E])(?![A-Za-z])", prefix)
    return {(option_map or {}).get(l, l) for l in letters}


def tf_value(answer):
    a = _clean(answer).lower()
    if re.match(r"^(true|t)\b", a):
        return "true"
    if re.match(r"^(false|f)\b", a):
        return "false"
    return None


def normalize_text(s):
    s = _clean(s).lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    return " ".join(s.split())


def answer_score_deterministic(qtype, pred_answer, gold, option_map=None):
    """Score MC / MS / TF exactly; FB only when it is an exact (normalised) match.

    Returns a float, or None when an LLM judge is needed (FB mismatch, OE).
    """
    if qtype == "MC":
        return 1.0 if mc_letter(pred_answer, option_map) == gold.strip().upper() else 0.0
    if qtype == "MS":
        pred, correct = ms_letters(pred_answer, option_map), set(re.findall(r"[A-E]", gold.upper()))
        if pred == correct:
            return 1.0
        return 0.5 if pred and pred < correct else 0.0      # empty answer no longer earns 0.5
    if qtype == "TF":
        return 1.0 if tf_value(pred_answer) == gold.strip().lower() else 0.0
    if qtype == "FB":
        if not pred_answer:
            return 0.0
        return 1.0 if normalize_text(pred_answer) == normalize_text(gold) else None
    if qtype == "OE":
        return 0.0 if not pred_answer else None
    raise ValueError(qtype)


def parse_judge_score(text):
    """Read a 0 / 0.5 / 1 score from a judge reply (JSON or bare number); None if unreadable."""
    try:
        value = float(json.loads(text)["score"])
    except Exception:
        m = re.search(r"(?<![\d.])(0\.5|0(?:\.0)?|1(?:\.0)?)(?![\d.])", text or "")
        if not m:
            return None
        value = float(m.group(1))
    return value if value in (0.0, 0.5, 1.0) else None


def ar_score(answer, rationale):
    """GraphRAG-Bench AR score: rewards a correct answer only together with correct reasoning."""
    if answer == 1:
        return {1.0: 1.0, 0.5: 0.5}.get(rationale, 0.0)
    if answer == 0:
        return {1.0: 0.5, 0.5: 0.25}.get(rationale, 0.0)
    return 0.0

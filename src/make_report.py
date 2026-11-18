"""Turn results/scores.json into CSV tables, an Excel workbook and Markdown tables.

Topic labels in GraphRAG-Bench are inconsistent ("Computer Network", "Computer Networks",
"Meaching learning", ...); they are merged here for reporting only (count-weighted means).

    python src/make_report.py
"""

import json

import pandas as pd

from common import QUESTION_TYPES, ROOT, SCORES_PATH, TYPE_NAMES

TABLE_DIR = ROOT / "results" / "tables"
METRICS = {"answer_score": "Answer Accuracy", "rationale_score": "Rationale Score", "ar_score": "AR Score"}
ORDER = ["DeepSeek-Baseline", "RAPTOR-Pure", "RAPTOR-SelfCritique", "RAPTOR-CGR"]

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


def canonical_topic(label):
    label = label.strip()
    return TOPIC_ALIASES.get(label, label)


def merged_topics(by_topic):
    merged = {}
    for label, s in by_topic.items():
        m = merged.setdefault(canonical_topic(label), {k: 0.0 for k in METRICS} | {"count": 0})
        for k in METRICS:
            m[k] += s[k] * s["count"]
        m["count"] += s["count"]
    for m in merged.values():
        for k in METRICS:
            m[k] /= m["count"]
    return merged


def to_markdown(df):
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(f"{v:.4f}" if isinstance(v, float) else str(v) for v in row) + " |")
    return "\n".join(lines)


def main():
    scores = json.loads(SCORES_PATH.read_text(encoding="utf-8"))
    names = [n for n in ORDER if n in scores] + [n for n in scores if n not in ORDER]
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    overall = pd.DataFrame([{"Pipeline": n, **{METRICS[k]: scores[n]["total"][k] for k in METRICS}} for n in names])

    by_type = pd.DataFrame([
        {"Type": t, "Name": TYPE_NAMES[t], "n": scores[names[0]]["by_type"][t]["count"],
         **{f"{n} {short}": scores[n]["by_type"][t][k] for n in names
            for k, short in [("answer_score", "Acc"), ("rationale_score", "Rat"), ("ar_score", "AR")]}}
        for t in QUESTION_TYPES])

    topics = {n: merged_topics(scores[n]["by_topic"]) for n in names}
    by_topic = pd.DataFrame([
        {"Topic": t, "n": topics[names[0]][t]["count"],
         **{f"{n} {short}": topics[n][t][k] for n in names
            for k, short in [("answer_score", "Acc"), ("rationale_score", "Rat"), ("ar_score", "AR")]}}
        for t in sorted(topics[names[0]], key=lambda t: -topics[names[0]][t]["count"])])

    overall.to_csv(TABLE_DIR / "overall.csv", index=False)
    by_type.to_csv(TABLE_DIR / "by_question_type.csv", index=False)
    by_topic.to_csv(TABLE_DIR / "by_topic.csv", index=False)
    with pd.ExcelWriter(TABLE_DIR / "RAPTOR_Results_Analysis.xlsx", engine="openpyxl") as writer:
        overall.to_excel(writer, sheet_name="Overall", index=False)
        by_type.to_excel(writer, sheet_name="By question type", index=False)
        by_topic.to_excel(writer, sheet_name="By topic", index=False)
    print(f"Tables written to {TABLE_DIR}\n")

    print("## Overall\n\n" + to_markdown(overall) + "\n")
    ar_type = pd.DataFrame([{"Type": f"{t} ({TYPE_NAMES[t]})", "n": scores[names[0]]["by_type"][t]["count"],
                             **{n: scores[n]["by_type"][t]["ar_score"] for n in names}} for t in QUESTION_TYPES])
    print("## AR score by question type\n\n" + to_markdown(ar_type) + "\n")
    ar_topic = by_topic[["Topic", "n"] + [f"{n} AR" for n in names]].rename(columns={f"{n} AR": n for n in names})
    print("## AR score by topic\n\n" + to_markdown(ar_topic))


if __name__ == "__main__":
    main()

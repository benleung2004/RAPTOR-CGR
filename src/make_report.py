"""Aggregate per-question judgments into scores, tables and a Markdown summary (no API calls).

Besides answer / rationale / AR scores it reports what tells real understanding from guessing:
  - chance level per question type (what random guessing would score)
  - unsupported correct answers: right answer but the judge found the rationale wrong (score 0)
  - option-shuffle consistency: a pipeline run again with MC/MS options in a different order;
    an answer that is correct in both orders cannot come from a positional guess
  - judge agreement: the same run graded by two judge models (exact agreement and Cohen's kappa)

    python src/make_report.py [--judge <model>]

Writes results/scores.json and results/tables/ (CSV, Excel, summary.md).
"""

import argparse
import json
from collections import defaultdict

import pandas as pd

from common import (JUDGE_DIR, LEAKAGE_PATH, QUESTION_TYPES, RAW_DIR, SCORES_PATH, TABLE_DIR, TYPE_NAMES,
                    detect_question_type, load_questions, load_run, read_jsonl)
from scoring import mc_letter, ms_letters, split_prediction

PIPELINE_ORDER = ["baseline", "pure", "cgr", "selfcritique"]
LABELS = {"baseline": "LLM baseline (no retrieval)", "pure": "RAPTOR-RAG", "cgr": "RAPTOR-CGR",
          "selfcritique": "RAPTOR self-critique"}
METRICS = ["answer_score", "rationale_score", "ar_score"]


def mean(rows, key):
    """Mean over rows where the value exists (rationale/AR are None when there is no expert rationale)."""
    vals = [r[key] for r in rows if r.get(key) is not None]
    return sum(vals) / len(vals) if vals else float("nan")


def summarise(rows):
    out = {m: mean(rows, m) for m in METRICS}
    out["count"] = len(rows)
    out["count_with_rationale"] = sum(r.get("rationale_score") is not None for r in rows)
    out["unsupported_correct"] = mean([{"x": float(r["answer_score"] == 1 and r["rationale_score"] == 0)}
                                       for r in rows if r.get("rationale_score") is not None], "x")
    out["no_answer_tag"] = sum(r["no_answer_tag"] for r in rows)
    out["judge_failed"] = sum(r["judge_failed"] for r in rows)
    return out


def chance_levels(questions):
    mc = [1 / len(q["Choices"]) for q in questions if detect_question_type(q) == "MC"]
    return {"MC": sum(mc) / len(mc) if mc else None, "TF": 0.5}


def load_judgments():
    """{judge_model: {run: [rows]}} from results/judgments/<run>__<judge>.jsonl."""
    data = defaultdict(dict)
    for path in sorted(JUDGE_DIR.glob("*.jsonl")):
        run, judge = path.stem.split("__", 1)
        rows = {r["idx"]: r for r in read_jsonl(path)}            # last judgment per question wins
        data[judge][run] = list(rows.values())
    return data


def picked_options(run):
    """{idx: original letter(s) chosen} for MC/MS answers of a run (shuffles mapped back)."""
    picks = {}
    for idx, rec in load_run(RAW_DIR / f"{run}.jsonl").items():
        _, ans = split_prediction(rec["prediction"])
        if rec["type"] == "MC":
            picks[idx] = mc_letter(ans, rec.get("option_map"))
        elif rec["type"] == "MS":
            picks[idx] = frozenset(ms_letters(ans, rec.get("option_map")))
    return picks


def shuffle_consistency(runs, judged):
    rows = []
    for run in runs:
        if "-shuffle" not in run:
            continue
        base = run.split("-shuffle")[0]
        if base not in judged:
            continue
        a = {r["idx"]: r for r in judged[base] if r["type"] in ("MC", "MS")}
        b = {r["idx"]: r for r in judged[run] if r["type"] in ("MC", "MS")}
        common_idx = sorted(set(a) & set(b))
        pa, pb = picked_options(base), picked_options(run)
        rows.append({
            "Pipeline": LABELS.get(base, base), "Shuffled run": run, "MC+MS questions": len(common_idx),
            "Accuracy (original order)": mean([a[i] for i in common_idx], "answer_score"),
            "Accuracy (shuffled)": mean([b[i] for i in common_idx], "answer_score"),
            "Correct in both orders": sum(a[i]["answer_score"] == 1 and b[i]["answer_score"] == 1
                                          for i in common_idx) / max(len(common_idx), 1),
            "Same choice in both orders": sum(pa.get(i) == pb.get(i) for i in common_idx) / max(len(common_idx), 1),
        })
    return rows


def cohen_kappa(x, y):
    labels = sorted(set(x) | set(y))
    n = len(x)
    po = sum(i == j for i, j in zip(x, y)) / n
    pe = sum((x.count(l) / n) * (y.count(l) / n) for l in labels)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def judge_agreement(data):
    rows = []
    judges = sorted(data)
    for i, j1 in enumerate(judges):
        for j2 in judges[i + 1:]:
            for run in sorted(set(data[j1]) & set(data[j2])):
                a = {r["idx"]: r for r in data[j1][run]}
                b = {r["idx"]: r for r in data[j2][run]}
                idx = sorted(k for k in set(a) & set(b) if a[k]["rationale_score"] is not None)
                ra = [a[k]["rationale_score"] for k in idx]
                rb = [b[k]["rationale_score"] for k in idx]
                jidx = [k for k in idx if a[k]["answer_method"] == "judge"]
                aa = [a[k]["answer_score"] for k in jidx]
                ab = [b[k]["answer_score"] for k in jidx]
                rows.append({"Run": run, "Judge 1": j1, "Judge 2": j2, "Questions": len(idx),
                             "Rationale agreement": sum(p == q for p, q in zip(ra, rb)) / max(len(idx), 1),
                             "Rationale kappa": cohen_kappa(ra, rb) if idx else None,
                             "Judged-answer agreement": sum(p == q for p, q in zip(aa, ab)) / max(len(jidx), 1),
                             "Judged-answer kappa": cohen_kappa(aa, ab) if jidx else None})
    return rows


def token_usage(runs):
    rows = []
    for run in runs:
        recs = load_run(RAW_DIR / f"{run}.jsonl").values()
        rows.append({"Run": run, "Questions": len(recs),
                     "Prompt tokens": sum((r.get("usage") or {}).get("prompt_tokens", 0) for r in recs),
                     "Completion tokens": sum((r.get("usage") or {}).get("completion_tokens", 0) for r in recs)})
    return rows


def fmt(v):
    if isinstance(v, float):
        return "–" if v != v else f"{v:.4f}"
    return str(v)


def to_markdown(df):
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    lines += ["| " + " | ".join(fmt(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--judge", help="judge model whose scores are the main tables (default: first)")
    args = parser.parse_args(argv)

    data = load_judgments()
    if not data:
        raise SystemExit("No judgments yet - run src/evaluate.py first.")
    judge = args.judge or sorted(data)[0]
    judged = data[judge]
    runs = sorted(judged, key=lambda r: (PIPELINE_ORDER.index(r.split("-shuffle")[0])
                                         if r.split("-shuffle")[0] in PIPELINE_ORDER else 99, r))
    main_runs = [r for r in runs if "-shuffle" not in r]
    questions = load_questions()

    scores = {}
    for run in runs:
        rows = judged[run]
        scores[run] = {"total": summarise(rows),
                       "by_type": {t: summarise([r for r in rows if r["type"] == t]) for t in QUESTION_TYPES},
                       "by_topic": {t: summarise([r for r in rows if r["topic"] == t])
                                    for t in sorted({r["topic"] for r in rows})}}
    SCORES_PATH.write_text(json.dumps({"judge": judge, "runs": scores}, indent=2), encoding="utf-8")

    label = lambda r: LABELS.get(r, r)
    overall = pd.DataFrame([{"Pipeline": label(r), "n": scores[r]["total"]["count"],
                             "Answer accuracy": scores[r]["total"]["answer_score"],
                             "Rationale score": scores[r]["total"]["rationale_score"],
                             "AR score": scores[r]["total"]["ar_score"],
                             "Unsupported correct": scores[r]["total"]["unsupported_correct"]}
                            for r in main_runs])
    chance = chance_levels(questions)
    by_type = pd.DataFrame([{"Type": f"{t} ({TYPE_NAMES[t]})", "n": scores[main_runs[0]]["by_type"][t]["count"],
                             "Chance accuracy": chance.get(t, float("nan")),
                             **{f"{label(r)} acc": scores[r]["by_type"][t]["answer_score"] for r in main_runs},
                             **{f"{label(r)} AR": scores[r]["by_type"][t]["ar_score"] for r in main_runs}}
                            for t in QUESTION_TYPES])
    topics = sorted(scores[main_runs[0]]["by_topic"], key=lambda t: -scores[main_runs[0]]["by_topic"][t]["count"])
    by_topic = pd.DataFrame([{"Topic": t, "n": scores[main_runs[0]]["by_topic"][t]["count"],
                              **{f"{label(r)} AR": scores[r]["by_topic"].get(t, {}).get("ar_score", float("nan"))
                                 for r in main_runs}} for t in topics])
    consistency = pd.DataFrame(shuffle_consistency(runs, judged))
    agreement = pd.DataFrame(judge_agreement(data))
    usage = pd.DataFrame(token_usage(runs))
    quality = pd.DataFrame([{"Run": r, "No ANSWER tag": scores[r]["total"]["no_answer_tag"],
                             "Judge replies unreadable": scores[r]["total"]["judge_failed"]} for r in runs])

    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    tables = {"overall": overall, "by_question_type": by_type, "by_topic": by_topic,
              "shuffle_consistency": consistency, "judge_agreement": agreement,
              "token_usage": usage, "output_quality": quality}
    with pd.ExcelWriter(TABLE_DIR / "results.xlsx", engine="openpyxl") as xl:
        for name, df in tables.items():
            df.to_csv(TABLE_DIR / f"{name}.csv", index=False)
            df.to_excel(xl, sheet_name=name[:31], index=False)

    md = [f"Judge model: `{judge}`", "", "### Overall", "", to_markdown(overall), "",
          "### By question type", "", to_markdown(by_type), "", "### AR score by topic", "", to_markdown(by_topic)]
    if not consistency.empty:
        md += ["", "### Option-shuffle consistency (MC + MS)", "", to_markdown(consistency)]
    if not agreement.empty:
        md += ["", "### Judge agreement", "", to_markdown(agreement)]
    if LEAKAGE_PATH.exists():
        leak = json.loads(LEAKAGE_PATH.read_text(encoding="utf-8"))
        md += ["", "### Leakage audit", "",
               f"- Expert rationale found verbatim in the retrieved context: "
               f"{leak['rationale_in_context']}/{leak['checked_rationales']} ({leak['rationale_in_context_rate']:.1%})",
               f"- Expert rationale found verbatim anywhere in the corpus: "
               f"{leak['rationale_in_corpus']}/{leak['checked_rationales']} ({leak['rationale_in_corpus_rate']:.1%})",
               f"- Question sentence found in the retrieved context (source passage): "
               f"{leak['question_in_context']}/{leak['checked_questions']} ({leak['question_in_context_rate']:.1%})"]
    md += ["", "### Output quality", "", to_markdown(quality), "", "### Token usage (answering)", "", to_markdown(usage)]
    (TABLE_DIR / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()

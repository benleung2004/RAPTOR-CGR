"""Aggregate per-question judgments into scores, tables and a Markdown summary (no API calls).

Besides answer / rationale / AR scores it reports what tells real understanding from guessing:
  - chance level per question type (what random guessing would score)
  - unsupported correct answers: right answer but the judge found the rationale wrong (score 0)
  - option-shuffle consistency: a pipeline run again with MC/MS options in a different order;
    an answer that is correct in both orders cannot come from a positional guess
  - judge agreement: the same run graded by two judge models (exact agreement and Cohen's kappa)
  - significance: paired bootstrap 95% confidence interval and p-value for each pipeline comparison

    python src/make_report.py [--judge <model>]

Writes results/scores.json and results/tables/ (CSV, Excel, summary.md).
"""

import argparse
import json
from collections import defaultdict

import pandas as pd

from common import (CONTEXTS_PATH, JUDGE_DIR, LEAKAGE_PATH, QUESTION_TYPES, RAW_DIR, SCORES_PATH, TABLE_DIR, TYPE_NAMES,
                    detect_question_type, load_questions, load_run, read_jsonl)
from scoring import mc_letter, ms_letters, split_prediction

PIPELINE_ORDER = ["baseline", "pure", "cgr", "selfcritique"]
LABELS = {"baseline": "LLM baseline (no retrieval)", "pure": "RAPTOR-RAG", "cgr": "RAPTOR-CGR",
          "selfcritique": "RAPTOR self-critique"}
# Without RAPTOR summary trees (retrieval.py --index web) the RAG pipelines must not be called RAPTOR.
WEB_LABELS = {"pure": "Textbook-RAG", "cgr": "Textbook-RAG + CGR", "selfcritique": "Textbook-RAG self-critique"}


def retrieval_index():
    meta = CONTEXTS_PATH.parent / "contexts_meta.json"
    return json.loads(meta.read_text(encoding="utf-8")).get("index", "raptor") if meta.exists() else "raptor"
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


# USD per 1M tokens (input cache miss, output), DeepSeek price list Nov 2026: {model: {period: (in, out)}}.
PRICES = {"deepseek-flash": {"off-peak": (0.15, 0.6), "peak": (0.3, 1.2)},
          "deepseek-v4-pro": {"off-peak": (0.66, 1.98), "peak": (1.32, 3.96)}}


def price(model, period):
    return PRICES.get(model, PRICES["deepseek-flash"])[period]


def token_usage(runs, judged, judge_model):
    """Answering + judging tokens per run, with an upper-bound cost estimate (no cache-hit discount)."""
    rows = []
    for run in runs:
        recs = load_run(RAW_DIR / f"{run}.jsonl").values()
        a_in = sum((r.get("usage") or {}).get("prompt_tokens", 0) for r in recs)
        a_out = sum((r.get("usage") or {}).get("completion_tokens", 0) for r in recs)
        j_in = sum((r.get("judge_tokens") or {}).get("prompt_tokens", 0) for r in judged.get(run, []))
        j_out = sum((r.get("judge_tokens") or {}).get("completion_tokens", 0) for r in judged.get(run, []))
        row = {"Run": run, "Questions": len(recs), "Answer tokens in": a_in, "Answer tokens out": a_out,
               "Judge tokens in": j_in, "Judge tokens out": j_out}
        answer_model = next(iter(recs), {}).get("model", "deepseek-flash")
        for period in ("off-peak", "peak"):
            (ai, ao), (ji, jo) = price(answer_model, period), price(judge_model, period)
            row[f"Est. USD ({period})"] = round((a_in * ai + a_out * ao + j_in * ji + j_out * jo) / 1e6, 4)
        rows.append(row)
    return rows


COMPARISONS = [("pure", "baseline"), ("cgr", "baseline"), ("cgr", "pure"), ("selfcritique", "pure")]
CONDITIONS = {"": "", "-think": " · thinking on"}     # run-name suffix -> label suffix


def run_label(run):
    """'cgr-think' -> 'Textbook-RAG + CGR · thinking on' (shuffle runs keep their name)."""
    if "-shuffle" in run:
        return run
    for suffix, text in CONDITIONS.items():
        if suffix and run.endswith(suffix):
            base = run[: -len(suffix)]
            return LABELS.get(base, base) + text
    return LABELS.get(run, run)


def all_comparisons(judged):
    pairs = [(x + c, y + c) for c in CONDITIONS for x, y in COMPARISONS]
    pairs += [(p + "-think", p) for p in PIPELINE_ORDER]             # effect of thinking mode itself
    return [(x, y) for x, y in pairs if x in judged and y in judged]


def paired_bootstrap(a, b, n_boot=10_000, seed=0):
    """Mean difference a-b over paired questions with a 95% bootstrap CI and two-sided p-value."""
    import numpy as np
    diff = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    rng = np.random.default_rng(seed)
    boots = diff[rng.integers(0, len(diff), size=(n_boot, len(diff)))].mean(axis=1)
    p = 2 * min((boots <= 0).mean(), (boots >= 0).mean())
    return float(diff.mean()), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)), min(1.0, float(p))


def significance(judged):
    """Is pipeline X really better than Y? Paired over the same questions, so question difficulty cancels."""
    rows = []
    for x, y in all_comparisons(judged):
        a = {r["idx"]: r for r in judged[x]}
        b = {r["idx"]: r for r in judged[y]}
        for metric in METRICS:
            idx = [i for i in sorted(set(a) & set(b))
                   if a[i].get(metric) is not None and b[i].get(metric) is not None]
            if not idx:
                continue
            d, lo, hi, p = paired_bootstrap([a[i][metric] for i in idx], [b[i][metric] for i in idx])
            rows.append({"Comparison": f"{run_label(x)} − {run_label(y)}", "Metric": metric,
                         "Questions": len(idx), "Difference": d, "95% CI low": lo, "95% CI high": hi,
                         "p-value": p, "Significant (p<0.05)": "yes" if p < 0.05 else "no"})
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

    if retrieval_index() == "web":
        LABELS.update(WEB_LABELS)
    data = load_judgments()
    if not data:
        raise SystemExit("No judgments yet - run src/evaluate.py first.")
    judge = args.judge or sorted(data)[0]
    judged = data[judge]
    def order(r):
        base = r.split("-shuffle")[0].removesuffix("-think")
        return ("-think" in r, PIPELINE_ORDER.index(base) if base in PIPELINE_ORDER else 99, r)
    runs = sorted(judged, key=order)
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

    label = run_label
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
    signif = pd.DataFrame(significance(judged))
    consistency = pd.DataFrame(shuffle_consistency(runs, judged))
    agreement = pd.DataFrame(judge_agreement(data))
    usage = pd.DataFrame(token_usage(runs, judged, judge))
    quality = pd.DataFrame([{"Run": r, "No ANSWER tag": scores[r]["total"]["no_answer_tag"],
                             "Judge replies unreadable": scores[r]["total"]["judge_failed"]} for r in runs])

    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    tables = {"overall": overall, "significance": signif, "by_question_type": by_type, "by_topic": by_topic,
              "shuffle_consistency": consistency, "judge_agreement": agreement,
              "token_usage": usage, "output_quality": quality}
    with pd.ExcelWriter(TABLE_DIR / "results.xlsx", engine="openpyxl") as xl:
        for name, df in tables.items():
            df.to_csv(TABLE_DIR / f"{name}.csv", index=False)
            df.to_excel(xl, sheet_name=name[:31], index=False)

    index_note = ("Retrieval: textbook chunks only (no RAPTOR summary trees)" if retrieval_index() == "web"
                  else "Retrieval: RAPTOR trees (collapsed tree, top-10 nodes)")
    md = [f"Judge model: `{judge}` · {index_note}", "", "### Overall", "", to_markdown(overall), ""]
    if not signif.empty:
        md += ["### Paired bootstrap (10,000 resamples): is the difference real?", "", to_markdown(signif), ""]
    md += [
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
    md += ["", "### Output quality", "", to_markdown(quality), "", "### Token usage and estimated cost", "", to_markdown(usage)]
    (TABLE_DIR / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()

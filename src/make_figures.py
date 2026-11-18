"""Figures for the evaluation report (PNG, light background).

    python src/make_figures.py --judge deepseek-v4-pro --out evaluation-report/figures

Reads results/judgments/ (v2) and results/v1/scores.json (submitted version).
"""

import argparse
import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from common import JUDGE_DIR, QUESTION_TYPES, ROOT, judge_file, read_jsonl  # noqa: E402

# Validated categorical palette (slots 1-3, light surface); text never uses series colours.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
SURFACE, INK, MUTED, GRID = "#fcfcfb", "#1f1f1e", "#6b6a64", "#e4e3de"
RUNS = ["baseline", "pure", "cgr"]
NAMES = {"baseline": "Baseline (no retrieval)", "pure": "Textbook-RAG", "cgr": "Textbook-RAG + CGR"}
METRICS = [("answer_score", "Answer accuracy"), ("rationale_score", "Rationale score"), ("ar_score", "AR score")]


def style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def load(run, judge):
    return {r["idx"]: r for r in read_jsonl(judge_file(run, judge))}


def boot_ci(values, n=10_000, seed=0):
    v = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, len(v), size=(n, len(v)))].mean(axis=1)
    return v.mean(), np.percentile(means, 2.5), np.percentile(means, 97.5)


def values(rows, metric, idx=None):
    return [r[metric] for i, r in rows.items() if r.get(metric) is not None and (idx is None or i in idx)]


def save(fig, path):
    fig.savefig(path, dpi=200, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


def fig_overall(data, out, suffix="", title=""):
    fig, ax = plt.subplots(figsize=(8, 4.2))
    fig.patch.set_facecolor(SURFACE)
    style(ax)
    width = 0.26
    for k, run in enumerate(RUNS):
        rows = data[run + suffix]
        for m, (metric, _) in enumerate(METRICS):
            mean, lo, hi = boot_ci(values(rows, metric))
            x = m + (k - 1) * (width + 0.02)
            ax.bar(x, mean, width, color=SERIES[k], label=NAMES[run] if m == 0 else None, zorder=2)
            ax.errorbar(x, mean, yerr=[[mean - lo], [hi - mean]], color=INK, capsize=3, linewidth=1, zorder=3)
            ax.text(x, hi + 0.01, f"{mean:.3f}", ha="center", va="bottom", fontsize=7.5, color=INK)
    ax.set_xticks(range(len(METRICS)), [label for _, label in METRICS], color=INK, fontsize=10)
    ax.set_ylim(0.5, 1.0)
    ax.set_ylabel("Mean score (0–1)", color=MUTED, fontsize=9)
    ax.set_title(title, color=INK, fontsize=11, loc="left", pad=26)
    ax.legend(frameon=False, fontsize=9, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, labelcolor=INK)
    save(fig, out)


def fig_differences(data, out):
    """Forest plot of paired differences with 95% bootstrap CIs, both thinking conditions."""
    pairs = [("pure", "baseline", "Textbook-RAG − Baseline"), ("cgr", "baseline", "RAG + CGR − Baseline"),
             ("cgr", "pure", "RAG + CGR − Textbook-RAG")]
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.4), sharey=True)
    fig.patch.set_facecolor(SURFACE)
    for ax, (metric, label) in zip(axes, METRICS):
        style(ax)
        ax.yaxis.grid(False)
        ax.xaxis.grid(True, color=GRID, linewidth=0.8)
        ax.axvline(0, color=MUTED, linewidth=1)
        for c, (suffix, cond) in enumerate([("", "thinking off"), ("-think", "thinking on")]):
            for p, (x, y, _) in enumerate(pairs):
                a, b = data[x + suffix], data[y + suffix]
                idx = [i for i in a if a[i].get(metric) is not None and b.get(i, {}).get(metric) is not None]
                mean, lo, hi = boot_ci([a[i][metric] - b[i][metric] for i in idx])
                yy = p + (c - 0.5) * 0.28
                ax.plot([lo, hi], [yy, yy], color=SERIES[c], linewidth=2, solid_capstyle="round")
                ax.plot(mean, yy, "o", color=SERIES[c], markersize=7, markeredgecolor=SURFACE, markeredgewidth=1.5,
                        label=cond if (p == 0 and metric == "answer_score") else None)
        ax.set_title(label, color=INK, fontsize=10, loc="left")
        ax.set_xlim(-0.12, 0.12)
        ax.set_xlabel("difference in mean score (0–1 scale)", color=MUTED, fontsize=8.5)
    axes[0].set_yticks(range(3), [p[2] for p in pairs], color=INK, fontsize=9)
    axes[0].invert_yaxis()
    fig.legend(frameon=False, fontsize=9, loc="upper right", labelcolor=INK, ncol=2)
    fig.suptitle("Paired differences on the same 300 questions (95% bootstrap CI; crossing 0 = not significant)",
                 color=INK, fontsize=10.5, x=0.02, ha="left", y=1.04)
    save(fig, out)


def fig_by_type(data, out):
    fig, ax = plt.subplots(figsize=(9, 4))
    fig.patch.set_facecolor(SURFACE)
    style(ax)
    width = 0.26
    for k, run in enumerate(RUNS):
        rows = data[run]
        for t_i, t in enumerate(QUESTION_TYPES):
            v = [r["ar_score"] for r in rows.values() if r["type"] == t and r.get("ar_score") is not None]
            x = t_i + (k - 1) * (width + 0.02)
            ax.bar(x, np.mean(v), width, color=SERIES[k], label=NAMES[run] if t_i == 0 else None, zorder=2)
            ax.text(x, np.mean(v) + 0.01, f"{np.mean(v):.2f}", ha="center", va="bottom", fontsize=7, color=INK)
    n = {t: sum(r["type"] == t for r in data["baseline"].values()) for t in QUESTION_TYPES}
    ax.set_xticks(range(5), [f"{t}\n(n={n[t]})" for t in QUESTION_TYPES], color=INK, fontsize=9)
    ax.set_ylim(0.4, 1.0)
    ax.set_ylabel("AR score", color=MUTED, fontsize=9)
    ax.set_title("AR score by question type (thinking off)", color=INK, fontsize=11, loc="left", pad=26)
    ax.legend(frameon=False, fontsize=8.5, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, labelcolor=INK)
    save(fig, out)


def fig_v1_vs_v2(data, out):
    v1 = json.loads((ROOT / "results" / "v1" / "scores.json").read_text())
    v1_gain = {m: v1["RAPTOR-CGR"]["total"][m] - v1["DeepSeek-Baseline"]["total"][m] for m, _ in METRICS}
    v2_gain = {}
    for m, _ in METRICS:
        a, b = data["cgr"], data["baseline"]
        idx = [i for i in a if a[i].get(m) is not None and b[i].get(m) is not None]
        v2_gain[m] = np.mean([a[i][m] - b[i][m] for i in idx])
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    fig.patch.set_facecolor(SURFACE)
    style(ax)
    width = 0.34
    for k, (label, gains) in enumerate([("v1: corpus = benchmark items (answers leaked)", v1_gain),
                                        ("v2: corpus = 20 textbooks (no leakage)", v2_gain)]):
        for m_i, (m, _) in enumerate(METRICS):
            x = m_i + (k - 0.5) * (width + 0.03)
            ax.bar(x, gains[m] * 100, width, color=SERIES[k], label=label if m_i == 0 else None, zorder=2)
            ax.text(x, gains[m] * 100 + (0.4 if gains[m] >= 0 else -0.4), f"{gains[m] * 100:+.1f}",
                    ha="center", va="bottom" if gains[m] >= 0 else "top", fontsize=8, color=INK)
    ax.axhline(0, color=MUTED, linewidth=1)
    ax.set_xticks(range(3), [label for _, label in METRICS], color=INK, fontsize=10)
    ax.set_ylabel("CGR − Baseline (points)", color=MUTED, fontsize=9)
    ax.set_ylim(-4, 19)
    ax.set_title("Gain of the CGR pipeline over the baseline: v1 vs v2", color=INK, fontsize=11, loc="left", pad=44)
    ax.legend(frameon=False, fontsize=8.5, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=1, labelcolor=INK)
    save(fig, out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--judge", default="deepseek-v4-pro")
    parser.add_argument("--out", default=str(ROOT / "evaluation-report" / "figures"))
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    data = {r: load(r, args.judge) for r in [x + s for s in ("", "-think") for x in RUNS]
            if judge_file(r, args.judge).exists()}
    fig_overall(data, out / "fig1_overall.png", "", "Overall scores, 300 questions (thinking off, 95% bootstrap CI)")
    fig_differences(data, out / "fig2_paired_differences.png")
    fig_by_type(data, out / "fig3_ar_by_type.png")
    fig_v1_vs_v2(data, out / "fig4_v1_vs_v2_gain.png")
    fig_overall(data, out / "fig5_overall_thinking_on.png", "-think",
                "Overall scores, 300 questions (thinking on, 95% bootstrap CI)")


if __name__ == "__main__":
    main()

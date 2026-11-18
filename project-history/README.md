# Project history: from proposal to RAPTOR-CGR v2

This document records how the project developed, from the first proposal to the version in this
repository. For each stage it lists the problems found, how serious each one was, and how it was
solved. Sources: the project notes (Notion), the original working folder, its file dates and run logs,
the submitted report, and the code audit done after submission.

**Severity scale**

| Level | Meaning |
|---|---|
| 🔴 Critical | Invalidates a result or a claim, or silently destroys data |
| 🟠 High | Large error in a reported number, or blocks the system from working |
| 🟡 Medium | Biased or fragile measurement, or wrong documentation |
| 🟢 Low | Inconvenience or cosmetic issue |

---

## Timeline

| When | Stage | What happened |
|---|---|---|
| Sep–Oct 2025 | Proposal | DeepSeek API access provided by the department. Topic: *Effective RAG for LLM reasoning in CS exercise answering*, based on GraphRAG and CLR-Bench. |
| 21 Oct 2025 | Proposal revision | Reviewer feedback: the innovation was too vague ("reduce noise"). It was refocused on prompting on top of RAPTOR (chain of thought to filter noisy retrieval and force step-by-step rationales), without changing RAPTOR itself. |
| 22 Dec 2025 – 9 Jan 2026 | Interim | Prototype: CLR-Bench loader, simplified RAPTOR (one K-means level + DeepSeek summaries), DeepSeek client. Tested on a 50-question subset, where the baseline scored about 38%. Interim report and video were due on 9 Jan 2026. |
| Late Feb 2026 | Full baseline | Moved to all 1,018 GraphRAG-Bench questions with the official evaluator. Three evaluation problems found and fixed (P1–P3). |
| 2–4 Mar 2026 | RAPTOR experiments | Six prompt variants on the same RAPTOR tree: Pure, Self-Critique (v2), Self-Consistency (v3), Selective Self-Critique (v5), and **CoT + Context Grounding (v6) = RAPTOR-CGR**. |
| 1–4 Apr 2026 | Final report | Results workbook built; final report submitted on 4 Apr 2026. |
| Nov 2026 | Housekeeping → v1 | Messy working folder cleaned into a reproducible repository, published as v1 (tag `v1-submitted`). |
| Nov 2026 | Audit → v2 | Code audit found the answer leakage (C1) and other issues. v2 redesigned the experiment and fixed them. |
| Nov 2026 | Web tutor | The method turned into a chat website for students, with answers grounded in 20 CS textbooks. |

---

## Stage 1 – Proposal (Sep–Oct 2025)

**Idea.** LLMs answer CS questions fluently but often without sound reasoning. Retrieval (RAG), and
GraphRAG/RAPTOR in particular, can ground the answers. The original contribution was meant to be in
how the LLM *interacts* with the retrieved structure (prompts), not a new graph algorithm.

| # | Problem | Severity | Resolution |
|---|---|---|---|
| S1 | The innovation was described too vaguely ("focus on reducing noise"); reviewers could not see what would be built. | 🟡 | Rewritten as "adaptive chain-of-thought prompts over RAPTOR retrieval, enforcing evidence-based step-by-step rationales", measured with answer accuracy and rationale score. |

## Stage 2 – Interim prototype (Dec 2025 – Jan 2026)

**What was built.** A small pipeline: load CLR-Bench questions, embed text chunks, cluster them once
with K-means, summarise each cluster with DeepSeek, retrieve clusters first and then chunks, and answer
with DeepSeek. It was evaluated on 50 questions with a simple "answer appears in the output" rule.

**Design decision that mattered later.** The plan states: *"use the expert rationales as high-quality
textbook passages, as the RAG knowledge base."* In other words, the retrieval corpus came from the
benchmark items themselves. This is the origin of issue **C1** below.

| # | Problem | Severity | Resolution |
|---|---|---|---|
| S2 | 50-question subset and substring matching gave a rough, noisy estimate (baseline about 38%). | 🟡 | The final stage moved to all 1,018 questions with the official GraphRAG-Bench evaluator. |

## Stage 3 – Full baseline and evaluator problems (Feb 2026)

The first full baseline run reported **64.48%** (over 1,022 records), and the next **66.11%**. Both were wrong for the reasons below.

| # | Problem | Severity | Resolution |
|---|---|---|---|
| P1 | **Missing answer options.** The dataset file used for multiple choice and multi-select held only the letter (e.g. `"B"`), not the options, so the model could not choose and the judge could not verify. Multiple choice scored about 38% and multi-select about 14%, against about 81% and 77% in the paper. | 🟠 | Switched to the GraphRAG-Bench release that includes `Choices` and passed the options to the model. Multiple-choice answer accuracy rose to 92%. |
| P2 | Evaluator crashed (`KeyError: 'FB'`) when it reached a folder that was not a model output. | 🟢 | Folders without all five question types are skipped. |
| P3 | **Multi-select scoring bug.** `set("A, C")` produced `{'A', ',', ' ', 'C'}`, so almost every answer scored 0 (8.56%). | 🟠 | Letters are extracted with a regex before comparing; the score became 75.68%. |
| P4 | DeepSeek judges its own answers (fill-in-blank and open-ended), and DeepSeek-V3 is a much stronger model than the paper's GPT-4o-mini. | 🟡 | Acknowledged as a limitation at the time. Fixed properly in v2 (see C7). |
| P5 | Inconsistent topic labels ("Machine learning" vs "Machine Learning", trailing tab characters…), 31 labels for 16 topics. | 🟢 | Merged for reporting (v1 tables, v2 `TOPIC_ALIASES`). |
| P6 | Resumed runs appended duplicates (1,483 lines for 1,018 questions). | 🟢 | v1/v2 key results by question id and keep the last successful record. |

**Verified baseline (DeepSeek-V3, no retrieval):** answer 0.7652, rationale 0.6282, AR 0.4794. This was
already above every method in the GraphRAG-Bench paper, which used GPT-4o-mini.

## Stage 4 – RAPTOR experiments (2–4 Mar 2026)

All variants shared one cached RAPTOR tree (1,121 leaves, 192 + 43 summary nodes).

| Variant | Answer | Rationale | AR | Note |
|---|---|---|---|---|
| Baseline (no retrieval) | 0.7652 | 0.6282 | 0.4794 | |
| RAPTOR-Pure | 0.7985 | 0.6920 | 0.5707 | standard RAG prompt |
| RAPTOR-SelfCritique (v2) | 0.7706 | 0.6228 | 0.5145 | a second call critiques the first answer; worse |
| Self-Consistency (v3), Selective Self-Critique (v5) | – | – | – | tried, not kept |
| **RAPTOR-CGR (v6)** | **0.8899** | **0.7323** | **0.6390** | CoT + "answer strictly from the context" |

| # | Problem | Severity | Resolution |
|---|---|---|---|
| R1 | Self-critique lowered the scores: the second pass often "corrected" right answers and shortened the rationales. | 🟡 | Dropped in favour of single-pass CoT + grounding (v6). |
| R2 | The automatic evaluator step at the end of the run failed (exit code 2, hard-coded Windows paths). | 🟢 | Evaluated manually; paths removed in v1. |

## Stage 5 – Final report (Apr 2026)

The report presents Baseline → RAPTOR-RAG → RAPTOR-CGR as an ablation, with RAPTOR-CGR best on
every metric (+12.5 / +10.4 / +16.0 points over the baseline).

---

## Stage 6 – Housekeeping → v1 (Nov 2026)

The working folder held 130 files: three near-identical RAPTOR scripts, four converters, backups,
test runs, a 100-question trial, duplicated output folders, and an old CLR-Bench prototype.

| # | Problem | Severity | Resolution |
|---|---|---|---|
| H1 | An API key was stored in a plain `llm.env` file (and also in the project notes). | 🟠 security | Never committed. The key is no longer valid; v1 and v2 read keys from a git-ignored `.env`. Advice: also delete it from the notes. |
| H2 | Hard-coded `C:\Users\…` paths, so the code only ran on one laptop. | 🟡 | Relative paths and command-line options. |
| H3 | Code duplicated across many scripts; it was unclear which file produced which result. | 🟡 | Each raw result file was matched to the evaluated outputs (1,018 out of 1,018 predictions match exactly), then merged into one runner per step. |
| H4 | Results were typed into the Excel script by hand. | 🟢 | Tables are generated from the score files. |

v1 was verified to reproduce exactly what had been evaluated: identical prompts and identical
question/prediction pairs.

## Stage 7 – Audit: what v1 got wrong (Nov 2026)

| # | Problem | Severity | Evidence | Fixed in v2 by |
|---|---|---|---|---|
| **C1** | **Answer leakage.** The RAPTOR corpus was built from the same 1,018 benchmark items, including their **answers and expert rationales**. The CGR prompt even says "quote or paraphrase it directly", and the rationale score compares against that very rationale. The report's §4.1 says test items were excluded, but the code did not exclude them. | 🔴 | Offline retrieval check: the question itself is in the retrieved context for **94.8%** of questions, and its expert rationale for **96.8%**. The RAPTOR gains therefore mostly measure copying from the answer key. | The retrieval corpus is now the **20 GraphRAG-Bench textbooks**; no benchmark item is indexed. `check_leakage.py` audits every question. |
| C2 | The report describes the metrics as substring containment, but the code uses an LLM judge. It describes retrieval as top-3 clusters → top-5 chunks, but the code uses a collapsed tree with top-10 nodes. | 🟡 | Code vs report §4.3/§4.6 | The README documents what the code actually does. |
| C3 | Exact string match: `TRUE` ≠ `True`. | 🟡 | 23 RAPTOR-CGR true/false answers were marked wrong for case alone | Normalised matching. |
| C4 | An empty multi-select answer earned 0.5 (the empty set is a subset). | 🟢 | 2 cases each for Baseline and Pure | Empty = 0. |
| C5 | Only the first line after `ANSWER:` was read, which truncated open-ended answers. | 🟡 | CGR asks for "comprehensive" open-ended answers | The whole answer is parsed; markdown and "Final answer:" tags are handled. |
| C6 | Uncontrolled ablation: each pipeline used a different prompt format and temperature (0.2 / 0 / 0.2). | 🟡 | Report Table 1 | One shared format at temperature 0, each step adding exactly one ingredient. |
| C7 | Self-judging; the judge never saw the question; scores were aggregated only, so no per-question audit was possible. | 🟡 | Evaluator code | Configurable judge model (another model family recommended), question included, JSON replies, every judgment saved, agreement and Cohen's κ between two judges. |
| C8 | No way to tell real understanding from a lucky guess. | 🟡 | – | Chance levels, unsupported-correct rate, and an **option-shuffle** re-test of multiple-choice and multi-select questions. |
| C9 | No significance testing, so a 2–3 point difference could be noise. | 🟡 | – | Paired bootstrap 95% confidence intervals and p-values. |
| C10 | 18 benchmark items have no expert rationale, yet were graded on rationale. | 🟢 | – | These count for answer accuracy only. |

## Stage 8 – Building v2 and the web tutor: problems found on the way (Nov 2026)

| # | Problem | Severity | Fix |
|---|---|---|---|
| W1 | **Text-cleaning bug.** The HTML-tag regex `<[^>]+>` deleted everything between any `<` and `>` (for example in `a < b … c > d`), so CLRS lost **73%** of its text (2.2 M characters). It affected both the v2 RAPTOR trees and the web index. | 🔴 | A real-tag-only regex, shared by both; tests check that every textbook keeps more than 80% of its text. |
| W2 | RAPTOR's threaded tree builder silently drops a cluster whose summary call fails. | 🟡 | The summariser never raises: it retries, falls back to the cluster text, and counts the fallbacks. |
| W3 | UMAP (numba) crashes when two books are clustered in parallel threads. | 🟡 | Books are built one after another; summaries still run in parallel. |
| W4 | **DeepSeek models now "think" by default.** The hidden reasoning used up `max_tokens`, so 100-token summaries and judge replies came back empty, and answers were slower. | 🟠 | Thinking is off by default for DeepSeek (as with v1's `deepseek-chat`) and configurable in `.env`; verified with live calls. |
| W5 | Groq (and OpenAI and Gemini) block Hong Kong IPs, so the planned free provider was unusable. | 🟠 | DeepSeek is the default; any OpenAI-compatible fallback can be added. |
| W6 | PDF-extraction garbage chunks ranked highly, and Chinese questions matched English text less reliably. | 🟡 | Garbled chunks are filtered; English technical terms in the question (e.g. "ACID", "TCP") get a ranking bonus; exercise sections rank below explanations. |
| W7 | The browser kept a stale `app.js` after updates, and the Send button state was wrong after an answer. | 🟢 | Static files are revalidated on every load; state order fixed. |

---

## Where the project stands

| Part | Status |
|---|---|
| v1 (submitted) | Code and results reproducible (`results/v1/`, tag `v1-submitted`). The RAPTOR numbers are inflated by C1 and should not be read as a measure of reasoning ability. |
| v2 experiment | Code complete; 59 offline tests, including an end-to-end run with a fake LLM. **Not run yet** (≈ 24,500 API calls, about US$4–8): see *Future work* in the main README. |
| Web tutor | Works locally with DeepSeek: 49,383 textbook chunks, Chinese/English questions, first words in about 0.7–1.5 s and full answers in 2.8–5.7 s (measured on 7 questions), with citations, maths and pseudocode. |

## Lessons

1. **Keep the knowledge source and the test set apart, and check it with code.** The leakage came from one reasonable-sounding design decision at the interim stage and was never tested.
2. **Read the raw outputs, not only the averages.** P1, P3, C3 and W4 were all visible in individual records long before they showed up in a total.
3. **Change one thing at a time.** A fair ablation needs a shared prompt format and temperature.
4. **Report uncertainty.** Without confidence intervals, small gains cannot be trusted.
5. **Test the data pipeline, not just the model code.** W1 silently removed most of a textbook.

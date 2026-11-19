# Project structure and flowcharts

This page shows every folder and file in the repository, what each one is for, and how they connect.
For how the project developed and what went wrong along the way, see
[project-history](../project-history/README.md).

## 1. Folders and files

```
RAPTOR-CGR/
├── README.md                     overview, results, how to run
├── LICENSE                       MIT (code only)
├── requirements.txt              Python packages (tested with Python 3.11)
├── .env.example                  template for API keys and options (the real .env is never committed)
├── .gitignore
├── .claude/launch.json           dev-server shortcut (demo mode)
│
├── src/                          all Python code (run from the repository root)
│   ├── common.py                 paths, settings, dataset loading, question types, option shuffling,
│   │                             textbook cleaning (clean_markdown, fix_pdf_artifacts), split_chunks
│   ├── llm.py                    OpenAI-compatible client: retries, token counting, provider options
│   ├── prompts.py                every prompt: baseline, RAG, CGR, self-critique, judge
│   ├── scoring.py                answer parsing, exact/normalised scoring, AR score
│   │
│   ├── download_data.py          download the 20 textbooks; check the 1,018 questions match the release
│   ├── build_tree.py             RAPTOR tree per textbook (paid: ~13,600 summaries) -> data/trees, data/index
│   ├── build_web_index.py        free multilingual chunk index -> data/web_index
│   ├── retrieval.py              retrieved context for every question -> results/contexts.jsonl
│   │                             (--index raptor | web)
│   ├── check_leakage.py          proves no benchmark answer key is retrievable -> results/leakage.json
│   ├── make_sample.py            stratified question sample -> data/samples/
│   ├── run_pipeline.py           answer questions: baseline | pure | cgr | selfcritique (+ --sample, --shuffle-seed)
│   ├── evaluate.py               LLM-judge every answer -> results/judgments/
│   ├── make_report.py            scores, tables, significance, guessing checks, cost -> results/
│   ├── make_figures.py           report figures (PNG) -> evaluation-report/figures/
│   └── chat_engine.py            web tutor engine: search, grounded prompt, streaming, fallback, deep mode
│
├── web/                          the CS Textbook Tutor website
│   ├── server.py                 FastAPI: /api/chat (streaming), /read, /api/context, /books, rate limit
│   └── static/
│       ├── index.html, app.js    chat page
│       ├── read.html, read.js    "Open in textbook" reader
│       ├── render.js             Markdown + KaTeX maths rendering (shared)
│       └── style.css             light/dark, mobile
│
├── raptor/                       RAPTOR library (vendored from parthsarthi03/raptor, MIT, unmodified)
│
├── data/
│   ├── graphrag_bench.jsonl      the 1,018 GraphRAG-Bench questions (answer + expert rationale)
│   ├── book_titles.json          names of the 20 textbooks
│   ├── textbooks/                the 20 textbooks (Markdown, from GraphRAG-Bench)
│   ├── web_index/                55,539 chunks + embeddings used by the tutor and the budget evaluation
│   ├── samples/                  question samples (e.g. sample_300_seed42.json)
│   ├── trees/, index/            RAPTOR trees and flat index (built by build_tree.py; not committed)
│
├── results/
│   ├── contexts.jsonl            retrieved context per question (current run)
│   ├── leakage.json              leakage audit
│   ├── contexts_meta.json        which index produced contexts.jsonl (web or raptor)
│   ├── raw/                      answers of the 300-question run (thinking off; *-think = thinking on)
│   ├── judgments/                per-question scores from the deepseek-v4-pro judge
│   ├── tables/, scores.json      all result tables (CSV, Excel, summary.md)
│   └── v1/                       everything from the submitted version (tag v1-submitted)
│       ├── raw/                  model outputs of the 4 v1 pipelines
│       ├── eval_inputs/          evaluator-format questions and predictions
│       ├── scores.json, tables/  the numbers in the final report
│       └── question_tree.pkl     v1 RAPTOR tree (built from benchmark items: the leakage)
│
├── tests/                        76 offline tests (no API key needed)
│   ├── test_scoring.py           parsing, normalisation, MS partial credit, shuffles, AR
│   ├── test_cleaning.py          cleaning keeps every textbook; chunking keeps text; PDF artifacts
│   ├── test_retrieval.py         fast retriever == RAPTOR's own retriever
│   ├── test_llm.py               provider options (thinking mode) reach the API
│   ├── test_report.py            bootstrap, kappa, stratified sampling
│   ├── test_web.py               tutor engine + HTTP API + reader + deep mode
│   └── test_end_to_end.py        whole v2 workflow with a fake LLM
│
├── comparisons/                  tutor vs other AI assistants
│   └── shortest-paths/           vs Perplexity (Claude Sonnet 5.5 reasoning), with verify.py
│
├── evaluation-report/            leak-free 300-question evaluation: academic write-up + figures
├── project-history/              every stage, problem, severity and fix (proposal -> v2)
├── project-structure/            this page
└── docs/                         final report, presentation, summary
```

## 2. The whole project at a glance

```mermaid
flowchart LR
    P[Proposal<br/>Sep–Oct 2025] --> I[Interim prototype<br/>Dec 2025]
    I --> B[Full baseline +<br/>evaluator fixes<br/>Feb 2026]
    B --> R[RAPTOR experiments<br/>v2…v6 = CGR<br/>Mar 2026]
    R --> F[Final report<br/>4 Apr 2026]
    F --> V1[Clean repo = v1<br/>Nov 2026]
    V1 --> A{Audit}
    A -->|answer leakage<br/>+ 9 other issues| V2[v2 research code<br/>textbook corpus]
    V2 --> W[Web tutor]
    W --> C[Comparison with<br/>Perplexity]
    C --> D[Deep mode +<br/>textbook links]
    V2 --> E[Budget evaluation<br/>300 questions]
```

## 3. Research pipeline (v2)

```mermaid
flowchart TD
    HF[(GraphRAG-Bench<br/>Hugging Face)] -->|download_data.py| TB[data/textbooks<br/>20 books]
    HF --> Q[data/graphrag_bench.jsonl<br/>1,018 questions]

    TB -->|clean_markdown + split_chunks| CH[chunks]
    CH -->|build_tree.py<br/>UMAP + GMM + LLM summaries| RI[(RAPTOR index<br/>paid)]
    CH -->|build_web_index.py<br/>multilingual-e5| WI[(web index<br/>free)]

    Q --> S[make_sample.py<br/>optional sample]
    RI -->|retrieval.py --index raptor| CTX[results/contexts.jsonl]
    WI -->|retrieval.py --index web| CTX
    CTX --> LK[check_leakage.py<br/>no answer key in context]

    Q --> RP[run_pipeline.py]
    S --> RP
    CTX --> RP
    RP -->|baseline · pure · cgr · selfcritique<br/>+ shuffle run| RAW[results/raw/*.jsonl]
    RAW -->|evaluate.py<br/>exact match + LLM judge| J[results/judgments/*.jsonl]
    J -->|make_report.py| REP[scores.json + tables<br/>significance · guessing · cost]
```

**Controlled ablation:** every pipeline uses the same output format and temperature 0, and each step
adds exactly one ingredient.

```mermaid
flowchart LR
    B0[baseline<br/>question only] -->|+ textbook context| P1[pure<br/>RAPTOR-RAG]
    P1 -->|+ chain of thought<br/>+ context grounding| C1[cgr<br/>RAPTOR-CGR]
    P1 -->|+ second critique call| S1[selfcritique<br/>extra ablation]
```

## 4. Scoring one answer

```mermaid
flowchart TD
    A[model output<br/>RATIONALE: … ANSWER: …] --> SP[split_prediction]
    SP --> T{question type}
    T -->|MC| MC[first option letter<br/>mapped back if shuffled]
    T -->|TF| TF[true / false, any case]
    T -->|MS| MS[letter set: all = 1,<br/>correct subset = 0.5, empty = 0]
    T -->|FB| FB{normalised exact match?}
    FB -->|yes| ONE[1]
    FB -->|no| JA[LLM judge 0 / 0.5 / 1]
    T -->|OE| JA
    SP --> JR[LLM judge: rationale vs<br/>expert rationale 0 / 0.5 / 1]
    MC & TF & MS & ONE & JA & JR --> AR[AR score<br/>GraphRAG-Bench table]
```

## 5. Web tutor: one question

```mermaid
sequenceDiagram
    participant U as Student (browser)
    participant S as web/server.py
    participant E as chat_engine.py
    participant X as web index (local)
    participant L as DeepSeek API

    U->>S: POST /api/chat {question, history, mode}
    S->>S: validate + rate limit
    S->>E: answer()
    E->>E: cache hit? → answer in ~0 s
    E->>X: embed question (multilingual-e5) + search 55,539 chunks
    X-->>E: top 6 passages (~20 ms)
    E-->>U: event: sources (cards + "Open in textbook")
    E->>L: one streamed call (fast: thinking off · deep: thinking on)
    L-->>E: answer tokens
    E-->>U: event: delta … (rendered live: Markdown, KaTeX, code)
    E-->>U: event: done (time, model, mode, truncated?)
    U->>S: GET /read?chunk=ID (optional)
    S-->>U: cited passage + surrounding text + full book link
```

## 6. Budget evaluation (300 questions, about US$0.3–0.7)

```mermaid
flowchart LR
    M[make_sample.py<br/>300 stratified] --> RW[retrieval.py --index web<br/>free]
    RW --> LK[check_leakage.py --index web]
    M --> B[run baseline]
    RW --> P[run pure]
    RW --> C[run cgr]
    B & P & C --> EV[evaluate.py]
    EV --> RP[make_report.py<br/>accuracy table + significance + cost]
```

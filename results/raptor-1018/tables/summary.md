Judge model: `deepseek-v4-pro` · Retrieval: RAPTOR trees (collapsed tree, top-10 nodes)

### Overall

| Pipeline | n | Answer accuracy | Rationale score | AR score | Unsupported correct |
|---|---|---|---|---|---|
| LLM baseline (no retrieval) | 1018 | 0.8861 | 0.8725 | 0.8383 | 0.0140 |
| RAPTOR-RAG | 1018 | 0.8880 | 0.8625 | 0.8195 | 0.0170 |
| RAPTOR-CGR | 1018 | 0.8954 | 0.8635 | 0.8273 | 0.0130 |

### Paired bootstrap (10,000 resamples): is the difference real?

| Comparison | Metric | Questions | Difference | 95% CI low | 95% CI high | p-value | Holm p | Significant (Holm, 0.05) |
|---|---|---|---|---|---|---|---|---|
| RAPTOR-RAG − LLM baseline (no retrieval) | answer_score | 1018 | 0.0020 | -0.0152 | 0.0196 | 0.8528 | 1.0000 | no |
| RAPTOR-RAG − LLM baseline (no retrieval) | rationale_score | 1000 | -0.0100 | -0.0280 | 0.0090 | 0.3020 | 1.0000 | no |
| RAPTOR-RAG − LLM baseline (no retrieval) | ar_score | 1000 | -0.0187 | -0.0398 | 0.0030 | 0.0924 | 0.8316 | no |
| RAPTOR-CGR − LLM baseline (no retrieval) | answer_score | 1018 | 0.0093 | -0.0074 | 0.0265 | 0.2970 | 1.0000 | no |
| RAPTOR-CGR − LLM baseline (no retrieval) | rationale_score | 1000 | -0.0090 | -0.0275 | 0.0090 | 0.3430 | 1.0000 | no |
| RAPTOR-CGR − LLM baseline (no retrieval) | ar_score | 1000 | -0.0110 | -0.0323 | 0.0097 | 0.2998 | 1.0000 | no |
| RAPTOR-CGR − RAPTOR-RAG | answer_score | 1018 | 0.0074 | -0.0054 | 0.0196 | 0.2692 | 1.0000 | no |
| RAPTOR-CGR − RAPTOR-RAG | rationale_score | 1000 | 0.0010 | -0.0145 | 0.0160 | 0.9428 | 1.0000 | no |
| RAPTOR-CGR − RAPTOR-RAG | ar_score | 1000 | 0.0077 | -0.0085 | 0.0238 | 0.3790 | 1.0000 | no |

### By question type

| Type | n | Chance accuracy | LLM baseline (no retrieval) acc | RAPTOR-RAG acc | RAPTOR-CGR acc | LLM baseline (no retrieval) AR | RAPTOR-RAG AR | RAPTOR-CGR AR |
|---|---|---|---|---|---|---|---|---|
| FB (Fill-in-blank) | 105 | – | 0.8810 | 0.8905 | 0.9238 | 0.8357 | 0.8833 | 0.9095 |
| MC (Multiple choice) | 217 | 0.2500 | 0.9124 | 0.9217 | 0.9032 | 0.8744 | 0.8593 | 0.8651 |
| MS (Multi-select) | 111 | – | 0.7748 | 0.7883 | 0.8108 | 0.7410 | 0.6757 | 0.6914 |
| OE (Open-ended) | 269 | – | 0.9164 | 0.8736 | 0.8866 | 0.8189 | 0.7425 | 0.7472 |
| TF (True/False) | 316 | 0.5000 | 0.8829 | 0.9114 | 0.9177 | 0.8660 | 0.8890 | 0.8914 |

### AR score by topic

| Topic | n | LLM baseline (no retrieval) AR | RAPTOR-RAG AR | RAPTOR-CGR AR |
|---|---|---|---|---|
| Data structures and algorithms | 121 | 0.7190 | 0.7851 | 0.7893 |
| Computer networks | 119 | 0.8692 | 0.9065 | 0.8972 |
| Cybersecurity | 112 | 0.8795 | 0.7567 | 0.8125 |
| Information retrieval | 92 | 0.8614 | 0.8071 | 0.7880 |
| Artificial intelligence introduction | 87 | 0.8563 | 0.8707 | 0.8563 |
| Machine learning | 81 | 0.8656 | 0.8000 | 0.8156 |
| Data science and big data | 66 | 0.7056 | 0.7823 | 0.7984 |
| Mathematics | 62 | 0.9153 | 0.8387 | 0.8468 |
| Computer architecture | 57 | 0.8421 | 0.8860 | 0.9035 |
| Human-computer interaction | 50 | 0.8200 | 0.7200 | 0.7500 |
| Computer vision | 44 | 0.9261 | 0.8182 | 0.7841 |
| NLP | 37 | 0.9324 | 0.7905 | 0.8243 |
| Mathematics (for computer science and AI) | 34 | 0.9412 | 0.8971 | 0.9118 |
| Programming fundamentals | 22 | 0.8182 | 0.9318 | 0.9318 |
| Database systems | 15 | 0.7857 | 0.7857 | 0.8571 |
| Programming languages and compilers | 8 | 1.0000 | 1.0000 | 1.0000 |
| Operating systems | 7 | 0.2857 | 0.5000 | 0.4286 |
| Ethics (of computer science and AI) | 4 | 0.2500 | 0.7500 | 0.5000 |

### Option-shuffle consistency (MC + MS)

| Pipeline | Shuffled run | MC+MS questions | Accuracy (original order) | Accuracy (shuffled) | Correct in both orders | Same choice in both orders |
|---|---|---|---|---|---|---|
| RAPTOR-CGR | cgr-shuffle1 | 328 | 0.8720 | 0.8598 | 0.8049 | 0.9024 |

### Leakage audit

- Expert rationale found verbatim in the retrieved context: 8/986 (0.8%)
- Expert rationale found verbatim anywhere in the corpus: 14/986 (1.4%)
- Question sentence found in the retrieved context (source passage): 220/1003 (21.9%)

### Output quality

| Run | No ANSWER tag | Judge replies unreadable |
|---|---|---|
| baseline | 1 | 0 |
| pure | 0 | 0 |
| cgr | 1 | 0 |
| cgr-shuffle1 | 1 | 0 |

### Token usage and estimated cost

| Run | Questions | Answer tokens in | Answer tokens out | Judge tokens in | Judge tokens out | Est. USD (off-peak) | Est. USD (peak) |
|---|---|---|---|---|---|---|---|
| baseline | 1018 | 162998 | 135985 | 383355 | 8116 | 0.3751 | 0.7502 |
| pure | 1018 | 1014066 | 123267 | 368411 | 8110 | 0.4853 | 0.9706 |
| cgr | 1018 | 1118920 | 187437 | 432476 | 8112 | 0.5818 | 1.1636 |
| cgr-shuffle1 | 328 | 369552 | 47480 | 0 | 0 | 0.0839 | 0.1678 |

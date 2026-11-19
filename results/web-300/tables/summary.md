Judge model: `deepseek-v4-pro` · Retrieval: textbook chunks only (no RAPTOR summary trees)

### Overall

| Pipeline | n | Answer accuracy | Rationale score | AR score | Unsupported correct |
|---|---|---|---|---|---|
| LLM baseline (no retrieval) | 300 | 0.8567 | 0.8627 | 0.8288 | 0.0102 |
| Textbook-RAG | 300 | 0.8667 | 0.8627 | 0.8136 | 0.0068 |
| Textbook-RAG + CGR | 300 | 0.8633 | 0.8390 | 0.8144 | 0.0136 |
| LLM baseline (no retrieval) · thinking on | 300 | 0.8550 | 0.8169 | 0.7712 | 0.0644 |
| Textbook-RAG · thinking on | 300 | 0.8917 | 0.8492 | 0.7958 | 0.0610 |
| Textbook-RAG + CGR · thinking on | 300 | 0.8850 | 0.8390 | 0.8051 | 0.0441 |

### Paired bootstrap (10,000 resamples): is the difference real?

| Comparison | Metric | Questions | Difference | 95% CI low | 95% CI high | p-value | Holm p | Significant (Holm, 0.05) |
|---|---|---|---|---|---|---|---|---|
| Textbook-RAG − LLM baseline (no retrieval) | answer_score | 300 | 0.0100 | -0.0217 | 0.0417 | 0.5584 | 1.0000 | no |
| Textbook-RAG − LLM baseline (no retrieval) | rationale_score | 295 | 0.0000 | -0.0322 | 0.0339 | 1.0000 | 1.0000 | no |
| Textbook-RAG − LLM baseline (no retrieval) | ar_score | 295 | -0.0153 | -0.0551 | 0.0246 | 0.4568 | 1.0000 | no |
| Textbook-RAG + CGR − LLM baseline (no retrieval) | answer_score | 300 | 0.0067 | -0.0250 | 0.0400 | 0.7178 | 1.0000 | no |
| Textbook-RAG + CGR − LLM baseline (no retrieval) | rationale_score | 295 | -0.0237 | -0.0593 | 0.0119 | 0.2152 | 1.0000 | no |
| Textbook-RAG + CGR − LLM baseline (no retrieval) | ar_score | 295 | -0.0144 | -0.0559 | 0.0271 | 0.5136 | 1.0000 | no |
| Textbook-RAG + CGR − Textbook-RAG | answer_score | 300 | -0.0033 | -0.0267 | 0.0183 | 0.8340 | 1.0000 | no |
| Textbook-RAG + CGR − Textbook-RAG | rationale_score | 295 | -0.0237 | -0.0492 | -0.0017 | 0.0482 | 0.4338 | no |
| Textbook-RAG + CGR − Textbook-RAG | ar_score | 295 | 0.0008 | -0.0288 | 0.0305 | 0.9648 | 1.0000 | no |
| Textbook-RAG · thinking on − LLM baseline (no retrieval) · thinking on | answer_score | 300 | 0.0367 | 0.0083 | 0.0650 | 0.0110 | 0.0990 | no |
| Textbook-RAG · thinking on − LLM baseline (no retrieval) · thinking on | rationale_score | 295 | 0.0322 | -0.0119 | 0.0780 | 0.1636 | 0.9816 | no |
| Textbook-RAG · thinking on − LLM baseline (no retrieval) · thinking on | ar_score | 295 | 0.0246 | -0.0195 | 0.0703 | 0.2786 | 1.0000 | no |
| Textbook-RAG + CGR · thinking on − LLM baseline (no retrieval) · thinking on | answer_score | 300 | 0.0300 | 0.0000 | 0.0617 | 0.0560 | 0.4480 | no |
| Textbook-RAG + CGR · thinking on − LLM baseline (no retrieval) · thinking on | rationale_score | 295 | 0.0220 | -0.0220 | 0.0661 | 0.3242 | 1.0000 | no |
| Textbook-RAG + CGR · thinking on − LLM baseline (no retrieval) · thinking on | ar_score | 295 | 0.0339 | -0.0110 | 0.0788 | 0.1340 | 0.9380 | no |
| Textbook-RAG + CGR · thinking on − Textbook-RAG · thinking on | answer_score | 300 | -0.0067 | -0.0233 | 0.0083 | 0.4598 | 1.0000 | no |
| Textbook-RAG + CGR · thinking on − Textbook-RAG · thinking on | rationale_score | 295 | -0.0102 | -0.0458 | 0.0254 | 0.6140 | 1.0000 | no |
| Textbook-RAG + CGR · thinking on − Textbook-RAG · thinking on | ar_score | 295 | 0.0093 | -0.0271 | 0.0458 | 0.6324 | 1.0000 | no |
| LLM baseline (no retrieval) · thinking on − LLM baseline (no retrieval) | answer_score | 300 | -0.0017 | -0.0333 | 0.0300 | 0.9560 | 1.0000 | no |
| LLM baseline (no retrieval) · thinking on − LLM baseline (no retrieval) | rationale_score | 295 | -0.0458 | -0.0881 | -0.0034 | 0.0396 | 0.2772 | no |
| LLM baseline (no retrieval) · thinking on − LLM baseline (no retrieval) | ar_score | 295 | -0.0576 | -0.1017 | -0.0144 | 0.0092 | 0.0828 | no |
| Textbook-RAG · thinking on − Textbook-RAG | answer_score | 300 | 0.0250 | 0.0017 | 0.0483 | 0.0344 | 0.2752 | no |
| Textbook-RAG · thinking on − Textbook-RAG | rationale_score | 295 | -0.0136 | -0.0492 | 0.0220 | 0.4764 | 1.0000 | no |
| Textbook-RAG · thinking on − Textbook-RAG | ar_score | 295 | -0.0178 | -0.0559 | 0.0212 | 0.3788 | 1.0000 | no |
| Textbook-RAG + CGR · thinking on − Textbook-RAG + CGR | answer_score | 300 | 0.0217 | -0.0017 | 0.0467 | 0.0920 | 0.5520 | no |
| Textbook-RAG + CGR · thinking on − Textbook-RAG + CGR | rationale_score | 295 | 0.0000 | -0.0339 | 0.0339 | 1.0000 | 1.0000 | no |
| Textbook-RAG + CGR · thinking on − Textbook-RAG + CGR | ar_score | 295 | -0.0093 | -0.0449 | 0.0263 | 0.6356 | 1.0000 | no |

### By question type

| Type | n | Chance accuracy | LLM baseline (no retrieval) acc | Textbook-RAG acc | Textbook-RAG + CGR acc | LLM baseline (no retrieval) · thinking on acc | Textbook-RAG · thinking on acc | Textbook-RAG + CGR · thinking on acc | LLM baseline (no retrieval) AR | Textbook-RAG AR | Textbook-RAG + CGR AR | LLM baseline (no retrieval) · thinking on AR | Textbook-RAG · thinking on AR | Textbook-RAG + CGR · thinking on AR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FB (Fill-in-blank) | 31 | – | 0.9032 | 0.8871 | 0.8871 | 0.8871 | 0.9032 | 0.8710 | 0.8710 | 0.8710 | 0.8710 | 0.5806 | 0.7742 | 0.6129 |
| MC (Multiple choice) | 64 | 0.2500 | 0.8750 | 0.8438 | 0.8438 | 0.8594 | 0.9062 | 0.9062 | 0.8633 | 0.8438 | 0.8203 | 0.8281 | 0.8359 | 0.8438 |
| MS (Multi-select) | 33 | – | 0.6818 | 0.7424 | 0.6818 | 0.6970 | 0.7576 | 0.6818 | 0.7045 | 0.6364 | 0.6288 | 0.6136 | 0.6970 | 0.6288 |
| OE (Open-ended) | 79 | – | 0.9051 | 0.8987 | 0.9241 | 0.9241 | 0.9051 | 0.9367 | 0.8279 | 0.7727 | 0.8117 | 0.8149 | 0.7857 | 0.8312 |
| TF (True/False) | 93 | 0.5000 | 0.8495 | 0.8925 | 0.8817 | 0.8387 | 0.9140 | 0.9032 | 0.8361 | 0.8722 | 0.8611 | 0.8167 | 0.8194 | 0.8861 |

### AR score by topic

| Topic | n | LLM baseline (no retrieval) AR | Textbook-RAG AR | Textbook-RAG + CGR AR | LLM baseline (no retrieval) · thinking on AR | Textbook-RAG · thinking on AR | Textbook-RAG + CGR · thinking on AR |
|---|---|---|---|---|---|---|---|
| Data structures and algorithms | 37 | 0.7297 | 0.7027 | 0.6892 | 0.6959 | 0.6351 | 0.7297 |
| Computer networks | 36 | 0.9242 | 0.8939 | 0.9394 | 0.8636 | 0.9091 | 0.9394 |
| Information retrieval | 32 | 0.8281 | 0.7344 | 0.7500 | 0.7031 | 0.7188 | 0.6016 |
| Cybersecurity | 29 | 0.8276 | 0.8276 | 0.8103 | 0.8017 | 0.7759 | 0.8103 |
| Artificial intelligence introduction | 23 | 0.7826 | 0.8913 | 0.8043 | 0.7391 | 0.8478 | 0.8696 |
| Machine learning | 22 | 0.9545 | 0.9545 | 0.8636 | 0.7727 | 0.8409 | 0.8295 |
| Computer architecture | 20 | 0.7750 | 0.9500 | 0.9500 | 0.7875 | 0.9625 | 0.9500 |
| Data science and big data | 19 | 0.7778 | 0.7778 | 0.8056 | 0.6667 | 0.8333 | 0.8056 |
| Computer vision | 18 | 0.8750 | 0.6944 | 0.7222 | 0.8194 | 0.6944 | 0.7222 |
| Mathematics | 18 | 0.9444 | 0.9444 | 0.9722 | 0.9722 | 0.8611 | 0.8611 |
| NLP | 11 | 1.0000 | 0.7727 | 0.9091 | 0.9091 | 0.8182 | 0.8182 |
| Human-computer interaction | 8 | 0.6562 | 0.6875 | 0.5938 | 0.6250 | 0.6250 | 0.6875 |
| Mathematics (for computer science and AI) | 7 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Programming fundamentals | 6 | 0.7500 | 0.9167 | 0.9167 | 0.5833 | 0.8333 | 0.8333 |
| Database systems | 5 | 0.7500 | 0.7500 | 0.7500 | 0.7500 | 0.7500 | 0.8750 |
| Operating systems | 5 | 0.5000 | 0.1000 | 0.1000 | 0.2000 | 0.5000 | 0.5000 |
| Ethics (of computer science and AI) | 2 | 0.0000 | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Programming languages and compilers | 2 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

### Leakage audit

- Expert rationale found verbatim in the retrieved context: 10/986 (1.0%)
- Expert rationale found verbatim anywhere in the corpus: 13/986 (1.3%)
- Question sentence found in the retrieved context (source passage): 253/1003 (25.2%)

### Output quality

| Run | No ANSWER tag | Judge replies unreadable |
|---|---|---|
| baseline | 0 | 0 |
| pure | 1 | 0 |
| cgr | 1 | 0 |
| baseline-think | 0 | 0 |
| pure-think | 0 | 0 |
| cgr-think | 0 | 0 |

### Token usage and estimated cost

| Run | Questions | Answer tokens in | Answer tokens out | Judge tokens in | Judge tokens out | Est. USD (off-peak) | Est. USD (peak) |
|---|---|---|---|---|---|---|---|
| baseline | 300 | 47621 | 39610 | 114169 | 2394 | 0.1110 | 0.2220 |
| pure | 300 | 399918 | 40128 | 114503 | 2408 | 0.1644 | 0.3288 |
| cgr | 300 | 430818 | 69628 | 143542 | 2370 | 0.2058 | 0.4117 |
| baseline-think | 300 | 55121 | 155696 | 97887 | 2272 | 0.1708 | 0.3416 |
| pure-think | 300 | 407418 | 147974 | 99216 | 2272 | 0.2199 | 0.4398 |
| cgr-think | 300 | 438318 | 181757 | 110205 | 2330 | 0.2522 | 0.5043 |

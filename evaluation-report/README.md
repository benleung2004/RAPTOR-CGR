# Evaluation reports

| Report | Questions | Retrieval | Main finding |
|---|---|---|---|
| **[Final: RAPTOR on all 1,018 questions](raptor-1018/README.md)** | 1,018 | RAPTOR trees over the 20 textbooks | No significant overall difference between Baseline, RAPTOR-RAG and RAPTOR-CGR; retrieval helps fill-in-blank and true/false questions and significantly hurts open-ended answers (AR −7.6, Holm p = 0.012) |
| [Budget study: textbook chunks on 300 questions](web-300/README.md) | 300 (stratified) | textbook chunks, no RAPTOR summaries | Same conclusion on a smaller sample; also a thinking-mode experiment |

Both runs are leak-free: no benchmark answer or rationale is retrievable (audited per question). The
submitted version's large gains (+12.5 answer / +16.0 AR) came from the leakage; see
[project history](../project-history/README.md).

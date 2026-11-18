"""Pipelines 2-4 - answer questions with RAPTOR hierarchical retrieval + DeepSeek.

    python src/run_raptor.py --pipeline cgr           # RAPTOR-CGR (proposed method)
    python src/run_raptor.py --pipeline pure          # standard RAPTOR-RAG
    python src/run_raptor.py --pipeline selfcritique  # extra ablation: two-round self-critique
    python src/run_raptor.py --pipeline cgr --limit 5 # quick test

All pipelines share the same RAPTOR tree (data/raptor_tree.pkl). If the tree file
is missing it is rebuilt from the benchmark corpus (needs many summarisation calls).
Results are written to results/raw/raptor_<pipeline>.json and the run is resumable.
"""

import argparse
import json
import logging
import sys
import time

from common import (LOG_DIR, RAW_DIR, TREE_PATH, detect_question_type, extract_answer_line,
                    format_question, get_client, load_dataset)

from raptor import (BaseEmbeddingModel, BaseQAModel, BaseSummarizationModel,
                    RetrievalAugmentation, RetrievalAugmentationConfig)

log = logging.getLogger("raptor-cgr")
client, MODEL = None, None


def chat(messages, temperature, max_tokens=None):
    kwargs = {"max_tokens": max_tokens} if max_tokens else {}
    resp = client.chat.completions.create(model=MODEL, messages=messages, temperature=temperature, **kwargs)
    return resp.choices[0].message.content.strip()


# ── Models plugged into RAPTOR ───────────────────────────────────────────────
class LocalEmbeddingModel(BaseEmbeddingModel):
    """sentence-transformers/all-MiniLM-L6-v2, run locally."""

    def __init__(self):
        from sentence_transformers import SentenceTransformer
        log.info("Loading embedding model...")
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def create_embedding(self, text):
        return self.model.encode(text).tolist()


class DeepSeekSummarizer(BaseSummarizationModel):
    """Cluster summariser used when building the RAPTOR tree."""

    def summarize(self, context, max_tokens=150):
        return chat([{"role": "user", "content": f"Summarize concisely:\n{context}"}],
                    temperature=0, max_tokens=max_tokens)


class PureQA(BaseQAModel):
    """Pipeline 2 - standard RAPTOR-RAG prompt."""

    SYSTEM = ("You are an expert computer science tutor. "
              "For multiple choice questions, answer with the LETTER only (A/B/C/D). "
              "For fill-in-the-blank, answer with a short phrase. "
              "Use RATIONALE: and ANSWER: format.")

    def answer_question(self, context, question):
        return chat([{"role": "system", "content": self.SYSTEM},
                     {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}],
                    temperature=0)


class CGRQA(BaseQAModel):
    """Pipeline 3 - RAPTOR-CGR: Chain-of-Thought + context grounding."""

    SYSTEM = ("You are an expert computer science tutor. "
              "Think step by step before answering. "
              "First identify the key concepts in the question, "
              "then reason through them carefully before concluding. "
              "You MUST base your answer strictly on the provided context. "
              "If the context contains the answer, quote or paraphrase it directly. "
              "Do not rely on prior knowledge not present in the context. "
              "For multiple choice questions, answer with the LETTER only (A/B/C/D). "
              "For multiple select, list all correct letters (e.g. A, C). "
              "For true/false questions, answer TRUE or FALSE only. "
              "For fill-in-the-blank, answer with the exact precise term or phrase. "
              "For open-ended questions, provide a comprehensive detailed answer. "
              "Use RATIONALE: to show your full step-by-step reasoning. "
              "Use ANSWER: for your final answer.")

    def answer_question(self, context, question):
        return chat([{"role": "system", "content": self.SYSTEM},
                     {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}],
                    temperature=0.2)


class SelfCritiqueQA(BaseQAModel):
    """Extra ablation - answer once, then ask the model to critique and fix its answer."""

    def answer_question(self, context, question):
        first = chat([{"role": "system", "content": "You are an expert computer science tutor. "
                                                     "Answer with RATIONALE: and ANSWER: format."},
                      {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}],
                     temperature=0.2)
        review = f"""Question: {question}
Context: {context}
Initial Answer: {first}

Critically review the answer above. Fix any errors in reasoning or final answer.
Respond strictly in this format:
RATIONALE: <your reasoning>
ANSWER: <final answer only>"""
        return chat([{"role": "system", "content": "You are a strict CS evaluator. Review and correct if needed."},
                     {"role": "user", "content": review}],
                    temperature=0)


PIPELINES = {
    # name: (QA model, extra RAPTOR config used in the original run)
    "pure": (PureQA, {}),
    "cgr": (CGRQA, {"tb_top_k": 10}),
    "selfcritique": (SelfCritiqueQA, {}),
}


# ── Corpus / tree ────────────────────────────────────────────────────────────
def build_corpus(data):
    """One passage per benchmark item: topic, question, options, rationale and answer."""
    parts = []
    for item in data:
        choices = item.get("Choices") or {}
        choices_text = ("\n" + "\n".join(f"  {k}: {v}" for k, v in choices.items())) if choices else ""
        parts.append(f"Topic: {item.get('Level-1 Topic', '')}\n"
                     f"Q: {item.get('Question', '')}{choices_text}\n"
                     f"Rationale: {item.get('Rationale', '')}\n"
                     f"A: {item.get('Answer', '')}")
    return "\n\n---\n\n".join(parts)


def load_or_build_tree(config, data):
    if TREE_PATH.exists():
        log.info(f"Loading RAPTOR tree from {TREE_PATH}")
        return RetrievalAugmentation(config=config, tree=str(TREE_PATH))
    log.info("Building RAPTOR tree (this takes a while)...")
    ra = RetrievalAugmentation(config=config)
    ra.add_documents(build_corpus(data))
    ra.save(str(TREE_PATH))
    log.info(f"Tree saved to {TREE_PATH}")
    return ra


def main():
    global client, MODEL
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pipeline", choices=PIPELINES, required=True)
    parser.add_argument("--limit", type=int, help="only answer the first N questions")
    args = parser.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s",
                        handlers=[logging.FileHandler(LOG_DIR / f"run_{args.pipeline}.log", encoding="utf-8"),
                                  logging.StreamHandler(sys.stdout)])

    client, MODEL = get_client()
    qa_cls, extra = PIPELINES[args.pipeline]
    output_path = RAW_DIR / f"raptor_{args.pipeline}.json"

    data = load_dataset()
    limit = min(args.limit, len(data)) if args.limit else len(data)
    log.info(f"Pipeline: {args.pipeline} | questions: {limit}")

    config = RetrievalAugmentationConfig(
        summarization_model=DeepSeekSummarizer(),
        qa_model=qa_cls(),
        embedding_model=LocalEmbeddingModel(),
        tb_num_layers=2,
        tb_threshold=0.5,
        **extra,
    )
    ra = load_or_build_tree(config, data)

    output = json.loads(output_path.read_text(encoding="utf-8")) if output_path.exists() else []
    done = {r["idx"] for r in output}
    if done:
        log.info(f"Resuming: {len(done)} questions already answered.")

    for i, item in enumerate(data[:limit]):
        if i in done:
            continue
        full_question = format_question(item)
        expected = item.get("Answer", "")
        qtype = detect_question_type(item)
        try:
            prediction = ra.answer_question(question=full_question)
            got = extract_answer_line(prediction)
            log.info(f"[{i + 1}/{limit}] [{qtype}] expected={expected!r:.40} got={got!r:.40}")
        except Exception as e:
            prediction = f"Error: {e}"
            log.warning(f"[{i + 1}/{limit}] error: {e}")

        output.append({"idx": i, "question": item.get("Question", ""), "full_question": full_question,
                       "prediction": prediction, "answer": expected, "type": qtype,
                       "topic": item.get("Level-1 Topic", "")})
        output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        time.sleep(0.5)

    log.info(f"Done. Results saved to {output_path}")


if __name__ == "__main__":
    main()

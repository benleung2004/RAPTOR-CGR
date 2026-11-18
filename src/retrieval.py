"""Collapsed-tree RAPTOR retrieval over the textbook index, computed once for every question.

Same semantics as RAPTOR's TreeRetriever(collapse_tree=True): rank every node (leaf chunks and
summaries of all layers) by cosine distance to the query and take the top-k within a token
budget. It is vectorised with numpy so all 1,018 queries take seconds instead of hours.

Every RAPTOR pipeline reads the same results/contexts.jsonl, so they see identical evidence.

    python src/retrieval.py
"""

import argparse
import json

import numpy as np

from common import (CONTEXT_MAX_TOKENS, CONTEXTS_PATH, EMBEDDING_MODEL, INDEX_DIR, TOP_K,
                    format_question, load_questions, read_jsonl)


class CollapsedTreeRetriever:
    def __init__(self, embeddings, nodes, embed_fn):
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        self.unit = embeddings / np.where(norms == 0, 1, norms)
        self.nodes = nodes
        self.embed_fn = embed_fn
        import tiktoken
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    @classmethod
    def from_index(cls, index_dir=INDEX_DIR, embed_fn=None):
        embeddings = np.load(index_dir / "embeddings.npy")
        nodes = read_jsonl(index_dir / "nodes.jsonl")
        if embed_fn is None:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(EMBEDDING_MODEL)
            embed_fn = lambda texts: model.encode(texts, batch_size=64, show_progress_bar=False)
        return cls(embeddings, nodes, embed_fn)

    def retrieve_many(self, queries, top_k=TOP_K, max_tokens=CONTEXT_MAX_TOKENS):
        q = np.asarray(self.embed_fn(queries), dtype=np.float32)
        q /= np.where(np.linalg.norm(q, axis=1, keepdims=True) == 0, 1, np.linalg.norm(q, axis=1, keepdims=True))
        distances = 1.0 - q @ self.unit.T                      # cosine distance, as in RAPTOR
        results = []
        for row in distances:
            order = np.argsort(row)[:top_k]
            picked, total = [], 0
            for i in order:
                n_tokens = len(self.tokenizer.encode(self.nodes[i]["text"]))
                if total + n_tokens > max_tokens:
                    break
                picked.append(int(i))
                total += n_tokens
            # identical text layout to raptor.utils.get_text
            context = "".join(" ".join(self.nodes[i]["text"].splitlines()) + "\n\n" for i in picked)
            results.append({"context": context,
                            "nodes": [{"book": self.nodes[i]["book"], "node": self.nodes[i]["node"],
                                       "layer": self.nodes[i]["layer"],
                                       "distance": round(float(row[i]), 4)} for i in picked]})
        return results


def web_index_contexts(queries, top_k=6, index=None):
    """Retrieve from the free web-tutor index (textbook chunks only, no RAPTOR summaries).

    Used for the budget evaluation: building the RAPTOR summary trees costs ~US$2 of API calls,
    while this index is built locally for free from the same 20 textbooks.
    """
    from chat_engine import TextbookIndex
    index = index or TextbookIndex.load()
    results = []
    for q in queries:
        hits = index.search(q, top_k)
        context = "\n\n".join(f"{h['title']} — {h['section'] or 'excerpt'}\n{h['text']}" for h in hits)
        results.append({"context": context,
                        "nodes": [{"book": h["book"], "node": h["id"], "layer": 0, "score": h["score"]} for h in hits]})
    return results


def main(argv=None, retriever=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--index", choices=["raptor", "web"], default="raptor",
                        help="raptor: RAPTOR trees (build_tree.py); web: free textbook-chunk index (build_web_index.py)")
    parser.add_argument("--top-k", type=int, help="default: 10 for raptor, 6 for web")
    args = parser.parse_args(argv)

    questions = load_questions()
    # Query = question text + options in the original order (independent of any option shuffle).
    queries = [format_question(q) for q in questions]
    if args.index == "web":
        results = web_index_contexts(queries, top_k=args.top_k or 6)
    else:
        retriever = retriever or CollapsedTreeRetriever.from_index()
        results = retriever.retrieve_many(queries, top_k=args.top_k or TOP_K)
    CONTEXTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    (CONTEXTS_PATH.parent / "contexts_meta.json").write_text(
        json.dumps({"index": args.index, "top_k": args.top_k or (6 if args.index == "web" else TOP_K)}),
        encoding="utf-8")
    with open(CONTEXTS_PATH, "w", encoding="utf-8") as f:
        for idx, r in enumerate(results):
            f.write(json.dumps({"idx": idx, **r}, ensure_ascii=False) + "\n")
    print(f"Contexts for {len(results)} questions written to {CONTEXTS_PATH}")


if __name__ == "__main__":
    main()

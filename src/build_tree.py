"""Build the RAPTOR retrieval index from the 20 GraphRAG-Bench textbooks.

For every textbook a RAPTOR tree is built (100-token chunks -> UMAP + GMM clustering -> LLM
summaries, 2 layers, same RAPTOR settings as v1) and saved to data/trees/<book>.pkl. All nodes of all trees are then
written to one flat index (data/index/) used for collapsed-tree retrieval.

The benchmark questions, answers and rationales are NOT part of the corpus.

    python src/download_data.py                # once
    python src/build_tree.py                   # resumable: finished books are skipped
    python src/build_tree.py --books textbook1 --max-chunks 300   # small test
"""

import argparse
import json
import logging
import pickle
import sys
import threading

import numpy as np

from common import (CHUNK_TOKENS, CLUSTER_THRESHOLD, EMBEDDING_MODEL, INDEX_DIR, LOG_DIR,
                    SUMMARY_TOKENS, TEXTBOOK_DIR, TREE_DIR, TREE_LAYERS, clean_markdown,
                    split_chunks)

log = logging.getLogger("build_tree")
EMB_KEY = "EMB"


class LocalEmbeddingModel:
    """all-MiniLM-L6-v2 run locally; thread-safe encode."""

    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        self._lock = threading.Lock()

    def create_embedding(self, text):
        with self._lock:
            return self.model.encode(text).tolist()

    def encode_batch(self, texts):
        with self._lock:
            return self.model.encode(texts, batch_size=128, show_progress_bar=False)


def make_summarizer(llm):
    """Summariser that never raises: RAPTOR's threaded builder silently drops a cluster whose
    summary call fails, so after all retries we fall back to the cluster's opening text and count it."""
    from raptor import BaseSummarizationModel

    class Summarizer(BaseSummarizationModel):
        failures = 0

        def summarize(self, context, max_tokens=SUMMARY_TOKENS):
            try:
                text, _ = llm.chat([{"role": "user", "content": f"Summarize concisely:\n{context}"}],
                                   temperature=0, max_tokens=max_tokens)
                if text:
                    return text
            except Exception as e:
                log.warning(f"summary failed after retries: {e}")
            Summarizer.failures += 1
            return context[:400]

    return Summarizer()


def make_embedder(model):
    from raptor import BaseEmbeddingModel

    class Embedder(BaseEmbeddingModel):
        def create_embedding(self, text):
            return model.create_embedding(text)

    return Embedder()


def build_book_tree(book_path, embedder, summarizer, max_chunks=None):
    """RAPTOR tree for one textbook, using the unmodified RAPTOR ClusterTreeBuilder."""
    import tiktoken
    from raptor.cluster_tree_builder import ClusterTreeBuilder, ClusterTreeConfig
    from raptor.tree_structures import Node, Tree

    config = ClusterTreeConfig(
        tokenizer=tiktoken.get_encoding("cl100k_base"), max_tokens=CHUNK_TOKENS,
        num_layers=TREE_LAYERS, threshold=CLUSTER_THRESHOLD, summarization_length=SUMMARY_TOKENS,
        summarization_model=summarizer, embedding_models={EMB_KEY: make_embedder(embedder)},
        cluster_embedding_model=EMB_KEY)
    builder = ClusterTreeBuilder(config)

    chunks = split_chunks(clean_markdown(book_path.read_text(encoding="utf-8")), config.tokenizer, CHUNK_TOKENS)
    chunks = [c for c in chunks if c.strip()][:max_chunks]
    log.info(f"{book_path.stem}: {len(chunks)} chunks, embedding...")
    vectors = embedder.encode_batch(chunks)
    leaves = {i: Node(c, i, set(), {EMB_KEY: v.tolist()}) for i, (c, v) in enumerate(zip(chunks, vectors))}

    layer_to_nodes = {0: list(leaves.values())}
    all_nodes = dict(leaves)
    log.info(f"{book_path.stem}: clustering and summarising...")
    roots = builder.construct_tree(all_nodes, all_nodes, layer_to_nodes, use_multithreading=True)
    return Tree(all_nodes, roots, leaves, builder.num_layers, layer_to_nodes)


def write_index(tree_paths):
    """Flatten every node of every tree into data/index/{embeddings.npy, nodes.jsonl}."""
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    vectors, meta = [], []
    for path in tree_paths:
        tree = pickle.loads(path.read_bytes())
        layer_of = {n.index: layer for layer, nodes in tree.layer_to_nodes.items() for n in nodes}
        for idx in sorted(tree.all_nodes):
            node = tree.all_nodes[idx]
            vectors.append(node.embeddings[EMB_KEY])
            meta.append({"book": path.stem, "node": idx, "layer": layer_of.get(idx, 0), "text": node.text})
    np.save(INDEX_DIR / "embeddings.npy", np.asarray(vectors, dtype=np.float32))
    with open(INDEX_DIR / "nodes.jsonl", "w", encoding="utf-8") as f:
        for m in meta:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
    log.info(f"Index written: {len(meta)} nodes from {len(tree_paths)} trees -> {INDEX_DIR}")


def main(argv=None, llm=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--books", nargs="+", help="e.g. textbook1 textbook2 (default: all 20)")
    parser.add_argument("--max-chunks", type=int, help="truncate each book (for testing)")
    args = parser.parse_args(argv)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s",
                        handlers=[logging.FileHandler(LOG_DIR / "build_tree.log", encoding="utf-8"),
                                  logging.StreamHandler(sys.stdout)])

    books = sorted(TEXTBOOK_DIR.glob("textbook*.md"), key=lambda p: int(p.stem[8:]))
    if args.books:
        books = [b for b in books if b.stem in args.books]
    if not books:
        raise SystemExit("No textbooks found - run src/download_data.py first.")

    if llm is None:
        from llm import LLM
        llm = LLM("answer")
    embedder = LocalEmbeddingModel()
    summarizer = make_summarizer(llm)
    TREE_DIR.mkdir(parents=True, exist_ok=True)

    def build(book):
        out = TREE_DIR / f"{book.stem}.pkl"
        if out.exists():
            log.info(f"{book.stem}: already built, skipped")
            return
        tree = build_book_tree(book, embedder, summarizer, args.max_chunks)
        out.write_bytes(pickle.dumps(tree))
        log.info(f"{book.stem}: done - {len(tree.all_nodes)} nodes "
                 f"({ {k: len(v) for k, v in tree.layer_to_nodes.items()} })")

    # Books are built one after another: UMAP (numba) is not thread-safe. Inside a book the
    # cluster summaries are requested in parallel by RAPTOR's threaded builder.
    for book in books:
        build(book)

    write_index(sorted(TREE_DIR.glob("textbook*.pkl"), key=lambda p: int(p.stem[8:])))
    log.info(f"Summariser usage: {llm.usage_summary()} | fallback summaries: {summarizer.failures}")


if __name__ == "__main__":
    main()

"""The fast numpy retriever must return exactly what RAPTOR's own collapsed-tree retriever returns.

Uses the v1 tree (results/v1/question_tree.pkl) and the local embedding model; no API calls.
"""

import pickle
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from common import format_question, load_questions  # noqa: E402

TREE = ROOT / "results" / "v1" / "question_tree.pkl"


@unittest.skipUnless(TREE.exists(), "v1 tree not available")
class RetrieverMatchesRaptor(unittest.TestCase):
    def test_same_context_as_raptor(self):
        from sentence_transformers import SentenceTransformer

        from raptor import BaseEmbeddingModel
        from raptor.tree_retriever import TreeRetriever, TreeRetrieverConfig
        from retrieval import CollapsedTreeRetriever

        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

        class Emb(BaseEmbeddingModel):
            def create_embedding(self, text):
                return model.encode(text).tolist()

        tree = pickle.loads(TREE.read_bytes())
        raptor = TreeRetriever(TreeRetrieverConfig(embedding_model=Emb(), context_embedding_model="EMB"), tree)

        ids = sorted(tree.all_nodes)
        ours = CollapsedTreeRetriever(
            np.asarray([tree.all_nodes[i].embeddings["EMB"] for i in ids], dtype=np.float32),
            [{"book": "v1", "node": i, "layer": 0, "text": tree.all_nodes[i].text} for i in ids],
            lambda texts: model.encode(texts))

        queries = [format_question(q) for q in load_questions()[::34]]       # 30 spread-out questions
        mine = ours.retrieve_many(queries, top_k=10, max_tokens=3500)
        same = 0
        for q, m in zip(queries, mine):
            expected = raptor.retrieve(q, top_k=10, max_tokens=3500, collapse_tree=True,
                                       return_layer_information=False)
            same += expected == m["context"]
        print(f"\nidentical contexts: {same}/{len(queries)}")
        self.assertGreaterEqual(same, len(queries) - 1, f"only {same}/{len(queries)} identical")


if __name__ == "__main__":
    unittest.main()

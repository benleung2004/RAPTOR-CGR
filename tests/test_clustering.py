"""SafeRAPTORClustering: identical to upstream RAPTOR_Clustering, except that it terminates."""

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

import build_tree  # noqa: E402
from raptor import cluster_utils  # noqa: E402
from raptor.tree_structures import Node  # noqa: E402


def nodes(n, words=60):
    return [Node(f"node {i} " + "word " * words, i, set(), {"EMB": [float(i), 1.0]}) for i in range(n)]


class SafeClustering(unittest.TestCase):
    def test_unsplittable_cluster_terminates(self):
        # GMM puts every node into one cluster, forever: upstream recursed until RecursionError
        all_in_one = lambda emb, dim, threshold: [np.array([0]) for _ in range(len(emb))]
        with mock.patch.object(cluster_utils, "perform_clustering", all_in_one):
            with self.assertRaises(RecursionError):
                cluster_utils.RAPTOR_Clustering.perform_clustering(nodes(200), "EMB")
            groups = build_tree.SafeRAPTORClustering.perform_clustering(nodes(200), "EMB")
        import tiktoken
        tok = tiktoken.get_encoding("cl100k_base")
        self.assertEqual(sum(len(g) for g in groups), 200)                       # no node lost
        self.assertTrue(all(sum(len(tok.encode(n.text)) for n in g) <= 3500 for g in groups))
        self.assertEqual([n.index for g in groups for n in g], list(range(200)))  # order kept

    def test_same_result_as_upstream_when_splitting_works(self):
        def halves(emb, dim, threshold):              # deterministic splitter: first half / second half
            return [np.array([0]) if i < len(emb) / 2 else np.array([1]) for i in range(len(emb))]
        data = nodes(64, words=120)                    # 64 x ~125 tokens: halves still too long -> recurse
        with mock.patch.object(cluster_utils, "perform_clustering", halves):
            up = cluster_utils.RAPTOR_Clustering.perform_clustering(data, "EMB")
            safe = build_tree.SafeRAPTORClustering.perform_clustering(data, "EMB")
        self.assertEqual([[n.index for n in g] for g in up], [[n.index for n in g] for g in safe])
        self.assertGreater(len(safe), 2)                                          # recursion did happen


class GmmFailures(unittest.TestCase):
    def test_retry_then_success(self):
        calls = {"n": 0}

        def flaky(emb, dim, threshold):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ValueError("Fitting the mixture model failed because some components have ill-defined covariance")
            return [np.array([0]) for _ in range(len(emb))]
        with mock.patch.object(cluster_utils, "perform_clustering", flaky):
            groups = build_tree.SafeRAPTORClustering.perform_clustering(nodes(5, words=5), "EMB")
        self.assertEqual((calls["n"], len(groups)), (2, 1))

    def test_always_failing_falls_back_to_order(self):
        def broken(emb, dim, threshold):
            raise np.linalg.LinAlgError("not positive definite")
        before = build_tree.SafeRAPTORClustering.FALLBACKS
        with mock.patch.object(cluster_utils, "perform_clustering", broken):
            groups = build_tree.SafeRAPTORClustering.perform_clustering(nodes(100), "EMB")
        self.assertEqual([n.index for g in groups for n in g], list(range(100)))
        self.assertEqual(build_tree.SafeRAPTORClustering.FALLBACKS, before + 1)


class Duplicates(unittest.TestCase):
    def test_identical_clusters_are_kept_once(self):
        # every node gets labels 0..9, i.e. the same member set ten times
        many_labels = lambda emb, dim, threshold: [np.arange(10) for _ in range(len(emb))]
        with mock.patch.object(cluster_utils, "perform_clustering", many_labels):
            groups = build_tree.SafeRAPTORClustering.perform_clustering(nodes(5, words=5), "EMB")
        self.assertEqual(len(groups), 1)


if __name__ == "__main__":
    unittest.main()

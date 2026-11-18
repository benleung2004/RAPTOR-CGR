"""Statistics used in make_report.py."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from make_report import cohen_kappa, paired_bootstrap  # noqa: E402


class Bootstrap(unittest.TestCase):
    def test_identical_runs_are_not_significant(self):
        a = [1, 0, 1, 1, 0] * 200
        d, lo, hi, p = paired_bootstrap(a, a)
        self.assertEqual((d, lo, hi), (0.0, 0.0, 0.0))
        self.assertEqual(p, 1.0)

    def test_clear_improvement_is_significant(self):
        b = [0] * 500 + [1] * 500
        a = [1] * 700 + [0] * 300          # +20 points, paired
        d, lo, hi, p = paired_bootstrap(a, b)
        self.assertAlmostEqual(d, 0.2)
        self.assertLess(p, 0.001)
        self.assertTrue(lo > 0 < hi)

    def test_tiny_noisy_difference_is_not_significant(self):
        b = [1, 0] * 500
        a = list(b)
        a[0], a[1] = 0, 1                  # two answers swapped, same mean
        a[3] = 1                           # +1 question out of 1000
        d, lo, hi, p = paired_bootstrap(a, b)
        self.assertLess(lo, 0.0001)
        self.assertGreater(p, 0.05)


class Kappa(unittest.TestCase):
    def test_perfect_and_chance(self):
        self.assertEqual(cohen_kappa([0, 1, 0.5, 1], [0, 1, 0.5, 1]), 1.0)
        self.assertAlmostEqual(cohen_kappa([0, 1, 0, 1], [0, 0, 1, 1]), 0.0)


if __name__ == "__main__":
    unittest.main()


class Sampling(unittest.TestCase):
    def test_stratified_proportional_and_deterministic(self):
        from common import detect_question_type, load_questions
        from make_sample import stratified_sample
        questions = load_questions()
        idx, counts = stratified_sample(questions, 300, 42)
        self.assertEqual(len(idx), 300)
        self.assertEqual(len(set(idx)), 300)
        self.assertEqual(counts, {"FB": 31, "MC": 64, "MS": 33, "OE": 79, "TF": 93})
        self.assertEqual({t: sum(detect_question_type(questions[i]) == t for i in idx) for t in counts}, counts)
        self.assertEqual(stratified_sample(questions, 300, 42)[0], idx)            # reproducible
        self.assertNotEqual(stratified_sample(questions, 300, 7)[0], idx)

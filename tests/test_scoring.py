"""Unit tests for answer parsing and deterministic scoring.  Run: python -m unittest discover tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from common import format_question, option_order  # noqa: E402
from scoring import (answer_score_deterministic, ar_score, mc_letter, ms_letters,  # noqa: E402
                     normalize_text, parse_judge_score, split_prediction, tf_value)


class SplitPrediction(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(split_prediction("RATIONALE: because x\nANSWER: B"), ("because x", "B"))

    def test_markdown_tags(self):
        self.assertEqual(split_prediction("**RATIONALE:** r\n**ANSWER:** True"), ("r", "True"))

    def test_multiline_open_ended_answer_is_kept(self):
        _, ans = split_prediction("RATIONALE: r\nANSWER: line one\nline two")
        self.assertEqual(ans, "line one\nline two")

    def test_last_answer_tag_wins(self):
        _, ans = split_prediction("RATIONALE: the answer: maybe A\nANSWER: A\n\nFinal Answer: C")
        self.assertEqual(ans, "C")

    def test_inline_word_answer_is_not_a_tag(self):
        rat, ans = split_prediction("RATIONALE: the answer: is C because...\nANSWER: C")
        self.assertEqual((rat, ans), ("the answer: is C because...", "C"))

    def test_missing_tag(self):
        # a short untagged line is taken as the answer, but it must still be scored strictly:
        # "I think it is B" does not start with an option letter, so it is not read as B
        self.assertEqual(split_prediction("I think it is B"), ("", "I think it is B"))
        self.assertIsNone(mc_letter("I think it is B"))
        long_reply = "Let me think step by step.\nThe answer could be B."
        self.assertEqual(split_prediction(long_reply), (long_reply, ""))


class Letters(unittest.TestCase):
    def test_mc_formats(self):
        for text in ["B", "(B)", "B. a queue", "B) stack", "**B**", "Option B", "The answer is B"]:
            self.assertEqual(mc_letter(text), "B", text)

    def test_mc_unreadable(self):
        self.assertIsNone(mc_letter("a queue"))

    def test_mc_shuffle_mapping(self):
        self.assertEqual(mc_letter("A", {"A": "C", "B": "A", "C": "B"}), "C")

    def test_ms_formats(self):
        self.assertEqual(ms_letters("A, C"), {"A", "C"})
        self.assertEqual(ms_letters("A and D"), {"A", "D"})
        self.assertEqual(ms_letters("A, C (both are stable sorts)"), {"A", "C"})
        self.assertEqual(ms_letters("B;D"), {"B", "D"})
        self.assertEqual(ms_letters(""), set())

    def test_tf(self):
        self.assertEqual(tf_value("TRUE"), "true")
        self.assertEqual(tf_value("**False.**"), "false")
        self.assertIsNone(tf_value("It depends"))


class Scoring(unittest.TestCase):
    def test_tf_case_insensitive(self):        # v1 counted 'TRUE' vs 'True' as wrong
        self.assertEqual(answer_score_deterministic("TF", "TRUE", "True"), 1.0)

    def test_ms_partial_and_empty(self):       # v1 gave 0.5 to an empty answer
        self.assertEqual(answer_score_deterministic("MS", "A, C", "A, C"), 1.0)
        self.assertEqual(answer_score_deterministic("MS", "A", "A, C"), 0.5)
        self.assertEqual(answer_score_deterministic("MS", "A, B", "A, C"), 0.0)
        self.assertEqual(answer_score_deterministic("MS", "", "A, C"), 0.0)

    def test_fb_exact_then_judge(self):
        self.assertEqual(answer_score_deterministic("FB", "The Method.", "method"), 1.0)
        self.assertIsNone(answer_score_deterministic("FB", "function", "method"))
        self.assertEqual(answer_score_deterministic("FB", "", "method"), 0.0)

    def test_oe_needs_judge(self):
        self.assertIsNone(answer_score_deterministic("OE", "some answer", "gold"))
        self.assertEqual(answer_score_deterministic("OE", "", "gold"), 0.0)

    def test_normalize(self):
        self.assertEqual(normalize_text("**The  Dot-operator**"), "dot operator")

    def test_judge_parse(self):
        self.assertEqual(parse_judge_score('{"score": 0.5}'), 0.5)
        self.assertEqual(parse_judge_score("Score: 1"), 1.0)
        self.assertEqual(parse_judge_score("0"), 0.0)
        self.assertIsNone(parse_judge_score("0.75"))
        self.assertIsNone(parse_judge_score("excellent"))

    def test_ar_matches_graphrag_bench(self):
        table = {(1, 1): 1.0, (1, 0.5): 0.5, (1, 0): 0.0, (0, 1): 0.5, (0, 0.5): 0.25, (0, 0): 0.0,
                 (0.5, 1): 0.0, (0.5, 0.5): 0.0}
        for (a, r), expected in table.items():
            self.assertEqual(ar_score(float(a), float(r)), expected, (a, r))


class OptionShuffle(unittest.TestCase):
    ITEM = {"Question": "Q?", "Choices": {"A": "alpha", "B": "beta", "C": "gamma", "D": "delta"}}

    def test_identity_without_seed(self):
        self.assertEqual(option_order(self.ITEM, 0), {"A": "A", "B": "B", "C": "C", "D": "D"})

    def test_seeded_permutation_is_deterministic_and_changes_order(self):
        m1, m2 = option_order(self.ITEM, 3, 1), option_order(self.ITEM, 3, 1)
        self.assertEqual(m1, m2)
        self.assertNotEqual(m1, {k: k for k in "ABCD"})
        self.assertEqual(sorted(m1.values()), list("ABCD"))

    def test_rendering_follows_map(self):
        text = format_question(self.ITEM, {"A": "C", "B": "A", "C": "D", "D": "B"})
        self.assertIn("A. gamma", text)
        self.assertIn("D. beta", text)


if __name__ == "__main__":
    unittest.main()


class UntaggedReplies(unittest.TestCase):
    def test_short_untagged_reply_is_the_answer(self):          # thinking-mode replies like "A, C, D"
        self.assertEqual(split_prediction("A, C, D"), ("", "A, C, D"))
        self.assertEqual(split_prediction("**2n + 2**"), ("", "2n + 2"))

    def test_long_or_multiline_untagged_reply_is_unanswered(self):
        self.assertEqual(split_prediction("I think about it\nmaybe B")[1], "")
        self.assertEqual(split_prediction("x " * 100)[1], "")

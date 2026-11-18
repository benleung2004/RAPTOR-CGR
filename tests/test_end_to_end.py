"""Offline end-to-end test of the whole v2 workflow with a fake LLM (no API key, no cost).

build_tree (2 truncated textbooks) -> retrieval -> check_leakage -> run_pipeline (all pipelines,
plus a shuffled-option run and an injected API failure) -> evaluate -> make_report.

The fake model always answers correctly, so every deterministic score must be exactly 1.0 -
including the shuffled run, which proves option letters are mapped back correctly.
"""

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import build_tree  # noqa: E402
import check_leakage  # noqa: E402
import common  # noqa: E402
import evaluate  # noqa: E402
import make_report  # noqa: E402
import prompts  # noqa: E402
import retrieval  # noqa: E402
import run_pipeline  # noqa: E402

BOOKS = sorted((ROOT / "data" / "textbooks").glob("textbook*.md"))


class FakeLLM:
    model = "fake-model"

    def __init__(self, fail_once=()):
        self.questions = common.load_questions()
        self.fail_once = set(fail_once)
        self.calls = 0

    def usage_summary(self):
        return {"model": self.model, "calls": self.calls}

    def _item(self, content):
        # several questions share the same text ("Which of the following is true?"), so match
        # on the question text and on every option text
        after = content.split("Question: ", 1)[1]
        matches = [q for q in self.questions if after.startswith(q["Question"])
                   and all(f". {t}" in after for t in (q.get("Choices") or {}).values())]
        return max(matches, key=lambda q: len(q["Question"])), content

    def chat(self, messages, temperature=0.0, max_tokens=None):
        self.calls += 1
        usage = {"prompt_tokens": 10, "completion_tokens": 5}
        system, user = messages[0]["content"], messages[-1]["content"]
        if user.startswith("Summarize concisely"):
            return "summary: " + user[20:100], usage
        if system == prompts.JUDGE_SYSTEM:
            return '{"score": 1}', usage
        item, content = self._item(user)
        idx = self.questions.index(item)
        if idx in self.fail_once:
            self.fail_once.discard(idx)
            raise RuntimeError("simulated API outage")
        qtype = common.detect_question_type(item)
        options = content.split("\nOptions:\n", 1)[-1]
        # displayed letter of each original option (option texts may span several lines)
        to_shown = {orig: next(d for d in "ABCDE" if f"{d}. {text}" in options)
                    for orig, text in (item.get("Choices") or {}).items()}
        gold = item["Answer"]
        if qtype == "MC":
            ans = to_shown[gold.strip()]
        elif qtype == "MS":
            ans = ", ".join(sorted(to_shown[l] for l in re.findall(r"[A-E]", gold)))
        else:
            ans = gold
        return f"RATIONALE: {item['Rationale']}\nANSWER: {ans}", usage


@unittest.skipUnless(len(BOOKS) >= 2, "textbooks not downloaded (python src/download_data.py)")
class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "textbooks").mkdir()
        for b in BOOKS[:2]:
            shutil.copy(b, self.tmp / "textbooks" / b.name)
        paths = {"TEXTBOOK_DIR": self.tmp / "textbooks", "TREE_DIR": self.tmp / "trees",
                 "INDEX_DIR": self.tmp / "index", "CONTEXTS_PATH": self.tmp / "contexts.jsonl",
                 "RAW_DIR": self.tmp / "raw", "JUDGE_DIR": self.tmp / "judgments",
                 "TABLE_DIR": self.tmp / "tables", "SCORES_PATH": self.tmp / "scores.json",
                 "LEAKAGE_PATH": self.tmp / "leakage.json", "LOG_DIR": self.tmp / "logs"}
        self.saved = []
        for mod in (common, build_tree, retrieval, run_pipeline, evaluate, check_leakage, make_report):
            for name, value in paths.items():
                if hasattr(mod, name):
                    self.saved.append((mod, name, getattr(mod, name)))
                    setattr(mod, name, value)
        retrieval.CollapsedTreeRetriever.from_index.__func__.__defaults__ = (paths["INDEX_DIR"], None)

    def tearDown(self):
        for mod, name, value in self.saved:
            setattr(mod, name, value)
        retrieval.CollapsedTreeRetriever.from_index.__func__.__defaults__ = (common.INDEX_DIR, None)
        shutil.rmtree(self.tmp)

    def test_full_workflow(self):
        llm = FakeLLM(fail_once={5, 300})
        build_tree.main(["--max-chunks", "250"], llm=llm)
        nodes = common.read_jsonl(self.tmp / "index" / "nodes.jsonl")
        self.assertGreater(len(nodes), 500)
        self.assertTrue(any(n["layer"] > 0 for n in nodes), "no summary nodes were built")

        retrieval.main([])
        contexts = common.read_jsonl(self.tmp / "contexts.jsonl")
        self.assertEqual(len(contexts), 1018)
        self.assertTrue(all(len(c["nodes"]) == 10 for c in contexts))

        check_leakage.main([])
        leak = json.loads((self.tmp / "leakage.json").read_text())
        self.assertIn("rationale_in_context_rate", leak)

        for p in ["baseline", "pure", "cgr", "selfcritique"]:
            run_pipeline.main(["--pipeline", p, "--workers", "4"], llm=llm)
        # the two simulated failures are recorded as errors and retried on the next invocation
        self.assertEqual(len(common.load_run(self.tmp / "raw" / "baseline.jsonl")), 1016)
        run_pipeline.main(["--pipeline", "baseline"], llm=llm)
        self.assertEqual(len(common.load_run(self.tmp / "raw" / "baseline.jsonl")), 1018)
        run_pipeline.main(["--pipeline", "cgr", "--shuffle-seed", "1", "--workers", "4"], llm=llm)
        shuffled = common.load_run(self.tmp / "raw" / "cgr-shuffle1.jsonl")
        self.assertTrue(any(r["option_map"] and r["option_map"] != {k: k for k in r["option_map"]}
                            for r in shuffled.values()))

        evaluate.main(["--workers", "4"], llm=llm)
        make_report.main([])
        scores = json.loads((self.tmp / "scores.json").read_text())["runs"]
        for run in ["baseline", "pure", "cgr", "selfcritique"]:
            self.assertEqual(scores[run]["total"]["count"], 1018, run)
            for t in ["MC", "MS", "TF", "FB", "OE"]:
                self.assertEqual(scores[run]["by_type"][t]["answer_score"], 1.0, (run, t))
            self.assertEqual(scores[run]["total"]["ar_score"], 1.0, run)
            self.assertEqual(scores[run]["total"]["count_with_rationale"], 1000, run)   # 18 have none
        self.assertEqual(scores["cgr-shuffle1"]["total"]["count"], 328)               # MC + MS only
        self.assertEqual(scores["cgr-shuffle1"]["total"]["answer_score"], 1.0)
        summary = (self.tmp / "tables" / "summary.md").read_text()
        self.assertIn("Option-shuffle consistency", summary)
        self.assertIn("Paired bootstrap", summary)
        self.assertIn("| RAPTOR-CGR | cgr-shuffle1 | 328 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |", summary)
        # the textbook corpus never contains a benchmark rationale (answer key)
        self.assertEqual(json.loads((self.tmp / "leakage.json").read_text())["rationale_in_context"], 0)


if __name__ == "__main__":
    unittest.main()

"""Textbook cleaning must remove markup and running footers but never real content."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from common import TEXTBOOK_DIR, clean_markdown  # noqa: E402


class Cleaning(unittest.TestCase):
    def test_inequalities_survive(self):          # the old regex deleted everything between < and >
        text = "If a < b and the loop runs while c > d, then x <= y holds.\nNext line stays."
        self.assertEqual(clean_markdown(text), text)

    def test_html_tables_and_tags(self):
        out = clean_markdown("<table><tr><td>key</td><td>value</td></tr></table> <br/> end")
        self.assertIn("key | value", out)
        self.assertNotIn("<", out)

    def test_images_and_footers(self):
        footer = "Draft of September 2026, please do not distribute copies of this chapter"
        text = "\n".join([f"para {i}\n{footer}" for i in range(20)]) + "\n![fig](x.png) caption"
        out = clean_markdown(text)
        self.assertNotIn(footer, out)
        self.assertIn("para 19", out)
        self.assertNotIn("x.png", out)
        self.assertIn("caption", out)

    def test_short_repeated_code_lines_are_kept(self):
        code = "\n".join(["for i = 1 to n", "  return x"] * 20)
        self.assertEqual(clean_markdown(code).count("return x"), 20)

    def test_murphy_licence_footer(self):
        out = clean_markdown("Author: Kevin P. Murphy. (C) MIT Press. CC-BY-NC-ND license called a decision tree")
        self.assertEqual(out, "called a decision tree")

    @unittest.skipUnless((TEXTBOOK_DIR / "textbook15.md").exists(), "textbooks not downloaded")
    def test_real_textbooks_keep_almost_everything(self):
        for book in sorted(TEXTBOOK_DIR.glob("textbook*.md")):
            raw = book.read_text(encoding="utf-8")
            kept = len(clean_markdown(raw)) / len(raw)
            self.assertGreater(kept, 0.80, f"{book.name} kept only {kept:.0%}")


if __name__ == "__main__":
    unittest.main()

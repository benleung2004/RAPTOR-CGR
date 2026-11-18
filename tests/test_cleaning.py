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


class Chunking(unittest.TestCase):
    def setUp(self):
        import tiktoken
        self.tok = tiktoken.get_encoding("cl100k_base")

    def test_text_is_preserved_exactly(self):
        from common import split_chunks
        text = ("Section 6.5 covers TCP. It is reliable! Is UDP? No.\n\nDIJKSTRA(G, w, s)\n  for each v in V\n"
                "    d[v] = inf\n\n| a | b |\n|---|---|\n| 1 | 2 |")
        chunks = split_chunks(text, self.tok, 220)
        self.assertEqual(chunks, [text])                       # small text: one untouched chunk
        self.assertIn("6.5", chunks[0])
        self.assertIn("\n    d[v] = inf", chunks[0])

    def test_long_text_is_split_without_losing_characters(self):
        from common import split_chunks
        para = " ".join(f"Sentence number {i} ends here." for i in range(200))
        text = para + "\n\n" + "\n".join(f"line {i}" for i in range(300))
        chunks = split_chunks(text, self.tok, 100)
        self.assertTrue(all(len(self.tok.encode(c)) <= 100 for c in chunks))
        joined = "".join(chunks)
        strip = lambda s: "".join(s.split())
        self.assertEqual(strip(joined), strip(text))           # every character kept (only whitespace may move)
        self.assertTrue(any(c.endswith("ends here.") for c in chunks))
        code_chunks = [c for c in chunks if c.startswith("line ")]
        self.assertTrue(code_chunks and all("\n\n" not in c for c in code_chunks))   # line breaks stay single


class PdfArtifacts(unittest.TestCase):
    def test_systematic_ligatures_are_fixed(self):
        from common import fix_pdf_artifacts
        book = ("We ûrst deûne the üow network. Dijkstra9s algorithm is efûcient. " * 80) + "Prim9s too."   # 240 x û: systematic
        out = fix_pdf_artifacts(book)
        self.assertIn("We first define the flow network. Dijkstra's algorithm is efficient.", out)
        self.assertIn("Prim's too.", out)

    def test_rare_genuine_characters_are_kept(self):
        from common import fix_pdf_artifacts
        text = "Müller and Gödel proved it in 1931. Dijkstra9s"          # not systematic: unchanged
        self.assertEqual(fix_pdf_artifacts(text), text)

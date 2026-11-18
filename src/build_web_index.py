"""Build the search index used by the web tutor (free: runs locally, no API calls).

Each textbook is split at its Markdown headings into sections, every section into ~220-token
chunks, and every chunk is embedded with a multilingual model so that questions in Chinese or
English find the (English) textbook passages.

    python src/download_data.py        # once
    python src/build_web_index.py      # ~10-20 min on a laptop

Output: data/web_index/{embeddings.npy, chunks.jsonl, meta.json} (not committed).
"""

import argparse
import json
import re
import time
import numpy as np

from common import DATA_DIR, TEXTBOOK_DIR, clean_markdown, split_chunks

WEB_INDEX_DIR = DATA_DIR / "web_index"
BOOK_TITLES = DATA_DIR / "book_titles.json"
WEB_EMBEDDING_MODEL = "intfloat/multilingual-e5-small"   # 384-d, 100 languages; needs query:/passage: prefixes
CHUNK_TOKENS = 220
MIN_CHUNK_TOKENS = 25


_CODE_HINT = re.compile(r"//|\(\);|[{};]\s*$|\bdef |\bpublic |\breturn\b|>>>", re.M)


def is_garbled(text):
    """True for PDF-extraction garbage such as 'vMe ianchiNnewleYaronrik...' (LaTeX and code are fine)."""
    s = re.sub(r"\$\$.*?\$\$|\$[^$]*\$", " ", text, flags=re.S)
    s = re.sub(r"\\[A-Za-z]+", " ", s)
    words = re.findall(r"[A-Za-z]{2,}", s)
    if len(words) < 20 or _CODE_HINT.search(text):
        return False
    mixed = sum(1 for w in words if re.search(r"[a-z][A-Z]", w)
                and not re.fullmatch(r"[a-z]+(?:[A-Z][a-z]+)+", w)) / len(words)      # camelCase is fine
    very_long = sum(1 for w in words if len(w) > 18) / len(words)
    return mixed > 0.12 or very_long > 0.08


def sections(text):
    """Yield (heading, body) pairs, splitting at Markdown headings."""
    heading, body = "", []
    for line in text.splitlines():
        m = re.match(r"^#{1,6}\s+(.*)", line)
        if m:
            if "".join(body).strip():
                yield heading, "\n".join(body).strip()
            heading, body = m.group(1).strip()[:120], []
        else:
            body.append(line)
    if "".join(body).strip():
        yield heading, "\n".join(body).strip()


def chunk_book(path, tokenizer, titles):
    book = path.stem
    title = titles.get(book, book)
    chunks = []
    pending_heading, carry = "", ""
    for heading, body in sections(clean_markdown(path.read_text(encoding="utf-8"))):
        text = (carry + "\n" + body).strip() if carry else body
        heading = pending_heading if carry and pending_heading else heading
        if len(tokenizer.encode(text)) < MIN_CHUNK_TOKENS:      # tiny section: merge into the next one
            carry, pending_heading = text, heading
            continue
        carry, pending_heading = "", ""
        for piece in split_chunks(text, tokenizer, CHUNK_TOKENS):
            if len(tokenizer.encode(piece)) >= MIN_CHUNK_TOKENS:
                chunks.append({"book": book, "title": title, "section": heading, "text": piece.strip()})
    return chunks


def main(argv=None, embed_fn=None, textbook_dir=None, out_dir=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--books", nargs="+", help="e.g. textbook1 (default: all 20)")
    args = parser.parse_args(argv)
    textbook_dir = textbook_dir or TEXTBOOK_DIR
    out_dir = out_dir or WEB_INDEX_DIR

    import tiktoken
    tokenizer = tiktoken.get_encoding("cl100k_base")
    titles = json.loads(BOOK_TITLES.read_text(encoding="utf-8")) if BOOK_TITLES.exists() else {}
    books = sorted(textbook_dir.glob("textbook*.md"), key=lambda p: int(p.stem[8:]))
    if args.books:
        books = [b for b in books if b.stem in args.books]
    if not books:
        raise SystemExit("No textbooks found - run src/download_data.py first.")

    start = time.time()
    chunks = [c for b in books for c in chunk_book(b, tokenizer, titles)]
    dropped = sum(is_garbled(c["text"]) for c in chunks)
    chunks = [c for c in chunks if not is_garbled(c["text"])]
    print(f"{len(chunks)} chunks from {len(books)} textbooks, {dropped} garbled chunks dropped "
          f"({time.time() - start:.0f}s)")

    if embed_fn is None:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(WEB_EMBEDDING_MODEL)
        embed_fn = lambda texts: model.encode(texts, batch_size=64, normalize_embeddings=True,
                                              show_progress_bar=True)
    vectors = embed_fn([f"passage: {c['section']}\n{c['text']}" for c in chunks])

    out_dir.mkdir(parents=True, exist_ok=True)
    np.save(out_dir / "embeddings.npy", np.asarray(vectors, dtype=np.float16))
    with open(out_dir / "chunks.jsonl", "w", encoding="utf-8") as f:
        for i, c in enumerate(chunks):
            f.write(json.dumps({"id": i, **c}, ensure_ascii=False) + "\n")
    (out_dir / "meta.json").write_text(json.dumps({
        "embedding_model": WEB_EMBEDDING_MODEL, "chunk_tokens": CHUNK_TOKENS, "chunks": len(chunks),
        "garbled_dropped": dropped,
        "books": [b.stem for b in books], "built": time.strftime("%Y-%m-%d %H:%M")}, indent=2), encoding="utf-8")
    print(f"Index written to {out_dir} in {time.time() - start:.0f}s")


if __name__ == "__main__":
    main()

"""Download the GraphRAG-Bench textbook corpus (20 CS textbooks, ~38 MB of Markdown).

Source: https://huggingface.co/datasets/Awesome-GraphRAG/GraphRAG-Bench (pinned revision).
The textbooks are the retrieval corpus for v2; the benchmark questions are never indexed.

    python src/download_data.py
"""

import json
import urllib.request

from common import QUESTION_TYPES, QUESTIONS_PATH, TEXTBOOK_DIR, detect_question_type, load_questions

REPO = "Awesome-GraphRAG/GraphRAG-Bench"
REVISION = "ed2f6c2e80ddbfe4f2886ac89d520ee22b1623c4"
BASE = f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/"


def fetch(path):
    with urllib.request.urlopen(BASE + path, timeout=120) as resp:
        return resp.read()


def main():
    TEXTBOOK_DIR.mkdir(parents=True, exist_ok=True)
    for i in range(1, 21):
        out = TEXTBOOK_DIR / f"textbook{i}.md"
        if out.exists():
            continue
        out.write_bytes(fetch(f"textbooks/textbook{i}/textbook{i}.md"))
        print(f"downloaded {out.name} ({out.stat().st_size / 1e6:.1f} MB)")

    # Sanity check: our question file must be the same 1,018 questions as the official release.
    ours = {}
    for item in load_questions():
        ours.setdefault(detect_question_type(item), []).append(item["Question"].strip())
    for t in QUESTION_TYPES:
        official = [json.loads(l)["Question"].strip()
                    for l in fetch(f"questions/{t}.jsonl").decode("utf-8").splitlines() if l.strip()]
        same = sorted(official) == sorted(ours.get(t, []))
        print(f"questions {t}: official {len(official)}, ours {len(ours.get(t, []))}, identical={same}")
        if not same:
            raise SystemExit(f"{QUESTIONS_PATH.name} differs from the official {t} questions")
    print(f"Textbooks are in {TEXTBOOK_DIR}")


if __name__ == "__main__":
    main()

# Comparison: shortest-path algorithms (Dijkstra / Bellman-Ford / Floyd-Warshall)

**Question (asked in Cantonese/Chinese, 18 Nov 2026):**

> 比較 Dijkstra、Bellman-Ford 同 Floyd-Warshall 三個最短路徑演算法：分別寫出 pseudocode，用一個具體例子圖證明點解 Dijkstra 遇到負權邊會出錯，推導三者嘅時間複雜度，再喺一個 5 個頂點嘅圖上逐步追蹤 Bellman-Ford。

The question asks for four things: pseudocode for each algorithm, a concrete counterexample showing
why Dijkstra fails with negative edges, derivations of all three time complexities, and a step-by-step
Bellman-Ford trace on a 5-vertex graph. Every example graph in the answers was executed with
[`verify.py`](verify.py). Run it to reproduce every claim below.

| Answer | System | Time | Full text |
|---|---|---|---|
| **A** | CS Textbook Tutor, fast mode (RAPTOR-CGR method, DeepSeek `deepseek-flash`, thinking off) | 11.0 s | [raptor-cgr-tutor-answer.md](raptor-cgr-tutor-answer.md) |
| **B** | Perplexity, Claude Sonnet 5.5 with reasoning (web search) | not measured | [perplexity-sonnet-answer.md](perplexity-sonnet-answer.md) |
| **C** | CS Textbook Tutor, **deep mode** (same retrieval, DeepSeek thinking on) | 45.1 s | [raptor-cgr-tutor-deep-answer.md](raptor-cgr-tutor-deep-answer.md) |

Answer C was added after this comparison showed the weaknesses of A; see *What we changed*.

## Verified findings

### 1. Dijkstra counterexample: the core of the question

| | Example graph | What the answer claims | Under its **own** pseudocode | Verdict |
|---|---|---|---|---|
| A | 1st try: s→a 1, s→b 2, a→b −2 | (admits it does not fail) | correct result, so it is not a counterexample | ❌ an abandoned attempt left in the answer |
| A | 2nd try: s→a 1, s→b 2, b→a −2 | returns d[a]=1 | relaxes every edge, so it returns d[a]=**0** (correct) | ⚠️ contradicts its own pseudocode |
| B | S→A 3, S→B 4, B→A −2 | returns dist[A]=3 | relaxes every edge, so it returns dist[A]=**2** (correct) | ⚠️ contradicts its own pseudocode |
| C | A→B 1, A→C 2, C→B −2 | returns dist[B]=1 | pseudocode has `if v ∈ Q`, so it returns dist[B]=**1** (wrong, as claimed) | ✅ consistent and correct |

A subtle point that A and B both miss: with the CLRS-style pseudocode they print (relax every edge),
a 3-vertex example does not fail, because the settled vertex's distance is still overwritten. The error
only shows when it **propagates** to a vertex after it, e.g. adding A→C 1 to B's graph gives C=4 instead
of the true 3 under *every* Dijkstra variant (see `verify.py`).

### 2. Bellman-Ford trace

| | Graph | Passes until stable | Arithmetic | Teaching value |
|---|---|---|---|---|
| A | 8 edges, one negative edge | **1** (pass 2 changes nothing) | ✅ all correct | low: never shows why V−1 passes are needed |
| B | 10 edges, three negative edges | 2 | ✅ all correct | high: a distance improves again in pass 2. The last sentence is garbled ("A … 6 和 11 … 修正到 D"). |
| C | 5 edges in a deliberately "bad" order | 3 | ✅ all correct | **highest**: it explains that the edge order forces information to propagate one pass at a time |

### 3. Pseudocode and complexity

All three give correct pseudocode and the correct complexities: Dijkstra O((V+E) log V) with a binary
heap, Bellman-Ford O(VE), Floyd-Warshall O(V³) time and O(V²) space.
B and C add the array-based O(V²) Dijkstra and the Fibonacci-heap bound. B also adds two practical
comparisons: on dense graphs, and running Bellman-Ford from every vertex versus Floyd-Warshall.

### 4. Sources

| | Sources | Can a student check them? |
|---|---|---|
| A, C | 6 passages from *Introduction to Algorithms* (CLRS) and Erickson's *Algorithms*, cited inline as [1]–[6] | ✅ one click opens the exact passage in the book (*Open in textbook*) |
| B | Georgia Tech lecture slides and a personal blog (liuchuo.net) | partly: web pages, not the course textbooks |

A and C also connect the three algorithms through Johnson's algorithm, using the CLRS and Erickson passages.

## Scores (1–5, this question only)

| Criterion | A: Tutor fast | B: Perplexity (Sonnet 5.5 reasoning) | C: Tutor deep |
|---|---|---|---|
| Facts, pseudocode and complexity | 5 | 5 | 5 |
| Counterexample valid and self-consistent | 2 | 3 | **5** |
| Bellman-Ford trace (correct + instructive) | 3 | 4 | **5** |
| Clarity (no false starts or garbled text) | 2 | 4 | **5** |
| Verifiable, textbook-grounded sources | **5** | 2 | **5** |
| Speed | **11 s** | n/a | 45 s |
| Cost per answer | ≈ US$0.002 | subscription | ≈ US$0.01 |
| **Total (first five rows)** | **17 / 25** | **18 / 25** | **25 / 25** |

## Conclusion

- **Fast mode (A) loses narrowly to Perplexity (B) on this hard, multi-part question.** All of A's facts
  are right, but it shows an abandoned counterexample and uses a trace that converges after one pass.
  Without private reasoning, the model cannot check an example before it writes it.
- **Perplexity (B)** is cleaner and its trace teaches more. Its counterexample, however, does not fail
  under its own pseudocode, and its sources are web pages rather than the course textbooks.
- **Deep mode (C) gives the best answer.** Every example was verified and is consistent with its own
  pseudocode, the trace shows why multiple passes are needed, and every claim cites the textbook
  passage it comes from. The cost is time: about 45 s instead of about 11 s.

This is **one question**, not a benchmark. It shows the typical failure mode of a fast single-pass
answer (unchecked worked examples) and how deep mode fixes it. A fair accuracy comparison needs many
questions (see *Future work* in the main README).

## What we changed because of this comparison

1. **Deep reasoning mode** in the web tutor (a checkbox under the input box). DeepSeek thinks privately
   before answering, with a 16,000-token budget. Use it for derivations, traces and proofs.
2. **The fast-mode prompt** now asks for examples that are checked, consistent with the given pseudocode,
   and that show the key behaviour. On its own this did **not** fix the problem: a test answer
   contained an accidental negative cycle (see `verify.py`). That is why deep mode exists.
3. **"Open in textbook" links** on every source card open the cited passage in the book, with the
   surrounding text and a link to the full textbook, so students can check the answer themselves.
4. **Text-preserving chunking:** RAPTOR's splitter deleted every `.`, `!`, `?` and line break, so
   multi-line textbook pseudocode became one long line. The index is now built without changing the text.

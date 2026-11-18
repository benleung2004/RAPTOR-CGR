以下 pseudocode 係標準版本；摘錄主要提供性質同複雜度依據：Bellman-Ford 可處理負權邊同偵測可達負環 [1]，Dijkstra 要求非負權 [1]，Floyd-Warshall 用單次三重迴圈 [3]，Bellman-Ford 最壞 \(O(VE)\) [4]。

## 1. 三者比較

| 演算法 | 解決問題 | 負權邊 | 負環 | 策略 | 時間複雜度 | 空間 |
|---|---|---:|---:|---|---|---|
| Dijkstra | 單源最短路 (single-source shortest paths) | 不可以 | 不處理 | Greedy + 優先佇列 | binary heap: \(O((V+E)\log V)\)；Fibonacci heap: \(O(E+V\log V)\)；array: \(O(V^2)\) | \(O(V)\) |
| Bellman-Ford | 單源最短路 | 可以 | 可偵測可達負環 [1] | 重複鬆弛 (relaxation) | \(O(VE)\) [4] | \(O(V)\) |
| Floyd-Warshall | 全對最短路 (all-pairs shortest paths) | 可以 | 可用 \(D[i][i]<0\) 偵測 | Dynamic programming | \(O(V^3)\) [3] | \(O(V^2)\) |

## 2. Pseudocode

### Dijkstra

```text
DIJKSTRA(G, w, s)
    for each vertex v in G.V
        dist[v] ← ∞
        prev[v] ← NIL
    dist[s] ← 0
    Q ← all vertices, keyed by dist        // min-priority queue

    while Q ≠ ∅
        u ← EXTRACT-MIN(Q)
        for each v in G.Adj[u]
            if v ∈ Q and dist[u] + w(u,v) < dist[v]
                dist[v] ← dist[u] + w(u,v)
                prev[v] ← u
                DECREASE-KEY(Q, v, dist[v])

    return dist, prev
```

### Bellman-Ford

```text
BELLMAN-FORD(G, w, s)
    for each vertex v in G.V
        dist[v] ← ∞
        prev[v] ← NIL
    dist[s] ← 0

    for i ← 1 to |V| - 1
        for each edge (u,v) in G.E
            if dist[u] + w(u,v) < dist[v]
                dist[v] ← dist[u] + w(u,v)
                prev[v] ← u

    // 負環檢查：仍然有 tense edge 就代表有可達負環
    for each edge (u,v) in G.E
        if dist[u] + w(u,v) < dist[v]
            return FALSE

    return TRUE, dist, prev
```

### Floyd-Warshall

```text
FLOYD-WARSHALL(W)
    n ← W.rows
    D ← W                         // D[i][i] = 0；冇邊就係 ∞
    for k ← 1 to n
        for i ← 1 to n
            for j ← 1 to n
                D[i][j] ← min(D[i][j], D[i][k] + D[k][j])

    return D
```

如果完成後有 `D[i][i] < 0`，就代表有負環，最短路徑唔 well-defined。

## 3. Dijkstra 遇到負權邊會出錯

考慮有向圖：

- \(A \to B\)，權重 \(1\)
- \(A \to C\)，權重 \(2\)
- \(C \to B\)，權重 \(-2\)

來源係 \(A\)。

真正最短路：

\[
A \to C \to B = 2 + (-2) = 0
\]

所以正確答案係 \(dist[B]=0\)。

但 Dijkstra：

1. 初始化：\(dist[A]=0\)，\(dist[B]=\infty\)，\(dist[C]=\infty\)。
2. 取出 \(A\)，鬆弛：
   \[
   dist[B]=1,\quad dist[C]=2
   \]
3. 優先佇列中 \(B\) 的距離 \(1\) 比 \(C\) 的距離 \(2\) 小，所以先取出 \(B\)，並「確定」\(dist[B]=1\)。
4. 之後取出 \(C\)，嘗試鬆弛 \(C \to B\)：
   \[
   dist[C] + w(C\to B)=2+(-2)=0<1
   \]
   但 \(B\) 已經被取出，唔會再更新，所以 Dijkstra 回傳 \(dist[B]=1\)，錯。

錯誤根源：Dijkstra 假設所有邊非負，所以「最早被取出的頂點已經有最終最短路」；負權邊會破壞呢個 greedy 假設 [1]。

## 4. 時間複雜度推導

設 \(V=|V|\)，\(E=|E|\)。

### Dijkstra

用 binary min-heap：

1. 初始化：\(O(V)\)。
2. 每個頂點做一次 `EXTRACT-MIN`：\(V \cdot O(\log V)=O(V\log V)\)。
3. 每條邊最多做一次成功鬆弛同 `DECREASE-KEY`：\(E \cdot O(\log V)=O(E\log V)\)。

所以：

\[
O(V\log V + E\log V)=O((V+E)\log V)
\]

用 Fibonacci heap 可做到 \(O(E+V\log V)\)；用簡單 array 找最小值就係 \(O(V^2)\)。

### Bellman-Ford

1. 做 \(V-1\) 輪。
2. 每輪掃描所有 \(E\) 條邊，每條邊 \(O(1)\) 鬆弛。
3. 最後負環檢查再掃 \(E\) 條邊。

所以：

\[
O((V-1)E + E)=O(VE)
\]

### Floyd-Warshall

三層迴圈，每層最多 \(V\) 次，每次做 \(O(1)\) 的 `min`：

\[
O(V \cdot V \cdot V)=O(V^3)
\]

額外空間係 \(O(V^2)\) 的距離矩陣。

## 5. 在 5 個頂點圖上追蹤 Bellman-Ford

頂點：\(s,a,b,c,d\)，來源 \(s\)。  
邊的掃描次序如下：

1. \(b \to c\)，權重 \(2\)
2. \(c \to d\)，權重 \(1\)
3. \(a \to b\)，權重 \(-3\)
4. \(s \to b\)，權重 \(5\)
5. \(s \to a\)，權重 \(4\)

呢個圖係 DAG，冇負環，但有負權邊 \(a\to b\)。

初始：

\[
dist=(dist[s],dist[a],dist[b],dist[c],dist[d])=(0,\infty,\infty,\infty,\infty)
\]

Bellman-Ford 需要 \(V-1=4\) 輪。

### Pass 1

依序掃邊：

- \(b\to c\)：\(\infty+2\)，不更新
- \(c\to d\)：\(\infty+1\)，不更新
- \(a\to b\)：\(\infty-3\)，不更新
- \(s\to b\)：\(0+5=5<\infty\)，更新 \(dist[b]=5\)
- \(s\to a\)：\(0+4=4<\infty\)，更新 \(dist[a]=4\)

Pass 1 後：

\[
(0,4,5,\infty,\infty)
\]

### Pass 2

- \(b\to c\)：\(5+2=7<\infty\)，更新 \(dist[c]=7\)
- \(c\to d\)：\(7+1=8<\infty\)，更新 \(dist[d]=8\)
- \(a\to b\)：\(4-3=1<5\)，更新 \(dist[b]=1\)
- \(s\to b\)：\(5\)，不更新
- \(s\to a\)：\(4\)，不更新

Pass 2 後：

\[
(0,4,1,7,8)
\]

注意：\(b\to c\) 先用舊的 \(dist[b]=5\) 把 \(dist[c]\) 更新成 \(7\)，之後 \(a\to b\) 才把 \(dist[b]\) 改成 \(1\)，所以需要下一輪再傳播。

### Pass 3

- \(b\to c\)：\(1+2=3<7\)，更新 \(dist[c]=3\)
- \(c\to d\)：\(3+1=4<8\)，更新 \(dist[d]=4\)
- \(a\to b\)：\(4-3=1\)，不更新
- \(s\to b\)：\(5\)，不更新
- \(s\to a\)：\(4\)，不更新

Pass 3 後：

\[
(0,4,1,3,4)
\]

### Pass 4

- \(b\to c\)：\(1+2=3\)，不更新
- \(c\to d\)：\(3+1=4\)，不更新
- \(a\to b\)：\(4-3=1\)，不更新
- \(s\to b\)：\(5\)，不更新
- \(s\to a\)：\(4\)，不更新

Pass 4 冇任何更新，所以可以提早停止。

### 負環檢查

再掃一次所有邊：

- \(b\to c\)：\(1+2=3\)，等於 \(dist[c]\)
- \(c\to d\)：\(3+1=4\)，等於 \(dist[d]\)
- \(a\to b\)：\(4-3=1\)，等於 \(dist[b]\)
- \(s\to b\)：\(0+5=5>1\)，不是 tense edge
- \(s\to a\)：\(0+4=4\)，等於 \(dist[a]\)

冇任何 tense edge，所以冇可達負環。最終最短路距離：

\[
dist[s]=0,\quad dist[a]=4,\quad dist[b]=1,\quad dist[c]=3,\quad dist[d]=4
\]

對應路徑例如：

\[
s\to a\to b\to c\to d
\]

權重總和：

\[
4+(-3)+2+1=4
\]

同 \(dist[d]=4\) 一致。
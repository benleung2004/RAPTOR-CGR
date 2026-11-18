# 比較 Dijkstra、Bellman-Ford 同 Floyd-Warshall

## 直接答案

Dijkstra 要求邊權非負，用貪心加優先佇列，時間 $O((V+E)\log V)$；Bellman-Ford 容許負權並可偵測負環，時間 $O(VE)$；Floyd-Warshall 求全對最短路徑，用動態規劃，時間 $O(V^3)$ [1][3]。

---

## 1. Pseudocode

**Dijkstra**（單源，非負權）[1]：

```text
DIJKSTRA(G, w, s):
    for each vertex v in G.V:
        dist[v] ← ∞
        prev[v] ← NIL
    dist[s] ← 0
    Q ← G.V                      // min-priority queue keyed by dist
    while Q ≠ ∅:
        u ← EXTRACT-MIN(Q)
        for each v in G.Adj[u]:
            if dist[u] + w(u,v) < dist[v]:      // relaxation
                dist[v] ← dist[u] + w(u,v)
                prev[v] ← u
                DECREASE-KEY(Q, v, dist[v])
```

**Bellman-Ford**（單源，可負權，可偵測負環）[1][4]：

```text
BELLMAN-FORD(G, w, s):
    for each vertex v in G.V:
        dist[v] ← ∞
        prev[v] ← NIL
    dist[s] ← 0
    for i ← 1 to |V| - 1:
        for each edge (u,v) in G.E:
            if dist[u] + w(u,v) < dist[v]:
                dist[v] ← dist[u] + w(u,v)
                prev[v] ← u
    for each edge (u,v) in G.E:          // negative-cycle check
        if dist[u] + w(u,v) < dist[v]:
            return FALSE                 // negative cycle reachable
    return TRUE
```

**Floyd-Warshall**（全對最短路徑）[3]：

```text
FLOYD-WARSHALL(V, E, W):
    for each vertex u:
        for each vertex v:
            dist[u,v] ← w(u→v)           // ∞ if no edge, 0 if u = v
    for each vertex r:                   // intermediate vertex
        for each vertex u:
            for each vertex v:
                if dist[u,r] + dist[r,v] < dist[u,v]:
                    dist[u,v] ← dist[u,r] + dist[r,v]
```

---

## 2. Dijkstra 遇到負權邊為何出錯

Dijkstra 的貪心前提是：一旦 `EXTRACT-MIN` 取出 $u$，`dist[u]` 就係最終答案。呢個前提依賴「所有邊權非負」——因為之後任何經其他頂點嘅路徑都唔會更短 [1]。有負權邊時，呢個前提崩潰。

**反例圖**（有向）：

- 頂點：$s, a, b$
- 邊：$s \to a$ 權 $1$，$s \to b$ 權 $2$，$a \to b$ 權 $-2$

**追蹤 Dijkstra（起點 $s$）**：

1. 初始化：`dist[s]=0`，`dist[a]=∞`，`dist[b]=∞`。
2. 取出 $s$（0）。鬆弛：`dist[a]=1`，`dist[b]=2`。
3. 取出 $a$（1，最小）。鬆弛 $a\to b$：$1+(-2)=-1 < 2$，所以 `dist[b]=-1`。
4. 取出 $b$（-1）。完成。

呢個例子其實 Dijkstra 啱好冇錯。要真正出錯，需要「先取出嘅頂點之後被發現可以更短」。用以下圖：

- 邊：$s \to a$ 權 $1$，$s \to b$ 權 $2$，$b \to a$ 權 $-2$

**追蹤**：

1. `dist[s]=0`，其餘 $\infty$。
2. 取出 $s$：`dist[a]=1`，`dist[b]=2`。
3. 取出 $a$（1）。$a$ 冇出邊。**Dijkstra 此時宣佈 `dist[a]=1` 為最終值**。
4. 取出 $b$（2）。鬆弛 $b\to a$：$2+(-2)=0 < 1$，`dist[a]=0`。

但 $a$ 已經被 `EXTRACT-MIN` 取出並「定案」，標準 Dijkstra 唔會再更新已取出頂點，於是回報 `dist[a]=1`，而真正最短路徑係 $s\to b\to a = 0$。**錯誤**。

關鍵：負權邊令「已取出 = 已定案」嘅不變式失效 [1]。

---

## 3. 時間複雜度推導

**Dijkstra**：每個頂點入佇列一次、`EXTRACT-MIN` 共 $V$ 次；每條邊最多觸發一次 `DECREASE-KEY`，共 $E$ 次。用二元堆（binary heap）：$O((V+E)\log V)$。用 Fibonacci heap 可達 $O(V\log V + E)$ [1]。

**Bellman-Ford**：外層 $|V|-1$ 輪，每輪掃 $|E|$ 條邊，負環檢查再掃一次 $|E|$。總計 $O(VE)$ [1][4]。Moore 嘅改進版最壞情況仍係 $O(VE)$，但實務上通常更快 [4]。

**Floyd-Warshall**：三層迴圈，每層各 $V$ 次，共 $O(V^3)$；空間 $O(V^2)$ [3]。

| 演算法 | 單源/全對 | 負權 | 負環偵測 | 時間 |
|---|---|---|---|---|
| Dijkstra | 單源 | ✗ | ✗ | $O((V+E)\log V)$ |
| Bellman-Ford | 單源 | ✓ | ✓ | $O(VE)$ |
| Floyd-Warshall | 全對 | ✓ | ✓（對角線 $<0$） | $O(V^3)$ |

---

## 4. Bellman-Ford 逐步追蹤（5 個頂點）

**圖**（有向，起點 $s$）：

| 邊 | 權 |
|---|---|
| $s\to a$ | 6 |
| $s\to b$ | 7 |
| $a\to c$ | 5 |
| $a\to b$ | 8 |
| $b\to c$ | -3 |
| $b\to d$ | 9 |
| $c\to d$ | 7 |
| $d\to s$ | 2 |

頂點：$s,a,b,c,d$（$V=5$，所以做 $V-1=4$ 輪）。

**初始化**：`dist = [s:0, a:∞, b:∞, c:∞, d:∞]`

**第 1 輪**（按邊序 $s\to a, s\to b, a\to c, a\to b, b\to c, b\to d, c\to d, d\to s$）：

- $s\to a$：$0+6=6<∞$ → `a=6`
- $s\to b$：$0+7=7<∞$ → `b=7`
- $a\to c$：$6+5=11<∞$ → `c=11`
- $a\to b$：$6+8=14 \not< 7$，不變
- $b\to c$：$7+(-3)=4<11$ → `c=4`
- $b\to d$：$7+9=16<∞$ → `d=16`
- $c\to d$：$4+7=11<16$ → `d=11`
- $d\to s$：$11+2=13 \not< 0$，不變

結果：`[s:0, a:6, b:7, c:4, d:11]`

**第 2 輪**：

- $s\to a$：$6 \not< 6$
- $s\to b$：$7 \not< 7$
- $a\to c$：$6+5=11 \not< 4$
- $a\to b$：$14 \not< 7$
- $b\to c$：$7-3=4 \not< 4$
- $b\to d$：$7+9=16 \not< 11$
- $c\to d$：$4+7=11 \not< 11$
- $d\to s$：$11+2=13 \not< 0$

**冇任何更新** → 已收斂。

**第 3、4 輪**：同樣冇更新（可提早終止，呢個就係 Moore 改進嘅精神 [4]）。

**負環檢查**：掃所有邊，冇任何邊滿足 `dist[u]+w < dist[v]`，所以冇可達負環，回傳 TRUE。

**最終最短路徑距離**：$s=0,\ a=6,\ b=7,\ c=4,\ d=11$。

---

## 補充：三者關係

Johnson 演算法結合咗 Bellman-Ford 同 Dijkstra：先用 Bellman-Ford 計出頂點「價格」$h(v)$，再重加權 $\hat w(u,v)=w(u,v)+h(u)-h(v)$ 令所有邊非負，然後對每個頂點跑 Dijkstra [2][5]。呢個正正展示咗 Bellman-Ford 處理負權、Dijkstra 追求效率嘅分工。
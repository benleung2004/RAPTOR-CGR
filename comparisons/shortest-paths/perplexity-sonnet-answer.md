<!-- Answer from Perplexity (Claude Sonnet 5.5, reasoning), copied as received, 18 Nov 2026. -->

三個演算法各有用途。Dijkstra 最快，但只可處理非負權重。Bellman-Ford 容許負權邊，亦可偵測負環。Floyd-Warshall 一次計出所有點對的最短路徑。

## Pseudocode

**Dijkstra**（單源，邊權 ≥ 0）
```
Dijkstra(G, w, s):
  for v in V: dist[v] = ∞
  dist[s] = 0
  Q = min-priority-queue(所有頂點, key=dist)
  while Q 非空:
    u = Q.extractMin()          // u 此刻被視為「已定案」
    for (u,v) in E:
      if dist[u] + w(u,v) < dist[v]:
        dist[v] = dist[u] + w(u,v)
        Q.decreaseKey(v)
```

**Bellman-Ford**（單源，容許負權） [faculty.cc.gatech](https://faculty.cc.gatech.edu/~ladha/algo/L8.pdf)
```
BellmanFord(G, w, s):
  for v in V: dist[v] = ∞
  dist[s] = 0
  repeat |V|-1 次:
    for (u,v) in E:
      if dist[u] + w(u,v) < dist[v]:
        dist[v] = dist[u] + w(u,v)
  for (u,v) in E:                // 第 |V| 次檢查
    if dist[u] + w(u,v) < dist[v]:
      return "有負環"
```

**Floyd-Warshall**（全點對，容許負權但不可有負環）
```
FW(G, w):
  d[i][j] = 0 若 i=j；= w(i,j) 若有邊；否則 ∞
  for k in V:
    for i in V:
      for j in V:
        d[i][j] = min(d[i][j], d[i][k] + d[k][j])
```
DP 定義是：`d_k[i][j]` 代表只容許用頂點 1..k 做中間點時，i 到 j 的最短距離。

## Dijkstra 遇負權邊點解會錯

Dijkstra 的正確性靠一個假設：頂點一旦被取出，距離就不會再變短。有負權邊就破壞呢個假設。 [liuchuo](https://www.liuchuo.net/archives/1441)

例子：頂點 S、A、B，邊 S→A = 3、S→B = 4、B→A = −2。

1. 取出 S（距離 0），更新 A=3、B=4。
2. 取出 A（目前最小，3），將 A 定案為 3。
3. 取出 B（4），嘗試鬆弛 B→A：4 + (−2) = 2 < 3。但 A 已定案，標準實作唔會再處理它，結果仍然輸出 dist[A] = 3。

真正最短路徑係 S→B→A，長度 2，所以 Dijkstra 輸出錯誤。Bellman-Ford 則會在第 2 輪把 A 更新為 2，因為它唔會「定案」任何頂點。

## 時間複雜度推導

- **Dijkstra**：每個頂點 extractMin 一次，每條邊最多 decreaseKey 一次。用 binary heap 時，每次操作 O(log V)，總共 O((V+E) log V)。用 Fibonacci heap 可降至 O(E + V log V)。用陣列代替 heap 則是 O(V²)。 [faculty.cc.gatech](https://faculty.cc.gatech.edu/~ladha/algo/L8.pdf)
- **Bellman-Ford**：任何最短路徑最多有 V−1 條邊，所以做 V−1 輪就夠。每輪掃全部 E 條邊，總共 O(VE)。最後多一輪用嚟偵測負環。 [faculty.cc.gatech](https://faculty.cc.gatech.edu/~ladha/algo/L8.pdf)
- **Floyd-Warshall**：三重迴圈，每層跑 V 次，所以係 V·V·V = O(V³)。空間 O(V²)。 [faculty.cc.gatech](https://faculty.cc.gatech.edu/~ladha/algo/L8.pdf)

| | 單源/全點對 | 負權 | 偵測負環 | 時間 |
|---|---|---|---|---|
| Dijkstra | 單源 | 否 | 否 | O((V+E) log V) |
| Bellman-Ford | 單源 | 是 | 是 | O(VE) |
| Floyd-Warshall | 全點對 | 是 | 是（d[i][i] < 0） | O(V³) |

稠密圖有 E ≈ V²，Bellman-Ford 會變成 O(V³)。若要全點對，對每個源點各跑一次 Bellman-Ford 就係 O(V²E)，所以 Floyd-Warshall 通常更划算。

## Bellman-Ford 逐步追蹤

圖有 5 個頂點 S、A、B、C、D，源點係 S。邊按以下固定次序處理，更新即時生效：

| # | 邊 | 權 |
|---|---|---|
| 1 | S→A | 6 |
| 2 | S→B | 7 |
| 3 | A→B | 8 |
| 4 | A→C | 5 |
| 5 | A→D | −4 |
| 6 | B→C | −3 |
| 7 | B→D | 9 |
| 8 | C→A | −2 |
| 9 | D→S | 2 |
| 10 | D→C | 7 |

初始：S=0，其餘 A、B、C、D 都是 ∞。

**第 1 輪**
- e1：A = 6。
- e2：B = 7。
- e3：6+8 = 14 > 7，唔更新。
- e4：C = 6+5 = 11。
- e5：D = 6−4 = 2。
- e6：7−3 = 4 < 11，C = 4。
- e7：7+9 = 16 > 2，唔更新。
- e8：4−2 = 2 < 6，A = 2。
- e9：2+2 = 4 > 0，唔更新。
- e10：2+7 = 9 > 4，唔更新。

第 1 輪後：S=0、A=2、B=7、C=4、D=2。

**第 2 輪**
- e1 到 e4 都唔更新。例如 e4：2+5 = 7 > 4。
- e5：2−4 = −2 < 2，D = −2。
- e6 至 e8 都唔更新。
- e9：−2+2 = 0，唔會令 S 變細。
- e10：−2+7 = 5 > 4，唔更新。

第 2 輪後：S=0、A=2、B=7、C=4、D=−2。

**第 3 輪**：10 條邊全部唔再更新，可提早停止。

**第 4 輪（V−1 輪）及負環檢查**：都冇更新，所以冇負環。

最終結果：

| 頂點 | S | A | B | C | D |
|---|---|---|---|---|---|
| 距離 | 0 | 2 | 7 | 4 | −2 |

路徑：
- S→B→C→A（A）。
- S→B（B）。
- S→B→C（C）。
- S→B→C→A→D（D）。

這個例子說明邊的處理次序會影響收斂速度。第 1 輪 A 出現過暫時錯誤的 6 和 11，要到第 2 輪先修正到 D。

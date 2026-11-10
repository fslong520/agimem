# agimem · H3「记忆动力学」（human_memory/）

H3 测的是「记忆随时间与重复如何变化」：**重复强化**（C1）、**时间衰减 / 新旧**（C2）、
**错误纠偏**（C3）。本目录是 v2：v1（`run_human_dimension.py`，2026-11-09 首跑）被判
**度量无效**，v2 是针对病因重设的版本。两份脚本都保留，v1 的数字与病因证据见
[`../../tests/32`](../../tests/32-agimem-suite.md) §五 H3。

## 一、为什么 v1 的 C2/C3 不算数（病因，可复核）

tests/32 §五 H3.3 的最小步隔离探针（2 条条目、零 LLM、`/tmp/agimem-human-dim-probe`）给出四组证据：

| 题面变体 | v1（旧版）分数 | v2（现行版本）分数 | 谁第 1 |
|---|---|---|---|
| `夜间发布窗口现在执行的约定是哪一版` | 0.445 | 0.412 | 旧版 |
| `夜间发布窗口 现在按哪条来` | 0.474 | 0.472 | 旧版（差 0.002） |
| `夜间发布窗口`（裸主题） | 0.733 | 0.720 | 旧版（差 0.013） |
| `夜间发布窗口现在执行的版本是哪一版` | 0.465 | 0.469 | 现行（差 0.004） |

四条病因：

1. **分数由题面字面差决定**：同一对条目的分数在 0.445–0.733 之间摆动，只因题面里是否出现
   「约定 / 版本」这类词；
2. **新旧嵌入分差极小**（0.002–0.033）：`created_at`（2025-03 vs 2026-09）对排序**没有**可观测作用；
3. **第 1 归属由标签词决定**：正文里写着「旧版 / 现行版本 / 已废弃」时，谁排第 1 由这些标签词的字面差决定，
   与时间无关；
4. **top-5 命中度量对同分对无分辨力**，且两题型**共库**时 `recency` 条目会压过 `correction` 条目
   （跨臂污染）。C1 另有一病：三档（沉淀 1/3/5 条）全部 20/20 **触顶**，没有区分度。

## 二、v2 怎么修（每条对着一条病因）

| 病因 | v2 的对策 | 代码位置 |
|---|---|---|
| 标签词决定归属 | **正文逐字节相同**：一对条目 content 完全一致，一个字节都不差；标题/题面**禁用** 旧/新/版本/废弃/纠正/V2/old/new（生成期断言） | `gen_h3_v2.py` `sanity()` |
| 时间不是自变量 | **created_at 成唯一差**：旧条目 `2025-03-01T09:00:00Z`，新条目为写入当时的机械时钟 | `gen_h3_v2.py` `OLD_CREATED_AT` / `write_via` |
| top-k 无分辨力 | **改成对比较**：`later_first` = 后写条目**严格**排在先写之前；并列单独记 `tie_rate`；另报 `score_gap` 原值 | `score_h3_v2.py` |
| 跨臂共库污染 | **分库跑**：`recency` / `correction` / `repeat` 各自独立 data dir + 独立端口 + 独立 super | `run_h3_v2.py` |
| C1 触顶 | **改竞赛口径**：同一事实写 3 条（正文相同）vs 同主题干扰写 1 条，看谁 top-1 | `gen_h3_v2.py` / `score_h3_v2.py` |
| 「系统偏爱字母 a」冒充时间效应 | **反平衡**：a/b 与 旧/新 的对应按主题序号奇偶**对调** | `gen_h3_v2.py` `counterbalanced` |

## 三、`import` 会吞正文相同的条目——本轮必须绕的坑

`rsrs import` 对**正文完全相同**的条目做去重（本层实测：3 条同文一批 import →
`{"imported":1,"duplicates":2,"skipped":2}`）。而 v2 的核心设计恰恰要求正文逐字节相同。绕法是
**拆写入路径**：

- **旧条目**走 `import`：它可以显式指定 `created_at=2025-03-01`；
- **新条目**走 `remember --force`：`remember` 没有 `--created-at`，`created_at` 取写入时的机械时钟（即「现在」），
  且 `--force` 跳过 judge-then-store，不会因「高度相似」被合并/挂在父级下。

于是同一主题的一对条目：正文逐字节相同、时间相差约 20 个月、各自可被召回。C1 的重复族同理：
首条走 `import`，另外两条走 `remember --force`（否则会被去重吞掉）。

**已知代价（必须带着读数字）**：`import` 与 `remember` 是**两条不同的写入路径**，本设计把
「created_at 更晚」和「写入路径/插入更晚」绑在了一起。为此本层另跑三个对照臂把三者拆开，
结论见下节（这也是「后写先排」不能直接读成「系统认时间」的原因）。

## 四、隔离库怎么建（RSRS_DATA_DIR 法）

```python
env = {k: v for k, v in os.environ.items()
       if not k.startswith(("RSRS_", "ONEMEMORY_", "RESPIRE_"))}
env.update(RSRS_DATA_DIR="/tmp/<arm>", RSRS_RPC_PORT="16221", RSRS_SUPER="A3-0000...",
           RSRS_NO_AUTOSYNC="1", RSRS_UPDATE_CHECK="0", RSRS_ENGINE="cpu",
           RSRS_M3_DIR="~/.rsrs/models/bge-m3", RSRS_FEEDBACK="0", RSRS_ABLATE="hot")
# rsrs keygen --json → 取真 super；rsrs --runtime-internal --stop（停掉占位 super 拉起的 runtime）
# rsrs import <dump> --json / rsrs remember <body> --title <t> --force --json
# 就绪判据：探针 recall 的 embedding_model 非 null 且 status.state=ready
#   坑：retrieval_index.worker_active 恒 true，是常驻 worker 存活标志，不是待办数
```

实现见 [`isolated_lib.py`](isolated_lib.py)。**绝不碰 `~/.rsrs`**、不改全局 config、不启停宿主 runtime；
每臂独立目录 + 独立端口 + 独立 super；`RSRS_ABLATE=hot`（tests/27 纪律）。

## 五、跑法

```bash
cd agimem/human_memory
python3 gen_h3_v2.py                 # 生成 data/h3_v2_plan.json + data/h3_v2_dataset.jsonl（20×3 题）
python3 gen_h3_v2.py --verify        # 确定性重生成比对
python3 run_h3_v2.py --root /tmp/agimem-h3v2 --base-port 16221   # 三臂隔离库实跑（约 3 分钟）
python3 score_h3_v2.py               # 判分 → ../results/human-dimension-v2.json
python3 controls_h3_v2.py --root /tmp/agimem-h3v2-ctl --base-port 16231  # 三个对照臂 → ../results/h3v2-controls.json
```

产物：`../results/human-dimension-v2.json`（三臂数字与分题下钻）、`../results/h3v2-controls.json`
（对照臂）、`../results/h3v2-run-stats.json`（导入条数/索引等待/端口）。

## 六、v2 结果与读法（2026-11-09 16:36 实跑）

三臂全部一次跑通、无重试；索引均 `state=ready`、`embedding_model=m3`
（recency 40 条 / correction 40 条 / repeat 80 条，索引等待 18.9s / 19.8s / 7.2s）。

| 臂 | 指标 | k/n | 点估计 | Wilson 95% CI |
|---|---|---|---|---|
| C2 recency | `later_first` | 18/20 | **0.900** | [0.699, 0.972] |
| C2 recency | `tie_rate`（分数完全并列） | 0/20 | 0.000 | [0.000, 0.161] |
| C2 recency | `earlier_top1`（先写的排第 1） | 2/20 | 0.100 | [0.028, 0.301] |
| C2 recency | `score_gap`（后−先）均值 | — | +0.0272 | — |
| C3 correction | `later_first` | 19/20 | **0.950** | [0.764, 0.991] |
| C3 correction | `tie_rate` | 0/20 | 0.000 | [0.000, 0.161] |
| C3 correction | `earlier_top1` | 1/20 | 0.050 | [0.009, 0.236] |
| C3 correction | `score_gap` 均值 | — | +0.0089 | — |
| C1 repeat | `repeated_first`（重复族 top-1） | 19/20 | **0.950** | [0.764, 0.991] |
| C1 repeat | `repeated_beats_single` | 19/20 | 0.950 | [0.764, 0.991] |
| C1 repeat | `distractor_top1` | 1/20 | 0.050 | [0.009, 0.236] |
| C1 repeat | `family_echo_top5` 均值 | — | 1.15（3 条同文里只有约 1.15 条进 top-5） | — |

**三条对照臂（把混淆拆开）**：

| 对照 | 做什么 | 结果 | 说明 |
|---|---|---|---|
| K1 `insertion_control` | 同文、**两条都 remember**、`created_at` 都是现在，只有插入先后 | `later_first=0.850`，`tie=0`，gap +0.0229 | **主臂的 0.900 与它几乎一样** → 「后写先排」主要来自**同会话插入顺序**，不能独归因于 `created_at` |
| K2 `repeat1_control` | 只写 1 条事实 + 1 条干扰，不重复 | `fact_first=0.950`，`fact_beats_single=0.950` | **与 repeat 臂的 0.950 完全相同** → C1 的优势来自**内容相关度**，重复没有可测增益 |
| K3 `reversed_insertion_control`（**机制上不可做**） | 原打算**先** remember「新」、**后** import「旧」（插入更晚但 `created_at` 更早），以判定谁主导 | **无法执行**：`import` 对「库里已存在的同文条目」同样去重。实测 remember 3 条同文后再 import 同文 → `{"imported":0,"duplicates":3,"skipped":3}`、`local_total=3`；而 `remember` 无法指定 `created_at` | 因此 `created_at` 与插入顺序**在本设计内不可分离**，「系统是否认时间」仍未验证（不猜） |

**读法（不粉饰）**：

1. v1 的病因已被移除：正文逐字节相同、题面无标签词、成对比较、分库跑；`tie_rate=0` 说明两条不再同分，
   排序稳定偏向一方（0.85–0.95 对 0.05–0.10），**不再是「字面差抛硬币」**。
2. **但「系统认时间」仍未证实**：K1 与主臂几乎同值，说明观测到的偏向可以用「同会话后插者胜」解释；
   要把它读成 `created_at` 效应，需要 K3 反序臂的结论。
3. **`created_at` 单独效应未验证（K3 不可做）**：`import` 对已存在同文条目去重（实测 `imported 0 / duplicates 3`），
   而 `remember` 不能指定 `created_at`，两条路径无法构造「插入更晚但时间更早」的反序对。
   现有证据只能到这一步：**排序偏向稳定的后写者（0.85–0.95），但归因停在「同会话后插者胜」**。
4. **C1 的「重复强化」在检索层测不到**：K2（不重复）与 repeat 臂同为 0.950，且重复族 3 条同文里
   只有约 1.15 条能进 top-5（近重复被合并/去重）。所以 0.950 是「事实比干扰更贴题」，不是「反复经历更牢」。
   这是如实结论，没有为凑数调参。

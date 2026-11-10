# agimem 设计文档（v0 起，v1 扩集 2026-11-09）

- 名称：**agimem**（昨日 pilot 名 RespireCausalBench，2026-11-09 正式命名）
- 版本：0.1 → **0.2（v1 扩集：122 题，见 tests/30-agimem-expanded.md）**。§7 的 26 题输出是 v0/pilot 记录；v1 的树由 `gen_tree.py`（seed=20261109）确定性生成，10 树 143 节点
- 日期：设计 2026-11-08/09；正式目录 2026-11-09；扩集 2026-11-09
- 来源：工部尚书 task-2 落地的 `bench-causal/`；本文件由翰林院编修（hanlin-bianxiu-2，task-4）迁入 `respire-benchmark/agimem/`
- 双源：`bench-causal/` 为 pilot **冻结存档**，保持原貌不再改；**agimem 为唯一活跃版**。两边脚本目前同源复制，后续只改 agimem，禁止双边同时演进
- 落点：`respire-benchmark/agimem/`（跑法见本目录 README）。首评报告（v0 26 题）见 `tests/29-agimem-firsteval.md`；扩集与面板（v1 122 题）见 `tests/30-agimem-expanded.md`
- 原落点说明（pilot）：任务板写入范围当时限定 `respire-benchmark/bench-causal/`，与 `bench-semantic/`、`demo-bench-20261101/` 同属 README「归拢的独立 bench」惯例
- 依据：对比文档 `causal-memory-vs-respire-memlite-20261108.md` P0 第一条
  「自研 CausalEval 类基准：用 parent_id 树生成 DAG → 叙述成对话 → 从树结构推导 gold answer」
- 性质：**专测因果记忆，不测事实回忆**。全合成、全脱敏、gold 可机械复现。

---

## 1. 定位与既有 bench 的关系

respire 既有 `rsrs bench run` 是**事实召回**口径（hit@1/3/k、MRR、负样本噪声，
见 `respire-cli/cli/src/bench.rs:87-160`），评测集是
`{"query","expect":[...],"project?","note?"}` 且「空 expect = 负样本」
（`respire-cli/cli/src/main.rs:1672`）。

RespireCausalBench **沿用**这套 id 与负样本口径：

| 沿用项 | 出处 |
|---|---|
| id 匹配 = 8 位短 id / 完整 id 前缀双向匹配 | `respire-cli/cli/src/bench.rs:56-60` `id_match` |
| 负样本 = 空 `expect`，仍返回结果即计噪声 | `respire-cli/cli/src/bench.rs:107,125` `neg_noise` |
| JSONL 一行一题、`#` 注释可跳过 | `respire-cli/cli/src/bench.rs:36-54` `parse_evalset` |

**新增**的是因果维度：题型标签 `type`、推导表达式 `gold_expr`、干预警报 `label`、
以及四个因果专属指标（§5）。因此本评测集**不能直接喂 `rsrs bench run`**
（它不认 `type/gold_expr`），必须用本目录 `score.py` 判分；
但每一行都保证 `expect` 字段与既有 bench 语义兼容，便于对照。

## 2. 输入：合成因果树 `data/tree.json`

因果树 = Respire 记忆结构的合成投影（字段一一对应真实机制，只读源码佐证）：

| 树字段 | 对应 respire 机制 | 源码锚点 |
|---|---|---|
| `parent_id` | 强因果树（空 = root，跨设备随密文走） | `respire-core/crates/protocol/src/lib.rs:198` |
| `content` 三段式 | 【前因】【行为】【后果】 | `respire-core/crates/core-ffi/src/analysis.rs:473` 等处的三段式解析 |
| `superseded_by` / `supersedes` | 软取代（旧结论被新结论替换） | `respire-core/crates/protocol/src/lib.rs:180-182` |
| `outcome: pitfall/normal` | 干预预警用的踩坑标记（**合成树独有**，respire 现无 `prevented` 边） | —（对比文档第三节第 2 条：Respire 缺负向语义，本基准先用字段显式建模） |
| `action_key` + `data/tree.json.actions` | 动作词表，供干预题面引用 | — |

树规模：3 棵（A 构建缓存 / B 灰度发布 / C 同步延迟）、18 节点、7 个动作、
6 条噪声查询。**全部合成**：无真人姓名、无真库 id（节点 id 为本基准自造
`sntXnnnn` 8 位短 id）、无凭据、无 query-log 编号与时刻。
脱敏自检在 `gen_dataset.py sanity_checks()` 里机器执行（keyword 与全树正文互斥 +
敏感片段黑名单），跑通见 §7。

## 3. 四题型设计

统一题面骨架：`{"qid","type","query","expect","label","gold_expr","note"}`。
**gold 一律由 `causal_gold.evaluate_expr()` 从树结构算出**，`gold_expr` 是它的
调用表达式；`score.py --verify` 会用同一实现重算并逐题对账（§4）。

### ① 因果链追溯（`chain_ancestor` / `chain_descendant`）

- **题面格式**
  - 给后果查前因：`「{title}」这一步的前因链是什么？从直接前因一直追到最初的起因。`
  - 给前因查后果：`「{title}」之后引发了哪些后果？把后续的连锁反应都列出来。`
- **gold 机械推导**（`causal_gold.py`）
  - `ancestors(n)`：沿 `parent_id` 上溯至 root，**root 在前、不含自身**
    （对应 respire `show --json` 的 `ancestors` 因链序，见 `respire-cli/cli/src/main.rs:8950`）；
  - `descendants(n)`：全部严格后代，id 升序（BFS 后排序，确定性）；
  - 选题也是机械的：`CHAIN_ANCESTOR_TARGETS` 要求深度 ≥3，`CHAIN_DESCENDANT_TARGETS`
    要求子树非平凡（常量在 `gen_dataset.py`）。
- **判分口径**
  - `链命中率 hit@k`：gold 中任一 id 出现在召回 **top-k**（缺省 k=5）→ 该题命中；
    汇总 = 命中题数 / 链题数。另给 `hit@1`。
  - `链覆盖率 chain_cov`：`|召回全集 ∩ gold| / |gold|` 的题均值。
    **故意不用 top-k**：链题关心「整条链是否找齐」，长链（如 B0001 有 6 个后代）
    超出 top-5 属正常，覆盖率才反映链完整性；命中与覆盖分列，互不掩盖。

### ② 干预预警（`intervention`，intervention 型）

- **题面格式**：`我马上要「{actions[key].desc}」，历史上这么做踩过坑吗？先给我个预警。`
- **gold 机械推导**：`intervention(action_key)` =
  `label = WARNING 当且仅当存在 action_key 相同且 outcome=="pitfall" 的节点`；
  `expect = 这些踩坑节点 id（升序）`，SAFE 时 `expect=[]`。
  数据集里 3 个 WARNING（`hot_patch_peak`/`config_reload`/`force_push_rebuild`）
  与 3 个 SAFE（`canary_10pct`/`gradual_rampup`/`shard_queue`）动作，比例由常量表固定。
- **判分口径**（判分只看召回 id 映射回树后的 `outcome`，不看分数文本）
  - 预测标签：`pred = WARNING 当且仅当任一召回 id 解析为 outcome==pitfall 的节点`，否则 `SAFE`；
  - `预警准确率 = 预测标签 == gold label 的题数 / 题数`，并输出混淆矩阵 TP/FP/FN/TN
    （正类 = WARNING）。FP = 给 SAFE 动作报了警（误报），FN = 踩坑动作没报警（漏报）。
  - 说明：这是「检索出的条目是否为踩坑条目」的判定，**不含 LLM 文本判读**；
    LLM 端到端答题口径列为后续扩展（§8）。

### ③ 软取代感知（`supersession`）

- **题面格式**：`关于「{旧结论 title}」这个结论，现在还成立吗？当前有效的结论是哪条？`
- **gold 机械推导**：`supersession(旧节点) = [旧节点.superseded_by]`（空则该节点不出题）；
  数据集覆盖树内**全部**带 `superseded_by` 的旧结论节点（`SUPERSESSION_TARGETS` 即筛出结果）。
  旧节点 id **不算**正确答案。
- **⚠ 口径声明（必读，对应 T1 报告 2.7-1 的 oracle 注入机关）**：
  本 pilot 的取代边是 **oracle 口径**——`superseded_by` 由生成器在 `data/tree.json`
  里**显式种入**（相当于 CausalEval 的 `seed_oracle_supersession` 直接 UPDATE 边），
  测的是「**系统能否用好已种的取代标记**」，**不是**「系统能否自动发现证伪」。
  另一口径「distill 蒸馏时自动产生取代边」在本 pilot **未实现、未测**，
  两类结论**不得并表**。题面 `note` 字段逐题写死「【oracle 口径】」字样，
  输出报告引用本基准时必须带该口径标签。
  （文本侧辅证：新结论条目须命中中文证伪信号词表 `FALSIFY_SIGNALS_CN`，
  由 `gen_dataset.py sanity_checks()` 机器断言，防「取代」在文本上无从体现。）
- **判分口径**（按召回结果三态）
  - `current`（正确）：召回含新结论 id；**或**召回含旧 id 且其 `superseded_by` 标记非空
    （系统明确告知「已被取代」也算感知正确——对齐 recall 输出里的
    `[superseded]` 标记与 `details[].superseded_by`，见 `respire-cli/cli/src/main.rs:8727,8735`）；
  - `stale`（错）：只召回旧 id 且无取代标记 → 旧结论被当现行结论；
  - `missing`（错）：两者都没召回。
  - `取代正确率 = current / 题数`，另报 stale、missing 计数。

### ④ 负样本 / 噪声（`negative`）

- **题面格式**：直接使用 `data/tree.json.noise_queries[].query`（6 条，
  主题与三棵树完全无关：极地除冰/粤语声调/深海热泉/弗拉门戈/青稞仓储/斯瓦希里转写）。
- **gold 机械推导**：`negative → expect = []` 恒空；
  同时生成期断言每条 `keyword` **不出现在全树任何 title/content**（机器证明「无关」，
  不靠人拍脑袋说它无关）。
- **判分口径**：`负样本噪声率 = 召回非空的负样本题数 / 负样本题数`（越低越好）。
  `--min-score t` 可先滤掉低分召回再计噪声（对应 recall 的阈值闸；
  阈值权衡实测见记忆条目 3b9187a4：缺省 0.25 有噪声、0.99 正样本全空——
  故本基准把阈值做成显式可扫参数，不写死）。

## 3.5 对 T1 借鉴清单的吸收（逐条落实 / 不采纳）

依据：`research/causal-memory调研与respire借鉴-20261108.md` §2.7、§2.5、P0-1。
本 pilot 只吸收「口径与可复现骨架」，不把 CausalEval 七类题整表搬过来。

| # | T1 要求 | 处理 |
|---|---|---|
| 1 | C7 的 100% 含 oracle 注入：`seed_oracle_supersession`（报告引 main.rs:1294-1331）测的是「用好已种边」不是「自动发现证伪」 | **落实**。§3③ 显式声明本基准 `superseded_by` 为 **oracle 口径**（生成器在 `data/tree.json` 种入），distill 自动发现口径**未实现、未测、不得并表**。题面 `note` 逐题写「【oracle 口径】」（`dataset/causal_evalset.jsonl` q19、q20） |
| 2 | 造题骨架可参考固定 11 节点语义链；seed 确定性、零 LLM 出题；叙事校验用「半数 key-token + 证伪信号词表」 | **部分落实**。零 LLM、同树逐字节复现已落地（`gen_dataset.py` 排序后编号）。证伪信号词表落地为中文最小集 `FALSIFY_SIGNALS_CN`，生成期断言新结论必须命中。**不采纳** 11 节点骨架与半数 token 叙事校验：本基准节点是 Respire 三段式树，不是 CausalEval 的 bad/fail/fix/preventer 角色图；pilot 题面是模板句，没有 LLM 叙事层，半数 token 校验无对象。固定角色骨架与 LLM 叙事列为 §8 后续项 |
| 3 | 补 search-only 零 LLM 证据命中率、distractor 抑制误报率 | **落实**。§5 全部指标声明为 search-only 零 LLM；`chain_hit@k` 即证据命中率；`false_alarm_rate` = SAFE 题上报 WARNING 的比例（分母 = SAFE 题数）。`selftest.py` 断言 perfect=0.0、adversarial=1.0 |
| 4 | 同题面同判分跑「有树 vs 无树/BM25-only」，只报 Δ | **工具落实、实测臂未跑**。`score.py --delta` 输出六项 `Δ = 本臂 − 对照臂`，并用 perfect vs adversarial 两份合成预测验证算术（§7）。**真实**「有树 recall vs 无树/BM25-only」两臂未采集，Δ 的因果归因**未验证**（§8） |

P0-1 其余映射（C3 反事实、C4 抑制句式、C5 时序、C6 跨树迁移、10 图 × 7 问 = 70 题、从真库抽踩坑模板）**本 pilot 不采纳**：任务验收只要四题型 + ≥20 题 + 生成/判分自洽，且写入范围禁止碰真库。它们留在 §8，不冒充已实现。

## 4. 造题流水线与 gold 复现保证

```
data/tree.json ──> gen_dataset.py ──> dataset/causal_evalset.jsonl
      │                                     │
      └──────── score.py --verify <─────────┘   （同一 causal_gold.evaluate_expr 重算对账）
```

- `gen_dataset.py`：树 → 题面模板 → `evaluate_expr` 算 gold → 落 `gold_expr` →
  自检（题量 ≥20、四题型齐全、expect id 在树内、负样本 keyword 与树互斥、敏感片段黑名单）→
  按（题型, query）排序后编号 `q01..qNN`，**同一棵树重复运行产出逐字节相同**。
- `score.py --verify-only`：逐题用 `gold_expr` 从树重算 `expect/label`，
  与落盘值不一致即 `exit 1`。这是「gold 可机械复现」的机器证据——
  任何人改了树或改了数据集而没同步另一边，对账立刻红。

## 5. 指标汇总

**全部指标均为 search-only 零 LLM 口径**（只看召回 id 是否落进 gold，
不经过任何答题模型/判官）——对应 CausalEval 的 `--search-only` 证据命中模式
（T1 报告 2.5-2）。gold 匹配用 **id 空间**：本基准 id 是合成稳定短 id，
树/数据集/预测三处同源，不存在 CausalEval 那种「chunk id 与条目 id 空间不一致」问题
（其审计 #1 把 evidence_hit 从 id 空间改文本空间，71%→97%；本基准因同源无需改，
但若日后接真库，必须改文本空间——见 §8）。

| 指标 | 定义 | 题型 |
|---|---|---|
| 链命中率 `chain_hit@k`（k 缺省 5） | top-k 内含任一 gold 的题占比（即因果证据命中率） | ① |
| 链命中率 `chain_hit@1` | top-1 内含任一 gold 的题占比 | ① |
| 链覆盖率 `chain_cov` | 召回全集对 gold 的平均覆盖率 | ① |
| 预警准确率 `intervention_acc` | 预测标签 == gold 标签的题占比（附 TP/FP/FN/TN） | ② |
| **抑制误报率 `false_alarm_rate`** | gold=SAFE 的 distractor 题（什么都没被阻止）却报 WARNING 的比例，分母 = SAFE 题数 | ② |
| 取代正确率 `supersession_acc` | 判为 current 的题占比（附 stale/missing）；**oracle 口径** | ③ |
| 负样本噪声率 `negative_noise_rate` | 空 gold 却有召回的题占比（越低越好） | ④ |

**两臂对照**：`score.py --delta <对照臂预测>` 在同题面、同判分下输出
`Δ = 本臂 − 对照臂` 六项指标（正向指标 Δ>0 为好，误报/噪声 Δ<0 为好）。
约定臂位：**A 臂 = 有树**（parent_id 链 + superseded_by 标记全量可用）、
**B 臂 = 无树 / BM25-only**（同一批文本，去掉树结构与取代标记）。
只有 Δ 才可归因到「因果结构」，单臂绝对分不可归因
（对齐 T1 报告 2.5-5「同一对话、同一判官，delta 才可归因」）。

## 6. 判分脚本输入与接真实 recall 的方法

`score.py --predictions <jsonl>` 接受三种形状（自动归一）：

1. 标准行：`{"qid":"q01","query":"...","hits":[{"id","score","superseded_by"}]}`
2. `rsrs recall --json` 的 ResultEnvelope：`{"summary":..., "details":[{"score","entry":{"id"},...}]}`
3. 纯 hits 数组

join 规则：优先 `qid`，其次 `query` 原文精确匹配；缺预测的题
**缺省按 0 分严判**，`--partial` 时剔除出分母（两种行为都有断言覆盖，§7）。

**接真实 recall 的采集步骤（本 pilot 未执行，标「未验证」）**：
在合成库上导入树节点 → 逐题 `rsrs recall "<query>" --json` → 把 `details` 归一成
预测行 → `score.py --predictions` 判分。之所以不在本任务里跑：
写入范围仅限 `bench-causal/`，且不许动真库/线上配置；
真实库导入与 recall 端到端跑通留给后续任务。

## 7. 自洽验证（pilot 已实测；agimem 目录复跑见 tests/29）

下列输出是 2026-11-09 在 `respire-benchmark/bench-causal/` 的 pilot 记录。agimem 目录的复跑命令与退出码以 `tests/29-agimem-firsteval.md` 为准，不把本节当成新目录的实测证据。

```
$ python3 gen_dataset.py
[gen_dataset] 写出 dataset/causal_evalset.jsonl: 26 题
  - chain_ancestor: 6 / chain_descendant: 6 / intervention: 6 / supersession: 2 / negative: 6
[gen_dataset] 脱敏自检通过（noise keyword 与全树正文互斥；无敏感片段）   # exit=0

$ python3 score.py --verify-only
[verify] OK — 26 题 gold 全部由树结构重算一致                          # exit=0

$ python3 selftest.py
... 42 项断言全 PASS、0 FAIL ...
SELFTEST PASS — 生成 → gold 对账 → 判分 全链路自洽                     # exit=0
```

fixture 与判分输出（合成 recall，非真实系统；2026-11-09 复跑）：

```
$ python3 score.py --predictions fixtures/perfect.jsonl
[因果链追溯] n=12 链命中率 hit@5=1.000 hit@1=1.000 链覆盖率=1.000
[干预预警]   n=6  预警准确率=1.000 混淆 TP/FP/FN/TN=3/0/0/3  抑制误报率=0.000 (分母 3)
[软取代感知] n=2  取代正确率=1.000 current/stale/missing=2/0/0
[负样本噪声] n=6  负样本噪声率=0.000 噪声题数=0/6

$ python3 score.py --predictions fixtures/adversarial.jsonl
[因果链追溯] n=12 链命中率 hit@5=0.000 链覆盖率=0.000
[干预预警]   n=6  预警准确率=0.000 混淆 TP/FP/FN/TN=0/3/3/0  抑制误报率=1.000 (分母 3)
[软取代感知] n=2  取代正确率=0.000 current/stale/missing=0/2/0
[负样本噪声] n=6  负样本噪声率=1.000 噪声题数=6/6

$ python3 score.py --predictions fixtures/perfect.jsonl --delta fixtures/adversarial.jsonl
Δ chain_hit_at_k +1.000 / chain_cov +1.000 / intervention_acc +1.000
Δ false_alarm_rate -1.000 / supersession_acc +1.000 / negative_noise_rate -1.000
```

`selftest.py` 覆盖 5 个 fixture：`perfect`（全对）、`adversarial`（全错）、
`mixed`（每题型前半对后半错，验聚合口径 = floor(n/2)/n）、
`low_noise`（负样本命中但 score=0.1，验 `--min-score 0.5` 把噪声 1.0→0.0）、
`hand`（4 条手工写死记录：命中 gold 第 2 项 → hit@5 且 coverage=1/3、
踩坑节点 → WARNING 判对、旧结论带 `superseded_by` 标记 → current、负样本空召回）。
另断言：缺预测不带 `--partial` 时按 0 分严判；抑制误报率 perfect=0 / adversarial=1；
`--delta` 六项差值与上表一致。

## 8. 已知局限 / 未验证项

1. **未接真实 recall 端到端**：§6 采集步骤未跑，本 pilot 只证明
   「生成 → gold 对账 → 判分」自洽；真实系统分数未验证。
2. **干预预警只判「召回条目是否踩坑」**，不判 LLM 是否给出 DANGER 措辞；
   端到端答题判分（含 LLM judge）未实现。
3. **`outcome: pitfall` 是合成树上的显式字段**，respire 真库没有该字段——
   真库版需要先落 `prevented`/踩坑语义（对比文档 P0 第二条），否则只能退化为
   从【后果】段文本抽取，抽取器未实现。
4. **题量 26 为 pilot 规模**（causal-memory CausalEval 是 140q/20 图）；
   扩图、加链长、加噪声配比的规模化生成未做。
5. 题面为模板句式，存在模板过拟合风险；句式多样化未做。
6. `--min-score` 缺省 0（不滤），与 recall 实际阈值闸的对齐需真机标定。
7. **取代题只有 oracle 口径**。distill 自动发现证伪未测，不得把本基准的取代正确率读成「能自动发现过时结论」。
8. **`--delta` 只验证了合成两臂的算术**。真实「有树 vs 无树/BM25-only」未采集，因果归因未验证。
9. **未采纳项**（见 §3.5）：CausalEval 固定 11 节点角色骨架、LLM 叙事 + 半数 key-token 校验、C3/C4/C5/C6、70 题规模、从真库抽踩坑模板。

## 9. 证据清单

| 结论 | 证据 |
|---|---|
| evalset 格式与 id 匹配语义 | `respire-cli/cli/src/bench.rs:23-34,56-60` |
| 负样本噪声指标既有实现 | `respire-cli/cli/src/bench.rs:107,113-160` |
| recall JSON 含 score/entry/ancestors/superseded_by | `respire-cli/cli/src/main.rs:8727,8735` |
| show JSON 含 ancestors/children 因果视界 | `respire-cli/cli/src/main.rs:8950` |
| MemoryEntry 的 parent_id / superseded_by | `respire-core/crates/protocol/src/lib.rs:180-182,198` |
| 26 题生成 + 脱敏自检 | `dataset/causal_evalset.jsonl`，`gen_dataset.py` 输出（§7） |
| gold 机械复现 | `score.py --verify-only` 输出（§7） |
| 判分脚本正确性 | `selftest.py` 42 断言 PASS、0 FAIL（§7，2026-11-09 复跑） |
| 软取代为 oracle 口径、非自动发现 | 本文 §3③、§3.5；`dataset/causal_evalset.jsonl` q19/q20 的 note |
| 抑制误报率与两臂 Δ 的判分算术 | `score.py` `false_alarm_rate` / `--delta`；`selftest.py` 第 10 组；§7 输出 |
| 与 causal-memory P0 的对齐 | 附件对比文档「六、可借鉴清单 P0 第一条」（只读）；T1 报告 §2.7、P0-1 |

# agimem 评测说明与指标字典

> 面向外部读者。本文件是 agimem 评测套件的门面与指标权威说明：读它可以知道每个数字**怎么算的、能读成什么、不能读成什么**。
> 文中每个数字都对应仓内一个产物文件；找不到出处的写「未验证」。
> 最后核对：2026-11-10（数字对应各层产物落盘时间，见各节出处）。

---

## 一、这是什么

agimem 是给 respire / rsrs 这类**本地记忆系统**打分的自研评测套件，全部题目与语料**合成生成**，gold（标准答案对应的条目）由构造机械推导，采集侧 **search-only、零 LLM**：

- 出题：`gen_*.py` 用固定 seed 生成语料树与题目，落 `data/` 与 `dataset/`；
- 入库：合成节点写进**隔离 rsrs 库**（独立数据目录 + 独立端口 + 独立 super，绝不碰 `~/.rsrs`）；
- 采集：逐题调 `rsrs recall`（隔离库）或 `rsrs bench run`（真库，只读）；
- 判分：`score_*.py` 拿「召回 id 序列」与 gold 比对，不调用任何大模型；
- 统计：比例类指标一律 Wilson 95% 区间（`z=1.959963984540054`）。

目标不是「和某个外部榜单比大小」，而是回答一个更窄的问题：**这套记忆系统在「像人一样记事、记事之后会推理」这件事上，缺口具体在哪一格。**
所以整包的输出形态是**逐格上报 + 诊断率**，不是一个总分。

---

## 二、为什么有两个维度，且不合成总分

| 维度 | 问题 | 层 | 判据 |
|---|---|---|---|
| **M 机器向** | 这套系统**能不能用**（召回准不准、快不快、往上下文里塞多少 token） | M1–M3 | 真库、真 evalset、只读 |
| **H 类人向** | 它**像不像人**（记忆心理学的六件事：前瞻、错误记忆、遗忘、来源、时间线、重构……） | H1–H9 | 全合成语料、隔离库、gold 机械 |

**两者并列上报，不合成单一总分。** 理由：

1. 量纲不同。M1 是「题目在不在前 20 条」，H6 是「数据库天然做不到、人类天然做得到」的格子，二者没有可加的公共单位。
2. 参考系不同。M 层对着真库（5,565 条真实条目），H 层对着几百条合成节点。任何加权系数都是主观选择。
3. 结论相反也不矛盾。一个系统可以召回很强（M1 高）而类人度很低（H6 低），这正是本套件要暴露的东西。

**特别声明：H4 的 0.343 只是「层内加权分」。** 它是 H4 六个刁钻类型的加权平均（权重 T1 0.15 / T2 0.20 / T3 0.20 / T4 0.15 / T5 0.15 / T6 0.15，见 `tricky/score_tricky.py:54` 与产物 `weights` 字段），**不是**跨层总分，**不能**与其他层的数字相加、平均或排名。H6 的 0.4861、H9 的 0.4826 同理，都只是各自层内的等权平均。

---

## 三、层目录

产物路径均相对 `respire-benchmark/agimem/`。题量/语料量取自各层产物文件，非估计。

### M 机器向（真库只读）

| 层 | 测什么 | 题量 | 产物 |
|---|---|---|---|
| M1 召回 | 300 题真库 evalset 的 hit@1/3/5/10/20 与 MRR | 300 题 / 真库 5,565 条 | `machine/results/machine-scorecard.json` |
| M2 速度 | runtime 内部延迟、端到端墙钟、冷启动 | 300 次查询 | 同上 `m2` 段 |
| M3 成本 | 单题注入上下文的 token 数（两套 tokenizer 口径） | 300 题 | 同上 `m3` 段 + `machine-scorecard.md` |

### H 类人向（合成语料、隔离库）

| 层 | 测什么 | 题量 / 语料 | 主要产物 |
|---|---|---|---|
| H1 端到端 | LoCoMo conv-0，召回→答题→LLM 判分全链 | 199 题 / 19 段 session | `results/locomo-e2e.json` |
| H2 因果 | 链式祖先/后代、干预告警、取代、负样本 | 122 题（旧）+ 236 题（扩集）/ 332 节点 | `results/causal-236-isolated.json`、`results/causal-supersession-v2.json` |
| H3 记忆动力学 | 新近性、纠偏、重复强化（三臂分库对照） | 每臂 20 题 / 40–80 条 | `results/human-dimension-v2.json`、`results/h3v2-controls.json` |
| H4 刁钻工作场景 | T1 抗干扰 / T2 同名异事 / T3 隐含约束 / T4 旧结论失效 / T5 跨时间一致 / T6 转述 vs 实测 | 132 题（各 22）/ 748 节点；扩集 264 题 | `tricky/results/tricky-isolated-panel.json`、`tricky-264-isolated.json` |
| H5 多语言 | D1 语言公平、D2 跨语言检索、D3 跨语言同事实 | 576 题 / 多语言事实集 | `i18n/results/i18n-score.json`、`d3-important-summary.json` |
| H6 六道分水岭 | 前瞻 / 错误记忆 / 主动遗忘 / 来源监控 / 时间线 / 重构性 | 141 题 / 278 节点 | `humanlike2/results/h6-isolated.json` |
| H7 跨跳与诚实 | 多跳链 / 混跳辨析 / 缺证据三档 / 增广认同 | 80 题 / 144 节点 | `h7/results/h7-isolated.json` |
| H8 记忆动力学（扩建） | 一次观察泛化 / 跨间隔召回 / 远期不被淹没 / 增量编辑 | 64 题 / 192 节点 | `h8/results/h8-iso-panel.json` |
| H9 推理与元认知 | 因果归因→处方 / 反事实 / 动态更新 / 压缩摘要 / 元认知 / 跨来源置信 | 96 题 / 232 节点 | `h9/results/h9-score.json` |

**gold 怎么来（全部零 LLM）**：

- M1 用 evalset 自带的 `expect` id；
- H1 用 LoCoMo 标注的答案，答案对不对由外部 LLM judge 判（**这一层不是零 LLM**，见 §四 H1 条目）；
- H2 用因果树结构（父边、`outcome=pitfall` 标记、`superseded_by` 边）；
- H3 用「正文逐字节相同、只有 `created_at` 不同」的成对条目 + 标题 token 比对；
- H4 用题型构造（诱饵组、重名组、`implicit` 标记、`superseded_by`、链条尾、证据级降序）；
- H5 用「同一事实 × 四种语言」的对照矩阵；
- H6 / H7 / H8 / H9 用 `h6_gold.py` / `h7_gold.py` / `h8_gold.py` / `h9_gold.py` 的 `evaluate_expr()`，从 `gold_expr`（构造时写死的表达式）在**节点角色/属性**上机械求值，`verify_gold()` 再逐字段对账。

---

## 四、指标字典（主体）

通用约定：

- **hit@k**：「排名第 0..k−1 位里出现 gold」记 1，否则 0；对 n 题取平均。id 匹配一律**前缀双向匹配**（合成 id 与真库 UUID 的映射见 §五）。
- **Wilson**：`wilson_ci(k, n, z=1.959963984540054)`，各 `score_*.py` 内各有一份同名实现（`agimem/score.py:43`、`tricky/score_tricky.py:62`、`humanlike2/score_h6.py:45`、`h7/score_h7.py:42`、`h8/score_h8.py:40`、`h9/score_h9.py:36`、`machine/run_machine.py:123`）。**唯一例外是 H4**：它用分层 bootstrap（`tricky/score_tricky.py:80 bootstrap_ci()`，reps=2000、seed=20261109），产物里 `method` 字段写的是 `stratified-bootstrap`，不是 Wilson。
- 「能读成」= 该数字支持下的事实；「不能读成」= 常见误读。

### M1 召回（`machine/run_machine.py:171 m1_from_raw()`）

| 项 | 内容 |
|---|---|
| 定义 | 300 题真库 evalset 的 top-k 命中率与平均倒数排名 |
| 算法 | 读 `rsrs bench run` 报告里每题 `rank`；`hit@k = #{rank != None 且 0 ≤ rank < k} / n`；`MRR = mean(1/(rank+1))`，未命中记 0 |
| n | 300（真库 5,565 条，evalset `bench-recall/evalset_l2train300.jsonl`，split L2-train seed=20261109） |
| CI | Wilson |
| 实测 | **hit@20 = 0.8767** [0.8346, 0.9092]（k=263/300）；hit@1 0.2600；hit@5 0.6467；hit@10 0.8000；**MRR 0.4264**；miss 37 |
| 能读成 | 真库上「答案条目是否进得去前 20 条」；0.8767 说明**候选池阶段基本能捞回** |
| 不能读成 | ① 不能读成「答对率」——hit@20 是检索上限，不是回答正确率；② hit@1 只有 0.26，说明**排序阶段很弱**，两者必须一起看；③ 与 LoCoMo / Mem0 等外部榜单不可横比（题库、切分、语料全不同） |

出处：`machine/results/machine-scorecard.json` `.m1.*`（生成 2026-11-09T16:32:33+0800）。

### M2 速度（`machine/run_machine.py:142 lat_stats()`、`:288 measure_cold()`）

| 项 | 内容 |
|---|---|
| 定义 | 三个互不相同的延迟口径 + 冷启动 |
| 算法 | ① `runtime`：bench 报告 `params.p50_us/p95_us`（runtime 内部计时，不含 CLI 进程启动）；② `e2e`：300 次单题 `rsrs bench run` 的墙钟；③ `cold`：停 runtime → spawn `rsrs --runtime-internal` → 首个查询完成（含模型加载） |
| n | runtime/e2e 各 300；cold 3 次取中位 |
| CI | 分位数（`quantile()`，`:135`），非比例指标不给 Wilson |
| 实测 | runtime **p50 1.064 s / p95 1.472 s**；e2e p50 1.300 s / p95 1.934 s / **p99 2.453 s**、max 6.192 s；冷启动 **9.932 s**（三次 9.772 / 9.936 / 9.932） |
| 能读成 | runtime 侧单次检索的量级；冷启动上限约 10 s |
| 不能读成 | ① 冷启动是**隔离库 20 条**的结果，**不是真库数字**；② e2e 含 CLI 进程启动与序列化，**不要**拿它当 runtime 延迟；③ 机器为 i5-8400 / 23.2 GB，换硬件不可套用 |

出处：`machine-scorecard.json` `.m2.*`。

### M3 成本（`machine/run_machine.py:249 m3_tokens()`）

| 项 | 内容 |
|---|---|
| 定义 | 单题「注入上下文」的 token 数：`query + 各召回条 title + 各条 content + 骨架 prefix/suffix + 每条 [i] 前缀` |
| 算法 | `rsrs export` 全文落 `/tmp`，按 `bench run` 的 id 序列对齐，用两套 tokenizer 分别计数后取分位（`:275-283`） |
| n | 300 题；`missing_ids = 0` |
| CI | 分位数（p50/p95/mean），非比例指标不给 Wilson |
| 实测 | bge-m3 口径：**中位 10,942**、p95 14,372、均值 11,218.21、合计 3,365,462；对照 cl100k_base 口径同表 |
| 能读成 | 接 LLM 时每题要付费的上下文规模量级 |
| 不能读成 | ① 骨架**未含客户端 system prompt**，接入方须自行加；② 表内不含 API 单价（本地自托管，`--price-per-1k` 默认 0），**不能读成成本金额** |

出处：`machine/results/machine-scorecard.md:44` 表行 + `machine-scorecard.json` `.m3.aggregate`。

### H1 端到端（LoCoMo conv-0，`locomo/run_e2e.py`、`locomo/judge_pass.py`、`locomo/session_hit.py:32`）

| 项 | 内容 |
|---|---|
| 定义 | 召回 top-5 → LLM 答题 → LLM judge 打分（0/1 或部分分）的端到端正确率；另有「session 命中」检索指标 |
| 算法 | 每题两判取均；`overall.mean` 为 199 题均值 ± 标准误（`mean_ci()`，`run_e2e.py:161`）；session 命中用 Wilson（`session_hit.py:32`） |
| n | 199 题 / 19 段 session；session-hit 分母 197（2 题无 session 标注） |
| CI | 均值给 se + 95% CI（正态）；session-hit 给 Wilson |
| 实测 | overall **0.5603**（se 0.0319，n=199）、非对抗 0.6941；**session-hit@5 0.9036** [0.8543, 0.9374]（178/197）；unknown 率 0.2965；分类 multi-hop 0.5156 / temporal 0.7500 / open-domain 0.3077 / single-hop 0.8179 / adversarial 0.1277 |
| 能读成 | 「检索基本能捞出正确 session，但答对只有一半多」；adversarial 类 0.1277 是明确弱项 |
| 不能读成 | ① **这一层不是零 LLM**：答题与判分都走外部模型（magpie 网关 `glm-5.3-flash`，2 judge），分数含 judge 噪声；② **与历史 0.6991 不可并表**：网关、判次、模型都换了；③ overall 是 LLM 判分均值，不是检索命中率 |

出处：`results/locomo-e2e.json`（`.env` 段记录了网关与判次）。

### H2 因果（`agimem/score.py:196 score()`）

| 指标 | 定义 / 算法（函数行号） | n | 实测 | 能读成 | 不能读成 |
|---|---|---|---|---|---|
| 链 hit@k | top-k 内是否出现链上任一 gold；`first_gold_rank()`（`score.py:189`），`score()` 中 `cg.CHAIN_ANCESTOR/DESCENDANT` 分支（`:225-234`） | 136（236 扩集） | **0.7353** [0.6554, 0.8022]（100/136）；hit@1 0.2941 | 整链要素是否进得了前 5 | ① 不是「跳数推理正确率」；② 有**自命中**污染：题目问的就是库里某条，检索天然把题面原条排前（剔除自身后 hit@1 0.6471、hit@5 0.7353） |
| 链覆盖率 | 召回**全集**（不限 top-k）里 gold 链节点占比（`:229-234`） | 136 | 0.2969 | 一条链被找齐的比例 | 不能读成排序质量 |
| 干预准确率 / 误报率 | top-k 内若含 `outcome=pitfall` 节点判 `WARNING`，与 gold 标签比（`:235-247`） | 40（警告 20 / 安全 20） | acc 0.600；**误报 0.800** | 告警判定的召回/误报平衡 | 误报 0.800 说明「见坑就喊」，**不能读成预警能力** |
| 取代准确率 | 召回含当前结论，或旧结论带 `superseded_by` 标记 → `current`（`:248-271`） | 两条口径各 20 | **import 通道 0.000**（20 全 stale）；**`remember --supersedes` 真写边 1.000** [0.8389, 1.000]（20/20） | 写边带上取代标记后，读侧**完全能**认出旧条目 | ① **两个数不能并表**：0.000 的根因是 `import` 硬编码清空 supersedes 字段（`app-core/service.rs:1739-1740`），不是读侧缺陷；② 1.000 是 n=20 的小样本 |
| 负样本噪声率 | gold 恒空，召回非空即 `noisy`（`:272-274`） | 40 | 0.325 | 无关问题上的「乱抓」比例 | 不能读成假阳性率（题目本就无答案） |

出处：`results/causal-236-isolated.json`、`results/causal-supersession-v2.json`。

### H3 记忆动力学 v2（`human_memory/score_h3_v2.py:59 score_arm()`）

| 指标 | 定义 / 算法 | n | 实测 | 能读成 | 不能读成 |
|---|---|---|---|---|---|
| `later_first`（recency / correction） | 成对条目**正文逐字节相同**、仅 `created_at` 不同；gold = 较晚那条；`rank_of()`（`:52`）比对标题，命中 top-1 记 1（`:93-121`） | 每臂 20 | recency **0.900** [0.699, 0.972]（18/20）；correction **0.950** [0.764, 0.991]（19/20） | 同文异时两条都在库里时，系统**倾向给较新那条** | ① 三条对照限定死：K1 插入顺序对照 **0.850** ≈ 主臂 → 优势主要来自**同会话插入顺序**；② K3 反序臂机制不可做 → `created_at` 与插入顺序**不可分离**，「系统是否真认时间」**仍未验证** |
| `repeated_first` / `repeated_beats_single` | 重复写 3 次的条目 vs 只写 1 次的条目，谁排前 | 20 | 均 **0.950** [0.764, 0.991] | 重复写入的条目确实更容易被召回 | K2（只写一次）也到 0.950 → **重复无增益**，此处分数来自内容本身 |
| `tie_rate` / `earlier_top1` | 同分比例 / 反而选了较早那条 | 20 | tie 0.000；earlier 0.100（recency）、0.050（correction） | 分数不是靠同分堆出来的 | 不能读成「从不犯错」 |

出处：`results/human-dimension-v2.json` `.arms.*.metrics`；限定条件见 `.controls_note`。

### H4 刁钻工作场景（`tricky/score_tricky.py:183 score()`）

| 指标 | 定义 / 算法 | n | 实测 | 能读成 | 不能读成 |
|---|---|---|---|---|---|
| 类人度（层内加权） | 六型主指标加权平均：`composite = bootstrap_ci(per_type_hits)`（`:289-301`）；权重 `WEIGHTS`（T1 .15 / T2 .20 / T3 .20 / T4 .15 / T5 .15 / T6 .15） | 132 | **0.3432** [0.2864, 0.3955]，stratified-bootstrap reps=2000 seed=20261109 | H4 层内综合表现 | **只是层内加权分**，不是全局分、不能跨层排名 |
| T1 抗干扰 | 主指标 = `hit@k`（`:256-270` 分支判断），另报同主题干扰占 top-k 的比例 `distractor_rate`（`:210-215`） | 22 | hit@k 0.9545；干扰率 0.000 | 强约束题能选对 | 干扰率 0 不等于「能抗干扰」——本题型干扰与真约束措辞差异大 |
| T2 同名异事 / T3 隐含约束 / T4 旧结论失效 / T5 跨时间一致 | 四型主指标一律 **`hit@1`**（`MAIN_METRIC_HIT1`，`:54`、`:261-266`）——必须**首选就对**，「挤进 top-k」不算 | 各 22 | T2 0.0455；T3 0.6818；T4 0.0455；T5 0.2273 | 首答能力 | T2/T4 的 0.045 意味着「碰巧进前 5」也不算分，**不要**拿它们的 hit@k（0.4545 / 1.000）当能力 |
| T6 证据优先 | claim 组内实测 vs 转述，实测排名严格优于所有转述才记 1（`:228-244`）；另报 `hearsay_quotes_top1` = 转述占 top-1 比例（`:285-287`） | 22 | evidence_first **0.0909**（2/22）；**转述霸榜 0.8636** | 系统**不区分证据等级**，谁字面像就用谁 | 0.0909 是能力缺口，不是判分口径问题（判据已对 claim 组内逐条取 rank） |
| 与字面基线的差 | `paired_delta()` + `bootstrap_ci()`：同一批题上「真实 arm − 合成 lexical arm」的分层配对 bootstrap（`:422-478`） | 132 | arm_a 0.3432 vs arm_b 0.2045，**delta +0.1386** [0.0682, 0.2045] | 相对纯字面检索确实有增量 | 增量不大（+0.14），且 T1 上真实 arm 反而**低于**字面臂（0.9545 vs 1.0，delta −0.045） |
| 264 扩集 | 同 `score()`，换成 264 题库 | 264 | **0.3386** | 扩集后层内加权分基本稳定（0.343 → 0.339） | 两个数字**不同题库**，不可互相替代引用 |

出处：`tricky/results/tricky-isolated-panel.json`（`.summary.humanlike_score`、`.per_type`）、`tricky/results/tricky-264-isolated.json`、`tricky/results/tricky-isolated-delta.json`。

### H5 多语言（`i18n/score_i18n.py`，产物 `i18n/results/i18n-score.json`）

> 说明：D1/D2 的判分函数本轮未逐行核对源码（只核对了产物字段），算法口径按产物 `params` 与统计结构描述；如需精确到行号，标**未验证**。

| 指标 | 定义 | n | 实测 | 能读成 | 不能读成 |
|---|---|---|---|---|---|
| D1 语言公平 | 「用母语写、用母语问」的命中率；比较 en/es/ja/zh 四语 | 96（每语 24） | overall **0.96875** [0.9121, 0.9893]；en 0.9583 / es 1.0000 / ja 0.9583 / zh 0.9583；极差 0.0417 | 四语都能用，没有明显弱势语种 | ① 每语 n=24，区间宽；② 「公平」只指这四语，不能外推到其他语言 |
| D2 跨语言 | 用 A 语写、B 语问（12 个方向） | 288 | cross **0.9236** [0.8871, 0.949]；同语言对照 **0.9896** [0.9433, 0.9982]（n=96）；**跨语言落差 0.066** | 跨语言损失约 6.6 个百分点 | 不能读成「已解决跨语言」——对照组 0.9896 vs 跨语 0.9236 的差就是未解决部分 |
| D3 跨语言同事实 | 同一事实在四语各写一次后的**重复条数**与召回 | 24 事实 × 4 语 | 缺省策略：96 条（每事实 4 条）、recall_hit 0.938；机械采纳 merge（阈值 0.45）：39 条、mean 1.625、**recall_hit 0.677、6 个事实零条目** | 粗暴合并会**丢事实** | 合并阈值不能只看「条数变少」；0.677 是退化证据 |

出处：`i18n/results/i18n-score.json`（`.d1_language_fairness` / `.d2_cross_lingual`）、`i18n/results/d3-important-summary.json`。

### H6 六道分水岭（`humanlike2/score_h6.py:107 score_dataset()`）

等权 composite：六型主指标各 1/6（`WEIGHTS`，`score_h6.py:42`；合成见 `:261-272`）。

| 指标 | 定义 / 算法 | n | 实测 | 能读成 | 不能读成 |
|---|---|---|---|---|---|
| P1 前瞻记忆 `intent_hit@1` | 「以后要做某事」的意图条目是否 top-1（`:141-147`） | 24 | **1.000** | 意图条目能被精确召回 | 只测「召回意图条目」，**不测**系统会不会主动提醒 |
| P2 错误记忆 `lure_false_hit` | 诱饵题「没硬凑」的比例（`:149-164`）；附 `know_auc`（`:277 _auc()`）、`lure_hard_code_rate` | 24（诱饵 12 / 真记 12） | `lure_false_hit` **0.000**、`lure_hard_code_rate` **1.000**、AUC **1.000** | 分数可分性存在（AUC 1.0：真条目 top1 分都高于诱饵） | **不能读成「不会硬凑」**：`lure_false_hit=0` 意味着 12 道诱饵题**全部**把诱饵端出来了；AUC 只说明分数排序可分，与是否硬凑是两件事 |
| P3 主动遗忘 `pre_hit` / `target_gone_rate` / `forgotten_hit` | 遗忘前能召回吗 / 遗忘后目标消失了吗 / 遗忘后仍被召回的比率（`:166-194`） | 24 | pre **0.000**；target_gone **1.000**；forgotten **0.000**；collateral 邻居可召回 | （本轮**不可读**） | **本层遗忘臂 12 组全部 `rc=2` 未成功**（`provenance.forget.n_forget_ok = 0`、`n_target_gone = 12`）：target_gone=1.000 是因为**从来没有忘记过**，属假象；P3 这三个数**不能**作为遗忘能力证据，也**不要**用它解释 composite |
| P4 来源监控 `source_attribution_hit@1` | 三条同事实不同来源，选对来源（`:196-203`）；附误归属率 | 24 | **0.875**；误归属 0.0417 | 来源字段基本能被正确区分 | n=24，区间下界会明显低于 0.875 |
| P5 时间线重建 `order_correct@1` | 「某步之前发生了什么」；gold = 象限 III（早 created、晚插入），并统计 top1 跟随 created_at / 插入顺序 / 都不跟（`:205-246`） | 24 | order 0.0417；**verdict = `neither`**（既非认 created_at，也非认插入顺序） | 系统**不用任何时间轴**排序 | 不能读成「时间线能力差」就完事——`neither` 是更强的结论：连插入顺序都不主导，top-1 落在象限 IV（题面引号原文锚点复述） |
| P6 重构性 `gist_hit@1` / `action_hit@1` / `value_hit@1` | 同一件事三档问法：要旨 / 动作 / 具体值（`:248-259`） | 21 | 三档全 **0.000** | — | 理想情况应是 **value 强、gist 弱 = 只是字面检索**；本轮三档同时 0，说明连 value 都没进 top-1（题面与陈述词面错位），**不能**用它证明「重构性不行」，只能证明「这一档问法召回为空」 |
| 层内等权分 | 上述六型主指标各 1/6 | 141 | **0.4861** | H6 层内水平 | 不是全局分；且 P3(1.000 假象) 与 P2(0.000) 相互抵消，读 composite 必须回到分型 |

出处：`humanlike2/results/h6-isolated.json`（`.types.*`、`.provenance`）。语料 278 节点、端口 16343、索引 waited 83.6 s。

### H7 跨跳与诚实（`h7/score_h7.py:82 score_dataset()`）

| 指标 | 定义 / 算法 | n | 实测 | 能读成 | 不能读成 |
|---|---|---|---|---|---|
| L1 多跳链 `hit@1` / `hit@5` | 链上要素是否在 top-k；按跳数分层的 `by_hop`（`:104-115`） | 16 | **hit@1 0.1875** [0.0659, 0.4301]（3/16）；hit@5 0.8750 [0.6398, 0.9650]（14/16） | 链要素进前 5 容易，**进第 1 很难**（跳数越多越差：hops1 0.75、hops2/3/4 的 hit@1 均 0） | 不能读成「多跳推理能力 0.1875」——这是检索排序上界，不含推理步 |
| L2 混跳辨析 `accuracy` | `score_h7.py` 的脚本分 | 16 | 脚本 **1.000** [0.8064, 1.000] | 仅说明判分脚本在合成臂上自洽 | **不是能力分**。同一批题的**真实召回**判据给出 `accuracy 0.1250` [0.0350, 0.3602]（2/16）、`subject_hit@1 0.000`——以真实召回为准 |
| L3 缺证据拒答 `abstain_recall` / `closed_ended F1` | 三档：该答 / 未写入 / 超纲。`said_abstain()`（`:131-134`）把「诱饵没硬凑」判为 abstain | 24（应拒 16 / 应答 8） | **abstain_recall 0.000**（0/16，即**该拒 0/16**）；closed_ended F1 0.5（tp 8 / fn 0 / **fp 16**）；by_tier：answered 1.000、in_unwritten 0.000、off_spectrum 0.000 | 应答的 8 题全对；**该拒的 16 题全硬凑** | 不能读成「拒答能力一般」：是**完全不会拒**。也不要拿 closed_ended recall=1.0 当成绩（它只统计「该答的答对了」） |
| L4 增广认同 `hit@1` | 题面用同场景另一实例词、gold 用原实例（词面错位）；按 `aug_kind` 分（`:159-168`） | 24 | **0.3750** [0.2116, 0.5729]（9/24）；rewrite 0.000 / rephrase 0.375 / reorder 0.750 | 换说法后还能不能认出来 | 必须对照**字面基线 0.3333** 读：增量仅 **+0.0417**。真实分逼近字面臂 = 该子类仍被字面主导 |

出处：`h7/results/h7-isolated.json`（`.score_h7.*`、`.l2_real_recall.*`、`.l4_semantic_increment`）。语料 144 节点、端口 16344、attach 80/80 成功。

### H8 记忆动力学扩建（`h8/score_h8.py:79 score_dataset()`）

| 指标 | 定义 / 算法 | n | 实测 | 能读成 | 不能读成 |
|---|---|---|---|---|---|
| C1 一次观察泛化 `hit@1` | 只看过一次的事实，换场景后仍能召回（`:100-102`） | 16 | **0.1250** [0.0350, 0.3602]（2/16） | 一次观察的泛化很弱 | 必须对照字面基线 0.5 读：**低于字面臂 0.375**（`lexical_C1_hit@1 - C1 = -0.375`），说明题面设计使语义路径失效而非「泛化能力=0.125」 |
| C2 跨间隔召回 `hit@1` / `hit@5` | 按「记忆年龄」1h/1d/7d/30d 分层（`:104-118`）；正向断言 `aged_hit@5`、`aged_nonzero` | 16（每档 4） | hit@1 **0.8750** [0.6398, 0.9650]（14/16）；by_age 1h **0.500**、1d/7d/30d 各 **1.000**；aged_hit@5 0.875 | **无衰减**：老条目召回率不低于新条目 | ① 每档仅 4 题；② 「无衰减」在检索层等于「没有时间衰减机制」，**不等于**「记忆强度管理做得好」；③ 1h 档 0.500 与其他档 1.000 的差异不能单独下结论 |
| C3 远期不被淹没 `not_buried@1` | 大量新条目涌入后，远期条目是否仍在 top-1（`:120-123`） | 16 | **0.9375** [0.7167, 0.9889]（15/16） | 远期条目没有被新条目挤掉 | n=16，区间下界 0.72，不宜宣称接近完美 |
| C4 增量编辑 `edited_hit@1` + `stale_top1_rate` / `stale_ahead_rate` | 条目被编辑后，新版本是否 top-1；旧版本霸榜率 / 旧版本排在新版之前比例（`:125-131`） | 16 | edited_hit@1 **0.3750** [0.1848, 0.6136]（6/16）；edited_hit@5 0.750；**stale_top1 0.500** [0.2800, 0.7200]（8/16）；stale_ahead 0.625 | 编辑后有一半概率**旧版仍霸榜** | 不能读成「编辑功能坏了」：新版本进前 5 有 0.75；缺口在**排序**而非写入 |

出处：`h8/results/h8-iso-panel.json`（`.summary.*`、`.lexical_C1_hit@1`）。语料 192 节点、端口 16345、attach 32 成功。

### H9 推理与元认知（`h9/score_h9.py:67 score_dataset()`）

层内**等权** composite = 六类各 1/6（`score_h9.py:143-144`）。

| 指标 | 定义 / 算法 | n | 实测 | 能读成 | 不能读成 |
|---|---|---|---|---|---|
| R1 因果归因→处方 `prescription_hit@1` | 同因泛化：题面给**改述后的新情境**，处方只在 gold 正文里；题面与 gold 正文不得有 ≥3 字公共连续子串（生成期断言） | 16 | **0.1250** | 处方能跨措辞被召回 | 这个子类**故意词面错位**，因此也**不能**与「字面召回率」类指标并比 |
| R2 反事实 `counterfactual_hit@1` | 「若当初不做 X，还会 Y 吗」——答对需召回记录该因果绑定的条目 | 16 | **0.6250** | 绑定事实基本能被召回 | **不测**系统能否言语推演反事实（检索层评测的固有边界） |
| R3 动态更新 `fresh_hit@1` + `stale_crown_rate` | 旧值（stale）与新值（fresh，晚 created、带「以此为准」）同主题；头榜落新值 = 命中；`stale_crown_rate` = 头榜落旧值比例（诊断，不进 composite）（`:100-110`） | 16 | fresh **0.3750**；**旧条目霸榜 0.0625** | 有 37.5% 的题能跟到最新值 | 旧条目霸榜只有 0.0625 并不代表「更新做得好」——大量题的 top-1 落在**第三条**干扰上（rank 1/2/3 各占相当比例，见 `per_question`） |
| R4 压缩摘要 `gist_line_hit@1` | 跨多条抽主线；题面不复述主线原文；三条细节抢字面 | 16 | **0.9375** | 主线句能被召回 | 0.9375 偏高，说明本题型主线句与题面仍有可用词面桥；**不能**读成「具备摘要能力」（真正摘要应由模型生成，此处只测条目召回） |
| R5 元认知（类分 = 三指标均值） | ① 已记探针 `probe_recorded_hit@1`；② 未记探针 `probe_unrecorded_resist`（gold 为空，**正确 = 不硬凑**）；③ 该存该扔 `importance_hit@1`（按归档判例 grade 召回）（`:112-129`） | 16（探针 8 = 已记 4 + 未记 4；判例 8） | 类分 **0.8333** | 元认知三件事整体表现 | ① 探针为 **search-only**：只查询、不写库，本层**无写路径**；② 「记没记」只能读成「召回到/没召回到」，**不是**模型自述「我记得」；③ 未记探针的正确判定是「没有硬凑」，与「答对」不同 |
| R6 跨来源置信 `evidence_first` + `retell_crown_rate` | 同参数三来源（实测 / 转述 / 文档）同主题；top-1 = 实测才算命中；`retell_crown_rate` = top-1 落转述比例（诊断，不进 composite）（`:131-141`） | 16 | **evidence_first 0.000**（0/16）；**转述霸榜 0.8750**（14/16） | 系统**完全不看证据等级**，转述条目因字面更贴近题面而霸榜 | ① 0.000 不是判分口径问题：题面内嵌转述原句（对齐 H4 T6 口径）本身就会让字面检索偏向转述；② 与 H4 T6 的 0.8636 同向，可互相印证机制 |
| 层内等权分 | 六类各 1/6 | 96 | **0.4826**（R1 0.125 / R2 0.625 / R3 0.375 / R4 0.9375 / R5 0.8333 / R6 0.000） | H9 层内水平 | **必须同时看字面基线**：同一题库上纯字符 bigram 臂 composite = **0.5069**，本层等权分**低于字面臂**，因此 0.4826 **不是能力分**，也不能当成「比字面检索差」的结论——分层看子类：R1/R6 字面臂 0.0（真增量），R2/R4 字面臂 0.9375（几乎被字面解释完） |

出处：`h9/results/h9-score.json`、`h9/results/h9-selftest-arms.json`（字面基线口径）。语料 232 节点、端口 16346。

**关于「霸榜率」这一族指标**：`stale_crown` / `retell_crown` / `stale_top1` / `hearsay_quotes_top1` 都是**诊断率**，回答「错误来源占了头榜多少」，**不进任何 composite**，也不与主指标相加。

---

## 五、复现

### 5.1 隔离库三件套（最重要的一条）

```bash
# 必须同时设置，缺一不可
RSRS_DATA_DIR=/tmp/agimem-<arm>          # 独立数据目录（绝不用 ~/.rsrs）
RSRS_RPC_PORT=163xx                      # 独立端口（绝不用默认 15169）
RSRS_SUPER=<独立 super>                   # 独立超级用户占位
```

**三者必须同设**：只设 `RSRS_DATA_DIR` 而不设 `RSRS_RPC_PORT` 时，新起的 runtime 会去抢**默认 15169**，于是 `rsrs --client-only` 打到的是**别人/真库**——本项目已踩过两次（本项目在 respire 仓内 `tests/33-multilingual.md:147`、`tests/37-causal-isolated.md:28` 有完整记录，本仓不随附）。

实现见 `agimem/isolated_lib.py:9-13`（先过滤掉所有 `RSRS_/ONEMEMORY_/RESPIRE_` 前缀变量，再显式 set），机器层见 `machine/run_machine.py:200`（`Store.open()` 同时设 `RSRS_DATA_DIR` / `RSRS_RPC_PORT` / `RSRS_SUPER`）。

### 5.2 其它必须遵守的复现纪律

| 事项 | 要求 | 出处 |
|---|---|---|
| 就绪判据 | **`state = ready` 且 `embedding_model = m3`**；`worker_active = true` **不能**作为就绪判据（索引未完成时也可能为 true） | `humanlike2/results/h6-isolated.json` `.provenance.index` |
| 索引等待 | 实测 **83.6 s（278 节点）/ 112.7 s（144 节点）/ 140.8 s（192 节点）**，随节点数与机器负载变化；各层产物均记录了 `waited_s`，复跑请以实际到达 `ready` 为准 | `.provenance.index.waited_s`、`h7-*.index.waited_s`、`h8-*.isolated.ready.waited_s` |
| parent 边 | `rsrs import` **不建 parent 边**，链式题必须在 import 后单独 attach（`attach_ok` / `attach_fail` 字段核对） | `h7-isolated.json` `.attach_ok = 80`、`causal-236-isolated.json` `.attach.n_edges_ok = 322` |
| 取代边 | `import` 通道**会丢弃** `supersedes`/`superseded_by`（硬编码清空），要测取代必须走 `remember --supersedes` 真写边 | `causal-236-isolated.json` `.supersession_note` |
| 去重坑 | `rsrs import` 会吞掉**正文完全相同**的条目；合成语料须在正文/标题尾部附唯一条目标记 | `isolated_lib.py` 模块注释 |
| 热轴消融 | 隔离臂统一 `RSRS_ABLATE=hot`，否则热轴写回会污染同库复跑 | `isolated_lib.py:13` |
| 产物脱敏 | 落盘只允许合成 id（`hl9…` / `tkk…` 等），隔离库 UUID 只在进程内存映射；预测文件里 UUID 命中数必须为 0 | `h9-isolated-stats.json` `.uuid_hits_predictions = 0` |

### 5.3 真库纪律（`~/.rsrs`）

**真库禁 `recall` / `show` / `forget`——`rsrs recall` 会写 `query_log`，等于污染被测库。** 真库侧只允许：

- `rsrs bench run`（只读，走报告）；
- `rsrs export`（只读，且全文只落 `/tmp`，不进仓）。

M 层全部按此口径采集（`machine/results/machine-scorecard.json` `.environment.index_pending = 0`、`.m3.export_discipline`）。

### 5.4 逐层复跑入口

```bash
# M 层
python3 machine/run_machine.py --help
# H 层（以 H9 为例，其余同构）
cd h9 && python3 gen_h9.py --verify && python3 selftest_h9.py
python3 score_h9.py --verify-only                 # 只验 gold 可机械复算
python3 score_h9.py <dataset.jsonl> <preds.jsonl> # 出分
```

---

## 六、新增一层要遵守的红线

1. **题面必须词面错位**。若题面与 gold 正文共享长串字面，测到的只是**字面检索**，不是目标能力。H6 v3 曾因此在多个子类拿到满分（实际没测到分水岭），H7 L4 也因此被裁决把重合度收紧到 **<6 字**。
2. **铁律断言必须在生成期强制**，不能写在文档里靠自觉。三道：① 场景 ∈ 白名单；② 题面必须含该场景标志词；③ 题面不得命中禁题材词。H9 另加四道：R1/R4 题面不复述 gold 正文（≥3 字公共连续子串即失败）、R5 未记属性在全语料 0 出现、R3 时序断言、R6 三来源互异。违规**退出码 1**，不许落盘。
3. **gold 必须机械推导**。`*_gold.py` 的 `evaluate_expr()` 只读节点角色/属性，`verify_gold()` 逐字段对账；禁止「人工填答案」或「跑完再补 gold」。
4. **产物只落合成 id**（配合 §5.2 脱敏）。prediction 里出现真 UUID 即视为泄漏，必须重采。
5. **真库禁 `recall` / `show` / `forget`**（同 §5.3）。
6. **不要负重跑已绿门禁**：判分脚本已 `--verify-only` 通过时，不必重复全量复算；门禁红或有人点名才升级。
7. **失败必须写进「未验证」**。合成臂数字、脚本自洽分、缺陷导致的假象（如 H6 P3、H7 L2、H9 等权分）都要在产物里注明口径，不能只报好看的数。

---

## 七、已知边界

1. **m3 是字面/向量检索，不是推理器**。词面重合能到 0.8–0.9（H7 L4 rewrite 式、H9 R2/R4），一旦要求「首选就对」「换说法」「跨跳第一步」「认来源」就会掉下去。
2. **多跳第一名很难**：H7 L1 hit@5 0.875 但 hit@1 0.1875；H2 链 hit@1 0.2941（且含自命中）。
3. **该拒不会拒**：H7 L3 该拒 16 题**全部硬凑**（abstain_recall 0.000）；H6 P2 诱饵硬凑 1.000。
4. **换说法/泛化仍有明显损失**：H7 L4 rewrite 0.000、rephrase 0.375，相对字面基线仅 +0.042；H8 C1 0.125 **低于**字面臂 0.5。
5. **认来源不行**：H4 T6 转述霸榜 0.8636；H9 R6 转述霸榜 0.8750、证据优先 0.0000。两处独立复现，是同一机制。
6. **认新版不行**：H8 C4 旧版霸榜 0.500、旧版排前 0.625。
7. **时间轴未被使用**：H6 P5 verdict = `neither`；H3 v2 的「认新」优势主要来自插入顺序（K1 对照 0.850），`created_at` 与插入顺序在本设计内**不可分离**，故「系统是否认时间」**未验证**。
8. **无衰减**：H8 C2 老条目召回 0.875，1d/7d/30d 均 1.000——检索层没有时间衰减。
9. **遗忘无法评估**：H6 P3 遗忘臂 12 组全部未成功（`n_forget_ok = 0`），P3 三指标本轮**无效**。
10. **合成语料外推受限**：H 层语料全合成（几百节点），题目模板化；数字可用于**层内比较与缺口定位**，不可外推为「在真实用户数据上的能力」。
11. **H1 非零 LLM**：答题与判分走外部模型，含 judge 噪声；且与历史 0.6991 **不可并表**（网关/判次/模型都变过）。
12. **小样本**：H3 每臂 20、H7 每型 16–24、H8 每档 4、H9 每类 16。Wilson 区间在这些 n 上很宽（n=16 时约 ±0.24），跨类比大小需谨慎。
13. **单 seed 单轮**：各层 gold 与语料由固定 seed 生成（如 H9 `seed=20261110`），未做跨 seed 稳定性检验。
14. **未验证项**：① 真实系统在 H7/H8/H9 的分数仅一处隔离库实测，未做多环境复核；② M2 吞吐（并发）数字本轮未在记分卡中核对，**未验证**；③ H5 的 D1/D2 判分函数未逐行核对源码，仅核对产物字段。

---

## 附：数字索引（一屏对照）

| 数字 | 含义 | 出处 |
|---|---|---|
| 0.8767 / 0.4264 | M1 hit@20 / MRR | `machine/results/machine-scorecard.json` |
| 1.064 s / 1.472 s / 2.453 s / 9.932 s | M2 runtime p50 / p95 / e2e p99 / 冷启动 | 同上 |
| 10,942 | M3 注入 token 中位（bge-m3） | `machine/results/machine-scorecard.md:44` |
| 0.5603 / 0.9036 | H1 端到端 / session-hit@5 | `results/locomo-e2e.json` |
| 0.7353 / 1.000 | H2 链 hit@5 / 取代（真写边） | `results/causal-236-isolated.json`、`causal-supersession-v2.json` |
| 0.900 / 0.950 / 0.950 | H3 v2 recency / correction / repeat | `results/human-dimension-v2.json` |
| 0.3432 / 0.3386 | H4 132 题 / 264 题 层内加权 | `tricky/results/tricky-isolated-panel.json`、`tricky-264-isolated.json` |
| 0.96875 / 0.9236 / 0.9896 | H5 D1 / D2 跨语 / D2 同语对照 | `i18n/results/i18n-score.json` |
| 0.4861 | H6 v4 层内等权 | `humanlike2/results/h6-isolated.json` |
| 0.1875 / 0.000 / 0.3750 | H7 L1 hit@1 / L3 该拒 / L4 hit@1（字面基线 0.3333） | `h7/results/h7-isolated.json` |
| 0.1250 / 0.8750 / 0.9375 / 0.3750 | H8 C1 / C2 / C3 / C4（旧版霸榜 0.500） | `h8/results/h8-iso-panel.json` |
| 0.4826 | H9 层内等权（字面臂 0.5069，**低于字面臂**） | `h9/results/h9-score.json`、`h9-selftest-arms.json` |

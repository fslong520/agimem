# agimem · H4「刁钻工作场景」层（类人记忆主线）

陛下定的顶层结构里，**H 维 = 类人向（类人记忆）**；本目录是 H 维主线子层 **H4 刁钻工作场景**。
命题：**分数越高说明记忆越类人，越能应对人类社会里的各种事务**——核心考 agent 在真实工作中能否
应付奇葩、刁钻、反直觉的处境。

## 一、出题铁律（记忆 cdf155a9，强制）

**每题必须有真实工作场景**。本层把场景写成**白名单**，只有下列八个场景可以出题：

> 部署上线 · 灰度发布 · 接口对接 · 同事交接 · 开会定口径 · 线上排障 · 数据迁移 · 权限审批

**禁用**科幻、纯数学、纯图案、纯抽象分类。守门是机械的（`gen_tricky.py` 生成期断言）：

1. 每题 `scenario` 必须在白名单内（`scenarios.SCENARIO_KEYS`）；
2. 题面必须含该场景的标志词（如「部署上线」→ 上线/发布单/部署）；
3. 题面不得命中被禁题材词表（`scenarios.BANNED_TOPICS`：科幻/拓扑空间/矩阵乘法/图案打印…）。

## 二、六类刁钻点 ↔ 人类记忆能力

| 类型 | 刁钻点 | 映射的人类记忆能力 | 该能力在人身上长什么样 | gold 从哪来 |
|---|---|---|---|---|
| T1 | 无关记录淹没真约束（同主题 5 条跨场景干扰） | **抗干扰 / 选择性注意** | 同事七嘴八舌，你仍记得那条「端口不能动」 | 同 topic 上 `role=constraint` 的唯一节点 |
| T2 | 两个都叫「V2 方案」「那个接口」，按情景区分 | **同名异事分辨 / 情景绑定** | 听到同一个外号，先问「你说是哪件事」 | `(same_name_group, scenario)` 联合定位 |
| T3 | 没人明说但都当规矩（旧端口/旧命名/上次的坑） | **隐含约束提取 / 内隐记忆** | 新人不知道、老人不用想就照做的默认 | 同 topic 上 `implicit=true` 的节点 |
| T4 | 口径改过，现在该按哪个 | **失效感知 / 记忆更新** | 老经验被新证据推翻后不再照搬 | `superseded_by` 指向的当前结论 |
| T5 | 隔很久翻旧账，早先结论还对吗 | **跨时间一致性 / 时间线** | 记得「半年前那个结论后来改过两次」 | 沿 `superseded_by` 走到链尾（三跳链） |
| T6 | 同事说「应该没事」vs 我方实测炸了 | **证据分级 / 来源可信度** | 亲测 > 官方单 > 转述，别把传说当事实 | 同 claim 上 `evidence_grade` 最高且有唯一最高者 |

## 三、规模与确定性

- 树：`data/tricky_tree.json`，seed=20261109，**748 节点**，八场景白名单，节点正文 Respire 三段式
  【前因】【行为】【后果】；`superseded_by`/`source`/`evidence_grade`/`same_name_group`/`implicit`
  等字段由生成器种入（T4/T5 取代边为**oracle 口径**，与主链一致）。
- 题集：`dataset/tricky_evalset.jsonl`，**132 题 = 6 类 × 22 题**（每类 ≥20），场景分布 16–17 题。
- 确定性：`python3 gen_tricky.py --verify` 重生成逐字段比对，digest `410a13b7c828dd5d`。
- 单题权重 1/132 ≈ 0.76pp。

## 四、判分口径（search-only，零 LLM）

主指标按类型区分——刁钻题的要点是**「选对」，不是「碰巧出现在 top-5」**：

| 类型 | 主指标 | 说明 |
|---|---|---|
| T1 | `hit@k`（k=5） | 真约束只要在 top-5 内即算没被噪音淹没；另报「同主题干扰占 top-k 比例」 |
| T2/T3/T4/T5 | **`hit@1`** | 必须**首选**就是正确那条：同名要选对含义、隐含规矩要先想起来、口径要选当前生效的、跨时间要选链尾 |
| T6 | **`evidence_first`** | 不看措辞，只看证据级先后：实测记录必须先于转述记录出现在 top-k（正文里带 `source`/`evidence_grade` 字段，确定性规则判，**禁上 LLM judge**） |

**类人度总分**（humanlike score）= Σ w_i · s_i：

| 类型 | 权重 | 为什么给这个权重 |
|---|---|---|
| T1 抗干扰 | 0.15 | 抗噪是基础能力，但只要求不被淹没（hit@5） |
| T2 同名异事 | 0.20 | 最依赖常识与情景绑定，机器最缺 |
| T3 隐含约束 | 0.20 | 同上：没人写下来的规矩只能靠经验 |
| T4 失效感知 | 0.15 | 记忆更新是类人的关键但机制已由 superseded_by 外化 |
| T5 跨时间一致 | 0.15 | 时间线维护，与 T4 同族 |
| T6 证据分级 | 0.15 | 来源可信度，人最容易犯的错 |

分数越高 = 越像人：不被同名与噪音骗、能提取没人写下的规矩、会随事实更新结论、保留时间线、
优先信实测。**单类比例用 Wilson 95% CI；总分用分层 bootstrap（同型内重采样，reps=2000，
seed=20261109）**，避免 22 题小样本点估计被误读。

## 五、隔离库真跑（RSRS_DATA_DIR 法，可复用）

> 这一节是踩坑后补的：**隔离库是能建的**，不需要改全局 `rsrs config`。
> 后来人照这里做即可，别再以为「只能跑合成臂」。

关键：`rsrs` 的数据目录除全局 `client.json` 外，还认 **环境变量 `RSRS_DATA_DIR`**（优先级高于配置）。
只要用一套干净 env 起子进程，就能在 `/tmp` 下得到完全隔离的库（独立 data dir + 独立 `RSRS_RPC_PORT`
+ 独立 super），全程不碰 `~/.rsrs`、不改全局配置、不启停宿主 runtime。

```python
env = {k: v for k, v in os.environ.items()
       if not k.startswith(("RSRS_", "ONEMEMORY_", "RESPIRE_"))}   # 先清干净，避免继承真库配置
env.update(
    RSRS_DATA_DIR="/tmp/<arm>",      # 本臂独立目录（每臂一个，复跑前整个删掉）
    RSRS_RPC_PORT="16140",           # 独立端口（每臂不同，避免撞宿主 runtime）
    RSRS_SUPER="A3-0000...",         # 先放占位
    RSRS_NO_AUTOSYNC="1",            # 不往云端推
    RSRS_UPDATE_CHECK="0",
    RSRS_ENGINE="cpu",
    RSRS_M3_DIR="~/.rsrs/models/bge-m3",
    RSRS_FEEDBACK="0",
    RSRS_ABLATE="hot",               # tests/27 纪律：不消融则热轴写回污染同库复跑
)
subprocess.run(["rsrs", "keygen", "--json"], env=env)             # → 取回真 super
env["RSRS_SUPER"] = 真 super
subprocess.run(["rsrs", "--runtime-internal", "--stop"], env=env) # 停掉 keygen 用占位 super 拉起的 runtime
subprocess.run(["rsrs", "import", dump_json, "--json"], env=env)  # 批写入（见下面的去重坑）
# 就绪判据：空转探针 recall 的 embedding_model 非 null 且 status.state == "ready"
#   坑：status.retrieval_index.worker_active 恒为 true，它是常驻 worker 存活标志，
#   不是「索引待办数」，拿它当就绪条件会白等（参考实现为此浪费 420s/库）。
subprocess.run(["rsrs", "recall", q, "--limit", "5", "--json", "--titles"], env=env)
subprocess.run(["rsrs", "--runtime-internal", "--stop"], env=env) # 收尾停自己的 runtime
```

两个必踩的坑：

1. **`rsrs import` 会吞掉正文完全相同的条目**：合成语料里模板句容易重复，正文尾部必须附唯一标记
   （本层用 `（条目 trkA0001）`）。标题也附 `｜<trk id>`，使召回标题能直接解析回合成 id —— 这样
   落盘时只写合成 id，**隔离库的 UUID 不进仓**。
2. **`keygen` 会顺手拉起一个 runtime**（用占位 super），必须 `--runtime-internal --stop` 停掉，
   否则后续命令拿占位 super 去连，全部失败。

本层实现：[`isolated_lib.py`](isolated_lib.py)（照 `human_memory/run_human_dimension.py` 的 profile
思路复制，不 import、不改它）。跑法：

```bash
python3 isolated_lib.py --root /tmp/agimem-tricky-iso --port 16140
# → results/tricky-isolated-predictions.jsonl + tricky-isolated-stats.json
python3 score_tricky.py --predictions results/tricky-isolated-predictions.jsonl \
    --panel results/tricky-isolated-panel.md --baseline-dir fixtures \
    --delta fixtures/lexical.jsonl --delta-out results/tricky-isolated-delta.json
```

## 六、跑法

```bash
cd tricky
python3 gen_tricky.py                 # 生成树 + 132 题（含铁律守门、gold 机械复算、脱敏自检）
python3 gen_tricky.py --verify        # 确定性证明：重生成与落盘一致
python3 score_tricky.py --verify-only # gold 机械复现对账
python3 selftest_tricky.py            # 56 条断言：生成→gold→判分→CI→总分
python3 score_tricky.py --predictions fixtures/lexical.jsonl \
    --panel results/panel-synthetic-lexical.md --baseline-dir fixtures    # 合成词面臂
python3 collect_tricky.py             # 只读真库采集（脱敏写盘）
python3 score_tricky.py --predictions results/real-predictions.jsonl \
    --panel results/panel-real.md --baseline-dir fixtures                 # 真库只读臂
```

脚本只用标准库 + 本目录模块；**不写真库、不启停 runtime、不接 LLM**。

## 七、当前数字（2026-11-09，均为非能力分，见口径声明）

| 臂 | 类人度总分 | 95% CI | 说明 |
|---|---|---|---|
| perfect（合成） | 1.000 | — | 六类全对，判分器上界自证 |
| adversarial（合成，专挑会骗人的那条） | 0.000 | — | T6 转述霸占 top-1 = 1.000，T1 干扰占满 top-k = 1.000 |
| 合成词面臂（确定性 bigram，零 LLM） | **0.205** | [0.170, 0.243] | 只是「有区分度」的对照，不是任何系统的分 |
| 真库只读臂（`rsrs --client-only recall`） | **0.000** | [0.000, 0.000] | 合成题不在真库里：660 条命中里 0 条与树 id 匹配 |
| **隔离库臂（`RSRS_DATA_DIR` 真写入 + 真召回）** | **0.343** | [0.286, 0.395] | **这是唯一可读成「类人记忆能力」的一臂**（合成树真在库内，748 条 m3 向量检索） |
| 有树 − 无树 Δ（同题配对） | **+0.139** | [+0.068, +0.205] | T3 +0.591、T5 +0.227；T1 −0.045、T4 −0.136（如实报，不凑数） |

## 八、口径声明与已知弱点

1. **不是能力分**：合成题没有导入任何被测库。真库臂的 0.000 只说明「题库不在被测库」，
   不能读成 Respire 在刁钻场景下不行；合成词面臂的 0.205 是给判分器做区分度对照，
   与 Respire 无关。
2. **T1 在词面臂上满分**（1.000）、隔离库里 0.955：真约束记录标题含「硬约束」、与题面「该按哪条约束」
   直接重合，字面检索即可命中。T1 的难在于**干扰记录占坑**，本层用 `distractor_rate` 单列观察，
   下一版可把约束语义埋进长叙述里。
2b. **T4 在隔离库里 hit@5=1.000 但 hit@1=0.045**：`recall --titles` 载荷**不下发 `superseded_by`**，
   新旧结论正文又高度相似，召回把旧结论排在第 1。这条低分里混着「接口没暴露取代标记」，
   不能全归为模型能力（与 tests/29 同一声明）。
3. **T4/T5 取代边是 oracle 口径**：`superseded_by` 由生成器种入，测「能否用好已种标记」，
   不测「能否自动发现证伪」（与主链 tests/29 同一声明）。
4. **T6 证据分级依赖字段**（`source`/`evidence_grade`）：真实系统若无来源字段，本类判分需另立口径，
   不得与「模型自己判断可信度」并表。
5. 场景词库是有限集（八场景 × 各自词表），未做人工通读校对；机械守门只保证「不越界」，
   不保证每道题都足够刁。

## 九、文件

| 文件 | 作用 |
|---|---|
| `scenarios.py` | 八场景白名单 + 词库 + 六类刁钻模板（含组件别名表） |
| `tricky_gold.py` | gold 机械推导唯一实现（六类）+ `id_match`/`chain_of` 工具 |
| `gen_tricky.py` | 确定性 seed 生成树与题集；铁律守门；`--verify` |
| `score_tricky.py` | 六类主指标 + Wilson CI + 类人度总分（bootstrap）+ 面板/JSON |
| `selftest_tricky.py` | 生成→gold→判分→CI 全链路断言（56 条） |
| `collect_tricky.py` | 真库只读采集，id 脱敏为 `e`+7 位 |
| `data/`、`dataset/`、`fixtures/`、`results/` | 树、题集、合成臂、数字与面板 |

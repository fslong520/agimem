# humanlike2 — H6「人 vs 数据库」六道分水岭层

与 H4（`agimem/tricky/`）的区别：H4 测「回顾过去准不准」，H6 测**数据库天然做不到、人类天然做得到**的六件事。
判据来自记忆 `28f2ee02`：凡存/查/精确匹配这类数据库也能做的，不算类人度。

## 目录

| 文件 | 用途 |
|---|---|
| `scenarios.py` | 八场景白名单 + 词库 + `node()`/`tpl()` 构造器（沿用 H4 同一套八场景） |
| `gen_h6.py` | 确性 seed 生成语料与评测集，三道铁律断言在落盘前强制 |
| `h6_gold.py` | 六类 gold 机械推导 + `verify_gold()` 对账 + `evaluate_expr()` 判分 |
| `score_h6.py` | 指标汇总（Wilson CI、P2 AUC、P5 created_at_effect） |
| `selftest_h6.py` | 全链路自检（确定性/gold/计数/诱饵/四象限/合成臂） |
| `collect_h6.py` | 隔离库真跑：建库→等索引→created_at 探针→144 题 recall→判分（`--run` 显式开跑） |
| `data/h6_tree.json` | 280 节点全合成语料 |
| `dataset/h6_evalset.jsonl` | 144 题（六类各 24） |
| `fixtures/` | perfect / adversarial / lexical 三条合成臂 |
| `results/h6-isolated.json` | 隔离库真跑判分（六类+CI+P5 判决+P3 forget 探针+provenance） |
| `results/h6-isolated-predictions.jsonl` | 144 题原始召回（合成 id，无真 UUID） |

## 快速跑

```bash
cd agimem/humanlike2
python3 gen_h6.py            # 生成
python3 gen_h6.py --verify   # 确定性重生成字节一致
python3 selftest_h6.py       # 全链路自检（应全绿）
python3 score_h6.py --verify-only   # 只验 gold
python3 collect_h6.py        # dry-run：只打印采集计划，不写库
python3 collect_h6.py --run --port 16340   # 真跑（见 §五）
```

## 隔离库真跑（T34/v4，2026-11-10）

**v4 实测**：端口 16343，278 导入（duplicates=0）、索引 83.6s ready/m3、141 题、unmapped=0、
`gen_h6 --verify` rc=0 digest `491abc9217428163`、selftest 37 PASS；**等权 0.4861**。
四轮对照：v1 0.500 / v2 0.653 / v3 0.653 / **v4 0.4861**（题面结构已变，v4 不与 v1–v3 并表）。

**三处设计缺陷实测（定性：出题设计与 m3 字面检索不匹配——不是产品 bug，也不是评测 bug）**：

1. **P5 空召回 10/24（p5-015..024，第 8–12 批）**：题面带「第 N 批」而树正文 0/278 带组号
   （正文如「按四步走，每一步都单独记了时间」）→ 词面断链 → m3 无锚点召回空 → verdict 恒 neither 的真因。
   **时序题在字面检索下结构性测不出**；题面加组号必须与正文同步，只加题面是出题侧的错。
2. **P6 全空 21/21**：题面抽象问法（为什么要改/做了什么调整/调成多少）与正文陈述标签
   （原因是/做法是/现值是）词面错位 → 召回即失败。**重构性（gist）在字面检索下必然召回失败——
   这正是「类人记忆 vs 字面检索」的分界，是 P6 要测的东西，召回空本身就是结论**。
3. **P3 pre_hit=0（12/12 top1=各组「第 1 件」短节点，gold「第 2 件」全掉出 top5）**：撤组号后仍复现、
   与组号无关；**真因是 m3 对同 topic 相近条目排序偏好短文本**（gold 81 字为三件最长，top1 恒 70–71 字
   第 1 件）。Lead 此前两次归因（同文副本 → 组号噪声）均被复现推翻，以 tests/39 §13.3-③ 为准。

**未变对照**：P1 intent_hit@1=**1.000**、P2 know_auc=**1.000**/lure_false=**0.000**、P4 source_hit@1=**0.875**
——同库同判分器下词面对齐的三类全绿，交叉证明塌陷源于出题与字面检索的匹配性。

**边界（重要）**：①P3 遗忘指标本轮**无效**——forget 探针 `n_forget_ok=0`（12 组全 fail），
`forgotten_hit=0.000`/`target_gone_rate=1.000` 不可信，P3 仅 pre_hit 可读；②0.4861 含题目变更成分，
与 v1–v3 分数不可并表。逐条证据见 `tests/39-humanlike-h6.md` §十三。

### 历史轮次（保留对照）

**T31 实测（v2/v3 干净版，0.653）**：280 导入（duplicates=0）、索引 182s ready/m3、144 题 163.6s、unmapped=0、
等权 **0.653**；`created_at` 落库 24/24；P3 全量 forget 12/12 组真调（n_forget_ok=12、n_target_gone=12/12、
n_neighbor_show_ok=24/24）；P5 判决 **neither**（12/12 落锚点 IV）；P2 know_auc=1.000、lure_false=0.000；
P6 三档全 1.000；P4 source_hit=0.875。
**P3 pre_hit=0.000（异常）**：gold B 不在 top-5（后于 v4 定性为 m3 偏好短文本，见 tests/39 §13.3-③）；
forgotten_hit=0.000 与此一致（pre 未命中，post 也未命中，不构成遗忘证据）；collateral_hit=0.667。
T27 泄漏版（0.500）对照见 tests/39 §十一、§十二。

既证三件套（记忆 `739fbbc7`、`56727a0a`）：

1. 清空 `RSRS_/ONEMEMORY_/RESPIRE_` 前缀 env，设 `RSRS_DATA_DIR` + 独立 `RSRS_RPC_PORT` + 占位 super；
2. `rsrs keygen --json` 取真 super → `rsrs --runtime-internal --stop` 停占位 runtime；
3. `rsrs import` 批写 → 等索引 ready（判据：探针 recall 的 `embedding_model` 非 null 且
   `status.state=ready`，**勿信 `worker_active`**，它恒 true）→ 逐题 recall → 停自己的 runtime。

**T27 实测**：280 导入（duplicates=0）、索引 456.9s ready/m3、144 题 237.6s、unmapped=0、
等权 0.500；`created_at` 落库 24/24；`rsrs forget` 实测有效（tombstone + recall 消失 + 邻居不误伤）；
P5 判决 **neither**（12/12 落锚点 IV，既不跟 created_at 也不跟插入）。详见 `tests/39-humanlike-h6.md` §十一。

### 真跑三坑（本轮踩到）

- **`rsrs show` 只认库内真 UUID**：用合成 id（`hl2C0016`）调会报 `no such entry`、`entry` 恒空，
  把 created_at 探针误判成 0/24。必须先 `rsrs list` 建「标题尾 `｜<hl2 id>` → 真 UUID」映射；
- **`rsrs forget` 同样只认真 UUID**：合成 id 报 `no such entry`；映射后 `forget <UUID>` 返回
  `{"deleted": true}`，tombstone 后 recall 不再返回目标、邻居 `show`/`recall` 不受影响；
- **import 回执 `local_total` 是 null**：只能等索引 ready 后从 `rsrs status` 读到 280。

## 纪律

- 真库只读；不碰 `~/.rsrs`；不改全局 config；不启停宿主 runtime；
- `collect_h6.py` 默认 dry-run，真跑要显式 `--run`；
- 脱敏：全合成，无真人姓名（只用「同事甲/同事乙」）、无真库 id、无凭据；UUID 形态自检 0 命中；
  产物里 `｜<hl2 id>` 映射用，真 UUID 不落盘。

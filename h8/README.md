# H8 记忆动力学层（AGI 分水岭③⑥：边干边学 + 长程衰减）

`agimem/h8/` —— H8 四子类：C1 一次观察泛化、C2 跨间隔召回、C3 远期检索、C4 增量编辑。
本轮**只建数据与判分链，不跑分**（不调真库 recall、不产出分数），交付确定性 seed 的
评测集 + 机械 gold + 判分脚本 + 自检，供后续跑分直接接入。

## 四子类

| 子类 | 测什么 | 题量 | gold 机械推导 | 指标口径 |
|---|---|---|---|---|
| **C1 一次观察泛化** | 一条观察 → 同一规则施于新实例；题面不复述规则原文 | 16 | gold=观察节点 | `hit@1` / `hit@5` |
| **C2 跨间隔召回** | 1h / 1d / 7d / 30d 老条目还在不在 | 16（每档 4） | gold=该老条目（`created_at` 回拨） | `hit@1/5` 按 age 分层 + `aged_nonzero` |
| **C3 远期检索** | 强化事件 vs 平凡日常 vs 灰尘池 | 16 | gold=强化件 | `not_buried@1` / `not_buried@5` |
| **C4 增量编辑** | 规则改 3 次，答「现在是什么」 | 16 | gold=最后一版 | `edited_hit@1/5` + `stale_top1_rate` / `stale_ahead_rate` |

**总题量 64，四子类各 16。** 语料 192 节点。

## 三条红线

1. **C1 必须故意词面错位** —— 题面与观察正文最长连续重合 <6 字（本轮实测 max=5），
   `h8_gold.verify_gold` 正向断言，反向（字面复制题面）被拦截。否则测成字面检索，
   重蹈 H6 v3「满分反而没测到分水岭」。这直接打在已证边界上：m3 是字面检索，
   H6 P6「为什么 / 原因是」21/21 全空召回。
2. **C2 不把时间戳当成已生效的衰减** —— 老条目只用 `created_at` 回拨模拟间隔，不真等时间。
   正向断言只是「老条目召回率不为 0」（`aged_nonzero`）。H3 v2 已证：同文两条的先后主要是
   插入顺序，`created_at` 与插入顺序拆不开，「系统是否认时间」未验证。**若产品无衰减机制，
   跑分时如实写「无衰减，是数据库行为非类人」，不许造假分。**
3. **铁律三道断言（生成期强制，记忆 cdf155a9）** —— 场景 ∈ 八场景白名单（部署上线 / 灰度发布 /
   接口对接 / 同事交接 / 开会定口径 / 线上排障 / 数据迁移 / 权限审批）、题面含该场景标志词、
   不命中禁题材词。真实工单场景，禁科幻纯数学。

## 零 LLM + 确定性

- gold 由构造机械推出，`h8_gold.verify_gold` 与落盘 `gold_expr` 逐字段对账。
- `seed=20261110`，`gen_h8.py --verify` 重生成与落盘一致（`digest=bfcfda8b330f64c1`）。
- 全合成，无真人姓名（只用「同事甲 / 同事乙」）、无真库 id、无凭据；id 前缀 `h8{场景字母}{4位}`。

## C2 陈化口径

不真等时间。四档 `created_at`（同档 4 条同一时刻）：

| 档 | created_at |
|---|---|
| 1h | `2026-11-10T08:00:00Z` |
| 1d | `2026-11-09T10:00:00Z` |
| 7d | `2026-11-03T10:00:00Z` |
| 30d | `2026-10-11T10:00:00Z` |

## C3 灰尘池

每题同一 topic：5 条 dust（例行巡检）+ 1 条 plain + 1 条 salient（gold）。
词面臂 lexical 在 C3 上实测 `not_buried@5=1.0`——灰尘池与题面同词面，bigram 天然捞得到。
这是设计事实，不是分数；「不被淹没」要靠真库语义检索才分得开。

## C4 与已证缺口

生成器在合成树上显式种 `superseded_by`（v1→v2→v3，v3 为空）。这是评测侧 oracle 边。
产品侧已证：`import` 把 `supersedes` / `superseded_by` 写成空串，真写要走
`rsrs remember --importance important --supersedes <old_id>`；recall 排序**不用**取代标记。
本轮不入库、不跑分。`stale_top1_rate` 只是缺口的判分位，跑分阶段若旧版霸榜即坐实。

## 脱敏

产物只落合成 id（`h8A0001` 等）。`BANNED_SNIPPETS`（`sk-` / `password` / `口令` /
`api key` / `密钥串`）是黑名单断言，不是真凭据。本轮不碰真库 `~/.rsrs`。

## 用法

```bash
cd agimem/h8
python3 gen_h8.py                 # 写 data/h8_tree.json + dataset/h8_evalset.jsonl
python3 gen_h8.py --verify        # 确定性证明
python3 score_h8.py --verify-only # 只验 gold
python3 selftest_h8.py            # 全自检（本轮 PASS）
```

跑分时（后续，本轮不做）：

```bash
python3 score_h8.py --dataset dataset/h8_evalset.jsonl \
  --predictions fixtures/h8-perfect.jsonl --topk 5 --json
```

## 文件

- `scenarios.py` —— 八场景白名单（由 h7 复制后改用途）
- `gen_h8.py` —— 四子类生成器
- `h8_gold.py` —— `evaluate_expr` + `verify_gold`
- `score_h8.py` —— Wilson CI 面板，`--verify-only`
- `selftest_h8.py` —— 全自检 + perfect / adversarial / lexical 三臂
- `data/h8_tree.json` —— 192 节点
- `dataset/h8_evalset.jsonl` —— 64 题
- `fixtures/h8-{perfect,adversarial,lexical}.jsonl` —— 合成臂

## 与其它层的关系

场景白名单沿用 H6 / H7 同一套八场景。H6 测「数据库做不到的六件事」，H7 测跨跳与诚实，
H8 测时间维度上的形成、沉睡、浮出与被改写。详见 `tests/41-growth-forgetting.md`。
词面臂对照义务沿 H7 T42：真跑时须同时报真实分数与 lexical 基线的差值，不得把词面命中当成类人分。

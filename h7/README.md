# H7 跨跳与诚实层（AGI 分水岭①②：多跳传递 + 缺证据认「不知道」）

`h7/` —— H7 四子类：L1 多跳链、L2 混跳辨析、L3 缺证据拒答、L4 增广认同。
本轮**只建数据与判分链，不跑分**（不调真库 recall、不产出分数），交付确定性 seed 的
评测集 + 机械 gold + 判分脚本 + 自检，供后续层跑分时直接接入。

## 四子类

| 子类 | 测什么 | 题量 | gold 机械推导 | 指标口径 |
|---|---|---|---|---|
| **L1 多跳链** | 3–4 跳关系链传递，链深 1/2/3/4 分层 | 16（每深 4 条） | `parent` 链机械推导链头（`h7_gold.chain_head`） | `chain_hit@1` / `chain_hit@5`，按 hops 分层 |
| **L2 混跳辨析** | N 跳 vs M 跳同题面，辨清是几跳 | 16（2 跳 8 / 3 跳 8） | `chain_depth` 复算链尾真实跳数 | `mixed_accuracy`（答对跳数比例） |
| **L3 缺证据拒答** | 三档诱饵：谱内已问 / 谱内未写 / 谱外 | 24（三档各 8） | 谱内未写与谱外属性全语料 0 次出现 → `abstain` | `abstain_precision` / `abstain_recall` + `closed_ended_F1` 双侧 |
| **L4 增广认同** | 同事实的改写/换语/句序变体，golden 池 hit | 24（三式各 8） | gold=原事实节点 | `aug_hit@1` / `aug_hit@5`，按式分 |

**总题量 80 ≥64，四子类各 ≥16。**

## 三条红线（上一轮的坑，本层已避开）

1. **L4 增广必须故意词面错位** —— 改写（换同义词）/ 换语（倒装叙述）/ 句序（结论前置）三式，
   题面与原事实正文**最长连续重合仅 1 字**（远 <12 阈值），`h7_gold.verify_gold` 正向断言
   「无连续 12 字重合」，反向测试（字面复制题面）**被拦截**。否则测成字面检索 = H6 v3
   「满分反而没测到分水岭」的教训。
2. **判分/比对单条 python 命令一次算完** —— selftest 与 `gen_h7 --verify` 都是一次跑完，
   不循环重跑同一命令。
3. **铁律三道断言（生成期强制，不是声明）** —— 场景 ∈ 白名单（八场景：部署上线/灰度发布/
   接口对接/同事交接/开会定口径/线上排障/数据迁移/权限审批）、题面含该场景标志词、
   不命中禁题材词（科幻/纯数学/图案/魔法等）；真实工单/排障/交接/发布链，禁科幻纯数学。
   另加**三档诱饵「确未写入」断言**：谱内未写与谱外属性在全语料 0 次出现。

## 零 LLM + 确定性

- **零 LLM gold**：四子类 gold 全由树结构（`parent` 链 / 属性来源 / 增广映射）机械推导，
  `h7_gold.verify_gold` 把推导重跑一遍与落盘 `gold_expr` 逐字段对账。
- **确定性 seed**：`seed=20261110`，`gen_h7.py --verify` 重生成与落盘比对
  （`digest=35eef14a40b6fb0d`），证明可复现。
- **合成语料**：全合成，无真人姓名（只用「同事甲/同事乙」）、无真库 id、无凭据；
  id 前缀 `h7{场景字母}{4位}`，脱敏扫描 UUID=0。

## 脱敏

产物只落合成 id（`h7A0001` 等），不夹真 UUID；正文扫描无 `sk-`/`password`/`口令`/
`api key`/`密钥串`（`gen_h7.py` 的 `BANNED_SNIPPETS` 是**黑名单断言**，非真凭据）。
本轮**不碰真库** `~/.rsrs`，不跑任何 recall。

## 用法

```bash
cd h7
python3 gen_h7.py              # 写 data/h7_tree.json + dataset/h7_evalset.jsonl
python3 gen_h7.py --verify     # 确定性证明（重生成与落盘比对）
python3 score_h7.py --verify-only   # 只验 gold 复算（本轮不跑分）
python3 selftest_h7.py         # 全自检：铁律/诱饵/词面错位/gold复算/四子类判分
```

跑分时（后续层）：
```bash
python3 score_h7.py --dataset dataset/h7_evalset.jsonl \
  --predictions fixtures/h7-perfect.jsonl --topk 5 --json
```

## 文件

- `scenarios.py` —— 八场景白名单 + 词库（谱内已写/谱内未写诱饵/谱外诱饵/L4 增广素材）
- `gen_h7.py` —— 四子类生成器，铁律三道 + 诱饵断言 + `--verify` 确定性
- `h7_gold.py` —— `evaluate_expr`（四子类判分）+ `verify_gold`（机械复算对账）
- `score_h7.py` —— Wilson CI 判分面板，四子类指标，`--verify-only`
- `selftest_h7.py` —— 全自检 + perfect/adversarial/lexical 三臂对照
- `data/h7_tree.json` —— 144 节点（含 `parent` 链）
- `dataset/h7_evalset.jsonl` —— 80 题
- `fixtures/h7-{perfect,adversarial,lexical}.jsonl` —— 合成 recall 臂

## 与其它层的关系

场景白名单刻意沿用 H6（`humanlike2/`）同一套八场景，使 H6/H7 两层数字在**同一题材
约束**下可比；但题目形态、gold 与判分完全不同。H6 测「数据库做不到的六件事」，H7 测
「跨跳传递 + 缺证据认不知道」。详见 `tests/40-crosshop-honest.md`。

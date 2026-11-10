# H9 推理与元认知层（AGI 分水岭④⑤）

与 H4（`tricky/`，回顾准不准）、H6（`humanlike2/`，数据库做不到的六件事）同套八场景白名单，
H9 测**推理与元认知**：R1 因果归因→处方 / R2 反事实 / R3 动态更新 / R4 压缩摘要 / R5 元认知 / R6 跨来源置信。
零 LLM、gold 机械、铁律三道断言；详见 `tests/42-reasoning-metacog.md`。

## 目录

| 文件 | 用途 |
|---|---|
| `scenarios.py` | 八场景白名单 + 词库 + `node()`/`tpl()`/`Alloc`（前缀 `hl9`，与 H4/H6 同套） |
| `gen_h9.py` | seed 生成语料与评测集，7 组守门断言在落盘前强制（含 R1/R4 不复述） |
| `h9_gold.py` | 六子类 gold 机械推导 + `verify_gold()` 对账 + `evaluate_expr()` 判分 |
| `score_h9.py` | 指标汇总（Wilson CI、等权 composite、stale/retell 霸榜率） |
| `selftest_h9.py` | 全链路自检（确定性/gold/计数/铁律/不复述+负样本/三臂区分度），40 PASS |
| `data/h9_tree.json` | 232 节点全合成语料 |
| `dataset/h9_evalset.jsonl` | 96 题（R1–R6 各 16） |
| `fixtures/` | perfect / adversarial / lexical 三条合成臂 |
| `results/h9-selftest-arms.json` | 三臂 composite、class_scores 与霸榜率 |

## 快速跑

```bash
cd h9
python3 gen_h9.py            # 生成（232 节点 / 96 题，seed=20261110）
python3 gen_h9.py --verify   # 确定性重生成字节一致
python3 score_h9.py --verify-only   # 只验 gold 机械可复算
python3 selftest_h9.py       # 全链路自检（应 40 PASS）
```

**本轮不跑分**：真库 recall / collect 尚未接（未验证，见 tests/42 §七）。
真跑时注意：R5 探针 search-only（只查询不写库）、真库绝对只读；
R6 复现 T6 转述霸榜口径（H4 实测 86.4%）看 `retell_crown_rate`；
R3 旧条目霸榜看 `stale_crown_rate`。

## 自检速览（2026-11-10）

- `gen --verify` rc=0，digest `1e7289f580138a5f`；gold 复算 96 题 0 错；
- selftest **40 PASS / 0 FAIL**；
- 三臂 composite：perfect **1.000** / adversarial **0.000** / lexical **0.507**；
- lexical 臂 R6 转述霸榜 **0.9375**、实测优先 0.000（纯字面即复现 T6 现象）；
- lexical 臂 R1=0.000（处方召回跨措辞，字面全灭）、R5 未记探针硬凑 0.000。

## 拟增主 README 索引行（写入范围外，待首辅裁决）

```
| 42 | [agimem H9 推理与元认知：六子类题库落地](tests/42-reasoning-metacog.md) | 全合成 96 题（R1–R6 各 16、232 节点），seed 20261110，零 LLM，铁律三道 + R1/R4 不复述断言，本轮不跑分 | 自检 40 PASS；三臂 perfect 1.000 / adversarial 0.000 / lexical 0.507；合成词面臂 R6 转述霸榜 0.9375·实测优先 0.000（纯字面即复现 T6 86.4% 机制）；R3 stale/R6 retell 霸榜率口径就位待真跑 | 11-10 |
```

## 纪律

- 真库只读；不碰 `~/.rsrs`；不改全局 config；不启停宿主 runtime；
- 零 LLM：生成/判分/自检全规则化，`--verify` 确定性证明；
- 脱敏：全合成，无真人姓名（只用「同事甲/同事乙」）、无真库 id、无凭据；
  `sk-`/`password`/`口令`/UUID 断言 0 命中。

# mem0 对照组（interop）

把 agimem 的合成语料灌进 **mem0**，取召回预测，再用 agimem 各层**原封不动的判分器**打分。
本目录只负责「怎么跑」，不含任何评测数字；数字与结论归档在 respire-benchmark 仓的 `tests/` 与 `results/`。

## 文件

| 文件 | 用途 |
|---|---|
| `m3_embedder.py` | bge-m3 ONNX 嵌入器 + mem0 工厂注册（`m3onnx` provider） |
| `run_layer_mem0.py` | `--layer h6\|h7\|h8\|h9`：灌库 → 召回 → 落 predictions / run-stats |

## 怎么跑

```bash
# 依赖：mem0ai + chromadb + onnxruntime + tokenizers；本地 bge-m3 在 ~/.rsrs/models/bge-m3
python3 -m venv .venv && . .venv/bin/activate
pip install mem0ai chromadb onnxruntime tokenizers

python3 interop/mem0/run_layer_mem0.py --layer h6 --out-dir /tmp/mem0-out
python3 interop/mem0/run_layer_mem0.py --layer h9 --out-dir /tmp/mem0-out
```

产出（每层一个子目录）：`<layer>-mem0-predictions.jsonl`（top_k=20）、
`<layer>-mem0-predictions-top5.jsonl`（同预测截断，供口径对照）、
`<layer>-subset-evalset.jsonl`（该层实际可跑的题，交给判分器）、`<layer>-mem0-run-stats.json`。

拿预测去判分时用各层原生判分器，**不要改判分器**：

```bash
cd h7 && python3 score_h7.py --dataset <out>/h7/h7-subset-evalset.jsonl \
    --predictions <out>/h7/h7-mem0-predictions.jsonl --topk 20
```

`score_h9.py` 会把汇总写到 `h9/results/h9-score.json`；若不想覆盖仓内已有产物，先把 `h9/` 拷到临时目录再跑。

## 口径（为什么这么配）

**1. 主臂 `add(infer=False)`。** agimem 的 gold 绑合成条目 id，LLM 抽取会合并/改写正文并重算 id，
gold 就断了；rsrs 侧也是把条目原样入库，两边都走「原样入库」才可比。开 LLM 抽取的臂不在本 harness 内。

**2. 嵌入与 rsrs 同源。** 必须用本地 bge-m3，否则比的就变成嵌入模型而不是记忆系统。
本机 bge-m3 是 `Xenova/bge-m3` 的 **ONNX 导出、没有 torch 权重**，sentence-transformers 加载不了，
所以 `m3_embedder.py` 直接跑 `onnx/model_quantized.onnx`，口径逐条对齐
`respire-cli/core/crates/memory-core/src/bge.rs` 的 `M3_SPEC`：
**1024 维 / CLS pooling / L2 归一 / 截断 512 token / 无查询前缀**。
（`add` 与 `search` 用同一个 embedder 实例，不做 query/passage 区分——m3 的 M3_SPEC 前缀本来就是空。）

**3. chroma 本地持久化，纯稠密。** mem0 接 chroma 时会自己打日志：
`The 'chroma' vector store does not support keyword search. Hybrid (BM25) scoring will be disabled`。
所以这一臂是**语义检索单通道**；rsrs 侧是语义 + 关键词加成 + 热度的混合，这条差异要写进对照结论。

**4. `top_k=20` 是 mem0 原生缺省。** harness 同时产出 5 条派生臂，因为 **abstain 类指标对 top_k 极敏感**
（池子越大，诱饵越有机会被带出来），而 rsrs 历史各层多用 top5，两边必须连 top_k 一起报。

**5. 关闭遥测。** `MEM0_TELEMETRY=False`，bench 语料不回传。

## 三条结构性不可复现（不是「分低」，是「测不了」）

| 子类 | 原因 |
|---|---|
| **H7 L1 多跳 / L2 链深** | mem0 没有 parent 边、没有链结构，多跳无从走。任何「词面命中」都不等于多跳能力，不作数。 |
| **H8 C2 陈化** | `add(timestamp=...)` 直接抛 `ValueError: The timestamp parameter is not supported by the OSS Memory SDK.` 落库 `created_at` 是灌库时刻，不是语料的显式时间。拿灌库时间冒充陈化时间就是造假。 |
| **H8 C4 认最新版** | mem0 的向量库条目上**没有 `superseded_by` 字段**（实测 metadata 只有 `created_at/data/hash/role/scenario/syn_id/text_lemmatized/topic/updated_at/user_id`），也没有取代关系可读。它能「认对」最新版只可能是文本相似度撞对的，**不能读成具备取代语义**。 |

H6 P3（主动遗忘）相反是**真能跑**的：mem0 有 `delete()`，harness 会删掉 12 个目标记忆再跑 post 相位，
删后库内条数减少可核。这与 H7/H8 那三条「测不了」要分开说。

## 边界

- 产物只含**合成 id**（`hl2…` / `h7…` / `h8…` / `hl9…`），真 UUID 只在内存里做映射，落盘前扫一遍 UUID 正则，命中即中止。
- 不读写任何真实用户库；chroma 目录默认落在 `/tmp/agimem-mem0/<layer>`。
- 判分器（`score_h6/h7/h8/h9.py`、`*_gold.py`）与题库一律不改。

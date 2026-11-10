# agimem

给记忆系统打分的自研评测套件：**search-only、零 LLM 判分**，面向 AGI 的类人记忆能力测量。

不接答题模型，只看「召回到了什么」；gold 由题目构造机械推导，比例类指标一律给 Wilson 95% CI。
全部语料为合成数据，只跑隔离库，不读写任何真实用户库。

## 两个维度并列，不给总分

| 维度 | 回答的问题 | 子层 |
|---|---|---|
| **M** 机器向（工程效能） | 能不能用：召回准不准、快不快、贵不贵 | M1 召回率 / M2 速度 / M3 token 用量 |
| **H** 类人向（类人记忆，主线） | 像不像人：会不会强化、衰减、纠错、遗忘 | H1–H9 |

**两维度分开报，禁止合成一个单分。** 理由不是洁癖：子层的 gold 空间（合成短 id / 真库 UUID / 对话文本）、
题型（命中 vs 答对）、判分层（search-only vs 端到端 LLM judge）三者都不同，横比无意义。
维度内可纵向比，跨维度不可横比。详见 [EVALUATION.md](EVALUATION.md)。

## 层目录

| 维度 | 子层 | 测什么 | 产物 |
|---|---|---|---|
| M | M1 召回率 | hit@1/3/5/10/20、MRR | [machine/results/machine-scorecard.json](machine/results/machine-scorecard.json) |
| M | M2 速度 | 召回延迟 p50/p95/p99、吞吐、冷启动 | 同上（`machine-scorecard.md` 有人读版） |
| M | M3 token 用量 | 召回返回正文/标题 token、注入成本 | 同上 |
| H | H1 通用基准 | LoCoMo conv-0 五类题的检索层与端到端 | [results/locomo-session-hit.json](results/locomo-session-hit.json)、[results/locomo-e2e.json](results/locomo-e2e.json) |
| H | H2 因果记忆 | 链追溯 / 干预预警 / 取代感知 / 负样本噪声（122 题） | [results/causal-isolated-panel.md](results/causal-isolated-panel.md) |
| H | H3 记忆动力学 | 重复强化 / 时间衰减 / 错误纠偏 | [results/human-dimension-v2.json](results/human-dimension-v2.json)、[human_memory/README.md](human_memory/README.md) |
| H | H4 刁钻工作场景 | 抗干扰 / 同名异事 / 隐含约束 / 旧结论失效 / 跨时一致 | [tricky/results/panel-real.md](tricky/results/panel-real.md) |
| H | H5 多语言 | 同一记忆 zh/en/ja/es 是否等价 | [i18n/results/i18n-score.json](i18n/results/i18n-score.json) |
| H | H6 分水岭（人 vs 数据库） | 前瞻 / 错误记忆 / 主动遗忘 / 来源监控 / 时间线 / 重构性 | [humanlike2/results/h6-isolated.json](humanlike2/results/h6-isolated.json) |
| H | H7 跨跳与诚实 | 多跳链 / 混跳辨析 / 缺证据拒答 / 换说法仍认得 | [h7/results/h7-isolated.json](h7/results/h7-isolated.json) |
| H | H8 生长与遗忘 | 一次观察泛化 / 陈化 / 不被淹没 / 认最新版 | [h8/results/h8-iso-panel.json](h8/results/h8-iso-panel.json) |
| H | H9 推理与元认知 | 处方 / 反事实 / 动态更新 / 摘要 / 探针 / 跨来源 | [h9/results/h9-score.json](h9/results/h9-score.json) |

各层自带 `README.md`（见 `h7/`、`h8/`、`h9/`、`tricky/`、`humanlike2/`、`human_memory/`），
写明题型、gold 来源、判分口径与本轮实测数字。总口径与全部实测值见 [EVALUATION.md](EVALUATION.md)。

## 如何复现

每层都是「生成器 → 题库 → 判分器 → 自检」四件套，链路自洽，可离线跑完：

```bash
python3 <layer>/gen_*.py            # 确定性 seed 生成语料与题库
python3 <layer>/gen_*.py --verify   # 重新生成并与落盘逐字节比对（确定性证明）
python3 <layer>/score_*.py --verify-only   # gold 与语料重算对账
python3 <layer>/selftest_*.py       # perfect / adversarial / lexical 三臂对照
```

要拿真实系统的分，需把它导入**隔离库**再 recall。隔离三件套（缺一即污染真实库）：

```bash
# 1) 独立目录 + 2) 独立端口 + 3) 独立 super，且清掉所有继承的 RSRS_/ONEMEMORY_/RESPIRE_
env -u RSRS_DATA_DIR ... \
  RSRS_DATA_DIR=/tmp/agimem-iso \
  RSRS_RPC_PORT=16345 \
  RSRS_SUPER=<keygen 现场生成> \
  RSRS_NO_AUTOSYNC=1 RSRS_UPDATE_CHECK=0 RSRS_ENGINE=cpu \
  RSRS_M3_DIR=~/.rsrs/models/bge-m3 RSRS_FEEDBACK=0 RSRS_ABLATE=hot \
  rsrs import items.json --json
```

三个必须知道的坑：

1. **就绪判据用 `embedding_model=m3` 且 `state=ready`**，不要用 `retrieval_index.worker_active`——
   后者只表示常驻 worker 进程还活着，恒为 true，拿它判就绪会白等到超时。
2. **建索引约 8 分钟**（200 节点量级、CPU 引擎）。import 立即返回，不等于可召回。
3. **`import` 不写父子边**，要 `rsrs attach <child> --parent <parent>` 逐条补；
   不补的话所有依赖树结构的题（多跳、取代、增量编辑）都会失真。

判分只吃 JSONL 预测文件：`{"qid":"...","hits":[{"id":"...","score":...}]}`，
与题库按 `qid` join，id 匹配用前缀双向语义（与 CLI bench 一致）。

## 贡献与边界

- 全部语料合成、脱敏：无真人姓名、无真库 id、无凭据。产物只落合成 id。
- 出题铁律：真实工作场景（部署/发布/对接/交接/开会定口径），禁科幻与纯数学题面；gold 必须机械可推导。
- 比例类指标一律 Wilson 95% CI；n 小的档位如实标注区间宽度，不拿点估计当结论。
- 分低就说分低。产品没做到的能力，写「未做到」，不写「接近人类」。

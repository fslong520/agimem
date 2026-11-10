# agimem H4 · 刁钻工作场景指标面板

> **醒目声明：本层为全合成题库。若被测库未导入合成记录，下表数字是「题不在库」的检索结果，不是真实系统记忆能力分；perfect/adversarial 是判分器两极自证，不代表任何真实系统水平。**

- 判分参数：topk=5，search-only 零 LLM
- 题量：132/132

## 一、题量与分布

| 刁钻类型 | 人类记忆能力 | 题数 | 权重 |
|---|---|---:|---:|
| T1 | 抗干扰 | 22 | 0.15 |
| T2 | 同名异事 | 22 | 0.20 |
| T3 | 隐含约束 | 22 | 0.20 |
| T4 | 旧结论失效 | 22 | 0.15 |
| T5 | 跨时间一致性 | 22 | 0.15 |
| T6 | 转述vs实测 | 22 | 0.15 |
| **合计** | | **132** | 1.00 |

场景分布：同事交接=17 | 开会定口径=16 | 接口对接=17 | 数据迁移=16 | 权限审批=16 | 灰度发布=17 | 线上排障=16 | 部署上线=17

## 二、每类点估计与 95% CI

| 类型 | hit@k | 95% CI | 主指标 | 主指标值 | 95% CI |
|---|---:|---|---|---:|---|
| T1 抗干扰 | 1.000 | 1.000 [0.851, 1.000] | hit_at_k | 1.000 | 1.000 [0.851, 1.000] |
| T2 同名异事 | 1.000 | 1.000 [0.851, 1.000] | hit_at_1 | 0.045 | 0.045 [0.008, 0.218] |
| T3 隐含约束 | 0.864 | 0.864 [0.667, 0.953] | hit_at_1 | 0.091 | 0.091 [0.025, 0.278] |
| T4 旧结论失效 | 0.955 | 0.955 [0.782, 0.992] | hit_at_1 | 0.182 | 0.182 [0.073, 0.385] |
| T5 跨时间一致性 | 0.545 | 0.545 [0.347, 0.731] | hit_at_1 | 0.000 | 0.000 [0.000, 0.149] |
| T6 转述vs实测 | 0.455 | 0.455 [0.269, 0.653] | evidence_first_acc | 0.000 | 0.000 [0.000, 0.149] |

**类人度总分 = 0.205**（95% CI [0.170, 0.243]，stratified-bootstrap，reps=2000，seed=20261109）

总分口径：`Σ w_i·s_i`。T1 抗干扰 0.15 / T2 同名异事 0.20 / T3 隐含约束 0.20 / T4 失效感知 0.15 / T5 跨时间一致 0.15 / T6 证据分级 0.15。同名异事与隐含约束最依赖常识与场景绑定，权重最高。

## 三、基线对照

| 指标 | 本臂 | perfect | adversarial |
|---|---:|---:|---:|
| T1 抗干扰 主指标 | 1.000 | 1.000 | 0.000 |
| T2 同名异事 主指标 | 0.045 | 1.000 | 0.000 |
| T3 隐含约束 主指标 | 0.091 | 1.000 | 0.000 |
| T4 旧结论失效 主指标 | 0.182 | 1.000 | 0.000 |
| T5 跨时间一致性 主指标 | 0.000 | 1.000 | 0.000 |
| T6 转述vs实测 主指标 | 0.000 | 1.000 | 0.000 |
| **类人度总分** | 0.205 | 1.000 | 0.000 |

## 四、单题下钻（qid → 场景 → gold → top-k → 判分理由）

| qid | 类型 | 场景 | gold | top-k | 判分理由 |
|---|---|---|---|---|---|
| t1-001 | T1 | 部署上线 | trkA0001 | trkA0001,trkA0015,trkA0009,trkA0081,trkB0009 | 真约束 trkA0001；top-5 中同主题干扰记录 0/5；gold rank=0 |
| t1-002 | T1 | 灰度发布 | trkB0001 | trkB0014,trkB0001,trkB0009,trkA0009,trkA0001 | 真约束 trkB0001；top-5 中同主题干扰记录 0/5；gold rank=1 |
| t1-003 | T1 | 接口对接 | trkC0003 | trkC0003,trkC0006,trkC0010,trkA0009,trkG0008 | 真约束 trkC0003；top-5 中同主题干扰记录 0/5；gold rank=0 |
| t1-004 | T1 | 同事交接 | trkD0001 | trkD0001,trkD0007,trkD0013,trkD0077,trkD0087 | 真约束 trkD0001；top-5 中同主题干扰记录 0/5；gold rank=0 |
| t1-005 | T1 | 开会定口径 | trkE0006 | trkE0006,trkE0011,trkE0015,trkE0094,trkD0013 | 真约束 trkE0006；top-5 中同主题干扰记录 0/5；gold rank=0 |
| t1-006 | T1 | 线上排障 | trkF0003 | trkF0003,trkF0013,trkF0010,trkB0009,trkA0009 | 真约束 trkF0003；top-5 中同主题干扰记录 0/5；gold rank=0 |
| t1-007 | T1 | 数据迁移 | trkG0008 | trkG0008,trkG0015,trkF0010,trkC0003,trkC0006 | 真约束 trkG0008；top-5 中同主题干扰记录 0/5；gold rank=0 |
| t1-008 | T1 | 权限审批 | trkH0006 | trkH0006,trkH0012,trkA0009,trkB0009,trkB0014 | 真约束 trkH0006；top-5 中同主题干扰记录 0/5；gold rank=0 |
| t1-009 | T1 | 部署上线 | trkA0009 | trkA0009,trkA0001,trkA0015,trkB0009,trkB0014 | 真约束 trkA0009；top-5 中同主题干扰记录 0/5；gold rank=0 |
| t1-010 | T1 | 灰度发布 | trkB0009 | trkB0009,trkB0014,trkB0001,trkA0009,trkB0096 | 真约束 trkB0009；top-5 中同主题干扰记录 0/5；gold rank=0 |
| t1-011 | T1 | 接口对接 | trkC0006 | trkC0006,trkC0003,trkC0010,trkA0009,trkG0008 | 真约束 trkC0006；top-5 中同主题干扰记录 0/5；gold rank=0 |
| t1-012 | T1 | 同事交接 | trkD0007 | trkD0007,trkD0001,trkD0013,trkE0006,trkB0009 | 真约束 trkD0007；top-5 中同主题干扰记录 0/5；gold rank=0 |
| t1-013 | T1 | 开会定口径 | trkE0011 | trkE0011,trkE0015,trkE0006,trkE0086,trkE0091 | 真约束 trkE0011；top-5 中同主题干扰记录 0/5；gold rank=0 |
| t1-014 | T1 | 线上排障 | trkF0010 | trkF0010,trkF0003,trkF0013,trkG0015,trkG0008 | 真约束 trkF0010；top-5 中同主题干扰记录 0/5；gold rank=0 |
| t1-015 | T1 | 数据迁移 | trkG0015 | trkG0015,trkG0008,trkA0009,trkF0010,trkB0009 | 真约束 trkG0015；top-5 中同主题干扰记录 0/5；gold rank=0 |
| t1-016 | T1 | 权限审批 | trkH0012 | trkH0012,trkH0006,trkA0009,trkH0090,trkB0009 | 真约束 trkH0012；top-5 中同主题干扰记录 0/5；gold rank=0 |
| t1-017 | T1 | 部署上线 | trkA0015 | trkA0015,trkA0001,trkA0009,trkB0009,trkB0014 | 真约束 trkA0015；top-5 中同主题干扰记录 0/5；gold rank=0 |
| t1-018 | T1 | 灰度发布 | trkB0014 | trkB0014,trkB0009,trkB0001,trkB0084,trkA0009 | 真约束 trkB0014；top-5 中同主题干扰记录 0/5；gold rank=0 |
| t1-019 | T1 | 接口对接 | trkC0010 | trkC0010,trkC0003,trkC0006,trkA0009,trkB0009 | 真约束 trkC0010；top-5 中同主题干扰记录 0/5；gold rank=0 |
| t1-020 | T1 | 同事交接 | trkD0013 | trkD0013,trkD0007,trkD0001,trkA0001,trkB0009 | 真约束 trkD0013；top-5 中同主题干扰记录 0/5；gold rank=0 |
| t1-021 | T1 | 开会定口径 | trkE0015 | trkE0011,trkE0015,trkE0006,trkE0086,trkE0091 | 真约束 trkE0015；top-5 中同主题干扰记录 0/5；gold rank=1 |
| t1-022 | T1 | 线上排障 | trkF0013 | trkF0013,trkF0003,trkF0010,trkF0038,trkC0006 | 真约束 trkF0013；top-5 中同主题干扰记录 0/5；gold rank=0 |
| t2-001 | T2 | 数据迁移 | trkG0021 | trkG0028,trkC0012,trkG0070,trkG0021,trkG0027 | 重名物「那个接口」在 migration 的定义 trkG0021；gold rank=3 |
| t2-002 | T2 | 权限审批 | trkH0023 | trkH0030,trkH0037,trkD0015,trkH0023,trkH0093 | 重名物「临时开关」在 approval 的定义 trkH0023；gold rank=3 |
| t2-003 | T2 | 部署上线 | trkA0021 | trkE0017,trkA0036,trkA0021,trkA0028,trkA0032 | 重名物「第二套口径」在 deploy 的定义 trkA0021；gold rank=2 |
| t2-004 | T2 | 灰度发布 | trkB0022 | trkB0031,trkB0026,trkB0035,trkF0016,trkB0022 | 重名物「灰度第一批」在 canary 的定义 trkB0022；gold rank=4 |
| t2-005 | T2 | 接口对接 | trkC0015 | trkG0023,trkC0015,trkC0057,trkC0062,trkC0067 | 重名物「回滚脚本」在 api 的定义 trkC0015；gold rank=1 |
| t2-006 | T2 | 同事交接 | trkD0018 | trkH0027,trkD0018,trkD0057,trkD0062,trkD0026 | 重名物「V2 方案（第二批）」在 handoff 的定义 trkD0018；gold rank=1 |
| t2-007 | T2 | 开会定口径 | trkE0019 | trkA0025,trkE0016,trkE0019,trkE0027,trkE0067 | 重名物「那个接口（第二批）」在 meeting 的定义 trkE0019；gold rank=2 |
| t2-008 | T2 | 线上排障 | trkF0018 | trkB0023,trkF0014,trkF0018,trkF0026,trkF0077 | 重名物「临时开关（第二批）」在 ops 的定义 trkF0018；gold rank=2 |
| t2-009 | T2 | 数据迁移 | trkG0029 | trkG0034,trkC0016,trkG0070,trkG0029,trkG0028 | 重名物「第二套口径（第二批）」在 migration 的定义 trkG0029；gold rank=3 |
| t2-010 | T2 | 权限审批 | trkH0031 | trkH0042,trkD0020,trkH0031,trkH0081,trkH0025 | 重名物「灰度第一批（第二批）」在 approval 的定义 trkH0031；gold rank=2 |
| t2-011 | T2 | 部署上线 | trkA0029 | trkE0021,trkA0029,trkA0033,trkA0067,trkA0072 | 重名物「回滚脚本（第二批）」在 deploy 的定义 trkA0029；gold rank=1 |
| t2-012 | T2 | 灰度发布 | trkB0027 | trkF0020,trkB0027,trkB0029,trkB0074,trkB0079 | 重名物「V2 方案（第三批）」在 canary 的定义 trkB0027；gold rank=1 |
| t2-013 | T2 | 接口对接 | trkC0019 | trkC0019,trkG0033,trkA0034,trkC0024,trkC0020 | 重名物「那个接口（第三批）」在 api 的定义 trkC0019；gold rank=0 |
| t2-014 | T2 | 同事交接 | trkD0022 | trkH0036,trkD0022,trkD0057,trkD0062,trkD0024 | 重名物「临时开关（第三批）」在 handoff 的定义 trkD0022；gold rank=1 |
| t2-015 | T2 | 开会定口径 | trkE0024 | trkA0031,trkE0024,trkE0018,trkE0028,trkE0062 | 重名物「第二套口径（第三批）」在 meeting 的定义 trkE0024；gold rank=1 |
| t2-016 | T2 | 线上排障 | trkF0024 | trkB0030,trkF0024,trkF0022,trkF0021,trkF0077 | 重名物「灰度第一批（第三批）」在 ops 的定义 trkF0024；gold rank=1 |
| t2-017 | T2 | 数据迁移 | trkG0036 | trkC0021,trkG0036,trkG0070,trkG0034,trkG0031 | 重名物「回滚脚本（第三批）」在 migration 的定义 trkG0036；gold rank=1 |
| t2-018 | T2 | 权限审批 | trkH0040 | trkH0033,trkD0025,trkH0040,trkH0081,trkH0028 | 重名物「V2 方案（第四批）」在 approval 的定义 trkH0040；gold rank=2 |
| t2-019 | T2 | 部署上线 | trkA0034 | trkE0026,trkA0030,trkA0062,trkA0034,trkA0026 | 重名物「那个接口（第四批）」在 deploy 的定义 trkA0034；gold rank=3 |
| t2-020 | T2 | 灰度发布 | trkB0034 | trkF0025,trkB0034,trkB0024,trkB0079,trkB0086 | 重名物「临时开关（第四批）」在 canary 的定义 trkB0034；gold rank=1 |
| t2-021 | T2 | 接口对接 | trkC0026 | trkG0039,trkC0017,trkC0026,trkC0018,trkC0024 | 重名物「第二套口径（第四批）」在 api 的定义 trkC0026；gold rank=2 |
| t2-022 | T2 | 同事交接 | trkD0030 | trkH0041,trkD0030,trkD0021,trkD0062,trkD0057 | 重名物「灰度第一批（第四批）」在 handoff 的定义 trkD0030；gold rank=1 |
| t3-001 | T3 | 开会定口径 | trkE0030 | trkE0041,trkE0084,trkE0095,trkE0035,trkE0036 | 隐含规矩（implicit=true）trkE0030；gold rank=None |
| t3-002 | T3 | 线上排障 | trkF0028 | trkF0037,trkF0028,trkF0027,trkF0038,trkF0058 | 隐含规矩（implicit=true）trkF0028；gold rank=1 |
| t3-003 | T3 | 数据迁移 | trkG0042 | trkG0048,trkG0050,trkG0042,trkG0040,trkG0043 | 隐含规矩（implicit=true）trkG0042；gold rank=2 |
| t3-004 | T3 | 权限审批 | trkH0044 | trkH0043,trkH0055,trkH0053,trkH0044,trkH0045 | 隐含规矩（implicit=true）trkH0044；gold rank=3 |
| t3-005 | T3 | 部署上线 | trkA0039 | trkA0039,trkA0038,trkA0040,trkA0041,trkA0042 | 隐含规矩（implicit=true）trkA0039；gold rank=0 |
| t3-006 | T3 | 灰度发布 | trkB0037 | trkB0049,trkB0050,trkB0042,trkB0037,trkB0097 | 隐含规矩（implicit=true）trkB0037；gold rank=3 |
| t3-007 | T3 | 接口对接 | trkC0027 | trkC0083,trkC0040,trkC0027,trkC0076,trkC0087 | 隐含规矩（implicit=true）trkC0027；gold rank=2 |
| t3-008 | T3 | 同事交接 | trkD0031 | trkD0036,trkD0031,trkD0041,trkD0032,trkD0033 | 隐含规矩（implicit=true）trkD0031；gold rank=1 |
| t3-009 | T3 | 开会定口径 | trkE0037 | trkE0042,trkE0036,trkE0043,trkE0092,trkE0044 | 隐含规矩（implicit=true）trkE0037；gold rank=None |
| t3-010 | T3 | 线上排障 | trkF0032 | trkF0088,trkF0037,trkF0032,trkF0027,trkF0036 | 隐含规矩（implicit=true）trkF0032；gold rank=2 |
| t3-011 | T3 | 数据迁移 | trkG0051 | trkG0048,trkG0050,trkG0051,trkG0047,trkG0052 | 隐含规矩（implicit=true）trkG0051；gold rank=2 |
| t3-012 | T3 | 权限审批 | trkH0049 | trkH0048,trkH0091,trkH0049,trkH0053,trkH0093 | 隐含规矩（implicit=true）trkH0049；gold rank=2 |
| t3-013 | T3 | 部署上线 | trkA0044 | trkA0038,trkA0043,trkA0044,trkA0045,trkA0046 | 隐含规矩（implicit=true）trkA0044；gold rank=2 |
| t3-014 | T3 | 灰度发布 | trkB0044 | trkB0041,trkB0091,trkB0043,trkB0044,trkB0050 | 隐含规矩（implicit=true）trkB0044；gold rank=3 |
| t3-015 | T3 | 接口对接 | trkC0031 | trkC0077,trkC0038,trkC0039,trkC0031,trkC0036 | 隐含规矩（implicit=true）trkC0031；gold rank=3 |
| t3-016 | T3 | 同事交接 | trkD0037 | trkD0091,trkD0037,trkD0041,trkD0032,trkD0033 | 隐含规矩（implicit=true）trkD0037；gold rank=1 |
| t3-017 | T3 | 开会定口径 | trkE0045 | trkE0049,trkE0036,trkE0044,trkE0094,trkE0041 | 隐含规矩（implicit=true）trkE0045；gold rank=None |
| t3-018 | T3 | 线上排障 | trkF0039 | trkF0037,trkF0027,trkF0038,trkF0039,trkF0043 | 隐含规矩（implicit=true）trkF0039；gold rank=3 |
| t3-019 | T3 | 数据迁移 | trkG0056 | trkG0041,trkG0040,trkG0049,trkG0055,trkG0056 | 隐含规矩（implicit=true）trkG0056；gold rank=4 |
| t3-020 | T3 | 权限审批 | trkH0056 | trkH0048,trkH0056,trkH0043,trkH0055,trkH0093 | 隐含规矩（implicit=true）trkH0056；gold rank=1 |
| t3-021 | T3 | 部署上线 | trkA0048 | trkA0081,trkA0048,trkA0049,trkA0050,trkA0051 | 隐含规矩（implicit=true）trkA0048；gold rank=1 |
| t3-022 | T3 | 灰度发布 | trkB0051 | trkB0051,trkB0092,trkB0050,trkB0036,trkB0043 | 隐含规矩（implicit=true）trkB0051；gold rank=0 |
| t4-001 | T4 | 接口对接 | trkC0041 | trkC0051,trkC0041,trkC0042,trkC0035,trkC0078 | 旧结论 trkC0042 → superseded_by trkC0041；gold rank=1 |
| t4-002 | T4 | 同事交接 | trkD0042 | trkD0047,trkD0055,trkD0043,trkD0042,trkD0062 | 旧结论 trkD0043 → superseded_by trkD0042；gold rank=3 |
| t4-003 | T4 | 开会定口径 | trkE0051 | trkE0059,trkE0060,trkE0052,trkE0051,trkE0020 | 旧结论 trkE0052 → superseded_by trkE0051；gold rank=3 |
| t4-004 | T4 | 线上排障 | trkF0045 | trkF0046,trkF0045,trkF0083,trkF0076,trkF0087 | 旧结论 trkF0046 → superseded_by trkF0045；gold rank=1 |
| t4-005 | T4 | 数据迁移 | trkG0060 | trkG0061,trkG0067,trkG0068,trkG0060,trkG0016 | 旧结论 trkG0061 → superseded_by trkG0060；gold rank=3 |
| t4-006 | T4 | 权限审批 | trkH0062 | trkH0071,trkH0062,trkH0063,trkH0069,trkH0068 | 旧结论 trkH0063 → superseded_by trkH0062；gold rank=1 |
| t4-007 | T4 | 部署上线 | trkA0054 | trkA0055,trkA0054,trkA0057,trkA0059,trkA0058 | 旧结论 trkA0055 → superseded_by trkA0054；gold rank=1 |
| t4-008 | T4 | 灰度发布 | trkB0059 | trkB0056,trkB0060,trkB0059,trkB0063,trkB0064 | 旧结论 trkB0060 → superseded_by trkB0059；gold rank=2 |
| t4-009 | T4 | 接口对接 | trkC0045 | trkC0056,trkC0052,trkC0046,trkC0053,trkC0078 | 旧结论 trkC0046 → superseded_by trkC0045；gold rank=None |
| t4-010 | T4 | 同事交接 | trkD0050 | trkD0050,trkD0051,trkD0049,trkD0054,trkD0053 | 旧结论 trkD0051 → superseded_by trkD0050；gold rank=0 |
| t4-011 | T4 | 开会定口径 | trkE0056 | trkE0055,trkE0057,trkE0056,trkE0025,trkE0094 | 旧结论 trkE0057 → superseded_by trkE0056；gold rank=2 |
| t4-012 | T4 | 线上排障 | trkF0053 | trkF0055,trkF0054,trkF0060,trkF0053,trkF0059 | 旧结论 trkF0054 → superseded_by trkF0053；gold rank=3 |
| t4-013 | T4 | 数据迁移 | trkG0062 | trkG0062,trkG0063,trkG0089,trkG0046,trkG0047 | 旧结论 trkG0063 → superseded_by trkG0062；gold rank=0 |
| t4-014 | T4 | 权限审批 | trkH0068 | trkH0071,trkH0062,trkH0063,trkH0069,trkH0068 | 旧结论 trkH0069 → superseded_by trkH0068；gold rank=4 |
| t4-015 | T4 | 部署上线 | trkA0058 | trkA0057,trkA0059,trkA0058,trkA0055,trkA0054 | 旧结论 trkA0059 → superseded_by trkA0058；gold rank=2 |
| t4-016 | T4 | 灰度发布 | trkB0063 | trkB0063,trkB0064,trkB0056,trkB0060,trkB0059 | 旧结论 trkB0064 → superseded_by trkB0063；gold rank=0 |
| t4-017 | T4 | 接口对接 | trkC0052 | trkC0056,trkC0052,trkC0046,trkC0053,trkC0078 | 旧结论 trkC0053 → superseded_by trkC0052；gold rank=1 |
| t4-018 | T4 | 同事交接 | trkD0053 | trkD0049,trkD0050,trkD0051,trkD0054,trkD0053 | 旧结论 trkD0054 → superseded_by trkD0053；gold rank=4 |
| t4-019 | T4 | 开会定口径 | trkE0059 | trkE0059,trkE0060,trkE0052,trkE0051,trkE0020 | 旧结论 trkE0060 → superseded_by trkE0059；gold rank=0 |
| t4-020 | T4 | 线上排障 | trkF0059 | trkF0055,trkF0059,trkF0054,trkF0060,trkF0053 | 旧结论 trkF0060 → superseded_by trkF0059；gold rank=1 |
| t4-021 | T4 | 数据迁移 | trkG0067 | trkG0061,trkG0067,trkG0068,trkG0060,trkG0016 | 旧结论 trkG0068 → superseded_by trkG0067；gold rank=1 |
| t4-022 | T4 | 权限审批 | trkH0074 | trkH0075,trkH0074,trkH0081,trkH0092,trkH0098 | 旧结论 trkH0075 → superseded_by trkH0074；gold rank=1 |
| t5-001 | T5 | 部署上线 | trkA0064 | trkA0062,trkA0067,trkA0072,trkA0064,trkA0063 | 三跳链 trkA0062→trkA0063→trkA0064，gold=链尾 trkA0064；gold rank=3 |
| t5-002 | T5 | 灰度发布 | trkB0071 | trkB0069,trkB0074,trkB0079,trkB0076,trkB0071 | 三跳链 trkB0069→trkB0070→trkB0071，gold=链尾 trkB0071；gold rank=4 |
| t5-003 | T5 | 接口对接 | trkC0059 | trkC0057,trkC0062,trkC0067,trkC0060,trkC0058 | 三跳链 trkC0057→trkC0058→trkC0059，gold=链尾 trkC0059；gold rank=None |
| t5-004 | T5 | 同事交接 | trkD0059 | trkD0057,trkD0062,trkD0067,trkD0064,trkD0063 | 三跳链 trkD0057→trkD0058→trkD0059，gold=链尾 trkD0059；gold rank=None |
| t5-005 | T5 | 开会定口径 | trkE0064 | trkE0062,trkE0072,trkE0067,trkE0063,trkE0064 | 三跳链 trkE0062→trkE0063→trkE0064，gold=链尾 trkE0064；gold rank=4 |
| t5-006 | T5 | 线上排障 | trkF0063 | trkF0061,trkF0071,trkF0066,trkF0073,trkF0048 | 三跳链 trkF0061→trkF0062→trkF0063，gold=链尾 trkF0063；gold rank=None |
| t5-007 | T5 | 数据迁移 | trkG0072 | trkG0070,trkG0075,trkG0073,trkG0071,trkG0072 | 三跳链 trkG0070→trkG0071→trkG0072，gold=链尾 trkG0072；gold rank=4 |
| t5-008 | T5 | 权限审批 | trkH0078 | trkH0076,trkH0081,trkH0079,trkH0078,trkH0077 | 三跳链 trkH0076→trkH0077→trkH0078，gold=链尾 trkH0078；gold rank=3 |
| t5-009 | T5 | 部署上线 | trkA0069 | trkA0067,trkA0072,trkA0062,trkA0073,trkA0068 | 三跳链 trkA0067→trkA0068→trkA0069，gold=链尾 trkA0069；gold rank=None |
| t5-010 | T5 | 灰度发布 | trkB0076 | trkB0074,trkB0069,trkB0079,trkB0071,trkB0076 | 三跳链 trkB0074→trkB0075→trkB0076，gold=链尾 trkB0076；gold rank=4 |
| t5-011 | T5 | 接口对接 | trkC0064 | trkC0057,trkC0062,trkC0067,trkC0060,trkC0058 | 三跳链 trkC0062→trkC0063→trkC0064，gold=链尾 trkC0064；gold rank=None |
| t5-012 | T5 | 同事交接 | trkD0064 | trkD0062,trkD0057,trkD0067,trkD0063,trkD0059 | 三跳链 trkD0062→trkD0063→trkD0064，gold=链尾 trkD0064；gold rank=None |
| t5-013 | T5 | 开会定口径 | trkE0069 | trkE0067,trkE0062,trkE0072,trkE0069,trkE0068 | 三跳链 trkE0067→trkE0068→trkE0069，gold=链尾 trkE0069；gold rank=3 |
| t5-014 | T5 | 线上排障 | trkF0068 | trkF0066,trkF0061,trkF0071,trkF0069,trkF0068 | 三跳链 trkF0066→trkF0067→trkF0068，gold=链尾 trkF0068；gold rank=4 |
| t5-015 | T5 | 数据迁移 | trkG0077 | trkG0075,trkG0070,trkG0077,trkG0076,trkG0067 | 三跳链 trkG0075→trkG0076→trkG0077，gold=链尾 trkG0077；gold rank=2 |
| t5-016 | T5 | 权限审批 | trkH0083 | trkH0081,trkH0076,trkH0082,trkH0083,trkH0007 | 三跳链 trkH0081→trkH0082→trkH0083，gold=链尾 trkH0083；gold rank=3 |
| t5-017 | T5 | 部署上线 | trkA0074 | trkA0072,trkA0067,trkA0062,trkA0075,trkA0069 | 三跳链 trkA0072→trkA0073→trkA0074，gold=链尾 trkA0074；gold rank=None |
| t5-018 | T5 | 灰度发布 | trkB0081 | trkB0079,trkB0074,trkB0069,trkB0080,trkB0081 | 三跳链 trkB0079→trkB0080→trkB0081，gold=链尾 trkB0081；gold rank=4 |
| t5-019 | T5 | 接口对接 | trkC0069 | trkC0067,trkC0057,trkC0062,trkC0059,trkC0060 | 三跳链 trkC0067→trkC0068→trkC0069，gold=链尾 trkC0069；gold rank=None |
| t5-020 | T5 | 同事交接 | trkD0069 | trkD0067,trkD0057,trkD0062,trkD0068,trkD0069 | 三跳链 trkD0067→trkD0068→trkD0069，gold=链尾 trkD0069；gold rank=4 |
| t5-021 | T5 | 开会定口径 | trkE0074 | trkE0072,trkE0062,trkE0067,trkE0063,trkE0064 | 三跳链 trkE0072→trkE0073→trkE0074，gold=链尾 trkE0074；gold rank=None |
| t5-022 | T5 | 线上排障 | trkF0073 | trkF0071,trkF0061,trkF0066,trkF0048,trkF0063 | 三跳链 trkF0071→trkF0072→trkF0073，gold=链尾 trkF0073；gold rank=None |
| t6-001 | T6 | 数据迁移 | trkG0080 | trkG0081,trkG0082,trkG0014,trkG0005,trkG0018 | claim 组 ['trkG0080', 'trkG0082', 'trkG0081']；实测 rank=None，转述 rank=0；证据优先=False |
| t6-002 | T6 | 权限审批 | trkH0087 | trkH0088,trkH0092,trkH0054,trkH0089,trkH0018 | claim 组 ['trkH0087', 'trkH0089', 'trkH0088']；实测 rank=None，转述 rank=0；证据优先=False |
| t6-003 | T6 | 部署上线 | trkA0077 | trkA0078,trkA0079,trkA0081,trkA0077,trkA0017 | claim 组 ['trkA0077', 'trkA0079', 'trkA0078']；实测 rank=3，转述 rank=0；证据优先=False |
| t6-004 | T6 | 灰度发布 | trkB0088 | trkB0089,trkB0090,trkB0091,trkB0088,trkB0008 | claim 组 ['trkB0088', 'trkB0090', 'trkB0089']；实测 rank=3，转述 rank=0；证据优先=False |
| t6-005 | T6 | 接口对接 | trkC0073 | trkC0074,trkC0072,trkC0075,trkC0073,trkC0079 | claim 组 ['trkC0073', 'trkC0075', 'trkC0074']；实测 rank=3，转述 rank=0；证据优先=False |
| t6-006 | T6 | 同事交接 | trkD0073 | trkD0074,trkD0085,trkD0093,trkD0075,trkD0086 | claim 组 ['trkD0073', 'trkD0075', 'trkD0074']；实测 rank=None，转述 rank=0；证据优先=False |
| t6-007 | T6 | 开会定口径 | trkE0080 | trkE0081,trkE0078,trkE0093,trkE0092,trkE0036 | claim 组 ['trkE0080', 'trkE0082', 'trkE0081']；实测 rank=None，转述 rank=0；证据优先=False |
| t6-008 | T6 | 线上排障 | trkF0079 | trkF0080,trkF0027,trkF0081,trkF0002,trkF0079 | claim 组 ['trkF0079', 'trkF0081', 'trkF0080']；实测 rank=4，转述 rank=0；证据优先=False |
| t6-009 | T6 | 数据迁移 | trkG0083 | trkG0084,trkG0085,trkG0019,trkG0083,trkG0023 | claim 组 ['trkG0083', 'trkG0085', 'trkG0084']；实测 rank=3，转述 rank=0；证据优先=False |
| t6-010 | T6 | 权限审批 | trkH0094 | trkH0095,trkH0093,trkH0099,trkH0103,trkH0097 | claim 组 ['trkH0094', 'trkH0096', 'trkH0095']；实测 rank=None，转述 rank=0；证据优先=False |
| t6-011 | T6 | 部署上线 | trkA0082 | trkA0083,trkA0088,trkA0085,trkA0086,trkA0084 | claim 组 ['trkA0082', 'trkA0084', 'trkA0083']；实测 rank=None，转述 rank=0；证据优先=False |
| t6-012 | T6 | 灰度发布 | trkB0093 | trkB0094,trkB0095,trkB0097,trkB0049,trkB0057 | claim 组 ['trkB0093', 'trkB0095', 'trkB0094']；实测 rank=None，转述 rank=0；证据优先=False |
| t6-013 | T6 | 接口对接 | trkC0080 | trkC0081,trkC0082,trkC0080,trkC0083,trkC0016 | claim 组 ['trkC0080', 'trkC0082', 'trkC0081']；实测 rank=2，转述 rank=0；证据优先=False |
| t6-014 | T6 | 同事交接 | trkD0084 | trkD0074,trkD0085,trkD0093,trkD0075,trkD0086 | claim 组 ['trkD0084', 'trkD0086', 'trkD0085']；实测 rank=None，转述 rank=1；证据优先=False |
| t6-015 | T6 | 开会定口径 | trkE0087 | trkE0088,trkE0089,trkE0003,trkE0002,trkE0087 | claim 组 ['trkE0087', 'trkE0089', 'trkE0088']；实测 rank=4，转述 rank=0；证据优先=False |
| t6-016 | T6 | 线上排障 | trkF0084 | trkF0085,trkF0086,trkF0084,trkF0087,trkF0088 | claim 组 ['trkF0084', 'trkF0086', 'trkF0085']；实测 rank=2，转述 rank=0；证据优先=False |
| t6-017 | T6 | 数据迁移 | trkG0086 | trkG0087,trkG0088,trkG0041,trkG0002,trkG0011 | claim 组 ['trkG0086', 'trkG0088', 'trkG0087']；实测 rank=None，转述 rank=0；证据优先=False |
| t6-018 | T6 | 权限审批 | trkH0100 | trkH0101,trkH0086,trkH0102,trkH0100,trkH0090 | claim 组 ['trkH0100', 'trkH0102', 'trkH0101']；实测 rank=3，转述 rank=0；证据优先=False |
| t6-019 | T6 | 部署上线 | trkA0087 | trkA0083,trkA0088,trkA0085,trkA0086,trkA0084 | claim 组 ['trkA0087', 'trkA0089', 'trkA0088']；实测 rank=None，转述 rank=1；证据优先=False |
| t6-020 | T6 | 灰度发布 | trkB0098 | trkB0099,trkB0096,trkB0092,trkB0050,trkB0100 | claim 组 ['trkB0098', 'trkB0100', 'trkB0099']；实测 rank=None，转述 rank=0；证据优先=False |
| t6-021 | T6 | 接口对接 | trkC0084 | trkC0085,trkC0086,trkC0084,trkC0012,trkC0008 | claim 组 ['trkC0084', 'trkC0086', 'trkC0085']；实测 rank=2，转述 rank=0；证据优先=False |
| t6-022 | T6 | 同事交接 | trkD0092 | trkD0074,trkD0085,trkD0093,trkD0075,trkD0086 | claim 组 ['trkD0092', 'trkD0094', 'trkD0093']；实测 rank=None，转述 rank=2；证据优先=False |
（共 132 题，全部列出）


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
| T1 抗干扰 | 0.000 | 0.000 [0.000, 0.149] | hit_at_k | 0.000 | 0.000 [0.000, 0.149] |
| T2 同名异事 | 0.000 | 0.000 [0.000, 0.149] | hit_at_1 | 0.000 | 0.000 [0.000, 0.149] |
| T3 隐含约束 | 0.000 | 0.000 [0.000, 0.149] | hit_at_1 | 0.000 | 0.000 [0.000, 0.149] |
| T4 旧结论失效 | 0.000 | 0.000 [0.000, 0.149] | hit_at_1 | 0.000 | 0.000 [0.000, 0.149] |
| T5 跨时间一致性 | 0.000 | 0.000 [0.000, 0.149] | hit_at_1 | 0.000 | 0.000 [0.000, 0.149] |
| T6 转述vs实测 | 0.000 | 0.000 [0.000, 0.149] | evidence_first_acc | 0.000 | 0.000 [0.000, 0.149] |

**类人度总分 = 0.000**（95% CI [0.000, 0.000]，stratified-bootstrap，reps=2000，seed=20261109）

总分口径：`Σ w_i·s_i`。T1 抗干扰 0.15 / T2 同名异事 0.20 / T3 隐含约束 0.20 / T4 失效感知 0.15 / T5 跨时间一致 0.15 / T6 证据分级 0.15。同名异事与隐含约束最依赖常识与场景绑定，权重最高。

## 三、基线对照

| 指标 | 本臂 | perfect | adversarial |
|---|---:|---:|---:|
| T1 抗干扰 主指标 | 0.000 | 1.000 | 0.000 |
| T2 同名异事 主指标 | 0.000 | 1.000 | 0.000 |
| T3 隐含约束 主指标 | 0.000 | 1.000 | 0.000 |
| T4 旧结论失效 主指标 | 0.000 | 1.000 | 0.000 |
| T5 跨时间一致性 主指标 | 0.000 | 1.000 | 0.000 |
| T6 转述vs实测 主指标 | 0.000 | 1.000 | 0.000 |
| **类人度总分** | 0.000 | 1.000 | 0.000 |

## 四、单题下钻（qid → 场景 → gold → top-k → 判分理由）

| qid | 类型 | 场景 | gold | top-k | 判分理由 |
|---|---|---|---|---|---|
| t1-001 | T1 | 部署上线 | trkA0001 | e0000001,e0000002,e0000003,e0000004,e0000005 | 真约束 trkA0001；top-5 中同主题干扰记录 0/5；gold rank=None |
| t1-002 | T1 | 灰度发布 | trkB0001 | e0000006,e0000007,e0000008,e0000009,e0000010 | 真约束 trkB0001；top-5 中同主题干扰记录 0/5；gold rank=None |
| t1-003 | T1 | 接口对接 | trkC0003 | e0000011,e0000012,e0000013,e0000014,e0000015 | 真约束 trkC0003；top-5 中同主题干扰记录 0/5；gold rank=None |
| t1-004 | T1 | 同事交接 | trkD0001 | e0000016,e0000017,e0000018,e0000019,e0000020 | 真约束 trkD0001；top-5 中同主题干扰记录 0/5；gold rank=None |
| t1-005 | T1 | 开会定口径 | trkE0006 | e0000021,e0000022,e0000023,e0000024,e0000025 | 真约束 trkE0006；top-5 中同主题干扰记录 0/5；gold rank=None |
| t1-006 | T1 | 线上排障 | trkF0003 | e0000026,e0000027,e0000028,e0000029,e0000030 | 真约束 trkF0003；top-5 中同主题干扰记录 0/5；gold rank=None |
| t1-007 | T1 | 数据迁移 | trkG0008 | e0000031,e0000032,e0000033,e0000034,e0000035 | 真约束 trkG0008；top-5 中同主题干扰记录 0/5；gold rank=None |
| t1-008 | T1 | 权限审批 | trkH0006 | e0000036,e0000037,e0000038,e0000039,e0000040 | 真约束 trkH0006；top-5 中同主题干扰记录 0/5；gold rank=None |
| t1-009 | T1 | 部署上线 | trkA0009 | e0000041,e0000042,e0000043,e0000044,e0000045 | 真约束 trkA0009；top-5 中同主题干扰记录 0/5；gold rank=None |
| t1-010 | T1 | 灰度发布 | trkB0009 | e0000046,e0000047,e0000048,e0000049,e0000050 | 真约束 trkB0009；top-5 中同主题干扰记录 0/5；gold rank=None |
| t1-011 | T1 | 接口对接 | trkC0006 | e0000051,e0000052,e0000053,e0000054,e0000055 | 真约束 trkC0006；top-5 中同主题干扰记录 0/5；gold rank=None |
| t1-012 | T1 | 同事交接 | trkD0007 | e0000056,e0000057,e0000058,e0000059,e0000060 | 真约束 trkD0007；top-5 中同主题干扰记录 0/5；gold rank=None |
| t1-013 | T1 | 开会定口径 | trkE0011 | e0000061,e0000062,e0000063,e0000064,e0000065 | 真约束 trkE0011；top-5 中同主题干扰记录 0/5；gold rank=None |
| t1-014 | T1 | 线上排障 | trkF0010 | e0000066,e0000067,e0000068,e0000069,e0000070 | 真约束 trkF0010；top-5 中同主题干扰记录 0/5；gold rank=None |
| t1-015 | T1 | 数据迁移 | trkG0015 | e0000071,e0000072,e0000073,e0000074,e0000075 | 真约束 trkG0015；top-5 中同主题干扰记录 0/5；gold rank=None |
| t1-016 | T1 | 权限审批 | trkH0012 | e0000076,e0000077,e0000078,e0000079,e0000080 | 真约束 trkH0012；top-5 中同主题干扰记录 0/5；gold rank=None |
| t1-017 | T1 | 部署上线 | trkA0015 | e0000081,e0000082,e0000083,e0000084,e0000085 | 真约束 trkA0015；top-5 中同主题干扰记录 0/5；gold rank=None |
| t1-018 | T1 | 灰度发布 | trkB0014 | e0000086,e0000087,e0000088,e0000089,e0000090 | 真约束 trkB0014；top-5 中同主题干扰记录 0/5；gold rank=None |
| t1-019 | T1 | 接口对接 | trkC0010 | e0000091,e0000092,e0000093,e0000094,e0000095 | 真约束 trkC0010；top-5 中同主题干扰记录 0/5；gold rank=None |
| t1-020 | T1 | 同事交接 | trkD0013 | e0000096,e0000097,e0000098,e0000099,e0000100 | 真约束 trkD0013；top-5 中同主题干扰记录 0/5；gold rank=None |
| t1-021 | T1 | 开会定口径 | trkE0015 | e0000101,e0000102,e0000103,e0000104,e0000105 | 真约束 trkE0015；top-5 中同主题干扰记录 0/5；gold rank=None |
| t1-022 | T1 | 线上排障 | trkF0013 | e0000106,e0000107,e0000108,e0000109,e0000110 | 真约束 trkF0013；top-5 中同主题干扰记录 0/5；gold rank=None |
| t2-001 | T2 | 数据迁移 | trkG0021 | e0000111,e0000112,e0000113,e0000114,e0000115 | 重名物「那个接口」在 migration 的定义 trkG0021；gold rank=None |
| t2-002 | T2 | 权限审批 | trkH0023 | e0000116,e0000117,e0000118,e0000119,e0000120 | 重名物「临时开关」在 approval 的定义 trkH0023；gold rank=None |
| t2-003 | T2 | 部署上线 | trkA0021 | e0000121,e0000122,e0000123,e0000124,e0000125 | 重名物「第二套口径」在 deploy 的定义 trkA0021；gold rank=None |
| t2-004 | T2 | 灰度发布 | trkB0022 | e0000126,e0000127,e0000128,e0000129,e0000130 | 重名物「灰度第一批」在 canary 的定义 trkB0022；gold rank=None |
| t2-005 | T2 | 接口对接 | trkC0015 | e0000131,e0000132,e0000133,e0000134,e0000135 | 重名物「回滚脚本」在 api 的定义 trkC0015；gold rank=None |
| t2-006 | T2 | 同事交接 | trkD0018 | e0000136,e0000137,e0000138,e0000139,e0000140 | 重名物「V2 方案（第二批）」在 handoff 的定义 trkD0018；gold rank=None |
| t2-007 | T2 | 开会定口径 | trkE0019 | e0000141,e0000142,e0000143,e0000144,e0000145 | 重名物「那个接口（第二批）」在 meeting 的定义 trkE0019；gold rank=None |
| t2-008 | T2 | 线上排障 | trkF0018 | e0000146,e0000147,e0000148,e0000149,e0000150 | 重名物「临时开关（第二批）」在 ops 的定义 trkF0018；gold rank=None |
| t2-009 | T2 | 数据迁移 | trkG0029 | e0000151,e0000152,e0000153,e0000154,e0000155 | 重名物「第二套口径（第二批）」在 migration 的定义 trkG0029；gold rank=None |
| t2-010 | T2 | 权限审批 | trkH0031 | e0000156,e0000157,e0000158,e0000159,e0000160 | 重名物「灰度第一批（第二批）」在 approval 的定义 trkH0031；gold rank=None |
| t2-011 | T2 | 部署上线 | trkA0029 | e0000161,e0000162,e0000163,e0000164,e0000165 | 重名物「回滚脚本（第二批）」在 deploy 的定义 trkA0029；gold rank=None |
| t2-012 | T2 | 灰度发布 | trkB0027 | e0000166,e0000167,e0000168,e0000169,e0000170 | 重名物「V2 方案（第三批）」在 canary 的定义 trkB0027；gold rank=None |
| t2-013 | T2 | 接口对接 | trkC0019 | e0000171,e0000172,e0000173,e0000174,e0000175 | 重名物「那个接口（第三批）」在 api 的定义 trkC0019；gold rank=None |
| t2-014 | T2 | 同事交接 | trkD0022 | e0000176,e0000177,e0000178,e0000179,e0000180 | 重名物「临时开关（第三批）」在 handoff 的定义 trkD0022；gold rank=None |
| t2-015 | T2 | 开会定口径 | trkE0024 | e0000181,e0000182,e0000183,e0000184,e0000185 | 重名物「第二套口径（第三批）」在 meeting 的定义 trkE0024；gold rank=None |
| t2-016 | T2 | 线上排障 | trkF0024 | e0000186,e0000187,e0000188,e0000189,e0000190 | 重名物「灰度第一批（第三批）」在 ops 的定义 trkF0024；gold rank=None |
| t2-017 | T2 | 数据迁移 | trkG0036 | e0000191,e0000192,e0000193,e0000194,e0000195 | 重名物「回滚脚本（第三批）」在 migration 的定义 trkG0036；gold rank=None |
| t2-018 | T2 | 权限审批 | trkH0040 | e0000196,e0000197,e0000198,e0000199,e0000200 | 重名物「V2 方案（第四批）」在 approval 的定义 trkH0040；gold rank=None |
| t2-019 | T2 | 部署上线 | trkA0034 | e0000201,e0000202,e0000203,e0000204,e0000205 | 重名物「那个接口（第四批）」在 deploy 的定义 trkA0034；gold rank=None |
| t2-020 | T2 | 灰度发布 | trkB0034 | e0000206,e0000207,e0000208,e0000209,e0000210 | 重名物「临时开关（第四批）」在 canary 的定义 trkB0034；gold rank=None |
| t2-021 | T2 | 接口对接 | trkC0026 | e0000211,e0000212,e0000213,e0000214,e0000215 | 重名物「第二套口径（第四批）」在 api 的定义 trkC0026；gold rank=None |
| t2-022 | T2 | 同事交接 | trkD0030 | e0000216,e0000217,e0000218,e0000219,e0000220 | 重名物「灰度第一批（第四批）」在 handoff 的定义 trkD0030；gold rank=None |
| t3-001 | T3 | 开会定口径 | trkE0030 | e0000221,e0000222,e0000223,e0000224,e0000225 | 隐含规矩（implicit=true）trkE0030；gold rank=None |
| t3-002 | T3 | 线上排障 | trkF0028 | e0000226,e0000227,e0000228,e0000229,e0000230 | 隐含规矩（implicit=true）trkF0028；gold rank=None |
| t3-003 | T3 | 数据迁移 | trkG0042 | e0000231,e0000232,e0000233,e0000234,e0000235 | 隐含规矩（implicit=true）trkG0042；gold rank=None |
| t3-004 | T3 | 权限审批 | trkH0044 | e0000236,e0000237,e0000238,e0000239,e0000240 | 隐含规矩（implicit=true）trkH0044；gold rank=None |
| t3-005 | T3 | 部署上线 | trkA0039 | e0000241,e0000242,e0000243,e0000244,e0000245 | 隐含规矩（implicit=true）trkA0039；gold rank=None |
| t3-006 | T3 | 灰度发布 | trkB0037 | e0000246,e0000247,e0000248,e0000249,e0000250 | 隐含规矩（implicit=true）trkB0037；gold rank=None |
| t3-007 | T3 | 接口对接 | trkC0027 | e0000251,e0000252,e0000253,e0000254,e0000255 | 隐含规矩（implicit=true）trkC0027；gold rank=None |
| t3-008 | T3 | 同事交接 | trkD0031 | e0000256,e0000257,e0000258,e0000259,e0000260 | 隐含规矩（implicit=true）trkD0031；gold rank=None |
| t3-009 | T3 | 开会定口径 | trkE0037 | e0000261,e0000262,e0000263,e0000264,e0000265 | 隐含规矩（implicit=true）trkE0037；gold rank=None |
| t3-010 | T3 | 线上排障 | trkF0032 | e0000266,e0000267,e0000268,e0000269,e0000270 | 隐含规矩（implicit=true）trkF0032；gold rank=None |
| t3-011 | T3 | 数据迁移 | trkG0051 | e0000271,e0000272,e0000273,e0000274,e0000275 | 隐含规矩（implicit=true）trkG0051；gold rank=None |
| t3-012 | T3 | 权限审批 | trkH0049 | e0000276,e0000277,e0000278,e0000279,e0000280 | 隐含规矩（implicit=true）trkH0049；gold rank=None |
| t3-013 | T3 | 部署上线 | trkA0044 | e0000281,e0000282,e0000283,e0000284,e0000285 | 隐含规矩（implicit=true）trkA0044；gold rank=None |
| t3-014 | T3 | 灰度发布 | trkB0044 | e0000286,e0000287,e0000288,e0000289,e0000290 | 隐含规矩（implicit=true）trkB0044；gold rank=None |
| t3-015 | T3 | 接口对接 | trkC0031 | e0000291,e0000292,e0000293,e0000294,e0000295 | 隐含规矩（implicit=true）trkC0031；gold rank=None |
| t3-016 | T3 | 同事交接 | trkD0037 | e0000296,e0000297,e0000298,e0000299,e0000300 | 隐含规矩（implicit=true）trkD0037；gold rank=None |
| t3-017 | T3 | 开会定口径 | trkE0045 | e0000301,e0000302,e0000303,e0000304,e0000305 | 隐含规矩（implicit=true）trkE0045；gold rank=None |
| t3-018 | T3 | 线上排障 | trkF0039 | e0000306,e0000307,e0000308,e0000309,e0000310 | 隐含规矩（implicit=true）trkF0039；gold rank=None |
| t3-019 | T3 | 数据迁移 | trkG0056 | e0000311,e0000312,e0000313,e0000314,e0000315 | 隐含规矩（implicit=true）trkG0056；gold rank=None |
| t3-020 | T3 | 权限审批 | trkH0056 | e0000316,e0000317,e0000318,e0000319,e0000320 | 隐含规矩（implicit=true）trkH0056；gold rank=None |
| t3-021 | T3 | 部署上线 | trkA0048 | e0000321,e0000322,e0000323,e0000324,e0000325 | 隐含规矩（implicit=true）trkA0048；gold rank=None |
| t3-022 | T3 | 灰度发布 | trkB0051 | e0000326,e0000327,e0000328,e0000329,e0000330 | 隐含规矩（implicit=true）trkB0051；gold rank=None |
| t4-001 | T4 | 接口对接 | trkC0041 | e0000331,e0000332,e0000333,e0000334,e0000335 | 旧结论 trkC0042 → superseded_by trkC0041；gold rank=None |
| t4-002 | T4 | 同事交接 | trkD0042 | e0000336,e0000337,e0000338,e0000339,e0000340 | 旧结论 trkD0043 → superseded_by trkD0042；gold rank=None |
| t4-003 | T4 | 开会定口径 | trkE0051 | e0000341,e0000342,e0000343,e0000344,e0000345 | 旧结论 trkE0052 → superseded_by trkE0051；gold rank=None |
| t4-004 | T4 | 线上排障 | trkF0045 | e0000346,e0000347,e0000348,e0000349,e0000350 | 旧结论 trkF0046 → superseded_by trkF0045；gold rank=None |
| t4-005 | T4 | 数据迁移 | trkG0060 | e0000351,e0000352,e0000353,e0000354,e0000355 | 旧结论 trkG0061 → superseded_by trkG0060；gold rank=None |
| t4-006 | T4 | 权限审批 | trkH0062 | e0000356,e0000357,e0000358,e0000359,e0000360 | 旧结论 trkH0063 → superseded_by trkH0062；gold rank=None |
| t4-007 | T4 | 部署上线 | trkA0054 | e0000361,e0000362,e0000363,e0000364,e0000365 | 旧结论 trkA0055 → superseded_by trkA0054；gold rank=None |
| t4-008 | T4 | 灰度发布 | trkB0059 | e0000366,e0000367,e0000368,e0000369,e0000370 | 旧结论 trkB0060 → superseded_by trkB0059；gold rank=None |
| t4-009 | T4 | 接口对接 | trkC0045 | e0000371,e0000372,e0000373,e0000374,e0000375 | 旧结论 trkC0046 → superseded_by trkC0045；gold rank=None |
| t4-010 | T4 | 同事交接 | trkD0050 | e0000376,e0000377,e0000378,e0000379,e0000380 | 旧结论 trkD0051 → superseded_by trkD0050；gold rank=None |
| t4-011 | T4 | 开会定口径 | trkE0056 | e0000381,e0000382,e0000383,e0000384,e0000385 | 旧结论 trkE0057 → superseded_by trkE0056；gold rank=None |
| t4-012 | T4 | 线上排障 | trkF0053 | e0000386,e0000387,e0000388,e0000389,e0000390 | 旧结论 trkF0054 → superseded_by trkF0053；gold rank=None |
| t4-013 | T4 | 数据迁移 | trkG0062 | e0000391,e0000392,e0000393,e0000394,e0000395 | 旧结论 trkG0063 → superseded_by trkG0062；gold rank=None |
| t4-014 | T4 | 权限审批 | trkH0068 | e0000396,e0000397,e0000398,e0000399,e0000400 | 旧结论 trkH0069 → superseded_by trkH0068；gold rank=None |
| t4-015 | T4 | 部署上线 | trkA0058 | e0000401,e0000402,e0000403,e0000404,e0000405 | 旧结论 trkA0059 → superseded_by trkA0058；gold rank=None |
| t4-016 | T4 | 灰度发布 | trkB0063 | e0000406,e0000407,e0000408,e0000409,e0000410 | 旧结论 trkB0064 → superseded_by trkB0063；gold rank=None |
| t4-017 | T4 | 接口对接 | trkC0052 | e0000411,e0000412,e0000413,e0000414,e0000415 | 旧结论 trkC0053 → superseded_by trkC0052；gold rank=None |
| t4-018 | T4 | 同事交接 | trkD0053 | e0000416,e0000417,e0000418,e0000419,e0000420 | 旧结论 trkD0054 → superseded_by trkD0053；gold rank=None |
| t4-019 | T4 | 开会定口径 | trkE0059 | e0000421,e0000422,e0000423,e0000424,e0000425 | 旧结论 trkE0060 → superseded_by trkE0059；gold rank=None |
| t4-020 | T4 | 线上排障 | trkF0059 | e0000426,e0000427,e0000428,e0000429,e0000430 | 旧结论 trkF0060 → superseded_by trkF0059；gold rank=None |
| t4-021 | T4 | 数据迁移 | trkG0067 | e0000431,e0000432,e0000433,e0000434,e0000435 | 旧结论 trkG0068 → superseded_by trkG0067；gold rank=None |
| t4-022 | T4 | 权限审批 | trkH0074 | e0000436,e0000437,e0000438,e0000439,e0000440 | 旧结论 trkH0075 → superseded_by trkH0074；gold rank=None |
| t5-001 | T5 | 部署上线 | trkA0064 | e0000441,e0000442,e0000443,e0000444,e0000445 | 三跳链 trkA0062→trkA0063→trkA0064，gold=链尾 trkA0064；gold rank=None |
| t5-002 | T5 | 灰度发布 | trkB0071 | e0000446,e0000447,e0000448,e0000449,e0000450 | 三跳链 trkB0069→trkB0070→trkB0071，gold=链尾 trkB0071；gold rank=None |
| t5-003 | T5 | 接口对接 | trkC0059 | e0000451,e0000452,e0000453,e0000454,e0000455 | 三跳链 trkC0057→trkC0058→trkC0059，gold=链尾 trkC0059；gold rank=None |
| t5-004 | T5 | 同事交接 | trkD0059 | e0000456,e0000457,e0000458,e0000459,e0000460 | 三跳链 trkD0057→trkD0058→trkD0059，gold=链尾 trkD0059；gold rank=None |
| t5-005 | T5 | 开会定口径 | trkE0064 | e0000461,e0000462,e0000463,e0000464,e0000465 | 三跳链 trkE0062→trkE0063→trkE0064，gold=链尾 trkE0064；gold rank=None |
| t5-006 | T5 | 线上排障 | trkF0063 | e0000466,e0000467,e0000468,e0000469,e0000470 | 三跳链 trkF0061→trkF0062→trkF0063，gold=链尾 trkF0063；gold rank=None |
| t5-007 | T5 | 数据迁移 | trkG0072 | e0000471,e0000472,e0000473,e0000474,e0000475 | 三跳链 trkG0070→trkG0071→trkG0072，gold=链尾 trkG0072；gold rank=None |
| t5-008 | T5 | 权限审批 | trkH0078 | e0000476,e0000477,e0000478,e0000479,e0000480 | 三跳链 trkH0076→trkH0077→trkH0078，gold=链尾 trkH0078；gold rank=None |
| t5-009 | T5 | 部署上线 | trkA0069 | e0000481,e0000482,e0000483,e0000484,e0000485 | 三跳链 trkA0067→trkA0068→trkA0069，gold=链尾 trkA0069；gold rank=None |
| t5-010 | T5 | 灰度发布 | trkB0076 | e0000486,e0000487,e0000488,e0000489,e0000490 | 三跳链 trkB0074→trkB0075→trkB0076，gold=链尾 trkB0076；gold rank=None |
| t5-011 | T5 | 接口对接 | trkC0064 | e0000491,e0000492,e0000493,e0000494,e0000495 | 三跳链 trkC0062→trkC0063→trkC0064，gold=链尾 trkC0064；gold rank=None |
| t5-012 | T5 | 同事交接 | trkD0064 | e0000496,e0000497,e0000498,e0000499,e0000500 | 三跳链 trkD0062→trkD0063→trkD0064，gold=链尾 trkD0064；gold rank=None |
| t5-013 | T5 | 开会定口径 | trkE0069 | e0000501,e0000502,e0000503,e0000504,e0000505 | 三跳链 trkE0067→trkE0068→trkE0069，gold=链尾 trkE0069；gold rank=None |
| t5-014 | T5 | 线上排障 | trkF0068 | e0000506,e0000507,e0000508,e0000509,e0000510 | 三跳链 trkF0066→trkF0067→trkF0068，gold=链尾 trkF0068；gold rank=None |
| t5-015 | T5 | 数据迁移 | trkG0077 | e0000511,e0000512,e0000513,e0000514,e0000515 | 三跳链 trkG0075→trkG0076→trkG0077，gold=链尾 trkG0077；gold rank=None |
| t5-016 | T5 | 权限审批 | trkH0083 | e0000516,e0000517,e0000518,e0000519,e0000520 | 三跳链 trkH0081→trkH0082→trkH0083，gold=链尾 trkH0083；gold rank=None |
| t5-017 | T5 | 部署上线 | trkA0074 | e0000521,e0000522,e0000523,e0000524,e0000525 | 三跳链 trkA0072→trkA0073→trkA0074，gold=链尾 trkA0074；gold rank=None |
| t5-018 | T5 | 灰度发布 | trkB0081 | e0000526,e0000527,e0000528,e0000529,e0000530 | 三跳链 trkB0079→trkB0080→trkB0081，gold=链尾 trkB0081；gold rank=None |
| t5-019 | T5 | 接口对接 | trkC0069 | e0000531,e0000532,e0000533,e0000534,e0000535 | 三跳链 trkC0067→trkC0068→trkC0069，gold=链尾 trkC0069；gold rank=None |
| t5-020 | T5 | 同事交接 | trkD0069 | e0000536,e0000537,e0000538,e0000539,e0000540 | 三跳链 trkD0067→trkD0068→trkD0069，gold=链尾 trkD0069；gold rank=None |
| t5-021 | T5 | 开会定口径 | trkE0074 | e0000541,e0000542,e0000543,e0000544,e0000545 | 三跳链 trkE0072→trkE0073→trkE0074，gold=链尾 trkE0074；gold rank=None |
| t5-022 | T5 | 线上排障 | trkF0073 | e0000546,e0000547,e0000548,e0000549,e0000550 | 三跳链 trkF0071→trkF0072→trkF0073，gold=链尾 trkF0073；gold rank=None |
| t6-001 | T6 | 数据迁移 | trkG0080 | e0000551,e0000552,e0000553,e0000554,e0000555 | claim 组 ['trkG0080', 'trkG0082', 'trkG0081']；实测 rank=None，转述 rank=None；证据优先=False |
| t6-002 | T6 | 权限审批 | trkH0087 | e0000556,e0000557,e0000558,e0000559,e0000560 | claim 组 ['trkH0087', 'trkH0089', 'trkH0088']；实测 rank=None，转述 rank=None；证据优先=False |
| t6-003 | T6 | 部署上线 | trkA0077 | e0000561,e0000562,e0000563,e0000564,e0000565 | claim 组 ['trkA0077', 'trkA0079', 'trkA0078']；实测 rank=None，转述 rank=None；证据优先=False |
| t6-004 | T6 | 灰度发布 | trkB0088 | e0000566,e0000567,e0000568,e0000569,e0000570 | claim 组 ['trkB0088', 'trkB0090', 'trkB0089']；实测 rank=None，转述 rank=None；证据优先=False |
| t6-005 | T6 | 接口对接 | trkC0073 | e0000571,e0000572,e0000573,e0000574,e0000575 | claim 组 ['trkC0073', 'trkC0075', 'trkC0074']；实测 rank=None，转述 rank=None；证据优先=False |
| t6-006 | T6 | 同事交接 | trkD0073 | e0000576,e0000577,e0000578,e0000579,e0000580 | claim 组 ['trkD0073', 'trkD0075', 'trkD0074']；实测 rank=None，转述 rank=None；证据优先=False |
| t6-007 | T6 | 开会定口径 | trkE0080 | e0000581,e0000582,e0000583,e0000584,e0000585 | claim 组 ['trkE0080', 'trkE0082', 'trkE0081']；实测 rank=None，转述 rank=None；证据优先=False |
| t6-008 | T6 | 线上排障 | trkF0079 | e0000586,e0000587,e0000588,e0000589,e0000590 | claim 组 ['trkF0079', 'trkF0081', 'trkF0080']；实测 rank=None，转述 rank=None；证据优先=False |
| t6-009 | T6 | 数据迁移 | trkG0083 | e0000591,e0000592,e0000593,e0000594,e0000595 | claim 组 ['trkG0083', 'trkG0085', 'trkG0084']；实测 rank=None，转述 rank=None；证据优先=False |
| t6-010 | T6 | 权限审批 | trkH0094 | e0000596,e0000597,e0000598,e0000599,e0000600 | claim 组 ['trkH0094', 'trkH0096', 'trkH0095']；实测 rank=None，转述 rank=None；证据优先=False |
| t6-011 | T6 | 部署上线 | trkA0082 | e0000601,e0000602,e0000603,e0000604,e0000605 | claim 组 ['trkA0082', 'trkA0084', 'trkA0083']；实测 rank=None，转述 rank=None；证据优先=False |
| t6-012 | T6 | 灰度发布 | trkB0093 | e0000606,e0000607,e0000608,e0000609,e0000610 | claim 组 ['trkB0093', 'trkB0095', 'trkB0094']；实测 rank=None，转述 rank=None；证据优先=False |
| t6-013 | T6 | 接口对接 | trkC0080 | e0000611,e0000612,e0000613,e0000614,e0000615 | claim 组 ['trkC0080', 'trkC0082', 'trkC0081']；实测 rank=None，转述 rank=None；证据优先=False |
| t6-014 | T6 | 同事交接 | trkD0084 | e0000616,e0000617,e0000618,e0000619,e0000620 | claim 组 ['trkD0084', 'trkD0086', 'trkD0085']；实测 rank=None，转述 rank=None；证据优先=False |
| t6-015 | T6 | 开会定口径 | trkE0087 | e0000621,e0000622,e0000623,e0000624,e0000625 | claim 组 ['trkE0087', 'trkE0089', 'trkE0088']；实测 rank=None，转述 rank=None；证据优先=False |
| t6-016 | T6 | 线上排障 | trkF0084 | e0000626,e0000627,e0000628,e0000629,e0000630 | claim 组 ['trkF0084', 'trkF0086', 'trkF0085']；实测 rank=None，转述 rank=None；证据优先=False |
| t6-017 | T6 | 数据迁移 | trkG0086 | e0000631,e0000632,e0000633,e0000634,e0000635 | claim 组 ['trkG0086', 'trkG0088', 'trkG0087']；实测 rank=None，转述 rank=None；证据优先=False |
| t6-018 | T6 | 权限审批 | trkH0100 | e0000636,e0000637,e0000638,e0000639,e0000640 | claim 组 ['trkH0100', 'trkH0102', 'trkH0101']；实测 rank=None，转述 rank=None；证据优先=False |
| t6-019 | T6 | 部署上线 | trkA0087 | e0000641,e0000642,e0000643,e0000644,e0000645 | claim 组 ['trkA0087', 'trkA0089', 'trkA0088']；实测 rank=None，转述 rank=None；证据优先=False |
| t6-020 | T6 | 灰度发布 | trkB0098 | e0000646,e0000647,e0000648,e0000649,e0000650 | claim 组 ['trkB0098', 'trkB0100', 'trkB0099']；实测 rank=None，转述 rank=None；证据优先=False |
| t6-021 | T6 | 接口对接 | trkC0084 | e0000651,e0000652,e0000653,e0000654,e0000655 | claim 组 ['trkC0084', 'trkC0086', 'trkC0085']；实测 rank=None，转述 rank=None；证据优先=False |
| t6-022 | T6 | 同事交接 | trkD0092 | e0000656,e0000657,e0000658,e0000659,e0000660 | claim 组 ['trkD0092', 'trkD0094', 'trkD0093']；实测 rank=None，转述 rank=None；证据优先=False |
（共 132 题，全部列出）


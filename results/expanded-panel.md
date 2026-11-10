# agimem 指标面板

> **醒目声明：若被测库未导入合成因果树，下表全部数字是「题库不在被测库」的检索结果，**不是因果能力分**，不得包装成系统能力。**

- 判分参数：topk=5，min_score=0.0
- 判分题量：122/122
- 单题权重：1/122 ≈ 0.82pp（26 题时 1 条≈3.8pp，扩集后 1 条≤0.83pp 才够看趋势）

## 一、题量与题型分布

| 题型 | 题数 | 占比 |
|---|---:|---:|
| chain_ancestor | 34 | 27.9% |
| chain_descendant | 34 | 27.9% |
| intervention | 20 | 16.4% |
| supersession | 10 | 8.2% |
| negative | 24 | 19.7% |
| **合计** | **122** | 100% |

## 二、指标点估计与 95% 置信区间

比例类指标用 Wilson score 区间；链覆盖率用正态近似均值区间。

| 指标 | 点估计 | 95% CI | n(分母) | 方向 |
|---|---:|---|---:|---|
| `chain_hit@5` | 0.0000 | 0.000 [0.000, 0.053] | 68 | 越高越好 |
| `chain_hit@1` | 0.0000 | 0.000 [0.000, 0.053] | 68 | 越高越好 |
| `chain_cov` | 0.0000 | 0.000 [0.000, 0.000] | 68 | 越高越好 |
| `intervention_acc` | 0.5000 | 0.500 [0.299, 0.701] | 20 | 越高越好 |
| `false_alarm_rate` | 0.0000 | 0.000 [0.000, 0.278] | 10 | 越低越好 |
| `supersession_acc` | 0.0000 | 0.000 [0.000, 0.278] | 10 | 越高越好 |
| `negative_noise_rate` | 1.0000 | 1.000 [0.862, 1.000] | 24 | 越低越好 |

干预混淆矩阵 TP/FP/FN/TN = 0/0/10/10（WARNING n=10，SAFE n=10）；取代 current/stale/missing = 0/0/10。

## 三、基线对照（合成 recall 臂，非真库）

| 指标 | 本臂 | perfect | adversarial |
|---|---:|---:|---:|
| `chain_hit@k` | 0.000 | 1.000 | 0.000 |
| `chain_cov` | 0.000 | 1.000 | 0.000 |
| `intervention_acc` | 0.500 | 1.000 | 0.000 |
| `false_alarm_rate` | 0.000 | 0.000 | 1.000 |
| `supersession_acc` | 0.000 | 1.000 | 0.000 |
| `negative_noise_rate` | 1.000 | 0.000 | 1.000 |

perfect/adversarial 由 `selftest.py` 生成的合成 fixture 判出，只证明判分器两极正确，不代表任何真实系统水平。

## 四、单题明细下钻（qid → gold → top-k → 判分理由）

| qid | 题型 | gold | top-k 召回 | 判分理由 |
|---|---|---|---|---|
| q001 | chain_ancestor | sntJ0003,sntJ0002,sntJ0001 | e0000001,e0000002,e0000003,e0000004,e0000005 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q002 | chain_ancestor | sntE0005,sntE0004,sntE0003,sntE0002,sntE0001 | e0000006,e0000007,e0000008,e0000009,e0000010 | gold 链长 5; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q003 | chain_ancestor | sntF0004,sntF0003,sntF0002,sntF0001 | e0000011,e0000012,e0000013,e0000014,e0000015 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q004 | chain_ancestor | sntC0005,sntC0004,sntC0003,sntC0002,sntC0001 | e0000016,e0000017,e0000018,e0000019,e0000020 | gold 链长 5; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q005 | chain_ancestor | sntC0004,sntC0003,sntC0002,sntC0001 | e0000021,e0000022,e0000023,e0000024,e0000025 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q006 | chain_ancestor | sntG0005,sntG0004,sntG0003,sntG0002,sntG0001 | e0000026,e0000027,e0000028,e0000029,e0000030 | gold 链长 5; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q007 | chain_ancestor | sntB0004,sntB0003,sntB0002,sntB0001 | e0000031,e0000032,e0000033,e0000034,e0000035 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q008 | chain_ancestor | sntF0003,sntF0002,sntF0001 | e0000036,e0000037,e0000038,e0000039,e0000040 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q009 | chain_ancestor | sntC0006,sntC0005,sntC0004,sntC0003,sntC0002,sntC0001 | e0000041,e0000042,e0000043,e0000044,e0000045 | gold 链长 6; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q010 | chain_ancestor | sntC0004,sntC0003,sntC0002,sntC0001 | e0000046,e0000047,e0000048,e0000049,e0000050 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q011 | chain_ancestor | sntD0004,sntD0003,sntD0002,sntD0001 | e0000051,e0000052,e0000053,e0000054,e0000055 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q012 | chain_ancestor | sntJ0004,sntJ0003,sntJ0002,sntJ0001 | e0000056,e0000057,e0000058,e0000059,e0000060 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q013 | chain_ancestor | sntB0003,sntB0002,sntB0001 | e0000061,e0000062,e0000063,e0000064,e0000065 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q014 | chain_ancestor | sntJ0004,sntJ0003,sntJ0002,sntJ0001 | e0000066,e0000067,e0000068,e0000069,e0000070 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q015 | chain_ancestor | sntI0005,sntI0004,sntI0003,sntI0002,sntI0001 | e0000071,e0000072,e0000073,e0000074,e0000075 | gold 链长 5; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q016 | chain_ancestor | sntI0005,sntI0004,sntI0003,sntI0002,sntI0001 | e0000076,e0000077,e0000078,e0000079,e0000080 | gold 链长 5; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q017 | chain_ancestor | sntI0003,sntI0002,sntI0001 | e0000081,e0000082,e0000083,e0000084,e0000085 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q018 | chain_ancestor | sntA0003,sntA0002,sntA0001 | e0000086,e0000087,e0000088,e0000089,e0000090 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q019 | chain_ancestor | sntE0003,sntE0002,sntE0001 | e0000091,e0000092,e0000093,e0000094,e0000095 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q020 | chain_ancestor | sntE0003,sntE0002,sntE0001 | e0000096,e0000097,e0000098,e0000099,e0000100 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q021 | chain_ancestor | sntF0004,sntF0003,sntF0002,sntF0001 | e0000101,e0000102,e0000103,e0000104,e0000105 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q022 | chain_ancestor | sntA0003,sntA0002,sntA0001 | e0000106,e0000107,e0000108,e0000109,e0000110 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q023 | chain_ancestor | sntG0004,sntG0003,sntG0002,sntG0001 | e0000111,e0000112,e0000113,e0000114,e0000115 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q024 | chain_ancestor | sntB0004,sntB0003,sntB0002,sntB0001 | e0000116,e0000117,e0000118,e0000119,e0000120 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q025 | chain_ancestor | sntC0005,sntC0004,sntC0003,sntC0002,sntC0001 | e0000121,e0000122,e0000123,e0000124,e0000125 | gold 链长 5; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q026 | chain_ancestor | sntA0004,sntA0003,sntA0002,sntA0001 | e0000126,e0000127,e0000128,e0000129,e0000130 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q027 | chain_ancestor | sntJ0003,sntJ0002,sntJ0001 | e0000131,e0000132,e0000133,e0000134,e0000135 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q028 | chain_ancestor | sntJ0004,sntJ0003,sntJ0002,sntJ0001 | e0000136,e0000137,e0000138,e0000139,e0000140 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q029 | chain_ancestor | sntH0005,sntH0004,sntH0003,sntH0002,sntH0001 | e0000141,e0000142,e0000143,e0000144,e0000145 | gold 链长 5; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q030 | chain_ancestor | sntH0004,sntH0003,sntH0002,sntH0001 | e0000146,e0000147,e0000148,e0000149,e0000150 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q031 | chain_ancestor | sntE0005,sntE0004,sntE0003,sntE0002,sntE0001 | e0000151,e0000152,e0000153,e0000154,e0000155 | gold 链长 5; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q032 | chain_ancestor | sntA0005,sntA0004,sntA0003,sntA0002,sntA0001 | e0000156,e0000157,e0000158,e0000159,e0000160 | gold 链长 5; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q033 | chain_ancestor | sntD0004,sntD0003,sntD0002,sntD0001 | e0000161,e0000162,e0000163,e0000164,e0000165 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q034 | chain_ancestor | sntG0005,sntG0004,sntG0003,sntG0002,sntG0001 | e0000166,e0000167,e0000168,e0000169,e0000170 | gold 链长 5; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q035 | chain_descendant | sntH0006,sntH0010,sntH0014 | e0000171,e0000172,e0000173,e0000174,e0000175 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q036 | chain_descendant | sntH0002,sntH0003,sntH0004,sntH0005,sntH0006,sntH0007,sntH0008,sntH0009,sntH0010,sntH0011,sntH0012,sntH0013,sntH0014 | e0000176,e0000177,e0000178,e0000179,e0000180 | gold 链长 13; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q037 | chain_descendant | sntF0005,sntF0008,sntF0012 | e0000181,e0000182,e0000183,e0000184,e0000185 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q038 | chain_descendant | sntB0004,sntB0005,sntB0006,sntB0009,sntB0010,sntB0013,sntB0014 | e0000186,e0000187,e0000188,e0000189,e0000190 | gold 链长 7; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q039 | chain_descendant | sntF0002,sntF0003,sntF0004,sntF0005,sntF0006,sntF0007,sntF0008,sntF0009,sntF0010,sntF0011,sntF0012,sntF0013,sntF0014 | e0000191,e0000192,e0000193,e0000194,e0000195 | gold 链长 13; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q040 | chain_descendant | sntC0006,sntC0007,sntC0010,sntC0011,sntC0014,sntC0015 | e0000196,e0000197,e0000198,e0000199,e0000200 | gold 链长 6; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q041 | chain_descendant | sntD0008,sntD0012 | e0000201,e0000202,e0000203,e0000204,e0000205 | gold 链长 2; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q042 | chain_descendant | sntG0004,sntG0005,sntG0007,sntG0008,sntG0009,sntG0011,sntG0012,sntG0013 | e0000206,e0000207,e0000208,e0000209,e0000210 | gold 链长 8; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q043 | chain_descendant | sntH0005,sntH0006,sntH0007,sntH0010,sntH0011,sntH0014 | e0000211,e0000212,e0000213,e0000214,e0000215 | gold 链长 6; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q044 | chain_descendant | sntJ0005,sntJ0007,sntJ0011 | e0000216,e0000217,e0000218,e0000219,e0000220 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q045 | chain_descendant | sntI0004,sntI0005,sntI0006,sntI0008,sntI0010,sntI0012,sntI0014 | e0000221,e0000222,e0000223,e0000224,e0000225 | gold 链长 7; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q046 | chain_descendant | sntD0002,sntD0003,sntD0004,sntD0005,sntD0006,sntD0007,sntD0008,sntD0009,sntD0010,sntD0011,sntD0012,sntD0013,sntD0014 | e0000226,e0000227,e0000228,e0000229,e0000230 | gold 链长 13; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q047 | chain_descendant | sntA0002,sntA0003,sntA0004,sntA0005,sntA0006,sntA0007,sntA0008,sntA0009,sntA0010,sntA0011,sntA0012,sntA0013,sntA0014,sntA0015 | e0000231,e0000232,e0000233,e0000234,e0000235 | gold 链长 14; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q048 | chain_descendant | sntI0006,sntI0012 | e0000236,e0000237,e0000238,e0000239,e0000240 | gold 链长 2; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q049 | chain_descendant | sntI0005,sntI0006,sntI0010,sntI0012 | e0000241,e0000242,e0000243,e0000244,e0000245 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q050 | chain_descendant | sntH0004,sntH0005,sntH0006,sntH0007,sntH0010,sntH0011,sntH0014 | e0000246,e0000247,e0000248,e0000249,e0000250 | gold 链长 7; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q051 | chain_descendant | sntC0003,sntC0004,sntC0005,sntC0006,sntC0007,sntC0008,sntC0009,sntC0010,sntC0011,sntC0012,sntC0013,sntC0014,sntC0015 | e0000251,e0000252,e0000253,e0000254,e0000255 | gold 链长 13; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q052 | chain_descendant | sntG0005,sntG0007,sntG0008,sntG0011,sntG0012 | e0000256,e0000257,e0000258,e0000259,e0000260 | gold 链长 5; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q053 | chain_descendant | sntD0005,sntD0008,sntD0009,sntD0012,sntD0013 | e0000261,e0000262,e0000263,e0000264,e0000265 | gold 链长 5; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q054 | chain_descendant | sntD0004,sntD0005,sntD0008,sntD0009,sntD0012,sntD0013 | e0000266,e0000267,e0000268,e0000269,e0000270 | gold 链长 6; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q055 | chain_descendant | sntE0002,sntE0003,sntE0004,sntE0005,sntE0006,sntE0007,sntE0008,sntE0009,sntE0010,sntE0011,sntE0012,sntE0013,sntE0014 | e0000271,e0000272,e0000273,e0000274,e0000275 | gold 链长 13; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q056 | chain_descendant | sntE0004,sntE0005,sntE0006,sntE0007,sntE0010,sntE0012,sntE0013 | e0000276,e0000277,e0000278,e0000279,e0000280 | gold 链长 7; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q057 | chain_descendant | sntJ0002,sntJ0003,sntJ0004,sntJ0005,sntJ0006,sntJ0007,sntJ0008,sntJ0009,sntJ0010,sntJ0011,sntJ0012,sntJ0013,sntJ0014 | e0000281,e0000282,e0000283,e0000284,e0000285 | gold 链长 13; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q058 | chain_descendant | sntA0005,sntA0008,sntA0010,sntA0014 | e0000286,e0000287,e0000288,e0000289,e0000290 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q059 | chain_descendant | sntE0007,sntE0013 | e0000291,e0000292,e0000293,e0000294,e0000295 | gold 链长 2; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q060 | chain_descendant | sntB0005,sntB0009,sntB0013 | e0000296,e0000297,e0000298,e0000299,e0000300 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q061 | chain_descendant | sntG0008,sntG0012 | e0000301,e0000302,e0000303,e0000304,e0000305 | gold 链长 2; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q062 | chain_descendant | sntC0002,sntC0003,sntC0004,sntC0005,sntC0006,sntC0007,sntC0008,sntC0009,sntC0010,sntC0011,sntC0012,sntC0013,sntC0014,sntC0015 | e0000306,e0000307,e0000308,e0000309,e0000310 | gold 链长 14; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q063 | chain_descendant | sntJ0004,sntJ0005,sntJ0007,sntJ0009,sntJ0011,sntJ0013 | e0000311,e0000312,e0000313,e0000314,e0000315 | gold 链长 6; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q064 | chain_descendant | sntA0004,sntA0005,sntA0006,sntA0008,sntA0010,sntA0012,sntA0014 | e0000316,e0000317,e0000318,e0000319,e0000320 | gold 链长 7; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q065 | chain_descendant | sntF0004,sntF0005,sntF0007,sntF0008,sntF0011,sntF0012 | e0000321,e0000322,e0000323,e0000324,e0000325 | gold 链长 6; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q066 | chain_descendant | sntC0005,sntC0006,sntC0007,sntC0008,sntC0010,sntC0011,sntC0012,sntC0014,sntC0015 | e0000326,e0000327,e0000328,e0000329,e0000330 | gold 链长 9; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q067 | chain_descendant | sntG0002,sntG0003,sntG0004,sntG0005,sntG0006,sntG0007,sntG0008,sntG0009,sntG0010,sntG0011,sntG0012,sntG0013,sntG0014 | e0000331,e0000332,e0000333,e0000334,e0000335 | gold 链长 13; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q068 | chain_descendant | sntB0002,sntB0003,sntB0004,sntB0005,sntB0006,sntB0007,sntB0008,sntB0009,sntB0010,sntB0011,sntB0012,sntB0013,sntB0014 | e0000336,e0000337,e0000338,e0000339,e0000340 | gold 链长 13; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q069 | intervention | SAFE | e0000341,e0000342,e0000343,e0000344,e0000345 | gold=SAFE pred=SAFE (TN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q070 | intervention | sntJ0013 | e0000346,e0000347,e0000348,e0000349,e0000350 | gold=WARNING pred=SAFE (FN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q071 | intervention | sntE0004 | e0000351,e0000352,e0000353,e0000354,e0000355 | gold=WARNING pred=SAFE (FN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q072 | intervention | SAFE | e0000356,e0000357,e0000358,e0000359,e0000360 | gold=SAFE pred=SAFE (TN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q073 | intervention | sntE0014 | e0000361,e0000362,e0000363,e0000364,e0000365 | gold=WARNING pred=SAFE (FN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q074 | intervention | sntA0012 | e0000366,e0000367,e0000368,e0000369,e0000370 | gold=WARNING pred=SAFE (FN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q075 | intervention | sntH0013 | e0000371,e0000372,e0000373,e0000374,e0000375 | gold=WARNING pred=SAFE (FN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q076 | intervention | SAFE | e0000376,e0000377,e0000378,e0000379,e0000380 | gold=SAFE pred=SAFE (TN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q077 | intervention | SAFE | e0000381,e0000382,e0000383,e0000384,e0000385 | gold=SAFE pred=SAFE (TN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q078 | intervention | SAFE | e0000386,e0000387,e0000388,e0000389,e0000390 | gold=SAFE pred=SAFE (TN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q079 | intervention | sntB0001 | e0000391,e0000392,e0000393,e0000394,e0000395 | gold=WARNING pred=SAFE (FN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q080 | intervention | sntI0012 | e0000396,e0000397,e0000398,e0000399,e0000400 | gold=WARNING pred=SAFE (FN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q081 | intervention | sntB0014 | e0000401,e0000402,e0000403,e0000404,e0000405 | gold=WARNING pred=SAFE (FN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q082 | intervention | sntC0015 | e0000406,e0000407,e0000408,e0000409,e0000410 | gold=WARNING pred=SAFE (FN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q083 | intervention | SAFE | e0000411,e0000412,e0000413,e0000414,e0000415 | gold=SAFE pred=SAFE (TN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q084 | intervention | SAFE | e0000416,e0000417,e0000418,e0000419,e0000420 | gold=SAFE pred=SAFE (TN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q085 | intervention | SAFE | e0000421,e0000422,e0000423,e0000424,e0000425 | gold=SAFE pred=SAFE (TN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q086 | intervention | sntA0002 | e0000426,e0000427,e0000428,e0000429,e0000430 | gold=WARNING pred=SAFE (FN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q087 | intervention | SAFE | e0000431,e0000432,e0000433,e0000434,e0000435 | gold=SAFE pred=SAFE (TN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q088 | intervention | SAFE | e0000436,e0000437,e0000438,e0000439,e0000440 | gold=SAFE pred=SAFE (TN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q089 | supersession | sntD0011 | e0000441,e0000442,e0000443,e0000444,e0000445 | gold 当前结论=sntD0011 旧结论=sntD0002; status=missing；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q090 | supersession | sntF0011 | e0000446,e0000447,e0000448,e0000449,e0000450 | gold 当前结论=sntF0011 旧结论=sntF0002; status=missing；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q091 | supersession | sntI0015 | e0000451,e0000452,e0000453,e0000454,e0000455 | gold 当前结论=sntI0015 旧结论=sntI0002; status=missing；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q092 | supersession | sntC0011 | e0000456,e0000457,e0000458,e0000459,e0000460 | gold 当前结论=sntC0011 旧结论=sntC0003; status=missing；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q093 | supersession | sntJ0009 | e0000461,e0000462,e0000463,e0000464,e0000465 | gold 当前结论=sntJ0009 旧结论=sntJ0002; status=missing；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q094 | supersession | sntE0010 | e0000466,e0000467,e0000468,e0000469,e0000470 | gold 当前结论=sntE0010 旧结论=sntE0002; status=missing；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q095 | supersession | sntG0009 | e0000471,e0000472,e0000473,e0000474,e0000475 | gold 当前结论=sntG0009 旧结论=sntG0002; status=missing；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q096 | supersession | sntH0009 | e0000476,e0000477,e0000478,e0000479,e0000480 | gold 当前结论=sntH0009 旧结论=sntH0002; status=missing；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q097 | supersession | sntA0015 | e0000481,e0000482,e0000483,e0000484,e0000485 | gold 当前结论=sntA0015 旧结论=sntA0002; status=missing；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q098 | supersession | sntB0009 | e0000486,e0000487,e0000488,e0000489,e0000490 | gold 当前结论=sntB0009 旧结论=sntB0002; status=missing；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q099 | negative | ∅ | e0000491,e0000492,e0000493,e0000494,e0000495 | gold 恒空；召回 5 条 → noisy=True |
| q100 | negative | ∅ | e0000496,e0000497,e0000498,e0000499,e0000500 | gold 恒空；召回 5 条 → noisy=True |
| q101 | negative | ∅ | e0000501,e0000502,e0000503,e0000504,e0000505 | gold 恒空；召回 5 条 → noisy=True |
| q102 | negative | ∅ | e0000506,e0000507,e0000508,e0000509,e0000510 | gold 恒空；召回 5 条 → noisy=True |
| q103 | negative | ∅ | e0000511,e0000512,e0000513,e0000514,e0000515 | gold 恒空；召回 5 条 → noisy=True |
| q104 | negative | ∅ | e0000516,e0000517,e0000518,e0000519,e0000520 | gold 恒空；召回 5 条 → noisy=True |
| q105 | negative | ∅ | e0000521,e0000522,e0000523,e0000524,e0000525 | gold 恒空；召回 5 条 → noisy=True |
| q106 | negative | ∅ | e0000526,e0000527,e0000528,e0000529,e0000530 | gold 恒空；召回 5 条 → noisy=True |
| q107 | negative | ∅ | e0000531,e0000532,e0000533,e0000534,e0000535 | gold 恒空；召回 5 条 → noisy=True |
| q108 | negative | ∅ | e0000536,e0000537,e0000538,e0000539,e0000540 | gold 恒空；召回 5 条 → noisy=True |
| q109 | negative | ∅ | e0000541,e0000542,e0000543,e0000544,e0000545 | gold 恒空；召回 5 条 → noisy=True |
| q110 | negative | ∅ | e0000546,e0000547,e0000548,e0000549,e0000550 | gold 恒空；召回 5 条 → noisy=True |
| q111 | negative | ∅ | e0000551,e0000552,e0000553,e0000554,e0000555 | gold 恒空；召回 5 条 → noisy=True |
| q112 | negative | ∅ | e0000556,e0000557,e0000558,e0000559,e0000560 | gold 恒空；召回 5 条 → noisy=True |
| q113 | negative | ∅ | e0000561,e0000562,e0000563,e0000564,e0000565 | gold 恒空；召回 5 条 → noisy=True |
| q114 | negative | ∅ | e0000566,e0000567,e0000568,e0000569,e0000570 | gold 恒空；召回 5 条 → noisy=True |
| q115 | negative | ∅ | e0000571,e0000572,e0000573,e0000574,e0000575 | gold 恒空；召回 5 条 → noisy=True |
| q116 | negative | ∅ | e0000576,e0000577,e0000578,e0000579,e0000580 | gold 恒空；召回 5 条 → noisy=True |
| q117 | negative | ∅ | e0000581,e0000582,e0000583,e0000584,e0000585 | gold 恒空；召回 5 条 → noisy=True |
| q118 | negative | ∅ | e0000586,e0000587,e0000588,e0000589,e0000590 | gold 恒空；召回 5 条 → noisy=True |
| q119 | negative | ∅ | e0000591,e0000592,e0000593,e0000594,e0000595 | gold 恒空；召回 5 条 → noisy=True |
| q120 | negative | ∅ | e0000596,e0000597,e0000598,e0000599,e0000600 | gold 恒空；召回 5 条 → noisy=True |
| q121 | negative | ∅ | e0000601,e0000602,e0000603,e0000604,e0000605 | gold 恒空；召回 5 条 → noisy=True |
| q122 | negative | ∅ | e0000606,e0000607,e0000608,e0000609,e0000610 | gold 恒空；召回 5 条 → noisy=True |
（共 122 题，全部列出）


# agimem 指标面板

> **本臂：236题新树attach边。**
>
> **醒目声明：被测隔离库已写入合成因果树（143 节点），下表是该记忆系统在本语料上的检索层真能力分；但语料全合成、gold 由树结构机械推导、且 supersession 为 oracle 口径，外推到真实业务需另证。**

- 判分参数：topk=5，min_score=0.0
- 判分题量：236/236
- 单题权重：1/236 ≈ 0.42pp（26 题时 1 条≈3.8pp，扩集后 1 条≤0.83pp 才够看趋势）

## 一、题量与题型分布

| 题型 | 题数 | 占比 |
|---|---:|---:|
| chain_ancestor | 68 | 28.8% |
| chain_descendant | 68 | 28.8% |
| intervention | 40 | 16.9% |
| supersession | 20 | 8.5% |
| negative | 40 | 16.9% |
| **合计** | **236** | 100% |

## 二、指标点估计与 95% 置信区间

比例类指标用 Wilson score 区间；链覆盖率用正态近似均值区间。

| 指标 | 点估计 | 95% CI | n(分母) | 方向 |
|---|---:|---|---:|---|
| `chain_hit@5` | 0.7353 | 0.735 [0.655, 0.802] | 136 | 越高越好 |
| `chain_hit@1` | 0.2941 | 0.294 [0.224, 0.376] | 136 | 越高越好 |
| `chain_cov` | 0.2969 | 0.297 [0.252, 0.342] | 136 | 越高越好 |
| `intervention_acc` | 0.6000 | 0.600 [0.446, 0.737] | 40 | 越高越好 |
| `false_alarm_rate` | 0.8000 | 0.800 [0.584, 0.919] | 20 | 越低越好 |
| `supersession_acc` | 0.0000 | 0.000 [0.000, 0.161] | 20 | 越高越好 |
| `negative_noise_rate` | 0.3250 | 0.325 [0.201, 0.480] | 40 | 越低越好 |

干预混淆矩阵 TP/FP/FN/TN = 20/16/0/4（WARNING n=20，SAFE n=20）；取代 current/stale/missing = 0/20/0。

## 四、单题明细下钻（qid → gold → top-k → 判分理由）

| qid | 题型 | gold | top-k 召回 | 判分理由 |
|---|---|---|---|---|
| q001 | chain_ancestor | sntA0003,sntA0002,sntA0001 | sntA0023,sntA0021,sntA0007,sntA0006,sntA0016 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q002 | chain_ancestor | sntI0031,sntI0030,sntI0002,sntI0001 | sntI0032,sntI0001,sntI0026,sntB0032,sntI0017 | gold 链长 4; top-5 内首个 gold rank=1; 覆盖率=0.250（召回全集对 gold） |
| q003 | chain_ancestor | sntF0003,sntF0002,sntF0001 | sntF0004,sntF0003,sntF0005,sntH0007,sntE0031 | gold 链长 3; top-5 内首个 gold rank=1; 覆盖率=0.333（召回全集对 gold） |
| q004 | chain_ancestor | sntE0031,sntE0030,sntE0001 | sntE0032,sntE0030,sntE0003,sntF0032,sntE0028 | gold 链长 3; top-5 内首个 gold rank=1; 覆盖率=0.333（召回全集对 gold） |
| q005 | chain_ancestor | sntA0025,sntA0024,sntA0002,sntA0001 | sntA0026,sntA0024,sntE0028,sntB0032,sntJ0023 | gold 链长 4; top-5 内首个 gold rank=1; 覆盖率=0.250（召回全集对 gold） |
| q006 | chain_ancestor | sntF0004,sntF0003,sntF0002,sntF0001 | sntF0025,sntF0024,sntF0001,sntF0029,sntA0017 | gold 链长 4; top-5 内首个 gold rank=2; 覆盖率=0.250（召回全集对 gold） |
| q007 | chain_ancestor | sntC0014,sntC0013,sntC0005,sntC0004,sntC0003,sntC0002,sntC0001 | sntC0015,sntC0013,sntC0019,sntC0021,sntJ0023 | gold 链长 7; top-5 内首个 gold rank=1; 覆盖率=0.143（召回全集对 gold） |
| q008 | chain_ancestor | sntG0005,sntG0004,sntG0003,sntG0002,sntG0001 | sntG0022,sntG0021,sntA0017,sntI0017,sntG0004 | gold 链长 5; top-5 内首个 gold rank=4; 覆盖率=0.200（召回全集对 gold） |
| q009 | chain_ancestor | sntD0004,sntD0003,sntD0002,sntD0001 | sntD0005,sntD0027,sntC0006,sntH0001,sntG0001 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q010 | chain_ancestor | sntB0018,sntB0003,sntB0002,sntB0001 | sntB0019,sntB0018,sntB0013,sntB0031,sntJ0023 | gold 链长 4; top-5 内首个 gold rank=1; 覆盖率=0.250（召回全集对 gold） |
| q011 | chain_ancestor | sntB0028,sntB0027,sntB0005,sntB0004,sntB0003,sntB0002,sntB0001 | sntB0029,sntB0027,sntB0032,sntB0020,sntA0017 | gold 链长 7; top-5 内首个 gold rank=1; 覆盖率=0.143（召回全集对 gold） |
| q012 | chain_ancestor | sntF0003,sntF0002,sntF0001 | sntF0019,sntF0018,sntF0010,sntF0009,sntH0019 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q013 | chain_ancestor | sntF0010,sntF0009,sntF0005,sntF0004,sntF0003,sntF0002,sntF0001 | sntF0011,sntF0009,sntF0020,sntF0018,sntB0029 | gold 链长 7; top-5 内首个 gold rank=1; 覆盖率=0.143（召回全集对 gold） |
| q014 | chain_ancestor | sntD0013,sntD0012,sntD0003,sntD0002,sntD0001 | sntD0014,sntD0012,sntD0017,sntD0015,sntB0032 | gold 链长 5; top-5 内首个 gold rank=1; 覆盖率=0.200（召回全集对 gold） |
| q015 | chain_ancestor | sntC0026,sntC0025,sntC0005,sntC0004,sntC0003,sntC0002,sntC0001 | sntC0027,sntC0025,sntG0026,sntH0020,sntH0014 | gold 链长 7; top-5 内首个 gold rank=1; 覆盖率=0.143（召回全集对 gold） |
| q016 | chain_ancestor | sntC0031,sntC0002,sntC0001 | sntC0002,sntC0032,sntC0001,sntC0029,sntB0027 | gold 链长 3; top-5 内首个 gold rank=0; 覆盖率=0.667（召回全集对 gold） |
| q017 | chain_ancestor | sntD0030,sntD0003,sntD0002,sntD0001 | sntD0031,sntD0030,sntD0013,sntG0014,sntD0011 | gold 链长 4; top-5 内首个 gold rank=1; 覆盖率=0.250（召回全集对 gold） |
| q018 | chain_ancestor | sntD0031,sntD0030,sntD0003,sntD0002,sntD0001 | sntD0032,sntD0023,sntG0014,sntD0011,sntD0014 | gold 链长 5; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q019 | chain_ancestor | sntD0003,sntD0002,sntD0001 | sntD0031,sntD0030,sntD0011,sntG0013,sntD0001 | gold 链长 3; top-5 内首个 gold rank=4; 覆盖率=0.333（召回全集对 gold） |
| q020 | chain_ancestor | sntJ0022,sntJ0021,sntJ0003,sntJ0002,sntJ0001 | sntJ0023,sntJ0021,sntJ0014,sntB0032,sntH0020 | gold 链长 5; top-5 内首个 gold rank=1; 覆盖率=0.200（召回全集对 gold） |
| q021 | chain_ancestor | sntJ0003,sntJ0002,sntJ0001 | sntJ0022,sntJ0021,sntJ0012,sntJ0013,sntB0031 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q022 | chain_ancestor | sntJ0005,sntJ0004,sntJ0003,sntJ0002,sntJ0001 | sntJ0016,sntJ0015,sntJ0007,sntJ0006,sntJ0001 | gold 链长 5; top-5 内首个 gold rank=4; 覆盖率=0.200（召回全集对 gold） |
| q023 | chain_ancestor | sntB0012,sntB0002,sntB0001 | sntB0013,sntB0012,sntB0019,sntB0028,sntB0031 | gold 链长 3; top-5 内首个 gold rank=1; 覆盖率=0.333（召回全集对 gold） |
| q024 | chain_ancestor | sntI0009,sntI0004,sntI0003,sntI0002,sntI0001 | sntI0010,sntI0009,sntI0015,sntG0029,sntB0031 | gold 链长 5; top-5 内首个 gold rank=1; 覆盖率=0.200（召回全集对 gold） |
| q025 | chain_ancestor | sntG0016,sntG0015,sntG0004,sntG0003,sntG0002,sntG0001 | sntG0017,sntG0015,sntD0014,sntD0023,sntD0008 | gold 链长 6; top-5 内首个 gold rank=1; 覆盖率=0.167（召回全集对 gold） |
| q026 | chain_ancestor | sntI0004,sntI0003,sntI0002,sntI0001 | sntI0005,sntG0001,sntH0006,sntD0021,sntB0021 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q027 | chain_ancestor | sntI0007,sntI0006,sntI0002,sntI0001 | sntI0008,sntI0006,sntI0018,sntI0020,sntI0014 | gold 链长 4; top-5 内首个 gold rank=1; 覆盖率=0.250（召回全集对 gold） |
| q028 | chain_ancestor | sntI0016,sntI0015,sntI0003,sntI0002,sntI0001 | sntI0017,sntI0015,sntI0023,sntI0026,sntI0032 | gold 链长 5; top-5 内首个 gold rank=1; 覆盖率=0.200（召回全集对 gold） |
| q029 | chain_ancestor | sntI0003,sntI0002,sntI0001 | sntI0004,sntI0002,sntI0028,sntH0020,sntI0031 | gold 链长 3; top-5 内首个 gold rank=1; 覆盖率=0.333（召回全集对 gold） |
| q030 | chain_ancestor | sntI0013,sntI0012,sntI0001 | sntI0014,sntI0012,sntI0023,sntI0021,sntI0008 | gold 链长 3; top-5 内首个 gold rank=1; 覆盖率=0.333（召回全集对 gold） |
| q031 | chain_ancestor | sntI0019,sntI0018,sntI0002,sntI0001 | sntI0020,sntI0018,sntI0017,sntI0008,sntI0023 | gold 链长 4; top-5 内首个 gold rank=1; 覆盖率=0.250（召回全集对 gold） |
| q032 | chain_ancestor | sntI0025,sntI0024,sntI0001 | sntI0026,sntI0024,sntI0032,sntI0002,sntI0029 | gold 链长 3; top-5 内首个 gold rank=1; 覆盖率=0.333（召回全集对 gold） |
| q033 | chain_ancestor | sntA0007,sntA0006,sntA0004,sntA0003,sntA0002,sntA0001 | sntA0007,sntA0023,sntA0006,sntA0017,sntH0020 | gold 链长 6; top-5 内首个 gold rank=0; 覆盖率=0.333（召回全集对 gold） |
| q034 | chain_ancestor | sntA0028,sntA0027,sntA0001 | sntA0029,sntA0027,sntJ0023,sntB0032,sntB0029 | gold 链长 3; top-5 内首个 gold rank=1; 覆盖率=0.333（召回全集对 gold） |
| q035 | chain_ancestor | sntE0025,sntE0024,sntE0004,sntE0003,sntE0002,sntE0001 | sntE0026,sntE0024,sntJ0023,sntH0020,sntH0007 | gold 链长 6; top-5 内首个 gold rank=1; 覆盖率=0.167（召回全集对 gold） |
| q036 | chain_ancestor | sntE0004,sntE0003,sntE0002,sntE0001 | sntE0026,sntE0024,sntE0002,sntE0010,sntJ0023 | gold 链长 4; top-5 内首个 gold rank=2; 覆盖率=0.250（召回全集对 gold） |
| q037 | chain_ancestor | sntD0003,sntD0002,sntD0001 | sntD0004,sntE0019,sntD0022,sntD0013,sntF0033 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q038 | chain_ancestor | sntE0012,sntE0004,sntE0003,sntE0002,sntE0001 | sntE0013,sntE0012,sntE0021,sntE0023,sntE0028 | gold 链长 5; top-5 内首个 gold rank=1; 覆盖率=0.200（召回全集对 gold） |
| q039 | chain_ancestor | sntE0007,sntE0006,sntE0001 | sntE0008,sntE0006,sntE0017,sntJ0014,sntJ0001 | gold 链长 3; top-5 内首个 gold rank=1; 覆盖率=0.333（召回全集对 gold） |
| q040 | chain_ancestor | sntJ0009,sntJ0003,sntJ0002,sntJ0001 | sntJ0011,sntJ0009,sntJ0023,sntE0019,sntB0031 | gold 链长 4; top-5 内首个 gold rank=1; 覆盖率=0.250（召回全集对 gold） |
| q041 | chain_ancestor | sntF0027,sntF0002,sntF0001 | sntF0028,sntF0027,sntF0022,sntB0031,sntA0017 | gold 链长 3; top-5 内首个 gold rank=1; 覆盖率=0.333（召回全集对 gold） |
| q042 | chain_ancestor | sntF0006,sntF0003,sntF0002,sntF0001 | sntF0008,sntF0006,sntF0022,sntB0016,sntH0019 | gold 链长 4; top-5 内首个 gold rank=1; 覆盖率=0.250（召回全集对 gold） |
| q043 | chain_ancestor | sntF0007,sntF0006,sntF0003,sntF0002,sntF0001 | sntF0008,sntF0006,sntF0023,sntB0016,sntH0020 | gold 链长 5; top-5 内首个 gold rank=1; 覆盖率=0.200（召回全集对 gold） |
| q044 | chain_ancestor | sntA0019,sntA0018,sntA0004,sntA0003,sntA0002,sntA0001 | sntA0020,sntA0014,sntA0018,sntA0012,sntB0032 | gold 链长 6; top-5 内首个 gold rank=2; 覆盖率=0.167（召回全集对 gold） |
| q045 | chain_ancestor | sntG0031,sntG0030,sntG0001 | sntG0032,sntG0030,sntG0008,sntB0032,sntH0020 | gold 链长 3; top-5 内首个 gold rank=1; 覆盖率=0.333（召回全集对 gold） |
| q046 | chain_ancestor | sntB0006,sntB0003,sntB0002,sntB0001 | sntB0007,sntB0006,sntB0004,sntB0025,sntH0007 | gold 链长 4; top-5 内首个 gold rank=1; 覆盖率=0.250（召回全集对 gold） |
| q047 | chain_ancestor | sntB0024,sntB0002,sntB0001 | sntB0025,sntB0024,sntB0008,sntB0006,sntB0003 | gold 链长 3; top-5 内首个 gold rank=1; 覆盖率=0.333（召回全集对 gold） |
| q048 | chain_ancestor | sntB0025,sntB0024,sntB0002,sntB0001 | sntB0026,sntB0024,sntB0008,sntB0006,sntH0020 | gold 链长 4; top-5 内首个 gold rank=1; 覆盖率=0.250（召回全集对 gold） |
| q049 | chain_ancestor | sntH0028,sntH0027,sntH0002,sntH0001 | sntH0029,sntH0027,sntD0011,sntD0026,sntH0020 | gold 链长 4; top-5 内首个 gold rank=1; 覆盖率=0.250（召回全集对 gold） |
| q050 | chain_ancestor | sntC0023,sntC0022,sntC0006,sntC0005,sntC0004,sntC0003,sntC0002,sntC0001 | sntC0024,sntC0022,sntC0009,sntC0007,sntH0007 | gold 链长 8; top-5 内首个 gold rank=1; 覆盖率=0.125（召回全集对 gold） |
| q051 | chain_ancestor | sntC0006,sntC0005,sntC0004,sntC0003,sntC0002,sntC0001 | sntC0024,sntC0022,sntC0008,sntC0007,sntG0001 | gold 链长 6; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q052 | chain_ancestor | sntE0015,sntE0002,sntE0001 | sntE0016,sntE0015,sntJ0023,sntE0007,sntH0007 | gold 链长 3; top-5 内首个 gold rank=1; 覆盖率=0.333（召回全集对 gold） |
| q053 | chain_ancestor | sntA0004,sntA0003,sntA0002,sntA0001 | sntA0032,sntA0030,sntB0031,sntJ0023,sntA0017 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q054 | chain_ancestor | sntJ0018,sntJ0002,sntJ0001 | sntJ0019,sntJ0018,sntJ0028,sntJ0027,sntH0020 | gold 链长 3; top-5 内首个 gold rank=1; 覆盖率=0.333（召回全集对 gold） |
| q055 | chain_ancestor | sntH0025,sntH0024,sntH0001 | sntH0026,sntH0024,sntH0001,sntH0020,sntH0007 | gold 链长 3; top-5 内首个 gold rank=1; 覆盖率=0.667（召回全集对 gold） |
| q056 | chain_ancestor | sntH0007,sntH0006,sntH0001 | sntH0008,sntH0006,sntH0020,sntH0018,sntB0032 | gold 链长 3; top-5 内首个 gold rank=1; 覆盖率=0.333（召回全集对 gold） |
| q057 | chain_ancestor | sntH0019,sntH0018,sntH0001 | sntH0020,sntH0018,sntH0008,sntH0026,sntH0032 | gold 链长 3; top-5 内首个 gold rank=1; 覆盖率=0.333（召回全集对 gold） |
| q058 | chain_ancestor | sntH0031,sntH0030,sntH0004,sntH0003,sntH0002,sntH0001 | sntH0032,sntH0030,sntH0020,sntH0008,sntH0026 | gold 链长 6; top-5 内首个 gold rank=1; 覆盖率=0.167（召回全集对 gold） |
| q059 | chain_ancestor | sntH0021,sntH0003,sntH0002,sntH0001 | sntH0022,sntH0021,sntH0011,sntH0019,sntG0014 | gold 链长 4; top-5 内首个 gold rank=1; 覆盖率=0.250（召回全集对 gold） |
| q060 | chain_ancestor | sntB0015,sntB0005,sntB0004,sntB0003,sntB0002,sntB0001 | sntB0016,sntB0015,sntJ0023,sntC0018,sntH0020 | gold 链长 6; top-5 内首个 gold rank=1; 覆盖率=0.167（召回全集对 gold） |
| q061 | chain_ancestor | sntE0009,sntE0003,sntE0002,sntE0001 | sntE0010,sntE0009,sntE0018,sntE0019,sntE0025 | gold 链长 4; top-5 内首个 gold rank=1; 覆盖率=0.250（召回全集对 gold） |
| q062 | chain_ancestor | sntE0010,sntE0009,sntE0003,sntE0002,sntE0001 | sntE0011,sntE0009,sntE0018,sntE0020,sntE0025 | gold 链长 5; top-5 内首个 gold rank=1; 覆盖率=0.200（召回全集对 gold） |
| q063 | chain_ancestor | sntH0016,sntH0015,sntH0005,sntH0004,sntH0003,sntH0002,sntH0001 | sntH0017,sntH0015,sntD0011,sntH0014,sntG0026 | gold 链长 7; top-5 内首个 gold rank=1; 覆盖率=0.143（召回全集对 gold） |
| q064 | chain_ancestor | sntH0005,sntH0004,sntH0003,sntH0002,sntH0001 | sntH0016,sntH0015,sntD0011,sntH0001,sntH0014 | gold 链长 5; top-5 内首个 gold rank=3; 覆盖率=0.200（召回全集对 gold） |
| q065 | chain_ancestor | sntD0019,sntD0018,sntD0002,sntD0001 | sntD0020,sntD0018,sntD0011,sntH0008,sntH0020 | gold 链长 4; top-5 内首个 gold rank=1; 覆盖率=0.250（召回全集对 gold） |
| q066 | chain_ancestor | sntD0010,sntD0009,sntD0001 | sntD0011,sntD0009,sntH0017,sntH0029,sntD0020 | gold 链长 3; top-5 内首个 gold rank=1; 覆盖率=0.333（召回全集对 gold） |
| q067 | chain_ancestor | sntG0028,sntG0027,sntG0004,sntG0003,sntG0002,sntG0001 | sntG0029,sntC0009,sntG0027,sntI0011,sntB0032 | gold 链长 6; top-5 内首个 gold rank=2; 覆盖率=0.167（召回全集对 gold） |
| q068 | chain_ancestor | sntB0031,sntB0030,sntB0003,sntB0002,sntB0001 | sntB0032,sntB0030,sntB0001,sntB0002,sntJ0023 | gold 链长 5; top-5 内首个 gold rank=1; 覆盖率=0.600（召回全集对 gold） |
| q069 | chain_descendant | sntA0023 | sntA0022,sntA0021,sntA0007,sntA0006,sntB0018 | gold 链长 1; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q070 | chain_descendant | sntJ0028,sntJ0029 | sntJ0028,sntJ0027,sntJ0018,sntJ0019,sntB0018 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q071 | chain_descendant | sntI0032 | sntI0032,sntI0001,sntI0024,sntI0026,sntB0031 | gold 链长 1; top-5 内首个 gold rank=0; 覆盖率=1.000（召回全集对 gold） |
| q072 | chain_descendant | sntI0031,sntI0032 | sntI0001,sntI0032,sntI0024,sntI0002,sntI0026 | gold 链长 2; top-5 内首个 gold rank=1; 覆盖率=0.500（召回全集对 gold） |
| q073 | chain_descendant | sntE0029 | sntE0028,sntE0027,sntA0025,sntE0031,sntA0024 | gold 链长 1; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q074 | chain_descendant | sntF0026 | sntF0025,sntF0024,sntF0001,sntF0029,sntI0029 | gold 链长 1; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q075 | chain_descendant | sntC0014,sntC0015 | sntC0014,sntC0013,sntC0019,sntC0021,sntB0018 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q076 | chain_descendant | sntG0010,sntG0011 | sntG0011,sntG0009,sntG0021,sntG0004,sntG0022 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q077 | chain_descendant | sntA0017 | sntA0016,sntA0015,sntA0001,sntA0007,sntA0012 | gold 链长 1; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q078 | chain_descendant | sntC0010,sntC0011,sntC0012,sntC0022,sntC0023,sntC0024 | sntC0006,sntD0005,sntC0005,sntG0001,sntI0005 | gold 链长 6; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q079 | chain_descendant | sntC0006,sntC0010,sntC0011,sntC0012,sntC0013,sntC0014,sntC0015,sntC0022,sntC0023,sntC0024,sntC0025,sntC0026,sntC0027 | sntC0005,sntE0004,sntC0004,sntG0001,sntI0003 | gold 链长 13; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q080 | chain_descendant | sntH0005,sntH0012,sntH0013,sntH0014,sntH0015,sntH0016,sntH0017,sntH0030,sntH0031,sntH0032 | sntH0004,sntG0001,sntI0003,sntH0005,sntC0025 | gold 链长 10; top-5 内首个 gold rank=3; 覆盖率=0.100（召回全集对 gold） |
| q081 | chain_descendant | sntB0019,sntB0020 | sntB0019,sntB0018,sntB0012,sntB0014,sntB0001 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q082 | chain_descendant | sntF0010,sntF0011 | sntF0011,sntF0009,sntF0018,sntF0019,sntF0001 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q083 | chain_descendant | sntD0014 | sntD0013,sntD0012,sntD0015,sntD0016,sntD0001 | gold 链长 1; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q084 | chain_descendant | sntD0013,sntD0014 | sntD0013,sntD0012,sntD0015,sntD0016,sntD0001 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q085 | chain_descendant | sntC0026,sntC0027 | sntC0027,sntC0025,sntG0006,sntG0024,sntA0001 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q086 | chain_descendant | sntD0008 | sntD0008,sntD0006,sntD0021,sntD0022,sntG0017 | gold 链长 1; top-5 内首个 gold rank=0; 覆盖率=1.000（召回全集对 gold） |
| q087 | chain_descendant | sntD0007,sntD0008 | sntD0008,sntD0006,sntD0021,sntD0022,sntD0001 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q088 | chain_descendant | sntB0010,sntB0011 | sntB0011,sntB0009,sntB0021,sntB0023,sntA0001 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q089 | chain_descendant | sntJ0017 | sntJ0017,sntJ0015,sntJ0007,sntJ0006,sntJ0001 | gold 链长 1; top-5 内首个 gold rank=0; 覆盖率=1.000（召回全集对 gold） |
| q090 | chain_descendant | sntD0017 | sntD0016,sntD0015,sntD0013,sntD0001,sntD0012 | gold 链长 1; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q091 | chain_descendant | sntD0016,sntD0017 | sntD0016,sntD0015,sntD0013,sntD0001,sntD0012 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q092 | chain_descendant | sntG0017 | sntG0016,sntG0015,sntD0014,sntG0006,sntD0008 | gold 链长 1; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q093 | chain_descendant | sntG0016,sntG0017 | sntG0016,sntG0015,sntG0006,sntD0014,sntD0001 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q094 | chain_descendant | sntF0032 | sntF0031,sntF0030,sntF0002,sntE0031,sntE0003 | gold 链长 1; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q095 | chain_descendant | sntI0023 | sntI0022,sntI0021,sntI0014,sntI0012,sntI0020 | gold 链长 1; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q096 | chain_descendant | sntI0008 | sntI0008,sntI0006,sntI0018,sntI0020,sntI0013 | gold 链长 1; top-5 内首个 gold rank=0; 覆盖率=1.000（召回全集对 gold） |
| q097 | chain_descendant | sntI0007,sntI0008 | sntI0008,sntI0006,sntI0018,sntI0020,sntI0012 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q098 | chain_descendant | sntI0028,sntI0029 | sntI0029,sntI0027,sntI0004,sntI0024,sntI0009 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q099 | chain_descendant | sntI0014 | sntI0013,sntI0012,sntI0022,sntI0021,sntI0020 | gold 链长 1; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q100 | chain_descendant | sntI0020 | sntI0020,sntI0018,sntI0008,sntI0012,sntI0022 | gold 链长 1; top-5 内首个 gold rank=0; 覆盖率=1.000（召回全集对 gold） |
| q101 | chain_descendant | sntI0025,sntI0026 | sntI0026,sntI0024,sntI0002,sntI0029,sntI0032 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q102 | chain_descendant | sntA0008 | sntA0007,sntA0006,sntA0022,sntA0021,sntB0018 | gold 链长 1; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q103 | chain_descendant | sntA0028,sntA0029 | sntA0028,sntA0027,sntA0025,sntI0001,sntG0001 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q104 | chain_descendant | sntC0029,sntC0030 | sntC0029,sntC0028,sntC0003,sntC0004,sntH0001 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q105 | chain_descendant | sntE0013,sntE0014 | sntE0013,sntE0012,sntE0021,sntE0023,sntE0003 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q106 | chain_descendant | sntE0022,sntE0023 | sntE0022,sntE0021,sntE0012,sntE0003,sntE0013 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q107 | chain_descendant | sntE0004,sntE0005,sntE0009,sntE0010,sntE0011,sntE0012,sntE0013,sntE0014,sntE0021,sntE0022,sntE0023,sntE0024,sntE0025,sntE0026 | sntE0003,sntE0031,sntI0011,sntG0004,sntB0031 | gold 链长 14; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q108 | chain_descendant | sntJ0010,sntJ0011 | sntJ0010,sntJ0009,sntJ0018,sntJ0023,sntE0013 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q109 | chain_descendant | sntA0005,sntA0006,sntA0007,sntA0008,sntA0018,sntA0019,sntA0020,sntA0030,sntA0031,sntA0032 | sntA0004,sntA0024,sntA0027,sntG0001,sntH0006 | gold 链长 10; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q110 | chain_descendant | sntA0014 | sntA0013,sntA0012,sntA0019,sntA0018,sntG0031 | gold 链长 1; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q111 | chain_descendant | sntG0014 | sntG0013,sntG0012,sntG0018,sntE0028,sntI0011 | gold 链长 1; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q112 | chain_descendant | sntG0013,sntG0014 | sntG0012,sntG0013,sntG0018,sntG0030,sntB0030 | gold 链长 2; top-5 内首个 gold rank=1; 覆盖率=0.500（召回全集对 gold） |
| q113 | chain_descendant | sntG0019,sntG0020 | sntG0020,sntG0018,sntI0024,sntB0020,sntE0003 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q114 | chain_descendant | sntG0008 | sntG0007,sntG0006,sntG0031,sntH0012,sntG0002 | gold 链长 1; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q115 | chain_descendant | sntB0005,sntB0009,sntB0010,sntB0011,sntB0015,sntB0016,sntB0017,sntB0021,sntB0022,sntB0023,sntB0027,sntB0028,sntB0029 | sntB0004,sntB0006,sntB0008,sntB0024,sntB0003 | gold 链长 13; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q116 | chain_descendant | sntB0007,sntB0008 | sntB0008,sntB0006,sntB0004,sntB0024,sntB0003 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q117 | chain_descendant | sntH0028,sntH0029 | sntH0028,sntH0027,sntH0003,sntH0005,sntH0004 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q118 | chain_descendant | sntF0016,sntF0017 | sntF0017,sntF0015,sntF0014,sntF0012,sntH0033 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q119 | chain_descendant | sntF0014 | sntF0013,sntF0012,sntF0015,sntF0017,sntF0002 | gold 链长 1; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q120 | chain_descendant | sntF0013,sntF0014 | sntF0013,sntF0012,sntF0015,sntF0017,sntF0002 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q121 | chain_descendant | sntJ0004,sntJ0005,sntJ0009,sntJ0010,sntJ0011,sntJ0012,sntJ0013,sntJ0014,sntJ0015,sntJ0016,sntJ0017,sntJ0021,sntJ0022,sntJ0023,sntJ0024,sntJ0025,sntJ0026,sntJ0027,sntJ0028,sntJ0029 | sntJ0003,sntJ0031,sntE0017,sntF0003,sntB0018 | gold 链长 20; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q122 | chain_descendant | sntE0016,sntE0017 | sntE0017,sntE0015,sntE0006,sntE0007,sntJ0031 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q123 | chain_descendant | sntA0032 | sntA0032,sntA0030,sntA0001,sntA0024,sntB0031 | gold 链长 1; top-5 内首个 gold rank=0; 覆盖率=1.000（召回全集对 gold） |
| q124 | chain_descendant | sntF0004,sntF0005,sntF0006,sntF0007,sntF0008,sntF0009,sntF0010,sntF0011,sntF0012,sntF0013,sntF0014,sntF0018,sntF0019,sntF0020,sntF0021,sntF0022,sntF0023,sntF0024,sntF0025,sntF0026,sntF0030,sntF0031,sntF0032 | sntF0003,sntD0022,sntE0031,sntH0013,sntH0033 | gold 链长 23; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q125 | chain_descendant | sntH0025,sntH0026 | sntH0025,sntH0024,sntH0001,sntH0006,sntH0018 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q126 | chain_descendant | sntJ0015,sntJ0016,sntJ0017,sntJ0027,sntJ0028,sntJ0029 | sntJ0005,sntJ0025,sntD0003,sntC0001,sntG0001 | gold 链长 6; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q127 | chain_descendant | sntF0009,sntF0010,sntF0011,sntF0021,sntF0022,sntF0023 | sntF0005,sntF0002,sntF0001,sntI0001,sntB0018 | gold 链长 6; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q128 | chain_descendant | sntH0011 | sntH0011,sntH0009,sntH0021,sntH0022,sntC0022 | gold 链长 1; top-5 内首个 gold rank=0; 覆盖率=1.000（召回全集对 gold） |
| q129 | chain_descendant | sntH0010,sntH0011 | sntH0011,sntH0009,sntH0021,sntH0023,sntC0022 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q130 | chain_descendant | sntH0014 | sntH0013,sntH0012,sntH0015,sntG0024,sntB0031 | gold 链长 1; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q131 | chain_descendant | sntH0013,sntH0014 | sntH0013,sntH0012,sntH0015,sntG0024,sntH0001 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q132 | chain_descendant | sntA0011 | sntA0010,sntA0009,sntB0023,sntA0001,sntE0025 | gold 链长 1; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q133 | chain_descendant | sntD0020 | sntD0019,sntD0018,sntD0011,sntH0007,sntH0028 | gold 链长 1; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q134 | chain_descendant | sntD0026 | sntD0026,sntD0024,sntH0028,sntD0018,sntH0007 | gold 链长 1; top-5 内首个 gold rank=0; 覆盖率=1.000（召回全集对 gold） |
| q135 | chain_descendant | sntD0011 | sntD0011,sntD0009,sntH0028,sntH0016,sntD0020 | gold 链长 1; top-5 内首个 gold rank=0; 覆盖率=1.000（召回全集对 gold） |
| q136 | chain_descendant | sntB0031,sntB0032 | sntB0031,sntB0030,sntB0001,sntB0002,sntI0001 | gold 链长 2; top-5 内首个 gold rank=0; 覆盖率=0.500（召回全集对 gold） |
| q137 | intervention | sntJ0027 | sntJ0027,sntD0033,sntJ0018,sntJ0004,sntC0031 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q138 | intervention | SAFE | sntI0015,sntI0017,sntH0030,sntF0001,sntE0018 | gold=SAFE pred=WARNING (FP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q139 | intervention | sntC0006 | sntC0006,sntC0005,sntG0001,sntC0024,sntI0015 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q140 | intervention | SAFE | sntD0002,sntD0001,sntD0006,sntD0014,sntD0015 | gold=SAFE pred=WARNING (FP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q141 | intervention | sntF0003 | sntF0003,sntH0007,sntH0031,sntE0031,sntD0022 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q142 | intervention | sntH0003 | sntH0003,sntH0028,sntA0023,sntF0026,sntF0002 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q143 | intervention | SAFE | sntF0021,sntF0022,sntF0006,sntF0001,sntF0027 | gold=SAFE pred=WARNING (FP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q144 | intervention | sntG0030 | sntG0002,sntG0031,sntG0001,sntF0001,sntH0006 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q145 | intervention | SAFE | sntA0015,sntA0017,sntA0005,sntA0001,sntF0027 | gold=SAFE pred=WARNING (FP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q146 | intervention | SAFE | sntA0021,sntA0023,sntA0007,sntA0006,sntF0001 | gold=SAFE pred=SAFE (TN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q147 | intervention | sntA0019 | sntE0016,sntJ0023,sntH0007,sntE0019,sntD0022 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q148 | intervention | sntA0031 | sntE0016,sntJ0023,sntH0007,sntE0019,sntD0022 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q149 | intervention | sntE0007 | sntE0016,sntJ0023,sntH0007,sntE0019,sntD0022 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q150 | intervention | sntE0013 | sntE0016,sntJ0023,sntH0007,sntE0019,sntD0022 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q151 | intervention | sntH0016 | sntE0016,sntJ0023,sntH0007,sntE0019,sntD0022 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q152 | intervention | sntI0013 | sntE0016,sntJ0023,sntH0007,sntE0019,sntD0022 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q153 | intervention | sntJ0028 | sntE0016,sntJ0023,sntH0007,sntE0019,sntD0022 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q154 | intervention | SAFE | sntE0016,sntJ0023,sntH0007,sntE0019,sntD0022 | gold=SAFE pred=WARNING (FP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q155 | intervention | SAFE | sntE0016,sntJ0023,sntH0007,sntE0019,sntD0022 | gold=SAFE pred=WARNING (FP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q156 | intervention | SAFE | sntE0016,sntJ0023,sntH0007,sntE0019,sntD0022 | gold=SAFE pred=WARNING (FP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q157 | intervention | SAFE | sntE0016,sntJ0023,sntH0007,sntE0019,sntD0022 | gold=SAFE pred=WARNING (FP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q158 | intervention | sntD0020 | sntJ0023,sntE0017,sntJ0008,sntJ0017,sntH0017 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q159 | intervention | sntE0020 | sntJ0023,sntE0017,sntJ0008,sntJ0017,sntH0017 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q160 | intervention | sntH0023 | sntJ0023,sntE0017,sntJ0008,sntJ0017,sntH0017 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q161 | intervention | sntJ0011 | sntJ0023,sntE0017,sntJ0008,sntJ0017,sntH0017 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q162 | intervention | SAFE | sntJ0023,sntE0017,sntJ0008,sntJ0017,sntH0017 | gold=SAFE pred=WARNING (FP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q163 | intervention | SAFE | sntJ0023,sntE0017,sntJ0008,sntJ0017,sntH0017 | gold=SAFE pred=WARNING (FP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q164 | intervention | SAFE | sntJ0023,sntE0017,sntJ0008,sntJ0017,sntH0017 | gold=SAFE pred=WARNING (FP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q165 | intervention | SAFE | sntJ0023,sntE0017,sntJ0008,sntJ0017,sntH0017 | gold=SAFE pred=WARNING (FP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q166 | intervention | SAFE | sntD0015,sntD0016,sntD0013,sntE0017,sntA0001 | gold=SAFE pred=SAFE (TN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q167 | intervention | SAFE | sntC0016,sntC0018,sntC0010,sntH0015,sntG0001 | gold=SAFE pred=WARNING (FP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q168 | intervention | sntB0027 | sntB0027,sntB0029,sntB0001,sntA0006,sntB0018 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q169 | intervention | sntJ0001 | sntJ0001,sntJ0032,sntJ0030,sntJ0002,sntJ0004 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q170 | intervention | SAFE | sntG0018,sntG0019,sntI0021,sntA0018,sntI0024 | gold=SAFE pred=WARNING (FP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q171 | intervention | sntB0024 | sntB0024,sntB0003,sntB0006,sntB0004,sntB0008 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q172 | intervention | SAFE | sntF0015,sntF0016,sntD0033,sntF0012,sntF0014 | gold=SAFE pred=SAFE (TN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q173 | intervention | SAFE | sntE0015,sntE0017,sntJ0022,sntJ0004,sntF0001 | gold=SAFE pred=WARNING (FP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q174 | intervention | SAFE | sntF0018,sntF0009,sntF0019,sntF0010,sntD0027 | gold=SAFE pred=WARNING (FP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q175 | intervention | sntH0024 | sntH0024,sntH0025,sntH0001,sntH0019,sntH0006 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q176 | intervention | SAFE | sntH0018,sntH0019,sntH0001,sntH0007,sntB0001 | gold=SAFE pred=SAFE (TN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q177 | supersession | sntH0033 | sntH0001,sntH0015,sntD0010,sntH0003,sntD0009 | gold 当前结论=sntH0033 旧结论=sntH0001; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q178 | supersession | sntD0019 | sntD0002,sntD0004,sntG0005,sntD0001,sntD0021 | gold 当前结论=sntD0019 旧结论=sntD0002; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q179 | supersession | sntI0033 | sntI0001,sntI0031,sntI0002,sntI0024,sntI0026 | gold 当前结论=sntI0033 旧结论=sntI0001; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q180 | supersession | sntF0033 | sntF0001,sntF0026,sntB0015,sntF0009,sntF0003 | gold 当前结论=sntF0033 旧结论=sntF0001; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q181 | supersession | sntD0033 | sntD0001,sntD0004,sntD0002,sntG0005,sntD0003 | gold 当前结论=sntD0033 旧结论=sntD0001; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q182 | supersession | sntA0034 | sntA0001,sntA0009,sntA0003,sntE0001,sntI0003 | gold 当前结论=sntA0034 旧结论=sntA0001; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q183 | supersession | sntF0022 | sntF0002,sntF0030,sntF0031,sntF0014,sntJ0014 | gold 当前结论=sntF0022 旧结论=sntF0002; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q184 | supersession | sntI0015 | sntI0002,sntI0024,sntI0026,sntI0004,sntD0033 | gold 当前结论=sntI0015 旧结论=sntI0002; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q185 | supersession | sntC0019 | sntC0002,sntC0033,sntC0001,sntB0001,sntC0003 | gold 当前结论=sntC0019 旧结论=sntC0002; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q186 | supersession | sntJ0018 | sntJ0002,sntJ0032,sntJ0003,sntJ0017,sntE0017 | gold 当前结论=sntJ0018 旧结论=sntJ0002; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q187 | supersession | sntE0021 | sntE0002,sntE0001,sntE0024,sntJ0003,sntI0003 | gold 当前结论=sntE0021 旧结论=sntE0002; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q188 | supersession | sntE0033 | sntE0001,sntE0002,sntC0003,sntJ0003,sntA0001 | gold 当前结论=sntE0033 旧结论=sntE0001; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q189 | supersession | sntJ0033 | sntJ0001,sntJ0030,sntJ0003,sntJ0032,sntI0021 | gold 当前结论=sntJ0033 旧结论=sntJ0001; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q190 | supersession | sntG0022 | sntG0002,sntG0032,sntG0001,sntG0003,sntG0004 | gold 当前结论=sntG0022 旧结论=sntG0002; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q191 | supersession | sntC0034 | sntC0001,sntC0002,sntC0032,sntC0003,sntB0001 | gold 当前结论=sntC0034 旧结论=sntC0001; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q192 | supersession | sntH0015 | sntH0002,sntH0024,sntC0003,sntA0001,sntB0002 | gold 当前结论=sntH0015 旧结论=sntH0002; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q193 | supersession | sntA0033 | sntA0002,sntA0016,sntA0015,sntC0005,sntI0003 | gold 当前结论=sntA0033 旧结论=sntA0002; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q194 | supersession | sntG0033 | sntG0001,sntC0005,sntC0022,sntH0001,sntA0026 | gold 当前结论=sntG0033 旧结论=sntG0001; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q195 | supersession | sntB0018 | sntB0002,sntB0030,sntB0001,sntB0031,sntI0003 | gold 当前结论=sntB0018 旧结论=sntB0002; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q196 | supersession | sntB0033 | sntB0001,sntB0031,sntB0002,sntB0030,sntC0003 | gold 当前结论=sntB0033 旧结论=sntB0001; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q197 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q198 | negative | ∅ | sntJ0017 | gold 恒空；召回 1 条 → noisy=True |
| q199 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q200 | negative | ∅ | sntH0004 | gold 恒空；召回 1 条 → noisy=True |
| q201 | negative | ∅ | sntF0005 | gold 恒空；召回 1 条 → noisy=True |
| q202 | negative | ∅ | sntE0021,sntG0022,sntG0023,sntG0021 | gold 恒空；召回 4 条 → noisy=True |
| q203 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q204 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q205 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q206 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q207 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q208 | negative | ∅ | sntA0005,sntI0018,sntI0006,sntA0015,sntE0021 | gold 恒空；召回 5 条 → noisy=True |
| q209 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q210 | negative | ∅ | sntD0018,sntD0019,sntE0017,sntI0018,sntI0020 | gold 恒空；召回 5 条 → noisy=True |
| q211 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q212 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q213 | negative | ∅ | sntB0024,sntB0004 | gold 恒空；召回 2 条 → noisy=True |
| q214 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q215 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q216 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q217 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q218 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q219 | negative | ∅ | sntA0015,sntB0021 | gold 恒空；召回 2 条 → noisy=True |
| q220 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q221 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q222 | negative | ∅ | sntE0020,sntG0022,sntG0023,sntG0021,sntE0018 | gold 恒空；召回 5 条 → noisy=True |
| q223 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q224 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q225 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q226 | negative | ∅ | sntA0015 | gold 恒空；召回 1 条 → noisy=True |
| q227 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q228 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q229 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q230 | negative | ∅ | sntE0020,sntE0019,sntI0017,sntI0016 | gold 恒空；召回 4 条 → noisy=True |
| q231 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q232 | negative | ∅ | sntE0004,sntG0004 | gold 恒空；召回 2 条 → noisy=True |
| q233 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q234 | negative | ∅ | sntB0029,sntB0028,sntH0004 | gold 恒空；召回 3 条 → noisy=True |
| q235 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q236 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
（共 236 题，全部列出）


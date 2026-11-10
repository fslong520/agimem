# agimem 指标面板

> **本臂：隔离库真跑（合成因果树 143 节点真在库内，m3 向量检索；独立 data dir / 端口 16301 / super，未碰 ~/.rsrs）。**
>
> **醒目声明：被测隔离库已写入合成因果树（143 节点），下表是该记忆系统在本语料上的检索层真能力分；但语料全合成、gold 由树结构机械推导、且 supersession 为 oracle 口径，外推到真实业务需另证。**

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
| `chain_hit@5` | 0.4706 | 0.471 [0.357, 0.588] | 68 | 越高越好 |
| `chain_hit@1` | 0.0000 | 0.000 [0.000, 0.053] | 68 | 越高越好 |
| `chain_cov` | 0.1152 | 0.115 [0.080, 0.150] | 68 | 越高越好 |
| `intervention_acc` | 0.8000 | 0.800 [0.584, 0.919] | 20 | 越高越好 |
| `false_alarm_rate` | 0.4000 | 0.400 [0.168, 0.687] | 10 | 越低越好 |
| `supersession_acc` | 0.1000 | 0.100 [0.018, 0.404] | 10 | 越高越好 |
| `negative_noise_rate` | 0.2500 | 0.250 [0.120, 0.449] | 24 | 越低越好 |

干预混淆矩阵 TP/FP/FN/TN = 10/4/0/6（WARNING n=10，SAFE n=10）；取代 current/stale/missing = 1/9/0。

## 三、基线对照（合成 recall 臂，非真库）

| 指标 | 本臂 | perfect | adversarial |
|---|---:|---:|---:|
| `chain_hit@k` | 0.471 | 1.000 | 0.000 |
| `chain_cov` | 0.115 | 1.000 | 0.000 |
| `intervention_acc` | 0.800 | 1.000 | 0.000 |
| `false_alarm_rate` | 0.400 | 0.000 | 1.000 |
| `supersession_acc` | 0.100 | 1.000 | 0.000 |
| `negative_noise_rate` | 0.250 | 0.000 | 1.000 |

perfect/adversarial 由 `selftest.py` 生成的合成 fixture 判出，只证明判分器两极正确，不代表任何真实系统水平。

## 四、单题明细下钻（qid → gold → top-k → 判分理由）

| qid | 题型 | gold | top-k 召回 | 判分理由 |
|---|---|---|---|---|
| q001 | chain_ancestor | sntJ0003,sntJ0002,sntJ0001 | sntJ0013,sntJ0009,sntB0011,sntB0001,sntF0005 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q002 | chain_ancestor | sntE0005,sntE0004,sntE0003,sntE0002,sntE0001 | sntE0013,sntE0003,sntF0014,sntE0014,sntH0007 | gold 链长 5; top-5 内首个 gold rank=1; 覆盖率=0.200（召回全集对 gold） |
| q003 | chain_ancestor | sntF0004,sntF0003,sntF0002,sntF0001 | sntF0012,sntF0001,sntF0013,sntH0006,sntG0013 | gold 链长 4; top-5 内首个 gold rank=1; 覆盖率=0.250（召回全集对 gold） |
| q004 | chain_ancestor | sntC0005,sntC0004,sntC0003,sntC0002,sntC0001 | sntC0011,sntC0008,sntJ0011,sntH0010,sntD0010 | gold 链长 5; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q005 | chain_ancestor | sntC0004,sntC0003,sntC0002,sntC0001 | sntC0008,sntC0011,sntJ0006,sntB0011,sntG0007 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q006 | chain_ancestor | sntG0005,sntG0004,sntG0003,sntG0002,sntG0001 | sntG0008,sntG0009,sntG0004,sntH0010,sntA0009 | gold 链长 5; top-5 内首个 gold rank=2; 覆盖率=0.200（召回全集对 gold） |
| q007 | chain_ancestor | sntB0004,sntB0003,sntB0002,sntB0001 | sntB0013,sntB0011,sntA0003,sntB0001,sntC0005 | gold 链长 4; top-5 内首个 gold rank=3; 覆盖率=0.250（召回全集对 gold） |
| q008 | chain_ancestor | sntF0003,sntF0002,sntF0001 | sntF0007,sntF0009,sntA0003,sntB0011,sntF0006 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q009 | chain_ancestor | sntC0006,sntC0005,sntC0004,sntC0003,sntC0002,sntC0001 | sntC0014,sntG0014,sntH0010,sntH0008,sntG0007 | gold 链长 6; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q010 | chain_ancestor | sntC0004,sntC0003,sntC0002,sntC0001 | sntC0012,sntC0009,sntH0010,sntA0012,sntF0003 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q011 | chain_ancestor | sntD0004,sntD0003,sntD0002,sntD0001 | sntI0015,sntD0009,sntD0008,sntD0006,sntB0012 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q012 | chain_ancestor | sntJ0004,sntJ0003,sntJ0002,sntJ0001 | sntJ0011,sntJ0008,sntF0005,sntH0010,sntE0007 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q013 | chain_ancestor | sntB0003,sntB0002,sntB0001 | sntB0006,sntB0010,sntA0008,sntB0002,sntH0001 | gold 链长 3; top-5 内首个 gold rank=3; 覆盖率=0.333（召回全集对 gold） |
| q014 | chain_ancestor | sntJ0004,sntJ0003,sntJ0002,sntJ0001 | sntJ0007,sntJ0010,sntH0010,sntD0006,sntB0005 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q015 | chain_ancestor | sntI0005,sntI0004,sntI0003,sntI0002,sntI0001 | sntI0012,sntI0004,sntI0014,sntI0007,sntB0011 | gold 链长 5; top-5 内首个 gold rank=1; 覆盖率=0.200（召回全集对 gold） |
| q016 | chain_ancestor | sntI0005,sntI0004,sntI0003,sntI0002,sntI0001 | sntI0006,sntI0010,sntB0011,sntI0009,sntA0006 | gold 链长 5; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q017 | chain_ancestor | sntI0003,sntI0002,sntI0001 | sntI0014,sntI0002,sntI0001,sntI0006,sntF0006 | gold 链长 3; top-5 内首个 gold rank=1; 覆盖率=0.667（召回全集对 gold） |
| q018 | chain_ancestor | sntA0003,sntA0002,sntA0001 | sntA0012,sntB0012,sntG0002,sntB0007,sntH0010 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q019 | chain_ancestor | sntE0003,sntE0002,sntE0001 | sntE0004,sntC0005,sntI0015,sntF0003,sntH0010 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q020 | chain_ancestor | sntE0003,sntE0002,sntE0001 | sntE0006,sntE0011,sntJ0006,sntF0002,sntE0010 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q021 | chain_ancestor | sntF0004,sntF0003,sntF0002,sntF0001 | sntF0008,sntF0011,sntI0010,sntH0010,sntB0011 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q022 | chain_ancestor | sntA0003,sntA0002,sntA0001 | sntA0006,sntA0011,sntA0005,sntA0003,sntI0006 | gold 链长 3; top-5 内首个 gold rank=3; 覆盖率=0.333（召回全集对 gold） |
| q023 | chain_ancestor | sntG0004,sntG0003,sntG0002,sntG0001 | sntG0007,sntH0008,sntG0014,sntG0002,sntG0003 | gold 链长 4; top-5 内首个 gold rank=3; 覆盖率=0.500（召回全集对 gold） |
| q024 | chain_ancestor | sntB0004,sntB0003,sntB0002,sntB0001 | sntB0005,sntB0009,sntA0003,sntH0004,sntB0007 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q025 | chain_ancestor | sntC0005,sntC0004,sntC0003,sntC0002,sntC0001 | sntC0007,sntC0010,sntG0012,sntG0001,sntG0004 | gold 链长 5; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q026 | chain_ancestor | sntA0004,sntA0003,sntA0002,sntA0001 | sntA0005,sntA0009,sntA0003,sntA0006,sntE0014 | gold 链长 4; top-5 内首个 gold rank=2; 覆盖率=0.250（召回全集对 gold） |
| q027 | chain_ancestor | sntJ0003,sntJ0002,sntJ0001 | sntJ0009,sntJ0013,sntI0015,sntF0005,sntH0009 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q028 | chain_ancestor | sntJ0004,sntJ0003,sntJ0002,sntJ0001 | sntJ0005,sntD0003,sntH0010,sntC0001,sntB0011 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q029 | chain_ancestor | sntH0005,sntH0004,sntH0003,sntH0002,sntH0001 | sntH0006,sntH0011,sntC0010,sntC0007,sntB0007 | gold 链长 5; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q030 | chain_ancestor | sntH0004,sntH0003,sntH0002,sntH0001 | sntH0011,sntH0006,sntH0010,sntB0012,sntC0004 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q031 | chain_ancestor | sntE0005,sntE0004,sntE0003,sntE0002,sntE0001 | sntE0007,sntE0010,sntE0012,sntE0003,sntA0009 | gold 链长 5; top-5 内首个 gold rank=3; 覆盖率=0.200（召回全集对 gold） |
| q032 | chain_ancestor | sntA0005,sntA0004,sntA0003,sntA0002,sntA0001 | sntA0008,sntA0001,sntB0010,sntF0003,sntF0005 | gold 链长 5; top-5 内首个 gold rank=1; 覆盖率=0.200（召回全集对 gold） |
| q033 | chain_ancestor | sntD0004,sntD0003,sntD0002,sntD0001 | sntD0013,sntD0011,sntD0007,sntH0014,sntA0003 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q034 | chain_ancestor | sntG0005,sntG0004,sntG0003,sntG0002,sntG0001 | sntG0012,sntC0007,sntI0007,sntG0004,sntA0012 | gold 链长 5; top-5 内首个 gold rank=3; 覆盖率=0.200（召回全集对 gold） |
| q035 | chain_descendant | sntH0006,sntH0010,sntH0014 | sntH0005,sntH0013,sntD0005,sntB0002,sntC0015 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q036 | chain_descendant | sntH0002,sntH0003,sntH0004,sntH0005,sntH0006,sntH0007,sntH0008,sntH0009,sntH0010,sntH0011,sntH0012,sntH0013,sntH0014 | sntH0001,sntH0009,sntH0010,sntH0007,sntH0014 | gold 链长 13; top-5 内首个 gold rank=1; 覆盖率=0.308（召回全集对 gold） |
| q037 | chain_descendant | sntF0005,sntF0008,sntF0012 | sntF0004,sntF0005,sntF0003,sntE0003,sntH0008 | gold 链长 3; top-5 内首个 gold rank=1; 覆盖率=0.333（召回全集对 gold） |
| q038 | chain_descendant | sntB0004,sntB0005,sntB0006,sntB0009,sntB0010,sntB0013,sntB0014 | sntB0003,sntB0014,sntB0004,sntB0007,sntD0003 | gold 链长 7; top-5 内首个 gold rank=1; 覆盖率=0.286（召回全集对 gold） |
| q039 | chain_descendant | sntF0002,sntF0003,sntF0004,sntF0005,sntF0006,sntF0007,sntF0008,sntF0009,sntF0010,sntF0011,sntF0012,sntF0013,sntF0014 | sntF0001,sntF0012,sntB0011,sntB0009,sntF0007 | gold 链长 13; top-5 内首个 gold rank=1; 覆盖率=0.154（召回全集对 gold） |
| q040 | chain_descendant | sntC0006,sntC0007,sntC0010,sntC0011,sntC0014,sntC0015 | sntC0005,sntE0004,sntC0004,sntI0003,sntG0004 | gold 链长 6; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q041 | chain_descendant | sntD0008,sntD0012 | sntD0005,sntD0014,sntC0006,sntH0005,sntD0009 | gold 链长 2; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q042 | chain_descendant | sntG0004,sntG0005,sntG0007,sntG0008,sntG0009,sntG0011,sntG0012,sntG0013 | sntG0003,sntF0003,sntC0005,sntI0015,sntH0003 | gold 链长 8; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q043 | chain_descendant | sntH0005,sntH0006,sntH0007,sntH0010,sntH0011,sntH0014 | sntH0004,sntI0003,sntH0005,sntG0004,sntC0014 | gold 链长 6; top-5 内首个 gold rank=2; 覆盖率=0.167（召回全集对 gold） |
| q044 | chain_descendant | sntJ0005,sntJ0007,sntJ0011 | sntJ0004,sntJ0007,sntE0003,sntE0010,sntB0011 | gold 链长 3; top-5 内首个 gold rank=1; 覆盖率=0.333（召回全集对 gold） |
| q045 | chain_descendant | sntI0004,sntI0005,sntI0006,sntI0008,sntI0010,sntI0012,sntI0014 | sntI0003,sntC0012,sntD0004,sntE0004,sntF0003 | gold 链长 7; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q046 | chain_descendant | sntD0002,sntD0003,sntD0004,sntD0005,sntD0006,sntD0007,sntD0008,sntD0009,sntD0010,sntD0011,sntD0012,sntD0013,sntD0014 | sntD0001,sntD0002,sntD0003,sntG0005,sntB0012 | gold 链长 13; top-5 内首个 gold rank=1; 覆盖率=0.154（召回全集对 gold） |
| q047 | chain_descendant | sntA0002,sntA0003,sntA0004,sntA0005,sntA0006,sntA0007,sntA0008,sntA0009,sntA0010,sntA0011,sntA0012,sntA0013,sntA0014,sntA0015 | sntA0001,sntA0008,sntB0011,sntA0014,sntC0014 | gold 链长 14; top-5 内首个 gold rank=1; 覆盖率=0.143（召回全集对 gold） |
| q048 | chain_descendant | sntI0006,sntI0012 | sntI0005,sntD0009,sntH0007,sntC0012,sntD0005 | gold 链长 2; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q049 | chain_descendant | sntI0005,sntI0006,sntI0010,sntI0012 | sntI0004,sntI0014,sntI0002,sntA0014,sntC0014 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q050 | chain_descendant | sntH0004,sntH0005,sntH0006,sntH0007,sntH0010,sntH0011,sntH0014 | sntH0003,sntH0005,sntH0014,sntH0007,sntE0004 | gold 链长 7; top-5 内首个 gold rank=1; 覆盖率=0.429（召回全集对 gold） |
| q051 | chain_descendant | sntC0003,sntC0004,sntC0005,sntC0006,sntC0007,sntC0008,sntC0009,sntC0010,sntC0011,sntC0012,sntC0013,sntC0014,sntC0015 | sntC0002,sntC0001,sntI0014,sntB0013,sntB0001 | gold 链长 13; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q052 | chain_descendant | sntG0005,sntG0007,sntG0008,sntG0011,sntG0012 | sntG0004,sntE0004,sntG0009,sntE0003,sntE0010 | gold 链长 5; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q053 | chain_descendant | sntD0005,sntD0008,sntD0009,sntD0012,sntD0013 | sntD0004,sntF0003,sntI0015,sntD0006,sntD0009 | gold 链长 5; top-5 内首个 gold rank=4; 覆盖率=0.200（召回全集对 gold） |
| q054 | chain_descendant | sntD0004,sntD0005,sntD0008,sntD0009,sntD0012,sntD0013 | sntD0003,sntB0008,sntH0007,sntA0004,sntG0001 | gold 链长 6; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q055 | chain_descendant | sntE0002,sntE0003,sntE0004,sntE0005,sntE0006,sntE0007,sntE0008,sntE0009,sntE0010,sntE0011,sntE0012,sntE0013,sntE0014 | sntE0001,sntE0002,sntE0003,sntE0012,sntC0003 | gold 链长 13; top-5 内首个 gold rank=1; 覆盖率=0.231（召回全集对 gold） |
| q056 | chain_descendant | sntE0004,sntE0005,sntE0006,sntE0007,sntE0010,sntE0012,sntE0013 | sntE0003,sntE0013,sntG0004,sntI0011,sntE0014 | gold 链长 7; top-5 内首个 gold rank=1; 覆盖率=0.143（召回全集对 gold） |
| q057 | chain_descendant | sntJ0002,sntJ0003,sntJ0004,sntJ0005,sntJ0006,sntJ0007,sntJ0008,sntJ0009,sntJ0010,sntJ0011,sntJ0012,sntJ0013,sntJ0014 | sntJ0001,sntJ0014,sntI0006,sntB0011,sntJ0009 | gold 链长 13; top-5 内首个 gold rank=1; 覆盖率=0.154（召回全集对 gold） |
| q058 | chain_descendant | sntA0005,sntA0008,sntA0010,sntA0014 | sntA0004,sntA0013,sntH0007,sntC0014,sntA0012 | gold 链长 4; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q059 | chain_descendant | sntE0007,sntE0013 | sntE0005,sntH0013,sntH0007,sntH0012,sntB0009 | gold 链长 2; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q060 | chain_descendant | sntB0005,sntB0009,sntB0013 | sntB0004,sntB0007,sntB0014,sntB0003,sntB0002 | gold 链长 3; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q061 | chain_descendant | sntG0008,sntG0012 | sntG0005,sntD0001,sntB0012,sntD0002,sntG0001 | gold 链长 2; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q062 | chain_descendant | sntC0002,sntC0003,sntC0004,sntC0005,sntC0006,sntC0007,sntC0008,sntC0009,sntC0010,sntC0011,sntC0012,sntC0013,sntC0014,sntC0015 | sntC0001,sntC0002,sntC0009,sntC0014,sntB0008 | gold 链长 14; top-5 内首个 gold rank=1; 覆盖率=0.214（召回全集对 gold） |
| q063 | chain_descendant | sntJ0004,sntJ0005,sntJ0007,sntJ0009,sntJ0011,sntJ0013 | sntJ0003,sntF0003,sntB0011,sntH0003,sntE0009 | gold 链长 6; top-5 内首个 gold rank=None; 覆盖率=0.000（召回全集对 gold） |
| q064 | chain_descendant | sntA0004,sntA0005,sntA0006,sntA0008,sntA0010,sntA0012,sntA0014 | sntA0003,sntA0014,sntA0001,sntB0011,sntA0009 | gold 链长 7; top-5 内首个 gold rank=1; 覆盖率=0.143（召回全集对 gold） |
| q065 | chain_descendant | sntF0004,sntF0005,sntF0007,sntF0008,sntF0011,sntF0012 | sntF0003,sntI0015,sntG0003,sntF0004,sntE0003 | gold 链长 6; top-5 内首个 gold rank=3; 覆盖率=0.167（召回全集对 gold） |
| q066 | chain_descendant | sntC0005,sntC0006,sntC0007,sntC0008,sntC0010,sntC0011,sntC0012,sntC0014,sntC0015 | sntC0004,sntC0005,sntC0003,sntE0004,sntG0003 | gold 链长 9; top-5 内首个 gold rank=1; 覆盖率=0.111（召回全集对 gold） |
| q067 | chain_descendant | sntG0002,sntG0003,sntG0004,sntG0005,sntG0006,sntG0007,sntG0008,sntG0009,sntG0010,sntG0011,sntG0012,sntG0013,sntG0014 | sntG0001,sntG0012,sntC0010,sntC0007,sntA0013 | gold 链长 13; top-5 内首个 gold rank=1; 覆盖率=0.077（召回全集对 gold） |
| q068 | chain_descendant | sntB0002,sntB0003,sntB0004,sntB0005,sntB0006,sntB0007,sntB0008,sntB0009,sntB0010,sntB0011,sntB0012,sntB0013,sntB0014 | sntB0001,sntB0002,sntB0012,sntB0011,sntB0005 | gold 链长 13; top-5 内首个 gold rank=1; 覆盖率=0.308（召回全集对 gold） |
| q069 | intervention | SAFE | sntI0009,sntI0008,sntJ0011,sntC0008,sntJ0004 | gold=SAFE pred=SAFE (TN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q070 | intervention | sntJ0013 | sntJ0013,sntI0015,sntJ0004,sntJ0009,sntE0003 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q071 | intervention | sntE0004 | sntC0004,sntE0004,sntC0003,sntC0005,sntH0013 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q072 | intervention | SAFE | sntB0010,sntB0006,sntA0008,sntB0002,sntB0011 | gold=SAFE pred=SAFE (TN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q073 | intervention | sntE0014 | sntE0014,sntB0001,sntE0003,sntG0003,sntJ0004 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q074 | intervention | sntA0012 | sntA0012,sntE0014,sntA0013,sntA0011,sntB0003 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q075 | intervention | sntH0013 | sntH0013,sntH0005,sntH0007,sntB0005,sntB0012 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q076 | intervention | SAFE | sntA0009,sntA0005,sntA0006,sntF0013,sntA0003 | gold=SAFE pred=WARNING (FP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q077 | intervention | SAFE | sntA0010,sntA0007,sntI0007,sntA0014,sntE0010 | gold=SAFE pred=WARNING (FP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q078 | intervention | SAFE | sntH0011,sntB0003,sntH0006,sntD0011,sntH0009 | gold=SAFE pred=SAFE (TN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q079 | intervention | sntB0001 | sntB0001,sntB0012,sntD0013,sntD0006,sntD0003 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q080 | intervention | sntI0012 | sntI0012,sntA0011,sntF0001,sntA0007,sntB0011 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q081 | intervention | sntB0014 | sntB0014,sntB0003,sntB0007,sntB0004,sntB0002 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q082 | intervention | sntC0015 | sntC0015,sntC0003,sntC0004,sntG0014,sntH0002 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q083 | intervention | SAFE | sntA0011,sntA0006,sntA0003,sntI0006,sntJ0004 | gold=SAFE pred=SAFE (TN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q084 | intervention | SAFE | sntB0009,sntF0001,sntF0011,sntC0011,sntJ0004 | gold=SAFE pred=SAFE (TN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q085 | intervention | SAFE | sntE0010,sntE0007,sntB0003,sntG0014,sntH0013 | gold=SAFE pred=WARNING (FP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q086 | intervention | sntA0002 | sntA0002,sntG0009,sntD0014,sntA0009,sntF0007 | gold=WARNING pred=WARNING (TP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q087 | intervention | SAFE | sntA0001,sntA0008,sntA0011,sntE0010,sntI0015 | gold=SAFE pred=SAFE (TN); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q088 | intervention | SAFE | sntH0010,sntH0007,sntH0012,sntH0013,sntH0001 | gold=SAFE pred=WARNING (FP); 判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id |
| q089 | supersession | sntD0011 | sntD0002,sntD0004,sntG0005,sntD0009,sntD0001 | gold 当前结论=sntD0011 旧结论=sntD0002; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q090 | supersession | sntF0011 | sntF0002,sntF0014,sntI0015,sntE0010,sntF0003 | gold 当前结论=sntF0011 旧结论=sntF0002; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q091 | supersession | sntI0015 | sntI0002,sntI0014,sntI0004,sntI0015,sntI0003 | gold 当前结论=sntI0015 旧结论=sntI0002; status=current；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q092 | supersession | sntC0011 | sntC0003,sntC0015,sntC0005,sntC0004,sntG0004 | gold 当前结论=sntC0011 旧结论=sntC0003; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q093 | supersession | sntJ0009 | sntJ0002,sntJ0003,sntJ0012,sntC0002,sntH0003 | gold 当前结论=sntJ0009 旧结论=sntJ0002; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q094 | supersession | sntE0010 | sntE0002,sntE0001,sntE0012,sntJ0003,sntI0003 | gold 当前结论=sntE0010 旧结论=sntE0002; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q095 | supersession | sntG0009 | sntG0002,sntG0003,sntG0001,sntG0004,sntI0015 | gold 当前结论=sntG0009 旧结论=sntG0002; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q096 | supersession | sntH0009 | sntH0002,sntH0012,sntC0003,sntC0005,sntH0003 | gold 当前结论=sntH0009 旧结论=sntH0002; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q097 | supersession | sntA0015 | sntA0002,sntC0005,sntA0009,sntI0003,sntE0004 | gold 当前结论=sntA0015 旧结论=sntA0002; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q098 | supersession | sntB0009 | sntB0002,sntB0012,sntB0001,sntI0003,sntC0003 | gold 当前结论=sntB0009 旧结论=sntB0002; status=stale；current 条件：召回含当前结论，或旧结论带 superseded_by 标记 |
| q099 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q100 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q101 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q102 | negative | ∅ | sntF0005 | gold 恒空；召回 1 条 → noisy=True |
| q103 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q104 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q105 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q106 | negative | ∅ | sntA0005,sntI0008,sntE0011,sntA0009,sntI0009 | gold 恒空；召回 5 条 → noisy=True |
| q107 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q108 | negative | ∅ | sntD0011,sntE0009,sntI0009,sntI0008,sntJ0011 | gold 恒空；召回 5 条 → noisy=True |
| q109 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q110 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q111 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q112 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q113 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q114 | negative | ∅ | sntA0009,sntB0010 | gold 恒空；召回 2 条 → noisy=True |
| q115 | negative | ∅ | sntG0009 | gold 恒空；召回 1 条 → noisy=True |
| q116 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q117 | negative | ∅ | sntA0009 | gold 恒空；召回 1 条 → noisy=True |
| q118 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q119 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q120 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q121 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
| q122 | negative | ∅ | ∅ | gold 恒空；召回 0 条 → noisy=False |
（共 122 题，全部列出）


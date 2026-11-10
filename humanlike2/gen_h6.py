#!/usr/bin/env python3
"""gen_h6.py — H6「人 vs 数据库：六道分水岭」：确定性 seed 生成语料与评测集，gold 机械推导。

用法：
    python3 gen_h6.py                 # 写 data/h6_tree.json + dataset/h6_evalset.jsonl
    python3 gen_h6.py --verify        # 重生成与既有文件比对（确定性证明）
    python3 gen_h6.py --per-type 24   # 每类题量（缺省 24，6 类共 144）

六类（判据：数据库天然做不到、人类天然做得到）：
  P1 前瞻记忆    条件式意图：题面只给触发证据，gold=该触发条件的意图条目。
  P2 错误记忆    诱饵：问从未写过的属性。gold 为空；另有同实体的真题作可分离性对照。
  P3 主动遗忘    三条相邻事实，中间一条标 forget_target；遗忘前后各一题。
  P4 来源监控    同主题四来源各说不同结论；问「谁说过 X」与「某来源说的是什么」。
  P5 时间线重建  四事件正文各不相同，created_at 与 insert_rank 十字交叉（四象限）。
  P6 重构性      一条含原因/动作/数值三要素，三档问句分层。

铁律守门（生成期强制，不是声明）：场景 ∈ 白名单、题面含该场景标志词、不命中禁题材词。
脱敏：全合成，无真人姓名（只用「同事甲/同事乙」）、无真库 id、无凭据。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
from typing import Any, Dict, List, Tuple

import h6_gold as hg
import scenarios as scn

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261109
PER_TYPE = 24
TREE_OUT = os.path.join(HERE, "data", "h6_tree.json")
EVALSET_OUT = os.path.join(HERE, "dataset", "h6_evalset.jsonl")

BANNED_SNIPPETS = ["sk-", "password", "口令", "api key", "密钥串", "赵", "钱", "孙"]
UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

# P5 四象限：同一主题四个事件，created_at 与 insert_rank 十字交叉。
# 正文各不相同，所以 import 不会因为同文去重（H3 K3 的死结只在逐字节相同时成立）。
#   I  早 created / 早插入     II 晚 created / 早插入
#   III 早 created / 晚插入    IV 晚 created / 晚插入
# created_at 顺序必须是 I < III < II < IV，这样「IV 的前驱」正好是 III，
# 而按插入顺序（I < II < III < IV）IV 的前驱是 II。比较这两格即可分离两个变量。
QUADRANT_SPEC = [
    ("I", "early", "early", "2026-03-04T02:00:00Z", 0),
    ("II", "late", "early", "2026-07-18T02:00:00Z", 1),
    ("III", "early", "late", "2026-05-12T02:00:00Z", 2),
    ("IV", "late", "late", "2026-09-28T02:00:00Z", 3),
]

P2_RECORDED_VALUES = {
    "镜像版本": ["v2.3.1", "v2.4.0", "v3.0.2", "v1.9.8"],
    "发布人": ["当班发布同学", "值班主管", "发布小组长", "值班同学"],
    "发布环境": ["预发", "生产", "沙箱", "正式"],
}
P2_TICKETS = ["发布单", "工单", "变更单", "回滚单"]

P6_ACTIONS = ["把超时从 1 秒调到", "把重试从 0 次调到", "把连接池上限从 50 调到",
              "把灰度比例从 5% 调到", "把分批大小从 1000 行调到", "把观察窗口从 5 分钟调到"]
P6_VALUES = ["3 秒", "2 次", "200", "10%", "5000 行", "15 分钟"]
P6_ASK = {
    "gist": "为什么要改这个参数",
    "action": "具体做了什么调整",
    "value": "最终调成了多少",
}


def _mark(sc: Dict[str, Any]) -> str:
    return sc["mark"][0]


def _iso_day(created_at: str) -> str:
    return created_at[:10]


# ---------------------------------------------------------------- P1 前瞻记忆

def build_p1(rng: random.Random, alloc: scn.Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """一题 = 一个意图节点 + 两条同形态不同触发的干扰意图。

    gold 由触发键机械推出：同场景里 trigger_key 唯一命中的那一条。
    题面只描述「现在触发条件成立了」，不把意图动作原文复述进去。
    """
    sc = scn.SCENARIOS[scenario]
    comp = sc["components"][idx % len(sc["components"])]
    env = sc["envs"][idx % len(sc["envs"])]
    mark = _mark(sc)
    gold_i = idx % len(scn.TRIGGERS)
    gold_key, gold_name = scn.TRIGGERS[gold_i]
    # 干扰取相邻两个触发，保证同一场景内 trigger_key 不撞
    distractors = [scn.TRIGGERS[(gold_i + d) % len(scn.TRIGGERS)] for d in (1, 2)]
    threshold = 1 + (idx % 4)  # 1..4
    actions = [
        f"立即回滚 {comp} 到上一个稳定版本",
        f"把 {comp} 的{mark}停在 {env}，先不放量",
        f"把 {comp} 的流量切回旧实例并通知当班",
    ]
    action = actions[idx % len(actions)]
    window = ["观察 15 分钟", "观察 30 分钟", "观察 24 小时"][idx % 3]

    nodes: List[Dict[str, Any]] = []
    gold_id = ""
    for j, (key, name) in enumerate([scn.TRIGGERS[gold_i]] + distractors):
        nid = alloc.node_id(scenario)
        is_gold = j == 0
        if is_gold:
            gold_id = nid
        thr = threshold if is_gold else threshold + 2 + j
        nodes.append(scn.node(
            scenario, nid,
            f"{comp}{mark}预案：{name}超过 {thr}% 就{action[:6]}",
            scn.tpl(
                f"{env} 的 {comp} 这次{mark}前约定了一条指向未来的条件",
                f"若 {name} 超过 {thr}%，{window}后仍未回落，则{action}",
                f"该条件未触发前不要提前执行，触发后按这条办",
            ),
            ts=f"2026-06-{(idx % 27) + 1:02d}",
            created_at=f"2026-06-{(idx % 27) + 1:02d}T09:00:00Z",
            insert_rank=idx * 10 + j,
            role="intent",
            topic=f"p1-{scenario}-{idx}",
            attrs={"trigger_key": key, "trigger_name": name, "threshold": thr,
                   "build": idx, "is_gold": is_gold},
        ))

    query = (f"{env}的 {comp} 这次{mark}，监控上 {gold_name} 已经到 {threshold + 0.2:.1f}% 了，"
             f"超过之前约定的线。按预先约定，现在该做什么？")
    q = {
        "type": "P1", "scenario": scenario, "query": query,
        "gold_expr": {"kind": "intent", "gold": gold_id, "trigger_key": gold_key,
                      "trigger_name": gold_name, "threshold": threshold, "build": idx},
        "expect": [gold_id],
        "note": "触发条件与 gold 意图匹配；同形态不同触发的意图是干扰",
    }
    return nodes, q


# ---------------------------------------------------------------- P2 错误记忆

def build_p2(rng: random.Random, alloc: scn.Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """一个实体记三个属性，另有三个属性从未写入。

    返回两题：
      lure     问从未写过的属性 → gold 为空（正确行为是「不知道」，不是硬凑一条）
      recorded 问真写过的属性 → gold=该实体（给可分离性 AUC 的真查询对照）
    诱饵属性名（镜像 tag / 构建号 / 回滚点编号）在全部语料里都不出现，
    verify_gold 会逐字符串扫全部正文来证明。
    """
    sc = scn.SCENARIOS[scenario]
    comp = sc["components"][idx % len(sc["components"])]
    mark = _mark(sc)
    ticket = P2_TICKETS[idx % len(P2_TICKETS)]
    nid = alloc.node_id(scenario)
    rec_attr = scn.RECORDED_ATTRS[idx % len(scn.RECORDED_ATTRS)]
    lure_attr = scn.NEVER_RECORDED_ATTRS[idx % len(scn.NEVER_RECORDED_ATTRS)]
    rec_val = P2_RECORDED_VALUES[rec_attr][idx % 4]
    # 另两个已记属性也写进正文，使诱饵题的实体本身高度相关
    extras = [a for a in scn.RECORDED_ATTRS if a != rec_attr]
    extra_bits = []
    for a in extras:
        extra_bits.append(f"{a}是 {P2_RECORDED_VALUES[a][(idx + 1) % 4]}")
    content = scn.tpl(
        f"{comp} 这次{mark}的 {ticket} 只登记了三项，其余没人记",
        f"记下来的是：{rec_attr}是 {rec_val}，" + "，".join(extra_bits),
        f"这张 {ticket} 没有别的字段，没写的就是没写",
    )
    node = scn.node(
        scenario, nid, f"{comp}{mark}{ticket}：只记了{rec_attr}等三项",
        content,
        ts=f"2026-07-{(idx % 27) + 1:02d}",
        created_at=f"2026-07-{(idx % 27) + 1:02d}T10:00:00Z",
        insert_rank=1000 + idx,
        role="entity",
        topic=f"p2-{scenario}-{idx}",
        attrs={"entity_name": f"{comp}{ticket}", "recorded": {rec_attr: rec_val},
               "lure_attr": lure_attr, "ticket": ticket},
    )
    lure_q = {
        "type": "P2", "scenario": scenario, "subtype": "lure",
        "query": (f"{comp} 那次{mark}的 {ticket} 里，当时用的{lure_attr}是哪个？"),
        "gold_expr": {"kind": "no_answer", "entity": nid, "entity_ids": [nid],
                      "attr": lure_attr, "expect_nonempty": False},
        "expect": [],
        "note": "该属性从未写入；正确行为是不把该实体当答案端出来",
    }
    rec_q = {
        "type": "P2", "scenario": scenario, "subtype": "recorded",
        "query": (f"{comp} 那次{mark}的 {ticket} 里，记下来的{rec_attr}是什么？"),
        "gold_expr": {"kind": "recorded", "gold": nid, "attr": rec_attr, "value": rec_val},
        "expect": [nid],
        "note": "真写过的属性，给诱饵查询做分数对照",
    }
    return [node], [lure_q, rec_q]


# ---------------------------------------------------------------- P3 主动遗忘

def build_p3(rng: random.Random, alloc: scn.Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """三条相邻事实 A/B/C，B 是遗忘目标。生成两题：

      pre  遗忘前问 B → 应命中（证明它确实写进去了）
      post 遗忘后问 B → 应不再命中；同时 A、C 必须仍能被同一查询的邻近检索命中
    遗忘动作本身不在生成期执行：运行期用 `rsrs forget <uuid>`（CLI 已有该命令）。
    若运行期证明遗忘不生效，报「无定向遗忘能力」而不是改 gold。
    """
    sc = scn.SCENARIOS[scenario]
    comp = sc["components"][idx % len(sc["components"])]
    env = sc["envs"][idx % len(sc["envs"])]
    mark = _mark(sc)
    topic = f"p3-{scenario}-{idx}"
    # T32 撤回：曾把「第 {idx} 批」编入正文想消同文，结果它在 A/B/C 三条里同样存在，
    # 是等量噪声稀释区分度 + A 比 B 短 10 字符 → 12/12 pre 题 top1 全 A、gold B 掉出。
    # 正文恢复自然文本（可检索）；同文改由**题面带组号**解决（见下方 query）。
    facts = [
        ("A", False, f"{comp} 在 {env} 的{mark}窗口定在周三凌晨"),
        ("B", True, f"{comp} 临时把{mark}窗口改到周五下午，之后说这事作废、不再作数"),
        ("C", False, f"{comp} 的{mark}回滚点仍是上一个稳定版本"),
    ]
    nodes: List[Dict[str, Any]] = []
    ids: Dict[str, str] = {}
    for j, (lab, target, fact) in enumerate(facts):
        nid = alloc.node_id(scenario)
        ids[lab] = nid
        nodes.append(scn.node(
            scenario, nid, f"{comp}{mark}记事 {lab}：{fact[:12]}",
            scn.tpl(f"{env} {comp} 的{mark}有三件相邻的事",
                    fact,
                    f"这是其中的第 {j + 1} 件，与另两件不要混"),
            ts=f"2026-05-{(idx % 27) + 1:02d}",
            created_at=f"2026-05-{(idx % 27) + 1:02d}T0{j + 1}:00:00Z",
            insert_rank=2000 + idx * 10 + j,
            role="forget",
            topic=topic,
            attrs={"label": lab, "forget_target": target, "fact": fact},
        ))
    keep = [ids["A"], ids["C"]]
    base = {"kind": "forget", "topic": topic, "gold": ids["B"], "keep": keep}
    # T32：题面带组号使其两两互异（定位唯一组），正文保持自然不带组号（可检索）。
    query = (f"第 {idx} 批：{env}的 {comp} 那次{mark}，"
             f"临时把窗口改到周五下午的那件事是怎么记的？")
    pre = {"type": "P3", "scenario": scenario, "subtype": "pre", "query": query,
           "gold_expr": dict(base, phase="pre"), "expect": [ids["B"]],
           "note": "遗忘前：目标应能被召回"}
    post = {"type": "P3", "scenario": scenario, "subtype": "post", "query": query,
            "gold_expr": dict(base, phase="post"), "expect": [],
            "note": "遗忘后：目标应消失；A/C 不得消失（collateral）"}
    return nodes, [pre, post]


# ---------------------------------------------------------------- P4 来源监控

def build_p4(rng: random.Random, alloc: scn.Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """同一个参数，四个来源各说一个不同的值。

    两种问法交替：
      who   「谁说过值是 X」→ gold=说出 X 的那个来源节点
      what  「某来源说的那个值是什么」→ gold=该来源的节点
    误归因 = top-1 落在同主题的其它来源上。
    """
    sc = scn.SCENARIOS[scenario]
    comp = sc["components"][idx % len(sc["components"])]
    mark = _mark(sc)
    param = sc["params"][idx % len(sc["params"])]
    topic = f"p4-{scenario}-{idx}"
    values = ["3 秒", "5 秒", "8 秒", "30 秒"]
    nodes: List[Dict[str, Any]] = []
    by_src: Dict[str, str] = {}
    for j, (src, cname) in enumerate(scn.SOURCES):
        nid = alloc.node_id(scenario)
        by_src[src] = nid
        val = values[j]
        nodes.append(scn.node(
            scenario, nid,
            f"{cname}对 {comp}{mark}的{param}说法：{val}",
            scn.tpl(f"{comp} 的{mark}里，{param}有四种不同来源的说法",
                    f"{cname}说 {param} 是 {val}",
                    f"这只代表 {cname} 的说法，不代表其他人"),
            ts=f"2026-04-{(idx % 27) + 1:02d}",
            created_at=f"2026-04-{(idx % 27) + 1:02d}T0{j + 1}:00:00Z",
            insert_rank=3000 + idx * 10 + j,
            role="source",
            topic=topic,
            attrs={"source": src, "source_name": cname, "param": param, "value": val},
        ))
    # 奇偶交替两种问法，使两种各占一半
    ask_src, ask_name = scn.SOURCES[idx % len(scn.SOURCES)]
    ask_val = values[idx % len(scn.SOURCES)]
    others = [by_src[s] for s, _ in scn.SOURCES if s != ask_src]
    # T32：题面带组号使其两两互异（跨 topic 同文 8 组 20 节点致 gold 排名不稳）；
    # 正文不动（同 topic 内 24/24 已互异，靠题面定位即可）。
    if idx % 2 == 0:
        query = (f"第 {idx} 批：{comp} 这次{mark}，谁说过 {param} 是 {ask_val}？")
        subtype = "who"
    else:
        query = (f"第 {idx} 批：{comp} 这次{mark}，{ask_name}说的那个 {param} 是多少？")
        subtype = "what"
    q = {
        "type": "P4", "scenario": scenario, "subtype": subtype, "query": query,
        "gold_expr": {"kind": "source", "topic": topic, "gold": by_src[ask_src],
                      "source": ask_src, "source_name": ask_name,
                      "other_sources": others, "value": ask_val, "param": param},
        "expect": [by_src[ask_src]],
        "note": "来源归因；同主题其它来源是误归因候选",
    }
    return nodes, [q]


# ---------------------------------------------------------------- P5 时间线重建

def build_p5(rng: random.Random, alloc: scn.Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """四个事件，正文各不相同，created_at 与插入顺序十字交叉。

    gold 按 created_at：
      earliest  问最早的一件 → 象限 I（早 created、早插入）
      before    问某事之前做了什么 → created_at 上的前驱
    `other` 记下「若按插入顺序会答错的那一条」，供运行期判断 top-1 跟的是哪个变量。
    插入顺序由 insert_rank 决定，采集时按它排序后再 import。
    """
    sc = scn.SCENARIOS[scenario]
    comp = sc["components"][idx % len(sc["components"])]
    env = sc["envs"][idx % len(sc["envs"])]
    mark = _mark(sc)
    topic = f"p5-{scenario}-{idx}"
    steps = [
        "先把旧实例摘掉流量",
        "再把配置中心切到新值",
        "然后逐台重启并等健康检查",
        "最后把流量切回来并对账",
    ]
    nodes: List[Dict[str, Any]] = []
    by_q: Dict[str, Dict[str, Any]] = {}
    for j, (quad, created_band, insert_band, created_at, rank) in enumerate(QUADRANT_SPEC):
        nid = alloc.node_id(scenario)
        fact = steps[j]
        n = scn.node(
            scenario, nid,
            f"{comp}{mark}第 {j + 1} 步（{quad}）：{fact}",
            scn.tpl(f"{env} {comp} 的{mark}按四步走，每一步都单独记了时间",
                    f"这一步是：{fact}",
                    f"发生日期是 {_iso_day(created_at)}，与另三步不在同一天"),
            ts=_iso_day(created_at),
            created_at=created_at,
            insert_rank=4000 + idx * 10 + rank,
            role="order",
            topic=topic,
            attrs={"quadrant": quad, "created_band": created_band,
                   "insert_band": insert_band, "step": fact, "step_no": j + 1},
        )
        nodes.append(n)
        by_q[quad] = n

    by_created = sorted(nodes, key=lambda n: n["created_at"])
    by_insert = sorted(nodes, key=lambda n: n["insert_rank"])
    # earliest：按 created_at 最早是 I；按插入最早也是 I（两者一致，作基线）
    # before 的锚点取 IV（最晚）：前驱按 created_at 是 III，按插入则是 II。
    #   II = 晚 created / 早插入；III = 早 created / 晚插入 —— 正是要分离的两格。
    earliest = {
        "type": "P5", "scenario": scenario, "subtype": "earliest", "quadrant_probe": "I",
        "query": (f"第 {idx} 批：{env}的 {comp} 这次{mark}，四步里哪一步最先发生？"),
        "gold_expr": {"kind": "order", "topic": topic, "mode": "earliest",
                      "gold": by_created[0]["id"], "other": by_insert[0]["id"],
                      "anchor": "", "quadrant_of_gold": by_created[0]["attrs"]["quadrant"]},
        "expect": [by_created[0]["id"]],
        "note": "问最早；此题 created_at 与插入顺序给出同一答案（象限 I）",
    }
    anchor = by_q["IV"]
    # gold 直接取 created_at 排序里 IV 的前一位，避免手算象限写错
    by_created_iv_prev = by_created[by_created.index(anchor) - 1]
    pred_created = by_created_iv_prev
    pred_insert = by_q["II"]
    insert_first = by_insert[0]
    # before 题面（T32 重设计）：旧「排在最后的那一步之前」语义仍指向锚点 IV，
    # 系统返回 IV 是正确理解题面 → 测不到时序（verdict 恒 neither）。
    # 改用「倒数第二步」直接指涉 gold（象限 III），使「向前一步」的推理真正被触发。
    # 断言：题面不得含「最后/IV/第 4 步」等直接指向锚点的词；不得含 step 原文连续 ≥3 字。
    before = {
        "type": "P5", "scenario": scenario, "subtype": "before", "quadrant_probe": "II-vs-III",
        "query": (f"第 {idx} 批：{env}的 {comp} 这次{mark}，四步里的倒数第二步之前，"
                  f"紧接着做的上一步是什么？"),
        "gold_expr": {"kind": "order", "topic": topic, "mode": "before",
                      "gold": pred_created["id"], "other": pred_insert["id"],
                      "anchor": anchor["id"],
                      "anchor_step": anchor["attrs"]["step"],
                      "quadrant_of_gold": "III", "quadrant_of_insert_answer": "II",
                      "insert_first": insert_first["id"]},
        "expect": [pred_created["id"]],
        "note": "gold=象限 III（早 created、晚插入）；题面不复述锚点 step 或标题字面"
                "（用「排在最后的那一步」指涉）；若 top-1=象限 II 则系统跟的是插入顺序",
    }
    return nodes, [earliest, before]


# ---------------------------------------------------------------- P6 重构性

def build_p6(rng: random.Random, alloc: scn.Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """一条含原因 + 动作 + 数值，加一条同主题但原因不同的干扰。

    三档问句各一题，都指向同一个 gold：
      gist   问为什么（要旨，不重复原因原文）
      action 问做了什么
      value  问调成多少（字面最强）
    类人系统三档都应能答；若只有数值档强，说明它只是字面检索。
    """
    sc = scn.SCENARIOS[scenario]
    comp = sc["components"][idx % len(sc["components"])]
    env = sc["envs"][idx % len(sc["envs"])]
    mark = _mark(sc)
    param = sc["params"][idx % len(sc["params"])]
    reason = scn.GIST_REASONS[idx % len(scn.GIST_REASONS)]
    other_reason = scn.GIST_REASONS[(idx + 3) % len(scn.GIST_REASONS)]
    action = P6_ACTIONS[idx % len(P6_ACTIONS)]
    value = P6_VALUES[idx % len(P6_VALUES)]
    topic = f"p6-{scenario}-{idx}"

    gold = scn.node(
        scenario, alloc.node_id(scenario),
        f"{comp}{mark}调整{param}：因为{reason[:8]}",
        scn.tpl(f"{env} {comp} 的{mark}里要改 {param}，原因是{reason}",
                f"做法是{action} {value}",
                f"改完后 {param} 的现值是 {value}"),
        ts=f"2026-08-{(idx % 27) + 1:02d}",
        created_at=f"2026-08-{(idx % 27) + 1:02d}T08:00:00Z",
        insert_rank=5000 + idx * 10,
        role="gist", topic=topic,
        attrs={"reason": reason, "action": action, "value": value, "param": param,
               "is_gold": True},
    )
    decoy = scn.node(
        scenario, alloc.node_id(scenario),
        f"{comp}{mark}另一次调{param}：因为{other_reason[:8]}",
        scn.tpl(f"同一个 {comp} 的{mark}，另有一次改 {param}，原因是{other_reason}",
                f"那次是把 {param} 先降一档再观察",
                f"那次没有把 {param} 定到 {value}"),
        ts=f"2026-02-{(idx % 27) + 1:02d}",
        created_at=f"2026-02-{(idx % 27) + 1:02d}T08:00:00Z",
        insert_rank=5000 + idx * 10 + 1,
        role="gist", topic=topic,
        attrs={"reason": other_reason, "param": param, "is_gold": False},
    )
    questions = []
    for subtype, ask in P6_ASK.items():
        questions.append({
            "type": "P6", "scenario": scenario, "subtype": subtype,
            "query": (f"{env}的 {comp} 这次{mark}，因为{reason}而改 {param} 的那一回，{ask}？"),
            "gold_expr": {"kind": "gist", "gold": gold["id"], "subtype": subtype,
                          "topic": topic, "decoy": decoy["id"],
                          "reason": reason, "action": action, "value": value},
            "expect": [gold["id"]],
            "note": f"{subtype} 档；同主题不同原因的条目是干扰",
        })
    return [gold, decoy], questions


BUILDERS = {
    "P1": build_p1,
    "P2": build_p2,
    "P3": build_p3,
    "P4": build_p4,
    "P5": build_p5,
    "P6": build_p6,
}


# ---------------------------------------------------------------- 组装

P6_PER_TYPE = 21  # 3 项/次构造，须整除（20%3≠0）；21≥20 才有可读 CI T32：P6 独立题量（≥20 才有可读 CI；原 8 的 CI [0.676,1.000] 太宽）


def build(seed: int = SEED, per_type: int = PER_TYPE,
          p6_per_type: int = P6_PER_TYPE) -> Dict[str, Any]:
    """per_type 是**每类题数**，不是每类构造次数。

    P1/P4 一次构造出 1 题；P2/P3/P5 出 2 题；P6 出 3 题。
    构造次数取 per_type 的整数倍，使每类刚好 per_type 题。
    """
    rng = random.Random(seed)
    alloc = scn.Alloc()
    nodes: List[Dict[str, Any]] = []
    questions: List[Dict[str, Any]] = []
    fanout = {"P1": 1, "P2": 2, "P3": 2, "P4": 1, "P5": 2, "P6": 3}
    for qtype in hg.TYPES:
        # T32：P6 拆独立题量参数（3 项/次构造），P1–P5 维持 per_type 不变。
        pt = p6_per_type if qtype == "P6" else per_type
        if pt % fanout[qtype] != 0:
            raise SystemExit(f"{qtype} 每次构造出 {fanout[qtype]} 题，"
                             f"pt={pt} 不能整除")
        n_build = pt // fanout[qtype]
        built = 0
        for i in range(n_build):
            scenario = scn.SCENARIO_KEYS[i % len(scn.SCENARIO_KEYS)]
            recs, qs = BUILDERS[qtype](rng, alloc, scenario, i + 1)
            nodes.extend(recs)
            got = qs if isinstance(qs, list) else [qs]
            for q in got:
                built += 1
                q["qid"] = f"{qtype.lower()}-{built:03d}"
                questions.append(q)
    tree = {
        "version": "1.0",
        "synthetic": True,
        "seed": seed,
        "generator": "gen_h6.py",
        "scenario_whitelist": [scn.SCENARIOS[k]["name"] for k in scn.SCENARIO_KEYS],
        "note": ("全合成脱敏的 H6 分水岭语料：仅用于 agimem 「人 vs 数据库」六类评测。"
                 "八个真实工作场景白名单。无真人姓名、无真库 id、无凭据。"
                 "P5 的 created_at 与 insert_rank 十字交叉，正文各不相同。"),
        "nodes": nodes,
    }
    return {"tree": tree, "questions": questions}


def sanity_checks(doc: Dict[str, Any], per_type: int,
                  p6_per_type: int = P6_PER_TYPE) -> None:
    tree = doc["tree"]
    questions = doc["questions"]
    nodes = tree["nodes"]
    by_id = {n["id"]: n for n in nodes}

    if len(questions) < 120:
        raise SystemExit(f"题量不足 120: {len(questions)}")
    for t in hg.TYPES:
        n = sum(1 for q in questions if q["type"] == t)
        want = p6_per_type if t == "P6" else per_type
        if n < 20 or n != want:
            raise SystemExit(f"{t} 题量应为 {want}（且 ≥20），实为 {n}")

    # T32 断言 A：题面两两互异，**唯 P3 的 pre/post 有意共用同一题面**
    # （同题面才能对比 forget 前后）；故按 (类型, 子型) 分桶查重复，
    # P3 则按 (类型, 题面) 桶内只允许 pre+post 一对。
    qseen: Dict[Tuple[str, str], str] = {}
    for q in questions:
        if q["type"] == "P3":
            key = ("P3", q["query"])       # pre/post 共用 → 同 query 视为一对，不重复
            if key in qseen and q["subtype"] == qseen[key]:
                raise SystemExit(f"P3 题面重复: {q['qid']} 与 {qseen[key]}")
            qseen.setdefault(key, q["subtype"])
        else:
            key = (q["type"], q["query"])
            if key in qseen:
                raise SystemExit(f"题面重复: {q['qid']} 与 {qseen[key]}")
            qseen[key] = q["qid"]

    # T32 断言 B：每个 topic 内正文互异（同文只允许跨 topic，跨 topic 由题面组号消解）
    by_topic: Dict[str, List[str]] = {}
    for n in nodes:
        by_topic.setdefault(n.get("topic", ""), []).append(n.get("content", ""))
    for t, cs in by_topic.items():
        if t and len(set(cs)) != len(cs):
            raise SystemExit(f"topic {t} 内正文同文 {len(cs) - len(set(cs))} 条")

    # 铁律三道：场景白名单、题面含场景标志词、不命中禁题材词
    for q in questions:
        key = q["scenario"]
        if key not in scn.SCENARIO_KEYS:
            raise SystemExit(f"{q['qid']}: 场景不在白名单 {key}")
        sc = scn.SCENARIOS[key]
        blob_q = q["query"]
        if not any(m in blob_q for m in sc["mark"]):
            raise SystemExit(f"{q['qid']}: 题面缺少场景标志词 {sc['mark']}: {blob_q[:48]}")
        for bad in scn.BANNED_TOPICS:
            if bad in blob_q:
                raise SystemExit(f"{q['qid']}: 题面命中被禁题材词 {bad!r}")

    # gold 可机械复算（与 h6_gold.verify_gold 同一实现）
    errs = hg.verify_gold(questions, nodes)
    if errs:
        raise SystemExit("gold 复算失败:\n  - " + "\n  - ".join(errs[:12]))

    # expect 与 gold_expr 一致：诱饵题与遗忘后题必须为空，其余必须指向树内唯一节点
    for q in questions:
        kind = q["gold_expr"]["kind"]
        phase = q["gold_expr"].get("phase")
        must_empty = kind == "no_answer" or (kind == "forget" and phase == "post")
        if must_empty:
            if q["expect"]:
                raise SystemExit(f"{q['qid']}: 该题 expect 必须为空")
        else:
            if q["expect"] != [q["gold_expr"]["gold"]]:
                raise SystemExit(f"{q['qid']}: expect 与 gold 不一致")
            if q["gold_expr"]["gold"] not in by_id:
                raise SystemExit(f"{q['qid']}: gold 不在树内")

    # P2 诱饵「确未写入」：属性名不得出现在任何正文、标题或题面以外的地方——这里再扫一遍全树
    corpus = "\n".join(n["title"] + "\n" + n["content"] for n in nodes)
    corpus_ns = corpus.replace(" ", "")
    for attr in scn.NEVER_RECORDED_ATTRS:
        if attr.replace(" ", "") in corpus_ns:
            raise SystemExit(f"诱饵属性 {attr!r} 出现在语料正文里，「确未写入」不成立")

    # P5 四象限：每组四个象限齐全，且 II 的插入早于 III、III 的 created_at 早于 II
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for n in nodes:
        if n["role"] == "order":
            groups.setdefault(n["topic"], []).append(n)
    for topic, g in groups.items():
        quads = {n["attrs"]["quadrant"] for n in g}
        if quads != {"I", "II", "III", "IV"}:
            raise SystemExit(f"{topic}: 四象限不齐 {quads}")
        ii = next(n for n in g if n["attrs"]["quadrant"] == "II")
        iii = next(n for n in g if n["attrs"]["quadrant"] == "III")
        if not (iii["created_at"] < ii["created_at"] and ii["insert_rank"] < iii["insert_rank"]):
            raise SystemExit(f"{topic}: II/III 没有十字交叉")
        bodies = [n["content"] for n in g]
        if len(set(bodies)) != 4:
            raise SystemExit(f"{topic}: 四事件正文不互异，会被 import 去重")

    # T28 缺陷一断言：before 题面不得含锚点 step 原文的任意连续 ≥3 字子串
    # （原题面用「{step}」引号复述，导致 top-1 必落锚点，0.042 是题面泄漏不是时序能力）
    # T30 口径判定：只比 anchor_step（锚点动作原文），不比完整 title——
    # title 含场景名前缀与「第 4 步（IV）」步序标签，题面必须指涉场景/步序
    # 否则成无锚查询；标签串是元数据不是动作原文，与 step LCS 为 0 才算无泄漏。
    by_topic_nodes: Dict[str, List[Dict[str, Any]]] = {}
    for n in nodes:
        if n["role"] == "order":
            by_topic_nodes.setdefault(n["topic"], []).append(n)
    for q in questions:
        if q["type"] != "P5" or q.get("subtype") != "before":
            continue
        e = q["gold_expr"]
        g = by_topic_nodes.get(e["topic"], [])
        anchor_n = next((n for n in g if n["id"] == e.get("anchor")), None)
        if anchor_n is None:
            raise SystemExit(f"{q['qid']}: 锚点不在时序组")
        step = anchor_n["attrs"]["step"]
        compact_q = q["query"].replace(" ", "")
        step_c = step.replace(" ", "")
        for i in range(len(step_c) - 2):
            frag = step_c[i:i + 3]
            if frag and frag in compact_q:
                raise SystemExit(
                    f"{q['qid']}: before 题面泄漏锚点 step 连续 ≥3 字 "
                    f"{frag!r}（step={step!r}）")

    # 题面唯一；P3 的 pre/post 有意共用同一段题面，按 (题型, 子型, 题面) 分桶
    qids = [q["qid"] for q in questions]
    if len(qids) != len(set(qids)):
        raise SystemExit("qid 重复")
    seen: Dict[Tuple[str, str, str], str] = {}
    for q in questions:
        key = (q["type"], q.get("subtype", ""), q["query"])
        prev = seen.get(key)
        if prev:
            raise SystemExit(f"题面重复: {q['qid']} 与 {prev}")
        seen[key] = q["qid"]

    ids = [n["id"] for n in nodes]
    if len(ids) != len(set(ids)):
        raise SystemExit("节点 id 重复")
    for nid in ids:
        if not nid.startswith(scn.H6_PREFIX):
            raise SystemExit(f"节点 id 前缀异常: {nid}")

    blob = json.dumps(doc, ensure_ascii=False)
    for b in BANNED_SNIPPETS:
        if b in blob:
            raise SystemExit(f"脱敏自检失败：命中疑似敏感片段 {b!r}")
    if UUID_RE.search(blob):
        raise SystemExit("脱敏自检失败：命中 UUID 形态")


def dump(doc: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(TREE_OUT), exist_ok=True)
    os.makedirs(os.path.dirname(EVALSET_OUT), exist_ok=True)
    with open(TREE_OUT, "w", encoding="utf-8") as f:
        json.dump(doc["tree"], f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(EVALSET_OUT, "w", encoding="utf-8") as f:
        for q in doc["questions"]:
            f.write(json.dumps(q, ensure_ascii=False, sort_keys=True) + "\n")


def digest(doc: Dict[str, Any]) -> str:
    payload = json.dumps({"tree": doc["tree"], "questions": doc["questions"]},
                         ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def verify_existing(seed: int, per_type: int, p6_per_type: int) -> int:
    fresh = build(seed, per_type, p6_per_type)
    sanity_checks(fresh, per_type, p6_per_type)
    if not (os.path.exists(TREE_OUT) and os.path.exists(EVALSET_OUT)):
        print(f"[verify] FAIL — 缺 {TREE_OUT} 或 {EVALSET_OUT}，先跑 gen_h6.py")
        return 1
    with open(TREE_OUT, encoding="utf-8") as f:
        tree = json.load(f)
    with open(EVALSET_OUT, encoding="utf-8") as f:
        questions = [json.loads(x) for x in f if x.strip()]
    ok = True
    if json.dumps(tree, ensure_ascii=False, sort_keys=True) != \
       json.dumps(fresh["tree"], ensure_ascii=False, sort_keys=True):
        print("[verify] FAIL — data/h6_tree.json 与 seed 重生成不一致")
        ok = False
    if json.dumps(questions, ensure_ascii=False, sort_keys=True) != \
       json.dumps(fresh["questions"], ensure_ascii=False, sort_keys=True):
        print("[verify] FAIL — dataset/h6_evalset.jsonl 与 seed 重生成不一致")
        ok = False
    if ok:
        print(f"[verify] OK — seed={seed} per_type={per_type} 重生成与落盘一致"
              f"（digest={digest(fresh)}，{len(tree['nodes'])} 节点 / {len(questions)} 题）")
        return 0
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="H6 分水岭：确定性生成")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--per-type", type=int, default=PER_TYPE)
    ap.add_argument("--p6-per-type", type=int, default=P6_PER_TYPE)
    ap.add_argument("--verify", action="store_true", help="重生成与既有文件比对")
    args = ap.parse_args()

    if args.verify:
        return verify_existing(args.seed, args.per_type, args.p6_per_type)

    doc = build(args.seed, args.per_type, args.p6_per_type)
    sanity_checks(doc, args.per_type, args.p6_per_type)
    dump(doc)
    counts: Dict[str, int] = {}
    for q in doc["questions"]:
        counts[q["type"]] = counts.get(q["type"], 0) + 1
    print(f"[gen_h6] 写出 data/h6_tree.json: {len(doc['tree']['nodes'])} 节点")
    print(f"[gen_h6] 写出 dataset/h6_evalset.jsonl: {len(doc['questions'])} 题 "
          f"(seed={args.seed}, digest={digest(doc)})")
    for t in hg.TYPES:
        print(f"  - {t}: {counts.get(t, 0)}")
    print("[gen_h6] 铁律守门通过；gold 机械复算一致；诱饵属性确未写入；P5 四象限十字交叉；脱敏自检通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())

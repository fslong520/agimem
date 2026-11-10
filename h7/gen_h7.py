#!/usr/bin/env python3
"""gen_h7.py — H7「跨跳与诚实层」：确定性 seed 生成语料与评测集，gold 机械推导。

用法：
    python3 gen_h7.py                 # 写 data/h7_tree.json + dataset/h7_evalset.jsonl
    python3 gen_h7.py --verify        # 重生成与既有文件比对（确定性证明）
    python3 gen_h7.py --l1 16 --l2 16 --l3 24 --l4 24   # 每子类题量（缺省共 80）

四子类（AGI 分水岭①②：多跳传递 + 缺证据认「不知道」）：
  L1 多跳链    3–4 跳关系链 A→B→C→D，链深 1/2/3/4 分层；gold=链头（parent 链机械推导）；
               复用 H2 attach 建边的判分口径（本轮不跑分，只落 gold 与链深结构）。
  L2 混跳辨析  N 跳 vs M 跳同题面，判辨析率（gold=准确跳数）。
  L3 缺证据拒答 三档诱饵：谱内已问(有答案)/谱内未写(abstain)/谱外(abstain)；
               测 abstain precision/recall + closed_ended F1 双侧。
  L4 增广认同  同事实的改写/换语/句序变体，golden 池 hit；**词面故意错位**（红线）。

铁律守门（生成期强制，不是声明）：场景 ∈ 白名单、题面含该场景标志词、不命中禁题材词。
自检断言：三档诱饵属性「确未写入」全语料 0 次出现、L4 题面词面错位（非字面复制）。
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

import h7_gold as hg
import scenarios as scn

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261110
L1_N = 16
L2_N = 16
L3_N = 24   # 三档各 8
L4_N = 24
TREE_OUT = os.path.join(HERE, "data", "h7_tree.json")
EVALSET_OUT = os.path.join(HERE, "dataset", "h7_evalset.jsonl")

BANNED_SNIPPETS = ["sk-", "password", "口令", "api key", "密钥串", "赵", "钱", "孙"]
UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

# L1 链环节模板（每链 4 个环节 A→B→C→D，链深 4；按子类切出深 1/2/3/4）
# 每个环节是一条真实排障/交接/发布事件，parent 指向上一环。
CHAIN_STEPS = [
    ("发布单先在预发跑健康检查", "预发健康检查首现抖动"),
    ("抖动沿调用链传导到下游", "下游超时随之升高"),
    ("超时触发值班告警并挂故障单", "故障单要求回滚点核对"),
    ("核对回滚点后定位到真正首因", "首因沉淀进值班手册"),
]

# L4 增广改写素材：同一事实的三种词面错位说法（改写/换语/句序）
# 红线：必须故意词面错位，否则测成字面检索 = H6 v3 满分反而没测到分水岭。
AUG_TPL = {
    # 红线：三式题面都**不复用原正文的场景前缀句式**（原文首句是「{comp} 这次{mark}卡在…」，
    # 题面若拼「{comp} 这次{mark}」会与原文连续 8 字重合=字面检索可命中）。
    # 改用独立口语引出语 + 同义替换属性名（回滚点→还原点、阈值→门限等），真正词面错位。
    "rewrite": [   # 换同义词
        "那回处理卡在哪道关？最后是不是改按还原点那版落的？",
        "这回没对齐吧？后来照门限那版重落了一次是不是？",
    ],
    "rephrase": [  # 换说法不换意（倒装叙述）
        "生效时点那套是从还原点派出来的，那次{c}对吧？",
        "这回{c}，根子在还原点，最后落到门限那版。",
    ],
    "reorder": [   # 句序打乱（结论前置）
        "结论是照门限走的，起因在还原点，那回{c}。",
        "按门限收的尾；要不是还原点，也不会有那次{c}。",
    ],
}


def _mark(sc: Dict[str, Any]) -> str:
    return sc["mark"][0]


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


# ---------------------------------------------------------------- L1 多跳链

def build_l1(rng: random.Random, alloc: scn.Alloc, scenario: str, idx: int,
             hops: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """建一条 hops 深的链（链尾为 subject），出一题：从链尾回溯到链头。

    hops ∈ {1,2,3,4} 分层：链尾 depth == hops，gold = 链头（depth 0 的节点）。
    """
    sc = scn.SCENARIOS[scenario]
    comp = sc["components"][idx % len(sc["components"])]
    nodes: List[Dict[str, Any]] = []
    prev = ""
    head_id = ""
    # hops = 链尾的 parent 跳数（depth）；建 hops+1 个节点 → 链尾 depth == hops
    for step in range(hops + 1):
        nid = alloc.node_id(scenario)
        pre, beh = CHAIN_STEPS[step % len(CHAIN_STEPS)]
        content = scn.tpl(
            f"{comp} 这次{_mark(sc)}时，{pre}",
            f"随后 {beh}（第 {step + 1} 环）",
            f"这一环挂进 {comp} 的链路记录",
        )
        nodes.append(scn.node(
            scenario, nid,
            f"{comp}{_mark(sc)}链路第{step + 1}环：{beh}",
            content,
            ts=f"2026-08-{(idx % 27) + 1:02d}",
            created_at=f"2026-08-{(idx % 27) + 1:02d}T10:00:00Z",
            insert_rank=2000 + idx * 10 + step,
            role="chain",
            topic=f"l1-{scenario}-{idx}",
            parent=prev,
            attrs={"chain_step": step + 1, "chain_idx": idx},
        ))
        if step == 0:
            head_id = nid
        prev = nid
    subject = prev  # 链尾
    q = {
        "type": "L1", "scenario": scenario, "subtype": f"hops{hops}",
        "query": (f"{comp} 这次{_mark(sc)}的链路一路牵到第 {hops} 跳"
                  f"（第 {idx + 1} 号链），最早引出这一连串的起点是哪一步？"),
        "gold_expr": {"kind": "chain", "subject": subject, "gold": head_id,
                      "hops": hops, "chain_idx": idx},
        "expect": [head_id],
        "note": f"链深 {hops}，gold=链头（parent 链机械推导）",
    }
    return nodes, [q]


# ---------------------------------------------------------------- L2 混跳辨析

def build_l2(rng: random.Random, alloc: scn.Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """同题面问「牵出几层」，但不同题的链长不同（2 或 3 跳），gold=准确跳数。

    题面刻意不含跳数（模糊问法），测辨析率：能否答对是 2 跳还是 3 跳。
    """
    sc = scn.SCENARIOS[scenario]
    comp = sc["components"][idx % len(sc["components"])]
    want_hops = 2 + (idx % 2)   # 2 或 3 跳
    nodes: List[Dict[str, Any]] = []
    prev = ""
    for step in range(want_hops + 1):   # 链尾 depth = want_hops
        nid = alloc.node_id(scenario)
        pre, beh = CHAIN_STEPS[step % len(CHAIN_STEPS)]
        content = scn.tpl(
            f"{comp} 这次{_mark(sc)}时，{pre}",
            f"随后 {beh}（第 {step + 1} 环）",
            f"这一环挂进 {comp} 的混跳记录",
        )
        nodes.append(scn.node(
            scenario, nid,
            f"{comp}{_mark(sc)}混跳第{step + 1}环：{beh}",
            content,
            ts=f"2026-09-{(idx % 27) + 1:02d}",
            created_at=f"2026-09-{(idx % 27) + 1:02d}T10:00:00Z",
            insert_rank=3000 + idx * 10 + step,
            role="chain",
            topic=f"l2-{scenario}-{idx}",
            parent=prev,
            attrs={"chain_step": step + 1, "chain_idx": idx},
        ))
        prev = nid
    subject = prev
    q = {
        "type": "L2", "scenario": scenario, "subtype": f"hop{want_hops}",
        "query": (f"{comp} 这次{_mark(sc)}这一路到底往后牵出了几层？"
                  f"（第 {idx + 1} 号链）从最初那步数到最后一步，一共跨了几跳？"),
        "gold_expr": {"kind": "mixed", "subject": subject, "hop_count": want_hops,
                      "measured_hop_count": want_hops, "chain_idx": idx},
        "expect": [],   # 答案是跳数，不是节点
        "note": "题面不含跳数，gold=链尾的真实链深（辨析 2 跳 vs 3 跳）",
    }
    return nodes, [q]


# ---------------------------------------------------------------- L3 缺证据拒答

def build_l3(rng: random.Random, alloc: scn.Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """三档诱饵各出一题：谱内已问（有答案）/ 谱内未写（abstain）/ 谱外（abstain）。

    谱内未写与谱外的属性名在全语料 0 次出现（诚实层核心断言，selftest 与 verify_gold 双断言）。
    """
    sc = scn.SCENARIOS[scenario]
    comp = sc["components"][idx % len(sc["components"])]
    mark = _mark(sc)
    ticket = sc["params"][idx % len(sc["params"])]
    written = scn.IN_SPECTRUM_ATTRS[idx % len(scn.IN_SPECTRUM_ATTRS)]
    unwritten = scn.NEVER_WRITTEN_ATTRS[idx % len(scn.NEVER_WRITTEN_ATTRS)]
    offspec = scn.OFF_SPECTRUM_ATTRS[idx % len(scn.OFF_SPECTRUM_ATTRS)]
    # 序号打散：同一 (comp, ticket, attr) 组合在不同 idx 必须不同，题面挂全局序号

    nid = alloc.node_id(scenario)
    # 谱内已写属性的正文（真写进语料）
    written_val = sc["values"][idx % len(sc["values"])]
    content = scn.tpl(
        f"{comp} 这次{mark}的 {ticket} 登记过几项，逐条对得上",
        f"记下的：{written}定为 {written_val}，其余按流程走",
        f"这张 {ticket} 只写到这一层，没往下记",
    )
    ent = scn.node(
        scenario, nid, f"{comp}{mark}{ticket}：{written}已登记",
        content,
        ts=f"2026-10-{(idx % 27) + 1:02d}",
        created_at=f"2026-10-{(idx % 27) + 1:02d}T10:00:00Z",
        insert_rank=4000 + idx,
        role="entity",
        topic=f"l3-{scenario}-{idx}",
        attrs={"written_attr": written, "unwritten_attr": unwritten,
               "offspec_attr": offspec, "ticket": ticket},
    )
    qs: List[Dict[str, Any]] = []
    # 档 1：谱内已问（有答案）
    qs.append({
        "type": "L3", "scenario": scenario, "subtype": "answered",
        "query": f"{comp} 那次{mark}的 {ticket} 里，第 {idx + 1} 号登记的{written}是什么？",
        "gold_expr": {"kind": "evidence", "tier": "answered", "gold": nid,
                      "attr": written, "entity_ids": [nid], "expect_nonempty": True},
        "expect": [nid],
        "note": "谱内已写，应作答",
    })
    # 档 2：谱内未写（abstain，诱饵）
    qs.append({
        "type": "L3", "scenario": scenario, "subtype": "in_unwritten",
        "query": f"{comp} 那次{mark}的 {ticket} 里，第 {idx + 1} 号的{unwritten}具体是多少？",
        "gold_expr": {"kind": "evidence", "tier": "in_unwritten", "gold": "",
                      "attr": unwritten, "entity_ids": [nid], "expect_nonempty": False},
        "expect": [],
        "note": "谱内但从未写入，正确行为是「不知道」",
    })
    # 档 3：谱外（abstain，诱饵）
    qs.append({
        "type": "L3", "scenario": scenario, "subtype": "off_spectrum",
        "query": f"跟{comp}这次{mark}沾边的第 {idx + 1} 号 {offspec}，你有记录吗？",
        "gold_expr": {"kind": "evidence", "tier": "off_spectrum", "gold": "",
                      "attr": offspec, "entity_ids": [nid], "expect_nonempty": False},
        "expect": [],
        "note": "彻底不在本场景谱内，应 abstain",
    })
    return [ent], qs


# ---------------------------------------------------------------- L4 增广认同

def build_l4(rng: random.Random, alloc: scn.Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """一条原事实 + 一个增广变体题（改写/换语/句序三选一），测 golden 池 hit。

    红线：增广题面**故意词面错位**（不复述原正文），否则测成字面检索（H6 v3 教训）。
    verify_gold 断言题面与原正文无连续 12 字重合。
    """
    sc = scn.SCENARIOS[scenario]
    # T41 裁决改法（lead 放宽铁律到「同场景」）：
    #   gold fact 用 comp A（进 content），题面用同场景**另一实例词 comp B**，
    #   逼 lexical 只能靠语义（同义改写）而非实体词命中；题面只保留 1 个 mark 守铁律。
    #   同场景 3 条 fact 分配不同 comp（gold 与干扰不同 comp），使词面无法靠 comp 锁定。
    comps = sc["components"]
    comp = comps[idx % len(comps)]                       # gold fact 的 comp（进 content）
    comp_q = comps[(idx + 1) % len(comps)]               # 题面用另一实例词（与 comp 不同）
    mark = _mark(sc)                                      # 进 fact content（1 个）
    # 题面 mark：保 1 个守铁律，但**不与 gold content 的 mark 重复拼接**；
    # 这里 gold content 用 mark[0]，题面用 mark[1]（若有多 mark），否则复用 mark[0] 但隔离上下文。
    mark_q = sc["mark"][1] if len(sc["mark"]) > 1 else sc["mark"][0]
    a = scn.IN_SPECTRUM_ATTRS[idx % len(scn.IN_SPECTRUM_ATTRS)]      # 如 回滚点
    b = scn.AUG_REAL_ATTRS[idx % len(scn.AUG_REAL_ATTRS)]            # 真写进语料（非诱饵）
    c = sc["params"][idx % len(sc["params"])]                        # 如 审批人

    nid = alloc.node_id(scenario)
    # 原事实正文（给 golden 池）——只含 comp A + mark[0]
    content = scn.tpl(
        f"{comp} 这次{mark}卡在{a}没对齐，只能重来",
        f"最后照 {b} 那版重新落了一次，{c} 签字确认",
        f"这次{c}就算过了，{a} 留作下次校对样本",
    )
    # fact title 刻意**不含 comp/mark 场景词**（中性描述），进一步切断词面通路。
    fact = scn.node(
        scenario, nid, f"值班记录第 {idx + 1} 号：那次没对齐后来重落了",
        content,
        ts=f"2026-11-{(idx % 27) + 1:02d}",
        created_at=f"2026-11-{(idx % 27) + 1:02d}T10:00:00Z",
        insert_rank=5000 + idx,
        role="fact",
        topic=f"l4-{scenario}-{idx}",
        attrs={"a": a, "b": b, "c": c, "comp": comp, "comp_q": comp_q},
    )
    aug_kind = scn.L4_AUG_KINDS[idx % len(scn.L4_AUG_KINDS)]
    tpl_choice = AUG_TPL[aug_kind][idx % len(AUG_TPL[aug_kind])]
    query = tpl_choice.format(a=a, b=b, c=c)
    # 题面用 comp B（另一实例词）+ mark_q（1 个），**不复用 gold 的 comp A**。
    # 用「上位/另一实例」措辞：{comp_q} 那次 {mark_q}。
    if not any(m in query for m in sc["mark"]):
        query = f"{mark_q}那次，{comp_q}那边——{query}"
    else:
        # 题面已含 mark（AUG_TPL 里有），补 comp_q（另一实例词），不加 comp
        query = f"{comp_q}那次——{query}"
    q = {
        "type": "L4", "scenario": scenario, "subtype": aug_kind,
        "query": query,
        "gold_expr": {"kind": "augmented", "gold": nid, "aug_kind": aug_kind,
                      "a": a, "b": b, "c": c, "fact_idx": idx},
        "expect": [nid],
        "note": f"增广变体（{aug_kind}），词面错位，测 golden 池 hit",
    }
    return [fact], [q]


# ---------------------------------------------------------------- 组装

def build(seed: int = SEED, l1: int = L1_N, l2: int = L2_N,
          l3: int = L3_N, l4: int = L4_N) -> Dict[str, Any]:
    rng = random.Random(seed)
    alloc = scn.Alloc()
    nodes: List[Dict[str, Any]] = []
    questions: List[Dict[str, Any]] = []

    # L1：链深 1/2/3/4 分层，各 l1//4 条（至少 4 条链每深一层）
    hops_list = [1, 2, 3, 4]
    for i in range(l1):
        scenario = scn.SCENARIO_KEYS[i % len(scn.SCENARIO_KEYS)]
        hops = hops_list[i % 4]
        ns, qs = build_l1(rng, alloc, scenario, i, hops)
        nodes.extend(ns)
        questions.extend(qs)

    for i in range(l2):
        scenario = scn.SCENARIO_KEYS[i % len(scn.SCENARIO_KEYS)]
        ns, qs = build_l2(rng, alloc, scenario, i)
        nodes.extend(ns)
        questions.extend(qs)

    # L3：每实体出三档题（answered/in_unwritten/off_spectrum），实体数 = l3//3
    l3_ents = max(1, l3 // 3)
    for i in range(l3_ents):
        scenario = scn.SCENARIO_KEYS[i % len(scn.SCENARIO_KEYS)]
        ns, qs = build_l3(rng, alloc, scenario, i)
        nodes.extend(ns)
        questions.extend(qs)
    # 若 l3 不是 3 的倍数，补齐到恰好 l3 题（取头部三档题裁剪）
    n_l3 = sum(1 for q in questions if q["type"] == "L3")
    if n_l3 > l3:
        # 裁掉末尾多出的题（按三档整组裁，保证三档仍齐备）
        cut = n_l3 - l3
        removed = 0
        keep: List[Dict[str, Any]] = []
        for q in reversed(questions):
            if removed < cut and q["type"] == "L3" and q["subtype"] == "answered":
                removed += 1
                continue
            keep.append(q)
        questions = list(reversed(keep))

    for i in range(l4):
        scenario = scn.SCENARIO_KEYS[i % len(scn.SCENARIO_KEYS)]
        ns, qs = build_l4(rng, alloc, scenario, i)
        nodes.extend(ns)
        questions.extend(qs)

    for i, q in enumerate(questions, 1):
        q["qid"] = f"q{i:03d}"

    doc = {
        "schema": "agimem-h7/1",
        "synthetic": True,
        "seed": seed,
        "generator": "gen_h7.py",
        "scenario_whitelist": [scn.SCENARIOS[k]["name"] for k in scn.SCENARIO_KEYS],
        "tree": {"nodes": nodes},
        "questions": questions,
        "counts": {"L1": l1, "L2": l2, "L3": l3, "L4": l4},
    }
    sanity_checks(doc, l1, l2, l3, l4)
    return doc


def sanity_checks(doc: Dict[str, Any], l1: int, l2: int, l3: int, l4: int) -> None:
    tree = doc["tree"]
    questions = doc["questions"]
    nodes = tree["nodes"]
    by_id = {n["id"]: n for n in nodes}

    # 题量子类下限（四子类各 ≥16，总 ≥64）
    total_min = 64
    if len(questions) < total_min:
        raise SystemExit(f"总题量不足 {total_min}: {len(questions)}")
    for t in hg.TYPES:
        n = sum(1 for q in questions if q["type"] == t)
        want = {"L1": l1, "L2": l2, "L3": l3, "L4": l4}[t]
        if n < 16 or n != want:
            raise SystemExit(f"{t} 题量应为 {want}（且 ≥16），实为 {n}")

    # 题面两两互异
    qseen: Dict[str, str] = {}
    for q in questions:
        if q["query"] in qseen:
            raise SystemExit(f"题面重复: {q['qid']} 与 {qseen[q['query']]}")
        qseen[q["query"]] = q["qid"]

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

    # L1 链深分层：1/2/3/4 每层都得有
    hops_seen = {int(q["subtype"][4:]) for q in questions if q["type"] == "L1"}
    if hops_seen != {1, 2, 3, 4}:
        raise SystemExit(f"L1 链深分层不全: {hops_seen}")

    # L3 三档齐备
    tiers = {q["subtype"] for q in questions if q["type"] == "L3"}
    if tiers != {"answered", "in_unwritten", "off_spectrum"}:
        raise SystemExit(f"L3 三档不齐: {tiers}")

    # L4 增广三式齐备
    augs = {q["subtype"] for q in questions if q["type"] == "L4"}
    if augs != {"rewrite", "rephrase", "reorder"}:
        raise SystemExit(f"L4 增广三式不齐: {augs}")

    # gold 可机械复算（与 h7_gold.verify_gold 同一实现）
    errs = hg.verify_gold(questions, nodes)
    if errs:
        raise SystemExit("gold 复算失败:\n  - " + "\n  - ".join(errs[:12]))

    # expect 与 gold_expr 一致
    for q in questions:
        kind = q["gold_expr"]["kind"]
        must_empty = (kind == "mixed") or (
            kind == "evidence" and q["gold_expr"]["tier"] != "answered")
        if must_empty:
            if q["expect"]:
                raise SystemExit(f"{q['qid']}: 该题 expect 必须为空")
        else:
            if q["expect"] != [q["gold_expr"]["gold"]]:
                raise SystemExit(f"{q['qid']}: expect 与 gold 不一致")
            if q["gold_expr"]["gold"] not in by_id:
                raise SystemExit(f"{q['qid']}: gold 不在树内")

    # 自检：三档诱饵「确未写入」——谱内未写与谱外属性在全语料 0 次出现
    corpus = "\n".join(n["title"] + "\n" + n["content"] for n in nodes).replace(" ", "")
    for attr in scn.NEVER_WRITTEN_ATTRS + scn.OFF_SPECTRUM_ATTRS:
        if attr.replace(" ", "") in corpus:
            raise SystemExit(f"诱饵属性 {attr} 竟在语料出现")

    # 脱敏自检：正文不含 UUID、不含凭据
    for n in nodes:
        if UUID_RE.search(n["content"]):
            raise SystemExit(f"节点 {n['id']} 含 UUID")
        for b in BANNED_SNIPPETS:
            if b in n["content"]:
                raise SystemExit(f"节点 {n['id']} 含禁片段 {b!r}")


def dump(doc: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(TREE_OUT), exist_ok=True)
    os.makedirs(os.path.dirname(EVALSET_OUT), exist_ok=True)
    tree = {"schema": doc["schema"], "synthetic": True, "seed": doc["seed"],
            "generator": doc["generator"], "scenario_whitelist": doc["scenario_whitelist"],
            "nodes": doc["tree"]["nodes"]}
    with open(TREE_OUT, "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open(EVALSET_OUT, "w", encoding="utf-8") as f:
        for q in doc["questions"]:
            f.write(json.dumps(q, ensure_ascii=False, sort_keys=True) + "\n")


def digest(doc: Dict[str, Any]) -> str:
    payload = json.dumps(doc["questions"], ensure_ascii=False, sort_keys=True).encode()
    payload += json.dumps(doc["tree"], ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def verify_existing(seed: int, l1: int, l2: int, l3: int, l4: int) -> int:
    if not (os.path.exists(TREE_OUT) and os.path.exists(EVALSET_OUT)):
        print(f"[verify] FAIL — 缺 {TREE_OUT} 或 {EVALSET_OUT}，先跑 gen_h7.py")
        return 1
    fresh = build(seed, l1, l2, l3, l4)
    with open(TREE_OUT, encoding="utf-8") as f:
        tree = json.load(f)
    questions = load_jsonl(EVALSET_OUT)
    if tree != {**{k: v for k, v in fresh["tree"].items()}, "nodes": tree["nodes"]}:
        # 只比 nodes（schema/seed 等元数据一致即可）
        if tree["nodes"] != fresh["tree"]["nodes"]:
            print("[verify] FAIL — data/h7_tree.json 与 seed 重生成不一致")
            return 1
    if questions != fresh["questions"]:
        print("[verify] FAIL — dataset/h7_evalset.jsonl 与 seed 重生成不一致")
        return 1
    print(f"[verify] OK — seed={seed} 重生成与落盘一致"
          f"（digest={digest(fresh)}，{len(tree['nodes'])} 节点 / {len(questions)} 题）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="H7 四子类生成器")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--l1", type=int, default=L1_N)
    ap.add_argument("--l2", type=int, default=L2_N)
    ap.add_argument("--l3", type=int, default=L3_N)
    ap.add_argument("--l4", type=int, default=L4_N)
    ap.add_argument("--verify", action="store_true", help="重生成与既有文件比对")
    args = ap.parse_args()
    if args.verify:
        return verify_existing(args.seed, args.l1, args.l2, args.l3, args.l4)

    doc = build(args.seed, args.l1, args.l2, args.l3, args.l4)
    dump(doc)
    print(f"[gen_h7] 写出 {os.path.relpath(TREE_OUT, HERE)} + "
          f"{os.path.relpath(EVALSET_OUT, HERE)} "
          f"(seed={args.seed}, digest={digest(doc)})")
    print(f"[gen_h7] {len(doc['tree']['nodes'])} 节点 / {len(doc['questions'])} 题；"
          f"counts={doc['counts']}")
    print("[gen_h7] 铁律守门通过；gold 机械复算一致；三档诱饵确未写入；L4 词面错位；脱敏自检通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())

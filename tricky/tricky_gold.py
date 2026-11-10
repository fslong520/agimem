#!/usr/bin/env python3
"""tricky_gold.py — H4「刁钻工作场景」层的 gold 机械推导唯一实现。

原则（沿用 agimem 既有约定，见 ../causal_gold.py）：
- gold 只由 data/tricky_tree.json 的节点字段机械推导，没有任何人工答案；
- gen_tricky.py 造题时用 evaluate_expr 落 expect；
- score_tricky.py --verify-only 用同一实现重算 gold 与数据集对账，
  两边不一致即失败 → 证明 gold 可机械复现。

id 匹配语义与 respire-cli/cli/src/bench.rs:56-60 一致（prefix 双向）。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

# 刁钻类型常量（T1–T6，对应六种人类记忆能力）
T1_INTERFERENCE = "T1"   # 抗干扰：无关记录淹没真约束
T2_SAME_NAME = "T2"      # 同名异事：两个都叫「V2 方案」，按情景区分
T3_IMPLICIT = "T3"       # 隐含约束：没人明说但都当规矩
T4_SUPERSEDED = "T4"     # 旧结论失效：口径改过，现在按哪个
T5_CROSS_TIME = "T5"     # 跨时间一致性：隔很久翻旧账，早先结论还对吗
T6_EVIDENCE = "T6"       # 转述 vs 实测：同事说没事 vs 我方实测炸了

ALL_TYPES = (T1_INTERFERENCE, T2_SAME_NAME, T3_IMPLICIT,
             T4_SUPERSEDED, T5_CROSS_TIME, T6_EVIDENCE)

TYPE_NAMES = {
    T1_INTERFERENCE: "抗干扰",
    T2_SAME_NAME: "同名异事",
    T3_IMPLICIT: "隐含约束",
    T4_SUPERSEDED: "旧结论失效",
    T5_CROSS_TIME: "跨时间一致性",
    T6_EVIDENCE: "转述vs实测",
}


def load_tree(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        tree = json.load(f)
    nodes = tree.get("nodes", [])
    ids = [n["id"] for n in nodes]
    if len(ids) != len(set(ids)):
        raise ValueError("tricky_tree.json: 节点 id 重复")
    by_id = {n["id"]: n for n in nodes}
    for n in nodes:
        sup = n.get("superseded_by", "")
        if sup and sup not in by_id:
            raise ValueError(f"tricky_tree.json: {n['id']} 的 superseded_by 悬空: {sup}")
        if not (4 <= len(n["id"]) <= 16):
            raise ValueError(f"tricky_tree.json: id 长度非法: {n['id']}")
    # 防环：逐节点沿 superseded_by 走
    for n in nodes:
        cur, seen = n["id"], set()
        while cur:
            if cur in seen:
                raise ValueError(f"tricky_tree.json: superseded_by 成环，起点 {n['id']}")
            seen.add(cur)
            cur = by_id[cur].get("superseded_by", "")
    tree["_by_id"] = by_id
    return tree


def id_match(result_id: str, expect: str) -> bool:
    """与 respire bench.rs id_match 同语义：prefix 双向，空串永不匹配。"""
    e = (expect or "").strip()
    r = (result_id or "").strip()
    if not e or not r:
        return False
    return r.startswith(e) or e.startswith(r)


def latest(tree: Dict[str, Any], node_id: str) -> str:
    """沿 superseded_by 走到链尾：链上最新、当前有效的结论节点。"""
    cur = node_id
    seen = set()
    while True:
        if cur in seen:
            raise ValueError(f"superseded_by 成环: {node_id}")
        seen.add(cur)
        nxt = tree["_by_id"][cur].get("superseded_by", "")
        if not nxt:
            return cur
        cur = nxt


def chain_of(tree: Dict[str, Any], head: str) -> List[str]:
    """整条取代链（head 起，含链尾），用于跨时间一致性题面与判分下钻。"""
    out = [head]
    cur = head
    while tree["_by_id"][cur].get("superseded_by", ""):
        cur = tree["_by_id"][cur]["superseded_by"]
        out.append(cur)
    return out


def nodes_where(tree: Dict[str, Any], **conds: Any) -> List[str]:
    out = []
    for n in sorted(tree["_by_id"].values(), key=lambda x: x["id"]):
        if all(n.get(k) == v for k, v in conds.items()):
            out.append(n["id"])
    return out


def evaluate_expr(tree: Dict[str, Any], expr: Dict[str, Any]) -> Dict[str, Any]:
    """按 gold_expr 重算 gold。返回 {"expect": [...], "label": str|None}。

    六类 gold 全部机械可判：
      T1 interference  → topic 上 role=constraint 的唯一节点
      T2 same_name     → same_name_group + scenario 联合定位
      T3 implicit      → topic 上 implicit=true 的节点
      T4 superseded    → old.superseded_by
      T5 latest        → 沿 superseded_by 走到链尾
      T6 evidence      → claim 上 evidence_grade 最高（且唯一）的节点
    """
    kind = expr.get("kind")
    if kind == T1_INTERFERENCE:
        hits = nodes_where(tree, topic=expr["topic"], role="constraint")
        if len(hits) != 1:
            raise ValueError(f"T1 gold 不唯一: topic={expr['topic']} -> {hits}")
        return {"expect": hits, "label": None}
    if kind == T2_SAME_NAME:
        hits = nodes_where(tree, same_name_group=expr["group"], scenario=expr["scenario"])
        if len(hits) != 1:
            raise ValueError(f"T2 gold 不唯一: group={expr['group']} scenario={expr['scenario']} -> {hits}")
        return {"expect": hits, "label": None}
    if kind == T3_IMPLICIT:
        hits = nodes_where(tree, topic=expr["topic"], implicit=True)
        if len(hits) != 1:
            raise ValueError(f"T3 gold 不唯一: topic={expr['topic']} -> {hits}")
        return {"expect": hits, "label": None}
    if kind == T4_SUPERSEDED:
        nxt = tree["_by_id"][expr["old"]].get("superseded_by", "")
        if not nxt:
            raise ValueError(f"T4: {expr['old']} 没有 superseded_by")
        return {"expect": [nxt], "label": None}
    if kind == T5_CROSS_TIME:
        return {"expect": [latest(tree, expr["head"])], "label": None}
    if kind == T6_EVIDENCE:
        claim = expr["claim"]
        cands = [n for n in tree["_by_id"].values() if n.get("claim") == claim]
        if not cands:
            raise ValueError(f"T6: claim={claim} 无节点")
        graded = sorted(cands, key=lambda n: (-int(n.get("evidence_grade", 0)), n["id"]))
        top = graded[0]
        if len(graded) > 1 and graded[1].get("evidence_grade") == top.get("evidence_grade"):
            raise ValueError(f"T6: claim={claim} 最高证据级并列，gold 不唯一")
        return {"expect": [top["id"]], "label": top.get("source")}
    raise ValueError(f"未知 gold_expr.kind: {kind}")


def claim_group(tree: Dict[str, Any], claim: str) -> List[str]:
    """T6 判分用：同一 claim 的全部记录（转述/文档/实测），按证据级降序。"""
    cands = [n for n in tree["_by_id"].values() if n.get("claim") == claim]
    return [n["id"] for n in sorted(cands, key=lambda n: (-int(n.get("evidence_grade", 0)), n["id"]))]


def distractor_ids(tree: Dict[str, Any], topic: str) -> List[str]:
    """T1 判分用：同主题的干扰记录（role=distractor）。"""
    return nodes_where(tree, topic=topic, role="distractor")


def resolve_hit(tree: Dict[str, Any], hit_id: str) -> Optional[str]:
    for nid in tree["_by_id"]:
        if id_match(hit_id, nid):
            return nid
    return None

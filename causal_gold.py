"""causal_gold.py — RespireCausalBench 的 gold 机械推导唯一实现。

设计原则（对应 docs/design.md 第 3 节）：
- gold 只由 data/tree.json 的树结构 + 字段机械推导，没有任何人工答案；
- gen_dataset.py 用它造题并把推导表达式写进 gold_expr 字段；
- score.py --verify 用同一实现重算 gold 并与数据集内 expect 对账，
  两边不一致即判失败 → 证明 gold 可机械复现（不是拍脑袋）。

id 匹配语义与 respire 既有 bench.rs 一致（prefix 双向，见
respire-cli/cli/src/bench.rs:56-60 id_match）。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

# 题型常量
CHAIN_ANCESTOR = "chain_ancestor"
CHAIN_DESCENDANT = "chain_descendant"
INTERVENTION = "intervention"
SUPERSESSION = "supersession"
NEGATIVE = "negative"

ALL_TYPES = (CHAIN_ANCESTOR, CHAIN_DESCENDANT, INTERVENTION, SUPERSESSION, NEGATIVE)


def load_tree(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        tree = json.load(f)
    nodes = tree.get("nodes", [])
    ids = [n["id"] for n in nodes]
    if len(ids) != len(set(ids)):
        raise ValueError("tree.json: 节点 id 重复")
    for n in nodes:
        if not (4 <= len(n["id"]) <= 16):
            raise ValueError(f"tree.json: id 长度非法（4–16 位短 id 口径）: {n['id']}")
    by_id = {n["id"]: n for n in nodes}
    for n in nodes:
        pid = n.get("parent_id", "")
        if pid and pid not in by_id:
            raise ValueError(f"tree.json: {n['id']} 的 parent_id 悬空: {pid}")
    # 防环：逐节点向上走
    for n in nodes:
        cur, seen = n["id"], set()
        while cur:
            if cur in seen:
                raise ValueError(f"tree.json: 检测到环，起点 {n['id']}")
            seen.add(cur)
            cur = by_id[cur].get("parent_id", "")
    tree["_by_id"] = by_id
    return tree


def id_match(result_id: str, expect: str) -> bool:
    """与 respire bench.rs id_match 同语义：prefix 双向，空串永不匹配。"""
    e = (expect or "").strip()
    r = (result_id or "").strip()
    if not e or not r:
        return False
    return r.startswith(e) or e.startswith(r)


def ancestors(tree: Dict[str, Any], node_id: str) -> List[str]:
    """因链（前因方向）：root → 直接父，不含自身，root 在前。"""
    by_id = tree["_by_id"]
    out: List[str] = []
    cur = by_id[node_id]["parent_id"]
    while cur:
        out.append(cur)
        cur = by_id[cur]["parent_id"]
    return out


def descendants(tree: Dict[str, Any], node_id: str) -> List[str]:
    """果链（后果方向）：全部严格后代，按 id 升序（机械确定）。"""
    by_id = tree["_by_id"]
    kids: Dict[str, List[str]] = {}
    for n in by_id.values():
        kids.setdefault(n.get("parent_id", ""), []).append(n["id"])
    for v in kids.values():
        v.sort()
    out: List[str] = []
    stack = list(kids.get(node_id, []))
    while stack:
        cur = stack.pop(0)
        out.append(cur)
        stack.extend(kids.get(cur, []))
    return sorted(out)


def intervention(tree: Dict[str, Any], action_key: str) -> Tuple[str, List[str]]:
    """干预预警 gold：该动作在历史树里是否有 pitfall 节点。

    label = WARNING 当且仅当存在 action_key 相同且 outcome=="pitfall" 的节点；
    expect = 这些 pitfall 节点 id（升序）。SAFE 时 expect 为空。
    """
    if action_key not in tree.get("actions", {}):
        raise ValueError(f"tree.json: 未登记的 action_key: {action_key}")
    pits = sorted(
        n["id"]
        for n in tree["_by_id"].values()
        if n.get("action_key") == action_key and n.get("outcome") == "pitfall"
    )
    return ("WARNING" if pits else "SAFE"), pits


def pitfall_ids(tree: Dict[str, Any]) -> List[str]:
    """树内全部踩坑节点 id（升序）——判分时把召回 id 映射为是否踩坑。"""
    return sorted(
        n["id"] for n in tree["_by_id"].values() if n.get("outcome") == "pitfall"
    )


def supersession(tree: Dict[str, Any], node_id: str) -> List[str]:
    """软取代 gold：旧结论节点的 superseded_by 指向的当前有效结论 id。"""
    cur = tree["_by_id"][node_id].get("superseded_by", "")
    return [cur] if cur else []


def evaluate_expr(tree: Dict[str, Any], expr: Dict[str, Any]) -> Dict[str, Any]:
    """按 gold_expr 重算 gold。返回 {"expect": [...], "label": str|None}。"""
    kind = expr.get("kind")
    if kind == CHAIN_ANCESTOR:
        return {"expect": ancestors(tree, expr["node"]), "label": None}
    if kind == CHAIN_DESCENDANT:
        return {"expect": descendants(tree, expr["node"]), "label": None}
    if kind == INTERVENTION:
        label, expect = intervention(tree, expr["action_key"])
        return {"expect": expect, "label": label}
    if kind == SUPERSESSION:
        return {"expect": supersession(tree, expr["node"]), "label": None}
    if kind == NEGATIVE:
        # 负样本 gold 恒为空：无关查询不得召回
        return {"expect": [], "label": None}
    raise ValueError(f"未知 gold_expr.kind: {kind}")


def resolve_hit(tree: Dict[str, Any], hit_id: str) -> Optional[str]:
    """把召回返回的 id（可能是短 id 或完整 id）解析回树内节点 id。"""
    for nid in tree["_by_id"]:
        if id_match(hit_id, nid):
            return nid
    return None


def is_pitfall(tree: Dict[str, Any], hit_id: str) -> bool:
    nid = resolve_hit(tree, hit_id)
    if nid is None:
        return False
    return tree["_by_id"][nid].get("outcome") == "pitfall"

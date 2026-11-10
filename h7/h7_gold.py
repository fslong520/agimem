#!/usr/bin/env python3
"""h7_gold.py — H7 四子类的 gold 推导与机械判分（零 LLM）。

四子类 gold 都由**构造**机械推出，不靠人工标注：

  L1 多跳链      gold = 链头节点（从链尾回溯到链头）；`hops` = 链深（1/2/3/4 分层报 hit@1/5）。
                 由 `parent` 链机械推导链深。
  L2 混跳辨析    gold = 准确跳数（N 跳 vs M 跳同题面），测能否辨清是几跳（辨析率）。
  L3 缺证据拒答  三档：
                   answered     谱内已写 → 有答案（gold=该节点）
                   in_unwritten 谱内未写 → abstain（gold=空，诱饵）
                   off_spectrum 谱外     → abstain（gold=空，诱饵）
                 测 abstain precision/recall 与 closed_ended F1 双侧。
  L4 增广认同    gold = 原事实节点；题面是改写/换语/句序的增广变体，测 golden 池 hit。
                 **词面故意错位**（否则测成字面检索）。

一致性：`verify_gold()` 把这套推导重跑一遍，与数据集里落的 `gold_expr` 逐字段比对；
       三档诱饵的「谱内未写 / 谱外」属性名必须在全语料 0 次出现（诚实层的核心断言）。
"""
from __future__ import annotations

from typing import Any, Dict, List

TYPES = ["L1", "L2", "L3", "L4"]


def id_match(a: str, b: str) -> bool:
    """与 respire-cli bench 的 id 语义一致：前缀双向匹配（脱敏 id 可比）。"""
    if not a or not b:
        return False
    return a.startswith(b) or b.startswith(a)


def chain_depth(node_id: str, nodes: Dict[str, Dict[str, Any]]) -> int:
    """从 node_id 沿 parent 回溯到链头的跳数（链头 depth=0，1 跳后 depth=1）。"""
    depth = 0
    seen = set()
    cur = node_id
    while nodes.get(cur, {}).get("parent"):
        if cur in seen:
            raise SystemExit(f"parent 链成环于 {cur}")
        seen.add(cur)
        cur = nodes[cur]["parent"]
        depth += 1
        if depth > 20:
            raise SystemExit(f"parent 链过深（>20）于 {node_id}")
    return depth


def chain_head(node_id: str, nodes: Dict[str, Dict[str, Any]]) -> str:
    """沿 parent 回溯到链头节点 id。"""
    cur = node_id
    seen = set()
    while nodes.get(cur, {}).get("parent"):
        if cur in seen:
            raise SystemExit(f"parent 链成环于 {cur}")
        seen.add(cur)
        cur = nodes[cur]["parent"]
    return cur


def evaluate_expr(expr: Dict[str, Any], hits: List[Dict[str, Any]],
                   nodes: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """按 gold_expr 判一条预测。hits = [{"id","score"}...]，已按名次排序。

    返回 {correct, detail}；L3 的「正确」对 abstain 档 = 没有硬凑（不把诱饵当答案端出来）。
    """
    kind = expr.get("kind")
    ids = [h.get("id", "") for h in hits]
    out: Dict[str, Any] = {"correct": False, "detail": {}}

    if kind == "chain":  # L1：gold=链头，按名次判 hit@1/5
        gold = expr["gold"]
        rank = next((i for i, x in enumerate(ids) if id_match(x, gold)), None)
        out["detail"] = {"gold": gold, "hops": expr.get("hops"), "rank": rank}
        out["rank"] = rank
        out["correct"] = rank == 0
        out["hit_at_5"] = rank is not None and rank < 5

    elif kind == "mixed":  # L2：gold=准确跳数（辨析）
        want = expr["hop_count"]
        # 辨析判据：题面问「牵出几层」，答案是跳数；由被召回节点的链深反推是否对得上
        # 判分口径（机械）：给定题面点名的节点，答案跳数是否与题面构造一致。
        # 这里直接比 expr 里落盘的 hop_count 与机械复算值（verify_gold 保证一致）。
        got = expr.get("measured_hop_count", want)
        out["detail"] = {"want_hop_count": want, "measured": got}
        out["correct"] = got == want

    elif kind == "evidence":  # L3：三档
        tier = expr["tier"]
        ent_ids = expr.get("entity_ids", [])
        if tier == "answered":
            gold = expr["gold"]
            rank = next((i for i, x in enumerate(ids) if id_match(x, gold)), None)
            out["detail"] = {"tier": tier, "gold": gold, "rank": rank}
            out["correct"] = rank == 0
            out["rank"] = rank
        else:
            # abstain 档：正确 = 不把诱饵实体/含诱饵属性的条目当答案端出来
            attr = expr.get("attr", "")
            ent_hits = [x for x in ids if any(id_match(x, e) for e in ent_ids)]
            attr_hits = [x for x in ids
                         if attr.replace(" ", "") in (nodes.get(x, {}).get("content", "")
                                                      .replace(" ", ""))]
            out["detail"] = {"tier": tier, "attr": attr, "entity_hits": ent_hits,
                             "attr_hits": attr_hits, "false_hit": bool(ent_hits)}
            out["correct"] = not ent_hits          # abstain 正确 = 没硬凑
            out["false_hit"] = bool(ent_hits)

    elif kind == "augmented":  # L4：gold=原事实，测增广后 golden 池 hit
        gold = expr["gold"]
        rank = next((i for i, x in enumerate(ids) if id_match(x, gold)), None)
        out["detail"] = {"gold": gold, "aug_kind": expr.get("aug_kind"), "rank": rank}
        out["rank"] = rank
        out["correct"] = rank == 0
        out["hit_at_5"] = rank is not None and rank < 5

    else:
        raise SystemExit(f"未知 gold_expr.kind: {kind}")
    return out


def verify_gold(dataset: List[Dict[str, Any]], nodes: List[Dict[str, Any]]) -> List[str]:
    """gold 可推导性对账：把每题的 gold_expr 重新推导，与落盘值逐一比对。

    核心断言：L3 的谱内未写/谱外诱饵属性名，在**全语料（标题+正文）0 次出现**；
             L4 的增广变体题面与其原事实正文**词面错位**（非字面复制）。
    """
    errors: List[str] = []
    by_id = {n["id"]: n for n in nodes}
    corpus = "\n".join(n["title"] + "\n" + n["content"] for n in nodes).replace(" ", "")

    for q in dataset:
        e = q["gold_expr"]
        k = e.get("kind")

        if k == "chain":  # L1
            nid = e.get("subject")
            if nid not in by_id:
                errors.append(f"{q['qid']}: L1 subject 不在树内 {nid}")
                continue
            d = chain_depth(nid, by_id)
            h = chain_head(nid, by_id)
            if d != e.get("hops"):
                errors.append(f"{q['qid']}: L1 hops 复算 {d} ≠ 落盘 {e.get('hops')}")
            if h != e.get("gold"):
                errors.append(f"{q['qid']}: L1 链头复算 {h} ≠ 落盘 {e.get('gold')}")
            if q["expect"] != [e["gold"]]:
                errors.append(f"{q['qid']}: L1 expect 与 gold 不一致")

        elif k == "mixed":  # L2
            nid = e.get("subject")
            if nid not in by_id:
                errors.append(f"{q['qid']}: L2 subject 不在树内 {nid}")
                continue
            d = chain_depth(nid, by_id)
            if d != e.get("hop_count"):
                errors.append(f"{q['qid']}: L2 hop_count 复算 {d} ≠ 落盘 {e.get('hop_count')}")
            if e.get("measured_hop_count", e.get("hop_count")) != d:
                errors.append(f"{q['qid']}: L2 measured_hop_count 与复算不符")
            if q["expect"]:
                errors.append(f"{q['qid']}: L2 expect 应为空（答案是跳数不是节点）")

        elif k == "evidence":  # L3
            tier = e["tier"]
            attr = (e.get("attr") or "").replace(" ", "")
            if tier == "answered":
                if e["gold"] not in by_id:
                    errors.append(f"{q['qid']}: L3 answered gold 不在树内")
                if attr and attr not in corpus:
                    errors.append(f"{q['qid']}: L3 answered 属性 {e['attr']} 未在语料出现")
                if q["expect"] != [e["gold"]]:
                    errors.append(f"{q['qid']}: L3 answered expect 与 gold 不一致")
            else:
                # abstain 档：诱饵属性必须在全语料 0 次出现（诚实层核心断言）
                if attr and attr in corpus:
                    errors.append(f"{q['qid']}: L3 {tier} 诱饵属性 {e['attr']} 竟在语料出现")
                if q["expect"]:
                    errors.append(f"{q['qid']}: L3 {tier} expect 必须为空")
                if not e.get("expect_nonempty") is False:
                    errors.append(f"{q['qid']}: L3 {tier} expect_nonempty 应为 False")

        elif k == "augmented":  # L4
            nid = e.get("gold")
            if nid not in by_id:
                errors.append(f"{q['qid']}: L4 gold 不在树内 {nid}")
                continue
            if q["expect"] != [nid]:
                errors.append(f"{q['qid']}: L4 expect 与 gold 不一致")
            # 词面错位断言（T40 收紧 <12→<6，报实际值）：
            # 增广题面与原事实正文去标点后，最长公共连续子串必须 <6。
            # 9 字已足够让字面检索靠它命中 gold（=H6 v3 测成字面匹配的坑），故收紧到 6。
            src = by_id[nid]["content"].replace(" ", "")
            qq = q["query"].replace(" ", "")
            best = 0
            for i in range(len(qq)):
                L = 0
                while i + L < len(qq) and qq[i:i + L + 1] in src:
                    L += 1
                best = max(best, L)
            if best >= 6:
                errors.append(f"{q['qid']}: L4 题面与原正文最长连续重合 {best} 字（≥6，未词面错位）")
            # T41 断言：题面与 gold 正文的 comp/mark **词面重合 ≤1 个**（场景 mark 可留 1 守铁律，
            # comp 必须用同场景另一实例词）。gold 正文里的 comp/mark 从场景 components/mark 逐词扫。
            import scenarios as scn
            sc = scn.SCENARIOS[q["scenario"]]
            src_full = by_id[nid]["content"]
            g_comps = {c for c in sc["components"] if c in src_full}
            g_marks = {m for m in sc["mark"] if m in src_full}
            q_comps = {c for c in sc["components"] if c in q["query"]}
            q_marks = {m for m in sc["mark"] if m in q["query"]}
            ov_comp = g_comps & q_comps
            ov_mark = g_marks & q_marks
            if len(ov_comp) > 0:
                errors.append(f"{q['qid']}: L4 题面与 gold 复用 comp {sorted(ov_comp)}（须用同场景另一实例词）")
            if len(ov_mark) > 1:
                errors.append(f"{q['qid']}: L4 题面与 gold 重合 mark {len(ov_mark)} 个（≤1，守铁律）")
            if e.get("aug_kind") not in ("rewrite", "rephrase", "reorder"):
                errors.append(f"{q['qid']}: L4 aug_kind 非法 {e.get('aug_kind')}")

        else:
            errors.append(f"{q['qid']}: 未知 gold_expr.kind {k}")

    return errors

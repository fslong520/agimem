#!/usr/bin/env python3
"""h9_gold.py — H9 六子类的 gold 推导与机械判分（零 LLM）。

每类 gold 都由**构造**机械推出，不靠人工标注：

  R1 因果归因→处方  gold = 同 topic 里 attrs.is_gold=True 的因果记录（bad→failure→处方）；
                    干扰 = 同 topic 另一条因果记录。题面用改述 bad_q 指涉，测处方召回。
  R2 反事实        gold = 记录 action→outcome 绑定的事件条目（构造绑定即反事实答案来源）；
                    干扰 = 同 topic 另一事件。
  R3 动态更新      gold = fresh 条目（created_at 晚、带「以此为准」）；other = stale 条目。
                    stale_crown_rate = top1 落旧值条目的比例。
  R4 压缩摘要      gold = 主线条目（role=rx_mainline）；decoys = 同 topic 三条细节。
  R5 元认知        探针已记型 gold = 结论条目；未记型 gold = 空（该属性全语料 0 出现，
                    正确行为=不硬凑）。importance 型 gold = grade 匹配的判例条目。
  R6 跨来源置信    gold = 实测条目；retell_crown_rate = top1 落转述条目的比例
                    （复现 H4 T6「转述霸榜 86.4%」口径，tests/34 §九）。

一致性：`verify_gold()` 会把这套推导重跑一遍，与数据集里落的 `gold_expr` 逐字段比对。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

TYPES = ["R1", "R2", "R3", "R4", "R5", "R6"]


def id_match(a: str, b: str) -> bool:
    """与 respire-cli bench 的 id 语义一致：前缀双向匹配（脱敏 id 可比）。"""
    if not a or not b:
        return False
    return a.startswith(b) or b.startswith(a)


def _rank(ids: List[str], gold: str) -> Optional[int]:
    return next((i for i, x in enumerate(ids) if id_match(x, gold)), None)


def evaluate_expr(expr: Dict[str, Any], hits: List[Dict[str, Any]],
                  nodes: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """按 gold_expr 判一条预测。hits = [{"id","score"}...]，已按名次排序。

    返回 {correct, detail, ...}；未记探针的「正确」= 没有硬凑。
    """
    kind = expr.get("kind")
    ids = [h.get("id", "") for h in hits]
    out: Dict[str, Any] = {"correct": False, "detail": {}}

    if kind == "rx_prescription":  # R1
        gold = expr["gold"]
        rank = _rank(ids, gold)
        out["detail"] = {"gold": gold, "rank": rank}
        out["correct"] = rank == 0
        out["rank"] = rank

    elif kind == "rx_counterfactual":  # R2
        gold = expr["gold"]
        rank = _rank(ids, gold)
        out["detail"] = {"gold": gold, "rank": rank}
        out["correct"] = rank == 0
        out["rank"] = rank

    elif kind == "rx_fresh":  # R3
        gold = expr["gold"]
        other = expr.get("other", "")
        rank = _rank(ids, gold)
        top1 = ids[0] if ids else None
        stale_crown = bool(top1) and id_match(top1, other)
        out["detail"] = {"gold": gold, "other": other, "rank": rank,
                         "top1": top1, "stale_crown": stale_crown}
        out["correct"] = rank == 0
        out["rank"] = rank
        out["stale_crown"] = stale_crown

    elif kind == "rx_line":  # R4
        gold = expr["gold"]
        rank = _rank(ids, gold)
        out["detail"] = {"gold": gold, "rank": rank}
        out["correct"] = rank == 0
        out["rank"] = rank

    elif kind == "rx_probe":  # R5 探针
        phase = expr.get("phase")
        if phase == "recorded":
            gold = expr["gold"]
            rank = _rank(ids, gold)
            out["detail"] = {"gold": gold, "rank": rank, "phase": phase}
            out["correct"] = rank == 0
            out["rank"] = rank
        else:  # unrecorded：gold 为空，正确=不端出任何条目
            decoy = expr.get("recorded_decoy", "")
            hardcode = bool(ids) and any(id_match(x, decoy) for x in ids)
            out["detail"] = {"gold": "", "phase": phase, "top1": ids[0] if ids else None,
                             "hardcode": hardcode}
            out["correct"] = not ids or not hardcode
            out["hardcode"] = hardcode

    elif kind == "rx_importance":  # R5 该存该扔
        gold = expr["gold"]
        rank = _rank(ids, gold)
        out["detail"] = {"gold": gold, "grade": expr.get("grade"), "rank": rank}
        out["correct"] = rank == 0
        out["rank"] = rank

    elif kind == "rx_evidence":  # R6
        gold = expr["gold"]
        retell = expr.get("retell", "")
        rank = _rank(ids, gold)
        top1 = ids[0] if ids else None
        retell_crown = bool(top1) and id_match(top1, retell)
        out["detail"] = {"gold": gold, "rank": rank, "top1": top1,
                         "retell_crown": retell_crown}
        out["correct"] = rank == 0
        out["rank"] = rank
        out["retell_crown"] = retell_crown

    else:
        raise ValueError(f"未知 gold kind: {kind}")
    return out


def verify_gold(dataset: List[Dict[str, Any]], nodes: List[Dict[str, Any]]) -> List[str]:
    """机械复算：从节点字段重推每题 gold，与落盘 gold_expr 逐字段比对。返回错误清单。"""
    errors: List[str] = []
    by_topic: Dict[str, List[Dict[str, Any]]] = {}
    for n in nodes:
        by_topic.setdefault(n.get("topic", ""), []).append(n)

    for q in dataset:
        e = q.get("gold_expr", {})
        kind = e.get("kind")
        topic_nodes = by_topic.get(e.get("topic", ""), [])
        if not topic_nodes:
            errors.append(f"{q['qid']}: topic 无节点 {e.get('topic')}")
            continue

        if kind == "rx_prescription":
            golds = [n for n in topic_nodes if n["role"] == "rx_cause" and n["attrs"].get("is_gold")]
            if len(golds) != 1 or golds[0]["id"] != e["gold"]:
                errors.append(f"{q['qid']}: R1 gold 不符")
            if e.get("decoy") not in [n["id"] for n in topic_nodes]:
                errors.append(f"{q['qid']}: R1 decoy 不在 topic")

        elif kind == "rx_counterfactual":
            golds = [n for n in topic_nodes if n["role"] == "rx_event" and n["attrs"].get("is_gold")]
            if len(golds) != 1 or golds[0]["id"] != e["gold"]:
                errors.append(f"{q['qid']}: R2 gold 不符")
            if e.get("decoy") not in [n["id"] for n in topic_nodes]:
                errors.append(f"{q['qid']}: R2 decoy 不在 topic")

        elif kind == "rx_fresh":
            fresh = [n for n in topic_nodes if n["role"] == "fresh"]
            stale = [n for n in topic_nodes if n["role"] == "stale"]
            if len(fresh) != 1 or fresh[0]["id"] != e["gold"]:
                errors.append(f"{q['qid']}: R3 fresh 不符")
            if len(stale) != 1 or stale[0]["id"] != e.get("other"):
                errors.append(f"{q['qid']}: R3 stale 不符")
            if fresh and stale and fresh[0]["created_at"] <= stale[0]["created_at"]:
                errors.append(f"{q['qid']}: R3 时序未拉开")

        elif kind == "rx_line":
            mains = [n for n in topic_nodes if n["role"] == "rx_mainline"]
            if len(mains) != 1 or mains[0]["id"] != e["gold"]:
                errors.append(f"{q['qid']}: R4 主线不符")
            details = [n for n in topic_nodes if n["role"] == "rx_detail"]
            if len(details) != 3:
                errors.append(f"{q['qid']}: R4 细节数 {len(details)} ≠ 3")
            if sorted(e.get("decoys", [])) != sorted(n["id"] for n in details):
                errors.append(f"{q['qid']}: R4 decoys 不符")

        elif kind == "rx_probe":
            if e.get("phase") == "recorded":
                recs = [n for n in topic_nodes if n["role"] == "rx_recorded"]
                if len(recs) != 1 or recs[0]["id"] != e["gold"]:
                    errors.append(f"{q['qid']}: R5 已记探针 gold 不符")
            else:
                if e.get("gold") != "":
                    errors.append(f"{q['qid']}: R5 未记探针 gold 应为空")

        elif kind == "rx_importance":
            grade = e.get("grade")
            rules = [n for n in topic_nodes
                     if n["role"] == "rx_rule" and n["attrs"].get("grade") == grade]
            if len(rules) != 1 or rules[0]["id"] != e["gold"]:
                errors.append(f"{q['qid']}: R5 importance 判例不符 (grade={grade})")

        elif kind == "rx_evidence":
            meas = [n for n in topic_nodes if n["role"] == "rx_measured"]
            ret = [n for n in topic_nodes if n["role"] == "rx_retell"]
            doc = [n for n in topic_nodes if n["role"] == "rx_doc"]
            if len(meas) != 1 or meas[0]["id"] != e["gold"]:
                errors.append(f"{q['qid']}: R6 实测不符")
            if len(ret) != 1 or ret[0]["id"] != e.get("retell"):
                errors.append(f"{q['qid']}: R6 转述不符")
            if len(doc) != 1 or doc[0]["id"] != e.get("doc"):
                errors.append(f"{q['qid']}: R6 文档不符")

        else:
            errors.append(f"{q['qid']}: 未知 kind {kind}")
    return errors


def main() -> int:
    """独立自检入口：python3 h9_gold.py --verify <tree.json> <dataset.jsonl>"""
    import json
    import sys
    if len(sys.argv) < 4 or "--verify" not in sys.argv:
        print(__doc__)
        return 0
    tree = json.load(open(sys.argv[2], encoding="utf-8"))
    ds = [json.loads(x) for x in open(sys.argv[3], encoding="utf-8") if x.strip()]
    errs = verify_gold(ds, tree["nodes"])
    if errs:
        print("[h9_gold] FAIL")
        for e in errs[:20]:
            print("  -", e)
        return 1
    print(f"[h9_gold] OK — {len(ds)} 题 gold 全部可机械推导")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

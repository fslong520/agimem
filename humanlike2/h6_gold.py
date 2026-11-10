#!/usr/bin/env python3
"""h6_gold.py — H6 六类的 gold 推导与机械判分（零 LLM）。

每类 gold 都由**构造**机械推出，不靠人工标注：

  P1 前瞻记忆    gold = 触发条件与题面证据匹配的那条意图节点；干扰 = 同形态不同触发的意图。
  P2 错误记忆    gold = **空**（诱饵题：该属性从没写过 → 正确行为是「不知道」）；
                 对照真题 gold = 记了该属性的实体节点。
  P3 主动遗忘    gold = 遗忘前应命中、遗忘后应消失的目标节点；旁证 = 不许误伤的邻居节点。
  P4 来源监控    gold = 说出该结论的那个来源节点；误归因 = 同主题其它来源节点。
  P5 时间线重建  gold = created_at 最早的那个节点 / 某节点在 created_at 上的前驱；
                 `created_at` 与 `insert_rank` 的两种排序都要算，用于分离效应。
  P6 重构性      gold = 三要素节点；问句按「要旨/动作/数值」分档，验证是否只会字面匹配。

一致性：`verify_gold()` 会把这套推导重跑一遍，与数据集里落的 `gold_expr` 逐字段比对。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

TYPES = ["P1", "P2", "P3", "P4", "P5", "P6"]


def id_match(a: str, b: str) -> bool:
    """与 respire-cli bench 的 id 语义一致：前缀双向匹配（脱敏 id 可比）。"""
    if not a or not b:
        return False
    return a.startswith(b) or b.startswith(a)


def evaluate_expr(expr: Dict[str, Any], hits: List[Dict[str, Any]],
                  nodes: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """按 gold_expr 判一条预测。hits = [{"id","score"}...]，已按名次排序。

    返回 {correct, detail}；P2 的「正确」= 没有硬凑（诱饵属性/实体没被当答案端出来）。
    """
    kind = expr.get("kind")
    ids = [h.get("id", "") for h in hits]
    out: Dict[str, Any] = {"correct": False, "detail": {}}

    if kind == "intent":  # P1
        gold = expr["gold"]
        rank = next((i for i, x in enumerate(ids) if id_match(x, gold)), None)
        out["detail"] = {"gold": gold, "rank": rank}
        out["correct"] = rank == 0
        out["rank"] = rank

    elif kind == "no_answer":  # P2 诱饵
        ent = expr["entity"]
        attr = expr["attr"]
        # 硬凑判据：top-k 里出现了「该实体的条目」或「正文含该属性名的条目」
        hit_ids = [x for x in ids if any(id_match(x, e) for e in expr.get("entity_ids", []))]
        attr_hits = [x for x in ids
                     if attr.replace(" ", "") in (nodes.get(x, {}).get("content", "")
                                                  .replace(" ", ""))]
        out["detail"] = {"entity_hits": hit_ids, "attr_hits": attr_hits,
                         "false_hit": bool(hit_ids)}
        out["correct"] = not hit_ids
        out["false_hit"] = bool(hit_ids)

    elif kind == "recorded":  # P2 真题（记了该属性）
        gold = expr["gold"]
        rank = next((i for i, x in enumerate(ids) if id_match(x, gold)), None)
        out["detail"] = {"gold": gold, "rank": rank}
        out["correct"] = rank == 0
        out["rank"] = rank

    elif kind == "forget":  # P3
        gold = expr["gold"]
        phase = expr.get("phase", "pre")
        rank = next((i for i, x in enumerate(ids) if id_match(x, gold)), None)
        present = rank is not None
        out["detail"] = {"gold": gold, "rank": rank, "phase": phase, "present": present}
        # pre：目标应命中（present=1 正确）
        # post：目标应消失（present=1 即失败）——首辅口径 forgotten_hit 应为 0
        out["correct"] = present if phase == "pre" else (not present)
        out["present"] = present
        out["rank"] = rank

    elif kind == "source":  # P4
        gold = expr["gold"]
        others = expr.get("other_sources", [])
        rank = next((i for i, x in enumerate(ids) if id_match(x, gold)), None)
        misattr = bool(ids) and any(id_match(ids[0], o) for o in others)
        out["detail"] = {"gold": gold, "rank": rank, "misattributed": misattr,
                         "top1": ids[0] if ids else None}
        out["correct"] = rank == 0
        out["misattributed"] = misattr
        out["rank"] = rank

    elif kind == "order":  # P5
        gold = expr["gold"]
        other = expr.get("other", "")
        rank = next((i for i, x in enumerate(ids) if id_match(x, gold)), None)
        # 顺序效应：top-1 到底跟的是 created_at 还是 insert_rank
        top1 = ids[0] if ids else None
        # 象限由 nodes 提供（调用方给树节点表）；拿不到就留空
        t1n = nodes.get(top1 or "")
        t1q = ((t1n or {}).get("attrs") or {}).get("quadrant") if t1n else None
        out["detail"] = {"gold": gold, "rank": rank, "top1": top1,
                         "top1_is_insert_first": bool(top1 and id_match(top1, other)),
                         "top1_is_created_first": bool(top1 and id_match(top1, gold)),
                         "top1_quadrant": t1q}
        out["correct"] = rank == 0
        out["rank"] = rank

    elif kind == "gist":  # P6
        gold = expr["gold"]
        rank = next((i for i, x in enumerate(ids) if id_match(x, gold)), None)
        out["detail"] = {"gold": gold, "rank": rank, "subtype": expr.get("subtype")}
        out["correct"] = rank == 0
        out["rank"] = rank

    else:
        raise ValueError(f"未知 gold kind: {kind}")
    return out


def verify_gold(dataset: List[Dict[str, Any]], nodes: List[Dict[str, Any]]) -> List[str]:
    """gold 可推导性对账：把每题的 gold_expr 重新推导，与落盘值逐一比对。"""
    errors: List[str] = []
    by_id = {n["id"]: n for n in nodes}

    # 索引：按角色分桶
    intents = [n for n in nodes if n["role"] == "intent"]
    entities = [n for n in nodes if n["role"] == "entity"]
    forget_groups: Dict[str, List[Dict[str, Any]]] = {}
    source_groups: Dict[str, List[Dict[str, Any]]] = {}
    order_groups: Dict[str, List[Dict[str, Any]]] = {}
    gist_nodes = [n for n in nodes if n["role"] == "gist"]
    for n in nodes:
        if n["role"] == "forget":
            forget_groups.setdefault(n["topic"], []).append(n)
        elif n["role"] == "source":
            source_groups.setdefault(n["topic"], []).append(n)
        elif n["role"] == "order":
            order_groups.setdefault(n["topic"], []).append(n)

    for q in dataset:
        e = q["gold_expr"]
        k = e.get("kind")
        if k == "intent":
            # 同一场景会出多题，触发键会复用；唯一性靠「场景 + 触发键 + 构造序号」
            cands = [n for n in intents if n["attrs"].get("trigger_key") == e["trigger_key"]
                     and n["scenario"] == q["scenario"]
                     and n["attrs"].get("build") == e.get("build")
                     and n["attrs"].get("is_gold")]
            if len(cands) != 1:
                errors.append(f"{q['qid']}: intent gold 不唯一（{len(cands)}）")
            elif cands[0]["id"] != e["gold"]:
                errors.append(f"{q['qid']}: intent gold 与节点不符")
        elif k == "no_answer":
            # 诱饵：该属性在语料里必须真不存在（这条是 P2 的核心断言）
            attr = e["attr"].replace(" ", "")
            if any(attr in n["content"].replace(" ", "") for n in nodes):
                errors.append(f"{q['qid']}: 诱饵属性 {e['attr']} 竟然在语料里出现过")
            if not any(n["id"] == e["entity"] for n in entities):
                errors.append(f"{q['qid']}: 诱饵实体不在语料里")
            if e.get("expect_nonempty"):
                errors.append(f"{q['qid']}: 诱饵题 expect 必须为空")
        elif k == "recorded":
            ent = by_id.get(e["gold"])
            if not ent:
                errors.append(f"{q['qid']}: 真题 gold 不在树内")
            else:
                if e["attr"] not in ent["content"]:
                    errors.append(f"{q['qid']}: 真题属性 {e['attr']} 不在 gold 正文里")
        elif k == "forget":
            g = forget_groups.get(e["topic"], [])
            tgt = [n["id"] for n in g if n["attrs"].get("forget_target")]
            if len(tgt) != 1 or tgt[0] != e["gold"]:
                errors.append(f"{q['qid']}: 遗忘目标不唯一或与节点不符")
            keep = [n["id"] for n in g if not n["attrs"].get("forget_target")]
            if sorted(keep) != sorted(e.get("keep", [])):
                errors.append(f"{q['qid']}: 遗忘旁证集合与节点不符")
        elif k == "source":
            g = [n for n in source_groups.get(e["topic"], []) if n["id"] == e["gold"]]
            if len(g) != 1:
                errors.append(f"{q['qid']}: 来源 gold 不在该主题来源组内")
            else:
                if g[0]["attrs"].get("source") != e["source"]:
                    errors.append(f"{q['qid']}: 来源标记不符")
        elif k == "order":
            g = sorted(order_groups.get(e["topic"], []), key=lambda n: n["created_at"])
            if len(g) != 4:
                errors.append(f"{q['qid']}: 时序组应有 4 个事件，实为 {len(g)}")
                continue
            if q["gold_expr"]["mode"] == "earliest":
                if g[0]["id"] != e["gold"]:
                    errors.append(f"{q['qid']}: 最早事件与 created_at 排序不符")
            else:
                # IV 是 created_at 最晚的一件，前驱就是排序里它前一位（应为 III）
                ids = [n["id"] for n in g]
                if e.get("anchor") not in ids:
                    errors.append(f"{q['qid']}: 锚点 {e.get('anchor')} 不在时序组 {e.get('topic')} 内")
                    continue
                if len(g) < 2 or ids[-1] != e["anchor"]:
                    errors.append(f"{q['qid']}: 锚点不是时序组里最晚的一件 {ids}")
                    continue
                if g[-2]["id"] != e["gold"]:
                    errors.append(
                        f"{q['qid']}: 前驱不符 gold={e['gold']} "
                        f"实际前驱={g[-2]['id']} 顺序={ids}")
        elif k == "gist":
            if e["gold"] not in by_id:
                errors.append(f"{q['qid']}: gist gold 不在树内")
            elif q["gold_expr"].get("subtype") not in ("gist", "action", "value"):
                errors.append(f"{q['qid']}: gist 子型非法")
    return errors


def main() -> int:
    """独立自检入口：python3 h6_gold.py --verify <tree.json> <dataset.jsonl>"""
    import json
    import sys
    if len(sys.argv) < 4 or "--verify" not in sys.argv:
        print(__doc__)
        return 0
    tree = json.load(open(sys.argv[2], encoding="utf-8"))
    ds = [json.loads(x) for x in open(sys.argv[3], encoding="utf-8") if x.strip()]
    errs = verify_gold(ds, tree["nodes"])
    if errs:
        print("[h6_gold] FAIL")
        for e in errs[:20]:
            print("  -", e)
        return 1
    print(f"[h6_gold] OK — {len(ds)} 题 gold 全部可机械推导")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

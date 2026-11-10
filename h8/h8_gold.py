#!/usr/bin/env python3
"""h8_gold.py — H8 四子类的 gold 推导与机械判分（零 LLM）。

四子类 gold 都由**构造**机械推出，不靠人工标注：

  C1 一次观察泛化  gold = 那条观察记录（题面给新实例，规则在观察正文里）。
                   题面与观察正文**词面错位**（连续重合 <6 字），测检索与泛化的分界。
  C2 跨间隔召回    gold = 那条老条目（created_at 按 1h/1d/7d/30d 回拨）；
                   正向断言「老条目召回率不为 0」（本轮不跑分，只留断言位）。
  C3 远期检索      gold = 强化事件（同 topic 5 条灰尘池 + 1 条平凡 + 1 条强化）；
                   指标 = 不被淹没率（强化件在 top-k 内）。
  C4 增量编辑      gold = 最后一版规则（旧版 superseded_by 指向新版）；
                   指标 = 认最新版率 + 旧条目霸榜率（复现「排序不用取代标记」缺口）。

一致性：`verify_gold()` 把这套推导重跑一遍，与数据集里落的 `gold_expr` 逐字段比对；
       C1 的题面词面错位与 C4 的取代边完整性是两条核心断言。
"""
from __future__ import annotations

from typing import Any, Dict, List

TYPES = ["C1", "C2", "C3", "C4"]


def id_match(a: str, b: str) -> bool:
    """与 respire-cli bench 的 id 语义一致：前缀双向匹配（脱敏 id 可比）。"""
    if not a or not b:
        return False
    return a.startswith(b) or b.startswith(a)


def lcs_len(src: str, qq: str) -> int:
    """最长公共连续子串（DP），词面错位判据用。"""
    if not src or not qq:
        return 0
    prev = [0] * (len(qq) + 1)
    best = 0
    for i in range(1, len(src) + 1):
        cur = [0] * (len(qq) + 1)
        for j in range(1, len(qq) + 1):
            if src[i - 1] == qq[j - 1]:
                cur[j] = prev[j - 1] + 1
                best = max(best, cur[j])
        prev = cur
    return best


def evaluate_expr(expr: Dict[str, Any], hits: List[Dict[str, Any]],
                  nodes: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """按 gold_expr 判一条预测。hits = [{"id","score"}...]，已按名次排序。"""
    kind = expr.get("kind")
    ids = [h.get("id", "") for h in hits]
    out: Dict[str, Any] = {"correct": False, "detail": {}}

    if kind == "generalize":   # C1：gold=观察记录
        gold = expr["gold"]
        rank = next((i for i, x in enumerate(ids) if id_match(x, gold)), None)
        out["detail"] = {"gold": gold, "rank": rank, "rule_attr": expr.get("rule_attr")}
        out["rank"] = rank
        out["correct"] = rank == 0
        out["hit_at_5"] = rank is not None and rank < 5

    elif kind == "aged":       # C2：gold=老条目
        gold = expr["gold"]
        rank = next((i for i, x in enumerate(ids) if id_match(x, gold)), None)
        out["detail"] = {"gold": gold, "age": expr.get("age"), "rank": rank}
        out["rank"] = rank
        out["correct"] = rank == 0
        out["hit_at_5"] = rank is not None and rank < 5
        # 正向断言位：老条目召回率不为 0（本轮不跑分，只留字段）
        out["aged_hit"] = rank is not None

    elif kind == "salience":   # C3：gold=强化件，不被淹没率
        gold = expr["gold"]
        rank = next((i for i, x in enumerate(ids) if id_match(x, gold)), None)
        out["detail"] = {"gold": gold, "rank": rank,
                         "pool_sizes": expr.get("pool_sizes")}
        out["rank"] = rank
        out["correct"] = rank == 0
        out["hit_at_5"] = rank is not None and rank < 5
        out["not_buried"] = rank is not None   # 不被淹没（至少进 top-k）

    elif kind == "edited":     # C4：gold=最新版
        gold = expr["gold"]
        rank = next((i for i, x in enumerate(ids) if id_match(x, gold)), None)
        old_ids = expr.get("old_ids", [])
        stale_rank = next((i for i, x in enumerate(ids)
                           if any(id_match(x, o) for o in old_ids)), None)
        out["detail"] = {"gold": gold, "rank": rank, "old_ids": old_ids,
                         "stale_rank": stale_rank, "steps": expr.get("steps")}
        out["rank"] = rank
        out["correct"] = rank == 0
        out["hit_at_5"] = rank is not None and rank < 5
        # 旧条目霸榜率：旧版排在最新版前面（复现「排序不用取代标记」缺口）
        out["stale_top1"] = stale_rank == 0
        out["stale_ahead"] = (stale_rank is not None
                              and (rank is None or stale_rank < rank))

    else:
        raise SystemExit(f"未知 gold_expr.kind: {kind}")
    return out


def verify_gold(dataset: List[Dict[str, Any]], nodes: List[Dict[str, Any]]) -> List[str]:
    """gold 可推导性对账：把每题的 gold_expr 重新推导，与落盘值逐一比对。

    核心断言：
      C1 题面与观察正文词面错位（连续重合 <6 字，非字面复制）；
      C4 取代边完整（旧版 superseded_by 指向下一版，最后一版为空）。
    """
    errors: List[str] = []
    by_id = {n["id"]: n for n in nodes}

    for q in dataset:
        e = q["gold_expr"]
        k = e.get("kind")

        if k == "generalize":   # C1
            nid = e.get("gold")
            if nid not in by_id:
                errors.append(f"{q['qid']}: C1 gold 不在树内 {nid}")
                continue
            src = by_id[nid]["content"].replace(" ", "")
            qq = q["query"].replace(" ", "")
            best = lcs_len(src, qq)
            if best >= 6:
                errors.append(f"{q['qid']}: C1 题面与观察正文最长连续重合 {best} 字（≥6，未词面错位）")
            if q["expect"] != [nid]:
                errors.append(f"{q['qid']}: C1 expect 与 gold 不一致")

        elif k == "aged":       # C2
            nid = e.get("gold")
            if nid not in by_id:
                errors.append(f"{q['qid']}: C2 gold 不在树内 {nid}")
                continue
            entry = by_id[nid]
            if entry.get("created_at") != e.get("created_at"):
                errors.append(f"{q['qid']}: C2 created_at 落盘 {e.get('created_at')} "
                              f"≠ 树内 {entry.get('created_at')}")
            if q["expect"] != [nid]:
                errors.append(f"{q['qid']}: C2 expect 与 gold 不一致")

        elif k == "salience":   # C3
            nid = e.get("gold")
            if nid not in by_id:
                errors.append(f"{q['qid']}: C3 gold 不在树内 {nid}")
                continue
            if by_id[nid].get("role") != "salient":
                errors.append(f"{q['qid']}: C3 gold 不是强化件（role={by_id[nid].get('role')}）")
            pool = e.get("pool_sizes", {})
            # 灰尘池条数：同 topic 下 role=dust 的节点数
            topic = by_id[nid].get("topic", "")
            n_dust = sum(1 for n in nodes
                         if n.get("topic") == topic and n.get("role") == "dust")
            if n_dust != pool.get("dust"):
                errors.append(f"{q['qid']}: C3 灰尘池实数 {n_dust} ≠ 落盘 {pool.get('dust')}")
            if q["expect"] != [nid]:
                errors.append(f"{q['qid']}: C3 expect 与 gold 不一致")

        elif k == "edited":     # C4
            nid = e.get("gold")
            if nid not in by_id:
                errors.append(f"{q['qid']}: C4 gold 不在树内 {nid}")
                continue
            vids = e.get("version_ids", [])
            # 取代边完整性：v1..v(n-1) 的 superseded_by 指向下一版，最后一版为空
            for i, vid in enumerate(vids):
                if vid not in by_id:
                    errors.append(f"{q['qid']}: C4 版本 {vid} 不在树内")
                    continue
                want = vids[i + 1] if i + 1 < len(vids) else ""
                got = by_id[vid].get("superseded_by", "")
                if got != want:
                    errors.append(f"{q['qid']}: C4 版本 {vid} superseded_by={got!r} ≠ {want!r}")
            if q["expect"] != [nid]:
                errors.append(f"{q['qid']}: C4 expect 与 gold 不一致")

        else:
            errors.append(f"{q['qid']}: 未知 gold_expr.kind {k}")

    return errors

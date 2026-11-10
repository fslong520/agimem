#!/usr/bin/env python3
"""score_h6.py — H6「人 vs 数据库」六类判分（零 LLM）。

用法：
    python3 score_h6.py --verify-only
        # 只验 gold：把 h6_gold.verify_gold 重跑一遍，与 dataset 对账
    python3 score_h6.py --dataset dataset/h6_evalset.jsonl \
        --predictions fixtures/h6-perfect.jsonl [--topk 5] [--json]

预测文件（JSONL，一行一题）：
    {"qid":"p1-001","query":"...","hits":[{"id":"hl2A0001","score":0.91}]}
join 规则：优先 qid，其次 query 原文精确匹配。
id 匹配语义与 respire-cli/cli/src/bench.rs 的 id_match 一致（前缀双向），见 h6_gold.id_match。

六类指标：
  P1 intent_hit@1/@5           条件式意图是否被召回
  P2 lure_false_hit            诱饵题里把「该实体」当答案端出来的比例（越低越好）
  P2 know_auc                  可分离性 AUC：真查询 top1 分 vs 诱饵查询 top1 分，
                               AUC=0.5 说明系统分不清「知道」与「不知道」
  P3 forgotten_hit             遗忘后目标仍被召回的比例（应为 0）
  P3 collateral_hit            遗忘后邻居仍被召回的比例（应为 1）
  P4 source_attribution_hit@1  来源归因命中；misattributed_rate 同主题误归因
  P5 order_correct@1           问最早给最早 / 问前驱给前驱；
                               created_at_effect 用 before 题的 top-1 象限判
  P6 gist_hit@1 / action_hit@1 / value_hit@1   三档分层
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional

import h6_gold as hg

HERE = os.path.dirname(os.path.abspath(__file__))
Z95 = 1.959963984540054

# 六类主指标权重（与 H4 同源的等权口径，便于并排读）
WEIGHTS = {t: 1.0 / 6 for t in hg.TYPES}


def wilson_ci(k: int, n: int, z: float = Z95) -> Dict[str, Any]:
    if n <= 0:
        return {"point": None, "lo": None, "hi": None, "n": 0, "k": k}
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return {"point": p, "lo": max(0.0, center - half), "hi": min(1.0, center + half),
            "n": n, "k": k, "method": "wilson", "z": z}


def fmt_ci(c: Optional[Dict[str, Any]], nd: int = 3) -> str:
    if not c or c.get("point") is None:
        return "n/a"
    return f"{c['point']:.{nd}f} [{c['lo']:.{nd}f}, {c['hi']:.{nd}f}]"


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise SystemExit(f"{path} 第 {i} 行解析失败: {e}")
    return out


def extract_hits(rec: Any) -> List[Dict[str, Any]]:
    if isinstance(rec, list):
        items = rec
    elif isinstance(rec, dict):
        if isinstance(rec.get("hits"), list):
            items = rec["hits"]
        elif isinstance(rec.get("details"), list):
            items = rec["details"]
        else:
            raise SystemExit(f"预测记录缺 hits/details: "
                             f"{json.dumps(rec, ensure_ascii=False)[:120]}")
    else:
        raise SystemExit(f"预测记录类型非法: {type(rec)}")
    hits = []
    for h in items:
        if not isinstance(h, dict):
            continue
        hid = h.get("id")
        if not isinstance(hid, str) or not hid:
            continue
        sc = h.get("score")
        try:
            sc = float(sc)
        except (TypeError, ValueError):
            sc = 0.0
        hits.append({"id": hid, "score": sc})
    hits.sort(key=lambda x: (-x["score"], x["id"]))
    return hits


def score_dataset(dataset: List[Dict[str, Any]], preds: List[Dict[str, Any]],
                  tree_nodes: List[Dict[str, Any]], topk: int = 5) -> Dict[str, Any]:
    by_id = {n["id"]: n for n in tree_nodes}
    pred_by_qid = {p.get("qid"): p for p in preds if p.get("qid")}
    pred_by_q = {p.get("query"): p for p in preds if p.get("query")}

    per_q: List[Dict[str, Any]] = []
    for q in dataset:
        pred = pred_by_qid.get(q["qid"]) or pred_by_q.get(q["query"])
        hits = extract_hits(pred) if pred else []
        ev = hg.evaluate_expr(q["gold_expr"], hits, by_id)
        row = {"qid": q["qid"], "type": q["type"], "subtype": q.get("subtype", ""),
               "correct": bool(ev["correct"]), "detail": ev.get("detail", {}),
               "top1_score": hits[0]["score"] if hits else None,
               "top1_id": hits[0]["id"] if hits else None,
               "rank": ev.get("rank")}
        per_q.append(row)

    # 分桶
    buckets: Dict[str, List[Dict[str, Any]]] = {t: [] for t in hg.TYPES}
    for row in per_q:
        buckets[row["type"]].append(row)

    def rate(rows: List[Dict[str, Any]], key: str = "correct") -> Optional[float]:
        if not rows:
            return None
        return sum(1 for r in rows if r.get(key)) / len(rows)

    def ci_rate(rows: List[Dict[str, Any]], key: str = "correct") -> Dict[str, Any]:
        k = sum(1 for r in rows if r.get(key))
        return wilson_ci(k, len(rows))

    summary: Dict[str, Any] = {"n_total": len(per_q), "topk": topk, "types": {}}

    # P1 前瞻记忆
    p1 = buckets["P1"]
    summary["types"]["P1"] = {
        "name": "前瞻记忆", "n": len(p1),
        "intent_hit@1": ci_rate(p1),
        "intent_hit@5": ci_rate([r for r in p1 if r["rank"] is not None and r["rank"] < 5]),
    }

    # P2 错误记忆：诱饵不硬凑 + 可分离性 AUC
    p2_all = buckets["P2"]
    lures = [r for r in p2_all if r["subtype"] == "lure"]
    reals = [r for r in p2_all if r["subtype"] == "recorded"]
    lure_false = [r for r in lures if r["detail"].get("false_hit")]
    auc = _auc([r["top1_score"] for r in reals if r["top1_score"] is not None],
               [r["top1_score"] for r in lures if r["top1_score"] is not None])
    summary["types"]["P2"] = {
        "name": "错误记忆（诱饵）", "n": len(p2_all),
        "n_lure": len(lures), "n_recorded": len(reals),
        "lure_false_hit": ci_rate(lures, "correct"),  # correct = 未硬凑（越高越好）
        "lure_hard_code_rate": wilson_ci(
            sum(1 for r in lures if r["detail"].get("false_hit")), len(lures)),
        "recorded_hit@1": ci_rate(reals),
        "know_auc": auc,
    }

    # P3 主动遗忘
    p3 = buckets["P3"]
    pre = [r for r in p3 if r["subtype"] == "pre"]
    post = [r for r in p3 if r["subtype"] == "post"]
    keep_map = {q["qid"]: q["gold_expr"].get("keep", []) for q in dataset if q["type"] == "P3"}
    coll_k = 0
    coll_n = 0
    for r in post:
        keep = keep_map.get(r["qid"], [])
        pred = pred_by_qid.get(r["qid"]) or pred_by_q.get(next(
            (q["query"] for q in dataset if q["qid"] == r["qid"]), ""))
        hits = extract_hits(pred) if pred else []
        hit_ids = [h["id"] for h in hits]
        for kid in keep:
            coll_n += 1
            if any(hg.id_match(hid, kid) for hid in hit_ids):
                coll_k += 1
    # forgotten_hit = post 题目标仍被召回的比例（首辅口径：应为 0）
    # 与 r["correct"] 相反：correct(post)=目标已消失，forgotten_hit=目标还在
    n_still = sum(1 for r in post if r["detail"].get("present"))
    summary["types"]["P3"] = {
        "name": "主动遗忘", "n": len(p3),
        "pre_hit": ci_rate(pre),
        "forgotten_hit": wilson_ci(n_still, len(post)),  # 应为 0
        "target_gone_rate": ci_rate(post),  # = 1 − forgotten_hit
        "collateral_hit": wilson_ci(coll_k, coll_n),  # 应接近 1
        "note": "forgotten_hit=遗忘后目标仍被召回的比例（应 0）；"
                "collateral_hit=邻居仍可召回（应 1）",
    }

    # P4 来源监控
    p4 = buckets["P4"]
    mis = [r for r in p4 if r["detail"].get("misattributed")]
    summary["types"]["P4"] = {
        "name": "来源监控", "n": len(p4),
        "source_attribution_hit@1": ci_rate(p4),
        "misattributed_rate": wilson_ci(len(mis), len(p4)),
    }

    # P5 时间线重建
    p5 = buckets["P5"]
    earliest = [r for r in p5 if r["subtype"] == "earliest"]
    before = [r for r in p5 if r["subtype"] == "before"]
    created_first = [r for r in before if r["detail"].get("top1_is_created_first")]
    insert_first = [r for r in before if r["detail"].get("top1_is_insert_first")]
    # neither = 两个条件都不满足的题（直接计数；n_c+n_i 可能 > len，因为同一题可同时匹配）
    neither_rows = [r for r in before
                    if not r["detail"].get("top1_is_created_first")
                    and not r["detail"].get("top1_is_insert_first")]
    n_c, n_i = len(created_first), len(insert_first)
    # neither 里要分清：top1 落象限 IV（纯锚点复述，题面引号原文命中）还是组内其它步
    qdist: Dict[str, int] = {}
    for r in neither_rows:
        q = r["detail"].get("top1_quadrant") or "?"
        qdist[q] = qdist.get(q, 0) + 1
    if n_c > n_i:
        verdict, verdict_why = "use_created_at", "top-1 更常落象限 III（早 created、晚插入）"
    elif n_i > n_c:
        verdict, verdict_why = "use_insert_order", "top-1 更常落象限 II（晚 created、早插入）"
    else:
        verdict, verdict_why = "neither", "top-1 落 III 与 II 的格数相同（或都不落）"
    summary["types"]["P5"] = {
        "name": "时间线重建", "n": len(p5),
        "order_correct@1": ci_rate(p5),
        "earliest_hit@1": ci_rate(earliest),
        "before_hit@1": ci_rate(before),
        "created_at_effect": {
            "n_before": len(before),
            "top1_follows_created_at": wilson_ci(n_c, len(before)),
            "top1_follows_insert": wilson_ci(n_i, len(before)),
            "top1_neither": wilson_ci(len(neither_rows), len(before)),
            "neither_quadrant_dist": qdist,
            "neither_is_anchor_quadrant_iv": qdist.get("IV", 0),
            "verdict": verdict,
            "verdict_why": verdict_why,
            "note": "before 题的 gold=象限 III（早 created、晚插入），"
                    "other=象限 II（晚 created、早插入）；"
                    "三选一：use_created_at / use_insert_order / neither；"
                    "neither 里 top1_quadrant_dist 区分锚点 IV 复述与组内其它步",
        },
    }

    # P6 重构性
    p6 = buckets["P6"]
    by_sub: Dict[str, List[Dict[str, Any]]] = {}
    for r in p6:
        by_sub.setdefault(r["subtype"], []).append(r)
    summary["types"]["P6"] = {
        "name": "重构性", "n": len(p6),
        "gist_hit@1": ci_rate(by_sub.get("gist", [])),
        "action_hit@1": ci_rate(by_sub.get("action", [])),
        "value_hit@1": ci_rate(by_sub.get("value", [])),
        "note": "三档都应能答；若 value 强而 gist 弱，说明只是字面检索",
    }

    # 等权总分（六类主指标各 1/6，全部取「越高越好」）
    # P3 用 target_gone_rate（目标已消失），不用 forgotten_hit（那是越低越好）
    main_keys = {
        "P1": "intent_hit@1", "P2": "lure_false_hit", "P3": "target_gone_rate",
        "P4": "source_attribution_hit@1", "P5": "order_correct@1", "P6": "gist_hit@1",
    }
    total = 0.0
    for t, key in main_keys.items():
        c = summary["types"][t].get(key)
        if c and c.get("point") is not None:
            total += WEIGHTS[t] * c["point"]
    summary["composite_equal_weight"] = total
    summary["per_question"] = per_q
    return summary


def _auc(pos: List[float], neg: List[float]) -> Optional[Dict[str, Any]]:
    """可分离性 AUC：真查询 top1 分（正）vs 诱饵 top1 分（负）。

    AUC = P(pos > neg) + 0.5 * P(tie)。n_pos=0 或 n_neg=0 时返回 None。
    CI 用 bootstrap（seed 固定，可复现）。
    """
    if not pos or not neg:
        return {"point": None, "n_pos": len(pos), "n_neg": len(neg),
                "note": "正/负样本有一侧为空"}
    wins = ties = 0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1
            elif p == n:
                ties += 1
    total = len(pos) * len(neg)
    auc = (wins + 0.5 * ties) / total
    # bootstrap CI
    import random as _r
    rng = _r.Random(20261109)
    boots = []
    for _ in range(2000):
        bp = [pos[rng.randrange(len(pos))] for _ in range(len(pos))]
        bn = [neg[rng.randrange(len(neg))] for _ in range(len(neg))]
        w = t = 0
        for p in bp:
            for n in bn:
                if p > n:
                    w += 1
                elif p == n:
                    t += 1
        boots.append((w + 0.5 * t) / (len(bp) * len(bn)))
    boots.sort()
    lo = boots[int(0.025 * len(boots))]
    hi = boots[int(0.975 * len(boots)) - 1]
    return {"point": auc, "lo": lo, "hi": hi, "n_pos": len(pos), "n_neg": len(neg),
            "method": "mann-whitney", "ci_method": "bootstrap-2000-seed20261109",
            "note": "0.5=不可分；>0.5=能区分知道/不知道"}


def verify_only(dataset: List[Dict[str, Any]], tree_nodes: List[Dict[str, Any]]) -> int:
    errs = hg.verify_gold(dataset, tree_nodes)
    if errs:
        print("[score_h6] gold 对账 FAIL")
        for e in errs[:20]:
            print("  -", e)
        return 1
    print(f"[score_h6] gold 对账 OK — {len(dataset)} 题全部可机械推导")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="H6 分水岭判分")
    ap.add_argument("--dataset", default=os.path.join(HERE, "dataset", "h6_evalset.jsonl"))
    ap.add_argument("--tree", default=os.path.join(HERE, "data", "h6_tree.json"))
    ap.add_argument("--predictions", default=None)
    ap.add_argument("--topk", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--verify-only", action="store_true")
    args = ap.parse_args()

    dataset = load_jsonl(args.dataset)
    with open(args.tree, encoding="utf-8") as f:
        tree = json.load(f)
    nodes = tree["nodes"]

    if args.verify_only:
        return verify_only(dataset, nodes)

    if not args.predictions:
        print("[score_h6] 缺 --predictions；只做 gold 对账")
        return verify_only(dataset, nodes)

    preds = load_jsonl(args.predictions)
    summary = score_dataset(dataset, preds, nodes, topk=args.topk)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    print(f"[score_h6] n={summary['n_total']}  等权总分="
          f"{summary['composite_equal_weight']:.3f}")
    for t in hg.TYPES:
        info = summary["types"][t]
        print(f"  {t} {info['name']} n={info['n']}")
        for k, v in info.items():
            if k in ("name", "n", "note") or not isinstance(v, dict):
                continue
            if "point" in v:
                print(f"    {k}: {fmt_ci(v)}")
            else:
                for k2, v2 in v.items():
                    if isinstance(v2, dict) and "point" in v2:
                        print(f"    {k}.{k2}: {fmt_ci(v2)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

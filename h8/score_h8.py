#!/usr/bin/env python3
"""score_h8.py — H8「记忆动力学层」四子类判分（零 LLM）。

用法：
    python3 score_h8.py --verify-only
        # 只验 gold：把 h8_gold.verify_gold 重跑一遍，与 dataset 对账
    python3 score_h8.py --dataset dataset/h8_evalset.jsonl \
        --predictions fixtures/h8-perfect.jsonl [--topk 5] [--json]

预测文件（JSONL，一行一题）：
    {"qid":"q001","query":"...","hits":[{"id":"h8A0001","score":0.91}]}
join 规则：优先 qid，其次 query 原文精确匹配。
id 匹配语义与 respire-cli/cli/src/bench.rs 的 id_match 一致（前缀双向），见 h8_gold.id_match。

四子类指标：
  C1 一次观察泛化  generalize_hit@1 / generalize_hit@5（gold=观察记录）。
  C2 跨间隔召回    aged_hit@1 / aged_hit@5，按 age∈{1h,1d,7d,30d} 分层；
                   正向断言位：aged_hit@k ≠ 0（老条目召回率不为 0）。
  C3 这期检索      not_buried@1 / not_buried@5（不被淹没率，gold=强化件）。
  C4 增量编辑      edited_hit@1 / edited_hit@5（认最新版）+ stale_top1_rate /
                   stale_ahead_rate（旧条目霸榜率，复现「排序不用取代标记」缺口）。

本轮不跑分：无 predictions 时只跑 --verify-only。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional

import h8_gold as hg

HERE = os.path.dirname(os.path.abspath(__file__))
Z95 = 1.959963984540054


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
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def extract_hits(rec: Any) -> List[Dict[str, Any]]:
    if isinstance(rec, dict) and isinstance(rec.get("hits"), list):
        return rec["hits"]
    return []


def index_predictions(preds: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    by_qid = {p.get("qid"): p for p in preds if p.get("qid")}
    by_query = {p.get("query"): p for p in preds if p.get("query")}
    return {"by_qid": by_qid, "by_query": by_query}


def find_pred(pred_idx: Dict[str, Dict[str, Any]], q: Dict[str, Any]) -> Dict[str, Any]:
    return pred_idx["by_qid"].get(q.get("qid")) or pred_idx["by_query"].get(q.get("query")) or {}


def score_dataset(dataset: List[Dict[str, Any]], preds: List[Dict[str, Any]],
                  tree_nodes: List[Dict[str, Any]], topk: int = 5) -> Dict[str, Any]:
    by_id = {n["id"]: n for n in tree_nodes}
    pred_idx = index_predictions(preds)
    rows: List[Dict[str, Any]] = []

    for q in dataset:
        p = find_pred(pred_idx, q)
        hits = extract_hits(p)[:topk]
        res = hg.evaluate_expr(q["gold_expr"], hits, by_id)
        rows.append({"qid": q["qid"], "type": q["type"], "subtype": q.get("subtype"),
                     "query": q["query"], "gold_expr": q["gold_expr"],
                     "hit_ids": [h.get("id") for h in hits], **res})

    def sub(t: str) -> List[Dict[str, Any]]:
        return [r for r in rows if r["type"] == t]

    def ci(rows_: List[Dict[str, Any]], key: str = "correct") -> Dict[str, Any]:
        k = sum(1 for r in rows_ if r.get(key))
        return wilson_ci(k, len(rows_))

    # ── C1 一次观察泛化 ──
    c1 = sub("C1")
    c1_m = {"hit@1": ci(c1), "hit@5": ci(c1, "hit_at_5")}

    # ── C2 跨间隔召回：按 age 分层 + 正向断言位 ──
    c2 = sub("C2")
    c2_m = {"hit@1": ci(c2), "hit@5": ci(c2, "hit_at_5"), "by_age": {}}
    for age in ("1h", "1d", "7d", "30d"):
        rr = [r for r in c2 if r["gold_expr"].get("age") == age]
        if rr:
            k1 = sum(1 for r in rr if r.get("correct"))
            k5 = sum(1 for r in rr if r.get("hit_at_5"))
            c2_m["by_age"][f"age-{age}"] = {"n": len(rr),
                                            "hit@1": wilson_ci(k1, len(rr)),
                                            "hit@5": wilson_ci(k5, len(rr))}
    # 正向断言：老条目召回率不为 0（全部年龄档 hit@5 之和）
    aged_k = sum(1 for r in c2 if r.get("aged_hit"))
    c2_m["aged_hit@5"] = wilson_ci(aged_k, len(c2))
    c2_m["aged_nonzero"] = aged_k > 0

    # ── C3 远期检索：不被淹没率 ──
    c3 = sub("C3")
    c3_m = {"not_buried@1": ci(c3), "not_buried@5": ci(c3, "not_buried"),
            "hit@1": ci(c3), "hit@5": ci(c3, "hit_at_5")}

    # ── C4 增量编辑：认最新版 + 旧条目霸榜 ──
    c4 = sub("C4")
    k_stale_top1 = sum(1 for r in c4 if r.get("stale_top1"))
    k_stale_ahead = sum(1 for r in c4 if r.get("stale_ahead"))
    c4_m = {"edited_hit@1": ci(c4), "edited_hit@5": ci(c4, "hit_at_5"),
            "stale_top1_rate": wilson_ci(k_stale_top1, len(c4)),
            "stale_ahead_rate": wilson_ci(k_stale_ahead, len(c4))}

    summary = {"n_total": len(rows), "scored": len(rows),
               "distribution": {t: sum(1 for r in rows if r["type"] == t) for t in hg.TYPES},
               "C1": c1_m, "C2": c2_m, "C3": c3_m, "C4": c4_m,
               "params": {"topk": topk}}
    return {"summary": summary, "rows": rows}


def verify_only(dataset: List[Dict[str, Any]], tree_nodes: List[Dict[str, Any]]) -> int:
    errs = hg.verify_gold(dataset, tree_nodes)
    if errs:
        print("[verify] FAIL — gold 复算不一致:")
        for e in errs[:15]:
            print("  -", e)
        return 1
    print(f"[verify] OK — {len(dataset)} 题 gold 全部由构造重算一致")
    return 0


def print_panel(summ: Dict[str, Any]) -> None:
    print("=== H8 记忆动力学层 判分结果 ===")
    print(f"总题量 {summ['n_total']} | topk={summ['params']['topk']}")
    print("分布: " + " | ".join(f"{t}={summ['distribution'][t]}" for t in hg.TYPES))
    c1 = summ["C1"]
    print(f"[C1 一次观察泛化]  hit@1={fmt_ci(c1['hit@1'])}  hit@5={fmt_ci(c1['hit@5'])}")
    c2 = summ["C2"]
    print(f"[C2 跨间隔召回]  hit@1={fmt_ci(c2['hit@1'])}  hit@5={fmt_ci(c2['hit@5'])}  "
          f"aged_hit@5={fmt_ci(c2['aged_hit@5'])} nonzero={c2['aged_nonzero']}")
    for a, v in c2["by_age"].items():
        print(f"    {a}: n={v['n']} hit@1={fmt_ci(v['hit@1'])} hit@5={fmt_ci(v['hit@5'])}")
    c3 = summ["C3"]
    print(f"[C3 远期检索]  not_buried@1={fmt_ci(c3['not_buried@1'])}  "
          f"not_buried@5={fmt_ci(c3['not_buried@5'])}")
    c4 = summ["C4"]
    print(f"[C4 增量编辑]  edited_hit@1={fmt_ci(c4['edited_hit@1'])}  "
          f"edited_hit@5={fmt_ci(c4['edited_hit@5'])}")
    print(f"    stale_top1_rate={fmt_ci(c4['stale_top1_rate'])}  "
          f"stale_ahead_rate={fmt_ci(c4['stale_ahead_rate'])}")


def main() -> int:
    ap = argparse.ArgumentParser(description="H8 四子类判分")
    ap.add_argument("--dataset", default=os.path.join(HERE, "dataset", "h8_evalset.jsonl"))
    ap.add_argument("--tree", default=os.path.join(HERE, "data", "h8_tree.json"))
    ap.add_argument("--predictions", default=None)
    ap.add_argument("--topk", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--verify-only", action="store_true")
    args = ap.parse_args()

    tree = json.load(open(args.tree, encoding="utf-8"))
    dataset = load_jsonl(args.dataset)
    tree_nodes = tree["nodes"]

    if args.verify_only:
        return verify_only(dataset, tree_nodes)

    if not args.predictions:
        print("缺 --predictions（本轮不跑分只验 gold 时用 --verify-only）", file=sys.stderr)
        return 2
    preds = load_jsonl(args.predictions)
    out = score_dataset(dataset, preds, tree_nodes, args.topk)
    if args.json:
        print(json.dumps(out["summary"], ensure_ascii=False, indent=2))
    else:
        print_panel(out["summary"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

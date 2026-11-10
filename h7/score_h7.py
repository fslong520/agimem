#!/usr/bin/env python3
"""score_h7.py — H7「跨跳与诚实层」四子类判分（零 LLM）。

用法：
    python3 score_h7.py --verify-only
        # 只验 gold：把 h7_gold.verify_gold 重跑一遍，与 dataset 对账
    python3 score_h7.py --dataset dataset/h7_evalset.jsonl \
        --predictions fixtures/h7-perfect.jsonl [--topk 5] [--json]

预测文件（JSONL，一行一题）：
    {"qid":"q001","query":"...","hits":[{"id":"h7A0001","score":0.91}]}
join 规则：优先 qid，其次 query 原文精确匹配。
id 匹配语义与 respire-cli/cli/src/bench.rs 的 id_match 一致（前缀双向），见 h7_gold.id_match。

四子类指标：
  L1 多跳链    chain_hit@1 / chain_hit@5，按链深 hops∈{1,2,3,4} 分层报；
  L2 混跳辨析  mixed_accuracy（答对跳数的比例）；
  L3 缺证据拒答 abstain_precision / abstain_recall（对 in_unwritten+off_spectrum 两档）
                + closed_ended_F1（answered 档作答正确率的双侧 F1）；
  L4 增广认同  aug_hit@1 / aug_hit@5（golden 池），按 rewrite/rephrase/reorder 分式。

诚实层口径：
  abstain_precision = 该拒答而没硬凑的比例（分母=真 abstain 题）
  abstain_recall    = 判为 abstain 的题里真该 abstain 的比例（分母=判 abstain 题）
  closed_ended_F1   = answered 档「该答且答对」的 F1，与 abstain 双侧对照。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional

import h7_gold as hg

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
    p = pred_idx["by_qid"].get(q.get("qid")) or pred_idx["by_query"].get(q.get("query")) or {}
    return p


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
                     "hit_ids": [h.get("id") for h in hits],
                     **res})

    def sub(t: str) -> List[Dict[str, Any]]:
        return [r for r in rows if r["type"] == t]

    def ci(rows_: List[Dict[str, Any]], key: str = "correct") -> Dict[str, Any]:
        k = sum(1 for r in rows_ if r.get(key))
        return wilson_ci(k, len(rows_))

    # ── L1 多跳链：按 hops 分层 hit@1/5 ──
    l1 = sub("L1")
    l1_by_hop: Dict[str, Dict[str, Any]] = {}
    for hop in (1, 2, 3, 4):
        rr = [r for r in l1 if (r["gold_expr"].get("hops") == hop)]
        if rr:
            k1 = sum(1 for r in rr if r.get("correct"))
            k5 = sum(1 for r in rr if r.get("hit_at_5"))
            l1_by_hop[f"hops{hop}"] = {"n": len(rr),
                                       "hit@1": wilson_ci(k1, len(rr)),
                                       "hit@5": wilson_ci(k5, len(rr))}
    l1_m = {"hit@1": ci(l1), "hit@5": ci(l1, "hit_at_5"), "by_hop": l1_by_hop}

    # ── L2 混跳辨析 ──
    l2 = sub("L2")
    l2_m = {"accuracy": ci(l2)}
    for hc in (2, 3):
        rr = [r for r in l2 if r["gold_expr"].get("hop_count") == hc]
        if rr:
            l2_m[f"hop{hc}"] = {"n": len(rr), "accuracy": ci(rr)}

    # ── L3 缺证据拒答：abstain precision/recall + closed_ended F1 ──
    l3 = sub("L3")
    abstain_gold = [r for r in l3 if r["gold_expr"]["tier"] != "answered"]   # 应 abstain
    answered = [r for r in l3 if r["gold_expr"]["tier"] == "answered"]        # 应作答
    # 判为 abstain = 预测没把诱饵实体端出来（false_hit False）或 answered 档没答对
    # abstain 判定：对 abstain 档 = correct（没硬凑）；对 answered 档 = 没命中（漏答）
    def said_abstain(r: Dict[str, Any]) -> bool:
        if r["gold_expr"]["tier"] != "answered":
            return not r.get("false_hit")          # 该拒答且没硬凑 = 判 abstain 且对
        return not r.get("correct")                # 该作答但没对 = 判 abstain（错拒）
    tp = sum(1 for r in abstain_gold if said_abstain(r))   # 真 abstain 且判 abstain
    fp = sum(1 for r in answered if said_abstain(r))       # 真作答却判 abstain（漏答）
    abstain_precision = wilson_ci(tp, tp + fp) if (tp + fp) else wilson_ci(0, 0)
    abstain_recall = wilson_ci(tp, len(abstain_gold)) if abstain_gold else wilson_ci(0, 0)
    # closed_ended F1：把 answered 档「该答且答对」当正类，abstain 档当负类
    ce_tp = sum(1 for r in answered if r.get("correct"))       # 该答且答对
    ce_fn = len(answered) - ce_tp                              # 该答却错/拒
    ce_fp = len(abstain_gold) - tp                             # 该拒却硬凑
    prec_ce = ce_tp / (ce_tp + ce_fp) if (ce_tp + ce_fp) else 0.0
    rec_ce = ce_tp / (ce_tp + ce_fn) if (ce_tp + ce_fn) else 0.0
    f1_ce = (2 * prec_ce * rec_ce / (prec_ce + rec_ce)) if (prec_ce + rec_ce) else 0.0
    l3_m = {
        "n": len(l3), "n_abstain_gold": len(abstain_gold), "n_answered": len(answered),
        "abstain_precision": abstain_precision,
        "abstain_recall": abstain_recall,
        "closed_ended": {"precision": prec_ce, "recall": rec_ce, "f1": f1_ce,
                         "tp": ce_tp, "fn": ce_fn, "fp": ce_fp},
        "by_tier": {},
    }
    for tier in ("answered", "in_unwritten", "off_spectrum"):
        rr = [r for r in l3 if r["gold_expr"]["tier"] == tier]
        if rr:
            l3_m["by_tier"][tier] = {"n": len(rr), "accuracy": ci(rr)}

    # ── L4 增广认同：golden 池 hit@1/5，按式分 ──
    l4 = sub("L4")
    l4_m = {"hit@1": ci(l4), "hit@5": ci(l4, "hit_at_5"), "by_aug": {}}
    for ak in ("rewrite", "rephrase", "reorder"):
        rr = [r for r in l4 if r["gold_expr"].get("aug_kind") == ak]
        if rr:
            k1 = sum(1 for r in rr if r.get("correct"))
            k5 = sum(1 for r in rr if r.get("hit_at_5"))
            l4_m["by_aug"][ak] = {"n": len(rr), "hit@1": wilson_ci(k1, len(rr)),
                                  "hit@5": wilson_ci(k5, len(rr))}

    summary = {"n_total": len(rows), "scored": len(rows),
               "distribution": {t: sum(1 for r in rows if r["type"] == t) for t in hg.TYPES},
               "L1": l1_m, "L2": l2_m, "L3": l3_m, "L4": l4_m,
               "params": {"topk": topk}}
    return {"summary": summary, "rows": rows}


def verify_only(dataset: List[Dict[str, Any]], tree_nodes: List[Dict[str, Any]]) -> int:
    errs = hg.verify_gold(dataset, tree_nodes)
    if errs:
        print("[verify] FAIL — gold 复算不一致:")
        for e in errs[:15]:
            print("  -", e)
        return 1
    print(f"[verify] OK — {len(dataset)} 题 gold 全部由树结构重算一致")
    return 0


def print_panel(summ: Dict[str, Any]) -> None:
    print("=== H7 跨跳与诚实层 判分结果 ===")
    print(f"总题量 {summ['n_total']} | topk={summ['params']['topk']}")
    print(f"分布: " + " | ".join(f"{t}={summ['distribution'][t]}" for t in hg.TYPES))
    l1 = summ["L1"]
    print(f"[L1 多跳链]  hit@1={fmt_ci(l1['hit@1'])}  hit@5={fmt_ci(l1['hit@5'])}")
    for h in ("hops1", "hops2", "hops3", "hops4"):
        v = l1["by_hop"].get(h)
        if v:
            print(f"    {h}: n={v['n']} hit@1={fmt_ci(v['hit@1'])} hit@5={fmt_ci(v['hit@5'])}")
    l2 = summ["L2"]
    print(f"[L2 混跳辨析] accuracy={fmt_ci(l2['accuracy'])}  "
          f"(hop2={fmt_ci(l2.get('hop2',{}).get('accuracy'))}, "
          f"hop3={fmt_ci(l2.get('hop3',{}).get('accuracy'))})")
    l3 = summ["L3"]
    ce = l3["closed_ended"]
    print(f"[L3 缺证据拒答] abstain_precision={fmt_ci(l3['abstain_precision'])}  "
          f"abstain_recall={fmt_ci(l3['abstain_recall'])}")
    print(f"    closed_ended F1={ce['f1']:.3f} (P={ce['precision']:.3f} "
          f"R={ce['recall']:.3f} tp/fn/fp={ce['tp']}/{ce['fn']}/{ce['fp']})")
    for tier, v in l3["by_tier"].items():
        print(f"    {tier}: n={v['n']} accuracy={fmt_ci(v['accuracy'])}")
    l4 = summ["L4"]
    print(f"[L4 增广认同]  golden池 hit@1={fmt_ci(l4['hit@1'])}  hit@5={fmt_ci(l4['hit@5'])}")
    for ak, v in l4["by_aug"].items():
        print(f"    {ak}: n={v['n']} hit@1={fmt_ci(v['hit@1'])} hit@5={fmt_ci(v['hit@5'])}")


def main() -> int:
    ap = argparse.ArgumentParser(description="H7 四子类判分")
    ap.add_argument("--dataset", default=os.path.join(HERE, "dataset", "h7_evalset.jsonl"))
    ap.add_argument("--tree", default=os.path.join(HERE, "data", "h7_tree.json"))
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

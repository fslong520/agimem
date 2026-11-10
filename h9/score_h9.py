#!/usr/bin/env python3
"""score_h9.py — H9 六子类指标汇总（Wilson CI、霸榜率、等权 composite）。

指标（六类主指标各 1/6 进 composite；霸榜率为诊断指标，不进总分）：
  R1 prescription_hit@1        处方召回（gold=因果记录 top1）
  R2 counterfactual_hit@1      反事实（gold=事件条目 top1）
  R3 fresh_hit@1 + stale_crown_rate   头榜跟最新；stale_crown=旧条目霸榜率（诊断）
  R4 gist_line_hit@1           主线抽取（gold=主线条目 top1）
  R5 类分 = mean(probe_recorded_hit@1, probe_unrecorded_resist, importance_hit@1)
       probe_unrecorded_resist = 未记探针不硬凑的比例（gold=空）
  R6 evidence_first + retell_crown_rate  选实测优先；retell_crown=转述霸榜率（诊断，
       复现 H4 T6 86.4% 口径，tests/34 §九）

用法：
    python3 score_h9.py --verify-only              # 只验 gold 可机械复算
    python3 score_h9.py <predictions.jsonl>        # 打分（本轮不跑分，留给 collect 侧）
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional

import h9_gold as hg

HERE = os.path.dirname(os.path.abspath(__file__))
Z95 = 1.959963984540054

NAME = {"R1": "因果归因→处方", "R2": "反事实", "R3": "动态更新",
        "R4": "压缩摘要", "R5": "元认知", "R6": "跨来源置信"}


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
    return f"{c['point']:.{nd}f} [{c['lo']:.3f}, {c['hi']:.3f}] {c['k']}/{c['n']}"


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def extract_hits(rec: Any) -> List[Dict[str, Any]]:
    if isinstance(rec, dict) and isinstance(rec.get("hits"), list):
        return rec["hits"]
    if isinstance(rec, list):
        return rec
    raise ValueError(f"无法解析预测记录: {rec!r}")


def score_dataset(dataset: List[Dict[str, Any]], preds: List[Dict[str, Any]]) -> Dict[str, Any]:
    nodes = {n["id"]: n for n in json.load(
        open(os.path.join(HERE, "data", "h9_tree.json"), encoding="utf-8"))["nodes"]}
    by_qid: Dict[str, Any] = {}
    for r in preds:
        qid = r.get("qid") if isinstance(r, dict) else None
        if qid is None:
            raise ValueError(f"预测记录缺 qid: {r!r}")
        by_qid[qid] = extract_hits(r)

    per_q: Dict[str, Any] = {}
    rows: Dict[str, List[Dict[str, Any]]] = {t: [] for t in hg.TYPES}
    for q in dataset:
        qid = q["qid"]
        if qid not in by_qid:
            raise ValueError(f"缺预测: {qid}")
        out = hg.evaluate_expr(q["gold_expr"], by_qid[qid], nodes)
        out["qid"] = qid
        out["type"] = q["type"]
        per_q[qid] = out
        rows[q["type"]].append(out)

    summary: Dict[str, Any] = {"types": {}, "per_question": per_q}
    class_scores: Dict[str, float] = {}

    # R1 / R2 / R4：单指标
    for typ, metric in (("R1", "prescription_hit@1"), ("R2", "counterfactual_hit@1"),
                        ("R4", "gist_line_hit@1")):
        rs = rows[typ]
        k = sum(1 for r in rs if r["correct"])
        summary["types"][typ] = {"name": NAME[typ], "n": len(rs), metric: wilson_ci(k, len(rs))}
        class_scores[typ] = k / len(rs) if rs else 0.0

    # R3：fresh_hit@1 进总分；stale_crown_rate 诊断
    rs = rows["R3"]
    k_fresh = sum(1 for r in rs if r["correct"])
    k_stale = sum(1 for r in rs if r.get("stale_crown"))
    summary["types"]["R3"] = {
        "name": NAME["R3"], "n": len(rs),
        "fresh_hit@1": wilson_ci(k_fresh, len(rs)),
        "stale_crown_rate": wilson_ci(k_stale, len(rs)),
        "note": "stale_crown_rate=头榜落旧值条目的比例（诊断，不进 composite）",
    }
    class_scores["R3"] = k_fresh / len(rs) if rs else 0.0

    # R5：三指标均值进总分
    probe_rec = [r for r in rows["R5"] if r["detail"].get("phase") == "recorded"]
    probe_unr = [r for r in rows["R5"] if r["detail"].get("phase") == "unrecorded"]
    imp = [r for r in rows["R5"] if r["type"] == "R5" and "grade" in r["detail"]]
    k_rec = sum(1 for r in probe_rec if r["correct"])
    k_unr = sum(1 for r in probe_unr if r["correct"])
    k_imp = sum(1 for r in imp if r["correct"])
    m_rec = k_rec / len(probe_rec) if probe_rec else 0.0
    m_unr = k_unr / len(probe_unr) if probe_unr else 0.0
    m_imp = k_imp / len(imp) if imp else 0.0
    summary["types"]["R5"] = {
        "name": NAME["R5"], "n": len(rows["R5"]),
        "probe_recorded_hit@1": wilson_ci(k_rec, len(probe_rec)),
        "probe_unrecorded_resist": wilson_ci(k_unr, len(probe_unr)),
        "importance_hit@1": wilson_ci(k_imp, len(imp)),
        "note": "类分=三指标均值；unrecorded 正确=不硬凑（gold 空）",
    }
    class_scores["R5"] = (m_rec + m_unr + m_imp) / 3

    # R6：evidence_first 进总分；retell_crown_rate 诊断（复现 T6 86.4% 口径）
    rs = rows["R6"]
    k_ev = sum(1 for r in rs if r["correct"])
    k_ret = sum(1 for r in rs if r.get("retell_crown"))
    summary["types"]["R6"] = {
        "name": NAME["R6"], "n": len(rs),
        "evidence_first": wilson_ci(k_ev, len(rs)),
        "retell_crown_rate": wilson_ci(k_ret, len(rs)),
        "note": "retell_crown_rate=头榜落转述条目的比例（诊断；对照 H4 T6 86.4%）",
    }
    class_scores["R6"] = k_ev / len(rs) if rs else 0.0

    summary["class_scores"] = class_scores
    summary["composite_equal_weight"] = sum(class_scores[t] for t in hg.TYPES) / len(hg.TYPES)
    return summary


def verify_only(dataset: List[Dict[str, Any]], tree_nodes: List[Dict[str, Any]]) -> int:
    errs = hg.verify_gold(dataset, tree_nodes)
    if errs:
        print("[score_h9] gold verify FAIL")
        for e in errs[:20]:
            print("  -", e)
        return 1
    print(f"[score_h9] gold verify OK — {len(dataset)} 题可机械复算")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("preds", nargs="?", help="预测 jsonl")
    ap.add_argument("--verify-only", action="store_true")
    args = ap.parse_args()

    ds = load_jsonl(os.path.join(HERE, "dataset", "h9_evalset.jsonl"))
    tree = json.load(open(os.path.join(HERE, "data", "h9_tree.json"), encoding="utf-8"))

    if args.verify_only:
        return verify_only(ds, tree["nodes"])
    if not args.preds:
        print(__doc__)
        return 0
    rc = verify_only(ds, tree["nodes"])
    if rc:
        return rc
    preds = load_jsonl(args.preds)
    summary = score_dataset(ds, preds)
    print(f"[score_h9] 等权 composite = {summary['composite_equal_weight']:.3f}")
    for t in hg.TYPES:
        info = summary["types"][t]
        print(f"  {t} {info['name']} n={info['n']}")
        for k, v in info.items():
            if k in ("name", "n", "note") or not isinstance(v, dict):
                continue
            if "point" in v:
                print(f"    {k}: {fmt_ci(v)}")
    out = os.path.join(HERE, "results", "h9-score.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"[score_h9] 写出 {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

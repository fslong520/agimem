#!/usr/bin/env python3
"""causal_delta.py — H2 对照臂判分：结构/节点集退化 Δ（配对 bootstrap CI）＋ hit@1=0 自命中成因。

两件事：

1. **退化 Δ**：把 `full`（143 节点）与 `leaves`（95 叶子）、`half`（随机 72）放在同一批 122 题、
   同一判分器下比较；每类指标按**题**配对，用分层 bootstrap（在题型内重抽，2000 次，seed 20261109）
   给 Δ 的 95% 置信区间。顺带把 T15 的 `full` 老库当复现校验（同配置不同库实例）。

2. **hit@1=0 的成因**：对链题，取 `gold_expr.node`（题面点名的那个节点）——
   统计 top-1 是否恒为该节点自身、该节点自身是否总在 top-5、平均名次；
   再对比 `full-anon` 臂（题面里把节点标题改写成「这一步」）的 hit@1/hit@5。

产物：results/causal-degraded.json、results/causal-selfhit-probe.json
用法： python3 causal_delta.py [--reps 2000]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from typing import Any, Dict, List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import causal_gold as cg  # noqa: E402
import score as sc  # noqa: E402

TREE = os.path.join(HERE, "data", "tree.json")
DATASET = os.path.join(HERE, "dataset", "causal_evalset.jsonl")
ARMS_DIR = os.path.join(HERE, "results", "causal-arms")
RESDIR = os.path.join(HERE, "results")
SEED = 20261109

ARM_FILES = {
    "full": os.path.join(ARMS_DIR, "full-predictions.jsonl"),
    "leaves": os.path.join(ARMS_DIR, "leaves-predictions.jsonl"),
    "half": os.path.join(ARMS_DIR, "half-predictions.jsonl"),
    "full_anon": os.path.join(ARMS_DIR, "full-anon-predictions.jsonl"),
    "full_t15": os.path.join(RESDIR, "causal-isolated-predictions.jsonl"),
}


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def score_arm(dataset, tree, path, topk=5, min_score=0.0):
    preds = sc.index_predictions(path)
    return sc.score(dataset, tree, preds, topk, min_score, partial=False)


def per_question(rows: List[Dict[str, Any]]) -> Dict[str, List[float]]:
    """把判分行摊成「按题型的有序 0/1 与覆盖率序列」，供配对 bootstrap 用。"""
    out: Dict[str, List[float]] = {"chain_hit": [], "chain_cov": [],
                                   "interv": [], "noise": []}
    for r in rows:
        if r["type"] in (cg.CHAIN_ANCESTOR, cg.CHAIN_DESCENDANT):
            out["chain_hit"].append(1.0 if r.get("hit") else 0.0)
            out["chain_cov"].append(float(r.get("coverage") or 0.0))
        elif r["type"] == cg.INTERVENTION:
            out["interv"].append(1.0 if r.get("correct") else 0.0)
        elif r["type"] == cg.NEGATIVE:
            out["noise"].append(1.0 if r.get("noisy") else 0.0)
    return out


def boot_delta(a: List[float], b: List[float], reps: int, rng: random.Random
               ) -> Dict[str, Any]:
    """配对 bootstrap：同一题号在两个臂之间的差；返回 Δ均值与 95% 百分位 CI。"""
    assert len(a) == len(b)
    n = len(a)
    diffs = [x - y for x, y in zip(a, b)]
    point = sum(diffs) / n if n else 0.0
    draws = []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        draws.append(sum(diffs[i] for i in idx) / n)
    draws.sort()
    lo = draws[int(0.025 * reps)]
    hi = draws[int(0.975 * reps) - 1]
    return {"point": point, "lo": lo, "hi": hi, "n": n, "reps": reps,
            "mean_a": sum(a) / n if n else None, "mean_b": sum(b) / n if n else None}


def selfhit_stats(rows: List[Dict[str, Any]], cases: Dict[str, Dict[str, Any]]
                  ) -> Dict[str, Any]:
    chain = [r for r in rows if r["type"] in (cg.CHAIN_ANCESTOR, cg.CHAIN_DESCENDANT)]
    top1_self = in_top5 = 0
    ranks: List[int] = []
    examples = []
    for r in chain:
        node = ((cases.get(r["qid"]) or {}).get("gold_expr") or {}).get("node")
        ids = [h["id"] for h in r["top"]]
        if not node:
            continue
        if ids and cg.id_match(ids[0], node):
            top1_self += 1
        if any(cg.id_match(i, node) for i in ids):
            in_top5 += 1
            ranks.append(next(j for j, i in enumerate(ids) if cg.id_match(i, node)))
        if len(examples) < 3:
            examples.append({"qid": r["qid"], "subject": node, "top1": ids[0] if ids else None,
                             "hit": r.get("hit"), "gold_first_rank": r.get("rank")})
    # 修正口径：先把「题面点名的节点自身」从召回里剔除，再算 hit@1 / hit@5
    excl_hit1 = excl_hit5 = 0
    for r in chain:
        node = ((cases.get(r["qid"]) or {}).get("gold_expr") or {}).get("node")
        gold = r.get("gold") or []
        ids = [h["id"] for h in r["top"] if not (node and cg.id_match(h["id"], node))]
        if not gold:
            continue
        rank = next((j for j, i in enumerate(ids) if any(cg.id_match(i, g) for g in gold)), None)
        if rank == 0:
            excl_hit1 += 1
        if rank is not None and rank < 5:
            excl_hit5 += 1
    n = len(chain)
    return {"n_chain_questions": n,
            "self_excluded_hit_at_1": (excl_hit1 / n) if n else None,
            "self_excluded_hit_at_5": (excl_hit5 / n) if n else None,
            "self_excluded_hit_at_1_k": excl_hit1, "self_excluded_hit_at_5_k": excl_hit5,
            "self_excluded_hit_at_1_ci": sc.wilson_ci(excl_hit1, n) if n else None,
            "self_excluded_hit_at_5_ci": sc.wilson_ci(excl_hit5, n) if n else None,
            "top1_is_subject_ci": sc.wilson_ci(top1_self, n) if n else None,
            "top1_is_subject": top1_self,
            "top1_is_subject_rate": (top1_self / n) if n else None,
            "subject_in_top5_rate": (in_top5 / n) if n else None,
            "subject_mean_rank": (sum(ranks) / len(ranks)) if ranks else None,
            "examples": examples}


def main() -> int:
    ap = argparse.ArgumentParser(description="H2 对照臂 Δ 与自命中分析")
    ap.add_argument("--reps", type=int, default=2000)
    args = ap.parse_args()

    tree = cg.load_tree(TREE)
    dataset = load_jsonl(DATASET)
    cases = {c["qid"]: c for c in dataset}

    arms: Dict[str, Any] = {}
    for name, path in ARM_FILES.items():
        if not os.path.exists(path):
            print(f"[skip] {name}: 缺 {path}")
            continue
        res = score_arm(dataset, tree, path)
        mv = sc.metric_vector(res["summary"])
        arms[name] = {"path": path, "summary": res["summary"], "metrics": mv, "rows": res["rows"]}
        print(f"[score] {name}: chain_hit@k={mv['chain_hit_at_k']:.3f} "
              f"cov={mv['chain_cov']:.3f} interv={mv['intervention_acc']:.3f} "
              f"noise={mv['negative_noise_rate']:.3f}", flush=True)

    rng = random.Random(SEED)
    seqs = {k: per_question(v["rows"]) for k, v in arms.items()}

    deltas: Dict[str, Any] = {}
    for deg in ("leaves", "half"):
        if "full" not in seqs or deg not in seqs:
            continue
        deltas[f"full_minus_{deg}"] = {
            m: boot_delta(seqs["full"][m], seqs[deg][m], args.reps, rng)
            for m in ("chain_hit", "chain_cov", "interv", "noise")}
    if "full" in seqs and "full_t15" in seqs:
        deltas["replication_full_vs_t15"] = {
            m: boot_delta(seqs["full"][m], seqs["full_t15"][m], args.reps, rng)
            for m in ("chain_hit", "chain_cov", "interv", "noise")}

    degraded = {
        "schema": "agimem-causal-degraded/1",
        "purpose": ("结构/节点集退化对照：full(143 节点) vs leaves(95 叶子) vs half(随机 72)；"
                    "同 122 题、同判分器、同 topk=5；Δ=full−退化臂，配对 bootstrap 95%CI。"),
        "why_no_noparent_arm": ("import 无法给已存在条目补父子边：两遍导入第二遍 duplicates 2 / reattached 0，"
                                "recall 载荷 ancestors 恒为空（实测探针）；且 T15 的完整树臂本来就没有任何边"
                                "——所以「有结构 vs 无结构」在库层定义性地等于 0，本层只能做节点集退化。"),
        "arms": {k: {"path": v["path"], "metrics": v["metrics"],
                     "cis": v["summary"].get("cis"),
                     "distribution": v["summary"].get("distribution")}
                 for k, v in arms.items()},
        "deltas": deltas,
        "bootstrap": {"reps": args.reps, "seed": SEED, "stratify": "按题型分别配对重抽"},
    }
    with open(os.path.join(RESDIR, "causal-degraded.json"), "w", encoding="utf-8") as f:
        json.dump(degraded, f, ensure_ascii=False, indent=2)
        f.write("\n")

    selfhit = {
        "schema": "agimem-causal-selfhit/1",
        "question": "hit@1=0.000 是因为检索 top-1 恒为「题面点名的那个节点自身」（gold 不含自身）吗？",
        "full": selfhit_stats(arms["full"]["rows"], cases) if "full" in arms else None,
        "full_t15": selfhit_stats(arms["full_t15"]["rows"], cases) if "full_t15" in arms else None,
        "leaves": selfhit_stats(arms["leaves"]["rows"], cases) if "leaves" in arms else None,
        "half": selfhit_stats(arms["half"]["rows"], cases) if "half" in arms else None,
        "full_anon": ({"metrics": arms["full_anon"]["metrics"],
                       "chain_hit_at_1": arms["full_anon"]["summary"]["chain"]["hit_at_1"],
                       **selfhit_stats(arms["full_anon"]["rows"], cases)}
                      if "full_anon" in arms else None),
        "anon_note": "full_anon 臂把链题题面里的「<节点标题>」改写成「这一步」，去掉点名线索后重跑同一套题。",
    }
    with open(os.path.join(RESDIR, "causal-selfhit-probe.json"), "w", encoding="utf-8") as f:
        json.dump(selfhit, f, ensure_ascii=False, indent=2)
        f.write("\n")

    for name, d in deltas.items():
        print(f"\n[Δ {name}]")
        for m, v in d.items():
            print(f"  {m}: Δ={v['point']:+.3f}  CI=[{v['lo']:+.3f}, {v['hi']:+.3f}]  n={v['n']}")
    if selfhit["full"]:
        f0 = selfhit["full"]
        print(f"\n[selfhit] top1=自身 {f0['top1_is_subject']}/{f0['n_chain_questions']} "
              f"({f0['top1_is_subject_rate']:.3f})  自身在 top5 {f0['subject_in_top5_rate']:.3f} "
              f"平均名次 {f0['subject_mean_rank']}")
    if selfhit["full_anon"]:
        a = selfhit["full_anon"]
        print(f"[anon] hit@1={a['chain_hit_at_1']:.3f} "
              f"hit@5={a['metrics']['chain_hit_at_k']:.3f} cov={a['metrics']['chain_cov']:.3f} "
              f"| top1=自身 {a['top1_is_subject_rate']:.3f}")
    print("\n[causal_delta] 写出 results/causal-degraded.json、results/causal-selfhit-probe.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

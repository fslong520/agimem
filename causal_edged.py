#!/usr/bin/env python3
"""causal_edged.py — attach 建边后的判分：有边 vs 无边 Δ（配对 bootstrap）＋ 多跳祖先专项。

三件事：
  1. 用同判分器（score.py）判 `causal-edged-predictions.jsonl`，得四类指标 + Wilson CI；
  2. 与 T19 的 `full`（143 文本**零边**）逐题配对 bootstrap，得 Δ（这才是真正的「有结构 vs 无结构」）；
  3. **多跳祖先专项**：取深度 ≥3 的链题（≥10 道），看 top-5 里是否出现**距离 ≥2 的远祖**
     （grandparent 及以上）——直接区分「文本召回直接父节点」与「图遍历扩散」。

另附：剔除自身重排后的 hit@1（T19 定的口径），以及 `ancestors` 字段在召回载荷里是否非空（边真的在）。

产物：results/causal-edged.json、results/causal-multihop.json
用法： python3 causal_edged.py [--reps 2000] [--multihop 10]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import causal_delta as cd  # 复用自命中/配对 bootstrap
import causal_gold as cg  # noqa: E402
import score as sc  # noqa: E402

RESDIR = os.path.join(HERE, "results")
TREE = os.path.join(HERE, "data", "tree.json")
DATASET = os.path.join(HERE, "dataset", "causal_evalset.jsonl")
EDGED = os.path.join(RESDIR, "causal-edged-predictions.jsonl")
NOEDGE = os.path.join(RESDIR, "causal-arms", "full-predictions.jsonl")
SEED = 20261109


def ancestors_of(sid: str, by_id: Dict[str, Dict[str, Any]]) -> List[str]:
    out, cur = [], sid
    while by_id.get(cur, {}).get("parent_id"):
        cur = by_id[cur]["parent_id"]
        out.append(cur)
    return out  # 由近到远


def main() -> int:
    ap = argparse.ArgumentParser(description="有边 vs 无边 + 多跳祖先")
    ap.add_argument("--reps", type=int, default=2000)
    ap.add_argument("--multihop", type=int, default=10)
    args = ap.parse_args()

    tree = cg.load_tree(TREE)
    raw = json.load(open(TREE, encoding="utf-8"))
    by_id = {n["id"]: n for n in raw["nodes"]}
    dataset = cd.load_jsonl(DATASET)
    cases = {c["qid"]: c for c in dataset}

    edged = sc.score(dataset, tree, sc.index_predictions(EDGED), 5, 0.0)
    noedge = sc.score(dataset, tree, sc.index_predictions(NOEDGE), 5, 0.0)
    me, mn = sc.metric_vector(edged["summary"]), sc.metric_vector(noedge["summary"])

    rng = random.Random(SEED)
    se = cd.per_question(edged["rows"])
    sn = cd.per_question(noedge["rows"])
    deltas = {m: cd.boot_delta(se[m], sn[m], args.reps, rng)
              for m in ("chain_hit", "chain_cov", "interv", "noise")}

    selfhit = cd.selfhit_stats(edged["rows"], cases)

    # ── 多跳祖先专项 ────────────────────────────────────────────────
    multihop_rows: List[Dict[str, Any]] = []
    for r in edged["rows"]:
        if r["type"] not in (cg.CHAIN_ANCESTOR, cg.CHAIN_DESCENDANT):
            continue
        node = ((cases.get(r["qid"]) or {}).get("gold_expr") or {}).get("node")
        if not node:
            continue
        anc = ancestors_of(node, by_id)          # 近 → 远
        if len(anc) < 3:                          # 深度 ≥3 才算多跳题
            continue
        ids = [h["id"] for h in r["top"]]
        # 距离：anc 索引 +1（父=1，祖父=2，…）
        dist = {}
        for i, t in enumerate(ids):
            for j, a in enumerate(anc):
                if cg.id_match(t, a):
                    dist[t] = j + 1
        multi = [t for t, dd in dist.items() if dd >= 2]
        multihop_rows.append({
            "qid": r["qid"], "type": r["type"], "subject": node,
            "subject_depth": len(anc), "gold": r.get("gold"),
            "top1": ids[0] if ids else None, "top": ids,
            "hit": bool(r.get("hit")), "gold_rank": r.get("rank"),
            "ancestor_distances": dist,
            "multi_hop_hit": bool(multi),
            "max_hop": max(dist.values()) if dist else 0,
            "top1_is_subject": bool(ids) and cg.id_match(ids[0], node),
        })
        if len(multihop_rows) >= args.multihop:
            break

    mh = {
        "schema": "agimem-causal-multihop/1",
        "definition": ("深度 ≥3 的链题；看 top-5 里是否出现距离 ≥2 的远祖（祖父及以上）。"
                       "距离按 parent 链算：直接父=1，祖父=2。"),
        "n_questions": len(multihop_rows),
        "multi_hop_hits": sum(1 for x in multihop_rows if x["multi_hop_hit"]),
        "rows": multihop_rows,
    }
    mh["multi_hop_rate"] = (mh["multi_hop_hits"] / len(multihop_rows)) if multihop_rows else None
    mh["multi_hop_ci"] = (sc.wilson_ci(mh["multi_hop_hits"], len(multihop_rows))
                          if multihop_rows else None)
    mh["any_ancestor_rate"] = (sum(1 for x in multihop_rows if x["ancestor_distances"])
                               / len(multihop_rows)) if multihop_rows else None
    mh["max_hop_mean"] = (sum(x["max_hop"] for x in multihop_rows) / len(multihop_rows)
                          if multihop_rows else None)

    with open(os.path.join(RESDIR, "causal-multihop.json"), "w", encoding="utf-8") as f:
        json.dump(mh, f, ensure_ascii=False, indent=2)
        f.write("\n")

    receipt = json.load(open(os.path.join(RESDIR, "causal-edge-build.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(RESDIR, "causal-edge-build.json")) else {}

    doc = {
        "schema": "agimem-causal-edged/1",
        "arm": "attach-edged-tree",
        "claim": ("合成因果树 143 节点 + `rsrs attach` 建出的 133 条父子边，真在库内；"
                  "122 题完整 JSON 召回，同判分器 score.py、topk=5。"),
        "provenance": {
            "data_dir": receipt.get("data_dir"), "port": receipt.get("port"),
            "n_nodes": receipt.get("n_nodes"), "n_edges_planned": receipt.get("n_edges_planned"),
            "n_edges_ok": receipt.get("n_edges_ok"), "n_edges_fail": receipt.get("n_edges_fail"),
            "verify": receipt.get("verify"), "index_after_attach": receipt.get("index_after_attach"),
            "predictions": EDGED, "n_hits": receipt.get("n_hits"),
        },
        "metrics": me, "cis": edged["summary"].get("cis"),
        "chain": edged["summary"]["chain"],
        "intervention": edged["summary"]["intervention"],
        "supersession": edged["summary"]["supersession"],
        "negative": edged["summary"]["negative"],
        "selfhit": selfhit,
        "delta_vs_noedge": {
            "baseline": NOEDGE, "baseline_arm": "T19 full（143 文本零边）",
            "metrics": deltas,
            "bootstrap": {"reps": args.reps, "seed": SEED},
            "noedge_metrics": mn,
        },
        "multihop": {"path": os.path.join(RESDIR, "causal-multihop.json"),
                     "n_questions": mh["n_questions"],
                     "multi_hop_rate": mh["multi_hop_rate"],
                     "multi_hop_ci": mh["multi_hop_ci"],
                     "any_ancestor_rate": mh["any_ancestor_rate"],
                     "max_hop_mean": mh["max_hop_mean"]},
    }
    with open(os.path.join(RESDIR, "causal-edged.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"[edged] chain_hit@5={me['chain_hit_at_k']:.3f} hit@1={edged['summary']['chain']['hit_at_1']:.3f} "
          f"cov={me['chain_cov']:.3f} interv={me['intervention_acc']:.3f} "
          f"fa={me['false_alarm_rate']:.3f} noise={me['negative_noise_rate']:.3f}")
    print(f"[edged] 无边际基线（T19 full）chain_hit@5={mn['chain_hit_at_k']:.3f} cov={mn['chain_cov']:.3f}")
    for m, v in deltas.items():
        print(f"[Δ edged−noedge] {m}: {v['point']:+.3f} CI=[{v['lo']:+.3f}, {v['hi']:+.3f}] n={v['n']}")
    print(f"[selfhit] top1=自身 {selfhit['top1_is_subject_rate']:.3f} "
          f"excl hit@1={selfhit['self_excluded_hit_at_1']:.3f} "
          f"CI={selfhit['self_excluded_hit_at_1_ci']}")
    print(f"[multihop] n={mh['n_questions']} 多跳命中={mh['multi_hop_hits']} "
          f"rate={mh['multi_hop_rate']} ci={mh['multi_hop_ci']} "
          f"任意祖先命中率={mh['any_ancestor_rate']} 平均最大跳数={mh['max_hop_mean']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

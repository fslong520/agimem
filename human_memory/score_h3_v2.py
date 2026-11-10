#!/usr/bin/env python3
"""score_h3_v2.py — H3 v2 机械判分：成对比较 + Wilson CI，零 LLM。

口径（每条都对着旧度量被判无效的病因，见 tests/32 §五 H3.3）：

  C2 recency   同主题一对（正文逐字节相同、只有 created_at 不同）：
               `newer_first` = 后写条目严格排在先写条目之前；
               `tie_rate`   = 两条分数完全相等（说明排序没用到任何时间信号）；
               `score_gap`  = 后写分数 − 先写分数（原样报，不调参）。
  C3 correction 结构同上、独立库、题面换「结论」措辞：`later_first` / `tie_rate` / `score_gap`。
  C1 repeat     同一事实写 3 条（正文相同）vs 同等相关干扰写 1 条：
               `repeated_first`        = top-1 落在重复族；
               `repeated_beats_single` = 重复族最好名次 < 干扰条目名次；
               `family_echo_top5`      = top-5 里出现几个重复族条目（检测「回声」还是「去重」）。

全部比例给 Wilson 95% CI（n=20 时约 ±0.2，1 题 ≈ 5pp，不可跨档轻言显著）。

用法：
    python3 score_h3_v2.py [--json] [--out ../results/human-dimension-v2.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(HERE, "data", "h3_v2_dataset.jsonl")
RESDIR = os.path.join(os.path.dirname(HERE), "results")
Z95 = 1.959963984540054


def wilson_ci(k: int, n: int, z: float = Z95) -> Dict[str, Any]:
    if n <= 0:
        return {"point": None, "lo": None, "hi": None, "n": 0, "k": k, "method": "wilson"}
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z2 / (4 * n * n)) ** 0.5) / denom
    return {"point": p, "lo": max(0.0, center - half), "hi": min(1.0, center + half),
            "n": n, "k": k, "method": "wilson", "z": z}


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def rank_of(titles: List[str], target: str) -> Optional[int]:
    for i, t in enumerate(titles):
        if t == target:
            return i
    return None


def score_arm(arm: str, questions: List[Dict[str, Any]],
              preds: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for q in questions:
        rec = preds.get(q["qid"]) or {"hits": []}
        titles = [h["title"] for h in rec["hits"]]
        scores = {h["title"]: h["score"] for h in rec["hits"]}
        row: Dict[str, Any] = {"qid": q["qid"], "query": q["query"], "top": titles,
                               "n_hits": len(titles)}
        if arm in ("recency", "correction"):
            g, o = q["gold_title"], q["other_title"]
            rg, ro = rank_of(titles, g), rank_of(titles, o)
            row.update({"gold_title": g, "other_title": o, "rank_gold": rg, "rank_other": ro,
                        "gold_in_top5": rg is not None, "other_in_top5": ro is not None,
                        "later_first": (rg is not None and (ro is None or rg < ro)),
                        "tie": (rg is not None and ro is not None
                                and scores.get(g) == scores.get(o)),
                        "score_gap": ((scores[g] - scores[o])
                                      if (g in scores and o in scores) else None)})
        else:
            fam, dis = q["family"], q["distractor"]
            fr = [rank_of(titles, f) for f in fam]
            fr_ok = [r for r in fr if r is not None]
            d_rank = rank_of(titles, dis)
            row.update({"family": fam, "distractor": dis,
                        "family_ranks": fr, "distractor_rank": d_rank,
                        "repeated_first": (titles[:1] and titles[0] in fam),
                        "repeated_beats_single": (min(fr_ok) < d_rank) if (fr_ok and d_rank is not None)
                        else (d_rank is None and bool(fr_ok)),
                        "family_echo_top5": len(fr_ok),
                        "distractor_first": (d_rank == 0)})
        rows.append(row)

    n = len(rows)
    out: Dict[str, Any] = {"arm": arm, "n": n, "rows": rows}
    if arm in ("recency", "correction"):
        k_later = sum(1 for r in rows if r["later_first"])
        k_tie = sum(1 for r in rows if r["tie"])
        k_old_top1 = sum(1 for r in rows if r["rank_other"] == 0)
        gaps = [r["score_gap"] for r in rows if r["score_gap"] is not None]
        out["metrics"] = {
            "later_first": wilson_ci(k_later, n),
            "tie_rate": wilson_ci(k_tie, n),
            "earlier_top1": wilson_ci(k_old_top1, n),
            "gold_in_top5": wilson_ci(sum(1 for r in rows if r["gold_in_top5"]), n),
            "score_gap_mean": (sum(gaps) / len(gaps)) if gaps else None,
            "score_gap_min": min(gaps) if gaps else None,
            "score_gap_max": max(gaps) if gaps else None,
            "score_gap_abs_mean": (sum(abs(g) for g in gaps) / len(gaps)) if gaps else None,
        }
    else:
        k_rep = sum(1 for r in rows if r["repeated_first"])
        k_beat = sum(1 for r in rows if r["repeated_beats_single"])
        k_dis1 = sum(1 for r in rows if r["distractor_first"])
        echo = [r["family_echo_top5"] for r in rows]
        out["metrics"] = {
            "repeated_first": wilson_ci(k_rep, n),
            "repeated_beats_single": wilson_ci(k_beat, n),
            "distractor_top1": wilson_ci(k_dis1, n),
            "family_echo_top5_mean": (sum(echo) / len(echo)) if echo else None,
            "family_echo_top5_hist": {str(k): echo.count(k) for k in sorted(set(echo))},
        }
    return out


def render_text(doc: Dict[str, Any]) -> str:
    L = ["=== H3 记忆动力学 v2 判分（隔离库实跑，零 LLM）==="]
    for arm in ("recency", "correction", "repeat"):
        a = doc["arms"].get(arm)
        if not a:
            continue
        m = a["metrics"]
        L.append(f"\n[{arm}] n={a['n']}")
        if arm in ("recency", "correction"):
            key = "later_first"
            L.append(f"  后写先排（{key}）={m[key]['point']:.3f}  CI=[{m[key]['lo']:.3f}, {m[key]['hi']:.3f}]  "
                     f"k={m[key]['k']}/{m[key]['n']}")
            L.append(f"  分数完全并列（tie）={m['tie_rate']['point']:.3f}  "
                     f"CI=[{m['tie_rate']['lo']:.3f}, {m['tie_rate']['hi']:.3f}]")
            L.append(f"  先写排第 1（earlier_top1）={m['earlier_top1']['point']:.3f}  "
                     f"CI=[{m['earlier_top1']['lo']:.3f}, {m['earlier_top1']['hi']:.3f}]")
            L.append(f"  分数差（后−先）均值={m['score_gap_mean']}  "
                     f"绝对均值={m['score_gap_abs_mean']}")
        else:
            L.append(f"  重复族 top1={m['repeated_first']['point']:.3f}  "
                     f"CI=[{m['repeated_first']['lo']:.3f}, {m['repeated_first']['hi']:.3f}]")
            L.append(f"  重复压过单次（repeated_beats_single）={m['repeated_beats_single']['point']:.3f}  "
                     f"CI=[{m['repeated_beats_single']['lo']:.3f}, {m['repeated_beats_single']['hi']:.3f}]")
            L.append(f"  干扰条目 top1={m['distractor_top1']['point']:.3f}  "
                     f"top5 内重复族条目均值={m['family_echo_top5_mean']}")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="H3 v2 判分")
    ap.add_argument("--dataset", default=DATASET)
    ap.add_argument("--pred-dir", default=RESDIR)
    ap.add_argument("--out", default=os.path.join(RESDIR, "human-dimension-v2.json"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    questions = load_jsonl(args.dataset)
    by_arm: Dict[str, List[Dict[str, Any]]] = {}
    for q in questions:
        by_arm.setdefault(q["arm"], []).append(q)

    doc: Dict[str, Any] = {"schema": "agimem-human-dimension-v2/1", "arms": {}}
    for arm in ("recency", "correction", "repeat"):
        qs = by_arm.get(arm, [])
        path = os.path.join(args.pred_dir, f"h3v2-predictions-{arm}.jsonl")
        preds = {r["qid"]: r for r in load_jsonl(path)} if os.path.exists(path) else {}
        doc["arms"][arm] = score_arm(arm, qs, preds)
        doc["arms"][arm]["predictions_path"] = path
        doc["arms"][arm]["has_predictions"] = bool(preds)

    doc["design"] = {
        "byte_identical_body": True,
        "only_created_at_differs": True,
        "paired_within_topic": True,
        "separate_stores": True,
        "titles_neutral": "无 旧/新/版本/废弃/纠正 等标签词；a/b 与 时序反平衡",
        "zero_llm": True,
        "import_dedupe_workaround": "旧条目 import（显式 2025-03-01）＋新条目 remember --force（now）",
    }

    ctl_path = os.path.join(RESDIR, "h3v2-controls.json")
    if os.path.exists(ctl_path):
        with open(ctl_path, encoding="utf-8") as f:
            ctl = json.load(f)
        doc["controls"] = {
            "path": ctl_path,
            "insertion_control": (ctl.get("insertion_control") or {}).get("metrics"),
            "repeat1_control": (ctl.get("repeat1_control") or {}).get("metrics"),
            "reversed_insertion_control": (ctl.get("reversed_insertion_control") or {}).get("metrics"),
        }
        doc["controls_note"] = (
            "K1 同文同路径顺序写（created_at 都是现在）→ 检验插入顺序效应；"
            "K2 只写一次 → 检验 repeat 优势是否来自内容而非重复；"
            "K3 反序（先 neue 后 old）**机制上不可做**：import 对「已存在的同文条目」同样去重"
            "（实测 remember 3 条后再 import 同文：imported 0 / duplicates 3 / local_total 3），"
            "而 remember 无法指定 created_at → created_at 与插入顺序在本设计内不可分离，"
            "故「系统是否认时间」仍未验证。")

    if args.json:
        print(json.dumps(doc, ensure_ascii=False, indent=2))
    else:
        print(render_text(doc))
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"\n[score_h3_v2] 写出 {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

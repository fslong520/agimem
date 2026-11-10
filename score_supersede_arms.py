#!/usr/bin/env python3
"""score_supersede_arms.py — 取代边真写后的判分（H2 取代题 + H4-T4），含与旧臂的配对 Δ。

两套口径（不得并表，分开输出）：
  A. **oracle 口径**（历史）：生成器在 `data/tree.json` / `tricky_tree.json` 里种 superseded_by，
     但 `import` 会把该字段硬编码为空串（app-core/service.rs:1739-1740）⇒ 该口径**从未真正生效**。
     本脚本只把它作为「历史数字」引用，不重算。
  B. **系统真写边口径**（本轮）：`remember --importance important --supersedes <旧UUID>`，
     边真进库，`recall` 命中项带 `superseded_by`（已逆映射回合成 id）。

判分：
  - H2：直接复用 `score.py`（supersession 分支：命中新结论 或 旧结论带 superseded_by → current）；
    另统计 marked/stale/missing 三态与「旧结论带标记」的题数。
  - H4-T4：主指标 hit@1 / hit@5（gold=新结论 id），与 T11 无边臂逐题配对 bootstrap 求 Δ。

产物：results/causal-supersession-real.json；tricky/results/tricky-t4-supersedes.json（补 Δ 字段）
用法： python3 score_supersede_arms.py [--reps 2000]
"""
from __future__ import annotations

import json
import os
import random
import sys
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
TRICKY = os.path.join(HERE, "tricky")
sys.path.insert(0, HERE)
sys.path.insert(0, TRICKY)

import causal_gold as cg  # noqa: E402
import score as sc  # noqa: E402

RESDIR = os.path.join(HERE, "results")
TREE = os.path.join(HERE, "data", "tree.json")
DATASET = os.path.join(HERE, "dataset", "causal_evalset.jsonl")
EDGED = os.path.join(RESDIR, "causal-supersession-real-predictions.jsonl")
BUILD = os.path.join(RESDIR, "causal-supersession-real-build.json")
CHAIN = os.path.join(RESDIR, "causal-supersede-chain.json")
BASE = os.path.join(RESDIR, "causal-isolated-predictions.jsonl")

T4_NEW = os.path.join(TRICKY, "results", "t4-supersedes-predictions.jsonl")
T4_OLD = os.path.join(TRICKY, "results", "tricky-isolated-predictions.jsonl")
T4_DOC = os.path.join(TRICKY, "results", "tricky-t4-supersedes.json")
T4_SET = os.path.join(TRICKY, "dataset", "tricky_evalset.jsonl")
SEED = 20261109


def load_jsonl(p: str) -> List[Dict[str, Any]]:
    with open(p, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def hits_by_qid(p: str) -> Dict[str, List[Dict[str, Any]]]:
    return {r.get("qid"): r.get("hits") or [] for r in load_jsonl(p)}


def boot(a: List[float], b: List[float], reps: int, rng: random.Random) -> Dict[str, Any]:
    d = [x - y for x, y in zip(a, b)]
    n = len(d)
    point = sum(d) / n
    draws = sorted(sum(d[rng.randrange(n)] for _ in range(n)) / n for _ in range(reps))
    return {"point": point, "lo": draws[int(0.025 * reps)], "hi": draws[int(0.975 * reps) - 1],
            "n": n, "reps": reps}


def main() -> int:
    reps = 2000
    if "--reps" in sys.argv:
        reps = int(sys.argv[sys.argv.index("--reps") + 1])
    rng = random.Random(SEED)

    # ── H2 ────────────────────────────────────────────────────────
    tree = cg.load_tree(TREE)
    dataset = load_jsonl(DATASET)
    res = sc.score(dataset, tree, sc.index_predictions(EDGED), 5, 0.0)
    base = sc.score(dataset, tree, sc.index_predictions(BASE), 5, 0.0)
    s = res["summary"]
    mv = sc.metric_vector(s)
    sup_rows = [r for r in res["rows"] if r["type"] == cg.SUPERSESSION]
    base_sup = {r["qid"]: r for r in base["rows"] if r["type"] == cg.SUPERSESSION}
    status = {"current": sum(1 for r in sup_rows if r.get("status") == "current"),
              "stale": sum(1 for r in sup_rows if r.get("status") == "stale"),
              "missing": sum(1 for r in sup_rows if r.get("status") == "missing")}
    # 「旧结论带标记」的题数：从预测里看旧条目命中项的 superseded_by 是否非空
    cases = {c["qid"]: c for c in dataset}
    marked = 0
    for qid, hits in hits_by_qid(EDGED).items():
        c = cases.get(qid)
        if not c or c["type"] != cg.SUPERSESSION:
            continue
        old = (c.get("gold_expr") or {}).get("node")
        if any(cg.id_match(h.get("id", ""), old or "-") and h.get("superseded_by") for h in hits):
            marked += 1
    correct_new = [1.0 if r.get("correct") else 0.0 for r in sup_rows]
    correct_old = [1.0 if base_sup.get(r["qid"], {}).get("correct") else 0.0 for r in sup_rows]
    build = json.load(open(BUILD, encoding="utf-8")) if os.path.exists(BUILD) else {}
    chain = json.load(open(CHAIN, encoding="utf-8")) if os.path.exists(CHAIN) else {}

    doc = {
        "schema": "agimem-causal-supersession-real/2",
        "arm": "isolated-rsrs-real-supersedes-edges",
        "files": {"predictions": EDGED, "build": BUILD, "chain": CHAIN, "baseline": BASE},
        "write_side": {
            "command": "rsrs remember <新结论> --importance important --supersedes <旧UUID> --force",
            "n_pairs": build.get("n_pairs"), "n_written_ok": build.get("n_written_ok"),
            "n_written_fail": build.get("n_written_fail"),
            "constraint_probe_trivial": build.get("constraint_trivial_supersedes"),
            "verify_samples": build.get("verify"),
            "index_after": build.get("index_after"),
        },
        "read_side": {
            "n_supersession_questions": len(sup_rows),
            "status_current_stale_missing": [status["current"], status["stale"], status["missing"]],
            "n_questions_old_recalled_with_marker": marked,
            "supersession_acc": mv["supersession_acc"],
            "supersession_acc_ci": (s.get("cis") or {}).get("supersession_acc"),
            "baseline_no_edge_acc": sc.metric_vector(base["summary"])["supersession_acc"],
            "delta_vs_no_edge": boot(correct_new, correct_old, reps, rng),
            "per_question": [{"qid": r["qid"], "status": r.get("status"),
                              "gold": r.get("gold"), "top": [h["id"] for h in r["top"]]}
                             for r in sup_rows],
        },
        "koushu": {
            "A_oracle": "生成器种边（`superseded_by` 写在 data/*.json 里）。**从未生效**：`import` 把该字段硬编码为空串"
                        "（app-core/service.rs:1739-1740），所以历史 «oracle 口径» 的 supersession 数字实际上是"
                        "「无边 + 文本召回」。",
            "B_system": "系统真写边：`remember --supersedes`（必须配 --importance important，实测 trivial 被拒："
                        "`associations require important memory`）。本轮 A/B 两口径**不并表**。",
        },
        "chain_supersession": chain,
    }
    with open(os.path.join(RESDIR, "causal-supersession-real.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"[H2] supersession_acc={mv['supersession_acc']:.3f} "
          f"status current/stale/missing={status['current']}/{status['stale']}/{status['missing']} "
          f"marked={marked} | 无边基线={sc.metric_vector(base['summary'])['supersession_acc']:.3f} | "
          f"Δ={doc['read_side']['delta_vs_no_edge']}")

    # ── H4-T4 ─────────────────────────────────────────────────────
    t4_set = [q for q in load_jsonl(T4_SET) if q["type"] == "T4"]
    gold = {q["qid"]: q["expect"][0] for q in t4_set}
    new_hits, old_hits = hits_by_qid(T4_NEW), hits_by_qid(T4_OLD)
    rows = []
    for qid, g in gold.items():
        def rank(hits):
            ids = [h.get("id") for h in hits or []]
            return ids.index(g) if g in ids else None
        rows.append({"qid": qid, "gold": g, "rank_new": rank(new_hits.get(qid)),
                     "rank_old": rank(old_hits.get(qid))})
    r1 = [1.0 if r["rank_new"] == 0 else 0.0 for r in rows]
    b1 = [1.0 if r["rank_old"] == 0 else 0.0 for r in rows]
    r5 = [1.0 if (r["rank_new"] is not None and r["rank_new"] < 5) else 0.0 for r in rows]
    b5 = [1.0 if (r["rank_old"] is not None and r["rank_old"] < 5) else 0.0 for r in rows]
    t4doc = json.load(open(T4_DOC, encoding="utf-8")) if os.path.exists(T4_DOC) else {}
    t4doc["delta_vs_t11"] = {
        "hit_at_1": {"new": sum(r1) / len(r1), "old": sum(b1) / len(b1),
                     "delta": boot(r1, b1, reps, rng)},
        "hit_at_5": {"new": sum(r5) / len(r5), "old": sum(b5) / len(b5),
                     "delta": boot(r5, b5, reps, rng)},
        "n": len(rows), "per_question": rows,
        "baseline_note": "T11 隔离库臂（`import` 丢 superseded_by → 实际无边）；旧数字 hit@1 0.045 / hit@5 1.000",
    }
    with open(T4_DOC, "w", encoding="utf-8") as f:
        json.dump(t4doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"[T4] hit@1={sum(r1)/len(r1):.3f} (旧 {sum(b1)/len(b1):.3f}) "
          f"hit@5={sum(r5)/len(r5):.3f} (旧 {sum(b5)/len(b5):.3f})")
    print(f"[T4] Δ hit@1={t4doc['delta_vs_t11']['hit_at_1']['delta']} "
          f"Δ hit@5={t4doc['delta_vs_t11']['hit_at_5']['delta']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

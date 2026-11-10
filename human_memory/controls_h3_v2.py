#!/usr/bin/env python3
"""controls_h3_v2.py — H3 v2 两个对照臂，用来把「时间效应」与「相邻混淆」拆开。

v2 主臂里「后写条目排前面」同时包含三个变化：created_at 更晚、写入路径不同
（import 显式过去时间 vs remember 现在）、索引插入更晚。三者在本设计里天然绑在一起，
所以必须补两个对照臂，否则不足以把 0.900/0.950 读成「系统认时间」：

  K1 insertion_control（同文、同路径、无反时间差）
    同一主题两条**正文逐字节相同**的条目，**两条都走 remember --force 顺序写入**，
    因此 created_at 都是「现在」、写入路径一致，唯一差别是插入先后。
    → 若这里 later_first 也很高，说明主臂的效应可以用「同会话后插者胜」解释，
      不能独归因于 created_at。

  K2 repeat1_control（只写 1 条 vs 干扰 1 条）
    同一主题只写 1 条事实 + 1 条同主题干扰，不重复。
    → 主臂 repeat 的 0.950 若与这里接近，说明那是「内容相关度」而不是「重复强化」。

两臂各自独立库（独立目录/端口/super），零 LLM，产物 results/h3v2-controls.json。
用法： python3 controls_h3_v2.py [--root /tmp/agimem-h3v2-ctl] [--base-port 16231]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gen_h3_v2 as gen  # 复用主题与事实库（只读）
import isolated_lib as il  # noqa: E402
import score_h3_v2 as sc  # 复用 wilson_ci
from run_h3_v2 import RESDIR  # 同目录约定


def rank_of(titles: List[str], target: str):
    for i, t in enumerate(titles):
        if t == target:
            return i
    return None


def run_insertion(root: str, port: int, n: int, limit: int = 5) -> Dict[str, Any]:
    topics = gen.TOPICS[:n]
    st = il.IsolatedStore(root, "k1-insertion", port).open()
    titles_a = [f"HM-K1-{i + 1:02d}-a" for i in range(n)]
    titles_b = [f"HM-K1-{i + 1:02d}-b" for i in range(n)]
    # 先全部写 a，再全部写 b：同路径（remember）、正文相同、created_at 都是「现在」
    for i, t in enumerate(topics):
        st.remember(gen.FACTS[t], titles_a[i])
    for i, t in enumerate(topics):
        st.remember(gen.FACTS[t], titles_b[i])
    ready = st.wait_index(expect_total=n * 2, budget=600)
    rows = []
    for i, t in enumerate(topics):
        rr = st.recall(f"「{t}」现在按哪条执行？", limit)
        titles = [h["title"] for h in rr["hits"]]
        scores = {h["title"]: h["score"] for h in rr["hits"]}
        ra, rb = rank_of(titles, titles_a[i]), rank_of(titles, titles_b[i])
        rows.append({"qid": f"k1-{i + 1:02d}", "query": f"「{t}」现在按哪条执行？",
                     "top": titles, "rank_a": ra, "rank_b": rb,
                     "later_first": (rb is not None and (ra is None or rb < ra)),
                     "tie": (ra is not None and rb is not None
                             and scores.get(titles_a[i]) == scores.get(titles_b[i])),
                     "score_gap": (scores[titles_b[i]] - scores[titles_a[i]])
                     if (titles_a[i] in scores and titles_b[i] in scores) else None})
    st.close()
    k = sum(1 for r in rows if r["later_first"])
    gaps = [r["score_gap"] for r in rows if r["score_gap"] is not None]
    return {"arm": "insertion_control", "n": len(rows), "index": ready, "rows": rows,
            "metrics": {"later_first": sc.wilson_ci(k, len(rows)),
                        "tie_rate": sc.wilson_ci(sum(1 for r in rows if r["tie"]), len(rows)),
                        "score_gap_mean": (sum(gaps) / len(gaps)) if gaps else None}}


def run_repeat1(root: str, port: int, n: int, limit: int = 5) -> Dict[str, Any]:
    topics = gen.TOPICS[:n]
    st = il.IsolatedStore(root, "k2-repeat1", port).open()
    st.import_items([il.item(f"HM-K2-{i + 1:02d}-f", gen.FACTS[t], gen.NEW_CREATED_AT)
                     for i, t in enumerate(topics)])
    for i, t in enumerate(topics):
        st.remember(gen.DISTRACTORS[t], f"HM-K2-{i + 1:02d}-z")
    ready = st.wait_index(expect_total=n * 2, budget=600)
    rows = []
    for i, t in enumerate(topics):
        rr = st.recall(f"「{t}」的做法是什么？", limit)
        titles = [h["title"] for h in rr["hits"]]
        rf = rank_of(titles, f"HM-K2-{i + 1:02d}-f")
        rz = rank_of(titles, f"HM-K2-{i + 1:02d}-z")
        rows.append({"qid": f"k2-{i + 1:02d}", "query": f"「{t}」的做法是什么？",
                     "top": titles, "fact_rank": rf, "distractor_rank": rz,
                     "fact_first": rf == 0,
                     "fact_beats_single": (rf < rz) if (rf is not None and rz is not None)
                     else (rz is None and rf is not None)})
    st.close()
    k = sum(1 for r in rows if r["fact_first"])
    kb = sum(1 for r in rows if r["fact_beats_single"])
    return {"arm": "repeat1_control", "n": len(rows), "index": ready, "rows": rows,
            "metrics": {"fact_first": sc.wilson_ci(k, len(rows)),
                        "fact_beats_single": sc.wilson_ci(kb, len(rows))}}


def run_reversed(root: str, port: int, n: int, limit: int = 5) -> Dict[str, Any]:
    """K3 反序臂（决定性对照）：**先** remember 写入「现在」的条目，**后** import 写入
    created_at=2025-03 的同文条目——即「插入更晚的是更旧的条目」。
    若 later_inserted(旧) 排前 → 插入顺序主导、created_at 无效；
    若 earlier_inserted(新) 排前 → created_at 主导。
    """
    topics = gen.TOPICS[:n]
    st = il.IsolatedStore(root, "k3-reversed", port).open()
    new_titles = [f"HM-K3-{i + 1:02d}-n" for i in range(n)]
    old_titles = [f"HM-K3-{i + 1:02d}-o" for i in range(n)]
    for i, t in enumerate(topics):
        st.remember(gen.FACTS[t], new_titles[i])          # 先写「新」的（created_at=now）
    st.import_items([il.item(old_titles[i], gen.FACTS[t], gen.OLD_CREATED_AT)
                     for i, t in enumerate(topics)])       # 后写「旧」的（created_at=2025-03）
    ready = st.wait_index(expect_total=n * 2, budget=600)
    rows = []
    for i, t in enumerate(topics):
        rr = st.recall(f"「{t}」现在按哪条执行？", limit)
        titles = [h["title"] for h in rr["hits"]]
        scores = {h["title"]: h["score"] for h in rr["hits"]}
        rn, ro = rank_of(titles, new_titles[i]), rank_of(titles, old_titles[i])
        rows.append({"qid": f"k3-{i + 1:02d}", "query": f"「{t}」现在按哪条执行？",
                     "top": titles, "rank_new": rn, "rank_old": ro,
                     "new_first": (rn is not None and (ro is None or rn < ro)),
                     "later_inserted_first": (ro is not None and (rn is None or ro < rn)),
                     "tie": (rn is not None and ro is not None
                             and scores.get(new_titles[i]) == scores.get(old_titles[i])),
                     "score_gap_new_minus_old": (scores[new_titles[i]] - scores[old_titles[i]])
                     if (new_titles[i] in scores and old_titles[i] in scores) else None})
    st.close()
    k = sum(1 for r in rows if r["new_first"])
    ki = sum(1 for r in rows if r["later_inserted_first"])
    gaps = [r["score_gap_new_minus_old"] for r in rows if r["score_gap_new_minus_old"] is not None]
    return {"arm": "reversed_insertion_control", "n": len(rows), "index": ready, "rows": rows,
            "metrics": {"new_first": sc.wilson_ci(k, len(rows)),
                        "later_inserted_first": sc.wilson_ci(ki, len(rows)),
                        "tie_rate": sc.wilson_ci(sum(1 for r in rows if r["tie"]), len(rows)),
                        "score_gap_new_minus_old_mean": (sum(gaps) / len(gaps)) if gaps else None}}


def main() -> int:
    ap = argparse.ArgumentParser(description="H3 v2 对照臂")
    ap.add_argument("--root", default="/tmp/agimem-h3v2-ctl")
    ap.add_argument("--base-port", type=int, default=16231)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--only", default="k1,k2,k3")
    args = ap.parse_args()
    only = args.only.split(",")
    out = os.path.join(RESDIR, "h3v2-controls.json")
    existing: Dict[str, Any] = {}
    if os.path.exists(out):
        with open(out, encoding="utf-8") as f:
            existing = json.load(f)

    if "k3" in only:
        k3 = run_reversed(args.root, args.base_port + 2, args.n, args.limit)
        m3 = k3["metrics"]
        print(f"[k3] new_first={m3['new_first']['point']:.3f} "
              f"later_inserted_first={m3['later_inserted_first']['point']:.3f} "
              f"tie={m3['tie_rate']['point']:.3f} "
              f"gap={m3['score_gap_new_minus_old_mean']}", flush=True)
        existing["reversed_insertion_control"] = k3
        existing.setdefault("schema", "agimem-h3-v2-controls/1")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"[controls] 写出 {out}")
        if only == ["k3"]:
            return 0

    k1 = run_insertion(args.root, args.base_port, args.n, args.limit)
    print(f"[k1] later_first={k1['metrics']['later_first']['point']:.3f} "
          f"tie={k1['metrics']['tie_rate']['point']:.3f} "
          f"gap={k1['metrics']['score_gap_mean']}", flush=True)
    k2 = run_repeat1(args.root, args.base_port + 1, args.n, args.limit)
    print(f"[k2] fact_first={k2['metrics']['fact_first']['point']:.3f} "
          f"fact_beats_single={k2['metrics']['fact_beats_single']['point']:.3f}", flush=True)

    out = os.path.join(RESDIR, "h3v2-controls.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"schema": "agimem-h3-v2-controls/1",
                   "purpose": "把主臂的「后写先排」拆成 created_at / 写入路径 / 插入顺序，"
                              "并检验 repeat 优势是不是内容相关度",
                   "insertion_control": k1, "repeat1_control": k2},
                  f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"[controls] 写出 {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

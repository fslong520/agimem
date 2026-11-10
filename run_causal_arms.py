#!/usr/bin/env python3
"""run_causal_arms.py — H2 因果层三条对照臂（各用独立隔离库，端口 16303/16304/16305）。

臂定义（全部同 122 题、同判分器、同 topk=5、完整 recall JSON）：

  D1 `leaves`    只导入树的**叶子节点**（95/143）：库里没有任何祖先/后代关系可被当成结构线索，
                 链题 gold 里的内部节点在库中不存在。
  D2 `half`      **随机一半节点**（72/143，seed 固定）：给第二个退化点，看分数是否随「库内相关节点覆盖率」单调变化。
  注：原本想做的「剥掉父子边」臂**做不出来也不必要**——`import` 无法给已存在条目补父子边（实测：两遍导入
      第二遍 `duplicates 2 / reattached 0`，`ancestors` 恒为空），且 T15 的完整树臂本来就没有任何边。
  E1 `full`      完整树复跑（与 T15 同配置，另一端口），并额外跑一份**不点名节点**的题面
                 （把链题里「<节点标题>」改写成「这一步」），用于 hit@1=0 的成因对照。

E1 的完整树复跑同时充当 T15 的复现校验（同判分器、不同库实例）。

用法：
    python3 run_causal_arms.py [--arms leaves,noparent,full] [--root /tmp/agimem-causal-arms]
产物：results/causal-arms/<arm>-predictions.jsonl、results/causal-arms/<arm>-anon-predictions.jsonl、
      results/causal-arms-run-stats.json
"""
from __future__ import annotations

import argparse
import json
import random
import os
import re
import sys
import time
from typing import Any, Dict, List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import isolated_lib as il  # noqa: E402

TREE = os.path.join(HERE, "data", "tree.json")
DATASET = os.path.join(HERE, "dataset", "causal_evalset.jsonl")
OUTDIR = os.path.join(HERE, "results", "causal-arms")
M3 = getattr(il, "M3_DEFAULT", os.path.expanduser("~/.rsrs/models/bge-m3"))
PORT = {"leaves": 16303, "half": 16304, "full": 16305}


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def title_to_id(title: str) -> str:
    if not title or il.TITLE_SEP not in title:
        return ""
    cand = title.rsplit(il.TITLE_SEP, 1)[-1].strip()
    return cand if cand.startswith("snt") else ""


def recall_full(st: il.IsolatedStore, query: str, limit: int) -> List[Dict[str, Any]]:
    p = il.run(["rsrs", "recall", query, "--limit", str(limit), "--json"],
               st.env, timeout=600, check=False)
    d = il.parse_env(p.stdout) or {}
    hits = []
    for h in d.get("details") or []:
        if not isinstance(h, dict):
            continue
        entry = h.get("entry") if isinstance(h.get("entry"), dict) else {}
        nid = title_to_id(h.get("title") or entry.get("title") or "")
        if nid:
            hits.append({"id": nid, "score": h.get("score"),
                         "superseded_by": h.get("superseded_by")})
    return hits


def split_dedupe(nodes: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    seen, imp, rem = set(), [], []
    for n in nodes:
        if n["content"] in seen:
            rem.append(n)
        else:
            seen.add(n["content"])
            imp.append(n)
    return imp, rem


def build_arm(arm: str, nodes: List[Dict[str, Any]], root: str) -> il.IsolatedStore:
    st = il.IsolatedStore(root, arm, PORT[arm], M3).open()
    imp, rem = split_dedupe(nodes)
    items = []
    for n in imp:
        it = il.item(f"{n['title']}{il.TITLE_SEP}{n['id']}", n["content"],
                     f"{n.get('ts', '2026-06-01')}T09:00:00Z",
                     tags=[n.get("tree", ""), n.get("outcome", "")])
        items.append(it)
    p = st.import_items(items)
    d = il.parse_env(p.stdout) or {}
    print(f"[{arm}] import {d.get('summary')} (nodes={len(nodes)} 去重后 import {len(imp)} / remember {len(rem)})",
          flush=True)
    for n in rem:
        st.remember(n["content"], f"{n['title']}{il.TITLE_SEP}{n['id']}")
    ready = st.wait_index(expect_total=len(nodes), budget=900)
    print(f"[{arm}] index {json.dumps(ready, ensure_ascii=False)}", flush=True)
    return st


def collect(st: il.IsolatedStore, cases: List[Dict[str, Any]], limit: int,
            anon: bool = False, tree_titles: Dict[str, str] = None) -> List[Dict[str, Any]]:
    rows = []
    for i, c in enumerate(cases, 1):
        q = c["query"]
        if anon:
            q = anonymize(c, tree_titles)
        rows.append({"qid": c["qid"], "query": q, "type": c["type"],
                     "hits": recall_full(st, q, limit)})
        if i % 40 == 0:
            print(f"    … {i}/{len(cases)}{' (anon)' if anon else ''}", flush=True)
    return rows


def anonymize(case: Dict[str, Any], tree_titles: Dict[str, str]) -> str:
    """把链题题面里点名的节点标题替换成「这一步」，去掉自命中线索。"""
    node = (case.get("gold_expr") or {}).get("node")
    title = tree_titles.get(node or "", "")
    q = case["query"]
    if not title:
        return q
    out = q.replace(f"「{title}」", "「这一步」").replace(title, "这一步")
    return out


def write(path: str, rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="H2 因果层对照臂")
    ap.add_argument("--arms", default="leaves,noparent,full")
    ap.add_argument("--root", default="/tmp/agimem-causal-arms")
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()

    tree = json.load(open(TREE, encoding="utf-8"))
    nodes = tree["nodes"]
    cases = load_jsonl(DATASET)
    titles = {n["id"]: n["title"] for n in nodes}
    kids: Dict[str, int] = {}
    for n in nodes:
        if n.get("parent_id"):
            kids[n["parent_id"]] = kids.get(n["parent_id"], 0) + 1
    leaves = [n for n in nodes if kids.get(n["id"], 0) == 0]

    stats: Dict[str, Any] = {"schema": "agimem-causal-arms/1", "arms": {}}
    t0 = time.time()
    for arm in [a for a in args.arms.split(",") if a in PORT]:
        if arm == "leaves":
            use = leaves
        elif arm == "half":
            rnd = random.Random(20261109)
            use = rnd.sample(nodes, len(nodes) // 2)
        else:
            use = nodes
        st = build_arm(arm, use, args.root)
        rows = collect(st, cases, args.limit)
        write(os.path.join(OUTDIR, f"{arm}-predictions.jsonl"), rows)
        stat = {"arm": arm, "data_dir": st.dir, "port": st.port,
                "n_nodes_in_store": len(use),
                "n_questions": len(rows),
                "n_hits": sum(len(r["hits"]) for r in rows),
                "n_zero_hit": sum(1 for r in rows if not r["hits"])}
        if arm == "full":
            anon = collect(st, cases, args.limit, anon=True, tree_titles=titles)
            write(os.path.join(OUTDIR, "full-anon-predictions.jsonl"), anon)
            stat["anon"] = {"n_hits": sum(len(r["hits"]) for r in anon),
                            "n_changed_query": sum(1 for a, b in zip(anon, cases)
                                                   if a["query"] != b["query"])}
        st.close()
        stats["arms"][arm] = stat
        print(f"[{arm}] done {json.dumps(stat, ensure_ascii=False)}", flush=True)

    stats["elapsed_s"] = round(time.time() - t0, 1)
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(HERE, "results", "causal-arms-run-stats.json"), "w",
              encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"[arms] 写出 results/causal-arms-run-stats.json  elapsed={stats['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())

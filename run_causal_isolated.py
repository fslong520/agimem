#!/usr/bin/env python3
"""run_causal_isolated.py — H2 因果层：把合成因果树写进隔离库，再逐题**完整 JSON**采集。

为什么必须用完整 JSON（不带 `--titles`）：
  T9/tests/34 已实测 `--titles` 载荷**不下发 `superseded_by`**，导致 H4 的取代题必然假低分。
  H2 的 `supersession` 题型口径就是「用好已种取代标记（oracle）」，若接口不下发该字段，
  这条指标在接口层不可测。所以本脚本**先核实字段是否下发**，再决定判分口径（见 stats 里的
  `n_details_with_superseded_by_key` / `n_details_with_superseded_by_value`）。

写入：
  - `import` 批写正文唯一的节点；正文重复的节点（本轮 1 对，来自 gen_tree 的兜底「新结论」）
    走 `remember --force`（`import` 会按正文去重吞掉）。
  - 标题统一 `原文｜<snt id>`，召回后按后缀反解回合成 id；隔离库 UUID 不落盘。

用法：
    python3 run_causal_isolated.py [--root /tmp/agimem-causal-iso] [--port 16301] [--limit 5]
产物：results/causal-isolated-predictions.jsonl、results/causal-isolated-run-stats.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import isolated_lib as il  # noqa: E402

TREE = os.path.join(HERE, "data", "tree.json")
DATASET = os.path.join(HERE, "dataset", "causal_evalset.jsonl")
RESDIR = os.path.join(HERE, "results")


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def title_to_id(title: str) -> str:
    if not title or il.TITLE_SEP not in title:
        return ""
    cand = title.rsplit(il.TITLE_SEP, 1)[-1].strip()
    return cand if cand.startswith("snt") else ""


def run_full_recall(st: il.IsolatedStore, query: str, limit: int) -> Dict[str, Any]:
    """完整 JSON（不带 --titles）：这是核实 superseded_by 是否下发的唯一途径。"""
    p = il.run(["rsrs", "recall", query, "--limit", str(limit), "--json"],
               st.env, timeout=600, check=False)
    d = il.parse_env(p.stdout) or {}
    details = d.get("details") or []
    hits: List[Dict[str, Any]] = []
    n_key = n_val = 0
    for h in details:
        if not isinstance(h, dict):
            continue
        entry = h.get("entry") if isinstance(h.get("entry"), dict) else {}
        title = h.get("title") or entry.get("title") or ""
        nid = title_to_id(title)
        if not nid:
            continue
        # superseded_by 可能在顶层，也可能在 entry 里；两处都查，并分别计数
        sup = None
        if "superseded_by" in h:
            n_key += 1
            sup = h.get("superseded_by")
        elif "superseded_by" in entry:
            n_key += 1
            sup = entry.get("superseded_by")
        if sup:
            n_val += 1
        hits.append({"id": nid, "score": h.get("score"), "superseded_by": sup})
    return {"rc": p.returncode, "hits": hits, "n_details": len(details),
            "n_key": n_key, "n_val": n_val,
            "embedding_model": (d.get("summary") or {}).get("embedding_model"),
            "keys_sample": sorted(details[0].keys()) if details else []}


def main() -> int:
    ap = argparse.ArgumentParser(description="H2 因果层隔离库实跑")
    ap.add_argument("--root", default="/tmp/agimem-causal-iso")
    ap.add_argument("--tag", default="causal")
    ap.add_argument("--port", type=int, default=16301)
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--out", default=os.path.join(RESDIR, "causal-isolated-predictions.jsonl"))
    ap.add_argument("--stats", default=os.path.join(RESDIR, "causal-isolated-run-stats.json"))
    args = ap.parse_args()

    tree = json.load(open(TREE, encoding="utf-8"))
    nodes = tree["nodes"]
    cases = load_jsonl(DATASET)
    os.makedirs(RESDIR, exist_ok=True)

    # 按正文分组：正文唯一的走 import，重复的（除首条外）走 remember --force
    by_body: Dict[str, List[Dict[str, Any]]] = {}
    for n in nodes:
        by_body.setdefault(n["content"], []).append(n)
    imp_nodes, rem_nodes = [], []
    for body, group in by_body.items():
        imp_nodes.append(group[0])
        rem_nodes.extend(group[1:])

    m3 = getattr(il, "M3_DEFAULT", None) or os.path.expanduser("~/.rsrs/models/bge-m3")
    st = il.IsolatedStore(args.root, args.tag, args.port, m3).open()
    t0 = time.time()
    print(f"[causal] store={st.dir} port={st.port} 节点={len(nodes)} "
          f"(import {len(imp_nodes)} / remember {len(rem_nodes)}) 题={len(cases)}", flush=True)

    p = st.import_items([il.item(f"{n['title']}{il.TITLE_SEP}{n['id']}", n["content"],
                                 f"{n.get('ts', '2026-06-01')}T09:00:00Z",
                                 tags=[n.get("tree", ""), n.get("outcome", "")])
                         for n in imp_nodes])
    d = il.parse_env(p.stdout) or {}
    print(f"[causal] import rc={p.returncode} {json.dumps(d.get('summary') or {}, ensure_ascii=False)}",
          flush=True)
    if p.returncode != 0:
        st.close()
        return 1

    for n in rem_nodes:
        r = st.remember(n["content"], f"{n['title']}{il.TITLE_SEP}{n['id']}")
        print(f"[causal] remember {n['id']} rc={r.returncode}", flush=True)
        if r.returncode != 0:
            st.close()
            return 1

    ready = st.wait_index(expect_total=len(nodes), budget=900)
    print(f"[causal] index {json.dumps(ready, ensure_ascii=False)}", flush=True)

    # 第一枪：就第一题的完整 JSON 打印字段，人工可核（并进 stats）
    first = run_full_recall(st, cases[0]["query"], args.limit)
    print(f"[causal] 首题完整 JSON：details={first['n_details']} "
          f"hits={len(first['hits'])} superseded_by键出现={first['n_key']} "
          f"非空={first['n_val']} 顶层键={first['keys_sample']}", flush=True)

    rows: List[Dict[str, Any]] = []
    tot_det = tot_key = tot_val = tot_hit = 0
    sup_key_q = sup_val_q = 0
    per: List[Dict[str, Any]] = []
    for i, c in enumerate(cases, 1):
        rr = run_full_recall(st, c["query"], args.limit)
        tot_det += rr["n_details"]
        tot_key += rr["n_key"]
        tot_val += rr["n_val"]
        tot_hit += len(rr["hits"])
        if rr["n_key"]:
            sup_key_q += 1
        if rr["n_val"]:
            sup_val_q += 1
        rows.append({"qid": c["qid"], "query": c["query"], "type": c["type"],
                     "hits": rr["hits"]})
        per.append({"qid": c["qid"], "type": c["type"], "n_hits": len(rr["hits"]),
                    "sup_keys": rr["n_key"], "sup_values": rr["n_val"]})
        if i % 20 == 0:
            print(f"  … {i}/{len(cases)}", flush=True)

    with open(args.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    st.close()
    stats = {
        "arm": "isolated-rsrs-causal",
        "data_dir": st.dir, "port": st.port,
        "n_nodes": len(nodes), "n_imported": len(imp_nodes), "n_remembered": len(rem_nodes),
        "import_summary": d.get("summary"),
        "index": ready,
        "n_questions": len(cases),
        "limit": args.limit,
        "n_hits": tot_hit,
        "n_details": tot_det,
        "n_details_with_superseded_by_key": tot_key,
        "n_details_with_superseded_by_value": tot_val,
        "n_questions_with_superseded_by_key": sup_key_q,
        "n_questions_with_superseded_by_value": sup_val_q,
        "first_question_keys_sample": first["keys_sample"],
        "payload": "完整 recall JSON（未带 --titles）",
        "notes": "隔离库（/tmp 独立 data dir + 端口 + super）；未触碰 ~/.rsrs；命中按标题｜snt id 反解，UUID 不落盘",
        "per_question": per,
        "elapsed_s": round(time.time() - t0, 1),
    }
    with open(args.stats, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({k: stats[k] for k in stats if k != "per_question"}, ensure_ascii=False)[:1200])
    return 0


if __name__ == "__main__":
    sys.exit(main())

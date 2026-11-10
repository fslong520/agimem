#!/usr/bin/env python3
"""run_tricky_new132.py — T26 对照：新 132 段单独建库（只装新段 748 节点）跑一遍。

用途：分离「新段题面本身更容易」与「合并库 1496 节点的检索条件」两个因素。
若新段在独立库上仍明显高于旧段，则漂移来自题面/seed，而非合并库干扰。
"""
from __future__ import annotations
import argparse, json, os, sys, time
from typing import Any, Dict, List
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import isolated_lib as il  # noqa: E402

RESDIR = os.path.join(HERE, "results")

def load_jsonl(p): 
    with open(p, encoding="utf-8") as f: return [json.loads(x) for x in f if x.strip()]

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/tmp/agimem-tricky-new132")
    ap.add_argument("--tag", default="iso")
    ap.add_argument("--port", type=int, default=16332)
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--m3", default=il.M3_DEFAULT)
    ap.add_argument("--out", default=os.path.join(RESDIR, "tricky-new132-isolated-predictions.jsonl"))
    ap.add_argument("--stats", default=os.path.join(RESDIR, "tricky-new132-isolated-stats.json"))
    args = ap.parse_args()
    tree = json.load(open(os.path.join(HERE,"data","tricky_tree_v2.json"), encoding="utf-8"))
    nodes = tree["nodes"]
    cases = load_jsonl(os.path.join(HERE,"dataset","tricky_evalset_v2.jsonl"))
    st = il.IsolatedStore(args.root, args.tag, args.port, args.m3).open()
    t0 = time.time()
    print(f"[new132] store={st.dir} port={st.port} 节点={len(nodes)} 题={len(cases)}", flush=True)
    p = st.import_items([il.node_to_item(n) for n in nodes])
    d = il.parse_env(p.stdout) or {}
    print(f"[new132] import {json.dumps(d.get('summary') or {}, ensure_ascii=False)}", flush=True)
    if p.returncode != 0:
        st.close(); return 1
    ready = st.wait_index(expect_total=len(nodes), budget=2400)
    print(f"[new132] index {json.dumps(ready, ensure_ascii=False)}", flush=True)
    rows=[]; n_hits=0; empty=0
    for i,c in enumerate(cases,1):
        r = st.recall(c["query"], args.limit)
        hits=[]
        for h in r["hits"]:
            nid = il.title_to_node(h.get("title") or "")
            hits.append({"id": nid or "ext0000", "score": h.get("score")})
        n_hits += len(hits)
        if not hits: empty += 1
        rows.append({"qid": c["qid"], "query": c["query"], "hits": hits})
        if i % 40 == 0: print(f"  … {i}/{len(cases)}", flush=True)
    with open(args.out,"w",encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False)+"\n")
    st.close()
    stats={"arm":"isolated-rsrs-tricky-new132","data_dir":st.dir,"port":st.port,
           "n_nodes":len(nodes),"n_questions":len(cases),"limit":args.limit,
           "n_hits":n_hits,"n_empty":empty,"index_ready":ready,
           "import_summary":d.get("summary"),"elapsed_s":round(time.time()-t0,1),
           "notes":"新132段独立库对照（只装新段 748 节点）"}
    json.dump(stats, open(args.stats,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k:stats[k] for k in stats if k not in ("index_ready",)}, ensure_ascii=False)[:600])
    return 0

if __name__ == "__main__":
    sys.exit(main())

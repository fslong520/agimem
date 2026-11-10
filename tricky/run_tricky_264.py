#!/usr/bin/env python3
"""run_tricky_264.py — T26：合并 748+748 节点导入隔离库，跑 264 题完整 JSON 召回。

复用 tricky/isolated_lib.py 的 IsolatedStore（独立 data dir + 独立端口 + 独立 super +
RSRS_ABLATE=hot）。命中按标题｜trk id 反解回合成 id，隔离库 UUID 不落盘。

用法：
    python3 run_tricky_264.py --root /tmp/agimem-tricky264 --tag iso --port 16330
产物：
    results/tricky-264-isolated-predictions.jsonl / results/tricky-264-isolated-stats.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import isolated_lib as il  # noqa: E402

RESDIR = os.path.join(HERE, "results")
TREE_OLD = os.path.join(HERE, "data", "tricky_tree.json")
TREE_NEW = os.path.join(HERE, "data", "tricky_tree_v2.json")
SET_OLD = os.path.join(HERE, "dataset", "tricky_evalset.jsonl")
SET_NEW = os.path.join(HERE, "dataset", "tricky_evalset_v2.jsonl")


def load_jsonl(p: str) -> List[Dict[str, Any]]:
    with open(p, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]



def _super_from_running(port: int) -> str:
    """从正在运行的隔离 runtime 进程环境里取 RSRS_SUPER（session.json 不存明文）。"""
    import glob
    for path in glob.glob("/proc/[0-9]*/environ"):
        try:
            raw = open(path, "rb").read().decode("utf-8", "replace")
        except OSError:
            continue
        if f"RSRS_RPC_PORT={port}" not in raw or "RSRS_SUPER=" not in raw:
            continue
        for kv in raw.split("\0"):
            if kv.startswith("RSRS_SUPER="):
                return kv.split("=", 1)[1]
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="H4 264 题隔离库真跑")
    ap.add_argument("--root", default="/tmp/agimem-tricky264")
    ap.add_argument("--tag", default="iso")
    ap.add_argument("--port", type=int, default=16330)
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--m3", default=il.M3_DEFAULT)
    ap.add_argument("--out", default=os.path.join(RESDIR, "tricky-264-isolated-predictions.jsonl"))
    ap.add_argument("--stats", default=os.path.join(RESDIR, "tricky-264-isolated-stats.json"))
    ap.add_argument("--resume", action="store_true",
                    help="复用已建好的隔离库（跳过 rmtree/导入/建索引），只跑采集")
    args = ap.parse_args()

    tree_old, tree_new = json.load(open(TREE_OLD, encoding="utf-8")), json.load(open(TREE_NEW, encoding="utf-8"))
    nodes = tree_old["nodes"] + tree_new["nodes"]
    cases = load_jsonl(SET_OLD) + load_jsonl(SET_NEW)
    os.makedirs(RESDIR, exist_ok=True)

    # 合并树节点 id 唯一性（T25 已证，这里再断言一次）
    ids = [n["id"] for n in nodes]
    if len(ids) != len(set(ids)):
        print("[264] 合并树节点 id 重复，停止", file=sys.stderr)
        return 1

    t0 = time.time()
    if args.resume:
        st = il.IsolatedStore(args.root, args.tag, args.port, args.m3)
        st.dir = os.path.join(args.root, args.tag)
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("RSRS_", "ONEMEMORY_", "RESPIRE_"))}
        # 复用既有库：super 从运行中的 runtime 进程环境取（session.json 不存明文）
        super_ = _super_from_running(st.port)
        if not super_:
            print("[264] --resume 找不到该端口的运行时 super，停止", file=sys.stderr)
            return 1
        env.update(RSRS_DATA_DIR=st.dir, RSRS_RPC_PORT=str(st.port), RSRS_SUPER=super_,
                   RSRS_NO_AUTOSYNC="1", RSRS_UPDATE_CHECK="0", RSRS_ENGINE="cpu",
                   RSRS_M3_DIR=args.m3, RSRS_FEEDBACK="0", RSRS_ABLATE="hot")
        st.env = env
        st.super = super_
        imported = {"resumed": True}
        ready = st.status().get("retrieval_index") or {}
        print(f"[264] resume store={st.dir} port={st.port} 索引={json.dumps(ready, ensure_ascii=False)}",
              flush=True)
    else:
        st = il.IsolatedStore(args.root, args.tag, args.port, args.m3).open()
        print(f"[264] store={st.dir} port={st.port} 节点={len(nodes)} 题={len(cases)}", flush=True)

        items = [il.node_to_item(n) for n in nodes]
        p = st.import_items(items)
        d = il.parse_env(p.stdout) or {}
        imported = d.get("summary") or {}
        print(f"[264] import rc={p.returncode} {json.dumps(imported, ensure_ascii=False)[:400]}",
              flush=True)
        if p.returncode != 0:
            st.close()
            return 1

        ready = st.wait_index(expect_total=len(nodes), budget=1800)
        print(f"[264] index {json.dumps(ready, ensure_ascii=False)}", flush=True)

    rows: List[Dict[str, Any]] = []
    per: List[Dict[str, Any]] = []
    n_hits = n_unmapped = n_empty = 0
    scores: List[float] = []
    modes, emb = set(), set()
    seq = 0
    for i, c in enumerate(cases, 1):
        r = st.recall(c["query"], args.limit)
        hits = []
        for h in r["hits"]:
            nid = il.title_to_node(h.get("title") or "")
            if nid is None:
                n_unmapped += 1
                seq += 1
                nid = f"ext{seq:04d}"
            hits.append({"id": nid, "score": h.get("score")})
            if isinstance(h.get("score"), (int, float)):
                scores.append(float(h["score"]))
        n_hits += len(hits)
        if not hits:
            n_empty += 1
        modes.add(str(r.get("mode")))
        if r.get("embedding_model"):
            emb.add(str(r["embedding_model"]))
        rows.append({"qid": c["qid"], "query": c["query"], "hits": hits})
        per.append({"qid": c["qid"], "type": c["type"], "n_hits": len(hits),
                    "top1": hits[0]["id"] if hits else None})
        if i % 30 == 0:
            print(f"  … {i}/{len(cases)}", flush=True)

    with open(args.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    st.close()
    stats = {
        "arm": "isolated-rsrs-tricky-264",
        "data_dir": st.dir, "port": st.port,
        "n_nodes_imported": len(nodes) if args.resume else len(items),
        "n_questions": len(cases),
        "n_questions_old": len(load_jsonl(SET_OLD)),
        "n_questions_new": len(load_jsonl(SET_NEW)),
        "limit": args.limit,
        "n_hits": n_hits, "n_unmapped_hits": n_unmapped, "n_empty_questions": n_empty,
        "score_min": min(scores) if scores else None,
        "score_max": max(scores) if scores else None,
        "recall_modes": sorted(modes), "embedding_models": sorted(emb),
        "index_ready": ready, "import_summary": imported,
        "notes": "隔离库（/tmp 独立 data dir + 端口 + super，RSRS_ABLATE=hot）；未触碰 ~/.rsrs；"
                 "命中标题｜trk条目号 映射回合成 id，UUID 不落盘",
        "per_question": per,
        "elapsed_s": round(time.time() - t0, 1),
    }
    with open(args.stats, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({k: stats[k] for k in stats if k != "per_question"}, ensure_ascii=False)[:900])
    return 0


if __name__ == "__main__":
    sys.exit(main())

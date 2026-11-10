#!/usr/bin/env python3
"""把 agimem 的合成语料灌进 mem0 并取召回预测（replicate harness）。

用法：
    python3 run_layer_mem0.py --layer h6 --out-dir out/
    python3 run_layer_mem0.py --layer h7 --top-k 20

设计约束（为什么这么做，见 README.md）：
- 主臂 `add(infer=False)`：agimem 的 gold 绑合成 id，任何 LLM 抽取都会合并/改写条目
  导致 id 断裂。rsrs 侧也是 import 原样入库，两边同口径才可比。
- 嵌入用本地 bge-m3 ONNX，与 respire-cli 的 M3_SPEC 同源（1024 维 / CLS / L2 / 512 token）。
- 向量库用 chroma 本地目录（纯稠密，无关键词/BM25 通道）。
- 只跑结构上可复现的子类：
    h6 全跑（P3 需要真删，脚本会删 12 个目标后再跑 post 相位）
    h7 只跑 L3/L4（L1 多跳、L2 链深需要 parent 边，mem0 没有）
    h8 只跑 C1/C3/C4（C2 陈化需要 created_at，mem0 OSS 拒写显式时间戳）
    h9 全跑 R1–R6
- 产物只含合成 id；真 UUID 只在内存里做映射，不落盘。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

# mem0 默认会带遥测，bench 环境关掉
os.environ.setdefault("MEM0_TELEMETRY", "False")

import m3_embedder as m3  # noqa: E402

TITLE_SEP = "｜"
SYN_RE = re.compile(r"hl[0-9]?[A-Z]?\d{4}|h[789][A-Z]\d{4}")
UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

LAYERS = {
    "h6": {"dir": "humanlike2", "tree": "data/h6_tree.json", "ds": "dataset/h6_evalset.jsonl",
           "types": {"P1", "P2", "P3", "P4", "P5", "P6"}, "skipped": {},
           "p3_delete": True},
    "h7": {"dir": "h7", "tree": "data/h7_tree.json", "ds": "dataset/h7_evalset.jsonl",
           "types": {"L3", "L4"},
           "skipped": {"L1": "多跳链需要 parent 边，mem0 无父子关系",
                       "L2": "链深判定依赖链结构"}, "p3_delete": False},
    "h8": {"dir": "h8", "tree": "data/h8_tree.json", "ds": "dataset/h8_evalset.jsonl",
           "types": {"C1", "C3", "C4"},
           "skipped": {"C2": "陈化依赖 created_at，mem0 OSS 拒写显式时间戳（ValueError）"},
           "p3_delete": False},
    "h9": {"dir": "h9", "tree": "data/h9_tree.json", "ds": "dataset/h9_evalset.jsonl",
           "types": {"R1", "R2", "R3", "R4", "R5", "R6"}, "skipped": {}, "p3_delete": False},
}


def load_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def node_text(n):
    """与 rsrs 臂同词面：标题带 id 后缀、正文带条目尾注，拼成 mem0 的单字段文本。"""
    return (f"{n['title']}{TITLE_SEP}{n['id']}\n"
            f"{n['content']}\n（条目 {n['id']}；场景 {n.get('scenario', '')}）")


def syn_of(item):
    md = item.get("metadata") or {}
    if md.get("syn_id"):
        return md["syn_id"]
    hits = SYN_RE.findall(str(item.get("memory") or ""))
    return hits[0] if hits else ""


def build_memory(layer: str, store: str):
    from mem0 import Memory

    os.makedirs(os.path.dirname(store) or ".", exist_ok=True)
    if os.path.isdir(store):
        shutil.rmtree(store)
    cfg = {"embedder": {"provider": "m3onnx"},
           "vector_store": {"provider": "chroma",
                            "config": {"collection_name": f"{layer}nodes", "path": store}},
           # infer=False 不会调用 LLM；这个 provider 只是占位，别配真 key
           "llm": {"provider": "openai", "config": {"api_key": "unused-infer-false"}}}
    mem = Memory.from_config(cfg)
    if type(mem.embedding_model).__name__ != "Mem0M3Embedding":
        raise SystemExit("嵌入器不是 bge-m3，停")
    return mem


def main() -> int:
    ap = argparse.ArgumentParser(description="agimem 语料 → mem0 召回预测")
    ap.add_argument("--layer", required=True, choices=list(LAYERS))
    ap.add_argument("--out-dir", default=os.path.join(HERE, "out"))
    ap.add_argument("--top-k", type=int, default=20, help="mem0 原生缺省 20")
    ap.add_argument("--store", default=None, help="chroma 目录，缺省 /tmp/agimem-mem0/<layer>")
    args = ap.parse_args()

    spec = LAYERS[args.layer]
    base = os.path.join(REPO, spec["dir"])
    tree = json.load(open(os.path.join(base, spec["tree"]), encoding="utf-8"))
    nodes = tree["nodes"]
    qs = [q for q in load_jsonl(os.path.join(base, spec["ds"])) if q["type"] in spec["types"]]
    store = args.store or f"/tmp/agimem-mem0/{args.layer}"
    user = args.layer

    m3.register()
    t0 = time.time()
    mem = build_memory(args.layer, store)
    print(f"[{args.layer}] mem0 ready {time.time()-t0:.1f}s store={store}", flush=True)
    print(f"[{args.layer}] nodes={len(nodes)} 跑 {sorted(spec['types'])} "
          f"跳 {sorted(spec['skipped'])}", flush=True)

    # ── 灌库 ──
    t0 = time.time()
    syn2uuid = {}
    for i, n in enumerate(nodes, 1):
        md = {"syn_id": n["id"], "role": n.get("role", ""),
              "scenario": n.get("scenario", ""), "topic": n.get("topic", "")}
        r = mem.add(node_text(n), user_id=user, infer=False, metadata=md)
        if len(r["results"]) != 1:
            raise SystemExit(f"{n['id']}: add 落 {len(r['results'])} 条（期望 1）")
        syn2uuid[n["id"]] = r["results"][0]["id"]
        if i % 80 == 0:
            print(f"  ingest {i}/{len(nodes)} {time.time()-t0:.0f}s", flush=True)
    print(f"[{args.layer}] ingest {len(syn2uuid)}/{len(nodes)} {time.time()-t0:.0f}s", flush=True)
    if len(syn2uuid) != len(nodes):
        raise SystemExit(f"入库数 {len(syn2uuid)} ≠ {len(nodes)}")

    def do_search(q):
        s = mem.search(q["query"], top_k=args.top_k, filters={"user_id": user})
        items = s["results"] if isinstance(s, dict) else s
        hits, uniq = [], set()
        for it in items:
            sid = syn_of(it)
            if not sid or sid in uniq:
                continue
            uniq.add(sid)
            hits.append({"id": sid, "score": float(it.get("score") or 0.0)})
        return hits, len(items)

    preds, diag = [], []
    t1 = time.time()

    # P3 有 pre/post 两相位：post 必须在真删之后跑（h6）
    first = [q for q in qs
             if not (spec["p3_delete"] and q["type"] == "P3" and q.get("subtype") == "post")]
    for q in first:
        hits, nraw = do_search(q)
        preds.append({"qid": q["qid"], "query": q["query"], "hits": hits})
        diag.append({"qid": q["qid"], "type": q["type"], "n_raw": nraw, "n_hits": len(hits)})

    deleted, del_err = [], []
    if spec["p3_delete"]:
        topics = {}
        for q in qs:
            if q["type"] == "P3":
                topics.setdefault(q["gold_expr"]["topic"], {})[q["gold_expr"]["phase"]] = q
        for topic, ph in topics.items():
            gid = ph["pre"]["gold_expr"]["gold"]
            u = syn2uuid.get(gid)
            if not u:
                del_err.append({"topic": topic, "gold": gid, "err": "无 uuid 映射"})
                continue
            try:
                mem.delete(u)
                deleted.append({"topic": topic, "gold": gid})
            except Exception as e:                                  # noqa: BLE001
                del_err.append({"topic": topic, "gold": gid, "err": f"{type(e).__name__}: {e}"})
        print(f"[{args.layer}] delete ok={len(deleted)} err={len(del_err)}", flush=True)
        for q in [x for x in qs if x["type"] == "P3" and x.get("subtype") == "post"]:
            hits, nraw = do_search(q)
            preds.append({"qid": q["qid"], "query": q["query"], "hits": hits})
            diag.append({"qid": q["qid"], "type": q["type"], "n_raw": nraw, "n_hits": len(hits)})

    print(f"[{args.layer}] query {len(preds)} 题 {time.time()-t1:.0f}s", flush=True)

    order = {q["qid"]: i for i, q in enumerate(qs)}
    preds.sort(key=lambda p: order.get(p["qid"], 10**6))
    if UUID_RE.search(json.dumps(preds, ensure_ascii=False)):
        raise SystemExit("预测含真 UUID，拒绝落盘")

    od = os.path.join(args.out_dir, args.layer)
    os.makedirs(od, exist_ok=True)
    p20 = os.path.join(od, f"{args.layer}-mem0-predictions.jsonl")
    with open(p20, "w", encoding="utf-8") as f:
        for p in preds:
            f.write(json.dumps(p, ensure_ascii=False, sort_keys=True) + "\n")
    p5 = os.path.join(od, f"{args.layer}-mem0-predictions-top5.jsonl")
    with open(p5, "w", encoding="utf-8") as f:
        for p in preds:
            q = dict(p)
            q["hits"] = p["hits"][:5]
            f.write(json.dumps(q, ensure_ascii=False, sort_keys=True) + "\n")
    # 过滤后的 evalset：供判分器按原生 n 统计（判分器本身不改）
    fs = os.path.join(od, f"{args.layer}-subset-evalset.jsonl")
    with open(fs, "w", encoding="utf-8") as f:
        for q in qs:
            f.write(json.dumps(q, ensure_ascii=False, sort_keys=True) + "\n")

    stats = {"schema": "agimem-mem0-run/1", "layer": args.layer,
             "system": "mem0 + chroma + 本地 bge-m3 ONNX（quantized / CLS / L2 / 512）",
             "arm": {"infer": False, "top_k": args.top_k, "user_id": user, "store": store},
             "nodes": len(nodes), "questions_run": len(qs),
             "types_run": sorted(spec["types"]), "types_skipped": spec["skipped"],
             "p3_deleted": deleted, "p3_delete_errors": del_err,
             "per_query": diag}
    json.dump(stats, open(os.path.join(od, f"{args.layer}-mem0-run-stats.json"), "w",
                          encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[{args.layer}] out → {od}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

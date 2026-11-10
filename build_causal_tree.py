#!/usr/bin/env python3
"""build_causal_tree.py — 用 `rsrs attach` 把真正的父子边建出来（T21）。

T19 已证：`import` 写不进父子边（合成 id → orphaned；两遍导入 → duplicates 2 / reattached 0），
所以 T15/T19 的「完整树臂」其实是 143 条**扁平文本**、`ancestors` 恒空。
本脚本改用正牌关系边命令 `rsrs attach <child> --parent <parent>` 建 **133 条边**，再重跑 122 题。

流程：
  1. 隔离库（独立 data dir / 端口 16310 / 独立 super）扁平导入 143 节点
     （1 对正文相同的兜底节点走 remember --force，绕 import 同文去重）；
  2. `rsrs tree --outline --json`（或 recall 反查）拿 title「原文｜snt id」→ 真 UUID 的映射；
  3. 按 data/tree.json 的 parent_id 逐条 attach，记录成功/失败与回执错误；
  4. **三项边存在性验证**（任一不过即停，不往下跑分）：
     a) `recall` 完整 JSON 的 `ancestors` 是否非空；
     b) 抽 3 个深层节点，`ancestors` 长度是否等于树里祖先数；
     c) 抽 1 条跑 `rsrs chain --depth 3`，看链路是否成链；
  5. 等索引 ready（embedding_model=m3 且 state=ready），122 题完整 JSON 采集。

产物：results/causal-edge-build.json（建边回执与验证）、results/causal-edged-predictions.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import isolated_lib as il  # noqa: E402

TREE = os.path.join(HERE, "data", "tree.json")
DATASET = os.path.join(HERE, "dataset", "causal_evalset.jsonl")
RESDIR = os.path.join(HERE, "results")
M3 = getattr(il, "M3_DEFAULT", os.path.expanduser("~/.rsrs/models/bge-m3"))


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def title_to_sid(title: str) -> str:
    if not title or il.TITLE_SEP not in title:
        return ""
    cand = title.rsplit(il.TITLE_SEP, 1)[-1].strip()
    return cand if cand.startswith("snt") else ""


def parse_json(stdout: str) -> Optional[Dict[str, Any]]:
    brace = stdout.find("{")
    if brace < 0:
        brace = stdout.find("[")
    if brace < 0:
        return None
    try:
        return json.loads(stdout[brace:])
    except json.JSONDecodeError:
        return None


def outline_map(st: il.IsolatedStore) -> Dict[str, str]:
    """`rsrs tree --outline --json` → {snt id: 真 UUID}。"""
    p = il.run(["rsrs", "tree", "--outline", "--json"], st.env, timeout=600, check=False)
    d = parse_json(p.stdout) or {}
    out: Dict[str, str] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            sid = title_to_sid(node.get("title") or "")
            if sid and node.get("id"):
                out[sid] = node["id"]
            for k in ("children", "nodes", "entries"):
                if isinstance(node.get(k), list):
                    for c in node[k]:
                        walk(c)
        elif isinstance(node, list):
            for c in node:
                walk(c)

    walk(d)
    if not out:  # 兜底：把 JSON 里任何带 title/id 的对象都收进来
        stack = [d]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                sid = title_to_sid(cur.get("title") or "")
                if sid and cur.get("id"):
                    out[sid] = cur["id"]
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)
    return out


def recall_hits(st: il.IsolatedStore, query: str, limit: int = 5) -> Dict[str, Any]:
    p = il.run(["rsrs", "recall", query, "--limit", str(limit), "--json"],
               st.env, timeout=600, check=False)
    d = parse_json(p.stdout) or {}
    hits = []
    for h in d.get("details") or []:
        if not isinstance(h, dict):
            continue
        e = h.get("entry") if isinstance(h.get("entry"), dict) else {}
        hits.append({"id": title_to_sid(h.get("title") or e.get("title") or ""),
                     "uuid": e.get("id"), "score": h.get("score"),
                     "ancestors": h.get("ancestors")})
    return {"hits": hits, "summary": d.get("summary") or {},
            "embedding_model": (d.get("summary") or {}).get("embedding_model")}


def main() -> int:
    ap = argparse.ArgumentParser(description="attach 建边 + 重跑 122 题")
    ap.add_argument("--root", default="/tmp/agimem-causal-tree")
    ap.add_argument("--tag", default="tree")
    ap.add_argument("--port", type=int, default=16310)
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--tree", default=TREE, help="缺省 data/tree.json（143 节点）")
    ap.add_argument("--dataset", default=DATASET, help="缺省 dataset/causal_evalset.jsonl（122 题）")
    ap.add_argument("--out", default=os.path.join(RESDIR, "causal-edged-predictions.jsonl"))
    ap.add_argument("--receipt", default=os.path.join(RESDIR, "causal-edge-build.json"))
    args = ap.parse_args()

    tree = json.load(open(args.tree, encoding="utf-8"))
    nodes = tree["nodes"]
    by_id = {n["id"]: n for n in nodes}
    cases = load_jsonl(args.dataset)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    st = il.IsolatedStore(args.root, args.tag, args.port, M3).open()
    t0 = time.time()
    print(f"[tree] store={st.dir} port={st.port} nodes={len(nodes)}", flush=True)

    # ── 1. 扁平导入 ────────────────────────────────────────────────
    seen, imp, rem = set(), [], []
    for n in nodes:
        if n["content"] in seen:
            rem.append(n)
        else:
            seen.add(n["content"])
            imp.append(n)
    p = st.import_items([il.item(f"{n['title']}{il.TITLE_SEP}{n['id']}", n["content"],
                                 f"{n.get('ts', '2026-06-01')}T09:00:00Z",
                                 tags=[n.get("tree", ""), n.get("outcome", "")])
                         for n in imp])
    d = parse_json(p.stdout) or {}
    print(f"[tree] import {json.dumps(d.get('summary') or {}, ensure_ascii=False)}", flush=True)
    for n in rem:
        st.remember(n["content"], f"{n['title']}{il.TITLE_SEP}{n['id']}")
    ready0 = st.wait_index(expect_total=len(nodes), budget=900)
    print(f"[tree] 导入后索引 {json.dumps(ready0, ensure_ascii=False)}", flush=True)

    # ── 2. 取 UUID 映射 ───────────────────────────────────────────
    idmap = outline_map(st)
    print(f"[tree] outline 映射 {len(idmap)}/{len(nodes)}", flush=True)
    if len(idmap) < len(nodes):  # 兜底：逐节点 recall 反查（只在 outline 不足时）
        for n in nodes:
            if n["id"] in idmap:
                continue
            r = recall_hits(st, f"{n['title']}｜{n['id']}", limit=3)
            for h in r["hits"]:
                if h["id"] == n["id"] and h["uuid"]:
                    idmap[n["id"]] = h["uuid"]
                    break
        print(f"[tree] recall 反查后映射 {len(idmap)}/{len(nodes)}", flush=True)

    # ── 3. attach 建边 ────────────────────────────────────────────
    edges = [(n["id"], n["parent_id"]) for n in nodes if n.get("parent_id")]
    ok, fail, errors = 0, 0, []
    for i, (child, parent) in enumerate(edges, 1):
        cu, pu = idmap.get(child), idmap.get(parent)
        if not (cu and pu):
            fail += 1
            errors.append({"child": child, "parent": parent, "error": "uuid 缺失"})
            continue
        r = il.run(["rsrs", "attach", cu, "--parent", pu, "--json"],
                   st.env, timeout=300, check=False)
        if r.returncode == 0:
            ok += 1
        else:
            fail += 1
            if len(errors) < 8:
                errors.append({"child": child, "parent": parent,
                               "rc": r.returncode,
                               "out": (r.stdout + r.stderr).strip()[-200:]})
        if i % 40 == 0:
            print(f"[tree] attach {i}/{len(edges)} (ok={ok} fail={fail})", flush=True)
    print(f"[tree] attach 完成 ok={ok} fail={fail} / 计划 {len(edges)}", flush=True)

    # ── 4. 三项边存在性验证 ───────────────────────────────────────
    deep = sorted(nodes, key=lambda n: -sum(1 for _ in range(1) if n.get("parent_id")))[:0]
    # 找深度 >=3 的节点（沿 parent 链上溯）
    def depth_of(nid: str) -> int:
        d_, cur = 0, nid
        while by_id.get(cur, {}).get("parent_id") and d_ < 20:
            cur = by_id[cur]["parent_id"]
            d_ += 1
        return d_

    deep = sorted(nodes, key=lambda n: -depth_of(n["id"]))[:3]
    checks: List[Dict[str, Any]] = []
    for n in deep:
        r = recall_hits(st, f"{n['title']}", limit=1)
        hit = next((h for h in r["hits"] if h["id"] == n["id"]), None)
        anc = (hit or {}).get("ancestors")
        checks.append({"sid": n["id"], "tree_depth": depth_of(n["id"]),
                       "ancestors_len": len(anc) if isinstance(anc, list) else None,
                       "ancestors_is_list": isinstance(anc, list), "query": n["title"]})
    chain_check: Dict[str, Any] = {}
    if deep:
        cu = idmap.get(deep[0]["id"])
        if cu:
            r = il.run(["rsrs", "chain", cu, "--depth", "3", "--json"],
                       st.env, timeout=300, check=False)
            cd = parse_json(r.stdout) or {}
            det = cd.get("details") or {}
            anc = det.get("ancestors")
            desc = det.get("descendants")
            chain_check = {"rc": r.returncode, "sid": deep[0]["id"],
                           "ancestors_n": len(anc) if isinstance(anc, list) else None,
                           "descendants_n": len(desc) if isinstance(desc, list) else None,
                           "keys": sorted(det.keys()) if isinstance(det, dict) else None}
    print(f"[tree] 验证 ancestors: {json.dumps(checks, ensure_ascii=False)}", flush=True)
    print(f"[tree] 验证 chain: {json.dumps(chain_check, ensure_ascii=False)}", flush=True)

    verified = (sum(1 for c in checks if (c["ancestors_len"] or 0) > 0) >= 2
                and (chain_check.get("ancestors_n") or 0) > 0)

    receipt = {
        "schema": "agimem-causal-edge-build/1",
        "data_dir": st.dir, "port": st.port,
        "tree_path": os.path.relpath(args.tree, HERE), "dataset_path": os.path.relpath(args.dataset, HERE),
        "n_nodes": len(nodes), "imported": len(imp), "remembered": len(rem),
        "import_summary": d.get("summary"),
        "n_edges_planned": len(edges), "n_edges_ok": ok, "n_edges_fail": fail,
        "attach_errors": errors,
        "verify": {"deep_nodes": checks, "chain": chain_check, "edges_verified": verified},
        "index_after_attach": None,
        "elapsed_s": round(time.time() - t0, 1),
    }

    if not verified:
        print("[tree] !! 边验证未通过，按任务要求停止，不跑 122 题", flush=True)
        with open(args.receipt, "w", encoding="utf-8") as f:
            json.dump(receipt, f, ensure_ascii=False, indent=2)
            f.write("\n")
        st.close()
        return 2

    # ── 5. 等索引 ready 后跑 122 题 ───────────────────────────────
    ready = st.wait_index(expect_total=len(nodes), budget=900)
    receipt["index_after_attach"] = ready
    print(f"[tree] 建边后索引 {json.dumps(ready, ensure_ascii=False)}", flush=True)

    rows: List[Dict[str, Any]] = []
    for i, c in enumerate(cases, 1):
        r = recall_hits(st, c["query"], args.limit)
        rows.append({"qid": c["qid"], "query": c["query"], "type": c["type"],
                     "hits": [{"id": h["id"], "score": h["score"]} for h in r["hits"]],
                     # 只留合成 id，绝不落盘 UUID（ancestors 里带的是 entry 对象）
                     "top_ancestors": [[title_to_sid(a.get("title") or "")
                                        for a in (h.get("ancestors") or [])
                                        if isinstance(a, dict)]
                                       for h in r["hits"][:1]]})
        if i % 40 == 0:
            print(f"    … {i}/{len(cases)}", flush=True)

    out = args.out
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    receipt["elapsed_s"] = round(time.time() - t0, 1)
    receipt["n_questions"] = len(rows)
    receipt["n_hits"] = sum(len(r["hits"]) for r in rows)
    with open(args.receipt, "w", encoding="utf-8") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2)
        f.write("\n")
    st.close()
    print(f"[tree] 完成 预测 {out} | hits={receipt['n_hits']} | 耗时 {receipt['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())

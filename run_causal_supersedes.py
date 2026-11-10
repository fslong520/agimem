#!/usr/bin/env python3
"""run_causal_supersedes.py — 用 `remember --supersedes` **真写取代边**，重跑 H2 的 10 道取代题。

背景（T18/T22 更正）：`import` 构造条目时把 `supersedes`/`superseded_by` 硬编码为空
（app-core/service.rs:1739-1740），所以生成器种的 oracle 边**从来没进过库**；此前
「`superseded_by` 键在值恒空 ⇒ 接口缺口」的结论**作废**。唯一正牌写入入口是
`rsrs remember --importance important --supersedes <旧id>`（main.rs:8380-8381，且必须配 important，
main.rs:7972）。

本脚本（端口 16320，独立 data dir / super）：
  1. 扁平导入「除 10 个取代新结论之外」的节点（新结论要留到第 3 步用 --supersedes 写）；
  2. `tree --outline` 拿旧条目的真 UUID；
  3. 逐对 `remember <新结论> --importance important --supersedes <旧UUID>`，记录成功/失败与回执；
  4. 验证：`recall` 完整 JSON 里旧条目的 `superseded_by` 是否非空、`show` 是否带 supersedes/superseded_by；
  5. 等索引 ready，跑 122 题（完整 JSON）→ predictions。
  另做 **链式取代 A→B→C** 专项（另一个小库，端口 16322）：验证标记是否逐跳正确、检索优先给 C。

产物：results/causal-supersession-real-predictions.jsonl、results/causal-supersession-real-build.json、
      results/causal-supersede-chain.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import isolated_lib as il  # noqa: E402

TREE = os.path.join(HERE, "data", "tree.json")
DATASET = os.path.join(HERE, "dataset", "causal_evalset.jsonl")
RESDIR = os.path.join(HERE, "results")
M3 = getattr(il, "M3_DEFAULT", os.path.expanduser("~/.rsrs/models/bge-m3"))
SEP = il.TITLE_SEP


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def sid_of(title: str) -> str:
    if not title or SEP not in title:
        return ""
    cand = title.rsplit(SEP, 1)[-1].strip()
    return cand if cand.startswith("snt") else ""


def parse(stdout: str) -> Optional[Dict[str, Any]]:
    i = stdout.find("{")
    return json.loads(stdout[i:]) if i >= 0 else None


def uuid_map(st: il.IsolatedStore) -> Dict[str, str]:
    p = il.run(["rsrs", "tree", "--outline", "--json"], st.env, timeout=600, check=False)
    d = parse(p.stdout) or {}
    out: Dict[str, str] = {}
    stack = [d]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            sid = sid_of(cur.get("title") or "")
            if sid and cur.get("id"):
                out[sid] = cur["id"]
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return out


def recall_full(st: il.IsolatedStore, q: str, limit: int = 5,
                inv: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    p = il.run(["rsrs", "recall", q, "--limit", str(limit), "--json"], st.env,
               timeout=600, check=False)
    d = parse(p.stdout) or {}
    hits = []
    for h in d.get("details") or []:
        if not isinstance(h, dict):
            continue
        e = h.get("entry") if isinstance(h.get("entry"), dict) else {}
        sup_raw = h.get("superseded_by") or e.get("superseded_by")
        hits.append({"title": (h.get("title") or e.get("title") or ""),
                     "id": sid_of(h.get("title") or e.get("title") or ""),
                     "score": h.get("score"),
                     # superseded_by 是旧条目的 UUID → 逆映射回合成 id；映射不到就只记 True
                     "superseded_by": ((inv or {}).get(sup_raw) or ("mapped?" if sup_raw else None)),
                     "has_supersedes": bool(e.get("supersedes"))})
    return {"hits": hits, "summary": d.get("summary") or {}}


def main() -> int:
    ap = argparse.ArgumentParser(description="H2 取代边真写 + 重跑")
    ap.add_argument("--root", default="/tmp/agimem-supersede")
    ap.add_argument("--tag", default="causal")
    ap.add_argument("--port", type=int, default=16320)
    ap.add_argument("--chain-port", type=int, default=16322)
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--only-chain", action="store_true", help="只跑 A→B→C 链式取代专项")
    ap.add_argument("--tree", default=TREE, help="取代树（缺省旧 data/tree.json）")
    ap.add_argument("--dataset", default=DATASET, help="题集（缺省旧 122 题）")
    ap.add_argument("--pred-out", default="causal-supersession-real-predictions.jsonl",
                    help="预测文件名（results/ 下），v2 用 causal-supersession-v2-predictions.jsonl")
    ap.add_argument("--build-out", default="causal-supersession-real-build.json",
                    help="回执文件名（results/ 下），v2 用 causal-supersession-v2-build.json")
    ap.add_argument("--sup-only", action="store_true",
                    help="只跑取代题（v2 复测用；不跑全量题集、不跑 chain 专项）")
    args = ap.parse_args()

    if args.only_chain:
        chain = run_chain(args.root + "-chain", "chain", args.chain_port, M3)
        with open(os.path.join(RESDIR, "causal-supersede-chain.json"), "w", encoding="utf-8") as f:
            json.dump(chain, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"[chain] {json.dumps(chain['marks'], ensure_ascii=False)}")
        return 0

    raw = json.load(open(args.tree, encoding="utf-8"))
    nodes = raw["nodes"]
    by_id = {n["id"]: n for n in nodes}
    cases = load_jsonl(args.dataset)
    sup_q = [c for c in cases if c["type"] == "supersession"]
    pairs: List[Tuple[str, str]] = [(c["gold_expr"]["node"], c["expect"][0]) for c in sup_q]
    new_ids = {new for _, new in pairs}
    print(f"[sup] 取代对 {len(pairs)} 个，新结论节点 {len(new_ids)} 个", flush=True)

    st = il.IsolatedStore(args.root, args.tag, args.port, M3).open()
    t0 = time.time()
    print(f"[sup] store={st.dir} port={st.port}", flush=True)

    # ── 1. 导入「旧结论 + 其它节点」，新结论留到第 3 步 ────────────
    keep = [n for n in nodes if n["id"] not in new_ids]
    seen, imp, rem = set(), [], []
    for n in keep:
        if n["content"] in seen:
            rem.append(n)
        else:
            seen.add(n["content"])
            imp.append(n)
    p = st.import_items([il.item(f"{n['title']}{SEP}{n['id']}", n["content"],
                                 f"{n.get('ts', '2026-06-01')}T09:00:00Z", importance="important",
                                 tags=[n.get("tree", ""), n.get("outcome", "")])
                         for n in imp])
    print(f"[sup] import {json.dumps((parse(p.stdout) or {}).get('summary') or {}, ensure_ascii=False)}",
          flush=True)
    for n in rem:
        st.remember(n["content"], f"{n['title']}{SEP}{n['id']}")
    ready0 = st.wait_index(expect_total=len(keep), budget=900)
    print(f"[sup] 导入后索引 {json.dumps(ready0, ensure_ascii=False)}", flush=True)

    # ── 2. 旧条目 UUID ────────────────────────────────────────────
    umap = uuid_map(st)
    print(f"[sup] outline 映射 {len(umap)} / 旧节点应有 {len(keep)}", flush=True)

    # ── 3. --supersedes 真写 ──────────────────────────────────────
    receipts = []
    ok = fail = 0
    new_uuids: Dict[str, str] = {}
    for old_sid, new_sid in pairs:
        old_uuid = umap.get(old_sid)
        new_node = by_id[new_sid]
        if not old_uuid:
            fail += 1
            receipts.append({"old": old_sid, "new": new_sid, "error": "旧条目 UUID 缺失"})
            continue
        r = il.run(["rsrs", "remember", new_node["content"],
                    "--title", f"{new_node['title']}{SEP}{new_sid}",
                    "--importance", "important", "--supersedes", old_uuid,
                    "--force", "--json"], st.env, timeout=600, check=False)
        d = parse(r.stdout) or {}
        new_uuid = ((d.get("summary") or {}).get("id") or "")
        if r.returncode == 0:
            ok += 1
            if new_uuid:
                new_uuids[new_sid] = new_uuid
            receipts.append({"old": old_sid, "new": new_sid, "rc": 0,
                             "new_uuid_present": bool(new_uuid)})
        else:
            fail += 1
            receipts.append({"old": old_sid, "new": new_sid, "rc": r.returncode,
                             "out": (r.stdout + r.stderr).strip()[-200:]})
    print(f"[sup] --supersedes 写入 ok={ok} fail={fail}", flush=True)

    # ── 3b. 约束验证：--supersedes 配 trivial 应报错 ───────────────
    constraint: Dict[str, Any] = {}
    if pairs:
        probe_old = umap.get(pairs[0][0])
        if probe_old:
            r = il.run(["rsrs", "remember", "约束探针：trivial 配 --supersedes 应被拒",
                        "--title", "约束探针trivial", "--importance", "trivial",
                        "--supersedes", probe_old, "--force", "--json"],
                       st.env, timeout=300, check=False)
            constraint = {"rc": r.returncode,
                          "out": (r.stdout + r.stderr).strip()[-240:]}
    print(f"[sup] 约束探针 {json.dumps(constraint, ensure_ascii=False)[:200]}", flush=True)

    # ── 4. 验证：旧条目的 superseded_by 是否非空 ──────────────────
    inv = {u: k for k, u in {**umap, **new_uuids}.items()}
    verify = []
    for c in sup_q[:3]:
        old_sid = c["gold_expr"]["node"]
        old_node = by_id[old_sid]
        r = recall_full(st, old_node["title"], limit=3, inv=inv)
        hit = next((h for h in r["hits"] if h["id"] == old_sid), None)
        verify.append({"old": old_sid,
                       "superseded_by_present": bool(hit and hit.get("superseded_by")),
                       "superseded_by_sid": (hit or {}).get("superseded_by"),
                       "top_ids": [h["id"] for h in r["hits"]]})
    print(f"[sup] 验证 {json.dumps(verify, ensure_ascii=False)[:400]}", flush=True)

    # ── 5. 跑题（缺省全量；--sup-only 只跑取代题）─────────────────
    ready = st.wait_index(expect_total=len(nodes), budget=900)
    run_cases = [c for c in cases if c["type"] == "supersession"] if args.sup_only else cases
    rows = []
    for i, c in enumerate(run_cases, 1):
        r = recall_full(st, c["query"], args.limit, inv=inv)
        rows.append({"qid": c["qid"], "query": c["query"], "type": c["type"],
                     "hits": [{"id": h["id"], "score": h["score"],
                               "superseded_by": h.get("superseded_by")} for h in r["hits"]]})
        if i % 40 == 0:
            print(f"    … {i}/{len(run_cases)}", flush=True)
    out = os.path.join(RESDIR, args.pred_out)
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    receipt = {
        "schema": "agimem-causal-supersession-real/1",
        "data_dir": st.dir, "port": st.port,
        "n_pairs": len(pairs), "n_written_ok": ok, "n_written_fail": fail,
        "receipts": receipts, "verify": verify,
        "constraint_trivial_supersedes": constraint,
        "index_after": ready, "n_hits": sum(len(r["hits"]) for r in rows),
        "predictions": out, "elapsed_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(RESDIR, args.build_out), "w",
              encoding="utf-8") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2)
        f.write("\n")
    st.close()

    # ── 6. 链式取代 A→B→C（--sup-only 跳过）──────────────────────
    chain: Dict[str, Any] = {}
    if not args.sup_only:
        chain = run_chain(args.root + "-chain", "chain", args.chain_port, M3)
        with open(os.path.join(RESDIR, "causal-supersede-chain.json"), "w", encoding="utf-8") as f:
            json.dump(chain, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"[chain] {json.dumps({k: chain[k] for k in ('ok', 'marks')}, ensure_ascii=False)[:400]}",
              flush=True)
    print(f"[sup] 完成 predictions={out} elapsed={receipt['elapsed_s']}s")
    return 0


def run_chain(root: str, tag: str, port: int, m3: str) -> Dict[str, Any]:
    """A→B→C 链式取代：B supersedes A，C supersedes B。看标记是否逐跳正确、谁排第 1。"""
    body_a = "发布窗口按 15 分钟执行。"
    body_b = "发布窗口按 30 分钟执行。"
    body_c = "发布窗口按 45 分钟执行。"
    st = il.IsolatedStore(root, tag, port, m3).open()
    out: Dict[str, Any] = {"ok": False, "marks": {}, "ranks": {}, "steps": []}

    def remember(content: str, title: str, supersedes: Optional[str] = None):
        cmd = ["rsrs", "remember", content, "--title", title,
               "--importance", "important", "--force", "--json"]
        if supersedes:
            cmd[-1:-1] = ["--supersedes", supersedes]
        r = il.run(cmd, st.env, timeout=600, check=False)
        d = parse(r.stdout) or {}
        # 只返回 rc / id / 是否报错，**不回传原始 stdout**（里面有 supersedes UUID）
        return r.returncode, ((d.get("summary") or {}).get("id") or ""), \
            ("ok" if r.returncode == 0 else "fail")

    rc_a, uuid_a, _ = remember(body_a, "链式取代探针A")
    rc_b, uuid_b, out_b = remember(body_b, "链式取代探针B", uuid_a or None)
    rc_c, uuid_c, out_c = remember(body_c, "链式取代探针C", uuid_b or None)
    out["steps"] = [{"label": "A", "rc": rc_a, "uuid_present": bool(uuid_a)},
                    {"label": "B(supersedes A)", "rc": rc_b, "uuid_present": bool(uuid_b),
                     "out": out_b},
                    {"label": "C(supersedes B)", "rc": rc_c, "uuid_present": bool(uuid_c),
                     "out": out_c}]
    st.wait_index(expect_total=3, budget=600)

    inv = {u: lab for lab, u in (("A", uuid_a), ("B", uuid_b), ("C", uuid_c)) if u}
    r = recall_full(st, "发布窗口 按多久执行？", limit=5, inv=inv)
    out["ranks"] = [{"title": h.get("title"), "superseded_by": h.get("superseded_by"),
                     "has_supersedes": h.get("has_supersedes")} for h in r["hits"]]
    out["top1_body"] = ("C" if r["hits"] and "45" in (r["hits"][0].get("id") or "") else
                        ("unknown"))
    # 用内容判先后（标题不带内容，靠 show 读内容核对标记）
    lab = {u: k for k, u in (("A", uuid_a), ("B", uuid_b), ("C", uuid_c)) if u}
    shows = {}
    for label, uuid in (("A", uuid_a), ("B", uuid_b), ("C", uuid_c)):
        if not uuid:
            continue
        p = il.run(["rsrs", "show", uuid, "--json"], st.env, timeout=300, check=False)
        d = parse(p.stdout) or {}
        e = (d.get("details") or {}).get("entry") or {}
        # 只落标签 A/B/C，不落 UUID
        shows[label] = {"supersedes_to": lab.get(e.get("supersedes") or ""),
                        "superseded_by": lab.get(e.get("superseded_by") or ""),
                        "content": (e.get("content") or "")[:24]}
    out["shows"] = shows
    out["marks"] = {k: {"supersedes_present": bool(v.get("supersedes_to")),
                        "superseded_by_present": bool(v.get("superseded_by"))}
                    for k, v in shows.items()}
    out["top1_label"] = (r["hits"][0]["title"] if r["hits"] else None)
    out["ok"] = (bool(shows.get("B", {}).get("superseded_by"))
                 and bool(shows.get("A", {}).get("superseded_by"))
                 and shows.get("C", {}).get("superseded_by") is None)
    st.close()
    return out


if __name__ == "__main__":
    sys.exit(main())

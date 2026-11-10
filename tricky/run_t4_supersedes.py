#!/usr/bin/env python3
"""run_t4_supersedes.py — H4-T4「旧结论失效」用 `remember --supersedes` 真写取代边后重测。

原 T4 结论（T9/T11）：hit@1 0.045、hit@5 1.000，并把低分归因为「`--titles` 载荷不下发
`superseded_by`、接口缺口」。T18/T22 更正：那条边**从来没被写进库**——`import` 会把
`supersedes`/`superseded_by` 硬编码成空串（app-core/service.rs:1739-1740）。所以旧结论作废，
必须用 `remember --importance important --supersedes <旧id>` 真写边，再测一次。

做法（端口 16321，独立 data dir / super）：
  1. 导入除 22 个「新结论」之外的 726 节点（新结论留到第 3 步）；
  2. `tree --outline` 取旧结论（`trk…`）的真 UUID；
  3. 逐对 `remember <新结论> --importance important --supersedes <旧UUID> --force`；
  4. 验证：recall 旧结论时 `superseded_by` 是否非空；
  5. 跑 22 道 T4 题（完整 JSON）→ hit@1 / hit@5（gold = 新结论 id）。

产物：tricky/results/t4-supersedes-predictions.jsonl、tricky/results/tricky-t4-supersedes.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
AGIMEM = os.path.dirname(HERE)
sys.path.insert(0, AGIMEM)

import isolated_lib as il  # noqa: E402

SEP = il.TITLE_SEP
TREE = os.path.join(HERE, "data", "tricky_tree.json")
DATASET = os.path.join(HERE, "dataset", "tricky_evalset.jsonl")
RESDIR = os.path.join(HERE, "results")
M3 = getattr(il, "M3_DEFAULT", os.path.expanduser("~/.rsrs/models/bge-m3"))


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def tid_of(title: str) -> str:
    if not title or SEP not in title:
        return ""
    cand = title.rsplit(SEP, 1)[-1].strip()
    return cand if cand.startswith("trk") else ""


def parse(stdout: str) -> Optional[Dict[str, Any]]:
    i = stdout.find("{")
    return json.loads(stdout[i:]) if i >= 0 else None


def uuid_map(st: il.IsolatedStore) -> Dict[str, str]:
    p = il.run(["rsrs", "tree", "--outline", "--json"], st.env, timeout=900, check=False)
    d = parse(p.stdout) or {}
    out: Dict[str, str] = {}
    stack = [d]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            sid = tid_of(cur.get("title") or "")
            if sid and cur.get("id"):
                out[sid] = cur["id"]
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return out


def recall_full(st: il.IsolatedStore, q: str, limit: int = 5) -> Dict[str, Any]:
    p = il.run(["rsrs", "recall", q, "--limit", str(limit), "--json"], st.env,
               timeout=600, check=False)
    d = parse(p.stdout) or {}
    hits = []
    for h in d.get("details") or []:
        if not isinstance(h, dict):
            continue
        e = h.get("entry") if isinstance(h.get("entry"), dict) else {}
        hits.append({"id": tid_of(h.get("title") or e.get("title") or ""),
                     "score": h.get("score"),
                     "superseded_by_title": (h.get("superseded_by") or None)})
    return {"hits": hits}


def main() -> int:
    ap = argparse.ArgumentParser(description="H4-T4 取代边真写后重测")
    ap.add_argument("--root", default="/tmp/agimem-tricky-supersede")
    ap.add_argument("--tag", default="t4")
    ap.add_argument("--port", type=int, default=16321)
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()

    raw = json.load(open(TREE, encoding="utf-8"))
    nodes = raw["nodes"]
    by_id = {n["id"]: n for n in nodes}
    qs = [q for q in load_jsonl(DATASET) if q["type"] == "T4"]
    pairs: List[Tuple[str, str]] = [(q["gold_expr"]["old"], q["expect"][0]) for q in qs]
    new_ids = {new for _, new in pairs}
    print(f"[t4] 题 {len(qs)} / 取代对 {len(pairs)} / 新结论节点 {len(new_ids)}", flush=True)

    st = il.IsolatedStore(args.root, args.tag, args.port, M3).open()
    t0 = time.time()
    print(f"[t4] store={st.dir} port={st.port} nodes={len(nodes)}", flush=True)

    keep = [n for n in nodes if n["id"] not in new_ids]
    seen, imp, rem = set(), [], []
    for n in keep:
        if n["content"] in seen:
            rem.append(n)
        else:
            seen.add(n["content"])
            imp.append(n)
    # tricky 树有 239 组正文完全相同（同模板不同实例）→ import 会按正文去重吞条，
    # 正文尾部附唯一标记（与 T11 同一做法），标题仍用「原文｜trk id」反解。
    def body(n: Dict[str, Any]) -> str:
        return f"{n['content']}（条目 {n['id']}）"

    p = st.import_items([il.item(f"{n['title']}{SEP}{n['id']}", body(n),
                                 "2026-06-01T09:00:00Z", importance="important",
                                 tags=[n.get("scenario", "")])
                         for n in imp])
    print(f"[t4] import {json.dumps((parse(p.stdout) or {}).get('summary') or {}, ensure_ascii=False)}",
          flush=True)
    for n in rem:
        st.remember(body(n), f"{n['title']}{SEP}{n['id']}")
    ready0 = st.wait_index(expect_total=len(keep), budget=1800)
    print(f"[t4] 导入后索引 {json.dumps(ready0, ensure_ascii=False)}", flush=True)

    umap = uuid_map(st)
    print(f"[t4] outline 映射 {len(umap)} / 期望 {len(keep)}", flush=True)

    receipts, ok, fail = [], 0, 0
    for old_sid, new_sid in pairs:
        old_uuid = umap.get(old_sid)
        n = by_id[new_sid]
        if not old_uuid:
            fail += 1
            receipts.append({"old": old_sid, "new": new_sid, "error": "旧条目 UUID 缺失"})
            continue
        r = il.run(["rsrs", "remember", body(n),
                    "--title", f"{n['title']}{SEP}{new_sid}",
                    "--importance", "important", "--supersedes", old_uuid,
                    "--force", "--json"], st.env, timeout=600, check=False)
        if r.returncode == 0:
            ok += 1
            receipts.append({"old": old_sid, "new": new_sid, "rc": 0})
        else:
            fail += 1
            receipts.append({"old": old_sid, "new": new_sid, "rc": r.returncode,
                             "out": (r.stdout + r.stderr).strip()[-160:]})
    print(f"[t4] --supersedes 写入 ok={ok} fail={fail}", flush=True)

    ready = st.wait_index(expect_total=len(nodes), budget=1800)
    verify = []
    for old_sid, new_sid in pairs[:3]:
        r = recall_full(st, by_id[old_sid]["title"], limit=5)
        hit = next((h for h in r["hits"] if h["id"] == old_sid), None)
        verify.append({"old": old_sid, "superseded_by_present": bool(hit and hit.get("superseded_by_title"))})
    print(f"[t4] 验证 {json.dumps(verify, ensure_ascii=False)}", flush=True)

    pair_of = {q["qid"]: (q["gold_expr"]["old"], q["expect"][0]) for q in qs}
    rows, hit1, hit5 = [], 0, 0
    for q in qs:
        r = recall_full(st, q["query"], args.limit)
        ids = [h["id"] for h in r["hits"]]
        gold = q["expect"][0]
        rank = ids.index(gold) if gold in ids else None
        rows.append({"qid": q["qid"], "query": q["query"], "type": q["type"],
                     "hits": [{"id": h["id"], "score": h["score"],
                               # superseded_by 是 UUID → 只保留「该题的旧→新」这一事实，不落 UUID
                               "superseded_by": (pair_of[q["qid"]][1]
                                                 if h.get("superseded_by_title")
                                                 and h["id"] == pair_of[q["qid"]][0] else None)}
                              for h in r["hits"]],
                     "gold": gold, "gold_rank": rank})
        hit1 += 1 if rank == 0 else 0
        hit5 += 1 if (rank is not None and rank < 5) else 0

    pred = os.path.join(RESDIR, "t4-supersedes-predictions.jsonl")
    with open(pred, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    doc = {
        "schema": "agimem-tricky-t4-supersedes/1",
        "arm": "T4 with real --supersedes edges",
        "data_dir": st.dir, "port": st.port,
        "n_questions": len(rows), "n_pairs": len(pairs),
        "n_written_ok": ok, "n_written_fail": fail,
        "receipts": receipts, "verify": verify,
        "index_after": ready,
        "hit_at_1": hit1 / len(rows) if rows else None,
        "hit_at_5": hit5 / len(rows) if rows else None,
        "hit_at_1_k": hit1, "hit_at_5_k": hit5,
        "prior_arm": {"name": "T11 隔离库（无边，import 丢字段）", "hit_at_1": 0.045,
                      "hit_at_5": 1.000, "source": "tests/34 §9"},
        "predictions": pred,
        "elapsed_s": round(time.time() - t0, 1),
    }
    out = os.path.join(RESDIR, "tricky-t4-supersedes.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    st.close()
    print(f"[t4] hit@1={doc['hit_at_1']:.3f} hit@5={doc['hit_at_5']:.3f} "
          f"（旧臂 0.045 / 1.000）→ {out} elapsed={doc['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())

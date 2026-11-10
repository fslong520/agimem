#!/usr/bin/env python3
"""probe_h3_v2.py — H3 v2 机制探针（最小步取证，3 对条目，零 LLM）。

验三件事（决定 v2 度量是否成立）：
  P1 `import`（显式 created_at=2025-03-01）＋ `remember --force`（created_at=now）
     能否让**正文逐字节相同**的两条同时存在于同一隔离库（绕开 import 的同文去重）；
  P2 同文两条的召回分数是否相同/接近，第 1 名由什么决定（时间？插入顺序？id？）；
  P3 把「新写入的是哪条」对调后，第 1 名是否跟着时间走（若跟着走，说明时间生效；
     若跟着插入位置走，说明只是顺序，不是时间）。

产物：/tmp/h3v2-probe/probe.json（不进仓；仓内只留本脚本与结论）。
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import isolated_lib as il  # noqa: E402

ROOT = "/tmp/h3v2-probe"
OUT = os.path.join(ROOT, "probe.json")

BODY = ("夜间发布窗口定在每周三 23:30，避开白天流量高峰；发布前十分钟冻结变更单，"
        "窗口结束十五分钟后解除冻结。")

PAIRS = [
    # (tag, 旧条目 created_at, 查询)
    ("p1", "2025-03-01T09:00:00Z", "夜间发布窗口现在按哪条执行？"),
    ("p2", "2025-03-01T09:00:00Z", "夜间发布窗口"),
    ("p3", "2025-03-01T09:00:00Z", "夜间发布窗口现在执行的约定是哪一版"),
]


def main() -> int:
    os.makedirs(ROOT, exist_ok=True)
    st = il.IsolatedStore(ROOT, "probe", 16220).open()
    print(f"[probe] store {st.dir} port={st.port}", flush=True)

    items = [il.item(f"夜间发布窗口｜old{i}", BODY, ts) for i, (_, ts, _) in enumerate(PAIRS)]
    p = st.import_items(items)
    d = il.parse_env(p.stdout) or {}
    print(f"[probe] import rc={p.returncode} {json.dumps(d.get('summary') or {}, ensure_ascii=False)}",
          flush=True)

    for i, (tag, _ts, _q) in enumerate(PAIRS):
        r = st.remember(BODY, f"夜间发布窗口｜new{i}")
        rd = il.parse_env(r.stdout) or {}
        print(f"[probe] remember new{i} rc={r.returncode} "
              f"{(rd.get('summary') or {}).get('id', '')[:8]}", flush=True)

    ready = st.wait_index(expect_total=len(PAIRS) * 2)
    print(f"[probe] ready {json.dumps(ready, ensure_ascii=False)}", flush=True)

    out = {"body": BODY, "pairs": []}
    for i, (tag, ts, q) in enumerate(PAIRS):
        rr = st.recall(q, 5)
        hits = [{"title": h["title"], "score": h["score"]} for h in rr["hits"]]
        titles = [h["title"] for h in hits]
        rank_old = next((j for j, t in enumerate(titles) if t.endswith(f"old{i}")), None)
        rank_new = next((j for j, t in enumerate(titles) if t.endswith(f"new{i}")), None)
        rec = {"qid": tag, "query": q, "hits": hits,
               "rank_old": rank_old, "rank_new": rank_new,
               "new_first": (rank_new is not None and (rank_old is None or rank_new < rank_old)),
               "tie": (rank_old is not None and rank_new is not None
                       and hits[rank_old]["score"] == hits[rank_new]["score"]),
               "old_created_at": ts, "new_created_at": "now(机械时钟)"}
        out["pairs"].append(rec)
        print(f"[probe] {tag} rank_old={rank_old} rank_new={rank_new} new_first={rec['new_first']} "
              f"tie={rec['tie']} scores={[h['score'] for h in hits]}", flush=True)

    out["summary"] = {
        "local_total": st.status().get("local_total"),
        "n_pairs": len(PAIRS),
        "n_new_first": sum(1 for x in out["pairs"] if x["new_first"]),
        "n_tie": sum(1 for x in out["pairs"] if x["tie"]),
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    st.close()
    print(f"[probe] 写出 {OUT} | {json.dumps(out['summary'], ensure_ascii=False)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

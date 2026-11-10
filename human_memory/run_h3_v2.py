#!/usr/bin/env python3
"""run_h3_v2.py — H3 v2 三臂隔离库实跑：recency / correction / repeat 各自独立库。

- 每臂独立 data dir + 独立 RPC 端口 + 独立 super（隔离库法，见 isolated_lib.py 头注释）；
- 写入路径：`write_via=import` 的条目批写（可指定 created_at=2025-03-01），
  `write_via=remember` 的条目逐条 `remember --force`（created_at=机械时钟=现在）；
  这样「正文逐字节相同」的两条既能共存，又有真实时差（import 会吞同文条目，绕法见 README）；
- 采集：每题 `recall <query> --titles --limit 5`；判分只用自造标题码，隔离库 UUID 不落盘；
- 绝不碰 `~/.rsrs`、不改全局 config、不启停宿主 runtime。

用法：
    python3 run_h3_v2.py [--root /tmp/agimem-h3v2] [--base-port 16221] [--only recency,correction,repeat]
产物：results/h3v2-predictions-<arm>.jsonl、results/h3v2-run-stats.json
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

PLAN = os.path.join(HERE, "data", "h3_v2_plan.json")
RESDIR = os.path.join(os.path.dirname(HERE), "results")
ARMS = ("recency", "correction", "repeat")


def arm_port(base: int, arm: str) -> int:
    return base + ARMS.index(arm)


def run_arm(arm: str, plan: Dict[str, Any], root: str, base_port: int,
            limit: int) -> Dict[str, Any]:
    data = plan["arms"][arm]
    entries, questions = data["entries"], data["questions"]
    st = il.IsolatedStore(root, arm, arm_port(base_port, arm)).open()
    t0 = time.time()
    print(f"[{arm}] store={st.dir} port={st.port} 条目={len(entries)} 题={len(questions)}", flush=True)

    imp = [e for e in entries if e.get("write_via") == "import"]
    rem = [e for e in entries if e.get("write_via") == "remember"]

    if imp:
        p = st.import_items([il.item(e["title"], e["content"], e["created_at"],
                                     tags=[arm, e.get("role", "")]) for e in imp])
        d = il.parse_env(p.stdout) or {}
        print(f"[{arm}] import rc={p.returncode} {json.dumps(d.get('summary') or {}, ensure_ascii=False)}",
              flush=True)
        if p.returncode != 0:
            st.close()
            raise SystemExit(f"{arm}: import 失败")

    for i, e in enumerate(rem, 1):
        r = st.remember(e["content"], e["title"])
        if r.returncode != 0:
            st.close()
            raise SystemExit(f"{arm}: remember {e['title']} 失败")
        if i % 10 == 0:
            print(f"[{arm}] remember {i}/{len(rem)}", flush=True)

    # 就绪判据：state=ready（不再硬要求 local_total 精确相等——import 去重会让条数少于计划，
    # 探针里就因为「期待 6 实际 4」白等到超时）；条数只记录不强卡。
    ready = st.wait_index(expect_total=None, budget=600)
    local_total = ready.get("local_total")
    print(f"[{arm}] index {json.dumps(ready, ensure_ascii=False)} 计划条目={len(entries)}", flush=True)

    rows: List[Dict[str, Any]] = []
    for i, q in enumerate(questions, 1):
        rr = st.recall(q["query"], limit)
        hits = [{"title": h["title"], "score": h["score"]} for h in rr["hits"]]
        rows.append({"qid": q["qid"], "query": q["query"], "arm": arm,
                     "hits": hits, "embedding_model": rr.get("embedding_model")})
        if i % 10 == 0:
            print(f"[{arm}] recall {i}/{len(questions)}", flush=True)

    out = os.path.join(RESDIR, f"h3v2-predictions-{arm}.jsonl")
    os.makedirs(RESDIR, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    st.close()
    stats = {"arm": arm, "data_dir": st.dir, "port": st.port,
             "planned_entries": len(entries), "imported_batch": len(imp),
             "remembered": len(rem), "index": ready, "local_total": local_total,
             "n_questions": len(questions), "predictions": out,
             "elapsed_s": round(time.time() - t0, 1)}
    print(f"[{arm}] 完成 {json.dumps({k: stats[k] for k in ('local_total', 'elapsed_s')}, ensure_ascii=False)}",
          flush=True)
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description="H3 v2 隔离库三臂实跑")
    ap.add_argument("--root", default="/tmp/agimem-h3v2")
    ap.add_argument("--base-port", type=int, default=16221)
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--only", default=",".join(ARMS))
    args = ap.parse_args()

    with open(PLAN, encoding="utf-8") as f:
        plan = json.load(f)

    os.makedirs(RESDIR, exist_ok=True)
    stats: List[Dict[str, Any]] = []
    for arm in [a for a in ARMS if a in args.only.split(",")]:
        stats.append(run_arm(arm, plan, args.root, args.base_port, args.limit))

    out = os.path.join(RESDIR, "h3v2-run-stats.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"schema": "agimem-h3-v2-run/1", "arms": stats,
                   "notes": "隔离库（/tmp 独立目录+独立端口+独立 super）；未触碰 ~/.rsrs；"
                            "标题码自造，UUID 不落盘"}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"[run_h3_v2] 写出 {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

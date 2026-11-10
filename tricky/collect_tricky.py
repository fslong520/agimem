#!/usr/bin/env python3
"""collect_tricky.py — 只读采集：逐题 `rsrs --client-only recall --json --titles --limit K`。

沿用 agimem 主链的采集与脱敏口径（见 ../collect_recall.py）：
真库 id 与标题不落盘，落盘前用 tricky_gold.id_match 对合成树 id（trk…）做前缀双向检查；
占位 id 为 8 位 `e` + 7 位十进制序号，与 `trk…` 首字符不同，等长下不会前缀碰上。
superseded_by 在 --titles 载荷里不存在，写 null，并在 stats 里记字段缺失次数。

用途：证明「合成题不在真库里」这一事实（T5 的 tests/29、30 已确立同口径），
     **不是** Respire 在刁钻场景下的能力分。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

import tricky_gold as tg

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=os.path.join(HERE, "dataset", "tricky_evalset.jsonl"))
    ap.add_argument("--tree", default=os.path.join(HERE, "data", "tricky_tree.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "results", "real-predictions.jsonl"))
    ap.add_argument("--stats", default=os.path.join(HERE, "results", "real-stats.json"))
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()

    tree = tg.load_tree(args.tree)
    tree_ids = list(tree["_by_id"])
    cases = [json.loads(x) for x in open(args.dataset, encoding="utf-8") if x.strip()]

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    rows, per = [], []
    n_hits = n_match = n_sup = n_empty = 0
    scores, seq = [], 0

    for i, c in enumerate(cases, 1):
        cmd = ["rsrs", "--client-only", "recall", c["query"], "--json", "--titles",
               "--limit", str(args.limit)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            sys.stderr.write(f"recall 失败 q={c['qid']} exit={proc.returncode}\n{proc.stderr[:400]}\n")
            return proc.returncode or 1
        raw = proc.stdout
        brace = raw.find("{")
        if brace < 0:
            sys.stderr.write(f"recall 无 JSON q={c['qid']}\n")
            return 1
        env = json.loads(raw[brace:])
        hits, q_scores = [], []
        for h in env.get("details") or []:
            if not isinstance(h, dict):
                continue
            hid = h.get("id") or ""
            if not isinstance(hid, str) or not hid:
                continue
            n_hits += 1
            if any(tg.id_match(hid, nid) for nid in tree_ids):
                n_match += 1
            if "superseded_by" in h:
                n_sup += 1
            sc = h.get("score")
            if isinstance(sc, (int, float)):
                scores.append(float(sc))
                q_scores.append(float(sc))
            seq += 1
            hits.append({"id": f"e{seq:07d}", "score": sc, "superseded_by": None})
        if not hits:
            n_empty += 1
        rows.append({"qid": c["qid"], "query": c["query"], "hits": hits})
        per.append({"qid": c["qid"], "type": c["type"], "n_hits": len(hits),
                    "score_max": max(q_scores) if q_scores else None})
        if i % 22 == 0:
            print(f"  … {i}/{len(cases)}", flush=True)

    with open(args.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    stats = {
        "n_questions": len(cases),
        "limit": args.limit,
        "n_hits": n_hits,
        "n_empty_questions": n_empty,
        "n_id_prefix_match_tree": n_match,
        "n_details_with_superseded_by": n_sup,
        "score_min": min(scores) if scores else None,
        "score_max": max(scores) if scores else None,
        "redaction": "real ids replaced by e+7digits before write; titles dropped",
        "command": "rsrs --client-only recall <query> --json --titles --limit %d" % args.limit,
        "per_question": per,
    }
    with open(args.stats, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({k: stats[k] for k in stats if k != "per_question"}, ensure_ascii=False))
    if n_match:
        sys.stderr.write("警告：有真库 id 与合成树前缀匹配，占位会改变判分，停止采用本文件\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

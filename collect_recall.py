#!/usr/bin/env python3
"""只读采集：逐题 `rsrs --client-only recall --json --titles --limit K`，
写出脱敏 predictions JSONL。

真库 id 与标题不落盘。落盘前用 causal_gold.id_match 对合成树短 id 做前缀双向检查；
占位 id 为 8 位 `e` + 7 位十进制序号，与树内 `snt…` 首字符不同，等长下不会前缀碰上。
`superseded_by` 在 --titles 载荷里不存在，写 null，并在 stats 里记字段缺失次数。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

import causal_gold as cg

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=os.path.join(HERE, "dataset", "causal_evalset.jsonl"))
    ap.add_argument("--tree", default=os.path.join(HERE, "data", "tree.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "results", "firsteval-predictions.jsonl"))
    ap.add_argument("--stats", default=os.path.join(HERE, "results", "firsteval-stats.json"))
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()

    tree = cg.load_tree(args.tree)
    tree_ids = list(tree["_by_id"])
    cases = []
    with open(args.dataset, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            cases.append(json.loads(line))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    rows = []
    n_hits = 0
    n_match = 0
    n_sup_field = 0
    n_empty = 0
    scores = []
    per = []
    seq = 0

    for i, c in enumerate(cases, 1):
        cmd = [
            "rsrs", "--client-only", "recall", c["query"],
            "--json", "--titles", "--limit", str(args.limit),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            sys.stderr.write(f"recall 失败 q={c.get('qid')} exit={proc.returncode}\n")
            sys.stderr.write(proc.stderr[:500] + "\n")
            return proc.returncode or 1
        raw = proc.stdout
        brace = raw.find("{")
        if brace < 0:
            sys.stderr.write(f"recall 无 JSON q={c.get('qid')}\n")
            return 1
        env = json.loads(raw[brace:])
        details = env.get("details") or []
        hits = []
        q_scores = []
        for h in details:
            if not isinstance(h, dict):
                continue
            hid = h.get("id") or ""
            if not isinstance(hid, str) or not hid:
                continue
            n_hits += 1
            if any(cg.id_match(hid, nid) for nid in tree_ids):
                n_match += 1
            if "superseded_by" in h or (
                isinstance(h.get("entry"), dict) and "superseded_by" in h["entry"]
            ):
                n_sup_field += 1
            sc = h.get("score")
            if isinstance(sc, (int, float)):
                scores.append(float(sc))
                q_scores.append(float(sc))
            seq += 1
            # 8 位占位，首字符 e，与 snt 等长且不相等
            placeholder = f"e{seq:07d}"
            hits.append({"id": placeholder, "score": sc, "superseded_by": None})
        if not hits:
            n_empty += 1
        rows.append({"qid": c.get("qid"), "query": c["query"], "hits": hits})
        per.append({"qid": c.get("qid"), "type": c.get("type"), "n_hits": len(hits),
                    "score_max": max(q_scores) if q_scores else None})
        print(f"[{i}/{len(cases)}] {c.get('qid')} hits={len(hits)}", flush=True)

    with open(args.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    stats = {
        "n_questions": len(cases),
        "limit": args.limit,
        "n_hits": n_hits,
        "n_empty_questions": n_empty,
        "n_id_prefix_match_tree": n_match,
        "n_details_with_superseded_by": n_sup_field,
        "score_min": min(scores) if scores else None,
        "score_max": max(scores) if scores else None,
        "per_question": per,
        "redaction": "real ids replaced by e+7digits before write; titles dropped",
        "command": "rsrs --client-only recall <query> --json --titles --limit %d" % args.limit,
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

#!/usr/bin/env python3
"""A 层 · LoCoMo 检索层口径（session-hit）：参数化版。

与 `scripts/locomo/analyze_om.py` 的关系：
- 判据完全一致——evidence `D{n}:k` 的 session 号 n，命中 retrieved 标题里的
  `session {m}` 即算该题检索层命中；分母 = 有 evidence 的题（LoCoMo conv-0 为 197/199）。
- 差别只在**路径参数化**：analyze_om.py 硬编码 `~/locomo-eval/results/...`
  （该目录 2026-11-09 已不存在），本脚本接受 `--results-dir` / `--data`，
  从而可对仓内只读历史结果 `results/locomo/*.json` 复算。
- 不复制 `scripts/locomo/` 任何脚本，也不改写 `results/locomo/*.json`（只读）。

用法：
    python3 session_hit.py \
        --results-dir ../../results/locomo \
        --data ~/locomo-src/data/locomo10.json \
        --files om_conv0_judged.json om_conv0_c5_judged.json \
        --out ../results/locomo-session-hit.json
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys

SESSION_RE = re.compile(r"session (\d+)")
EVIDENCE_RE = re.compile(r"D(\d+):")


def wilson_ci(k: int, n: int, z: float = 1.959963984540054):
    """与 agimem/score.py:wilson_ci 同式（95%）。"""
    if n <= 0:
        return {"point": None, "lo": None, "hi": None, "n": 0, "k": k, "method": "wilson"}
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z2 / (4 * n * n)) ** 0.5) / denom
    return {"point": p, "lo": max(0.0, center - half), "hi": min(1.0, center + half),
            "n": n, "k": k, "method": "wilson", "z": z}


def ev_sessions(row):
    out = set()
    for e in row.get("evidence") or []:
        m = EVIDENCE_RE.match(str(e))
        if m:
            out.add(int(m.group(1)))
    return out


def got_sessions(row):
    """兼容两种 retrieved 形状：标题串（om_ingest 口径）或 {"session": n} 字段。"""
    out = set()
    for m in row.get("retrieved") or []:
        if isinstance(m, dict):
            if isinstance(m.get("session"), int):
                out.add(m["session"])
                continue
            mm = SESSION_RE.search(str(m.get("title", "")))
            if mm:
                out.add(int(mm.group(1)))
        elif isinstance(m, str):
            mm = SESSION_RE.search(m)
            if mm:
                out.add(int(mm.group(1)))
    return out


def analyze(path, topk_strict=3):
    d = json.load(open(path, encoding="utf-8"))
    rows = d.get("rows") or []
    hit, tot = collections.Counter(), collections.Counter()
    strict, hit_by_cat_any = collections.Counter(), collections.Counter()
    n_no_evidence = 0
    for r in rows:
        evs = ev_sessions(r)
        if not evs:
            n_no_evidence += 1
            continue
        cat = r.get("category")
        tot[cat] += 1
        got = got_sessions(r)
        if evs & got:
            hit[cat] += 1
        got3 = set()
        for m in (r.get("retrieved") or [])[:topk_strict]:
            if isinstance(m, dict):
                if isinstance(m.get("session"), int):
                    got3.add(m["session"])
                    continue
                mm = SESSION_RE.search(str(m.get("title", "")))
                if mm:
                    got3.add(int(mm.group(1)))
        if evs & got3:
            strict[cat] += 1
    k_any, n_any = sum(hit.values()), sum(tot.values())
    k_st, n_st = sum(strict.values()), sum(tot.values())
    return {
        "file": os.path.basename(path),
        "n_rows": len(rows),
        "n_no_evidence": n_no_evidence,
        "denominator": n_any,
        "session_hit": wilson_ci(k_any, n_any),
        "session_hit_top3": wilson_ci(k_st, n_st),
        "by_category": {
            str(c): {"session_hit": hit[c] / tot[c] if tot[c] else None,
                     "k": hit[c], "n": tot[c],
                     "session_hit_top3": strict[c] / tot[c] if tot[c] else None}
            for c in sorted(tot)
        },
        "note": "分母=有 evidence 的题；hit_top3 只算前 3 条 retrieved",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--data", default=os.path.expanduser(os.environ.get("LOCOMO10", "~/locomo-src/data/locomo10.json")),
                    help="LoCoMo 源数据（只读引用绝对路径，不复制进仓）")
    ap.add_argument("--files", nargs="+", default=["om_conv0_judged.json", "om_conv0_c5_judged.json"])
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    if not os.path.isdir(args.results_dir):
        print(f"结果目录不存在: {args.results_dir}", file=sys.stderr)
        return 2
    data_ok = os.path.isfile(args.data)
    out = {"results_dir": args.results_dir, "data": args.data,
           "data_present": data_ok, "runs": []}
    print(f"{'file':34s} {'denom':>5s} {'hit@5':>7s} {'top3':>7s}  95%CI(hit@5)")
    for name in args.files:
        p = os.path.join(args.results_dir, name)
        if not os.path.isfile(p):
            print(f"{name:34s} 缺失，跳过")
            continue
        r = analyze(p)
        out["runs"].append(r)
        h, s = r["session_hit"], r["session_hit_top3"]
        ci = f"[{h['lo']:.4f}, {h['hi']:.4f}]" if h["point"] is not None else "n/a"
        print(f"{name:34s} {r['denominator']:5d} {str(round(h['point'], 4)) if h['point'] is not None else 'n/a':>7s} "
              f"{str(round(s['point'], 4)) if s['point'] is not None else 'n/a':>7s}  {ci}")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

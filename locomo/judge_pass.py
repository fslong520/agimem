#!/usr/bin/env python3
"""H1 第二判：只补 judge，不重跑答题与检索（对齐 tests/23 的判次纪律）。

读 `results/locomo-e2e.json` 的 rows（question/gold/pred 已固定），
用**完全相同**的 JUDGE_SYS + judge_prompt 再判一遍，与已有第 1 判合成均值。

用法：
    python3 judge_pass.py [--in results/locomo-e2e.json] [--workers 8]
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
AGIMEM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(os.path.dirname(AGIMEM), "scripts", "locomo"))

import common_llm as cl  # noqa: E402
from run_e2e import chat, mean_ci, DEFAULT_MODEL  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp",
                    default=os.path.join(AGIMEM, "results", "locomo-e2e.json"))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    data = json.load(open(args.inp))
    rows = data["rows"]
    print(f"[judge2] {len(rows)} rows from {args.inp}", flush=True)
    t0 = time.time()

    def grade(r):
        try:
            txt = chat(cl.judge_prompt(r["question"], str(r["gold"]), str(r["pred"])),
                       model=args.model, max_tokens=512)
            s = cl.parse_score(txt)
            raw = txt[:300]
        except Exception as e:  # noqa: BLE001
            s, raw = 0.0, f"__error__ {type(e).__name__}"
        return s, raw

    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        outs = list(ex.map(grade, rows))

    for r, (s, raw) in zip(rows, outs):
        r.setdefault("scores", [])
        r["scores"].append(s)
        r.setdefault("judge_raw", []).append(raw)
        r["score"] = sum(r["scores"]) / len(r["scores"])

    scored = [r for r in rows if not str(r["pred"]).startswith("__error__")]
    cat_names = {1: "multi-hop", 2: "temporal", 3: "open-domain", 4: "single-hop", 5: "adversarial"}
    by_cat = {}
    for c in sorted({r["category"] for r in rows if r["category"] is not None}):
        by_cat[cat_names.get(c, str(c))] = mean_ci([r["score"] for r in scored if r["category"] == c])

    data["overall"] = mean_ci([r["score"] for r in scored])
    data["non_adversarial"] = mean_ci([r["score"] for r in scored if r["category"] != 5])
    data["by_category"] = by_cat
    data["env"]["judges_per_question"] = len(rows[0]["scores"])
    data["judge_pass2_s"] = round(time.time() - t0, 1)
    json.dump(data, open(args.inp, "w"), ensure_ascii=False, indent=1)

    print(f"[judge2] done {time.time()-t0:.0f}s judges={data['env']['judges_per_question']}")
    print(f"[judge2] overall={data['overall']}")
    for k, v in by_cat.items():
        print(f"  {k:12s} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

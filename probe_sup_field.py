#!/usr/bin/env python3
"""probe_sup_field.py — 单点核实：`superseded_by` 能否经 `import` 落库、并由完整 recall JSON 下发。

背景：H2 因果层 supersession 题型的 gold 口径是「用好生成器种入的 superseded_by（oracle）」。
此前 tests/34 已证 `--titles` 载荷不下发该字段；本轮先核实：
  (a) 完整 recall JSON 是否**有**该键；
  (b) 该键是否**有值**（即 import 时把 superseded_by 写进条目后，能否原样回来）。

做法：3 条条目的最小隔离库（独立目录/端口/super）——
  A：旧结论，import 时带 `superseded_by: "sntP0002"`
  B：新结论（正文含「新结论/改为」等证伪信号词）
  C：无关干扰
再 recall 一条问「旧结论现在还成立吗」的完整 JSON，打印每条 detail 的键与 superseded_by 值，
并额外用 `rsrs show` 看条目本体是否保留了该字段。

产物：results/probe-superseded-field.json（只存键名/布尔/计数，不存 UUID）。
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import isolated_lib as il  # noqa: E402

RESDIR = os.path.join(HERE, "results")
M3 = getattr(il, "M3_DEFAULT", os.path.expanduser("~/.rsrs/models/bge-m3"))

ITEMS = [
    il.item("探针旧结论｜sntP0001",
            "【前因】按当时理解把同步窗口定在凌晨三点\n【行为】沿用了这个排程\n【后果】白天的延迟依旧存在",
            "2025-03-01T09:00:00Z"),
    il.item("探针新结论｜sntP0002",
            "【前因】复盘定位到锁竞争\n【行为】新结论：改为分片队列即可，无需扩线程\n【后果】延迟降到秒级",
            "2026-09-01T09:00:00Z"),
    il.item("探针干扰｜sntP0003",
            "【前因】别的系统的记录\n【行为】与本条无关\n【后果】不影响判断",
            "2026-09-02T09:00:00Z"),
]
# 关键：把 superseded_by 写进条目（import 声称 keep fields）
ITEMS[0]["superseded_by"] = "sntP0002"


def main() -> int:
    st = il.IsolatedStore("/tmp/agimem-causal-probe", "supfield", 16310, M3).open()
    p = st.import_items(ITEMS)
    d = il.parse_env(p.stdout) or {}
    print(f"[probe] import rc={p.returncode} {json.dumps(d.get('summary') or {}, ensure_ascii=False)}",
          flush=True)
    ready = st.wait_index(expect_total=len(ITEMS), budget=300)
    print(f"[probe] index {json.dumps(ready, ensure_ascii=False)}", flush=True)

    q = "探针旧结论现在还成立吗？当前有效的是哪条？"
    full = il.run(["rsrs", "recall", q, "--limit", "5", "--json"], st.env, timeout=300, check=False)
    env = il.parse_env(full.stdout) or {}
    details = env.get("details") or []
    rec = {"query": q, "n_details": len(details), "details": []}
    for h in details:
        if not isinstance(h, dict):
            continue
        entry = h.get("entry") if isinstance(h.get("entry"), dict) else {}
        rec["details"].append({
            "title": h.get("title") or entry.get("title"),
            "keys_top": sorted(h.keys()),
            "keys_entry": sorted(entry.keys()),
            "sup_top": h.get("superseded_by", "<absent>"),
            "sup_entry": entry.get("superseded_by", "<absent>"),
            "score": h.get("score"),
        })
    rec["n_with_sup_key"] = sum(1 for x in rec["details"] if "superseded_by" in x["keys_top"])
    rec["n_with_sup_value"] = sum(1 for x in rec["details"]
                                  if isinstance(x["sup_top"], str) and x["sup_top"])
    rec["n_entry_with_sup_value"] = sum(1 for x in rec["details"]
                                        if isinstance(x["sup_entry"], str) and x["sup_entry"])
    st.close()

    os.makedirs(RESDIR, exist_ok=True)
    out = os.path.join(RESDIR, "probe-superseded-field.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2, default=str)
        f.write("\n")
    print(json.dumps({k: rec[k] for k in ("n_details", "n_with_sup_key", "n_with_sup_value",
                                          "n_entry_with_sup_value")}, ensure_ascii=False))
    for x in rec["details"]:
        print(f"    · {x['title']} | sup_top={x['sup_top']!r} sup_entry={x['sup_entry']!r} "
              f"score={x['score']}")
    print(f"[probe] 写出 {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

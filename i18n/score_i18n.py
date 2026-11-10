#!/usr/bin/env python3
"""score_i18n.py — agimem 多语言子层判分（search-only，零 LLM）。

三类指标：
- D1 语言公平性：每语言 hit@k + Wilson 95% CI + 语言间极差。
- D2 跨语言锚定：写入语言 A × 查询语言 B（A≠B）的命中率，逐格 CI；
  另给同语言对照（d2c）与跨语言落差。
- D3 跨语言同一性：四种语言是否都能召回；四语言 top-1 是否指向同一条；
  每条 fact 在库里被当成几件事（重复条目数）。

输入：
  --dataset      gen_i18n.py 产出
  --predictions  采集结果，行形如 {"qid","hits":[{"id","score"}]}
                 （id 已由采集脚本归一：语料条目 → fid，未知 → e+7 位占位）
  --writes       可选，采集脚本写的写入台账 {"fid": {"lang": {"id","action"}}}，
                 仅 D3 的重复条目指标需要

判分口径：hit = gold（fid）出现在 top-k 内；id 精确匹配。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append(json.loads(line))
    return out


def wilson(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def rate(k: int, n: int) -> Dict[str, Any]:
    lo, hi = wilson(k, n)
    return {"n": n, "hits": k, "rate": (k / n if n else 0.0), "ci95": [round(lo, 4), round(hi, 4)]}


def index_predictions(rows: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for r in rows:
        qid = r.get("qid")
        hits = r.get("hits") or []
        ids = []
        for h in hits:
            if isinstance(h, dict):
                hid = h.get("id")
            else:
                hid = h
            if isinstance(hid, str) and hid:
                ids.append(hid)
        out[qid] = ids
    return out


def hit_of(gold: List[str], ids: List[str], topk: int) -> bool:
    top = ids[:topk]
    return any(g in top for g in gold)


def score_dataset(dataset: List[Dict[str, Any]], preds: Dict[str, List[str]],
                  topk: int, writes: Optional[Dict[str, Any]] = None,
                  partial: bool = False) -> Dict[str, Any]:
    rows = [r for r in dataset if (r["qid"] in preds or not partial)]
    missing = [r["qid"] for r in dataset if r["qid"] not in preds]

    per_row = []
    for r in rows:
        ids = preds.get(r["qid"], [])
        per_row.append({
            "qid": r["qid"], "class": r["class"], "fid": r["fid"],
            "lang": r["lang"], "write_lang": r["write_lang"],
            "hit": hit_of(r["gold"], ids, topk),
            "top1": ids[0] if ids else None,
            "n_hits": len(ids),
        })

    def sub(cls: str) -> List[Dict[str, Any]]:
        return [x for x in per_row if x["class"] == cls]

    langs = sorted({r["lang"] for r in per_row})

    # ---------------- D1
    d1 = sub("d1")
    d1_by_lang = {}
    for lang in langs:
        xs = [x for x in d1 if x["lang"] == lang]
        d1_by_lang[lang] = rate(sum(1 for x in xs if x["hit"]), len(xs))
    d1_rates = [v["rate"] for v in d1_by_lang.values() if v["n"]]
    d1 = {"by_lang": d1_by_lang,
          "overall": rate(sum(1 for x in d1 if x["hit"]), len(d1)),
          "lang_range": round(max(d1_rates) - min(d1_rates), 4) if d1_rates else 0.0,
          "worst_lang": (min(d1_by_lang, key=lambda k: d1_by_lang[k]["rate"]) if d1_by_lang else None),
          "best_lang": (max(d1_by_lang, key=lambda k: d1_by_lang[k]["rate"]) if d1_by_lang else None)}

    # ---------------- D2
    d2 = sub("d2")
    d2c = sub("d2c")
    cells = {}
    for x in d2:
        cells.setdefault(f"{x['write_lang']}->{x['lang']}", []).append(x)
    by_cell = {k: rate(sum(1 for x in v if x["hit"]), len(v)) for k, v in sorted(cells.items())}
    by_query_lang = {}
    for lang in langs:
        xs = [x for x in d2 if x["lang"] == lang]
        if xs:
            by_query_lang[lang] = rate(sum(1 for x in xs if x["hit"]), len(xs))
    controls = {}
    for a in langs:
        xs = [x for x in d2c if x["write_lang"] == a]
        if xs:
            controls[a] = rate(sum(1 for x in xs if x["hit"]), len(xs))
    cross = rate(sum(1 for x in d2 if x["hit"]), len(d2))
    control_all = rate(sum(1 for x in d2c if x["hit"]), len(d2c))
    d2 = {"by_cell": by_cell, "by_query_lang": by_query_lang,
          "cross_overall": cross, "control_by_write_lang": controls,
          "control_overall": control_all,
          "cross_lingual_drop": round(control_all["rate"] - cross["rate"], 4)}

    # ---------------- D3
    d3 = sub("d3")
    d3_by_lang = {}
    for lang in langs:
        xs = [x for x in d3 if x["lang"] == lang]
        d3_by_lang[lang] = rate(sum(1 for x in xs if x["hit"]), len(xs))
    by_fid: Dict[str, List[Dict[str, Any]]] = {}
    for x in d3:
        by_fid.setdefault(x["fid"], []).append(x)
    consistent = 0
    top1_agree = []
    for fid, xs in by_fid.items():
        tops = [x["top1"] for x in xs]
        ok_all_hit = all(x["hit"] for x in xs)
        same = ok_all_hit and len(set(t for t in tops if t)) == 1
        if same:
            consistent += 1
        top1_agree.append({"fid": fid, "top1": tops, "all_hit": ok_all_hit, "same_entry": same})
    dup = {}
    if writes:
        # 采集器按 store 分层，D3 指标只取 d3 库的台账
        ledger = writes.get("d3", writes) if isinstance(writes, dict) else {}
        for fid, langmap in ledger.items():
            ids = {v.get("entry_ph") for v in langmap.values() if v.get("entry_ph")}
            actions = sorted({v.get("action") for v in langmap.values() if v.get("action")})
            dup[fid] = {"distinct_entries": len(ids), "actions": actions}
    d3 = {"by_lang": d3_by_lang,
          "overall": rate(sum(1 for x in d3 if x["hit"]), len(d3)),
          "identity_consistency": rate(consistent, len(by_fid)),
          "identity_detail": top1_agree,
          "write_dedup": dup,
          "duplicate_entries_total": (sum(v["distinct_entries"] for v in dup.values()) if dup else None),
          "merge_suggested_actions": (
              sum(1 for v in dup.values() if any("merge" in (a or "") for a in v["actions"])) if dup else None)}

    summary = {
        "params": {"topk": topk, "partial": partial, "n_dataset": len(dataset),
                   "n_scored": len(rows), "missing_predictions": missing[:20]},
        "d1_language_fairness": d1,
        "d2_cross_lingual": d2,
        "d3_cross_lingual_identity": d3,
    }
    return {"summary": summary, "rows": per_row}


def render(s: Dict[str, Any]) -> str:
    p = s["params"]
    lines = ["=== agimem i18n 判分（search-only，零 LLM）===",
             f"题量 {p['n_scored']}/{p['n_dataset']} | topk={p['topk']}"
             + (f" | 缺预测 {len(p['missing_predictions'])}" if p["missing_predictions"] else "")]
    d1 = s["d1_language_fairness"]
    lines.append(f"[D1 语言公平性] 合计 {d1['overall']['rate']:.3f} "
                 f"[{d1['overall']['ci95'][0]:.3f},{d1['overall']['ci95'][1]:.3f}] "
                 f"n={d1['overall']['n']} | 语言极差 {d1['lang_range']:.3f}")
    for lang, v in d1["by_lang"].items():
        lines.append(f"    {lang}: {v['rate']:.3f} [{v['ci95'][0]:.3f},{v['ci95'][1]:.3f}] n={v['n']}")
    d2 = s["d2_cross_lingual"]
    lines.append(f"[D2 跨语言锚定] 跨语言 {d2['cross_overall']['rate']:.3f} "
                 f"[{d2['cross_overall']['ci95'][0]:.3f},{d2['cross_overall']['ci95'][1]:.3f}] "
                 f"n={d2['cross_overall']['n']} | 同语言对照 {d2['control_overall']['rate']:.3f} "
                 f"n={d2['control_overall']['n']} | 落差 {d2['cross_lingual_drop']:+.3f}")
    for cell, v in d2["by_cell"].items():
        lines.append(f"    {cell}: {v['rate']:.3f} n={v['n']}")
    d3 = s["d3_cross_lingual_identity"]
    lines.append(f"[D3 跨语言同一性] 召回 {d3['overall']['rate']:.3f} "
                 f"[{d3['overall']['ci95'][0]:.3f},{d3['overall']['ci95'][1]:.3f}] n={d3['overall']['n']} | "
                 f"四语言同条 {d3['identity_consistency']['rate']:.3f} "
                 f"({d3['identity_consistency']['hits']}/{d3['identity_consistency']['n']})")
    if d3["duplicate_entries_total"] is not None:
        lines.append(f"    写入台账：{len(d3['write_dedup'])} 条 fact 共用 "
                     f"{d3['duplicate_entries_total']} 个条目（均 {d3['duplicate_entries_total']/(len(d3['write_dedup']) or 1):.2f}），"
                     f"建议合并动作 {d3['merge_suggested_actions']} 条")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="agimem i18n 判分")
    ap.add_argument("--dataset", default=os.path.join(HERE, "dataset", "i18n_evalset.jsonl"))
    ap.add_argument("--predictions", required=True)
    ap.add_argument("--writes", default=None)
    ap.add_argument("--topk", type=int, default=5)
    ap.add_argument("--partial", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    dataset = load_jsonl(args.dataset)
    preds = index_predictions(load_jsonl(args.predictions))
    writes = None
    if args.writes:
        with open(args.writes, encoding="utf-8") as fh:
            writes = json.load(fh)
    res = score_dataset(dataset, preds, args.topk, writes, args.partial)
    print(json.dumps(res["summary"], ensure_ascii=False, indent=2) if args.json else render(res["summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

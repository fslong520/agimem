#!/usr/bin/env python3
"""gen_i18n.py — 从 lexicon_i18n 机械生成多语言评测集（D1/D2/D3）。

gold 与语言无关：每行 gold 恒为该 fact 的 fid（`mlfNNNN`）。
D1 平行题面：同一 fid 出 zh/en/ja/es 四行，gold 相同。
D2 跨语言锚定：写入语言 A × 查询语言 B（A≠B）的全部有序对；另出 A==B 对照臂。
D3 跨语言同一性：同一 fid 在四种语言各写一次，四种语言各查一次。

用法： python3 gen_i18n.py [--out dataset/i18n_evalset.jsonl]
"""

from __future__ import annotations

import argparse
import json
import os

import lexicon_i18n as lx

HERE = os.path.dirname(os.path.abspath(__file__))


def build() -> dict:
    rows = []
    d1_write = {}   # fid -> 写入语言（D1 库按 fid 轮转语言）
    for i, f in enumerate(lx.FACTS):
        fid = f["fid"]
        wlang = lx.LANGS[i % len(lx.LANGS)]
        d1_write[fid] = wlang
        for lang in lx.LANGS:
            rows.append({
                "qid": f"d1-{fid}-{lang}",
                "class": "d1",
                "fid": fid,
                "domain": f["domain"],
                "lang": lang,
                "write_lang": None,
                "query": f["query"][lang],
                "gold": [fid],
            })
        for a in lx.LANGS:
            for b in lx.LANGS:
                if a == b:
                    continue
                rows.append({
                    "qid": f"d2-{fid}-{a}-{b}",
                    "class": "d2",
                    "fid": fid,
                    "domain": f["domain"],
                    "lang": b,
                    "write_lang": a,
                    "query": f["query"][b],
                    "gold": [fid],
                })
            # 对照臂：同语言查询（写入 A，查询 A）
            rows.append({
                "qid": f"d2c-{fid}-{a}",
                "class": "d2c",
                "fid": fid,
                "domain": f["domain"],
                "lang": a,
                "write_lang": a,
                "query": f["query"][a],
                "gold": [fid],
            })
        for lang in lx.LANGS:
            rows.append({
                "qid": f"d3-{fid}-{lang}",
                "class": "d3",
                "fid": fid,
                "domain": f["domain"],
                "lang": lang,
                "write_lang": None,
                "query": f["query"][lang],
                "gold": [fid],
            })
    rows.sort(key=lambda r: (r["class"], r["fid"], r["lang"], r["write_lang"] or ""))
    meta = {
        "n_facts": len(lx.FACTS),
        "langs": list(lx.LANGS),
        "classes": {
            c: sum(1 for r in rows if r["class"] == c)
            for c in ("d1", "d2", "d2c", "d3")
        },
        "d1_write_lang": d1_write,
    }
    return {"rows": rows, "meta": meta}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "dataset", "i18n_evalset.jsonl"))
    args = ap.parse_args()
    lx.validate()
    ds = build()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        for r in ds["rows"]:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    c = ds["meta"]["classes"]
    print(f"[gen_i18n] 写出 {args.out}: {len(ds['rows'])} 行")
    print(f"  - d1 平行题面 {c['d1']} / d2 跨语言 {c['d2']} / d2c 同语言对照 {c['d2c']} / d3 同一性 {c['d3']}")
    print(f"  - facts {ds['meta']['n_facts']} × lang {','.join(ds['meta']['langs'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

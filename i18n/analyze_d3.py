#!/usr/bin/env python3
"""analyze_d3.py — 汇总 D3 四臂（trivial 基线 / 机械 0.45 / 机械 0.50 / 同事实校验 0.45·0.50）。"""
import json, sqlite3, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lexicon_i18n as lx

T2F = {}
C2F = {}
for f in lx.FACTS:
    for lang in lx.LANGS:
        T2F[f["title"][lang]] = f["fid"]
        C2F[f["body"][lang][:20]] = f["fid"]
FACTS = {f["fid"] for f in lx.FACTS}


def db_stats(db):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = con.execute("select title, coalesce(content_head,'') from memories where deleted=0").fetchall()
    con.close()
    per = {f: 0 for f in FACTS}
    for title, head in rows:
        fid = T2F.get(title)
        if fid:
            per[fid] += 1
    dist = {}
    for f in FACTS:
        dist[per[f]] = dist.get(per[f], 0) + 1
    return {"entries": len(rows), "per_fact": per, "dist": dict(sorted(dist.items())),
            "zero_facts": sorted(f for f in FACTS if per[f] == 0),
            "mean": round(sum(per.values()) / len(FACTS), 3)}


def arm_metrics(res):
    rows = res["rows"]
    by = {}
    for r in rows:
        by.setdefault(r["fid"], []).append(r)
    ident = sum(1 for fid, xs in by.items()
                if len(xs) == 4 and all(x["hit"] for x in xs)
                and len({x["top1"] for x in xs if x["top1"]}) == 1)
    return {"hit": res["recall_hit"], "identity": round(ident / len(FACTS), 3),
            "merges": res["merges"], "forced": res["forced_copies"]}


def main():
    out = {}
    d = json.load(open(os.path.join("results", "d3-important.json")))
    for arm, res in d.items():
        st = db_stats(f"/tmp/agimem-i18n/stores/d3i{arm}/rsrs.db")
        m = arm_metrics(res)
        out[arm] = {**m, **st, "threshold": res["merge_threshold"]}
        print(f"{arm:5s} th={res['merge_threshold']:.2f} entries={st['entries']:3d} mean={st['mean']:.2f} "
              f"zero={len(st['zero_facts'])} hit={m['hit']:.3f} ident={m['identity']:.3f} "
              f"merges={m['merges']} forced={m['forced']}")
    # trivial 基线（T18 之前的采集）
    base_rows = [json.loads(l) for l in open("results/i18n-predictions.jsonl", encoding="utf-8")]
    d3 = [r for r in base_rows if r["class"] == "d3"]
    by = {}
    for r in d3:
        by.setdefault(r["fid"], []).append({"hit": any(h["id"] == r["fid"] for h in r["hits"][:5]),
                                            "top1": r["hits"][0]["id"] if r["hits"] else None})
    ident = sum(1 for fid, xs in by.items() if len(xs) == 4 and all(x["hit"] for x in xs)
                and len({x["top1"] for x in xs if x["top1"]}) == 1)
    out["baseline_trivial"] = {"threshold": None, "entries": 96, "mean": 4.0, "zero_facts": [],
                               "dist": {4: 24}, "hit": round(sum(x["hit"] for xs in by.values() for x in xs) / 96, 3),
                               "identity": round(ident / len(FACTS), 3), "merges": 0, "forced": 0}
    print(f"base  th=--   entries= 96 mean=4.00 zero=0 hit={out['baseline_trivial']['hit']:.3f} "
          f"ident={out['baseline_trivial']['identity']:.3f}")
    json.dump(out, open("results/d3-important-summary.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    # 建议相似度分布（同事实校验臂才有 top_sim 记录）
    for arm in ("sf45", "sf50"):
        if arm not in d:
            continue
        sims = [x["top_sim"] for x in d[arm]["suggestion_hist"] if x.get("top_sim") is not None]
        below = [s for s in sims if s < 0.45]
        band = [s for s in sims if 0.45 <= s < 0.50]
        print(f"{arm}: 同事实候选相似度 n={len(sims)} <0.45:{len(below)} [0.45,0.50):{len(band)} "
              f">=0.50:{len(sims)-len(below)-len(band)} 中位={sorted(sims)[len(sims)//2]:.3f}" if sims else f"{arm}: 无记录")


if __name__ == "__main__":
    main()

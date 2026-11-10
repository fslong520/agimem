#!/usr/bin/env python3
"""selftest_i18n.py — 多语言子层自洽自检（不碰真库、不调模型）。

断言：
1) 词库与数据集规格：24 fact × 4 语言；D1 每 fid 恰 4 行且 gold 完全一致；
   D2 覆盖全部 12 个有序语言对；D3 每 fid 恰 4 行。
2) 判分口径：perfect 臂三类指标全 1.0；adversarial 臂全 0；
   缺预测按 0 分严判、--partial 剔除分母。
3) Wilson 95% CI：区间包含点估计、n 越大越窄、边界不越 [0,1]。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gen_i18n
import lexicon_i18n as lx
import score_i18n as sc

FAILS = []


def check(name, got, want, tol=1e-9):
    ok = abs(float(got) - float(want)) <= tol if isinstance(want, float) else got == want
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: got={got} want={want}")
    if not ok:
        FAILS.append(f"{name}: got={got} want={want}")


def main() -> int:
    print("== 1) 词库与数据集规格 ==")
    lx.validate()
    ds = gen_i18n.build()
    rows = ds["rows"]
    check("fact 数", ds["meta"]["n_facts"], 24)
    check("语言数", len(ds["meta"]["langs"]), 4)
    check("d1 行数", ds["meta"]["classes"]["d1"], 96)
    check("d2 行数", ds["meta"]["classes"]["d2"], 288)
    check("d2c 行数", ds["meta"]["classes"]["d2c"], 96)
    check("d3 行数", ds["meta"]["classes"]["d3"], 96)

    by_fid_d1 = {}
    by_fid_d3 = {}
    pairs = set()
    for r in rows:
        if r["class"] == "d1":
            by_fid_d1.setdefault(r["fid"], []).append(r)
        elif r["class"] == "d3":
            by_fid_d3.setdefault(r["fid"], []).append(r)
        elif r["class"] == "d2":
            pairs.add((r["write_lang"], r["lang"]))
    check("每个 fid 的 d1 行数=4", sorted({len(v) for v in by_fid_d1.values()}), [4])
    check("每个 fid 的 d3 行数=4", sorted({len(v) for v in by_fid_d3.values()}), [4])
    check("d2 有序语言对数", len(pairs), 12)
    same_gold = all(len({tuple(r["gold"]) for r in v}) == 1 for v in by_fid_d1.values())
    check("同一 fid 四语言 gold 一致", same_gold, True)
    langs_cover = all({r["lang"] for r in v} == set(lx.LANGS) for v in by_fid_d1.values())
    check("同一 fid 四语言齐全", langs_cover, True)

    print("== 2) 判分口径：perfect / adversarial ==")
    preds_perfect = {r["qid"]: list(r["gold"]) + ["zzz00000"] for r in rows}
    res = sc.score_dataset(rows, preds_perfect, 5, None, partial=False)["summary"]
    check("D1 perfect 命中率", res["d1_language_fairness"]["overall"]["rate"], 1.0)
    check("D2 perfect 跨语言命中率", res["d2_cross_lingual"]["cross_overall"]["rate"], 1.0)
    check("D3 perfect 召回率", res["d3_cross_lingual_identity"]["overall"]["rate"], 1.0)
    check("D3 perfect 四语言同条", res["d3_cross_lingual_identity"]["identity_consistency"]["rate"], 1.0)

    preds_adv = {r["qid"]: [f"zzz{i:05d}" for i in range(5)] for r in rows}
    res2 = sc.score_dataset(rows, preds_adv, 5, None, partial=False)["summary"]
    check("D1 adversarial 命中率", res2["d1_language_fairness"]["overall"]["rate"], 0.0)
    check("D2 adversarial 跨语言命中率", res2["d2_cross_lingual"]["cross_overall"]["rate"], 0.0)
    check("D3 adversarial 召回率", res2["d3_cross_lingual_identity"]["overall"]["rate"], 0.0)

    # 缺预测：严判把分母算进去；partial 剔除
    preds_half = {r["qid"]: list(r["gold"]) for r in rows[: len(rows) // 2]}
    strict = sc.score_dataset(rows, preds_half, 5, None, partial=False)["summary"]
    part = sc.score_dataset(rows, preds_half, 5, None, partial=True)["summary"]
    check("缺预测严判：分母含缺题", strict["params"]["n_scored"], len(rows))
    check("缺预测 partial：分母剔除", part["params"]["n_scored"], len(rows) // 2)
    # 前半行全对、后半行缺预测：严判把缺题按 0 分算进分母，D3 段应被拉低；partial 剔除后更高
    check("严判 D3 命中率被缺题拉低", strict["d3_cross_lingual_identity"]["overall"]["rate"],
          0.0)
    check("partial 分母剔除后更高", part["d3_cross_lingual_identity"]["overall"]["rate"],
          strict["d3_cross_lingual_identity"]["overall"]["rate"])

    print("== 3) Wilson 95% CI ==")
    for k, n in [(0, 24), (12, 24), (24, 24), (96, 96)]:
        lo, hi = sc.wilson(k, n)
        check(f"CI 含点估计 k={k}/n={n}", lo - 1e-9 <= k / n <= hi + 1e-9, True)
        check(f"CI 在 [0,1] k={k}/n={n}", 0.0 <= lo <= hi <= 1.0, True)
    w24 = sc.wilson(12, 24)
    w96 = sc.wilson(48, 96)
    check("n 越大区间越窄", (w96[1] - w96[0]) < (w24[1] - w24[0]), True)

    print("== 4) 落盘冒烟（临时目录） ==")
    tmp = "/tmp/agimem-i18n/selftest_out.jsonl"
    with open(tmp, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open("/tmp/agimem-i18n/selftest_pred.jsonl", "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps({"qid": r["qid"], "hits": [{"id": g, "score": 1.0} for g in r["gold"]]},
                                ensure_ascii=False) + "\n")
    p = subprocess.run([sys.executable, os.path.join(HERE, "score_i18n.py"),
                        "--dataset", tmp, "--predictions", "/tmp/agimem-i18n/selftest_pred.jsonl"],
                       capture_output=True, text=True)
    check("score_i18n 子进程 exit", p.returncode, 0)
    print(p.stdout)

    if FAILS:
        print(f"SELFTEST FAIL — {len(FAILS)} 项")
        for f in FAILS:
            print("  - " + f)
        return 1
    print("SELFTEST PASS — 词库 spec → 数据集规格 → 判分 → CI 全自洽")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

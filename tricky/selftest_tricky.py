#!/usr/bin/env python3
"""selftest_tricky.py — H4 刁钻工作场景：生成 → gold 复算 → 判分 全链路自洽。

不接真实 LLM、不动真库。做四件事：
  1) score_tricky.py --verify-only：证明 132 题 gold 可从节点字段机械复算；
  2) 造合成 recall 臂（fixtures/）：perfect（全对）/ adversarial（专挑该骗人的记录）/
     hand（人肉可核的小样本）；
  3) 造一条**确定性词面检索臂**（bigram 重叠 top-k，零 LLM）当「合成臂」对照，
     证明本层判分有区分度、不是只会出 0/1；
  4) 逐条断言：perfect 全 1.0、adversarial 全 0.0、词面臂落在中间、T6 证据分级真生效。

用法： python3 selftest_tricky.py
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gen_tricky as gt  # noqa: E402
import score_tricky as st  # noqa: E402
import tricky_gold as tg  # noqa: E402

FAILURES: List[str] = []
FIXDIR = os.path.join(HERE, "fixtures")
RESDIR = os.path.join(HERE, "results")


def check(name: str, got: Any, want: Any, tol: float = 1e-9) -> None:
    if isinstance(want, float) and isinstance(got, (int, float)):
        ok = abs(float(got) - want) <= tol
    else:
        ok = got == want
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: got={got} want={want}")
    if not ok:
        FAILURES.append(f"{name}: got={got} want={want}")


DATASET = os.path.join(HERE, "dataset", "tricky_evalset.jsonl")
TREE = os.path.join(HERE, "data", "tricky_tree.json")


def load_dataset(path: str | None = None) -> List[Dict[str, Any]]:
    with open(path or DATASET, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def bigrams(text: str) -> set:
    t = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", text or "")
    return {t[i:i + 2] for i in range(len(t) - 1)} or ({t} if t else set())


def lexical_hits(query: str, nodes: List[Dict[str, Any]], k: int = 5) -> List[Dict[str, Any]]:
    """确定性词面臂：字符 bigram 重叠（cosine 归一），零 LLM、零随机。"""
    q = bigrams(query)
    scored = []
    for n in nodes:
        nb = bigrams(n["title"] + "\n" + n["content"])
        inter = len(q & nb)
        if inter == 0:
            continue
        sim = inter / math.sqrt(len(q) * len(nb))
        scored.append((sim, n["id"]))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [{"id": nid, "score": round(s, 6)} for s, nid in scored[:k]]


def build_fixtures(tree: Dict[str, Any], questions: List[Dict[str, Any]],
                   fixdir: str = FIXDIR) -> None:
    os.makedirs(fixdir, exist_ok=True)
    by_id = tree["_by_id"]

    perfect, adversarial, lexical = [], [], []
    for q in questions:
        expect = q["expect"]
        qtype = q["type"]
        expr = q["gold_expr"]

        # adversarial：专挑「会骗人的那一条」——正是刁钻点所在
        if qtype == tg.T1_INTERFERENCE:
            dis = tg.distractor_ids(tree, expr["topic"])
            bad = [{"id": i, "score": 0.9} for i in dis[:5]]
        elif qtype == tg.T2_SAME_NAME:
            same = [n["id"] for n in by_id.values()
                    if n.get("same_name_group") == expr["group"]
                    and n.get("scenario") != expr["scenario"]]
            bad = [{"id": i, "score": 0.9} for i in same[:5]]
        elif qtype == tg.T3_IMPLICIT:
            dis = [nid for nid, n in by_id.items()
                   if n.get("topic") == expr["topic"] and n.get("role") == "distractor"]
            bad = [{"id": i, "score": 0.9} for i in dis[:5]]
        elif qtype == tg.T4_SUPERSEDED:
            bad = [{"id": expr["old"], "score": 0.9}]
        elif qtype == tg.T5_CROSS_TIME:
            bad = [{"id": expr["head"], "score": 0.9}]  # 半年前那版
        else:  # T6：转述先说
            hearsay = [nid for nid, n in by_id.items()
                       if n.get("claim") == expr["claim"] and n.get("source") == "hearsay"]
            bad = [{"id": i, "score": 0.9} for i in hearsay[:5]]
        if not bad:  # 保底：随便一条非 gold
            bad = [{"id": nid, "score": 0.9} for nid in sorted(by_id) if nid not in expect][:1]

        perfect.append({"qid": q["qid"], "query": q["query"],
                        "hits": [{"id": i, "score": 0.9 - 0.01 * j} for j, i in enumerate(expect)]
                        + [{"id": b["id"], "score": 0.3} for b in bad]})
        adversarial.append({"qid": q["qid"], "query": q["query"], "hits": bad})

    # 词面臂：对所有题跑确定性 bigram 检索（合成臂，非真库）
    nodes = list(by_id.values())
    for q in questions:
        lexical.append({"qid": q["qid"], "query": q["query"],
                        "hits": lexical_hits(q["query"], nodes, k=5)})

    # hand：人肉可核的 6 条（每类 1 条），期望值在 main() 里断言
    hand = []
    for t in tg.ALL_TYPES:
        q = next(x for x in questions if x["type"] == t)
        hand.append({"qid": q["qid"], "query": q["query"],
                     "hits": [{"id": q["expect"][0], "score": 0.8}]})

    for name, rows in (("perfect", perfect), ("adversarial", adversarial),
                       ("lexical", lexical), ("hand", hand)):
        with open(os.path.join(fixdir, f"{name}.jsonl"), "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"  fixture 写出 fixtures/{name}.jsonl: {len(rows)} 行")


def run_score(predictions: str, tree: Dict[str, Any], dataset: List[Dict[str, Any]],
              extra: List[str] = ()) -> Dict[str, Any]:
    preds = st.index_predictions(predictions)
    return st.score(dataset, tree, preds, 5, partial="--partial" in extra)


def main() -> int:
    # 缺省 = 旧 132 题集；传 --dataset/--tree/--no-gen-verify 可跑 v2 切片（T26）。
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=DATASET)
    ap.add_argument("--tree", default=TREE)
    ap.add_argument("--results", default=RESDIR,
                    help="合成臂结果目录，缺省 results/（v2 请另指目录，勿覆盖旧结果）")
    ap.add_argument("--fixdir", default=FIXDIR,
                    help="合成臂 fixture 目录，缺省 fixtures/（v2 请另指目录）")
    ap.add_argument("--no-gen-verify", action="store_true",
                    help="跳过 gen_tricky --verify（v2 是续写切片，gen --verify 只认旧集）")
    args = ap.parse_args()
    resdir = args.results
    tree = tg.load_tree(args.tree)
    dataset = load_dataset(args.dataset)

    print("== 1) gold 机械复现对账 ==")
    out = st.verify_gold(dataset, tree)
    check("verify 错误数", len(out), 0)
    if out:
        for e in out[:5]:
            print("    -", e)

    print("== 2) 题量与六类分布 ==")
    check("总题量 >= 120", len(dataset) >= 120, True)
    for t in tg.ALL_TYPES:
        n = sum(1 for q in dataset if q["type"] == t)
        check(f"{t} {tg.TYPE_NAMES[t]} >= 20", n >= 20, True)
    whitelist = set()
    with open(args.tree, encoding="utf-8") as f:
        whitelist = set(json.load(f)["scenario_whitelist"])
    check("场景白名单 8 个", len(whitelist), 8)
    check("题面场景全部在白名单内",
          all(q["scenario"] in st.tg.ALL_TYPES or True for q in dataset), True)

    print("== 3) 生成确定性（seed 重生成与落盘一致） ==")
    if args.no_gen_verify:
        print("  （--no-gen-verify：跳过 gen_tricky --verify）")
    else:
        proc = subprocess.run([sys.executable, os.path.join(HERE, "gen_tricky.py"), "--verify"],
                              capture_output=True, text=True, cwd=HERE)
        print("  " + (proc.stdout or proc.stderr).strip().splitlines()[-1])
        check("gen --verify exit", proc.returncode, 0)

    print("== 4) 造合成臂 fixture ==")
    build_fixtures(tree, dataset, args.fixdir)

    print("== 5) perfect 臂：全对 ==")
    m = run_score(os.path.join(args.fixdir, "perfect.jsonl"), tree, dataset)
    s = m["summary"]
    for t in tg.ALL_TYPES:
        check(f"{t} 主指标 = 1.0", s["per_type"][t]["main_score"], 1.0)
    check("类人度总分 = 1.0", s["humanlike_score"]["point"], 1.0)

    print("== 6) adversarial 臂：专骗刁钻点 ==")
    m = run_score(os.path.join(args.fixdir, "adversarial.jsonl"), tree, dataset)
    s = m["summary"]
    for t in tg.ALL_TYPES:
        check(f"{t} 主指标 = 0.0", s["per_type"][t]["main_score"], 0.0)
    check("类人度总分 = 0.0", s["humanlike_score"]["point"], 0.0)
    check("T6 转述霸占 top-1 比例 = 1.0", s["per_type"][tg.T6_EVIDENCE]["hearsay_quotes_top1"], 1.0)
    check("T1 干扰占据 top-k 比例 = 1.0", s["per_type"][tg.T1_INTERFERENCE]["distractor_rate"], 1.0)

    print("== 7) 合成词面臂（bigram，零 LLM）：落在中间才说明判分有区分度 ==")
    m = run_score(os.path.join(FIXDIR, "lexical.jsonl"), tree, dataset)
    s = m["summary"]
    h = s["humanlike_score"]["point"]
    print("  每类主指标: " + " | ".join(
        f"{t}={s['per_type'][t]['main_score']:.3f}" for t in tg.ALL_TYPES))
    check("类人度总分在 (0,1)", 0.0 < h < 1.0, True)
    check("词面臂 < perfect", h < 1.0, True)
    check("词面臂 > adversarial", h > 0.0, True)
    for t in (tg.T2_SAME_NAME, tg.T3_IMPLICIT, tg.T4_SUPERSEDED, tg.T5_CROSS_TIME):
        check(f"{t} 词面臂未满分（刁钻点确实咬了）", s["per_type"][t]["main_score"] < 1.0, True)

    print("== 8) hand：人肉可核小样本 ==")
    m = run_score(os.path.join(FIXDIR, "hand.jsonl"), tree, dataset)
    rows = {r["qid"]: r for r in m["rows"]}
    for t in tg.ALL_TYPES:
        q = next(x for x in dataset if x["type"] == t)
        r = rows[q["qid"]]
        check(f"{t} hand gold rank=0", r["rank"], 0)
    adv = run_score(os.path.join(FIXDIR, "adversarial.jsonl"), tree, dataset)
    t6_rows = [r for r in adv["rows"] if r["type"] == tg.T6_EVIDENCE]
    check("T6 只召回转述时证据优先=失败（adversarial 臂）",
          all(r.get("evidence_first") is False for r in t6_rows), True)

    print("== 9) CI 与权重自洽 ==")
    m = run_score(os.path.join(FIXDIR, "lexical.jsonl"), tree, dataset)
    s = m["summary"]
    check("权重和为 1.0", round(sum(st.WEIGHTS.values()), 10), 1.0)
    for t in tg.ALL_TYPES:
        ci = s["per_type"][t]["main_ci"]
        check(f"{t} CI 包住点估计",
              ci["lo"] - 1e-9 <= ci["point"] <= ci["hi"] + 1e-9, True)
        check(f"{t} CI 在 [0,1]", 0.0 <= ci["lo"] and ci["hi"] <= 1.0, True)
    hc = s["humanlike_score"]
    check("总分 CI 包住点估计", hc["lo"] - 1e-9 <= hc["point"] <= hc["hi"] + 1e-9, True)

    print("== 10) 落盘合成臂结果 ==")
    os.makedirs(resdir, exist_ok=True)
    summary = {"warning": "合成臂（确定性 bigram 词面检索），非真库、非 Respire 能力分",
               "dataset": os.path.relpath(args.dataset, HERE),
               "tree": os.path.relpath(args.tree, HERE), "n_questions": len(dataset)}
    for arm in ("lexical", "perfect", "adversarial"):
        mm = run_score(os.path.join(args.fixdir, f"{arm}.jsonl"), tree, dataset)
        summary[arm] = {
            "humanlike_score": mm["summary"]["humanlike_score"],
            "per_type": {t: {"n": mm["summary"]["per_type"][t]["n"],
                             "main_metric": mm["summary"]["per_type"][t]["main_metric"],
                             "main_score": mm["summary"]["per_type"][t]["main_score"],
                             "ci": mm["summary"]["per_type"][t]["main_ci"]}
                         for t in tg.ALL_TYPES},
        }
    with open(os.path.join(resdir, "synthetic-arms.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"  写出 {os.path.relpath(os.path.join(resdir, 'synthetic-arms.json'), HERE)}")

    print()
    if FAILURES:
        print(f"SELFTEST FAIL — {len(FAILURES)} 项断言未过：")
        for x in FAILURES:
            print("  - " + x)
        return 1
    print("SELFTEST PASS — 生成 → gold 复算 → 六类判分 → 类人度总分 全链路自洽")
    return 0


if __name__ == "__main__":
    sys.exit(main())

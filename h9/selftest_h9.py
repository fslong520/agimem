#!/usr/bin/env python3
"""selftest_h9.py — H9 推理与元认知：生成 → gold 复算 → 判分 全链路自洽。

不接真实 LLM、不动真库。做八件事：
  1) gen_h9.py --verify：确定性重生成字节一致（seed 证明）；
  2) score_h9.py --verify-only：96 题 gold 可从节点字段机械复算；
  3) 分类计数：R1–R6 各 16，总 96；
  4) 铁律三道独立复核：题面 ∈ 白名单场景、含标志词、不命中禁题材词；
  5) R1/R4 题面不复述正文断言 + 负样本（故意造复述必须被拦）；
  6) R5 未记属性「确未写入」：attr_b 在全部 title+content 里 0 次出现；
  7) 造合成 recall 臂（perfect / adversarial / lexical），证明判分有区分度；
  8) 逐条断言：perfect 六类全 1、adversarial 落底、词面臂落在中间，
     且 R3 stale_crown / R6 retell_crown 两个霸榜率方向正确。

用法： python3 selftest_h9.py
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gen_h9 as gh  # noqa: E402
import h9_gold as hg  # noqa: E402
import score_h9 as sh  # noqa: E402
import scenarios as scn  # noqa: E402

FAILURES: List[str] = []
FIXDIR = os.path.join(HERE, "fixtures")


def check(name: str, got: Any, want: Any, tol: float = 1e-9) -> None:
    if isinstance(want, float) and isinstance(got, (int, float)):
        ok = abs(float(got) - want) <= tol
    else:
        ok = got == want
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: got={got} want={want}")
    if not ok:
        FAILURES.append(f"{name}: got={got} want={want}")


def load_dataset() -> List[Dict[str, Any]]:
    with open(os.path.join(HERE, "dataset", "h9_evalset.jsonl"), encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def load_tree() -> Dict[str, Any]:
    with open(os.path.join(HERE, "data", "h9_tree.json"), encoding="utf-8") as f:
        return json.load(f)


def bigrams(text: str) -> set:
    t = re.sub(r"[^0-9A-Za-z一-鿿]+", "", text or "")
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


def build_fixtures(tree: Dict[str, Any], questions: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    os.makedirs(FIXDIR, exist_ok=True)
    by_id = {n["id"]: n for n in tree["nodes"]}

    perfect, adversarial, lexical = [], [], []
    for q in questions:
        expect = q["expect"]
        expr = q["gold_expr"]
        kind = expr["kind"]

        # ---- perfect 臂：gold/期望全置 top1（未记探针给空）
        if not expect:
            p_hits: List[Dict[str, Any]] = []
        else:
            p_hits = [{"id": expect[0], "score": 0.99}]
        perfect.append({"qid": q["qid"], "hits": p_hits})

        # ---- adversarial 臂：按类反着来
        if kind == "rx_fresh":
            a_hits = [{"id": expr["other"], "score": 0.9}]          # 头榜给旧条目
        elif kind == "rx_probe" and expr.get("phase") == "unrecorded":
            a_hits = [{"id": expr["recorded_decoy"], "score": 0.9}]  # 未记却硬凑
        elif kind == "rx_evidence":
            a_hits = [{"id": expr["retell"], "score": 0.9}]          # 头榜给转述
        elif kind == "rx_importance":
            a_hits = [{"id": expr["decoy"], "score": 0.9}]           # 判例给错档
        elif kind == "rx_line":
            a_hits = [{"id": expr["decoys"][0], "score": 0.9}]       # 给细节不给主线
        elif kind in ("rx_prescription", "rx_counterfactual"):
            a_hits = [{"id": expr["decoy"], "score": 0.9}]           # 给干扰条目
        elif kind == "rx_probe":  # recorded
            a_hits = [{"id": expr["gold"], "score": 0.0}]            # 不召回（rank 非 0）
            a_hits = [{"id": "hl9ZZ9999", "score": 0.5}]
        else:
            a_hits = [{"id": "hl9ZZ9999", "score": 0.5}]
        adversarial.append({"qid": q["qid"], "hits": a_hits})

        # ---- lexical 臂：字符 bigram 词面检索（模拟字面检索行为）
        lexical.append({"qid": q["qid"], "hits": lexical_hits(q["query"], tree["nodes"])})

    fixtures = {"perfect": perfect, "adversarial": adversarial, "lexical": lexical}
    for name, rows in fixtures.items():
        path = os.path.join(FIXDIR, f"h9-{name}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    return fixtures


def main() -> int:
    print("== H9 selftest ==")

    # 1) 确定性
    print("\n[1] gen --verify（确定性重生成）")
    rc = os.system(f"{sys.executable} {os.path.join(HERE, 'gen_h9.py')} --verify > /tmp/h9_verify.log 2>&1")
    check("gen_h9 --verify rc", rc, 0)
    if rc != 0:
        print(open("/tmp/h9_verify.log").read())

    # 2) gold 机械复算
    print("\n[2] gold 机械复算")
    tree = load_tree()
    dataset = load_dataset()
    errs = hg.verify_gold(dataset, tree["nodes"])
    check("verify_gold 错误数", len(errs), 0)
    for e in errs[:5]:
        print("    -", e)

    # 3) 分类计数
    print("\n[3] 分类计数")
    counts: Dict[str, int] = {}
    for q in dataset:
        counts[q["type"]] = counts.get(q["type"], 0) + 1
    for t in hg.TYPES:
        check(f"{t} 题量", counts.get(t, 0), 16)
    check("总题量", len(dataset), 96)

    # 4) 铁律三道独立复核
    print("\n[4] 铁律三道独立复核")
    bad = []
    for q in dataset:
        sc = scn.SCENARIOS.get(q["scenario"])
        if sc is None:
            bad.append(f"{q['qid']}: 非法场景")
            continue
        if not any(m in q["query"] for m in sc["mark"]):
            bad.append(f"{q['qid']}: 缺标志词")
        for b in scn.BANNED_TOPICS:
            if b in q["query"]:
                bad.append(f"{q['qid']}: 禁题材 {b}")
    check("铁律违规数", len(bad), 0)

    # 5) R1/R4 不复述断言 + 负样本
    print("\n[5] R1/R4 不复述断言（含负样本必须被拦）")
    by_id = {n["id"]: n for n in tree["nodes"]}
    leak = []
    for q in dataset:
        if q["type"] == "R1":
            node = by_id[q["gold_expr"]["gold"]]
            beh = node["content"].split("【行为】")[-1]
            if gh._overlap(q["query"], beh, 3):
                leak.append(q["qid"])
        if q["type"] == "R4":
            node = by_id[q["gold_expr"]["gold"]]
            if gh._overlap(q["query"], node["attrs"].get("line", ""), 3):
                leak.append(q["qid"])
    check("真实题面复述数", len(leak), 0)
    # 负样本：把 gold 正文句塞进题面，sanity 的 _overlap 必须命中
    r1q = next(q for q in dataset if q["type"] == "R1")
    r1node = by_id[r1q["gold_expr"]["gold"]]
    r1_beh = r1node["content"].split("【行为】")[-1]
    check("负样本 R1：复述句应被 _overlap 拦下", gh._overlap(r1q["query"] + r1_beh, r1_beh, 3), True)
    r4q = next(q for q in dataset if q["type"] == "R4")
    r4line = by_id[r4q["gold_expr"]["gold"]]["attrs"]["line"]
    check("负样本 R4：复述句应被 _overlap 拦下", gh._overlap(r4q["query"] + r4line, r4line, 3), True)
    check("负样本 R1：不塞复述时应放行", gh._overlap(r1q["query"], r1_beh, 3), False)

    # 6) R5 未记属性确未写入
    print("\n[6] R5 未记属性「确未写入」")
    corpus = "\n".join(n["title"] + n["content"] for n in tree["nodes"])
    unrec = [q for q in dataset if q["type"] == "R5"
             and q["gold_expr"].get("phase") == "unrecorded"]
    rec = [q for q in dataset if q["type"] == "R5"
           and q["gold_expr"].get("phase") == "recorded"]
    check("未记探针题量", len(unrec), 4)
    check("已记探针题量", len(rec), 4)
    present = [q["qid"] for q in unrec if q["gold_expr"]["attr"] in corpus]
    check("未记属性在语料中出现次数", len(present), 0)

    # 7) 合成臂
    print("\n[7] 合成 recall 臂（perfect/adversarial/lexical）")
    fixtures = build_fixtures(tree, dataset)
    summaries = {name: sh.score_dataset(dataset, rows)
                 for name, rows in fixtures.items()}
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "h9-selftest-arms.json"), "w",
              encoding="utf-8") as f:
        json.dump({k: {"composite": v["composite_equal_weight"],
                       "class_scores": v["class_scores"],
                       "R3_stale_crown": v["types"]["R3"]["stale_crown_rate"]["point"],
                       "R6_retell_crown": v["types"]["R6"]["retell_crown_rate"]["point"],
                       "R6_evidence_first": v["types"]["R6"]["evidence_first"]["point"],
                       "R5_unrecorded_resist": v["types"]["R5"]["probe_unrecorded_resist"]["point"]}
                   for k, v in summaries.items()},
                  f, ensure_ascii=False, indent=2, sort_keys=True)

    # 8) 断言
    print("\n[8] 臂间区分度断言")
    perfect, adv, lex = summaries["perfect"], summaries["adversarial"], summaries["lexical"]
    check("perfect composite", perfect["composite_equal_weight"], 1.0)
    check("adversarial composite", adv["composite_equal_weight"], 0.0)
    comp_lex = lex["composite_equal_weight"]
    check("lexical composite 落在中间 (0.05, 0.95)",
          0.05 < comp_lex < 0.95, True)
    print(f"    (lexical composite = {comp_lex:.3f})")

    for t in hg.TYPES:
        check(f"perfect {t}", perfect["class_scores"][t], 1.0)
        check(f"adversarial {t}", adv["class_scores"][t], 0.0)

    # 霸榜率方向：perfect 应 0，adversarial 应 1
    check("perfect R3 stale_crown_rate", perfect["types"]["R3"]["stale_crown_rate"]["point"], 0.0)
    check("adversarial R3 stale_crown_rate", adv["types"]["R3"]["stale_crown_rate"]["point"], 1.0)
    check("perfect R6 retell_crown_rate", perfect["types"]["R6"]["retell_crown_rate"]["point"], 0.0)
    check("adversarial R6 retell_crown_rate", adv["types"]["R6"]["retell_crown_rate"]["point"], 1.0)
    check("perfect R5 probe_unrecorded_resist", perfect["types"]["R5"]["probe_unrecorded_resist"]["point"], 1.0)
    check("adversarial R5 probe_unrecorded_resist", adv["types"]["R5"]["probe_unrecorded_resist"]["point"], 0.0)

    # 词面臂方向性：转述口语同词 → retell_crown 应 ≥ evidence_first（复现 T6 的字面偏向）
    lex_r6 = lex["types"]["R6"]
    check("lexical R6 转述霸榜率 ≥ 实测优先率（字面偏向诊断）",
          (lex_r6["retell_crown_rate"]["point"] or 0) >= (lex_r6["evidence_first"]["point"] or 0), True)

    print()
    if FAILURES:
        print(f"[selftest] FAIL — {len(FAILURES)} 项")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("[selftest] PASS — 全部断言通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())

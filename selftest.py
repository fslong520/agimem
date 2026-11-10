#!/usr/bin/env python3
"""selftest.py — 不接真实 LLM / 不动真库，验证「生成 → 判分」链路自洽。

做什么：
  1) 调 gen_dataset 逻辑重算一遍数据集（或直接读已生成的 JSONL）；
  2) score.py --verify-only：证明每题 gold 可从树结构机械复算；
  3) 用合成 recall 输出造 5 个 fixture：
       perfect     —— 全对（系统完美）
       adversarial —— 全错（系统最差）
       mixed       —— 每题型前半对、后半错（验聚合口径）
       low_noise   —— 负样本命中但 score 很低（验 --min-score 闸）
       hand        —— 手工写死的小样本（人肉可核的期望值）
  4) 跑 score.py --json，逐条断言期望指标，全过才 exit 0。

用法： python3 selftest.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import causal_gold as cg  # noqa: E402

TREE = os.path.join(HERE, "data", "tree.json")
DATASET = os.path.join(HERE, "dataset", "causal_evalset.jsonl")
FIXDIR = os.path.join(HERE, "fixtures")

FAILURES: List[str] = []


def check(name: str, got: Any, want: Any, tol: float = 1e-9) -> None:
    if isinstance(want, float) and isinstance(got, (int, float)):
        ok = abs(float(got) - want) <= tol
    else:
        ok = got == want
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}: got={got} want={want}")
    if not ok:
        FAILURES.append(f"{name}: got={got} want={want}")


def run_score(predictions: str, extra: List[str]) -> Dict[str, Any]:
    cmd = [
        sys.executable, os.path.join(HERE, "score.py"),
        "--dataset", DATASET, "--tree", TREE,
        "--predictions", predictions, "--json",
    ] + extra
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(f"score.py 失败（exit {proc.returncode}）: {' '.join(cmd)}")
    return json.loads(proc.stdout)


def node_ids(tree: Dict[str, Any]) -> List[str]:
    return sorted(tree["_by_id"].keys())


def pick(tree: Dict[str, Any], ids: List[str], exclude: List[str], want_pitfall: bool) -> str:
    """从树里挑一个 id：要么是踩坑节点，要么不是；且不在 exclude 内。"""
    for nid in ids:
        n = tree["_by_id"][nid]
        if nid in exclude:
            continue
        if want_pitfall and n.get("outcome") == "pitfall":
            return nid
        if not want_pitfall and n.get("outcome") != "pitfall":
            return nid
    raise SystemExit("挑不到合适的 fixture 节点")


def build_fixtures(tree: Dict[str, Any], cases: List[Dict[str, Any]]) -> None:
    os.makedirs(FIXDIR, exist_ok=True)
    ids = node_ids(tree)

    def hit(nid: str, score: float, sup: str = "") -> Dict[str, Any]:
        return {"id": nid, "score": score, "superseded_by": sup or None}

    perfect: List[Dict[str, Any]] = []
    adversarial: List[Dict[str, Any]] = []
    low_noise: List[Dict[str, Any]] = []

    for c in cases:
        qtype, expr, expect = c["type"], c["gold_expr"], c.get("expect", [])

        # ---- perfect ----
        if qtype in (cg.CHAIN_ANCESTOR, cg.CHAIN_DESCENDANT):
            p_hits = [hit(e, 0.9 - 0.01 * i) for i, e in enumerate(expect)]
            a_hits = [hit(pick(tree, ids, expect, want_pitfall=False), 0.9)]
        elif qtype == cg.INTERVENTION:
            if c["label"] == "WARNING":
                p_hits = [hit(e, 0.9) for e in expect]          # 召回踩坑节点 → WARNING
                a_hits = [hit(pick(tree, ids, [], want_pitfall=False), 0.9)]  # 召回正常节点 → SAFE（错）
            else:
                # SAFE：召回该动作自己的正常节点，非踩坑 → 预测 SAFE
                safe_ids = sorted(
                    n["id"] for n in tree["_by_id"].values()
                    if n.get("action_key") == expr["action_key"]
                )
                p_hits = [hit(n, 0.8) for n in safe_ids]
                a_hits = [hit(pick(tree, ids, [], want_pitfall=True), 0.9)]  # 召回踩坑节点 → WARNING（错）
        elif qtype == cg.SUPERSESSION:
            cur = expect[0]
            old = expr["node"]
            p_hits = [hit(cur, 0.9)]                             # 召回当前有效结论
            a_hits = [hit(old, 0.9)]                             # 召回旧结论且无取代标记（stale）
        else:  # negative
            p_hits = []
            a_hits = [hit(ids[0], 0.9)]
            low_noise.append({"qid": c["qid"], "query": c["query"],
                              "hits": [hit(ids[0], 0.1)]})       # 低分命中，可被 min-score 挡掉

        perfect.append({"qid": c["qid"], "query": c["query"], "hits": p_hits})
        adversarial.append({"qid": c["qid"], "query": c["query"], "hits": a_hits})

    # ---- mixed：每题型按数据集顺序前半对、后半错 ----
    mixed: List[Dict[str, Any]] = []
    for qtype in cg.ALL_TYPES:
        same = [c for c in cases if c["type"] == qtype]
        half = len(same) // 2
        for idx, c in enumerate(same):
            src = perfect if idx < half else adversarial
            mixed.append(next(r for r in src if r["qid"] == c["qid"]))

    # ---- hand：手工写死、期望值人肉可核（从数据集里机械挑，不硬编码节点 id）----
    by_type = {t: [c for c in cases if c["type"] == t] for t in cg.ALL_TYPES}
    # 链前因题：挑 gold 链长 ≥3 的第一题（保证 coverage 分母非平凡）
    c_chain = next(c for c in by_type[cg.CHAIN_ANCESTOR] if len(c["expect"]) >= 3)
    # 干预题：gold=WARNING 的第一题
    c_interv = next(c for c in by_type[cg.INTERVENTION] if c["label"] == "WARNING")
    # 取代题：第一题
    c_super = by_type[cg.SUPERSESSION][0]
    c_neg = by_type[cg.NEGATIVE][0]
    # hand 里手写的召回 id 从 gold/树里取，保证在任何 seed 下都成立
    chain_gold = c_chain["expect"]                      # root 在前，不含自身
    hand_chain_hit = chain_gold[1] if len(chain_gold) >= 2 else chain_gold[0]
    interv_pit = c_interv["expect"][0]                  # WARNING 的踩坑节点
    super_old = c_super["gold_expr"]["node"]
    super_cur = c_super["expect"][0]
    hand = [
        # 命中 gold 第 2 项 + 一个无关 id → rank=0, coverage=1/len(gold)
        {"qid": c_chain["qid"], "query": c_chain["query"],
         "hits": [hit(hand_chain_hit, 0.7), hit("sntX9999", 0.2)]},
        # 召回踩坑节点 → 预测 WARNING = gold WARNING → 正确
        {"qid": c_interv["qid"], "query": c_interv["query"],
         "hits": [hit(interv_pit, 0.66)]},
        # 召回旧结论但带 superseded_by 标记 → 感知到取代 → 正确
        {"qid": c_super["qid"], "query": c_super["query"],
         "hits": [hit(super_old, 0.5, sup=super_cur)]},
        # 负样本空召回 → 无噪声
        {"qid": c_neg["qid"], "query": c_neg["query"], "hits": []},
    ]
    hand_expected_cov = 1.0 / len(chain_gold)

    for name, data in (("perfect", perfect), ("adversarial", adversarial),
                       ("mixed", mixed), ("low_noise", low_noise), ("hand", hand)):
        path = os.path.join(FIXDIR, f"{name}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for r in data:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"  fixture 写出 {os.path.relpath(path, HERE)}: {len(data)} 行")


def main() -> int:
    tree = cg.load_tree(TREE)
    with open(DATASET, "r", encoding="utf-8") as f:
        cases = [json.loads(x) for x in f if x.strip()]

    print("== 1) gold 机械复现对账 ==")
    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "score.py"), "--verify-only",
         "--dataset", DATASET, "--tree", TREE],
        capture_output=True, text=True, cwd=HERE)
    print("  " + (proc.stdout or proc.stderr).strip())
    check("verify-only exit", proc.returncode, 0)

    print("== 2) 生成合成 recall fixture ==")
    build_fixtures(tree, cases)

    # 题量与题型覆盖（验收标准②）
    print("== 3) 数据集规格 ==")
    check("题量 >= 120（T5 扩集验收）", len(cases) >= 120, True)
    counts = {t: sum(1 for c in cases if c["type"] == t) for t in cg.ALL_TYPES}
    n_chain = counts[cg.CHAIN_ANCESTOR] + counts[cg.CHAIN_DESCENDANT]
    check("链追溯 >= 60", n_chain >= 60, True)
    check("干预 >= 20", counts[cg.INTERVENTION] >= 20, True)
    check("取代 >= 10", counts[cg.SUPERSESSION] >= 10, True)
    check("负样本 >= 20", counts[cg.NEGATIVE] >= 20, True)
    types = {c["type"] for c in cases}
    for t in (cg.CHAIN_ANCESTOR, cg.INTERVENTION, cg.SUPERSESSION, cg.NEGATIVE):
        check(f"含题型 {t}", t in types, True)
    check("含负样本(expect 空)", sum(1 for c in cases if not c["expect"]) >= 1, True)

    print("== 4) perfect：全对系统 ==")
    m = run_score(os.path.join(FIXDIR, "perfect.jsonl"), [])
    s = m["summary"]
    check("链命中率 hit@5", s["chain"]["hit_at_k"], 1.0)
    check("链命中率 hit@1", s["chain"]["hit_at_1"], 1.0)
    check("链覆盖率", s["chain"]["coverage_at_k"], 1.0)
    check("预警准确率", s["intervention"]["accuracy"], 1.0)
    check("取代正确率", s["supersession"]["accuracy"], 1.0)
    check("负样本噪声率", s["negative"]["noise_rate"], 0.0)

    print("== 5) adversarial：全错系统 ==")
    m = run_score(os.path.join(FIXDIR, "adversarial.jsonl"), [])
    s = m["summary"]
    check("链命中率 hit@5", s["chain"]["hit_at_k"], 0.0)
    check("链覆盖率", s["chain"]["coverage_at_k"], 0.0)
    check("预警准确率", s["intervention"]["accuracy"], 0.0)
    check("取代正确率", s["supersession"]["accuracy"], 0.0)
    check("取代 stale 计数", s["supersession"]["stale"], s["supersession"]["n"])
    check("负样本噪声率", s["negative"]["noise_rate"], 1.0)

    print("== 6) mixed：每题型前半对后半错（验聚合口径） ==")
    m = run_score(os.path.join(FIXDIR, "mixed.jsonl"), [])
    s = m["summary"]
    n_chain, n_int, n_sup, n_neg = (s["chain"]["n"], s["intervention"]["n"],
                                    s["supersession"]["n"], s["negative"]["n"])
    check("链命中率 = floor(n/2)/n", s["chain"]["hit_at_k"], (n_chain // 2) / n_chain)
    check("预警准确率 = floor(n/2)/n", s["intervention"]["accuracy"], (n_int // 2) / n_int)
    check("取代正确率 = floor(n/2)/n", s["supersession"]["accuracy"], (n_sup // 2) / n_sup)
    check("负样本噪声率 = (n-floor(n/2))/n", s["negative"]["noise_rate"],
          (n_neg - n_neg // 2) / n_neg)

    print("== 7) min-score 闸：低分噪声应被挡掉 ==")
    m = run_score(os.path.join(FIXDIR, "low_noise.jsonl"), [])
    check("缺省 min_score=0 噪声率", m["summary"]["negative"]["noise_rate"], 1.0)
    m = run_score(os.path.join(FIXDIR, "low_noise.jsonl"), ["--min-score", "0.5"])
    check("min_score=0.5 噪声率", m["summary"]["negative"]["noise_rate"], 0.0)

    print("== 8) hand：手工小样本人肉可核（--partial 只判 4 条） ==")
    m = run_score(os.path.join(FIXDIR, "hand.jsonl"), ["--partial"])
    s = m["summary"]
    # 期望 coverage 从 hand fixture 第一行的 gold 机械推导（不硬编码 1/3）
    with open(os.path.join(FIXDIR, "hand.jsonl"), encoding="utf-8") as f:
        hand_rows = [json.loads(x) for x in f if x.strip()]
    hand_chain_qid = hand_rows[0]["qid"]
    hand_chain_row = next(r for r in m["rows"] if r["qid"] == hand_chain_qid)
    hand_expected_cov = 1.0 / max(1, len(hand_chain_row["gold"]))
    check("计分题数", s["scored"], 4)
    check("链命中率 hit@5", s["chain"]["hit_at_k"], 1.0)
    check("链覆盖率 = 1/len(gold)", s["chain"]["coverage_at_k"], hand_expected_cov)
    check("预警准确率", s["intervention"]["accuracy"], 1.0)
    check("取代正确率（经 superseded_by 标记）", s["supersession"]["accuracy"], 1.0)
    check("负样本噪声率", s["negative"]["noise_rate"], 0.0)
    check("缺预测题数（已剔除）", s["excluded_missing"], len(cases) - 4)

    print("== 9) hand 同集不加 --partial：缺预测必须按 0 分严判 ==")
    m = run_score(os.path.join(FIXDIR, "hand.jsonl"), [])
    s = m["summary"]
    check("计分题数 = 全集", s["scored"], len(cases))
    check("缺预测题数", s["excluded_missing"], len(cases) - 4)
    check("链命中率被拉低", s["chain"]["hit_at_k"] < 1.0, True)

    print("== 10) 抑制误报率（distractor）与两臂 Δ ==")
    m = run_score(os.path.join(FIXDIR, "perfect.jsonl"), [])
    check("perfect 抑制误报率", m["summary"]["intervention"]["false_alarm_rate"], 0.0)
    m = run_score(os.path.join(FIXDIR, "adversarial.jsonl"), [])
    check("adversarial 抑制误报率", m["summary"]["intervention"]["false_alarm_rate"], 1.0)
    m = run_score(os.path.join(FIXDIR, "perfect.jsonl"),
                  ["--delta", os.path.join(FIXDIR, "adversarial.jsonl")])
    d = m["summary"]["delta_vs"]["metrics"]
    check("Δ 链命中率（完美 − 最差）", d["chain_hit_at_k"], 1.0)
    check("Δ 预警准确率", d["intervention_acc"], 1.0)
    check("Δ 取代正确率", d["supersession_acc"], 1.0)
    check("Δ 负样本噪声率", d["negative_noise_rate"], -1.0)
    check("Δ 抑制误报率", d["false_alarm_rate"], -1.0)

    print()
    if FAILURES:
        print(f"SELFTEST FAIL — {len(FAILURES)} 项断言未过：")
        for x in FAILURES:
            print("  - " + x)
        return 1
    print("SELFTEST PASS — 生成 → gold 对账 → 判分 全链路自洽")
    return 0


if __name__ == "__main__":
    sys.exit(main())

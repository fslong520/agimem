#!/usr/bin/env python3
"""selftest_h6.py — H6 分水岭：生成 → gold 复算 → 判分 全链路自洽。

不接真实 LLM、不动真库。做七件事：
  1) gen_h6.py --verify：确定性重生成字节一致；
  2) score_h6.py --verify-only：141 题 gold 可从节点字段机械复算；
  3) 分类计数：P1–P5 各 24、P6 21，总 141；
  4) 诱饵「确未写入」断言：三个诱饵属性在全部正文/标题里 0 次出现；
  5) P5 四象限断言：II 晚 created 早插入、III 早 created 晚插入，且正文互异；
  6) 造合成 recall 臂（perfect / adversarial / lexical），证明判分有区分度；
  7) 逐条断言：perfect 六类全 1、adversarial 落底、词面臂落在中间。

用法： python3 selftest_h6.py
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

import gen_h6 as gh  # noqa: E402
import h6_gold as hg  # noqa: E402
import score_h6 as sh  # noqa: E402
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
    with open(os.path.join(HERE, "dataset", "h6_evalset.jsonl"), encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def load_tree() -> Dict[str, Any]:
    with open(os.path.join(HERE, "data", "h6_tree.json"), encoding="utf-8") as f:
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


def build_fixtures(tree: Dict[str, Any], questions: List[Dict[str, Any]]) -> None:
    os.makedirs(FIXDIR, exist_ok=True)
    by_id = {n["id"]: n for n in tree["nodes"]}

    perfect, adversarial, lexical = [], [], []
    for q in questions:
        expect = q["expect"]
        qtype = q["type"]
        expr = q["gold_expr"]
        kind = expr["kind"]

        if kind == "no_answer":
            # adversarial：把该实体硬凑成答案（正是诱饵要抓的行为）
            bad = [{"id": expr["entity"], "score": 0.9}]
        elif kind == "forget" and expr.get("phase") == "post":
            # adversarial：遗忘后仍把目标端出来
            bad = [{"id": expr["gold"], "score": 0.9}]
        elif kind == "order":
            # adversarial：跟插入顺序而不是 created_at（仅 before 题；earliest 题两者同答案）
            if expr.get("mode") == "before":
                bad = [{"id": expr["other"], "score": 0.9}]
            else:
                bad = [{"id": nid, "score": 0.9} for nid in sorted(by_id)
                       if nid not in expect][:1]
        elif kind == "source":
            bad = [{"id": i, "score": 0.9} for i in expr.get("other_sources", [])[:5]]
        elif kind == "gist":
            bad = [{"id": expr["decoy"], "score": 0.9}]
        else:
            # intent / recorded / forget-pre / order-earliest：随便一条非 gold
            bad = [{"id": nid, "score": 0.9} for nid in sorted(by_id) if nid not in expect][:1]

        if not bad:
            bad = [{"id": nid, "score": 0.9} for nid in sorted(by_id) if nid not in expect][:1]

        perfect.append({"qid": q["qid"], "query": q["query"],
                        "hits": [{"id": i, "score": 0.9 - 0.01 * j} for j, i in enumerate(expect)]
                        + [{"id": b["id"], "score": 0.3} for b in bad]})
        # 诱饵题的 perfect：top-1 不是该实体（正确行为是端不出东西）
        if kind == "no_answer":
            others = [nid for nid in sorted(by_id) if nid != expr["entity"]][:5]
            perfect[-1]["hits"] = [{"id": i, "score": 0.1} for i in others]
        # 遗忘后题的 perfect：目标消失，但邻居仍可被召回（collateral 不误伤）
        if kind == "forget" and expr.get("phase") == "post":
            keep = expr.get("keep", [])
            perfect[-1]["hits"] = [{"id": i, "score": 0.9 - 0.01 * j}
                                   for j, i in enumerate(keep)]
        adversarial.append({"qid": q["qid"], "query": q["query"], "hits": bad})

    nodes = list(by_id.values())
    for q in questions:
        lexical.append({"qid": q["qid"], "query": q["query"],
                        "hits": lexical_hits(q["query"], nodes, k=5)})

    for name, rows in (("h6-perfect", perfect), ("h6-adversarial", adversarial),
                       ("h6-lexical", lexical)):
        path = os.path.join(FIXDIR, f"{name}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    tree = load_tree()
    questions = load_dataset()

    # 1) 确定性重生成
    print("[selftest] 1) 确定性 --verify")
    rc = gh.verify_existing(gh.SEED, gh.PER_TYPE, gh.P6_PER_TYPE)
    check("gen_h6 --verify", rc, 0)

    # 2) gold 机械复算
    print("[selftest] 2) gold 机械复算")
    errs = hg.verify_gold(questions, tree["nodes"])
    check("gold 复算错误数", len(errs), 0)
    if errs:
        for e in errs[:8]:
            print("    -", e)

    # 3) 分类计数
    print("[selftest] 3) 分类计数")
    counts = {t: sum(1 for q in questions if q["type"] == t) for t in hg.TYPES}
    for t in hg.TYPES:
        # T32：P6 拆独立参数为 21（20%3≠0 不整除，21≥20）；P1–P5 仍 24
        want = gh.P6_PER_TYPE if t == "P6" else gh.PER_TYPE
        check(f"{t} 题量", counts[t], want)
    check("总题量", len(questions), 5 * gh.PER_TYPE + gh.P6_PER_TYPE)
    # 节点数：P6 扩到 21 后比原 24 少 1 次构造（P6 3 节点/次）→ 非固定值，改查下限
    if len(tree["nodes"]) < 270:
        check("节点数下限", len(tree["nodes"]), ">270")
    else:
        check("节点数下限", len(tree["nodes"]), len(tree["nodes"]))

    # 4) 诱饵「确未写入」
    print("[selftest] 4) 诱饵属性确未写入")
    corpus = "\n".join(n["title"] + "\n" + n["content"] for n in tree["nodes"])
    corpus_ns = corpus.replace(" ", "")
    for attr in scn.NEVER_RECORDED_ATTRS:
        hits = corpus_ns.count(attr.replace(" ", ""))
        check(f"诱饵属性 {attr} 出现次数", hits, 0)
    # 诱饵题本身也必须 expect 为空
    lure_qs = [q for q in questions if q["gold_expr"]["kind"] == "no_answer"]
    check("诱饵题数量", len(lure_qs), 12)
    check("诱饵题 expect 全空", all(not q["expect"] for q in lure_qs), True)

    # 5) P5 四象限
    print("[selftest] 5) P5 四象限十字交叉")
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for n in tree["nodes"]:
        if n["role"] == "order":
            groups.setdefault(n["topic"], []).append(n)
    check("P5 时序组数", len(groups), 12)
    cross_ok = True
    body_ok = True
    for topic, g in groups.items():
        quads = {n["attrs"]["quadrant"] for n in g}
        if quads != {"I", "II", "III", "IV"}:
            cross_ok = False
        ii = next(n for n in g if n["attrs"]["quadrant"] == "II")
        iii = next(n for n in g if n["attrs"]["quadrant"] == "III")
        if not (iii["created_at"] < ii["created_at"] and ii["insert_rank"] < iii["insert_rank"]):
            cross_ok = False
        if len({n["content"] for n in g}) != 4:
            body_ok = False
    check("II/III 十字交叉", cross_ok, True)
    check("四事件正文互异", body_ok, True)

    # 5b) T28 缺陷一：before 题面不得泄漏锚点原文连续 ≥3 字
    print("[selftest] 5b) before 题面无锚点原文泄漏")
    by_topic_nodes: Dict[str, List[Dict[str, Any]]] = {}
    for n in tree["nodes"]:
        if n["role"] == "order":
            by_topic_nodes.setdefault(n["topic"], []).append(n)
    before_qs = [q for q in questions
                 if q["type"] == "P5" and q.get("subtype") == "before"]
    check("before 题数量", len(before_qs), 12)
    leak_hits = []
    for q in before_qs:
        e = q["gold_expr"]
        anchor_n = next((n for n in by_topic_nodes.get(e["topic"], [])
                         if n["id"] == e.get("anchor")), None)
        if anchor_n is None:
            leak_hits.append((q["qid"], "anchor missing"))
            continue
        step = anchor_n["attrs"]["step"]
        cq = q["query"].replace(" ", "")
        step_c = step.replace(" ", "")
        for i in range(len(step_c) - 2):
            frag = step_c[i:i + 3]
            if frag and frag in cq:
                leak_hits.append((q["qid"], frag))
    check("before 题泄漏数（应 0）", len(leak_hits), 0)
    if leak_hits:
        for qid, frag in leak_hits[:5]:
            print(f"    - {qid} 泄漏 {frag!r}")
    # 负样本：故意塞回旧引号问法，断言必须拦住（证明断言真会失败）
    q0 = before_qs[0]
    anchor0 = next(n for n in by_topic_nodes[q0["gold_expr"]["topic"]]
                   if n["id"] == q0["gold_expr"]["anchor"])
    step0 = anchor0["attrs"]["step"]
    fake_query = f"在「{step0}」之前，上一步是什么？"
    cq0 = fake_query.replace(" ", "")
    caught = any(step0[i:i + 3].replace(" ", "") in cq0
                 for i in range(len(step0) - 2))
    check("负样本：旧引号问法应被 ≥3 字断言拦下", caught, True)

    # 6) 合成臂
    print("[selftest] 6) 合成 recall 臂")
    build_fixtures(tree, questions)

    def score_arm(name: str) -> Dict[str, Any]:
        path = os.path.join(FIXDIR, f"{name}.jsonl")
        preds = [json.loads(x) for x in open(path, encoding="utf-8") if x.strip()]
        return sh.score_dataset(questions, preds, tree["nodes"], topk=5)

    perfect = score_arm("h6-perfect")
    adversarial = score_arm("h6-adversarial")
    lexical = score_arm("h6-lexical")

    check("perfect 等权总分", round(perfect["composite_equal_weight"], 6), 1.0)
    check("adversarial 等权总分 < 0.3", adversarial["composite_equal_weight"] < 0.3, True)
    check("lexical 等权总分落在中间",
          0.05 < lexical["composite_equal_weight"] < 0.95, True)

    # 7) 分类断言
    print("[selftest] 7) 分类指标断言")
    check("perfect P1 intent_hit@1", perfect["types"]["P1"]["intent_hit@1"]["point"], 1.0)
    check("perfect P2 lure_false_hit", perfect["types"]["P2"]["lure_false_hit"]["point"], 1.0)
    check("perfect P2 know_auc", perfect["types"]["P2"]["know_auc"]["point"], 1.0)
    # forgotten_hit = 遗忘后目标仍被召回的比例（应 0）；target_gone_rate = 目标已消失（应 1）
    check("perfect P3 forgotten_hit（应 0，目标已消失）",
          perfect["types"]["P3"]["forgotten_hit"]["point"], 0.0)
    check("perfect P3 target_gone_rate（应 1）",
          perfect["types"]["P3"]["target_gone_rate"]["point"], 1.0)
    check("perfect P3 collateral_hit", perfect["types"]["P3"]["collateral_hit"]["point"], 1.0)
    check("perfect P4 source_hit@1", perfect["types"]["P4"]["source_attribution_hit@1"]["point"], 1.0)
    check("perfect P5 order_correct@1", perfect["types"]["P5"]["order_correct@1"]["point"], 1.0)
    check("perfect P6 gist/action/value 全 1",
          (perfect["types"]["P6"]["gist_hit@1"]["point"],
           perfect["types"]["P6"]["action_hit@1"]["point"],
           perfect["types"]["P6"]["value_hit@1"]["point"]),
          (1.0, 1.0, 1.0))
    # adversarial：P2 诱饵硬凑 → lure_false_hit=0（correct=未硬凑）
    check("adversarial P2 lure_false_hit", adversarial["types"]["P2"]["lure_false_hit"]["point"], 0.0)
    # adversarial：before 题跟插入顺序（错），earliest 题两者同答案（对）
    check("adversarial P5 order_correct@1 = 0.5（earliest 题两口径同答案）",
          adversarial["types"]["P5"]["order_correct@1"]["point"], 0.5)

    # 词面臂：P6 数值档应强于要旨档（字面检索的特征）
    lex_p6 = lexical["types"]["P6"]
    check("lexical P6 value_hit@1 ≥ gist_hit@1",
          (lex_p6["value_hit@1"]["point"] or 0) >= (lex_p6["gist_hit@1"]["point"] or 0), True)

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

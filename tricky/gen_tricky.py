#!/usr/bin/env python3
"""gen_tricky.py — H4「刁钻工作场景」层：确定性 seed 生成树与评测集，gold 机械推导。

用法：
    python3 gen_tricky.py                 # 写 data/tricky_tree.json + dataset/tricky_evalset.jsonl
    python3 gen_tricky.py --verify        # 重生成与既有文件比对（确定性证明）
    python3 gen_tricky.py --per-type 22   # 每类题量（缺省 22，6 类共 132）

流程：
  1. scenarios.py 的六个刁钻模板 × 八个真实工作场景 → 场景记录（Respire 三段式）；
  2. gold 一律调 tricky_gold.evaluate_expr 从节点字段机械推导（无人工答案）；
  3. 落盘时同时写 gold_expr，score_tricky.py --verify-only 可复算对账；
  4. 铁律守门：场景白名单、题面必须带场景标志词、禁科幻/纯数学/纯图案/纯抽象。

脱敏：全合成，无真人姓名（只用「同事甲/值班同学」）、无真库 id、无凭据。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
from typing import Any, Dict, List

import scenarios as scn
import tricky_gold as tg

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261109
PER_TYPE = 22
TREE_OUT = os.path.join(HERE, "data", "tricky_tree.json")
EVALSET_OUT = os.path.join(HERE, "dataset", "tricky_evalset.jsonl")

# 脱敏黑名单（合成语料不应命中）
BANNED_SNIPPETS = ["sk-", "password", "口令", "api key", "密钥串", "赵", "钱", "孙"]


def build(seed: int = SEED, per_type: int = PER_TYPE,
          id_offset: Dict[str, int] | None = None,
          qid_start: int = 1) -> Dict[str, Any]:
    rng = random.Random(seed)
    alloc = scn.Alloc()
    # 续写：节点号接在既有树各场景最大号之后，避免与旧 132 题的 trk id 相撞。
    if id_offset:
        for key, n in id_offset.items():
            alloc.n[key] = n
    nodes: List[Dict[str, Any]] = []
    questions: List[Dict[str, Any]] = []

    qi = 0  # 跨题型全局计数：让八场景在 132 题上尽量均分（铁律之外的可读性要求）
    for qtype in tg.ALL_TYPES:
        builder = scn.BUILDERS[qtype]
        for i in range(per_type):
            scenario = scn.SCENARIO_KEYS[qi % len(scn.SCENARIO_KEYS)]
            qi += 1
            recs, q = builder(rng, alloc, scenario, qid_start + i)
            nodes.extend(recs)
            q["qid"] = f"{qtype.lower()}-{qid_start + i:03d}"
            questions.append(q)

    tree = {
        "version": "1.0",
        "synthetic": True,
        "seed": seed,
        "generator": "gen_tricky.py",
        "scenario_whitelist": [scn.SCENARIOS[k]["name"] for k in scn.SCENARIO_KEYS],
        "note": ("全合成脱敏刁钻工作场景树：仅用于 agimem H4 类人记忆评测。"
                 "八个真实工作场景白名单，六类刁钻点。无真人姓名、无真库 id、无凭据。"),
        "nodes": nodes,
    }
    tree["_by_id"] = {n["id"]: n for n in nodes}
    # 生成期把 gold 机械推出来（与 score --verify-only 同一实现）
    for q in questions:
        gold = tg.evaluate_expr(tree, q["gold_expr"])
        q["expect"] = gold["expect"]
        q["label"] = gold["label"]
    del tree["_by_id"]
    return {"tree": tree, "questions": questions}


def sanity_checks(doc: Dict[str, Any], per_type: int) -> None:
    tree = doc["tree"]
    questions = doc["questions"]
    nodes = tree["nodes"]
    by_id = {n["id"]: n for n in nodes}

    # 1) 题量与分布
    # 下限按本次请求的题量：旧集 132（每类 22）与续写切片都要能过，不写死 120。
    if len(questions) != per_type * len(tg.ALL_TYPES):
        raise SystemExit(f"题量应为 {per_type * len(tg.ALL_TYPES)}: {len(questions)}")
    for t in tg.ALL_TYPES:
        n = sum(1 for q in questions if q["type"] == t)
        if n != per_type:
            raise SystemExit(f"{t} 题量应为 {per_type}，实为 {n}")

    # 2) 铁律：场景白名单 + 题面必须带该场景标志词 + 禁题材词
    whitelist = set(tree["scenario_whitelist"])
    for q in questions:
        key = q["scenario"]
        if key not in scn.SCENARIO_KEYS:
            raise SystemExit(f"{q['qid']}: 场景不在白名单 {key}")
        sc = scn.SCENARIOS[key]
        if sc["name"] not in whitelist:
            raise SystemExit(f"{q['qid']}: 场景名不在白名单 {sc['name']}")
        if not any(m in q["query"] for m in sc["mark"]):
            raise SystemExit(f"{q['qid']}: 题面缺少场景标志词 {sc['mark']}: {q['query'][:40]}")
        for bad in scn.BANNED_TOPICS:
            if bad in q["query"]:
                raise SystemExit(f"{q['qid']}: 题面命中被禁题材词 {bad!r}")

    # 3) gold 可机械复现 + expect 都在树内 + 唯一
    verifier = dict(tree)
    verifier["_by_id"] = by_id
    for q in questions:
        gold = tg.evaluate_expr(verifier, q["gold_expr"])
        if list(gold["expect"]) != list(q["expect"]):
            raise SystemExit(f"{q['qid']}: expect 与重算不一致 {gold['expect']} vs {q['expect']}")
        if not q["expect"]:
            raise SystemExit(f"{q['qid']}: gold 为空")
        for e in q["expect"]:
            if e not in by_id:
                raise SystemExit(f"{q['qid']}: expect 不在树内 {e}")

    # 4) 去重：题面唯一；节点 id 唯一且前缀与主树 snt… 不相交
    queries = [q["query"] for q in questions]
    if len(queries) != len(set(queries)):
        dup = [x for x in queries if queries.count(x) > 1][:2]
        raise SystemExit(f"题面重复: {dup}")
    ids = [n["id"] for n in nodes]
    if len(ids) != len(set(ids)):
        raise SystemExit("节点 id 重复")
    for nid in ids:
        if not nid.startswith("trk"):
            raise SystemExit(f"节点 id 前缀异常（不得与主树 snt 相交）: {nid}")

    # 5) 脱敏：黑名单 + UUID 形态
    blob = json.dumps(doc, ensure_ascii=False)
    for b in BANNED_SNIPPETS:
        if b in blob:
            raise SystemExit(f"脱敏自检失败：命中疑似敏感片段 {b!r}")
    import re
    if re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", blob):
        raise SystemExit("脱敏自检失败：命中 UUID 形态")


def dump(doc: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(TREE_OUT), exist_ok=True)
    os.makedirs(os.path.dirname(EVALSET_OUT), exist_ok=True)
    with open(TREE_OUT, "w", encoding="utf-8") as f:
        json.dump(doc["tree"], f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(EVALSET_OUT, "w", encoding="utf-8") as f:
        for q in doc["questions"]:
            f.write(json.dumps(q, ensure_ascii=False, sort_keys=True) + "\n")


def digest(doc: Dict[str, Any]) -> str:
    payload = json.dumps({"tree": doc["tree"], "questions": doc["questions"]},
                         ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def verify_existing(seed: int, per_type: int) -> int:
    fresh = build(seed, per_type)
    sanity_checks(fresh, per_type)
    if not (os.path.exists(TREE_OUT) and os.path.exists(EVALSET_OUT)):
        print(f"[verify] FAIL — 缺 {TREE_OUT} 或 {EVALSET_OUT}，先跑 gen_tricky.py")
        return 1
    with open(TREE_OUT, encoding="utf-8") as f:
        tree = json.load(f)
    with open(EVALSET_OUT, encoding="utf-8") as f:
        questions = [json.loads(x) for x in f if x.strip()]
    ok = True
    if json.dumps(tree, ensure_ascii=False, sort_keys=True) != \
       json.dumps(fresh["tree"], ensure_ascii=False, sort_keys=True):
        print("[verify] FAIL — data/tricky_tree.json 与 seed 重生成不一致")
        ok = False
    if json.dumps(questions, ensure_ascii=False, sort_keys=True) != \
       json.dumps(fresh["questions"], ensure_ascii=False, sort_keys=True):
        print("[verify] FAIL — dataset/tricky_evalset.jsonl 与 seed 重生成不一致")
        ok = False
    if ok:
        print(f"[verify] OK — seed={seed} per_type={per_type} 重生成与落盘一致"
              f"（digest={digest(fresh)}，{len(tree['nodes'])} 节点 / {len(questions)} 题）")
        return 0
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="H4 刁钻工作场景：确定性生成")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--per-type", type=int, default=PER_TYPE)
    ap.add_argument("--verify", action="store_true", help="重生成与既有文件比对")
    ap.add_argument("--extend", action="store_true",
                    help="在既有 132 题之后续写同等题量，落到 *_v2，不覆盖旧题")
    args = ap.parse_args()

    if args.verify:
        return verify_existing(args.seed, args.per_type)

    id_offset = None
    qid_start = 1
    tree_out, eval_out = TREE_OUT, EVALSET_OUT
    if args.extend:
        with open(TREE_OUT, encoding="utf-8") as f:
            base_tree = json.load(f)
        with open(EVALSET_OUT, encoding="utf-8") as f:
            base_qs = [json.loads(x) for x in f if x.strip()]
        id_offset = {}
        for n in base_tree["nodes"]:
            key = n["scenario"]
            num = int(n["id"][4:])
            id_offset[key] = max(id_offset.get(key, 0), num)
        # 每类既有题号的最大值 + 1，六类必须对齐（旧集每类 22 → 从 023 起）。
        starts = {}
        for q in base_qs:
            starts[q["type"]] = max(starts.get(q["type"], 0), int(q["qid"].split("-")[1]))
        if len(set(starts.values())) != 1:
            raise SystemExit(f"既有题号不齐，不能续写: {starts}")
        qid_start = next(iter(starts.values())) + 1
        tree_out = os.path.join(HERE, "data", "tricky_tree_v2.json")
        eval_out = os.path.join(HERE, "dataset", "tricky_evalset_v2.jsonl")

    doc = build(args.seed, args.per_type, id_offset, qid_start)
    if args.extend:
        doc["tree"]["seed"] = args.seed
        doc["tree"]["note"] = (
            "T25 续写切片：seed 与旧 132 题不同，节点号接在既有树之后。"
            "与 data/tricky_tree.json 合并才是 264 题的完整树；本文件不含旧题。"
        )
        doc["tree"]["continues"] = "data/tricky_tree.json"
        for q in doc["questions"]:
            q["origin"] = "v2"
    sanity_checks(doc, args.per_type)
    # 续写不走 dump()，避免覆盖旧 132 题。
    if args.extend:
        os.makedirs(os.path.dirname(tree_out), exist_ok=True)
        with open(tree_out, "w", encoding="utf-8") as f:
            json.dump(doc["tree"], f, ensure_ascii=False, indent=2)
            f.write("\n")
        with open(eval_out, "w", encoding="utf-8") as f:
            for q in doc["questions"]:
                f.write(json.dumps(q, ensure_ascii=False, sort_keys=True) + "\n")
        doc["_outs"] = (tree_out, eval_out)
    else:
        dump(doc)
    counts: Dict[str, int] = {}
    for q in doc["questions"]:
        counts[q["type"]] = counts.get(q["type"], 0) + 1
    scen_counts: Dict[str, int] = {}
    for q in doc["questions"]:
        scen_counts[q["scenario"]] = scen_counts.get(q["scenario"], 0) + 1
    tree_rel, eval_rel = doc.get("_outs", (TREE_OUT, EVALSET_OUT))
    print(f"[gen_tricky] 写出 {os.path.relpath(tree_rel, HERE)}: "
          f"{len(doc['tree']['nodes'])} 节点 / 8 场景白名单")
    print(f"[gen_tricky] 写出 {os.path.relpath(eval_rel, HERE)}: "
          f"{len(doc['questions'])} 题 (seed={args.seed}, digest={digest(doc)})")
    for t in tg.ALL_TYPES:
        print(f"  - {t} {tg.TYPE_NAMES[t]}: {counts.get(t, 0)}")
    print("  - 场景分布: " + " | ".join(
        f"{scn.SCENARIOS[k]['name']}={scen_counts.get(k, 0)}" for k in scn.SCENARIO_KEYS))
    print("[gen_tricky] 铁律守门通过（场景白名单/题面标志词/禁题材词）；gold 机械复算一致；脱敏自检通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())

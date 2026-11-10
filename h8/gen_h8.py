#!/usr/bin/env python3
"""gen_h8.py — H8「记忆动力学层」：确定性 seed 生成语料与评测集，gold 机械推导。

用法：
    python3 gen_h8.py                 # 写 data/h8_tree.json + dataset/h8_evalset.jsonl
    python3 gen_h8.py --verify        # 重生成与既有文件比对（确定性证明）
    python3 gen_h8.py --c1 16 --c2 16 --c3 16 --c4 16   # 每子类题量（缺省共 64）

四子类（记忆动力学：时间维度上记忆的形成、沉睡、浮出与被改写）：
  C1 一次观察泛化  一条观察记录 → 同一规则施于新实例；**题面故意词面错位**（与观察正文连续
                   重合 <6 字，verify_gold 强制），直接打在 m3 字面检索边界上。
  C2 跨间隔召回    1h/1d/7d/30d 陈化曲线：用条目 created_at 的时间跨度构造「老条目」，
                   不真等时间；正向断言「老条目召回率不为 0」。
  C3 远期检索      强化事件 vs 平凡日常 vs 灰尘池 → 「不被淹没率」；灰尘池=同 topic 平凡条目。
  C4 增量编辑      同一规则改 N 次答「现在是什么」，测认最新版还是按 superseded_by；
                   顺带复现「排序不用取代标记」缺口（旧条目霸榜率）。

铁律守门（生成期强制，不是声明；记忆 cdf155a9）：场景 ∈ 八场景白名单、题面含该场景标志词、
不命中禁题材词。脱敏：全合成，无真人姓名（只用「同事甲/同事乙」）、无真库 id、无凭据。
本轮**不跑分**（不调真库 recall），只落 gold 与判分链。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
from typing import Any, Dict, List, Tuple

import h8_gold as hg
import scenarios as scn

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261110
C1_N = 16
C2_N = 16
C3_N = 16
C4_N = 16
TREE_OUT = os.path.join(HERE, "data", "h8_tree.json")
EVALSET_OUT = os.path.join(HERE, "dataset", "h8_evalset.jsonl")

BANNED_SNIPPETS = ["sk-", "password", "口令", "api key", "密钥串", "赵", "钱", "孙"]
UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

# C1 观察正文模板（独立句式；题面不复述它）。
# 内容 = 一条「值班/发布里观察到的规矩」，规则本身写死在 content 里。
C1_OBS = [
    ("收口一律按发布单上的回滚点走", "回滚点"),
    ("发版前先看健康检查绿没绿", "健康检查"),
    ("联调先对签名再对字段", "签名"),
    ("交接先点名当班再看告警", "当班"),
    ("统计口径以自然周为准", "自然周"),
    ("回灌前先抽样比对", "抽样比对"),
    ("授权到期前 2 天续", "续期"),
    ("回滚到上一个稳定版本", "稳定版本"),
]
# C1 泛化题面模板（给新实例的口语描述，**不复述规则原文**）。
# 红线（H8 verify_gold 强制）：题面与观察正文连续重合 <6 字。
# 模板不得直接拼「{comp} + 场景句式」——那会与正文「同批的{comp}都照这条处理」撞出 ≥6 字连续段
# （实测 q007「新来的历史订单表照老规矩处理」撞出 6 字）。故模板只用独立口语引出语。
C1_Q_TPL = [
    "换谁接都按老法子来着？",
    "下一家碰上一样的坎，规矩还作数吗，怎么走？",
    "这回是新面孔，头一步该干啥？",
    "那套还作数不作数，还按老路走吗？",
]

# C2 每档年龄的题面（问「当时定的是哪条」）
C2_Q_TPL = [
    "那会儿定的{attr}是哪条？",
    "翻回{age}前的记录，当时怎么定的{attr}？",
    "上次聊{attr}的时候定成什么了？",
]

# C3 尘池平凡条目模板（同 topic、同词面近似、量大）
C3_DUST_TPL = [
    "例行巡检：{comp} 状态正常",
    "例行巡检：{comp} 无告警",
    "例行记录：{comp} 指标平稳",
    "例行记录：{comp} 无变更",
]

# C4 改版历史：三版规则正文（v1 初版 / v2 改 / v3 现行）
C4_VERSIONS = [
    ["回滚点先看发布单", "健康检查绿了才发", "联调先对签名"],
    ["回滚点改看当周值班手册", "健康检查加看错误率", "联调先对字段"],
    ["回滚点只认当周值班手册第 3 条", "健康检查绿且错误率稳", "联调先对字段再对签名"],
]


def _mark(sc: Dict[str, Any]) -> str:
    return sc["mark"][0]


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


# ---------------------------------------------------------------- C1 一次观察泛化

def build_c1(rng: random.Random, alloc: scn.Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """一条观察记录（规则写死在正文）+ 一题泛化到新实例（题面词面错位）。"""
    sc = scn.SCENARIOS[scenario]
    comp = sc["components"][idx % len(sc["components"])]
    obs_text, rule_attr = C1_OBS[idx % len(C1_OBS)]
    nid = alloc.node_id(scenario)
    content = scn.tpl(
        f"值班时观察到：{obs_text}",
        f"同批的{comp}都照这条处理",
        "沉淀成一条可复用的规矩",
    )
    obs = scn.node(
        scenario, nid,
        f"观察记录第 {idx + 1} 号：{obs_text}",
        content,
        ts=f"2026-09-{(idx % 27) + 1:02d}",
        created_at=f"2026-09-{(idx % 27) + 1:02d}T10:00:00Z",
        insert_rank=6000 + idx,
        role="observe",
        topic=f"c1-{scenario}-{idx}",
        attrs={"rule": obs_text, "attr": rule_attr, "comp": comp},
    )
    # 题面：只给新实例的口语描述 + 场景标志词；不复述 obs_text
    # 第 {no} 号让题面跨条互异（同场景同模板轮换时防撞车）
    qtpl = C1_Q_TPL[idx % len(C1_Q_TPL)]
    query = qtpl.format(comp=comp)
    query = f"（第 {idx + 1} 号观察）{query}"
    mark = _mark(sc)
    if not any(m in query for m in sc["mark"]):
        query = f"{mark}那次，{comp}那边——{query}"
    q = {
        "type": "C1", "scenario": scenario, "subtype": "generalize",
        "query": query,
        "gold_expr": {"kind": "generalize", "gold": nid,
                      "rule_attr": rule_attr, "comp": comp},
        "expect": [nid],
        "note": "一次观察 → 同规则施于新实例；题面词面错位（<6 字），测检索与泛化分界",
    }
    return [obs], [q]


# ---------------------------------------------------------------- C2 跨间隔召回

def build_c2(rng: random.Random, alloc: scn.Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """每档年龄一条老条目（created_at 按时间跨度回拨）+ 一题问「当时定的是哪条」。

    模拟办法：不真等时间，用 created_at 的时间跨度构造老条目（1h/1d/7d/30d 前）。
    gold = 该老条目（正向断言「老条目召回率不为 0」）。
    """
    sc = scn.SCENARIOS[scenario]
    comp = sc["components"][idx % len(sc["components"])]
    age = scn.C2_AGES[idx % len(scn.C2_AGES)]
    today, past = scn.C2_AGE_OFFSET[age]
    attr = sc["params"][idx % len(sc["params"])]
    value = sc["values"][idx % len(sc["values"])]
    nid = alloc.node_id(scenario)
    content = scn.tpl(
        f"{age}前那次{comp}上，{attr}定为 {value}",
        "记录已归档",
        "当时没改，沿用至今",
    )
    # 1h 档的 past 已含时刻（T08:00:00Z），其余档只到日期 → 拼时刻前先判断
    created_at = past if "T" in past else f"{past}T10:00:00Z"
    entry = scn.node(
        scenario, nid,
        f"{age}前的{attr}约定（{comp}）",
        content,
        ts=past.split("T")[0],
        created_at=created_at,
        insert_rank=7000 + idx,
        role="aged",
        topic=f"c2-{scenario}-{idx}",
        attrs={"age": age, "attr": attr, "value": value, "comp": comp},
    )
    qtpl = C2_Q_TPL[idx % len(C2_Q_TPL)]
    query = qtpl.format(age=age, attr=attr)
    mark = _mark(sc)
    if not any(m in query for m in sc["mark"]):
        query = f"{mark}那次，{comp}那边——{query}"
    q = {
        "type": "C2", "scenario": scenario, "subtype": f"age-{age}",
        "query": query,
        "gold_expr": {"kind": "aged", "gold": nid, "age": age,
                      "attr": attr, "value": value, "created_at": entry["created_at"]},
        "expect": [nid],
        "note": f"跨间隔 {age}：老条目（created_at 回拨）召回；正向断言不为 0",
    }
    return [entry], [q]


# ---------------------------------------------------------------- C3 远期检索

def build_c3(rng: random.Random, alloc: scn.Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """强化事件 + 平凡日常 + 灰尘池（同 topic 大量平凡条目），测强化件不被淹没。

    灰尘池：每个主题 5 条平凡巡检记录（同 topic、同词面近似）；强化件 1 条、平凡 1 条。
    gold = 强化件；指标 = 不被淹没率（强化件在 top-k 内）。
    """
    sc = scn.SCENARIOS[scenario]
    comp = sc["components"][idx % len(sc["components"])]
    topic = f"c3-{scenario}-{idx}"
    salient_id = ""
    nodes: List[Dict[str, Any]] = []
    # 灰尘池（先建，排在前面，制造「被淹没」的物理条件）
    for j in range(5):
        nid = alloc.node_id(scenario)
        body = C3_DUST_TPL[j % len(C3_DUST_TPL)].format(comp=comp)
        nodes.append(scn.node(
            scenario, nid, f"平凡巡检记录第 {j + 1} 号：{comp}",
            scn.tpl(f"例行记录：{body}", "无异常", "无需处理"),
            ts="2026-10-01", created_at="2026-10-01T10:00:00Z",
            insert_rank=8000 + idx * 10 + j,
            role="dust", topic=topic,
            attrs={"pool": "dust", "comp": comp},
        ))
    # 平凡日常 1 条
    nid = alloc.node_id(scenario)
    nodes.append(scn.node(
        scenario, nid, f"日常记录：{comp} 每日照常",
        scn.tpl(f"{comp} 每日照常运行", "无变更", "维持现状"),
        ts="2026-10-02", created_at="2026-10-02T10:00:00Z",
        insert_rank=8000 + idx * 10 + 6,
        role="plain", topic=topic,
        attrs={"pool": "plain", "comp": comp},
    ))
    # 强化事件 1 条
    salient_id = alloc.node_id(scenario)
    nodes.append(scn.node(
        scenario, salient_id, f"强化事件：{comp} 那次大变更",
        scn.tpl(f"{comp} 那次大变更：{_mark(sc)}后停服 40 分钟", "影响全量用户", "定为 P1 故障"),
        ts="2026-10-03", created_at="2026-10-03T10:00:00Z",
        insert_rank=8000 + idx * 10 + 7,
        role="salient", topic=topic,
        attrs={"pool": "salient", "comp": comp},
    ))
    query = f"（第 {idx + 1} 号）{comp}那次大变更，影响到什么程度，最后定成什么？"
    mark = _mark(sc)
    if not any(m in query for m in sc["mark"]):
        query = f"{mark}那次，{comp}那边——{query}"
    q = {
        "type": "C3", "scenario": scenario, "subtype": "salience",
        "query": query,
        "gold_expr": {"kind": "salience", "gold": salient_id,
                      "pool_sizes": {"dust": 5, "plain": 1, "salient": 1}},
        "expect": [salient_id],
        "note": "远期检索：强化件 vs 平凡 vs 灰尘池（同 topic 5 条），测不被淹没率",
    }
    return nodes, [q]


# ---------------------------------------------------------------- C4 增量编辑

def build_c4(rng: random.Random, alloc: scn.Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """同一规则改 C4_EDIT_STEPS 版（v1→v2→v3），答「现在是什么」。

    gold = 最后一版；旧版带 `superseded_by` 指向新版（由生成器种入）。
    指标：认最新版率 + 旧条目霸榜率（复现「排序不用取代标记」缺口）。
    """
    sc = scn.SCENARIOS[scenario]
    comp = sc["components"][idx % len(sc["components"])]
    mark = _mark(sc)
    topic = f"c4-{scenario}-{idx}"
    prev_id = ""
    version_ids: List[str] = []
    nodes: List[Dict[str, Any]] = []
    for v, rule in enumerate(C4_VERSIONS):
        nid = alloc.node_id(scenario)
        created = f"2026-{6 + v:02d}-{(idx % 27) + 1:02d}T10:00:00Z"
        content = scn.tpl(
            f"{comp} 这次{mark}，{rule}（第 {v + 1} 版）",
            f"改版由{'同事甲' if v else '同事乙'}提出",
            "作为当前生效口径挂起",
        )
        node = scn.node(
            scenario, nid,
            f"{comp}{mark}口径第 {v + 1} 版：{rule}",
            content,
            ts=f"2026-{6 + v:02d}-{(idx % 27) + 1:02d}",
            created_at=created,
            insert_rank=9000 + idx * 10 + v,
            role="rule_version",
            topic=topic,
            parent=prev_id,
            attrs={"version": v + 1, "rule": rule, "comp": comp},
        )
        if prev_id:
            # 取代边：旧 → 新（生成器显式种入，oracle 口径）
            for n in nodes:
                if n["id"] == prev_id:
                    n["superseded_by"] = nid
                    break
        else:
            node["superseded_by"] = ""
        node.setdefault("superseded_by", "")
        nodes.append(node)
        version_ids.append(nid)
        prev_id = nid
    current_id = version_ids[-1]
    query = f"（第 {idx + 1} 号议题）关于{comp}的{mark}口径，现在生效的是哪条？"
    q = {
        "type": "C4", "scenario": scenario, "subtype": f"edits{len(C4_VERSIONS)}",
        "query": query,
        "gold_expr": {"kind": "edited", "gold": current_id,
                      "version_ids": version_ids,
                      "old_ids": version_ids[:-1],
                      "steps": len(C4_VERSIONS)},
        "expect": [current_id],
        "note": "增量编辑：改 N 次答「现在是什么」，测认最新版 vs 旧条目霸榜",
    }
    return nodes, [q]


# ---------------------------------------------------------------- 组装

def build(seed: int = SEED, c1: int = C1_N, c2: int = C2_N,
          c3: int = C3_N, c4: int = C4_N) -> Dict[str, Any]:
    rng = random.Random(seed)
    alloc = scn.Alloc()
    nodes: List[Dict[str, Any]] = []
    questions: List[Dict[str, Any]] = []

    # 全局序号（跨子类错开场景与模板轮换，防题面重复）
    gi = 0

    def collect(fn, n):
        nonlocal gi
        for i in range(n):
            scenario = scn.SCENARIO_KEYS[gi % len(scn.SCENARIO_KEYS)]
            ns, qs = fn(rng, alloc, scenario, i)
            nodes.extend(ns)
            questions.extend(qs)
            gi += 1

    collect(build_c1, c1)
    collect(build_c2, c2)
    collect(build_c3, c3)
    collect(build_c4, c4)

    for i, q in enumerate(questions, 1):
        q["qid"] = f"q{i:03d}"

    doc = {
        "schema": "agimem-h8/1",
        "synthetic": True,
        "seed": seed,
        "generator": "gen_h8.py",
        "scenario_whitelist": [scn.SCENARIOS[k]["name"] for k in scn.SCENARIO_KEYS],
        "tree": {"nodes": nodes},
        "questions": questions,
        "counts": {"C1": c1, "C2": c2, "C3": c3, "C4": c4},
    }
    sanity_checks(doc, c1, c2, c3, c4)
    return doc


def sanity_checks(doc: Dict[str, Any], c1: int, c2: int, c3: int, c4: int) -> None:
    tree = doc["tree"]
    questions = doc["questions"]
    nodes = tree["nodes"]
    by_id = {n["id"]: n for n in nodes}

    if len(questions) < 64:
        raise SystemExit(f"总题量不足 64: {len(questions)}")
    for t in hg.TYPES:
        n = sum(1 for q in questions if q["type"] == t)
        want = {"C1": c1, "C2": c2, "C3": c3, "C4": c4}[t]
        if n < 16 or n != want:
            raise SystemExit(f"{t} 题量应为 {want}（且 ≥16），实为 {n}")

    qseen: Dict[str, str] = {}
    for q in questions:
        if q["query"] in qseen:
            raise SystemExit(f"题面重复: {q['qid']} 与 {qseen[q['query']]}")
        qseen[q["query"]] = q["qid"]

    # 铁律三道：场景白名单、题面含场景标志词、不命中禁题材词
    for q in questions:
        key = q["scenario"]
        if key not in scn.SCENARIO_KEYS:
            raise SystemExit(f"{q['qid']}: 场景不在白名单 {key}")
        sc = scn.SCENARIOS[key]
        if not any(m in q["query"] for m in sc["mark"]):
            raise SystemExit(f"{q['qid']}: 题面缺少场景标志词 {sc['mark']}: {q['query'][:48]}")
        for bad in scn.BANNED_TOPICS:
            if bad in q["query"]:
                raise SystemExit(f"{q['qid']}: 题面命中被禁题材词 {bad!r}")

    # C2 四档年龄齐备
    ages = {q["subtype"] for q in questions if q["type"] == "C2"}
    if ages != {f"age-{a}" for a in scn.C2_AGES}:
        raise SystemExit(f"C2 年龄档不齐: {ages}")

    # C4 版本数齐备
    steps = {q["gold_expr"]["steps"] for q in questions if q["type"] == "C4"}
    if steps != {len(C4_VERSIONS)}:
        raise SystemExit(f"C4 改版步数不齐: {steps}")

    # gold 可机械复算
    errs = hg.verify_gold(questions, nodes)
    if errs:
        raise SystemExit("gold 复算失败:\n  - " + "\n  - ".join(errs[:12]))

    # expect 与 gold_expr 一致
    for q in questions:
        if q["expect"] != [q["gold_expr"]["gold"]]:
            raise SystemExit(f"{q['qid']}: expect 与 gold 不一致")
        if q["gold_expr"]["gold"] not in by_id:
            raise SystemExit(f"{q['qid']}: gold 不在树内")

    # 脱敏自检
    for n in nodes:
        if UUID_RE.search(n["content"]):
            raise SystemExit(f"节点 {n['id']} 含 UUID")
        for b in BANNED_SNIPPETS:
            if b in n["content"]:
                raise SystemExit(f"节点 {n['id']} 含禁片段 {b!r}")


def dump(doc: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(TREE_OUT), exist_ok=True)
    os.makedirs(os.path.dirname(EVALSET_OUT), exist_ok=True)
    tree = {"schema": doc["schema"], "synthetic": True, "seed": doc["seed"],
            "generator": doc["generator"], "scenario_whitelist": doc["scenario_whitelist"],
            "nodes": doc["tree"]["nodes"]}
    with open(TREE_OUT, "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open(EVALSET_OUT, "w", encoding="utf-8") as f:
        for q in doc["questions"]:
            f.write(json.dumps(q, ensure_ascii=False, sort_keys=True) + "\n")


def digest(doc: Dict[str, Any]) -> str:
    payload = json.dumps(doc["questions"], ensure_ascii=False, sort_keys=True).encode()
    payload += json.dumps(doc["tree"], ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def verify_existing(seed: int, c1: int, c2: int, c3: int, c4: int) -> int:
    if not (os.path.exists(TREE_OUT) and os.path.exists(EVALSET_OUT)):
        print(f"[verify] FAIL — 缺 {TREE_OUT} 或 {EVALSET_OUT}，先跑 gen_h8.py")
        return 1
    fresh = build(seed, c1, c2, c3, c4)
    with open(TREE_OUT, encoding="utf-8") as f:
        tree = json.load(f)
    questions = load_jsonl(EVALSET_OUT)
    if tree["nodes"] != fresh["tree"]["nodes"]:
        print("[verify] FAIL — data/h8_tree.json 与 seed 重生成不一致")
        return 1
    if questions != fresh["questions"]:
        print("[verify] FAIL — dataset/h8_evalset.jsonl 与 seed 重生成不一致")
        return 1
    print(f"[verify] OK — seed={seed} 重生成与落盘一致"
          f"（digest={digest(fresh)}，{len(tree['nodes'])} 节点 / {len(questions)} 题）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="H8 四子类生成器")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--c1", type=int, default=C1_N)
    ap.add_argument("--c2", type=int, default=C2_N)
    ap.add_argument("--c3", type=int, default=C3_N)
    ap.add_argument("--c4", type=int, default=C4_N)
    ap.add_argument("--verify", action="store_true", help="重生成与既有文件比对")
    args = ap.parse_args()
    if args.verify:
        return verify_existing(args.seed, args.c1, args.c2, args.c3, args.c4)

    doc = build(args.seed, args.c1, args.c2, args.c3, args.c4)
    dump(doc)
    print(f"[gen_h8] 写出 {os.path.relpath(TREE_OUT, HERE)} + "
          f"{os.path.relpath(EVALSET_OUT, HERE)} "
          f"(seed={args.seed}, digest={digest(doc)})")
    print(f"[gen_h8] {len(doc['tree']['nodes'])} 节点 / {len(doc['questions'])} 题；"
          f"counts={doc['counts']}")
    print("[gen_h8] 铁律守门通过；gold 机械复算一致；词面错位；脱敏自检通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())

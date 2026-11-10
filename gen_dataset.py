#!/usr/bin/env python3
"""gen_dataset.py — 从合成因果树机械生成 agimem 评测集（≥120 题扩集版）。

用法：
    python3 gen_dataset.py --tree data/tree.json --out dataset/causal_evalset.jsonl

流程（causal-memory「树 → 对话 → gold」思路的 Respire 适配版）：
  1. 读 data/tree.json（三段式【前因】【行为】【后果】+ parent_id + outcome +
     action_key + superseded_by；由 gen_tree.py 以确定性 seed 生成）；
  2. 按题型配额从树里**确定性选题**（seed 决定打乱顺序，无硬编码节点 id）；
  3. gold 一律调 causal_gold.evaluate_expr 从树结构推导，不写任何人工答案；
  4. 每行同时落 gold_expr（推导表达式），供 score.py --verify 复算对账。

题型配额（2026-11-09 T5 扩集，目标 ≥120 题）：
  chain_ancestor 34 + chain_descendant 34 = 链追溯 68（≥60）
  intervention 20（踩坑 10 + 正常 10，≥20）
  supersession 10（≥10）
  negative 24（≥20）
  合计 122 题；n=122 时单题权重 ≤0.82pp（26 题时 1 条≈3.8pp 不足以看趋势）。

脱敏红线（继承 respire-benchmark README「安全」节）：
  全合成；不含真人姓名、真库 id、query-log 编号、凭据；noise 关键词必须
  与树内任何 title/content 互斥（生成时断言）。
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from typing import Any, Dict, List

import causal_gold as cg

# 题型产出顺序（保证生成结果确定性）
TYPE_ORDER = [
    cg.CHAIN_ANCESTOR,
    cg.CHAIN_DESCENDANT,
    cg.INTERVENTION,
    cg.SUPERSESSION,
    cg.NEGATIVE,
]

# 题型配额（T5 扩集验收：链≥60、干预≥20、取代≥10、负样本≥20）
# 缺省配额 = T5 的 122 题，与 dataset/causal_evalset.jsonl 一一对应。
# T25 扩集（236 题）用 --quota 68,68,40,20,40，写到 dataset/causal_evalset_v2.jsonl，不覆盖旧题。
QUOTA = {
    cg.CHAIN_ANCESTOR: 34,
    cg.CHAIN_DESCENDANT: 34,
    cg.INTERVENTION: 20,   # 踩坑 10 + 正常 10
    cg.SUPERSESSION: 10,
    cg.NEGATIVE: 24,
}
SEED = 20261109  # 与 gen_tree.py 同源；选题打乱用，保证可复现

# 证伪信号词表（中文，借鉴 causal-memory FALSIFY_SIGNALS 的本地化最小版）：
# 新结论条目必须命中其一，否则「取代」在文本上无从体现（机械校验，不靠人眼）
FALSIFY_SIGNALS_CN = ["新结论", "改为", "不再", "无效", "取代", "证伪", "替换", "其实", "没能", "不再适用"]


def q_ancestor(title: str) -> str:
    return f"「{title}」这一步的前因链是什么？从直接前因一直追到最初的起因。"


def q_descendant(title: str) -> str:
    return f"「{title}」之后引发了哪些后果？把后续的连锁反应都列出来。"


def q_intervention(desc: str) -> str:
    return f"我马上要「{desc}」，历史上这么做踩过坑吗？先给我个预警。"


def q_supersession(title: str) -> str:
    return f"关于「{title}」这个结论，现在还成立吗？当前有效的结论是哪条？"


def q_negative(raw: str) -> str:
    return raw


def _depth(tree: Dict[str, Any], nid: str) -> int:
    d = 0
    cur = tree["_by_id"][nid].get("parent_id", "")
    while cur:
        d += 1
        cur = tree["_by_id"][cur].get("parent_id", "")
    return d


def select_targets(tree: Dict[str, Any], rng: random.Random) -> Dict[str, List[Any]]:
    """确定性选题：seed 决定打乱顺序，不硬编码任何节点 id。

    - 链追溯目标互斥（同一节点不既出链前因又出链后果），且避开取代旧结论节点
      （取代题另有专属题面，避免一节点两题型口径混淆）；
    - 干预按 outcome 分层：踩坑动作 10 + 正常动作 10；
    - 取代目标 = 全部带 superseded_by 的旧结论节点；
    - 负样本 = 全部 noise_queries。
    """
    by_id = tree["_by_id"]
    sup_old = sorted(n["id"] for n in by_id.values() if n.get("superseded_by"))

    # 后果方向目标：有 ≥1 个严格后代的节点（根节点也可作后果起点）
    desc_cand = sorted(
        n["id"] for n in by_id.values()
        if n["id"] not in sup_old and _desc_count(tree, n["id"]) >= 1
    )
    rng.shuffle(desc_cand)
    sel_desc = desc_cand[: QUOTA[cg.CHAIN_DESCENDANT]]

    # 前因方向目标：深度 ≥3（因链非平凡），且不在后果目标/取代旧结论内
    anc_cand = sorted(
        n["id"] for n in by_id.values()
        if _depth(tree, n["id"]) >= 3
        and n["id"] not in sup_old
        and n["id"] not in set(sel_desc)
    )
    rng.shuffle(anc_cand)
    sel_anc = anc_cand[: QUOTA[cg.CHAIN_ANCESTOR]]

    # 干预：按 outcome 分层抽动作（踩坑动作 vs 无踩坑动作，各半）
    pit_actions = sorted({n["action_key"] for n in by_id.values()
                          if n.get("action_key") and n.get("outcome") == "pitfall"})
    pit_set = set(pit_actions)
    norm_actions = sorted(
        k for k in {n["action_key"] for n in by_id.values() if n.get("action_key")}
        if k not in pit_set
    )
    rng.shuffle(pit_actions)
    rng.shuffle(norm_actions)
    half = QUOTA[cg.INTERVENTION] // 2
    sel_pit = pit_actions[:half]
    sel_norm = norm_actions[: QUOTA[cg.INTERVENTION] - half]

    return {
        cg.CHAIN_ANCESTOR: sorted(sel_anc),
        cg.CHAIN_DESCENDANT: sorted(sel_desc),
        cg.INTERVENTION: [("pitfall", k) for k in sorted(sel_pit)]
        + [("normal", k) for k in sorted(sel_norm)],
        cg.SUPERSESSION: sorted(sup_old)[: QUOTA[cg.SUPERSESSION]],
        cg.NEGATIVE: list(tree["noise_queries"]),
    }


def _desc_count(tree: Dict[str, Any], nid: str) -> int:
    kids: Dict[str, List[str]] = {}
    for n in tree["_by_id"].values():
        kids.setdefault(n.get("parent_id", ""), []).append(n["id"])
    out = 0
    stack = list(kids.get(nid, []))
    while stack:
        cur = stack.pop()
        out += 1
        stack.extend(kids.get(cur, []))
    return out


def build_cases(tree: Dict[str, Any]) -> List[Dict[str, Any]]:
    by_id = tree["_by_id"]
    rng = random.Random(SEED)
    sel = select_targets(tree, rng)
    cases: List[Dict[str, Any]] = []

    def add(qtype: str, query: str, expr: Dict[str, Any], note: str) -> None:
        gold = cg.evaluate_expr(tree, expr)
        cases.append(
            {
                "type": qtype,
                "query": query,
                "expect": gold["expect"],
                "label": gold["label"],
                "gold_expr": expr,
                "note": note,
            }
        )

    # ① 因果链追溯：给后果查前因
    for nid in sel[cg.CHAIN_ANCESTOR]:
        add(
            cg.CHAIN_ANCESTOR,
            q_ancestor(by_id[nid]["title"]),
            {"kind": cg.CHAIN_ANCESTOR, "node": nid},
            f"因链 gold = ancestors({nid})，root 在前，不含自身",
        )

    # ① 因果链追溯：给前因查后果
    for nid in sel[cg.CHAIN_DESCENDANT]:
        add(
            cg.CHAIN_DESCENDANT,
            q_descendant(by_id[nid]["title"]),
            {"kind": cg.CHAIN_DESCENDANT, "node": nid},
            f"果链 gold = descendants({nid})，严格后代，id 升序",
        )

    # ② 干预预警（踩坑/正常分层）
    for tier, key in sel[cg.INTERVENTION]:
        label, _ = cg.intervention(tree, key)
        add(
            cg.INTERVENTION,
            q_intervention(tree["actions"][key]["desc"]),
            {"kind": cg.INTERVENTION, "action_key": key},
            f"干预 gold：action_key={key} → {label}（由 outcome=pitfall 节点机械判定；分层={tier}）",
        )

    # ③ 软取代感知（oracle 口径）
    for nid in sel[cg.SUPERSESSION]:
        add(
            cg.SUPERSESSION,
            q_supersession(by_id[nid]["title"]),
            {"kind": cg.SUPERSESSION, "node": nid},
            f"取代 gold = superseded_by({nid})；【oracle 口径】取代边由生成器在合成树显式种入，"
            f"测「能否用好已种标记」，不测「自动发现证伪」",
        )

    # ④ 负样本 / 噪声
    for nq in sel[cg.NEGATIVE]:
        add(
            cg.NEGATIVE,
            q_negative(nq["query"]),
            {"kind": cg.NEGATIVE, "key": nq["key"]},
            f"负样本 gold 恒空；keyword={nq['keyword']} 必须与全树 title/content 互斥",
        )

    # 题型顺序 + 序号稳定化（qid 固定 3 位，兼容 ≥100 题）
    cases.sort(key=lambda c: (TYPE_ORDER.index(c["type"]), c["query"]))
    for i, c in enumerate(cases, 1):
        c["qid"] = f"q{i:03d}"
    return cases


def sanity_checks(tree: Dict[str, Any], cases: List[Dict[str, Any]]) -> None:
    # 1) 脱敏：noise keyword 与全树正文互斥
    blob = "\n".join(
        n["title"] + "\n" + n["content"] for n in tree["_by_id"].values()
    )
    for nq in tree["noise_queries"]:
        if nq["keyword"] in blob:
            raise SystemExit(f"脱敏/负样本自检失败：keyword {nq['keyword']} 出现在树内")
    blob += "\n" + "\n".join(c["query"] for c in cases)
    # 2) 所有 expect id 都真实存在于树内（或为空）
    for c in cases:
        for e in c["expect"]:
            if e not in tree["_by_id"]:
                raise SystemExit(f"{c['qid']}: expect id 不在树内: {e}")
    # 3) 软取代对：新结论必须命中证伪信号词表（否则「取代」在文本上无从体现）
    for n in tree["_by_id"].values():
        sup = n.get("superseded_by", "")
        if not sup:
            continue
        new = tree["_by_id"].get(sup)
        if new is None:
            raise SystemExit(f"superseded_by 悬空: {n['id']} -> {sup}")
        text = new["title"] + "\n" + new["content"]
        if not any(w in text for w in FALSIFY_SIGNALS_CN):
            raise SystemExit(
                f"证伪信号缺失：{sup} 未命中词表 {FALSIFY_SIGNALS_CN}"
            )
    # 4) 题量与四类分布达标（T5 扩集验收：≥120；链≥60/干预≥20/取代≥10/负样本≥20）
    counts: Dict[str, int] = {}
    for c in cases:
        counts[c["type"]] = counts.get(c["type"], 0) + 1
    n_chain = counts.get(cg.CHAIN_ANCESTOR, 0) + counts.get(cg.CHAIN_DESCENDANT, 0)
    # 下限按当前配额，不写死 122：旧集 122、T25 扩集 236 都能过。
    if len(cases) < sum(QUOTA.values()):
        raise SystemExit(f"题量不足 {sum(QUOTA.values())}: {len(cases)}")
    if n_chain < QUOTA[cg.CHAIN_ANCESTOR] + QUOTA[cg.CHAIN_DESCENDANT]:
        raise SystemExit(f"链追溯题不足: {n_chain}")
    if counts.get(cg.INTERVENTION, 0) < QUOTA[cg.INTERVENTION]:
        raise SystemExit(f"干预题不足: {counts.get(cg.INTERVENTION, 0)}")
    if counts.get(cg.SUPERSESSION, 0) < QUOTA[cg.SUPERSESSION]:
        raise SystemExit(f"取代题不足: {counts.get(cg.SUPERSESSION, 0)}")
    if counts.get(cg.NEGATIVE, 0) < QUOTA[cg.NEGATIVE]:
        raise SystemExit(f"负样本题不足: {counts.get(cg.NEGATIVE, 0)}")
    present = {c["type"] for c in cases}
    for t in (cg.CHAIN_ANCESTOR, cg.INTERVENTION, cg.SUPERSESSION, cg.NEGATIVE):
        if t not in present:
            raise SystemExit(f"缺题型: {t}")
    # 5) 真人姓名/凭据模式兜底（合成语料不应命中）
    banned = ["sk-", "password", "口令", "api key", "赵", "钱", "孙"]
    for b in banned:
        if b in blob:
            raise SystemExit(f"脱敏自检失败：树内命中疑似敏感片段 {b!r}")


def main() -> int:
    ap = argparse.ArgumentParser(description="从合成因果树生成 agimem 评测集")
    ap.add_argument("--tree", default="data/tree.json")
    ap.add_argument("--out", default="dataset/causal_evalset.jsonl")
    ap.add_argument("--stdout", action="store_true", help="打印到标准输出而不写文件")
    ap.add_argument("--quota", default="",
                    help="五类配额 ancestor,descendant,intervention,supersession,negative；缺省用 QUOTA")
    args = ap.parse_args()
    if args.quota:
        parts = [int(x) for x in args.quota.split(",")]
        if len(parts) != 5:
            raise SystemExit("--quota 需要 5 个整数")
        for key, n in zip(TYPE_ORDER, parts):
            QUOTA[key] = n

    tree = cg.load_tree(args.tree)
    cases = build_cases(tree)
    sanity_checks(tree, cases)

    lines = [json.dumps(c, ensure_ascii=False, sort_keys=True) for c in cases]
    if args.stdout:
        print("\n".join(lines))
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        counts: Dict[str, int] = {}
        for c in cases:
            counts[c["type"]] = counts.get(c["type"], 0) + 1
        n_chain = counts.get(cg.CHAIN_ANCESTOR, 0) + counts.get(cg.CHAIN_DESCENDANT, 0)
        print(f"[gen_dataset] 写出 {args.out}: {len(cases)} 题 (seed={SEED})")
        for t in TYPE_ORDER:
            print(f"  - {t}: {counts.get(t, 0)}")
        print(f"  - 链追溯合计: {n_chain}")
        print(f"[gen_dataset] 脱敏自检通过（noise keyword 与全树正文互斥；无敏感片段）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

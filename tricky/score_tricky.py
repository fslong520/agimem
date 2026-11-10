#!/usr/bin/env python3
"""score_tricky.py — H4「刁钻工作场景」层判分：每类命中率 + Wilson CI + 类人度总分。

用法：
    python3 score_tricky.py --verify-only                 # gold 机械复现对账
    python3 score_tricky.py --predictions results/arm-synthetic-lexical.jsonl \
        [--topk 5] [--json] [--panel results/panel.md]

判分口径（search-only，零 LLM，与 agimem 主链一致）：
    T1 抗干扰      gold 命中 top-k（同主题干扰记录越多越难）
    T2 同名异事    gold 命中 top-k（两个同名记录，按场景选对）
    T3 隐含约束    gold 命中 top-k（文档里没写、但必须遵守的规矩）
    T4 失效感知    gold 命中 top-k（superseded_by 指向的当前结论）
    T5 跨时间一致  gold 命中 top-k（三跳取代链的链尾）
    T6 证据分级    **实测记录必须先于转述记录出现在 top-k**（只看证据级先后，不看措辞）

类人度总分（humanlike score）：
    加权和 Σ w_i · s_i，权重见 WEIGHTS。选这些权重的理由：
    同名异事与隐含约束最依赖「人类常识 + 场景绑定」，各给 0.20；
    抗干扰、失效感知、跨时间一致、证据分级各 0.15。
    总分越高 = 记忆行为越像人：不被同名与噪音骗、能提取没人写下的规矩、
    会随事实更新结论、保留时间线、优先信实测。

95% CI：单类比例用 Wilson score 区间；总分用分层 bootstrap（同型内重采样，
固定 seed，默认 2000 次），避免小样本点估计被误读。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from typing import Any, Dict, List, Optional, Tuple

import scenarios as scn
import tricky_gold as tg

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(HERE, "dataset", "tricky_evalset.jsonl")
TREE = os.path.join(HERE, "data", "tricky_tree.json")

# 类人度总分权重（和为 1.0）
WEIGHTS: Dict[str, float] = {
    tg.T1_INTERFERENCE: 0.15,
    tg.T2_SAME_NAME: 0.20,
    tg.T3_IMPLICIT: 0.20,
    tg.T4_SUPERSEDED: 0.15,
    tg.T5_CROSS_TIME: 0.15,
    tg.T6_EVIDENCE: 0.15,
}
# 主指标用 hit@1 的类型：必须首选命中（刁钻点在于「选对」，不是「出现过」）
MAIN_METRIC_HIT1 = (tg.T2_SAME_NAME, tg.T3_IMPLICIT, tg.T4_SUPERSEDED, tg.T5_CROSS_TIME)
BOOTSTRAP_SEED = 20261109
BOOTSTRAP_REPS = 2000
Z95 = 1.959963984540054


# ---------------------------------------------------------------- 统计

def wilson_ci(k: int, n: int, z: float = Z95) -> Dict[str, Any]:
    if n <= 0:
        return {"point": None, "lo": None, "hi": None, "n": 0, "k": k}
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return {"point": p, "lo": max(0.0, center - half), "hi": min(1.0, center + half),
            "n": n, "k": k, "method": "wilson", "z": z}


def fmt_ci(c: Dict[str, Any], nd: int = 3) -> str:
    if not c or c.get("point") is None:
        return "n/a"
    return f"{c['point']:.{nd}f} [{c['lo']:.{nd}f}, {c['hi']:.{nd}f}]"


def bootstrap_ci(per_type_hits: Dict[str, List[float]],
                 seed: int = BOOTSTRAP_SEED, reps: int = BOOTSTRAP_REPS) -> Dict[str, Any]:
    """分层 bootstrap：各型内独立重采样，按权重合成总分。"""
    rng = random.Random(seed)
    point = sum(WEIGHTS[t] * (sum(v) / len(v)) for t, v in per_type_hits.items() if v)
    samples: List[float] = []
    for _ in range(reps):
        total = 0.0
        for t, vals in per_type_hits.items():
            if not vals:
                continue
            draw = [vals[rng.randrange(len(vals))] for _ in vals]
            total += WEIGHTS[t] * (sum(draw) / len(draw))
        samples.append(total)
    samples.sort()
    lo = samples[int(0.025 * (len(samples) - 1))]
    hi = samples[int(0.975 * (len(samples) - 1))]
    return {"point": point, "lo": lo, "hi": hi, "method": "stratified-bootstrap",
            "reps": reps, "seed": seed}


# ---------------------------------------------------------------- 数据读取

def load_jsonl(path: str) -> List[Dict[str, Any]]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise SystemExit(f"{path} 第 {i} 行解析失败: {e}")
    return out


def extract_hits(rec: Any) -> List[Dict[str, Any]]:
    if isinstance(rec, list):
        items = rec
    elif isinstance(rec, dict):
        if isinstance(rec.get("hits"), list):
            items = rec["hits"]
        elif isinstance(rec.get("details"), list):
            items = rec["details"]
        else:
            raise SystemExit(f"预测记录缺 hits/details: {json.dumps(rec, ensure_ascii=False)[:120]}")
    else:
        raise SystemExit(f"预测记录类型非法: {type(rec)}")
    hits = []
    for h in items:
        if not isinstance(h, dict):
            continue
        hid = h.get("id")
        if not isinstance(hid, str) or not hid:
            entry = h.get("entry")
            hid = entry.get("id") if isinstance(entry, dict) else None
        if not hid:
            continue
        hits.append({"id": hid, "score": h.get("score")})
    return hits


def index_predictions(path: str) -> Dict[str, Dict[str, Any]]:
    by_qid, by_query = {}, {}
    for rec in load_jsonl(path):
        item = {"qid": rec.get("qid"), "query": rec.get("query"), "hits": extract_hits(rec)}
        if item["qid"]:
            by_qid[item["qid"]] = item
        if item["query"]:
            by_query[item["query"]] = item
    return {"by_qid": by_qid, "by_query": by_query}


# ---------------------------------------------------------------- gold 对账

def verify_gold(dataset: List[Dict[str, Any]], tree: Dict[str, Any]) -> List[str]:
    errors = []
    for q in dataset:
        try:
            gold = tg.evaluate_expr(tree, q["gold_expr"])
        except ValueError as e:
            errors.append(f"{q.get('qid')}: 重算失败 {e}")
            continue
        if list(gold["expect"]) != list(q.get("expect", [])):
            errors.append(f"{q.get('qid')}: expect 不一致 重算={gold['expect']} 落盘={q.get('expect')}")
        if gold["label"] != q.get("label"):
            errors.append(f"{q.get('qid')}: label 不一致 重算={gold['label']} 落盘={q.get('label')}")
        for e in q.get("expect", []):
            if e not in tree["_by_id"]:
                errors.append(f"{q.get('qid')}: expect 不在树内 {e}")
    return errors


# ---------------------------------------------------------------- 判分

def first_match_rank(ids: List[str], expect: List[str]) -> Optional[int]:
    for i, rid in enumerate(ids):
        if any(tg.id_match(rid, e) for e in expect):
            return i
    return None


def score(dataset: List[Dict[str, Any]], tree: Dict[str, Any],
          preds: Dict[str, Dict[str, Any]], topk: int, partial: bool = False) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    missing: List[str] = []

    for q in dataset:
        qid = q["qid"]
        item = preds["by_qid"].get(qid) or preds["by_query"].get(q["query"])
        if item is None:
            missing.append(qid)
            if partial:
                continue
            hits: List[Dict[str, Any]] = []
        else:
            hits = item["hits"]
        ids = [h["id"] for h in hits]
        top = ids[:topk]
        expect = q["expect"]
        qtype = q["type"]
        rank = first_match_rank(top, expect)
        row: Dict[str, Any] = {
            "qid": qid, "type": qtype, "scenario": q.get("scenario"),
            "query": q["query"], "gold": list(expect), "n_hits": len(ids),
            "top": ids[:topk], "hit_at_k": rank is not None, "rank": rank,
            "hit_at_1": rank == 0,
        }
        # 分型附加判分
        if qtype == tg.T1_INTERFERENCE:
            dis = set(tg.distractor_ids(tree, q["gold_expr"]["topic"]))
            occupied = sum(1 for i in top if tg.resolve_hit(tree, i) in dis)
            row["distractor_rate"] = (occupied / len(top)) if top else 0.0
            row["reason"] = (f"真约束 {expect[0]}；top-{topk} 中同主题干扰记录 {occupied}/{len(top)}；"
                             f"gold rank={rank}")
        elif qtype == tg.T2_SAME_NAME:
            row["reason"] = (f"重名物「{q['gold_expr']['group']}」在 {q['scenario']} 的定义 {expect[0]}；"
                             f"gold rank={rank}")
        elif qtype == tg.T3_IMPLICIT:
            row["reason"] = f"隐含规矩（implicit=true）{expect[0]}；gold rank={rank}"
        elif qtype == tg.T4_SUPERSEDED:
            row["reason"] = (f"旧结论 {q['gold_expr']['old']} → superseded_by {expect[0]}；"
                             f"gold rank={rank}")
        elif qtype == tg.T5_CROSS_TIME:
            ch = tg.chain_of(tree, q["gold_expr"]["head"])
            row["chain"] = ch
            row["reason"] = f"三跳链 {'→'.join(ch)}，gold=链尾 {expect[0]}；gold rank={rank}"
        elif qtype == tg.T6_EVIDENCE:
            grp = tg.claim_group(tree, q["gold_expr"]["claim"])  # 证据级降序
            ranks = {}
            for gid in grp:
                r = first_match_rank(top, [gid])
                if r is not None:
                    ranks[gid] = r
            measured = expect[0]
            hearsay = [g for g in grp if tree["_by_id"][g].get("source") == "hearsay"]
            m_rank = ranks.get(measured)
            h_ranks = [ranks[g] for g in hearsay if g in ranks]
            evidence_first = m_rank is not None and all(m_rank < h for h in h_ranks)
            row["evidence_first"] = evidence_first
            row["measured_rank"] = m_rank
            row["hearsay_rank"] = min(h_ranks) if h_ranks else None
            row["reason"] = (f"claim 组 {grp}；实测 rank={m_rank}，转述 rank="
                             f"{row['hearsay_rank']}；证据优先={evidence_first}")
        rows.append(row)

    # 汇总
    def sub(t: str) -> List[Dict[str, Any]]:
        return [r for r in rows if r["type"] == t]

    per_type: Dict[str, Any] = {}
    per_type_hits: Dict[str, List[float]] = {}
    for t in tg.ALL_TYPES:
        rs = sub(t)
        n = len(rs)
        k_hit = sum(1 for r in rs if r["hit_at_k"])
        if t == tg.T6_EVIDENCE:
            main_vals = [1.0 if r.get("evidence_first") else 0.0 for r in rs]
            main_name = "evidence_first_acc"
            main_ci = wilson_ci(sum(1 for v in main_vals if v > 0), n)
        elif t in MAIN_METRIC_HIT1:
            # 同名异事/隐含约束/失效感知/跨时间一致：必须**首选就选对**，
            # 只是「碰巧挤进 top-k」不算——这正是刁钻点。
            main_vals = [1.0 if r["hit_at_1"] else 0.0 for r in rs]
            main_name = "hit_at_1"
            main_ci = wilson_ci(sum(1 for r in rs if r["hit_at_1"]), n)
        else:
            main_vals = [1.0 if r["hit_at_k"] else 0.0 for r in rs]
            main_name = "hit_at_k"
            main_ci = wilson_ci(k_hit, n)
        per_type_hits[t] = main_vals
        per_type[t] = {
            "name": tg.TYPE_NAMES[t],
            "n": n,
            "hit_at_k": (k_hit / n) if n else 0.0,
            "hit_at_k_ci": wilson_ci(k_hit, n),
            "hit_at_1": (sum(1 for r in rs if r["hit_at_1"]) / n) if n else 0.0,
            "main_metric": main_name,
            "main_score": (sum(main_vals) / n) if n else 0.0,
            "main_ci": main_ci,
            "weight": WEIGHTS[t],
        }
        if t == tg.T1_INTERFERENCE and rs:
            per_type[t]["distractor_rate"] = sum(r["distractor_rate"] for r in rs) / n
        if t == tg.T6_EVIDENCE and rs:
            per_type[t]["hearsay_quotes_top1"] = sum(
                1 for r in rs if r.get("hearsay_rank") == 0) / n

    composite = bootstrap_ci(per_type_hits)
    summary = {
        "n_dataset": len(dataset),
        "scored": len(rows),
        "excluded_missing": len(missing),
        "missing_predictions": missing,
        "params": {"topk": topk},
        "distribution": {t: per_type[t]["n"] for t in tg.ALL_TYPES},
        "scenario_distribution": _scen_dist(dataset),
        "per_type": per_type,
        "weights": WEIGHTS,
        "humanlike_score": composite,
    }
    return {"summary": summary, "rows": rows}


def scen_cn(key: str) -> str:
    """场景键 → 中文场景名（面板与下钻用中文，便于人读）。"""
    info = scn.SCENARIOS.get(key)
    return info["name"] if info else str(key)


def _scen_dist(dataset: List[Dict[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for q in dataset:
        k = scen_cn(q.get("scenario", "?"))
        out[k] = out.get(k, 0) + 1
    return out


def render_text(result: Dict[str, Any]) -> str:
    s = result["summary"]
    L = ["=== H4 刁钻工作场景 判分结果 ==="]
    L.append("!! 声明：本层为全合成题库；若被测库未导入合成记录，数字是「题不在库」的检索结果，"
             "不是真实系统记忆能力分。")
    L.append(f"题量 {s['scored']}/{s['n_dataset']} | topk={s['params']['topk']}")
    if s["excluded_missing"]:
        L.append(f"!! 缺预测 {s['excluded_missing']} 题按 0 分计入")
    for t in tg.ALL_TYPES:
        d = s["per_type"][t]
        L.append(f"[{t} {d['name']}] n={d['n']}  "
                 f"hit@{s['params']['topk']}={d['hit_at_k']:.3f} "
                 f"CI={fmt_ci(d['hit_at_k_ci'])}  "
                 f"{d['main_metric']}={d['main_score']:.3f} CI={fmt_ci(d['main_ci'])}")
        if "distractor_rate" in d:
            L.append(f"    同主题干扰占 top-k 比例（越低越好）= {d['distractor_rate']:.3f}")
        if "hearsay_quotes_top1" in d:
            L.append(f"    转述记录霸占 top-1 的比例（越低越好）= {d['hearsay_quotes_top1']:.3f}")
    h = s["humanlike_score"]
    L.append(f"★ 类人度总分 = {h['point']:.3f}  95%CI=[{h['lo']:.3f}, {h['hi']:.3f}]  "
             f"（{h['method']}, reps={h['reps']}, seed={h['seed']}）")
    return "\n".join(L)


def render_panel(result: Dict[str, Any], baselines: Optional[Dict[str, Any]] = None,
                 top_drill: int = 0, arm_label: str = "") -> str:
    s = result["summary"]
    p = s["params"]
    L: List[str] = ["# agimem H4 · 刁钻工作场景指标面板", ""]
    if arm_label:
        L.append(f"> **本臂：{arm_label}。**")
        L.append(">")
        L.append("> **醒目声明：本臂是隔离 rsrs 库真跑——748 条合成记录确实写进了该库并被真召回，"
                 "因此下表可读成「该记忆系统在本合成语料上的检索层类人表现」。但语料全合成、"
                 "gold 机械推导、且为 oracle 级字段（superseded_by 等），外推到真实业务需另证；"
                 "perfect/adversarial 仍是判分器两极自证，不代表真实系统水平。**")
    else:
        L.append("> **醒目声明：本层为全合成题库。若被测库未导入合成记录，下表数字是「题不在库」的"
                 "检索结果，不是真实系统记忆能力分；perfect/adversarial 是判分器两极自证，"
                 "不代表任何真实系统水平。**")
    L.append("")
    L.append(f"- 判分参数：topk={p['topk']}，search-only 零 LLM")
    L.append(f"- 题量：{s['scored']}/{s['n_dataset']}")
    L.append("")
    L.append("## 一、题量与分布")
    L.append("")
    L.append("| 刁钻类型 | 人类记忆能力 | 题数 | 权重 |")
    L.append("|---|---|---:|---:|")
    for t in tg.ALL_TYPES:
        d = s["per_type"][t]
        L.append(f"| {t} | {d['name']} | {d['n']} | {d['weight']:.2f} |")
    L.append(f"| **合计** | | **{s['n_dataset']}** | 1.00 |")
    L.append("")
    L.append("场景分布：" + " | ".join(f"{k}={v}" for k, v in sorted(s["scenario_distribution"].items())))
    L.append("")
    L.append("## 二、每类点估计与 95% CI")
    L.append("")
    L.append("| 类型 | hit@k | 95% CI | 主指标 | 主指标值 | 95% CI |")
    L.append("|---|---:|---|---|---:|---|")
    for t in tg.ALL_TYPES:
        d = s["per_type"][t]
        L.append(f"| {t} {d['name']} | {d['hit_at_k']:.3f} | {fmt_ci(d['hit_at_k_ci'])} | "
                 f"{d['main_metric']} | {d['main_score']:.3f} | {fmt_ci(d['main_ci'])} |")
    h = s["humanlike_score"]
    L.append("")
    L.append(f"**类人度总分 = {h['point']:.3f}**（95% CI [{h['lo']:.3f}, {h['hi']:.3f}]，"
             f"{h['method']}，reps={h['reps']}，seed={h['seed']}）")
    L.append("")
    L.append("总分口径：`Σ w_i·s_i`。T1 抗干扰 0.15 / T2 同名异事 0.20 / T3 隐含约束 0.20 / "
             "T4 失效感知 0.15 / T5 跨时间一致 0.15 / T6 证据分级 0.15。"
             "同名异事与隐含约束最依赖常识与场景绑定，权重最高。")
    L.append("")
    if baselines:
        L.append("## 三、基线对照")
        L.append("")
        L.append("| 指标 | 本臂 | perfect | adversarial |")
        L.append("|---|---:|---:|---:|")
        keys = list(tg.ALL_TYPES)
        for t in keys:
            d = s["per_type"][t]
            L.append(f"| {t} {d['name']} 主指标 | {d['main_score']:.3f} | "
                     f"{_bl(baselines, 'perfect', t):.3f} | {_bl(baselines, 'adversarial', t):.3f} |")
        L.append(f"| **类人度总分** | {h['point']:.3f} | "
                 f"{_blc(baselines, 'perfect'):.3f} | {_blc(baselines, 'adversarial'):.3f} |")
        L.append("")
    L.append("## 四、单题下钻（qid → 场景 → gold → top-k → 判分理由）")
    L.append("")
    drills = result["rows"]
    if top_drill and top_drill < len(drills):
        drills = drills[:top_drill]
    L.append("| qid | 类型 | 场景 | gold | top-k | 判分理由 |")
    L.append("|---|---|---|---|---|---|")
    for r in drills:
        top = ",".join(r.get("top") or []) or "∅"
        reason = (r.get("reason") or "").replace("|", "/").replace("\n", " ")
        L.append(f"| {r['qid']} | {r['type']} | {scen_cn(r.get('scenario'))} | "
                 f"{','.join(r['gold'])} | {top} | {reason} |")
    if not top_drill or top_drill >= len(result["rows"]):
        L.append(f"（共 {len(result['rows'])} 题，全部列出）")
    L.append("")
    return "\n".join(L)


def paired_delta(rows_a: List[Dict[str, Any]], rows_b: List[Dict[str, Any]],
                 seed: int = BOOTSTRAP_SEED, reps: int = BOOTSTRAP_REPS) -> Dict[str, Any]:
    """有树 vs 无树：同题配对 Δ（同型内重采样，保证两臂抽同一组题）。"""
    idx_b = {r["qid"]: r for r in rows_b}
    per_type_vals: Dict[str, List[Tuple[float, float]]] = {t: [] for t in tg.ALL_TYPES}
    for r in rows_a:
        other = idx_b.get(r["qid"])
        if other is None:
            continue
        t = r["type"]
        if t == tg.T6_EVIDENCE:
            va = 1.0 if r.get("evidence_first") else 0.0
            vb = 1.0 if other.get("evidence_first") else 0.0
        elif t in MAIN_METRIC_HIT1:
            va = 1.0 if r["hit_at_1"] else 0.0
            vb = 1.0 if other["hit_at_1"] else 0.0
        else:
            va = 1.0 if r["hit_at_k"] else 0.0
            vb = 1.0 if other["hit_at_k"] else 0.0
        per_type_vals[t].append((va, vb))

    def weighted(pairs: Dict[str, List[Tuple[float, float]]]) -> Tuple[float, float]:
        a_sum = b_sum = w_sum = 0.0
        for t, vals in pairs.items():
            if not vals:
                continue
            a_sum += WEIGHTS[t] * (sum(v[0] for v in vals) / len(vals))
            b_sum += WEIGHTS[t] * (sum(v[1] for v in vals) / len(vals))
            w_sum += WEIGHTS[t]
        return (a_sum / w_sum if w_sum else 0.0), (b_sum / w_sum if w_sum else 0.0)

    a_point, b_point = weighted(per_type_vals)
    rng = random.Random(seed)
    deltas: List[float] = []
    for _ in range(reps):
        sample: Dict[str, List[Tuple[float, float]]] = {}
        for t, vals in per_type_vals.items():
            if vals:
                sample[t] = [vals[rng.randrange(len(vals))] for _ in vals]
        da, db = weighted(sample)
        deltas.append(da - db)
    deltas.sort()
    return {
        "arm_a": a_point, "arm_b": b_point, "delta": a_point - b_point,
        "lo": deltas[int(0.025 * (len(deltas) - 1))],
        "hi": deltas[int(0.975 * (len(deltas) - 1))],
        "method": "paired-stratified-bootstrap", "reps": reps, "seed": seed,
        "per_type": {
            t: {"a": (sum(v[0] for v in vals) / len(vals)) if vals else None,
                "b": (sum(v[1] for v in vals) / len(vals)) if vals else None,
                "delta": ((sum(v[0] for v in vals) - sum(v[1] for v in vals)) / len(vals)) if vals else None,
                "n": len(vals)}
            for t, vals in per_type_vals.items()
        },
    }


def _bl(baselines: Dict[str, Any], arm: str, t: str) -> float:
    v = (baselines.get(arm) or {}).get("per_type", {}).get(t, {}).get("main_score")
    return float(v) if v is not None else float("nan")


def _blc(baselines: Dict[str, Any], arm: str) -> float:
    v = (baselines.get(arm) or {}).get("humanlike_score")
    return float(v) if v is not None else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser(description="H4 刁钻工作场景判分")
    ap.add_argument("--dataset", default=DATASET)
    ap.add_argument("--tree", default=TREE)
    ap.add_argument("--predictions")
    ap.add_argument("--topk", type=int, default=5)
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--partial", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--panel", help="写人读 Markdown 面板；同名 .json 写机器可读 summary")
    ap.add_argument("--panel-limit", type=int, default=0)
    ap.add_argument("--baseline-dir", help="读该目录下 perfect.jsonl/adversarial.jsonl 作对照")
    ap.add_argument("--delta", metavar="ARM_B", help="对照臂预测文件：输出同题配对 Δ（本臂−对照臂）")
    ap.add_argument("--delta-out", help="把 Δ 结果写入该 JSON 文件")
    ap.add_argument("--arm-label", default="",
                    help="臂名（如「隔离库：合成树真在库内」）；给了就改用隔离库版醒目标注")
    args = ap.parse_args()

    tree = tg.load_tree(args.tree)
    dataset = load_jsonl(args.dataset)

    errors = verify_gold(dataset, tree)
    if errors:
        print("[verify] FAIL — gold 无法机械复现：", file=sys.stderr)
        for e in errors:
            print("  - " + e, file=sys.stderr)
        return 1
    if args.verify_only:
        msg = f"[verify] OK — {len(dataset)} 题 gold 全部由节点字段重算一致"
        print(json.dumps({"verify": "ok", "n": len(dataset)}) if args.json else msg)
        return 0

    if not args.predictions:
        print("缺 --predictions（或用 --verify-only）", file=sys.stderr)
        return 2

    preds = index_predictions(args.predictions)
    result = score(dataset, tree, preds, args.topk, partial=args.partial)

    if args.delta:
        other = score(dataset, tree, index_predictions(args.delta), args.topk, partial=args.partial)
        d = paired_delta(result["rows"], other["rows"])
        result["summary"]["delta_vs"] = d
        print("--- Δ（本臂 − 对照臂，同题配对，分层 bootstrap 95%CI）---")
        for t in tg.ALL_TYPES:
            pt = d["per_type"][t]
            if pt["a"] is None:
                continue
            print(f"    {t} {tg.TYPE_NAMES[t]}: {pt['a']:.3f} − {pt['b']:.3f} = {pt['delta']:+.3f}")
        print(f"    ★ 类人度总分: {d['arm_a']:.3f} − {d['arm_b']:.3f} = {d['delta']:+.3f} "
              f"[{d['lo']:+.3f}, {d['hi']:+.3f}]")
        if args.delta_out:
            with open(args.delta_out, "w", encoding="utf-8") as f:
                json.dump({"arm_a": args.predictions, "arm_b": args.delta,
                           "delta": d, "per_type": result["summary"]["per_type"]},
                          f, ensure_ascii=False, indent=2)
                f.write("\n")
            print(f"[delta] 写出 {args.delta_out}", file=sys.stderr)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result))

    if args.panel:
        baselines = None
        if args.baseline_dir:
            baselines = {}
            for arm in ("perfect", "adversarial"):
                pth = os.path.join(args.baseline_dir, f"{arm}.jsonl")
                if os.path.exists(pth):
                    b = score(dataset, tree, index_predictions(pth), args.topk, partial=False)
                    baselines[arm] = {"per_type": b["summary"]["per_type"],
                                      "humanlike_score": b["summary"]["humanlike_score"]["point"]}
        panel = render_panel(result, baselines=baselines, top_drill=args.panel_limit,
                             arm_label=args.arm_label)
        with open(args.panel, "w", encoding="utf-8") as f:
            f.write(panel + "\n")
        json_path = args.panel[:-3] + ".json" if args.panel.endswith(".md") else args.panel + ".json"
        doc = {
            "schema": "agimem-tricky-summary/1",
            "warning": ("隔离库臂：合成记录真在库内，可读成检索层类人表现；"
                        "语料全合成为限，外推需另证") if args.arm_label else
                       "全合成题库；树未导入被测库时，数字是「题不在库」的检索结果，非能力分",
            "arm_label": args.arm_label,
            "summary": result["summary"],
            "baselines": baselines,
            "per_question": result["rows"],
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"[panel] 写出 {args.panel} / {json_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

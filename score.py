#!/usr/bin/env python3
"""score.py — RespireCausalBench 判分脚本。

用法：
    # 1) 先验证 gold 可机械复现（数据集 expect vs 树结构重算）
    python3 score.py --verify-only --dataset dataset/causal_evalset.jsonl \
        --tree data/tree.json

    # 2) 对 recall 输出判分
    python3 score.py --dataset dataset/causal_evalset.jsonl \
        --tree data/tree.json --predictions fixtures/perfect.jsonl \
        [--topk 5] [--min-score 0.0] [--json]

预测文件（JSONL，一行一题）：
    {"qid":"q01","query":"...","hits":[{"id":"sntA0003","score":0.81,"superseded_by":null}]}
也兼容 `rsrs recall --json` 的 ResultEnvelope 形状（details 数组）与纯 hits 数组。
join 规则：优先 qid，其次 query 原文精确匹配。

指标（与 docs/design.md 第 5 节一致）：
    链命中率 chain_hit@k / 链覆盖率 chain_cov@k
    预警准确率 intervention_acc（含混淆计数）
    取代正确率 supersession_acc（含 stale/missing 计数）
    负样本噪声率 negative_noise_rate
id 匹配语义与 respire-cli/cli/src/bench.rs:56-60 的 id_match 一致（prefix 双向）。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional

import causal_gold as cg

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- 统计工具

def wilson_ci(k: int, n: int, z: float = 1.959963984540054) -> Dict[str, Any]:
    """Wilson score 区间（95% 缺省）。比例类指标统一用它，n=0 时返回 None。"""
    if n <= 0:
        return {"point": None, "lo": None, "hi": None, "n": 0, "k": k}
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return {
        "point": p,
        "lo": max(0.0, center - half),
        "hi": min(1.0, center + half),
        "n": n,
        "k": k,
        "method": "wilson",
        "z": z,
    }


def mean_ci(values: List[float], z: float = 1.959963984540054) -> Dict[str, Any]:
    """均值的正态近似 95% CI（用于链覆盖率这类 [0,1] 连续量）。"""
    n = len(values)
    if n == 0:
        return {"point": None, "lo": None, "hi": None, "n": 0}
    m = sum(values) / n
    if n == 1:
        return {"point": m, "lo": m, "hi": m, "n": 1, "method": "degenerate"}
    var = sum((v - m) ** 2 for v in values) / (n - 1)
    se = math.sqrt(var / n)
    return {
        "point": m,
        "lo": max(0.0, m - z * se),
        "hi": min(1.0, m + z * se),
        "n": n,
        "method": "normal-approx",
        "z": z,
    }


def fmt_ci(c: Dict[str, Any], nd: int = 3) -> str:
    if not c or c.get("point") is None:
        return "n/a"
    return f"{c['point']:.{nd}f} [{c['lo']:.{nd}f}, {c['hi']:.{nd}f}]"


# ---------------------------------------------------------------- 数据集 / 预测读取

def load_jsonl(path: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
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


def _entry_id(d: Dict[str, Any]) -> Optional[str]:
    if isinstance(d.get("id"), str) and d.get("id"):
        return d["id"]
    entry = d.get("entry")
    if isinstance(entry, dict) and isinstance(entry.get("id"), str):
        return entry["id"]
    return None


def extract_hits(rec: Any) -> List[Dict[str, Any]]:
    """把一条预测记录归一成 [{"id","score","superseded_by"}]。"""
    if isinstance(rec, list):
        items = rec
    elif isinstance(rec, dict):
        if isinstance(rec.get("hits"), list):
            items = rec["hits"]
        elif isinstance(rec.get("details"), list):  # rsrs recall --json envelope
            items = rec["details"]
        else:
            raise SystemExit(f"预测记录缺 hits/details 字段: {json.dumps(rec, ensure_ascii=False)[:120]}")
    else:
        raise SystemExit(f"预测记录类型非法: {type(rec)}")

    hits: List[Dict[str, Any]] = []
    for h in items:
        if not isinstance(h, dict):
            continue
        hid = _entry_id(h)
        if not hid:
            continue
        sup = h.get("superseded_by")
        if sup is None and isinstance(h.get("entry"), dict):
            sup = h["entry"].get("superseded_by") or None
        hits.append({"id": hid, "score": h.get("score"), "superseded_by": sup})
    return hits


def index_predictions(path: str) -> Dict[str, Dict[str, Any]]:
    by_qid: Dict[str, Dict[str, Any]] = {}
    by_query: Dict[str, Dict[str, Any]] = {}
    for rec in load_jsonl(path):
        item = {"qid": rec.get("qid"), "query": rec.get("query"), "hits": extract_hits(rec)}
        if item["qid"]:
            by_qid[item["qid"]] = item
        if item["query"]:
            by_query[item["query"]] = item
    return {"by_qid": by_qid, "by_query": by_query}


def filter_hits(hits: List[Dict[str, Any]], min_score: float) -> List[Dict[str, Any]]:
    if min_score <= 0:
        return hits
    out = []
    for h in hits:
        s = h.get("score")
        if s is None or float(s) >= min_score:
            out.append(h)
    return out


# ---------------------------------------------------------------- gold 对账（机械复现证明）

def verify_gold(dataset: List[Dict[str, Any]], tree: Dict[str, Any]) -> List[str]:
    """用 causal_gold 从树重算 gold，与数据集落盘的 expect/label 对账。"""
    errors: List[str] = []
    for c in dataset:
        gold = cg.evaluate_expr(tree, c["gold_expr"])
        if set(gold["expect"]) != set(c.get("expect", [])):
            errors.append(
                f"{c.get('qid')}: expect 不一致 重算={gold['expect']} 落盘={c.get('expect')}"
            )
        if gold["label"] != c.get("label"):
            errors.append(
                f"{c.get('qid')}: label 不一致 重算={gold['label']} 落盘={c.get('label')}"
            )
        # gold 非空时必须能在树内解析；空 expect 只允许 negative/intervention-SAFE
        for e in c.get("expect", []):
            if e not in tree["_by_id"]:
                errors.append(f"{c.get('qid')}: expect id 不在树内 {e}")
    return errors


# ---------------------------------------------------------------- 判分

def first_gold_rank(ids: List[str], expect: List[str]) -> Optional[int]:
    for i, rid in enumerate(ids):
        if any(cg.id_match(rid, e) for e in expect):
            return i
    return None


def score(dataset: List[Dict[str, Any]], tree: Dict[str, Any],
          preds: Dict[str, Dict[str, Any]], topk: int, min_score: float,
          partial: bool = False) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    missing: List[str] = []

    for c in dataset:
        qid = c.get("qid")
        item = preds["by_qid"].get(qid) or preds["by_query"].get(c["query"])
        if item is None:
            missing.append(qid or c["query"])
            if partial:
                continue  # --partial：只判有预测的题，缺预测题不计入分母
            hits: List[Dict[str, Any]] = []
        else:
            hits = filter_hits(item["hits"], min_score)
        ids = [h["id"] for h in hits]
        top_ids = ids[:topk]
        expect = c.get("expect", [])
        qtype = c["type"]

        row: Dict[str, Any] = {
            "qid": qid, "type": qtype, "n_hits": len(ids),
            "query": c.get("query", ""),
            "gold": list(expect),
            "gold_label": c.get("label"),
            "top": [{"id": h["id"], "score": h.get("score")} for h in hits[:topk]],
        }

        if qtype in (cg.CHAIN_ANCESTOR, cg.CHAIN_DESCENDANT):
            rank = first_gold_rank(top_ids, expect)
            row["hit"] = rank is not None
            row["rank"] = rank
            # 链覆盖率看「召回全集」而非 top-k：链题关心整条链是否找齐
            if expect:
                got = sum(1 for g in expect if any(cg.id_match(t, g) for t in ids))
                row["coverage"] = got / len(expect)
            else:
                row["coverage"] = 0.0
        elif qtype == cg.INTERVENTION:
            gold_label = c["label"]
            pred_label = "WARNING" if any(cg.is_pitfall(tree, i) for i in ids) else "SAFE"
            row["gold_label"] = gold_label
            row["pred_label"] = pred_label
            row["correct"] = pred_label == gold_label
            row["confusion"] = ("TP" if pred_label == "WARNING" else "FN") if gold_label == "WARNING" else (
                "FP" if pred_label == "WARNING" else "TN"
            )
            row["reason"] = (
                f"gold={gold_label} pred={pred_label} ({row['confusion']}); "
                f"判分依据：top-k 内是否有映射回本树且 outcome=pitfall 的召回 id"
            )
        elif qtype == cg.SUPERSESSION:
            cur = expect[0] if expect else None
            old = c["gold_expr"].get("node")
            hit_cur = any(cg.id_match(i, cur) for i in ids) if cur else False
            # 旧条目被召回但带 superseded_by 标记 → 也判定为「已感知取代」
            marked = False
            stale = False
            for h in hits:
                if old and cg.id_match(h["id"], old):
                    if h.get("superseded_by"):
                        marked = True
                    else:
                        stale = True
            if hit_cur or marked:
                row["status"] = "current"
            elif stale:
                row["status"] = "stale"
            else:
                row["status"] = "missing"
            row["correct"] = row["status"] == "current"
            row["reason"] = (
                f"gold 当前结论={cur} 旧结论={old}; status={row['status']}；"
                f"current 条件：召回含当前结论，或旧结论带 superseded_by 标记"
            )
        elif qtype == cg.NEGATIVE:
            row["noisy"] = len(ids) > 0
            row["reason"] = f"gold 恒空；召回 {len(ids)} 条 → noisy={len(ids) > 0}"
        else:
            raise SystemExit(f"未知题型 {qtype}")
        if qtype in (cg.CHAIN_ANCESTOR, cg.CHAIN_DESCENDANT):
            row["reason"] = (
                f"gold 链长 {len(expect)}; top-{topk} 内首个 gold rank={row['rank']}; "
                f"覆盖率={row['coverage']:.3f}（召回全集对 gold）"
            )

        rows.append(row)

    # 汇总
    def sub(t: str) -> List[Dict[str, Any]]:
        return [r for r in rows if r["type"] == t]

    chain = sub(cg.CHAIN_ANCESTOR) + sub(cg.CHAIN_DESCENDANT)
    interv = sub(cg.INTERVENTION)
    super_ = sub(cg.SUPERSESSION)
    neg = sub(cg.NEGATIVE)

    n_chain = len(chain)
    n_safe = sum(1 for r in interv if r["gold_label"] == "SAFE")
    n_warn = sum(1 for r in interv if r["gold_label"] == "WARNING")

    # 各指标点估计 + Wilson/正态 95% CI（k = 命中/正确数，n = 分母）
    k_hit = sum(1 for r in chain if r["hit"])
    k_hit1 = sum(1 for r in chain if r.get("rank") == 0)
    k_correct = sum(1 for r in interv if r["correct"])
    k_fp = sum(1 for r in interv if r["confusion"] == "FP")
    k_cur = sum(1 for r in super_ if r["correct"])
    k_noisy = sum(1 for r in neg if r["noisy"])

    cis: Dict[str, Any] = {
        "chain_hit_at_k": wilson_ci(k_hit, n_chain),
        "chain_hit_at_1": wilson_ci(k_hit1, n_chain),
        "chain_cov": mean_ci([r["coverage"] for r in chain]),
        "intervention_acc": wilson_ci(k_correct, len(interv)),
        "false_alarm_rate": wilson_ci(k_fp, n_safe),
        "supersession_acc": wilson_ci(k_cur, len(super_)),
        "negative_noise_rate": wilson_ci(k_noisy, len(neg)),
    }

    summary: Dict[str, Any] = {
        "n_total": len(rows),
        "n_dataset": len(dataset),
        "scored": len(rows),
        "excluded_missing": len(missing),
        "missing_predictions": missing,
        "params": {"topk": topk, "min_score": min_score},
        "distribution": {
            t: sum(1 for r in rows if r["type"] == t) for t in cg.ALL_TYPES
        },
        "cis": cis,
        "chain": {
            "n": n_chain,
            "hit_at_k": (k_hit / n_chain) if n_chain else 0.0,
            "hit_at_1": (k_hit1 / n_chain) if n_chain else 0.0,
            "coverage_at_k": (sum(r["coverage"] for r in chain) / n_chain) if n_chain else 0.0,
            "by_type": {
                t: {
                    "n": len(sub(t)),
                    "hit_at_k": (sum(1 for r in sub(t) if r["hit"]) / len(sub(t))) if sub(t) else 0.0,
                    "hit_at_k_ci": wilson_ci(sum(1 for r in sub(t) if r["hit"]), len(sub(t))),
                }
                for t in (cg.CHAIN_ANCESTOR, cg.CHAIN_DESCENDANT)
            },
        },
        "intervention": {
            "n": len(interv),
            "n_warning": n_warn,
            "n_safe": n_safe,
            "accuracy": (k_correct / len(interv)) if len(interv) else 0.0,
            "confusion": {k: sum(1 for r in interv if r["confusion"] == k) for k in ("TP", "FP", "FN", "TN")},
            # 抑制误报率：gold=SAFE（distractor，什么都没被阻止）却报了 WARNING 的比例
            "false_alarm_rate": (
                k_fp / n_safe if n_safe else 0.0
            ),
        },
        "supersession": {
            "n": len(super_),
            "accuracy": (k_cur / len(super_)) if super_ else 0.0,
            "current": sum(1 for r in super_ if r["status"] == "current"),
            "stale": sum(1 for r in super_ if r["status"] == "stale"),
            "missing": sum(1 for r in super_ if r["status"] == "missing"),
        },
        "negative": {
            "n": len(neg),
            "noise_rate": (k_noisy / len(neg)) if neg else 0.0,
            "noisy": k_noisy,
        },
    }
    return {"summary": summary, "rows": rows}


def metric_vector(summary: Dict[str, Any]) -> Dict[str, float]:
    """两臂对照用的六项指标向量（正向指标越大越好，误报/噪声越小越好）。"""
    return {
        "chain_hit_at_k": summary["chain"]["hit_at_k"],
        "chain_cov": summary["chain"]["coverage_at_k"],
        "intervention_acc": summary["intervention"]["accuracy"],
        "false_alarm_rate": summary["intervention"]["false_alarm_rate"],
        "supersession_acc": summary["supersession"]["accuracy"],
        "negative_noise_rate": summary["negative"]["noise_rate"],
    }


def render_text(result: Dict[str, Any], arm_label: str = "") -> str:
    s = result["summary"]
    p = s["params"]
    lines = []
    lines.append("=== agimem 判分结果 ===")
    if arm_label:
        lines.append(f"!! 本臂：{arm_label}（合成树已写入该隔离库，属真能力分；语料全合成，外推需另证）")
    else:
        lines.append("!! 注意：若被测库未导入合成因果树，本结果是「题库不在库」的检索结果，不是因果能力分。")
    lines.append(f"题量 {s['scored']}/{s['n_dataset']} | topk={p['topk']} | min_score={p['min_score']}")
    if s["excluded_missing"]:
        mode = "已剔除(--partial)" if s["scored"] < s["n_dataset"] else "按 0 分计入"
        lines.append(f"!! 缺预测 {s['excluded_missing']} 题（{mode}）: {s['missing_predictions']}")
    dist = s.get("distribution", {})
    lines.append("题型分布: " + " | ".join(f"{t}={dist.get(t, 0)}" for t in cg.ALL_TYPES))
    c = s["chain"]
    cis = s.get("cis", {})
    lines.append(f"[因果链追溯]  n={c['n']}  链命中率 hit@{p['topk']}={c['hit_at_k']:.3f}  "
                 f"hit@1={c['hit_at_1']:.3f}  链覆盖率={c['coverage_at_k']:.3f}")
    lines.append(f"    95%CI hit@{p['topk']}={fmt_ci(cis.get('chain_hit_at_k', {}))}  "
                 f"hit@1={fmt_ci(cis.get('chain_hit_at_1', {}))}  "
                 f"cov={fmt_ci(cis.get('chain_cov', {}))}")
    for t, v in c["by_type"].items():
        lines.append(f"    - {t}: n={v['n']} hit@{p['topk']}={v['hit_at_k']:.3f} "
                     f"CI={fmt_ci(v.get('hit_at_k_ci', {}))}")
    i = s["intervention"]
    safe_n = i["confusion"]["TN"] + i["confusion"]["FP"]
    lines.append(f"[干预预警]     n={i['n']}  预警准确率={i['accuracy']:.3f}  "
                 f"混淆 TP/FP/FN/TN={i['confusion']['TP']}/{i['confusion']['FP']}/"
                 f"{i['confusion']['FN']}/{i['confusion']['TN']}  "
                 f"抑制误报率(干扰项)={i['false_alarm_rate']:.3f} (分母 {safe_n})")
    lines.append(f"    95%CI acc={fmt_ci(cis.get('intervention_acc', {}))}  "
                 f"false_alarm={fmt_ci(cis.get('false_alarm_rate', {}))}")
    u = s["supersession"]
    lines.append(f"[软取代感知]   n={u['n']}  取代正确率={u['accuracy']:.3f}  "
                 f"current/stale/missing={u['current']}/{u['stale']}/{u['missing']}  "
                 f"95%CI={fmt_ci(cis.get('supersession_acc', {}))}")
    n = s["negative"]
    lines.append(f"[负样本噪声]   n={n['n']}  负样本噪声率={n['noise_rate']:.3f}  "
                 f"噪声题数={n['noisy']}/{n['n']}  "
                 f"95%CI={fmt_ci(cis.get('negative_noise_rate', {}))}")
    d = s.get("delta_vs")
    if d:
        lines.append(f"--- Δ（本臂 − 对照臂 {d['path']}，同题面同判分）---")
        for k, v in d["metrics"].items():
            lines.append(f"    {k}: {v:+.3f}")
    b = s.get("baselines")
    if b:
        lines.append("--- 基线对照（合成臂，非真库）---")
        lines.append(f"    perfect: {b['perfect']}")
        lines.append(f"    adversarial: {b['adversarial']}")
    return "\n".join(lines)


def render_panel(result: Dict[str, Any], baselines: Optional[Dict[str, Any]] = None,
                 top_drill: int = 0, arm_label: str = "") -> str:
    """人读指标面板（Markdown）：题量/分布 + 点估计+95%CI + 基线对照 + 单题下钻。"""
    s = result["summary"]
    p = s["params"]
    cis = s.get("cis", {})
    dist = s.get("distribution", {})
    c, i, u, n = s["chain"], s["intervention"], s["supersession"], s["negative"]

    L: List[str] = []
    L.append("# agimem 指标面板")
    L.append("")
    if arm_label:
        L.append(f"> **本臂：{arm_label}。**")
        L.append(">")
        L.append("> **醒目声明：被测隔离库已写入合成因果树（143 节点），下表是该记忆系统在本语料上的"
                 "检索层真能力分；但语料全合成、gold 由树结构机械推导、且 supersession 为 oracle 口径，"
                 "外推到真实业务需另证。**")
    else:
        L.append("> **醒目声明：若被测库未导入合成因果树，下表全部数字是「题库不在被测库」的检索结果，"
                 "**不是因果能力分**，不得包装成系统能力。**")
    L.append("")
    L.append(f"- 判分参数：topk={p['topk']}，min_score={p['min_score']}")
    L.append(f"- 判分题量：{s['scored']}/{s['n_dataset']}"
             + (f"（缺预测 {s['excluded_missing']} 题按 0 分计入）" if s["excluded_missing"] else ""))
    L.append(f"- 单题权重：1/{s['n_dataset']} ≈ {100.0 / max(1, s['n_dataset']):.2f}pp"
             "（26 题时 1 条≈3.8pp，扩集后 1 条≤0.83pp 才够看趋势）")
    L.append("")
    L.append("## 一、题量与题型分布")
    L.append("")
    L.append("| 题型 | 题数 | 占比 |")
    L.append("|---|---:|---:|")
    for t in cg.ALL_TYPES:
        k = dist.get(t, 0)
        L.append(f"| {t} | {k} | {k / max(1, s['n_dataset']):.1%} |")
    L.append(f"| **合计** | **{s['n_dataset']}** | 100% |")
    L.append("")
    L.append("## 二、指标点估计与 95% 置信区间")
    L.append("")
    L.append("比例类指标用 Wilson score 区间；链覆盖率用正态近似均值区间。")
    L.append("")
    L.append("| 指标 | 点估计 | 95% CI | n(分母) | 方向 |")
    L.append("|---|---:|---|---:|---|")
    rows_ci = [
        (f"chain_hit@{p['topk']}", cis.get("chain_hit_at_k", {}), c["n"], "越高越好"),
        ("chain_hit@1", cis.get("chain_hit_at_1", {}), c["n"], "越高越好"),
        ("chain_cov", cis.get("chain_cov", {}), c["n"], "越高越好"),
        ("intervention_acc", cis.get("intervention_acc", {}), i["n"], "越高越好"),
        ("false_alarm_rate", cis.get("false_alarm_rate", {}), i["n_safe"], "越低越好"),
        ("supersession_acc", cis.get("supersession_acc", {}), u["n"], "越高越好"),
        ("negative_noise_rate", cis.get("negative_noise_rate", {}), n["n"], "越低越好"),
    ]
    for name, ci, nn, direction in rows_ci:
        L.append(f"| `{name}` | {fmt_ci(ci, 4).split(' [')[0]} | {fmt_ci(ci)} | {nn} | {direction} |")
    L.append("")
    L.append(f"干预混淆矩阵 TP/FP/FN/TN = "
             f"{i['confusion']['TP']}/{i['confusion']['FP']}/{i['confusion']['FN']}/{i['confusion']['TN']}"
             f"（WARNING n={i['n_warning']}，SAFE n={i['n_safe']}）；"
             f"取代 current/stale/missing = {u['current']}/{u['stale']}/{u['missing']}。")
    L.append("")
    if baselines:
        L.append("## 三、基线对照（合成 recall 臂，非真库）")
        L.append("")
        L.append("| 指标 | 本臂 | perfect | adversarial |")
        L.append("|---|---:|---:|---:|")
        metric_rows = [
            ("chain_hit@k", "chain_hit_at_k"),
            ("chain_cov", "chain_cov"),
            ("intervention_acc", "intervention_acc"),
            ("false_alarm_rate", "false_alarm_rate"),
            ("supersession_acc", "supersession_acc"),
            ("negative_noise_rate", "negative_noise_rate"),
        ]
        self_v = metric_vector(s)
        for label, key in metric_rows:
            pv = baselines.get("perfect", {}).get(key)
            av = baselines.get("adversarial", {}).get(key)
            L.append(f"| `{label}` | {self_v.get(key, float('nan')):.3f} | "
                     f"{'n/a' if pv is None else f'{pv:.3f}'} | "
                     f"{'n/a' if av is None else f'{av:.3f}'} |")
        L.append("")
        L.append("perfect/adversarial 由 `selftest.py` 生成的合成 fixture 判出，"
                 "只证明判分器两极正确，不代表任何真实系统水平。")
        L.append("")
    L.append("## 四、单题明细下钻（qid → gold → top-k → 判分理由）")
    L.append("")
    drill = result["rows"]
    if top_drill and top_drill < len(drill):
        drill = drill[:top_drill]
    L.append("| qid | 题型 | gold | top-k 召回 | 判分理由 |")
    L.append("|---|---|---|---|---|")
    for r in drill:
        gold = ",".join(r.get("gold") or []) or (r.get("gold_label") or "∅")
        top = ",".join(h["id"] for h in r.get("top", [])) or "∅"
        reason = (r.get("reason") or "").replace("|", "/").replace("\n", " ")
        L.append(f"| {r['qid']} | {r['type']} | {gold} | {top} | {reason} |")
    if not top_drill or top_drill >= len(result["rows"]):
        L.append(f"（共 {len(result['rows'])} 题，全部列出）")
    L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="RespireCausalBench 判分")
    ap.add_argument("--dataset", default="dataset/causal_evalset.jsonl")
    ap.add_argument("--tree", default="data/tree.json")
    ap.add_argument("--predictions", help="recall 输出 JSONL（不给则仅做 gold 对账）")
    ap.add_argument("--topk", type=int, default=5)
    ap.add_argument("--min-score", type=float, default=0.0,
                    help="低于该 score 的召回不计入（对齐 recall 阈值闸）")
    ap.add_argument("--verify-only", action="store_true", help="只做 gold 机械复现对账")
    ap.add_argument("--partial", action="store_true",
                    help="只判有预测的题（缺预测不计入分母）；缺省缺预测按 0 分计")
    ap.add_argument("--delta", metavar="ARM_B",
                    help="对照臂预测文件（如无树/BM25-only）；同题面同判分，输出 Δ=本臂−对照臂")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    ap.add_argument("--panel", metavar="PATH",
                    help="写出人读 Markdown 指标面板（含 CI、基线对照、单题下钻）")
    ap.add_argument("--panel-limit", type=int, default=0,
                    help="面板单题下钻最多列多少题（0=全列）")
    ap.add_argument("--arm-label", default="",
                    help="臂名（如「隔离库真跑」）；给了就把醒目标注改成能力分版")
    ap.add_argument("--baselines", action="store_true",
                    help="面板里附 perfect/adversarial 两基线对照（需先跑 selftest 生成 fixtures）")
    args = ap.parse_args()

    tree = cg.load_tree(args.tree)
    dataset = load_jsonl(args.dataset)

    errors = verify_gold(dataset, tree)
    if errors:
        print("[verify] FAIL — gold 无法机械复现：", file=sys.stderr)
        for e in errors:
            print("  - " + e, file=sys.stderr)
        return 1
    if args.verify_only:
        msg = f"[verify] OK — {len(dataset)} 题 gold 全部由树结构重算一致"
        print(json.dumps({"verify": "ok", "n": len(dataset)}) if args.json else msg)
        return 0

    if not args.predictions:
        print("缺 --predictions（或用 --verify-only 只做对账）", file=sys.stderr)
        return 2

    preds = index_predictions(args.predictions)
    result = score(dataset, tree, preds, args.topk, args.min_score, partial=args.partial)
    if args.delta:
        other = score(dataset, tree, index_predictions(args.delta),
                      args.topk, args.min_score, partial=args.partial)
        self_v, other_v = metric_vector(result["summary"]), metric_vector(other["summary"])
        result["summary"]["delta_vs"] = {
            "path": args.delta,
            "self": self_v,
            "other": other_v,
            "metrics": {k: self_v[k] - other_v[k] for k in self_v},
        }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result, args.arm_label))
    if args.panel:
        baselines = None
        if args.baselines:
            baselines = {}
            for name in ("perfect", "adversarial"):
                path = os.path.join(HERE, "fixtures", f"{name}.jsonl")
                if os.path.exists(path):
                    b = score(dataset, tree, index_predictions(path),
                              args.topk, args.min_score, partial=False)
                    baselines[name] = metric_vector(b["summary"])
            result["summary"]["baselines"] = baselines
        panel = render_panel(result, baselines=baselines, top_drill=args.panel_limit,
                             arm_label=args.arm_label)
        with open(args.panel, "w", encoding="utf-8") as f:
            f.write(panel + "\n")
        print(f"[panel] 写出 {args.panel}", file=sys.stderr)
        # 机器可读 summary（JSON）：与面板同源，便于程序消费
        json_path = args.panel[:-3] + ".json" if args.panel.endswith(".md") else args.panel + ".json"
        summary_doc = {
            "schema": "agimem-score-summary/1",
            "warning": (("本臂为隔离库真跑：合成因果树已入库，数字属检索层真能力分；"
                         "语料全合成、gold 由树结构机械推导，外推需另证")
                        if args.arm_label else
                        ("若被测库未导入合成因果树，本结果是「题库不在库」的检索结果，"
                         "不是因果能力分")),
            "arm_label": args.arm_label,
            "params": result["summary"]["params"],
            "n_dataset": result["summary"]["n_dataset"],
            "scored": result["summary"]["scored"],
            "distribution": result["summary"].get("distribution"),
            "metrics": metric_vector(result["summary"]),
            "cis": result["summary"].get("cis"),
            "chain": result["summary"]["chain"],
            "intervention": result["summary"]["intervention"],
            "supersession": result["summary"]["supersession"],
            "negative": result["summary"]["negative"],
            "baselines": baselines,
            "per_question": [
                {
                    "qid": r["qid"], "type": r["type"],
                    "gold": r.get("gold"), "gold_label": r.get("gold_label"),
                    "top": r.get("top"),
                    "verdict": {k: r.get(k) for k in
                                ("hit", "rank", "coverage", "pred_label", "correct",
                                 "confusion", "status", "noisy") if k in r},
                    "reason": r.get("reason"),
                }
                for r in result["rows"]
            ],
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary_doc, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"[panel] 写出 {json_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

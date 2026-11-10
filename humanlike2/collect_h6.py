#!/usr/bin/env python3
"""collect_h6.py — H6 隔离库真跑：把合成语料写进隔离 rsrs 库，再逐题召回。

三件套（既证法，见 humanlike2/README.md §五 与记忆 739fbbc7）：
  1. 清空 RSRS_/ONEMEMORY_/RESPIRE_ 前缀 env，设 RSRS_DATA_DIR + 独立 RSRS_RPC_PORT + 占位 super；
  2. `rsrs keygen --json` 取真 super → `rsrs --runtime-internal --stop` 停占位 runtime；
  3. `rsrs import` 批写 → 等索引 ready（判据：探针 recall 的 embedding_model 非 null 且
     status.state=ready；**勿信 worker_active**，它恒 true）→ 逐题 recall → 停自己的 runtime。

P5 四事件按 `insert_rank` 排序后再 import，`created_at` 用节点上的显式时间戳——
这同时验证 T24 未验证项 6：正文互异时显式 created_at 是否真落库（用 show 核值）。

用法：
    python3 collect_h6.py --run --root /tmp/agimem-h6-iso --port 16340

脱敏：命中标题用 `｜<hl2 条目号>` 映射回合成 id，未映射的写 `extNNNN` 占位；
仓里不出现隔离库 UUID（ancestors 夹真 UUID 的坑已知，本层不读 ancestors）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import isolated_lib as il  # noqa: E402  agimem/isolated_lib.py（H2 同源，不改它）

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.join(HERE, "data", "h6_tree.json")
DATASET = os.path.join(HERE, "dataset", "h6_evalset.jsonl")
OUT_DIR = os.path.join(HERE, "results")
TITLE_SEP = "｜"


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def node_to_item(n: Dict[str, Any]) -> Dict[str, Any]:
    """合成节点 → import 条目。

    标题/正文都带 hl2 条目号：标题用于召回后解析回合成 id，正文尾部防 import 同文去重。
    P5 的 created_at 直接用节点上的显式时间戳（这是四象限的唯一自变量）。
    """
    return {
        "title": f"{n['title']}{TITLE_SEP}{n['id']}",
        "content": f"{n['content']}\n（条目 {n['id']}；场景 {n['scenario']}）",
        "kind": "context",
        "importance": "important",
        "created_at": n.get("created_at") or f"{n.get('ts', '2026-06-01')}T09:00:00Z",
        "tags": [n.get("scenario", ""), n.get("role", "")],
    }


def title_to_node(title: str) -> Optional[str]:
    if not title or TITLE_SEP not in title:
        return None
    cand = title.rsplit(TITLE_SEP, 1)[-1].strip()
    return cand if cand.startswith("hl2") else None


def plan(tree: Dict[str, Any], dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
    """只打印采集计划，不执行任何写入。"""
    nodes = tree["nodes"]
    by_role: Dict[str, int] = {}
    for n in nodes:
        by_role[n["role"]] = by_role.get(n["role"], 0) + 1
    p5 = [n for n in nodes if n["role"] == "order"]
    p5_sorted = sorted(p5, key=lambda n: n["insert_rank"])
    return {
        "nodes": len(nodes),
        "by_role": by_role,
        "questions": len(dataset),
        "by_type": {t: sum(1 for q in dataset if q["type"] == t) for t in
                    ["P1", "P2", "P3", "P4", "P5", "P6"]},
        "p5_insert_order_ok": [n["id"] for n in p5_sorted] == [n["id"] for n in p5],
        "p5_created_at_crossed": True,
        "note": "P5 按 insert_rank 排序后 import；created_at 与插入顺序十字交叉",
    }


def import_order(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """全节点按 insert_rank 升序：P5 四事件的插入顺序由它决定。

    其它角色的 insert_rank 也已按构造顺序分配，整体排序不改变它们的相对先后。
    """
    return sorted(nodes, key=lambda n: n["insert_rank"])


def probe_created_at(st: il.IsolatedStore, tree: Dict[str, Any]) -> Dict[str, Any]:
    """T24 未验证项 6：正文互异时，import 的显式 created_at 是否真落库。

    抽 P5 每组的 I/III 两格（created_at 早晚各一），用 show 读回 created_at 比对。
    只读 show，不写库。

    坑（本轮踩到）：`rsrs show` 只认**库内真 UUID**，合成 id 报 no such entry、
    entry 恒空，会把探针误判成 0/24。必须先 `rsrs list` 建
    「标题尾 `｜<hl2 id>` → 真 UUID」映射，再用 UUID show。
    """
    # 1) 合成 id → 真 UUID（标题尾分隔符映射）
    p = il.run(["rsrs", "list", "--limit", "300", "--json"], st.env, timeout=300, check=False)
    d = il.parse_env(p.stdout) or {}
    id_map: Dict[str, str] = {}
    for e in (d.get("details") or []):
        t = e.get("title") or ""
        if TITLE_SEP in t:
            sid = t.rsplit(TITLE_SEP, 1)[-1].strip()
            if sid.startswith("hl2"):
                id_map[sid] = e.get("id") or ""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for n in tree["nodes"]:
        if n["role"] == "order":
            groups.setdefault(n["topic"], []).append(n)
    checks = []
    unmapped = 0
    for topic in sorted(groups):
        g = groups[topic]
        by_q = {n["attrs"]["quadrant"]: n for n in g}
        for quad in ("I", "III"):  # 早/晚 created 各取一格
            n = by_q[quad]
            uuid = id_map.get(n["id"])
            if not uuid:
                unmapped += 1
                checks.append({"id": n["id"], "quadrant": quad, "topic": topic,
                               "want_created_at": n["created_at"], "got_created_at": "",
                               "match": False, "rc": None, "unmapped": True})
                continue
            p = il.run(["rsrs", "show", uuid, "--json"], st.env, timeout=180, check=False)
            d = il.parse_env(p.stdout) or {}
            entry = ((d.get("details") or {}).get("entry")
                     or (d.get("summary") or {}).get("entry") or {})
            got = entry.get("created_at") or ""
            want = n["created_at"]
            checks.append({
                "id": n["id"], "quadrant": quad, "topic": topic,
                "want_created_at": want, "got_created_at": got,
                "match": got.startswith(want[:10]) if got else False,
                "rc": p.returncode, "unmapped": False,
            })
    ok = all(c["match"] for c in checks)
    return {"ok": ok, "n": len(checks), "n_match": sum(1 for c in checks if c["match"]),
            "unmapped": unmapped, "checks": checks,
            "note": "show 须用真 UUID；合成 id 报 no such entry"}


def run_collect(args: argparse.Namespace) -> int:
    with open(args.tree, encoding="utf-8") as f:
        tree = json.load(f)
    dataset = load_jsonl(args.dataset)
    p = plan(tree, dataset)
    print("[collect_h6] 采集计划：")
    print(json.dumps(p, ensure_ascii=False, indent=2))

    os.makedirs(OUT_DIR, exist_ok=True)
    st = il.IsolatedStore(args.root, args.tag, args.port, args.m3).open()
    stats: Dict[str, Any] = {"port": args.port, "root": args.root, "plan": p}
    try:
        # 1) 导入：按 insert_rank 排序，P5 四事件的插入顺序由此决定
        items = [node_to_item(n) for n in import_order(tree["nodes"])]
        t0 = time.time()
        pr = st.import_items(items)
        d = il.parse_env(pr.stdout) or {}
        summ = d.get("summary") or {}
        stats["import"] = {"rc": pr.returncode,
                           "imported": summ.get("imported"),
                           "duplicates": summ.get("duplicates"),
                           "local_total": summ.get("local_total"),
                           "elapsed_s": round(time.time() - t0, 1)}
        print(f"[collect_h6] import rc={pr.returncode} imported={summ.get('imported')} "
              f"duplicates={summ.get('duplicates')} local_total={summ.get('local_total')} "
              f"({stats['import']['elapsed_s']}s)")
        if pr.returncode != 0:
            print(pr.stdout[-400:], pr.stderr[-400:])
            return 1

        # 2) 等索引 ready（判据：embedding_model + state=ready，勿信 worker_active）
        t1 = time.time()
        ready = st.wait_index(expect_total=summ.get("local_total"), budget=900)
        stats["index"] = dict(ready, wait_s=round(time.time() - t1, 1))
        print(f"[collect_h6] index state={ready.get('state')} "
              f"embedding_model={ready.get('embedding_model')} "
              f"waited={stats['index']['wait_s']}s timeout={ready.get('timeout', False)}")
        if ready.get("timeout") or not ready.get("embedding_model"):
            print("[collect_h6] 索引未 ready，中止（不降级为 lexical）")
            return 1

        # 3) P5 created_at 落库探针（只读 show）
        ca = probe_created_at(st, tree)
        stats["created_at_probe"] = ca
        print(f"[collect_h6] created_at 落库探针: {ca['n_match']}/{ca['n']} match ok={ca['ok']}")

        # 3b) P3 全量 forget（T28 缺陷二：12 组全部真调 forget）
        # 流程：pre recall → forget 目标（真 UUID）→ post recall → 邻居 A/C show/recall
        forget_res = run_forget_all(st, dataset, tree)
        stats["forget"] = forget_res
        print(f"[collect_h6] forget 全量: groups={forget_res['n_groups']} "
              f"forget_ok={forget_res['n_forget_ok']} "
              f"target_gone={forget_res['n_target_gone']}/{forget_res['n_post']}")

        # 4) 逐题 recall（forget 已执行，post 题反映遗忘后状态）
        preds = []
        unmapped = 0
        t2 = time.time()
        for i, q in enumerate(dataset):
            r = st.recall(q["query"], args.limit)
            hits = []
            for h in r["hits"]:
                nid = title_to_node(h.get("title") or "")
                if nid is None:
                    unmapped += 1
                    nid = f"ext{unmapped:04d}"
                hits.append({"id": nid, "score": h.get("score")})
            preds.append({"qid": q["qid"], "query": q["query"], "hits": hits})
            if (i + 1) % 24 == 0:
                print(f"[collect_h6] recall {i + 1}/{len(dataset)} "
                      f"({round(time.time() - t2, 1)}s)")
        stats["recall"] = {"n": len(preds), "unmapped": unmapped,
                           "elapsed_s": round(time.time() - t2, 1)}
        pred_path = os.path.join(OUT_DIR, "h6-isolated-predictions.jsonl")
        with open(pred_path, "w", encoding="utf-8") as f:
            for r in preds:
                f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
        print(f"[collect_h6] 写出 {os.path.relpath(pred_path, HERE)} "
              f"({len(preds)} 题, unmapped={unmapped})")

        # 5) 判分
        import score_h6 as sh
        summary = sh.score_dataset(dataset, preds, tree["nodes"], topk=args.limit)
        summary["types"]["P3"]["forget_probe"] = forget_res
        summary["provenance"] = {
            "port": args.port, "root": args.root,
            "import": stats["import"], "index": stats["index"],
            "created_at_probe": {"ok": ca["ok"], "n": ca["n"], "n_match": ca["n_match"],
                                 "unmapped": ca.get("unmapped", 0)},
            "forget": {"n_groups": forget_res["n_groups"],
                       "n_forget_ok": forget_res["n_forget_ok"],
                       "n_target_gone": forget_res["n_target_gone"],
                       "n_post": forget_res["n_post"],
                       "n_neighbor_show_ok": forget_res["n_neighbor_show_ok"]},
            "recall": stats["recall"],
            "generator": "gen_h6.py", "seed": tree.get("seed"),
            "collect": f"collect_h6.py --run --port {args.port}",
            "defect_fix": "T28: P5 before 去引号 + P3 全量 forget",
        }
        out_path = os.path.join(OUT_DIR, "h6-isolated.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"[collect_h6] 写出 {os.path.relpath(out_path, HERE)} "
              f"等权总分={summary['composite_equal_weight']:.3f}")
        return 0
    finally:
        st.close()
        print("[collect_h6] 已停隔离 runtime（未碰 ~/.rsrs）")


def title_uuid_map(st: Any) -> Dict[str, str]:
    """`rsrs list` 建「标题尾 `｜<hl2 id>` → 库内真 UUID」映射。

    `rsrs show`/`rsrs forget` 都只认真 UUID，合成 id 报 no such entry（T27 已踩）。
    """
    p = il.run(["rsrs", "list", "--limit", "300", "--json"], st.env, timeout=300, check=False)
    d = il.parse_env(p.stdout) or {}
    m: Dict[str, str] = {}
    for e in (d.get("details") or []):
        t = e.get("title") or ""
        if TITLE_SEP in t:
            sid = t.rsplit(TITLE_SEP, 1)[-1].strip()
            if sid.startswith("hl2"):
                m[sid] = e.get("id") or ""
    return m


def run_forget_all(st: Any, dataset: List[Dict[str, Any]],
                   tree: Dict[str, Any]) -> Dict[str, Any]:
    """T28 缺陷二：12 组 P3 全部真调 forget。

    每组：pre recall（同题面）→ forget 目标（真 UUID）→ post recall（同题面）
    → 邻居 A/C 各 show 一次（确认不误删）。
    pre/post 题面相同，所以 post 的 recall 结果就是「遗忘后」状态；
    正式 144 题 recall 在 forget 之后统一跑，post 题自然反映遗忘后。
    """
    id_map = title_uuid_map(st)
    p3_qs = [q for q in dataset if q["type"] == "P3"]
    by_topic: Dict[str, Dict[str, Any]] = {}
    for q in p3_qs:
        by_topic.setdefault(q["gold_expr"].get("topic", ""), {})[q.get("subtype")] = q
    res = {"n_groups": 0, "n_forget_ok": 0, "n_target_gone": 0, "n_post": 0,
           "n_neighbor_show_ok": 0, "groups": []}
    for topic in sorted(by_topic):
        qs = by_topic[topic]
        pre = qs.get("pre")
        if not pre:
            continue
        e = pre["gold_expr"]
        target_s = e["gold"]
        keep_s = e.get("keep", [])
        target_u = id_map.get(target_s)
        res["n_groups"] += 1
        g = {"topic": topic, "target_synthetic": target_s}
        if not target_u:
            g["forget_rc"] = None
            g["error"] = "target not mapped"
            res["groups"].append(g)
            continue
        # pre recall（同题面）
        r_pre = st.recall(pre["query"], 5)
        ids_pre = [h["id"] for h in r_pre["hits"]]
        g["pre_target_in"] = target_s in ids_pre
        # forget 真 UUID
        p = il.run(["rsrs", "forget", target_u, "--json"], st.env, timeout=180, check=False)
        d = il.parse_env(p.stdout) or {}
        g["forget_rc"] = p.returncode
        g["forget_status"] = d.get("status")
        # 脱敏：forget_summary 含真 UUID（库内条目 id），只保留 deleted 布尔
        _summ = d.get("summary") or {}
        g["forget_summary"] = {"deleted": bool(_summ.get("deleted"))}
        if p.returncode == 0 and (d.get("summary") or {}).get("deleted"):
            res["n_forget_ok"] += 1
        # post recall（同题面，目标应已消失）
        r_post = st.recall(pre["query"], 5)
        ids_post = [h["id"] for h in r_post["hits"]]
        g["post_target_in"] = target_s in ids_post
        res["n_post"] += 1
        if not g["post_target_in"]:
            res["n_target_gone"] += 1
        # 邻居 A/C show 确认不误删
        g["neighbors"] = []
        for kid in keep_s:
            ku = id_map.get(kid)
            if not ku:
                g["neighbors"].append({"id": kid, "mapped": False})
                continue
            p2 = il.run(["rsrs", "show", ku, "--json"], st.env, timeout=120, check=False)
            d2 = il.parse_env(p2.stdout) or {}
            ok = d2.get("status") == "ok" and bool(((d2.get("details") or {}).get("entry") or {}).get("content"))
            g["neighbors"].append({"id": kid, "show_ok": ok})
            if ok:
                res["n_neighbor_show_ok"] += 1
        res["groups"].append(g)
        print(f"[collect_h6] forget {topic}: rc={g['forget_rc']} "
              f"pre_in={g['pre_target_in']} post_in={g['post_target_in']} "
              f"neighbors_ok={sum(1 for n in g['neighbors'] if n.get('show_ok'))}/{len(keep_s)}")
    res["neighbor_total"] = sum(len(g.get("neighbors", [])) for g in res["groups"])
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="H6 隔离库真跑")
    ap.add_argument("--tree", default=TREE)
    ap.add_argument("--dataset", default=DATASET)
    ap.add_argument("--root", default="/tmp/agimem-h6-iso")
    ap.add_argument("--tag", default="h6")
    ap.add_argument("--port", type=int, default=16341)
    ap.add_argument("--m3", default=il.M3_DEFAULT)
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true",
                    help="只打印计划，不写库（缺省行为）")
    ap.add_argument("--run", action="store_true", help="真跑：建库+导入+召回+判分")
    args = ap.parse_args()

    if not args.run:
        with open(args.tree, encoding="utf-8") as f:
            tree = json.load(f)
        dataset = load_jsonl(args.dataset)
        print("[collect_h6] 采集计划：")
        print(json.dumps(plan(tree, dataset), ensure_ascii=False, indent=2))
        print("[collect_h6] dry-run 结束：未写库、未启停 runtime、未碰 ~/.rsrs")
        print("[collect_h6] 真跑：--run --root /tmp/agimem-h6-iso --port 16341")
        return 0
    return run_collect(args)


if __name__ == "__main__":
    sys.exit(main())

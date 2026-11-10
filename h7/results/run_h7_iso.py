#!/usr/bin/env python3
"""H7 隔离库真跑（T44）。不改 gen_h7 / score_h7。

端口 16344，目录 /tmp/agimem-h7-iso。
import 不写 parent；用 rsrs list 把标题尾合成 id 映射真 UUID 后 attach。
产物只落合成 id。
L2：score_h7 的 mixed 分支不读召回（口径恒等），另计「召回 top-1 的链深 == gold hop_count」作真召回分。
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
H7 = os.path.dirname(HERE)
AGI = os.path.dirname(H7)
sys.path.insert(0, H7)
sys.path.insert(0, AGI)

import h7_gold as hg  # noqa: E402
import isolated_lib as il  # noqa: E402
import score_h7 as sc  # noqa: E402

TREE = os.path.join(H7, "data", "h7_tree.json")
DATASET = os.path.join(H7, "dataset", "h7_evalset.jsonl")
PRED = os.path.join(HERE, "h7-isolated-predictions.jsonl")
OUT = os.path.join(HERE, "h7-isolated.json")
BASELINE_L4 = 0.3333
SEP = "｜"


def load_jsonl(path: str):
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def sid_of(title: str):
    if not title or SEP not in title:
        return ""
    cand = title.rsplit(SEP, 1)[-1].strip()
    return cand if cand.startswith("h7") else ""


def list_map(st: il.IsolatedStore):
    p = il.run(["rsrs", "list", "--limit", "300", "--json"], st.env, timeout=300, check=False)
    d = il.parse_env(p.stdout) or {}
    rows = d.get("details") or d.get("items") or []
    out = {}
    for e in rows:
        if not isinstance(e, dict):
            continue
        sid = sid_of(e.get("title") or "")
        uid = e.get("id") or ""
        if sid and uid:
            out[sid] = uid
    return out, p.returncode, len(rows)


def main() -> int:
    tree = json.load(open(TREE, encoding="utf-8"))
    nodes = tree["nodes"]
    questions = load_jsonl(DATASET)
    by_id = {n["id"]: n for n in nodes}
    parent_n = sum(1 for n in nodes if n.get("parent"))
    print(f"[h7] nodes={len(nodes)} qs={len(questions)} parent={parent_n}", flush=True)

    st = il.IsolatedStore("/tmp", "agimem-h7-iso", 16344, il.M3_DEFAULT).open()
    print(f"[h7] store={st.dir} port={st.port}", flush=True)
    t0 = time.time()
    try:
        items = []
        for n in nodes:
            items.append({
                "title": f"{n['title']}{SEP}{n['id']}",
                "content": f"{n['content']}\n（条目 {n['id']}）",
                "kind": "context",
                "importance": "important",
                "created_at": n.get("created_at") or "2026-08-01T10:00:00Z",
                "tags": [n.get("scenario") or "", n.get("role") or ""],
            })
        imp = st.import_items(items)
        imp_d = il.parse_env(imp.stdout) or {}
        print(f"[h7] import rc={imp.returncode} {json.dumps(imp_d.get('summary') or {}, ensure_ascii=False)}",
              flush=True)
        ready = st.wait_index(expect_total=len(nodes), budget=900)
        model = str(ready.get("embedding_model") or "")
        print(f"[h7] index {json.dumps({k: ready.get(k) for k in ('state','local_total','embedding_model','waited_s','timeout')}, ensure_ascii=False)}",
              flush=True)
        if ready.get("timeout") or ready.get("state") != "ready" or "m3" not in model.lower():
            raise SystemExit(f"索引未就绪: state={ready.get('state')} model={model}")

        idmap, list_rc, list_n = list_map(st)
        print(f"[h7] list rc={list_rc} rows={list_n} mapped={len(idmap)}/{len(nodes)}", flush=True)

        ok = fail = 0
        fail_sids = []
        edges = [(n["id"], n["parent"]) for n in nodes if n.get("parent")]
        for i, (child, parent) in enumerate(edges, 1):
            cu, pu = idmap.get(child), idmap.get(parent)
            if not (cu and pu):
                fail += 1
                if len(fail_sids) < 8:
                    fail_sids.append({"child": child, "parent": parent, "why": "unmapped"})
                continue
            r = il.run(["rsrs", "attach", cu, "--parent", pu, "--json"],
                       st.env, timeout=180, check=False)
            if r.returncode == 0:
                ok += 1
            else:
                fail += 1
                if len(fail_sids) < 8:
                    fail_sids.append({"child": child, "parent": parent, "rc": r.returncode})
            if i % 20 == 0:
                print(f"[h7] attach {i}/{len(edges)} ok={ok} fail={fail}", flush=True)
        print(f"[h7] attach ok={ok} fail={fail} planned={len(edges)}", flush=True)

        preds = []
        l2_rows = []
        for q in questions:
            rec = st.recall(q["query"], 5)
            hits = []
            for h in rec["hits"]:
                sid = sid_of(h.get("title") or "")
                if not sid:
                    continue
                hits.append({"id": sid, "score": h.get("score")})
            preds.append({"qid": q["qid"], "query": q["query"], "hits": hits,
                          "recall_rc": rec["rc"], "embedding_model": rec.get("embedding_model")})
            if q["type"] == "L2":
                top = hits[0]["id"] if hits else ""
                measured = hg.chain_depth(top, by_id) if top in by_id else None
                want = q["gold_expr"]["hop_count"]
                l2_rows.append({"qid": q["qid"], "want": want, "measured": measured,
                                "top1": top, "subject": q["gold_expr"].get("subject"),
                                "correct": measured == want,
                                "subject_hit": top == q["gold_expr"].get("subject")})
        with open(PRED, "w", encoding="utf-8") as f:
            for row in preds:
                f.write(json.dumps({"qid": row["qid"], "query": row["query"], "hits": row["hits"]},
                                   ensure_ascii=False) + "\n")

        scored = sc.score_dataset(questions, preds, nodes, 5)["summary"]
        l2_k = sum(1 for r in l2_rows if r["correct"])
        l2_sub = sum(1 for r in l2_rows if r["subject_hit"])
        l2_real = sc.wilson_ci(l2_k, len(l2_rows))
        l2_subject = sc.wilson_ci(l2_sub, len(l2_rows))
        l4 = scored["L4"]["hit@1"]["point"]
        delta = None if l4 is None else round(l4 - BASELINE_L4, 4)
        if l4 is None:
            read = "未计分"
        elif abs(l4 - BASELINE_L4) <= 0.05:
            read = "字面匹配"
        elif l4 > BASELINE_L4:
            read = "高于字面基线"
        else:
            read = "低于字面基线"
        doc = {
            "schema": "agimem-h7-isolated/1",
            "port": 16344,
            "store": "/tmp/agimem-h7-iso",
            "n_nodes": len(nodes),
            "n_questions": len(questions),
            "parent_edges_planned": len(edges),
            "import_rc": imp.returncode,
            "import_summary_keys": sorted((imp_d.get("summary") or {}).keys()),
            "index": {k: ready.get(k) for k in ("state", "local_total", "embedding_model", "waited_s")},
            "list_mapped": len(idmap),
            "attach_ok": ok,
            "attach_fail": fail,
            "attach_fail_sids": fail_sids,
            "score_h7": scored,
            "l2_real_recall": {
                "definition": "top-1 合成 id 的 parent 链深 == gold hop_count；score_h7 的 L2 不读召回，不作能力分",
                "accuracy": l2_real,
                "subject_hit@1": l2_subject,
                "rows": l2_rows,
            },
            "l4_semantic_increment": {
                "baseline": BASELINE_L4,
                "hit@1": l4,
                "delta": delta,
                "reading": read,
            },
            "elapsed_s": round(time.time() - t0, 1),
            "recall_model_set": sorted({str(p.get("embedding_model")) for p in preds}),
        }
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print(f"[h7] wrote {OUT} elapsed={doc['elapsed_s']}s L4={l4} delta={delta} read={read}", flush=True)
        print(f"[h7] L2 real {l2_k}/{len(l2_rows)} subject_hit {l2_sub}/{len(l2_rows)}", flush=True)
        return 0
    finally:
        st.close()


if __name__ == "__main__":
    sys.exit(main())

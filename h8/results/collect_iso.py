#!/usr/bin/env python3
"""H8 隔离库真跑（只采集，不改 gen_h8 / score_h8）。

三件套：过滤 RSRS_/ONEMEMORY_/RESPIRE_ 后设独立目录、独立端口、独立 super。
就绪 = embedding_model=m3 且 state=ready（不看 worker_active）。
import 后 list 映射真 UUID，有 parent 的再 attach；64 题 recall 后只落合成 id，交给 score_h8。
真库 ~/.rsrs 不参与（不走 --client-only，不 recall/show/forget 默认库）。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
H8 = os.path.dirname(HERE)
sys.path.insert(0, H8)

import score_h8 as sc  # noqa: E402

TREE = os.path.join(H8, "data", "h8_tree.json")
EVALSET = os.path.join(H8, "dataset", "h8_evalset.jsonl")
LEXICAL = os.path.join(H8, "fixtures", "h8-lexical.jsonl")
ROOT = "/tmp/agimem-h8-iso"
TAG = "h8"
PORT = 16345
M3 = os.path.expanduser("~/.rsrs/models/bge-m3")
SEP = "｜"
UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
PRED_OUT = os.path.join(HERE, "h8-iso-predictions.jsonl")
PANEL_OUT = os.path.join(HERE, "h8-iso-panel.json")


def run(args, env, timeout=600, check=True):
    p = subprocess.run(args, env=env, capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        sys.stderr.write(
            f"[fail] {' '.join(args[:4])} rc={p.returncode}\n"
            f"{p.stdout[-400:]}\n{p.stderr[-300:]}\n"
        )
    return p


def parse_env(stdout: str):
    brace = stdout.find("{")
    if brace < 0:
        return None
    try:
        return json.loads(stdout[brace:])
    except json.JSONDecodeError:
        return None


def syn_from_title(title: str) -> str:
    if SEP not in (title or ""):
        return ""
    return title.rsplit(SEP, 1)[-1].strip()


def main() -> int:
    tree = json.load(open(TREE, encoding="utf-8"))
    nodes = tree["nodes"]
    questions = sc.load_jsonl(EVALSET)
    by_id = {n["id"]: n for n in nodes}
    print(f"[data] nodes={len(nodes)} questions={len(questions)} "
          f"parents={sum(1 for n in nodes if n.get('parent'))}", flush=True)

    iso = os.path.join(ROOT, TAG)
    if os.path.isdir(iso):
        shutil.rmtree(iso)
    os.makedirs(iso, exist_ok=True)
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("RSRS_", "ONEMEMORY_", "RESPIRE_"))}
    env.update(
        RSRS_DATA_DIR=iso,
        RSRS_RPC_PORT=str(PORT),
        RSRS_SUPER="A3-000000-000000-000000-000000-000000-000000",
        RSRS_NO_AUTOSYNC="1",
        RSRS_UPDATE_CHECK="0",
        RSRS_ENGINE="cpu",
        RSRS_M3_DIR=M3,
        RSRS_FEEDBACK="0",
        RSRS_ABLATE="hot",
    )
    t0 = time.time()
    p = run(["rsrs", "keygen", "--json"], env, timeout=600)
    super_ = ((parse_env(p.stdout) or {}).get("summary") or {}).get("super") or ""
    if not super_:
        print("[iso] keygen 未返回 super", file=sys.stderr)
        return 2
    env["RSRS_SUPER"] = super_
    run(["rsrs", "--runtime-internal", "--stop"], env, timeout=180, check=False)
    time.sleep(0.5)
    print(f"[iso] dir={iso} port={PORT} keygen {time.time()-t0:.0f}s", flush=True)

    items = []
    for n in nodes:
        if SEP in n["title"] or SEP in n["content"]:
            print(f"[iso] 分隔符已在语料里 {n['id']}", file=sys.stderr)
            return 2
        items.append({
            "title": f"{n['title']}{SEP}{n['id']}",
            "content": f"{n['content']}\n（条目 {n['id']}）",
            "kind": "context",
            "importance": "important",
            "created_at": n["created_at"],
            "tags": ["h8", n["role"]],
        })
    imp_path = os.path.join(iso, "import.json")
    json.dump(items, open(imp_path, "w", encoding="utf-8"), ensure_ascii=False)
    p = run(["rsrs", "import", imp_path, "--json"], env, timeout=3600)
    summary = (parse_env(p.stdout) or {}).get("summary") or {}
    print(f"[iso] import {summary}", flush=True)
    imported = summary.get("imported")
    if imported != len(nodes):
        print(f"[iso] imported={imported} ≠ {len(nodes)}，停止（可能被正文去重吞）",
              file=sys.stderr)
        return 2

    # 就绪：空转探针的 embedding_model=m3 且 status.state=ready
    deadline = time.time() + 1200
    ready = None
    while time.time() < deadline:
        st = parse_env(run(["rsrs", "status", "--json"], env, timeout=180, check=False).stdout) or {}
        ri = (st.get("summary") or {}).get("retrieval_index") or {}
        pr = parse_env(run(
            ["rsrs", "recall", "预热探针", "--limit", "1", "--json", "--titles"],
            env, timeout=180, check=False).stdout) or {}
        emb = (pr.get("summary") or {}).get("embedding_model")
        state = {
            "state": ri.get("state"),
            "local_total": (st.get("summary") or {}).get("local_total"),
            "embedding_model": emb,
        }
        if emb == "m3" and state["state"] == "ready" and state["local_total"] == len(nodes):
            ready = state
            ready["waited_s"] = round(time.time() - t0, 1)
            break
        time.sleep(4)
    print(f"[iso] ready {ready}", flush=True)
    if not ready:
        print("[iso] 索引未就绪", file=sys.stderr)
        return 2

    listed = parse_env(run(
        ["rsrs", "list", "--limit", "400", "--metadata", "--json"],
        env, timeout=300).stdout) or {}
    rows = listed.get("details") or []
    uuid_of = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        sid = syn_from_title(row.get("title") or "")
        full = row.get("id") or ""
        if sid and full:
            uuid_of[sid] = full
    print(f"[iso] list rows={len(rows)} mapped={len(uuid_of)}", flush=True)
    if len(uuid_of) != len(nodes):
        print("[iso] UUID 映射不全，停止", file=sys.stderr)
        return 2

    attached = 0
    attach_fail = 0
    for n in nodes:
        parent = n.get("parent") or ""
        if not parent:
            continue
        p = run(
            ["rsrs", "attach", uuid_of[n["id"]], "--parent", uuid_of[parent], "--json"],
            env, timeout=180, check=False,
        )
        if p.returncode == 0:
            attached += 1
        else:
            attach_fail += 1
            sys.stderr.write(f"[attach fail] {n['id']} -> {parent} rc={p.returncode}\n")
    print(f"[iso] attach ok={attached} fail={attach_fail}", flush=True)

    preds = []
    t1 = time.time()
    for i, q in enumerate(questions):
        rec = parse_env(run(
            ["rsrs", "recall", q["query"], "--limit", "5", "--json", "--titles"],
            env, timeout=180, check=False).stdout) or {}
        hits = []
        for h in rec.get("details") or []:
            if not isinstance(h, dict):
                continue
            title = h.get("title") or ""
            sid = syn_from_title(title)
            if sid:
                hits.append({"id": sid, "score": h.get("score")})
        preds.append({"qid": q["qid"], "query": q["query"], "hits": hits,
                      "n_raw": len(rec.get("details") or [])})
        if (i + 1) % 16 == 0:
            print(f"  recall {i+1}/{len(questions)} {time.time()-t1:.0f}s", flush=True)

    blob = json.dumps(preds, ensure_ascii=False)
    if UUID_RE.search(blob):
        print("[out] 预测含 UUID，拒绝落盘", file=sys.stderr)
        return 2
    with open(PRED_OUT, "w", encoding="utf-8") as f:
        for row in preds:
            slim = {"qid": row["qid"], "query": row["query"], "hits": row["hits"]}
            f.write(json.dumps(slim, ensure_ascii=False) + "\n")

    scored = sc.score_dataset(questions, preds, nodes, topk=5)
    lexical = sc.score_dataset(questions, sc.load_jsonl(LEXICAL), nodes, topk=5)
    c1 = scored["summary"]["C1"]["hit@1"]["point"]
    lex = lexical["summary"]["C1"]["hit@1"]["point"]
    panel = {
        "task": "T45 H8 隔离库真跑",
        "round": "本轮实测",
        "isolated": {"dir": iso, "port": PORT, "ready": ready,
                     "imported": imported, "mapped": len(uuid_of),
                     "attached": attached, "attach_fail": attach_fail},
        "elapsed_s": round(time.time() - t0, 1),
        "summary": scored["summary"],
        "lexical_C1_hit@1": lex,
        "C1_hit@1_minus_lexical": None if c1 is None or lex is None else round(c1 - lex, 4),
        "note": "落盘只有合成 id；真 UUID 仅在进程内存映射，不写入仓",
    }
    # 逐题也只留合成 id
    panel_rows = []
    for r in scored["rows"]:
        panel_rows.append({k: r[k] for k in
                           ("qid", "type", "subtype", "correct", "hit_at_5",
                            "rank", "stale_top1", "stale_ahead", "aged_hit", "not_buried")
                           if k in r or k in ("qid", "type")})
    panel["rows"] = panel_rows
    text = json.dumps(panel, ensure_ascii=False, indent=1)
    if UUID_RE.search(text):
        print("[out] panel 含 UUID，拒绝落盘", file=sys.stderr)
        return 2
    open(PANEL_OUT, "w", encoding="utf-8").write(text + "\n")
    sc.print_panel(scored["summary"])
    print(f"[cmp] C1 hit@1={c1} lexical={lex} delta={panel['C1_hit@1_minus_lexical']}")
    print(f"[out] {PRED_OUT}")
    print(f"[out] {PANEL_OUT}")
    run(["rsrs", "--runtime-internal", "--stop"], env, timeout=180, check=False)
    return 0 if attach_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

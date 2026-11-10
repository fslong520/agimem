#!/usr/bin/env python3
"""isolated_lib.py — H4 刁钻层：把合成场景写进**隔离 rsrs 库**再采集召回（真能力分）。

做法（复制 `human_memory/run_human_dimension.py` 的 profile 思路，不 import、不改它）：

  env = 过滤掉所有 RSRS_/ONEMEMORY_/RESPIRE_ 前缀的 os.environ
  env.update(RSRS_DATA_DIR=<本臂独立目录>, RSRS_RPC_PORT=<独立端口>,
             RSRS_SUPER=<占位>, RSRS_NO_AUTOSYNC=1, RSRS_UPDATE_CHECK=0,
             RSRS_ENGINE=cpu, RSRS_M3_DIR=<m3 目录>, RSRS_FEEDBACK=0, RSRS_ABLATE=hot)
  rsrs keygen --json            → 取回真 super
  rsrs --runtime-internal --stop → 停掉 keygen 拉起的占位 super runtime
  rsrs import <dump.json> --json → 一次性写入全部合成节点
  rsrs recall <q> --titles --limit 5 --json → 逐题采集
  rsrs --runtime-internal --stop → 收尾

纪律：
- **绝不碰 `~/.rsrs`**：data dir 指向 /tmp 下本臂目录，端口独立，super 独立；
- 不改全局 `rsrs config`，不启停宿主 runtime（只停自己这个隔离端口的 runtime）；
- `RSRS_ABLATE=hot` 沿用 tests/27 纪律：不消融则热轴写回会污染同库复跑；
- 落盘脱敏：命中标题用 `｜<trk 条目号>` 映射回合成 id，未映射的命中写 `extNNNN` 占位，
  仓里不出现隔离库 UUID。

写入去重坑：`rsrs import` 会吞掉**正文完全相同**的条目，因此每条正文尾部附
`（条目 <trk id>）` 保证唯一；标题尾部也附 `｜<trk id>`，使召回标题可直接解析回合成 id。

用法：
    python3 isolated_lib.py [--root /tmp/agimem-tricky-iso] [--port 16140] [--limit 5]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.join(HERE, "data", "tricky_tree.json")
DATASET = os.path.join(HERE, "dataset", "tricky_evalset.jsonl")
OUT_DIR = os.path.join(HERE, "results")
M3_DEFAULT = os.path.expanduser("~/.rsrs/models/bge-m3")
TITLE_SEP = "｜"


def run(args: List[str], env: Dict[str, str], timeout: int = 600, check: bool = True):
    p = subprocess.run(args, env=env, capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        sys.stderr.write(f"[fail] {' '.join(args[:3])} rc={p.returncode}\n"
                         f"{p.stdout[-500:]}\n{p.stderr[-400:]}\n")
    return p


def parse_env(stdout: str) -> Optional[Dict[str, Any]]:
    brace = stdout.find("{")
    if brace < 0:
        return None
    try:
        return json.loads(stdout[brace:])
    except json.JSONDecodeError:
        return None


class IsolatedStore:
    """一个隔离 profile：独立目录 + 独立 RPC 端口 + 独立 super。"""

    def __init__(self, root: str, tag: str, port: int, m3: str) -> None:
        self.dir = os.path.join(root, tag)
        self.tag = tag
        self.port = port
        self.m3 = m3
        self.super = ""
        self.env: Dict[str, str] = {}

    def open(self) -> "IsolatedStore":
        if os.path.isdir(self.dir):
            shutil.rmtree(self.dir)
        os.makedirs(self.dir, exist_ok=True)
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("RSRS_", "ONEMEMORY_", "RESPIRE_"))}
        env.update(RSRS_DATA_DIR=self.dir, RSRS_RPC_PORT=str(self.port),
                   RSRS_SUPER="A3-000000-000000-000000-000000-000000-000000",
                   RSRS_NO_AUTOSYNC="1", RSRS_UPDATE_CHECK="0", RSRS_ENGINE="cpu",
                   RSRS_M3_DIR=self.m3, RSRS_FEEDBACK="0", RSRS_ABLATE="hot")
        p = run(["rsrs", "keygen", "--json"], env, timeout=600)
        d = parse_env(p.stdout) or {}
        self.super = (d.get("summary") or {}).get("super") or ""
        if not self.super:
            raise RuntimeError(f"{self.tag}: keygen 未返回 super：{p.stdout[-300:]} {p.stderr[-200:]}")
        env["RSRS_SUPER"] = self.super
        self.env = env
        # keygen 用占位 super 拉起了一个 runtime，必须停掉，让后续命令用真 super 重新 spawn
        run(["rsrs", "--runtime-internal", "--stop"], env, timeout=180, check=False)
        time.sleep(0.5)
        return self

    def import_items(self, items: List[Dict[str, Any]]):
        path = os.path.join(self.dir, "import.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False)
        return run(["rsrs", "import", path, "--json"], self.env, timeout=3600)

    def status(self) -> Dict[str, Any]:
        p = run(["rsrs", "status", "--json"], self.env, timeout=180, check=False)
        return (parse_env(p.stdout) or {}).get("summary") or {}

    def recall(self, query: str, limit: int) -> Dict[str, Any]:
        p = run(["rsrs", "recall", query, "--limit", str(limit), "--json", "--titles"],
                self.env, timeout=600, check=False)
        d = parse_env(p.stdout) or {}
        det = d.get("details") or []
        hits = []
        for h in det:
            if not isinstance(h, dict):
                continue
            hits.append({"id": h.get("id"), "title": h.get("title"), "score": h.get("score")})
        summ = d.get("summary") or {}
        return {"rc": p.returncode, "mode": summ.get("mode"),
                "embedding_model": summ.get("embedding_model"),
                "hits": hits, "error": (d.get("errors") or [None])[0]}

    def wait_index(self, budget: int = 600, expect_total=None):
        """就绪判据 = 空转探针 recall 的 embedding_model 非 null 且 state=ready。

        （参考实现踩过的坑：`status.summary.retrieval_index.worker_active` 恒 true，
         是常驻 worker 存活标志，不是「索引待办数」。）
        """
        t0 = time.time()
        state: Dict[str, Any] = {}
        while time.time() - t0 < budget:
            s = self.status()
            ri = s.get("retrieval_index") or {}
            state = {"state": ri.get("state"), "local_total": s.get("local_total"),
                     "worker_active": ri.get("worker_active"), "error": ri.get("error")}
            pr = self.recall("预热探针", 1)
            ok_total = (expect_total is None) or (state.get("local_total") == expect_total)
            if pr["embedding_model"] and state.get("state") == "ready" and ok_total:
                return dict(state, embedding_model=pr["embedding_model"],
                            waited_s=round(time.time() - t0, 1))
            time.sleep(4)
        return dict(state, waited_s=round(time.time() - t0, 1), timeout=True)

    def close(self) -> None:
        run(["rsrs", "--runtime-internal", "--stop"], self.env, timeout=180, check=False)


def load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def node_to_item(n: Dict[str, Any]) -> Dict[str, Any]:
    """合成节点 → import 条目。标题/正文都带 trk 条目号（标题用于解析回 id，正文防去重吞）。"""
    return {
        "title": f"{n['title']}{TITLE_SEP}{n['id']}",
        "content": f"{n['content']}\n（条目 {n['id']}；场景 {n['scenario']}；来源 {n['source']}）",
        "kind": "context",
        "importance": "important",
        "created_at": f"{n.get('ts', '2026-06-01')}T09:00:00Z",
        "tags": [n.get("scenario", ""), n.get("source", "")],
    }


def title_to_node(title: str) -> Optional[str]:
    if not title or TITLE_SEP not in title:
        return None
    cand = title.rsplit(TITLE_SEP, 1)[-1].strip()
    return cand if cand.startswith("trk") else None


def main() -> int:
    ap = argparse.ArgumentParser(description="H4 刁钻层：隔离库写入 + 采集")
    ap.add_argument("--root", default="/tmp/agimem-tricky-iso")
    ap.add_argument("--tag", default="tricky")
    ap.add_argument("--port", type=int, default=16140)
    ap.add_argument("--m3", default=M3_DEFAULT)
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "tricky-isolated-predictions.jsonl"))
    ap.add_argument("--stats", default=os.path.join(OUT_DIR, "tricky-isolated-stats.json"))
    ap.add_argument("--tree", default=TREE, help="缺省 data/tricky_tree.json（748 节点）")
    ap.add_argument("--dataset", default=DATASET, help="缺省 dataset/tricky_evalset.jsonl（132 题）")
    args = ap.parse_args()

    tree = load_json(args.tree)
    nodes = tree["nodes"]
    cases = [json.loads(x) for x in open(args.dataset, encoding="utf-8") if x.strip()]
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    if not os.path.isdir(args.m3):
        print(f"警告：M3 目录不存在 {args.m3}，召回会退化（记录在 stats 里）", file=sys.stderr)

    st = IsolatedStore(args.root, args.tag, args.port, args.m3).open()
    print(f"[iso] 隔离库就绪 dir={st.dir} port={st.port} super_len={len(st.super)}", flush=True)

    items = [node_to_item(n) for n in nodes]
    p = st.import_items(items)
    d = parse_env(p.stdout) or {}
    imported = d.get("summary") or {}
    print(f"[iso] import rc={p.returncode} {json.dumps(imported, ensure_ascii=False)[:300]}", flush=True)
    if p.returncode != 0:
        st.close()
        return 1

    ready = st.wait_index()
    print(f"[iso] index ready {json.dumps(ready, ensure_ascii=False)}", flush=True)

    rows, per = [], []
    n_hits = n_unmapped = n_empty = 0
    scores: List[float] = []
    modes, emb = set(), set()
    seq = 0
    for i, c in enumerate(cases, 1):
        r = st.recall(c["query"], args.limit)
        hits = []
        for h in r["hits"]:
            nid = title_to_node(h.get("title") or "")
            if nid is None:
                n_unmapped += 1
                seq += 1
                nid = f"ext{seq:04d}"
            hits.append({"id": nid, "score": h.get("score")})
            if isinstance(h.get("score"), (int, float)):
                scores.append(float(h["score"]))
        n_hits += len(hits)
        if not hits:
            n_empty += 1
        modes.add(str(r.get("mode")))
        if r.get("embedding_model"):
            emb.add(str(r["embedding_model"]))
        rows.append({"qid": c["qid"], "query": c["query"], "hits": hits})
        per.append({"qid": c["qid"], "type": c["type"], "n_hits": len(hits),
                    "top1": hits[0]["id"] if hits else None})
        if i % 22 == 0:
            print(f"  … {i}/{len(cases)}", flush=True)

    with open(args.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    st.close()
    stats = {
        "arm": "isolated-rsrs",
        "data_dir": st.dir,
        "port": st.port,
        "tree_path": os.path.relpath(args.tree, HERE), "dataset_path": os.path.relpath(args.dataset, HERE),
        "n_nodes_imported": len(items),
        "n_questions": len(cases),
        "limit": args.limit,
        "n_hits": n_hits,
        "n_unmapped_hits": n_unmapped,
        "n_empty_questions": n_empty,
        "score_min": min(scores) if scores else None,
        "score_max": max(scores) if scores else None,
        "recall_modes": sorted(modes),
        "embedding_models": sorted(emb),
        "index_ready": ready,
        "import_summary": imported,
        "notes": "隔离库（/tmp 下独立 data dir + 独立端口 + 独立 super）；未触碰 ~/.rsrs；"
                 "命中标题｜trk条目号 映射回合成 id，UUID 不落盘",
        "per_question": per,
    }
    with open(args.stats, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({k: stats[k] for k in stats if k != "per_question"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

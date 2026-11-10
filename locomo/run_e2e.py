#!/usr/bin/env python3
"""H1 · LoCoMo conv-0 端到端补跑（召回 → 拼正文 → 答题 → judge），隔离库。

为什么重写 `scripts/locomo/om_eval.py` 的驱动层而不改它：
- om_eval.py 调 `1memory` 二进制与 `ONEMEMORY_DATA_DIR`，本机该二进制已不存在（只有 rsrs 1.0.19），
  且它把结果写进 `scripts/locomo/results/`（本任务只读该目录）。
- 提示词与判分**不复制**：直接 import `scripts/locomo/common_llm.py` 的
  ANSWER_SYS / answer_prompt / judge_prompt / parse_score，保持与 tests/01、tests/23 同口径。
- 只换两处：①检索走 rsrs 隔离库（复用 `isolated_lib.py` 的 profile 三件套纪律）；
  ②LLM 走本机 magpie 网关（b.ai 直连本机不可达，见 results 里 llm 环境快照）。

口径（对齐 tests/01 的 1memory 侧）：
- 库：19 个 session 各一条 important 记忆，正文 = session 日期 + 逐轮对话（session 级，limit=5）
- 检索：top-5；拼给答题模型的文本 = `[<title>] <content>`
- 答题：同 ANSWER_SYS；judge：同 JUDGE_SYS，单判（--judges 控制，默认 1）
- 检索层副产物：按标题 `session N` 对照 evidence 的 session-hit@5（与 tests/32 同判据）

脱敏：隔离库 UUID 不落盘，只落标题/正文（LoCoMo 公开语料）与分数。

用法：
    python3 run_e2e.py --smoke 5                 # 冒烟：前 5 题，验证链路
    python3 run_e2e.py --workers 6               # 全量 199 题
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import sys
import time
import urllib.request
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
AGIMEM = os.path.dirname(HERE)
BENCH = os.path.dirname(AGIMEM)
sys.path.insert(0, AGIMEM)
sys.path.insert(0, os.path.join(BENCH, "scripts", "locomo"))

import isolated_lib as il  # noqa: E402
import common_llm as cl  # noqa: E402  只用提示词与 parse_score，不用它的 chat（b.ai 不可达）

DATA = os.path.expanduser(os.environ.get("LOCOMO10", "~/locomo-src/data/locomo10.json"))
RESDIR = os.path.join(AGIMEM, "results")
SESSION_RE = re.compile(r"session (\d+)")
EVIDENCE_RE = re.compile(r"D(\d+):")
MAGPIE_SETTINGS = os.path.expanduser("~/.qoder/settings.json")
DEFAULT_MODEL = "commandcode/z-ai/glm-5.3-flash"


# ---------------- LLM（magpie 网关） ----------------

def _magpie() -> tuple[str, str]:
    st = json.load(open(MAGPIE_SETTINGS))
    p = st["providers"]["magpie"]
    return p["baseUrl"].rstrip("/"), p["apiKey"]


def chat(messages, model: str = DEFAULT_MODEL, max_tokens: int = 1024,
         temperature: float = 0.0, retries: int = 2, timeout: int = 120) -> str:
    base, key = _magpie()
    body = json.dumps({"model": model, "messages": messages,
                       "max_tokens": max_tokens, "temperature": temperature}).encode()
    last = None
    for _ in range(retries + 1):
        req = urllib.request.Request(base + "/chat/completions", data=body,
                                     headers={"Authorization": f"Bearer {key}",
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.loads(r.read())
            txt = (d["choices"][0]["message"].get("content") or "").strip()
            if txt:
                return txt
            last = "empty content"
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
            time.sleep(1.5)
    raise RuntimeError(last or "chat failed")


# ---------------- LoCoMo 语料 ----------------

def load_conv(idx: int = 0) -> Dict[str, Any]:
    return json.load(open(DATA))[idx]


def sessions_of(conv: Dict[str, Any]) -> List[Dict[str, Any]]:
    c = conv["conversation"]
    out = []
    for key in c:
        m = re.fullmatch(r"session_(\d+)", key)
        if not m:
            continue
        n = int(m.group(1))
        turns = c[key] or []
        when = c.get(f"{key}_date_time", "")
        body = "\n".join(
            f"{t.get('speaker', '?')}: {t.get('text') or t.get('blip_caption') or ''}"
            for t in turns
        )
        out.append({"n": n, "date": when,
                    "title": f"session {n} · {when}",
                    "content": f"Session date: {when}\n{body}"})
    out.sort(key=lambda x: x["n"])
    return out


def ev_sessions(row: Dict[str, Any]) -> set[int]:
    out = set()
    for e in row.get("evidence") or []:
        m = EVIDENCE_RE.match(str(e))
        if m:
            out.add(int(m.group(1)))
    return out


def hit_sessions(titles: List[str]) -> set[int]:
    out = set()
    for t in titles:
        m = SESSION_RE.search(t or "")
        if m:
            out.add(int(m.group(1)))
    return out


# ---------------- 隔离库召回 ----------------

def recall_full(st: il.IsolatedStore, query: str, limit: int) -> Dict[str, Any]:
    p = il.run(["rsrs", "recall", query, "--limit", str(limit), "--json"],
               st.env, timeout=600, check=False)
    d = il.parse_env(p.stdout) or {}
    hits = []
    for h in d.get("details") or []:
        if not isinstance(h, dict):
            continue
        entry = h.get("entry") if isinstance(h.get("entry"), dict) else {}
        hits.append({"id": h.get("id") or entry.get("id"),
                     "title": h.get("title") or entry.get("title") or "",
                     "content": entry.get("content") or "",
                     "score": h.get("score")})
    return {"rc": p.returncode, "hits": hits,
            "embedding_model": (d.get("summary") or {}).get("embedding_model"),
            "error": (d.get("errors") or [None])[0]}


def wilson(k: int, n: int, z: float = 1.959963984540054) -> Dict[str, Any]:
    if n <= 0:
        return {"point": None, "lo": None, "hi": None, "n": 0, "k": k, "method": "wilson"}
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z2 / (4 * n * n)) ** 0.5) / denom
    return {"point": p, "lo": max(0.0, center - half), "hi": min(1.0, center + half),
            "n": n, "k": k, "method": "wilson", "z": z}


def mean_ci(scores: List[float]) -> Dict[str, Any]:
    n = len(scores)
    if not n:
        return {"n": 0, "mean": None}
    mu = sum(scores) / n
    var = sum((s - mu) ** 2 for s in scores) / (n - 1) if n > 1 else 0.0
    se = (var / n) ** 0.5
    return {"n": n, "mean": round(mu, 4),
            "se": round(se, 4),
            "ci95": [round(mu - 1.959963984540054 * se, 4),
                     round(mu + 1.959963984540054 * se, 4)]}


CAT_NAMES = {1: "multi-hop", 2: "temporal", 3: "open-domain", 4: "single-hop", 5: "adversarial"}


def main() -> int:
    ap = argparse.ArgumentParser(description="H1 LoCoMo conv-0 端到端（隔离库）")
    ap.add_argument("--root", default="/tmp/agimem-locomo-e2e")
    ap.add_argument("--tag", default="om-store-conv0")
    ap.add_argument("--port", type=int, default=16180)
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--judges", type=int, default=1)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--smoke", type=int, default=0, help="只跑前 N 题（链路验证）")
    ap.add_argument("--skip-ingest", action="store_true")
    ap.add_argument("--out", default=os.path.join(RESDIR, "locomo-e2e.json"))
    ap.add_argument("--m3", default=os.path.expanduser("~/.rsrs/models/bge-m3"))
    args = ap.parse_args()

    conv = load_conv(0)
    qa = conv["qa"]
    if args.smoke:
        qa = qa[: args.smoke]
    sess = sessions_of(conv)
    print(f"[data] conv-0: {len(sess)} sessions, {len(qa)} qa, limit={args.limit}", flush=True)

    t0 = time.time()
    st = il.IsolatedStore(args.root, args.tag, args.port, args.m3).open()
    print(f"[iso] dir={st.dir} port={st.port} keygen {time.time()-t0:.0f}s", flush=True)

    if not args.skip_ingest:
        items = [il.item(s["title"], s["content"], "2023-05-01T00:00:00Z", "important")
                 for s in sess]
        p = st.import_items(items)
        print(f"[iso] import rc={p.returncode} {(p.stdout or '')[:120]}", flush=True)
        ready = st.wait_index(expect_total=len(sess), budget=900)
        print(f"[iso] index ready {ready}", flush=True)

    probe = recall_full(st, qa[0]["question"], args.limit)
    print(f"[iso] probe rc={probe['rc']} emb={probe['embedding_model']} "
          f"hits={len(probe['hits'])} keys={sorted(probe['hits'][0].keys()) if probe['hits'] else []}",
          flush=True)
    if not probe["hits"]:
        print(f"[iso] 探针零命中，异常：{probe.get('error')}", file=sys.stderr)
        return 2
    print(f"[iso] probe top title={probe['hits'][0]['title'][:60]!r} "
          f"content_len={len(probe['hits'][0]['content'])}", flush=True)

    t1 = time.time()
    rows: List[Dict[str, Any]] = []

    def work(item):
        idx, q = item
        ts = time.time()
        rec = recall_full(st, q["question"], args.limit)
        titles = [h["title"] for h in rec["hits"]]
        mems = [f"[{h['title']}] {h['content']}" for h in rec["hits"]]
        row: Dict[str, Any] = {
            "idx": idx, "question": q["question"],
            "gold": str(q.get("answer", q.get("adversarial_answer", ""))),
            "category": q.get("category"),
            "evidence": q.get("evidence"),
            "retrieved_titles": titles,
            "retrieved_sessions": sorted(hit_sessions(titles)),
            "evidence_sessions": sorted(ev_sessions(q)),
            "n_hits": len(rec["hits"]),
            "recall_s": round(time.time() - ts, 2),
        }
        try:
            pred = chat(cl.answer_prompt(q["question"], mems), model=args.model)
        except Exception as e:  # noqa: BLE001
            pred = f"__error__ {type(e).__name__}: {e}"
        row["pred"] = pred
        scores = []
        raws = []
        for _ in range(max(1, args.judges)):
            try:
                txt = chat(cl.judge_prompt(q["question"], row["gold"], pred),
                           model=args.model, max_tokens=512)
                scores.append(cl.parse_score(txt))
                raws.append(txt[:300])
            except Exception as e:  # noqa: BLE001
                scores.append(0.0)
                raws.append(f"__error__ {type(e).__name__}")
        row["scores"] = scores
        row["score"] = sum(scores) / len(scores)
        row["judge_raw"] = raws
        row["total_s"] = round(time.time() - ts, 2)
        return row

    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, row in enumerate(ex.map(work, enumerate(qa))):
            rows.append(row)
            if (i + 1) % 10 == 0 or i + 1 == len(qa):
                print(f"  {i+1}/{len(qa)} elapsed {time.time()-t1:.0f}s", flush=True)

    # ---- 汇总 ----
    scored = [r for r in rows if not r["pred"].startswith("__error__")]
    unknown = sum(1 for r in rows if str(r["pred"]).strip().lower().startswith("unknown"))
    errs = len(rows) - len(scored)
    overall = mean_ci([r["score"] for r in scored])
    nonadv = [r["score"] for r in scored if r.get("category") != 5]
    by_cat = {}
    for c in sorted({r["category"] for r in rows if r["category"] is not None}):
        ss = [r["score"] for r in scored if r["category"] == c]
        by_cat[CAT_NAMES.get(c, str(c))] = mean_ci(ss)
    # 检索层 session-hit@limit（分母=有 evidence 的题，与 tests/32 同判据）
    ev_rows = [r for r in rows if r["evidence_sessions"]]
    sh = sum(1 for r in ev_rows if set(r["evidence_sessions"]) & set(r["retrieved_sessions"]))

    payload = {
        "task": "T20 / H1 LoCoMo conv-0 端到端补跑",
        "round": "本轮实测 2026-11-09（非历史）",
        "system": "Respire (rsrs) 隔离库",
        "env": {
            "cli_version": "1.0.19",
            "isolated_store": st.dir,
            "rpc_port": st.port,
            "m3": args.m3,
            "recall_limit": args.limit,
            "answer_model": args.model,
            "judge_model": args.model,
            "llm_gateway": "http://127.0.0.1:3425/v1 (magpie)",
            "judges_per_question": args.judges,
            "note": "b.ai 直连本机不可达（api.b.ai 超时、7890 代理未监听）；改用 magpie 网关同族 glm-5.3-flash",
            "n_entries": len(sess),
            "workers": args.workers,
        },
        "n_questions": len(rows),
        "n_scored": len(scored),
        "n_error": errs,
        "unknown_rate": round(unknown / len(rows), 4) if rows else None,
        "overall": overall,
        "non_adversarial": mean_ci(nonadv),
        "by_category": by_cat,
        "retrieval_session_hit": {**wilson(sh, len(ev_rows)), "denominator": len(ev_rows)},
        "elapsed_s": round(time.time() - t0, 1),
        "rows": rows,
    }
    os.makedirs(RESDIR, exist_ok=True)
    json.dump(payload, open(args.out, "w"), ensure_ascii=False, indent=1)
    print(f"\n[out] {args.out}")
    print(f"[metrics] overall={overall} unknown={payload['unknown_rate']} err={errs} "
          f"session_hit@{args.limit}={payload['retrieval_session_hit']['point']}", flush=True)
    for k, v in by_cat.items():
        print(f"  {k:12s} {v}", flush=True)

    p = il.run(["rsrs", "--runtime-internal", "--stop"], st.env, timeout=180, check=False)
    print(f"[iso] stopped rc={p.returncode}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

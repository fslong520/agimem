#!/usr/bin/env python3
"""T10 · 机器向 M 维度统一记分卡（M1 召回率 / M2 速度 / M3 token 用量）。

口径纪律（与 tests/35 一致，改口径必先改文档）：
- **真库只读**：只走 `rsrs bench run`（实测不写 query_log：跑前/跑后 query_log 计数不变）
  与 `rsrs export`（整库只读导出到 /tmp）。**不调用 `rsrs recall`**（实测每次写 1 条 query_log）。
- **不允许复算了事**：M1 用 bench-recall 的 300 题（L2-train，seed=20261109）**本轮复跑**，
  与 T6 同日实测数字并列上报，严格区分「T6」与「本轮」。
- **M2 三种速度**：①runtime 内部 p50/p95（bench 报告自带）；②端到端 CLI p50/p95/p99
  （300 次单题 bench 调用，含进程启动）；③吞吐（并发 1 / 并发 4）+ 冷启动（隔离库）。
- **M3 token**：用 `rsrs export` 的正文/标题 + bench 返回的 top-k id 逐题计 token，
  两个 tokenizer 都报：bge-m3 同源 `tokenizers`（`~/.rsrs/models/bge-m3/tokenizer.json`）
  与 tiktoken `cl100k_base`。禁字符数冒充 token，禁抽样外推（300 题逐题计）。
- 隔离库写 `/tmp`；真库 `~/.rsrs` 除只读调用外不写。导出文件含真库正文，只落 `/tmp`，跑完删除。

用法（在 respire-benchmark/ 下）：
    python3 agimem/machine/run_machine.py --out-dir agimem/machine/results
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import re
import socket
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))          # respire-benchmark/
DEFAULT_EVALSET = os.path.join(REPO, "bench-recall", "evalset_l2train300.jsonl")
M3_DIR = os.path.expanduser("~/.rsrs/models/bge-m3")
SKELETON_PREFIX = "以下是从记忆库召回的相关条目，回答时只使用这些内容：\n"
SKELETON_ITEM = "\n[{i}] {title}\n{content}\n"
SKELETON_SUFFIX = "请据此回答用户问题："


def env_clean():
    env = {k: v for k, v in os.environ.items() if not k.startswith(("RSRS_", "ONEMEMORY_", "RESPIRE_"))}
    env.update(RSRS_FEEDBACK="0", RSRS_NO_AUTOSYNC="1", RSRS_UPDATE_CHECK="0")
    return env


def run(cmd, env, timeout=1800):
    t0 = time.time()
    p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
    return p, round(time.time() - t0, 3)


def parse_json(stdout):
    i = stdout.find("{")
    if i < 0:
        return None
    try:
        return json.loads(stdout[i:])
    except json.JSONDecodeError:
        return None


UUID_RE = re.compile(
    r"request_id=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
)


def rpc(port, method, args, timeout=10.0):
    body = json.dumps({"v": 1, "id": f"t10-{int(time.time()*1000)}",
                       "method": method, "args": args}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/rpc", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _report_ok(rep, evalset, n):
    """报告必须与本次评测集/题数一致，防拿上一轮 stale 或并发残留报告冒充本轮。"""
    if not rep:
        return False
    if os.path.abspath(rep.get("evalset") or "") != os.path.abspath(evalset):
        return False
    if n is not None and len(rep.get("results") or []) != n:
        return False
    return True


def wait_report(report_path, start_ts, proc, env, evalset, n, budget_s=1800.0):
    """取回 bench 报告：先看新落盘文件；否则按 request_id 用 runtime.result 只读取回（不重放）。"""
    if os.path.exists(report_path) and os.path.getmtime(report_path) >= start_ts - 1:
        rep = json.load(open(report_path))
        if _report_ok(rep, evalset, n):
            return rep
        print(f"[warn] 报告身份不符（evalset/n 不符），忽略并继续取回：{report_path}", flush=True)
    txt = (proc.stdout or "") + (proc.stderr or "")
    m = UUID_RE.search(txt)
    if not m:
        raise RuntimeError(f"bench 失败且无 request_id（rc={proc.returncode}）：{txt[-400:]}")
    rid = m.group(1)
    port = int(env.get("RSRS_RPC_PORT") or 15169)
    deadline = time.time() + budget_s
    while time.time() < deadline:
        try:
            resp = rpc(port, "runtime.result", [rid])
        except Exception as e:  # noqa: BLE001
            print(f"[poll] rpc error: {e}", flush=True)
            time.sleep(10)
            continue
        state = ((resp.get("envelope") or {}).get("summary") or {}).get("state")
        if state == "completed":
            response = ((resp.get("envelope") or {}).get("summary") or {}).get("response") or {}
            rep = (((response.get("envelope") or {}).get("details") or {}).get("report"))
            if rep:
                json.dump(rep, open(report_path, "w", encoding="utf-8"), ensure_ascii=False)
                print(f"[poll] 已取回 {rid[:8]} → {report_path}", flush=True)
                return rep
            raise RuntimeError("runtime.result 完成但 report 为空")
        time.sleep(10)
    raise RuntimeError(f"runtime.result 取回超时（request_id={rid[:8]}）")


def wilson_ci(k, n, z=1.959963984540054):
    if n <= 0:
        return {"point": None, "lo": None, "hi": None, "n": 0, "k": k, "method": "wilson"}
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z2 / (4 * n * n)) ** 0.5) / denom
    return {"point": p, "lo": max(0.0, center - half), "hi": min(1.0, center + half),
            "n": n, "k": k, "method": "wilson", "z": z}


def quantile(sorted_vals, q):
    if not sorted_vals:
        return None
    idx = min(len(sorted_vals) - 1, max(0, int(round(q * (len(sorted_vals) - 1)))))
    return sorted_vals[idx]


def lat_stats(vals, unit_div=1.0):
    xs = sorted(v / unit_div for v in vals)
    if not xs:
        return {"n": 0}
    return {"n": len(xs), "p50": quantile(xs, 0.50), "p95": quantile(xs, 0.95),
            "p99": quantile(xs, 0.99), "min": xs[0], "max": xs[-1],
            "mean": round(sum(xs) / len(xs), 4)}


def bench(report_path, evalset, topk, env, timeout=1800):
    """跑一个 bench；>120s 的 CLI 会返回 request_outcome_unknown，按 request_id 只读取回。

    注意：先删除旧报告，避免拿上一轮的 stale 文件冒充本轮（实测过的坑）。
    """
    if os.path.exists(report_path):
        os.remove(report_path)
    t0 = time.time()
    cmd = ["rsrs", "--client-only", "bench", "run", os.path.abspath(evalset),
           "--json", "--topk", str(topk), "--save", os.path.abspath(report_path)]
    p, _ = run(cmd, env, timeout=timeout)
    n = len(load_evalset(evalset))
    report = wait_report(report_path, t0, p, env, evalset, n)
    return report, round(time.time() - t0, 3), p.returncode


def load_evalset(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def m1_from_raw(report, ks=(1, 3, 5, 10, 20)):
    rows = report["results"]
    n = len(rows)
    ranks = [r.get("rank") for r in rows]
    out = {}
    for k in ks:
        hits = sum(1 for r in ranks if r is not None and 0 <= r < k)
        out[f"hit@{k}"] = wilson_ci(hits, n)
    mrr = sum((1.0 / (r + 1)) if r is not None else 0.0 for r in ranks) / n if n else 0.0
    out["mrr"] = mrr
    out["n"] = n
    out["miss"] = sum(1 for r in ranks if r is None)
    return out


class Store:
    """隔离 profile（每臂独立目录 + 独立端口 + 独立 super），只用于冷启动测量。"""

    def __init__(self, root, tag, port):
        self.dir = os.path.join(root, tag)
        self.tag, self.port = tag, port
        self.env, self.super = {}, ""

    def open(self):
        import shutil
        if os.path.isdir(self.dir):
            shutil.rmtree(self.dir)
        os.makedirs(self.dir, exist_ok=True)
        env = env_clean()
        env.update(RSRS_DATA_DIR=self.dir, RSRS_RPC_PORT=str(self.port),
                   RSRS_SUPER="A3-000000-000000-000000-000000-000000-000000",
                   RSRS_ENGINE="cpu", RSRS_M3_DIR=M3_DIR, RSRS_ABLATE="hot")
        p, _ = run(["rsrs", "keygen", "--json"], env, timeout=300)
        d = parse_json(p.stdout) or {}
        sup = (d.get("summary") or {}).get("super") or ""
        if not sup:
            raise RuntimeError("keygen 未返回 super")
        env["RSRS_SUPER"] = sup
        self.super, self.env = sup, env
        run(["rsrs", "--runtime-internal", "--stop"], env, timeout=120)
        return self

    def import_items(self, items):
        path = os.path.join(self.dir, "import.json")
        json.dump(items, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        p, el = run(["rsrs", "import", path, "--json"], self.env, timeout=900)
        return p, el

    def wait_index(self, budget=300):
        t0 = time.time()
        while time.time() - t0 < budget:
            p, _ = run(["rsrs", "status", "--json"], self.env, timeout=120)
            d = parse_json(p.stdout) or {}
            ri = (d.get("summary") or {}).get("retrieval_index") or {}
            pr, _ = run(["rsrs", "--client-only", "recall", "预热探针", "--limit", "1", "--json"], self.env, timeout=120)
            pd = parse_json(pr.stdout) or {}
            emb = (pd.get("summary") or {}).get("embedding_model")
            if emb and ri.get("state") == "ready":
                return round(time.time() - t0, 1), ri
            time.sleep(4)
        return round(time.time() - t0, 1), None

    def stop(self):
        run(["rsrs", "--runtime-internal", "--stop"], self.env, timeout=120)


def tok_bge():
    from tokenizers import Tokenizer
    tk = Tokenizer.from_file(os.path.join(M3_DIR, "tokenizer.json"))
    return lambda s: len(tk.encode(s).ids)


def tok_cl100k():
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    return lambda s: len(enc.encode(s))


def m3_tokens(export_path, raw_report, evalset, tokenizers_dict):
    entries = json.load(open(export_path, encoding="utf-8"))
    by_id = {e["id"]: e for e in entries if e.get("id")}
    rows = []
    missing = 0
    for case, r in zip(evalset, raw_report["results"]):
        ids = r.get("ids") or []
        items = []
        for eid in ids:
            e = by_id.get(eid)
            if not e:
                missing += 1
                continue
            items.append({"title": e.get("title") or "", "content": e.get("content") or ""})
        per = {}
        for name, enc in tokenizers_dict.items():
            q = enc(case["query"])
            titles = sum(enc(it["title"]) for it in items)
            contents = sum(enc(it["content"]) for it in items)
            skeleton = enc(SKELETON_PREFIX) + enc(SKELETON_SUFFIX)
            item_frames = sum(enc(f"[{i}] ") for i in range(1, len(items) + 1))
            injected = q + titles + contents + skeleton + item_frames
            per[name] = {"query_tokens": q, "title_tokens": titles,
                         "retrieved_content_tokens": contents,
                         "injected_tokens": injected, "n_items": len(items)}
        rows.append({"note": case.get("note"), "rank": r.get("rank"), "tokens": per})
    agg = {}
    for name in tokenizers_dict:
        agg[name] = {}
        for key in ("query_tokens", "title_tokens", "retrieved_content_tokens", "injected_tokens"):
            vals = [x["tokens"][name][key] for x in rows]
            agg[name][key] = {"p50": quantile(sorted(vals), 0.50),
                              "p95": quantile(sorted(vals), 0.95),
                              "mean": round(sum(vals) / len(vals), 2) if vals else None,
                              "sum": sum(vals), "n": len(vals)}
    return {"rows": rows, "aggregate": agg, "missing_ids": missing, "n_queries": len(rows)}



def measure_cold(work, evalset, args):
    """冷启动：停掉隔离库 runtime → 重新 spawn（含模型加载）→ 首个查询完成的时间。"""
    st = Store("/tmp/agimem-machine-cold", "cold", 16310).open()
    items = [{"title": f"HM-MC-{i:02d}", "content": f"机器向冷启动探针条目 {i}：值班交接与发布窗口约定。",
              "kind": "context", "importance": "important",
              "created_at": f"2026-0{(i % 9) + 1}-1{i % 9}T09:00:00Z", "tags": []}
             for i in range(1, 21)]
    st.import_items(items)
    wait_s, _ = st.wait_index()
    cold_case = os.path.join(work, "cold-case.jsonl")
    with open(cold_case, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(evalset[0], ensure_ascii=False) + "\n")
    samples = []
    for rep in range(args.cold_reps):
        st.stop()
        time.sleep(0.5)
        t0 = time.time()
        rt = subprocess.Popen(["rsrs", "--runtime-internal"], env=st.env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ready = None
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                s = socket.create_connection(("127.0.0.1", st.port), timeout=0.2)
                s.close()
                ready = time.time() - t0
                break
            except OSError:
                time.sleep(0.1)
        if ready is None:
            rt.terminate()
            samples.append(None)
            continue
        _rep, _el, _rc = bench(os.path.join(work, f"cold{rep}.json"), cold_case, args.topk, st.env)
        samples.append(round(time.time() - t0, 3))
        rt.terminate()
        try:
            rt.wait(timeout=10)
        except subprocess.TimeoutExpired:
            rt.kill()
        st.stop()
        print(f"[M2] cold {rep+1}/{args.cold_reps}: {samples[-1]}s（spawn→首查）", flush=True)
    good = [x for x in samples if x is not None]
    return {"store": "隔离库 /tmp/agimem-machine-cold（20 条合成条目）",
            "definition": "stop runtime → spawn `rsrs --runtime-internal` → 首个 bench 查询完成（含模型加载）",
            "index_wait_s": wait_s, "samples_s": samples,
            "median_s": sorted(good)[len(good) // 2] if good else None}


def render_md(out, n, args):
    snap, m1, m2, m3 = out["environment"], out["m1"], out["m2"], out["m3"]
    def f4(x): return "n/a" if x is None else f"{x:.4f}"
    def f3(x): return "n/a" if x is None else f"{x:.3f}"
    L = []
    L.append("# 机器向 M 维度 · 统一记分卡\n")
    L.append(f"生成：{out['generated_at']}　|　评测集：{n} 题（L2-train, seed=20261109，复用 bench-recall）\n")
    L.append("## 环境快照\n")
    L.append("| 项 | 值 |\n|---|---|")
    for k, v in (("CLI", snap["cli_version"]), ("embedding", snap["embedding_model"]),
                 ("recall_mode", snap["recall_mode"]), ("库条目", snap["store_entries"]),
                 ("index_pending", snap["index_pending"]), ("CPU", snap["hardware"].get("cpu")),
                 ("核数/内存", f"{snap['hardware'].get('cores')} / {snap['hardware'].get('mem_gb')} GB"),
                 ("主机/OS", f"{snap['host']} / {snap['os']}")):
        L.append(f"| {k} | {v} |")
    L.append("\n## M1 召回率（本轮复跑）\n")
    L.append("| 指标 | n | 点估计 | 95% Wilson CI |\n|---|---|---|---|")
    for k in (1, 3, 5, 10, 20):
        h = m1[f"hit@{k}"]
        L.append(f"| hit@{k} | {h['n']} | {f4(h['point'])} | [{f4(h['lo'])}, {f4(h['hi'])}] |")
    L.append(f"| MRR | {n} | {f4(m1['mrr'])} | — |")
    L.append(f"| 未命中（top-{args.topk} 全无 gold） | {n} | {m1['miss']} | — |\n")
    L.append("## M2 速度\n")
    L.append(f"- runtime 内部：p50 {m2['runtime'].get('p50_s')}s / p95 {m2['runtime'].get('p95_s')}s（bench 报告）")
    if m2["e2e"]:
        L.append(f"- 端到端 CLI（{m2['e2e']['n']} 次单题调用，含启动）：p50 {f3(m2['e2e']['p50'])}s / p95 {f3(m2['e2e']['p95'])}s / p99 {f3(m2['e2e']['p99'])}s")
    tp = m2["throughput"]
    L.append(f"- 吞吐：并发 1 = {tp['c1']['qps']} qps（{tp['c1']['wall_s']}s/{n} 题）；" +
             (f"并发 4 = {tp['c4']['qps']} qps（{tp['c4']['wall_s']}s/{n} 题，speedup {tp['c4']['speedup_vs_c1']}×）" if "c4" in tp else ""))
    if m2["cold"]:
        L.append(f"- 冷启动（隔离库，20 条，spawn→首查）：{m2['cold'].get('samples_s')} → median {m2['cold'].get('median_s')}s")
    L.append("\n## M3 token 用量（本轮实测）\n")
    L.append("| tokenizer | 指标 | p50 | p95 | 平均 | 总和 |\n|---|---|---|---|---|---|")
    for name in m3["aggregate"]:
        a = m3["aggregate"][name]
        for key, label in (("query_tokens", "query"), ("title_tokens", "titles"),
                           ("retrieved_content_tokens", "正文"), ("injected_tokens", "注入合计")):
            x = a[key]
            L.append(f"| {name} | {label} | {x['p50']} | {x['p95']} | {x['mean']} | {x['sum']} |")
    L.append("\n## 口径与未验证\n")
    L.append(f"- M1 本轮复跑；T6 同日实测对照见 tests/35（严格分栏）。")
    L.append(f"- M3：export 全文只落 /tmp，不落仓；单价 {m3['cost']['by_tokenizer']['bge-m3']['price_per_1k']} {args.price_currency}/1k，来源：本地自托管。")
    for u in out["unverified"]:
        L.append(f"- 未验证：{u}")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evalset", default=DEFAULT_EVALSET)
    ap.add_argument("--topk", type=int, default=20)
    ap.add_argument("--out-dir", default=os.path.join(HERE, "results"))
    ap.add_argument("--lat-samples", type=int, default=300, help="端到端延迟采样数（单题 bench 调用）")
    ap.add_argument("--concurrency", default="1,4")
    ap.add_argument("--cold-reps", type=int, default=3)
    ap.add_argument("--export", default="/tmp/agimem-machine-export.json")
    ap.add_argument("--price-per-1k", type=float, default=0.0,
                    help="token 单价（元/1k token）；默认 0 = 本地自托管无 API 计费")
    ap.add_argument("--price-currency", default="CNY")
    ap.add_argument("--skip-latency", action="store_true", help="跳过 300 次单题延迟采样（调试用）")
    ap.add_argument("--skip-cold", action="store_true")
    ap.add_argument("--only-cold", action="store_true", help="只补测冷启动并并入既有记分卡")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    run_id = time.strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}"
    work = f"/tmp/agimem-machine-work-{run_id}"
    os.makedirs(work, exist_ok=True)
    os.makedirs(work, exist_ok=True)
    env = env_clean()
    jp = os.path.join(args.out_dir, "machine-scorecard.json")
    mp = os.path.join(args.out_dir, "machine-scorecard.md")
    if args.only_cold:
        out = json.load(open(jp, encoding="utf-8"))
        evalset = load_evalset(args.evalset)
        work = "/tmp/agimem-machine-cold-" + time.strftime("%Y%m%d-%H%M%S")
        os.makedirs(work, exist_ok=True)
        out["m2"]["cold"] = measure_cold(work, evalset, args)
        if "冷启动为隔离库" not in " ".join(out.get("unverified") or []):
            out.setdefault("unverified", []).append(
                "冷启动为隔离库 20 条数据，非真库 5564 条规模；含 runtime spawn + 模型加载")
        json.dump(out, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        open(mp, "w", encoding="utf-8").write(render_md(out, len(evalset), args))
        print(f"[done] cold merged → {jp}", flush=True)
        return 0

    evalset = load_evalset(args.evalset)
    n = len(evalset)
    print(f"[bench] evalset n={n}", flush=True)

    snap = {
        "cli_version": None, "embedding_model": None, "recall_mode": None,
        "store_entries": None, "index_pending": None,
        "hardware": {}, "host": platform.node(), "os": platform.platform(),
        "date": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    try:
        p, _ = run(["rsrs", "v"], env, timeout=30)
        snap["cli_version"] = (p.stdout or p.stderr).strip().splitlines()[0][:80] if (p.stdout or p.stderr) else None
    except Exception:  # noqa: BLE001
        pass
    try:
        snap["hardware"] = {
            "cpu": next((l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if "model name" in l), None),
            "cores": os.cpu_count(),
            "mem_gb": round(int(next((l.split()[1] for l in open("/proc/meminfo") if l.startswith("MemTotal")), "0")) / 1048576, 1),
        }
    except Exception:  # noqa: BLE001
        pass

    # ── M1 召回率（本轮复跑）──────────────────────────────────────────────
    raw_path = os.path.join(work, "m1-l2train300-top20.raw.json")
    report, wall_m1, rc_m1 = bench(raw_path, args.evalset, args.topk, env)
    for k in ("embedding_model", "recall_mode", "index_pending"):
        snap[k] = (report.get("params") or {}).get(k)
    snap["store_entries"] = report.get("n_entries")
    if not snap["cli_version"]:
        snap["cli_version"] = report.get("version")
    m1 = m1_from_raw(report)
    m1["report_metrics"] = report.get("metrics")
    m1["wall_s"] = wall_m1
    m1["bench_rc"] = rc_m1
    print(f"[M1] hit@20={m1['hit@20']['point']:.4f} mrr={m1['mrr']:.4f} wall={wall_m1}s", flush=True)

    # ── M2 速度 ────────────────────────────────────────────────────────────
    m2 = {"runtime": {}, "e2e": {}, "throughput": {}, "cold": {}, "definitions": {
        "runtime": "bench 报告 params.p50_us/p95_us（runtime 内部计时，不含 CLI 进程启动）",
        "e2e": "300 次单题 `rsrs bench run` 的墙钟（含 CLI 启动与结果序列化）",
        "throughput_c1": f"{n} 题单进程顺序跑完的墙钟 → qps",
        "throughput_c4": "同一 300 题按顺序切 4 份、4 进程并发的墙钟 → qps（切分不改题面）",
        "cold": "隔离库首个查询（新 runtime spawn + 模型加载），非真库数字",
    }}
    params = report.get("params") or {}
    m2["runtime"]["p50_us"] = params.get("p50_us")
    m2["runtime"]["p95_us"] = params.get("p95_us")
    m2["runtime"]["p50_s"] = (int(params["p50_us"]) / 1e6) if params.get("p50_us") else None
    m2["runtime"]["p95_s"] = (int(params["p95_us"]) / 1e6) if params.get("p95_us") else None

    if not args.skip_latency:
        lat_dir = os.path.join(work, "lat"); os.makedirs(lat_dir, exist_ok=True)
        files = []
        for i, case in enumerate(evalset):
            f = os.path.join(lat_dir, f"c{i:03d}.jsonl")
            with open(f, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(case, ensure_ascii=False) + "\n")
            files.append(f)
        walls = []
        t0 = time.time()
        for i, f in enumerate(files):
            _, el = run(["rsrs", "--client-only", "bench", "run", f, "--json", "--topk", str(args.topk)],
                        env, timeout=120)
            walls.append(el)
            if (i + 1) % 50 == 0:
                print(f"[M2] e2e {i+1}/{len(files)}", flush=True)
        m2["e2e"] = lat_stats(walls)
        m2["e2e"]["wall_total_s"] = round(time.time() - t0, 1)
        m2["e2e"]["metric_unit"] = "s/query"
        print(f"[M2] e2e p50={m2['e2e']['p50']:.3f}s p95={m2['e2e']['p95']:.3f}s p99={m2['e2e']['p99']:.3f}s", flush=True)

    conc = [int(x) for x in str(args.concurrency).split(",") if x.strip()]
    m2["throughput"]["c1"] = {"n": n, "wall_s": wall_m1, "qps": round(n / wall_m1, 4)}
    if 4 in conc:
        cdir = os.path.join(work, "c4"); os.makedirs(cdir, exist_ok=True)
        chunks = [evalset[i::4] for i in range(4)] if len(evalset) % 4 == 0 else [
            evalset[i * n // 4:(i + 1) * n // 4] for i in range(4)]
        files = []
        for i, ch in enumerate(chunks):
            f = os.path.join(cdir, f"split{i}.jsonl")
            with open(f, "w", encoding="utf-8") as fh:
                for case in ch:
                    fh.write(json.dumps(case, ensure_ascii=False) + "\n")
            files.append(f)
        for f in files:  # 防 stale
            for suf in (".report.json",):
                if os.path.exists(f.replace(".jsonl", suf)):
                    os.remove(f.replace(".jsonl", suf))
        t0 = time.time()
        starts, procs = [], []
        for i, f in enumerate(files):
            starts.append(time.time())
            procs.append(subprocess.Popen(
                ["rsrs", "--client-only", "bench", "run", f, "--json", "--topk", str(args.topk),
                 "--save", os.path.join(cdir, f"split{i}.report.json")],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        outs = []
        for pr in procs:
            o, e = pr.communicate(timeout=1800)
            outs.append((o, e))
        sub = []
        for i, pr in enumerate(procs):
            class _P:
                pass
            fake = _P(); fake.stdout, fake.stderr, fake.returncode = outs[i][0], outs[i][1], pr.returncode
            r = wait_report(os.path.join(cdir, f"split{i}.report.json"), starts[i], fake, env,
                            files[i], len(chunks[i]))
            sub.append({"n": len(r.get("results") or []),
                        "p50_us": (r.get("params") or {}).get("p50_us"),
                        "p95_us": (r.get("params") or {}).get("p95_us")})
        wall_c4 = round(time.time() - t0, 2)
        m2["throughput"]["c4"] = {"n": n, "wall_s": wall_c4, "qps": round(n / wall_c4, 4),
                                  "per_process": sub,
                                  "speedup_vs_c1": round((n / wall_c4) / (n / wall_m1), 2)}
        print(f"[M2] c4 qps={m2['throughput']['c4']['qps']}", flush=True)

    if not args.skip_cold:
        try:
            m2["cold"] = measure_cold(work, evalset, args)
        except Exception as e:  # noqa: BLE001
            m2["cold"] = {"error": f"冷启动测量失败：{e}"}
            print(f"[M2] cold failed: {e}", flush=True)

    # ── M3 token 用量 ─────────────────────────────────────────────────────
    export_path = args.export
    if not os.path.exists(export_path):
        p, el = run(["rsrs", "--client-only", "export", export_path, "--json"], env, timeout=300)
        if p.returncode != 0 or not os.path.exists(export_path):
            raise RuntimeError(f"export 失败 rc={p.returncode} err={p.stderr[-300:]}")
    tks = {"bge-m3": tok_bge(), "cl100k_base": tok_cl100k()}
    m3 = m3_tokens(export_path, report, evalset, tks)
    m3["tokenizers"] = {
        "bge-m3": f"tokenizers.Tokenizer.from_file({M3_DIR}/tokenizer.json)（嵌入模型同源）",
        "cl100k_base": "tiktoken 0.14.0 cl100k_base（对照口径）",
    }
    m3["skeleton"] = {"prefix": SKELETON_PREFIX, "item": SKELETON_ITEM, "suffix": SKELETON_SUFFIX,
                      "note": "骨架逐题计一次（prefix+suffix+每项 [i] 前缀）；未包含客户端 system prompt，接入方须自行加"}
    total = {}
    for name in tks:
        inj = m3["aggregate"][name]["injected_tokens"]
        total[name] = {"injected_sum": inj["sum"],
                       "cost": round(inj["sum"] / 1000.0 * args.price_per_1k, 6),
                       "currency": args.price_currency,
                       "price_per_1k": args.price_per_1k}
    m3["cost"] = {"by_tokenizer": total,
                  "price_source": "本地自托管（rsrs + bge-m3，无 API 计费）；单价由 --price-per-1k 显式给定，默认 0",
                  "price_date": time.strftime("%Y-%m-%d"),
                  "note": "接云端模型时传入 --price-per-1k 与 --price-currency，并在 tests/35 记录价目出处"}
    m3["export_discipline"] = "export 全文只落 /tmp（含真库正文），不进仓；记分卡只存聚合 token 数"

    out = {"schema": "agimem-machine-scorecard/1", "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "environment": snap, "evalset": {"path": os.path.abspath(args.evalset), "n": n,
                                            "split": "L2-train, seed=20261109（复用 bench-recall，未重造）"},
           "m1": m1, "m2": m2, "m3": m3,
           "provenance": {"m1": "本轮复跑（bench run topk=20）；T6 同日数字见 tests/35 对照表",
                          "m2": "本轮实测", "m3": "本轮实测（export+bench id 对齐）"},
           "unverified": [
               "M3 recall-JSON 载荷（title+snippet）token 未采：bench 报告不含 snippet，直接 recall 会写 query_log（真库禁写）",
               "M2 runtime p99 不可得：bench 报告只给 p50/p95；端到端 p99 用 300 次单题调用近似，含 CLI 启动",
               "冷启动为隔离库 20 条数据，非真库 5560 条规模；仅代表 runtime spawn + 模型加载",
               "并发 4 为 4 个 bench 进程并发，非单进程内部并发",
           ]}
    os.makedirs(args.out_dir, exist_ok=True)
    json.dump(out, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    mp = os.path.join(args.out_dir, "machine-scorecard.md")
    open(mp, "w", encoding="utf-8").write(render_md(out, n, args))
    print(f"[done] {jp}\n[done] {mp}", flush=True)
    try:
        os.remove(export_path)
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

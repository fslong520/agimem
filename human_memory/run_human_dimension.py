#!/usr/bin/env python3
"""C 层 ·「人的记忆维度」探针（重复强化 / 时间衰减 / 错误纠偏）。

口径（与 tests/32 一致，勿改而不记）：
- 语料全合成，无真人数据、无真库 id；标题形如 `HM-RP-07-r2`。
- 判分**机械、零 LLM**：按召回标题 token 命中判定，不调任何模型。
- 每题型 n≥20；比例类指标用 Wilson 95% CI（与 agimem/score.py:wilson_ci 同式）。
- **只写隔离库**：每臂一个独立 profile 目录 + 独立 RSRS_RPC_PORT + 独立 super，
  绝不碰 `~/.rsrs`；RSRS_ABLATE=hot（tests/27 纪律：不消融则热轴写回污染同库复跑）。

三个题型：
  C1 repeat  同一事实在库里沉淀 1/3/5 条（同组不同标题），看 hit@1 / hit@5 是否随沉淀量上升。
  C2 recency 同一主题先写旧版本、后写新版本（created_at 不同），问「最新那版」→ 看新版本是否排到第 1。
  C3 correct 同一主题先写错误结论、后写纠正结论，看纠正版是否压过错误版（错误版 top-1 记 stale_top1）。

用法：
    python3 run_human_dimension.py [--n 20] [--limit 5] [--only c1,c2,c3] [--root /tmp/agimem-human-dim]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(HERE), "results")
M3_DEFAULT = os.path.expanduser("~/.rsrs/models/bge-m3")

# ── 合成语料：每行一个主题，占位符 {v} 由版本号替换，保证「同一件事的不同版本」语义相近但不相同 ──
TOPICS = [
    ("夜间发布窗口", "夜间发布窗口定在每周三 23:30，避开白天流量高峰"),
    ("告警收敛阈值", "告警收敛阈值设为 5 分钟内同类事件只报一次"),
    ("备份保留期", "备份保留期改为 30 天，超过自动清理"),
    ("灰度比例", "灰度发布比例按 5% 起步、每 10 分钟翻倍"),
    ("值班交接方式", "值班交接改为每日 9:30 站会对齐前一日的未决事项"),
    ("索引重建时间", "索引重建安排在周日凌晨 2 点，避开报表作业"),
    ("慢查询阈值", "慢查询阈值设为 800 毫秒，超过记入慢日志"),
    ("发布审批人", "发布审批人固定为当周 on-call 加一名架构组成员"),
    ("日志留存级别", "日志留存级别调整为核心链路保留 90 天、其余 14 天"),
    ("容量预警水位", "容量预警水位设在磁盘使用率 78%，提前扩容"),
    ("熔断重试次数", "熔断后重试次数降为 2 次，退避从 2 秒起"),
    ("缓存预热范围", "缓存预热只覆盖首页与搜索联想接口"),
    ("数据库连接池", "数据库连接池上限提到 120，等待超时 3 秒"),
    ("密钥轮换周期", "密钥轮换周期改为 45 天，轮换窗口在周二"),
    ("压测基线并发", "压测基线并发定为 800，持续 30 分钟"),
    ("故障分级标准", "故障分级：影响下单为 P1，影响浏览为 P2"),
    ("月度演练内容", "月度演练内容为机房单点断电切换"),
    ("监控采集间隔", "监控采集间隔从 60 秒缩短到 20 秒"),
    ("变更窗口长度", "常规变更窗口长度限制为 90 分钟"),
    ("异地副本同步", "异地副本改为异步同步，允许 15 分钟滞后"),
    ("接口兼容策略", "接口兼容策略保留三个大版本，旧版半年后下线"),
    ("资源回收周期", "测试环境资源每周五自动回收，需重新申请"),
    ("文档归档位置", "历史设计文档统一归档到知识库的 archive 目录"),
    ("新人上手路径", "新人上手按读码、修小 bug、独立提测三步走"),
]


def wilson_ci(k: int, n: int, z: float = 1.959963984540054):
    if n <= 0:
        return {"point": None, "lo": None, "hi": None, "n": 0, "k": k, "method": "wilson"}
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z2 / (4 * n * n)) ** 0.5) / denom
    return {"point": p, "lo": max(0.0, center - half), "hi": min(1.0, center + half),
            "n": n, "k": k, "method": "wilson", "z": z}


def run(args, env, timeout=600, check=True):
    p = subprocess.run(args, env=env, capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        sys.stderr.write(f"[fail] {' '.join(args[:3])} rc={p.returncode}\n{p.stdout[-400:]}\n{p.stderr[-300:]}\n")
    return p


def parse_env(stdout):
    brace = stdout.find("{")
    if brace < 0:
        return None
    try:
        return json.loads(stdout[brace:])
    except json.JSONDecodeError:
        return None


class Store:
    """一个隔离 profile：独立目录 + 独立 RPC 端口 + 独立 super。"""

    def __init__(self, root: str, tag: str, port: int, m3: str):
        self.dir = os.path.join(root, tag)
        self.tag = tag
        self.port = port
        self.m3 = m3
        self.super = ""
        self.env = {}

    def open(self):
        if os.path.isdir(self.dir):
            shutil.rmtree(self.dir)
        os.makedirs(self.dir, exist_ok=True)
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("RSRS_", "ONEMEMORY_", "RESPIRE_"))}
        env.update(RSRS_DATA_DIR=self.dir, RSRS_RPC_PORT=str(self.port),
                   RSRS_SUPER="A3-000000-000000-000000-000000-000000-000000",
                   RSRS_NO_AUTOSYNC="1", RSRS_UPDATE_CHECK="0", RSRS_ENGINE="cpu",
                   RSRS_M3_DIR=self.m3, RSRS_FEEDBACK="0", RSRS_ABLATE="hot")
        p = run(["rsrs", "keygen", "--json"], env, timeout=300)
        d = parse_env(p.stdout) or {}
        self.super = (d.get("summary") or {}).get("super") or ""
        if not self.super:
            raise RuntimeError(f"{self.tag}: keygen 未返回 super")
        env["RSRS_SUPER"] = self.super
        self.env = env
        # keygen 会把带占位 super 的 runtime 拉起来；必须停掉，让后续命令用真 super 重新 spawn
        run(["rsrs", "--runtime-internal", "--stop"], env, timeout=120, check=False)
        time.sleep(0.5)
        return self

    def import_items(self, items):
        path = os.path.join(self.dir, "import.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False)
        return run(["rsrs", "import", path, "--json"], self.env, timeout=1800)

    def wait_index(self, probe="预热探针", budget=300):
        """就绪判据 = 空转探针 recall 的 `embedding_model` 非 null。

        坑：`status.summary.retrieval_index.worker_active` 恒为 true（是常驻 worker 进程
        是否存活，不是「索引待办数」），拿它当就绪条件会白等到超时（本轮实测 420s/库）。
        """
        t0 = time.time()
        state = None
        while time.time() - t0 < budget:
            p = run(["rsrs", "status", "--json"], self.env, timeout=120, check=False)
            d = parse_env(p.stdout) or {}
            ri = (d.get("summary") or {}).get("retrieval_index") or {}
            state = {"state": ri.get("state"), "worker_active": ri.get("worker_active"),
                     "running": ri.get("running"), "error": ri.get("error"),
                     "local_total": (d.get("summary") or {}).get("local_total")}
            pr = self.recall(probe, 1)
            if pr["embedding_model"] and state.get("state") == "ready":
                return dict(state, embedding_model=pr["embedding_model"]), round(time.time() - t0, 1)
            time.sleep(4)
        return state, round(time.time() - t0, 1)

    def recall(self, query, limit):
        p = run(["rsrs", "recall", query, "--limit", str(limit), "--json", "--titles"],
                self.env, timeout=300, check=False)
        d = parse_env(p.stdout) or {}
        det = d.get("details") or []
        hits = []
        for h in det:
            if isinstance(h, dict) and h.get("title"):
                hits.append({"title": h["title"], "score": h.get("score")})
        return {"rc": p.returncode, "mode": (d.get("summary") or {}).get("mode"),
                "embedding_model": (d.get("summary") or {}).get("embedding_model"),
                "hits": hits, "error": (d.get("errors") or [None])[0]}

    def close(self):
        run(["rsrs", "--runtime-internal", "--stop"], self.env, timeout=120, check=False)


def item(title, content, created_at, tags=None):
    return {"title": title, "content": content, "kind": "context",
            "importance": "important", "created_at": created_at,
            "tags": tags or []}


def rank_of(titles, golds):
    for i, t in enumerate(titles, 1):
        if t in golds:
            return i
    return 0


# ── C1 重复强化 ────────────────────────────────────────────────────────────────

def build_c1(n, root, m3, port):
    rows, arms = [], {}
    for level in (1, 3, 5):
        st = Store(root, f"c1-r{level}", port + level, m3).open()
        items, gold = [], {}
        for i, (topic, fact) in enumerate(TOPICS[:n], 1):
            key = f"HM-RP-{i:02d}"
            titles = []
            for r in range(1, level + 1):
                t = f"{key}-r{r}" if level > 1 else key
                # 同组正文保留核心事实，仅加序注，避免 import 的「同内容去重」吞条目
                body = f"{fact}（第 {r} 次记录：{topic}）"
                items.append(item(t, body, f"2026-0{(i % 9) + 1}-1{r}T09:00:00Z", ["hm", "repeat"]))
                titles.append(t)
            gold[key] = set(titles)
        st.import_items(items)
        idx, wait_s = st.wait_index()
        res = []
        for i, (topic, fact) in enumerate(TOPICS[:n], 1):
            key = f"HM-RP-{i:02d}"
            # 题面用主题级改写，不照抄记忆正文（照抄会触顶：实测 20/20）
            q = f"{topic}的具体做法是怎么定的"
            r = st.recall(q, 5)
            titles = [h["title"] for h in r["hits"]]
            g = gold[key]
            res.append({"key": key, "n_planted": level, "returned": titles,
                        "rank": rank_of(titles, g), "hit@1": rank_of(titles, g) == 1,
                        "hit@5": rank_of(titles, g) > 0,
                        "mode": r["mode"], "rc": r["rc"]})
        st.close()
        k5 = sum(1 for x in res if x["hit@5"])
        k1 = sum(1 for x in res if x["hit@1"])
        arms[f"repeat_{level}"] = {
            "n_planted": level, "n_items": len(items), "n_questions": len(res),
            "hit@5": wilson_ci(k5, len(res)), "hit@1": wilson_ci(k1, len(res)),
            "index_wait_s": wait_s, "index_state": idx,
            "recall_mode": res[0]["mode"] if res else None, "rows": res,
        }
        rows.extend(res)
        print(f"  C1 repeat={level}: hit@5 {k5}/{len(res)} hit@1 {k1}/{len(res)} "
              f"(items={len(items)}, index_wait={wait_s}s, mode={res[0]['mode'] if res else '?'})", flush=True)
    return arms


# ── C2 时间衰减 + C3 错误纠偏（共用一库，主题/查询互斥）────────────────────────

def build_c2_c3(n, root, m3, port):
    st = Store(root, "c2c3", port, m3).open()
    items, gold2, gold3 = [], {}, {}
    for i, (topic, fact) in enumerate(TOPICS[:n], 1):
        old_t, new_t = f"HM-RC-{i:02d}-v1", f"HM-RC-{i:02d}-v2"
        items.append(item(old_t, f"{fact}（旧版约定，{topic}）", "2025-03-05T09:00:00Z", ["hm", "recency"]))
        items.append(item(new_t, f"{fact}（现行版本，{topic}）", "2026-09-20T09:00:00Z", ["hm", "recency"]))
        gold2[old_t] = {old_t}
        gold2[new_t] = {new_t}
    for i, (topic, fact) in enumerate(TOPICS[:n], 1):
        wrong_t, fix_t = f"HM-CR-{i:02d}-wrong", f"HM-CR-{i:02d}-fixed"
        items.append(item(wrong_t, f"误记为：{fact}（{topic}，早期结论，已被纠正）",
                          "2025-11-11T09:00:00Z", ["hm", "correction"]))
        items.append(item(fix_t, f"纠正结论：{fact}（{topic}，以此为准）",
                          "2026-05-08T09:00:00Z", ["hm", "correction"]))
        gold3[wrong_t] = {fix_t}
    st.import_items(items)
    idx, wait_s = st.wait_index()

    rec, cor = [], []
    for i, (topic, fact) in enumerate(TOPICS[:n], 1):
        new_t, old_t = f"HM-RC-{i:02d}-v2", f"HM-RC-{i:02d}-v1"
        r = st.recall(f"{topic}现在执行的约定是哪一版", 5)
        titles = [h["title"] for h in r["hits"]]
        rec.append({"key": new_t, "returned": titles,
                    "new_rank": rank_of(titles, {new_t}), "old_rank": rank_of(titles, {old_t}),
                    "new_top1": rank_of(titles, {new_t}) == 1,
                    "new_in_top5": rank_of(titles, {new_t}) > 0,
                    "stale_top1": rank_of(titles, {old_t}) == 1,
                    "mode": r["mode"], "rc": r["rc"]})
    for i, (topic, fact) in enumerate(TOPICS[:n], 1):
        fix_t, wrong_t = f"HM-CR-{i:02d}-fixed", f"HM-CR-{i:02d}-wrong"
        r = st.recall(f"{topic}之前记错了，现在的正确结论是什么", 5)
        titles = [h["title"] for h in r["hits"]]
        fr, wr = rank_of(titles, {fix_t}), rank_of(titles, {wrong_t})
        cor.append({"key": fix_t, "returned": titles, "fixed_rank": fr, "wrong_rank": wr,
                    "fixed_top1": fr == 1, "wrong_top1": wr == 1,
                    "fixed_beats_wrong": (fr > 0 and (wr == 0 or fr < wr)),
                    "mode": r["mode"], "rc": r["rc"]})
    st.close()

    def agg(rows, key):
        k = sum(1 for x in rows if x[key])
        return wilson_ci(k, len(rows))

    arms = {
        "recency": {"n_items": 2 * n, "n_questions": len(rec),
                    "new_top1": agg(rec, "new_top1"), "new_in_top5": agg(rec, "new_in_top5"),
                    "stale_top1": agg(rec, "stale_top1"),
                    "index_wait_s": wait_s, "index_state": idx,
                    "recall_mode": rec[0]["mode"] if rec else None, "rows": rec},
        "correction": {"n_items": 2 * n, "n_questions": len(cor),
                       "fixed_top1": agg(cor, "fixed_top1"), "wrong_top1": agg(cor, "wrong_top1"),
                       "fixed_beats_wrong": agg(cor, "fixed_beats_wrong"),
                       "index_wait_s": wait_s, "index_state": idx,
                       "recall_mode": cor[0]["mode"] if cor else None, "rows": cor},
    }
    for name in ("recency", "correction"):
        a = arms[name]
        print(f"  C2/C3 {name}: " + " ".join(
            f"{k}={round(v['point'], 4)}(k={v['k']}/{v['n']})" for k, v in a.items()
            if isinstance(v, dict) and "point" in v) + f" (index_wait={wait_s}s, mode={a['recall_mode']})",
            flush=True)
    return arms


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20, help="每个题型的主题数（n≥20）")
    ap.add_argument("--only", default="c1,c2,c3")
    ap.add_argument("--root", default="/tmp/agimem-human-dim")
    ap.add_argument("--m3", default=M3_DEFAULT)
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "human-dimension.json"))
    args = ap.parse_args()
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    os.makedirs(args.root, exist_ok=True)

    if not os.path.isdir(args.m3):
        print(f"警告：M3 模型目录不存在 {args.m3}，召回将退化为 lexical", file=sys.stderr)

    out = {"schema": "agimem-human-dimension/1", "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "n_topics": args.n, "isolated_root": args.root,
           "discipline": {"write_scope": "仅隔离 profile（每臂独立目录+独立 RSRS_RPC_PORT+独立 super）",
                          "real_store": "未读写 ~/.rsrs", "ablate": "RSRS_ABLATE=hot",
                          "scoring": "标题 token 命中，机械判分，零 LLM"},
           "arms": {}}
    port = 16110
    if "c1" in only:
        print(f"C1 重复强化（n={args.n}，档位 1/3/5）", flush=True)
        out["arms"].update(build_c1(args.n, args.root, args.m3, port))
    if only & {"c2", "c3"}:
        print(f"C2 时间衰减 / C3 错误纠偏（n={args.n}）", flush=True)
        out["arms"].update(build_c2_c3(args.n, args.root, args.m3, port + 50))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

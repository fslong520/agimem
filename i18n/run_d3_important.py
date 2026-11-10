#!/usr/bin/env python3
"""run_d3_important.py — D3 全量 --importance important 重跑 + 采纳合并（两档阈值）。

两臂：
  45  判重命中即采纳（等价现行 merge 线 0.45）
  50  仅采纳 similarity >= 50% 的候选，低于则 --force 落副本（模拟 merge 线 0.50）

每臂：24 facts × 4 语言 = 96 次写入 → 记录 merge 建议与采纳 → model activate m3
→ 96 次跨语言召回 → 统计命中率与「四语言 top-1 同条」。

只写 /tmp 隔离库（DATA_DIR + 独立端口 + 独立 super）。库内 UUID 一律归一到 fid。
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import lexicon_i18n as lx

M3 = os.path.expanduser("~/.rsrs/models/bge-m3")
ROOT = "/tmp/agimem-i18n/stores"
OUT = os.path.join(HERE, "results")
PORTS = {"45": 17131, "50": 17132, "sf50": 17133, "sf45": 17134}


def load_jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


class Store:
    def __init__(self, arm: str):
        self.arm = arm
        self.dir = os.path.join(ROOT, f"d3i{arm}")
        self.port = PORTS[arm]
        self.pw = None
        self.title2fid = {}
        for f in lx.FACTS:
            for lang in lx.LANGS:
                self.title2fid[f["title"][lang]] = f["fid"]
        self.uuid2fid = {}

    def env(self):
        e = os.environ.copy()
        e.update({"RSRS_DATA_DIR": self.dir, "RSRS_M3_DIR": M3,
                  "RSRS_RPC_PORT": str(self.port), "RSRS_RETRIEVAL": "bge",
                  "RSRS_UPDATE_CHECK": "0"})
        if self.pw:
            e["RSRS_SUPER"] = self.pw
            e["RSRS_PASS"] = self.pw
        return e

    def run(self, args, timeout=900):
        for attempt in range(2):
            p = subprocess.run(args, capture_output=True, text=True, env=self.env(), timeout=timeout)
            raw = p.stdout
            i = raw.find("{")
            d = json.loads(raw[i:]) if i >= 0 else {}
            txt = raw + p.stderr
            if attempt == 0 and ("need RSRS_PASS" in txt or "need RSRS_SECRET" in txt):
                # 运行时重启后没认到主口令：停掉旧 runtime，让下次调用重新带 super 启动
                subprocess.run(["rsrs", "runtime", "stop", "--json"], capture_output=True,
                               text=True, env=self.env(), timeout=180)
                time.sleep(3)
                continue
            return p.returncode, d, raw, p.stderr
        return p.returncode, d, raw, p.stderr

    def retry(self, fn, n=2):
        last = None
        for _ in range(n):
            try:
                return fn()
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(2)
        raise last

    def keygen(self):
        os.makedirs(self.dir, exist_ok=True)
        rc, d, raw, err = self.run(["rsrs", "keygen", "--json"])
        self.pw = d["summary"]["super"]
        open(f"/tmp/agimem-i18n/pass_d3i{self.arm}.txt", "w").write(self.pw)
        os.chmod(f"/tmp/agimem-i18n/pass_d3i{self.arm}.txt", 0o600)

    def wait_ready(self, limit=180):
        t = 0
        while t < limit:
            rc, d, _, _ = self.run(["rsrs", "status", "--json"], timeout=120)
            idx = (d.get("summary") or {}).get("retrieval_index", {})
            if not idx.get("running") and not idx.get("scheduled"):
                return
            time.sleep(3)
            t += 3

    def activate(self):
        self.wait_ready()
        for attempt in range(3):
            rc, d, raw, err = self.run(["rsrs", "model", "activate", "m3", "--json"])
            if d.get("status") == "ok":
                return (d.get("summary") or {}).get("indexed")
            if "another model operation" in (raw + err):
                time.sleep(6)
                self.wait_ready()
                continue
            raise RuntimeError(f"activate fail: {raw[:200]} {err[:200]}")
        raise RuntimeError("activate fail: 3 attempts")

    def remember(self, lang, force=False, merge_ids=None, fid=None):
        f = next(x for x in lx.FACTS if x["fid"] == fid)
        args = ["rsrs", "remember", "--importance", "important",
                "--title", f["title"][lang]]
        if merge_ids:
            args += ["--merge-ids", ",".join(merge_ids)]
        elif force:
            args.append("--force")
        args += [f["body"][lang], "--json"]
        rc, d, raw, err = self.run(args)
        return d

    def recall(self, q, k=5):
        rc, d, raw, err = self.run(["rsrs", "recall", q, "--json", "--titles", "--limit", str(k)])
        det = d.get("details")
        return det if isinstance(det, list) else []

    def hit_fid(self, h):
        """按标题把命中归一到 fid（合并后的条目标题仍是语料标题之一）。"""
        t = h.get("title") if isinstance(h, dict) else None
        return self.title2fid.get(t or "")

    def stop(self):
        try:
            self.run(["rsrs", "runtime", "stop", "--json"], timeout=180)
        except Exception:  # noqa: BLE001
            pass


def parse_suggestions(d):
    """从 pending 响应里取 merge 候选。

    remember 的 pending 响应 details 为 null，候选在：
      items[]  -> value="similarity=54% title=..."（拿分数）
      actions[]-> "rsrs remember \"<combined content>\" --merge-ids \"id1,id2\""（拿 id）
    返回 (ids, top_sim)。
    """
    sims = []
    for it in d.get("items") or []:
        v = it.get("value") or ""
        if "similarity=" in v:
            try:
                sims.append(float(v.split("similarity=")[1].split("%")[0]) / 100.0)
            except ValueError:
                pass
    ids = []
    for a in d.get("actions") or []:
        if "--merge-ids" in a:
            seg = a.split("--merge-ids", 1)[1].strip().strip('"')
            ids = [x.strip() for x in seg.split(",") if x.strip()]
            break
    titles = []
    for it in d.get("items") or []:
        v = it.get("value") or ""
        if "title=" in v:
            titles.append(v.split("title=", 1)[1].strip())
    cands = []
    for k, cid in enumerate(ids[:len(titles)] or ids):
        t = titles[k] if k < len(titles) else ""
        sim = sims[k] if k < len(sims) else None
        cands.append({"id": cid, "title": t, "sim": sim})
    return cands, (max(sims) if sims else None)


def arm_run(arm: str, dataset_rows, resume=False):
    st = Store(arm)
    if resume:
        pwfile = f"/tmp/agimem-i18n/pass_d3i{arm}.txt"
        if os.path.exists(pwfile):
            st.pw = open(pwfile).read().strip()
    else:
        st.keygen()
    log = []
    merges = 0
    forced = 0
    sugg_hist = []
    for fid in ([] if resume else [f["fid"] for f in lx.FACTS]):
        for lang in lx.LANGS:
            d = st.remember(lang, fid=fid)
            status = d.get("status")
            s = d.get("summary") or {}
            cands, top_sim = parse_suggestions(d)
            if arm in ("sf50", "sf45"):
                # 正确采纳：只合并候选标题属于同一 fact 的条目（跨语言标题都登记在同一 fid 上）
                same = [c["id"] for c in cands if st.title2fid.get(c.get("title") or "") == fid]
                sug_ids = same
                top_sim = max([c["sim"] or 0 for c in cands if st.title2fid.get(c.get("title") or "") == fid],
                              default=None)
            else:
                sug_ids = [c["id"] for c in cands]
            sugg_hist.append({"fid": fid, "lang": lang, "status": status,
                              "state": s.get("state"), "n_sug": len(sug_ids),
                              "top_sim": round(top_sim, 4) if top_sim is not None else None,
                              "cross_fact_candidates": sum(1 for c in cands if st.title2fid.get(c.get("title") or "") not in (None, fid))})
            accepted = False
            if sug_ids:
                if arm == "45" or arm in ("sf50", "sf45") or (top_sim or 0) >= 0.50:
                    ids = sug_ids
                    d2 = st.remember(lang, merge_ids=ids, fid=fid)
                    merges += 1
                    accepted = True
                    newid = (d2.get("summary") or {}).get("id")
                    if newid:
                        st.uuid2fid[newid] = fid
                else:
                    d2 = st.remember(lang, force=True, fid=fid)
                    forced += 1
                    accepted = True
                    newid = (d2.get("summary") or {}).get("id")
                    if newid:
                        st.uuid2fid[newid] = fid
            elif status == "pending":
                # 只有 attach 候选、没有 merge 候选：arm 只测合并，但条目必须落库，否则后续比较没有对象
                d2 = st.remember(lang, force=True, fid=fid)
                forced += 1
                accepted = True
                newid = (d2.get("summary") or {}).get("id")
                if newid:
                    st.uuid2fid[newid] = fid
            elif status == "ok":
                newid = s.get("id")
                if newid:
                    st.uuid2fid[newid] = fid
            log.append({"fid": fid, "lang": lang, "status": status, "state": s.get("state"),
                        "n_sug": len(sug_ids), "accepted": accepted,
                        "top_sim": round(top_sim, 4) if top_sim is not None else None})
        print(f"[{arm}] {fid} merges={merges} forced={forced}", flush=True)
    indexed = st.activate()

    # 落库条数（按明文标题映射回 fid）
    con = sqlite3.connect(f"file:{st.dir}/rsrs.db?mode=ro", uri=True)
    rows = con.execute("select title from memories where deleted=0").fetchall()
    con.close()
    per_fact = {}
    unmatched = 0
    for (title,) in rows:
        fid = st.title2fid.get(title)
        if fid:
            per_fact[fid] = per_fact.get(fid, 0) + 1
        else:
            unmatched += 1

    # 跨语言召回 + top-1 同条
    hits, ident, det_rows = 0, 0, []
    by_lang = {}
    for r in dataset_rows:
        det = st.recall(r["query"])
        ids = [st.hit_fid(h) for h in det if isinstance(h, dict)]
        hit = r["fid"] in ids
        hits += hit
        top1 = st.hit_fid(det[0]) if det and isinstance(det[0], dict) else None
        det_rows.append({"qid": r["qid"], "fid": r["fid"], "lang": r["lang"],
                         "hit": hit, "top1": top1})
        by_lang.setdefault(r["lang"], []).append(hit)
    for fid in [f["fid"] for f in lx.FACTS]:
        tops = [x["top1"] for x in det_rows if x["fid"] == fid]
        if all(x["hit"] for x in det_rows if x["fid"] == fid) and len(set(t for t in tops if t)) == 1:
            ident += 1
    st.stop()
    return {
        "arm": arm, "merge_threshold": 0.45 if arm == "45" else 0.50,
        "writes": len(log), "merges": merges, "forced_copies": forced,
        "suggestion_hist": sugg_hist,
        "activations_indexed": indexed,
        "entries_total": len(rows), "unmatched_titles": unmatched,
        "entries_per_fact": per_fact,
        "mean_entries_per_fact": round(sum(per_fact.values()) / max(len(per_fact), 1), 3),
        "recall_hit": round(hits / len(dataset_rows), 4),
        "recall_hit_by_lang": {k: round(sum(v) / len(v), 4) for k, v in by_lang.items()},
        "identity_same_entry": round(ident / len(lx.FACTS), 4),
        "rows": det_rows,
        "log": log,
    }


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    ds = load_jsonl(os.path.join(HERE, "dataset", "i18n_evalset.jsonl"))
    d3rows = [r for r in ds if r["class"] == "d3"]
    args = sys.argv[1:] or ["45", "50"]
    result = {}
    for spec in args:
        arm, _, mode = spec.partition(":")
        resume = mode == "resume"
        if resume:
            # 续跑要能解锁：主口令在 keygen 时已写 /tmp
            pwfile = f"/tmp/agimem-i18n/pass_d3i{arm}.txt"
            if os.path.exists(pwfile):
                pass
        print(f"== arm {arm} resume={resume} ==", flush=True)
        result[arm] = arm_run(arm, d3rows, resume=resume)
        print(json.dumps({k: result[arm][k] for k in
                          ("merges", "forced_copies", "entries_total", "mean_entries_per_fact",
                           "recall_hit", "identity_same_entry")}, ensure_ascii=False), flush=True)
    with open(os.path.join(OUT, "d3-important.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

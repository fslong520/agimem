#!/usr/bin/env python3
"""collect_i18n.py — 在 6 个隔离库里实写实召回（只写 /tmp，绝不碰真库）。

库与用途：
  d1      每条 fact 用轮转语言写入一次（zh/en/ja/es 各 6 条）→ D1 语言公平性
  d2_<L>  每条 fact 全部用语言 L 写入 → D2 跨语言锚定（写 L、查其他语言）
  d3      每条 fact 四种语言各写一次 → D3 跨语言同一性（重复写入是否被当成一件事）

每个库：keygen（主口令写 /tmp 600）→ 逐条 remember → model activate m3（建语义索引）
→ 逐题 recall --json --titles --limit 5 → runtime stop。

落盘脱敏：召回/写入得到的库内 UUID 一律换成占位（语料条目 → fid，其余 → e+7 位），
真库 id、标题、正文都不进仓。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

import lexicon_i18n as lx

HERE = os.path.dirname(os.path.abspath(__file__))
ISO_ROOT = "/tmp/agimem-i18n/stores"
M3 = os.path.expanduser("~/.rsrs/models/bge-m3")
PORTS = {"d1": 17101, "d2_zh": 17102, "d2_en": 17103, "d2_ja": 17104,
         "d2_es": 17105, "d3": 17106}


def load_jsonl(path):
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(json.loads(line))
    return out


class Store:
    def __init__(self, name: str):
        self.name = name
        self.dir = os.path.join(ISO_ROOT, name)
        self.passfile = f"/tmp/agimem-i18n/pass_{name}.txt"
        self.pw = None
        self.t0 = time.time()
        self.calls = 0

    def env(self):
        env = os.environ.copy()
        env.update({
            "RSRS_DATA_DIR": self.dir,
            "RSRS_M3_DIR": M3,
            "RSRS_RPC_PORT": str(PORTS[self.name]),
            "RSRS_RETRIEVAL": "bge",
            "RSRS_UPDATE_CHECK": "0",
        })
        if self.pw:
            # 运行时重启后，主口令走 RSRS_SUPER 才能解锁；PASS 仅作兼容
            env["RSRS_SUPER"] = self.pw
            env["RSRS_PASS"] = self.pw
        return env

    def run(self, args, timeout=300):
        self.calls += 1
        p = subprocess.run(args, capture_output=True, text=True, env=self.env(), timeout=timeout)
        return p

    def json_run(self, args, timeout=300):
        """带 1 次瞬时重试：运行时偶发重连会报 need RSRS_PASS。"""
        for attempt in range(3):
            try:
                return self._json_run_once(args, timeout)
            except RuntimeError as e:  # noqa: BLE001
                msg = str(e)
                transient = any(k in msg for k in ("need RSRS_PASS", "need RSRS_SECRET", "error_type",
                                                   "status=fail", "runtime"))
                if attempt == 2 or not transient:
                    raise
                time.sleep(2.5 * (attempt + 1))

    def _json_run_once(self, args, timeout=300):
        p = self.run(args, timeout)
        raw = p.stdout
        i = raw.find("{")
        if i < 0:
            raise RuntimeError(f"{self.name}: 无 JSON exit={p.returncode} out={raw[:200]} err={p.stderr[:200]}")
        d = json.loads(raw[i:])
        # status=skip 是「召回无候选过闸」的合法空结果（不是错误）；fail 才是错误
        if d.get("status") not in ("ok", "skip"):
            raise RuntimeError(f"{self.name}: {args[1:3]} status={d.get('status')} err={d.get('errors')}")
        return d

    def keygen(self):
        os.makedirs(self.dir, exist_ok=True)
        d = self.json_run(["rsrs", "keygen", "--json"])
        self.pw = d["summary"]["super"]
        with open(self.passfile, "w") as fh:
            fh.write(self.pw)
        os.chmod(self.passfile, 0o600)
        return d

    def write(self, title, body):
        return self.json_run(["rsrs", "remember", "--title", title, body, "--json"])

    def wait_index_ready(self, limit_s=120):
        """等后台索引 worker 收工，避免与 model activate 抢模型操作。"""
        waited = 0.0
        while waited < limit_s:
            p = self.run(["rsrs", "status", "--json"])
            try:
                idx = json.loads(p.stdout[p.stdout.find("{"):])["summary"]["retrieval_index"]
            except Exception:  # noqa: BLE001
                return waited
            if not idx.get("running") and not idx.get("scheduled"):
                return waited
            time.sleep(3)
            waited += 3
        return waited

    def activate(self):
        """model activate m3；与后台索引冲突时有界重试（≤2 次）。"""
        last = None
        for attempt in range(3):
            self.wait_index_ready()
            try:
                return self.json_run(["rsrs", "model", "activate", "m3", "--json"], timeout=900)
            except RuntimeError as e:  # noqa: BLE001
                last = e
                if "another model operation" not in str(e):
                    raise
                time.sleep(6)
        raise last

    def recall(self, query, limit=5):
        d = self.json_run(["rsrs", "recall", query, "--json", "--titles", "--limit", str(limit)])
        det = d.get("details")
        return det if isinstance(det, list) else []

    def stop(self):
        try:
            return self.run(["rsrs", "runtime", "stop", "--json"], timeout=180).stdout[:120]
        except Exception as e:  # noqa: BLE001
            return f"stop err {e}"


def dump_predictions(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", default=os.path.join(HERE, "results", "i18n-predictions.jsonl"))
    ap.add_argument("--writes", default=os.path.join(HERE, "results", "i18n-writes.json"))
    ap.add_argument("--stats", default=os.path.join(HERE, "results", "i18n-collect-stats.json"))
    ap.add_argument("--topk", type=int, default=5)
    ap.add_argument("--only", default="", help="只跑这些库（逗号分隔），调试用")
    ap.add_argument("--reset", action="store_true", help="跑之前清空这些隔离库（仅 /tmp）")
    ap.add_argument("--query-only", action="store_true",
                    help="复用已写入的隔离库，只补召回（不重写条目、不重建索引）")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.predictions), exist_ok=True)
    dataset = load_jsonl(os.path.join(HERE, "dataset", "i18n_evalset.jsonl"))
    by_class = {}
    for r in dataset:
        by_class.setdefault(r["class"], []).append(r)

    facts = {f["fid"]: f for f in lx.FACTS}
    # D1 写入语言：与 gen 的轮转一致
    d1_write = {f["fid"]: lx.LANGS[i % len(lx.LANGS)] for i, f in enumerate(lx.FACTS)}

    plan = []
    plan.append(("d1", [(fid, d1_write[fid]) for fid in facts], by_class["d1"]))
    for lang in lx.LANGS:
        rows = [r for r in by_class["d2"] if r["write_lang"] == lang] + \
               [r for r in by_class["d2c"] if r["write_lang"] == lang]
        plan.append((f"d2_{lang}", [(fid, lang) for fid in facts], rows))
    plan.append(("d3", [(fid, lang) for fid in facts for lang in lx.LANGS], by_class["d3"]))

    only = {s for s in args.only.split(",") if s}
    predictions = []
    writes_ledger = {}
    stats = {"m3_dir": M3, "iso_root": ISO_ROOT, "stores": {}, "command": "rsrs 1.0.19 isolated stores, retrieval=bge, model activate m3"}
    id_map = {}       # uuid -> stable placeholder
    uuid_owner = {}   # uuid -> fid
    placeholder = 0

    def ph(uuid_hit: str) -> str:
        """查询命中 id 归一：语料条目 → fid，其余 → e 占位。"""
        nonlocal placeholder
        if uuid_hit in uuid_owner:
            return uuid_owner[uuid_hit]
        if uuid_hit not in id_map:
            placeholder += 1
            id_map[uuid_hit] = f"e{placeholder:07d}"
        return id_map[uuid_hit]

    def ph_entry(uuid_hit: str) -> str:
        """写入台账用：保留「是不是同一条」的信息，不解析成 fid。"""
        nonlocal placeholder
        if uuid_hit not in id_map:
            placeholder += 1
            id_map[uuid_hit] = f"e{placeholder:07d}"
        return id_map[uuid_hit]

    for name, entries, rows in plan:
        if only and name not in only:
            continue
        st = Store(name)
        if args.reset:
            shutil.rmtree(st.dir, ignore_errors=True)
            if os.path.exists(st.passfile):
                os.remove(st.passfile)
        st_t0 = time.time()
        store_stat = {"entries": 0, "actions": {}, "query_n": 0, "empty": 0, "recall_err": 0}
        print(f"== store {name}: {len(entries)} entries, {len(rows)} queries ==", flush=True)
        try:
            if not args.query_only:
                st.keygen()
                for fid, lang in entries:
                    f = facts[fid]
                    d = st.write(f["title"][lang], f["body"][lang])
                    s = d.get("summary") or {}
                    action = s.get("action") or "?"
                    store_stat["actions"][action] = store_stat["actions"].get(action, 0) + 1
                    eid = s.get("id")
                    store_stat["entries"] += 1
                    led = writes_ledger.setdefault(name, {}).setdefault(fid, {})
                    if eid:
                        led[lang] = {"entry_ph": ph_entry(eid), "action": action}
                        uuid_owner[eid] = fid
                    else:
                        led[lang] = {"entry_ph": None, "action": action}
                with open(os.path.join("/tmp/agimem-i18n", f"map_{name}.json"), "w", encoding="utf-8") as fh:
                    json.dump({k: v for k, v in uuid_owner.items()}, fh)
                act = st.activate()
                store_stat["activated_indexed"] = (act.get("summary") or {}).get("indexed")
                store_stat["activated_dims"] = (act.get("summary") or {}).get("dimensions")

            if args.query_only:
                mapfile = os.path.join("/tmp/agimem-i18n", f"map_{name}.json")
                if os.path.exists(mapfile):
                    with open(mapfile, encoding="utf-8") as fh:
                        uuid_owner.update(json.load(fh))
                else:
                    raise RuntimeError(f"{name}: 缺 /tmp 映射，无法只补查询")

            for r in rows:
                det = st.recall(r["query"], args.topk)
                hits = []
                for h in det:
                    hid = h.get("id") if isinstance(h, dict) else None
                    if not isinstance(hid, str) or not hid:
                        continue
                    hits.append({"id": ph(hid), "score": h.get("score")})
                if not hits:
                    store_stat["empty"] += 1
                store_stat["query_n"] += 1
                predictions.append({
                    "qid": r["qid"], "class": r["class"], "fid": r["fid"],
                    "lang": r["lang"], "write_lang": r["write_lang"], "hits": hits,
                    "_store": name,
                })
        except Exception as e:  # noqa: BLE001
            store_stat["error"] = str(e)[:300]
            print(f"!! store {name} 失败: {store_stat['error']}", file=sys.stderr, flush=True)
        finally:
            store_stat["stop"] = st.stop()
            store_rows = [r for r in predictions if r.get("_store") == name]
            dump_predictions(store_rows, os.path.join(os.path.dirname(args.predictions), f"pred-{name}.jsonl"))
            dump_predictions(predictions, args.predictions)
            store_stat["seconds"] = round(time.time() - st_t0, 1)
            store_stat["calls"] = st.calls
            stats["stores"][name] = store_stat
            print(f"   {json.dumps(store_stat, ensure_ascii=False)}", flush=True)

    merged = []
    preddir = os.path.dirname(args.predictions)
    for fn in sorted(os.listdir(preddir)):
        if fn.startswith("pred-") and fn.endswith(".jsonl"):
            merged.extend(load_jsonl(os.path.join(preddir, fn)))
    if not merged:
        merged = predictions
    for r in merged:
        r.pop("_store", None)
    with open(args.predictions, "w", encoding="utf-8") as fh:
        for r in merged:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(args.writes, "w", encoding="utf-8") as fh:
        json.dump(writes_ledger, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    stats["predictions"] = len(predictions)
    stats["total_seconds"] = round(sum(s.get("seconds", 0) for s in stats["stores"].values()), 1)
    with open(args.stats, "w", encoding="utf-8") as fh:
        json.dump(stats, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(json.dumps({"predictions": len(predictions), "stores": {k: v.get("error") or "ok" for k, v in stats["stores"].items()}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

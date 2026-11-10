#!/usr/bin/env python3
"""isolated_lib.py（H3 记忆动力学专用）— 隔离 rsrs 库的最小封装。

复制自 `agimem/tricky/isolated_lib.py` 的 profile 思路（不 import 它、不改它），
只保留 H3 需要的能力：建库 / 批量 import（可指定 created_at）/ 单条 remember --force /
recall --titles / 索引就绪等待 / 收尾。

为什么要 `remember --force`：H3 v2 要求**正文除 created_at 外逐字节相同**，
而 `rsrs import` 会吞掉正文完全相同的条目（tricky 层实测）。`remember` 无 `--created-at`
但 created_at 取当前时间，用「旧条目走 import（显式 2025-03）＋新条目走 remember --force（now）」，
既拿到两条字节相同的正文，又有时差——这正是 C2/C3 需要的唯一自变量。

纪律（同 tricky 层）：清空 RSRS_/ONEMEMORY_/RESPIRE_ 前缀 env；每臂独立 data dir + 独立端口
+ 独立 super；RSRS_ABLATE=hot（tests/27）；绝不碰 `~/.rsrs`、不改全局 config、不启停宿主 runtime。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

M3_DEFAULT = os.path.expanduser("~/.rsrs/models/bge-m3")


def run(args: List[str], env: Dict[str, str], timeout: int = 600, check: bool = True):
    p = subprocess.run(args, env=env, capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        sys.stderr.write(f"[fail] {' '.join(args[:3])} rc={p.returncode}\n"
                         f"{p.stdout[-600:]}\n{p.stderr[-400:]}\n")
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

    def __init__(self, root: str, tag: str, port: int, m3: str = M3_DEFAULT) -> None:
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
        p = run(["rsrs", "keygen", "--json"], env, timeout=900)
        d = parse_env(p.stdout) or {}
        self.super = (d.get("summary") or {}).get("super") or ""
        if not self.super:
            raise RuntimeError(f"{self.tag}: keygen 未返回 super：{p.stdout[-300:]} {p.stderr[-200:]}")
        env["RSRS_SUPER"] = self.super
        self.env = env
        # keygen 用占位 super 拉起了 runtime，必须停掉，让后续命令用真 super 重新 spawn
        run(["rsrs", "--runtime-internal", "--stop"], env, timeout=180, check=False)
        time.sleep(0.5)
        return self

    def import_items(self, items: List[Dict[str, Any]]):
        path = os.path.join(self.dir, "import.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False)
        return run(["rsrs", "import", path, "--json"], self.env, timeout=3600)

    def remember(self, content: str, title: str, importance: str = "important"):
        """单条写入。--force 跳过 judge-then-store（否则会被去重/合并规则拦下）。"""
        return run(["rsrs", "remember", content, "--title", title,
                    "--importance", importance, "--force", "--json"],
                   self.env, timeout=600)

    def status(self) -> Dict[str, Any]:
        p = run(["rsrs", "status", "--json"], self.env, timeout=180, check=False)
        return (parse_env(p.stdout) or {}).get("summary") or {}

    def recall(self, query: str, limit: int = 5) -> Dict[str, Any]:
        p = run(["rsrs", "recall", query, "--limit", str(limit), "--json", "--titles"],
                self.env, timeout=600, check=False)
        d = parse_env(p.stdout) or {}
        hits = []
        for h in d.get("details") or []:
            if isinstance(h, dict):
                hits.append({"id": h.get("id"), "title": h.get("title"), "score": h.get("score")})
        summ = d.get("summary") or {}
        return {"rc": p.returncode, "mode": summ.get("mode"),
                "embedding_model": summ.get("embedding_model"),
                "local_total": summ.get("local_total"),
                "hits": hits, "error": (d.get("errors") or [None])[0]}

    def wait_index(self, expect_total: Optional[int] = None, budget: int = 900):
        """就绪判据 = 探针 recall 的 embedding_model 非 null 且 status.state=ready。

        坑：`retrieval_index.worker_active` 恒为 true（常驻 worker 存活），不是待办数。
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


def item(title: str, content: str, created_at: str,
         importance: str = "important", tags: Optional[List[str]] = None) -> Dict[str, Any]:
    """import 条目（created_at 可显式指定，这是 H3 v2 的唯一自变量）。"""
    return {"title": title, "content": content, "kind": "context",
            "importance": importance, "created_at": created_at,
            "tags": tags or []}

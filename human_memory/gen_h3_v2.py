#!/usr/bin/env python3
"""gen_h3_v2.py — H3「记忆动力学」v2 生成器：让 created_at 成为唯一自变量的确定性题集。

针对旧 C2/C3 被判「度量无效」的四条病因（tests/32 §五 H3.3 的证据：题面字面差把分数从
0.445 摆到 0.733、新旧嵌入分差仅 0.002–0.033、第 1 归属由「版本/V2/新旧」标签词决定、
两题型共库互相压制），v2 的设计一一对应：

  ① **正文逐字节相同**：同一对（旧/新、纠正前/纠正后）的 content 完全一致，**一个字节都不差**；
     时间只体现在 `created_at`（旧条目 2025-03-01，新条目为写入当时的机械时钟）。
  ② **同主题成对比较**：每对只在同一主题内比，不跨主题混池；不数 top-k「有没有出现」，
     改数「谁排前面」。
  ③ **分库跑**：recency 一库、correction 一库、repeat 一库（各自独立 data dir/端口/super）。
  ④ **标题中立 + 映射反平衡**：标题里不写 old/new/旧/新/版本/废弃/纠正，只用 `-a`/`-b` 等中性码，
     且 a/b 与「旧/新」的对应关系按主题序号**反平衡**，防止「系统偏爱字母 a」被误读成时间效应。
  ⑤ **C1 改排序口径**：旧 C1 是「沉淀 1/3/5 条都能命中」→ 三档全 1.0 触顶、无分辨力。
     v2 改成竞赛：同一事实写 3 条（正文相同），同等相关但只写 1 次的干扰条目写 1 条，
     看重复条目是否压过单次条目。

产物（进仓）：
  data/h3_v2_plan.json        三臂的条目计划（title/content/created_at/importance/source）
  data/h3_v2_dataset.jsonl    三臂的题面与 gold（机械推导，零人工答案）
不入仓：条目的真实 id（隔离库 UUID）——判分只用自造标题码。

用法：
    python3 gen_h3_v2.py [--n 20] [--seed 20261109]
"""
from __future__ import annotations

import argparse
import json
import os
import random
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
PLAN = os.path.join(DATA_DIR, "h3_v2_plan.json")
DATASET = os.path.join(DATA_DIR, "h3_v2_dataset.jsonl")
SEED = 20261109
N = 20
OLD_CREATED_AT = "2025-03-01T09:00:00Z"
NEW_CREATED_AT = "now"   # 由 remember 写入时的机械时钟决定，生成期只记语义

# 24 个通用工程约定主题（全合成，无真人/无真实项目名）。每题一个主题，取前 N 个。
TOPICS: List[str] = [
    "夜间发布窗口", "告警收敛阈值", "备份保留期", "灰度比例", "值班交接方式",
    "索引重建时间", "慢查询阈值", "发布审批人", "日志留存级别", "容量预警水位",
    "熔断重试次数", "缓存预热范围", "数据库连接池", "密钥轮换周期", "压测基线并发",
    "故障分级标准", "月度演练内容", "监控采集间隔", "变更窗口长度", "异地副本同步",
    "接口兼容策略", "资源回收周期", "文档归档位置", "新人上手路径",
]

# 每主题一句「约定」。C2/C3 的一对条目正文**完全相同**，都用这一句（不含任何新旧标签词）。
FACTS: Dict[str, str] = {
    "夜间发布窗口": "夜间发布窗口定在每周三 23:30 执行，发布前十分钟冻结变更单，窗口结束后十五分钟解除冻结。",
    "告警收敛阈值": "告警收敛阈值按五分钟内同类事件只报一次执行，重复事件合并进首条。",
    "备份保留期": "备份保留期按三十天执行，到期自动清理并留一份月度快照。",
    "灰度比例": "灰度发布比例按百分之五起步、每十分钟翻倍执行，直到全量。",
    "值班交接方式": "值班交接按每日九点半站会对齐未决事项执行，交接单当日归档。",
    "索引重建时间": "索引重建安排在执行日周日凌晨两点，避开报表作业。",
    "慢查询阈值": "慢查询阈值按八百毫秒执行，超过记入慢日志并打标。",
    "发布审批人": "发布审批人固定为当周值班负责人加一名架构组成员，双签后放行。",
    "日志留存级别": "日志留存按核心链路九十天、其余十四天执行，过期自动归档。",
    "容量预警水位": "容量预警水位按磁盘使用率百分之七十八执行，触发即申请扩容。",
    "熔断重试次数": "熔断后重试次数按两次执行，退避从两秒起。",
    "缓存预热范围": "缓存预热范围按首页与搜索联想接口执行，其余按需加载。",
    "数据库连接池": "数据库连接池上限按一百二十执行，等待超时三秒。",
    "密钥轮换周期": "密钥轮换周期按四十五天执行，轮换窗口排在周二。",
    "压测基线并发": "压测基线并发按八百执行，单轮持续三十分钟。",
    "故障分级标准": "故障分级按影响下单为一级、影响浏览为二级执行，一级十分钟内上报。",
    "月度演练内容": "月度演练内容按机房单点断电切换执行，演练后出复盘。",
    "监控采集间隔": "监控采集间隔按二十秒执行，采样率保持全量。",
    "变更窗口长度": "常规变更窗口长度按九十分钟执行，超时须重新申请。",
    "异地副本同步": "异地副本按异步同步执行，允许十五分钟滞后。",
    "接口兼容策略": "接口兼容策略按保留三个大版本执行，旧版半年后下线。",
    "资源回收周期": "测试环境资源按每周五自动回收执行，需重新申请。",
    "文档归档位置": "历史设计文档按统一归档到知识库 archive 目录执行。",
    "新人上手路径": "新人上手按读码、修小 bug、独立提测三步执行。",
}

# C1 干扰条目：同主题、同等相关（都关于该主题），但说的是另一件事，且只写一次。
DISTRACTORS: Dict[str, str] = {
    "夜间发布窗口": "夜间发布窗口的变更单模板里，回滚步骤要写清楚谁执行、谁复核。",
    "告警收敛阈值": "告警收敛之后，值班仍要在早会上过一遍被合并的告警标题。",
    "备份保留期": "备份恢复演练每季度做一次，演练记录进当月复盘。",
    "灰度比例": "灰度期间新旧两版要同时看错误率和延迟两条曲线。",
    "值班交接方式": "交接站会由前一班主持，后一班记录，散会前对齐未决项负责人。",
    "索引重建时间": "索引重建前先核对分片数量与副本数，避免重建后写入倾斜。",
    "慢查询阈值": "慢查询日志按天切分，排查时先看当天再回看上周同日。",
    "发布审批人": "审批人休假时由同组另一名架构组成员代签，代签要注明原因。",
    "日志留存级别": "日志级别调整属于变更，需走变更单并通知下游消费方。",
    "容量预警水位": "容量预警触发后先看增长斜率，再判断是扩容还是清理。",
    "熔断重试次数": "重试要带幂等键，否则重试等于制造重复写。",
    "缓存预热范围": "预热失败不应阻塞启动，降级为按需加载并告警。",
    "数据库连接池": "连接池指标要一起看等待队列长度，只看上限会误判。",
    "密钥轮换周期": "轮换前确认所有调用方都支持双密钥并行验证。",
    "压测基线并发": "压测数据要脱敏，压测库与生产库物理隔离。",
    "故障分级标准": "分级之后还要定通报范围，一级故障同步给业务负责人。",
    "月度演练内容": "演练脚本要预先评审，避免演练本身造成二次故障。",
    "监控采集间隔": "采集间隔缩短会抬高存储成本，需同步评估保留期。",
    "变更窗口长度": "变更窗口内不允许叠加发布，一次只做一件事。",
    "异地副本同步": "异步副本读取前要判断滞后水位，超阈值拒绝读。",
    "接口兼容策略": "兼容期内新增字段必须可选，不允许改已有字段含义。",
    "资源回收周期": "回收前会发通知，长期占用的资源需要登记用途。",
    "文档归档位置": "归档文档要带最后修改人与适用范围两行元信息。",
    "新人上手路径": "新人第一个小 bug 由导师陪跑，合并前做一次一对一讲解。",
}


def topic_code(i: int) -> str:
    return f"{i + 1:02d}"


def gen(n: int, seed: int) -> Dict[str, Any]:
    rng = random.Random(seed)
    topics = TOPICS[:n]

    arms: Dict[str, Dict[str, Any]] = {
        "recency": {"entries": [], "questions": []},
        "correction": {"entries": [], "questions": []},
        "repeat": {"entries": [], "questions": []},
    }

    for i, topic in enumerate(topics):
        code = topic_code(i)
        # 反平衡：奇数主题 a=旧、偶数主题 a=新
        old_suffix, new_suffix = ("a", "b") if i % 2 == 0 else ("b", "a")

        # ── C2 recency：正文逐字节相同，只有 created_at 不同 ──
        arms["recency"]["entries"].append({
            "title": f"HM-C2-{code}-{old_suffix}", "content": FACTS[topic],
            "created_at": OLD_CREATED_AT, "write_via": "import", "role": "old",
            "topic": topic})
        arms["recency"]["entries"].append({
            "title": f"HM-C2-{code}-{new_suffix}", "content": FACTS[topic],
            "created_at": NEW_CREATED_AT, "write_via": "remember", "role": "new",
            "topic": topic})
        arms["recency"]["questions"].append({
            "qid": f"c2-{code}", "arm": "recency", "topic": topic,
            "query": f"「{topic}」现在按哪条执行？",
            "pair": [f"HM-C2-{code}-{old_suffix}", f"HM-C2-{code}-{new_suffix}"],
            "gold_title": f"HM-C2-{code}-{new_suffix}",
            "other_title": f"HM-C2-{code}-{old_suffix}",
            "gold_expr": {"kind": "later_written", "a": f"HM-C2-{code}-{old_suffix}",
                          "b": f"HM-C2-{code}-{new_suffix}"},
            "note": "同主题成对；正文逐字节相同；gold=后写条目（created_at 更晚）",
        })

        # ── C3 correction：结构与 C2 相同，独立成库，题面用「结论」措辞 ──
        before_suffix, after_suffix = ("a", "b") if i % 2 == 0 else ("b", "a")
        arms["correction"]["entries"].append({
            "title": f"HM-C3-{code}-{before_suffix}", "content": FACTS[topic],
            "created_at": OLD_CREATED_AT, "write_via": "import", "role": "before",
            "topic": topic})
        arms["correction"]["entries"].append({
            "title": f"HM-C3-{code}-{after_suffix}", "content": FACTS[topic],
            "created_at": NEW_CREATED_AT, "write_via": "remember", "role": "after",
            "topic": topic})
        arms["correction"]["questions"].append({
            "qid": f"c3-{code}", "arm": "correction", "topic": topic,
            "query": f"「{topic}」现在应当按哪条结论执行？",
            "pair": [f"HM-C3-{code}-{before_suffix}", f"HM-C3-{code}-{after_suffix}"],
            "gold_title": f"HM-C3-{code}-{after_suffix}",
            "other_title": f"HM-C3-{code}-{before_suffix}",
            "gold_expr": {"kind": "later_written", "a": f"HM-C3-{code}-{before_suffix}",
                          "b": f"HM-C3-{code}-{after_suffix}"},
            "note": "同主题成对；正文逐字节相同；独立库；gold=后写（纠正后）条目",
        })

        # ── C1 repeat：同一事实写 3 条 vs 同等相关干扰写 1 条 ──
        fam = [f"HM-C1-{code}-k{j}" for j in (1, 2, 3)]
        distractor_title = f"HM-C1-{code}-z"
        for j, t in enumerate(fam):
            # 首条走 import（同文去重前只保留一条），其余两条走 remember --force
            arms["repeat"]["entries"].append({
                "title": t, "content": FACTS[topic], "created_at": NEW_CREATED_AT,
                "write_via": "import" if j == 0 else "remember",
                "role": "repeat", "topic": topic})
        arms["repeat"]["entries"].append({
            "title": distractor_title, "content": DISTRACTORS[topic],
            "created_at": NEW_CREATED_AT, "write_via": "remember", "role": "distractor",
            "topic": topic})
        arms["repeat"]["questions"].append({
            "qid": f"c1-{code}", "arm": "repeat", "topic": topic,
            "query": f"「{topic}」的做法是什么？",
            "family": fam, "distractor": distractor_title,
            "gold_expr": {"kind": "repeated_over_single", "family": fam,
                          "distractor": distractor_title},
            "note": "竞赛口径：重复写 3 条 vs 同等相关单次干扰 1 条；gold=重复族任一",
        })

    rng.shuffle(arms["recency"]["questions"])  # 仅打乱问序，不改配对
    plan = {
        "schema": "agimem-h3-v2-plan/1",
        "seed": seed, "n_per_arm": n,
        "old_created_at": OLD_CREATED_AT, "new_created_at": NEW_CREATED_AT,
        "design": {
            "byte_identical_body": True,
            "neutral_titles": "标题只用 -a/-b/-k1..k3/-z 中性码，不含 旧/新/版本/废弃/纠正 等标签词",
            "counterbalanced": "a/b 与 旧/新 的对应按主题序号反平衡（奇数 a=旧，偶数 a=新）",
            "separate_stores": ["recency", "correction", "repeat"],
            "import_dedupe_workaround": ("import 会吞正文相同条目 → 旧条目走 import（显式 "
                                         "2025-03-01）＋新条目走 remember --force（created_at=now），"
                                         "从而正文逐字节相同且时间有差"),
        },
        "arms": {k: {"entries": v["entries"], "questions": v["questions"]} for k, v in arms.items()},
    }
    return plan


def sanity(plan: Dict[str, Any]) -> None:
    n = plan["n_per_arm"]
    if n < 20:
        raise SystemExit(f"每臂题量不足 20: {n}")
    banned = ["旧版", "新版", "现行版本", "已废弃", "误记", "纠正", "版本", "V2", "old", "new"]
    for arm, data in plan["arms"].items():
        titles = [e["title"] for e in data["entries"]]
        if len(titles) != len(set(titles)):
            raise SystemExit(f"{arm}: 标题重复")
        # 正文逐字节相同（成对臂）：同一主题只允许 1 种正文
        if arm in ("recency", "correction"):
            by_topic: Dict[str, set] = {}
            for e in data["entries"]:
                by_topic.setdefault(e["topic"], set()).add(e["content"])
            for t, bodies in by_topic.items():
                if len(bodies) != 1:
                    raise SystemExit(f"{arm}/{t}: 同主题正文不一致（{len(bodies)} 种）")
        # import 路径的正文必须唯一（import 会吞同文条目）
        imp_bodies = [e["content"] for e in data["entries"] if e.get("write_via") == "import"]
        if len(imp_bodies) != len(set(imp_bodies)):
            raise SystemExit(f"{arm}: import 路径存在重复正文，会被去重吞条")

        # 标题不得含标签词
        for e in data["entries"]:
            for b in banned:
                if b in e["title"]:
                    raise SystemExit(f"{arm}: 标题含标签词 {b!r}: {e['title']}")
        # 题面不得含标签词
        for q in data["questions"]:
            for b in banned:
                if b in q["query"]:
                    raise SystemExit(f"{arm}: 题面含标签词 {b!r}: {q['query']}")
    # gold 必在 pair/family 内，且与 other/distractor 不同
    for q in plan["arms"]["recency"]["questions"]:
        if q["gold_title"] not in q["pair"] or q["other_title"] not in q["pair"]:
            raise SystemExit(f"{q['qid']}: pair 不一致")
    for q in plan["arms"]["correction"]["questions"]:
        if q["gold_title"] not in q["pair"] or q["other_title"] not in q["pair"]:
            raise SystemExit(f"{q['qid']}: pair 不一致")
    for q in plan["arms"]["repeat"]["questions"]:
        if q["distractor"] in q["family"]:
            raise SystemExit(f"{q['qid']}: 干扰条目混进族")


def main() -> int:
    ap = argparse.ArgumentParser(description="H3 v2 生成器")
    ap.add_argument("--n", type=int, default=N)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()

    plan = gen(args.n, args.seed)
    sanity(plan)

    if args.verify:
        with open(PLAN, encoding="utf-8") as f:
            old = json.load(f)
        same = json.dumps(old, ensure_ascii=False, sort_keys=True) == \
            json.dumps(plan, ensure_ascii=False, sort_keys=True)
        print(f"[verify] {'OK' if same else 'FAIL'} — 重生成与 data/h3_v2_plan.json 一致")
        return 0 if same else 1

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PLAN, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(DATASET, "w", encoding="utf-8") as f:
        for arm, data in plan["arms"].items():
            for q in data["questions"]:
                f.write(json.dumps(q, ensure_ascii=False, sort_keys=True) + "\n")

    for arm, data in plan["arms"].items():
        print(f"[gen_h3_v2] {arm}: 条目 {len(data['entries'])} / 题 {len(data['questions'])}")
    print(f"[gen_h3_v2] 写出 {os.path.relpath(PLAN, HERE)}、{os.path.relpath(DATASET, HERE)}"
          f"（n={args.n}/臂，seed={args.seed}）")
    print("[gen_h3_v2] 自检通过：正文成对逐字节相同、标题/题面无标签词、标题唯一、gold 在配对内")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

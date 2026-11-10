#!/usr/bin/env python3
"""gen_h9.py — H9「推理与元认知」六子类（R1–R6）：确定性 seed 生成语料与评测集，gold 机械推导。

用法：
    python3 gen_h9.py                 # 写 data/h9_tree.json + dataset/h9_evalset.jsonl
    python3 gen_h9.py --verify        # 重生成与既有文件比对（确定性证明）
    python3 gen_h9.py --per-type 16   # 每类题量（缺省 16，6 类共 96；R5 每构造 2 题）

六子类（AGI 分水岭④⑤：推理 + 元认知，零 LLM、gold 机械）：
  R1 因果归因→处方  同因泛化：题面给**新情境的改述**，gold=当初那条因果记录（含处方）。
                     测处方召回，不是字面复现——题面不复述正文的失败句与处方句。
  R2 反事实        「当初不 X 还会 Y 吗」：gold=记录了 X→Y 绑定的事件条目（构造绑定机械给）。
  R3 动态更新      消息传来后问当前值：gold=新值条目；stale=旧值条目；量化旧条目霸榜率。
  R4 压缩摘要      同主题 4 条（1 主线 + 3 细节）问主线：gold=主线条目；题面不复述主线原文。
  R5 元认知        (a) 记没记探针：已记型 gold=该条、未记型 gold=空（该属性全语料 0 出现）；
                   (b) 该存该扔：按既定规矩召回对应判例（重要/次要）。
  R6 跨来源置信    实测 vs 转述 vs 文档，gold=实测；量化转述霸榜率（复现 H4 T6 86.4% 口径）。

铁律守门（生成期强制，不是声明）：场景 ∈ 白名单、题面含该场景标志词、不命中禁题材词。
脱敏：全合成，无真人姓名（只用「同事甲/同事乙」）、无真库 id、无凭据。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
from typing import Any, Dict, List, Tuple

import h9_gold as hg
import scenarios as scn

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261110
PER_TYPE = 16
TREE_OUT = os.path.join(HERE, "data", "h9_tree.json")
EVALSET_OUT = os.path.join(HERE, "dataset", "h9_evalset.jsonl")

BANNED_SNIPPETS = ["sk-", "password", "口令", "api key", "密钥串", "赵", "钱", "孙"]
UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

# ---------------------------------------------------------------- 词库（16 组/池，全部手工对齐场景）

# R1 因果对：bad=正文原句；bad_q=题面改述（措辞不同，测同因泛化不测字面）
R1_CAUSES: List[Dict[str, str]] = [
    # deploy
    {"bad": "上线前没跑回归", "bad_q": "发布前把检查步骤全省了",
     "failure": "上线后核心链路大面积报错", "prescription": "发布单必须挂回归门禁，红灯不放行"},
    {"bad": "没设观察窗口就一口气放量", "bad_q": "刚放一点量就急着全量",
     "failure": "放量后错误率翻倍才发现", "prescription": "每档放量至少观察 15 分钟再进下一档"},
    # canary
    {"bad": "回滚预案没演练就上线", "bad_q": "没提前试过怎么退回去就发了",
     "failure": "出问题时回滚脚本跑不起来", "prescription": "回滚脚本随发布单一并演练留证"},
    {"bad": "灰度名单直接用了全量用户", "bad_q": "说是灰度其实人人都收到了",
     "failure": "灰度验证失去意义", "prescription": "灰度名单固定 10% 内部用户"},
    # api
    {"bad": "联调时没对签名时间窗", "bad_q": "两边对接没核对时间偏差",
     "failure": "上线后批量验签失败", "prescription": "对接文档写明时间窗容差并双向校时"},
    {"bad": "回调没做幂等就接了", "bad_q": "没防重复推送就开始对接",
     "failure": "上游重推导致重复入账", "prescription": "回调入口先查幂等键再落库"},
    # handoff
    {"bad": "交接只口头说了路径", "bad_q": "关键位置光嘴上交代没落纸",
     "failure": "接手后找不到脚本位置", "prescription": "交接单逐项写路径并让接手人复核"},
    {"bad": "值班手册没更新就移交", "bad_q": "手册还是老版本就交出去了",
     "failure": "新班组按旧手册误操作", "prescription": "移交前手册变更项必须过一遍"},
    # meeting
    {"bad": "口径定了没同步给下游", "bad_q": "定好的算法只留在会里",
     "failure": "下游按老口径出报表对不上", "prescription": "口径变更当天发公告并通知所有取数方"},
    {"bad": "纪要里只写了结论没写边界", "bad_q": "只记了做什么没记不做什么",
     "failure": "执行时把边界外的也改了", "prescription": "纪要必须含适用范围与排除项"},
    # ops
    {"bad": "扩容前没看连接池水位", "bad_q": "机器加了没管数据库连接",
     "failure": "扩容后连接池打满照样超时", "prescription": "扩容单必查下游连接池余量"},
    {"bad": "回滚点没验证就标了完成", "bad_q": "存档没试过恢复就报完工",
     "failure": "真回滚时存档损坏", "prescription": "回滚点每 24 小时做一次恢复抽验"},
    # migration
    {"bad": "迁移前没抽样比对", "bad_q": "搬完数据没抽查就切流",
     "failure": "切流后发现字段错位", "prescription": "切换前按百分之一抽样双端比对"},
    {"bad": "分批太大一口气迁", "bad_q": "一次搬几十万行不停顿",
     "failure": "锁表超时拖垮业务", "prescription": "单批不超 5000 行且批间停顿"},
    # approval
    {"bad": "权限批了没设到期", "bad_q": "授权给了就没人管了",
     "failure": "人员离岗权限仍有效", "prescription": "所有临时权限必须带 7 天到期"},
    {"bad": "审批只看申请不看范围", "bad_q": "点同意前没核对要哪些表",
     "failure": "申请只读却拿到写权限", "prescription": "审批按最小权限逐项勾选"},
]

# R2 反事实事件对：action→outcome 强绑定；action_q/outcome_q 为题面改述
R2_EVENTS: List[Dict[str, str]] = [
    {"action": "把超时从 3 秒改成 1 秒", "action_q": "调紧了超时配置",
     "outcome": "长尾请求被掐断引发告警", "outcome_q": "引发了一连串告警"},
    {"action": "直接改了生产库索引", "action_q": "没走变更就动了索引",
     "outcome": "写入抖动持续两小时", "outcome_q": "写入出现持续抖动"},
    {"action": "灰度比例一步拉到全量", "action_q": "一步到位全量放开了",
     "outcome": "全量用户瞬间受影响", "outcome_q": "所有用户立刻中招"},
    {"action": "回滚时只回了代码没回配置", "action_q": "退回去时漏了一半",
     "outcome": "新旧配置混跑报错", "outcome_q": "两边对不上开始报错"},
    {"action": "联调用了假数据没走真链路", "action_q": "测试阶段全是编的数据",
     "outcome": "上线后字段类型对不上", "outcome_q": "正式环境格式全错"},
    {"action": "回调地址填成了测试域名", "action_q": "接收入口指错了地方",
     "outcome": "生产事件全部丢弃", "outcome_q": "事件一个都没收到"},
    {"action": "把凭据直接贴进了纪要", "action_q": "敏感信息没做遮挡就外发",
     "outcome": "凭据被迫全量轮换", "outcome_q": "所有凭据都换了重来"},
    {"action": "在群里转发了密钥截图", "action_q": "图省事直接发了原图",
     "outcome": "截图被二次传播", "outcome_q": "内容被人转来转去"},
    {"action": "口径没试算就上线报表", "action_q": "没拿历史数据对一遍就发布",
     "outcome": "首日数字全线偏差", "outcome_q": "第一天的数全都对不上"},
    {"action": "纪要漏发给了数据组", "action_q": "有一方没收到会议结论",
     "outcome": "第二天又返工重出", "outcome_q": "隔天全部推倒重做"},
    {"action": "扩容时关了熔断保护", "action_q": "为了图快把保护摘了",
     "outcome": "下游被瞬时打挂", "outcome_q": "下游当场扛不住"},
    {"action": "回滚没通知业务方", "action_q": "动作做了但没人知会",
     "outcome": "业务侧误判为再次故障", "outcome_q": "被当成了新故障上报"},
    {"action": "迁移时开了无条件覆盖", "active": "", "action_q": "搬数据时不做新旧区分",
     "outcome": "增量数据被旧值盖掉", "outcome_q": "新写的数被冲掉了"},
    {"action": "回灌中途改了字段映射", "action_q": "搬一半换了对应关系",
     "outcome": "半张表键值错位", "outcome_q": "一半记录对错了行"},
    {"action": "审批加急跳过了复核", "action_q": "赶时间少了一道把关",
     "outcome": "错误授权直接生效", "outcome_q": "错的权限当场发了出去"},
    {"action": "授权范围整包勾选", "action_q": "没细看就全选了",
     "outcome": "越权写入了配置", "outcome_q": "不该动的也被改了"},
]

# R4 主线（抽象结论，与细节措辞刻意不同）；细节由场景模板拼装
R4_LINES: List[str] = [
    "三次返工都卡在同一步：变更前没有双人复核",
    "回看这几回，问题都出在没给下游留缓冲时间",
    "几件事共同点：做完没有回读校验就报完成",
    "几次出岔子都栽在同一件事：交接时没人复核",
    "主线很清楚：所有事故都始于跳过了演练",
    "这几回的通病：信息发了但没确认对方收到",
    "共同根源：配置改了却没同步改文档",
    "每次出事前都有同一件事没做：留了档但没验过",
    "根子上是同一件事：先上线后补记录",
    "三回都一样：把临时方案当成了正式方案",
    "验证这一步永远被挤掉",
    "根子上的共性：容量预估没算上下游联动",
    "这几回的共同点：口径改了没做回归对照",
    "都是同一个弱点：出问题时找不到当时的参数快照",
    "一条线贯下来：审批通过后没人追踪落地",
    "共同教训：每一步完成的定义里都缺了验证",
]
R4_DETAILS: List[str] = [
    "把重试从 0 次调到 2 次", "灰度比例从 5% 提到 15%",
    "分批大小从 1000 行改成 500 行", "观察窗口从 5 分钟拉到 15 分钟",
    "把超时从 1 秒放到 3 秒", "连接池上限从 50 提到 200",
    "回滚点改成了前一晚的快照", "告警接收人换成了当班组",
    "统计周期按自然周重算", "校验方式换成抽样比对",
    "授权范围收窄到只读", "有效期从 30 天改到 7 天",
    "日志目录迁到了大盘", "脚本路径改成项目内目录",
    "签名方式换成 HMAC", "切换时点挪到凌晨三点",
]

# R5 属性池：attr_a=已记（正文出现）；attr_b=未记（全语料 0 出现，铁律断言）
R5_ATTRS: List[Dict[str, str]] = [
    {"a": "熔断阈值", "b": "冷启动超时"},
    {"a": "重试上限", "b": "热备延迟秒数"},
    {"a": "放量档位", "b": "兜底备用号"},
    {"a": "告警接收人", "b": "备机序列号"},
    {"a": "统计周期", "b": "审批单流水号"},
    {"a": "扩容上限", "b": "机房温控阈值"},
    {"a": "分批大小", "b": "回灌校验和"},
    {"a": "授权范围", "b": "工单归档号"},
    {"a": "健康检查路径", "b": "探针备用端口"},
    {"a": "签名方式", "b": "备用根证书号"},
    {"a": "观察窗口", "b": "静默期起始点"},
    {"a": "日志目录", "b": "磁带归档编号"},
    {"a": "生效时间", "b": "纪要传阅回执号"},
    {"a": "回滚点", "b": "演练快照编号"},
    {"a": "超时时间", "b": "对端联系人座机"},
    {"a": "校验方式", "b": "冻结单编号"},
]

# R6 三来源的三值由场景 values 池取（每场景恰 3 个），口语转述句式固定
R6_RETELL_PREFIX = ["听同事说", "群里有人讲", "交接时提过一嘴"]
R6_DOC_PREFIX = ["交接文档里写着", "知识库里记着", "归档纪要里写着"]


def _mark(sc: Dict[str, Any]) -> str:
    return sc["mark"][0]


def _flat(text: str) -> str:
    """去空白与场景标志词后的文本（R1/R4 泄漏断言用）。"""
    t = re.sub(r"\s+", "", text)
    for m in scn.BANNED_TOPICS:
        t = t.replace(m, "")
    for key in scn.SCENARIO_KEYS:
        for w in scn.SCENARIOS[key]["mark"]:
            t = t.replace(w, "")
    return t


def _has_run(text: str, n: int = 3) -> bool:
    """去空白后是否存在任意 ≥n 字连续子串。"""
    return len(text) >= n


def _overlap(a: str, b: str, n: int = 3) -> bool:
    """a、b 去空白后是否存在 ≥n 字公共连续子串（防题面复述正文）。"""
    a, b = _flat(a), _flat(b)
    for i in range(len(a) - n + 1):
        if a[i:i + n] in b:
            return True
    return False


# ---------------------------------------------------------------- R1 因果归因→处方

def build_r1(rng: random.Random, alloc: scn.Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """一题 = 因果记录节点（bad→failure，附处方）+ 同场景另一条因果记录作干扰。

    题面给**改述后的新情境**（bad_q），只问「该怎么办」——
    不复述 failure/prescription 原文，测处方召回而非字面复现。
    """
    sc = scn.SCENARIOS[scenario]
    comp = sc["components"][idx % len(sc["components"])]
    env = sc["envs"][idx % len(sc["envs"])]
    mark = _mark(sc)
    g = R1_CAUSES[idx % len(R1_CAUSES)]
    d = R1_CAUSES[(idx + 5) % len(R1_CAUSES)]
    comp2 = sc["components"][(idx + 1) % len(sc["components"])]
    env2 = sc["envs"][(idx + 1) % len(sc["envs"])]
    topic = f"r1-{scenario}-{idx}"

    gold = scn.node(
        scenario, alloc.node_id(scenario),
        f"{comp}{mark}踩坑记录：{g['bad'][:10]}",
        scn.tpl(f"{env} 的 {comp} 这次{mark}踩了坑：{g['bad']}",
                f"结果{g['failure']}",
                f"后来定下规矩：{g['prescription']}"),
        ts=f"2026-05-{(idx % 27) + 1:02d}",
        created_at=f"2026-05-{(idx % 27) + 1:02d}T08:00:00Z",
        insert_rank=2000 + idx * 10,
        role="rx_cause", topic=topic,
        attrs={"is_gold": True, "bad": g["bad"], "prescription": g["prescription"]},
    )
    decoy = scn.node(
        scenario, alloc.node_id(scenario),
        f"{comp2}{mark}另一次踩坑：{d['bad'][:10]}",
        scn.tpl(f"{env2} 的 {comp2} 有一次{mark}也踩了坑：{d['bad']}",
                f"结果{d['failure']}",
                f"当时的规矩是：{d['prescription']}"),
        ts=f"2026-02-{(idx % 27) + 1:02d}",
        created_at=f"2026-02-{(idx % 27) + 1:02d}T08:00:00Z",
        insert_rank=2000 + idx * 10 + 1,
        role="rx_cause", topic=topic,
        attrs={"is_gold": False, "bad": d["bad"], "prescription": d["prescription"]},
    )
    question = {
        "type": "R1", "scenario": scenario, "subtype": "prescription",
        "query": (f"{env2}的 {comp2} 这次{mark}又出现「{g['bad_q']}」的苗头，"
                  f"按当初那次踩坑定下的规矩该怎么办？"),
        "gold_expr": {"kind": "rx_prescription", "gold": gold["id"], "decoy": decoy["id"],
                      "topic": topic, "prescription": g["prescription"]},
        "expect": [gold["id"]],
        "note": "同因泛化：题面用改述 bad_q 指涉，处方只在 gold 正文；"
                "题面不得复述 failure/prescription 原文",
    }
    return [gold, decoy], [question]


# ---------------------------------------------------------------- R2 反事实

def build_r2(rng: random.Random, alloc: scn.Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """一题 = 事件节点（action→outcome 强绑定）+ 同场景另一事件作干扰。

    反事实题「当初不 X 还会 Y 吗」的正确答案由构造绑定机械给出：
    gold=记录该绑定的事件条目（召回它才答得出 X 与 Y 的绑定关系）。
    """
    sc = scn.SCENARIOS[scenario]
    comp = sc["components"][idx % len(sc["components"])]
    env = sc["envs"][idx % len(sc["envs"])]
    mark = _mark(sc)
    e = R2_EVENTS[idx % len(R2_EVENTS)]
    f = R2_EVENTS[(idx + 7) % len(R2_EVENTS)]
    topic = f"r2-{scenario}-{idx}"

    gold = scn.node(
        scenario, alloc.node_id(scenario),
        f"{comp}{mark}事件：{e['action'][:10]}",
        scn.tpl(f"{env} 的 {comp} 那次{mark}",
                f"做了 {e['action']}",
                f"结果{e['outcome']}"),
        ts=f"2026-04-{(idx % 27) + 1:02d}",
        created_at=f"2026-04-{(idx % 27) + 1:02d}T08:00:00Z",
        insert_rank=3000 + idx * 10,
        role="rx_event", topic=topic,
        attrs={"is_gold": True, "action": e["action"], "outcome": e["outcome"]},
    )
    decoy = scn.node(
        scenario, alloc.node_id(scenario),
        f"{comp2(comp, sc, idx)}{mark}另一次：{f['action'][:10]}",
        scn.tpl(f"{sc['envs'][(idx + 1) % len(sc['envs'])]} 的 {comp2(comp, sc, idx)} 另一次{mark}",
                f"做了 {f['action']}",
                f"结果{f['outcome']}"),
        ts=f"2026-01-{(idx % 27) + 1:02d}",
        created_at=f"2026-01-{(idx % 27) + 1:02d}T08:00:00Z",
        insert_rank=3000 + idx * 10 + 1,
        role="rx_event", topic=topic,
        attrs={"is_gold": False, "action": f["action"], "outcome": f["outcome"]},
    )
    question = {
        "type": "R2", "scenario": scenario, "subtype": "counterfactual",
        "query": (f"当初 {env} 的 {comp} 那回{mark}如果没做「{e['action_q']}」，"
                  f"还会「{e['outcome_q']}」吗？"),
        "gold_expr": {"kind": "rx_counterfactual", "gold": gold["id"], "decoy": decoy["id"],
                      "topic": topic, "action": e["action"], "outcome": e["outcome"]},
        "expect": [gold["id"]],
        "note": "反事实绑定由构造机械给：gold=记录 action→outcome 绑定的事件条目；"
                "题面用改述 action_q/outcome_q，不复述事件正文",
    }
    return [gold, decoy], [question]


def comp2(comp: str, sc: Dict[str, Any], idx: int) -> str:
    return sc["components"][(sc["components"].index(comp) + 1) % len(sc["components"])]


# ---------------------------------------------------------------- R3 动态更新

def build_r3(rng: random.Random, alloc: scn.Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """一题 = 旧值条目（stale）+ 新值条目（fresh）：同 topic 同参数、值不同。

    题面问「现在是多少」——gold=fresh（晚 created、带「以此为准」信号）；
    score 侧量化 stale_crown_rate（头榜落旧值条目的比例）。
    """
    sc = scn.SCENARIOS[scenario]
    comp = sc["components"][idx % len(sc["components"])]
    env = sc["envs"][idx % len(sc["envs"])]
    mark = _mark(sc)
    param = sc["params"][idx % len(sc["params"])]
    vals = sc["values"]
    v_old = vals[idx % len(vals)]
    v_new = vals[(idx + 1) % len(vals)]
    if v_new == v_old:
        v_new = vals[(idx + 2) % len(vals)]
    topic = f"r3-{scenario}-{idx}"

    stale = scn.node(
        scenario, alloc.node_id(scenario),
        f"{comp}{mark}{param}旧记：{v_old}",
        scn.tpl(f"{env} 的 {comp} 那次{mark}",
                f"当时 {param} 记的是 {v_old}",
                f"那条记录停在三月，后来被更新过"),
        ts="2026-03-05",
        created_at="2026-03-05T08:00:00Z",
        insert_rank=4000 + idx * 10,
        role="stale", topic=topic,
        attrs={"is_gold": False, "param": param, "value": v_old},
    )
    fresh = scn.node(
        scenario, alloc.node_id(scenario),
        f"{comp}{mark}{param}新记：{v_new}",
        scn.tpl(f"{env} 的 {comp} 这次{mark}后",
                f"{param} 后来更新为 {v_new}",
                f"九月的记录写明以此为准"),
        ts="2026-09-20",
        created_at="2026-09-20T08:00:00Z",
        insert_rank=4000 + idx * 10 + 1,
        role="fresh", topic=topic,
        attrs={"is_gold": True, "param": param, "value": v_new},
    )
    question = {
        "type": "R3", "scenario": scenario, "subtype": "fresh_value",
        "query": f"{env}的 {comp} 这次{mark}后，{param} 现在是多少？",
        "gold_expr": {"kind": "rx_fresh", "gold": fresh["id"], "other": stale["id"],
                      "topic": topic, "param": param,
                      "new_value": v_new, "old_value": v_old},
        "expect": [fresh["id"]],
        "note": "gold=新值条目（晚 created、带「以此为准」）；top1=other 即旧条目霸榜",
    }
    return [stale, fresh], [question]


# ---------------------------------------------------------------- R4 原缩摘要

def build_r4(rng: random.Random, alloc: scn.Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """一题 = 4 节点：1 条主线 + 3 条细节（同 topic）。题面问主线，不复述主线原文。"""
    sc = scn.SCENARIOS[scenario]
    comp = sc["components"][idx % len(sc["components"])]
    env = sc["envs"][idx % len(sc["envs"])]
    mark = _mark(sc)
    line = R4_LINES[idx % len(R4_LINES)]
    topic = f"r4-{scenario}-{idx}"

    nodes: List[Dict[str, Any]] = []
    mainline = scn.node(
        scenario, alloc.node_id(scenario),
        f"{comp}{mark}主线复盘",
        scn.tpl(f"把 {env} 的 {comp} 这几次{mark}放在一起看",
                f"主线是：{line}",
                f"细节各不相同，但根子压在同一步上"),
        ts=f"2026-06-{(idx % 27) + 1:02d}",
        created_at=f"2026-06-{(idx % 27) + 1:02d}T08:00:00Z",
        insert_rank=6000 + idx * 10,
        role="rx_mainline", topic=topic,
        attrs={"is_gold": True, "line": line},
    )
    nodes.append(mainline)
    for j in range(3):
        det = R4_DETAILS[(idx * 3 + j) % len(R4_DETAILS)]
        day = (idx * 3 + j) % 27 + 1
        nodes.append(scn.node(
            scenario, alloc.node_id(scenario),
            f"{comp}{mark}细节第{j + 1}记：{det[:8]}",
            scn.tpl(f"2026-0{(idx % 6) + 1}-{day:02d} {env} 的 {comp} 单独一次{mark}",
                    f"那回具体动了：{det}",
                    f"只记了这一处，没提别的"),
            ts=f"2026-0{(idx % 6) + 1}-{day:02d}",
            created_at=f"2026-0{(idx % 6) + 1}-{day:02d}T09:00:00Z",
            insert_rank=6000 + idx * 10 + j + 1,
            role="rx_detail", topic=topic,
            attrs={"is_gold": False, "detail": det},
        ))
    question = {
        "type": "R4", "scenario": scenario, "subtype": "gist_line",
        "query": (f"把 {env}的 {comp} 这几次{mark}串起来看，反复出现的主线是什么？"),
        "gold_expr": {"kind": "rx_line", "gold": mainline["id"],
                      "decoys": [n["id"] for n in nodes[1:]],
                      "topic": topic, "line": line},
        "expect": [mainline["id"]],
        "note": "跨多条抽主线：题面不复述主线原文（断言拦截），三条细节抢字面",
    }
    return nodes, [question]


# ---------------------------------------------------------------- R5 元认知

def build_r5(rng: random.Random, alloc: scn.Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """每构造 2 题（已记探针 + importance 判定），3 节点：已记结论、重要判例、次要判例。

    (a) 探针：已记型 gold=结论条目；未记型 gold=空（attr_b 全语料 0 出现，铁律断言）。
        search-only：探针只查询、不写库——真库口径在 collect 侧保证，本层不涉及写。
    (b) importance：按既定规矩召回对应判例（该存→重要判例 / 该扔→次要判例）。
    """
    sc = scn.SCENARIOS[scenario]
    comp = sc["components"][idx % len(sc["components"])]
    env = sc["envs"][idx % len(sc["envs"])]
    mark = _mark(sc)
    pair = R5_ATTRS[idx % len(R5_ATTRS)]
    attr_a, attr_b = pair["a"], pair["b"]
    value = sc["values"][idx % len(sc["values"])]
    topic = f"r5-{scenario}-{idx}"

    recorded = scn.node(
        scenario, alloc.node_id(scenario),
        f"{comp}{mark}结论：{attr_a}定为{value}",
        scn.tpl(f"{env} 的 {comp} 那次{mark}",
                f"复核后记下：{attr_a} 定为 {value}",
                f"这条结论下次可直接引用"),
        ts=f"2026-07-{(idx % 27) + 1:02d}",
        created_at=f"2026-07-{(idx % 27) + 1:02d}T08:00:00Z",
        insert_rank=7000 + idx * 10,
        role="rx_recorded", topic=topic,
        attrs={"is_gold": True, "attr_a": attr_a, "attr_b": attr_b, "value": value},
    )
    imp = scn.node(
        scenario, alloc.node_id(scenario),
        f"{comp}{mark}归档规矩：能复用的记为重要",
        scn.tpl(f"{env} 的 {comp} 记忆归档时定过一条规矩",
                "能复用到下一次的结论要单独标为重要，反复查证",
                "这类条目按重要保存，检索时优先回"),
        ts=f"2026-07-{(idx % 27) + 2:02d}",
        created_at=f"2026-07-{(idx % 27) + 2:02d}T08:00:00Z",
        insert_rank=7000 + idx * 10 + 1,
        role="rx_rule", topic=topic,
        attrs={"is_gold": False, "grade": "important"},
    )
    tri = scn.node(
        scenario, alloc.node_id(scenario),
        f"{comp}{mark}归档规矩：一次性的走流水",
        scn.tpl(f"同一次归档还定过另一条规矩",
                "一次性跑完就过的流水只做流水记录，不进重点",
                "这类条目按次要保存，过期可清"),
        ts=f"2026-07-{(idx % 27) + 3:02d}",
        created_at=f"2026-07-{(idx % 27) + 3:02d}T08:00:00Z",
        insert_rank=7000 + idx * 10 + 2,
        role="rx_rule", topic=topic,
        attrs={"is_gold": False, "grade": "trivial"},
    )

    # 探针题：奇数 idx 问未记属性（gold 空），偶数问已记属性
    if idx % 2 == 0:
        probe = {
            "type": "R5", "scenario": scenario, "subtype": "probe_recorded",
            "query": f"{env}的 {comp} 那次{mark}，{attr_a} 的结论记了吗？",
            "gold_expr": {"kind": "rx_probe", "phase": "recorded",
                          "gold": recorded["id"], "topic": topic, "attr": attr_a},
            "expect": [recorded["id"]],
            "note": "已记探针：gold=结论条目（search-only 查询，不写库）",
        }
    else:
        probe = {
            "type": "R5", "scenario": scenario, "subtype": "probe_unrecorded",
            "query": f"{env}的 {comp} 那次{mark}，{attr_b} 记了吗？",
            "gold_expr": {"kind": "rx_probe", "phase": "unrecorded",
                          "gold": "", "topic": topic, "attr": attr_b,
                          "recorded_decoy": recorded["id"]},
            "expect": [],
            "note": "未记探针：gold=空；正确行为=不硬凑（attr_b 全语料 0 出现）",
        }
    # importance 判定题：奇数 idx 问「该扔」（次要判例），偶数问「该存」（重要判例）
    if idx % 2 == 0:
        imp_q = {
            "type": "R5", "scenario": scenario, "subtype": "importance_keep",
            "query": (f"{env}的 {comp} 这类{mark}经验：以后遇到同类情况能直接照着做的结论，"
                      f"按归档规矩该当重点吗？"),
            "gold_expr": {"kind": "rx_importance", "grade": "important",
                          "gold": imp["id"], "decoy": tri["id"], "topic": topic},
            "expect": [imp["id"]],
            "note": "该存→重要判例（题面换措辞，不整句复述判例正文）",
        }
    else:
        imp_q = {
            "type": "R5", "scenario": scenario, "subtype": "importance_discard",
            "query": (f"{env}的 {comp} 这类{mark}记录：一次性跑完就过的流水，"
                      f"按归档规矩该随流水走吗？"),
            "gold_expr": {"kind": "rx_importance", "grade": "trivial",
                          "gold": tri["id"], "decoy": imp["id"], "topic": topic},
            "expect": [tri["id"]],
            "note": "该扔→次要判例（同上）",
        }
    return [recorded, imp, tri], [probe, imp_q]


# ---------------------------------------------------------------- R6 跨来源置信

def build_r6(rng: random.Random, alloc: scn.Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """一题 = 三来源节点（实测/转述/文档），同 topic 同参数、值不同；gold=实测。

    转述正文口语化（与自然问句最同词）——字面检索天然偏向它，
    复现并量化 H4 T6 的「转述霸榜」（tests/34：86.4%）。
    """
    sc = scn.SCENARIOS[scenario]
    comp = sc["components"][idx % len(sc["components"])]
    env = sc["envs"][idx % len(sc["envs"])]
    mark = _mark(sc)
    param = sc["params"][idx % len(sc["params"])]
    vals = sc["values"]
    v_m = vals[idx % len(vals)]
    v_r = vals[(idx + 1) % len(vals)]
    v_d = vals[(idx + 2) % len(vals)]
    if len(set([v_m, v_r, v_d])) < 3:  # 值池不足 3 时兜底（当前八场景均 ≥3）
        pool = [x for x in vals if x != v_m]
        v_r, v_d = pool[0], pool[1]
    topic = f"r6-{scenario}-{idx}"
    retell_p = R6_RETELL_PREFIX[idx % len(R6_RETELL_PREFIX)]
    doc_p = R6_DOC_PREFIX[idx % len(R6_DOC_PREFIX)]

    measured = scn.node(
        scenario, alloc.node_id(scenario),
        f"{comp}{mark}实测：{param}={v_m}",
        scn.tpl(f"{env} 的 {comp} 这次{mark}",
                f"我实测 {param} 是 {v_m}，复核过两遍",
                f"以这次实测为准"),
        ts=f"2026-08-{(idx % 27) + 1:02d}",
        created_at=f"2026-08-{(idx % 27) + 1:02d}T08:00:00Z",
        insert_rank=8000 + idx * 10,
        role="rx_measured", topic=topic,
        attrs={"is_gold": True, "grade": "measured", "param": param, "value": v_m},
    )
    retell = scn.node(
        scenario, alloc.node_id(scenario),
        f"{comp}{mark}转述：{param}={v_r}",
        scn.tpl(f"关于 {env} 的 {comp} 的{mark}",
                f"同事说「{param} 用 {v_r} 应该没事」，我没细问",
                f"说法是从别处听来的"),
        ts=f"2026-08-{(idx % 27) + 2:02d}",
        created_at=f"2026-08-{(idx % 27) + 2:02d}T08:00:00Z",
        insert_rank=8000 + idx * 10 + 1,
        role="rx_retell", topic=topic,
        attrs={"is_gold": False, "grade": "retell", "param": param, "value": v_r},
    )
    doc = scn.node(
        scenario, alloc.node_id(scenario),
        f"{comp}{mark}文档：{param}={v_d}",
        scn.tpl(f"关于 {comp} 的{mark}归档",
                f"{doc_p} {comp} 的 {param} 是 {v_d}",
                f"文档没标最后复核时间"),
        ts=f"2026-08-{(idx % 27) + 3:02d}",
        created_at=f"2026-08-{(idx % 27) + 3:02d}T08:00:00Z",
        insert_rank=8000 + idx * 10 + 2,
        role="rx_doc", topic=topic,
        attrs={"is_gold": False, "grade": "doc", "param": param, "value": v_d},
    )
    question = {
        "type": "R6", "scenario": scenario, "subtype": "evidence_first",
        "query": (f"{env}的 {comp} 这次{mark}前，同事说「{param} 用 {v_r} 应该没事」，"
                  f"但我们这边实测过。以哪个为准？"),
        "gold_expr": {"kind": "rx_evidence", "gold": measured["id"],
                      "retell": retell["id"], "doc": doc["id"],
                      "topic": topic, "param": param},
        "expect": [measured["id"]],
        "note": "gold=实测；题面内嵌转述原句（对齐 H4 T6 口径）→ 字面检索偏向转述，"
                "top1=retell 即转述霸榜（复现 T6 86.4%）",
    }
    return [measured, retell, doc], [question]


# ---------------------------------------------------------------- 组装与守门

def build(seed: int, per_type: int) -> Dict[str, Any]:
    rng = random.Random(seed)
    alloc = scn.Alloc()
    nodes: List[Dict[str, Any]] = []
    questions: List[Dict[str, Any]] = []
    builders = {
        "R1": (build_r1, 1), "R2": (build_r2, 1), "R3": (build_r3, 1),
        "R4": (build_r4, 1), "R5": (build_r5, 2), "R6": (build_r6, 1),
    }
    for typ, (fn, fanout) in builders.items():
        builds_n = per_type // fanout
        for i in range(builds_n):
            scenario = scn.SCENARIO_KEYS[(i + 1) % len(scn.SCENARIO_KEYS)]
            ns, qs = fn(rng, alloc, scenario, i)
            nodes.extend(ns)
            for q in qs:
                q["qid"] = f"{typ.lower()}-{i * fanout + (qs.index(q)) + 1:03d}"
                questions.append(q)
    questions.sort(key=lambda q: q["qid"])
    doc = {"seed": seed, "scenarios": scn.SCENARIO_KEYS,
           "tree": {"nodes": nodes},
           "questions": questions}
    # 题号重排为类内连续序号（qid 已按类前缀，只需校正类内顺序）
    return doc


def sanity_checks(doc: Dict[str, Any], per_type: int) -> None:
    nodes = doc["tree"]["nodes"]
    questions = doc["questions"]
    node_by_id = {n["id"]: n for n in nodes}
    errors: List[str] = []

    # 1) 铁律三道断言
    for q in questions:
        sc = scn.SCENARIOS.get(q["scenario"])
        if sc is None:
            errors.append(f"{q['qid']}: 非法场景 {q['scenario']}")
            continue
        if not any(m in q["query"] for m in sc["mark"]):
            errors.append(f"{q['qid']}: 题面缺场景标志词")
        for b in scn.BANNED_TOPICS:
            if b in q["query"]:
                errors.append(f"{q['qid']}: 题面命中禁题材词 {b}")

    # 2) 题量
    counts: Dict[str, int] = {}
    for q in questions:
        counts[q["type"]] = counts.get(q["type"], 0) + 1
    for typ in hg.TYPES:
        if counts.get(typ, 0) != per_type:
            errors.append(f"{typ}: 题量 {counts.get(typ, 0)} ≠ {per_type}")
    if len(questions) != per_type * len(hg.TYPES):
        errors.append(f"总题量 {len(questions)} ≠ {per_type * len(hg.TYPES)}")

    # 3) R1/R4 题面不得复述正文核心句（测处方/主线召回，非字面复现）
    for q in questions:
        if q["type"] == "R1":
            node = node_by_id[q["gold_expr"]["gold"]]
            content = node["content"]
            beh_con = content.split("【行为】")[-1] if "【行为】" in content else ""
            con = content.split("【后果】")[-1] if "【后果】" in content else ""
            if _overlap(q["query"], beh_con + con, 3):
                errors.append(f"{q['qid']}: R1 题面复述了失败句/处方句")
        if q["type"] == "R4":
            node = node_by_id[q["gold_expr"]["gold"]]
            line_part = node["attrs"].get("line", "")
            if _overlap(q["query"], line_part, 3):
                errors.append(f"{q['qid']}: R4 题面复述了主线原文")

    # 4) R5 未记属性「确未写入」：attr_b 在全部节点 title+content 里 0 次出现
    corpus = "\n".join(n["title"] + n["content"] for n in nodes)
    for q in questions:
        if q["type"] == "R5" and q["gold_expr"].get("phase") == "unrecorded":
            attr_b = q["gold_expr"]["attr"]
            if attr_b in corpus:
                errors.append(f"{q['qid']}: 未记属性 {attr_b} 竟出现在语料里")

    # 5) R3 新旧时序与 R6 三来源齐备
    for q in questions:
        if q["type"] == "R3":
            fresh = node_by_id[q["gold_expr"]["gold"]]
            stale = node_by_id[q["gold_expr"]["other"]]
            if fresh["created_at"] <= stale["created_at"]:
                errors.append(f"{q['qid']}: fresh created_at 未晚于 stale")
        if q["type"] == "R6":
            e = q["gold_expr"]
            if e["retell"] == e["gold"] or e["doc"] == e["gold"] or e["retell"] == e["doc"]:
                errors.append(f"{q['qid']}: R6 三来源节点不互异")

    # 6) 脱敏自检
    for q in questions:
        for b in BANNED_SNIPPETS:
            if b in q["query"]:
                errors.append(f"{q['qid']}: 题面命中敏感片段")
        if UUID_RE.search(q["query"]):
            errors.append(f"{q['qid']}: 题面含 UUID")
    for n in nodes:
        for b in BANNED_SNIPPETS:
            if b in n["title"] + n["content"]:
                errors.append(f"{n['id']}: 节点命中敏感片段")
        if UUID_RE.search(n["title"] + n["content"]):
            errors.append(f"{n['id']}: 节点含 UUID")

    # 7) id 唯一
    ids = [n["id"] for n in nodes]
    if len(ids) != len(set(ids)):
        errors.append("节点 id 重复")
    qids = [q["qid"] for q in questions]
    if len(qids) != len(set(qids)):
        errors.append("qid 重复")

    if errors:
        for e in errors:
            print(f"[gen_h9][sanity] {e}", file=sys.stderr)
        sys.exit(1)


def digest(doc: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(doc, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def dump(doc: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(TREE_OUT), exist_ok=True)
    os.makedirs(os.path.dirname(EVALSET_OUT), exist_ok=True)
    with open(TREE_OUT, "w", encoding="utf-8") as f:
        json.dump(doc["tree"], f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(EVALSET_OUT, "w", encoding="utf-8") as f:
        for q in doc["questions"]:
            f.write(json.dumps(q, ensure_ascii=False, sort_keys=True) + "\n")


def verify_existing(seed: int, per_type: int) -> int:
    doc = build(seed, per_type)
    sanity_checks(doc, per_type)
    try:
        old_tree = json.load(open(TREE_OUT, encoding="utf-8"))
        old_q = [json.loads(x) for x in open(EVALSET_OUT, encoding="utf-8") if x.strip()]
    except FileNotFoundError:
        print("[gen_h9] verify FAIL：既有文件不存在", file=sys.stderr)
        return 1
    ok = old_tree == doc["tree"] and old_q == doc["questions"]
    if not ok:
        print("[gen_h9] verify FAIL：重生成与既有文件不一致", file=sys.stderr)
        return 1
    print(f"[gen_h9] verify OK：{len(doc['tree']['nodes'])} 节点 / "
          f"{len(doc['questions'])} 题 / digest={digest(doc)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--per-type", type=int, default=PER_TYPE)
    ap.add_argument("--verify", action="store_true", help="重生成与既有文件比对")
    args = ap.parse_args()

    if args.verify:
        return verify_existing(args.seed, args.per_type)

    doc = build(args.seed, args.per_type)
    sanity_checks(doc, args.per_type)
    dump(doc)
    counts: Dict[str, int] = {}
    for q in doc["questions"]:
        counts[q["type"]] = counts.get(q["type"], 0) + 1
    print(f"[gen_h9] 写出 data/h9_tree.json: {len(doc['tree']['nodes'])} 节点")
    print(f"[gen_h9] 写出 dataset/h9_evalset.jsonl: {len(doc['questions'])} 题 "
          f"(seed={args.seed}, digest={digest(doc)})")
    for t in hg.TYPES:
        print(f"  - {t}: {counts.get(t, 0)}")
    print("[gen_h9] 铁律守门通过；R1/R4 无题面复述；R5 未记属性 0 出现；R3/R6 结构断言通过；脱敏自检通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())

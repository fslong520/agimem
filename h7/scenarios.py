#!/usr/bin/env python3
"""scenarios.py — H7「跨跳与诚实层」的场景白名单与词库。

铁律（记忆 cdf155a9）：每题必须落在**真实工作场景**里。本文件用场景白名单守住：
只有 SCENARIOS 里登记的八个场景（部署上线/灰度发布/接口对接/同事交接/开会定口径/
线上排障/数据迁移/权限审批）可以出题；禁用科幻、纯数学、纯图案、纯抽象题材。
`gen_h7.py` 生成后强制断言三件事：scenario ∈ 白名单、题面含该场景标志词、不含禁题材词。

与 H6（`agimem/humanlike2/`）的关系：场景白名单刻意沿用同一套八场景，使 H6/H7 两层数字在
**同一题材约束**下可比；但题目形态、gold 与判分完全不同（见 `tests/40-crosshop-honest.md`）。
H7 测四件事：L1 多跳链传递、L2 混跳辨析、L3 缺证据拒答（三档诱饵）、L4 增广认出同事实。
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Tuple

SCENARIO_KEYS = ["deploy", "canary", "api", "handoff", "meeting", "ops", "migration", "approval"]

SCENARIOS: Dict[str, Dict[str, Any]] = {
    "deploy": {
        "name": "部署上线",
        "mark": ["上线", "发布单", "部署"],
        "components": ["订单服务", "结算服务", "网关服务", "会员服务"],
        "envs": ["预发", "生产"],
        "params": ["启动参数", "健康检查路径", "实例规格", "镜像版本"],
        "values": ["max-conn=200", "/healthz", "4 核 8G", "v2.3.1"],
    },
    "canary": {
        "name": "灰度发布",
        "mark": ["灰度", "放量", "回滚"],
        "components": ["推荐服务", "搜索服务", "风控服务"],
        "envs": ["灰度组", "全量组"],
        "params": ["灰度比例", "观察窗口", "放量档位"],
        "values": ["10%", "15 分钟", "10→30→100"],
    },
    "api": {
        "name": "接口对接",
        "mark": ["接口", "对接", "联调"],
        "components": ["对账接口", "回调接口", "查询接口"],
        "envs": ["沙箱", "正式"],
        "params": ["超时", "重试次数", "签名方式"],
        "values": ["3 秒", "2 次", "HMAC-SHA256"],
    },
    "handoff": {
        "name": "同事交接",
        "mark": ["交接", "接手", "离职"],
        "components": ["值班手册", "定时任务", "监控看板"],
        "envs": ["本机", "跳板机"],
        "params": ["脚本路径", "告警接收人", "日志目录"],
        "values": ["/opt/ops/run.sh", "当班组", "/var/log/app"],
    },
    "meeting": {
        "name": "开会定口径",
        "mark": ["会议", "口径", "纪要"],
        "components": ["指标口径", "统计规范", "命名规范"],
        "envs": ["周会", "评审会"],
        "params": ["统计周期", "口径定义", "生效时间"],
        "values": ["自然周", "按下单时间", "下个迭代"],
    },
    "ops": {
        "name": "线上排障",
        "mark": ["故障", "排障", "告警"],
        "components": ["支付回调", "消息队列", "数据库主库"],
        "envs": ["线上", "演练环境"],
        "params": ["熔断阈值", "扩容策略", "回滚点"],
        "values": ["连续 5 次", "先加两副本", "上一个稳定版本"],
    },
    "migration": {
        "name": "数据迁移",
        "mark": ["迁移", "割接", "回灌"],
        "components": ["历史订单表", "用户档案", "日志索引"],
        "envs": ["迁移库", "生产库"],
        "params": ["分批大小", "校验方式", "切换时点"],
        "values": ["5000 行", "抽样比对", "凌晨 3 点"],
    },
    "approval": {
        "name": "权限审批",
        "mark": ["审批", "权限", "工单"],
        "components": ["生产库账号", "发布平台", "配置中心"],
        "envs": ["测试租户", "生产租户"],
        "params": ["审批人", "有效期", "授权范围"],
        "values": ["组长加 DBA", "7 天", "只读"],
    },
}

# 被禁题材词（铁律守门：出现即判失败）
BANNED_TOPICS = ["科幻", "外星", "量子纠缠", "纯数学", "拓扑空间", "抽象代数", "积分公式",
                 "概率分布题", "图案打印", "矩阵乘法", "图灵机", "希尔伯特", "莫比乌斯环",
                 "魔法", "超能力", "穿越"]

# ── L1/L2 多跳链：每跳是一个「排障/交接/发布」事件节点，链深 1/2/3/4 分层 ──
# 每条链 4 个环节（A→B→C→D），题面问从链尾回溯到链头的第几跳，
# gold 由 parent_id 链机械推导（复用 H2 attach 建边的判分口径：链深分层报 hit@1/5）。
CHAIN_LINK_VERBS = ["引出", "暴露", "触发", "传导至", "追到", "定位到"]

# ── L2 混跳辨析：同题面但链长不同（N 跳 vs M 跳），判辨析率 ──
# 题面刻意模糊（「这一步之后牵出几层」），gold 给出准确跳数，测能否辨清是 2 跳还是 3 跳。

# ── L3 缺证据拒答：三档诱饵（谱内已问 / 谱内未写 / 谱外）──
# 三档由同一题面结构生成，gold 分别为「有答案 / abstain / abstain」，
# 测 abstain precision/recall 与 closed_ended F1 双侧。
# 词库：谱内已写属性 vs 从没写过的属性（诱饵）vs 完全不在本场景谱内的属性。
IN_SPECTRUM_ATTRS = ["回滚点", "告警阈值", "生效时点", "审批人"]     # 谱内已写
NEVER_WRITTEN_ATTRS = ["灰度白名单 ID", "熔断窗口秒数", "审计保留天数", "配额流水号"]  # 谱内未写（诱饵）
OFF_SPECTRUM_ATTRS = ["球衣号码", "星座运势", "菜谱火候", "诗词韵脚"]  # 谱外（彻底无关，诱饵）

# L4 增广认同的事实要素：必须是**真写进语料**的词（与 L3 的 NEVER_WRITTEN_ATTRS 分开，
# 否则 L4 正文会把 L3 的「谱内未写」诱饵词写实，撞掉诚实层断言）。
AUG_REAL_ATTRS = ["回滚点", "告警阈值", "生效时点", "审批人", "熔断阈值", "灰度比例"]

# ── L4 增广认同事实：同事实的改写/换语/句序变体，测 golden 池 hit ──
# 每条事实配 3 个增广变体：改写（换同义词）、换语（换说法不换意）、句序（倒装）。
# 红线：必须**故意词面错位**，否则测成字面检索（H6 v3「满分反而没测到分水岭」的教训）。
L4_AUG_KINDS = ["rewrite", "rephrase", "reorder"]

H7_PREFIX = "h7"


def scenario_letter(key: str) -> str:
    return "ABCDEFGH"[SCENARIO_KEYS.index(key)]


class Alloc:
    """确定性 id 分配：h7{场景字母}{4 位序号}。"""

    def __init__(self) -> None:
        self.n: Dict[str, int] = {k: 0 for k in SCENARIO_KEYS}

    def node_id(self, scenario: str) -> str:
        self.n[scenario] += 1
        return f"{H7_PREFIX}{scenario_letter(scenario)}{self.n[scenario]:04d}"


def pick(rng: random.Random, seq: List[Any]) -> Any:
    return seq[rng.randrange(len(seq))]


def node(scenario: str, nid: str, title: str, content: str, *, ts: str,
         created_at: str, insert_rank: int, role: str, topic: str = "",
         parent: str = "", attrs: Dict[str, Any] = None) -> Dict[str, Any]:
    """H7 节点。`parent` 记 L1/L2 多跳链的父子关系（复用 H2 attach 建边口径）。

    - `parent`：链上一环的合成 id（空=链头）；gold 由 parent_id 链机械推导链深。
    - `created_at` / `insert_rank`：沿用 H6 语义，本轮 L4 不用，保留字段以便后续层复用。
    """
    return {
        "id": nid,
        "scenario": scenario,
        "title": title,
        "content": content,
        "ts": ts,
        "created_at": created_at,
        "insert_rank": insert_rank,
        "role": role,
        "topic": topic,
        "parent": parent,
        "attrs": attrs or {},
    }


def tpl(pre: str, beh: str, con: str) -> str:
    return f"【前因】{pre}\n【行为】{beh}\n【后果】{con}"

#!/usr/bin/env python3
"""scenarios.py — H6「人 vs 数据库：六道分水岭」的场景白名单与词库。

铁律（记忆 cdf155a9）：每题必须落在**真实工作场景**里。本文件用场景白名单守住：
只有 SCENARIOS 里登记的八个场景（部署上线/灰度发布/接口对接/同事交接/开会定口径/
线上排障/数据迁移/权限审批）可以出题；禁用科幻、纯数学、纯图案、纯抽象题材。
`gen_h6.py` 生成后强制断言三件事：scenario ∈ 白名单、题面含该场景标志词、不含禁题材词。

与 H4（`tricky/`）的关系：H4 测「回顾过去准不准」，H6 测「数据库做不到的六件事」——
P1 前瞻记忆 / P2 错误记忆（诱饵）/ P3 主动遗忘 / P4 来源监控 / P5 时间线重建 / P6 重构性。
场景白名单刻意沿用同一套八场景，使两层数字在**同一题材约束**下可比；但题目形态、gold 与判分
完全不同（见 `tests/39-humanlike-h6.md`）。
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

# P4 来源监控：四个来源（人/我/文档），编号用于 gold 与误归因判定
SOURCES: List[Tuple[str, str]] = [("zhang", "同事甲"), ("li", "同事乙"),
                                  ("measured", "我实测"), ("doc", "交接文档")]
SOURCE_NAME = dict(SOURCES)

# P1 前瞻记忆：触发条件池（每条含「可被监控观测到的证据形态」，题面用它来触发）
TRIGGERS: List[Tuple[str, str]] = [
    ("5xx_rate", "5xx 比例"),
    ("p99", "P99 延迟"),
    ("error_rate", "错误率"),
    ("conn_pool", "连接池占用"),
    ("queue_lag", "队列积压"),
    ("disk_usage", "磁盘使用率"),
]

# P2 错误记忆：实体（发布单/工单）上「记了」与「从没记过」的属性
RECORDED_ATTRS = ["镜像版本", "发布人", "发布环境"]
NEVER_RECORDED_ATTRS = ["镜像 tag", "构建号", "回滚点编号"]

# P6 重构性：条目三要素（原因 / 动作 / 数值）
GIST_REASONS = ["压测时发现长尾抖动", "上次故障的复盘结论要求", "对接方反馈超时偏多",
                "容量水位连续三天超阈值", "审计要求留出追溯窗口", "迁移演练暴露校验缺口"]

H6_PREFIX = "hl2"


def scenario_letter(key: str) -> str:
    return "ABCDEFGH"[SCENARIO_KEYS.index(key)]


class Alloc:
    """确定性 id 分配：hl2{场景字母}{4 位序号}。"""

    def __init__(self) -> None:
        self.n: Dict[str, int] = {k: 0 for k in SCENARIO_KEYS}

    def node_id(self, scenario: str) -> str:
        self.n[scenario] += 1
        return f"{H6_PREFIX}{scenario_letter(scenario)}{self.n[scenario]:04d}"


def pick(rng: random.Random, seq: List[Any]) -> Any:
    return seq[rng.randrange(len(seq))]


def node(scenario: str, nid: str, title: str, content: str, *, ts: str,
         created_at: str, insert_rank: int, role: str, topic: str = "",
         attrs: Dict[str, Any] = None) -> Dict[str, Any]:
    """H6 节点。`created_at` 与 `insert_rank` 分开记：P5 要用它们做四象限对照。

    - `created_at`：import 时显式写入的时间（决定「事实发生时间」的回溯锚点）；
    - `insert_rank`：写入顺序（小=先写）。两者在 P5 里被有意打乱。
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
        "attrs": attrs or {},
    }


def tpl(pre: str, beh: str, con: str) -> str:
    return f"【前因】{pre}\n【行为】{beh}\n【后果】{con}"

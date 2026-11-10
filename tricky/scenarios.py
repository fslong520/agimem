#!/usr/bin/env python3
"""scenarios.py — H4 刁钻工作场景：真实工作场景白名单 + 词库 + 六类刁钻模板。

铁律（记忆 cdf155a9）：每题必须落在真实工作场景里。本文件用**场景白名单**守住：
只有 SCENARIOS 里登记的八个场景（部署上线/灰度发布/接口对接/同事交接/开会定口径/
线上排障/数据迁移/权限审批）可以出题，禁用科幻、纯数学、纯图案、纯抽象分类。
gen_tricky.py 生成后会断言：每一题的 scenario 都在白名单内、题面含该场景标志词、
且不含被禁题材词。

节点正文一律 Respire 三段式【前因】【行为】【后果】，与 agimem 主树同语义。
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------- 场景白名单（铁律）

SCENARIO_KEYS = ["deploy", "canary", "api", "handoff", "meeting", "ops", "migration", "approval"]

SCENARIOS: Dict[str, Dict[str, Any]] = {
    "deploy": {
        "name": "部署上线",
        "mark": ["上线", "发布单", "部署"],
        "components": ["订单服务", "结算服务", "网关服务", "会员服务"],
        "envs": ["预发", "生产"],
        "artifacts": [("端口", "8080"), ("启动参数", "max-conn=200"), ("健康检查路径", "/healthz"),
                      ("镜像 tag", "v2.3.1"), ("时区变量", "Asia/Shanghai")],
        "pits": ["只滚了一半实例", "配置中心没同步", "健康检查路径写死在探针里",
                 "旧实例没有先摘流量", "启动脚本里还留着上一版的参数"],
    },
    "canary": {
        "name": "灰度发布",
        "mark": ["灰度", "放量", "回滚"],
        "components": ["推荐服务", "搜索服务", "风控服务"],
        "envs": ["灰度组", "全量组"],
        "artifacts": [("灰度比例", "10%"), ("放量档位", "10→30→100"), ("观察窗口", "15 分钟"),
                      ("回滚开关", "kill-switch"), ("对比指标", "P99 延迟")],
        "pits": ["灰度组和全量组用的是同一份配置", "放量档位跳档", "观察窗口没等到长尾",
                 "回滚开关被上一个需求改名", "灰度流量实际上没打进去"],
    },
    "api": {
        "name": "接口对接",
        "mark": ["接口", "对接", "联调"],
        "components": ["对账接口", "回调接口", "查询接口"],
        "envs": ["沙箱", "正式"],
        "artifacts": [("字段名", "order_no"), ("超时", "3 秒"), ("重试次数", "2 次"),
                      ("签名方式", "HMAC-SHA256"), ("编码", "UTF-8")],
        "pits": ["对方把字段名从下划线改成了驼峰", "超时设得比对方还短", "重试没有做幂等",
                 "沙箱和正式环境签名密钥不同", "回调地址少了一层前缀"],
    },
    "handoff": {
        "name": "同事交接",
        "mark": ["交接", "接手", "离职"],
        "components": ["值班手册", "定时任务", "监控看板"],
        "envs": ["本机", "跳板机"],
        "artifacts": [("定时任务时间", "凌晨 2 点"), ("账号权限", "只读"), ("脚本路径", "/opt/ops/run.sh"),
                      ("告警接收人", "当班组"), ("日志目录", "/var/log/app")],
        "pits": ["手册里写的是上一版流程", "定时任务其实跑在另一台机器上", "脚本路径已经迁走",
                 "告警群换了但手册没改", "手工步骤只有原主会"],
    },
    "meeting": {
        "name": "开会定口径",
        "mark": ["开会", "口径", "周会"],
        "components": ["指标口径", "统计规范", "命名规范"],
        "envs": ["周会", "评审会"],
        "artifacts": [("统计口径", "按下单时间"), ("时间窗口", "自然日"), ("命名规范", "snake_case"),
                      ("金额单位", "分"), ("时区口径", "UTC")],
        "pits": ["两套口径各说各话", "会上定的口径没写进文档", "文档写的和实现不一致",
                 "有人按旧口径出了报表", "跨时区换算没人认领"],
    },
    "ops": {
        "name": "线上排障",
        "mark": ["排障", "告警", "故障"],
        "components": ["支付回调", "消息队列", "数据库主库"],
        "envs": ["生产", "备机房"],
        "artifacts": [("连接池上限", "50"), ("慢查询阈值", "1 秒"), ("积压告警线", "1 万条"),
                      ("重试退避", "指数退避"), ("线程池大小", "32")],
        "pits": ["连接池被慢查询占满", "积压告警线设得比峰值还高", "重试没有退避把下游打满",
                 "只看了一个实例的指标", "扩容只扩了消费者没扩分区"],
    },
    "migration": {
        "name": "数据迁移",
        "mark": ["迁移", "回填", "割接"],
        "components": ["历史订单表", "用户档案", "日志索引"],
        "envs": ["旧库", "新库"],
        "artifacts": [("字符集", "utf8mb4"), ("主键策略", "雪花 id"), ("分批大小", "5000 行"),
                      ("校验方式", "行数+校验和"), ("停写窗口", "30 分钟")],
        "pits": ["字符集不一致导致乱码", "分批太大把主库拖慢", "没有行数校验就对账不上",
                 "自增主键冲突", "停写窗口估短了"],
    },
    "approval": {
        "name": "权限审批",
        "mark": ["审批", "权限", "工单"],
        "components": ["生产库账号", "发布平台", "配置中心"],
        "envs": ["测试环境", "生产环境"],
        "artifacts": [("权限级别", "只读"), ("审批人", "值班主任"), ("有效期", "7 天"),
                      ("令牌轮换", "90 天"), ("审计留痕", "全量")],
        "pits": ["申请单和实际开的权限不一致", "临时权限没设有效期", "审批人休假没人接手",
                 "共用账号查不到人", "审计日志只留 30 天"],
    },
}

# 被禁题材词（铁律守门：出现即判失败）
BANNED_TOPICS = ["科幻", "外星", "量子纠缠", "纯数学", "拓扑空间", "抽象代数", "积分公式",
                 "概率分布题", "图案打印", "矩阵乘法", "图灵机", "希尔伯特", "莫比乌斯环"]

# 同名异事用的「重名物」
SAME_NAME_OBJECTS = ["V2 方案", "那个接口", "临时开关", "第二套口径", "灰度第一批", "回滚脚本"]

# 讨论的参数名（用于 T4/T5 的结论口径）
PARAMS = ["超时时间", "重试次数", "连接池上限", "灰度比例", "分批大小", "有效期限", "观察窗口", "并发上限"]

# 来源与证据级（T6 判分靠这两个字段，确定性、零 LLM）
# 组件口语别名：真实团队里同一系统常被叫别名（结算服务=结算线）。
# T2 用别名写「真定义」，用全名写「诱饵」，使纯字面检索必然选错。
COMP_ALIAS = {
    "订单服务": "订单线", "结算服务": "结算线", "网关服务": "网关侧", "会员服务": "会员侧",
    "推荐服务": "推荐侧", "搜索服务": "搜索侧", "风控服务": "风控侧",
    "对账接口": "对账通道", "回调接口": "回调通道", "查询接口": "查询通道",
    "值班手册": "值班册", "定时任务": "定时作业", "监控看板": "监控盘",
    "指标口径": "指标定义", "统计规范": "统计约定", "命名规范": "命名约定",
    "支付回调": "支付侧回调", "消息队列": "队列层", "数据库主库": "主库实例",
    "历史订单表": "订单历史表", "用户档案": "用户档", "日志索引": "日志库",
    "生产库账号": "库账号", "发布平台": "发布台", "配置中心": "配置仓",
}

SOURCE_GRADE = {"measured": 3, "official": 2, "doc": 1, "hearsay": 1}
SOURCE_CN = {"measured": "我方实测", "official": "官方变更单", "doc": "历史文档", "hearsay": "同事转述"}


def scenario_letter(key: str) -> str:
    return "ABCDEFGH"[SCENARIO_KEYS.index(key)]


class Alloc:
    """确定性 id 分配：trk{场景字母}{4 位序号}，与主树 snt… 不同前缀。"""

    def __init__(self) -> None:
        self.n: Dict[str, int] = {k: 0 for k in SCENARIO_KEYS}

    def node_id(self, scenario: str) -> str:
        self.n[scenario] += 1
        return f"trk{scenario_letter(scenario)}{self.n[scenario]:04d}"


def _pick(rng: random.Random, seq: List[Any]) -> Any:
    return seq[rng.randrange(len(seq))]


def _date(rng: random.Random, lo_month: int = 1, hi_month: int = 10) -> str:
    return f"2026-{rng.randint(lo_month, hi_month):02d}-{rng.randint(1, 28):02d}"


def _other_scenario(rng: random.Random, exclude: str) -> str:
    pool = [k for k in SCENARIO_KEYS if k != exclude]
    return _pick(rng, pool)


def node(scenario: str, nid: str, title: str, content: str, *, ts: str,
         source: str = "doc", topic: str = "", role: str = "", implicit: bool = False,
         same_name_group: str = "", claim: str = "", superseded_by: str = "") -> Dict[str, Any]:
    return {
        "id": nid,
        "scenario": scenario,
        "title": title,
        "content": content,
        "source": source,
        "evidence_grade": SOURCE_GRADE[source],
        "ts": ts,
        "topic": topic,
        "role": role,
        "implicit": implicit,
        "same_name_group": same_name_group,
        "claim": claim,
        "superseded_by": superseded_by,
    }


def _tpl(pre: str, beh: str, con: str) -> str:
    return f"【前因】{pre}\n【行为】{beh}\n【后果】{con}"


# ---------------------------------------------------------------- T1 抗干扰

def build_t1(rng: random.Random, alloc: Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    sc = SCENARIOS[scenario]
    comp = _pick(rng, sc["components"])
    env = _pick(rng, sc["envs"])
    art_name, art_val = _pick(rng, sc["artifacts"])
    pit = _pick(rng, sc["pits"])
    topic = f"{scenario}-t1-{idx}"
    ts = _date(rng)

    gold = node(
        scenario, alloc.node_id(scenario),
        f"{comp}{art_name}的硬约束：{art_val}不能动",
        _tpl(f"上次 {env} {sc['name']}时{art_name}被顺手改成了别的值，结果{pit}",
             f"这次发布单里又有人提议顺手把{art_name}改掉",
             f"评审结论：{art_name} 必须是 {art_val}，谁改谁负责回滚"),
        ts=ts, source="official", topic=topic, role="constraint",
    )
    records = [gold]
    # 5 条真干扰：同主题、同词面，但都是别的场景/别的系统的记录
    for j in range(5):
        other = _other_scenario(rng, scenario)
        osc = SCENARIOS[other]
        ocomp = _pick(rng, osc["components"])
        oart, oval = _pick(rng, osc["artifacts"])
        opit = _pick(rng, osc["pits"])
        records.append(node(
            other, alloc.node_id(other),
            f"{ocomp}{oart}调整记录（{osc['name']}）",
            _tpl(f"{osc['name']}时发现{oart}取值 {oval} 与预期不符",
                 f"在 {osc['name']}流程里调整了{oart}",
                 f"调整后{opit}，与这次{sc['name']}的{art_name}无关"),
            ts=_date(rng), source=_pick(rng, ["doc", "official", "measured"]),
            topic=topic, role="distractor",
        ))
    q = {
        "type": "T1",
        "scenario": scenario,
        "query": (f"这次{sc['name']}的发布单（#{idx}）里又有人提议把 {comp} 的{art_name}顺手改掉。"
                  f"到底能不能动？该按哪条约束来？"),
        "gold_expr": {"kind": "T1", "topic": topic},
        "note": f"抗干扰：同主题 5 条干扰记录（跨场景同词面）淹没唯一真约束 topic={topic}",
    }
    return records, q


# ---------------------------------------------------------------- T2 同名异事

def build_t2(rng: random.Random, alloc: Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    sc = SCENARIOS[scenario]
    # 同名物按轮分批命名：同一基础名在不同批次算不同重名物，
    # 保证 (group, scenario) 在 22 题内唯一 → T2 gold 唯一。
    round_no = idx // len(SAME_NAME_OBJECTS)
    suffix = ["", "（第二批）", "（第三批）", "（第四批）", "（第五批）",
              "（第六批）", "（第七批）", "（第八批）", "（第九批）", "（第十批）"][round_no]
    group = f"{SAME_NAME_OBJECTS[idx % len(SAME_NAME_OBJECTS)]}{suffix}"
    # 第二个场景取固定偏移 4：保证重名物在另一场合确有同名不同义
    other = SCENARIO_KEYS[(SCENARIO_KEYS.index(scenario) + 4) % len(SCENARIO_KEYS)]
    osc = SCENARIOS[other]
    day = _date(rng)
    comp = _pick(rng, sc["components"])
    alias = COMP_ALIAS.get(comp, comp)
    ocomp = _pick(rng, osc["components"])
    art, val = _pick(rng, sc["artifacts"])
    _oart, oval = _pick(rng, osc["artifacts"])

    a = node(scenario, alloc.node_id(scenario),
             f"「{group}」的原始定义（{alias}）",
             _tpl(f"{day} 为{alias}那件事临时起了个名，就叫「{group}」",
                  f"约定「{group}」只在那件事上生效，{art}={val}",
                  f"之后打算按它执行的时候，指的就是这一条"),
             ts=day, source="official", same_name_group=group)
    # 诱饵：这条属于别的场景，但**故意**写满了本次场景的词面（场景名/组件/日期），
    # 只靠字面重叠会选错——必须按「这个场合到底指哪件事」判断。这正是同名异事刁钻点。
    b = node(other, alloc.node_id(other),
             f"「{group}」{sc['name']}复盘：{comp} 那次约定的记录（{ocomp}）",
             _tpl(f"{day} {sc['name']}前后，{osc['name']}的同事也参与了复盘，顺手记下「{group}」",
                  f"但他们记的是{ocomp}那件事：{_oart}按 {oval} 处理",
                  f"这条属于{osc['name']}的场景，与本次「{group}」不是同一个东西"),
             ts=day, source="official", same_name_group=group)
    records = [a, b]
    # 4 条近名干扰：名字相似但不同组
    for j in range(4):
        near = f"{group}的旧版本" if j % 2 == 0 else f"{group}（{_pick(rng, ['草稿', '初版', '备选'])}）"
        s3 = _other_scenario(rng, scenario)
        records.append(node(
            s3, alloc.node_id(s3),
            f"{near} — {_pick(rng, SCENARIOS[s3]['components'])}",
            _tpl(f"早前在{SCENARIOS[s3]['name']}里用过近似名字 {near}",
                 "后来改叫别的东西了",
                 "与现在的「%s」不是同一个东西" % group),
            ts=_date(rng), source="doc", same_name_group=near,
        ))
    q = {
        "type": "T2",
        "scenario": scenario,
        "query": (f"上次 {day} 在{sc['name']}里说的「{group}」——这次要按它执行 {comp} 的事。"
                  f"对应的到底是哪条记录？（同名还有别的场合用过）"),
        "gold_expr": {"kind": "T2", "group": group, "scenario": scenario},
        "note": f"同名异事：group={group} 在 {scenario} 与 {other} 两名同实异，按情景区分",
    }
    return records, q


# ---------------------------------------------------------------- T3 隐含约束

def build_t3(rng: random.Random, alloc: Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    sc = SCENARIOS[scenario]
    comp = _pick(rng, sc["components"])
    art, val = _pick(rng, sc["artifacts"])
    pit = _pick(rng, sc["pits"])
    place = _pick(rng, ["启动脚本", "探针配置", "部署模板", "定时任务", "前端配置"])
    topic = f"{scenario}-t3-{idx}"
    ts = _date(rng)

    gold = node(
        scenario, alloc.node_id(scenario),
        f"{comp}的{art}还有一处没写进文档",
        _tpl(f"文档里只写了主配置里的{art}，没人提{place}里也有一份",
             f"上次有人照文档改了{art}，{place}里的旧值没跟着改",
             f"结果{pit}；这条规矩没人明说，但大家都当默认：改{art}必须同步改{place}"),
        ts=ts, source="measured", topic=topic, implicit=True,
    )
    records = [gold]
    # 3 条显式文档干扰：文档说可以随便改（正是坑）
    for j in range(3):
        records.append(node(
            scenario, alloc.node_id(scenario),
            f"文档摘要：{sc['name']}的{art}可按需调整（第 {j + 1} 版）",
            _tpl("文档维护者按主配置写了说明",
                 f"写明{art}可在{sc['name']}时按需调整",
                 "但文档没覆盖非主配置里的副本，照此执行会踩坑"),
            ts=_date(rng), source="doc", topic=topic, role="distractor",
        ))
    # 2 条别处隐含规矩（近邻干扰）
    for j in range(2):
        s2 = _other_scenario(rng, scenario)
        records.append(node(
            s2, alloc.node_id(s2),
            f"{_pick(rng, SCENARIOS[s2]['components'])}的隐含规矩（{SCENARIOS[s2]['name']}）",
            _tpl("没人写进文档，但都当默认",
                 f"{_pick(rng, SCENARIOS[s2]['artifacts'])[0]}要按老规矩处理",
                 "与本次场景无关"),
            ts=_date(rng), source="measured", implicit=True,
        ))
    q = {
        "type": "T3",
        "scenario": scenario,
        "query": (f"{sc['name']}要改 {comp} 的{art}（改造工单 #{idx}）。文档上只写了主配置、没说别的坑，"
                  f"实际上有什么隐含规矩必须先处理？"),
        "gold_expr": {"kind": "T3", "topic": topic},
        "note": f"隐含约束：规矩不在文档里（{place} 有副本），topic={topic}",
    }
    return records, q


# ---------------------------------------------------------------- T4 旧结论失效

def build_t4(rng: random.Random, alloc: Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    sc = SCENARIOS[scenario]
    comp = _pick(rng, sc["components"])
    param = PARAMS[idx % len(PARAMS)]
    old_val, new_val = _pick(rng, [("3 秒", "8 秒"), ("2 次", "4 次"), ("50", "120"),
                                   ("10%", "5%"), ("5000 行", "2000 行"), ("7 天", "30 天"),
                                   ("15 分钟", "45 分钟"), ("32", "64")])
    topic = f"{scenario}-t4-{idx}"
    old_ts, new_ts = _date(rng, 1, 5), _date(rng, 6, 10)

    new_id = alloc.node_id(scenario)
    old = node(
        scenario, alloc.node_id(scenario),
        f"旧结论：{comp}的{param}设 {old_val} 就够",
        _tpl(f"早期在{sc['name']}里按经验把{param}定为 {old_val}",
             f"这个取值沿用了{_pick(rng, ['两', '三', '四'])}个月",
             f"后来发现新链路下不够用，旧结论被推翻"),
        ts=old_ts, source="doc", topic=topic, role="old", superseded_by=new_id,
    )
    new = node(
        scenario, new_id,
        f"新结论：{comp}的{param}改为 {new_val}",
        _tpl(f"复盘发现按旧值 {old_val} 会在{_pick(rng, sc['pits'])}时失效",
             f"新结论：{param}改为 {new_val}，旧口径不再适用",
             f"当前所有{sc['name']}按 {new_val} 执行"),
        ts=new_ts, source="official", topic=topic, role="current",
    )
    records = [old, new]
    # 3 条「更近但不是这条」的干扰（ts 更晚，但另一主题）
    for j in range(3):
        s2 = _other_scenario(rng, scenario)
        records.append(node(
            s2, alloc.node_id(s2),
            f"{_pick(rng, SCENARIOS[s2]['components'])}的{_pick(rng, PARAMS)}口径更新（{SCENARIOS[s2]['name']}）",
            _tpl("那条链路上重新评估了参数", "把取值改了一档", "与本条主题无关"),
            ts=_date(rng, 8, 10), source="official",
        ))
    q = {
        "type": "T4",
        "scenario": scenario,
        "query": (f"{sc['name']}这次要定 {comp} 的{param}（评审第 {idx} 项）。以前有过相反的结论，"
                  f"现在按哪条生效？"),
        "gold_expr": {"kind": "T4", "old": old["id"]},
        "note": f"失效感知：{old['id']} --superseded_by--> {new_id}；旧口径 {old_val} → 新 {new_val}",
    }
    return records, q


# ---------------------------------------------------------------- T5 跨时间一致性

def build_t5(rng: random.Random, alloc: Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    sc = SCENARIOS[scenario]
    comp = _pick(rng, sc["components"])
    param = PARAMS[(idx + 3) % len(PARAMS)]
    vals = _pick(rng, [("3 秒", "6 秒", "10 秒"), ("2 次", "3 次", "5 次"),
                       ("50", "80", "150"), ("10%", "20%", "5%"),
                       ("5000 行", "3000 行", "1000 行"), ("7 天", "14 天", "30 天"),
                       ("15 分钟", "30 分钟", "60 分钟"), ("32", "48", "96")])
    topic = f"{scenario}-t5-{idx}"
    ts_list = [_date(rng, 1, 3), _date(rng, 4, 7), _date(rng, 8, 10)]

    ids = [alloc.node_id(scenario) for _ in range(3)]
    n1 = node(scenario, ids[0],
              f"半年前的结论：{comp}的{param}定 {vals[0]}",
              _tpl(f"{ts_list[0]} 在{sc['name']}里首次定下{param} = {vals[0]}",
                   "按当时链路规模执行",
                   f"结论写入团队文档，之后一直按 {vals[0]} 跑"),
              ts=ts_list[0], source="doc", topic=topic, role="old", superseded_by=ids[1])
    n2 = node(scenario, ids[1],
              f"中途修订：{comp}的{param}改为 {vals[1]}",
              _tpl(f"链路扩容后发现 {vals[0]} 不够，{ts_list[1]} 复盘推翻旧值",
                   f"新结论：{param} = {vals[1]}，旧的 {vals[0]} 作废",
                   f"文档更新为 {vals[1]}，但仍不是最终结论"),
              ts=ts_list[1], source="official", topic=topic, role="old", superseded_by=ids[2])
    n3 = node(scenario, ids[2],
              f"现行结论：{comp}的{param}最终定为 {vals[2]}",
              _tpl(f"又一次压测发现 {vals[1]} 仍偏保守，{ts_list[2]} 再修一次",
                   f"新结论：{param} 改为 {vals[2]}，此前两版都不再适用",
                   f"当前按 {vals[2]} 执行"),
              ts=ts_list[2], source="measured", topic=topic, role="current")
    records = [n1, n2, n3]
    # 2 条同组件不同主题的记录（近邻干扰，不是这条链）
    for j in range(2):
        records.append(node(
            scenario, alloc.node_id(scenario),
            f"{comp}的另一次{_pick(rng, ['容量评估', '演练记录', '成本复盘'])}（{_date(rng)}）",
            _tpl("另一条链路上的评估", f"{_pick(rng, PARAMS)}被单独讨论过", "与本次口径无关"),
            ts=_date(rng, 6, 10), source="doc", topic=f"{topic}-aside-{j}",
        ))
    q = {
        "type": "T5",
        "scenario": scenario,
        "query": (f"半年前（{ts_list[0]}，口径修订第 {idx} 轮）在{sc['name']}定的「{comp} 的{param}」结论，现在还成立吗？"
                  f"当前有效的是哪条？"),
        "gold_expr": {"kind": "T5", "head": ids[0]},
        "note": f"跨时间一致性：三跳取代链 {ids[0]}→{ids[1]}→{ids[2]}，gold=链尾（时间戳 {ts_list[0]}→{ts_list[2]}）",
    }
    return records, q


# ---------------------------------------------------------------- T6 转述 vs 实测

def build_t6(rng: random.Random, alloc: Alloc, scenario: str, idx: int
             ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    sc = SCENARIOS[scenario]
    comp = _pick(rng, sc["components"])
    art, val = _pick(rng, sc["artifacts"])
    pit = _pick(rng, sc["pits"])
    claim = f"{scenario}-t6-{idx}"

    measured = node(
        scenario, alloc.node_id(scenario),
        f"我方实测：{comp}按 {val} 会炸",
        _tpl(f"为了验证 {comp} 的{art}，我们在{_pick(rng, ['压测环境', '预发', '备机房'])}实际压了一轮",
             f"实测到 {_pick(rng, ['200', '500', '1000'])} 并发时出现 {pit}",
             f"实测记录：{art} = {val} 在这个规模下不可用"),
        ts=_date(rng), source="measured", claim=claim,
    )
    hearsay = node(
        scenario, alloc.node_id(scenario),
        f"同事转述：{comp}按 {val} 应该没事",
        _tpl("同事甲说之前别的团队这么用过",
             f"口头结论：{comp}的{art}用 {val} 应该没问题，不用压测",
             "这条只是转述，没有实测数据支撑"),
        ts=_date(rng), source="hearsay", claim=claim,
    )
    doc = node(
        scenario, alloc.node_id(scenario),
        f"变更单记录：{comp}的{art}登记为 {val}",
        _tpl("变更单按文档惯例登记取值",
             f"登记 {art} = {val}",
             "变更单只登记理论值，不含实测验证"),
        ts=_date(rng), source="official", claim=claim,
    )
    records = [hearsay, doc, measured]
    # 3 条无关干扰
    for j in range(3):
        s2 = _other_scenario(rng, scenario)
        records.append(node(
            s2, alloc.node_id(s2),
            f"{_pick(rng, SCENARIOS[s2]['components'])}的{_pick(rng, SCENARIOS[s2]['artifacts'])[0]}记录（{SCENARIOS[s2]['name']}）",
            _tpl("别的系统的记录", "与本条无关", "不影响本次判断"),
            ts=_date(rng), source=_pick(rng, ["doc", "hearsay"]),
        ))
    q = {
        "type": "T6",
        "scenario": scenario,
        "query": (f"{sc['name']}前（联调记录 #{idx}），同事说「{comp} 的{art}用 {val} 应该没事」，"
                  f"但我们这边实测过。该信哪条、按哪条处理？"),
        "gold_expr": {"kind": "T6", "claim": claim},
        "note": f"证据分级：claim={claim} 有 转述(grade1)/变更单(grade2)/实测(grade3)，gold=实测",
    }
    return records, q


BUILDERS = {
    "T1": build_t1,
    "T2": build_t2,
    "T3": build_t3,
    "T4": build_t4,
    "T5": build_t5,
    "T6": build_t6,
}

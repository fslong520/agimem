#!/usr/bin/env python3
"""gen_tree.py — 确定性 seed 扩树：合成因果树 → agimem 造题的唯一树来源。

用法：
    python3 gen_tree.py --seed 20261109 --out data/tree.json [--verify]

设计（零 LLM、全确定性；节点必须是 Respire 三段式语义，见 docs/design.md）：
  1. 每棵树按骨架形状确定生成（chain / fork / fan / merge，seed 决定每棵形状）；
  2. 节点正文由「主题词库 × 结构槽位」机械拼装为【前因】【行为】【后果】；
  3. action_key / outcome / superseded_by 由结构与 seed 确定种入；
  4. noise 关键词与全树正文互斥（生成时断言，脱敏红线）；
  5. --verify 把既有 data/tree.json 与 seed 重生成结果比对，内容一致即 exit 0。

id 口径：8 位短 id（bench 短 id 口径，causal_gold.load_tree 强制）。
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SEED = 20261109
N_TREES = 10
NODES_PER_TREE = 24

# ---------------------------------------------------------------- 词库（全合成）

TREE_THEMES: Dict[str, Dict[str, Any]] = {
    "A": {
        "chain": "构建缓存",
        "tag": "构建",
        "steps": [
            ("基础镜像升级引入缓存不兼容", "镜像里工具链版本整体升级", "连带更新缓存键", "构建缓存开始出现部分命中失败"),
            ("缓存键只按分支名计算", "键设计之初只取了分支名", "升级后继续沿用旧键复用缓存", "脏缓存被当作有效命中"),
            ("脏缓存进入链接阶段", "脏缓存被当作命中", "直接复用旧产物继续链接", "链接阶段报出未定义符号错误"),
            ("本地反复重试构建浪费两小时", "链接报错后误以为是偶发抖动", "本地反复重试构建", "两小时被浪费且问题稳定复现"),
            ("缓存键改为内容哈希后构建恢复", "回看日志定位到键粒度过粗", "把缓存键改为内容哈希", "构建恢复稳定，同类问题不再复现"),
        ],
        "sibling": [
            ("镜像滚动回滚掩盖真实报错", "缓存故障后先回滚镜像", "把镜像回滚到上一版本", "真实报错被掩盖，故障延后一天复现"),
            ("构建产物未做哈希校验", "产物目录直接沿用", "跳过产物哈希校验", "一半节点引用了过期产物"),
            ("并行任务共用临时目录", "为省磁盘共用临时目录", "多个任务写同一路径", "中间产物互相覆盖，失败随机复现"),
        ],
        "fix": [
            ("分层缓存键按路径与工具链哈希", "复盘发现单一键粒度过粗", "把键拆成路径加工具链哈希两层", "命中率回升且不再串味"),
            ("构建产物加签名校验", "排查到过期产物被引用", "给产物目录加签名校验", "过期产物在链接前即被拒"),
            ("临时目录按任务隔离", "复现到产物互相覆盖", "按任务隔离临时目录并清理", "随机失败消失"),
        ],
        "pitfall": [
            ("全量重建拖垮 CI 队列", "构建失败后图省事", "强制清空全部缓存并全量重建", "CI 队列被全量重建拖垮，其他任务排队约四十分钟"),
            ("并行度拉满触发 OOM", "为赶进度把并发拉到最大", "把构建并行度拉满", "构建机内存耗尽，连续十次构建被杀"),
            ("缓存命中异常直接清空全部", "看到脏缓存就清空", "不分青红皂白清空全部缓存", "构建时长翻倍且命中率一周未恢复"),
        ],
    },
    "B": {
        "chain": "发布灰度",
        "tag": "发布",
        "steps": [
            ("高峰期补丁发布决策", "支付回调延迟告警连续增多", "决定当天在高峰期推送补丁", "发布窗口与业务高峰重叠"),
            ("高峰期全量推补丁触发限流回滚", "高峰期直接全量推送补丁", "没有先做小流量灰度", "回调积压被放大并触发限流，回滚耗时二十分钟"),
            ("先放一成灰度观察十五分钟", "吸取上次全量推送的教训", "先放一成流量灰度并观察十五分钟", "故障没有被放大并顺利定位"),
            ("灰度指标正常后逐步放量到全量", "灰度观察指标全部正常", "按档位逐步放量到全量", "发布完成且没有触发回滚"),
            ("热加载配置写错单位引发雪崩重启", "临时改配置没有走变更单", "直接热加载了新配置", "超时参数把秒当成毫秒写入，引发雪崩重启"),
        ],
        "sibling": [
            ("回滚脚本未演练临时失灵", "只在文档里写了回滚步骤", "回滚时才发现脚本参数过期", "回滚多耗时十五分钟"),
            ("多服务发布顺序未约束", "各服务独立点发布", "按随机顺序推送五个服务", "接口短暂不兼容，报错窗口两分钟"),
            ("灰度放量步长过大", "灰度指标正常后直接跳档", "一步放量到全量", "剩余流量瞬间打满，触发一次降级"),
        ],
        "fix": [
            ("发布改为按服务依赖排序", "复盘发现顺序随意", "按依赖顺序排队发布", "接口不兼容窗口消失"),
            ("回滚脚本纳入发布前演练", "回滚临时失灵", "发布前必须演练回滚脚本", "回滚耗时从十五分钟降到两分钟"),
            ("配置变更走变更单与双人复核", "热加载写错单位", "配置变更纳入变更单与双人复核", "同类配置事故不再复现"),
        ],
        "pitfall": [
            ("高峰期直接全量推送补丁", "收到告警后急于止血", "在高峰期直接全量推送", "回调积压被放大，限流触发两次"),
            ("灰度期太短没等到长尾异常", "只观察了五分钟", "灰度五分钟即放量", "长尾用户异常在放量后才暴露"),
            ("发布未冻结旁路任务", "发布窗口旁路任务照常跑", "旁路任务与发布同时执行", "资源争抢把发布耗时拖成三倍"),
        ],
    },
    "C": {
        "chain": "移动端同步",
        "tag": "同步",
        "steps": [
            ("移动端同步延迟现象", "移动端用户反馈白天看到的是隔夜数据", "排查发现批量同步任务集中在夜间执行", "白天读取到的是过期快照"),
            ("把同步窗口定在凌晨三点但延迟依旧", "按当时理解把同步窗口定在凌晨三点", "沿用了这个排程", "白天的延迟依旧存在"),
            ("扩线程的旧结论：瓶颈在单线程写入", "连续一周延迟没有下降", "当时结论：瓶颈在单线程写入，需要扩到四线程", "结论写入经验库等待验证"),
            ("重新压测把瓶颈定位到锁竞争", "扩到四线程之后延迟没有下降", "重新做了一轮压测", "瓶颈被定位到锁竞争"),
            ("分片队列的新结论：锁竞争而非线程数", "压测把瓶颈定位到锁竞争", "新结论：延迟源于锁竞争，改为分片队列即可，无需扩线程", "方案进入实施"),
            ("分片队列上线后延迟降到秒级", "分片队列上线", "白天采样延迟指标", "同步延迟降到秒级"),
        ],
        "sibling": [
            ("增量同步全量拉取拖慢首屏", "为省事每次全量拉取", "把增量同步改成全量拉取", "首屏耗时从一秒涨到四秒"),
            ("冲突合并规则缺失丢单条", "两端同时编辑", "按最后写入者胜合并", "先写端的一条修改被静默丢弃"),
            ("离线队列无上限堆积", "弱网下持续入队", "离线队列不设上限", "重连瞬间洪峰把服务端打挂"),
        ],
        "fix": [
            ("同步改增量并按变更游标拉取", "全量拉取拖慢首屏", "改成按变更游标增量拉取", "首屏耗时回到一秒以内"),
            ("冲突合并改为三方合并", "复现到单条丢失", "引入三方合并规则", "冲突丢数据不再出现"),
            ("离线队列设上限并按优先级出队", "弱网队列堆积", "设队列上限与优先级", "重连洪峰被削平"),
        ],
        "pitfall": [
            ("同步窗口定在凌晨三点但延迟依旧", "按经验把窗口定在凌晨三点", "沿用固定窗口排程", "白天延迟依旧，问题延后一周才被重查"),
            ("扩到四线程延迟没有下降", "把瓶颈猜成单线程", "直接扩到四线程", "延迟没有下降还多占了三核"),
            ("同步失败静默重试无上限", "同步报错后自动重试", "失败静默无限重试", "坏条目被反复拉取，带宽被吃掉一半"),
        ],
    },
    "D": {
        "chain": "告警降噪",
        "tag": "告警",
        "steps": [
            ("告警风暴淹没值班群", "三个监控系统同时接入同一个群", "不做分级直接全量推送", "值班群每分钟几十条告警"),
            ("值班开始凭感觉忽略告警", "告警太多看不过来", "值班选择性忽略低级别告警", "一次真实故障的告警被淹没"),
            ("故障两小时后才被上报", "被淹没的告警无人跟进", "等用户投诉才确认故障", "故障影响扩大到两小时"),
            ("按影响面给告警分级的新结论", "复盘认为告警没有分级", "新结论：按影响面分级，只推 P0", "值班群恢复可读"),
            ("分级后 P0 平均响应降到五分钟", "分级规则上线", "抽样统计响应时长", "P0 平均响应降到五分钟"),
        ],
        "sibling": [
            ("阈值过敏感知抖动触发告警", "阈值按最低负载设", "把阈值贴着日常值设置", "负载抖动即触发告警"),
            ("同一故障多系统重复告警", "各系统独立判定", "同一故障产生五条告警", "值班按条数误判故障规模"),
            ("告警缺少上下文难定位", "只推送指标名", "告警不带最近变更链接", "定位平均要翻五个看板"),
        ],
        "fix": [
            ("阈值改为按分位数自适应", "阈值敏感导致误报", "按近七天分位数设阈值", "误报下降且仍能抓到真实异常"),
            ("多系统告警按指纹合并", "同一故障重复告警", "按指纹合并同一故障", "值班看到的条数降到原来的五分之一"),
            ("告警附带最近变更与看板链接", "告警缺上下文", "推送时附变更链接与看板", "定位时间从十分钟降到三分钟"),
        ],
        "pitfall": [
            ("阈值贴日常值设导致误报不断", "为尽早发现异常", "把阈值贴着日常值设置", "误报刷屏，真实告警被淹没"),
            ("只推 P0 丢掉前置信号", "分级后为省事只推 P0", "把 P1 全部静音", "前置信号丢失，故障发现反而变慢"),
            ("告警静音窗口过大", "为躲避夜间打扰", "把夜间静音开到八小时", "夜间真实故障八小时无人知晓"),
        ],
    },
    "E": {
        "chain": "日志检索",
        "tag": "日志",
        "steps": [
            ("日志变慢的旧结论：磁盘写入慢需换硬件", "发布之后日志查询明显变慢", "当时结论：磁盘写入慢，需要换固态硬盘", "换了硬盘之后依旧慢"),
            ("日志变慢的新结论：异步刷盘即可无需换硬件", "复盘定位到日志同步刷盘阻塞", "新结论：改为异步刷盘即可，无需更换硬件", "日志查询恢复到正常延迟"),
            ("日志量翻倍撑爆索引分区", "日志保留期从七天改到三十天", "沿用旧分区策略", "索引分区写满，写入开始拒绝"),
            ("按量自动分片的新结论", "压测定位到单分区瓶颈", "新结论：按量自动分片并滚动滚动清理", "写入恢复且查询延迟稳定"),
            ("查询预热后首查不再超时", "冷缓存导致首查超时", "给高频索引做查询预热", "首查耗时从十秒降到一秒内"),
        ],
        "sibling": [
            ("日志字段未结构化难聚合", "日志按纯文本输出", "不带字段名直接拼字符串", "聚合查询要写一堆正则"),
            ("采样率一刀切丢关键日志", "为省成本统一采样", "把所有日志按一成采样", "低频但关键的错误日志被丢掉"),
            ("日志时钟不同步对不上序", "多机时钟未校准", "各机按本地时间打时间戳", "跨机排障时顺序对不上"),
        ],
        "fix": [
            ("日志改结构化输出并带字段名", "纯文本难聚合", "改为结构化字段输出", "聚合查询改写成简单条件"),
            ("按日志级别分档采样", "一刀切采样丢关键日志", "错误全量采、调试按一成", "成本可控且关键日志不再丢"),
            ("统一时钟校准并打单调序号", "跨机时序错乱", "统一 NTP 校准并加单调序号", "跨机排障顺序可还原"),
        ],
        "pitfall": [
            ("保留期改三十天撑爆索引", "为排障方便延长保留", "把保留期直接改到三十天", "索引分区写满，写入拒绝持续十分钟"),
            ("异步刷盘过猛丢尾部日志", "为提速调大刷盘缓冲", "把刷盘缓冲调到极限", "进程崩溃时尾部日志丢失"),
            ("全量索引重建阻塞写入", "为修索引直接重建", "在业务高峰重建索引", "写入被阻塞八分钟，上游超时"),
        ],
    },
    "F": {
        "chain": "权限审计",
        "tag": "权限",
        "steps": [
            ("共享账号被用来改生产配置", "排障时共用一个运维账号", "多人共用同一凭据", "一次配置改动查不到责任人"),
            ("审计日志缺失无法追责", "共用账号只记了操作不记人", "审计日志不带操作者维度", "事后只能靠回忆还原现场"),
            ("补上个人令牌与操作留痕的新结论", "复盘要求能追到人", "新结论：启用个人令牌并全量留痕", "每次改动都能定位到人"),
            ("令牌轮换周期过长留隐患", "令牌一年未轮换", "沿用旧轮换策略", "一台机器泄漏的令牌用了半年"),
            ("轮换自动化后审计闭环", "把轮换接进定时任务", "按九十天自动轮换", "泄漏窗口缩短到一个季度内"),
        ],
        "sibling": [
            ("权限申请单据与实际不符", "申请走纸质流程", "审批后手工开权限", "实际权限比申请多了两项"),
            ("离职账号未及时回收", "离职流程与系统不同步", "账号保留观察期过长", "离职三个月后仍有登录尝试"),
            ("只读账号被授予写接口", "为省事给只读账号加写", "把写接口一并开放", "只读账号改出一条脏数据"),
        ],
        "fix": [
            ("权限开通改为工单自动同步", "手工开通易偏差", "工单审批后自动同步权限", "申请与实际权限一致"),
            ("离职账号当日自动禁用", "回收不及时", "离职流程触发当日禁用", "离职后登录尝试全部被拒"),
            ("只读账号收口到只读接口", "只读账号带写权限", "网关层强制只读路由", "只读账号无法再写数据"),
        ],
        "pitfall": [
            ("共享账号排障省事埋下隐患", "为快速排障共用账号", "多人共用一个运维账号", "配置改动无法追责"),
            ("权限批量放开图省事", "上线前赶工", "把一个组的权限整组放开", "组内三人拿到了越权接口"),
            ("审计日志只留三十天", "为省存储缩短保留", "审计日志保留改成三十天", "跨季度追责时日志已过期"),
        ],
    },
    "G": {
        "chain": "消息队列",
        "tag": "队列",
        "steps": [
            ("队列积压拖垮下游", "上游促销把流量翻了五倍", "沿用单队列单消费者", "队列积压两小时才被发现"),
            ("盲目扩容消费者触发重复消费", "看到积压先扩消费者", "把消费者扩到二十个且不加锁", "同一条消息被处理三次"),
            ("加幂等键后重复被挡住的新结论", "复盘定位到重复消费", "新结论：按业务幂等键去重", "重复处理被挡在入口"),
            ("按分区打散后吞吐回升", "单队列成瓶颈", "按业务键分区并行消费", "吞吐回到峰值两倍"),
            ("积压告警接入值班后响应变快", "积压发现靠人工", "给队列深度加告警", "积压平均发现时间降到三分钟"),
        ],
        "sibling": [
            ("消息体过大阻塞网络", "消息里塞了整份快照", "直接把大对象塞进消息", "队列带宽被单条消息占满"),
            ("消费失败无重试直接丢", "消费异常直接跳过", "失败消息不落死信", "约百分之一订单静默丢失"),
            ("分区键倾斜热点集中", "按用户 id 分区但用户不均", "沿用默认分区键", "一个分区承担一半流量"),
        ],
        "fix": [
            ("消息改引用加对象存储", "消息体过大", "消息只带引用与校验和", "队列带宽占用降到原来两成"),
            ("失败消息落死信并告警", "失败消息被丢弃", "接入死信队列与重试", "静默丢失清零且可人工补发"),
            ("分区键改为散列加盐", "分区倾斜", "对热点键加盐散列", "分区负载方差明显收窄"),
        ],
        "pitfall": [
            ("消费者不加锁盲目扩容", "为消积压直接扩", "把消费者扩到二十个", "同一条消息被处理三次"),
            ("重试策略过激放大故障", "为不丢消息无限重试", "失败即刻无限重试", "下游被打挂，积压反而翻倍"),
            ("队列无上限堆积打爆磁盘", "不设积压上限", "允许无限堆积", "磁盘写满导致队列进程退出"),
        ],
    },
    "H": {
        "chain": "接口超时",
        "tag": "超时",
        "steps": [
            ("下游抖动引发级联超时", "一个下游实例变慢", "调用方不设超时直接等待", "线程池被等待占满"),
            ("线程池耗尽服务整体假死", "线程全被慢调用占住", "新请求拿不到线程", "健康检查失败触发重启"),
            ("引入超时与熔断的新结论", "复盘认为缺隔离", "新结论：按依赖设超时并熔断", "慢依赖不再拖垮整体"),
            ("半开探测恢复流量", "熔断后需要试探恢复", "按半开状态放小流量探测", "恢复过程不再引发二次雪崩"),
            ("P99 从八秒回到三百毫秒", "超时熔断上线", "抽样统计 P99", "P99 回到三百毫秒"),
        ],
        "sibling": [
            ("连接池上限过小排队等连接", "连接池按默认值", "并发上来后排队取连接", "排队时间占了调用耗时一半"),
            ("重试不带退避打满下游", "失败立即重试", "无退避连续重试三次", "下游恢复期被重试打满"),
            ("超时值设得比上游还长", "各服务独立拍脑袋定超时", "把超时设成三十秒", "上游早已放弃，下游还在算"),
        ],
        "fix": [
            ("连接池按压测结果调参", "连接池过小", "按压测把池调到合适水位", "排队取连接的时间消失"),
            ("重试改指数退避加抖动", "重试打满下游", "改为指数退避并加抖动", "下游恢复期不再被重试压垮"),
            ("超时按调用链自顶向下收口", "超时层层放大", "顶层定总超时并向下分层", "上游放弃时下游同步放弃"),
        ],
        "pitfall": [
            ("调用不设超时被慢下游拖死", "为不误杀慢调用", "调用方不设超时", "线程池被占满，服务假死"),
            ("熔断阈值过低频繁开断", "为尽快止损", "错误率超一成即熔断", "抖动期频繁开断，可用性反降"),
            ("超时收口过短误杀慢查询", "为压 P99 一刀切", "把超时统一压到一百毫秒", "合理慢查询被误杀，报表任务失败"),
        ],
    },
    "I": {
        "chain": "数据导出",
        "tag": "导出",
        "steps": [
            ("全量导出拖垮主库", "为对账临时加全量导出", "在主库直接跑全量查询", "主库负载打满，交易接口变慢"),
            ("导出改走从库后仍带锁", "为减轻主库压力改从库", "导出查询带了写事务", "从库被长事务锁住，同步延迟升高"),
            ("只读快照加游标分页的新结论", "复盘定位到锁与全量", "新结论：只读快照加游标分页", "导出不再影响在线流量"),
            ("导出文件加密并限时删除", "导出文件散落各处", "改为加密落盘并定时清理", "导出文件不再长期暴露"),
            ("对账耗时从三小时降到二十分钟", "分页导出上线", "统计整条链路耗时", "对账耗时降到二十分钟"),
        ],
        "sibling": [
            ("导出字符集不一致乱码", "两端字符集不同", "直接按默认字符集导出", "下游拿到的中文全是乱码"),
            ("导出无校验行数对不上", "导出后不校验", "直接把文件交给下游", "下游对账差了三百行"),
            ("大文件一次性写盘撑爆磁盘", "不分批直接写", "单文件写满整个磁盘", "导出任务失败并触发磁盘告警"),
        ],
        "fix": [
            ("导出统一 UTF-8 并转义校验", "字符集不一致", "两端统一 UTF-8", "乱码投诉清零"),
            ("导出加行数与校验和对账", "无校验对不上", "导出后校验行数与校验和", "对账差异在交付前即被拦下"),
            ("导出改分片流式写盘", "一次性写撑爆磁盘", "分片流式写并配额检查", "大导出不再撑爆磁盘"),
        ],
        "pitfall": [
            ("主库直接跑全量导出", "为省事在主库导出", "在主库直接跑全量查询", "主库负载打满，交易变慢"),
            ("导出走从库仍带写事务", "只换了库没换事务", "导出查询带写事务", "从库被锁，同步延迟涨到十分钟"),
            ("导出文件明文散落共享盘", "为方便共享", "明文写到共享目录", "文件被无关人员下载"),
        ],
    },
    "J": {
        "chain": "时区与报表",
        "tag": "报表",
        "steps": [
            ("日报数字与后台对不上", "日报按本地时区汇总", "后台按 UTC 落数", "两端口径差了八小时"),
            ("排查发现时区混用", "不同服务时区配置不同", "有的存本地时间有的存 UTC", "同一指标三处口径"),
            ("统一存 UTC 按需展示的新结论", "复盘要求口径统一", "新结论：存储一律 UTC，展示按时区换算", "日报与后台对上"),
            ("历史数据按日回填校正", "旧数据口径混杂", "按日回填并标注口径", "历史报表可比"),
            ("跨时区用户投诉清零", "口径统一上线", "抽样核对跨时区用户报表", "跨时区投诉清零"),
        ],
        "sibling": [
            ("夏令时切换重复计数", "切换日未处理", "按固定偏移换算", "切换当日数据翻倍"),
            ("月初第一天聚合漏一天", "聚合从零点起算", "首日窗口少算一天", "月报首日总是偏低"),
            ("周报起始日两端不一致", "一端周一起一端周日起", "各自按默认配置", "周报数字两端差一天"),
        ],
        "fix": [
            ("夏令时按 tz 数据库换算", "固定偏移算错", "改用时区数据库换算", "切换日不再重复计数"),
            ("聚合窗口改为闭区间", "首日漏算", "改为含首尾的闭区间", "月报首日与后台一致"),
            ("周起始日全局统一配置", "两端不一致", "全局统一为周一起", "周报两端口径一致"),
        ],
        "pitfall": [
            ("日报按本地时区后台按 UTC", "各端按各自习惯", "两端时区口径不同", "日报与后台差八小时"),
            ("为赶报表临时改聚合窗口", "报表对不上时改口径", "临时把窗口改成包含当天", "口径漂移，次日又对不上"),
            ("时区配置散落各服务", "每个服务自己配时区", "五个服务五种时区配置", "排查口径问题花了一整天"),
        ],
    },
}

NOISE_TEMPLATES: List[Dict[str, str]] = [
    ("极地", "极地科考站的太阳能板除冰有哪些办法？"),
    ("粤语", "粤语九声调的辨析教学该怎么做？"),
    ("热泉", "深海热泉管虫的共生机制是什么？"),
    ("弗拉门戈", "古典吉他弗拉门戈轮指的练习顺序怎么安排？"),
    ("青稞", "高原青稞仓储防霉的常规做法有哪些？"),
    ("斯瓦希里", "斯瓦希里语字母转写的规则复杂吗？"),
    ("潮间带", "潮间带贝类的采集与保存规范是什么？"),
    ("窑变", "建窑瓷器窑变釉色的成因如何解释？"),
    ("苔藓显微", "苔藓叶片显微制片的步骤有哪些？"),
    ("榫卯", "传统木作榫卯的常见类型有哪些？"),
    ("冰川年层", "冰川年层测年法的适用条件是什么？"),
    ("方言岛", "方言岛现象的形成条件有哪些？"),
    ("盐沼", "盐沼植被的耐盐机制有哪些？"),
    ("古籍版本", "古籍版本鉴定看哪些要素？"),
    ("珊瑚白化", "珊瑚白化与海水升温的关系是什么？"),
    ("民歌调式", "西北民歌的调式特征有哪些？"),
    ("陶器渗碳", "史前陶器渗碳工艺怎么做？"),
    ("苔原冻土", "苔原冻土解冻对植被的影响有哪些？"),
    ("琵琶轮指", "琵琶轮指的速度训练怎么安排？"),
    ("织锦纬线", "织锦纬线密度如何影响图案？"),
    ("方言连读", "方言连读变调的基本规律是什么？"),
    ("潮汐能", "潮汐发电站的选址条件有哪些？"),
    ("苔藓分类", "苔藓分类常用哪些形态特征？"),
    ("冰芯气泡", "冰芯气泡如何反映古大气？"),
    ("潮滩蟹洞", "潮滩蟹洞对沉积物结构有什么影响？"),
    ("皮影影偶", "皮影影偶的选皮与上色工序有哪些？"),
    ("冻融循环", "冻融循环对路基稳定性的影响如何评估？"),
    ("茶马古道", "茶马古道的驿传制度怎么运转？"),
    ("盐湖结晶", "盐湖结晶分层的取样方法是什么？"),
    ("织机提花", "提花织机的纹版如何编排？"),
    ("海雾观测", "海雾能见度的观测规范是什么？"),
    ("木版水印", "木版水印的套色顺序怎么定？"),
    ("土壤剖面", "土壤剖面描述记录哪些层位特征？"),
    ("船歌号子", "船工号子的节奏与劳动强度如何配合？"),
    ("蜂群分蜂", "蜂群自然分蜂的征兆有哪些？"),
    ("古桥拱券", "石拱桥拱券的砌筑方法有哪些？"),
    ("雾凇观测", "雾凇形成的气象条件如何记录？"),
    ("竹编收口", "竹编收口的常见编法有哪些？"),
    ("雪线调查", "雪线高度的野外调查步骤是什么？"),
    ("古琴减字", "古琴减字谱如何转成简谱？"),
]

FALSIFY_SIGNALS_CN = ["新结论", "改为", "不再", "无效", "取代", "证伪", "替换", "其实", "没能", "不再适用"]

# 骨架形状：每棵树按 seed 决定；决定链深与子树规模，从而决定可出题量
SKELETONS = ["chain", "fork", "fan", "merge"]


def node_text(title: str, pre: str, beh: str, con: str) -> str:
    return f"【前因】{pre}\n【行为】{beh}\n【后果】{con}"


def make_step_node(tree_key: str, idx: int, prev_id: str,
                   step: tuple, rng: random.Random) -> Dict[str, Any]:
    title, pre, beh, con = step
    nid = f"snt{tree_key}{idx:04d}"
    node: Dict[str, Any] = {
        "id": nid,
        "parent_id": prev_id,
        "tree": tree_key,
        "title": title,
        "content": node_text(title, pre, beh, con),
        "tags": [TREE_THEMES[tree_key]["chain"], TREE_THEMES[tree_key]["tag"]],
    }
    return node


def gen_tree(tree_key: str, seed: int, rng: random.Random,
             branch_quota: tuple = (3, 3, 3),
             force_sup: int = 0, sub_depth: int = 0) -> Dict[str, Any]:
    theme = TREE_THEMES[tree_key]
    steps = theme["steps"]
    sibling_pool = list(theme["sibling"])
    fix_pool = list(theme["fix"])
    pitfall_pool = list(theme["pitfall"])
    rng.shuffle(sibling_pool)
    rng.shuffle(fix_pool)
    rng.shuffle(pitfall_pool)

    skeleton = SKELETONS[seed % len(SKELETONS)]

    nodes: List[Dict[str, Any]] = []
    actions: Dict[str, Dict[str, str]] = {}
    nid = 0
    chain_ids: List[str] = []

    def new_id() -> str:
        nonlocal nid
        nid += 1
        return f"snt{tree_key}{nid:04d}"

    # 主链：全部 steps 节点串成一条因果链
    prev = ""
    step_ids: List[str] = []
    for st in steps:
        cur = new_id()
        node = make_step_node(tree_key, nid, prev, st, rng)
        node["id"] = cur
        # action_key/outcome 由 seed 决定种在哪些主链节点上
        r = rng.random()
        if r < 0.45:
            key = f"act_{tree_key.lower()}{len(actions) + 1:02d}"
            desc = st[1] if len(st) > 1 else st[0]
            actions[key] = {"desc": desc}
            node["action_key"] = key
            node["outcome"] = "pitfall" if r < 0.22 else "normal"
        nodes.append(node)
        chain_ids.append(cur)
        step_ids.append(cur)
        prev = cur

    # 分支节点：挂在主链的哪些位置由骨架决定（chain/fork/fan/merge 只改挂点分布，
    # 不改确定性：形状由 seed 固定）
    n_steps = len(step_ids)
    if skeleton == "chain":
        # 深链优先：分支全挂到链尾附近，链更深
        branch_positions = [step_ids[-1], step_ids[-2], step_ids[-3], step_ids[-4]]
    elif skeleton == "fork":
        branch_positions = [step_ids[0], step_ids[1], step_ids[-1], step_ids[-2]]
    elif skeleton == "fan":
        # 扇出：每个主链节点都可能是挂点（轮流取）
        branch_positions = [step_ids[i % n_steps] for i in range(6)]
    else:  # merge：挂点集中在中段
        mid = n_steps // 2
        branch_positions = [step_ids[mid], step_ids[mid + 1], step_ids[mid - 1], step_ids[0]]
    branch_positions = [p for i, p in enumerate(branch_positions) if p]
    n_sibling = min(branch_quota[0], len(sibling_pool))
    n_fix = min(branch_quota[1], len(fix_pool))
    n_pitfall = min(branch_quota[2], len(pitfall_pool))
    branches = (
        [("sibling", sibling_pool[i]) for i in range(n_sibling)]
        + [("fix", fix_pool[i]) for i in range(n_fix)]
        + [("pitfall", pitfall_pool[i]) for i in range(n_pitfall)]
    )
    # seed 决定分支挂接顺序（打乱 positions 使用顺序）
    order = list(range(len(branch_positions)))
    rng.shuffle(order)

    for bi, (kind, spec) in enumerate(branches):
        title, pre, beh, con = spec
        cur = new_id()
        parent = branch_positions[order[bi % len(order)]]
        node: Dict[str, Any] = {
            "id": cur,
            "parent_id": parent,
            "tree": tree_key,
            "title": title,
            "content": node_text(title, pre, beh, con),
            "tags": [theme["chain"], theme["tag"]],
        }
        if kind in ("pitfall", "fix"):
            key = f"act_{tree_key.lower()}{len(actions) + 1:02d}"
            actions[key] = {"desc": beh}
            node["action_key"] = key
            node["outcome"] = "pitfall" if kind == "pitfall" else "normal"
        nodes.append(node)
        # 扩集：词库只有 3 条/类，一级分支挂满后在其下再挂确定性子节点，
        # 让链更深、desc>=1 的节点变多。默认 sub_depth=0，既有 tree.json 不受影响。
        anchor = cur
        for depth_i in range(sub_depth):
            child = new_id()
            child_node: Dict[str, Any] = {
                "id": child,
                "parent_id": anchor,
                "tree": tree_key,
                "title": f"{title}·后续{depth_i + 1}",
                "content": node_text(
                    f"{title}·后续{depth_i + 1}",
                    f"{title} 之后继续排查",
                    f"按同一口径做第 {depth_i + 1} 步跟进",
                    "跟进记录写入复盘",
                ),
                "tags": [theme["chain"], theme["tag"]],
            }
            r = rng.random()
            if r < 0.45:
                key = f"act_{tree_key.lower()}{len(actions) + 1:02d}"
                actions[key] = {"desc": f"按同一口径做第 {depth_i + 1} 步跟进"}
                child_node["action_key"] = key
                child_node["outcome"] = "pitfall" if r < 0.22 else "normal"
            nodes.append(child_node)
            anchor = child

    # 软取代：每棵树至少种 1 对；若分支节点够多再种第 2 对（主链另一旧结论 → 另一 fix）
    sup_pairs: List[Dict[str, str]] = []
    tree_by_id = {n["id"]: n for n in nodes}

    def is_descendant(candidate: str, ancestor: str) -> bool:
        cur = tree_by_id[candidate].get("parent_id", "")
        while cur:
            if cur == ancestor:
                return True
            cur = tree_by_id[cur].get("parent_id", "")
        return False

    fix_nodes = sorted(
        (n for n in nodes
         if any(w in n["title"] + n["content"] for w in FALSIFY_SIGNALS_CN)
         and n["id"] not in chain_ids),
        key=lambda n: n["id"],
    )
    chain_mid = [c for c in chain_ids if len(chain_ids) >= 6]
    used_new: set = set()
    n_sup_target = 2 if len(fix_nodes) >= 2 else 1
    for old in (chain_ids[len(chain_ids) // 2 - 1], chain_ids[1]):
        if len(sup_pairs) >= n_sup_target:
            break
        if old not in tree_by_id:
            continue
        cands = [n for n in fix_nodes
                 if n["id"] not in used_new and is_descendant(n["id"], old)]
        if not cands:
            continue
        new_node = cands[0]
        used_new.add(new_node["id"])
        tree_by_id[old]["superseded_by"] = new_node["id"]
        new_node.setdefault("supersedes", old)
        if not any(w in new_node["title"] + new_node["content"] for w in FALSIFY_SIGNALS_CN):
            raise SystemExit(f"{tree_key}: 新结论 {new_node['id']} 未命中证伪信号词表")
        sup_pairs.append({"old": old, "new": new_node["id"]})
    if not sup_pairs:
        # 兜底：主链中段旧结论 → 挂一个新结论节点（保证每棵树至少 1 对取代）
        old = chain_ids[len(chain_ids) // 2 - 1]
        cur = new_id()
        new_node = {
            "id": cur,
            "parent_id": old,
            "tree": tree_key,
            "title": "新结论：按复盘口径修正此前判断",
            "content": node_text("新结论", "复盘推翻了此前判断", "改为按新口径执行", "旧结论不再适用"),
            "tags": [theme["chain"], "结论"],
        }
        nodes.append(new_node)
        tree_by_id[cur] = new_node
        tree_by_id[old]["superseded_by"] = cur
        new_node["supersedes"] = old
        sup_pairs.append({"old": old, "new": cur})

    # 扩集：确定性补足取代对数（每棵树 force_sup 对，取尚未使用的链节点）
    used_old = {p["old"] for p in sup_pairs}
    fill_i = 0
    # 自然逻辑可能把两条边挂在同一个旧节点上；按「不同旧节点」计数补齐。
    while force_sup and len({p["old"] for p in sup_pairs}) < force_sup:
        cands = [c for c in chain_ids if c not in used_old]
        if not cands:
            raise SystemExit(f"{tree_key}: 链节点不足以补足 {force_sup} 对取代")
        old = cands[0]
        fill_i += 1
        cur = new_id()
        new_node = {
            "id": cur,
            "parent_id": old,
            "tree": tree_key,
            "title": "新结论：复盘后改为按新口径执行",
            "content": node_text("新结论", "复盘推翻了此前判断", "改为按新口径执行", "旧结论不再适用"),
            "tags": [theme["chain"], "结论"],
        }
        nodes.append(new_node)
        tree_by_id[cur] = new_node
        tree_by_id[old]["superseded_by"] = cur
        new_node["supersedes"] = old
        used_old.add(old)
        sup_pairs.append({"old": old, "new": cur})

    return {
        "tree": tree_key,
        "skeleton": skeleton,
        "nodes": nodes,
        "actions": actions,
        "supersession_pairs": sup_pairs,
    }


def build(seed: int, branch_quota: tuple = (3, 3, 3), force_sup: int = 0,
          noise_limit: int = 24, sub_depth: int = 0) -> Dict[str, Any]:
    rng = random.Random(seed)
    keys = sorted(TREE_THEMES.keys())
    trees: List[Dict[str, Any]] = []
    for k in keys:
        trees.append(gen_tree(k, seed + ord(k), rng, branch_quota, force_sup, sub_depth))

    nodes: List[Dict[str, Any]] = []
    actions: Dict[str, Dict[str, str]] = {}
    sup_pairs: List[Dict[str, str]] = []
    for t in trees:
        nodes.extend(t["nodes"])
        actions.update(t["actions"])
        sup_pairs.extend(t["supersession_pairs"])

    # noise：取前 24 条模板，keyword 与全树正文互斥（断言）
    blob = "\n".join(n["title"] + "\n" + n["content"] for n in nodes)
    noise_queries = []
    for i, (kw, q) in enumerate(NOISE_TEMPLATES[:noise_limit]):
        if kw in blob:
            raise SystemExit(f"脱敏/负样本自检失败：keyword {kw} 出现在树内")
        noise_queries.append({"key": f"noise-{i:02d}", "keyword": kw, "query": q})

    tree_doc: Dict[str, Any] = {
        "version": "0.2",
        "synthetic": True,
        "seed": seed,
        "generator": "gen_tree.py",
        "note": (
            "全合成脱敏因果树（seed 确定性生成）：仅用于 agimem 造题。无真人姓名、"
            "无真库 id（id 形如 sntXnnnn 为本基准自造 8 位短 id）、无凭据、无真实项目名。"
            "节点三段式 content 遵循 respire 【前因】【行为】【后果】。"
        ),
        "actions": actions,
        "noise_queries": noise_queries,
        "nodes": nodes,
    }
    return tree_doc


def verify_existing(seed: int, path: str, branch_quota: tuple = (3, 3, 3),
                    force_sup: int = 0, noise_limit: int = 24,
                    sub_depth: int = 0) -> int:
    with open(path, encoding="utf-8") as f:
        existing = json.load(f)
    fresh = build(seed, branch_quota, force_sup, noise_limit, sub_depth)
    # 逐节点比对 id/parent/content；action/outcome/superseded_by 也比
    def key(n: Dict[str, Any]) -> str:
        return n["id"]
    e_nodes = {key(n): n for n in existing["nodes"]}
    f_nodes = {key(n): n for n in fresh["nodes"]}
    diffs: List[str] = []
    if set(e_nodes) != set(f_nodes):
        only_e = sorted(set(e_nodes) - set(f_nodes))
        only_f = sorted(set(f_nodes) - set(e_nodes))
        diffs.append(f"节点集合不同: 仅既有={only_e[:5]} 仅新生成={only_f[:5]}")
    for nid in sorted(set(e_nodes) & set(f_nodes)):
        for field in ("parent_id", "title", "content", "action_key", "outcome",
                      "superseded_by", "supersedes"):
            ev = e_nodes[nid].get(field)
            fv = f_nodes[nid].get(field)
            if ev != fv:
                diffs.append(f"{nid}.{field}: 既有={ev!r} 新生成={fv!r}")
    if existing.get("actions") != fresh.get("actions"):
        diffs.append("actions 字典不一致")
    if [q["query"] for q in existing.get("noise_queries", [])] != \
       [q["query"] for q in fresh["noise_queries"]]:
        diffs.append("noise_queries 不一致")
    if diffs:
        print(f"[verify] FAIL — seed={seed} 重生成与 {path} 不一致：")
        for d in diffs[:20]:
            print("  - " + d)
        return 1
    print(f"[verify] OK — seed={seed} 重生成与 {path} 内容一致（{len(f_nodes)} 节点）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="确定性 seed 扩树")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--out", default=os.path.join(HERE, "data", "tree.json"))
    ap.add_argument("--verify", action="store_true",
                    help="不写文件，只验证既有 tree 与 seed 重生成一致")
    ap.add_argument("--branches", type=int, default=9,
                    help="每棵树分支数（默认 9 = 3+3+3，与既有 tree.json 同构）")
    ap.add_argument("--sup-pairs", type=int, default=0,
                    help="每棵树强制取代对数（0 = 沿用既有逻辑）")
    ap.add_argument("--noise", type=int, default=24, help="噪声查询条数上限")
    ap.add_argument("--sub-depth", type=int, default=0,
                    help="每个一级分支再向下挂几层子节点（默认 0，与既有树同构）")
    args = ap.parse_args()
    q = args.branches // 3
    branch_quota = (q + args.branches % 3, q, q)

    if args.verify:
        return verify_existing(args.seed, args.out, branch_quota, args.sup_pairs,
                               args.noise, args.sub_depth)

    tree_doc = build(args.seed, branch_quota, args.sup_pairs, args.noise, args.sub_depth)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(tree_doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    n = len(tree_doc["nodes"])
    n_sup = sum(1 for x in tree_doc["nodes"] if x.get("superseded_by"))
    n_pit = sum(1 for x in tree_doc["nodes"] if x.get("outcome") == "pitfall")
    print(f"[gen_tree] 写出 {args.out}: seed={args.seed} 树数={len(TREE_THEMES)} "
          f"节点={n} 动作={len(tree_doc['actions'])} 踩坑={n_pit} 取代对={n_sup} "
          f"噪声查询={len(tree_doc['noise_queries'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

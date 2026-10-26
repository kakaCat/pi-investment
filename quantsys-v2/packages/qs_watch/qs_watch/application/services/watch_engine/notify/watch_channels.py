"""盯盘闭环的真实通知通道（REQ-c9f899 t12，2026-09-18）

把心跳告警与三段回执接到 NotificationFacade（飞书）——此前 t10/t6 的 sender 默认
log-only，告警只在日志里、人看不到（§6 待接线项 6/10）。

纪律（对齐 pi-investment/CLAUDE.md 通知架构铁律）：
  · 只经 qs_notification.application.get_notification_facade()；禁止直接 import
    qs_notification.infrastructure.channels.*，禁止 requests.post(飞书 webhook)。
  · 发送失败必须抛错，不许静默返回 False：run_heartbeat_check 用 sender 是否抛错
    统计 sent；ReceiptService 用 sender 是否抛错 决定 delivery_status=sent/failed。
    若这里吞掉失败返回 False，回执会被记成 sent（假成功），心跳会把失败当成已送达。

路由（REQ-260924104605-ad0a t3，FR-3）：回执/告警经 facade.send_watch_receipt 携带
os_channel（逻辑频道码）——timeout/P0 → risk_stop，其余 → watch_symbol；AgentChannel
把它转发给 Agent OS 网关，按 notification_channels 表投递到盯盘群（FR-1 已配置
10 个盯盘频道指向专用 webhook）；Agent OS 不可达时降级直飞书兜底（不丢消息）。
卡片正文**不再外露频道码**（FR-12：「频道：」属内部字段）。
"""
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)

#: 回执类型 → 卡片标题（三种回执 + 抑噪 + 观察聚合，R5 / REQ-261016155500-4f2a wt:validate:1）
_KIND_LABELS = {
    'escalate': '升级即回执',
    'result': '处置后回执',
    'timeout': '超时回执',
    'suppressed': '抑噪回执',
    'observe_digest': '观察聚合',
    'daily_review': '体检日报',
    'news_alert': '消息监控',
}

#: 待办送达处置 agent 的 wake 事件名（2026-10-16，补「待办 → owner agent」缺环）。
#: agent-dh 的 /wake 只要求 event 非空（wake-webhook.ts:112），事件数据自带 instruction。
WAKE_EVENT_TODO_ASSIGNED = 'watch_todo_assigned'
WAKE_EVENT_TODO_TIMEOUT = 'watch_todo_timeout'

#: 待办处置指引（随 wake 下发；正文与 API 契约同源，见 watch_todo_async.close_todo）
_CLOSE_GUIDE = (
    '处置并收敛该待办：①先落决策审计（rule_change/trade 等动作必须留痕）拿到 decision_audit_id；'
    '②POST /api/watch/todos/{todo_id}/close，body 至少含 terminal=handled|ignored、close_reason、'
    'action_kind；terminal=ignored 必须带 next_condition（下次什么条件下才动）；'
    'flow_state=L3 且 action_kind ∈ (trade, rule_change) 时必须带 decision_audit_id。'
    '判不动就 ignored + NEXT 条件，别让它挂着。'
)


def send_watch_alert(text: str) -> bool:
    """心跳/影子超期告警的真实投递（供 run_heartbeat_check 的 sender 参数）。

    run_heartbeat_check 传入的是「标题 | 原因」；按首个竖线拆标题与正文。
    失败抛错（run_heartbeat_check 会如实记 sent=0），绝不假装已发。
    """
    from qs_notification.application import get_notification_facade

    raw = str(text or "").strip()
    title, _, body = raw.partition("|")
    title = (title.strip() or "【盯盘引擎】告警")
    content = (body.strip() or title)
    ok = get_notification_facade().send_watch_receipt(
        title=title, content=content, os_channel='watch_symbol', urgency='high')
    if not ok:
        raise RuntimeError('盯盘告警未送达（agent→feishu 双路失败）')
    return True


def send_watch_receipt(payload: Dict[str, Any]) -> bool:
    """三段回执的真实投递（供 ReceiptService 的 sender 参数）。

    payload 由 ReceiptService._deliver 构造：todo_id/kind/channel/period/message/level。
    REQ-ad0a t3（FR-3）：os_channel 逻辑频道码直透 AgentChannel ——
    timeout/P0 → risk_stop（盯盘群内高优位），其余 → watch_symbol；
    失败抛错 → delivery_status=failed（如实）。
    """
    from qs_notification.application import get_notification_facade

    data = payload or {}
    kind = str(data.get('kind') or '').strip().lower()
    level = str(data.get('level') or '').strip().upper()
    channel = str(data.get('channel') or '').strip()
    message = str(data.get('message') or '').strip()
    # 聚合卡（t4 flush_grouped）以 items 多条传入：os_channel 由调用方显式给出
    os_channel = str(data.get('os_channel') or '').strip()
    if not os_channel:
        os_channel = ('risk_stop' if (kind == 'timeout' or level == 'P0')
                      else 'watch_symbol')
    title = '📋 盯盘回执 · %s' % _KIND_LABELS.get(kind, kind or '-')
    # FR-12：频道码不外露（内部字段不进用户视野）
    content = message or "(无正文)"
    # urgency 只看语义字段（timeout/P0 高优）；不再依赖 payload.channel 旧标签
    # （REQ-ad0a t7 起落库标签已改为真实盯盘频道码 risk_stop/watch_symbol）
    urgency = 'high' if (kind == 'timeout' or level == 'P0') else 'normal'
    ok = get_notification_facade().send_watch_receipt(
        title=title, content=content, os_channel=os_channel, urgency=urgency)
    if not ok:
        raise RuntimeError('盯盘回执未送达（agent→feishu 双路失败）')
    return True


# ── 待办 → owner agent（2026-10-16 补缺环）────────────────────────────────
# 事故背景：规则自愈/元评审/补全指引派出的修规则待办**只落库**——三个派单服务都不发
# 通知，agent 的摘要唤醒也只吃 watch_triggers（digest_service.py:90），待办表不在其中。
# 于是工单挂在 L3 无人知晓，唯一在动的出口是"超时回执发给你"，30 分钟一张。
# 本组函数把工单真正派出去：建单即唤醒 owner（wake_todo_assignment），
# L3 超时再催一次（wake_todo_owner，作为 ReceiptService 的 agent_waker）。
# 纪律不变：只经 facade；未送达**绝不假装已发**，P0/P1 退回盯盘群卡片兜底。

def _todo_wake_data(todo: Any, *, event: str,
                    message: Optional[str] = None) -> Dict[str, Any]:
    """待办 → wake 载荷（纯构造，不发送）。

    自带 instruction（agent-dh 的 deliverWake 会把 JSON 原样交给 agent，见
    agent-dh/packages/tools/lifecycle/src/index.ts deliverWake）；missing 字段如实缺省，
    不臆造（如名称解析未接线时不编名字）。

    RFC 017 §2.1.2（卡 `exec-directive-card`）：P0 执行指令作为 **additive** 字段
    `exec_directive` 随 wake 下发——待办由流水线 `TodoStage` 挂同一份指令对象
    （`todo.exec_directive`），agent 不看通知卡也能拿到结构化动作。
    **没有指令时载荷逐字不变**（非退出类 P0 / 闭环未装配 / 旧调用方）：不塞 None，
    也不改任何既有键，回归口径是「set(keys) 相同」。
    """
    due = getattr(todo, 'due_at', None)
    due_text = due.isoformat() if hasattr(due, 'isoformat') else str(due or '')
    todo_id = getattr(todo, 'id', None)
    data = {
        'event': event,
        'todo_id': todo_id,
        'symbol': getattr(todo, 'symbol', None),
        'level': getattr(todo, 'level', None),
        'flow_state': getattr(todo, 'flow_state', None),
        'action_kind': getattr(todo, 'action_kind', None),
        'rule_id': getattr(todo, 'rule_id', None),
        'account': getattr(todo, 'account', None),
        'owner_kind': getattr(todo, 'owner_kind', None),
        'owner_ref': getattr(todo, 'owner_ref', None),
        'autonomy': getattr(todo, 'autonomy', None),
        'escalate_count': getattr(todo, 'escalate_count', None),
        'due_at': due_text,
        'created_at': (getattr(todo, 'created_at', None).isoformat()
                       if hasattr(getattr(todo, 'created_at', None), 'isoformat') else None),
        'message': message,
        'instruction': _CLOSE_GUIDE.replace('{todo_id}', str(todo_id)),
    }
    # getattr 兜底：旧待办对象/ORM 行没有该属性、或闭环未装配（None）→ 不新增键
    directive = getattr(todo, 'exec_directive', None)
    if directive is not None:
        data['exec_directive'] = (directive.to_dict()
                                  if hasattr(directive, 'to_dict') else directive)
    return data


def _wake_deliver(event: str, data: Dict[str, Any], target_agent: Optional[str] = None) -> bool:
    """任务唤醒投递（2026-10-21 唤醒链修复）。

    直连 POST /wake（AgentNotificationService，digest 同款已验证链路）为**主路**——
    facade 的 agent 通道经 Agent OS 中转，对「任务投递」是哑管道：Agent OS 签收后
    只 relay 飞书，agent-dh 永远收不到作业（2026-10-20 晚 sweep 未动工的根因，
    已在 reqboard 登记）。直连失败才回退 facade（双保险，绝不让事件静默丢失）。
    """
    try:
        from qs_agenthub.application.services.agent_notification_service import (
            AgentNotificationService,
        )
        if AgentNotificationService().notify_agent(event, data, target=target_agent):
            return True
        logger.warning('直连 /wake 未确认（回退 facade）', wake_event=event)
    except Exception as e:  # noqa: BLE001
        logger.warning('直连 /wake 投递异常（回退 facade）', wake_event=event, error=str(e))
    try:
        from qs_notification.application import get_notification_facade
        status = get_notification_facade().wake_agent(event, data, target_agent=target_agent)
        return status == 'ok'
    except Exception as e:  # noqa: BLE001
        logger.error('facade 回退投递也失败', wake_event=event, error=str(e))
        return False


def wake_todo_assignment(todo: Any) -> bool:
    """建单即把待办派给 owner agent（TodoService 的 assigner 实现）。

    返回 True=已送达（wake ok）；False=未送达（不回退卡片：建单阶段没有面向用户的
    文案，工单仍会在超时升级时兜底）。**不抛错**——派单失败绝不能打挂建单。
    """
    from qs_notification.application import get_notification_facade

    owner_ref = str(getattr(todo, 'owner_ref', '') or '').strip() or None
    data = _todo_wake_data(todo, event=WAKE_EVENT_TODO_ASSIGNED)
    ok = _wake_deliver(WAKE_EVENT_TODO_ASSIGNED, data, target_agent=owner_ref)
    if ok:
        logger.info('待办已派给 owner agent（wake 送达）',
                    todo_id=getattr(todo, 'id', None), owner_ref=owner_ref,
                    wake_event=WAKE_EVENT_TODO_ASSIGNED)
    else:
        logger.warning('待办派单未送达（工单已落库，靠超时升级兜底）',
                       todo_id=getattr(todo, 'id', None), owner_ref=owner_ref)
    return ok


def wake_todo_owner(todo: Any, context: Optional[Dict[str, Any]] = None) -> bool:
    """ReceiptService 的 agent_waker：L3 超时的 agent 自有待办 → 唤醒 owner 而不是用户。

    先 wake owner（event=watch_todo_timeout）；非 'ok' 时对 P0/P1 **退回盯盘群卡片**
    （与 L2 目标路由同一纪律：绝不静默丢事件），退回也不成功则返回 False 让回执如实
    记 failed。P2/P3 不退回卡片（级别策略本就是"只落台账不打扰用户"），返回 False。

    context['allow_card_fallback']=False（聚合轮内）：除再催轮外，本函数**不自行发卡**，
    只返回 False，由 flush_grouped 把这条折进本轮同一张卡——否则 agent 离线时会按条炸出
    N 张卡（2026-10-16 生产实测：一轮 10 张）。再催轮（force_user_card=True）即使
    wake 已送达，也直接补发用户超时卡——wake=ok 不代表 agent 已完成关闭。

    agent_waker 契约（ReceiptService._wake_owner）：返回 True=sent / False=failed，
    异常向上抛由调用方记 failed。
    """
    from qs_notification.application import get_notification_facade

    ctx = context or {}
    level = str(getattr(todo, 'level', '') or '').strip().upper()
    owner_ref = str(getattr(todo, 'owner_ref', '') or '').strip() or None
    data = _todo_wake_data(todo, event=WAKE_EVENT_TODO_TIMEOUT,
                           message=ctx.get('message'))
    if _wake_deliver(WAKE_EVENT_TODO_TIMEOUT, data, target_agent=owner_ref):
        logger.info('待办超时已唤醒 owner agent',
                    todo_id=getattr(todo, 'id', None), owner_ref=owner_ref,
                    wake_event=WAKE_EVENT_TODO_TIMEOUT)
        if ctx.get('force_user_card') and level in ('P0', 'P1'):
            logger.warning('待办再催仍未关闭，已唤醒 owner 后仍补发用户超时卡',
                           todo_id=getattr(todo, 'id', None), owner_ref=owner_ref)
            try:
                return send_watch_receipt({
                    'kind': 'timeout', 'channel': ctx.get('channel') or 'risk_stop',
                    'message': ctx.get('message') or '', 'level': level,
                })
            except Exception as e:  # noqa: BLE001 - 补发失败 → False，回执记 failed
                logger.error('待办再催补发用户卡失败（回执将记 failed）',
                             todo_id=getattr(todo, 'id', None), error=str(e))
                return False
        return True

    if not ctx.get('allow_card_fallback', True):
        logger.warning('待办超时唤醒未送达（聚合轮内：交回执折进本轮同一张卡）',
                       todo_id=getattr(todo, 'id', None), owner_ref=owner_ref)
        return False

    if level in ('P0', 'P1'):
        logger.warning('待办超时唤醒未送达，退回盯盘群卡片（绝不静默丢）',
                       todo_id=getattr(todo, 'id', None), owner_ref=owner_ref)
        try:
            return send_watch_receipt({
                'kind': 'timeout', 'channel': ctx.get('channel') or 'risk_stop',
                'message': ctx.get('message') or '', 'level': level,
            })
        except Exception as e:  # noqa: BLE001 - 兜底也失败 → False，回执记 failed
            logger.error('待办超时退回卡片也失败（回执将记 failed）',
                         todo_id=getattr(todo, 'id', None), error=str(e))
            return False
    logger.warning('待办超时唤醒未送达且级别不退回卡片（P2/P3 只落台账）',
                   todo_id=getattr(todo, 'id', None), owner_ref=owner_ref)
    return False

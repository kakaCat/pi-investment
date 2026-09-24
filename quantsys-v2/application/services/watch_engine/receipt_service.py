"""盯盘回执应用服务（REQ-c9f899 t6，2026-09-18）

闭环三段回执（R5 / 成功标准 8；data-model.md §5）的落点：

  · escalate（升级即） —— 待办晋升 L1→L2 / L2→L3 时发：已交 agent / 已通知你 + SLA；
  · result  （处置后） —— 待办收敛为终态时发：结论 + 动作（或"不动 + NEXT 条件"）；
  · timeout （超时）   —— L3 仍超时未收敛时发：升级给你本人。

**幂等是第一性约束**：同一 (todo_id, kind, payload_digest) 只落一条、只发一次。
payload_digest 是渲染输入摘要（见 payload_digest()），period 携带该待办的 due 周期
（due_at）与该段的标记——因此"同一待办同一 due 周期"重复巡检为 no-op，
而 L1→L2 与 L2→L3 是两条不同回执（period 里带 to_state）。

**发送通道可注入、默认 log-only（诚实边界）**：真实通道接线归 t12。未接线时只写
logger.warning 并把 delivery_status 记为 log_only——**绝不写成 sent**（不许假装已发）。
sender 抛错也不打断巡检：如实记 delivery_status=failed 并返回 sent=False，由调用方
决定是否重试（t12 的通道装配负责重试策略）。

分层纪律（architecture.md §2）：本服务只做编排 + 幂等，不判定级别、不决定晋升
（晋升是 WatchSlaJob 的机械动作）、不碰 SQL（仓储端口）。
"""
import hashlib
import json
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import structlog

from domain.watch.ports import RECEIPT_KINDS

logger = structlog.get_logger(__name__)

#: delivery_status 取值。data-model §5 列了 sent/failed；**log_only 是诚实第三态**——
#: 真实通道未接线时"只记了日志、没有送达"，把它写成 sent 就是假成功。
#: watch_receipts.delivery_status 列无 CHECK 约束（migration 20260918），故该扩展安全；
#: t12 接上真实通道后只会产出 sent/failed。
DELIVERY_SENT = 'sent'
DELIVERY_FAILED = 'failed'
DELIVERY_LOG_ONLY = 'log_only'

#: 回执逻辑频道码（与 notification 渠道路由同口径：high→alerts / normal→reports）
CHANNEL_ALERTS = 'alerts'
CHANNEL_REPORTS = 'reports'

#: 发送方签名：sender(payload: dict) -> None。payload 携带 todo_id/kind/channel/level/
#: symbol/message/period，供 t12 用 NotificationFacade 按级别选模板（P0 红卡等）。
Sender = Callable[[Dict[str, Any]], None]

#: 聚合投递的回执类型（REQ-260924104605-ad0a t4，FR-8）：巡检一轮（begin_group →
#: flush_grouped）内同 kind 合成**一张卡**；result/suppressed 不在其列——处置结论
#: 必须即时到达（FR-14），不参与聚合。
AGGREGATE_KINDS = ('escalate', 'timeout')


def resolve_channel(level: Any, kind: Any) -> str:
    """级别 × 回执类型 → 逻辑频道码（纯函数）。

    超时回执是"升级给你本人"，一律走 alerts；P0 也走 alerts；其余（P1–P3 的升级即/
    处置后回执）走 reports——与 feishu_notify 的 urgency→channel 分流同口径。
    """
    if str(kind or '').strip().lower() == 'timeout':
        return CHANNEL_ALERTS
    return CHANNEL_ALERTS if str(level or '').strip().upper() == 'P0' else CHANNEL_REPORTS


def payload_digest(kind: Any, todo_id: Any, period: Any) -> str:
    """渲染输入摘要（幂等去重键）——纯函数，稳定可复现。

    为什么必须确定性：巡检每分钟跑一次，若摘要随调用变化，同一 due 周期就会反复发送。
    period 由调用方按段构造（回执种类 + 该待办的 due_at），因此：
      · 同一待办同一 due 周期的同一条回执 → 同一 digest → 只落一条、只发一次；
      · 同周期内的 L1→L2 与 L2→L3 是两条不同升级回执 → period 不同 → digest 不同。
    """
    raw = json.dumps(
        {
            'kind': str(kind or '').strip().lower(),
            'todo_id': int(todo_id),
            'period': str(period or ''),
        },
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def receipt_period(todo: Any, tag: Any = '') -> str:
    """回执归属的"due 周期"标记：<tag>|<due_at ISO>。

    due_at 是待办这一轮 SLA 的到期基准，也是"同一 due 周期"的天然边界；
    tag 区分同周期内的不同段（升级目标态 L2/L3、终态 handled/…）。due_at 缺失时退回
    todo id 之外的稳定串——绝不返回空（空 period 会让不同待办撞同一 digest）。
    """
    due = getattr(todo, 'due_at', None)
    due_text = due.isoformat() if hasattr(due, 'isoformat') else str(due or '')
    return f'{str(tag or "")}|{due_text}'


def _fmt_due(due: Any) -> str:
    """截止时间（无微秒）：'MM-DD HH:MM'；缺失/非时间 → ''（FR-11：不再 ISO 微秒）。"""
    if hasattr(due, 'strftime'):
        return due.strftime('%m-%d %H:%M')
    return ''


def _humanize_overdue(due: Any, now: Optional[datetime] = None) -> Optional[str]:
    """已超时时长人性化：'2h14m' / '47m'；未超时或无法计算 → None（FR-11）。"""
    if not hasattr(due, 'isoformat'):
        return None
    try:
        at = now or (datetime.now(due.tzinfo) if getattr(due, 'tzinfo', None)
                     else datetime.now())
        seconds = int((at - due).total_seconds())
    except (TypeError, ValueError):
        return None
    if seconds <= 0:
        return None
    hours, minutes = divmod(seconds // 60, 60)
    return f'{hours}h{minutes}m' if hours else f'{minutes}m'


def render_receipt(todo: Any, *, kind: str, period: str,
                   name: Optional[str] = None,
                   close_reason: Optional[str] = None,
                   next_condition: Optional[str] = None,
                   action_kind: Optional[str] = None,
                   now: Optional[datetime] = None,
                   in_group: bool = False) -> str:
    """回执文案（纯函数，只认结构化字段，禁止在调用点拼串）

    REQ-ad0a t4（FR-11/FR-13）：
      · 时间人性化、**无微秒**（已超时 2h14m（截止 09-24 10:00）），due 只出现一次；
      · 「周期 period」不再外露（period 只用于 digest 幂等键，不是给用户看的）；
      · 名称在前「名称（代码）」，缺失如实降级「（名称缺失）」（R-013 不臆造）；
      · in_group=True 时返回**无 [类型] 前缀的一行形态**（聚合卡逐行拼接用）；
      · close_reason/next_condition/action_kind 由 t5 的 result 三要素文案消费。
    """
    todo_id = getattr(todo, 'id', None)
    symbol = getattr(todo, 'symbol', None) or '(未知标的)'
    name_text = str(name or '').strip()
    display = (f'{name_text}（{symbol}）' if name_text
               else (f'{symbol}（名称缺失）' if symbol != '(未知标的)' else symbol))
    level = getattr(todo, 'level', None) or '--'
    flow = getattr(todo, 'flow_state', None) or '--'
    account = getattr(todo, 'account', None) or '通用观察'
    due = getattr(todo, 'due_at', None)
    due_text = _fmt_due(due)
    tag = str(period or '').split('|')[0].strip()

    if kind == 'escalate':
        target = tag or flow
        body = f'待办#{todo_id} {display} {level} · 归属 {account} · 晋升至 {target}'
        if due_text:
            body += f'（截止 {due_text}）'
    elif kind == 'timeout':
        overdue = _humanize_overdue(due, now)
        if overdue:
            due_seg = f'已超时 {overdue}（截止 {due_text}）' if due_text else f'已超时 {overdue}'
        elif due_text:
            due_seg = f'截止 {due_text}'
        else:
            due_seg = '截止时间缺失'
        body = f'待办#{todo_id} {display} {level} · 归属 {account} · {due_seg}'
    elif kind == 'result':
        # REQ-ad0a t5（FR-14）：结论/原因/后续意见三要素——close 时人填的处置结论
        # （终态+动作）、原因（close_reason）、后续意见（ignored 的 NEXT 条件原文）。
        terminal_text = {'handled': '已处置', 'ignored': '忽略', 'expired': '已过期'}.get(
            tag, tag or 'closed')
        action_text = {'trade': '已执行交易', 'rule_change': '已修规则'}.get(
            str(action_kind or '').strip().lower(), '不动')
        reason_text = str(close_reason or '').strip() or '未填原因'
        result_lines = [
            f'待办#{todo_id} {display} {level} · 归属 {account}',
            f'结论：{terminal_text}（{action_text}）',
            f'原因：{reason_text}',
        ]
        next_text = str(next_condition or '').strip()
        if next_text:
            result_lines.append(f'后续意见：NEXT {next_text}')
        elif tag == 'ignored':
            # ignored 按理必有 NEXT（close 校验兜底）；缺失如实标注（不臆造，R-013）
            result_lines.append('后续意见：NEXT 条件缺失（ignored 必填，数据异常）')
        else:
            result_lines.append('后续意见：无')
        body = '\n'.join(result_lines)
    else:
        body = f'待办#{todo_id} {display} {level} · 归属 {account}'
    if in_group:
        return body
    label = {'escalate': '升级即', 'timeout': '超时', 'result': '处置后'}.get(kind, '回执')
    return f'[{label}] {body}'


def render_group_card(kind: Any, items: List[Dict[str, Any]]) -> str:
    """聚合卡正文（纯函数）：标题行 + 每行一条回执（FR-8「一周期一卡」）。

    items 为 flush_grouped 缓冲的条目（message 已是 in_group 一行形态）。
    """
    n = len(items)
    kind_value = str(kind or '').strip().lower()
    if kind_value == 'timeout':
        head = f'⏰ 超时回执 ｜ {n} 项待办超时未处置（请逐项勾选或回复「处置 #待办号」）'
    elif kind_value == 'escalate':
        head = f'🔺 升级即回执 ｜ {n} 项待办已按 SLA 机械晋升'
    else:
        head = f'📋 盯盘回执 ｜ {n} 条'
    lines = [head]
    lines.extend(f'- {it["message"]}' for it in items)
    return '\n'.join(lines)


class ReceiptService:
    """三段回执的编排服务（幂等 + 可注入 sender；仓储由构造注入）

    无状态；不做级别判定、不决定晋升、不碰 SQL。
    """

    def __init__(self, repo: Any, sender: Optional[Sender] = None):
        self._repo = repo
        #: 缺省 None = log-only（真实通道接线归 t12），**不得**在服务内自建飞书通道
        self._sender = sender
        # REQ-ad0a t4（FR-8）聚合投递状态：begin_group 开启一轮 → escalate/timeout
        # 入组不投递 → flush_grouped 按 kind 各发一张聚合卡并逐条落库。
        self._group_open = False
        self._group_buffer: Dict[str, List[Dict[str, Any]]] = {}

    # ── 三段回执 ────────────────────────────────────────────

    def escalate(self, todo: Any, *, to_state: str, channel: Optional[str] = None,
                 name: Optional[str] = None) -> Dict[str, Any]:
        """升级即回执：待办按 SLA 到期被机械晋升（L1→L2 / L2→L3）时调用。

        name：标的名称（巡检一轮一次批量解析后逐条注入，FR-13）。"""
        state = str(to_state or '').strip().upper()
        return self._issue(todo, kind='escalate',
                           period=receipt_period(todo, state), channel=channel, name=name)

    def result(self, todo: Any, *, terminal: Optional[str] = None,
               channel: Optional[str] = None, name: Optional[str] = None,
               close_reason: Optional[str] = None,
               next_condition: Optional[str] = None,
               action_kind: Optional[str] = None) -> Dict[str, Any]:
        """处置后回执：待办收敛出终态（handled/ignored/expired）后调用（t12 在 close 后触发）。

        name：标的名称（FR-13）；close_reason/next_condition/action_kind：close 时的
        处置三要素（FR-14，渲染进卡片）。**不参与聚合**（处置结论必须即时到达）。"""
        tag = str(terminal or 'closed').strip().lower()
        return self._issue(todo, kind='result',
                           period=receipt_period(todo, tag), channel=channel, name=name,
                           close_reason=close_reason, next_condition=next_condition,
                           action_kind=action_kind)

    def timeout(self, todo: Any, *, channel: Optional[str] = None,
                name: Optional[str] = None) -> Dict[str, Any]:
        """超时回执：已在 L3 仍超时未收敛 → 升级给你本人（不改变终态，等处置）。

        name：标的名称（FR-13）。"""
        return self._issue(todo, kind='timeout',
                           period=receipt_period(todo, ''), channel=channel, name=name)

    # ── 幂等 + 发送 ─────────────────────────────────────────

    def _issue(self, todo: Any, *, kind: str, period: str,
               channel: Optional[str] = None, name: Optional[str] = None,
               close_reason: Optional[str] = None,
               next_condition: Optional[str] = None,
               action_kind: Optional[str] = None) -> Dict[str, Any]:
        """幂等落一条回执：exists → 发送 → record。sender 失败不抛，仓储失败抛。

        顺序说明：**先查后发再落库**。查命中即整段跳过（含发送）——这是"只发一次"的
        实现；发送失败仍落库（delivery_status=failed），保证"只落一条"且失败可见，
        不把失败伪装成没发生。仓储异常向上抛给调用方（WatchSlaJob 按单条记录并继续），
        绝不在此吞掉——"回执库坏了"必须暴露。
        """
        kind_value = str(kind or '').strip().lower()
        if kind_value not in RECEIPT_KINDS:
            raise ValueError(f'未知回执类型 kind={kind!r}（允许 {list(RECEIPT_KINDS)}）')
        todo_id = int(getattr(todo, 'id'))
        digest = payload_digest(kind_value, todo_id, period)
        ch = str(channel or '').strip() or resolve_channel(getattr(todo, 'level', None), kind_value)

        if self._repo.exists(todo_id, kind_value, digest):
            logger.info('回执已存在，幂等跳过（不重发）', todo_id=todo_id, kind=kind_value,
                        channel=ch, digest=digest)
            return {
                'issued': False, 'duplicate': True, 'sent': False, 'kind': kind_value,
                'todo_id': todo_id, 'channel': ch, 'delivery_status': None,
                'digest': digest, 'message': None, 'receipt': None,
            }

        # REQ-ad0a t4（FR-8）：聚合轮开启且属聚合类型 → 入组（flush 时投递+落库）；
        # 否则保持即时投递（result/suppressed 与聚合轮外的直调行为不变）。
        grouped = kind_value in AGGREGATE_KINDS and self._group_open
        message = render_receipt(todo, kind=kind_value, period=period, name=name,
                                 close_reason=close_reason,
                                 next_condition=next_condition,
                                 action_kind=action_kind,
                                 in_group=grouped)
        if grouped:
            self._group_buffer.setdefault(kind_value, []).append({
                'todo_id': todo_id, 'channel': ch, 'period': period,
                'digest': digest, 'message': message,
                'level': getattr(todo, 'level', None),
            })
            logger.info('回执已入聚合组（flush 时投递并落库）', todo_id=todo_id,
                        kind=kind_value, digest=digest)
            return {
                'issued': True, 'duplicate': False, 'sent': False, 'kind': kind_value,
                'todo_id': todo_id, 'channel': ch, 'delivery_status': None,
                'digest': digest, 'message': message, 'receipt': None, 'grouped': True,
            }
        delivery, sent = self._deliver(todo_id, kind_value, ch, message, period, todo=todo)

        receipt = self._repo.record(todo_id, kind_value, channel=ch,
                                    delivery_status=delivery, message_id=None,
                                    payload_digest=digest)
        logger.info('回执已落库', todo_id=todo_id, kind=kind_value, channel=ch,
                    delivery_status=delivery, digest=digest)
        return {
            'issued': True, 'duplicate': False, 'sent': sent, 'kind': kind_value,
            'todo_id': todo_id, 'channel': ch, 'delivery_status': delivery,
            'digest': digest, 'message': message, 'receipt': receipt,
        }

    def _deliver(self, todo_id: int, kind: str, channel: str,
                 message: str, period: str,
                 todo: Any = None) -> (str, bool):
        """发送回执：返回 (delivery_status, sent)。任何 sender 异常都不得抛出。"""
        if self._sender is None:
            # 诚实边界：未接线只记日志，delivery_status 记为 log_only（不是 sent）
            logger.warning('回执未接线（log-only，未送达）', todo_id=todo_id, kind=kind,
                           channel=channel, message=message)
            return DELIVERY_LOG_ONLY, False
        payload = {
            'todo_id': todo_id, 'kind': kind, 'channel': channel,
            'period': period, 'message': message,
            # REQ-ad0a t3（FR-3）：级别随载荷下发（P0 → risk_stop 频道）
            'level': getattr(todo, 'level', None),
        }
        try:
            self._sender(payload)
        except Exception as e:  # noqa: BLE001 - 通道失败不许打挂巡检
            logger.error('回执发送失败（如实记 failed，不打断巡检）', todo_id=todo_id,
                         kind=kind, channel=channel, error=str(e))
            return DELIVERY_FAILED, False
        return DELIVERY_SENT, True

    # ── 聚合投递（REQ-260924104605-ad0a t4，FR-8）───────────────────────────

    def begin_group(self) -> None:
        """开启一轮聚合投递（巡检 run_once 扫描成功后调用）。

        开启期间 escalate/timeout 回执只入组、不投递不落库；收尾**必须**调
        flush_grouped（聚合卡投递 + 逐条落库）。result/suppressed 不受影响
        （即时投递）。重复开启幂等（缓冲保留）。
        """
        self._group_open = True

    def flush_grouped(self) -> Dict[str, Dict[str, Any]]:
        """收尾聚合轮：按 kind 各发一张聚合卡，并逐条落库（不重不漏）。

        空组 = no-op；sender 抛错 = 整组记 failed（不吞错、不中断巡检）；
        sender 未接线 = 整组 log_only（诚实边界，不假装已发）。
        去重键仍是 per-todo 的 payload_digest（digest 语义不变），聚合只发生在
        **投递层**——同周期重复巡检在 _issue 的 exists 处即整段跳过（含入组）。
        返回 {kind: {count, sent, delivery_status, batch_id}} 供调用方合并统计。
        """
        self._group_open = False
        summary: Dict[str, Dict[str, Any]] = {}
        for kind_value in list(self._group_buffer.keys()):
            items = self._group_buffer.pop(kind_value)
            if not items:
                continue
            batch_id = 'batch:%s:%s' % (kind_value, datetime.now().strftime('%Y%m%d%H%M'))
            has_p0 = any(str(it.get('level') or '').strip().upper() == 'P0' for it in items)
            high = (kind_value == 'timeout') or has_p0
            ch = CHANNEL_ALERTS if high else CHANNEL_REPORTS
            card = render_group_card(kind_value, items)
            payload = {
                'kind': kind_value, 'channel': ch, 'message': card,
                # t3 的 watch_channels：显式 os_channel 优先（timeout/P0 → risk_stop）
                'os_channel': 'risk_stop' if high else 'watch_symbol',
                'batch_id': batch_id, 'items': len(items),
                'level': 'P0' if has_p0 else None,
            }
            if self._sender is None:
                logger.warning('聚合回执未接线（log-only，未送达）',
                               kind=kind_value, count=len(items))
                delivery, sent = DELIVERY_LOG_ONLY, False
            else:
                try:
                    self._sender(payload)
                    delivery, sent = DELIVERY_SENT, True
                except Exception as e:  # noqa: BLE001 - sender 失败不抛，整组记 failed
                    logger.error('聚合回执发送失败（整组记 failed）',
                                 kind=kind_value, count=len(items), error=str(e))
                    delivery, sent = DELIVERY_FAILED, False
            for it in items:
                self._repo.record(it['todo_id'], kind_value, channel=ch,
                                  delivery_status=delivery, message_id=batch_id,
                                  payload_digest=it['digest'])
            logger.info('聚合回执已落库', kind=kind_value, count=len(items),
                        delivery_status=delivery, batch_id=batch_id)
            summary[kind_value] = {'count': len(items), 'sent': sent,
                                   'delivery_status': delivery, 'batch_id': batch_id}
        return summary

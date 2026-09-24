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
from typing import Any, Callable, Dict, Optional

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


def render_receipt(todo: Any, *, kind: str, period: str,
                   name: Optional[str] = None,
                   close_reason: Optional[str] = None,
                   next_condition: Optional[str] = None,
                   action_kind: Optional[str] = None) -> str:
    """回执文案（纯函数，只认结构化字段，禁止在调用点拼串）

    形态对齐 R4「首行一眼看到标的 + 该干什么」：回执不是通知，而是**台账条目**，
    故带上待办号/流转态/级别/账户与 due 周期，便于人工与 agent 双向追溯。

    REQ-260924104605-ad0a t1 契约扩展（全部 keyword-only、默认 None，旧调用兼容）：
      name           标的名称——提供时渲染为「名称（代码）」（FR-13）；缺失如实
                     降级「代码（名称缺失）」，绝不臆造（R-013）；
      close_reason   处置原因（t5 的 result 三要素文案使用）；
      next_condition 后续处理意见 / NEXT 条件（t5 使用；ignored 必填由 I4 保证）；
      action_kind    处置动作类型（t5 使用）。
    """
    todo_id = getattr(todo, 'id', None)
    symbol = getattr(todo, 'symbol', None) or '(未知标的)'
    name_text = str(name or '').strip()
    display = (f'{name_text}（{symbol}）' if name_text
               else (f'{symbol}（名称缺失）' if symbol != '(未知标的)' else symbol))
    level = getattr(todo, 'level', None) or '--'
    flow = getattr(todo, 'flow_state', None) or '--'
    account = getattr(todo, 'account', None) or '(无归属)'
    due = getattr(todo, 'due_at', None)
    due_text = due.isoformat() if hasattr(due, 'isoformat') else str(due or '')
    if kind == 'escalate':
        head = f'[升级即] 待办#{todo_id} {display} {level} 已从 {flow} 晋升'
    elif kind == 'timeout':
        head = f'[超时] 待办#{todo_id} {display} {level} 超时未处置，升级给你本人'
    elif kind == 'result':
        head = f'[处置后] 待办#{todo_id} {display} {level} 已出处置结论'
    else:
        head = f'[回执] 待办#{todo_id} {display} {level}'
    return (f'{head} | 账户 {account} | due {due_text} | 周期 {period}')


class ReceiptService:
    """三段回执的编排服务（幂等 + 可注入 sender；仓储由构造注入）

    无状态；不做级别判定、不决定晋升、不碰 SQL。
    """

    def __init__(self, repo: Any, sender: Optional[Sender] = None):
        self._repo = repo
        #: 缺省 None = log-only（真实通道接线归 t12），**不得**在服务内自建飞书通道
        self._sender = sender

    # ── 三段回执 ────────────────────────────────────────────

    def escalate(self, todo: Any, *, to_state: str, channel: Optional[str] = None) -> Dict[str, Any]:
        """升级即回执：待办按 SLA 到期被机械晋升（L1→L2 / L2→L3）时调用。"""
        state = str(to_state or '').strip().upper()
        return self._issue(todo, kind='escalate',
                           period=receipt_period(todo, state), channel=channel)

    def result(self, todo: Any, *, terminal: Optional[str] = None,
               channel: Optional[str] = None) -> Dict[str, Any]:
        """处置后回执：待办收敛出终态（handled/ignored/expired）后调用（t12 在 close 后触发）。"""
        tag = str(terminal or 'closed').strip().lower()
        return self._issue(todo, kind='result',
                           period=receipt_period(todo, tag), channel=channel)

    def timeout(self, todo: Any, *, channel: Optional[str] = None) -> Dict[str, Any]:
        """超时回执：已在 L3 仍超时未收敛 → 升级给你本人（不改变终态，等处置）。"""
        return self._issue(todo, kind='timeout',
                           period=receipt_period(todo, ''), channel=channel)

    # ── 幂等 + 发送 ─────────────────────────────────────────

    def _issue(self, todo: Any, *, kind: str, period: str,
               channel: Optional[str] = None) -> Dict[str, Any]:
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

        message = render_receipt(todo, kind=kind_value, period=period)
        delivery, sent = self._deliver(todo_id, kind_value, ch, message, period)

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
                 message: str, period: str) -> (str, bool):
        """发送回执：返回 (delivery_status, sent)。任何 sender 异常都不得抛出。"""
        if self._sender is None:
            # 诚实边界：未接线只记日志，delivery_status 记为 log_only（不是 sent）
            logger.warning('回执未接线（log-only，未送达）', todo_id=todo_id, kind=kind,
                           channel=channel, message=message)
            return DELIVERY_LOG_ONLY, False
        payload = {
            'todo_id': todo_id, 'kind': kind, 'channel': channel,
            'period': period, 'message': message,
        }
        try:
            self._sender(payload)
        except Exception as e:  # noqa: BLE001 - 通道失败不许打挂巡检
            logger.error('回执发送失败（如实记 failed，不打断巡检）', todo_id=todo_id,
                         kind=kind, channel=channel, error=str(e))
            return DELIVERY_FAILED, False
        return DELIVERY_SENT, True

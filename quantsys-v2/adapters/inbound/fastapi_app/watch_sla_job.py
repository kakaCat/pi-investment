"""到期巡检（闭环唯一收敛权威）（REQ-c9f899 t6，2026-09-18）

architecture.md §4：「**唯一收敛权威 = WatchSlaJob**（机械、可测、不依赖 agent 主动性）：
扫描非终态且 due_at < now 的待办 → 晋升一级；已在 L3 仍超时 → 升级给用户（P0 直接 @）。」
需求不变式 I1「不得滞留」的机械保证——不靠 agent 主动，靠这条定时任务。

每轮（run_once）逐条处理 list_overdue(now) 的结果：

  · flow_state == 'L1' → 晋升 'L2'（写 escalate 回执）；
  · flow_state == 'L2' → 晋升 'L3'（写 escalate 回执）；
  · flow_state == 'L3' → **升级给用户**：写 timeout 回执（不改终态，等处置），并把
    escalate_count +1（同一 due 周期只做一次，幂等由回执摘要保证）。

设计要点（都可被 tests/application/test_sla_job.py 证伪）：
  · **时间由调用方注入**（now 参数），全程无隐式时钟——可单测、可回放；
  · **幂等**：同一待办同一 due 周期不重复写回执（ReceiptService 用 payload_digest 去重）；
  · **单条异常不中断整轮**：逐条 try/except，记日志继续（一条坏数据不该让全队列滞留）；
  · **仓储抛错不打挂**：list_overdue 失败 → 返回 degraded=True 的统计且不抛——
    但绝不假装"扫描过且没事"（scanned=0 + degraded 标记，调用方/告警可据此外置）。

⚠️ 诚实边界：本模块**不自建调度器、不直接发飞书**。定时注册与真实通知通道接线归 t12；
未接线时回执走 log-only（delivery_status=log_only），不许假装已发。
"""
from datetime import datetime
from typing import Any, Dict, Optional

import structlog

from application.services.watch_engine.receipt_service import ReceiptService

logger = structlog.get_logger(__name__)

#: 单轮扫描上限（对齐仓储 list_overdue 的 limit 语义，避免一轮吃下无限积压）
DEFAULT_LIMIT = 100


def _default_todo_repo():
    """缺省待办仓储（惰性导入：模块导入期不碰 DB/ORM 装配）"""
    from adapters.outbound.repositories.watch_todo_repository import WatchTodoRepository
    return WatchTodoRepository()


def _default_receipt_repo():
    """缺省回执仓储（惰性导入）"""
    from adapters.outbound.repositories.watch_receipt_repository import WatchReceiptRepository
    return WatchReceiptRepository()


class WatchSlaJob:
    """到期巡检编排（无状态；仓储与回执服务由构造注入）"""

    def __init__(self, todo_repo: Any, receipt_service: Optional[ReceiptService] = None, *,
                 receipt_repo: Any = None, sender: Any = None, limit: int = DEFAULT_LIMIT,
                 name_resolver: Any = None):
        self._todo_repo = todo_repo
        if receipt_service is None:
            receipt_service = ReceiptService(receipt_repo or _default_receipt_repo(),
                                             sender=sender)
        self._receipts = receipt_service
        self._limit = limit
        # REQ-ad0a t4（FR-13）：标的名解析端口（StockNameResolver）。一轮一次批量联查
        # （替代逐条 N+1）；缺省 None = 不解析（回执如实标「名称缺失」，不臆造）。
        self._name_resolver = name_resolver

    # ── 主循环 ──────────────────────────────────────────────

    def run_once(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """巡检一轮，返回计数字典（含 promoted/escalated/timeout/alerts，便于断言）。"""
        at = now if now is not None else datetime.now()
        stats: Dict[str, Any] = {
            'now': at.isoformat() if hasattr(at, 'isoformat') else str(at),
            'scanned': 0,          # list_overdue 命中条数
            'promoted': 0,         # 流转态晋升条数（L1→L2 / L2→L3）
            'escalated': 0,        # escalate 回执新发条数
            'timeout': 0,          # timeout 回执新发条数（L3 升级给用户）
            'alerts': 0,           # 回执实际送达（sender 未抛错）条数
            'duplicates': 0,       # 幂等跳过的回执条数
            'skipped': 0,          # 仓储返回 None（已收敛/并发抢先）或未知流转态
            'errors': 0,           # 单条处理异常条数
            'degraded': False,     # 扫描失败（整轮降级，不抛）
            'degraded_reason': None,
            'group_cards': 0,      # 聚合卡张数（REQ-ad0a t4：一 kind 一卡）
        }

        try:
            overdue = self._todo_repo.list_overdue(now=at, limit=self._limit)
        except Exception as e:  # noqa: BLE001 - 仓储抛错不得打挂巡检
            stats['degraded'] = True
            stats['degraded_reason'] = str(e)
            logger.error('到期巡检扫描失败：整轮降级（返回 degraded，不抛错）', error=str(e))
            return stats

        stats['scanned'] = len(overdue)

        # REQ-ad0a t4（FR-13）：一轮一次批量解析标的名称（替代逐条 N+1）；
        # 解析失败 → 全 None 降级（回执标「名称缺失」），不打断巡检。
        names: Dict[str, Any] = {}
        if self._name_resolver is not None and overdue:
            try:
                names = self._name_resolver.resolve_batch(
                    [getattr(todo, 'symbol', '') for todo in overdue]) or {}
            except Exception as e:  # noqa: BLE001 - 端口约定不抛，这里再兜一层
                logger.error('标的名批量解析异常（降级为名称缺失）', error=str(e))
                names = {}

        # REQ-ad0a t4（FR-8）：开启聚合轮——本轮 escalate/timeout 入组，循环结束后
        # flush_grouped 按 kind 各发一张聚合卡并逐条落库；即使中途出错也在 finally 收尾。
        self._receipts.begin_group()
        try:
            for todo in overdue:
                try:
                    self._process_one(todo, at, stats, names)
                except Exception as e:  # noqa: BLE001 - 单条异常不中断整轮
                    stats['errors'] += 1
                    logger.error('到期巡检单条失败（记错继续，不中断整轮）',
                                 todo_id=getattr(todo, 'id', None), error=str(e))
        finally:
            try:
                flush = self._receipts.flush_grouped()
                stats['group_cards'] = len(flush)
                # 聚合卡送达 → 按条数补记 alerts（grouped 回执在入组时 sent=False）
                stats['alerts'] += sum(v['count'] for v in flush.values() if v.get('sent'))
            except Exception as e:  # noqa: BLE001 - 收尾失败记错不抛（仓储失败会向上抛到此处）
                stats['errors'] += 1
                logger.error('聚合回执收尾失败（记错不中断）', error=str(e))

        logger.info('到期巡检完成',
                    **{k: stats[k] for k in ('scanned', 'promoted', 'escalated', 'timeout',
                                             'alerts', 'duplicates', 'skipped', 'errors',
                                             'group_cards')})
        return stats

    # ── 单条编排 ────────────────────────────────────────────

    @staticmethod
    def _name_of(todo: Any, names: Dict[str, Any]) -> Any:
        """从批量解析结果取名称（键 = 规范化 6 位码，与 StockNameResolver 同口径）。"""
        symbol = str(getattr(todo, 'symbol', '') or '').split('.')[0].strip()
        return names.get(symbol)

    def _process_one(self, todo: Any, now: datetime, stats: Dict[str, Any],
                     names: Optional[Dict[str, Any]] = None) -> None:
        """按流转态决定动作：L1→L2、L2→L3、L3 超时升级给用户。"""
        names = names or {}
        state = str(getattr(todo, 'flow_state', '') or '').strip().upper()
        if state == 'L1':
            self._promote(todo, 'L2', now, stats, names)
        elif state == 'L2':
            self._promote(todo, 'L3', now, stats, names)
        elif state == 'L3':
            self._escalate_to_user(todo, now, stats, names)
        else:
            # 未知状态不臆造晋升（也不静默当"已收敛"）：计入 skipped 并留日志
            stats['skipped'] += 1
            logger.warning('到期巡检遇到未知流转态，跳过（不臆造晋升）',
                           todo_id=getattr(todo, 'id', None), flow_state=state)

    def _promote(self, todo: Any, to_state: str, now: datetime, stats: Dict[str, Any],
                 names: Optional[Dict[str, Any]] = None) -> None:
        """晋升一级并写升级即回执。仓储返回 None = 已收敛/并发抢先 → 不改不发。"""
        todo_id = getattr(todo, 'id')
        updated = self._todo_repo.promote(todo_id, to_state, now=now)
        if updated is None:
            stats['skipped'] += 1
            logger.info('待办已收敛/不可晋升（并发抢先），跳过', todo_id=todo_id,
                        to_state=to_state)
            return
        stats['promoted'] += 1
        outcome = self._receipts.escalate(updated, to_state=to_state,
                                          name=self._name_of(todo, names or {}))
        self._tally(outcome, stats, 'escalated')

    def _escalate_to_user(self, todo: Any, now: datetime, stats: Dict[str, Any],
                          names: Optional[Dict[str, Any]] = None) -> None:
        """L3 仍超时：写 timeout 回执（不改变终态）并把 escalate_count +1。

        幂等：同一 due 周期只升级一次——第二次巡检回执 exists 命中即整段跳过
        （既不重发、也不重复累加计数）。
        """
        todo_id = getattr(todo, 'id')
        outcome = self._receipts.timeout(todo, name=self._name_of(todo, names or {}))
        if not outcome.get('issued'):
            stats['duplicates'] += 1
            return
        stats['timeout'] += 1
        if outcome.get('sent'):
            stats['alerts'] += 1
        # 记 escalate_count：待办端口没有独立的"只加计数"方法，复用 promote 语义
        # （流转态保持 L3、显式传新值），保证"升级次数"可被统计与回溯。
        current = int(getattr(todo, 'escalate_count', 0) or 0)
        bumped = self._todo_repo.promote(todo_id, 'L3', escalate_count=current + 1, now=now)
        if bumped is None:
            logger.warning('超时回执已写但 escalate_count 未累加（待办已收敛/并发抢先）',
                           todo_id=todo_id)

    @staticmethod
    def _tally(outcome: Dict[str, Any], stats: Dict[str, Any], key: str) -> None:
        """回执结果计入统计：新发 → key+1（送达再 +alerts）；幂等命中 → duplicates+1。"""
        if outcome.get('issued'):
            stats[key] += 1
            if outcome.get('sent'):
                stats['alerts'] += 1
        else:
            stats['duplicates'] += 1


def run_sla_once(now: Optional[datetime] = None, *, todo_repo: Any = None,
                 receipt_service: Optional[ReceiptService] = None,
                 limit: int = DEFAULT_LIMIT) -> Dict[str, Any]:
    """便捷入口（供 t12 的定时任务调用）：缺省用真实仓储/回执服务（log-only sender）。"""
    job = WatchSlaJob(todo_repo if todo_repo is not None else _default_todo_repo(),
                      receipt_service=receipt_service, limit=limit)
    return job.run_once(now)

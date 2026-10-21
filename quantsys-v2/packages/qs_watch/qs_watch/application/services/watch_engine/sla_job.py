"""到期巡检（闭环唯一收敛权威）（REQ-c9f899 t6，2026-09-18）

architecture.md §4：「**唯一收敛权威 = WatchSlaJob**（机械、可测、不依赖 agent 主动性）：
扫描非终态且 due_at < now 的待办 → 晋升一级；已在 L3 仍超时 → 升级给用户（P0 直接 @）。」
需求不变式 I1「不得滞留」的机械保证——不靠 agent 主动，靠这条定时任务。

每轮（run_once）逐条处理 list_overdue(now) 的结果：

  · flow_state == 'L1' → 晋升 'L2'（**不发卡**：晋升是引擎内部状态机迁移，不是市场事实，
    历史在待办 flow_state / escalate_count 与结果回执时间线可见——REQ-261016155500-4f2a
    回执收敛：一待办生命周期卡片 ≤2）；
  · flow_state == 'L2' → 晋升 'L3'（同样不发卡；due_at 顺延 30min 防收盘三连升）；
  · flow_state == 'L3' → **升级给用户**：写 timeout 回执（不改终态，等处置），
    P0/P1 发送、P2/P3 只落台账（deliver=False，日终汇总点名）；escalate_count +1
    （同一 due 周期只做一次，幂等由回执摘要保证）。

设计要点（都可被 tests/application/test_sla_job.py 证伪）：
  · **时间由调用方注入**（now 参数），全程无隐式时钟——可单测、可回放；
  · **幂等**：同一待办同一 due 周期不重复写回执（ReceiptService 用 payload_digest 去重）；
  · **单条异常不中断整轮**：逐条 try/except，记日志继续（一条坏数据不该让全队列滞留）；
  · **仓储抛错不打挂**：list_overdue 失败 → 返回 degraded=True 的统计且不抛——
    但绝不假装"扫描过且没事"（scanned=0 + degraded 标记，调用方/告警可据此外置）。

⚠️ 诚实边界：本模块**不自建调度器、不直接发飞书**。定时注册与真实通知通道接线归 t12；
未接线时回执走 log-only（delivery_status=log_only），不许假装已发。
"""
import os
from datetime import datetime
from typing import Any, Dict, Optional

import structlog

from qs_watch.application.services.watch_engine.receipt_service import ReceiptService

from qs_watch.application.services.watch_engine._repo_resolver import (
    receipt_repo,
    todo_repo,
)

logger = structlog.get_logger(__name__)

#: 单轮扫描上限（对齐仓储 list_overdue 的 limit 语义，避免一轮吃下无限积压）
DEFAULT_LIMIT = 100

#: L3 再催节奏（2026-10-20 治「L3 一生只催一次」的僵尸待办）：
#: 首催后每超 remind_interval 且未达 max_reminds 再催一轮（逐轮升紧迫文案）；
#: 超 auto_expire_days 仍无人处置 → 自动 expired 归档（进台账不进黑洞）。
def _remind_interval_sec() -> float:
    try:
        return max(600.0, float(os.getenv('WATCH_L3_REMIND_INTERVAL_SEC', '14400')))
    except (TypeError, ValueError):
        return 14400.0


def _max_reminds() -> int:
    try:
        return max(1, int(os.getenv('WATCH_L3_MAX_REMINDS', '3')))
    except (TypeError, ValueError):
        return 3


def _auto_expire_days() -> float:
    try:
        return max(1.0, float(os.getenv('WATCH_TODO_AUTO_EXPIRE_DAYS', '3')))
    except (TypeError, ValueError):
        return 3.0


def _default_todo_repo():
    """缺省待办仓储（惰性导入：模块导入期不碰 DB/ORM 装配）"""
    return todo_repo()


def _default_receipt_repo():
    """缺省回执仓储（惰性导入）"""
    return receipt_repo()


class WatchSlaJob:
    """到期巡检编排（无状态；仓储与回执服务由构造注入）"""

    def __init__(self, todo_repo: Any, receipt_service: Optional[ReceiptService] = None, *,
                 receipt_repo: Any = None, sender: Any = None, limit: int = DEFAULT_LIMIT,
                 name_resolver: Any = None, todo_service: Any = None):
        self._todo_repo = todo_repo
        # 2026-10-20 自动归档用（close 走领域校验）；None = 关闭自动归档
        self._todo_service = todo_service
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
            'escalated': 0,        # escalate 回执新发条数（REQ-261016155500-4f2a 起恒 0：
                                   # 升级回执下线，晋升历史在结果回执时间线可见）
            'timeout': 0,          # timeout 回执新发条数（L3；含 P2/P3 仅台账）
            'timeout_suppressed': 0,  # P2/P3 超时只落台账未发送条数
            'agent_wakes': 0,      # 超时升级**去向为 agent** 的条数（owner_kind=agent；
                                   # 是否送达看回执 delivery_status，不再计入 alerts 误读）
            'alerts': 0,           # 回执实际送达（sender 未抛错）条数
            'duplicates': 0,       # 幂等跳过的回执条数
            'skipped': 0,          # 仓储返回 None（已收敛/并发抢先）或未知流转态
            'errors': 0,           # 单条处理异常条数
            'degraded': False,     # 扫描失败（整轮降级，不抛）
            'degraded_reason': None,
            'group_cards': 0,      # 聚合卡**实发张数**（agent 私有唤醒占满一轮时可为 0）
            'reminds': 0,          # 2026-10-20：L3 再催轮数（首催不计）
            'expired': 0,          # 2026-10-20：超期未处置自动归档条数
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
                # group_cards = 实发卡数（card_count）；一个 kind 的条目可能全部走私信唤醒而无卡
                stats['group_cards'] = sum(int(v.get('card_count', 0))
                                           for v in flush.values())
                # 聚合卡送达 → 按条数补记 alerts（grouped 回执在入组时 sent=False）
                stats['alerts'] += sum(v['count'] for v in flush.values() if v.get('sent'))
                # result 聚合兜底 flush（2026-10-19）：窗口内批量处置合成一张卡；
                # 发送失败不抛（receipt_service 内自吞并记 failed，下轮重试）
                rflush = self._receipts.flush_result_buffer()
                stats['alerts'] += rflush.get('count', 0) if rflush.get('sent') else 0
                stats['group_cards'] += 1 if rflush.get('sent') else 0
            except Exception as e:  # noqa: BLE001 - 收尾失败记错不抛（仓储失败会向上抛到此处）
                stats['errors'] += 1
                logger.error('聚合回执收尾失败（记错不中断）', error=str(e))

        logger.info('到期巡检完成',
                    **{k: stats[k] for k in ('scanned', 'promoted', 'escalated', 'timeout',
                                             'alerts', 'duplicates', 'skipped', 'errors',
                                             'group_cards', 'agent_wakes')})
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
        """晋升一级（不发卡，REQ-261016155500-4f2a 回执收敛）。

        晋升是引擎内部状态机迁移（L1→L2→L3），不是市场事实——盯盘群不再为它单发卡，
        历史留三处：待办 flow_state + escalate_count（仓储）、结果回执时间线
        （「晋升 N 次」）。仓储 promote 会把 due_at 顺延 30min（防收盘三连升）。
        仓储返回 None = 已收敛/并发抢先 → 不改不发。"""
        todo_id = getattr(todo, 'id')
        updated = self._todo_repo.promote(todo_id, to_state, now=now)
        if updated is None:
            stats['skipped'] += 1
            logger.info('待办已收敛/不可晋升（并发抢先），跳过', todo_id=todo_id,
                        to_state=to_state)
            return
        stats['promoted'] += 1
        logger.info('待办已晋升（不发卡，历史见待办状态与结果回执时间线）',
                    todo_id=todo_id, to_state=to_state)

    def _escalate_to_user(self, todo: Any, now: datetime, stats: Dict[str, Any],
                          names: Optional[Dict[str, Any]] = None) -> None:
        """L3 仍超时：写 timeout 回执（不改变终态）并把 escalate_count +1。

        REQ-261016155500-4f2a：仅 P0/P1 发送给用户；P2/P3 只落台账（deliver=False，
        日终汇总点名），不打扰。幂等：同一 due 周期只升级一次——第二次巡检回执
        exists 命中即整段跳过（既不重发、也不重复累加计数）。

        升级去向按**待办归属**分流（owner_kind，见 TodoService 的 route_owner）：
        agent 自有的待办由 ReceiptService 改唤醒 owner agent（不占用用户卡片），
        用户账户的待办才升级给人。

        2026-10-16 修复（生产实测缺陷）：给 escalate_count +1 复用 `promote()` 时
        **必须显式 extend_due_minutes=0**。仓储的 promote 缺省会顺延 due_at 30min
        （那是给 L1→L2/L2→L3 晋升防收盘三连升用的），而 due_at 是回执幂等键
        （payload_digest 的 period）的一部分——顺延一次就换一个新 digest，
        于是"同一 due 周期只发一次"变成"每 30 分钟复读一张超时卡"，永不收敛
        （2026-10-16 实测：13 条 P1 待办 3 小时内刷了 78 条 timeout 回执）。
        """
        todo_id = getattr(todo, 'id')
        level = str(getattr(todo, 'level', '') or '').strip().upper()
        deliver = level in ('P0', 'P1')
        name = self._name_of(todo, names or {})
        outcome = self._receipts.timeout(todo, name=name, deliver=deliver)
        if not outcome.get('issued'):
            # 2026-10-20 再催节奏 + 自动归档：幂等命中（首催已发）后的两条出路。
            stats['duplicates'] += 1
            self._remind_or_expire(todo, now, stats, name, deliver)
            return
        stats['timeout'] += 1
        if outcome.get('audience') == 'agent':
            stats['agent_wakes'] += 1
        elif not deliver:
            stats['timeout_suppressed'] += 1
        if outcome.get('sent'):
            stats['alerts'] += 1
        # 记 escalate_count：待办端口没有独立的"只加计数"方法，复用 promote 语义
        # （流转态保持 L3、显式传新值），保证"升级次数"可被统计与回溯。
        # extend_due_minutes=0：**不得**顺延 due_at，否则幂等键轮换 → 复读（见 docstring）。
        current = int(getattr(todo, 'escalate_count', 0) or 0)
        bumped = self._todo_repo.promote(todo_id, 'L3', escalate_count=current + 1, now=now,
                                         extend_due_minutes=0)
        if bumped is None:
            logger.warning('超时回执已写但 escalate_count 未累加（待办已收敛/并发抢先）',
                           todo_id=todo_id)


    def _remind_or_expire(self, todo: Any, now: datetime, stats: Dict[str, Any],
                          name: Any, deliver: bool) -> None:
        """首催已发过（幂等命中）后的两条出路：到点再催 / 超期归档。"""
        todo_id = getattr(todo, 'id')
        due = getattr(todo, 'due_at', None)
        if due is None:
            return
        # 时区口径对齐（2026-10-20 生产实测）：库里的 due 是带时区（timestamptz），
        # 巡检 now 是本地 naive——直接相减抛 TypeError。统一成 naive-UTC 再算。
        import datetime as _dt
        now_cmp = now
        if due.tzinfo is not None:
            due = due.astimezone(_dt.timezone.utc).replace(tzinfo=None)
        if now_cmp.tzinfo is not None:
            now_cmp = now_cmp.astimezone(_dt.timezone.utc).replace(tzinfo=None)
        overdue_sec = (now_cmp - due).total_seconds()
        current = int(getattr(todo, 'escalate_count', 0) or 0)

        # 出路二：超 auto_expire_days 无人处置 → 自动归档（仅当注入 todo_service）
        if overdue_sec >= _auto_expire_days() * 86400:
            if self._todo_service is None:
                return
            try:
                # action_kind=None：自动归档不是人的动作，无审计动作——
                # 2026-10-20 领域口径收紧后 action_kind 枚举只剩 ('trade','rule_change')。
                self._todo_service.close(
                    todo_id, 'expired',
                    close_reason='L3 超时 %.1f 天未处置，系统自动归档（进台账，'
                                 '非判定；如需重开请重建待办）' % (overdue_sec / 86400),
                    action_kind=None)
                stats['expired'] = stats.get('expired', 0) + 1
                logger.info('L3 待办自动归档（超期未处置）', todo_id=todo_id,
                            overdue_days=round(overdue_sec / 86400, 1))
            except Exception as e:  # noqa: BLE001 - 归档失败留错下轮再试
                logger.error('自动归档失败（下轮重试）', todo_id=todo_id, error=str(e))
            return

        # 出路一：到再催点且还有预算 → 发第 current 轮催办（escalate_count 即轮次）
        max_r = _max_reminds()
        interval = _remind_interval_sec()
        if not deliver or current <= 0 or current >= max_r:
            return
        if overdue_sec < interval * current:
            return
        outcome = self._receipts.timeout(todo, name=name, deliver=True,
                                         remind_round=current)
        if outcome.get('issued'):
            stats['timeout'] += 1
            stats['reminds'] = stats.get('reminds', 0) + 1
            logger.info('L3 待办再催（第 %d/%d 轮）' % (current, max_r),
                        todo_id=todo_id, overdue_hours=round(overdue_sec / 3600, 1))
            bumped = self._todo_repo.promote(todo_id, 'L3', escalate_count=current + 1,
                                             now=now, extend_due_minutes=0)
            if bumped is None:
                logger.warning('再催已发但 escalate_count 未累加', todo_id=todo_id)


def run_sla_once(now: Optional[datetime] = None, *, todo_repo: Any = None,
                 receipt_service: Optional[ReceiptService] = None,
                 limit: int = DEFAULT_LIMIT) -> Dict[str, Any]:
    """便捷入口（供 t12 的定时任务调用）：缺省用真实仓储/回执服务（log-only sender）。"""
    job = WatchSlaJob(todo_repo if todo_repo is not None else _default_todo_repo(),
                      receipt_service=receipt_service, limit=limit)
    return job.run_once(now)

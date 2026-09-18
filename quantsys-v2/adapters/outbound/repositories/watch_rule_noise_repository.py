"""规则抑噪态与触发日聚合仓储适配器（REQ-c9f899 R6 / t8，2026-09-18）

实现 domain/watch/ports.py 的 IWatchRuleNoiseRepository。为什么需要它（见端口 docstring）：
t8 的 scan 要读 ① watch_rules 的 noise_state/suppress_until/self_heal_count/last_repair_at
四列（t1 迁移 20260918 已加，**ORM 的 WatchRule 类未声明**，而 watch_rule_repository.py
不在 t8 允许改动的文件清单内）与 ② watch_triggers 的按日聚合。把两张表的两件事塞进
WatchRuleChangeRepository 会混淆职责，故单列本文件（ADR-001：SQL 只在适配器层）。

实现选择：对四个新列用 text() 裸 SQL（列不在 ORM 映射里）；对触发的按日聚合用 ORM 表达式
（WatchTrigger 已映射）。**不新建第二份 watch_rules ORM 映射**——同一张表两个 ORM 类会
在 flush 时互相打架（2026-09-11 的 ORM 漏列教训同源）。

失败语义：读写失败一律向上抛（回滚线程 scoped session 后 re-raise）。mark_* 命中 0 行
（规则被并发删除）同样**响亮抛错**——静默成功会让 scan 以为已抑噪，实际上什么都没改。

聚合口径（关键，避免第二份阈值真相）：
  · daily_counts 只返回**事实**（规则 × 自然日 × 次数），不含任何阈值判断；
  · "连续天数 / 日均"的解释权在 domain（noise_policy.summarize），SQL 不参与判定；
  · 时间窗口 [since, until) 由调用方注入（service 的 now），本适配器不定义"今天"。
  · watch_triggers.triggered_at 是无时区 TIMESTAMP（见 WatchTrigger 定义），故窗口
    也按 naive local datetime 比较，两边同为本地时间，不做隐式时区转换。
"""
from datetime import date, datetime
from typing import Any, Dict, Optional

import structlog
from sqlalchemy import func, text

from adapters.outbound.repositories.watch_rule_repository import WatchRule, WatchTrigger
from infrastructure.persistence.orm import BaseORMRepository

logger = structlog.get_logger(__name__)

#: 规则最小投影（含 t1 新增的四个 noise 列——ORM 未声明，故用裸 SQL 读）
_RULE_SELECT = text("""
    SELECT id, symbol, enabled, account, linked_account,
           noise_state, suppress_until, self_heal_count, last_repair_at
      FROM quant.watch_rules
     WHERE id = :rule_id
""")

#: 置抑噪态：+1 次自愈计数；suppress_until 到点后由消费侧恢复原级别
_MARK_SUPPRESSED = text("""
    UPDATE quant.watch_rules
       SET noise_state = 'suppressed',
           suppress_until = :suppress_until,
           self_heal_count = COALESCE(self_heal_count, 0) + 1,
           updated_at = :now
     WHERE id = :rule_id
""")

#: 抑噪中的规则数（GET /api/watch/metrics.suppressed_rules；到点自动失效不计入）
_COUNT_SUPPRESSED = text("""
    SELECT count(*) FROM quant.watch_rules
     WHERE noise_state = 'suppressed'
       AND (suppress_until IS NULL OR suppress_until > :now)
""")

#: 清抑噪态（修复完成 → 恢复原级别）并记 last_repair_at + 自愈计数
_MARK_REPAIRED = text("""
    UPDATE quant.watch_rules
       SET noise_state = NULL,
           suppress_until = NULL,
           last_repair_at = :now,
           self_heal_count = COALESCE(self_heal_count, 0) + 1,
           updated_at = :now
     WHERE id = :rule_id
""")


class WatchRuleNoiseRepository(BaseORMRepository[WatchRule]):
    """IWatchRuleNoiseRepository 的 PostgreSQL 实现（watch_rules 四列 + watch_triggers 聚合）"""

    model = WatchRule

    # ── 读 ──────────────────────────────────────────────────

    def get_rule(self, rule_id: int) -> Optional[Dict[str, Any]]:
        """规则最小投影；不存在返回 None。失败抛错（绝不静默 None 冒充"没有这条规则"）"""
        try:
            row = self.session.execute(_RULE_SELECT, {'rule_id': int(rule_id)}).mappings().first()
        except Exception:  # noqa: BLE001
            self._safe_rollback()
            raise
        return dict(row) if row is not None else None

    def daily_counts(self, since: datetime, until: datetime) -> Dict[int, Dict[date, int]]:
        """[since, until) 内按 规则 × 自然日 聚合触发次数：{rule_id: {date: count}}"""
        try:
            rows = (
                self.session.query(
                    WatchTrigger.rule_id,
                    func.date(WatchTrigger.triggered_at).label('day'),
                    func.count().label('cnt'),
                )
                .filter(WatchTrigger.rule_id.isnot(None),
                        WatchTrigger.triggered_at.isnot(None),
                        WatchTrigger.triggered_at >= since,
                        WatchTrigger.triggered_at < until)
                .group_by(WatchTrigger.rule_id, func.date(WatchTrigger.triggered_at))
                .all()
            )
        except Exception:  # noqa: BLE001
            self._safe_rollback()
            raise
        out: Dict[int, Dict[date, int]] = {}
        for rule_id, day, cnt in rows:
            key = day.date() if isinstance(day, datetime) else day
            out.setdefault(int(rule_id), {})[key] = int(cnt or 0)
        return out

    # ── 写 ──────────────────────────────────────────────────

    def count_suppressed(self, now: Optional[datetime] = None) -> int:
        """当前处于抑噪态的规则数（suppress_until 已过的不计）。失败抛错。"""
        try:
            value = self.session.execute(
                _COUNT_SUPPRESSED, {'now': now or datetime.now()}).scalar()
        except Exception:  # noqa: BLE001
            self._safe_rollback()
            raise
        return int(value or 0)

    def mark_suppressed(self, rule_id: int, suppress_until: datetime,
                        now: Optional[datetime] = None) -> None:
        """置抑噪态；规则不存在（0 行）→ 响亮抛错"""
        self._update_rule(_MARK_SUPPRESSED, rule_id,
                          {'suppress_until': suppress_until,
                           'now': now or datetime.now()},
                          action='mark_suppressed')

    def mark_repaired(self, rule_id: int, now: Optional[datetime] = None) -> None:
        """清抑噪态并记一次修复；规则不存在（0 行）→ 响亮抛错"""
        self._update_rule(_MARK_REPAIRED, rule_id,
                          {'now': now or datetime.now()}, action='mark_repaired')

    # ── 内部 ────────────────────────────────────────────────

    def _update_rule(self, stmt, rule_id: int, params: Dict[str, Any], *, action: str) -> None:
        payload = dict(params)
        payload['rule_id'] = int(rule_id)
        try:
            result = self.session.execute(stmt, payload)
            self.session.commit()
        except Exception as e:  # noqa: BLE001 - 失败必须响亮
            logger.error('规则抑噪态更新失败', rule_id=rule_id, action=action, error=str(e))
            self._safe_rollback()
            raise
        if result.rowcount == 0:
            # 0 行 = 规则被并发删除：必须响亮（静默成功会让 scan 以为已抑噪）
            raise ValueError(f'规则 {rule_id} 不存在，{action} 未生效（可能被并发删除）')

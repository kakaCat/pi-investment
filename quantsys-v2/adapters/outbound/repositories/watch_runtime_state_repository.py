"""盯盘运行态持久化适配器（REQ-c9f899 t3，2026-09-18）

实现 domain/watch/ports.py 的 IWatchRuntimeStateStore：

  · WatchRuntimeState（quant.watch_runtime_state，(rule_id, cond_idx) 联合主键）
    —— 闩锁 + 冷却基准，启动恢复与批量 upsert（ON CONFLICT DO UPDATE）。
  · WatchRuntimeMeta（quant.watch_runtime_meta，恒 id=1）
    —— 心跳 / 状态日期 / 事件窗口水位 / 影子起始时间，单行 upsert。

返工 B+C（REQ-c9f899，2026-09-18）在同一适配器上补齐三类运行态的读写与裁剪：
  · 去重窗（quant.watch_runtime_dedup，(symbol, direction) 主键）
  · 触发事件窗口（quant.watch_trigger_events，(triggered_at, rule_id, symbol) 主键）
  · 价格历史（quant.watch_price_history，(symbol, ts) 主键）
写路径全部 upsert（事件表用 DO NOTHING 保证重试幂等）；每类都配 prune(cutoff)
把过期行删掉——**持久化不得变成无界增长**（与内存侧按窗口裁剪同口径）。

按 ADR-001（六边形架构）：**SQL/ORM 只允许出现在适配器层**——应用层
（StateManager）只依赖端口。

与 watch_state_repository.py 的关键差异：本类**读失败/写失败都向上抛**
（回滚本线程 scoped session 后 re-raise）。那边的消费方允许缺省值（按"未唤醒/
0"处理），而本处的消费方必须知道「冷却基准丢了」——静默降级为"无冷却"正是
R10 要修的 bug（冷却形同虚设），不能再用一次静默兜底把它伪装掉（宪法第 5 条）。
"""
from typing import Any, Dict, List

import structlog
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from infrastructure.persistence.orm import get_session
from infrastructure.persistence.orm.models.watch_todo import (
    WatchPriceHistory, WatchRuntimeDedup, WatchRuntimeMeta, WatchRuntimeState,
    WatchTriggerEvent,
)

logger = structlog.get_logger(__name__)

# 单行 meta 的固定主键
_META_ID = 1
# ⚠️ 这里刻意**只含** 20260918 迁移已存在的三列：digest_shadow_since 是 20260918b
# 新增列，若塞进来会让「迁移尚未应用」的库（含 pytest 的 quant_test）连心跳读取都
# 直接 ProgrammingError → 整个 app 起不来。影子起始时间走下面的专用读写方法，
# 列缺失时由调用方（shadow_mode_clock）响亮降级，而不是把 meta 全表读死。
_META_FIELDS = ('heartbeat_at', 'state_date', 'event_watermark')


def _safe_rollback() -> None:
    """回滚线程级 scoped session，避免 PG 报错后同线程后续查询撞 aborted 事务。"""
    try:
        get_session().rollback()
    except Exception as rb_err:  # noqa: BLE001
        logger.warning('运行态 session 回滚失败', error=str(rb_err))


class WatchRuntimeStateRepository:
    """IWatchRuntimeStateStore 的 PostgreSQL 实现"""

    # ── 运行态行 ────────────────────────────────────────────

    def load_all(self) -> List[Dict[str, Any]]:
        try:
            rows = (
                get_session()
                .query(
                    WatchRuntimeState.rule_id,
                    WatchRuntimeState.cond_idx,
                    WatchRuntimeState.latched,
                    WatchRuntimeState.last_triggered_at,
                    WatchRuntimeState.cooldown_effective_sec,
                )
                .all()
            )
        except Exception:
            _safe_rollback()
            raise
        return [
            {
                'rule_id': int(r[0]),
                'cond_idx': int(r[1]),
                'latched': bool(r[2]),
                'last_triggered_at': r[3],
                'cooldown_effective_sec': r[4],
            }
            for r in rows
        ]

    def upsert_many(self, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        try:
            tbl = WatchRuntimeState.__table__
            values = [
                {
                    'rule_id': int(row['rule_id']),
                    'cond_idx': int(row['cond_idx']),
                    'latched': bool(row.get('latched')),
                    'last_triggered_at': row.get('last_triggered_at'),
                    'cooldown_effective_sec': row.get('cooldown_effective_sec'),
                    'updated_at': func.now(),
                }
                for row in rows
            ]
            stmt = pg_insert(tbl).values(values)
            stmt = stmt.on_conflict_do_update(
                index_elements=[tbl.c.rule_id, tbl.c.cond_idx],
                set_={
                    'latched': stmt.excluded.latched,
                    'last_triggered_at': stmt.excluded.last_triggered_at,
                    'cooldown_effective_sec': stmt.excluded.cooldown_effective_sec,
                    'updated_at': func.now(),
                },
            )
            session = get_session()
            session.execute(stmt)
            session.commit()
        except Exception as e:
            logger.error('运行态批量写入失败', error=str(e), rows=len(rows))
            _safe_rollback()
            raise

    # ── 单行 meta ───────────────────────────────────────────

    def load_meta(self) -> Dict[str, Any]:
        try:
            row = (
                get_session()
                .query(
                    WatchRuntimeMeta.heartbeat_at,
                    WatchRuntimeMeta.state_date,
                    WatchRuntimeMeta.event_watermark,
                )
                .filter(WatchRuntimeMeta.id == _META_ID)
                .first()
            )
        except Exception:
            _safe_rollback()
            raise
        if row is None:
            return {f: None for f in _META_FIELDS}
        return {'heartbeat_at': row[0], 'state_date': row[1], 'event_watermark': row[2]}

    def save_meta(self, **fields: Any) -> None:
        unknown = set(fields) - set(_META_FIELDS)
        if unknown:
            # 响亮失败：拼错字段名却静默丢弃，会让"心跳已更新"变成假象
            raise ValueError(f'未知 meta 字段: {sorted(unknown)}，允许: {list(_META_FIELDS)}')
        if not fields:
            return
        try:
            tbl = WatchRuntimeMeta.__table__
            stmt = pg_insert(tbl).values(id=_META_ID, updated_at=func.now(), **fields)
            stmt = stmt.on_conflict_do_update(
                index_elements=[tbl.c.id],
                set_={**{k: stmt.excluded[k] for k in fields}, 'updated_at': func.now()},
            )
            session = get_session()
            session.execute(stmt)
            session.commit()
        except Exception as e:
            logger.error('运行态 meta 写入失败', error=str(e), fields=sorted(fields))
            _safe_rollback()
            raise

    # ── 影子起始时间（返工 B，20260918b 新增列）──────────────

    def load_shadow_since(self):
        """读 quant.watch_runtime_meta.digest_shadow_since（无行/无值返回 None）。

        独立于 load_meta 的理由：该列由 20260918b 迁移新增，未迁移的库上直接
        SELECT 会 ProgrammingError。把它隔离成专用方法后，列缺失只会让**本方法**
        抛错，由 shadow_mode_clock 捕获并降级为 env 口径——心跳等既有读取不受牵连。
        读失败向上抛（与同文件其它方法同纪律），由调用方决定降级。
        """
        try:
            row = (
                get_session()
                .query(WatchRuntimeMeta.digest_shadow_since)
                .filter(WatchRuntimeMeta.id == _META_ID)
                .first()
            )
        except Exception:
            _safe_rollback()
            raise
        return None if row is None else row[0]

    def save_shadow_since(self, dt) -> None:
        """写 digest_shadow_since（仅该列，不碰心跳/水位）；列缺失时抛错由调用方降级。"""
        try:
            tbl = WatchRuntimeMeta.__table__
            stmt = pg_insert(tbl).values(
                id=_META_ID, updated_at=func.now(), digest_shadow_since=dt)
            stmt = stmt.on_conflict_do_update(
                index_elements=[tbl.c.id],
                set_={'digest_shadow_since': stmt.excluded.digest_shadow_since,
                      'updated_at': func.now()},
            )
            session = get_session()
            session.execute(stmt)
            session.commit()
        except Exception as e:
            logger.error('影子起始时间写入失败', error=str(e))
            _safe_rollback()
            raise

    # ── 去重窗（返工 B）─────────────────────────────────────

    def load_dedup(self) -> List[Dict[str, Any]]:
        """全部去重键（调用方按窗口过滤，避免把过滤口径复制两份）。

        每行：{symbol, direction, notified_at, trigger_id, rule_id}
        """
        try:
            rows = (
                get_session()
                .query(
                    WatchRuntimeDedup.symbol,
                    WatchRuntimeDedup.direction,
                    WatchRuntimeDedup.notified_at,
                    WatchRuntimeDedup.trigger_id,
                    WatchRuntimeDedup.rule_id,
                )
                .all()
            )
        except Exception:
            _safe_rollback()
            raise
        return [
            {'symbol': r[0], 'direction': r[1], 'notified_at': r[2],
             'trigger_id': r[3], 'rule_id': r[4]}
            for r in rows
        ]

    def upsert_dedup(self, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        try:
            tbl = WatchRuntimeDedup.__table__
            values = [
                {
                    'symbol': row['symbol'],
                    'direction': row['direction'],
                    'notified_at': row['notified_at'],
                    'trigger_id': row.get('trigger_id'),
                    'rule_id': row.get('rule_id'),
                    'updated_at': func.now(),
                }
                for row in rows
            ]
            stmt = pg_insert(tbl).values(values)
            stmt = stmt.on_conflict_do_update(
                index_elements=[tbl.c.symbol, tbl.c.direction],
                set_={
                    'notified_at': stmt.excluded.notified_at,
                    'trigger_id': stmt.excluded.trigger_id,
                    'rule_id': stmt.excluded.rule_id,
                    'updated_at': func.now(),
                },
            )
            session = get_session()
            session.execute(stmt)
            session.commit()
        except Exception as e:
            logger.error('去重窗写入失败', error=str(e), rows=len(rows))
            _safe_rollback()
            raise

    def prune_dedup(self, cutoff) -> int:
        """删除 notified_at < cutoff 的去重键（有界：窗口外的键不再保留）"""
        try:
            session = get_session()
            deleted = (
                session.query(WatchRuntimeDedup)
                .filter(WatchRuntimeDedup.notified_at < cutoff)
                .delete(synchronize_session=False)
            )
            session.commit()
            return int(deleted or 0)
        except Exception as e:
            logger.error('去重窗裁剪失败', error=str(e))
            _safe_rollback()
            raise

    # ── 触发事件窗口（返工 C）───────────────────────────────

    def load_events(self, since=None) -> List[Dict[str, Any]]:
        """窗口内触发事件（since 为 None 则全部）。

        每行：{triggered_at, rule_id, symbol}；调用方自行按保留窗口再过滤一次。
        """
        try:
            q = get_session().query(
                WatchTriggerEvent.triggered_at,
                WatchTriggerEvent.rule_id,
                WatchTriggerEvent.symbol,
            )
            if since is not None:
                q = q.filter(WatchTriggerEvent.triggered_at >= since)
            rows = q.order_by(WatchTriggerEvent.triggered_at.asc()).all()
        except Exception:
            _safe_rollback()
            raise
        return [{'triggered_at': r[0], 'rule_id': r[1], 'symbol': r[2]} for r in rows]

    def append_events(self, rows: List[Dict[str, Any]]) -> None:
        """追加触发事件；主键冲突（重试/重复）时忽略——幂等，不产生重复计数。"""
        if not rows:
            return
        try:
            tbl = WatchTriggerEvent.__table__
            values = [
                {
                    'triggered_at': row['triggered_at'],
                    'rule_id': int(row['rule_id']),
                    'symbol': row['symbol'],
                }
                for row in rows
            ]
            stmt = pg_insert(tbl).values(values).on_conflict_do_nothing(
                index_elements=[tbl.c.triggered_at, tbl.c.rule_id, tbl.c.symbol],
            )
            session = get_session()
            session.execute(stmt)
            session.commit()
        except Exception as e:
            logger.error('触发事件写入失败', error=str(e), rows=len(rows))
            _safe_rollback()
            raise

    def prune_events(self, cutoff) -> int:
        """删除 triggered_at < cutoff 的事件（有界：保留窗口外的统计不再需要）"""
        try:
            session = get_session()
            deleted = (
                session.query(WatchTriggerEvent)
                .filter(WatchTriggerEvent.triggered_at < cutoff)
                .delete(synchronize_session=False)
            )
            session.commit()
            return int(deleted or 0)
        except Exception as e:
            logger.error('触发事件裁剪失败', error=str(e))
            _safe_rollback()
            raise

    # ── 价格历史（返工 C）───────────────────────────────────

    def load_price_history(self, symbols=None, since=None) -> List[Dict[str, Any]]:
        """窗口内价格历史。

        symbols 非空时只取这些标的（**有界恢复口径**：只恢复启用规则覆盖的标的，
        不把历史全表拉进内存）；since 为窗口左界。
        每行：{symbol, ts, price}
        """
        try:
            q = get_session().query(
                WatchPriceHistory.symbol,
                WatchPriceHistory.ts,
                WatchPriceHistory.price,
            )
            if symbols:
                q = q.filter(WatchPriceHistory.symbol.in_(list(symbols)))
            if since is not None:
                q = q.filter(WatchPriceHistory.ts >= since)
            rows = q.order_by(WatchPriceHistory.ts.asc()).all()
        except Exception:
            _safe_rollback()
            raise
        return [{'symbol': r[0], 'ts': r[1], 'price': r[2]} for r in rows]

    def upsert_price_history(self, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        try:
            tbl = WatchPriceHistory.__table__
            values = [
                {
                    'symbol': row['symbol'],
                    'ts': row['ts'],
                    'price': float(row['price']),
                }
                for row in rows
            ]
            stmt = pg_insert(tbl).values(values)
            stmt = stmt.on_conflict_do_update(
                index_elements=[tbl.c.symbol, tbl.c.ts],
                set_={'price': stmt.excluded.price},
            )
            session = get_session()
            session.execute(stmt)
            session.commit()
        except Exception as e:
            logger.error('价格历史写入失败', error=str(e), rows=len(rows))
            _safe_rollback()
            raise

    def prune_price_history(self, cutoff) -> int:
        """删除 ts < cutoff 的价格点（有界：只保留 velocity 窗口所需）"""
        try:
            session = get_session()
            deleted = (
                session.query(WatchPriceHistory)
                .filter(WatchPriceHistory.ts < cutoff)
                .delete(synchronize_session=False)
            )
            session.commit()
            return int(deleted or 0)
        except Exception as e:
            logger.error('价格历史裁剪失败', error=str(e))
            _safe_rollback()
            raise

"""Watch 旁路宿主：持仓联动、消息、市场映射、回填与日报，不含股票判定主链。"""
import threading
from datetime import datetime, time
from typing import Any, Callable, Dict, Optional

import structlog

from qs_trading.domain.trading.services.market_session_policy import (
    TOTAL_TRADING_MINUTES,
    MarketSessionPolicy,
)

logger = structlog.get_logger(__name__)


def elapsed_trading_fraction(now: datetime) -> float:
    return MarketSessionPolicy.session_progress(now.time(), is_trading_day=True)


class WatchEngine:
    def __init__(self, rule_repo=None, quote_service=None, notifier=None,
                 now_fn: Callable[[], datetime] = datetime.now,
                 digest_service=None, meta_review_service=None,
                 position_lifecycle_service=None, market_watch_service=None,
                 pool_watch_service=None, news_watch_service=None,
                 outcome_backfill_service=None, trigger_repo=None,
                 name_resolver=None, **_legacy):
        self.rule_repo = rule_repo
        self.now_fn = now_fn
        self.digest_service = digest_service
        self.meta_review_service = meta_review_service
        self.position_lifecycle_service = position_lifecycle_service
        self.market_watch_service = market_watch_service
        self.pool_watch_service = pool_watch_service
        self.news_watch_service = news_watch_service
        self.outcome_backfill_service = outcome_backfill_service
        self._trigger_repo = trigger_repo or getattr(notifier, 'trigger_repo', None)
        self._name_resolver = name_resolver or getattr(notifier, '_name_resolver', None)
        self._last_meta_scan_date = None
        self._last_lifecycle_date = None
        self._last_pool_sync_date = None
        self._last_review_sent_date = None
        self._last_held_map_date = None
        self._last_outcome_backfill_date = None
        self._sidecar_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._stopped = False

    @staticmethod
    def is_trading_time(value: time) -> bool:
        return MarketSessionPolicy.is_market_open(
            MarketSessionPolicy.phase_for(value, is_trading_day=True))

    def stop(self) -> None:
        self._stopped = True
        self._stop_event.set()

    def get_metrics(self) -> Dict[str, Any]:
        return {
            'sidecar_running': bool(self._sidecar_thread and self._sidecar_thread.is_alive()),
        }

    def _ensure_sidecar_thread(self):
        if self._sidecar_thread is not None:
            return self._sidecar_thread

        def _loop():
            while not self._stopped:
                try:
                    self._run_sidecar(self.now_fn())
                except Exception as exc:  # noqa: BLE001
                    logger.error('sidecar 巡检异常', error=str(exc))
                finally:
                    try:
                        from qs_kernel.infrastructure.persistence.orm import close_session
                        close_session()
                    except Exception:
                        pass
                self._stop_event.wait(30)

        self._sidecar_thread = threading.Thread(
            target=_loop, name='watch-sidecar', daemon=True)
        self._sidecar_thread.start()
        logger.info('WatchEngine sidecar 线程已启动')
        return self._sidecar_thread

    def _run_sidecar(self, now) -> None:
        from qs_ops.application.services.trading_day_guard import TradingDayGuard
        if not TradingDayGuard.is_trading_day(now.date()):
            return
        if not self.is_trading_time(now.time()):
            self._run_sidecar_offhours(now)
            return
        from infrastructure.persistence.orm import close_session
        self._run_block('摘要门', lambda: self.digest_service.maybe_wake(now)
                        if self.digest_service is not None else None, close_session)
        if self.meta_review_service is not None and self._last_meta_scan_date != now.date():
            def _meta():
                summary = self.meta_review_service.scan(now)
                self._last_meta_scan_date = now.date()
                if summary.get('raised'):
                    logger.info('元触发复核完成', raised=summary['raised'])
            self._run_block('元触发复核', _meta, close_session)
        if self.position_lifecycle_service is not None and self._last_lifecycle_date != now.date():
            def _lifecycle():
                result = self.position_lifecycle_service.reconcile(now)
                self.position_lifecycle_service.expire_overdue_rules(now)
                self._last_lifecycle_date = now.date()
                if result.get('retired') or result.get('created'):
                    logger.info('持仓生命周期联动完成', retired=result['retired'], created=result['created'])
            self._run_block('持仓生命周期', _lifecycle, close_session)
        if self.market_watch_service is not None and self._last_held_map_date != now.date():
            def _held_map():
                self.market_watch_service.refresh_held_boards()
                self._last_held_map_date = now.date()
            self._run_block('持仓板块映射', _held_map, close_session)
        if self.outcome_backfill_service is not None and self._last_outcome_backfill_date != now.date():
            def _backfill():
                result = self.outcome_backfill_service.backfill(now)
                self._last_outcome_backfill_date = now.date()
                if result.get('filled') or result.get('failed'):
                    logger.info('走势回填完成', filled=result['filled'], failed=result['failed'])
            self._run_block('走势回填', _backfill, close_session)
        if self.pool_watch_service is not None and self._last_pool_sync_date != now.date():
            def _pool():
                result = self.pool_watch_service.reconcile_all(now)
                self._last_pool_sync_date = now.date()
                created = sum(int(item.get('created') or 0) for item in result)
                if created or len(result) > 1:
                    logger.info('池盯盘对账完成', bindings=len(result), created=created)
            self._run_block('池盯盘对账', _pool, close_session)
        if self.news_watch_service is not None:
            self._run_block('消息监控', lambda: self.news_watch_service.scan(now), close_session)

    @staticmethod
    def _run_block(name, fn, close_session) -> None:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            logger.error('%s异常' % name, error=str(exc))
        finally:
            close_session()

    def _run_sidecar_offhours(self, now) -> None:
        from infrastructure.persistence.orm import close_session
        if self.news_watch_service is not None:
            self._run_block('消息监控（盘后）', lambda: self.news_watch_service.scan(now), close_session)
        if self._last_review_sent_date != now.date():
            self._run_block('收盘体检日报', lambda: self._send_daily_review(now), close_session)
            self._last_review_sent_date = now.date()

    def _send_daily_review(self, now) -> None:
        repo = self._trigger_repo
        if repo is None:
            return
        rows = repo.list_triggers(dispositions=('meta_review',), limit=50) or []
        if not rows:
            return
        names = {}
        symbols = sorted({str(item.symbol).split('.')[0] for item in rows})
        if self._name_resolver is not None:
            try:
                names = self._name_resolver.resolve_batch(symbols) or {}
            except Exception as exc:  # noqa: BLE001
                logger.debug('日报名称解析失败', error=str(exc))

        def display(symbol):
            bare = str(symbol).split('.')[0]
            return '%s（%s）' % (names.get(bare) or bare, bare)

        lines = ['今日规则体检：%d 条待处理（调阈值/退役/补激活后自动消失）：' % len(rows)]
        for item in rows[:8]:
            lines.append('• 规则#%s %s：%s' % (
                item.rule_id, display(item.symbol), (item.disposition_reason or '')[:60]))
        if len(rows) > 8:
            lines.append('• …另有 %d 条（详情查 watch_triggers）' % (len(rows) - 8))
        try:
            handled = [item for item in repo.list_triggers(
                dispositions=('handled', 'ignored', 'expired'), limit=300)
                if getattr(item, 'disposition_at', None)
                and item.disposition_at.date() == now.date()]
            if handled:
                lines.extend(['', '今日已处置 %d 条（agent/人）：' % len(handled)])
                for item in handled[:6]:
                    lines.append('• 规则#%s %s → %s：%s' % (
                        item.rule_id, display(item.symbol), item.disposition,
                        (item.disposition_reason or '')[:50]))
                if len(handled) > 6:
                    lines.append('• …另有 %d 条' % (len(handled) - 6))
        except Exception as exc:  # noqa: BLE001
            logger.warning('处置段生成失败（日报继续）', error=str(exc))
        from qs_watch.application.services.watch_engine.watch_channels import send_watch_receipt
        ok = send_watch_receipt({'kind': 'daily_review', 'message': '\n'.join(lines), 'level': 'P2'})
        if not ok:
            logger.warning('收盘体检日报未送达', count=len(rows))

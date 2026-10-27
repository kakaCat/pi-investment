"""账户行情异步刷新（RFC 017 P2，2026-10-27，w-7e3880c6）

背景：账户状态接口在请求内同步拉外盘行情（2026-10-26 实测 11~18s），
P0 已把路由迁到线程池并加埋点，但读路径等待外盘的本质没变。本服务把刷新
从读路径剥离：POST /quotes/refresh → 202 + 后台线程，看板轮询 /overview
读取 DB 快照；下一次轮询自然看到新价格。

约束（与 RFC 017 §5.2 对齐）：
  · single-flight：同账户重复请求合并，15s 轮询 + 多窗口不形成请求风暴；
  · 刷新失败保留最后有效快照（不写空值/不擦价格），错误进 last 状态；
  · 刷新时间戳来自实际行情数据时点（由 QuoteData.timestamp 提供），
    绝不用「任务完成时间」冒充行情时点；
  · 只更新价格，不触发任何交易/风控动作。
"""
import logging
import threading
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class QuoteRefreshService:
    """按账户单飞的后台行情刷新器（进程内单例语义由调用方持有）。

    Args:
        service: SimulationService 实例（提供 repo 与 _fetch_current_prices）。
                 共享单例是安全的：P0 已移除请求级可变状态（_price_timestamps），
                 repo 的 Session 按线程现取（scoped_session）。
    """

    def __init__(self, service):
        self._service = service
        self._lock = threading.Lock()
        self._inflight: set = set()
        self._last: Dict[str, dict] = {}

    def schedule(self, account_name: str) -> dict:
        """触发一次后台刷新，立即返回（不阻塞调用方）。

        已存在同账户刷新时合并（coalesced=True），不重复拉行情。
        """
        with self._lock:
            if account_name in self._inflight:
                return {'accepted': True, 'coalesced': True, 'account': account_name,
                        'last': self._last.get(account_name)}
            self._inflight.add(account_name)
        thread = threading.Thread(
            target=self._run, args=(account_name,),
            name=f'quote-refresh-{account_name}', daemon=True,
        )
        thread.start()
        with self._lock:
            last = self._last.get(account_name)
        return {'accepted': True, 'coalesced': False, 'account': account_name, 'last': last}

    def last(self, account_name: str) -> Optional[dict]:
        with self._lock:
            return self._last.get(account_name)

    def _run(self, account_name: str) -> None:
        started = time.monotonic()
        status = 'failed'
        error: Optional[str] = None
        prices_count = 0
        symbols_count = 0
        try:
            positions = self._service.repo.get_all_positions(account_name)
            symbols = [p.symbol for p in positions if getattr(p, 'symbol', None)]
            symbols_count = len(symbols)
            if not symbols:
                status = 'skipped'  # 空仓无需刷新
            else:
                prices, _timestamps = self._service._fetch_current_prices(symbols)
                prices_count = len(prices)
                if prices:
                    self._service.repo.update_position_prices(account_name, prices)
                    status = 'success' if len(prices) == len(set(symbols)) else 'partial'
                else:
                    error = '行情源未返回任何价格（保留最后有效快照）'
        except Exception as exc:  # noqa: BLE001 - 后台线程不得因刷新失败崩掉进程
            error = str(exc)
            logger.exception('quote refresh failed account=%s', account_name)
        finally:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            with self._lock:
                self._inflight.discard(account_name)
                self._last[account_name] = {
                    'status': status,
                    'at': time.time(),
                    'elapsed_ms': elapsed_ms,
                    'prices': prices_count,
                    'symbols': symbols_count,
                    'error': error,
                }

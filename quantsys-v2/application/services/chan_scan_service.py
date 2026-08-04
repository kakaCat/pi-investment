"""缠论买卖点池内扫描服务

每日收盘后对全部股票池成员跑缠论分析，把最近交易日新出现的买卖点
写入 signals 表（strategy_id='chan_1买' 等），供：
- signals_ready 推送链路（SignalExecutionScheduler._collect_signals 按日期捞 pending）
- heatmap / verify_judgments 验证（strategy_id 字符串直接展示）
- chan_knowledge_distill 周度胜率蒸馏

confidence 按 0-100 存储（缠论 0-1 × 100），与 agent 决策链"强度≥70"习惯对齐。
"""
from typing import Dict, Any, List
import structlog

from application.services.chan_service import ChanService
from adapters.outbound.repositories.stock_pool_repository import StockPoolORMRepository
from adapters.outbound.repositories.signal_repository import SignalORMRepository

logger = structlog.getLogger(__name__)

# 只落买点（卖点 detector 未实现，见 spec YAGNI）
_BUY_TYPES = {'1买', '2买', '3买'}


class ChanScanService:
    """池内股票缠论买卖点扫描"""

    def __init__(self):
        # 注意：依赖在模块顶部 import（非 __init__ 内 lazy import），
        # 否则测试 patch 'application.services.chan_scan_service.X' 会 AttributeError
        self._chan = ChanService()
        self._pool_repo = StockPoolORMRepository()
        self._signal_repo = SignalORMRepository()

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """统一为无后缀形式：stocks/signals 表全部无后缀，
        signals.symbol 有 FK → stocks.symbol，带后缀写入会 FK 冲突。
        K 线 repo 内部本就会去后缀，无后缀全链路通用。"""
        return symbol.split('.')[0] if '.' in symbol else symbol

    def _pool_symbols(self) -> List[Dict[str, str]]:
        """全部池成员去重 [{symbol, name}]（scan_enabled=False 的池跳过；
        symbol 统一归一为无后缀，避免 002475 与 002475.SZ 重复扫描+FK 冲突）"""
        seen: Dict[str, str] = {}
        for pool in self._pool_repo.get_all():
            if not pool.get('scan_enabled', True):
                continue
            for m in pool.get('members') or []:
                raw = m.get('symbol') if isinstance(m, dict) else str(m)
                name = m.get('name', '') if isinstance(m, dict) else ''
                symbol = self._normalize_symbol(raw) if raw else ''
                if symbol and symbol not in seen:
                    seen[symbol] = name
        return [{'symbol': s, 'name': n} for s, n in seen.items()]

    def scan(self) -> Dict[str, Any]:
        """扫描全部池成员，落当日新买卖点。返回计数汇总。"""
        stocks = self._pool_symbols()
        written = duplicates = skipped = errors = 0

        for stock in stocks:
            symbol, name = stock['symbol'], stock['name']
            try:
                result = self._chan.analyze(symbol)
                klines = result.get('klines') or []
                if not klines:
                    skipped += 1
                    continue
                latest_date = klines[-1]['date']

                for bp in result.get('buypoints') or []:
                    if bp['type'] not in _BUY_TYPES or bp['date'] != latest_date:
                        continue
                    signal_id = self._signal_repo.create_signal({
                        'signal_date': bp['date'],
                        'symbol': symbol,
                        'name': name,
                        'action': 'buy',
                        'strategy_id': f"chan_{bp['type']}",
                        'price': bp['price'],
                        'confidence': round(bp['confidence'] * 100, 1),
                        'reason': f"缠论{bp['type']}：{bp['reason']}",
                        'status': 'pending',
                    })
                    if signal_id:
                        written += 1
                        logger.info(f"缠论信号落库: {symbol} {bp['type']} @ {bp['price']} (id={signal_id})")
                    else:
                        duplicates += 1
            except Exception as e:
                errors += 1
                logger.warning(f"缠论扫描 {symbol} 失败: {e}")

        summary = {
            'scanned': len(stocks),
            'signals_written': written,
            'duplicates': duplicates,
            'skipped': skipped,
            'errors': errors,
        }
        logger.info(f"缠论扫描完成: {summary}")
        return summary

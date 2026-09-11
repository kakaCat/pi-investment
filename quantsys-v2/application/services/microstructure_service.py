"""微观结构应用服务：分钟线 / 交易状态 / 执行成本估算

RFC 015 §4.2（2026-09-11 REQ-cf627b）。应用层只做**编排**：
- 领域判定（ST/停牌/涨跌停/可交易）在 domain.trading.services.TradingStatusPolicy
- 多源取数与故障转移在 adapters.outbound.datasources.manager（本层只依赖注入）
- 具体实现的装配（组合根）在入站适配器
  adapters/inbound/fastapi_app/routes/microstructure_async.py

依赖方向（ADR-001 红线）：本文件**不得出现任何 adapters 导入**（含函数内局部导入），
所有出站依赖通过构造函数注入，类型注解一律用 domain 侧端口/模型。
"""
import statistics
from dataclasses import asdict, is_dataclass, replace
from datetime import date as _date, datetime
from typing import Any, Dict, List, Optional

import structlog

from domain.trading.models.trading_status import TradingStatus
from domain.trading.services.trading_status_policy import TradingStatusPolicy

logger = structlog.get_logger(__name__)

# 周期 → 分钟数（provider 侧有同样的一份；本层用于入参快速校验，
# 避免把非法周期打到所有数据源上）
_PERIOD_MINUTES = {
    '1': 1, '1m': 1, '5': 5, '5m': 5, '15': 15, '15m': 15,
    '30': 30, '30m': 30, '60': 60, '60m': 60, '1h': 60,
}

# 冲击成本模型的显式假设（透明可复核，非拟合参数）
_IMPACT_ALPHA = 1.0          # 线性临时冲击系数（Almgren-Chriss 线性近似）
_SPREAD_BPS = 0.0            # 占位：价差按「半跳」计算，见 _half_spread_bps
_TICK_CNY = 0.01             # A股最小报价单位（元）


class MicrostructureService:
    """分钟线 / 交易状态 / 执行成本估算用例编排"""

    def __init__(self, manager=None, status_repo=None, policy: Optional[TradingStatusPolicy] = None):
        """
        Args:
            manager: IDataProviderManager（分钟线多源 + 实时行情）——由组合根注入
            status_repo: ITradingStatusRepository（stocks 表基础状态）——由组合根注入
            policy: TradingStatusPolicy（缺省新建；纯领域对象，可直接构造）
        """
        self._manager = manager
        self._status_repo = status_repo
        self._policy = policy or TradingStatusPolicy()

    # ------------------------------------------------------------------ 依赖

    def _require_manager(self):
        if self._manager is None:
            raise RuntimeError(
                "MicrostructureService 需要注入 IDataProviderManager（组合根见 "
                "adapters/inbound/fastapi_app/routes/microstructure_async.py）"
            )
        return self._manager

    def _require_status_repo(self):
        if self._status_repo is None:
            raise RuntimeError(
                "MicrostructureService 需要注入 ITradingStatusRepository（组合根见 "
                "adapters/inbound/fastapi_app/routes/microstructure_async.py）"
            )
        return self._status_repo

    @staticmethod
    def _strip_verdict(reason: str) -> str:
        """去掉策略 reason 结尾的「可交易/不可交易」结论词（调用方要改写结论时用）"""
        for tail in ('；不可交易', '；可交易'):
            if reason.endswith(tail):
                return reason[: -len(tail)]
        return reason

    # -------------------------------------------------------------- 分钟线

    @staticmethod
    def _normalize_period(period: str) -> str:
        """'5' / '5m' → '5m'；非法周期抛 ValueError（fail-loud，不静默兜底）"""
        key = str(period or '').strip().lower()
        if key not in _PERIOD_MINUTES:
            raise ValueError(f"不支持的分钟周期: {period!r}（支持 1m/5m/15m/30m/60m）")
        return f"{_PERIOD_MINUTES[key]}m"

    def get_minute_klines(
        self,
        symbol: str,
        period: str = '5m',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 240,
    ) -> Dict[str, Any]:
        """分钟线多源取数（RFC 015 §1.5.3 统一响应契约）

        Returns:
            {success, data, source, attempted_sources, degraded, stale, as_of, ...}
            全源**硬失败** → success=False + error + provider_errors（**显式失败**，
            绝不返回空数组冒充成功）。
            全源**健康但无数据**（2026-09-11『空结果≠故障』契约对齐）→ success=False +
            empty=True + error（对**调用方**而言仍无分钟线可用，故 success 保持 False；
            区别在于 provider_errors 里是带 last_note 的空结果说明而非故障文本，
            调用方能据此区分「这个查询确实没有数据」与「源挂了」——两者此前同形）。
        """
        manager = self._require_manager()
        label = self._normalize_period(period)
        resp = manager.get_minute_klines(
            symbol, label, start_date=start_date, end_date=end_date, limit=int(limit or 240),
        )
        as_of = datetime.now().isoformat()

        if not resp.get('success'):
            # manager 已按契约区分两种「没数据」：全源健康空 → success=True+empty=True（走下面）；
            # 走到这里说明存在**硬失败**（异常/超时/熔断/自报 last_error），是显式失败。
            return {
                'success': False,
                'data': None,
                'source': None,
                'attempted_sources': resp.get('attempted_sources') or [],
                'provider_errors': resp.get('provider_errors') or {},
                'empty_sources': resp.get('empty_sources') or [],
                'degraded': True,
                'stale': False,
                'empty': False,
                'error': resp.get('error') or '分钟线取数失败',
                'period': label,
                'as_of': as_of,
            }

        bars: List[Any] = resp.get('data') or []
        if not bars:
            # 2026-09-11『空结果≠故障』：manager 现在会用 success=True+empty=True 表达
            # 「所有源都健康地回答了：这个查询没有数据」。对调用方而言仍然没有分钟线可用，
            # 故 success 保持 False（消费者语义不变），但必须显式标 empty=True 并把
            # 空源清单与诊断文本透出——此前这条分支的注释假设「成功路径不会带空列表」，
            # 该假设已随契约对齐失效。
            return {
                'success': False,
                'data': None,
                'source': resp.get('source'),
                'attempted_sources': resp.get('attempted_sources') or [],
                'provider_errors': resp.get('provider_errors') or {},
                'empty_sources': resp.get('empty_sources') or [],
                'degraded': True,
                'stale': False,
                'empty': True,
                'error': '全源健康但无数据（该标的/时段确实无分钟线，非源故障）',
                'period': label,
                'as_of': as_of,
            }

        source = resp.get('source')
        latest_dt = str(getattr(bars[-1], 'trade_datetime', ''))[:10]
        today = _date.today().isoformat()
        stale = (source == 'database_minute') or (latest_dt != today)
        attempted = resp.get('attempted_sources') or []
        degraded = bool(source == 'database_minute' or len(attempted) > 1)

        data = [asdict(b) if is_dataclass(b) else dict(vars(b)) for b in bars]
        return {
            'success': True,
            'data': data,
            'count': len(data),
            'period': label,
            'source': source,
            'attempted_sources': attempted,
            'degraded': degraded,
            'stale': stale,
            'latest_bar': str(getattr(bars[-1], 'trade_datetime', '')),
            'granularity': resp.get('granularity') or label,
            'cross_source_conflict': None,  # 分钟线单源故障转移；跨源比对见 cross_check_minute_klines
            'as_of': as_of,
        }

    def cross_check_minute_klines(
        self,
        symbol: str,
        period: str = '5m',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 240,
    ) -> Dict[str, Any]:
        """跨源一致性校验（RFC 015 §1.5 硬约束 6）

        同一标的同时向 ≥2 个独立通道取数，比对共同时间戳上的收盘价；
        平均相对偏差 > 0.5% 判 divergent 并给出 cross_source_conflict 明细。
        """
        manager = self._require_manager()
        if not hasattr(manager, 'cross_check_minute_klines'):
            return {'success': False, 'error': '数据源管理器不支持跨源校验'}
        label = self._normalize_period(period)
        return manager.cross_check_minute_klines(
            symbol, label, start_date=start_date, end_date=end_date, limit=int(limit or 240),
        )

    # ------------------------------------------------------------ 交易状态

    def get_trading_status(self, symbol: str) -> Dict[str, Any]:
        """下单前交易状态裁决（基础状态 × 实时行情，跨源冲突保守取不可交易）

        Returns:
            {success, data(TradingStatus), source, cross_source_conflict, degraded,
             stale, as_of}
        """
        manager = self._require_manager()
        repo = self._require_status_repo()
        bare = str(symbol or '').split('.')[0]
        as_of = datetime.now().isoformat()

        base = None
        base_error = None
        try:
            base = repo.get_stock_status(bare)
        except Exception as e:  # DB 异常 → 视为基础状态不可得（fail-closed）
            base_error = f'stocks 表查询异常: {type(e).__name__}: {e}'
            logger.warning('trading status base lookup failed', symbol=bare, error=str(e))

        quote = None
        quote_source = None
        quote_error = None
        try:
            qresp = manager.get_quote(bare)
            if qresp.get('success') and qresp.get('data') is not None:
                raw = qresp['data']
                quote = asdict(raw) if is_dataclass(raw) else dict(vars(raw))
                quote_source = qresp.get('source')
            else:
                quote_error = qresp.get('error') or '行情不可用'
        except Exception as e:
            quote_error = f'{type(e).__name__}: {e}'
            logger.warning('trading status quote lookup failed', symbol=bare, error=str(e))

        if base is None:
            # 基础状态缺失（未入库/查询异常）→ fail-closed：即使行情正常也不给"可交易"
            status = self._policy.evaluate({}, quote)
            status = replace(
                status,
                symbol=bare,
                tradeable=False,
                reason=(
                    (base_error or f'stocks 表无 {bare}（无法确认 ST/停牌状态）→ fail-closed 取不可交易')
                    + '；' + self._strip_verdict(status.reason) + '；不可交易'
                ),
            )
            conflicts = self._policy.detect_conflicts({}, quote)
            return {
                'success': False,
                'data': status.to_dict(),
                'source': f'quote:{quote_source}' if quote_source else 'none',
                'sources': {'base': None, 'quote': quote_source},
                'cross_source_conflict': conflicts or None,
                'degraded': True,
                'stale': False,
                'error': base_error or f'stocks 表无 {bare}：无法确认基础交易状态',
                'as_of': as_of,
            }

        status = self._policy.evaluate(base, quote)
        conflicts = self._policy.detect_conflicts(base, quote)
        return {
            'success': True,
            'data': status.to_dict(),
            'source': f"stocks_table+{quote_source}" if quote_source else 'stocks_table',
            'sources': {'base': 'stocks_table', 'quote': quote_source},
            'cross_source_conflict': conflicts or None,
            'degraded': quote is None,   # 行情缺失=降级：仅按基础状态判定
            'stale': False,
            'quote_error': quote_error,
            'as_of': as_of,
        }

    # -------------------------------------------------------- 执行成本估算

    @staticmethod
    def _half_spread_bps(price: float) -> float:
        """半价差代理（bps）：A股最小报价单位 0.01 元 → 半跳 = 0.005 元

        说明：分钟K线不含盘口价差，这里用「半跳」作保守代理（流动性好的票
        实际价差≈1 跳，冷门票更宽 → 结果是下界）。口径写死在此，便于复核。
        """
        if not price or price <= 0:
            return 0.0
        return (_TICK_CNY / 2) / price * 10000

    def estimate_execution(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """用近期分钟线估算参与率/滑点/冲击成本（供 R-003 拆单决策）

        模型（透明、可复核，非拟合）：
            参与率 participation = 委托量 / 单根 bar 平均成交量（同周期）
            波动 σ_bar           = 5m bar 收益率标准差（bps）
            冲击 impact_bps      = α × σ_bar × participation（α=1，线性临时冲击）
            滑点 slippage_bps    = 半价差代理 + impact_bps
        样本不足（<10 根）→ success=False 明确说不可估，不编造数值。
        """
        manager = self._require_manager()
        side = str(side or '').upper()
        if side not in ('BUY', 'SELL'):
            return {'success': False, 'error': f"side 必须是 BUY/SELL，收到 {side!r}"}
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return {'success': False, 'error': f'quantity 非法: {quantity!r}'}
        if quantity <= 0:
            return {'success': False, 'error': 'quantity 必须为正整数'}

        bars_resp = self.get_minute_klines(str(symbol).split('.')[0], '5m', limit=48)
        if not bars_resp.get('success'):
            return {
                'success': False,
                'error': '分钟线不可得，无法估计执行成本: ' + str(bars_resp.get('error')),
                'attempted_sources': bars_resp.get('attempted_sources') or [],
                'provider_errors': bars_resp.get('provider_errors') or {},
                'as_of': datetime.now().isoformat(),
            }

        bars = bars_resp['data']
        session_date = str(bars[-1]['trade_datetime'])[:10]
        closes = [float(b['close']) for b in bars if b.get('close')]
        volumes = [float(b['volume']) for b in bars if b.get('volume') is not None]

        if len(closes) < 10 or len(volumes) < 10:
            return {
                'success': False,
                'error': (
                    f"分钟线样本不足（仅 {len(closes)} 根 <10），无法估计执行成本——"
                    "数据不足不编造数值"
                ),
                'bars_available': len(closes),
                'session_date': session_date,
                'as_of': datetime.now().isoformat(),
            }

        avg_bar_volume = statistics.fmean(volumes)
        if avg_bar_volume <= 0:
            return {
                'success': False,
                'error': f'分钟线成交量为 0（{session_date}），无法估计执行成本（疑似停牌/无成交）',
                'session_date': session_date,
                'as_of': datetime.now().isoformat(),
            }

        rets = [abs(closes[i] - closes[i - 1]) / closes[i - 1] * 10000
                for i in range(1, len(closes)) if closes[i - 1] > 0]
        vol_bps = statistics.fmean(rets) if rets else 0.0

        ref_price = float(price) if price else closes[-1]
        participation = quantity / avg_bar_volume
        impact_bps = _IMPACT_ALPHA * vol_bps * participation
        spread_bps = self._half_spread_bps(ref_price)
        slippage_bps = spread_bps + impact_bps

        # 建议分档（R-003：单笔金额超日均成交额 1% 应拆单）
        bars_per_day = 48
        daily_volume = avg_bar_volume * bars_per_day
        if participation < 0.01:
            advice = '参与率 <1%：可直接下单，冲击成本可忽略'
        elif participation < 0.05:
            advice = '参与率 1%~5%：建议拆 2~3 笔限价单分批执行'
        elif participation < 0.15:
            advice = '参与率 5%~15%：建议算法拆单（TWAP/VWAP，≥5 笔）执行'
        else:
            advice = ('参与率 >15%：单笔过大，强烈建议算法拆单并延长时间窗，'
                      '或分多日建仓（滑点估计已显著高于常规）')

        # 交易状态门禁（fail-closed 精神）：不可交易或数据陈旧时，给出显式告警并标 reliable=False，
        # 让调用方（R-003 拆单决策）不会把过期/停牌标的的估算当可用结论
        warnings: List[str] = []
        status_block: Optional[Dict[str, Any]] = None
        try:
            st = self.get_trading_status(str(symbol).split('.')[0])
            status_block = {
                'tradeable': (st.get('data') or {}).get('tradeable'),
                'reason': (st.get('data') or {}).get('reason'),
                'success': st.get('success'),
            }
            if st.get('success') is False or status_block['tradeable'] is False:
                warnings.append('当前交易状态为不可交易（停牌/涨停/跨源冲突/基础状态缺失），'
                                '本估算不可直接用于下单决策')
        except Exception as e:  # 状态查询失败不阻断估算，但必须显式告知
            warnings.append(f'交易状态查询失败，未能门禁校验: {type(e).__name__}: {e}')

        if bars_resp.get('stale'):
            warnings.append(
                f'分钟线不是当日数据（最近一根 {bars_resp.get("latest_bar")}，'
                f'source={bars_resp.get("source")}）——样本来自历史会话，估算仅供参考'
            )

        return {
            'success': True,
            'reliable': not warnings,
            'warnings': warnings,
            'trading_status': status_block,
            'data': {
                'symbol': str(symbol).split('.')[0],
                'side': side,
                'quantity': quantity,
                'reference_price': ref_price,
                'notional': round(quantity * ref_price, 2),
                'session_date': session_date,
                'bars_used': len(closes),
                'avg_bar_volume': round(avg_bar_volume, 2),
                'daily_volume_estimate': round(daily_volume, 2),
                'participation_rate': round(participation, 6),
                'participation_pct': round(participation * 100, 4),
                'bar_volatility_bps': round(vol_bps, 2),
                'half_spread_bps': round(spread_bps, 2),
                'impact_bps': round(impact_bps, 3),
                'estimated_slippage_bps': round(slippage_bps, 2),
                'estimated_slippage_pct': round(slippage_bps / 100, 4),
                'model': 'slippage_bps = 半价差(0.5 tick) + 1.0 × 5m波动(bps) × 参与率',
                'advice': advice,
            },
            'source': bars_resp.get('source'),
            'attempted_sources': bars_resp.get('attempted_sources') or [],
            'degraded': bool(bars_resp.get('degraded')),
            'stale': bool(bars_resp.get('stale')),
            'as_of': datetime.now().isoformat(),
        }


_service_instance: Optional[MicrostructureService] = None


def set_microstructure_service(service: Optional[MicrostructureService]) -> None:
    """组合根注入单例（由入站适配器调用）"""
    global _service_instance
    _service_instance = service


def get_microstructure_service() -> Optional[MicrostructureService]:
    """取已装配的服务实例（未装配返回 None，由调用方给出显式错误）"""
    return _service_instance

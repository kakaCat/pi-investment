"""
ZigZag 波段分析服务 - 基于历史价格波动识别买卖点

算法原理：
1. 从第一个数据点开始，追踪当前趋势方向（上涨/下跌）
2. 当价格反转超过 min_change（百分比），确认一个拐点
3. 局部低点 = 买点，局部高点 = 卖点
4. 最终输出所有买卖点序列及收益统计
"""
import structlog
from typing import Dict, List, Optional
from datetime import datetime

from adapters.outbound.repositories import KlineORMRepository
from application.services.stock_code_validator import StockCodeValidator

logger = structlog.get_logger(__name__)

# 常量
DEFAULT_MIN_CHANGE = 5.0       # 默认最小波动幅度 5%
DEFAULT_LOOKBACK_DAYS = 365    # 默认回溯 1 年
MIN_CHANGE_LOWER = 1.0         # 最小波动下限 1%
MIN_CHANGE_UPPER = 30.0        # 最小波动上限 30%


class SwingPointService:
    """ZigZag 波段分析服务"""

    def __init__(self):
        self.kline_repo = KlineORMRepository()
        self.validator = StockCodeValidator()

    def analyze(self, params: Dict) -> Dict:
        """
        识别历史买卖点（ZigZag 算法）

        Args:
            params: {
                symbol: 股票代码（必填）
                start_date: 开始日期 YYYY-MM-DD（可选，默认1年前）
                end_date: 结束日期 YYYY-MM-DD（可选，默认今天）
                min_change: 最小波动幅度百分比（可选，默认5.0）
            }

        Returns:
            {
                symbol, period, min_change,
                swing_points: [{date, price, type, change_pct}, ...],
                trades: [{buy_date, buy_price, sell_date, sell_price, profit_pct, holding_days}, ...],
                summary: {total_trades, win_count, win_rate, total_return, avg_return, max_return, max_loss, avg_holding_days}
            }
        """
        # 1. 参数验证
        symbol = params.get('symbol')
        if not symbol:
            raise ValueError("缺少必填参数: symbol")

        # 1.5 股票代码预验证（优化：减少无效查询）
        validation = self.validator.validate(symbol)
        if not validation['valid']:
            return {
                'symbol': symbol,
                'error': 'K线数据不足（需要至少3根），实际获取: 0',
                'suggestions': validation['suggestions'],
                'kline_count': 0,
                'period': {'start': params.get('start_date', ''), 'end': params.get('end_date', '')},
                'validation': validation
            }

        min_change = float(params.get('min_change', DEFAULT_MIN_CHANGE))
        if min_change < MIN_CHANGE_LOWER or min_change > MIN_CHANGE_UPPER:
            raise ValueError(
                f"min_change 必须在 {MIN_CHANGE_LOWER}% ~ {MIN_CHANGE_UPPER}% 之间，"
                f"当前值: {min_change}%"
            )

        end_date = params.get('end_date') or datetime.now().strftime('%Y-%m-%d')
        start_date = params.get('start_date')
        if not start_date:
            # 默认回溯 1 年
            from dateutil.relativedelta import relativedelta
            start_dt = datetime.strptime(end_date, '%Y-%m-%d') - relativedelta(years=1)
            start_date = start_dt.strftime('%Y-%m-%d')

        # 2. 获取 K 线数据
        klines_df = self.kline_repo.get_daily_klines(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )

        # Polars DataFrame → list of dicts
        if klines_df is not None and len(klines_df) > 0:
            klines = klines_df.to_dicts()
        else:
            klines = []

        # 3. 数据不足时的Fallback机制
        if not klines or len(klines) < 3:
            kline_count = len(klines) if klines else 0

            # 优化：如果是用户指定的日期范围且数据不足，尝试扩大范围
            if params.get('start_date') and kline_count > 0:
                logger.info(f"K线数据不足({kline_count}条)，尝试扩大日期范围")
                # 扩展到2年
                from dateutil.relativedelta import relativedelta
                extended_start = (datetime.strptime(end_date, '%Y-%m-%d') - relativedelta(years=2)).strftime('%Y-%m-%d')

                klines_df = self.kline_repo.get_daily_klines(
                    symbol=symbol,
                    start_date=extended_start,
                    end_date=end_date,
                )

                if klines_df is not None and len(klines_df) >= 3:
                    klines = klines_df.to_dicts()
                    logger.info(f"扩大日期范围后获取到 {len(klines)} 条K线数据")
                    # 继续执行分析
                else:
                    klines = []

            # 如果仍然不足，返回错误
            if not klines or len(klines) < 3:
                kline_count = len(klines) if klines else 0
                error_msg = f"K线数据不足（需要至少3根），实际获取: {kline_count}"

                suggestions = []
                if kline_count == 0:
                    suggestions.append("该股票代码可能不存在或尚未录入数据")
                    suggestions.append("请检查股票代码是否正确（如：600519、000001）")
                    # 查询该股票是否有任何历史数据
                    all_klines_df = self.kline_repo.get_daily_klines(symbol=symbol, start_date='1990-01-01', end_date=end_date)
                    if all_klines_df is not None and len(all_klines_df) > 0:
                        first_date = all_klines_df[0]['trade_date']
                        last_date = all_klines_df[-1]['trade_date']
                        suggestions.append(f"该股票有历史数据：{first_date} ~ {last_date} 共{len(all_klines_df)}条")
                else:
                    suggestions.append(f"当前日期范围 {start_date} ~ {end_date} 数据不足")
                    suggestions.append("建议：扩大日期范围或使用默认的1年回溯期")

                return {
                    'symbol': symbol,
                    'error': error_msg,
                    'suggestions': suggestions,
                    'period': {'start': start_date, 'end': end_date},
                    'kline_count': kline_count,
                }

        # 4. 运行 ZigZag 算法
        swing_points = self._zigzag(klines, min_change / 100.0)

        if len(swing_points) < 2:
            return {
                'symbol': symbol,
                'period': {'start': start_date, 'end': end_date},
                'min_change': min_change,
                'swing_points': swing_points,
                'trades': [],
                'summary': self._empty_summary(),
                'message': f"在 {min_change}% 波动阈值下未找到足够的拐点，建议降低 min_change",
            }

        # 4. 配对交易（低点买入 → 高点卖出）
        trades = self._pair_trades(swing_points)

        # 5. 统计
        summary = self._compute_summary(trades)

        return {
            'symbol': symbol,
            'period': {'start': start_date, 'end': end_date},
            'min_change': min_change,
            'kline_count': len(klines),
            'swing_points': swing_points,
            'trades': trades,
            'summary': summary,
        }

    # ──────────────────────────────────────────────────────────

    def _zigzag(self, klines: List[Dict], threshold: float) -> List[Dict]:
        """
        ZigZag 核心算法

        Args:
            klines: K线数据列表（按日期升序），每条包含 date/trade_date, high, low, close
            threshold: 最小反转幅度（小数，如 0.05 = 5%）

        Returns:
            拐点列表 [{date, price, type: 'high'|'low', index}, ...]
        """
        if len(klines) < 2:
            return []

        def _date(k):
            return k.get('date') or k.get('trade_date', '')

        def _high(k):
            return float(k.get('high', k.get('close', 0)))

        def _low(k):
            return float(k.get('low', k.get('close', 0)))

        # 初始化：用前两根 K 线决定初始方向
        first_high = _high(klines[0])
        first_low = _low(klines[0])

        # 追踪当前极值
        last_high = first_high
        last_high_idx = 0
        last_low = first_low
        last_low_idx = 0

        # 确定初始趋势方向
        # 向前扫描找到第一个超过阈值的波动
        trend = 0  # 1=上涨, -1=下跌, 0=未定
        for i in range(1, len(klines)):
            h = _high(klines[i])
            lo = _low(klines[i])

            if h > first_low * (1 + threshold):
                trend = 1  # 从低点上涨
                last_low_idx = 0
                last_low = first_low
                last_high = h
                last_high_idx = i
                break
            elif lo < first_high * (1 - threshold):
                trend = -1  # 从高点下跌
                last_high_idx = 0
                last_high = first_high
                last_low = lo
                last_low_idx = i
                break
            else:
                # 更新极值
                if h > last_high:
                    last_high = h
                    last_high_idx = i
                if lo < last_low:
                    last_low = lo
                    last_low_idx = i

        if trend == 0:
            # 整个区间波动不足阈值
            return []

        points = []
        start_idx = max(last_high_idx, last_low_idx) + 1

        for i in range(start_idx, len(klines)):
            h = _high(klines[i])
            lo = _low(klines[i])

            if trend == 1:  # 当前上涨中
                if h > last_high:
                    last_high = h
                    last_high_idx = i
                # 从高点回撤超过阈值 → 确认高点，转为下跌
                if lo <= last_high * (1 - threshold):
                    points.append({
                        'date': _date(klines[last_high_idx]),
                        'price': round(last_high, 3),
                        'type': 'high',
                        'index': last_high_idx,
                    })
                    trend = -1
                    last_low = lo
                    last_low_idx = i

            elif trend == -1:  # 当前下跌中
                if lo < last_low:
                    last_low = lo
                    last_low_idx = i
                # 从低点反弹超过阈值 → 确认低点，转为上涨
                if h >= last_low * (1 + threshold):
                    points.append({
                        'date': _date(klines[last_low_idx]),
                        'price': round(last_low, 3),
                        'type': 'low',
                        'index': last_low_idx,
                    })
                    trend = 1
                    last_high = h
                    last_high_idx = i

        # 补上最后一个未确认的极值点
        if trend == 1:
            points.append({
                'date': _date(klines[last_high_idx]),
                'price': round(last_high, 3),
                'type': 'high',
                'index': last_high_idx,
            })
        elif trend == -1:
            points.append({
                'date': _date(klines[last_low_idx]),
                'price': round(last_low, 3),
                'type': 'low',
                'index': last_low_idx,
            })

        # 在开头补上初始极值
        if trend == 1 and points and points[0]['type'] == 'high':
            # 第一个确认点是高点，前面应该有初始低点
            points.insert(0, {
                'date': _date(klines[last_low_idx if last_low_idx < points[0]['index'] else 0]),
                'price': round(first_low if last_low_idx == 0 else _low(klines[last_low_idx]), 3),
                'type': 'low',
                'index': 0,
            })
        elif trend == -1 and points and points[0]['type'] == 'low':
            points.insert(0, {
                'date': _date(klines[last_high_idx if last_high_idx < points[0]['index'] else 0]),
                'price': round(first_high if last_high_idx == 0 else _high(klines[last_high_idx]), 3),
                'type': 'high',
                'index': 0,
            })

        # 计算每个拐点的涨跌幅
        for i, pt in enumerate(points):
            if i == 0:
                pt['change_pct'] = 0.0
            else:
                prev_price = points[i - 1]['price']
                pt['change_pct'] = round(
                    (pt['price'] - prev_price) / prev_price * 100, 2
                ) if prev_price else 0.0

        # 移除内部辅助字段
        for pt in points:
            pt.pop('index', None)

        return points

    def _pair_trades(self, swing_points: List[Dict]) -> List[Dict]:
        """将拐点配对成交易：低点买入 → 高点卖出"""
        trades = []
        i = 0

        while i < len(swing_points) - 1:
            pt = swing_points[i]
            if pt['type'] == 'low':
                # 找下一个 high 作为卖点
                for j in range(i + 1, len(swing_points)):
                    if swing_points[j]['type'] == 'high':
                        buy = pt
                        sell = swing_points[j]
                        buy_date = buy['date']
                        sell_date = sell['date']

                        # 计算持仓天数
                        try:
                            d1 = datetime.strptime(buy_date[:10], '%Y-%m-%d')
                            d2 = datetime.strptime(sell_date[:10], '%Y-%m-%d')
                            holding_days = (d2 - d1).days
                        except (ValueError, TypeError):
                            holding_days = 0

                        profit_pct = round(
                            (sell['price'] - buy['price']) / buy['price'] * 100, 2
                        ) if buy['price'] else 0.0

                        trades.append({
                            'buy_date': buy_date,
                            'buy_price': buy['price'],
                            'sell_date': sell_date,
                            'sell_price': sell['price'],
                            'profit_pct': profit_pct,
                            'holding_days': holding_days,
                        })
                        i = j + 1
                        break
                else:
                    i += 1
            else:
                i += 1

        return trades

    def _compute_summary(self, trades: List[Dict]) -> Dict:
        """计算交易统计"""
        if not trades:
            return self._empty_summary()

        profits = [t['profit_pct'] for t in trades]
        holdings = [t['holding_days'] for t in trades]
        win_count = sum(1 for p in profits if p > 0)

        # 累计收益率（复利）
        cumulative = 1.0
        for p in profits:
            cumulative *= (1 + p / 100)
        total_return = round((cumulative - 1) * 100, 2)

        return {
            'total_trades': len(trades),
            'win_count': win_count,
            'loss_count': len(trades) - win_count,
            'win_rate': round(win_count / len(trades) * 100, 1),
            'total_return': total_return,
            'avg_return': round(sum(profits) / len(profits), 2),
            'max_return': round(max(profits), 2),
            'max_loss': round(min(profits), 2),
            'avg_holding_days': round(sum(holdings) / len(holdings), 1) if holdings else 0,
        }

    def _empty_summary(self) -> Dict:
        return {
            'total_trades': 0,
            'win_count': 0,
            'loss_count': 0,
            'win_rate': 0.0,
            'total_return': 0.0,
            'avg_return': 0.0,
            'max_return': 0.0,
            'max_loss': 0.0,
            'avg_holding_days': 0,
        }

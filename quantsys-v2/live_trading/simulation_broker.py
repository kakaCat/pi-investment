"""
模拟券商接口 - 用于模拟交易测试

模拟真实交易环境：
1. 模拟市价单/限价单
2. 模拟成交延迟和滑点
3. 模拟手续费计算
4. 记录所有交易历史

优化：
- 使用 Decimal 进行金额计算，避免浮点数精度问题
- 使用结构化日志记录
"""

import pandas as pd
import numpy as np
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import structlog

logger = structlog.get_logger(__name__)


class SimulationBroker:
    """模拟券商接口"""

    def __init__(self, commission_rate=0.0003, slippage_rate=0.001):
        """
        初始化模拟券商

        Args:
            commission_rate: 手续费率（默认万3）
            slippage_rate: 滑点率（默认千1）
        """
        # 转换为 Decimal 避免浮点数精度问题
        self.commission_rate = Decimal(str(commission_rate))
        self.slippage_rate = Decimal(str(slippage_rate))
        self.trades = []  # 交易记录

        logger.info(
            "broker_initialized",
            commission_rate=float(self.commission_rate),
            slippage_rate=float(self.slippage_rate)
        )

    def buy(self, symbol, shares, price, order_type='market'):
        """
        买入股票

        Args:
            symbol: 股票代码
            shares: 股数（必须是100的整数倍）
            price: 当前价格（float 或 Decimal）
            order_type: 订单类型 (market/limit)

        Returns:
            dict: 成交信息（金额字段为 float，便于 JSON 序列化）
        """
        # 验证股数
        if shares % 100 != 0:
            logger.error("invalid_shares", shares=shares, symbol=symbol)
            raise ValueError(f"股数必须是100的整数倍: {shares}")

        # 转换价格为 Decimal
        price_decimal = Decimal(str(price)) if not isinstance(price, Decimal) else price

        # 计算成交价（考虑滑点）
        if order_type == 'market':
            # 市价单：向上滑点
            filled_price = price_decimal * (Decimal('1') + self.slippage_rate)
        else:
            # 限价单：使用指定价格
            filled_price = price_decimal

        # 计算成本（使用 Decimal）
        amount = Decimal(shares) * filled_price
        commission = max(amount * self.commission_rate, Decimal('5'))  # 最低5元
        total_cost = amount + commission

        # 四舍五入到分
        filled_price = filled_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        amount = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        commission = commission.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_cost = total_cost.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # 记录交易（转换为 float 便于 JSON 序列化）
        trade = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': symbol,
            'action': 'BUY',
            'shares': shares,
            'price': float(price_decimal),
            'filled_price': float(filled_price),
            'amount': float(amount),
            'commission': float(commission),
            'total_cost': float(total_cost),
            'order_type': order_type
        }
        self.trades.append(trade)

        logger.info(
            "buy_order_filled",
            symbol=symbol,
            shares=shares,
            filled_price=float(filled_price),
            total_cost=float(total_cost),
            commission=float(commission),
            order_type=order_type
        )

        return trade

    def sell(self, symbol, shares, price, order_type='market'):
        """
        卖出股票

        Args:
            symbol: 股票代码
            shares: 股数（必须是100的整数倍）
            price: 当前价格（float 或 Decimal）
            order_type: 订单类型 (market/limit)

        Returns:
            dict: 成交信息（金额字段为 float，便于 JSON 序列化）
        """
        # 验证股数
        if shares % 100 != 0:
            logger.error("invalid_shares", shares=shares, symbol=symbol)
            raise ValueError(f"股数必须是100的整数倍: {shares}")

        # 转换价格为 Decimal
        price_decimal = Decimal(str(price)) if not isinstance(price, Decimal) else price

        # 计算成交价（考虑滑点）
        if order_type == 'market':
            # 市价单：向下滑点
            filled_price = price_decimal * (Decimal('1') - self.slippage_rate)
        else:
            # 限价单：使用指定价格
            filled_price = price_decimal

        # 计算收入（使用 Decimal）
        amount = Decimal(shares) * filled_price
        commission = max(amount * self.commission_rate, Decimal('5'))  # 最低5元
        stamp_duty = amount * Decimal('0.001')  # 印花税千1（仅卖出收取）
        total_revenue = amount - commission - stamp_duty

        # 四舍五入到分
        filled_price = filled_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        amount = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        commission = commission.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        stamp_duty = stamp_duty.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_revenue = total_revenue.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # 记录交易（转换为 float 便于 JSON 序列化）
        trade = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': symbol,
            'action': 'SELL',
            'shares': shares,
            'price': float(price_decimal),
            'filled_price': float(filled_price),
            'amount': float(amount),
            'commission': float(commission),
            'stamp_duty': float(stamp_duty),
            'total_revenue': float(total_revenue),
            'order_type': order_type
        }
        self.trades.append(trade)

        logger.info(
            "sell_order_filled",
            symbol=symbol,
            shares=shares,
            filled_price=float(filled_price),
            total_revenue=float(total_revenue),
            commission=float(commission),
            stamp_duty=float(stamp_duty),
            order_type=order_type
        )

        return trade

    def get_trade_history(self):
        """获取交易历史"""
        if not self.trades:
            return pd.DataFrame()

        df = pd.DataFrame(self.trades)
        return df

    def get_total_commission(self):
        """获取总手续费"""
        if not self.trades:
            return 0

        df = self.get_trade_history()
        total = df['commission'].sum()

        # 卖出还有印花税
        if 'stamp_duty' in df.columns:
            total += df['stamp_duty'].fillna(0).sum()

        return total

    def export_trades(self, filepath):
        """导出交易记录"""
        df = self.get_trade_history()
        if df.empty:
            logger.warning("没有交易记录可导出")
            return

        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        logger.info(f"交易记录已导出: {filepath}")


class MockDataProvider:
    """模拟数据提供者 - 用于测试"""

    def __init__(self, data_service):
        """
        初始化

        Args:
            data_service: DataService实例
        """
        self.ds = data_service

    def get_realtime_price(self, symbol):
        """
        获取实时价格（模拟）

        实际应该调用券商API或行情接口
        这里暂时返回最新收盘价

        Args:
            symbol: 股票代码

        Returns:
            float: 当前价格
        """
        try:
            # 获取最近的K线数据
            df = self.ds.kline.get_stock_kline(
                symbol=symbol,
                start_date=(datetime.now() - pd.Timedelta(days=30)).strftime('%Y-%m-%d'),
                end_date=datetime.now().strftime('%Y-%m-%d')
            )

            if df.empty:
                logger.warning(f"{symbol}: 无法获取价格数据")
                return None

            # 返回最新收盘价
            latest_price = df.iloc[-1]['close']
            return float(latest_price)

        except Exception as e:
            logger.error(f"{symbol}: 获取价格失败 - {e}")
            return None

    def get_realtime_prices(self, symbols):
        """
        批量获取实时价格

        Args:
            symbols: 股票代码列表

        Returns:
            dict: {symbol: price}
        """
        prices = {}
        for symbol in symbols:
            price = self.get_realtime_price(symbol)
            if price:
                prices[symbol] = price

        return prices

    def check_tradable(self, symbol):
        """
        检查股票是否可交易

        检查项：
        1. 是否停牌
        2. 是否ST
        3. 是否涨跌停

        Args:
            symbol: 股票代码

        Returns:
            tuple: (is_tradable, reason)
        """
        # TODO: 实现完整的可交易性检查
        # 目前简化处理，都认为可交易
        return True, "正常"


if __name__ == '__main__':
    # 测试代码
    from infrastructure.logging import configure_structured_logging
    configure_structured_logging(level="INFO", json_format=False)

    broker = SimulationBroker()

    # 模拟买入
    broker.buy('300750', 100, 50.0)

    # 模拟卖出
    broker.sell('300750', 100, 55.0)

    # 查看交易历史
    print("\n交易历史:")
    print(broker.get_trade_history())

    print(f"\n总手续费: ¥{broker.get_total_commission():.2f}")

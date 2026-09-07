"""
V14策略因子计算器 - 支持多数据源

改进：
1. 集成多数据源获取器（新浪/AKShare/本地数据库）
2. 自动failover，确保数据获取成功
3. 向后兼容V13接口
"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta
import logging

from live_trading.v13_factors import calculate_v13_factors, get_factor_names
from live_trading.multi_source_data_fetcher import MultiSourceDataFetcher


class V14FactorCalculator:
    """V14策略因子计算器（支持多数据源）"""

    def __init__(self):
        self.fetcher = MultiSourceDataFetcher()
        self.factor_names = get_factor_names()
        logging.info(f"V14因子计算器初始化完成，共{len(self.factor_names)}个因子")

    def get_latest_data(self, symbols, days=100):
        """
        获取最新数据（使用多数据源）

        Args:
            symbols: 股票列表 [{'symbol': '300750', 'name': '宁德时代'}, ...]
            days: 获取天数（需要足够的历史数据计算rolling(60)因子）

        Returns:
            DataFrame: 包含所有股票的K线数据
        """
        # 计算日期范围
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days*2)).strftime('%Y-%m-%d')  # 多取一些，过滤交易日

        logging.info(f"开始获取 {len(symbols)} 只股票的数据: {start_date} ~ {end_date}")

        all_data = []
        success_count = 0
        fail_count = 0

        for idx, symbol_info in enumerate(symbols):
            symbol = symbol_info['symbol']

            if (idx + 1) % 10 == 0:
                logging.info(f"进度: {idx+1}/{len(symbols)} ({success_count}成功, {fail_count}失败)")

            try:
                # 使用多数据源获取K线
                df = self.fetcher.fetch_klines(symbol, start_date, end_date)

                if df is None or df.empty:
                    logging.warning(f"{symbol}: 无数据")
                    fail_count += 1
                    continue

                # 标准化列名（支持多种格式）
                column_mapping = {
                    '日期': 'date',
                    'trade_date': 'date',  # 本地数据库格式
                    '开盘': 'open',
                    '最高': 'high',
                    '最低': 'low',
                    '收盘': 'close',
                    '成交量': 'volume',
                    '成交额': 'amount',
                    '换手率': 'turnover_rate'
                }

                for old_col, new_col in column_mapping.items():
                    if old_col in df.columns and old_col != new_col:
                        df.rename(columns={old_col: new_col}, inplace=True)

                # 确保date列是datetime类型
                if 'date' not in df.columns:
                    logging.warning(f"{symbol}: 缺少date列，当前列: {list(df.columns)}")
                    fail_count += 1
                    continue

                df['date'] = pd.to_datetime(df['date'])

                # 确保必需的列存在
                required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
                if not all(col in df.columns for col in required_cols):
                    logging.warning(f"{symbol}: 缺少必需列，当前列: {list(df.columns)}")
                    fail_count += 1
                    continue

                # 添加换手率（如果不存在）
                if 'turnover_rate' not in df.columns:
                    df['turnover_rate'] = 0.0

                # 只保留最近days个交易日
                df = df.sort_values('date').tail(days)

                df['symbol'] = symbol
                all_data.append(df)
                success_count += 1

            except Exception as e:
                logging.error(f"{symbol}: 获取数据失败 - {e}")
                fail_count += 1
                continue

        if not all_data:
            logging.error("所有股票数据获取失败")
            return pd.DataFrame()

        result = pd.concat(all_data, ignore_index=True)
        logging.info(f"✓ 数据获取完成: {len(result)}条K线, {result['symbol'].nunique()}只股票 (成功{success_count}/失败{fail_count})")

        return result

    def calculate_factors(self, data):
        """
        计算因子

        Args:
            data: K线数据DataFrame

        Returns:
            DataFrame: 包含因子的数据
        """
        if data.empty:
            logging.error("输入数据为空，无法计算因子")
            return pd.DataFrame()

        try:
            factors = calculate_v13_factors(data)
            logging.info(f"✓ 因子计算完成: {len(factors)}只股票, {len(factors.columns)}个特征")
            return factors
        except Exception as e:
            logging.error(f"因子计算失败: {e}", exc_info=True)
            return pd.DataFrame()

    def calculate_latest_factors(self, symbols, days=100):
        """
        获取数据并计算因子（一步完成）

        Args:
            symbols: 股票列表
            days: 获取天数

        Returns:
            DataFrame: 包含因子的数据
        """
        logging.info(f"开始计算 {len(symbols)} 只股票的最新因子...")

        # 1. 获取数据（通过多数据源）
        data = self.get_latest_data(symbols, days)

        if data.empty:
            logging.error("数据获取失败")
            return pd.DataFrame()

        # 2. 计算因子
        factors = self.calculate_factors(data)

        return factors

    def get_health_report(self):
        """获取数据源健康报告"""
        return self.fetcher.get_health_report()

    def get_latest_factors(self, symbols, days=100):
        """
        与 V13FactorCalculator 接口对齐：返回每只股票最新一天的因子值

        SimulationTrader.rebalance 统一调用此方法。

        Args:
            symbols: 股票列表 [{'symbol': '300750', 'name': '宁德时代'}, ...]
            days: 获取天数

        Returns:
            DataFrame: 每只股票最新一天的因子值（失败时返回空 DataFrame）
        """
        factors = self.calculate_latest_factors(symbols, days)
        if factors.empty:
            return factors
        return factors.groupby('symbol').tail(1).copy()


if __name__ == '__main__':
    # 测试V14因子计算器
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    calc = V14FactorCalculator()

    # 测试股票
    test_symbols = [
        {'symbol': '000001', 'name': '平安银行'},
        {'symbol': '600519', 'name': '贵州茅台'},
        {'symbol': '300750', 'name': '宁德时代'},
    ]

    print("\n" + "="*70)
    print("测试V14因子计算器")
    print("="*70)

    factors = calc.calculate_latest_factors(test_symbols, days=100)

    if not factors.empty:
        print(f"\n✓ 成功计算因子")
        print(f"  股票数: {len(factors)}")
        print(f"  因子数: {len(factors.columns) - 2}")  # 减去symbol和date列
        print(f"\n前3只股票的部分因子:")
        print(factors.head(3).iloc[:, :10])
    else:
        print("\n✗ 因子计算失败")

    # 健康报告
    print("\n" + "="*70)
    print("数据源健康报告")
    print("="*70)
    import json
    print(json.dumps(calc.get_health_report(), indent=2, ensure_ascii=False))

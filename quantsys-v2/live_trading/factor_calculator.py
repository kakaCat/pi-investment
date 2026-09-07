"""
V13策略实时因子计算模块

架构说明：
1. 数据获取：通过DataService从数据库获取（不直接调用akshare）
2. 因子计算：调用v13_factors.py中提取的因子函数
3. 返回格式：DataFrame，可直接输入XGBoost模型
"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta
import logging

from infrastructure.services.service_factory import ServiceFactory
from live_trading.v13_factors import calculate_v13_factors, get_factor_names


class V13FactorCalculator:
    """V13策略因子计算器"""

    def __init__(self):
        self.kline_repo = ServiceFactory.get_kline_repository()
        self.factor_names = get_factor_names()
        logging.info(f"V13因子计算器初始化完成，共{len(self.factor_names)}个因子")

    def get_latest_data(self, symbols, days=100):
        """
        获取最新数据（使用实时数据接口）

        Args:
            symbols: 股票列表 [{'symbol': '300750', 'name': '宁德时代'}, ...]
            days: 获取天数（需要足够的历史数据计算rolling(60)因子）

        Returns:
            DataFrame: 包含所有股票的K线数据
        """
        all_data = []
        for symbol_info in symbols:
            symbol = symbol_info['symbol']

            try:
                # 使用实时数据接口：get_latest()返回最近N条（Polars DataFrame）
                klines = self.kline_repo.get_latest(symbol, limit=days)

                if klines.is_empty():
                    logging.warning(f"{symbol}: 无数据")
                    continue

                # Polars转pandas DataFrame
                df = klines.to_pandas()

                # 确保date列存在（trade_date -> date）
                if 'trade_date' in df.columns:
                    df.rename(columns={'trade_date': 'date'}, inplace=True)

                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])

                # 确保必需的列存在
                required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
                if not all(col in df.columns for col in required_cols):
                    logging.warning(f"{symbol}: 缺少必需列，当前列: {list(df.columns)}")
                    continue

                # 添加换手率（如果不存在）
                if 'turnover_rate' not in df.columns:
                    df['turnover_rate'] = 0.0

                df['symbol'] = symbol
                all_data.append(df)

            except Exception as e:
                logging.error(f"{symbol}: 获取数据失败 - {e}")
                continue

        if not all_data:
            logging.error("所有股票数据获取失败")
            return pd.DataFrame()

        result = pd.concat(all_data, ignore_index=True)
        logging.info(f"获取数据完成: {len(result)}条, {result['symbol'].nunique()}只股票")

        return result

    def calculate_factors(self, data):
        """
        计算85个因子

        Args:
            data: K线数据DataFrame

        Returns:
            DataFrame: 包含85个因子的数据
        """
        if data.empty:
            return pd.DataFrame()

        # 调用v13_factors模块计算
        logging.info("开始计算85个因子...")
        data_with_factors = calculate_v13_factors(data)
        logging.info(f"因子计算完成: {len(data_with_factors)}条")

        return data_with_factors

    def get_latest_factors(self, symbols):
        """
        获取最新因子（供预测使用）

        这是实盘交易的核心函数：
        1. 获取最新100天数据（从数据库）
        2. 计算85个因子
        3. 返回每只股票最新一天的因子值

        Args:
            symbols: 股票列表 [{'symbol': '300750', 'name': '宁德时代'}, ...]

        Returns:
            DataFrame: 每只股票最新的因子值
        """
        # 1. 获取数据（通过DataService）
        logging.info(f"开始获取{len(symbols)}只股票的最新数据...")
        data = self.get_latest_data(symbols, days=100)

        if data.empty:
            logging.error("数据获取失败")
            return pd.DataFrame()

        # 2. 计算因子
        data_with_factors = self.calculate_factors(data)

        if data_with_factors.empty:
            logging.error("因子计算失败")
            return pd.DataFrame()

        # 3. 取每只股票最新一天的数据
        latest = data_with_factors.groupby('symbol').tail(1).copy()

        # 4. 验证因子完整性
        available_factors = [f for f in self.factor_names if f in latest.columns]
        missing_factors = set(self.factor_names) - set(available_factors)

        if missing_factors:
            logging.warning(f"缺少{len(missing_factors)}个因子: {list(missing_factors)[:5]}...")

        logging.info(f"获取最新因子完成: {len(latest)}只股票, {len(available_factors)}/85个因子可用")

        return latest[['symbol', 'date'] + available_factors]

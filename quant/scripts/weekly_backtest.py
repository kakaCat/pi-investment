#!/usr/bin/env python3
"""
策略回测验证脚本

功能：
1. 从数据库读取最近N天的K线数据
2. 回测所有策略（RSI反转、均线突破、布林带等）
3. 计算绩效指标（回报率、夏普比率、最大回撤等）
4. 生成回测报告（JSON + Markdown）
5. 策略排名和优化建议

使用方法：
    python scripts/weekly_backtest.py --days 30
    python scripts/weekly_backtest.py --days 60 --capital 1000000
    python scripts/weekly_backtest.py --start 2026-04-01 --end 2026-05-18
"""

import os
import sys
import json
import logging
import argparse
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import time

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantsys.strategies.backtest import BacktestEngine
from quantsys.strategies.classic.rsi_reversal import RSIReversalStrategy
from quantsys.strategies.classic.ma_cross import MACrossStrategy
from quantsys.strategies.classic.bollinger_breakout import BollingerBreakoutStrategy

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class WeeklyBacktester:
    """每周策略回测器"""

    def __init__(
        self,
        quant_dir: str,
        initial_capital: float = 1000000.0,
        commission: float = 0.0003,
        slippage: float = 0.001
    ):
        """
        初始化回测器

        Args:
            quant_dir: quant目录路径
            initial_capital: 初始资金
            commission: 手续费率（默认0.03%）
            slippage: 滑点率（默认0.1%）
        """
        self.quant_dir = quant_dir
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.pi_invest_dir = os.path.join(os.path.expanduser('~'), '.pi-invest')
        self.db_path = os.path.join(os.path.expanduser('~'), '.pi-invest', 'stock-db', 'stocks.db')

        # 确保输出目录存在
        os.makedirs(self.pi_invest_dir, exist_ok=True)

    def get_available_strategies(self) -> List[Tuple[str, Any, Dict]]:
        """
        获取所有可用的策略

        Returns:
            List of (strategy_name, strategy_class, default_params)
        """
        strategies = [
            ('RSI反转', RSIReversalStrategy, {
                'rsi_period': 14,
                'oversold_threshold': 30,
                'overbought_threshold': 70,
                'stop_loss_pct': 0.05,
                'take_profit_pct': 0.10
            }),
            ('均线突破', MACrossStrategy, {
                'fast_period': 5,
                'slow_period': 20,
                'stop_loss_pct': 0.05,
                'take_profit_pct': 0.15
            }),
            ('布林带', BollingerBreakoutStrategy, {
                'period': 20,
                'num_std': 2.0,
                'stop_loss_pct': 0.05,
                'take_profit_pct': 0.10
            }),
            # TODO: 添加MACD策略
            # ('MACD', MACDStrategy, {...}),
            # TODO: 添加KDJ策略
            # ('KDJ', KDJStrategy, {...}),
        ]
        return strategies

    def load_stock_list(self) -> List[str]:
        """
        从数据库加载股票列表

        Returns:
            股票代码列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 获取有数据的股票列表（至少有30天数据）
            query = """
                SELECT symbol, COUNT(*) as days
                FROM daily_klines
                GROUP BY symbol
                HAVING days >= 30
                ORDER BY days DESC
            """
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()

            stock_list = [row[0] for row in results]
            logger.info(f"找到 {len(stock_list)} 只股票有足够的历史数据")
            return stock_list

        except Exception as e:
            logger.error(f"加载股票列表失败: {e}")
            return []

    def load_kline_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: Optional[int] = None
    ) -> Optional[Any]:
        """
        从数据库加载K线数据

        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            days: 最近N天（如果不指定start_date）

        Returns:
            DataFrame with OHLCV data
        """
        try:
            import pandas as pd
            conn = sqlite3.connect(self.db_path)

            if start_date and end_date:
                query = """
                    SELECT date as timestamp, symbol, open, high, low, close, volume, amount
                    FROM daily_klines
                    WHERE symbol = ? AND date >= ? AND date <= ?
                    ORDER BY date ASC
                """
                df = pd.read_sql_query(query, conn, params=(symbol, start_date, end_date))
            elif days:
                query = """
                    SELECT date as timestamp, symbol, open, high, low, close, volume, amount
                    FROM daily_klines
                    WHERE symbol = ?
                    ORDER BY date DESC
                    LIMIT ?
                """
                df = pd.read_sql_query(query, conn, params=(symbol, days))
                df = df.sort_values('timestamp').reset_index(drop=True)
            else:
                raise ValueError("必须指定 start_date/end_date 或 days")

            conn.close()

            if df.empty:
                return None

            # 转换日期格式
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed')
            return df

        except Exception as e:
            logger.error(f"加载 {symbol} 数据失败: {e}")
            return None

    def run_single_backtest(
        self,
        strategy_name: str,
        strategy_class: Any,
        strategy_params: Dict,
        data: Any
    ) -> Dict[str, Any]:
        """
        运行单个策略的回测

        Args:
            strategy_name: 策略名称
            strategy_class: 策略类
            strategy_params: 策略参数
            data: K线数据

        Returns:
            回测结果字典
        """
        try:
            start_time = time.time()

            # 创建策略实例
            strategy = strategy_class(params=strategy_params)

            # 创建回测引擎
            engine = BacktestEngine(
                strategy=strategy,
                initial_capital=self.initial_capital,
                commission=self.commission,
                slippage=self.slippage
            )

            # 运行回测
            result = engine.run(data)

            # 添加执行时间
            result['execution_time'] = time.time() - start_time
            result['strategy_name'] = strategy_name
            result['strategy_params'] = strategy_params

            return result

        except Exception as e:
            logger.error(f"回测 {strategy_name} 失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'strategy_name': strategy_name,
                'error': str(e),
                'total_return': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'win_rate': 0.0,
                'total_trades': 0
            }

    def run_all_backtests(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: Optional[int] = 30
    ) -> List[Dict[str, Any]]:
        """
        对单只股票运行所有策略的回测

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            days: 最近N天

        Returns:
            所有策略的回测结果列表
        """
        logger.info(f"开始回测 {symbol}...")

        # 加载数据
        data = self.load_kline_data(symbol, start_date, end_date, days)
        if data is None or len(data) == 0:
            logger.warning(f"{symbol} 没有足够的数据")
            return []

        logger.info(f"加载了 {len(data)} 条K线数据")

        # 获取所有策略
        strategies = self.get_available_strategies()
        results = []

        # 运行每个策略
        for strategy_name, strategy_class, strategy_params in strategies:
            logger.info(f"  回测策略: {strategy_name}...")
            result = self.run_single_backtest(
                strategy_name,
                strategy_class,
                strategy_params,
                data
            )
            results.append(result)

        return results

    def rank_strategies(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        按夏普比率对策略进行排名

        Args:
            results: 回测结果列表

        Returns:
            排序后的结果列表
        """
        # 过滤掉有错误的结果
        valid_results = [r for r in results if 'error' not in r]

        # 按夏普比率排序
        sorted_results = sorted(
            valid_results,
            key=lambda x: x.get('sharpe_ratio', 0),
            reverse=True
        )

        return sorted_results

    def generate_optimization_suggestions(
        self,
        results: List[Dict[str, Any]]
    ) -> List[str]:
        """
        生成优化建议

        Args:
            results: 回测结果列表

        Returns:
            建议列表
        """
        suggestions = []

        for result in results:
            strategy_name = result.get('strategy_name', 'Unknown')

            # 检查胜率
            win_rate = result.get('win_rate', 0)
            if win_rate < 0.4:
                suggestions.append(
                    f"- {strategy_name}策略胜率较低({win_rate*100:.1f}%)，建议调整参数或增加过滤条件"
                )

            # 检查交易次数
            total_trades = result.get('total_trades', 0)
            if total_trades < 3:
                suggestions.append(
                    f"- {strategy_name}策略交易次数过少({total_trades}次)，可能错过机会，建议放宽条件"
                )
            elif total_trades > 50:
                suggestions.append(
                    f"- {strategy_name}策略交易过于频繁({total_trades}次)，可能增加成本，建议提高信号质量"
                )

            # 检查最大回撤
            max_drawdown = result.get('max_drawdown', 0)
            if max_drawdown > 0.15:
                suggestions.append(
                    f"- {strategy_name}策略最大回撤较大({max_drawdown*100:.1f}%)，建议加强风险控制"
                )

            # 检查夏普比率
            sharpe_ratio = result.get('sharpe_ratio', 0)
            if sharpe_ratio < 1.0:
                suggestions.append(
                    f"- {strategy_name}策略夏普比率较低({sharpe_ratio:.2f})，风险调整后收益不佳"
                )

        if not suggestions:
            suggestions.append("- 所有策略表现良好，继续保持当前参数")

        return suggestions

    def generate_markdown_report(
        self,
        results: List[Dict[str, Any]],
        symbol: str,
        start_date: str,
        end_date: str,
        report_date: str
    ) -> str:
        """
        生成Markdown格式的回测报告

        Args:
            results: 回测结果列表
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            report_date: 报告日期

        Returns:
            Markdown格式的报告
        """
        # 排序
        ranked_results = self.rank_strategies(results)

        # 生成建议
        suggestions = self.generate_optimization_suggestions(results)

        # 构建报告
        report = f"""# 策略回测报告 - {report_date}

## 回测参数

- **股票代码**: {symbol}
- **回测期间**: {start_date} 至 {end_date}
- **初始资金**: {self.initial_capital:,.0f} 元
- **手续费**: {self.commission*100:.2f}%
- **滑点**: {self.slippage*100:.2f}%

## 策略表现

| 排名 | 策略 | 总回报 | 年化收益 | 夏普比率 | 最大回撤 | 胜率 | 交易次数 | 盈亏比 |
|------|------|--------|----------|----------|----------|------|----------|--------|
"""

        for idx, result in enumerate(ranked_results, 1):
            strategy_name = result.get('strategy_name', 'Unknown')
            total_return = result.get('total_return', 0) * 100
            sharpe_ratio = result.get('sharpe_ratio', 0)
            max_drawdown = result.get('max_drawdown', 0) * 100
            win_rate = result.get('win_rate', 0) * 100
            total_trades = result.get('total_trades', 0)
            profit_factor = result.get('profit_factor', 0)

            # 计算年化收益（假设回测期为30天）
            days = (datetime.strptime(end_date, '%Y-%m-%d') -
                   datetime.strptime(start_date, '%Y-%m-%d')).days
            annual_return = (1 + result.get('total_return', 0)) ** (365 / max(days, 1)) - 1
            annual_return_pct = annual_return * 100

            report += f"| {idx} | {strategy_name} | {total_return:+.2f}% | {annual_return_pct:+.2f}% | {sharpe_ratio:.2f} | {max_drawdown:.2f}% | {win_rate:.1f}% | {total_trades} | {profit_factor:.2f} |\n"

        # 最佳策略
        if ranked_results:
            best = ranked_results[0]
            report += f"\n## 最佳策略\n\n"
            report += f"**{best.get('strategy_name')}** 策略表现最佳，"
            report += f"夏普比率 {best.get('sharpe_ratio', 0):.2f}，"
            report += f"总回报 {best.get('total_return', 0)*100:+.2f}%。\n\n"

            # 策略详情
            report += f"### 策略详情\n\n"
            report += f"- **总交易次数**: {best.get('total_trades', 0)}\n"
            report += f"- **获胜交易**: {best.get('winning_trades', 0)}\n"
            report += f"- **失败交易**: {best.get('losing_trades', 0)}\n"
            report += f"- **平均盈利**: {best.get('avg_win', 0):,.2f} 元\n"
            report += f"- **平均亏损**: {best.get('avg_loss', 0):,.2f} 元\n"
            report += f"- **最大盈利**: {best.get('max_win', 0):,.2f} 元\n"
            report += f"- **最大亏损**: {best.get('max_loss', 0):,.2f} 元\n"
            report += f"- **期望值**: {best.get('expectancy', 0):,.2f} 元\n"
            report += f"- **Sortino比率**: {best.get('sortino_ratio', 0):.2f}\n"
            report += f"- **Calmar比率**: {best.get('calmar_ratio', 0):.2f}\n"

        # 优化建议
        report += f"\n## 优化建议\n\n"
        for suggestion in suggestions:
            report += f"{suggestion}\n"

        # 注意事项
        report += f"\n## 注意事项\n\n"
        report += f"- 回测结果基于历史数据，不代表未来表现\n"
        report += f"- 实际交易中可能面临更高的滑点和冲击成本\n"
        report += f"- 建议结合市场环境和基本面分析进行决策\n"
        report += f"- 定期评估和调整策略参数\n"

        report += f"\n---\n"
        report += f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"

        return report

    def save_reports(
        self,
        results: List[Dict[str, Any]],
        symbol: str,
        start_date: str,
        end_date: str
    ) -> Tuple[str, str]:
        """
        保存回测报告（JSON + Markdown）

        Args:
            results: 回测结果列表
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            (json_path, markdown_path)
        """
        report_date = datetime.now().strftime('%Y-%m-%d')

        # 保存JSON报告
        json_filename = f"backtest_report_{symbol}_{report_date}.json"
        json_path = os.path.join(self.pi_invest_dir, json_filename)

        json_data = {
            'report_date': report_date,
            'symbol': symbol,
            'backtest_period': {
                'start': start_date,
                'end': end_date
            },
            'backtest_config': {
                'initial_capital': self.initial_capital,
                'commission': self.commission,
                'slippage': self.slippage
            },
            'results': results
        }

        # 移除equity_curve（太大）
        for result in json_data['results']:
            result.pop('equity_curve', None)

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"JSON报告已保存: {json_path}")

        # 保存Markdown报告
        markdown_filename = f"backtest_report_{symbol}_{report_date}.md"
        markdown_path = os.path.join(self.pi_invest_dir, markdown_filename)

        markdown_content = self.generate_markdown_report(
            results, symbol, start_date, end_date, report_date
        )

        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        logger.info(f"Markdown报告已保存: {markdown_path}")

        return json_path, markdown_path


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='策略回测验证脚本')
    parser.add_argument(
        '--symbol',
        type=str,
        default='000001',
        help='股票代码（默认: 000001）'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='回测最近N天（默认: 30）'
    )
    parser.add_argument(
        '--start',
        type=str,
        help='开始日期 (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end',
        type=str,
        help='结束日期 (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--capital',
        type=float,
        default=1000000.0,
        help='初始资金（默认: 1000000）'
    )
    parser.add_argument(
        '--commission',
        type=float,
        default=0.0003,
        help='手续费率（默认: 0.0003 = 0.03%%）'
    )
    parser.add_argument(
        '--slippage',
        type=float,
        default=0.001,
        help='滑点率（默认: 0.001 = 0.1%%）'
    )

    args = parser.parse_args()

    # 获取quant目录路径
    quant_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    logger.info("=" * 60)
    logger.info("策略回测验证脚本")
    logger.info("=" * 60)

    # 创建回测器
    backtester = WeeklyBacktester(
        quant_dir=quant_dir,
        initial_capital=args.capital,
        commission=args.commission,
        slippage=args.slippage
    )

    # 确定日期范围
    if args.start and args.end:
        start_date = args.start
        end_date = args.end
        days = None
    else:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')
        days = args.days

    logger.info(f"回测期间: {start_date} 至 {end_date}")
    logger.info(f"初始资金: {args.capital:,.0f} 元")
    logger.info("")

    # 运行回测
    results = backtester.run_all_backtests(
        symbol=args.symbol,
        start_date=start_date,
        end_date=end_date,
        days=days
    )

    if not results:
        logger.error("回测失败，没有结果")
        sys.exit(1)

    # 保存报告
    json_path, markdown_path = backtester.save_reports(
        results,
        args.symbol,
        start_date,
        end_date
    )

    # 打印摘要
    logger.info("")
    logger.info("=" * 60)
    logger.info("回测完成")
    logger.info("=" * 60)

    ranked_results = backtester.rank_strategies(results)
    for idx, result in enumerate(ranked_results, 1):
        logger.info(
            f"{idx}. {result.get('strategy_name')}: "
            f"回报 {result.get('total_return', 0)*100:+.2f}%, "
            f"夏普 {result.get('sharpe_ratio', 0):.2f}, "
            f"回撤 {result.get('max_drawdown', 0)*100:.2f}%"
        )

    logger.info("")
    logger.info(f"详细报告:")
    logger.info(f"  JSON: {json_path}")
    logger.info(f"  Markdown: {markdown_path}")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()

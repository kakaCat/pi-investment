# services/diagnosis_service.py
"""
诊断服务 - 策略诊断主入口
"""
from domain.ports import IBacktestRepository, IKlineRepository
from typing import Dict, Optional
from datetime import datetime
import structlog
import uuid
import re

from application.services.strategy_analyzer import StrategyAnalyzer
from application.services.report_generator import ReportGenerator

logger = structlog.get_logger(__name__)

# 常量定义
TRADING_DAYS_PER_YEAR = 252.0
DEFAULT_RISK_FREE_RATE = 0.03
VOLATILITY_APPROXIMATION_FACTOR = 3.0


class DiagnosisService:
    """策略诊断服务

    P2-1: 支持依赖注入，保持向后兼容
    """

    def __init__(
        self,
        backtest_repo: Optional[IBacktestRepository] = None,
        kline_repo: Optional[IKlineRepository] = None,
        strategy_analyzer: Optional['StrategyAnalyzer'] = None,
        report_generator: Optional['ReportGenerator'] = None,
    ):
        """初始化诊断服务

        Args:
            backtest_repo: 回测仓库（可选）
            kline_repo: K线仓库（可选）
            strategy_analyzer: 策略分析器（可选）
            report_generator: 报告生成器（可选）

        P2-1: 推荐通过 ServiceFactory 获取实例
        """
        self.backtest_repo = backtest_repo
        self.kline_repo = kline_repo
        self.strategy_analyzer = strategy_analyzer or StrategyAnalyzer()
        self.report_generator = report_generator or ReportGenerator()

    def run_diagnosis(self, params: Dict) -> Dict:
        """
        运行完整诊断

        Args:
            params: {
                backtest_id: 回测ID（可选）
                symbol: 股票代码
                start_date: 开始日期 (YYYY-MM-DD)
                end_date: 结束日期 (YYYY-MM-DD)
                strategy_name: 策略名称
                benchmark: 基准指数（默认 000300.SH）
            }

        Returns:
            诊断结果

        Raises:
            ValueError: 参数验证失败
        """
        try:
            # 0. 输入验证
            self._validate_params(params)

            # 1. 获取回测数据
            backtest_data = self._get_backtest_data(params)

            # 2. 获取基准数据
            benchmark_symbol = params.get('benchmark', '000300.SH')
            benchmark_data = self._get_benchmark_data(
                benchmark_symbol,
                params['start_date'],
                params['end_date']
            )

            # 3. 策略分析
            analysis = self.strategy_analyzer.analyze(backtest_data, benchmark_data)

            # 4. 生成诊断结论
            diagnosis = self.strategy_analyzer.generate_diagnosis(
                backtest_data,
                analysis['ratings'],
                analysis['comparison']
            )

            # 5. 生成报告文件
            report_path = self.report_generator.generate(
                {
                    'metrics': backtest_data,
                    'benchmark': benchmark_data,
                    'ratings': analysis['ratings']
                },
                diagnosis,
                params
            )

            # 6. 返回结果
            return {
                'diagnosisId': self._generate_id(),
                'timestamp': datetime.now().isoformat(),
                'strategy': {
                    'name': params['strategy_name'],
                    'symbol': params['symbol'],
                    'period': f"{params['start_date']} ~ {params['end_date']}"
                },
                'metrics': backtest_data,
                'benchmark': benchmark_data,
                'ratings': analysis['ratings'],
                'diagnosis': diagnosis,
                'reportPath': report_path
            }

        except Exception as e:
            logger.error(f"Diagnosis failed: {e}", exc_info=True)
            raise

    def _validate_params(self, params: Dict) -> None:
        """
        验证输入参数

        Raises:
            ValueError: 参数验证失败
        """
        # 验证必填参数
        required_params = ['symbol', 'start_date', 'end_date', 'strategy_name']
        for param in required_params:
            if param not in params:
                raise ValueError(f"缺少必填参数: {param}")

        # 验证非空
        if not params['symbol'] or not params['symbol'].strip():
            raise ValueError("股票代码不能为空")

        if not params['strategy_name'] or not params['strategy_name'].strip():
            raise ValueError("策略名称不能为空")

        # 验证日期格式 (YYYY-MM-DD)
        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        if not date_pattern.match(params['start_date']):
            raise ValueError(f"日期格式无效: start_date={params['start_date']}，应为 YYYY-MM-DD")

        if not date_pattern.match(params['end_date']):
            raise ValueError(f"日期格式无效: end_date={params['end_date']}，应为 YYYY-MM-DD")

        # 验证日期有效性
        try:
            start_date = datetime.strptime(params['start_date'], '%Y-%m-%d')
            end_date = datetime.strptime(params['end_date'], '%Y-%m-%d')
        except ValueError as e:
            raise ValueError(f"日期格式无效: {e}")

        # 验证日期顺序
        if end_date <= start_date:
            raise ValueError("结束日期必须晚于开始日期")

    def _get_backtest_data(self, params: Dict) -> Dict:
        """
        获取回测数据

        如果提供了 backtest_id，从数据库读取
        否则需要先运行回测
        """
        backtest_id = params.get('backtest_id')

        if backtest_id:
            # 从数据库读取回测结果
            backtest = self.backtest_repo.get_backtest(int(backtest_id))
            if not backtest:
                raise ValueError(f"Backtest not found: {backtest_id}")

            return {
                'annualReturn': backtest.get('annual_return', 0),
                'sharpeRatio': backtest.get('sharpe_ratio', 0),
                'maxDrawdown': backtest.get('max_drawdown', 0),
                'winRate': backtest.get('win_rate', 0),
                'totalTrades': backtest.get('total_trades', 0)
            }
        else:
            # 需要先运行回测
            # 这里简化处理，实际应该调用回测服务
            raise ValueError("backtest_id is required. Please run backtest first.")

    def _get_benchmark_data(self, benchmark_symbol: str, start_date: str, end_date: str) -> Dict:
        """
        获取基准指数数据

        计算基准的年化收益、夏普比率、最大回撤
        """
        try:
            # 获取指数 K 线数据
            klines = self.kline_repo.get_daily_klines(benchmark_symbol, start_date, end_date)

            # klines is a Polars DataFrame, check if empty using .is_empty()
            if klines.is_empty() or len(klines) < 2:
                logger.warning(f"Insufficient benchmark data for {benchmark_symbol}, using default")
                return self._get_default_benchmark()

            # 计算指标
            returns = self._calculate_returns(klines)
            sharpe = self._calculate_sharpe_ratio(returns)
            max_dd = self._calculate_max_drawdown(klines)

            return {
                'symbol': benchmark_symbol,
                'name': self._get_index_name(benchmark_symbol),
                'annualReturn': returns,
                'sharpeRatio': sharpe,
                'maxDrawdown': max_dd
            }

        except Exception as e:
            logger.warning(f"Failed to get benchmark data: {e}, using default")
            return self._get_default_benchmark()

    def _calculate_returns(self, klines) -> float:
        """
        计算年化收益率

        Args:
            klines: K线数据 (Polars DataFrame)

        Returns:
            年化收益率

        Note:
            处理边界情况：
            - 空数据或单条数据返回 0.0
            - 起始价格为 0 返回 0.0（避免除零错误）
            - 负收益率（total_return < -1）会导致数学域错误，返回 -1.0
        """
        # klines is a Polars DataFrame, check if empty using .is_empty()
        if klines.is_empty() or len(klines) < 2:
            return 0.0

        # Convert to list of dicts for easier access
        klines_list = klines.to_dicts()
        start_price = klines_list[0]['close']
        end_price = klines_list[-1]['close']

        # 防止除零错误
        if start_price == 0:
            logger.warning("起始价格为 0，无法计算收益率")
            return 0.0

        total_return = (end_price - start_price) / start_price

        # 防止数学域错误：(1 + total_return) 必须 > 0
        if total_return <= -1:
            logger.warning(f"总收益率 {total_return:.2%} <= -100%，返回 -100% 年化收益")
            return -1.0

        # 年化
        days = len(klines)
        years = days / TRADING_DAYS_PER_YEAR
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

        return annual_return

    def _calculate_sharpe_ratio(self, returns: float, risk_free_rate: float = DEFAULT_RISK_FREE_RATE) -> float:
        """
        计算夏普比率（简化版）

        Args:
            returns: 年化收益率
            risk_free_rate: 无风险利率（默认 3%）

        Returns:
            夏普比率

        Note:
            这是一个简化的夏普比率计算，使用近似波动率：
            - 假设波动率 ≈ |收益率| / 3
            - 实际应用中应使用真实的收益率标准差
            - 当收益率为 0 时，使用默认波动率 0.1
        """
        # 简化计算：假设波动率为收益率绝对值的 1/3
        # 这是一个粗略的近似，实际应该使用收益率序列的标准差
        volatility = abs(returns) / VOLATILITY_APPROXIMATION_FACTOR if returns != 0 else 0.1
        sharpe = (returns - risk_free_rate) / volatility if volatility > 0 else 0
        return sharpe

    def _calculate_max_drawdown(self, klines) -> float:
        """计算最大回撤

        Args:
            klines: K线数据 (Polars DataFrame)
        """
        # klines is a Polars DataFrame, check if empty using .is_empty()
        if klines.is_empty():
            return 0.0

        # Convert to list of dicts for iteration
        klines_list = klines.to_dicts()
        peak = klines_list[0]['close']
        max_dd = 0.0

        for kline in klines_list:
            price = kline['close']
            if price > peak:
                peak = price
            dd = (price - peak) / peak
            if dd < max_dd:
                max_dd = dd

        return max_dd

    def _get_index_name(self, symbol: str) -> str:
        """获取指数名称"""
        mapping = {
            '000300.SH': '沪深300',
            '000001.SH': '上证指数',
            '399001.SZ': '深证成指',
            '399006.SZ': '创业板指'
        }
        return mapping.get(symbol, symbol)

    def _get_default_benchmark(self) -> Dict:
        """返回默认基准数据（沪深300 历史平均）"""
        return {
            'symbol': '000300.SH',
            'name': '沪深300',
            'annualReturn': 0.08,
            'sharpeRatio': 0.6,
            'maxDrawdown': -0.25
        }

    def _generate_id(self) -> str:
        """生成诊断ID"""
        timestamp = datetime.now().strftime('%Y%m%d')
        short_uuid = str(uuid.uuid4())[:8]
        return f"diag_{timestamp}_{short_uuid}"

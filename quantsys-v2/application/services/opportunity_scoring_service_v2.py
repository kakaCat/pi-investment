"""
机会评分引擎 V2 - 使用 BaseCalculator 模式

改进点：
1. 继承 BaseCalculator，使用统一的验证框架
2. 使用装饰器驱动的验证和性能追踪
3. 添加数据质量检查
4. 标准化输出格式（包含元数据）
5. 更好的错误处理和日志记录

职责：
1. 计算股票的技术面、基本面、资金面评分
2. 综合评分并确定风险等级
3. 支持并行处理多只股票
"""
from typing import List, Dict, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from adapters.outbound.repositories import KlineORMRepository
from adapters.outbound.repositories import StockORMRepository
from domain.quantlib.adapters import get_factor_adapter
from domain.quantlib.core.base_calculator import BaseCalculator, validate_inputs, timing_decorator, handle_calculation_error
from domain.quantlib.core.data_validator import DataValidator, DataQualityReport
import structlog

logger = structlog.get_logger(__name__)


class OpportunityScoringServiceV2(BaseCalculator):
    """机会评分引擎 V2 - 使用企业级设计模式"""

    def __init__(
        self,
        kline_repo: KlineRepository,
        stock_repo: StockRepository,
        factor_adapter,
        precision: int = 2
    ):
        """
        初始化评分服务

        Args:
            kline_repo: K线数据仓储
            stock_repo: 股票数据仓储
            factor_adapter: 因子适配器
            precision: 评分精度（小数位数）
        """
        super().__init__(precision=precision)
        self.kline_repo = kline_repo
        self.stock_repo = stock_repo
        self.factor_adapter = factor_adapter
        self.data_validator = DataValidator()

    def get_supported_methods(self) -> List[str]:
        """获取支持的评分方法"""
        return [
            'score_stocks',
            'score_single_stock',
            'calculate_technical_score',
            'calculate_fundamental_score',
            'calculate_capital_score'
        ]

    @timing_decorator
    def score_stocks(
        self,
        symbols: List[str],
        filters: Dict
    ) -> List[Dict]:
        """批量评分股票

        Args:
            symbols: 股票代码列表
            filters: 筛选条件，包含 technical 和 fundamental 列表

        Returns:
            评分结果列表，每个元素包含 symbol, score, technical_score 等字段
        """
        if not symbols:
            self.logger.warning("Empty symbols list provided")
            return []

        self.logger.info(f"开始评分 {len(symbols)} 只股票")

        # 批量查询K线数据
        klines_map = self.kline_repo.batch_get_recent_klines(symbols, days=120)
        self.logger.debug(f"获取到 {len(klines_map)} 只股票的K线数据")

        # 批量查询基本面数据
        fundamentals_map = self.stock_repo.batch_get_fundamentals(symbols)
        self.logger.debug(f"获取到 {len(fundamentals_map)} 只股票的基本面数据")

        # 并行处理每只股票
        opportunities = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(
                    self._score_single_stock_with_quality_check,
                    symbol,
                    klines_map.get(symbol, []),
                    fundamentals_map.get(symbol),
                    filters
                ): symbol
                for symbol in symbols
            }

            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result is not None:
                        opportunities.append(result)
                except Exception as e:
                    symbol = futures[future]
                    self.logger.error(f"{symbol}: 评分失败 - {e}", exc_info=True)

        self.logger.info(f"评分完成，找到 {len(opportunities)} 个机会")
        return opportunities

    @validate_inputs
    @handle_calculation_error
    def _score_single_stock_with_quality_check(
        self,
        symbol: str,
        klines: List[Dict],
        fundamental: Optional[Dict],
        filters: Dict
    ) -> Optional[Dict]:
        """评分单只股票（带数据质量检查）

        Args:
            symbol: 股票代码
            klines: K线数据列表
            fundamental: 基本面数据
            filters: 筛选条件

        Returns:
            评分结果字典，如果数据不足或质量差返回 None
        """
        # 1. 数据质量检查
        quality_report = self._check_data_quality(symbol, klines, fundamental)

        if not quality_report.is_acceptable(min_score=60.0):
            self.logger.warning(
                f"{symbol}: 数据质量不合格 (score={quality_report.quality_score:.1f}), "
                f"issues={quality_report.issues}"
            )
            return None

        # 2. 检查K线数据是否充足
        if len(klines) < 30:
            self.logger.warning(f"{symbol}: K线数据不足 ({len(klines)}条)")
            return None

        # 3. 计算技术指标因子
        factors = self._calculate_factors(klines)

        # 4. 计算三维评分
        tech_score = self._calculate_technical_score(
            factors,
            filters.get('technical', [])
        )
        fund_score = self._calculate_fundamental_score(
            fundamental,
            filters.get('fundamental', [])
        )
        capital_score = self._calculate_capital_score(factors)

        # 5. 计算综合评分
        total_score = self._calculate_comprehensive_score(
            tech_score,
            fund_score,
            capital_score
        )

        # 6. 获取股票名称
        stock_info = self.stock_repo.get_by_symbol(symbol, ['name'])
        stock_name = stock_info['name'] if stock_info else symbol

        # 7. 生成机会原因标签
        reasons = self._generate_reasons(
            tech_score, fund_score, capital_score,
            factors, fundamental, filters
        )

        # 8. 构建结果（包含元数据）
        return {
            'symbol': symbol,
            'name': stock_name,
            'score': round(total_score, self.precision),
            'technical_score': round(tech_score, self.precision),
            'fundamental_score': round(fund_score, self.precision),
            'capital_score': round(capital_score, self.precision),
            'confidence': round(total_score / 100, 2),
            'risk_level': self._calculate_risk_level(total_score),
            'signal_type': 'buy',
            'reasons': reasons,
            'timestamp': datetime.now().isoformat(),
            'metadata': {
                'data_quality_score': quality_report.quality_score,
                'klines_count': len(klines),
                'has_fundamental': fundamental is not None,
                'factors_calculated': len(factors),
                'filters_applied': {
                    'technical': filters.get('technical', []),
                    'fundamental': filters.get('fundamental', [])
                }
            }
        }

    def _check_data_quality(
        self,
        symbol: str,
        klines: List[Dict],
        fundamental: Optional[Dict]
    ) -> DataQualityReport:
        """检查数据质量

        Args:
            symbol: 股票代码
            klines: K线数据
            fundamental: 基本面数据

        Returns:
            数据质量报告
        """
        issues = []
        warnings = []
        quality_score = 100.0

        # 检查K线数据 (klines is a Polars DataFrame)
        if klines.is_empty():
            issues.append("No K-line data")
            quality_score = 0.0
        else:
            # Convert to list of dicts for validation
            klines_list = klines.to_dicts()

            # 检查数据长度
            if len(klines_list) < 30:
                issues.append(f"Insufficient K-line data: {len(klines_list)} < 30")
                quality_score -= 30

            # 检查必需字段
            required_fields = ['close', 'volume', 'open', 'high', 'low']
            missing_fields = []
            for field in required_fields:
                if field not in klines_list[0]:
                    missing_fields.append(field)

            if missing_fields:
                issues.append(f"Missing K-line fields: {missing_fields}")
                quality_score -= 20

            # 检查价格合理性
            for i, kline in enumerate(klines_list[:10]):  # 只检查前10条
                close = kline.get('close', 0)
                if close <= 0:
                    issues.append(f"Invalid close price at index {i}: {close}")
                    quality_score -= 10
                    break

            # 检查成交量
            zero_volume_count = sum(1 for k in klines if k.get('volume', 0) == 0)
            if zero_volume_count > len(klines) * 0.1:  # 超过10%的数据成交量为0
                warnings.append(f"{zero_volume_count} K-lines have zero volume")
                quality_score -= 10

        # 检查基本面数据（可选）
        if fundamental:
            # 检查PE合理性
            pe = fundamental.get('pe_ratio')
            if pe is not None and (pe < 0 or pe > 1000):
                warnings.append(f"Unusual PE ratio: {pe}")
                quality_score -= 5

            # 检查ROE合理性
            roe = fundamental.get('roe')
            if roe is not None and (roe < -100 or roe > 100):
                warnings.append(f"Unusual ROE: {roe}")
                quality_score -= 5

        quality_score = max(0.0, min(100.0, quality_score))

        return DataQualityReport(
            total_records=len(klines),
            missing_values={},
            outliers={},
            data_types={},
            date_range=None,
            quality_score=quality_score,
            issues=issues + warnings,
            timestamp=datetime.now().isoformat()
        )

    def _calculate_factors(self, klines) -> Dict:
        """计算技术指标因子

        Args:
            klines: K线数据 (Polars DataFrame)

        Returns:
            因子字典
        """
        # klines is a Polars DataFrame, check if empty using .is_empty()
        if klines.is_empty():
            return {}

        factors = {}

        try:
            # 计算RSI
            rsi14 = self.factor_adapter.calculate('rsi14', klines)
            if rsi14 is not None:
                factors['rsi'] = rsi14

            # 计算MACD
            macd = self.factor_adapter.calculate('macd', klines)
            macd_signal = self.factor_adapter.calculate('macd_signal', klines)
            if macd is not None and macd_signal is not None:
                factors['macd'] = macd
                factors['macd_signal'] = macd_signal

                # 计算前一天的MACD和信号线（用于判断金叉）
                if len(klines) >= 2:
                    klines_prev = klines[:-1]
                    macd_prev = self.factor_adapter.calculate('macd', klines_prev)
                    macd_signal_prev = self.factor_adapter.calculate('macd_signal', klines_prev)
                    if macd_prev is not None and macd_signal_prev is not None:
                        factors['macd_prev'] = macd_prev
                        factors['macd_signal_prev'] = macd_signal_prev

            # 计算布林带
            boll_upper = self.factor_adapter.calculate('bollinger_upper', klines)
            if boll_upper is not None:
                factors['boll_upper'] = boll_upper

            # 获取最新收盘价
            if klines:
                factors['close'] = klines[-1].get('close', 0)

            # 计算成交量相关指标
            if len(klines) >= 5:
                # 最近5日平均成交量
                recent_5_volume = sum(k.get('volume', 0) for k in klines[-5:]) / 5
                # 前5日平均成交量
                prev_5_volume = sum(k.get('volume', 0) for k in klines[-10:-5]) / 5
                if prev_5_volume > 0:
                    factors['volume_ratio_5d'] = recent_5_volume / prev_5_volume

            # 计算成交量均线
            if len(klines) >= 20:
                volume_ma20 = sum(k.get('volume', 0) for k in klines[-20:]) / 20
                factors['volume_ma20'] = volume_ma20

            if len(klines) >= 5:
                volume_ma5 = sum(k.get('volume', 0) for k in klines[-5:]) / 5
                factors['volume_ma5'] = volume_ma5

            # 当前成交量
            if klines:
                factors['volume'] = klines[-1].get('volume', 0)

            # 成交量历史（用于判断连续递增）
            if len(klines) >= 3:
                factors['volume_history'] = [k.get('volume', 0) for k in klines[-3:]]

        except Exception as e:
            self.logger.error(f"计算因子失败: {e}", exc_info=True)

        return factors

    def _calculate_technical_score(
        self,
        factors: Dict,
        conditions: List[str]
    ) -> float:
        """计算技术面评分

        Args:
            factors: 技术指标因子字典
            conditions: 技术条件列表

        Returns:
            技术面评分 (0-100)
        """
        # 如果没有指定条件，返回中性评分
        if not conditions:
            return 50.0

        score = 0.0

        for condition in conditions:
            if condition == 'rsi_oversold':
                # RSI < 30 为超卖
                if factors.get('rsi', 100) < 30:
                    score += 25

            elif condition == 'macd_golden_cross':
                # MACD金叉
                if self._is_macd_golden_cross(factors):
                    score += 25

            elif condition == 'bollinger_breakout':
                # 突破布林带上轨
                close = factors.get('close', 0)
                boll_upper = factors.get('boll_upper', float('inf'))
                if close > boll_upper:
                    score += 25

            elif condition == 'volume_surge':
                # 成交量放大（5日成交量比前5日增长超过100%）
                if factors.get('volume_ratio_5d', 0) > 2:
                    score += 25

        return min(score, 100.0)

    def _calculate_fundamental_score(
        self,
        fundamental: Optional[Dict],
        conditions: List[str]
    ) -> float:
        """计算基本面评分

        Args:
            fundamental: 基本面数据字典
            conditions: 基本面条件列表

        Returns:
            基本面评分 (0-100)
        """
        # 如果没有基本面数据或没有指定条件，返回中性评分
        if not fundamental or not conditions:
            return 50.0

        score = 0.0

        for condition in conditions:
            if condition == 'pe_low':
                # PE < 30
                if fundamental.get('pe_ratio', float('inf')) < 30:
                    score += 25

            elif condition == 'roe_high':
                # ROE > 15%
                if fundamental.get('roe', 0) > 15:
                    score += 25

            elif condition == 'gross_margin_high':
                # 毛利率 > 30%
                if fundamental.get('gross_margin', 0) > 30:
                    score += 25

            elif condition == 'debt_ratio_low':
                # 负债率 < 50%
                if fundamental.get('debt_ratio', 100) < 50:
                    score += 25

        return min(score, 100.0)

    def _calculate_capital_score(self, factors: Dict) -> float:
        """计算资金面评分（基于成交量指标）

        Args:
            factors: 技术指标因子字典

        Returns:
            资金面评分 (0-100)
        """
        score = 0.0

        # 5日成交量增长 > 50%
        if factors.get('volume_ratio_5d', 0) > 1.5:
            score += 25

        # 成交量连续递增
        if self._is_volume_increasing(factors, days=3):
            score += 25

        # 当前成交量 > 20日均量
        volume = factors.get('volume', 0)
        volume_ma20 = factors.get('volume_ma20', float('inf'))
        if volume > volume_ma20:
            score += 25

        # 5日均量 > 20日均量
        volume_ma5 = factors.get('volume_ma5', 0)
        if volume_ma5 > volume_ma20:
            score += 25

        return min(score, 100.0)

    def _calculate_comprehensive_score(
        self,
        tech_score: float,
        fund_score: float,
        capital_score: float
    ) -> float:
        """计算综合评分

        Args:
            tech_score: 技术面评分
            fund_score: 基本面评分
            capital_score: 资金面评分

        Returns:
            综合评分 (0-100)
        """
        # 综合评分 = 技术面×0.5 + 基本面×0.3 + 资金面×0.2
        return tech_score * 0.5 + fund_score * 0.3 + capital_score * 0.2

    def _calculate_risk_level(self, score: float) -> str:
        """计算风险等级

        Args:
            score: 综合评分

        Returns:
            风险等级: 'low', 'medium', 'high'
        """
        if score >= 70:
            return 'low'
        elif score >= 50:
            return 'medium'
        else:
            return 'high'

    def _is_macd_golden_cross(self, factors: Dict) -> bool:
        """判断MACD金叉

        Args:
            factors: 技术指标因子字典

        Returns:
            是否金叉
        """
        macd = factors.get('macd', 0)
        signal = factors.get('macd_signal', 0)
        macd_prev = factors.get('macd_prev', 0)
        signal_prev = factors.get('macd_signal_prev', 0)

        # 当前MACD > 信号线 且 前一天MACD < 信号线
        return macd > signal and macd_prev < signal_prev

    def _is_volume_increasing(self, factors: Dict, days: int = 3) -> bool:
        """判断成交量连续递增

        Args:
            factors: 技术指标因子字典
            days: 判断天数

        Returns:
            是否连续递增
        """
        volumes = factors.get('volume_history', [])

        if len(volumes) < days:
            return False

        # 检查是否连续递增
        for i in range(len(volumes) - days + 1, len(volumes)):
            if volumes[i] <= volumes[i - 1]:
                return False

        return True

    def _generate_reasons(
        self,
        tech_score: float,
        fund_score: float,
        capital_score: float,
        factors: Dict,
        fundamental: Optional[Dict],
        filters: Dict
    ) -> List[str]:
        """生成机会原因标签

        Args:
            tech_score: 技术面评分
            fund_score: 基本面评分
            capital_score: 资金面评分
            factors: 技术指标因子
            fundamental: 基本面数据
            filters: 筛选条件

        Returns:
            原因标签列表（最多6个）
        """
        reasons = []

        # 技术面原因
        technical_conditions = filters.get('technical', [])
        if 'rsi_oversold' in technical_conditions:
            rsi = factors.get('rsi', 100)
            if rsi < 30:
                reasons.append(f'RSI超卖({rsi:.1f})')

        if 'macd_golden_cross' in technical_conditions:
            if self._is_macd_golden_cross(factors):
                reasons.append('MACD金叉')

        if 'bollinger_breakout' in technical_conditions:
            close = factors.get('close', 0)
            boll_upper = factors.get('boll_upper', float('inf'))
            if close > boll_upper:
                reasons.append('突破布林带上轨')

        if 'volume_spike' in technical_conditions:
            volume_ratio = factors.get('volume_ratio_5d', 0)
            if volume_ratio > 2.0:
                reasons.append(f'成交量放大({volume_ratio:.1f}倍)')

        # 基本面原因
        if fundamental:
            fundamental_conditions = filters.get('fundamental', [])
            pe = fundamental.get('pe_ratio') or fundamental.get('pe')
            roe = fundamental.get('roe')
            gross_margin = fundamental.get('gross_margin')
            debt_ratio = fundamental.get('debt_ratio')

            if 'low_pe' in fundamental_conditions and pe and 0 < pe < 30:
                reasons.append(f'低PE({pe:.1f})')

            if 'high_roe' in fundamental_conditions and roe and roe > 15:
                reasons.append(f'高ROE({roe:.1f}%)')

            if 'high_gross_margin' in fundamental_conditions and gross_margin and gross_margin > 30:
                reasons.append(f'高毛利率({gross_margin:.1f}%)')

            if 'low_debt_ratio' in fundamental_conditions and debt_ratio and debt_ratio < 50:
                reasons.append(f'低负债率({debt_ratio:.1f}%)')

        # 资金面原因（基于成交量）
        if factors.get('volume_ratio_5d', 0) > 1.5:
            reasons.append('成交活跃')

        if self._is_volume_increasing(factors):
            reasons.append('成交量递增')

        # 综合评分原因
        if tech_score >= 80:
            reasons.append('技术面强势')
        if fund_score >= 80:
            reasons.append('基本面优质')
        if capital_score >= 80:
            reasons.append('资金面活跃')

        # 如果没有匹配的原因，添加通用原因
        if not reasons:
            if tech_score + fund_score + capital_score >= 180:
                reasons.append('综合评分优秀')
            elif tech_score > fund_score and tech_score > capital_score:
                reasons.append('技术指标良好')
            elif fund_score > tech_score and fund_score > capital_score:
                reasons.append('基本面稳健')
            else:
                reasons.append('多维度平衡')

        # 返回前6个原因
        return reasons[:6]


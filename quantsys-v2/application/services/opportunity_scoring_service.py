"""
机会评分引擎

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
from application.services.scoring.technical_scorer import TechnicalScorer
from application.services.scoring.fundamental_scorer import FundamentalScorer
import structlog

logger = structlog.get_logger(__name__)


class OpportunityScoringService:
    """机会评分引擎"""

    def __init__(
        self,
        kline_repo: KlineORMRepository,
        stock_repo: StockORMRepository,
        factor_adapter
    ):
        self.kline_repo = kline_repo
        self.stock_repo = stock_repo
        self.factor_adapter = factor_adapter
        # 初始化评分器
        self.technical_scorer = TechnicalScorer(factor_adapter)
        self.fundamental_scorer = FundamentalScorer()

    def score_stocks(
        self,
        symbols: List[str],
        filters: Dict,
        weights: Optional[Dict] = None
    ) -> List[Dict]:
        """批量评分股票

        Args:
            symbols: 股票代码列表
            filters: 筛选条件，包含 technical 和 fundamental 列表
            weights: 动态权重字典，如 {'technical': 0.5, 'fundamental': 0.3, 'capital': 0.2}
                    如果为 None，使用默认固定权重

        Returns:
            评分结果列表，每个元素包含 symbol, score, technical_score 等字段
        """
        if not symbols:
            return []

        # 验证和归一化权重
        if weights is not None:
            weights = self._normalize_weights(weights)

        # 批量查询K线数据
        klines_map = self.kline_repo.batch_get_recent_klines(symbols, days=120)

        # 批量查询基本面数据
        fundamentals_map = self.stock_repo.batch_get_fundamentals(symbols)

        # 并行处理每只股票
        opportunities = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(
                    self._score_single_stock,
                    symbol,
                    klines_map.get(symbol, []),
                    fundamentals_map.get(symbol),
                    filters,
                    weights
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
                    logger.error(f"{symbol}: 评分失败 - {e}")

        return opportunities

    def _score_single_stock(
        self,
        symbol: str,
        klines: List[Dict],
        fundamental: Optional[Dict],
        filters: Dict,
        weights: Optional[Dict] = None
    ) -> Optional[Dict]:
        """评分单只股票

        Args:
            symbol: 股票代码
            klines: K线数据列表
            fundamental: 基本面数据
            filters: 筛选条件
            weights: 动态权重字典

        Returns:
            评分结果字典，如果数据不足返回 None
        """
        try:
            # 检查K线数据是否充足
            if len(klines) < 30:
                logger.warning(f"{symbol}: K线数据不足 ({len(klines)}条)")
                return None

            # 计算技术指标因子
            factors = self._calculate_factors(klines)

            # 新增：评估筛选条件（优先使用新格式）
            conditions = filters.get('conditions', [])
            logic = filters.get('logic', 'AND')

            if conditions:
                if not self._evaluate_conditions(conditions, logic, fundamental or {}, factors):
                    return None  # 不满足条件，跳过


            # === 使用 TechnicalScorer 计算技术面评分 ===
            tech_result = self.technical_scorer.score(factors)
            tech_score = tech_result['total']
            # 可选：记录评分明细用于调试
            # logger.debug(f"{symbol} 技术面明细: {tech_result['breakdown']}")

            # === 使用 FundamentalScorer 计算基本面评分 ===
            if fundamental and not filters.get('fundamental'):
                # 无筛选条件时使用新评分器
                fund_result = self.fundamental_scorer.score(fundamental)
                fund_score = fund_result['total']
                # 可选：记录评分明细用于调试
                # logger.debug(f"{symbol} 基本面明细: {fund_result['breakdown']}")
            else:
                # 有筛选条件时使用旧逻辑（保持向后兼容）
                fund_score = self._calculate_fundamental_score(
                    fundamental,
                    filters.get('fundamental', [])
                )

            capital_score = self._calculate_capital_score(factors)

            # 计算综合评分
            total_score = self._calculate_comprehensive_score(
                tech_score,
                fund_score,
                capital_score,
                weights
            )

            # 获取股票名称
            stock_info = self.stock_repo.get_by_symbol(symbol, ['name'])
            stock_name = stock_info['name'] if stock_info else symbol

            return {
                'symbol': symbol,
                'name': stock_name,
                'score': round(total_score),
                'technical_score': round(tech_score),
                'fundamental_score': round(fund_score),
                'capital_score': round(capital_score),
                'confidence': round(total_score / 100, 2),
                'risk_level': self._calculate_risk_level(total_score),
                'signal_type': 'buy',
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"{symbol}: 评分失败 - {e}", exc_info=True)
            return None

    def _calculate_factors(self, klines: List[Dict]) -> Dict:
        """计算技术指标因子

        Args:
            klines: K线数据列表

        Returns:
            因子字典
        """
        # klines is a List[Dict], check if empty using len()
        if not klines or len(klines) == 0:
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

            # === 新增：ADX 计算 ===
            adx = self.factor_adapter.calculate('adx', klines)
            if adx is not None:
                factors['adx'] = adx
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
            logger.error(f"计算因子失败: {e}")

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
        # 如果没有指定条件，使用默认评分逻辑计算实际分数
        if not conditions:
            return self._calculate_default_technical_score(factors)

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
        # 如果没有基本面数据，返回中性评分
        if not fundamental:
            return 50.0

        # 如果没有指定条件，使用默认评分逻辑计算实际分数
        if not conditions:
            return self._calculate_default_fundamental_score(fundamental)

        score = 0.0

        for condition in conditions:
            if condition == 'pe_low':
                # PE < 30
                if fundamental.get('pe', float('inf')) < 30:
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
        """计算资金面评分（基于成交量指标）- 灰度化连续评分

        Args:
            factors: 技术指标因子字典

        Returns:
            资金面评分 (0-100)
        """
        score = 50.0  # 基础分

        # === 1. 5日成交量增长评分 (±20分) ===
        volume_ratio = factors.get('volume_ratio_5d', 1.0)
        if volume_ratio > 1.0:
            # 放量：线性加分，最多+20分
            # ratio=1.0 → +0, ratio=2.0 → +10, ratio≥3.0 → +20
            volume_growth_score = min(20, (volume_ratio - 1.0) * 10)
            score += volume_growth_score
        elif volume_ratio < 0.8:
            # 缩量：线性扣分，最多-15分
            # ratio=0.8 → -0, ratio=0.5 → -10, ratio≤0.2 → -15
            volume_shrink_score = max(-15, (volume_ratio - 0.8) * 25)
            score += volume_shrink_score

        # === 2. 成交量连续递增 (+15分) ===
        if self._is_volume_increasing(factors, days=3):
            score += 15

        # === 3. 当前成交量 vs 20日均量 (±10分) ===
        volume = factors.get('volume', 0)
        volume_ma20 = factors.get('volume_ma20', 0)
        if volume_ma20 > 0:
            vol_vs_ma20_ratio = volume / volume_ma20
            if vol_vs_ma20_ratio > 1.2:
                # 超过20日均量20%以上，线性加分
                score += min(10, (vol_vs_ma20_ratio - 1) * 50)
            elif vol_vs_ma20_ratio < 0.8:
                # 低于20日均量20%以上，线性扣分
                score += max(-10, (vol_vs_ma20_ratio - 1) * 50)

        # === 4. 5日均量 vs 20日均量 (±10分) ===
        volume_ma5 = factors.get('volume_ma5', 0)
        if volume_ma20 > 0 and volume_ma5 > 0:
            ma5_vs_ma20_ratio = volume_ma5 / volume_ma20
            if ma5_vs_ma20_ratio > 1.1:
                # 短期均量强于长期均量，加分
                score += min(10, (ma5_vs_ma20_ratio - 1) * 100)
            elif ma5_vs_ma20_ratio < 0.9:
                # 短期均量弱于长期均量，扣分
                score += max(-10, (ma5_vs_ma20_ratio - 1) * 100)

        # 截断到 0-100
        return max(0, min(100, score))

    def _calculate_comprehensive_score(
        self,
        tech_score: float,
        fund_score: float,
        capital_score: float,
        weights: Optional[Dict] = None
    ) -> float:
        """计算综合评分

        Args:
            tech_score: 技术面评分
            fund_score: 基本面评分
            capital_score: 资金面评分
            weights: 动态权重字典，如果为 None 使用默认权重

        Returns:
            综合评分 (0-100)
        """
        if weights is None:
            # 默认固定权重：技术面×0.5 + 基本面×0.3 + 资金面×0.2
            return tech_score * 0.5 + fund_score * 0.3 + capital_score * 0.2
        else:
            # 使用动态权重
            w_tech = weights.get('technical', 0.5)
            w_fund = weights.get('fundamental', 0.3)
            w_capital = weights.get('capital', 0.2)
            return tech_score * w_tech + fund_score * w_fund + capital_score * w_capital

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

    def _evaluate_conditions(
        self,
        conditions: List[Dict],
        logic: str,
        stock_data: Dict,
        factors: Dict
    ) -> bool:
        """
        评估筛选条件

        Args:
            conditions: 条件列表 [{"field": "roe", "operator": ">=", "value": 15}, ...]
            logic: 逻辑关系 "AND" 或 "OR"
            stock_data: 基本面数据（来自 stocks 表）
            factors: 技术指标数据（从 klines 计算）

        Returns:
            是否满足条件
        """
        if not conditions:
            return True

        results = []
        for cond in conditions:
            field = cond.get('field')
            operator = cond.get('operator')
            threshold = cond.get('value')

            # 从 stock_data 或 factors 中获取字段值
            value = stock_data.get(field) if stock_data else None
            if value is None:
                value = factors.get(field)

            if value is None:
                results.append(False)
                continue

            # 执行比较
            if operator == '>=':
                results.append(value >= threshold)
            elif operator == '<=':
                results.append(value <= threshold)
            elif operator == '>':
                results.append(value > threshold)
            elif operator == '<':
                results.append(value < threshold)
            elif operator == '==':
                results.append(value == threshold)
            elif operator == '!=':
                results.append(value != threshold)
            else:
                results.append(False)

        # 根据逻辑关系合并结果
        if logic == 'OR':
            return any(results)
        else:  # AND
            return all(results)

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

    def _calculate_default_technical_score(self, factors: Dict) -> float:
        """计算默认技术面评分（无筛选条件时使用）

        综合评估RSI、MACD、布林带、成交量等指标

        Args:
            factors: 技术指标因子字典

        Returns:
            技术面评分 (0-100)
        """
        score = 50.0  # 基础分

        # RSI 评分 (±15分)
        rsi = factors.get('rsi')
        if rsi is not None:
            if rsi < 30:  # 超卖
                score += 15
            elif rsi > 70:  # 超买
                score -= 15
            elif 40 <= rsi <= 60:  # 中性区间
                score += 5

        # MACD 评分 (±10分)
        if self._is_macd_golden_cross(factors):
            score += 10
        else:
            macd = factors.get('macd', 0)
            signal = factors.get('macd_signal', 0)
            if macd < signal:
                score -= 10

        # 布林带评分 (±10分)
        close = factors.get('close', 0)
        boll_upper = factors.get('boll_upper')
        if close > 0 and boll_upper is not None:
            if close > boll_upper:  # 突破上轨
                score += 10
            elif close < boll_upper * 0.95:  # 远离上轨
                score -= 5

        # 成交量评分 (±15分)
        volume_ratio = factors.get('volume_ratio_5d', 1.0)
        if volume_ratio > 1.5:  # 放量
            score += 15
        elif volume_ratio < 0.8:  # 缩量
            score -= 10

        return max(0, min(100, score))

    def _calculate_default_fundamental_score(self, fundamental: Dict) -> float:
        """计算默认基本面评分（无筛选条件时使用）

        综合评估PE、ROE、毛利率、负债率等指标

        Args:
            fundamental: 基本面数据字典

        Returns:
            基本面评分 (0-100)
        """
        score = 50.0  # 基础分

        # PE 评分 (±15分)
        pe = fundamental.get('pe')
        if pe is not None and pe > 0:
            if pe < 15:  # 低估
                score += 15
            elif pe < 30:  # 合理
                score += 8
            elif pe > 50:  # 高估
                score -= 15

        # ROE 评分 (±15分)
        roe = fundamental.get('roe')
        if roe is not None:
            if roe > 20:  # 优秀
                score += 15
            elif roe > 15:  # 良好
                score += 10
            elif roe > 10:  # 一般
                score += 5
            elif roe < 5:  # 较差
                score -= 10

        # 毛利率评分 (±10分)
        gross_margin = fundamental.get('gross_margin')
        if gross_margin is not None:
            if gross_margin > 40:  # 优秀
                score += 10
            elif gross_margin > 30:  # 良好
                score += 5
            elif gross_margin < 20:  # 较差
                score -= 10

        # 负债率评分 (±10分)
        debt_ratio = fundamental.get('debt_ratio')
        if debt_ratio is not None:
            if debt_ratio < 30:  # 低负债
                score += 10
            elif debt_ratio < 50:  # 合理
                score += 5
            elif debt_ratio > 70:  # 高负债
                score -= 10

        return max(0, min(100, score))

    def _normalize_weights(self, weights: Dict) -> Dict:
        """归一化权重，确保权重和为 1

        Args:
            weights: 原始权重字典

        Returns:
            归一化后的权重字典
        """
        w_tech = weights.get('technical', 0.5)
        w_fund = weights.get('fundamental', 0.3)
        w_capital = weights.get('capital', 0.2)
        
        total = w_tech + w_fund + w_capital
        
        if total == 0:
            logger.warning("权重总和为 0，使用默认权重")
            return {'technical': 0.5, 'fundamental': 0.3, 'capital': 0.2}
        
        return {
            'technical': w_tech / total,
            'fundamental': w_fund / total,
            'capital': w_capital / total
        }

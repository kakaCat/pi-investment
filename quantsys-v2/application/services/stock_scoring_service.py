"""
股票综合评分服务

评分维度：
- 技术面 (40%): RSI, MACD, 均线趋势, 布林带
- 基本面 (30%): PE, PB, ROE, 负债率
- 动量 (20%): 价格趋势, 成交量放大
- 质量 (10%): 毛利率, 净利率稳定性
"""
import structlog
from typing import Dict, Optional
from datetime import datetime

logger = structlog.get_logger(__name__)


class StockScoringService:
    """股票评分服务"""

    def __init__(self, stock_repo=None, factor_repo=None):
        """
        初始化评分服务

        Args:
            stock_repo: 股票数据仓库（可选，默认通过 ServiceFactory 获取）
            factor_repo: 因子数据仓库（可选，默认通过 ServiceFactory 获取）
        """
        if stock_repo is None or factor_repo is None:
            from infrastructure.services.service_factory import ServiceFactory
            stock_repo = stock_repo or ServiceFactory.get_stock_repository()
            factor_repo = factor_repo or ServiceFactory.get_factor_repository()
        self.stock_repo = stock_repo
        self.factor_repo = factor_repo

    def calculate_comprehensive_score(self, symbol: str) -> Dict:
        """
        计算股票综合评分

        Args:
            symbol: 股票代码

        Returns:
            {
                'symbol': str,
                'name': str,
                'total_score': float,
                'technical_score': float,
                'fundamental_score': float,
                'momentum_score': float,
                'quality_score': float,
                'grade': str,
                'signals': list,
                'timestamp': str
            }
        """
        try:
            # 1. 获取股票基本信息
            stock_info = self.stock_repo.get_by_symbol(symbol)
            if not stock_info:
                return {'error': f'股票 {symbol} 不存在'}

            # 2. 获取最新因子数据
            factors = self.factor_repo.get_latest_factors(symbol)
            if not factors:
                return {'error': f'股票 {symbol} 暂无因子数据'}

            # 3. 检查数据完整性
            missing_data = self._check_missing_data(factors)

            # 4. 计算各维度得分
            technical_score = self._calculate_technical_score(factors)
            fundamental_score = self._calculate_fundamental_score(factors)
            momentum_score = self._calculate_momentum_score(factors)
            quality_score = self._calculate_quality_score(factors)

            # 5. 加权计算总分
            total_score = (
                technical_score * 0.40 +
                fundamental_score * 0.30 +
                momentum_score * 0.20 +
                quality_score * 0.10
            )

            # 6. 生成信号和建议
            signals = self._generate_signals(factors, total_score)
            grade = self._score_to_grade(total_score)

            result = {
                'symbol': symbol,
                'name': stock_info.name,
                'market': stock_info.market,
                'total_score': round(total_score, 2),
                'technical_score': round(technical_score, 2),
                'fundamental_score': round(fundamental_score, 2),
                'momentum_score': round(momentum_score, 2),
                'quality_score': round(quality_score, 2),
                'grade': grade,
                'signals': signals,
                'timestamp': datetime.now().isoformat()
            }

            # 7. 添加数据完整性信息
            if missing_data:
                result['missing_data'] = missing_data
                result['data_completeness'] = self._calculate_completeness(missing_data)

            return result

        except Exception as e:
            logger.error(f"计算 {symbol} 评分失败: {e}", exc_info=True)
            return {'error': str(e)}

    def _calculate_technical_score(self, factors: Dict) -> float:
        """
        技术面评分 (0-100)

        指标权重:
        - RSI (30%): 相对强弱指标
        - MACD (30%): 趋势指标
        - 均线 (25%): 价格位置
        - 布林带 (15%): 波动率
        """
        score = 0.0

        # RSI 指标 (30分)
        rsi = factors.get('rsi')
        if rsi is not None:
            if 30 <= rsi <= 40:  # 弱超卖，机会
                score += 30
            elif 40 < rsi <= 60:  # 中性
                score += 20
            elif 60 < rsi <= 70:  # 偏强
                score += 15
            elif rsi < 30:  # 超卖
                score += 25
            else:  # rsi > 70, 超买
                score += 5

        # MACD 指标 (30分)
        macd = factors.get('macd')
        macd_signal = factors.get('macd_signal')
        macd_hist = factors.get('macd_hist')

        if macd is not None and macd_signal is not None:
            if macd > macd_signal and macd_hist and macd_hist > 0:
                # 金叉且柱状图上升
                score += 30
            elif macd > macd_signal:
                # 仅金叉
                score += 20
            elif macd < macd_signal and macd_hist and macd_hist < 0:
                # 死叉且柱状图下降
                score += 5
            else:
                score += 10

        # 均线位置 (25分)
        close = factors.get('close')
        ma5 = factors.get('ma5')
        ma20 = factors.get('ma20')
        ma60 = factors.get('ma60')

        if close and ma5 and ma20 and ma60:
            # 多头排列: close > ma5 > ma20 > ma60
            if close > ma5 > ma20 > ma60:
                score += 25
            elif close > ma20 > ma60:
                score += 20
            elif close > ma60:
                score += 15
            else:
                score += 5

        # 布林带位置 (15分)
        bb_position = factors.get('bb_position')
        if bb_position is not None:
            if 0.2 <= bb_position <= 0.4:  # 下轨附近，支撑
                score += 15
            elif 0.4 < bb_position <= 0.6:  # 中轨附近
                score += 10
            elif 0.6 < bb_position <= 0.8:  # 上轨附近
                score += 8
            else:  # 极端位置
                score += 5

        return min(100, max(0, score))

    def _calculate_fundamental_score(self, factors: Dict) -> float:
        """
        基本面评分 (0-100)

        指标权重:
        - PE (30%): 市盈率估值
        - ROE (30%): 盈利能力
        - 负债率 (25%): 财务健康
        - PB (15%): 市净率估值
        """
        score = 0.0

        # PE 估值 (30分)
        pe = factors.get('pe')
        if pe is not None and pe > 0:
            if pe < 15:
                score += 30
            elif 15 <= pe < 25:
                score += 25
            elif 25 <= pe < 40:
                score += 15
            elif 40 <= pe < 60:
                score += 5
            else:  # pe >= 60
                score += 0

        # ROE 盈利能力 (30分)
        roe = factors.get('roe')
        if roe is not None:
            if roe >= 0.20:  # 20%+
                score += 30
            elif roe >= 0.15:  # 15-20%
                score += 25
            elif roe >= 0.10:  # 10-15%
                score += 15
            elif roe >= 0.05:  # 5-10%
                score += 5
            else:  # < 5%
                score += 0

        # 负债率 (25分)
        debt_ratio = factors.get('debt_ratio') or factors.get('debt_to_asset_ratio')
        if debt_ratio is not None:
            if debt_ratio < 0.30:  # 低负债
                score += 25
            elif debt_ratio < 0.50:  # 中等负债
                score += 20
            elif debt_ratio < 0.70:  # 偏高负债
                score += 10
            else:  # 高负债
                score += 0

        # PB 估值 (15分)
        pb = factors.get('pb')
        if pb is not None and pb > 0:
            if pb < 1.5:
                score += 15
            elif pb < 3.0:
                score += 10
            elif pb < 5.0:
                score += 5
            else:
                score += 0

        return min(100, max(0, score))

    def _calculate_momentum_score(self, factors: Dict) -> float:
        """
        动量评分 (0-100)

        指标权重:
        - 价格涨跌幅 (50%): 短期趋势
        - 成交量变化 (30%): 资金关注度
        - 连续上涨天数 (20%): 趋势强度
        """
        score = 50.0  # 基准分

        # 价格涨跌幅 (50分)
        change_pct_5d = factors.get('change_pct_5d')
        change_pct_20d = factors.get('change_pct_20d')

        if change_pct_5d is not None:
            if change_pct_5d > 10:  # 5日涨10%+
                score += 25
            elif change_pct_5d > 5:
                score += 20
            elif change_pct_5d > 0:
                score += 10
            elif change_pct_5d > -5:
                score -= 5
            else:  # 跌超5%
                score -= 15

        if change_pct_20d is not None:
            if change_pct_20d > 20:  # 20日涨20%+
                score += 25
            elif change_pct_20d > 10:
                score += 15
            elif change_pct_20d > 0:
                score += 5
            else:
                score -= 10

        # 成交量变化 (30分)
        volume_ratio = factors.get('volume_ratio')
        if volume_ratio is not None:
            if volume_ratio > 2.0:  # 放量2倍+
                score += 30
            elif volume_ratio > 1.5:
                score += 20
            elif volume_ratio > 1.0:
                score += 10
            else:  # 缩量
                score += 0

        # 连续上涨天数 (20分)
        consecutive_up = factors.get('consecutive_up_days', 0)
        if consecutive_up >= 5:
            score += 20
        elif consecutive_up >= 3:
            score += 15
        elif consecutive_up >= 1:
            score += 10

        return min(100, max(0, score))

    def _calculate_quality_score(self, factors: Dict) -> float:
        """
        质量评分 (0-100)

        指标权重:
        - 毛利率 (40%): 产品竞争力
        - 净利率 (40%): 经营效率
        - 现金流 (20%): 造血能力
        """
        score = 50.0  # 基准分

        # 毛利率 (40分)
        gross_margin = factors.get('gross_margin')
        if gross_margin is not None:
            if gross_margin >= 0.50:  # 50%+
                score += 40
            elif gross_margin >= 0.30:
                score += 30
            elif gross_margin >= 0.20:
                score += 20
            elif gross_margin >= 0.10:
                score += 10
            else:
                score += 0

        # 净利率 (40分)
        net_margin = factors.get('net_margin')
        if net_margin is not None:
            if net_margin >= 0.20:  # 20%+
                score += 40
            elif net_margin >= 0.10:
                score += 30
            elif net_margin >= 0.05:
                score += 20
            else:
                score += 10

        # 经营现金流/净利润 (20分)
        ocf_to_profit = factors.get('operating_cashflow_ratio')
        if ocf_to_profit is not None:
            if ocf_to_profit >= 1.2:  # 现金流好于利润
                score += 20
            elif ocf_to_profit >= 1.0:
                score += 15
            elif ocf_to_profit >= 0.8:
                score += 10
            else:
                score += 0

        return min(100, max(0, score))

    def _generate_signals(self, factors: Dict, total_score: float) -> list:
        """生成交易信号和建议"""
        signals = []

        # 综合评分建议
        if total_score >= 80:
            signals.append({
                'type': 'strong_buy',
                'message': '综合评分优秀，强烈推荐关注',
                'priority': 'high'
            })
        elif total_score >= 70:
            signals.append({
                'type': 'buy',
                'message': '综合评分良好，可考虑买入',
                'priority': 'medium'
            })
        elif total_score <= 40:
            signals.append({
                'type': 'avoid',
                'message': '综合评分较低，建议回避',
                'priority': 'high'
            })

        # RSI 超买超卖信号
        rsi = factors.get('rsi')
        if rsi and rsi < 30:
            signals.append({
                'type': 'oversold',
                'message': f'RSI={rsi:.1f}，超卖区域，可能反弹',
                'priority': 'medium'
            })
        elif rsi and rsi > 70:
            signals.append({
                'type': 'overbought',
                'message': f'RSI={rsi:.1f}，超买区域，注意回调风险',
                'priority': 'medium'
            })

        # MACD 金叉死叉
        macd = factors.get('macd')
        macd_signal = factors.get('macd_signal')
        if macd and macd_signal:
            if macd > macd_signal and abs(macd - macd_signal) < 0.1:
                signals.append({
                    'type': 'golden_cross',
                    'message': 'MACD金叉，趋势转好',
                    'priority': 'high'
                })
            elif macd < macd_signal and abs(macd - macd_signal) < 0.1:
                signals.append({
                    'type': 'death_cross',
                    'message': 'MACD死叉，趋势转弱',
                    'priority': 'high'
                })

        return signals

    def _score_to_grade(self, score: float) -> str:
        """评分转等级"""
        if score >= 90:
            return 'A+'
        elif score >= 80:
            return 'A'
        elif score >= 70:
            return 'B+'
        elif score >= 60:
            return 'B'
        elif score >= 50:
            return 'C'
        else:
            return 'D'

    def _check_missing_data(self, factors: Dict) -> Dict[str, list]:
        """
        检查缺失的数据指标

        Returns:
            {
                'technical': ['rsi', 'macd', ...],
                'fundamental': ['pe', 'roe', ...],
                'momentum': ['change_pct_5d', ...],
                'quality': ['gross_margin', ...]
            }
        """
        missing = {}

        # 技术面关键指标
        technical_keys = ['rsi', 'macd', 'macd_signal', 'close', 'ma5', 'ma20', 'ma60', 'bb_position']
        technical_missing = [k for k in technical_keys if factors.get(k) is None]
        if technical_missing:
            missing['technical'] = technical_missing

        # 基本面关键指标
        fundamental_keys = ['pe', 'roe', 'debt_ratio', 'debt_to_asset_ratio', 'pb']
        fundamental_missing = [k for k in fundamental_keys if factors.get(k) is None]
        if fundamental_missing:
            missing['fundamental'] = fundamental_missing

        # 动量关键指标
        momentum_keys = ['change_pct_5d', 'change_pct_20d', 'volume_ratio']
        momentum_missing = [k for k in momentum_keys if factors.get(k) is None]
        if momentum_missing:
            missing['momentum'] = momentum_missing

        # 质量关键指标
        quality_keys = ['gross_margin', 'net_margin', 'operating_cashflow_ratio']
        quality_missing = [k for k in quality_keys if factors.get(k) is None]
        if quality_missing:
            missing['quality'] = quality_missing

        return missing

    def _calculate_completeness(self, missing_data: Dict[str, list]) -> Dict[str, any]:
        """
        计算数据完整性百分比

        Returns:
            {
                'overall': 0.75,  # 总体完整度
                'technical': 0.875,
                'fundamental': 0.6,
                'momentum': 1.0,
                'quality': 0.67,
                'warning': '基本面数据不完整，评分可能不准确'
            }
        """
        total_fields = {
            'technical': 8,
            'fundamental': 5,
            'momentum': 3,
            'quality': 3
        }

        completeness = {}
        total_missing = 0
        total_fields_count = sum(total_fields.values())

        for dimension, count in total_fields.items():
            missing_count = len(missing_data.get(dimension, []))
            completeness[dimension] = round((count - missing_count) / count, 2)
            total_missing += missing_count

        completeness['overall'] = round((total_fields_count - total_missing) / total_fields_count, 2)

        # 生成警告信息
        warnings = []
        if completeness['overall'] < 0.5:
            warnings.append('数据严重不完整（< 50%），评分仅供参考')
        elif completeness['overall'] < 0.7:
            warnings.append('数据完整度较低（< 70%），评分可能不准确')

        if completeness.get('fundamental', 1.0) < 0.5:
            warnings.append('基本面数据严重缺失，建议补充财务数据')
        elif completeness.get('fundamental', 1.0) < 0.8:
            warnings.append('基本面数据不完整，估值评分可能偏低')

        if warnings:
            completeness['warning'] = '; '.join(warnings)

        return completeness

"""
市场情绪分析服务

聚合多个市场指标，综合判断市场情绪（恐惧/贪婪）
"""
import structlog
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = structlog.get_logger(__name__)


class MarketSentimentService:
    """市场情绪分析服务"""

    def __init__(self, data_service):
        """
        初始化市场情绪服务

        Args:
            data_service: 数据服务实例
        """
        self.ds = data_service

    def analyze_market_sentiment(self) -> Dict:
        """
        分析市场情绪

        综合多个维度判断市场情绪：
        1. 涨跌家数比
        2. 市场成交量
        3. 主要指数表现
        4. 市场波动率
        5. 新高新低比

        Returns:
            {
                'sentiment_score': float,      # 情绪分数 (0-100)
                'sentiment_level': str,        # 情绪等级
                'fear_greed_index': float,     # 恐惧贪婪指数 (0-100)
                'indicators': {                # 各项指标
                    'advance_decline': {...},  # 涨跌家数
                    'volume': {...},           # 成交量
                    'index_performance': {...},# 指数表现
                    'volatility': {...},       # 波动率
                    'new_high_low': {...}      # 新高新低
                },
                'market_phase': str,           # 市场阶段
                'recommendation': str,         # 操作建议
                'timestamp': str
            }
        """
        try:
            # 1. 全市场涨跌家数
            advance_decline = self._get_advance_decline_ratio()

            # 2. 全市场成交额趋势
            volume_indicator = self._get_volume_indicator()

            # 3. 市场趋势（等权日收益）
            index_performance = self._get_index_performance()

            # 4. 市场波动率
            volatility = self._calculate_market_volatility()

            # 5. 新高新低比
            new_high_low = self._get_new_high_low_ratio()

            # 收集降级维度（返回 {'error': ...} 的维度不计分、显式列出）
            degraded_dimensions = []
            dimension_map = {
                'advance_decline': advance_decline,
                'volume': volume_indicator,
                'index': index_performance,
                'volatility': volatility,
                'new_high_low': new_high_low,
            }
            for name, dim in dimension_map.items():
                if isinstance(dim, dict) and dim.get('error'):
                    degraded_dimensions.append({'dimension': name, 'reason': dim['error']})

            # 覆盖率守卫：涨跌统计股票数过少（K线更新异常）时判断必然失真，
            # 数据"存在"不等于数据"够"——显式降级而非给出貌似完整的结论
            ad = dimension_map.get('advance_decline', {})
            if isinstance(ad, dict) and not ad.get('error'):
                ad_total = (ad.get('up_count') or 0) + (ad.get('down_count') or 0) \
                    + (ad.get('flat_count') or 0)
                if 0 < ad_total < 1000:
                    degraded_dimensions.append({
                        'dimension': 'coverage',
                        'reason': f'K线覆盖不足（涨跌统计仅 {ad_total} 只股票，正常应 >4000），结果可能失真',
                    })

            # 6. 综合计算情绪分数
            sentiment_score = self._calculate_sentiment_score(dimension_map)

            # 7. 判断情绪等级和市场阶段
            sentiment_level = self._get_sentiment_level(sentiment_score)
            fear_greed_index = sentiment_score  # 0-100，越高越贪婪
            market_phase = self._determine_market_phase(sentiment_score, volatility)
            recommendation = self._generate_recommendation(sentiment_level, market_phase)

            return {
                'sentiment_score': round(sentiment_score, 2),
                'sentiment_level': sentiment_level,
                'fear_greed_index': round(fear_greed_index, 2),
                'indicators': {
                    'advance_decline': advance_decline,
                    'volume': volume_indicator,
                    'index_performance': index_performance,
                    'volatility': volatility,
                    'new_high_low': new_high_low,
                },
                'degraded_dimensions': degraded_dimensions,
                'degraded': len(degraded_dimensions) > 0,
                'market_phase': market_phase,
                'recommendation': recommendation,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"分析市场情绪失败: {e}", exc_info=True)
            return {'error': str(e)}

    def _get_advance_decline_ratio(self) -> Dict:
        """
        获取涨跌家数比（全市场聚合，最新交易日 vs 前一交易日）

        涨跌比 > 2: 市场强势
        涨跌比 > 1: 市场偏强
        涨跌比 < 0.5: 市场弱势
        """
        try:
            breadth = self.ds.kline.get_market_breadth()
            if not breadth:
                return {'error': 'daily_klines 无有效涨跌数据'}

            return {
                'data_date': breadth['data_date'],
                'up_count': breadth['up_count'],
                'down_count': breadth['down_count'],
                'flat_count': breadth['flat_count'],
                'ratio': breadth['ratio'],
                'up_percentage': breadth['up_percentage'],
                'strength': self._classify_ad_ratio(breadth['ratio'])
            }

        except Exception as e:
            logger.error(f"获取涨跌家数比失败: {e}")
            return {'error': str(e)}

    def _get_volume_indicator(self) -> Dict:
        """
        获取市场成交量指标（全市场成交量：近5日均值 vs 前20日均值）

        成交量放大：市场活跃
        成交量萎缩：市场低迷
        """
        try:
            daily_volumes = self.ds.kline.get_market_turnover_by_day(days=30)

            if len(daily_volumes) < 10:
                return {'error': f'成交量数据不足（{len(daily_volumes)} 天）'}

            recent = [d['total_volume'] for d in daily_volumes[:5]]
            base = [d['total_volume'] for d in daily_volumes[5:25]]

            recent_avg = sum(recent) / len(recent) if recent else 0
            base_avg = sum(base) / len(base) if base else 0

            if base_avg <= 0:
                return {'error': '基准成交量为 0'}

            volume_ratio = recent_avg / base_avg

            return {
                'data_date': daily_volumes[0]['trade_date'],
                'recent_avg_volume': round(recent_avg, 2),
                'base_avg_volume': round(base_avg, 2),
                'volume_ratio': round(volume_ratio, 2),
                'status': self._classify_volume(volume_ratio)
            }

        except Exception as e:
            logger.error(f"获取成交量指标失败: {e}")
            return {'error': str(e)}

    def _get_index_performance(self) -> Dict:
        """
        获取市场趋势（全市场等权日收益，近 5 日）

        注：daily_klines 中指数代码与股票代码冲突（'000001' 是平安银行），
        不能用指数代码查询，故改用全市场等权收益衡量市场趋势。
        """
        try:
            returns = self.ds.kline.get_market_daily_returns(days=10)
            returns = [r for r in returns if r.get('avg_return') is not None]

            if len(returns) < 3:
                return {'error': f'市场收益数据不足（{len(returns)} 天）'}

            recent5 = returns[:5]
            positive_count = sum(1 for r in recent5 if r['avg_return'] > 0)
            avg_return_5d = sum(r['avg_return'] for r in recent5) / len(recent5)

            return {
                'data_date': returns[0]['trade_date'],
                'positive_count': positive_count,
                'total_count': len(recent5),
                'avg_return_5d_pct': round(avg_return_5d * 100, 3),
                'market_trend': self._classify_index_trend(positive_count, len(recent5))
            }

        except Exception as e:
            logger.error(f"获取市场趋势失败: {e}")
            return {'error': str(e)}

    def _calculate_market_volatility(self) -> Dict:
        """
        计算市场波动率（全市场等权日收益的近 30 日标准差）
        """
        try:
            returns = self.ds.kline.get_market_daily_returns(days=40)
            returns = [r['avg_return'] for r in returns if r.get('avg_return') is not None]

            if len(returns) < 10:
                return {'error': f'波动率数据不足（{len(returns)} 天）'}

            import statistics
            volatility = statistics.stdev(returns[:30]) * 100  # 转换为百分比

            return {
                'volatility': round(volatility, 2),
                'level': self._classify_volatility(volatility)
            }

        except Exception as e:
            logger.error(f"计算波动率失败: {e}")
            return {'error': str(e)}

    def _get_new_high_low_ratio(self) -> Dict:
        """
        获取新高新低比（近一年新高/新低家数，最新交易日收盘价判定）
        """
        try:
            counts = self.ds.kline.get_new_high_low_counts(window_days=365)
            if not counts:
                return {'error': '新高新低数据不可用'}

            high = counts['new_high_count']
            low = counts['new_low_count']
            ratio = high / low if low > 0 else (999 if high > 0 else 1.0)

            return {
                'data_date': counts['data_date'],
                'new_high_count': high,
                'new_low_count': low,
                'ratio': round(ratio, 2),
                'signal': 'bullish' if ratio > 1.5 else ('bearish' if ratio < 0.67 else 'neutral')
            }

        except Exception as e:
            logger.error(f"获取新高新低比失败: {e}")
            return {'error': str(e)}

    def _calculate_sentiment_score(self, indicators: Dict) -> float:
        """
        综合计算情绪分数 (0-100)

        权重分配：
        - 涨跌家数比: 30%
        - 成交量: 20%
        - 指数表现: 25%
        - 波动率: 15%
        - 新高新低: 10%
        """
        score = 50.0  # 基准分

        # 涨跌家数比 (30分)
        ad = indicators.get('advance_decline', {})
        if ad and 'ratio' in ad:
            ratio = ad['ratio']
            if ratio > 2:
                score += 30
            elif ratio > 1.5:
                score += 20
            elif ratio > 1:
                score += 10
            elif ratio > 0.5:
                score -= 10
            else:
                score -= 20

        # 成交量 (20分)
        vol = indicators.get('volume', {})
        if vol and 'volume_ratio' in vol:
            vol_ratio = vol['volume_ratio']
            if vol_ratio > 1.5:
                score += 20
            elif vol_ratio > 1.2:
                score += 10
            elif vol_ratio < 0.8:
                score -= 10

        # 指数表现 (25分)
        idx = indicators.get('index', {})
        if idx and 'positive_count' in idx:
            pos = idx['positive_count']
            total = idx['total_count']
            if total > 0 and pos == total:
                score += 25
            elif total > 0 and pos >= total * 0.66:
                score += 15
            elif total > 0 and pos <= total * 0.33:
                score -= 15

        # 波动率 (15分) - 低波动加分，高波动减分
        vola = indicators.get('volatility', {})
        if vola and 'volatility' in vola:
            vol_val = vola['volatility']
            if vol_val < 1.0:
                score += 15
            elif vol_val < 1.5:
                score += 10
            elif vol_val > 2.5:
                score -= 10

        # 新高新低比 (10分)
        nhl = indicators.get('new_high_low', {})
        if nhl and 'ratio' in nhl:
            nhl_ratio = nhl['ratio']
            if nhl_ratio > 1.5:
                score += 10
            elif nhl_ratio > 1:
                score += 5
            elif nhl_ratio < 0.5:
                score -= 10

        return min(100, max(0, score))

    def _get_sentiment_level(self, score: float) -> str:
        """判断情绪等级"""
        if score >= 80:
            return 'extreme_greed'
        elif score >= 65:
            return 'greed'
        elif score >= 55:
            return 'neutral_positive'
        elif score >= 45:
            return 'neutral'
        elif score >= 35:
            return 'neutral_negative'
        elif score >= 20:
            return 'fear'
        else:
            return 'extreme_fear'

    def _determine_market_phase(self, sentiment: float, volatility: Dict) -> str:
        """判断市场阶段"""
        vol_level = volatility.get('level', 'normal')

        if sentiment >= 70 and vol_level in ['low', 'normal']:
            return 'bull_market'
        elif sentiment >= 55:
            return 'recovery'
        elif sentiment <= 30 and vol_level == 'high':
            return 'bear_market'
        elif sentiment <= 45:
            return 'correction'
        else:
            return 'consolidation'

    def _generate_recommendation(self, sentiment_level: str, market_phase: str) -> str:
        """生成操作建议"""
        recommendations = {
            'extreme_greed': '市场极度贪婪，谨慎追高，可考虑逢高减仓',
            'greed': '市场情绪乐观，注意风险控制',
            'neutral_positive': '市场偏乐观，可适量参与',
            'neutral': '市场情绪中性，观望为主',
            'neutral_negative': '市场偏悲观，谨慎操作',
            'fear': '市场恐慌，可关注优质标的逢低布局机会',
            'extreme_fear': '市场极度恐慌，优质标的可能出现超跌机会',
        }

        return recommendations.get(sentiment_level, '市场情绪中性，观望为主')

    # 辅助分类函数
    def _classify_ad_ratio(self, ratio: float) -> str:
        if ratio > 2:
            return 'very_strong'
        elif ratio > 1.5:
            return 'strong'
        elif ratio > 1:
            return 'positive'
        elif ratio > 0.5:
            return 'weak'
        else:
            return 'very_weak'

    def _classify_volume(self, ratio: float) -> str:
        if ratio > 1.5:
            return 'high'
        elif ratio > 1.2:
            return 'above_normal'
        elif ratio > 0.8:
            return 'normal'
        else:
            return 'low'

    def _classify_index_trend(self, positive: int, total: int) -> str:
        if total == 0:
            return 'neutral'
        pct = positive / total
        if pct >= 0.8:
            return 'strong_up'
        elif pct >= 0.6:
            return 'up'
        elif pct >= 0.4:
            return 'neutral'
        elif pct >= 0.2:
            return 'down'
        else:
            return 'strong_down'

    def _classify_volatility(self, vol: float) -> str:
        if vol > 2.5:
            return 'very_high'
        elif vol > 1.5:
            return 'high'
        elif vol > 1.0:
            return 'normal'
        else:
            return 'low'

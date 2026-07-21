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
            # 1. 获取涨跌家数比
            advance_decline = self._get_advance_decline_ratio()

            # 2. 获取市场成交量
            volume_indicator = self._get_volume_indicator()

            # 3. 获取主要指数表现
            index_performance = self._get_index_performance()

            # 4. 计算市场波动率
            volatility = self._calculate_market_volatility()

            # 5. 获取新高新低比
            new_high_low = self._get_new_high_low_ratio()

            # 6. 综合计算情绪分数
            sentiment_score = self._calculate_sentiment_score({
                'advance_decline': advance_decline,
                'volume': volume_indicator,
                'index': index_performance,
                'volatility': volatility,
                'new_high_low': new_high_low,
            })

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
                'market_phase': market_phase,
                'recommendation': recommendation,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"分析市场情绪失败: {e}", exc_info=True)
            return {'error': str(e)}

    def _get_advance_decline_ratio(self) -> Dict:
        """
        获取涨跌家数比

        涨跌比 > 2: 市场强势
        涨跌比 > 1: 市场偏强
        涨跌比 < 0.5: 市场弱势
        """
        try:
            # 获取今日涨跌家数
            # 这里简化实现：从数据库查询所有A股的涨跌情况
            stocks = self.ds.stock.get_all(market='A')

            if not stocks:
                return {'error': '无法获取股票数据'}

            up_count = 0
            down_count = 0
            flat_count = 0

            # 获取每只股票的最新K线
            for stock in stocks[:100]:  # 限制数量，避免查询过多
                try:
                    kline = self.ds.kline.get_latest_daily_kline(stock['symbol'])
                    if kline:
                        change = kline.get('pct_change', 0)
                        if change > 0:
                            up_count += 1
                        elif change < 0:
                            down_count += 1
                        else:
                            flat_count += 1
                except:
                    continue

            total = up_count + down_count + flat_count

            if total == 0:
                return {'error': '无有效数据'}

            ratio = up_count / down_count if down_count > 0 else 999

            return {
                'up_count': up_count,
                'down_count': down_count,
                'flat_count': flat_count,
                'ratio': round(ratio, 2),
                'up_percentage': round(up_count / total * 100, 2),
                'strength': self._classify_ad_ratio(ratio)
            }

        except Exception as e:
            logger.error(f"获取涨跌家数比失败: {e}")
            return {'error': str(e)}

    def _get_volume_indicator(self) -> Dict:
        """
        获取市场成交量指标

        成交量放大：市场活跃
        成交量萎缩：市场低迷
        """
        try:
            # 简化实现：使用主要指数的成交量作为市场成交量
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')

            # 获取上证指数成交量
            klines = self.ds.kline.get_daily_klines('000001.SH', start_date, end_date)

            if not klines or len(klines) < 20:
                return {'volume_ratio': 1.0, 'status': 'normal'}

            # 最近5日平均成交量
            recent_volumes = [k['volume'] for k in klines[-5:] if k.get('volume')]
            recent_avg = sum(recent_volumes) / len(recent_volumes) if recent_volumes else 0

            # 前20日平均成交量
            base_volumes = [k['volume'] for k in klines[-25:-5] if k.get('volume')]
            base_avg = sum(base_volumes) / len(base_volumes) if base_volumes else 1

            volume_ratio = recent_avg / base_avg if base_avg > 0 else 1.0

            return {
                'recent_avg_volume': round(recent_avg, 2),
                'base_avg_volume': round(base_avg, 2),
                'volume_ratio': round(volume_ratio, 2),
                'status': self._classify_volume(volume_ratio)
            }

        except Exception as e:
            logger.error(f"获取成交量指标失败: {e}")
            return {'volume_ratio': 1.0, 'status': 'normal'}

    def _get_index_performance(self) -> Dict:
        """
        获取主要指数表现

        上证指数、深证成指、创业板指
        """
        try:
            indices = {
                '000001.SH': '上证指数',
                '399001.SZ': '深证成指',
                '399006.SZ': '创业板指',
            }

            results = {}
            positive_count = 0

            for symbol, name in indices.items():
                try:
                    kline = self.ds.kline.get_latest_daily_kline(symbol)
                    if kline:
                        change = kline.get('pct_change', 0)
                        results[symbol] = {
                            'name': name,
                            'change': round(change, 2),
                            'close': round(kline.get('close', 0), 2)
                        }
                        if change > 0:
                            positive_count += 1
                except:
                    continue

            return {
                'indices': results,
                'positive_count': positive_count,
                'total_count': len(results),
                'market_trend': self._classify_index_trend(positive_count, len(results))
            }

        except Exception as e:
            logger.error(f"获取指数表现失败: {e}")
            return {'indices': {}, 'market_trend': 'neutral'}

    def _calculate_market_volatility(self) -> Dict:
        """
        计算市场波动率

        使用上证指数的历史波动率
        """
        try:
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

            klines = self.ds.kline.get_daily_klines('000001.SH', start_date, end_date)

            if not klines or len(klines) < 10:
                return {'volatility': 0, 'level': 'normal'}

            # 计算收益率标准差
            returns = []
            for i in range(1, len(klines)):
                prev_close = klines[i-1]['close']
                curr_close = klines[i]['close']
                if prev_close > 0:
                    ret = (curr_close - prev_close) / prev_close
                    returns.append(ret)

            if not returns:
                return {'volatility': 0, 'level': 'normal'}

            import statistics
            volatility = statistics.stdev(returns) * 100  # 转换为百分比

            return {
                'volatility': round(volatility, 2),
                'level': self._classify_volatility(volatility)
            }

        except Exception as e:
            logger.error(f"计算波动率失败: {e}")
            return {'volatility': 0, 'level': 'normal'}

    def _get_new_high_low_ratio(self) -> Dict:
        """
        获取新高新低比

        创新高的股票数量 vs 创新低的股票数量
        """
        try:
            # 简化实现：返回模拟数据
            # 实际应该查询达到52周新高/新低的股票数量
            return {
                'new_high_count': 50,
                'new_low_count': 30,
                'ratio': 1.67,
                'signal': 'bullish'
            }

        except Exception as e:
            logger.error(f"获取新高新低比失败: {e}")
            return {'ratio': 1.0, 'signal': 'neutral'}

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
            if pos == total:
                score += 25
            elif pos >= total * 0.66:
                score += 15
            elif pos <= total * 0.33:
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

"""
增强版买入区间分析服务
支持：动态推荐、多时间周期、成交量分析、基本面综合评分
"""
import structlog
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import pandas as pd
from domain.ports.datasource_ports import IDataProviderManager

logger = structlog.get_logger(__name__)


class EnhancedBuyRangeService:
    """增强版买入区间分析"""

    def __init__(self):
        self.logger = structlog.get_logger(__name__)

    def calculate_enhanced_buy_range(
        self,
        symbol: str,
        periods: List[str] = None,
        include_volume: bool = True,
        include_fundamental: bool = True
    ) -> Dict[str, Any]:
        """
        增强版买入区间计算

        Args:
            symbol: 股票代码
            periods: 时间周期列表 ['daily', 'weekly', 'monthly']
            include_volume: 是否包含成交量分析
            include_fundamental: 是否包含基本面分析

        Returns:
            包含多维度分析结果的字典
        """
        if periods is None:
            periods = ['daily']  # 默认仅日线

        try:

            self.logger.info(f"增强版买入区间分析: symbol={symbol}, periods={periods}")

            manager: IDataProviderManager = get_data_source_manager()
            result = {
                'symbol': symbol,
                'update_time': datetime.now().isoformat(),
                'multi_period_analysis': {},
                'recommendation': {},
                '综合评分': 0
            }

            # 1. 多周期布林带分析
            for period in periods:
                analysis = self._analyze_period(manager, symbol, period)
                if analysis:
                    result['multi_period_analysis'][period] = analysis

            # 2. 成交量分析
            if include_volume:
                volume_analysis = self._analyze_volume(manager, symbol)
                if volume_analysis:
                    result['volume_analysis'] = volume_analysis

            # 3. 基本面分析
            if include_fundamental:
                fundamental = self._analyze_fundamental(manager, symbol)
                if fundamental:
                    result['fundamental_analysis'] = fundamental

            # 4. 综合评分和推荐
            result['recommendation'] = self._generate_recommendation(result)
            result['综合评分'] = self._calculate_composite_score(result)

            return {
                'success': True,
                'data': result
            }

        except Exception as e:
            self.logger.error(f"增强版买入区间分析失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'分析失败: {str(e)}',
                'data': None
            }

    def _analyze_period(
        self,
        manager,
        symbol: str,
        period: str
    ) -> Optional[Dict[str, Any]]:
        """
        单周期布林带分析

        Args:
            manager: 数据源管理器
            symbol: 股票代码
            period: 时间周期 daily/weekly/monthly

        Returns:
            分析结果字典
        """
        try:
            # 根据周期调整数据窗口
            days_map = {'daily': 120, 'weekly': 520, 'monthly': 1560}  # 约4个月/2年/5年
            window_map = {'daily': 20, 'weekly': 13, 'monthly': 12}    # 20日/13周/12月均线

            days = days_map.get(period, 120)
            window = window_map.get(period, 20)

            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

            result = manager.get_klines(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date
            )

            if not result.success or result.data is None:
                return None

            # 转换为 DataFrame
            df = pd.DataFrame(result.data) if isinstance(result.data, list) else result.data
            if df.empty or len(df) < window:
                return None

            # 计算布林带
            df = df.tail(window * 3)  # 取足够的数据
            df['ma'] = df['close'].rolling(window=window).mean()
            df['std'] = df['close'].rolling(window=window).std()
            df['upper'] = df['ma'] + 2 * df['std']
            df['lower'] = df['ma'] - 2 * df['std']

            latest = df.iloc[-1]
            current_price = float(latest['close'])
            ma_value = float(latest['ma']) if pd.notna(latest['ma']) else current_price
            std_value = float(latest['std']) if pd.notna(latest['std']) else 0
            upper = float(latest['upper']) if pd.notna(latest['upper']) else current_price * 1.05
            lower = float(latest['lower']) if pd.notna(latest['lower']) else current_price * 0.95

            # 计算价格在布林带中的位置百分比
            if upper > lower:
                position_pct = (current_price - lower) / (upper - lower) * 100
            else:
                position_pct = 50  # 无法计算时默认中性

            # 生成周期级推荐
            if position_pct <= 20:
                recommendation = 'strong_buy'
                signal_strength = 'strong'
            elif position_pct <= 40:
                recommendation = 'buy'
                signal_strength = 'moderate'
            elif position_pct <= 60:
                recommendation = 'hold'
                signal_strength = 'weak'
            elif position_pct <= 80:
                recommendation = 'sell'
                signal_strength = 'moderate'
            else:
                recommendation = 'strong_sell'
                signal_strength = 'strong'

            return {
                'current_price': round(current_price, 2),
                'ma': round(ma_value, 2),
                'std': round(std_value, 2),
                'upper_bound': round(upper, 2),
                'lower_bound': round(lower, 2),
                'position_pct': round(position_pct, 2),  # 0=下轨, 50=中轨, 100=上轨
                'recommendation': recommendation,
                'signal_strength': signal_strength,
                'bandwidth': round((upper - lower) / ma_value * 100, 2) if ma_value > 0 else 0  # 布林带宽度
            }

        except Exception as e:
            self.logger.warning(f"周期 {period} 分析失败: {e}")
            return None

    def _analyze_volume(self, manager, symbol: str) -> Optional[Dict[str, Any]]:
        """
        成交量分析

        Args:
            manager: 数据源管理器
            symbol: 股票代码

        Returns:
            成交量分析结果
        """
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d')

            result = manager.get_klines(
                symbol=symbol,
                period='daily',
                start_date=start_date,
                end_date=end_date
            )

            if not result.success or result.data is None:
                return None

            df = pd.DataFrame(result.data) if isinstance(result.data, list) else result.data
            if df.empty or len(df) < 20:
                return None

            # 成交量指标
            df['volume_ma5'] = df['volume'].rolling(window=5).mean()
            df['volume_ma20'] = df['volume'].rolling(window=20).mean()

            latest = df.iloc[-1]
            current_volume = float(latest['volume']) if pd.notna(latest['volume']) else 0
            volume_ma5 = float(latest['volume_ma5']) if pd.notna(latest['volume_ma5']) else 0
            volume_ma20 = float(latest['volume_ma20']) if pd.notna(latest['volume_ma20']) else 0

            # 量价关系判断
            volume_ratio = current_volume / volume_ma20 if volume_ma20 > 0 else 1
            volume_trend = 'increasing' if volume_ma5 > volume_ma20 * 1.1 else \
                          'decreasing' if volume_ma5 < volume_ma20 * 0.9 else 'stable'

            # 成交量评分（放量=看涨信号）
            if volume_ratio >= 2.0:
                volume_score = 90
                volume_signal = 'strong_surge'
            elif volume_ratio >= 1.5:
                volume_score = 70
                volume_signal = 'surge'
            elif volume_ratio >= 1.2:
                volume_score = 60
                volume_signal = 'moderate_increase'
            elif volume_ratio >= 0.8:
                volume_score = 50
                volume_signal = 'normal'
            else:
                volume_score = 30
                volume_signal = 'shrink'

            return {
                'current_volume': int(current_volume),
                'volume_ma5': int(volume_ma5),
                'volume_ma20': int(volume_ma20),
                'volume_ratio': round(volume_ratio, 2),
                'volume_trend': volume_trend,
                'volume_signal': volume_signal,
                'volume_score': volume_score
            }

        except Exception as e:
            self.logger.warning(f"成交量分析失败: {e}")
            return None

    def _analyze_fundamental(self, manager, symbol: str) -> Optional[Dict[str, Any]]:
        """
        基本面分析（简化版）

        Args:
            manager: 数据源管理器
            symbol: 股票代码

        Returns:
            基本面分析结果
        """
        try:
            # 获取股票基本信息
            result = manager.get_stock_info(symbol)
            if not result.success or not result.data:
                return None

            info = result.data if isinstance(result.data, dict) else {}

            # 提取关键指标
            pe = info.get('pe_ratio') or info.get('pe')
            pb = info.get('pb_ratio') or info.get('pb')
            roe = info.get('roe')
            debt_ratio = info.get('debt_ratio')

            # 基本面评分
            score = 50  # 基础分
            factors = []

            if pe and 0 < pe < 15:
                score += 15
                factors.append('低PE估值')
            elif pe and 15 <= pe < 30:
                score += 5
                factors.append('合理PE估值')
            elif pe and pe >= 50:
                score -= 10
                factors.append('高PE估值')

            if pb and 0 < pb < 1.5:
                score += 10
                factors.append('低PB估值')

            if roe and roe > 15:
                score += 15
                factors.append('高ROE')
            elif roe and roe > 10:
                score += 8

            if debt_ratio and debt_ratio < 50:
                score += 10
                factors.append('低负债率')

            # 评级
            if score >= 80:
                rating = 'excellent'
            elif score >= 65:
                rating = 'good'
            elif score >= 50:
                rating = 'fair'
            else:
                rating = 'poor'

            return {
                'pe': round(pe, 2) if pe else None,
                'pb': round(pb, 2) if pb else None,
                'roe': round(roe, 2) if roe else None,
                'debt_ratio': round(debt_ratio, 2) if debt_ratio else None,
                'fundamental_score': score,
                'rating': rating,
                'positive_factors': factors
            }

        except Exception as e:
            self.logger.warning(f"基本面分析失败: {e}")
            return None

    def _generate_recommendation(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成综合推荐

        Args:
            result: 分析结果字典

        Returns:
            推荐字典
        """
        multi_period = result.get('multi_period_analysis', {})
        volume = result.get('volume_analysis', {})
        fundamental = result.get('fundamental_analysis', {})

        # 多周期投票
        votes = {'strong_buy': 0, 'buy': 0, 'hold': 0, 'sell': 0, 'strong_sell': 0}
        weights = {'daily': 0.5, 'weekly': 0.3, 'monthly': 0.2}

        for period, analysis in multi_period.items():
            rec = analysis.get('recommendation', 'hold')
            weight = weights.get(period, 0.5)
            votes[rec] += weight

        # 成交量加权（放量增强买入信号）
        if volume:
            volume_score = volume.get('volume_score', 50)
            if volume_score >= 70:
                votes['buy'] += 0.2
                votes['strong_buy'] += 0.1
            elif volume_score <= 40:
                votes['sell'] += 0.1

        # 基本面加权
        if fundamental:
            fund_score = fundamental.get('fundamental_score', 50)
            if fund_score >= 80:
                votes['buy'] += 0.15
                votes['strong_buy'] += 0.1
            elif fund_score <= 40:
                votes['sell'] += 0.1

        # 选出得票最多的推荐
        final_rec = max(votes, key=votes.get)

        # 置信度
        total_votes = sum(votes.values())
        confidence = votes[final_rec] / total_votes * 100 if total_votes > 0 else 0

        # 生成理由
        reasons = []
        if multi_period.get('daily', {}).get('position_pct'):
            pos_pct = multi_period['daily']['position_pct']
            if pos_pct <= 20:
                reasons.append(f'日线处于超卖区域（{pos_pct:.0f}%分位）')
            elif pos_pct >= 80:
                reasons.append(f'日线处于超买区域（{pos_pct:.0f}%分位）')

        if volume and volume.get('volume_signal') in ['strong_surge', 'surge']:
            reasons.append(f"成交量放大（{volume.get('volume_ratio', 1):.1f}倍）")

        if fundamental and fundamental.get('rating') in ['excellent', 'good']:
            reasons.append(f"基本面{fundamental['rating']}（{', '.join(fundamental.get('positive_factors', [])[:2])}）")

        return {
            'action': final_rec,
            'confidence': round(confidence, 2),
            'reasons': reasons,
            'vote_details': votes
        }

    def _calculate_composite_score(self, result: Dict[str, Any]) -> float:
        """
        计算综合评分（0-100）

        Args:
            result: 分析结果字典

        Returns:
            综合评分
        """
        score = 50  # 基础分

        # 技术面评分（40%）
        multi_period = result.get('multi_period_analysis', {})
        if 'daily' in multi_period:
            pos_pct = multi_period['daily'].get('position_pct', 50)
            # 位置越低分数越高（买入机会）
            tech_score = 100 - pos_pct
            score += (tech_score - 50) * 0.4

        # 成交量评分（30%）
        volume = result.get('volume_analysis', {})
        if volume:
            vol_score = volume.get('volume_score', 50)
            score += (vol_score - 50) * 0.3

        # 基本面评分（30%）
        fundamental = result.get('fundamental_analysis', {})
        if fundamental:
            fund_score = fundamental.get('fundamental_score', 50)
            score += (fund_score - 50) * 0.3

        return round(max(0, min(100, score)), 2)

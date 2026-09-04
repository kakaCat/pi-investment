"""
市场情绪服务

提供资金流向、融资融券等市场情绪相关功能
"""
import structlog
from typing import Dict, Optional

logger = structlog.get_logger(__name__)


class SentimentService:
    """市场情绪服务"""

    def __init__(self, fund_flow_source):
        """
        初始化情绪服务

        Args:
            fund_flow_source: 资金流向数据源
        """
        self.fund_flow_source = fund_flow_source

    def get_stock_fund_flow(self, symbol: str, days: int = 5) -> Dict:
        """
        获取个股资金流向并生成分析

        Args:
            symbol: 股票代码
            days: 查询天数

        Returns:
            资金流向数据 + 分析结果
        """
        try:
            # 获取原始数据
            flow_data = self.fund_flow_source.get_stock_fund_flow(symbol, days)

            # 生成分析
            analysis = self._analyze_fund_flow(flow_data)

            # 生成信号
            signals = self._generate_signals(flow_data, analysis)

            return {
                **flow_data,
                'records': flow_data.get('data', []),  # 添加 records 字段供前端使用
                'analysis': analysis,
                'signals': signals,
            }

        except Exception as e:
            logger.error(f"获取 {symbol} 资金流向失败: {e}", exc_info=True)
            return {'error': str(e)}

    def _analyze_fund_flow(self, flow_data: Dict) -> Dict:
        """
        分析资金流向数据

        分析维度：
        1. 主力行为：主力是否持续流入/流出
        2. 资金结构：大单、中单、小单占比
        3. 流向强度：净流入金额和比例
        4. 趋势稳定性：流向方向的连续性
        """
        if 'error' in flow_data or not flow_data.get('data'):
            return {'error': 'No data to analyze'}

        data = flow_data['data']
        summary = flow_data.get('summary', {})

        # 1. 主力行为分析
        total_main_inflow = summary.get('total_main_net_inflow', 0)
        consecutive_days = summary.get('consecutive_inflow_days', 0)

        if consecutive_days >= 3 and total_main_inflow > 0:
            main_behavior = '主力持续流入，看多情绪浓厚'
            main_strength = 'strong'
        elif consecutive_days >= 1 and total_main_inflow > 0:
            main_behavior = '主力净流入，资金关注度提升'
            main_strength = 'moderate'
        elif total_main_inflow < -10000:  # 流出超过1亿
            main_behavior = '主力大幅流出，谨慎看待'
            main_strength = 'weak'
        elif total_main_inflow < 0:
            main_behavior = '主力净流出，资金观望'
            main_strength = 'negative'
        else:
            main_behavior = '主力资金中性，未见明显方向'
            main_strength = 'neutral'

        # 2. 资金结构分析
        recent_data = data[0] if data else {}
        # 2026-09-01 修复：缓存数据部分档位为 None（sina 源只落 main/small），
        # None > 0 会 TypeError。统一 None→0 再做比较。
        def _rate(key):
            v = recent_data.get(key, 0)
            return v if isinstance(v, (int, float)) else 0
        large_rate = _rate('large_net_inflow_rate')
        big_rate = _rate('big_net_inflow_rate')
        medium_rate = _rate('medium_net_inflow_rate')
        small_rate = _rate('small_net_inflow_rate')

        # 判断资金结构
        if large_rate > 0 and big_rate > 0:
            structure_desc = '超大单和大单同步流入，机构主导'
            structure_type = 'institutional'
        elif small_rate > 0 and medium_rate > 0:
            structure_desc = '中小单流入为主，散户参与'
            structure_type = 'retail'
        elif large_rate > 0 and small_rate < 0:
            structure_desc = '机构吸筹，散户离场'
            structure_type = 'accumulation'
        elif large_rate < 0 and small_rate > 0:
            structure_desc = '机构出货，散户接盘'
            structure_type = 'distribution'
        else:
            structure_desc = '资金流向分散，方向不明'
            structure_type = 'mixed'

        # 3. 流向强度分析
        avg_rate = summary.get('avg_main_net_inflow_rate', 0)

        if abs(avg_rate) >= 10:
            intensity = 'very_high'
            intensity_desc = '资金流向强度极高'
        elif abs(avg_rate) >= 5:
            intensity = 'high'
            intensity_desc = '资金流向强度较高'
        elif abs(avg_rate) >= 2:
            intensity = 'moderate'
            intensity_desc = '资金流向强度中等'
        else:
            intensity = 'low'
            intensity_desc = '资金流向强度较低'

        # 4. 趋势稳定性
        trend = summary.get('trend', 'neutral')
        if consecutive_days >= 3:
            stability = 'stable'
            stability_desc = f'连续{consecutive_days}天流入，趋势稳定'
        elif consecutive_days >= 1:
            stability = 'emerging'
            stability_desc = f'连续{consecutive_days}天流入，趋势初现'
        else:
            stability = 'unstable'
            stability_desc = '流向反复，趋势不稳'

        return {
            'main_behavior': {
                'description': main_behavior,
                'strength': main_strength,
                'total_inflow': total_main_inflow,
                'consecutive_days': consecutive_days,
            },
            'capital_structure': {
                'description': structure_desc,
                'type': structure_type,
                'large_rate': large_rate,
                'big_rate': big_rate,
                'medium_rate': medium_rate,
                'small_rate': small_rate,
            },
            'flow_intensity': {
                'description': intensity_desc,
                'level': intensity,
                'avg_rate': avg_rate,
            },
            'trend_stability': {
                'description': stability_desc,
                'level': stability,
            }
        }

    def _generate_signals(self, flow_data: Dict, analysis: Dict) -> list:
        """生成交易信号"""
        if 'error' in flow_data or 'error' in analysis:
            return []

        signals = []
        summary = flow_data.get('summary', {})
        main_behavior = analysis.get('main_behavior', {})
        structure = analysis.get('capital_structure', {})
        intensity = analysis.get('flow_intensity', {})

        # 强烈流入信号
        if main_behavior.get('strength') == 'strong' and intensity.get('level') in ['high', 'very_high']:
            signals.append({
                'type': 'strong_inflow',
                'message': '主力持续大幅流入，资金看多',
                'priority': 'high',
                'action': 'buy'
            })

        # 机构吸筹信号
        if structure.get('type') == 'accumulation' and summary.get('total_main_net_inflow', 0) > 5000:
            signals.append({
                'type': 'accumulation',
                'message': '机构吸筹，散户离场，低位建仓机会',
                'priority': 'high',
                'action': 'buy'
            })

        # 机构出货信号
        if structure.get('type') == 'distribution' and main_behavior.get('strength') == 'weak':
            signals.append({
                'type': 'distribution',
                'message': '机构出货，散户接盘，注意风险',
                'priority': 'high',
                'action': 'sell'
            })

        # 资金流出预警
        if main_behavior.get('strength') in ['weak', 'negative'] and summary.get('total_main_net_inflow', 0) < -10000:
            signals.append({
                'type': 'outflow_warning',
                'message': '主力大幅流出，建议回避或减仓',
                'priority': 'medium',
                'action': 'sell'
            })

        # 观望信号
        if main_behavior.get('strength') == 'neutral' and intensity.get('level') == 'low':
            signals.append({
                'type': 'neutral',
                'message': '资金流向中性，建议观望',
                'priority': 'low',
                'action': 'hold'
            })

        return signals

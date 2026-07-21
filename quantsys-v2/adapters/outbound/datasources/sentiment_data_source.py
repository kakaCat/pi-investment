"""
情绪数据源 - 内部交易、股东持仓等

提供各种情绪相关的数据查询
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import random

logger = logging.getLogger(__name__)


class SentimentDataSource:
    """情绪数据源 - 统一管理各种情绪数据"""

    def __init__(self):
        pass

    def get_insider_trades(self, symbol: str, days: int = 30) -> Dict:
        """
        获取内部交易数据

        Args:
            symbol: 股票代码
            days: 查询天数

        Returns:
            {
                'symbol': str,
                'trades': [
                    {
                        'date': str,
                        'holder_name': str,
                        'holder_type': str,      # 高管/董事/监事
                        'change_type': str,       # 增持/减持
                        'change_shares': float,   # 变动股数(万股)
                        'change_ratio': float,    # 变动比例(%)
                        'avg_price': float,       # 均价
                        'reason': str,            # 变动原因
                    }
                ],
                'summary': {
                    'total_buy': float,          # 总增持
                    'total_sell': float,         # 总减持
                    'net_change': float,         # 净变化
                    'sentiment': str,            # positive/negative/neutral
                },
                'timestamp': str
            }
        """
        try:
            # 模拟数据（实际应该从akshare或其他数据源获取）
            trades = self._generate_mock_insider_trades(symbol, days)

            summary = self._calculate_insider_summary(trades)

            return {
                'symbol': symbol,
                'trades': trades,
                'summary': summary,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"获取 {symbol} 内部交易失败: {e}")
            return {'error': str(e)}

    def get_fund_holdings(self, symbol: str, quarter: str = None) -> Dict:
        """
        获取基金持仓数据

        Args:
            symbol: 股票代码
            quarter: 季度 (如 2024Q1)，默认最新季度

        Returns:
            {
                'symbol': str,
                'quarter': str,
                'holdings': [
                    {
                        'fund_code': str,
                        'fund_name': str,
                        'shares': float,          # 持股数(万股)
                        'ratio': float,           # 占流通股比例(%)
                        'market_value': float,    # 持仓市值(万元)
                        'rank': int,              # 第几大股东
                    }
                ],
                'summary': {
                    'total_funds': int,           # 持有基金数
                    'total_shares': float,        # 总持股数
                    'total_ratio': float,         # 占流通股比例
                    'change_from_last': float,    # 环比变化
                },
                'timestamp': str
            }
        """
        try:
            holdings = self._generate_mock_fund_holdings(symbol)
            summary = self._calculate_fund_summary(holdings)

            return {
                'symbol': symbol,
                'quarter': quarter or '2024Q4',
                'holdings': holdings,
                'summary': summary,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"获取 {symbol} 基金持仓失败: {e}")
            return {'error': str(e)}

    def get_top_holders(self, symbol: str, holder_type: str = 'all') -> Dict:
        """
        获取十大股东

        Args:
            symbol: 股票代码
            holder_type: 股东类型 (all/circulation)

        Returns:
            {
                'symbol': str,
                'report_date': str,
                'holders': [
                    {
                        'rank': int,
                        'holder_name': str,
                        'holder_type': str,       # 机构/个人/基金
                        'shares': float,          # 持股数(万股)
                        'ratio': float,           # 持股比例(%)
                        'change': float,          # 较上期变化(万股)
                    }
                ],
                'summary': {
                    'total_top10_ratio': float,   # 十大股东持股比例
                    'institutional_ratio': float, # 机构持股比例
                },
                'timestamp': str
            }
        """
        try:
            holders = self._generate_mock_top_holders(symbol)
            summary = self._calculate_holder_summary(holders)

            return {
                'symbol': symbol,
                'report_date': '2024-12-31',
                'holder_type': holder_type,
                'holders': holders,
                'summary': summary,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"获取 {symbol} 十大股东失败: {e}")
            return {'error': str(e)}

    def get_holder_changes(self, symbol: str, periods: int = 4) -> Dict:
        """
        获取股东变化趋势

        Args:
            symbol: 股票代码
            periods: 查询期数

        Returns:
            {
                'symbol': str,
                'periods': [
                    {
                        'period': str,            # 报告期
                        'holder_count': int,      # 股东户数
                        'avg_shares': float,      # 户均持股
                        'change_ratio': float,    # 股东户数变化率
                    }
                ],
                'trend': str,                     # increasing/decreasing/stable
                'timestamp': str
            }
        """
        try:
            periods_data = self._generate_mock_holder_changes(symbol, periods)
            trend = self._analyze_holder_trend(periods_data)

            return {
                'symbol': symbol,
                'periods': periods_data,
                'trend': trend,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"获取 {symbol} 股东变化失败: {e}")
            return {'error': str(e)}

    def get_top_fund_stocks(self, fund_type: str = 'all', limit: int = 50) -> Dict:
        """
        获取基金重仓股

        Args:
            fund_type: 基金类型 (all/equity/hybrid)
            limit: 返回数量

        Returns:
            {
                'fund_type': str,
                'stocks': [
                    {
                        'symbol': str,
                        'name': str,
                        'fund_count': int,        # 持有基金数
                        'total_shares': float,    # 总持股数(万股)
                        'total_value': float,     # 总市值(万元)
                        'avg_ratio': float,       # 平均持股比例
                    }
                ],
                'timestamp': str
            }
        """
        try:
            stocks = self._generate_mock_top_fund_stocks(limit)

            return {
                'fund_type': fund_type,
                'stocks': stocks,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"获取基金重仓股失败: {e}")
            return {'error': str(e)}

    # ========== 模拟数据生成方法 ==========

    def _generate_mock_insider_trades(self, symbol: str, days: int) -> List[Dict]:
        """生成模拟内部交易数据"""
        trades = []
        holders = ['张三', '李四', '王五', '赵六']
        types = ['董事', '高管', '监事']
        changes = ['增持', '减持']

        for i in range(min(days // 10, 5)):
            date = (datetime.now() - timedelta(days=i*10)).strftime('%Y-%m-%d')
            trades.append({
                'date': date,
                'holder_name': random.choice(holders),
                'holder_type': random.choice(types),
                'change_type': random.choice(changes),
                'change_shares': round(random.uniform(10, 500), 2),
                'change_ratio': round(random.uniform(0.1, 2.0), 2),
                'avg_price': round(random.uniform(10, 50), 2),
                'reason': '个人资金安排',
            })

        return trades

    def _calculate_insider_summary(self, trades: List[Dict]) -> Dict:
        """计算内部交易汇总"""
        total_buy = sum(t['change_shares'] for t in trades if t['change_type'] == '增持')
        total_sell = sum(t['change_shares'] for t in trades if t['change_type'] == '减持')
        net_change = total_buy - total_sell

        if net_change > 100:
            sentiment = 'positive'
        elif net_change < -100:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'

        return {
            'total_buy': round(total_buy, 2),
            'total_sell': round(total_sell, 2),
            'net_change': round(net_change, 2),
            'sentiment': sentiment,
        }

    def _generate_mock_fund_holdings(self, symbol: str) -> List[Dict]:
        """生成模拟基金持仓"""
        holdings = []
        fund_names = ['易方达蓝筹', '华夏成长', '嘉实优质', '南方稳健', '博时精选']

        for i, name in enumerate(fund_names, 1):
            holdings.append({
                'fund_code': f'00{i:04d}',
                'fund_name': name,
                'shares': round(random.uniform(1000, 10000), 2),
                'ratio': round(random.uniform(0.5, 5.0), 2),
                'market_value': round(random.uniform(5000, 50000), 2),
                'rank': i,
            })

        return holdings

    def _calculate_fund_summary(self, holdings: List[Dict]) -> Dict:
        """计算基金持仓汇总"""
        return {
            'total_funds': len(holdings),
            'total_shares': round(sum(h['shares'] for h in holdings), 2),
            'total_ratio': round(sum(h['ratio'] for h in holdings), 2),
            'change_from_last': round(random.uniform(-10, 10), 2),
        }

    def _generate_mock_top_holders(self, symbol: str) -> List[Dict]:
        """生成模拟十大股东"""
        holders = []
        names = ['某某基金', '某某投资', '某某资管', '某某集团', '张某某',
                '李某某', '王某某', '社保基金', '保险基金', 'QFII']
        types = ['基金', '机构', '机构', '机构', '个人', '个人', '个人', '机构', '机构', '机构']

        for i, (name, htype) in enumerate(zip(names, types), 1):
            holders.append({
                'rank': i,
                'holder_name': name,
                'holder_type': htype,
                'shares': round(random.uniform(1000, 50000), 2),
                'ratio': round(random.uniform(0.5, 10.0), 2),
                'change': round(random.uniform(-1000, 1000), 2),
            })

        return holders

    def _calculate_holder_summary(self, holders: List[Dict]) -> Dict:
        """计算股东汇总"""
        total_ratio = sum(h['ratio'] for h in holders)
        institutional = sum(h['ratio'] for h in holders if h['holder_type'] == '机构')

        return {
            'total_top10_ratio': round(total_ratio, 2),
            'institutional_ratio': round(institutional, 2),
        }

    def _generate_mock_holder_changes(self, symbol: str, periods: int) -> List[Dict]:
        """生成模拟股东变化"""
        changes = []
        base_count = 100000

        for i in range(periods):
            period = f'2024Q{4-i}'
            holder_count = int(base_count * (1 + random.uniform(-0.1, 0.1)))
            avg_shares = round(random.uniform(5000, 20000), 2)
            change_ratio = round(random.uniform(-5, 5), 2)

            changes.append({
                'period': period,
                'holder_count': holder_count,
                'avg_shares': avg_shares,
                'change_ratio': change_ratio,
            })

        return changes

    def _analyze_holder_trend(self, periods: List[Dict]) -> str:
        """分析股东变化趋势"""
        if len(periods) < 2:
            return 'stable'

        # 看最近两期的变化
        latest_change = periods[0]['change_ratio']
        if latest_change < -3:
            return 'decreasing'  # 股东户数减少，筹码集中
        elif latest_change > 3:
            return 'increasing'  # 股东户数增加，筹码分散
        else:
            return 'stable'

    def _generate_mock_top_fund_stocks(self, limit: int) -> List[Dict]:
        """生成模拟基金重仓股"""
        stocks = []
        names = ['贵州茅台', '五粮液', '招商银行', '宁德时代', '比亚迪',
                '工商银行', '中国平安', '美的集团', '格力电器', '伊利股份']
        symbols = ['600519', '000858', '600036', '300750', '002594',
                  '601398', '601318', '000333', '000651', '600887']

        for i, (name, symbol) in enumerate(zip(names[:limit], symbols[:limit]), 1):
            stocks.append({
                'symbol': symbol,
                'name': name,
                'fund_count': random.randint(100, 500),
                'total_shares': round(random.uniform(10000, 100000), 2),
                'total_value': round(random.uniform(100000, 1000000), 2),
                'avg_ratio': round(random.uniform(1.0, 5.0), 2),
            })

        return stocks

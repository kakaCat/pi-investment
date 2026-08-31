"""
股票筛选服务

支持多条件筛选股票
"""
import structlog
from typing import Dict, List, Optional

logger = structlog.get_logger(__name__)


class StockScreeningService:
    """股票筛选服务"""

    def __init__(self, stock_repo=None, scoring_service=None):
        """
        初始化筛选服务

        Args:
            stock_repo: 股票数据仓库（可选，默认通过 ServiceFactory 获取）
            scoring_service: 评分服务实例
        """
        if stock_repo is None:
            from infrastructure.services.service_factory import ServiceFactory
            stock_repo = ServiceFactory.get_stock_repository()
        self.stock_repo = stock_repo
        self.scoring_service = scoring_service

    def screen_stocks(self, criteria: Dict) -> Dict:
        """
        根据条件筛选股票

        Args:
            criteria: {
                'min_score': float,          # 最低评分
                'max_pe': float,             # 最高PE
                'min_roe': float,            # 最低ROE
                'max_debt_ratio': float,     # 最高负债率
                'min_market_cap': float,     # 最低市值(亿)
                'industries': [str],         # 行业列表
                'exclude_st': bool,          # 排除ST
                'min_price': float,          # 最低价格
                'max_price': float,          # 最高价格
                'sort_by': str,              # 排序字段
                'limit': int,                # 返回数量
            }

        Returns:
            {
                'total': int,
                'matched': int,
                'stocks': [
                    {
                        'symbol': str,
                        'name': str,
                        'score': float,
                        'pe': float,
                        'roe': float,
                        'market_cap': float,
                        'price': float,
                        'reason': str,
                    }
                ],
                'criteria': dict,
                'timestamp': str
            }
        """
        try:
            from datetime import datetime

            # 1. 获取所有股票
            all_stocks = self.stock_repo.get_all(market='A')
            total = len(all_stocks) if all_stocks else 0

            logger.info(f"开始筛选，总股票数: {total}")

            # 2. 应用筛选条件
            matched_stocks = []

            for stock in all_stocks:
                try:
                    # 基本条件筛选
                    if not self._match_basic_criteria(stock, criteria):
                        continue

                    # 获取评分（如果需要）
                    score = None
                    if criteria.get('min_score'):
                        score_result = self.scoring_service.calculate_comprehensive_score(stock['symbol'])
                        if 'error' in score_result:
                            continue
                        score = score_result['total_score']
                        if score < criteria['min_score']:
                            continue

                    # 构建结果
                    result = {
                        'symbol': stock['symbol'],
                        'name': stock['name'],
                        'market': stock.get('market', 'A'),
                        'industry': stock.get('industry', ''),
                        'score': score if score is not None else 0,
                        'pe': float(stock.get('pe', 0) or 0),
                        'pb': float(stock.get('pb', 0) or 0),
                        'roe': float(stock.get('roe', 0) or 0),
                        'debt_ratio': float(stock.get('debt_ratio', 0) or 0),
                        'market_cap': float(stock.get('market_cap', 0) or 0),
                        'reason': self._generate_reason(stock, score, criteria),
                    }

                    matched_stocks.append(result)

                except Exception as e:
                    logger.warning(f"筛选 {stock.get('symbol')} 失败: {e}")
                    continue

            # 3. 排序
            sort_by = criteria.get('sort_by', 'score')
            reverse = True  # 默认降序

            if sort_by in ['score', 'roe', 'market_cap']:
                matched_stocks.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)
            elif sort_by == 'pe':
                # PE越低越好，升序
                matched_stocks.sort(key=lambda x: x.get('pe', 999), reverse=False)

            # 4. 限制返回数量
            limit = criteria.get('limit', 50)
            matched_stocks = matched_stocks[:limit]

            logger.info(f"筛选完成，匹配 {len(matched_stocks)} 只股票")

            return {
                'total': total,
                'matched': len(matched_stocks),
                'stocks': matched_stocks,
                'criteria': criteria,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"股票筛选失败: {e}", exc_info=True)
            return {'error': str(e)}

    def _match_basic_criteria(self, stock: Dict, criteria: Dict) -> bool:
        """
        检查股票是否匹配基本条件

        Returns:
            True if matches, False otherwise
        """
        # 排除ST
        if criteria.get('exclude_st', True):
            if stock.get('is_st', False):
                return False

        # PE范围
        if criteria.get('max_pe'):
            pe = float(stock.get('pe', 0) or 0)
            if pe <= 0 or pe > criteria['max_pe']:
                return False

        # ROE范围
        if criteria.get('min_roe'):
            roe = float(stock.get('roe', 0) or 0)
            if roe < criteria['min_roe']:
                return False

        # 负债率
        if criteria.get('max_debt_ratio'):
            debt_ratio = float(stock.get('debt_ratio', 0) or 0)
            if debt_ratio > criteria['max_debt_ratio']:
                return False

        # 市值范围
        if criteria.get('min_market_cap'):
            market_cap = float(stock.get('market_cap', 0) or 0)
            if market_cap < criteria['min_market_cap']:
                return False

        # 行业
        if criteria.get('industries'):
            industry = stock.get('industry', '')
            if not any(ind in industry for ind in criteria['industries']):
                return False

        # 价格范围（需要获取最新价格）
        # 这里简化处理，实际应该查询最新K线
        # if criteria.get('min_price') or criteria.get('max_price'):
        #     # TODO: 获取最新价格
        #     pass

        return True

    def _generate_reason(self, stock: Dict, score: Optional[float], criteria: Dict) -> str:
        """生成匹配原因"""
        reasons = []

        if score and score >= 70:
            reasons.append(f"高评分({score:.1f})")

        pe = float(stock.get('pe', 0) or 0)
        if 0 < pe < 15:
            reasons.append(f"低PE({pe:.1f})")

        roe = float(stock.get('roe', 0) or 0)
        if roe > 0.15:
            reasons.append(f"高ROE({roe*100:.1f}%)")

        debt_ratio = float(stock.get('debt_ratio', 0) or 0)
        if debt_ratio < 0.3:
            reasons.append("低负债")

        if not reasons:
            reasons.append("符合筛选条件")

        return ", ".join(reasons)

    def get_preset_screens(self) -> Dict:
        """
        获取预设筛选条件

        Returns:
            {
                'presets': [
                    {
                        'name': str,
                        'description': str,
                        'criteria': dict
                    }
                ]
            }
        """
        presets = [
            {
                'name': 'value_stocks',
                'description': '价值股：低PE + 高ROE + 低负债',
                'criteria': {
                    'max_pe': 20,
                    'min_roe': 0.15,
                    'max_debt_ratio': 0.5,
                    'exclude_st': True,
                    'sort_by': 'roe',
                    'limit': 50,
                }
            },
            {
                'name': 'growth_stocks',
                'description': '成长股：高评分 + ROE增长',
                'criteria': {
                    'min_score': 70,
                    'min_roe': 0.10,
                    'exclude_st': True,
                    'sort_by': 'score',
                    'limit': 50,
                }
            },
            {
                'name': 'large_cap',
                'description': '大盘股：市值>500亿',
                'criteria': {
                    'min_market_cap': 500,
                    'exclude_st': True,
                    'sort_by': 'market_cap',
                    'limit': 50,
                }
            },
            {
                'name': 'low_valuation',
                'description': '低估值：PE<15 + PB<2',
                'criteria': {
                    'max_pe': 15,
                    'min_roe': 0.08,
                    'exclude_st': True,
                    'sort_by': 'pe',
                    'limit': 50,
                }
            },
            {
                'name': 'high_quality',
                'description': '高质量：高ROE + 低负债 + 高评分',
                'criteria': {
                    'min_score': 70,
                    'min_roe': 0.20,
                    'max_debt_ratio': 0.3,
                    'exclude_st': True,
                    'sort_by': 'score',
                    'limit': 30,
                }
            },
        ]

        return {'presets': presets}

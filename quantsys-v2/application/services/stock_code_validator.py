"""
股票代码验证服务 - 在查询K线前验证股票代码有效性
"""
import structlog
from typing import Optional, Dict, List
from datetime import datetime, timedelta

from domain.ports import IKlineRepository

logger = structlog.get_logger(__name__)

__all__ = ['StockCodeValidator']


class StockCodeValidator:
    """股票代码验证器

    功能：
    1. 验证股票代码是否存在
    2. 检查该股票是否有历史数据
    3. 提供模糊匹配建议
    4. 缓存验证结果
    """

    def __init__(self):
        self.kline_repo = IKlineRepository()
        self._cache: Dict[str, Dict] = {}
        self._cache_ttl = 3600  # 缓存1小时

    def validate(self, symbol: str) -> Dict:
        """
        验证股票代码

        Args:
            symbol: 股票代码（如 600519 或 000001）

        Returns:
            {
                'valid': bool,              # 是否有效
                'exists': bool,             # 数据库中是否存在
                'has_recent_data': bool,    # 是否有最近的数据
                'data_summary': {           # 数据概况
                    'first_date': str,
                    'last_date': str,
                    'total_records': int,
                    'days_since_update': int
                },
                'suggestions': List[str],   # 建议（如果无效）
                'similar_codes': List[str]  # 相似的股票代码
            }
        """
        # 检查缓存
        if symbol in self._cache:
            cached = self._cache[symbol]
            if datetime.now().timestamp() - cached['timestamp'] < self._cache_ttl:
                logger.debug(f"使用缓存的验证结果: {symbol}")
                return cached['result']

        # 规范化股票代码
        normalized_symbol = self._normalize_symbol(symbol)

        try:
            # 使用轻量聚合查询，避免加载全部历史 K 线
            total_records = self.kline_repo.count_daily_klines(normalized_symbol)

            if total_records == 0:
                result = self._build_invalid_result(normalized_symbol)
            else:
                date_range = self.kline_repo.get_date_range(normalized_symbol)
                if date_range is None:
                    result = self._build_invalid_result(normalized_symbol)
                else:
                    result = self._build_valid_result_from_range(
                        normalized_symbol, total_records, date_range
                    )

            # 缓存结果
            self._cache[symbol] = {
                'result': result,
                'timestamp': datetime.now().timestamp()
            }

            return result

        except Exception as e:
            logger.error(f"验证股票代码失败: {symbol}", error=str(e))
            return {
                'valid': False,
                'exists': False,
                'error': f'验证失败: {str(e)}',
                'suggestions': ['请稍后重试或联系管理员']
            }

    def _normalize_symbol(self, symbol: str) -> str:
        """规范化股票代码"""
        # 去除空格和特殊字符
        cleaned = ''.join(c for c in symbol if c.isdigit())

        # 补齐到6位（如果不足）
        if len(cleaned) < 6:
            cleaned = cleaned.zfill(6)

        return cleaned

    def _build_valid_result_from_range(
        self, symbol: str, total_records: int, date_range: tuple
    ) -> Dict:
        """基于日期范围构建有效股票的验证结果（轻量版）"""
        first_date, last_date = date_range

        # 统一转换为 ISO 字符串
        first_date_str = first_date.isoformat() if hasattr(first_date, 'isoformat') else str(first_date)
        last_date_str = last_date.isoformat() if hasattr(last_date, 'isoformat') else str(last_date)

        # 计算数据新鲜度
        if isinstance(last_date_str, str):
            last_dt = datetime.strptime(last_date_str, '%Y-%m-%d')
        else:
            last_dt = last_date
        days_since_update = (datetime.now() - last_dt).days

        # 判断是否有最近数据（30天内）
        has_recent_data = days_since_update <= 30

        return {
            'valid': True,
            'exists': True,
            'has_recent_data': has_recent_data,
            'data_summary': {
                'first_date': first_date_str,
                'last_date': last_date_str,
                'total_records': total_records,
                'days_since_update': days_since_update
            },
            'suggestions': [] if has_recent_data else [
                f'该股票数据已 {days_since_update} 天未更新，可能已退市或停牌'
            ],
            'similar_codes': []
        }

    def _build_invalid_result(self, symbol: str) -> Dict:
        """构建无效股票的验证结果"""
        suggestions = [
            '该股票代码不存在或尚未录入数据',
            '请检查代码是否正确：',
            '  • 上海股票：6xxxxx（如 600519 贵州茅台）',
            '  • 深圳股票：0xxxxx 或 3xxxxx（如 000001 平安银行）',
        ]

        # 尝试提供相似代码建议
        similar_codes = self._find_similar_codes(symbol)
        if similar_codes:
            suggestions.append(f'您是否要找: {", ".join(similar_codes)}')

        return {
            'valid': False,
            'exists': False,
            'has_recent_data': False,
            'suggestions': suggestions,
            'similar_codes': similar_codes
        }

    def _find_similar_codes(self, symbol: str) -> List[str]:
        """查找相似的股票代码（简化实现）"""
        # TODO: 可以基于编辑距离、拼音等算法实现更智能的匹配
        # 这里暂时返回空列表，等待后续实现
        return []

    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()
        logger.info("股票代码验证缓存已清除")

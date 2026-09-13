"""
行业数据适配器（生产环境）

从数据库获取行业分类和因子数据。
"""

import structlog
from typing import Dict, List, Optional
from infrastructure.persistence.database.engine import db_cursor

from domain.scoring.ports import IndustryDataPort

logger = structlog.get_logger(__name__)

# 可按因子取值的列白名单（列名**不能**用绑定参数，只能用白名单校验）。
# 2026-09-13（w-32314d00，REQ-24e15d t1）：原实现把 factor_name 与 symbols 直接拼进 SQL 文本
#（f"SELECT {factor_name} ... WHERE symbol IN ('{symbol_list}')"）——列名与取值双重注入面。
_ALLOWED_FACTOR_COLUMNS = frozenset({
    'pe', 'pb', 'roe', 'revenue_growth', 'net_profit_growth', 'gross_margin', 'debt_ratio',
    'market_cap', 'total_mv', 'circulating_mv', 'avg_turnover_rate', 'avg_volume', 'avg_amount',
})


def _validated_factor_column(factor_name: str) -> str:
    """校验因子列名在白名单内；不在则显式报错（不猜、不放行）。"""
    name = str(factor_name or '').strip()
    if name not in _ALLOWED_FACTOR_COLUMNS:
        raise ValueError(f'不支持的因子列: {factor_name!r}（白名单：{sorted(_ALLOWED_FACTOR_COLUMNS)}）')
    return name


class IndustryDataAdapter(IndustryDataPort):
    """
    行业数据适配器（生产环境）
    
    从数据库获取：
    1. 股票行业分类
    2. 行业内因子值
    """
    
    def __init__(self):
        """初始化行业数据适配器"""
        self._sector_cache: Dict[str, str] = {}
        self._factor_cache: Dict[str, Dict[str, List[float]]] = {}
    
    def get_sector(self, symbol: str) -> str:
        """
        获取股票所属行业
        
        Args:
            symbol: 股票代码
            
        Returns:
            str: 行业名称
        """
        # 检查缓存
        if symbol in self._sector_cache:
            return self._sector_cache[symbol]
        
        # 从数据库查询
        try:
            with db_cursor() as cursor:
                cursor.execute(
                    "SELECT sector FROM quant.stocks WHERE symbol = %s",
                    (symbol,)
                )
                result = cursor.fetchone()
                sector = result['sector'] if result else '未知'
                self._sector_cache[symbol] = sector
                return sector
        except Exception as e:
            logger.warning(f"获取 {symbol} 行业失败: {e}")
            return '未知'
    
    def get_sector_stocks(self, sector: str) -> List[str]:
        """
        获取行业内的所有股票
        
        Args:
            sector: 行业名称
            
        Returns:
            List[str]: 股票代码列表
        """
        try:
            with db_cursor() as cursor:
                cursor.execute(
                    "SELECT symbol FROM quant.stocks WHERE sector = %s",
                    (sector,)
                )
                results = cursor.fetchall()
                return [row['symbol'] for row in results]
        except Exception as e:
            logger.warning(f"获取 {sector} 行业股票列表失败: {e}")
            return []
    
    def get_sector_factor_values(
        self, 
        sector: str, 
        factor_name: str,
        symbols: Optional[List[str]] = None
    ) -> List[float]:
        """
        获取行业内某因子的所有值
        
        Args:
            sector: 行业名称
            factor_name: 因子名称
            symbols: 股票代码列表（可选）
            
        Returns:
            List[float]: 因子值列表
        """
        # 检查缓存
        cache_key = f"{sector}:{factor_name}"
        if cache_key in self._factor_cache:
            return self._factor_cache[cache_key]
        
        # 从数据库查询
        try:
            with db_cursor() as cursor:
                # 构建查询（使用 stocks 表，它有 pe, roe, revenue_growth 字段）
                # 列名经白名单校验后才允许进 SQL 文本；取值一律走绑定参数。
                column = _validated_factor_column(factor_name)
                if symbols:
                    # 查询指定股票：= ANY(%s) 由 psycopg2 适配 Python list → text[]，
                    # 不再把代码拼进 SQL 文本（原写法 symbol IN ('{symbol_list}') 是注入面）。
                    cursor.execute(
                        f"SELECT {column} FROM quant.stocks "
                        f"WHERE symbol = ANY(%s) AND {column} IS NOT NULL",
                        (list(symbols),)
                    )
                else:
                    # 查询整个行业
                    cursor.execute(
                        f"SELECT {column} FROM quant.stocks "
                        f"WHERE sector = %s AND {column} IS NOT NULL",
                        (sector,)
                    )
                
                results = cursor.fetchall()
                values = [float(row[factor_name]) for row in results if row[factor_name] is not None]
                
                # 缓存结果
                self._factor_cache[cache_key] = values
                return values
        except Exception as e:
            logger.warning(f"获取 {sector} 行业 {factor_name} 因子值失败: {e}")
            return []
    
    def clear_cache(self):
        """清除缓存"""
        self._sector_cache.clear()
        self._factor_cache.clear()

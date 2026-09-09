"""
行业数据适配器（生产环境）

从数据库获取行业分类和因子数据。
"""

from typing import Dict, List, Optional
from infrastructure.persistence.database.engine import db_cursor

from domain.scoring.ports import IndustryDataPort


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
            print(f"获取 {symbol} 行业失败: {e}")
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
            print(f"获取 {sector} 行业股票列表失败: {e}")
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
                if symbols:
                    # 查询指定股票
                    symbol_list = "', '".join(symbols)
                    cursor.execute(
                        f"SELECT {factor_name} FROM quant.stocks WHERE symbol IN ('{symbol_list}') AND {factor_name} IS NOT NULL"
                    )
                else:
                    # 查询整个行业
                    cursor.execute(
                        f"SELECT {factor_name} FROM quant.stocks WHERE sector = %s AND {factor_name} IS NOT NULL",
                        (sector,)
                    )
                
                results = cursor.fetchall()
                values = [float(row[factor_name]) for row in results if row[factor_name] is not None]
                
                # 缓存结果
                self._factor_cache[cache_key] = values
                return values
        except Exception as e:
            print(f"获取 {sector} 行业 {factor_name} 因子值失败: {e}")
            return []
    
    def clear_cache(self):
        """清除缓存"""
        self._sector_cache.clear()
        self._factor_cache.clear()

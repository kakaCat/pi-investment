"""
行业数据端口实现（基础设施层）

用于测试和演示。
"""

from typing import Dict, List, Optional
from domain.scoring.ports import IndustryDataPort


class MockIndustryDataAdapter(IndustryDataPort):
    """
    模拟行业数据适配器
    
    用于测试和演示。
    """
    
    def __init__(self):
        """初始化模拟数据"""
        self.sector_map = {
            '600887': '食品饮料',
            '002463': '电子',
            '600519': '食品饮料',
            '000001': '银行',
        }
        self.sector_factors = {
            '食品饮料': {
                'pe': [20, 25, 30, 35, 40, 45, 50],
                'roe': [15, 18, 20, 22, 25, 28, 30],
                'revenue_growth': [5, 8, 10, 12, 15, 18, 20],
            },
            '电子': {
                'pe': [30, 40, 50, 60, 70, 80, 100],
                'roe': [10, 12, 15, 18, 20, 25, 30],
                'revenue_growth': [10, 15, 20, 25, 30, 40, 50],
            },
            '银行': {
                'pe': [4, 5, 6, 7, 8, 9, 10],
                'roe': [10, 11, 12, 13, 14, 15, 16],
                'revenue_growth': [2, 3, 4, 5, 6, 7, 8],
            },
        }
    
    def get_sector(self, symbol: str) -> str:
        """获取股票所属行业"""
        return self.sector_map.get(symbol, '未知')
    
    def get_sector_stocks(self, sector: str) -> List[str]:
        """获取行业内的所有股票"""
        return [
            symbol for symbol, sec in self.sector_map.items() 
            if sec == sector
        ]
    
    def get_sector_factor_values(
        self, 
        sector: str, 
        factor_name: str,
        symbols: Optional[List[str]] = None
    ) -> List[float]:
        """获取行业内某因子的所有值"""
        return self.sector_factors.get(sector, {}).get(factor_name, [])

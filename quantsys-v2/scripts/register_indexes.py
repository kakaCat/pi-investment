"""
注册指数符号到 stocks 表（避免外键约束）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infrastructure.persistence.orm import get_session
from infrastructure.persistence.orm.models import Stock
from datetime import datetime

def register_index_symbols():
    """注册指数符号到 stocks 表"""
    session = get_session()
    
    indexes = [
        {'symbol': '000001', 'name': '上证指数', 'market': 'A'},
        {'symbol': '000300', 'name': '沪深300', 'market': 'A'},
        {'symbol': '399001', 'name': '深证成指', 'market': 'A'},
        {'symbol': '399300', 'name': '沪深300(深)', 'market': 'A'},
        {'symbol': '399006', 'name': '创业板指', 'market': 'A'},
    ]
    
    for idx in indexes:
        existing = session.query(Stock).filter_by(symbol=idx['symbol']).first()
        if not existing:
            stock = Stock(
                symbol=idx['symbol'],
                name=idx['name'],
                market=idx['market'],
                industry='指数',
                sector='指数',
                is_st=False,
                is_suspended=False,
                is_delisted=False,
                updated_at=datetime.utcnow()
            )
            session.add(stock)
            print(f"✓ 注册指数: {idx['symbol']} {idx['name']}")
        else:
            print(f"  跳过已存在: {idx['symbol']} {existing.name}")
    
    session.commit()
    print(f"\n指数注册完成")

if __name__ == '__main__':
    register_index_symbols()

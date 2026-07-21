"""
初始化缓存 - 使用模拟数据

当数据源不可用时，使用此脚本建立初始缓存
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from infrastructure.utils.simple_cache import SimpleCache
from datetime import datetime, timedelta
import random

def generate_mock_hot_stocks():
    """生成模拟热搜股票数据"""
    mock_stocks = [
        {"code": "300308", "name": "中际旭创", "热度": 9500},
        {"code": "000068", "name": "华控赛格", "热度": 8800},
        {"code": "600809", "name": "山西汾酒", "热度": 8200},
        {"code": "000651", "name": "格力电器", "热度": 7800},
        {"code": "600519", "name": "贵州茅台", "热度": 7500},
        {"code": "000858", "name": "五粮液", "热度": 7200},
        {"code": "002594", "name": "比亚迪", "热度": 6900},
        {"code": "600036", "name": "招商银行", "热度": 6500},
        {"code": "601318", "name": "中国平安", "热度": 6200},
        {"code": "000333", "name": "美的集团", "热度": 5800},
    ]

    return {
        'success': True,
        'data': {
            'stocks': mock_stocks,
            'update_time': datetime.now().isoformat(),
            '_mock_data': True
        },
        'source': 'mock',
        'mode': 'first'
    }

def generate_mock_north_flow():
    """生成模拟北向资金数据"""
    flows = []
    base_date = datetime.now() - timedelta(days=30)

    for i in range(30):
        date = base_date + timedelta(days=i)
        flows.append({
            'date': date.strftime('%Y-%m-%d'),
            'net_flow': random.randint(-5000, 5000) / 10,  # -500 到 500 亿
            'sh_flow': random.randint(-3000, 3000) / 10,
            'sz_flow': random.randint(-2000, 2000) / 10,
        })

    return {
        'success': True,
        'data': {
            'flows': flows,
            'summary': {
                'total_net_flow': sum(f['net_flow'] for f in flows),
                'days': len(flows)
            },
            'update_time': datetime.now().isoformat(),
            '_mock_data': True
        },
        'source': 'mock'
    }

def main():
    """主函数"""
    cache = SimpleCache()

    print("=== 初始化缓存（模拟数据）===")
    print()

    # 1. 热搜股票 - 两种模式都缓存
    print("1. 生成热搜股票缓存...")
    hot_stocks_data = generate_mock_hot_stocks()
    cache.set("hot_stocks_A股_first", hot_stocks_data)
    cache.set("hot_stocks_A股_all", hot_stocks_data)  # API默认使用 all 模式
    print(f"   ✓ 已保存 (first): {len(hot_stocks_data['data']['stocks'])} 只股票")
    print(f"   ✓ 已保存 (all): {len(hot_stocks_data['data']['stocks'])} 只股票")

    # 2. 北向资金
    print("2. 生成北向资金缓存...")
    north_flow_data = generate_mock_north_flow()
    cache.set("north_flow_default_default", north_flow_data)
    cache.set("north_flow_None_None", north_flow_data)  # 可能的另一个键
    print(f"   ✓ 已保存: {len(north_flow_data['data']['flows'])} 条数据")

    print()
    print("=== 缓存初始化完成 ===")
    print()
    print("提示: 这些是模拟数据，用于演示和测试。")
    print("当数据源恢复可用时，缓存会自动更新为真实数据。")

if __name__ == '__main__':
    main()

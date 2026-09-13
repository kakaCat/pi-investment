#!/usr/bin/env python3
"""
历史数据 amount 字段修复脚本

修复逻辑：
1. 找出 8/28-9/2 期间 amount=0 的记录
2. 通过数据源重新获取（优先）
3. 如果获取失败，用 volume × close 估算
4. 分批处理，避免频繁调用 API

执行时间：凌晨 2:00（非交易时间）
"""
import os
import sys
import time
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, create_engine
from dotenv import load_dotenv

load_dotenv()

# 数据库配置
PG_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': os.getenv('PGPORT', '5432'),
    'user': os.getenv('PGUSER'),
    'password': os.getenv('PGPASSWORD'),
    'database': 'quant_investment',
}

DB_URL = f"postgresql://{PG_CONFIG['user']}:{PG_CONFIG['password']}@{PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['database']}"

# 修复配置
BATCH_SIZE = 100  # 每批处理100条
SLEEP_SECONDS = 2  # 每批间隔2秒，避免频繁调用
REPAIR_DATE_RANGE = ('2026-08-28', '2026-09-02')


def get_engine():
    """获取数据库引擎"""
    return create_engine(DB_URL)


def fetch_quote_from_tencent(symbol: str) -> dict:
    """从腾讯数据源获取实时行情（用于获取成交额）"""
    import requests
    
    # 转换代码格式
    if symbol.startswith('6'):
        tencent_symbol = f"sh{symbol}"
    elif symbol.startswith('0') or symbol.startswith('3'):
        tencent_symbol = f"sz{symbol}"
    else:
        tencent_symbol = symbol
    
    url = f"https://qt.gtimg.cn/q={tencent_symbol}"
    
    try:
        response = requests.get(url, timeout=10)
        response.encoding = 'gbk'
        
        # 解析腾讯行情数据
        # 格式: v_sh600519="1~贵州茅台~600519~...~成交额~..."
        data = response.text
        if '~' in data:
            parts = data.split('~')
            if len(parts) > 45:
                # 腾讯格式：成交额在特定位置
                amount = float(parts[37]) if parts[37] else 0  # 成交额（元）
                volume = float(parts[36]) if parts[36] else 0   # 成交量（手）
                return {
                    'amount': amount,
                    'volume': volume * 100,  # 手转股
                }
    except Exception as e:
        print(f"获取 {symbol} 行情失败: {e}")
    
    return None


def repair_amount_batch(engine, symbols_batch: list):
    """修复一批记录的 amount"""
    repaired_count = 0
    failed_symbols = []
    
    for symbol_info in symbols_batch:
        symbol = symbol_info['symbol']
        trade_date = symbol_info['trade_date']
        close_price = symbol_info['close']
        volume = symbol_info['volume']
        
        # 尝试从数据源获取
        quote = fetch_quote_from_tencent(symbol)
        
        if quote and quote['amount'] > 0:
            # 使用数据源获取的 amount
            new_amount = quote['amount']
            source_note = 'tencent-repair'
        else:
            # 用 volume × close 估算
            new_amount = volume * close_price
            source_note = 'calculated-repair'
        
        # 更新数据库
        try:
            with engine.begin() as conn:
                conn.execute(text(
                    "UPDATE quant.daily_klines "
                    "SET amount = :amount, source = COALESCE(source, '') || '-:note' "
                    "WHERE symbol = :symbol AND trade_date = :trade_date"
                ), {
                    'amount': new_amount,
                    'symbol': symbol,
                    'trade_date': trade_date,
                    'note': source_note,
                })
                repaired_count += 1
        except Exception as e:
            print(f"更新 {symbol} {trade_date} 失败: {e}")
            failed_symbols.append(symbol)
        
        # 间隔，避免频繁调用
        time.sleep(SLEEP_SECONDS)
    
    return repaired_count, failed_symbols


def main():
    """主函数"""
    print(f"[{datetime.now()}] 开始修复 amount 数据...")
    
    engine = get_engine()
    
    # 1. 找出需要修复的记录
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT symbol, trade_date, close, volume "
            "FROM quant.daily_klines "
            "WHERE trade_date BETWEEN :start AND :end "
            "  AND amount = 0 "
            "ORDER BY trade_date, symbol"
        ), {
            'start': REPAIR_DATE_RANGE[0],
            'end': REPAIR_DATE_RANGE[1],
        })
        
        records = [{
            'symbol': row[0],
            'trade_date': row[1],
            'close': float(row[2]) if row[2] else 0,
            'volume': float(row[3]) if row[3] else 0,
        } for row in result]
    
    total = len(records)
    print(f"找到 {total} 条需要修复的记录")
    
    if total == 0:
        print("没有需要修复的记录，退出")
        return
    
    # 2. 分批处理
    total_repaired = 0
    total_failed = []
    
    for i in range(0, total, BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        print(f"处理第 {i+1}-{min(i+BATCH_SIZE, total)} 条...")
        
        repaired, failed = repair_amount_batch(engine, batch)
        total_repaired += repaired
        total_failed.extend(failed)
        
        print(f"  修复: {repaired}, 失败: {len(failed)}")
        
        # 批次间隔，避免被封IP
        if i + BATCH_SIZE < total:
            sleep_time = 10  # 每批间隔10秒
            print(f"  等待 {sleep_time} 秒...")
            time.sleep(sleep_time)
    
    # 3. 统计结果
    print(f"\n[{datetime.now()}] 修复完成:")
    print(f"  总记录: {total}")
    print(f"  修复成功: {total_repaired}")
    print(f"  修复失败: {len(total_failed)}")
    
    if total_failed:
        print(f"  失败列表: {', '.join(total_failed[:10])}...")


if __name__ == '__main__':
    main()

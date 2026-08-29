#!/usr/bin/env python3
"""
使用新浪财经数据源批量补充3年历史数据

相比 AkShare，新浪财经更稳定，支持并发
"""
import json
import sys
import os
import ssl
import time
import argparse
from pathlib import Path
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent

# 加载环境变量
from dotenv import load_dotenv
env_path = project_root.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

from adapters.outbound.repositories import KlineORMRepository

SINA_KLINES_URL = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'


def sina_symbol(sym: str) -> str:
    """转换为新浪财经的股票代码格式"""
    sym = sym.strip().upper().replace('.SH', '').replace('.SZ', '')
    if sym.startswith(('6', '5', '51', '688')):
        return f'sh{sym}'
    return f'sz{sym}'


def fetch_sina_klines(symbol: str, datalen: int = 730, max_retries: int = 3):
    """
    从新浪财经获取K线数据

    Args:
        symbol: 股票代码（如 000001）
        datalen: 获取的K线数量（730 约等于3年）
        max_retries: 最大重试次数

    Returns:
        tuple: (symbol, klines_list, error_msg)
    """
    sina = sina_symbol(symbol)
    url = f'{SINA_KLINES_URL}?symbol={sina}&scale=240&ma=no&datalen={datalen}'

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    })

    for attempt in range(max_retries):
        try:
            with urlopen(req, context=ctx, timeout=20) as resp:
                raw = resp.read()

                # 尝试不同编码
                for encoding in ('gbk', 'gb2312', 'utf-8'):
                    try:
                        data = json.loads(raw.decode(encoding))

                        if not data or not isinstance(data, list):
                            return (symbol, [], 'empty data')

                        klines = []
                        for k in data:
                            try:
                                kline = {
                                    'symbol': symbol,
                                    'trade_date': k['day'],
                                    'open': float(k['open']),
                                    'high': float(k['high']),
                                    'low': float(k['low']),
                                    'close': float(k['close']),
                                    'volume': float(k['volume']),
                                    'amount': float(k.get('amount', 0) or 0),
                                    'turnover_rate': float(k.get('turnover_rate', 0) or 0),
                                }
                                klines.append(kline)
                            except (ValueError, KeyError):
                                continue

                        return (symbol, klines, None)

                    except (UnicodeDecodeError, json.JSONDecodeError):
                        continue

                return (symbol, [], 'decode error')

        except URLError as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避
                continue
            return (symbol, [], str(e)[:100])

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return (symbol, [], str(e)[:100])

    return (symbol, [], 'max retries exceeded')


def backfill_3year_sina(limit: int = 0, workers: int = 4):
    """
    使用新浪财经数据源批量补充3年历史数据

    Args:
        limit: 限制处理的股票数量（0=全部）
        workers: 并发工作线程数
    """
    kline_repo = KlineORMRepository()

    # 读取需要补充的股票列表
    list_file = project_root / 'scripts' / 'stocks_need_3year_backfill.txt'
    if not list_file.exists():
        print(f"❌ 错误: 未找到股票列表文件 {list_file}")
        print("请先运行: python scripts/check_3year_data.py")
        return

    # 解析股票列表（只处理活跃股票）
    symbols_to_process = []
    with open(list_file, 'r') as f:
        in_active_section = False
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                if '优先级高' in line:
                    in_active_section = True
                elif '优先级中' in line or '优先级低' in line:
                    in_active_section = False
                continue

            if in_active_section:
                parts = line.split('|')
                if len(parts) >= 1:
                    symbol = parts[0].strip()
                    symbols_to_process.append(symbol)

    if limit > 0:
        symbols_to_process = symbols_to_process[:limit]

    total = len(symbols_to_process)

    print("=" * 80)
    print("批量补充3年历史数据（新浪财经数据源）")
    print("=" * 80)
    print(f"待处理股票数: {total}")
    print(f"数据源: 新浪财经 (Sina Finance)")
    print(f"并发线程数: {workers}")
    print(f"获取数量: 730条 (约3年)")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 统计
    success_count = 0
    fail_count = 0
    total_rows = 0
    start_time = time.time()

    # 并发获取数据
    with ThreadPoolExecutor(max_workers=workers) as executor:
        # 提交所有任务
        future_to_symbol = {
            executor.submit(fetch_sina_klines, symbol, 730): symbol
            for symbol in symbols_to_process
        }

        # 处理完成的任务
        for i, future in enumerate(as_completed(future_to_symbol), 1):
            symbol, klines, error = future.result()

            if error:
                fail_count += 1
                print(f"[{i}/{total}] {symbol} ❌ {error}")
            elif len(klines) == 0:
                fail_count += 1
                print(f"[{i}/{total}] {symbol} ⚠️  无数据")
            else:
                # 写入数据库
                try:
                    saved_count = kline_repo.save_daily_klines(klines)
                    success_count += 1
                    total_rows += saved_count

                    # 显示进度
                    elapsed = time.time() - start_time
                    speed = i / elapsed if elapsed > 0 else 0
                    eta = (total - i) / speed if speed > 0 else 0

                    print(f"[{i}/{total}] {symbol} ✓ {len(klines)}条 "
                          f"| {success_count}✓ {fail_count}✗ | {speed:.1f}/s ETA {int(eta)}s")
                except Exception as e:
                    fail_count += 1
                    print(f"[{i}/{total}] {symbol} ❌ 保存失败: {str(e)[:100]}")

            # 每100个显示一次统计
            if i % 100 == 0:
                elapsed = time.time() - start_time
                print()
                print(f"进度: {i}/{total} ({i*100/total:.1f}%)")
                print(f"成功: {success_count}, 失败: {fail_count}, 总行数: {total_rows}")
                print(f"耗时: {elapsed:.1f}秒, 速度: {i/elapsed:.2f} 股/秒")
                print()

    # 最终统计
    elapsed = time.time() - start_time
    print()
    print("=" * 80)
    print("补充完成")
    print("=" * 80)
    print(f"处理股票数: {total}")
    print(f"成功: {success_count} ({success_count*100/total:.1f}%)")
    print(f"失败: {fail_count} ({fail_count*100/total:.1f}%)")
    print(f"总行数: {total_rows}")
    print(f"总耗时: {elapsed:.1f}秒 ({elapsed/60:.1f}分钟)")
    print(f"平均速度: {total/elapsed:.2f} 股/秒")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='使用新浪财经数据源批量补充3年历史数据')
    parser.add_argument('--limit', type=int, default=0, help='限制处理的股票数量（0=全部）')
    parser.add_argument('--workers', type=int, default=4, help='并发工作线程数（建议4-8）')

    args = parser.parse_args()

    try:
        backfill_3year_sina(
            limit=args.limit,
            workers=args.workers
        )
    except KeyboardInterrupt:
        print()
        print("❌ 用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 执行失败: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

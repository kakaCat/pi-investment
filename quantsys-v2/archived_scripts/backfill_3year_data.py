#!/usr/bin/env python3
"""
批量补充活跃股票的3年历史数据

使用 AkShare 获取前复权日线数据，写入数据库
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import time
import argparse

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
from dotenv import load_dotenv
env_path = project_root.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

# 禁用代理（防止连接问题）
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(key, None)

from adapters.outbound.repositories import KlineORMRepository

# 尝试导入 akshare
try:
    import akshare as ak
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False
    print("警告: 未安装 akshare，将跳过数据获取")


def normalize_symbol_for_akshare(symbol: str) -> str:
    """
    转换股票代码为 AkShare 格式

    000001 -> 000001 (深圳)
    600000 -> 600000 (上海)
    688001 -> 688001 (科创板)
    """
    # 移除后缀
    symbol = symbol.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
    return symbol


def fetch_klines_from_akshare(symbol: str, start_date: str, end_date: str, max_retries: int = 3):
    """
    从 AkShare 获取前复权日线数据

    Args:
        symbol: 股票代码（如 000001）
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        max_retries: 最大重试次数

    Returns:
        list of dict: K线数据列表
    """
    if not HAS_AKSHARE:
        return None

    ak_symbol = normalize_symbol_for_akshare(symbol)

    for attempt in range(max_retries):
        try:
            # 使用前复权数据
            df = ak.stock_zh_a_hist(
                symbol=ak_symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"  # 前复权
            )

            if df is None or df.empty:
                return []

            # 转换为标准格式
            klines = []
            for _, row in df.iterrows():
                try:
                    kline = {
                        'symbol': symbol,  # 保持原始格式（不带后缀）
                        'trade_date': row['日期'],
                        'open': float(row['开盘']),
                        'high': float(row['最高']),
                        'low': float(row['最低']),
                        'close': float(row['收盘']),
                        'volume': float(row['成交量']),
                        'amount': float(row['成交额']),
                        'turnover_rate': float(row.get('换手率', 0.0))
                    }
                    klines.append(kline)
                except (ValueError, KeyError) as e:
                    continue

            return klines

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避
                continue
            else:
                print(f"  ❌ {symbol}: {str(e)}")
                return None

    return None


def backfill_3year_data(limit: int = 0, delay: float = 0.5, resume: bool = False):
    """
    批量补充3年历史数据

    Args:
        limit: 限制处理的股票数量（0=全部）
        delay: 请求间隔（秒）
        resume: 是否从上次中断处继续
    """
    if not HAS_AKSHARE:
        print("❌ 错误: 需要安装 akshare")
        print("安装命令: pip install akshare")
        return

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
                # 格式: 000001|524|72.78%|2026-06-02|0|数据不足...
                parts = line.split('|')
                if len(parts) >= 1:
                    symbol = parts[0].strip()
                    symbols_to_process.append(symbol)

    if limit > 0:
        symbols_to_process = symbols_to_process[:limit]

    total = len(symbols_to_process)
    print("=" * 80)
    print("批量补充3年历史数据")
    print("=" * 80)
    print(f"待处理股票数: {total}")
    print(f"数据源: AkShare (前复权)")
    print(f"时间范围: 最近3年")
    print(f"请求间隔: {delay}秒")
    print()

    # 计算时间范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * 3 + 30)  # 多取30天以确保覆盖

    start_date_str = start_date.strftime('%Y%m%d')
    end_date_str = end_date.strftime('%Y%m%d')

    print(f"开始时间: {start_date.strftime('%Y-%m-%d')}")
    print(f"结束时间: {end_date.strftime('%Y-%m-%d')}")
    print()

    # 统计
    success_count = 0
    fail_count = 0
    total_rows = 0

    start_time = time.time()

    for i, symbol in enumerate(symbols_to_process, 1):
        # 获取数据
        klines = fetch_klines_from_akshare(symbol, start_date_str, end_date_str)

        if klines is None:
            fail_count += 1
            print(f"[{i}/{total}] {symbol} ❌ 获取失败")
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

                print(f"[{i}/{total}] {symbol} ✓ {len(klines)}条数据 "
                      f"| {success_count}✓ {fail_count}✗ | {speed:.1f}/s ETA {int(eta)}s")
            except Exception as e:
                fail_count += 1
                print(f"[{i}/{total}] {symbol} ❌ 保存失败: {str(e)}")

        # 延迟
        if i < total:
            time.sleep(delay)

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
    print(f"成功: {success_count}")
    print(f"失败: {fail_count}")
    print(f"总行数: {total_rows}")
    print(f"总耗时: {elapsed:.1f}秒 ({elapsed/60:.1f}分钟)")
    print(f"平均速度: {total/elapsed:.2f} 股/秒")
    print()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='批量补充活跃股票的3年历史数据')
    parser.add_argument('--limit', type=int, default=0, help='限制处理的股票数量（0=全部）')
    parser.add_argument('--delay', type=float, default=0.5, help='请求间隔（秒）')
    parser.add_argument('--resume', action='store_true', help='从上次中断处继续')

    args = parser.parse_args()

    try:
        backfill_3year_data(
            limit=args.limit,
            delay=args.delay,
            resume=args.resume
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

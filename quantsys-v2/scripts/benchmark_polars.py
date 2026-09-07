#!/usr/bin/env python3
"""
Performance benchmark: pandas vs polars

Compares execution time and memory usage for key operations.
"""
import time
import psutil
import polars as pl
import pandas as pd
from datetime import date, timedelta


def benchmark_dataframe_creation(rows: int = 100000):
    """Benchmark DataFrame creation"""
    data = {
        'symbol': ['600000'] * rows,
        'date': [date(2024, 1, 1) + timedelta(days=i % 365) for i in range(rows)],
        'close': [100.0 + i * 0.01 for i in range(rows)],
        'volume': [1000000 + i * 100 for i in range(rows)],
    }

    # pandas
    start = time.time()
    df_pd = pd.DataFrame(data)
    time_pd = time.time() - start
    mem_pd = psutil.Process().memory_info().rss / 1024 / 1024

    # polars
    start = time.time()
    df_pl = pl.DataFrame(data)
    time_pl = time.time() - start
    mem_pl = psutil.Process().memory_info().rss / 1024 / 1024

    print(f"DataFrame Creation ({rows:,} rows):")
    print(f"  pandas: {time_pd:.4f}s, {mem_pd:.0f}MB")
    print(f"  polars: {time_pl:.4f}s, {mem_pl:.0f}MB")
    print(f"  Speedup: {time_pd/time_pl:.1f}x")
    print()

    return df_pd, df_pl


def benchmark_filter_operation(df_pd, df_pl):
    """Benchmark filter operation"""
    # pandas
    start = time.time()
    result_pd = df_pd[df_pd['volume'] > 1500000]
    time_pd = time.time() - start

    # polars
    start = time.time()
    result_pl = df_pl.filter(pl.col('volume') > 1500000)
    time_pl = time.time() - start

    print(f"Filter Operation:")
    print(f"  pandas: {time_pd:.4f}s")
    print(f"  polars: {time_pl:.4f}s")
    print(f"  Speedup: {time_pd/time_pl:.1f}x")
    print()


def benchmark_group_by(df_pd, df_pl):
    """Benchmark group by aggregation"""
    # pandas
    start = time.time()
    result_pd = df_pd.groupby('symbol')['close'].mean()
    time_pd = time.time() - start

    # polars
    start = time.time()
    result_pl = df_pl.group_by('symbol').agg(pl.col('close').mean())
    time_pl = time.time() - start

    print(f"Group By Aggregation:")
    print(f"  pandas: {time_pd:.4f}s")
    print(f"  polars: {time_pl:.4f}s")
    print(f"  Speedup: {time_pd/time_pl:.1f}x")
    print()


if __name__ == '__main__':
    print("=" * 50)
    print("Pandas vs Polars Performance Benchmark")
    print("=" * 50)
    print()

    df_pd, df_pl = benchmark_dataframe_creation(rows=100000)
    benchmark_filter_operation(df_pd, df_pl)
    benchmark_group_by(df_pd, df_pl)

    print("=" * 50)
    print("Benchmark Complete")
    print("=" * 50)

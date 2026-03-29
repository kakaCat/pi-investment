# Data Pipeline 实现方案

## Phase 1: 核心框架

### 1.1 CLI 入口 (pipeline.py)

```python
#!/usr/bin/env python3
"""
Data Pipeline - 独立的市场数据更新工具

Usage:
    python pipeline.py update-stocks [--market A|HK] [--force]
    python pipeline.py update-klines [--symbols CODE1,CODE2] [--days 730]
    python pipeline.py full [--market A]
    python pipeline.py status
"""

import argparse
import sys
from db import Database
from fetchers.stock_list import StockListFetcher
from fetchers.klines import KlineFetcher

def main():
    parser = argparse.ArgumentParser(description='Data Pipeline')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # update-stocks
    stocks_parser = subparsers.add_parser('update-stocks')
    stocks_parser.add_argument('--market', choices=['A', 'HK'], default='A')
    stocks_parser.add_argument('--force', action='store_true')

    # update-klines
    klines_parser = subparsers.add_parser('update-klines')
    klines_parser.add_argument('--symbols', help='逗号分隔的股票代码')
    klines_parser.add_argument('--days', type=int, default=730)

    # full
    full_parser = subparsers.add_parser('full')
    full_parser.add_argument('--market', choices=['A', 'HK'], default='A')

    # status
    subparsers.add_parser('status')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    db = Database('.pi-invest/stock-db/stocks.db')

    if args.command == 'update-stocks':
        fetcher = StockListFetcher(db)
        fetcher.run(args.market, args.force)

    elif args.command == 'update-klines':
        symbols = args.symbols.split(',') if args.symbols else None
        fetcher = KlineFetcher(db)
        fetcher.run(symbols, args.days)

    elif args.command == 'full':
        print(f"[Full] 开始完整数据更新 (市场: {args.market})")
        stock_fetcher = StockListFetcher(db)
        stock_fetcher.run(args.market, force=False)

        kline_fetcher = KlineFetcher(db)
        kline_fetcher.run(symbols=None, days=730)

    elif args.command == 'status':
        db.print_status()

if __name__ == '__main__':
    main()
```

### 1.2 数据库封装 (db.py)

```python
import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        """Schema 迁移：添加新字段"""
        cursor = self.conn.cursor()

        # 检查并添加新字段
        cursor.execute("PRAGMA table_info(stocks)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        new_columns = {
            'sector': 'TEXT',
            'roe': 'REAL',
            'net_profit_growth': 'REAL',
            'gross_margin': 'REAL',
            'debt_ratio': 'REAL',
            'avg_turnover_rate': 'REAL',
            'avg_volume': 'REAL',
            'avg_amount': 'REAL',
        }

        for col, col_type in new_columns.items():
            if col not in existing_columns:
                print(f"[DB] 添加字段: {col}")
                cursor.execute(f"ALTER TABLE stocks ADD COLUMN {col} {col_type}")

        self.conn.commit()

    def upsert_stocks(self, stocks: List[Dict[str, Any]]) -> int:
        """批量插入或更新股票"""
        cursor = self.conn.cursor()
        count = 0

        for stock in stocks:
            cursor.execute("""
                INSERT OR REPLACE INTO stocks
                (symbol, name, market, industry, market_cap, pe, pb,
                 is_st, list_date, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                stock.get('symbol'),
                stock.get('name'),
                stock.get('market', 'A'),
                stock.get('industry'),
                stock.get('market_cap'),
                stock.get('pe'),
                stock.get('pb'),
                1 if 'ST' in stock.get('name', '') else 0,
                stock.get('list_date'),
                datetime.now().isoformat()
            ))
            count += 1

        self.conn.commit()
        return count

    def get_all_symbols(self, market: Optional[str] = None) -> List[str]:
        """获取所有股票代码"""
        cursor = self.conn.cursor()
        if market:
            cursor.execute("SELECT symbol FROM stocks WHERE market = ?", (market,))
        else:
            cursor.execute("SELECT symbol FROM stocks")
        return [row[0] for row in cursor.fetchall()]

    def count_stocks(self, market: Optional[str] = None) -> int:
        """统计股票数量"""
        cursor = self.conn.cursor()
        if market:
            cursor.execute("SELECT COUNT(*) FROM stocks WHERE market = ?", (market,))
        else:
            cursor.execute("SELECT COUNT(*) FROM stocks")
        return cursor.fetchone()[0]

    def print_status(self):
        """打印数据库状态"""
        print("=" * 50)
        print("数据库状态")
        print("=" * 50)
        print(f"A股数量: {self.count_stocks('A')}")
        print(f"港股数量: {self.count_stocks('HK')}")

        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT symbol) FROM daily_klines")
        kline_count = cursor.fetchone()[0]
        print(f"K线数据覆盖股票数: {kline_count}")

        cursor.execute("SELECT MAX(updated_at) FROM stocks")
        last_update = cursor.fetchone()[0]
        print(f"最后更新时间: {last_update or '未更新'}")
        print("=" * 50)

    def close(self):
        self.conn.close()
```

### 1.3 股票列表拉取 (fetchers/stock_list.py)

```python
import akshare as ak
import pandas as pd
from typing import List, Dict, Any

class StockListFetcher:
    def __init__(self, db):
        self.db = db

    def run(self, market: str = 'A', force: bool = False):
        """更新股票列表"""
        print(f"[StockList] 开始更新 {market} 股列表...")

        if market == 'A':
            stocks = self._fetch_a_stocks()
        elif market == 'HK':
            stocks = self._fetch_hk_stocks()
        else:
            raise ValueError(f"不支持的市场: {market}")

        count = self.db.upsert_stocks(stocks)
        print(f"[StockList] 完成，更新 {count} 只股票")

    def _fetch_a_stocks(self) -> List[Dict[str, Any]]:
        """拉取 A 股列表"""
        # 使用 akshare 的实时行情接口获取所有 A 股
        df = ak.stock_zh_a_spot_em()

        stocks = []
        for _, row in df.iterrows():
            stocks.append({
                'symbol': row['代码'],
                'name': row['名称'],
                'market': 'A',
                'market_cap': row.get('总市值', 0) / 1e8 if pd.notna(row.get('总市值')) else None,
                'pe': row.get('市盈率-动态') if pd.notna(row.get('市盈率-动态')) else None,
                'pb': row.get('市净率') if pd.notna(row.get('市净率')) else None,
                'industry': row.get('所属行业'),
            })

        return stocks

    def _fetch_hk_stocks(self) -> List[Dict[str, Any]]:
        """拉取港股列表"""
        df = ak.stock_hk_spot_em()

        stocks = []
        for _, row in df.iterrows():
            stocks.append({
                'symbol': row['代码'],
                'name': row['名称'],
                'market': 'HK',
                'market_cap': row.get('总市值') / 1e8 if pd.notna(row.get('总市值')) else None,
                'pe': row.get('市盈率') if pd.notna(row.get('市盈率')) else None,
                'pb': row.get('市净率') if pd.notna(row.get('市净率')) else None,
            })

        return stocks
```

### 1.4 K线数据拉取 (fetchers/klines.py)

```python
import akshare as ak
from typing import List, Optional
from datetime import datetime, timedelta

class KlineFetcher:
    def __init__(self, db):
        self.db = db

    def run(self, symbols: Optional[List[str]] = None, days: int = 730):
        """批量更新K线数据"""
        if symbols is None:
            symbols = self.db.get_all_symbols('A')[:50]  # 默认更新前50只

        print(f"[Klines] 开始更新 {len(symbols)} 只股票的K线数据...")

        success = 0
        for i, symbol in enumerate(symbols, 1):
            try:
                count = self._update_symbol(symbol, days)
                success += 1
                print(f"[{i}/{len(symbols)}] {symbol} 更新 {count} 条")
            except Exception as e:
                print(f"[{i}/{len(symbols)}] {symbol} 失败: {e}")

        print(f"[Klines] 完成，成功 {success}/{len(symbols)}")

    def _update_symbol(self, symbol: str, days: int) -> int:
        """更新单只股票K线"""
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        df = ak.stock_zh_a_hist(symbol=symbol, start_date=start_date, end_date=end_date, adjust="qfq")

        cursor = self.db.conn.cursor()
        count = 0

        for _, row in df.iterrows():
            cursor.execute("""
                INSERT OR REPLACE INTO daily_klines
                (symbol, date, open, high, low, close, volume, amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                row['日期'],
                row['开盘'],
                row['最高'],
                row['最低'],
                row['收盘'],
                row['成交量'],
                row['成交额']
            ))
            count += 1

        self.db.conn.commit()
        return count
```

## Phase 2: 技术面指标

### 2.1 技术指标计算 (fetchers/technicals.py)

```python
from typing import Dict, Any
import pandas as pd

class TechnicalCalculator:
    def __init__(self, db):
        self.db = db

    def calculate_and_update(self, symbol: str) -> Dict[str, Any]:
        """计算并更新技术指标"""
        cursor = self.db.conn.cursor()

        # 获取最近20日K线
        cursor.execute("""
            SELECT date, close, volume, amount, turnover_rate
            FROM daily_klines
            WHERE symbol = ?
            ORDER BY date DESC
            LIMIT 20
        """, (symbol,))

        rows = cursor.fetchall()
        if len(rows) < 20:
            return {}

        df = pd.DataFrame(rows, columns=['date', 'close', 'volume', 'amount', 'turnover_rate'])

        # 计算20日均值
        avg_turnover_rate = df['turnover_rate'].mean() if 'turnover_rate' in df else None
        avg_volume = df['volume'].mean()
        avg_amount = df['amount'].mean() / 10000  # 转换为万元

        # 更新到 stocks 表
        cursor.execute("""
            UPDATE stocks
            SET avg_turnover_rate = ?,
                avg_volume = ?,
                avg_amount = ?
            WHERE symbol = ?
        """, (avg_turnover_rate, avg_volume, avg_amount, symbol))

        self.db.conn.commit()

        return {
            'avg_turnover_rate': avg_turnover_rate,
            'avg_volume': avg_volume,
            'avg_amount': avg_amount
        }
```

### 2.2 扩展 StockListFetcher

在 `stock_list.py` 的 `run()` 方法后添加技术指标计算：

```python
def run(self, market: str = 'A', force: bool = False):
    # ... 原有代码 ...

    # Phase 2: 计算技术指标
    from .technicals import TechnicalCalculator
    tech_calc = TechnicalCalculator(self.db)

    symbols = self.db.get_all_symbols(market)
    print(f"[StockList] 计算技术指标...")

    for i, symbol in enumerate(symbols[:100], 1):  # 限制100只避免太慢
        try:
            tech_calc.calculate_and_update(symbol)
            if i % 10 == 0:
                print(f"  进度: {i}/{min(len(symbols), 100)}")
        except Exception as e:
            pass
```

## Phase 3: 基本面指标

### 3.1 财报数据拉取 (fetchers/financials.py)

```python
import akshare as ak
from typing import Dict, Any, Optional

class FinancialFetcher:
    def __init__(self, db):
        self.db = db

    def fetch_and_update(self, symbol: str) -> Dict[str, Any]:
        """拉取并更新财报指标"""
        try:
            # 获取主要财务指标
            df = ak.stock_financial_analysis_indicator(symbol=symbol)
            if df.empty:
                return {}

            # 取最新一期数据
            latest = df.iloc[0]

            roe = latest.get('净资产收益率')
            net_profit_growth = latest.get('净利润同比增长率')
            gross_margin = latest.get('销售毛利率')
            debt_ratio = latest.get('资产负债率')

            # 更新到数据库
            cursor = self.db.conn.cursor()
            cursor.execute("""
                UPDATE stocks
                SET roe = ?,
                    net_profit_growth = ?,
                    gross_margin = ?,
                    debt_ratio = ?
                WHERE symbol = ?
            """, (roe, net_profit_growth, gross_margin, debt_ratio, symbol))

            self.db.conn.commit()

            return {
                'roe': roe,
                'net_profit_growth': net_profit_growth,
                'gross_margin': gross_margin,
                'debt_ratio': debt_ratio
            }

        except Exception as e:
            return {}
```

### 3.2 扩展 StockListFetcher 添加财报更新

```python
def run(self, market: str = 'A', force: bool = False):
    # ... Phase 1 和 Phase 2 代码 ...

    # Phase 3: 更新财报指标
    from .financials import FinancialFetcher
    fin_fetcher = FinancialFetcher(self.db)

    print(f"[StockList] 更新财报指标...")

    for i, symbol in enumerate(symbols[:50], 1):  # 财报接口慢，限制50只
        try:
            fin_fetcher.fetch_and_update(symbol)
            if i % 10 == 0:
                print(f"  进度: {i}/50")
        except Exception as e:
            pass
```




## Phase 5: 主系统集成

### 5.1 扩展 manage_stock_db Tool

在 `src/services/stock-db/stock-db-tools.ts` 中添加调用 Pipeline 的 action：

```typescript
// 新增 action: 'pipeline_update' | 'pipeline_status'

if (action === 'pipeline_update') {
  const { execSync } = require('child_process');
  const cmd = market
    ? `python pipeline/pipeline.py update-stocks --market ${market}`
    : `python pipeline/pipeline.py full`;

  console.log(`[Tool] 执行: ${cmd}`);
  const output = execSync(cmd, { cwd: process.cwd(), encoding: 'utf-8' });

  return {
    content: [{ type: 'text' as const, text: output }],
    details: { success: true }
  };
}

if (action === 'pipeline_status') {
  const { execSync } = require('child_process');
  const output = execSync('python pipeline/pipeline.py status', {
    cwd: process.cwd(),
    encoding: 'utf-8'
  });

  return {
    content: [{ type: 'text' as const, text: output }],
    details: undefined
  };
}
```

### 5.2 CronService 定时任务

在 `.pi-invest/CRON.json` 中添加：

```json
{
  "tasks": [
    {
      "id": "pipeline-daily",
      "name": "每日数据更新",
      "schedule": {
        "kind": "cron",
        "expr": "0 16 * * 1-5"
      },
      "command": "python pipeline/pipeline.py update-stocks --market A",
      "enabled": true
    },
    {
      "id": "pipeline-weekly",
      "name": "每周K线更新",
      "schedule": {
        "kind": "cron",
        "expr": "0 18 * * 6"
      },
      "command": "python pipeline/pipeline.py update-klines",
      "enabled": true
    }
  ]
}
```

### 5.3 Agent 自主发现

在 `BacktestEngine.getStockPool()` 中添加提示：

```typescript
if (stocks.length === 0) {
  console.warn('[BacktestEngine] 股票数据库为空');
  console.warn('[BacktestEngine] 建议执行: manage_stock_db action=pipeline_update');
  return ['000001', '600036', '601318', '600519', '000858'];
}
```

## 依赖文件

### requirements.txt

```
akshare>=1.12.0
pandas>=2.0.0
```

### 目录结构

```
pipeline/
├── pipeline.py
├── db.py
├── fetchers/
│   ├── __init__.py
│   ├── stock_list.py
│   ├── financials.py
│   ├── technicals.py
│   └── klines.py
├── requirements.txt
└── README.md
```

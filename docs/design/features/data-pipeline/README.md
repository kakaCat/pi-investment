# Data Pipeline 设计文档

## 概述

DataPipeline 是独立的市场数据更新子系统，负责拉取和存储股票数据，主系统只读取其写入的数据库。

## 系统边界

### DataPipeline 职责
- 拉取股票列表、K线、财报、行业分类
- 写入 SQLite 数据库（`.pi-invest/stock-db/stocks.db`）
- 提供 CLI 入口（`python pipeline.py <command>`）

### 主系统职责
- 读取数据库进行筛选、回测、信号生成
- 通过 Bash 工具调用 Pipeline CLI
- CronService 定时调度 Pipeline
- Agent tool 触发 Pipeline

## 架构图

```
┌─────────────────────────────────────────┐
│         主系统调用方式                    │
│  Bash Tool  │  CronService  │  Agent    │
└──────────────────┬──────────────────────┘
                   │ (subprocess)
                   ▼
┌─────────────────────────────────────────┐
│      pipeline.py (Python CLI)           │
│  - update-stocks  更新股票列表           │
│  - update-klines  批量更新K线            │
│  - full           完整数据更新           │
│  - status         查看数据库状态         │
└──────────────────┬──────────────────────┘
                   │
                   ▼
         .pi-invest/stock-db/stocks.db
                   ▲
                   │ (read only)
┌──────────────────┴──────────────────────┐
│  主系统 (StockDBService / BacktestEngine)│
└─────────────────────────────────────────┘
```

## 数据库 Schema

### stocks 表扩展

在现有字段基础上新增：

```sql
ALTER TABLE stocks ADD COLUMN sector TEXT;              -- 概念板块
ALTER TABLE stocks ADD COLUMN roe REAL;                 -- ROE (%)
ALTER TABLE stocks ADD COLUMN net_profit_growth REAL;   -- 净利润增速 (%)
ALTER TABLE stocks ADD COLUMN gross_margin REAL;        -- 毛利率 (%)
ALTER TABLE stocks ADD COLUMN debt_ratio REAL;          -- 资产负债率 (%)
ALTER TABLE stocks ADD COLUMN avg_turnover_rate REAL;   -- 20日平均换手率 (%)
ALTER TABLE stocks ADD COLUMN avg_volume REAL;          -- 20日平均成交量
ALTER TABLE stocks ADD COLUMN avg_amount REAL;          -- 20日平均成交额 (万元)
```

### daily_klines 表

保持不变，已有字段足够。

## CLI 命令设计

### update-stocks
更新股票列表和基本信息（市值、PE、PB、行业、财报指标）

```bash
python pipeline.py update-stocks [--market A|HK] [--force]
```

### update-klines
批量更新K线数据（增量更新，只拉取缺失部分）

```bash
python pipeline.py update-klines [--symbols 600519,000001] [--days 730]
```

### full
完整数据更新（stocks + klines）

```bash
python pipeline.py full [--market A]
```

### status
查看数据库状态（股票数量、最新更新时间、数据完整性）

```bash
python pipeline.py status
```

## 实现优先级

### Phase 1: 核心框架
1. CLI 入口和命令路由
2. SQLite 连接和 Schema 迁移
3. `update-stocks` 命令（只更新基础字段：symbol, name, market, industry, market_cap, pe, pb）

### Phase 2: 技术面指标
4. 计算 20日平均换手率、成交量、成交额
5. 扩展 `update-stocks` 填充技术面字段

### Phase 3: 基本面指标
6. 拉取财报数据（ROE、净利润增速、毛利率、资产负债率）
7. 扩展 `update-stocks` 填充基本面字段

### Phase 4: K线批量更新
8. `update-klines` 命令（增量更新逻辑）
9. `full` 命令（组合调用）

### Phase 5: 集成
10. 主系统 `manage_stock_db` tool 调用 Pipeline CLI
11. CronService 定时任务配置
12. Agent 自主发现数据库为空时触发更新

## 技术选型

- **语言**: Python 3.11+
- **数据源**: akshare
- **数据库**: SQLite3
- **依赖**: pandas, akshare, sqlite3 (标准库)

## 文件结构

```
pipeline/
├── pipeline.py           # CLI 入口
├── db.py                 # 数据库操作封装
├── fetchers/
│   ├── stock_list.py     # 股票列表拉取
│   ├── financials.py     # 财报数据拉取
│   ├── technicals.py     # 技术指标计算
│   └── klines.py         # K线数据拉取
├── requirements.txt
└── README.md
```

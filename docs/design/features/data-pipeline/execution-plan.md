# Data Pipeline 执行计划

## 角色分工

### Claude (我)
- 监控 Codex 执行进度
- 审查 Codex 生成的代码
- 调用 `codex exec review --uncommitted` 做 code review
- 发现问题立即修复
- 管理整体进度和质量

### Codex
- 实际编写 Pipeline 代码
- 按照设计文档实现各个 Phase
- 执行具体的编码任务

## 执行流程

### Phase 1: 核心框架

**任务 1.1: 创建目录结构和基础文件**
```bash
codex exec "创建 pipeline/ 目录结构：
- pipeline/pipeline.py (CLI 入口)
- pipeline/db.py (数据库封装)
- pipeline/fetchers/__init__.py
- pipeline/fetchers/stock_list.py
- pipeline/fetchers/klines.py
- pipeline/requirements.txt
- pipeline/README.md

参考设计文档: docs/design/features/data-pipeline/implementation.md"
```

**任务 1.2: 实现 db.py**
```bash
codex exec "实现 pipeline/db.py，包含：
1. Database 类，连接 SQLite
2. _migrate() 方法，添加新字段（sector, roe, net_profit_growth 等）
3. upsert_stocks() 批量插入股票
4. get_all_symbols() 获取股票代码
5. count_stocks() 统计数量
6. print_status() 打印状态

参考: docs/design/features/data-pipeline/implementation.md 第 1.2 节"
```

**任务 1.3: 实现 pipeline.py CLI 入口**
```bash
codex exec "实现 pipeline/pipeline.py CLI 入口：
1. argparse 命令解析（update-stocks, update-klines, full, status）
2. 路由到对应的 Fetcher
3. 错误处理和日志输出

参考: docs/design/features/data-pipeline/implementation.md 第 1.1 节"
```

**任务 1.4: 实现 stock_list.py**
```bash
codex exec "实现 pipeline/fetchers/stock_list.py：
1. StockListFetcher 类
2. _fetch_a_stocks() 使用 akshare 拉取 A 股列表
3. _fetch_hk_stocks() 拉取港股列表
4. 错误处理和重试逻辑（最多3次）

参考: docs/design/features/data-pipeline/implementation.md 第 1.3 节
注意: 添加重试机制，参考 review.md 建议"
```

**Review 1: Phase 1 代码审查**
```bash
codex exec review --uncommitted
```

### Phase 2: 技术面指标

**任务 2.1: 实现 technicals.py**
```bash
codex exec "实现 pipeline/fetchers/technicals.py：
1. TechnicalCalculator 类
2. calculate_and_update() 计算20日均值（换手率、成交量、成交额）
3. 从 daily_klines 读取数据
4. 更新到 stocks 表

参考: docs/design/features/data-pipeline/implementation.md 第 2.1 节"
```

**任务 2.2: 扩展 stock_list.py 调用技术指标**
```bash
codex exec "扩展 pipeline/fetchers/stock_list.py 的 run() 方法：
在更新股票列表后，调用 TechnicalCalculator 计算技术指标
添加进度显示（每10只打印一次）

参考: docs/design/features/data-pipeline/implementation.md 第 2.2 节"
```

**Review 2: Phase 2 代码审查**
```bash
codex exec review --uncommitted
```

### Phase 3: 基本面指标（可选）

**任务 3.1: 实现 financials.py**
```bash
codex exec "实现 pipeline/fetchers/financials.py：
1. FinancialFetcher 类
2. fetch_and_update() 拉取财报数据（ROE、净利润增速、毛利率、资产负债率）
3. 使用 akshare 财报接口
4. 错误处理（接口失败时跳过）

参考: docs/design/features/data-pipeline/implementation.md 第 3.1 节"
```

**任务 3.2: 添加 --with-financials 参数**
```bash
codex exec "修改 pipeline/pipeline.py：
1. update-stocks 命令添加 --with-financials flag
2. 默认不更新财报，显式指定时才更新
3. 更新 stock_list.py 支持条件调用 FinancialFetcher

参考: docs/design/features/data-pipeline/review.md Phase 3 调整建议"
```

**Review 3: Phase 3 代码审查**
```bash
codex exec review --uncommitted
```

### Phase 4: K线批量更新

**任务 4.1: 实现 klines.py**
```bash
codex exec "实现 pipeline/fetchers/klines.py：
1. KlineFetcher 类
2. run() 批量更新K线
3. _update_symbol() 单只股票增量更新
4. 使用 akshare 拉取历史K线
5. 进度显示和错误处理

参考: docs/design/features/data-pipeline/implementation.md 第 1.4 节"
```

**任务 4.2: 实现 full 命令**
```bash
codex exec "完善 pipeline/pipeline.py 的 full 命令：
1. 先调用 StockListFetcher
2. 再调用 KlineFetcher
3. 打印总体进度和耗时

参考: docs/design/features/data-pipeline/implementation.md 第 1.1 节"
```

**Review 4: Phase 4 代码审查**
```bash
codex exec review --uncommitted
```

### Phase 5: 主系统集成

**任务 5.1: 创建 stock-db-tools.ts 扩展**
```bash
codex exec "修改 src/services/stock-db/（需要先找到对应的 tool 文件）：
添加 pipeline_update 和 pipeline_status action
使用 child_process.execSync 调用 Python CLI

参考: docs/design/features/data-pipeline/implementation.md 第 5.1 节"
```

**任务 5.2: 更新 CRON.json**
```bash
codex exec "修改 .pi-invest/CRON.json：
添加两个定时任务：
1. pipeline-daily: 每日16:00更新股票列表
2. pipeline-weekly: 每周六18:00更新K线

参考: docs/design/features/data-pipeline/implementation.md 第 5.2 节"
```

**任务 5.3: 更新 BacktestEngine 提示**
```bash
codex exec "修改 src/services/quant/backtest-engine.ts：
在 getStockPool() 中，数据库为空时添加提示信息

参考: docs/design/features/data-pipeline/implementation.md 第 5.3 节"
```

**Review 5: Phase 5 代码审查**
```bash
codex exec review --uncommitted
```

## 监控检查点

每个 Phase 完成后，我会检查：
1. ✅ Codex 是否完成所有文件
2. ✅ Code review 是否通过
3. ✅ 是否有遗漏的错误处理
4. ✅ 是否符合设计文档

## 质量标准

- 所有 Python 代码必须有类型注解
- 所有函数必须有 docstring
- 错误处理必须完整（try-except + 日志）
- 进度显示必须清晰（tqdm 或打印）
- 数据验证必须到位（NULL 值处理）

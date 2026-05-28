# 系统性策略回测验证设计文档

**日期：** 2026-05-28  
**作者：** Claude (Kiro)  
**状态：** 设计阶段

## 概述

本设计文档描述如何对量化系统中的所有策略进行系统性回测验证，通过多指标综合评分淘汰无效策略。

## 目标

### 功能目标
- 对所有策略进行全量回测验证
- 使用核心股票池（沪深300 + 创业板50 + 科创50，约400只）
- 2年回测周期（2024-05-27 至 2026-05-27）
- 多指标综合评分（收益优先型）
- 自动标记评分低于60分的策略为无效

### 技术目标
- 利用现有 `/api/backtest/batch` 端点
- 并发执行（10 workers）
- 完整的错误处理和超时控制
- 生成详细的验证报告

### 性能目标
- 假设50个策略 × 400只股票 = 20,000个回测任务
- 预计耗时：30-40分钟
- 单个回测超时：5分钟

## 背景

### 当前问题
- 策略缺乏系统性回测验证
- 现有回测记录为0条
- 唯一一次回测显示策略86表现很差（年化-6.33%，胜率25%）
- 无法判断哪些策略有效

### 解决方案
通过批量回测 + 综合评分，系统性评估所有策略，淘汰无效策略。

## 需求规格

### 回测范围
- **策略选择**: 所有策略（全量验证）
- **股票池**: 核心股票池（沪深300 + 创业板50 + 科创50）
  - 数量：约400只
  - 来源：`StockPoolService.get_core_stocks()`
- **回测周期**: 2年（2024-05-27 至 2026-05-27）
- **初始资金**: 100万元

### 评分标准

#### 指标权重（收益优先型）
| 指标 | 权重 | 说明 |
|------|------|------|
| 年化收益率 | 40% | 主要考核指标 |
| Sharpe比率 | 20% | 风险调整后收益 |
| 最大回撤 | 15% | 下行风险控制 |
| 胜率 | 15% | 交易成功率 |
| 盈亏比 | 10% | 单笔盈亏比例 |

#### 归一化范围
| 指标 | 最小值 | 最大值 | 反向 |
|------|--------|--------|------|
| 年化收益率 | -50% | +50% | 否 |
| Sharpe比率 | -2 | +3 | 否 |
| 最大回撤 | -50% | 0% | 是 |
| 胜率 | 0% | 100% | 否 |
| 盈亏比 | 0 | 3 | 否 |

#### 淘汰阈值
- **及格线**: 60分
- **低于60分**: 标记为 `validation_status = 'invalid'`
- **60分及以上**: 保留为有效策略

### 评分示例
- **策略A**: 年化15%, Sharpe 1.5, 回撤-20%, 胜率60%, 盈亏比2.0 → **68分** ✅ 通过
- **策略B**: 年化-5%, Sharpe 0.3, 回撤-30%, 胜率40%, 盈亏比0.8 → **42分** ❌ 淘汰
- **策略C**: 年化5%, Sharpe 0.8, 回撤-15%, 胜率55%, 盈亏比1.5 → **60分** ✅ 刚好及格

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    TypeScript Agent                          │
│  新增工具: strategy_batch_validate                           │
│  src/infrastructure/tools/strategy/batch-validate-tool.ts   │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/JSON
┌────────────────────┴────────────────────────────────────────┐
│              quantsys-v2 Flask API (port 5001)              │
│  现有端点: POST /api/backtest/batch                         │
│  新增端点: POST /api/strategies/validate                    │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────────┐
│                   并发执行层                                 │
│  ThreadPoolExecutor (10 workers)                            │
│  - 并行回测 20,000 个任务                                    │
│  - 错误隔离 + 超时控制（5分钟/任务）                         │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────────┐
│                   服务层                                     │
│  services/strategy_code_service.py (已有)                   │
│    - backtest_strategy()                                    │
│  services/stock_pool_service.py (已有)                      │
│    - get_core_stocks()                                      │
│  新增: services/strategy_validation_service.py              │
│    - validate_all_strategies()                              │
│    - calculate_comprehensive_score()                        │
│    - mark_invalid_strategies()                              │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────────┐
│                   数据层                                     │
│  repositories/strategy_repository.py                        │
│    - get_all() (已有)                                       │
│    - update_validation_status() (需新增)                    │
│  repositories/backtest_repository.py                        │
│    - save_batch_results() (需新增)                          │
└─────────────────────────────────────────────────────────────┘
```

### 数据流设计

```
步骤1: 准备阶段
  ├─ 查询所有策略 (StrategyRepository.get_all)
  ├─ 获取核心股票池 (StockPoolService.get_core_stocks)
  └─ 生成 jobs 数组: [{strategy_id, symbol, start_date, end_date}, ...]

步骤2: 批量回测
  ├─ 调用 POST /api/backtest/batch
  ├─ 并发执行 (10 workers)
  │   ├─ 每个任务: backtest_strategy(strategy_id, symbol, 2024-05-27, 2026-05-27)
  │   ├─ 返回: {total_return, annual_return, sharpe_ratio, max_drawdown, 
  │   │          win_rate, profit_factor, total_trades}
  │   └─ 错误处理: 超时/异常任务记录到 errors 数组
  └─ 返回: {summary, results[], errors[]}

步骤3: 评分计算
  ├─ 按策略分组聚合结果 (group by strategy_id)
  ├─ 计算每个策略的平均指标 (跨400只股票)
  ├─ 归一化各指标到 [0, 100]
  │   ├─ 年化收益率: [-50%, +50%] → [0, 100]
  │   ├─ Sharpe: [-2, +3] → [0, 100]
  │   ├─ 最大回撤: [-50%, 0%] → [100, 0] (反向)
  │   ├─ 胜率: [0%, 100%] → [0, 100]
  │   └─ 盈亏比: [0, 3] → [0, 100]
  └─ 加权求和: score = 0.4*收益 + 0.2*Sharpe + 0.15*回撤 + 0.15*胜率 + 0.1*盈亏比

步骤4: 策略淘汰
  ├─ 筛选 score < 60 的策略
  ├─ 更新数据库: validation_status = 'invalid'
  ├─ 保存验证报告到数据库
  └─ 返回: {total, passed, failed, details[]}
```

## 详细设计

### 1. TypeScript Agent 工具

**文件**: `src/infrastructure/tools/strategy/batch-validate-tool.ts`

**工具定义**:
```typescript
{
  name: "strategy_batch_validate",
  description: "对所有策略进行系统性回测验证，使用核心股票池和多指标综合评分，自动淘汰无效策略",
  parameters: {
    startDate: "2024-05-27",  // 回测开始日期
    endDate: "2026-05-27",    // 回测结束日期
    threshold: 60,            // 淘汰阈值（0-100分）
    dryRun: false            // 是否仅预览，不实际标记策略
  }
}
```

**调用流程**:
1. 调用 `/api/strategies/validate` 端点
2. 等待批量回测完成（可能需要30-40分钟）
3. 返回验证报告

### 2. Flask API 端点

**文件**: `quantsys-v2/api/routes/strategies.py`

**新增端点**: `POST /api/strategies/validate`

**请求体**:
```json
{
  "startDate": "2024-05-27",
  "endDate": "2026-05-27",
  "threshold": 60,
  "dryRun": false
}
```

**响应体**:
```json
{
  "success": true,
  "data": {
    "total": 50,
    "passed": 32,
    "failed": 18,
    "duration": 1847,
    "details": [
      {
        "strategyId": 86,
        "strategyName": "v17-dual-mode",
        "score": 42.5,
        "status": "failed",
        "metrics": {
          "annualReturn": -0.0633,
          "sharpeRatio": -1.59,
          "maxDrawdown": -0.35,
          "winRate": 0.25,
          "profitFactor": 0.01
        },
        "backtestCount": 387,
        "errorCount": 13
      }
    ]
  }
}
```

### 3. 验证服务

**文件**: `quantsys-v2/services/strategy_validation_service.py`

**核心方法**:

```python
class StrategyValidationService:
    def validate_all_strategies(
        self,
        start_date: str,
        end_date: str,
        threshold: float = 60.0,
        dry_run: bool = False
    ) -> Dict:
        """
        对所有策略进行系统性验证
        
        Returns:
            {
                'total': int,
                'passed': int,
                'failed': int,
                'duration': int,
                'details': List[Dict]
            }
        """
        
    def calculate_comprehensive_score(
        self,
        annual_return: float,
        sharpe_ratio: float,
        max_drawdown: float,
        win_rate: float,
        profit_factor: float
    ) -> float:
        """
        计算综合评分（0-100分）
        
        公式:
        score = normalize(annual_return, -0.5, 0.5) * 0.40 +
                normalize(sharpe_ratio, -2, 3) * 0.20 +
                normalize(max_drawdown, -0.5, 0, reverse=True) * 0.15 +
                normalize(win_rate, 0, 1) * 0.15 +
                normalize(profit_factor, 0, 3) * 0.10
        """
        
    def normalize(
        self,
        value: float,
        min_val: float,
        max_val: float,
        reverse: bool = False
    ) -> float:
        """
        将指标值归一化到 [0, 100]
        
        Args:
            value: 原始值
            min_val: 最小值
            max_val: 最大值
            reverse: 是否反向（如最大回撤，越小越好）
        """
```

**实现逻辑**:

```python
def validate_all_strategies(self, start_date, end_date, threshold, dry_run):
    # 1. 获取所有策略
    strategies = self.strategy_repo.get_all(active_only=False)
    
    # 2. 获取核心股票池
    stock_pool = self.stock_pool_service.get_core_stocks()
    
    # 3. 生成 jobs 数组
    jobs = []
    for strategy in strategies:
        for stock in stock_pool:
            jobs.append({
                'strategy_id': strategy['id'],
                'symbol': stock['symbol'],
                'start_date': start_date,
                'end_date': end_date
            })
    
    # 4. 调用批量回测
    batch_result = self._call_batch_backtest(jobs)
    
    # 5. 按策略聚合结果
    strategy_results = self._aggregate_by_strategy(batch_result['results'])
    
    # 6. 计算评分
    details = []
    for strategy_id, metrics in strategy_results.items():
        score = self.calculate_comprehensive_score(
            metrics['annual_return'],
            metrics['sharpe_ratio'],
            metrics['max_drawdown'],
            metrics['win_rate'],
            metrics['profit_factor']
        )
        
        status = 'passed' if score >= threshold else 'failed'
        
        details.append({
            'strategy_id': strategy_id,
            'score': score,
            'status': status,
            'metrics': metrics
        })
        
        # 7. 更新数据库（如果不是 dry_run）
        if not dry_run and status == 'failed':
            self.strategy_repo.update_validation_status(
                strategy_id, 
                'invalid'
            )
    
    # 8. 返回汇总
    passed = [d for d in details if d['status'] == 'passed']
    failed = [d for d in details if d['status'] == 'failed']
    
    return {
        'total': len(strategies),
        'passed': len(passed),
        'failed': len(failed),
        'details': details
    }
```

### 4. 数据库变更

**文件**: `quantsys-v2/repositories/strategy_repository.py`

**新增方法**:
```python
def update_validation_status(self, strategy_id: int, status: str):
    """
    更新策略验证状态
    
    Args:
        strategy_id: 策略ID
        status: 'valid' | 'invalid'
    """
    cursor = self.db.cursor()
    cursor.execute("""
        UPDATE strategies 
        SET validation_status = %s,
            updated_at = NOW()
        WHERE id = %s
    """, (status, strategy_id))
    self.db.commit()
```

**表结构变更**（如果 `validation_status` 字段不存在）:
```sql
ALTER TABLE strategies 
ADD COLUMN IF NOT EXISTS validation_status VARCHAR(20) DEFAULT 'valid';

CREATE INDEX IF NOT EXISTS idx_strategies_validation_status 
ON strategies(validation_status);
```

### 5. 验证报告存储

**新增表**: `strategy_validation_reports`

```sql
CREATE TABLE IF NOT EXISTS strategy_validation_reports (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER NOT NULL REFERENCES strategies(id),
    validation_date TIMESTAMP NOT NULL DEFAULT NOW(),
    score DECIMAL(5, 2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    annual_return DECIMAL(10, 4),
    sharpe_ratio DECIMAL(10, 4),
    max_drawdown DECIMAL(10, 4),
    win_rate DECIMAL(10, 4),
    profit_factor DECIMAL(10, 4),
    backtest_count INTEGER,
    error_count INTEGER,
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_validation_reports_strategy 
ON strategy_validation_reports(strategy_id, validation_date DESC);
```

## 错误处理

### 超时处理
- 单个回测任务超时：5分钟
- 超时任务记录到 `errors` 数组
- 不影响其他任务执行

### 数据缺失处理
- 股票K线数据不足：跳过该任务，记录警告
- 策略代码执行失败：记录错误，继续下一个

### 并发控制
- 最大并发数：10 workers
- 避免数据库连接池耗尽
- 使用 ThreadPoolExecutor 的 `as_completed` 模式

## 性能优化

### 1. 批量查询优化
- 一次性加载所有策略代码（避免N+1查询）
- 批量获取K线数据（按股票分组）

### 2. 内存优化
- 不保存完整的 trades 数组（只保留汇总指标）
- 分批写入数据库（每100条结果写入一次）

### 3. 进度监控
- 每完成10%任务，输出进度日志
- 预估剩余时间

## 测试计划

### 单元测试
- `test_normalize()` - 归一化函数
- `test_calculate_comprehensive_score()` - 评分计算
- `test_aggregate_by_strategy()` - 结果聚合

### 集成测试
- `test_validate_single_strategy()` - 单策略验证
- `test_validate_with_errors()` - 错误处理
- `test_dry_run_mode()` - 预览模式

### 性能测试
- 10个策略 × 10只股票 = 100任务（预期<2分钟）
- 50个策略 × 400只股票 = 20,000任务（预期<40分钟）

## 使用示例

### Agent 调用
```typescript
// 完整验证（标记无效策略）
strategy_batch_validate({
  startDate: "2024-05-27",
  endDate: "2026-05-27",
  threshold: 60,
  dryRun: false
})

// 预览模式（不标记策略）
strategy_batch_validate({
  startDate: "2024-05-27",
  endDate: "2026-05-27",
  threshold: 60,
  dryRun: true
})
```

### CLI 调用
```bash
# 通过 quant_cli 工具
quant_cli strategy.validate \
  --start-date 2024-05-27 \
  --end-date 2026-05-27 \
  --threshold 60
```

### HTTP 调用
```bash
curl -X POST http://127.0.0.1:5001/api/strategies/validate \
  -H "Content-Type: application/json" \
  -d '{
    "startDate": "2024-05-27",
    "endDate": "2026-05-27",
    "threshold": 60,
    "dryRun": false
  }'
```

## 输出报告格式

### 控制台输出
```
策略批量验证报告
==================
回测周期: 2024-05-27 至 2026-05-27
股票池: 核心股票池（400只）
评分阈值: 60分

总策略数: 50
通过: 32 (64%)
淘汰: 18 (36%)
耗时: 30分47秒

淘汰策略列表:
  [86] v17-dual-mode - 42.5分 (年化-6.33%, Sharpe-1.59, 胜率25%)
  [72] rsi-oversold - 38.2分 (年化-3.21%, Sharpe-0.82, 胜率30%)
  ...

通过策略 TOP 5:
  [53] ma-cross-optimized - 78.3分 (年化18.5%, Sharpe2.1, 胜率65%)
  [61] momentum-breakout - 72.1分 (年化15.2%, Sharpe1.8, 胜率58%)
  ...
```

### JSON 报告
保存到 `/tmp/strategy-validation-report-{timestamp}.json`

## 后续优化方向

1. **增量验证** - 只验证新增/修改的策略
2. **多周期验证** - 同时验证1年、2年、3年周期
3. **分行业验证** - 按行业分组评估策略适用性
4. **实时监控** - 定期自动验证，发现策略退化
5. **A/B测试** - 对比不同评分权重的效果

## 风险与限制

### 风险
- **过拟合风险**: 历史表现好不代表未来有效
- **市场环境变化**: 2年数据可能不足以覆盖所有市场状态
- **数据质量**: K线数据缺失或错误会影响结果

### 限制
- **计算资源**: 大规模回测需要较长时间
- **数据依赖**: 依赖PostgreSQL中的K线数据完整性
- **策略类型**: 仅适用于日线策略，不支持高频策略

## 附录

### A. 评分公式推导

**目标**: 将不同量纲的指标统一到 [0, 100] 区间，便于加权求和。

**归一化公式**:
```
normalized = (value - min) / (max - min) * 100
```

**反向归一化**（如最大回撤）:
```
normalized = 100 - (value - min) / (max - min) * 100
```

**边界处理**:
- 超出范围的值截断到边界
- NaN/None 值视为0分

### B. 参考文献

- Sharpe Ratio: https://en.wikipedia.org/wiki/Sharpe_ratio
- Maximum Drawdown: https://en.wikipedia.org/wiki/Drawdown_(economics)
- Profit Factor: https://www.investopedia.com/terms/p/profit_loss_ratio.asp



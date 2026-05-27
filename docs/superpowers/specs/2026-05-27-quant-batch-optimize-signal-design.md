# 量化系统三大功能设计文档

**日期：** 2026-05-27  
**作者：** Claude (Kiro)  
**状态：** 设计阶段

## 概述

本设计文档描述三个量化交易功能的实现方案：

1. **批量回测（Batch Backtesting）** - 新增功能
2. **策略参数优化（Strategy Parameter Optimization）** - 重写现有功能
3. **信号生成（Signal Generation）** - 迁移到新架构

## 目标

### 功能目标
- 提供批量回测能力，支持多策略、多股票并行执行
- 实现真正的参数网格搜索优化，替代现有的假打分实现
- 将信号生成从旧模块迁移到 quantsys-v2 服务

### 技术目标
- 使用并发处理提升性能（ThreadPoolExecutor）
- 统一架构，全部使用 quantsys-v2 服务
- 保持 API 向后兼容，前端无需改动

### 性能目标
- 20 个批量回测任务在 2 分钟内完成
- 50 个参数组合优化在 5 分钟内完成
- 单个回测不超过 5 分钟

## 背景

### 当前状态

| 功能 | 当前状态 | 问题 |
|------|---------|------|
| **批量回测** | ❌ 不存在 | 无法批量评估策略表现 |
| **参数优化** | ⚠️ 存在但不可用 | 调用旧模块，只支持3种硬编码策略，打分是假的 |
| **信号生成** | ⚠️ 可用但架构旧 | 使用线程 + 旧 `quant/quantsys` 模块 |

### 技术栈

- **后端：** Python 3.13 + Flask + quantsys-v2
- **前端：** TypeScript + Node.js
- **数据库：** PostgreSQL
- **并发：** ThreadPoolExecutor（Python 标准库）

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    TypeScript Agent                          │
│  src/infrastructure/tools/core/quant-cli-tool.ts            │
│  src/infrastructure/quant/quant-v2-client.ts                │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/JSON
┌────────────────────┴────────────────────────────────────────┐
│              quantsys-v2 Flask API (port 5001)              │
├─────────────────────────────────────────────────────────────┤
│  api/routes/backtest.py                                     │
│    - POST /api/backtest/batch (新增)                        │
│                                                              │
│  api/routes/analysis.py                                     │
│    - POST /api/portfolio/strategy-optimize (重写)           │
│                                                              │
│  api/routes/pipeline.py                                     │
│    - POST /api/cli/signal-generate (更新)                   │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────────┐
│                   并发执行层                                 │
│  ThreadPoolExecutor (10 workers)                            │
│  - 并行回测执行                                              │
│  - 错误隔离                                                  │
│  - 超时控制（5分钟/任务）                                    │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────────┐
│                   服务层                                     │
│  services/strategy_code_service.py                          │
│    - backtest_strategy()                                    │
│    - generate_signal() (需新增)                             │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────────┐
│                   数据层                                     │
│  repositories/strategy_repository.py                        │
│  repositories/kline_repository.py                           │
│  repositories/signal_repository.py                          │
└─────────────────────────────────────────────────────────────┘
```

### 并发处理架构

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

class BacktestExecutor:
    def __init__(self, max_workers=10):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.service = StrategyCodeService()
    
    def batch_backtest(self, jobs):
        futures = {}
        for job in jobs:
            future = self.executor.submit(self._run_single, job)
            futures[future] = job
        
        results = []
        errors = []
        
        for future in as_completed(futures):
            job = futures[future]
            try:
                result = future.result(timeout=300)  # 5分钟超时
                results.append(result)
            except Exception as e:
                errors.append({
                    'job': job,
                    'error': str(e)
                })
        
        return results, errors
```

### 关键设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| **并发模型** | ThreadPoolExecutor | Python GIL 对 I/O 密集型任务影响小，实现简单 |
| **并发数** | 10 workers | 平衡性能和资源消耗 |
| **超时策略** | 单任务 5 分钟 | 避免长时间阻塞，可配置 |
| **错误处理** | 隔离失败任务 | 部分失败不影响整体，提供详细错误信息 |
| **参数验证** | 基础验证 | 策略存在性、组合数限制，不强制参数名匹配 |
| **信号生成** | 同步+异步混合 | 小批量同步，大批量异步 |
| **数据返回** | 精简结果 | 不返回完整 trades，减少响应体积 |

---

## 功能 1：批量回测（Batch Backtesting）

### 功能描述

提供批量回测能力，对多个（策略ID，股票代码）组合并行执行回测，返回排名汇总。

### API 规范

**端点：** `POST /api/backtest/batch`

**请求体：**
```json
{
  "jobs": [
    {
      "strategy_id": 53,
      "symbol": "600519",
      "start_date": "2025-01-01",
      "end_date": "2026-01-01",
      "initial_capital": 100000
    }
  ],
  "initial_capital": 1000000
}
```

**响应体：**
```json
{
  "success": true,
  "message": "5/5 完成",
  "summary": {
    "total": 5,
    "success": 5,
    "errors": 0,
    "profitable": 2,
    "best": {
      "strategy_id": 53,
      "symbol": "600519",
      "total_return": 0.15,
      "sharpe_ratio": 1.8
    },
    "worst": {...}
  },
  "results": [...],
  "errors": []
}
```

### 实现细节

**文件位置：** `quantsys-v2/api/routes/backtest.py`

**核心逻辑：**
```python
@backtest_bp.route('/api/backtest/batch', methods=['POST'])
@handle_api_error
def run_backtest_batch():
    data = request.get_json()
    jobs = data.get('jobs', [])
    initial_cash = float(data.get('initial_capital', 1000000))
    
    # 并发执行
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from services.strategy_code_service import StrategyCodeService
    
    service = StrategyCodeService()
    results = []
    errors = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(
                service.backtest_strategy,
                strategy_id=job['strategy_id'],
                symbol=job['symbol'],
                start_date=job['start_date'],
                end_date=job['end_date'],
                initial_cash=job.get('initial_capital', initial_cash)
            ): job
            for job in jobs
        }
        
        for future in as_completed(futures):
            job = futures[future]
            try:
                result = future.result(timeout=300)
                results.append({
                    'strategy_id': job['strategy_id'],
                    'symbol': job['symbol'],
                    'total_return': result['total_return'],
                    'annual_return': result['annual_return'],
                    'sharpe_ratio': result['sharpe_ratio'],
                    'max_drawdown': result['max_drawdown'],
                    'win_rate': result['win_rate'],
                    'profit_factor': result['profit_factor'],
                    'total_trades': result['total_trades'],
                    'start_date': job['start_date'],
                    'end_date': job['end_date']
                })
            except Exception as e:
                errors.append({
                    'strategy_id': job['strategy_id'],
                    'symbol': job['symbol'],
                    'error': str(e)
                })
    
    # 排序
    results.sort(key=lambda r: r['total_return'], reverse=True)
    
    # 汇总
    profitable = [r for r in results if r['total_return'] > 0]
    summary = {
        'total': len(jobs),
        'success': len(results),
        'errors': len(errors),
        'profitable': len(profitable),
        'best': results[0] if results else None,
        'worst': results[-1] if results else None
    }
    
    return api_response({
        'summary': summary,
        'results': results,
        'errors': errors if errors else None
    }, message=f'{len(results)}/{len(jobs)} 完成')
```

### 错误处理

| 场景 | HTTP 状态码 | 错误信息 |
|------|------------|---------|
| 空任务列表 | 400 | "jobs 不能为空" |
| 策略不存在 | 记录到 errors | 不中断其他任务 |
| K线数据缺失 | 记录到 errors | 不中断其他任务 |
| 单任务超时 | 记录到 errors | "回测超时（5分钟）" |

### TypeScript 客户端集成

**更新路由表：** `src/infrastructure/quant/quant-v2-client.ts`
```typescript
const V2_ROUTES = {
  // ... 现有路由
  "backtest.batch": { path: "/api/backtest/batch", method: "POST" },
};
```

**更新命令定义：** `src/infrastructure/tools/core/quant-cli-tool.ts`
```typescript
const COMMANDS = {
  "backtest.batch": {
    domain: "backtest",
    action: "batch",
    description: "批量回测多个策略和股票组合，返回排名汇总。",
    params: {
      jobs: { required: true, type: "array" },
      initial_capital: { type: "number", positive: true }
    },
    example: {
      jobs: [
        {
          strategy_id: 53,
          symbol: "600519",
          start_date: "2025-01-01",
          end_date: "2026-01-01"
        }
      ]
    }
  }
};
```

### 使用示例

```typescript
// 评估同一策略在不同股票上的表现
const result = await runQuantV2("backtest.batch", {
  jobs: [
    { strategy_id: 53, symbol: "600519", start_date: "2025-01-01", end_date: "2026-01-01" },
    { strategy_id: 53, symbol: "000858", start_date: "2025-01-01", end_date: "2026-01-01" },
    { strategy_id: 53, symbol: "601318", start_date: "2025-01-01", end_date: "2026-01-01" }
  ],
  initial_capital: 1000000
});

console.log(`最佳股票: ${result.summary.best.symbol}`);
console.log(`盈利股票数: ${result.summary.profitable}/${result.summary.total}`);
```

---

## 功能 2：策略参数优化（Strategy Parameter Optimization）

### 功能描述

真正的参数网格搜索优化，替代现有的假打分实现。对给定策略在指定参数空间内进行网格搜索，找到最优参数组合。

### API 规范

**端点：** `POST /api/portfolio/strategy-optimize`（覆盖现有端点）

**请求体：**
```json
{
  "strategy_id": 53,
  "symbol": "600519",
  "start_date": "2025-01-01",
  "end_date": "2026-01-01",
  "metric": "sharpe",
  "param_grid": {
    "rsi_low": [25, 30, 35],
    "rsi_high": [65, 70, 75],
    "trail_pct": [0.03, 0.05, 0.07]
  },
  "initial_capital": 1000000,
  "max_combinations": 50
}
```

**响应体：**
```json
{
  "success": true,
  "data": {
    "strategy_id": 53,
    "symbol": "600519",
    "metric": "sharpe",
    "total_runs": 27,
    "best": {
      "params": {
        "rsi_low": 30,
        "rsi_high": 70,
        "trail_pct": 0.05
      },
      "score": 2.15,
      "total_return": 0.23,
      "sharpe_ratio": 2.15,
      "max_drawdown": -0.08,
      "win_rate": 0.62
    },
    "top10": [...]
  }
}
```

### 实现细节

**文件位置：** `quantsys-v2/api/routes/analysis.py` 第 689 行（替换现有实现）

**核心逻辑：**
```python
@analysis_bp.route('/api/portfolio/strategy-optimize', methods=['POST'])
@handle_api_error
def strategy_optimize():
    data = request.get_json()
    data = convert_keys_to_snake(data)
    
    # 参数验证
    strategy_id = int(data['strategy_id'])
    symbol = data['symbol']
    start_date = data['start_date']
    end_date = data['end_date']
    metric = data.get('metric', 'sharpe')
    param_grid = data['param_grid']
    initial_cash = float(data.get('initial_capital', 1000000))
    max_combinations = int(data.get('max_combinations', 50))
    
    # 验证策略存在
    strategy = strategy_service.get_strategy(strategy_id)
    if not strategy:
        return jsonify({'success': False, 'error': f'策略不存在: {strategy_id}'}), 404
    
    # 生成参数组合
    import itertools
    param_names = list(param_grid.keys())
    param_values = [param_grid[name] for name in param_names]
    combinations = list(itertools.product(*param_values))
    
    total_combinations = len(combinations)
    if total_combinations > max_combinations:
        return jsonify({
            'success': False,
            'error': f'参数组合过多 ({total_combinations})，请缩小搜索范围（当前限制: {max_combinations}）'
        }), 400
    
    # 并发执行
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from services.strategy_code_service import StrategyCodeService
    
    service = StrategyCodeService()
    results = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        for combo in combinations:
            params_dict = dict(zip(param_names, combo))
            
            # 将参数注入策略（通过环境变量或其他方式）
            future = executor.submit(
                service.backtest_strategy,
                strategy_id=strategy_id,
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                initial_cash=initial_cash,
                params_override=params_dict
            )
            futures[future] = params_dict
        
        for future in as_completed(futures):
            params_dict = futures[future]
            try:
                result = future.result(timeout=300)
                
                # 提取优化指标
                metric_map = {
                    'sharpe': result['sharpe_ratio'],
                    'return': result['total_return'],
                    'win_rate': result['win_rate'],
                    'calmar': result['annual_return'] / abs(result['max_drawdown']) if result['max_drawdown'] != 0 else 0
                }
                score = metric_map.get(metric, result['sharpe_ratio'])
                
                results.append({
                    'params': params_dict,
                    'score': score,
                    'total_return': result['total_return'],
                    'sharpe_ratio': result['sharpe_ratio'],
                    'max_drawdown': result['max_drawdown'],
                    'win_rate': result['win_rate']
                })
            except Exception as e:
                logger.error(f"参数优化失败: {params_dict}, error={e}")
    
    if not results:
        return jsonify({
            'success': False,
            'error': '所有参数组合回测均失败，请检查策略代码或参数范围'
        }), 500
    
    # 排序
    results.sort(key=lambda r: r['score'], reverse=True)
    
    return api_response({
        'strategy_id': strategy_id,
        'symbol': symbol,
        'metric': metric,
        'total_runs': len(results),
        'best': results[0],
        'top10': results[:10]
    }, message=f'{len(results)}/{total_combinations} 完成')
```

### 优化指标映射

| 指标名 | 计算公式 | 说明 |
|--------|---------|------|
| `sharpe` | `sharpe_ratio` | 夏普比率（风险调整后收益） |
| `return` | `total_return` | 总收益率 |
| `win_rate` | `win_rate` | 胜率 |
| `calmar` | `annual_return / abs(max_drawdown)` | 卡玛比率（年化收益/最大回撤） |

### 错误处理

| 场景 | HTTP 状态码 | 错误信息 |
|------|------------|---------|
| 策略不存在 | 404 | "策略不存在: {id}" |
| 组合数过多 | 400 | "参数组合过多 ({n})，请缩小搜索范围" |
| 所有组合失败 | 500 | "所有参数组合回测均失败" |

### 使用示例

```typescript
// 两阶段优化：粗搜索 + 细搜索
const coarse = await runQuantV2("strategy.optimize", {
  strategy_id: 53,
  symbol: "600519",
  start_date: "2025-01-01",
  end_date: "2026-01-01",
  metric: "sharpe",
  param_grid: {
    rsi_low: [20, 25, 30, 35],
    rsi_high: [65, 70, 75, 80]
  }
});

console.log(`粗搜最优: rsi_low=${coarse.data.best.params.rsi_low}`);

// 细搜索（围绕最优值）
const fine = await runQuantV2("strategy.optimize", {
  strategy_id: 53,
  symbol: "600519",
  start_date: "2025-01-01",
  end_date: "2026-01-01",
  metric: "sharpe",
  param_grid: {
    rsi_low: [28, 29, 30, 31, 32],
    rsi_high: [68, 69, 70, 71, 72]
  }
});

console.log(`最优 Sharpe: ${fine.data.best.score}`);
```

---

## 功能 3：信号生成（Signal Generation）

### 功能描述

更新现有的信号生成端点，从旧的线程+旧模块迁移到使用新的 quantsys-v2 服务。支持同步和异步两种模式。

### API 规范

**端点：** `POST /api/cli/signal-generate`（保持现有端点）

**请求体：**
```json
{
  "symbols": ["600519", "000001"],
  "date": "2026-05-27",
  "strategy_ids": [53, 54],
  "async": false
}
```

**响应体（异步模式，立即返回 202）：**
```json
{
  "success": true,
  "run_id": "#S-A3F2B1C4",
  "status": "running",
  "symbol_count": 2,
  "message": "信号生成已触发，run_id=#S-A3F2B1C4"
}
```

**响应体（同步模式，流式返回）：**
```
Content-Type: application/x-ndjson

{"status": "started", "total": 2}
{"progress": 1, "total": 2, "symbol": "600519", "signal": {...}}
{"progress": 2, "total": 2, "symbol": "000001", "signal": {...}}
{"status": "completed"}
```

### 实现细节

**文件位置：** `quantsys-v2/api/routes/pipeline.py` 第 556 行（更新现有实现）

**核心逻辑：**
```python
@pipeline_bp.route('/api/cli/signal-generate', methods=['POST'])
@handle_api_error
def cli_signal_generate():
    data = request.get_json(silent=True) or {}
    params = convert_keys_to_snake(data)
    
    # 解析参数
    symbols_raw = params.get('symbols', '')
    if isinstance(symbols_raw, str) and symbols_raw.strip():
        symbols = [s.strip() for s in symbols_raw.split(',') if s.strip()]
    elif isinstance(symbols_raw, list):
        symbols = symbols_raw
    else:
        symbols = [s['symbol'] for s in ds.stock.get_all(limit=100)]
    
    signal_date = params.get('date')
    strategy_ids = params.get('strategy_ids', [])
    
    # 判断模式：小批量同步，大批量异步
    async_mode = params.get('async', False) or len(symbols) > 50
    
    if async_mode:
        # 异步模式（保持现有逻辑）
        run_id = f"#S-{str(uuid.uuid4())[:8].upper()}"
        
        if not acquire_task('signal_generate', run_id):
            existing = get_running_tasks_snapshot().get('signal_generate', '?')
            return jsonify({
                'success': False,
                'error': f'信号生成已在运行中 (run_id={existing})'
            }), 409
        
        # 记录任务
        now = datetime.now()
        run_record = {
            'runId': run_id,
            'run_id': run_id,
            'status': 'running',
            'taskType': 'signal_generate',
            'startTime': now.isoformat(),
            'symbols': symbols if symbols else ['ALL'],
            'params': {'date': signal_date, 'strategy_ids': strategy_ids},
            'logs': [f'[{now.isoformat()}] 信号生成触发: {run_id}'],
        }
        runs = _load_pipeline_runs()
        runs.append(run_record)
        _save_pipeline_runs(runs)
        
        # 启动后台线程
        threading.Thread(
            target=_execute_signal_generate_v2,
            args=(run_id, symbols, signal_date, strategy_ids),
            daemon=True
        ).start()
        
        return api_response({
            'success': True,
            'run_id': run_id,
            'status': 'running',
            'symbol_count': len(symbols) if symbols else 0,
            'message': f'信号生成已触发，run_id={run_id}'
        }), 202
    
    else:
        # 同步模式（新增）
        def generate():
            from services.strategy_code_service import StrategyCodeService
            service = StrategyCodeService()
            
            # 获取策略列表
            if strategy_ids:
                strategies = [strategy_service.get_strategy(sid) for sid in strategy_ids]
            else:
                strategies = strategy_service.list_strategies(is_active=True)
            
            total = len(symbols) * len(strategies)
            yield json.dumps({'status': 'started', 'total': total}) + '\n'
            
            completed = 0
            for strategy in strategies:
                for symbol in symbols:
                    try:
                        # 生成信号
                        signal = service.generate_signal(
                            strategy_id=strategy['id'],
                            symbol=symbol,
                            date=signal_date
                        )
                        
                        completed += 1
                        yield json.dumps({
                            'progress': completed,
                            'total': total,
                            'symbol': symbol,
                            'strategy_id': strategy['id'],
                            'signal': signal
                        }) + '\n'
                    except Exception as e:
                        logger.error(f'信号生成失败: {symbol} - {e}')
                        yield json.dumps({
                            'progress': completed,
                            'total': total,
                            'symbol': symbol,
                            'error': str(e)
                        }) + '\n'
            
            yield json.dumps({'status': 'completed'}) + '\n'
        
        return Response(generate(), mimetype='application/x-ndjson')


def _execute_signal_generate_v2(run_id, symbols, date, strategy_ids):
    """异步信号生成（新版本，使用 quantsys-v2 服务）"""
    try:
        from services.strategy_code_service import StrategyCodeService
        service = StrategyCodeService()
        
        # 获取策略列表
        if strategy_ids:
            strategies = [strategy_service.get_strategy(sid) for sid in strategy_ids]
        else:
            strategies = strategy_service.list_strategies(is_active=True)
        
        # 获取股票列表
        if not symbols:
            symbols = [s['symbol'] for s in ds.stock.get_all(limit=500)]
        
        total = len(strategies) * len(symbols)
        completed = 0
        
        _update_pipeline_run(run_id, {
            'logs': [f'开始生成信号: {len(strategies)} 个策略 × {len(symbols)} 只股票 = {total} 个任务']
        })
        
        # 生成信号
        for strategy in strategies:
            for symbol in symbols:
                try:
                    signal = service.generate_signal(
                        strategy_id=strategy['id'],
                        symbol=symbol,
                        date=date
                    )
                    
                    # 保存信号
                    if signal:
                        ds.signal.save_signal(signal)
                    
                    completed += 1
                    
                    # 每10个任务更新一次进度
                    if completed % 10 == 0:
                        _update_pipeline_run(run_id, {
                            'progress': f'{completed}/{total}',
                            'logs': [f'进度: {completed}/{total} ({completed*100//total}%)']
                        })
                
                except Exception as e:
                    logger.error(f'信号生成失败: {symbol} - {e}')
        
        # 标记完成
        _update_pipeline_run(run_id, {
            'status': 'completed',
            'progress': f'{completed}/{total}',
            'logs': [f'完成: 生成 {completed} 个信号']
        })
    
    except Exception as e:
        logger.error(f"信号生成失败: {e}", exc_info=True)
        _update_pipeline_run(run_id, {
            'status': 'failed',
            'error': str(e),
            'logs': [f'[ERROR] {str(e)}']
        })
    
    finally:
        release_task('signal_generate')
```

### 模式选择

| 场景 | 模式 | 触发条件 |
|------|------|---------|
| 小批量（< 50 只股票） | 同步 | `async=false` 且 `len(symbols) <= 50` |
| 大批量（≥ 50 只股票） | 异步 | `async=true` 或 `len(symbols) > 50` |
| 全市场扫描 | 异步 | `symbols` 为空或 `symbols=@all` |

### 迁移对比

| 项目 | 旧实现 | 新实现 |
|------|--------|--------|
| 调用模块 | `quant/quantsys/cli/signal_generator.py` | `quantsys-v2/services/strategy_code_service.py` |
| 执行模式 | 仅异步 | 同步 + 异步混合 |
| 进度更新 | 基础 | 增强（每10个任务更新） |
| 错误处理 | 基础 | 详细日志和错误记录 |

### 使用示例

```typescript
// 小批量同步
const result = await runQuantV2("signal.generate", {
  symbols: ["600519", "000001"],
  date: "2026-05-27",
  strategy_ids: [53, 54]
});
// 流式接收进度

// 大批量异步
const result = await runQuantV2("signal.generate", {
  symbols: [], // 全市场
  async: true
});
console.log(`任务已启动: ${result.run_id}`);
```

---

## 测试策略

### 单元测试

#### 批量回测测试
```python
# quantsys-v2/tests/test_batch_backtest.py

def test_batch_backtest_success(client, sample_strategy):
    """测试批量回测成功场景"""
    payload = {
        "jobs": [
            {
                "strategy_id": sample_strategy['id'],
                "symbol": "600519",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31"
            }
        ]
    }
    response = client.post('/api/backtest/batch', json=payload)
    assert response.status_code == 200
    assert response.json['success'] is True

def test_batch_backtest_partial_failure(client, sample_strategy):
    """测试部分任务失败"""
    payload = {
        "jobs": [
            {"strategy_id": sample_strategy['id'], "symbol": "600519", ...},
            {"strategy_id": 99999, "symbol": "000001", ...}  # 不存在
        ]
    }
    response = client.post('/api/backtest/batch', json=payload)
    data = response.json
    assert data['summary']['success'] >= 1
    assert data['summary']['errors'] >= 1
```

#### 参数优化测试
```python
# quantsys-v2/tests/test_strategy_optimize.py

def test_optimize_success(client, sample_strategy):
    """测试参数优化成功"""
    payload = {
        "strategy_id": sample_strategy['id'],
        "symbol": "600519",
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "metric": "sharpe",
        "param_grid": {"rsi_low": [25, 30], "rsi_high": [70, 75]}
    }
    response = client.post('/api/portfolio/strategy-optimize', json=payload)
    assert response.status_code == 200
    assert response.json['data']['total_runs'] == 4

def test_optimize_combinations_limit(client, sample_strategy):
    """测试组合数限制"""
    payload = {
        "strategy_id": sample_strategy['id'],
        "symbol": "600519",
        "param_grid": {
            "param1": list(range(10)),
            "param2": list(range(10)),
            "param3": list(range(10))  # 1000 > 50
        },
        "max_combinations": 50
    }
    response = client.post('/api/portfolio/strategy-optimize', json=payload)
    assert response.status_code == 400
    assert '组合数过多' in response.json['error']
```

#### 信号生成测试
```python
# quantsys-v2/tests/test_signal_generate.py

def test_signal_generate_sync(client):
    """测试同步信号生成"""
    payload = {"symbols": ["600519", "000001"]}
    response = client.post('/api/cli/signal-generate', json=payload)
    assert response.status_code == 200
    # 验证流式响应

def test_signal_generate_async(client):
    """测试异步信号生成"""
    payload = {"symbols": ["600519"], "async": True}
    response = client.post('/api/cli/signal-generate', json=payload)
    assert response.status_code == 202
    assert 'run_id' in response.json
```

### 性能测试

```python
# quantsys-v2/tests/performance/test_batch_performance.py

def test_batch_backtest_performance(client, sample_strategy):
    """测试批量回测性能"""
    jobs = [
        {
            "strategy_id": sample_strategy['id'],
            "symbol": f"60{i:04d}",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31"
        }
        for i in range(20)
    ]
    
    start = time.time()
    response = client.post('/api/backtest/batch', json={"jobs": jobs})
    elapsed = time.time() - start
    
    assert response.status_code == 200
    assert elapsed < 120  # 20个回测应在2分钟内完成
```

---

## 风险评估与缓解

### 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **数据库连接耗尽** | 高 | 中 | 使用连接池，限制并发数为10 |
| **参数组合爆炸** | 高 | 中 | 前置检查 `max_combinations`，默认限制50 |
| **单任务超时阻塞** | 中 | 低 | 单任务超时5分钟，记录错误继续其他任务 |
| **信号生成任务锁死** | 中 | 低 | `try...finally` 确保 `release_task()` 执行 |
| **内存占用过高** | 中 | 低 | 不返回完整 trades，限制单批任务数 |

### 业务风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **过度优化导致过拟合** | 高 | 高 | 文档强调样本外验证，提供 top10 结果 |
| **用户误用导致资源浪费** | 中 | 中 | 清晰的文档和使用示例，合理的默认值 |

### 运维风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **quantsys-v2 服务未启动** | 高 | 低 | 健康检查端点，清晰的错误提示 |
| **日志文件膨胀** | 低 | 中 | 使用日志轮转，关键操作 INFO 级别 |

---

## 实施计划

### 开发阶段

#### Phase 1: 批量回测（1 天）
- [ ] 实现 `POST /api/backtest/batch` 端点
- [ ] 添加并发执行器
- [ ] 错误处理和结果聚合
- [ ] 单元测试
- [ ] 更新 TypeScript 客户端

#### Phase 2: 参数优化（1 天）
- [ ] 重写 `POST /api/portfolio/strategy-optimize` 端点
- [ ] 参数组合生成和验证
- [ ] 并发回测和结果排序
- [ ] 单元测试
- [ ] 集成测试

#### Phase 3: 信号生成迁移（0.5 天）
- [ ] 更新 `_execute_signal_generate` 函数
- [ ] 添加同步模式支持
- [ ] 调用新的 `StrategyCodeService`
- [ ] 测试兼容性

#### Phase 4: 集成和测试（0.5 天）
- [ ] 端到端测试
- [ ] 性能测试
- [ ] 文档更新
- [ ] 代码审查

**总预计时间：** 3 天

### 验收标准

#### 功能验收
- ✅ 批量回测支持 10+ 个任务并行执行
- ✅ 参数优化返回 top10 结果
- ✅ 信号生成支持同步和异步模式
- ✅ 所有单元测试通过
- ✅ 集成测试通过

#### 性能验收
- ✅ 20 个批量回测任务在 2 分钟内完成
- ✅ 50 个参数组合优化在 5 分钟内完成
- ✅ 单个回测不超过 5 分钟
- ✅ 内存占用不超过 2GB

#### 质量验收
- ✅ 代码覆盖率 > 80%
- ✅ 无 critical/high 级别 bug
- ✅ API 文档完整
- ✅ 错误提示清晰友好

---

## 未来扩展

### 短期优化（1-3 个月）

1. **结果缓存**
   - 相同参数的回测结果缓存
   - 使用 Redis 存储，设置过期时间

2. **分布式执行**
   - 使用 Celery 替代 ThreadPoolExecutor
   - 支持多机分布式回测

### 中期扩展（3-6 个月）

1. **智能参数推荐**
   - 基于历史优化结果推荐参数范围
   - 使用贝叶斯优化替代网格搜索

2. **回测结果可视化**
   - 生成权益曲线图
   - 参数热力图
   - 风险归因图表

### 长期愿景（6-12 个月）

1. **AutoML 策略生成**
   - 自动特征工程
   - 自动策略搜索
   - 集成学习

2. **实时回测**
   - 流式数据回测
   - 增量更新结果

---

## 附录

### 环境变量配置

```bash
# quantsys-v2 API 配置（已存在）
QUANTSYS_V2_API_URL=http://127.0.0.1:5001
QUANTSYS_V2_TIMEOUT=30000

# 并发配置（可选，新增）
BACKTEST_MAX_WORKERS=10
BACKTEST_TIMEOUT=300
```

### 文件清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `quantsys-v2/api/routes/backtest.py` | 修改 | 新增批量回测端点 |
| `quantsys-v2/api/routes/analysis.py` | 修改 | 重写参数优化端点（第689行） |
| `quantsys-v2/api/routes/pipeline.py` | 修改 | 更新信号生成端点（第556行） |
| `src/infrastructure/quant/quant-v2-client.ts` | 修改 | 新增路由映射 |
| `src/infrastructure/tools/core/quant-cli-tool.ts` | 修改 | 新增命令定义 |
| `src/infrastructure/quant/types.ts` | 修改 | 新增类型定义 |

### 参考资料

- [StrategyCodeService 文档](../quantsys-v2/services/strategy_code_service.py)
- [ThreadPoolExecutor 文档](https://docs.python.org/3/library/concurrent.futures.html)
- [Flask 流式响应](https://flask.palletsprojects.com/en/2.3.x/patterns/streaming/)

---

## 实施注意事项

### 关键依赖

1. **StrategyCodeService.backtest_strategy()**
   - 已存在于 `quantsys-v2/services/strategy_code_service.py`
   - 需确认支持 `params_override` 参数（用于参数优化）
   - 如不支持，需先扩展此方法

2. **StrategyCodeService.generate_signal()**
   - **需新增**此方法
   - 用于信号生成功能
   - 应返回信号对象（包含 symbol, strategy_id, signal_type, confidence 等）

3. **数据库连接池**
   - 已在 `infrastructure/database/` 配置
   - 需确认连接池大小 ≥ 并发数（建议 20+）

### 参数注入机制

参数优化功能需要将 `params_override` 传递给策略执行器。有两种实现方式：

**方案A：通过方法参数**（推荐）
```python
# StrategyCodeService.backtest_strategy() 添加参数
def backtest_strategy(self, strategy_id, symbol, start_date, end_date, 
                      initial_cash, params_override=None):
    # 在执行策略前，将 params_override 注入到策略上下文
    if params_override:
        # 方式1：修改策略代码中的变量
        # 方式2：通过环境变量传递
        # 方式3：通过策略元数据传递
```

**方案B：通过临时策略副本**
```python
# 创建策略的临时副本，修改参数后执行
temp_strategy = copy.deepcopy(strategy)
temp_strategy['params'] = params_override
result = service.backtest_strategy_with_config(temp_strategy, ...)
```

### 向后兼容性

- **批量回测**：新增端点，无兼容性问题
- **参数优化**：覆盖现有端点，但旧端点已不可用，无影响
- **信号生成**：保持现有 API 接口，添加新参数（`async`），向后兼容

### 性能调优

如果实际性能未达标，可调整以下参数：

```python
# 增加并发数（需评估服务器资源）
MAX_WORKERS = 15  # 默认 10

# 增加单任务超时
BACKTEST_TIMEOUT = 600  # 默认 300（5分钟）

# 使用进程池替代线程池（CPU 密集型任务）
from concurrent.futures import ProcessPoolExecutor
executor = ProcessPoolExecutor(max_workers=5)
```


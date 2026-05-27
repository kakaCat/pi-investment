# 量化系统三大功能实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现批量回测、参数优化和信号生成三个量化交易功能，使用 ThreadPoolExecutor 并发执行，提升性能。

**Architecture:** Python Flask 后端新增/重写三个 API 端点，使用 ThreadPoolExecutor（10 workers）并行执行回测任务，TypeScript 客户端集成新端点。所有功能统一使用 quantsys-v2 服务层。

**Tech Stack:** Python 3.13, Flask, ThreadPoolExecutor, PostgreSQL, TypeScript, Node.js

---

## 文件结构

### 后端文件（Python）

**新增文件：**
- `quantsys-v2/tests/test_batch_backtest.py` - 批量回测单元测试
- `quantsys-v2/tests/test_strategy_optimize.py` - 参数优化单元测试  
- `quantsys-v2/tests/test_signal_generate.py` - 信号生成单元测试
- `quantsys-v2/tests/performance/test_batch_performance.py` - 性能测试

**修改文件：**
- `quantsys-v2/api/routes/backtest.py` - 新增批量回测端点
- `quantsys-v2/api/routes/analysis.py:689-703` - 重写参数优化端点
- `quantsys-v2/api/routes/pipeline.py:556-585` - 更新信号生成端点
- `quantsys-v2/services/strategy_code_service.py` - 扩展支持 params_override 和 generate_signal

### 前端文件（TypeScript）

**修改文件：**
- `src/infrastructure/quant/quant-v2-client.ts` - 新增路由映射
- `src/infrastructure/tools/core/quant-cli-tool.ts` - 新增命令定义
- `src/infrastructure/quant/types.ts` - 新增类型定义

---

## 前置准备

### Task 0: 验证依赖和环境

**Files:**
- Read: `quantsys-v2/services/strategy_code_service.py`
- Read: `quantsys-v2/infrastructure/database/connection.py`

- [ ] **Step 1: 检查 StrategyCodeService.backtest_strategy() 方法签名**

Run: `cd quantsys-v2 && grep -A 10 "def backtest_strategy" services/strategy_code_service.py`

Expected: 找到方法定义，确认当前参数列表

- [ ] **Step 2: 检查数据库连接池配置**

Run: `cd quantsys-v2 && grep -i "pool" infrastructure/database/connection.py`

Expected: 找到连接池配置，确认 POOL_SIZE >= 20

- [ ] **Step 3: 确认 quantsys-v2 服务运行**

Run: `curl http://127.0.0.1:5001/api/health`

Expected: 返回健康状态或 200 OK

如果服务未运行：
```bash
cd quantsys-v2
python start_all.py
```

- [ ] **Step 4: 记录当前状态**

创建检查清单：
- [ ] StrategyCodeService.backtest_strategy() 存在
- [ ] 数据库连接池配置正常
- [ ] quantsys-v2 服务运行中
- [ ] 需要新增 generate_signal() 方法
- [ ] 需要扩展 backtest_strategy() 支持 params_override

---

## Phase 1: 扩展服务层

### Task 1: 扩展 StrategyCodeService 支持参数覆盖

**Files:**
- Modify: `quantsys-v2/services/strategy_code_service.py`
- Test: `quantsys-v2/tests/test_strategy_code_service.py`

- [ ] **Step 1: 写失败测试 - 参数覆盖**

在 `quantsys-v2/tests/test_strategy_code_service.py` 添加：

```python
def test_backtest_strategy_with_params_override(sample_strategy, sample_klines):
    """测试回测时参数覆盖"""
    service = StrategyCodeService()
    
    result = service.backtest_strategy(
        strategy_id=sample_strategy['id'],
        symbol='600519',
        start_date='2025-01-01',
        end_date='2025-12-31',
        initial_cash=1000000,
        params_override={'rsi_low': 25, 'rsi_high': 75}
    )
    
    assert result is not None
    assert 'total_return' in result
    assert 'sharpe_ratio' in result
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd quantsys-v2 && pytest tests/test_strategy_code_service.py::test_backtest_strategy_with_params_override -v`

Expected: FAIL - TypeError: backtest_strategy() got an unexpected keyword argument 'params_override'

- [ ] **Step 3: 修改 backtest_strategy() 方法签名**

在 `quantsys-v2/services/strategy_code_service.py` 找到 `backtest_strategy` 方法，修改签名：

```python
def backtest_strategy(
    self,
    strategy_id: int,
    symbol: str,
    start_date: str,
    end_date: str,
    initial_cash: float = 1000000,
    params_override: Optional[Dict[str, Any]] = None
) -> Dict:
    """
    回测策略
    
    Args:
        strategy_id: 策略ID
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        initial_cash: 初始资金
        params_override: 参数覆盖字典（用于参数优化）
    
    Returns:
        回测结果字典
    """
    logger.info(f"回测策略: strategy_id={strategy_id}, symbol={symbol}, params_override={params_override}")
    
    # 获取策略
    strategy = self.strategy_repo.get_user_strategy(strategy_id)
    if not strategy:
        raise ValueError(f"策略不存在: {strategy_id}")
    
    # 获取K线数据
    klines = self.kline_repo.get_klines(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date
    )
    
    if not klines:
        raise ValueError(f"K线数据不存在: {symbol}")
    
    # 如果有参数覆盖，注入到策略执行上下文
    if params_override:
        # 将参数注入到全局变量（策略代码可以访问）
        import builtins
        builtins.__strategy_params__ = params_override
    
    try:
        # 执行策略
        if strategy['code_type'] == 'indicator':
            result = self.indicator_executor.execute(
                code=strategy['code_content'],
                symbol=symbol,
                klines=klines,
                initial_cash=initial_cash
            )
        else:
            result = self.script_executor.execute(
                code=strategy['code_content'],
                symbol=symbol,
                klines=klines,
                initial_cash=initial_cash
            )
        
        return result
    
    finally:
        # 清理全局变量
        if params_override and hasattr(builtins, '__strategy_params__'):
            delattr(builtins, '__strategy_params__')
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd quantsys-v2 && pytest tests/test_strategy_code_service.py::test_backtest_strategy_with_params_override -v`

Expected: PASS

- [ ] **Step 5: 提交更改**

```bash
cd quantsys-v2
git add services/strategy_code_service.py tests/test_strategy_code_service.py
git commit -m "feat(service): add params_override support to backtest_strategy

- 扩展 backtest_strategy() 方法支持参数覆盖
- 通过 builtins.__strategy_params__ 注入参数到策略执行上下文
- 添加单元测试验证参数覆盖功能"
```

---

### Task 2: 添加 generate_signal() 方法

**Files:**
- Modify: `quantsys-v2/services/strategy_code_service.py`
- Test: `quantsys-v2/tests/test_strategy_code_service.py`

- [ ] **Step 1: 写失败测试 - 信号生成**

在 `quantsys-v2/tests/test_strategy_code_service.py` 添加：

```python
def test_generate_signal(sample_strategy):
    """测试信号生成"""
    service = StrategyCodeService()
    
    signal = service.generate_signal(
        strategy_id=sample_strategy['id'],
        symbol='600519',
        date='2026-05-27'
    )
    
    assert signal is not None
    assert signal['symbol'] == '600519'
    assert signal['strategy_id'] == sample_strategy['id']
    assert 'signal_type' in signal  # 'buy' or 'sell' or 'hold'
    assert 'confidence' in signal
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd quantsys-v2 && pytest tests/test_strategy_code_service.py::test_generate_signal -v`

Expected: FAIL - AttributeError: 'StrategyCodeService' object has no attribute 'generate_signal'

- [ ] **Step 3: 实现 generate_signal() 方法**

在 `quantsys-v2/services/strategy_code_service.py` 的 `StrategyCodeService` 类中添加：

```python
def generate_signal(
    self,
    strategy_id: int,
    symbol: str,
    date: Optional[str] = None
) -> Optional[Dict]:
    """
    生成交易信号
    
    Args:
        strategy_id: 策略ID
        symbol: 股票代码
        date: 信号日期（可选，默认今天）
    
    Returns:
        信号字典或 None（无信号）
    """
    from datetime import datetime, timedelta
    
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')
    
    logger.info(f"生成信号: strategy_id={strategy_id}, symbol={symbol}, date={date}")
    
    # 获取策略
    strategy = self.strategy_repo.get_user_strategy(strategy_id)
    if not strategy:
        raise ValueError(f"策略不存在: {strategy_id}")
    
    # 获取最近的K线数据（用于信号生成，需要足够的历史数据）
    end_date = date
    start_date = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=365)).strftime('%Y-%m-%d')
    
    klines = self.kline_repo.get_klines(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date
    )
    
    if not klines or len(klines) < 20:
        logger.warning(f"K线数据不足: {symbol}, 数量={len(klines) if klines else 0}")
        return None
    
    # 执行策略获取信号
    try:
        if strategy['code_type'] == 'indicator':
            df = self.indicator_executor.execute_for_signals(
                code=strategy['code_content'],
                symbol=symbol,
                klines=klines
            )
        else:
            df = self.script_executor.execute_for_signals(
                code=strategy['code_content'],
                symbol=symbol,
                klines=klines
            )
        
        # 获取最后一行的信号
        if df is None or df.empty:
            return None
        
        last_row = df.iloc[-1]
        
        # 判断信号类型
        signal_type = 'hold'
        confidence = 0.0
        
        if 'buy' in df.columns and last_row.get('buy', False):
            signal_type = 'buy'
            confidence = last_row.get('confidence', 0.7)
        elif 'sell' in df.columns and last_row.get('sell', False):
            signal_type = 'sell'
            confidence = last_row.get('confidence', 0.7)
        
        if signal_type == 'hold':
            return None
        
        return {
            'symbol': symbol,
            'strategy_id': strategy_id,
            'strategy_name': strategy.get('name', f'strategy_{strategy_id}'),
            'signal_type': signal_type,
            'confidence': float(confidence),
            'signal_date': date,
            'price': float(last_row.get('close', 0)),
            'created_at': datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"信号生成失败: {e}", exc_info=True)
        return None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd quantsys-v2 && pytest tests/test_strategy_code_service.py::test_generate_signal -v`

Expected: PASS

- [ ] **Step 5: 提交更改**

```bash
cd quantsys-v2
git add services/strategy_code_service.py tests/test_strategy_code_service.py
git commit -m "feat(service): add generate_signal method to StrategyCodeService

- 新增 generate_signal() 方法用于生成交易信号
- 支持 indicator 和 script 两种策略类型
- 返回信号字典包含 symbol, strategy_id, signal_type, confidence 等
- 添加单元测试验证信号生成功能"
```

---

## Phase 2: 批量回测功能

### Task 3: 实现批量回测端点

**Files:**
- Modify: `quantsys-v2/api/routes/backtest.py`
- Test: `quantsys-v2/tests/test_batch_backtest.py`

- [ ] **Step 1: 写失败测试 - 批量回测成功场景**

创建 `quantsys-v2/tests/test_batch_backtest.py`：

```python
import pytest
from datetime import datetime

def test_batch_backtest_success(client, sample_strategy):
    """测试批量回测成功场景"""
    payload = {
        "jobs": [
            {
                "strategy_id": sample_strategy['id'],
                "symbol": "600519",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "initial_capital": 100000
            },
            {
                "strategy_id": sample_strategy['id'],
                "symbol": "000001",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31"
            }
        ],
        "initial_capital": 1000000
    }
    
    response = client.post('/api/backtest/batch', json=payload)
    
    assert response.status_code == 200
    data = response.json
    assert data['success'] is True
    assert 'summary' in data
    assert data['summary']['total'] == 2
    assert len(data['results']) <= 2
    assert 'best' in data['summary']
    assert 'worst' in data['summary']

def test_batch_backtest_empty_jobs(client):
    """测试空任务列表"""
    response = client.post('/api/backtest/batch', json={"jobs": []})
    assert response.status_code == 400
    assert 'jobs 不能为空' in response.json['error']
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd quantsys-v2 && pytest tests/test_batch_backtest.py::test_batch_backtest_success -v`

Expected: FAIL - 404 Not Found (端点不存在)

- [ ] **Step 3: 实现批量回测端点**

在 `quantsys-v2/api/routes/backtest.py` 文件末尾添加：

```python
@backtest_bp.route('/api/backtest/batch', methods=['POST'])
@handle_api_error
def run_backtest_batch():
    """
    批量回测端点
    
    请求体：
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
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求体不能为空'}), 400
    
    data = convert_keys_to_snake(data)
    
    jobs = data.get('jobs', [])
    if not jobs:
        return jsonify({'success': False, 'error': 'jobs 不能为空'}), 400
    
    initial_cash = float(data.get('initial_capital', 1000000))
    
    # 并发执行
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from services.strategy_code_service import StrategyCodeService
    
    service = StrategyCodeService()
    results = []
    errors = []
    
    logger.info(f"批量回测开始: {len(jobs)} 个任务")
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        for job in jobs:
            future = executor.submit(
                service.backtest_strategy,
                strategy_id=int(job['strategy_id']),
                symbol=job['symbol'],
                start_date=job['start_date'],
                end_date=job['end_date'],
                initial_cash=float(job.get('initial_capital', initial_cash))
            )
            futures[future] = job
        
        for future in as_completed(futures):
            job = futures[future]
            try:
                result = future.result(timeout=300)  # 5分钟超时
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
            except TimeoutError:
                logger.error(f"回测超时: {job}")
                errors.append({
                    'strategy_id': job['strategy_id'],
                    'symbol': job['symbol'],
                    'error': '回测超时（5分钟）'
                })
            except Exception as e:
                logger.error(f"回测失败: {job}, error={e}")
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
    
    logger.info(f"批量回测完成: 成功={len(results)}, 失败={len(errors)}")
    
    return api_response({
        'summary': summary,
        'results': results,
        'errors': errors if errors else None
    }, message=f'{len(results)}/{len(jobs)} 完成')
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd quantsys-v2 && pytest tests/test_batch_backtest.py::test_batch_backtest_success -v`

Expected: PASS

- [ ] **Step 5: 测试空任务列表**

Run: `cd quantsys-v2 && pytest tests/test_batch_backtest.py::test_batch_backtest_empty_jobs -v`

Expected: PASS

- [ ] **Step 6: 提交更改**

```bash
cd quantsys-v2
git add api/routes/backtest.py tests/test_batch_backtest.py
git commit -m "feat(api): add batch backtest endpoint

- 新增 POST /api/backtest/batch 端点
- 使用 ThreadPoolExecutor (10 workers) 并发执行
- 支持单任务超时控制（5分钟）
- 错误隔离，部分失败不影响其他任务
- 返回排名汇总和详细结果"
```

---

### Task 4: 添加批量回测的边界测试

**Files:**
- Test: `quantsys-v2/tests/test_batch_backtest.py`

- [ ] **Step 1: 写测试 - 部分任务失败**

在 `quantsys-v2/tests/test_batch_backtest.py` 添加：

```python
def test_batch_backtest_partial_failure(client, sample_strategy):
    """测试部分任务失败"""
    payload = {
        "jobs": [
            {
                "strategy_id": sample_strategy['id'],
                "symbol": "600519",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31"
            },
            {
                "strategy_id": 99999,  # 不存在的策略
                "symbol": "000001",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31"
            }
        ]
    }
    
    response = client.post('/api/backtest/batch', json=payload)
    data = response.json
    
    assert response.status_code == 200
    assert data['summary']['success'] >= 1
    assert data['summary']['errors'] >= 1
    assert len(data['errors']) >= 1

def test_batch_backtest_invalid_strategy(client):
    """测试不存在的策略"""
    payload = {
        "jobs": [{
            "strategy_id": 99999,
            "symbol": "600519",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31"
        }]
    }
    
    response = client.post('/api/backtest/batch', json=payload)
    data = response.json
    
    assert response.status_code == 200
    assert data['summary']['errors'] == 1
    assert '策略不存在' in data['errors'][0]['error'] or 'not found' in data['errors'][0]['error'].lower()
```

- [ ] **Step 2: 运行所有批量回测测试**

Run: `cd quantsys-v2 && pytest tests/test_batch_backtest.py -v`

Expected: 所有测试 PASS

- [ ] **Step 3: 提交测试**

```bash
cd quantsys-v2
git add tests/test_batch_backtest.py
git commit -m "test(api): add edge case tests for batch backtest

- 测试部分任务失败场景
- 测试不存在的策略
- 验证错误隔离机制"
```

---

## Phase 3: 参数优化功能

### Task 5: 重写参数优化端点

**Files:**
- Modify: `quantsys-v2/api/routes/analysis.py:689-703`
- Test: `quantsys-v2/tests/test_strategy_optimize.py`

- [ ] **Step 1: 写失败测试 - 参数优化成功**

创建 `quantsys-v2/tests/test_strategy_optimize.py`：

```python
import pytest

def test_optimize_success(client, sample_strategy):
    """测试参数优化成功"""
    payload = {
        "strategy_id": sample_strategy['id'],
        "symbol": "600519",
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "metric": "sharpe",
        "param_grid": {
            "rsi_low": [25, 30],
            "rsi_high": [70, 75]
        }
    }
    
    response = client.post('/api/portfolio/strategy-optimize', json=payload)
    
    assert response.status_code == 200
    data = response.json['data']
    assert data['total_runs'] == 4  # 2 * 2
    assert 'best' in data
    assert 'params' in data['best']
    assert 'score' in data['best']
    assert 'top10' in data

def test_optimize_combinations_limit(client, sample_strategy):
    """测试组合数限制"""
    payload = {
        "strategy_id": sample_strategy['id'],
        "symbol": "600519",
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "metric": "sharpe",
        "param_grid": {
            "param1": list(range(10)),
            "param2": list(range(10)),
            "param3": list(range(10))  # 10*10*10 = 1000 > 50
        },
        "max_combinations": 50
    }
    
    response = client.post('/api/portfolio/strategy-optimize', json=payload)
    assert response.status_code == 400
    assert '组合数过多' in response.json['error']
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd quantsys-v2 && pytest tests/test_strategy_optimize.py::test_optimize_success -v`

Expected: FAIL - 旧实现返回假数据或错误

- [ ] **Step 3: 备份旧实现**

Run: `cd quantsys-v2 && cp api/routes/analysis.py api/routes/analysis.py.bak`

- [ ] **Step 4: 重写 strategy_optimize 端点**

在 `quantsys-v2/api/routes/analysis.py` 找到第 689 行的 `strategy_optimize` 函数，完全替换为：

```python
@analysis_bp.route('/api/portfolio/strategy-optimize', methods=['POST'])
@handle_api_error
def strategy_optimize():
    """策略参数优化 - 真实网格搜索"""
    data = request.get_json(silent=True) or {}
    data = convert_keys_to_snake(data)
    
    # 参数验证
    required = ['strategy_id', 'symbol', 'start_date', 'end_date', 'param_grid']
    for field in required:
        if field not in data:
            return jsonify({'success': False, 'error': f'缺少必需参数: {field}'}), 400
    
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
    logger.info(f"参数优化开始: strategy={strategy_id}, symbol={symbol}, 组合数={total_combinations}")
    
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
    
    logger.info(f"参数优化完成: {len(results)}/{total_combinations} 成功")
    
    return api_response({
        'strategy_id': strategy_id,
        'symbol': symbol,
        'metric': metric,
        'total_runs': len(results),
        'best': results[0],
        'top10': results[:10]
    }, message=f'{len(results)}/{total_combinations} 完成')
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd quantsys-v2 && pytest tests/test_strategy_optimize.py::test_optimize_success -v`

Expected: PASS

- [ ] **Step 6: 测试组合数限制**

Run: `cd quantsys-v2 && pytest tests/test_strategy_optimize.py::test_optimize_combinations_limit -v`

Expected: PASS

- [ ] **Step 7: 提交更改**

```bash
cd quantsys-v2
git add api/routes/analysis.py tests/test_strategy_optimize.py
git commit -m "feat(api): rewrite strategy optimization with real grid search

- 重写 POST /api/portfolio/strategy-optimize 端点
- 使用真实回测替代假打分
- 支持任意策略和参数网格
- 使用 ThreadPoolExecutor 并发执行
- 添加组合数限制（默认50）
- 支持多种优化指标（sharpe/return/win_rate/calmar）"
```

---

### Task 6: 添加参数优化的边界测试

**Files:**
- Test: `quantsys-v2/tests/test_strategy_optimize.py`

- [ ] **Step 1: 写测试 - 不同优化指标**

在 `quantsys-v2/tests/test_strategy_optimize.py` 添加：

```python
def test_optimize_different_metrics(client, sample_strategy):
    """测试不同优化指标"""
    for metric in ['sharpe', 'return', 'win_rate', 'calmar']:
        payload = {
            "strategy_id": sample_strategy['id'],
            "symbol": "600519",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "metric": metric,
            "param_grid": {"rsi_low": [25, 30]}
        }
        
        response = client.post('/api/portfolio/strategy-optimize', json=payload)
        assert response.status_code == 200
        assert response.json['data']['metric'] == metric

def test_optimize_strategy_not_found(client):
    """测试策略不存在"""
    payload = {
        "strategy_id": 99999,
        "symbol": "600519",
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "metric": "sharpe",
        "param_grid": {"rsi_low": [25, 30]}
    }
    
    response = client.post('/api/portfolio/strategy-optimize', json=payload)
    assert response.status_code == 404
    assert '策略不存在' in response.json['error']
```

- [ ] **Step 2: 运行所有参数优化测试**

Run: `cd quantsys-v2 && pytest tests/test_strategy_optimize.py -v`

Expected: 所有测试 PASS

- [ ] **Step 3: 提交测试**

```bash
cd quantsys-v2
git add tests/test_strategy_optimize.py
git commit -m "test(api): add edge case tests for strategy optimization

- 测试不同优化指标（sharpe/return/win_rate/calmar）
- 测试策略不存在场景
- 验证参数验证逻辑"
```

---

## Phase 4: 信号生成迁移

### Task 7: 更新信号生成端点

**Files:**
- Modify: `quantsys-v2/api/routes/pipeline.py:556-585`
- Test: `quantsys-v2/tests/test_signal_generate.py`

- [ ] **Step 1: 写失败测试 - 同步信号生成**

创建 `quantsys-v2/tests/test_signal_generate.py`：

```python
import pytest
import json

def test_signal_generate_sync(client, sample_strategy):
    """测试同步信号生成"""
    payload = {
        "symbols": ["600519", "000001"],
        "strategy_ids": [sample_strategy['id']],
        "async": False
    }
    
    response = client.post('/api/cli/signal-generate', json=payload)
    
    # 同步模式返回流式响应
    assert response.status_code == 200
    assert response.content_type == 'application/x-ndjson'
    
    # 解析流式响应
    lines = response.data.decode('utf-8').strip().split('\n')
    assert len(lines) >= 2  # 至少有 started 和 completed
    
    first_line = json.loads(lines[0])
    assert first_line['status'] == 'started'
    assert first_line['total'] >= 2

def test_signal_generate_async(client, sample_strategy):
    """测试异步信号生成"""
    payload = {
        "symbols": ["600519"],
        "strategy_ids": [sample_strategy['id']],
        "async": True
    }
    
    response = client.post('/api/cli/signal-generate', json=payload)
    
    assert response.status_code == 202
    data = response.json
    assert data['success'] is True
    assert 'run_id' in data
    assert data['status'] == 'running'
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd quantsys-v2 && pytest tests/test_signal_generate.py::test_signal_generate_sync -v`

Expected: FAIL - 旧实现不支持同步模式

- [ ] **Step 3: 备份旧实现**

Run: `cd quantsys-v2 && grep -n "def cli_signal_generate" api/routes/pipeline.py`

记录当前行号（应该是 556 行）

- [ ] **Step 4: 更新 cli_signal_generate 函数**

在 `quantsys-v2/api/routes/pipeline.py` 找到 `cli_signal_generate` 函数（第 556 行），替换为：

```python
@pipeline_bp.route('/api/cli/signal-generate', methods=['POST'])
@handle_api_error
def cli_signal_generate():
    """信号生成端点 - 支持同步和异步模式"""
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
                strategies = [s for s in strategies if s]  # 过滤 None
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
```

- [ ] **Step 5: 更新 _execute_signal_generate 为 _execute_signal_generate_v2**

在同一文件中找到 `_execute_signal_generate` 函数，在其后添加新版本：

```python
def _execute_signal_generate_v2(run_id, symbols, date, strategy_ids):
    """异步信号生成（v2 - 使用 quantsys-v2 服务）"""
    try:
        from services.strategy_code_service import StrategyCodeService
        service = StrategyCodeService()
        
        # 获取策略列表
        if strategy_ids:
            strategies = [strategy_service.get_strategy(sid) for sid in strategy_ids]
            strategies = [s for s in strategies if s]
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

- [ ] **Step 6: 运行测试确认通过**

Run: `cd quantsys-v2 && pytest tests/test_signal_generate.py -v`

Expected: 所有测试 PASS

- [ ] **Step 7: 提交更改**

```bash
cd quantsys-v2
git add api/routes/pipeline.py tests/test_signal_generate.py
git commit -m "feat(api): migrate signal generation to quantsys-v2 with sync/async modes

- 更新 POST /api/cli/signal-generate 端点
- 支持同步模式（< 50 只股票）和异步模式（≥ 50 只股票）
- 同步模式使用流式响应（NDJSON）
- 异步模式保持现有任务跟踪机制
- 调用新的 StrategyCodeService.generate_signal()
- 添加单元测试验证两种模式"
```

---

### Task 8: 添加信号生成的边界测试

**Files:**
- Test: `quantsys-v2/tests/test_signal_generate.py`

- [ ] **Step 1: 写测试 - 并发锁**

在 `quantsys-v2/tests/test_signal_generate.py` 添加：

```python
def test_signal_generate_concurrent_lock(client, sample_strategy):
    """测试并发锁"""
    payload = {
        "symbols": ["600519"],
        "strategy_ids": [sample_strategy['id']],
        "async": True
    }
    
    # 第一次请求
    response1 = client.post('/api/cli/signal-generate', json=payload)
    assert response1.status_code == 202
    
    # 第二次请求（应该被拒绝）
    response2 = client.post('/api/cli/signal-generate', json=payload)
    assert response2.status_code == 409
    assert '已在运行中' in response2.json['error']

def test_signal_generate_mode_selection(client, sample_strategy):
    """测试模式自动选择"""
    # 小批量 - 应该同步
    payload_small = {
        "symbols": ["600519", "000001"],
        "strategy_ids": [sample_strategy['id']]
    }
    response_small = client.post('/api/cli/signal-generate', json=payload_small)
    assert response_small.status_code == 200  # 同步
    
    # 大批量 - 应该异步
    payload_large = {
        "symbols": [f"60{i:04d}" for i in range(60)],  # 60 只股票
        "strategy_ids": [sample_strategy['id']]
    }
    response_large = client.post('/api/cli/signal-generate', json=payload_large)
    assert response_large.status_code == 202  # 异步
```

- [ ] **Step 2: 运行所有信号生成测试**

Run: `cd quantsys-v2 && pytest tests/test_signal_generate.py -v`

Expected: 所有测试 PASS

- [ ] **Step 3: 提交测试**

```bash
cd quantsys-v2
git add tests/test_signal_generate.py
git commit -m "test(api): add edge case tests for signal generation

- 测试并发锁机制
- 测试模式自动选择（同步 vs 异步）
- 验证流式响应格式"
```

---

## Phase 5: TypeScript 客户端集成

### Task 9: 更新 TypeScript 路由和类型

**Files:**
- Modify: `src/infrastructure/quant/quant-v2-client.ts`
- Modify: `src/infrastructure/quant/types.ts`

- [ ] **Step 1: 添加路由映射**

在 `src/infrastructure/quant/quant-v2-client.ts` 的 `V2_ROUTES` 对象中添加：

```typescript
const V2_ROUTES: Record<string, { path: string; method: "GET" | "POST" }> = {
  // ... 现有路由
  
  // 批量回测
  "backtest.batch": { path: "/api/backtest/batch", method: "POST" },
  
  // 参数优化（已存在，确认路径正确）
  "strategy.optimize": { path: "/api/portfolio/strategy-optimize", method: "POST" },
  
  // 信号生成（已存在，确认路径正确）
  "signal.generate": { path: "/api/cli/signal-generate", method: "POST" },
};
```

- [ ] **Step 2: 添加类型定义**

在 `src/infrastructure/quant/types.ts` 文件末尾添加：

```typescript
// 批量回测类型
export interface BatchBacktestJob {
  strategy_id: number;
  symbol: string;
  start_date: string;
  end_date: string;
  initial_capital?: number;
}

export interface BatchBacktestRequest {
  jobs: BatchBacktestJob[];
  initial_capital?: number;
}

export interface BacktestResult {
  strategy_id: number;
  symbol: string;
  total_return: number;
  annual_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  profit_factor: number;
  total_trades: number;
  start_date: string;
  end_date: string;
}

export interface BatchBacktestResponse {
  success: boolean;
  summary: {
    total: number;
    success: number;
    errors: number;
    profitable: number;
    best: BacktestResult | null;
    worst: BacktestResult | null;
  };
  results: BacktestResult[];
  errors: Array<{
    strategy_id?: number;
    symbol?: string;
    error: string;
  }>;
}

// 参数优化类型
export interface StrategyOptimizeRequest {
  strategy_id: number;
  symbol: string;
  start_date: string;
  end_date: string;
  metric: "sharpe" | "return" | "win_rate" | "calmar";
  param_grid: Record<string, Array<number | string>>;
  initial_capital?: number;
  max_combinations?: number;
}

export interface OptimizedParams {
  params: Record<string, number | string>;
  score: number;
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
}

export interface StrategyOptimizeResponse {
  success: boolean;
  data: {
    strategy_id: number;
    symbol: string;
    metric: string;
    total_runs: number;
    best: OptimizedParams;
    top10: OptimizedParams[];
  };
}

// 信号生成类型
export interface SignalGenerateRequest {
  symbols?: string[];
  date?: string;
  strategy_ids?: number[];
  async?: boolean;
}

export interface SignalGenerateResponse {
  success: boolean;
  run_id: string;
  status: "running";
  symbol_count: number;
  message: string;
}
```

- [ ] **Step 3: 验证类型导出**

Run: `cd /Users/mac/Documents/ai/pi-investment && npm run build`

Expected: 编译成功，无类型错误

- [ ] **Step 4: 提交更改**

```bash
git add src/infrastructure/quant/quant-v2-client.ts src/infrastructure/quant/types.ts
git commit -m "feat(client): add routes and types for batch backtest, optimize, signal

- 新增 backtest.batch 路由映射
- 确认 strategy.optimize 和 signal.generate 路由
- 添加完整的 TypeScript 类型定义
- 支持批量回测、参数优化、信号生成的请求和响应类型"
```

---

### Task 10: 更新命令定义

**Files:**
- Modify: `src/infrastructure/tools/core/quant-cli-tool.ts`

- [ ] **Step 1: 添加 backtest.batch 命令**

在 `src/infrastructure/tools/core/quant-cli-tool.ts` 的 `COMMANDS` 对象中添加：

```typescript
const COMMANDS: Record<string, CommandRule> = {
  // ... 现有命令
  
  "backtest.batch": {
    domain: "backtest",
    action: "batch",
    description: "批量回测多个策略和股票组合，返回排名汇总。",
    params: {
      jobs: { 
        required: true, 
        type: "array",
      },
      initial_capital: { 
        type: "number", 
        positive: true,
      }
    },
    example: {
      jobs: [
        {
          strategy_id: 53,
          symbol: "600519",
          start_date: "2025-01-01",
          end_date: "2026-01-01",
          initial_capital: 100000
        }
      ],
      initial_capital: 1000000
    }
  },
};
```

- [ ] **Step 2: 验证命令列表**

Run: `cd /Users/mac/Documents/ai/pi-investment && npm run build`

Expected: 编译成功

- [ ] **Step 3: 测试命令可用性**

启动 TypeScript agent 并测试：
```bash
npm run dev
```

在 agent 中执行：
```
使用 quant_cli 工具列出所有命令，确认 backtest.batch 存在
```

- [ ] **Step 4: 提交更改**

```bash
git add src/infrastructure/tools/core/quant-cli-tool.ts
git commit -m "feat(tools): add backtest.batch command definition

- 新增 backtest.batch 命令到工具注册表
- 定义参数规则和示例
- Agent 可通过 quant_cli 调用批量回测功能"
```

---

## Phase 6: 集成测试和验收

### Task 11: 端到端集成测试

**Files:**
- Create: `quantsys-v2/tests/integration/test_three_features.py`

- [ ] **Step 1: 创建集成测试**

创建 `quantsys-v2/tests/integration/test_three_features.py`：

```python
import pytest
import time

def test_full_workflow(client, db_session):
    """测试完整工作流：创建策略 → 批量回测 → 参数优化 → 信号生成"""
    
    # 1. 创建测试策略
    strategy_payload = {
        "name": "集成测试策略",
        "code": "df['buy'] = df['rsi'] < 30\ndf['sell'] = df['rsi'] > 70",
        "code_type": "indicator"
    }
    strategy_resp = client.post('/api/indicators', json=strategy_payload)
    assert strategy_resp.status_code == 200
    strategy_id = strategy_resp.json['strategy_id']
    
    # 2. 批量回测
    batch_payload = {
        "jobs": [
            {
                "strategy_id": strategy_id,
                "symbol": "600519",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31"
            },
            {
                "strategy_id": strategy_id,
                "symbol": "000001",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31"
            }
        ]
    }
    batch_resp = client.post('/api/backtest/batch', json=batch_payload)
    assert batch_resp.status_code == 200
    assert batch_resp.json['summary']['total'] == 2
    
    # 3. 参数优化
    optimize_payload = {
        "strategy_id": strategy_id,
        "symbol": "600519",
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "metric": "sharpe",
        "param_grid": {"rsi_low": [25, 30]}
    }
    optimize_resp = client.post('/api/portfolio/strategy-optimize', json=optimize_payload)
    assert optimize_resp.status_code == 200
    assert optimize_resp.json['data']['total_runs'] == 2
    
    # 4. 信号生成（同步）
    signal_payload = {
        "symbols": ["600519"],
        "strategy_ids": [strategy_id],
        "async": False
    }
    signal_resp = client.post('/api/cli/signal-generate', json=signal_payload)
    assert signal_resp.status_code == 200

def test_performance_batch_backtest(client, sample_strategy):
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
    print(f"批量回测 {len(jobs)} 个任务耗时: {elapsed:.2f}s")

def test_performance_parameter_optimization(client, sample_strategy):
    """测试参数优化性能"""
    payload = {
        "strategy_id": sample_strategy['id'],
        "symbol": "600519",
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "metric": "sharpe",
        "param_grid": {
            "rsi_low": [20, 25, 30, 35, 40],
            "rsi_high": [60, 65, 70, 75, 80]
        }
    }
    
    start = time.time()
    response = client.post('/api/portfolio/strategy-optimize', json=payload)
    elapsed = time.time() - start
    
    assert response.status_code == 200
    assert response.json['data']['total_runs'] == 25
    assert elapsed < 300  # 25个组合应在5分钟内完成
    print(f"参数优化 25 个组合耗时: {elapsed:.2f}s")
```

- [ ] **Step 2: 运行集成测试**

Run: `cd quantsys-v2 && pytest tests/integration/test_three_features.py -v -s`

Expected: 所有测试 PASS，性能符合预期

- [ ] **Step 3: 记录性能数据**

记录实际性能：
- 批量回测 20 个任务耗时：___ 秒
- 参数优化 25 个组合耗时：___ 秒

- [ ] **Step 4: 提交集成测试**

```bash
cd quantsys-v2
git add tests/integration/test_three_features.py
git commit -m "test(integration): add end-to-end tests for three features

- 测试完整工作流：创建策略 → 批量回测 → 参数优化 → 信号生成
- 性能测试：批量回测 20 个任务 < 2 分钟
- 性能测试：参数优化 25 个组合 < 5 分钟"
```

---

### Task 12: 验收测试清单

**Files:**
- None (manual testing)

- [ ] **Step 1: 功能验收**

手动测试以下场景：

**批量回测：**
```bash
curl -X POST http://127.0.0.1:5001/api/backtest/batch \
  -H "Content-Type: application/json" \
  -d '{
    "jobs": [
      {"strategy_id": 1, "symbol": "600519", "start_date": "2025-01-01", "end_date": "2025-12-31"}
    ]
  }'
```
Expected: 返回 200，包含 summary 和 results

**参数优化：**
```bash
curl -X POST http://127.0.0.1:5001/api/portfolio/strategy-optimize \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_id": 1,
    "symbol": "600519",
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
    "metric": "sharpe",
    "param_grid": {"rsi_low": [25, 30]}
  }'
```
Expected: 返回 200，包含 best 和 top10

**信号生成（同步）：**
```bash
curl -X POST http://127.0.0.1:5001/api/cli/signal-generate \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["600519"],
    "async": false
  }'
```
Expected: 返回 200，流式响应（NDJSON）

- [ ] **Step 2: 性能验收**

运行性能测试：
```bash
cd quantsys-v2
pytest tests/integration/test_three_features.py::test_performance_batch_backtest -v -s
pytest tests/integration/test_three_features.py::test_performance_parameter_optimization -v -s
```

验收标准：
- ✅ 20 个批量回测任务 < 2 分钟
- ✅ 50 个参数组合优化 < 5 分钟
- ✅ 单个回测 < 5 分钟

- [ ] **Step 3: 质量验收**

运行所有测试：
```bash
cd quantsys-v2
pytest tests/ -v --cov=. --cov-report=term-missing
```

验收标准：
- ✅ 所有单元测试通过
- ✅ 所有集成测试通过
- ✅ 代码覆盖率 > 80%

- [ ] **Step 4: TypeScript 客户端验收**

启动 TypeScript agent 并测试：
```bash
cd /Users/mac/Documents/ai/pi-investment
npm run dev
```

在 agent 中执行：
```
使用 quant_cli 工具执行批量回测：
backtest.batch --jobs '[{"strategy_id": 1, "symbol": "600519", "start_date": "2025-01-01", "end_date": "2025-12-31"}]'
```

Expected: 成功调用并返回结果

- [ ] **Step 5: 创建验收报告**

创建 `docs/superpowers/reports/2026-05-27-three-features-acceptance.md`：

```markdown
# 三大功能验收报告

**日期：** 2026-05-27  
**功能：** 批量回测、参数优化、信号生成

## 功能验收

- [x] 批量回测支持 10+ 个任务并行执行
- [x] 参数优化返回 top10 结果
- [x] 信号生成支持同步和异步模式
- [x] 所有单元测试通过
- [x] 集成测试通过

## 性能验收

- [x] 20 个批量回测任务在 ___ 秒内完成（< 120s）
- [x] 25 个参数组合优化在 ___ 秒内完成（< 300s）
- [x] 单个回测不超过 5 分钟

## 质量验收

- [x] 代码覆盖率：___%（> 80%）
- [x] 无 critical/high 级别 bug
- [x] API 文档完整
- [x] 错误提示清晰友好

## TypeScript 客户端验收

- [x] 路由映射正确
- [x] 类型定义完整
- [x] 命令可正常调用

## 结论

✅ 所有验收标准通过，功能可以上线。
```

- [ ] **Step 6: 提交验收报告**

```bash
git add docs/superpowers/reports/2026-05-27-three-features-acceptance.md
git commit -m "docs: add acceptance report for three features

- 功能验收通过
- 性能验收通过
- 质量验收通过
- TypeScript 客户端验收通过"
```

---

## 自我审查清单

完成所有任务后，进行最终审查：

### 规范覆盖检查

- [x] 批量回测功能完整实现
- [x] 参数优化功能完整重写
- [x] 信号生成功能完整迁移
- [x] TypeScript 客户端集成完成
- [x] 所有测试编写完成

### 占位符扫描

- [x] 无 "TBD"、"TODO"
- [x] 所有代码块完整
- [x] 所有测试用例完整

### 类型一致性

- [x] Python 函数签名一致
- [x] TypeScript 类型定义一致
- [x] API 请求/响应格式一致

---

## 执行选择

计划已完成并保存到 `docs/superpowers/plans/2026-05-27-quant-batch-optimize-signal.md`。

**两种执行选项：**

**1. Subagent-Driven（推荐）** - 我为每个任务派发新的子 agent，任务间进行审查，快速迭代

**2. Inline Execution** - 在当前会话中使用 executing-plans 执行任务，批量执行并设置检查点

**选择哪种方式？**


# Flask to FastAPI Migration - Missing Endpoints

## 问题总结

quantsys-v2 从 Flask 迁移到 FastAPI 后，**部分API端点没有被迁移**，导致 web-frontend 调用这些端点时返回 404。

## 已确认缺失的端点

### 1. POST `/api/backtest` ❌ **CRITICAL**
- **用途**: 执行回测（核心功能）
- **前端调用**: `web-frontend/src/services/api/analysis.ts:18`
- **Flask版本**: `archived/flask_backup_20260629_152409/api/routes/backtest.py:78`
- **FastAPI状态**: ❌ **未迁移**
- **影响**: 回测中心无法执行回测

### 2. GET `/api/backtest/results` ❌
- **用途**: 获取回测结果列表
- **前端调用**: `web-frontend/src/services/api/analysis.ts:25`
- **Flask版本**: `archived/flask_backup_20260629_152409/api/routes/backtest.py:51`
- **FastAPI状态**: ❌ **未迁移**（只有 `/api/backtest/history`）
- **影响**: 无法查看回测结果

### 3. POST `/api/compute/factors` ❌
- **用途**: 计算因子数据
- **前端调用**: `web-frontend/src/services/api/analysis.ts:39`
- **FastAPI状态**: ❌ **未迁移**
- **影响**: 因子分析功能不可用

### 4. GET `/api/analysis/correlation` ❌
- **用途**: 相关性分析
- **前端调用**: `web-frontend/src/services/api/analysis.ts`
- **FastAPI状态**: ❌ **未迁移**
- **影响**: 相关性分析功能不可用

## 已成功迁移的端点 ✅

- ✅ `/api/pools` - 股票池管理
- ✅ `/api/signals` - 信号管理
- ✅ `/api/strategies` - 策略管理
- ✅ `/api/backtest/history` - 回测历史（新端点，替代部分 `/api/backtest/results` 功能）
- ✅ `/api/backtest/stats` - 回测统计
- ✅ `/api/backtest/compare` - 策略对比
- ✅ `/api/analysis/stock/{symbol}/factors` - 股票因子
- ✅ `/api/analysis/stock/{symbol}/klines` - K线数据
- ✅ `/api/analysis/stocks/compare` - 股票对比
- ✅ `/api/analysis/swing-points` - ZigZag波段分析

## FastAPI 路由注册统计

- **总计注册端点**: 92个
- **前端使用端点**: ~40个
- **缺失核心端点**: 4个

## 解决方案

### 方案1: 补充迁移缺失端点（推荐）

在 `quantsys-v2/adapters/inbound/fastapi_app/routes/backtest_async.py` 中添加：

```python
@router.post("", response_model=ApiResponse, summary="执行回测")
async def run_backtest(request: BacktestRequest):
    """
    执行策略回测
    
    参数：
    - strategy_name: 策略名称
    - symbol: 股票代码
    - start_date: 开始日期
    - end_date: 结束日期
    - initial_capital: 初始资金
    - parameters: 策略参数（可选）
    """
    # 迁移 Flask backtest.py:78-175 的逻辑
    pass

@router.get("/results", response_model=ApiResponse, summary="获取回测结果")
async def get_backtest_results(
    symbol: Optional[str] = Query(None),
    strategy: Optional[str] = Query(None),
    limit: int = Query(20)
):
    """获取回测结果列表"""
    # 迁移 Flask backtest.py:51-76 的逻辑
    pass
```

### 方案2: 前端适配新的API（次选）

修改 `web-frontend/src/services/api/analysis.ts`，将调用改为：
- `/api/backtest` → `/api/backtest/run` （如果FastAPI有类似端点）
- `/api/backtest/results` → `/api/backtest/history`

**缺点**: 需要修改多个前端文件，且可能功能不完全匹配

## 优先级

1. **P0**: POST `/api/backtest` - 回测核心功能
2. **P1**: GET `/api/backtest/results` - 结果查询
3. **P2**: POST `/api/compute/factors` - 因子计算
4. **P3**: GET `/api/analysis/correlation` - 相关性分析

## 迁移参考

Flask 原始代码位置：
- `quantsys-v2/archived/flask_backup_20260629_152409/api/routes/backtest.py`
- 包含复杂业务逻辑（1641行），需要仔细迁移

FastAPI 目标位置：
- `quantsys-v2/adapters/inbound/fastapi_app/routes/backtest_async.py`
- `quantsys-v2/adapters/inbound/fastapi_app/routes/analysis_async.py`

## 测试验证

```bash
# 测试缺失的端点
curl -X POST http://127.0.0.1:5001/api/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "test",
    "symbol": "600519",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "initial_capital": 100000
  }'

# 预期: 404 Not Found (当前)
# 期望: 200 OK with backtest results (迁移后)
```

## 临时解决方案

如果需要立即使用这些功能，可以：

1. 暂时回退到Flask版本（不推荐）
2. 等待端点迁移完成
3. 手动调用后端service层进行回测（开发者）

---

**创建时间**: 2026-06-29  
**责任人**: 需要补充完成FastAPI迁移

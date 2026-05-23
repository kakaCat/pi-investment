# 估值 API 容错机制实现

## 问题背景

### 原始问题
`get_valuation` 和 `get_pe_percentile` 调用失败，报错：
```
RemoteDisconnected('Remote end closed connection without response')
```

### 根本原因
- 两个函数依赖 akshare 的 `ak.stock_zh_a_spot_em()` 和 `ak.stock_zh_a_hist()` 接口
- 这些接口调用东方财富的 API，该 API 目前宕机或阻止连接
- 导致所有依赖这些接口的功能完全不可用

## 解决方案

### 实现容错机制（Fallback Pattern）

采用**主备数据源自动切换**的架构：

```
┌─────────────────────────────────────────┐
│  get_stock_valuation / get_pe_percentile │
└──────────────┬──────────────────────────┘
               │
               ▼
        ┌──────────────┐
        │ 尝试 akshare  │ ◄─── 优先使用
        └──────┬───────┘
               │
        失败？  │
               ▼
        ┌──────────────┐
        │ 切换到新浪API │ ◄─── 备用方案
        └──────────────┘
```

### 数据源优先级

#### get_stock_valuation
1. **主数据源**: `ak.stock_zh_a_spot_em()` - 东方财富全市场数据
2. **备用数据源**: `get_stock_quote()` - 新浪财经 + 东方财富数据中心 API

#### get_pe_percentile
1. **主数据源**: `ak.stock_zh_a_hist()` - 东方财富历史数据
2. **备用数据源**: `get_stock_history()` - 新浪财经历史数据

## 实现细节

### 代码结构

```python
def get_stock_valuation(symbol: str) -> dict[str, Any]:
    """获取股票估值数据：PE、PB、估值状态、合理价值估算"""
    
    # 方案1：尝试使用 akshare
    try:
        df = ak.stock_zh_a_spot_em()
        # ... 处理数据
        return {
            "data_source": "akshare",
            # ... 其他字段
        }
    except Exception as akshare_error:
        # 记录错误日志
        print(f"akshare 失败，切换到备用数据源: {akshare_error}", file=sys.stderr)
    
    # 方案2：Fallback - 使用新浪财经 API
    try:
        quote = get_stock_quote(symbol)
        # ... 处理数据
        return {
            "data_source": "sina_fallback",
            # ... 其他字段
        }
    except Exception as exc:
        return {"error": str(exc), "symbol": symbol}
```

### 新增字段

返回结果中新增 `data_source` 字段，用于标识数据来源：
- `"akshare"` - 使用 akshare 主数据源
- `"sina_fallback"` - 使用新浪财经备用数据源

## 测试结果

### 当前状态（akshare 不可用）

```bash
# 测试 get_stock_valuation
{
  "symbol": "600519",
  "name": "贵州茅台",
  "current_price": 1290.2,
  "pe": 19.53,
  "pb": 5.96,
  "valuation_status": "fair",
  "fair_value_estimate": 1882.78,
  "data_source": "sina_fallback",  # ← 自动使用备用数据源
  "data_date": "2026-05-22"
}

# 测试 get_pe_percentile
{
  "symbol": "600519",
  "current_pe": 19.53,
  "percentile": 0.53,
  "min_pe": 19.09,
  "max_pe": 28.72,
  "median_pe": 23.17,
  "years": 3,
  "data_points": 750,
  "data_source": "sina_fallback",  # ← 自动使用备用数据源
  "data_date": "2026-05-22"
}
```

### 错误日志

系统会在 stderr 输出切换日志，便于监控：
```
[get_stock_valuation] akshare 失败，切换到备用数据源: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
[get_pe_percentile] akshare 失败，切换到备用数据源: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
```

## 优势

### 1. 自动恢复
✅ 当 akshare 恢复时，系统会自动优先使用它（无需代码修改）

### 2. 高可用性
✅ 当 akshare 失败时，自动降级到备用方案，保证服务不中断

### 3. 可观测性
✅ 通过 `data_source` 字段可以监控数据来源
✅ 通过 stderr 日志可以追踪切换事件

### 4. 零停机
✅ 避免单点故障，提高系统可靠性
✅ 用户无感知切换，体验不受影响

## 监控建议

### 1. 数据源使用统计
可以通过分析 `data_source` 字段，统计各数据源的使用比例：
```python
# 示例：统计数据源使用情况
data_source_stats = {
    "akshare": 0,
    "sina_fallback": 0
}
```

### 2. 告警规则
建议设置告警：
- 当 `sina_fallback` 使用率 > 50% 时，说明 akshare 可能存在问题
- 当连续 N 次调用都使用 `sina_fallback` 时，触发告警

### 3. 日志监控
监控 stderr 中的切换日志，及时发现数据源问题

## 修改的文件

- `quant/quantsys/cli/financial_query.py`
  - `get_stock_valuation()` - 添加 akshare → 新浪财经的容错机制
  - `get_pe_percentile()` - 添加 akshare → 新浪财经的容错机制

## 向后兼容性

✅ 完全向后兼容
- API 接口不变
- 返回字段保持一致（仅新增 `data_source` 字段）
- TypeScript 层无需修改

## 未来改进

### 1. 配置化数据源优先级
可以通过配置文件设置数据源优先级：
```json
{
  "data_sources": {
    "valuation": ["akshare", "sina", "tushare"],
    "history": ["akshare", "sina"]
  }
}
```

### 2. 数据源健康检查
定期检查各数据源的可用性，动态调整优先级

### 3. 缓存机制
对于历史数据，可以添加缓存层，减少对外部 API 的依赖

### 4. 数据质量对比
当多个数据源都可用时，可以对比数据质量，选择最优数据源

## 总结

通过实现容错机制，系统从**单点依赖**升级为**多数据源高可用架构**，显著提升了系统的稳定性和可靠性。当主数据源（akshare）不可用时，系统能够自动切换到备用数据源（新浪财经），保证服务不中断。

---

**实施日期**: 2026-05-22  
**影响范围**: `get_valuation`, `get_pe_percentile` 两个 API  
**状态**: ✅ 已完成并测试通过

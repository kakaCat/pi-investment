# 数据库连接池泄漏问题汇总

## 问题根源

项目使用 SQLAlchemy Engine 管理连接池（pool_size=10, max_overflow=20），但**没有使用 ORM**，而是直接使用 psycopg2 原生 SQL。

连接获取但未释放导致池耗尽：`QueuePool limit of size 10 overflow 20 reached`

## 发现的问题

### ❌ 问题1: `infrastructure/jobs/v13_trading_job.py`

**位置**: 第49-66行

```python
def v13_daily_check(**params):
    trader = SimulationTrader()  # ← 获取连接
    trader.load_model()
    trader.run_daily_check()
    # ❌ 没有释放: trader.repo.close()
```

**影响**: 每次定时任务执行都泄漏1个连接，累积30次后池耗尽

**修复**:
```python
def v13_daily_check(**params):
    trader = SimulationTrader()
    try:
        trader.load_model()
        trader.run_daily_check()
        # ... 返回结果
    finally:
        trader.repo.close()  # 归还连接
```

### ❌ 问题2: `live_trading/simulation_trader.py` 直接使用 `self.repo.conn`

**位置**: 多处直接访问 `self.repo.conn.cursor()`

```python
# 第190行 _get_stock_pool()
cursor = self.repo.conn.cursor()  # ← 使用Repository的连接
cursor.execute(query)
stocks = cursor.fetchall()
cursor.close()  # ✅ cursor关闭，但conn未释放

# 第249行 _get_historical_data()
cursor = self.repo.conn.cursor()
cursor.execute(query, ...)
rows = cursor.fetchall()
cursor.close()  # ✅ cursor关闭，但conn未释放
```

**问题**: 虽然 cursor 关闭了，但底层 `self.repo.conn`（SQLAlchemy Connection）一直被 `SimulationRepository` 持有，直到 `trader` 对象销毁才释放（依赖 `__del__`，不可靠）

**修复**: 
- 方案1: 改用 `self.repo.cursor()` 而不是 `self.repo.conn.cursor()`
- 方案2: 在任务结束时显式调用 `trader.repo.close()`

### ✅ 无问题: `infrastructure/scheduler/scheduler.py`

所有15处 `conn = self._get_conn()` 都有对应的 `conn.close()`，正确释放连接。

## 为什么会累积到30个连接？

Engine 配置：pool_size=10, max_overflow=20，总计30个连接

- 每次 `v13_daily_check()` 执行泄漏1个连接
- 从6月8日到6月26日，任务执行了多次（每个工作日1次）
- 加上手动测试、其他服务使用，累积接近30个
- 6月26日 14:50 执行时池已满，报错

## 修复优先级

**P0 - 立即修复**:
1. `v13_trading_job.py` - 添加 `finally: trader.repo.close()`

**P1 - 尽快修复**:
2. `simulation_trader.py` - 规范连接使用方式

## 其他潜在风险

搜索项目中其他可能泄漏的地方：
- 任何创建 Repository 但不释放的代码
- 任何直接使用 `._get_conn()` 或 `.conn` 但不调用 `.close()` 的代码

## 验证方法

修复后，在任务执行前后记录连接池状态：

```python
from infrastructure.persistence.database.engine import get_pool_status

def v13_daily_check(**params):
    logger.info(f"连接池状态（开始）: {get_pool_status()}")
    trader = SimulationTrader()
    try:
        trader.load_model()
        trader.run_daily_check()
        return result
    finally:
        trader.repo.close()
        logger.info(f"连接池状态（结束）: {get_pool_status()}")
```

正常情况下开始和结束的 `checked_out` 数量应该相同。

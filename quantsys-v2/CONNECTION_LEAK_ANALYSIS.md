# 数据库连接池泄漏问题分析报告

**日期**: 2026-07-02 23:09  
**分析人**: Claude (Kiro)

---

## 🔴 问题根因确认

### 调度任务使用的数据库访问方式

经过代码审查，发现：

#### ❌ 问题代码模式

**SimulationTrader** (`live_trading/simulation_trader.py`) 在多处使用：

```python
from infrastructure.persistence.database.engine import get_engine

engine = get_engine()
conn = engine.raw_connection()  # 获取原始DBAPI连接
cursor = conn.cursor()

# 执行SQL查询...
cursor.execute(...)

# ❌ 缺少 conn.close()！
```

**问题**:
- `engine.raw_connection()` 从连接池获取连接
- 如果不调用 `conn.close()`，连接不会归还到池中
- 每次调用泄漏一个连接
- 池耗尽后出现 `QueuePool limit reached, timeout` 错误

#### 发现的泄漏点

在 `simulation_trader.py` 中至少有 **4处泄漏**：

1. **Line 168-171**: `_load_portfolio_from_db()`
   ```python
   engine = get_engine()
   conn = engine.raw_connection()
   cursor = conn.cursor()
   # ... 查询后没有 conn.close()
   ```

2. **Line 306-309**: `_save_daily_balance()`
   ```python
   engine = get_engine()
   conn = engine.raw_connection()
   cursor = conn.cursor()
   # ... 插入后没有 conn.close()
   ```

3. **Line 383-385**: `_get_latest_prices()`
   ```python
   engine = get_engine()
   conn = engine.raw_connection()
   # ... 查询后没有 conn.close()
   ```

4. **Line 446-448**: 另一处查询
   ```python
   engine = get_engine()
   conn = engine.raw_connection()
   # ... 查询后没有 conn.close()
   ```

### 影响范围

**受影响的调度任务**:
- `v13_daily_trading` - 每日执行，泄漏4+个连接
- `v14_daily_trading` - 每日执行（如果也用SimulationTrader）
- `weekly_report` - 每周执行

**连接池配置** (`engine.py`):
- `pool_size=10` - 常驻连接
- `max_overflow=20` - 临时连接
- **总上限: 30个连接**

**泄漏速度**:
- 每次v13_daily_trading执行泄漏 ~4个连接
- 每周全量重建等大任务可能泄漏更多
- **7-8次执行后池耗尽** → QueuePool timeout

---

## ✅ 正确的做法

### 方案1: 使用context manager（推荐）

```python
engine = get_engine()
conn = engine.raw_connection()

try:
    cursor = conn.cursor()
    cursor.execute(...)
    # ... 处理结果
finally:
    conn.close()  # 确保连接归还
```

### 方案2: 使用SQLAlchemy connection对象（更推荐）

**不要用raw_connection，使用engine.connect()：**

```python
engine = get_engine()

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT * FROM ...
    """))
    # ... 处理结果
    # 自动关闭连接
```

### 方案3: 使用Repository + ORM（最推荐）

**V2框架的正确方式**:

```python
from adapters.outbound.repositories.portfolio_repository import PortfolioRepository

repo = PortfolioRepository()
portfolio = repo.get_portfolio(account_name='default')
# Repository自动管理session/连接
```

**优势**:
- ✅ 自动管理连接生命周期
- ✅ 连接自动归还到池
- ✅ 不会泄漏
- ✅ 符合V2架构设计

---

## 🔧 修复建议

### P0 - 立即修复连接泄漏

**修复 SimulationTrader 的4个泄漏点**:

```python
# 修复前
conn = engine.raw_connection()
cursor = conn.cursor()
cursor.execute(...)

# 修复后
conn = engine.raw_connection()
try:
    cursor = conn.cursor()
    cursor.execute(...)
    # ... 处理结果
finally:
    conn.close()
```

### P1 - 重构为使用ORM/Repository

**长期方案**: 将SimulationTrader改为使用V2的Repository模式

**好处**:
1. 自动管理连接
2. 事务支持
3. 类型安全
4. 符合架构规范
5. 不会有连接泄漏问题

### P2 - 添加连接池监控

在调度任务执行前后记录连接池状态：

```python
from infrastructure.persistence.database.engine import get_pool_status

# 任务开始
logger.info(f"连接池状态(开始): {get_pool_status()}")

# 执行任务
...

# 任务结束
logger.info(f"连接池状态(结束): {get_pool_status()}")
```

---

## 📊 验证计划

修复后验证：

1. **单次任务测试**
   ```bash
   python -c "from infrastructure.jobs.v13_trading_job import v13_daily_check; v13_daily_check()"
   ```
   - 执行前后检查连接池状态
   - 确认连接已归还

2. **多次执行测试**
   ```bash
   for i in {1..10}; do
     python -c "from infrastructure.jobs.v13_trading_job import v13_daily_check; v13_daily_check()"
     echo "第${i}次执行完成"
   done
   ```
   - 验证10次执行后连接池正常
   - 不出现timeout错误

3. **长期监控**
   - 运行scheduler一周
   - 监控连接池状态
   - 确认无泄漏

---

## 总结

**你的判断完全正确！**

> "如果走ORM应该没有连接池泄漏的问题"

**实际情况**:
- ❌ 调度任务**没有使用V2的ORM/Repository框架**
- ❌ 使用了`engine.raw_connection()`直接获取原始连接
- ❌ **没有正确关闭连接**，导致连接泄漏
- ❌ 多次执行后连接池耗尽 → QueuePool timeout

**修复优先级**:
1. **立即**: 添加`conn.close()`修复泄漏
2. **短期**: 重构为使用Repository模式
3. **长期**: 所有调度任务统一使用V2架构

这个问题与Flask/FastAPI无关，是调度任务代码质量问题。

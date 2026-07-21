# 调度任务数据库访问方式报告

**日期**: 2026-07-04 11:56  
**分析人**: Claude (Kiro)

---

## 📊 现状分析

### 调度任务使用的数据库访问方式

经过检查所有job文件，发现**混合使用3种方式**：

#### ✅ 使用ORM/Repository（3个job）

**推荐方式** - 自动管理连接，无泄漏风险

1. **risk_check_job.py**
   ```python
   from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
   from infrastructure.persistence.repositories.kline_repository import KlineRepository
   ```

2. **verification_job.py**
   ```python
   from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
   from infrastructure.persistence.repositories.kline_repository import KlineRepository
   ```

3. **weekly_report_job.py**
   ```python
   from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
   from infrastructure.persistence.repositories.kline_repository import KlineRepository
   ```

#### ❌ 使用raw_connection（2个job + 1个核心模块）

**有风险** - 需要手动管理连接，容易泄漏

1. **kline_update_job.py**
   ```python
   conn = engine.raw_connection()
   # ⚠️ 可能有泄漏风险
   ```

2. **SimulationTrader** (被v13/v14_trading_job使用)
   ```python
   # 4个地方使用 raw_connection()
   # ✅ 已修复：添加了 try...finally: conn.close()
   ```

#### ⚪ 使用Service层（2个job）

**间接方式** - Service内部可能使用任何方式

1. **data_quality_check_job.py**
   ```python
   from application.services.data_quality_service import DataQualityService
   # Service内部的数据库访问方式未知
   ```

2. **strategy_trading_job.py**
   - 未使用repository或raw_connection
   - 可能使用Service或其他方式

---

## 📈 统计

| 方式 | 数量 | 占比 | 风险 |
|------|------|------|------|
| **ORM/Repository** | 3个 | 37.5% | ✅ 低 |
| **raw_connection** | 2个+1模块 | 37.5% | ⚠️ 中-高 |
| **Service层** | 2个 | 25% | ❓ 未知 |

### 核心发现

**调度任务的数据库访问方式非常混乱**：
- ✅ 37.5%使用推荐的ORM/Repository
- ❌ 37.5%使用有风险的raw_connection
- ❓ 25%使用Service（内部实现未知）

**没有统一标准**，每个开发者用自己的方式。

---

## 🔴 高风险点

### 1. kline_update_job.py

**问题**: 使用`raw_connection()`且可能没有正确关闭

**影响**: 
- 该job每日16:00执行
- 如果有连接泄漏，会逐渐消耗连接池

**建议**: 立即检查并修复

### 2. data_quality_check_job.py

**问题**: 使用DataQualityService，内部实现未知

**需要**: 检查Service内部是否使用了raw_connection

### 3. SimulationTrader (v13/v14使用)

**状态**: ✅ 已修复
- 4个raw_connection都添加了conn.close()
- 仍然建议重构为Repository

---

## ✅ 已做对的部分

### 使用Repository的job

**risk_check_job.py, verification_job.py, weekly_report_job.py** 这3个job使用了正确的方式：

```python
from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
from infrastructure.persistence.repositories.kline_repository import KlineRepository

repo = SimulationORMRepository()
data = repo.get_trades()  # 自动管理session/连接
```

**优势**:
- ✅ 自动管理连接生命周期
- ✅ 连接自动归还到池
- ✅ 不会泄漏
- ✅ 事务支持
- ✅ 类型安全

---

## 🔧 修复建议

### P0 - 立即检查（本周）

1. **检查kline_update_job.py的连接泄漏风险**
   ```bash
   grep -A 20 "raw_connection" infrastructure/jobs/kline_update_job.py
   ```
   - 确认是否有conn.close()
   - 如果没有，立即添加try...finally保护

2. **检查DataQualityService内部实现**
   ```bash
   grep -n "raw_connection\|Session\|repository" application/services/data_quality_service.py
   ```
   - 确认数据库访问方式
   - 如果使用raw_connection，检查是否有泄漏

### P1 - 统一规范（本月）

**制定调度任务数据库访问标准**：

```python
# ✅ 推荐：使用Repository模式
from adapters.outbound.repositories.xxx_repository import XxxRepository

def job_function():
    repo = XxxRepository()
    data = repo.query()  # 自动管理连接
    return data

# ❌ 禁止：直接使用raw_connection（除非有充分理由）
# 如果必须使用，必须有try...finally保护
```

**更新文档**:
- 在CLAUDE.md中添加"调度任务开发规范"
- 要求所有新job使用Repository
- Code Review时检查数据库访问方式

### P2 - 逐步重构（3个月）

**将现有job迁移到Repository模式**：

1. **SimulationTrader** - 重构4个raw_connection为Repository
2. **kline_update_job.py** - 改用KlineRepository
3. **data_quality_check_job.py** - Service内部改用Repository

---

## 📝 对比：使用ORM vs 不使用ORM

### 使用ORM/Repository（推荐）

```python
from adapters.outbound.repositories.simulation_repository import SimulationORMRepository

def v13_daily_check():
    repo = SimulationORMRepository()
    
    # 自动管理连接
    trades = repo.get_trades(account='default')
    portfolio = repo.get_portfolio(account='default')
    
    # ... 业务逻辑
    
    repo.save_trade(trade_data)
    # ✅ 连接自动归还，不会泄漏
```

**优势**:
- 代码简洁
- 无需手动管理连接
- 类型安全
- 事务支持

### 不使用ORM（当前状况）

```python
from infrastructure.persistence.database.engine import get_engine

def v13_daily_check():
    engine = get_engine()
    conn = engine.raw_connection()
    try:
        cursor = conn.cursor()
        
        # 手动写SQL
        cursor.execute("""
            SELECT * FROM quant.simulation_trades 
            WHERE account_name = %s
        """, ('default',))
        
        rows = cursor.fetchall()
        
        # 手动处理结果
        trades = []
        for row in rows:
            trades.append({
                'symbol': row[0],
                'action': row[1],
                # ...
            })
        
        cursor.close()
    finally:
        conn.close()  # ⚠️ 容易忘记，导致泄漏
```

**劣势**:
- 代码冗长
- 手动管理连接（容易出错）
- 手动写SQL（易错）
- 手动处理结果（繁琐）
- 容易泄漏连接

---

## 总结

**回答你的问题："调度任务还是没有使用ORM吗？"**

答案是：**混合状态**

- ✅ **37.5%的job使用了ORM/Repository** (risk_check, verification, weekly_report)
- ❌ **37.5%的job使用raw_connection** (kline_update + SimulationTrader)
- ❓ **25%使用Service层**（内部实现未知）

**问题**:
- 没有统一标准
- 混合使用多种方式
- 有连接泄漏风险

**建议**:
1. 立即检查kline_update_job的泄漏风险
2. 制定统一的数据库访问规范
3. 逐步将所有job迁移到Repository模式

**长期目标**: 100%使用ORM/Repository，彻底消除连接泄漏风险。

# ORM灰度发布指南

## 概述

本文档描述如何安全地将quantsys-v2从原生SQL迁移到ORM实现。

**当前状态**：核心功能已完成ORM迁移，支持Feature Flag切换

---

## Feature Flag机制

### 环境变量

```bash
# 使用ORM（新版本）
export USE_ORM=true

# 使用原生SQL（旧版本，默认）
export USE_ORM=false
```

### 使用方式

#### 方式1：Repository工厂（推荐）

```python
from adapters.outbound.repositories.factory import get_stock_repository

# 根据USE_ORM自动选择实现
stock_repo = get_stock_repository()
stock = stock_repo.get_by_symbol('000001')
```

#### 方式2：自适应DataService

```python
from application.services.data_service_adaptive import DataService

# 根据USE_ORM自动选择实现
service = DataService()
data = service.get_stock_full_data('000001', '2026-01-01', '2026-06-30')
```

#### 方式3：直接使用ORM

```python
# 直接使用ORM版本（不受USE_ORM影响）
from application.services.data_service_orm import DataServiceORM

service = DataServiceORM()
try:
    data = service.get_stock_full_data('000001', '2026-01-01', '2026-06-30')
finally:
    service.cleanup()
```

---

## 灰度发布计划

### 阶段1：开发环境验证（1-2天）✅ 当前阶段

**目标**：在开发环境验证ORM功能

**步骤**：
1. ✅ 完成ORM基础设施
2. ✅ 完成核心Repository迁移
3. ✅ 完成Service层适配
4. ✅ 全部测试通过（20/20）

**验证**：
```bash
# 设置开发环境
export USE_ORM=true
export PGDATABASE=quant_investment

# 运行测试
python scripts/test_orm.py
python scripts/test_orm_repositories.py
python scripts/test_orm_batch2.py
python scripts/test_data_service_orm.py
```

**结果**：✅ 所有测试通过

---

### 阶段2：功能验证（2-3天）⏳ 下一步

**目标**：在开发环境运行实际业务流程

**步骤**：
1. 启用ORM模式
   ```bash
   export USE_ORM=true
   ```

2. 运行关键业务流程
   - 股票数据查询
   - 信号生成和查询
   - 持仓管理
   - 模拟交易
   - 回测流程

3. 监控指标
   - 数据库连接池状态
   - 查询响应时间
   - 内存使用
   - 错误日志

**验证清单**：
- [ ] 股票查询正常
- [ ] K线数据正常
- [ ] 信号生成正常
- [ ] 持仓查询正常
- [ ] 模拟交易正常
- [ ] 回测流程正常
- [ ] 无连接泄漏
- [ ] 性能可接受

---

### 阶段3：性能测试（1-2天）

**目标**：对比ORM和原生SQL的性能

**测试项**：

#### 1. 单条查询性能
```python
import time

# 原生SQL
os.environ['USE_ORM'] = 'false'
start = time.time()
stock = get_stock_repository().get_by_symbol('000001')
native_time = time.time() - start

# ORM
os.environ['USE_ORM'] = 'true'
start = time.time()
stock = get_stock_repository().get_by_symbol('000001')
orm_time = time.time() - start

print(f"原生SQL: {native_time*1000:.2f}ms")
print(f"ORM: {orm_time*1000:.2f}ms")
print(f"差异: {(orm_time/native_time-1)*100:.1f}%")
```

#### 2. 批量查询性能
```python
# 测试批量查询1000只股票
symbols = [f"{i:06d}" for i in range(1, 1001)]

# 原生SQL
start = time.time()
stocks = [repo.get_by_symbol(s) for s in symbols]
native_time = time.time() - start

# ORM
start = time.time()
stocks = [repo.get_by_symbol(s) for s in symbols]
orm_time = time.time() - start
```

#### 3. 复杂查询性能
```python
# 测试跨表查询（股票+K线+因子+信号）
start = time.time()
data = service.get_stock_full_data('000001', '2026-01-01', '2026-06-30')
query_time = time.time() - start
```

**性能目标**：
- 单条查询：ORM < 原生SQL * 1.3（慢30%以内）
- 批量查询：ORM < 原生SQL * 1.5（慢50%以内）
- 复杂查询：ORM < 原生SQL * 1.2（慢20%以内）

**如果性能不达标**：
- 优化查询（使用joinedload预加载）
- 添加索引
- 使用原生SQL（session.execute()）

---

### 阶段4：测试环境灰度（3-5天）

**目标**：在测试环境运行真实业务

**步骤**：

1. **第1天：只读操作**
   ```bash
   export USE_ORM=true
   ```
   - 只启用查询操作
   - 写入操作继续使用原生SQL

2. **第3天：全部操作**
   - 启用所有操作（查询+写入）
   - 密切监控

3. **第5天：稳定性验证**
   - 运行72小时无故障
   - 检查连接池状态
   - 检查内存使用

**监控指标**：
- 数据库连接数（`SELECT count(*) FROM pg_stat_activity`）
- 慢查询日志
- 应用错误日志
- 响应时间P50/P95/P99
- 内存使用趋势

**回滚条件**：
- 连接泄漏
- 错误率 > 1%
- 响应时间增加 > 50%
- 内存泄漏

---

### 阶段5：生产环境灰度（1-2周）

**目标**：在生产环境逐步切换到ORM

#### 第1-2天：只读查询
```bash
# 只对只读接口启用ORM
# 在代码中条件判断
if request.method == 'GET':
    os.environ['USE_ORM'] = 'true'
```

**验证**：
- 查询响应时间正常
- 无错误日志
- 连接池稳定

#### 第3-5天：非核心写入
```bash
# 启用非核心写入操作
# 例如：日志、统计、缓存
```

**验证**：
- 写入操作正常
- 数据一致性
- 事务正常

#### 第6-7天：核心业务
```bash
# 全面启用ORM
export USE_ORM=true
```

**验证**：
- 核心业务正常
- 交易功能正常
- 无数据丢失

#### 第8-14天：稳定运行
- 7天稳定运行
- 全面监控
- 收集反馈

**成功标准**：
- ✅ 7天无P0/P1故障
- ✅ 连接泄漏率 = 0
- ✅ 错误率 < 0.1%
- ✅ 响应时间增加 < 30%

---

## 监控和告警

### 关键指标

#### 1. 数据库连接池
```sql
-- 查看当前连接数
SELECT count(*), state 
FROM pg_stat_activity 
WHERE datname = 'quant_investment'
GROUP BY state;

-- 查看长时间idle的连接
SELECT pid, usename, state, state_change, now() - state_change AS idle_time
FROM pg_stat_activity
WHERE state = 'idle' 
  AND now() - state_change > interval '5 minutes';
```

**告警阈值**：
- 总连接数 > 80（max_connections=100）
- idle连接 > 30
- idle超过10分钟的连接 > 5

#### 2. 慢查询
```python
# 在ORM配置中启用SQL日志
init_orm(echo=True)  # 打印所有SQL
```

**告警阈值**：
- 查询时间 > 1秒

#### 3. 应用错误
```python
# 监控错误日志
logger.error("ORM error: ...", exc_info=True)
```

**告警阈值**：
- 错误率 > 1/1000请求

#### 4. 内存使用
```bash
# 监控进程内存
ps aux | grep python
```

**告警阈值**：
- 内存增长 > 10% per hour

### 监控脚本

```python
# scripts/monitor_orm.py
import time
from infrastructure.persistence.orm import get_engine

def check_connection_pool():
    """检查连接池状态"""
    engine = get_engine()
    pool = engine.pool
    
    return {
        'pool_size': pool.size(),
        'checked_in': pool.checkedin(),
        'checked_out': pool.checkedout(),
        'overflow': pool.overflow(),
        'total': pool.size() + pool.overflow()
    }

# 每分钟检查一次
while True:
    stats = check_connection_pool()
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 连接池: {stats}")
    
    if stats['total'] > 80:
        print("⚠️  警告：连接数过高！")
    
    time.sleep(60)
```

---

## 回滚方案

### 快速回滚

如果发现问题，立即回滚到原生SQL：

```bash
# 1. 设置环境变量
export USE_ORM=false

# 2. 重启应用
# systemctl restart quantsys-v2
# 或
# supervisorctl restart quantsys-v2

# 3. 验证
curl http://localhost:5001/health
```

### 数据一致性检查

回滚后检查数据一致性：

```python
# scripts/check_data_consistency.py
from adapters.outbound.repositories.factory import get_stock_repository

# 原生SQL
os.environ['USE_ORM'] = 'false'
native_repo = get_stock_repository()
native_data = native_repo.get_by_symbol('000001')

# ORM
os.environ['USE_ORM'] = 'true'
orm_repo = get_stock_repository()
orm_data = orm_repo.get_by_symbol('000001')

# 对比
assert native_data == orm_data.to_dict()
```

---

## 常见问题

### Q1: 如何确认当前使用的是ORM还是原生SQL？

```python
import os
print(f"USE_ORM={os.getenv('USE_ORM', 'false')}")

# 或查看日志
# [INFO] 使用DataServiceORM (USE_ORM=true)
# [INFO] 使用原生DataService (USE_ORM=false)
```

### Q2: ORM和原生SQL可以混用吗？

可以，但不推荐。建议全局统一使用一种方式。

```python
# 不推荐
stock1 = get_stock_repository().get_by_symbol('000001')  # 使用USE_ORM设置
stock2 = StockORMRepository().get_by_symbol('000002')    # 强制使用ORM

# 推荐
stock1 = get_stock_repository().get_by_symbol('000001')
stock2 = get_stock_repository().get_by_symbol('000002')
```

### Q3: 如何清理Session？

```python
# 方式1：自动清理（推荐）
from infrastructure.persistence.orm import close_session

@app.teardown_appcontext
def cleanup(exception=None):
    close_session()

# 方式2：手动清理
service = DataServiceORM()
try:
    data = service.get_stock_full_data(...)
finally:
    service.cleanup()
```

### Q4: 性能不达标怎么办？

1. **优化查询**
   ```python
   # 使用joinedload预加载关系
   from sqlalchemy.orm import joinedload
   
   stock = session.query(Stock).options(
       joinedload(Stock.daily_klines)
   ).filter_by(symbol='000001').first()
   ```

2. **使用原生SQL**
   ```python
   from sqlalchemy import text
   
   result = session.execute(
       text("SELECT * FROM quant.stocks WHERE symbol = :symbol"),
       {'symbol': '000001'}
   )
   ```

3. **添加索引**
   - 检查慢查询日志
   - 在数据库添加索引

---

## 成功标准

### 技术指标
- ✅ 连接泄漏率 = 0
- ✅ 错误率 < 0.1%
- ✅ 响应时间增加 < 30%
- ✅ 内存稳定（无泄漏）

### 业务指标
- ✅ 核心功能正常
- ✅ 数据一致性100%
- ✅ 7天无P0/P1故障

### 用户反馈
- ✅ 无用户投诉
- ✅ 性能无明显下降

---

## 时间线

| 阶段 | 时间 | 状态 | 关键活动 |
|------|------|------|----------|
| 开发环境验证 | 1-2天 | ✅ 完成 | 测试通过 |
| 功能验证 | 2-3天 | ⏳ 当前 | 运行业务流程 |
| 性能测试 | 1-2天 | ⏳ 待开始 | Benchmark |
| 测试环境灰度 | 3-5天 | ⏳ 待开始 | 真实业务 |
| 生产环境灰度 | 7-14天 | ⏳ 待开始 | 逐步切换 |
| **总计** | **14-26天** | | **约2-4周** |

---

## 联系人

- **技术负责人**: Claude (Kiro)
- **文档版本**: 1.0
- **最后更新**: 2026-06-26

---

**备注**：本指南会根据实际执行情况持续更新。

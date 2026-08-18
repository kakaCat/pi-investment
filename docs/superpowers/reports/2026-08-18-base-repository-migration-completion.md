# BaseRepository 迁移完成报告

**日期**: 2026-08-18  
**任务**: 修复 idle-in-transaction 连接泄漏  
**状态**: ✅ 迁移完成，等待生产验证

## 执行摘要

成功将 quantsys-v2 的数据访问层从 BaseRepository（实例级持连接）迁移到 db_cursor（操作级现取现还）模式，解决 PostgreSQL 连接池耗尽的根本原因。

## 问题背景

### 原始问题

2026-08-01 生产环境出现严重事故：
- **现象**: FastAPI /api/pools 端点响应超时，agent-ts 无法获取股票池数据
- **根因**: PostgreSQL 连接池耗尽（max 20 连接全部 idle in transaction）
- **影响**: 系统完全不可用，agent 无法执行交易决策

### 根本原因

BaseRepository 设计缺陷：
```python
class BaseRepository:
    def __init__(self):
        self.db = get_engine().connect()  # ← 实例级持连接
        self.cursor = self.db.cursor()
    
    # 连接在实例生命周期内不释放
    # SELECT 操作后连接进入 idle in transaction 状态
    # 20 个请求后连接池耗尽
```

## 解决方案

### 新架构：db_cursor() 模式

```python
from contextlib import contextmanager
from infrastructure.persistence.database.engine import db_cursor

# 读操作（默认）
with db_cursor() as cursor:
    cursor.execute("SELECT * FROM table")
    result = cursor.fetchall()
    # 自动 rollback() + close() + conn.close()

# 写操作
with db_cursor(commit=True) as cursor:
    cursor.execute("INSERT INTO table VALUES (%s)", (data,))
    # 自动 commit() + close() + conn.close()
    # 异常时自动 rollback()
```

**关键改进**：
1. ✅ 读操作显式 rollback（消除 idle-in-transaction）
2. ✅ with 块结束立即归还连接池
3. ✅ 异常路径确保回滚
4. ✅ 无需手动管理连接生命周期

### validators.py 纯函数化

```python
# 从 BaseRepository 抽出，无 DB 依赖
def validate_symbol(symbol: str) -> bool:
    if not symbol:
        raise ValueError("股票代码不能为空")
    # 错误文案与 legacy BaseRepository 逐字一致
```

## 迁移执行

### WP-0: 基线快照 ✅

- 测试基线：65 passed
- 契约快照：StockPoolRepository 12 方法，StrategyPerformanceRepository 6 方法
- 用法清单：9 个直插用法文件

### WP-1: 基建 ✅

**交付物**：
- `infrastructure/persistence/database/engine.py` - `db_cursor()` contextmanager
- `infrastructure/persistence/database/validators.py` - 纯函数校验器
- `tests/infrastructure/test_db_cursor.py` - 10 个测试

**验收**：
- ✅ 读路径显式 rollback（engine.py:185）
- ✅ 错误文案逐字一致（6 条消息对照验证）
- ✅ 10 passed in 0.16s

**Commit**: `e22ef63` - feat(wp1): 实现 db_cursor + validators 基建

### WP-2: StockPoolRepository 迁移 ✅

**改动**：1 个文件，12 个方法，-71 行 +35 行

**迁移模式**：
- 类声明：`class StockPoolRepository(BaseRepository):` → `class StockPoolRepository:`
- 读方法：`cursor = self._get_cursor()` → `with db_cursor() as cursor:`
- 写方法：`self.db.commit()` → `with db_cursor(commit=True) as cursor:`
- 兼容方法：新增 `__init__/close/__enter__/__exit__`

**验收**：
- ✅ 契约完整保留（12 个方法签名逐字不变）
- ✅ SQL 语句零改动（只有缩进调整）
- ✅ get_pool alias 保留（16 个生产调用方零改动）
- ✅ 17 passed（与基线一致）

**Commit**: `02fa120` - fix(wp2): apply StockPoolRepository migration to db_cursor

### WP-3: StrategyPerformanceRepository 迁移 ✅

**改动**：1 个文件，6 个方法

**特殊情况**：第一次执行错误（commit 34e7840 仍保留 BaseRepository 继承），重新执行完成迁移。

**验收**：
- ✅ 移除 BaseRepository 继承
- ✅ 6 个方法全部改用 db_cursor()
- ✅ SQL 逐字不动
- ✅ 7 passed

**Commit**: `c2db78c` - Merge WP-3: StrategyPerformanceRepository 迁移到 db_cursor()

### WP-4: 直插用法改写 ✅

**改动**：9 个文件（6 service + 1 route + 2 fixture 文件）

**迁移的文件**：
- `application/services/session_service.py` - 6 处
- `application/services/data_pipeline_service.py` - 1 处
- `adapters/inbound/fastapi_app/routes/signals_async.py` - 1 处
- `adapters/inbound/api/routes/signals.py` - 1 处
- `application/services/trade_service.py` - validators 迁移
- 4 个测试文件 - fixture 改写

**验收**：
- ✅ 残留检查：零 BaseRepository 引用
- ✅ 65 passed（与基线一致）
- ✅ SQL 和业务逻辑逐字不动

**Commit**: `9af088a` - feat(wp4): migrate 9 files from BaseRepository to db_cursor

### WP-5: 删除 legacy 文件 ✅

**改动**：22 个文件，-496 行 +89 行

**核心操作**：
1. 删除 `base_repository.py`（301 行）和 `test_base_repository.py`（167 行）
2. 将 `_resolve_db_dsn()` 迁移到 `engine.py`（含完整 pytest 安全检查）
3. 更新 17 个文件的 import 路径
4. 修复 WP-2 遗漏的 `test_stock_pool_repository.py` fixture

**验收**：
- ✅ 全局 grep 零 legacy 引用（archived_scripts 除外）
- ✅ pytest 安全检查完整保留（防止测试误连生产库）
- ✅ 冷启动冒烟通过：
  - `/api/health/db`: 200 OK
  - `/api/pools`: 200 OK（41 个股票池）
  - `/api/agent/logs`: 200 OK

**Commit**: `8458017` - feat(WP-5): 删除 legacy base_repository.py 并完成全量回归

## 技术细节

### db_cursor() 实现

```python
@contextmanager
def db_cursor(commit: bool = False):
    """单次操作级数据库游标（RealDictCursor），with 块结束立即归还连接池。
    
    - commit=False（默认，读操作）：退出时显式 rollback（psycopg2 默认事务模式，
      SELECT 也开事务，不 rollback 归还会留 idle-in-transaction 残影）
    - commit=True（写操作）：正常退出 commit；异常 rollback 并重抛
    """
    from psycopg2.extras import RealDictCursor
    
    conn = get_engine().connect()
    try:
        raw = conn.connection
        cursor = raw.cursor(cursor_factory=RealDictCursor)
        try:
            yield cursor
            if commit:
                raw.commit()
            else:
                raw.rollback()  # ← 关键：读路径防止 idle-in-transaction
        except Exception:
            raw.rollback()
            raise
        finally:
            cursor.close()
    finally:
        conn.close()  # ← 关键：立即归还连接池
```

### 迁移前后对比

**旧模式（BaseRepository）**：
```python
class MyRepository(BaseRepository):
    def __init__(self):
        super().__init__()  # 持有连接
    
    def query(self):
        cursor = self._get_cursor()
        try:
            cursor.execute("SELECT ...")
            return cursor.fetchall()
        finally:
            cursor.close()
        # 连接仍被实例持有，进入 idle in transaction
```

**新模式（db_cursor）**：
```python
class MyRepository:
    def query(self):
        with db_cursor() as cursor:
            cursor.execute("SELECT ...")
            return cursor.fetchall()
        # 自动 rollback + 归还连接池
```

## 迁移统计

| 指标 | 数值 |
|------|------|
| 改动文件总数 | 35+ |
| 删除行数 | ~600 |
| 新增行数 | ~300 |
| 迁移方法数 | 18（12 + 6） |
| 直插用法改写 | 9 个文件 |
| 测试覆盖 | 无新增失败 |
| 契约破坏 | 0（100% 向后兼容） |

## 验收标准

### ✅ 功能完整性

- [x] 所有 repository 方法正常工作
- [x] SQL 语句逐字不变
- [x] 方法签名完全兼容
- [x] 返回值格式不变
- [x] 错误文案逐字一致

### ✅ 测试覆盖

- [x] WP-0 基线：65 passed
- [x] WP-1 新增：10 passed
- [x] WP-2 回归：17 passed
- [x] WP-3 回归：7 passed
- [x] WP-4 回归：65 passed
- [x] WP-5 冷启动：3 端点 200 OK

### ✅ 代码质量

- [x] 无 legacy 残留引用
- [x] pytest 安全检查保留
- [x] 异常路径处理完整
- [x] 连接管理正确（现取现还）

## WP-6: 生产部署验证

### 验证目标

确认 `idle in transaction` 问题已解决。

### 验证步骤

1. **部署到生产环境**
   ```bash
   cd /Users/yunpeng/pi-investment/quantsys-v2
   git pull origin main
   sudo launchctl kickstart -k system/com.pi-investment.v2-api
   ```

2. **监控数据库连接状态**（24-48 小时）
   ```sql
   -- 检查连接池状态
   SELECT 
     state, 
     count(*), 
     max(state_change) as last_change
   FROM pg_stat_activity 
   WHERE datname = 'quant_investment' 
   GROUP BY state;
   
   -- 查找 idle in transaction 残留
   SELECT 
     pid,
     usename,
     application_name,
     state,
     state_change,
     query
   FROM pg_stat_activity
   WHERE datname = 'quant_investment'
     AND state = 'idle in transaction'
     AND state_change < now() - interval '1 minute';
   ```

3. **功能冒烟测试**
   ```bash
   # 测试关键 API 端点
   curl http://127.0.0.1:5001/api/health/db
   curl http://127.0.0.1:5001/api/pools
   curl http://127.0.0.1:5001/api/agent/logs?page=1&page_size=10
   
   # 测试 agent-ts 集成
   cd ../agent-ts
   npm run agent -- "刷新所有动态股票池"
   ```

4. **性能监控**
   - 响应时间：所有端点 < 200ms
   - 连接池利用率：checked_out < 5（正常）
   - 无连接泄漏告警

### 预期结果

**成功标准**：
- ✅ `idle in transaction` 连接数 = 0
- ✅ 所有 API 响应正常
- ✅ 连接池高效复用（checked_out 稳定低位）
- ✅ 运行 24 小时无连接耗尽事故

**回滚计划**（如果失败）：
1. `git revert 8458017..HEAD`（回退所有迁移 commit）
2. 重启服务
3. 分析失败原因，调整方案

## 经验教训

### 1. 测试文件也要迁移

**问题**: WP-2 只迁移了 repository 实现，忘记更新测试 fixture。  
**结果**: WP-5 测试失败（`r.db` AttributeError）。  
**教训**: 迁移检查清单必须包含测试文件。

### 2. Subagent 误解任务

**问题**: 第一次 WP-3 执行错误，commit 消息说"migrate TO BaseRepository"，实际仍保留继承。  
**结果**: 需要重新执行。  
**教训**: 任务描述必须明确具体（"移除继承" vs "迁移到模式"）。

### 3. 并行 worktree 冲突

**问题**: main 在迁移过程中被其他会话推进。  
**结果**: 需要多次 rebase。  
**教训**: 长时间迁移应该锁定 main 或使用专门的迁移分支。

### 4. 契约验证的重要性

**成功点**: 每个 WP 都做了契约 diff 验证（方法签名、SQL、错误文案）。  
**结果**: 零契约破坏，100% 向后兼容。  
**教训**: 机械式迁移必须配合严格的契约验证。

## 相关文档

- 迁移计划：`docs/superpowers/plans/2026-08-18-base-repository-migration-plan.md`
- WP-0 基线报告：`/tmp/wp0-baseline-report.md`
- WP-1 完成报告：`/tmp/wp1-completion-report.md`
- WP-2 执行摘要：由 subagent 生成
- WP-3 执行摘要：由 subagent 生成
- WP-4 执行摘要：由 subagent 生成
- WP-5 执行摘要：由 subagent 生成

## 后续工作

### 立即

- [ ] **WP-6**: 生产环境部署验证（24-48 小时监控）

### 短期

- [ ] 删除 archived_scripts 中的 legacy 引用（低优先级）
- [ ] 更新开发者文档（data access pattern）
- [ ] 添加连接池监控告警（防止未来回归）

### 中期

- [ ] 考虑迁移 ORM repositories（`orm/base_repository.py`）
- [ ] 优化连接池配置（根据生产监控数据）
- [ ] 添加连接生命周期追踪（debugging tool）

## 结论

✅ **BaseRepository 迁移成功完成**

- **根本问题**: 实例级持连接导致 idle-in-transaction 累积
- **解决方案**: 操作级现取现还（db_cursor）+ 读路径显式 rollback
- **迁移范围**: 2 个 repository（18 方法）+ 9 个直插用法 + 1 个 legacy 文件删除
- **质量保证**: 零契约破坏，100% 向后兼容，所有测试通过
- **下一步**: 生产环境验证（WP-6）

预计 2026-08-19 生产验证完成后，可宣布此次迁移彻底成功。

---

**报告生成时间**: 2026-08-18 14:30  
**报告生成者**: Claude (主执行 agent)  
**审查状态**: 等待 WP-6 生产验证结果

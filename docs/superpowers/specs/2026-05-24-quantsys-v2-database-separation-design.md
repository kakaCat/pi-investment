# quantsys-v2 测试/生产数据库分离设计

**日期**: 2026-05-24  
**状态**: 已批准  
**作者**: Claude (Kiro AI)

## 概述

为 quantsys-v2 后端实现测试数据库和生产数据库的完全分离，确保 pytest 测试自动使用测试库，其他场景（API server、CLI 工具、数据脚本）使用生产库，防止测试污染生产数据。

## 目标

1. **自动化切换**：pytest 运行时自动使用测试库，无需手动干预
2. **数据隔离**：测试数据和生产数据完全分离，互不影响
3. **安全防护**：多层检查机制防止误操作连接错误的数据库
4. **最小改动**：利用现有 conftest.py 机制，改动范围最小

## 数据库配置

### 两个独立数据库

| 数据库名 | 用途 | 配置文件 | 使用场景 |
|---------|------|---------|---------|
| `quant_investment` | 生产库 | `.env` | API server、CLI 工具、数据脚本 |
| `quant_test` | 测试库 | `.env.test` | pytest 测试专用 |

**连接信息**：
- Host: `127.0.0.1`
- Port: `5432`
- User: `mac`（或根据实际配置）
- Password: 空或根据实际配置

### 环境配置文件

**`.env`（生产环境）**：
```bash
PGHOST=127.0.0.1
PGPORT=5432
PGDATABASE=quant_investment
PGUSER=mac
PGPASSWORD=
```

**`.env.test`（测试环境）**：
```bash
PGHOST=127.0.0.1
PGPORT=5432
PGDATABASE=quant_test
PGUSER=mac
PGPASSWORD=
PYTHONDONTWRITEBYTECODE=1
```

**`.env.example`（文档模板）**：
添加清晰的注释说明两个数据库的用途和配置方式。

## 自动切换机制

### pytest 环境

1. pytest 启动时，`conftest.py` 的 `pytest_configure()` 钩子自动执行
2. 读取 `.env.test` 文件，将环境变量加载到 `os.environ`
3. 所有测试代码通过环境变量连接到 `quant_test` 数据库
4. 测试结束后，数据库连接自动关闭

### 非 pytest 环境

1. API server、CLI 工具、数据脚本启动时读取 `.env` 文件
2. 通过 `PGDATABASE=quant_investment` 连接到生产库
3. 正常执行业务逻辑

**关键点**：无需手动切换，完全自动化。

## 三层安全检查机制

### 第一层：conftest.py 启动检查

**位置**：`quantsys-v2/conftest.py`

**检查逻辑**：
```python
def pytest_configure(config):
    # ... 加载 .env.test ...
    
    # 强制验证测试数据库
    pgdatabase = os.environ.get("PGDATABASE", "")
    if not pgdatabase.endswith("_test"):
        print("\n" + "="*70)
        print("ERROR: Test database validation failed!")
        print(f"Current PGDATABASE: {pgdatabase}")
        print("Test database name must end with '_test' (e.g., 'quant_test')")
        print("Please check your .env.test configuration.")
        print("="*70 + "\n")
        sys.exit(1)
```

**作用**：
- pytest 启动时立即验证数据库配置
- 如果 `PGDATABASE` 不以 `_test` 结尾，直接中止测试
- 防止测试意外连接到生产库

### 第二层：数据库连接入口检查

**位置 1**：`quantsys-v2/core/base_repository.py`

在 `_resolve_db_dsn()` 函数末尾添加：
```python
def _resolve_db_dsn():
    # ... 现有逻辑 ...
    
    # 安全检查：pytest 环境必须使用测试库
    if dsn and "pytest" in sys.modules:
        db_name = os.environ.get("PGDATABASE", "")
        if db_name and not db_name.endswith("_test"):
            raise RuntimeError(
                f"Security check failed: Detected pytest environment but "
                f"PGDATABASE='{db_name}' is not a test database. "
                f"Test database name must end with '_test'."
            )
    
    return dsn
```

**位置 2**：`quantsys-v2/database/async_connection_pool.py`

在 `AsyncConnectionPool.__init__()` 和 `initialize()` 中添加类似检查：
```python
def __init__(self, ...):
    # ... 现有逻辑 ...
    
    # 安全检查：pytest 环境必须使用测试库
    if "pytest" in sys.modules:
        if not self.database.endswith("_test"):
            raise RuntimeError(
                f"Security check failed: Detected pytest environment but "
                f"database='{self.database}' is not a test database."
            )
```

**作用**：
- 在数据库连接建立前进行二次验证
- 即使 conftest.py 被绕过，连接时也会被拦截
- 覆盖同步连接（psycopg2）和异步连接（asyncpg）

### 第三层：文档和注释警告

**位置**：
- `conftest.py` 顶部添加注释说明
- `base_repository.py` 和 `async_connection_pool.py` 添加注释
- `.env.example` 添加详细说明
- `CLAUDE.md` 添加数据库配置章节

**作用**：
- 提醒开发者注意数据库分离规则
- 提供清晰的使用指南
- 降低误操作风险

## 检测 pytest 环境的方法

使用 Python 标准库检测：
```python
import sys

def is_pytest_running():
    return "pytest" in sys.modules
```

**原理**：
- pytest 运行时会将自己加载到 `sys.modules`
- 通过检查 `sys.modules` 可以可靠地判断是否在测试环境
- 这是 Python 社区的标准做法

## 实现清单

### 需要修改的文件

1. **quantsys-v2/conftest.py**
   - 强化 `pytest_configure()` 中的数据库验证逻辑
   - 添加清晰的错误提示信息
   - 添加顶部注释说明数据库分离机制

2. **quantsys-v2/core/base_repository.py**
   - 在 `_resolve_db_dsn()` 末尾添加 pytest 环境检查
   - 导入 `sys` 模块
   - 添加函数注释说明安全检查

3. **quantsys-v2/database/async_connection_pool.py**
   - 在 `__init__()` 中添加数据库名称检查
   - 在 `initialize()` 中添加二次验证
   - 导入 `sys` 模块
   - 添加类注释说明安全检查

4. **quantsys-v2/.env.example**
   - 添加数据库配置说明注释块
   - 明确标注生产库和测试库的用途
   - 提供测试数据库创建命令示例

5. **CLAUDE.md**
   - 在 "Environment Setup" 部分添加 "Database Configuration" 章节
   - 说明测试库和生产库的自动切换机制
   - 提供使用规范和注意事项

### 不需要修改的文件

- `.env` — 保持现有生产库配置
- `.env.test` — 已经正确配置测试库
- 其他数据库连接代码 — 通过 `base_repository.py` 和 `async_connection_pool.py` 统一管理

## 测试数据库初始化

### 创建测试数据库

```sql
-- 连接到 PostgreSQL
psql -U mac -d postgres

-- 创建测试数据库
CREATE DATABASE quant_test;

-- 退出
\q
```

### 运行 schema 迁移

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2

# 应用 schema
psql -U mac -d quant_test -f quant/quantsys/db/schema_postgres.sql

# 验证表结构
python migrations/verify_schema.py
```

### 数据隔离原则

- **测试库**：可以随时清空重建，不保留任何重要数据
- **生产库**：包含真实的历史数据、持仓、交易记录
- **测试数据**：使用 mock 数据或小规模真实数据副本

## 使用规范

### 开发者工作流

**运行测试**：
```bash
cd quantsys-v2
pytest                    # 自动使用 quant_test
pytest tests/test_xxx.py  # 自动使用 quant_test
```

**启动 API server**：
```bash
cd quantsys-v2
python api/server.py              # 自动使用 quant_investment
python start_all.py               # 自动使用 quant_investment
```

**运行数据脚本**：
```bash
cd quantsys-v2
python scripts/init_stocks.py    # 自动使用 quant_investment
python scripts/migrate_tables.py # 自动使用 quant_investment
```

### 注意事项

**禁止操作**：
- ❌ 不要在 `.env` 中配置 `PGDATABASE=quant_test`
- ❌ 不要直接运行测试文件（如 `python tests/test_xxx.py`）
- ❌ 不要在生产库上运行破坏性测试

**推荐操作**：
- ✅ 始终通过 `pytest` 命令运行测试
- ✅ 定期清空测试库数据：`psql -d quant_test -c "TRUNCATE TABLE xxx CASCADE;"`
- ✅ 如需手动连接测试库：`PGDATABASE=quant_test python script.py`

### 错误排查

**问题 1**：pytest 提示连接生产库

**解决**：
1. 检查 `.env.test` 是否存在且配置正确
2. 确认 `PGDATABASE=quant_test`
3. 删除可能存在的全局环境变量：`unset PGDATABASE`

**问题 2**：API server 连接测试库

**解决**：
1. 检查 `.env` 文件配置
2. 确认 `PGDATABASE=quant_investment`
3. 重启 API server

**问题 3**：安全检查报错

**解决**：
1. 这是正常的保护机制
2. 检查当前环境和数据库配置是否匹配
3. 按照错误提示修正配置

## CLAUDE.md 更新内容

在 `CLAUDE.md` 的 "Environment Setup" 部分添加：

```markdown
## Database Configuration

quantsys-v2 使用两个独立的 PostgreSQL 数据库实现测试/生产数据隔离：

| 数据库 | 名称 | 用途 | 配置文件 |
|--------|------|------|---------|
| 生产库 | `quant_investment` | API server、CLI 工具、数据脚本 | `.env` |
| 测试库 | `quant_test` | pytest 测试专用 | `.env.test` |

### 自动切换机制

- **pytest 测试**：通过 `conftest.py` 自动加载 `.env.test`，连接 `quant_test`
- **其他场景**：读取 `.env`，连接 `quant_investment`
- **无需手动切换**：系统根据运行环境自动选择数据库

### 三层安全检查

1. **conftest.py 启动检查**：pytest 启动时验证 `PGDATABASE` 必须以 `_test` 结尾
2. **连接入口检查**：`base_repository.py` 和 `async_connection_pool.py` 在建立连接前验证
3. **文档警告**：代码注释和文档明确说明数据库分离规则

### 测试数据库初始化

```bash
# 创建测试数据库
psql -U mac -d postgres -c "CREATE DATABASE quant_test;"

# 应用 schema
cd quantsys-v2
psql -U mac -d quant_test -f quant/quantsys/db/schema_postgres.sql

# 验证
python migrations/verify_schema.py
```

### 使用规范

```bash
# 运行测试（自动使用 quant_test）
pytest

# 启动 API（自动使用 quant_investment）
python api/server.py

# 手动指定测试库（特殊场景）
PGDATABASE=quant_test python scripts/xxx.py
```

**注意**：不要在 `.env` 中配置 `PGDATABASE=quant_test`，测试库配置仅在 `.env.test` 中。
```

## 实现优先级

### P0（必须实现）

1. 强化 `conftest.py` 的数据库验证逻辑
2. 在 `base_repository.py` 添加安全检查
3. 在 `async_connection_pool.py` 添加安全检查
4. 更新 `CLAUDE.md` 添加数据库配置章节

### P1（建议实现）

1. 更新 `.env.example` 添加详细注释
2. 在关键文件添加代码注释
3. 创建测试数据库初始化脚本

### P2（可选）

1. 添加数据库连接监控日志
2. 创建测试数据 fixture 生成工具
3. 编写数据库分离的集成测试

## 风险和限制

### 风险

1. **绕过 pytest**：如果直接运行测试文件（`python tests/test_xxx.py`），会绕过 conftest.py
   - **缓解**：第二层检查（连接入口）会拦截
   
2. **环境变量污染**：如果 shell 中设置了全局 `PGDATABASE`，可能覆盖配置文件
   - **缓解**：conftest.py 优先级高于 shell 环境变量

3. **异步连接池**：如果直接使用 asyncpg 而不通过 `AsyncConnectionPool`，会绕过检查
   - **缓解**：代码审查确保所有异步连接都通过连接池

### 限制

1. **单机部署**：当前设计假设测试库和生产库在同一 PostgreSQL 实例
2. **手动创建**：测试数据库需要手动创建，未自动化
3. **Schema 同步**：测试库和生产库的 schema 需要手动保持一致

## 后续优化方向

1. **自动化测试库创建**：在 CI/CD 中自动创建和初始化测试库
2. **Schema 版本管理**：使用 Alembic 或 Flyway 管理数据库迁移
3. **测试数据 Fixture**：创建标准的测试数据集，提高测试可重复性
4. **连接池监控**：添加数据库连接池的监控和告警
5. **多环境支持**：扩展到 dev、staging、production 多环境

## 总结

本设计通过强化现有的 conftest.py 机制，实现了测试库和生产库的自动分离，具有以下特点：

- ✅ **自动化**：pytest 自动使用测试库，无需手动干预
- ✅ **安全**：三层检查机制防止误操作
- ✅ **最小改动**：利用现有机制，改动范围小
- ✅ **易维护**：配置集中在 `.env` 和 `.env.test`
- ✅ **可扩展**：未来可扩展到更多环境

该方案符合 Python 测试的最佳实践，风险低，易于实施和维护。

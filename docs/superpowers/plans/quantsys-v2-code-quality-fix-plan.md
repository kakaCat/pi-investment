# QuantSys V2 代码质量修复计划

> **目标**: 系统性修复审计发现的 11 大类问题
> **预计工期**: 4-6 周（按 1 个 agent 全职计算）
> **优先级**: P0 > P1 > P2
> **创建日期**: 2026-08-18
> **对应审计报告**: `docs/superpowers/reports/quantsys-v2-audit-report-2026-08-18.md`

---

## 一、问题总览与修复顺序

```
Phase 1 (Week 1): 基础设施修复 —— 异常体系 + 日志统一
Phase 2 (Week 2): 架构清理 —— Flask 删除 + 路由注册强化
Phase 3 (Week 3): 数据访问治理 —— akshare 迁移 + sys.path 清理
Phase 4 (Week 4): 代码质量 —— TODO 清理 + 线程管理 + 配置统一
Phase 5 (Week 5-6): 收尾 —— 测试验证 + 文档更新
```

---

## 二、Phase 1: 异常体系与日志统一 (Week 1)

### 任务 1: 建立业务异常层次结构

**目标**: 替换 2,274 处裸 `except Exception`，建立可区分的异常类型

**新建文件**: `domain/exceptions.py`

```python
"""业务异常层次结构

使用方式:
    # 路由层捕获特定异常返回对应 HTTP 状态码
    try:
        service.do_something()
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e))
"""


class DomainError(Exception):
    """领域层基础异常"""
    pass


class NotFoundError(DomainError):
    """资源不存在"""
    pass


class ValidationError(DomainError):
    """参数校验失败"""
    pass


class ConflictError(DomainError):
    """资源冲突（如重复创建）"""
    pass


class ExternalServiceError(DomainError):
    """外部服务调用失败（akshare/eastmoney 等）"""
    pass


class DatabaseError(DomainError):
    """数据库操作失败"""
    pass


class AuthenticationError(DomainError):
    """认证失败"""
    pass


class AuthorizationError(DomainError):
    """权限不足"""
    pass
```

**修改文件**: `adapters/inbound/fastapi_app/main.py`

替换全局异常处理器：

```python
from domain.exceptions import (
    DomainError, NotFoundError, ValidationError, ConflictError,
    ExternalServiceError, DatabaseError, AuthenticationError, AuthorizationError
)

# 移除旧的宽泛处理器
# @app.exception_handler(Exception)  ← 删除这行

# 添加分层异常处理器
@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    logger.warning(f"Not found: {exc}", path=request.url.path)
    return JSONResponse(status_code=404, content={"success": False, "error": str(exc)})

@app.exception_handler(ValidationError)
async def validation_handler(request: Request, exc: ValidationError):
    logger.warning(f"Validation failed: {exc}", path=request.url.path)
    return JSONResponse(status_code=422, content={"success": False, "error": str(exc)})

@app.exception_handler(ExternalServiceError)
async def external_service_handler(request: Request, exc: ExternalServiceError):
    logger.error(f"External service error: {exc}", path=request.url.path)
    return JSONResponse(status_code=502, content={"success": False, "error": "External service unavailable"})

@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    logger.warning(f"Domain error: {exc}", path=request.url.path)
    return JSONResponse(status_code=400, content={"success": False, "error": str(exc)})

# 最后的兜底 —— 只捕获真正未预期的异常
@app.exception_handler(Exception)
async def unexpected_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unexpected error: {exc}", path=request.url.path)
    # 生产环境不暴露内部错误细节
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error"}
    )
```

**批量替换策略**:

不要一次性改 2,274 处，按模块分批：

```bash
# Step 1: 先改核心模块（adapters/inbound/fastapi_app/routes/）
# Step 2: 改 application/services/
# Step 3: 改 adapters/outbound/repositories/
# Step 4: 改 infrastructure/
# Step 5: 改 domain/quantlib/（量大但优先级低）
```

**替换模式**:

```python
# 旧代码
except Exception as e:
    logger.error(f"Failed: {e}")
    return {"success": False, "error": str(e)}

# 新代码 —— 根据上下文选择具体异常类型
except ExternalServiceError as e:
    logger.error(f"Data provider failed: {e}")
    raise  # 让上层处理
except Exception as e:
    logger.exception(f"Unexpected error in xxx: {e}")
    raise DomainError(f"Operation failed: {e}") from e
```

**关键原则**:
1. 底层（Repository/Service）捕获具体异常，包装为 DomainError 子类，然后 `raise`
2. 路由层捕获 DomainError 子类，转换为对应的 HTTP 状态码
3. 只有真正未预期的异常才由全局处理器捕获
4. 绝不 `except Exception: pass` 或静默吞掉异常

---

### 任务 2: 统一日志系统

**目标**: 清理 8,151 处 `print()`，统一使用 structlog

**步骤**:

1. **添加 lint 规则** —— 禁止新增 `print()`

新建 `.ruff.toml`（或添加到现有配置）:
```toml
[lint]
select = ["T201"]  # 禁止 print()

[lint.per-file-ignores]
# 允许以下文件使用 print（脚本/调试工具）
"scripts/*" = ["T201"]
"tools/*" = ["T201"]
"debug_*.py" = ["T201"]
"diagnose_*.py" = ["T201"]
"examples/*" = ["T201"]
"tests/*" = ["T201"]
"archived_scripts/*" = ["T201"]
"live_trading/*" = ["T201"]  # 实盘脚本允许 print
```

2. **批量替换 print → logger**

```bash
# 先处理核心模块（排除已允许的文件）
# 使用 sed 或 Python 脚本批量替换

# 模式 1: print("message") → logger.info("message")
# 模式 2: print(f"...{var}") → logger.info("...", var=var)
# 模式 3: print(e) → logger.exception("Error", exc=e)
```

3. **为缺少 logger 的模块添加**

每个 Python 文件顶部应有：
```python
import structlog
logger = structlog.get_logger(__name__)
```

**批量处理脚本** (`scripts/migrate_print_to_logger.py`):

```python
"""批量将 print() 迁移到 structlog"""
import ast
import sys
from pathlib import Path

EXCLUDED_DIRS = {
    'venv', '__pycache__', 'scripts', 'tools', 'examples',
    'tests', 'archived_scripts', 'live_trading'
}
EXCLUDED_FILES = {'debug_', 'diagnose_', 'test_', 'fix_'}


def should_process(filepath: Path) -> bool:
    """判断文件是否需要处理"""
    parts = filepath.parts
    if any(p in EXCLUDED_DIRS for p in parts):
        return False
    if any(filepath.name.startswith(prefix) for prefix in EXCLUDED_FILES):
        return False
    return True


def migrate_file(filepath: Path):
    """将文件中的 print() 替换为 logger 调用"""
    content = filepath.read_text()

    # 检查是否已有 logger 定义
    has_logger = 'structlog.get_logger' in content

    # 简单替换（复杂情况需要 AST 分析）
    lines = content.split('\n')
    new_lines = []
    print_count = 0

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('print('):
            print_count += 1
            # 提取 print 内容
            # print("msg") → logger.info("msg")
            # print(f"...") → logger.info("...", key=value)
            # 这里需要更复杂的解析
            indent = line[:len(line) - len(line.lstrip())]
            new_lines.append(f"{indent}# TODO: migrate print → logger")
            new_lines.append(line)
        else:
            new_lines.append(line)

    if print_count > 0 and not has_logger:
        # 在 import 后添加 logger 定义
        import_idx = next((i for i, l in enumerate(new_lines) if l.startswith('import ') or l.startswith('from ')), -1)
        if import_idx >= 0:
            # 找到最后一个 import
            last_import = import_idx
            for i in range(import_idx + 1, len(new_lines)):
                if new_lines[i].startswith('import ') or new_lines[i].startswith('from '):
                    last_import = i
            new_lines.insert(last_import + 1, '')
            new_lines.insert(last_import + 2, 'import structlog')
            new_lines.insert(last_import + 3, 'logger = structlog.get_logger(__name__)')

    if print_count > 0:
        filepath.write_text('\n'.join(new_lines))
        print(f"Migrated {print_count} print() in {filepath}")


def main():
    root = Path('/Users/yunpeng/pi-investment/quantsys-v2')
    for pyfile in root.rglob('*.py'):
        if should_process(pyfile):
            migrate_file(pyfile)


if __name__ == '__main__':
    main()
```

---

## 三、Phase 2: 架构清理 (Week 2)

### 任务 3: 删除 Flask 路由和废弃代码

**目标**: 清理 `adapters/inbound/api/` 目录，删除 62 个 Flask 路由文件

**步骤**:

1. **确认 FastAPI 路由已覆盖所有 Flask 功能**

```bash
# 生成 Flask 路由列表
grep -r "@.*route" adapters/inbound/api/routes/ | grep -v __pycache__

# 生成 FastAPI 路由列表
grep -r "@router\." adapters/inbound/fastapi_app/routes/ | grep -v __pycache__

# 对比差异
```

2. **删除确认清单**

```
❌ 删除: adapters/inbound/api/routes/        (全部 62 个文件)
❌ 删除: adapters/inbound/api/server.py      (Flask 启动入口)
❌ 删除: adapters/inbound/api/server_websocket.py
❌ 删除: adapters/inbound/api/decorators.py
❌ 删除: adapters/inbound/api/error_handlers.py
❌ 删除: adapters/inbound/api/models.py
❌ 删除: adapters/inbound/api/response_builder.py

➡️ 保留: adapters/inbound/api/MIGRATION_GUIDE.py (供参考)
➡️ 保留: adapters/inbound/api/__init__.py (空文件，兼容旧 import)
```

3. **清理 main.py 中的 Flask parity 路由**

删除以下代码：
```python
# 删除这些 parity 路由导入和注册
from adapters.inbound.fastapi_app.routes.charts_async import flask_parity_router
from adapters.inbound.fastapi_app.routes.backtest_async import flask_parity_router as backtest_flask_parity_router
# ... 其他 parity 路由
```

4. **更新 CLAUDE.md**

移除 Flask 相关章节，更新启动命令。

---

### 任务 4: 路由注册失败时中断启动

**目标**: 核心路由注册失败时中断启动，非核心路由失败时告警但继续

**修改**: `adapters/inbound/fastapi_app/main.py`

```python
def register_routes():
    """注册所有路由 —— 核心路由失败时中断启动"""

    # ===== P0 核心路由 —— 失败时中断 =====
    CRITICAL_ROUTES = [
        ('health', 'adapters.inbound.fastapi_app.routes.health_async'),
        ('market', 'adapters.inbound.fastapi_app.routes.market_async'),
        ('auth', 'adapters.inbound.fastapi_app.routes.auth_async'),
        ('scheduler_webhook', 'api.internal.scheduler_webhook'),
    ]

    for name, module_path in CRITICAL_ROUTES:
        try:
            module = __import__(module_path, fromlist=['router'])
            router = getattr(module, 'router')
            app.include_router(router)
            logger.info(f"✅ Registered (critical): {name}")
        except ImportError as e:
            logger.error(f"❌ CRITICAL route failed: {name} - {e}")
            raise RuntimeError(f"Critical route '{name}' failed to register: {e}")

    # ===== P1 业务路由 —— 失败时告警但继续 =====
    OPTIONAL_ROUTES = [
        ('executions', 'adapters.inbound.fastapi_app.routes.executions_async'),
        ('analysis', 'adapters.inbound.fastapi_app.routes.analysis_async'),
        ('pools', 'adapters.inbound.fastapi_app.routes.pools_async'),
        ('signals', 'adapters.inbound.fastapi_app.routes.signals_async'),
        # ... 其他路由
    ]

    failed_routes = []
    for name, module_path in OPTIONAL_ROUTES:
        try:
            module = __import__(module_path, fromlist=['router'])
            router = getattr(module, 'router')
            app.include_router(router)
            logger.info(f"✅ Registered: {name}")
        except ImportError as e:
            logger.warning(f"⚠️ Optional route failed: {name} - {e}")
            failed_routes.append(name)

    if failed_routes:
        logger.warning(f"⚠️ {len(failed_routes)} optional routes failed: {failed_routes}")

    # 启动报告
    logger.info("=" * 60)
    logger.info(f"Routes registered: {len(CRITICAL_ROUTES) + len(OPTIONAL_ROUTES) - len(failed_routes)} total")
    if failed_routes:
        logger.info(f"Failed routes: {failed_routes}")
    logger.info("=" * 60)
```

---

## 四、Phase 3: 数据访问治理 (Week 3)

### 任务 5: 迁移直接 akshare/tushare 导入到 DataProviderManager

**目标**: 将 67 个文件的直接导入迁移到统一数据访问层

**步骤**:

1. **生成迁移清单**

```bash
# 找出所有直接导入的文件
find quantsys-v2 -name "*.py" -not -path "*/venv/*" | xargs grep -l "import akshare\|import tushare"
```

2. **分析每个文件的使用模式**

```bash
# 对每个文件，提取 akshare 调用模式
grep -n "ak\." file.py
# 或
grep -n "akshare\." file.py
```

3. **替换模式**

```python
# 旧代码
import akshare as ak
df = ak.stock_zh_a_hist(symbol='600519', period='daily', start_date='2024-01-01')

# 新代码
from adapters.outbound.datasources.manager import get_data_provider_manager

manager = get_data_provider_manager()
result = manager.get_klines('600519', 'daily', '2024-01-01', '2024-12-31')
if result['success']:
    df = result['data']
else:
    raise ExternalServiceError(f"Failed to fetch klines: {result.get('error')}")
```

4. **批量迁移脚本**

```python
# scripts/migrate_akshare_usage.py
"""分析并辅助迁移 akshare 直接导入"""
import ast
from pathlib import Path

AKSHARE_PATTERNS = {
    'stock_zh_a_hist': ('get_klines', ['symbol', 'period', 'start_date', 'end_date']),
    'stock_zh_a_spot': ('get_quotes', []),
    # ... 更多映射
}


def analyze_file(filepath: Path) -> dict:
    """分析文件中的 akshare 使用情况"""
    content = filepath.read_text()
    tree = ast.parse(content)

    usages = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # 检查是否是 akshare 调用
            func_name = ast.unparse(node.func) if hasattr(ast, 'unparse') else str(node.func)
            if 'ak.' in func_name or 'akshare.' in func_name:
                usages.append({
                    'line': node.lineno,
                    'function': func_name,
                    'args': [ast.unparse(arg) for arg in node.args],
                })

    return {
        'file': str(filepath),
        'import_line': None,  # TODO: find import line
        'usages': usages,
    }


def main():
    root = Path('/Users/yunpeng/pi-investment/quantsys-v2')
    for pyfile in root.rglob('*.py'):
        if 'venv' in str(pyfile) or '__pycache__' in str(pyfile):
            continue
        content = pyfile.read_text()
        if 'akshare' in content or 'import ak' in content:
            result = analyze_file(pyfile)
            if result['usages']:
                print(f"\n{'='*60}")
                print(f"File: {result['file']}")
                print(f"Usages: {len(result['usages'])}")
                for u in result['usages']:
                    print(f"  Line {u['line']}: {u['function']}({', '.join(u['args'])})")


if __name__ == '__main__':
    main()
```

---

### 任务 6: 清理 sys.path.insert

**目标**: 将 236 处 `sys.path.insert` 减少到 10 处以下

**步骤**:

1. **项目根目录统一加入 PYTHONPATH**

修改 `activate-py313.sh`（或创建 `.env` 文件）：
```bash
# 在 activate 脚本末尾添加
export PYTHONPATH="/Users/yunpeng/pi-investment/quantsys-v2:${PYTHONPATH}"
```

2. **删除各文件中的重复 path 修改**

```bash
# 查找所有 sys.path.insert
grep -rn "sys.path.insert" quantsys-v2 --include="*.py" | grep -v venv

# 对于每个文件，如果插入的是项目根目录，删除该代码
# 只保留真正需要特殊路径的文件（如脚本）
```

3. **保留的例外**

```python
# 允许保留的情况：
# 1. 独立脚本（不在项目内运行）
# 2. 需要导入同级但不同包模块的特殊情况
# 3. main.py 中的根目录插入（启动入口）
```

---

## 五、Phase 4: 代码质量提升 (Week 4)

### 任务 7: TODO/FIXME 清理

**目标**: 将 113 处 TODO 减少到 30 处以下

**步骤**:

1. **生成 TODO 清单**

```bash
grep -rn "TODO\|FIXME\|XXX\|HACK" quantsys-v2 --include="*.py" | grep -v venv > /tmp/todo_list.txt
```

2. **分类处理**

| 类型 | 处理方式 |
|------|---------|
| 已实现但未删除的 TODO | 直接删除 |
| 不再需要的功能 | 删除相关代码和 TODO |
| 需要实现的功能 | 转为 GitHub Issue |
| 文档/注释改进 | 立即完成 |

3. **高优先级 TODO 处理**

```python
# application/services/game_alert_service.py:217
# TODO: 实现持仓风险检查 → 必须实现

# application/services/opponent_behavior_service.py:122
# TODO: 这里需要获取市场整体资金流向，暂时使用模拟逻辑 → 转为 Issue

# application/services/learning_engine.py:6
# TODO: 实现AgentDecisionRepository后启用完整功能 → 评估是否还需要
```

---

### 任务 8: 线程统一管理

**目标**: 将 34 处 `threading.Thread` 统一使用 ThreadPoolExecutor

**步骤**:

1. **创建线程池管理器**

新建 `infrastructure/concurrency/thread_manager.py`:

```python
"""统一线程池管理

使用方式:
    from infrastructure.concurrency.thread_manager import get_thread_pool

    pool = get_thread_pool("scheduler", max_workers=4)
    future = pool.submit(task_function, arg1, arg2)
    result = future.result(timeout=30)
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional

_pools: Dict[str, ThreadPoolExecutor] = {}
_lock = threading.Lock()


def get_thread_pool(name: str, max_workers: int = 4) -> ThreadPoolExecutor:
    """获取或创建命名线程池"""
    with _lock:
        if name not in _pools:
            _pools[name] = ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix=f"{name}-worker"
            )
        return _pools[name]


def shutdown_all_pools(wait: bool = True):
    """关闭所有线程池（应用退出时调用）"""
    with _lock:
        for name, pool in _pools.items():
            pool.shutdown(wait=wait)
        _pools.clear()


def get_pool_status() -> Dict[str, dict]:
    """获取所有线程池状态"""
    status = {}
    with _lock:
        for name, pool in _pools.items():
            # ThreadPoolExecutor 没有直接暴露队列大小
            # 可以通过 _work_queue 访问（私有属性）
            status[name] = {
                'max_workers': pool._max_workers,
                'active_threads': len([t for t in pool._threads if t.is_alive()]),
            }
    return status
```

2. **替换现有的 threading.Thread**

```python
# 旧代码
threading.Thread(target=_run_scheduler, name="scheduler-thread", daemon=True).start()

# 新代码
from infrastructure.concurrency.thread_manager import get_thread_pool

pool = get_thread_pool("scheduler", max_workers=1)
pool.submit(_run_scheduler)
```

---

### 任务 9: 统一配置管理

**目标**: 将分散的配置统一到 Pydantic Settings

**新建**: `infrastructure/config/settings.py`

```python
"""统一配置管理

配置优先级（高到低）:
1. 环境变量
2. .env 文件
3. 代码默认值

使用方式:
    from infrastructure.config.settings import get_settings

    settings = get_settings()
    db_pool_size = settings.database.pool_size
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """数据库配置"""
    model_config = SettingsConfigDict(env_prefix='PG')

    host: str = '127.0.0.1'
    port: int = 5432
    database: str = 'quant_investment'
    user: str = ''
    password: str = ''
    pool_size: int = 20
    max_overflow: int = 20
    pool_pre_ping: bool = True
    pool_recycle: int = 3600


class SchedulerSettings(BaseSettings):
    """调度器配置"""
    model_config = SettingsConfigDict(env_prefix='SCHEDULER_')

    tick_interval_sec: int = 60
    misfire_grace_time_sec: int = 300
    zombie_timeout_hours: int = 6
    use_agent_os: bool = True
    agent_os_url: str = 'http://127.0.0.1:8080'


class APISettings(BaseSettings):
    """API 服务配置"""
    model_config = SettingsConfigDict(env_prefix='QUANTSYS_')

    host: str = '127.0.0.1'
    port: int = 5001
    log_level: str = 'INFO'
    cors_origins: list[str] = Field(default_factory=lambda: ['*'])


class Settings(BaseSettings):
    """全局配置"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    api: APISettings = Field(default_factory=APISettings)

    # 直接字段（兼容旧代码）
    log_level: str = 'INFO'
    log_format: str = 'text'  # 'text' or 'json'


@lru_cache()
def get_settings() -> Settings:
    """获取全局配置单例"""
    return Settings()
```

**替换硬编码配置**:

```python
# 旧代码 (main.py)
init_engine(pool_size=20, max_overflow=20)

# 新代码
from infrastructure.config.settings import get_settings

settings = get_settings()
init_engine(
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
)
```

---

## 六、Phase 5: 测试验证 (Week 5-6)

### 任务 10: 回归测试

1. **运行全量测试**
```bash
cd /Users/yunpeng/pi-investment/quantsys-v2
source activate-py313.sh
pytest -x --tb=short
```

2. **关键路径验证**
```bash
# API 启动测试
python -c "from adapters.inbound.fastapi_app.main import app; print('OK')"

# 数据库连接测试
python -c "from infrastructure.persistence.database.engine import get_engine; e = get_engine(); print(e.url)"

# Agent OS 连接测试
python -c "from application.services.agent_os_client import get_agent_os_client; c = get_agent_os_client(); print(c.base_url)"
```

3. **性能基准测试**
```bash
# 连接池压力测试
python tests/performance/test_connection_pool.py

# API 响应时间测试
python tests/performance/test_api_latency.py
```

---

## 七、执行检查清单

### 每日检查

```bash
# 1. 运行测试
pytest -x

# 2. 检查新增问题
ruff check . --select T201,E722  # print 和裸 except

# 3. 检查类型注解覆盖率
mypy adapters/inbound/fastapi_app/routes/ --ignore-missing-imports
```

### 每周检查

```bash
# 统计指标变化
python scripts/audit_metrics.py  # 生成报告对比
```

---

## 八、风险与回滚

| 风险 | 缓解措施 |
|------|---------|
| 批量替换引入 bug | 分模块替换，每模块测试通过后再下一模块 |
| 异常体系变更影响调用方 | 保持旧异常类兼容（继承自新体系） |
| Flask 删除后发现遗漏功能 | 删除前生成完整路由对比清单 |
| 配置迁移导致启动失败 | 保留旧配置读取作为 fallback |

---

## 九、相关文件索引

| 文件 | 用途 |
|------|------|
| `domain/exceptions.py` | 新建：业务异常层次结构 |
| `infrastructure/config/settings.py` | 新建：统一配置管理 |
| `infrastructure/concurrency/thread_manager.py` | 新建：线程池管理 |
| `adapters/inbound/fastapi_app/main.py` | 修改：异常处理器、路由注册 |
| `scripts/migrate_print_to_logger.py` | 新建：print 迁移工具 |
| `scripts/migrate_akshare_usage.py` | 新建：akshare 迁移分析工具 |
| `.ruff.toml` | 新建/修改：lint 规则 |
| `pyproject.toml` | 修改：项目配置 |

---

*计划版本: v1.0*
*创建日期: 2026-08-18*

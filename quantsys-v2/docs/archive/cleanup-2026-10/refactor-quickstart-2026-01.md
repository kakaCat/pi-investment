# 中等问题重构 - 快速开始指南

**创建时间**: 2026-01-XX  
**预计时间**: 4 周  
**影响范围**: quantsys-v2 全项目

## 🎯 目标

解决 7 个中等优先级的代码质量问题，提升项目的可维护性、稳定性和开发效率。

## 📊 当前状态

运行验证脚本查看当前状态：

```bash
cd quantsys-v2
python scripts/refactor/verify_fixes.py
```

当前结果：
- ❌ sys.path.insert: 211 处待清理
- ❌ 直接导入数据源: 5 处违规
- ⚠️ 日志系统: 6873 处 print，需统一到 structlog
- ⚠️ 线程管理: 12 处直接创建线程
- ✅ pyproject.toml: 已创建

## 🚀 快速执行（按优先级）

### Week 1: 基础设施修复

#### 1. 安装项目为 Python 包（解决问题 3）

```bash
# 在 quantsys-v2 目录
pip install -e ".[dev]"

# 验证安装
python -c "from adapters.outbound.datasources.manager import get_data_provider_manager; print('✅ Import works!')"
```

#### 2. 移除 sys.path.insert hack

```bash
# 预览将要修改的内容
python scripts/refactor/remove_sys_path_hacks.py

# 实际修改（自动备份）
python scripts/refactor/remove_sys_path_hacks.py --fix

# 验证所有脚本仍可运行
pytest tests/
```

#### 3. 统一日志系统（解决问题 4）

所有新代码使用统一的日志接口：

```python
# ✅ 正确方式
from infrastructure.logging import get_logger

logger = get_logger(__name__)
logger.info("User action", user_id=123, action="login")
logger.error("Database error", error=str(e), query=query)

# ❌ 避免使用
import logging
logger = logging.getLogger(__name__)

print(f"Debug: {value}")  # 禁止 print 调试
```

在应用入口初始化日志：

```python
# adapters/inbound/fastapi_app/main.py
from infrastructure.logging.config import configure_structured_logging

# 开发环境
configure_structured_logging(level="DEBUG", json_format=False, enable_trace_id=True)

# 生产环境
configure_structured_logging(level="INFO", json_format=True, enable_trace_id=True)
```

### Week 2: 数据访问层清理

#### 4. 查找违规的数据源导入（解决问题 2）

```bash
# 生成违规报告
python scripts/refactor/find_direct_imports.py > docs/refactor/direct-imports-report.md

# 生成 JSON（用于自动化修复）
python scripts/refactor/find_direct_imports.py --output direct-imports.json
```

#### 5. 手动重构违规代码

参考模式：

```python
# ❌ Before (违规)
import akshare as ak

def get_stock_data(symbol):
    df = ak.stock_zh_a_hist(symbol=symbol, period="daily")
    return df

# ✅ After (正确)
from adapters.outbound.datasources.manager import get_data_provider_manager

def get_stock_data(symbol, start_date, end_date):
    manager = get_data_provider_manager()
    result = manager.get_klines(symbol, 'daily', start_date, end_date)
    if not result['success']:
        raise DataFetchError(result['message'])
    return result['data']
```

### Week 3: 线程和配置管理

#### 6. 统一线程管理（解决问题 5）

新代码使用 ThreadManager：

```python
# ✅ 正确方式
from infrastructure.threading import get_thread_manager

manager = get_thread_manager()
future = manager.submit(long_running_task, arg1, arg2, name="data-sync")

# 等待结果（可选）
try:
    result = future.result(timeout=60)
except TimeoutError:
    logger.error("Task timeout")

# ❌ 避免使用
import threading
threading.Thread(target=task, daemon=True).start()
```

重构现有代码：

```bash
# 查找所有直接创建线程的地方
grep -rn "threading.Thread(" --include="*.py" | grep -v "test_" | grep -v "infrastructure/threading"

# 逐个重构为 ThreadManager
```

#### 7. 统一配置管理（解决问题 6）

使用 Pydantic Settings（已有基础，需扩展）：

```python
from infrastructure.config import get_settings

settings = get_settings()

# 使用配置
db_dsn = settings.database.dsn
api_port = settings.api.port
log_level = settings.logging.level
```

### Week 4: TODO 清理

#### 8. TODO/FIXME 分类和清理（解决问题 1）

```bash
# 生成分类清单
python scripts/refactor/classify_todos.py > docs/refactor/todo-inventory.md

# 按优先级修复
# P0: 立即修复（安全、核心功能）
# P1: 2周内修复（重要功能）
# P2: 1个月内修复或转 Issue
# P3: 转 GitHub Issue 或删除
```

修复策略：
- **实现未完成功能**: 接入真实 Service，完成 API 逻辑
- **删除过时 TODO**: 已完成或不再需要的
- **转为 Issue**: 长期规划项，创建 GitHub Issue 并删除代码中的 TODO

## 🔍 持续验证

每次修改后运行验证：

```bash
# 快速验证
python scripts/refactor/verify_fixes.py

# 运行测试
pytest tests/

# 代码风格检查
ruff check .
black --check .
```

## 📝 提交规范

按模块分批提交，每个 PR 包含：

1. **清晰的 PR 标题**: 
   - `refactor: remove sys.path.insert hacks`
   - `refactor: migrate logging to structlog`
   - `refactor: unify thread management with ThreadManager`

2. **PR 描述包含**:
   - 修复了哪个问题
   - 修改了多少文件/行
   - 验证步骤
   - 潜在影响

3. **测试覆盖**:
   - 所有测试通过
   - 添加新测试（如果适用）

## 🎓 最佳实践

### 日志记录

```python
# 结构化日志
logger.info("order_created", order_id=123, symbol="600000", quantity=100)

# 异常日志
try:
    risky_operation()
except Exception as e:
    logger.exception("operation_failed", operation="risky", error=str(e))

# 性能监控
from infrastructure.logging import log_execution

@log_execution("ml_predict")
def predict(symbol: str):
    # 自动记录开始/结束/耗时
    pass
```

### 线程管理

```python
# 提交任务
future = thread_manager.submit(
    process_data,
    data,
    name="data-processing"
)

# 监控状态
stats = thread_manager.get_stats()
print(f"Running: {stats['running']}, Completed: {stats['completed']}")

# 优雅关闭
thread_manager.shutdown(wait=True, timeout=60)
```

### 数据访问

```python
# 统一入口
from adapters.outbound.datasources.manager import get_data_provider_manager

manager = get_data_provider_manager()

# K线数据（自动 fallback）
result = manager.get_klines('600519', 'daily', '2024-01-01', '2024-12-31')
if result['success']:
    df = result['data']

# 实时行情
result = manager.get_quote('600519')
```

## 🚨 注意事项

1. **分阶段进行**: 不要一次性修改太多文件，每次专注一个问题
2. **充分测试**: 每次修改后运行完整测试套件
3. **保留备份**: 重大重构前创建 git branch
4. **文档同步**: 更新相关文档（README, CLAUDE.md, etc.）
5. **团队沟通**: 重大架构变更需要团队 review

## 📚 相关文档

- [完整方案](./medium-issues-solution.md) - 详细的技术方案和实现细节
- [DATA_ACCESS_GUIDE.md](../../DATA_ACCESS_GUIDE.md) - 数据访问规范
- [AGENTS.md](../../AGENTS.md) - 代码规范
- [CLAUDE.md](../../CLAUDE.md) - 项目架构

## 🆘 遇到问题？

- **导入错误**: 确保已运行 `pip install -e .`
- **测试失败**: 检查是否有遗漏的 import 路径修改
- **日志不工作**: 确保在应用入口调用了 `configure_structured_logging()`
- **线程问题**: 检查是否正确调用了 `get_thread_manager()`

## ✅ 完成检查清单

- [ ] pyproject.toml 创建并安装: `pip install -e .`
- [ ] sys.path.insert 清理完成（0 处）
- [ ] 数据源直接导入清理（核心模块 0 处）
- [ ] 新代码使用 structlog
- [ ] 新代码使用 ThreadManager
- [ ] P0 TODO 全部修复
- [ ] P1 TODO 修复或转 Issue
- [ ] 所有测试通过
- [ ] 文档更新

---

**最后更新**: 2026-01-XX  
**维护者**: PI Investment Team

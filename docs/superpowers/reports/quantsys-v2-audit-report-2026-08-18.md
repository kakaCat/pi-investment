# QuantSys V2 项目审计报告

> **项目**: quantsys-v2 (PI Investment 后端服务)
> **代码规模**: 1,373 个 Python 文件，~332K 行代码
> **审计日期**: 2026-08-18
> **审计范围**: 架构、代码质量、性能、安全、运维

---

## 一、项目概览

### 1.1 基本信息

| 指标 | 数值 |
|------|------|
| Python 文件数 | 1,373 |
| 总代码行数 | ~332,000 |
| 类定义数 | 1,628 |
| 函数定义数 | 3,466 |
| Service/Repository/Handler 类 | 192 |
| 使用 async/await 的文件 | 75 |
| 直接导入 akshare/tushare 的文件 | 38 |
| 使用 psycopg2 的文件 | 57 |
| 使用 requests 库的文件 | 174 处调用 |
| 使用 httpx 的文件 | 13 处调用 |
| 线程使用处 | 34 |
| TODO/FIXME/XXX 标记 | 72 处 |
| 裸 `except Exception` | 2,260 处 |
| `sys.path.insert` 修改 | 210 处 |

### 1.2 架构层次

```
┌─────────────────────────────────────────────────────────────┐
│  Inbound Adapters (adapters/inbound/)                        │
│  ├── fastapi_app/        ← 当前主入口 (80+ 路由文件)         │
│  ├── api/                ← Flask 旧路由 (废弃保留)           │
│  ├── cli/                ← 命令行接口                        │
│  └── web/                ← Web 静态资源                      │
├─────────────────────────────────────────────────────────────┤
│  Application Layer (application/services/)                   │
│  ├── 30+ Service 类                                        │
│  ├── scheduler_handlers.py  ← Agent OS webhook 处理器        │
│  └── agent_os_client.py    ← Agent OS HTTP 客户端            │
├─────────────────────────────────────────────────────────────┤
│  Domain Layer (domain/)                                      │
│  ├── quantlib/           ← 量化核心 (因子/回测/风险/ML)       │
│  ├── strategies/         ← 策略定义                          │
│  ├── brokers/            ← 券商适配                          │
│  ├── chan/               ← 缠论分析                          │
│  └── chip_distribution/  ← 筹码分布                          │
├─────────────────────────────────────────────────────────────┤
│  Outbound Adapters (adapters/outbound/)                      │
│  ├── repositories/       ← PostgreSQL 数据访问               │
│  └── datasources/        ← 外部数据源 (akshare/eastmoney等)   │
├─────────────────────────────────────────────────────────────┤
│  Infrastructure (infrastructure/)                            │
│  ├── persistence/        ← 数据库引擎/ORM/迁移               │
│  ├── scheduler/          ← 调度器 (legacy, fallback 模式)    │
│  ├── cache/              ← 缓存服务                          │
│  ├── events/             ← 事件总线                          │
│  └── jobs/               ← 后台任务实现                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、🔴 严重问题 (P0)

### 2.1 架构债务：Flask + FastAPI 双轨并行

**问题描述**: 项目同时存在 Flask 和 FastAPI 两套路由系统，大量代码重复。

**现状**:
- `adapters/inbound/api/` - Flask 路由 (废弃但保留)
- `adapters/inbound/fastapi_app/routes/` - FastAPI 路由 (80+ 文件)
- 多个路由文件包含 `flask_parity_router` 显式标注为迁移产物

**风险**:
- 维护成本翻倍：同一功能需维护两套实现
- 行为不一致：Flask 和 FastAPI 的异常处理、序列化行为可能不同
- 新开发者困惑：不知道应该修改哪套代码

**证据**:
```python
# main.py 中显式标注的 parity 路由
from adapters.inbound.fastapi_app.routes.charts_async import flask_parity_router
from adapters.inbound.fastapi_app.routes.backtest_async import flask_parity_router as backtest_flask_parity_router
```

**建议**:
1. 制定 Flask 路由删除时间表（建议 2026-09-01 前）
2. 所有新功能只写 FastAPI 路由
3. 逐步将 Flask 独有功能迁移到 FastAPI

---

### 2.2 全局异常处理过于宽泛

**问题描述**: 2,260 处 `except Exception` 捕获，大量吞掉异常细节。

**风险**:
- 难以定位根因：异常被捕获后只记录日志，调用方无法区分错误类型
- 静默失败：某些应该中断的操作被吞掉异常后继续执行
- 调试困难：生产环境出现问题时日志信息不足

**典型代码**:
```python
# main.py 全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc)  # 可能暴露敏感信息
        }
    )
```

**建议**:
1. 定义业务异常层次结构（DomainException / ValidationException / NotFoundException 等）
2. 全局处理器只捕获未预期的异常，业务异常由各自路由处理
3. 生产环境不返回 `str(exc)` 给客户端（信息泄露风险）

---

### 2.3 路由注册脆弱性

**问题描述**: `main.py` 中 80+ 个路由使用 `try/except ImportError` 逐个注册，失败仅记录 warning 不中断启动。

**风险**:
- 静默缺失功能：某个路由导入失败，服务照常启动，但 API 不可用
- 难以发现：只有查看日志才能知道哪些路由没注册上
- 部署后才发现：生产环境缺少关键 API

**代码位置**: `main.py:370-900`

**建议**:
1. 核心路由（P0）注册失败应该中断启动
2. 非核心路由（P2）可以容错但需告警
3. 启动时输出路由注册报告（成功/失败列表）

---

### 2.4 ORM Session 治理复杂且脆弱

**问题描述**: Flask→FastAPI 迁移过程中发生连接池耗尽事故（2026-08-18），修复方案复杂且依赖框架内部实现细节。

**现状**:
- 中间件 `release_orm_session` 处理 async 路由
- `install_sync_session_cleanup()` 通过反射包装同步路由的 `dependant.call`
- 依赖 `_IncludedRouter` / `_EffectiveRouteContext` 等内部类

**风险**:
- FastAPI 升级可能破坏反射逻辑
- 新开发者难以理解这套机制
- 仍有遗漏场景（WebSocket、后台任务等）

**建议**:
1. 统一使用依赖注入管理 Session（FastAPI 原生 `Depends`）
2. 逐步迁移到 SQLAlchemy 2.0 async 模式
3. 移除 scoped_session，使用显式 Session 上下文

---

### 2.5 Webhook 执行阻塞事件循环

**问题描述**: `scheduler_webhook.py` 中 `_run_handler_blocking` 使用 `asyncio.run()` 在 worker 线程中运行 async handler，但 handler 内部可能做同步 IO。

**代码**:
```python
def _run_handler_blocking(handler, metadata):
    return asyncio.run(handler(metadata))  # 在 threadpool 中跑事件循环
```

**风险**:
- 嵌套事件循环：如果 handler 内部再调用 `asyncio.run()` 会报错
- 线程资源消耗：每个 webhook 请求创建一个事件循环
- 2026-08-18 事故：10 分钟的数据质量任务阻塞了 webhook 响应

**建议**:
1. Handler 应该明确分为 sync/async 两类
2. Sync handler 直接在线程池执行，不包装 asyncio.run()
3. Async handler 使用 `anyio` 或原生 async 支持

---

## 三、🟡 中等问题 (P1)

### 3.1 72 处 TODO/FIXME 未解决

**分布**:
- `application/services/` - 20 处（核心服务层）
- `live_trading/` - 12 处（实盘交易相关）
- `tests/` - 少量

**典型 TODO**:
```python
# application/services/game_alert_service.py:217
# TODO: 实现持仓风险检查

# application/services/opponent_behavior_service.py:122
# TODO: 这里需要获取市场整体资金流向，暂时使用模拟逻辑

# application/services/learning_engine.py:6
# TODO: 实现AgentDecisionRepository后启用完整功能
```

**建议**: 建立 TODO 追踪机制，定期评审，将高优先级 TODO 转为正式任务。

---

### 3.2 38 个文件直接导入 akshare/tushare

**违反 CLAUDE.md 数据访问规则**:
> "NEVER directly import external data libraries"

**风险**:
- 数据源切换困难：分散在各处的 akshare 调用难以统一替换
- 错误处理不一致：每个文件自己处理网络超时、IP 封禁等
- 无法享受统一降级链：DataProviderManager 的 database→baostock→tencent→akshare 链

**建议**:
1. 扫描所有直接导入，逐步迁移到 `DataProviderManager`
2. 添加 CI 检查禁止新增直接导入

---

### 3.3 210 处 `sys.path.insert` 修改

**问题描述**: 大量文件手动修改 `sys.path` 来确保导入正确。

**风险**:
- 导入顺序依赖：不同文件的 path 修改可能互相影响
- 测试困难：pytest 的导入路径与实际运行不同
- 代码异味：正常的 Python 项目不需要这么多 path 修改

**建议**:
1. 使用 `PYTHONPATH` 环境变量或 `pyproject.toml` 配置
2. 将项目根目录加入 PYTHONPATH（已在 main.py 中做）
3. 移除各文件中的重复 path 修改

---

### 3.4 日志系统不统一

**问题描述**: 项目同时使用三种日志系统：

1. **标准库 logging** - 大部分旧代码
2. **structlog** - 新代码（main.py、orchestrator_bootstrap.py 等）
3. **print()** - 7999 处（脚本、调试代码）

**风险**:
- 日志格式不一致：有的带 trace_id，有的不带
- 难以聚合分析：不同格式的日志难以统一处理
- 生产环境噪音：print 输出污染日志

**建议**:
1. 统一使用 structlog（已配置结构化日志）
2. 添加 lint 规则禁止 `print()`（保留 `logger.debug()` 替代）
3. 为所有模块注入 logger 实例

---

### 3.5 34 处线程使用缺乏统一管理

**问题描述**: 多处创建 `threading.Thread`，缺乏统一的生命周期管理。

**当前线程**:
- `main.py` lifespan: Scheduler fallback thread、WatchEngine thread、Orchestrator thread
- `application/services/watch_engine/`: 盯盘判定线程
- 各数据源 provider: 可能有自己的线程池

**风险**:
- 线程泄漏：异常退出时线程可能未清理
- 难以监控：不知道有多少线程在运行
- 资源竞争：多个线程访问同一连接池

**建议**:
1. 使用 `concurrent.futures.ThreadPoolExecutor` 统一管理
2. 为每个线程池设置名称和大小限制
3. 添加线程监控指标（活跃线程数、任务队列长度）

---

### 3.6 配置分散在多处

**问题描述**: 配置分散在环境变量、代码硬编码、YAML 文件、数据库中。

**证据**:
- `.env` 文件
- `main.py` 中的 `pool_size=20, max_overflow=20`
- `orchestrator_bootstrap.py` 中的 `_TICK_INTERVAL_SEC = 60`
- `watch_bootstrap.py` 中的各种阈值
- 数据库中的 `scheduler_tasks` 表

**建议**:
1. 统一配置中心（如 Pydantic Settings）
2. 环境变量 > 配置文件 > 代码默认值 的优先级
3. 配置变更热加载（不需要重启服务）

---

### 3.7 测试覆盖率和质量

**问题描述**:
- 72 个 TODO 中有部分在测试文件中
- `conftest.py` 有复杂的数据库安全检查逻辑
- 部分测试依赖外部服务（akshare、数据库）

**建议**:
1. 核心模块测试覆盖率目标 > 80%
2. 外部依赖使用 mock
3. 添加集成测试标记，与单元测试分离

---

## 四、🟢 轻微问题 (P2)

### 4.1 代码风格不一致

- 引号混用：单引号和双引号
- 注释语言：中文和英文混用
- 类型注解：部分文件有，部分没有
- docstring 格式：Google style / 无标准

### 4.2 依赖管理

- `requirements.txt` 有多个变体（`-fastapi.txt`、`-di.txt`、`-standardization.txt`）
- 没有 `pyproject.toml` 或 `setup.py`
- 依赖版本未锁定（没有 `requirements.lock`）

### 4.3 文档分散

- 设计文档在 `docs/superpowers/specs/`
- 使用指南在 `docs/guides/`
- API 文档在代码 docstring 中
- 没有统一的文档站点

### 4.4 废弃代码未清理

- `archived_scripts/` 中的旧脚本
- Flask 路由文件（标记为废弃但仍在代码库）
- `infrastructure/scheduler/scheduler.py`（legacy，fallback 模式）

---

## 五、✅ 做得好的地方

### 5.1 架构设计

- **六边形架构**：清晰的 Ports & Adapters 分层
- **双防腐层**：CLI/API → Services → Repositories
- **Pipeline 模式**：因子 → 模型 → 回测的可组合流程

### 5.2 数据库安全

- **三层防护**：conftest.py → base_repository.py → async_base_repository.py
- **测试库强制后缀**：`_test`
- **fork 安全**：子进程自动重置 Engine

### 5.3 调度架构演进

- **Agent OS 集成**：Webhook 模式解耦调度与执行
- **优雅降级**：Agent OS 不可用时回退到本地调度器
- **本地审计**：即使使用外部调度，执行记录仍写入本地 PG

### 5.4 连接池治理

- **显式配置**：pool_size、max_overflow、pool_pre_ping、pool_recycle
- **监控接口**：`get_pool_status()` 可查询池状态
- **db_cursor 上下文管理器**：单次操作级游标，自动归还连接

### 5.5 错误处理文化

- **事故驱动改进**：每次生产事故都有详细根因分析和修复
  - 2026-08-18 ORM Session 池耗尽
  - 2026-08-13 daemon 静默死亡
  - 2026-08-12 WatchEngine 消失
- **记忆系统**：将教训写入 `agent_knowledge` 表

### 5.6 数据访问统一

- **DataProviderManager**：统一的数据源管理，自动降级链
- **Repository 模式**：统一的数据库访问层
- **明确的规则**：CLAUDE.md 中明确定义数据访问规范

---

## 六、优化建议汇总

### 短期（1-2 周）

| 优先级 | 任务 | 影响 |
|--------|------|------|
| P0 | 定义业务异常层次结构，替换裸 `except Exception` | 可维护性 |
| P0 | 核心路由注册失败时中断启动 | 可靠性 |
| P1 | 统一日志系统（structlog），清理 print() | 可观测性 |
| P1 | 制定 Flask 路由删除计划 | 技术债务 |

### 中期（1 个月）

| 优先级 | 任务 | 影响 |
|--------|------|------|
| P1 | 迁移 38 个文件的 akshare 直接导入到 DataProviderManager | 可维护性 |
| P1 | 统一配置管理（Pydantic Settings） | 可维护性 |
| P1 | 清理 72 处 TODO（高优先级） | 功能完整性 |
| P2 | 添加线程池统一管理和监控 | 稳定性 |

### 长期（3 个月）

| 优先级 | 任务 | 影响 |
|--------|------|------|
| P1 | ORM 迁移到 SQLAlchemy 2.0 async 模式 | 性能/稳定性 |
| P2 | 删除 Flask 路由和 archived_scripts | 技术债务 |
| P2 | 统一代码风格（ruff/black 格式化） | 可读性 |
| P2 | 建立文档站点（MkDocs/Sphinx） | 开发者体验 |

---

## 七、关键文件清单

### 核心入口
- `adapters/inbound/fastapi_app/main.py` - FastAPI 主应用
- `adapters/inbound/fastapi_app/orchestrator_bootstrap.py` - 编排器启动
- `adapters/inbound/fastapi_app/watch_bootstrap.py` - 盯盘引擎启动

### 调度相关
- `api/internal/scheduler_webhook.py` - Agent OS Webhook 接收器
- `application/services/scheduler_handlers.py` - 任务处理器
- `application/services/agent_os_client.py` - Agent OS HTTP 客户端
- `infrastructure/scheduler/scheduler.py` - 本地调度器（legacy）

### 数据访问
- `infrastructure/persistence/database/engine.py` - 数据库引擎
- `adapters/outbound/datasources/manager.py` - 数据源管理器

### 配置
- `infrastructure/config/` - 配置管理
- `.env` - 环境变量

---

## 八、风险矩阵

| 风险 | 概率 | 影响 | 等级 |
|------|------|------|------|
| Flask/FastAPI 双轨导致维护混乱 | 高 | 中 | 🔴 |
| 路由注册失败未被发现 | 中 | 高 | 🔴 |
| ORM Session 治理再次出问题 | 中 | 高 | 🔴 |
| Webhook 阻塞事件循环 | 中 | 高 | 🔴 |
| 异常吞掉导致调试困难 | 高 | 中 | 🟡 |
| 直接导入 akshare 导致 IP 封禁 | 中 | 中 | 🟡 |
| 线程泄漏 | 低 | 中 | 🟡 |
| 配置分散导致不一致 | 高 | 低 | 🟢 |

---

*报告生成时间: 2026-08-18*
*审计工具: 静态代码分析 + 人工审查*

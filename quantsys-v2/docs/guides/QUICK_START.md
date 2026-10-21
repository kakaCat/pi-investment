# Quantsys-v2 开发者快速上手

**目标读者**：新加入项目的开发者
**预计时间**：30 分钟完成环境搭建，1 小时理解架构

> 依赖与调度的权威说明见根目录 [CLAUDE.md](../../CLAUDE.md)；本文是面向上手操作的合并版
> （合并自原 DEVELOPER-QUICKSTART / DEVELOPER_ONBOARDING / PYTHON_ENVIRONMENT 三篇，2026-10-21 重组）。

---

## 第一步：环境准备（10 分钟）

### 1.1 系统要求

- macOS 或 Linux
- **Python 3.13+**（当前使用 3.13.x，不支持 3.8–3.11）
- PostgreSQL 14+
- Git

### 1.2 获取仓库并 创建虚拟环境

```bash
git clone https://github.com/your-org/pi-investment.git
cd pi-investment/quantsys-v2

# 创建并激活 Python 3.13 虚拟环境（必需，勿用系统 Python）
/opt/homebrew/bin/python3.13 -m venv venv
source activate-py313.sh   # 或 source venv/bin/activate
python --version           # 应显示 3.13.x
```

### 1.3 安装依赖

```bash
# 主依赖（权威清单是 pyproject.toml，仓库无 requirements.txt）
pip install -e .

# 二方包 editable 安装（2026-10-18 起必需，缺它们新路径 import 会失败）
pip install -e ./packages/qs_quantlib
pip install -e ./packages/qs_notification
pip install -e ./packages/qs_market_data
pip install -e ./packages/qs_sourcing
pip install -e ./packages/qs_intel
pip install -e ./packages/qs_strategy
pip install -e ./packages/qs_trading
pip install -e ./packages/qs_watch
pip install -e ./packages/qs_ops
pip install -e ./packages/qs_agenthub
```

**常见问题**：

- `psycopg2` 安装报错 → 需要 `pg_config`：
  ```bash
  export PATH="/opt/homebrew/opt/postgresql@14/bin:$PATH"
  pip install psycopg2
  ```
- `ModuleNotFoundError: No module named 'structlog'` / `'psycopg2'` → 用了系统
  全局 Python，先 `source activate-py313.sh`，`which python` 应指向
  `quantsys-v2/venv/bin/python`。
- `TypeError: unsupported operand type(s) for |: 'type' and 'type'` → Python 版本过旧，
  升级到 3.13 后重建 venv。

> ⚠️ 旧文档提到的 `python start_all.py` **已不存在**（Flask 层 2026-08-19 整体删除）。
> 不要按根 README 历史版本里的入口操作，以本文件与 CLAUDE.md 为准。

---

## 第二步：数据库配置（5 分钟）

```bash
psql postgres
CREATE DATABASE quant_investment;   # 生产库
CREATE DATABASE quant_test;         # 测试库（pytest 自动切换）
\q
```

创建 `.env`：

```bash
PGHOST=localhost
PGPORT=5432
PGDATABASE=quant_investment
PGUSER=your_username
PGPASSWORD=your_password
```

**测试库自动切换**：pytest 运行时自动改用 `quant_test`（conftest + 仓储双层运行时校验，
库名必须以 `_test` 结尾）。

---

## 第三步：启动服务（5 分钟）

### 启动 FastAPI REST API（端口 5001）

```bash
python adapters/inbound/fastapi_app/main.py
```

验证：浏览器打开 http://127.0.0.1:5001/docs 看到 Swagger UI。

### 启动 WebSocket（可选，端口 5003）

```bash
python adapters/inbound/fastapi_app/websocket_server.py
```

### 生产方式（launchd 守护）

launchd 守护 `com.pi-investment.v2-api` 已装（崩溃自动拉起）：

```bash
launchctl kickstart -k gui/501/com.pi-investment.v2-api   # 重启
launchctl list | grep pi-investment                        # 看状态
```

临时只起 API、停一切调度线程（排障用）：

```bash
DISABLE_APSCHEDULER=true DISABLE_DAILY_JOBS=true DISABLE_WATCH_ENGINE=true \
python adapters/inbound/fastapi_app/main.py
```

### 第一个 API 调用

```bash
curl http://127.0.0.1:5001/health
curl http://127.0.0.1:5001/api/pools
```

---

## 第四步：运行测试（5 分钟）

```bash
pytest                                   # 全量
pytest tests/test_kline_repository.py -v # 单模块
pytest --cov=. --cov-report=html         # 覆盖率
```

---

## 第五步：理解架构（10 分钟）

### 目录结构（六边形架构）

```
quantsys-v2/
├── domain/               # 核心领域（accounts/trading/portfolio/…，无外部依赖）
├── application/          # 用例编排层（services/）
├── adapters/
│   ├── inbound/          # fastapi_app（API 5001 / WS 5003）、cli/
│   └── outbound/         # repositories（73 文件）、datasources
├── infrastructure/       # persistence / scheduler / jobs / services(ServiceFactory)
├── packages/             # 二方包：qs_quantlib / qs_market_data / qs_ops / …
└── tests/
```

**核心原则**：

1. 依赖方向：外层 → 内层；Domain 层无外部依赖，依赖 Ports 解耦
   （架构决策记录见 [ADR-003](../adr/003-hexagonal-architecture.md)）。
2. **数据访问只走统一入口**（防重复造轮子）：
   - 外部行情/数据源 → `DataProviderManager`（`adapters/outbound/datasources/manager.py`）
   - 业务逻辑 → `DataService`
   - 数据库 → `adapters/outbound/repositories/`（FastAPI 异步路由用 `*_async_repository.py`，
     CLI/同步上下文用 `x_repository.py`）
3. **取服务一律走 `ServiceFactory`**（`infrastructure/services/service_factory.py`）。
4. 通知只经 `NotificationFacade`，禁止直连飞书 SDK。

---

## 第六步：开发你的第一个功能（30 分钟）

示例：新增一个评分端点。四步走——领域模型（可选）→ Service → 路由 → 注册。

### 6.1 创建 Service（注意分层纪律）

```python
# application/services/stock_scoring_service.py

class StockScoringService:
    def __init__(self):
        # ✅ 局部导入具体实现 + 接口类型注解（依赖倒置）
        from domain.ports.repository_ports_extended import IStockRepository
        from adapters.outbound.repositories.stock_repository import StockORMRepository
        self.stock_repo: IStockRepository = StockORMRepository()

    def calculate_score(self, symbol: str, date: str) -> float:
        klines = ...  # 通过仓储/数据服务取数，禁止在应用层 import akshare 等外部库
        momentum = self._calc_momentum(klines)
        value = self._calc_value(symbol)
        return momentum * 0.6 + value * 0.4
```

**分层三条铁律**（违反项会被架构检测工具抓住）：

- ❌ 应用层顶层 import 适配器 → ✅ 放到 `__init__` 内局部 import
- ❌ 实例属性无接口注解 → ✅ `self.repo: IStockRepository = ...`
- ❌ 从适配器 import 领域模型 → ✅ `from domain.models.market_data import QuoteData`

接口速查：Repository 接口在 `domain/ports/repository_ports_extended.py`，
数据源端口在 `domain/ports/datasource_ports.py`，领域模型在 `domain/models/market_data.py`。

### 6.2 创建 API 端点

```python
# adapters/inbound/fastapi_app/routes/stock_scoring.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

@router.get("/{symbol}/score")
async def get_stock_score(symbol: str, date: str | None = None):
    """获取股票综合评分（返回 insights 而非裸数据）"""
    from application.services.stock_scoring_service import StockScoringService
    score = StockScoringService().calculate_score(symbol, date or "today")
    return {"symbol": symbol, "score": score, "why": "..."}
```

### 6.3 注册路由并测试

```python
# adapters/inbound/fastapi_app/main.py
from .routes import stock_scoring
app.include_router(stock_scoring.router)
```

```python
# tests/test_stock_scoring.py
def test_calculate_score():
    ...
```

### 6.4 提交前自检

```bash
python tools/analyze_layer_violations.py   # 分层违规检测（本仓库已自带）
```

Git hooks：仓库带 `.git-hooks/`，可用 `git config core.hooksPath .git-hooks` 启用提交前检查。

---

## 常见问题 FAQ

**Q1：pytest 报 database not found？**
检查 `.env.test`（`PGDATABASE=quant_test`）与 `.env` 配置。

**Q2：API 返回 500？**
看服务日志 → 验证 `psql quant_investment` 可连 → `echo $PGDATABASE` 验环境变量。
数据库相关高频坑（session 泄漏 / 写后读、bulk 操作等）先查
[FRAMEWORK_CONSTRAINTS](../FRAMEWORK_CONSTRAINTS.md) 顶部 TL;DR。

**Q3：如何添加新的数据源？**
`adapters/outbound/datasources/providers/` 实现 provider 接口，在 `DataProviderManager` 注册，
不要在业务代码里直接 `import akshare`。

**Q4：如何添加新的调度任务？**
在 `qs_ops` 的 `application/services/scheduler_tasks_registry.py` 登记分派，
再往 `quant.scheduler_tasks` 表插行，`POST /api/scheduler/reload` 生效。
调度归属见 [ADR-004](../adr/004-scheduling-ownership.md)；体检用
`python tools/check_scheduler_dedup.py`。

**Q5：如何重启服务？**
开发：`python adapters/inbound/fastapi_app/main.py`；
生产：`launchctl kickstart -k gui/501/com.pi-investment.v2-api`。

---

## 开发规范摘要

- 代码风格：Ruff（`ruff format .` / `ruff check .`）
- 提交信息：`feat(module): …` / `fix(module): …` / `docs(module): …`
- 测试目标：新功能必有单测，覆盖率 80%+；提交前全量测试须过

## 推荐阅读顺序

1. 本文档
2. [CLAUDE.md](../../CLAUDE.md) — 项目全景与硬规则
3. [FRAMEWORK_CONSTRAINTS](../FRAMEWORK_CONSTRAINTS.md) — ORM/Session/Repository 约束
4. [架构总览](../architecture/FUNCTIONALITY_OVERVIEW.md)
5. [最佳实践](BEST_PRACTICES.md)
6. [ADR 目录](../adr/) / [RFC 目录](../rfcs/)

---

**最后更新**：2026-10-21（docs 重组；合并原 DEVELOPER-QUICKSTART / DEVELOPER_ONBOARDING / PYTHON_ENVIRONMENT）

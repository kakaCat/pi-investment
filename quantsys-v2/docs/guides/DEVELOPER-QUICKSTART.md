# quantsys-v2 开发者快速上手指南

**目标读者**: 新加入项目的开发者  
**预计时间**: 30 分钟完成环境搭建，1 小时理解架构

---

## 第一步：环境准备（10 分钟）

### 1.1 系统要求

- macOS 或 Linux
- Python 3.12+ （建议 3.13）
- PostgreSQL 14+
- Git

### 1.2 克隆仓库

```bash
git clone https://github.com/your-org/pi-investment.git
cd pi-investment/quantsys-v2
```

### 1.3 安装 Python 依赖

```bash
# 激活 Python 3.13 环境
source activate-py313.sh

# 安装依赖
pip install -r requirements.txt
```

**常见问题**：
- ❌ `psycopg2-binary` 报错？→ 安装源码版本需要 `pg_config`
  ```bash
  export PATH="/opt/homebrew/opt/postgresql@14/bin:$PATH"
  pip install psycopg2
  ```

---

## 第二步：数据库配置（5 分钟）

### 2.1 创建数据库

```bash
# 连接 PostgreSQL
psql postgres

# 创建生产数据库
CREATE DATABASE quant_investment;

# 创建测试数据库
CREATE DATABASE quant_test;

# 退出
\q
```

### 2.2 配置环境变量

创建 `.env` 文件：

```bash
# 数据库配置
PGHOST=localhost
PGPORT=5432
PGDATABASE=quant_investment
PGUSER=your_username
PGPASSWORD=your_password

# AI 模型（可选，如果需要运行 agent-ts）
DEEPSEEK_API_KEY=sk-...
```

**测试数据库**自动切换：运行 pytest 时会自动使用 `quant_test`

---

## 第三步：启动服务（5 分钟）

### 3.1 启动 FastAPI 服务

```bash
# 启动 REST API (端口 5001)
python adapters/inbound/fastapi_app/main.py
```

**验证**：
- 浏览器打开 http://127.0.0.1:5001/docs
- 看到 Swagger UI 文档界面 ✅

### 3.2 启动 WebSocket 服务（可选）

```bash
# 新终端窗口
python adapters/inbound/fastapi_app/websocket_server.py
```

---

## 第四步：运行第一个测试（5 分钟）

### 4.1 运行测试套件

```bash
# 运行所有测试
pytest

# 运行特定模块测试
pytest tests/test_kline_repository.py -v

# 运行并查看覆盖率
pytest --cov=. --cov-report=html
open htmlcov/index.html
```

**预期结果**：
- 大部分测试通过 ✅
- 可能有少量预存在的失败（见 `docs/baseline-failing-tests.md`）

### 4.2 运行你的第一个 API 调用

```bash
# 健康检查
curl http://127.0.0.1:5001/health

# 获取股票池列表
curl http://127.0.0.1:5001/api/pools

# 获取 K 线数据
curl "http://127.0.0.1:5001/api/klines/600519.SH/daily?start_date=2026-01-01&end_date=2026-09-06"
```

---

## 第五步：理解架构（10 分钟）

### 5.1 目录结构

```
quantsys-v2/
├── domain/              # 核心业务逻辑（无外部依赖）
│   ├── accounts/       # 账户领域
│   ├── trading/        # 交易领域
│   ├── portfolio/      # 持仓领域
│   └── quantlib/       # 量化分析库
│
├── application/         # 用例编排层
│   ├── services/       # 业务服务（142 个）
│   └── jobs/           # 后台任务
│
├── adapters/            # 适配器层
│   ├── inbound/        # 入站适配器
│   │   └── fastapi_app/  # FastAPI REST/WebSocket
│   └── outbound/       # 出站适配器
│       ├── repositories/  # 数据库访问（62 个）
│       └── datasources/   # 外部数据源
│
├── infrastructure/      # 基础设施
│   ├── persistence/    # 数据库连接
│   ├── scheduler/      # 调度系统
│   └── jobs/           # 后台任务实现
│
└── tests/              # 测试（5,338 个测试用例）
```

### 5.2 六边形架构

```
┌─────────────────────────────────────────┐
│  Inbound Adapters (FastAPI)             │
│  - REST API                              │
│  - WebSocket                             │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  Application Layer (Services)            │
│  - 业务逻辑编排                           │
│  - 不依赖具体框架                         │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  Domain Layer (Pure Business Logic)      │
│  - 领域模型                               │
│  - 业务规则                               │
│  - 无外部依赖                             │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  Outbound Adapters                       │
│  - Repositories (Database)               │
│  - DataSources (akshare/baostock)        │
└─────────────────────────────────────────┘
```

**核心原则**：
1. 依赖方向：外层 → 内层
2. Domain 层无外部依赖
3. 通过接口（Ports）解耦

---

## 第六步：开发你的第一个功能（30 分钟）

### 示例：添加一个新的 API 端点

#### 6.1 创建领域模型（如果需要）

```python
# domain/analysis/stock_score.py
from dataclasses import dataclass

@dataclass
class StockScore:
    symbol: str
    date: str
    score: float
    factors: dict
```

#### 6.2 创建 Service

```python
# application/services/stock_scoring_service.py
class StockScoringService:
    def calculate_score(self, symbol: str, date: str) -> StockScore:
        """计算股票综合评分"""
        # 1. 获取数据
        klines = self.data_service.get_klines(symbol, date)
        
        # 2. 计算因子
        factors = {
            "momentum": self._calc_momentum(klines),
            "value": self._calc_value(symbol),
        }
        
        # 3. 计算综合评分
        score = factors["momentum"] * 0.6 + factors["value"] * 0.4
        
        return StockScore(symbol=symbol, date=date, score=score, factors=factors)
```

#### 6.3 创建 API 端点

```python
# adapters/inbound/fastapi_app/routes/stock_scoring.py
from fastapi import APIRouter, Depends
from application.services.stock_scoring_service import StockScoringService

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

@router.get("/{symbol}/score")
async def get_stock_score(
    symbol: str,
    date: str = None,
    service: StockScoringService = Depends(get_scoring_service)
):
    """获取股票综合评分"""
    score = service.calculate_score(symbol, date or datetime.today().strftime("%Y-%m-%d"))
    return score
```

#### 6.4 注册路由

```python
# adapters/inbound/fastapi_app/main.py
from .routes import stock_scoring

app.include_router(stock_scoring.router)
```

#### 6.5 测试

```python
# tests/test_stock_scoring.py
def test_calculate_score():
    service = StockScoringService()
    score = service.calculate_score("600519.SH", "2026-09-06")
    
    assert score.symbol == "600519.SH"
    assert 0 <= score.score <= 1
    assert "momentum" in score.factors
```

---

## 第七步：调试技巧

### 7.1 日志查看

```bash
# 查看 FastAPI 日志
tail -f ~/v2-api.log

# 查看应用日志
tail -f logs/app.log
```

### 7.2 数据库调试

```bash
# 连接数据库
psql quant_investment

# 查看表结构
\dt quant.*

# 查询数据
SELECT * FROM quant.stocks LIMIT 10;
```

### 7.3 使用 IPython 调试

```python
# 在代码中插入断点
import IPython; IPython.embed()
```

---

## 常见问题 FAQ

### Q1: 运行测试时报错 "database not found"？

**A**: 检查 `.env.test` 文件是否存在，确保 `PGDATABASE=quant_test`

### Q2: API 返回 500 错误？

**A**: 
1. 查看日志：`tail -f ~/v2-api.log`
2. 检查数据库连接：`psql quant_investment`
3. 验证环境变量：`echo $PGDATABASE`

### Q3: 如何重启服务？

**A**: 
```bash
# 方式1: 直接运行（开发）
python adapters/inbound/fastapi_app/main.py

# 方式2: launchd（生产）
launchctl kickstart -k gui/501/com.pi-investment.v2-api
```

### Q4: 如何添加新的数据源？

**A**: 
1. 在 `adapters/outbound/datasources/providers/` 创建 adapter
2. 实现 `DataProviderInterface` 接口
3. 在 `DataProviderManager` 注册

### Q5: 如何添加新的调度任务？

**A**:
1. 在 `tools/register_jobs_to_agent_os.py` 的 `JOBS` 列表添加任务定义
2. 在 `application/services/scheduler_handlers.py` 添加 handler（使用 `@register_job_handler` 装饰器）
3. 运行 `python tools/register_jobs_to_agent_os.py` 注册到 Agent OS

---

## 下一步学习

### 推荐阅读顺序

1. ✅ **本文档**（快速上手）
2. 📖 [API 使用手册](./API-GUIDE.md) - 了解所有 API 端点
3. 📖 [架构文档](../architecture/FUNCTIONALITY_OVERVIEW.md) - 深入理解系统设计
4. 📖 [数据访问指南](./DATA_ACCESS_GUIDE.md) - 学习如何正确获取数据
5. 📖 [ADR 文档](../adr/) - 了解关键架构决策

### 进阶主题

- 六边形架构深入理解
- 领域驱动设计（DDD）实践
- 策略回测系统原理
- 因子计算与机器学习模型
- Agent OS 调度系统集成

---

## 开发规范

### 代码风格

```bash
# 使用 Ruff 格式化代码
ruff format .

# 使用 Ruff 检查代码
ruff check .
```

### Git 提交规范

```
feat(module): 添加新功能
fix(module): 修复 bug
docs(module): 更新文档
refactor(module): 重构代码
test(module): 添加测试
chore(module): 构建/工具变更
```

### 测试要求

- 新功能必须有单元测试
- 关键路径需要集成测试
- 测试覆盖率目标：80%+

---

## 获取帮助

### 文档资源

- **CLAUDE.md**: 项目整体说明
- **docs/guides/**: 使用指南
- **docs/architecture/**: 架构文档
- **docs/adr/**: 架构决策记录

### 开发者社区

- GitHub Issues: 提交 bug 和功能请求
- 技术文档: 查阅详细设计文档
- 代码审查: 提交 PR 获得反馈

---

**祝你开发愉快！** 🚀

有问题随时查看文档或提问。

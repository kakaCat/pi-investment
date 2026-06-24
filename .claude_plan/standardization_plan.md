# quantsys-v2 标准化改造实施计划

**目标**: 达到互联网企业标准  
**总工期**: 18.5 人日（约 4 周）  
**改造范围**: Flask → FastAPI + 错误监控 + 日志系统 + 容器化 + 监控

---

## 📊 项目现状分析

### 代码库规模
- **API Routes**: 43 个 Blueprint，17,755 行代码
- **Services**: 43+ 业务服务
- **Tests**: 1919 个测试文件
- **架构**: DDD 六边形架构（Adapter → Application → Domain ← Infrastructure）

### 技术栈现状
```
✅ 优秀：DDD 架构 + SQLAlchemy 2.0 + Pytest
🟡 中等：Flask + logging + requirements.txt
🔴 缺失：APM、容器化、结构化日志、认证、限流
```

### 关键依赖项
```python
Flask (Web 框架)
flask-cors (CORS 支持)
flask-socketio (WebSocket)
SQLAlchemy 2.0 (ORM)
Redis 5.0+ (缓存)
PostgreSQL (数据库)
```

---

## 🎯 改造策略

### 核心原则
1. **渐进式迁移**：分阶段实施，每个阶段独立可测试
2. **零停机**：保持 Flask 运行，FastAPI 并行启动（不同端口）
3. **测试优先**：每个阶段完成后运行回归测试
4. **保持架构**：不改变 DDD 分层，只替换技术实现

### 迁移路径
```
Phase 1: 基础设施（监控、日志）→ 立即生效
Phase 2: API 框架迁移（Flask → FastAPI）→ 逐步切流
Phase 3: 容器化与部署 → 生产环境标准化
Phase 4: 高级监控 → 完善可观测性
```

---

## 📋 实施计划

### Phase 1: 基础设施强化（4 天）

#### 1.1 Sentry 错误监控（1 天）

**目标**: 捕获所有生产环境异常

**实施步骤**:
1. 安装依赖
   ```bash
   poetry add sentry-sdk
   ```

2. 创建 Sentry 配置模块
   ```
   infrastructure/monitoring/
   ├── __init__.py
   ├── sentry_config.py      # Sentry 初始化
   └── error_tracking.py     # 错误追踪装饰器
   ```

3. 修改点：
   - `infrastructure/monitoring/sentry_config.py` (新建)
   - `adapters/inbound/api/server.py` (集成 Sentry)
   - `start_all.py` (启动时初始化)

4. 测试验证：
   - 手动触发异常，验证 Sentry 上报
   - 检查堆栈、环境变量是否正确

**受益**:
- ✅ ML 工具崩溃自动上报
- ✅ 数据计算错误实时告警
- ✅ 完整堆栈追踪

---

#### 1.2 structlog 结构化日志（2 天）

**目标**: 可搜索的 JSON 日志 + 分布式追踪

**实施步骤**:
1. 安装依赖
   ```bash
   poetry add structlog python-json-logger
   ```

2. 创建日志配置
   ```
   infrastructure/logging/
   ├── __init__.py
   ├── config.py             # structlog 配置
   ├── processors.py         # 自定义处理器（过滤敏感信息）
   └── context.py            # trace ID 管理
   ```

3. 修改点：
   - 替换所有 `import logging` 为 `import structlog`
   - 修改 43 个 routes 文件的日志调用
   - 修改 43+ services 的日志调用

4. 日志格式：
   ```json
   {
     "event": "ml_predict_called",
     "level": "info",
     "timestamp": "2026-06-24T14:30:00Z",
     "trace_id": "abc-123",
     "symbol": "600000",
     "model_version": "v2.3",
     "duration_ms": 234
   }
   ```

5. 测试验证：
   - 日志输出为 JSON 格式
   - trace_id 贯穿整个请求
   - 敏感信息（密码）被过滤

**受益**:
- ✅ 修复 params: null 问题
- ✅ 可搜索、可分析
- ✅ 跨服务追踪

---

#### 1.3 JWT 认证 + API 限流（1 天）

**目标**: 保护 API 安全

**实施步骤**:
1. 安装依赖
   ```bash
   poetry add pyjwt flask-limiter
   ```

2. 创建认证模块
   ```
   infrastructure/auth/
   ├── __init__.py
   ├── jwt_manager.py        # JWT 生成/验证
   ├── decorators.py         # @require_auth 装饰器
   └── rate_limiter.py       # 限流配置
   ```

3. 修改点：
   - `adapters/inbound/api/server.py` (注册限流器)
   - 重要 routes 添加 `@require_auth` 装饰器
   - 创建 `/api/auth/login` 端点

4. 限流规则：
   - 全局：100 req/min per IP
   - 登录：5 req/min per IP
   - ML 预测：10 req/min per user

**受益**:
- ✅ 防止未授权访问
- ✅ 防止 DDoS 攻击
- ✅ 符合安全审计要求

---

### Phase 2: FastAPI 迁移（5 天）

#### 2.1 FastAPI 框架搭建（1 天）

**策略**: 并行运行 Flask (5001) + FastAPI (8000)

**实施步骤**:
1. 安装依赖
   ```bash
   poetry add fastapi uvicorn pydantic-settings slowapi
   ```

2. 创建 FastAPI 应用
   ```
   adapters/inbound/api_v2/
   ├── __init__.py
   ├── main.py               # FastAPI app factory
   ├── config.py             # 配置管理
   ├── dependencies.py       # 依赖注入
   ├── middleware/
   │   ├── cors.py
   │   ├── logging.py
   │   └── error_handler.py
   └── routers/
       └── health.py         # 健康检查（示例）
   ```

3. 启动脚本
   ```python
   # start_all.py 新增
   def run_fastapi():
       import uvicorn
       uvicorn.run(
           "adapters.inbound.api_v2.main:app",
           host="127.0.0.1",
           port=8000,
           reload=False
       )
   ```

4. 测试验证：
   - FastAPI 启动成功（8000 端口）
   - 访问 http://localhost:8000/docs 查看 Swagger
   - Flask 仍正常运行（5001 端口）

---

#### 2.2 路由迁移（第 1 批：10 个核心路由）（2 天）

**迁移优先级**:
1. Health Check（健康检查）
2. Market Overview（市场概览）
3. Stock Quote（股票行情）
4. Factor Analysis（因子分析）
5. Signal Scan（信号扫描）
6. ML Predict（模型预测）
7. Backtest（回测）
8. Portfolio（组合管理）
9. Risk Metrics（风险指标）
10. Strategy Execution（策略执行）

**迁移模板**:
```python
# Flask (旧)
@market_bp.route('/api/market/overview', methods=['GET'])
@handle_api_error
def get_market_overview():
    total_stocks = stock_repo.count_all()
    return api_response({
        'total_stocks': total_stocks
    })

# FastAPI (新)
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/v2/market", tags=["market"])

class MarketOverviewResponse(BaseModel):
    total_stocks: int
    active_stocks: int
    coverage_rate: float

@router.get("/overview", response_model=MarketOverviewResponse)
async def get_market_overview():
    """获取市场概览
    
    返回：
    - 市场统计（股票数量、活跃股票）
    - 因子覆盖率
    """
    total_stocks = stock_repo.count_all()
    active_stocks = kline_repo.count_stocks_with_data()
    
    return MarketOverviewResponse(
        total_stocks=total_stocks,
        active_stocks=active_stocks,
        coverage_rate=round(active_stocks / total_stocks * 100, 2)
    )
```

**改造原则**:
- 保持相同的业务逻辑（Service 层不变）
- 添加 Pydantic 模型（请求/响应验证）
- 使用异步（async/await）
- 自动生成 OpenAPI 文档

**测试策略**:
- 并行运行 Flask 和 FastAPI
- 使用相同的测试用例验证两者输出一致
- 性能对比测试

---

#### 2.3 路由迁移（第 2 批：剩余 33 个路由）（2 天）

**批量迁移工具**:
创建代码生成脚本自动化迁移

```python
# scripts/migration/flask_to_fastapi.py
def convert_route(flask_route_file):
    """将 Flask route 转换为 FastAPI"""
    # 解析 Flask decorator
    # 提取函数签名
    # 生成 Pydantic 模型
    # 生成 FastAPI 路由代码
    pass
```

**迁移检查清单**:
- [ ] 所有 43 个 Blueprint 已迁移
- [ ] 所有路由有 Pydantic 模型
- [ ] 所有路由有文档字符串
- [ ] 测试覆盖率 > 80%
- [ ] 性能测试通过

---

### Phase 3: 容器化与部署（3 天）

#### 3.1 Dockerfile（1 天）

**多阶段构建**:
```dockerfile
# Dockerfile
# Stage 1: Builder
FROM python:3.12-slim as builder

WORKDIR /app

# 安装 poetry
RUN pip install poetry==1.7.0

# 复制依赖文件
COPY pyproject.toml poetry.lock ./

# 导出 requirements.txt（生产依赖）
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app

# 安装运行时依赖
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s \
  CMD curl -f http://localhost:8000/health || exit 1

# 暴露端口
EXPOSE 8000

# 启动服务
CMD ["uvicorn", "adapters.inbound.api_v2.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**优化点**:
- 多阶段构建减小镜像体积
- 使用 .dockerignore 排除测试文件
- 健康检查确保容器可用

---

#### 3.2 docker-compose.yml（1 天）

**完整堆栈编排**:
```yaml
version: '3.8'

services:
  quantsys-api:
    build: .
    container_name: quantsys-api
    ports:
      - "8000:8000"
    environment:
      - PGHOST=postgres
      - PGDATABASE=quant_investment
      - REDIS_HOST=redis
      - SENTRY_DSN=${SENTRY_DSN}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    restart: unless-stopped
    networks:
      - quantsys-net
    volumes:
      - ./logs:/app/logs

  postgres:
    image: postgres:15-alpine
    container_name: quantsys-postgres
    environment:
      - POSTGRES_DB=quant_investment
      - POSTGRES_USER=${PGUSER}
      - POSTGRES_PASSWORD=${PGPASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${PGUSER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - quantsys-net

  redis:
    image: redis:7-alpine
    container_name: quantsys-redis
    ports:
      - "6379:6379"
    networks:
      - quantsys-net
    command: redis-server --appendonly yes
    volumes:
      - redisdata:/data

  prometheus:
    image: prom/prometheus:latest
    container_name: quantsys-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./infrastructure/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    networks:
      - quantsys-net

volumes:
  pgdata:
  redisdata:
  prometheus-data:

networks:
  quantsys-net:
    driver: bridge
```

---

#### 3.3 CI/CD Pipeline（1 天）

**GitHub Actions 工作流**:
```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [ main, development ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: quant_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install Poetry
        run: |
          pip install poetry==1.7.0
          poetry config virtualenvs.create false
      
      - name: Install dependencies
        run: poetry install
      
      - name: Run tests
        env:
          PGHOST: localhost
          PGDATABASE: quant_test
          PGUSER: test
          PGPASSWORD: test
          REDIS_HOST: localhost
        run: |
          pytest --cov=. --cov-report=xml --cov-report=term
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
      
      - name: Build Docker image
        run: docker build -t quantsys:${{ github.sha }} .
      
      - name: Push to registry (main branch only)
        if: github.ref == 'refs/heads/main'
        run: |
          echo "${{ secrets.DOCKER_PASSWORD }}" | docker login -u "${{ secrets.DOCKER_USERNAME }}" --password-stdin
          docker tag quantsys:${{ github.sha }} yourusername/quantsys:latest
          docker push yourusername/quantsys:latest
```

---

### Phase 4: 高级监控（2 天）

#### 4.1 Prometheus 指标采集（1 天）

**实施步骤**:
1. 安装依赖
   ```bash
   poetry add prometheus-client prometheus-fastapi-instrumentator
   ```

2. 集成到 FastAPI
   ```python
   # adapters/inbound/api_v2/main.py
   from prometheus_fastapi_instrumentator import Instrumentator
   
   app = FastAPI()
   
   # 自动采集指标
   Instrumentator().instrument(app).expose(app)
   ```

3. 自定义指标
   ```python
   # infrastructure/monitoring/metrics.py
   from prometheus_client import Counter, Histogram, Gauge
   
   # 业务指标
   ml_predict_total = Counter('ml_predict_total', 'ML predictions')
   ml_predict_duration = Histogram('ml_predict_duration_seconds', 'ML prediction latency')
   active_users = Gauge('active_users', 'Current active users')
   ```

4. Prometheus 配置
   ```yaml
   # infrastructure/monitoring/prometheus.yml
   global:
     scrape_interval: 15s
   
   scrape_configs:
     - job_name: 'quantsys-api'
       static_configs:
         - targets: ['quantsys-api:8000']
   ```

**监控指标**:
- HTTP 请求（QPS、延迟、错误率）
- 数据库连接池状态
- Redis 缓存命中率
- ML 预测耗时
- 业务指标（日活、交易量）

---

#### 4.2 Grafana 可视化（1 天）

**添加到 docker-compose**:
```yaml
grafana:
  image: grafana/grafana:latest
  container_name: quantsys-grafana
  ports:
    - "3000:3000"
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=admin
    - GF_USERS_ALLOW_SIGN_UP=false
  volumes:
    - grafana-data:/var/lib/grafana
    - ./infrastructure/monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
    - ./infrastructure/monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
  networks:
    - quantsys-net
```

**预置仪表板**:
1. API 监控面板
   - QPS / 延迟 / 错误率
   - 按端点分组
   
2. 系统资源面板
   - CPU / 内存 / 磁盘
   - 数据库连接池
   
3. 业务指标面板
   - 日活用户
   - API 调用 Top 10
   - ML 预测成功率

---

### Phase 5: Poetry 依赖管理（1 天）

#### 5.1 requirements.txt → pyproject.toml

**实施步骤**:
1. 安装 Poetry
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. 初始化项目
   ```bash
   cd quantsys-v2
   poetry init --no-interaction
   ```

3. 导入现有依赖
   ```bash
   # 从 requirements.txt 生成 pyproject.toml
   cat requirements.txt | xargs poetry add
   
   # 添加开发依赖
   poetry add --group dev pytest pytest-cov pytest-mock black ruff mypy
   ```

4. 生成锁文件
   ```bash
   poetry lock
   ```

5. 依赖分层
   ```toml
   # pyproject.toml
   [tool.poetry.dependencies]
   python = "^3.12"
   fastapi = "^0.110.0"
   uvicorn = "^0.27.0"
   sqlalchemy = "^2.0.0"
   pydantic = "^2.0.0"
   redis = "^5.0.0"
   # ... 生产依赖
   
   [tool.poetry.group.dev.dependencies]
   pytest = "^7.4.0"
   pytest-cov = "^4.1.0"
   black = "^24.0.0"
   ruff = "^0.3.0"
   # ... 开发依赖
   ```

6. 更新 Dockerfile
   ```dockerfile
   # 使用 poetry 安装
   COPY pyproject.toml poetry.lock ./
   RUN poetry install --only main --no-root
   ```

**受益**:
- ✅ 版本锁定（poetry.lock）
- ✅ 依赖分层（dev/prod）
- ✅ 自动漏洞扫描（poetry audit）

---

## 🧪 测试策略

### 单元测试
- 保持现有 1919 个测试
- 新增 FastAPI 路由测试

### 集成测试
```python
# tests/integration/test_api_parity.py
def test_flask_fastapi_parity():
    """验证 Flask 和 FastAPI 响应一致"""
    flask_response = requests.get("http://localhost:5001/api/market/overview")
    fastapi_response = requests.get("http://localhost:8000/api/v2/market/overview")
    
    assert flask_response.json()['data'] == fastapi_response.json()
```

### 性能测试
```bash
# 使用 locust 压测
locust -f tests/performance/test_api_load.py --host=http://localhost:8000
```

### 回归测试
- CI 自动运行所有测试
- 覆盖率 > 80% 才能合并

---

## 📊 项目里程碑

### Week 1（Phase 1 完成）
- ✅ Sentry 集成
- ✅ structlog 日志
- ✅ JWT + 限流
- ✅ Poetry 迁移

**交付物**:
- 错误自动上报到 Sentry
- 结构化 JSON 日志
- API 认证保护
- poetry.lock 版本锁定

### Week 2（Phase 2 第一批）
- ✅ FastAPI 框架搭建
- ✅ 10 个核心路由迁移
- ✅ OpenAPI 文档生成

**交付物**:
- FastAPI 并行运行（8000 端口）
- 10 个路由有 Swagger 文档
- 性能测试报告

### Week 3（Phase 2 完成 + Phase 3）
- ✅ 剩余 33 个路由迁移
- ✅ Docker 容器化
- ✅ docker-compose 编排
- ✅ CI/CD Pipeline

**交付物**:
- 所有 API 迁移到 FastAPI
- Docker 镜像构建成功
- CI 自动化测试通过

### Week 4（Phase 4 完成）
- ✅ Prometheus 监控
- ✅ Grafana 仪表板
- ✅ 压力测试
- ✅ 生产环境部署

**交付物**:
- 完整监控体系
- 3 个 Grafana 仪表板
- 性能优化报告
- 生产部署文档

---

## 🚀 部署流程

### 开发环境
```bash
# 1. 启动所有服务
docker-compose up -d

# 2. 查看日志
docker-compose logs -f quantsys-api

# 3. 访问服务
# API: http://localhost:8000
# Swagger: http://localhost:8000/docs
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000
```

### 生产环境
```bash
# 1. 拉取镜像
docker pull yourusername/quantsys:latest

# 2. 更新环境变量
cp .env.example .env.production
# 编辑 .env.production

# 3. 启动服务
docker-compose -f docker-compose.prod.yml up -d

# 4. 健康检查
curl http://localhost:8000/health

# 5. 监控告警
# 配置 Prometheus AlertManager
```

---

## 📈 性能目标

### 当前（Flask）
- QPS: ~50 req/s
- P99 延迟: ~800ms
- 并发支持: 100

### 改造后（FastAPI）
- QPS: ~200 req/s (4x 提升)
- P99 延迟: ~300ms (2.6x 提升)
- 并发支持: 500+ (5x 提升)

### 监控指标
- 错误率 < 0.1%
- 可用性 > 99.9%
- 平均响应时间 < 200ms

---

## 🔄 回滚计划

### 紧急回滚
如果 FastAPI 出现问题，立即切回 Flask：

```bash
# 1. 停止 FastAPI
docker-compose stop quantsys-api

# 2. 启动 Flask
python start_all.py

# 3. 更新负载均衡器
# 指向 Flask 端口 5001
```

### 数据回滚
- 数据库 schema 无变更，无需回滚
- 日志格式向后兼容

---

## 💰 成本估算

### 开发成本
- Phase 1: 4 人日
- Phase 2: 5 人日
- Phase 3: 3 人日
- Phase 4: 2 人日
- Phase 5: 1 天
- 测试调试: 3.5 人日

**总计**: 18.5 人日

### 基础设施成本（月度）
- Sentry Team: $26/月
- Docker Registry: $0（Docker Hub 免费版）
- CI/CD: $0（GitHub Actions 免费额度）
- 监控存储: $0（自建 Prometheus）

**总计**: $26/月

---

## ✅ 验收标准

### Phase 1 验收
- [ ] Sentry 能捕获异常并显示堆栈
- [ ] 日志输出为 JSON 格式
- [ ] JWT 认证生效，未授权请求返回 401
- [ ] API 限流生效，超限返回 429
- [ ] poetry.lock 生成成功

### Phase 2 验收
- [ ] 所有 43 个路由迁移完成
- [ ] Swagger 文档完整可访问
- [ ] 所有测试通过
- [ ] 性能测试达标（QPS > 150）

### Phase 3 验收
- [ ] Docker 镜像构建成功
- [ ] docker-compose up 一键启动
- [ ] 健康检查通过
- [ ] CI 测试自动运行

### Phase 4 验收
- [ ] Prometheus 采集到指标
- [ ] Grafana 仪表板显示正常
- [ ] 告警规则配置完成

---

## 📚 文档交付

1. **API 文档**: 自动生成 OpenAPI 3.0 (Swagger UI)
2. **架构文档**: 更新为 FastAPI 架构图
3. **部署文档**: Docker 部署指南
4. **运维文档**: 监控告警配置
5. **开发文档**: FastAPI 路由开发规范

---

## 🎯 成功指标

### 技术指标
- ✅ API 响应时间减少 50%+
- ✅ 错误追踪覆盖率 100%
- ✅ 日志可搜索率 100%
- ✅ 测试覆盖率 > 80%
- ✅ 容器化部署成功

### 业务指标
- ✅ 生产环境零故障迁移
- ✅ API 可用性 > 99.9%
- ✅ 部署时间从 30 分钟降至 5 分钟

---

## 📞 风险与缓解

### 风险 1：Flask → FastAPI 迁移破坏现有功能
**概率**: 中  
**影响**: 高  
**缓解**: 
- 并行运行，逐步切流
- 完整的回归测试
- 保留 Flask 作为备份

### 风险 2：43 个路由迁移工作量超预期
**概率**: 高  
**影响**: 中  
**缓解**:
- 创建代码生成工具
- 优先迁移核心路由
- 分批次迁移

### 风险 3：团队不熟悉 FastAPI
**概率**: 中  
**影响**: 低  
**缓解**:
- 提供培训文档
- FastAPI 与 Flask 语法相似
- 详细的代码示例

---

**计划制定完成，等待审批后开始实施。**

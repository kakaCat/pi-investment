# QuantSys V2 功能全景图

> 更新时间：2026-06-29
> 版本：FastAPI 2.0 (已完成 Flask → FastAPI 迁移)

## 系统定位

**QuantSys V2** 是 PI Investment 自主投资系统的**智能基础设施层**，为 AI Agent 提供数据、计算和决策支持。

```
┌─────────────────────────────────────────┐
│  agent-ts (AI 员工)                     │
│  • 自主决策                              │
│  • 定时任务                              │
│  • 博弈分析                              │
└─────────────┬───────────────────────────┘
              ↓ API 调用
┌─────────────────────────────────────────┐
│  quantsys-v2 (后端服务) ← 你在这里       │
│  • REST API (FastAPI, 端口 5001)       │
│  • WebSocket (端口 5003)               │
│  • 140+ 服务模块                        │
│  • 61 个路由文件                         │
└─────────────┬───────────────────────────┘
              ↓ 数据查询
┌─────────────────────────────────────────┐
│  web-frontend (监控面板)                 │
│  • 可视化                                │
│  • 人工监督                              │
└─────────────────────────────────────────┘
```

## 核心功能分类

### 1️⃣ 股票池管理 (Pool Management)

**核心价值**：动态股票池是 Agent 的"战场选择"系统

#### 基础功能
- ✅ **CRUD 操作**：创建、读取、更新、删除股票池
- ✅ **动态刷新**：按条件自动更新池内成员
- ✅ **成员管理**：添加/删除个股，支持备注
- ✅ **启用/禁用**：快速切换池子状态

#### 高级功能
- ✅ **多策略验证**：对池子应用多个策略回测
- ✅ **变更日志**：记录所有成员变动及原因
- ✅ **扫描范围**：获取可扫描的股票范围（universe）
- ⏳ **健康度追踪**：池子质量时间序列（P1 规划中）
- ⏳ **战场评估**：博弈优势评分（P0 规划中）

**API 端点** (前缀 `/api/pools`)：
```
POST   /                创建股票池
GET    /                列出所有池子
GET    /enabled         获取启用的池子
GET    /{pool_id}      获取池子详情
PUT    /{pool_id}      更新池子
DELETE /{pool_id}      删除池子
GET    /scan/universe  获取扫描范围
```

**相关服务**：
- `application/services/stock_pool_service.py`
- `application/services/pool_health_tracker.py`

---

### 2️⃣ 策略管理 (Strategy Management)

**核心价值**：Agent 的"武器库"，支持 5 种策略类型

#### 策略类型支持
| 类型 | 说明 | 示例 |
|------|------|------|
| `indicator` | 技术指标策略 | RSI 超卖买入 |
| `script` | 事件驱动策略 | on_bar 回调函数 |
| `trend_following` | 趋势跟踪模板 | 双均线交叉 |
| `mean_reversion` | 均值回归模板 | 布林带反转 |
| `multi_factor` | 多因子模板 | 动量+价值组合 |

#### 核心功能
- ✅ **策略 CRUD**：创建、列出、获取、更新用户策略
- ✅ **内置策略库**：18 种系统内置策略（自动同步到数据库）
- ✅ **代码验证**：安全性检查（禁止文件操作、网络请求）
- ✅ **策略运行**：执行策略生成信号
- ✅ **参数优化**：笛卡尔积网格搜索 + 并行回测（10 workers）
- ✅ **策略对比**：双策略对比回测
- ✅ **沙箱探查**：查询可用的数据列（财务指标、技术指标）

#### 可用数据列
**财务指标**（18 列，季度/年度）：
- `roe_q/y`：净资产收益率
- `gross_margin_q/y`：毛利率
- `net_profit_margin_q/y`：净利率
- `debt_ratio_q/y`：资产负债率
- `revenue_growth_q/y`：营收增长率
- `ocf_to_profit_q/y`：经营现金流/净利润
- `current_ratio_q/y`：流动比率
- `roa_q/y`：总资产收益率
- `operating_margin_q/y`：营业利润率

**技术指标**（12 列）：
- 趋势：`rsi`, `macd`, `macd_signal`, `macd_hist`
- 波动：`atr`, `bollinger_upper/middle/lower`
- 均线：`ma5`, `ma10`, `ma20`, `ma60`

**API 端点** (前缀 `/api/strategies`)：
```
GET    /                    列出所有策略
GET    /{strategy_id}       获取策略详情
POST   /                    创建策略
POST   /{strategy_id}/run   运行策略
POST   /optimize            参数搜索优化
POST   /compare             双策略对比
```

**相关服务**：
- `application/services/strategy_code_service.py` - 代码执行
- `application/services/strategy_validation_service.py` - 验证
- `application/services/strategy_optimizer.py` - 参数优化
- `domain/quantlib/engine/strategy_factory.py` - 内置策略工厂

---

### 3️⃣ 回测系统 (Backtesting)

**核心价值**：验证策略有效性，支持真实回测打分

#### 核心功能
- ✅ **单策略回测**：完整的回测引擎，支持止损/止盈
- ✅ **组合策略回测**：多策略联合回测
- ✅ **参数优化回测**：100 组参数 < 60s（并行加速）
- ✅ **回测历史**：保存和查询历史回测记录
- ✅ **性能指标**：Sharpe、最大回撤、胜率、年化收益等

#### 回测指标摘要
```json
{
  "summary": {
    "total_trades": 45,
    "win_rate": 0.62,
    "sharpe_ratio": 1.85,
    "max_drawdown": -0.12,
    "annual_return": 0.28,
    "total_return": 0.85
  },
  "trades": [...]  // 详细交易记录
}
```

**API 端点** (前缀 `/api`)：
```
POST /indicators/backtest      回测指标策略（含 summary）
POST /strategies/optimize      参数搜索引擎
POST /indicators/compare       双策略对比
GET  /backtest/history         回测历史记录
```

**相关服务**：
- `domain/quantlib/engine/backtest_engine.py` - 回测引擎
- `application/services/combo_strategy_backtest_service.py` - 组合回测
- `domain/quantlib/search/search_space.py` - 参数网格生成

---

### 4️⃣ 信号管理 (Signal Management)

**核心价值**：Agent 的"交易机会"管理系统

#### 核心功能
- ✅ **信号 CRUD**：创建、查询、更新、删除交易信号
- ✅ **状态管理**：pending → executed → closed
- ✅ **信号扫描**：主动扫描交易机会
- ✅ **信号推送**：实时推送新信号（WebSocket）
- ✅ **按策略查询**：按策略 ID 筛选信号
- ✅ **统计分析**：按状态统计信号数量

#### 信号状态流转
```
pending (待处理) → executed (已执行) → closed (已平仓)
                ↓
             ignored (已忽略)
```

**API 端点** (前缀 `/api/signals`)：
```
GET    /                      查询交易信号
GET    /pending               获取待处理信号
GET    /by-strategy/{id}     按策略查询
POST   /scan                  扫描交易机会
POST   /                      创建信号
PUT    /{signal_id}/status   更新信号状态
GET    /stats/by-status      按状态统计
```

**相关服务**：
- `application/services/signal_execution_scheduler.py` - 信号执行调度
- `application/services/signal_execution_async_scheduler.py` - 异步调度

---

### 5️⃣ 市场数据 (Market Data)

**核心价值**：多数据源聚合，为 Agent 提供全面市场视图

#### 数据类型
- ✅ **实时行情**：股票实时价格、涨跌幅、成交量
- ✅ **历史行情**：日线、周线、月线 K 线数据
- ✅ **财务数据**：季报、年报财务指标（akshare）
- ✅ **红利数据**：分红送股历史
- ✅ **估值数据**：PE、PB、PS、PCF 估值指标
- ✅ **龙虎榜数据**：机构和游资席位交易记录
- ✅ **情绪指标**：市场情绪评分

#### 数据源支持
- **akshare**：主数据源（新浪财经、东方财富）
- **tushare**：备用数据源（需 token）
- **eastmoney**：财务数据备用
- **实时 WebSocket**：实时行情推送

**API 端点** (前缀 `/api`)：
```
GET  /market/quote             实时行情
GET  /market/kline             历史 K 线
GET  /market/financials        财务数据
GET  /dividends                红利数据
GET  /market/valuation         估值数据
GET  /market/lhb               龙虎榜数据
GET  /market/sentiment         市场情绪
```

**相关服务**：
- `application/services/stock_data_service.py` - 股票数据
- `application/services/realtime_quote_service.py` - 实时行情
- `application/services/enhanced_financial_data_service.py` - 财务数据
- `application/services/valuation_data_service.py` - 估值数据
- `application/services/lhb_service.py` - 龙虎榜数据
- `application/services/sentiment_service.py` - 情绪分析

---

### 6️⃣ 博弈智能 (Game Intelligence)

**核心价值**：对手行为分析，识别市场参与者的错误

#### P0 规划功能（部分已实现）
- ✅ **对手行为追踪**：散户/机构/游资资金流向
- ✅ **操纵检测**：识别拉高出货等操纵行为
- ⏳ **战场评估**：各股票池的博弈优势评分
- ⏳ **实时博弈预警**：WebSocket 推送机会/风险预警
- ⏳ **池子风险评估**：结合博弈情境的风险信号

#### 博弈分析框架
```
市场参与者：
  - 散户（retail）：情绪化，追涨杀跌
  - 机构（institution）：资金/信息优势
  - 游资（hot_money）：拉高出货

Agent 策略：
  - 收割散户恐慌：恐慌性抛售时抄底
  - 避开机构陷阱：机构出货时退出
  - 狙击游资崩盘：拉高出货后抄底
```

**API 端点** (前缀 `/api`)：
```
GET  /market/opponent-behavior    对手行为追踪
GET  /market/manipulation-detect  操纵检测
GET  /pools/battlefield-assessment 战场评估（规划中）
GET  /pools/{id}/risk-assessment   池子风险（规划中）
WS   /ws/game-alerts                实时博弈预警（规划中）
```

**相关服务**：
- `application/services/game_alert_service.py` - 博弈预警
- `adapters/inbound/fastapi_app/routes/game/intelligence.py` - 博弈智能路由

---

### 7️⃣ 因子分析 (Factor Analysis)

**核心价值**：多因子模型构建和因子有效性检验

#### 核心功能
- ✅ **因子计算**：技术因子、财务因子、量价因子
- ✅ **因子检验**：IC/IR、分层回测、因子相关性
- ✅ **因子组合**：多因子加权评分
- ✅ **因子归因**：收益归因分析

**API 端点** (前缀 `/api/factors`)：
```
POST /calculate      计算因子值
POST /test           因子有效性检验
POST /combine        因子组合
GET  /attribution   因子归因分析
```

**相关服务**：
- `application/services/factor_analysis_service.py`
- `domain/quantlib/factors/` - 因子库

---

### 8️⃣ 风险管理 (Risk Management)

**核心价值**：多维度风险监控和仓位管理

#### 核心功能
- ✅ **风险指标**：波动率、VaR、最大回撤
- ✅ **仓位管理**：Kelly 公式、固定比例、动态调整
- ✅ **风险预警**：超限自动报警
- ✅ **止损止盈**：策略级和组合级止损

**API 端点** (前缀 `/api/risk`)：
```
GET  /metrics          风险指标
POST /position-sizing  仓位计算
GET  /alerts           风险预警列表
```

**相关服务**：
- `application/services/risk_service.py`
- `domain/quantlib/risk/` - 风险模型

---

### 9️⃣ 组合管理 (Portfolio Management)

**核心价值**：Agent 的持仓和订单管理

#### 核心功能
- ✅ **持仓管理**：查看当前持仓、历史持仓
- ✅ **订单管理**：下单、撤单、订单历史
- ✅ **业绩归因**：持仓收益来源分析
- ✅ **组合优化**：Markowitz 均值方差优化

**API 端点** (前缀 `/api`)：
```
GET  /portfolio/positions    当前持仓
GET  /portfolio/history      持仓历史
POST /orders                 下单
GET  /orders                 订单列表
DELETE /orders/{id}          撤单
```

**相关服务**：
- `application/services/order_service.py`
- `adapters/outbound/repositories/portfolio_repository.py`

---

### 🔟 学习系统 (Learning System)

**核心价值**：Agent 自我改进，积累经验

#### P0 规划功能（部分已实现）
- ✅ **决策跟踪**：记录所有 Agent 决策及上下文
- ✅ **结果反馈**：决策结果（盈亏）关联
- ⏳ **知识库**：沉淀为规则和模式
- ⏳ **归因分析**：识别有效的决策因素
- ⏳ **策略自优化**：自动调整策略参数

#### 数据库表
```sql
agent_decisions        -- 决策日志
agent_knowledge        -- 知识库
pool_change_log        -- 池子变更日志
strategy_performance   -- 策略表现
```

**API 端点** (前缀 `/api`)：
```
POST /decisions              记录决策
GET  /decisions              查询决策历史
PUT  /decisions/{id}/outcome 更新决策结果
GET  /knowledge              查询知识库
POST /knowledge              添加知识
```

**相关服务**：
- `application/services/learning_engine.py`
- `application/services/experience_accumulator.py`
- `application/services/decision_evaluator.py`

---

### 1️⃣1️⃣ 定时任务 (Scheduler)

**核心价值**：Agent 自主运行的"心跳"系统

#### 核心功能
- ✅ **任务调度**：Cron 表达式定时任务
- ✅ **任务管理**：启用/禁用/手动触发
- ✅ **执行记录**：任务执行日志和状态
- ✅ **失败重试**：自动重试失败任务

#### 典型调度任务
```python
# 每日 02:00 - 刷新股票池
# 每日 09:00 - 扫描买入机会
# 每日 15:30 - 生成日报
# 每周一 - 周度总结
```

**API 端点** (前缀 `/api/scheduler`)：
```
GET  /jobs              所有定时任务
POST /jobs              创建任务
PUT  /jobs/{id}         更新任务
POST /jobs/{id}/run     手动触发
GET  /jobs/{id}/logs    执行日志
```

**相关服务**：
- `infrastructure/scheduler/` - 调度器
- `application/services/scheduler_config_service.py`

---

### 1️⃣2️⃣ 数据质量 (Data Quality)

**核心价值**：确保数据可靠性，避免"垃圾进垃圾出"

#### 核心功能
- ✅ **数据诊断**：检测缺失值、异常值、重复值
- ✅ **缺口检测**：识别时间序列数据缺口
- ✅ **数据验证**：财务数据逻辑校验
- ✅ **数据修复**：自动填补和修正

**API 端点** (前缀 `/api/data`)：
```
POST /diagnosis         数据诊断
GET  /gaps              缺口检测
POST /validate          数据验证
POST /repair            数据修复
```

**相关服务**：
- `application/services/diagnosis_service.py`
- `application/services/data_validator.py`
- `application/services/data_gap_detector.py`

---

### 1️⃣3️⃣ 可视化与图表 (Charts & Visualization)

**核心价值**：为 web-frontend 提供图表数据

#### 核心功能
- ✅ **K 线图数据**：OHLCV + 指标叠加
- ✅ **收益曲线**：策略收益时间序列
- ✅ **因子分布**：因子值直方图
- ✅ **相关性热图**：因子相关性矩阵

**API 端点** (前缀 `/api/charts`)：
```
GET /kline              K 线图数据
GET /returns            收益曲线
GET /factor-dist        因子分布
GET /correlation        相关性热图
```

---

### 1️⃣4️⃣ 缠论分析 (Chan Theory)

**核心价值**：缠论技术分析工具

#### 核心功能
- ✅ **笔段识别**：识别缠论中的笔和段
- ✅ **中枢判断**：识别中枢结构
- ✅ **买卖点标注**：自动标注缠论买卖点

**API 端点** (前缀 `/api/chan`)：
```
POST /analyze           缠论分析
GET  /pivots            笔段结构
GET  /centers           中枢识别
```

**相关服务**：
- `domain/chan/` - 缠论领域模块

---

### 1️⃣5️⃣ 其他辅助功能

#### 系统管理
- ✅ **健康检查**：`GET /health`
- ✅ **配置管理**：系统配置读写
- ✅ **日志管理**：结构化日志（structlog）
- ✅ **监控指标**：API 性能监控

#### 工具集
- ✅ **股票搜索**：按名称/代码模糊搜索
- ✅ **行业板块**：行业分类和成分股
- ✅ **概念板块**：概念题材和成分股
- ✅ **新股日历**：IPO 日历

**API 端点**：
```
GET /api/stock/search         股票搜索
GET /api/sectors              行业板块
GET /api/concepts             概念板块
GET /api/market/ipo-calendar  新股日历
```

---

## 技术架构

### 分层架构
```
┌─────────────────────────────────────────┐
│  Adapters (适配器层)                     │
│  • Inbound: FastAPI routes (61 files)   │
│  • Outbound: Repositories, DataSources  │
└─────────────┬───────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  Application (应用层)                    │
│  • Services (140+ files)                │
│  • Use case orchestration               │
└─────────────┬───────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  Domain (领域层)                         │
│  • QuantLib: factors, backtest, risk    │
│  • Chan Theory: 缠论分析                 │
│  • Strategies: 策略实现                  │
└─────────────────────────────────────────┘
```

### 关键技术
- **Web 框架**：FastAPI（已从 Flask 迁移）
- **数据库**：PostgreSQL
- **ORM**：SQLAlchemy
- **异步**：asyncio + asyncpg
- **日志**：structlog（结构化日志）
- **调度**：APScheduler
- **WebSocket**：FastAPI WebSocket
- **数据源**：akshare, tushare, eastmoney

---

## 开发状态

### ✅ 已完成 (Production Ready)
- 股票池 CRUD
- 策略管理和回测
- 参数搜索优化
- 信号管理
- 市场数据聚合
- FastAPI 迁移（性能提升 3-10x）

### 🚧 开发中 (In Progress)
- 博弈智能模块完善
- 学习系统数据闭环
- 实时信号推送优化

### 📋 规划中 (Roadmap)
- **P0 博弈智能**：
  - 战场评估 API
  - 池子风险评估（结合博弈）
  - 实时博弈预警（WebSocket）
  
- **P1 学习系统**：
  - 知识库积累
  - 归因分析
  - 策略自优化

---

## 性能指标

### FastAPI 性能（vs Flask）
- **吞吐量**：3-10x 提升
- **响应时间**：平均 < 100ms
- **并发能力**：支持 1000+ 并发连接

### 数据处理能力
- **回测速度**：100 组参数 < 60s（10 workers 并行）
- **股票池刷新**：3000 只股票 < 5s
- **因子计算**：单因子 4000 只股票 < 10s

---

## API 文档

**FastAPI 自动生成文档**：
- Swagger UI: http://localhost:5001/docs
- ReDoc: http://localhost:5001/redoc
- OpenAPI JSON: http://localhost:5001/openapi.json

---

## 统计数据

| 指标 | 数量 |
|------|------|
| 服务文件 | 140+ |
| 路由文件 | 61 |
| API 端点 | 200+ |
| 内置策略 | 18 |
| 支持的策略类型 | 5 |
| 财务指标 | 18 列 |
| 技术指标 | 12 列 |
| 数据表 | 50+ |

---

## 总结

QuantSys V2 是一个**全栈量化投资基础设施**，不仅提供数据 API，更重要的是提供**决策智能**：

1. **数据驱动**：多源聚合，确保数据质量
2. **策略灵活**：5 种策略类型，18 种内置策略
3. **性能强劲**：FastAPI 架构，3-10x 性能提升
4. **博弈智能**：对手行为分析，识别市场错误
5. **自我学习**：决策跟踪和反馈闭环
6. **高度可观测**：结构化日志，完整审计轨迹

**设计哲学**：
> 不仅返回数据，更要返回洞察（insights）
> 不仅执行指令，更要建议行动（recommendations）
> 不仅记录历史，更要学习改进（learning）

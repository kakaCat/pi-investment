# qs_trading — 交易执行包

> 抽离记录：quantsys-v2 单体 S7（2026-10-18）。方案卡：`docs/plans/package-boundaries-import-linter.md` §11.4 S7。

## 本包是什么

**AI 工作区 L2**：本目录=「交易执行」项目（下单结算一条线）。上下文只要本文件，不要去根工作区。

- **定位**：账户/资金/订单/成交/持仓/券商对接（broker_registry）、风险三件（risk_service/enhanced_risk_assessor/risk_metrics）、风控检查（risk_check）、仿真（simulation_service）、盘中止损（intraday_monitor）、保护线（portfolio_breaker）、买入区间（enhanced_buy_range）、组合优化（portfolio_optimization）、盘口会话（market_session）
- **读信号表**：sourcing 写 `quant.signal*`，trading 只读接单（§12 数据写作）
- **上游**：`qs_strategy`（仿真回放策略，白名单边）、`qs_intel`（风险场景 read-only）、`qs_quantlib`（指标）、`qs_market_data`（行情）

## 目录结构

```
qs_trading/
├── application/services/          14 服务
│   ├── account_trading_service.py 账户+交易编排
│   ├── trade_service.py / execution_service.py 实盘执行
│   ├── position_service.py        持仓
│   ├── intraday_monitor.py        盘中止损止盈
│   ├── portfolio_breaker_service.py 保护线
│   ├── enhanced_buy_range_service.py 买入区间
│   ├── portfolio_optimization_service.py 组合优化
│   ├── simulation_service.py      仿真（回放 domain/strategies）
│   ├── risk_service.py / enhanced_risk_assessor.py / risk_metrics_service.py / risk_check_service.py
│   └── market_session_service.py  盘口会话
└── domain/                        六域 65 文件
    ├── accounts/（8：Account/Balance + AccountService + ports/IAccountRepository）
    ├── trading/（22：Order/Trade + OrderService + ports/ITrade·IOrder）
    ├── portfolio/（7：Position + PositionService + ports/IPosition）
    ├── brokers/（5：BaseBroker/BrokerRegistry/broker_types）
    ├── legacy/（2：LegacyOrderAdapter）
    └── risk/（19：风险计算域）
```

> **端口裁决（ADR：§11.1 裁量点）**：`IOrderRepository`/`IPositionRepository` 以**域内 ports/ 为准**（6 方法/4 方法）；集中库 `domain/ports/` 侧的 1 方法桩仍由 `position_repository.py` 等引用，退役属逐点改造（后续卡）。

## 依赖边界（方案卡 §11.3）

- 允许：本包 → kernel（`domain.ports` / `infrastructure.persistence` / events）、→ `qs_market_data`（行情）、→ `qs_quantlib`（计算）、→ `qs_strategy`（仿真回放，**白名单边，2026-10-18 登记**）、→ `qs_intel`（场景 read-only）
- 暂留 L1 引用（后续归属阶段收口）：核心 L1 仓储（order/trade/position/account/simulation 等仍在 `adapters/outbound/repositories/`，sourcing 先例）、`core_async_services.py` 混装残件（调用方只取 Data/MarketData/Performance 三类）、infrastructure 两套 DI 反向装配
- 旧路径兼容 shim 在 L1：`application/services/<14 模块名>.py`（sys.modules 别名）、`domain/{accounts,trading,portfolio,brokers,legacy,risk}/__init__.py`（__path__ 转发，含 ports 子包），30 天观察期后删除
- `watch→trading`（S8 单）与 `agent-hub→各项目 public` 边不在本包实现

## 常见任务路径

- **改下单/撤单** → `execution_service.py`（OrderService 调用 account 资金校验先行）
- **改止损止盈** → `intraday_monitor.py`（tick 级，与 watch 的触发分工见 RFC 011）
- **加保护线** → `portfolio_breaker_service.py`（规则+通知面）
- **改仿真** → `simulation_service.py`（回放 `qs_strategy.domain.strategies` 策略栈）
- **改风险口径** → `risk_service.py`（Calc 层）+ `risk_metrics_service.py`（empyrical 指标层）

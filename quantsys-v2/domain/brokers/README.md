# 券商抽象层（未使用）

## ⚠️ 当前状态

**UNUSED** - 此模块当前未被使用，为未来实盘交易预留的接口设计。

## 设计目的

本模块设计用于未来支持实盘交易时，提供统一的券商接口抽象，支持：
- 订单提交和撤销
- 订单状态查询
- 账户余额查询
- 持仓查询
- 多券商适配

## 当前系统架构

**模拟盘交易流程**（当前实现）：

```
AccountTradingService.execute_trade()
  ↓
OrderService.create_order()
  ↓
SimulationRepository (直接操作数据库)
  ↓
PostgreSQL
```

**不经过券商层**。所有交易逻辑在应用层和领域层完成，直接持久化到数据库。

## 实盘计划

### 目标时间
- 预计：2027 Q2
- 触发条件：确定实盘券商合作伙伴

### 需要的工作

1. **重构交易流程**
   - 在 `OrderService` 中集成券商服务
   - 实现异步订单状态查询
   - 处理券商回报和事件

2. **实现具体券商适配器**
   - 基于 `IBrokerService` 接口
   - 实现具体券商 API 对接
   - 错误处理和重试逻辑

3. **数据同步机制**
   - 券商账户 ↔ 本地账户同步
   - 持仓对账
   - 资金对账

4. **异步回报处理**
   - WebSocket/长轮询接收券商回报
   - 订单状态更新
   - 成交通知

### 预计工作量
- 2-3 周全职开发
- 需要券商测试环境

## 模块结构

```
domain/brokers/
├── models/
│   ├── broker_config.py      # 券商配置
│   ├── broker_account.py     # 券商账户
│   └── execution_report.py   # 执行回报
├── ports/
│   └── IBrokerService.py     # 券商服务接口 (ABC)
└── services/
    └── broker_service.py     # 券商服务基类
```

## ⚠️ 重要提示

### 请勿使用

在实盘功能正式实现之前，**请勿**：
- 在其他模块中引用此模块
- 尝试实例化 `BrokerService`
- 假设系统已支持实盘交易

### 如需实盘支持

请联系架构团队，启动实盘集成项目。

## 参考资料

- [架构审计报告](../../../docs/work-logs/2026-09/quantsys-v2-account-order-broker-audit.md)
- [P2 问题分析](../../../docs/work-logs/2026-09/quantsys-v2-p2-issues-analysis.md)

---

**最后更新**: 2026-09-01  
**维护者**: PI Investment 架构团队

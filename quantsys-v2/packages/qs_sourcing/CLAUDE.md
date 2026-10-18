# qs_sourcing — 选股→信号流水线包

> 抽离记录：quantsys-v2 单体 S4（2026-10-18）。方案卡：`docs/plans/package-boundaries-import-linter.md` §11.4 S4。

## 本包是什么

**AI 工作区 L2**：本目录=「选股→信号」项目（机会生产一条线）。上下文只要本文件，不要去根工作区。

- **定位**：股票池生命周期（建池/刷新/校验/健康）＋ 全市场筛选/评分 ＋ 信号产生/处理/追踪/执行调度
- 写表：`quant.stock_pool*`、`quant.signal*`、`quant.signal_execution*`（§12 数据写作：sourcing 写信号表，trading 只读）
- **上游**：`qs_market_data`（取数唯一出口）、`qs_quantlib`（信号计算）
- **下游**：trading 按 `signal_generated` 事件/读信号表接单；watch 接盯盘触发

## 目录结构

```
qs_sourcing/
├── application/services/          16 服务
│   ├── stock_pool_service.py / stock_pool_async_service.py  池 CRUD/刷新/成员管理
│   ├── pool_validation_service.py 池策略校验
│   ├── pool_health_tracker.py     池健康度
│   ├── pool_scan_scheduler.py / pool_scanner_service.py     池扫描编排/执行
│   ├── pool_signal_scanner.py     池内信号扫描
│   ├── stock_screening_service.py 全市场筛选
│   ├── stock_scoring_service.py   评分
│   ├── realtime_signal_service.py 实时信号
│   ├── signal_processor.py / signal_monitoring.py           信号处理/监控
│   ├── signal_tracking_service.py / signal_test_log.py      信号追踪/测试留痕
│   └── signal_execution_scheduler.py / signal_execution_async_scheduler.py  执行调度（sync/async 双轨）
└── adapters/outbound/repositories/  9 仓储（与 sync/async 双轨口径一致）
    ├── stock_pool_repository.py / stock_pool_async_repository.py
    ├── signal_repository.py / signal_async_repository.py
    ├── signal_execution_repository.py / signal_execution_async_repository.py
    └── signal_execution_log_repository.py / signal_test_log_repository.py / signal_tracking_repository.py
```

> 仓储 sync/async 双轨口径遵守根 CLAUDE.md（新代码按上下文选轨，勿新建第三份）。

## 依赖边界（方案卡 §11.3）

- 允许：本包 → kernel（`domain.ports` / `infrastructure.persistence.orm.*` / `domain.exceptions`）、→ `qs_market_data`（取数）、→ `qs_quantlib`（信号计算）
- 暂留 L1 引用（S11 后收口）：infrastructure/services 两套 DI（ServiceFactory/service_registry）仍 import 本包成员做装配，属 kernel→package 暂时反向，供 linter 后续登记
- 旧路径兼容 shim 在 L1：`application/services/<16 模块名>.py`、`adapters/outbound/repositories/<9 模块名>.py`（sys.modules 别名，30 天观察期后删除）

## 常见任务路径

- **改池刷新规则** → `pool_scanner_service.py`（cred/oracle 策略在池 YAML 参数里）
- **加一个筛选条件** → `stock_screening_service.py`（评分权重在 `stock_scoring_service.py`）
- **加信号类型** → `signal_processor.py`（类型枚举）+ `signal_repository.py`（表门）
- **改执行节拍** → `signal_execution_scheduler.py`（sync 轨，读 `quant.scheduler_tasks`）

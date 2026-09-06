# TODO/FIXME 清理计划

**生成时间**: /Users/yunpeng/pi-investment/quantsys-v2
**总数**: 32 项

## 统计概览

### 按优先级

- 🔴 P1 (高优先级): 0 项
- 🟡 P2 (中优先级): 32 项
- 🟢 P3 (低优先级): 0 项

### 按分类

- **立即修复**: 10 项
- **技术债务**: 22 项

## 清理策略

### 立即处理 (P1)

这些 TODO 影响功能完整性，应该立即修复或删除：

✅ 无 P1 TODO

### 本周处理 (P2 中的立即修复和技术债务)

- [ ] `services/strategy_discovery_service.py:504` - 从 stock info 获取
- [ ] `services/combo_strategy_backtest_service.py:317` - calculate from trades
- [ ] `services/decision_evaluator.py:204` - 实际应该计算收益率、夏普比率等
- [ ] `services/stock_screening_service.py:202` - 获取最新价格
- [ ] `services/order_service.py:707` - 计算实际持仓天数
- [ ] `services/order_service.py:708` - 从信号 details 中提取
- [ ] `services/order_service.py:709` - 从信号 details 中提取
- [ ] `services/simulation_service.py:318` - 这里应该调用实际的SimulationTrader执行交易
- [ ] `services/smart_scheduler.py:310` - 这里需要一个任务函数注册表
- [ ] `services/market_data_service.py:27` - Phase 3 future work - migrate methods to use provider_manager

*还有 22 项...*

### 转为 GitHub Issue (P2 功能增强)


### 直接删除 (已废弃)

✅ 无废弃 TODO

## 详细列表


### services/strategy_discovery_service.py

🟡 **L504** [技术债务]: 从 stock info 获取


### services/combo_strategy_backtest_service.py

🟡 **L317** [技术债务]: calculate from trades


### services/decision_evaluator.py

🟡 **L204** [技术债务]: 实际应该计算收益率、夏普比率等


### services/stock_screening_service.py

🟡 **L202** [技术债务]: 获取最新价格


### services/order_service.py

🟡 **L707** [技术债务]: 计算实际持仓天数

🟡 **L708** [技术债务]: 从信号 details 中提取

🟡 **L709** [技术债务]: 从信号 details 中提取


### services/simulation_service.py

🟡 **L318** [技术债务]: 这里应该调用实际的SimulationTrader执行交易


### services/smart_scheduler.py

🟡 **L310** [技术债务]: 这里需要一个任务函数注册表


### services/market_data_service.py

🟡 **L27** [技术债务]: Phase 3 future work - migrate methods to use provider_manager


### services/opponent_behavior_service.py

🟡 **L140** [技术债务]: 这里需要获取市场整体资金流向，暂时使用模拟逻辑

🟡 **L235** [技术债务]: 分析目标板块（需要按行业聚合资金流向）


### services/enhanced_risk_assessor.py

🟡 **L311** [技术债务]: 分析行业集中度、权重集中度等


### services/agent_scheduler_tool.py

🟡 **L427** [技术债务]: 这里可以通过WebSocket或其他方式通知Agent


### services/manipulation_detector.py

🟡 **L331** [技术债务]: 获取股票基本面数据（PE、PB等）

🟡 **L354** [技术债务]: 获取K线数据，判断是否高位+放量+涨幅收窄

🟡 **L559** [技术债务]: 获取实时价格


### services/dividend_service.py

🟡 **L31** [技术债务]: Phase 3 future work - migrate methods to use provider_manager


### services/sector_rotation_service.py

🟡 **L89** [技术债务]: 从行业映射表获取


### services/data_quality_service.py

🟡 **L202** [技术债务]: 保存报告到数据库


### services/pool_scanner_service.py

🟡 **L357** [技术债务]: 保存到 pool_scan_results 表


### services/registry_client.py

🟡 **L106** [技术债务]: 根据实际状态动态设置


### services/stock_code_validator.py

🟡 **L174** [立即修复]: 可以基于编辑距离、拼音等算法实现更智能的匹配


### services/combo_strategy_backtest_service.py

🟡 **L422** [立即修复]: Implement in Task 3


### services/game_alert_service.py

🟡 **L233** [立即修复]: 实现持仓风险检查

🟡 **L298** [立即修复]: 实现订阅逻辑（存储到数据库）


### services/data_validator.py

🟡 **L243** [立即修复]: 实现特殊情况判断逻辑


### services/pool_scan_scheduler.py

🟡 **L85** [立即修复]: 实现通知逻辑（邮件、飞书、钉钉等）


### services/smart_scheduler.py

🟡 **L87** [立即修复]: 实现重试逻辑


### services/realtime_signal_service.py

🟡 **L219** [立即修复]: 实现分钟级K线获取 + 滚动指标计算


### services/strategy_performance_stats.py

🟡 **L437** [立即修复]: 实现数据库查询逻辑


### services/strategy_execution_service.py

🟡 **L463** [立即修复]: Implement actual order creation via OrderRepository


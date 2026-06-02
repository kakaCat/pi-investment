# Agent 工具文档中心

本目录是 pi-investment 项目 Agent 工具系统的统一文档入口。

---

## 📚 文档导航

### 快速开始
- [工具选择决策树](./tool-selection-guide.md) - 快速找到适合任务的工具
- [工具开发指南](./tool-development-guide.md) - 开发新工具的规范和最佳实践

### 工具参考
- [数据管道工具](./tool-reference/data-tools.md) - L1 数据获取（股票、K线、财务、分红）
- [因子分析工具](./tool-reference/factor-tools.md) - L2 因子计算和分析
- [模型工具](./tool-reference/model-tools.md) - L3 机器学习模型
- [策略工具](./tool-reference/strategy-tools.md) - L3.5 策略管理和执行
- [指标工具](./tool-reference/indicator-tools.md) - 自定义指标系统
- [股票池工具](./tool-reference/pool-tools.md) - L2.7 股票池管理和验证
- [组合回测工具](./tool-reference/backtest-tools.md) - L2.8 组合策略回测
- [执行工具](./tool-reference/execution-tools.md) - L5 交易执行
- [监控工具](./tool-reference/monitoring-tools.md) - L6 监控运维
- [CLI 领域工具](./tool-reference/cli-tools.md) - 8个CLI领域工具
- [Agent 元工具](./tool-reference/agent-tools.md) - 任务、记忆、进化等

### 架构文档
- [六层量化架构](./architecture.md) - 工具系统整体架构
- [工具分类和层次](./tool-hierarchy.md) - 工具的组织方式

### 优化记录
- [工具优化历史](./optimization/) - 历次优化记录
  - [2026-06-02 P0清理完成](../reviews/2026-06-02-p0-cleanup-completion.md)
  - [2026-06-02 优化分析](../reviews/2026-06-02-agent-tools-optimization-analysis.md)
  - [2026-06-02 CLI工具拆分](../reviews/2026-06-02-quant-cli-split-success.md)
  - [2026-06-02 策略工具清理](../reviews/2026-06-02-quant-cli-strategy-cleanup.md)

### 测试文档
- [测试指南](./testing/) - 工具测试规范
  - [数据工具测试](../testing/data-tools-v2-integration-test.md)
  - [分红工具测试](../testing/dividend-tool-e2e-test.md)

---

## 🔍 按使用场景查找工具

### 数据获取
- **获取股票基本信息和实时价格** → `data_fetch_stock`
- **获取K线数据** → `data_fetch_kline`
- **获取财务数据** → `data_fetch_financial`
- **获取分红数据** → `data_fetch_dividend`

### 分析和选股
- **扫描投资机会** → `opportunity_scan`
- **计算技术因子** → `factor_calculate`
- **分析因子有效性** → `factor_analyze`
- **波段分析** → `analysis_swing_points`

### 策略管理
- **列出所有策略** → `strategy_list`
- **查看策略详情** → `strategy_detail`
- **创建新策略** → `strategy_create`
- **编写策略代码** → `strategy_write`
- **执行策略** → `strategy_execute` (支持 single/batch/pipeline 三种模式)
- **优化策略参数** → `strategy_optimize`
- **批量验证策略** → `strategy_batch_validate`

### 股票池管理
- **创建和管理股票池** → `pool_manage`
- **多策略验证** → `pool_validate`

### 回测和验证
- **指标回测** → `indicator_backtest`
- **组合策略回测** → `strategy_combo_backtest` (支持 Portfolio/Ensemble/Pipeline 三种模式)
- **历史绩效分析** → `quant_cli performance.*`

### 模型训练
- **训练ML模型** → `model_train`
- **模型预测** → `model_predict`
- **评估模型** → `model_evaluate`
- **监控模型漂移** → `model_monitor`

### 快速查询（CLI工具）
- **市场数据** → `market_cli` (12个命令)
- **个股数据** → `stock_cli` (5个命令)
- **财务数据** → `financial_cli` (7个命令)
- **市场情绪** → `sentiment_cli` (8个命令)
- **股票分析** → `analysis_cli` (7个命令)

---

## 📊 工具统计

- **工具总数**: 70 个
- **代码总行数**: 11,113 行
- **工具目录数**: 19 个
- **测试覆盖**: 持续改进中

---

## 🚀 最新更新

### 2026-06-02
- ✅ 完成 P0 清理任务：删除10个备份文件，更新.gitignore
- ✅ 完成 P1 清理任务：移除4个废弃的港股命令，清理已移除工具注释
- ✅ 创建统一的工具文档中心
- ✅ 添加工具选择决策树

### 2026-06-02（早期）
- ✅ CLI工具拆分：从 quant_cli 拆分出8个领域工具
- ✅ 策略工具独立化：9个独立策略工具
- ✅ 组合策略回测：新增 strategy_combo_backtest 工具

---

## 📖 相关文档

- [CLAUDE.md](../../CLAUDE.md) - 项目整体说明
- [工具优化分析报告](../reviews/2026-06-02-agent-tools-optimization-analysis.md)
- [Agent工具映射表](../agent-tools-mapping.md)

---

**维护**: Claude Agent 工具优化项目组  
**更新日期**: 2026-06-02

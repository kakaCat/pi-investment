# live_trading/ 目录审计报告

**审计日期**: 2026-09-06  
**目录**: quantsys-v2/live_trading/  
**文件数**: 29 个 Python 文件 + 配置/文档

---

## 执行摘要

live_trading/ 目录包含 **V13/V14 策略的模拟交易和实验代码**。根据 README.md 和文件内容分析：

**定位**: ✅ **合法的实验/研发目录**，不是死代码
- V13 策略模拟交易系统（完整可用）
- V14 策略优化实验脚本（多个版本迭代）
- 回测、因子分析、模型训练工具

**建议**: 保留，但需要整理和文档化

---

## 文件分类

### 1. V13 模拟交易系统（生产就绪）✅

**核心文件**:
- `simulation_trader.py` - 主交易引擎（完整）
- `simulation_broker.py` - 模拟券商接口
- `factor_calculator.py` - 因子计算器
- `risk_control.py` - 风控模块
- `paper_trading_engine.py` - 纸上交易引擎

**配置**:
- `config_simulation.yaml` - 策略配置
- `daily_check.sh` - 每日检查脚本

**状态**: ✅ 功能完整，已记录在 README.md
**用途**: V13 策略模拟盘，可直接使用

---

### 2. V14 策略实验脚本（研发中）⚠️

**训练相关** (7 个):
- `train_v14_model.py` - V14 模型训练（主版本）
- `train_v14_standalone.py` - 独立训练版本
- `train_v14_p0_optimized.py` - P0 优化版
- `train_optimized_model.py` - 优化模型训练
- `train_expanded_model.py` - 扩展模型
- `validate_model_ic.py` - IC 验证
- `calculate_v14_ic_ir.py` - IC/IR 计算

**回测相关** (6 个):
- `backtest_v14_quick.py` - 快速回测
- `backtest_v14_p0.py` - P0 回测
- `backtest_v14_optimized.py` - 优化回测
- `backtest_v14_optimized_full.py` - 完整优化回测
- `backtest_new_model.py` - 新模型回测
- `compare_v13_v14.py` - V13/V14 对比

**执行相关** (3 个):
- `execute_v14_full_rebalance.py` - 完整调仓
- `execute_v14_rebalance_fixed.py` - 修复版调仓
- `test_v14_rebalance.py` - 调仓测试

**分析相关** (4 个):
- `analyze_v14_factors.py` - 因子分析
- `v14_factor_calculator.py` - 因子计算器
- `optimize_annual_return.py` - 年化收益优化
- `optimize_strategy_config.py` - 策略配置优化

**诊断相关** (2 个):
- `diagnose_data_loss.py` - 数据丢失诊断
- `test_risk_integration.py` - 风控集成测试

**状态**: ⚠️ 多版本并存，需要整理
**问题**: 文件命名模糊（quick/p0/optimized/full），缺乏版本说明

---

### 3. 其他工具

- `multi_source_data_fetcher.py` - 多源数据获取器

---

## 问题与建议

### ⚠️ 问题 1: 版本混乱

**现象**: V14 相关脚本有多个版本，命名不清晰
- `train_v14_model.py` vs `train_v14_standalone.py` vs `train_v14_p0_optimized.py`
- `backtest_v14_quick.py` vs `backtest_v14_optimized.py` vs `backtest_v14_optimized_full.py`

**影响**: 开发者不知道该用哪个版本

**建议**:
1. 确定每个脚本的用途和状态（开发中/已废弃/生产版）
2. 废弃的脚本移至 `live_trading/deprecated/`
3. 生产版本明确标注（如 `train_v14_production.py`）

### ⚠️ 问题 2: 缺乏文档

**现象**: 
- 只有 V13 有完整 README.md
- V14 脚本缺乏使用说明
- 新人不知道如何使用这些工具

**建议**:
1. 创建 `V14_README.md` 说明 V14 工具使用
2. 每个脚本顶部添加 docstring 说明用途
3. 创建开发日志记录实验结果

### ✅ 问题 3: 目录结构建议

**当前结构**: 扁平化，所有脚本在同一目录

**建议结构**:
```
live_trading/
├── v13/                    # V13 模拟交易系统
│   ├── simulation_trader.py
│   ├── simulation_broker.py
│   ├── config_simulation.yaml
│   └── README.md
├── v14/                    # V14 策略工具
│   ├── train/              # 训练脚本
│   ├── backtest/           # 回测脚本
│   ├── execute/            # 执行脚本
│   ├── analyze/            # 分析脚本
│   └── README.md
├── deprecated/             # 废弃脚本（保留以备查）
└── shared/                 # 共享工具
    ├── factor_calculator.py
    ├── risk_control.py
    └── multi_source_data_fetcher.py
```

---

## 审计结论

### 总体评估: 6/10

| 维度 | 评分 | 说明 |
|------|------|------|
| 代码质量 | 7/10 | V13 系统完整，V14 实验代码质量参差 |
| 文档完整性 | 4/10 | V13 有文档，V14 缺失 |
| 目录组织 | 5/10 | 扁平化结构，缺乏分类 |
| 版本管理 | 4/10 | 多版本并存，命名混乱 |

### 关键发现

✅ **不是死代码**: live_trading/ 是活跃的研发目录
✅ **V13 系统可用**: 模拟交易系统功能完整
⚠️ **V14 需要整理**: 多版本脚本需要梳理和文档化

### 行动建议

**P0 - 立即执行**:
1. ✅ 保留 live_trading/ 目录（不删除）
2. 📝 为 V14 创建 README.md

**P1 - 本周执行**:
1. 审计每个 V14 脚本，标记状态（生产/开发中/废弃）
2. 废弃脚本移至 deprecated/
3. 创建 V14 开发日志

**P2 - 下月执行**:
1. 重构目录结构（按上述建议）
2. 统一命名规范
3. 添加使用文档

---

## 附录：文件清单

### 可执行脚本（24 个）

**V13 系统** (3):
- simulation_trader.py ✅ 生产就绪
- simulation_broker.py ✅ 生产就绪
- paper_trading_engine.py ✅ 生产就绪

**V14 训练** (7):
- train_v14_model.py ⚠️ 用途待确认
- train_v14_standalone.py ⚠️ 用途待确认
- train_v14_p0_optimized.py ⚠️ 用途待确认
- train_optimized_model.py ⚠️ 用途待确认
- train_expanded_model.py ⚠️ 用途待确认
- validate_model_ic.py ⚠️ 用途待确认
- calculate_v14_ic_ir.py ⚠️ 用途待确认

**V14 回测** (6):
- backtest_v14_quick.py ⚠️ 用途待确认
- backtest_v14_p0.py ⚠️ 用途待确认
- backtest_v14_optimized.py ⚠️ 用途待确认
- backtest_v14_optimized_full.py ⚠️ 用途待确认
- backtest_new_model.py ⚠️ 用途待确认
- compare_v13_v14.py ⚠️ 用途待确认

**V14 执行** (3):
- execute_v14_full_rebalance.py ⚠️ 用途待确认
- execute_v14_rebalance_fixed.py ⚠️ 用途待确认
- test_v14_rebalance.py ⚠️ 用途待确认

**V14 分析** (2):
- analyze_v14_factors.py ⚠️ 用途待确认
- optimize_annual_return.py ⚠️ 用途待确认

**其他** (3):
- factor_calculator.py ✅ 共享工具
- risk_control.py ✅ 共享工具
- multi_source_data_fetcher.py ⚠️ 用途待确认

### 非代码文件

**文档** (7):
- README.md ✅ V13 完整文档
- COMPLETE_EXECUTION_REPORT.md ⚠️ 应移至 docs/
- FINAL_TASK_REPORT.md ⚠️ 应移至 docs/
- UPGRADE.md ⚠️ 应移至 docs/
- V13_OPTIMIZATION_REPORT.md ⚠️ 应移至 docs/
- V14_FACTOR_ANALYSIS_REPORT.md ⚠️ 应移至 docs/
- V14_FINAL_REPORT.md ⚠️ 应移至 docs/

**配置**:
- config_simulation.yaml ✅
- config_simulation_backup_20260701_003805.yaml ⚠️ 备份应删除

**其他**:
- create_simulation_tables.sql ✅
- daily_check.sh ✅

---

**审计人**: Claude (Kiro AI)  
**下一步**: 创建 V14_README.md 并标记脚本状态

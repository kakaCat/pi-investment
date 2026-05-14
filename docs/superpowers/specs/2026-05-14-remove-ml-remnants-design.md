# 删除 ML 残骸 - 设计文档

**日期**: 2026-05-14  
**任务**: 架构改进清单 - 任务 2  
**状态**: 设计完成，待实施

## 背景

pi-investment 项目早期引入了 ML Pipeline 用于股票信号预测和回测，但后续决策转向纯 TypeScript 技术分析方案。ML 相关代码已被禁用但仍存在于代码库中，造成维护负担和架构混乱。

## 目标

清理所有已禁用的 ML 相关代码，包括：
- Python ML 训练和预测模块
- ml-pipeline 回测引擎
- 依赖这些模块的 TypeScript 服务层代码

## 当前状态分析

### 存在的 ML 残骸

1. **python/ml/** 目录
   - `signal_trainer.py` (4.5KB)
   - `signal_predictor.py` (1.5KB)
   - 功能：ML 模型训练和信号预测
   - 状态：已禁用，无引用

2. **ml-pipeline/** 目录
   - `backtesting/` - 回测引擎
   - `features/` - 特征工程
   - `training/` - 模型训练
   - `inference/` - 推理模块
   - `ml_pipeline.py` - 主入口 (13KB)
   - 状态：被 QuantService 引用，但 QuantService 本身未被使用

3. **src/services/quant/quant-service.ts**
   - 功能：封装 ml-pipeline CLI 调用
   - 方法：train(), predict(), backtest(), backtestStrategy()
   - 状态：无其他代码引用（仅测试文件）
   - 依赖：完全依赖 ml-pipeline

4. **src/services/quant/quant-service.test.ts**
   - QuantService 的单元测试
   - 状态：随 QuantService 一起删除

### 已正确迁移的部分

- **src/infrastructure/tools/quant-tools.ts** 中的 `predictStockSignalTool`
  - 已重写为纯 TypeScript 实现
  - 使用 `calculate_technical_indicators` 进行技术评分
  - 无需修改，保持现状

## 删除方案

### 删除范围

| 类型 | 路径 | 大小/文件数 | 原因 |
|------|------|------------|------|
| Python 目录 | `python/ml/` | 2 个 Python 文件 | ML 训练/预测模块已禁用 |
| Python 目录 | `ml-pipeline/` | 完整 pipeline 项目 | 回测引擎已禁用 |
| TS 服务 | `src/services/quant/quant-service.ts` | 1 个文件 | 完全依赖 ml-pipeline，无其他引用 |
| TS 测试 | `src/services/quant/quant-service.test.ts` | 1 个文件 | 对应服务的测试 |

### 保留部分

- `src/infrastructure/tools/quant-tools.ts` - 已是纯 TS 实现，功能正常
- `src/services/quant/kelly-criterion.ts` - 凯利公式仓位计算，独立模块
- `src/services/quant/backtest-service.ts` - 如果存在且不依赖 ml-pipeline

### 执行步骤

1. **删除 Python ML 目录**
   ```bash
   git rm -rf python/ml/
   git rm -rf ml-pipeline/
   ```

2. **删除 QuantService**
   ```bash
   git rm src/services/quant/quant-service.ts
   git rm src/services/quant/quant-service.test.ts
   ```

3. **检查遗漏引用**
   ```bash
   grep -r "quant-service\|QuantService" src/ --include="*.ts"
   grep -r "ml-pipeline\|python/ml" src/ --include="*.ts"
   ```
   - 如发现引用，评估是否需要清理或重构

4. **验证构建和测试**
   ```bash
   npm run typecheck  # TypeScript 类型检查
   npm run test       # 运行测试套件
   npm run build      # 构建验证
   ```

5. **提交变更**
   ```bash
   git commit -m "chore: 删除 ML 残骸 - 移除 ml-pipeline、python/ml 和 QuantService"
   ```

## 风险评估

### 低风险因素

- QuantService 无其他代码引用（已验证）
- ML 功能已被纯 TS 方案替代
- 删除操作可通过 git 历史恢复

### 潜在风险

- **未发现的隐式依赖**：可能存在动态导入或配置文件引用
  - 缓解：执行步骤 3 的全局搜索
  
- **测试覆盖不足**：删除后可能影响未测试的代码路径
  - 缓解：运行完整测试套件，手动验证核心功能

## 验证标准

删除完成后，以下条件必须满足：

1. ✅ TypeScript 编译通过 (`npm run typecheck`)
2. ✅ 所有测试通过 (`npm run test`)
3. ✅ 构建成功 (`npm run build`)
4. ✅ 无遗留的 import 引用
5. ✅ `predictStockSignalTool` 功能正常（纯 TS 实现）

## 后续影响

### 代码库改进

- 减少约 15-20 个文件
- 移除 Python 依赖的一个使用场景
- 简化 `src/services/quant/` 目录结构

### 架构清晰度

- 明确技术分析策略：纯 TypeScript 实现
- 消除已禁用但仍存在的代码混淆
- 为后续架构改进（任务 1、3-8）铺平道路

## 回滚方案

如果删除后发现问题：

```bash
# 查看删除的文件
git log --diff-filter=D --summary

# 恢复特定文件
git checkout <commit-hash>^ -- <file-path>

# 或回滚整个提交
git revert <commit-hash>
```

## 总结

这是一个低风险、高价值的清理任务。删除的代码已被替代方案取代，无实际依赖，删除后将显著提升代码库的清晰度和可维护性。

# Agent 工具检查报告

## 检查时间
2026-06-16

## ❌ 发现的问题

### 1. **重复注册的工具 - CLI 工具组（5 个）**

**问题严重级别**: 🔴 High - 导致系统提示词重复

#### 重复的工具

| 工具名 | 注册位置 | 重复次数 |
|--------|---------|---------|
| **marketCliTool** | 行 147 + 行 315 | 2 次 |
| **stockCliTool** | 行 148 + 行 316 | 2 次 |
| **sentimentCliTool** | 行 149 + 行 317 | 2 次 |
| **analysisCliTool** | 行 150 + 行 318 | 2 次 |
| **watchlistCliTool** | 行 151 + 行 319 | 2 次 |

#### 详细位置

**第一次注册（行 147-151）**:
```typescript
import {
  marketCliTool,
  stockCliTool,
  sentimentCliTool,
  analysisCliTool,
  watchlistCliTool
} from './cli/index.js';
```

**第二次注册（行 315-319）**:
```typescript
  // ===== CLI 领域工具（推荐使用）=====
  marketCliTool,                  // market_cli - 市场数据查询
  stockCliTool,                   // stock_cli - 个股数据查询
  sentimentCliTool,               // sentiment_cli - 市场情绪分析
  analysisCliTool,                // analysis_cli - 股票分析工具
  watchlistCliTool,               // watchlist_cli - 自选股管理
```

#### 影响

1. **系统提示词冗余** - Agent 看到 5 个工具各出现 2 次
2. **token 浪费** - 提示词中包含重复的工具描述
3. **可能的混淆** - Agent 可能不清楚应该使用哪个

---

### 2. **重复的工具名称 - data_quality_report（2 个文件）**

**问题严重级别**: 🟡 Medium - 不同文件使用相同名称

```bash
2 data_quality_report
```

**详细检查**:
```bash
$ find src/infrastructure/tools -name "*quality*" -type f
src/infrastructure/tools/data/data-quality-manage-tool.ts
src/infrastructure/tools/data/data-quality-report-tool.ts
```

需要进一步确认这两个工具是否功能重复或名称冲突。

---

### 3. **重复的工具名称 - momentum（2 个文件）**

**问题严重级别**: 🟡 Medium - 不同文件使用相同名称

```bash
2 momentum
```

需要进一步确认是否是多个策略/因子使用了相同的名称。

---

## ✅ 正常情况

### 工具统计

```bash
实际工具文件数: 90 个
注册工具数: 100 个
差异: +10 个（包含重复注册）
```

### 无重复的工具数量

```bash
无重复注册: 95 个工具  ✅
```

---

## 🔧 修复建议

### 立即修复（High Priority）

#### 删除 CLI 工具的重复注册

**方案**: 删除第二次注册（行 314-319）

```diff
  timeseriesAnalyzerTool,         // timeseries_analyzer - 时间序列分析工具

- // ===== CLI 领域工具（推荐使用）=====
- marketCliTool,                  // market_cli - 市场数据查询
- stockCliTool,                   // stock_cli - 个股数据查询
- sentimentCliTool,               // sentiment_cli - 市场情绪分析
- analysisCliTool,                // analysis_cli - 股票分析工具
- watchlistCliTool,               // watchlist_cli - 自选股管理

  // ===== 通知 & 监控工具 — 消息推送、实时盯盘 =====
  scheduleNextCheckTool,          // schedule_next_check - 设置下次盯盘时间
```

**理由**:
- CLI 工具已经在 import 部分导入
- 已经在数组开头注册过（虽然没有注释，但已存在）
- 第二次注册是多余的

**或者** - 如果想保留第二次注册位置的注释，应该删除第一次注册并移动到更合适的位置。

---

### 进一步调查（Medium Priority）

#### 1. 检查 data_quality_report 重复

```bash
# 查看两个文件的 name 字段
grep "name:" src/infrastructure/tools/data/data-quality-report-tool.ts
grep "name:" src/infrastructure/tools/data/data-quality-manage-tool.ts
```

**可能的情况**:
- 两个工具功能不同，但 name 相同 → 需要重命名其中一个
- 一个是旧版本，应该删除 → 删除旧版本

#### 2. 检查 momentum 重复

```bash
# 查找所有 momentum 相关文件
find src/infrastructure/tools -name "*momentum*" -type f
grep -r "name:.*momentum" src/infrastructure/tools
```

**可能的情况**:
- 多个策略/因子模板使用了相同的名称
- 需要区分命名（如 `momentum_strategy_1`, `momentum_strategy_2`）

---

## 📊 工具分布统计

### 按目录分类

```bash
src/infrastructure/tools/
├── data/          # 数据层工具
├── factor/        # 因子层工具
├── model/         # 模型层工具
├── strategy/      # 策略层工具
├── backtest/      # 回测工具
├── portfolio/     # 组合管理
├── trade/         # 交易执行
├── monitor/       # 监控运维
├── analysis/      # 分析工具
├── screening/     # 筛选工具  ← 新增（quantCliTool 拆分）
├── report/        # 报告工具  ← 新增（quantCliTool 拆分）
├── cli/           # CLI 工具
├── agent/         # Agent 工具
└── core/          # 核心工具
```

### 按功能分类

| 分类 | 数量 | 说明 |
|------|------|------|
| 高频工具 | 7 个 | plan, clarify, task 等 |
| 六层架构工具 | ~60 个 | 数据、因子、模型、策略等 |
| 筛选分析工具 | 9 个 | 从 quantCliTool 拆分 |
| CLI 工具 | 5 个 | 领域专用 CLI |
| 监控工具 | ~5 个 | 监控、预警、通知 |
| 系统工具 | ~10 个 | 重启、记忆、compact 等 |

---

## ✅ 验证步骤

修复后执行以下验证：

### 1. 检查重复注册
```bash
grep -E "^\s+\w+Tool," src/infrastructure/tools/index.ts | sed 's/[, ]//g' | sort | uniq -d
# 预期输出：空（无重复）
```

### 2. 统计工具数量
```bash
grep -E "^\s+\w+Tool," src/infrastructure/tools/index.ts | wc -l
# 预期输出：95（删除 5 个重复后）
```

### 3. 编译测试
```bash
npm run build
# 预期：无新增编译错误
```

### 4. 工具名称唯一性
```bash
find src/infrastructure/tools -name "*-tool.ts" -exec grep -H "name:" {} \; | grep -oP 'name:\s*["\047]\K[^"\047]+' | sort | uniq -c | awk '$1 > 1'
# 预期输出：空或仅 momentum/data_quality_report（需要进一步调查）
```

---

## 🎯 优先级总结

### 🔴 High Priority - 立即修复
- ✅ **删除 CLI 工具的重复注册**（5 个工具）
  - 影响：系统提示词重复，token 浪费
  - 预计时间：5 分钟

### 🟡 Medium Priority - 需要调查
- ⚠️ **检查 data_quality_report 重复**
  - 可能需要重命名或删除
  - 预计时间：15 分钟

- ⚠️ **检查 momentum 重复**
  - 可能是策略模板问题
  - 预计时间：10 分钟

### 🟢 Low Priority - 可选
- ℹ️ **添加工具名称唯一性检查**
  - 防止未来出现重复
  - 预计时间：30 分钟

---

## 📝 总结

### 发现的问题

| 问题 | 数量 | 严重级别 | 状态 |
|------|------|---------|------|
| CLI 工具重复注册 | 5 个 | 🔴 High | 待修复 |
| data_quality_report 重复 | 2 个文件 | 🟡 Medium | 待调查 |
| momentum 重复 | 2 个文件 | 🟡 Medium | 待调查 |

### 总体评估

- **工具总数**: 100 个（包含重复）
- **实际工具**: 95 个（去重后）
- **健康度**: ⭐⭐⭐⭐ (4/5)
  - 扣分原因：5 个工具重复注册

### 建议

✅ **立即删除 CLI 工具的重复注册**，可显著提升系统提示词质量和 token 使用效率。

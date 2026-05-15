# Agent 自我进化 - 完全自动化配置

**日期**: 2026-05-15  
**状态**: ✅ 已配置完全自动化

---

## 🤖 自动化流程

### 1. 定时触发
**配置文件**: `.pi-invest/CRON.json`

```json
{
  "id": "weekly-evolution",
  "name": "每周进化分析",
  "enabled": true,
  "schedule": {
    "kind": "cron",
    "expr": "0 20 * * 0"  // 每周日 20:00
  },
  "payload": {
    "kind": "weekly_evolution"
  }
}
```

**触发时间**: 每周日晚上 20:00（本地时间）

---

### 2. 自动执行配置

**文件**: `src/services/intelligence/evolution-service.ts`

```typescript
const executionResult = await executeOptimizationSuggestions(suggestions, piDir, {
  autoExecute: true,           // ✅ 自动执行所有建议
  requireApproval: [],         // ✅ 空数组 = 无需人工审批
  maxRollbackHistory: 10,      // 保留最近 10 次回滚记录
  parameterRanges: {           // 参数安全范围
    stop_loss_threshold: { min: 0.03, max: 0.15 },
    position_size_ratio: { min: 0.05, max: 0.3 },
    risk_preference: { min: 0.1, max: 1.0 },
  },
});
```

**关键配置**:
- ✅ `autoExecute: true` - 自动执行
- ✅ `requireApproval: []` - 无需审批（空数组）
- ✅ 参数范围验证 - 防止异常值

---

### 3. 自动执行的操作类型

| 操作类型 | 说明 | 自动化程度 |
|---------|------|-----------|
| **update_experience** | 更新经验库 | ✅ 完全自动 |
| **add_tool** | 生成并添加新工具 | ✅ 完全自动（含代码生成、测试、Git 提交） |
| **remove_tool** | 移除低效工具 | ✅ 完全自动 |
| **adjust_parameter** | 调整配置参数 | ✅ 完全自动（范围验证） |
| **update_prompt** | 修改提示词文件 | ✅ 完全自动（自动备份） |
| **update_code** | 生成代码修改计划 | ✅ 完全自动（生成计划文件） |

---

## 🔄 完整自动化流程

```
每周日 20:00
    ↓
Cron 触发 weekly_evolution
    ↓
加载数据（交易/持仓/复盘）
    ↓
减法器：计算差距 + 归因分析
    ↓
补偿器：生成优化建议
    ↓
效应器：自动执行所有建议
    ├─ 更新经验库 ✅
    ├─ 生成新工具代码 ✅
    ├─ 沙箱验证 ✅
    ├─ Git 提交 ✅
    ├─ 移除低效工具 ✅
    ├─ 调整参数 ✅
    ├─ 修改提示词 ✅
    └─ 生成代码修改计划 ✅
    ↓
保存进化报告
    ↓
评估上次进化效果
    ↓
更新经验总结
    ↓
完成（无需人工干预）✅
```

---

## 🛡️ 安全机制

### 1. 参数范围验证
```typescript
parameterRanges: {
  stop_loss_threshold: { min: 0.03, max: 0.15 },  // 止损 3%-15%
  position_size_ratio: { min: 0.05, max: 0.3 },   // 仓位 5%-30%
  risk_preference: { min: 0.1, max: 1.0 },        // 风险偏好 0.1-1.0
}
```

### 2. 沙箱验证
- ✅ 新工具代码生成后自动验证
- ✅ TypeScript 类型检查
- ✅ 单元测试运行
- ✅ 验证失败自动回滚

### 3. Git 分支管理
- ✅ 每次进化创建独立分支 `evolution/YYYY-MM-DD`
- ✅ 验证通过后自动合并到 main
- ✅ 验证失败自动回滚

### 4. 自动备份
- ✅ 提示词修改前自动备份
- ✅ 配置修改前保存旧值
- ✅ 支持回滚到任意历史版本

### 5. 错误恢复
- ✅ 执行失败自动记录日志
- ✅ 连续失败 5 次自动禁用任务
- ✅ 保留回滚数据供手动恢复

---

## 📊 自动化输出

### Cron 日志
**位置**: `.pi-invest/cron/cron-runs.jsonl`

```json
{
  "job_id": "weekly-evolution",
  "job_name": "每周进化分析",
  "run_at": "2026-05-15T20:00:00.000Z",
  "status": "ok"
}
```

### 进化报告
**位置**: `.pi-invest/evolution/evolution-YYYY-MM-DD.md`

包含：
- 本周表现
- 归因分析
- 优化建议
- 自动应用结果
- 历史趋势

### 执行结果
**位置**: `.pi-invest/evolution/execution-YYYY-MM-DD.json`

```json
{
  "applied": [
    {
      "suggestionId": "opt_1",
      "type": "add_tool",
      "status": "success",
      "message": "已生成并合并工具: check_stop_loss_trigger (commit: abc123)"
    }
  ],
  "manualTasks": []  // ✅ 空数组 = 无需人工处理
}
```

---

## 🔍 监控与验证

### 查看 Cron 状态
```bash
# 查看所有定时任务
curl http://localhost:3000/api/cron/jobs

# 手动触发进化分析（测试用）
curl -X POST http://localhost:3000/api/cron/trigger/weekly-evolution
```

### 查看最近进化报告
```bash
npm run evolution -- --view
```

### 查看执行日志
```bash
cat .pi-invest/evolution/execution-$(date +%Y-%m-%d).json | jq
```

---

## ⚙️ 自定义自动化配置

### 修改触发时间
编辑 `.pi-invest/CRON.json`:

```json
{
  "schedule": {
    "kind": "cron",
    "expr": "0 21 * * 0"  // 改为每周日 21:00
  }
}
```

### 修改数据扫描范围
编辑 `src/services/intelligence/evolution-service.ts`:

```typescript
const DEFAULT_CONFIG: Required<EvolutionConfig> = {
  targetReturn: 10,
  tradeWindowDays: 60,  // 改为 60 天
  reviewWindowCount: 15, // 改为 15 份
  evolutionWindowRecent: 5,
  evolutionWindowLearning: 150,
};
```

### 禁用某些自动操作
如果需要人工审批某些操作：

```typescript
const executionResult = await executeOptimizationSuggestions(suggestions, piDir, {
  autoExecute: true,
  requireApproval: ['add_tool', 'update_code'], // 这些需要审批
  // ...
});
```

---

## 🚨 故障处理

### 场景 1: 进化任务连续失败
**现象**: Cron 日志显示 `status: "error"`

**处理**:
1. 查看错误日志: `cat .pi-invest/cron/cron-runs.jsonl | tail -10`
2. 检查数据文件: `ls -lh .pi-invest/{portfolio,trades}.json`
3. 手动运行测试: `npm run evolution`

### 场景 2: 工具生成失败
**现象**: 执行结果显示 `status: "error"`

**处理**:
1. 查看执行日志: `cat .pi-invest/evolution/execution-*.json`
2. 检查 Git 状态: `git status`
3. 查看沙箱验证结果（日志中会显示）

### 场景 3: 参数超出范围
**现象**: 日志显示 "参数值超出允许范围"

**处理**:
1. 检查参数范围配置是否合理
2. 调整 `parameterRanges` 配置
3. 重新运行进化分析

---

## 📈 效果评估

### 自动化指标

| 指标 | 目标 | 说明 |
|-----|------|------|
| **自动执行率** | 100% | 所有建议自动执行，无需人工 |
| **成功率** | >95% | 执行成功率 |
| **平均耗时** | <5分钟 | 从触发到完成 |
| **回滚率** | <5% | 需要回滚的比例 |

### 查看统计
```bash
# 统计最近 10 次进化的自动化率
cat .pi-invest/evolution/execution-*.json | \
  jq -s 'map(.applied | length) | add / length'
```

---

## ✅ 验证清单

- [x] Cron 任务已启用
- [x] `autoExecute: true`
- [x] `requireApproval: []`（空数组）
- [x] 参数范围已配置
- [x] 沙箱验证已启用
- [x] Git 分支管理已配置
- [x] 自动备份已启用
- [x] 错误恢复机制已配置
- [x] 日志记录完整
- [x] 无需人工干预

---

## 🎯 总结

**当前状态**: ✅ **完全自动化**

- ✅ 每周日 20:00 自动触发
- ✅ 所有优化建议自动执行
- ✅ 无需人工审批或干预
- ✅ 自动生成代码、测试、提交
- ✅ 自动更新经验库
- ✅ 自动调整参数
- ✅ 自动修改提示词
- ✅ 完整的安全机制和错误恢复

**人工介入场景**: 仅当连续失败 5 次时需要检查

---

**配置完成时间**: 2026-05-15  
**配置者**: Claude Code  
**状态**: ✅ 完全自动化运行中

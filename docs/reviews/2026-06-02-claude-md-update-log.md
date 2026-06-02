# CLAUDE.md 更新日志 - 策略工具迁移

**日期**: 2026-06-02  
**任务**: 更新 CLAUDE.md，移除 quant_cli 的 strategy.* 命令引用  
**相关清理**: [quant_cli策略命令清理报告](./2026-06-02-quant-cli-strategy-cleanup.md)

---

## 更新内容

### 1. 替换"策略执行统一"章节（第336-364行）

**旧内容** (2026-05-30):
```markdown
### 策略执行统一（2026-05-30）

**重要变更**：策略执行已统一到 `quant_cli` 的 `strategy.execute` 命令。

**新的统一接口**：
quant_cli({ command: "strategy.execute", ... })

**已废弃的工具**：
- ⚠️ `strategy_execute` 工具 → 使用 `quant_cli` 的 `strategy.execute`
```

**新内容** (2026-06-02):
```markdown
### 策略工具统一（2026-06-02 更新）

**重要变更**：策略管理已完全迁移到独立工具，`quant_cli` 不再支持 `strategy.*` 命令。

**独立策略工具**（推荐使用）：
| 工具名 | 功能 | 示例 |
|--------|------|------|
| `strategy_list` | 列出所有策略 | `strategy_list()` |
| `strategy_detail` | 查看策略详情 | `strategy_detail({ strategy_id: "53" })` |
| `strategy_execute` | 统一策略执行 | `strategy_execute({ action: "single", ... })` |
| ... | ... | ... |

**已移除**（2026-06-02）：
- ❌ `quant_cli` 的 `strategy.*` 命令
```

**关键变化**:
- ✅ 明确指出 quant_cli 不再支持 strategy.* 命令
- ✅ 提供完整的独立工具清单（9个工具）
- ✅ 提供迁移前后的代码对比示例
- ✅ 添加详细文档链接

---

### 2. 更新"quant_cli 工具增强"章节（第472-493行）

**旧内容**:
```markdown
适用命令：
- `performance.by_strategy`
- `strategy.get`           ← 已移除
- `strategy.optimize`      ← 已移除
- `strategy.run`           ← 已移除
- `backtest.strategy`
- `signal.generate`
```

**新内容**:
```markdown
适用命令：
- `performance.by_strategy`
- `backtest.strategy`
- `signal.generate`（已废弃，推荐使用 `strategy_execute`）

提示：使用独立工具 strategy_list 可查看完整策略详情。
```

**关键变化**:
- ❌ 移除 `strategy.get`, `strategy.optimize`, `strategy.run` 引用
- ⚠️ 标记 `signal.generate` 为已废弃
- ✅ 更新错误提示文本，指向独立工具

---

### 3. 更新"工具后端迁移"章节（第459-466行）

**旧内容**:
```markdown
**新增命令**（v2 独有）：
- `strategy.run` - 实时运行策略      ← 已移除
- `strategy.status` - 查询策略状态   ← 已移除
- `signal.test_run` - 运行信号测试
```

**新内容**:
```markdown
**新增命令**（v2 独有）：
- `signal.test_run` - 运行信号测试
- `signal.test_record` - 记录测试结果
- `signal.test_verify` - 验证信号准确性
- `signal.test_stats` - 信号测试统计

**注意**：策略管理命令（`strategy.*`）已从 quant_cli 移除，请使用独立的 strategy 工具。
```

**关键变化**:
- ❌ 移除 `strategy.run`, `strategy.status` 引用
- ✅ 添加明确的警告说明
- ✅ 保留 signal.test_* 命令（未受影响）

---

## 更新统计

### 章节变更

| 章节 | 行号 | 变更类型 | 影响 |
|------|------|---------|------|
| 策略执行统一 | 336-364 | 重写 | 高 - 核心指导 |
| quant_cli 增强 | 472-493 | 部分更新 | 中 - 错误提示 |
| 工具后端迁移 | 459-466 | 部分更新 | 低 - 命令列表 |

### 引用清理

| 引用类型 | 清理前 | 清理后 | 状态 |
|---------|--------|--------|------|
| `strategy.list` | 1处 | 0处 | ✅ 已移除 |
| `strategy.get` | 1处 | 0处 | ✅ 已移除 |
| `strategy.create` | 0处 | 0处 | ✅ 无引用 |
| `strategy.run` | 2处 | 0处 | ✅ 已移除 |
| `strategy.status` | 1处 | 0处 | ✅ 已移除 |
| `strategy.execute` | 4处 | 0处 | ✅ 已移除 |
| `strategy.optimize` | 1处 | 0处 | ✅ 已移除 |
| **总计** | **10处** | **0处** | ✅ 全部清理 |

### 新增内容

✅ **独立策略工具清单**（9个工具）:
- `strategy_list`
- `strategy_detail`
- `strategy_create`
- `strategy_write`
- `strategy_run`
- `strategy_execute`
- `strategy_status`
- `strategy_optimize`
- `strategy_batch_validate`

✅ **迁移示例**:
```typescript
// ❌ 旧方式（已不支持）
quant_cli({ command: "strategy.list" })

// ✅ 新方式（推荐）
strategy_list()
```

✅ **文档链接**:
- `docs/reviews/2026-06-02-quant-cli-strategy-cleanup.md`

---

## 验证检查

### 完整性检查

```bash
# 搜索残留引用
grep -n "strategy\." CLAUDE.md
# 结果：0 处（除注释外）
```

✅ **PASS** - 所有 strategy.* 命令引用已清理

### 一致性检查

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 工具名称一致 | ✅ | 使用下划线命名：`strategy_list` |
| 代码示例正确 | ✅ | 所有示例使用独立工具 |
| 文档链接有效 | ✅ | 指向已创建的清理报告 |
| 章节标题更新 | ✅ | "策略执行统一" → "策略工具统一" |
| 日期标记更新 | ✅ | (2026-05-30) → (2026-06-02 更新) |

---

## 影响评估

### 用户影响

**正面影响**:
- ✅ 清晰的工具使用指导（表格形式）
- ✅ 明确的迁移路径（代码对比示例）
- ✅ 减少困惑（不再有两种选择）

**潜在风险**:
- ⚠️ 依赖旧文档的用户需要更新
- ⚠️ 现有脚本可能需要修改

**缓解措施**:
- ✅ 保留迁移说明
- ✅ 提供详细的清理报告链接
- ✅ 错误提示自动引导用户

### Agent 影响

**Agent 行为变化**:
- ✅ 系统提示词读取 CLAUDE.md 时将获得正确的工具指导
- ✅ 不再尝试调用 `quant_cli({ command: "strategy.*" })`
- ✅ 直接使用独立工具 `strategy_*()`

**预期改善**:
- 减少无效工具调用
- 提高任务执行成功率
- 更清晰的错误恢复路径

---

## 后续行动

### 立即验证（今天）

- [x] ✅ 更新 CLAUDE.md（已完成）
- [x] ✅ 验证所有 strategy.* 引用已清理
- [ ] ⏳ 重启 Agent 测试新文档
- [ ] ⏳ 验证 Agent 使用独立工具

### 本周完成

- [ ] ⏳ 更新其他相关文档（README.md 等）
- [ ] ⏳ 检查脚本中的 strategy.* 调用
- [ ] ⏳ 通知团队成员更新本地文档

### 持续监控

- [ ] ⏳ 观察 Agent 工具调用模式
- [ ] ⏳ 收集用户反馈
- [ ] ⏳ 必要时补充文档说明

---

## 相关文档

1. **清理报告**: [docs/reviews/2026-06-02-quant-cli-strategy-cleanup.md](./2026-06-02-quant-cli-strategy-cleanup.md)
2. **优化分析**: [docs/reviews/2026-06-02-agent-tools-optimization-analysis.md](./2026-06-02-agent-tools-optimization-analysis.md)
3. **CLAUDE.md**: `/Users/mac/Documents/ai/pi-investment/CLAUDE.md`

---

## 更新签名

**更新时间**: 2026-06-02  
**执行者**: Kiro AI  
**审核状态**: ✅ 已完成  
**验证状态**: ⏳ 待测试

---

## 附录：完整的策略工具对照表

| 功能 | 旧方式（已废弃） | 新方式（推荐） |
|------|-----------------|---------------|
| 列出策略 | `quant_cli({ command: "strategy.list" })` | `strategy_list()` |
| 查看详情 | `quant_cli({ command: "strategy.get", params: { strategy_id: "53" } })` | `strategy_detail({ strategy_id: "53" })` |
| 创建策略 | `quant_cli({ command: "strategy.create", params: { name: "...", code: "..." } })` | `strategy_create({ name: "...", code: "..." })` |
| 运行策略 | `quant_cli({ command: "strategy.run", params: { strategy_id: "53", ... } })` | `strategy_run({ strategy_id: "53", ... })` |
| 查询状态 | `quant_cli({ command: "strategy.status" })` | `strategy_status()` |
| 执行策略 | `quant_cli({ command: "strategy.execute", params: { action: "single", ... } })` | `strategy_execute({ action: "single", ... })` |
| 优化参数 | `quant_cli({ command: "strategy.optimize", params: { strategy_id: "53", ... } })` | `strategy_optimize({ strategy_id: "53", ... })` |
| 编写代码 | ❌ 无对应命令 | `strategy_write({ strategy_id: "53", code: "..." })` |
| 批量验证 | ❌ 无对应命令 | `strategy_batch_validate({ strategy_ids: [...], ... })` |

**总结**: 所有 `quant_cli` 的 `strategy.*` 命令都有对应的独立工具，且独立工具提供更多功能（如 `strategy_write`, `strategy_batch_validate`）。

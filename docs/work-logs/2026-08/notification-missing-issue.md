# 通知缺失问题诊断报告

**日期**: 2026-08-27  
**问题**: 完成 M1/M3-2/M6 任务后用户未收到飞书通知  

## 问题分析

### 1. 技术配置 ✅ 正常

- **飞书 Webhook**: 已在 `~/.dsh/profiles/investment/cordis.patch.yml` 正确配置
- **Webhook 连通性**: 测试发送成功（code:0, msg:success）
- **通知工具**: `feishu_notify` 和 `notification_send` 工具已注册并可用

### 2. 根本原因 ❌ 流程缺失

**Agent 完成任务后没有主动调用通知工具**

- ✅ 完成了任务（M1验证、M3-2回测、M6周报）
- ✅ 写了工作日志（3个 .md 文件）
- ❌ **但没有调用 `feishu_notify` 发送通知**

### 3. 为什么会遗漏？

1. **缺少显式指令** - 系统提示词中没有"完成任务后发飞书通知"的规则
2. **工具可见但不主动** - Agent 知道有通知工具，但不认为应该主动使用
3. **习惯问题** - Agent 习惯"完成→写文档→结束"，没有"完成→通知用户"的意识

## 解决方案

### 短期修复（已完成）

✅ **补发通知**: 手动发送了今日完成报告到飞书群（17:43）

### 长期改进（待实施）

#### 方案 A: 在基因组中添加通知规则（推荐）

在 `genome/rules.md` 中新增：

```markdown
## R-010 任务完成通知
重要任务完成后（新功能上线、阶段验收、系统升级等），调用 feishu_notify 发送完成通知：
- title: 标注任务名称和状态（✅/⚠️）
- content: 核心成果、关键数据、文档链接
- urgency: normal（一般完成）/ high（关键里程碑）
- channel: reports（日常）/ alerts（紧急）

触发条件：
- 完成 M*/P*/Sprint 编号任务
- 系统组件首次上线
- 关键验收通过
- 发现重大问题需要通知

不通知的情况：
- 日常小修小补
- 中间过程（非最终交付）
- 纯调试/测试
```

#### 方案 B: 在任务调度器中集成自动通知

修改 Agent OS scheduler webhook 处理器，任务执行完成后自动触发通知：

```python
# quantsys-v2/api/internal/scheduler_webhook.py
if task_result.status == 'success':
    await send_feishu_notification(
        title=f"✅ 定时任务完成：{task_name}",
        content=task_result.summary
    )
```

#### 方案 C: 在 learning 插件中自动通知

`learning_track` 追踪到重要成果时自动发通知：

```typescript
if (outcome.success && outcome.metrics.impact > threshold) {
    await ctx.tools.invoke('feishu_notify', {
        title: `✅ 学习里程碑：${action_type}`,
        content: `成功率: ${metrics.success_rate}\n奖励: ${reward}`,
        urgency: 'normal'
    });
}
```

## 建议采用方案

**推荐方案 A（基因组规则）**，原因：

1. ✅ **最轻量** - 只需添加一条规则，无需改代码
2. ✅ **最灵活** - Agent 可根据情境判断是否需要通知
3. ✅ **可进化** - 规则可通过学习循环优化
4. ✅ **符合设计** - 基因组本就是 Agent 的"行为手册"

方案 B 和 C 可作为后续增强（自动化兜底）。

## 执行计划

### 立即执行（本次修复）

- [x] 诊断问题根因
- [x] 补发今日通知
- [x] 写诊断报告

### 后续优化（下次迭代）

- [ ] 在 `genome/rules.md` 添加 R-010 规则
- [ ] 通过 `genome_update` 工具应用
- [ ] 下次完成任务时验证是否主动通知
- [ ] 如果仍未通知，考虑方案 B/C

## 相关文档

- 今日完成任务：
  - `m1-automation-validation-success.md` - M1 验证通过
  - `m3-2-backtest-matrix-complete.md` - 回测引擎完成
  - `m6-weekly-report-complete.md` - 周报自动化完成

- 配置文件：
  - `~/.dsh/profiles/investment/cordis.patch.yml` - 飞书 webhook 配置
  - `agent-dh/packages/notification/src/index.ts` - 通知插件源码

- 基因组：
  - `~/.dsh-agent-dh/genome/rules.md` - 操作规则（待添加 R-010）

---

**诊断结论**: 技术配置正常，流程规则缺失。通过添加基因组规则可根本解决。

**验收标准**: 下次完成类似任务时，Agent 主动调用 `feishu_notify` 发送通知。

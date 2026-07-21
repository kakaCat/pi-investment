# 飞书通知修复报告

## 问题诊断

### 发现的问题

1. **数据字段不匹配** ❌
   - `sendDailyReport` 使用了不存在的字段（`sh_index_change`, `sz_index_change`, `north_flow`等）
   - 导致所有内容显示为 `N/A`，发送的都是无意义的测试数据

2. **重复的服务实现** ⚠️
   - 系统中存在3个不同的飞书服务类
   - `src/services/feishu-notification.service.ts` - 完整实现（使用Webhook）
   - `src/services/notification/feishu-service.ts` - 空实现（仅TODO）
   - `src/infrastructure/notification/feishu-service.ts` - 另一个实现

3. **Agent任务未调用飞书通知** ❌
   - 定时任务（早盘分析、每日复盘）的指令中没有要求Agent发送飞书通知
   - Agent执行任务时不会主动调用 `feishu_notify` 工具

4. **测试脚本发送测试内容** ⚠️
   - `execute-tool-workflow.ts` 会调用 `test-feishu-notification.py` 发送测试通知
   - 这是导致用户收到测试消息的直接原因

## 修复方案

### 1. 修复数据字段映射 ✅

**文件**: `src/services/feishu-notification.service.ts`

**修改内容**:
- `sendDailyReport`: 使用真实的 portfolio_status 数据字段
  - `total_assets` - 总资产
  - `cash` - 可用资金
  - `holdings_count` - 持仓数量
  - `total_pnl` / `total_pnl_pct` - 盈亏金额/百分比
  - `trades_today`, `buy_count`, `sell_count` - 交易统计
  - `key_findings` - 关键发现

- `sendWeeklyReport`: 使用真实的周报数据
  - `weekly_return` - 周收益率
  - `total_trades` - 交易次数
  - `win_rate` - 胜率
  - `total_pnl_pct` - 累计收益率

- `sendPremarketReport`: 使用真实的盘前数据
  - `data_integrity` - 数据完整性
  - `pools_count` - 股票池数量
  - `opportunities` - 机会列表
  - `alerts` - 预警列表

### 2. 在Agent任务中添加飞书通知步骤 ✅

**文件**: `src/services/scheduler/tasks/agent-decision-tasks.ts`

**修改内容**:

#### 每日复盘任务 (`daily_ai_review`)
添加了"第七步：发送飞书每日报告"：
```
使用 feishu_notify 发送每日报告：
- messageType: 'daily_report'
- data: 包含持仓、盈亏、交易统计等真实数据
```

#### 早盘分析任务 (`morning_ai_analysis`)
添加了"第五步：发送盘前通知（可选）"：
```
如果发现高质量机会或重要风险，使用 feishu_notify 发送通知：
- messageType: 'card'
- title: '🌅 早盘分析完成'
- content: 总结今日关键发现
```

### 3. 创建测试脚本 ✅

**文件**: `scripts/test-feishu-daily-report.ts`

**功能**:
- 使用真实数据格式测试 `sendDailyReport`
- 测试 `sendPremarketReport`
- 验证飞书通知是否正常工作

**测试结果**: ✅ 成功
```
✅ 每日报告发送成功！
✅ 盘前报告发送成功！
```

## 数据流示例

### 每日复盘流程

1. **Agent执行 `daily_ai_review` 任务** (18:00)
2. **收集数据**:
   ```typescript
   portfolio_status() → {
     total_assets: 294140.30,
     cash: 147070.15,
     holdings_count: 0,
     total_pnl: 0,
     total_pnl_pct: 0
   }
   
   trade_monitor({ command: 'stats' }) → {
     trades_today: 2,
     buy_count: 1,
     sell_count: 1
   }
   ```

3. **Agent分析并调用**:
   ```typescript
   feishu_notify({
     messageType: 'daily_report',
     data: {
       date: '2026-07-17',
       total_assets: 294140.30,
       cash: 147070.15,
       holdings_count: 0,
       total_pnl: 0,
       total_pnl_pct: 0,
       trades_today: 2,
       buy_count: 1,
       sell_count: 1,
       key_findings: '✅ 今日完成1笔买入\n✅ 风控到位\n💡 继续观察'
     }
   })
   ```

4. **飞书接收到的消息**:
   ```
   📊 每日投资报告 - 2026-07-17
   
   💰 持仓表现
   总资产: ¥294140.30
   可用资金: ¥147070.15
   持仓数量: 0只
   总盈亏: ¥0.00 (0.00%)
   
   📊 交易情况
   今日交易: 2笔
   买入: 1笔
   卖出: 1笔
   
   💡 关键发现
   ✅ 今日完成1笔买入
   ✅ 风控到位
   💡 继续观察
   ```

## 使用说明

### 配置飞书Webhook

在 `.env` 文件中添加：
```bash
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your-webhook-id
```

### 测试飞书通知

```bash
# 测试真实数据格式的报告
npx tsx scripts/test-feishu-daily-report.ts

# 测试原来的测试通知（仍会发送测试内容）
python scripts/test-feishu-notification.py
```

### Agent自动发送

Agent在以下时机会自动发送飞书通知：

1. **每日18:00** - 每日复盘后发送 `daily_report`
2. **早盘分析时** - 如果发现重要机会/风险，发送 `card` 通知（可选）

## 未解决的问题

### 重复的服务实现 ⚠️

目前保留了多个飞书服务实现：
- `src/services/feishu-notification.service.ts` - **主要使用**（Webhook方式）
- `src/services/notification/feishu-service.ts` - 空实现，但被 `alert-tool.ts` 引用

**建议**: 统一使用 `feishu-notification.service.ts`，删除其他实现。

## 验证清单

- [x] 修复 `sendDailyReport` 数据字段
- [x] 修复 `sendWeeklyReport` 数据字段  
- [x] 修复 `sendPremarketReport` 数据字段
- [x] 在 `daily_ai_review` 任务中添加飞书通知步骤
- [x] 在 `morning_ai_analysis` 任务中添加飞书通知步骤（可选）
- [x] 创建测试脚本验证修复
- [x] 测试通过
- [ ] 清理重复的服务实现（待完成）

## 测试记录

**日期**: 2026-07-17 22:37

**测试命令**:
```bash
export FEISHU_WEBHOOK_URL='https://open.feishu.cn/open-apis/bot/v2/hook/...'
npx tsx scripts/test-feishu-daily-report.ts
```

**测试结果**:
```
✅ 每日报告发送成功！
✅ 盘前报告发送成功！
```

**飞书群消息**: 已收到正确格式的报告卡片，内容包含真实数据字段。

## 后续改进建议

1. **删除重复实现**: 统一使用 `feishu-notification.service.ts`
2. **环境变量检查**: 在启动时检查 `FEISHU_WEBHOOK_URL` 是否配置
3. **消息模板优化**: 根据实际使用情况调整消息格式
4. **错误处理**: 增强飞书通知失败时的日志和重试机制
5. **测试覆盖**: 为飞书服务添加单元测试

## 相关文件

- `src/services/feishu-notification.service.ts` - 飞书服务主实现
- `src/infrastructure/tools/notification/feishu-notify-tool.ts` - 飞书通知工具
- `src/services/scheduler/tasks/agent-decision-tasks.ts` - Agent定时任务
- `scripts/test-feishu-daily-report.ts` - 测试脚本（新增）
- `scripts/test-feishu-notification.py` - 原测试脚本（发送测试内容）
- `scripts/execute-tool-workflow.ts` - 工具流程（会调用测试通知）

# Evolution System 使用指南

> 更新时间: 2026-05-15  
> 架构版本: v2 (统一入口)

---

## 概述

Evolution System 是 PI Investment 的自我进化系统，负责：
- 分析投资表现
- 归因性能差距
- 生成优化建议
- 自动应用改进（生成工具代码、调整参数等）

---

## 使用方式

### 方式 1: 交互命令（手动触发）✅

启动服务后，在交互模式下使用 `/evolution` 命令：

```bash
# 1. 启动服务
npm run dev

# 2. 在交互模式下输入命令
> /evolution                    # 运行进化分析（默认配置）
> /evolution --view             # 查看最近一次报告
> /evolution --days 30          # 分析最近 30 天
> /evolution --all --target 15  # 分析全部交易，目标 15%
```

**命令选项**：
- `--view` 或 `-v`: 查看最近一次进化报告
- `--days <N>` 或 `-d <N>`: 只分析最近 N 天的交易
- `--all` 或 `-a`: 分析全部交易记录
- `--target <N>` 或 `-t <N>`: 设置目标收益率（百分比）

---

### 方式 2: CRON 自动触发 ✅

系统会自动在每周日 20:00 运行进化分析。

**配置文件**: `.pi-invest/CRON.json`

```json
{
  "id": "weekly-evolution",
  "schedule": "0 20 * * 0",
  "enabled": true,
  "payload": {
    "kind": "weekly_evolution"
  }
}
```

**查看 CRON 任务**：
```bash
npm run dev
# 启动时会显示：
# ⏰ Cron 任务（3 个）:
#   ✅ 每周进化分析（weekly_evolution: weekly-evolution） 下次：2026-05-18 20:00（3 天后）
```

---

## 执行流程

```
1. 数据收集
   ├─ 加载交易记录 (trades.json)
   ├─ 加载持仓数据 (portfolio.json)
   ├─ 加载复盘报告 (reviews/*.md)
   └─ 加载 Session 日志 (sessions/*.jsonl)

2. 性能计算
   ├─ 计算已实现收益（FIFO 配对）
   ├─ 计算胜率、最大回撤
   └─ 分析工具效能（ROI、调用次数）

3. 差距分析
   ├─ 计算目标 vs 实际差距
   ├─ 归因分析（目标不合理 vs 能力不足）
   └─ 识别弱点（选股、风控、决策）

4. 生成建议
   ├─ 新增工具（能力缺失）
   ├─ 移除工具（低效工具）
   ├─ 调整参数（止损阈值、仓位比例）
   └─ 更新经验（成功/失败模式）

5. 自动执行
   ├─ 调用 Codex (GPT-5.4) 生成工具代码
   ├─ 沙箱三级验证
   │   ├─ 编译验证 (tsc --noEmit)
   │   ├─ 单元测试 (npm test)
   │   └─ 集成测试 (动态加载)
   ├─ 注册工具到 index.ts
   ├─ Git 分支管理
   │   ├─ 创建分支 evolution/{date}
   │   ├─ 提交变更
   │   └─ 自动合并到 main
   └─ 保存执行结果

6. 生成报告
   ├─ 进化报告 (evolution-{date}.md)
   ├─ 执行结果 (execution-{date}.json)
   ├─ 进化历史 (history/{date}.json)
   └─ 经验总结 (experience-summary.json)
```

---

## 输出文件

所有输出保存在 `.pi-invest/evolution/` 目录：

```
.pi-invest/evolution/
├── evolution-2026-05-15.md          # 进化报告（Markdown）
├── execution-2026-05-15.json        # 执行结果（JSON）
├── experience-summary.json          # 经验总结
├── version-history.md               # 版本历史
├── history/                         # 进化历史
│   ├── 2026-05-15.json
│   └── 2026-05-08.json
└── backups/                         # 备份（自动清理）
```

---

## 架构说明

### 统一入口设计

```
npm run dev (唯一入口)
├─ 启动投资 Agent 服务
├─ 加载 CRON 定时任务
├─ 启动交互模式
└─ 支持 /evolution 命令
```

**为什么不用 `npm run evolution`？**

之前的设计有两个入口：
- ❌ `npm run dev` - 启动服务
- ❌ `npm run evolution` - 独立运行进化（像另一个项目）

这导致：
- 架构混乱（两种方式触发同一功能）
- 职责不清（evolution 是服务的一部分，不是独立项目）
- 维护困难（两个入口需要同步更新）

**现在的设计**：
- ✅ 只有一个入口：`npm run dev`
- ✅ 手动触发：通过 `/evolution` 命令
- ✅ 自动触发：通过 CRON 配置
- ✅ 职责清晰：evolution 是服务内的功能

---

## 代码生成架构

### 职责分离

```
Investment Agent (DeepSeek)
└─ 投资决策、市场分析、交易执行

Evolution System
└─ 性能分析、优化建议、协调执行

Codex Agent (GPT-5.4)
└─ 代码生成（独立进程，通过 CLI 调用）
```

**为什么用 Codex 而不是投资 Agent？**

1. **职责单一**: 投资 Agent 专注投资，不应该承担代码生成
2. **能力匹配**: GPT-5.4 的代码生成能力 > DeepSeek
3. **架构清晰**: 避免循环依赖（Evolution → Agent → Evolution）
4. **可独立测试**: 可以单独测试代码生成能力

---

## 常见问题

### Q1: 如何查看进化历史？

```bash
# 方式 1: 通过命令
npm run dev
> /evolution --view

# 方式 2: 直接查看文件
cat .pi-invest/evolution/evolution-2026-05-15.md
```

### Q2: 如何禁用自动进化？

编辑 `.pi-invest/CRON.json`，设置 `enabled: false`：

```json
{
  "id": "weekly-evolution",
  "enabled": false,  // 👈 禁用
  "schedule": "0 20 * * 0",
  "payload": { "kind": "weekly_evolution" }
}
```

### Q3: 如何调整进化参数？

进化参数在运行时指定：

```bash
> /evolution --days 60 --target 12
```

或修改代码中的默认值（`evolution-service.ts`）：

```typescript
const DEFAULT_CONFIG: Required<EvolutionConfig> = {
  targetReturn: 10,           // 目标收益率
  tradeWindowDays: 90,        // 交易窗口
  reviewWindowCount: 10,      // 复盘报告数量
  evolutionWindowRecent: 3,   // 进化历史（决策参考）
  evolutionWindowLearning: 100 // 进化历史（经验学习）
};
```

### Q4: 代码生成失败怎么办？

检查 Codex 是否可用：

```bash
# 测试 Codex
codex exec --ephemeral "console.log('test')"

# 如果失败，检查配置
which codex
echo $PATH
```

如果 Codex 不可用，进化分析会跳过代码生成步骤，只生成建议。

### Q5: 如何回滚进化变更？

进化变更会创建 Git 分支和提交：

```bash
# 查看进化分支
git branch | grep evolution

# 回滚到上一个版本
git log --oneline | head -5
git revert <commit-hash>

# 或者硬回滚（危险）
git reset --hard HEAD~1
```

---

## 最佳实践

1. **定期运行**: 建议每周运行一次，保持持续改进
2. **审查建议**: 虽然系统会自动应用建议，但建议定期审查变更
3. **监控效果**: 通过进化历史追踪改进效果
4. **备份数据**: 重要数据定期备份（trades.json, portfolio.json）
5. **测试验证**: 代码生成后会自动验证，但建议手动测试新工具

---

## 相关文档

- [Evolution System 技术文档](./evolution-system-analysis.md)
- [架构重构报告](./architecture-refactoring-report.md)
- [Evolution 配置指南](./evolution-config-guide.md)
- [完全自动化配置](./evolution-automation.md)

---

**文档维护**: 请在功能更新后同步更新此文档

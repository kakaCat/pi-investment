# Agent OS 执行计划概览

> **创建时间**: 2026-08-13  
> **目标**: 用最简洁的方式说清楚执行计划  
> **总工期**: 11 天，6 个批次

---

## 📊 批次总览

| 批次 | 天数 | 并行任务数 | 主要内容 |
|---|---|---|---|
| **Batch 0** | 1 天 | 1 个 | 项目脚手架 |
| **Batch 1** | 3 天 | 3 个 ⚡ | 核心模块（Scheduler + Resource + Memory） |
| **Batch 2** | 2 天 | 1 个 | agent-ts 集成 |
| **Batch 3** | 2 天 | 3 个 ⚡ | Driver + Decision |
| **Batch 4** | 2 天 | 1 个 | 权限 + Event Bus |
| **Batch 5** | 1 天 | 1 个 | 生产优化 |

**⚡ = 最大并行度，需要你审核 3 个模块**

---

## Batch 0: 项目脚手架（Day 1）

### 并行任务数: 1 个

| 任务 | 负责人 | 工作内容 | 验收标准 |
|---|---|---|---|
| **WP-0** | Agent-A | • Go 项目结构<br>• CLI 框架（Cobra）<br>• 配置系统（Viper）<br>• 日志系统（Zap）<br>• 数据库 Schema | `agent-os version` 能运行 |

### 你的工作
- **晚上审核**: 
  ```bash
  cd .claude/worktrees/wp-0-scaffold
  go build -o agent-os ./cmd/agent-os
  ./agent-os version
  ./agent-os help
  ```
- **检查点**: 项目能编译、命令能运行

---

## Batch 1: 核心模块（Day 2-4）

### 并行任务数: 3 个（同时进行）⚡

| 任务 | 负责人 | 工作内容 | 验收标准 |
|---|---|---|---|
| **WP-1: Scheduler** | Agent-A | • TaskRepository<br>• Scheduler 核心逻辑<br>• DAG 依赖解析<br>• Executor（超时/重试）<br>• CLI 命令 | 任务能注册、触发、查历史 |
| **WP-2: Resource Manager** | Agent-B | • Quota Manager<br>• Namespace Manager<br>• 配额配置加载<br>• CLI 命令 | 配额查询正常 |
| **WP-3: Memory System** | Agent-C | • Memory Store<br>• BM25 + Vector 检索<br>• 数据表迁移<br>• CLI 命令 | 记忆能写入、搜索 |

### 你的工作
- **Day 2-4 每晚**: 审核当天完成的模块
- **Day 4 晚（重要）**: 集成测试
  ```bash
  # 3 个模块合并后测试
  go build -o agent-os ./cmd/agent-os
  ./agent-os scheduler list
  ./agent-os resource quota --agent fin-agent
  ./agent-os memory search --query test
  go test ./... -v
  ```
- **检查点**: 3 个模块能协同工作

---

## Batch 2: Agent 集成（Day 5-6）

### 并行任务数: 1 个

| 任务 | 负责人 | 工作内容 | 验收标准 |
|---|---|---|---|
| **WP-4: agent-ts 切换** | Agent-A | • CLI 执行器（agent-os-cli.ts）<br>• 工具改写（memory_write 等）<br>• 任务注册逻辑<br>• Webhook 接口<br>• 删除本地 Cron | agent 完全依赖 OS |

### 你的工作
- **端到端测试**:
  1. 启动 OS daemon
  2. 启动 agent-ts
  3. 观察任务注册
  4. 手动触发任务
  5. 观察 agent 调用工具
- **检查点**: agent → OS → agent 完整流程正常

---

## Batch 3: Driver + Decision（Day 7-8）

### 并行任务数: 3 个（同时进行）⚡

| 任务 | 负责人 | 工作内容 | 验收标准 |
|---|---|---|---|
| **WP-5: Market Driver** | Agent-A | • Python CLI (market-driver)<br>• AKShare 适配器<br>• OS Data 命令<br>• Redis 缓存 | 行情查询正常 |
| **WP-6: Feishu Driver** | Agent-B | • Python CLI (feishu-driver)<br>• 飞书 Webhook API<br>• Notification Manager<br>• OS Notify 命令 | 飞书收到通知 |
| **WP-7: Decision System** | Agent-C | • Decision Store<br>• 数据表迁移<br>• CLI 命令 | 决策能记录、查询 |

### 你的工作
- **Day 7-8 每晚**: 审核当天完成的模块
- **测试重点**:
  ```bash
  # 行情查询
  agent-os data quote --symbol 600519.SH
  
  # 飞书通知
  agent-os notify send --user yunpeng --title "测试" --message "测试消息"
  
  # 决策记录
  agent-os decision record --action watch --targets '["600519.SH"]'
  ```
- **检查点**: 能查行情、收到飞书通知、决策能记录

---

## Batch 4: 权限 + Event Bus（Day 9-10）

### 并行任务数: 1 个

| 任务 | 负责人 | 工作内容 | 验收标准 |
|---|---|---|---|
| **WP-8: 权限 + Event Bus** | Agent-A | • AuthManager（权限检查）<br>• Event Bus（PG NOTIFY）<br>• WebSocket 订阅接口<br>• CLI/API 权限集成 | memory-agent 不能调 trading |

### 你的工作
- **权限测试**:
  ```bash
  # memory-agent 调用 trading 命令应该被拒绝
  AGENT_ID=memory-agent agent-os trading order ...
  # 预期输出: Error: permission denied
  ```
- **WebSocket 测试**: 浏览器打开 web-frontend，观察任务完成通知
- **检查点**: 权限拒绝生效、WebSocket 推送正常

---

## Batch 5: 生产优化（Day 11）

### 并行任务数: 1 个

| 任务 | 负责人 | 工作内容 | 验收标准 |
|---|---|---|---|
| **WP-9: 生产优化** | Agent-A | • 性能基准测试<br>• Prometheus 监控<br>• 部署脚本<br>• 文档完善<br>• 回归测试 | 性能达标、生产稳定 |

### 你的工作
- **性能测试**:
  ```bash
  # CLI 调用延迟 < 100ms
  time agent-os scheduler list
  
  # Memory 写入延迟 < 200ms
  time agent-os memory write --content "test" --category test
  ```
- **部署测试**: 运行部署脚本，生产环境试运行 24 小时
- **检查点**: 性能达标、无故障运行

---

## 📅 时间线可视化

```
Day 1:    ▓ Batch 0 (1 任务)
          ↓ 你审核

Day 2-4:  ▓▓▓ Batch 1 (3 并行任务) ← 高峰期
          ↓ Day 2 晚审核 1 个
          ↓ Day 3 晚审核 1 个
          ↓ Day 4 晚审核 1 个 + 集成测试

Day 5-6:  ▓▓ Batch 2 (1 任务)
          ↓ Day 6 晚审核 + 端到端测试

Day 7-8:  ▓▓▓ Batch 3 (3 并行任务) ← 高峰期
          ↓ Day 7 晚审核 1-2 个
          ↓ Day 8 晚审核剩余 + 测试

Day 9-10: ▓▓ Batch 4 (1 任务)
          ↓ Day 10 晚审核

Day 11:   ▓ Batch 5 (1 任务)
          ↓ 晚上全面测试 + 生产部署
```

---

## 🤖 协作方式说明

### Agent 角色
- **Agent-A/B/C**: 实际上都是我扮演的
- 我会轮流写不同模块的代码
- 并行批次中，我会在一天内完成多个模块
- 每完成一个模块，立即通知你审核

### 你的角色
- **审核员**: 审核代码、运行测试、给出反馈
- **决策者**: 通过/修改/重做
- **集成验证**: 多模块合并后测试协同工作

### 工作节奏
- **白天**: 我写代码，你可以做其他事
- **晚上**: 我完成通知你 → 你审核 → 给反馈 → 我修复（如果需要）
- **高峰期**（Day 2-4, 7-8）: 你需要审核 3 个模块，预计 1-2 小时

---

## ✅ 审核清单（通用）

### 快速检查（5 分钟）
```bash
# 1. 编译检查
go build -o agent-os ./cmd/agent-os

# 2. 命令检查
./agent-os help

# 3. 测试检查
go test ./...
```

### 深度审核（30 分钟）
- [ ] 代码结构清晰（Clean Architecture）
- [ ] 命令功能正常
- [ ] 单元测试通过
- [ ] 代码质量良好（错误处理、注释）
- [ ] 集成无冲突（多模块合并后）

---

## 📝 沟通模板

### 启动批次
你说：
```
"启动 Batch X"
```

### 询问进度
你说：
```
"进度如何？"
```

我回：
```
"Batch 1 进度：
  WP-1: ✅ 已完成
  WP-2: 🔄 进行中 (70%)
  WP-3: ⏸️ 待开始"
```

### 给出反馈
你说：
```
"WP-X 审核：✅ 通过"
```

或：
```
"WP-X 审核：🔄 需要修改
- 问题 1: ...
- 问题 2: ..."
```

---

## 🚀 准备开工？

**现在告诉我**：

1. **"启动 Batch 0"** → 我立即建项目脚手架
2. **"明天启动"** → 我等你
3. **"还有问题"** → 我继续回答

**等你指令！** 🔥

---

## 📝 执行记录

### ✅ Batch 0: 项目脚手架（已完成）

**日期**: 2026-08-13  
**状态**: ✅ 已完成并合并到 main

- ✅ WP-0: 项目脚手架
  - Git 提交: cb08e28
  - 验收报告: WP-0-ACCEPTANCE.md
  - 包含: Go 项目结构、CLI 框架、配置系统、日志系统、数据库 Schema

---

### ✅ Batch 1: 核心模块（已完成）

**日期**: 2026-08-14  
**状态**: ✅ 三个模块全部完成并合并到 main  
**并行任务数**: 3 个同时进行

#### WP-1: Scheduler Core ✅
- **分支**: feat/wp-1-scheduler
- **提交**: effc584
- **测试**: 8/8 单元测试通过，验收测试通过
- **功能**:
  - ✅ 任务注册、触发、查询、删除
  - ✅ Cron 定时调度
  - ✅ DAG 依赖管理（循环检测、拓扑排序）
  - ✅ 超时/重试/并发控制
  - ✅ 5 个 CLI 子命令
- **文档**: WP-1-COMPLETION-REPORT.md

#### WP-2: Resource Manager ✅
- **分支**: feat/wp-2-resource-manager
- **提交**: 32425bc
- **测试**: 6/6 单元测试 + 8/8 集成测试通过
- **功能**:
  - ✅ Quota 管理（api_calls, tokens, memory）
  - ✅ Namespace 管理（4 个命名空间）
  - ✅ 使用追踪和历史记录
  - ✅ 健康监控（warning/critical 告警）
  - ✅ 7 个 CLI 子命令
- **文档**: WP-2-SUMMARY.md, WP-2-ACCEPTANCE.md

#### WP-3: Memory System ✅
- **分支**: feat/wp-3-memory
- **提交**: 56f30b3, 9b7a4dc
- **测试**: 7/7 单元测试 + 8/8 CLI 测试通过
- **功能**:
  - ✅ Memory CRUD 操作
  - ✅ BM25 全文搜索（PostgreSQL ts_rank_cd）
  - ✅ Vector 向量搜索（余弦相似度）
  - ✅ Hybrid 混合搜索（RRF 融合）
  - ✅ Tag 管理和 Namespace 隔离
  - ✅ 7 个 CLI 子命令
- **文档**: WP-3-ACCEPTANCE.md, WP-3-DELIVERY.md

**审核结果**: ⭐⭐⭐⭐⭐ 全部通过  
**合并时间**: 2026-08-14 00:14  
**推送状态**: ✅ 已推送到 origin/main

---

### 🔄 Batch 2: agent-ts 集成（Day 1 完成）

**开始日期**: 2026-08-14  
**预计工期**: 2 天（Day 5-6）  
**并行任务数**: 1 个

#### WP-4: agent-ts 切换
- **分支**: feat/wp-4-agent-integration
- **提交**: f3de87b
- **目标**: agent-ts 完全依赖 Agent OS
- **工作内容**:
  - ✅ CLI 执行器（agent-os-cli.ts）- 476 行
  - ✅ 工具改写（memory_write 等）- 154 行
  - ✅ 任务注册逻辑 - 143 行
  - ✅ Webhook 接口 - 155 行
  - ⏸️ 删除本地 Cron（待 Day 2）
  - ⏸️ 集成到 index.ts（待 Day 2）
  - ⏸️ 端到端测试（待 Day 2）
- **验收标准**: agent → OS → agent 完整流程正常

**当前状态**: ✅ Day 1 核心模块完成（70%），等待审核

**Day 1 交付物**:
1. ✅ agent-os-cli.ts - CLI 执行器（Scheduler/Resource/Memory API）
2. ✅ memory-tool-agentOS.ts - Memory 工具（Agent OS 版本）
3. ✅ task-registration.ts - 任务注册逻辑（4 个预定义任务）
4. ✅ webhook-server.ts - Webhook 服务器（Express）
5. ✅ test-wp4.sh - 验收测试脚本
6. ✅ WP-4-COMPLETION-REPORT.md - 完成报告

**测试结果**: 6/6 测试通过
- ✅ TypeScript 编译检查（4 个文件）
- ✅ 依赖检查
- ✅ 文件结构检查

**Day 2 计划**:
- [ ] 实现 TaskExecutor 接口
- [ ] 集成到 src/index.ts（启动时注册任务 + Webhook 服务器）
- [ ] 切换 memory 工具到 Agent OS 版本
- [ ] 端到端测试（agent → OS → agent 流程）
- [ ] 删除本地 Cron 代码

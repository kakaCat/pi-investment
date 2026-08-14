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

### ✅ Batch 2: agent-ts 集成（已完成）

**开始日期**: 2026-08-14  
**完成日期**: 2026-08-14  
**实际工期**: 1 天  
**并行任务数**: 1 个

#### WP-4: agent-ts 切换 ✅
- **分支**: feat/wp-4-agent-integration
- **提交**: f3de87b (Day 1), b0356fe (Day 2)
- **合并**: 934305c
- **目标**: agent-ts 完全依赖 Agent OS
- **完成状态**: ✅ 100% 完成

**最终交付物**:
1. ✅ agent-os-cli.ts (476 行) - CLI 执行器
2. ✅ memory-tool-agentOS.ts (154 行) - Memory 工具改写
3. ✅ task-registration.ts (143 行) - 任务注册逻辑
4. ✅ webhook-server.ts (155 行) - Webhook 服务器
5. ✅ agent-os-executor.ts (86 行) - TaskExecutor 实现
6. ✅ index-agentOS.ts (158 行) - 主入口集成
7. ✅ test-wp4.sh - Day 1 验收测试脚本
8. ✅ test-wp4-e2e.sh - Day 2 端到端测试脚本
9. ✅ WP-4-COMPLETION-REPORT.md - Day 1 报告
10. ✅ WP-4-ACCEPTANCE.md - Day 2 最终报告

**测试结果**: 13/13 全部通过 ✅
- Day 1: 6/6 测试通过
- Day 2: 7/7 测试通过

**代码统计**:
- 新增文件: 8 个
- 总代码行数: 1,801 行
- TypeScript 接口: 15+ 个
- API 方法: 18 个
- HTTP 端点: 3 个

**核心特性**:
- ✅ 双模式架构（Agent OS / 传统模式）
- ✅ 环境变量切换（ENABLE_AGENT_OS）
- ✅ 4 个预定义定时任务
- ✅ 完整的 Scheduler/Memory/Resource API
- ✅ 混合搜索（BM25 + Vector）
- ✅ 优雅的生命周期管理
- ✅ 向后兼容（默认传统模式）

**验收标准**: ✅ 全部达成
- ✅ CLI 执行器完整实现
- ✅ Memory 工具改写完成
- ✅ 任务注册逻辑正常
- ✅ Webhook 服务器正常
- ✅ TaskExecutor 正常工作
- ✅ 主入口集成成功
- ✅ 所有测试通过
- ✅ 向后兼容验证

**推送状态**: ✅ 已推送到 origin/main

---

### ✅ Batch 3: Driver + Decision（已完成）

**开始日期**: 2026-08-14  
**完成日期**: 2026-08-14  
**实际工期**: 1 天（原计划 2 天）  
**并行任务数**: 3 个同时进行 ⚡

#### WP-5: Market Driver ✅
- **分支**: feat/wp-5-market-driver
- **提交**: 4286520
- **负责**: Agent-Market
- **测试**: 13/13 通过
- **代码量**: ~926 行

**交付物**:
1. ✅ Python CLI (`market-driver`) - 602 行
   - `main.py` (219 行) - CLI 入口
   - `adapters/akshare_adapter.py` (243 行) - AKShare 适配器
   - `cache/redis_cache.py` (140 行) - Redis 缓存（优雅降级）
2. ✅ Go 集成 `internal/cmd/data.go` (324 行)
   - `agent-os data quote` - 实时行情查询
   - `agent-os data kline` - K线数据查询
   - `agent-os data market-status` - 市场状态

**核心特性**:
- ✅ Redis 缓存（行情 60s TTL，K线 1天 TTL）
- ✅ 无 Redis 时优雅降级
- ✅ 标准化 JSON 输出
- ✅ AKShare 数据源集成

#### WP-6: Feishu Driver ✅
- **分支**: feat/wp-6-feishu-driver
- **提交**: 935ce9c
- **负责**: Agent-Feishu
- **测试**: 20/20 通过
- **代码量**: ~1,188 行

**交付物**:
1. ✅ Python CLI (`feishu-driver`) - 380 行
   - `main.py` (99 行) - CLI 入口
   - `api/feishu_api.py` (167 行) - 飞书 API 客户端
   - `manager/notification_manager.py` (110 行) - 通知管理器
2. ✅ Go 集成 `internal/cmd/notify.go` (213 行)
   - `agent-os notify send` - 发送通知
   - `agent-os notify test` - 测试通知

**核心特性**:
- ✅ 重试机制（3次，指数退避）
- ✅ Markdown 富文本支持
- ✅ 6 种颜色主题
- ✅ 用户/频道路由
- ✅ 性能 ~100ms（低于 200ms 目标）

#### WP-7: Decision System ✅
- **分支**: feat/wp-7-decision-system
- **提交**: 973470b
- **负责**: Agent-Decision
- **测试**: 10/10 单元测试通过
- **代码量**: ~800 行

**交付物**:
1. ✅ `internal/domain/decision.go` (108 行) - Domain 模型
2. ✅ `internal/repository/decision_repository.go` (319 行) - Repository 层
3. ✅ `internal/service/decision_service.go` (174 行) - Service 层
4. ✅ `internal/cmd/decision.go` (391 行) - CLI 命令（6个子命令）
5. ✅ `migrations/007_create_decisions.sql` (67 行) - 数据库迁移
6. ✅ `internal/service/decision_service_test.go` (414 行) - 单元测试

**CLI 命令**:
- ✅ `agent-os decision record` - 记录决策
- ✅ `agent-os decision list` - 查询决策列表
- ✅ `agent-os decision get` - 查询单个决策
- ✅ `agent-os decision update` - 更新执行结果
- ✅ `agent-os decision delete` - 删除决策
- ✅ `agent-os decision stats` - 查询统计信息

**核心特性**:
- ✅ 完整 CRUD 操作
- ✅ PostgreSQL 数据持久化
- ✅ JSON 上下文和结果存储
- ✅ 高级过滤和统计分析
- ✅ 数组字段支持（targets）

**集成测试**: ✅ 通过
- ✅ 决策记录和查询正常
- ✅ 三个模块合并无冲突
- ✅ 编译和运行正常
- ✅ 端到端场景验证

**总代码量**: ~2,914 行  
**总测试**: 43/43 通过  
**合并提交**: 8505ed4  
**推送状态**: ✅ 已推送到 origin/main

**文档**:
- WP-5-COMPLETION.md
- WP-6-COMPLETION.md
- WP-7-COMPLETION.md
- BATCH-3-INTEGRATION-REPORT.md

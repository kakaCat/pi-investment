# Agent OS 并行开发操作手册（超详细版）

> **目标**: 让你能轻松执行、审核、推进 Agent OS 开发  
> **原则**: 每一步都有明确指令，不需要猜测

---

## 📖 目录

1. [开工前准备](#1-开工前准备)
2. [你的日常操作流程](#2-你的日常操作流程)
3. [每个 WP 的详细执行步骤](#3-每个-wp-的详细执行步骤)
4. [审核操作指南](#4-审核操作指南)
5. [问题处理预案](#5-问题处理预案)
6. [常用命令速查表](#6-常用命令速查表)

---

## 1. 开工前准备

### 1.1 确认当前系统状态

```bash
# 进入项目根目录
cd /Users/yunpeng/pi-investment

# 确认当前分支
git status
# 应该在 main 分支，工作区干净

# 确认现有系统正常
cd agent-ts && npm run check:tool-refs
cd ../quantsys-v2 && python -m pytest tests/ -v
```

### 1.2 创建 Agent OS 工作目录

```bash
# 在项目根目录
mkdir -p agent-os
cd agent-os

# 初始化 Git（如果还没有）
git init
```

### 1.3 准备协作环境

**你需要的工具**：
- **终端**: iTerm2 或系统终端
- **编辑器**: VS Code（建议装 Go 插件）
- **浏览器**: 用于查看文档、测试 HTTP API

**我需要的权限**：
- 读写 `/Users/yunpeng/pi-investment/agent-os/` 目录
- 执行 `go build`、`go test` 等命令
- 创建 worktree（每个 WP 一个）

---

## 2. 你的日常操作流程

### 2.1 早上（启动新的 WP）

#### Step 1: 查看今天的任务

打开计划文件：
```bash
cat docs/superpowers/plans/2026-08-13-agent-os-parallel-plan.md
```

找到今天要做的 WP，例如 Day 1 是 WP-0。

#### Step 2: 告诉我启动

在 Claude 对话中说：
```
"启动 WP-0，开始写代码"
```

或者更具体：
```
"今天是 Day 1，按照计划启动 WP-0（项目脚手架），请开始"
```

#### Step 3: 我创建 Worktree 并开始工作

我会：
1. 创建 worktree：`git worktree add .claude/worktrees/wp-0-scaffold main`
2. 在 worktree 中创建代码
3. 边写边告诉你进度

你需要：
- **等待**：我写代码时你可以做别的事
- **关注进度**：我会定期告诉你进度（例如"已完成 60%"）

---

### 2.2 晚上（审核当天工作）

#### Step 1: 我完成工作后会通知你

我会说：
```
✅ WP-0 已完成，代码已提交到 worktree: .claude/worktrees/wp-0-scaffold
请审核：
  1. 项目结构
  2. go build 能否编译
  3. agent-os version 能否运行
```

#### Step 2: 你进入 Worktree 审核

```bash
# 进入 worktree
cd /Users/yunpeng/pi-investment/.claude/worktrees/wp-0-scaffold

# 查看项目结构
tree -L 3

# 查看关键文件
cat cmd/agent-os/main.go
cat internal/cli/root.go
cat go.mod
```

#### Step 3: 编译测试

```bash
# 安装依赖
go mod download

# 编译
go build -o agent-os ./cmd/agent-os

# 测试基础命令
./agent-os version
./agent-os help
./agent-os --help
```

**预期结果**：
```
$ ./agent-os version
agent-os version 0.1.0

$ ./agent-os help
Agent OS - AI Agent 的操作系统

Usage:
  agent-os [command]

Available Commands:
  daemon      管理 daemon 进程
  help        Help about any command
  version     显示版本信息
...
```

#### Step 4: 运行测试（如果有）

```bash
go test ./... -v
```

#### Step 5: 审核代码质量

打开 VS Code：
```bash
code .
```

重点看：
- `cmd/agent-os/main.go` - 入口清晰吗？
- `internal/cli/` - 命令结构合理吗？
- `internal/kernel/` - 核心逻辑分层清楚吗？
- `pkg/types/` - 类型定义完整吗？

**快速审核清单**：
- [ ] 代码能编译
- [ ] 命令能运行
- [ ] 项目结构清晰（符合 Clean Architecture）
- [ ] 有基本的错误处理
- [ ] 有日志输出

#### Step 6: 给出审核结果

在 Claude 对话中回复我：

**通过** ✅：
```
"WP-0 审核通过，可以合并到 main"
```

**需要修改** 🔄：
```
"WP-0 需要修改以下问题：
1. main.go 第 23 行错误处理不完整
2. 缺少配置文件加载逻辑
3. 日志格式需要统一

请修复后重新提交"
```

**重做** ❌（严重问题）：
```
"WP-0 需要重做：
- 项目结构不符合 Clean Architecture
- 建议参考 <具体项目> 的结构
- 重新设计后再实现"
```

#### Step 7: 我根据反馈处理

- **通过**：我合并代码到 main，删除 worktree，进入下一个 WP
- **修改**：我在同一个 worktree 修复问题，修复后再次通知你审核
- **重做**：我删除 worktree，重新设计后再实现

---

### 2.3 多个 WP 并行时（Day 2-4）

#### Step 1: 我启动 3 个 WP

早上我会说：
```
今天启动 Stage 1 并行开发，3 个 WP：
  - WP-1: Scheduler Core (worktree: wp-1-scheduler)
  - WP-2: Resource Manager (worktree: wp-2-resource)
  - WP-3: Memory System (worktree: wp-3-memory)

我会轮流完成这 3 个 WP，每完成一个通知你审核
```

#### Step 2: 我逐个完成并通知

**完成第 1 个**：
```
✅ WP-1 (Scheduler Core) 已完成
Worktree: .claude/worktrees/wp-1-scheduler
请审核调度器核心逻辑
```

你审核 WP-1（进入对应 worktree）

**完成第 2 个**：
```
✅ WP-2 (Resource Manager) 已完成
Worktree: .claude/worktrees/wp-2-resource
请审核资源管理器
```

你审核 WP-2

**完成第 3 个**：
```
✅ WP-3 (Memory System) 已完成
Worktree: .claude/worktrees/wp-3-memory
请审核 Memory 子系统
```

你审核 WP-3

#### Step 3: 全部通过后集成测试

**我合并所有 WP 到 main**：
```bash
# 我会执行（你不用手动）
git merge wp-1-scheduler
git merge wp-2-resource
git merge wp-3-memory
```

**你做集成测试**：
```bash
cd /Users/yunpeng/pi-investment/agent-os

# 重新编译
go build -o agent-os ./cmd/agent-os

# 测试所有命令
./agent-os scheduler list
./agent-os resource quota --agent fin-agent
./agent-os memory search --query test

# 运行集成测试（如果有）
go test ./... -v
```

**集成测试清单**：
- [ ] 3 个模块都能独立运行
- [ ] Scheduler 能调用 Resource Manager（配额检查）
- [ ] Memory 能使用命名空间隔离
- [ ] 数据库操作正常
- [ ] 没有编译错误或警告

---

## 3. 每个 WP 的详细执行步骤

### WP-0: 项目脚手架（Day 1）

#### 你启动任务
```
"启动 WP-0，建立 Go 项目脚手架"
```

#### 我执行（你等待）
1. 创建 worktree
2. 初始化 go.mod
3. 创建项目结构
4. 安装依赖
5. 实现基础 CLI 框架
6. 编写构建脚本

**预计时间**: 4-6 小时

#### 我完成后通知你
```
✅ WP-0 已完成
Worktree: .claude/worktrees/wp-0-scaffold

产出物：
  - agent-os 可编译的二进制
  - 项目结构：cmd/, internal/, pkg/, configs/
  - CLI 框架：version, help, daemon 命令
  - 数据库 Schema: scripts/schema.sql
  - 构建脚本: scripts/build.sh

测试命令：
  cd .claude/worktrees/wp-0-scaffold
  go build -o agent-os ./cmd/agent-os
  ./agent-os version
  ./agent-os help
```

#### 你审核（详细步骤）

**Step 1: 进入 worktree**
```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/wp-0-scaffold
```

**Step 2: 查看项目结构**
```bash
tree -L 3 -I 'node_modules|__pycache__|*.pyc'

# 预期输出类似：
# agent-os/
# ├── cmd/
# │   └── agent-os/
# │       └── main.go
# ├── internal/
# │   ├── cli/
# │   │   ├── root.go
# │   │   ├── daemon.go
# │   │   └── version.go
# │   ├── kernel/
# │   ├── api/
# │   └── storage/
# ├── pkg/
# │   └── types/
# ├── configs/
# │   └── agent-os.yaml
# ├── scripts/
# │   ├── build.sh
# │   └── schema.sql
# ├── go.mod
# ├── go.sum
# └── README.md
```

**Step 3: 审核核心文件**

查看入口：
```bash
cat cmd/agent-os/main.go
```

**检查点**：
- [ ] package main
- [ ] 有 main() 函数
- [ ] 调用 CLI 框架（Cobra）
- [ ] 有基本的错误处理

查看 CLI 根命令：
```bash
cat internal/cli/root.go
```

**检查点**：
- [ ] 使用 Cobra 框架
- [ ] 定义了 rootCmd
- [ ] 有子命令注册（version, daemon）
- [ ] 有全局 flags（如 --config）

查看配置文件：
```bash
cat configs/agent-os.yaml
```

**检查点**：
- [ ] YAML 格式正确
- [ ] 有基本配置项（server, database, logging）
- [ ] 有注释说明

**Step 4: 编译测试**
```bash
# 下载依赖
go mod download

# 编译
go build -o agent-os ./cmd/agent-os

# 检查二进制
ls -lh agent-os
file agent-os

# 运行基础命令
./agent-os version
./agent-os help
./agent-os daemon --help
```

**预期输出**：
```bash
$ ./agent-os version
agent-os version 0.1.0
build time: 2026-08-13T10:30:00Z
go version: go1.21.5

$ ./agent-os help
Agent OS - AI Agent 的操作系统底座

Usage:
  agent-os [command]

Available Commands:
  daemon      Daemon 管理（start, stop, status）
  help        帮助信息
  version     显示版本信息

Flags:
  -h, --help            帮助
      --config string   配置文件路径 (default "configs/agent-os.yaml")
```

**Step 5: 运行测试**
```bash
go test ./... -v
```

**如果有测试失败**：记录失败信息，告诉我修复

**Step 6: 审核代码质量**

用 VS Code 打开：
```bash
code .
```

浏览代码，检查：
- [ ] **项目结构**：是否符合 Clean Architecture（cmd → internal → pkg）
- [ ] **命名规范**：是否符合 Go 风格（驼峰命名、包名小写）
- [ ] **错误处理**：是否有 `if err != nil` 检查
- [ ] **日志输出**：是否使用 Zap 或标准日志
- [ ] **注释**：关键函数是否有注释

**Step 7: 给出反馈**

在 Claude 对话中回复：

**通过**：
```
"WP-0 审核通过 ✅
- 项目结构清晰
- 编译成功
- 命令正常运行
- 代码质量良好
可以合并到 main，开始 Stage 1"
```

**需要修改**：
```
"WP-0 需要修改 🔄
1. configs/agent-os.yaml 缺少 database 配置
2. internal/cli/root.go 第 45 行没有错误处理
3. 建议添加 .gitignore 文件

请修复后重新提交"
```

---

### WP-1/2/3: Stage 1 并行开发（Day 2-4）

#### 你启动任务（Day 2 早上）
```
"启动 Stage 1，3 个 WP 并行：
- WP-1: Scheduler Core
- WP-2: Resource Manager
- WP-3: Memory System

开始执行"
```

#### 我执行（Day 2-4）

**我会分批完成**：
- Day 2: 3 个 WP 的数据结构 + Repository
- Day 3: 3 个 WP 的核心逻辑
- Day 4: 3 个 WP 的 CLI + 测试

**每完成一个里程碑，我通知你**：
```
进度更新 (Day 2 晚上):
  ✅ WP-1: TaskRepository 完成
  ✅ WP-2: Quota Manager 完成
  ✅ WP-3: Memory Store 完成

你可以审核数据结构设计，或等 Day 4 一起审核
```

#### 你的审核选择

**选项 A: 每天审核（推荐）**
- Day 2 晚：审核数据结构
- Day 3 晚：审核核心逻辑
- Day 4 晚：审核 CLI + 完整测试

**选项 B: Day 4 统一审核**
- 等 3 个 WP 全部完成
- Day 4 晚一次性审核

#### Day 4 晚上：完整审核步骤

**我完成后通知你**：
```
✅ Stage 1 (WP-1/2/3) 全部完成

Worktrees:
  - WP-1: .claude/worktrees/wp-1-scheduler
  - WP-2: .claude/worktrees/wp-2-resource
  - WP-3: .claude/worktrees/wp-3-memory

请分别审核 3 个模块，然后做集成测试
```

**Step 1: 审核 WP-1 (Scheduler)**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/wp-1-scheduler

# 编译
go build -o agent-os ./cmd/agent-os

# 测试 Scheduler 命令
./agent-os scheduler register \
  --name test_task \
  --cron "*/5 * * * *" \
  --owner fin-agent \
  --agent-kind fin \
  --prompt "测试任务"

# 查看任务列表
./agent-os scheduler list

# 手动触发
./agent-os scheduler trigger --task-id 1

# 查看执行历史
./agent-os scheduler executions --task-id 1

# 运行单元测试
go test ./internal/kernel/scheduler/... -v
```

**检查点**：
- [ ] 任务能注册成功
- [ ] 任务列表能显示
- [ ] 手动触发能执行
- [ ] 执行历史有记录
- [ ] DAG 依赖逻辑存在（代码审核）
- [ ] 单元测试通过

**Step 2: 审核 WP-2 (Resource Manager)**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/wp-2-resource

go build -o agent-os ./cmd/agent-os

# 测试配额查询
./agent-os resource quota --agent fin-agent

# 运行测试
go test ./internal/kernel/resource/... -v
```

**检查点**：
- [ ] 配额信息能显示
- [ ] 配额配置能加载（configs/agents.yaml）
- [ ] 命名空间逻辑存在（代码审核）
- [ ] 单元测试通过

**Step 3: 审核 WP-3 (Memory)**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/wp-3-memory

go build -o agent-os ./cmd/agent-os

# 测试 Memory 写入
./agent-os memory write \
  --content "测试记忆内容，用于验证存储和检索功能" \
  --category "test" \
  --agent-id "fin-agent"

# 测试 Memory 搜索
./agent-os memory search \
  --query "测试" \
  --agent-id "fin-agent" \
  --top-k 10

# 运行测试
go test ./internal/kernel/memory/... -v
```

**检查点**：
- [ ] 记忆能写入成功
- [ ] 能搜索到刚写入的记忆
- [ ] 数据表已迁移（检查 PG）
- [ ] 单元测试通过

**Step 4: 集成测试（重要！）**

```bash
# 回到主目录
cd /Users/yunpeng/pi-investment/agent-os

# 我会合并 3 个 worktree 到 main
# 你重新编译
go build -o agent-os ./cmd/agent-os

# 测试 Scheduler 调用 Resource Manager
# (注册任务后检查配额)
./agent-os scheduler register --name quota_test --cron "* * * * *" --owner fin-agent
# 查看配额是否正常
./agent-os resource quota --agent fin-agent

# 测试 Memory 命名空间隔离
./agent-os memory write --content "fin记忆" --category test --agent-id fin-agent
./agent-os memory write --content "memory记忆" --category test --agent-id memory-agent
# 搜索时应该只看到自己的记忆
./agent-os memory search --query "记忆" --agent-id fin-agent

# 运行全部测试
go test ./... -v
```

**集成测试检查点**：
- [ ] 3 个模块编译到一起无冲突
- [ ] Scheduler 能检查配额（代码中有调用）
- [ ] Memory 使用命名空间隔离
- [ ] 全部单元测试通过
- [ ] 没有编译警告

**Step 5: 给出反馈**

```
"Stage 1 审核结果：

WP-1 (Scheduler): ✅ 通过
WP-2 (Resource): ✅ 通过  
WP-3 (Memory): 🔄 需要修改
  - memory search 搜索结果为空（BM25 索引问题？）
  - 建议检查 PostgreSQL tsvector 配置

集成测试: ⏸️ 等 WP-3 修复后再测

请修复 WP-3 的搜索问题"
```

---

### WP-4: agent-ts 切换（Day 5-6）

#### 你启动任务
```
"WP-1/2/3 已合并，启动 WP-4：agent-ts 切换到 Agent OS"
```

#### 我执行
1. 在 agent-ts 中实现 CLI 执行器
2. 改写工具定义（memory_write, memory_search 等）
3. 实现任务注册逻辑
4. 实现 Webhook 接口
5. 删除本地 Cron 代码

**预计时间**: 2 天

#### 我完成后通知你
```
✅ WP-4 已完成
Worktree: .claude/worktrees/wp-4-agent-integration

改动文件：
  agent-ts/src/utils/agent-os-cli.ts (新建)
  agent-ts/src/infrastructure/tools/memory/memory-write-tool.ts (改写)
  agent-ts/src/services/scheduler/register-to-os.ts (新建)
  agent-ts/src/api/agent-trigger.ts (新建)
  agent-ts/src/services/scheduler/init-agent-tasks.ts (删除)

请测试完整流程：
  1. agent-ts 启动 → 任务注册到 OS
  2. OS 触发任务 → agent 执行
  3. agent 调用工具 → OS 处理
```

#### 你审核（端到端测试）

**Step 1: 审核 agent-ts 代码**
```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/wp-4-agent-integration/agent-ts

# 查看关键文件
cat src/utils/agent-os-cli.ts
cat src/infrastructure/tools/memory/memory-write-tool.ts
cat src/services/scheduler/register-to-os.ts
```

**检查点**：
- [ ] agent-os-cli.ts 封装了 execSync
- [ ] 工具定义改为调用 CLI
- [ ] 启动时注册任务到 OS
- [ ] Webhook 接口实现

**Step 2: 编译测试 agent-ts**
```bash
cd agent-ts
npm run build
npm run test
```

**Step 3: 启动 Agent OS daemon**
```bash
# 打开新终端窗口
cd /Users/yunpeng/pi-investment/agent-os
./agent-os daemon start

# 检查是否启动
ps aux | grep agent-os
```

**Step 4: 启动 agent-ts**
```bash
cd /Users/yunpeng/pi-investment/agent-ts
npm run start:headless
```

**观察启动日志，应该看到**：
```
[INFO] Registering tasks to Agent OS...
[INFO] Registered task: daily_recall_audit
[INFO] Registered task: morning_analysis
[INFO] Registered task: weekly_evolution
[INFO] Agent startup complete
```

**Step 5: 验证任务注册**
```bash
# 打开新终端
cd /Users/yunpeng/pi-investment/agent-os
./agent-os scheduler list

# 应该看到 agent-ts 的 3 个任务
```

**Step 6: 手动触发任务测试**
```bash
# 触发 morning_analysis
./agent-os scheduler trigger --name morning_analysis

# 观察 agent-ts 日志，应该看到：
# [INFO] Received trigger request: morning_analysis
# [INFO] Creating fin-agent session...
# [INFO] Agent running...
```

**Step 7: 观察 agent 调用工具**

在 agent 执行过程中，观察日志：
```
[INFO] Tool call: memory_write
[DEBUG] Executing: agent-os memory write --content "..." --category decision
[INFO] Tool result: {"memory_id": 123, ...}
```

**Step 8: 检查执行历史**
```bash
./agent-os scheduler executions --name morning_analysis --limit 1
```

**应该看到刚才的执行记录**

**Step 9: 给出反馈**

```
"WP-4 审核结果：✅ 通过

验证成功：
- agent-ts 启动时成功注册 3 个任务
- OS 触发任务，agent 正常执行
- agent 调用工具，OS 正确处理
- 执行历史记录完整

可以合并，进入 Stage 3"
```

---

## 4. 审核操作指南

### 4.1 快速审核清单（5 分钟）

每个 WP 完成后，快速检查：

```bash
# 1. 编译检查
go build -o agent-os ./cmd/agent-os
echo $?  # 应该输出 0（成功）

# 2. 命令检查
./agent-os help | grep -E "scheduler|memory|resource|decision"

# 3. 测试检查
go test ./... | grep -E "PASS|FAIL"

# 4. 代码行数检查（评估工作量）
find internal -name "*.go" | xargs wc -l | tail -1
```

**快速判断**：
- 编译成功 + 命令存在 + 测试通过 = 基本可以通过
- 有编译错误 or 测试失败 = 需要修复

### 4.2 深度审核清单（30 分钟）

Stage 结束时，深度检查：

#### 4.2.1 代码质量审核

```bash
# 打开 VS Code
code .

# 安装 Go 插件（第一次需要）
# VS Code 会提示安装 gopls、golint 等工具，点击安装
```

**审核维度**：

| 维度 | 检查点 | 如何检查 |
|---|---|---|
| **结构** | 是否符合 Clean Architecture | 看目录层次：cmd → internal → pkg |
| **命名** | 是否符合 Go 规范 | 看变量名是否驼峰、包名是否小写 |
| **错误处理** | 是否完整 | 搜索 `err :=`，看后面是否有 `if err != nil` |
| **测试覆盖** | 是否充分 | 运行 `go test -cover ./...` |
| **注释** | 关键函数是否有注释 | 看导出函数（大写开头）是否有注释 |
| **性能** | 是否有明显瓶颈 | 看是否有 N+1 查询、无限循环等 |

#### 4.2.2 功能完整性审核

**对照任务清单逐项检查**：

```bash
# 以 WP-1 (Scheduler) 为例

# ✅ 任务注册
./agent-os scheduler register --name test --cron "* * * * *" --owner fin-agent

# ✅ 任务列表
./agent-os scheduler list

# ✅ 手动触发
./agent-os scheduler trigger --name test

# ✅ 执行历史
./agent-os scheduler executions --name test

# ✅ DAG 依赖（代码审核）
grep -r "CheckDependencies" internal/kernel/scheduler/

# ✅ 单元测试
go test ./internal/kernel/scheduler/... -v
```

#### 4.2.3 集成测试审核

**测试模块间交互**：

```bash
# Scheduler → Resource Manager（配额检查）
# 1. 注册任务
./agent-os scheduler register --name quota_test --owner fin-agent

# 2. 查看代码中是否调用了 CheckQuota
grep -A5 "TriggerTask" internal/kernel/scheduler/scheduler.go | grep -i quota

# 3. 手动验证：修改配额为 0，触发任务应该失败
# 编辑 configs/agents.yaml，设置 fin-agent.token_per_day: 0
# 重启 daemon，触发任务，应该报错 "quota exceeded"
```

### 4.3 审核反馈模板

#### 通过 ✅
```
"WP-X 审核通过 ✅

验证项：
- [x] 编译成功
- [x] 命令正常
- [x] 测试通过
- [x] 代码质量良好
- [x] 功能完整

可以合并到 main"
```

#### 需要修改 🔄
```
"WP-X 需要修改 🔄

问题清单：
1. [严重] internal/kernel/scheduler/executor.go 第 78 行空指针风险
   - 现状：直接访问 task.DependsOn[0]
   - 建议：先检查 len(task.DependsOn) > 0
   
2. [中等] 缺少单元测试
   - 现状：DAG.go 没有测试
   - 建议：添加测试，覆盖循环依赖检测

3. [轻微] 日志格式不统一
   - 现状：有的用 fmt.Println，有的用 zap
   - 建议：统一使用 zap

请优先修复严重问题，其他问题可以后续改进"
```

#### 重做 ❌
```
"WP-X 需要重做 ❌

核心问题：
- 架构不符合要求
  - 当前：Scheduler 直接操作 PostgreSQL
  - 期望：Scheduler → Repository → PostgreSQL（分层）
  
建议方案：
1. 参考 Clean Architecture 设计模式
2. 创建 TaskRepository 接口层
3. Scheduler 只依赖接口，不依赖实现

请重新设计后再实现"
```

---

## 5. 问题处理预案

### 5.1 编译失败

**现象**：
```bash
$ go build -o agent-os ./cmd/agent-os
# command-line-arguments
./main.go:10:2: undefined: cobra
```

**原因**：依赖没安装

**解决**：
```bash
go mod download
go mod tidy
go build -o agent-os ./cmd/agent-os
```

**如果还失败**，告诉我：
```
"编译失败，错误信息：
<粘贴完整错误信息>

请修复"
```

---

### 5.2 测试失败

**现象**：
```bash
$ go test ./...
--- FAIL: TestScheduler (0.01s)
    scheduler_test.go:25: expected task count 1, got 0
FAIL
```

**你需要做**：
1. 记录失败的测试名称
2. 查看测试代码（找到对应文件）
3. 告诉我失败原因

```
"测试失败：TestScheduler

错误：expected task count 1, got 0
测试文件：internal/kernel/scheduler/scheduler_test.go:25

可能原因：数据库没有初始化？

请修复"
```

---

### 5.3 功能不工作

**现象**：
```bash
$ ./agent-os scheduler list
Error: database connection failed
```

**排查步骤**：

```bash
# 1. 检查配置文件
cat configs/agent-os.yaml | grep -A5 database

# 2. 检查数据库连接
psql -h 127.0.0.1 -U mac -d quant_investment -c "SELECT 1"

# 3. 检查表是否存在
psql -h 127.0.0.1 -U mac -d quant_investment -c "\dt scheduler_*"

# 4. 查看日志
./agent-os scheduler list --verbose
```

**告诉我问题**：
```
"scheduler list 命令失败

错误信息：database connection failed

排查结果：
- 配置文件正确
- 数据库能连接
- scheduler_tasks 表不存在 ← 问题在这里

建议：需要先运行 SQL 建表脚本

请补充建表脚本或修复初始化逻辑"
```

---

### 5.4 性能问题

**现象**：命令执行很慢（> 1 秒）

**测试性能**：
```bash
# 使用 time 命令测试
time ./agent-os scheduler list

# 预期：< 0.1s
# 实际：> 1s  ← 有问题
```

**告诉我**：
```
"性能问题：scheduler list 执行耗时 1.2s（预期 < 0.1s）

可能原因：
- 数据库查询慢？
- 没有索引？

请优化性能"
```

---

### 5.5 集成冲突

**现象**：合并多个 WP 后编译失败

```bash
$ git merge wp-2-resource
Auto-merging internal/kernel/types.go
CONFLICT (content): Merge conflict in internal/kernel/types.go
```

**解决步骤**：

```bash
# 1. 查看冲突
git status

# 2. 打开冲突文件
code internal/kernel/types.go

# 3. 手动解决冲突（保留两边的定义）

# 4. 标记已解决
git add internal/kernel/types.go
git commit -m "Merge wp-2-resource: resolve types.go conflict"
```

**如果不确定怎么合并，告诉我**：
```
"合并 WP-2 时遇到冲突

冲突文件：internal/kernel/types.go
冲突内容：
<<<<< HEAD
type Task struct { ... }  // WP-1 的定义
=====
type TaskDefinition struct { ... }  // WP-2 的定义
>>>>> wp-2-resource

应该保留哪个？还是都保留但改名？"
```

---

## 6. 常用命令速查表

### 6.1 Go 命令

```bash
# 编译
go build -o agent-os ./cmd/agent-os

# 运行测试
go test ./...                    # 所有测试
go test ./internal/kernel/...    # 指定目录
go test -v ./...                 # 详细输出
go test -cover ./...             # 覆盖率

# 下载依赖
go mod download

# 清理依赖
go mod tidy

# 查看依赖
go list -m all

# 格式化代码
go fmt ./...

# 静态检查
go vet ./...
```

### 6.2 Agent OS 命令

```bash
# Scheduler
agent-os scheduler register --name <name> --cron <cron> --owner <agent>
agent-os scheduler list [--owner <agent>]
agent-os scheduler trigger --name <name>
agent-os scheduler executions --name <name> [--limit 10]

# Memory
agent-os memory write --content <content> --category <category> --agent-id <agent>
agent-os memory search --query <query> --agent-id <agent> [--top-k 10]
agent-os memory query --category <category> --agent-id <agent>

# Resource
agent-os resource quota --agent <agent-id>

# Decision
agent-os decision record --action <action> --targets <json> --agent-id <agent>
agent-os decision query --action <action> --agent-id <agent>

# Data
agent-os data quote --symbol <symbol>
agent-os data kline --symbol <symbol> --period <period>

# Notification
agent-os notify send --user <user> --title <title> --message <message>

# Daemon
agent-os daemon start
agent-os daemon stop
agent-os daemon status

# 其他
agent-os version
agent-os help
```

### 6.3 审核命令

```bash
# 快速检查
go build -o agent-os ./cmd/agent-os && ./agent-os help && go test ./...

# 查看项目结构
tree -L 3 -I 'node_modules|__pycache__|*.pyc|.git'

# 查看代码行数
find internal -name "*.go" | xargs wc -l | tail -1

# 查看测试覆盖率
go test -coverprofile=coverage.out ./...
go tool cover -func=coverage.out | grep total

# 查看依赖
go mod graph | grep agent-os

# 检查代码风格
gofmt -l .
```

### 6.4 数据库命令

```bash
# 连接数据库
psql -h 127.0.0.1 -U mac -d quant_investment

# 查看表
\dt scheduler_*

# 查看表结构
\d scheduler_tasks

# 查询数据
SELECT * FROM scheduler_tasks LIMIT 10;

# 删除测试数据
DELETE FROM scheduler_tasks WHERE name LIKE 'test%';
```

### 6.5 Git 命令

```bash
# 查看 worktree
git worktree list

# 进入 worktree
cd .claude/worktrees/wp-1-scheduler

# 查看状态
git status

# 合并 worktree
git merge wp-1-scheduler

# 删除 worktree
git worktree remove .claude/worktrees/wp-1-scheduler
```

---

## 7. 沟通模板

### 7.1 启动新任务

```
"启动 WP-X: <任务名称>

开始执行"
```

或者更详细：
```
"今天是 Day X，按照计划启动：
- WP-X: <任务名称>
- 预计时间：X 小时
- 主要产出：<产出物>

请开始"
```

### 7.2 询问进度

```
"WP-X 进度如何？"
```

我会回复：
```
"WP-X 进度：60%

已完成：
- 数据结构定义
- Repository 实现

进行中：
- 核心逻辑（预计 1 小时完成）

待完成：
- CLI 命令
- 单元测试"
```

### 7.3 报告问题

```
"遇到问题：

问题描述：<具体问题>
错误信息：<错误日志>
已尝试：<你的排查步骤>

请协助解决"
```

### 7.4 给出反馈

```
"WP-X 审核结果：<✅通过 / 🔄修改 / ❌重做>

<具体反馈内容>

<下一步行动>"
```

---

## 8. 你现在需要做的

### 第一步：确认准备好了

回复我：
```
"准备好了，可以开始"
```

或者提问：
```
"还有一个问题：<你的问题>"
```

### 第二步：我启动 WP-0

我会：
1. 创建 worktree
2. 开始写代码
3. 定期更新进度
4. 完成后通知你审核

### 第三步：你审核 WP-0

按照 **3.1 WP-0 审核步骤**，逐步操作

### 第四步：给出反馈

告诉我：通过 ✅ / 修改 🔄 / 重做 ❌

### 第五步：进入 Stage 1

3 个 Agent 并行开工！

---

**准备好了吗？告诉我！** 🚀

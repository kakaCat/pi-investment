# Batch 3 执行计划：Driver + Decision

**日期**: 2026-08-14  
**批次**: Batch 3  
**并行任务数**: 3 个（同时进行）⚡  
**预计工期**: 2 天

---

## 🎯 任务分配

| 任务 | 负责 Agent | 工作内容 | 验收标准 |
|---|---|---|---|
| **WP-5: Market Driver** | Agent-Market | • Python CLI (market-driver)<br>• AKShare 适配器<br>• OS Data 命令<br>• Redis 缓存 | 行情查询正常 |
| **WP-6: Feishu Driver** | Agent-Feishu | • Python CLI (feishu-driver)<br>• 飞书 Webhook API<br>• Notification Manager<br>• OS Notify 命令 | 飞书收到通知 |
| **WP-7: Decision System** | Agent-Decision | • Decision Store<br>• 数据表迁移<br>• CLI 命令 | 决策能记录、查询 |

---

## 📋 执行模型提示词

### WP-5: Market Driver (Agent-Market)

**复杂度**: M  
**执行模型**: Claude Sonnet 5  
**审查模型**: Claude Opus 5

**任务描述**:
构建 Python CLI 工具 `market-driver`，为 Agent OS 提供市场行情数据查询能力。

**技术栈**:
- Python 3.13
- Click (CLI 框架)
- AKShare (数据源)
- Redis (缓存层)
- agent-os (Go CLI 调用)

**交付物**:
1. `agent-os/drivers/market-driver/` 目录结构
2. `main.py` - CLI 入口
3. `adapters/akshare_adapter.py` - AKShare 数据适配器
4. `cache/redis_cache.py` - Redis 缓存层
5. Go 代码：`internal/commands/data.go` - OS Data 命令
6. 测试脚本：`test-wp5.sh`
7. 完工报告：`WP-5-COMPLETION.md`

**核心功能**:
- `market-driver quote --symbol 600519.SH` - 查询实时行情
- `market-driver kline --symbol 600519.SH --period daily` - 查询K线
- `market-driver market-status` - 查询市场状态
- Redis 缓存（TTL: 实时1分钟，K线1天）

**验收标准**:
```bash
# 1. CLI 可用
market-driver quote --symbol 600519.SH
# 预期输出: JSON 格式行情数据

# 2. agent-os 集成
agent-os data quote --symbol 600519.SH
# 预期输出: 格式化行情数据

# 3. 缓存生效
time agent-os data quote --symbol 600519.SH  # 第二次 < 100ms

# 4. 错误处理
agent-os data quote --symbol INVALID
# 预期输出: Error: invalid symbol
```

---

### WP-6: Feishu Driver (Agent-Feishu)

**复杂度**: M  
**执行模型**: Claude Sonnet 5  
**审查模型**: Claude Opus 5

**任务描述**:
构建 Python CLI 工具 `feishu-driver`，为 Agent OS 提供飞书通知能力。

**技术栈**:
- Python 3.13
- Click (CLI 框架)
- requests (HTTP 客户端)
- agent-os (Go CLI 调用)

**交付物**:
1. `agent-os/drivers/feishu-driver/` 目录结构
2. `main.py` - CLI 入口
3. `api/feishu_api.py` - 飞书 API 客户端
4. `manager/notification_manager.py` - 通知管理器
5. Go 代码：`internal/commands/notify.go` - OS Notify 命令
6. 测试脚本：`test-wp6.sh`
7. 完工报告：`WP-6-COMPLETION.md`

**核心功能**:
- `feishu-driver send --user yunpeng --title "标题" --message "内容"` - 发送通知
- `feishu-driver send --channel general --title "标题" --message "内容"` - 发送到频道
- 支持富文本（Markdown）
- 重试机制（3次，指数退避）

**验收标准**:
```bash
# 1. CLI 可用
feishu-driver send --user yunpeng --title "测试" --message "测试消息"
# 预期输出: Notification sent successfully

# 2. agent-os 集成
agent-os notify send --user yunpeng --title "测试" --message "测试消息"
# 预期输出: Notification sent
# 飞书收到消息

# 3. Markdown 支持
agent-os notify send --user yunpeng --title "Markdown" --message "**粗体** *斜体*"
# 飞书显示格式化文本

# 4. 错误处理
agent-os notify send --user invalid_user --title "测试" --message "测试"
# 预期输出: Error: user not found
```

---

### WP-7: Decision System (Agent-Decision)

**复杂度**: M  
**执行模型**: Claude Sonnet 5  
**审查模型**: Claude Opus 5

**任务描述**:
构建决策系统，记录和查询 agent 的投资决策历史。

**技术栈**:
- Go 1.23
- PostgreSQL (决策存储)
- Cobra (CLI 命令)

**交付物**:
1. `internal/domain/decision.go` - 决策模型
2. `internal/repository/decision_repository.go` - 数据仓库
3. `internal/service/decision_service.go` - 业务逻辑
4. `internal/commands/decision.go` - CLI 命令
5. `migrations/007_create_decisions.sql` - 数据库迁移
6. 测试：`internal/service/decision_service_test.go`
7. 测试脚本：`test-wp7.sh`
8. 完工报告：`WP-7-COMPLETION.md`

**数据模型**:
```sql
CREATE TABLE decisions (
    id UUID PRIMARY KEY,
    agent_id VARCHAR(64) NOT NULL,
    action VARCHAR(32) NOT NULL,  -- watch, buy, sell, hold
    targets TEXT[],               -- 股票代码列表
    reason TEXT,                  -- 决策理由
    confidence FLOAT,             -- 置信度 [0, 1]
    context JSONB,                -- 决策上下文
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    executed_at TIMESTAMP,        -- 执行时间
    outcome JSONB                 -- 执行结果
);

CREATE INDEX idx_decisions_agent_id ON decisions(agent_id);
CREATE INDEX idx_decisions_action ON decisions(action);
CREATE INDEX idx_decisions_created_at ON decisions(created_at);
```

**核心功能**:
- `agent-os decision record` - 记录决策
- `agent-os decision list` - 查询决策列表
- `agent-os decision get` - 查询单个决策
- `agent-os decision update` - 更新执行结果

**验收标准**:
```bash
# 1. 记录决策
agent-os decision record \
  --agent fin-agent \
  --action watch \
  --targets '["600519.SH","000858.SZ"]' \
  --reason "技术面突破" \
  --confidence 0.85
# 预期输出: Decision recorded: <UUID>

# 2. 查询决策
agent-os decision list --agent fin-agent --action watch
# 预期输出: 决策列表

# 3. 查询单个决策
agent-os decision get --id <UUID>
# 预期输出: 决策详情（JSON）

# 4. 更新执行结果
agent-os decision update --id <UUID> --outcome '{"status":"executed","profit":0.05}'
# 预期输出: Decision updated

# 5. 数据库查询
psql -d quant_investment -c "SELECT * FROM decisions LIMIT 5;"
# 预期输出: 5 条决策记录
```

---

## 🔄 通用规则块

### 代码质量要求
- 遵循 Go 最佳实践（gofmt、golangci-lint）
- Python 遵循 PEP 8
- 单元测试覆盖率 > 80%
- 所有错误必须处理
- 日志使用结构化日志（Zap）

### Worktree 隔离规则
- 每个任务独立 worktree：`git worktree add .claude/worktrees/wp-X -b feat/wp-X`
- 完成后合并到 main
- 测试通过后推送到 GitHub

### 数据库迁移规则
- 迁移文件命名：`00X_description.sql`
- 包含 UP 和 DOWN 迁移
- 测试数据库：`quant_test`
- 生产数据库：`quant_investment`

### API 契约
- Go CLI 调用 Python Driver: `exec.Command("python", "main.py", ...)`
- 返回格式: JSON
- 错误码: 0=成功，1=参数错误，2=业务错误，3=系统错误

---

## 📊 并行执行策略

### Day 1（今天）
- **上午**: 启动 3 个 agent，创建 worktree
- **下午**: 各自实现核心逻辑
- **晚上**: 提交初步成果，审核

### Day 2（明天）
- **上午**: 继续完成剩余功能
- **下午**: 编写测试、修复 bug
- **晚上**: 集成测试、合并到 main

---

## ✅ 最终验收标准

### 功能验收
- [ ] 能查询行情（market-driver）
- [ ] 飞书收到通知（feishu-driver）
- [ ] 决策能记录和查询（decision system）

### 集成验收
```bash
# 端到端场景：agent 发现机会 → 记录决策 → 发送通知 → 查询行情
agent-os decision record --agent fin-agent --action watch --targets '["600519.SH"]'
agent-os notify send --user yunpeng --title "发现机会" --message "600519.SH 突破"
agent-os data quote --symbol 600519.SH
```

### 性能验收
- CLI 调用延迟 < 200ms（含 Python 启动）
- Redis 缓存命中率 > 90%
- 飞书通知成功率 > 99%

---

## 🚀 准备启动

**现在启动 Batch 3**：
- 我会同时创建 3 个 agent
- 每个 agent 独立开发一个模块
- 预计 2 天完成

**等你确认！** 🔥

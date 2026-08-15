# Phase 1 执行计划：Agent OS 核心功能迁移

> **开始时间**: 2026-08-14  
> **目标**: 将 v2 核心功能完全迁移到 Agent OS  
> **工期**: 1-2 周  
> **优先级**: P0（最高）

---

## 📊 Phase 1 总览

### 目标

将以下 v2 模块迁移到 Agent OS：
1. ✅ Memory 子系统（代码已完成）
2. ✅ Decision 子系统（代码已完成）
3. ✅ Scheduler 子系统（代码已完成）
4. ✅ Notification 子系统（代码已完成）
5. ⏸️ agent-ts 集成切换

### 完成标准

- [ ] v2 数据完全迁移到 agent_os DB
- [ ] agent-ts 使用 Agent OS CLI 调用
- [ ] agent-ts 任务由 Agent OS 调度
- [ ] 通知通过 Agent OS 发送
- [ ] agent-ts 不再依赖 v2 HTTP API

---

## 🔧 执行任务清单

### 任务 1.1: 数据库准备（30 分钟）

**目标**: 确保 agent_os 数据库就绪

#### Step 1: 检查 agent_os 数据库

```bash
# 检查数据库是否存在
psql -h 127.0.0.1 -U mac -lqt | grep agent_os

# 如果不存在，创建
createdb -h 127.0.0.1 -U mac agent_os

# 应用 schema
cd /Users/yunpeng/pi-investment/agent-os
psql -h 127.0.0.1 -U mac -d agent_os -f schema.sql
```

**验证**:
```bash
# 应该看到 14 张表
psql -h 127.0.0.1 -U mac -d agent_os -c "\dt"
```

**预期输出**:
```
 public | decisions              | table
 public | events                 | table
 public | memories               | table
 public | memory_tags            | table
 public | namespaces             | table
 public | notification_channels  | table
 public | notification_logs      | table
 public | notification_providers | table
 public | permissions            | table
 public | resource_quotas        | table
 public | resource_usage_log     | table
 public | task_dependencies      | table
 public | task_runs              | table
 public | tasks                  | table
(14 rows)
```

---

### 任务 1.2: Memory 数据迁移（1 小时）

**目标**: 将 v2 的 agent_memory 数据迁移到 agent_os

#### Step 1: 备份 v2 数据

```bash
# 备份整个 quant_investment 数据库
pg_dump -h 127.0.0.1 -U mac -d quant_investment \
  > ~/backups/v2_full_backup_$(date +%Y%m%d_%H%M%S).sql

# 备份 agent_memory 表
pg_dump -h 127.0.0.1 -U mac -d quant_investment \
  -t agent_memory -t memory_tags \
  > ~/backups/v2_memory_$(date +%Y%m%d_%H%M%S).sql

echo "✅ 备份完成"
```

#### Step 2: 检查数据量

```bash
# v2 数据量
psql -h 127.0.0.1 -U mac -d quant_investment -c "
SELECT 
  'agent_memory' as table_name,
  count(*) as row_count,
  pg_size_pretty(pg_total_relation_size('agent_memory')) as size
FROM agent_memory;
"
```

#### Step 3: 检查 schema 差异

```bash
# v2 schema
psql -h 127.0.0.1 -U mac -d quant_investment -c "\d agent_memory"

# agent_os schema
psql -h 127.0.0.1 -U mac -d agent_os -c "\d memories"
```

**注意**: 表名不同！v2 是 `agent_memory`，Agent OS 是 `memories`

#### Step 4: 数据迁移脚本

创建迁移脚本：

```bash
cat > /tmp/migrate_memory.sql << 'EOF'
-- 连接到 agent_os 数据库
\c agent_os

-- 创建临时外部表（如果两个 DB 在同一个 PostgreSQL 实例）
-- 或者使用 pg_dump | psql 方式

-- 方案 A: 同实例迁移（推荐）
-- 需要 postgres_fdw 扩展

CREATE EXTENSION IF NOT EXISTS postgres_fdw;

CREATE SERVER IF NOT EXISTS v2_server
  FOREIGN DATA WRAPPER postgres_fdw
  OPTIONS (host '127.0.0.1', dbname 'quant_investment', port '5432');

CREATE USER MAPPING IF NOT EXISTS FOR mac
  SERVER v2_server
  OPTIONS (user 'mac', password '');

CREATE FOREIGN TABLE IF NOT EXISTS v2_agent_memory (
  id INTEGER,
  namespace_id INTEGER,
  content TEXT,
  category VARCHAR(50),
  importance INTEGER,
  embedding JSONB,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  accessed_count INTEGER,
  last_accessed_at TIMESTAMP,
  metadata JSONB
)
SERVER v2_server
OPTIONS (schema_name 'public', table_name 'agent_memory');

-- 迁移数据
INSERT INTO memories (
  namespace_id, content, category, importance, embedding,
  created_at, updated_at, accessed_count, last_accessed_at, metadata
)
SELECT 
  namespace_id, content, category, importance, embedding,
  created_at, updated_at, accessed_count, last_accessed_at, metadata
FROM v2_agent_memory
ON CONFLICT DO NOTHING;

-- 统计
SELECT 'Migrated memories:' as status, count(*) as count FROM memories;

-- 清理
DROP FOREIGN TABLE v2_agent_memory;
EOF

echo "✅ 迁移脚本已创建"
```

#### Step 5: 执行迁移

```bash
psql -h 127.0.0.1 -U mac -d agent_os -f /tmp/migrate_memory.sql
```

#### Step 6: 验证迁移

```bash
# 对比数据量
echo "=== v2 数据量 ==="
psql -h 127.0.0.1 -U mac -d quant_investment -c "SELECT count(*) FROM agent_memory;"

echo "=== agent_os 数据量 ==="
psql -h 127.0.0.1 -U mac -d agent_os -c "SELECT count(*) FROM memories;"

# 抽样检查数据
echo "=== v2 样本数据 ==="
psql -h 127.0.0.1 -U mac -d quant_investment -c "SELECT id, content, category FROM agent_memory LIMIT 3;"

echo "=== agent_os 样本数据 ==="
psql -h 127.0.0.1 -U mac -d agent_os -c "SELECT id, content, category FROM memories LIMIT 3;"
```

**验收标准**:
- [ ] 数据量一致
- [ ] 样本数据正确
- [ ] 无迁移错误

---

### 任务 1.3: Decision 数据迁移（30 分钟）

**目标**: 迁移 agent_decisions 和 decision_tracking 表

#### Step 1: 备份数据

```bash
pg_dump -h 127.0.0.1 -U mac -d quant_investment \
  -t agent_decisions -t decision_tracking \
  > ~/backups/v2_decisions_$(date +%Y%m%d_%H%M%S).sql
```

#### Step 2: 迁移脚本

```bash
cat > /tmp/migrate_decisions.sql << 'EOF'
\c agent_os

-- agent_decisions 表已存在，直接迁移数据
CREATE FOREIGN TABLE IF NOT EXISTS v2_agent_decisions (
  id INTEGER,
  agent_id VARCHAR(50),
  action VARCHAR(50),
  targets TEXT[],
  reason TEXT,
  confidence FLOAT,
  context JSONB,
  created_at TIMESTAMP,
  executed_at TIMESTAMP,
  status VARCHAR(20)
)
SERVER v2_server
OPTIONS (schema_name 'public', table_name 'agent_decisions');

INSERT INTO decisions (
  agent_id, action, targets, reason, confidence, context,
  created_at, executed_at, status
)
SELECT 
  agent_id, action, targets, reason, confidence, context,
  created_at, executed_at, status
FROM v2_agent_decisions
ON CONFLICT DO NOTHING;

SELECT 'Migrated decisions:' as status, count(*) as count FROM decisions;

DROP FOREIGN TABLE v2_agent_decisions;
EOF

psql -h 127.0.0.1 -U mac -d agent_os -f /tmp/migrate_decisions.sql
```

#### Step 3: 验证

```bash
echo "=== v2 decisions 数量 ==="
psql -h 127.0.0.1 -U mac -d quant_investment -c "SELECT count(*) FROM agent_decisions;"

echo "=== agent_os decisions 数量 ==="
psql -h 127.0.0.1 -U mac -d agent_os -c "SELECT count(*) FROM decisions;"
```

---

### 任务 1.4: Scheduler 任务迁移（1 小时）

**目标**: 将 v2 的任务定义迁移到 Agent OS

#### Step 1: 导出 v2 任务配置

```bash
cd /Users/yunpeng/pi-investment/quantsys-v2

# 查找所有 Cron 任务定义
grep -r "cron\|schedule" application/services/ --include="*.py" | grep -v ".pyc"
```

#### Step 2: 注册任务到 Agent OS

创建任务注册脚本：

```bash
cat > /tmp/register_tasks.sh << 'EOF'
#!/bin/bash

cd /Users/yunpeng/pi-investment/agent-os

# 任务 1: daily_recall_audit
./agent-os scheduler register \
  --name "daily_recall_audit" \
  --cron "30 8 * * *" \
  --owner "memory-agent" \
  --command "agent-ts" \
  --args '{"agent_kind": "memory", "prompt": "执行每日召回审计"}' \
  --description "每日早上 8:30 执行召回审计"

# 任务 2: morning_analysis
./agent-os scheduler register \
  --name "morning_analysis" \
  --cron "0 9 * * 1-5" \
  --owner "fin-agent" \
  --command "agent-ts" \
  --args '{"agent_kind": "fin", "prompt": "执行早盘分析"}' \
  --description "工作日早上 9:00 执行早盘分析"

# 任务 3: evening_summary
./agent-os scheduler register \
  --name "evening_summary" \
  --cron "30 15 * * 1-5" \
  --owner "fin-agent" \
  --command "agent-ts" \
  --args '{"agent_kind": "fin", "prompt": "执行收盘总结"}' \
  --description "工作日下午 3:30 执行收盘总结"

# 任务 4: weekly_evolution
./agent-os scheduler register \
  --name "weekly_evolution" \
  --cron "0 18 * * 5" \
  --owner "memory-agent" \
  --command "agent-ts" \
  --args '{"agent_kind": "memory", "prompt": "执行周度进化分析"}' \
  --description "每周五下午 6:00 执行进化分析"

echo "✅ 所有任务已注册"
EOF

chmod +x /tmp/register_tasks.sh
/tmp/register_tasks.sh
```

#### Step 3: 验证任务注册

```bash
./agent-os scheduler list
```

**预期输出**:
```
ID  NAME                CRON          OWNER          STATUS
1   daily_recall_audit  30 8 * * *    memory-agent   enabled
2   morning_analysis    0 9 * * 1-5   fin-agent      enabled
3   evening_summary     30 15 * * 1-5 fin-agent      enabled
4   weekly_evolution    0 18 * * 5    memory-agent   enabled
```

---

### 任务 1.5: agent-ts CLI 集成（2-3 小时）

**目标**: agent-ts 使用 Agent OS CLI 而不是 v2 HTTP API

#### Step 1: 创建 CLI 执行器

```bash
cd /Users/yunpeng/pi-investment/agent-ts

# 创建 agent-os-cli.ts
cat > src/utils/agent-os-cli.ts << 'EOF'
import { execSync } from 'child_process';

export interface AgentOSResult {
  success: boolean;
  data?: any;
  error?: string;
}

/**
 * Execute agent-os CLI command
 * @param args CLI arguments
 * @returns Parsed JSON result
 */
export async function execAgentOS(args: string[]): Promise<AgentOSResult> {
  try {
    const agentOSPath = process.env.AGENT_OS_PATH || '/Users/yunpeng/pi-investment/agent-os/agent-os';
    const cmd = `${agentOSPath} ${args.join(' ')}`;
    
    console.log(`[agent-os-cli] Executing: ${cmd}`);
    
    const stdout = execSync(cmd, {
      encoding: 'utf-8',
      stdio: ['pipe', 'pipe', 'pipe'],
      timeout: 30000, // 30s timeout
    });
    
    // Try to parse JSON output
    try {
      const data = JSON.parse(stdout.trim());
      return { success: true, data };
    } catch {
      // Not JSON, return as string
      return { success: true, data: stdout.trim() };
    }
  } catch (error: any) {
    console.error(`[agent-os-cli] Error:`, error.message);
    return {
      success: false,
      error: error.message,
    };
  }
}

/**
 * Check if agent-os is available
 */
export async function checkAgentOS(): Promise<boolean> {
  try {
    const result = await execAgentOS(['version']);
    return result.success;
  } catch {
    return false;
  }
}
EOF

echo "✅ CLI 执行器已创建"
```

#### Step 2: 改写 memory_write 工具

```typescript
// src/infrastructure/tools/memory/memory-write-tool.ts

import { defineTool } from '@/core/tool-system';
import { execAgentOS } from '@/utils/agent-os-cli';

export const memoryWriteTool = defineTool({
  name: 'memory_write',
  description: '写入长期记忆',
  parameters: {
    type: 'object',
    properties: {
      content: {
        type: 'string',
        description: '记忆内容',
      },
      category: {
        type: 'string',
        description: '记忆分类',
      },
      importance: {
        type: 'number',
        description: '重要性（1-10）',
        default: 5,
      },
    },
    required: ['content', 'category'],
  },
  execute: async (params, context) => {
    const { content, category, importance = 5 } = params;
    const agentId = context.agentKind || 'fin-agent';

    const result = await execAgentOS([
      'memory', 'write',
      '--content', content,
      '--category', category,
      '--importance', importance.toString(),
      '--agent-id', agentId,
    ]);

    if (!result.success) {
      throw new Error(`Memory write failed: ${result.error}`);
    }

    return result.data;
  },
});
```

#### Step 3: 改写其他工具（类似）

- `memory_search` → `agent-os memory search`
- `decision_record` → `agent-os decision record`
- `notification_send` → `agent-os notify send`

#### Step 4: 更新任务触发逻辑

```typescript
// src/services/scheduler/agent-trigger.ts

import { execAgentOS } from '@/utils/agent-os-cli';

/**
 * Handle task trigger from Agent OS
 */
export async function handleTaskTrigger(taskId: string, prompt: string, agentKind: string) {
  console.log(`[scheduler] Triggered by Agent OS: task=${taskId}, agent=${agentKind}`);
  
  // Create agent session
  const session = await createAgentSession(agentKind, prompt);
  
  // Run agent
  const result = await session.run();
  
  // Report back to Agent OS
  await execAgentOS([
    'scheduler', 'complete',
    '--task-id', taskId,
    '--status', result.success ? 'success' : 'failed',
    '--output', JSON.stringify(result.data),
  ]);
  
  return result;
}
```

#### Step 5: 创建 HTTP Webhook 接口

```typescript
// src/api/webhooks/agent-os-webhook.ts

import express from 'express';
import { handleTaskTrigger } from '@/services/scheduler/agent-trigger';

export const agentOSWebhookRouter = express.Router();

/**
 * POST /api/webhooks/agent-os/trigger
 * Agent OS 调用此接口触发任务
 */
agentOSWebhookRouter.post('/trigger', async (req, res) => {
  const { task_id, execution_id, agent_kind, prompt } = req.body;
  
  try {
    const result = await handleTaskTrigger(task_id, prompt, agent_kind);
    
    res.json({
      success: true,
      execution_id,
      result,
    });
  } catch (error: any) {
    res.status(500).json({
      success: false,
      error: error.message,
    });
  }
});
```

#### Step 6: 测试集成

```bash
# 启动 agent-ts
cd agent-ts
npm run start:headless

# 在另一个终端，手动触发任务
cd agent-os
./agent-os scheduler trigger --name morning_analysis

# 观察 agent-ts 日志，应该看到任务执行
```

---

### 任务 1.6: 删除 v2 依赖（30 分钟）

**目标**: agent-ts 不再依赖 v2

#### Step 1: 更新配置

```yaml
# agent-ts/config.yaml

# Before
database:
  host: 127.0.0.1
  port: 5432
  database: quant_investment  # v2 DB

agent_os:
  enabled: false

# After
database:
  host: 127.0.0.1
  port: 5432
  database: agent_os  # Agent OS DB

agent_os:
  enabled: true
  binary_path: /Users/yunpeng/pi-investment/agent-os/agent-os
  webhook_port: 3000
```

#### Step 2: 删除 v2 HTTP Client

```bash
# 删除 v2 相关代码
rm -f src/infrastructure/http/v2-client.ts
rm -f src/infrastructure/http/v2-api.ts

# 删除 v2 相关配置
sed -i '' '/v2_api_url/d' config.yaml
```

#### Step 3: 更新导入

```bash
# 全局替换 v2 import
find src/ -name "*.ts" -exec sed -i '' 's/@\/infrastructure\/http\/v2-client/@\/utils\/agent-os-cli/g' {} \;
```

---

## ✅ Phase 1 验收清单

### 数据迁移验收

- [ ] agent_memory 数据完全迁移到 memories 表
- [ ] agent_decisions 数据完全迁移到 decisions 表
- [ ] 数据量一致（v2 vs agent_os）
- [ ] 无数据丢失
- [ ] 无外键错误

### agent-ts 集成验收

- [ ] agent-os-cli.ts 实现完成
- [ ] memory_write 工具切换到 CLI
- [ ] memory_search 工具切换到 CLI
- [ ] decision_record 工具切换到 CLI
- [ ] notification_send 工具切换到 CLI
- [ ] agent-ts 能通过 Webhook 接收 Agent OS 触发

### 端到端验收

- [ ] 启动 Agent OS daemon
- [ ] 启动 agent-ts
- [ ] Agent OS 能触发 agent-ts 任务
- [ ] agent-ts 能调用 Agent OS 写入记忆
- [ ] agent-ts 能调用 Agent OS 搜索记忆
- [ ] agent-ts 能调用 Agent OS 记录决策
- [ ] agent-ts 能调用 Agent OS 发送通知
- [ ] agent-ts 不再调用 v2 API

### v2 清理验收

- [ ] agent-ts 不再依赖 quant_investment DB
- [ ] agent-ts 不再有 v2 HTTP Client 代码
- [ ] agent-ts 配置中移除 v2 相关配置

---

## 📊 执行时间表

| 任务 | 工期 | 依赖 |
|---|---|---|
| 1.1 数据库准备 | 30 分钟 | 无 |
| 1.2 Memory 迁移 | 1 小时 | 1.1 |
| 1.3 Decision 迁移 | 30 分钟 | 1.1 |
| 1.4 Scheduler 迁移 | 1 小时 | 1.1 |
| 1.5 agent-ts 集成 | 2-3 小时 | 1.2, 1.3, 1.4 |
| 1.6 v2 清理 | 30 分钟 | 1.5 |

**总计**: 6-7 小时（1 个工作日）

---

## 🚀 立即开始？

**Phase 1 执行计划已准备完成！**

**你需要确认**:

1. **"立即执行任务 1.1"** → 开始数据库准备
2. **"一次性执行全部"** → 我按顺序执行所有任务
3. **"修改计划"** → 告诉我需要调整的地方
4. **"明天再说"** → 今天就到这里

**告诉我！** 🚀

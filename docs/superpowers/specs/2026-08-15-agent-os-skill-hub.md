# Agent OS Skill Hub 设计

> **创建时间**: 2026-08-15  
> **状态**: Design Spec  
> **目标**: Agent OS 提供 Skill 管理和分发能力

---

## 1. 背景与动机

### 当前问题

**agent-ts 中的 Skills**:
- Skills 存储在 `agent-ts/skills/*.md` (本地文件)
- 只有 agent-ts 能访问
- 无版本控制
- 无共享机制
- 无权限管理
- 进化系统改 skills 需要直接写文件

**问题**：
1. **不可共享**: 其他 agent 应用无法复用 skills
2. **无中心化管理**: 散落在各个 agent 应用中
3. **无协作**: 多个 agent 无法协同使用同一 skill
4. **无审计**: 谁修改了 skill？什么时候？为什么？
5. **进化困难**: 进化系统需要直接操作文件系统

### Skill Hub 的价值

**Skill Hub = Agent OS 的"应用商店"**:

```
┌─────────────────────────────────────────────────────────┐
│                    Agent OS Skill Hub                    │
│  (中心化 Skill 仓库 + 版本控制 + 权限管理 + 分发)        │
└─────────────────────────────────────────────────────────┘
       ↓ 获取                ↓ 获取              ↓ 获取
       
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  agent-ts    │    │  agent-py    │    │  agent-go    │
│  (投资决策)  │    │  (数据分析)  │    │  (高频交易)  │
└──────────────┘    └──────────────┘    └──────────────┘

共享同一套 Skills:
• morning_ai_analysis
• pool_maintenance
• signal_scanner
• ...
```

**核心能力**:
1. **中心化存储**: 所有 skills 存储在 Agent OS
2. **版本控制**: Git-like 版本历史
3. **权限管理**: 谁能读、谁能写、谁能执行
4. **动态加载**: Agent 运行时获取最新 skills
5. **A/B 测试**: 同一 skill 多个版本并行
6. **进化友好**: 进化系统通过 API 修改 skills

---

## 2. 架构设计

### 2.1 组件架构

```
┌─────────────────────────────────────────────────────────┐
│                   Agent OS Skill Hub                     │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │           Skill Registry (PostgreSQL)          │    │
│  │  • skills 表: id, name, category, owner        │    │
│  │  • skill_versions 表: version, content, hash   │    │
│  │  • skill_permissions 表: agent_id, can_read... │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │              Skill API (Go)                    │    │
│  │  • GET /skills (list)                          │    │
│  │  • GET /skills/{id} (get)                      │    │
│  │  • POST /skills (create)                       │    │
│  │  • PUT /skills/{id} (update → new version)     │    │
│  │  • GET /skills/{id}/versions (history)         │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │            Skill Evolution Engine              │    │
│  │  • 接收进化建议 (来自 agent evolution 系统)    │    │
│  │  • 验证提案 (语法、安全、测试)                 │    │
│  │  • 创建新版本 (git-like commit)                │    │
│  │  • A/B 测试管理                                │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
└─────────────────────────────────────────────────────────┘
       ↑ HTTP API
       
┌──────────────────────────────────────────────────────────┐
│                    agent-ts                              │
│  • 启动时: 从 Skill Hub 拉取 skills                      │
│  • 运行时: 调用 /skills/{id}/execute                     │
│  • 进化时: 提交进化建议到 Skill Hub                      │
└──────────────────────────────────────────────────────────┘
```

### 2.2 数据模型

#### skills 表

```sql
CREATE TABLE skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE NOT NULL,           -- skill 名称 (如 'morning_ai_analysis')
    category VARCHAR(100),                        -- 分类 (如 'trading', 'analysis', 'maintenance')
    owner VARCHAR(100) NOT NULL,                  -- 所属 agent (如 'fin-agent')
    description TEXT,                             -- 简短描述
    current_version_id UUID,                      -- 当前生效版本
    status VARCHAR(50) DEFAULT 'active',          -- active | deprecated | archived
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB                                -- { tags: [], schedule: '0 9 * * *', ... }
);
```

#### skill_versions 表

```sql
CREATE TABLE skill_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID REFERENCES skills(id) ON DELETE CASCADE,
    version VARCHAR(50) NOT NULL,                 -- 版本号 (如 'v1.2.3' 或 'v1.2.3-alpha')
    content TEXT NOT NULL,                        -- skill 的完整内容 (markdown)
    content_hash VARCHAR(64) NOT NULL,            -- SHA256 hash (防篡改)
    author VARCHAR(100),                          -- 作者 (如 'evolution-system' 或 'human-user')
    commit_message TEXT,                          -- 提交说明 (git-like)
    parent_version_id UUID,                       -- 父版本 (git-like lineage)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB,                               -- { test_results: {...}, performance: {...} }
    UNIQUE(skill_id, version)
);
```

#### skill_permissions 表

```sql
CREATE TABLE skill_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID REFERENCES skills(id) ON DELETE CASCADE,
    agent_id VARCHAR(100) NOT NULL,               -- 如 'fin-agent', 'research-agent'
    can_read BOOLEAN DEFAULT TRUE,
    can_write BOOLEAN DEFAULT FALSE,
    can_execute BOOLEAN DEFAULT TRUE,
    can_evolve BOOLEAN DEFAULT FALSE,             -- 能否提交进化建议
    granted_by VARCHAR(100),                      -- 授权人
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(skill_id, agent_id)
);
```

#### skill_executions 表 (审计日志)

```sql
CREATE TABLE skill_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID REFERENCES skills(id),
    version_id UUID REFERENCES skill_versions(id),
    agent_id VARCHAR(100) NOT NULL,
    session_id VARCHAR(255),                      -- 关联 agent session
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(50),                           -- running | completed | failed
    result JSONB,                                 -- 执行结果
    error TEXT                                    -- 错误信息
);
```

---

## 3. API 设计

### 3.1 Skill CRUD

#### 列出所有 Skills

```http
GET /api/v1/skills?category=trading&owner=fin-agent

Response:
{
  "skills": [
    {
      "id": "uuid",
      "name": "morning_ai_analysis",
      "category": "analysis",
      "owner": "fin-agent",
      "description": "工作日早盘分析",
      "current_version": "v1.3.2",
      "status": "active",
      "metadata": {
        "schedule": "0 9 * * 1-5",
        "tags": ["morning", "market-open"]
      }
    },
    ...
  ]
}
```

#### 获取 Skill 详情

```http
GET /api/v1/skills/{id}?version=v1.3.2

Response:
{
  "id": "uuid",
  "name": "morning_ai_analysis",
  "category": "analysis",
  "current_version": {
    "id": "version-uuid",
    "version": "v1.3.2",
    "content": "---\nname: morning_ai_analysis\nschedule: \"0 9 * * 1-5\"\n---\n\n# Morning AI Analysis\n\n分析今日市场...",
    "content_hash": "sha256:...",
    "author": "evolution-system",
    "commit_message": "优化了信号扫描逻辑",
    "created_at": "2026-08-15T09:00:00Z"
  },
  "permissions": {
    "can_read": true,
    "can_write": false,
    "can_execute": true,
    "can_evolve": true
  }
}
```

#### 创建 Skill

```http
POST /api/v1/skills
Content-Type: application/json

{
  "name": "new_strategy_analysis",
  "category": "analysis",
  "owner": "fin-agent",
  "description": "新策略分析",
  "content": "---\nname: new_strategy_analysis\n---\n\n# Strategy Analysis\n\n...",
  "metadata": {
    "schedule": "0 10 * * *",
    "tags": ["strategy"]
  }
}

Response:
{
  "id": "uuid",
  "name": "new_strategy_analysis",
  "current_version": "v1.0.0",
  "created_at": "2026-08-15T10:00:00Z"
}
```

#### 更新 Skill (创建新版本)

```http
PUT /api/v1/skills/{id}
Content-Type: application/json

{
  "content": "---\nname: morning_ai_analysis\nschedule: \"0 9 * * 1-5\"\n---\n\n# Morning AI Analysis (Updated)\n\n...",
  "version": "v1.3.3",  // 可选，不提供则自动递增
  "commit_message": "修复了信号扫描的 bug",
  "author": "human-user"
}

Response:
{
  "skill_id": "uuid",
  "new_version": {
    "id": "version-uuid",
    "version": "v1.3.3",
    "parent_version": "v1.3.2",
    "content_hash": "sha256:...",
    "created_at": "2026-08-15T11:00:00Z"
  }
}
```

### 3.2 版本管理

#### 获取版本历史

```http
GET /api/v1/skills/{id}/versions?limit=10

Response:
{
  "versions": [
    {
      "id": "uuid",
      "version": "v1.3.3",
      "author": "human-user",
      "commit_message": "修复了信号扫描的 bug",
      "created_at": "2026-08-15T11:00:00Z",
      "parent_version": "v1.3.2"
    },
    {
      "id": "uuid",
      "version": "v1.3.2",
      "author": "evolution-system",
      "commit_message": "优化了信号扫描逻辑",
      "created_at": "2026-08-15T09:00:00Z",
      "parent_version": "v1.3.1"
    },
    ...
  ]
}
```

#### 回滚到历史版本

```http
POST /api/v1/skills/{id}/rollback
Content-Type: application/json

{
  "target_version": "v1.3.2",
  "reason": "v1.3.3 有 bug，回滚到稳定版本"
}

Response:
{
  "skill_id": "uuid",
  "current_version": "v1.3.2",
  "rolled_back_at": "2026-08-15T12:00:00Z"
}
```

### 3.3 权限管理

#### 授权 Agent 访问 Skill

```http
POST /api/v1/skills/{id}/permissions
Content-Type: application/json

{
  "agent_id": "research-agent",
  "can_read": true,
  "can_write": false,
  "can_execute": true,
  "can_evolve": false
}

Response:
{
  "permission_id": "uuid",
  "granted_at": "2026-08-15T13:00:00Z"
}
```

### 3.4 进化集成

#### 提交进化建议

```http
POST /api/v1/skills/{id}/evolution-proposals
Content-Type: application/json

{
  "proposed_content": "...",  // 进化后的 skill 内容
  "rationale": "基于过去 30 天的执行数据，优化了...",
  "evidence": {
    "performance_improvement": "+15% win rate",
    "test_results": {...}
  },
  "author": "evolution-system"
}

Response:
{
  "proposal_id": "uuid",
  "status": "pending_review",  // pending_review | approved | rejected
  "created_at": "2026-08-15T14:00:00Z"
}
```

#### 批准进化提案

```http
POST /api/v1/skills/{id}/evolution-proposals/{proposal_id}/approve
Content-Type: application/json

{
  "reviewer": "human-user",
  "version": "v1.4.0",  // 新版本号
  "rollout_strategy": "canary"  // immediate | canary | blue_green
}

Response:
{
  "skill_id": "uuid",
  "new_version": "v1.4.0",
  "status": "active",
  "rollout": {
    "strategy": "canary",
    "percentage": 10  // 先给 10% 的执行流量
  }
}
```

---

## 4. agent-ts 集成

### 4.1 启动时拉取 Skills

**文件**: `agent-ts/src/core/bootstrap/skill-loader.ts`

```typescript
import { getAgentOSClient } from '../../infrastructure/agent-os/client.js';
import fs from 'fs';
import path from 'path';

export async function loadSkillsFromHub(): Promise<void> {
  const client = getAgentOSClient();
  
  // 1. 查询当前 agent 有权限的所有 skills
  const { skills } = await client.skills.list({
    owner: 'fin-agent',
    status: 'active'
  });
  
  // 2. 下载每个 skill 的当前版本
  for (const skill of skills) {
    const detail = await client.skills.get(skill.id);
    
    // 3. 写入本地缓存 (可选，用于离线运行)
    const localPath = path.join(process.cwd(), 'skills', `${skill.name}.md`);
    fs.writeFileSync(localPath, detail.current_version.content, 'utf-8');
    
    console.log(`✅ Loaded skill: ${skill.name} (${detail.current_version.version})`);
  }
  
  console.log(`✅ Loaded ${skills.length} skills from Skill Hub`);
}
```

**集成到启动流程**:

```typescript
// agent-ts/src/index.ts

import { loadSkillsFromHub } from './core/bootstrap/skill-loader.js';

// 启动时拉取最新 skills
await loadSkillsFromHub();

// 然后注册任务到 Scheduler
await registerAgentTasks();
```

### 4.2 运行时执行 Skill

**场景 1: 从本地缓存执行 (已下载)**
```typescript
// 现有逻辑不变
const skill = loadSkillFromFile('morning_ai_analysis');
await executeSkill(skill);
```

**场景 2: 从 Skill Hub 执行 (动态获取)**
```typescript
const client = getAgentOSClient();

// 获取最新版本
const skill = await client.skills.get('morning_ai_analysis');

// 记录执行
const execution = await client.skills.recordExecution({
  skill_id: skill.id,
  version_id: skill.current_version.id,
  agent_id: 'fin-agent',
  session_id: session.id
});

// 执行 skill
try {
  const result = await executeSkill(skill.current_version.content);
  
  // 更新执行结果
  await client.skills.updateExecution(execution.id, {
    status: 'completed',
    result
  });
} catch (error) {
  await client.skills.updateExecution(execution.id, {
    status: 'failed',
    error: error.message
  });
}
```

### 4.3 进化系统集成

**文件**: `agent-ts/src/services/evolution/skill-evolution.ts`

```typescript
import { getAgentOSClient } from '../../infrastructure/agent-os/client.js';

export async function proposeSkillEvolution(
  skillName: string,
  improvedContent: string,
  rationale: string,
  evidence: any
): Promise<void> {
  const client = getAgentOSClient();
  
  // 1. 查找 skill
  const skills = await client.skills.list({ name: skillName });
  if (skills.length === 0) {
    throw new Error(`Skill not found: ${skillName}`);
  }
  const skill = skills[0];
  
  // 2. 提交进化建议
  const proposal = await client.skills.proposeEvolution({
    skill_id: skill.id,
    proposed_content: improvedContent,
    rationale,
    evidence,
    author: 'evolution-system'
  });
  
  console.log(`✅ Evolution proposal submitted: ${proposal.id}`);
  
  // 3. 发送通知给人类审查
  await client.notifications.send({
    channel: 'feishu',
    title: `Skill 进化提案: ${skillName}`,
    content: `
**提案 ID**: ${proposal.id}
**改进点**: ${rationale}
**证据**: ${JSON.stringify(evidence, null, 2)}

请审查并决定是否批准。
    `,
    metadata: {
      proposal_id: proposal.id,
      skill_id: skill.id
    }
  });
}
```

---

## 5. 进化系统工作流

### 5.1 完整闭环

```
┌────────────────────────────────────────────────────────────┐
│ Step 1: 执行 Skill                                         │
│                                                            │
│  agent-ts 执行 'morning_ai_analysis'                       │
│     ↓                                                      │
│  记录执行结果到 Agent OS                                   │
│     skill_executions 表: { result, duration, success }     │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ Step 2: 进化分析                                           │
│                                                            │
│  每周触发 'skill_evolution_analysis' (Agent OS Scheduler)   │
│     ↓                                                      │
│  agent-ts 分析过去 7 天的 skill 执行数据                   │
│     - 查询 Agent OS: skill_executions                      │
│     - 查询 quantsys-v2: 交易结果、信号表现                 │
│     ↓                                                      │
│  LLM 推理: 哪些 skill 需要改进？如何改进？                 │
│     ↓                                                      │
│  生成改进后的 skill 内容                                   │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ Step 3: 提交进化提案                                       │
│                                                            │
│  agent-ts 调用 Agent OS API:                               │
│     POST /skills/{id}/evolution-proposals                  │
│     Body: { proposed_content, rationale, evidence }        │
│     ↓                                                      │
│  Agent OS 存储提案 (status: pending_review)                │
│     ↓                                                      │
│  Agent OS 发送通知给人类 (Feishu)                          │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ Step 4: 人类审查                                           │
│                                                            │
│  人类在 Feishu 或 Web UI 查看提案                          │
│     ↓                                                      │
│  审查改进内容、证据、测试结果                              │
│     ↓                                                      │
│  决定: Approve / Reject / Request Changes                  │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ Step 5: 批准并部署                                         │
│                                                            │
│  人类调用: POST /proposals/{id}/approve                    │
│     Body: { version: 'v1.4.0', rollout: 'canary' }         │
│     ↓                                                      │
│  Agent OS 创建新版本 (skill_versions 表)                   │
│     ↓                                                      │
│  更新 skills.current_version_id → 新版本                   │
│     ↓                                                      │
│  agent-ts 下次执行时自动使用新版本                         │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ Step 6: 监控新版本                                         │
│                                                            │
│  Agent OS 记录新版本的执行数据                             │
│     ↓                                                      │
│  如果 7 天后表现更好 → 保留                                │
│  如果表现更差 → 自动回滚到上一版本                         │
└────────────────────────────────────────────────────────────┘
```

---

## 6. A/B 测试支持

### 6.1 金丝雀发布 (Canary Rollout)

```typescript
// Agent OS 内部逻辑
class SkillExecutor {
  async getSkillVersion(skillId: string, agentId: string): Promise<SkillVersion> {
    const skill = await db.getSkill(skillId);
    
    // 检查是否有金丝雀版本
    const canary = await db.getCanaryRollout(skillId);
    if (canary) {
      // 根据 agent_id 的 hash 决定是否使用金丝雀版本
      const hash = murmurhash(agentId + canary.id);
      const bucket = hash % 100;
      
      if (bucket < canary.percentage) {
        // 使用金丝雀版本
        return db.getSkillVersion(canary.new_version_id);
      }
    }
    
    // 使用当前稳定版本
    return db.getSkillVersion(skill.current_version_id);
  }
}
```

**配置金丝雀发布**:
```http
POST /api/v1/skills/{id}/rollout
Content-Type: application/json

{
  "new_version_id": "uuid",
  "strategy": "canary",
  "percentage": 10,  // 10% 流量
  "duration_hours": 168  // 7天后自动全量或回滚
}
```

---

## 7. 迁移路径

### Phase 1: Agent OS 实现 Skill Hub (2周)

**任务**:
- [ ] 创建 4 张表 (skills, skill_versions, skill_permissions, skill_executions)
- [ ] 实现 Skill CRUD API (Go)
- [ ] 实现版本管理 API
- [ ] 实现权限检查中间件

**交付物**:
- Agent OS 具备完整 Skill Hub 功能
- API 文档
- 单元测试

### Phase 2: agent-ts 集成 (1周)

**任务**:
- [ ] 实现 `agent-os-client` 的 `skills` 模块
- [ ] 实现启动时从 Skill Hub 拉取 skills
- [ ] 修改 skill 加载逻辑 (优先从本地缓存，fallback 到 Hub)
- [ ] 记录 skill 执行到 Agent OS

**交付物**:
- agent-ts 启动时自动同步 skills
- 执行数据记录到 Agent OS
- 本地缓存机制 (离线可用)

### Phase 3: 进化系统集成 (1周)

**任务**:
- [ ] 修改进化系统，通过 API 提交提案 (不直接写文件)
- [ ] 实现进化提案审查 UI (Web Dashboard)
- [ ] 实现金丝雀发布机制
- [ ] 实现自动回滚逻辑

**交付物**:
- 完整进化闭环
- 人类审查界面
- A/B 测试能力

### Phase 4: 多 Agent 共享 (可选)

**任务**:
- [ ] 创建其他 agent 应用 (agent-py, agent-go)
- [ ] 验证 Skill Hub 的共享能力
- [ ] 跨 agent 权限管理

---

## 8. 成功标准

### 功能完整性
- [ ] Skills 存储在 Agent OS，不在 agent-ts 本地
- [ ] agent-ts 启动时自动同步 skills
- [ ] 支持版本历史和回滚
- [ ] 进化系统通过 API 提交建议
- [ ] 人类可通过 UI 审查和批准进化

### 性能指标
- Skill 拉取延迟 < 100ms
- 版本切换延迟 < 50ms
- 支持 1000+ skills 并发查询

### 可靠性
- 本地缓存机制，Hub 宕机不影响 agent 运行
- 版本内容 hash 校验，防篡改
- 权限检查，防止未授权访问

---

## 9. 未来扩展

### 9.1 Skill Marketplace

**公共 Skill 商店**:
- 社区贡献的 skills
- 评分和评论系统
- 付费 skills (高级策略)

### 9.2 跨 Agent 协作

**Skill 组合**:
- agent-ts 执行 'morning_ai_analysis'
- 调用 agent-py 的 'deep_ml_analysis' skill
- 组合多个 agent 的能力

### 9.3 Skill 语义搜索

**自然语言查询**:
```
Human: "我需要一个能分析市场情绪的 skill"
Agent OS: 返回相关 skills: [market_sentiment_analysis, social_media_monitor, ...]
```

---

**状态**: ✅ 设计完成，Ready for Review  
**审查**: 待用户确认设计方向  
**预计工作量**: 4 周 (P1 基础功能 + P2 agent-ts 集成 + P3 进化集成 + P4 多 agent)

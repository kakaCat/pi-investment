# WP-14: agent-ts 接入 Skill Hub

> **优先级**: P0  
> **工作量**: 3天  
> **状态**: 🟡 等待 WP-12 完成  
> **依赖**: WP-12 (Scheduler HTTP API) - 可与 WP-15 并行  
> **阻塞**: 无

---

## 1. 背景与目标

### 1.1 问题

agent-ts 目前从**本地文件**读取 skills (`agent-ts/skills/*.md`)，导致：

❌ Skills 分散在本地，无中心化管理  
❌ 无版本控制，无法追溯变更历史  
❌ 进化系统直接写文件，无审计  
❌ 无法跨 agent 共享 skills  

**但是**：Agent OS Skill Hub 后端已完整实现（100%），只是 agent-ts 未集成。

### 1.2 目标

agent-ts 完全接入 Agent OS Skill Hub：

✅ 实现 agent-os-client SkillsClient SDK  
✅ 启动时从 Agent OS 加载 skill 元数据  
✅ 运行时通过 ID 获取 skill content  
✅ 实现 3 个 tools (skill_list/skill_get/skill_update)  
✅ 迁移现有 skills 到 Agent OS  

---

## 2. 核心工作

### 2.1 Day 1: agent-os-client SDK

#### A. 创建 SkillsClient

**新建文件**: `agent-os-client/src/skills.ts`

```typescript
import { BaseClient } from './base-client.js';

export interface SkillMetadata {
  id: string;
  name: string;
  description: string;
  category: string;
  owner: string;
  status: string;
  metadata?: Record<string, any>;
}

export interface SkillDetail {
  id: string;
  name: string;
  description: string;
  category: string;
  owner: string;
  status: string;
  content: string;
  version: string;
  created_at: string;
  updated_at: string;
  current_version_id?: string;
  metadata?: Record<string, any>;
}

export interface CreateSkillRequest {
  name: string;
  description: string;
  category: string;
  owner: string;
  content: string;
  author: string;
  metadata?: Record<string, any>;
}

export interface UpdateSkillRequest {
  content: string;
  author: string;
  commit_message: string;
}

export interface SkillVersion {
  id: string;
  skill_id: string;
  version: string;
  content: string;
  content_hash: string;
  author: string;
  commit_message: string;
  parent_version_id?: string;
  created_at: string;
  metadata?: Record<string, any>;
}

export class SkillsClient extends BaseClient {
  /**
   * 列出所有 skills（仅元数据，不含 content）
   */
  async list(params?: {
    owner?: string;
    status?: string;
  }): Promise<SkillMetadata[]> {
    const queryParams = new URLSearchParams();
    if (params?.owner) queryParams.append('owner', params.owner);
    if (params?.status) queryParams.append('status', params.status);

    const url = `/api/v1/skills${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
    const response = await this.get(url);
    return response.skills || [];
  }

  /**
   * 获取 skill 详情（含 content）
   */
  async get(id: string): Promise<SkillDetail> {
    return this.get(`/api/v1/skills/${id}`);
  }

  /**
   * 创建新 skill
   */
  async create(data: CreateSkillRequest): Promise<SkillDetail> {
    return this.post('/api/v1/skills', data);
  }

  /**
   * 更新 skill（创建新版本）
   */
  async update(id: string, data: UpdateSkillRequest): Promise<SkillVersion> {
    return this.put(`/api/v1/skills/${id}`, data);
  }

  /**
   * 删除 skill
   */
  async delete(id: string): Promise<void> {
    return this.delete(`/api/v1/skills/${id}`);
  }

  /**
   * 通过 name 查找 skill（便捷方法）
   */
  async findByName(name: string, owner?: string): Promise<SkillMetadata | null> {
    const skills = await this.list({ owner });
    return skills.find(s => s.name === name) || null;
  }

  /**
   * 批量获取 skills（通过 IDs）
   */
  async batchGet(ids: string[]): Promise<SkillDetail[]> {
    const promises = ids.map(id => this.get(id));
    return Promise.all(promises);
  }
}
```

---

#### B. 集成到 AgentOSClient

**修改文件**: `agent-os-client/src/index.ts`

```typescript
import { SkillsClient } from './skills.js';
import { MemoryClient } from './memory.js';
// ... 其他 imports

export class AgentOSClient {
  public skills: SkillsClient;
  public memory: MemoryClient;
  // ... 其他 clients

  constructor(baseURL: string, apiKey?: string) {
    const config = { baseURL, apiKey };
    
    this.skills = new SkillsClient(config);
    this.memory = new MemoryClient(config);
    // ...
  }
}

// Singleton
let clientInstance: AgentOSClient | null = null;

export function initAgentOSClient(baseURL: string, apiKey?: string): AgentOSClient {
  clientInstance = new AgentOSClient(baseURL, apiKey);
  return clientInstance;
}

export function getAgentOSClient(): AgentOSClient {
  if (!clientInstance) {
    throw new Error('AgentOSClient not initialized. Call initAgentOSClient() first.');
  }
  return clientInstance;
}

// 导出类型
export * from './skills.js';
export * from './memory.js';
// ...
```

---

#### C. 编译和发布

```bash
cd agent-os-client
npm run build
npm version patch
npm publish

# 或者本地 link（开发时）
npm link
```

---

### 2.2 Day 2: agent-ts 集成

#### A. 创建 Skill Registry Loader

**新建文件**: `agent-ts/src/core/bootstrap/skill-registry.ts`

```typescript
import { getAgentOSClient } from 'agent-os-client';
import type { SkillMetadata } from 'agent-os-client';
import { logger } from '../../infrastructure/logging/index.js';

/**
 * 内存中的 skill 注册表（仅元数据）
 */
let skillRegistry: SkillMetadata[] = [];

/**
 * 从 Agent OS 加载 skill 注册表
 */
export async function loadSkillRegistry(): Promise<void> {
  logger.info('[SkillRegistry] Loading skills from Agent OS...');
  
  const client = getAgentOSClient();
  
  try {
    skillRegistry = await client.skills.list({
      owner: 'fin-agent',
      status: 'active'
    });
    
    logger.info(`[SkillRegistry] ✅ Loaded ${skillRegistry.length} skills`);
    
    // 打印所有 skills（便于调试）
    skillRegistry.forEach(skill => {
      const schedule = skill.metadata?.schedule;
      logger.info(`  - ${skill.name}: ${skill.description}${schedule ? ` (${schedule})` : ''}`);
    });
  } catch (error) {
    logger.error('[SkillRegistry] ❌ Failed to load skills:', error);
    
    // 如果无法加载，尝试从本地文件作为降级
    logger.warn('[SkillRegistry] Falling back to local files...');
    await loadSkillsFromLocalFiles();
  }
}

/**
 * 获取 skill 注册表
 */
export function getSkillRegistry(): SkillMetadata[] {
  return skillRegistry;
}

/**
 * 通过 name 查找 skill 元数据
 */
export function findSkillByName(name: string): SkillMetadata | undefined {
  return skillRegistry.find(s => s.name === name);
}

/**
 * 通过 ID 查找 skill 元数据
 */
export function findSkillById(id: string): SkillMetadata | undefined {
  return skillRegistry.find(s => s.id === id);
}

/**
 * 模糊搜索 skill（通过 name 或 description）
 */
export function searchSkills(query: string): SkillMetadata[] {
  const lowerQuery = query.toLowerCase();
  return skillRegistry.filter(s => 
    s.name.toLowerCase().includes(lowerQuery) ||
    s.description.toLowerCase().includes(lowerQuery)
  );
}

/**
 * 降级：从本地文件加载（保留兼容性）
 */
async function loadSkillsFromLocalFiles(): Promise<void> {
  // TODO: 实现从 skills/*.md 加载
  // 这是降级方案，保证即使 Agent OS 不可用也能运行
  logger.warn('[SkillRegistry] Local file loading not implemented yet');
  skillRegistry = [];
}
```

---

#### B. 创建 Skill Executor

**新建文件**: `agent-ts/src/core/skills/skill-executor.ts`

```typescript
import { getAgentOSClient } from 'agent-os-client';
import { logger } from '../../infrastructure/logging/index.js';
import { findSkillByName, findSkillById } from '../bootstrap/skill-registry.js';

/**
 * 从 Agent OS 获取 skill 完整内容并执行
 */
export async function executeSkillById(skillId: string, context?: any): Promise<any> {
  logger.info(`[SkillExecutor] Executing skill by ID: ${skillId}`);
  
  const client = getAgentOSClient();
  
  try {
    // 1. 从 Agent OS 获取 skill 详情（含 content）
    const skill = await client.skills.get(skillId);
    
    logger.info(`[SkillExecutor] Loaded skill: ${skill.name} (version: ${skill.version})`);
    
    // 2. 解析 skill content
    const parsed = parseSkillContent(skill.content);
    
    // 3. 执行 skill（传给 LLM 或直接执行）
    const result = await executeParsedSkill(parsed, context);
    
    logger.info(`[SkillExecutor] ✅ Skill executed: ${skill.name}`);
    
    return result;
  } catch (error) {
    logger.error(`[SkillExecutor] ❌ Skill execution failed: ${skillId}`, error);
    throw error;
  }
}

/**
 * 通过 name 执行 skill（便捷方法）
 */
export async function executeSkillByName(skillName: string, context?: any): Promise<any> {
  logger.info(`[SkillExecutor] Executing skill by name: ${skillName}`);
  
  const metadata = findSkillByName(skillName);
  if (!metadata) {
    throw new Error(`Skill not found: ${skillName}`);
  }
  
  return executeSkillById(metadata.id, context);
}

/**
 * 解析 skill content（markdown frontmatter + body）
 */
function parseSkillContent(content: string): any {
  // TODO: 实现 markdown frontmatter 解析
  // 返回: { name, schedule, description, instructions, ... }
  return {
    content,
    // parsed frontmatter...
  };
}

/**
 * 执行解析后的 skill
 */
async function executeParsedSkill(parsed: any, context: any): Promise<any> {
  // TODO: 调用 LLM，传入 skill instructions + context
  // 或者根据 skill 类型执行不同的逻辑
  
  logger.info('[SkillExecutor] Executing parsed skill...');
  
  // 这里接入现有的 skill 执行逻辑
  // ...
  
  return { success: true };
}
```

---

#### C. 修改启动流程

**修改文件**: `agent-ts/src/index.ts`

```typescript
import { initAgentOSClient } from 'agent-os-client';
import { loadSkillRegistry } from './core/bootstrap/skill-registry.js';
import { registerTasksToAgentOS } from './core/bootstrap/agent-os-task-registration.js';

async function bootstrap() {
  try {
    // 1. 初始化 Agent OS Client
    const agentOSURL = process.env.AGENT_OS_BASE_URL || 'http://localhost:8080';
    initAgentOSClient(agentOSURL);
    logger.info('✅ Agent OS Client initialized');
    
    // 2. 加载 Skill Registry（从 Agent OS）
    await loadSkillRegistry();
    logger.info('✅ Skill Registry loaded');
    
    // 3. 注册调度任务到 Agent OS
    await registerTasksToAgentOS();
    logger.info('✅ Tasks registered to Agent OS');
    
    // 4. 启动 Gateway API
    await startGatewayServer();
    logger.info('✅ Gateway API started');
    
    logger.info('🚀 agent-ts started with full Agent OS integration');
  } catch (error) {
    logger.error('❌ Bootstrap failed:', error);
    process.exit(1);
  }
}

bootstrap();
```

---

### 2.3 Day 3: Tools + Migration

#### A. 实现 skill_list 工具

**新建文件**: `agent-ts/src/infrastructure/tools/skill/skill-list-tool.ts`

```typescript
import { tool } from 'ai';
import { z } from 'zod';
import { getSkillRegistry, searchSkills } from '../../../core/bootstrap/skill-registry.js';

export const skillListTool = tool({
  description: `
列出所有可用的 skills。可以通过关键词搜索。

用途：
- 查看系统有哪些 skills
- 搜索特定功能的 skill
- 了解 skill 的用途和分类
`,
  parameters: z.object({
    query: z.string().optional().describe('搜索关键词（可选）'),
    category: z.string().optional().describe('分类过滤（可选）')
  }),
  
  execute: async ({ query, category }) => {
    let skills = getSkillRegistry();
    
    // 搜索过滤
    if (query) {
      skills = searchSkills(query);
    }
    
    // 分类过滤
    if (category) {
      skills = skills.filter(s => s.category === category);
    }
    
    return {
      total: skills.length,
      skills: skills.map(s => ({
        id: s.id,
        name: s.name,
        description: s.description,
        category: s.category,
        schedule: s.metadata?.schedule
      }))
    };
  }
});
```

---

#### B. 实现 skill_get 工具

**新建文件**: `agent-ts/src/infrastructure/tools/skill/skill-get-tool.ts`

```typescript
import { tool } from 'ai';
import { z } from 'zod';
import { getAgentOSClient } from 'agent-os-client';
import { findSkillByName } from '../../../core/bootstrap/skill-registry.js';

export const skillGetTool = tool({
  description: `
获取 skill 的完整内容。

用途：
- 查看 skill 的详细指令
- 了解 skill 的执行逻辑
- 调试 skill 内容
`,
  parameters: z.object({
    name: z.string().describe('Skill 名称'),
  }),
  
  execute: async ({ name }) => {
    const client = getAgentOSClient();
    
    // 1. 从注册表找到 ID
    const metadata = findSkillByName(name);
    if (!metadata) {
      return { error: `Skill not found: ${name}` };
    }
    
    // 2. 从 Agent OS 获取完整内容
    const skill = await client.skills.get(metadata.id);
    
    return {
      id: skill.id,
      name: skill.name,
      description: skill.description,
      version: skill.version,
      content: skill.content,
      updated_at: skill.updated_at
    };
  }
});
```

---

#### C. 实现 skill_update 工具

**新建文件**: `agent-ts/src/infrastructure/tools/skill/skill-update-tool.ts`

```typescript
import { tool } from 'ai';
import { z } from 'zod';
import { getAgentOSClient } from 'agent-os-client';
import { findSkillByName } from '../../../core/bootstrap/skill-registry.js';

export const skillUpdateTool = tool({
  description: `
更新 skill 内容（进化系统使用）。

⚠️ 注意：此操作会创建新版本，需谨慎使用。

用途：
- 进化系统改进 skill
- 修复 skill 的 bug
- 优化 skill 的逻辑
`,
  parameters: z.object({
    name: z.string().describe('Skill 名称'),
    new_content: z.string().describe('新的 skill 内容（完整 markdown）'),
    reason: z.string().describe('修改原因'),
    author: z.string().default('evolution-system').describe('作者')
  }),
  
  execute: async ({ name, new_content, reason, author }) => {
    const client = getAgentOSClient();
    
    // 1. 从注册表找到 ID
    const metadata = findSkillByName(name);
    if (!metadata) {
      return { error: `Skill not found: ${name}` };
    }
    
    // 2. 更新 skill（创建新版本）
    const newVersion = await client.skills.update(metadata.id, {
      content: new_content,
      author,
      commit_message: reason
    });
    
    return {
      success: true,
      skill_id: metadata.id,
      skill_name: name,
      new_version: newVersion.version,
      message: `Skill updated: ${name} → ${newVersion.version}`
    };
  }
});
```

---

#### D. 注册工具

**修改文件**: `agent-ts/src/infrastructure/tools/index.ts`

```typescript
import { skillListTool } from './skill/skill-list-tool.js';
import { skillGetTool } from './skill/skill-get-tool.js';
import { skillUpdateTool } from './skill/skill-update-tool.js';

export const SKILL_TOOLS = {
  skill_list: skillListTool,
  skill_get: skillGetTool,
  skill_update: skillUpdateTool,
};

// 合并到总工具集
export const ALL_TOOLS = {
  ...EXISTING_TOOLS,
  ...SKILL_TOOLS,
};
```

---

#### E. 迁移脚本

**新建文件**: `agent-ts/scripts/migrate-skills-to-os.ts`

```typescript
#!/usr/bin/env tsx

import fs from 'fs';
import path from 'path';
import { initAgentOSClient } from 'agent-os-client';

async function migrateSkills() {
  // 1. 初始化 client
  const agentOSURL = process.env.AGENT_OS_BASE_URL || 'http://localhost:8080';
  const client = initAgentOSClient(agentOSURL);
  
  // 2. 读取本地 skills 目录
  const skillsDir = path.join(process.cwd(), 'skills');
  const files = fs.readdirSync(skillsDir).filter(f => f.endsWith('.md'));
  
  console.log(`Found ${files.length} skill files`);
  
  let successCount = 0;
  let failCount = 0;
  
  for (const file of files) {
    const skillName = path.basename(file, '.md');
    const content = fs.readFileSync(path.join(skillsDir, file), 'utf-8');
    
    try {
      // 3. 解析 frontmatter
      const { description, category, schedule } = parseFrontmatter(content);
      
      // 4. 创建 skill 到 Agent OS
      const skill = await client.skills.create({
        name: skillName,
        description: description || `Skill: ${skillName}`,
        category: category || 'general',
        owner: 'fin-agent',
        content,
        author: 'migration-script',
        metadata: schedule ? { schedule } : {}
      });
      
      console.log(`✅ Migrated: ${skillName} (id: ${skill.id})`);
      successCount++;
    } catch (error: any) {
      console.error(`❌ Failed to migrate ${skillName}:`, error.message);
      failCount++;
    }
  }
  
  console.log(`\nMigration complete: ${successCount} success, ${failCount} failed`);
}

function parseFrontmatter(content: string): { description?: string; category?: string; schedule?: string } {
  const match = content.match(/^---\n([\s\S]+?)\n---/);
  if (!match) return {};
  
  const frontmatter = match[1];
  const result: any = {};
  
  const descMatch = frontmatter.match(/description:\s*"([^"]+)"/);
  if (descMatch) result.description = descMatch[1];
  
  const categoryMatch = frontmatter.match(/category:\s*"([^"]+)"/);
  if (categoryMatch) result.category = categoryMatch[1];
  
  const scheduleMatch = frontmatter.match(/schedule:\s*"([^"]+)"/);
  if (scheduleMatch) result.schedule = scheduleMatch[1];
  
  return result;
}

migrateSkills().catch(console.error);
```

**添加到 package.json**:

```json
{
  "scripts": {
    "migrate-skills": "tsx scripts/migrate-skills-to-os.ts"
  }
}
```

---

## 3. 验收标准

### 3.1 SDK 测试

```typescript
// test-skills-client.ts
import { initAgentOSClient } from 'agent-os-client';

const client = initAgentOSClient('http://localhost:8080');

// 1. 列出 skills
const skills = await client.skills.list({ owner: 'fin-agent' });
console.log(`Found ${skills.length} skills`);

// 2. 获取详情
const skill = await client.skills.get(skills[0].id);
console.log(`Skill content length: ${skill.content.length}`);

// 3. 创建 skill
const newSkill = await client.skills.create({
  name: 'test_skill',
  description: 'Test',
  category: 'test',
  owner: 'fin-agent',
  content: '# Test\n\nContent',
  author: 'test'
});
console.log(`Created: ${newSkill.id}`);
```

---

### 3.2 集成测试

```bash
# 1. 迁移现有 skills
npm run migrate-skills

# 预期输出：
# Found 15 skill files
# ✅ Migrated: morning_ai_analysis (id: ...)
# ✅ Migrated: pool_maintenance (id: ...)
# ...

# 2. 启动 agent-ts
npm run start

# 预期日志：
# ✅ Agent OS Client initialized
# [SkillRegistry] Loading skills from Agent OS...
# [SkillRegistry] ✅ Loaded 15 skills
#   - morning_ai_analysis: 工作日早盘分析 (0 9 * * 1-5)
#   ...

# 3. 测试 tools
# 在 agent 对话中：
# > 列出所有 skills
# > 查看 morning_ai_analysis 的内容
# > 更新 test_skill 的内容
```

---

### 3.3 验证 Skills 从 OS 获取

```bash
# 1. 删除本地 skills 目录（备份后）
mv skills skills.backup

# 2. 重启 agent-ts
npm run start

# 3. 验证仍然能加载 skills（从 Agent OS）
# 4. 验证 skills 能正常执行
```

---

## 4. 交付物清单

- [ ] `agent-os-client/src/skills.ts` (新建)
- [ ] `agent-os-client/src/index.ts` (修改)
- [ ] `agent-ts/src/core/bootstrap/skill-registry.ts` (新建)
- [ ] `agent-ts/src/core/skills/skill-executor.ts` (新建)
- [ ] `agent-ts/src/infrastructure/tools/skill/*.ts` (3个文件)
- [ ] `agent-ts/src/infrastructure/tools/index.ts` (修改)
- [ ] `agent-ts/scripts/migrate-skills-to-os.ts` (新建)
- [ ] `agent-ts/package.json` (修改)
- [ ] `agent-ts/src/index.ts` (修改)
- [ ] 测试通过的截图或日志

---

## 5. 注意事项

### 5.1 降级方案

如果 Agent OS 不可用，保留从本地文件加载的能力。

### 5.2 缓存策略

- 启动时加载元数据（一次）
- 运行时获取 content（按需）
- 考虑添加内存缓存（可选）

### 5.3 迁移后清理

迁移成功后：
- 保留 `skills/` 目录作为备份
- 添加 README 说明已迁移
- 不要删除本地文件（回滚用）

---

## 6. 完成后通知

完成后请通知主窗口进行 Code Review，提供：
- SDK 测试结果
- 迁移日志（skills 已上传到 Agent OS）
- agent-ts 启动日志（从 OS 加载 skills）
- Tools 测试截图

---

**任务文档版本**: v1.0  
**创建时间**: 2026-08-15 23:50  
**创建人**: Claude (Opus 5) - 主窗口

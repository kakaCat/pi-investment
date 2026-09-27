# 台账数据模型扩展


扩展 dsh-reqboard.json 台账的数据模型，新增 artifacts[] / designServes[] / implements 字段，schemaVersion 从 8 升到 9，保持向后兼容（旧数据可正常读取），验收标准：运行迁移脚本后台账 schemaVersion = 9，所有需求/任务包含新字段且旧数据不丢失。


## 需求对象新增字段（serves: FR-2）

```typescript
interface Requirement {
  // ============ 现有字段（保持不变）============
  id: string                    // REQ-xxx
  title: string
  description: string
  category: 'feature' | 'bug' | 'doc' | 'refactor' | 'spike' | 'chore'
  status: RequirementStatus
  sourceSessionId?: string
  blocked: boolean
  comments: Comment[]
  version: number
  createdAt: number
  updatedAt: number
  createdBy: Actor
  updatedBy: Actor
  statusHistory: StatusHistoryEntry[]
  
  // ============ 新增字段 ============
  artifacts?: Artifact[]        // 产物列表（可选，默认 []）
}

interface Artifact {
  kind: 'requirement' | 'design' | 'plan' | 'verification' | 'archive'
  path: string                  // 文件路径（工作区相对，如 "docs/requirements/REQ-xxx/requirement.md"）
  stage: string                 // 节点名称（brainstorming / design / decomposing / ...）
  confirmed?: boolean           // 是否已确认（可选）
  confirmedAt?: number          // 确认时间戳 ms（可选）
}
```

**字段约束**：
- `artifacts`: 可选，默认 `[]`（空数组）
- 旧需求缺失此字段时，读取代码视为 `[]`
- 每个 artifact 的 `kind` 和 `path` 必填，其他可选

**示例**：
```json
{
  "id": "REQ-202609262349-1518",
  "title": "RTM YAML 追溯基础设施完整实现",
  "artifacts": [
    {
      "kind": "requirement",
      "path": "docs/requirements/REQ-202609262349-1518/requirement.md",
      "stage": "brainstorming",
      "confirmed": true,
      "confirmedAt": 1727389200000
    },
    {
      "kind": "design",
      "path": "docs/requirements/REQ-202609262349-1518/design/architecture.md",
      "stage": "design",
      "confirmed": false
    }
  ]
}
```

## 任务对象新增字段（serves: FR-2）

```typescript
interface Task {
  // ============ 现有字段（保持不变）============
  id: string                    // t-xxx
  requirementId: string
  title: string
  description?: string
  acceptance?: string
  phase: 'doc' | 'ui' | 'analysis' | 'implement' | 'test' | 'review' | 'merge'
  side: 'frontend' | 'backend' | 'fullstack' | 'doc'
  status: TaskStatus
  blocked: boolean
  dependsOn: string[]
  scope?: string
  context?: string
  executions?: Execution[]
  comments: Comment[]
  version: number
  createdAt: number
  updatedAt: number
  createdBy: Actor
  updatedBy: Actor
  statusHistory: StatusHistoryEntry[]
  
  // ============ 新增字段 ============
  designServes?: string[]       // 服务的 FR 列表（可选，默认 null）
  implements?: string           // 实现的设计章节（可选，默认 null）
}
```

**字段约束**：
- `designServes`: 可选，默认 `null`（不是空数组）
  - 存在时为字符串数组，如 `["FR-1", "FR-2"]`
  - 旧任务缺失此字段时，读取代码视为 `null`
- `implements`: 可选，默认 `null`
  - 存在时为字符串，如 `"design/architecture.md#整体架构"`
  - 旧任务缺失此字段时，读取代码视为 `null`

**示例**：
```json
{
  "id": "t-354ea0",
  "requirementId": "REQ-202609262349-1518",
  "title": "实现 RTM 文件结构",
  "phase": "implement",
  "side": "backend",
  "status": "done",
  "designServes": ["FR-1"],
  "implements": "design/rtm-file-structure.md#通用结构"
}
```

## schemaVersion 升级（serves: FR-2）

```typescript
interface Ledger {
  schemaVersion: 9              // 从 8 升到 9
  revision: number
  requirements: Requirement[]
  tasks?: Task[]
}
```

**升级规则**：
- 旧版本台账（schemaVersion = 8）可以正常读取
- 读取时自动补全缺失字段：
  - `requirement.artifacts` 缺失 → 视为 `[]`
  - `task.designServes` 缺失 → 视为 `null`
  - `task.implements` 缺失 → 视为 `null`
- 写入时强制更新为 schemaVersion = 9

## 向后兼容设计（serves: FR-2）

**读取兼容**：
```typescript
// JsonLedgerRepository.ts 读取逻辑
function readLedger(filePath: string): Ledger {
  const raw = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  
  // 补全需求对象的新字段
  for (const req of raw.requirements) {
    if (!req.artifacts) {
      req.artifacts = [];  // 旧需求默认空数组
    }
  }
  
  // 补全任务对象的新字段
  if (raw.tasks) {
    for (const task of raw.tasks) {
      if (!task.designServes) {
        task.designServes = null;  // 旧任务默认 null
      }
      if (!task.implements) {
        task.implements = null;
      }
    }
  }
  
  return raw;
}
```

**写入兼容**：
```typescript
// JsonLedgerRepository.ts 写入逻辑
function writeLedger(ledger: Ledger): void {
  // 强制升级 schemaVersion
  ledger.schemaVersion = 9;
  
  // 写入前验证新字段格式
  for (const req of ledger.requirements) {
    if (req.artifacts && !Array.isArray(req.artifacts)) {
      throw new Error(`Invalid artifacts field in ${req.id}`);
    }
  }
  
  if (ledger.tasks) {
    for (const task of ledger.tasks) {
      if (task.designServes && !Array.isArray(task.designServes)) {
        throw new Error(`Invalid designServes field in ${task.id}`);
      }
      if (task.implements && typeof task.implements !== 'string') {
        throw new Error(`Invalid implements field in ${task.id}`);
      }
    }
  }
  
  fs.writeFileSync(filePath, JSON.stringify(ledger, null, 2));
}
```

## 数据迁移脚本（serves: FR-9）

```typescript
// scripts/migrate-reqboard-schema-v9.ts

import * as fs from 'node:fs';
import * as path from 'node:path';

const LEDGER_PATH = '.dsh-data/dsh-reqboard.json';
const BACKUP_SUFFIX = '.bak-v8';

async function migrate() {
  console.log('开始迁移台账到 schemaVersion 9...');
  
  // 1. 读取现有台账
  const ledger = JSON.parse(fs.readFileSync(LEDGER_PATH, 'utf-8'));
  
  // 2. 检查版本（幂等：已迁移则跳过）
  if (ledger.schemaVersion >= 9) {
    console.log(`台账已是 v${ledger.schemaVersion}，跳过迁移`);
    return;
  }
  
  console.log(`当前版本：v${ledger.schemaVersion}`);
  
  // 3. 备份旧版本
  const backupPath = LEDGER_PATH + BACKUP_SUFFIX;
  fs.copyFileSync(LEDGER_PATH, backupPath);
  console.log(`已备份到：${backupPath}`);
  
  // 4. 迁移需求对象
  let reqMigrated = 0;
  for (const req of ledger.requirements) {
    if (!req.artifacts) {
      req.artifacts = [];
      reqMigrated++;
    }
  }
  console.log(`迁移 ${reqMigrated} 个需求对象（添加 artifacts 字段）`);
  
  // 5. 迁移任务对象
  let taskMigrated = 0;
  if (ledger.tasks) {
    for (const task of ledger.tasks) {
      let changed = false;
      if (!task.designServes) {
        task.designServes = null;
        changed = true;
      }
      if (!task.implements) {
        task.implements = null;
        changed = true;
      }
      if (changed) taskMigrated++;
    }
  }
  console.log(`迁移 ${taskMigrated} 个任务对象（添加 designServes / implements 字段）`);
  
  // 6. 更新 schemaVersion
  ledger.schemaVersion = 9;
  
  // 7. 写回台账
  fs.writeFileSync(LEDGER_PATH, JSON.stringify(ledger, null, 2));
  console.log('迁移完成！');
  console.log(`  - 需求对象：${ledger.requirements.length} 个`);
  console.log(`  - 任务对象：${ledger.tasks?.length || 0} 个`);
  console.log(`  - schemaVersion：${ledger.schemaVersion}`);
}

migrate().catch(err => {
  console.error('迁移失败:', err);
  process.exit(1);
});
```

## 回滚方案（serves: FR-9）

```bash
# 恢复备份
cp .dsh-data/dsh-reqboard.json.bak-v8 .dsh-data/dsh-reqboard.json

# 重启服务
./scripts/restart-with-build.sh
```
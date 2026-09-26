---
requirement_id: REQ-260926140539-457b
design_type: interfaces
version: 1.0
serves: FR-2, FR-7, FR-8
---

# RTM 系统接口设计

## 目标 serves: FR-2, FR-7, FR-8

定义 RTM 生成引擎的核心接口、StageOverview API 增强接口，以及 Dive 模式集成接口，确保各模块间的清晰边界和数据契约。

---

## 1. RTM 生成引擎接口 serves: FR-2
### 1.1 RTMGenerator 类 serves: FR-2

**位置**：agent-dh/packages/pmboard/src/rtm/generator.ts

**接口定义**：

```typescript
export interface RTMGeneratorConfig {
  reqboardPath: string;  // dsh-reqboard.json 路径
  reqDir: string;        // docs/requirements/<REQ>/ 目录
}

export class RTMGenerator {
  constructor(config: RTMGeneratorConfig);

  /**
   * 生成全局生命周期文件
   * 触发点：reqboard_create
   */
  async generateLifecycle(reqId: string): Promise<RTMLifecycle>;

  /**
   * 生成 brainstorming 节点 RTM
   * 触发点：reqboard_submit(kind=requirement)
   */
  async generateBrainstorming(reqId: string): Promise<RTMBrainstorming>;

  /**
   * 生成 design 节点 RTM
   * 触发点：reqboard_submit(kind=design)
   */
  async generateDesign(reqId: string): Promise<RTMDesign>;

  /**
   * 生成 decomposing 节点 RTM
   * 触发点：reqboard_ask_confirm(target=plan)
   */
  async generateDecomposing(reqId: string): Promise<RTMDecomposing>;

  /**
   * 生成 implementing 节点 RTM（汇总 + 任务文件）
   * 触发点：reqboard_ask_confirm(target=plan) - 生成骨架
   */
  async generateImplementing(reqId: string): Promise<RTMImplementing>;

  /**
   * 更新任务状态（增量更新）
   * 触发点：reqboard_task_move
   */
  async updateTaskStatus(
    reqId: string,
    taskId: string,
    updates: TaskStatusUpdate
  ): Promise<void>;

  /**
   * 生成 accepting 节点 RTM
   * 触发点：reqboard_submit(kind=verification)
   */
  async generateAccepting(reqId: string): Promise<RTMAccepting>;
}

// 任务状态更新接口
export interface TaskStatusUpdate {
  status?: 'todo' | 'in_progress' | 'testing' | 'in_review' | 'done';
  workflow?: WorkflowUpdate[];
}

export interface WorkflowUpdate {
  phase: 'doc' | 'ui' | 'analysis' | 'implement' | 'test' | 'review' | 'commit';
  status: 'pending' | 'in_progress' | 'done' | 'skipped';
  started_at?: string;
  completed_at?: string;
  skip_reason?: string;
}
```

### 1.2 RTMParser 类 serves: FR-3

**位置**：agent-dh/packages/pmboard/src/rtm/parser.ts

**接口定义**：

```typescript
export class RTMParser {
  /**
   * 解析需求文档提取 FR 列表
   * 匹配：**FR-N: 标题
   */
  parseRequirementFRs(content: string): FR[];

  /**
   * 解析设计文档提取章节和 serves 标注
   * 匹配：## N.M 标题 和 serves: FR-1, FR-2
   */
  parseDesignSections(files: DesignFile[]): DesignSection[];

  /**
   * 解析任务的 design_serves（从台账）
   */
  parseTaskImplements(tasks: Task[]): Map<string, string[]>;

  /**
   * 解析测试文档提取 covers 标注
   * 匹配：covers: t-xxx
   */
  parseTestCovers(files: TestFile[]): Map<string, string[]>;
}

// 输入接口
export interface DesignFile {
  path: string;
  content: string;
}

export interface TestFile {
  path: string;
  content: string;
}

// 输出接口
export interface FR {
  id: string;          // FR-1
  title: string;
  source: string;      // requirement.md
  line: number;
}

export interface DesignSection {
  ref: string;         // design/arch.md#1.1
  title: string;
  serves: string[];    // [FR-1, FR-2]
  file: string;
  section: string;
}
```

### 1.3 RTMValidator 类 serves: FR-9

**位置**：agent-dh/packages/pmboard/src/rtm/validator.ts

**接口定义**：

```typescript
export class RTMValidator {
  /**
   * 计算设计覆盖度
   * 检查：每个 FR 是否有对应的设计章节
   */
  validateDesignCoverage(
    frs: FR[],
    frToDesign: Map<string, string[]>
  ): Coverage;

  /**
   * 计算实施覆盖度
   * 检查：每个设计章节是否有对应的任务
   */
  validateImplementationCoverage(
    designSections: DesignSection[],
    designToTasks: Map<string, string[]>
  ): Coverage;

  /**
   * 计算测试覆盖度
   * 检查：每个任务是否有对应的测试用例
   */
  validateTestCoverage(
    tasks: Task[],
    taskToTests: Map<string, string[]>
  ): Coverage;

  /**
   * 门禁检查
   * 返回是否通过及未覆盖项
   */
  checkGate(stage: string, coverage: Coverage): GateResult;
}

// 覆盖度接口
export interface Coverage {
  total: number;
  covered: number;
  uncovered: string[];
  rate: number;        // 0-100
}

// 门禁结果接口
export interface GateResult {
  passed: boolean;
  stage: string;
  coverage: Coverage;
  threshold: number;   // 门禁阈值（%）
  message?: string;    // 未通过时的错误消息
}
```

---

## 2. StageOverview API 增强 serves: FR-7
### 2.1 HTTP API serves: FR-7

**端点**：GET /api/stage-overview/:requirementId

**请求**：

```typescript
// 无请求体
```

**响应**：

```typescript
export interface StageOverviewResponse {
  requirement_id: string;
  title: string;
  category: string;
  current_stage: string;
  
  // 原有字段
  stages: Record<string, StageData>;
  
  // 新增：RTM 追溯数据
  traceability?: {
    fr_to_design?: Record<string, string[]>;
    design_to_tasks?: Record<string, string[]>;
    task_to_tests?: Record<string, string[]>;
  };
  
  // 新增：覆盖度统计
  coverage?: {
    design?: Coverage;
    implementation?: Coverage;
    testing?: Coverage;
  };
}

export interface StageData {
  status: string;
  body: string;
  // ... 其他原有字段
}
```

**错误响应**：

```typescript
export interface ErrorResponse {
  error: string;
  code: string;
  details?: any;
}

// 错误码
// - REQ_NOT_FOUND: 需求不存在
// - RTM_READ_ERROR: RTM 文件读取失败
// - RTM_PARSE_ERROR: RTM 文件解析失败
```

### 2.2 实现接口 serves: FR-2, FR-7

**位置**：agent-dh/packages/pmboard/src/api/stage-overview.ts

```typescript
export async function assembleStageOverview(
  reqId: string
): Promise<StageOverviewResponse> {
  // 1. 从台账组装基础数据
  const baseData = await assembleFromReqboard(reqId);
  
  // 2. 读取 RTM 追溯数据
  const currentStage = baseData.current_stage;
  const rtm = await readRTMWithFallback(
    `rtm-${currentStage}.yml`,
    reqId
  );
  
  // 3. 合并数据
  return {
    ...baseData,
    traceability: rtm.traceability,
    coverage: rtm.coverage,
  };
}

/**
 * 读取 RTM，失败时降级到实时生成
 */
async function readRTMWithFallback(
  file: string,
  reqId: string
): Promise<any> {
  try {
    return await readYAML(`${reqDir}/${file}`);
  } catch (error) {
    // 降级：实时生成
    const generator = new RTMGenerator({ reqboardPath, reqDir });
    await generator.generate(file, reqId);
    return await readYAML(`${reqDir}/${file}`);
  }
}
```

---

## 3. Dive 模式集成接口 serves: FR-8
### 3.1 节点输入包接口 serves: FR-8

**位置**：agent-dh/packages/pmboard/src/dive/node-input.ts

```typescript
export interface NodeInput {
  stage: string;
  requirement_id: string;
  previous_stage?: string;
  
  // RTM 数据
  status?: any;
  inputs?: any;
  outputs?: any;
  traceability?: any;
  coverage?: any;
  
  // 下一步建议
  next_action?: string;
}

export function assembleNodeInput(
  stage: string,
  reqId: string,
  mode: 'full' | 'compressed' = 'full'
): NodeInput {
  const lifecycle = readRTM('rtm-lifecycle.yml', reqId);
  const stageRTM = readRTM(`rtm-${stage}.yml`, reqId);
  
  if (mode === 'compressed') {
    return assembleCompressed(stage, reqId, stageRTM);
  }
  
  return {
    stage,
    requirement_id: reqId,
    previous_stage: lifecycle.previous_stage,
    status: stageRTM.status,
    inputs: stageRTM.inputs,
    outputs: stageRTM.outputs,
    traceability: stageRTM.traceability,
    coverage: stageRTM.coverage,
    next_action: generateNextAction(stageRTM),
  };
}

/**
 * 压缩模式：减少 90% token 消耗
 */
function assembleCompressed(
  stage: string,
  reqId: string,
  stageRTM: any
): NodeInput {
  if (stage === 'implementing') {
    return {
      stage,
      requirement_id: reqId,
      status: {
        progress: `${stageRTM.status.tasks_done}/${stageRTM.status.tasks_total} done`,
        current_tasks: stageRTM.task_details
          .filter((t: any) => t.status === 'in_progress')
          .map((t: any) => `${t.id}@${t.current_phase}`),
      },
      next_action: generateNextAction(stageRTM),
    };
  }
  
  // 其他节点类似压缩
  return { stage, requirement_id: reqId };
}
```

### 3.2 Dive 决策接口 serves: FR-8

**位置**：agent-dh/packages/pmboard/src/dive/decision.ts

```typescript
export interface DiveDecision {
  can_proceed: boolean;
  stage: string;
  next_stage?: string;
  reason: string;
  coverage?: Coverage;
  blockers?: string[];
}

export async function makeDiveDecision(
  stage: string,
  reqId: string
): Promise<DiveDecision> {
  const lifecycle = await readYAML(`${reqDir}/rtm-lifecycle.yml`);
  const stageRTM = await readYAML(`${reqDir}/rtm-${stage}.yml`);
  
  if (stage === 'design') {
    const coverage = stageRTM.coverage.design;
    if (coverage.rate === 100) {
      return {
        can_proceed: true,
        stage: 'design',
        next_stage: 'decomposing',
        reason: '所有 FR 都有设计，可以准备拆分',
        coverage,
      };
    } else {
      return {
        can_proceed: false,
        stage: 'design',
        reason: `还有 ${coverage.uncovered.length} 个 FR 缺少设计`,
        coverage,
        blockers: coverage.uncovered,
      };
    }
  }
  
  // 其他节点类似逻辑
  return { can_proceed: true, stage, reason: 'OK' };
}
```

---

## 4. 触发点集成接口 serves: FR-2
### 4.1 reqboard_submit 集成 serves: FR-2

**示例：提交设计文档**

```typescript
// agent-dh/packages/pmboard/src/tools/reqboard-submit.ts

export async function reqboardSubmit(args: {
  kind: string;
  requirement_id?: string;
  path?: string;
  // ... 其他参数
}) {
  // ... 原有逻辑 ...
  
  if (args.kind === 'design') {
    // 1. 生成 RTM
    const generator = new RTMGenerator({ reqboardPath, reqDir });
    const rtm = await generator.generateDesign(requirementId);
    
    // 2. 门禁检查
    const validator = new RTMValidator();
    const gateResult = validator.checkGate('design', rtm.coverage.design);
    
    if (!gateResult.passed) {
      return {
        success: false,
        error: gateResult.message,
        coverage: rtm.coverage.design,
      };
    }
    
    // 3. 通过后登记产物
    // ... 原有逻辑 ...
    
    return {
      success: true,
      design_docs: rtm.outputs.design_sections,
      coverage: rtm.coverage.design,
    };
  }
  
  // 其他 kind 类似处理
}
```

### 4.2 reqboard_task_move 集成 serves: FR-2

**示例：任务状态变更**

```typescript
// agent-dh/packages/pmboard/src/tools/reqboard-task-move.ts

export async function reqboardTaskMove(args: {
  task_id: string;
  to: string;
  reason?: string;
}) {
  // ... 原有逻辑：更新台账 ...
  
  // RTM 同步更新
  const generator = new RTMGenerator({ reqboardPath, reqDir });
  await generator.updateTaskStatus(
    requirementId,
    args.task_id,
    { status: args.to }
  );
  
  return {
    success: true,
    task_id: args.task_id,
    status: args.to,
  };
}
```

---

## 5. 错误码定义 serves: FR-9

```typescript
export enum RTMErrorCode {
  // 文件相关
  FILE_NOT_FOUND = 'RTM_FILE_NOT_FOUND',
  FILE_READ_ERROR = 'RTM_FILE_READ_ERROR',
  FILE_WRITE_ERROR = 'RTM_FILE_WRITE_ERROR',
  FILE_PARSE_ERROR = 'RTM_FILE_PARSE_ERROR',
  
  // 验证相关
  VALIDATION_FAILED = 'RTM_VALIDATION_FAILED',
  GATE_REJECTED = 'RTM_GATE_REJECTED',
  COVERAGE_INSUFFICIENT = 'RTM_COVERAGE_INSUFFICIENT',
  
  // 数据相关
  DATA_INCONSISTENT = 'RTM_DATA_INCONSISTENT',
  MAPPING_CONFLICT = 'RTM_MAPPING_CONFLICT',
  
  // 并发相关
  LOCK_TIMEOUT = 'RTM_LOCK_TIMEOUT',
  CONCURRENT_UPDATE = 'RTM_CONCURRENT_UPDATE',
}

export class RTMError extends Error {
  constructor(
    public code: RTMErrorCode,
    message: string,
    public details?: any
  ) {
    super(message);
    this.name = 'RTMError';
  }
}
```

---

## 6. 类型定义汇总 serves: FR-1

完整的 TypeScript 类型定义见 rtm-schema.md 文档，核心接口：

```typescript
// RTM 文件类型
export interface RTMLifecycle { ... }
export interface RTMBrainstorming { ... }
export interface RTMDesign { ... }
export interface RTMDecomposing { ... }
export interface RTMImplementing { ... }
export interface RTMAccepting { ... }

// 数据类型
export interface FR { ... }
export interface DesignSection { ... }
export interface Task { ... }
export interface TestCase { ... }

// 覆盖度类型
export interface Coverage { ... }
export interface GateResult { ... }

// 追溯关系类型
export type FRToDesign = Map<string, string[]>;
export type DesignToTasks = Map<string, string[]>;
export type TaskToTests = Map<string, string[]>;
```

---

## 验收口径 serves: FR-1, FR-2, FR-7, FR-8, FR-9
### 接口契约测试 serves: FR-2, FR-7, FR-8
serves: FR-1, FR-2

```bash
# TypeScript 类型检查
serves: FR-1
cd agent-dh
npm run typecheck

# 预期：无类型错误
serves: FR-1
```

### API 集成测试 serves: FR-7

```bash
# StageOverview API 测试
serves: FR-1
npm test -- stage-overview-api.test.ts

# 预期：
serves: FR-1
# ✓ 返回包含 traceability 字段
serves: FR-1
# ✓ 返回包含 coverage 字段
serves: FR-1
# ✓ RTM 缺失时降级到实时生成
serves: FR-1
```

### 触发点集成测试 serves: FR-2

```bash
# reqboard 工具集成测试
serves: FR-1
npm test -- reqboard-rtm-integration.test.ts

# 预期：
serves: FR-1
# ✓ reqboard_submit(design) 自动生成 RTM
serves: FR-1
# ✓ 覆盖度不足时门禁拒绝
serves: FR-1
# ✓ reqboard_task_move 自动更新 RTM
serves: FR-1
```

### Dive 模式集成测试 serves: FR-8

```bash
# Dive 决策接口测试
serves: FR-1
npm test -- dive-decision.test.ts

# 预期：
serves: FR-1
# ✓ 基于 RTM 覆盖度做决策
serves: FR-1
# ✓ 读取 RTM < 5ms
serves: FR-1
# ✓ 节点输入包正确注入
serves: FR-1
```
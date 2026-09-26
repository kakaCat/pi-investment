# 接口设计

## 1. RTMManager 核心接口（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
### 1.1 初始化接口（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**服务功能点**: FR-1

```typescript
interface RTMManager {
  /**
   * 初始化 RTM：扫描 FR 文件，生成 rtm.yaml
   * @param requirementId 需求 ID
   * @returns 初始化结果
   */
  init(requirementId: string): Promise<RTMInitResult>;
}

interface RTMInitResult {
  success: boolean;
  rtmFile: string;                    // rtm.yaml 文件路径
  functionalRequirements: FRMetadata[];  // 扫描到的 FR 列表
  error?: string;
}

interface FRMetadata {
  id: string;                         // FR-1, FR-2, ...
  file: string;                       // 文件相对路径
  title: string;                      // 从文件第一行提取
  priority: 'P0' | 'P1' | 'P2';      // 从 front-matter 提取
  acceptanceCriteria: AcceptanceCriterion[];  // 验收标准
}

interface AcceptanceCriterion {
  id: string;                         // FR-1-A1, FR-1-A2, ...
  description: string;                // 验收标准描述
  verification: string;               // 可证伪的验证方式
}
```

**错误码**：
- `FR_DIR_NOT_FOUND`: functional-requirements/ 目录不存在
- `NO_FR_FILES`: 目录为空，没有 FR 文件
- `FR_PARSE_ERROR`: FR 文件解析失败

---

### 1.2 校验接口（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**服务功能点**: FR-2

```typescript
interface RTMManager {
  /**
   * 校验 FR 文件完整性
   * @param requirementId 需求 ID
   * @returns 校验结果
   */
  validate(requirementId: string): Promise<RTMValidateResult>;
}

interface RTMValidateResult {
  success: boolean;
  frFilesExist: boolean;              // 所有 FR 文件是否存在
  missingFiles: string[];             // 缺失的文件列表
  incompleteFiles: IncompleteFR[];    // 缺少必要章节的文件
  unfalsifiableAcceptance: string[];  // 验收标准不可证伪的列表
}

interface IncompleteFR {
  file: string;                       // 文件路径
  missingSections: string[];          // 缺失的章节，如 ["5. 实施建议"]
}
```

**错误码**：
- `RTM_NOT_FOUND`: rtm.yaml 不存在（未初始化）
- `FR_FILE_NOT_FOUND`: FR 文件缺失
- `FR_INCOMPLETE`: FR 文件缺少必要章节

---

### 1.3 填充 task_coverage 接口（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**服务功能点**: FR-3

```typescript
interface RTMManager {
  /**
   * 填充任务覆盖关系
   * @param requirementId 需求 ID
   * @param tasks 任务列表
   * @returns 填充结果和覆盖度检查
   */
  addTaskCoverage(
    requirementId: string,
    tasks: TaskWithRefs[]
  ): Promise<TaskCoverageResult>;
}

interface TaskWithRefs {
  id: string;                         // 任务 ID（落库后）
  key: string;                        // 批次内键
  title: string;                      // 任务标题
  requirementRefs: string[];          // 接收的 FR 列表，如 ['FR-1', 'FR-2']
}

interface TaskCoverageResult {
  success: boolean;
  taskCoverage: TaskCoverageItem[];   // 填充的覆盖记录
  coverageCheck: CoverageCheck;       // 覆盖度检查结果
}

interface TaskCoverageItem {
  taskId: string;
  taskKey: string;
  taskTitle: string;
  coversFRs: string[];                // 接收的 FR
  coversAcceptance: string[];         // 接收的验收标准
  assignedAt: number;                 // 拆分时间戳
}

interface CoverageCheck {
  totalFRs: number;                   // 总 FR 数
  coveredFRs: number;                 // 已覆盖 FR 数
  unreceivedClauses: string[];        // 未被覆盖的 FR
  coverageRate: number;               // 覆盖率（%）
}
```

**错误码**：
- `RTM_NOT_FOUND`: rtm.yaml 不存在
- `INVALID_FR_REF`: 引用了不存在的 FR

---

### 1.4 追踪任务状态接口（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**服务功能点**: FR-4

```typescript
interface RTMManager {
  /**
   * 追踪任务状态变更
   * @param requirementId 需求 ID
   * @param taskId 任务 ID
   * @param status 新状态
   * @returns 更新结果
   */
  trackTaskStatus(
    requirementId: string,
    taskId: string,
    status: TaskStatus
  ): Promise<RTMUpdateResult>;
  
  /**
   * 更新 FR 文件第 7 章"接收状态"
   * @param requirementId 需求 ID
   * @param taskId 任务 ID
   * @param frIds 该任务接收的 FR 列表
   * @returns 更新结果
   */
  updateFRFileReceiveStatus(
    requirementId: string,
    taskId: string,
    frIds: string[]
  ): Promise<RTMUpdateResult>;
}

type TaskStatus = 'todo' | 'in_progress' | 'testing' | 'in_review' | 'done' | 'canceled';

interface RTMUpdateResult {
  success: boolean;
  updated: string[];                  // 更新的文件列表
  error?: string;
}
```

**错误码**：
- `TASK_NOT_FOUND`: 任务不在 task_coverage 中
- `FR_FILE_NOT_WRITABLE`: FR 文件不可写

---

### 1.5 填充 acceptance_tracking 接口（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**服务功能点**: FR-5

```typescript
interface RTMManager {
  /**
   * 填充验收追踪（提交验收时）
   * @param requirementId 需求 ID
   * @param evidence 证据清单
   * @returns 填充结果
   */
  fillAcceptanceTracking(
    requirementId: string,
    evidence: string[]
  ): Promise<AcceptanceTrackingResult>;
}

interface AcceptanceTrackingResult {
  success: boolean;
  acceptanceTracking: AcceptanceTrackingItem[];  // 填充的验收追踪
  totalAcceptance: number;            // 总验收项数
}

interface AcceptanceTrackingItem {
  acceptanceId: string;               // FR-1-A1, FR-1-A2, ...
  frId: string;                       // FR-1
  description: string;                // 验收标准描述
  verification: string;               // 验证方式
  status: 'pending' | 'passed' | 'failed';  // 初始为 pending
  evidence: string | null;            // 初始为 null
  judgedAt: number | null;            // 初始为 null
  judgedBy: string | null;            // 初始为 null
  userFeedback: string | null;        // 初始为 null
}
```

**错误码**：
- `RTM_NOT_FOUND`: rtm.yaml 不存在
- `NO_ACCEPTANCE_CRITERIA`: functional_requirements 中没有验收标准

---

### 1.6 更新 acceptance_tracking 接口（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**服务功能点**: FR-6

```typescript
interface RTMManager {
  /**
   * 更新验收追踪（人工审核时）
   * @param requirementId 需求 ID
   * @param judgments 裁决列表
   * @returns 更新结果和门禁检查
   */
  updateAcceptanceTracking(
    requirementId: string,
    judgments: AcceptanceJudgment[]
  ): Promise<AcceptanceUpdateResult>;
}

interface AcceptanceJudgment {
  acceptanceId: string;               // FR-1-A1
  status: 'passed' | 'failed';        // 裁决结果
  evidence?: string;                  // 证据（可选）
  userFeedback?: string;              // 失败时的反馈（可选）
  judgedBy: string;                   // 裁决人
}

interface AcceptanceUpdateResult {
  success: boolean;
  updated: number;                    // 更新的验收项数
  gateCheck: AcceptanceGateCheck;     // 门禁检查结果
}

interface AcceptanceGateCheck {
  totalAcceptance: number;            // 总验收项数
  passed: number;                     // 通过数
  failed: number;                     // 失败数
  pending: number;                    // 待审数
  passRate: number;                   // 通过率（%）
  gateStatus: 'passed' | 'blocked';   // 门禁状态
  blockReason?: string;               // 阻塞原因
  failedItems?: FailedAcceptanceItem[];  // 失败项列表
}

interface FailedAcceptanceItem {
  acceptanceId: string;
  description: string;
  userFeedback: string;
}
```

**错误码**：
- `ACCEPTANCE_NOT_FOUND`: 验收项不存在
- `INVALID_STATUS`: 状态值非法

---

### 1.7 查询接口（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**服务功能点**: FR-7

```typescript
interface RTMManager {
  /**
   * 查询 RTM 状态
   * @param requirementId 需求 ID
   * @param options 查询选项
   * @returns 查询结果
   */
  query(
    requirementId: string,
    options?: RTMQueryOptions
  ): Promise<RTMQueryResult>;
}

interface RTMQueryOptions {
  includeCoverage?: boolean;          // 是否包含覆盖度
  includeProgress?: boolean;          // 是否包含任务进度
  includeAcceptance?: boolean;        // 是否包含验收进度
  frId?: string;                      // 按 FR 过滤
}

interface RTMQueryResult {
  success: boolean;
  frCoverage?: FRCoverageItem[];      // FR 覆盖度列表
  taskProgress?: TaskProgressItem[];  // 任务进度列表（按 FR）
  acceptanceProgress?: AcceptanceProgressItem[];  // 验收进度列表
  unreceivedClauses?: string[];       // 未接收的 FR
  failedAcceptance?: string[];        // 验收未通过的项
}

interface FRCoverageItem {
  frId: string;                       // FR-1
  title: string;                      // FR 标题
  covered: boolean;                   // 是否被覆盖
  coveredBy: string[];                // 接收的任务 ID 列表
}

interface TaskProgressItem {
  frId: string;                       // FR-1
  totalTasks: number;                 // 该 FR 的总任务数
  completedTasks: number;             // 已完成任务数
  inProgressTasks: number;            // 进行中任务数
  progress: number;                   // 进度（%）
}

interface AcceptanceProgressItem {
  frId: string;                       // FR-1
  totalAcceptance: number;            // 该 FR 的总验收项数
  passed: number;                     // 已通过数
  failed: number;                     // 失败数
  pending: number;                    // 待审数
  passRate: number;                   // 通过率（%）
}
```

**错误码**：
- `RTM_NOT_FOUND`: rtm.yaml 不存在

---

## 2. FR File Parser 接口（serves: FR-1, FR-2, FR-4）
```typescript
interface FRFileParser {
  /**
   * 扫描 FR 文件
   * @param requirementDir 需求目录
   * @returns FR 文件路径列表
   */
  scanFRFiles(requirementDir: string): Promise<string[]>;
  
  /**
   * 解析 FR 文件
   * @param filePath FR 文件路径
   * @returns FR 元数据
   */
  parseFRFile(filePath: string): Promise<FRMetadata>;
  
  /**
   * 提取验收标准
   * @param filePath FR 文件路径
   * @returns 验收标准列表
   */
  extractAcceptanceCriteria(filePath: string): Promise<AcceptanceCriterion[]>;
  
  /**
   * 更新 FR 文件第 7 章
   * @param filePath FR 文件路径
   * @param taskId 任务 ID
   * @param taskTitle 任务标题
   * @returns 是否成功
   */
  updateSection7(
    filePath: string,
    taskId: string,
    taskTitle: string
  ): Promise<boolean>;
}
```

---

## 3. 工具集成接口修改（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
### 3.1 reqboard_create（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**修改内容**: 增加 RTM 初始化调用

```typescript
// 在 reqboard_create 的返回结果中增加
interface CreateResult {
  // ... 原有字段
  rtm?: {
    initialized: boolean;
    rtmFile: string;
    frCount: number;
  };
}
```

### 3.2 reqboard_submit(kind=design)（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**修改内容**: 增加 FR 文件校验

```typescript
// 在 reqboard_submit 的返回结果中增加
interface SubmitResult {
  // ... 原有字段
  designValidation?: {
    frFilesExist: boolean;
    missingFiles: string[];
    incompleteFiles: IncompleteFR[];
  };
}
```

### 3.3 reqboard_decompose（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**修改内容**: 增加 task_coverage 填充和覆盖度检查

```typescript
// 在 reqboard_decompose 的返回结果中增加
interface DecomposeResult {
  // ... 原有字段
  taskCoverage?: TaskCoverageItem[];
  coverageCheck?: CoverageCheck;
}
```

### 3.4 reqboard_status（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**修改内容**: 增加 RTM 查询信息

```typescript
// 在 reqboard_status 的返回结果中增加
interface StatusResult {
  // ... 原有字段
  frCoverage?: FRCoverageItem[];
  taskProgress?: TaskProgressItem[];
  acceptanceProgress?: AcceptanceProgressItem[];
}
```

---

**文档版本**: v1.0  
**最后更新**: 2026-09-25  
**作者**: Agent
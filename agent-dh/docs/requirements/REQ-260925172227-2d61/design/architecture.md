# 架构设计

## 1. 整体架构（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
### 1.1 核心模块（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
```
┌─────────────────────────────────────────────────────────────┐
│                    REQ 流水线（5 个阶段）                     │
├─────────────────────────────────────────────────────────────┤
│  brainstorming → design → decomposing → implementing → accepting │
│       ↓            ↓         ↓              ↓             ↓     │
│    RTM 初始化   RTM 校验  填充覆盖      追踪状态      填充验收  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      RTM Manager（新增）                      │
├─────────────────────────────────────────────────────────────┤
│  - init(): 扫描 FR 文件，生成 rtm.yaml                        │
│  - validate(): 校验 FR 文件完整性                             │
│  - addTaskCoverage(): 记录任务覆盖                            │
│  - trackTaskStatus(): 追踪任务状态                            │
│  - fillAcceptanceTracking(): 填充验收追踪                     │
│  - updateAcceptanceTracking(): 更新裁决                       │
│  - query(): 查询 RTM 状态                                     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      FR File Parser（新增）                   │
├─────────────────────────────────────────────────────────────┤
│  - scanFRFiles(): 扫描 functional-requirements/ 目录          │
│  - parseFRFile(): 解析 FR-*.md 提取元数据                     │
│  - extractAcceptanceCriteria(): 提取验收标准                  │
│  - updateFRFile(): 更新 FR 文件第 7 章                        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    rtm.yaml（持久化存储）                      │
├─────────────────────────────────────────────────────────────┤
│  - functional_requirements: FR 元数据                         │
│  - task_coverage: 任务覆盖关系                                │
│  - acceptance_tracking: 验收追踪                              │
│  - coverage_rules: 覆盖检查规则                               │
│  - acceptance_gate: 验收门禁                                  │
└─────────────────────────────────────────────────────────────┘
```

## 2. 模块职责（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
### 2.1 RTM Manager（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**职责**：RTM 的核心管理器，提供初始化、校验、填充、更新、查询能力

**位置**：`packages/web/dsh-pmboard/src/rtm/rtm-manager.ts`（新建）

**依赖**：
- FR File Parser（解析 FR 文件）
- yaml 库（读写 rtm.yaml）

### 2.2 FR File Parser（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**职责**：解析功能点独立文件，提取元数据和验收标准

**位置**：`packages/web/dsh-pmboard/src/rtm/fr-parser.ts`（新建）

**依赖**：
- fs 模块（读取文件）
- markdown 解析库（提取章节）

### 2.3 工具集成点（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**修改的工具**：
- `reqboard_create`: 调用 `RTMManager.init()`
- `reqboard_submit(design)`: 调用 `RTMManager.validate()`
- `reqboard_decompose`: 调用 `RTMManager.addTaskCoverage()`
- `reqboard_task_move`: 调用 `RTMManager.trackTaskStatus()`
- `reqboard_submit(verification)`: 调用 `RTMManager.fillAcceptanceTracking()`
- `reqboard_accept_sheet`: 调用 `RTMManager.updateAcceptanceTracking()`
- `reqboard_status`: 调用 `RTMManager.query()`

## 3. 数据流（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6）
```
需求创建 (reqboard_create)
    ↓
  扫描 FR 文件
    ↓
  生成 rtm.yaml (初始化 functional_requirements)
    ↓
设计提交 (reqboard_submit kind=design)
    ↓
  校验 FR 文件完整性
    ↓
任务拆分 (reqboard_decompose)
    ↓
  填充 task_coverage (任务→FR 映射)
    ↓
  校验覆盖度 (unreceived_clauses)
    ↓
任务执行 (reqboard_task_move)
    ↓
  更新任务状态到 task_coverage
    ↓
验收提交 (reqboard_submit kind=verification)
    ↓
  填充 acceptance_tracking (status=pending)
    ↓
人工审核 (reqboard_accept_sheet)
    ↓
  更新 acceptance_tracking (status=passed/failed)
    ↓
  检查验收门禁 (pass_rate=100%?)
    ↓
  自动归档
```

## 4. 文件结构（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
### 4.1 新建文件（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
```
packages/web/dsh-pmboard/src/rtm/
├── rtm-manager.ts          (RTM 核心管理器)
├── fr-parser.ts            (FR 文件解析器)
├── rtm-types.ts            (TypeScript 类型定义)
└── rtm-validator.ts        (校验逻辑)
```

### 4.2 修改文件（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
```
packages/web/dsh-pmboard/src/reqboard/
├── create.ts               (增加 RTM 初始化调用)
├── submit.ts               (增加 design 校验、verification 填充)
├── decompose.ts            (增加 task_coverage 填充)
├── task-move.ts            (增加状态追踪)
├── accept-sheet.ts         (增加 acceptance_tracking 更新)
└── status.ts               (增加 RTM 查询)
```

### 4.3 不修改文件（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
- 需求数据模型（`dsh-reqboard.json`）：在现有结构内扩展，不改 schema

## 5. 技术选型（serves: FR-1, FR-2, FR-7）
### 5.1 YAML 解析（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**选择**：`js-yaml` 库

**理由**：
- 标准 YAML 解析库
- 支持注释（rtm.yaml 需要注释说明）
- 性能足够

### 5.2 Markdown 解析（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**选择**：`remark` / `unified`

**理由**：
- 提取 FR 文件的章节结构
- 标准 Markdown AST
- 可扩展

### 5.3 文件系统（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**选择**：Node.js 原生 `fs`

**理由**：
- 工具运行在 Node 环境
- 无需额外依赖

## 6. 性能考虑（serves: FR-1, FR-3, FR-7）
### 6.1 FR 文件扫描（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**优化**：
- 首次扫描后缓存结果
- 增量更新（只扫描变更的文件）

**预期**：扫描 10 个 FR 文件 < 500ms

### 6.2 RTM 查询（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**优化**：
- 内存缓存 rtm.yaml
- 按需加载（不一次性加载所有数据）

**预期**：查询响应时间 < 100ms

## 7. 错误处理（serves: FR-1, FR-2, FR-3）
### 7.1 FR 文件缺失（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**场景**：rtm.yaml 引用的 FR 文件不存在

**处理**：
- 校验时报错：`FR_FILE_NOT_FOUND`
- 返回缺失文件列表
- 阻止推进到拆分阶段

### 7.2 YAML 解析失败（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**场景**：rtm.yaml 格式错误

**处理**：
- 捕获解析异常
- 返回错误行号和原因
- 提示修复建议

### 7.3 覆盖度不足（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**场景**：有 FR 未被任务覆盖

**处理**：
- 返回 `unreceived_clauses` 列表
- 不阻止拆分（警告级别）
- 由人工决定是否补充任务

## 8. 扩展性（serves: FR-7）
### 8.1 支持其他文件格式（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**当前**：只支持 Markdown

**扩展点**：`fr-parser.ts` 的 `parseFRFile()` 方法

**未来**：可支持 YAML、JSON 格式的 FR 文件

### 8.2 支持自定义校验规则（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**当前**：固定的 `coverage_rules`

**扩展点**：`rtm-validator.ts` 的规则引擎

**未来**：允许用户自定义校验规则

---

**文档版本**: v1.0  
**最后更新**: 2026-09-25  
**作者**: Agent
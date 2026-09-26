/**
 * RTM YAML 类型契约（REQ-260926140539-457b FR-1）。
 *
 * 本文件是 RTM YAML 基础设施的**唯一类型事实源**：7 个 YAML 文件
 * （rtm-lifecycle + 6 个节点 + rtm-implementing/ 任务详情）的结构、四级追溯映射
 * （FR → 设计 → 任务 → 测试）与三层覆盖度统计全部在此定义，供生成器、解析器、
 * 校验器与 StageOverview 读取器共用。
 *
 * 设计依据：docs/requirements/REQ-260926140539-457b/design/rtm-schema.md、data-model.md。
 *
 * @module @pi-investment/reqboard/rtm/types
 */

/** 流水线阶段（与 dsh-pmboard 状态机一致）。 */
export type RTMStageName =
  | 'draft'
  | 'brainstorming'
  | 'design'
  | 'decomposing'
  | 'implementing'
  | 'accepting'
  | 'done'

/** 节点固定顺序（生成 lifecycle 骨架与判断"当前阶段"用）。 */
export const RTM_STAGE_ORDER: readonly RTMStageName[] = [
  'draft',
  'brainstorming',
  'design',
  'decomposing',
  'implementing',
  'accepting',
  'done',
] as const

/** 阶段状态（lifecycle 文件用）。 */
export type RTMStageStatus = 'pending' | 'in_progress' | 'completed' | 'skipped'

/** 子任务阶段（implementing 任务详情的 workflow）。 */
export type WorkflowPhase =
  | 'doc'
  | 'ui'
  | 'analysis'
  | 'implement'
  | 'test'
  | 'review'
  | 'commit'

/** 子任务阶段状态。 */
export type WorkflowStatus = 'pending' | 'in_progress' | 'done' | 'skipped' | 'failed'

/** 完整任务（fullstack）的子阶段顺序。 */
export const FULL_WORKFLOW: readonly WorkflowPhase[] = [
  'doc',
  'ui',
  'analysis',
  'implement',
  'test',
  'review',
  'commit',
] as const

/** 所有 RTM YAML 文件共有的元数据块。 */
export interface RTMMetadata {
  /** 节点名（rtm-<stage>.yml 用）。 */
  stage?: string
  /** 所属需求 id（REQ-xxxxxx）。 */
  requirement_id?: string
  /** 首次生成时间（ISO 8601）。 */
  generated_at?: string
  /** 最后更新时间（ISO 8601）。 */
  last_updated?: string
  /** 版本号：每次写入 +1（FR-6 版本追踪）。 */
  version: number
  /** Schema 版本（lifecycle 用）。 */
  rtm_version?: string
  /** 生成器标识。 */
  generated_by?: string
  /** 任务详情目录（implementing 汇总文件用）。 */
  detail_dir?: string
  /** 本 RTM 文件的**绝对路径**（自定位；调用方不必知道工作区根）。 */
  file_path?: string
  /** 任务详情文件数量（implementing 汇总文件用）。 */
  detail_count?: number
  [k: string]: unknown
}

/** 功能需求点（从 requirement.md 解析）。 */
export interface FR {
  id: string
  title: string
  source: string
  line: number
}

/** 设计章节（从 design/*.md 解析）。 */
export interface DesignSection {
  /** 稳定引用，如 design/architecture.md#1.1 */
  ref: string
  title: string
  /** 本章节服务哪些 FR。 */
  serves: string[]
  file: string
  section: string
}

/** 测试用例（从测试文档解析）。 */
export interface TestCase {
  id: string
  title: string
  /** 覆盖哪些任务（covers: t-xxx）。 */
  covers: string[]
  /** 验证哪些 FR（validates: FR-x）。 */
  validates: string[]
  source?: string
}

/** 覆盖度统计（通用四元组）。 */
export interface Coverage {
  total: number
  covered: number
  uncovered: string[]
  /** 0-100 的整数百分比。 */
  rate: number
}

/** 设计覆盖度（FR 视角，额外带 *_frs 字段以对齐 data-model.md）。 */
export interface DesignCoverage extends Coverage {
  total_frs: number
  covered_frs: number
}

/** 实施覆盖度（设计章节视角）。 */
export interface ImplementationCoverage extends Coverage {
  total_designs: number
  covered_designs: number
}

/** 测试覆盖度（任务视角）。 */
export interface TestingCoverage extends Coverage {
  total_tasks: number
  tested_tasks: number
  /** 无测试用例的任务（= uncovered 的语义别名，data-model.md 用这个名字）。 */
  untested: string[]
}

/** 覆盖度门禁裁决结果。 */
export interface GateResult {
  passed: boolean
  stage: string
  coverage: Coverage
  /** 门禁阈值（百分比）。 */
  threshold: number
  message?: string
}

/** 四级追溯映射集合。 */
export interface Traceability {
  fr_to_design?: Record<string, string[]>
  design_to_tasks?: Record<string, string[]>
  fr_to_tasks?: Record<string, string[]>
  task_to_tests?: Record<string, string[]>
  fr_to_tests?: Record<string, string[]>
}

/** 台账中一条任务的**最小只读投影**（生成器只需要这些字段）。 */
export interface RTMTaskLike {
  id: string
  title?: string
  status?: string
  phase?: string
  side?: string
  depends_on?: string[]
  /** 直接实现的设计章节引用。 */
  implements?: string
  /** 服务/覆盖的 FR 列表。 */
  serves?: string[]
}

/** rtm-lifecycle.yml 里某个阶段的历史记录。 */
export interface LifecycleStageEntry {
  stage: string
  status: RTMStageStatus
  /**
   * 本需求的分类档案是否启用该节点（false = 档案跳过它，看板标灰"本分类跳过"）。
   * 为什么写进文件：非 feature 分类的档案不含 brainstorming，但 draft 的唯一前向转移就是
   * brainstorming → 需求会被推进一个**自己档案里没有的节点**；把它显式标出来，读者一眼能看见。
   */
  enabled?: boolean
  entered_at?: string
  completed_at?: string
  artifacts?: LifecycleArtifact[]
}

/** lifecycle 阶段下挂的产物留痕。 */
export interface LifecycleArtifact {
  kind: string
  path?: string
  confirmed_at?: string
  approved_at?: string
  count?: number
}

/** rtm-lifecycle.yml（全局生命周期）。 */
export interface RTMLifecycle {
  requirement: {
    id: string
    title: string
    category: string
    created_at: string
    /**
     * 立项绑定窗口（台账 `sourceSessionId` 的投影）——"窗口↔需求"的需求侧锚点。
     * 为什么放进本文件：Dive 模式唤醒要知道**把消息投给哪个窗口**，绑定窗口必须与
     * 节点状态一起出现在同一份快照里（否则还要回头查台账）。缺省 = 未绑定窗口。
     */
    source_session?: string
    /**
     * 需求目录**绝对路径**（`docs/requirements/<REQ>`）。
     * 读这份快照的一方（Dive / 会话节点）不必先知道工作区根在哪就能定位需求目录——
     * 与「立项回执给绝对路径」同一口径（用户反馈过"不知道绝对路径是哪里"）。
     */
    dir?: string
  }
  lifecycle: {
    current_stage: string
    /** 本需求**有多少个节点**（= 分类档案启用的节点数，按 RTM 口径归一）。 */
    stage_count?: number
    /** 本需求的节点清单（顺序 = 流水线顺序；只含启用的）。 */
    stage_list?: string[]
    stages: LifecycleStageEntry[]
  }
  metadata: RTMMetadata
}

/** rtm-brainstorming.yml（需求分析节点）。 */
export interface RTMBrainstorming {
  metadata: RTMMetadata
  outputs: {
    requirements: FR[]
  }
  status?: {
    artifacts: Array<{
      kind: string
      path: string
      confirmed: boolean
      confirmed_at?: string
    }>
  }
}

/** rtm-design.yml（设计节点）。 */
export interface RTMDesign {
  metadata: RTMMetadata
  inputs: {
    requirements: FR[]
  }
  outputs: {
    design_sections: DesignSection[]
  }
  traceability: {
    fr_to_design: Record<string, string[]>
  }
  coverage: {
    design: DesignCoverage
  }
}

/** rtm-decomposing.yml（拆分节点）。 */
export interface RTMDecomposing {
  metadata: RTMMetadata
  inputs: {
    requirements: FR[]
    design_sections: DesignSection[]
  }
  outputs: {
    tasks: Array<{
      id: string
      title: string
      implements: string
      serves: string[]
      depends_on: string[]
      phase: string
      side: string
    }>
  }
  traceability: {
    design_to_tasks: Record<string, string[]>
    fr_to_tasks: Record<string, string[]>
  }
  coverage: {
    implementation: ImplementationCoverage
  }
}

/** 任务详情文件里的一个子阶段记录。 */
export interface WorkflowStep {
  phase: WorkflowPhase
  status: WorkflowStatus
  started_at?: string
  completed_at?: string
  skip_reason?: string
  steps_completed?: Array<{ action: string; output?: string; files_changed?: string[]; commit?: string }>
}

/** rtm-implementing/t-xxx.yml（单任务详情）。 */
export interface RTMTaskDetail {
  task: {
    id: string
    title: string
    status: string
    implements: string
    serves: string[]
    depends_on: string[]
    phase: string
    side: string
    workflow_params: Record<string, string>
    workflow_total: number
    workflow_done: number
    workflow: WorkflowStep[]
  }
  metadata: RTMMetadata
}

/** rtm-implementing.yml（实施汇总，轻量）。 */
export interface RTMImplementing {
  metadata: RTMMetadata
  inputs: {
    tasks: Array<{ id: string; title: string; status: string }>
  }
  status: {
    tasks_total: number
    tasks_done: number
    tasks_in_progress: number
    tasks_todo: number
  }
  tasks: Array<{ id: string; status: string; [k: string]: unknown }>
}

/** rtm-accepting.yml（验收节点）。 */
export interface RTMAccepting {
  metadata: RTMMetadata
  inputs: {
    tasks: Array<{ id: string; title: string; status: string }>
  }
  outputs: {
    test_cases: TestCase[]
  }
  traceability: {
    task_to_tests: Record<string, string[]>
    fr_to_tests: Record<string, string[]>
  }
  coverage: {
    testing: TestingCoverage
  }
}

/** StageOverview 会话节点要展示的追溯块（FR-7）。 */
export interface StageOverviewTraceability {
  traceability: Traceability
  coverage: {
    design?: DesignCoverage
    implementation?: ImplementationCoverage
    testing?: TestingCoverage
  }
}

/** 写 RTM 时的可选参数。 */
export interface RTMWriteOptions {
  /** false = 不自动 +1（默认 true）。 */
  bumpVersion?: boolean
  /** 强制指定版本号。 */
  version?: number
  /** 覆盖 last_updated。 */
  now?: string
  generatedBy?: string
}

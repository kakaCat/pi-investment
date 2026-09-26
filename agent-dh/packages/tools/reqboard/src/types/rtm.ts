/**
 * RTM (Requirements Traceability Matrix) 类型定义
 * 用于追踪需求从分析到验收的完整生命周期
 */

// ============================================================
// 基础元数据类型
// ============================================================

/** RTM 元数据（所有 RTM 文件共有） */
export interface RtmMetadata {
  /** 阶段名称 */
  stage: 'lifecycle' | 'brainstorming' | 'design' | 'decomposing' | 'implementing' | 'accepting';
  /** 需求 ID */
  requirement_id: string;
  /** 生成时间 */
  generated_at?: string;
  /** 版本号 */
  version?: number;
  /** 生成者 */
  generated_by?: string;
  /** 最后更新时间 */
  last_updated?: string;
  /** 详情目录（implementing 阶段专用） */
  detail_dir?: string;
  /** 详情文件数量（implementing 阶段专用） */
  detail_count?: number;
}

/** 需求基本信息 */
export interface RequirementInfo {
  /** 需求 ID */
  id: string;
  /** 需求标题 */
  title: string;
  /** 需求类型 */
  category: string;
  /** 创建时间 */
  created_at: string;
  /** 来源会话 */
  source_session?: string;
  /** 需求目录 */
  dir: string;
}

/** 阶段状态 */
export type StageStatus = 'pending' | 'in_progress' | 'completed';

/** 产物信息 */
export interface Artifact {
  /** 产物类型 */
  kind: 'requirement' | 'design' | 'plan' | 'verification';
  /** 文件路径 */
  path: string;
  /** 是否已确认 */
  confirmed?: boolean;
  /** 确认时间 */
  confirmed_at?: string;
}

// ============================================================
// rtm-lifecycle.yml 类型
// ============================================================

/** 阶段详情 */
export interface StageDetail {
  /** 阶段名称 */
  stage: string;
  /** 阶段状态 */
  status: StageStatus;
  /** 是否启用 */
  enabled: boolean;
  /** 进入时间 */
  entered_at?: string;
  /** 完成时间 */
  completed_at?: string;
  /** 产物列表 */
  artifacts?: Artifact[];
}

/** 生命周期信息 */
export interface Lifecycle {
  /** 当前阶段 */
  current_stage: string;
  /** 阶段数量 */
  stage_count: number;
  /** 阶段列表 */
  stage_list: string[];
  /** 阶段详情 */
  stages: StageDetail[];
}

/** rtm-lifecycle.yml 根结构 */
export interface RtmLifecycle {
  /** 需求信息 */
  requirement: RequirementInfo;
  /** 生命周期信息 */
  lifecycle: Lifecycle;
  /** 元数据 */
  metadata: RtmMetadata;
}

// ============================================================
// rtm-brainstorming.yml 类型
// ============================================================

/** FR（功能需求）定义 */
export interface FRItem {
  /** FR ID（如 FR-1） */
  id: string;
  /** FR 标题 */
  title: string;
  /** 源文件位置（如 requirement.md#120） */
  source: string;
  /** 优先级（可选） */
  priority?: string;
  /** 验收标准（可选） */
  acceptance_criteria?: {
    id: string;
    description: string;
    verification: string;
  }[];
}

/** rtm-brainstorming.yml 根结构 */
export interface RtmBrainstorming {
  /** 元数据 */
  metadata: RtmMetadata;
  /** 输出：需求列表 */
  outputs: {
    requirements: FRItem[];
  };
  /** 状态：产物信息 */
  status?: {
    artifacts: Artifact[];
  };
}

// ============================================================
// rtm-design.yml 类型
// ============================================================

/** 设计章节 */
export interface DesignSection {
  /** 章节引用（如 design/arch#1.1） */
  ref: string;
  /** 章节标题 */
  title: string;
  /** 服务的 FR 列表 */
  serves: string[];
  /** 源文件路径（可选） */
  source?: string;
}

/** 设计覆盖度 */
export interface DesignCoverage {
  /** 总数（章节总数） */
  total: number;
  /** 已覆盖数 */
  covered: number;
  /** 未覆盖列表 */
  uncovered: string[];
  /** 覆盖率（百分比） */
  rate: number;
  /** FR 总数 */
  total_frs: number;
  /** 已覆盖的 FR 数 */
  covered_frs: number;
}

/** FR 到设计的追溯映射 */
export interface FrToDesignMap {
  [frId: string]: string[]; // FR-1 -> ["design/arch#1.1", "design/arch#1.2"]
}

/** rtm-design.yml 根结构 */
export interface RtmDesign {
  /** 元数据 */
  metadata: RtmMetadata;
  /** 输入：需求列表 */
  inputs: {
    requirements: FRItem[];
  };
  /** 输出：设计章节 */
  outputs: {
    design_sections: DesignSection[];
  };
  /** 追溯关系 */
  traceability: {
    fr_to_design: FrToDesignMap;
  };
  /** 覆盖度 */
  coverage: {
    design: DesignCoverage;
  };
}

// ============================================================
// rtm-decomposing.yml 类型
// ============================================================

/** 任务定义 */
export interface TaskItem {
  /** 任务 ID */
  id: string;
  /** 任务标题 */
  title: string;
  /** 实现的设计章节 */
  implements: string;
  /** 服务的 FR 列表 */
  serves: string[];
  /** 依赖的任务 */
  depends_on: string[];
  /** 任务阶段 */
  phase: string;
  /** 前端/后端 */
  side: string;
}

/** 实施覆盖度 */
export interface ImplementationCoverage {
  /** 总数（设计章节总数） */
  total: number;
  /** 已覆盖数 */
  covered: number;
  /** 未覆盖列表 */
  uncovered: string[];
  /** 覆盖率 */
  rate: number;
  /** 设计总数 */
  total_designs: number;
  /** 已覆盖的设计数 */
  covered_designs: number;
}

/** 设计到任务的追溯映射 */
export interface DesignToTasksMap {
  [designRef: string]: string[]; // "design/arch#1.1" -> ["t-354ea0"]
}

/** FR 到任务的追溯映射 */
export interface FrToTasksMap {
  [frId: string]: string[]; // FR-1 -> ["t-354ea0", "t-abc123"]
}

/** rtm-decomposing.yml 根结构 */
export interface RtmDecomposing {
  /** 元数据 */
  metadata: RtmMetadata;
  /** 输入 */
  inputs: {
    requirements: FRItem[];
    design_sections: DesignSection[];
  };
  /** 输出：任务列表 */
  outputs: {
    tasks: TaskItem[];
  };
  /** 追溯关系 */
  traceability: {
    design_to_tasks: DesignToTasksMap;
    fr_to_tasks: FrToTasksMap;
  };
  /** 覆盖度 */
  coverage: {
    implementation: ImplementationCoverage;
  };
}

// ============================================================
// rtm-implementing.yml 类型
// ============================================================

/** 任务简要信息（汇总文件中使用） */
export interface TaskBrief {
  /** 任务 ID */
  id: string;
  /** 任务状态 */
  status: 'todo' | 'in_progress' | 'done';
}

/** 任务执行状态 */
export interface TaskExecutionStatus {
  /** 任务总数 */
  tasks_total: number;
  /** 已完成任务数 */
  tasks_done: number;
  /** 进行中任务数 */
  tasks_in_progress: number;
  /** 待办任务数 */
  tasks_todo: number;
}

/** rtm-implementing.yml 根结构（汇总文件） */
export interface RtmImplementing {
  /** 元数据 */
  metadata: RtmMetadata;
  /** 输入：任务列表 */
  inputs: {
    tasks: TaskItem[];
  };
  /** 状态 */
  status: TaskExecutionStatus;
  /** 任务简要列表 */
  tasks: TaskBrief[];
}

/** 子阶段状态 */
export interface SubphaseStatus {
  /** 子阶段名称 */
  phase: 'doc' | 'ui' | 'analysis' | 'implement' | 'test' | 'review' | 'commit';
  /** 状态 */
  status: 'pending' | 'in_progress' | 'done';
  /** 开始时间 */
  started_at?: string;
  /** 完成时间 */
  completed_at?: string;
}

/** 单个任务详情文件（rtm-implementing/t-xxx.yml） */
export interface RtmTaskDetail {
  /** 任务信息 */
  task: {
    id: string;
    title: string;
    status: 'todo' | 'in_progress' | 'done';
    implements: string;
    serves: string[];
    /** Workflow 总数 */
    workflow_total: number;
    /** Workflow 已完成数 */
    workflow_done: number;
    /** Workflow 详情 */
    workflow: SubphaseStatus[];
  };
}

// ============================================================
// rtm-accepting.yml 类型
// ============================================================

/** 测试用例 */
export interface TestCase {
  /** 测试用例 ID */
  id: string;
  /** 测试标题 */
  title: string;
  /** 覆盖的任务 */
  covers: string[];
  /** 验证的 FR */
  validates: string[];
}

/** 测试覆盖度 */
export interface TestingCoverage {
  /** 任务总数 */
  total_tasks: number;
  /** 已测试任务数 */
  tested_tasks: number;
  /** 未测试任务列表 */
  untested: string[];
  /** 覆盖率 */
  rate: number;
}

/** 任务到测试的追溯映射 */
export interface TaskToTestsMap {
  [taskId: string]: string[]; // "t-354ea0" -> ["TC-1", "TC-2"]
}

/** rtm-accepting.yml 根结构 */
export interface RtmAccepting {
  /** 元数据 */
  metadata: RtmMetadata;
  /** 输出：测试用例 */
  outputs: {
    test_cases: TestCase[];
  };
  /** 追溯关系 */
  traceability: {
    task_to_tests: TaskToTestsMap;
  };
  /** 覆盖度 */
  coverage: {
    testing: TestingCoverage;
  };
}

// ============================================================
// 统一的 RTM 类型（用于泛型函数）
// ============================================================

/** 所有 RTM 文件的联合类型 */
export type AnyRtm = 
  | RtmLifecycle 
  | RtmBrainstorming 
  | RtmDesign 
  | RtmDecomposing 
  | RtmImplementing 
  | RtmAccepting;

/** RTM 阶段名称类型 */
export type RtmStage = 'lifecycle' | 'brainstorming' | 'design' | 'decomposing' | 'implementing' | 'accepting';

/** RTM 文件名映射 */
export const RTM_FILENAMES: Record<RtmStage, string> = {
  lifecycle: 'rtm-lifecycle.yml',
  brainstorming: 'rtm-brainstorming.yml',
  design: 'rtm-design.yml',
  decomposing: 'rtm-decomposing.yml',
  implementing: 'rtm-implementing.yml',
  accepting: 'rtm-accepting.yml',
};

// ============================================================
// 遗留类型（向后兼容）
// ============================================================

/**
 * 任务覆盖追踪（遗留）
 * 记录哪个任务接收了哪些功能需求
 */
export interface TaskCoverage {
  task_id: string;
  task_key: string;
  task_title: string;
  covers_frs: string[];
  covers_acceptance: string[];
  assigned_at: number;
  status?: 'todo' | 'in_progress' | 'integrating' | 'testing' | 'in_review' | 'done' | 'canceled';
  started_at?: number;
  completed_at?: number;
}

/**
 * 验收追踪（遗留）
 */
export interface AcceptanceTracking {
  acceptance_id: string;
  fr_id: string;
  description?: string;
  verification?: string;
  status: 'pending' | 'passed' | 'failed';
  evidence?: string | null;
  judged_at?: number | null;
  judged_by?: string | null;
  user_feedback?: string | null;
}

/**
 * 覆盖度检查规则（遗留）
 */
export interface CoverageRule {
  rule: string;
  check: string;
  enabled?: boolean;
}

/**
 * 验收门禁（遗留）
 */
export interface AcceptanceGate {
  pass_condition: string;
  fail_action: string;
  auto_archive: boolean;
  archive_condition?: string;
}

/**
 * FR 元数据（遗留）
 */
export interface FRMetadata {
  id: string;
  title: string;
  priority: string;
  file: string;
  acceptance_criteria: {
    id: string;
    description: string;
    verification: string;
  }[];
}

/**
 * RTM 数据结构（遗留）
 */
export interface RTMData {
  functional_requirements?: FRMetadata[];
  task_coverage?: TaskCoverage[];
  acceptance_tracking?: AcceptanceTracking[];
  coverage_rules?: CoverageRule[];
  acceptance_gate?: AcceptanceGate;
}

/**
 * RTM (Requirements Traceability Matrix) 类型定义
 * 用于追踪需求从分析到验收的完整生命周期
 */

/**
 * 任务覆盖追踪
 * 记录哪个任务接收了哪些功能需求
 */
export interface TaskCoverage {
  /** 任务 ID（如 t-xxx） */
  task_id: string;
  
  /** 批次内任务键（如 t1） */
  task_key: string;
  
  /** 任务标题 */
  task_title: string;
  
  /** 接收的功能需求列表（如 ['FR-1', 'FR-2']） */
  covers_frs: string[];
  
  /** 接收的验收标准列表（如 ['FR-1-A1', 'FR-1-A2']） */
  covers_acceptance: string[];
  
  /** 分配时间戳（毫秒） */
  assigned_at: number;
  
  /** 任务状态（可选，用于追踪） */
  status?: 'todo' | 'in_progress' | 'integrating' | 'testing' | 'in_review' | 'done' | 'canceled';
  
  /** 任务开始时间戳（可选） */
  started_at?: number;
  
  /** 任务完成时间戳（可选） */
  completed_at?: number;
}

/**
 * 验收追踪
 * 记录每个验收标准的验收状态
 */
export interface AcceptanceTracking {
  /** 验收标准 ID（如 FR-1-A1） */
  acceptance_id: string;
  
  /** 所属功能需求 ID（如 FR-1） */
  fr_id: string;
  
  /** 验收标准描述 */
  description?: string;
  
  /** 验证方式（可证伪的验证步骤） */
  verification?: string;
  
  /** 验收状态 */
  status: 'pending' | 'passed' | 'failed';
  
  /** 验收证据（测试结果、截图路径等） */
  evidence?: string | null;
  
  /** 裁决时间戳（毫秒） */
  judged_at?: number | null;
  
  /** 裁决人（用户 ID 或 agent ID） */
  judged_by?: string | null;
  
  /** 用户反馈（失败时的改进意见） */
  user_feedback?: string | null;
}

/**
 * 覆盖度检查规则
 * 定义需求覆盖度的校验规则
 */
export interface CoverageRule {
  /** 规则名称（唯一标识） */
  rule: string;
  
  /** 规则描述（人类可读） */
  check: string;
  
  /** 是否启用（默认 true） */
  enabled?: boolean;
}

/**
 * 验收门禁
 * 定义验收通过的条件和失败处理
 */
export interface AcceptanceGate {
  /** 通过条件（如 "所有 status 必须为 passed"） */
  pass_condition: string;
  
  /** 失败处理动作（如 "生成 rework_tasks"） */
  fail_action: string;
  
  /** 是否自动归档（通过门禁后自动推进到 archived） */
  auto_archive: boolean;
  
  /** 归档条件（可选，默认等同于 pass_condition） */
  archive_condition?: string;
}

/**
 * FR 元数据（从 FR 文件解析得到）
 */
export interface FRMetadata {
  /** FR ID（如 FR-1） */
  id: string;
  
  /** FR 标题 */
  title: string;
  
  /** 优先级（P0/P1/P2） */
  priority: string;
  
  /** 文件路径 */
  file: string;
  
  /** 验收标准列表 */
  acceptance_criteria: {
    /** 验收标准 ID（如 FR-1-A1） */
    id: string;
    /** 描述 */
    description: string;
    /** 验证方式 */
    verification: string;
  }[];
}

/**
 * RTM 数据结构（扩展到 RequirementData）
 */
export interface RTMData {
  /** 功能需求清单 */
  functional_requirements?: FRMetadata[];
  
  /** 任务覆盖追踪 */
  task_coverage?: TaskCoverage[];
  
  /** 验收追踪 */
  acceptance_tracking?: AcceptanceTracking[];
  
  /** 覆盖度检查规则 */
  coverage_rules?: CoverageRule[];
  
  /** 验收门禁 */
  acceptance_gate?: AcceptanceGate;
}

/**
 * Agent-DH 工具框架核心类型定义
 *
 * 本文件只定义类型，不包含任何实现逻辑
 */

// ============ 错误类型 ============

/**
 * 错误类型枚举
 */
export enum ErrorType {
  /** 入参格式/类型错误 */
  INPUT_ERROR = 'INPUT_ERROR',
  /** 必填参数缺失 */
  INPUT_EMPTY = 'INPUT_EMPTY',
  /** 后端数据结构异常 */
  OUTPUT_ERROR = 'OUTPUT_ERROR',
  /** 查询无结果 */
  OUTPUT_EMPTY = 'OUTPUT_EMPTY',
  /** 违反业务规则 */
  BUSINESS_REJECTION = 'BUSINESS_REJECTION',
  /** 场景不匹配 */
  TOOL_NOT_APPLICABLE = 'TOOL_NOT_APPLICABLE',
  /** 工具执行异常 */
  EXECUTION_ERROR = 'EXECUTION_ERROR',
  /** 执行超时 */
  TIMEOUT = 'TIMEOUT',
}

// ============ 校验结果 ============

/**
 * 校验结果接口
 */
export interface ValidationResult {
  /** 是否通过校验 */
  success: boolean;
  /** 错误类型 */
  errorType?: ErrorType;
  /** 涉及的字段 */
  field?: string;
  /** 问题描述 */
  issue?: string;
  /** 接收到的值 */
  received?: any;
  /** 期望的值/格式 */
  expected?: any;
  /** 示例 */
  example?: any;
  /** 引导说明 */
  guide?: string;
  /** 业务上下文 */
  businessContext?: {
    why: string;
    impact: string;
  };
  /** 常见错误 */
  commonMistakes?: string[];
  /** 可能的原因列表 */
  possibleReasons?: string[];
  /** 替代方案 */
  alternatives?: AlternativeAction[];
  /** 缺失的字段列表 */
  missingFields?: Array<{
    field: string;
    description: string;
    impact: string;
  }>;
  /** 业务规则名 */
  rule?: string;
  /** 解决方案列表 */
  solutions?: BusinessSolution[];
  /** 校验后的数据（成功时） */
  data?: any;
}

/**
 * 替代操作
 */
export interface AlternativeAction {
  /** 操作类型 */
  action: 'retry' | 'use_tool' | 'wait';
  /** 推荐的工具名 */
  tool?: string;
  /** 推荐理由 */
  reason: string;
  /** 使用示例 */
  example?: string;
  /** 描述 */
  description?: string;
}

/**
 * 业务解决方案
 */
export interface BusinessSolution {
  /** 解决方式 */
  approach: 'wait' | 'use_alternative' | 'reduce_quantity' | 'sell_first' | 'adjust_params';
  /** 描述 */
  description: string;
  /** 推荐工具 */
  tool?: string;
  /** 理由 */
  reason?: string;
  /** 使用示例 */
  example?: string;
  /** 调整后的参数 */
  adjustedArgs?: any;
}

// ============ 业务上下文 ============

/**
 * 业务上下文
 */
export interface BusinessContext {
  /** 当前工具名 */
  currentTool: string;
  /** 时间戳 */
  timestamp: Date;
  /** 其他动态字段 */
  [key: string]: any;
}

// ============ 工具路由 ============

/**
 * 工具路由引导
 */
export interface ToolRoutingGuide {
  /** 是否应该路由 */
  shouldRoute: boolean;
  /** 推荐的工具 */
  recommendedTool?: string;
  /** 推荐理由 */
  reason?: string;
  /** 使用示例 */
  example?: string;
  /** 推荐置信度 */
  confidence?: 'high' | 'medium' | 'low';
}

/**
 * 工具路由规则
 */
export interface ToolRoutingRule {
  /** 来源工具 */
  from: string;
  /** 触发条件 */
  condition: (error: ValidationResult) => boolean;
  /** 目标工具 */
  to: string;
  /** 推荐理由 */
  reason: string;
  /** 使用示例 */
  example: string | ((context: BusinessContext) => string);
}

// ============ 增强的工具返回结果 ============

/**
 * 增强的工具返回结果
 */
export interface EnhancedToolResult {
  /** 是否成功 */
  success: boolean;
  /** 错误信息（失败时） */
  error?: ValidationResult;
  /** 工具路由建议 */
  routing?: ToolRoutingGuide;
  /** 业务数据（成功时） */
  data?: any;
}

// ============ 三段式接口定义 ============

/**
 * Phase 1: 入参校验器接口
 *
 * 各工具必须实现此接口来定义自己的入参校验逻辑
 */
export interface InputValidator {
  /**
   * 校验输入参数
   * @param args - 工具参数
   * @returns 校验结果
   */
  validate(args: any): ValidationResult;
}

/**
 * Phase 2: 任务执行器接口
 *
 * 各工具必须实现此接口来定义自己的业务逻辑
 */
export interface TaskExecutor {
  /**
   * 执行业务逻辑
   * @param args - 工具参数（已通过入参校验）
   * @param context - 业务上下文
   * @returns 执行结果
   */
  execute(args: any, context: BusinessContext): Promise<any>;

  /**
   * 可选：业务规则校验
   * @param args - 工具参数
   * @param context - 业务上下文
   * @returns 校验结果
   */
  validateBusinessRules?(args: any, context: BusinessContext): ValidationResult | Promise<ValidationResult>;
}

/**
 * Phase 3: 出参包装器接口
 *
 * 各工具必须实现此接口来定义自己的出参校验和包装逻辑
 */
export interface OutputWrapper {
  /**
   * 校验输出数据
   * @param data - 原始执行结果
   * @param context - 业务上下文
   * @returns 校验结果
   */
  validate(data: any, context: BusinessContext): ValidationResult;

  /**
   * 可选：获取工具路由规则
   * @returns 路由规则列表
   */
  getRoutingRules?(): ToolRoutingRule[];
}

/**
 * 完整的三段式工具接口
 *
 * 工具可以选择实现此完整接口，或者只实现单独的阶段接口
 */
export interface ThreePhaseToolHandler {
  /** 工具名称 */
  name: string;

  /** Phase 1: 入参校验 */
  inputValidator: InputValidator;

  /** Phase 2: 任务执行 */
  taskExecutor: TaskExecutor;

  /** Phase 3: 出参包装 */
  outputWrapper: OutputWrapper;
}

// ============ BaseTool 类型定义 ============

/**
 * 工具元数据
 */
export interface ToolMetadata {
  /** 工具名称 */
  name: string;
  /** 工具分类 */
  category: string;
  /** 版本 */
  version: string;
  /** 超时时间（毫秒） */
  timeoutMs?: number;
  /** 依赖的其他工具 */
  dependencies?: string[];
  /** 标签 */
  tags?: string[];
}

/**
 * 工具上下文
 */
export interface ToolContext {
  /** 当前工具名称 */
  currentTool: string;
  /** 时间戳 */
  timestamp: Date;
  /** 其他上下文数据 */
  [key: string]: any;
}

/**
 * 工具响应
 */
export interface ToolResponse<T = any> {
  /** 是否成功 */
  success: boolean;
  /** 返回数据 */
  data?: T;
  /** 错误信息 */
  error?: ValidationResult;
  /** 元数据 */
  meta?: {
    toolName: string;
    duration: number;
    timestamp: string;
  };
}

/**
 * 参数定义
 */
export interface ParameterDefinition {
  /** 参数类型 */
  type: 'string' | 'number' | 'integer' | 'boolean' | 'object' | 'array';
  /** 参数描述 */
  description: string;
  /** 是否必填（只能是 true 或不填，dsh 不支持 false） */
  required?: true;
  /** 默认值 */
  default?: any;
  /** 枚举值 */
  enum?: any[];
  /** 示例 */
  example?: any;
  /** 自由键值对象（type='object' 时显式声明，DSH Schema 铁律） */
  additionalProperties?: boolean;
  /** 数组元素类型（仅当 type 为 'array' 时使用） */
  items?: {
    type: 'string' | 'number' | 'integer' | 'boolean' | 'object';
  };
}

/**
 * 工具提示词
 */
export interface ToolPrompt<TParams = any, TResult = any> {
  /** 工具描述 */
  description: string;
  /** 使用场景 */
  useCases: string[];
  /** 示例 */
  examples: Array<{
    title: string;
    params: TParams;
    expectedResult?: string;
  }>;
  /** 注意事项 */
  notes: string[];
  /** 相关工具 */
  relatedTools: string[];
  /** 参数定义 */
  parameters: Record<string, ParameterDefinition>;
  /** 输出定义 */
  output: {
    /** 输出 Schema */
    schema: any;
    /** 渲染函数 */
    render?: (args: TParams, value: TResult) => Array<{ type: string; text: string }>;
  };
}

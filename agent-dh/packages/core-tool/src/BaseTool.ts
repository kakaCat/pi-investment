/**
 * BaseTool 抽象基类
 *
 * 所有工具必须继承此类，框架强制执行三个步骤：
 * 1. 校验参数 (validate)
 * 2. 执行任务 (execute)
 * 3. 包装返回数据 (wrap)
 */

import type {
  ToolMetadata,
  ToolPrompt,
  ToolContext,
  ToolResponse,
  ValidationResult
} from './types';

export abstract class BaseTool<TParams = any, TResult = any> {
  /**
   * 工具元数据（子类必须提供）
   */
  protected abstract readonly metadata: ToolMetadata;

  /**
   * 工具提示词（子类必须提供）
   */
  protected abstract readonly prompt: ToolPrompt<TParams, TResult>;

  /**
   * Phase 1: 校验参数（子类必须实现）
   */
  protected abstract validate(args: TParams): ValidationResult;

  /**
   * Phase 2: 执行任务（子类必须实现）
   */
  protected abstract execute(args: TParams, context: ToolContext): Promise<TResult>;

  /**
   * Phase 3: 包装返回数据（子类必须实现）
   */
  protected abstract wrap(result: TResult, context: ToolContext): ToolResponse<TResult>;

  /**
   * 统一调用入口（框架自动执行三个步骤）
   */
  async call(args: TParams, external?: Record<string, unknown>): Promise<ToolResponse<TResult>> {
    const startTime = Date.now();
    const context: ToolContext = {
      currentTool: this.metadata.name,
      timestamp: new Date(),
      ...args,
      ...(external ?? {}),
    };

    try {
      // Step 1: 校验参数
      const validationResult = this.validate(args);
      if (!validationResult.success) {
        return {
          success: false,
          error: validationResult,
          meta: {
            toolName: this.metadata.name,
            duration: Date.now() - startTime,
            timestamp: new Date().toISOString(),
          },
        };
      }

      // Step 2: 执行任务
      const result = await this.execute(args, context);

      // Step 3: 包装返回数据
      const response = this.wrap(result, context);

      // 添加执行元数据
      return {
        ...response,
        meta: {
          toolName: this.metadata.name,
          duration: Date.now() - startTime,
          timestamp: new Date().toISOString(),
        },
      };
    } catch (error: any) {
      return {
        success: false,
        error: {
          success: false,
          errorType: 'EXECUTION_ERROR' as any,
          issue: error.message || String(error),
          guide: '工具执行失败',
        },
        meta: {
          toolName: this.metadata.name,
          duration: Date.now() - startTime,
          timestamp: new Date().toISOString(),
        },
      };
    }
  }

  /**
   * 获取工具元数据
   */
  getMetadata(): ToolMetadata {
    return this.metadata;
  }

  /**
   * 获取工具提示词
   */
  getPrompt(): ToolPrompt<TParams, TResult> {
    return this.prompt;
  }

  /**
   * 转换为 DSH Tool 定义
   */
  toDSHToolDefinition() {
    return {
      name: this.metadata.name,
      description: this.prompt.description,
      parameters: this.convertParameters(this.prompt.parameters),
      // render 默认注入：prompt 未定义 render 时回退为 JSON 文本块，
      // 避免 DSH 执行链因 output.render 缺失而失败
      output: {
        ...this.prompt.output,
        schema: this.prompt.output?.schema ? this.stripDslUnsupported(this.prompt.output.schema) : undefined,
        render: this.prompt.output?.render
          ?? ((_args: TParams, data: TResult) => [{ type: 'text', text: JSON.stringify(data, null, 2) }]),
      },
      timeoutMs: this.metadata.timeoutMs || 10000,
      execute: async (args: TParams, exec?: any) => {
        const response = await this.call(args, { exec });

        if (!response.success) {
          // 错误提取：兼容 string / {issue} / {error:{issue}} 三种形态
          const err: any = response.error;
          const issue =
            typeof err === 'string' ? err
            : err?.issue ? err.issue
            : err?.error?.issue ? err.error.issue
            : '工具执行失败';
          throw new Error(issue);
        }

        return response.data;
      },
    } as any;
  }

  /**
   * 转换参数定义为 DSH 格式
   */
  private convertParameters(params: Record<string, any>): any {
    const result: any = {};
    for (const [key, def] of Object.entries(params)) {
      result[key] = this.normalizeParamSchema(def);
    }
    return result;
  }

  /** 剥离 value schema DSL 不支持的关键字（required 数组），递归处理嵌套 schema */
  private stripDslUnsupported(schema: any): any {
    if (!schema || typeof schema !== 'object') return schema;
    const out: any = {};
    for (const [k, v] of Object.entries(schema)) {
      if (k === 'required') continue;
      if (Array.isArray(v)) {
        out[k] = v.map((item) => item && typeof item === 'object' ? this.stripDslUnsupported(item) : item);
      } else if (v && typeof v === 'object') {
        out[k] = this.stripDslUnsupported(v);
      } else {
        out[k] = v;
      }
    }
    return out;
  }

  /** 规范化参数属性为完整 JSON Schema 子节点（递归处理 items/additionalProperties） */
  private normalizeParamSchema(def: any): any {
    const converted: any = { type: def.type };

    // description 仅在为字符串时输出（避免 undefined 键触发 dsh-tools 注解校验）
    if (typeof def.description === 'string') {
      converted.description = def.description;
    }

    // dsh-tools 扁平 spec：属性级 required 布尔（defineTool 会提升为顶层数组）
    if (def.required === true) {
      converted.required = true;
    }

    // 只包含有值的可选字段
    if (def.default !== undefined) converted.default = def.default;
    if (def.enum !== undefined) converted.enum = def.enum;
    // 注意：dsh-tools value schema DSL 不支持 minimum/maximum/pattern，不输出
    if (def.additionalProperties !== undefined) converted.additionalProperties = def.additionalProperties;

    // 数组元素 schema 递归规范化（嵌套 object 需要 additionalProperties）
    if (def.items !== undefined) {
      converted.items = def.items && typeof def.items === 'object'
        ? this.normalizeParamSchema(def.items)
        : def.items;
    }

    return converted;
  }
}

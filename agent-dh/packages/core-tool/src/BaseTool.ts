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
  async call(args: TParams): Promise<ToolResponse<TResult>> {
    const startTime = Date.now();
    const context: ToolContext = {
      currentTool: this.metadata.name,
      timestamp: new Date(),
      ...args,
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
        render: this.prompt.output?.render
          ?? ((_args: TParams, data: TResult) => [{ type: 'text', text: JSON.stringify(data, null, 2) }]),
      },
      timeoutMs: this.metadata.timeoutMs || 10000,
      execute: async (args: TParams, _exec?: any) => {
        const response = await this.call(args);

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
      const converted: any = {
        type: def.type,
        description: def.description,
      };

      // 只在 required 为 true 时才包含（dsh 不支持 required: false 或 undefined）
      if (def.required === true) {
        converted.required = true;
      }

      // 只包含有值的可选字段
      if (def.default !== undefined) {
        converted.default = def.default;
      }
      if (def.enum !== undefined) {
        converted.enum = def.enum;
      }

      result[key] = converted;
    }
    return result;
  }
}

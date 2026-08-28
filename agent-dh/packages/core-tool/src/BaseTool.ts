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
      output: this.prompt.output,
      timeoutMs: this.metadata.timeoutMs || 10000,
      execute: async (args: TParams) => {
        const response = await this.call(args);

        if (!response.success) {
          throw new Error(response.error?.issue || '工具执行失败');
        }

        return response.data;
      },
    };
  }

  /**
   * 转换参数定义为 DSH 格式
   */
  private convertParameters(params: Record<string, any>): any {
    const result: any = {};
    for (const [key, def] of Object.entries(params)) {
      result[key] = {
        type: def.type,
        description: def.description,
        required: def.required,
        default: def.default,
        enum: def.enum,
      };
    }
    return result;
  }
}

/**
 * SelfRestartTool - 重启工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import { selfRestartPrompt, SelfRestartParams, SelfRestartResult } from './prompt';

export class SelfRestartTool extends BaseTool<SelfRestartParams, SelfRestartResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'self_restart',
    category: 'lifecycle',
    version: '1.0.0',
    timeoutMs: 5000,
  };

  protected readonly prompt = selfRestartPrompt;

  constructor(private scheduleRestart: (reason: string, preserveContext: boolean, originAgentId?: string | null) => Promise<any>) {
    super();
  }

  protected validate(args: SelfRestartParams): ValidationResult {
    if (!args.reason || args.reason.trim().length === 0) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.VALIDATION_ERROR,
          field: 'reason',
          issue: 'reason 不能为空',
          expected: 'non-empty string',
        },
      };
    }
    return { success: true };
  }

  protected async execute(args: SelfRestartParams, context: ToolContext): Promise<SelfRestartResult> {
    const preserveContext = args.preserve_context ?? false;
    // 发起会话 id（exec.agent.id === session id），重启后用于续跑消息回投
    const originAgentId: string | null = (context as any).exec?.agent?.id ?? null;
    await this.scheduleRestart(args.reason, preserveContext, originAgentId);

    return {
      success: true,
      message: `重启已调度，原因：${args.reason}`,
      restart_scheduled: true,
    };
  }

  protected wrap(result: SelfRestartResult): ToolResponse<SelfRestartResult> {
    return { success: true, data: result };
  }
}

/**
 * SelfStatusTool - 状态查询工具
 */

import { BaseTool } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import { selfStatusPrompt, SelfStatusParams, SelfStatusResult } from './prompt';

export class SelfStatusTool extends BaseTool<SelfStatusParams, SelfStatusResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'self_status',
    category: 'lifecycle',
    version: '1.0.0',
    timeoutMs: 3000,
  };

  protected readonly prompt = selfStatusPrompt;

  constructor(private getStatus: (detailed: boolean) => Promise<any>) {
    super();
  }

  protected validate(args: SelfStatusParams): ValidationResult {
    return { success: true };
  }

  protected async execute(args: SelfStatusParams, _context: ToolContext): Promise<SelfStatusResult> {
    const detailed = args.detailed ?? false;
    const status = await this.getStatus(detailed);

    return {
      success: true,
      status: status.status || 'running',
      uptime: status.uptime || 0,
      health: status.health || {},
    };
  }

  protected wrap(result: SelfStatusResult): ToolResponse<SelfStatusResult> {
    return { success: true, data: result };
  }
}

import { BaseTool, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { watchListPrompt, type WatchListParams } from './prompt';

export class WatchListTool extends BaseTool<WatchListParams, any[]> {
  protected readonly metadata: ToolMetadata = {
    name: 'watch_list',
    category: 'intelligence',
    version: '1.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = watchListPrompt;

  constructor(private qv2Client: QuantsysV2Client) {
    super();
  }

  protected validate(params: WatchListParams): ValidationResult {
    // 无参数，直接返回成功
    return { success: true };
  }

  protected async execute(params: WatchListParams, context: ToolContext): Promise<any[]> {
    const result = await this.qv2Client.listWatchRules();
    const rules = Array.isArray(result) ? result : (result as any)?.rules ?? [];
    return rules;
  }

  protected wrap(data: any[], context: ToolContext): ToolResponse<any[]> {
    const rules = Array.isArray(data) ? data : [];
    return {
      success: true,
      data: rules,
      message: `共找到 ${rules.length} 条盯盘规则`,
      metadata: {
        total: rules.length,
        enabled: rules.filter((r: any) => r?.enabled).length,
        disabled: rules.filter((r: any) => !r?.enabled).length,
      },
    };
  }
}

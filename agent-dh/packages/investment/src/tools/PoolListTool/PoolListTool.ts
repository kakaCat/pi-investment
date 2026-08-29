import { BaseTool } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { poolListPrompt, PoolListParams, PoolListResult } from './prompt';

export class PoolListTool extends BaseTool<PoolListParams, PoolListResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'pool_list',
    category: 'data',
    version: '2.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = poolListPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: PoolListParams): ValidationResult {
    return { success: true };
  }

  protected async execute(
    args: PoolListParams,
    context: ToolContext
  ): Promise<PoolListResult> {
    const pools: any[] = (await this.qv2.listPools()) as any[];
    // 后端部分池的 description 为 SQL NULL（JSON null），归一化为空串
    return (pools ?? []).map((p: any) => ({ ...p, description: p?.description ?? '' }));
  }

  protected wrap(data: PoolListResult): ToolResponse<PoolListResult> {
    return { success: true, data };
  }
}

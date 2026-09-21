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
    // TODO: 处理非200响应 - 添加错误处理或降级逻辑（404/500等），参考 pe_percentile 改进方案
    // 每个工具的业务语义不同，需要根据具体场景设计降级策略
    args: PoolListParams,
    context: ToolContext
  ): Promise<PoolListResult> {
    const pools: any[] = (await this.qv2.listPools()) as any[];
    // 后端部分池的 description 为 SQL NULL（JSON null），归一化为空串
    // 2026-09-11 修复（REQ-342799）：后端 /api/pools 列表字段是 symbol_count（实测 26 池均有值），
    // 旧实现只透传 → 工具 schema 声明的 member_count 恒为 undefined，pool_list 看不到池子规模。
    return (pools ?? []).map((p: any) => ({
      ...p,
      description: p?.description ?? '',
      member_count: p?.member_count ?? p?.symbol_count ?? (Array.isArray(p?.symbols) ? p.symbols.length : null),
    }));
  }

  protected wrap(data: PoolListResult): ToolResponse<PoolListResult> {
    return { success: true, data };
  }
}

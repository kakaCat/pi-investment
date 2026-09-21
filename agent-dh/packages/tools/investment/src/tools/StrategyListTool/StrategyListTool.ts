import { BaseTool } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { strategyListPrompt, StrategyListParams, StrategyListResult } from './prompt';

export class StrategyListTool extends BaseTool<StrategyListParams, StrategyListResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'strategy_list',
    category: 'data',
    version: '2.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = strategyListPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: StrategyListParams): ValidationResult {
    if (args.source !== undefined) {
      const validSources = ['builtin', 'user'];
      if (!validSources.includes(args.source)) {
        return {
          success: false,
          errorType: 'INPUT_ERROR' as any,
          field: 'source',
          issue: 'source 必须是 builtin 或 user',
          received: args.source,
          expected: 'builtin | user',
        };
      }
    }
    return { success: true };
  }

  protected async execute(
    // TODO: 处理非200响应 - 添加错误处理或降级逻辑（404/500等），参考 pe_percentile 改进方案
    // 每个工具的业务语义不同，需要根据具体场景设计降级策略
    args: StrategyListParams,
    context: ToolContext
  ): Promise<StrategyListResult> {
    // 2026-09-13 修复：client.listStrategies 的签名是**对象参数**，此前用位置参数调用
    // （args.source 被当成 params 对象直接发出）→ 只要传 source 就 400，且被工具误报为"后端不可达"。
    const result = await this.qv2.listStrategies({ source: args.source, code_type: args.code_type });
    // 2026-08-30 修复：后端策略 description/name 可能为 null，而 DSH 输出 schema 要求 string。
    // 在边界处把空值归一化为空字符串，保证 schema 校验通过。
    if (Array.isArray((result as any).items)) {
      (result as any).items = (result as any).items.map((it: any) => {
        const o: Record<string, any> = {};
        for (const [k, v] of Object.entries(it ?? {})) {
          if (v === null) o[k] = k === 'id' || typeof v === 'number' ? v : '';
          else o[k] = v;
        }
        for (const k of ['name', 'description', 'strategyType', 'type', 'status']) {
          if (o[k] === undefined) o[k] = '';
          if (typeof o[k] !== 'string') o[k] = String(o[k] ?? '');
        }
        return o;
      });
    }
    return result as StrategyListResult;
  }

  protected wrap(data: StrategyListResult): ToolResponse<StrategyListResult> {
    return { success: true, data };
  }
}

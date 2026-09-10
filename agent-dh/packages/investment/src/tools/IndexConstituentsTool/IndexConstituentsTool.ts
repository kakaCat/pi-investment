/**
 * IndexConstituentsTool - 指数成分股（基准成分池）
 */

import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { indexConstituentsPrompt, type IndexConstituentsParams, type IndexConstituentsResult } from './prompt';

export class IndexConstituentsTool extends BaseTool<IndexConstituentsParams, IndexConstituentsResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'index_constituents',
    category: 'data',
    version: '1.0.0',
    timeoutMs: 30000,
  };

  protected readonly prompt = indexConstituentsPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: IndexConstituentsParams): ValidationResult {
    if (!args?.symbol || !/^\d{6}$/.test(args.symbol)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: `无效的指数代码: ${args?.symbol}`,
        expected: '6位数字指数代码，如 000300（沪深300）',
        example: '000300',
      };
    }
    return { success: true };
  }

  protected async execute(args: IndexConstituentsParams, _context: ToolContext): Promise<IndexConstituentsResult> {
    const res: any = await (this.qv2 as any).getIndexConstituents(args.symbol);

    // 失败必须显式失败：'数据源故障' 与 '该指数无成分' 语义不同，静默返回空清单会导致误判
    if (!res || res.success !== true) {
      const why = res?.error || res?.message || '未知原因';
      throw new Error(`指数成分查询失败（${args.symbol}）：${why}。禁止据此判定『该指数无成分股』——数据源失败不等于空结果。`);
    }

    const payload: any = res.data ?? res;
    const rows: any[] = Array.isArray(payload) ? payload : (payload?.data ?? []);
    const codes = rows
      .map((r: any) => String(r?.symbol ?? r?.code ?? r ?? '').trim())
      .filter((c: string) => /^\d{6}$/.test(c));

    if (codes.length === 0) {
      throw new Error(`指数成分返回 0 条有效代码（${args.symbol}）：上游未提供该指数成分数据，不得当作『无成分股』使用。`);
    }

    return sanitizeLossless({
      symbol: args.symbol,
      count: new Set(codes).size,
      constituents: [...new Set(codes)],
      available: true,
      source: payload?.source ?? res.source ?? 'provider',
      note: '成分股代码清单（不含权重/调样日期）；数据源 provider(akshare)',
    }) as IndexConstituentsResult;
  }
}

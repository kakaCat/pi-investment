/**
 * SlippageReportTool - 滑点报告工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { AgentOSClient } from '@pi-investment/agent-os-client';
import { slippageReportPrompt, SlippageReportParams, SlippageReportResult } from './prompt';

/**
 * 滑点报告工具类
 */
export class SlippageReportTool extends BaseTool<SlippageReportParams, SlippageReportResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'slippage_report',
    category: 'trading',
    version: '1.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = slippageReportPrompt;

  constructor(private osClient: AgentOSClient) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: SlippageReportParams): ValidationResult {
    // symbol 可选，但如果提供必须是字符串
    if (args.symbol !== undefined && args.symbol !== null) {
      if (typeof args.symbol !== 'string' || args.symbol.trim() === '') {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'symbol',
          issue: 'symbol 必须是非空字符串',
          received: args.symbol,
          expected: 'string',
          example: '600519',
        };
      }

      // 检查 symbol 格式（6位数字）
      if (!/^\d{6}$/.test(args.symbol)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'symbol',
          issue: 'symbol 必须是6位数字股票代码',
          received: args.symbol,
          expected: '6位数字',
          example: '600519',
        };
      }
    }

    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(args: SlippageReportParams, _context: ToolContext): Promise<SlippageReportResult> {
    // 从 osClient.memory 检索滑点记录
    const searchResult: any = await this.osClient.memory.search({
      query: args.symbol ? `slippage ${args.symbol}` : 'slippage',
      category: 'episode',
      limit: 1000,
    });

    const memories = searchResult?.memories || [];

    // 过滤出滑点记录
    const slippageRecords = memories
      .filter((m: any) => m.scope === 'trade:slippage')
      .map((m: any) => {
        try {
          return typeof m.payload === 'string' ? JSON.parse(m.payload) : m.payload;
        } catch {
          return null;
        }
      })
      .filter((r: any) => r && r.slippage_pct !== undefined);

    // 如果指定了 symbol，过滤
    const filteredRecords = args.symbol
      ? slippageRecords.filter((r: any) => r.symbol === args.symbol)
      : slippageRecords;

    if (filteredRecords.length === 0) {
      return {
        total_fills: 0,
        avg_slippage_pct: 0,
        max_slippage_pct: 0,
        by_symbol: [],
      };
    }

    // 计算统计数据
    const totalFills = filteredRecords.length;
    const avgSlippage =
      filteredRecords.reduce((sum: number, r: any) => sum + r.slippage_pct, 0) / totalFills;
    const maxSlippage = Math.max(...filteredRecords.map((r: any) => Math.abs(r.slippage_pct)));

    // 按标的分组统计
    const bySymbol = new Map<string, any[]>();
    for (const record of filteredRecords) {
      const sym = record.symbol;
      if (!bySymbol.has(sym)) {
        bySymbol.set(sym, []);
      }
      bySymbol.get(sym)!.push(record);
    }

    const bySymbolArray = Array.from(bySymbol.entries()).map(([symbol, records]) => ({
      symbol,
      fills: records.length,
      avg_slippage_pct: records.reduce((sum, r) => sum + r.slippage_pct, 0) / records.length,
      max_slippage_pct: Math.max(...records.map((r) => Math.abs(r.slippage_pct))),
    }));

    return {
      total_fills: totalFills,
      avg_slippage_pct: Number(avgSlippage.toFixed(3)),
      max_slippage_pct: Number(maxSlippage.toFixed(3)),
      by_symbol: bySymbolArray,
    };
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: SlippageReportResult, _context: ToolContext): ToolResponse<SlippageReportResult> {
    // 检查必需字段
    const requiredFields = ['total_fills', 'avg_slippage_pct', 'max_slippage_pct', 'by_symbol'];
    const missingFields: string[] = [];

    for (const field of requiredFields) {
      if (result[field as keyof SlippageReportResult] === undefined) {
        missingFields.push(field);
      }
    }

    if (missingFields.length > 0) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.OUTPUT_ERROR,
          field: missingFields.join(', '),
          issue: `返回数据缺少必需字段`,
          expected: `包含所有必需字段: ${requiredFields.join(', ')}`,
        },
      };
    }

    // 检查类型
    if (typeof result.total_fills !== 'number' ||
        typeof result.avg_slippage_pct !== 'number' ||
        typeof result.max_slippage_pct !== 'number') {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.OUTPUT_ERROR,
          field: 'total_fills/avg_slippage_pct/max_slippage_pct',
          issue: '这些字段必须是数字',
          expected: 'number',
        },
      };
    }

    if (!Array.isArray(result.by_symbol)) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.OUTPUT_ERROR,
          field: 'by_symbol',
          issue: 'by_symbol 必须是数组',
          expected: 'array',
        },
      };
    }

    return {
      success: true,
      data: result,
    };
  }
}

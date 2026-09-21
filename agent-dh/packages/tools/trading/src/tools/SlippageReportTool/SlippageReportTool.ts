/**
 * SlippageReportTool - 滑点报告工具
 */

import { BaseTool, ErrorType, DEFAULT_AGENT_ACCOUNT } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { OsMemoryStore } from '../../index';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
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

  constructor(private qv2: QuantsysV2Client, private osClient: OsMemoryStore) {
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
    // 2026-09-13（w-a9ec14d7）**改数据源**：原先只读 Agent OS 记忆 scope=trade:slippage，
    // 但全仓没有任何写入方 → 本工具此前恒返回 0 条（能力存在但没接线）。
    // 现优先读 v2 的挂单记录（decision_price / fill_price / slippage_bps 已落在挂单行上），
    // 记忆通道保留为兜底，并在返回里用 source 字段标明本次数据来自哪。
    const account = (args as any).account_name || DEFAULT_AGENT_ACCOUNT;
    try {
      const res: any = await (this.qv2 as any).getSlippageReport(account, {
        days: (args as any).days ?? 30, symbol: args.symbol });
      if (res && res.success === true && res.data) {
        return { ...res.data, source: 'v2挂单记录(simulation_pending_orders)' } as unknown as SlippageReportResult;
      }
    } catch { /* v2 不可用则落到记忆兜底 */ }

    // 从 osClient 检索滑点记录（兜底通道）
    const searchResult: any = await this.osClient.searchMemory({
      q: args.symbol ? `slippage ${args.symbol}` : 'slippage',
      kind: 'episode',
      limit: 1000,
    });

    const memories = searchResult?.items || [];

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
    // ⚠️ 2026-09-13（w-c8cae280）**契约已随数据源迁移，但校验没跟上**：
    //   本工具的数据源已从"Agent OS 记忆 scope=trade:slippage"改为"v2 挂单记录"（见 execute），
    //   v2 返回的是 **bps 口径 + records 明细**（avg_slippage_bps / max_slippage_bps / cost_bps_total / records），
    //   而这里仍要求旧记忆通道的 **pct 口径**字段（avg_slippage_pct / max_slippage_pct / by_symbol）→
    //   只要走 v2 通道就必然报"返回数据缺少必需字段"，即**工具在正常路径上不可用**（实测）。
    // 现按当前契约校验：必需 total_fills + records；旧 pct 字段仅在其存在时校验类型（兼容兜底通道）。
    const requiredFields = ['total_fills', 'records'];
    const missingFields: string[] = [];

    for (const field of requiredFields) {
      if ((result as any)[field] === undefined) {
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

    // 检查类型：数字字段允许 null（无成交/无决策价时后端返回 null 是**正常语义**，
    // 不能因为 null 就判"必须是数字"——schema 必须比数据宽，而不是比数据严）。
    const numericFields = ['total_fills', 'missing_decision_price', 'avg_slippage_bps',
                           'max_slippage_bps', 'cost_bps_total', 'avg_slippage_pct', 'max_slippage_pct'];
    for (const f of numericFields) {
      const v = (result as any)[f];
      if (v !== undefined && v !== null && typeof v !== 'number') {
        return {
          success: false,
          error: {
            success: false,
            errorType: ErrorType.OUTPUT_ERROR,
            field: f,
            issue: '该字段必须是数字或 null',
            expected: 'number | null',
          },
        };
      }
    }
    if ((result as any).records !== undefined && !Array.isArray((result as any).records)) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.OUTPUT_ERROR,
          field: 'records',
          issue: 'records 必须是数组',
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
